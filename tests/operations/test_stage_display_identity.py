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
