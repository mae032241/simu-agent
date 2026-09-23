from __future__ import annotations

import pytest
from pydantic import ValidationError

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.cognitive import EvidenceAudit, HypothesisProposal
from scidiscovery.artifact_agent.schema.research_cycle import ScientificReview
from scidiscovery.artifact_agent.schema.scientific_foundation import ScientificFoundation
from scidiscovery.artifact_agent.service.run_outputs import _validation_details
from scidiscovery.operation_contract import SemanticRuleViolation, validate_evidence_source_aliases, validation_diagnostics
from tests.operations.test_agent_contract_alignment import (
    experiment_case, _partial_experiment, _review_run,
)


def test_review_binds_direct_progress_reference_and_repairs_unknown_source_in_same_run(tmp_path, experiment_case):
    from scidiscovery.artifact_agent.transforms import materialize_experiment_plan
    intent, inputs = _partial_experiment(experiment_case)
    plan, _ = materialize_experiment_plan({
        'experiment_design_intent': canonical_json(intent),
        'research_objective': inputs['research_objective'],
        'hypothesis_portfolio': inputs['hypothesis_portfolio'],
    })
    runtime, run_id, workspace = _review_run(tmp_path, {
        'experiment_plan': plan, 'current_progress': canonical_json({'completed_units': 60}),
    })
    payload = {'review_target': 'experiment_portfolio', 'verdict': 'revise',
        'summary': 'Use the bound progress to assess the next experiment.',
        'findings': [{'finding_key': 'progress', 'statement': 'The previous work is available.',
            'epistemic_status': 'runtime_observation', 'evidence_keys': ['unknown_progress']}]}
    path = workspace.output_directory / 'result.json'
    def write():
        path.write_bytes(canonical_json({'schema_version': 1, 'payload': payload,
            'handoff': {'verdict': 'revise', 'summary': 'Review completed.'}}))
    write()
    state, details = runtime.runs.submit(run_id)
    assert state == 'rejected'
    assert details[0]['path'] == '$.payload.findings[0].evidence_keys[0]'
    assert 'bound to this task' in details[0]['message']
    assert runtime.runs.status(run_id).state == 'running'
    payload['findings'][0]['evidence_keys'] = ['current_progress', 'current_progress']
    write()
    assert runtime.runs.submit(run_id) == ('completed', ())
    assert runtime.runs.status(run_id).state == 'completed'


@pytest.mark.parametrize(('model', 'payload'), [
    (ScientificReview, {'review_target': 'experiment_portfolio', 'verdict': 'revise', 'summary': 'Probe',
        'findings': [{'finding_key': 'f', 'statement': 'Probe', 'epistemic_status': 'inference', 'evidence_keys': ['source']}]}),
    (EvidenceAudit, {'checks': [{'check_key': 'c', 'subject': 'Probe', 'status': 'unknown', 'basis': 'Probe', 'evidence_keys': ['source']}]}),
    (ScientificFoundation, {'title': 'Probe', 'objective': 'Probe', 'summary': 'Probe',
        'items': [{'item_key': 'i', 'item_type': 'fact', 'epistemic_status': 'paper_fact', 'statement': 'Probe', 'scope': 'Probe', 'evidence_keys': ['source']}]}),
    (HypothesisProposal, {'schema_version': 2, 'research_objective_key': 'objective', 'stage_objective': 'Probe', 'contradiction': 'Probe',
        'hypotheses': [{'hypothesis_key': 'h', 'statement': 'Probe', 'mechanism': 'Probe', 'scope': 'Probe', 'evidence_keys': ['source'],
            'predictions': [{'prediction_key': 'p', 'observable': 'Probe', 'expected_outcome': 'Probe'}],
            'falsifiers': [{'falsifier_key': 'f', 'observable': 'Probe', 'rejection_condition': 'Probe'}]}]}),
])
def test_scientific_forms_need_no_duplicate_source_ledger(model, payload):
    model.model_validate_json(canonical_json(payload), strict=True)
    validate_evidence_source_aliases(payload, {'source'})
    with pytest.raises(SemanticRuleViolation) as caught:
        validate_evidence_source_aliases(payload, {'different_source'})
    assert caught.value.details[0]['path'].endswith('.evidence_keys[0]')


def test_plain_model_relationship_diagnostic_retains_reason():
    from curve_score.schema import CurveInterval
    with pytest.raises(ValidationError) as caught:
        CurveInterval.model_validate_json('{"start":2,"stop":1}')
    details = validation_diagnostics(caught.value, schema=CurveInterval.model_json_schema())
    assert details[0]['message'] == 'curve interval stop must exceed start'
    assert details[0]['phase'] == 'tool_arguments'


