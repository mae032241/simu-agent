"""Deterministic curve normalization and comparison schemas."""

from __future__ import annotations

import math
from bisect import bisect_right
from typing import Annotated, Literal

from pydantic import Field, model_validator

from scidiscovery.artifact_agent.schema.common import (
    Identifier,
    SchemaModel,
    Sha256,
    canonical_sha256,
)
from scidiscovery.artifact_agent.schema.units import units_equivalent
from scidiscovery.artifact_agent.schema.experiment import (
    ExperimentPortfolio,
    ExperimentProposal,
    ValidationPlan,
    deterministic_validation_check_keys,
)
from scidiscovery.operation_contract import SemanticRuleViolation


CurveStatus = Literal["available", "unavailable"]
CheckStatus = Literal["pass", "fail", "unavailable"]
AggregateStatus = Literal["pass", "fail", "inconclusive", "unavailable"]
CurveScientificRole = Literal[
    "experimental_target",
    "simulation_candidate",
    "numerical_reference",
    "numerical_variant",
    "analytic_control",
    "diagnostic_series",
]
CurveComparisonPurpose = Literal[
    "unspecified_legacy",
    "target_fit",
    "numerical_convergence",
    "mechanism_separation",
    "implementation_sanity",
    "exploratory_diagnostic",
]
CurveGateScope = Literal[
    "unspecified_legacy",
    "objective",
    "numerical_qualification",
    "mechanism",
    "diagnostic_only",
]
CurveMetricProfile = Literal[
    "unspecified_legacy",
    "point",
    "smooth_curve",
    "sharp_front",
]


class CurveAxis(SchemaModel):
    name: Identifier
    unit: Annotated[str, Field(min_length=1, max_length=128)]
    scale: Literal["linear", "log10"] = "linear"


class CurvePoint(SchemaModel):
    x: Annotated[float, Field(allow_inf_nan=False)]
    y: Annotated[float, Field(allow_inf_nan=False)]


class CurveInterval(SchemaModel):
    start: Annotated[float, Field(allow_inf_nan=False)]
    stop: Annotated[float, Field(allow_inf_nan=False)]

    @model_validator(mode="after")
    def _ordered(self) -> CurveInterval:
        if self.stop <= self.start:
            raise ValueError("curve interval stop must exceed start")
        return self


class CurveAvailability(SchemaModel):
    status: CurveStatus
    reason_code: Identifier | None = None
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    def _reason_matches_status(self) -> CurveAvailability:
        if self.status == "available" and self.reason_code is not None:
            raise ValueError("available curve cannot declare an unavailable reason")
        if self.status == "unavailable" and self.reason_code is None:
            raise ValueError("unavailable curve requires a reason code")
        return self


class CurveSeries(SchemaModel):
    series_key: Identifier
    case_key: Identifier
    role: Identifier
    scientific_role: CurveScientificRole | None = None
    x_axis: CurveAxis
    y_axis: CurveAxis
    points: Annotated[tuple[CurvePoint, ...], Field(max_length=1_000_000)]
    valid_intervals: Annotated[
        tuple[CurveInterval, ...], Field(default=(), max_length=4096)
    ]
    exclusions: Annotated[
        tuple[CurveInterval, ...], Field(default=(), max_length=4096)
    ]
    availability: CurveAvailability
    source_locator: Annotated[str, Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    def _points_and_intervals_are_coherent(self) -> CurveSeries:
        if self.availability.status == "available" and len(self.points) < 2:
            raise ValueError("available curve requires at least two points")
        xs = tuple(item.x for item in self.points)
        if self.x_axis.scale == "log10" and any(item.x <= 0 for item in self.points):
            raise ValueError("log10 x-axis requires positive point values")
        if self.y_axis.scale == "log10" and any(item.y < 0 for item in self.points):
            raise ValueError("log10 y-axis requires nonnegative point values")
        for label, intervals in (
            ("valid", self.valid_intervals),
            ("exclusion", self.exclusions),
        ):
            if any(
                right.start < left.stop
                for left, right in zip(intervals, intervals[1:])
            ):
                raise ValueError(f"curve {label} intervals must not overlap")
            if self.points and any(
                item.start < min(xs) or item.stop > max(xs) for item in intervals
            ):
                raise ValueError(f"curve {label} interval exceeds point domain")
        return self


class CurveSeriesDeclaration(SchemaModel):
    series_key: Identifier
    case_key: Identifier
    role: Identifier
    scientific_role: CurveScientificRole | None = None
    source: Literal["solver_output", "reference_input"] = "solver_output"
    x_axis: CurveAxis
    y_axis: CurveAxis
    min_points: Annotated[int, Field(ge=2, le=1_000_000)] = 2
    max_points: Annotated[int, Field(ge=2, le=1_000_000)] = 1_000_000

    @model_validator(mode="after")
    def _point_bounds_are_ordered(self) -> CurveSeriesDeclaration:
        if self.max_points < self.min_points:
            raise ValueError("curve declaration max_points must not be below min_points")
        return self


class CurveBundle(SchemaModel):
    source_profile: Identifier
    source_digests: Annotated[
        tuple[Sha256, ...], Field(min_length=1, max_length=4096)
    ]
    series: Annotated[tuple[CurveSeries, ...], Field(min_length=1, max_length=10000)]

    @model_validator(mode="after")
    def _series_are_unique(self) -> CurveBundle:
        keys = tuple(item.series_key for item in self.series)
        identities = tuple((item.case_key, item.role) for item in self.series)
        if len(keys) != len(set(keys)):
            raise ValueError("curve bundle series keys must be unique")
        if len(identities) != len(set(identities)):
            raise ValueError("curve bundle case/role identities must be unique")
        if len(self.source_digests) != len(set(self.source_digests)):
            raise ValueError("curve bundle source digests must be unique")
        return self


class CurveDomain(SchemaModel):
    start: Annotated[float, Field(allow_inf_nan=False)]
    stop: Annotated[float, Field(allow_inf_nan=False)]
    unit: Annotated[str, Field(min_length=1, max_length=128)]
    min_points: Annotated[int, Field(ge=2, le=1_000_000)] = 2

    @model_validator(mode="after")
    def _ordered(self) -> CurveDomain:
        if self.stop <= self.start:
            raise ValueError("curve comparison domain stop must exceed start")
        return self


class CurveThreshold(SchemaModel):
    comparison: Literal["le", "ge", "abs_le"]
    value: Annotated[float, Field(allow_inf_nan=False)]
    unit: Annotated[str, Field(min_length=1, max_length=128)]

    @model_validator(mode="after")
    def _absolute_limit_is_nonnegative(self) -> CurveThreshold:
        if self.comparison == "abs_le" and self.value < 0:
            raise ValueError("absolute threshold must be nonnegative")
        return self


class CurveFloorMask(SchemaModel):
    reference_at_or_below: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    candidate_at_or_below: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    unit: Annotated[str, Field(min_length=1, max_length=128)]
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]


