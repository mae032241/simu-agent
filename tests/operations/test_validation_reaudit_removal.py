"""Allow bounded scientific work while preserving real identity and computation checks."""
from copy import deepcopy
from decimal import Decimal
import json
from types import SimpleNamespace

import pytest
from pydantic import TypeAdapter, ValidationError

from curve_figure_evidence.figure_digitization_contract import FigureDigitizationRequest
from curve_score.schema import CurveComparisonSpec, CurveOperatorSpec
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.experiment import ExperimentPortfolio
from scidiscovery.artifact_agent.schema.experiment_intent import (
    ExperimentDesignIntent, materialize_experiment_design_intent,
)
from scidiscovery.artifact_agent.schema.research_objective import ResearchObjectiveContract
from scidiscovery.artifact_agent.schema.validation import HypothesisAssessment
from scidiscovery.operation_contract import SemanticRuleViolation
from tcad_artifact.device_parameters import ScientificDecimal
from tcad_artifact.parameter_operations import ParameterEvidencePackage, _audit_context
from tcad_artifact.project_packager import validate_project_case_controls
from tcad_artifact.plugin import _author_context, _review_context
from tests.operations.test_agent_contract_alignment import experiment_case, _review_run
from tests.operations.test_l4_local_tcad import _review_context_fixture
from tests.operations.test_m2_parameter_package import _package
from tests.operations.test_minimal_figure_extraction import _png, _request
from tests.operations.test_tcad_result_analysis import (
    analysis_report, analysis_system, open_analysis, raw_request, write_analysis,
)


def _plan(experiment_case):
    intent, sources = deepcopy(experiment_case)
    intent['objective_key'] = 'objective_expected'
    return materialize_experiment_design_intent(
        ExperimentDesignIntent.model_validate_json(canonical_json(intent)),
        ResearchObjectiveContract.model_validate_json(sources['research_objective']),
    ).model_dump(mode='json')


def test_review_can_submit_multiple_locators_and_repeated_references(tmp_path, experiment_case):
    raw = canonical_json(_plan(experiment_case))
    runtime, run_id, workspace = _review_run(tmp_path, {'experiment_plan': raw})
    payload = {
        'review_target': 'experiment_portfolio', 'verdict': 'revise', 'summary': 'Two exact locations.',
        'evidence': [{'source_key': 'experiment_plan', 'source_type': 'frozen_input', 'locator': path}
                     for path in ('experiment_plan:/proposals/0', 'experiment_plan:/validation_plans/0')],
        'evidence_item_keys': ['item.a', 'item.a'],
        'findings': [{'finding_key': 'scope', 'statement': 'Review the relation between these locations.',
                      'epistemic_status': 'inference', 'evidence_keys': ['experiment_plan', 'experiment_plan']}],
    }
    output = workspace.output_directory / 'result.json'
    envelope = {'schema_version': 1, 'handoff': {'verdict': 'revise', 'summary': 'Bounded review.'}, 'payload': payload}
    payload['evidence'][0]['source_key'] = 'unbound_source'
    output.write_bytes(canonical_json(envelope))
    assert runtime.runs.submit(run_id)[0] == 'rejected'
    payload['evidence'][0]['source_key'] = 'experiment_plan'
    output.write_bytes(canonical_json(envelope))
    assert runtime.runs.submit(run_id) == ('completed', ())


def test_parameter_family_preserves_repeated_citations_without_overwriting_types():
    raw = _package().model_dump(mode='json')
    foundation = raw['scientific_intake']['scientific_foundation']
    foundation['evidence'].append({**foundation['evidence'][0], 'locator': 'source_a:line-2'})
    foundation['items'][0]['evidence_keys'] *= 2
    foundation['items'][0]['tags'] = ['parameter', 'parameter']
    raw['source_catalog']['sources'][0]['authors'] = ['A. Smith', 'A. Smith']
    parsed = ParameterEvidencePackage.model_validate_json(canonical_json(raw))
    assert len(parsed.scientific_intake.scientific_foundation.evidence) == 2
    # The earlier citation must not be silently hidden by a dict keyed on source_key.
    foundation['evidence'][0]['source_type'] = 'runtime_output'
    with pytest.raises(ValidationError, match='source type differs'):
        ParameterEvidencePackage.model_validate_json(canonical_json(raw))


