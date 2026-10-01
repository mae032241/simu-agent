"""Mixed-version admission and explicit administrator recovery, no live solver."""
import fcntl
import json
from types import SimpleNamespace

import pytest

from tests.operations.test_approval_wait_recovery import execution
from tests.operations.test_experiment_approval_handoff import experiment, start


def test_old_runner_is_rejected_before_reservation_or_prepare(tmp_path, monkeypatch):
    from tcad_artifact.command_adapter import CommandTCADExecutorAdapter
    from tcad_artifact.ssh_transport import SSHTCADTransport
    f = experiment(tmp_path, monkeypatch, seconds=60)
    calls = []
    def old_rpc(request):
        calls.append(request['params']['name'])
        return {'jsonrpc': '2.0', 'id': request['id'], 'error': {'code': -32601, 'message': 'unsupported runner RPC method'}}
    transport = SSHTCADTransport(remote=SimpleNamespace(rpc=old_rpc), local_result_root=tmp_path / 'results')
    adapter = object.__new__(CommandTCADExecutorAdapter)
    monkeypatch.setattr(adapter, '_call', transport.handle)
    monkeypatch.setattr(f.adapter, 'validate_submission_protocol', adapter.validate_submission_protocol, raising=False)
    from scidiscovery.operation_contract import DiagnosticError
    with pytest.raises(DiagnosticError) as caught:
        start(f)
    assert 'protocol' in str(caught.value.__cause__)
    eid = execution(f).object_id
    assert calls == ['tcad_submission_protocol']
    assert f.adapter.submits == 0
    assert f.runtime.executions.prepared_submission(eid) is None
    assert f.runtime.executions.budget_accounting(eid) == {}
    assert f.coordinator.bridge.submissions.summary(eid)['state'] == 'failed'


def test_admin_confirmation_keeps_budget_until_remote_retirement(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.interfaces.submission_recovery import authorize_legacy_retirement
    from scidiscovery.artifact_agent.service.engineering_diagnostics import atomic_json
    from scidiscovery.artifact_agent.service.execution_submission import ExecutionSubmission
    f = experiment(tmp_path, monkeypatch, seconds=60)
    def unavailable(*args, **kwargs):
        raise TimeoutError('response lost')
    monkeypatch.setattr(f.adapter, 'submit', unavailable)
    assert start(f)['submission']['state'] == 'unknown'
    eid = execution(f).object_id
    path = f.runtime.executions.exchange_root / eid / 'submission.json'
    record = json.loads(path.read_bytes())
    record.pop('retirement_supported')
    atomic_json(path, record)
    state = f.runtime.executions.database_path.parent.parent
    before = f.runtime.executions.budget_accounting(eid)
    def authorize(confirmed=True):
        return authorize_legacy_retirement(state, eid, confirm_old_submitters_stopped=confirmed,
            reason='Operator stopped all old submitters and upgraded remote runner')
    with pytest.raises(ValueError, match='Confirm'):
        authorize(False)
    lock = ExecutionSubmission._lock(path.parent / 'submission.lock')
    try:
        with pytest.raises(RuntimeError, match='local submitter'):
            authorize()
    finally:
        __import__('os').close(lock)
    assert authorize()['budget_released'] is False
    assert f.runtime.executions.budget_accounting(eid) == before
    assert authorize()['state'] == 'retirement_already_enabled'
    from tests.operations.test_execution_submission import _wait
    audit = json.loads(path.read_bytes())['administrator_recovery']
    # A normal Worker status query launches asynchronous exact-submission lookup.
    f.worker.call_tool('worker_experiment_execute', {'action': 'status'})
    _wait(lambda: f.coordinator.bridge.submissions.summary(eid)['state'] != 'pending')
    assert json.loads(path.read_bytes())['administrator_recovery'] == audit
    assert 'administrator_recovery' not in f.coordinator.bridge.submissions.summary(eid)
    monkeypatch.setattr(f.adapter, 'retire_submission', unavailable, raising=False)
    with pytest.raises(TimeoutError):
        f.coordinator.bridge.abandon(eid)
    assert f.runtime.executions.budget_accounting(eid) == before
    monkeypatch.setattr(f.adapter, 'retire_submission', lambda _: None)
    f.coordinator.bridge.abandon(eid)
    assert f.runtime.executions.status(eid).state == 'abandoned'
    assert not f.runtime.executions.budget_needs_settlement(eid)


def test_busy_remote_retirement_returns_actionable_error(tmp_path):
    from tcad_artifact import remote_runner_py36 as runner
    config = {'state_root': str(tmp_path), 'result_root': str(tmp_path / 'runs')}
    with (tmp_path / 'submission.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        with pytest.raises(RuntimeError, match='retry abandon/cancel later'):
            runner._retire_submission(config, 'a'*64)
    assert not (tmp_path / 'retired_submissions').exists()


def test_deployment_rejects_old_runner_even_with_capabilities_and_policy(tmp_path):
    from tests.artifact_agent.test_remote_tcad_deployment import setup, SOURCE
    module, request, runner, config = setup(tmp_path)
    source = SOURCE.read_text().replace('if name == "tcad_submission_protocol":', 'if name == "unsupported_protocol":')
    runner.write_text(source)
    with pytest.raises(RuntimeError, match='protocol discovery'):
        module.probe(runner, config)
    runner.write_bytes(SOURCE.read_bytes())
    assert module.probe(runner, config)['policy_available'] is True
