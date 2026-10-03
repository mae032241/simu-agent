"""An execution package is not the identity of its scientific review subject."""
import json
import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.operation_contract import DiagnosticError
from tests.operations.test_experiment_approval_handoff import experiment, start
from tests.operations.test_experiment_continuation import submit


def revised_material(f):
    context = f.worker._context('worker_experiment_prepare', f.worker._registered['worker_experiment_prepare'])
    original = f.runs.sealed_material_record(f.runs.status(f.run_id), f.alias)
    payload = f.coordinator._implementation_payload(original)
    material = json.loads(f.runtime.artifacts.read(context.source_descriptor(f.alias).artifact_ref))
    material['explanation'] = 'Revised explanation of the same executable implementation.'
    revised = f.coordinator.seal_implementation(context, payload=f.runtime.artifacts.read(payload),
        scientific_material=canonical_json(material), sources=('research_objective',), private_outputs=('tcad_manifest',))
    assert original['artifact_ref'] != revised['artifact_ref']
    assert f.coordinator._implementation_payload(revised) == payload
    return original, revised


def execution_id(f):
    return f.runtime.scheduler_bindings.list(instance=f.instance.instance_id, namespace='execution',
        name_prefix='experiment-' + f.run_id + '-')[0].object_id


def test_exact_receipt_survives_review_start_collect_and_delivery(tmp_path, monkeypatch):
    f = experiment(tmp_path, monkeypatch, seconds=60)
    original, revised = revised_material(f)
    handoff = f.worker.call_tool('worker_experiment_execute', {'action': 'review', 'implementation': revised['alias']})
    assert handoff['review']['subject_artifact_name'] == revised['artifact_name']
    f.alias = revised['alias']
    assert start(f)['state'] == 'running'
    eid = execution_id(f)
    assert f.coordinator._execution_implementation_record(f.runs.status(f.run_id), eid)['artifact_ref'] == revised['artifact_ref']
    assert start(f)['state'] == 'running' and f.adapter.submits == 1
    f.adapter.state = 'succeeded'
    f.worker.call_tool('worker_experiment_execute', {'action': 'advance'})
    collected = f.worker.call_tool('worker_experiment_execute', {'action': 'collect'})
    assert collected['state'] == 'collected'
    assert f.worker.call_tool('worker_experiment_execute', {'action': 'status'})['state'] == 'collected'
    validity = f.worker.call_tool('worker_experiment_stage', {'stage':'validity',
        'conclusion':'Retained fixture observations with exact implementation.', 'materials':[collected['reference']]})
    result = submit(f, [f.alias, collected['reference'], validity['reference']])
    assert result['state'] == 'completed', result


def test_later_material_revision_does_not_rebind_started_execution(tmp_path, monkeypatch):
    f = experiment(tmp_path, monkeypatch, seconds=60)
    assert start(f)['state'] == 'running'
    original, revised = revised_material(f)
    eid = execution_id(f)
    assert f.coordinator._execution_implementation_record(f.runs.status(f.run_id), eid)['artifact_ref'] == original['artifact_ref']
    with pytest.raises(DiagnosticError) as caught:
        f.worker.call_tool('worker_experiment_execute', {'action':'start', 'implementation':revised['alias']})
    assert caught.value.details[0]['code'] == 'experiment_execution_implementation_changed'
    assert f.runs.status(f.run_id).state == 'running' and f.adapter.submits == 1


def test_legacy_ambiguous_package_is_repairable_and_does_not_choose_latest(tmp_path, monkeypatch):
    f = experiment(tmp_path, monkeypatch, seconds=60)
    original, revised = revised_material(f)
    with pytest.raises(DiagnosticError) as caught:
        f.coordinator._run_implementation_record(f.runs.status(f.run_id), f.coordinator._implementation_payload(original))
    assert caught.value.details[0]['code'] == 'experiment_implementation_ambiguous'
    from scidiscovery.artifact_agent.service.submission_errors import classify_submission_error
    assert classify_submission_error(caught.value).disposition == 'reject'
    assert f.runs.status(f.run_id).state == 'running'


def test_revision_cannot_inherit_independent_review_of_same_package(tmp_path, monkeypatch):
    from dataclasses import replace
    from tests.operations.test_task_execution_review import review
    f = experiment(tmp_path, monkeypatch, seconds=60)
    original, revised = revised_material(f)
    name = f.runs.publish_sealed_material(f.runs.status(f.run_id), original['alias'])
    review(f, 'original-review', name, 'pass')
    run = f.runs.status(f.run_id)
    run = replace(run, recovery_policy={**run.recovery_policy, 'require_execution_review':True})
    assert f.coordinator._required_review(run, original) is not None
    with pytest.raises(DiagnosticError) as caught:
        f.coordinator._required_review(run, revised)
    assert caught.value.details[0]['code'] == 'experiment_execution_review_required'


def test_historical_execution_without_receipt_identity_keeps_unique_binding(tmp_path, monkeypatch):
    from tests.operations.test_experiment_continuation import continuation
    from tests.operations.test_lifecycle_diagnostic_repair import pending_execution
    f = continuation(tmp_path, monkeypatch)
    eid = pending_execution(f)
    recovered = f.coordinator._execution_implementation_record(f.runs.status(f.run_id), eid)
    assert recovered['artifact_ref'] == f.implementation['artifact_ref']
