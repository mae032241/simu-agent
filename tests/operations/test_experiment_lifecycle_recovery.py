"""Lost Workers retain the exact external execution and allow bounded recovery."""
import sqlite3
from types import SimpleNamespace

import pytest

from tests.operations.test_experiment_approval_handoff import experiment, start


@pytest.mark.parametrize("remote_state", ["succeeded", "failed", "cancelled"])
def test_final_delivery_refreshes_execution_without_waiting_for_background(tmp_path, monkeypatch, remote_state):
    from tests.operations.test_experiment_continuation import submit
    f = experiment(tmp_path, monkeypatch, seconds=60)
    assert start(f)["state"] == "running"
    f.adapter.state = remote_state
    monkeypatch.setattr(f.coordinator.bridge, "start", lambda **_: pytest.fail("delivery started a job"))
    monkeypatch.setattr(f.coordinator.collection, "collect", lambda *args, **kwargs: pytest.fail("delivery collected data"))
    # No status/advance call and no lifecycle tick between remote exit and submit.
    result = submit(f, [f.alias], outcome="inconclusive")
    assert result["state"] == "completed", result
    assert f.adapter.submits == 1


def test_final_delivery_blocks_active_or_unobservable_execution(tmp_path, monkeypatch):
    from tests.operations.test_experiment_continuation import submit
    f = experiment(tmp_path, monkeypatch, seconds=60)
    assert start(f)["state"] == "running"
    assert submit(f, [f.alias], outcome="inconclusive")["state"] == "rejected"
    def unavailable(_):
        raise TimeoutError("fixture observation unavailable")
    monkeypatch.setattr(f.adapter, "status", unavailable)
    assert submit(f, [f.alias], outcome="inconclusive")["state"] == "rejected"
    assert f.adapter.submits == 1


def expired_execution(tmp_path, monkeypatch):
    f = experiment(tmp_path, monkeypatch, seconds=60)
    start(f)
    f.binding = next(b for b in f.runtime.scheduler_bindings.list(
        instance=f.instance.instance_id, namespace="execution")
        if b.name.startswith("experiment-" + f.run_id + "-"))
    f.root.facade.execution_bridge = f.coordinator.bridge
    f.root.facade.execution_collection = SimpleNamespace(
        collect=f.coordinator.collection.collect, summary=lambda _: {})
    with sqlite3.connect(f.runs.database_path) as connection:
        connection.execute("UPDATE runs SET deadline_at=? WHERE run_id=?",
            ("2000-01-01T00:00:00.000000Z", f.run_id))
    return f


def test_expired_worker_preserves_execution_and_root_can_collect(tmp_path, monkeypatch):
    f = expired_execution(tmp_path, monkeypatch)
    monkeypatch.setattr(f.coordinator, "_cancel", lambda _: pytest.fail("Worker expiry cancelled solver"))
    f.runtime.executions.save_observation(f.binding.object_id, {"progress":{
        "log_tails":[{"source":"solver_log", "tail":"original execution log"}]}})
    with pytest.raises(Exception, match="managed within"):
        f.root.call_tool("execution_logs", {"name":f.binding.name}, surface="execution")
    f.runs.reconcile_expired_active()
    assert f.root.call_tool("execution_logs", {"name":f.binding.name}, surface="execution")["text"] == "original execution log"
    assert f.runs.status(f.run_id).state == "failed"
    assert f.runtime.executions.status(f.binding.object_id).state == "running"
    listed = f.root.call_tool("execution_list", {}, surface="execution")["executions"]
    assert [x["name"] for x in listed] == [f.binding.name]
    assert listed[0]["recovery"]["task_name"] == "continuation"
    events = f.root.call_tool("lifecycle_events", {})["events"]
    assert any(e["object_type"] == "execution" and e["name"] == f.binding.name for e in events)
    assert f.root.call_tool("execution_start", {"name": f.binding.name}, surface="execution")["state"] == "running"
    assert f.adapter.submits == 1  # Explicit takeover never restarts an existing solver.
    f.adapter.state = "succeeded"
    status = f.root.call_tool("execution_sync", {"name": f.binding.name}, surface="execution")
    assert status["state"] == "succeeded"
    f.root.call_tool("execution_collect", {"name": f.binding.name}, surface="execution")
    assert f.runtime.executions.status(f.binding.object_id).state == "collected"
    outputs = f.root.call_tool("execution_outputs", {"name": f.binding.name}, surface="execution")
    assert outputs["outputs"] and f.adapter.submits == 1
    assert f.runs.status(f.run_id).state == "failed"  # Solver success is not Worker completion.


