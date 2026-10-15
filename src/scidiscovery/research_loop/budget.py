"""Append-only time facts and operator ceilings; no scientific scheduling."""
from __future__ import annotations

from contextlib import contextmanager
import errno
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import time

from . import contracts


def clock_stamp():
    return dict(at_unix=time.time(), at_boottime=time.clock_gettime(time.CLOCK_BOOTTIME),
                boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())


def _duration(before, after, *, legacy_elapsed=False):
    if 'at_boottime' not in before:  # Legacy elapsed startup has no monotonic anchor.
        wall = after['at_unix'] - before['at_unix']
        if wall < 0:
            raise ValueError('Control clock moved backwards; consumption is not refundable')
        return wall
    if before['boot_id'] != after['boot_id']:
        raise ValueError('Control clock boot changed; elapsed interval cannot be verified')
    elapsed = after['at_boottime'] - before['at_boottime']
    # UTC can slew or step without a boot-clock reversal. It is a display
    # timestamp, never a second authority over advancement consumption.
    # Legacy elapsed retains its previously frozen UTC refusal rules.
    wall = after['at_unix'] - before['at_unix']
    if elapsed < 0 or legacy_elapsed and (wall < 0 or wall + .02 < elapsed):
        raise ValueError('Control clock moved backwards; consumption is not refundable')
    return elapsed


def _events(root, settings):
    events, parent = [], None
    identity = contracts.digest(root / 'settings.json')
    for seq, path in enumerate(sorted((root / 'control-ledger').glob('*.json')), 1):
        data = contracts.regular(path).read_bytes()
        event = json.loads(data)
        if not isinstance(event, dict):
            raise ValueError('Invalid control ledger event')
        if (type(event.get('seq')) is not int or path.name != f'{seq:06d}.json' or event.get('seq') != seq
                or event.get('parent_sha256') != parent or event.get('settings_sha256') != identity
                or type(event.get('at_unix')) not in (int, float) or not math.isfinite(event['at_unix'])
                or type(event.get('at_boottime')) not in (int, float)
                or not math.isfinite(event['at_boottime']) or event['at_boottime'] < 0
                or not isinstance(event.get('boot_id'), str) or not event['boot_id']
                or event.get('kind') not in {'clock', 'budget_amend', 'closeout_begin', 'action_intent', 'action_outcome'}):
            raise ValueError('Control ledger identity, sequence or time changed')
        if events:
            _duration(events[-1], event, legacy_elapsed=settings.get('time_budget_basis', 'elapsed') == 'elapsed')
        if event['kind'] == 'budget_amend':
            for limits in (event.get('before'), event.get('after')):
                if (not isinstance(limits, dict) or set(limits) != {'max_tokens', 'max_seconds'}
                        or type(limits['max_tokens']) is not int or limits['max_tokens'] <= 0
                        or type(limits['max_seconds']) not in (int, float)
                        or not 0 < limits['max_seconds'] < float('inf')):
                    raise ValueError('Invalid audited budget ceilings')
            if not isinstance(event.get('authorization_note'), str) or not event['authorization_note'].strip():
                raise ValueError('Budget amendment has no operator decision')
        if event['kind'] == 'clock' and event.get('phase') not in {'advance', 'paused'}:
            raise ValueError('Unknown control clock phase')
        if event['kind'] == 'closeout_begin':
            if (type(event.get('source_cutoff')) is not int or event['source_cutoff'] < 0
                    or type(event.get('first_step')) is not int or event['first_step'] <= event['source_cutoff']
                    or type(event.get('preparation_seconds')) not in (int, float)
                    or not math.isfinite(event['preparation_seconds']) or event['preparation_seconds'] < 0
                    or not isinstance(event.get('stop_reason'), str) or event.get('mode') not in {'model', 'export_only'}):
                raise ValueError('Invalid immutable closeout boundary')
            if 'authorization_step' in event and (type(event['authorization_step']) is not int or event['authorization_step'] != event['source_cutoff']):
                raise ValueError('Direct delivery authorization must bind its exact scientific boundary')
        if event['kind'] == 'action_intent':
            if (event.get('action_kind') not in {'submit', 'confirm'} or not isinstance(event.get('action_id'), str)
                    or not isinstance(event.get('operation_id'), str) or not isinstance(event.get('decision'), dict)
                    or not isinstance(event.get('binding'), dict) or type(event.get('max_seconds')) not in (int, float)
                    or not 0 < event['max_seconds'] < float('inf')
                    or type(event.get('advance_seconds')) not in (int, float) or not math.isfinite(event['advance_seconds']) or event['advance_seconds'] < 0):
                raise ValueError('Invalid bounded delivery action intent')
        if event['kind'] == 'action_outcome' and (not isinstance(event.get('action_id'), str)
                or not isinstance(event.get('result'), dict) or event['result'].get('status') not in {'confirmed', 'failed', 'unknown', 'rejected', 'engineering_error', 'unclassified'}):
            raise ValueError('Invalid delivery action outcome')
        events.append(event)
        parent = hashlib.sha256(data).hexdigest()
    return events, parent


