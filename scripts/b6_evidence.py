"""Small acceptance evidence helpers; no model calls or scientific state writes."""
import hashlib
import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from scidiscovery.artifact_agent.storage.control_io import bounded_control_io, connect_database
from scidiscovery.artifact_agent.service.progression_records import hydrate_control_row
from scidiscovery.artifact_agent.service.research_loops import current_loop, loop_usage


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
        separators=(',', ':')).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def verify_prior_turns(rpc, references):
    """No new model work until the interrupted acceptance's exact turns ended."""
    evidence=[]
    for reference in references:
        thread=rpc('thread/read',dict(threadId=reference['thread_id'],includeTurns=True))['thread']
        turn=next((v for v in thread.get('turns',[]) if v['id']==reference['turn_id']),None)
        if thread.get('id')!=reference['thread_id'] or turn is None:
            raise RuntimeError('prior_native_turn_not_found')
        evidence.append(dict(**reference,status=turn['status']))
        if turn['status'] not in {'completed','failed','interrupted'}:
            raise RuntimeError('prior_native_turn_not_terminal; do_not_start_another_case')
    return evidence


def write(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))
    temporary.replace(path)


def _read_database(candidate, database, read_transaction, deadline=None):
    """Retry only a complete read snapshot, within one absolute deadline."""
    path = Path(candidate) / 'state/database' / (database + '.sqlite3')
    deadline = min(time.monotonic() + 2., deadline if deadline is not None else float('inf'))
    with bounded_control_io(wait_seconds=lambda: .1, remaining_seconds=lambda: deadline-time.monotonic()):
        while True:
            try:
                with closing(connect_database(path.resolve().as_uri() + '?mode=ro', uri=True,
                                              deadline_monotonic=deadline)) as db:
                    db.row_factory = sqlite3.Row
                    db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
                    db.execute('BEGIN')  # References and records share one read snapshot.
                    return read_transaction(db)
            except sqlite3.OperationalError as error:
                code = getattr(error, 'sqlite_errorcode', 0) & 0xff
                remaining = deadline-time.monotonic()
                if code not in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED} or remaining <= 0:
                    raise
                # The failed connection has closed; discard partial hydration.
                time.sleep(min(.01, remaining))


def _json_columns(row):
    # SQLite stores canonical JSON as BLOB in production. Normalize only
    # declared JSON columns for evidence serialization; preserve all other
    # binary data and reject invalid UTF-8 instead of stringifying bytes.
    return {key: value.decode('utf-8') if key.endswith('_json') and isinstance(value, bytes)
            else value for key, value in dict(row).items()}


def rows(candidate, database, query, args=()):
    return _read_database(candidate, database,
        lambda db: [_json_columns(row) for row in db.execute(query, args)])


def control_rows(candidate, query='SELECT * FROM scheduler_progression', args=(), *, accounting=False,
                 loop_id=None, deadline=None):
    # Original A6 snapshots predate progression. Absence is a valid fresh
    # baseline; malformed existing tables still raise instead of hiding errors.
    def read_transaction(db):
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='scheduler_progression'").fetchone():
            return []
        values = []
        for row in db.execute(query, args):
            row = _json_columns(row)
            if accounting and row.get('checkpoint_json'):
                checkpoint = json.loads(row['checkpoint_json'])
                if loop_id is not None and checkpoint.get('current_loop_id') != loop_id:
                    raise ValueError('acceptance_research_loop_changed')
                if checkpoint.get('current_loop_id'):
                    row = hydrate_control_row(db, row, accounting_only=True)
                elif checkpoint.get('detail_collections'):
                    raise ValueError('acceptance_usage_requires_exact_research_loop')
            values.append(row)
        return values
    return _read_database(candidate, 'scheduler-bindings', read_transaction, deadline)


def run_snapshot(candidate):
    return rows(candidate, 'runs', 'SELECT run_id,state,output_ref_json FROM runs ORDER BY run_id')


def participants(candidate, run_ids):
    workers, helpers = [], []
    for run in run_ids:
        workers += rows(candidate, 'runs', 'SELECT * FROM worker_connections WHERE run_id=?', (run,))
        # request_json contains original subproblem text, not needed by the audit.
        helpers += rows(candidate, 'runs', 'SELECT run_id,name,platform_session,owner_thread,thread_id,admitted_at,released_at FROM worker_participants WHERE run_id=?', (run,))
    return workers, helpers


def sealed_outputs(candidate, runs):
    evidence = []
    for run in runs:
        if run['state'] != 'completed' or not run['output_ref_json']:
            raise ValueError('run_not_sealed')
        ref = json.loads(run['output_ref_json'])
        sha = ref['sha256']
        path = Path(candidate) / 'state/artifacts/sha256' / sha[:2] / sha[2:]
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != sha:
                raise ValueError('sealed_bytes_mismatch')
        evidence.append(dict(run_id=run['run_id'], reference=ref, path=str(path)))
    return evidence


