"""Bound one local compiled Worker process tree and forward termination signals."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any


MEMORY_LIMIT_EXIT_CODE = 86


def _process_table() -> dict[int, tuple[int, int]]:
    """Return pid -> (parent pid, resident KiB) for the current /proc snapshot."""

    table: dict[int, tuple[int, int]] = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdecimal():
            continue
        parent_pid: int | None = None
        resident_kib = 0
        try:
            for line in (entry / "status").read_text("utf-8").splitlines():
                if line.startswith("PPid:"):
                    parent_pid = int(line.split()[1])
                elif line.startswith("VmRSS:"):
                    resident_kib = int(line.split()[1])
                if parent_pid is not None and resident_kib:
                    break
        except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError):
            continue
        if parent_pid is not None:
            table[int(entry.name)] = (parent_pid, resident_kib)
    return table


def _descendant_rss_kib(root_pid: int) -> tuple[set[int], int]:
    table = _process_table()
    children: dict[int, list[int]] = {}
    for pid, (parent_pid, _) in table.items():
        children.setdefault(parent_pid, []).append(pid)
    descendants: set[int] = set()
    pending = [root_pid]
    while pending:
        pid = pending.pop()
        if pid in descendants:
            continue
        descendants.add(pid)
        pending.extend(children.get(pid, ()))
    return descendants, sum(table.get(pid, (0, 0))[1] for pid in descendants)


def _signal_processes(process_group: int, pids: set[int], signum: int) -> None:
    try:
        os.killpg(process_group, signum)
    except ProcessLookupError:
        pass
    for pid in sorted(pids, reverse=True):
        try:
            os.kill(pid, signum)
        except ProcessLookupError:
            pass


def _cleanup_after_root_exit(process_group: int, observed_pids: set[int]) -> None:
    """Do not let background descendants outlive one completed Worker."""

    live_observed = {pid for pid in observed_pids if Path(f"/proc/{pid}").exists()}
    try:
        os.killpg(process_group, 0)
        group_exists = True
    except ProcessLookupError:
        group_exists = False
    if not live_observed and not group_exists:
        return
    _signal_processes(process_group, live_observed, signal.SIGTERM)
    time.sleep(0.05)
    live_observed = {
        pid for pid in live_observed if Path(f"/proc/{pid}").exists()
    }
    _signal_processes(process_group, live_observed, signal.SIGKILL)


def run_process_group(
    command: list[str],
    environment: dict[str, str],
    *,
    aggregate_memory_limit_mib: int,
    sample_interval_seconds: float = 0.1,
) -> tuple[int, int, bool]:
    """Run one process tree.

    Returns ``(exit_code, peak_tree_rss_kib, memory_limit_exceeded)``.  The
    /proc sampler is a trusted-local emergency brake, not an OS isolation
    boundary; production backends still need a cgroup or equivalent.
    """

    if aggregate_memory_limit_mib <= 0:
        raise ValueError("aggregate memory limit must be positive")
    if sample_interval_seconds <= 0:
        raise ValueError("sample interval must be positive")
    process = subprocess.Popen(command, env=environment, start_new_session=True)
    memory_limit_kib = aggregate_memory_limit_mib * 1024
    peak_rss_kib = 0
    memory_limit_exceeded = False
    termination_started: float | None = None
    previous: dict[int, Any] = {}
    observed_pids: set[int] = set()

    def forward(signum: int, _frame: Any) -> None:
        nonlocal termination_started
        if process.poll() is not None:
            return
        descendants, _ = _descendant_rss_kib(process.pid)
        if termination_started is None:
            termination_started = time.monotonic()
            _signal_processes(process.pid, descendants, signum)
        else:
            _signal_processes(process.pid, descendants, signal.SIGKILL)

    for signum in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        previous[signum] = signal.signal(signum, forward)
    try:
        while True:
            descendants, resident_kib = _descendant_rss_kib(process.pid)
            observed_pids.update(descendants)
            peak_rss_kib = max(peak_rss_kib, resident_kib)
            if resident_kib > memory_limit_kib:
                memory_limit_exceeded = True
                _signal_processes(process.pid, descendants, signal.SIGKILL)
                process.wait()
                _cleanup_after_root_exit(process.pid, observed_pids)
                return MEMORY_LIMIT_EXIT_CODE, peak_rss_kib, True
            try:
                return_code = process.wait(timeout=sample_interval_seconds)
                _cleanup_after_root_exit(process.pid, observed_pids)
                return return_code, peak_rss_kib, memory_limit_exceeded
            except subprocess.TimeoutExpired:
                if (
                    termination_started is not None
                    and time.monotonic() - termination_started >= 5
                ):
                    descendants, _ = _descendant_rss_kib(process.pid)
                    _signal_processes(process.pid, descendants, signal.SIGKILL)
    finally:
        if process.poll() is None:
            descendants, _ = _descendant_rss_kib(process.pid)
            _signal_processes(process.pid, descendants, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                descendants, _ = _descendant_rss_kib(process.pid)
                _signal_processes(process.pid, descendants, signal.SIGKILL)
                process.wait()
        for signum, handler in previous.items():
            signal.signal(signum, handler)


__all__ = ["MEMORY_LIMIT_EXIT_CODE", "run_process_group"]
