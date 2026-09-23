"""Optional stdlib launcher, executed by the Local Worker, never by the service.

Copied unchanged to tools/ in an analysis workspace. Records are observations,
not execution attestations or requirements for scientific submission.
"""
from __future__ import annotations

import argparse
import builtins
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
ERROR_TYPES = frozenset(name for name, value in vars(builtins).items()
    if isinstance(value, type) and issubclass(value, BaseException))


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


def _project_record(value):
    result = {}
    for key in ("started_at", "ended_at", "first_started_at"):
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
    kind = value.get("error_type")
    result["error_type"] = kind if isinstance(kind, str) and kind in ERROR_TYPES else None
    for key in ("stdout_log", "stderr_log"):
        item = value.get(key)
        result[key] = item if isinstance(item, str) and re.fullmatch(
            r"scratch/\.analysis-process/[0-9a-f]{32}\.(stdout|stderr)\.log", item) else None
    return result


def read_summary(workspace):
    """Pure, bounded Root projection: no commands, script or log contents."""
    try:
        path = _directory(workspace) / "latest.json"
        if not path.exists() and not path.is_symlink():
            return {"coverage": "unobserved", "scientific_evidence": False,
                "reason": "no_records" if (Path(workspace) / "tools/local_process_observation.py").is_file() else "not_installed"}
        value = _read_json(path)
        result = {"coverage": "local_launcher", "scientific_evidence": False, "observation_status": "available", **_project_record(value)}
        for key in ("attempt_count", "error_count", "total_stdout_bytes", "total_stderr_bytes"):
            item = value.get(key)
            result[key] = item if type(item) is int and 0 <= item <= 2**63 - 1 else 0
        history = value.get("recent_errors", [])
        result["recent_errors"] = [_project_record(item) for item in history[-8:] if isinstance(item, dict)] if isinstance(history, list) else []
        if "recent_errors" not in value and _failed(result):
            # Legacy launchers only retained the latest observation, not counts.
            result.update(recent_errors=[_project_record(value)], error_count=1)
        return result
    except (OSError, ValueError, TypeError, AttributeError) as error:
        return {"coverage": "unobserved", "scientific_evidence": False,
            "reason": "record_read_failed", "error_type": type(error).__name__}


def materialize_launcher(workspace, *, analysis_policy=False):
    """Control-only preparation; the copied launcher remains stdlib-only."""
    from .local_workspace import write_control_workspace_file
    root = Path(workspace)
    (root / "scratch").mkdir(exist_ok=True, mode=0o700)
    tool = Path("tools/local_process_observation.py")
    if not (root / tool).exists():
        write_control_workspace_file(root, tool, Path(__file__).read_bytes(),
            replace=False, mode=0o400, create_parents=True)
    write_control_workspace_file(root, Path("tools/local_process_policy.json"),
        json.dumps({"policy": "analysis" if analysis_policy else "inherit"}).encode(),
        replace=True, mode=0o400, create_parents=True)
    return tool.as_posix()


def _failed(record):
    return record.get("exit_code") not in (0, None) or record.get("timed_out") or record.get("cancelled") or record.get("reason")


def _save_finished(directory, name, record):
    if _failed(record):
        record["error_count"] += 1
        record["recent_errors"] = [*record["recent_errors"], _project_record(record)][-8:]
    _write(directory / (name + ".json"), record)
    _write(directory / "latest.json", record)


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


