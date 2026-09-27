"""Immutable scientific objectives and deterministic experiment coverage."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import Field, model_validator

from scidiscovery.artifact_agent.schema.common import (
    Identifier,
    SchemaModel,
    Sha256,
    canonical_sha256,
)
from .schema import (
    CurveBundle,
    CurveExperimentContract,
    CurveDomain,
    CurveSeries,
    curve_units_equivalent,
    validate_curve_experiment_contract,
)
from scidiscovery.artifact_agent.schema.research_objective import (
    ObjectiveClosureRequirement,
    ObjectiveIntent,
    ObjectiveTarget,
    ResearchObjectiveContract,
)

if TYPE_CHECKING:
    from scidiscovery.artifact_agent.schema.experiment import ExperimentPortfolio


ObjectiveCoverageStatus = Literal["pass", "blocked", "fail"]

# Digitized axis bounds may be serialized at fewer decimal places than points.
# Keep this far below a sampled interval; exclusions still block real overlap.
_DOMAIN_BOUNDARY_REL_TOL = 1e-12
_DOMAIN_BOUNDARY_ABS_TOL = 1e-15



class ObjectiveCoverageBundle(SchemaModel):
    source_name: Identifier
    bundle_sha256: Sha256
    series_keys: Annotated[tuple[Identifier, ...], Field(min_length=1, max_length=10000)]


class ObjectiveTargetCoverage(SchemaModel):
    target_key: Identifier
    reference_series_key: Identifier | None = None
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
    curve_contracts: tuple[CurveExperimentContract, ...],
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

    contract_keys = tuple(item.experiment_key for item in curve_contracts)
    if len(contract_keys) != len(set(contract_keys)):
        raise ValueError("curve objective coverage contracts must be unique by experiment")
    comparison_records = []
    target_bindings = {}
    for contract in curve_contracts:
        validate_curve_experiment_contract(contract, portfolio)
        spec = contract.comparison_spec
        for binding in contract.objective_target_bindings:
            if binding.target_key in target_bindings:
                raise ValueError("curve objective target is bound more than once")
            target_bindings[binding.target_key] = binding
        declarations = {item.series_key: item for item in spec.series_declarations}
        for comparison in spec.comparisons:
            comparison_records.append((comparison, declarations))

    target_results: list[ObjectiveTargetCoverage] = []
    for target in objective.mandatory_targets:
        semantic_reasons: list[str] = []
        support_reasons: list[str] = []
        binding = target_bindings.get(target.target_key)
        reference_series_key = (
            binding.reference_series_key if binding is not None else None
        )
        if binding is None:
            semantic_reasons.append("target_curve_binding_missing")
        matching = [
            (comparison, declarations)
            for comparison, declarations in comparison_records
            if reference_series_key is not None
            and comparison.reference_series == reference_series_key
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
            assert binding is not None
            for required_domain in binding.required_domains:
                if not any(
                    _domains_equal(required_domain, comparison.domain)
                    for comparison, _ in matching
                ):
                    semantic_reasons.append("target_domain_missing")

        supplied = (
            actual.get(reference_series_key)
            if reference_series_key is not None
            else None
        )
        if supplied is None:
            semantic_reasons.append("target_reference_missing")
        else:
            _, bundle = supplied
            series = next(
                item
                for item in bundle.series
                if item.series_key == reference_series_key
            )
            if series.availability.status != "available":
                support_reasons.append("target_reference_unavailable")
            else:
                assert binding is not None
                for domain in binding.required_domains:
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
                reference_series_key=reference_series_key,
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
                target_bindings[key].reference_series_key
                for key in requirement.target_keys
                if key in target_bindings
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
    "ObjectiveIntent",
    "ObjectiveTarget",
    "ObjectiveTargetCoverage",
    "ObjectiveRequirementCoverage",
    "ResearchObjectiveContract",
    "evaluate_objective_coverage",
]
