"""Compact scientific experiment intent and deterministic plan materialization."""

from __future__ import annotations

import hashlib
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import Identifier, SchemaModel, Sha256, canonical_json, canonical_sha256
from .curve_score import (
    CurveAxis,
    CurveComparison,
    CurveComparisonPurpose,
    CurveComparisonSpec,
    CurveDomain,
    CurveFloorMask,
    CurveMetricProfile,
    CurveOperatorSpec,
    CurveReferenceDisposition,
    CurveSeriesDeclaration,
    CurveThreshold,
)
from .device_parameters import DeviceParameterSet
from .experiment import (
    CaseExpectation,
    ComparisonContract,
    ComparisonVariable,
    ExperimentCase,
    ExperimentFactor,
    ExperimentPortfolio,
    ExperimentProposal,
    ExperimentValueAssessment,
    FactorSetting,
    IdentifiabilityClaim,
    PredictionTest,
    ResourceEstimate,
    MetricThreshold,
    ValidationCheck,
    ValidationDimensionPlan,
    ValidationPlan,
    experiment_value_score,
    validate_experiment_design_task_output,
    validate_experiment_portfolio,
)
from .scientific_foundation import ScalarValue
from .scientific_objective import ResearchObjectiveContract


Level = Literal["low", "medium", "high"]


def _values_equal(left: ScalarValue, right: ScalarValue) -> bool:
    return type(left) is type(right) and left == right


class IntentCase(SchemaModel):
    """One scientifically meaningful case without repeated control values."""

    case_key: Identifier
    scientific_role: Literal[
        "baseline", "control", "perturbation", "convergence"
    ]
    purpose: Annotated[str, Field(min_length=1, max_length=4096)]


class IntentCaseOverride(SchemaModel):
    """A value that differs from a variable's baseline value for one case."""

    case_key: Identifier
    value: ScalarValue


class IntentComparisonVariable(SchemaModel):
    """One control variable expressed once plus sparse per-case overrides."""

    variable_key: Identifier
    scientific_path: Annotated[str, Field(min_length=1, max_length=4096)]
    factor_type: Literal["physical", "numerical", "implementation"]
    comparison_role: Literal[
        "intended_change", "frozen", "permitted_difference"
    ]
    unit: Annotated[str, Field(min_length=1, max_length=128)]
    baseline_value: ScalarValue
    case_overrides: Annotated[
        tuple[IntentCaseOverride, ...], Field(max_length=10000)
    ] = ()
    equivalence_rule: Literal["exact", "absolute_tolerance", "reviewed"]
    tolerance: float | None = Field(default=None, ge=0)
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    def _override_and_tolerance_contract(self) -> IntentComparisonVariable:
        keys = tuple(item.case_key for item in self.case_overrides)
        if len(keys) != len(set(keys)):
            raise ValueError("intent variable case overrides must be unique")
        if self.equivalence_rule == "absolute_tolerance":
            if self.tolerance is None:
                raise ValueError("absolute_tolerance requires tolerance")
            values = (self.baseline_value, *(item.value for item in self.case_overrides))
            if not all(type(item) in {int, float} for item in values):
                raise ValueError("absolute_tolerance requires numeric values")
        elif self.tolerance is not None:
            raise ValueError("tolerance is only valid with absolute_tolerance")
        return self


class IntentResourceEstimate(SchemaModel):
    """Agent-owned cost judgment; case count is derived by control."""

    relative_cost: Level
    runtime_basis: Annotated[str, Field(min_length=1, max_length=4096)]


IntentNumber = int | float


class IntentCurveDomain(SchemaModel):
    start: IntentNumber
    stop: IntentNumber
    unit: Annotated[str, Field(min_length=1, max_length=128)]
    min_points: Annotated[int, Field(ge=2, le=1_000_000)] = 2

    @model_validator(mode="after")
    def _ordered(self) -> IntentCurveDomain:
        if float(self.stop) <= float(self.start):
            raise ValueError("curve intent domain stop must exceed start")
        return self


