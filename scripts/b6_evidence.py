"""Small acceptance evidence helpers; no model calls or scientific state writes."""
import hashlib
import json
import math
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


def accepted_goal_loop(control):
    """One exact admission scope shared by exploration and batch proofs."""
    cp = json.loads(control['checkpoint_json'])
    scope = dict(instance=control['instance_id'], goal=json.loads(control['objective_ref_json']),
        loop=cp.get('current_loop_id'))
    if not scope['instance'] or not scope['goal'] or not scope['loop']:
        raise ValueError('acceptance_goal_loop_missing')
    identities = {v['run_id'] for v in cp.get('admissions', {}).values()
        if v.get('state') == 'accepted' and v.get('loop_id') == scope['loop'] and v.get('objective_ref') == scope['goal']
        and not v.get('interactive_session_id') and v.get('run_id')}
    return scope, identities


def accepted_case_runs(candidate, control, *, max_runs, expected_scope=None):
    scope, identities = accepted_goal_loop(control)
    if expected_scope is not None and scope != expected_scope:
        raise ValueError('acceptance_goal_loop_changed')
    if len(identities) > max_runs:
        raise ValueError('acceptance_run_scope_exceeded')
    if not identities:
        return []
    found = rows(candidate, 'runs', 'SELECT run_id,state,output_ref_json FROM runs WHERE instance_id=? '
        'AND run_id IN ('+','.join('?' for _ in identities)+') ORDER BY run_id', (scope['instance'], *sorted(identities)))
    if {v['run_id'] for v in found} != identities:
        raise ValueError('acceptance_admitted_run_scope_mismatch')
    return found


def authorized_case_scope(candidate, control, authorization):
    scope = accepted_goal_loop(control)[0]
    bound = rows(candidate, 'scheduler-bindings',
        "SELECT object_id FROM scheduler_bindings WHERE instance=? AND namespace='artifact' AND name=?",
        (scope['instance'], authorization['objective_name']))
    if (scope['loop'] != authorization['id'] or control.get('objective_name') != authorization['objective_name']
            or bound != [{'object_id':scope['goal']['artifact_id']}]):
        raise ValueError('acceptance_authorized_goal_loop_changed')
    return scope


def exploratory_case(case):
    """Only autonomous multi-task/batch benches retain failed attempts and continue."""
    return case.get('scenario') == 'autonomous' and bool(case.get('multi_task') or case.get('batch_delivery'))


def case_delivery_ready(runs, *, exploratory=False):
    terminal = {'completed','failed','timed_out','cancelled'} if exploratory else {'completed'}
    return bool(runs) and any(v['state']=='completed' for v in runs) and all(v['state'] in terminal for v in runs)


def participants(candidate, run_ids):
    workers, helpers = [], []
    for run in run_ids:
        workers += rows(candidate, 'runs', 'SELECT * FROM worker_connections WHERE run_id=?', (run,))
        # request_json contains original subproblem text, not needed by the audit.
        helpers += rows(candidate, 'runs', 'SELECT run_id,name,platform_session,owner_thread,thread_id,admitted_at,released_at FROM worker_participants WHERE run_id=?', (run,))
    return workers, helpers


def sealed_outputs(candidate, runs, *, exploratory=False):
    if exploratory:
        if not case_delivery_ready(runs, exploratory=True):
            raise ValueError('case_required_sealed_delivery_missing')
        runs = [v for v in runs if v['state'] == 'completed']
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


P6S_PREDICTION_PROTOCOL = (
    '本合成机制验收使用公开 science.experiment.v1 完整任务；先查当前合同。'
    '本 bench 的预测任务须在 worker_experiment_stage 的设计阶段使用可选 prediction_declaration，'
    '绑定实际收到的鉴别材料 alias，给出工况 A、x=4 的预测及可证伪判据；尚未投递的观测不可作为输入。'
    '允许在同一任务内修订，最终 ExperimentReport.adopted_stages 必须仅采用一个确切声明原件；'
    'running 预览不触发投递。预测子任务可按实际范围交付 outcome=inconclusive，'
    '不必等待未投递的验证观测，也不代表科学结论已验证。'
    '后续比较任务使用可选 comparison，引用投递所依据的确切声明和实际验证材料 alias，'
    '最终 adopted_stages 采用比较原件；not_run 不算已比较，负结果仍须保留。'
    '这些交付条件只属于本 bench，普通任务的可选字段仍可省略。')


