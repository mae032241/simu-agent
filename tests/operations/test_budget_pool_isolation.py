"""Grant accounting reads exact pool members before opening decision Artifacts."""
import pytest

from tests.operations.test_instance_archive import archive_system
from tests.operations.test_execution_archive_budget import _policy_executions
from scidiscovery.agent_execution_settings import BudgetExtensionSettings
from scidiscovery.artifact_agent.schema.approval import ApprovalOption, LocalIdentityRef
from scidiscovery.artifact_agent.service.approvals import (
    ApprovalError, ApprovalAccessDenied, BudgetExtensionAccountingError,
)


def grants(system):
    runtime, *_ = system
    ids, admission = _policy_executions(system)
    service = runtime.executions
    service.budget_extension_limits = BudgetExtensionSettings(max_seconds_per_decision=100, max_total_seconds_per_pool=100)
    original = service.request(ids[1])
    other = service.create(executor='fixture', preparation_profile='fixture',
        payload_ref=original.payload_ref, compiled_identity=original.compiled_identity)
    service.authorize_policy(execution_id=other, admission=admission.model_copy(update={'budget_key': 'e'*64}),
        compiled_identity=original.compiled_identity)
    requests = []
    for index, eid in enumerate((*ids, other)):
        aid = f'isolated_grant_{index}'
        launch = runtime.approvals.create_request(approval_id=aid, idempotency_key=aid,
            kind='execution_authorization', subject_refs=service.approval_subject_refs(eid), question='Fixture approval',
            options=(ApprovalOption(option_id='authorize_execution', label='Approve', description='Authorize', requires_rationale=False),
                ApprovalOption(option_id='reject_execution', label='Reject', description='Reject', requires_rationale=False)),
            requested_by=runtime.actor, compiled_identity=service.request(eid).compiled_identity)
        review = runtime.approvals.review(aid, access_token=launch.access_token)
        requests.append(dict(approval_id=aid, access_token=launch.access_token, csrf_token=review.csrf_token,
            decision_nonce=review.decision_nonce, selected_option='authorize_execution', rationale='',
            decided_by=LocalIdentityRef(identity_id='user', display_name='User'), ui_session_id='isolation',
            additional_wall_time_seconds=60))
    return runtime, ids, requests


def seal_without_projection(service, request, monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr(service, 'apply_budget_extension', lambda _: (_ for _ in ()).throw(OSError('projection interrupted')))
        with pytest.raises(OSError):
            service.record_budget_extension_decision(**request)


@pytest.mark.parametrize('missing', ['pointer', 'history', 'reservation'])
def test_missing_policy_does_not_block_foreign_pool_or_erase_signed_grant(archive_system, monkeypatch, missing):
    runtime, ids, requests = grants(archive_system)
    service = runtime.executions
    seal_without_projection(service, requests[0], monkeypatch)
    with service._connect() as db:
        db.execute('DELETE FROM execution_current_policy WHERE execution_id=?', (ids[0],))
        if missing == 'history':
            db.execute('DELETE FROM execution_policy_authorizations WHERE execution_id=?', (ids[0],))
        elif missing == 'reservation':
            db.execute('DELETE FROM execution_budget_reservations WHERE execution_id=?', (ids[0],))
    service.record_budget_extension_decision(**requests[2])
    # The original pool still counts its signed, unprojected 60 seconds.
    with pytest.raises(ApprovalAccessDenied, match='cumulative'):
        service.record_budget_extension_decision(**requests[1])
    assert runtime.approvals.status(requests[1]['approval_id']).status == 'pending'


@pytest.mark.parametrize('projected', [False, True])
def test_bad_decision_is_isolated_and_projected_grants_use_the_ledger(archive_system, monkeypatch, projected):
    runtime, _, requests = grants(archive_system)
    service = runtime.executions
    if projected:
        service.record_budget_extension_decision(**requests[0])
    else:
        seal_without_projection(service, requests[0], monkeypatch)
    ref = runtime.approvals.status(requests[0]['approval_id']).decision_ref
    load = runtime.approvals._load_decision
    def corrupt(original):
        if original == ref:
            raise ApprovalError('fixture corrupt decision')
        return load(original)
    monkeypatch.setattr(runtime.approvals, '_load_decision', corrupt)
    service.record_budget_extension_decision(**requests[2])
    if projected:
        service.record_budget_extension_decision(**{**requests[1], 'additional_wall_time_seconds': 40})
    else:
        with pytest.raises(BudgetExtensionAccountingError, match='当前预算池'):
            service.record_budget_extension_decision(**requests[1])
        assert runtime.approvals.status(requests[1]['approval_id']).status == 'pending'