class CurveOperatorSpec(SchemaModel):
    operator_key: Identifier
    validation_check_key: Identifier | None = None
    kind: Literal[
        "point_difference",
        "residual_rms",
        "residual_max_abs",
        "mean_signed_difference",
        "crossing_shift",
        "width_shift",
    ]
    value_space: Literal["linear", "log10"] = "linear"
    level: Annotated[float, Field(allow_inf_nan=False)] | None = None
    second_level: Annotated[float, Field(allow_inf_nan=False)] | None = None
    crossing_direction: Literal["increasing", "decreasing", "either"] = "either"
    x: Annotated[float, Field(allow_inf_nan=False)] | None = None
    threshold: CurveThreshold | None = None

    @model_validator(mode="after")
    def _parameters_match_operator(self) -> CurveOperatorSpec:
        needs_level = self.kind in {"crossing_shift", "width_shift"}
        if needs_level != (self.level is not None):
            raise ValueError("crossing and width operators require a level")
        needs_second = self.kind == "width_shift"
        if needs_second != (self.second_level is not None):
            raise ValueError("width operator requires a second level")
        if self.kind in {"crossing_shift", "width_shift"} and self.value_space != "linear":
            raise ValueError("crossing levels are expressed in linear curve values")
        if (
            self.kind == "width_shift"
            and self.level is not None
            and self.second_level == self.level
        ):
            raise ValueError("width levels must differ")
        if (self.kind == "point_difference") != (self.x is not None):
            raise ValueError("point-difference operator requires exactly one x value")
        return self


class CurveComparison(SchemaModel):
    comparison_key: Identifier
    reference_series: Identifier
    candidate_series: Identifier
    domain: CurveDomain
    interpolation: Literal["linear_y", "log10_y"]
    evaluation_points: Annotated[int, Field(ge=2, le=1_000_000)] = 257
    operators: Annotated[
        tuple[CurveOperatorSpec, ...], Field(min_length=1, max_length=256)
    ]
    required: bool = True
    purpose: CurveComparisonPurpose = "unspecified_legacy"
    gate_scope: CurveGateScope = "unspecified_legacy"
    metric_profile: CurveMetricProfile = "unspecified_legacy"
    floor_mask: CurveFloorMask | None = None

    @model_validator(mode="after")
    def _operators_are_unique(self) -> CurveComparison:
        keys = tuple(item.operator_key for item in self.operators)
        if len(keys) != len(set(keys)):
            raise ValueError("curve comparison operator keys must be unique")
        if self.reference_series == self.candidate_series:
            raise ValueError("curve comparison requires distinct series")
        legacy_count = sum(
            (
                self.purpose == "unspecified_legacy",
                self.gate_scope == "unspecified_legacy",
                self.metric_profile == "unspecified_legacy",
            )
        )
        if legacy_count not in {0, 3}:
            raise ValueError(
                "curve purpose, gate scope, and metric profile must be declared together"
            )
        expected_scope = {
            "target_fit": "objective",
            "numerical_convergence": "numerical_qualification",
            "mechanism_separation": "mechanism",
            "implementation_sanity": "numerical_qualification",
            "exploratory_diagnostic": "diagnostic_only",
        }.get(self.purpose)
        if expected_scope is not None and self.gate_scope != expected_scope:
            raise ValueError("curve comparison purpose has an incompatible gate scope")
        if self.purpose == "target_fit" and not self.required:
            raise ValueError("target-fit comparison cannot be optional")
        if self.purpose == "exploratory_diagnostic" and self.required:
            raise ValueError("exploratory diagnostic comparison cannot gate a claim")
        front_operators = tuple(
            item
            for item in self.operators
            if item.kind in {"crossing_shift", "width_shift"}
        )
        if self.metric_profile == "sharp_front" and not front_operators:
            raise ValueError(
                "sharp-front comparison requires a crossing or width operator"
            )
        if (
            self.metric_profile == "sharp_front"
            and self.gate_scope == "numerical_qualification"
            and self.required
            and not any(item.threshold is not None for item in front_operators)
        ):
            raise ValueError(
                "numerical-qualification sharp-front comparison requires a "
                "thresholded crossing or width operator"
            )
        if self.metric_profile == "point" and any(
            item.kind != "point_difference" for item in self.operators
        ):
            raise ValueError("point comparison requires point-difference operators")
        if self.metric_profile == "smooth_curve" and any(
            item.kind
            not in {"residual_rms", "residual_max_abs", "mean_signed_difference"}
            for item in self.operators
        ):
            raise ValueError("smooth-curve comparison requires residual operators")
        return self


class CurveReferenceDisposition(SchemaModel):
    series_key: Identifier
    disposition: Literal["compare", "exclude"]
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]


