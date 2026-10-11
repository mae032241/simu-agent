"""Budget control facts, with simulated time and no model execution."""
import json
from pathlib import Path

import pytest

from scidiscovery.research_loop import budget, contracts, controller, native, runtime
from scidiscovery.research_loop.cli import main, status


@pytest.fixture
def clocked(tmp_path, monkeypatch):
    public = tmp_path / 'public'
    public.mkdir()
    objective = public / 'objective.md'
    objective.write_text('Resolve a bounded mechanism.')
    root = tmp_path / 'instance'
    controller.prepare(root, objective, public, ['fixture-never-launch'], max_tokens=100,
        max_seconds=20, max_steps=3, model='fixture', reasoning_effort='high')
    now = [100.]
    monkeypatch.setattr(budget.time, 'time', lambda: now[0])
    monkeypatch.setattr(budget.time, 'clock_gettime', lambda _: now[0])
    contracts.write(root / 'host-started.json', budget.clock_stamp())
    return root, now


def transition(root, phase):
    with controller._writer(root):
        budget.transition(root, phase, 'fixture transition')


def original_intent(root):
    contracts.build_job(root, 1, 'H', [])
    record = contracts.host_record(contracts.workspace(root, 1))
    contracts.write(record / 'native-intent.json', dict(step=1,
        task_sha256=contracts.digest(root / 'jobs/001.json')))
    return record


def test_active_clock_counts_overlapping_control_and_native_once(clocked):
    root, now = clocked
    transition(root, 'advance')
    now[0] = 105.
    transition(root, 'advance')  # Joining the same execution is no new interval.
    assert budget.snapshot(root)['advance_seconds'] == 5
    assert budget.snapshot(root)['ledger_events'] == 1
    transition(root, 'paused')
    now[0] = 130.
    value = budget.snapshot(root)
    assert value['advance_seconds'] == 5
    assert value['paused_seconds'] == 25
    assert value['elapsed_seconds'] == 30
    assert value['seconds_remaining'] == 15
    transition(root, 'advance')
    now[0] = 134.
    assert budget.snapshot(root)['advance_seconds'] == 9
    assert budget.snapshot(root)['seconds_remaining'] == 11


def test_pause_request_and_restart_do_not_make_unknown_time_free(clocked):
    root, now = clocked
    transition(root, 'advance')
    record = original_intent(root)
    now[0] = 110.
    assert main(['pause', '--root', str(root)]) == 0
    assert budget.snapshot(root)['clock_phase'] == 'advance'
    now[0] = 120.
    assert controller.run(root)['status'] == 'native_outcome_unsealed'
    assert budget.snapshot(root)['consumed_seconds'] == 20
    now[0] = 160.
    # A later observation may prove the old execution ended; never backdate
    # the closed clock to its claimed old timestamp and refund unknown time.
    contracts.write(record / 'native-outcome.json', dict(returncode=1, stop_reason=None,
        finished_at_unix=105., cleanup='observed_group_cleaned', usage=dict(unknown_steps=[])))
    assert controller.run(root)['status'] == 'native_outcome_unsealed'
    assert budget.snapshot(root)['clock_phase'] == 'paused'
    assert budget.snapshot(root)['advance_seconds'] == 60
    now[0] = 200.
    assert budget.snapshot(root)['advance_seconds'] == 60
    assert budget.snapshot(root)['paused_seconds'] == 40


def test_explicit_pause_stays_paused_across_run_restarts(clocked):
    root, now = clocked
    transition(root, 'advance')
    now[0] = 105.
    assert main(['pause', '--root', str(root)]) == 0
    now[0] = 200.
    assert controller.run(root)['status'] == 'paused'
    assert controller.run(root)['status'] == 'paused'
    assert budget.snapshot(root)['advance_seconds'] == 5
    assert budget.snapshot(root)['paused_seconds'] == 95
    assert not (root / 'jobs').exists()


