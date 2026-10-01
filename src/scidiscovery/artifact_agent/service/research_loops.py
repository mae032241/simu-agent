"""Budget identity projections in the existing scheduling control ledger.

The progression row selects the current scope. Authorization records retain
immutable UI provenance and configuration, with cumulative balances derived
from the same task and native usage records, including late observations.
"""
def current_loop(checkpoint):
    identity = checkpoint.get('current_loop_id')
    if identity is not None and identity not in checkpoint.get('loop_authorizations', {}):
        raise ValueError('Research loop authorization is missing; do not reset its budget.')
    return identity


def loop_usage(checkpoint, identity=None):
    identity = current_loop(checkpoint) if identity is None else identity
    records = checkpoint.get('usage_records', {})
    return {thread: record for thread, record in records.items()
        if identity is None or record.get('loop_id') == identity}


def loop_task_count(checkpoint, identity=None, *, kind=None):
    identity = current_loop(checkpoint) if identity is None else identity
    selected = [item for item in checkpoint.get('admissions', {}).values()
        if (item.get('loop_id') == identity if identity is not None else not item.get('interactive_session_id'))]
    if identity is not None and any(item.get('task_classification', {}).get('kind') not in
            {'research', 'independent_review'} for item in selected):
        raise ValueError('Research loop task classification is missing; do not infer or reset its budget.')
    return sum(kind is None or item.get('task_classification', {}).get('kind', 'research') == kind
        for item in selected)


def loop_task_budget(checkpoint, limits, identity=None):
    research = loop_task_count(checkpoint, identity, kind='research')
    reviews = loop_task_count(checkpoint, identity, kind='independent_review')
    return dict(tasks=research + reviews, research_tasks=research, independent_reviews=reviews,
        remaining_research_tasks=max(0, limits['max_tasks'] - research),
        remaining_independent_reviews=max(0, limits['max_reviews'] - reviews))


def loop_usage_summary(checkpoint, identity=None):
    from ...platforms.codex_usage import usage_summary
    identity = current_loop(checkpoint) if identity is None else identity
    records = loop_usage(checkpoint, identity)
    summary = usage_summary(list(records.values()))
    authorization = checkpoint.get('loop_authorizations', {}).get(identity, {})
    if authorization.get('unmeasured_frontend_root'):
        summary.update(coverage='partial' if records else 'missing',
            unmeasured_roles=['frontend_root', 'frontend_worker', 'frontend_helper'],
            limitation='Frontend Root, Worker and helper usage is not connected to native telemetry. Known tokens are a lower bound; '
                'bounded_fallback enforces known usage, task and enabled-time limits, not an all-role token hard cap.')
    return summary


def recovery_budget(checkpoint, limits):
    recovery = checkpoint.get('recovery', {})
    return dict(used=recovery.get('used', 0),
        by_kind=recovery.get('by_kind', {}),
        remaining=max(0, limits['max_recoveries']-recovery.get('used', 0)),
        consecutive_failures=recovery.get('consecutive_failures', 0),
        next_at=recovery.get('next_at'), pending_kind=recovery.get('pending_kind'),
        last_failure=recovery.get('last_failure'),
        failed_turns_enabled=limits['recover_failed_turns'],
        native_attempts_remaining=max(0, limits['max_attempts']-checkpoint.get('attempts', 0)))


def sync_loop_balances(checkpoint, now):
    """Late usage settles its original scope, never the current scope's balance."""
    from .progression_budget import time_budget, token_budget
    active = current_loop(checkpoint)
    scopes = checkpoint.get('_detail_projection', {}).get('scopes')
    for identity, record in checkpoint.get('loop_authorizations', {}).items():
        if scopes is not None and identity not in scopes and identity != active:
            continue  # Unread historical facts retain their last settled balance.
        limits = record['config']['effective']['progression']
        balance = dict(record.get('budget_snapshot') or {})
        if identity == active:
            balance.update(rounds=checkpoint.get('rounds', 0), attempts=checkpoint.get('attempts', 0),
                recovery=recovery_budget(checkpoint, limits), **time_budget(checkpoint, limits, now))
        balance.update(**loop_task_budget(checkpoint, limits, identity),
            **token_budget(dict(checkpoint, current_loop_id=identity), limits),
            usage=loop_usage_summary(checkpoint, identity))
        record['budget_snapshot'] = balance


def loop_scope_view(checkpoint):
    identity = current_loop(checkpoint)
    if identity is None:
        return dict(managed=False, scope='ordinary_interactive_instance_execution_limits')
    records = checkpoint['loop_authorizations']
    record = records[identity]
    return dict(managed=True, id=identity, authority='explicit_management_ui_budget_confirmation',
        authorized_at=record['authorized_at'], deadline_at=record['deadline_at'], limits=record['config']['effective']['progression'],
        history=[dict(id=key, authorized_at=value['authorized_at'], deadline_at=value['deadline_at'], budget=value.get('budget_snapshot'))
            for key, value in sorted(records.items(), key=lambda item: (item[1]['authorized_at'], item[0]))[-8:]],
        history_omitted=max(0, len(records)-8),
        scope='All subsequent interactive and background work uses this loop until explicit UI authorization of another loop. '
            'Goal changes, recovery and human continuation retain its budget. Instance execution pools remain cumulative.')
