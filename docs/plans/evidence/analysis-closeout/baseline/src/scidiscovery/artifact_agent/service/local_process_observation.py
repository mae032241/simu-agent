"""Optional stdlib launcher, executed by the Local Worker, never by the service.

Copied unchanged to tools/ in an analysis workspace. Records are observations,
not execution attestations or requirements for scientific submission.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import re
import resource
import selectors
import signal
import subprocess
import sys
import time
import uuid

RECORD_DIR = Path("scratch/.analysis-process")
LOG_LIMIT = 128 * 1024
MEMORY_LIMIT = 512 * 1024 * 1024


def normalize_log(raw, workspace):
    text = raw.decode("utf-8")
    text = text.replace(str(workspace) + "/", "")
    text = re.sub(r'(?<![\w])(?:/[\w.~-]+){2,}[^\s\"\']*|[A-Za-z]:\\[^\s\"\']+',
                  "[host-path]", text)
    return ("[normalized log copy; original retained]\n" + text).encode("utf-8")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _read_json(path, limit=16 * 1024):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError("observation unavailable")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("observation exceeds limit")
    return json.loads(raw)


def _write(path, value):
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w") as stream:
        json.dump(value, stream, allow_nan=False)
        stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


def effective_timeout(workspace, requested, reserve):
    """Recompute from control's absolute deadline at *this* launch, not open."""
    if not math.isfinite(requested) or requested <= 0 or not math.isfinite(reserve) or reserve < 0:
        raise ValueError("timeout must be positive and reserve nonnegative")
    try:
        assignment = _read_json(workspace / "assignment.json", 1024 * 1024)
        deadline = datetime.fromisoformat(assignment["budget"]["deadline_at"].replace("Z", "+00:00"))
        if deadline.tzinfo is None:
            raise ValueError("deadline has no timezone")
    except (OSError, ValueError, KeyError, TypeError):
        return requested, "unavailable"
    remaining = deadline.timestamp() - time.time()
    return min(requested, max(0, remaining - reserve)), "run_deadline"


def _directory(workspace):
    directory = workspace / RECORD_DIR
    if (workspace / "scratch").is_symlink() or directory.is_symlink():
        raise ValueError("observation directory is not task-local")
    return directory


def read_summary(workspace):
    """Pure, bounded Root projection: no commands, script or log contents."""
    try:
        value = _read_json(_directory(workspace) / "latest.json")
        result = {"coverage": "local_launcher", "scientific_evidence": False}
        for key in ("started_at", "ended_at"):
            item = value.get(key)
            result[key] = item if isinstance(item, str) and re.fullmatch(r"[0-9TZ:+.\-]{1,40}", item) else None
        for key in ("elapsed_seconds", "effective_timeout_seconds", "exit_code", "peak_rss_kib"):
            item = value.get(key)
            result[key] = item if type(item) in (int, float) and math.isfinite(item) else None
        for key in ("timed_out", "cancelled", "logs_truncated", "process_group_stopped"):
            result[key] = value.get(key) if type(value.get(key)) is bool else None
        for key, allowed in {"state": {"running", "finished", "not_started"},
            "budget_source": {"run_deadline", "unavailable"},
            "reason": {"insufficient_budget", "launch_failed", "interrupted", None}}.items():
            item = value.get(key)
            result[key] = item if isinstance(item, (str, type(None))) and item in allowed else None
        return result
    except (OSError, ValueError, TypeError, AttributeError):
        return {"coverage": "unobserved", "scientific_evidence": False}


def request_stop(workspace):
    """Fence launches and ask a managed launcher to stop; never trust a file PID."""
    try:
        directory = _directory(workspace)
        directory.mkdir(exist_ok=True, mode=0o700)
        path = directory / "stop"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        os.close(fd)
        until = time.monotonic() + 1
        while read_summary(workspace).get("state") == "running" and time.monotonic() < until:
            time.sleep(.02)
    except (OSError, ValueError):
        pass  # Unknown stop means preserve the original directory.


def _limits():
    current = resource.getrlimit(resource.RLIMIT_AS)[1]
    limit = MEMORY_LIMIT if current == resource.RLIM_INFINITY else min(MEMORY_LIMIT, current)
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))


def _group_exists(pgid):
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False


def _stop_group(process):
    for sig in (signal.SIGTERM, signal.SIGKILL):
        if not _group_exists(process.pid):
            break
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            break
        until = time.monotonic() + .2
        while time.monotonic() < until and _group_exists(process.pid):
            process.poll(); time.sleep(.01)
    process.wait(timeout=1)
    return not _group_exists(process.pid)


