"""Three-dimensional scientific validation reports."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import Identifier, SchemaModel, canonical_json
from .experiment import MetricThreshold, ValidationDimensionPlan, ValidationPlan
from .scientific_foundation import SourceType


HypothesisAssessmentOutcome = Literal[
    "supports",
    "contradicts",
    "inconclusive",
    "invalid_study",
    "not_tested",
]
RecommendedTaskMode = Literal[
    "evidence_intake",
    "baseline_replay",
    "baseline_provenance",
    "deck_revision",
    "new_mechanism",
    "result_diagnosis",
    "stop",
]


class HypothesisAssessment(SchemaModel):
    """A diagnostician's evidence-bound judgment about one tested hypothesis."""

    hypothesis_key: Identifier
    outcome: HypothesisAssessmentOutcome
    evidence_keys: Annotated[
        tuple[Identifier, ...], Field(min_length=1, max_length=64)
    ]
    predictions_checked: Annotated[tuple[Identifier, ...], Field(max_length=64)] = ()
    falsifiers_triggered: Annotated[tuple[Identifier, ...], Field(max_length=64)] = ()
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    def _references_are_unique(self) -> HypothesisAssessment:
        for values, label in (
            (self.evidence_keys, "evidence_keys"),
            (self.predictions_checked, "predictions_checked"),
            (self.falsifiers_triggered, "falsifiers_triggered"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"hypothesis assessment {label} must be unique")
        if self.outcome == "not_tested" and (
            self.predictions_checked or self.falsifiers_triggered
        ):
            raise ValueError("not_tested assessment cannot claim checked predictions")
        if self.falsifiers_triggered and self.outcome != "contradicts":
            raise ValueError("triggered falsifiers require a contradicting outcome")
        return self


class ValidationEvidence(SchemaModel):
    source_key: Identifier
    source_type: SourceType
    title: Annotated[str, Field(min_length=1, max_length=2048)]
    locator: Annotated[str, Field(min_length=1, max_length=4096)]


class ValidationCheckResult(SchemaModel):
    check_key: Identifier
    status: Literal["pass", "fail", "inconclusive", "not_run"]
    evaluation_mode: Literal["deterministic_threshold", "reviewed_qualitative"]
    observed_value: float | int | None = None
    observed_text: Annotated[str, Field(min_length=1, max_length=4096)]
    unit: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    evidence_keys: Annotated[tuple[Identifier, ...], Field(max_length=64)] = ()
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    def _result_has_required_observation(self) -> ValidationCheckResult:
        if self.status in {"pass", "fail"} and not self.evidence_keys:
            raise ValueError("pass/fail validation result requires evidence_keys")
        if (
            self.evaluation_mode == "deterministic_threshold"
            and self.status in {"pass", "fail"}
            and self.observed_value is None
        ):
            raise ValueError("deterministic pass/fail result requires observed_value")
        if self.observed_value is None and self.unit is not None:
            raise ValueError("unit cannot be declared without observed_value")
        if len(self.evidence_keys) != len(set(self.evidence_keys)):
            raise ValueError("validation evidence_keys must be unique")
        return self


class ValidationDimensionReport(SchemaModel):
    status: Literal["pass", "fail", "inconclusive", "not_applicable"]
    summary: Annotated[str, Field(min_length=1, max_length=4096)]
    results: Annotated[tuple[ValidationCheckResult, ...], Field(max_length=128)] = ()

    @model_validator(mode="after")
    def _status_matches_results(self) -> ValidationDimensionReport:
        if self.status == "not_applicable":
            if self.results:
                raise ValueError("not_applicable dimension cannot contain results")
            return self
        if not self.results:
            raise ValueError("active validation dimension requires results")
        keys = tuple(item.check_key for item in self.results)
        if len(keys) != len(set(keys)):
            raise ValueError("validation result check_key values must be unique")
        statuses = {item.status for item in self.results}
        if self.status == "pass" and statuses != {"pass"}:
            raise ValueError("passing dimension requires every check to pass")
        if self.status == "fail" and "fail" not in statuses:
            raise ValueError("failed dimension requires at least one failed check")
        if self.status == "inconclusive" and (
            "fail" in statuses or statuses == {"pass"}
        ):
            raise ValueError("inconclusive dimension has inconsistent check states")
        return self


class ValidationReport(SchemaModel):
    experiment_key: Identifier
    plan_key: Identifier
    summary: Annotated[str, Field(min_length=1, max_length=8192)]
    evidence: Annotated[tuple[ValidationEvidence, ...], Field(max_length=256)] = ()
    numerical: ValidationDimensionReport
    physical: ValidationDimensionReport
    experimental: ValidationDimensionReport
    overall_verdict: Literal["pass", "fail", "inconclusive"]
    claim_allowed: bool
    deviations: Annotated[tuple[str, ...], Field(max_length=128)] = ()
    next_action: Annotated[str, Field(min_length=1, max_length=4096)]
    knowledge_update_applicability: Literal["required", "not_applicable"] = (
        "not_applicable"
    )
    hypothesis_assessments: Annotated[
        tuple[HypothesisAssessment, ...], Field(max_length=32)
    ] = ()
    remaining_contradiction: Annotated[str, Field(min_length=1, max_length=8192)] | None = None
    recommended_task_mode: RecommendedTaskMode | None = None

    @model_validator(mode="after")
    def _verdict_is_derived_from_dimensions(self) -> ValidationReport:
        source_keys = tuple(item.source_key for item in self.evidence)
        if len(source_keys) != len(set(source_keys)):
            raise ValueError("validation source_key values must be unique")
        known_sources = set(source_keys)
        dimensions = (self.numerical, self.physical, self.experimental)
        results = tuple(item for dimension in dimensions for item in dimension.results)
        keys = tuple(item.check_key for item in results)
        if len(keys) != len(set(keys)):
            raise ValueError("validation result check_key values must be globally unique")
        for result in results:
            if not set(result.evidence_keys).issubset(known_sources):
                raise ValueError("validation result references an undeclared source_key")
        active = [item.status for item in dimensions if item.status != "not_applicable"]
        derived = (
            "fail"
            if "fail" in active
            else "pass"
            if active and set(active) == {"pass"}
            else "inconclusive"
        )
        if self.overall_verdict != derived:
            raise ValueError("overall_verdict does not match dimension results")
        if self.claim_allowed != (derived == "pass"):
            raise ValueError("claim_allowed is true only when all active dimensions pass")
        assessment_keys = tuple(
            item.hypothesis_key for item in self.hypothesis_assessments
        )
        if len(assessment_keys) != len(set(assessment_keys)):
            raise ValueError("a report may assess each hypothesis once")
        for assessment in self.hypothesis_assessments:
            if not set(assessment.evidence_keys).issubset(known_sources):
                raise ValueError(
                    "hypothesis assessment references an undeclared source_key"
                )
            if assessment.outcome == "supports" and (
                derived != "pass" or self.numerical.status != "pass"
            ):
                raise ValueError("support requires a numerically valid passing study")
            if assessment.outcome == "contradicts" and (
                derived != "fail" or self.numerical.status != "pass"
            ):
                raise ValueError(
                    "contradiction requires a numerically valid failed prediction"
                )
            if assessment.outcome == "inconclusive" and (
                derived != "inconclusive" or self.numerical.status != "pass"
            ):
                raise ValueError(
                    "inconclusive assessment requires a valid inconclusive study"
                )
            if (
                assessment.outcome == "invalid_study"
                and self.numerical.status == "pass"
            ):
                raise ValueError(
                    "invalid_study assessment requires failed or inconclusive numerics"
                )
        if self.knowledge_update_applicability == "required":
            if not self.hypothesis_assessments:
                raise ValueError(
                    "required knowledge update needs hypothesis_assessments"
                )
            if all(
                item.outcome == "not_tested"
                for item in self.hypothesis_assessments
            ):
                raise ValueError(
                    "required knowledge update needs at least one tested hypothesis"
                )
            if self.remaining_contradiction is None:
                raise ValueError(
                    "required knowledge update needs remaining_contradiction"
                )
            if self.recommended_task_mode is None:
                raise ValueError(
                    "required knowledge update needs recommended_task_mode"
                )
        elif (
            self.hypothesis_assessments
            or self.remaining_contradiction is not None
            or self.recommended_task_mode is not None
        ):
            raise ValueError(
                "not_applicable knowledge update cannot contain transition fields"
            )
        return self


class CurveMetricSummary(SchemaModel):
    points: Annotated[int, Field(ge=2)]
    rmse: Annotated[float, Field(ge=0)]
    normalized_rmse: Annotated[float, Field(ge=0)]
    mean_absolute_error: Annotated[float, Field(ge=0)]
    max_absolute_error: Annotated[float, Field(ge=0)]
    mean_absolute_percentage_error: Annotated[float, Field(ge=0)] | None = None
    slope_rmse: Annotated[float, Field(ge=0)]


def evaluate_threshold(observed: float, threshold: MetricThreshold) -> bool:
    if not math.isfinite(observed):
        raise ValueError("observed metric must be finite")
    if threshold.operator == "lt":
        return observed < threshold.value
    if threshold.operator == "le":
        return observed <= threshold.value
    if threshold.operator == "gt":
        return observed > threshold.value
    if threshold.operator == "ge":
        return observed >= threshold.value
    if threshold.operator == "between":
        assert threshold.upper_value is not None
        return threshold.value <= observed <= threshold.upper_value
    return math.isclose(observed, threshold.value, rel_tol=1e-12, abs_tol=1e-15)


def paired_curve_metrics(
    reference: Sequence[float], candidate: Sequence[float]
) -> CurveMetricSummary:
    if len(reference) != len(candidate) or len(reference) < 2:
        raise ValueError("paired curves require equal lengths of at least two points")
    ref = tuple(float(value) for value in reference)
    cand = tuple(float(value) for value in candidate)
    if not all(math.isfinite(value) for value in (*ref, *cand)):
        raise ValueError("paired curves must contain finite values")
    errors = tuple(right - left for left, right in zip(ref, cand, strict=True))
    absolute = tuple(abs(value) for value in errors)
    rmse = math.sqrt(sum(value * value for value in errors) / len(errors))
    scale = max(ref) - min(ref)
    if scale == 0:
        scale = max(max(abs(value) for value in ref), 1.0)
    percentages = [
        abs(error / target)
        for target, error in zip(ref, errors, strict=True)
        if target != 0
    ]
    slope_errors = tuple(
        (cand[index + 1] - cand[index]) - (ref[index + 1] - ref[index])
        for index in range(len(ref) - 1)
    )
    return CurveMetricSummary(
        points=len(ref),
        rmse=rmse,
        normalized_rmse=rmse / scale,
        mean_absolute_error=sum(absolute) / len(absolute),
        max_absolute_error=max(absolute),
        mean_absolute_percentage_error=(
            sum(percentages) / len(percentages) if percentages else None
        ),
        slope_rmse=math.sqrt(
            sum(value * value for value in slope_errors) / len(slope_errors)
        ),
    )


def relative_conservation_error(
    inflow: float, outflow: float, storage_change: float
) -> float:
    values = (float(inflow), float(outflow), float(storage_change))
    if not all(math.isfinite(value) for value in values):
        raise ValueError("conservation terms must be finite")
    residual = values[0] - values[1] - values[2]
    scale = max(abs(value) for value in values)
    return abs(residual) / scale if scale else 0.0


def validate_report_against_plan(
    plan: ValidationPlan, report: ValidationReport
) -> None:
    if report.plan_key != plan.plan_key or report.experiment_key != plan.experiment_key:
        raise ValueError("validation report does not bind the supplied plan")
    for name in ("numerical", "physical", "experimental"):
        planned: ValidationDimensionPlan = getattr(plan, name)
        observed: ValidationDimensionReport = getattr(report, name)
        if planned.applicability == "not_applicable":
            if observed.status != "not_applicable":
                raise ValueError(f"{name} report must be not_applicable")
            continue
        if observed.status == "not_applicable":
            raise ValueError(f"{name} report cannot skip a required dimension")
        planned_by_key = {item.check_key: item for item in planned.checks}
        observed_by_key = {item.check_key: item for item in observed.results}
        if set(planned_by_key) != set(observed_by_key):
            raise ValueError(f"{name} report does not cover the exact planned checks")
        for key, check in planned_by_key.items():
            result = observed_by_key[key]
            if result.evaluation_mode != check.evaluation_mode:
                raise ValueError("validation evaluation mode differs from plan")
            if check.evaluation_mode == "deterministic_threshold" and result.status in {
                "pass",
                "fail",
            }:
                assert check.threshold is not None and result.observed_value is not None
                passed = evaluate_threshold(float(result.observed_value), check.threshold)
                if (result.status == "pass") != passed:
                    raise ValueError("deterministic validation status disagrees with threshold")


def validate_validation_report(value: dict[str, object]) -> dict[str, object]:
    return ValidationReport.model_validate_json(
        canonical_json(value), strict=True
    ).model_dump(mode="json")


__all__ = [
    "CurveMetricSummary",
    "HypothesisAssessment",
    "HypothesisAssessmentOutcome",
    "RecommendedTaskMode",
    "ValidationCheckResult",
    "ValidationDimensionReport",
    "ValidationEvidence",
    "ValidationReport",
    "evaluate_threshold",
    "paired_curve_metrics",
    "relative_conservation_error",
    "validate_report_against_plan",
    "validate_validation_report",
]
