"""One explicit A-selected, scratch-only adapter audit; immutable node facts."""
from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path

from . import budget, contracts as c, delivery, execution, native

SCOPE = 'Adapter-scoped qualification, not target evidence or submission.'


def _directory(root, step):
    path = c.host_record(c.workspace(root, step)) / 'candidate-audit'
    if path.resolve() != path:
        raise ValueError('Candidate audit original location changed')
    return path


def _save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = delivery._bytes(value)
    if len(data) > delivery.MAX_BYTES:
        raise ValueError('Candidate audit original exceeds byte bound')
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o400)


def _decision(root, step):
    record = c.host_record(c.workspace(root, step))
    return dict(step=step, job_sha256=c.digest(root / 'jobs' / f'{step:03d}.json'),
                raw_sha256=c.digest(execution.raw(root, step)), seal_sha256=c.digest(record / 'result-identity.json'))


def _operation(root, decision, candidate):
    return hashlib.sha256(delivery._bytes(dict(decision=decision, candidate_id=candidate,
        settings_sha256=c.digest(root / 'settings.json')))).hexdigest()


def validate_intent(root, intent):
    decision = intent['decision']
    stored_fields = {'action_id', 'action_kind', 'operation_id', 'decision', 'candidate_id', 'max_seconds', 'advance_seconds'}
    if (set(intent) - {'binding'} != stored_fields or intent['action_kind'] != 'audit'
            or intent['operation_id'] != _operation(root, decision, intent['candidate_id'])
            or intent['action_id'] != intent['operation_id']
            or intent['max_seconds'] != c.settings(root)['delivery_policy']['submit_seconds']
            or type(intent['advance_seconds']) not in (int, float)
            or not math.isfinite(intent['advance_seconds']) or intent['advance_seconds'] < 0
            or intent['advance_seconds'] > budget.snapshot(root)['advance_seconds']):
        raise ValueError('Candidate audit accepted budget or identity changed')
    if decision != _decision(root, decision['step']):
        raise ValueError('Candidate audit scientific author changed')
    path = _directory(root, decision['step']) / 'intent.json'
    if c.read(c.regular(path)) != {key: value for key, value in intent.items() if key != 'binding'}:
        raise ValueError('Candidate audit accepted identity changed')
    job = c.read(root / 'jobs' / f'{decision["step"]:03d}.json')
    raw = c.science_payload(execution.raw(root, decision['step']), 'A', job['handoff_protocol'])
    if job.get('purpose') is not None:
        begin = budget.closeout_state(root)['begin']
        if (job['purpose'] != 'closeout' or begin is None or job['source_cutoff'] != begin['source_cutoff']
                or job['delivery_sources'] != begin['delivery_sources']
                or job['closeout_begin'] != dict(seq=begin['seq'], sha256=c.digest(root / 'control-ledger' / f'{begin["seq"]:06d}.json'))):
            raise ValueError('Candidate audit closeout boundary changed')
    if (job['role'] != 'A' or job['handoff_protocol'] < 9
            or raw['next_action'] != 'audit' or raw['candidate_recommendation'] != intent['candidate_id']):
        raise ValueError('Candidate audit differs from the original scientific request')


def validate_binding(root, intent):
    validate_intent(root, intent)
    directory = _directory(root, intent['decision']['step'])
    binding = c.read(c.regular(directory / 'binding.json'))
    if binding != intent['binding']:
        raise ValueError('Candidate audit object binding changed')
    refs = c.read(c.regular(directory / 'sources.json'))
    delivery.validate_sources(root, refs)
    rows = [row for row in refs['items'] if row['candidate_id'] == intent['candidate_id']]
    if (len(rows) != 1 or rows[0] != binding['source'] or binding['decision'] != intent['decision']
            or binding['operation_id'] != intent['operation_id'] or binding['candidate_id'] != intent['candidate_id']
            or binding['target'] != delivery._adapter(root)['target']):
        raise ValueError('Candidate audit no longer binds its selected original')


