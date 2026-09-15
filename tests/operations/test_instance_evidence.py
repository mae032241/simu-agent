from io import BytesIO
from urllib.parse import quote, urlencode

from PIL import Image
import pytest

from scidiscovery.artifact_agent.approval_ui.app import ApprovalUI
from scidiscovery.artifact_agent.approval_ui.access import access_cookie
from scidiscovery.artifact_agent.approval_ui.evidence import preview_type
from scidiscovery.artifact_agent.storage import CASIntegrityError
from tests.operations.test_instance_read_model import system, artifact, approval
from tests.operations.test_instance_browser_http import _request


def picture():
    target = BytesIO()
    Image.new("RGB", (4, 3), "white").save(target, format="PNG")
    return target.getvalue()


def test_safe_preview_checks_bytes_format_dimensions_and_media():
    raw = picture()
    assert preview_type(raw, "image/png") == "image/png"
    assert preview_type(raw, "image/jpeg") is None
    assert preview_type(b"<html><script>unsafe()</script></html>", "image/png") is None
    assert preview_type(raw, "image/svg+xml") is None
    assert preview_type(raw[:30], "image/png") is None


def test_streamed_original_uses_exact_verified_descriptor(system, monkeypatch):
    source = artifact(system, "original", raw=b"original bytes", media_type="text/plain")
    monkeypatch.setattr(system.artifacts.cas, "read", lambda *_args, **_kw: pytest.fail("download loaded full original"))
    with system.artifacts.open_original(source.ref) as stream:
        assert stream.read(4) == b"orig"
        assert stream.read() == b"inal bytes"
    path = system.artifacts.cas.path_for(source.sha256)
    path.write_bytes(b"different bytes")
    with pytest.raises(CASIntegrityError):
        with system.artifacts.open_original(source.ref):
            pytest.fail("corrupt original became available")
    path.unlink()
    target = path.with_name("symlink-target")
    target.write_bytes(b"original bytes")
    path.symlink_to(target)
    with pytest.raises(CASIntegrityError):
        with system.artifacts.open_original(source.ref):
            pytest.fail("symlink original became available")


def test_approval_evidence_never_uses_newer_same_instance_or_foreign_records(system):
    figure = artifact(system, "frozen_figure", raw=picture(), media_type="image/png")
    old = artifact(system, "old", {"goal": "exact old goal"}, parents=(figure.ref,))
    newer = artifact(system, "newer", {"goal": "later goal"}, instance=system.a)
    foreign = artifact(system, "foreign", instance=system.b)
    launch = approval(system, "frozen", (old.ref,))
    ui = ApprovalUI(system.approvals, bindings=system.bindings, read_model=system.model,
                    instance_management_secret=b"s" * 32)
    base = ui.start()
    try:
        def url(source, **query):
            return f"/review/{launch.approval_id}/evidence/{quote(source.artifact_id, safe='')}?" + urlencode({"token": launch.access_token, **query})
        assert _request(base, "GET", url(old, pointer="/goal"))[0] == 200
        assert b"exact old goal" in _request(base, "GET", url(old, pointer="/goal"))[2]
        assert _request(base, "GET", url(newer))[0] == 403
        assert _request(base, "GET", url(foreign))[0] == 403
        status, headers, body = _request(base, "GET", url(figure, format="image"))
        assert status == 200 and headers["Content-Type"] == "image/png" and body == picture()
        assert _request(base, "GET", url(old, format="download"))[2] == system.artifacts.read(old.ref)
        assert _request(base, "GET", f"/api/instances/{system.a}/overview?token={launch.access_token}")[0] == 403
    finally:
        ui.stop()


def test_browser_original_is_authorized_and_never_interprets_unknown_html(system):
    fake = artifact(system, "fake_image", raw=b"<script>secret()</script>", media_type="image/png", instance=system.a)
    ui = ApprovalUI(system.approvals, bindings=system.bindings, read_model=system.model,
                    instance_management_secret=b"s" * 32)
    base = ui.start()
    cookie = access_cookie(system.a, ui.browser_access.issue(instance_id=system.a))
    url = f"/instance/{system.a}/evidence/{fake.artifact_id}"
    try:
        assert _request(base, "GET", url)[0] == 403
        assert _request(base, "GET", url + "?format=image", cookie=cookie)[0] == 415
        status, headers, body = _request(base, "GET", url + "?format=download", cookie=cookie)
        assert status == 200 and body == b"<script>secret()</script>"
        assert headers["Content-Type"] == "application/octet-stream"
        assert headers["Content-Disposition"].startswith("attachment;")
    finally:
        ui.stop()
