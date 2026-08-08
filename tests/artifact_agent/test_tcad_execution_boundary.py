from __future__ import annotations

import hashlib
import io
import json
import os
import signal
import tarfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import tcad_artifact.execution_control as execution_control

from tcad_artifact.execution_control import (
    EXECUTION_TOOLS,
    ArchiveEntry,
    ExpectedOutput,
    FileDescriptor,
    ResourceLimits,
    TCADExecutionFacade,
    TCADExecutionPolicy,
    TCADExecutionRouter,
    TCADJobSpec,
    ToolProfile,
)


def _descriptor(name: str, path: Path, media_type: str) -> FileDescriptor:
    raw = path.read_bytes()
    return FileDescriptor(
        name=name,
        local_path=str(path),
        sha256=hashlib.sha256(raw).hexdigest(),
        size_bytes=len(raw),
        media_type=media_type,
    )


def test_local_execution_preserves_tool_symlink_launch_name(tmp_path: Path) -> None:
    target = tmp_path / "GENERIC"
    target.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    target.chmod(0o750)
    alias = tmp_path / "sprocess"
    alias.symlink_to(target.name)

    assert execution_control._verified_executable(str(alias)) == alias.absolute()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def test_tcad_surface_is_execution_only() -> None:
    assert {tool.name for tool in EXECUTION_TOOLS} == {
        "tcad_submit",
        "tcad_status",
        "tcad_cancel",
        "tcad_collect",
    }
    rendered = json.dumps([tool.schema() for tool in EXECUTION_TOOLS]).lower()
    for forbidden in (
        "approval",
        "artifact_id",
        "execution_id",
        "model",
        "deck",
        "permit",
        "signature",
    ):
        assert forbidden not in rendered


def test_submit_status_and_collect_use_only_local_job_descriptor(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    script = b"printf 'curve\\n' > curve.plt\n"
    archive_path = inputs / "job.tar"
    with tarfile.open(archive_path, "w") as archive:
        info = tarfile.TarInfo("run.sh")
        info.size = len(script)
        archive.addfile(info, io.BytesIO(script))

    job = TCADJobSpec(
        tool_profile="shell_smoke",
        input_archive=_descriptor("input_archive", archive_path, "application/x-tar"),
        archive_entries=(
            ArchiveEntry(
                relative_path="run.sh",
                sha256=hashlib.sha256(script).hexdigest(),
                size_bytes=len(script),
            ),
        ),
        arguments=("run.sh",),
        expected_outputs=(
            ExpectedOutput(
                name="curve",
                relative_path="curve.plt",
                media_type="text/plain",
                max_bytes=1024,
            ),
        ),
        limits=ResourceLimits(
            wall_time_seconds=10,
            cpu_time_seconds=10,
            max_memory_bytes=256 * 1024 * 1024,
            max_output_bytes=1024 * 1024,
            max_processes=8,
        ),
    )
    payload_path = inputs / "job.json"
    payload_path.write_bytes(_canonical(job.model_dump(mode="python")))
    router = TCADExecutionRouter(
        TCADExecutionFacade(
            policy=TCADExecutionPolicy(
                allowed_input_roots=(str(inputs),),
                tools=(
                    ToolProfile(
                        profile_id="shell_smoke",
                        executable="/bin/sh",
                    ),
                ),
            ),
            state_root=tmp_path / "tcad-state",
        )
    )
    submitted = router.call_tool(
        "tcad_submit",
        {
            "submission": _descriptor(
                "execution_payload", payload_path, "application/json"
            ).model_dump(mode="json")
        },
    )
    run_id = submitted["run_id"]
    deadline = time.monotonic() + 5
    while True:
        status = router.call_tool("tcad_status", {"run_id": run_id})
        if status["done"]:
            break
        assert time.monotonic() < deadline
        time.sleep(0.02)
    assert status["state"] == "succeeded"
    collected = router.call_tool("tcad_collect", {"run_id": run_id})
    assert {item["name"] for item in collected["outputs"]} == {
        "curve",
        "tcad_log",
        "tcad_manifest",
    }
    curve = next(item for item in collected["outputs"] if item["name"] == "curve")
    assert Path(curve["local_path"]).read_text(encoding="utf-8") == "curve\n"
    manifest_output = next(
        item for item in collected["outputs"] if item["name"] == "tcad_manifest"
    )
    collected_manifest = json.loads(
        Path(manifest_output["local_path"]).read_text(encoding="utf-8")
    )
    assert collected_manifest["terminal_state"] == "succeeded"
    assert collected_manifest["exit_code"] == 0


def test_concurrent_duplicate_submission_creates_one_run(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    job_path = _job_file(inputs, "duplicate", "sleep 1\n", wall_time_seconds=10)
    facade = _facade(tmp_path, inputs, max_concurrent_runs=2)
    submission = _descriptor("execution_payload", job_path, "application/json")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: facade.tcad_submit(submission=submission), range(2))
        )

    assert len({item["run_id"] for item in results}) == 1
    assert len(list((tmp_path / "tcad-state" / "runs").iterdir())) == 1
    facade.tcad_cancel(run_id=results[0]["run_id"])
    _wait_terminal(facade, results[0]["run_id"])


