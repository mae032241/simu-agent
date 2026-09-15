"""Exercise local management without a conversation, using isolated stores only."""
import json
import os
from pathlib import Path
import sys
import tempfile

for directory in ('src', 'plugins/tcad_artifact', 'plugins/curve_score', 'plugins/curve_figure_evidence', '.'):
    sys.path.insert(0, str(Path(directory).resolve()))
if os.environ.get('SCID_BROWSER_PYTHONPATH'):
    sys.path.append(os.environ['SCID_BROWSER_PYTHONPATH'])
if os.environ.get('SCID_INSTALLED_SITE'):
    sys.path.insert(0, os.environ['SCID_INSTALLED_SITE'])
    import scidiscovery.artifact_agent.approval_ui.app as installed_app
    assert Path(installed_app.__file__).is_relative_to(Path(os.environ['SCID_INSTALLED_SITE']))
from playwright.sync_api import sync_playwright, expect
from tests.operations.test_instance_management_http import management_ui

with tempfile.TemporaryDirectory(prefix='scid-workbench-client-') as temporary:
    fixture = management_ui.__wrapped__(Path(temporary))
    runtime, ui, first, second, _ = next(fixture)
    assert ':8765' not in ui.base_url
    a, b = ('sch_' + x * 32 for x in 'ab')
    runtime.scheduler_bindings.register_client(session_key=a)
    runtime.scheduler_bindings.register_client(session_key=b)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--no-zygote', '--single-process',
                '--disable-gpu', '--disable-dev-shm-usage', '--js-flags=--max-old-space-size=64'])
            page = browser.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(ui.base_url)
            page.locator('a[href="#session-setup"]').click()
            expect(page.locator('form[action="/instances/create-unbound"]')).to_be_visible()
            page.locator('input[name="name"]').fill('browser.standalone')
            page.locator('input[name="title"]').fill('浏览器独立创建')
            page.locator('textarea[name="objective"]').fill('合成测试原始目标')
            page.get_by_role('button', name='创建实例（不绑定对话）', exact=True).click()
            page.wait_for_load_state('networkidle')
            created = runtime.scheduler_bindings.select_instance(name='browser.standalone')
            assert not runtime.scheduler_bindings.session_binding_snapshot(session_key=a, instance_id=created.instance_id)['target_bound']
            page.goto(ui.base_url + '/instances/manage')
            card = page.locator('article').filter(has_text='第一个实例')
            card.get_by_role('button', name='Agent 设置', exact=True).click()
            page.wait_for_load_state('networkidle')
            assert page.title() == 'Agent 设置'
            assert page.locator('form.agent-settings-form').is_visible()
            page.get_by_role('link', name='当前实例', exact=True).click()
            page.wait_for_load_state('networkidle')
            assert '科研工作台' in page.title()
            page.goto(ui.base_url + '/sessions')
            client = page.locator('article').filter(has_text='bbbbbbbb')
            client.get_by_role('link', name='处理绑定申请').click()
            page.locator('select[name="name"]').select_option(second.name)
            page.get_by_role('button', name='绑定到当前会话', exact=True).click()
            page.wait_for_load_state('networkidle')
            assert runtime.scheduler_bindings.session_instance(session_key=b) == second.instance_id
            assert runtime.scheduler_bindings.session_instance(session_key=a) == first.instance_id
            page.goto(ui.base_url + '/sessions')
            page.locator('article').filter(has_text='aaaaaaaa').get_by_role('button', name='暂停后续调度').click()
            page.wait_for_load_state('networkidle')
            assert not runtime.scheduler_bindings.client_enabled(session_key=a)
            # A fresh browser recovers access directly without any client link.
            page.context.clear_cookies()
            page.goto(ui.base_url + f'/instance/{first.instance_id}/settings')
            page.get_by_role('button', name='进入Agent 设置', exact=True).click()
            page.wait_for_load_state('networkidle')
            assert page.locator('form.agent-settings-form').is_visible()
            assert not errors, errors
            assert runtime.runs.active_ids(instance_id=first.instance_id, limit=10) == ()
            browser.close()
            print(json.dumps({'browser': 'pass', 'unbound_creation': True, 'settings_without_conversation': True,
                'client_request_binding': True, 'pause': True, 'expired_browser_reentry': True,
                'javascript_errors': errors, 'scientific_runs_started': 0}))
    finally:
        fixture.close()
