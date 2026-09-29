"""Progress survives the complete-task Worker path and reaches UI observations."""
import json

import pytest

from tests.operations.test_experiment_approval_handoff import experiment, start


def test_worker_status_refreshes_and_reports_failure_without_submitting(tmp_path, monkeypatch):
    f = experiment(tmp_path, monkeypatch, seconds=60)
    progress = {"elapsed_seconds": 120, "observed_at": "2026-09-27T10:02:00Z",
        "log_tails": [{"source": "solver_log", "size_bytes": 256,
            "updated_at": "2026-09-27T10:01:55Z",
            "tail": "credential = hidden\nNewton iteration 3\n"}]}
    monkeypatch.setattr(f.adapter, "status_details", lambda _: {"state": "running", "progress": progress}, raising=False)
    result = start(f)
    assert result["progress"]["elapsed_seconds"] == 120
    assert result["progress"]["log_activity"][0]["size_bytes"] == 256
    assert "Newton" not in json.dumps(result)
    assert "log_tails" not in result["progress"] and "hidden" not in json.dumps(result)
    assert result["observation"]["state"] == "recorded"
    def unavailable(_):
        raise TimeoutError("fixture observation timeout")
    monkeypatch.setattr(f.adapter, "status_details", unavailable)
    failed = f.worker.call_tool("worker_experiment_execute", {"action": "advance"})
    assert failed["state"] == "running" and failed["progress"] == result["progress"]
    assert failed["observation"]["state"] == "refresh_failed"
    assert failed["observation"]["observed_at"] == result["observation"]["observed_at"]
    calls = []
    def current(_):
        calls.append(True)
        raise TimeoutError("fixture observation timeout")
    monkeypatch.setattr(f.adapter, "status_details", current)
    before = f.runs.tool_evidence(f.run_id)
    assert f.worker.call_tool("worker_experiment_execute", {"action": "status"}) == failed
    assert calls == [True]
    assert f.runs.tool_evidence(f.run_id) == before
    assert f.adapter.submits == 1


def test_worker_poll_updates_ui_even_when_execution_stays_running(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.approval_ui.read_model import InstanceReadModel
    from scidiscovery.artifact_agent.approval_ui.trajectory import TrajectoryStore, TrajectoryObserver
    from scidiscovery.artifact_agent.approval_ui.workbench_render import _node_card
    f = experiment(tmp_path, monkeypatch, seconds=60)
    progress = {"elapsed_seconds": 1, "log_tails": [{"source": "solver_log", "tail": "step 1",
        "size_bytes": 10, "updated_at": "2026-09-27T10:00:01Z"}]}
    monkeypatch.setattr(f.adapter, "status_details", lambda _: {"state": "running", "progress": progress}, raising=False)
    start(f)
    model = InstanceReadModel(artifacts=f.runtime.artifacts, bindings=f.runtime.scheduler_bindings,
        runs=f.runs, approvals=f.runtime.approvals, executions=f.runtime.executions, operation_catalog=f.catalog)
    store = TrajectoryStore(tmp_path / "ui.sqlite3")
    observer = TrajectoryObserver(model, store)
    instance = f.instance.instance_id
    assert observer.refresh(instance)
    cursor = store.events(instance)["cursor"]
    binding = next(b for b in f.runtime.scheduler_bindings.list(instance=instance, namespace="execution")
        if b.name.startswith("experiment-" + f.run_id))
    key = "execution:" + binding.name
    progress.update(elapsed_seconds=30)
    progress["log_tails"][0].update(tail="step 2", size_bytes=30, updated_at="2026-09-27T10:00:30Z")
    f.worker.call_tool("worker_experiment_execute", {"action": "advance"})
    monkeypatch.setattr(f.adapter, "status_details", lambda _: pytest.fail("UI queried remote"))
    assert observer.refresh(instance)
    events = store.events(instance, after=cursor)["events"]
    assert any(e["node_key"] == key and e["state"] == "running" for e in events)
    card = _node_card(model.node_metadata(instance, key), instance)
    assert "30" in card and "step 2" in card and "最近观测" in card
    assert "<progress aria-label=" in card and "完成比例未知" in card
    cursor = store.events(instance)["cursor"]
    assert observer.refresh(instance)
    assert store.events(instance, after=cursor)["events"] == []


def test_progress_projection_keeps_bounds_and_does_not_invent_measurements():
    from scidiscovery.plugin_runtime.experiment import progress_summary
    assert progress_summary(None) == {}
    assert progress_summary({"elapsed_seconds": float('nan')}) == {}
    original = {"private_binding": "unrelated", "log_tails": [
        {"source": "solver_log", "tail": "token=hidden /private/solver/run.log exe_abc123 " + "x" * 5000}
        for _ in range(20)]}
    result = progress_summary(original)
    assert "elapsed_seconds" not in result and "private_binding" not in result
    assert result["log_count"] == 20 and len(result["log_activity"]) == 2
    assert all("last_line" not in x for x in result["log_activity"])
    preview = progress_summary(original, include_log_text=True)
    assert all(x["last_line_truncated"] for x in preview["log_activity"])
    assert all(x not in json.dumps(preview) for x in ("hidden", "/private", "exe_abc123"))
    raw = json.dumps(result)
    assert len(raw) < 1500
    assert all(x not in raw for x in ("hidden", "/private", "exe_abc123"))


def test_worker_status_does_not_deliver_log_text_as_remote_logs_grow(tmp_path, monkeypatch):
    f = experiment(tmp_path, monkeypatch, seconds=60)
    monkeypatch.setattr(f.adapter, "status_details", lambda _: {"state":"running"}, raising=False)
    start(f)
    marker = "solver-log-must-not-enter-context"
    sizes = []
    # Adapter observations are bounded tails, not entire growing log files.
    for length in (100, 3000):
        progress = {"elapsed_seconds": 30, "log_tails": [
            {"source": "solver_log", "updated_at": "2026-09-27T10:00:30Z",
             "size_bytes": length, "tail": marker + "日" * length} for _ in range(8)]}
        monkeypatch.setattr(f.adapter, "status_details", lambda _: {"state": "running", "progress": progress}, raising=False)
        value = f.worker.call_tool("worker_experiment_execute", {"action": "status"})
        raw = json.dumps(value, ensure_ascii=False).encode()
        assert marker.encode() not in raw and "日".encode() not in raw
        assert "progress" in value, value
        assert value["progress"]["elapsed_seconds"] == 30
        assert value["progress"]["log_count"] == 8
        assert value["progress"]["log_details_omitted"] is True
        sizes.append(len(raw))
    assert max(sizes) < 1200 and abs(sizes[1] - sizes[0]) < 40
    assert f.adapter.submits == 1
