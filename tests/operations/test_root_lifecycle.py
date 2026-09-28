"""Local lifecycle controls; these tests do not establish live Worker survival."""
from datetime import datetime, timedelta, timezone
import io
import os
import json
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path
import sqlite3
import sys
import time

import pytest

from scripts import probe_root_host_live as live
from scripts.probe_root_lifecycle import DISPATCH, READBACK, RECOVER, NAME, LifecycleHost, require_no_started_lifecycle, require_lifecycle_resume


@pytest.mark.process_e2e
def test_installed_codex_proxy_forwards_raw_jsonl_without_websocket_upgrade(tmp_path):
    executable = shutil.which("codex")
    if executable is None:
        pytest.skip("Codex unavailable")
    with tempfile.TemporaryDirectory(prefix="scid-wire-", dir="/tmp") as short, socket.socket(socket.AF_UNIX) as listener:
        path = Path(short) / "raw.sock"
        listener.bind(str(path))
        listener.listen(1)
        listener.settimeout(5)
        with (tmp_path / "proxy.log").open("wb") as log:
            peer = subprocess.Popen([executable, "app-server", "proxy", "--sock", str(path)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log)
            try:
                request = b'{"id":1,"method":"initialize","params":{}}\n'
                peer.stdin.write(request)
                peer.stdin.flush()
                connection, _ = listener.accept()
                with connection:
                    connection.settimeout(5)
                    data = b""
                    while b"\n" not in data:
                        chunk = connection.recv(4096)
                        assert chunk, "proxy closed before sending request"
                        data += chunk
                    assert data == request  # No HTTP GET/Upgrade handshake.
            finally:
                peer.terminate()
                peer.communicate(timeout=5)


@pytest.mark.live_platform
def test_real_app_server_websocket_initialize_disconnect_reconnect_without_model(tmp_path, monkeypatch):
    if shutil.which("codex") is None:
        pytest.skip("Codex unavailable")
    pytest.importorskip("aiohttp")
    logs = Path(os.environ["SCID_TEST_LOG_DIR"])
    logs.mkdir(exist_ok=True)
    monkeypatch.setenv("SCID_TEST_LOG_DIR", str(logs))
    with tempfile.TemporaryDirectory(prefix="scid-ws-", dir="/tmp") as short:
        root = Path(short)
        # Zero-model transport test: empty writable profile, no copied credentials.
        (root / "codex-home").mkdir()
        monkeypatch.setenv("CODEX_HOME", str(root / "codex-home"))
        live.write(root / "candidate.json", {"python": sys.executable, "project": short, "profile": {}})
        host = LifecycleHost(root, json.loads(live.guard.DEFAULT_CONFIG.read_text())["limits"])
        try:
            host.app = host.launch_app([])
            host.attach_connection()
            params = {"clientInfo": {"name": "scid_transport_test", "version": "0.1"}}
            initial = host.rpc("initialize", params)
            assert initial.get("userAgent")
            server_pid = host.server.pid
            host.disconnect_client()
            assert host.server.poll() is None
            host.app = host.connect_client("client-after")
            host.attach_connection()
            reconnected = host.rpc("initialize", params)
            assert reconnected.get("userAgent") == initial["userAgent"]
            assert host.server.pid == server_pid and host.server.poll() is None
            assert host.thread is None and host.usage == {}
        finally:
            host.close()
        assert all(child.poll() is not None for child in host.children)


@pytest.mark.process_e2e
def test_websocket_client_performs_upgrade_and_reconnects_to_same_peer(tmp_path, monkeypatch):
    pytest.importorskip("aiohttp")
    logs = Path(os.environ["SCID_TEST_LOG_DIR"])
    logs.mkdir(exist_ok=True)
    monkeypatch.setenv("SCID_TEST_LOG_DIR", str(logs))
    with tempfile.TemporaryDirectory(prefix="scid-ws-", dir="/tmp") as short:
        root = Path(short)
        live.write(root / "candidate.json", {"python": sys.executable, "project": short, "profile": {}})
        script = root / "peer.py"
        script.write_text('''import sys
from aiohttp import web
async def handle(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    async for message in ws:
        value = message.json()
        assert value["method"] == "initialize"
        await ws.send_json({"id":value["id"], "result":{"userAgent":"fixture"}})
    return ws
app = web.Application()
app.router.add_get("/", handle)
web.run_app(app, path=sys.argv[1], print=None)
''')
        host = LifecycleHost(root, json.loads(live.guard.DEFAULT_CONFIG.read_text())["limits"])
        host.app_socket = root / "peer.sock"
        try:
            host.server = host.launch([sys.executable, str(script), str(host.app_socket)], "websocket-peer")
            deadline = time.monotonic() + 5
            while not host.app_socket.exists():
                assert host.server.poll() is None and time.monotonic() < deadline
                time.sleep(.02)
            for name in ("before", "after"):
                host.app = host.connect_client(name)
                host.attach_connection()
                assert host.rpc("initialize", {}) == {"userAgent": "fixture"}
                host.disconnect_client()
                assert host.server.poll() is None
        finally:
            host.close()


@pytest.mark.parametrize("case", ["pre_thread_failure", "run_exists", "thread_exists", "events", "incomplete"])
def test_lifecycle_retry_only_before_any_thread_or_run(tmp_path, case):
    database = tmp_path / "state/database"
    database.mkdir(parents=True)
    with sqlite3.connect(database / "runs.sqlite3") as db:
        db.execute("CREATE TABLE runs(output_binding_name TEXT)")
        if case == "run_exists":
            db.execute("INSERT INTO runs VALUES (?)", (NAME + ".output",))
    attempt = tmp_path / "lifecycle"
    (attempt / "fixture-logs").mkdir(parents=True)
    (attempt / "fixture-logs/events.log").write_text("{}\n" if case == "events" else "")
    live.write(attempt / "usage.json", {"root_thread": None, "threads": {}, "items": []})
    if case != "incomplete":
        live.write(attempt / "resource.json", {"returncode": 1, "stop_reason": "exited"})
    if case == "thread_exists":
        live.write(attempt / "thread.json", {"thread_id": "actual-root"})
    if case == "pre_thread_failure":
        require_no_started_lifecycle(tmp_path)
        assert attempt.is_dir()  # Failure evidence stays at its original path.
    else:
        with pytest.raises(RuntimeError, match="lifecycle_"):
            require_no_started_lifecycle(tmp_path)


@pytest.mark.process_e2e
def test_disconnect_closes_only_client_and_retains_owned_server(tmp_path, monkeypatch):
    logs = tmp_path / "logs"
    logs.mkdir()
    monkeypatch.setenv("SCID_TEST_LOG_DIR", str(logs))
    live.write(tmp_path / "candidate.json", {"python": sys.executable, "project": str(tmp_path), "profile": {}})
    host = LifecycleHost(tmp_path, json.loads(live.guard.DEFAULT_CONFIG.read_text())["limits"])
    try:
        # Both are local sleeping Python fixtures, not Codex or model processes.
        command = [sys.executable, "-c", "import time; time.sleep(30)"]
        host.server = host.launch(command, "server")
        host.app = host.launch(command, "client", True)
        host.attach_connection()
        host.connection.buffer.extend(b"partial stale frame")
        connection = host.connection
        client = host.app
        before = datetime.now(timezone.utc)
        disconnected = host.disconnect_client()
        assert disconnected >= before
        assert client.poll() is not None
        assert host.server.poll() is None
        assert host.children == [host.server]
        assert connection.closed
        assert host.connection is None and host.root_host is None
    finally:
        host.close()
    assert host.server.poll() is not None


@pytest.mark.parametrize("failure", [None, "finished_early", "wrong_identity", "queued", "resume_queued"])
def test_reconnect_reads_original_run_without_restarting_worker(tmp_path, monkeypatch, failure):
    host = object.__new__(LifecycleHost)
    host.root = tmp_path
    host.logdir = tmp_path / "logs"
    host.logdir.mkdir()
    host.thread = host.platform_session = "original-root"
    host.started_threads = {"actual-worker"}
    host.resources = {"worker_wakeup_timeout_seconds": 30}
    host.phase_deadline = time.monotonic() + 30
    host.children = []
    host.server = type("Server", (), {"pid": 123})()
    host.app = type("Client", (), {"pid": 124, "stdin": io.BytesIO(), "stdout": io.BytesIO()})()
    prompts, requests = [], []
    now = datetime.now(timezone.utc)
    host.resume_existing = failure == "resume_queued"
    original = {"run_id": "run", "thread_id": "actual-worker", "platform_session": host.platform_session}
    monkeypatch.setattr("scripts.probe_root_lifecycle.require_lifecycle_resume", lambda root: None)
    rows = iter([original if host.resume_existing else None, {"run_id": "run", "state": "completed" if failure == "finished_early" else "queued" if failure in ("queued", "resume_queued") else "running",
                       "thread_id": "actual-worker", "platform_session": host.platform_session},
                 {"run_id": "run", "state": "completed", "completed_at": (now + timedelta(seconds=1)).isoformat()}])
    monkeypatch.setattr(host, "run_row", lambda: next(rows))
    monkeypatch.setattr(host, "initialize_host", lambda **kw: {"state": "active"})
    monkeypatch.setattr(host, "await_instance", lambda value: None)
    monkeypatch.setattr(host, "current_instance", lambda: {"state": "active"})
    monkeypatch.setattr(host, "status", lambda *a, **kw: None)
    monkeypatch.setattr(host, "disconnect_client", lambda: now)
    monkeypatch.setattr(host, "connect_client", lambda name: host.app)
    def turn(prompt):
        prompts.append(prompt)
        if prompt == DISPATCH:
            (host.logdir / "events.log").write_text(json.dumps({"params": {"item": {
                "type": "subAgentActivity", "kind": "started", "agentThreadId": "actual-worker"}}}) + "\n")
        elif prompt.startswith(RECOVER):
            (host.logdir / "events.log").write_text("")
    monkeypatch.setattr(host, "turn", turn)
    def rpc(method, params):
        requests.append((method, params))
        return {"thread": {"id": "wrong" if failure == "wrong_identity" else params.get("threadId"),
                           "sessionId": host.platform_session}}
    monkeypatch.setattr(host, "rpc", rpc)
    def reconnect_root():
        actual=rpc("thread/resume", {"threadId":host.thread})["thread"]
        if actual["id"] != host.thread:
            raise RuntimeError("lifecycle_reconnected_identity_changed")
    monkeypatch.setattr(host,"reconnect_root",reconnect_root)
    if failure in ("finished_early", "wrong_identity"):
        with pytest.raises(RuntimeError, match="active_attached_worker" if failure == "finished_early" else "identity_changed"):
            host.run()
        assert prompts == [DISPATCH]
    else:
        host.run()
        assert prompts == [RECOVER + "\n原 Worker 的实际线程：actual-worker" if host.resume_existing else DISPATCH, READBACK]
        assert [p["threadId"] for m, p in requests if m == "thread/resume"] == (
            ["actual-worker", "original-root", "actual-worker"] if host.resume_existing else ["original-root", "actual-worker"])
        evidence = json.loads((tmp_path / "lifecycle.json").read_text())
        assert evidence["worker_completed_while_disconnected"]
        assert not evidence["b0a_passed"]
    assert all(method in ("initialize", "thread/resume") for method, _ in requests)


@pytest.mark.parametrize("state,attached,expired,allowed", [
    ("queued", True, False, True), ("running", True, False, True),
    ("completed", True, False, False), ("queued", False, False, False),
    ("queued", True, True, False),
])
def test_resume_admission_preserves_frozen_deadline(tmp_path, state, attached, expired, allowed):
    database = tmp_path / "state/database"
    database.mkdir(parents=True)
    deadline = (datetime.now(timezone.utc) + timedelta(seconds=-1 if expired else 60)).isoformat()
    with sqlite3.connect(database / "runs.sqlite3") as db:
        db.execute("CREATE TABLE runs(run_id TEXT,output_binding_name TEXT,state TEXT,deadline_at TEXT)")
        db.execute("CREATE TABLE worker_connections(run_id TEXT,thread_id TEXT)")
        db.execute("INSERT INTO runs VALUES (?,?,?,?)", ("run", NAME + ".output", state, deadline))
        if attached:
            db.execute("INSERT INTO worker_connections VALUES (?,?)", ("run", "worker"))
    if allowed:
        require_lifecycle_resume(tmp_path)
    else:
        with pytest.raises(RuntimeError, match="within_deadline"):
            require_lifecycle_resume(tmp_path)


def test_idle_resumed_worker_requires_turn_started_notification(monkeypatch):
    host = object.__new__(LifecycleHost)
    host.started_threads = set()
    host.resources = {"worker_wakeup_timeout_seconds": 30}
    clock = iter([0, 0, 31])
    monkeypatch.setattr("scripts.probe_root_lifecycle.time.monotonic", lambda: next(clock))
    monkeypatch.setattr(host, "pump", lambda: None)
    with pytest.raises(RuntimeError, match="worker_turn_not_started"):
        host.require_worker_turn_started("original-worker")


@pytest.mark.parametrize("outcome,error", [
    ("completed", None), ("failed", "lifecycle_worker_not_running"),
    ("changed", "lifecycle_run_changed"), ("stopped", "user_stop"),
    ("deadline", "lifecycle_run_deadline"), ("timeout", "execution_timeout"),
    ("server_exit", "owned_process_exited_while_disconnected"),
])
def test_disconnected_wait_requires_same_run_and_keeps_stop_conditions(tmp_path, monkeypatch, outcome, error):
    host = object.__new__(LifecycleHost)
    host.root = tmp_path
    host.phase_deadline = time.monotonic() + (30 if outcome != "timeout" else -1)
    host.children = []
    if outcome == "stopped":
        (tmp_path / "stop").touch()
    if outcome == "server_exit":
        class Exited:
            def poll(self): return 1
        host.children = [Exited()]
    row = {"run_id": "other" if outcome == "changed" else "run",
           "state": "completed" if outcome == "completed" else "failed" if outcome == "failed" else "running",
           "deadline_at": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()}
    monkeypatch.setattr(host, "run_row", lambda: row)
    monkeypatch.setattr(host, "rpc", lambda *a: pytest.fail("model/protocol call during disconnected observation"))
    if error:
        with pytest.raises((RuntimeError, TimeoutError), match=error):
            host.wait_disconnected("run")
    else:
        assert host.wait_disconnected("run") == row
