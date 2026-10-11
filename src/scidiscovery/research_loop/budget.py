"""Append-only time facts and operator ceilings; no scientific scheduling."""
from __future__ import annotations

from contextlib import contextmanager
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
                or event.get('kind') not in {'clock', 'budget_amend'}):
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
        events.append(event)
        parent = hashlib.sha256(data).hexdigest()
    return events, parent


@contextmanager
def _ledger_writer(root):
    fd = os.open(root / 'control-ledger.lock', os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def _append(root, settings, events, parent, **fields):
    stamp = clock_stamp()
    if events:
        _duration(events[-1], stamp, legacy_elapsed=settings.get('time_budget_basis', 'elapsed') == 'elapsed')
    event = dict(seq=len(events) + 1, parent_sha256=parent,
                 settings_sha256=contracts.digest(root / 'settings.json'), **stamp, **fields)
    contracts.write(root / 'control-ledger' / f'{event["seq"]:06d}.json', event)
    return event


def snapshot(root, settings=None):
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
    now = clock_stamp()
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


def execution_blocked(root):
    """Unknown or live originals prohibit inactive time and amendments."""
    from . import runtime
    settings = contracts.settings(root)
    for step in range(1, settings['max_steps'] + 1):
        record = contracts.host_record(contracts.workspace(root, step))
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
                if runtime.process_matches(child, binding):
                    return True
        except (OSError, ValueError, KeyError, TypeError):
            return True
    return False


def inactive(root, reason):
    if execution_blocked(root):
        transition(root, 'advance', 'unknown_or_running_original')
    else:
        transition(root, 'paused', reason)


def amend(root, *, max_tokens=None, max_seconds=None, authorization_note):
    """Operator entry only. A note records a decision; it authenticates nobody."""
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
    if job['role'] == 'W' and settings.get('search_policy') is not None:
        limits['max_seconds'] = min(limits['max_seconds'], settings['search_policy']['max_w_seconds'])
        limits['max_observed_tokens'] = min(limits['max_observed_tokens'], settings['search_policy']['max_w_observed_tokens'])
    return limits


def _node_duration(root, job, intent, limits):
    anchor = intent.get('budget_slice')
    if (not isinstance(anchor, dict) or anchor.get('task_sha256') != contracts.digest(root / 'jobs' / f'{job["step"]:03d}.json')
            or anchor.get('role') != job['role'] or anchor.get('limits') != node_limits(root, job)
            or anchor.get('shared_limits') != {key: limits[key] for key in ('max_tokens', 'max_seconds')}
            or anchor.get('boot_id') != clock_stamp()['boot_id']
            or type(anchor.get('advance_seconds')) not in (int, float)
            or not math.isfinite(anchor['advance_seconds']) or anchor['advance_seconds'] < 0):
        raise ValueError('Accepted node budget identity or boot changed')
    duration = limits['advance_seconds'] - anchor['advance_seconds']
    if duration < 0:
        raise ValueError('Node consumption cannot move backwards')
    return duration


def node_admission(root, job, *, ignore_step=None, intent=None):
    policy = node_limits(root, job)
    if policy is None:
        return None
    from . import native
    limits, meter = snapshot(root), native.usage(root)
    if any(step != ignore_step for step in meter['unknown_steps']):
        return 'usage_unknown'
    duration = _node_duration(root, job, intent, limits) if intent is not None else 0.
    if limits['seconds_remaining'] < max(0., policy['max_seconds'] - duration):
        return 'node_budget_unavailable_seconds'
    if limits['max_tokens'] - meter['observed_tokens'] < policy['max_observed_tokens']:
        return 'node_budget_unavailable_tokens'
    return None


def accept_node(root, job):
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
    if duration >= policy['max_seconds']:
        return 'node_slice_time_limit'
    if meter['input_tokens'] + meter['output_tokens'] >= policy['max_observed_tokens']:
        return 'node_slice_token_limit'
    return None


def node_report(root, job, intent, meter):
    duration = _node_duration(root, job, intent, snapshot(root))
    return dict(role=job['role'], advance_seconds=duration, input_tokens=meter['input_tokens'],
                cached_input_tokens=meter['cached_input_tokens'], output_tokens=meter['output_tokens'],
                observed_tokens=meter['input_tokens'] + meter['output_tokens'], dispatches=1,
                limits=intent['budget_slice']['limits'])
