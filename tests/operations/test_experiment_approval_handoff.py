"""Worker execution -> approval UI -> exact execution authorization regressions."""
import http.client
import json
from urllib.parse import parse_qs, urlencode, urlparse

import pytest

from scidiscovery.artifact_agent.approval_ui.app import ApprovalUI
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from tests.operations.test_experiment_continuation import continuation
from tests.operations.tcad_policy_fixtures import policy_snapshot


def experiment(tmp_path, monkeypatch, *, seconds=5400):
    from tcad_artifact.execution_policy import execution_admission
    from tcad_artifact.project_packager import ExecutionPackage
    f = continuation(tmp_path, monkeypatch)
    body = json.loads(f.runtime.artifacts.read(ArtifactRef.model_validate(f.implementation['artifact_ref'])))
    body['implementation']['resource_limits'].update(wall_time_seconds=seconds, max_storage_bytes=1800000000)
    (f.workspace / 'scratch/experiment.json').write_bytes(canonical_json(body['implementation']))
    f.alias = f.worker.call_tool('worker_experiment_prepare', {})['implementation']
    f.adapter = f.coordinator.bridge._adapter('tcad_artifact:tcad')
    f.adapter.submits = 0
    f.adapter.state = 'running'
    monkeypatch.setattr(f.adapter, 'lookup_submission', lambda _: ('next-external', f.adapter.state) if f.adapter.submits else None)
    def submit(*args, **kwargs):
        f.adapter.submits += 1
        return 'next-external', f.adapter.state
    monkeypatch.setattr(f.adapter, 'submit', submit)
    monkeypatch.setattr(f.adapter, 'execution_admission', lambda payload, **kwargs:
        execution_admission(policy_snapshot(), ExecutionPackage.model_validate_json(payload, strict=True)))
    f.coordinator.approval_base_url = 'http://127.0.0.1:8765'
    return f


def decide(f, result, selected):
    parsed = urlparse(result['review_url'])
    approval_id = parsed.path.rsplit('/', 1)[-1]
    token = parse_qs(parsed.query)['token'][0]
    review = f.runtime.approvals.review(approval_id, access_token=token)
    ui = ApprovalUI(f.runtime.approvals)
    base = ui.start()
    try:
        host = urlparse(base)
        connection = http.client.HTTPConnection(host.hostname, host.port, timeout=5)
        connection.request('GET', parsed.path + '?' + parsed.query)
        response = connection.getresponse()
        html = response.read().decode()
        assert response.status == 200 and selected in html
        form = urlencode(dict(token=token, csrf=review.csrf_token, nonce=review.decision_nonce,
            selected_option=selected, rationale='Fixture human decision for this exact execution.', confirm='confirm'))
        connection.request('POST', f'/review/{approval_id}/decision', body=form,
            headers={'Origin':base, 'Content-Type':'application/x-www-form-urlencoded'})
        response = connection.getresponse()
        response.read()
        assert response.status == 303
        connection.close()
    finally:
        ui.stop()
    return f.runtime.approvals.status(approval_id)


def start(f):
    return f.worker.call_tool('worker_experiment_execute', {'action':'start', 'implementation':f.alias})


def test_worker_approval_ui_accepts_and_resumes_exactly_once(tmp_path, monkeypatch):
    f = experiment(tmp_path, monkeypatch)
    first = start(f)
    assert first['state'] == 'awaiting_authorization'
    assert first['authorization']['budget']['wall_time_seconds'] == 5400
    assert first['authorization']['allowance']['wall_time_seconds'] == 3600
    name = first['approval_name']
    assert f.root.call_tool('approval_status', {'name':name})['status'] == 'pending'
    assert f.adapter.submits == 0
    again = f.worker.call_tool('worker_experiment_execute', {'action':'advance'})
    assert again['review_url'] == first['review_url'] and again['approval_name'] == name
    before = f.runtime.approvals.list_requests()
    status = f.worker.call_tool('worker_experiment_execute', {'action':'status'})
    assert status['state'] == 'awaiting_authorization'
    assert f.runtime.approvals.list_requests() == before
    decision = decide(f, first, 'authorize_execution')
    assert decision.status == 'decided'
    assert f.root.call_tool('approval_status', {'name':name})['selected_option'] == 'authorize_execution'
    assert f.worker.call_tool('worker_experiment_execute', {'action':'advance'})['state'] == 'running'
    assert f.worker.call_tool('worker_experiment_execute', {'action':'advance'})['state'] == 'running'
    assert f.adapter.submits == 1


