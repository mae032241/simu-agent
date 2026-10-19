"""Bound one local compiled Worker process tree and forward termination signals."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any, NamedTuple


MEMORY_LIMIT_EXIT_CODE = 86


class ProcessIdentity(NamedTuple):
    pid: int
    boot_id: str
    start_ticks: int


class _ProcessRecord(NamedTuple):
    identity: ProcessIdentity
    parent_pid: int
    resident_kib: int
    process_group: int
    session: int


def _process_record(pid: int, boot_id: str) -> _ProcessRecord | None:
    try:
        # comm may contain spaces and parentheses; stat fields follow its final ')'.
        fields = Path(f"/proc/{pid}/stat").read_text("utf-8").rsplit(")", 1)[1].split()
        return _ProcessRecord(
            ProcessIdentity(pid, boot_id, int(fields[19])),
            int(fields[1]), int(fields[21]) * os.sysconf("SC_PAGE_SIZE") // 1024,
            int(fields[2]), int(fields[3]),
        )
    except (OSError, ValueError, IndexError):
        return None


def _process_identity(pid: int) -> ProcessIdentity | None:
    boot_id = Path("/proc/sys/kernel/random/boot_id").read_text("utf-8").strip()
    record = _process_record(pid, boot_id)
    return record.identity if record else None


def _process_table() -> dict[int, _ProcessRecord]:
    """Return identities, parents and resident KiB from the current /proc snapshot."""

    boot_id = Path("/proc/sys/kernel/random/boot_id").read_text("utf-8").strip()
    table = {}
    for entry in Path("/proc").iterdir():
        if entry.name.isdecimal():
            record = _process_record(int(entry.name), boot_id)
            if record is not None:
                table[record.identity.pid] = record
    return table


def _descendant_rss_kib(owned: set[ProcessIdentity], *, diagnostic: dict | None = None) -> tuple[set[ProcessIdentity], int]:
    table = _process_table()
    children: dict[int, list[int]] = {}
    for pid, record in table.items():
        parent = table.get(record.parent_pid)
        if parent is not None and record.identity.start_ticks >= parent.identity.start_ticks:
            children.setdefault(record.parent_pid, []).append(pid)
    descendants: set[int] = set()
    # Observed descendants remain roots after reparenting. Reused PIDs never do.
    pending = [identity.pid for identity in tuple(owned)
               if identity.pid in table and table[identity.pid].identity == identity]
    # An unreaped original session leader also anchors ordinary children that
    # reparented before this sample. A recycled leader cannot anchor a group.
    for pid in tuple(pending):
        leader = table[pid]
        if leader.process_group == pid and leader.session == pid:
            pending.extend(member for member, record in table.items()
                           if record.process_group == pid and record.session == pid
                           and record.identity.start_ticks >= leader.identity.start_ticks)
    while pending:
        pid = pending.pop()
        if pid in descendants:
            continue
        descendants.add(pid)
        pending.extend(children.get(pid, ()))
    total = sum(table[pid].resident_kib for pid in descendants)
    if diagnostic is not None:
        ordered = sorted((table[pid] for pid in descendants), key=lambda item: (-item.resident_kib, item.identity.pid))
        diagnostic.clear()
        diagnostic.update(sampled_at_unix=time.time(), observed_tree_rss_kib=total,
            process_count=len(ordered), omitted_count=max(0, len(ordered)-16),
            processes=[dict(pid=item.identity.pid, boot_id=item.identity.boot_id, start_ticks=item.identity.start_ticks,
                parent_pid=item.parent_pid, resident_kib=item.resident_kib, process_group=item.process_group,
                session=item.session) for item in ordered[:16]],
            limitation='One /proc table pass of identity-bound observed descendants; sampled RSS is not a hard quota or inferred scientific call membership.')
    return ({table[pid].identity for pid in descendants}, total)


def _poll_process(process: subprocess.Popen, observed: set[ProcessIdentity]) -> int | None:
    """Observe the original leader's group before reaping releases its PID."""
    if process.returncode is None:
        exited = os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        if exited is None:
            return None
        descendants, _ = _descendant_rss_kib(observed)
        observed.update(descendants)
    return process.poll()


def _wait_process(
    process: subprocess.Popen, observed: set[ProcessIdentity], timeout: float | None = None,
) -> int:
    """Every reap path observes the original leader before releasing its PID."""
    deadline = None if timeout is None else time.monotonic() + timeout
    while True:
        return_code = _poll_process(process, observed)
        if return_code is not None:
            return return_code
        if deadline is not None and time.monotonic() >= deadline:
            raise subprocess.TimeoutExpired(process.args, timeout)
        time.sleep(.01 if deadline is None else min(.01, max(0., deadline - time.monotonic())))


def _signal_processes(identities: set[ProcessIdentity], signum: int) -> None:
    # Never signal a numeric group after its leader exits: that PGID can be reused.
    for identity in sorted(identities, reverse=True):
        if _process_identity(identity.pid) != identity:
            continue
        try:
            os.kill(identity.pid, signum)
        except ProcessLookupError:
            pass


def _cleanup_after_root_exit(observed: set[ProcessIdentity]) -> None:
    """Do not let observed background descendants outlive one completed Worker."""

    descendants, _ = _descendant_rss_kib(observed)
    observed.update(descendants)
    _signal_processes(observed, signal.SIGTERM)
    time.sleep(0.05)
    descendants, _ = _descendant_rss_kib(observed)
    observed.update(descendants)
    _signal_processes(observed, signal.SIGKILL)


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
    identity = _process_identity(process.pid)
    observed: set[ProcessIdentity] = {identity} if identity else set()

    def forward(signum: int, _frame: Any) -> None:
        nonlocal termination_started
        if process.returncode is not None:
            return
        descendants, _ = _descendant_rss_kib(observed)
        observed.update(descendants)
        if termination_started is None:
            termination_started = time.monotonic()
            _signal_processes(observed, signum)
        else:
            _signal_processes(observed, signal.SIGKILL)

    for signum in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        previous[signum] = signal.signal(signum, forward)
    try:
        while True:
            descendants, resident_kib = _descendant_rss_kib(observed)
            observed.update(descendants)
            peak_rss_kib = max(peak_rss_kib, resident_kib)
            if resident_kib > memory_limit_kib:
                memory_limit_exceeded = True
                _signal_processes(observed, signal.SIGKILL)
                _wait_process(process, observed)
                _cleanup_after_root_exit(observed)
                return MEMORY_LIMIT_EXIT_CODE, peak_rss_kib, True
            return_code = _poll_process(process, observed)
            if return_code is not None:
                _cleanup_after_root_exit(observed)
                return return_code, peak_rss_kib, memory_limit_exceeded
            if (
                termination_started is not None
                and time.monotonic() - termination_started >= 5
            ):
                descendants, _ = _descendant_rss_kib(observed)
                observed.update(descendants)
                _signal_processes(observed, signal.SIGKILL)
            time.sleep(sample_interval_seconds)
    finally:
        if process.returncode is None:
            descendants, _ = _descendant_rss_kib(observed)
            observed.update(descendants)
            _signal_processes(observed, signal.SIGTERM)
            try:
                _wait_process(process, observed, timeout=5)
            except subprocess.TimeoutExpired:
                descendants, _ = _descendant_rss_kib(observed)
                observed.update(descendants)
                _signal_processes(observed, signal.SIGKILL)
                _wait_process(process, observed)
            _cleanup_after_root_exit(observed)
        for signum, handler in previous.items():
            signal.signal(signum, handler)


__all__ = ["MEMORY_LIMIT_EXIT_CODE", "run_process_group"]
