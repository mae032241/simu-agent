"""A stage view and manual generation must never substitute the parent report."""
import json

import pytest

from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.artifact_agent.service.presentation_summaries import store_for
from scidiscovery.artifact_agent.approval_ui.read_model import ReadModelNotFound
from scidiscovery.artifact_agent.approval_ui.workbench_render import render_node
from tests.operations.test_experiment_continuation import continuation, submit
from tests.operations.test_experiment_ui_trajectory import model_for


def test_each_stage_and_version_retains_its_own_copy_and_folded_history(tmp_path, monkeypatch):
    f = continuation(tmp_path, monkeypatch)
    refs = []
    titles = {}
    for phase, text in [('design', '设计第一版'), ('design', '设计第二版'), ('validity', '有效性未确定')]:
        stage = f.worker.call_tool('worker_experiment_stage', {'stage': phase, 'conclusion': text})['reference']
        refs.append(stage)
        titles[f.runs.sealed_material_record(f.runs.status(f.run_id), stage)['artifact_ref']['sha256']] = text
    assert submit(f, refs, outcome='inconclusive')['state'] == 'completed'
    final = f.runs.status(f.run_id).output_ref
    titles[final.sha256] = '父实验最终导读'
    store = store_for(f.runs)
    while job := store.claim():
        ref = ArtifactRef.model_validate_json(job['source_ref'])
        store.finish(job['cache_key'], items=[{'source': '/summary' if ref == final else '/conclusion',
            'title': titles.get(ref.sha256, '其他材料'), 'summary': titles.get(ref.sha256, '其他材料')}])
    model = model_for(f)
    model.presentation_summaries = store
    for alias in refs:
        ref = ArtifactRef.model_validate(f.runs.sealed_material_record(f.runs.status(f.run_id), alias)['artifact_ref'])
        detail = model.node(f.instance.instance_id, 'run:continuation', stage_reference=alias)
        polled = model.node_metadata(f.instance.instance_id, 'run:continuation', stage_reference=alias)
        assert detail['display_copy']['items'][0]['title'] == titles[ref.sha256]
        assert polled['display_copy'] == detail['display_copy']
        html = render_node(detail, instance_id=f.instance.instance_id, csrf_token='fixture', can_retry_summary=True).decode()
        assert '父实验最终导读' not in html
        assert f"data-display-stage='{alias}'" in html
        assert "class='research-panel display-copy-panel'><summary>" in html
        assert "class='research-panel stage-history'><summary>" in html
        assert '当前阶段封存原文' in html and '重新整理' in html
    assert model.node_metadata(f.instance.instance_id, 'run:continuation')['display_copy']['items'][0]['title'] == '父实验最终导读'
    with store.connect() as db:
        db.execute('DELETE FROM display_summaries WHERE source_ref != ?', (final.model_dump_json(),))
    missing = model.node_metadata(f.instance.instance_id, 'run:continuation', stage_reference=refs[0])
    assert missing['display_copy']['state'] == 'not_generated'
    with pytest.raises(ReadModelNotFound):
        model.node_metadata(f.instance.instance_id, 'run:continuation', stage_reference='not-a-stage')


