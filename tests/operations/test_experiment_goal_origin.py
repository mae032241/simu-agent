"""Goals follow exact scientific lineage without a Root-owned projection task."""
import json
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.artifact_agent.interfaces.mcp_root_shared import RootToolError
from scidiscovery.operations.spec import scheduler_operation_view
from scidiscovery.artifact_agent.service.intake import USER_TEXT_SOURCE_ORIGIN
from curve_score.plugin import PLUGIN as CURVE
from tcad_artifact.plugin import PLUGIN as TCAD
from tests.operations.test_general_transform_operations import _root, _register, _intake
from tests.operations.test_historical_compatibility_paths import _complete, _artifact
from tests.operations.test_hypothesis_objective_boundary import _foundation, _proposal


def _setup(tmp_path, *, native_only=False):
    catalog = compile_catalog((CORE_PLUGIN, GENERAL, CURVE, TCAD),
        capability_selections={'general_science:experiment_task_protocol': 'none'} if native_only else None)
    runtime, instance, root = _root(tmp_path, catalog=catalog)
    runtime.runs.operation_catalog = catalog
    return runtime, instance, root


def _put(runtime, instance, name, payload, schema):
    _register(runtime, instance, name=name, raw=canonical_json(payload), kind='scientific_object', schema=schema)


def _request(subject):
    return dict(name='experiment', operation_id='science.experiment.v1',
                inputs=[dict(port='subject', artifact_names=[subject])], instruction='Test the selected mechanism.')


@pytest.mark.parametrize('carrier', ['objective', 'foundation', 'intake'])
def test_goal_carriers_alone_cannot_replace_a_hypothesis(tmp_path, carrier):
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
    rejected = root.call_tool('operation_preflight', request)
    assert not rejected['admissible'] and rejected['reason_code'] == 'input_origin_missing'
    with pytest.raises(RootToolError, match='input_origin_missing'):
        root.call_tool('operation_invoke', request)



def test_hypothesis_stage_and_global_goal_follow_original_not_newer_foundation(tmp_path, monkeypatch):
    from urllib.parse import parse_qs, urlparse
    from scidiscovery.artifact_agent.schema.approval import LocalIdentityRef
    from scidiscovery.artifact_agent.schema.research_cycle import ScientificIntake
    from tests.operations import test_frozen_input_execution as fixture
    intake = _intake().model_dump(mode='json')
    intake['scientific_foundation'] = json.loads(_foundation().replace(b'"source"', b'"paper"').replace(b'"target_item"', b'"target"'))
    intake['problem_frame']['objective'] = intake['scientific_foundation']['objective']
    monkeypatch.setattr(fixture, '_intake', lambda: ScientificIntake.model_validate_json(canonical_json(intake)))
    runtime, instance, root, split = fixture._system(tmp_path, monkeypatch, native_only=True)
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
    assert inputs['hypothesis_portfolio'] == _artifact(runtime, instance, subject).ref
    assert json.loads(runtime.artifacts.read(inputs['subject']))['stage_objective'] == proposal['stage_objective']
    # The generic successor binds the exact experiment and the same upstream science.
    from pathlib import Path
    from tests.operations.worker_fixtures import attached_worker
    worker = attached_worker(runtime, root, 'experiment')
    opened = worker.call_tool('worker_open_assignment', {})
    Path(opened['output_directory'], 'result.json').write_bytes(canonical_json({
        'schema_version': 1, 'payload': {'summary': 'Missing environment.', 'outcome': 'blocked',
            'remaining_question': 'Provide the environment.', 'limitations': ['No execution.'], 'adopted_stages': []}}))
    completed = worker.call_tool('worker_submit_result', {})
    assert completed['state'] == 'completed', completed
    experiment = root.call_tool('run_status', {'name': 'experiment'})['output_artifact_name']
    next_action = 'Test the existing hypothesis after repairing the missing environment; retain unmet global requirements.'
    remaining = 'There are no observations resolving the original hypothesis.'
    analysis = _complete(runtime, root, 'analysis', 'science.result.analyze.v1', {'subject': experiment},
        {'summary': 'The experiment was blocked, so the hypothesis remains untested.',
         'overall_verdict': 'inconclusive', 'claim_allowed': False,
         'next_action': next_action, 'remaining_contradiction': remaining,
         'limitations': ['No execution observations.']}, verdict='inconclusive')
    assert _artifact(runtime, instance, analysis).schema_id == 'scidiscovery.layered-diagnosis.v1'
    analysis_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='run', name='analysis')
    start = json.loads((runtime.runs.backend.open(analysis_id).root/'worker-start.json').read_bytes())
    role = ' '.join(start['role_instructions'].split())
    assert 'Use remaining_contradiction and next_action to explain how evidence changes the decision' in role
    assert 'continue tests within existing hypotheses and original criteria' in role
    assert 'closeout only when global conditions are supported' in role
    assert 'parameter improvements or a passing verdict alone do not establish scientific progress' in role
    retained = json.loads(runtime.artifacts.read(_artifact(runtime, instance, analysis).ref))
    assert retained['next_action'] == next_action and retained['remaining_contradiction'] == remaining
    inherited = {item.port_name: item.artifact_ref for item in runtime.runs.status(analysis_id).inputs}
    assert inherited['hypothesis_portfolio'] == inputs['hypothesis_portfolio']
    assert inherited['objective_source'] == inputs['objective_source']
    successor = {**_request(experiment), 'name': 'successor'}
    assert root.call_tool('operation_preflight', successor)['admissible']
    assert root.call_tool('operation_invoke', successor)['result']['state'] == 'queued'
    successor_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='run', name='successor')
    assert next(item.artifact_ref for item in runtime.runs.status(successor_id).inputs
                if item.port_name == 'hypothesis_portfolio') == inputs['hypothesis_portfolio']
    _put(runtime, instance, 'copied_proposal', proposal, 'scidiscovery.hypothesis-proposal.v2')
    rejected = root.call_tool('operation_preflight', {**_request('copied_proposal'), 'name': 'unsealed'})
    assert not rejected['admissible'] and rejected['reason_code'] in {'input_origin_unavailable', 'input_origin_missing'}
    empty = _complete(runtime, root, 'empty', 'science.hypothesis.propose.v1',
        {'scientific_foundation': 'split.scientific_foundation', 'problem_frame': 'split'}, _proposal())
    rejected = root.call_tool('operation_preflight', {**_request(empty), 'name': 'empty_test'})
    assert not rejected['admissible'] and rejected['reason_code'] == 'input_portfolio_empty'