class CurveComparisonSpec(SchemaModel):
    spec_key: Identifier
    series_declarations: Annotated[
        tuple[CurveSeriesDeclaration, ...], Field(default=(), max_length=10000)
    ]
    comparisons: Annotated[
        tuple[CurveComparison, ...], Field(min_length=1, max_length=10000)
    ]
    reference_dispositions: Annotated[
        tuple[CurveReferenceDisposition, ...], Field(default=(), max_length=10000)
    ] = ()
    aggregate_rule: Literal["all_required"] = "all_required"

    @model_validator(mode="after")
    def _comparisons_are_unique(self) -> CurveComparisonSpec:
        keys = tuple(item.comparison_key for item in self.comparisons)
        if len(keys) != len(set(keys)):
            raise ValueError("curve comparison keys must be unique")
        if not any(item.required for item in self.comparisons):
            raise ValueError("curve comparison spec requires a required comparison")
        series_keys = tuple(item.series_key for item in self.series_declarations)
        identities = tuple(
            (item.case_key, item.role) for item in self.series_declarations
        )
        if len(series_keys) != len(set(series_keys)) or len(identities) != len(
            set(identities)
        ):
            raise ValueError("curve series declarations must be unique")
        if self.series_declarations:
            declared = set(series_keys)
            referenced = {
                value
                for comparison in self.comparisons
                for value in (
                    comparison.reference_series,
                    comparison.candidate_series,
                )
            }
            if not referenced.issubset(declared):
                raise ValueError("curve comparison references an undeclared series")
            declarations = {
                item.series_key: item for item in self.series_declarations
            }
            for comparison in self.comparisons:
                if comparison.purpose == "unspecified_legacy":
                    continue
                reference_role = declarations[
                    comparison.reference_series
                ].scientific_role
                candidate_role = declarations[
                    comparison.candidate_series
                ].scientific_role
                if reference_role is None or candidate_role is None:
                    raise ValueError(
                        "purpose-aware comparison requires scientific series roles"
                    )
                allowed_roles = {
                    "target_fit": (
                        {"experimental_target"},
                        {"simulation_candidate"},
                    ),
                    "numerical_convergence": (
                        {"numerical_reference", "simulation_candidate"},
                        {"numerical_variant", "simulation_candidate"},
                    ),
                    "mechanism_separation": (
                        {"analytic_control", "simulation_candidate"},
                        {"simulation_candidate"},
                    ),
                    "implementation_sanity": (
                        {
                            "diagnostic_series",
                            "numerical_reference",
                            "simulation_candidate",
                        },
                        {"diagnostic_series", "numerical_variant"},
                    ),
                    "exploratory_diagnostic": (
                        {
                            "experimental_target",
                            "simulation_candidate",
                            "numerical_reference",
                            "numerical_variant",
                            "analytic_control",
                            "diagnostic_series",
                        },
                        {
                            "experimental_target",
                            "simulation_candidate",
                            "numerical_reference",
                            "numerical_variant",
                            "analytic_control",
                            "diagnostic_series",
                        },
                    ),
                }[comparison.purpose]
                if (
                    reference_role not in allowed_roles[0]
                    or candidate_role not in allowed_roles[1]
                ):
                    raise ValueError(
                        "curve comparison series roles are incompatible with its purpose"
                    )
                if comparison.purpose == "target_fit" and (
                    declarations[comparison.reference_series].source
                    != "reference_input"
                    or declarations[comparison.candidate_series].source
                    != "solver_output"
                ):
                    raise ValueError(
                        "target-fit comparison requires external target and solver candidate"
                    )
        disposition_keys = tuple(
            item.series_key for item in self.reference_dispositions
        )
        if len(disposition_keys) != len(set(disposition_keys)):
            raise ValueError("curve reference dispositions must be unique")
        compared_references = {
            item.reference_series for item in self.comparisons
        }
        declared_references = {
            item.series_key
            for item in self.series_declarations
            if item.source == "reference_input"
        }
        if not declared_references.issubset(compared_references):
            raise ValueError(
                "every reference_input declaration must be used by a comparison"
            )
        compare_dispositions = {
            item.series_key
            for item in self.reference_dispositions
            if item.disposition == "compare"
        }
        excluded = {
            item.series_key
            for item in self.reference_dispositions
            if item.disposition == "exclude"
        }
        if compare_dispositions and compare_dispositions != declared_references:
            raise ValueError(
                "compare dispositions must cover the exact comparison references"
            )
        if excluded & compared_references:
            raise ValueError("a compared reference series cannot be excluded")
        return self


class CurveObjectiveTargetBinding(SchemaModel):
    target_key: Identifier
    reference_series_key: Identifier
    required_domains: Annotated[
        tuple[CurveDomain, ...], Field(min_length=1, max_length=64)
    ]

    @model_validator(mode="after")
    def _domains_are_unique(self) -> CurveObjectiveTargetBinding:
        values = tuple(
            (item.start, item.stop, item.unit, item.min_points)
            for item in self.required_domains
        )
        if len(values) != len(set(values)):
            raise ValueError("curve objective binding domains must be unique")
        return self


class CurveExperimentContract(SchemaModel):
    """Curve-domain realization bound to one generic experiment proposal."""

    experiment_key: Identifier
    comparison_spec: CurveComparisonSpec
    objective_target_bindings: Annotated[
        tuple[CurveObjectiveTargetBinding, ...], Field(max_length=128)
    ] = ()

    @model_validator(mode="after")
    def _objective_bindings_are_unique(self) -> CurveExperimentContract:
        keys = tuple(item.target_key for item in self.objective_target_bindings)
        if len(keys) != len(set(keys)):
            raise ValueError("curve objective target bindings must be unique")
        declared = {item.series_key for item in self.comparison_spec.series_declarations}
        if not {
            item.reference_series_key for item in self.objective_target_bindings
        }.issubset(declared):
            raise ValueError("curve objective binding references an undeclared series")
        return self


def validate_curve_experiment_contract(
    contract: CurveExperimentContract,
    portfolio: ExperimentPortfolio,
    *,
    expected_evaluator_profile: str | None = None,
) -> tuple[Identifier, ...]:
    """Validate a curve realization against an immutable generic plan."""

    proposals = tuple(
        item
        for item in portfolio.proposals
        if item.experiment_key == contract.experiment_key
    )
    plans = tuple(
        item
        for item in portfolio.validation_plans
        if item.experiment_key == contract.experiment_key
    )
    if len(proposals) != 1 or len(plans) != 1:
        raise SemanticRuleViolation(
            "curve contract must name one exact experiment proposal and validation plan"
        )
    proposal = proposals[0]
    plan = plans[0]
    spec = contract.comparison_spec
    validate_curve_comparison_declaration_contract(spec)
    _validate_curve_cases(spec, proposal)
    _validate_curve_check_bindings(
        spec,
        plan,
        expected_evaluator_profile=expected_evaluator_profile,
    )
    return deterministic_validation_check_keys(plan)


def _validate_curve_cases(
    spec: CurveComparisonSpec,
    proposal: ExperimentProposal,
) -> None:
    cases = {item.case_key: item for item in proposal.cases}
    declarations = {item.series_key: item for item in spec.series_declarations}
    for declaration in spec.series_declarations:
        if declaration.source == "solver_output" and declaration.case_key not in cases:
            raise SemanticRuleViolation("curve solver series names an undeclared experiment case")
    for comparison in spec.comparisons:
        if comparison.purpose != "target_fit":
            continue
        candidate = declarations[comparison.candidate_series]
        candidate_case = cases.get(candidate.case_key)
        if candidate_case is None:
            raise SemanticRuleViolation(
                "target-fit solver candidate must name a declared experiment case"
            )
        if candidate_case.scientific_role == "convergence":
            raise SemanticRuleViolation("target-fit candidate cannot use a convergence-only case")
        generic = proposal.comparison_contract
        if generic is None:
            raise SemanticRuleViolation("target-fit candidate requires a comparison contract")
        for variable in generic.variables:
            if variable.factor_type not in {"numerical", "implementation"}:
                continue
            expected = {item.case_key: item.value for item in variable.expectations}
            baseline = expected[generic.baseline_case_key]
            candidate_value = expected[candidate.case_key]
            if type(candidate_value) is not type(baseline) or candidate_value != baseline:
                raise SemanticRuleViolation(
                    "target-fit candidate must preserve baseline numerical and "
                    f"implementation factors: {variable.variable_key}"
                )


