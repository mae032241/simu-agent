"""Approval intent and requested parameters stay visible and exact across UI entries."""
from urllib.parse import urlparse

import pytest

from scidiscovery.artifact_agent.approval_ui.approval_focus import render_approval_focus
from tests.operations.test_instance_content_display import providers


def test_key_parameters_use_only_frozen_subjects_and_escape_original_labels():
    def row(artifact, value):
        return {'name': '<unsafe>', 'selected_value': value, 'unit': 'cm^-3',
            'case_scope': 'case-A', 'conditions': '300 K',
            'source': {'artifact_id': artifact, 'json_pointer': '/parameters/0'}}
    presentation = {'parameters': [row('frozen', 3e15), row('ancestor', 'WRONG_OLD_VALUE')],
        'sections': [{'kind': 'execution_scope', 'items': [
            {'label': '入口', 'value': 'exact.cmd', 'source': {'artifact_id': 'frozen', 'json_pointer': '/entrypoint'}},
            {'label': '旧入口', 'value': 'WRONG_OLD_ENTRY', 'source': {'artifact_id': 'ancestor', 'json_pointer': '/entrypoint'}}]}]}
    page = render_approval_focus(presentation, subject_ids=['frozen'],
        evidence_href=lambda artifact, pointer: '/evidence/' + artifact)
    assert 'WRONG_OLD' not in page and '<unsafe>' not in page
    assert '&lt;unsafe&gt;' in page and 'exact.cmd' in page and 'cm^-3' in page and '300 K' in page
    assert '<details' not in page


@pytest.mark.process_e2e
def test_real_execution_approval_shows_request_limits_before_background_and_keeps_exact_decision(tmp_path, monkeypatch, providers):
    from scidiscovery.artifact_agent.approval_ui.app import ApprovalUI
    from scidiscovery.artifact_agent.approval_ui.access import access_cookie
    from tests.operations.test_experiment_approval_handoff import experiment, start
    from tests.operations.test_experiment_ui_trajectory import model_for
    from tests.operations.test_home_navigation import request

    f = experiment(tmp_path, monkeypatch)
    first = start(f)
    binding = f.runtime.scheduler_bindings.get_binding(instance=f.instance.instance_id,
        namespace='approval', name=first['approval_name'])
    status = f.runtime.approvals.status(binding.object_id)
    original = f.runtime.artifacts.read(status.approval_request_ref)
    ui = ApprovalUI(f.runtime.approvals, bindings=f.runtime.scheduler_bindings, read_model=model_for(f),
        instance_management_secret=b'approval-focus-fixture' * 3)
    base = ui.start(); instance = f.instance.instance_id
    cookie = access_cookie(instance, ui.browser_access.issue(instance))
    try:
        status_code, _, overview = request(base, 'GET', f'/instance/{instance}', cookie=cookie)
        assert status_code == 200 and '待你决定' in overview and '查看关键参数并审批' in overview
        assert '5,400 秒（90 分钟）' in overview and '3,600 秒（60 分钟）' in overview
        from urllib.parse import quote
        path = f'/instance/{instance}/nodes/' + quote('approval:' + first['approval_name'], safe='')
        status_code, _, node = request(base, 'GET', path, cookie=cookie)
        assert status_code == 200 and '核对参数并作出决定' in node
        target = urlparse(first['review_url'])
        status_code, _, review = request(base, 'GET', target.path + '?' + target.query)
        assert status_code == 200
        for page in (node, review):
            assert '本次审批关键参数' in page
            assert '5,400 秒（90 分钟）' in page
            assert '3,600 秒（60 分钟）' in page
            assert '1,800,000,000 字节（1.8 GB）' in page
            assert '超出自动额度' in page and '内存上限（字节）' in page
            focus_start = page.index('aria-label="本次审批关键参数"')
            focus_end = page.index('</section>', focus_start)
            assert '<details' not in page[focus_start:focus_end]
        assert review.index('本次审批关键参数') < review.index('审批事项与固定依据')
        assert "name='selected_option' value='authorize_execution'" in review
        assert "name='selected_option' value='reject_execution'" in review
        assert f.runtime.approvals.status(binding.object_id).status == 'pending'
        assert f.runtime.artifacts.read(status.approval_request_ref) == original
        assert f.adapter.submits == 0
    finally:
        ui.stop()