def batch_payloads(spec):
    """Project only the four public batches from one exact host-side fixture."""
    path = Path(spec['materials_file'])
    if not path.is_absolute() or path.stat().st_size > 65536:
        raise ValueError('batch_material_requires_bounded_absolute_host_file')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != spec['materials_sha256']:
        raise ValueError('batch_material_digest_changed')
    material = json.loads(raw)
    names = ['A_initial', 'A_discrimination', 'A_validation', 'B_changed_condition']
    if (material.get('fixture_version') != 1 or material.get('kind') != 'hourly_loop_memory_materials_not_runner_config'
            or len(material.get('batches', [])) != 4):
        raise ValueError('unsupported_batch_material')
    result = []
    for name, batch in zip(names, material['batches']):
        if batch.get('name') != name or set(batch) != {'name', 'condition', 'public_note', 'observations'}:
            raise ValueError('batch_public_projection_invalid')
        if (batch['condition'] != ('B' if name == 'B_changed_condition' else 'A')
                or not isinstance(batch['public_note'], str) or not 1 <= len(batch['public_note']) <= 8192
                or not isinstance(batch['observations'], list) or not 1 <= len(batch['observations']) <= 32
                or any(not isinstance(v, dict) or set(v) != {'x', 'y', 'error_abs'}
                    or any(type(n) not in (int, float) or not math.isfinite(n) for n in v.values())
                    or v['error_abs'] <= 0 for v in batch['observations'])):
            raise ValueError('batch_public_observation_invalid')
        text = json.dumps(batch, ensure_ascii=False, sort_keys=True, allow_nan=False)
        if name == 'A_discrimination':
            text += '\n' + P6S_PREDICTION_PROTOCOL
        if not 1 <= len(text) <= 16000:
            raise ValueError('batch_public_text_limit')
        result.append(dict(name=name, text=text))
    return result


class BatchBodyLimit(ValueError):
    """Body was not read; receipt role may already have been verified by the resolver."""
    def __init__(self, tool_name):
        super().__init__('batch_scientific_body_limit')
        self.tool_name = tool_name


class BatchMaterialReader:
    """Read-only, bounded adapter for the existing original-receipt resolver.

    No runtime is opened: reads cannot migrate state, bind an instance or submit
    work. The resolver retains the original producer's alias namespace.
    """
    def __init__(self, candidate, instance, run_ids):
        from types import SimpleNamespace
        from scidiscovery.artifact_agent.schema.refs import ArtifactRef
        self.root, self.instance = Path(candidate), instance
        if len(run_ids) > 128:
            raise ValueError('batch_run_read_limit')
        self.artifacts = self
        self.values, self.records = {}, {}
        for identity in run_ids:
            found = rows(candidate, 'runs',
                'SELECT instance_id,state,operation_id,CASE WHEN length(inputs_json)<=262144 THEN inputs_json END AS inputs_json,output_ref_json FROM runs WHERE run_id=?', (identity,))
            if len(found) != 1 or found[0]['instance_id'] != instance:
                raise ValueError('batch_run_scope_mismatch')
            value = found[0]
            if value['inputs_json'] is None:
                raise ValueError('batch_input_namespace_limit')
            inputs = json.loads(value['inputs_json'])
            if len(inputs) > 128:
                raise ValueError('batch_input_namespace_limit')
            self.values[identity] = SimpleNamespace(run_id=identity, instance_id=instance,
                state=value['state'], operation_id=value['operation_id'], output_ref=json.loads(value['output_ref_json']) if value['output_ref_json'] else None,
                inputs=[SimpleNamespace(source_name=v['source_name'], artifact_ref=ArtifactRef.model_validate(v['artifact_ref']))
                    for v in inputs])
            records = rows(candidate, 'runs',
                'SELECT CASE WHEN length(record_json)<=262144 THEN record_json END AS record_json FROM run_tool_evidence WHERE run_id=? ORDER BY ordinal LIMIT 129', (identity,))
            if len(records) > 128 or any(v['record_json'] is None for v in records) or sum(len(v['record_json'].encode()) for v in records) > 262144:
                raise ValueError('batch_receipt_coverage_limit')
            self.records[identity] = [json.loads(v['record_json']) for v in records]

    def status(self, identity):
        if identity not in self.values:
            raise ValueError('batch_original_producer_outside_goal_loop')
        return self.values[identity]

    def tool_evidence(self, identity):
        return [v for v in self.records[identity] if v.get('record_type') != 'reference_access']

    def reference_access_records(self, identity):
        return [v for v in self.records[identity] if v.get('record_type') == 'reference_access']

    def catalog(self, ref):
        from scidiscovery.artifact_agent.schema.artifact import ArtifactEnvelope
        found = rows(self.root, 'artifact_agent',
            'SELECT CASE WHEN length(envelope_json)<=262144 THEN envelope_json END AS envelope_json,envelope_sha256 FROM artifact_envelopes WHERE artifact_id=?', (ref.artifact_id,))
        if len(found) != 1 or found[0]['envelope_json'] is None:
            raise ValueError('batch_artifact_envelope_unavailable')
        raw = found[0]['envelope_json'].encode()
        if hashlib.sha256(raw).hexdigest() != found[0]['envelope_sha256']:
            raise ValueError('batch_artifact_envelope_corrupt')
        envelope = ArtifactEnvelope.model_validate_json(raw)
        if envelope.ref != ref:
            raise ValueError('batch_artifact_ref_mismatch')
        return envelope

    def verify(self, ref):
        envelope = self.catalog(ref)
        if envelope.size_bytes > 65536:
            raise BatchBodyLimit(envelope.labels.get('tool_name'))
        path = self.root/'state/artifacts/sha256'/ref.sha256[:2]/ref.sha256[2:]
        with path.open('rb') as stream:
            if path.stat().st_size != envelope.size_bytes or hashlib.file_digest(stream, 'sha256').hexdigest() != ref.sha256:
                raise ValueError('batch_artifact_bytes_mismatch')
        return envelope

    def read_json(self, ref):
        from scidiscovery.artifact_agent.schema.refs import ArtifactRef
        ref = ArtifactRef.model_validate(ref)
        envelope = self.verify(ref)
        if envelope.size_bytes > 65536:
            raise ValueError('batch_scientific_body_limit')
        return json.loads((self.root/'state/artifacts/sha256'/ref.sha256[:2]/ref.sha256[2:]).read_bytes())

    def material(self, identity, alias):
        from scidiscovery.artifact_agent.service.sealed_materials import resolve_material
        return resolve_material(self, self.status(identity), alias)