def usage_report(journey, workers, helpers, progression=None):
    """Never treat absent counters as zero or add cached input twice."""
    path = Path(journey) / 'usage.json'
    raw = read(path) if path.exists() else {}
    checkpoint = json.loads(progression['checkpoint_json']) if progression else {}
    loop_id = current_loop(checkpoint)
    authorization_path = Path(journey)/'loop-authorization.json'
    if progression and authorization_path.exists() and read(authorization_path)['id'] != loop_id:
        raise ValueError('acceptance_research_loop_changed')
    if checkpoint.get('detail_collections', {}).get('usage_records') and 'usage_records' not in checkpoint:
        raise ValueError('acceptance_usage_requires_hydration')
    records = loop_usage(checkpoint, loop_id)
    if loop_id:
        run_ids = {v.get('run_id') for v in checkpoint.get('admissions', {}).values()
            if v.get('loop_id') == loop_id and not v.get('interactive_session_id')}
        workers = [v for v in workers if v.get('run_id') in run_ids]
        helpers = [v for v in helpers if v.get('run_id') in run_ids]
        records = {key:value for key,value in records.items() if not value.get('interactive_session_id')}
    identities = {v['thread_id']:'worker' for v in workers if v.get('thread_id')}
    for value in helpers:
        if value.get('thread_id'):
            if value['thread_id'] in identities:
                raise ValueError('acceptance_usage_identity_conflict')
            identities[value['thread_id']] = 'helper'
    host = json.loads(progression.get('host_json') or 'null') if progression else None
    if host:
        if host['thread_id'] in identities:
            raise ValueError('acceptance_usage_identity_conflict')
        identities[host['thread_id']] = 'root'
    for identity, item in records.items():
        if item['role'] not in {'root','worker','helper'} or (identity in identities and item['role'] != identities[identity]):
            raise ValueError('acceptance_usage_identity_conflict')
        if loop_id and (item.get('thread_id') != identity or item.get('owner') != progression['instance_id']
                        or (item['role'] != 'root' and identity not in identities)):
            raise ValueError('acceptance_usage_identity_unbound')
    started_path = Path(journey) / 'started-threads.json'
    started = read(started_path) if started_path.exists() else []
    for identity in started:
        identities.setdefault(identity, 'unattributed')
    if raw.get('root_thread') and (not started_path.exists() or raw['root_thread'] in started or raw['root_thread'] in raw.get('threads', {})):
        identities[raw['root_thread']] = 'setup_root' if progression else 'root'
    observed = {}
    for identity, total in raw.get('threads', {}).items():
        if loop_id and identity not in identities and identity not in records and identity not in started:
            continue  # An unrelated observer notification is not this loop's usage.
        if loop_id and identities.get(identity) in {'root','worker','helper'}:
            continue  # Cumulative notifications cannot replace loop-owned deltas.
        values = {key:total.get(wire) for key, wire in (
            ('input_tokens','inputTokens'), ('cached_input_tokens','cachedInputTokens'), ('output_tokens','outputTokens'))}
        observed[identity] = dict(role=identities.get(identity, 'unattributed'), tokens=values)
    for identity, item in records.items():
        identities[identity] = item['role']
        tokens = item['counted_tokens']
        if set(tokens) != {'input_tokens','cached_input_tokens','output_tokens'}:
            raise ValueError('acceptance_usage_invalid')
        observed[identity] = dict(role=item['role'], tokens=tokens, partial=item['has_gaps'])
    if checkpoint.get('loop_authorizations', {}).get(loop_id, {}).get('unmeasured_frontend_root'):
        identities['unmeasured-frontend-participants'] = 'unattributed'
    if progression and not any(v['role']=='root' for v in observed.values()):
        identities['unmeasured-background-root'] = 'root'
    for identity, item in observed.items():
        identities.setdefault(identity, item['role'])
    groups = {}
    for identity, role in identities.items():
        group = groups.setdefault(role, dict(input_tokens=0, cached_input_tokens=0, output_tokens=0, missing_threads=0, observed_threads=0))
        item = observed.get(identity)
        if item is None or item.get('partial') or any(type(v) is not int for v in item['tokens'].values()):
            group['missing_threads'] += 1
        if item:
            group['observed_threads'] += 1
            for key, value in item['tokens'].items():
                if type(value) is int:
                    group[key] += value
    for role, group in groups.items():
        group['coverage'] = 'partial' if group['missing_threads'] else 'observed'
        group['input_plus_output'] = group['input_tokens'] + group['output_tokens']
        if not group['observed_threads']:
            for key in ('input_tokens','cached_input_tokens','output_tokens','input_plus_output'):
                group[key] = None
    # These are received notification envelopes, not necessarily model-visible
    # tool output. An empty observer must not claim zero output across threads.
    items = [item for item in raw.get('items', []) if item.get('type') in
        {'mcpToolCall', 'dynamicToolCall', 'commandExecution', 'custom_tool_call_output', 'function_call_output'}]
    tool_observation = dict(source='host_notifications', coverage='partial' if items else 'missing',
        notification_bytes=sum(item.get('bytes', 0) for item in items),
        observed_items=len(items), model_visible_text_bytes=None)
    return dict(groups=groups, coverage='observed' if groups and 'unattributed' not in groups and all(v['coverage']=='observed' for v in groups.values()) else 'partial',
        accounting_scope=dict(instance_id=progression.get('instance_id'), loop_id=loop_id,
            source='scheduler_progression_details' if checkpoint.get('_accounting_projection') else 'inline_checkpoint') if progression else None,
        tool_result_bytes=None, tool_output_observation=tool_observation,
        limitations=['No monetary cost estimate.', 'Cumulative native usage does not establish per-request billing.',
            'Tool bytes are not tokens; received notifications may omit native output.'])