def run(workspace, script, arguments=(), *, timeout, submission_reserve=120):
    """Run one task-local Python script; capture bounded logs incrementally."""
    workspace = Path(workspace).absolute()
    scratch = workspace / "scratch"
    relative = Path(script)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("script must be relative to scratch/")
    source = scratch / relative
    if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(scratch.resolve()):
        raise ValueError("script must be a regular task-local file")
    directory = _directory(workspace); directory.mkdir(exist_ok=True, mode=0o700)
    lock_fd = os.open(directory / "lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        seconds, budget_source = effective_timeout(workspace, timeout, submission_reserve)
        record = dict(state="not_started", started_at=None, ended_at=None,
            effective_timeout_seconds=seconds, budget_source=budget_source,
            timed_out=False, cancelled=False, process_group_stopped=None)
        if seconds <= 0 or (directory / "stop").exists():
            record.update(reason="insufficient_budget" if seconds <= 0 else "interrupted", ended_at=_now())
            _write(directory / "latest.json", record)
            return 124
        started = time.monotonic()
        record.update(state="running", started_at=_now())
        name = uuid.uuid4().hex
        _write(directory / "latest.json", record)
        process = None
        raw_logs = {}
        truncated = False
        rc = 1
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1"}
        try:
            process = subprocess.Popen([sys.executable, "-B", str(relative), *arguments], cwd=scratch,
                env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                start_new_session=True, preexec_fn=_limits)
            with selectors.DefaultSelector() as selector:
                for key, pipe in (("stdout", process.stdout), ("stderr", process.stderr)):
                    os.set_blocking(pipe.fileno(), False)
                    selector.register(pipe, selectors.EVENT_READ, key)
                    raw_logs[key] = (directory / (name + "." + key + ".raw")).open("xb")
                while selector.get_map() or process.poll() is None:
                    if time.monotonic() - started >= seconds or (directory / "stop").exists():
                        record.update(timed_out=time.monotonic() - started >= seconds,
                            cancelled=(directory / "stop").exists())
                        record["process_group_stopped"] = _stop_group(process)
                        break
                    if process.poll() is not None and _group_exists(process.pid):
                        record["process_group_stopped"] = _stop_group(process)
                    for key, _ in selector.select(.02):
                        data = os.read(key.fileobj.fileno(), 8192)
                        if not data:
                            selector.unregister(key.fileobj); key.fileobj.close(); continue
                        log = raw_logs[key.data]
                        available = max(0, LOG_LIMIT - log.tell())
                        log.write(data[:available]); truncated |= len(data) > available
                if process.poll() is None:
                    try:
                        process.wait(timeout=max(.001, seconds - (time.monotonic() - started)))
                    except subprocess.TimeoutExpired:
                        record["timed_out"] = True
                record["process_group_stopped"] = _stop_group(process)
                rc = 124 if record["timed_out"] or record["cancelled"] else process.returncode
        except (OSError, ValueError, KeyboardInterrupt):
            record["reason"] = "interrupted" if process else "launch_failed"
        finally:
            if process:
                record["process_group_stopped"] = _stop_group(process)
                for pipe in (process.stdout, process.stderr):
                    pipe.close()
            for log in raw_logs.values():
                log.close()
                raw_path = Path(log.name)
                raw = raw_path.read_bytes()  # Bounded during capture, at most LOG_LIMIT.
                try:
                    normalized = normalize_log(raw, workspace)
                    if truncated:
                        normalized += b"\n[log truncated at capture limit]\n"
                    raw_path.with_suffix(".log").write_bytes(normalized)
                except (OSError, UnicodeError):
                    pass
            record.update(state="finished", ended_at=_now(), elapsed_seconds=time.monotonic()-started,
                exit_code=process.returncode if process else None, logs_truncated=truncated,
                peak_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss if sys.platform.startswith("linux") else None)
            _write(directory / (name + ".json"), record)
            _write(directory / "latest.json", record)
        return rc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, required=True)
    parser.add_argument("--submission-reserve", type=float, default=120)
    parser.add_argument("script")
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    return run(Path(__file__).resolve().parents[1], args.script, args.arguments,
        timeout=args.timeout, submission_reserve=args.submission_reserve)


if __name__ == "__main__":
    sys.exit(main())