def test_budget_amend_is_audited_and_preserves_consumption_and_settings(clocked, capsys):
    root, now = clocked
    frozen = (root / 'settings.json').read_bytes()
    transition(root, 'advance')
    now[0] = 108.
    transition(root, 'paused')
    now[0] = 150.
    assert main(['budget-amend', '--root', str(root), '--max-tokens', '200', '--max-seconds', '30',
                 '--authorization-note', 'Operator authorizes this explicit ceiling.']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['authorization'] == 'operator_declaration_not_authentication'
    assert result['consumption'] == 'retained'
    value = budget.snapshot(root)
    assert value['advance_seconds'] == 8
    assert value['max_tokens'] == 200
    assert value['seconds_remaining'] == 22
    assert (root / 'settings.json').read_bytes() == frozen
    events, _ = budget._events(root, contracts.settings(root))
    assert [item['seq'] for item in events] == [1, 2, 3]
    assert events[2]['parent_sha256'] == contracts.digest(root / 'control-ledger/000002.json')
    assert events[2]['before'] == dict(max_tokens=100, max_seconds=20)
    assert events[2]['after'] == dict(max_tokens=200, max_seconds=30)
    assert events[2]['at_unix'] == 150


@pytest.mark.parametrize('note,changes', [('', dict(max_tokens=200)), ('Decision', {}),
    ('Decision', dict(max_tokens=True)), ('Decision', dict(max_seconds=float('nan')))])
def test_amend_rejects_missing_decision_or_invalid_ceiling(clocked, note, changes):
    root, now = clocked
    with pytest.raises(ValueError):
        budget.amend(root, authorization_note=note, **changes)
    assert not (root / 'control-ledger').exists()


def test_amend_rejects_writer_or_unknown_execution(clocked):
    root, now = clocked
    with controller._writer(root):
        with pytest.raises(RuntimeError, match='running controller'):
            budget.amend(root, max_tokens=200, authorization_note='Explicit operator decision')
    original_intent(root)
    with pytest.raises(RuntimeError, match='running or unknown'):
        budget.amend(root, max_tokens=200, authorization_note='Explicit operator decision')
    assert not (root / 'control-ledger').exists()


def test_runner_inactive_append_holds_host_writer_until_finished(clocked, monkeypatch):
    root, now = clocked
    transition(root, 'advance')
    now[0] = 103.
    original = budget.inactive
    def check_lock(root, reason):
        with pytest.raises(RuntimeError, match='running controller'):
            with controller._writer(root):
                pytest.fail('A second writer entered during runner stop append')
        original(root, reason)
    monkeypatch.setattr(budget, 'inactive', check_lock)
    runtime._complete_clock(root)
    assert budget.snapshot(root)['clock_phase'] == 'paused'
    transition(root, 'advance')
    with controller._writer(root):
        runtime._complete_clock(root)  # A live controller cannot be stopped.
    assert budget.snapshot(root)['clock_phase'] == 'advance'


@pytest.mark.parametrize('action', ['snapshot', 'transition', 'amend'])
def test_boot_clock_rollback_fails_closed_without_refunding_or_appending(clocked, monkeypatch, action):
    root, now = clocked
    transition(root, 'advance')
    now[0] = 110.
    transition(root, 'paused')
    before = {path.name: path.read_bytes() for path in (root / 'control-ledger').glob('*.json')}
    now[0] = 112.  # Advancing UTC cannot hide a negative boot-clock interval.
    monkeypatch.setattr(budget.time, 'clock_gettime', lambda _: 109.)
    with pytest.raises(ValueError, match='backwards'):
        if action == 'snapshot':
            budget.snapshot(root)
        elif action == 'transition':
            transition(root, 'advance')
        else:
            budget.amend(root, max_seconds=50, authorization_note='Explicit operator decision')
    assert {path.name: path.read_bytes() for path in (root / 'control-ledger').glob('*.json')} == before


@pytest.mark.parametrize('action', ['snapshot', 'transition', 'amend'])
def test_open_interval_utc_rollback_cannot_refund_observed_consumption(clocked, monkeypatch, action):
    root, now = clocked
    ticks = [100.]
    monkeypatch.setattr(budget.time, 'clock_gettime', lambda _: ticks[0])
    transition(root, 'advance')
    now[0] = ticks[0] = 120.
    assert budget.snapshot(root)['consumed_seconds'] == 20
    now[0] = 110.  # UTC reversed; the actual boot-clock consumption did not.
    if action == 'snapshot':
        assert budget.snapshot(root)['consumed_seconds'] == 20
    elif action == 'transition':
        transition(root, 'paused')
    else:
        budget.amend(root, max_seconds=50, authorization_note='Explicit operator decision')
    assert budget.snapshot(root)['consumed_seconds'] == 20
    now[0] = ticks[0] = 130.
    assert budget.snapshot(root)['consumed_seconds'] == (20 if action == 'transition' else 30)


def test_case02_clock_slew_uses_boot_consumption_without_false_stop(clocked, monkeypatch):
    root, now = clocked
    settings = contracts.settings(root)
    settings['max_seconds'] = 3600
    contracts.write(root / 'settings.json', settings)
    contracts.write(root / 'settings-identity.json', dict(sha256=contracts.digest(root / 'settings.json')))
    # Replay the observed same-boot case02 anchors, without touching that instance.
    now[0] = 1791694089.621297
    ticks = [2899.955554225]
    monkeypatch.setattr(budget.time, 'clock_gettime', lambda _: ticks[0])
    contracts.write(root / 'host-started.json', budget.clock_stamp())
    transition(root, 'advance')
    now[0], ticks[0] = 1791694169.1294773, 2979.883511218
    observed = budget.snapshot(root)
    assert observed['consumed_seconds'] == pytest.approx(79.927956993)
    assert observed['seconds_remaining'] == pytest.approx(3520.072043007)
    assert controller._launch_limit(root, settings) is None
    transition(root, 'paused')
    before = observed['consumed_seconds']
    # UTC may even step below an earlier display timestamp. Ledger ordering
    # and consumed time remain governed by BOOTTIME, not UTC.
    now[0], ticks[0] = 1791694080., ticks[0] + 5
    transition(root, 'advance')
    assert budget.snapshot(root)['consumed_seconds'] == before
    now[0], ticks[0] = now[0] + 1, ticks[0] + 1
    assert budget.snapshot(root)['consumed_seconds'] == before + 1


def test_changed_boot_refuses_unverifiable_open_interval(clocked, monkeypatch):
    root, now = clocked
    transition(root, 'advance')
    original = budget.clock_stamp
    monkeypatch.setattr(budget, 'clock_stamp', lambda: dict(original(), boot_id='different-boot'))
    with pytest.raises(ValueError, match='boot changed'):
        budget.snapshot(root)
    with pytest.raises(ValueError, match='boot changed'):
        transition(root, 'paused')
    assert len(list((root / 'control-ledger').glob('*.json'))) == 1


def test_legacy_elapsed_instance_retains_its_original_deadline(clocked):
    root, now = clocked
    settings = contracts.settings(root)
    settings.pop('time_budget_basis')
    contracts.write(root / 'settings.json', settings)
    contracts.write(root / 'settings-identity.json', dict(sha256=contracts.digest(root / 'settings.json')))
    now[0] = 105.
    transition(root, 'paused')
    now[0] = 130.
    value = budget.snapshot(root)
    assert value['time_budget_basis'] == 'elapsed'
    assert value['consumed_seconds'] == 30
    assert value['seconds_remaining'] == 0
    assert value['unclassified_seconds'] == 5
    assert value['paused_seconds'] == 25
    assert controller.run(root)['status'] == 'wall_limit'


@pytest.mark.parametrize('action', ['snapshot', 'transition', 'amend'])
def test_legacy_elapsed_ledger_rejects_open_utc_rollback_without_refund(clocked, monkeypatch, action):
    root, now = clocked
    settings = contracts.settings(root)
    settings.pop('time_budget_basis')
    contracts.write(root / 'settings.json', settings)
    contracts.write(root / 'settings-identity.json', dict(sha256=contracts.digest(root / 'settings.json')))
    ticks = [100.]
    monkeypatch.setattr(budget.time, 'clock_gettime', lambda _: ticks[0])
    transition(root, 'advance')
    now[0] = ticks[0] = 120.
    assert budget.snapshot(root)['consumed_seconds'] == 20
    before = {path.name: path.read_bytes() for path in (root / 'control-ledger').glob('*.json')}
    now[0] = 110.
    with pytest.raises(ValueError, match='backwards'):
        if action == 'snapshot':
            budget.snapshot(root)
        elif action == 'transition':
            transition(root, 'paused')
        else:
            budget.amend(root, max_seconds=50, authorization_note='Explicit operator decision')
    assert {path.name: path.read_bytes() for path in (root / 'control-ledger').glob('*.json')} == before
    now[0] = ticks[0] = 130.
    assert budget.snapshot(root)['consumed_seconds'] == 30


def test_overlay_limits_reach_controller_and_actual_native_launch_boundary(clocked, monkeypatch):
    root, now = clocked
    settings = contracts.settings(root)
    monkeypatch.setattr(native, 'usage', lambda _: dict(input_tokens=120, cached_input_tokens=0,
        output_tokens=0, observed_tokens=120, unknown_steps=[]))
    assert controller._launch_limit(root, settings) == 'token_limit'
    budget.amend(root, max_tokens=200, max_seconds=5, authorization_note='Explicit operator decision')
    transition(root, 'advance')
    assert controller._launch_limit(root, settings) is None
    original_intent(root)
    now[0] = 106.
    monkeypatch.setattr(native.subprocess, 'Popen', lambda *a, **kw: pytest.fail('active ceiling must prevent submission'))
    native.run_native(root, 1)
    outcome = contracts.read(contracts.host_record(contracts.workspace(root, 1)) / 'native-outcome.json')
    assert outcome['native_started'] is False
    assert outcome['stop_reason'] == 'wall_limit'
    assert settings['max_seconds'] == 20
    assert settings['max_tokens'] == 100


def test_ledger_tamper_is_rejected_and_status_is_read_only(clocked):
    root, now = clocked
    transition(root, 'advance')
    now[0] = 104.
    transition(root, 'paused')
    before = {path: path.read_bytes() for path in root.rglob('*') if path.is_file()}
    assert status(root)['budget']['consumed_seconds'] == 4
    assert {path: path.read_bytes() for path in root.rglob('*') if path.is_file()} == before
    first = root / 'control-ledger/000001.json'
    event = contracts.read(first)
    contracts.write(first, dict(event, reason='Changed audit reason'))
    with pytest.raises(ValueError, match='identity'):
        budget.snapshot(root)
