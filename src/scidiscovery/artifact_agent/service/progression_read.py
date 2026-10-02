"""Bounded mechanical handoff of exact goal admissions; never a goal verdict."""
import json

from .run_read_projection import RunReadProjection, run_is_terminal
from .scheduling_control import progression_status_view
from .scientific_progress import goal_bound_runs


def progression_read_view(*, bindings, runs, artifacts, operation_catalog, instance_id, session_key=None,
                          progress_cursor=None, progress_limit=4, executions=None, delivery_cursor=None, delivery_limit=8):
    row, handoff = runs.progression_handoff(instance_id=instance_id)
    clock = getattr(bindings, 'control_now', None)
    status = progression_status_view(row, session_key=session_key, now=clock() if clock else None)
    if row.get('historical'):
        status.update(historical=True, can_schedule=False, writer='none')
        if status.get('notifications'):
            status['notifications']['current_id'] = None
    checkpoint = json.loads(row.get('checkpoint_json', '{}'))
    if not row.get('objective_name'):
        if delivery_cursor is not None:
            raise ValueError('Delivery cursor requires its frozen goal.')
        return status
    projection = RunReadProjection(runs=runs, artifacts=artifacts, operation_catalog=operation_catalog)
    closeout = dict(kind='sealed_task_handoff', goal_assessment='not_inferred',
        stop_reason=status.get('reason'), tasks=[], in_flight=[], unresolved=[], omissions=[])
    closeout['history_read'] = dict(tool='run_list', view='history', limit=8)
    if current_omitted := status.get('accounting_details', {}).get('historical_records_omitted', {}).get('admissions'):
        closeout['omissions'].append(dict(reason='historical_loop_tasks', count=current_omitted,
            read=dict(tool='run_list', view='summary', limit=8)))
    closeout['budget_scope'] = 'current_loop' if checkpoint.get('current_loop_id') else 'ordinary_interactive'
    from .research_loops import loop_usage
    records = loop_usage(checkpoint)
    missing = dict(handoff['missing'])
    host = json.loads(row.get('host_json') or 'null')
    if host and records.get(host['thread_id'], {}).get('role') != 'root':
        missing['root'] = 1
    elif not host and checkpoint.get('started_at') is not None and not any(record['role'] == 'root' for record in records.values()):
        missing['root'] = 1
    current_runs = goal_bound_runs(checkpoint, json.loads(row["objective_ref_json"]))
    closeout['state_counts'] = handoff['state_counts']
    closeout['current_goal_state_counts'] = handoff['goal_state_counts']
    unresolved_count = sum(count for state, count in handoff['state_counts'].items()
        if state in {'admission_unresolved', 'identity_unresolved'})
    active_counts = {state: count for state, count in handoff['state_counts'].items()
        if not run_is_terminal(state) and state not in {'admission_unresolved', 'identity_unresolved'}}
    closeout['accepted_tasks_terminal'] = not active_counts and not unresolved_count
    for field in ('in_flight', 'unresolved'):
        closeout[field] = [dict(name=item['name'], state=item['state'],
            read=dict(tool='run_status', name=item['name'], intent='decision')) for item in handoff[field]]
    if unresolved_count > len(closeout['unresolved']):
        closeout['omissions'].append(dict(reason='unresolved_detail_limit',
            count=unresolved_count-len(closeout['unresolved']),
            original_read='Unbound or conflicting identities require repair before their originals can be read.'))
    if sum(active_counts.values()) > len(closeout['in_flight']):
        closeout['omissions'].append(dict(reason='in_flight_detail_limit',
            count=sum(active_counts.values())-len(closeout['in_flight']),
            reads=[dict(tool='run_list', view='summary', state=state, limit=8) for state in active_counts]))
    shown_count = len(handoff['tasks'])
    resolved_goal_count = sum(count for state, count in handoff['goal_state_counts'].items()
        if state not in {'admission_unresolved', 'identity_unresolved'})
    if resolved_goal_count > shown_count:
        closeout['omissions'].append(dict(reason='task_detail_limit', count=resolved_goal_count-shown_count,
            read=closeout['history_read'], active_read=dict(tool='run_list', view='summary', limit=8)))
    remaining = 32768
    for name, value in handoff['tasks']:
        read = dict(tool='run_status', name=name, intent='decision')
        item = projection.decision(name=name, value=value)
        # Task dispatch remains an explicit scheduler action; a handoff is read-only.
        item.pop('dispatch', None)
        item['read'] = read
        size = len(json.dumps(item, ensure_ascii=False).encode())
        if size > remaining:
            item = dict(name=name, state=value.state, output_artifact_name=item.get('output_artifact_name'), read=read)
            closeout['omissions'].append(dict(name=name, reason='handoff_context_limit', read=read))
        remaining -= len(json.dumps(item, ensure_ascii=False).encode())
        closeout['tasks'].append(item)
    if missing or handoff['unresolved_usage_identities']:
        status['usage']['coverage'] = 'partial' if records or status['usage'].get('groups') else 'missing'
    status['usage']['unmeasured_participants'] = missing
    status['usage']['unresolved_task_identities'] = handoff['unresolved_usage_identities']
    status['budget']['token_coverage'] = status['usage']['coverage']
    from .scientific_progress import progress_page, shadow_projection
    status['progress_shadow'] = shadow_projection(bindings=bindings, row=row)
    status['progress'] = progress_page(bindings=bindings, artifacts=artifacts, row=row,
        cursor=progress_cursor, limit=progress_limit)
    from .scientific_progress import terminal_delivery_page
    status['terminal_deliveries'] = dict(**terminal_delivery_page(bindings=bindings, row=row,
        cursor=delivery_cursor, limit=delivery_limit),
        meaning='Control delivery and decision boundary only; original reading and scientific value are not inferred.',
        coverage=checkpoint.get('terminal_delivery_coverage', 'controlled_briefs_and_structured_native_mcp_results'),
        limitations='Code-mode wrappers and arbitrary native tool output are not observable by this receipt.')
    status['external_work'] = external_work_view(bindings=bindings, runs=runs, artifacts=artifacts,
        executions=executions, row=row, related=current_runs)
    status['closeout'] = closeout
    return status


