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


def _duration(before, after):
    wall = after['at_unix'] - before['at_unix']
    if wall < 0:
        raise ValueError('Control clock moved backwards; consumption is not refundable')
    if 'at_boottime' not in before:  # Legacy elapsed startup has no monotonic anchor.
        return wall
    if before['boot_id'] != after['boot_id']:
        raise ValueError('Control clock boot changed; elapsed interval cannot be verified')
    elapsed = after['at_boottime'] - before['at_boottime']
    # Sampling UTC and boottime separately introduces a few microseconds of skew.
    if elapsed < 0 or wall + .02 < elapsed:
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
                or events and event['at_unix'] < events[-1]['at_unix']
                or event.get('kind') not in {'clock', 'budget_amend'}):
            raise ValueError('Control ledger identity, sequence or time changed')
        if events:
            _duration(events[-1], event)
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
        _duration(events[-1], stamp)
    event = dict(seq=len(events) + 1, parent_sha256=parent,
                 settings_sha256=contracts.digest(root / 'settings.json'), **stamp, **fields)
    contracts.write(root / 'control-ledger' / f'{event["seq"]:06d}.json', event)
    return event


def snapshot(root, settings=None):
    original = contracts.settings(root)
    if settings is not None and settings != original:
        raise ValueError('Budget view differs from original frozen settings')
    settings = original
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
        _duration(events[-1], now)
    if start is not None:
        _duration(start, now)
    basis = settings.get('time_budget_basis', 'elapsed')
    if basis not in {'active', 'elapsed'}:
        raise ValueError('Unknown frozen time-budget basis')
    if basis == 'active' and start is not None and 'at_boottime' not in start:
        raise ValueError('Active clock requires its original boot anchor')
    advance = paused = unclassified = 0.
    phase, at = ('paused' if basis == 'active' else 'unclassified'), start
    for event in events:
        if event['kind'] != 'clock':
            continue
        if at is not None:
            duration = _duration(at, event)
            if phase == 'advance':
                advance += duration
            elif phase == 'paused':
                paused += duration
            else:
                unclassified += duration
        at, phase = event, event['phase']
    if at is not None:
        if phase == 'advance':
            advance += _duration(at, now)
        elif phase == 'paused':
            paused += _duration(at, now)
        else:
            unclassified += _duration(at, now)
    elapsed = _duration(start, now) if start is not None else 0.
    consumed = advance if basis == 'active' else (now['at_unix'] - start['at_unix'] if start else 0.)
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
