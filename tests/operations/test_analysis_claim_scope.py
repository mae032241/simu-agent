"""Finite analysis, actual check coverage, and operation-specific evidence rights."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from curve_score.schema import CurveBundle, CurveComparisonSpec, CurveConsistencyReport, evaluate_curve_consistency
from curve_score.analysis_tool import evaluate_analysis_request
from curve_score.science_operations import Components, Resources, _validate_diagnosis_against
from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json, canonical_sha256
from scidiscovery.artifact_agent.schema.experiment import ExperimentPortfolio
from scidiscovery.artifact_agent.schema.layered_diagnosis import LayeredDiagnosisReport, diagnosis_consistency_issues
from scidiscovery.operation_contract import SemanticRuleViolation
from tests.operations import test_m2_curve_analysis_boundary as curve
from tests.operations.test_result_analysis_tool import score_inputs
from tests.operations.test_tcad_result_analysis import analysis_system


def test_local_objective_and_observation_are_not_erased_by_missing_numerical_evidence():
    raw = curve._passing_diagnosis().model_dump(mode='json')
    raw['overall_verdict'] = 'inconclusive'
    raw['gates']['numerical_validity'] = dict(status='not_evaluable', summary='The requested curve is missing.')
    raw['objective_assessment'] = dict(objective_key='local_structure', status='pass',
        summary='The cited structural observation establishes this finite target.', evidence_keys=['metric_report'])
    report = LayeredDiagnosisReport.model_validate_json(canonical_json(raw))
    assert report.gates.observation.status == 'pass'
    assert report.objective_assessment.status == 'pass'
    assert report.overall_verdict == 'inconclusive' and not report.claim_allowed


def test_mechanical_diagnostics_preserve_scientific_verdict_and_check_references():
    raw = curve._passing_diagnosis().model_dump(mode='json')
    raw['gates']['numerical_validity'] = dict(status='not_evaluable', summary='No curve.')
    raw.update(overall_verdict='pass', claim_allowed=True)
    report = LayeredDiagnosisReport.model_validate_json(canonical_json(raw))
    before = canonical_json(report)
    assert diagnosis_consistency_issues(report) == ()
    assert canonical_json(report) == before
    raw['gates']['observation']['evidence_keys'] = ['unbound_evidence']
    from curve_score.science_operations import _validate_diagnosis_references
    report = LayeredDiagnosisReport.model_validate_json(canonical_json(raw))
    with pytest.raises(ValueError, match='source bound to this task'):
        _validate_diagnosis_references(report, {'metric_report': b'bound fixture'})


@pytest.mark.parametrize('physical', ['fail', 'pass', 'inconclusive'])
def test_finite_hypothesis_contradiction_does_not_determine_whole_physical_gate(physical):
    raw = curve._passing_diagnosis().model_dump(mode='json')
    raw.update(study_kind='scientific', overall_verdict='inconclusive')
    raw['gates']['physical_interpretation'] = dict(status=physical,
        summary='Assess the whole model separately from one falsified prediction.', evidence_keys=['metric_report'])
    raw['hypothesis_assessments'] = [dict(hypothesis_key='finite_prediction', outcome='contradicts',
        evidence_keys=['metric_report'], rationale='This finite prediction conflicts with the observation.')]
    assert LayeredDiagnosisReport.model_validate_json(canonical_json(raw)).hypothesis_assessments[0].outcome == 'contradicts'


def metric_fixture(status='pass', *, ambiguous=False):
    plan = curve._plan()
    if ambiguous:
        raw_plan = plan.model_dump(mode='json')
        extra = deepcopy(raw_plan['validation_plans'][0]['numerical']['checks'][0])
        extra['check_key'] = 'another_profile_rms'
        raw_plan['validation_plans'][0]['numerical']['checks'].append(extra)
        plan = ExperimentPortfolio.model_validate_json(canonical_json(raw_plan))
    bundle = curve._bundle().model_dump(mode='json')
    if status == 'pass':
        bundle['series'][1]['points'] = deepcopy(bundle['series'][0]['points'])
    spec = curve._contract().comparison_spec
    if status == 'unavailable':
        raw_spec = spec.model_dump(mode='json')
        raw_spec['comparisons'][0]['domain'].update(start=2.0, stop=3.0)
        spec = CurveComparisonSpec.model_validate_json(canonical_json(raw_spec))
    report = evaluate_curve_consistency(CurveBundle.model_validate_json(canonical_json(bundle)), spec,
        validation_plan_sha256=canonical_sha256(plan.validation_plans[0]),
        covered_validation_check_keys=tuple(item.check_key for item in plan.validation_plans[0].numerical.checks))
    return plan, spec, report


@pytest.mark.parametrize('status', ['pass', 'fail', 'unavailable'])
def test_standalone_metric_status_does_not_override_analyst_verdict(status):
    plan, _, metric = metric_fixture(status)
    report = curve._passing_diagnosis().model_dump(mode='json')
    report['source_references'] = [dict(source_key='metric_report', input_alias='metric_report')]
    sources = {'experiment_plan': plan.canonical_json(), 'metric_report': metric.canonical_json()}
    Components.diagnosis_context.implementation(report, sources, {})


def test_ambiguous_check_correspondence_remains_a_scientific_review_question():
    plan, _, metric = metric_fixture(ambiguous=True)
    report = curve._passing_diagnosis().model_dump(mode='json')
    report['source_references'] = [dict(source_key='metric_report', input_alias='metric_report')]
    Components.diagnosis_context.implementation(report,
        {'experiment_plan': plan.canonical_json(), 'metric_report': metric.canonical_json()}, {})


@pytest.mark.parametrize('tamper', ['metric', 'threshold', 'unit', 'observed'])
def test_source_metric_method_differences_remain_visible_for_scientific_review(tamper):
    plan, _, metric = metric_fixture()
    raw = metric.model_dump(mode='json')
    comparison = raw['comparisons'][0]
    if tamper == 'metric':
        comparison['metrics'][0]['kind'] = 'residual_max_abs'
    elif tamper == 'threshold':
        comparison['checks'][0]['threshold']['value'] = 100.0
    elif tamper == 'unit':
        comparison['metrics'][0]['unit'] = 'cm^-3'
    else:
        comparison['checks'][0]['observed_value'] = 0.1
    altered = CurveConsistencyReport.model_validate_json(canonical_json(raw))
    report = curve._passing_diagnosis().model_dump(mode='json')
    report['source_references'] = [dict(source_key='metric_report', input_alias='metric_report')]
    Components.diagnosis_context.implementation(report,
        {'experiment_plan': plan.canonical_json(), 'metric_report': altered.canonical_json()}, {})


@pytest.mark.parametrize('status', ['pass', 'unavailable'])
def test_local_objective_uses_its_cited_comparison_despite_global_inconclusive_observation(status):
    plan, _, metric = metric_fixture(status)
    plan = plan.model_copy(update={'objective_key': 'local_profile'})
    raw = curve._passing_diagnosis().model_dump(mode='json')
    raw['overall_verdict'] = 'inconclusive'
    raw['gates']['control_equivalence'] = dict(status='not_evaluable', summary='An independent control remains unavailable.')
    raw['gates']['observation'] = dict(status='inconclusive', summary='Overall observations remain incomplete.')
    raw['objective_assessment'] = dict(objective_key='local_profile', status='pass',
        comparison_keys=['implementation_residual'], summary='This finite profile comparison passed.', evidence_keys=['metric_report'])
    raw['source_references'] = [dict(source_key='metric_report', input_alias='metric_report')]
    sources = {'experiment_plan': plan.canonical_json(), 'metric_report': metric.canonical_json()}
    Components.diagnosis_context.implementation(raw, sources, {})


@pytest.mark.parametrize('status', ['fail', 'unavailable'])
def test_precomputed_status_does_not_override_scientific_verdict(status):
    plan, spec, metric = metric_fixture(status)
    assert plan.objective_key is None and metric.covered_validation_check_keys == ('profile_rms',)
    contract = curve._contract().model_copy(update={'comparison_spec': spec})
    raw = curve._passing_diagnosis().model_dump(mode='json')
    raw['evidence'][0]['locator'] = 'curve_analysis_package:/metric_report'
    _validate_diagnosis_against(LayeredDiagnosisReport.model_validate_json(canonical_json(raw)), plan, contract, metric)


def mcp_call(worker, name, arguments):
    return MCPRouter(worker, name='analysis-scope').handle({'jsonrpc': '2.0', 'id': 1,
        'method': 'tools/call', 'params': {'name': name, 'arguments': arguments}})


def submit(worker, opened, report):
    Path(opened['output_directory'], 'result.json').write_bytes(canonical_json(dict(schema_version=1,
        handoff=dict(verdict='blocked', summary='Bounded evidence; remaining scope is explicit.'), payload=report)))
    return mcp_call(worker, 'worker_submit_result', {})['result']['structuredContent']


def generic_worker(tmp_path, *, plan=None, return_system=False):
    system = analysis_system(tmp_path, plan=plan)
    catalog, runtime, root, _, artifacts, register = system
    bundle = curve._bundle().model_dump(mode='json')
    bundle['series'][1]['points'] = deepcopy(bundle['series'][0]['points'])
    register('generic_results', b'Execution finished with the bounded output.', 'opaque', parents=(artifacts['plan'].ref,))
    register('generic_bundle', canonical_json(bundle), 'scidiscovery.curve-bundle.v1', parents=(artifacts['plan'].ref,))
    review = root.call_tool('run_status', {'name': 'plan_review'})['output_artifact_name']
    root.call_tool('operation_invoke', dict(name='generic_analysis', operation_id='science.result.diagnose.v1',
        instruction='Analyze only the exact bound plan, execution evidence, and optional curve calculations.', inputs=[
        dict(port='experiment_plan', artifact_names=['plan']), dict(port='experiment_review', artifact_names=[review]),
        dict(port='experiment_results', artifact_names=['generic_results']), dict(port='curve_bundle', artifact_names=['generic_bundle'])]))
    compiled = catalog.operation('science.result.diagnose.v1')
    worker = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    opened = worker.call_tool('worker_open_assignment', {})
    return (worker, opened, system) if return_system else (worker, opened)