@contextmanager
def _ledger_writer(root):
    from .protocol import require_current
    require_current(root)
    fd = os.open(root / 'control-ledger.lock', os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def _append(root, settings, events, parent, **fields):
    from .protocol import require_current
    require_current(root)
    stamp = clock_stamp()
    if events:
        _duration(events[-1], stamp, legacy_elapsed=settings.get('time_budget_basis', 'elapsed') == 'elapsed')
    event = dict(seq=len(events) + 1, parent_sha256=parent,
                 settings_sha256=contracts.digest(root / 'settings.json'), **stamp, **fields)
    contracts.write(root / 'control-ledger' / f'{event["seq"]:06d}.json', event)
    return event


def snapshot(root, settings=None, *, sample_stamp=None):
    original = contracts.settings(root)
    if settings is not None and settings != original:
        raise ValueError('Budget view differs from original frozen settings')
    settings = original
    basis = settings.get('time_budget_basis', 'elapsed')
    if basis not in {'active', 'elapsed'}:
        raise ValueError('Unknown frozen time-budget basis')
    def interval(before, after):
        return _duration(before, after, legacy_elapsed=basis == 'elapsed')
    events, _ = _events(root, settings)
    limits = dict(max_tokens=settings['max_tokens'], max_seconds=settings['max_seconds'])
    for event in events:
        if event['kind'] == 'budget_amend':
            if event.get('before') != limits:
                raise ValueError('Budget amendment predecessor changed')
            limits = event['after']
    now = clock_stamp() if sample_stamp is None else sample_stamp
    started = root / 'host-started.json'
    start = contracts.read(started) if started.exists() else None
    if events:
        interval(events[-1], now)
    if start is not None:
        interval(start, now)
    if basis == 'active' and start is not None and 'at_boottime' not in start:
        raise ValueError('Active clock requires its original boot anchor')
    advance = paused = unclassified = 0.
    phase, at = ('paused' if basis == 'active' else 'unclassified'), start
    for event in events:
        if event['kind'] != 'clock':
            continue
        if at is not None:
            duration = interval(at, event)
            if phase == 'advance':
                advance += duration
            elif phase == 'paused':
                paused += duration
            else:
                unclassified += duration
        at, phase = event, event['phase']
    if at is not None:
        if phase == 'advance':
            advance += interval(at, now)
        elif phase == 'paused':
            paused += interval(at, now)
        else:
            unclassified += interval(at, now)
    elapsed = interval(start, now) if start is not None else 0.
    if basis == 'elapsed' and start is not None:
        elapsed = _duration(dict(at_unix=start['at_unix']), now)
    consumed = advance if basis == 'active' else elapsed
    return dict(**limits, time_budget_basis=basis, advance_seconds=advance,
                paused_seconds=paused, unclassified_seconds=unclassified, elapsed_seconds=elapsed, consumed_seconds=consumed,
                seconds_remaining=max(0., limits['max_seconds'] - consumed), clock_phase=phase,
                ledger_events=len(events), historical_time='unknown_before_ledger' if basis == 'elapsed' else 'recorded')


def transition(root, phase, reason):
    """Caller owns the host writer lock; runner must obtain it too."""
    from .protocol import require_current
    require_current(root)
    if phase not in {'advance', 'paused'}:
        raise ValueError('Unknown control clock phase')
    settings = contracts.settings(root)
    if not (root / 'host-started.json').exists():
        if phase == 'advance':
            raise ValueError('Advance clock requires an original host start')
        snapshot(root, settings)
        return
    with _ledger_writer(root):
        events, parent = _events(root, settings)
        # Check rollback even when the phase is unchanged.
        snapshot(root, settings)
        current = next((item['phase'] for item in reversed(events) if item['kind'] == 'clock'), None)
        if current != phase:
            _append(root, settings, events, parent, kind='clock', phase=phase, reason=reason)


def execution_blocked(root, *, ignore_operation=None):
    """Unknown or live originals prohibit inactive time and amendments."""
    from . import runtime, execution
    settings = contracts.settings(root)
    from . import delivery
    from . import audit_recovery
    if audit_recovery.blocked(root):
        return True
    if delivery.preparation_blocked(root):
        return True
    from . import candidate_audit
    if candidate_audit.blocked(root):
        return True
    if settings.get('selection_policy'):
        from . import shortlist
        if shortlist.blocked(root):
            return True
    state = closeout_state(root)
    if state['begin'] is not None and state['begin']['stop_reason'] == 'delivery_cleanup_unknown':
        return True  # A read-only resolver can still leave unknown local work.
    for action in state['actions']:
        outcome = action['outcome']
        if outcome is not None and not outcome['result']['cleanup_confirmed']:
            return True
        if outcome is None:
            paths = list((root / 'host-delivery/action-processes').glob(action['intent']['action_id'] + '-*.json'))
            final_phase = 'promote' if action['intent']['action_kind'] == 'submit' else 'confirm'
            if not any(path.name == action['intent']['action_id'] + '-' + final_phase + '.json' for path in paths):
                return True  # Popen/identity persistence window is truly unknown.
            for path in paths:
                record = contracts.read(contracts.regular(path))
                identity = record.get('identity', {})
                if not isinstance(identity, dict):
                    return True
                if (record.get('action_id') != action['intent']['action_id'] or record.get('operation_id') != action['intent']['operation_id']
                        or record.get('phase') not in {'audit', 'promote', 'confirm'}
                        or path.name != action['intent']['action_id'] + '-' + record['phase'] + '.json'
                        or identity.get('task_sha256') != action['intent']['operation_id']
                        or identity.get('boot_id') != clock_stamp()['boot_id']
                        or any(type(identity.get(key)) is not int or identity[key] <= 0 for key in ('pid', 'start_ticks', 'pgid', 'sid'))
                        or runtime.process_matches(identity, action['intent']['operation_id'])
                        or _delivery_group_live(identity)):
                    return True
    if any(op != ignore_operation for op in state['unresolved_operations']):
        return True
    for step in range(1, settings['max_steps'] + 1):
        record = execution.record(root, step)
        if not (record / 'native-intent.json').exists():
            continue
        try:
            binding = contracts.digest(root / 'jobs' / f'{step:03d}.json')
            if contracts.read(record / 'native-intent.json')['task_sha256'] != binding:
                return True
            outcome = contracts.read(record / 'native-outcome.json')
            if outcome.get('stop_reason') in {'native_error_unknown', 'cleanup_unknown'}:
                return True
            if not (type(outcome.get('returncode')) is int or outcome.get('native_started') is False):
                return True
            if (record / 'native-process.json').exists():
                child = contracts.read(record / 'native-process.json')
                if runtime.process_matches(child, execution.identity(root, step)):
                    return True
        except (OSError, ValueError, KeyError, TypeError):
            return True
    return False


def _delivery_group_live(identity):
    """Read-only recovery check under the launcher's same-group contract."""
    from . import runtime
    for path in Path('/proc').glob('[0-9]*'):
        try:
            member = runtime.process_identity(int(path.name), identity['task_sha256'])
        except OSError as error:
            if error.errno in {errno.ENOENT, errno.ESRCH}:
                continue
            return True  # An unobservable member is not cleanup proof.
        except (ValueError, IndexError, KeyError, TypeError):
            return True
        if member['state'] != 'Z' and member['sid'] == identity['sid'] and member['pgid'] == identity['pgid']:
            return True
    return False


def inactive(root, reason):
    from .protocol import require_current
    require_current(root)
    if execution_blocked(root):
        transition(root, 'advance', 'unknown_or_running_original')
    else:
        transition(root, 'paused', reason)


def amend(root, *, max_tokens=None, max_seconds=None, authorization_note):
    """Operator entry only. A note records a decision; it authenticates nobody."""
    from .protocol import require_current
    require_current(root)
    from .controller import _writer
    if not isinstance(authorization_note, str) or not authorization_note.strip():
        raise ValueError('An explicit operator authorization note is required')
    if max_tokens is None and max_seconds is None:
        raise ValueError('Specify a revised token or seconds ceiling')
    if max_tokens is not None and (type(max_tokens) is not int or max_tokens <= 0):
        raise ValueError('max_tokens must be a positive integer')
    if max_seconds is not None and (type(max_seconds) not in (int, float) or not 0 < max_seconds < float('inf')):
        raise ValueError('max_seconds must be positive and finite')
    with _writer(root):
        if execution_blocked(root):
            raise RuntimeError('Budget amendment requires no running or unknown original execution')
        settings = contracts.settings(root)
        with _ledger_writer(root):
            events, parent = _events(root, settings)
            value = snapshot(root, settings)
            before = {key: value[key] for key in ('max_tokens', 'max_seconds')}
            after = dict(before, **({} if max_tokens is None else dict(max_tokens=max_tokens)),
                         **({} if max_seconds is None else dict(max_seconds=max_seconds)))
            event = _append(root, settings, events, parent, kind='budget_amend', before=before,
                            after=after, authorization_note=authorization_note.strip())
        return dict(status='budget_amended', amendment_seq=event['seq'], before=before, after=after,
                    consumption='retained', authorization='operator_declaration_not_authentication')

class NodeBudgetUnavailable(ValueError):
    """An unaccepted node cannot fit its remaining authorized allocation."""
    def __init__(self, reason):
        super().__init__('Node budget admission refused: ' + reason)
        self.reason = reason


def node_mode(root):
    mode = contracts.settings(root).get('node_budget_mode', 'hard')
    if mode not in ('soft', 'hard'):
        raise ValueError('Frozen node budget mode changed')
    return mode


def node_policy(value):
    """Explicit operator ceilings for every role; there are no trial defaults."""
    if not isinstance(value, dict) or set(value) != {'H', 'W', 'A', 'E'}:
        raise ValueError('Node budget policy requires exactly H/W/A/E')
    for role, limits in value.items():
        if (not isinstance(limits, dict) or set(limits) != {'max_observed_tokens', 'max_seconds'}
                or type(limits['max_observed_tokens']) is not int or limits['max_observed_tokens'] <= 0
                or type(limits['max_seconds']) not in (int, float)
                or not 0 < limits['max_seconds'] < float('inf')):
            raise ValueError(f'Node budget {role} requires positive finite explicit ceilings')
    return {role: dict(limits) for role, limits in value.items()}


def node_limits(root, job):
    settings = contracts.settings(root)
    policy = settings.get('node_budget_policy')
    if policy is None:
        return None
    limits = node_policy(policy)[job['role']]
    if job.get('purpose') == 'closeout' and job['role']=='A':
        delivery = settings.get('delivery_policy')
        if delivery is None or job['role'] != 'A':
            raise ValueError('Unconfigured closeout node budget')
        limits = dict(delivery['closeout_a'])
    elif job['role'] in ('H', 'A') and settings.get('role_budget_policy') is not None and settings.get('node_budget_mode', 'hard') == 'soft':
        # A soft review/hint target only; hard mode keeps its explicit operator ceilings.
        limits['max_observed_tokens'] = min(limits['max_observed_tokens'], settings['role_budget_policy']['thinking_node_target_tokens'])
    if job['role'] == 'W' and settings.get('search_policy') is not None:
        limits['max_seconds'] = min(limits['max_seconds'], settings['search_policy']['max_w_seconds'])
        limits['max_observed_tokens'] = min(limits['max_observed_tokens'], settings['search_policy']['max_w_observed_tokens'])
    return limits



def _attempt_consumption(root, job, paths):
    """Derive cumulative consumption from exact completed native facts."""
    from . import native
    tokens, seconds = 0, 0.
    policy = node_limits(root, job)
    for number, path in enumerate(paths):
        intent = contracts.read(contracts.regular(path / 'native-intent.json'))
        anchor = intent.get('budget_slice', {})
        meter = contracts.read(contracts.regular(path / 'usage.json'))
        report = contracts.read(contracts.regular(path / 'native-outcome.json')).get('budget_slice', {})
        if (native._usage_event(dict(type='turn.completed', usage=meter)) != meter
                or intent.get('task_sha256') != contracts.digest(root / 'jobs' / f'{job["step"]:03d}.json')
                or anchor.get('limits') != policy or anchor.get('role') != job['role']
                or anchor.get('previous_tokens', 0) != tokens or anchor.get('previous_seconds', 0.) != seconds
                or not report.get('usage_observed') or report.get('limits') != policy
                or report.get('role') != job['role'] or report.get('dispatches') != number + 1
                or any(report.get(key) != meter[key] for key in ('input_tokens', 'cached_input_tokens', 'output_tokens'))):
            raise ValueError('Original node usage report or identity changed')
        tokens += meter['input_tokens'] + meter['output_tokens']
        duration = report.get('advance_seconds')
        if (type(duration) not in (int, float) or not math.isfinite(duration) or duration < seconds
                or report.get('observed_tokens') != tokens):
            raise ValueError('Original cumulative node consumption changed')
        seconds = duration
    return tokens, seconds

def _node_duration(root, job, intent, limits):
    anchor = intent.get('budget_slice')
    if (not isinstance(anchor, dict) or anchor.get('task_sha256') != contracts.digest(root / 'jobs' / f'{job["step"]:03d}.json')
            or anchor.get('role') != job['role'] or anchor.get('limits') != node_limits(root, job)
            or anchor.get('shared_limits') != {key: limits[key] for key in ('max_tokens', 'max_seconds')}
            or anchor.get('boot_id') != clock_stamp()['boot_id']
            or type(anchor.get('advance_seconds')) not in (int, float)
            or not math.isfinite(anchor['advance_seconds']) or anchor['advance_seconds'] < 0):
        raise ValueError('Accepted node budget identity or boot changed')
    prior = anchor.get('previous_seconds', 0.)
    prior_tokens = anchor.get('previous_tokens', 0)
    if type(prior_tokens) is not int or prior_tokens < 0:
        raise ValueError('Invalid original node token consumption')
    if intent.get('attempt') is not None:
        from . import execution
        number = intent['attempt']
        paths = execution.records(root, job['step'])
        if type(number) is not int or not 0 < number < len(paths):
            raise ValueError('Continuation has no exact original execution')
        original = _attempt_consumption(root, job, paths[:number])
        if (prior_tokens, prior) != original:
            raise ValueError('Continuation cannot refund original consumption')
    elif prior_tokens or prior:
        raise ValueError('Initial node cannot invent previous consumption')
    if type(prior) not in (int, float) or not math.isfinite(prior) or prior < 0:
        raise ValueError('Invalid original node consumption')
    duration = limits['advance_seconds'] - anchor['advance_seconds'] + prior
    if duration < 0:
        raise ValueError('Node consumption cannot move backwards')
    return duration


def node_admission(root, job, *, ignore_step=None, intent=None):
    policy = node_limits(root, job)
    if policy is None:
        return None
    from . import native
    if contracts.settings(root).get('resume_policy') is not None:
        additional = 0 if (root / 'jobs' / f'{job["step"]:03d}.json').exists() else 1
        if used_steps(root) + additional > contracts.settings(root)['max_steps']:
            return 'step_limit'
    limits, meter = snapshot(root), native.usage(root)
    if any(step != ignore_step for step in meter['unknown_steps']):
        return 'usage_unknown'
    duration = _node_duration(root, job, intent, limits) if intent is not None else 0.
    soft = node_mode(root) == 'soft'
    if (limits['seconds_remaining'] <= 0 if soft else
            limits['seconds_remaining'] < max(0., policy['max_seconds'] - duration)):
        return 'node_budget_unavailable_seconds'
    needed_tokens = max(0, policy['max_observed_tokens'] - (intent.get('budget_slice', {}).get('previous_tokens', 0) if intent else 0))
    if (limits['max_tokens'] - meter['observed_tokens'] <= 0 if soft else
            limits['max_tokens'] - meter['observed_tokens'] < needed_tokens):
        return 'node_budget_unavailable_tokens'
    if job.get('purpose') == 'closeout':
        settings = contracts.settings(root)
        delivery = settings['delivery_policy']
        begin = closeout_state(root)['begin']
        if begin is None or begin['mode'] != 'model' or begin['source_cutoff'] != job['source_cutoff']:
            raise ValueError('Closeout node has no exact model boundary')
        external = delivery['adapter'] is not None
        floor = closeout_floor(settings, preparation_seconds=begin['preparation_seconds'])
        if job.get('engineering_repair'):
            floor=dict(tokens=floor['tokens']+delivery['closeout_a']['max_observed_tokens'],seconds=floor['seconds']+delivery['closeout_a']['max_seconds'],steps=floor['steps']+1)
        additional = 0 if (root / 'jobs' / f'{job["step"]:03d}.json').exists() else 1
        seconds_unavailable = (limits['seconds_remaining'] <= floor['seconds'] if soft else
            limits['seconds_remaining'] < max(0., policy['max_seconds'] - duration) + floor['seconds'])
        tokens_unavailable = (limits['max_tokens'] - meter['observed_tokens'] <= floor['tokens'] if soft else
            limits['max_tokens'] - meter['observed_tokens'] < policy['max_observed_tokens'] + floor['tokens'])
        if (seconds_unavailable or tokens_unavailable
                or settings['max_steps'] - used_steps(root) < additional + floor['steps']):
            return 'closeout_budget_unavailable'
        return None
    return exploration_admission(root, job, ignore_step=ignore_step, intent=intent)


def accept_node(root, job):
    from .protocol import require_current
    require_current(root,job)
    policy = node_limits(root, job)
    if policy is None:
        return None
    reason = node_admission(root, job)
    if reason:
        raise NodeBudgetUnavailable(reason)
    limits, stamp = snapshot(root), clock_stamp()
    return dict(task_sha256=contracts.digest(root / 'jobs' / f'{job["step"]:03d}.json'), role=job['role'],
                boot_id=stamp['boot_id'], advance_seconds=limits['advance_seconds'], limits=policy,
                shared_limits={key: limits[key] for key in ('max_tokens', 'max_seconds')})


def stop_node(root, job, intent, limits, meter):
    policy = node_limits(root, job)
    if policy is None:
        return None
    duration = _node_duration(root, job, intent, limits)
    if node_mode(root) == 'soft':
        return None
    if duration >= policy['max_seconds']:
        return 'node_slice_time_limit'
    if meter['input_tokens'] + meter['output_tokens'] + intent['budget_slice'].get('previous_tokens', 0) >= policy['max_observed_tokens']:
        return 'node_slice_token_limit'
    return None


def node_report(root, job, intent, meter):
    duration = _node_duration(root, job, intent, snapshot(root))
    return dict(role=job['role'], advance_seconds=duration, input_tokens=meter['input_tokens'],
                cached_input_tokens=meter['cached_input_tokens'], output_tokens=meter['output_tokens'],
                observed_tokens=meter['input_tokens'] + meter['output_tokens'] + intent['budget_slice'].get('previous_tokens', 0), dispatches=1 + intent.get('attempt', 0),
                limits=intent['budget_slice']['limits'])


def accept_continuation(root, job, paths):
    from .protocol import require_current
    require_current(root,job)
    from . import native
    tokens, seconds = _attempt_consumption(root, job, paths)
    policy = node_limits(root, job)
    limits, meter = snapshot(root), native.usage(root)
    if (type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0
            or node_mode(root)=='hard' and (tokens >= policy['max_observed_tokens'] or seconds >= policy['max_seconds'])):
        raise NodeBudgetUnavailable('worker_resume_node_exhausted')
    settings = contracts.settings(root)
    soft = node_mode(root) == 'soft'
    reserve = (closeout_floor(settings, preparation_seconds=closeout_state(root)['begin']['preparation_seconds'])
        if soft and job.get('purpose') == 'closeout' else delivery_reserve(settings)) or dict(tokens=0, seconds=0, steps=0)
    needed_tokens = 0 if soft else max(0, policy['max_observed_tokens'] - tokens)
    needed_seconds = 0. if soft else max(0., policy['max_seconds'] - seconds)
    if (meter['unknown_steps'] or limits['max_tokens'] - meter['observed_tokens'] < needed_tokens + reserve['tokens']
            or limits['seconds_remaining'] < needed_seconds + reserve['seconds']
            or node_mode(root)=='soft' and (limits['max_tokens'] - meter['observed_tokens'] <= reserve['tokens'] or limits['seconds_remaining'] <= reserve['seconds'])
            or contracts.settings(root)['max_steps'] - used_steps(root) < 1 + reserve['steps']):
        raise NodeBudgetUnavailable('worker_resume_budget_unavailable')
    return dict(task_sha256=contracts.digest(root / 'jobs' / f'{job["step"]:03d}.json'), role=job['role'],
                boot_id=clock_stamp()['boot_id'], advance_seconds=limits['advance_seconds'], limits=policy,
                shared_limits={key: limits[key] for key in ('max_tokens', 'max_seconds')},
                previous_tokens=tokens, previous_seconds=seconds)


def closeout_state(root):
    """Only immutable control facts; no second balance or mutable mode file."""
    events, _ = _events(root, contracts.settings(root))
    begin, actions, operations = None, {}, {}
    for event in events:
        if event['kind'] == 'closeout_begin':
            if begin is not None:
                raise ValueError('Closeout boundary cannot be published twice')
            begin = event
        elif event['kind'] == 'action_intent':
            if begin is None or event['action_id'] in actions:
                raise ValueError('Delivery intent requires a unique closeout action')
            op = event['operation_id']
            expected = dict(decision=event['decision'], binding=event['binding'])
            if op in operations:
                if event['action_kind'] != 'confirm' or expected != operations[op]:
                    raise ValueError('Delivery may only confirm the exact accepted operation')
            elif event['action_kind'] != 'submit':
                raise ValueError('Confirmation has no original submit identity')
            else:
                operations[op] = expected
            actions[event['action_id']] = dict(intent=event, outcome=None)
        elif event['kind'] == 'action_outcome':
            action = actions.get(event['action_id'])
            if action is None or action['outcome'] is not None:
                raise ValueError('Delivery outcome requires its original intent')
            _validate_action_result(action['intent'], event['result'])
            action['outcome'] = event
    rows = list(actions.values())
    unresolved = []
    for op in operations:
        sequence = [row for row in rows if row['intent']['operation_id'] == op]
        confirmed = max((row['intent']['seq'] for row in sequence if row['outcome'] is not None
                         and row['outcome']['result']['status'] == 'confirmed'), default=0)
        if any(row['intent']['seq'] > confirmed and (row['outcome'] is None
               or row['outcome']['result']['status'] == 'unknown') for row in sequence):
            unresolved.append(op)
    return dict(begin=begin, actions=rows, unresolved_operations=unresolved)


def delivery_reserve(settings):
    policy = settings.get('delivery_policy')
    if policy is None:
        return None
    external = policy['adapter'] is not None
    authors = 1 if settings.get('node_budget_mode', 'hard') == 'soft' else 3
    return dict(tokens=authors * policy['closeout_a']['max_observed_tokens'] + policy['inflight_tokens'],
                seconds=authors * policy['closeout_a']['max_seconds'] + policy['cleanup_seconds']
                        + (policy['submit_seconds'] + policy['confirm_seconds'] if external else 0),
                steps=authors + (2 if external else 0))


def closeout_floor(settings, *, preparation_seconds=0.):
    """After exploration: retain execution allowance, not another whole A target."""
    policy = settings['delivery_policy']
    external = policy['adapter'] is not None
    return dict(tokens=policy['inflight_tokens'],
                seconds=max(0., policy['cleanup_seconds'] - preparation_seconds)
                    + (policy['submit_seconds'] + policy['confirm_seconds'] if external else 0),
                steps=2 if external else 0)


def used_steps(root):
    from . import execution
    prepared = [int(path.stem) for path in (root / 'jobs').glob('*.json')]
    continuations = sum(len(execution.records(root, step)) - 1 for step in prepared)
    from . import candidate_audit
    from . import audit_recovery
    audits = sum(1 for _ in candidate_audit.facts(root)) + sum(1 for _ in audit_recovery.facts(root))
    if contracts.settings(root).get('selection_policy'):
        from . import shortlist
        audits += shortlist.calls(root)  # Control screening calls are bounded external actions too.
    return max(prepared, default=0) + continuations + len(closeout_state(root)['actions']) + audits


def exploration_admission(root, job, *, ignore_step=None, intent=None):
    settings = contracts.settings(root)
    reserve = delivery_reserve(settings)
    if reserve is None or job.get('purpose') == 'closeout':
        return None
    from . import native
    limits, meter = snapshot(root), native.usage(root)
    node = node_limits(root, job)
    if any(step != ignore_step for step in meter['unknown_steps']):
        return 'usage_unknown'
    soft = node_mode(root) == 'soft'
    needed_tokens = 0 if soft else max(0, node['max_observed_tokens'] - (intent.get('budget_slice', {}).get('previous_tokens', 0) if intent else 0))
    if (limits['max_tokens'] - meter['observed_tokens'] <= reserve['tokens'] if soft else
            limits['max_tokens'] - meter['observed_tokens'] < needed_tokens + reserve['tokens']):
        return 'closeout_reserve_tokens'
    duration = _node_duration(root, job, intent, limits) if intent is not None else 0.
    if (limits['seconds_remaining'] <= reserve['seconds'] if soft else
            limits['seconds_remaining'] < max(0., node['max_seconds'] - duration) + reserve['seconds']):
        return 'closeout_reserve_seconds'
    additional = 0 if (root / 'jobs' / f'{job["step"]:03d}.json').exists() else 1
    if settings['max_steps'] - used_steps(root) < additional + reserve['steps']:
        return 'closeout_reserve_steps'
    return None


def begin_closeout(root, cutoff, first_step, reason, *, export_only=False, delivery_sources=None, preparation_seconds=0., authorization_step=None):
    from .protocol import require_current
    require_current(root)
    settings = contracts.settings(root)
    with _ledger_writer(root):
        events, parent = _events(root, settings)
        existing = closeout_state(root)['begin']
        if existing is not None:
            return existing
        return _append(root, settings, events, parent, kind='closeout_begin', source_cutoff=cutoff,
                       first_step=first_step, stop_reason=reason, mode='export_only' if export_only else 'model',
                       delivery_sources=delivery_sources, preparation_seconds=preparation_seconds,
                       **(dict(authorization_step=authorization_step) if authorization_step is not None else {}))


def accept_action(root, kind, operation_id, decision, binding, max_seconds):
    from .protocol import require_current
    require_current(root)
    settings = contracts.settings(root)
    begin = closeout_state(root)['begin']
    if (settings.get('delivery_policy') is None or settings['delivery_policy']['adapter'] is None
            or begin is None or begin['mode'] != 'model'):
        raise ValueError('External delivery requires its frozen model closeout authorization')
    if kind not in {'submit', 'confirm'} or execution_blocked(root, ignore_operation=operation_id if kind == 'confirm' else None):
        raise RuntimeError('Delivery action is blocked by an original unresolved execution')
    from . import native
    meter = native.usage(root)
    limits = snapshot(root)
    if meter['unknown_steps'] or meter['observed_tokens'] >= limits['max_tokens']:
        raise NodeBudgetUnavailable('closeout_budget_unavailable')
    if limits['seconds_remaining'] < max_seconds or used_steps(root) >= settings['max_steps']:
        raise NodeBudgetUnavailable('closeout_budget_unavailable')
    with _ledger_writer(root):
        events, parent = _events(root, settings)
        action_id = f'action-{len(events) + 1:06d}'
        return _append(root, settings, events, parent, kind='action_intent', action_id=action_id,
                       action_kind=kind, operation_id=operation_id, decision=decision, binding=binding,
                       max_seconds=max_seconds, advance_seconds=limits['advance_seconds'])


def action_outcome(root, intent, result):
    from .protocol import require_current
    require_current(root)
    settings = contracts.settings(root)
    _validate_action_result(intent, result)
    with _ledger_writer(root):
        events, parent = _events(root, settings)
        return _append(root, settings, events, parent, kind='action_outcome', action_id=intent['action_id'], result=result)


def exploration_stop(root, job, limits):
    reserve = delivery_reserve(contracts.settings(root))
    if reserve is None or job.get('purpose') == 'closeout' or node_mode(root)=='soft':
        return None
    from . import native
    if limits['seconds_remaining'] <= reserve['seconds']:
        return 'closeout_protected_time_limit'
    if limits['max_tokens'] - native.usage(root)['observed_tokens'] <= reserve['tokens']:
        return 'closeout_protected_token_limit'
    return None


def _validate_action_result(intent, result):
    binding = intent['binding']
    if (set(result) - {'failure_phase','diagnostic'} != {'status', 'operation_id', 'candidate_id', 'artifact_sha256', 'note', 'cleanup_confirmed'}
            or 'failure_phase' in result and (result['status'] not in {'failed', 'rejected', 'engineering_error', 'unclassified', 'unknown'} or result['failure_phase'] not in {'audit', 'promote', 'confirm'})
            or 'diagnostic' in result and (not isinstance(result['diagnostic'],str) or len(result['diagnostic'].encode())>4096)
            or result['status'] not in {'confirmed', 'failed', 'unknown', 'rejected', 'engineering_error', 'unclassified'}
            or type(result['cleanup_confirmed']) is not bool
            or not result['cleanup_confirmed'] and result['status'] != 'unknown'
            or result['operation_id'] != intent['operation_id']
            or result['candidate_id'] != binding['candidate_id']
            or not isinstance(result['note'], str) or len(result['note'].encode()) > 4096
            or result['artifact_sha256'] not in {None, binding['source']['objects']['artifact']['sha256']}
            or result['status'] == 'confirmed' and result['artifact_sha256'] != binding['source']['objects']['artifact']['sha256']):
        raise ValueError('Delivery result differs from its exact accepted candidate and artifact')


def action_process(root, intent, phase, identity):
    from .protocol import require_current
    require_current(root)
    if phase not in {'audit', 'promote', 'confirm'} or identity['task_sha256'] != intent['operation_id']:
        raise ValueError('Delivery process differs from its exact action phase')
    path = root / 'host-delivery/action-processes' / (intent['action_id'] + '-' + phase + '.json')
    if path.exists() or path.is_symlink():
        raise ValueError('Delivery action phase cannot launch twice')
    contracts.write(path, dict(action_id=intent['action_id'], operation_id=intent['operation_id'], phase=phase, identity=identity))


def write_node_hint(root, job, intent, limits, meter, *, observed):
    """Optional replaceable advice; never read as a grant, meter or evidence."""
    from .protocol import require_current
    require_current(root,job)
    if node_mode(root)!='soft':
        return
    publish_review(root,job,intent,limits,meter,observed=observed)
    targets=node_limits(root,job)
    duration=_node_duration(root,job,intent,limits) if targets else None
    if targets is None and job['role']=='W' and job.get('search'):
        from . import search
        search.stop_reason(root,job,intent,limits,meter)
        targets=dict(max_observed_tokens=job['search']['limits']['max_w_observed_tokens'],max_seconds=job['search']['limits']['max_w_seconds'])
        duration=limits['advance_seconds']-intent['search_slice']['advance_seconds']
    prior=intent.get('budget_slice',{}).get('previous_tokens',0)
    consumed=prior+meter['input_tokens']+meter['output_tokens'] if observed else None
    settings = contracts.settings(root)
    closeout = job.get('purpose') == 'closeout'
    reserve = (closeout_floor(settings, preparation_seconds=closeout_state(root)['begin']['preparation_seconds'])
        if closeout else delivery_reserve(settings)) or dict(tokens=0,seconds=0,steps=0)
    from . import native
    shared=native.usage(root)
    remaining=limits['max_tokens']-shared['observed_tokens']
    state=('reached' if targets and ((consumed is not None and consumed>=targets['max_observed_tokens']) or duration>=targets['max_seconds'])
           else 'near' if targets and ((consumed is not None and consumed>=.8*targets['max_observed_tokens']) or duration>=.8*targets['max_seconds']) else 'within')
    hint=dict(scope='advice_only_not_authorization_or_scientific_evidence',updated_at_unix=time.time(),mode='soft',
        target_state=state,targets=targets,active_seconds=duration,observed_tokens_lower_bound=consumed,
        metering='observed_lower_bound' if observed else 'inflight_unknown',
        shared_observed_tokens_remaining_upper_bound=max(0,remaining),shared_active_seconds_remaining=limits['seconds_remaining'],
        reserve_state='reached' if remaining<=reserve['tokens'] or limits['seconds_remaining']<=reserve['seconds'] else 'within',
        reserve_scope='external_closeout_floor' if closeout else 'minimal_closeout_reserve',
        current_work_observed_tokens_remaining_upper_bound=max(0,remaining-reserve['tokens']),
        current_work_active_seconds_available=max(0.,limits['seconds_remaining']-reserve['seconds']),
        instruction='Near/reached targets or reserve: finish bounded actions and return your scientific JSON. Unknown usage is not zero. Shared hard limits still apply.')
    data=(json.dumps(hint,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    if len(data)>4096:raise ValueError('Budget advice exceeds byte bound')
    directory=contracts.workspace(root,job['step'])/'work'
    fd=None;temporary=None
    try:
        if directory.resolve()!=directory or directory.is_symlink():return
        destination=directory/'budget-status.json'
        if destination.is_symlink() or destination.exists() and not destination.is_file():
            return
        fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        identity=os.fstat(fd)
        temporary='.budget-hint-'+os.urandom(12).hex()+'.tmp'
        item=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=fd)
        with os.fdopen(item,'wb') as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno());os.fchmod(stream.fileno(),0o400)
        current=os.stat(directory,follow_symlinks=False)
        if (current.st_dev,current.st_ino)!=(identity.st_dev,identity.st_ino):return
        os.replace(temporary,'budget-status.json',src_dir_fd=fd,dst_dir_fd=fd);temporary=None
    except OSError:
        pass  # Advice unavailable cannot weaken or replace the independent guards.
    finally:
        if fd is not None:
            if temporary is not None:
                try:os.unlink(temporary,dir_fd=fd)
                except OSError:pass
            os.close(fd)


def _review_directory(root,job):
    return Path(root)/'host-runtime/experiment-control'/contracts.digest(Path(root)/'jobs'/f'{job["step"]:03d}.json')


def review_configuration(root,job):
    """Host-owned projection, shared by every implementation of this stage."""
    from .protocol import require_current
    require_current(root,job)
    from . import execution,experiments
    settings=contracts.settings(Path(root))
    if settings.get('managed_admission_version')!=experiments.ADMISSION_VERSION or job.get('managed_admission_version')!=experiments.ADMISSION_VERSION:
        raise experiments.UnsupportedExecution('Preserved review contract is read-only; prepare a new instance')
    if node_mode(root)!='soft':return dict(version=experiments.ADMISSION_VERSION,mode='hard')
    directory=_review_directory(root,job);directory.mkdir(parents=True,exist_ok=True)
    if directory.resolve()!=directory:raise ValueError('Host review directory changed')
    fd=os.open(directory/'accept.lock',os.O_RDONLY|os.O_CREAT|os.O_NOFOLLOW|os.O_CLOEXEC,0o444);os.close(fd)
    record=execution.record(root,job['step'])
    intent=contracts.read(contracts.regular(record/'native-intent.json'))
    meter=contracts.read(record/'usage.json') if (record/'usage.json').exists() else dict(input_tokens=0,cached_input_tokens=0,output_tokens=0)
    publish_review(root,job,intent,snapshot(Path(root)),meter,observed=(record/'usage.json').exists())
    return dict(version=experiments.ADMISSION_VERSION,mode='soft',directory=str(directory),
        stage_anchor=contracts.digest(Path(root)/'jobs'/f'{job["step"]:03d}.json'))


def publish_review(root,job,intent,limits,meter,*,observed):
    """Derive replaceable facts from original anchors, never an additional budget."""
    from .protocol import require_current
    require_current(root,job)
    from . import execution,experiments,native,search
    from .protocol import stage_scope
    root=Path(root);settings=contracts.settings(root)
    if job.get('managed_admission_version')!=experiments.ADMISSION_VERSION or settings.get('managed_admission_version')!=experiments.ADMISSION_VERSION:
        raise experiments.UnsupportedExecution('Preserved review contract is read-only; prepare a new instance')
    if node_mode(root)!='soft':return
    directory=_review_directory(root,job);directory.mkdir(parents=True,exist_ok=True)
    if directory.resolve()!=directory:raise ValueError('Host review directory changed')
    fd=os.open(directory/'accept.lock',os.O_RDONLY|os.O_CREAT|os.O_NOFOLLOW|os.O_CLOEXEC,0o444)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX)
        stamp=clock_stamp()
        limits=snapshot(root,sample_stamp=stamp)
        record=execution.record(root,job['step'])
        intent=contracts.read(contracts.regular(record/'native-intent.json'))
        observed=(record/'usage.json').exists()
        meter=contracts.read(contracts.regular(record/'usage.json')) if observed else dict(input_tokens=0,output_tokens=0)
        task=contracts.digest(root/'jobs'/f'{job["step"]:03d}.json')
        if intent.get('task_sha256')!=task:raise ValueError('Review publication has no exact native task')
        targets=node_limits(root,job);duration=None
        if targets is not None:duration=_node_duration(root,job,intent,limits)
        elif job['role']=='W' and job.get('search'):
            search.stop_reason(root,job,intent,limits,meter)
            targets=dict(max_observed_tokens=job['search']['limits']['max_w_observed_tokens'],max_seconds=job['search']['limits']['max_w_seconds'])
            duration=limits['advance_seconds']-intent['search_slice']['advance_seconds']
        prior=intent.get('budget_slice',{}).get('previous_tokens',0)
        consumed=prior+meter['input_tokens']+meter['output_tokens'] if observed else prior
        reserve=delivery_reserve(settings) or dict(tokens=0,seconds=0,steps=0)
        shared=native.usage(root)
        # The original grant remains the ceiling for this accepted stage.
        grant=intent.get('budget_slice',{}).get('shared_limits',dict(max_tokens=settings['max_tokens'],max_seconds=settings['max_seconds']))
        available_tokens=min(limits['max_tokens'],grant['max_tokens'])-shared['observed_tokens']-reserve['tokens']
        available_seconds=min(limits['seconds_remaining'],max(0.,grant['max_seconds']-limits['consumed_seconds']))-reserve['seconds']
        remaining=min(available_seconds,max(0.,targets['max_seconds']-duration)) if targets else available_seconds
        reason=('shared_usage_unknown' if any(step!=job['step'] for step in shared['unknown_steps']) else
            'reserve_reached' if available_seconds<=0 or available_tokens<=0 else
            'target_time_reached' if targets and duration>=targets['max_seconds'] else
            'target_tokens_reached' if targets and consumed>=targets['max_observed_tokens'] else None)
        value=dict(version=experiments.ADMISSION_VERSION,stage_anchor=task,
            scope=stage_scope(root,job),
            native_attempt=dict(number=len(execution.records(root,job['step']))-1,execution_key=execution.identity(root,job['step'])),
            boot_id=stamp['boot_id'],observed_at=stamp['at_unix'],deadline_boottime=stamp['at_boottime']+max(0.,remaining),
            valid_until_boottime=stamp['at_boottime']+10,pending=bool(reason),reason=reason,
            observed_tokens_lower_bound=consumed,inflight_usage_unknown=True,targets=targets)
        path=directory/'review.json'
        if path.exists():
            old=contracts.read(contracts.regular(path))
            if old.get('stage_anchor')!=task or old.get('scope')!=value['scope'] or old.get('boot_id')!=stamp['boot_id']:
                raise ValueError('Host review projection binding changed')
        contracts.write(path,value);path.chmod(0o400)
    finally:os.close(fd)
