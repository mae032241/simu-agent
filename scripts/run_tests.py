"""Run one explicit pytest lane serially, with bounded memory, logs and lifetime.

Linux RLIMIT_AS is a per-process hard ceiling. Tree RSS and system memory are
sampled emergency stops, not a cgroup aggregate hard limit or an OOM guarantee.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import resource
import selectors
import shutil
import signal
import subprocess
import sys
import time

from compiled_worker_process_guard import _descendant_rss_kib, _signal_processes

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "scripts/test_resources.json"
LANES = ("source", "installed", "process", "stress", "live")


def memory() -> dict[str, int]:
    fields = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
    return {key: int(fields[key].split()[0]) * 1024 for key in ("MemAvailable", "Dirty")}


def run_one(command, environment, limits, output, lock_fd):
    """Stream output to a capped log; always clean the child group and observed tree."""
    baseline = memory()
    if (baseline["MemAvailable"] < limits["minimum_available_bytes"]
            or baseline["Dirty"] > limits["dirty_stop_bytes"]):
        return {"returncode": None, "stop_reason": "system_memory_admission",
                "memory": baseline, "elapsed_seconds": 0, "observed_tree_rss_high_water_bytes": 0}

    def restrict():
        resource.setrlimit(resource.RLIMIT_AS, (limits["address_space_bytes"],) * 2)
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    started = time.monotonic()
    process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, start_new_session=True, preexec_fn=restrict, pass_fds=(lock_fd,))
    observed, peak, reason, written = set(), 0, "exited", 0
    current = baseline
    memory_triggers = []
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    os.set_blocking(process.stdout.fileno(), False)
    log = (output / "pytest.log").open("wb")
    try:
        while True:
            descendants, rss = _descendant_rss_kib(process.pid)
            observed.update(descendants)
            peak = max(peak, rss * 1024)
            current = memory()
            memory_triggers = [name for name, triggered in (
                ("available_below_minimum", current["MemAvailable"] < limits["minimum_available_bytes"]),
                ("available_drop", baseline["MemAvailable"] - current["MemAvailable"] > limits["available_drop_stop_bytes"]),
                ("dirty_above_limit", current["Dirty"] > limits["dirty_stop_bytes"]),
            ) if triggered]
            if memory_triggers:
                reason = "system_memory_stop"
                break
            if peak > limits["observed_tree_rss_stop_bytes"]:
                reason = "observed_tree_rss_limit"
                break
            if time.monotonic() - started >= limits["timeout_seconds"]:
                reason = "timeout"
                break
            fixture_bytes = sum(p.stat().st_size for p in (output / "fixture-logs").glob("*.log"))
            if fixture_bytes > limits["log_bytes"]:
                reason = "fixture_log_limit"
                break
            for key, _ in selector.select(limits["sample_interval_seconds"]):
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                remaining = max(0, limits["log_bytes"] - written)
                log.write(chunk[:remaining])
                written += len(chunk)
                if written > limits["log_bytes"]:
                    reason = "log_limit"
                    break
            if reason != "exited" or (process.poll() is not None and not selector.get_map()):
                break
    except BaseException:
        reason = "interrupted"
        raise
    finally:
        descendants, _ = _descendant_rss_kib(process.pid)
        observed.update(descendants)
        _signal_processes(process.pid, observed, signal.SIGTERM)
        try:
            process.wait(timeout=limits["termination_grace_seconds"])
        except subprocess.TimeoutExpired:
            pass
        # A successful/failed pytest can also leave a daemon or a new-session child.
        _signal_processes(process.pid, observed, signal.SIGKILL)
        process.wait()
        process.stdout.close()
        selector.close()
        log.close()
    return {"returncode": process.returncode, "stop_reason": reason,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "observed_tree_rss_high_water_bytes": peak,
            "system_memory_baseline": baseline, "system_memory_final": current,
            "memory_stop_triggers": memory_triggers}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lane", choices=LANES, default="source")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, required=True, help="new result directory, preferably /tmp")
    parser.add_argument("--collect-only", action="store_true")
    parser.add_argument("--per-file", action="store_true", help="fresh pytest process per test file; stops on failure")
    parser.add_argument("targets", nargs="*", help="pytest files or node IDs; defaults to tests")
    args = parser.parse_args()
    defaults = json.loads(DEFAULT_CONFIG.read_text())
    supplied = json.loads(args.config.read_text())
    config = {**defaults, **supplied, "limits": {**defaults["limits"], **supplied.get("limits", {})}}
    limits = config["limits"]
    required = defaults["limits"].keys()
    if set(limits) != set(required) or any(isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0
                                         for v in limits.values()):
        parser.error("resource config must contain exactly the documented positive limits")
    if not isinstance(limits["address_space_bytes"], int) or not isinstance(limits["log_bytes"], int):
        parser.error("address_space_bytes and log_bytes must be integers")
    if config["numeric_threads"] != 1:
        parser.error("numeric_threads must be 1; concurrent test workers are unsupported")
    if limits["observed_tree_rss_stop_bytes"] >= limits["address_space_bytes"]:
        parser.error("tree RSS emergency stop must be below the per-process address limit")
    if args.per_file and args.lane == "installed":
        parser.error("installed lane must share one session to reuse built wheels")
    targets = args.targets or ["tests"]
    for target in targets:
        path = (ROOT / target.split("::", 1)[0]).resolve()
        if not path.is_relative_to(ROOT / "tests") or not path.exists():
            parser.error(f"target must exist under tests/: {target}")
    batches = [targets]
    if args.per_file:
        expanded = []
        for target in targets:
            path = ROOT / target.split("::", 1)[0]
            if path.is_dir():
                expanded.extend(str(p.relative_to(ROOT)) for p in sorted(path.rglob("test_*.py")))
            else:
                expanded.append(target)
        batches = [[target] for target in dict.fromkeys(expanded)]
    lock_path = Path("/tmp") / f"scid-tests-{os.getuid()}.lock"
    with lock_path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("another pytest/runner owns this repository's serial lock")
        output = args.output.resolve()
        output.mkdir(parents=True, exist_ok=False)
        environment = dict(os.environ)
        for key in ("PYTHONPATH", "PYTEST_ADDOPTS", "PYTEST_PLUGINS", "SCIDISCOVERY_ROLE_DIR"):
            environment.pop(key, None)
        environment.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1",
            MPLBACKEND="Agg", SCID_TEST_LOCK_FD=str(lock.fileno()), SCID_TEST_GUARD="1")
        for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS"):
            environment[key] = "1"
        def interrupted(signum, _frame):
            raise KeyboardInterrupt(f"received signal {signum}")
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(signum, interrupted)
        results = {"lane": args.lane, "config": config, "status": "running", "batches": []}
        def save():
            (output / "result.json").write_text(json.dumps(results, indent=2) + "\n")
        save()
        try:
            for index, batch in enumerate(batches, 1):
                batch_output = output / f"batch-{index:03}"
                batch_output.mkdir()
                scratch = batch_output / "scratch"
                scratch.mkdir()
                environment.update(TMPDIR=str(scratch), SCID_TEST_LOG_DIR=str(batch_output / "fixture-logs"),
                    SCID_TEST_LOG_BYTES=str(limits["log_bytes"]), MPLCONFIGDIR=str(batch_output / "matplotlib"))
                command = [sys.executable, "-B", "-m", "pytest", "-q", "--tb=short", "-o", "addopts=",
                    "-p", "no:cacheprovider", "--test-lane", args.lane, "--basetemp", str(batch_output / "tmp")]
                if args.collect_only:
                    command.append("--collect-only")
                command.extend(batch)
                print(f"[{index}/{len(batches)}] {args.lane}: {' '.join(batch)}", flush=True)
                try:
                    result = run_one(command, environment, limits, batch_output, lock.fileno())
                finally:
                    shutil.rmtree(batch_output / "tmp", ignore_errors=True)
                    shutil.rmtree(scratch, ignore_errors=True)
                results["batches"].append({"targets": batch, **result})
                # Per-file selection can legitimately find only a different lane.
                passed = result["stop_reason"] == "exited" and (result["returncode"] == 0 or
                    (args.per_file and result["returncode"] == 5))
                results["status"] = "running" if passed else "failed"
                save()
                print(json.dumps(result), flush=True)
                if not passed:
                    return 1
        except BaseException:
            results["status"] = "interrupted"
            save()
            raise
        results["status"] = "passed"
        save()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