def test_generic_analysis_is_available_without_domain_plugins():
    catalog = compile_catalog((CORE_PLUGIN, GENERAL))
    analysis = catalog.operation('science.result.analyze.v1')
    assert not any(tool.name.startswith('worker_experiment') for tool in analysis.worker_tools)
    assert not any(tool.name.startswith('worker_experiment') for tool in
        catalog.operation('science.hypothesis.propose.v1').worker_tools)
    assert {port.name for port in scheduler_operation_view(analysis.spec).inputs} == {
        'subject', 'scientific_materials', 'user_context'}


def test_original_task_enters_hypothesis_without_intake_search_or_synthetic_key(tmp_path):
    runtime, instance, root = _setup(tmp_path, native_only=True)
    task_text = ('Compute 2+2 and retain the program and result. Global completion requires '
                 '11 valid trials and no improvement in the last 4 eligible trials, across sealed tasks.')
    root.call_tool('artifact_ingest_text', {'name': 'task', 'text': task_text})
    expected = _artifact(runtime, instance, 'task').ref
    proposal = _proposal(hypothesis_keys=('mechanism',))
    proposal.pop('research_objective_key')
    subject = _complete(runtime, root, 'hypothesis', 'science.hypothesis.propose.v1', {'subject': 'task'}, proposal)
    hypothesis_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='run', name='hypothesis')
    hypothesis_start = json.loads((runtime.runs.backend.open(hypothesis_id).root/'worker-start.json').read_bytes())
    hypothesis_role = ' '.join(hypothesis_start['role_instructions'].split())
    assert 'difference the next experiment can discriminate' in hypothesis_role
    assert 'do not require an experiment to exhaust a method catalogue' in hypothesis_role
    assert 'stage_objective' in hypothesis_role
    assert runtime.artifacts.read(expected).decode() == task_text
    sealed = json.loads(runtime.artifacts.read(_artifact(runtime, instance, subject).ref))
    assert sealed.get('research_objective_key') is None
    hypotheses = runtime.runs.operation_catalog.operation('science.hypothesis.propose.v1')
    assert not any(tool.name == 'worker_source_capture' for tool in hypotheses.worker_tools)
    assert hypotheses.spec.executor.native_tools.web_search == 'disabled'
    # Optional review consumes the same original, with no foundation qualification.
    _complete(runtime, root, 'critic', 'science.hypothesis.criticize.v1', {'hypothesis_portfolio': subject},
        {'schema_version': 2, 'disposition': 'ready_for_experiment', 'reviews': [{
            'hypothesis_key': 'mechanism', 'physical_plausibility': 'pass',
            'falsifiability': 'pass', 'finite_discriminability': 'pass'}]})
    assert root.call_tool('operation_invoke', _request(subject))['result']['state'] == 'queued'
    run_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='run', name='experiment')
    assert next(item.artifact_ref for item in runtime.runs.status(run_id).inputs
                if item.port_name == 'objective_source') == expected
    from tests.operations.worker_fixtures import attached_worker
    worker = attached_worker(runtime, root, 'experiment')
    opened = worker.call_tool('worker_open_assignment', {})
    start = json.loads(Path(opened['start_here_path']).read_bytes())
    role = ' '.join(start['role_instructions'].split())
    assert 'an affordable discriminating test may continue within those boundaries' in role
    assert "Global completion conditions and trial/stopping history accumulate across sealed tasks, not as this Worker's delivery floor" in role
    assert 'Do not make that global scientific decision yourself.' in role
    assert start['instruction'] == _request(subject)['instruction']
    assert '11 valid trials' not in role and 'last 4 eligible trials' not in role
    assert next(item.artifact_ref for item in runtime.runs.status(run_id).inputs
                if item.port_name == 'objective_source') == expected
    assert {run.operation_id for run in runtime.runs.list(instance_id=instance.instance_id)} == {
        'science.hypothesis.propose.v1', 'science.hypothesis.criticize.v1', 'science.experiment.v1'}