def token_totals(usage, *, require_complete=True):
    """Cached input is included once; partial telemetry is only a lower bound."""
    if require_complete and (usage.get('coverage') != 'observed' or not usage.get('groups')):
        raise ValueError('acceptance_usage_incomplete')
    total = uncached = 0
    for group in usage.get('groups', {}).values():
        values = [group.get(key) for key in ('input_tokens', 'cached_input_tokens', 'output_tokens')]
        if any(type(value) is not int or value < 0 for value in values):
            if require_complete:
                raise ValueError('acceptance_usage_invalid')
            continue
        inputs, cached, outputs = values
        if cached > inputs:
            raise ValueError('acceptance_usage_invalid')
        total += inputs + outputs
        uncached += inputs - cached + outputs
    return dict(total_tokens=total, uncached_tokens=uncached)


def budget_assessment(usage, limits, execution_seconds=None):
    """Observed resource outcome, independent of sealed science or process exit."""
    totals = token_totals(usage, require_complete=False)
    complete = usage.get('coverage') == 'observed' and bool(usage.get('groups'))
    missing = [] if complete else ['usage']
    if type(execution_seconds) in (int, float) and 0 <= execution_seconds < float('inf'):
        totals['execution_seconds'] = execution_seconds
    else:
        missing.append('execution_seconds')
    reached = [key for key, limit in limits.items() if key in totals and totals[key] >= limit]
    return dict(status='failed' if reached else 'not_observed' if missing else 'passed',
        observed=totals, coverage=usage.get('coverage', 'missing'), reached=reached, missing=missing,
        limitation='Delayed usage is an observed lower bound, not a hard token limit.')


def verdict(checks, required):
    values = [checks.get(key, 'not_observed') for key in required]
    if 'failed' in values:
        return 'failed'
    if 'blocked' in values:
        return 'blocked'
    return 'passed' if values and all(v=='passed' for v in values) else 'not_observed'


def compare(left, right):
    same = all(left.get(key)==right.get(key) and left.get(key) is not None for key in
        ('baseline_digest','conditions_digest','objective_digest'))
    quality = all(v.get('checks',{}).get('quality')=='passed' and v.get('status')=='passed' for v in (left,right))
    measured_all = all(v.get('usage',{}).get('coverage')=='observed' for v in (left,right))
    result = dict(comparable=same and quality and measured_all, quality_passed=quality,
        conditions_match=same, usage_complete=measured_all, roles={})
    if any('qualification' in v for v in (left, right)):
        result['qualification'] = {key: dict(manual=left.get('qualification', {}).get(key, 'not_observed'),
            autonomous=right.get('qualification', {}).get(key, 'not_observed'),
            both_passed=all(v.get('qualification', {}).get(key) == 'passed' for v in (left, right)))
            for key in ('science', 'cross_task', 'root_scheduling', 'overall')}
    for role in ('root','worker','helper','setup_root'):
        a, b = (v.get('usage',{}).get('groups',{}).get(role) for v in (left,right))
        measured = a is not None and b is not None and a['coverage']==b['coverage']=='observed' and all(v.get('usage',{}).get('coverage')=='observed' for v in (left,right))
        result['roles'][role] = dict(manual=a, autonomous=b, input_plus_output_ratio=(
            b['input_plus_output']/a['input_plus_output'] if measured and same and quality and a['input_plus_output'] else None))
    return result


def assess(evidence, rubric, review, *, objective=None):
    """Review is local acceptance evidence, never an approval or a run mutation."""
    expected = digest(evidence)
    if review.get('evidence_digest') != expected or review.get('rubric') != rubric:
        raise ValueError('review_does_not_match_exact_evidence_and_rubric')
    decisions = review.get('decisions', [])
    if not review.get('reviewer') or len(decisions) != len(rubric):
        raise ValueError('review_incomplete')
    if any(v.get('status') not in {'passed','failed','not_observed'} or not v.get('reason', '').strip() for v in decisions):
        raise ValueError('each_criterion_requires_status_and_evidence_reason')
    if objective is not None:
        try:
            from scripts.s0_scoring import assess_domains
        except ModuleNotFoundError:
            from s0_scoring import assess_domains
        return assess_domains(evidence, review, objective)['overall']
    return verdict({str(i):v['status'] for i,v in enumerate(decisions)}, [str(i) for i in range(len(rubric))])