def test_partial_comparison_retains_valid_refs_and_can_be_independently_reviewed(tmp_path, experiment_case):
    raw = _plan(experiment_case)
    proposal = raw['proposals'][0]
    proposal['cases'].append({**deepcopy(proposal['cases'][0]), 'case_key': 'additional',
                              'scientific_role': 'control', 'purpose': 'Additional observation.'})
    proposal['resource_estimate']['case_count'] += 1
    proposal['changed_factors'].append({'name': 'auxiliary', 'factor_type': 'implementation',
                                       'unit': '1', 'values': [0, 1], 'rationale': 'Only the extra case changes it.'})
    for index, case in enumerate(proposal['cases']):
        case['settings'].append({'name': 'auxiliary', 'unit': '1', 'value': int(index == 2)})
    proposal['required_observables'].append('additional observation')
    proposal['objectives'] *= 2
    proposal['current_objectives'] *= 2
    parsed = ExperimentPortfolio.model_validate_json(canonical_json(raw))
    contract = parsed.proposals[0].comparison_contract
    bindings = [SimpleNamespace(experiment_key=proposal['experiment_key'], case_key=item.case_key,
                               variable_key=variable.variable_key, scientific_path=variable.scientific_path,
                               unit=variable.unit, realized_value=str(item.value))
                for variable in contract.variables for item in variable.expectations]
    bindings.append(SimpleNamespace(experiment_key=proposal['experiment_key'], case_key='additional',
                                    variable_key='auxiliary', unit='1', realized_value='1'))
    project = SimpleNamespace(case_parameter_bindings=bindings, parameter_bindings=())
    validate_project_case_controls(project, parsed.canonical_json())
    bindings[-1].variable_key = 'undeclared_control'
    with pytest.raises(SemanticRuleViolation, match='undeclared control'):
        validate_project_case_controls(project, parsed.canonical_json())
    bindings[-1].variable_key = 'auxiliary'
    bindings[-1].realized_value = '0'
    with pytest.raises(SemanticRuleViolation, match='additional case control differs'):
        validate_project_case_controls(project, parsed.canonical_json())
    bindings[-1].realized_value = '1'
    runtime, run_id, workspace = _review_run(tmp_path, {'experiment_plan': parsed.canonical_json()})
    (workspace.output_directory / 'result.json').write_bytes(canonical_json({
        'schema_version': 1, 'handoff': {'verdict': 'revise', 'summary': 'Review local coverage.'},
        'payload': {'review_target': 'experiment_portfolio', 'verdict': 'revise',
                    'summary': 'The extra diagnostic is outside this comparison.'},
    }))
    assert runtime.runs.submit(run_id) == ('completed', ())
    for field, missing in (('comparison_case_keys', 'unknown_case'),):
        invalid = deepcopy(raw)
        invalid['proposals'][0]['comparison_contract'][field].append(missing)
        with pytest.raises(ValidationError):
            ExperimentPortfolio.model_validate_json(canonical_json(invalid))