def test_structured_hypothesis_cannot_omit_its_objective_key():
    from scidiscovery.general_science_components import _hypothesis_objective_context
    from scidiscovery.operation_contract import SemanticRuleViolation
    proposal = _proposal(hypothesis_keys=('mechanism',))
    proposal.pop('research_objective_key')
    with pytest.raises(SemanticRuleViolation, match='research_objective_key differs'):
        _hypothesis_objective_context(proposal, {'scientific_foundation': _foundation()}, {})


def test_completed_hypothesis_remains_reusable_after_its_contract_changes(tmp_path):
    runtime, instance, root = _setup(tmp_path, native_only=True)
    root.call_tool('artifact_ingest_text', {'name': 'task', 'text': 'Test the mechanism against the original task.'})
    proposal = _proposal(hypothesis_keys=('mechanism',))
    proposal.pop('research_objective_key')
    subject = _complete(runtime, root, 'hypothesis', 'science.hypothesis.propose.v1', {'subject': 'task'}, proposal)
    original = _artifact(runtime, instance, subject)
    changed = GENERAL.model_copy(update={'operations': tuple(
        op.model_copy(update={'version': 'next-generation'}) if op.operation_id == 'science.hypothesis.propose.v1' else op
        for op in GENERAL.operations)})
    current = compile_catalog((CORE_PLUGIN, changed, CURVE, TCAD),
        capability_selections={'general_science:experiment_task_protocol': 'none'})
    runtime.runs.operation_catalog = current
    root.facade._operation_catalog = current
    assert root.facade._run_output_family(original).contract_availability == 'historical'
    experiment = _complete(runtime, root, 'experiment', 'science.experiment.v1', {'subject': subject},
        {'summary': 'Environment unavailable.', 'outcome': 'blocked', 'remaining_question': 'Provide it.',
         'limitations': ['No execution.'], 'adopted_stages': []}, historical_ports=('hypothesis_portfolio',))
    analysis = _complete(runtime, root, 'analysis', 'science.result.analyze.v1', {'subject': experiment},
        {'summary': 'Original hypothesis remains untested.', 'overall_verdict': 'inconclusive',
         'claim_allowed': False, 'limitations': ['No observations.']},
        verdict='inconclusive', historical_ports=('hypothesis_portfolio',))
    assert _artifact(runtime, instance, analysis).schema_id == 'scidiscovery.layered-diagnosis.v1'
    feedback = _proposal(hypothesis_keys=('mechanism',))
    feedback.pop('research_objective_key')
    feedback['evidence'] = [{'source_key': 'result_analysis', 'source_type': 'frozen_input',
                             'locator': 'remaining_contradiction'}]
    next_hypothesis = _complete(runtime, root, 'next_hypothesis', 'science.hypothesis.propose.v1',
        {'subject': 'task', 'previous_hypotheses': subject, 'result_analysis': analysis}, feedback)
    next_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='run', name='next_hypothesis')
    next_inputs = {item.port_name: item.artifact_ref for item in runtime.runs.status(next_id).inputs}
    assert next_inputs['objective_source'] == _artifact(runtime, instance, 'task').ref
    assert next_inputs['result_analysis'] == _artifact(runtime, instance, analysis).ref
    assert _artifact(runtime, instance, next_hypothesis).schema_id == 'scidiscovery.hypothesis-proposal.v2'