def display_summary(workspace, name, record, *, return_code):
    """Worker display only; the existing on-disk observation remains the original."""
    result = {"state": record["state"], "return_code": return_code,
        "exit_code": record.get("exit_code"), "timed_out": record["timed_out"],
        "cancelled": record["cancelled"], "elapsed_seconds": record.get("elapsed_seconds"),
        "reason": record.get("reason"), "error_type": record.get("error_type"),
        "record_path": str(RECORD_DIR / (name + ".json")), "streams": {}}
    for key in ("stdout", "stderr"):
        total = record.get("launch_" + key + "_bytes", 0)
        saved = record.get("saved_" + key + "_bytes", 0)
        path = record.get(key + "_log")
        excerpts = []
        if path:
            # Only normalized, already retained logs; never retry the command for text.
            for line_no, line in enumerate((workspace / path).read_text().splitlines(), 1):
                if re.search(r"Traceback|Error|Exception|warning|failed", line, re.I):
                    fragment = line[:320]
                    excerpts.append({"line": line_no, "text": fragment, "line_truncated": len(line) > 320})
                    if len(excerpts) == 3:
                        break
        displayed = sum(len(item["text"].encode("utf-8")) for item in excerpts)
        result["streams"][key] = {"total_bytes": total, "saved_bytes": saved,
            "capture_truncated": total > saved, "displayed_normalized_bytes": displayed,
            "display_is_excerpt": True, "log_path": path,
            "raw_path": str(RECORD_DIR / (name + "." + key + ".raw")) if (workspace / RECORD_DIR / (name + "." + key + ".raw")).is_file() else None,
            "excerpts": excerpts}
    result["cause"] = "inspect referenced logs; snippets are not a root-cause diagnosis"
    payload = json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
    # Quotes/control characters may expand. Keep paths/coverage; omit excerpts explicitly.
    if len(payload.encode()) > 8192:
        for stream in result["streams"].values():
            stream.update(excerpts=[], displayed_normalized_bytes=0, excerpts_omitted="reply_budget")
        payload = json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
    sys.stdout.write(payload)


