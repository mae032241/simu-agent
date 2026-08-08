from __future__ import annotations

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.hypothesis import HypothesisPortfolio
from scidiscovery.artifact_agent.schema.knowledge import (
    derive_knowledge_update,
    project_knowledge_state,
)
from scidiscovery.artifact_agent.schema.layered_diagnosis import (
    LayeredDiagnosisReport,
)


def _portfolio() -> HypothesisPortfolio:
    return HypothesisPortfolio.model_validate_json(
        canonical_json(
            {
                "objective": "Explain the Fig.4 tail mismatch.",
                "contradiction": "The baseline front and tail cannot both be matched.",
                "foundation_summary": "The target curve is frozen.",
                "foundation_item_keys": ["fig4_target"],
                "hypotheses": [
                    {
                        "hypothesis_key": "secondary_tail",
                        "statement": "A second channel produces the dilute tail.",
                        "mechanism": "A slower defect-assisted channel extends the profile.",
                        "scope": "Fig.4 single-layer experiment.",
                        "predictions": [
                            {
                                "prediction_key": "tail_signature",
                                "observable": "Zinc depth profile",
                                "expected_outcome": "Tail improves without moving the front.",
                                "rationale": "The mechanisms dominate different concentration ranges.",
                            }
                        ],
                        "falsifiers": [
                            {
                                "falsifier_key": "tail_absent",
                                "observable": "Zinc depth profile",
                                "rejection_condition": "A valid control shows no tail change.",
                                "rationale": "The proposed channel must affect the tail.",
                            }
                        ],
                        "status": "under_test",
                        "support_level": "low",
                        "support_rationale": "The mechanism has not passed a valid test.",
                    }
                ],
                "ranking": ["secondary_tail"],
                "ranking_rationale": "This is the active hypothesis.",
            }
        ),
        strict=True,
    )


def _gate(status: str, summary: str) -> dict[str, object]:
    return {
        "status": status,
        "summary": summary,
        "evidence_keys": ["run"] if status in {"pass", "fail"} else [],
    }


def _invalid_report() -> LayeredDiagnosisReport:
    return LayeredDiagnosisReport.model_validate_json(
        canonical_json(
            {
                "experiment_key": "fig4_model_test",
                "plan_key": "validate_fig4_model_test",
                "summary": "The model comparison changed the mesh.",
                "evidence": [
                    {
                        "source_key": "run",
                        "source_type": "runtime_output",
                        "title": "Realization comparison",
                        "locator": "fig4_clean/control_equivalence.json",
                    }
                ],
                "gates": {
                    "evidence_identity": _gate("pass", "Identity verified."),
                    "implementation_fidelity": _gate("pass", "Implementation traced."),
                    "numerical_validity": _gate("pass", "Both runs converged."),
                    "control_equivalence": _gate("fail", "Mesh changed."),
                    "observation": _gate("not_evaluable", "Comparison invalid."),
                    "physical_interpretation": _gate(
                        "not_evaluable", "Hypothesis cannot be assessed."
                    ),
                },
                "overall_verdict": "invalid_study",
                "claim_allowed": False,
                "hypothesis_assessments": [
                    {
                        "hypothesis_key": "secondary_tail",
                        "outcome": "invalid_study",
                        "evidence_keys": ["run"],
                        "rationale": "The mesh change confounds the comparison.",
                    }
                ],
                "remaining_contradiction": "The physical effect remains unknown.",
                "recommended_task_mode": "baseline_replay",
                "next_action": "Run the exact baseline and a mesh-only control.",
            }
        ),
        strict=True,
    )


def test_invalid_layered_study_preserves_hypothesis_state() -> None:
    portfolio = _portfolio()
    report = _invalid_report()
    update = derive_knowledge_update(portfolio, report)
    transition = update.transitions[0]
    assert update.validation_verdict == "invalid_study"
    assert transition.prior_status == "under_test"
    assert transition.new_status == "under_test"
    assert transition.new_support_level == "low"
    projected = project_knowledge_state(portfolio, (update,))
    assert projected.hypotheses[0].status == "under_test"
    assert projected.remaining_contradiction == "The physical effect remains unknown."