def test_original_text_hypothesis_cannot_invent_a_structured_objective_key(tmp_path):
    from scidiscovery.general_science_components import _hypothesis_objective_context
    from scidiscovery.operations.input_validation import InputBindingDescriptor, ValidationSources
    from scidiscovery.operation_contract import SemanticRuleViolation
    runtime, instance, root = _setup(tmp_path, native_only=True)
    root.call_tool('artifact_ingest_text', {'name': 'task', 'text': 'Test a bounded mechanism.'})
    envelope = _artifact(runtime, instance, 'task')
    raw = runtime.artifacts.read(envelope.ref)
    descriptor = InputBindingDescriptor(source_name='subject', port_name='subject', artifact_ref=envelope.ref,
        media_type=envelope.media_type, size_bytes=envelope.size_bytes, sha256=envelope.sha256,
        labels=tuple(envelope.labels.items()))
    with pytest.raises(SemanticRuleViolation, match='must not invent'):
        _hypothesis_objective_context(_proposal(hypothesis_keys=('mechanism',)),
            ValidationSources({'subject': raw}, {'subject': descriptor}), {})


@pytest.mark.parametrize('historical', [False, True])
def test_raw_hypothesis_material_reaches_critic_as_an_exact_streamed_original(tmp_path, historical):
    from pathlib import Path
    from tests.operations.worker_fixtures import attached_worker
    runtime, instance, root = _setup(tmp_path, native_only=True)
    root.call_tool('artifact_ingest_text', {'name': 'task', 'text': 'Compare mechanisms using the supplied table.'})
    _register(runtime, instance, name='table', raw=b'x,y\n1,4\n', kind='source_file', schema='opaque', media_type='text/csv')
    proposal = _proposal(hypothesis_keys=('mechanism',))
    proposal.pop('research_objective_key')
    proposal['evidence'] = [{'source_key': 'scientific_materials', 'source_type': 'frozen_input', 'locator': 'row 1'}]
    subject = _complete(runtime, root, 'hypothesis', 'science.hypothesis.propose.v1',
        {'subject': 'task', 'scientific_materials': 'table'}, proposal)
    if historical:
        changed = GENERAL.model_copy(update={'operations': tuple(
            op.model_copy(update={'version': 'next-generation'}) if op.operation_id == 'science.hypothesis.propose.v1' else op
            for op in GENERAL.operations)})
        current = compile_catalog((CORE_PLUGIN, changed, CURVE, TCAD),
            capability_selections={'general_science:experiment_task_protocol': 'none'})
        runtime.runs.operation_catalog = current
        root.facade._operation_catalog = current
        assert root.facade._run_output_family(_artifact(runtime, instance, subject)).contract_availability == 'historical'
        from tests.operations.test_historical_compatibility_paths import _historical
        forged = _historical(runtime, instance, 'forged', _artifact(runtime, instance, subject),
            'science.hypothesis.propose.v1', 'hypothesis_portfolio')
        rejected = root.call_tool('operation_preflight', {'name': 'forged_critic',
            'operation_id': 'science.hypothesis.criticize.v1',
            'inputs': [{'port': 'hypothesis_portfolio', 'artifact_names': ['forged']}]})
        assert not rejected['admissible']
    assert root.call_tool('operation_invoke', {'name': 'critic', 'operation_id': 'science.hypothesis.criticize.v1',
        'inputs': [{'port': 'hypothesis_portfolio', 'artifact_names': [subject]}],
        'instruction': 'Review the exact hypotheses using their originals.'})['result']['state'] == 'queued'
    worker = attached_worker(runtime, root, 'critic')
    opened = worker.call_tool('worker_open_assignment', {})
    assignment = json.loads(Path(opened['assignment_path']).read_bytes())
    material = next(item for item in assignment['inputs'] if item['artifact_name'] == 'table')
    assert material['materialization'] == 'controlled_tool_stream_only'
    assert not (Path(opened['workspace_path']) / material['relative_path']).exists()
    exported = worker.call_tool('worker_materialize_input', {'source_name': material['source_name']})
    assert (Path(opened['workspace_path']) / exported['relative_path']).read_bytes() == b'x,y\n1,4\n'
    Path(opened['output_directory'], 'result.json').write_bytes(canonical_json({'schema_version': 1,
        'payload': {'schema_version': 2, 'disposition': 'ready_for_experiment', 'reviews': [{
            'hypothesis_key': 'mechanism', 'physical_plausibility': 'pass', 'falsifiability': 'pass',
            'finite_discriminability': 'pass'}], 'evidence': [{'source_key': material['source_name'],
                'source_type': 'frozen_input', 'locator': 'row 1'}]},
        'handoff': {'summary': 'Reviewed the exact source table.'}}))
    completed = worker.call_tool('worker_submit_result', {})
    assert completed['state'] == 'completed', json.dumps(completed)


