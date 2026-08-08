from __future__ import annotations

import pytest
from pydantic import ValidationError

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.hypothesis import (
    HypothesisPortfolio,
    validate_hypothesis_portfolio,
)


def _portfolio() -> dict[str, object]:
    return {
        "objective": "Explain a reverse-bias dark-current residual.",
        "contradiction": "The baseline underestimates the full reverse-bias curve.",
        "foundation_summary": "The complete structure and measured curve are frozen inputs.",
        "foundation_item_keys": ["reverse_bias_residual", "zinc_profile"],
        "hypotheses": [
            {
                "hypothesis_key": "field_localization",
                "statement": "A localized high-field region drives the residual current.",
                "mechanism": "The complete lateral contact topology concentrates electric field near a junction edge.",
                "scope": "Sample1/2 complete five-layer geometry at 140 K.",
                "prerequisites": ["The complete lateral topology must be realized."],
                "parameters": [
                    {
                        "name": "mesh_edge_spacing",
                        "role": "fixed",
                        "unit": "um",
                        "basis": "Numerical resolution must be independently converged.",
                    }
                ],
                "predictions": [
                    {
                        "prediction_key": "edge_field_peak",
                        "observable": "Spatial electric-field maximum",
                        "expected_outcome": "The complete topology creates a localized peak absent from the uniform control.",
                        "distinguishes_from": ["bulk_lifetime"],
                        "rationale": "Geometry localization is the mechanism-specific prediction.",
                    }
                ],
                "falsifiers": [
                    {
                        "falsifier_key": "no_local_peak",
                        "observable": "Spatial electric-field map",
                        "rejection_condition": "The converged complete and uniform structures have equivalent field distributions.",
                        "rationale": "Without field localization, the proposed mechanism has no driver.",
                    }
                ],
                "competing_hypothesis_keys": ["bulk_lifetime"],
                "evidence_impacts": [
                    {
                        "item_key": "reverse_bias_residual",
                        "direction": "supports",
                        "strength": "weak",
                        "rationale": "The residual is compatible with but does not identify localization.",
                    }
                ],
                "status": "testable",
                "support_level": "low",
                "support_rationale": "The required complete field map is not yet available.",
            },
            {
                "hypothesis_key": "bulk_lifetime",
                "statement": "A bulk SRH lifetime mismatch drives the residual current.",
                "mechanism": "Bulk generation scales with a shared carrier lifetime.",
                "scope": "Shared sample1/2 material regions at 140 K.",
                "parameters": [
                    {
                        "name": "tau_bulk",
                        "role": "calibratable",
                        "unit": "s",
                        "range_description": "1e-10 to 1e-6 s",
                        "basis": "Bounded diagnostic range pending material evidence.",
                    }
                ],
                "predictions": [
                    {
                        "prediction_key": "volume_scaling",
                        "observable": "Spatial SRH generation integral",
                        "expected_outcome": "Generation remains distributed through the depleted bulk.",
                        "distinguishes_from": ["field_localization"],
                        "rationale": "A bulk mechanism should not collapse to the junction edge.",
                    }
                ],
                "falsifiers": [
                    {
                        "falsifier_key": "edge_only_generation",
                        "observable": "Spatial SRH generation map",
                        "rejection_condition": "Generation is localized at the edge and insensitive to bulk volume.",
                        "rationale": "Edge-only generation contradicts the proposed bulk mechanism.",
                    }
                ],
                "competing_hypothesis_keys": ["field_localization"],
                "evidence_impacts": [
                    {
                        "item_key": "zinc_profile",
                        "direction": "neutral",
                        "strength": "weak",
                        "rationale": "The profile constrains geometry but does not determine lifetime.",
                    }
                ],
                "status": "proposed",
                "support_level": "unassessed",
                "support_rationale": "No spatial generation attribution exists yet.",
            },
        ],
        "ranking": ["field_localization", "bulk_lifetime"],
        "ranking_rationale": "Field localization is tested first because the complete structure is a prerequisite and adds no fitted lifetime.",
        "missing_inputs": ["Converged complete-structure field and generation maps."],
    }


def _validate(value: dict[str, object]) -> HypothesisPortfolio:
    return HypothesisPortfolio.model_validate_json(canonical_json(value), strict=True)


def test_portfolio_requires_competitors_predictions_and_falsifiers() -> None:
    portfolio = _validate(_portfolio())
    assert portfolio.ranking[0] == "field_localization"
    assert portfolio.hypotheses[0].predictions[0].distinguishes_from == (
        "bulk_lifetime",
    )
    assert validate_hypothesis_portfolio(_portfolio())["schema_version"] == 1


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda value: value["hypotheses"][1]["parameters"][0].pop("range_description"),
            "calibratable parameter requires range_description",
        ),
        (
            lambda value: value.update(ranking=["field_localization"]),
            "ranking must contain every hypothesis exactly once",
        ),
        (
            lambda value: value["hypotheses"][0].update(
                competing_hypothesis_keys=["unknown"]
            ),
            "undeclared competitor",
        ),
        (
            lambda value: value["hypotheses"][0].update(
                status="supported", evidence_impacts=[]
            ),
            "evidence-changing status requires evidence_impacts",
        ),
    ],
)
def test_portfolio_rejects_unbounded_or_unfalsifiable_state(mutation, message) -> None:
    value = _portfolio()
    mutation(value)
    with pytest.raises(ValidationError, match=message):
        _validate(value)
