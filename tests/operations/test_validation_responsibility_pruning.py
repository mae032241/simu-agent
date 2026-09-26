"""Scientific choices remain reviewable; control still verifies recorded facts."""

import pytest

from scidiscovery.artifact_agent.schema.cognitive import CriticReview
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.experiment_intent import (
    ExperimentDesignIntent, materialize_experiment_design_intent,
)
from scidiscovery.artifact_agent.schema.research_objective import ResearchObjectiveContract
from scidiscovery.operation_contract import SemanticRuleViolation
from tests.operations.test_agent_contract_alignment import (
    experiment_case, _experiment_run, _experiment_envelope,
)
from tests.operations.test_hypothesis_review_routing import _critic


@pytest.mark.parametrize('kind', ['scientific', 'engineering'])
def test_designer_can_choose_stage_shape_through_submit(tmp_path, experiment_case, kind):
    intent, sources = experiment_case
    proposal = intent['proposals'][0]
    proposal.update(identifiability_claims=[], prediction_tests=[])
    objective = None
    if kind == 'scientific':
        proposal.update(baseline_case_key=None, cases=proposal['cases'][:1], variables=[])
        objective = ResearchObjectiveContract.model_validate_json(sources['research_objective'])
        intent['objective_key'] = objective.objective_key
    else:
        intent.update(study_kind='engineering', objective_key=None,
            engineering_objective='Compare two implementation configurations.', selected_hypothesis_keys=[])
        proposal.update(hypothesis_keys=[], objectives=[intent['engineering_objective']],
                        current_objectives=[intent['engineering_objective']])
    parsed = ExperimentDesignIntent.model_validate_json(canonical_json(intent))
    plan = materialize_experiment_design_intent(parsed, objective)
    assert len(plan.proposals[0].cases) == (1 if kind == 'scientific' else 2)
    runtime, run_id, output = _experiment_run(tmp_path, sources)
    output.write_bytes(_experiment_envelope(intent))
    assert runtime.runs.submit(run_id) == ('completed', ())


@pytest.mark.parametrize('disposition', ['ready_for_experiment', 'inconclusive', 'reject'])
def test_critic_owns_disposition_and_can_report_no_known_remedy(disposition):
    raw = _critic(disposition='inconclusive', physical='unknown').model_dump(mode='json')
    raw['disposition'] = disposition
    raw['reviews'][0]['smallest_resolving_action'] = None
    assert CriticReview.model_validate_json(canonical_json(raw)).disposition == disposition


def test_current_computation_without_control_receipt_is_still_rejected():
    from curve_score.analysis_tool import evaluate_analysis_request
    from scidiscovery.artifact_agent.service.tool_evidence import calculation_sources
    from tests.operations.test_result_analysis_tool import score_inputs
    sources, request = score_inputs()
    record = evaluate_analysis_request(record_key='forged_origin', request=request, sources=sources)
    with pytest.raises(SemanticRuleViolation, match='controlled receipt'):
        calculation_sources(record, sources)
