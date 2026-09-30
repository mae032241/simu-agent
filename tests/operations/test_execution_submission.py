"""Slow/lost submissions keep one identity and remain queryable."""
import json
import threading
import time

import pytest

from scidiscovery.artifact_agent.execution_bridge import ExecutionBridge
from scidiscovery.artifact_agent.service.engineering_diagnostics import atomic_json
from scidiscovery.artifact_agent.service.executions import ExecutionServiceError
from tests.operations.test_r4_execution_approval_identity import _setup, _create_effect, _decide_execution_approval


def _ready(tmp_path):
    runtime, instance, adapter, facade, root, catalog = _setup(tmp_path)
    _create_effect(root, name="slow")
    _decide_execution_approval(runtime, root, name="slow")
    execution_id = facade._resolve("execution", "slow")
    return runtime, adapter, facade, root, execution_id


def _wait(predicate):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.01)
    pytest.fail("submission did not settle")


def test_slow_prepare_returns_pending_and_duplicate_start_cannot_submit_twice(tmp_path, monkeypatch):
    runtime, adapter, facade, root, execution_id = _ready(tmp_path)
    entered, release = threading.Event(), threading.Event()
    original = adapter.prepare
    def slow(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)
    monkeypatch.setattr(adapter, "prepare", slow)
    try:
        value = root.call_tool("execution_start", {"name": "slow"}, surface="execution")
        assert entered.is_set() and not release.is_set()
        assert value["submission"]["state"] == "pending"
        again = root.call_tool("execution_start", {"name": "slow"}, surface="execution")
        assert again["submission"]["state"] == "pending"
        status = root.call_tool("execution_status", {"name": "slow"}, surface="execution")
        assert status["submission"]["state"] == "pending"
        with pytest.raises(ExecutionServiceError, match="pending|progress"):
            root.call_tool("execution_abandon", {"name": "slow"}, surface="execution")
        assert adapter.submit_count == 0
        # Another bridge/process cannot acquire this persisted submission lock.
        other = ExecutionBridge(runtime.executions, adapters=facade.execution_bridge.adapters)
        assert other.submissions.summary(execution_id)["state"] == "pending"
        from scidiscovery.artifact_agent.service.maintenance import MaintenanceBusy
        with pytest.raises(MaintenanceBusy):
            with runtime.instance_maintenance.maintenance.exclusive(blocking=False):
                pytest.fail("background submission lost its maintenance lease")
    finally:
        release.set()
        _wait(lambda: facade.execution_bridge.submissions.summary(execution_id).get("state") == "submitted")
    assert adapter.submit_count == 1


def test_lost_response_status_recovers_without_resubmit(tmp_path):
    runtime, adapter, facade, root, execution_id = _ready(tmp_path)
    adapter.lose_response_once = True
    assert root.call_tool("execution_start", {"name": "slow"}, surface="execution")["submission"]["state"] == "unknown"
    assert facade.execution_bridge.submissions.summary(execution_id)["state"] == "unknown"
    # A fresh bridge has no in-memory future: durable identity is sufficient.
    facade.execution_bridge = ExecutionBridge(runtime.executions, adapters=facade.execution_bridge.adapters)
    root.call_tool("execution_status", {"name": "slow"}, surface="execution")
    _wait(lambda: facade.execution_bridge.submissions.summary(execution_id)["state"] == "submitted")
    assert adapter.submit_count == 1


def test_unknown_absent_lookup_never_resubmits_or_refunds(tmp_path, monkeypatch):
    runtime, adapter, facade, root, execution_id = _ready(tmp_path)
    def unavailable(*_args, **_kwargs):
        raise TimeoutError("remote acceptance unknown")
    monkeypatch.setattr(adapter, "submit", unavailable)
    assert root.call_tool("execution_start", {"name": "slow"}, surface="execution")["submission"]["state"] == "unknown"
    record = runtime.executions.prepared_submission(execution_id)
    assert record is not None
    # Explicit duplicate start is also restricted to lookup after uncertainty.
    value = root.call_tool("execution_start", {"name": "slow"}, surface="execution")
    assert value["submission"]["state"] == "unknown"
    assert value["submission"]["reason"] == "exact_submission_not_yet_visible"
    assert runtime.executions.prepared_submission(execution_id) == record
    with pytest.raises(ExecutionServiceError):
        root.call_tool("execution_abandon", {"name": "slow"}, surface="execution")


def test_interrupted_owner_is_not_reported_as_still_running(tmp_path):
    runtime, adapter, facade, root, execution_id = _ready(tmp_path)
    directory = runtime.executions.exchange_root / execution_id
    atomic_json(directory / "submission.json", {"state": "pending"})
    assert facade.execution_bridge.submissions.summary(execution_id)["state"] == "unknown"
    root.call_tool("execution_status", {"name": "slow"}, surface="execution")
    _wait(lambda: facade.execution_bridge.submissions.summary(execution_id)["state"] == "interrupted")
    assert adapter.submit_count == 0