def _outcome(root, step):
    directory = _directory(root, step)
    path = directory / 'outcome.json'
    if not path.exists():
        return None
    value = c.read(c.regular(path))
    if value['decision'] != _decision(root, step):
        raise ValueError('Candidate audit receipt scientific source changed')
    raw = c.read(execution.raw(root, step))
    if (type(value['accepted']) is not bool or value['accepted'] != (directory / 'intent.json').exists()
            or value['candidate_id'] != raw.get('candidate_recommendation')
            or raw.get('next_action') != 'audit'
            or type(value['result'].get('note')) is not str or len(value['result']['note'].encode()) > 1024):
        raise ValueError('Candidate audit outcome differs from its original request')
    if value['accepted']:
        intent = c.read(c.regular(directory / 'intent.json'))
        validate_intent(root, intent)
        if value['intent_sha256'] != c.digest(directory / 'intent.json'):
            raise ValueError('Candidate audit intent receipt changed')
        if value.get('binding_sha256') is not None:
            binding = c.read(c.regular(directory / 'binding.json'))
            validate_binding(root, dict(intent, binding=binding))
            if value['binding_sha256'] != c.digest(directory / 'binding.json'):
                raise ValueError('Candidate audit binding receipt changed')
        result = value['result']
        expected_artifact = binding['source']['objects']['artifact']['sha256'] if value.get('binding_sha256') is not None else None
        if (result.get('operation_id') != intent['operation_id'] or result.get('candidate_id') != intent['candidate_id']
                or result.get('artifact_sha256') != expected_artifact):
            raise ValueError('Candidate audit result object identity changed')
        process_path = directory / 'process.json'
        if value.get('process_sha256') is not None:
            if c.digest(c.regular(process_path)) != value['process_sha256']:
                raise ValueError('Candidate audit process original changed')
            process = c.read(process_path)
            identity = process.get('identity', {})
            if (process.get('operation_id') != intent['operation_id'] or process.get('phase') != 'audit'
                    or identity.get('task_sha256') != intent['operation_id']
                    or any(type(identity.get(key)) is not int or identity[key] <= 0 for key in ('pid', 'pgid', 'sid', 'start_ticks'))):
                raise ValueError('Candidate audit process identity changed')
        if result['status'] == 'audited' and (value.get('binding_sha256') is None or value.get('process_sha256') is None):
            raise ValueError('Audited receipt has no exact object and process original')
        result_path = directory / 'adapter-result.json'
        if c.digest(c.regular(result_path)) != value['result_sha256'] or c.read(result_path) != value['result']:
            raise ValueError('Candidate audit adapter result changed')
    elif value['result']['status'] != 'unavailable':
        raise ValueError('An unaccepted audit cannot acquire qualification')
    if (value['result']['status'] not in {'audited', 'failed', 'unknown', 'unavailable'}
            or type(value['result']['cleanup_confirmed']) is not bool):
        raise ValueError('Candidate audit outcome fields changed')
    return value


def facts(root):
    """No mutable current pointer; budgets derive accepted actions and unknowns."""
    for path in sorted((root / 'jobs').glob('*.json')):
        step = int(path.stem)
        directory = _directory(root, step)
        if (directory / 'intent.json').exists():
            intent = c.read(c.regular(directory / 'intent.json'))
            validate_intent(root, intent)
            yield intent, _outcome(root, step)


def blocked(root):
    return any(outcome is None or not outcome['result']['cleanup_confirmed'] for _, outcome in facts(root))


def receipt_ref(root, step):
    value = _outcome(root, step)
    if value is None:
        return None
    path = _directory(root, step) / 'outcome.json'
    return dict(step=step, path=path.relative_to(root).as_posix(), sha256=c.digest(path))


