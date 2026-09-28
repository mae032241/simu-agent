"""Bounded mechanical handoff of exact goal admissions; never a goal verdict."""
import json

from .run_read_projection import RunReadProjection, run_is_terminal
from .scheduling_control import progression_status_view
from .runs import RunNotFound
from .scheduler_bindings import SchedulerNameNotFound


def progression_read_view(*, bindings, runs, artifacts, operation_catalog, instance_id, session_key=None):
    row = bindings.progression_status(instance_id=instance_id, internal=True)
    status = progression_status_view(row, session_key=session_key)
    if row.get('historical'):
        status.update(historical=True, can_schedule=False, writer='none')
        if status.get('notifications'):
            status['notifications']['current_id'] = None
    checkpoint = json.loads(row.get('checkpoint_json', '{}'))
    if not row.get('objective_name'):
        return status
    projection = RunReadProjection(runs=runs, artifacts=artifacts, operation_catalog=operation_catalog)
    closeout = dict(kind='sealed_task_handoff', goal_assessment='not_inferred',
        stop_reason=status.get('reason'), tasks=[], in_flight=[], unresolved=[], omissions=[])
    records = checkpoint.get('usage_records', {})
    missing = {}
    if checkpoint.get('started_at') is not None and not any(record['role'] == 'root' for record in records.values()):
        missing['root'] = 1
    remaining = 32768
    for name, admission in checkpoint.get('admissions', {}).items():
        read = dict(tool='run_status', name=name, intent='decision')
        if admission.get('state') != 'accepted' or not admission.get('run_id'):
            closeout['unresolved'].append(dict(name=name, state='admission_unresolved', read=read))
            continue
        try:
            value = runs.status(admission['run_id'])
            binding = bindings.get_binding(instance=instance_id, namespace='run', name=name)
        except (RunNotFound, SchedulerNameNotFound):
            closeout['unresolved'].append(dict(name=name, state='identity_unresolved', read=read))
            continue
        if binding.object_id != value.run_id or value.instance_id != instance_id:
            closeout['unresolved'].append(dict(name=name, state='identity_unresolved', read=read))
            continue
        for identity in runs.native_identities(value.run_id):
            if identity['thread_id'] not in records:
                role = identity['role']
                missing[role] = missing.get(role, 0) + 1
        item = projection.decision(name=name, value=value)
        # Task dispatch remains an explicit scheduler action; a handoff is read-only.
        item.pop('dispatch', None)
        item['read'] = read
        if not run_is_terminal(value.state):
            closeout['in_flight'].append(dict(name=name, state=value.state, read=read))
        size = len(json.dumps(item, ensure_ascii=False).encode())
        if size > remaining:
            item = dict(name=name, state=value.state, output_artifact_name=item.get('output_artifact_name'), read=read)
            closeout['omissions'].append(dict(name=name, reason='handoff_context_limit', read=read))
        else:
            remaining -= size
        closeout['tasks'].append(item)
    closeout['accepted_tasks_terminal'] = not closeout['in_flight'] and not closeout['unresolved']
    if missing:
        status['usage']['coverage'] = 'partial' if records or status['usage'].get('groups') else 'missing'
    status['usage']['unmeasured_participants'] = missing
    status['budget']['token_coverage'] = status['usage']['coverage']
    status['closeout'] = closeout
    return status
