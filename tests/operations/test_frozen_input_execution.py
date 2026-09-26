"""Public-entry regressions for exact input identities across executor kinds."""
from __future__ import annotations
import json
from dataclasses import replace
import pytest
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL
from scidiscovery.general_science_components import Components, _intake_split
from scidiscovery.general_science_control_operations import _input
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.spec import CallableComponent, CollectionSpec, ComponentRef, InputDerivationSpec
from tests.operations.test_general_transform_operations import _root, _register, _intake
from tests.operations.test_historical_compatibility_paths import _complete, _artifact
from curve_score.plugin import PLUGIN as CURVE
from tcad_artifact.plugin import PLUGIN as TCAD


def _port(name, description, schema, **kwargs):
    base = _input(name, description, 'scidiscovery.scientific-foundation.v1' if schema == 'scidiscovery.tool-evidence-manifest.v1' else schema, **kwargs)
    return base.model_copy(update={'schema_id': schema, 'schema_resource': ComponentRef('tool_evidence_schema')}) if schema == 'scidiscovery.tool-evidence-manifest.v1' else base


def _system(tmp_path, monkeypatch, *, hidden_transform=False, consumer=None):
    operations = []
    for op in GENERAL.operations:
        if op.operation_id == 'science.intake.split.v1' and hidden_transform:
            proof = _port('proof', 'Exact private producer proof.', 'scidiscovery.tool-evidence-manifest.v1',
                usage='evidence_inventory', derivation=InputDerivationSpec(
                    anchor_port='scientific_intake', producer_output_port='recovery_manifest_output'))
            op = op.model_copy(update={'inputs': (*op.inputs, proof)})
        if op.operation_id == 'science.intake.split.v1' and consumer == 'collection':
            outputs = (op.outputs[0], op.outputs[1].model_copy(update={
                'min_items': 2, 'max_items': 2, 'collection': CollectionSpec(max_total_bytes=1024*1024)}))
            op = op.model_copy(update={'outputs': outputs, 'limits': op.limits.model_copy(update={'max_files': 3})})
        if op.operation_id == 'science.evidence.extract.v1' and consumer:
            anchor = _input('frame_anchor', 'Exact transform primary.', 'scidiscovery.problem-frame.v1', min_items=0, usage='prior_signal')
            rule = InputDerivationSpec(anchor_port='frame_anchor',
                producer_input_path=('scientific_intake',) if consumer == 'composed' else (),
                producer_output_port='recovery_manifest_output' if consumer == 'composed' else 'scientific_foundation')
            hidden = _port('origin', 'Exact derived source.',
                'scidiscovery.tool-evidence-manifest.v1' if consumer == 'composed' else 'scidiscovery.scientific-foundation.v1',
                min_items=0, max_items=2 if consumer == 'collection' else 1,
                usage='evidence_inventory', derivation=rule)
            op = op.model_copy(update={'inputs': (*op.inputs, anchor, hidden)})
        operations.append(op)
    def split(values):
        if hidden_transform:
            proof = json.loads(values['proof'][0])
            assert 'bindings' in proof or 'records' in proof
        result = _intake_split({k: values[k] for k in ('scientific_intake', 'evidence_audit')})
        if consumer == 'collection':
            second = json.loads(result['scientific_foundation'][0]); second['title'] += ' second'
            result['scientific_foundation'] += (json.dumps(second).encode(),)
        return result
    monkeypatch.setattr(Components, 'intake_split', CallableComponent('transform', split))
    catalog = compile_catalog((CORE_PLUGIN, GENERAL.model_copy(update={'operations': tuple(operations)}), CURVE, TCAD))
    runtime, instance, root = _root(tmp_path, catalog=catalog)
    runtime.runs.operation_catalog = catalog
    _register(runtime, instance, name='source', raw=b'Exact source.', kind='source', schema='opaque', media_type='text/plain')
    payload = json.loads(_intake().canonical_json().replace(b'"paper"', b'"source_material"'))
    intake = _complete(runtime, root, 'author', 'science.evidence.extract.v1', {'source_material': 'source'}, payload)
    audit_payload = {'checks': [{'check_key': 'source_traceability', 'subject': 'Frozen source',
        'status': 'pass', 'basis': 'Exact source.', 'evidence_keys': ['source_material']}],
        'evidence': [{'source_key': 'source_material', 'source_type': 'frozen_input', 'locator': 'line 1'}]}
    audit = _complete(runtime, root, 'auditor', 'science.evidence.audit.intake.v1',
        {'scientific_intake': intake, 'source_material': 'source'}, audit_payload)
    request = {'name': 'split', 'operation_id': 'science.intake.split.v1', 'inputs': [
        {'port': 'scientific_intake', 'artifact_names': [intake]},
        {'port': 'evidence_audit', 'artifact_names': [audit]}]}
    return runtime, instance, root, request