def public_receipt(root, ref):
    expected = receipt_ref(root, ref['step'])
    if expected != ref:
        raise ValueError('Frozen candidate audit receipt changed')
    value = _outcome(root, ref['step'])
    result = value['result']
    return dict(candidate_id=value['candidate_id'], status=result['status'],
                note=result['note'], scope=SCOPE)


def execute(root, job, payload):
    """Returns a blocking status, or None once an immutable receipt is available."""
    from .protocol import require_current
    require_current(root,job)
    step, chosen = job['step'], payload.get('candidate_recommendation')
    directory = _directory(root, step)
    previous = _outcome(root, step)
    if previous is not None:
        return None if previous['result']['cleanup_confirmed'] else 'candidate_audit_unknown'
    if (directory / 'intent.json').exists():
        return 'candidate_audit_unknown'  # Never repeat an uncertain accepted call.
    if (root / 'pause.request').exists():
        return 'paused'
    from . import correction
    if correction.gate(root, step) is not None:
        return 'correction_paused'
    decision = _decision(root, step)
    intent = None
    binding = None
    def finish(status, note, *, cleanup=True, result=None):
        result = result or dict(status=status, note=note, cleanup_confirmed=cleanup)
        if intent is not None and 'operation_id' not in result:
            result.update(operation_id=intent['operation_id'], candidate_id=chosen,
                          artifact_sha256=binding['source']['objects']['artifact']['sha256'] if binding else None)
        value = dict(decision=decision, candidate_id=chosen, accepted=intent is not None, result=result)
        if intent is not None:
            _save(directory / 'adapter-result.json', result)
            value.update(intent_sha256=c.digest(directory / 'intent.json'),
                         binding_sha256=c.digest(directory / 'binding.json') if binding is not None else None,
                         result_sha256=c.digest(directory / 'adapter-result.json'),
                         process_sha256=c.digest(directory / 'process.json') if (directory / 'process.json').exists() else None)
        _save(directory / 'outcome.json', value)
        return None if cleanup else 'candidate_audit_unknown'
    if chosen is None or chosen not in job['history']['candidate_ids']:
        return finish('unavailable', 'candidate_unavailable')
    policy = c.settings(root).get('delivery_policy')
    if policy is None or policy['adapter'] is None:
        return finish('unavailable', 'adapter_unavailable')
    if budget.execution_blocked(root):
        return 'candidate_audit_unknown'
    meter, limits = native.usage(root), budget.snapshot(root)
    settings = c.settings(root)
    reserve = budget.delivery_reserve(settings)
    soft_closeout = budget.node_mode(root) == 'soft' and job.get('purpose') == 'closeout'
    if soft_closeout:
        reserve = budget.closeout_floor(settings, preparation_seconds=budget.closeout_state(root)['begin']['preparation_seconds'])
        reserve['steps'] += 1  # One actual follow-up A, plus the external actions.
    if meter['unknown_steps']:
        return 'candidate_audit_usage_unknown'
    seconds_unavailable = (limits['seconds_remaining'] <= policy['submit_seconds'] + reserve['seconds'] if soft_closeout else
        limits['seconds_remaining'] < policy['submit_seconds'] + reserve['seconds'])
    tokens_unavailable = (limits['max_tokens'] - meter['observed_tokens'] <= reserve['tokens'] if soft_closeout else
        limits['max_tokens'] - meter['observed_tokens'] < reserve['tokens'])
    if (seconds_unavailable or tokens_unavailable
            or budget.used_steps(root) + 1 + reserve['steps'] > c.settings(root)['max_steps']):
        return finish('unavailable', 'candidate_audit_reserve_unavailable')
    budget.transition(root, 'advance', 'candidate_audit')
    operation = _operation(root, decision, chosen)
    intent = dict(action_id=operation, action_kind='audit', operation_id=operation, decision=decision,
                  candidate_id=chosen, max_seconds=policy['submit_seconds'], advance_seconds=budget.snapshot(root)['advance_seconds'])
    _save(directory / 'intent.json', intent)
    try:
        refs = job.get('delivery_sources') or delivery.freeze_sources(root, job['history']['nodes'], candidate_id=chosen)
        _save(directory / 'sources.json', refs)
        rows = [row for row in refs['items'] if row['candidate_id'] == chosen and row['status'] == 'audit_pending']
        if len(rows) != 1:
            return finish('unavailable', 'candidate_originals_unavailable')
        binding = dict(candidate_id=chosen, decision=decision, source=rows[0], target=policy['adapter']['target'], operation_id=operation)
        _save(directory / 'binding.json', binding)
        def process(phase, identity):
            _save(directory / 'process.json', dict(operation_id=operation, phase=phase, identity=identity))
        result = delivery.invoke(root, dict(intent, binding=binding), policy['submit_seconds'],
                                 on_process=process, audit_only=True)
        return finish(result['status'], result['note'], cleanup=result['cleanup_confirmed'], result=result)
    except delivery.DeliveryUnresolved as error:
        return finish('unknown', error.code, cleanup=error.code != 'delivery_cleanup_unknown')