class IntentCurveThreshold(SchemaModel):
    comparison: Literal["le", "ge", "abs_le"]
    value: IntentNumber
    unit: Annotated[str, Field(min_length=1, max_length=128)]
    basis: Annotated[str, Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    def _absolute_limit_is_nonnegative(self) -> IntentCurveThreshold:
        if self.comparison == "abs_le" and float(self.value) < 0:
            raise ValueError("absolute curve threshold must be nonnegative")
        return self


class IntentCurveFloorMask(SchemaModel):
    reference_at_or_below: IntentNumber
    candidate_at_or_below: IntentNumber
    unit: Annotated[str, Field(min_length=1, max_length=128)]
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    def _floors_are_nonnegative(self) -> IntentCurveFloorMask:
        if min(float(self.reference_at_or_below), float(self.candidate_at_or_below)) < 0:
            raise ValueError("curve intent floor values must be nonnegative")
        return self


class IntentCurveSeries(SchemaModel):
    """Scientific series identity; control derives execution-only role fields."""

    series_key: Identifier
    case_key: Identifier
    role: Identifier
    source: Literal["solver_output", "reference_input"] = "solver_output"
    x_axis: CurveAxis
    y_axis: CurveAxis
    min_points: Annotated[int, Field(ge=2, le=1_000_000)] = 2
    max_points: Annotated[int, Field(ge=2, le=1_000_000)] = 1_000_000

    @model_validator(mode="after")
    def _point_bounds_are_ordered(self) -> IntentCurveSeries:
        if self.max_points < self.min_points:
            raise ValueError("curve intent max_points must not be below min_points")
        return self


class IntentCurveOperator(SchemaModel):
    operator_key: Identifier
    kind: Literal[
        "point_difference",
        "residual_rms",
        "residual_max_abs",
        "mean_signed_difference",
        "crossing_shift",
        "width_shift",
    ]
    value_space: Literal["linear", "log10"] | None = None
    level: IntentNumber | None = None
    second_level: IntentNumber | None = None
    crossing_direction: Literal["increasing", "decreasing", "either"] = "either"
    x: IntentNumber | None = None
    threshold: IntentCurveThreshold | None = None

    @model_validator(mode="after")
    def _parameters_match_operator(self) -> IntentCurveOperator:
        front = self.kind in {"crossing_shift", "width_shift"}
        if front != (self.level is not None):
            raise ValueError("crossing and width intent operators require a level")
        if (self.kind == "width_shift") != (self.second_level is not None):
            raise ValueError("width intent operator requires a second level")
        if front and self.value_space not in {None, "linear"}:
            raise ValueError("crossing levels are always linear curve values")
        if (self.kind == "point_difference") != (self.x is not None):
            raise ValueError("point-difference intent operator requires one x value")
        return self


class IntentCurveComparison(SchemaModel):
    comparison_key: Identifier
    reference_series: Identifier
    candidate_series: Identifier
    observable: Annotated[str, Field(min_length=1, max_length=4096)]
    domain: IntentCurveDomain
    interpolation: Literal["linear_y", "log10_y"]
    evaluation_points: Annotated[int, Field(ge=2, le=1_000_000)] = 257
    operators: Annotated[
        tuple[IntentCurveOperator, ...], Field(min_length=1, max_length=256)
    ]
    required: bool = True
    purpose: CurveComparisonPurpose
    metric_profile: CurveMetricProfile
    floor_mask: IntentCurveFloorMask | None = None

    @model_validator(mode="after")
    def _operators_are_unique(self) -> IntentCurveComparison:
        keys = tuple(item.operator_key for item in self.operators)
        if len(keys) != len(set(keys)):
            raise ValueError("curve intent operator keys must be unique")
        if self.purpose == "target_fit" and not self.required:
            raise ValueError("target-fit comparison cannot be optional")
        if self.purpose == "exploratory_diagnostic" and self.required:
            raise ValueError("exploratory comparison cannot be required")
        return self


class IntentCurveComparisonSpec(SchemaModel):
    spec_key: Identifier
    series: Annotated[
        tuple[IntentCurveSeries, ...], Field(min_length=2, max_length=10000)
    ]
    comparisons: Annotated[
        tuple[IntentCurveComparison, ...], Field(min_length=1, max_length=10000)
    ]
    reference_dispositions: Annotated[
        tuple[CurveReferenceDisposition, ...], Field(default=(), max_length=10000)
    ] = ()

    @model_validator(mode="after")
    def _references_are_declared(self) -> IntentCurveComparisonSpec:
        series_keys = tuple(item.series_key for item in self.series)
        identities = tuple((item.case_key, item.role) for item in self.series)
        comparison_keys = tuple(item.comparison_key for item in self.comparisons)
        if len(series_keys) != len(set(series_keys)) or len(identities) != len(set(identities)):
            raise ValueError("curve intent series identities must be unique")
        if len(comparison_keys) != len(set(comparison_keys)):
            raise ValueError("curve intent comparison keys must be unique")
        declared = set(series_keys)
        if any(
            item.reference_series not in declared or item.candidate_series not in declared
            for item in self.comparisons
        ):
            raise ValueError("curve intent comparison references an undeclared series")
        return self


class IntentReviewedValidationCheck(SchemaModel):
    observable: Annotated[str, Field(min_length=1, max_length=4096)]
    metric: Annotated[str, Field(min_length=1, max_length=4096)]
    acceptance_condition: Annotated[str, Field(min_length=1, max_length=4096)]
    failure_action: Annotated[str, Field(min_length=1, max_length=4096)]
    basis: Annotated[str, Field(min_length=1, max_length=4096)]


class IntentValidationDimension(SchemaModel):
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]
    reviewed_checks: Annotated[
        tuple[IntentReviewedValidationCheck, ...], Field(max_length=128)
    ] = ()


