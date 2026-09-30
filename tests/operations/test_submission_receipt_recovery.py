"""Submission visibility and durable receipt interruption windows; no real TCAD."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scidiscovery.artifact_agent.execution_bridge import ExecutionBridge
from scidiscovery.artifact_agent.schema.common import canonical_json, canonical_sha256
from scidiscovery.artifact_agent.service.executions import ExecutionServiceError
from scidiscovery.artifact_agent.service.experiment_execution import ExperimentExecution
from scidiscovery.operation_contract import DiagnosticError
from tests.operations.test_experiment_continuation import continuation
from tests.operations.test_review_delivery_and_debug_scope import debug, debug_service
from tests.operations.test_tcad_execution_policy import _reauthorization_service
from tests.operations.tcad_policy_fixtures import policy_snapshot
from tcad_artifact.debug_contract import TCADDebugError


def test_changed_policy_cannot_reauthorize_an_invisible_prepared_submission(tmp_path):
    from scidiscovery.artifact_agent.service.executions import ExecutionApprovalError
    service, identity = _reauthorization_service(tmp_path)
    admission = policy_snapshot().admission(budget={"wall_time_seconds": 30, "max_storage_bytes": 1000}, budget_key="a"*64)
    descriptor = service.authorize_policy(execution_id="one", admission=admission, compiled_identity=identity)
    service.record_prepared_submission("one", descriptor, policy_digest=admission.policy_digest)
    request = service.request("one")
    service.request = lambda _: SimpleNamespace(**vars(request), preparation_profile="fixture", payload_ref=service.approval_subject_refs("one")[1])
    adapter = SimpleNamespace(lookup_submission=lambda _: None)
    bridge = ExecutionBridge(service, adapters={"tcad": adapter})
    changed = admission.model_copy(update={"reason": "changed authorization"})
    bridge.validate_request = lambda **_: changed
    service.budget_admission = lambda **kwargs: kwargs["admission"]
    with pytest.raises(ExecutionApprovalError, match="remains uncertain"):
        bridge.start(execution_id="one", approval_id=None, compiled_identity=identity, allow_policy_authorization=True)
    assert service.authorization("one")["reason"] == admission.reason
    assert service.authorization("one")["accounting"]["actual"] == {}


@pytest.mark.parametrize("corruption", ["bytes", "timing", "identity"])
@pytest.mark.parametrize("persisted_state", ["accepted", "collected"])
def test_invalid_receipt_never_settles_the_reservation(tmp_path, monkeypatch, corruption, persisted_state):
    f = continuation(tmp_path, monkeypatch)
    service = debug_service(f)
    collect = service.adapter.collect_with_budget
    monkeypatch.setattr(service.adapter, "collect_with_budget", lambda *args, **kwargs:
        replace(collect(*args, **kwargs), timing={"elapsed_seconds": .2}))
    debug(f, "receipt")
    path = next((service.exchange_root / "budgets").glob("*.json"))
    ledger = json.loads(path.read_bytes())
    record = ledger["runs"]["receipt"]
    if persisted_state == "accepted":
        record.pop("response")
    record.pop("actual_wall_seconds")
    record["state"] = persisted_state
    ledger["reserved_wall_seconds"] = sum(item["record"]["reserved_wall_seconds"] for item in ledger["reservations"].values())
    path.write_bytes(canonical_json(ledger))
    root = path.parent / "receipts" / canonical_sha256({"run_id": f.run_id, "run_name": "receipt"})
    receipt_path = root / "receipt.json"
    receipt = json.loads(receipt_path.read_bytes())
    if corruption == "bytes":
        retained = root / receipt["proof"]["files"][0]["sha256"]
        retained.chmod(0o600)
        retained.write_bytes(b"damaged")
    elif corruption == "timing":
        # Altering both projections must still fail against the hashed original.
        receipt["proof"]["progress"]["elapsed_seconds"] = 0
        receipt["response"]["progress"]["elapsed_seconds"] = 0
    else:
        receipt["submission"]["sha256"] = "0"*64
    receipt_path.chmod(0o600)
    receipt_path.write_bytes(canonical_json(receipt))
    before = json.loads(path.read_bytes())
    with pytest.raises(DiagnosticError) as caught:
        debug(f, "receipt")
    assert isinstance(caught.value.__cause__, TCADDebugError)
    assert json.loads(path.read_bytes()) == before
    assert "actual_wall_seconds" not in json.loads(path.read_bytes())["runs"]["receipt"]


@pytest.mark.process_e2e
def test_receipt_survives_exit_before_budget_commit_without_executor_access(tmp_path, monkeypatch):
    import multiprocessing
    import os
    f = continuation(tmp_path, monkeypatch)
    service = debug_service(f)
    collect = service.adapter.collect_with_budget
    monkeypatch.setattr(service.adapter, "collect_with_budget", lambda *args, **kwargs:
        replace(collect(*args, **kwargs), timing={"elapsed_seconds": .2}))
    policy = service.adapter.policy.model_copy(update={"total_wall_seconds": 4})
    monkeypatch.setattr(type(service.adapter), "policy", property(lambda _: policy))
    monkeypatch.setattr(service.adapter, "clamp_wall_time", lambda prepared, **_: replace(prepared, wall_time_seconds=4))
    save = service._save_receipt
    def exit_after_receipt(*args, **kwargs):
        save(*args, **kwargs)
        os._exit(17)
    monkeypatch.setattr(service, "_save_receipt", exit_after_receipt)
    child = multiprocessing.get_context("fork").Process(target=lambda: debug(f, "crash-window"))
    child.start()
    try:
        child.join(10)
        assert child.exitcode == 17
    finally:
        if child.is_alive():
            child.kill()
            child.join(5)
    path = next((service.exchange_root / "budgets").glob("*.json"))
    before = json.loads(path.read_bytes())
    assert "crash-window" not in before["runs"]
    assert "actual_wall_seconds" not in before["reservations"]["crash-window"]["record"]
    monkeypatch.setattr(service, "_save_receipt", save)
    for method in ("lookup_submission", "submit", "status", "status_details", "collect_with_budget"):
        monkeypatch.setattr(service.adapter, method, lambda *args, **kwargs: pytest.fail("receipt recovery contacted executor"), raising=False)
    first = debug(f, "crash-window")
    assert first["state"] == "succeeded"
    assert first["budget"]["actual_wall_seconds"] == 1
    assert first["budget"]["reserved_wall_seconds"] == 0
    assert first["budget"]["remaining_wall_seconds"] == 3
    settled = path.read_bytes()
    assert json.loads(settled)["runs"]["crash-window"]["state"] == "collected"
    assert json.loads(settled)["reserved_wall_seconds"] == before["reserved_wall_seconds"] - 3
    assert debug(f, "crash-window")["budget"] == first["budget"]
    assert path.read_bytes() == settled
    assert f.worker.call_tool("worker_experiment_debug", {"action": "status", "name": "crash-window"})["state"] == "collected"


@pytest.mark.process_e2e
@pytest.mark.parametrize("retire", [False, True])
def test_timed_out_daemon_submit_remains_owned_during_invisible_archive_check(tmp_path, monkeypatch, retire):
    import hashlib
    import io
    import multiprocessing
    import os
    import socket
    import sqlite3
    import sys
    import tarfile
    import time
    from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
    from scidiscovery.artifact_agent.schema.execution import LocalFileDescriptor
    from scidiscovery.plugin_runtime.transport import UnixSocketDaemon
    from tcad_artifact import execution_control as control
    from tests.operations.test_debug_readonly_status import fixture
    config = json.loads((Path(__file__).resolve().parents[2] / "plugins/tcad_artifact/config/execution-policy.example.json").read_bytes())
    config["allowed_input_roots"] = [str(tmp_path)]
    config["tools"] = [{**config["tools"][0], "executable": sys.executable,
        "arguments": ["-c", "import time; time.sleep(.3); print('fake solver finished')"], "environment": {}}]
    policy = control.TCADExecutionPolicy.model_validate_json(json.dumps(config), strict=True)
    archive = tmp_path / "inputs.tar"
    raw = b"# fixture only\n"
    with tarfile.open(archive, "w") as tar:
        item = tarfile.TarInfo("main.cmd")
        item.size = len(raw)
        tar.addfile(item, io.BytesIO(raw))
    job = control.TCADJobSpec(execution_purpose="development_debug", tool_profile=policy.tools[0].profile_id,
        solver_kind="sprocess", capability_sha256=policy.tools[0].canonical_sha256(),
        input_archive=control.FileDescriptor(name="archive", local_path=str(archive), media_type="application/x-tar",
            size_bytes=archive.stat().st_size, sha256=hashlib.sha256(archive.read_bytes()).hexdigest()),
        archive_entries=(control.ArchiveEntry(relative_path="main.cmd", size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()),),
        expected_outputs=(), limits=control.ResourceLimits(wall_time_seconds=4, cpu_time_seconds=4,
            max_memory_bytes=128*1024*1024, max_storage_bytes=1024*1024, max_output_bytes=1024*1024))
    submission_path = tmp_path / "submission.json"
    submission_raw = canonical_json(job.model_dump(mode="json"))
    submission_path.write_bytes(submission_raw)
    descriptor = LocalFileDescriptor(name="submission", local_path=str(submission_path), media_type="application/json",
        size_bytes=len(submission_raw), sha256=hashlib.sha256(submission_raw).hexdigest())
    ctx = multiprocessing.get_context("fork")
    paused, resume = ctx.Event(), ctx.Event()
    identity = control._file_identity
    def pause_archive(path, chunk_bytes):
        if path == archive:
            paused.set()
            if not resume.wait(10):
                raise TimeoutError("controlled pause expired")
        return identity(path, chunk_bytes)
    monkeypatch.setattr(control, "_file_identity", pause_archive)
    state_root = tmp_path / "backend"
    facade = control.TCADExecutionFacade(policy=policy, state_root=state_root)
    finished = ctx.Event()
    original_submit = facade.tcad_submit
    def tracked_submit(**kwargs):
        try:
            return original_submit(**kwargs)
        finally:
            finished.set()
    monkeypatch.setattr(facade, "tcad_submit", tracked_submit)
    socket_path = tmp_path / "backend.sock"
    daemon = ctx.Process(target=lambda: UnixSocketDaemon(socket_path,
        MCPRouter(control.TCADExecutionRouter(facade), name="submission-race")).serve_forever())
    def rpc(name, arguments, timeout=2):
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}}
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(timeout)
            connection.connect(str(socket_path))
            connection.sendall(canonical_json(request) + b"\n")
            with connection.makefile("rb") as stream:
                response = json.loads(stream.readline())
        assert "error" not in response, response
        return response["result"]["structuredContent"]
    def lookup(_):
        result = rpc("tcad_lookup_submission", {"submission_sha256": descriptor.sha256})
        return (result["run_id"], result["state"]) if result["found"] else None
    adapter = SimpleNamespace(lookup_submission=lookup,
        cancel=lambda external: rpc("tcad_cancel", {"run_id": external})["state"],
        status=lambda external: rpc("tcad_status", {"run_id": external})["state"],
        status_details=lambda external: rpc("tcad_status", {"run_id": external}))
    daemon.start()
    try:
        deadline = time.monotonic() + 5
        while not socket_path.exists() and time.monotonic() < deadline:
            time.sleep(.02)
        assert socket_path.exists()
        submitted = descriptor.model_dump(mode="json")
        submitted.pop("schema_version")
        with pytest.raises(TimeoutError):
            rpc("tcad_submit_retirable" if retire else "tcad_submit", {"submission": submitted}, timeout=.2)
        assert paused.is_set() and lookup(descriptor) is None
        if retire:
            proof = rpc("tcad_retire_submission", {"submission_sha256": descriptor.sha256})
            assert proof == {"found": False, "retired": True, "submission_sha256": descriptor.sha256}
            resume.set()
            assert finished.wait(5)
            assert lookup(descriptor) is None
            with sqlite3.connect(facade.database_path) as db:
                assert db.execute("SELECT COUNT(*) FROM submissions").fetchone()[0] == 0
            assert list(facade.runs_root.iterdir()) == []
            return
        debug_root = tmp_path / "debug"
        debug_root.mkdir()
        debugger, context, ledger_path = fixture(debug_root, reservation=True)
        debugger.adapter = adapter
        ledger = json.loads(ledger_path.read_bytes())
        ledger["reserved_wall_seconds"] = 30
        ledger["reservations"]["init"]["record"]["reserved_wall_seconds"] = 30
        ledger["reservations"]["init"]["submission"] = descriptor.model_dump(mode="json")
        ledger_path.write_bytes(canonical_json(ledger))
        inputs = (SimpleNamespace(port_name="research_objective", artifact_ref=context.input_ref("")),)
        pending = []
        assert debugger.experiment_activity({"private-run"}, inputs, pending=pending)
        assert pending and "uncertain" in pending[0]["message"]
        before = ledger_path.read_bytes()
        with pytest.raises(DiagnosticError, match="could not be confirmed"):
            debugger.experiment_activity({"private-run"}, inputs, cancel=True)
        assert ledger_path.read_bytes() == before
        assert debugger.status(context, run_name="init")["submission"] == "unknown"
        service, compiled = _reauthorization_service(tmp_path / "formal")
        admission = policy_snapshot().admission(budget={"wall_time_seconds": 30, "max_storage_bytes": 1000}, budget_key="a"*64)
        service.authorize_policy(execution_id="one", admission=admission, compiled_identity=compiled)
        service.record_prepared_submission("one", descriptor, policy_digest=admission.policy_digest)
        bridge = ExecutionBridge(service, adapters={"tcad": adapter})
        owner = ExperimentExecution(runs=None, executions=service, bridge=bridge, collection=None, approval_base_url=None)
        with pytest.raises(ExecutionServiceError, match="not confirmed"):
            bridge.abandon("one")
        with pytest.raises(DiagnosticError, match="could not be confirmed"):
            owner._cancel("one")
        owner._reconcile_authorization("one", SimpleNamespace(status="expired"))
        assert service.status("one").state == "authorized"
        assert service.authorization("one")["accounting"]["actual"] == {}
        resume.set()
        deadline = time.monotonic() + 5
        found = lookup(descriptor)
        while found is None and time.monotonic() < deadline:
            time.sleep(.02)
            found = lookup(descriptor)
        assert found is not None
        owner._cancel("one")
        assert service.status("one").external_run_id == found[0]
        assert service.status("one").state != "abandoned"
        debugger.experiment_activity({"private-run"}, inputs, cancel=True)
        assert json.loads(ledger_path.read_bytes())["runs"]["init"]["external_run_id"] == found[0]
        with sqlite3.connect(facade.database_path) as db:
            assert db.execute("SELECT COUNT(*) FROM submissions").fetchone()[0] == 1
        deadline = time.monotonic() + 5
        while adapter.status(found[0]) not in {"succeeded", "failed", "cancelled"} and time.monotonic() < deadline:
            time.sleep(.02)
        assert adapter.status(found[0]) in {"succeeded", "failed", "cancelled"}
    finally:
        resume.set()
        daemon.terminate()
        daemon.join(5)
        if daemon.is_alive():
            daemon.kill()
            daemon.join(5)
        for run in facade.runs_root.iterdir():
            pid = run / "launcher_pid"
            if pid.exists():
                try:
                    os.killpg(int(pid.read_text()), 9)
                except ProcessLookupError:
                    pass
