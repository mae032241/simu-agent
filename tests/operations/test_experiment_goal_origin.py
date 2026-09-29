"""Goals follow exact scientific lineage without a Root-owned projection task."""
import json

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.artifact_agent.interfaces.mcp_root_shared import RootToolError
from scidiscovery.operations.spec import scheduler_operation_view
from curve_score.plugin import PLUGIN as CURVE
from tcad_artifact.plugin import PLUGIN as TCAD
from tests.operations.test_general_transform_operations import _root, _register, _intake
from tests.operations.test_historical_compatibility_paths import _complete, _artifact
from tests.operations.test_hypothesis_objective_boundary import _foundation, _proposal


def _setup(tmp_path):
    catalog = compile_catalog((CORE_PLUGIN, GENERAL, CURVE, TCAD))
    runtime, instance, root = _root(tmp_path, catalog=catalog)
    runtime.runs.operation_catalog = catalog
    return runtime, instance, root


def _put(runtime, instance, name, payload, schema):
    _register(runtime, instance, name=name, raw=canonical_json(payload), kind='scientific_object', schema=schema)


def _request(subject):
    return dict(name='experiment', operation_id='science.experiment.v1',
                inputs=[dict(port='subject', artifact_names=[subject])], instruction='Test the selected mechanism.')


@pytest.mark.parametrize('carrier', ['objective', 'foundation', 'intake'])
def test_existing_goal_carriers_need_no_root_projection(tmp_path, carrier):
    runtime, instance, root = _setup(tmp_path)
    foundation = json.loads(_foundation())
    payload = {'objective': foundation['objective_contract'], 'foundation': foundation,
               'intake': {**_intake().model_dump(mode='json'), 'scientific_foundation': foundation}}[carrier]
    schema = {'objective': 'research-objective', 'foundation': 'scientific-foundation', 'intake': 'scientific-intake'}[carrier]
    _put(runtime, instance, 'selected', payload, f'scidiscovery.{schema}.v1')
    contract = scheduler_operation_view(runtime.runs.operation_catalog.operation('science.experiment.v1').spec)
    assert 'objective_source' not in {port.name for port in contract.inputs}
    assert 'research_objective' not in {port.name for port in contract.inputs}
    request = _request('selected')
    assert root.call_tool('operation_preflight', request)['admissible']
    assert root.call_tool('operation_invoke', request)['result']['state'] == 'queued'
    run_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='run', name='experiment')
    inputs = runtime.runs.status(run_id).inputs
    expected = _artifact(runtime, instance, 'selected').ref
    assert {item.artifact_ref for item in inputs if item.port_name in {'subject', 'objective_source'}} == {expected}



def test_hypothesis_stage_and_global_goal_follow_original_not_newer_foundation(tmp_path, monkeypatch):
    from urllib.parse import parse_qs, urlparse
    from scidiscovery.artifact_agent.schema.approval import LocalIdentityRef
    from scidiscovery.artifact_agent.schema.research_cycle import ScientificIntake
    from tests.operations import test_frozen_input_execution as fixture
    intake = _intake().model_dump(mode='json')
    intake['scientific_foundation'] = json.loads(_foundation().replace(b'"source"', b'"paper"').replace(b'"target_item"', b'"target"'))
    intake['problem_frame']['objective'] = intake['scientific_foundation']['objective']
    monkeypatch.setattr(fixture, '_intake', lambda: ScientificIntake.model_validate_json(canonical_json(intake)))
    runtime, instance, root, split = fixture._system(tmp_path, monkeypatch)
    # Root receives the science automatically in the ordinary result read.
    root_read = root.call_tool('run_status', {'name': 'author'})
    values = {item['pointer']: item.get('value') for item in root_read['selected_output']['items']}
    goal = ScientificIntake.model_validate_json(canonical_json(intake)).model_dump(mode='json')['scientific_foundation']['objective_contract']
    assert values['/scientific_foundation/objective'] == goal['statement']
    assert values['/scientific_foundation/objective_contract/closure_requirements'] == goal['closure_requirements']
    assert values['/scientific_foundation/objective_contract/mandatory_targets'] == goal['mandatory_targets']
    root.call_tool('operation_invoke', split)
    root.call_tool('operation_invoke', dict(name='qualify', operation_id='science.evidence.qualify.v1',
        inputs=[dict(port='scientific_foundation', artifact_names=['split.scientific_foundation'])]))
    approval_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='approval', name='qualify')
    launch = runtime.approvals.status(approval_id)
    token = parse_qs(urlparse(launch.review_path).query)['token'][0]
    review = runtime.approvals.review(approval_id, access_token=token)
    runtime.approvals.record_ui_decision(approval_id=approval_id, access_token=token,
        csrf_token=review.csrf_token, decision_nonce=review.decision_nonce,
        selected_option='approve', rationale='Fixture evidence approved.',
        decided_by=LocalIdentityRef(identity_id='independent_fixture', display_name='Fixture reviewer'),
        ui_session_id='goal-origin-fixture')
    proposal = _proposal(hypothesis_keys=('mechanism',))
    subject = _complete(runtime, root, 'hypothesis', 'science.hypothesis.propose.v1',
                        {'scientific_foundation': 'split.scientific_foundation', 'problem_frame': 'split'}, proposal)
    hypothesis_read = root.call_tool('run_status', {'name': 'hypothesis'})
    assert next(item['value'] for item in hypothesis_read['selected_output']['items']
                if item['pointer']=='/stage_objective') == proposal['stage_objective']
    _put(runtime, instance, 'newer_foundation', json.loads(_foundation('different_goal')), 'scidiscovery.scientific-foundation.v1')
    request = _request(subject)
    assert root.call_tool('operation_preflight', request)['admissible']
    assert root.call_tool('operation_invoke', request)['result']['state'] == 'queued'
    run_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='run', name='experiment')
    inputs = {item.port_name: item.artifact_ref for item in runtime.runs.status(run_id).inputs}
    assert inputs['objective_source'] == _artifact(runtime, instance, 'split.scientific_foundation').ref
    assert json.loads(runtime.artifacts.read(inputs['subject']))['stage_objective'] == proposal['stage_objective']


