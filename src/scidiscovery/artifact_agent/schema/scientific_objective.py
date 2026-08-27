"""Immutable scientific objectives and deterministic experiment coverage."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import Field, model_validator

from .common import Identifier, SchemaModel, Sha256, canonical_sha256
from .curve_score import (
    CurveBundle,
    CurveComparisonPurpose,
    CurveDomain,
    CurveSeries,
    curve_units_equivalent,
)

if TYPE_CHECKING:
    from .experiment import ExperimentPortfolio


ObjectiveIntent = Literal[
    "external_reproduction",
    "mechanism_discrimination",
    "numerical_qualification",
    "engineering",
]
ObjectiveCoverageStatus = Literal["pass", "blocked", "fail"]
ObjectiveReadinessStatus = Literal["not_declared", "blocked", "evaluable"]

# Digitized axis bounds may be serialized at fewer decimal places than points.
# Keep this far below a sampled interval; exclusions still block real overlap.
_DOMAIN_BOUNDARY_REL_TOL = 1e-12
_DOMAIN_BOUNDARY_ABS_TOL = 1e-15


class ObjectiveReadinessProjection(SchemaModel):
    status: ObjectiveReadinessStatus
    mandatory_target_gaps: Annotated[
        tuple[str, ...], Field(max_length=128)
    ] = ()

    @model_validator(mode="after")
    def _gaps_match_status(self) -> ObjectiveReadinessProjection:
        if self.status == "blocked" and not self.mandatory_target_gaps:
            raise ValueError("blocked objective readiness requires a target gap")
        if self.status != "blocked" and self.mandatory_target_gaps:
            raise ValueError("only blocked objective readiness may declare target gaps")
        if len(self.mandatory_target_gaps) != len(set(self.mandatory_target_gaps)):
            raise ValueError("mandatory target gaps must be unique")
        return self


class ObjectiveTarget(SchemaModel):
    target_key: Identifier
    observable: Annotated[str, Field(min_length=1, max_length=4096)]
    reference_series_key: Identifier
    required_domains: Annotated[
        tuple[CurveDomain, ...], Field(min_length=1, max_length=64)
    ]
    support_requirement: Literal["full_series", "qualified_segments"]
    evidence_item_keys: Annotated[
        tuple[Identifier, ...], Field(min_length=1, max_length=64)
    ]
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    def _domains_and_evidence_are_unique(self) -> ObjectiveTarget:
        if len(self.evidence_item_keys) != len(set(self.evidence_item_keys)):
            raise ValueError("objective target evidence_item_keys must be unique")
        domain_keys = tuple(
            (item.start, item.stop, item.unit, item.min_points)
            for item in self.required_domains
        )
        if len(domain_keys) != len(set(domain_keys)):
            raise ValueError("objective target required domains must be unique")
        return self


class ObjectiveClosureRequirement(SchemaModel):
    requirement_key: Identifier
    description: Annotated[str, Field(min_length=1, max_length=4096)]
    requirement_type: Literal[
        "target_coverage", "comparison_present", "validation_check_present"
    ] = "target_coverage"
    target_keys: Annotated[tuple[Identifier, ...], Field(max_length=64)] = ()
    comparison_purposes: Annotated[
        tuple[CurveComparisonPurpose, ...], Field(max_length=16)
    ] = ()
    validation_check_keys: Annotated[
        tuple[Identifier, ...], Field(max_length=128)
    ] = ()

    @model_validator(mode="after")
    def _targets_are_unique(self) -> ObjectiveClosureRequirement:
        for values, label in (
            (self.target_keys, "target_keys"),
            (self.comparison_purposes, "comparison_purposes"),
            (self.validation_check_keys, "validation_check_keys"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"objective closure {label} must be unique")
        if self.requirement_type == "target_coverage":
            if not self.target_keys:
                raise ValueError("target_coverage requires target_keys")
            if self.comparison_purposes or self.validation_check_keys:
                raise ValueError("target_coverage accepts only target_keys")
        elif self.requirement_type == "comparison_present":
            if not self.comparison_purposes:
                raise ValueError(
                    "comparison_present requires comparison_purposes"
                )
            if self.validation_check_keys:
                raise ValueError(
                    "comparison_present cannot declare validation_check_keys"
                )
        else:
            if not self.validation_check_keys:
                raise ValueError(
                    "validation_check_present requires validation_check_keys"
                )
            if self.target_keys or self.comparison_purposes:
                raise ValueError(
                    "validation_check_present accepts only validation_check_keys"
                )
        return self


class ResearchObjectiveContract(SchemaModel):
    objective_key: Identifier
    intent: ObjectiveIntent
    statement: Annotated[str, Field(min_length=1, max_length=8192)]
    mandatory_targets: Annotated[
        tuple[ObjectiveTarget, ...], Field(max_length=128)
    ] = ()
    closure_requirements: Annotated[
        tuple[ObjectiveClosureRequirement, ...], Field(min_length=1, max_length=128)
    ]

    @model_validator(mode="after")
    def _objective_is_complete(self) -> ResearchObjectiveContract:
        target_keys = tuple(item.target_key for item in self.mandatory_targets)
        requirement_keys = tuple(
            item.requirement_key for item in self.closure_requirements
        )
        if len(target_keys) != len(set(target_keys)):
            raise ValueError("objective target keys must be unique")
        if len(requirement_keys) != len(set(requirement_keys)):
            raise ValueError("objective closure requirement keys must be unique")
        if self.intent == "external_reproduction" and not self.mandatory_targets:
            raise ValueError(
                "external-reproduction objective requires a mandatory external target"
            )
        known_targets = set(target_keys)
        for requirement in self.closure_requirements:
            if not set(requirement.target_keys).issubset(known_targets):
                raise ValueError("closure requirement references an unknown target")
        return self


class ObjectiveCoverageBundle(SchemaModel):
    source_name: Identifier
    bundle_sha256: Sha256
    series_keys: Annotated[tuple[Identifier, ...], Field(min_length=1, max_length=10000)]


class ObjectiveTargetCoverage(SchemaModel):
    target_key: Identifier
    reference_series_key: Identifier
    status: ObjectiveCoverageStatus
    comparison_keys: Annotated[tuple[Identifier, ...], Field(max_length=10000)] = ()
    reason_codes: Annotated[tuple[Identifier, ...], Field(max_length=64)] = ()

    @model_validator(mode="after")
    def _status_matches_reasons(self) -> ObjectiveTargetCoverage:
        if len(self.comparison_keys) != len(set(self.comparison_keys)):
            raise ValueError("objective target comparison_keys must be unique")
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise ValueError("objective target reason_codes must be unique")
        if self.status == "pass" and self.reason_codes:
            raise ValueError("passing objective target cannot have reason codes")
        if self.status != "pass" and not self.reason_codes:
            raise ValueError("non-passing objective target requires a reason code")
        return self


class ObjectiveRequirementCoverage(SchemaModel):
    requirement_key: Identifier
    status: ObjectiveCoverageStatus
    reason_codes: Annotated[tuple[Identifier, ...], Field(max_length=64)] = ()

    @model_validator(mode="after")
    def _status_matches_reasons(self) -> ObjectiveRequirementCoverage:
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise ValueError("objective requirement reason_codes must be unique")
        if self.status == "pass" and self.reason_codes:
            raise ValueError("passing objective requirement cannot have reason codes")
        if self.status != "pass" and not self.reason_codes:
            raise ValueError(
                "non-passing objective requirement requires a reason code"
            )
        return self


class ObjectiveCoverageReport(SchemaModel):
    schema_id: Literal["scidiscovery.objective-coverage.v1"] = (
        "scidiscovery.objective-coverage.v1"
    )
    status: ObjectiveCoverageStatus
    objective_sha256: Sha256
    experiment_plan_sha256: Sha256
    bundles: Annotated[
        tuple[ObjectiveCoverageBundle, ...], Field(max_length=4096)
    ] = ()
    targets: Annotated[
        tuple[ObjectiveTargetCoverage, ...], Field(max_length=128)
    ] = ()
    requirements: Annotated[
        tuple[ObjectiveRequirementCoverage, ...], Field(max_length=128)
    ] = ()

    @model_validator(mode="after")
    def _aggregate_is_derived(self) -> ObjectiveCoverageReport:
        statuses = {
            item.status for item in (*self.targets, *self.requirements)
        }
        derived: ObjectiveCoverageStatus = (
            "fail" if "fail" in statuses else "blocked" if "blocked" in statuses else "pass"
        )
        if self.status != derived:
            raise ValueError("objective coverage status is not derived from its targets")
        target_keys = tuple(item.target_key for item in self.targets)
        if len(target_keys) != len(set(target_keys)):
            raise ValueError("objective coverage target keys must be unique")
        requirement_keys = tuple(
            item.requirement_key for item in self.requirements
        )
        if len(requirement_keys) != len(set(requirement_keys)):
            raise ValueError("objective coverage requirement keys must be unique")
        return self


def evaluate_objective_coverage(
    objective: ResearchObjectiveContract,
    portfolio: ExperimentPortfolio,
    reference_bundles: tuple[tuple[str, CurveBundle], ...],
) -> ObjectiveCoverageReport:
    """Validate that a plan retains every approved target without choosing it."""

    actual: dict[str, tuple[str, CurveBundle]] = {}
    for source_name, bundle in reference_bundles:
        for series in bundle.series:
            if series.series_key in actual:
                raise ValueError(
                    f"objective reference series is supplied more than once: {series.series_key}"
                )
            actual[series.series_key] = (source_name, bundle)

    comparison_records = []
    for proposal in portfolio.proposals:
        spec = proposal.curve_comparison_spec
        if spec is None:
            continue
        declarations = {item.series_key: item for item in spec.series_declarations}
        for comparison in spec.comparisons:
            comparison_records.append((comparison, declarations))

    target_results: list[ObjectiveTargetCoverage] = []
    for target in objective.mandatory_targets:
        semantic_reasons: list[str] = []
        support_reasons: list[str] = []
        matching = [
            (comparison, declarations)
            for comparison, declarations in comparison_records
            if comparison.reference_series == target.reference_series_key
            and comparison.purpose == "target_fit"
        ]
        if portfolio.objective_key != objective.objective_key:
            semantic_reasons.append("objective_key_mismatch")
        if objective.intent == "external_reproduction" and portfolio.study_kind != "scientific":
            semantic_reasons.append("external_objective_requires_scientific_study")
        if not matching:
            semantic_reasons.append("target_comparison_missing")
        else:
            for comparison, declarations in matching:
                reference = declarations.get(comparison.reference_series)
                candidate = declarations.get(comparison.candidate_series)
                if (
                    reference is None
                    or reference.source != "reference_input"
                    or reference.scientific_role != "experimental_target"
                    or candidate is None
                    or candidate.source != "solver_output"
                    or candidate.scientific_role != "simulation_candidate"
                ):
                    semantic_reasons.append("target_comparison_role_mismatch")
            for required_domain in target.required_domains:
                if not any(
                    _domains_equal(required_domain, comparison.domain)
                    for comparison, _ in matching
                ):
                    semantic_reasons.append("target_domain_missing")

        supplied = actual.get(target.reference_series_key)
        if supplied is None:
            semantic_reasons.append("target_reference_missing")
        else:
            _, bundle = supplied
            series = next(
                item
                for item in bundle.series
                if item.series_key == target.reference_series_key
            )
            if series.availability.status != "available":
                support_reasons.append("target_reference_unavailable")
            else:
                for domain in target.required_domains:
                    if not _series_covers_domain(series, domain):
                        support_reasons.append("target_support_unavailable")

        semantic_reasons = list(dict.fromkeys(semantic_reasons))
        support_reasons = list(dict.fromkeys(support_reasons))
        status: ObjectiveCoverageStatus = (
            "fail" if semantic_reasons else "blocked" if support_reasons else "pass"
        )
        target_results.append(
            ObjectiveTargetCoverage(
                target_key=target.target_key,
                reference_series_key=target.reference_series_key,
                status=status,
                comparison_keys=tuple(
                    comparison.comparison_key for comparison, _ in matching
                ),
                reason_codes=tuple((*semantic_reasons, *support_reasons)),
            )
        )

    target_by_key = {item.target_key: item for item in target_results}
    required_comparisons = tuple(
        comparison
        for comparison, _ in comparison_records
        if comparison.required
    )
    declared_check_keys = {
        check.check_key
        for plan in portfolio.validation_plans
        for dimension in (plan.numerical, plan.physical, plan.experimental)
        for check in dimension.checks
    }
    requirement_results: list[ObjectiveRequirementCoverage] = []
    target_definition_by_key = {
        item.target_key: item for item in objective.mandatory_targets
    }
    for requirement in objective.closure_requirements:
        reasons: list[str] = []
        status: ObjectiveCoverageStatus = "pass"
        if requirement.requirement_type == "target_coverage":
            target_statuses = {
                target_by_key[key].status for key in requirement.target_keys
            }
            if "fail" in target_statuses:
                status = "fail"
                reasons.append("required_target_failed")
            elif "blocked" in target_statuses:
                status = "blocked"
                reasons.append("required_target_blocked")
        elif requirement.requirement_type == "comparison_present":
            target_series = {
                target_definition_by_key[key].reference_series_key
                for key in requirement.target_keys
            }
            for purpose in requirement.comparison_purposes:
                if not any(
                    comparison.purpose == purpose
                    and (
                        not target_series
                        or comparison.reference_series in target_series
                    )
                    for comparison in required_comparisons
                ):
                    reasons.append("required_comparison_missing")
            if reasons:
                status = "fail"
        else:
            if not set(requirement.validation_check_keys).issubset(
                declared_check_keys
            ):
                status = "fail"
                reasons.append("required_validation_check_missing")
        requirement_results.append(
            ObjectiveRequirementCoverage(
                requirement_key=requirement.requirement_key,
                status=status,
                reason_codes=tuple(dict.fromkeys(reasons)),
            )
        )

    statuses = {
        item.status for item in (*target_results, *requirement_results)
    }
    aggregate: ObjectiveCoverageStatus = (
        "fail" if "fail" in statuses else "blocked" if "blocked" in statuses else "pass"
    )
    return ObjectiveCoverageReport(
        status=aggregate,
        objective_sha256=canonical_sha256(objective),
        experiment_plan_sha256=canonical_sha256(portfolio),
        bundles=tuple(
            ObjectiveCoverageBundle(
                source_name=name,
                bundle_sha256=canonical_sha256(bundle),
                series_keys=tuple(item.series_key for item in bundle.series),
            )
            for name, bundle in reference_bundles
        ),
        targets=tuple(target_results),
        requirements=tuple(requirement_results),
    )


def project_objective_readiness(
    objectives: tuple[ResearchObjectiveContract, ...],
    portfolios: tuple[ExperimentPortfolio, ...],
    coverage_reports: tuple[ObjectiveCoverageReport, ...],
) -> ObjectiveReadinessProjection:
    """Project whether the immutable objective can safely advance.

    An objective is evaluable before its first plan exists. Once a plan exists,
    each current plan must name the exact objective and have a passing coverage
    report over the exact plan bytes. This keeps unavailable paper targets from
    being silently replaced by numerical self-comparisons.
    """

    if not objectives:
        return ObjectiveReadinessProjection(status="not_declared")
    if len(objectives) != 1:
        return ObjectiveReadinessProjection(
            status="blocked",
            mandatory_target_gaps=("research_objective:multiple_current_objects",),
        )
    objective = objectives[0]
    if not portfolios:
        return ObjectiveReadinessProjection(status="evaluable")
    if len(portfolios) != 1:
        return ObjectiveReadinessProjection(
            status="blocked",
            mandatory_target_gaps=("experiment_plan:multiple_current_plans",),
        )

    gaps: list[str] = []
    exact_reports = {
        (item.objective_sha256, item.experiment_plan_sha256): item
        for item in coverage_reports
    }
    if len(exact_reports) != len(coverage_reports):
        gaps.append("objective_coverage:duplicate_exact_report")
    objective_digest = canonical_sha256(objective)
    for portfolio in portfolios:
        if portfolio.objective_key is None:
            gaps.append("experiment_plan:objective_key_missing")
            continue
        if portfolio.objective_key != objective.objective_key:
            gaps.append("experiment_plan:objective_key_mismatch")
            continue
        report = exact_reports.get(
            (objective_digest, canonical_sha256(portfolio))
        )
        if report is None:
            gaps.append("experiment_plan:objective_coverage_missing")
            continue
        if report.status != "pass":
            for target in report.targets:
                for reason in target.reason_codes:
                    gaps.append(f"{target.target_key}:{reason}")
            if not report.targets:
                gaps.append("objective_coverage:nonpassing_without_target_detail")
            for requirement in report.requirements:
                for reason in requirement.reason_codes:
                    gaps.append(f"{requirement.requirement_key}:{reason}")
    if gaps:
        return ObjectiveReadinessProjection(
            status="blocked",
            mandatory_target_gaps=tuple(dict.fromkeys(gaps)),
        )
    return ObjectiveReadinessProjection(status="evaluable")


def _domains_equal(left: CurveDomain, right: CurveDomain) -> bool:
    return (
        left.start == right.start
        and left.stop == right.stop
        and left.min_points == right.min_points
        and curve_units_equivalent(left.unit, right.unit)
    )


def _series_covers_domain(series: CurveSeries, domain: CurveDomain) -> bool:
    points = series.points
    in_domain = [
        item
        for item in points
        if not _domain_value_below(item.x, domain.start)
        and not _domain_value_above(item.x, domain.stop)
    ]
    if len(in_domain) < domain.min_points or not points:
        return False
    if _domain_value_below(domain.start, min(item.x for item in points)) or (
        _domain_value_above(domain.stop, max(item.x for item in points))
    ):
        return False
    valid_intervals = series.valid_intervals
    if valid_intervals and not any(
        not _domain_value_above(item.start, domain.start)
        and not _domain_value_below(item.stop, domain.stop)
        for item in valid_intervals
    ):
        return False
    exclusions = series.exclusions
    return not any(
        _domain_value_below(item.start, domain.stop)
        and _domain_value_above(item.stop, domain.start)
        for item in exclusions
    )


def _domain_value_below(left: float, right: float) -> bool:
    return left < right and not math.isclose(
        left,
        right,
        rel_tol=_DOMAIN_BOUNDARY_REL_TOL,
        abs_tol=_DOMAIN_BOUNDARY_ABS_TOL,
    )


def _domain_value_above(left: float, right: float) -> bool:
    return left > right and not math.isclose(
        left,
        right,
        rel_tol=_DOMAIN_BOUNDARY_REL_TOL,
        abs_tol=_DOMAIN_BOUNDARY_ABS_TOL,
    )


__all__ = [
    "ObjectiveClosureRequirement",
    "ObjectiveCoverageBundle",
    "ObjectiveCoverageReport",
    "ObjectiveCoverageStatus",
    "ObjectiveReadinessProjection",
    "ObjectiveReadinessStatus",
    "ObjectiveIntent",
    "ObjectiveTarget",
    "ObjectiveTargetCoverage",
    "ObjectiveRequirementCoverage",
    "ResearchObjectiveContract",
    "evaluate_objective_coverage",
    "project_objective_readiness",
]