def test_declared_context_rejection_retains_reason_without_details():
    details = _validation_details(SemanticRuleViolation('review target must match the bound object'), phase='output_context')
    assert details[0]['message'] == 'review target must match the bound object'
    assert details[0]['phase'] == 'output_context'


def test_analysis_reference_does_not_require_duplicated_citation_or_locator_prefix():
    from types import SimpleNamespace
    from curve_score.science_operations import _validate_analysis_evidence
    reference = SimpleNamespace(source_key='local_ref', input_alias='raw')
    report = SimpleNamespace(source_references=[reference, reference], evidence=[], calculation_records=[])
    _validate_analysis_evidence(report, {'raw': b'data'})
    report.evidence = [SimpleNamespace(source_key='local_ref', locator='/rows/2')]
    _validate_analysis_evidence(report, {'raw': b'data'})
    direct = SimpleNamespace(source_references=[], calculation_records=[],
        evidence=[SimpleNamespace(source_key='raw', locator='lines:2-3')])
    _validate_analysis_evidence(direct, {'raw': b'data'})
    with pytest.raises(SemanticRuleViolation):
        _validate_analysis_evidence(report, {'other': b'data'})
    report.source_references.append(SimpleNamespace(source_key='local_ref', input_alias='other'))
    with pytest.raises(SemanticRuleViolation, match='conflicting source mappings'):
        _validate_analysis_evidence(report, {'raw': b'data', 'other': b'data'})
    report.source_references = []
    report.evidence = [SimpleNamespace(source_key='local_ref', locator='raw:row1'),
                       SimpleNamespace(source_key='local_ref', locator='other:row2')]
    with pytest.raises(SemanticRuleViolation, match='conflicting source mappings'):
        _validate_analysis_evidence(report, {'raw': b'data', 'other': b'data'})
    report.evidence[1].locator = 'raw:row2'
    _validate_analysis_evidence(report, {'raw': b'data', 'other': b'data'})
    report.source_references = [reference]
    report.evidence[1].locator = 'other:row2'
    with pytest.raises(SemanticRuleViolation, match='conflicting source mappings'):
        _validate_analysis_evidence(report, {'raw': b'data', 'other': b'data'})


def test_generic_analysis_source_resolution_is_independent_of_optional_citation_rows():
    from types import SimpleNamespace as Item
    from curve_score.science_operations import _validate_analysis_evidence
    sources = {'raw': b'data', 'other': b'other'}
    report = Item(source_references=[Item(source_key='other', input_alias='raw')],
        calculation_records=[], evidence=[])
    for evidence in ([], [Item(source_key='other', locator='row1')]):
        report.evidence = evidence
        with pytest.raises(SemanticRuleViolation, match='conflicting source mappings') as caught:
            _validate_analysis_evidence(report, sources)
        assert caught.value.details[0]['path'] == '$.source_references[0].source_key'
    report.source_references = []
    report.calculation_records = [Item(record_key='score')]
    report.evidence = [Item(source_key='local', locator='raw:row1'),
        Item(source_key='local', locator='calculation_records:score')]
    with pytest.raises(SemanticRuleViolation, match='conflicting source mappings'):
        _validate_analysis_evidence(report, sources)
    report.evidence[1].source_key = 'score_evidence'
    _validate_analysis_evidence(report, sources)
    report.evidence = [Item(source_key='local', locator='row1'), Item(source_key='local', locator='raw:row2')]
    _validate_analysis_evidence(report, sources)


def test_parameter_sources_need_neither_unused_sources_nor_a_second_foundation_ledger():
    from types import SimpleNamespace
    from scidiscovery.operations.input_validation import ValidationSources
    from tcad_artifact.parameter_operations import ParameterEvidencePackage, validate_extract_context
    from tests.operations.test_m2_parameter_package import _package
    raw = _package('source_material_001').model_dump(mode='json')
    raw['scientific_intake']['scientific_foundation']['evidence'] = []
    ParameterEvidencePackage.model_validate_json(canonical_json(raw), strict=True)
    def bound_sources(values):
        return ValidationSources(values, {name: SimpleNamespace(port_name='source_material')
            for name in values})
    validate_extract_context(raw, bound_sources({'source_material_001': b'data', 'source_material_002': b'unused'}), {})
    with pytest.raises(SemanticRuleViolation) as caught:
        validate_extract_context(raw, bound_sources({'source_material_002': b'other'}), {})
    assert caught.value.details[0]['path'] == '$.source_catalog.sources[0].source_key'


