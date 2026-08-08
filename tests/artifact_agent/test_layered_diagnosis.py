from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.layered_diagnosis import (
    LayeredDiagnosisReport,
)


def _gate(status: str, summary: str) -> dict[str, object]:
    return {
        "status": status,
        "summary": summary,
        "evidence_keys": ["run"] if status in {"pass", "fail"} else [],
    }


def _invalid_control_report() -> dict[str, object]:
    return {
        "experiment_key": "fig4_model_test",
        "plan_key": "validate_fig4_model_test",
        "summary": "The comparison changed both model and mesh.",
        "evidence": [
            {
                "source_key": "run",
                "source_type": "runtime_output",
                "title": "Fig.4 realization and outputs",
                "locator": "clean_fixture/run",
            }
        ],
        "gates": {
            "evidence_identity": _gate("pass", "The compared outputs are identified."),
            "implementation_fidelity": _gate("pass", "Both realized projects are traceable."),
            "numerical_validity": _gate("pass", "Both solvers completed validly."),
            "control_equivalence": _gate("fail", "The mesh policy changed."),
            "observation": _gate("not_evaluable", "The confounded curve is not scored."),
            "physical_interpretation": _gate(
                "not_evaluable", "The physical hypothesis cannot be assessed."
            ),
        },
        "overall_verdict": "invalid_study",
        "claim_allowed": False,
        "hypothesis_assessments": [
            {
                "hypothesis_key": "secondary_tail",
                "outcome": "invalid_study",
                "evidence_keys": ["run"],
                "rationale": "The unplanned mesh change confounds the model comparison.",
            }
        ],
        "remaining_contradiction": "The effect of the physical model remains unknown.",
        "recommended_task_mode": "baseline_replay",
        "next_action": "Run a byte-exact baseline and then a mesh-only control.",
    }


def test_failed_control_produces_invalid_study_not_physical_rejection() -> None:
    report = LayeredDiagnosisReport.model_validate_json(
        canonical_json(_invalid_control_report()), strict=True
    )
    assert report.overall_verdict == "invalid_study"
    assert report.gates.first_failed_gate == "control_equivalence"
    assert report.hypothesis_assessments[0].outcome == "invalid_study"


def test_physical_interpretation_must_stop_after_control_failure() -> None:
    value = _invalid_control_report()
    value["gates"]["physical_interpretation"] = _gate(
        "fail", "The hypothesis appears inconsistent."
    )
    with pytest.raises(ValidationError, match="physical interpretation must be not_evaluable"):
        LayeredDiagnosisReport.model_validate_json(canonical_json(value), strict=True)


def test_invalid_study_cannot_claim_hypothesis_support() -> None:
    value = _invalid_control_report()
    value["hypothesis_assessments"][0]["outcome"] = "supports"
    with pytest.raises(ValidationError, match="cannot support or contradict"):
        LayeredDiagnosisReport.model_validate_json(canonical_json(value), strict=True)


def test_valid_failed_prediction_can_contradict_hypothesis() -> None:
    value = deepcopy(_invalid_control_report())
    value["gates"]["control_equivalence"] = _gate("pass", "The controls are equivalent.")
    value["gates"]["observation"] = _gate("fail", "The predicted tail is absent.")
    value["gates"]["physical_interpretation"] = _gate(
        "fail", "The pre-registered mechanism signature is absent."
    )
    value["overall_verdict"] = "fail"
    value["hypothesis_assessments"][0].update(
        outcome="contradicts",
        predictions_checked=["tail_signature"],
        falsifiers_triggered=["tail_absent"],
    )
    report = LayeredDiagnosisReport.model_validate_json(
        canonical_json(value), strict=True
    )
    assert report.hypothesis_assessments[0].outcome == "contradicts"
