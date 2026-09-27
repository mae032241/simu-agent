"""One serial test/build process tree; stop it before resource overruns spread."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import psutil

prefix = Path(sys.argv[1])
seconds = int(sys.argv[2])
command = sys.argv[3:]
limit = 512 * 1024 * 1024
env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", OPENBLAS_NUM_THREADS="1",
    OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
prefix.parent.mkdir(parents=True, exist_ok=True)
started = time.monotonic()
peak = 0
peak_processes = []
reason = None
known = {}
with prefix.with_suffix(".log").open("wb") as log:
    child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
        env=env, start_new_session=True)
    leader = psutil.Process(child.pid)
    while True:
        try:
            current = [leader, *leader.children(recursive=True)]
        except psutil.Error:
            current = []
        for process in current:
            known[process.pid] = process
        rss = 0
        live = []
        sample = []
        for process in known.values():
            try:
                if process.is_running() and process.status() != psutil.STATUS_ZOMBIE:
                    resident = process.memory_info().rss
                    rss += resident
                    sample.append({"name": process.name(), "rss_mib": round(resident / 1024 / 1024, 2)})
                    live.append(process)
            except psutil.Error:
                pass
        if rss > peak:
            peak = rss
            peak_processes = sorted(sample, key=lambda value: value["rss_mib"], reverse=True)[:12]
        if rss > limit or time.monotonic() - started > seconds:
            reason = "memory_budget_exceeded" if rss > limit else "wall_budget_exceeded"
            break
        if child.poll() is not None and not live:
            break
        time.sleep(.1)
    if reason:
        for process in reversed(live):
            try:
                process.kill()
            except psutil.Error:
                pass
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    code = child.wait()
record = {"command": command, "exit_code": code, "stop_reason": reason,
    "duration_seconds": round(time.monotonic()-started, 3),
    "peak_tree_rss_mib": round(peak/1024/1024, 2), "budget_mib": 512,
    "peak_processes": peak_processes}
prefix.with_suffix(".json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record))
sys.exit(124 if reason else code)