def test_worker_slow_policy_hands_approval_to_status(tmp_path, monkeypatch):
    from tests.operations.test_experiment_approval_handoff import experiment, start
    f = experiment(tmp_path, monkeypatch)
    release = threading.Event()
    original = f.adapter.execution_admission
    def slow(*args, **kwargs):
        assert release.wait(5)
        return original(*args, **kwargs)
    monkeypatch.setattr(f.adapter, "execution_admission", slow)
    try:
        assert start(f)["submission"]["state"] == "pending"
    finally:
        release.set()
    result = {}
    def approved():
        result.update(f.worker.call_tool("worker_experiment_execute", {"action": "status"}))
        return result.get("state") == "awaiting_authorization"
    _wait(approved)
    assert result["review_url"] and result["approval_name"]
    assert f.root.call_tool("approval_status", {"name": result["approval_name"]})["status"] == "pending"
    assert f.adapter.submits == 0


def test_late_preparation_failure_is_readable_not_stuck_pending(tmp_path, monkeypatch):
    runtime, adapter, facade, root, execution_id = _ready(tmp_path)
    release = threading.Event()
    def failure(*_args, **_kwargs):
        assert release.wait(5)
        raise RuntimeError("bounded preparation failure")
    monkeypatch.setattr(adapter, "prepare", failure)
    try:
        assert root.call_tool("execution_start", {"name": "slow"}, surface="execution")["submission"]["state"] == "pending"
    finally:
        release.set()
        _wait(lambda: facade.execution_bridge.submissions.summary(execution_id).get("state") == "failed")
    value = root.call_tool("execution_status", {"name": "slow"}, surface="execution")
    assert value["submission"]["error"]["reference"].startswith("diag_")
    assert set(value["submission"]["error"]) == {"reference", "available_sections"}
    assert "bounded preparation failure" not in json.dumps(value)
    assert adapter.submit_count == 0


@pytest.mark.process_e2e
@pytest.mark.parametrize("restart", [False, True])
def test_real_proxy_returns_before_slow_submission_then_status_recovers(tmp_path, monkeypatch, restart):
    import multiprocessing
    import os
    import subprocess
    import sys
    from types import SimpleNamespace
    from scidiscovery.plugin_runtime.transport import MCPRouter, UnixSocketDaemon

    runtime, adapter, facade, root, execution_id = _ready(tmp_path)
    # Exercise a real stdio proxy and socket daemon with a shorter equivalent
    # response deadline; the external submit remains blocked until after reply.
    facade.runs.agent_settings = facade.runs.agent_settings.model_copy(update={
        "execution_io": facade.runs.agent_settings.execution_io.model_copy(update={
            "submission_response_wait_seconds": .01})})
    release = tmp_path / "release"
    submitted = tmp_path / "submitted"
    original = adapter.submit
    def slow(descriptor):
        with submitted.open("a") as stream:
            stream.write("one submission\n")
        _wait(release.exists)
        return original(descriptor)
    monkeypatch.setattr(adapter, "submit", slow)
    monkeypatch.setattr(adapter, "lookup_submission", lambda _:
        ("unexpected-run", "accepted") if submitted.exists() else None)
    socket_path = tmp_path / "control.sock"
    router = MCPRouter(SimpleNamespace(call_tool=lambda name, arguments:
        root.call_tool(name, arguments, surface="execution")), name="submission-test")
    daemon = multiprocessing.get_context("fork").Process(
        target=UnixSocketDaemon(socket_path, router).serve_forever)
    daemon.start()
    def call(name):
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": name, "arguments": {"name": "slow"},
                "_meta": {"x-codex-turn-metadata": {
                    "session_id": "submission-test-root", "thread_id": "submission-test-root"}}}}
        result = subprocess.run([sys.executable, "-m", "scidiscovery.artifact_agent.interfaces.mcp_proxy",
            "--socket", str(socket_path), "--timeout", "0.3"], input=json.dumps(request) + "\n",
            text=True, capture_output=True, timeout=5,
            env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)})
        assert result.returncode == 0, result.stderr
        response = json.loads(result.stdout)
        assert "error" not in response, response
        return response["result"]["structuredContent"]
    try:
        _wait(socket_path.exists)
        assert call("execution_start")["submission"]["state"] == "pending"
        assert not release.exists()
        assert call("execution_start")["submission"]["state"] == "pending"
        if restart:
            _wait(submitted.exists)
            daemon.terminate()
            daemon.join(5)
            daemon = multiprocessing.get_context("fork").Process(
                target=UnixSocketDaemon(socket_path, router).serve_forever)
            daemon.start()
            # The old socket path may survive termination; wait for a live
            # replacement before invoking status through the real proxy.
            import socket
            def connected():
                try:
                    with socket.socket(socket.AF_UNIX) as client:
                        client.connect(str(socket_path))
                    return True
                except OSError:
                    return False
            _wait(connected)
            call("execution_status")
        release.touch()
        _wait(lambda: runtime.executions.status(execution_id).external_run_id is not None)
        assert call("execution_status")["state"] == "submitted"
        assert submitted.read_text() == "one submission\n"
    finally:
        release.touch()
        daemon.terminate()
        daemon.join(5)
        if daemon.is_alive():
            daemon.kill()
            daemon.join(5)
