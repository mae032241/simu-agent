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
    assert "scid_call(name='operation_invoke', arguments=" in contract['invocation']['description']
    assert 'Operation ID is not the tool name' in contract['invocation']['description']
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


def test_scheduler_batches_decisions_without_forcing_a_scientific_workflow():
    prompt = load_scheduler_prompt()
    assert "owner next_actions are recommendations" in prompt
    assert "independent tasks allowed by the current contract and budget" in prompt
    assert "control attaches the platform identity" in prompt
    assert "A service-managed turn should return to its host, which waits without model calls" in prompt
    assert "normally 300 seconds" in prompt
    assert "capped by the tool's declared maximum and the remaining execution deadline" in prompt
    assert "Do not periodically call list_agents while waiting" in prompt
    assert "reconcile uncertain dispatch identity or abnormal recovery" in prompt
    from scidiscovery.artifact_agent.service import progression
    source = __import__("inspect").getsource(progression)
    assert "When no decision remains, finish this turn rather" in source
    assert "service wakes you on authoritative changes" in source


def test_scheduler_keeps_global_stopping_gates_out_of_a_single_workers_delivery_floor():
    prompt = load_scheduler_prompt()
    for rule in ('Global completion, exploration, run-count and stopping conditions accumulate across\nsealed tasks',
            "Do not turn them into a single Worker's minimum workload or completion\ncondition",
            "or delay an owner's conditional discriminator, analysis or revision\nhandoff",
            "Relay the owner's bounded question\nand conditional return points unchanged",
            'Carry unmet cumulative requirements and\nexact trial/stopping history to A or the appropriate scientific owner',
            'binding on whole-goal closeout',
            'clarify using the exact sealed handoff and original goal'):
        assert rule in prompt
    # No fixed split replaces Worker judgment, and prior native/managed wait rules remain.
    assert 'nor a trial count forces handoff' in prompt
    assert 'owner next_actions are recommendations' in prompt
    assert 'Do not periodically call list_agents while waiting' in prompt
    assert 'normally 300 seconds' in prompt
    from scidiscovery.general_science_experiment_task import CORE_PROMPT
    assert 'Global completion and run counts are not your delivery floor' in CORE_PROMPT
