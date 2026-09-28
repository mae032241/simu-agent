"""Human cancellation closes a pending request without granting execution."""
from urllib.parse import parse_qs, urlparse

import pytest

from scidiscovery.artifact_agent.approval_ui.app import ApprovalUI
from tests.operations.test_experiment_approval_handoff import experiment, start
from tests.operations.test_instance_browser_http import _request


@pytest.mark.process_e2e
@pytest.mark.parametrize('prior_decision', [None, 'authorize_execution', 'reject_execution'])
def test_ui_cancellation_is_authenticated_idempotent_and_pending_only(tmp_path, monkeypatch, prior_decision):
    f = experiment(tmp_path, monkeypatch)
    pending = start(f)
    parsed = urlparse(pending['review_url'])
    approval_id = parsed.path.rsplit('/', 1)[-1]
    token = parse_qs(parsed.query)['token'][0]
    review = f.runtime.approvals.review(approval_id, access_token=token)
    before = f.runtime.artifacts.read(review.request_ref)
    assert all(o.option_id != 'cancel_approval' for o in review.request.options)
    ui = ApprovalUI(f.runtime.approvals)
    base = ui.start()
    endpoint = f'/review/{approval_id}/decision'
    form = dict(token=token, csrf=review.csrf_token, nonce=review.decision_nonce,
        selected_option='cancel_approval', rationale='This pending request is obsolete.', confirm='confirm')
    try:
        html = _request(base, 'GET', parsed.path+'?'+parsed.query)[2]
        assert b'data-cancel-approval' in html
        assert _request(base, 'POST', endpoint, form={**form, 'csrf':'wrong'})[0] == 403
        assert _request(base, 'POST', endpoint, form={**form, 'token':'wrong'})[0] == 403
        assert f.runtime.approvals.status(approval_id).status == 'pending'
        if prior_decision:
            assert _request(base, 'POST', endpoint, form={**form,'selected_option':prior_decision})[0] == 303
            original = f.runtime.approvals.status(approval_id).decision_ref
            assert _request(base, 'POST', endpoint, form=form)[0] == 409
            assert f.runtime.approvals.status(approval_id).decision_ref == original
            assert f.runtime.approvals.status(approval_id).status == 'decided'
        else:
            assert _request(base, 'POST', endpoint, form=form)[0] == 303
            original = f.runtime.approvals.status(approval_id).decision_ref
            assert _request(base, 'POST', endpoint, form=form)[0] == 303
            assert f.runtime.approvals.status(approval_id).decision_ref == original
            assert f.runtime.approvals.status(approval_id).status == 'cancelled_by_human'
            assert _request(base, 'POST', endpoint, form={**form,'selected_option':'authorize_execution'})[0] == 409
            for action in ('status', 'advance'):
                assert f.worker.call_tool('worker_experiment_execute', {'action':action})['state'] == 'authorization_cancelled'
            assert f.adapter.submits == 0
        assert b'data-cancel-approval' not in _request(base, 'GET', parsed.path+'?'+parsed.query)[2]
        assert f.runtime.artifacts.read(review.request_ref) == before
    finally:
        ui.stop()
