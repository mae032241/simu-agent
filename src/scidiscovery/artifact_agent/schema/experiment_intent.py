"""Compact domain-neutral experiment intent and deterministic materialization."""

from __future__ import annotations

import hashlib
from typing import Annotated, Literal

from pydantic import Field, ValidationError, model_validator

from .common import Identifier, SchemaModel, Sha256, canonical_json, canonical_sha256
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
    MetricThreshold,
    PredictionTest,
    ResourceEstimate,
    ValidationCheck,
    ValidationDimensionPlan,
    ValidationPlan,
    validate_experiment_design_task_output,
    validate_experiment_portfolio,
)
from .research_objective import ResearchObjectiveContract
from .scientific_foundation import ScalarValue
from ...operation_contract import (
    SemanticRuleViolation, contract_diagnostic, declared_violation, validation_diagnostics,
)


Level = Literal["low", "medium", "high"]


def _values_equal(left: ScalarValue, right: ScalarValue) -> bool:
    return type(left) is type(right) and left == right


ScientificText = Annotated[str, Field(min_length=1, max_length=4096)]
ScientificStatements = Annotated[tuple[ScientificText, ...], Field(min_length=1, max_length=64)]


class ExperimentScientificSkeleton(SchemaModel):
    """Scientific choices only; the author owns the concrete execution Portfolio."""

    selected_hypothesis_keys: Annotated[tuple[Identifier, ...], Field(min_length=1, max_length=32)]
    current_objectives: ScientificStatements
    competing_explanations_and_controls: ScientificStatements
    changed_conditions: ScientificStatements
    held_conditions: ScientificStatements
    observables: ScientificStatements
    discrimination_criteria_and_basis: ScientificStatements
    immutable_conditions: ScientificStatements
    stop_conditions: ScientificStatements
    feasibility_limitations: Annotated[tuple[ScientificText, ...], Field(max_length=64)] = ()


class IntentCase(SchemaModel):
    case_key: Identifier
    scientific_role: Literal[
        "baseline", "control", "perturbation", "convergence"
    ]
    purpose: Annotated[str, Field(min_length=1, max_length=4096)]


class IntentCaseOverride(SchemaModel):
    case_key: Identifier
    value: ScalarValue


class IntentComparisonVariable(SchemaModel):
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
    relative_cost: Level
    runtime_basis: Annotated[str, Field(min_length=1, max_length=4096)]


class IntentReviewedValidationCheck(SchemaModel):
    observable: Annotated[str, Field(min_length=1, max_length=4096)]
    metric: Annotated[str, Field(min_length=1, max_length=4096)]
    acceptance_condition: Annotated[str, Field(min_length=1, max_length=4096)]
    failure_action: Annotated[str, Field(min_length=1, max_length=4096)]
    basis: Annotated[str, Field(min_length=1, max_length=4096)]


class IntentDeterministicValidationCheck(SchemaModel):
    check_key: Identifier
    observable: Annotated[str, Field(min_length=1, max_length=4096)]
    metric: Annotated[str, Field(min_length=1, max_length=4096)]
    evaluator_profile: Identifier
    evaluator_metric: Identifier
    threshold: MetricThreshold
    acceptance_condition: Annotated[str, Field(min_length=1, max_length=4096)]
    failure_action: Annotated[str, Field(min_length=1, max_length=4096)]
    basis: Annotated[str, Field(min_length=1, max_length=4096)]


class IntentValidationDimension(SchemaModel):
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]
    deterministic_checks: Annotated[
        tuple[IntentDeterministicValidationCheck, ...], Field(max_length=128)
    ] = ()
    reviewed_checks: Annotated[
        tuple[IntentReviewedValidationCheck, ...], Field(max_length=128)
    ] = ()

    @model_validator(mode="after")
    def _deterministic_keys_are_unique(self) -> IntentValidationDimension:
        keys = tuple(item.check_key for item in self.deterministic_checks)
        if len(keys) != len(set(keys)):
            raise ValueError("deterministic validation check keys must be unique")
        return self


