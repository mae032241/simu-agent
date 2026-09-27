"""Bounded server observations survive transport, author and scheduler handoffs."""
import json
import os

import pytest

from tcad_artifact import remote_runner_py36 as server
from tcad_artifact.execution_adapter import TCADExecutorAdapter


def server_job(tmp_path, monkeypatch):
    run_id = "run_" + "a" * 32
    directory = tmp_path / run_id
    (directory / "work").mkdir(parents=True)
    for name, value in {"started_at": "2026-09-13T00:00:00Z", "submitted_at": "2026-09-13T00:00:00Z",
                        "pid": str(os.getpid()), "running": ""}.items():
        (directory / name).write_text(value)
    (directory / "worker.log").write_text("startup\n" * 1000 + "mesh initialization started\n")
    (directory / "work/main.log").write_text("PATH=/private/runtime/bin\ncredential = do-not-expose\nNewton iteration 3\n")
    monkeypatch.setattr(server, "_timestamp", lambda: "2026-09-13T00:00:12.000000Z")
    return run_id, directory, {"result_root": str(tmp_path)}


def finish_job(directory):
    manifest = {"terminal_state": "failed", "exit_code": 1, "error": "fixture solver failure", "outputs": [],
                "started_at": "2026-09-13T00:00:00Z", "completed_at": "2026-09-13T00:00:12Z"}
    (directory / "output_manifest.json").write_text(json.dumps(manifest))
    (directory / "diagnostic.log").write_text("Error: fixture convergence failure\nLast solver step: Newton 3\n")
    (directory / "done").touch()


def test_local_adapter_and_root_sync_expose_optional_progress_without_changing_status_query(tmp_path, monkeypatch):
    from tcad_artifact.execution_control import TCADExecutionFacade
    from tests.operations.test_r4_execution_approval_identity import _setup, _create_effect, _decide_execution_approval
    run_id, directory, config = server_job(tmp_path / "server", monkeypatch)
    control = object.__new__(TCADExecutionFacade)
    control.runs_root = directory.parent
    monkeypatch.setattr(control, "_tcad_status_value", lambda **kw: {"state": "running"})
    adapter = object.__new__(TCADExecutorAdapter)
    monkeypatch.setattr(adapter, "_call", lambda operation, payload: control.tcad_status(**payload))
    assert adapter.status(run_id) == "running"  # legacy interface remains a string
    runtime, _, effect, _, root, _ = _setup(tmp_path)
    _create_effect(root, name="progress")
    _decide_execution_approval(runtime, root, name="progress")
    root.call_tool("execution_start", {"name": "progress"}, surface="execution")
    monkeypatch.setattr(effect, "status_details", lambda _: adapter.status_details(run_id), raising=False)
    observed = root.call_tool("execution_sync", {"name": "progress"}, surface="execution")
    assert observed["state"] == "running" and observed["progress"]["elapsed_seconds"] == 12
    # A pure status read must not silently poll the server.
    monkeypatch.setattr(effect, "status_details", lambda _: pytest.fail("status polled the server"))
    assert root.call_tool("execution_status", {"name": "progress"}, surface="execution")["progress"] == observed["progress"]
    # Existing adapters without the optional extension still synchronize.
    monkeypatch.delattr(effect, "status_details")
    monkeypatch.setattr(effect, "status", lambda _: "running", raising=False)
    assert root.call_tool("execution_sync", {"name": "progress"}, surface="execution")["progress"] == observed["progress"]


def test_progress_is_bounded_nonblocking_and_unavailable_time_is_not_invented(tmp_path, monkeypatch):
    _, directory, _ = server_job(tmp_path, monkeypatch)
    outside = tmp_path / "outside"; outside.write_text("UNBOUND PRIVATE DATA")
    (directory / "worker.log").unlink()
    (directory / "worker.log").symlink_to(outside)
    (directory / "work/main.log").unlink()
    os.mkfifo(directory / "work/main.log")
    (directory / "started_at").unlink()
    value = server._job_progress(str(directory))
    assert value["log_tails"] == [] and "elapsed_seconds" not in value
    (directory / "worker.log").unlink()
    os.mkfifo(directory / "worker.log")
    assert server._job_progress(str(directory))["log_tails"] == []
    assert "elapsed_seconds" not in server._execution_timing("2026-09-13T00:00:00Z", terminal=True)
    only_end = server._execution_timing(None, "2026-09-13T00:00:12Z", terminal=True)
    assert only_end["completed_at"] == "2026-09-13T00:00:12Z" and "elapsed_seconds" not in only_end
