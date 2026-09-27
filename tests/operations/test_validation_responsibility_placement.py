"""Regressions for the concrete responsibility-placement audit failures."""
import json

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.operations.input_validation import OperationInvocationError


def test_curve_contract_pair_is_checked_at_admission():
    from curve_score.science_operations import _curve_contract_inputs, _curve_contract_context
    from curve_score.curve_contract_compiler import CurveContractCompileInput, compile_curve_contract
    from tests.operations.test_m2_curve_analysis_boundary import _compiler_plan, _compiler_objective, _bundle
    plan, objective, bundle = _compiler_plan(), _compiler_objective(), _bundle()
    sources = dict(experiment_plan=plan.canonical_json(), research_objective=objective.canonical_json(),
                   reference_bundle=bundle.canonical_json())
    _curve_contract_inputs(sources)
    wrong = objective.model_copy(update={'objective_key': 'different_objective'})
    with pytest.raises(OperationInvocationError, match='input_objective_mismatch'):
        _curve_contract_inputs(dict(sources, research_objective=wrong.canonical_json()))
    request = CurveContractCompileInput.model_validate(dict(experiment_key='implementation_check',
        target_bindings=[dict(target_key='target_implementation', reference_series_key='reference')],
        candidate_case_keys=['baseline'], comparison_metric='residual_rms'))
    contract = compile_curve_contract(request, objective=objective, portfolio=plan, reference_bundle=bundle)
    _curve_contract_context(contract.model_dump(mode='json'), sources, {})
    from scidiscovery.operation_contract import SemanticRuleViolation
    with pytest.raises(SemanticRuleViolation):
        compile_curve_contract(request, objective=wrong, portfolio=plan, reference_bundle=bundle)
    invalid = contract.model_copy(update={'experiment_key': 'invented'})
    with pytest.raises(SemanticRuleViolation):
        _curve_contract_context(invalid.model_dump(mode='json'), sources, {})


def test_analysis_submission_does_not_requalify_the_bound_package(tmp_path, monkeypatch):
    from tests.operations.test_tcad_result_analysis import analysis_system, open_analysis, write_analysis, analysis_report
    import tcad_artifact.project_packager as packager
    system = analysis_system(tmp_path)
    worker, opened = open_analysis(system)
    def forbidden(*args, **kwargs):
        pytest.fail('record reading reran project qualification')
    monkeypatch.setattr(packager, 'validate_deck_review_against_project', forbidden)
    write_analysis(opened, analysis_report())
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'


def test_unresolved_figure_retains_source_and_partial_fields_without_recovery():
    from curve_figure_evidence.figure_digitization_contract import FigureDigitizationRequest
    from curve_figure_evidence.figure_digitization_contract import materialize_figure_request
    from tests.operations.test_minimal_figure_extraction import _request, _png
    raw = _png()
    value = json.loads(_request(raw))
    value.update(request_status='unresolved', unresolved_reasons=['Recovery unavailable.'])
    value['source'] = {key: value['source'][key] for key in ('source_kind', 'media_type', 'source_sha256')}
    request = FigureDigitizationRequest.model_validate_json(canonical_json(value))
    assert request.plot_bbox is not None
    materialize_figure_request(value, raw)
    with pytest.raises(ValueError, match='cannot be materialized'):
        request.require_ready()
    with pytest.raises(ValueError, match='complete recovered source metadata'):
        FigureDigitizationRequest.model_validate_json(canonical_json(dict(value, request_status='ready', unresolved_reasons=[]))).require_ready()
    from scidiscovery.operation_contract import SemanticRuleViolation
    value['source']['source_sha256'] = 'f' * 64
    with pytest.raises(ValueError, match='source hash'):
        materialize_figure_request(value, raw)


def test_pdf_timeout_is_not_a_scientific_output_error(monkeypatch):
    import subprocess
    from curve_figure_evidence import figure_source
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired('pdfimages', 1)
    monkeypatch.setattr(figure_source.subprocess, 'run', timeout)
    with pytest.raises(TimeoutError, match='timed out'):
        figure_source._run(['pdfimages'], timeout_seconds=1)


def _final_request(tmp_path, schema_id, payload, *, inputs=None, handoff=None):
    from scidiscovery.operations.workspace import WorkspaceFinalizationRequest
    (tmp_path / 'output').mkdir(exist_ok=True)
    (tmp_path / 'output/result.json').write_bytes(canonical_json(dict(
        schema_version=1, handoff=handoff or {'summary': 'Synthetic fixture.'}, payload=payload)))
    return WorkspaceFinalizationRequest('fixture', tmp_path, inputs or {}, 2 * 1024**2, output_schema_id=schema_id)


