"""Compact reading and delivery through the existing production analysis lifecycle."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scidiscovery.artifact_agent.schema.claim import project_claim_decision
from scidiscovery.artifact_agent.schema.common import canonical_json, SchemaModel
from scidiscovery.artifact_agent.schema.layered_diagnosis import LayeredDiagnosisReport
from tests.operations.test_tcad_result_analysis import analysis_materials, analysis_report, analysis_system, open_analysis
from tests.operations.test_analysis_claim_scope import generic_worker, precomputed_worker, mcp_call
from tests.operations import test_m2_curve_analysis_boundary as curve


def compact_report(alias='runtime_manifest', verdict='inconclusive'):
    original = analysis_report(alias=alias)
    return {key: value for key, value in {**original,
        'summary': 'Finite fixture finding. ' * 180,
        'overall_verdict': verdict, 'claim_allowed': verdict == 'pass',
        'evidence': [dict(source_key=alias, source_type='runtime_output', title='Bound result', locator=alias)],
        'limitations': ['Only the bound fixture observation is available.'],
    }.items() if key in {'schema_version', 'study_kind', 'experiment_key', 'plan_key',
        'summary', 'overall_verdict', 'claim_allowed', 'evidence', 'limitations'}}


def submit_compact(worker, opened, payload):
    domain = json.loads(Path(opened['domain_workspace_path']).read_bytes())
    from curve_score.analysis_workspace import GUIDANCE, REPORT_GUIDANCE
    from scidiscovery.platforms.codex import _operation_toml, tomllib
    import sys
    start = json.loads(Path(opened['start_here_path']).read_bytes())
    assert start['guidance'] == GUIDANCE
    assert domain['patch_contract']['instruction'] == REPORT_GUIDANCE
    profile = tomllib.loads(_operation_toml(worker.compiled, python=Path(sys.executable),
        python_path=None, state_root=Path(opened['workspace_path']),
        local_workspace_root=Path(opened['workspace_path']), worker_backend='local'))
    prompt = profile['developer_instructions']
    assert GUIDANCE not in prompt and REPORT_GUIDANCE not in prompt
    assert 'analysis-start.json' in prompt and '/patch_contract' in prompt
    assert domain['patch_contract']['draft_may_omit'] == ['/handoff']
    Path(opened['output_directory'], 'result.json').write_bytes(canonical_json(
        dict(schema_version=1, payload=payload)))
    result = mcp_call(worker, 'worker_submit_result', {})['result']['structuredContent']
    assert result['state'] == 'completed', result


@pytest.mark.parametrize('verdict', ['pass', 'fail', 'inconclusive', 'invalid_study'])
def test_tcad_compact_report_seals_and_preserves_scientific_claim(tmp_path, verdict):
    system = analysis_system(tmp_path, state='failed' if verdict == 'invalid_study' else 'succeeded',
        bind_names=() if verdict == 'invalid_study' else ('A', 'B'))
    worker, opened = open_analysis(system)
    payload = compact_report(verdict=verdict)
    submit_compact(worker, opened, payload)
    status = system[2].call_tool('run_status', {'name': 'analysis', 'view': 'detail'})
    envelope = status['sealed_output']
    report = LayeredDiagnosisReport.model_validate_json(canonical_json(envelope['payload']))
    assert report.summary == payload['summary'] and report.gates is None
    assert report.remaining_contradiction is report.next_action is None
    decision = project_claim_decision(report)
    assert decision.numerical_verdict == 'not_evaluable'
    assert decision.overall_verdict == verdict and decision.claim_allowed == payload['claim_allowed']
    handoff = status['scheduler_signal']
    assert handoff['verdict'] == {'fail': 'blocked', 'invalid_study': 'blocked'}.get(verdict, verdict)
    assert 'payload.summary' in handoff['summary']
    assert len(handoff['summary']) < 256 < len(report.summary)
    # Reuse both compact history and its precise receipts, without rewriting the old Artifact.
    request = deepcopy(system[3]); request['name'] = 'next_analysis'
    request['inputs'].extend([
        dict(port='prior_analysis', artifact_names=['analysis.output']),
        dict(port='prior_analysis_manifest', artifact_names=['analysis.output.recovery_manifest'])]
        if verdict in {'pass', 'inconclusive'} else [
        dict(port='current_progress', artifact_names=['analysis.output'])])
    _, new_opened = open_analysis((*system[:3], request, *system[4:]))
    start = json.loads(Path(new_opened['start_here_path']).read_bytes())
    assert any(item['pointer'] == '/limitations' and 'bound fixture' in item['text'] for item in start['excerpts'])
    assert system[2].call_tool('run_status', {'name': 'analysis', 'view': 'detail'})['sealed_output'] == envelope


@pytest.mark.parametrize('kind', ['generic', 'curve_error'])
def test_other_analysis_operations_finalize_compact_drafts_through_mcp(tmp_path, kind):
    if kind == 'generic':
        worker, opened = generic_worker(tmp_path)
        report = compact_report('experiment_results')
    else:
        from curve_score.science_operations import Components
        package = Components.curve_error_analysis.implementation(
            {name: (raw,) for name, raw in curve._inputs().items()})['curve_analysis_package'][0]
        worker, opened = precomputed_worker(tmp_path, package)
        report = compact_report('curve_analysis_package')
        assert not any(item['name'] == 'worker_curve_score' for item in worker.list_tools())
    assert Path(opened['start_here_path']).is_file()
    submit_compact(worker, opened, report)


def test_handoff_normalizes_only_duplicate_fields_and_unknown_claims_still_fail():
    from scidiscovery.artifact_agent.service.result_materialization import materialize_general_result
    value = dict(payload=compact_report(verdict='fail'), handoff=dict(verdict='pass', summary='Old copy',
        missing_inputs=['Separate input note'], assumptions=['Conditional premise'], next_actions=['Historical extra']))
    materialize_general_result(value, 'scidiscovery.layered-diagnosis.v1')
    assert value['handoff']['verdict'] == 'blocked'
    assert value['handoff']['missing_inputs'] == ['Separate input note']
    assert value['handoff']['assumptions'] == ['Conditional premise']
    assert value['handoff']['next_actions'] == ['Historical extra']
    invalid = dict(payload={'summary': 'Missing scientific verdict'})
    materialize_general_result(invalid, 'scidiscovery.layered-diagnosis.v1')
    assert 'handoff' not in invalid
    with pytest.raises(TypeError, match='supported report'):
        project_claim_decision(SchemaModel())
    legacy = LayeredDiagnosisReport.model_validate_json(canonical_json(analysis_report()))
    assert project_claim_decision(legacy).numerical_verdict == legacy.gates.numerical_validity.status


def test_sealed_compact_analysis_reaches_next_design_preflight_and_original_input(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from tests.operations import test_agent_contract_alignment as alignment
    from tests.operations import test_general_transform_operations as transforms
    from tests.operations import test_tcad_result_analysis as tcad
    open_runtime = tcad.open_runtime
    monkeypatch.setattr(tcad, 'open_runtime', lambda **kwargs:
        open_runtime(approval_receipt_secret=b'fixture-only-receipt-key-32-bytes', **kwargs))
    system = analysis_system(tmp_path)
    worker, opened = open_analysis(system)
    submit_compact(worker, opened, compact_report())
    catalog, runtime, root = system[:3]
    completed = runtime.runs.status(worker._run_id)
    original = runtime.artifacts.read(completed.output_ref)
    # Reuse the existing design cohort fixture in the same instance. Its approval
    # stub belongs to that fixture; this test checks feedback transport, not governance.
    monkeypatch.setattr(transforms, '_root', lambda *args, **kwargs:
        (runtime, SimpleNamespace(instance_id=completed.instance_id), root))
    _, _, _, request, _ = alignment._feedback_root(tmp_path, monkeypatch,
        alignment.experiment_case.__wrapped__(), 'science.experiment.design.v1', catalog=catalog)
    request['inputs'].append(dict(port='current_progress', artifact_names=['analysis.output']))
    checked = root.call_tool('operation_preflight', request)
    assert checked['admissible'], checked
    root.call_tool('operation_invoke', request)
    operation = catalog.operation(request['operation_id'])
    designer = LocalWorkerMCPRouter(runtime.runs, operation_id=operation.spec.operation_id, operation_digest=operation.digest)
    opened = designer.call_tool('worker_open_assignment', {})
    assignment = json.loads(Path(opened['assignment_path']).read_bytes())
    item = next(item for item in assignment['inputs'] if item['port'] == 'current_progress')
    assert (Path(opened['workspace_path'])/item['relative_path']).read_bytes() == original
    assert json.loads(original)['limitations'] == compact_report()['limitations']


def pointer(value, path):
    for part in path.split('/')[1:]:
        part = part.replace('~1', '/').replace('~0', '~')
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def view_fixture(tmp_path, *, oversized=False):
    from scidiscovery.operations.workspace import WorkspaceMaterializationRequest
    plan, package, *_ = analysis_materials()
    plan, package = plan.model_dump(mode='json'), package.model_dump(mode='json')
    proposal = plan['proposals'][0]
    proposal['cases'] = [dict(case_key=f'case_{n}', scientific_role='baseline' if n == 0 else 'perturbation',
        purpose='Fixture case', settings=[]) for n in range(12)]
    observable = '完整公式和阈值' * 160
    proposal['required_observables'] = [observable]
    proposal['comparison_contract'] = dict(baseline_case_key='case_0',
        comparison_case_keys=[f'case_{n}' for n in range(1, 12)], required_observables=[observable],
        variables=[dict(variable_key=f'variable_{n}', scientific_path='Fixture parameter',
            factor_type='physical', comparison_role='intended_change', unit='um', equivalence_rule='exact',
            rationale='Read the complete original', expectations=[dict(case_key=f'case_{c}',
                value=('长值' * 20000 if oversized and n == 0 else c + n / 10)) for c in reversed(range(12))])
            for n in range(13)])
    package['project']['case_parameter_bindings'] = [{'control_only_marker': n} for n in range(156)]
    contents = {'experiment_plan': plan, 'reviewed_package': package, 'current_progress': {'unknown_future_field': 'Kept'}}
    schemas = {'experiment_plan': 'scidiscovery.experiment-portfolio.v1', 'reviewed_package': 'tcad.reviewed-deck-package.v2',
        'current_progress': 'future.schema'}
    inputs, paths, descriptors = [], {}, {}
    (tmp_path/'inputs').mkdir()
    for alias, value in contents.items():
        relative = f'inputs/{alias}.json'; path = tmp_path/relative
        path.write_bytes(canonical_json(value)); paths[alias] = path
        descriptors[alias] = SimpleNamespace(port_name=alias, size_bytes=path.stat().st_size,
            artifact_ref=SimpleNamespace(schema_id=schemas[alias]), output_name=None)
        inputs.append(dict(source_name=alias, port=alias, relative_path=relative, description='Fixture input',
            exposure='full', usage='evidence_inventory', media_type='application/json'))
    (tmp_path/'assignment.json').write_text(json.dumps(dict(inputs=inputs, tools=[])))
    request = WorkspaceMaterializationRequest(operation_id='fixture', workspace=tmp_path, input_paths=paths,
        binding_descriptors=descriptors, provisional_roots=(), edit_protocol='native')
    return request, contents


@pytest.mark.parametrize('oversized', [False, True])
def test_bounded_views_preserve_originals_matrix_values_and_full_rule_pointers(tmp_path, oversized):
    from tcad_artifact.analysis_bindings import materialize, source_bindings, workspace_sources
    request, contents = view_fixture(tmp_path, oversized=oversized)
    originals = {name: path.read_bytes() for name, path in request.input_paths.items()}
    sources = source_bindings(workspace_sources(request))
    materialize(request)
    start_raw, view_raw = ((tmp_path/name).read_bytes() for name in ('analysis-start.json', 'analysis-bindings.json'))
    assert len(start_raw) + len(view_raw) <= 32 * 1024
    assert b'control_only_marker' not in start_raw + view_raw
    assert {name: path.read_bytes() for name, path in request.input_paths.items()} == originals
    assert source_bindings(workspace_sources(request)) == sources
    start, view = json.loads(start_raw), json.loads(view_raw)
    assert {item['source_name'] for item in start['inputs']} == set(contents)
    assert all(item['size_bytes'] == len(originals[item['source_name']]) for item in start['inputs'])
    assert next(item for item in start['inputs'] if item['source_name'] == 'current_progress')['schema_id'] == 'future.schema'
    assert any(item['pointer'] == '/review' for item in view['project_index'])
    observables = [item for item in start['plan_index'] if 'observable' in item]
    assert len(observables) == 1 and len(observables[0]['pointers']) == 2
    for path in observables[0]['pointers']:
        assert pointer(contents['experiment_plan'], path).startswith(observables[0]['observable'])
    values = 0
    for entry in view['case_matrix']:
        original = pointer(contents[entry['source_name']], entry['pointer'])
        if 'case_columns' in entry:
            columns = entry['case_columns']
        if 'values' in entry:
            for case, index, value in zip(columns, entry['expectation_indices'], entry['values'], strict=True):
                assert original['expectations'][index] == {'case_key': case, 'value': value}
                values += 1
    assert values == (144 if oversized else 156)
    assert bool(view['omitted']) == oversized
    for entry in view['project_index']:
        original = pointer(contents[entry['source_name']], entry['pointer'])
        if 'source_file' in entry:
            assert isinstance(original, str) and len(original.encode()) == entry['content_bytes']


@pytest.mark.parametrize('explicit_notes', [False, True])
def test_scientific_review_can_submit_one_formal_summary(tmp_path, explicit_notes):
    from tests.operations import test_l4_local_tcad as f
    catalog, runtime, root, _ = f._system(tmp_path)
    request = dict(name='summary_review', operation_id='science.object.review.v1', instruction='Review the bound fixture.',
        inputs=[dict(port='experiment_plan', artifact_names=['experiment_plan'])])
    root.call_tool('operation_invoke', request)
    compiled = catalog.operation(request['operation_id'])
    worker = f.LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    opened = worker.call_tool('worker_open_assignment', {})
    schema = json.loads(Path(opened['workspace_path'], 'schema/result.schema.json').read_bytes())
    assert '/handoff' in schema['properties']['payload']['description']
    payload = dict(review_target='experiment_portfolio', verdict='revise', summary='Finite formal finding.')
    value = dict(schema_version=1, payload=payload)
    if not explicit_notes:
        for field in ('verdict', 'summary'):
            invalid = deepcopy(value)
            invalid['payload'][field] = []
            Path(opened['output_directory'], 'result.json').write_bytes(canonical_json(invalid))
            rejected = worker.call_tool('worker_submit_result', {})
            assert rejected['state'] == 'rejected', rejected
            assert rejected['diagnostics'][0]['path'] == '$.payload.' + field
    if explicit_notes:
        value['handoff'] = dict(summary='Preserve explicit prior note.', assumptions=['A separate premise.'])
    Path(opened['output_directory'], 'result.json').write_bytes(canonical_json(value))
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    status = root.call_tool('run_status', dict(name=request['name'], output_paths=['/summary']))
    assert status['selected_output']['items'][0]['value'] == payload['summary']
    assert status['scheduler_signal']['verdict'] == 'revise'
    assert status['scheduler_signal']['summary'] == ('Preserve explicit prior note.' if explicit_notes
        else 'Read the sealed payload.summary for the scientific conclusion.')


def test_formal_summary_projection_leaves_other_role_contracts_unchanged():
    from scidiscovery.artifact_agent.service.result_materialization import materialize_general_result
    for schema, payload in [
        ('scidiscovery.critic-review.v2', dict(disposition='ready_for_experiment')),
        ('scidiscovery.evidence-audit.v1', dict(checks=[dict(status='pass')])),
    ]:
        value = dict(payload=payload)
        materialize_general_result(value, schema)
        assert 'handoff' not in value
    malformed = dict(payload=dict(summary=None, verdict='pass'), handoff=dict(summary=None))
    from scidiscovery.operations.workspace import WorkspaceProtocolError
    with pytest.raises(WorkspaceProtocolError) as error:
        materialize_general_result(malformed, 'scidiscovery.scientific-review.v1')
    assert error.value.details[0]['path'] == '$.payload.summary'
    assert malformed['payload']['summary'] is malformed['handoff']['summary'] is None