def _validate_curve_check_bindings(
    spec: CurveComparisonSpec,
    plan: ValidationPlan,
    *,
    expected_evaluator_profile: str | None,
) -> None:
    checks = {
        check.check_key: check
        for dimension in (plan.numerical, plan.physical, plan.experimental)
        for check in dimension.checks
        if check.evaluation_mode == "deterministic_threshold"
    }
    bound: dict[str, CurveOperatorSpec] = {}
    for comparison in spec.comparisons:
        bound_in_comparison = 0
        for operator in comparison.operators:
            key = operator.validation_check_key
            if operator.threshold is not None and key is None:
                raise SemanticRuleViolation(
                    "thresholded curve operator requires validation_check_key"
                )
            if key is not None and operator.threshold is None:
                raise SemanticRuleViolation(
                    "curve validation_check_key requires an operator threshold"
                )
            if key is None:
                continue
            if key in bound:
                raise SemanticRuleViolation(
                    "each deterministic validation check must bind one curve operator"
                )
            bound[key] = operator
            bound_in_comparison += 1
        if (
            comparison.required
            and comparison.gate_scope == "numerical_qualification"
            and bound_in_comparison == 0
        ):
            raise SemanticRuleViolation(
                "required numerical-qualification curve comparison needs a "
                "thresholded validation-check binding"
            )
    if set(bound) != set(checks):
        raise SemanticRuleViolation(
            "curve contract must cover the exact deterministic validation checks; "
            f"missing={sorted(set(checks) - set(bound))}, "
            f"unexpected={sorted(set(bound) - set(checks))}"
        )
    for key, operator in bound.items():
        check = checks[key]
        threshold = operator.threshold
        planned = check.threshold
        assert threshold is not None and planned is not None
        if check.evaluator_metric != operator.kind:
            raise SemanticRuleViolation(
                f"curve operator kind does not match validation evaluator for {key}"
            )
        if (
            expected_evaluator_profile is not None
            and check.evaluator_profile != expected_evaluator_profile
        ):
            raise SemanticRuleViolation(
                f"validation check requires a different curve evaluator for {key}"
            )
        expected_operator = (
            "le" if threshold.comparison == "abs_le" else threshold.comparison
        )
        if (
            planned.operator != expected_operator
            or planned.value != threshold.value
            or planned.upper_value is not None
            or planned.unit != threshold.unit
        ):
            raise SemanticRuleViolation(
                f"curve operator threshold does not match validation check {key}"
            )


def validate_curve_comparison_declaration_contract(
    spec: CurveComparisonSpec,
) -> None:
    """Validate derived metric units without invalidating stored v1 payload parsing."""

    if not spec.series_declarations:
        return
    declarations = {item.series_key: item for item in spec.series_declarations}
    for comparison in spec.comparisons:
        reference = declarations[comparison.reference_series]
        candidate = declarations[comparison.candidate_series]
        if (
            not curve_units_equivalent(
                reference.x_axis.unit, comparison.domain.unit
            )
            or not curve_units_equivalent(
                candidate.x_axis.unit, comparison.domain.unit
            )
            or not curve_units_equivalent(
                reference.y_axis.unit, candidate.y_axis.unit
            )
        ):
            raise SemanticRuleViolation(
                "curve comparison declaration units differ from its domain"
            )
        for operator in comparison.operators:
            if operator.threshold is None:
                continue
            expected_unit = (
                comparison.domain.unit
                if operator.kind in {"crossing_shift", "width_shift"}
                else "decade"
                if operator.value_space == "log10"
                else reference.y_axis.unit
            )
            if not curve_units_equivalent(operator.threshold.unit, expected_unit):
                raise SemanticRuleViolation(
                    "curve operator threshold unit differs from its metric unit"
                )
        if comparison.floor_mask is not None and not curve_units_equivalent(
            comparison.floor_mask.unit, reference.y_axis.unit
        ):
            raise SemanticRuleViolation("curve floor mask unit differs from its series")


def curve_units_equivalent(left: str, right: str) -> bool:
    """Return whether curve-unit labels have identical numeric semantics.

    Exact unknown labels remain compatible with themselves for backward
    compatibility. Known aliases such as ``µm`` and ``um`` compare through the
    shared registry; different scales or dimensions remain incompatible.
    """

    if left == right:
        return True
    try:
        return units_equivalent(left, right)
    except ValueError:
        return False


class CurveReferenceCoverageBundle(SchemaModel):
    source_name: Identifier
    source_profile: Identifier
    bundle_sha256: Sha256
    series_keys: Annotated[tuple[Identifier, ...], Field(min_length=1, max_length=10000)]


class CurveReferenceOperatorSupport(SchemaModel):
    comparison_key: Identifier
    operator_key: Identifier
    series_key: Identifier
    status: Literal["pass", "fail"]
    level_crossing_count: Annotated[int, Field(ge=0, le=1_000_000)] | None = None
    second_level_crossing_count: Annotated[
        int, Field(ge=0, le=1_000_000)
    ] | None = None
    level_crossings: Annotated[tuple[float, ...], Field(max_length=1_000_000)] | None = None
    second_level_crossings: Annotated[
        tuple[float, ...], Field(max_length=1_000_000)
    ] | None = None
    reason_code: Identifier | None = None

    @model_validator(mode="after")
    def _status_matches_counts(self) -> CurveReferenceOperatorSupport:
        for count, locations in (
            (self.level_crossing_count, self.level_crossings),
            (self.second_level_crossing_count, self.second_level_crossings),
        ):
            if locations is not None:
                if any(not math.isfinite(value) for value in locations):
                    raise ValueError("reference crossings must be finite")
                if count != len(locations):
                    raise ValueError("reference crossing count must match locations")
        counts = tuple(
            value
            for value in (
                self.level_crossing_count,
                self.second_level_crossing_count,
            )
            if value is not None
        )
        passed = bool(counts) and all(value == 1 for value in counts)
        if self.status == "pass":
            if not passed or self.reason_code is not None:
                raise ValueError("passing reference operator support requires unique crossings")
        elif passed or self.reason_code is None:
            raise ValueError("failed reference operator support requires a reason")
        return self


class CurveReferenceComparisonSupport(SchemaModel):
    comparison_key: Identifier
    reference_series: Identifier
    status: Literal["pass", "fail"]
    domain_reason_code: Identifier | None = None
    operators: Annotated[
        tuple[CurveReferenceOperatorSupport, ...], Field(max_length=256)
    ] = ()

    @model_validator(mode="after")
    def _status_matches_support(self) -> CurveReferenceComparisonSupport:
        failed = self.domain_reason_code is not None or any(
            item.status == "fail" for item in self.operators
        )
        if (self.status == "fail") != failed:
            raise ValueError("reference comparison support status is inconsistent")
        return self