def run(workspace, script, arguments=(), *, timeout, submission_reserve=None, command=False, policy="analysis", display=None):
    """Observe Worker execution; argv mode has the same native permissions."""
    display = display or ("summary" if policy == "analysis" else "raw")
    if display not in {"summary", "raw"}:
        raise ValueError("display must be summary or raw")
    if submission_reserve is None:
        submission_reserve = 120 if policy == "analysis" else 0
    workspace = Path(workspace).absolute()
    scratch = workspace / "scratch"
    if command:
        argv, cwd = [script, *arguments], workspace
    else:
        relative = Path(script)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("script must be relative to scratch/")
        source = scratch / relative
        if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(scratch.resolve()):
            raise ValueError("script must be a regular task-local file")
        argv, cwd = [sys.executable, "-B", str(relative), *arguments], scratch
    directory = _directory(workspace); directory.mkdir(exist_ok=True, mode=0o700)
    lock_fd = os.open(directory / "lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        previous = read_summary(workspace)
        name = uuid.uuid4().hex
        seconds, budget_source = effective_timeout(workspace, timeout, submission_reserve)
        record = dict(state="not_started", started_at=None, ended_at=None,
            effective_timeout_seconds=seconds, budget_source=budget_source,
            timed_out=False, cancelled=False, process_group_stopped=None)
        record.update({key: previous.get(key, 0) for key in
            ("attempt_count", "error_count", "total_stdout_bytes", "total_stderr_bytes")})
        record.update(attempt_count=record["attempt_count"] + 1,
            first_started_at=previous.get("first_started_at"), recent_errors=previous.get("recent_errors", []))
        if seconds <= 0 or (directory / "stop").exists():
            record.update(reason="insufficient_budget" if seconds <= 0 else "interrupted", ended_at=_now())
            _save_finished(directory, name, record)
            if display == "summary":
                display_summary(workspace, name, record, return_code=124)
            return 124
        started = time.monotonic()
        record.update(state="running", started_at=_now())
        record["first_started_at"] = record["first_started_at"] or record["started_at"]
        _write(directory / "latest.json", record)
        process = None
        raw_logs = {}
        truncated = False
        rc = 1
        env = dict(os.environ)
        if policy == "analysis":
            env.update(PYTHONDONTWRITEBYTECODE="1", OPENBLAS_NUM_THREADS="1",
                OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
        try:
            process = subprocess.Popen(argv, cwd=cwd,
                env=env, stdin=subprocess.DEVNULL if policy == "analysis" else None,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                start_new_session=True, preexec_fn=_limits if policy == "analysis" else None)
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
                    if policy == "analysis" and process.poll() is not None and _group_exists(process.pid):
                        record["process_group_stopped"] = _stop_group(process)
                    for key, _ in selector.select(.02):
                        data = os.read(key.fileobj.fileno(), 8192)
                        if not data:
                            selector.unregister(key.fileobj); key.fileobj.close(); continue
                        log = raw_logs[key.data]
                        available = max(0, LOG_LIMIT - log.tell())
                        log.write(data[:available]); truncated |= len(data) > available
                        record["total_" + key.data + "_bytes"] += len(data)
                        field = "launch_" + key.data + "_bytes"
                        record[field] = record.get(field, 0) + len(data)
                        if command and display == "raw" and (available or policy != "analysis"):
                            stream = sys.stdout.buffer if key.data == "stdout" else sys.stderr.buffer
                            stream.write(data[:available] if policy == "analysis" else data); stream.flush()
                if process.poll() is None:
                    try:
                        process.wait(timeout=max(.001, seconds - (time.monotonic() - started)))
                    except subprocess.TimeoutExpired:
                        record["timed_out"] = True
                if policy == "analysis" or record["timed_out"] or record["cancelled"]:
                    record["process_group_stopped"] = _stop_group(process)
                rc = 124 if record["timed_out"] or record["cancelled"] else process.returncode
        except (OSError, ValueError, KeyboardInterrupt) as error:
            record["reason"] = "interrupted" if process else "launch_failed"
            record["error_type"] = type(error).__name__
            if not process:
                raw_logs["stderr"] = (directory / (name + ".stderr.raw")).open("xb")
                raw = (type(error).__name__ + ": " + str(error) + "\n").encode("utf-8")[:LOG_LIMIT]
                raw_logs["stderr"].write(raw)
                record["total_stderr_bytes"] += len(raw)
                record["launch_stderr_bytes"] = len(raw)
                if command and display == "raw":
                    sys.stderr.buffer.write(raw); sys.stderr.buffer.flush()
        finally:
            if process:
                if policy == "analysis" or process.poll() is None:
                    record["process_group_stopped"] = _stop_group(process)
                for pipe in (process.stdout, process.stderr):
                    pipe.close()
            for key, log in raw_logs.items():
                log.close()
                raw_path = Path(log.name)
                raw = raw_path.read_bytes()  # Bounded during capture, at most LOG_LIMIT.
                record["saved_" + key + "_bytes"] = len(raw)
                if key == "stderr":
                    kinds = re.findall(rb"(?m)^([A-Za-z]+):", raw)
                    record["error_type"] = next((kind.decode() for kind in reversed(kinds)
                        if kind.decode() in ERROR_TYPES), record.get("error_type"))
                try:
                    normalized = normalize_log(raw, workspace)
                    if truncated:
                        normalized += b"\n[log truncated at capture limit]\n"
                    raw_path.with_suffix(".log").write_bytes(normalized)
                    record[key + "_log"] = raw_path.with_suffix(".log").relative_to(workspace).as_posix()
                except (OSError, UnicodeError):
                    pass
            record.update(state="finished", ended_at=_now(), elapsed_seconds=time.monotonic()-started,
                exit_code=process.returncode if process else None, logs_truncated=truncated,
                peak_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss if sys.platform.startswith("linux") else None)
            _save_finished(directory, name, record)
        if display == "summary":
            display_summary(workspace, name, record, return_code=rc)
        return rc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, required=True)
    parser.add_argument("--submission-reserve", type=float, default=None)
    parser.add_argument("--display", choices=("summary", "raw"), default=None,
        help="Analysis defaults to a short observation; raw preserves stdout consumers.")
    parser.add_argument("--command", action="store_true",
        help="Run an argv command from the workspace root and return a short observation (or explicit raw stdout/stderr).")
    parser.add_argument("script")
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parents[1]
    policy_file = workspace / "tools/local_process_policy.json"
    policy = _read_json(policy_file).get("policy", "analysis") if policy_file.exists() else "analysis"
    return run(workspace, args.script, args.arguments, timeout=args.timeout,
        submission_reserve=args.submission_reserve, command=args.command, policy=policy, display=args.display)


if __name__ == "__main__":
    sys.exit(main())