def external_work_view(*, bindings, runs, artifacts, executions, row, related):
    """Cached execution records only. A task's terminal state does not end its job."""
    view = dict(items=[], omissions=[], policy='remind_only', observation='persisted_state_only',
        association_coverage='exact_task_or_direct_goal_source',
        read=dict(tool='execution_list', surface='execution', limit=10))
    if executions is None:
        view['omissions'].append('execution_reader_unavailable')
        view['association_coverage'] = 'unknown'
        return view
    candidates = executions.active_ids(instance_id=row['instance_id'], scheduler_database_path=bindings.database_path, limit=33)
    if len(candidates) > 32:
        view['omissions'].append('execution_candidate_limit')
        view['association_coverage'] = 'partial'
    names = {identity: name for name, identity in related.items()}
    objective = json.loads(row['objective_ref_json'])
    previous = {item['run_id']: name for name, item in json.loads(row['checkpoint_json']).get('admissions', {}).items()
        if item.get('run_id') and item.get('objective_ref') and item['objective_ref'] != objective}
    candidate_records = []
    for execution_id in candidates[:32]:
        refs = executions.record_references(execution_id)
        owner = artifacts.catalog(refs['request_ref']).labels.get('experiment_run')
        candidate_records.append((execution_id, refs, owner))
    if any(owner and owner not in names and owner not in previous for _, _, owner in candidate_records) and not row.get('historical'):
        from ..schema.refs import ArtifactRef
        limits = json.loads(row['config_json']).get('effective', {}).get('progression', {})
        related_tasks, omitted = runs.goal_related_runs(instance_id=row['instance_id'],
            artifact_ref=ArtifactRef.model_validate(objective), limit=17,
            source_limit=limits.get('related_source_limit', 128), identities_only=True)
        if omitted or len(related_tasks) > 16:
            view['omissions'].append('goal_source_or_task_limit')
            view['association_coverage'] = 'partial'
        for task in related_tasks[:16]:
            name = bindings.find_name(instance=row['instance_id'], namespace='run', object_id=task)
            if name:
                names[task] = name
    owners = [owner for _, refs, owner in candidate_records if owner and (
        owner in names or owner in previous or refs['payload_ref'].model_dump(mode='json') == objective)]
    owner_states = runs.external_task_states(instance_id=row['instance_id'], run_ids=owners) if owners else {}
    for execution_id, refs, owner in candidate_records:
        if owner not in names and owner not in previous and refs['payload_ref'].model_dump(mode='json') != objective:
            # Standalone executions can name the exact goal as a direct original parent.
            payload = artifacts.catalog(refs['payload_ref'])
            if owner or not any(ref.model_dump(mode='json') == objective for ref in payload.parent_refs):
                view['association_coverage'] = 'partial'
                if 'candidate_goal_association_unconfirmed' not in view['omissions']:
                    view['omissions'].append('candidate_goal_association_unconfirmed')
                continue
        name = bindings.find_name(instance=row['instance_id'], namespace='execution', object_id=execution_id)
        value = executions.status(execution_id)
        task_name = names.get(owner) or previous.get(owner)
        task_active = owner is not None and owner_states[owner] in {'queued', 'running'}
        view['items'].append(dict(name=task_name or name, task_name=task_name, state=value.state,
            goal_scope='previous_goal' if owner in previous and owner not in names else 'current_goal',
            observer='task_worker' if task_active else 'not_verified_after_task_terminal',
            next_consumer='task_worker' if task_active else 'scheduler_on_resume_or_takeover',
            read=dict(tool='run_status', name=task_name, intent='decision') if task_name else
                dict(tool='execution_status', surface='execution', name=name), action='Observe and collect explicitly; cancellation is separate.'))
    return view