def test_in_policy_worker_execution_needs_no_approval(tmp_path, monkeypatch):
    f = experiment(tmp_path, monkeypatch, seconds=60)
    before = f.runtime.approvals.list_requests()
    assert start(f)['state'] == 'running'
    assert f.adapter.submits == 1 and f.runtime.approvals.list_requests() == before


def test_worker_ui_rejection_stays_terminal_without_submission(tmp_path, monkeypatch):
    f = experiment(tmp_path, monkeypatch)
    first = start(f)
    decide(f, first, 'reject_execution')
    before = f.runtime.approvals.list_requests()
    for action in ('advance', 'status'):
        result = f.worker.call_tool('worker_experiment_execute', {'action':action})
        assert result['state'] == 'authorization_rejected'
        assert 'review_url' not in result
    assert f.adapter.submits == 0 and f.runtime.approvals.list_requests() == before


@pytest.mark.parametrize('kind', ['execution_authorization', 'scientific_qualification'])
def test_existing_worker_approve_receipt_resumes_without_rewriting_human_decision(tmp_path, monkeypatch, kind):
    from scidiscovery.artifact_agent.schema.approval import ApprovalOption
    f = experiment(tmp_path, monkeypatch)
    create = f.runtime.approvals.create_request
    def historical(**kwargs):
        kwargs['kind'] = kind
        kwargs['options'] = tuple(ApprovalOption(option_id='approve' if i == 0 else 'reject',
            label=o.label, description=o.description, requires_rationale=o.requires_rationale)
            for i,o in enumerate(kwargs['options']))
        return create(**kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(f.runtime.approvals, 'create_request', historical)
        first = start(f)
    if kind == 'execution_authorization':
        # The deployed Worker path also omitted the scheduler binding.
        with f.runtime.scheduler_bindings._connect() as connection:
            connection.execute("DELETE FROM scheduler_bindings WHERE namespace='approval'")
        pending = f.worker.call_tool('worker_experiment_execute', {'action':'advance'})
        assert pending['review_url'] == first['review_url']
        assert f.root.call_tool('approval_status', {'name':pending['approval_name']})['status'] == 'pending'
    decision = decide(f, first, 'approve')
    raw = f.runtime.artifacts.read(decision.decision_ref)
    if kind == 'execution_authorization':
        from scidiscovery.artifact_agent.service.executions import ExecutionApprovalError
        approval_id = urlparse(first['review_url']).path.rsplit('/', 1)[-1]
        original = f.runtime.executions.request(approval_id.removeprefix('apr_'))
        f.runtime.executions.create(executor=original.executor, preparation_profile=original.preparation_profile,
            payload_ref=original.payload_ref, execution_id='exe_other_request', compiled_identity=original.compiled_identity)
        with pytest.raises(ExecutionApprovalError, match='exact request and payload'):
            f.runtime.executions.authorize(execution_id='exe_other_request', approval_id=approval_id,
                compiled_identity=original.compiled_identity)
    expected = 'running' if kind == 'execution_authorization' else 'authorization_rejected'
    assert f.worker.call_tool('worker_experiment_execute', {'action':'advance'})['state'] == expected
    assert f.adapter.submits == (1 if kind == 'execution_authorization' else 0)
    assert f.runtime.artifacts.read(decision.decision_ref) == raw
