from contextlib import contextmanager
import http.client
from urllib.parse import urlencode, urlparse

import pytest

from scidiscovery.artifact_agent.approval_ui import app
from scidiscovery.artifact_agent.approval_ui.access import access_cookie
from scidiscovery.artifact_agent.approval_ui.trajectory import TrajectoryStore
from scidiscovery.artifact_agent.service.maintenance import StateMaintenanceLock
from tests.operations.test_instance_browser_http import _request
from tests.operations.test_instance_read_model import system, artifact


class QuietObserver:
    @contextmanager
    def subscribe(self, _instance):
        yield

    def stop(self):
        pass


@pytest.fixture
def event_ui(system, tmp_path, monkeypatch):
    monkeypatch.setattr(app, "SSE_SECONDS", .2)
    monkeypatch.setattr(app, "SSE_POLL_SECONDS", .03)
    lock = StateMaintenanceLock(tmp_path / "maintenance.lock")
    store = TrajectoryStore(tmp_path / "ui" / "workbench.sqlite3")
    ui = app.ApprovalUI(system.approvals, bindings=system.bindings, read_model=system.model,
        maintenance=lock, trajectory_store=store, instance_management_secret=b"s" * 32)
    ui.trajectory = QuietObserver()
    ui.start()
    cookie = access_cookie(system.a, ui.browser_access.issue(instance_id=system.a)).split(";", 1)[0]
    try:
        yield ui, store, lock, cookie
    finally:
        ui.stop()


def test_sse_wait_releases_maintenance_and_resumes_exact_cursor(event_ui, system):
    ui, store, lock, cookie = event_ui
    initial = store.events(system.a)["cursor"]
    store.observe(system.a, [{"key": "run:one", "state": "running"}])
    previous = store.events(system.a)["cursor"]
    store.observe(system.a, [{"key": "run:one", "state": "completed"}])
    target = urlparse(ui.base_url)
    connection = http.client.HTTPConnection(target.hostname, target.port, timeout=3)
    connection.request("GET", f"/api/instances/{system.a}/events?" + urlencode({"after": initial}),
                       headers={"Cookie": cookie, "Last-Event-ID": previous})
    response = connection.getresponse()
    assert response.status == 200
    assert response.readline() == b"event: nodes\n"
    with lock.exclusive(blocking=False):
        pass  # The open stream is waiting/writing, not holding a control lock.
    payload = response.read()
    assert b'"state":"completed"' in payload
    assert b'"state":"running"' not in payload  # Header wins over stale initial URL.
    connection.close()


def test_sse_permission_limit_and_cache_failure_are_bounded(event_ui, system, monkeypatch):
    ui, store, _, cookie = event_ui
    path = f"/api/instances/{system.a}/events"
    assert _request(ui.base_url, "GET", path)[0] == 403
    assert _request(ui.base_url, "GET", f"/api/instances/{system.b}/events", cookie=cookie)[0] == 403
    for _ in range(8):
        assert ui._stream_slots.acquire(blocking=False)
    try:
        status, headers, _ = _request(ui.base_url, "GET", path, cookie=cookie)
        assert status == 429 and headers["Retry-After"] == "10"
    finally:
        for _ in range(8):
            ui._stream_slots.release()
    monkeypatch.setattr(store, "events", lambda *args, **kw: (_ for _ in ()).throw(OSError("isolated UI cache unavailable")))
    assert _request(ui.base_url, "GET", path, cookie=cookie)[0] == 503
    assert _request(ui.base_url, "GET", f"/api/instances/{system.a}/overview", cookie=cookie)[0] == 200


def test_regular_reply_and_streamed_original_write_outside_control_lock(event_ui, system, monkeypatch):
    ui, _, lock, cookie = event_ui
    source = artifact(system, "download", raw=b"frozen original", media_type="text/plain", instance=system.a)
    observed = []
    respond = ui._respond
    def checked(handler, *args, **kw):
        if not getattr(handler, "_defer_reply", False):
            with lock.exclusive(blocking=False):
                observed.append("reply")
        return respond(handler, *args, **kw)
    monkeypatch.setattr(ui, "_respond", checked)
    original = ui._write_original
    def checked_original(handler, envelope, stream):
        with lock.exclusive(blocking=False):
            observed.append("original")
        return original(handler, envelope, stream)
    monkeypatch.setattr(ui, "_write_original", checked_original)
    assert _request(ui.base_url, "GET", f"/api/instances/{system.a}/overview", cookie=cookie)[0] == 200
    status, _, raw = _request(ui.base_url, "GET", f"/instance/{system.a}/evidence/{source.artifact_id}?format=download", cookie=cookie)
    assert status == 200 and raw == b"frozen original"
    assert observed == ["reply", "original"]
