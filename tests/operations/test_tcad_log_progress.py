"""Bounded server observations survive transport, author and scheduler handoffs."""
import json
import os
from pathlib import Path

import pytest

from tcad_artifact import remote_runner_py36 as server
from tcad_artifact.command_adapter import CommandTCADExecutorAdapter
from tcad_artifact.debug_adapter import TCADDevelopmentDebugBridge
from tcad_artifact.execution_adapter import TCADExecutorAdapter
from tcad_artifact.ssh_transport import SSHTCADTransport
from tests.operations.test_log_preservation import _descriptor


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


def test_server_progress_reaches_author_and_terminal_log_is_readable(tmp_path, monkeypatch):
    from tests.operations.test_l4_local_tcad import _budget_case
    run_id, directory, config = server_job(tmp_path / "server", monkeypatch)
    transport = SSHTCADTransport(None, local_result_root=tmp_path / "received")
    monkeypatch.setattr(transport, "_rpc", lambda name, payload: server._status(config, payload["run_id"]))
    adapter = object.__new__(CommandTCADExecutorAdapter)
    monkeypatch.setattr(adapter, "_call", transport.handle)
    bridge = TCADDevelopmentDebugBridge(adapter)
    worker, debug, opened = _budget_case(tmp_path)
    submit = debug.submit
    def submit_job(submission):
        submit(submission)
        return run_id, "running"
    monkeypatch.setattr(debug, "submit", submit_job)
    monkeypatch.setattr(debug, "status_details", bridge.status_details, raising=False)
    monkeypatch.setattr(debug, "collect", bridge.collect)
    monkeypatch.setattr(adapter, "collect", lambda _: tuple(
        _descriptor(item["name"], Path(item["local_path"]), item["media_type"])
        for item in server._collect(config, run_id)["outputs"]))
    request = {"run_name": "live", "mode": "preflight"}
    pending = worker.call_tool("worker_tcad_debug_run", request)
    assert pending["phase"] == "pending", pending
    assert pending["progress"]["elapsed_seconds"] == 12
    text = json.dumps(pending["progress"])
    assert "Newton iteration 3" in text and "mesh initialization started" in text
    assert "/private/runtime" not in text and "do-not-expose" not in text
    assert len(text.encode()) < 16 * 1024
    assert pending["reserved_wall_seconds_for_run"] == 60  # distinct from 12 seconds observed
    finish_job(directory)
    terminal = worker.call_tool("worker_tcad_debug_run", request)
    assert terminal["state"] == "failed" and terminal["phase"] == "collected", terminal
    assert terminal["progress"]["elapsed_seconds"] == 12
    assert terminal["progress"]["completed_at"] == "2026-09-13T00:00:12Z"
    log = Path(opened["workspace_path"]) / terminal["log_relative_path"]
    assert "fixture convergence failure" in log.read_text()
    assert "Last solver step: Newton 3" in log.read_text()
    assert worker.call_tool("worker_tcad_debug_run", request)["progress"] == terminal["progress"]
    assert debug.submissions == 1


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
    root.call_tool("execution_start", {"name": "progress"})
    monkeypatch.setattr(effect, "status_details", lambda _: adapter.status_details(run_id), raising=False)
    observed = root.call_tool("execution_sync", {"name": "progress"})
    assert observed["state"] == "running" and observed["progress"]["elapsed_seconds"] == 12
    # A pure status read must not silently poll the server.
    monkeypatch.setattr(effect, "status_details", lambda _: pytest.fail("status polled the server"))
    assert root.call_tool("execution_status", {"name": "progress"})["progress"] == observed["progress"]
    # Existing adapters without the optional extension still synchronize.
    monkeypatch.delattr(effect, "status_details")
    monkeypatch.setattr(effect, "status", lambda _: "running", raising=False)
    assert root.call_tool("execution_sync", {"name": "progress"})["progress"] == observed["progress"]


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


def test_server_charset_log_is_bound_and_readable_by_runtime_failure_author(tmp_path, monkeypatch):
    from tests.operations.test_l4_local_tcad import _system, _invoke, _debug_worker, _ImmediateDebugAdapter, _write_author_workspace, _project
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    from scidiscovery.artifact_agent.schema.common import canonical_json
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from tcad_artifact.local_debug_service import LocalTCADDebugService
    catalog, runtime, root, capability = _system(tmp_path)
    common = [{"port": "execution_capability", "artifact_names": ["execution_capability"]},
              {"port": "experiment_plan", "artifact_names": ["experiment_plan"]}]
    _invoke(root, "original", "tcad.deck.author.initial.v1", common)
    author = _debug_worker(catalog, runtime, _ImmediateDebugAdapter(), tmp_path / "debug")
    opened = author.call_tool("worker_open_assignment", {})
    _write_author_workspace(opened, _project(capability))
    for mode in ("preflight", "initialization"):
        assert author.call_tool("worker_tcad_debug_run", {"run_name": mode, "mode": mode})["state"] == "succeeded"
    assert author.call_tool("worker_submit_result", {})["state"] == "completed"
    prior = root.call_tool("run_status", {"name": "original"})["output_artifact_name"]
    instance = runtime.scheduler_bindings.list_instances()[0].instance_id
    def register(name, raw, schema, media):
        artifact = runtime.artifacts.register(raw, ArtifactRegistration(kind="fixture", schema_id=schema,
            payload_schema_version=1, media_type=media, creator=runtime.actor), idempotency_key=name)
        runtime.scheduler_bindings.bind(instance=instance, namespace="artifact", name=name, object_id=artifact.artifact_id)
    run_id, directory, config = server_job(tmp_path / "server", monkeypatch)
    finish_job(directory)
    log = next(item for item in server._collect(config, run_id)["outputs"] if item["name"] == "tcad_log")
    assert log["media_type"] == "text/plain; charset=utf-8"
    raw = Path(log["local_path"]).read_bytes()
    register("server_log", raw, "opaque", log["media_type"])
    # Bounded synthetic failure signal; the prior project above is truly sealed.
    register("failure", canonical_json(dict(schema_version=1, verdict="fail", terminal_state="failed", exit_code=1,
        checks=[dict(check_key="solver_failed", status="fail", rationale="Fixture solver failure.")],
        solver_native_output_count=0, transport_derived_output_count=0, parser_derived_output_count=0,
        rationale="Fixture terminal failure.")), "tcad.runtime-attestation.v1", "application/json")
    _invoke(root, "revision", "tcad.deck.author.runtime-failure.v1", [*common,
        {"port": "prior_project", "artifact_names": [prior]},
        {"port": "runtime_attestation", "artifact_names": ["failure"]},
        {"port": "solver_log", "artifact_names": ["server_log"]}])
    operation = catalog.operation("tcad.deck.author.runtime-failure.v1")
    revised = LocalWorkerMCPRouter(runtime.runs, operation_id=operation.spec.operation_id, operation_digest=operation.digest,
        tool_services={"tcad_artifact:tcad.development_debug": LocalTCADDebugService(
            adapter=_ImmediateDebugAdapter(), exchange_root=tmp_path / "revision-debug")})
    opened = revised.call_tool("worker_open_assignment", {})
    assignment = json.loads(Path(opened["assignment_path"]).read_text())
    binding = next(item for item in assignment["inputs"] if item["source_name"] == "solver_log")
    assert (Path(opened["workspace_path"]) / binding["relative_path"]).read_bytes() == raw
