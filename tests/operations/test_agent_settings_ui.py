from scidiscovery.artifact_agent.approval_ui.access import access_cookie
from tests.operations.test_instance_management_http import management_ui
from tests.operations.test_instance_browser_http import _request


def test_settings_http_permissions_cas_and_no_research_side_effects(management_ui):
    runtime, ui, first, second, cookie = management_ui
    target = first.instance_id
    path = f"/instance/{target}/manage/agent-settings"
    form = dict(csrf_token=ui.session_id, expected_revision="0", settings_action="save", operation_id="",
                default_model="gpt-5.6-luna", default_reasoning_effort="low",
                default_narrative_language="zh-CN", default_max_attempts="3")
    read_cookie = access_cookie(target, ui.browser_access.issue(target))
    status, headers, body = _request(ui.base_url, "GET", f"/instance/{target}/settings", cookie=read_cookie)
    assert status == 200 and "当前仅可查看设置".encode() in body
    assert headers["Referrer-Policy"] == "same-origin"
    assert b"name='referrer'" not in body
    assert "当前浏览授权仅允许查看".encode() in body
    assert "实例已归档".encode() not in body
    assert _request(ui.base_url, "POST", path, cookie=read_cookie, form=form)[0] == 403
    assert _request(ui.base_url, "POST", f"/instance/{second.instance_id}/manage/agent-settings", cookie=cookie, form=form)[0] == 403
    assert _request(ui.base_url, "POST", path, cookie=cookie, form={**form, "csrf_token": "wrong"})[0] == 403
    status, headers, _ = _request(ui.base_url, "POST", path, cookie=cookie, form=form)
    assert status == 303 and headers["Location"] == f"/instance/{target}/settings"
    assert ui.management._thread is None  # Saving settings does not start maintenance or science.
    saved = runtime.scheduler_bindings.agent_settings(target)
    assert saved["settings"]["defaults"]["model"] == "gpt-5.6-luna"
    assert saved["revision"] == 1
    assert _request(ui.base_url, "POST", path, cookie=cookie, form=form)[0] == 409
    assert runtime.scheduler_bindings.agent_settings(target) == saved
    assert runtime.scheduler_bindings.session_instance(session_key="sch_" + "a" * 32) == target
    assert runtime.runs.active_ids(instance_id=target, limit=10) == ()
    assert runtime.scheduler_bindings.agent_settings(second.instance_id)["revision"] == 0
    _, _, page = _request(ui.base_url, "GET", f"/instance/{target}/manage", cookie=cookie)
    assert b"agent-settings-form" not in page and b"data-settings-preview" not in page
    _, _, settings_page = _request(ui.base_url, "GET", f"/instance/{target}/settings", cookie=cookie)
    assert "实例默认".encode() in settings_page and b"data-settings-preview" in settings_page
    assert b"management-confirm" not in settings_page


def test_operation_override_form_preserves_other_overrides_and_resets(management_ui):
    from scidiscovery.artifact_agent.approval_ui.agent_settings import apply_form, agent_operations
    runtime, ui, first, _, _ = management_ui
    operations = agent_operations(runtime.operation_catalog)
    name = next(iter(operations))
    current = {"operations": {"disabled.operation": {"model": "retained"}, name: {"model": "old"}}}
    form = {"settings_action": ["save"], "operation_id": [name], "operation_model": ["new"],
            "operation_reasoning_effort": ["low"], "operation_max_attempts": [""]}
    saved = apply_form(current, form, runtime.operation_catalog)
    assert saved["operations"][name] == dict(model="new", reasoning_effort="low")
    assert saved["operations"]["disabled.operation"]["model"] == "retained"
    assert apply_form(saved, {"settings_action": ["reset"]}, runtime.operation_catalog) == {}


def test_separate_settings_and_archive_entry_grants_do_not_bind_or_start_work(management_ui):
    runtime, ui, first, _, _ = management_ui
    status, _, page = _request(ui.base_url, "GET", "/instances/manage")
    assert status == 200
    assert b"name='destination' value='settings'" in page
    assert b"name='destination' value='manage'" in page
    before = runtime.scheduler_bindings.session_instance(session_key="sch_" + "a" * 32)
    for destination in ("settings", "manage"):
        form = dict(csrf=ui.session_id, instance_id=first.instance_id,
                    scope="maintenance", destination=destination)
        assert _request(ui.base_url, "POST", "/instances/access", form={**form, "csrf": "bad"})[0] == 403
        status, headers, _ = _request(ui.base_url, "POST", "/instances/access", form=form)
        assert status == 303
        assert headers["Location"] == f"/instance/{first.instance_id}/{destination}"
        grant = headers["Set-Cookie"].split(";", 1)[0]
        status, _, page = _request(ui.base_url, "GET", headers["Location"], cookie=grant)
        assert status == 200
        assert (b"agent-settings-form" in page) == (destination == "settings")
        assert ("当前维护状态".encode() in page) == (destination == "manage")
    assert runtime.scheduler_bindings.session_instance(session_key="sch_" + "a" * 32) == before
    assert ui.management._thread is None
    assert runtime.runs.active_ids(instance_id=first.instance_id, limit=10) == ()
