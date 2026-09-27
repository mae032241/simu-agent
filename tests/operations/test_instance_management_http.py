import pytest

from scidiscovery.artifact_agent.approval_ui.access import access_cookie
from scidiscovery.artifact_agent.approval_ui.management import WorkbenchManagement
from scidiscovery.artifact_agent.approval_ui.read_model import InstanceReadModel
from scidiscovery.artifact_agent.approval_ui.trajectory import TrajectoryStore
from scidiscovery.artifact_agent.service.instance_archive import InstanceArchive
from tests.operations.test_instance_browser_http import _request
from tests.operations.test_m6a_direct_instance_management import _setup


@pytest.fixture
def management_ui(tmp_path):
    runtime, state, secret, ui, base = _setup(tmp_path)
    ui.read_model = InstanceReadModel(artifacts=runtime.artifacts, bindings=runtime.scheduler_bindings,
        runs=runtime.runs, approvals=runtime.approvals, executions=runtime.executions,
        operation_catalog=runtime.operation_catalog)
    ui.maintenance = runtime.maintenance
    ui.instance_archive = InstanceArchive(runtime, gate=runtime.instance_maintenance)
    ui.trajectory_store = TrajectoryStore(state / "ui" / "workbench.sqlite3")
    ui.management = WorkbenchManagement(ui.instance_archive, ui.trajectory_store)
    first = runtime.scheduler_bindings.create_instance_and_bind_session(session_key="sch_" + "a" * 32,
        name="maint.first", title="第一个实例", objective="原始目标")
    second = runtime.scheduler_bindings.create_instance(name="maint.second", title="Other", objective="Other objective")
    cookie = access_cookie(first.instance_id, ui.browser_access.issue(first.instance_id, maintenance=True))
    try:
        yield runtime, ui, first, second, cookie
    finally:
        ui.stop()


def _post_action(ui, instance_id, cookie, action, fingerprint):
    result = _request(ui.base_url, "POST", f"/instance/{instance_id}/manage/{action}", cookie=cookie,
        form={"csrf_token": ui.session_id, "confirm": "confirm", "fingerprint": fingerprint})
    if result[0] == 303:
        ui.management._thread.join(timeout=15)
        assert not ui.management._thread.is_alive(), "maintenance action did not finish"
    return result


def test_management_permissions_and_cache_cleanup_are_instance_scoped(management_ui):
    runtime, ui, first, second, cookie = management_ui
    target = first.instance_id
    path = f"/instance/{target}/manage"
    read_cookie = access_cookie(target, ui.browser_access.issue(target))
    assert _request(ui.base_url, "GET", path, cookie=read_cookie)[0] == 403
    assert _request(ui.base_url, "GET", f"/instance/{second.instance_id}/manage", cookie=cookie)[0] == 403
    assert _request(ui.base_url, "GET", path, cookie=cookie)[0] == 200
    for instance in (target, second.instance_id):
        ui.trajectory_store.observe(instance, [{"key": "run:a", "state": "completed"}])
    ui.trajectory_store.preferences(target, {"show_artifacts": False})
    original = ui.trajectory_store.observations(second.instance_id)
    before = ui.management.preview(target, "cleanup")
    assert _post_action(ui, target, read_cookie, "cleanup", before["fingerprint"])[0] == 403
    assert _post_action(ui, target, cookie, "cleanup", before["fingerprint"])[0] == 303
    assert not ui.management.status(target)["error"]
    assert ui.trajectory_store.observations(target)["items"] == []
    assert ui.trajectory_store.observations(second.instance_id) == original
    assert ui.trajectory_store.preferences(target) == {"show_artifacts": False}
    assert ui.management.status(target)["cleanup_result"]["physical_bytes_released"] == 0
    # Changed preview is rejected without removing newly observed history.
    ui.trajectory_store.observe(target, [{"key": "run:new", "state": "failed"}])
    _post_action(ui, target, cookie, "cleanup", before["fingerprint"])
    assert ui.management.status(target)["error"]
    assert ui.trajectory_store.observations(target)["items"]


def test_archive_browse_restore_invalidates_only_restored_instance_grant(management_ui):
    runtime, ui, first, second, cookie = management_ui
    target = first.instance_id
    other_cookie = access_cookie(second.instance_id, ui.browser_access.issue(second.instance_id))
    preview = ui.management.preview(target, "archive")
    assert preview["ready"], preview
    assert _post_action(ui, target, cookie, "archive", preview["fingerprint"])[0] == 303
    state = ui.management.status(target)
    assert not state["error"], state
    assert state["storage_state"] == "archived"
    assert _request(ui.base_url, "GET", f"/instance/{target}/manage", cookie=cookie)[0] == 200
    assert _request(ui.base_url, "GET", f"/api/instances/{target}/overview", cookie=cookie)[0] == 200
    assert _request(ui.base_url, "GET", f"/api/instances/{second.instance_id}/overview", cookie=other_cookie)[0] == 200
    preview = ui.management.preview(target, "restore")
    assert preview["ready"], preview
    assert _post_action(ui, target, cookie, "restore", preview["fingerprint"])[0] == 303
    state = ui.management.status(target)
    assert not state["error"], state
    assert state["storage_state"] == "restored"
    assert runtime.scheduler_bindings.get_instance(instance_id=target).state == "active"
    assert runtime.scheduler_bindings.session_instance(session_key="sch_" + "a" * 32) is None
    assert _request(ui.base_url, "GET", f"/api/instances/{target}/overview", cookie=cookie)[0] == 403
    assert _request(ui.base_url, "GET", f"/api/instances/{second.instance_id}/overview", cookie=other_cookie)[0] == 200
    fresh = access_cookie(target, ui.browser_access.issue(target, maintenance=True))
    assert _request(ui.base_url, "GET", f"/api/instances/{target}/overview", cookie=fresh)[0] == 200


def test_original_approval_links_read_archive_but_cannot_decide_or_refresh(management_ui):
    from scidiscovery.artifact_agent.schema.approval import approval_options_template
    from tests.operations.test_instance_archive import artifact
    runtime, ui, first, second, cookie = management_ui
    source = artifact(runtime, first.instance_id, "original.evidence", b"sealed original")
    launch = runtime.approvals.create_request(approval_id="apr_archive_http", kind="run_request",
        subject_refs=(source.ref,), question="Original pending decision?",
        options=approval_options_template("run_request"), idempotency_key="pending.http", requested_by=runtime.actor)
    runtime.scheduler_bindings.bind(instance=first.instance_id, namespace="approval",
        name="original.approval", object_id="apr_archive_http")
    path = f"/review/apr_archive_http?token={launch.access_token}"
    assert _request(ui.base_url, "GET", path)[0] == 200
    preview = ui.management.preview(first.instance_id, "archive")
    _post_action(ui, first.instance_id, cookie, "archive", preview["fingerprint"])
    assert not ui.management.status(first.instance_id)["error"]
    status, _, body = _request(ui.base_url, "GET", path)
    assert status == 200
    assert b'/review/apr_archive_http/decision' not in body
    assert _request(ui.base_url, "POST", "/review/apr_archive_http/refresh-access",
        form={"csrf": ui.session_id})[0] == 409
    assert _request(ui.base_url, "POST", "/review/apr_archive_http/decision",
        form={"token": launch.access_token, "csrf": "old", "nonce": "old",
              "selected_option": "approve", "rationale": "", "confirm": "confirm"})[0] == 409
    status, _, original = _request(ui.base_url, "GET",
        f"/review/apr_archive_http/evidence/{source.artifact_id}?token={launch.access_token}&format=download")
    assert status == 200 and original == b"sealed original"
