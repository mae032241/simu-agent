"""An explicit scientific task requirement, never a global stage-review gate."""
import json
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_root_shared import RootToolError
from scidiscovery.operation_contract import DiagnosticError
from tests.operations.test_experiment_continuation import continuation


@pytest.mark.parametrize("task", ["ordinary_agent", "native_experiment"])
def test_false_review_requirement_is_noop_without_execution_capability(tmp_path, task):
    if task == "ordinary_agent":
        from tests.operations.test_local_worker_contracts import _system
        _, runtime, instance, root = _system(tmp_path)
        request = {"name": "observation", "operation_id": "blind.csv.observe.v1",
            "inputs": [{"port": "source_table", "artifact_names": ["source_csv"]}],
            "instruction": "Observe the exact CSV."}
    else:
        from tests.operations.test_experiment_goal_origin import _setup, _request, _proposal, _complete
        runtime, instance, root = _setup(tmp_path, native_only=True)
        root.call_tool("artifact_ingest_text", {"name": "task", "text": "Compute 2+2 and retain the result."})
        proposal = _proposal(hypothesis_keys=("mechanism",))
        proposal.pop("research_objective_key")
        subject = _complete(runtime, root, "hypothesis", "science.hypothesis.propose.v1",
            {"subject": "task"}, proposal)
        request = _request(subject)
    assert runtime.runs.operation_catalog.operation(request["operation_id"]).spec.executor.capability is None
    omitted = root.call_tool("operation_preflight", request)
    explicit = root.call_tool("operation_preflight", {**request, "require_execution_review": False})
    assert omitted["admissible"] is True, omitted
    assert explicit["admissible"] is True, explicit
    assert explicit["normalized_request"] == omitted["normalized_request"]
    required = root.call_tool("operation_preflight", {**request, "require_execution_review": True})
    assert required["admissible"] is False
    assert "execution_review_not_applicable" in json.dumps(required)
    with pytest.raises(RootToolError, match="execution_review_not_applicable"):
        root.call_tool("operation_invoke", {**request, "require_execution_review": True})
    created = root.call_tool("operation_invoke", {**request, "require_execution_review": False})
    assert created["result"]["state"] == "queued"
    run_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id,
        namespace="run", name=request["name"])
    assert not runtime.runs.status(run_id).recovery_policy.get("require_execution_review")
    assert root.call_tool("operation_invoke", request)["result"]["state"] == "queued"
    assert runtime.scheduler_bindings.resolve(instance=instance.instance_id,
        namespace="run", name=request["name"]) == run_id


def review(f, name, subject, verdict, *, request=None):
    invocation = request or {"name": name, "operation_id": "science.object.review.v1",
        "inputs": [{"port": "subject", "artifact_names": [subject]}], "instruction": "Assess this exact implementation."}
    name = invocation["name"]
    result = f.root.call_tool("operation_invoke", invocation)
    assert result["result"]["state"] == "queued", result
    run_id = f.runtime.scheduler_bindings.resolve(instance=f.instance.instance_id, namespace="run", name=name)
    f.runs.worker_connections.attach(run_id=run_id, platform_session="review-session", thread_id=name)
    compiled = f.catalog.operation("science.object.review.v1")
    worker = LocalWorkerMCPRouter(f.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest,
        run_id=run_id, trusted_caller=("review-session", name))
    opened = worker.call_tool("worker_open_assignment", {})
    Path(opened["output_directory"], "result.json").write_text(json.dumps({"schema_version": 1,
        "payload": {"verdict": verdict, "summary": "Exact fixture assessment."}}))
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"


def test_explicit_review_blocks_missing_wrong_subject_and_negative_verdict(tmp_path, monkeypatch):
    f = continuation(tmp_path, monkeypatch, require_execution_review=True)
    assert f.runs.status(f.run_id).recovery_policy["require_execution_review"] is True
    assignment = json.loads((f.workspace / "assignment.json").read_bytes())
    assert assignment["execution_requirements"]["independent_implementation_review"] == "required"
    command = {"action": "start", "implementation": f.alias}
    def blocked(code):
        with pytest.raises(DiagnosticError) as caught:
            f.worker.call_tool("worker_experiment_execute", command)
        assert caught.value.details[0]["code"] == code
        assert not f.runtime.scheduler_bindings.list(instance=f.instance.instance_id, namespace="execution",
            name_prefix="experiment-" + f.run_id + "-")
    blocked("experiment_execution_review_required")
    review(f, "wrong-subject", "observe.output", "pass")
    blocked("experiment_execution_review_required")
    subject = next(i.artifact_name for i in f.runs.status(f.run_id).inputs if i.source_name == f.alias)
    review(f, "negative-review", subject, "revise")
    blocked("experiment_execution_review_not_passed")
    review(f, "passing-review", subject, "pass")
    adapter = f.coordinator.bridge._adapter("tcad_artifact:tcad")
    adapter.lookup_submission = lambda _: None
    adapter.state = "running"
    adapter.submit = lambda *args, **kwargs: ("new-reviewed-execution", "running")
    assert f.worker.call_tool("worker_experiment_execute", command)["state"] == "running"
    bound = f.runtime.scheduler_bindings.list(instance=f.instance.instance_id, namespace="execution",
        name_prefix="experiment-" + f.run_id + "-")[0]
    envelope = f.runtime.artifacts.get_by_id(f.runtime.executions.request_artifact_id(bound.object_id))
    assert "implementation_review" in envelope.labels


