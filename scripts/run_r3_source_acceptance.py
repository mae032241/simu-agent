"""Serial, explicitly enabled source checks; default only prints the reviewed plan."""
from __future__ import annotations

import argparse
import ast
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import tempfile
import time

from compiled_worker_process_guard import _descendant_rss_kib, _signal_processes


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "scripts/r3_source_acceptance.json"


def run_one(command, environment, limits, log):
    """RLIMIT_AS is per process; RSS sampling is only an additional emergency stop."""
    def restrict():
        resource.setrlimit(resource.RLIMIT_AS, (limits["address_space_bytes"],) * 2)
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    def memory():
        fields = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
        return {key: int(fields[key].split()[0]) * 1024 for key in ("MemAvailable", "Dirty")}
    baseline = memory()
    if baseline["MemAvailable"] < 8 * 1024**3 or baseline["Dirty"] > 128 * 1024**2:
        return {"returncode": None, "stop_reason": "system_memory_admission", "elapsed_seconds": 0,
            "observed_tree_rss_high_water_bytes": 0}
    start = time.monotonic()
    process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=log,
        stderr=subprocess.STDOUT, start_new_session=True, preexec_fn=restrict)
    observed, high_water, reason = set(), 0, "exited"
    try:
        while process.poll() is None:
            descendants, rss = _descendant_rss_kib(process.pid)
            observed.update(descendants)
            high_water = max(high_water, rss * 1024)
            observed_memory = memory()
            if (observed_memory["MemAvailable"] < 8 * 1024**3
                    or baseline["MemAvailable"] - observed_memory["MemAvailable"] > 2_000_000_000
                    or observed_memory["Dirty"] > 128 * 1024**2):
                reason = "system_memory_stop"
                break
            if time.monotonic() - start >= limits["timeout_seconds"]:
                reason = "timeout"
                break
            if high_water > limits["observed_tree_rss_stop_bytes"]:
                reason = "observed_tree_rss_limit"
                break
            time.sleep(limits["sample_interval_seconds"])
    finally:
        # Also stop descendants left behind after a nominally successful parent.
        descendants, _ = _descendant_rss_kib(process.pid)
        observed.update(descendants)
        _signal_processes(process.pid, observed, signal.SIGTERM)
        if process.poll() is None:
            try:
                process.wait(timeout=limits["termination_grace_seconds"])
            except subprocess.TimeoutExpired:
                pass
        _signal_processes(process.pid, observed, signal.SIGKILL)
        process.wait()
    return {"returncode": process.returncode, "stop_reason": reason,
        "elapsed_seconds": round(time.monotonic() - start, 3),
        "observed_tree_rss_high_water_bytes": high_water}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--execute", action="store_true",
        help="Run only after the user explicitly authorizes these source checks")
    parser.add_argument("--output", type=Path,
        help="New result directory; required when executing, never overwrite a prior result")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    limits = config["limits"]
    if any(not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0
           for value in limits.values()):
        parser.error("all configured limits must be positive numbers")
    checks = config["checks"]
    if config["numeric_threads"] != 1:
        parser.error("this reviewed source lane requires numeric_threads=1")
    for check in checks:
        relative, selector = check["node"].split("::")
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT / "tests/operations") or not path.is_file():
            parser.error("only existing tests/operations files are admitted")
        function = selector.split("[", 1)[0]
        tree = ast.parse(path.read_text())
        if function not in {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}:
            parser.error(f"test function missing: {check['node']}")
    if not args.execute:
        print(json.dumps(config, ensure_ascii=False, indent=2))
        return 0
    if args.output is None:
        parser.error("--output is required with --execute")
    lock_name = "scid-r3-source-" + hashlib.sha256(str(ROOT).encode()).hexdigest()[:16] + ".lock"
    lock = (Path(tempfile.gettempdir()) / lock_name).open("a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        parser.error("another source acceptance runner owns the serial lock")
    def interrupted(signum, _frame):
        raise KeyboardInterrupt(f"received signal {signum}")
    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, interrupted)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    environment = dict(os.environ)
    for key in ("PYTHONPATH", "PYTEST_ADDOPTS", "PYTEST_PLUGINS", "SCIDISCOVERY_ROLE_DIR"):
        environment.pop(key, None)
    environment.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHONNOUSERSITE="1",
        PYTHONDONTWRITEBYTECODE="1", MPLBACKEND="Agg", MPLCONFIGDIR=str(output / "matplotlib"))
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS"):
        environment[key] = str(config["numeric_threads"])
    results = {"config": config, "python": sys.executable,
        "config_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
        "status": "running", "checks": []}
    result_file = output / "result.json"
    def save():
        result_file.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    save()
    for index, check in enumerate(checks, 1):
        command = [sys.executable, "-B", "-m", "pytest", "-q", "-x", "-o", "addopts=",
            "-p", "no:cacheprovider", "--basetemp", str(output / f"tmp-{index:02}"), check["node"]]
        print(f"[{index}/{len(checks)}] {check['node']}", flush=True)
        with (output / f"{index:02}.log").open("wb") as log:
            result = run_one(command, environment, limits, log)
        results["checks"].append({**check, "command": command, **result})
        failed = result["returncode"] != 0 or result["stop_reason"] != "exited"
        results["status"] = "failed" if failed else "running"
        save()
        if failed:
            return 1
    results["status"] = "passed"
    save()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
