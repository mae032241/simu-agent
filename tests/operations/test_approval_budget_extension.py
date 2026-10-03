"""A human extension is exact, durable, additive and never a second execution."""
from urllib.parse import parse_qs, urlparse

import pytest

from scidiscovery.artifact_agent.approval_ui.app import ApprovalUI
from scidiscovery.artifact_agent.schema.approval import HumanDecision
from tests.operations.test_experiment_approval_handoff import experiment, start
from tests.operations.test_experiment_ui_trajectory import model_for
from tests.operations.test_instance_browser_http import _request
from tests.operations.test_approval_wait_recovery import execution
from tests.operations.test_instance_archive import archive_system


@pytest.mark.parametrize('legacy', [True, False])
def test_sealed_zero_extension_decisions_survive_upgrade_and_retry(tmp_path, monkeypatch, legacy):
    import hashlib
    import json
    from scidiscovery.artifact_agent.schema.common import canonical_json
    from scidiscovery.artifact_agent.schema.approval import LocalIdentityRef
    from tests.operations.test_r4_execution_approval_identity import (
        _setup, _create_effect, _reopen,
    )
    runtime, instance, adapter, _, root, catalog = _setup(tmp_path)
    name = 'historical_decision'
    _create_effect(root, name=name)
    aid = runtime.scheduler_bindings.resolve(instance=instance.instance_id,
        namespace='approval', name=name + '.approval')
    access = parse_qs(urlparse(runtime.approvals.status(aid).review_path).query)['token'][0]
    review = runtime.approvals.review(aid, access_token=access)
    request = dict(approval_id=aid, access_token=access, csrf_token=review.csrf_token,
        decision_nonce=review.decision_nonce, selected_option='authorize_execution', rationale='',
        decided_by=LocalIdentityRef(identity_id='fixture_reviewer', display_name='Fixture reviewer'),
        ui_session_id='upgrade-test')

    # Produce real sealed decisions with the two deployed wire layouts, without
    # changing CAS bytes or relaxing the production canonicality check.
    def wire_bytes(decision):
        document = decision.model_dump(mode='json')
        if legacy:
            document.pop('additional_wall_time_seconds')
        return canonical_json(document)

    with monkeypatch.context() as patch:
        patch.setattr(HumanDecision, 'canonical_json', wire_bytes)
        runtime.approvals.record_ui_decision(**request)
    ref = runtime.approvals.status(aid).decision_ref
    raw = runtime.artifacts.read(ref)
    assert ('additional_wall_time_seconds' not in json.loads(raw)) is legacy
    runtime, root = _reopen(tmp_path, instance, adapter, catalog)
    runtime.approvals.review(aid, access_token=access)
    loaded = runtime.approvals._load_decision(ref)
    assert loaded.additional_wall_time_seconds == 0
    assert loaded.canonical_json() == raw
    assert loaded.content_hash == hashlib.sha256(raw).hexdigest()
    assert runtime.approvals.record_ui_decision(**request) == ref
    assert runtime.approvals.status(aid).decision_ref == ref
    assert adapter.submit_count == 0
    from scidiscovery.artifact_agent.service.approvals import ApprovalError
    with monkeypatch.context() as patch:
        patch.setattr(runtime.artifacts, 'read', lambda _: json.dumps(json.loads(raw), indent=2).encode())
        with pytest.raises(ApprovalError, match='not canonical'):
            runtime.approvals._load_decision(ref)


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
        from scidiscovery.artifact_agent.service.approvals import BudgetExtensionAccountingError
        with monkeypatch.context() as patch:
            def unavailable(*_):
                raise BudgetExtensionAccountingError('无法核对当前预算池的历史授权')
            patch.setattr(service, 'validate_budget_extension', unavailable)
            status, _, body = _request(base, 'POST', endpoint, form=form)
            assert status == 409 and '当前预算池' in body.decode()
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


def test_grant_caps_include_sealed_unprojected_decisions_and_do_not_block_replay(archive_system, monkeypatch):
    from tests.operations.test_execution_archive_budget import _policy_executions
    from scidiscovery.agent_execution_settings import BudgetExtensionSettings
    from scidiscovery.artifact_agent.schema.approval import ApprovalOption, LocalIdentityRef
    from scidiscovery.artifact_agent.service.approvals import ApprovalAccessDenied
    runtime, _, _, _ = archive_system
    ids, _ = _policy_executions(archive_system)
    service = runtime.executions
    service.budget_extension_limits = BudgetExtensionSettings(max_seconds_per_decision=1800, max_total_seconds_per_pool=3000)
    requests = []
    for index, eid in enumerate(ids):
        aid = f'grant_{index}'
        launch = runtime.approvals.create_request(approval_id=aid, idempotency_key=aid, kind='execution_authorization',
            subject_refs=service.approval_subject_refs(eid), question='Extend this exact subject?',
            options=(ApprovalOption(option_id='authorize_execution', label='Approve', description='Authorize.', requires_rationale=False),
                ApprovalOption(option_id='reject_execution', label='Reject', description='Reject.', requires_rationale=False)),
            requested_by=runtime.actor, compiled_identity=service.request(eid).compiled_identity)
        view = runtime.approvals.review(aid, access_token=launch.access_token)
        requests.append(dict(approval_id=aid, access_token=launch.access_token, csrf_token=view.csrf_token,
            decision_nonce=view.decision_nonce, selected_option='authorize_execution', rationale='',
            decided_by=LocalIdentityRef(identity_id='user', display_name='User'), ui_session_id='caps'))
    with pytest.raises(ApprovalAccessDenied, match='execution policy service'):
        runtime.approvals.record_ui_decision(**requests[0], additional_wall_time_seconds=1800)
    with pytest.raises(ApprovalAccessDenied, match='per-decision'):
        service.record_budget_extension_decision(**requests[0], additional_wall_time_seconds=1801)
    with monkeypatch.context() as patch:
        patch.setattr(service, 'apply_budget_extension', lambda _: (_ for _ in ()).throw(OSError('interrupted')))
        with pytest.raises(OSError):
            service.record_budget_extension_decision(**requests[0], additional_wall_time_seconds=1800)
    assert runtime.approvals.status('grant_0').status == 'decided'
    with pytest.raises(ApprovalAccessDenied, match='cumulative'):
        service.record_budget_extension_decision(**requests[1], additional_wall_time_seconds=1500)
    assert runtime.approvals.status('grant_1').status == 'pending'
    service.record_budget_extension_decision(**requests[1], additional_wall_time_seconds=1200)
    service.budget_extension_limits = BudgetExtensionSettings(max_seconds_per_decision=0, max_total_seconds_per_pool=0)
    for _ in range(2):
        service.record_budget_extension_decision(**requests[0], additional_wall_time_seconds=1800)
    assert service.authorization(ids[0])['allowance']['wall_time_seconds'] == 3600 + 3000