@pytest.mark.process_e2e
def test_manual_generation_and_regeneration_are_bound_to_the_selected_stage(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.approval_ui.app import ApprovalUI
    from scidiscovery.artifact_agent.approval_ui.access import access_cookie
    from tests.operations.test_instance_browser_http import _request
    f = continuation(tmp_path, monkeypatch)
    stage = f.worker.call_tool('worker_experiment_stage', {'stage': 'design', 'conclusion': 'Stage only.'})['reference']
    assert submit(f, [stage], outcome='inconclusive')['state'] == 'completed'
    run = f.runs.status(f.run_id)
    ref = ArtifactRef.model_validate(f.runs.sealed_material_record(run, stage)['artifact_ref'])
    store = store_for(f.runs)
    with store.connect() as db:
        db.execute('DELETE FROM display_summaries')
    model = model_for(f); model.presentation_summaries = store
    ui = ApprovalUI(f.runtime.approvals, bindings=f.runtime.scheduler_bindings, read_model=model,
        instance_management_secret=b'display-generation-test' * 3)
    base = ui.start(); instance = f.instance.instance_id
    cookie = access_cookie(instance, ui.browser_access.issue(instance, maintenance=True))
    readonly = access_cookie(instance, ui.browser_access.issue(instance))
    page = f'/instance/{instance}/nodes/run%3Acontinuation?stage_reference={stage}'
    endpoint = f'/instance/{instance}/display-summary/'
    try:
        body = _request(base, 'GET', page, cookie=cookie)[2]
        assert b'display-summary/generate' in body and store.claim() is None
        form = {'csrf': ui.session_id, 'node_key': 'run:continuation', 'stage_reference': stage}
        assert _request(base, 'POST', endpoint+'generate', form=form, cookie=readonly)[0] == 403
        assert _request(base, 'POST', endpoint+'generate', form=form, cookie=cookie)[0] == 303
        assert _request(base, 'POST', endpoint+'generate', form=form, cookie=cookie)[0] == 303
        job = store.claim()
        assert ArtifactRef.model_validate_json(job['source_ref']) == ref
        assert store.claim() is None and store.read(instance, run.output_ref) is None
        store.finish(job['cache_key'], items=[{'source':'/conclusion', 'title':'阶段导读', 'summary':'Stage only.'}])
        api = f'/api/instances/{instance}/nodes/run%3Acontinuation?view=metadata&stage_reference={stage}'
        status, _, payload = _request(base, 'GET', api, cookie=cookie)
        refreshed = json.loads(payload)
        assert status == 200 and refreshed['stage_reference'] == stage
        assert refreshed['display_copy']['items'][0]['title'] == '阶段导读'
        assert _request(base, 'GET', api.replace(stage, 'missing-stage'), cookie=cookie)[0] == 404
        retry = store.read(instance, ref)['retry']
        forged = {'csrf':ui.session_id, 'node_key':'run:continuation', **retry}
        assert _request(base, 'POST', endpoint+'retry', form=forged, cookie=cookie)[0] == 409
        valid = {**forged, 'stage_reference':stage}
        assert _request(base, 'POST', endpoint+'retry', form=valid, cookie=cookie)[0] == 303
        assert _request(base, 'POST', endpoint+'retry', form=valid, cookie=cookie)[0] == 303
        assert ArtifactRef.model_validate_json(store.claim()['source_ref']) == ref
        assert store.claim() is None
        assert f.runs.status(f.run_id).output_ref == run.output_ref
    finally:
        ui.stop()


@pytest.mark.process_e2e
def test_directory_entry_can_enable_summary_actions_without_a_navigation_loop(tmp_path, monkeypatch):
    import re
    from html import unescape
    from scidiscovery.artifact_agent.approval_ui.app import ApprovalUI
    from tests.operations.test_home_navigation import request

    def form_with(page, text):
        for body in re.findall(r'<form\b[^>]*>.*?</form>', page, re.S):
            if text in body:
                return dict((name, unescape(value)) for name, value in
                    re.findall(r"name='([^']*)' value='([^']*)'", body))
        pytest.fail(f'Missing form: {text}')

    f = continuation(tmp_path, monkeypatch)
    stage = f.worker.call_tool('worker_experiment_stage', {'stage': 'design', 'conclusion': 'Design summary.'})['reference']
    store = store_for(f.runs)
    with store.connect() as db:
        db.execute('DELETE FROM display_summaries')
    model = model_for(f); model.presentation_summaries = store
    ui = ApprovalUI(f.runtime.approvals, bindings=f.runtime.scheduler_bindings, read_model=model,
        instance_management_secret=b'summary-browser-entry' * 3)
    base = ui.start(); instance = f.instance.instance_id
    try:
        status, _, directory = request(base, 'GET', '/instances/manage')
        assert status == 200
        access = form_with(directory, '查看状态与轨迹')
        assert access['instance_id'] == instance and access['scope'] == 'read'
        status, headers, _ = request(base, 'POST', '/instances/access', form=access)
        assert status == 303
        cookie = headers['Set-Cookie'].split(';', 1)[0]
        status, _, page = request(base, 'GET', headers['Location'], cookie=cookie)
        assert status == 200 and '从实例管理进入' not in page
        enable = form_with(page, '启用实例管理权限')
        assert store.claim() is None  # Browsing/enabling access must not run the model.
        denied = {'csrf':ui.session_id, 'node_key':'run:continuation', 'stage_reference':stage}
        assert request(base, 'POST', f'/instance/{instance}/display-summary/generate', cookie=cookie, form=denied)[0] == 403
        assert request(base, 'POST', '/instances/access', form={**enable, 'csrf':'wrong'}, cookie=cookie)[0] == 403
        status, headers, _ = request(base, 'POST', '/instances/access', form=enable, cookie=cookie)
        assert status == 303
        cookie = headers['Set-Cookie'].split(';', 1)[0]
        for path in (headers['Location'], f'/instance/{instance}/nodes/run%3Acontinuation'):
            status, _, page = request(base, 'GET', path, cookie=cookie)
            assert status == 200
            assert '从实例管理进入' not in page and '当前浏览授权为只读' not in page
            children = [row for row in re.findall(r"<li class='experiment-child'>.*?</li>", page, re.S)
                if '?stage_reference=' in row]
            assert children and all('data-summary-retry' in row for row in children)
            assert any(f"name='stage_reference' value='{stage}'" in row for row in children)
            from urllib.parse import parse_qs, urlparse
            for row in children:
                href = unescape(re.search(r"href='([^']*)'", row)[1])
                assert form_with(row, 'data-summary-retry')['stage_reference'] == parse_qs(urlparse(href).query)['stage_reference'][0]
        assert store.claim() is None
        assert request(base, 'POST', f'/instance/{instance}/display-summary/generate', cookie=cookie, form=denied)[0] == 303
        assert store.claim() is not None
        # Show the actual reason, rather than sending an authorized browser back to the directory.
        with store.connect() as db:
            db.execute('DELETE FROM display_summaries')
        for reason in ('instance_disabled', 'service_disabled', 'service_unavailable', 'read_only'):
            with monkeypatch.context() as patch:
                if reason == 'instance_disabled':
                    patch.setattr(ui.bindings, 'agent_settings', lambda _: {'settings': {'presentation': {'enabled': False}}})
                    expected = '此实例已关闭自动导读'
                elif reason == 'service_disabled':
                    from types import SimpleNamespace
                    patch.setattr(f.runs, 'agent_settings', SimpleNamespace(presentation=SimpleNamespace(enabled=False)))
                    expected = '服务配置已关闭自动导读'
                elif reason == 'service_unavailable':
                    patch.setattr(model, 'presentation_summaries', None)
                    expected = '自动导读服务尚未就绪'
                else:
                    patch.setattr(ui, '_cache_writable', lambda _: False)
                    expected = '实例当前为只读或正在维护'
                status, _, page = request(base, 'GET', f'/instance/{instance}', cookie=cookie)
                assert status == 200 and expected in page
                assert '从实例管理进入' not in page and '启用实例管理权限' not in page
                assert 'data-summary-retry' not in page
                assert request(base, 'POST', f'/instance/{instance}/display-summary/generate', cookie=cookie, form=denied)[0] == 409
    finally:
        ui.stop()