@pytest.mark.parametrize('payload,reason', [(None, 'input_objective_missing'), ({}, 'input_objective_missing'),
    ({'objective_contract': {'statement': 'Incomplete'}}, 'input_objective_invalid')])
def test_missing_science_is_reported_without_falling_back_to_other_goal(tmp_path, payload, reason):
    runtime, instance, root = _setup(tmp_path)
    _put(runtime, instance, 'selected', payload, 'scidiscovery.scientific-foundation.v1')
    _put(runtime, instance, 'unrelated', json.loads(_foundation()), 'scidiscovery.scientific-foundation.v1')
    result = root.call_tool('operation_preflight', _request('selected'))
    assert not result['admissible']
    assert result['reason_code'] == reason
    assert result['port'] == 'subject'


def test_root_cannot_supply_internal_goal_binding(tmp_path):
    runtime, instance, root = _setup(tmp_path)
    _put(runtime, instance, 'selected', json.loads(_foundation()), 'scidiscovery.scientific-foundation.v1')
    request = _request('selected')
    request['inputs'].append(dict(port='objective_source', artifact_names=['selected']))
    with pytest.raises(RootToolError, match='input_port_unknown'):
        root.call_tool('operation_invoke', request)


@pytest.mark.parametrize('ambiguous', [False, True])
def test_alternative_origins_deduplicate_refs_but_reject_distinct_goals(tmp_path, monkeypatch, ambiguous):
    from types import SimpleNamespace
    from scidiscovery.artifact_agent.service.operation_origins import OperationOrigins
    from scidiscovery.operations.invoke import InvocationArtifact, OperationInvocationError
    runtime, instance, root = _setup(tmp_path)
    _put(runtime, instance, 'selected', {'summary': 'Fixture result'}, 'opaque')
    _put(runtime, instance, 'one', json.loads(_foundation()), 'scidiscovery.scientific-foundation.v1')
    _put(runtime, instance, 'two', json.loads(_foundation('other')), 'scidiscovery.scientific-foundation.v1')
    first, second = (_artifact(runtime, instance, name).ref for name in ('one', 'two'))
    origin = OperationOrigins(artifacts=runtime.artifacts, bindings=runtime.scheduler_bindings,
        runs=runtime.runs, catalog=runtime.runs.operation_catalog, instance_id=instance.instance_id)
    # Isolate traversal ambiguity; the preceding test covers real sealed lineage.
    family = SimpleNamespace(producer_instance_id=instance.instance_id, producer_inputs=(
        SimpleNamespace(port_name='scientific_foundation', ref=first),
        SimpleNamespace(port_name='scientific_foundation', ref=second if ambiguous else first)))
    monkeypatch.setattr(origin, '_producer_output_family_from_envelope',
                        lambda name, envelope: family if name=='selected' else None)
    selected = _artifact(runtime, instance, 'selected')
    resolved = {'subject': (InvocationArtifact('selected', selected.ref, selected.schema_id,
                                              selected.media_type, selected.size_bytes),)}
    compiled = runtime.runs.operation_catalog.operation('science.experiment.v1')
    if ambiguous:
        with pytest.raises(OperationInvocationError, match='input_origin_ambiguous'):
            origin._derive_operation_inputs(compiled, resolved)
    else:
        origin._derive_operation_inputs(compiled, resolved)
        assert [item.ref for item in resolved['objective_source']] == [first]
