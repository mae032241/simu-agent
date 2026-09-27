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








def test_missing_foundation_objective_is_an_input_admission_error() -> None:
    import json
    from scidiscovery.general_science_components import _hypothesis_inputs
    from scidiscovery.operations.input_validation import OperationInvocationError

    foundation = json.loads(_foundation())
    foundation["objective_contract"] = None
    with pytest.raises(OperationInvocationError, match="input_objective_missing"):
        _hypothesis_inputs({"scientific_foundation": canonical_json(foundation)})


def test_hypothesis_can_reconsider_keys_within_bound_objective():
    _hypothesis_objective_context(_proposal(hypothesis_keys=("new_mechanism",)),
        {"scientific_foundation": _foundation(),
         "previous_hypotheses": canonical_json(_proposal(hypothesis_keys=("old_mechanism",)))}, {})