class CurveReferenceCoverageReport(SchemaModel):
    schema_version: Literal["scidiscovery.curve-reference-coverage.v1"]
    status: Literal["pass", "fail"]
    experiment_plan_sha256: Sha256
    comparison_spec_sha256: Sha256
    bundles: Annotated[
        tuple[CurveReferenceCoverageBundle, ...], Field(min_length=1, max_length=4096)
    ]
    required_reference_series: Annotated[
        tuple[Identifier, ...], Field(max_length=10000)
    ] = ()
    mapped_reference_series: Annotated[
        tuple[Identifier, ...], Field(max_length=10000)
    ] = ()
    excluded_reference_series: Annotated[
        tuple[Identifier, ...], Field(max_length=10000)
    ] = ()
    missing_declared_reference_series: Annotated[
        tuple[Identifier, ...], Field(max_length=10000)
    ] = ()
    unmapped_bundle_series: Annotated[
        tuple[Identifier, ...], Field(max_length=10000)
    ] = ()
    unknown_disposition_series: Annotated[
        tuple[Identifier, ...], Field(max_length=10000)
    ] = ()
    declaration_mismatch_series: Annotated[
        tuple[Identifier, ...], Field(max_length=10000)
    ] = ()
    comparison_support: Annotated[
        tuple[CurveReferenceComparisonSupport, ...], Field(max_length=10000)
    ] = ()

    @model_validator(mode="after")
    def _status_matches_coverage(self) -> CurveReferenceCoverageReport:
        failed = bool(
            self.missing_declared_reference_series
            or self.unmapped_bundle_series
            or self.unknown_disposition_series
            or self.declaration_mismatch_series
            or any(item.status == "fail" for item in self.comparison_support)
            or set(self.required_reference_series)
            != set(self.mapped_reference_series)
        )
        if (self.status == "fail") != failed:
            raise ValueError("curve reference coverage status is inconsistent")
        for values in (
            self.required_reference_series,
            self.mapped_reference_series,
            self.excluded_reference_series,
            self.missing_declared_reference_series,
            self.unmapped_bundle_series,
            self.unknown_disposition_series,
            self.declaration_mismatch_series,
        ):
            if len(values) != len(set(values)):
                raise ValueError("curve reference coverage series must be unique")
        return self


class CurveMetricCrossingSupport(SchemaModel):
    series_side: Literal["reference", "candidate"]
    level_role: Literal["level", "second_level"]
    level: Annotated[float, Field(allow_inf_nan=False)]
    locations: Annotated[tuple[float, ...], Field(max_length=1_000_000)]

    @model_validator(mode="after")
    def _locations_are_finite(self) -> CurveMetricCrossingSupport:
        if any(not math.isfinite(value) for value in self.locations):
            raise ValueError("metric crossing locations must be finite")
        return self


class CurveMetricResult(SchemaModel):
    comparison_key: Identifier
    operator_key: Identifier
    kind: Literal[
        "point_difference",
        "residual_rms",
        "residual_max_abs",
        "mean_signed_difference",
        "crossing_shift",
        "width_shift",
    ]
    status: CurveStatus
    value: float | None = None
    unit: Annotated[str, Field(min_length=1, max_length=128)]
    reason_code: Identifier | None = None
    crossing_support: Annotated[
        tuple[CurveMetricCrossingSupport, ...], Field(max_length=4)
    ] = ()
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    def _value_matches_status(self) -> CurveMetricResult:
        if self.status == "available":
            if self.value is None or self.reason_code is not None:
                raise ValueError("available metric requires only a finite value")
        elif self.value is not None or self.reason_code is None:
            raise ValueError("unavailable metric requires only a reason code")
        return self


class CurveThresholdResult(SchemaModel):
    comparison_key: Identifier
    operator_key: Identifier
    status: CheckStatus
    observed_value: float | None = None
    threshold: CurveThreshold
    reason_code: Identifier | None = None

    @model_validator(mode="after")
    def _observed_matches_status(self) -> CurveThresholdResult:
        if self.status in {"pass", "fail"}:
            if self.observed_value is None or self.reason_code is not None:
                raise ValueError("evaluated threshold requires an observed value")
        elif self.observed_value is not None or self.reason_code is None:
            raise ValueError("unavailable threshold requires a reason code")
        return self


class CurveComparisonResult(SchemaModel):
    comparison_key: Identifier
    required: bool
    purpose: CurveComparisonPurpose = "unspecified_legacy"
    gate_scope: CurveGateScope = "unspecified_legacy"
    metric_profile: CurveMetricProfile = "unspecified_legacy"
    status: AggregateStatus
    metrics: Annotated[
        tuple[CurveMetricResult, ...], Field(min_length=1, max_length=256)
    ]
    checks: Annotated[tuple[CurveThresholdResult, ...], Field(max_length=256)]
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    def _status_is_derived(self) -> CurveComparisonResult:
        legacy_fields = (
            self.purpose == "unspecified_legacy",
            self.gate_scope == "unspecified_legacy",
            self.metric_profile == "unspecified_legacy",
        )
        if any(legacy_fields) and not all(legacy_fields):
            raise ValueError(
                "curve comparison result scope fields must be declared together"
            )
        check_statuses = {item.status for item in self.checks}
        metric_statuses = {item.status for item in self.metrics}
        derived: AggregateStatus
        if "fail" in check_statuses:
            derived = "fail"
        elif "unavailable" in check_statuses or "unavailable" in metric_statuses:
            derived = "unavailable"
        elif not self.checks:
            derived = "inconclusive"
        else:
            derived = "pass"
        if self.status != derived:
            raise ValueError("curve comparison status does not match metrics and checks")
        return self


class CurveConsistencyReport(SchemaModel):
    curve_bundle_sha256: Sha256
    comparison_spec_sha256: Sha256
    normalizer_profile: Identifier
    operator_version: Identifier
    comparisons: Annotated[
        tuple[CurveComparisonResult, ...], Field(min_length=1, max_length=10000)
    ]
    aggregate_status: AggregateStatus
    validation_scope: Literal["standalone", "complete_plan"] = "standalone"
    validation_plan_sha256: Sha256 | None = None
    covered_validation_check_keys: Annotated[
        tuple[Identifier, ...], Field(max_length=384)
    ] = ()
    interpretation_boundary: Literal[
        "deterministic_metrics_only_no_physical_interpretation"
    ] = "deterministic_metrics_only_no_physical_interpretation"

    @model_validator(mode="after")
    def _aggregate_is_derived(self) -> CurveConsistencyReport:
        statuses = {item.status for item in self.comparisons if item.required}
        derived: AggregateStatus = (
            "fail"
            if "fail" in statuses
            else "inconclusive"
            if "inconclusive" in statuses
            else "unavailable"
            if "unavailable" in statuses
            else "pass"
        )
        if self.aggregate_status != derived:
            raise ValueError("curve report aggregate status is not derived")
        keys = self.covered_validation_check_keys
        if len(keys) != len(set(keys)):
            raise ValueError("covered validation check keys must be unique")
        if self.validation_scope == "standalone":
            if self.validation_plan_sha256 is not None or keys:
                raise ValueError(
                    "standalone curve report cannot claim validation-plan coverage"
                )
        elif self.validation_plan_sha256 is None:
            raise ValueError(
                "complete-plan curve report requires a plan digest"
            )
        return self


