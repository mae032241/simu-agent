"""Identity reuse is simulated; real cleanup touches only fixture children."""
import json
import os
from pathlib import Path
import signal
import sys
import time

import pytest

from scripts import compiled_worker_process_guard as guard
from scripts import run_tests


def record(pid, start, *, parent=1, rss=10, group=1, session=1, boot="boot"):
    return guard._ProcessRecord(guard.ProcessIdentity(pid, boot, start), parent, rss, group, session)


def no_group_signal(*args):
    pytest.fail("a numeric process group is not proof of ownership")


def test_proc_stat_identity_and_rss_allow_parentheses_in_comm(monkeypatch):
    fields = ["0"] * 22
    for index, value in {0: "S", 1: "11", 2: "101", 3: "101", 19: "7", 21: "13"}.items():
        fields[index] = value
    monkeypatch.setattr(guard.Path, "read_text", lambda *args: "101 (fixture (odd) name) " + " ".join(fields))
    value = guard._process_record(101, "boot")
    assert value.identity == guard.ProcessIdentity(101, "boot", 7)
    assert value.parent_pid == 11 and value.process_group == value.session == 101
    assert value.resident_kib == 13 * os.sysconf("SC_PAGE_SIZE") // 1024


@pytest.mark.parametrize("replacement", [None, guard.ProcessIdentity(101, "boot", 8),
                                        guard.ProcessIdentity(101, "other-boot", 7)])
def test_cleanup_never_signals_reused_or_missing_identities(monkeypatch, replacement):
    original = guard.ProcessIdentity(101, "boot", 7)
    unrelated = record(101, 8, group=101, session=101)
    unrelated_child = record(102, 9, parent=101, group=101, session=101)
    monkeypatch.setattr(guard, "_process_table", lambda: {101: unrelated, 102: unrelated_child})
    monkeypatch.setattr(guard, "_process_identity", lambda pid: replacement)
    monkeypatch.setattr(guard.os, "killpg", no_group_signal)
    monkeypatch.setattr(guard.os, "kill", lambda *args: pytest.fail("signalled a replacement"))
    monkeypatch.setattr(guard.time, "sleep", lambda _: None)
    guard._cleanup_after_root_exit({original})


def test_cleanup_rechecks_identity_between_term_and_kill(monkeypatch):
    original = guard.ProcessIdentity(101, "boot", 7)
    current = original
    sent = []
    monkeypatch.setattr(guard, "_process_table", lambda: {})
    monkeypatch.setattr(guard, "_process_identity", lambda pid: current)
    monkeypatch.setattr(guard.os, "killpg", no_group_signal)
    monkeypatch.setattr(guard.time, "sleep", lambda _: None)
    def send(pid, signum):
        nonlocal current
        sent.append((pid, signum))
        current = guard.ProcessIdentity(pid, "boot", 8)
    monkeypatch.setattr(guard.os, "kill", send)
    guard._cleanup_after_root_exit({original})
    assert sent == [(101, signal.SIGTERM)]


def test_sampling_keeps_owned_orphans_and_excludes_recycled_roots(monkeypatch):
    root = guard.ProcessIdentity(101, "boot", 7)
    orphan = record(102, 8, rss=20, group=102, session=102)
    child = record(103, 9, parent=102, rss=30, group=102, session=102)
    replacement = record(101, 10, rss=100, group=101, session=101)
    unrelated = record(104, 11, parent=101, rss=200, group=101, session=101)
    monkeypatch.setattr(guard, "_process_table", lambda: {r.identity.pid: r for r in
                        (orphan, child, replacement, unrelated)})
    identities, rss = guard._descendant_rss_kib({root, orphan.identity})
    assert identities == {orphan.identity, child.identity}
    assert rss == 50


def test_only_original_unreaped_leader_can_anchor_reparented_group(monkeypatch):
    root = record(101, 7, group=101, session=101)
    orphan = record(102, 8, group=101, session=101)
    unrelated_session = record(103, 9, group=101, session=103)
    monkeypatch.setattr(guard, "_process_table", lambda: {r.identity.pid: r for r in
                        (root, orphan, unrelated_session)})
    assert guard._descendant_rss_kib({root.identity}) == ({root.identity, orphan.identity}, 20)
    assert guard._descendant_rss_kib({guard.ProcessIdentity(101, "boot", 6)}) == (set(), 0)


@pytest.mark.process_e2e
def test_spawn_cancellation_waits_for_owned_identity(tmp_path, monkeypatch):
    original = run_tests._process_identity
    owned = set()
    def capture(pid):
        signal.raise_signal(signal.SIGTERM)
        identity = original(pid)
        assert identity is not None
        owned.add(identity)
        return identity
    monkeypatch.setattr(run_tests, "_process_identity", capture)
    limits = json.loads(run_tests.DEFAULT_CONFIG.read_text())["limits"]
    limits.update(minimum_available_bytes=1, termination_grace_seconds=.2)
    try:
        with (tmp_path / "inherited").open("w") as lock:
            with pytest.raises(run_tests.SupervisorInterrupted):
                run_tests.run_one([sys.executable, "-c", "import time;time.sleep(30)"],
                    dict(os.environ), limits, tmp_path, lock.fileno())
        result = json.loads((tmp_path / "resource.json").read_text())
        assert result["stop_reason"] == "interrupted" and result["cleanup_complete"]
        assert result["returncode"] == -signal.SIGTERM
    finally:
        guard._signal_processes(owned, signal.SIGKILL)


