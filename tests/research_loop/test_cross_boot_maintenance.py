"""Finite original-call IO and paused clock math; no real reboot/solver claim."""
import json
from pathlib import Path

import pytest

from scidiscovery.research_loop import (budget, contracts as c, controller,
    execution_authority as authority, execution_resume, experiments as e,
    instance_owner, qualification as q)
from execution_fixtures import execution_registry
from test_execution_resources import resource_registry, prepare
from test_native_execution_inputs import chain, _reviewed_execution


def _clock(monkeypatch):
    now = dict(at_unix=100., at_boottime=100., boot_id='old-boot')
    monkeypatch.setattr(budget, 'clock_stamp', lambda: dict(now))
    return now


def _owner_receipts(root, monkeypatch, name):
    """Budget-only trusted DI; actual external-owner fencing is tested separately."""
    directory = root / 'host-runtime/restore' / name
    checkpoint = q._save(root, directory / 'checkpoint.json', dict(instance_id=c.settings(root)['goal_id'],
        settings_ref=q._ref(root, root / 'settings.json'), budget=budget.paused_checkpoint(root)))
    transfer = q._save(root, directory / 'transfer.json', dict(checkpoint=checkpoint))
    def read(actual, original, moved):
        assert actual == root
        assert q._read(root, moved)['checkpoint'] == original
        return dict(checkpoint=q._read(root, original), transfer=q._read(root, moved))
    monkeypatch.setattr(instance_owner, 'read_transition', read)
    monkeypatch.setattr(instance_owner, 'verify_transition', read)
    return checkpoint, transfer


def test_paused_clock_bridge_preserves_consumption_grants_and_old_history(tmp_path, monkeypatch, resource_registry):
    root = prepare(tmp_path); now = _clock(monkeypatch)
    c.write(root / 'host-started.json', budget.clock_stamp()); started = (root / 'host-started.json').read_bytes()
    budget.transition(root, 'advance', 'First original segment')
    now.update(at_unix=102., at_boottime=102.)
    grant = budget.execution_grant(root)
    request = q._save(root, root / 'host-runtime/fixture-request.json', dict(kind='ledger math only'))
    decision = q._save(root, root / 'host-runtime/fixture-decision.json', dict(kind='not an execution permission'))
    reservation = budget.reserve_execution(root, binding=dict(call_id='fixture', scope={}, native_attempt={},
        interface={}, authority={}), request_ref=request, decision_ref=decision,
        budget=dict(wall_time_seconds=2, max_storage_bytes=20), grant_revision=grant['ref'],
        effective_allowance=grant['allowance'])
    budget.transition(root, 'waiting', 'Original async waiting')
    now.update(at_unix=105., at_boottime=105.)
    budget.transition(root, 'paused', 'Verified inactive owner')
    resources = budget.execution_accounting(root); revision = budget.authorization_revision(root)
    originals = {path.name: path.read_bytes() for path in (root / 'control-ledger').glob('*.json')}
    checkpoint, transfer = _owner_receipts(root, monkeypatch, 'one')
    now.update(at_unix=1000., at_boottime=10., boot_id='next-boot')
    with pytest.raises(ValueError, match='boot changed'):
        budget.snapshot(root)
    assert budget.reanchor_paused_checkpoint(root, checkpoint, transfer)['status'] == 'clock_reanchored'
    value = budget.snapshot(root)
    assert (value['advance_seconds'], value['waiting_seconds'], value['consumed_seconds'], value['seconds_remaining']) == (2., 3., 5., 995.)
    assert value['elapsed_seconds'] is None and value['unmeasured_paused_gap'] is True
    assert budget.execution_accounting(root) == resources
    assert budget.execution_reservation(root, reservation)['budget'] == dict(wall_time_seconds=2, max_storage_bytes=20)
    assert budget.authorization_revision(root) == revision
    count = value['ledger_events']
    assert budget.reanchor_paused_checkpoint(root, checkpoint, transfer)['status'] == 'clock_already_reanchored'
    assert budget.snapshot(root)['ledger_events'] == count
    budget.transition(root, 'advance', 'Second original segment')
    now.update(at_unix=1004., at_boottime=14.)
    budget.transition(root, 'paused', 'Second verified pause')
    assert budget.snapshot(root)['consumed_seconds'] == 9.
    second, moved = _owner_receipts(root, monkeypatch, 'two')
    now.update(at_unix=2000., at_boottime=2., boot_id='third-boot')
    assert budget.reanchor_paused_checkpoint(root, second, moved)['status'] == 'clock_reanchored'
    assert budget.snapshot(root)['consumed_seconds'] == 9.
    with pytest.raises(ValueError, match='reused on another boot'):
        budget.reanchor_paused_checkpoint(root, checkpoint, transfer)
    assert (root / 'host-started.json').read_bytes() == started
    assert all((root / 'control-ledger' / name).read_bytes() == raw for name, raw in originals.items())


