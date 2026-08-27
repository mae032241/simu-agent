"""Bounded experiment proposals with pre-registered validation plans."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from .common import Identifier, SchemaModel, canonical_json, canonical_sha256
from .scientific_foundation import ScalarValue
from .curve_score import (
    CurveComparisonSpec,
    CurveOperatorSpec,
    validate_curve_comparison_declaration_contract,
)
from .units import unit_definition


Level = Literal["low", "medium", "high"]


def _scalar_values_equal(left: ScalarValue, right: ScalarValue) -> bool:
    """Compare declared controls without Python's bool/int coercion."""

    return type(left) is type(right) and left == right


class MetricThreshold(SchemaModel):
    operator: Literal["lt", "le", "gt", "ge", "between", "equal"]
    value: float
    upper_value: float | None = None
    unit: Annotated[str, Field(min_length=1, max_length=128)]

    @field_validator("unit")
    @classmethod
    def _unit_is_supported(cls, value: str) -> str:
        unit_definition(value, label="threshold unit")
        return value

    @model_validator(mode="after")
    def _range_matches_operator(self) -> MetricThreshold:
        if self.operator == "between":
            if self.upper_value is None or self.upper_value < self.value:
                raise ValueError("between threshold requires upper_value >= value")
        elif self.upper_value is not None:
            raise ValueError("upper_value is only valid for a between threshold")
        return self


class ExperimentFactor(SchemaModel):
    name: Identifier
    factor_type: Literal["physical", "numerical", "implementation"]
    values: Annotated[tuple[ScalarValue, ...], Field(min_length=1, max_length=64)]
    unit: Annotated[str, Field(min_length=1, max_length=128)]
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    def _values_are_unique(self) -> ExperimentFactor:
        distinct = {
            (type(value).__name__, value)
            for value in self.values
        }
        if len(self.values) != len(distinct):
            raise ValueError("factor values must be unique")
        return self


class FactorSetting(SchemaModel):
    name: Identifier
    value: ScalarValue
    unit: Annotated[str, Field(min_length=1, max_length=128)]