def test_transform_uses_exact_hidden_ref_after_independent_audit(tmp_path, monkeypatch):
    runtime, instance, root, request = _system(tmp_path, monkeypatch, hidden_transform=True, consumer="sibling")
    assert root.call_tool('operation_preflight', request)['admissible']
    root.call_tool('operation_invoke', request)
    output = _artifact(runtime, instance, 'split')
    assert len(output.parent_refs) == len(set(output.parent_refs)) == 3
    consume = {'name': 'downstream', 'operation_id': 'science.evidence.extract.v1',
        'inputs': [{'port': 'source_material', 'artifact_names': ['source']},
                   {'port': 'frame_anchor', 'artifact_names': ['split']}],
        'instruction': 'Read the exact derived foundation.'}
    assert root.call_tool('operation_preflight', consume)['admissible']
    assert root.call_tool('operation_invoke', consume)['result']['state'] == 'queued'


@pytest.mark.parametrize('equal_bytes', [False, True])
def test_secondary_name_conflict_rejects_before_binding_any_output(tmp_path, monkeypatch, equal_bytes):
    from scidiscovery.artifact_agent.schema.research_cycle import ScientificIntake
    from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerNameConflict

    runtime, instance, root, request = _system(tmp_path, monkeypatch)
    intake = ScientificIntake.model_validate_json(
        runtime.artifacts.read(_artifact(runtime, instance, 'author.output').ref), strict=True)
    text = intake.scientific_foundation.canonical_json().decode() if equal_bytes else 'Unrelated original text.'
    root.call_tool('artifact_ingest_text', {'name': 'split.scientific_foundation', 'text': text})
    before = runtime.scheduler_bindings.list(instance=instance.instance_id, namespace='artifact')
    with pytest.raises(SchedulerNameConflict):
        root.call_tool('operation_invoke', request)
    assert runtime.scheduler_bindings.list(instance=instance.instance_id, namespace='artifact') == before



@pytest.mark.parametrize('legacy', [False, True])
def test_identical_transform_requests_keep_distinct_named_families(tmp_path, monkeypatch, legacy):
    runtime, instance, root, request = _system(tmp_path, monkeypatch)
    if legacy:
        register = runtime.artifacts.register
        def legacy_registration(content, registration, **kwargs):
            # Exercise the durable layout emitted before invocation-name labels.
            labels = {k: v for k, v in registration.labels.items() if k not in {'operation_invocation_name', 'operation_invocation_instance'}}
            return register(content, registration.model_copy(update={'labels': labels}), **kwargs)
        monkeypatch.setattr(runtime.artifacts, 'register', legacy_registration)
    first = root.call_tool('operation_invoke', request)
    root.call_tool('operation_invoke', {**request, 'name': 'second'})
    assert root.call_tool('operation_invoke', request) == first
    for name in ('split', 'second'):
        qualification = {'name': 'qualify_' + name, 'operation_id': 'science.evidence.qualify.v1',
            'inputs': [{'port': 'scientific_foundation', 'artifact_names': [name + '.scientific_foundation']}]}
        assert root.call_tool('operation_preflight', qualification)['admissible']
        assert root.call_tool('operation_invoke', qualification)['executor_kind'] == 'approval'
    from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerNameConflict
    audit_payload = {'checks': [{'check_key': 'source_traceability', 'subject': 'Frozen source',
        'status': 'pass', 'basis': 'Exact source.', 'evidence_keys': ['source_material']}],
        'evidence': [{'source_key': 'source_material', 'source_type': 'frozen_input', 'locator': 'line 1'}]}
    second_audit = _complete(runtime, root, 'auditor_second', 'science.evidence.audit.intake.v1',
        {'scientific_intake': 'author.output', 'source_material': 'source'}, audit_payload)
    changed = {**request, 'inputs': [request['inputs'][0],
        {'port': 'evidence_audit', 'artifact_names': [second_audit]}]}
    assert root.call_tool('operation_preflight', changed)['admissible']
    with pytest.raises(SchedulerNameConflict):
        root.call_tool('operation_invoke', changed)
    assert root.call_tool('operation_invoke', request) == first



