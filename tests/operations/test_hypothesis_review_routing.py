from __future__ import annotations


from scidiscovery.artifact_agent.schema.cognitive import (
    CriticReview,
    HypothesisReviewForm,
)
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.general_science_components import _critic_portfolio_context


def _critic(
    *,
    disposition: str = "revise_hypothesis",
    physical: str = "fail",
    falsifiability: str = "pass",
    discriminability: str = "pass",
    issue: str = "The mechanism statement is incomplete.",
) -> CriticReview:
    return CriticReview(
        disposition=disposition,
        reviews=(
            HypothesisReviewForm(
                hypothesis_key="hypothesis_a",
                physical_plausibility=physical,
                falsifiability=falsifiability,
                finite_discriminability=discriminability,
                issues=(issue,),
                smallest_resolving_action="Make one bounded correction.",
            ),
        ),
    )


def test_critic_routes_current_uncertainty_to_experiment_design() -> None:
    portfolio = canonical_json(
        {
            "schema_version": 2,
            "research_objective_key": "objective_a",
            "stage_objective": "Separate two bounded mechanisms.",
            "contradiction": "The current evidence does not distinguish them.",
            "evidence": [],
            "hypotheses": [
                {
                    "hypothesis_key": "hypothesis_a",
                    "statement": "A bounded mechanism changes the observable.",
                    "mechanism": "The mechanism has one finite intervention.",
                    "scope": "Only the supplied system.",
                    "parameters": [],
                    "predictions": [
                        {
                            "prediction_key": "prediction_a",
                            "observable": "A bounded response",
                            "expected_outcome": "The response changes direction.",
                        }
                    ],
                    "falsifiers": [
                        {
                            "falsifier_key": "falsifier_a",
                            "observable": "The same bounded response",
                            "rejection_condition": "No directional change occurs.",
                        }
                    ],
                    "competing_hypothesis_keys": [],
                    "evidence_keys": [],
                }
            ],
        }
    )
    review = _critic(
        disposition="ready_for_experiment",
        physical="pass",
        falsifiability="pass",
        discriminability="pass",
    )
    _critic_portfolio_context(
        review.model_dump(mode="json"),
        {"hypothesis_portfolio": portfolio},
        {"verdict": "pass"},
    )


# The real Root preflight/invoke source-continuity path is covered in
# test_user_context_contract, with completed producers and an actual fixture approval.
