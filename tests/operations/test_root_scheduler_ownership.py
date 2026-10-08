"""Production Root read authority and native Worker/UI compatibility."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolError
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.service.input_reader import compact_scheduler_fields
from tests.operations.test_l2_run_invariants import _system, _invoke, _worker, _envelope
from tests.operations.test_unified_mcp import call, result, rpc
from tests.operations.test_progression import progression, row


def structured_catalog():
    from blind_csv_plugin.plugin import PLUGIN
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN as GENERAL
    from scidiscovery.operations.catalog import compile_catalog
    author = PLUGIN.operations[0].model_copy(update={'decision_fields': ('structure', 'interpretation', 'limitations')})
    return compile_catalog((CORE_PLUGIN, GENERAL,
        PLUGIN.model_copy(update={'operations': (author, *PLUGIN.operations[1:])})))


def sealed(tmp_path):
    _, runtime, instance, source, root = _system(tmp_path)
    catalog = structured_catalog()
    runtime.runs.operation_catalog = root.facade._operation_catalog = catalog
    _invoke(root, 'observation')
    worker = _worker(catalog, runtime)
    opened = worker.call_tool('worker_open_assignment', {})
    value = json.loads(_envelope())
    value['handoff'].update(assumptions=['A finite fixture leaves causality unresolved.'],
        next_actions=['H: clarify whether a causal contrast is needed using source_csv and observation.output.'])
    Path(opened['output_directory'], 'result.json').write_text(json.dumps(value))
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    return catalog, runtime, instance, source, root, value


def test_generated_root_contract_and_real_mcp_reject_scientific_expansion(tmp_path):
    _, _, _, _, root, original = sealed(tmp_path)
    gateway = UnifiedMCPRouter(root, worker_backend='local')
    described = result(rpc(gateway, 'scid_describe', {'name': 'run_status'}))
    schema = described['inputSchema']
    assert schema['properties']['intent']['enum'] == ['decision', 'status', 'navigation']
    assert not {'output_fields', 'output_paths', 'stage_reference', 'stage_text_offset'} & schema['properties'].keys()
    for forbidden in ({'intent': 'full'}, {'output_fields': ['structure']},
                      {'output_paths': ['/structure']}, {'stage_reference': 'sealed-design'},
                      {'scheduler_view': False}):
        error = call(gateway, 'run_status', {'name': 'observation', **forbidden})['error']
        assert 'delegate' in error['message'].lower()
        assert error['data']['diagnostics']
    response = result(call(gateway, 'run_status', {'name': 'observation'}))
    encoded = json.dumps(response)
    assert 'numeric_means' not in encoded and 'sealed_output"' not in encoded
    assert '"intent": "full"' not in encoded and 'output_paths' not in encoded
    assert next(item for item in response['selected_output']['items'] if item['pointer'] == '/structure')['status'] == 'omitted'
    assert response['scheduler_signal']['next_actions'] == original['handoff']['next_actions']
    assert response['scheduler_signal']['assumptions'] == original['handoff']['assumptions']
    assert root.facade.run_status(name='observation', intent='full')['sealed_output']['payload'] == original['payload']


def test_generic_declared_statements_keep_exact_caveats_and_omit_raw_structures():
    payload = {'custom_fact': 'Exact plugin-authored conclusion.', 'caveats': ['Complete caveat.'] * 6,
        'raw': [9.87654321, 8.7654321], 'nested': {'sentinel': 'RAW_REPORT_SENTINEL'},
        'long': '界' * 2000}
    selected = compact_scheduler_fields(payload, ['/' + name for name in payload])
    items = {item['pointer']: item for item in selected['items']}
    assert items['/custom_fact']['value'] == payload['custom_fact']
    assert items['/caveats']['value'] == payload['caveats'][:4]
    assert items['/caveats']['omitted_children'] == 2
    assert all(items[pointer]['status'] == 'omitted' for pointer in ('/raw', '/nested', '/long'))
    assert 'RAW_REPORT_SENTINEL' not in json.dumps(selected) and '9.87654321' not in json.dumps(selected)
    assert 'read the full' not in selected['instruction']


def test_root_artifact_content_preserves_goal_and_context_but_delegates_evidence(tmp_path):
    _, runtime, instance, _, root, _ = sealed(tmp_path)
    gateway = UnifiedMCPRouter(root, worker_backend='local')
    root.call_tool('artifact_ingest_text', {'name': 'user-goal', 'text': 'Original constraints: retain exact units.'})
    assert result(call(gateway, 'artifact_catalog', {'name': 'user-goal', 'view': 'content'}))['text'].startswith('Original constraints:')
    # Use control's supported structured goal anchor, without making result schemas readable.
    goal = runtime.artifacts.register(b'{"objective":"Retain user constraints"}', ArtifactRegistration(
        kind='research_objective', schema_id='scidiscovery.research-objective.v1',
        payload_schema_version=1, media_type='application/json', creator=runtime.actor), idempotency_key='structured-goal')
    runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace='artifact',
        name='structured-goal', object_id=goal.artifact_id)
    assert result(call(gateway, 'artifact_catalog', {'name': 'structured-goal', 'view': 'content'}))['text'] == '{"objective":"Retain user constraints"}'
    for name in ('source_csv', 'observation.output'):
        error = call(gateway, 'artifact_catalog', {'name': name, 'view': 'content'})['error']
        assert name in error['message'] and 'scientific owner' in error['message']
        assert root.call_tool('artifact_catalog', {'name': name})['name'] == name
        assert root.facade.artifact_catalog(name=name, view='content')['text']
    # Evidence originals still enter an ordinary nonexperiment task directly.
    created = root.call_tool('operation_invoke', {'name': 'read-evidence',
        'operation_id': 'science.evidence.extract.v1',
        'inputs': [{'port': 'source_material', 'artifact_names': ['user-goal']}],
        'instruction': 'Assess the exact original constraint.'})
    assert created['result']['state'] == 'queued'


def test_raw_diagnostic_and_execution_log_bodies_stay_internal():
    sentinel = 'RAW_SCIENTIFIC_LOG_SENTINEL'
    facade = SimpleNamespace(runs=SimpleNamespace(), session_key=None,
        engineering_diagnostics=SimpleNamespace(capture=Mock()),
        diagnostic_read=Mock(return_value={'text': 'Exact operational fault',
            'available_sections': ['summary', 'traceback', 'stdout', 'stderr']}),
        execution_logs=Mock(return_value={'text': sentinel, 'source': 'stdout',
            'cached_bytes': len(sentinel), 'gap': None, 'before': None, 'after': 'cursor'}))
    root = RootMCPRouter(facade)
    with pytest.raises(RootToolError, match='Delegate'):
        root.call_tool('diagnostic_read', {'reference': 'diag_' + 'a' * 32, 'section': 'stdout'})
    safe = root.call_tool('diagnostic_read', {'reference': 'diag_' + 'a' * 32})
    assert safe['text'] == 'Exact operational fault'
    assert safe['available_sections'] == ['summary', 'traceback']
    response = root.call_tool('execution_logs', {'name': 'execution'}, surface='execution')
    assert sentinel not in json.dumps(response) and response['cached_bytes'] == len(sentinel)
    assert response['after'] == 'cursor' and response['content_unavailable']
    assert facade.execution_logs(name='execution')['text'] == sentinel


def test_role_prompts_delegate_science_without_new_gate():
    from scidiscovery.platforms.scheduler_prompt import load_scheduler_prompt, load_scheduler_guides
    from scidiscovery.general_science_resources import IDEATOR_PROMPT
    from scidiscovery.general_science_result_analysis import PROMPT
    from scidiscovery.artifact_agent.service.progression import INSTRUCTION
    root = load_scheduler_prompt()
    assert 'Root must not invent hypotheses' in root
    assert 'Hypothesis formulation (H)' in root and 'Analysis (A)' in root
    assert 'candidate-selection strategies' in IDEATOR_PROMPT
    assert 'Challenge H-derived' in PROMPT and 'payload.next_action' in PROMPT
    assert 'scientific owner' in INSTRUCTION
    for guide in load_scheduler_guides().values():
        assert 'intent="full"' not in guide and '"output_paths"' not in guide


def test_compiled_structured_field_is_omitted_across_root_history_closeout_and_background(progression):
    from tests.operations.test_attempt_history import SECRET
    from tests.operations.test_scientific_progress import active, finish
    p = progression
    p.catalog = structured_catalog()
    p.runtime.runs.operation_catalog = p.root.facade._operation_catalog = p.catalog
    p.root.facade.instance_management_secret = SECRET
    root = active(p)
    finish(p, root, 'structured-result')
    gateway = UnifiedMCPRouter(root, worker_backend='local')
    default = result(call(gateway, 'run_status', {'name': 'structured-result'}))
    structured = next(item for item in default['selected_output']['items'] if item['pointer'] == '/structure')
    assert structured['status'] == 'omitted' and 'value' not in structured
    history = result(call(gateway, 'run_list', {'view': 'history', 'limit': 8}))
    status = result(call(gateway, 'progression_status', {}))
    listed = result(call(gateway, 'run_list', {'view': 'detail'}))
    saved = row(p)
    snapshot = {'goal': saved['objective_ref_json'], 'runs': [{'name': 'structured-result', 'state': 'completed'}], 'approvals': []}
    brief = json.loads(p.coordinator._brief(saved, snapshot, 30000).split('\n')[-1])
    assert history['runs'] and status['closeout']['tasks'] and brief['changes']
    for response in (default, history, status['closeout'], listed, brief['changes']):
        text = json.dumps(response)
        assert 'numeric_means' not in text and 'source_sha256' not in text
        assert '"intent": "full"' not in text and 'output_paths' not in text
    full = root.facade.run_status(name='structured-result', intent='full')['sealed_output']
    assert full['payload']['structure']['numeric_means'] == {'value': 2.0}
    # A native Worker receives the intact original through its frozen input.
    root.call_tool('operation_invoke', {'name': 'independent-reader', 'operation_id': 'blind.csv.review.v1',
        'inputs': [{'port': 'source_table', 'artifact_names': ['source_csv']},
            {'port': 'csv_observation', 'artifact_names': ['structured-result.output']}],
        'instruction': 'Inspect the exact retained observation.'})
    profile = result(call(gateway, 'run_status', {'name': 'independent-reader'}))['execution_profile']['profile']
    result(call(gateway, 'worker_attach', {'name': 'independent-reader', 'thread_id': 'reader-child'}))
    opened = result(call(gateway, 'worker_open_assignment', child='reader-child', profile=profile))
    assignment = json.loads(Path(opened['assignment_path']).read_text())
    observation = next(item for item in assignment['inputs'] if item['source_name'] == 'csv_observation')
    original = json.loads((Path(opened['workspace_path']) / observation['relative_path']).read_text())
    assert original == full['payload']


def compiled_role(operation_id):
    from scidiscovery.operations.tooling import operation_role_instructions
    return operation_role_instructions(structured_catalog().operation(operation_id))


def test_compiled_worker_method_freedom_does_not_authorize_changed_hypotheses_or_data():
    prompt = compiled_role('science.experiment.v1')
    assert 'continuously try related parameters, implementations, numerical' in prompt
    assert "H's declared mechanisms, key assumptions, allowed data and validation" in prompt
    assert 'then H revision before executing the new' in prompt
    assert 'must not execute a new direction on that basis' in prompt
    assert 'held-out observations to choose a method' in prompt
    assert 'training data only' in prompt and 'train-only, remain binding' in prompt
    assert 'this adds no schema, gate or permission' in prompt


def test_compiled_hypothesis_improvement_and_diagnosis_have_distinct_scientific_scope():
    prompt = compiled_role('science.hypothesis.propose.v1')
    assert 'optimization or improvement goal' in prompt
    assert 'falsifiable mechanisms that' in prompt
    assert 'pure diagnosis goal has no required number of solution mechanisms' in prompt
    assert 'do not invent candidates to satisfy a count' in prompt
    assert 'real user authorization or no-leakage requirements' in prompt
    assert 'no exploratory execution outside its declared native permissions' in prompt


def test_compiled_analysis_and_root_preserve_real_constraints_and_neutral_closeout():
    from scidiscovery.platforms.scheduler_prompt import load_scheduler_prompt
    prompt = compiled_role('science.result.analyze.v1')
    assert 'train-only or no-leakage requirement may be binding' in prompt
    assert 'return it\nto H for explicit revision before W executes' in prompt
    root = load_scheduler_prompt()
    assert 'Relay owner direction neutrally' in root
    assert 'a budget stop is a\ncontrol boundary' in root
