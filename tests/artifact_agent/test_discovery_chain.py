from __future__ import annotations

from copy import deepcopy

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.discovery import validate_discovery_chain
from scidiscovery.artifact_agent.schema.experiment import ExperimentPortfolio
from scidiscovery.artifact_agent.schema.knowledge import KnowledgeUpdate
from scidiscovery.artifact_agent.schema.scientific_foundation import ScientificFoundation
from tests.artifact_agent.test_knowledge_update import _portfolio, _report, _update


def _foundation() -> ScientificFoundation:
    return ScientificFoundation.model_validate_json(
        canonical_json(
            {
                "title": "Frozen field-localization basis",
                "objective": "Explain the measured response difference.",
                "summary": "The target and device structure are frozen inputs.",
                "evidence": [
                    {
                        "source_key": "paper",
                        "source_type": "frozen_input",
                        "title": "Paper and digitized target",
                        "locator": "figure and device section",
                    }
                ],
                "items": [
                    {
                        "item_key": "target_curve",
                        "item_type": "target_data",
                        "epistemic_status": "paper_fact",
                        "statement": "The measured target curve is frozen.",
                        "scope": "The reported sample and temperature.",
                        "evidence_keys": ["paper"],
                    },
                    {
                        "item_key": "device_structure",
                        "item_type": "structure",
                        "epistemic_status": "paper_fact",
                        "statement": "The tested device structure is frozen.",
                        "scope": "The complete paper device.",
                        "evidence_keys": ["paper"],
                    },
                ],
            }
        ),
        strict=True,
    )


def _dimension(key: str, observable: str) -> dict[str, object]:
    return {
        "applicability": "required",
        "rationale": "This dimension is required for the scientific claim.",
        "checks": [
            {
                "check_key": key,
                "observable": observable,
                "metric": f"Reviewed {observable}",
                "evaluation_mode": "reviewed_qualitative",
                "acceptance_condition": "The pre-registered prediction is observed.",
                "failure_action": "Apply the pre-registered falsifier when numerics pass.",
                "basis": "Frozen experiment plan.",
            }
        ],
    }


def _experiments() -> ExperimentPortfolio:
    return ExperimentPortfolio.model_validate_json(
        canonical_json(
            {
                "objective": "Test the field-localization hypothesis.",
                "selected_hypothesis_keys": ["field_localization"],
                "proposals": [
                    {
                        "experiment_key": "field_study",
                        "objective": "Compare complete and uniform field topology.",
                        "hypothesis_keys": ["field_localization"],
                        "changed_factors": [
                            {
                                "name": "lateral_topology",
                                "factor_type": "physical",
                                "values": ["uniform", "complete"],
                                "unit": "categorical",
                                "rationale": "This isolates the proposed mechanism.",
                            }
                        ],
                        "frozen_invariants": ["Vertical structure and material parameters."],
                        "cases": [
                            {
                                "case_key": "uniform_control",
                                "scientific_role": "control",
                                "settings": [
                                    {
                                        "name": "lateral_topology",
                                        "value": "uniform",
                                        "unit": "categorical",
                                    }
                                ],
                                "purpose": "Establish the control field.",
                            },
                            {
                                "case_key": "complete_device",
                                "scientific_role": "perturbation",
                                "settings": [
                                    {
                                        "name": "lateral_topology",
                                        "value": "complete",
                                        "unit": "categorical",
                                    }
                                ],
                                "purpose": "Test the complete topology.",
                            },
                        ],
                        "required_observables": ["Electric-field map"],
                        "comparison_contract": {
                            "baseline_case_key": "uniform_control",
                            "comparison_case_keys": ["complete_device"],
                            "variables": [
                                {
                                    "variable_key": "lateral_topology",
                                    "scientific_path": "device.topology",
                                    "factor_type": "physical",
                                    "comparison_role": "intended_change",
                                    "unit": "categorical",
                                    "expectations": [
                                        {"case_key": "uniform_control", "value": "uniform"},
                                        {"case_key": "complete_device", "value": "complete"},
                                    ],
                                    "equivalence_rule": "exact",
                                    "rationale": "Topology is the selected factor.",
                                }
                            ],
                            "required_observables": ["Electric-field map"],
                            "identifiability_claims": [
                                {
                                    "hypothesis_key": "field_localization",
                                    "observable": "Electric-field map",
                                    "distinguishing_outcome": "The complete case has an edge peak.",
                                    "decision_rule": "Compare the converged field maps.",
                                    "ambiguity_conditions": ["A numerical difference creates the peak."],
                                    "smallest_resolving_control": "Freeze numerical settings.",
                                }
                            ],
                        },
                        "prediction_tests": [
                            {
                                "hypothesis_key": "field_localization",
                                "prediction_key": "edge_field_peak",
                                "observable": "Electric-field map",
                                "expected_result": "A resolved edge peak appears.",
                                "falsifying_result": "No peak appears after convergence.",
                            }
                        ],
                        "resource_estimate": {
                            "case_count": 2,
                            "relative_cost": "low",
                            "runtime_basis": "Two bounded field solves.",
                        },
                        "stop_conditions": ["Stop if the structure is not realized."],
                        "value_assessment": {
                            "evidence_support": "medium",
                            "discrimination_power": "high",
                            "information_gain": "high",
                            "cost": "low",
                            "added_free_parameters": 0,
                            "rationale": "The test isolates topology without fitting.",
                        },
                    }
                ],
                "validation_plans": [
                    {
                        "plan_key": "validate_field_study",
                        "experiment_key": "field_study",
                        "numerical": _dimension("numerical_check", "Convergence"),
                        "physical": _dimension("physical_check", "Field localization"),
                        "experimental": _dimension("experimental_check", "Target curve"),
                    }
                ],
                "priority_order": ["field_study"],
                "priority_rationale": "This is the smallest discriminating study.",
            }
        ),
        strict=True,
    )


def test_complete_scientific_object_chain_projects_one_result() -> None:
    update = KnowledgeUpdate.model_validate_json(canonical_json(_update()), strict=True)
    projection = validate_discovery_chain(
        _foundation(), _portfolio(), _experiments(), [_report()], [update]
    )
    assert projection.hypotheses[0].status == "weakened"
    assert projection.next_task_mode == "new_mechanism"


def test_chain_rejects_unknown_foundation_reference() -> None:
    portfolio_value = _portfolio().model_dump(mode="json")
    portfolio_value["foundation_item_keys"] = ["missing_item"]
    portfolio = _portfolio().model_validate_json(
        canonical_json(portfolio_value), strict=True
    )
    with pytest.raises(ValueError, match="unknown foundation item"):
        validate_discovery_chain(
            _foundation(), portfolio, _experiments(), [_report()], []
        )


def test_chain_rejects_prediction_reference_drift() -> None:
    experiment_value = deepcopy(_experiments().model_dump(mode="json"))
    experiment_value["proposals"][0]["prediction_tests"][0][
        "prediction_key"
    ] = "invented_prediction"
    experiments = ExperimentPortfolio.model_validate_json(
        canonical_json(experiment_value), strict=True
    )
    with pytest.raises(ValueError, match="unknown hypothesis prediction"):
        validate_discovery_chain(
            _foundation(), _portfolio(), experiments, [_report()], []
        )
