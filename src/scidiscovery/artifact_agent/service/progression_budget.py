"""One advisory cost projection and existing-budget admission rule.

Observed Worker-thread costs are advisory, never a promise about future usage.
Cached input is already part of input_tokens. No budget is increased here.
"""


def enabled_time(checkpoint, now, *, enabled=None):
    """Project or settle one durable interval; rollback never refunds time.

    Only control transitions and the original accepted-work coordinator choose
    enabled. A retained open interval conservatively includes disconnect gaps.
    """
    fields = ('enabled_seconds', 'enabled_at', 'time_high_water')
    if not all(key in checkpoint for key in fields):
        if 'started_at' in checkpoint:
            raise ValueError('Incomplete progression time record; initialize a fresh state root.')
        return 0
    current = max(now, checkpoint['time_high_water'])
    elapsed = checkpoint['enabled_seconds'] + (max(0, current - checkpoint['enabled_at'])
        if checkpoint['enabled_at'] is not None else 0)
    if enabled is not None:
        if checkpoint.get('fault_class') == 'outcome_unknown' or (
                checkpoint.get('phase') == 'prepared' and not checkpoint.get('turn_id')):
            enabled = checkpoint['enabled_at'] is not None  # Uncertain native activity cannot become a free pause.
        checkpoint.update(enabled_seconds=elapsed, time_high_water=current,
            enabled_at=current if enabled else None)
    return elapsed


def token_budget(checkpoint, limits):
    from .research_loops import loop_usage
    records = loop_usage(checkpoint)
    used = 0
    worker_costs = []
    for record in records.values():
        tokens = record['counted_tokens']
        cost = tokens['input_tokens'] + tokens['output_tokens']
        used += cost
        if record.get('role') == 'worker':
            worker_costs.append(cost)
    remaining = max(0, limits['max_tokens'] - used)
    reserve = min(limits.get('closeout_reserve_tokens', 100000), limits['max_tokens'])
    estimate = max(worker_costs, default=0)
    return dict(remaining_tokens=remaining, closeout_reserve_tokens=reserve,
        observed_worker_thread_tokens=estimate or None,
        new_task_allowed=remaining > reserve,
        limitation='Observed usage may lag. Worker-thread cost is advisory, may span reused tasks and excludes helpers; it does not bound the next task. Reserve is inside the total budget.')


def require_task_budget(checkpoint, limits):
    from ...operations.invoke import OperationInvocationError
    budget = token_budget(checkpoint, limits)
    if not budget['new_task_allowed']:
        raise OperationInvocationError('background_closeout_budget_reserved',
            message='Remaining token budget is reserved for goal closeout; consume accepted results and '
                'report completion or remaining work. Do not retry admission or increase the budget. '
                f"Remaining={budget['remaining_tokens']}, reserve={budget['closeout_reserve_tokens']}.")


def apply_usage_observation(db, row, checkpoint, observation):
    """Reduce exact cumulative counters inside the same ledger write transaction."""
    from ...platforms.codex_usage import observe_usage
    from .progression_records import detail_record
    from .research_loops import current_loop, loop_usage_summary
    params, identity = observation['params'], observation['identity']
    thread = params.get('threadId')
    root = thread == observation['root_thread']
    previous_record = detail_record(db, row['instance_id'], 'usage_records', thread)
    role = 'root' if root else identity.get('role', 'unattributed')
    loop_id = current_loop(checkpoint) if root else identity.get('loop_id')
    if previous_record is not None:
        if loop_id is not None and previous_record.get('loop_id') != loop_id:
            raise ValueError('Native usage thread cannot be reassigned across research loops.')
        loop_id = previous_record.get('loop_id')
        if previous_record['role'] != 'unattributed':
            if role != 'unattributed' and role != previous_record['role']:
                raise ValueError('Native usage role differs from its original binding.')
            role = previous_record['role']
    elif role == 'unattributed':
        loop_id = current_loop(checkpoint)
    independent = bool(identity.get('interactive_session_id')) and not loop_id
    collection = 'interactive_usage_records' if independent else 'usage_records'
    records = checkpoint.setdefault(collection, {})
    previous = detail_record(db, row['instance_id'], collection, thread)
    if previous is not None and previous.get('loop_id') != loop_id:
        raise ValueError('Native usage thread cannot be reassigned across research loops.')
    if previous and previous.get('pending_observation'):
        previous = None
    other = detail_record(db, row['instance_id'],
        'usage_records' if independent else 'interactive_usage_records', thread)
    if other:
        previous = dict(previous or {**other, 'counted_tokens': dict.fromkeys(other['counted_tokens'], 0)})
        previous['high_water'] = {key: max(value for value in
            (previous['high_water'][key], other['high_water'][key]) if value is not None)
            if any(value is not None for value in (previous['high_water'][key], other['high_water'][key])) else None
            for key in previous['high_water']}
        previous['has_gaps'] = True
    if previous and previous['role'] == 'unattributed' and role != 'unattributed':
        previous = {**previous, 'role': role, 'owner': row['instance_id']}
    record = observe_usage(params, previous=previous, role=role,
        owner=row['instance_id'] if role != 'unattributed' else None, outcome='running')
    records[thread] = {key: record[key] for key in ('platform', 'thread_id', 'role', 'owner',
        'outcome', 'high_water', 'counted_tokens', 'has_gaps', 'coverage')}
    if loop_id:
        records[thread]['loop_id'] = loop_id
    if not independent:
        checkpoint['usage_summary'] = loop_usage_summary(checkpoint)