@pytest.mark.parametrize('labels', [
    {'metric_profile': 'smooth_curve'},
    {'purpose': 'numerical_convergence', 'gate_scope': 'diagnostic_only', 'metric_profile': 'sharp_front'},
])
def test_curve_labels_do_not_block_valid_operator_or_its_sealed_result(tmp_path, labels):
    worker, opened = open_analysis(analysis_system(tmp_path))
    request = raw_request()
    comparison = request['comparison_spec']['comparisons'][0]
    for field in ('purpose', 'gate_scope', 'metric_profile'):
        comparison.pop(field, None)
    comparison.update(labels)
    comparison['operators'] = [{'operator_key': 'crossing', 'kind': 'crossing_shift', 'level': 1e11}]
    declarations = request['comparison_spec']['series_declarations']
    reference = next(x for x in declarations if x['series_key'] == comparison['reference_series'])
    declarations.append({**reference, 'series_key': 'unused_reference', 'case_key': 'unused_case'})
    for item in declarations:
        item.pop('scientific_role', None)
    record = worker.call_tool('worker_tcad_curve_score', {'record_key': 'local_crossing', 'request': request})
    assert record['status'] == 'computed', record
    report = analysis_report()
    report['calculation_records'] = [record]
    write_analysis(opened, report)
    result = worker.call_tool('worker_submit_result', {})
    assert result['state'] == 'completed', result


def test_curve_subset_keeps_actual_reference_and_operator_checks():
    raw = raw_request()['comparison_spec']
    raw['reference_dispositions'] = [{'series_key': 'missing', 'disposition': 'compare', 'rationale': 'Not present.'}]
    with pytest.raises(ValidationError, match='not actually compared'):
        CurveComparisonSpec.model_validate_json(canonical_json(raw))
    raw['reference_dispositions'] = []
    raw['comparisons'][0]['reference_series'] = 'missing'
    with pytest.raises(ValidationError, match='undeclared series'):
        CurveComparisonSpec.model_validate_json(canonical_json(raw))
    with pytest.raises(ValidationError, match='require a level'):
        CurveOperatorSpec.model_validate_json(canonical_json({'operator_key': 'a', 'kind': 'crossing_shift'}))


@pytest.mark.parametrize('keep', ['plot_bbox', 'axis_calibration', 'series', 'all'])
def test_unresolved_figure_keeps_partial_progress_but_cannot_execute(keep):
    raw = json.loads(_request(_png()))
    raw.update(request_status='unresolved', unresolved_reasons=['Remaining identity needs review.'])
    for field in ('plot_bbox', 'axis_calibration', 'series'):
        if keep not in (field, 'all'):
            raw.pop(field)
    parsed = FigureDigitizationRequest.model_validate_json(canonical_json(raw))
    field = 'plot_bbox' if keep == 'all' else keep
    assert parsed.model_dump(mode='json', exclude_unset=True)[field] == raw[field]
    with pytest.raises(ValueError, match='cannot be materialized'):
        parsed.require_ready()
    raw['plot_bbox'] = [-1, 0, 100, 100]
    with pytest.raises(ValidationError, match='exceeds'):
        FigureDigitizationRequest.model_validate_json(canonical_json(raw))


@pytest.mark.parametrize('outcome', ['inconclusive', 'invalid_study'])
def test_trigger_observation_does_not_determine_scientific_verdict(outcome):
    raw = {'hypothesis_key': 'h', 'outcome': outcome, 'evidence_keys': ['e', 'e'],
           'falsifiers_triggered': ['f', 'f'], 'rationale': 'Trigger pattern is present, but validity is unresolved.'}
    assert HypothesisAssessment.model_validate_json(canonical_json(raw)).outcome == outcome
    raw['outcome'] = 'not_tested'
    with pytest.raises(ValidationError, match='not_tested'):
        HypothesisAssessment.model_validate_json(canonical_json(raw))


@pytest.mark.parametrize('value', ['1.0', '.0123', '1E3', '1e-300', '1.234567890123456789012345678901234567890'])
def test_finite_decimal_spelling_and_precision_are_preserved(value):
    parsed = TypeAdapter(ScientificDecimal).validate_json(json.dumps(value))
    assert parsed == value and Decimal(parsed) == Decimal(value)


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '-Infinity', 'not-a-number'])
def test_nonfinite_or_nonnumeric_parameters_are_still_rejected(value):
    with pytest.raises(ValidationError):
        TypeAdapter(ScientificDecimal).validate_json(json.dumps(value))