def test_context_error_preserves_outer_reason_without_leaking_engineering_cause():
    error = SemanticRuleViolation('Reference must resolve within its bound source.')
    error.__cause__ = RuntimeError('internal storage path /private/state')
    details = _validation_details(error, phase='output_context')
    assert details[0]['message'] == str(error)
    assert 'private' not in str(details)


def test_runtime_owned_file_diagnostic_survives_sanitizing():
    from scidiscovery.artifact_agent.service.run_outputs import _with_rule
    from scidiscovery.operation_contract import sanitize_diagnostic_details
    details = _with_rule(({'path': '$.files', 'message': 'unexpected output file set', 'type': 'value_error'},),
        'runtime.files', frozenset({'runtime.files'}))
    saved = sanitize_diagnostic_details(details, schema={}, rules={'runtime.files'})
    assert saved[0]['path'] == '$.files'
    assert saved[0]['message'] == 'unexpected output file set'


def test_optional_metric_input_mismatch_is_an_admission_error_only():
    from curve_score.science_operations import _diagnosis_inputs, validate_analysis_report
    from scidiscovery.artifact_agent.schema.layered_diagnosis import LayeredDiagnosisReport
    from scidiscovery.operations.input_validation import OperationInvocationError
    from tests.operations.test_m2_curve_analysis_boundary import _inputs, _plan, _diagnosis
    from curve_score.schema import CurveConsistencyReport
    sources = _inputs()
    report = CurveConsistencyReport.model_validate_json(sources['metric_report'])
    report = report.model_copy(update={'validation_plan_sha256': '0' * 64})
    sources['metric_report'] = report.canonical_json()
    with pytest.raises(OperationInvocationError, match='input_metric_plan_mismatch'):
        _diagnosis_inputs(sources)
    # A pure output check cannot turn an unused input defect into output refusal.
    diagnosis = _diagnosis().model_copy(update={'objective_assessment': None})
    validate_analysis_report(diagnosis, _plan(), report)


@pytest.mark.parametrize('cite_subject', [False, True])
def test_general_qualification_accepts_direct_citations_through_complete_control_path(tmp_path, monkeypatch, cite_subject):
    from tests.operations import test_completed_science_compatibility as fixture
    complete = fixture._complete
    def without_ledger(runtime, root, name, operation_id, inputs, payload):
        if operation_id == 'science.evidence.extract.v1':
            payload['scientific_foundation']['evidence'] = []
        if operation_id == 'science.evidence.audit.intake.v1':
            payload.pop('evidence', None)
            if cite_subject:
                payload['checks'][0]['evidence_keys'].append('scientific_intake')
                payload['evidence'] = [{'source_key': 'scientific_intake', 'source_type': 'frozen_input',
                                        'locator': '/scientific_foundation'}]
        return complete(runtime, root, name, operation_id, inputs, payload)
    monkeypatch.setattr(fixture, '_complete', without_ledger)
    _, runtime, instance, _, _ = fixture._qualified_foundation(tmp_path)
    approval = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='approval', name='qualification')
    assert runtime.approvals.status(approval).status == 'decided'


def test_precomputed_analysis_can_cite_its_bound_plot_without_package_pointer():
    from types import SimpleNamespace
    from curve_score.science_operations import _validate_analysis_evidence
    report = SimpleNamespace(source_references=[], calculation_records=[],
        evidence=[SimpleNamespace(source_key='curve_analysis_plots_001', locator='left panel')])
    _validate_analysis_evidence(report, {'curve_analysis_package': b'{}', 'curve_analysis_plots_001': b'png'}, package={})
    with pytest.raises(SemanticRuleViolation, match='bound input'):
        _validate_analysis_evidence(report, {'curve_analysis_package': b'{}'}, package={})


@pytest.mark.parametrize('fault', ['missing_binding', 'missing_file', 'invalid_json'])
def test_author_frozen_input_defects_are_not_output_rejections(tmp_path, fault):
    from types import SimpleNamespace
    from tcad_artifact.operation_workspace import _input, _capability_snapshot
    from scidiscovery.artifact_agent.service.run_outputs import RunCheckerError
    with pytest.raises(RunCheckerError) as caught:
        if fault == 'invalid_json':
            _capability_snapshot(b'{')
        else:
            request = SimpleNamespace(input_paths={} if fault == 'missing_binding' else {'capability': tmp_path/'missing.json'})
            _input(request, 'capability')
    assert caught.value.category == ('admission_defect' if fault == 'invalid_json' else 'integrity_failure')