def collect_refs(root, sources, *, step, adjacent=None):
    """Only frozen refs witnessed by the verified prefix, plus this exact next A."""
    refs = {}
    values = []
    steps = {job['step'] for job, _, _, _ in sources}
    for job, _, _, _ in sources:
        ref = job.get('candidate_audit')
        if ref is not None:
            if job['role'] != 'A' or ref['step'] != job['step'] - 1:
                raise ValueError('Historical audit lacks its exact adjacent sealed anchor')
            values.append(ref)
    if adjacent is not None:
        if adjacent['step'] != step - 1 or adjacent['step'] not in steps:
            raise ValueError('Adjacent audit is outside the frozen scientific prefix')
        values.append(adjacent)
    for ref in values:
        if not 0 < ref['step'] < step:
            raise ValueError('Audit receipt is outside the task boundary')
        public_receipt(root, ref)  # Original outcome/binding/process, not scientific prose.
        if ref['step'] in refs and refs[ref['step']] != ref:
            raise ValueError('Conflicting original audit receipts')
        refs[ref['step']] = ref
    return [refs[key] for key in sorted(refs)]


def project_receipts(root, records, refs):
    """Adapter results and candidate-byte attribution; no leakage interpretation."""
    models = {}
    for record in records:
        observation = record.get('observation') or {}
        for context in observation.get('contexts', []):
            model = context.get('model')
            if context.get('status') == 'known_success' and model and model.get('retention') == 'archived':
                models.setdefault(context['candidate_id'], set()).add((model['sha256'], model['size_bytes']))
        actual = observation.get('actual_submission')
        if actual and actual.get('candidate_id') is not None and (actual.get('artifact') or {}).get('retention') == 'archived':
            model = actual['artifact']
            models.setdefault(actual['candidate_id'], set()).add((model['sha256'], model['size_bytes']))
    rows = []
    for ref in refs:
        public_receipt(root, ref)
        value = _outcome(root, ref['step'])
        result, chosen = value['result'], value['candidate_id']
        binding = None
        if value.get('binding_sha256') is not None:
            binding = c.read(c.regular(_directory(root, ref['step']) / 'binding.json'))
        artifact = binding['source']['objects']['artifact'] if binding is not None else None
        identities = models.get(chosen, set())
        match = ('unknown' if artifact is None or not identities else
                 'matched' if identities == {(artifact['sha256'], artifact['size_bytes'])} else 'different')
        spec = c.settings(root).get('delivery_policy', {}).get('adapter')
        label = Path(spec['adapter']).name if spec is not None else 'unavailable'
        rows.append(dict(candidate_id=chosen, adapter_result=result['status'], artifact_binding=match,
                         audit_step=ref['step'], adapter=label.encode()[:80].decode(errors='ignore'),
                         scope=SCOPE, leakage_flag=None))
    return rows
