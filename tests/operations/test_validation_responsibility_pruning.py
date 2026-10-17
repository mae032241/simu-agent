"""Scientific choices remain reviewable; control still verifies recorded facts."""

import pytest

from scidiscovery.artifact_agent.schema.cognitive import CriticReview
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.operation_contract import SemanticRuleViolation
from tests.operations.test_hypothesis_review_routing import _critic


@pytest.mark.parametrize('disposition', ['ready_for_experiment', 'inconclusive', 'reject'])
def test_critic_owns_disposition_and_can_report_no_known_remedy(disposition):
    raw = _critic(disposition='inconclusive', physical='unknown').model_dump(mode='json')
    raw['disposition'] = disposition
    raw['reviews'][0]['smallest_resolving_action'] = None
    assert CriticReview.model_validate_json(canonical_json(raw)).disposition == disposition


def test_current_computation_without_control_receipt_is_still_rejected():
    from curve_score.analysis_tool import evaluate_analysis_request
    from scidiscovery.operations.calculation_proof import calculation_sources
    from tests.operations.test_result_analysis_tool import score_inputs
    sources, request = score_inputs()
    record = evaluate_analysis_request(record_key='forged_origin', request=request, sources=sources)
    with pytest.raises(SemanticRuleViolation, match='registered calculation'):
        calculation_sources(record, sources)
