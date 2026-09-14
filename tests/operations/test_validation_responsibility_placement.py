"""Regressions for the concrete responsibility-placement audit failures."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

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
    from curve_figure_evidence.figure_science_operations import _validate_request_context
    from tests.operations.test_minimal_figure_extraction import _request, _png
    raw = _png()
    value = json.loads(_request(raw))
    value.update(request_status='unresolved', unresolved_reasons=['Recovery unavailable.'])
    value['source'] = {key: value['source'][key] for key in ('source_kind', 'media_type', 'source_sha256')}
    request = FigureDigitizationRequest.model_validate_json(canonical_json(value))
    assert request.plot_bbox is not None
    _validate_request_context(value, {'paper_source': raw}, {})
    with pytest.raises(ValueError, match='cannot be materialized'):
        request.require_ready()
    with pytest.raises(ValueError, match='complete recovered source metadata'):
        FigureDigitizationRequest.model_validate_json(canonical_json(dict(value, request_status='ready', unresolved_reasons=[]))).require_ready()
    from scidiscovery.operation_contract import SemanticRuleViolation
    value['source']['source_sha256'] = 'f' * 64
    with pytest.raises(SemanticRuleViolation, match='source hash'):
        _validate_request_context(value, {'paper_source': raw}, {})


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
    from scidiscovery.artifact_agent.service.result_materialization import finalize_general_result
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


def test_review_submission_derives_handoff_from_formal_verdict(tmp_path):
    from tests.operations.test_m2_curve_analysis_boundary import _root, _inputs, _register_inputs
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    catalog, runtime, instance, root = _root(tmp_path)
    _register_inputs(runtime, instance, _inputs())
    root.call_tool('operation_invoke', dict(name='review_without_mirror', operation_id='science.object.review.v1',
        inputs=[dict(port='experiment_plan', artifact_names=['experiment_plan'])], instruction='Review the bound fixture.'))
    compiled = catalog.operation('science.object.review.v1')
    worker = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    opened = worker.call_tool('worker_open_assignment', {})
    Path(opened['output_directory'], 'result.json').write_bytes(canonical_json(dict(schema_version=1,
        handoff=dict(summary='Finite review.'), payload=dict(review_target='experiment_portfolio', verdict='revise', summary='Revision needed.'))))
    submitted = worker.call_tool('worker_submit_result', {})
    assert submitted['state'] == 'completed', submitted
    status = root.call_tool('run_status', {'name': 'review_without_mirror'})
    assert status['scheduler_signal']['verdict'] == 'revise'


def test_deck_review_copies_capability_from_exact_subject(tmp_path):
    from tcad_artifact.operation_workspace import finalize_review_workspace
    source = tmp_path / 'project.json'
    raw = canonical_json({'capability_sha256': 'a' * 64})
    source.write_bytes(raw)
    request = _final_request(tmp_path, 'tcad.deck-review-report.v1', {'verdict': 'revise', 'summary': 'Finite review.'}, inputs={'project': source})
    result = json.loads(finalize_review_workspace(request))
    assert result['payload']['capability_sha256'] == 'a' * 64
    assert result['handoff']['verdict'] == 'revise'
    assert source.read_bytes() == raw


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


def test_curve_error_bad_bundle_is_rejected_before_transform(tmp_path):
    from tests.operations.test_m2_curve_analysis_boundary import _root, _inputs, _register_inputs, _analysis_request
    catalog, runtime, instance, root = _root(tmp_path)
    values = _inputs()
    metric = json.loads(values['metric_report'])
    metric['curve_bundle_sha256'] = 'f' * 64
    values['metric_report'] = canonical_json(metric)
    _register_inputs(runtime, instance, values)
    result = root.call_tool('operation_preflight', _analysis_request())
    assert not result['admissible']
    assert result['reason_code'] == 'input_metric_bundle_mismatch'
    assert result['diagnostics'][0]['path'] == '$.inputs.metric_report.curve_bundle_sha256'


def test_runtime_collection_mismatch_is_an_input_failure():
    from tcad_artifact.operation_transforms import runtime_inputs
    from tests.operations.test_tcad_result_analysis import analysis_materials
    from scidiscovery.operations.input_validation import ValidationSources
    # The owning analysis fixture returns the same exact package and manifest family.
    _, package, manifest, _, _ = analysis_materials()
    sources = ValidationSources({'reviewed_package': canonical_json(package.model_dump(mode='json')), 'runtime_manifest': manifest}, {})
    with pytest.raises(OperationInvocationError, match='input_runtime_collection_mismatch'):
        runtime_inputs(sources)


def test_historical_package_is_readable_but_nonpassing_package_cannot_execute():
    from tests.operations.test_tcad_result_analysis import analysis_materials
    from tcad_artifact.project_packager import ReviewedDeckPackage, validate_reviewed_deck_json, PackagerError
    _, package, _, _, _ = analysis_materials()
    value = package.model_dump(mode='json')
    value['review'].update(verdict='blocked', execution_ready=False)
    raw = canonical_json(value)
    ReviewedDeckPackage.model_validate_json(raw)
    with pytest.raises(PackagerError, match='invalid'):
        validate_reviewed_deck_json(raw)


def test_transform_engineering_failure_and_unavailable_are_distinct(tmp_path, monkeypatch):
    from scidiscovery.operations import invoke
    from scidiscovery.operation_contract import DiagnosticError
    from scidiscovery.operations.input_validation import OperationEngineeringError
    from tests.operations.test_m2_curve_analysis_boundary import _root, _inputs, _register_inputs, _analysis_request
    from scidiscovery.artifact_agent.interfaces.mcp_root import OperationCallInput
    _, runtime, instance, root = _root(tmp_path)
    values = _inputs()
    _register_inputs(runtime, instance, values)
    typed = OperationCallInput.model_validate(_analysis_request())
    bound = root.facade._prepare_operation_call(**{**typed.model_dump(exclude={'inputs'}), 'inputs': typed.inputs})
    def bug(_):
        raise ValueError('unexpected internal value')
    monkeypatch.setattr(invoke, '_executor_callable', lambda _: bug)
    with pytest.raises(OperationEngineeringError, match='executor_component_failed'):
        invoke.execute_compiled_transform(bound, values)
    expected = DiagnosticError('computation_unavailable')
    def unavailable(_):
        raise expected
    monkeypatch.setattr(invoke, '_executor_callable', lambda _: unavailable)
    with pytest.raises(DiagnosticError) as failure:
        invoke.execute_compiled_transform(bound, values)
    assert failure.value is expected


def test_unresolved_request_cannot_enter_quantitative_transform():
    from tests.operations.test_minimal_figure_extraction import _request, _png
    from curve_figure_evidence.operation_transforms import validate_materialization_inputs, FIGURE_OPERATIONS
    raw = _png()
    value = json.loads(_request(raw))
    sources = {'figure_request': canonical_json(value), 'paper_source': raw}
    assert FIGURE_OPERATIONS[0].input_validation is not None
    validate_materialization_inputs(sources)
    value.update(request_status='unresolved', unresolved_reasons=['Image identity is incomplete.'])
    with pytest.raises(OperationInvocationError, match='input_figure_not_ready'):
        validate_materialization_inputs(dict(sources, figure_request=canonical_json(value)))


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