@pytest.mark.parametrize('action', ['start', 'advance'])
def test_remote_execution_without_hypothesis_is_rejected_before_submission(action):
    from types import SimpleNamespace
    from scidiscovery.artifact_agent.service.experiment_execution import ExperimentExecution
    from scidiscovery.operation_contract import DiagnosticError
    coordinator = object.__new__(ExperimentExecution)
    coordinator.runs = SimpleNamespace(running_task=lambda run_id: SimpleNamespace(inputs=()))
    with pytest.raises(DiagnosticError) as rejected:
        coordinator.command(SimpleNamespace(run_id='without_science'), SimpleNamespace(action=action))
    assert rejected.value.details[0]['code'] == 'experiment_hypothesis_missing'


@pytest.mark.parametrize('payload,reason', [(None, 'input_objective_missing'), ({}, 'input_objective_missing'),
    ({'objective_contract': {'statement': 'Incomplete'}}, 'input_objective_invalid')])
def test_missing_science_is_reported_without_falling_back_to_other_goal(tmp_path, payload, reason):
    runtime, instance, root = _setup(tmp_path)
    _put(runtime, instance, 'selected', payload, 'scidiscovery.scientific-foundation.v1')
    _put(runtime, instance, 'unrelated', json.loads(_foundation()), 'scidiscovery.scientific-foundation.v1')
    result = root.call_tool('operation_preflight', _request('selected'))
    assert not result['admissible']
    assert result['reason_code'] == 'input_origin_missing'
    assert result['port'] == 'subject'


def test_root_cannot_supply_internal_goal_binding(tmp_path):
    runtime, instance, root = _setup(tmp_path)
    _put(runtime, instance, 'selected', json.loads(_foundation()), 'scidiscovery.scientific-foundation.v1')
    request = _request('selected')
    request['inputs'].append(dict(port='objective_source', artifact_names=['selected']))
    with pytest.raises(RootToolError, match='input_port_unknown'):
        root.call_tool('operation_invoke', request)


def test_original_task_cannot_replace_hypothesis_but_remains_a_valid_budget_source(tmp_path):
    from types import SimpleNamespace
    from scidiscovery.artifact_agent.service.experiment_execution import ExperimentExecution
    from scidiscovery.artifact_agent.schema.common import canonical_sha256
    runtime, instance, root = _setup(tmp_path, native_only=True)
    original = '计算 2+2，保留程序和结果。\nReport any missing environment.'
    root.call_tool('artifact_ingest_text', {'name': 'task', 'text': original})
    expected = _artifact(runtime, instance, 'task').ref
    rejected = root.call_tool('operation_preflight', _request('task'))
    assert not rejected['admissible'] and rejected['reason_code'] == 'input_origin_missing'
    with pytest.raises(RootToolError, match='input_origin_missing'):
        root.call_tool('operation_invoke', _request('task'))
    assert runtime.artifacts.read(expected) == original.encode('utf-8')
    coordinator = object.__new__(ExperimentExecution)
    coordinator.executions = SimpleNamespace(artifacts=runtime.artifacts)
    run = SimpleNamespace(instance_id=instance.instance_id, inputs=(
        SimpleNamespace(port_name='objective_source', artifact_ref=expected),))
    assert coordinator.budget_subject(run) == canonical_sha256({'instance': instance.instance_id})