class IntentValidationPlan(SchemaModel):
    numerical: IntentValidationDimension
    physical: IntentValidationDimension
    experimental: IntentValidationDimension


class ExperimentProposalIntent(SchemaModel):
    """Scientific choices for one experiment without mechanical expansion."""

    experiment_key: Identifier
    hypothesis_keys: Annotated[tuple[Identifier, ...], Field(max_length=12)] = ()
    frozen_invariants: Annotated[tuple[str, ...], Field(min_length=1, max_length=128)]
    cases: Annotated[tuple[IntentCase, ...], Field(min_length=1, max_length=10000)]
    baseline_case_key: Identifier | None = None
    variables: Annotated[
        tuple[IntentComparisonVariable, ...], Field(max_length=256)
    ] = ()
    required_observables: Annotated[
        tuple[str, ...], Field(min_length=1, max_length=128)
    ]
    identifiability_claims: Annotated[
        tuple[IdentifiabilityClaim, ...], Field(max_length=128)
    ] = ()
    curve_comparison_spec: CurveComparisonSpec | None = None
    curve_comparison_intent: IntentCurveComparisonSpec | None = None
    prediction_tests: Annotated[
        tuple[PredictionTest, ...], Field(max_length=128)
    ] = ()
    validation_plan: ValidationPlan | None = None
    validation_intent: IntentValidationPlan | None = None
    resource_estimate: IntentResourceEstimate
    stop_conditions: Annotated[tuple[str, ...], Field(min_length=1, max_length=64)]
    value_assessment: ExperimentValueAssessment

    @model_validator(mode="after")
    def _intent_is_bounded(self) -> ExperimentProposalIntent:
        case_keys = tuple(item.case_key for item in self.cases)
        variable_keys = tuple(item.variable_key for item in self.variables)
        for values, label in (
            (self.hypothesis_keys, "hypothesis_keys"),
            (case_keys, "case_key values"),
            (variable_keys, "comparison variable keys"),
            (self.required_observables, "required_observables"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{label} must be unique")
        if (self.validation_plan is None) == (self.validation_intent is None):
            raise ValueError(
                "intent requires exactly one legacy validation_plan or compact "
                "validation_intent"
            )
        if self.validation_plan is not None:
            if self.validation_plan.experiment_key != self.experiment_key:
                raise ValueError("intent validation plan experiment_key differs")
            if self.curve_comparison_intent is not None:
                raise ValueError(
                    "compact curve intent requires compact validation_intent"
                )
        else:
            if self.curve_comparison_spec is not None:
                raise ValueError(
                    "legacy curve comparison spec requires legacy validation_plan"
                )
        if self.curve_comparison_spec is not None and self.curve_comparison_intent is not None:
            raise ValueError("intent cannot declare both complete and compact curve specs")
        if self.curve_comparison_intent is not None:
            unknown_observables = {
                item.observable for item in self.curve_comparison_intent.comparisons
            } - set(self.required_observables)
            if unknown_observables:
                raise ValueError(
                    "curve intent comparison references an unrequired observable"
                )
        known_cases = set(case_keys)
        if self.baseline_case_key is None:
            if len(self.cases) != 1 or self.variables:
                raise ValueError(
                    "intent without a baseline comparison requires one case and no variables"
                )
        else:
            if self.baseline_case_key not in known_cases:
                raise ValueError("intent baseline case is undeclared")
            baseline = next(
                item for item in self.cases if item.case_key == self.baseline_case_key
            )
            if baseline.scientific_role not in {"baseline", "control"}:
                raise ValueError("intent baseline must be a baseline or control case")
            if len(self.cases) < 2 or not self.variables:
                raise ValueError("intent comparison requires cases and variables")
        for variable in self.variables:
            overrides = {item.case_key: item.value for item in variable.case_overrides}
            if self.baseline_case_key in overrides:
                raise ValueError("intent baseline value cannot also be overridden")
            unknown = set(overrides) - known_cases
            if unknown:
                raise ValueError("intent variable override references an unknown case")
            values = tuple(
                overrides.get(case_key, variable.baseline_value)
                for case_key in case_keys
            )
            distinct = {(type(item).__name__, item) for item in values}
            if variable.comparison_role == "intended_change" and len(distinct) < 2:
                raise ValueError("intended_change intent variable must vary")
            if variable.comparison_role == "frozen" and len(distinct) != 1:
                raise ValueError("frozen intent variable must not vary")
        return self


class ExperimentDesignIntent(SchemaModel):
    """Worker-authored scientific intent that control expands deterministically."""

    study_kind: Literal["scientific", "engineering"] = "scientific"
    objective_key: Identifier | None = None
    engineering_objective: Annotated[
        str | None, Field(default=None, min_length=1, max_length=8192)
    ] = None
    selected_hypothesis_keys: Annotated[
        tuple[Identifier, ...], Field(max_length=12)
    ] = ()
    proposals: Annotated[
        tuple[ExperimentProposalIntent, ...], Field(min_length=1, max_length=16)
    ]
    priority_order: Annotated[
        tuple[Identifier, ...], Field(min_length=1, max_length=16)
    ]
    priority_rationale: Annotated[str, Field(min_length=1, max_length=8192)]

    @model_validator(mode="after")
    def _portfolio_intent_is_complete(self) -> ExperimentDesignIntent:
        proposal_keys = tuple(item.experiment_key for item in self.proposals)
        curve_spec_count = sum(
            item.curve_comparison_spec is not None
            or item.curve_comparison_intent is not None
            for item in self.proposals
        )
        if curve_spec_count > 1:
            raise ValueError(
                "experiment intent supports exactly one executable curve comparison spec"
            )
        if len(proposal_keys) != len(set(proposal_keys)):
            raise ValueError("intent experiment_key values must be unique")
        if len(self.selected_hypothesis_keys) != len(set(self.selected_hypothesis_keys)):
            raise ValueError("intent selected_hypothesis_keys must be unique")
        if set(self.priority_order) != set(proposal_keys) or len(
            self.priority_order
        ) != len(set(self.priority_order)):
            raise ValueError("intent priority_order must contain every experiment once")
        selected = set(self.selected_hypothesis_keys)
        for proposal in self.proposals:
            if not set(proposal.hypothesis_keys).issubset(selected):
                raise ValueError("intent proposal references an unselected hypothesis")
        if self.study_kind == "scientific":
            if self.objective_key is None or not selected:
                raise ValueError("scientific intent requires objective and hypotheses")
            if self.engineering_objective is not None:
                raise ValueError("scientific intent cannot declare engineering_objective")
            for proposal in self.proposals:
                if (
                    not proposal.hypothesis_keys
                    or proposal.baseline_case_key is None
                    or not any(
                        item.comparison_role == "intended_change"
                        for item in proposal.variables
                    )
                    or not proposal.identifiability_claims
                    or not proposal.prediction_tests
                ):
                    raise ValueError(
                        "scientific intent requires hypotheses, comparisons, "
                        "identifiability claims, and prediction tests"
                    )
        else:
            if (
                self.objective_key is not None
                or selected
                or self.engineering_objective is None
            ):
                raise ValueError(
                    "engineering intent requires only an engineering objective"
                )
            for proposal in self.proposals:
                if (
                    proposal.hypothesis_keys
                    or len(proposal.cases) != 1
                    or proposal.baseline_case_key is not None
                    or proposal.variables
                    or proposal.identifiability_claims
                    or proposal.prediction_tests
                ):
                    raise ValueError(
                        "engineering intent must contain one non-comparison case"
                    )
        return self


class ExperimentPlanMaterializationReport(SchemaModel):
    schema_id: Literal["scidiscovery.experiment-plan-materialization.v1"] = (
        "scidiscovery.experiment-plan-materialization.v1"
    )
    status: Literal["pass"] = "pass"
    intent_sha256: Sha256
    objective_sha256: Sha256 | None = None
    hypothesis_portfolio_sha256: Sha256 | None = None
    candidate_eligibility_sha256: Sha256 | None = None
    experiment_plan_sha256: Sha256
    proposal_count: Annotated[int, Field(ge=1, le=16)]
    case_count: Annotated[int, Field(ge=1, le=10000)]
    comparison_variable_count: Annotated[int, Field(ge=0, le=4096)]

    @model_validator(mode="after")
    def _source_hashes_are_all_present_or_absent(
        self,
    ) -> ExperimentPlanMaterializationReport:
        values = (
            self.objective_sha256,
            self.hypothesis_portfolio_sha256,
            self.candidate_eligibility_sha256,
        )
        if any(item is None for item in values) and any(
            item is not None for item in values
        ):
            raise ValueError("materialization source hashes must be all present or absent")
        return self


def materialize_experiment_design_intent(
    intent: ExperimentDesignIntent,
    objective: ResearchObjectiveContract | None,
) -> ExperimentPortfolio:
    """Expand sparse intent into the existing strict complete portfolio schema."""

    if intent.study_kind == "scientific":
        if objective is None:
            raise ValueError("scientific experiment intent requires research objective")
        if intent.objective_key != objective.objective_key:
            raise ValueError(
                "experiment intent objective_key differs from research objective"
            )
        objective_statement = objective.statement
    else:
        if objective is not None:
            raise ValueError("engineering experiment intent cannot bind research objective")
        assert intent.engineering_objective is not None
        objective_statement = intent.engineering_objective
    proposals: list[ExperimentProposal] = []
    plans: list[ValidationPlan] = []
    for proposal_intent in intent.proposals:
        case_keys = tuple(item.case_key for item in proposal_intent.cases)
        variables = tuple(
            _materialize_variable(item, case_keys)
            for item in proposal_intent.variables
        )
        intended = tuple(
            item for item in variables if item.comparison_role == "intended_change"
        )
        changed_factors = tuple(
            ExperimentFactor(
                name=item.variable_key,
                factor_type=item.factor_type,
                values=_unique_scalar_values(
                    tuple(expectation.value for expectation in item.expectations)
                ),
                unit=item.unit,
                rationale=item.rationale,
            )
            for item in intended
        )
        intended_by_key = {item.variable_key: item for item in intended}
        cases = tuple(
            ExperimentCase(
                case_key=item.case_key,
                scientific_role=item.scientific_role,
                purpose=item.purpose,
                settings=tuple(
                    FactorSetting(
                        name=variable.variable_key,
                        value=next(
                            expectation.value
                            for expectation in variable.expectations
                            if expectation.case_key == item.case_key
                        ),
                        unit=variable.unit,
                    )
                    for variable in intended_by_key.values()
                ),
            )
            for item in proposal_intent.cases
        )
        contract = (
            None
            if proposal_intent.baseline_case_key is None
            else ComparisonContract(
                baseline_case_key=proposal_intent.baseline_case_key,
                comparison_case_keys=tuple(
                    key
                    for key in case_keys
                    if key != proposal_intent.baseline_case_key
                ),
                variables=variables,
                required_observables=proposal_intent.required_observables,
                identifiability_claims=proposal_intent.identifiability_claims,
            )
        )
        curve_spec, validation_plan = _materialize_curve_and_validation_intent(
            proposal_intent
        )
        proposals.append(
            ExperimentProposal(
                experiment_key=proposal_intent.experiment_key,
                objective=objective_statement,
                hypothesis_keys=proposal_intent.hypothesis_keys,
                changed_factors=changed_factors,
                frozen_invariants=proposal_intent.frozen_invariants,
                cases=cases,
                required_observables=proposal_intent.required_observables,
                comparison_contract=contract,
                curve_comparison_spec=curve_spec,
                prediction_tests=proposal_intent.prediction_tests,
                resource_estimate=ResourceEstimate(
                    case_count=len(cases),
                    relative_cost=proposal_intent.resource_estimate.relative_cost,
                    runtime_basis=proposal_intent.resource_estimate.runtime_basis,
                ),
                stop_conditions=proposal_intent.stop_conditions,
                value_assessment=proposal_intent.value_assessment,
            )
        )
        plans.append(validation_plan)
    portfolio = ExperimentPortfolio(
        study_kind=intent.study_kind,
        objective_key=intent.objective_key,
        objective=objective_statement,
        selected_hypothesis_keys=intent.selected_hypothesis_keys,
        proposals=tuple(proposals),
        validation_plans=tuple(plans),
        priority_order=intent.priority_order,
        priority_rationale=intent.priority_rationale,
    )
    validate_experiment_portfolio(portfolio.model_dump(mode="json"))
    expected_order = tuple(
        item.experiment_key
        for item in sorted(
            proposals,
            key=lambda item: (-experiment_value_score(item), item.experiment_key),
        )
    )
    scores = tuple(experiment_value_score(item) for item in proposals)
    if len(set(scores)) == len(scores) and portfolio.priority_order != expected_order:
        raise ValueError("intent priority order contradicts deterministic value scores")
    return portfolio


def validate_experiment_design_intent(value: dict[str, object]) -> dict[str, object]:
    intent = ExperimentDesignIntent.model_validate_json(canonical_json(value), strict=True)
    return intent.model_dump(mode="json")


def validate_experiment_design_intent_task_output(
    value: dict[str, object],
    inputs: dict[str, bytes],
    handoff: dict[str, object],
) -> None:
    intent = ExperimentDesignIntent.model_validate_json(
        canonical_json(value), strict=True
    )
    if any(proposal.validation_plan is not None for proposal in intent.proposals):
        raise ValueError(
            "new experiment design output must use compact validation_intent"
        )
    if any(
        proposal.curve_comparison_spec is not None for proposal in intent.proposals
    ):
        raise ValueError(
            "new experiment design output must use compact curve_comparison_intent"
        )
    if intent.study_kind == "engineering":
        portfolio = materialize_experiment_design_intent(intent, None)
        validate_experiment_design_task_output(
            portfolio.model_dump(mode="json"), inputs, handoff
        )
        return
    raw_objective = inputs.get("research_objective")
    if raw_objective is None:
        raise ValueError("experiment design intent requires research_objective")
    objective = ResearchObjectiveContract.model_validate_json(
        raw_objective, strict=True
    )
    raw_parameters = inputs.get("device_parameters")
    if raw_parameters is not None:
        _validate_tunable_parameter_mapping(
            intent,
            DeviceParameterSet.model_validate_json(raw_parameters, strict=True),
        )
    portfolio = materialize_experiment_design_intent(intent, objective)
    validate_experiment_design_task_output(
        portfolio.model_dump(mode="json"), inputs, handoff
    )


def _validate_tunable_parameter_mapping(
    intent: ExperimentDesignIntent,
    parameters: DeviceParameterSet,
) -> None:
    tunable_claims = tuple(
        item for item in parameters.claims if item.tuning is not None
    )
    for proposal in intent.proposals:
        variables = {item.variable_key: item for item in proposal.variables}
        case_keys = tuple(item.case_key for item in proposal.cases)
        for claim in tunable_claims:
            variable = variables.get(claim.parameter_key)
            if variable is None:
                raise ValueError(
                    f"tunable parameter {claim.parameter_key} is omitted from "
                    f"experiment {proposal.experiment_key}"
                )
            if variable.unit != claim.unit:
                raise ValueError(
                    f"tunable parameter {claim.parameter_key} unit differs from "
                    "the approved parameter set"
                )
            baseline = _intent_parameter_decimal(
                variable.baseline_value, claim.parameter_key
            )
            if baseline != Decimal(claim.selected_value):
                raise ValueError(
                    f"tunable parameter {claim.parameter_key} baseline differs from "
                    "the approved selected value"
                )
            if variable.comparison_role == "frozen":
                continue
            if variable.comparison_role != "intended_change":
                raise ValueError(
                    f"tunable parameter {claim.parameter_key} must be explicitly "
                    "scanned or frozen"
                )
            overrides = {
                item.case_key: item.value for item in variable.case_overrides
            }
            actual = {
                _intent_parameter_decimal(
                    overrides.get(case_key, variable.baseline_value),
                    claim.parameter_key,
                )
                for case_key in case_keys
            }
            assert claim.tuning is not None
            approved = {Decimal(item) for item in claim.tuning.candidate_values}
            if actual != approved:
                raise ValueError(
                    f"tunable parameter {claim.parameter_key} must use exactly "
                    "the approved candidate values"
                )


def _intent_parameter_decimal(value: ScalarValue, parameter_key: str) -> Decimal:
    if type(value) is not str:
        raise ValueError(
            f"tunable parameter {parameter_key} values must use "
            "scientific-notation strings"
        )
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise ValueError(
            f"tunable parameter {parameter_key} value is not numeric"
        ) from error
    if not parsed.is_finite():
        raise ValueError(f"tunable parameter {parameter_key} value must be finite")
    return parsed


def materialize_experiment_design_inputs(
    inputs: dict[str, bytes],
) -> tuple[ExperimentPortfolio, ExperimentPlanMaterializationReport]:
    if "experiment_design_intent" not in inputs:
        raise ValueError(
            "experiment plan materialization requires intent, objective, "
            "hypothesis portfolio, and candidate eligibility"
        )
    intent = ExperimentDesignIntent.model_validate_json(
        inputs["experiment_design_intent"], strict=True
    )
    if intent.study_kind == "engineering":
        if set(inputs) != {"experiment_design_intent"}:
            raise ValueError("engineering plan materialization requires only intent")
        objective = None
    else:
        required = {
            "experiment_design_intent",
            "research_objective",
            "hypothesis_portfolio",
            "candidate_eligibility",
        }
        if set(inputs) != required:
            raise ValueError(
                "scientific plan materialization requires intent, objective, "
                "hypothesis portfolio, and candidate eligibility"
            )
        objective = ResearchObjectiveContract.model_validate_json(
            inputs["research_objective"], strict=True
        )
    portfolio = materialize_experiment_design_intent(intent, objective)
    validation_inputs = {
        key: value for key, value in inputs.items() if key != "experiment_design_intent"
    }
    validate_experiment_design_task_output(
        portfolio.model_dump(mode="json"), validation_inputs, {}
    )
    report = ExperimentPlanMaterializationReport(
        intent_sha256=canonical_sha256(intent),
        objective_sha256=(
            canonical_sha256(objective) if objective is not None else None
        ),
        hypothesis_portfolio_sha256=(
            hashlib.sha256(inputs["hypothesis_portfolio"]).hexdigest()
            if "hypothesis_portfolio" in inputs
            else None
        ),
        candidate_eligibility_sha256=(
            hashlib.sha256(inputs["candidate_eligibility"]).hexdigest()
            if "candidate_eligibility" in inputs
            else None
        ),
        experiment_plan_sha256=canonical_sha256(portfolio),
        proposal_count=len(portfolio.proposals),
        case_count=sum(len(item.cases) for item in portfolio.proposals),
        comparison_variable_count=sum(
            len(item.comparison_contract.variables)
            for item in portfolio.proposals
            if item.comparison_contract is not None
        ),
    )
    return portfolio, report


def _materialize_curve_and_validation_intent(
    proposal: ExperimentProposalIntent,
) -> tuple[CurveComparisonSpec | None, ValidationPlan]:
    if proposal.validation_plan is not None:
        return proposal.curve_comparison_spec, proposal.validation_plan
    validation_intent = proposal.validation_intent
    assert validation_intent is not None
    curve_intent = proposal.curve_comparison_intent
    if curve_intent is None:
        return None, _materialize_validation_plan(
            proposal.experiment_key,
            validation_intent,
            generated={"numerical": [], "physical": [], "experimental": []},
        )

    comparisons: list[CurveComparison] = []
    generated: dict[str, list[ValidationCheck]] = {
        "numerical": [],
        "physical": [],
        "experimental": [],
    }
    for comparison in curve_intent.comparisons:
        gate_scope = {
            "target_fit": "objective",
            "numerical_convergence": "numerical_qualification",
            "mechanism_separation": "mechanism",
            "implementation_sanity": "numerical_qualification",
            "exploratory_diagnostic": "diagnostic_only",
            "unspecified_legacy": "unspecified_legacy",
        }[comparison.purpose]
        operators: list[CurveOperatorSpec] = []
        for operator in comparison.operators:
            check_key = None
            threshold = None
            if operator.threshold is not None:
                check_key = _bounded_identifier(
                    "curve", comparison.comparison_key, operator.operator_key
                )
                threshold = CurveThreshold(
                    comparison=operator.threshold.comparison,
                    value=float(operator.threshold.value),
                    unit=operator.threshold.unit,
                )
                dimension = {
                    "objective": "experimental",
                    "numerical_qualification": "numerical",
                    "mechanism": "physical",
                    "diagnostic_only": "physical",
                    "unspecified_legacy": "numerical",
                }[gate_scope]
                metric_threshold = MetricThreshold(
                    operator=(
                        "le"
                        if operator.threshold.comparison == "abs_le"
                        else operator.threshold.comparison
                    ),
                    value=float(operator.threshold.value),
                    unit=operator.threshold.unit,
                )
                generated[dimension].append(
                    ValidationCheck(
                        check_key=check_key,
                        observable=comparison.observable,
                        metric=operator.kind,
                        evaluation_mode="deterministic_threshold",
                        evaluator_profile="scidiscovery.curve-score.v1",
                        evaluator_metric=operator.kind,
                        threshold=metric_threshold,
                        acceptance_condition=(
                            f"{operator.kind} satisfies the declared "
                            f"{operator.threshold.comparison} "
                            f"{float(operator.threshold.value):g} "
                            f"{operator.threshold.unit} threshold."
                        ),
                        failure_action=(
                            "Fail the comparison's declared qualification gate."
                        ),
                        basis=operator.threshold.basis,
                    )
                )
            value_space = operator.value_space
            if value_space is None:
                value_space = (
                    "log10"
                    if operator.kind
                    in {
                        "residual_rms",
                        "residual_max_abs",
                        "mean_signed_difference",
                    }
                    and comparison.interpolation == "log10_y"
                    else "linear"
                )
            operators.append(
                CurveOperatorSpec(
                    operator_key=operator.operator_key,
                    validation_check_key=check_key,
                    kind=operator.kind,
                    value_space=value_space,
                    level=(float(operator.level) if operator.level is not None else None),
                    second_level=(
                        float(operator.second_level)
                        if operator.second_level is not None
                        else None
                    ),
                    crossing_direction=operator.crossing_direction,
                    x=float(operator.x) if operator.x is not None else None,
                    threshold=threshold,
                )
            )
        comparisons.append(
            CurveComparison(
                comparison_key=comparison.comparison_key,
                reference_series=comparison.reference_series,
                candidate_series=comparison.candidate_series,
                domain=CurveDomain(
                    start=float(comparison.domain.start),
                    stop=float(comparison.domain.stop),
                    unit=comparison.domain.unit,
                    min_points=comparison.domain.min_points,
                ),
                interpolation=comparison.interpolation,
                evaluation_points=comparison.evaluation_points,
                operators=tuple(operators),
                required=comparison.required,
                purpose=comparison.purpose,
                gate_scope=gate_scope,
                metric_profile=comparison.metric_profile,
                floor_mask=(
                    CurveFloorMask(
                        reference_at_or_below=float(
                            comparison.floor_mask.reference_at_or_below
                        ),
                        candidate_at_or_below=float(
                            comparison.floor_mask.candidate_at_or_below
                        ),
                        unit=comparison.floor_mask.unit,
                        rationale=comparison.floor_mask.rationale,
                    )
                    if comparison.floor_mask is not None
                    else None
                ),
            )
        )
    roles = _derive_curve_series_roles(curve_intent)
    spec = CurveComparisonSpec(
        spec_key=curve_intent.spec_key,
        series_declarations=tuple(
            CurveSeriesDeclaration(
                series_key=item.series_key,
                case_key=item.case_key,
                role=item.role,
                scientific_role=roles[item.series_key],
                source=item.source,
                x_axis=item.x_axis,
                y_axis=item.y_axis,
                min_points=item.min_points,
                max_points=item.max_points,
            )
            for item in curve_intent.series
        ),
        comparisons=tuple(comparisons),
        reference_dispositions=curve_intent.reference_dispositions,
    )
    return spec, _materialize_validation_plan(
        proposal.experiment_key, validation_intent, generated=generated
    )


def _derive_curve_series_roles(
    intent: IntentCurveComparisonSpec,
) -> dict[str, str]:
    roles: dict[str, str] = {}
    for series in intent.series:
        uses = tuple(
            (comparison, side)
            for comparison in intent.comparisons
            for side, key in (
                ("reference", comparison.reference_series),
                ("candidate", comparison.candidate_series),
            )
            if key == series.series_key
        )
        if series.source == "reference_input":
            roles[series.series_key] = "experimental_target"
        elif any(
            item.purpose in {"target_fit", "mechanism_separation"}
            for item, _ in uses
        ):
            roles[series.series_key] = "simulation_candidate"
        elif any(item.purpose == "numerical_convergence" for item, _ in uses):
            numerical_sides = {
                side
                for item, side in uses
                if item.purpose == "numerical_convergence"
            }
            roles[series.series_key] = (
                "simulation_candidate"
                if len(numerical_sides) > 1
                else (
                    "numerical_reference"
                    if "reference" in numerical_sides
                    else "numerical_variant"
                )
            )
        else:
            roles[series.series_key] = "diagnostic_series"
    return roles


def _materialize_validation_plan(
    experiment_key: str,
    intent: IntentValidationPlan,
    *,
    generated: dict[str, list[ValidationCheck]],
) -> ValidationPlan:
    dimensions = {}
    for dimension_name in ("numerical", "physical", "experimental"):
        dimension_intent = getattr(intent, dimension_name)
        checks = list(generated[dimension_name])
        checks.extend(
            ValidationCheck(
                check_key=_bounded_identifier(
                    dimension_name, "review", str(index + 1)
                ),
                observable=item.observable,
                metric=item.metric,
                evaluation_mode="reviewed_qualitative",
                acceptance_condition=item.acceptance_condition,
                failure_action=item.failure_action,
                basis=item.basis,
            )
            for index, item in enumerate(dimension_intent.reviewed_checks)
        )
        dimensions[dimension_name] = ValidationDimensionPlan(
            applicability="required" if checks else "not_applicable",
            rationale=dimension_intent.rationale,
            checks=tuple(checks),
        )
    return ValidationPlan(
        plan_key=_bounded_identifier(experiment_key, "validation"),
        experiment_key=experiment_key,
        numerical=dimensions["numerical"],
        physical=dimensions["physical"],
        experimental=dimensions["experimental"],
    )


def _bounded_identifier(*parts: str) -> str:
    value = "/".join(parts)
    if len(value) <= 256:
        return value
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{value[:239]}/{digest}"


def _materialize_variable(
    variable: IntentComparisonVariable,
    case_keys: tuple[str, ...],
) -> ComparisonVariable:
    overrides = {item.case_key: item.value for item in variable.case_overrides}
    return ComparisonVariable(
        variable_key=variable.variable_key,
        scientific_path=variable.scientific_path,
        factor_type=variable.factor_type,
        comparison_role=variable.comparison_role,
        unit=variable.unit,
        expectations=tuple(
            CaseExpectation(
                case_key=case_key,
                value=overrides.get(case_key, variable.baseline_value),
            )
            for case_key in case_keys
        ),
        equivalence_rule=variable.equivalence_rule,
        tolerance=variable.tolerance,
        rationale=variable.rationale,
    )


def _unique_scalar_values(values: tuple[ScalarValue, ...]) -> tuple[ScalarValue, ...]:
    unique: list[ScalarValue] = []
    for value in values:
        if not any(_values_equal(value, item) for item in unique):
            unique.append(value)
    return tuple(unique)


__all__ = [
    "ExperimentDesignIntent",
    "ExperimentPlanMaterializationReport",
    "ExperimentProposalIntent",
    "IntentCurveComparison",
    "IntentCurveComparisonSpec",
    "IntentCurveDomain",
    "IntentCurveOperator",
    "IntentCurveSeries",
    "IntentCurveThreshold",
    "IntentReviewedValidationCheck",
    "IntentValidationDimension",
    "IntentValidationPlan",
    "IntentCase",
    "IntentCaseOverride",
    "IntentComparisonVariable",
    "IntentResourceEstimate",
    "materialize_experiment_design_inputs",
    "materialize_experiment_design_intent",
    "validate_experiment_design_intent",
    "validate_experiment_design_intent_task_output",
]
