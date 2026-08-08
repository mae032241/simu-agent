from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.research_cycle import (
    ProblemFrame,
    ScientificReadiness,
    ScientificReview,
    validate_problem_frame_against_foundation,
)
from scidiscovery.artifact_agent.schema.scientific_foundation import (
    ScientificFoundation,
)


def _foundation() -> ScientificFoundation:
    return ScientificFoundation.model_validate_json(
        canonical_json(
            {
                "title": "Fig.4 foundation",
                "objective": "Reproduce the measured zinc profile.",
                "summary": "The target curve and diffusion time are source-backed.",
                "evidence": [
                    {
                        "source_key": "paper",
                        "source_type": "frozen_input",
                        "title": "Frozen paper source",
                        "locator": "paper.pdf#fig4",
                    }
                ],
                "items": [
                    {
                        "item_key": "fig4_target",
                        "item_type": "target_data",
                        "epistemic_status": "paper_fact",
                        "statement": "Fig.4 reports the measured zinc profile.",
                        "scope": "Single-layer diffusion experiment.",
                        "evidence_keys": ["paper"],
                    },
                    {
                        "item_key": "diffusion_time",
                        "item_type": "parameter",
                        "epistemic_status": "paper_fact",
                        "statement": "The diffusion time is fixed.",
                        "value": 13,
                        "unit": "minute",
                        "scope": "Fig.4 experiment.",
                        "evidence_keys": ["paper"],
                    },
                ],
            }
        ),
        strict=True,
    )


def _frame() -> dict[str, object]:
    return {
        "title": "Fig.4 single-layer reproduction",
        "scientific_question": "Which diffusion model reproduces the full profile?",
        "objective": "Reproduce the Fig.4 zinc concentration curve.",
        "current_contradiction": "The baseline front is shallower than the target.",
        "scope": "The paper's single-layer diffusion experiment only.",
        "foundation_item_keys": ["fig4_target", "diffusion_time"],
        "observables": [
            {
                "observable_key": "zinc_profile",
                "description": "Zinc concentration versus depth.",
                "role": "target",
                "foundation_item_keys": ["fig4_target"],
                "acceptance_relevance": "The full curve is the reproduction target.",
            }
        ],
        "claim_boundary": {
            "allowed_claim": "The declared model reproduces the scoped Fig.4 curve.",
            "required_conditions": [
                "Source identity, numerical validity, and control equivalence pass."
            ],
            "excluded_claims": ["The model is already validated for a full device."],
        },
        "stop_conditions": ["The full-curve metric meets its pre-registered threshold."],
    }


def test_problem_frame_binds_only_declared_foundation_items() -> None:
    frame = ProblemFrame.model_validate_json(canonical_json(_frame()), strict=True)
    validate_problem_frame_against_foundation(frame, _foundation())
    assert frame.observables[0].observable_key == "zinc_profile"


def test_problem_frame_rejects_unknown_observable_basis() -> None:
    value = deepcopy(_frame())
    value["observables"][0]["foundation_item_keys"] = ["unknown"]
    with pytest.raises(ValidationError, match="undeclared foundation item"):
        ProblemFrame.model_validate_json(canonical_json(value), strict=True)


def test_cross_object_validation_rejects_unknown_foundation_item() -> None:
    value = deepcopy(_frame())
    value["foundation_item_keys"].append("not_in_foundation")
    frame = ProblemFrame.model_validate_json(canonical_json(value), strict=True)
    with pytest.raises(ValueError, match="unknown foundation item"):
        validate_problem_frame_against_foundation(frame, _foundation())


def test_passing_hypothesis_review_cannot_hide_failed_identifiability() -> None:
    value = {
        "review_target": "hypothesis_portfolio",
        "verdict": "pass",
        "summary": "The proposal is reviewable.",
        "hypothesis_reviews": [
            {
                "hypothesis_key": "diffusion_tail",
                "physical_plausibility": "pass",
                "falsifiability": "pass",
                "identifiability": "fail",
                "smallest_resolving_action": "Add a tail-sensitive observable.",
                "rationale": "The existing metric cannot separate two mechanisms.",
            }
        ],
    }
    with pytest.raises(ValidationError, match="passing review"):
        ScientificReview.model_validate_json(canonical_json(value), strict=True)


def test_readiness_is_an_inventory_not_a_fixed_workflow() -> None:
    state = ScientificReadiness(
        current_contradiction="The baseline provenance is unresolved.",
        available_artifacts=("problem_frame", "scientific_foundation"),
        unresolved_needs=("Audit the historical baseline realization.",),
        claim_evaluability="not_evaluable",
        execution_readiness="not_ready",
        suggested_capabilities=("evidence_auditor",),
        rationale="The next action depends on provenance, not a fixed stage index.",
    )
    assert "stage" not in state.model_dump(mode="json")


def test_completed_readiness_requires_execution_result() -> None:
    with pytest.raises(ValidationError, match="execution_result"):
        ScientificReadiness(
            current_contradiction="The physical mismatch remains.",
            available_artifacts=("problem_frame",),
            claim_evaluability="not_evaluable",
            execution_readiness="completed",
            rationale="An execution result was not registered.",
        )