@pytest.mark.parametrize('raw,kind,schema,media,labels,reason', [
    (b'Text in an arbitrary file', 'source_file', 'opaque', 'text/plain', {}, 'input_origin_missing'),
    (b'\x00\xff', 'source_text', 'opaque', 'application/octet-stream', {'source_origin': USER_TEXT_SOURCE_ORIGIN}, 'input_origin_missing'),
    (b'\xff', 'source_text', 'opaque', 'text/plain; charset=utf-8', {'source_origin': USER_TEXT_SOURCE_ORIGIN}, 'input_objective_invalid'),
    (b'Task\x00binary', 'source_text', 'opaque', 'text/plain; charset=utf-8', {'source_origin': USER_TEXT_SOURCE_ORIGIN}, 'input_objective_invalid'),
    (b'   \n', 'source_text', 'opaque', 'text/plain; charset=utf-8', {'source_origin': USER_TEXT_SOURCE_ORIGIN}, 'input_objective_invalid'),
    (b'{broken json', 'objective', 'scidiscovery.research-objective.v1', 'application/json', {}, 'input_objective_invalid'),
    (b'{broken json', 'source_text', 'scidiscovery.research-objective.v1', 'text/plain; charset=utf-8', {'source_origin': USER_TEXT_SOURCE_ORIGIN}, 'input_objective_invalid'),
    (b'{"objective_key":"x","statement":NaN}', 'objective', 'scidiscovery.research-objective.v1', 'application/json', {}, 'input_objective_invalid'),
])
def test_nontext_and_broken_structured_sources_never_become_raw_goals(tmp_path, raw, kind, schema, media, labels, reason):
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    runtime, instance, root = _setup(tmp_path)
    envelope = runtime.artifacts.register(raw, ArtifactRegistration(kind=kind, schema_id=schema,
        payload_schema_version=1, media_type=media, labels=labels, creator=runtime.actor), idempotency_key='bad-source')
    runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace='artifact', name='selected', object_id=envelope.artifact_id)
    result = root.call_tool('operation_preflight', _request('selected'))
    assert not result['admissible'] and result['reason_code'] == 'input_origin_missing'
    with pytest.raises(RootToolError, match='input_origin_missing'):
        root.call_tool('operation_invoke', _request('selected'))
    hypothesis_request = {'name': 'hypothesis', 'operation_id': 'science.hypothesis.propose.v1',
        'inputs': [{'port': 'subject', 'artifact_names': ['selected']}], 'instruction': 'Understand the selected original.'}
    hypothesis = root.call_tool('operation_preflight', hypothesis_request)
    assert not hypothesis['admissible'] and hypothesis['reason_code'] == 'input_objective_invalid'


@pytest.mark.parametrize('ambiguous', [False, True])
@pytest.mark.parametrize('original_text', [False, True])
def test_alternative_origins_deduplicate_refs_but_reject_distinct_goals(tmp_path, monkeypatch, ambiguous, original_text):
    from types import SimpleNamespace
    from scidiscovery.artifact_agent.service.operation_origins import OperationOrigins
    from scidiscovery.operations.invoke import InvocationArtifact, OperationInvocationError
    runtime, instance, root = _setup(tmp_path)
    _put(runtime, instance, 'selected', {'summary': 'Fixture result'}, 'opaque')
    if original_text:
        root.call_tool('artifact_ingest_text', {'name': 'one', 'text': 'First exact task.'})
        root.call_tool('artifact_ingest_text', {'name': 'two', 'text': 'Second exact task.'})
    else:
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
    # Test the retained goal resolver separately from experiment hypothesis admission.
    from dataclasses import replace
    goal = next(port for port in compiled.spec.inputs if port.name == 'objective_source')
    goal = goal.model_copy(update={'derivation': goal.derivation.model_copy(update={'anchor_port': 'subject'})})
    compiled = replace(compiled, spec=compiled.spec.model_copy(update={'inputs': (compiled.spec.inputs[0], goal)}))
    if ambiguous:
        with pytest.raises(OperationInvocationError, match='input_origin_ambiguous') as error:
            origin._derive_operation_inputs(compiled, resolved)
        assert 'task text' in error.value.details[0]['message']
    else:
        origin._derive_operation_inputs(compiled, resolved)
        assert [item.ref for item in resolved['objective_source']] == [first]