def evaluate_curve_consistency(
    bundle: CurveBundle,
    spec: CurveComparisonSpec,
    *,
    operator_version: str = "curve-operators.v1",
    validation_plan_sha256: str | None = None,
    covered_validation_check_keys: tuple[str, ...] = (),
) -> CurveConsistencyReport:
    """Evaluate a declarative curve comparison without physical interpretation."""

    by_key = {item.series_key: item for item in bundle.series}
    results: list[CurveComparisonResult] = []
    for comparison in spec.comparisons:
        reference = by_key.get(comparison.reference_series)
        candidate = by_key.get(comparison.candidate_series)
        if reference is None or candidate is None:
            results.append(_unavailable_comparison(comparison, "series_missing"))
            continue
        reason = _comparison_unavailable_reason(reference, candidate, comparison)
        if reason is not None:
            results.append(_unavailable_comparison(comparison, reason))
            continue
        metrics = tuple(
            _evaluate_operator(reference, candidate, comparison, operator)
            for operator in comparison.operators
        )
        checks = tuple(
            _evaluate_threshold(metric, operator.threshold)
            for metric, operator in zip(metrics, comparison.operators, strict=True)
            if operator.threshold is not None
        )
        check_statuses = {item.status for item in checks}
        metric_statuses = {item.status for item in metrics}
        status: AggregateStatus = (
            "fail"
            if "fail" in check_statuses
            else "unavailable"
            if "unavailable" in check_statuses or "unavailable" in metric_statuses
            else "inconclusive"
            if not checks
            else "pass"
        )
        results.append(
            CurveComparisonResult(
                comparison_key=comparison.comparison_key,
                required=comparison.required,
                purpose=comparison.purpose,
                gate_scope=comparison.gate_scope,
                metric_profile=comparison.metric_profile,
                status=status,
                metrics=metrics,
                checks=checks,
                rationale=(
                    "All available deterministic curve checks passed."
                    if status == "pass"
                    else "One or more deterministic curve checks failed."
                    if status == "fail"
                    else "Metrics are available but no thresholded check was declared."
                    if status == "inconclusive"
                    else "Required curve support is unavailable."
                ),
            )
        )
    required_statuses = {
        result.status
        for result, comparison in zip(results, spec.comparisons, strict=True)
        if comparison.required
    }
    aggregate: AggregateStatus = (
        "fail"
        if "fail" in required_statuses
        else "inconclusive"
        if "inconclusive" in required_statuses
        else "unavailable"
        if "unavailable" in required_statuses
        else "pass"
    )
    return CurveConsistencyReport(
        curve_bundle_sha256=canonical_sha256(bundle),
        comparison_spec_sha256=canonical_sha256(spec),
        normalizer_profile=bundle.source_profile,
        operator_version=operator_version,
        comparisons=tuple(results),
        aggregate_status=aggregate,
        validation_scope=(
            "complete_plan" if validation_plan_sha256 is not None else "standalone"
        ),
        validation_plan_sha256=validation_plan_sha256,
        covered_validation_check_keys=covered_validation_check_keys,
    )


def _comparison_unavailable_reason(
    reference: CurveSeries,
    candidate: CurveSeries,
    comparison: CurveComparison,
) -> str | None:
    if reference.availability.status != "available":
        return "reference_unavailable"
    if candidate.availability.status != "available":
        return "candidate_unavailable"
    if (
        not curve_units_equivalent(reference.x_axis.unit, candidate.x_axis.unit)
        or not curve_units_equivalent(
            reference.x_axis.unit, comparison.domain.unit
        )
        or not curve_units_equivalent(reference.y_axis.unit, candidate.y_axis.unit)
    ):
        return "unit_mismatch"
    for series in (reference, candidate):
        reason = curve_series_domain_reason(series, comparison.domain)
        if reason is not None:
            return reason
    return None


def curve_series_domain_reason(
    series: CurveSeries,
    domain: CurveDomain,
) -> str | None:
    """Return the exact fail-closed reason for one series/domain contract."""

    if series.availability.status != "available":
        return "series_unavailable"
    in_domain = [
        item for item in series.points if domain.start <= item.x <= domain.stop
    ]
    if len(in_domain) < domain.min_points:
        return "insufficient_points"
    if domain.start < min(item.x for item in series.points) or domain.stop > max(
        item.x for item in series.points
    ):
        return "domain_not_covered"
    if series.valid_intervals and not any(
        interval.start <= domain.start and interval.stop >= domain.stop
        for interval in series.valid_intervals
    ):
        return "continuous_domain_unavailable"
    if any(
        interval.start < domain.stop and interval.stop > domain.start
        for interval in series.exclusions
    ):
        return "domain_excluded"
    return None


def _floor_masked(
    reference_value: float,
    candidate_value: float,
    comparison: CurveComparison,
) -> bool:
    floor = comparison.floor_mask
    return floor is not None and (
        reference_value <= floor.reference_at_or_below
        or candidate_value <= floor.candidate_at_or_below
    )


