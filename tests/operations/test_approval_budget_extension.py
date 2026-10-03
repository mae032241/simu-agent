"""A human extension is exact, durable, additive and never a second execution."""
from urllib.parse import parse_qs, urlparse

import pytest

from scidiscovery.artifact_agent.approval_ui.app import ApprovalUI
from scidiscovery.artifact_agent.schema.approval import HumanDecision
from tests.operations.test_experiment_approval_handoff import experiment, start
from tests.operations.test_experiment_ui_trajectory import model_for
from tests.operations.test_instance_browser_http import _request
from tests.operations.test_approval_wait_recovery import execution


@pytest.mark.process_e2e
def test_budget_extension_http_roundtrip_replay_recovery_and_scope(tmp_path, monkeypatch):
    f = experiment(tmp_path, monkeypatch)
    pending = start(f)
    target = urlparse(pending['review_url'])
    aid = target.path.rsplit('/', 1)[-1]
    token = parse_qs(target.query)['token'][0]
    review = f.runtime.approvals.review(aid, access_token=token)
    eid = execution(f).object_id
    service = f.runtime.executions
    original = f.runtime.artifacts.read(review.request_ref)
    ui = ApprovalUI(f.runtime.approvals, bindings=f.runtime.scheduler_bindings, read_model=model_for(f))
    base = ui.start()
    form = dict(token=token, csrf=review.csrf_token, nonce=review.decision_nonce,
        selected_option='authorize_execution', rationale='Extend this scientific subject.', confirm='confirm',
        additional_wall_time_hours='2.5')
    endpoint = target.path + '/decision'
    try:
        page = _request(base, 'GET', target.path+'?'+target.query)[2].decode()
        assert '追加累计耗时预算' in page and '同一科学主体' in page
        for bad in ({'csrf':'wrong'}, {'selected_option':'reject_execution'},
                    {'additional_wall_time_hours':'NaN'}, {'additional_wall_time_hours':'-1'}):
            assert _request(base, 'POST', endpoint, form={**form, **bad})[0] == 403
            assert f.runtime.approvals.status(aid).status == 'pending'
        # Crash after recording the human decision: an identical HTTP retry repairs
        # the budget projection without approving twice or incrementing twice.
        apply = service.apply_budget_extension
        with monkeypatch.context() as patch:
            patch.setattr(service, 'apply_budget_extension', lambda _: (_ for _ in ()).throw(OSError('interrupted')))
            assert _request(base, 'POST', endpoint, form=form)[0] == 503
        assert f.runtime.approvals.status(aid).status == 'decided'
        for _ in range(2):
            assert _request(base, 'POST', endpoint, form=form)[0] == 303
        apply(aid)
        assert _request(base, 'POST', endpoint, form={**form, 'additional_wall_time_hours':'3'})[0] == 409
        value = service.authorization(eid)
        assert value['allowance']['wall_time_seconds'] == 21600 + 9000
        assert value['per_execution_allowance']['wall_time_seconds'] == 3600
        assert value['allowance']['max_storage_bytes'] == pending['authorization']['allowance']['max_storage_bytes']
        assert f.adapter.submits == 0
        decision = HumanDecision.model_validate_json(f.runtime.artifacts.read(f.runtime.approvals.status(aid).decision_ref))
        assert decision.additional_wall_time_seconds == 9000
        assert f.runtime.artifacts.read(review.request_ref) == original
        assert f.worker.call_tool('worker_experiment_execute', {'action':'advance'})['state'] == 'running'
        assert f.adapter.submits == 1
        assert service.authorization(eid)['allowance']['wall_time_seconds'] == 30600
        from tests.operations.tcad_policy_fixtures import policy_snapshot
        owner = service.budget_owner(eid)
        admission = policy_snapshot().admission(budget={'wall_time_seconds': 60, 'max_storage_bytes': 1}, budget_key=owner)
        with service._connect() as db:
            assert service._budget_allowance(db, 'tcad_artifact:tcad', admission)['wall_time_seconds'] == 30600
            assert service._budget_allowance(db, 'other', admission)['wall_time_seconds'] == 21600
            other = admission.model_copy(update={'budget_key': 'f'*64})
            assert service._budget_allowance(db, 'tcad_artifact:tcad', other)['wall_time_seconds'] == 21600
        page = _request(base, 'GET', target.path+'?'+target.query)[2].decode()
        assert '用户已追加累计时长' in page and '9,000 秒' in page
    finally:
        ui.stop()
