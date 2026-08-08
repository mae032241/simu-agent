from __future__ import annotations

import json
from pathlib import Path

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.comparison import (
    RealizationSnapshot,
    evaluate_control_equivalence,
)
from scidiscovery.artifact_agent.schema.discovery import (
    validate_layered_discovery_chain,
    validate_experiments_against_hypotheses,
    validate_hypotheses_against_foundation,
    validate_review_against_hypotheses,
)
from scidiscovery.artifact_agent.schema.experiment import ExperimentPortfolio
from scidiscovery.artifact_agent.schema.hypothesis import HypothesisPortfolio
from scidiscovery.artifact_agent.schema.knowledge import (
    derive_knowledge_update,
)
from scidiscovery.artifact_agent.schema.layered_diagnosis import (
    LayeredDiagnosisReport,
)
from scidiscovery.artifact_agent.schema.research_cycle import (
    ProblemFrame,
    ScientificReview,
    validate_problem_frame_against_foundation,
)
from scidiscovery.artifact_agent.schema.scientific_foundation import (
    ScientificFoundation,
)


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "scientific_cycles"
    / "fig4_clean"
)


def _foundation() -> ScientificFoundation:
    return ScientificFoundation.model_validate_json(
        canonical_json(
            {
                "title": "Synthetic Fig.4 architecture fixture",
                "objective": "Test whether one declared mechanism changes the profile.",
                "summary": "Values are synthetic and carry no scientific claim.",
                "items": [
                    {
                        "item_key": "synthetic_target",
                        "item_type": "target_data",
                        "epistemic_status": "assumption",
                        "statement": "A synthetic target profile exists.",
                        "scope": "Architecture tests only.",
                        "rationale": "No historical Fig.4 data is admitted to the clean fixture.",
                    }
                ],
            }
        ),
        strict=True,
    )


def _frame() -> ProblemFrame:
    return ProblemFrame.model_validate_json(
        canonical_json(
            {
                "title": "Synthetic Fig.4 comparison",
                "scientific_question": "Is the mechanism effect distinguishable from mesh effects?",
                "objective": "Test whether one declared mechanism changes the profile.",
                "current_contradiction": "The candidate changes both model and mesh.",
                "scope": "Architecture tests only.",
                "foundation_item_keys": ["synthetic_target"],
                "observables": [
                    {
                        "observable_key": "profile",
                        "description": "Synthetic concentration versus depth.",
                        "role": "target",
                        "foundation_item_keys": ["synthetic_target"],
                        "acceptance_relevance": "It exercises comparison routing.",
                    }
                ],
                "claim_boundary": {
                    "allowed_claim": "Only the architecture gate behavior is tested.",
                    "required_conditions": ["No historical resource is loaded."],
                    "excluded_claims": ["Any claim about the paper's physical model."],
                },
                "stop_conditions": ["The invalid control is detected."],
            }
        ),
        strict=True,
    )


def _hypotheses() -> HypothesisPortfolio:
    return HypothesisPortfolio.model_validate_json(
        canonical_json(
            {
                "objective": "Test whether one declared mechanism changes the profile.",
                "contradiction": "The candidate changes both model and mesh.",
                "foundation_summary": "Only a synthetic target is available.",
                "foundation_item_keys": ["synthetic_target"],
                "hypotheses": [
                    {
                        "hypothesis_key": "tail_channel",
                        "statement": "A second channel changes the synthetic tail.",
                        "mechanism": "The channel contributes at low concentration.",
                        "scope": "Architecture fixture only.",
                        "predictions": [
                            {
                                "prediction_key": "tail_changes",
                                "observable": "profile",
                                "expected_outcome": "The tail changes while the front is fixed.",
                                "rationale": "This is the synthetic mechanism signature.",
                            }
                        ],
                        "falsifiers": [
                            {
                                "falsifier_key": "tail_unchanged",
                                "observable": "profile",
                                "rejection_condition": "A valid control shows no tail change.",
                                "rationale": "The mechanism must alter its signature.",
                            }
                        ],
                        "status": "under_test",
                        "support_level": "low",
                        "support_rationale": "No valid study has been completed.",
                    }
                ],
                "ranking": ["tail_channel"],
                "ranking_rationale": "It is the only synthetic hypothesis.",
            }
        ),
        strict=True,
    )


