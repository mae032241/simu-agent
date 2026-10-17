"""Present HWA contracts; proposed search allocation/policy is not implemented."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from scidiscovery.artifact_agent.schema.cognitive import HypothesisProposal
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.layered_diagnosis import LayeredDiagnosisReport
from scidiscovery.general_science_experiment_task import StageSubmission
from tests.operations.test_hypothesis_objective_boundary import _proposal


_NATIVE_PAYLOADS = json.loads((Path(__file__).resolve().parents[2]
    / 'scripts/acceptance/fixtures/search_mvp/native-payloads.json').read_text())


def _hypotheses():
    payload = _proposal(hypothesis_keys=('mechanism',))
    payload.pop('research_objective_key')
    return payload


def _analysis(action):
    return dict(summary='No valid observations; assess the bounded evaluation gap.',
        overall_verdict='inconclusive', claim_allowed=False,
        objective_assessment=dict(status='inconclusive', summary='The proxy does not establish the original goal.'),
        hypothesis_assessments=[dict(hypothesis_key='mechanism', outcome='not_tested',
            evidence_keys=['hypothesis_portfolio'], rationale='No valid observation was produced.')],
        progress_assessment=dict(outcome='unknown', reason='The goal-representativeness gap remains.'),
        limitations=['No observations and no independently representative target evaluation.'],
        remaining_contradiction='The mechanism and global contribution remain untested.',
        next_action=action)


@pytest.mark.parametrize('model,payload,proposed_field', [
    (HypothesisProposal, _NATIVE_PAYLOADS['hypothesis'], 'search_allocation'),
    (LayeredDiagnosisReport, _NATIVE_PAYLOADS['analysis'], 'search_assessment'),
    (StageSubmission, dict(stage='implementation', conclusion='Fixture-only implementation.'), 'candidate'),
], ids=['H-allocation-not-implemented', 'A-disposition-not-implemented', 'stage-candidate-not-implemented'])
def test_current_fields_accept_but_proposed_search_fields_are_forbidden(model, payload, proposed_field):
    # First prove the baseline payload is valid, so another invalid field cannot
    # accidentally satisfy the negative check. These future fields remain absent.
    retained = model.model_validate_json(canonical_json(payload), strict=True)
    assert proposed_field not in retained.model_dump(mode='json')
    with pytest.raises(ValidationError) as caught:
        model.model_validate_json(canonical_json({**payload, proposed_field: {}}), strict=True)
    assert [(item['loc'], item['type']) for item in caught.value.errors()] == [
        ((proposed_field,), 'extra_forbidden')]


    # This proves exact existing binding/startup, not scientific validity,
    # execution of a new evaluator, or automatic routing of free-text actions.