def test_recovery_is_not_exposed_while_owner_or_resumed_worker_active(tmp_path, monkeypatch):
    f = experiment(tmp_path, monkeypatch, seconds=60)
    start(f)
    assert f.root.call_tool("execution_list", {}, surface="execution")["executions"] == []
    value = f.runs.status(f.run_id)
    f.runs.record_failure(f.run_id, reason="Worker exited", expected_state=value.state,
        expected_last_activity_at=value.last_activity_at)
    listed = f.root.call_tool("execution_list", {}, surface="execution")["executions"]
    assert len(listed) == 1
    result = f.root.call_tool("operation_invoke", {**f.invocation, "name": "resumed",
        "resume_from": "continuation"})
    assert result["result"]["state"] == "queued", result
    assert f.root.call_tool("execution_list", {}, surface="execution")["executions"] == []
    f.root.facade.execution_bridge = f.coordinator.bridge
    for action in ("execution_collect", "execution_start", "execution_abandon", "execution_cancel"):
        with pytest.raises(Exception, match="managed within"):
            f.root.call_tool(action, {"name": listed[0]["name"]}, surface="execution")


def test_control_refreshes_after_worker_expiry_without_resubmitting(tmp_path, monkeypatch):
    from scidiscovery.agent_execution_settings import LifecycleSettings
    from scidiscovery.artifact_agent.service.lifecycle import LifecycleReconciler
    from scidiscovery.artifact_agent.interfaces.mcp_worker_protocol import WorkerToolError
    f = expired_execution(tmp_path, monkeypatch)
    observer = LifecycleReconciler(runs=f.runs, bridge=f.coordinator.bridge,
        settings=LifecycleSettings(batch_size=1))
    def unavailable(_):
        raise TimeoutError("fixture observation unavailable")
    monkeypatch.setattr(f.adapter, "status_details", unavailable, raising=False)
    # The fixture also has a terminal execution whose accounting is pending.
    # A one-item page must rotate past that execution to observe this one.
    for _ in range(3):
        observer.tick()
    assert f.runs.status(f.run_id).state == "failed"
    assert f.runtime.executions.status(f.binding.object_id).state == "running"
    assert f.runtime.executions.observation(f.binding.object_id)["observation_error"]
    with pytest.raises(WorkerToolError):
        f.worker.call_tool("worker_experiment_execute", {"action": "advance"})
    monkeypatch.setattr(f.adapter, "status_details", lambda _: {"state": "succeeded",
        "progress": {"elapsed_seconds": 12}}, raising=False)
    # Keyset pages wrap; old executions cannot starve a later one.
    for _ in range(3):
        observer.tick()
    assert f.runtime.executions.status(f.binding.object_id).state == "succeeded"
    assert f.runtime.executions.observation(f.binding.object_id)["progress"]["elapsed_seconds"] == 12
    assert f.adapter.submits == 1


def test_maintenance_defers_timeout_and_observation_until_available(tmp_path, monkeypatch):
    from scidiscovery.agent_execution_settings import LifecycleSettings
    from scidiscovery.artifact_agent.service.lifecycle import LifecycleReconciler
    f = expired_execution(tmp_path, monkeypatch)
    observer = LifecycleReconciler(runs=f.runs, bridge=f.coordinator.bridge, settings=LifecycleSettings())
    gate, instance_id = f.runs.instance_maintenance, f.instance.instance_id
    with gate.exclusive(instance_id):
        gate.begin(instance_id, "fixture-archive", "archive")
    f.adapter.state = "succeeded"
    assert f.runs.reconcile_expired_active() == 0  # Startup also respects maintenance.
    observer.tick()
    assert f.runs.status(f.run_id).state == "running"
    assert f.runtime.executions.status(f.binding.object_id).state == "running"
    with gate.exclusive(instance_id):
        gate.finish(instance_id, "fixture-archive")
    observer.tick()
    assert f.runs.status(f.run_id).state == "failed"
    assert f.runtime.executions.status(f.binding.object_id).state == "succeeded"
    assert f.adapter.submits == 1


def test_status_only_polling_sees_solver_finish_before_worker_deadline(tmp_path, monkeypatch):
    """Incident: remote ends, Worker keeps polling status, Run deadline is still live."""
    f = experiment(tmp_path, monkeypatch, seconds=60)
    assert start(f)["state"] == "running"
    f.adapter.state = "succeeded"
    status = f.worker.call_tool("worker_experiment_execute", {"action": "status"})
    assert status["state"] == "succeeded"
    assert status["observation"]["state"] == "recorded"
    assert f.runs.status(f.run_id).state == "running"
    assert f.adapter.submits == 1
