"""Mechanical scientific source identities in the generic analysis contract."""
import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.general_science_result_analysis import validate_context
from scidiscovery.operation_contract import SemanticRuleViolation
from scidiscovery.operations.input_validation import ValidationSources
from tests.operations.test_hypothesis_objective_boundary import _proposal


def sources(*, original_text=False):
    proposal = _proposal(hypothesis_keys=('mechanism',))
    if original_text:
        proposal.pop('research_objective_key')
    return ValidationSources({'hypothesis_portfolio': canonical_json(proposal),
        'experiment_results': b'{"summary":"Observed result"}',
        'scientific_materials': b'Other exact reference.'}, {})


def payload(**fields):
    return {'summary': 'Bounded interpretation.', 'overall_verdict': 'inconclusive',
        'claim_allowed': False, **fields}


def evidence(key, locator):
    return {'source_key': key, 'source_type': 'frozen_input',
        'title': 'Exact observation.', 'locator': locator}


@pytest.mark.parametrize('fields', [
    {'source_references': [{'source_key': 'experiment_results', 'input_alias': 'scientific_materials'}]},
    {'source_references': [{'source_key': 'observed', 'input_alias': 'experiment_results'}],
        'evidence': [evidence('observed', 'scientific_materials:table')]},
    {'source_references': [{'source_key': 'observed', 'input_alias': 'missing'}]},
    {'evidence': [evidence('fabricated', '/x')]},
])
def test_analysis_rejects_conflicting_or_unbound_sources(fields):
    with pytest.raises(SemanticRuleViolation):
        validate_context(payload(**fields), sources(), {})


def test_analysis_accepts_local_source_names_and_repeated_citations():
    reference = {'source_key': 'observed', 'input_alias': 'experiment_results'}
    validate_context(payload(source_references=[reference, reference],
        evidence=[evidence('observed', 'experiment_results:table')]*2), sources(), {})


@pytest.mark.parametrize('fields', [
    {'experiment_key': 'invented'}, {'plan_key': 'invented'},
    {'source_references': [{'source_key': 'observed', 'input_alias': 'experiment_results',
        'experiment_key': 'invented', 'case_key': 'invented'}]},
])
def test_generic_analysis_cannot_invent_plan_or_case_identities(fields):
    with pytest.raises(SemanticRuleViolation, match='no bound experiment plan'):
        validate_context(payload(**fields), sources(), {})


def test_original_text_analysis_cannot_invent_an_objective_key():
    with pytest.raises(SemanticRuleViolation, match='exact hypothesis objective'):
        validate_context(payload(objective_assessment={'objective_key': 'invented',
            'status': 'inconclusive', 'summary': 'No structured objective.'}), sources(original_text=True), {})


def test_analysis_cannot_assess_a_different_hypothesis():
    with pytest.raises(SemanticRuleViolation, match='exact experiment'):
        validate_context(payload(hypothesis_assessments=[{'hypothesis_key': 'other',
            'outcome': 'not_tested', 'evidence_keys': ['experiment_results'],
            'rationale': 'No test.'}]), sources(), {})


def test_optional_worker_progress_reuses_bound_evidence():
    validate_context(payload(progress_assessment=dict(outcome='no_progress', reason='The decision did not change.',
        evidence_keys=['experiment_results'])), sources(), {})
    with pytest.raises(SemanticRuleViolation):
        validate_context(payload(progress_assessment=dict(outcome='advance', reason='Unbound claim.',
            evidence_keys=['fabricated'])), sources(), {})


def test_progress_increment_is_separate_from_hypothesis_direction_but_checks_are_bound():
    assessed = dict(hypothesis_key='mechanism', outcome='contradicts', evidence_keys=['experiment_results'],
        rationale='A bounded negative observation.')
    validate_context(payload(hypothesis_assessments=[assessed], progress_assessment=dict(
        outcome='no_progress', reason='The same refutation was already known.', evidence_keys=['experiment_results'])), sources(), {})
    with pytest.raises(SemanticRuleViolation, match='exact hypothesis'):
        validate_context(payload(hypothesis_assessments=[dict(assessed, predictions_checked=['invented'])]), sources(), {})
