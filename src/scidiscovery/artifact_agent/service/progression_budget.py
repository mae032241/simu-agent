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


def time_budget(checkpoint, limits, now):
    """One projection for admission, native deadlines and UI; never grants time."""
    from datetime import datetime
    from .research_loops import current_loop
    elapsed = enabled_time(checkpoint, now)
    remaining = max(0, limits['max_elapsed_seconds'] - elapsed)
    budget = dict(elapsed_seconds=elapsed, remaining_seconds=remaining,
        effective_remaining_seconds=remaining,
        time_coverage='enabled_intervals_including_active_recovery_gaps')
    identity = current_loop(checkpoint)
    if identity:
        record = checkpoint['loop_authorizations'][identity]
        if 'deadline_at' not in record:
            raise ValueError('Research loop natural deadline is missing; initialize a fresh state root.')
        start = datetime.fromisoformat(record['authorized_at']).timestamp()
        deadline = datetime.fromisoformat(record['deadline_at']).timestamp()
        current = max(now, checkpoint['time_high_water'], start)
        calendar_remaining = max(0, deadline - current)
        budget.update(deadline_at=record['deadline_at'], calendar_elapsed_seconds=current-start,
            calendar_remaining_seconds=calendar_remaining,
            effective_remaining_seconds=min(remaining, calendar_remaining),
            time_coverage='frozen_calendar_deadline_and_enabled_intervals_including_active_recovery_gaps')
    budget['time_exhaustion'] = ('calendar_deadline' if budget.get('calendar_remaining_seconds') == 0
        else 'enabled_time' if remaining == 0 else None)
    return budget


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


def _reconcile_attribution(record, *, role, owner):
    """Only control-resolved attribution may label an ownerless observation.

    Loop ownership is checked by the caller before this shared reduction. The
    existing usage path also resolves Root; lifecycle callers resolve attached
    Workers/helpers. Counters and native facts are not reset or reconstructed.
    """
    if record['role'] == 'unattributed' and role != 'unattributed':
        if record['owner'] is not None:
            raise ValueError('Unattributed usage has a conflicting original owner.')
        return {**record, 'role': role, 'owner': owner}
    if (record['role'], record['owner']) != (role, owner):
        raise ValueError('Native observation differs from its original role or owner.')
    return record


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
    if previous:
        previous = _reconcile_attribution(previous, role=role,
            owner=row['instance_id'] if role != 'unattributed' else None)
    record = observe_usage(params, previous=previous, role=role,
        owner=row['instance_id'] if role != 'unattributed' else None, outcome='running')
    records[thread] = {key: record[key] for key in ('platform', 'thread_id', 'role', 'owner',
        'outcome', 'high_water', 'counted_tokens', 'has_gaps', 'coverage')}
    if previous_record and role == 'root':
        records[thread].update({key: previous_record[key] for key in
            ('root_started_round', 'scheduler_session', 'retired', 'retired_after_round',
             'retired_after_turn', 'retired_after_activity', 'context_delivered') if key in previous_record})
    if previous_record:
        records[thread].update({key: previous_record[key] for key in ('native_turn', 'native_terminal') if key in previous_record})
    if loop_id:
        records[thread]['loop_id'] = loop_id
    if not independent:
        checkpoint['usage_summary'] = loop_usage_summary(checkpoint)


def apply_native_observation(db, row, checkpoint, observation):
    """Native lifecycle proof shares the existing exact thread usage identity."""
    from ...platforms.codex_usage import observe_usage
    from .progression_records import detail_record
    identity = observation['identity']
    thread = identity['thread_id']
    record = detail_record(db, row['instance_id'], 'usage_records', thread)
    if record is None:
        record = dict(observe_usage(dict(threadId=thread), role=identity['role'], owner=row['instance_id']),
            loop_id=identity['loop_id'], pending_observation=True)
    if record.get('loop_id') != identity['loop_id']:
        raise ValueError('Native lifecycle proof differs from the original thread usage identity.')
    record = _reconcile_attribution(record, role=identity['role'], owner=row['instance_id'])
    binding = identity['binding_key']
    turn_id = observation.get('turn_id')
    turn = dict(binding_key=binding,turn_id=turn_id,connection_id=observation.get('connection_id'))
    if observation['source'] == 'turn_started':
        record['native_turn'] = turn
        record.pop('native_terminal', None)
    elif observation['source'] == 'thread_read' or record.get('native_turn') == turn:
        record['native_terminal'] = dict(turn,state=observation['state'],event_version=observation.get('event_version'))
    checkpoint.setdefault('usage_records', {})[thread] = record
