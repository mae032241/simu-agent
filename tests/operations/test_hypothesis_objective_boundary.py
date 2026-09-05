from __future__ import annotations

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.general_science_components import _hypothesis_objective_context


def _foundation(objective_key: str = "global_objective") -> bytes:
    return canonical_json(
        {
            "title": "Bounded foundation",
            "objective": "Reproduce one immutable target.",
            "summary": "One source-backed target is available.",
            "objective_contract": {
                "objective_key": objective_key,
                "intent": "external_reproduction",
                "statement": "Reproduce one immutable target.",
                "mandatory_targets": [
                    {
                        "target_key": "target",
                        "observable": "profile",
                        "support_requirement": "complete_observation",
                        "evidence_item_keys": ["target_item"],
                        "rationale": "The profile is the frozen target.",
                    }
                ],
                "closure_requirements": [
                    {
                        "requirement_key": "cover_target",
                        "description": "The target profile must be covered.",
                        "target_keys": ["target"],
                    }
                ],
            },
            "items": [
                {
                    "item_key": "target_item",
                    "item_type": "target_data",
                    "epistemic_status": "paper_fact",
                    "statement": "The supplied profile is the target.",
                    "scope": "Fixture only.",
                    "evidence_keys": ["source"],
                }
            ],
            "evidence": [
                {
                    "source_key": "source",
                    "source_type": "frozen_input",
                    "title": "Fixture",
                    "locator": "fixture.json",
                }
            ],
        }
    )


def _hypothesis(key: str) -> dict[str, object]:
    return {
        "hypothesis_key": key,
        "statement": "One bounded mechanism changes the target observable.",
        "mechanism": "The mechanism has one finite intervention.",
        "scope": "Fixture only.",
        "predictions": [
            {
                "prediction_key": f"{key}_prediction",
                "observable": "profile",
                "expected_outcome": "The profile changes direction.",
            }
        ],
        "falsifiers": [
            {
                "falsifier_key": f"{key}_falsifier",
                "observable": "profile",
                "rejection_condition": "No directional change occurs.",
            }
        ],
    }


def _proposal(
    objective_key: str = "global_objective",
    hypothesis_keys: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "schema_version": 2,
        "research_objective_key": objective_key,
        "stage_objective": "Discriminate two bounded mechanisms.",
        "contradiction": "The baseline differs from the target.",
        "hypotheses": [_hypothesis(key) for key in hypothesis_keys],
    }


def test_stage_objective_need_not_copy_global_objective_text() -> None:
    _hypothesis_objective_context(
        _proposal(), {"scientific_foundation": _foundation()}, {}
    )


def test_hypothesis_must_reference_the_exact_global_objective() -> None:
    with pytest.raises(ValueError, match="research_objective_key differs"):
        _hypothesis_objective_context(
            _proposal("other_objective"),
            {"scientific_foundation": _foundation()},
            {},
        )


def test_revision_cannot_move_a_portfolio_between_global_objectives() -> None:
    prior = canonical_json(_proposal("prior_objective"))
    with pytest.raises(ValueError, match="revision cannot change"):
        _hypothesis_objective_context(
            _proposal(),
            {
                "scientific_foundation": _foundation(),
                "prior_draft": prior,
            },
            {},
        )


def test_revision_cannot_add_remove_or_rename_hypotheses() -> None:
    prior = canonical_json(_proposal(hypothesis_keys=("mechanism_a",)))
    with pytest.raises(ValueError, match="cannot add, remove, or rename"):
        _hypothesis_objective_context(
            _proposal(hypothesis_keys=("mechanism_a_renamed",)),
            {
                "scientific_foundation": _foundation(),
                "prior_draft": prior,
            },
            {},
        )


def test_revision_may_reorder_the_same_stable_hypothesis_keys() -> None:
    prior = canonical_json(
        _proposal(hypothesis_keys=("mechanism_a", "mechanism_b"))
    )
    _hypothesis_objective_context(
        _proposal(hypothesis_keys=("mechanism_b", "mechanism_a")),
        {
            "scientific_foundation": _foundation(),
            "prior_draft": prior,
        },
        {},
    )