@pytest.mark.parametrize('consumer', ['sibling', 'collection', 'composed'])
def test_agent_freezes_declared_exact_derived_sources(tmp_path, monkeypatch, consumer):
    runtime, instance, root, request = _system(tmp_path, monkeypatch, consumer=consumer)
    root.call_tool('operation_invoke', request)
    consume = {'name': 'consume', 'operation_id': 'science.evidence.extract.v1',
        'inputs': [{'port': 'source_material', 'artifact_names': ['source']},
                   {'port': 'frame_anchor', 'artifact_names': ['split']}],
        'instruction': 'Read the exact declared sources.'}
    assert root.call_tool('operation_preflight', consume)['admissible']
    assert root.call_tool('operation_invoke', consume)['result']['state'] == 'queued'
    run_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='run', name='consume')
    derived = [item for item in runtime.runs.status(run_id).inputs if item.port_name == 'origin']
    assert len(derived) == (2 if consumer == 'collection' else 1)
    assert len({item.source_name for item in derived}) == len(derived)
    assert len({item.artifact_ref for item in derived}) == len(derived)


def test_transaction_rejects_wrong_derived_ref_after_root_admission(tmp_path, monkeypatch):
    runtime, instance, root, request = _system(tmp_path, monkeypatch, consumer='sibling')
    root.call_tool('operation_invoke', request)
    root.call_tool('operation_invoke', {**request, 'name': 'other'})
    wrong = _artifact(runtime, instance, 'other.scientific_foundation')
    consume = {'name': 'wrong_origin', 'operation_id': 'science.evidence.extract.v1',
        'inputs': [{'port': 'source_material', 'artifact_names': ['source']},
                   {'port': 'frame_anchor', 'artifact_names': ['split']}], 'instruction': 'Read exact sources.'}
    assert root.call_tool('operation_preflight', consume)['admissible']
    schedule = runtime.runs.schedule
    def altered(bound, **kwargs):
        inputs = tuple(replace(item, artifact=replace(item.artifact, ref=wrong.ref))
            if item.port_name == 'origin' else item for item in bound.inputs)
        return schedule(replace(bound, inputs=inputs), **kwargs)
    monkeypatch.setattr(runtime.runs, 'schedule', altered)
    with pytest.raises(Exception) as rejected:
        root.call_tool('operation_invoke', consume)
    assert 'input_origin_mismatch' in str(rejected.value.__cause__)
    assert not any(binding.name == 'wrong_origin' for binding in runtime.scheduler_bindings.list(
        instance=instance.instance_id, namespace='run'))


def test_foreign_named_copies_cannot_supply_composed_private_origin(tmp_path, monkeypatch):
    runtime, instance, root, request = _system(tmp_path, monkeypatch, consumer='composed')
    root.call_tool('operation_invoke', request)
    foreign = runtime.scheduler_bindings.create_instance(name='foreign', title='Foreign scope', objective='Reject foreign provenance.')
    for binding in runtime.scheduler_bindings.list(instance=instance.instance_id, namespace='artifact'):
        runtime.scheduler_bindings.bind(instance=foreign.instance_id, namespace='artifact', name=binding.name,
            object_id=binding.object_id, request_fingerprint=binding.request_fingerprint)
    root.facade.instance = foreign.instance_id
    consume = {'name': 'foreign_origin', 'operation_id': 'science.evidence.extract.v1',
        'inputs': [{'port': 'source_material', 'artifact_names': ['source']},
                   {'port': 'frame_anchor', 'artifact_names': ['split']}], 'instruction': 'Read exact sources.'}
    check = root.call_tool('operation_preflight', consume)
    assert not check['admissible']
    assert check['reason_code'] == 'input_origin_unavailable'
    with pytest.raises(Exception, match='input_origin_unavailable'):
        root.call_tool('operation_invoke', consume)
    assert not runtime.scheduler_bindings.list(instance=foreign.instance_id, namespace='run')
