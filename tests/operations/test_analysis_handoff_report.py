"""Compact reading and delivery through the existing production analysis lifecycle."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.layered_diagnosis import LayeredDiagnosisReport
from tests.operations.test_tcad_result_analysis import analysis_materials, analysis_report, analysis_system, open_analysis
from tests.operations.test_analysis_claim_scope import generic_worker, mcp_call


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
    assert domain['patch_contract']['schema'] == 'scidiscovery.layered-diagnosis.v1'
    assert 'generated_fields' not in domain['patch_contract']
    Path(opened['output_directory'], 'result.json').write_bytes(canonical_json(
        dict(schema_version=1, payload=payload)))
    result = mcp_call(worker, 'worker_submit_result', {})['result']['structuredContent']
    assert result['state'] == 'completed', result


def test_generic_analysis_finalizes_compact_draft_through_mcp(tmp_path):
    worker, opened = generic_worker(tmp_path)
    report = compact_report('experiment_results')
    assert Path(opened['start_here_path']).is_file()
    submit_compact(worker, opened, report)


@pytest.mark.parametrize('verdict, expected', [
    ('pass', 'pass'), ('fail', 'blocked'), ('inconclusive', 'inconclusive'), ('invalid_study', 'blocked'),
])
def test_analysis_verdict_projection_preserves_the_formal_report(verdict, expected):
    from scidiscovery.plugin_runtime.results import materialize_analysis_handoff
    payload = compact_report(verdict=verdict)
    value = dict(payload=deepcopy(payload))
    materialize_analysis_handoff(value)
    assert value['payload'] == payload
    assert value['handoff']['verdict'] == expected
    report = LayeredDiagnosisReport.model_validate_json(canonical_json(payload))
    assert report.gates is None
    assert report.overall_verdict == verdict and report.claim_allowed == payload['claim_allowed']


def test_handoff_normalizes_only_duplicate_fields_and_unknown_claims_still_fail():
    from scidiscovery.plugin_runtime.results import materialize_general_result
    value = dict(payload=compact_report(verdict='fail'), handoff=dict(verdict='pass', summary='Old copy',
        missing_inputs=['Separate input note'], assumptions=['Conditional premise'], next_actions=['Historical extra']))
    original_payload = deepcopy(value['payload'])
    materialize_general_result(value, 'scidiscovery.layered-diagnosis.v1')
    assert value['payload'] == original_payload
    assert 'run_status.' not in value['handoff']['summary']
    assert value['handoff']['verdict'] == 'blocked'
    assert value['handoff']['missing_inputs'] == ['Separate input note']
    assert value['handoff']['assumptions'] == ['Conditional premise']
    assert value['handoff']['next_actions'] == []
    invalid = dict(payload={'summary': 'Missing scientific verdict'})
    from scidiscovery.operations.workspace import WorkspaceProtocolError
    with pytest.raises(WorkspaceProtocolError) as error:
        materialize_general_result(invalid, 'scidiscovery.layered-diagnosis.v1')
    assert error.value.details[0]['path'] == '$.payload.overall_verdict'




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
    contents = {'experiment_plan': plan, 'execution_package': package, 'current_progress': {'unknown_future_field': 'Kept'}}
    schemas = {'experiment_plan': 'scidiscovery.experiment-portfolio.v1', 'execution_package': 'tcad.execution-package.v2',
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


def test_formal_summary_projection_leaves_other_role_contracts_unchanged():
    from scidiscovery.plugin_runtime.results import materialize_general_result
    for schema, payload in [
        ('scidiscovery.critic-review.v2', dict(disposition='ready_for_experiment')),
        ('scidiscovery.evidence-audit.v1', dict(checks=[dict(status='pass')])),
    ]:
        value = dict(payload=payload)
        materialize_general_result(value, schema)
        assert value['handoff'] == {'verdict': 'pass'}  # Summary remains the reviewer-authored conclusion.
    malformed = dict(payload=dict(summary=None, verdict='pass'), handoff=dict(summary=None))
    from scidiscovery.operations.workspace import WorkspaceProtocolError
    with pytest.raises(WorkspaceProtocolError) as error:
        materialize_general_result(malformed, 'scidiscovery.scientific-review.v1')
    assert error.value.details[0]['path'] == '$.payload.summary'
    assert malformed['payload']['summary'] is malformed['handoff']['summary'] is None
