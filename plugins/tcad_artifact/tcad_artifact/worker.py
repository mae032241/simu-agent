"""Detached worker lifecycle used internally by tcad_control."""

from __future__ import annotations

import hashlib
import json
import os
import resource
import signal
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


_DEBUG_STDOUT_BYTES = 256 * 1024
_DEBUG_SOLVER_LOG_BYTES = 240 * 1024


class _Cancelled(Exception):
    pass


class _RuntimeLimitExceeded(Exception):
    def __init__(self, *, exit_code: int, reason: str) -> None:
        super().__init__(reason)
        self.exit_code = exit_code
        self.reason = reason


def main(argv: list[str] | None = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    if len(values) != 1:
        return 64
    run_dir = Path(values[0]).absolute()
    job = json.loads((run_dir / "job.json").read_text(encoding="utf-8"))
    (run_dir / "pid").write_text(f"{os.getpid()}\n", encoding="ascii")
    (run_dir / "running").touch(exist_ok=False)
    started_at = _timestamp()
    exit_code = 99
    terminal = "failed"
    error = ""
    outputs: list[dict[str, object]] = []
    process: subprocess.Popen | None = None

    def cancel(*_: object) -> None:
        raise _Cancelled

    signal.signal(signal.SIGTERM, cancel)
    signal.signal(signal.SIGINT, cancel)
    try:
        environment = {
            "HOME": str(run_dir),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PATH": "/usr/bin:/bin",
            **job["environment"],
        }
        with (run_dir / "worker.log").open("wb") as log:
            process = subprocess.Popen(
                [job["executable"], *job["arguments"]],
                cwd=run_dir / "work",
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=environment,
                preexec_fn=lambda: _limits(job["limits"]),
                start_new_session=True,
            )
            _atomic_text(run_dir / "solver_pid", f"{process.pid}\n")
            exit_code = _wait_with_job_limits(process, job["limits"])
        _collect_outputs(
            run_dir / "work",
            job["expected_outputs"],
            job["limits"],
            records=outputs,
        )
        terminal = "succeeded" if exit_code == 0 else "failed"
    except _RuntimeLimitExceeded as failure:
        if process is not None:
            _terminate(process)
        exit_code = failure.exit_code
        error = failure.reason
    except _Cancelled:
        if process is not None and process.poll() is None:
            _terminate(process)
        exit_code = 130
        terminal = "cancelled"
        error = "cancelled"
    except Exception as failure:
        error = f"{type(failure).__name__}: {failure}"
        if exit_code == 0:
            exit_code = 97
    try:
        _augment_development_debug_log(run_dir, job)
    except Exception:
        pass
    manifest = {
        "completed_at": _timestamp(),
        "error": error,
        "exit_code": exit_code,
        "outputs": outputs,
        "started_at": started_at,
        "terminal_state": terminal,
    }
    _atomic_json(run_dir / "output_manifest.json", manifest)
    _atomic_text(run_dir / "status", f"{exit_code}\n")
    (run_dir / "running").unlink(missing_ok=True)
    (run_dir / "done").touch(exist_ok=False)
    return exit_code


def _collect_outputs(
    root: Path,
    expected: list[dict],
    limits: dict,
    *,
    records: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    records = [] if records is None else records
    total = sum(int(item["size_bytes"]) for item in records)
    for item in expected:
        capture = item.get("capture", "workspace_file")
        if capture == "workspace_file":
            path = root.joinpath(*item["relative_path"].split("/"))
        elif capture == "process_log":
            path = root.parent / "worker.log"
        else:
            raise RuntimeError("unsupported output capture mode")
        try:
            metadata = os.lstat(path)
        except FileNotFoundError:
            if item["required"]:
                raise RuntimeError(f"required output missing: {item['relative_path']}")
            continue
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise RuntimeError(f"output is not a regular file: {item['relative_path']}")
        content = path.read_bytes()
        if len(content) > item["max_bytes"]:
            raise RuntimeError(f"output exceeds contract: {item['relative_path']}")
        total += len(content)
        if total > limits["max_output_bytes"]:
            raise RuntimeError("total output exceeds job limit")
        if capture == "process_log":
            target = root.joinpath(*item["relative_path"].split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            _atomic_bytes(target, content)
        records.append(
            {
                "name": item["name"],
                "media_type": item["media_type"],
                "relative_path": item["relative_path"],
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
            }
        )
    return records


def _augment_development_debug_log(run_dir: Path, job: dict) -> None:
    if job.get("execution_purpose") != "development_debug":
        return
    arguments = job.get("arguments")
    if not isinstance(arguments, list) or not arguments:
        return
    entrypoint = arguments[-1]
    if not isinstance(entrypoint, str) or not entrypoint.endswith(".cmd"):
        return
    work_dir = run_dir / "work"
    preferred = Path(entrypoint).stem + ".log"
    names = [preferred]
    names.extend(
        path.name
        for path in sorted(work_dir.glob("*.log"))
        if path.name != preferred
    )
    solver_log = next(
        (
            work_dir / name
            for name in names[:32]
            if (work_dir / name).is_file() and not (work_dir / name).is_symlink()
        ),
        None,
    )
    if solver_log is None:
        return
    stdout = _bounded_excerpt(run_dir / "worker.log", _DEBUG_STDOUT_BYTES)
    solver = _bounded_excerpt(solver_log, _DEBUG_SOLVER_LOG_BYTES)
    _atomic_bytes(
        run_dir / "worker.log",
        stdout + b"\n--- scidiscovery solver diagnostic ---\n" + solver,
    )


def _bounded_excerpt(path: Path, limit: int) -> bytes:
    metadata = path.lstat()
    if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
        raise ValueError("debug log is not a regular file")
    with path.open("rb") as stream:
        if metadata.st_size <= limit:
            return stream.read(limit + 1)
        half = limit // 2
        head = stream.read(half)
        stream.seek(-half, os.SEEK_END)
        tail = stream.read(half)
    return head + b"\n--- bounded log omission ---\n" + tail


def _limits(limits: dict) -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (limits["cpu_time_seconds"], limits["cpu_time_seconds"] + 1))
    resource.setrlimit(resource.RLIMIT_AS, (limits["max_memory_bytes"], limits["max_memory_bytes"]))
    resource.setrlimit(resource.RLIMIT_FSIZE, (limits["max_output_bytes"], limits["max_output_bytes"]))


def _wait_with_job_limits(process: subprocess.Popen, limits: dict) -> int:
    deadline = time.monotonic() + limits["wall_time_seconds"]
    while True:
        result = process.poll()
        if result is not None:
            return result
        if time.monotonic() >= deadline:
            raise _RuntimeLimitExceeded(exit_code=124, reason="wall_time_exceeded")
        time.sleep(0.05)


def _terminate(process: subprocess.Popen, *, grace_seconds: float = 5.0) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=grace_seconds)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def _atomic_json(path: Path, value: object) -> None:
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()
    _atomic_bytes(path, raw)


def _atomic_bytes(path: Path, raw: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _atomic_text(path: Path, value: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("x", encoding="ascii") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
