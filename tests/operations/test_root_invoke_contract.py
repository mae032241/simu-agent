"""Root reads one selected calling contract without a discovery prerequisite."""
from copy import deepcopy
from unittest.mock import Mock

from scidiscovery.artifact_agent.interfaces.mcp_root import OperationCallInput
from scidiscovery.artifact_agent.interfaces.mcp_response_views import operation_invoke_contract, operation_revision_policy
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.spec import scheduler_operation_view
from scidiscovery.platforms.scheduler_prompt import load_scheduler_prompt
from tests.operations.test_agent_contract_alignment import CORE_PLUGIN
from tests.operations.test_unified_mcp import queued, result, rpc


def test_selected_h_contract_preserves_caller_defaults_constraints_and_action_rules_once():
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN))
    compiled = catalog.operation('science.hypothesis.propose.v1')
    original = scheduler_operation_view(compiled.spec).model_dump(mode='json', by_alias=True)
    original['future_constraint'] = {'required': True}
    original['inputs'][0]['future_port_constraint'] = {'exact': True}
    before = deepcopy(original)
    contract = operation_invoke_contract(original, revision_policy=operation_revision_policy(compiled.spec))
    assert original == before
    for field in ('inputs','outputs','input_validation','source_requirements','qualification_policy',
            'review_subject_policy','review_edge','requires_independent_review','requires_human_approval',
            'allows_policy_authorization','timeout_seconds','max_input_bytes','future_constraint'):
        assert contract[field] == original[field]
    schema = deepcopy(contract['invocation']['inputSchema'])
    assert schema['properties']['operation_id'].pop('const') == compiled.spec.operation_id
    assert schema['$defs']['OperationInputSelection']['properties']['port'].pop('enum') == [
        port['name'] for port in contract['inputs']]
    generic = OperationCallInput.model_json_schema()
    # Only the selected identity/ports and existing task guidance are specialized.
    for field in ('inputs','instruction','scientific_intent'):
        schema['properties'][field] = generic['properties'][field]
    assert schema == generic
    assert 'scientific_intent' not in contract['invocation']  # One definition in inputSchema.
    assert 'no separate scid_describe(operation_invoke)' in contract['invocation']['description']
    assert 'Optional preflight creates nothing' in contract['invocation']['description']


def test_root_can_describe_known_operation_without_catalog_or_generic_describe(tmp_path):
    _, _, root, gateway, _ = queued(tmp_path)
    root.call_tool = Mock(wraps=root.call_tool)
    operation_id = root.facade.run_status(name='observation')['operation_id']
    contract = result(rpc(gateway, 'scid_describe', {'name': operation_id}))['operations'][0]
    assert root.call_tool.call_count == 1
    assert root.call_tool.call_args.args == ('operation_catalog', {
        'operation_id': operation_id, 'view': 'detail', 'scope': 'all'})
    assert contract['invocation']['inputSchema']['properties']['operation_id']['const'] == operation_id
    # Calling-form schemas are not the Worker's scientific authoring form.
    assert 'role_instructions' not in contract and 'output_schema' not in contract
    assert all(isinstance(port['schema'], str) for port in contract['outputs'])
    assert 'RoleHandoff' not in contract['invocation']['inputSchema']['$defs']


def test_root_prompt_limits_discovery_and_keeps_authorization_and_owner_boundaries():
    prompt = load_scheduler_prompt()
    assert 'For a known exact\naction or interface name, call scid_describe directly.' in prompt
    assert 'without separately\ndescribing operation_invoke or reading the full interface catalog' in prompt
    for retained in ('complete experiment tasks manage their own execution through Worker tools',
            'never invoke internal', 'Human decisions occur only in the',
            'Control owns immutable', 'Scientific Workers own all independent scientific decisions'):
        assert retained in prompt