def test_parameter_audit_can_cite_its_subject_but_not_an_unbound_source():
    raw = {'checks': [{'check_key': 'missing', 'subject': 'requirements', 'status': 'fail',
                      'basis': 'The exact subject omits a needed condition.', 'evidence_keys': ['parameter_requirements']}],
           'evidence': [{'source_key': 'parameter_requirements', 'source_type': 'frozen_input', 'locator': '/parameters/0'}]}
    _audit_context(raw, {'parameter_requirements': b'{}'}, {'verdict': 'blocked'})
    with pytest.raises(SemanticRuleViolation, match='source bound to this task'):
        _audit_context(raw, {'different_input': b'{}'}, {'verdict': 'blocked'})


def test_deck_output_checks_consumed_parameters_without_requalifying_the_whole_set():
    project, sources, report = _review_context_fixture('none')
    coverage = json.loads(sources['parameter_coverage'])
    coverage.update(status='fail', blocking_count=1)
    coverage['items'].append({
        'parameter_key': 'unused_later_parameter', 'status': 'missing',
        'canonical_unit': 'V', 'independent_source_count': 0,
        'summary': 'Not consumed by this project.',
    })
    sources['parameter_coverage'] = canonical_json(coverage)
    _author_context(project.model_dump(mode='json'), sources, {'verdict': 'pass'})
    _review_context(report, sources, {'verdict': 'pass'})
    # A missing value actually consumed by the project still invalidates a pass.
    coverage['items'][0]['status'] = 'missing'
    coverage.update(confirmed_count=0, blocking_count=2)
    sources['parameter_coverage'] = canonical_json(coverage)
    with pytest.raises(SemanticRuleViolation, match='not usable by the deck'):
        _review_context(report, sources, {'verdict': 'pass'})


def test_curve_compiler_deduplicates_references_without_policing_case_roles():
    from curve_score.curve_contract_compiler import CurveContractCompileInput, compile_curve_contract
    from tests.operations.test_m2_curve_analysis_boundary import _compiler_plan, _compiler_objective, _bundle

    raw = _compiler_plan().model_dump(mode='json')
    proposal = raw['proposals'][0]
    proposal['required_observables'] = ['Independent description; target identity is selected by target_key.']
    proposal['cases'].append({**deepcopy(proposal['cases'][0]),
                              'case_key': 'extra_convergence', 'scientific_role': 'convergence'})
    proposal['resource_estimate']['case_count'] += 1
    plan = ExperimentPortfolio.model_validate_json(canonical_json(raw))
    request = CurveContractCompileInput.model_validate({
        'experiment_key': 'implementation_check',
        'target_bindings': [{'target_key': 'target_implementation', 'reference_series_key': 'reference',
                             'validation_check_keys': ['profile_rms', 'profile_rms']}],
        'candidate_case_keys': ['extra_convergence', 'extra_convergence'], 'comparison_metric': 'residual_rms',
    })
    contract = compile_curve_contract(request, objective=_compiler_objective(),
                                      portfolio=plan, reference_bundle=_bundle())
    assert len(contract.comparison_spec.comparisons) == 1
    operators = contract.comparison_spec.comparisons[0].operators
    assert len(operators) == 1 and operators[0].validation_check_key == 'profile_rms'


@pytest.mark.parametrize('mapped', [False, True])
def test_tcad_local_locator_survives_submission_and_wrong_alias_still_rejects(tmp_path, mapped):
    worker, opened = open_analysis(analysis_system(tmp_path))
    report = analysis_report(alias='solver_outputs_001', output_name='A', mapped=mapped)
    report['evidence'][0]['locator'] = 'lines-1-3'
    report['source_references'][0]['input_alias'] = 'unbound_alias'
    write_analysis(opened, report)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'rejected'
    report['source_references'][0]['input_alias'] = 'solver_outputs_001'
    write_analysis(opened, report)
    result = worker.call_tool('worker_submit_result', {})
    assert result['state'] == 'completed', result