def test_plan_draft_materializes_count_and_goal_without_changing_scientific_choices(tmp_path):
    from tests.operations.test_m2_curve_analysis_boundary import _compiler_plan
    from scidiscovery.plugin_runtime.results import finalize_general_result
    from scidiscovery.artifact_agent.schema.experiment import ExperimentPortfolio
    plan = _compiler_plan().model_dump(mode='json')
    expected = json.loads(canonical_json(plan))
    plan['proposals'][0]['resource_estimate'].pop('case_count')
    plan['proposals'][0]['objectives'].remove(plan['objective'])
    result = json.loads(finalize_general_result(_final_request(tmp_path, 'scidiscovery.experiment-portfolio.v1', plan)))
    assert result['payload'] == expected
    ExperimentPortfolio.model_validate_json(canonical_json(result['payload']))
    assert result['payload']['proposals'][0]['current_objectives'] == expected['proposals'][0]['current_objectives']


def test_parameter_draft_materializes_only_objective_copies_and_doi_identity(tmp_path):
    from tests.operations.test_m2_parameter_package import _package
    from tcad_artifact.parameter_operations import _finalize_parameter_result, ParameterEvidencePackage
    value = _package().model_dump(mode='json')
    source = value['source_catalog']['sources'][0]
    source['doi'] = 'https://doi.org/10.1234/ABC'
    source.pop('work_key')
    value['scientific_intake']['problem_frame'].pop('objective')
    request = _final_request(tmp_path, 'scidiscovery.parameter-evidence-package.v1', value)
    result = json.loads(_finalize_parameter_result(request))['payload']
    assert result['source_catalog']['sources'][0]['work_key'] == 'doi:10.1234/abc'
    assert result['scientific_intake']['problem_frame']['objective'] == result['scientific_intake']['scientific_foundation']['objective']
    assert result['device_parameters'] == value['device_parameters']
    ParameterEvidencePackage.model_validate_json(canonical_json(result))


def test_figure_draft_materializes_recovered_metadata_and_retains_image_choice():
    from tests.operations.test_minimal_figure_extraction import _png, _request
    from curve_figure_evidence.figure_digitization_contract import materialize_figure_request, FigureDigitizationRequest
    source = _png()
    value = json.loads(_request(source))
    expected = value['source'].copy()
    for key in ('width', 'height', 'recovered_image_sha256', 'recovery_tool', 'recovery_tool_version'):
        value['source'].pop(key)
    result = materialize_figure_request(value, source)
    assert result['source'] == expected
    assert result['series'] == value['series']
    FigureDigitizationRequest.model_validate_json(canonical_json(result)).require_ready()




def test_runtime_collection_mismatch_is_an_input_failure():
    from tcad_artifact.operation_transforms import runtime_inputs
    from tests.operations.test_tcad_result_analysis import analysis_materials
    from scidiscovery.operations.input_validation import ValidationSources
    # The owning analysis fixture returns the same exact package and manifest family.
    _, package, manifest, _, _ = analysis_materials()
    sources = ValidationSources({'execution_package': canonical_json(package.model_dump(mode='json')), 'runtime_manifest': manifest}, {})
    with pytest.raises(OperationInvocationError, match='input_runtime_collection_mismatch'):
        runtime_inputs(sources)


def test_execution_package_does_not_reintroduce_optional_review_as_a_gate():
    from tests.operations.test_tcad_result_analysis import analysis_materials
    from tcad_artifact.project_packager import ExecutionPackage, validate_execution_package_json, PackagerError
    _, package, _, _, _ = analysis_materials()
    value = package.model_dump(mode='json')
    value['review'].update(verdict='blocked', execution_ready=False)
    raw = canonical_json(value)
    ExecutionPackage.model_validate_json(raw)
    assert validate_execution_package_json(raw).review.verdict == 'blocked'
    value['review'] = None
    assert validate_execution_package_json(canonical_json(value)).review is None






def test_actual_finalizer_timeout_is_not_reported_as_checker_failure(tmp_path, monkeypatch):
    from tests.operations.test_tcad_result_analysis import analysis_system, open_analysis, write_analysis, analysis_report
    system = analysis_system(tmp_path)
    worker, opened = open_analysis(system)
    write_analysis(opened, analysis_report())
    def timeout(*args, **kwargs):
        raise TimeoutError('fixture image recovery timeout')
    runs = system[1].runs
    monkeypatch.setattr(runs, '_finalize_workspace', timeout)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'failed'
    assert runs.diagnostic_summary(runs.status(worker._run_id))['failure']['category'] == 'tool_timeout'