@pytest.mark.process_e2e
@pytest.mark.parametrize("supervisor", ["test_runner", "compiled_finally", "compiled_memory"])
def test_cleanup_captures_child_created_after_last_sample(tmp_path, monkeypatch, supervisor):
    identity_path, ready, trigger = (tmp_path / name for name in ("identity.json", "ready", "trigger"))
    script = """
import json,signal,subprocess,sys,time
from pathlib import Path
from scripts.compiled_worker_process_guard import _process_identity
identity,ready,trigger=map(Path,sys.argv[1:])
def spawn():
    child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    identity.write_text(json.dumps(_process_identity(child.pid)))
def term(*args):
    spawn()
    raise SystemExit(0)
signal.signal(signal.SIGTERM,term)
ready.touch()
while True:
    if trigger.exists() and not identity.exists():spawn()
    time.sleep(.005)
"""
    command = [sys.executable, "-c", script, str(identity_path), str(ready), str(trigger)]
    original_sample, original_signal = guard._descendant_rss_kib, guard._signal_processes
    injected = False
    def sample(owned):
        nonlocal injected
        identities, rss = original_sample(owned)
        if ready.exists():
            if supervisor == "compiled_memory":
                return identities, 129 * 1024
            if not injected:
                injected = True
                raise ValueError("sampler_failed_before_cleanup")
        return identities, rss
    def send(identities, signum):
        if signum == signal.SIGKILL and not trigger.exists():
            # Create the child after the final memory sample but before KILL.
            trigger.touch()
            deadline = time.monotonic() + 3
            while not identity_path.exists():
                assert time.monotonic() < deadline, "fixture did not fork before KILL"
                time.sleep(.005)
        original_signal(identities, signum)
    monkeypatch.setattr(guard.os, "killpg", no_group_signal)
    try:
        if supervisor == "test_runner":
            limits = json.loads(run_tests.DEFAULT_CONFIG.read_text())["limits"]
            limits.update(minimum_available_bytes=1, timeout_seconds=.3,
                          sample_interval_seconds=.02, termination_grace_seconds=.5)
            with (tmp_path / "inherited").open("w") as lock:
                result = run_tests.run_one(command, dict(os.environ), limits, tmp_path, lock.fileno())
            assert result["stop_reason"] == "timeout" and result["cleanup_complete"]
        else:
            monkeypatch.setattr(guard, "_descendant_rss_kib", sample)
            if supervisor == "compiled_memory":
                monkeypatch.setattr(guard, "_signal_processes", send)
                code, _, exceeded = guard.run_process_group(command, dict(os.environ),
                    aggregate_memory_limit_mib=128, sample_interval_seconds=.02)
                assert code == guard.MEMORY_LIMIT_EXIT_CODE and exceeded
            else:
                with pytest.raises(ValueError, match="sampler_failed_before_cleanup"):
                    guard.run_process_group(command, dict(os.environ),
                        aggregate_memory_limit_mib=128, sample_interval_seconds=.02)
        identity = guard.ProcessIdentity(*json.loads(identity_path.read_text()))
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            try:
                state = Path(f"/proc/{identity.pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
            except FileNotFoundError:
                break
            if state == "Z":
                break
            time.sleep(.01)
        else:
            pytest.fail("child created during cleanup outlived its root")
    finally:
        if identity_path.exists():
            original_signal({guard.ProcessIdentity(*json.loads(identity_path.read_text()))}, signal.SIGKILL)


@pytest.mark.process_e2e
@pytest.mark.parametrize("supervisor", ["compiled", "test_runner"])
def test_short_lived_root_cleans_child_born_between_samples(tmp_path, monkeypatch, supervisor):
    # The root and ordinary child both appear after the initial sample. Capture
    # the child while the original session leader is still unreaped.
    identity_path = tmp_path / "identity.json"
    script = """
import json,subprocess,sys,time
from pathlib import Path
from scripts.compiled_worker_process_guard import _process_identity
time.sleep(.08)
child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
Path(sys.argv[1]).write_text(json.dumps(_process_identity(child.pid)))
"""
    monkeypatch.setattr(guard.os, "killpg", no_group_signal)
    try:
        command = [sys.executable, "-c", script, str(identity_path)]
        if supervisor == "compiled":
            code, _, exceeded = guard.run_process_group(command, dict(os.environ),
                aggregate_memory_limit_mib=128, sample_interval_seconds=.3)
            assert code == 0 and not exceeded
        else:
            limits = json.loads(run_tests.DEFAULT_CONFIG.read_text())["limits"]
            limits.update(sample_interval_seconds=.3, minimum_available_bytes=1)
            with (tmp_path / "inherited").open("w") as lock:
                result = run_tests.run_one(command, dict(os.environ), limits, tmp_path, lock.fileno())
            assert result["returncode"] == 0 and result["cleanup_complete"]
            assert result["observed_tree_rss_high_water_bytes"] > 0
        identity = guard.ProcessIdentity(*json.loads(identity_path.read_text()))
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            try:
                state = Path(f"/proc/{identity.pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
            except FileNotFoundError:
                break
            if state == "Z":
                break
            time.sleep(.01)
        else:
            pytest.fail("ordinary child outlived its completed root")
    finally:
        if identity_path.exists():
            identity = guard.ProcessIdentity(*json.loads(identity_path.read_text()))
            guard._signal_processes({identity}, signal.SIGKILL)
