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
    records = checkpoint.get('usage_records', {})
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