def _evaluate_operator(
    reference: CurveSeries,
    candidate: CurveSeries,
    comparison: CurveComparison,
    operator: CurveOperatorSpec,
) -> CurveMetricResult:
    crossing_support: list[CurveMetricCrossingSupport] = []
    try:
        if operator.kind == "point_difference":
            assert operator.x is not None
            if not comparison.domain.start <= operator.x <= comparison.domain.stop:
                raise ValueError("point_outside_domain")
            reference_value = _raw_value_at(
                reference, operator.x, comparison.interpolation
            )
            candidate_value = _raw_value_at(
                candidate, operator.x, comparison.interpolation
            )
            if _floor_masked(reference_value, candidate_value, comparison):
                raise ValueError("point_floor_masked")
            if operator.value_space == "log10":
                if reference_value <= 0 or candidate_value <= 0:
                    raise ValueError("log_metric_nonpositive")
                value = math.log10(candidate_value) - math.log10(reference_value)
                unit = "decade"
            else:
                value = candidate_value - reference_value
                unit = reference.y_axis.unit
        elif operator.kind in {
            "residual_rms",
            "residual_max_abs",
            "mean_signed_difference",
        }:
            step = (
                comparison.domain.stop - comparison.domain.start
            ) / (comparison.evaluation_points - 1)
            xs = tuple(
                comparison.domain.stop
                if index == comparison.evaluation_points - 1
                else comparison.domain.start + step * index
                for index in range(comparison.evaluation_points)
            )
            residuals = []
            for x in xs:
                try:
                    reference_value = _raw_value_at(
                        reference, x, comparison.interpolation
                    )
                    candidate_value = _raw_value_at(
                        candidate, x, comparison.interpolation
                    )
                except ValueError:
                    # A repeated-x interface or another unsupported interpolation
                    # location is visible source evidence, but it is not an eligible
                    # numerical residual sample.
                    continue
                if _floor_masked(reference_value, candidate_value, comparison):
                    continue
                if operator.value_space == "log10":
                    if reference_value <= 0 or candidate_value <= 0:
                        continue
                    residuals.append(
                        math.log10(candidate_value) - math.log10(reference_value)
                    )
                else:
                    residuals.append(candidate_value - reference_value)
            if len(residuals) < comparison.domain.min_points:
                raise ValueError(
                    "insufficient_positive_support"
                    if operator.value_space == "log10"
                    else "insufficient_eligible_support"
                )
            value = (
                math.sqrt(sum(item * item for item in residuals) / len(residuals))
                if operator.kind == "residual_rms"
                else max(abs(item) for item in residuals)
                if operator.kind == "residual_max_abs"
                else sum(residuals) / len(residuals)
            )
            unit = "decade" if operator.value_space == "log10" else reference.y_axis.unit
        elif operator.kind == "crossing_shift":
            assert operator.level is not None
            reference_locations = curve_crossings(
                reference,
                operator.level,
                operator.crossing_direction,
                comparison.domain,
                comparison.interpolation,
            )
            candidate_locations = curve_crossings(
                candidate,
                operator.level,
                operator.crossing_direction,
                comparison.domain,
                comparison.interpolation,
            )
            crossing_support.extend(
                (
                    CurveMetricCrossingSupport(
                        series_side="reference",
                        level_role="level",
                        level=operator.level,
                        locations=reference_locations,
                    ),
                    CurveMetricCrossingSupport(
                        series_side="candidate",
                        level_role="level",
                        level=operator.level,
                        locations=candidate_locations,
                    ),
                )
            )
            reference_crossing = _require_unique_crossing(
                reference_locations, "reference_level"
            )
            candidate_crossing = _require_unique_crossing(
                candidate_locations, "candidate_level"
            )
            value = candidate_crossing - reference_crossing
            unit = comparison.domain.unit
        else:
            assert operator.level is not None and operator.second_level is not None
            reference_level_locations = curve_crossings(
                reference,
                operator.level,
                operator.crossing_direction,
                comparison.domain,
                comparison.interpolation,
            )
            reference_second_locations = curve_crossings(
                reference,
                operator.second_level,
                operator.crossing_direction,
                comparison.domain,
                comparison.interpolation,
            )
            candidate_level_locations = curve_crossings(
                candidate,
                operator.level,
                operator.crossing_direction,
                comparison.domain,
                comparison.interpolation,
            )
            candidate_second_locations = curve_crossings(
                candidate,
                operator.second_level,
                operator.crossing_direction,
                comparison.domain,
                comparison.interpolation,
            )
            crossing_support.extend(
                (
                    CurveMetricCrossingSupport(
                        series_side="reference",
                        level_role="level",
                        level=operator.level,
                        locations=reference_level_locations,
                    ),
                    CurveMetricCrossingSupport(
                        series_side="reference",
                        level_role="second_level",
                        level=operator.second_level,
                        locations=reference_second_locations,
                    ),
                    CurveMetricCrossingSupport(
                        series_side="candidate",
                        level_role="level",
                        level=operator.level,
                        locations=candidate_level_locations,
                    ),
                    CurveMetricCrossingSupport(
                        series_side="candidate",
                        level_role="second_level",
                        level=operator.second_level,
                        locations=candidate_second_locations,
                    ),
                )
            )
            reference_width = abs(
                _require_unique_crossing(
                    reference_level_locations,
                    "reference_level",
                )
                - _require_unique_crossing(
                    reference_second_locations,
                    "reference_second_level",
                )
            )
            candidate_width = abs(
                _require_unique_crossing(
                    candidate_level_locations,
                    "candidate_level",
                )
                - _require_unique_crossing(
                    candidate_second_locations,
                    "candidate_second_level",
                )
            )
            value = candidate_width - reference_width
            unit = comparison.domain.unit
        if not math.isfinite(value):
            raise ValueError("metric_nonfinite")
        return CurveMetricResult(
            comparison_key=comparison.comparison_key,
            operator_key=operator.operator_key,
            kind=operator.kind,
            status="available",
            value=value,
            unit=unit,
            crossing_support=tuple(crossing_support),
            rationale="The metric was computed from the declared continuous domain.",
        )
    except ValueError as error:
        return CurveMetricResult(
            comparison_key=comparison.comparison_key,
            operator_key=operator.operator_key,
            kind=operator.kind,
            status="unavailable",
            unit=(
                comparison.domain.unit
                if operator.kind in {"crossing_shift", "width_shift"}
                else "decade"
                if operator.value_space == "log10"
                else reference.y_axis.unit
            ),
            reason_code=str(error),
            crossing_support=tuple(crossing_support),
            rationale="The declared metric could not be evaluated without inference.",
        )


def _value_at(
    series: CurveSeries,
    x: float,
    interpolation: Literal["linear_y", "log10_y"],
    value_space: Literal["linear", "log10"],
) -> float:
    y = _raw_value_at(series, x, interpolation)
    if value_space == "log10":
        if y <= 0:
            raise ValueError("log_metric_nonpositive")
        return math.log10(y)
    return y


def _raw_value_at(
    series: CurveSeries,
    x: float,
    interpolation: Literal["linear_y", "log10_y"],
) -> float:
    """Interpolate raw values while preserving exact-zero support for diagnostics."""

    indexed = sorted(enumerate(series.points), key=lambda item: (item[1].x, item[0]))
    points = [item for _, item in indexed]
    xs = [item.x for item in points]
    if x < xs[0] or x > xs[-1]:
        raise ValueError("interpolation_outside_domain")
    left_exact = bisect_right(xs, x) - 1
    if left_exact >= 0 and xs[left_exact] == x:
        first = left_exact
        while first > 0 and xs[first - 1] == x:
            first -= 1
        if left_exact != first:
            raise ValueError("duplicate_x_masked")
        return points[first].y

    index = bisect_right(xs, x)
    if index == 0 or index == len(xs):
        raise ValueError("interpolation_outside_domain")
    left_index = index - 1
    while left_index + 1 < len(xs) and xs[left_index + 1] == xs[left_index]:
        left_index += 1
    right_index = index
    while right_index > 0 and xs[right_index - 1] == xs[right_index]:
        right_index -= 1
    left = points[left_index]
    right = points[right_index]
    if right.x <= left.x:
        raise ValueError("duplicate_x_masked")
    fraction = (x - left.x) / (right.x - left.x)
    if interpolation == "linear_y":
        return left.y + fraction * (right.y - left.y)
    if left.y > 0 and right.y > 0:
        try:
            return 10.0 ** (
                math.log10(left.y)
                + fraction * (math.log10(right.y) - math.log10(left.y))
            )
        except OverflowError as error:
            raise ValueError("log_interpolation_overflow") from error
    if left.y == 0 and right.y == 0:
        return 0.0
    raise ValueError("log_interpolation_nonpositive")