def batch_scientific_facts(candidate, control, *, max_runs, discrimination=None, validation=None, prediction=None):
    """Exact current goal/loop admissions; science correctness is not inferred."""
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    from scidiscovery.general_science_experiment_task import StageSubmission, ExperimentReport
    _, admissions = accepted_goal_loop(control)
    if len(admissions) > max_runs:
        raise ValueError('batch_admission_coverage_limit')
    reader = BatchMaterialReader(candidate, control['instance_id'], sorted(admissions))
    facts = dict(first_results=[], declarations=[], comparisons=[], waiting=[], declaration_coverage_complete=True)
    for identity in sorted(admissions):
        value = reader.status(identity)
        if value.operation_id != 'science.experiment.v1':
            continue  # This optional benchmark uses the declared complete experiment contract.
        if value.state != 'completed':
            facts['waiting'].append(dict(run_id=identity, reason='experiment_not_completed'))
            continue
        if value.output_ref is None:
            raise ValueError('batch_completed_report_missing')
        try:
            report = ExperimentReport.model_validate_json(json.dumps(reader.read_json(value.output_ref)))
        except BatchBodyLimit:
            facts['declaration_coverage_complete'] = False
            facts['waiting'].append(dict(run_id=identity, reason='completed_report_body_limit'))
            continue
        facts['first_results'].append(dict(run_id=identity, artifact_ref=value.output_ref))
        if not report.adopted_stages:
            facts['waiting'].append(dict(run_id=identity, reason='no_adopted_stages'))
        adopted_refs = set()
        for alias in report.adopted_stages:
            try:
                record = reader.material(identity, alias)
            except BatchBodyLimit as error:
                # resolve_material checks the unique original receipt and its
                # role/namespace before verify raises this precise read limit.
                # An unread stage can hide another declaration; a non-stage
                # receipt cannot. Neither unread body gains scientific credit.
                if error.tool_name == 'worker_experiment_stage':
                    facts['declaration_coverage_complete'] = False
                facts['waiting'].append(dict(run_id=identity, reason='adopted_stage_body_limit'
                    if error.tool_name == 'worker_experiment_stage' else 'unrelated_material_body_limit', alias=alias))
                continue
            if record is None:
                raise ValueError('batch_adopted_receipt_missing')
            ref = ArtifactRef.model_validate(record['artifact_ref'])
            if ref in adopted_refs:
                continue
            adopted_refs.add(ref)
            if record.get('tool_name') != 'worker_experiment_stage':
                facts['waiting'].append(dict(run_id=identity, reason='adopted_material_not_stage', artifact_ref=record['artifact_ref']))
                continue
            stage = StageSubmission.model_validate_json(json.dumps(reader.read_json(record['artifact_ref'])))
            refs = record['source_refs']
            if stage.prediction_declaration is None and stage.comparison is None:
                facts['waiting'].append(dict(run_id=identity, reason='adopted_stage_without_prediction_or_comparison', artifact_ref=record['artifact_ref']))
            if stage.prediction_declaration and discrimination:
                conditions = [refs.get(name) for name in stage.prediction_declaration.conditions]
                if None in conditions:
                    raise ValueError('batch_prediction_condition_namespace_missing')
                if record['producer_run_id'] != identity:
                    facts['waiting'].append(dict(run_id=identity, reason='prediction_not_authored_by_adopting_run', artifact_ref=record['artifact_ref']))
                elif ArtifactRef.model_validate(discrimination) in conditions:
                    facts['declarations'].append(dict(run_id=identity, artifact_ref=record['artifact_ref'], report_ref=value.output_ref))
                else:
                    facts['waiting'].append(dict(run_id=identity, reason='prediction_conditions_not_discrimination', artifact_ref=record['artifact_ref']))
            if not (stage.comparison and prediction and validation):
                continue
            comparison = stage.comparison
            observation_refs = [refs.get(name) for name in comparison.observations]
            if refs.get(comparison.prediction) is None or None in observation_refs:
                raise ValueError('batch_comparison_source_namespace_missing')
            reason = ('comparison_prediction_not_selected' if refs[comparison.prediction] != ArtifactRef.model_validate(prediction)
                else 'comparison_observations_not_validation' if ArtifactRef.model_validate(validation) not in observation_refs
                else 'comparison_not_run' if comparison.result.status == 'not_run' else None)
            if reason:
                facts['waiting'].append(dict(run_id=identity, reason=reason, artifact_ref=record['artifact_ref']))
                continue
            declaration = reader.material(identity, comparison.prediction)
            if declaration is None or declaration.get('tool_name') != 'worker_experiment_stage':
                raise ValueError('batch_declaration_original_receipt_missing')
            declared = StageSubmission.model_validate_json(json.dumps(reader.read_json(declaration['artifact_ref'])))
            if (declared.prediction_declaration is None
                    or comparison.result.check_key != declared.prediction_declaration.criterion.check_key
                    or comparison.result.evaluation_mode != declared.prediction_declaration.criterion.evaluation_mode):
                raise ValueError('batch_comparison_criterion_mismatch')
            completion = rows(candidate, 'runs', "SELECT rowid AS event_id FROM run_activity WHERE run_id=? "
                "AND activity='completion_committed' LIMIT 2", (identity,))
            if len(completion) > 1:
                raise ValueError('batch_comparison_completion_event_ambiguous')
            facts['comparisons'].append(dict(run_id=identity, artifact_ref=record['artifact_ref'], report_ref=value.output_ref,
                completion_event=completion[0]['event_id'] if completion else None))
    return facts