class IntentValidationPlan(SchemaModel):
    numerical: IntentValidationDimension
    physical: IntentValidationDimension
    experimental: IntentValidationDimension


class ExperimentProposalIntent(SchemaModel):
    """Scientific choices for one experiment without domain execution payloads."""

    experiment_key: Identifier
    objectives: Annotated[
        tuple[Annotated[str, Field(min_length=1, max_length=8192)], ...],
        Field(min_length=1, max_length=16),
    ]
    current_objectives: Annotated[
        tuple[Annotated[str, Field(min_length=1, max_length=8192)], ...],
        Field(min_length=1, max_length=16),
    ]
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
    prediction_tests: Annotated[
        tuple[PredictionTest, ...], Field(max_length=128)
    ] = ()
    validation_intent: IntentValidationPlan
    resource_estimate: IntentResourceEstimate
    stop_conditions: Annotated[tuple[str, ...], Field(min_length=1, max_length=64)]
    value_assessment: ExperimentValueAssessment

    @model_validator(mode="after")
    def _intent_is_bounded(self) -> ExperimentProposalIntent:
        case_keys = tuple(item.case_key for item in self.cases)
        variable_keys = tuple(item.variable_key for item in self.variables)
        for values, label in (
            (case_keys, "case_key values"),
            (variable_keys, "comparison variable keys"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{label} must be unique")
        if not set(self.current_objectives).issubset(self.objectives):
            raise ValueError("current_objectives must be an exact subset of objectives")
        known_cases = set(case_keys)
        if self.baseline_case_key is None and self.variables:
            baselines = tuple(item.case_key for item in self.cases
                              if item.scientific_role in {"baseline", "control"})
            if len(baselines) == 1:
                # Normalize validated fields during construction, before the frozen
                # intent is returned or sealed (as SchemaModel does for collections).
                object.__setattr__(self, "baseline_case_key", baselines[0])
        if self.baseline_case_key is None:
            if self.variables:
                raise declared_violation(
                    "Select a baseline_case_key: the declared cases do not identify one unambiguous baseline/control.",
                    path="$.baseline_case_key")
        if self.baseline_case_key is not None:
            if self.baseline_case_key not in known_cases:
                raise declared_violation("intent baseline case is undeclared", path="$.baseline_case_key")
            if len(self.cases) < 2 or not self.variables:
                raise ValueError("intent comparison requires cases and variables")
        for index, variable in enumerate(self.variables):
            overrides = {item.case_key: item.value for item in variable.case_overrides}
            if self.baseline_case_key in overrides:
                raise ValueError("intent baseline value cannot also be overridden")
            if set(overrides) - known_cases:
                raise ValueError("intent variable override references an unknown case")
            values = tuple(
                overrides.get(case_key, variable.baseline_value)
                for case_key in case_keys
            )
            distinct = {(type(item).__name__, item) for item in values}
            if variable.comparison_role == "intended_change" and len(distinct) < 2:
                raise declared_violation("intended_change intent variable must vary", path=f"$.variables[{index}].comparison_role")
            if variable.comparison_role == "frozen" and len(distinct) != 1:
                raise declared_violation("frozen intent variable must not vary across its declared cases", path=f"$.variables[{index}].comparison_role")
        return self


class ExperimentDesignIntent(SchemaModel):
    """Worker-authored scientific intent expanded by deterministic control."""

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
        if len(proposal_keys) != len(set(proposal_keys)):
            raise ValueError("intent experiment_key values must be unique")
        if set(self.priority_order) != set(proposal_keys) or len(
            self.priority_order
        ) != len(set(self.priority_order)):
            raise ValueError("intent priority_order must contain every experiment once")
        selected = set(self.selected_hypothesis_keys)
        for proposal in self.proposals:
            if not set(proposal.hypothesis_keys).issubset(selected):
                raise ValueError("intent proposal references an unselected hypothesis")
        if self.study_kind == "scientific":
            if not selected:
                raise ValueError("scientific intent requires hypotheses")
            if self.engineering_objective is not None:
                raise ValueError("scientific intent cannot declare engineering_objective")
        else:
            if (
                selected
                or self.engineering_objective is None
            ):
                raise ValueError(
                    "engineering intent requires only an engineering objective"
                )
        return self


class HistoricalExperimentProposalIntent(ExperimentProposalIntent):
    """Read sealed intents from before compact validation became mandatory."""

    validation_intent: IntentValidationPlan | None = None
    validation_plan: ValidationPlan | None = None

    @model_validator(mode="after")
    def _historical_validation_choice(self) -> HistoricalExperimentProposalIntent:
        if (self.validation_plan is None) == (self.validation_intent is None):
            raise ValueError(
                "intent requires exactly one complete validation_plan or compact validation_intent"
            )
        if (
            self.validation_plan is not None
            and self.validation_plan.experiment_key != self.experiment_key
        ):
            raise ValueError("intent validation plan experiment_key differs")
        return self


class HistoricalExperimentDesignIntent(ExperimentDesignIntent):
    """Historical input reader, never the contract for a new Worker output."""

    proposals: Annotated[
        tuple[HistoricalExperimentProposalIntent, ...], Field(min_length=1, max_length=16)
    ]


class ExperimentPlanMaterializationReport(SchemaModel):
    schema_id: Literal["scidiscovery.experiment-plan-materialization.v1"] = (
        "scidiscovery.experiment-plan-materialization.v1"
    )
    status: Literal["pass"] = "pass"
    intent_sha256: Sha256
    objective_sha256: Sha256 | None = None
    hypothesis_portfolio_sha256: Sha256 | None = None
    experiment_plan_sha256: Sha256
    proposal_count: Annotated[int, Field(ge=1, le=16)]
    case_count: Annotated[int, Field(ge=1, le=10000)]
    comparison_variable_count: Annotated[int, Field(ge=0, le=4096)]

    @model_validator(mode="after")
    def _source_hashes_are_all_present_or_absent(
        self,
    ) -> ExperimentPlanMaterializationReport:
        values = (self.objective_sha256, self.hypothesis_portfolio_sha256)
        if any(item is None for item in values) and any(
            item is not None for item in values
        ):
            raise ValueError("materialization source hashes must be all present or absent")
        return self


def materialize_experiment_design_intent(
    intent: ExperimentDesignIntent,
    objective: ResearchObjectiveContract | None,
) -> ExperimentPortfolio:
    if intent.study_kind == "scientific":
        if objective is None:
            raise ValueError("scientific experiment intent requires research objective")
        objective_statement = objective.statement
    else:
        if objective is not None:
            raise ValueError("engineering experiment intent cannot bind research objective")
        assert intent.engineering_objective is not None
        objective_statement = intent.engineering_objective
    proposals: list[ExperimentProposal] = []
    plans: list[ValidationPlan] = []
    for proposal_index, proposal_intent in enumerate(intent.proposals):
        case_keys = tuple(item.case_key for item in proposal_intent.cases)
        variables = []
        for variable_index, item in enumerate(proposal_intent.variables):
            try:
                variables.append(_materialize_variable(item, case_keys))
            except ValidationError as error:
                # Construction happens before the portfolio exists. Preserve the
                # editable intent location instead of exposing a relative field.
                prefix = ("proposals", proposal_index, "variables", variable_index)
                raise ValidationError.from_exception_data("ExperimentDesignIntent", [
                    {**detail, "loc": (*prefix, *detail["loc"])}
                    for detail in error.errors(include_url=False)
                ]) from error
        variables = tuple(variables)
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
        validation_plan = (
            proposal_intent.validation_plan
            if isinstance(proposal_intent, HistoricalExperimentProposalIntent)
            and proposal_intent.validation_plan is not None
            else _materialize_validation_plan(
                proposal_intent.experiment_key,
                proposal_intent.validation_intent,
            )
        )
        assert validation_plan is not None
        proposals.append(
            ExperimentProposal(
                experiment_key=proposal_intent.experiment_key,
                objectives=tuple(
                    dict.fromkeys((objective_statement, *proposal_intent.objectives))
                ),
                current_objectives=proposal_intent.current_objectives,
                hypothesis_keys=proposal_intent.hypothesis_keys,
                changed_factors=changed_factors,
                frozen_invariants=proposal_intent.frozen_invariants,
                cases=cases,
                required_observables=proposal_intent.required_observables,
                comparison_contract=contract,
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
        objective_key=objective.objective_key if intent.study_kind == "scientific" else None,
        objective=objective_statement,
        selected_hypothesis_keys=intent.selected_hypothesis_keys,
        proposals=tuple(proposals),
        validation_plans=tuple(plans),
        priority_order=intent.priority_order,
        priority_rationale=intent.priority_rationale,
    )
    validate_experiment_portfolio(portfolio.model_dump(mode="json"))
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
    objective = None
    if intent.study_kind == "scientific":
        raw_objective = inputs.get("research_objective")
        if raw_objective is None:
            raise SemanticRuleViolation("experiment design intent requires research_objective")
        objective = ResearchObjectiveContract.model_validate_json(
            raw_objective, strict=True
        )
    try:
        portfolio = materialize_experiment_design_intent(intent, objective)
    except ValidationError as error:
        # Only derived-model constraints reject Worker content here. Immutable
        # input parsing and unexpected materializer exceptions remain failures.
        details = tuple(
            contract_diagnostic("output_invalid", phase="output_payload", affected_action="submit",
                repairable=True, path=item["path"], message=item["message"],
                rule_id="experiment.design.intent_closure", error_type=item.get("type"))
            for item in validation_diagnostics(error, schema=ExperimentPortfolio.model_json_schema(),
                phase="output_payload", action="submit"))
        message = details[0]["message"] if details else "materialized experiment output requires correction"
        raise SemanticRuleViolation(message, details=details) from error
    validate_experiment_design_task_output(
        portfolio.model_dump(mode="json"), inputs, handoff
    )


def materialize_experiment_design_inputs(
    inputs: dict[str, bytes],
) -> tuple[ExperimentPortfolio, ExperimentPlanMaterializationReport]:
    if "experiment_design_intent" not in inputs:
        raise ValueError("experiment plan materialization requires intent")
    intent = HistoricalExperimentDesignIntent.model_validate_json(
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
        }
        if set(inputs) != required:
            raise ValueError(
                "scientific plan materialization requires intent, objective, and hypothesis portfolio"
            )
        objective = ResearchObjectiveContract.model_validate_json(
            inputs["research_objective"], strict=True
        )
    if intent.study_kind != "engineering":
        from .experiment import validate_experiment_input_objective
        validate_experiment_input_objective(inputs)
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


def _materialize_validation_plan(
    experiment_key: str,
    intent: IntentValidationPlan | None,
) -> ValidationPlan:
    if intent is None:
        raise ValueError("compact experiment intent requires validation_intent")
    dimensions: dict[str, ValidationDimensionPlan] = {}
    for dimension_name in ("numerical", "physical", "experimental"):
        dimension_intent = getattr(intent, dimension_name)
        checks = [
            ValidationCheck(
                check_key=item.check_key,
                observable=item.observable,
                metric=item.metric,
                evaluation_mode="deterministic_threshold",
                evaluator_profile=item.evaluator_profile,
                evaluator_metric=item.evaluator_metric,
                threshold=item.threshold,
                acceptance_condition=item.acceptance_condition,
                failure_action=item.failure_action,
                basis=item.basis,
            )
            for item in dimension_intent.deterministic_checks
        ]
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
    "IntentCase",
    "IntentCaseOverride",
    "IntentComparisonVariable",
    "IntentDeterministicValidationCheck",
    "IntentResourceEstimate",
    "IntentReviewedValidationCheck",
    "IntentValidationDimension",
    "IntentValidationPlan",
    "materialize_experiment_design_inputs",
    "materialize_experiment_design_intent",
    "validate_experiment_design_intent",
    "validate_experiment_design_intent_task_output",
]
