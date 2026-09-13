"""Deterministic compilation of the mechanical curve-contract fields."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from scidiscovery.artifact_agent.operation_tool_context import OperationToolContext
from scidiscovery.artifact_agent.schema.common import Identifier
from scidiscovery.artifact_agent.schema.experiment import ExperimentPortfolio
from scidiscovery.artifact_agent.schema.research_objective import (
    ResearchObjectiveContract,
)
from scidiscovery.artifact_agent.schema.role_result import RoleHandoff, RoleResultEnvelope
from scidiscovery.artifact_agent.service.local_workspace import (
    write_control_workspace_file,
)
from scidiscovery.operation_contract import SemanticRuleViolation
from scidiscovery.operations.tooling import WorkerToolDefinition

from .schema import (
    CurveBundle,
    CurveComparison,
    CurveComparisonSpec,
    CurveDomain,
    CurveExperimentContract,
    CurveInterval,
    CurveObjectiveTargetBinding,
    CurveOperatorSpec,
    CurveReferenceDisposition,
    CurveSeries,
    CurveSeriesDeclaration,
    CurveThreshold,
    validate_curve_experiment_contract,
)
from .transform_adapter import CURVE_SCORE_OPERATION


class _IntentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CurveTargetBindingIntent(_IntentModel):
    target_key: Identifier
    reference_series_key: Identifier
    validation_check_keys: Annotated[
        tuple[Identifier, ...], Field(max_length=64)
    ] = ()


class CurveContractCompileInput(_IntentModel):
    """Only the scientific choices that cannot be copied or calculated."""

    experiment_key: Identifier
    target_bindings: Annotated[
        tuple[CurveTargetBindingIntent, ...], Field(min_length=1, max_length=128)
    ]
    candidate_case_keys: Annotated[
        tuple[Identifier, ...], Field(min_length=1, max_length=10000)
    ]
    comparison_metric: Literal[
        "residual_rms", "residual_max_abs", "mean_signed_difference"
    ]

    @model_validator(mode="after")
    def _identities_are_unique(self) -> CurveContractCompileInput:
        keys = tuple(item.target_key for item in self.target_bindings)
        if len(keys) != len(set(keys)):
            raise ValueError("curve contract target bindings must be unique")
        return self


def compile_curve_contract(
    request: CurveContractCompileInput,
    *,
    objective: ResearchObjectiveContract,
    portfolio: ExperimentPortfolio,
    reference_bundle: CurveBundle,
) -> CurveExperimentContract:
    """Expand a small semantic selection into the existing v1 wire contract."""

    validate_curve_contract_inputs(objective, portfolio)
    return _compile_curve_contract(request, objective=objective, portfolio=portfolio,
                                   reference_bundle=reference_bundle)


def validate_curve_contract_inputs(
    objective: ResearchObjectiveContract, portfolio: ExperimentPortfolio,
) -> None:
    if portfolio.objective_key != objective.objective_key:
        raise SemanticRuleViolation(
            "curve contract objective differs from the experiment plan"
        )


def _compile_curve_contract(
    request: CurveContractCompileInput, *, objective: ResearchObjectiveContract,
    portfolio: ExperimentPortfolio, reference_bundle: CurveBundle,
) -> CurveExperimentContract:
    """Compile scientific selections against inputs already admitted by the caller."""
    proposals = tuple(
        item
        for item in portfolio.proposals
        if item.experiment_key == request.experiment_key
    )
    plans = tuple(
        item
        for item in portfolio.validation_plans
        if item.experiment_key == request.experiment_key
    )
    if len(proposals) != 1 or len(plans) != 1:
        raise SemanticRuleViolation(
            "curve contract must select one exact experiment and validation plan"
        )
    proposal, validation_plan = proposals[0], plans[0]
    bindings = {item.target_key: item for item in request.target_bindings}
    if not set(bindings).issubset(
        item.target_key for item in objective.mandatory_targets
    ):
        raise SemanticRuleViolation(
            "curve target_bindings names an unknown objective target_key"
        )
    selected_targets = tuple(
        item
        for item in objective.mandatory_targets
        if item.target_key in bindings
    )
    references = {item.series_key: item for item in reference_bundle.series}
    if not set(item.reference_series_key for item in request.target_bindings).issubset(
        references
    ):
        raise SemanticRuleViolation(
            "curve target binding names a missing reference series"
        )

    requested_cases = set(request.candidate_case_keys)
    cases = tuple(item for item in proposal.cases if item.case_key in requested_cases)
    if {item.case_key for item in cases} != requested_cases:
        raise SemanticRuleViolation("curve contract names an unknown experiment case")

    declarations: list[CurveSeriesDeclaration] = []
    comparisons: list[CurveComparison] = []
    comparison_observables: dict[str, str] = {}
    comparison_check_keys: dict[str, tuple[str, ...]] = {}
    target_contracts: list[CurveObjectiveTargetBinding] = []
    dispositions: list[CurveReferenceDisposition] = []

    for target in selected_targets:
        target_binding = bindings[target.target_key]
        reference = references[target_binding.reference_series_key]
        domains = _reference_domains(reference)
        declarations.append(
            CurveSeriesDeclaration(
                series_key=reference.series_key,
                case_key=reference.case_key,
                role=reference.role,
                scientific_role="experimental_target",
                source="reference_input",
                x_axis=reference.x_axis,
                y_axis=reference.y_axis,
                min_points=2,
                max_points=max(2, len(reference.points)),
            )
        )
        target_contracts.append(
            CurveObjectiveTargetBinding(
                target_key=target.target_key,
                reference_series_key=reference.series_key,
                required_domains=domains,
            )
        )
        dispositions.append(
            CurveReferenceDisposition(
                series_key=reference.series_key,
                disposition="compare",
                rationale=(
                    "The selected objective target is compared on the exact "
                    "continuous support declared by its immutable reference curve."
                ),
            )
        )
        for case in cases:
            candidate_key = _identifier(
                "series.candidate", case.case_key, target.target_key
            )
            declarations.append(
                CurveSeriesDeclaration(
                    series_key=candidate_key,
                    case_key=case.case_key,
                    role=_identifier("target", target.target_key),
                    scientific_role="simulation_candidate",
                    source="solver_output",
                    x_axis=reference.x_axis,
                    y_axis=reference.y_axis,
                )
            )
            for domain_index, domain in enumerate(domains, start=1):
                stem = _identifier(
                    "comparison",
                    case.case_key,
                    target.target_key,
                    f"support_{domain_index:03d}",
                )
                comparisons.append(
                    CurveComparison(
                        comparison_key=stem,
                        reference_series=reference.series_key,
                        candidate_series=candidate_key,
                        domain=domain,
                        interpolation=(
                            "log10_y"
                            if reference.y_axis.scale == "log10"
                            else "linear_y"
                        ),
                        evaluation_points=_domain_point_count(reference, domain),
                        operators=(
                            CurveOperatorSpec(
                                operator_key=_identifier(
                                    stem, request.comparison_metric
                                ),
                                kind=request.comparison_metric,
                                value_space=(
                                    "log10"
                                    if reference.y_axis.scale == "log10"
                                    else "linear"
                                ),
                            ),
                        ),
                        required=True,
                        purpose="target_fit",
                        gate_scope="objective",
                        metric_profile="smooth_curve",
                    )
                )
                comparison_observables[stem] = target.observable
                comparison_check_keys[stem] = target_binding.validation_check_keys

    comparisons = _bind_curve_score_checks(
        comparisons,
        validation_plan,
        comparison_observables=comparison_observables,
        comparison_check_keys=comparison_check_keys,
    )
    contract = CurveExperimentContract(
        experiment_key=proposal.experiment_key,
        comparison_spec=CurveComparisonSpec(
            spec_key=_identifier("curve_contract", proposal.experiment_key),
            series_declarations=tuple(declarations),
            comparisons=tuple(comparisons),
            reference_dispositions=tuple(dispositions),
        ),
        objective_target_bindings=tuple(target_contracts),
    )
    validate_curve_experiment_contract(
        contract,
        portfolio,
        expected_evaluator_profile=CURVE_SCORE_OPERATION,
    )
    return contract


def validate_compiled_curve_contract(
    contract: CurveExperimentContract,
    *,
    objective: ResearchObjectiveContract,
    portfolio: ExperimentPortfolio,
    reference_bundle: CurveBundle,
) -> None:
    """Require submitted mechanical fields to equal the compiler output."""

    proposal = next(
        (
            item
            for item in portfolio.proposals
            if item.experiment_key == contract.experiment_key
        ),
        None,
    )
    if proposal is None:
        raise SemanticRuleViolation("curve contract experiment is absent from the plan")
    declared_cases = {
        item.case_key
        for item in contract.comparison_spec.series_declarations
        if item.source == "solver_output"
    }
    request = CurveContractCompileInput(
        experiment_key=contract.experiment_key,
        target_bindings=tuple(
            CurveTargetBindingIntent(
                target_key=item.target_key,
                reference_series_key=item.reference_series_key,
                validation_check_keys=_target_validation_check_keys(
                    contract, item.target_key
                ),
            )
            for item in contract.objective_target_bindings
        ),
        candidate_case_keys=tuple(
            item.case_key for item in proposal.cases if item.case_key in declared_cases
        ),
        comparison_metric=contract.comparison_spec.comparisons[0].operators[0].kind,
    )
    expected = _compile_curve_contract(
        request,
        objective=objective,
        portfolio=portfolio,
        reference_bundle=reference_bundle,
    )
    if contract.canonical_json() != expected.canonical_json():
        raise SemanticRuleViolation(
            "curve contract mechanical fields differ from deterministic compilation"
        )


def _reference_domains(series: CurveSeries) -> tuple[CurveDomain, ...]:
    if series.availability.status != "available" or len(series.points) < 2:
        raise SemanticRuleViolation(
            f"curve reference series is unavailable: {series.series_key}"
        )
    intervals = series.valid_intervals
    if not intervals:
        low = min(item.x for item in series.points)
        high = max(item.x for item in series.points)
        if low >= high:
            raise SemanticRuleViolation(
                f"curve reference series has no finite x span: {series.series_key}"
            )
        intervals = (CurveInterval(start=low, stop=high),)
    supported_intervals = list(intervals)
    for exclusion in series.exclusions:
        remaining: list[CurveInterval] = []
        for interval in supported_intervals:
            if exclusion.stop <= interval.start or exclusion.start >= interval.stop:
                remaining.append(interval)
                continue
            if interval.start < exclusion.start:
                remaining.append(
                    CurveInterval(start=interval.start, stop=exclusion.start)
                )
            if exclusion.stop < interval.stop:
                remaining.append(CurveInterval(start=exclusion.stop, stop=interval.stop))
        supported_intervals = remaining
    domains = tuple(
        CurveDomain(
            start=item.start,
            stop=item.stop,
            unit=series.x_axis.unit,
            min_points=2,
        )
        for item in supported_intervals
        if _domain_point_count_raw(series, item.start, item.stop) >= 2
    )
    if not domains:
        raise SemanticRuleViolation(
            f"curve reference series has no two-point continuous support: {series.series_key}"
        )
    return domains


def _domain_point_count(series: CurveSeries, domain: CurveDomain) -> int:
    return max(2, _domain_point_count_raw(series, domain.start, domain.stop))


def _domain_point_count_raw(series: CurveSeries, start: float, stop: float) -> int:
    return sum(start <= item.x <= stop for item in series.points)


def _bind_curve_score_checks(
    comparisons,
    validation_plan,
    *,
    comparison_observables: dict[str, str],
    comparison_check_keys: dict[str, tuple[str, ...]],
):
    checks = tuple(
        check
        for dimension in (
            validation_plan.numerical,
            validation_plan.physical,
            validation_plan.experimental,
        )
        for check in dimension.checks
        if check.evaluation_mode == "deterministic_threshold"
        and check.evaluator_profile == CURVE_SCORE_OPERATION
    )
    checks_by_key = {item.check_key: item for item in checks}
    explicitly_bound = {
        key for keys in comparison_check_keys.values() for key in keys
    }
    if explicitly_bound and explicitly_bound != set(checks_by_key):
        raise SemanticRuleViolation(
            "curve target bindings must cover every curve-score validation check"
        )
    if not checks:
        return comparisons
    compiled = []
    for comparison in comparisons:
        operators = list(comparison.operators)
        selected = comparison_check_keys[comparison.comparison_key]
        comparison_checks = (
            tuple(checks_by_key[key] for key in dict.fromkeys(selected))
            if explicitly_bound
            else tuple(
                check
                for check in checks
                if check.observable
                == comparison_observables[comparison.comparison_key]
            )
        )
        for check in comparison_checks:
            if check.evaluator_metric not in {
                "residual_rms",
                "residual_max_abs",
                "mean_signed_difference",
            }:
                raise SemanticRuleViolation(
                    f"curve-score check requires parameters absent from the plan: {check.check_key}"
                )
            assert check.threshold is not None
            if check.threshold.operator not in {"le", "ge"}:
                raise SemanticRuleViolation(
                    f"curve-score threshold is not representable by v1: {check.check_key}"
                )
            replacement = CurveOperatorSpec(
                operator_key=_identifier(comparison.comparison_key, check.check_key),
                validation_check_key=check.check_key,
                kind=check.evaluator_metric,
                value_space=(
                    "log10" if comparison.interpolation == "log10_y" else "linear"
                ),
                threshold=CurveThreshold(
                    comparison=check.threshold.operator,
                    value=check.threshold.value,
                    unit=check.threshold.unit,
                ),
            )
            replace_index = next(
                (
                    index
                    for index, item in enumerate(operators)
                    if item.kind == check.evaluator_metric
                    and item.validation_check_key is None
                ),
                None,
            )
            if replace_index is None:
                operators.append(replacement)
            else:
                operators[replace_index] = replacement
        compiled.append(comparison.model_copy(update={"operators": tuple(operators)}))
    expected_check_keys = {item.check_key for item in checks}
    bound_check_keys = {
        item.validation_check_key
        for comparison in compiled
        for item in comparison.operators
        if item.validation_check_key is not None
    }
    if bound_check_keys != expected_check_keys:
        raise SemanticRuleViolation(
            "curve contract did not bind every curve-score validation check"
        )
    return compiled


def _target_validation_check_keys(
    contract: CurveExperimentContract, target_key: str
) -> tuple[str, ...]:
    declarations = {
        item.series_key: item for item in contract.comparison_spec.series_declarations
    }
    target_role = _identifier("target", target_key)
    keys: list[str] = []
    for comparison in contract.comparison_spec.comparisons:
        candidate = declarations[comparison.candidate_series]
        if candidate.role != target_role:
            continue
        for operator in comparison.operators:
            key = operator.validation_check_key
            if key is not None and key not in keys:
                keys.append(key)
    return tuple(keys)


def _identifier(prefix: str, *parts: str) -> str:
    value = ".".join((prefix, *parts))
    if len(value) > 256:
        raise SemanticRuleViolation("compiled curve identifier exceeds 256 characters")
    return value


def _compile_for_worker(
    request: BaseModel, context: OperationToolContext
) -> dict[str, object]:
    if not isinstance(request, CurveContractCompileInput):
        raise ValueError("curve contract compiler request has the wrong type")
    try:
        contract = compile_curve_contract(
            request,
            objective=ResearchObjectiveContract.model_validate_json(
                context.read_input("research_objective"), strict=True
            ),
            portfolio=ExperimentPortfolio.model_validate_json(
                context.read_input("experiment_plan"), strict=True
            ),
            reference_bundle=CurveBundle.model_validate_json(
                context.read_input("reference_bundle"), strict=True
            ),
        )
    except (SemanticRuleViolation, ValidationError) as error:
        return {
            "state": "rejected",
            "diagnostics": [
                {
                    "path": "$",
                    "message": str(error)[:4096],
                    "type": "semantic_selection_invalid",
                }
            ],
        }
    envelope = RoleResultEnvelope[CurveExperimentContract](
        schema_version=1,
        handoff=RoleHandoff(
            verdict="pass",
            summary=(
                "The curve contract was deterministically compiled from the exact "
                "plan, objective, reference bundle, and bounded semantic selection."
            ),
        ),
        payload=contract,
    ).canonical_json()
    write_control_workspace_file(
        context.workspace,
        Path("output/result.json"),
        envelope,
        replace=True,
        mode=0o600,
    )
    context.validate_outputs()
    return {
        "state": "ready",
        "relative_path": "output/result.json",
        "sha256": hashlib.sha256(envelope).hexdigest(),
        "series_count": len(contract.comparison_spec.series_declarations),
        "comparison_count": len(contract.comparison_spec.comparisons),
    }


CURVE_CONTRACT_COMPILER_TOOL = WorkerToolDefinition(
    name="worker_curve_contract_compile",
    description=(
        "Compile the complete v1 curve contract from one experiment key, exact "
        "objective-target/reference-series bindings, candidate case keys, and one "
        "supported residual metric. "
        "The tool copies axes and units, calculates support domains and counts, "
        "creates identifiers and operators, writes output/result.json, and validates it."
    ),
    input_model=CurveContractCompileInput,
    capability="curve.contract.compile",
    contextual_handler=_compile_for_worker,
)


__all__ = [
    "CURVE_CONTRACT_COMPILER_TOOL",
    "CurveContractCompileInput",
    "CurveTargetBindingIntent",
    "compile_curve_contract",
    "validate_compiled_curve_contract",
]
