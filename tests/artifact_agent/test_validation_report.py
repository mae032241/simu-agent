from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.experiment import (
    MetricThreshold,
    ValidationPlan,
)
from scidiscovery.artifact_agent.schema.validation import (
    ValidationReport,
    evaluate_threshold,
    paired_curve_metrics,
    relative_conservation_error,
    validate_report_against_plan,
    validate_validation_report,
)


def _check(key: str, *, deterministic: bool = False) -> dict[str, object]:
    value: dict[str, object] = {
        "check_key": key,
        "observable": f"{key} observable",
        "metric": f"{key} metric",
        "evaluation_mode": (
            "deterministic_threshold" if deterministic else "reviewed_qualitative"
        ),
        "acceptance_condition": "Pass the pre-registered condition.",
        "failure_action": "Reject the claim.",
        "basis": "Pre-registered validation basis.",
    }
    if deterministic:
        value["threshold"] = {
            "operator": "le",
            "value": 0.1,
            "unit": "dimensionless",
        }
    return value


def _plan() -> ValidationPlan:
    return ValidationPlan.model_validate_json(
        canonical_json(
            {
                "plan_key": "validate_field_study",
                "experiment_key": "field_study",
                "numerical": {
                    "applicability": "required",
                    "rationale": "Numerical convergence is required.",
                    "checks": [_check("curve_nrmse", deterministic=True)],
                },
                "physical": {
                    "applicability": "required",
                    "rationale": "Field localization is the mechanism prediction.",
                    "checks": [_check("field_map")],
                },
                "experimental": {
                    "applicability": "required",
                    "rationale": "The C-V curve is the measured target.",
                    "checks": [_check("cv_match")],
                },
            }
        ),
        strict=True,
    )


def _dimension(key: str, *, observed_value: float | None = None) -> dict[str, object]:
    deterministic = observed_value is not None
    result: dict[str, object] = {
        "check_key": key,
        "status": "pass",
        "evaluation_mode": (
            "deterministic_threshold" if deterministic else "reviewed_qualitative"
        ),
        "observed_text": f"{key} passed.",
        "evidence_keys": ["run_output"],
        "rationale": "The pre-registered criterion passed.",
    }
    if deterministic:
        result["observed_value"] = observed_value
        result["unit"] = "dimensionless"
    return {"status": "pass", "summary": f"{key} passed.", "results": [result]}


def _report() -> dict[str, object]:
    return {
        "experiment_key": "field_study",
        "plan_key": "validate_field_study",
        "summary": "All pre-registered checks passed.",
        "evidence": [
            {
                "source_key": "run_output",
                "source_type": "runtime_output",
                "title": "Collected TCAD outputs",
                "locator": "field.plt and cv.plt",
            }
        ],
        "numerical": _dimension("curve_nrmse", observed_value=0.05),
        "physical": _dimension("field_map"),
        "experimental": _dimension("cv_match"),
        "overall_verdict": "pass",
        "claim_allowed": True,
        "next_action": "Proceed to the next bounded hypothesis test.",
    }


def _parse_report(value: dict[str, object]) -> ValidationReport:
    return ValidationReport.model_validate_json(canonical_json(value), strict=True)


def test_deterministic_curve_and_conservation_metrics() -> None:
    metrics = paired_curve_metrics([0.0, 1.0, 2.0], [0.0, 1.1, 1.9])
    assert metrics.points == 3
    assert metrics.rmse == pytest.approx(math.sqrt(0.02 / 3))
    assert metrics.normalized_rmse == pytest.approx(metrics.rmse / 2)
    assert metrics.max_absolute_error == pytest.approx(0.1)
    assert metrics.slope_rmse > 0
    assert relative_conservation_error(10, 9, 1) == 0
    assert relative_conservation_error(10, 8, 1) == pytest.approx(0.1)


def test_threshold_evaluation_and_plan_binding() -> None:
    threshold = MetricThreshold(
        operator="between", value=0.0, upper_value=0.1, unit="dimensionless"
    )
    assert evaluate_threshold(0.05, threshold)
    assert not evaluate_threshold(0.2, threshold)
    report = _parse_report(_report())
    validate_report_against_plan(_plan(), report)
    assert validate_validation_report(_report())["claim_allowed"] is True


def test_report_cannot_claim_pass_when_a_dimension_fails() -> None:
    value = _report()
    value["physical"]["status"] = "fail"
    value["physical"]["results"][0]["status"] = "fail"
    with pytest.raises(ValidationError, match="overall_verdict"):
        _parse_report(value)


def test_report_rejects_unknown_evidence_source() -> None:
    value = _report()
    value["experimental"]["results"][0]["evidence_keys"] = ["missing"]
    with pytest.raises(ValidationError, match="undeclared source_key"):
        _parse_report(value)


def test_report_status_must_match_deterministic_threshold() -> None:
    value = _report()
    value["numerical"]["results"][0]["observed_value"] = 0.2
    report = _parse_report(value)
    with pytest.raises(ValueError, match="disagrees with threshold"):
        validate_report_against_plan(_plan(), report)


def test_required_plan_dimension_cannot_be_skipped() -> None:
    value = _report()
    value["experimental"] = {
        "status": "not_applicable",
        "summary": "Skipped incorrectly.",
    }
    value["overall_verdict"] = "pass"
    report = _parse_report(value)
    with pytest.raises(ValueError, match="cannot skip"):
        validate_report_against_plan(_plan(), report)


def test_required_knowledge_update_needs_explicit_hypothesis_judgment() -> None:
    value = _report()
    value["knowledge_update_applicability"] = "required"
    with pytest.raises(ValidationError, match="hypothesis_assessments"):
        _parse_report(value)


def test_engineering_report_cannot_smuggle_hypothesis_transition_fields() -> None:
    value = _report()
    value["remaining_contradiction"] = "An undeclared contradiction."
    with pytest.raises(ValidationError, match="not_applicable"):
        _parse_report(value)
