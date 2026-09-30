"""Small acceptance evidence helpers; no model calls or scientific state writes."""
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path


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


def rows(candidate, database, query, args=()):
    path = Path(candidate) / 'state/database' / (database + '.sqlite3')
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        # SQLite stores canonical JSON as BLOB in production. Normalize only
        # declared JSON columns for evidence serialization; preserve all other
        # binary data and reject invalid UTF-8 instead of stringifying bytes.
        return [{key: value.decode('utf-8') if key.endswith('_json') and isinstance(value, bytes)
                 else value for key, value in dict(row).items()} for row in db.execute(query, args)]


def control_rows(candidate, query='SELECT * FROM scheduler_progression', args=()):
    # Original A6 snapshots predate progression. Absence is a valid fresh
    # baseline; malformed existing tables still raise instead of hiding errors.
    if not rows(candidate, 'scheduler-bindings', "SELECT 1 FROM sqlite_master WHERE type='table' AND name='scheduler_progression'"):
        return []
    return rows(candidate, 'scheduler-bindings', query, args)


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
    identities = {v['thread_id']:'worker' for v in workers}
    identities.update({v['thread_id']:'helper' for v in helpers if v['thread_id']})
    started_path = Path(journey) / 'started-threads.json'
    started = read(started_path) if started_path.exists() else []
    for identity in started:
        identities.setdefault(identity, 'unattributed')
    if raw.get('root_thread') and (not started_path.exists() or raw['root_thread'] in started or raw['root_thread'] in raw.get('threads', {})):
        identities[raw['root_thread']] = 'setup_root' if progression else 'root'
    observed = {}
    for identity, total in raw.get('threads', {}).items():
        values = {key:total.get(wire) for key, wire in (
            ('input_tokens','inputTokens'), ('cached_input_tokens','cachedInputTokens'), ('output_tokens','outputTokens'))}
        observed[identity] = dict(role=identities.get(identity, 'unattributed'), tokens=values)
    checkpoint = json.loads(progression['checkpoint_json']) if progression else {}
    for identity, item in checkpoint.get('usage_records', {}).items():
        identities[identity] = item['role']
        observed[identity] = dict(role=item['role'], tokens=item['counted_tokens'], partial=item['has_gaps'])
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
