"""Bounded experiment proposals with pre-registered validation plans."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import Identifier, SchemaModel, canonical_json
from .scientific_foundation import ScalarValue


Level = Literal["low", "medium", "high"]


class MetricThreshold(SchemaModel):
    operator: Literal["lt", "le", "gt", "ge", "between", "equal"]
    value: float
    upper_value: float | None = None
    unit: Annotated[str, Field(min_length=1, max_length=128)]

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
        if len(self.values) != len(set(self.values)):
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
    prediction_tests: Annotated[
        tuple[PredictionTest, ...], Field(max_length=128)
    ] = ()
    resource_estimate: ResourceEstimate
    stop_conditions: Annotated[tuple[str, ...], Field(min_length=1, max_length=64)]
    value_assessment: ExperimentValueAssessment

    @model_validator(mode="after")
    def _proposal_is_bounded(self) -> ExperimentProposal:
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
        factor_names = {item.name for item in self.changed_factors}
        for case in self.cases:
            if not {item.name for item in case.settings}.issubset(factor_names):
                raise ValueError("case setting references an undeclared factor")
        if self.resource_estimate.case_count != len(self.cases):
            raise ValueError("resource case_count must equal the declared case count")
        if not {item.hypothesis_key for item in self.prediction_tests}.issubset(
            set(self.hypothesis_keys)
        ):
            raise ValueError("prediction test references an undeclared hypothesis")
        case_by_key = {item.case_key: item for item in self.cases}
        contract = self.comparison_contract
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
    threshold: MetricThreshold | None = None
    acceptance_condition: Annotated[str, Field(min_length=1, max_length=4096)]
    failure_action: Annotated[str, Field(min_length=1, max_length=4096)]
    basis: Annotated[str, Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    def _threshold_matches_evaluation(self) -> ValidationCheck:
        if self.evaluation_mode == "deterministic_threshold" and self.threshold is None:
            raise ValueError("deterministic_threshold check requires threshold")
        if self.evaluation_mode == "reviewed_qualitative" and self.threshold is not None:
            raise ValueError("reviewed_qualitative check cannot declare threshold")
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
        scores = [experiment_value_score(proposal_by_key[key]) for key in self.priority_order]
        if scores != sorted(scores, reverse=True):
            raise ValueError("priority_order must be non-increasing by deterministic value score")
        if self.study_kind == "scientific":
            if not selected:
                raise ValueError("scientific portfolio requires selected hypotheses")
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
    return ExperimentPortfolio.model_validate_json(
        canonical_json(value), strict=True
    ).model_dump(mode="json")


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
    "experiment_value_score",
    "validate_experiment_portfolio",
]