def test_clock_bridge_rejects_unpaused_stale_or_elapsed_checkpoints(tmp_path, monkeypatch, resource_registry):
    root = prepare(tmp_path); now = _clock(monkeypatch)
    c.write(root / 'host-started.json', budget.clock_stamp())
    budget.transition(root, 'advance', 'Scientific work still active')
    with pytest.raises(ValueError, match='already paused'):
        budget.paused_checkpoint(root)
    budget.transition(root, 'waiting', 'Unmeasured external execution')
    with pytest.raises(ValueError, match='already paused'):
        budget.paused_checkpoint(root)
    budget.transition(root, 'paused', 'Verified pause')
    checkpoint, transfer = _owner_receipts(root, monkeypatch, 'stale')
    budget.execution_grant(root)  # Any new original ledger event makes the cold checkpoint stale.
    now.update(at_unix=1000., at_boottime=1., boot_id='new-boot')
    with pytest.raises(ValueError, match='current original budget'):
        budget.reanchor_paused_checkpoint(root, checkpoint, transfer)
    settings = c.settings(root)
    with pytest.raises(ValueError, match='active budget'):
        budget._paused_checkpoint(root, dict(settings, time_budget_basis='elapsed'), [])


def test_cross_boot_original_maintenance_collects_without_scientific_dispatch(chain, capsys, monkeypatch):
    root, backend, output, active, config, _ = _reviewed_execution(chain, capsys)
    assert e.main(['--config', str(active), 'run', '--payload', str(output)]) == 2
    call = json.loads(capsys.readouterr().out)['call_id']; records = e.Records(config)
    accepted = (records.directory(call) / 'accepted.json').read_bytes()
    original_ledger = {path.name: path.read_bytes() for path in (root / 'control-ledger').glob('*.json')}
    old_seals = {c.host_record(c.workspace(root, step)) / 'result-identity.json':
        (c.host_record(c.workspace(root, step)) / 'result-identity.json').read_bytes() for step in range(1, 6)}
    stamp = budget.clock_stamp(); stamp.update(boot_id='maintenance-new-boot', at_boottime=10.)
    monkeypatch.setattr(budget, 'clock_stamp', lambda: dict(stamp))
    def no_science(*args, **kwargs):
        pytest.fail('Original maintenance must not seek scientific advancement authorization')
    monkeypatch.setattr(budget, 'snapshot', no_science)
    monkeypatch.setattr(authority, '_remaining', no_science)
    args = dict(max_seconds=30., authorization_note='Maintain the exact original job after reboot')
    result = controller.execution_resume(root, 6, call, maintenance='query', **args)
    assert result['state'] == 'queued' and result['call_id'] == call
    assert result['external_run_id'] == records.external(call)
    cancellations = []
    def cancel(external):
        cancellations.append(external); backend.state = 'cancelling'; return 'cancelling'
    monkeypatch.setattr(backend, 'cancel', cancel, raising=False)
    assert controller.execution_resume(root, 6, call, maintenance='cancel', **args)['status'] == 'cancelling'
    assert cancellations == [records.external(call)]
    backend.state = 'succeeded'
    result = controller.execution_resume(root, 6, call, maintenance='collect', **args)
    assert result['status'] == 'known_success'
    observed = json.loads(e.read(records.directory(call) / 'execution-observation.json'))
    e.verify_observation(observed, lambda item: Path(item['path']), interface=config['execution_interface'])
    assert observed['external_run_id'] == records.external(call) and observed['outputs']
    assert backend.submits == 1 and len(backend.prepared) == 1
    assert (records.directory(call) / 'accepted.json').read_bytes() == accepted
    assert {path.name: path.read_bytes() for path in (root / 'control-ledger').glob('*.json')} == original_ledger
    assert all(path.read_bytes() == raw for path, raw in old_seals.items())
    missing = '9999-' + 'f' * 32
    assert controller.execution_resume(root, 6, missing, maintenance='query', **args)['status'] == 'unknown'
    assert not (records.root / 'calls' / missing).exists()
    window = execution_resume._MaintenanceWindow(root, config, call, 'query', **dict(max_seconds=1., note='Finite boundary check'))
    services = window.services()
    with pytest.raises(e.UnsupportedExecution, match='no new execution identity'):
        services.call_identity(None, 1)
    with pytest.raises(e.UnsupportedExecution, match='cannot prepare'):
        services.gate(None)('prepare', call_id=call, prior_receipt=window.authority)
    stamp['at_boottime'] += 2.
    with pytest.raises(ValueError, match='expired'):
        window.check()
    assert backend.submits == 1
