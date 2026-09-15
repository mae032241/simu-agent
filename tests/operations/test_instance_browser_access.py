from datetime import datetime, timedelta, timezone

import pytest

from scidiscovery.artifact_agent.approval_ui.access import (
    BrowserAccessDenied, BrowserAccessService, access_cookie,
)


NOW = datetime(2026, 9, 14, tzinfo=timezone.utc)


def test_browser_grant_keeps_instance_and_maintenance_scopes_separate():
    access = BrowserAccessService(secret=b"test browser secret "*2, ui_session_id="boot_a")
    token = access.issue("instance_a", now=NOW)
    assert access.verify(token, instance_id="instance_a", now=NOW).scopes == ("read",)
    for instance, scope in (("instance_b", "read"), ("instance_a", "maintenance")):
        with pytest.raises(BrowserAccessDenied):
            access.verify(token, instance_id=instance, scope=scope, now=NOW)
    maintained = access.issue("instance_a", maintenance=True, now=NOW)
    assert "maintenance" in access.verify(maintained, instance_id="instance_a",
        scope="maintenance", now=NOW).scopes


def test_expiry_restart_and_restore_never_reactivate_old_browser_grants():
    secret = b"test browser secret "*2
    access = BrowserAccessService(secret=secret, ui_session_id="boot_a")
    token = access.issue("instance_a", now=NOW, lifetime=timedelta(minutes=1))
    with pytest.raises(BrowserAccessDenied):
        access.verify(token, instance_id="instance_a", now=NOW+timedelta(minutes=1))
    with pytest.raises(BrowserAccessDenied):
        BrowserAccessService(secret=secret, ui_session_id="boot_b").verify(
            token, instance_id="instance_a", now=NOW)
    with pytest.raises(BrowserAccessDenied):
        access.verify(token, instance_id="instance_a", now=NOW, issued_after=NOW)


def test_cookie_grants_do_not_accept_approval_tokens_or_other_instances():
    access = BrowserAccessService(secret=b"test browser secret "*2, ui_session_id="boot_a")
    token = access.issue("instance_a", now=NOW)
    cookie = access_cookie("instance_a", token)
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie
    assert access.from_cookie(cookie, instance_id="instance_a", now=NOW).instance_id == "instance_a"
    with pytest.raises(BrowserAccessDenied):
        access.from_cookie(cookie, instance_id="instance_b", now=NOW)
    changed = token[:16] + ("B" if token[16] == "A" else "A") + token[17:]
    for invalid in ("", "old_approval_token", "?"*100, changed):
        with pytest.raises(BrowserAccessDenied):
            access.verify(invalid, instance_id="instance_a", now=NOW)
