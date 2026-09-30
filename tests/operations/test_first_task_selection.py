"""Original goal -> source task, without hidden prerequisites or extra approval."""
import json
from unittest.mock import Mock

from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.spec import scheduler_operation_view
from tests.operations.test_general_transform_operations import _root, _intake
from tests.operations.test_historical_compatibility_paths import _complete
from tests.operations.test_hypothesis_objective_boundary import _foundation
from tests.operations.test_unified_mcp import rpc, call, result


def setup(tmp_path):
    catalog = compile_catalog((CORE_PLUGIN, GENERAL))
    runtime, instance, root = _root(tmp_path, catalog=catalog)
    runtime.runs.operation_catalog = catalog
    root.call_tool('artifact_ingest_text', dict(name='goal', text='Compare the supplied observations.', on_conflict='reject'))
    return runtime, instance, root, UnifiedMCPRouter(root)


def experiment(subject='goal'):
    return dict(name='experiment', operation_id='science.experiment.v1',
        inputs=[dict(port='subject', artifact_names=[subject])], instruction='Test the selected mechanism.')


def test_exact_public_contract_explains_raw_goal_rejection_before_worker(tmp_path, monkeypatch):
    runtime, instance, root, gateway = setup(tmp_path)
    capture = Mock()
    monkeypatch.setattr(root.facade.engineering_diagnostics, 'capture', capture)
    contract = result(rpc(gateway, 'scid_describe', {'name':'science.experiment.v1'}))['operations'][0]
    requirement, = contract['source_requirements']['subject']
    assert 'scidiscovery.scientific-intake.v1' in requirement
    assert 'Copying or renaming' in requirement
    assert 'objective_source' not in json.dumps(contract)
    for name in ['goal', 'copied-goal']:
        if name != 'goal':
            root.call_tool('artifact_ingest_text', dict(name=name, text='Compare the supplied observations.', on_conflict='reject'))
        preflight = result(call(gateway, 'operation_preflight', experiment(name)))
        assert preflight['reason_code'] == 'input_origin_missing'
        rejected = call(gateway, 'operation_invoke', experiment(name))
        wire = json.dumps(rejected)
        assert 'error' in rejected and requirement in wire
        assert 'engineering' not in wire and 'runtime_failure' not in wire
        assert '$.inputs.subject' in wire and 'objective_source' not in wire
    capture.assert_not_called()
    assert not runtime.runs.list(instance_id=instance.instance_id)


def test_original_can_be_answered_and_sealed_without_approval_or_root_goal_object(tmp_path):
    runtime, instance, root, gateway = setup(tmp_path)
    contract = result(rpc(gateway, 'scid_describe', {'name':'science.evidence.extract.v1'}))['operations'][0]
    assert contract['requires_human_approval'] is False
    assert contract['source_requirements'] == {}
    assert 'bounded scientific question' in contract['purpose']
    payload = _intake().model_dump(mode='json')
    payload['scientific_foundation'] = json.loads(_foundation().replace(
        b'"source"', b'"source_material"').replace(b'"target_item"', b'"target"'))
    payload['problem_frame']['objective'] = payload['scientific_foundation']['objective']
    name = _complete(runtime, root, 'analysis', 'science.evidence.extract.v1',
        {'source_material':'goal'}, payload)
    assert root.call_tool('run_status', {'name':'analysis'})['state'] == 'completed'
    assert not runtime.scheduler_bindings.list(instance=instance.instance_id, namespace='approval')
    # This is an optional later task, not a required extraction -> experiment chain.
    assert result(call(gateway, 'operation_preflight', experiment(name)))['admissible']


def test_origin_contract_follows_declaration_without_exposing_hidden_binding_names(tmp_path):
    runtime, _, _, _ = setup(tmp_path)
    original = runtime.runs.operation_catalog.operation('science.experiment.v1').spec
    changed = original.model_copy(update={'inputs':tuple(
        p.model_copy(update={'name':'private_goal_binding', 'derivation':p.derivation.model_copy(update={
            'source_schemas':('third-party.goal.v3',)})}) if p.derivation else p
        for p in original.inputs)})
    view = scheduler_operation_view(changed)
    text = json.dumps(view.source_requirements)
    assert 'third-party.goal.v3' in text and 'scidiscovery.scientific-intake.v1' not in text
    assert 'private_goal_binding' not in view.model_dump_json()


def test_real_control_failure_still_has_engineering_diagnostics(tmp_path, monkeypatch):
    from scidiscovery.operations.input_validation import OperationEngineeringError
    _, _, root, gateway = setup(tmp_path)
    def fail(**kwargs):
        raise OperationEngineeringError('control_component_failed')
    monkeypatch.setattr(root.facade, 'operation_invoke', fail)
    response = call(gateway, 'operation_invoke', experiment())
    assert 'engineering' in json.dumps(response)


def test_long_plugin_source_choices_preserve_contract_and_bounded_repair(tmp_path):
    from scidiscovery.artifact_agent.schema.common import ContractDiagnostic
    runtime, _, root, gateway = setup(tmp_path)
    schemas = tuple('third-party.' + 'x' * 70 + f'.{n}.v1' for n in range(12))
    spec = runtime.runs.operation_catalog.operation('science.experiment.v1').spec
    changed = spec.model_copy(update={'inputs':tuple(
        p.model_copy(update={'derivation':p.derivation.model_copy(update={'source_schemas':schemas})})
        if p.derivation else p for p in spec.inputs)})
    plugin = GENERAL.model_copy(update={'operations':tuple(
        changed if op.operation_id == changed.operation_id else op for op in GENERAL.operations)})
    root.facade._operation_catalog = runtime.runs.operation_catalog = compile_catalog((CORE_PLUGIN, plugin))
    contract = result(rpc(gateway, 'scid_describe', {'name':'science.experiment.v1'}))['operations'][0]
    assert all(schema in contract['source_requirements']['subject'][0] for schema in schemas)
    rejected = call(gateway, 'operation_invoke', experiment())
    wire = json.dumps(rejected)
    assert 'input_origin_missing' in wire and 'Read this action\'s source_requirements' in wire
    assert 'engineering' not in wire
    diagnostic = rejected['error']['data']['diagnostics'][0]
    assert len(diagnostic['message']) <= ContractDiagnostic.model_json_schema()['properties']['message']['maxLength']
