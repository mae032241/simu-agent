"""Small serialized science fixtures shared by source tests."""
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.experiment_intent import ExperimentDesignIntent


def _review() -> bytes:
    return canonical_json(
        {
            "review_target": "domain_contract",
            "verdict": "pass",
            "summary": "The frozen deterministic fixture is internally consistent.",
        }
    )


def _engineering_intent() -> bytes:
    return ExperimentDesignIntent.model_validate_json(
        canonical_json(
            {
                "study_kind": "engineering",
                "engineering_objective": "Verify one bounded analysis.",
                "proposals": [
                    {
                        "experiment_key": "engineering_smoke",
                        "objectives": ["Verify one bounded analysis."],
                        "current_objectives": ["Verify one bounded analysis."],
                        "frozen_invariants": ["same fixture"],
                        "cases": [
                            {
                                "case_key": "baseline",
                                "scientific_role": "baseline",
                                "purpose": "Run one fixed case.",
                            }
                        ],
                        "required_observables": ["terminal state"],
                        "validation_intent": {
                            "numerical": {
                                "rationale": "Check completion.",
                                "reviewed_checks": [
                                    {
                                        "observable": "terminal state",
                                        "metric": "clean completion",
                                        "acceptance_condition": "The run completes.",
                                        "failure_action": "Reject the implementation.",
                                        "basis": "Engineering smoke contract.",
                                    }
                                ],
                            },
                            "physical": {"rationale": "No physical claim."},
                            "experimental": {"rationale": "No wet experiment."},
                        },
                        "resource_estimate": {
                            "relative_cost": "low",
                            "runtime_basis": "One bounded case.",
                        },
                        "stop_conditions": ["Stop after completion."],
                        "value_assessment": {
                            "evidence_support": "high",
                            "discrimination_power": "low",
                            "information_gain": "medium",
                            "cost": "low",
                            "added_free_parameters": 0,
                            "rationale": "Close one implementation invariant.",
                        },
                    }
                ],
                "priority_order": ["engineering_smoke"],
                "priority_rationale": "Only one case exists.",
            }
        ),
        strict=True,
    ).canonical_json()