def _review() -> ScientificReview:
    return ScientificReview.model_validate_json(
        canonical_json(
            {
                "review_target": "hypothesis_portfolio",
                "verdict": "pass",
                "summary": "The synthetic hypothesis is testable if mesh is frozen.",
                "hypothesis_reviews": [
                    {
                        "hypothesis_key": "tail_channel",
                        "physical_plausibility": "pass",
                        "falsifiability": "pass",
                        "identifiability": "pass",
                        "confounders": ["A mesh change can alter the apparent tail."],
                        "smallest_resolving_action": "Freeze mesh or run a mesh-only control.",
                        "rationale": "The planned observable separates the effect only under equivalent numerics.",
                    }
                ],
                "evidence_item_keys": ["synthetic_target"],
            }
        ),
        strict=True,
    )


def _experiments() -> ExperimentPortfolio:
    dimension = lambda key: {
        "applicability": "required",
        "rationale": "The synthetic claim requires this check.",
        "checks": [
            {
                "check_key": key,
                "observable": "profile",
                "metric": key,
                "evaluation_mode": "reviewed_qualitative",
                "acceptance_condition": "The declared gate passes.",
                "failure_action": "Stop physical interpretation.",
                "basis": "Synthetic pre-registration.",
            }
        ],
    }
    proposal = {
        "experiment_key": "synthetic_model_ab",
        "objective": "Isolate the synthetic tail channel.",
        "hypothesis_keys": ["tail_channel"],
        "changed_factors": [
            {
                "name": "diffusion_model",
                "factor_type": "physical",
                "values": ["model_a", "model_a_plus_b"],
                "unit": "categorical",
                "rationale": "This is the intended mechanism change.",
            }
        ],
        "frozen_invariants": ["The mesh policy remains identical."],
        "cases": [
            {
                "case_key": "baseline",
                "scientific_role": "baseline",
                "settings": [{"name": "diffusion_model", "value": "model_a", "unit": "categorical"}],
                "purpose": "Establish the synthetic baseline.",
            },
            {
                "case_key": "candidate",
                "scientific_role": "perturbation",
                "settings": [{"name": "diffusion_model", "value": "model_a_plus_b", "unit": "categorical"}],
                "purpose": "Test the synthetic channel.",
            },
        ],
        "required_observables": ["profile"],
        "comparison_contract": {
            "baseline_case_key": "baseline",
            "comparison_case_keys": ["candidate"],
            "variables": [
                {
                    "variable_key": "diffusion_model",
                    "scientific_path": "physics.diffusion_model",
                    "factor_type": "physical",
                    "comparison_role": "intended_change",
                    "unit": "categorical",
                    "expectations": [
                        {"case_key": "baseline", "value": "model_a"},
                        {"case_key": "candidate", "value": "model_a_plus_b"},
                    ],
                    "equivalence_rule": "exact",
                    "rationale": "This is the intended change.",
                },
                {
                    "variable_key": "mesh_policy",
                    "scientific_path": "numerics.mesh.policy",
                    "factor_type": "numerical",
                    "comparison_role": "frozen",
                    "unit": "categorical",
                    "expectations": [
                        {"case_key": "baseline", "value": "mesh_v1"},
                        {"case_key": "candidate", "value": "mesh_v1"},
                    ],
                    "equivalence_rule": "exact",
                    "rationale": "Mesh must not confound the comparison.",
                },
            ],
            "required_observables": ["profile"],
            "identifiability_claims": [
                {
                    "hypothesis_key": "tail_channel",
                    "observable": "profile",
                    "distinguishing_outcome": "Only the tail changes.",
                    "decision_rule": "Compare front and tail separately.",
                    "ambiguity_conditions": ["The mesh changes."],
                    "smallest_resolving_control": "Run a mesh-only control.",
                }
            ],
        },
        "prediction_tests": [
            {
                "hypothesis_key": "tail_channel",
                "prediction_key": "tail_changes",
                "observable": "profile",
                "expected_result": "Only the tail changes.",
                "falsifying_result": "A valid control has no tail change.",
            }
        ],
        "resource_estimate": {"case_count": 2, "relative_cost": "low", "runtime_basis": "Two synthetic cases."},
        "stop_conditions": ["Stop when control equivalence fails."],
        "value_assessment": {
            "evidence_support": "low",
            "discrimination_power": "high",
            "information_gain": "high",
            "cost": "low",
            "added_free_parameters": 0,
            "rationale": "The fixture isolates one declared variable.",
        },
    }
    return ExperimentPortfolio.model_validate_json(
        canonical_json(
            {
                "objective": "Isolate the synthetic tail channel.",
                "selected_hypothesis_keys": ["tail_channel"],
                "proposals": [proposal],
                "validation_plans": [
                    {
                        "plan_key": "validate_synthetic_model_ab",
                        "experiment_key": "synthetic_model_ab",
                        "numerical": dimension("numerical"),
                        "physical": dimension("physical"),
                        "experimental": dimension("experimental"),
                    }
                ],
                "priority_order": ["synthetic_model_ab"],
                "priority_rationale": "It is the only synthetic study.",
            }
        ),
        strict=True,
    )