class ExperimentCase(SchemaModel):
    case_key: Identifier
    scientific_role: Literal[
        "baseline", "control", "perturbation", "convergence"
    ]
    settings: Annotated[tuple[FactorSetting, ...], Field(max_length=64)] = ()
    purpose: Annotated[str, Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    def _setting_names_are_unique(self) -> ExperimentCase:
        names = tuple(item.name for item in self.settings)
        if len(names) != len(set(names)):
            raise ValueError("case setting names must be unique")
        return self


class PredictionTest(SchemaModel):
    hypothesis_key: Identifier
    prediction_key: Identifier
    observable: Annotated[str, Field(min_length=1, max_length=4096)]
    expected_result: Annotated[str, Field(min_length=1, max_length=4096)]
    falsifying_result: Annotated[str, Field(min_length=1, max_length=4096)]


class CaseExpectation(SchemaModel):
    case_key: Identifier
    value: ScalarValue


class ComparisonVariable(SchemaModel):
    variable_key: Identifier
    scientific_path: Annotated[str, Field(min_length=1, max_length=4096)]
    factor_type: Literal["physical", "numerical", "implementation"]
    comparison_role: Literal[
        "intended_change", "frozen", "permitted_difference"
    ]
    unit: Annotated[str, Field(min_length=1, max_length=128)]
    expectations: Annotated[
        tuple[CaseExpectation, ...], Field(min_length=2, max_length=10000)
    ]
    equivalence_rule: Literal["exact", "absolute_tolerance", "reviewed"]
    tolerance: float | None = Field(default=None, ge=0)
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    def _comparison_semantics_are_explicit(self) -> ComparisonVariable:
        case_keys = tuple(item.case_key for item in self.expectations)
        if len(case_keys) != len(set(case_keys)):
            raise ValueError("comparison variable case expectations must be unique")
        values = tuple(item.value for item in self.expectations)
        if self.comparison_role == "intended_change" and len(set(values)) < 2:
            raise ValueError("intended_change variable must vary between cases")
        if self.comparison_role == "frozen" and len(set(values)) != 1:
            raise ValueError("frozen variable must have the same value in every case")
        if self.equivalence_rule == "absolute_tolerance":
            if self.tolerance is None:
                raise ValueError("absolute_tolerance requires tolerance")
            if not all(type(item) in {int, float} for item in values):
                raise ValueError("absolute_tolerance requires numeric expectations")
        elif self.tolerance is not None:
            raise ValueError("tolerance is only valid with absolute_tolerance")
        return self


class IdentifiabilityClaim(SchemaModel):
    hypothesis_key: Identifier
    competing_hypothesis_key: Identifier | None = None
    observable: Annotated[str, Field(min_length=1, max_length=4096)]
    distinguishing_outcome: Annotated[str, Field(min_length=1, max_length=4096)]
    decision_rule: Annotated[str, Field(min_length=1, max_length=4096)]
    ambiguity_conditions: Annotated[
        tuple[str, ...], Field(min_length=1, max_length=64)
    ]
    smallest_resolving_control: Annotated[str, Field(min_length=1, max_length=4096)]


class ComparisonContract(SchemaModel):
    baseline_case_key: Identifier
    comparison_case_keys: Annotated[
        tuple[Identifier, ...], Field(min_length=1, max_length=10000)
    ]
    variables: Annotated[
        tuple[ComparisonVariable, ...], Field(min_length=1, max_length=256)
    ]
    required_observables: Annotated[
        tuple[str, ...], Field(min_length=1, max_length=128)
    ]
    identifiability_claims: Annotated[
        tuple[IdentifiabilityClaim, ...], Field(min_length=1, max_length=128)
    ]

    @model_validator(mode="after")
    def _contract_keys_are_unique(self) -> ComparisonContract:
        if self.baseline_case_key in set(self.comparison_case_keys):
            raise ValueError("baseline cannot also be a comparison case")
        for values, label in (
            (self.comparison_case_keys, "comparison_case_keys"),
            (
                tuple(item.variable_key for item in self.variables),
                "comparison variable keys",
            ),
            (self.required_observables, "comparison required_observables"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{label} must be unique")
        expected_cases = {self.baseline_case_key, *self.comparison_case_keys}
        for variable in self.variables:
            if {item.case_key for item in variable.expectations} != expected_cases:
                raise ValueError(
                    "every comparison variable must cover the exact compared cases"
                )
        return self


class ResourceEstimate(SchemaModel):
    case_count: Annotated[int, Field(ge=1, le=10000)]
    relative_cost: Level
    runtime_basis: Annotated[str, Field(min_length=1, max_length=4096)]


class ExperimentValueAssessment(SchemaModel):
    evidence_support: Level
    discrimination_power: Level
    information_gain: Level
    cost: Level
    added_free_parameters: Annotated[int, Field(ge=0, le=128)]
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]


class ExperimentProposal(SchemaModel):
    experiment_key: Identifier
    objective: Annotated[str, Field(min_length=1, max_length=8192)]
    hypothesis_keys: Annotated[tuple[Identifier, ...], Field(max_length=12)] = ()
    changed_factors: Annotated[
        tuple[ExperimentFactor, ...], Field(max_length=64)
    ] = ()
    frozen_invariants: Annotated[tuple[str, ...], Field(min_length=1, max_length=128)]
    cases: Annotated[tuple[ExperimentCase, ...], Field(min_length=1, max_length=10000)]
    required_observables: Annotated[
        tuple[str, ...], Field(min_length=1, max_length=128)
    ]
    comparison_contract: ComparisonContract | None = None
    curve_comparison_spec: CurveComparisonSpec | None = None
    prediction_tests: Annotated[
        tuple[PredictionTest, ...], Field(max_length=128)
    ] = ()
    resource_estimate: ResourceEstimate
    stop_conditions: Annotated[tuple[str, ...], Field(min_length=1, max_length=64)]
    value_assessment: ExperimentValueAssessment

    @model_validator(mode="after")
    def _proposal_is_bounded(self) -> ExperimentProposal:
        if (
            self.curve_comparison_spec is not None
            and not self.curve_comparison_spec.series_declarations
        ):
            raise ValueError(
                "embedded curve comparison spec requires source series declarations"
            )
        for values, label in (
            (self.hypothesis_keys, "hypothesis_keys"),
            (
                tuple(item.name for item in self.changed_factors),
                "changed factor names",
            ),
            (tuple(item.case_key for item in self.cases), "case_key values"),
            (self.required_observables, "required_observables"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{label} must be unique")
        if not any(item.scientific_role in {"baseline", "control"} for item in self.cases):
            raise ValueError("experiment requires at least one baseline or control case")
        factor_by_name = {item.name: item for item in self.changed_factors}
        factor_names = set(factor_by_name)
        settings_by_case: dict[str, dict[str, FactorSetting]] = {}
        for case in self.cases:
            settings = {item.name: item for item in case.settings}
            if set(settings) != factor_names:
                raise ValueError(
                    "case settings must cover every changed factor exactly"
                )
            for name, setting in settings.items():
                factor = factor_by_name[name]
                if setting.unit != factor.unit:
                    raise ValueError(
                        f"case setting unit differs from changed factor: {name}"
                    )
                if not any(
                    _scalar_values_equal(setting.value, allowed)
                    for allowed in factor.values
                ):
                    raise ValueError(
                        f"case setting value is outside changed factor values: {name}"
                    )
            settings_by_case[case.case_key] = settings
        if self.resource_estimate.case_count != len(self.cases):
            raise ValueError("resource case_count must equal the declared case count")
        if not {item.hypothesis_key for item in self.prediction_tests}.issubset(
            set(self.hypothesis_keys)
        ):
            raise ValueError("prediction test references an undeclared hypothesis")
        case_by_key = {item.case_key: item for item in self.cases}
        contract = self.comparison_contract
        curve_spec = self.curve_comparison_spec
        if curve_spec is not None:
            declarations = {
                item.series_key: item for item in curve_spec.series_declarations
            }
            for comparison in curve_spec.comparisons:
                if comparison.purpose != "target_fit":
                    continue
                candidate = declarations[comparison.candidate_series]
                candidate_case = case_by_key.get(candidate.case_key)
                if candidate_case is None:
                    raise ValueError(
                        "target-fit solver candidate must name a declared experiment case"
                    )
                if candidate_case.scientific_role == "convergence":
                    raise ValueError(
                        "target-fit candidate cannot use a convergence-only case"
                    )
                if contract is None:
                    raise ValueError(
                        "target-fit candidate requires a comparison contract"
                    )
                expectation_by_variable = {
                    variable.variable_key: {
                        item.case_key: item.value
                        for item in variable.expectations
                    }
                    for variable in contract.variables
                    if variable.factor_type in {"numerical", "implementation"}
                }
                for variable_key, expected in expectation_by_variable.items():
                    baseline_value = expected[contract.baseline_case_key]
                    candidate_value = expected[candidate.case_key]
                    if (
                        type(candidate_value) is not type(baseline_value)
                        or candidate_value != baseline_value
                    ):
                        raise ValueError(
                            "target-fit candidate must preserve baseline numerical "
                            f"and implementation factors: {variable_key}"
                        )
        if contract is None:
            if len(self.cases) != 1:
                raise ValueError(
                    "experiment without comparison contract requires exactly one case"
                )
            if self.changed_factors:
                raise ValueError(
                    "experiment without comparison contract cannot declare changed factors"
                )
            return self
        compared_cases = {contract.baseline_case_key, *contract.comparison_case_keys}
        if compared_cases != set(case_by_key):
            raise ValueError("comparison contract must cover every experiment case")
        if case_by_key[contract.baseline_case_key].scientific_role not in {
            "baseline",
            "control",
        }:
            raise ValueError("comparison baseline must name a baseline or control case")
        intended = {
            item.variable_key
            for item in contract.variables
            if item.comparison_role == "intended_change"
        }
        if intended != factor_names:
            raise ValueError("intended comparison variables must equal changed factors")
        intended_by_key = {
            item.variable_key: item
            for item in contract.variables
            if item.comparison_role == "intended_change"
        }
        for factor_name, factor in factor_by_name.items():
            variable = intended_by_key[factor_name]
            if variable.factor_type != factor.factor_type:
                raise ValueError(
                    f"comparison factor type differs from changed factor: {factor_name}"
                )
            if variable.unit != factor.unit:
                raise ValueError(
                    f"comparison unit differs from changed factor: {factor_name}"
                )
            for expectation in variable.expectations:
                setting = settings_by_case[expectation.case_key][factor_name]
                if not _scalar_values_equal(expectation.value, setting.value):
                    raise ValueError(
                        "comparison expectation differs from exact case setting: "
                        f"{factor_name}/{expectation.case_key}"
                    )
        if set(contract.required_observables) != set(self.required_observables):
            raise ValueError(
                "comparison contract observables must equal required_observables"
            )
        claim_hypotheses = {
            item.hypothesis_key for item in contract.identifiability_claims
        }
        if claim_hypotheses != set(self.hypothesis_keys):
            raise ValueError(
                "identifiability claims must cover every experiment hypothesis"
            )
        if not {
            item.observable for item in contract.identifiability_claims
        }.issubset(set(self.required_observables)):
            raise ValueError(
                "identifiability claim references an unrequired observable"
            )
        return self


class ValidationCheck(SchemaModel):
    check_key: Identifier
    observable: Annotated[str, Field(min_length=1, max_length=4096)]
    metric: Annotated[str, Field(min_length=1, max_length=4096)]
    evaluation_mode: Literal["deterministic_threshold", "reviewed_qualitative"]
    evaluator_profile: Identifier | None = None
    evaluator_metric: Identifier | None = None
    threshold: MetricThreshold | None = None
    acceptance_condition: Annotated[str, Field(min_length=1, max_length=4096)]
    failure_action: Annotated[str, Field(min_length=1, max_length=4096)]
    basis: Annotated[str, Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    def _threshold_matches_evaluation(self) -> ValidationCheck:
        if (self.evaluator_profile is None) != (self.evaluator_metric is None):
            raise ValueError(
                "deterministic evaluator profile and metric must be supplied together"
            )
        if self.evaluation_mode == "deterministic_threshold" and self.threshold is None:
            raise ValueError("deterministic_threshold check requires threshold")
        if self.evaluation_mode == "reviewed_qualitative":
            if self.threshold is not None:
                raise ValueError("reviewed_qualitative check cannot declare threshold")
            if self.evaluator_profile is not None:
                raise ValueError(
                    "reviewed_qualitative check cannot declare a deterministic evaluator"
                )
        return self


class ValidationDimensionPlan(SchemaModel):
    applicability: Literal["required", "not_applicable"]
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]
    checks: Annotated[tuple[ValidationCheck, ...], Field(max_length=128)] = ()

    @model_validator(mode="after")
    def _applicability_matches_checks(self) -> ValidationDimensionPlan:
        if self.applicability == "required" and not self.checks:
            raise ValueError("required validation dimension needs at least one check")
        if self.applicability == "not_applicable" and self.checks:
            raise ValueError("not_applicable validation dimension cannot contain checks")
        keys = tuple(item.check_key for item in self.checks)
        if len(keys) != len(set(keys)):
            raise ValueError("validation check_key values must be unique within a dimension")
        return self


class ValidationPlan(SchemaModel):
    plan_key: Identifier
    experiment_key: Identifier
    numerical: ValidationDimensionPlan
    physical: ValidationDimensionPlan
    experimental: ValidationDimensionPlan
    claim_gate: Literal["all_required_checks_pass"] = "all_required_checks_pass"

    @model_validator(mode="after")
    def _check_keys_are_globally_unique(self) -> ValidationPlan:
        keys = tuple(
            item.check_key
            for dimension in (self.numerical, self.physical, self.experimental)
            for item in dimension.checks
        )
        if len(keys) != len(set(keys)):
            raise ValueError("validation check_key values must be globally unique")
        return self


class ExperimentPortfolio(SchemaModel):
    study_kind: Literal["scientific", "engineering"] = "scientific"
    objective_key: Identifier | None = None
    objective: Annotated[str, Field(min_length=1, max_length=8192)]
    selected_hypothesis_keys: Annotated[
        tuple[Identifier, ...], Field(max_length=12)
    ] = ()
    proposals: Annotated[
        tuple[ExperimentProposal, ...], Field(min_length=1, max_length=16)
    ]
    validation_plans: Annotated[
        tuple[ValidationPlan, ...], Field(min_length=1, max_length=16)
    ]
    priority_order: Annotated[
        tuple[Identifier, ...], Field(min_length=1, max_length=16)
    ]
    priority_rationale: Annotated[str, Field(min_length=1, max_length=8192)]

    @model_validator(mode="after")
    def _portfolio_is_complete_and_ranked(self) -> ExperimentPortfolio:
        proposal_keys = tuple(item.experiment_key for item in self.proposals)
        plan_keys = tuple(item.plan_key for item in self.validation_plans)
        curve_spec_count = sum(
            item.curve_comparison_spec is not None for item in self.proposals
        )
        if curve_spec_count > 1:
            raise ValueError(
                "experiment portfolio supports exactly one executable curve "
                "comparison spec"
            )
        if len(proposal_keys) != len(set(proposal_keys)):
            raise ValueError("experiment_key values must be unique")
        if len(plan_keys) != len(set(plan_keys)):
            raise ValueError("plan_key values must be unique")
        if len(self.selected_hypothesis_keys) != len(set(self.selected_hypothesis_keys)):
            raise ValueError("selected_hypothesis_keys must be unique")
        if set(self.priority_order) != set(proposal_keys) or len(
            self.priority_order
        ) != len(set(self.priority_order)):
            raise ValueError("priority_order must contain every experiment exactly once")
        proposal_by_key = {item.experiment_key: item for item in self.proposals}
        selected = set(self.selected_hypothesis_keys)
        for proposal in self.proposals:
            if not set(proposal.hypothesis_keys).issubset(selected):
                raise ValueError("proposal references an unselected hypothesis")
        if {item.experiment_key for item in self.validation_plans} != set(proposal_keys):
            raise ValueError("every experiment requires exactly one validation plan")
        plan_by_experiment = {
            item.experiment_key: item for item in self.validation_plans
        }
        for proposal in self.proposals:
            if proposal.curve_comparison_spec is not None:
                curve_validation_check_keys(
                    proposal,
                    plan_by_experiment[proposal.experiment_key],
                )
        scores = [experiment_value_score(proposal_by_key[key]) for key in self.priority_order]
        if scores != sorted(scores, reverse=True):
            raise ValueError("priority_order must be non-increasing by deterministic value score")
        if self.study_kind == "scientific":
            if not selected:
                raise ValueError("scientific portfolio requires selected hypotheses")
            if self.objective_key is None:
                raise ValueError("scientific portfolio requires objective_key")
            for proposal in self.proposals:
                if (
                    not proposal.hypothesis_keys
                    or not proposal.changed_factors
                    or len(proposal.cases) < 2
                    or proposal.comparison_contract is None
                    or not proposal.prediction_tests
                ):
                    raise ValueError(
                        "scientific experiment requires hypotheses, comparison cases, "
                        "changed factors, comparison contract, and prediction tests"
                    )
        else:
            if selected:
                raise ValueError("engineering portfolio cannot select scientific hypotheses")
            for proposal in self.proposals:
                if (
                    proposal.hypothesis_keys
                    or proposal.changed_factors
                    or len(proposal.cases) != 1
                    or proposal.comparison_contract is not None
                    or proposal.prediction_tests
                ):
                    raise ValueError(
                        "engineering experiment must be one case with no hypotheses, "
                        "changed factors, comparison contract, or prediction tests"
                    )
            for plan in self.validation_plans:
                if (
                    plan.numerical.applicability != "required"
                    or plan.physical.applicability != "not_applicable"
                    or plan.experimental.applicability != "not_applicable"
                ):
                    raise ValueError(
                        "engineering experiment requires numerical validation only"
                    )
        return self


def deterministic_validation_check_keys(plan: ValidationPlan) -> tuple[Identifier, ...]:
    """Return deterministic checks in their immutable declaration order."""

    return tuple(
        check.check_key
        for dimension in (plan.numerical, plan.physical, plan.experimental)
        for check in dimension.checks
        if check.evaluation_mode == "deterministic_threshold"
    )


def curve_validation_check_keys(
    proposal: ExperimentProposal,
    plan: ValidationPlan,
) -> tuple[Identifier, ...]:
    """Validate exact one-to-one coverage of a plan by its curve-score spec."""

    spec = proposal.curve_comparison_spec
    if spec is None:
        raise ValueError("proposal does not declare a curve comparison spec")
    if plan.experiment_key != proposal.experiment_key:
        raise ValueError("curve comparison spec and validation plan experiment mismatch")

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
                raise ValueError(
                    "thresholded curve operator requires validation_check_key"
                )
            if key is not None and operator.threshold is None:
                raise ValueError(
                    "curve validation_check_key requires an operator threshold"
                )
            if key is None:
                continue
            if key in bound:
                raise ValueError(
                    "each deterministic validation check must bind exactly one curve operator"
                )
            bound[key] = operator
            bound_in_comparison += 1
        if (
            comparison.required
            and comparison.gate_scope == "numerical_qualification"
            and bound_in_comparison == 0
        ):
            raise ValueError(
                "required numerical-qualification curve comparison needs a "
                "thresholded validation-check binding"
            )

    expected = set(checks)
    actual = set(bound)
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise ValueError(
            "curve comparison spec must cover the exact deterministic validation "
            f"checks; missing={missing}, unexpected={unexpected}"
        )
    for key, operator in bound.items():
        threshold = operator.threshold
        planned_check = checks[key]
        planned = planned_check.threshold
        assert threshold is not None and planned is not None
        if planned_check.evaluator_metric != operator.kind:
            raise ValueError(
                f"curve operator kind does not match validation evaluator for {key}"
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
            raise ValueError(
                f"curve operator threshold does not match validation check {key}"
            )
    return deterministic_validation_check_keys(plan)


_LEVEL_SCORE = {"low": 1, "medium": 2, "high": 3}


def experiment_value_score(proposal: ExperimentProposal) -> int:
    value = proposal.value_assessment
    return (
        _LEVEL_SCORE[value.evidence_support]
        + _LEVEL_SCORE[value.discrimination_power]
        + _LEVEL_SCORE[value.information_gain]
        - _LEVEL_SCORE[value.cost]
        - value.added_free_parameters
    )


def validate_experiment_portfolio(value: dict[str, object]) -> dict[str, object]:
    portfolio = ExperimentPortfolio.model_validate_json(
        canonical_json(value), strict=True
    )
    for proposal in portfolio.proposals:
        if proposal.curve_comparison_spec is not None:
            validate_curve_comparison_declaration_contract(
                proposal.curve_comparison_spec
            )
    return portfolio.model_dump(mode="json")


def validate_experiment_design_task_output(
    value: dict[str, object],
    inputs: dict[str, bytes],
    handoff: dict[str, object],
) -> None:
    """Bind a scientific plan to the exact approved objective when supplied."""

    del handoff
    portfolio = ExperimentPortfolio.model_validate_json(
        canonical_json(value), strict=True
    )
    for proposal in portfolio.proposals:
        if proposal.curve_comparison_spec is not None:
            validate_curve_comparison_declaration_contract(
                proposal.curve_comparison_spec
            )
    if portfolio.study_kind == "engineering":
        return
    raw_objective = inputs.get("research_objective")
    raw_hypotheses = inputs.get("hypothesis_portfolio")
    raw_eligibility = inputs.get("candidate_eligibility")
    if raw_objective is None:
        raise ValueError("scientific experiment design requires research_objective")
    if raw_hypotheses is None:
        raise ValueError("scientific experiment design requires hypothesis_portfolio")
    if raw_eligibility is None:
        raise ValueError("scientific experiment design requires candidate_eligibility")
    from .cognitive import HypothesisProposal
    from .eligibility import CandidateEligibility
    from .scientific_objective import ResearchObjectiveContract

    objective = ResearchObjectiveContract.model_validate_json(
        raw_objective, strict=True
    )
    hypotheses = HypothesisProposal.model_validate_json(raw_hypotheses, strict=True)
    eligibility = CandidateEligibility.model_validate_json(
        raw_eligibility, strict=True
    )
    hypothesis_keys = {item.hypothesis_key for item in hypotheses.hypotheses}
    selected = set(portfolio.selected_hypothesis_keys)
    if not selected.issubset(hypothesis_keys):
        raise ValueError(
            "experiment portfolio selects a hypothesis absent from the supplied portfolio"
        )
    if not selected.issubset(set(eligibility.eligible_hypothesis_keys)):
        raise ValueError(
            "experiment portfolio selects a hypothesis that is not eligible"
        )
    if eligibility.status != "ready":
        raise ValueError("scientific experiment design requires ready eligibility")
    if eligibility.objective != hypotheses.objective:
        raise ValueError(
            "candidate eligibility objective differs from hypothesis portfolio"
        )
    if eligibility.hypothesis_portfolio_sha256 != canonical_sha256(
        hypotheses.model_dump(mode="json")
    ):
        raise ValueError(
            "candidate eligibility does not bind the exact hypothesis portfolio"
        )
    if portfolio.objective != hypotheses.objective:
        raise ValueError(
            "experiment portfolio objective differs from hypothesis portfolio"
        )
    if portfolio.objective_key != objective.objective_key:
        raise ValueError(
            "experiment portfolio objective_key differs from research objective"
        )
    if portfolio.objective != objective.statement:
        raise ValueError(
            "experiment portfolio objective statement differs from research objective"
        )
    target_references = {
        comparison.reference_series
        for proposal in portfolio.proposals
        if proposal.curve_comparison_spec is not None
        for comparison in proposal.curve_comparison_spec.comparisons
        if comparison.purpose == "target_fit"
        and comparison.gate_scope == "objective"
        and comparison.required
    }
    missing_targets = tuple(
        target.target_key
        for target in objective.mandatory_targets
        if target.reference_series_key not in target_references
    )
    if missing_targets:
        raise ValueError(
            "experiment portfolio omits mandatory objective targets: "
            + ", ".join(missing_targets)
        )


__all__ = [
    "ExperimentCase",
    "CaseExpectation",
    "ComparisonContract",
    "ComparisonVariable",
    "ExperimentFactor",
    "ExperimentPortfolio",
    "ExperimentProposal",
    "ExperimentValueAssessment",
    "FactorSetting",
    "IdentifiabilityClaim",
    "MetricThreshold",
    "PredictionTest",
    "ResourceEstimate",
    "ValidationCheck",
    "ValidationDimensionPlan",
    "ValidationPlan",
    "curve_validation_check_keys",
    "deterministic_validation_check_keys",
    "experiment_value_score",
    "validate_experiment_portfolio",
    "validate_experiment_design_task_output",
]