def test_concurrent_run_limit_rejects_second_distinct_job(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    first = _job_file(inputs, "first", "sleep 30\n", wall_time_seconds=60)
    second = _job_file(inputs, "second", "printf done > second.out\n")
    facade = _facade(tmp_path, inputs, max_concurrent_runs=1)

    running = facade.tcad_submit(
        submission=_descriptor("execution_payload", first, "application/json")
    )
    with pytest.raises(Exception, match="concurrent run limit"):
        facade.tcad_submit(
            submission=_descriptor("execution_payload", second, "application/json")
        )

    facade.tcad_cancel(run_id=running["run_id"])
    _wait_terminal(facade, running["run_id"])
    accepted = facade.tcad_submit(
        submission=_descriptor("execution_payload", second, "application/json")
    )
    assert accepted["state"] == "accepted"
    _wait_terminal(facade, accepted["run_id"])


def test_missing_worker_is_reconciled_to_terminal_failure(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    job_path = _job_file(inputs, "lost", "sleep 30\n", wall_time_seconds=60)
    facade = _facade(tmp_path, inputs, max_concurrent_runs=1)
    submitted = facade.tcad_submit(
        submission=_descriptor("execution_payload", job_path, "application/json")
    )
    run_dir = tmp_path / "tcad-state" / "runs" / submitted["run_id"]
    deadline = time.monotonic() + 5
    while not (run_dir / "solver_pid").is_file():
        assert time.monotonic() < deadline
        time.sleep(0.02)

    launcher_pid = int((run_dir / "launcher_pid").read_text().strip())
    os.killpg(launcher_pid, signal.SIGKILL)
    deadline = time.monotonic() + 5
    while True:
        status = facade.tcad_status(run_id=submitted["run_id"])
        if status["done"]:
            break
        assert time.monotonic() < deadline
        time.sleep(0.02)
    assert status["state"] == "failed"
    assert status["exit_code"] == 98
    manifest = json.loads((run_dir / "output_manifest.json").read_text())
    assert manifest["error"] == "worker_lost"


def test_wall_timeout_terminates_solver_process_group(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    job_path = _job_file(
        inputs,
        "timeout",
        "sleep 30 &\necho $! > child.pid\nwait\n",
        wall_time_seconds=1,
    )
    facade = _facade(tmp_path, inputs, max_concurrent_runs=1)
    submitted = facade.tcad_submit(
        submission=_descriptor("execution_payload", job_path, "application/json")
    )
    status = _wait_terminal(facade, submitted["run_id"], timeout=5)
    assert status["state"] == "failed"
    assert status["exit_code"] == 124
    run_dir = tmp_path / "tcad-state" / "runs" / submitted["run_id"]
    manifest = json.loads((run_dir / "output_manifest.json").read_text())
    assert manifest["error"] == "wall_time_exceeded"
    child_pid = int((run_dir / "work" / "child.pid").read_text().strip())
    deadline = time.monotonic() + 2
    while Path(f"/proc/{child_pid}").exists():
        state = Path(f"/proc/{child_pid}/stat").read_text().rpartition(") ")[2][0]
        if state == "Z":
            break
        assert time.monotonic() < deadline
        time.sleep(0.02)


def test_process_limit_is_scoped_to_the_job_process_group(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    job_path = _job_file(
        inputs,
        "process-limit",
        "sleep 30 &\nwait\n",
        wall_time_seconds=10,
        max_processes=1,
    )
    facade = _facade(tmp_path, inputs, max_concurrent_runs=1)
    submitted = facade.tcad_submit(
        submission=_descriptor("execution_payload", job_path, "application/json")
    )
    status = _wait_terminal(facade, submitted["run_id"], timeout=5)
    assert status["state"] == "failed"
    assert status["exit_code"] == 125
    run_dir = tmp_path / "tcad-state" / "runs" / submitted["run_id"]
    manifest = json.loads((run_dir / "output_manifest.json").read_text())
    assert manifest["error"] == "process_limit_exceeded"


def test_cancel_during_preparation_never_launches_solver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    job_path = _job_file(inputs, "cancel-preparing", "sleep 30\n")
    facade = _facade(tmp_path, inputs, max_concurrent_runs=1)
    submission = _descriptor("execution_payload", job_path, "application/json")
    entered = threading.Event()
    release = threading.Event()
    original_extract = execution_control._extract_archive

    def delayed_extract(*args, **kwargs):
        entered.set()
        assert release.wait(timeout=5)
        return original_extract(*args, **kwargs)

    monkeypatch.setattr(execution_control, "_extract_archive", delayed_extract)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(facade.tcad_submit, submission=submission)
        assert entered.wait(timeout=5)
        with facade._connect() as connection:
            run_id = connection.execute(
                "SELECT run_id FROM submissions"
            ).fetchone()["run_id"]
        assert facade.tcad_cancel(run_id=run_id)["state"] == "cancelling"
        release.set()
        submitted = pending.result(timeout=5)

    assert submitted["state"] == "cancelled"
    run_dir = tmp_path / "tcad-state" / "runs" / run_id
    assert not (run_dir / "launcher_pid").exists()
    manifest = json.loads((run_dir / "output_manifest.json").read_text())
    assert manifest["error"] == "cancelled_before_launch"


def test_stale_preparation_is_reconciled_and_releases_capacity(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    facade = TCADExecutionFacade(
        policy=TCADExecutionPolicy(
            allowed_input_roots=(str(inputs),),
            tools=(ToolProfile(profile_id="shell_smoke", executable="/bin/sh"),),
            max_concurrent_runs=1,
            preparation_timeout_seconds=1,
        ),
        state_root=tmp_path / "tcad-state",
    )
    with facade._connect() as connection:
        connection.execute(
            """
            INSERT INTO submissions (
                job_sha256, run_id, submitted_at, lifecycle_state
            ) VALUES (?, ?, ?, 'preparing')
            """,
            ("0" * 64, "run_stale", "2000-01-01T00:00:00.000000Z"),
        )

    status = facade.tcad_status(run_id="run_stale")
    assert status == {
        "run_id": "run_stale",
        "state": "failed",
        "accepted_at": "2000-01-01T00:00:00.000000Z",
        "exit_code": 96,
        "done": True,
    }
    manifest = json.loads(
        (tmp_path / "tcad-state" / "runs" / "run_stale" / "output_manifest.json").read_text()
    )
    assert manifest["error"] == "preparation_lost"

    next_job = _job_file(inputs, "after-stale", "printf done\n")
    accepted = facade.tcad_submit(
        submission=_descriptor("execution_payload", next_job, "application/json")
    )
    assert _wait_terminal(facade, accepted["run_id"])["state"] == "succeeded"


def _facade(
    tmp_path: Path,
    inputs: Path,
    *,
    max_concurrent_runs: int,
) -> TCADExecutionFacade:
    return TCADExecutionFacade(
        policy=TCADExecutionPolicy(
            allowed_input_roots=(str(inputs),),
            tools=(ToolProfile(profile_id="shell_smoke", executable="/bin/sh"),),
            max_concurrent_runs=max_concurrent_runs,
        ),
        state_root=tmp_path / "tcad-state",
    )


def _job_file(
    root: Path,
    name: str,
    script_text: str,
    *,
    wall_time_seconds: int = 10,
    max_processes: int = 8,
) -> Path:
    script = script_text.encode()
    archive_path = root / f"{name}.tar"
    with tarfile.open(archive_path, "w") as archive:
        info = tarfile.TarInfo("run.sh")
        info.size = len(script)
        archive.addfile(info, io.BytesIO(script))
    job = TCADJobSpec(
        tool_profile="shell_smoke",
        input_archive=_descriptor("input_archive", archive_path, "application/x-tar"),
        archive_entries=(
            ArchiveEntry(
                relative_path="run.sh",
                sha256=hashlib.sha256(script).hexdigest(),
                size_bytes=len(script),
            ),
        ),
        arguments=("run.sh",),
        expected_outputs=(),
        limits=ResourceLimits(
            wall_time_seconds=wall_time_seconds,
            cpu_time_seconds=wall_time_seconds,
            max_memory_bytes=256 * 1024 * 1024,
            max_output_bytes=1024 * 1024,
            max_processes=max_processes,
        ),
    )
    path = root / f"{name}.json"
    path.write_bytes(_canonical(job.model_dump(mode="python")))
    return path


def _wait_terminal(
    facade: TCADExecutionFacade,
    run_id: str,
    *,
    timeout: float = 5,
) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while True:
        status = facade.tcad_status(run_id=run_id)
        if status["done"]:
            return status
        assert time.monotonic() < deadline
        time.sleep(0.02)