def usage_report(journey, workers, helpers, progression=None, *, candidate=None, exact_scope=None):
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
    excluded_threads = set()
    if loop_id:
        run_ids = {v.get('run_id') for v in checkpoint.get('admissions', {}).values()
            if v.get('loop_id') == loop_id and not v.get('interactive_session_id')}
        if exact_scope is not None:
            scope, selected = accepted_goal_loop(progression)
            if scope != exact_scope:
                raise ValueError('acceptance_goal_loop_changed')
            outside = {v['run_id'] for v in checkpoint.get('admissions', {}).values()
                if v.get('state')=='accepted' and v.get('loop_id')==loop_id and v.get('objective_ref')!=scope['goal']
                and not v.get('interactive_session_id') and v.get('run_id')}
            outside_workers, outside_helpers = participants(candidate, sorted(outside))
            excluded_roles = {v['thread_id']:'worker' for v in outside_workers if v.get('thread_id')}
            for value in outside_helpers:
                if value.get('thread_id'):
                    if value['thread_id'] in excluded_roles:
                        raise ValueError('acceptance_usage_identity_conflict')
                    excluded_roles[value['thread_id']] = 'helper'
            for identity, item in records.items():
                if (item.get('thread_id') != identity or item.get('owner') != progression['instance_id']
                        or item.get('role') not in {'root','worker','helper'}):
                    raise ValueError('acceptance_usage_identity_unbound')
                if identity in excluded_roles and item['role'] != excluded_roles[identity]:
                    raise ValueError('acceptance_usage_identity_conflict')
            excluded_threads = set(excluded_roles)
            records = {k:v for k,v in records.items() if k not in excluded_threads}
            run_ids = selected
        workers = [v for v in workers if v.get('run_id') in run_ids]
        helpers = [v for v in helpers if v.get('run_id') in run_ids]
        records = {key:value for key,value in records.items() if not value.get('interactive_session_id')}
    identities = {v['thread_id']:'worker' for v in workers if v.get('thread_id')}
    for value in helpers:
        if value.get('thread_id'):
            if value['thread_id'] in identities:
                raise ValueError('acceptance_usage_identity_conflict')
            identities[value['thread_id']] = 'helper'
    if excluded_threads.intersection(identities):
        raise ValueError('acceptance_usage_identity_conflict')
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
        if identity in excluded_threads:
            continue
        identities.setdefault(identity, 'unattributed')
    if raw.get('root_thread') and (not started_path.exists() or raw['root_thread'] in started or raw['root_thread'] in raw.get('threads', {})):
        identities[raw['root_thread']] = 'setup_root' if progression else 'root'
    observed = {}
    for identity, total in raw.get('threads', {}).items():
        if identity in excluded_threads:
            continue
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