def _single_crossing(
    series: CurveSeries,
    level: float,
    direction: Literal["increasing", "decreasing", "either"],
    domain: CurveDomain,
    interpolation: Literal["linear_y", "log10_y"],
    *,
    reason_prefix: str = "curve",
) -> float:
    crossings = curve_crossings(
        series,
        level,
        direction,
        domain,
        interpolation,
    )
    return _require_unique_crossing(crossings, reason_prefix)


def curve_crossings(
    series: CurveSeries,
    level: float,
    direction: Literal["increasing", "decreasing", "either"],
    domain: CurveDomain,
    interpolation: Literal["linear_y", "log10_y"],
) -> tuple[float, ...]:
    """Return every supported crossing without choosing, pairing, or repairing."""

    return _crossing_locations(series, level, direction, domain, interpolation)


def _require_unique_crossing(
    crossings: tuple[float, ...],
    reason_prefix: str,
) -> float:
    if len(crossings) != 1:
        raise ValueError(f"{reason_prefix}_crossing_count_{len(crossings)}")
    return crossings[0]


def _crossing_locations(
    series: CurveSeries,
    level: float,
    direction: Literal["increasing", "decreasing", "either"],
    domain: CurveDomain,
    interpolation: Literal["linear_y", "log10_y"],
) -> tuple[float, ...]:
    crossings: list[float] = []
    interior = sorted(
        (item for item in series.points if domain.start < item.x < domain.stop),
        key=lambda item: item.x,
    )
    points = [
        CurvePoint(
            x=domain.start,
            y=_value_at(series, domain.start, interpolation, "linear"),
        ),
        *interior,
        CurvePoint(
            x=domain.stop,
            y=_value_at(series, domain.stop, interpolation, "linear"),
        ),
    ]
    for left, right in zip(points, points[1:]):
        if right.x == left.x:
            # Preserve the interface observations, but never manufacture a
            # crossing from a vertical repeated-x seam.
            continue
        delta = right.y - left.y
        if delta == 0:
            continue
        if direction == "increasing" and delta <= 0:
            continue
        if direction == "decreasing" and delta >= 0:
            continue
        if (left.y - level) * (right.y - level) > 0:
            continue
        if interpolation == "log10_y":
            if left.y <= 0 or right.y <= 0 or level <= 0:
                raise ValueError("log_crossing_nonpositive")
            fraction = (math.log10(level) - math.log10(left.y)) / (
                math.log10(right.y) - math.log10(left.y)
            )
        else:
            fraction = (level - left.y) / delta
        if 0.0 <= fraction <= 1.0:
            location = left.x + fraction * (right.x - left.x)
            if not crossings or location != crossings[-1]:
                crossings.append(location)
    return tuple(crossings)


def _evaluate_threshold(
    metric: CurveMetricResult,
    threshold: CurveThreshold | None,
) -> CurveThresholdResult:
    assert threshold is not None
    if metric.status != "available":
        return CurveThresholdResult(
            comparison_key=metric.comparison_key,
            operator_key=metric.operator_key,
            status="unavailable",
            threshold=threshold,
            reason_code=metric.reason_code,
        )
    assert metric.value is not None
    if not curve_units_equivalent(metric.unit, threshold.unit):
        return CurveThresholdResult(
            comparison_key=metric.comparison_key,
            operator_key=metric.operator_key,
            status="unavailable",
            threshold=threshold,
            reason_code="threshold_unit_mismatch",
        )
    passed = (
        metric.value <= threshold.value
        if threshold.comparison == "le"
        else metric.value >= threshold.value
        if threshold.comparison == "ge"
        else abs(metric.value) <= threshold.value
    )
    return CurveThresholdResult(
        comparison_key=metric.comparison_key,
        operator_key=metric.operator_key,
        status="pass" if passed else "fail",
        observed_value=metric.value,
        threshold=threshold,
    )


def _unavailable_comparison(
    comparison: CurveComparison, reason_code: str
) -> CurveComparisonResult:
    metrics = tuple(
        CurveMetricResult(
            comparison_key=comparison.comparison_key,
            operator_key=operator.operator_key,
            kind=operator.kind,
            status="unavailable",
            unit=(
                comparison.domain.unit
                if operator.kind in {"crossing_shift", "width_shift"}
                else "decade"
                if operator.value_space == "log10"
                else "unresolved"
            ),
            reason_code=reason_code,
            rationale="The comparison input contract is unavailable.",
        )
        for operator in comparison.operators
    )
    checks = tuple(
        CurveThresholdResult(
            comparison_key=comparison.comparison_key,
            operator_key=operator.operator_key,
            status="unavailable",
            threshold=operator.threshold,
            reason_code=reason_code,
        )
        for operator in comparison.operators
        if operator.threshold is not None
    )
    return CurveComparisonResult(
        comparison_key=comparison.comparison_key,
        required=comparison.required,
        purpose=comparison.purpose,
        gate_scope=comparison.gate_scope,
        metric_profile=comparison.metric_profile,
        status="unavailable",
        metrics=metrics,
        checks=checks,
        rationale="Required curve input is unavailable.",
    )


__all__ = [
    "AggregateStatus",
    "CurveAvailability",
    "CurveAxis",
    "CurveBundle",
    "CurveComparison",
    "CurveComparisonResult",
    "CurveComparisonSpec",
    "CurveConsistencyReport",
    "CurveDomain",
    "CurveExperimentContract",
    "CurveInterval",
    "CurveMetricResult",
    "CurveMetricCrossingSupport",
    "CurveOperatorSpec",
    "CurveObjectiveTargetBinding",
    "CurvePoint",
    "CurveReferenceCoverageBundle",
    "CurveReferenceComparisonSupport",
    "CurveReferenceCoverageReport",
    "CurveReferenceOperatorSupport",
    "CurveReferenceDisposition",
    "CurveSeries",
    "CurveSeriesDeclaration",
    "CurveThreshold",
    "CurveThresholdResult",
    "evaluate_curve_consistency",
    "curve_crossings",
    "curve_series_domain_reason",
    "curve_units_equivalent",
    "validate_curve_comparison_declaration_contract",
    "validate_curve_experiment_contract",
]