def test_review_requirement_is_in_normalized_request_and_cannot_be_removed_on_recovery(tmp_path, monkeypatch):
    f = continuation(tmp_path, monkeypatch, require_execution_review=True)
    current = f.runs.status(f.run_id)
    f.runs.record_failure(f.run_id, reason="fixture stop", expected_state=current.state,
        expected_last_activity_at=current.last_activity_at)
    request = {**f.invocation, "name": "recovered", "resume_from": "continuation"}
    request.pop("require_execution_review")
    check = f.root.call_tool("operation_preflight", request)
    assert check["admissible"] is True, check
    assert check["normalized_request"]["require_execution_review"] is True
    bad = f.root.call_tool("operation_preflight", {**request, "require_execution_review": False})
    assert bad["admissible"] is False
    assert "execution_review_requirement_immutable" in json.dumps(bad)
    with pytest.raises(RootToolError, match="execution_review_requirement_immutable"):
        f.root.call_tool("operation_invoke", {**request, "require_execution_review": False})
    reply = f.root.call_tool("operation_invoke", check["normalized_request"])
    assert reply["result"]["state"] == "queued", reply


def test_live_prepare_review_and_same_run_execution_close_the_loop(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    from scidiscovery.artifact_agent.service.run_records import RunStateConflict
    f = continuation(tmp_path, monkeypatch, require_execution_review=True)
    authored = json.loads(f.runtime.artifacts.read(ArtifactRef.model_validate(f.implementation['artifact_ref'])))['implementation']
    path = f.workspace / 'scratch/experiment.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(authored))
    prepared = f.worker.call_tool('worker_experiment_prepare', {})
    alias = prepared['implementation']
    subject = prepared['artifact_name']
    assert f.runs.status(f.run_id).output_ref is None
    navigation = f.root.call_tool('run_status', {'name':'continuation', 'intent':'navigation', 'index_limit':1})
    assert navigation['evidence_outputs'] == [{'artifact_name':subject, 'schema':'opaque'}]
    assert navigation['evidence_outputs_status'] == 'sealed_materials_not_final_report'
    assert navigation['output_artifact_name'] is None
    assert f.worker.call_tool('worker_experiment_prepare', {})['state'] == 'waiting_for_review'
    command = {'action': 'start', 'implementation': alias}
    assert f.worker.call_tool('worker_experiment_execute', command)['state'] == 'waiting_for_review'
    handoff = f.worker.call_tool('worker_experiment_execute', {'action':'review', 'implementation':alias})
    assert handoff['review'] == prepared['review']
    assert handoff['review']['subject_artifact_name'] == subject
    preview = f.root.call_tool('run_status', {'name':'continuation', 'stage_reference':alias})['sealed_stages']['material']
    assert preview['source_artifact_name'] == subject
    reply = f.root.call_tool('operation_invoke', handoff['review']['request'])
    assert reply['result']['state'] == 'queued', reply
    reviewer_id = f.runtime.scheduler_bindings.resolve(instance=f.instance.instance_id,
        namespace='run', name=handoff['review']['request']['name'])
    with pytest.raises(RunStateConflict, match='different Agent'):
        f.runs.worker_connections.attach(run_id=reviewer_id, platform_session='continuation-fixture', thread_id='next-owner')
    f.runs.worker_connections.attach(run_id=reviewer_id, platform_session='independent-fixture', thread_id='reviewer')
    compiled = f.catalog.operation('science.object.review.v1')
    reviewer = LocalWorkerMCPRouter(f.runs, operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest, run_id=reviewer_id, trusted_caller=('independent-fixture', 'reviewer'))
    opened = reviewer.call_tool('worker_open_assignment', {})
    Path(opened['output_directory'], 'result.json').write_text(json.dumps({'schema_version':1,
        'payload':{'verdict':'pass', 'summary':'Fixture implementation is consistent.'}}))
    assert reviewer.call_tool('worker_submit_result', {})['state'] == 'completed'
    adapter = f.coordinator.bridge._adapter('tcad_artifact:tcad')
    adapter.lookup_submission = lambda _: None
    adapter.state = 'running'
    adapter.submit = lambda *args, **kwargs: ('reviewed-live-subject', 'running')
    assert f.worker.call_tool('worker_experiment_execute', command)['state'] == 'running'
    authored['files'][0]['content'] += '\n# new scientific implementation'
    path.write_text(json.dumps(authored))
    revised = f.worker.call_tool('worker_experiment_prepare', {})
    assert revised['artifact_name'] != subject
    first = f.root.call_tool('run_status', {'name':'continuation', 'intent':'navigation', 'index_limit':1})
    second = f.root.call_tool('run_status', {'name':'continuation', 'intent':'navigation',
        'index_limit':1, 'index_offset':first['evidence_outputs_next_offset']})
    assert first['evidence_outputs'][0]['artifact_name'] == subject
    assert second['evidence_outputs'][0]['artifact_name'] == revised['artifact_name']
    assert second['evidence_outputs_next_offset'] is None
    assert 'evidence_outputs' not in f.root.call_tool('run_status', {'name':'continuation', 'intent':'status'})
    assert f.worker.call_tool('worker_experiment_execute', {'action':'start', 'name':'new-version',
        'implementation':revised['implementation']})['state'] == 'waiting_for_review'
    bindings = f.runtime.scheduler_bindings.list(instance=f.instance.instance_id, namespace='execution',
        name_prefix='experiment-' + f.run_id + '-')
    assert len(bindings) == 1
    assert f.runs.status(f.run_id).state == 'running'


def test_stage_names_survive_failed_owner_and_old_receipt_can_be_published_explicitly(tmp_path, monkeypatch):
    f = continuation(tmp_path, monkeypatch, require_execution_review=True)
    stage = f.worker.call_tool('worker_experiment_stage', {'stage':'design', 'conclusion':'Exact live design.'})
    record = f.runs.sealed_material_record(f.runs.status(f.run_id), stage['reference'])
    subject = stage['artifact_name']
    assert f.runtime.scheduler_bindings.resolve(instance=f.instance.instance_id, namespace='artifact', name=subject) == record['artifact_ref']['artifact_id']
    # Emulate a receipt sealed by the previous deployment: reads do not create names.
    import sqlite3
    with sqlite3.connect(f.runs.scheduler_database_path) as db:
        db.execute('DELETE FROM scheduler_bindings WHERE instance=? AND namespace=? AND name=?',
            (f.instance.instance_id, 'artifact', subject))
    preview = f.root.call_tool('run_status', {'name':'continuation', 'stage_reference':stage['reference']})
    assert 'source_artifact_name' not in preview['sealed_stages']['material']
    assert f.runs.publish_sealed_material(f.runs.status(f.run_id), stage['reference']) == subject
    current = f.runs.status(f.run_id)
    f.runs.record_failure(f.run_id, reason='fixture interruption', expected_state=current.state,
        expected_last_activity_at=current.last_activity_at)
    review(f, 'review-failed-owners-stage', subject, 'pass')
    preview = f.root.call_tool('run_status', {'name':'continuation', 'stage_reference':stage['reference']})
    assert preview['sealed_stages']['material']['source_artifact_name'] == subject
    navigation = f.root.call_tool('run_status', {'name':'continuation', 'intent':'navigation'})
    assert navigation['evidence_outputs'] == [{'artifact_name':subject, 'schema':'opaque'}]


def test_seal_and_public_binding_roll_back_together(tmp_path, monkeypatch):
    f = continuation(tmp_path, monkeypatch)
    before = f.runs.tool_evidence(f.run_id)
    def unavailable(*args, **kwargs):
        raise RuntimeError('fixture binding transaction failure')
    with monkeypatch.context() as patch:
        patch.setattr(f.runs, '_bind_evidence_output', unavailable)
        with pytest.raises(DiagnosticError) as caught:
            f.worker.call_tool('worker_experiment_stage', {'stage':'design', 'conclusion':'Atomic handoff.'})
    assert caught.value.details[0]['code'] == 'runtime_failure'
    assert f.runs.tool_evidence(f.run_id) == before
    sealed = f.worker.call_tool('worker_experiment_stage', {'stage':'design', 'conclusion':'Atomic handoff.'})
    assert sealed['artifact_name']
    assert len(f.runs.tool_evidence(f.run_id)) == len(before) + 1


def test_generated_review_request_fits_public_name_contract():
    from types import SimpleNamespace
    from scidiscovery.artifact_agent.interfaces.mcp_root import OperationCallInput
    from scidiscovery.artifact_agent.service.experiment_execution import ExperimentExecution
    names = ['a' * 256, 'a' * 255 + 'b']
    requests = []
    for name in names:
        service = ExperimentExecution(runs=SimpleNamespace(publish_sealed_material=lambda *args: name,
            request_implementation_review=lambda *args: None, review_wait=lambda _: {'state':'requested'}),
            executions=None, bridge=None, collection=None, approval_base_url=None)
        request = service.review_handoff(SimpleNamespace(run_id='fixture-owner', recovery_policy={'require_execution_review':True}),
            {'alias':'material', 'artifact_ref':{'artifact_id':'art_'+'a'*32, 'sha256':'a'*64, 'kind':'fixture', 'schema_id':'fixture.v1'}})['request']
        OperationCallInput.model_validate_json(json.dumps(request))
        assert request['inputs'][0]['artifact_names'] == [name]
        requests.append(request['name'])
    assert requests[0] != requests[1]