def _snapshot(case: str, model: str, mesh: str) -> RealizationSnapshot:
    return RealizationSnapshot.model_validate_json(
        canonical_json(
            {
                "case_key": case,
                "source_description": "Synthetic realization.",
                "values": [
                    {
                        "variable_key": "diffusion_model",
                        "scientific_path": "physics.diffusion_model",
                        "value": model,
                        "unit": "categorical",
                        "source_locator": f"{case}/model",
                    },
                    {
                        "variable_key": "mesh_policy",
                        "scientific_path": "numerics.mesh.policy",
                        "value": mesh,
                        "unit": "categorical",
                        "source_locator": f"{case}/mesh",
                    },
                ],
            }
        ),
        strict=True,
    )


def _diagnosis() -> LayeredDiagnosisReport:
    gate = lambda status, text: {
        "status": status,
        "summary": text,
        "evidence_keys": ["synthetic_run"] if status in {"pass", "fail"} else [],
    }
    return LayeredDiagnosisReport.model_validate_json(
        canonical_json(
            {
                "experiment_key": "synthetic_model_ab",
                "plan_key": "validate_synthetic_model_ab",
                "summary": "Mesh drift invalidates the model comparison.",
                "evidence": [
                    {
                        "source_key": "synthetic_run",
                        "source_type": "runtime_output",
                        "title": "Synthetic realization result",
                        "locator": "in-memory architecture fixture",
                    }
                ],
                "gates": {
                    "evidence_identity": gate("pass", "Identity is explicit."),
                    "implementation_fidelity": gate("pass", "Both cases are traceable."),
                    "numerical_validity": gate("pass", "Synthetic runs are numerically valid."),
                    "control_equivalence": gate("fail", "Mesh policy changed."),
                    "observation": gate("not_evaluable", "Comparison is confounded."),
                    "physical_interpretation": gate("not_evaluable", "Hypothesis is not assessed."),
                },
                "overall_verdict": "invalid_study",
                "claim_allowed": False,
                "hypothesis_assessments": [
                    {
                        "hypothesis_key": "tail_channel",
                        "outcome": "invalid_study",
                        "evidence_keys": ["synthetic_run"],
                        "rationale": "The mesh drift confounds the intended model change.",
                    }
                ],
                "remaining_contradiction": "The mechanism effect remains unknown.",
                "recommended_task_mode": "baseline_replay",
                "next_action": "Freeze mesh and replay the comparison.",
            }
        ),
        strict=True,
    )


def test_clean_fig4_mock_loop_preserves_state_after_invalid_control() -> None:
    manifest = json.loads((FIXTURE / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["allowed_files"] == []
    foundation = _foundation()
    frame = _frame()
    hypotheses = _hypotheses()
    review = _review()
    experiments = _experiments()
    validate_problem_frame_against_foundation(frame, foundation)
    validate_hypotheses_against_foundation(foundation, hypotheses)
    validate_review_against_hypotheses(foundation, hypotheses, review)
    validate_experiments_against_hypotheses(hypotheses, experiments)

    control = evaluate_control_equivalence(
        experiments.proposals[0].comparison_contract,
        (
            _snapshot("baseline", "model_a", "mesh_v1"),
            _snapshot("candidate", "model_a_plus_b", "mesh_v2"),
        ),
    )
    assert control.status == "fail"
    diagnosis = _diagnosis()
    update = derive_knowledge_update(hypotheses, diagnosis)
    projected = validate_layered_discovery_chain(
        frame,
        foundation,
        hypotheses,
        (review,),
        experiments,
        (diagnosis,),
        (update,),
    )
    assert projected.hypotheses[0].status == "under_test"
    assert projected.hypotheses[0].support_level == "low"
    assert projected.remaining_contradiction == "The mechanism effect remains unknown."
