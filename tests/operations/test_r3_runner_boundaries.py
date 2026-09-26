"""Small real local processes and files; no TCAD binary, installer, or SSH host."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from tcad_artifact import remote_runner_py36
from tests.operations.tcad_policy_fixtures import policy_fields


FAKE_SOLVER = '''
from pathlib import Path
import os, signal, subprocess, sys, time
child = subprocess.Popen([sys.executable, "-c", "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(15)"])
Path("child.pid").write_text(str(child.pid))
mode = sys.argv[1]
if mode == "wall":
    Path("case-one.started").touch()
    time.sleep(0.6)
    Path("case-one.done").touch()
    Path("case-two.started").touch()
    time.sleep(0.8)
    Path("case-two.done").touch()
elif mode == "files":
    Path("first.bin").write_bytes(b"a" * 12000)
    Path("second.bin").write_bytes(b"b" * 12000)
    time.sleep(10)
elif mode == "stdout":
    os.write(1, b"log-data" * 4096)
    time.sleep(10)
elif mode == "parent_exit":
    Path("parent-done").touch()
'''


def _live(pid):
    try:
        # A killed orphan can remain a zombie until container init reaps it.
        return Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1][0] != "Z"
    except FileNotFoundError:
        return False


@pytest.mark.parametrize("mode", ["wall", "files", "stdout", "parent_exit"])
def test_real_runner_enforces_shared_limits_and_reaps_children(tmp_path, mode):
    work = tmp_path / "work"
    work.mkdir()
    (work / "fake_solver.py").write_text(FAKE_SOLVER)
    fields = policy_fields()
    job = {
        "runner_policy": {**fields["runner"], "sample_interval_seconds": 0.02,
                          "terminate_grace_seconds": 0.1, "transfer_chunk_bytes": 1024},
        "archive_entries": [], "executable": sys.executable,
        "arguments": ["fake_solver.py", mode], "environment": {},
        "execution_purpose": "production", "expected_outputs": [],
        "limits": {"max_storage_bytes": 16384 if mode in {"files", "stdout"} else 131072,
                   "cpu_time_seconds": 5, "wall_time_seconds": 1 if mode == "wall" else 4,
                   "max_memory_bytes": 268435456, "max_output_bytes": 1048576},
    }
    (tmp_path / "runtime.json").write_text(json.dumps(job))
    command = [sys.executable, "-c",
        "import runpy,sys; raise SystemExit(runpy.run_path(sys.argv[1])['_run_worker']({},sys.argv[2]))",
        remote_runner_py36.__file__, str(tmp_path)]
    started = time.monotonic()
    try:
        completed = subprocess.run(command, capture_output=True, timeout=15)
        elapsed = time.monotonic() - started
        manifest = json.loads((tmp_path / "output_manifest.json").read_text())
        assert elapsed < 8, (elapsed, manifest)
        assert (tmp_path / "done").is_file() and not (tmp_path / "running").exists()
        assert manifest["resource_usage"]["accounting"] == "sampled_logical_files"
        assert manifest["resource_usage"]["hard_quota"] is False
        child_pid = int((work / "child.pid").read_text())
        solver_pid = int((tmp_path / "solver_pid").read_text())
        until = time.monotonic() + 1
        while (_live(child_pid) or _live(solver_pid)) and time.monotonic() < until:
            time.sleep(0.02)
        assert not _live(child_pid) and not _live(solver_pid), "runner left solver descendants alive"
        if mode == "parent_exit":
            assert completed.returncode == 0 and manifest["terminal_state"] == "succeeded", manifest
        else:
            assert completed.returncode == 124 and manifest["terminal_state"] == "failed", manifest
            expected = "wall_time_exceeded" if mode == "wall" else "total_storage_exceeded"
            assert manifest["error"] == expected, manifest
        if mode == "wall":
            assert (work / "case-one.done").exists() and (work / "case-two.started").exists()
            assert not (work / "case-two.done").exists(), "case two received a reset wall budget"
        elif mode in {"files", "stdout"}:
            usage = manifest["resource_usage"]
            assert usage["observed_storage_high_water_bytes"] > job["limits"]["max_storage_bytes"]
            assert usage["storage_overshoot_bytes"] > 0
            if mode == "files":
                assert all((work / name).stat().st_size < job["limits"]["max_storage_bytes"]
                           for name in ("first.bin", "second.bin")), "must exercise aggregate files, not one-file cap"
            else:
                assert (tmp_path / "worker.log").stat().st_size >= 32768
    finally:
        # Defensive cleanup on a failed assertion/worker crash; no real solver exists.
        pid_file = tmp_path / "solver_pid"
        if pid_file.exists():
            try:
                os.killpg(int(pid_file.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_budget_reservations_and_settlement_survive_process_restart(tmp_path):
    script = '''
import json,sys
from pathlib import Path
from scidiscovery.artifact_agent.service.executions import ExecutionService
from tcad_artifact.execution_policy import ExecutionPolicySnapshot
root=Path(sys.argv[1]); phase=sys.argv[2]
service=ExecutionService(artifacts=None, approvals=None, database_path=root/'execution.sqlite', exchange_root=root/'exchange',service_actor=None)
policy=ExecutionPolicySnapshot.model_validate_json((root/'policy.json').read_text(),strict=True)
admission=policy.admission(budget={'max_storage_bytes':300,'wall_time_seconds':3},budget_key='a'*64)
if phase=='reserve':
    with service._connect() as connection:
        # A terminal execution whose usage receipt has not yet been observed.
        connection.execute("INSERT INTO executions (execution_id,executor,request_ref_json,payload_ref_json,state,created_at) VALUES ('first','fixture','{}','{}','failed','fixture')")
        service._reserve_budget(connection,'first','fixture',admission)
else:
    with service._connect() as connection:
        before=service._budget_remaining(connection,'fixture',admission)
    assert before=={'max_storage_bytes':700,'wall_time_seconds':1},before
    service.settle_budget('first',{'max_storage_bytes':100,'wall_time_seconds':1})
    # Repeated terminal observation cannot refund settled usage.
    service.settle_budget('first',{'max_storage_bytes':0,'wall_time_seconds':0})
    with service._connect() as connection:
        after=service._budget_remaining(connection,'fixture',admission)
    assert after=={'max_storage_bytes':900,'wall_time_seconds':3},after
    print(json.dumps(after))
'''
    fields = policy_fields()
    fields["agent_execution_policy"].update(max_storage_bytes=1000, max_wall_time_seconds=4)
    (tmp_path / "policy.json").write_text(json.dumps(fields))
    environment = {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)}
    for phase in ("reserve", "settle"):
        completed = subprocess.run([sys.executable, "-c", script, str(tmp_path), phase],
            env=environment, capture_output=True, text=True, timeout=15)
        assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {"max_storage_bytes": 900, "wall_time_seconds": 3}


def test_control_ingests_and_reads_file_reference_without_whole_file_read(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    from scidiscovery.artifact_agent.schema.refs import ActorRef
    from scidiscovery.artifact_agent.service.artifacts import ArtifactService
    source = tmp_path / "grid.bin"
    digest = hashlib.sha256()
    with source.open("wb") as stream:
        for _ in range(512):
            chunk = b"grid" * 1024
            digest.update(chunk)
            stream.write(chunk)
    service = ArtifactService.open(cas_root=tmp_path / "cas", database_path=tmp_path / "artifacts.sqlite")
    original_read_bytes = Path.read_bytes
    def bounded_only(path):
        if path == source or path.is_relative_to(tmp_path / "cas"):
            pytest.fail("binary ingestion must stream rather than read_bytes")
        return original_read_bytes(path)
    monkeypatch.setattr(Path, "read_bytes", bounded_only)
    artifact = service.register_file(source, ArtifactRegistration(kind="grid",schema_id="opaque",
        payload_schema_version=1, media_type="application/octet-stream",
        creator=ActorRef(actor_id="fixture", actor_type="service")),
        expected_sha256=digest.hexdigest(), expected_size=source.stat().st_size,
        idempotency_key="streamed-grid")
    monkeypatch.setattr(service.cas, "read", lambda *_: pytest.fail("original delivery must stream"))
    observed = hashlib.sha256()
    with service.open_original(artifact.ref) as stream:
        for chunk in iter(lambda: stream.read(1024), b""):
            observed.update(chunk)
    assert artifact.size_bytes == 2097152 and observed.hexdigest() == digest.hexdigest()


# These tests exercise real supervised child lifecycle and restart behavior.
pytestmark = pytest.mark.process_e2e
