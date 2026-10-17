"""Bounded server observations survive transport, author and scheduler handoffs."""
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
