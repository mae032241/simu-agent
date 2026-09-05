"""Curve-specific diagnosis Operations and components."""

from __future__ import annotations

from typing import Any

from scidiscovery.artifact_agent.schema.common import canonical_json, canonical_sha256
from .analysis import (
    CurveDiagnosticAnalysisPackage,
    analyze_curve_error,
    failed_residual_analysis_available,
    validate_curve_error_plot_collection,
)
from .schema import (
    CurveBundle,
    CurveConsistencyReport,
    CurveExperimentContract,
    validate_curve_experiment_contract,
)
from scidiscovery.artifact_agent.schema.experiment import (
    ExperimentPortfolio,
    deterministic_validation_check_keys,
)
from scidiscovery.artifact_agent.schema.layered_diagnosis import (
    LayeredDiagnosisReport,
    validate_layered_diagnosis,
)
from scidiscovery.artifact_agent.schema.research_cycle import (
    ScientificReview,
    validate_scientific_review,
)
from scidiscovery.artifact_agent.schema.research_objective import (
    ResearchObjectiveContract,
)
from scidiscovery.operation_declaration import (
    OPERATION_AGENT_PREAMBLE,
    payload_validator,
    schema_resource,
    scientific_semantic_contract,
    scientific_agent_operation,
)
from scidiscovery.operation_contract import SemanticRuleViolation
from scidiscovery.operations.spec import (
    CallableComponent,
    CollectionSpec,
    ComponentRef,
    ComponentSpec,
    ExecutorRef,
    InputPortSpec,
    LimitsSpec,
    OperationDescription,
    OperationSpec,
    OutputPortSpec,
    ReviewSpec,
)


_GENERAL_SCIENCE = "general_science"
_GENERAL_RESOURCES = {
    "opaque_schema",
    "experiment_portfolio_schema",
    "hypothesis_schema",
    "scientific_review_schema",
    "research_objective_schema",
}


def _resource_ref(name: str) -> ComponentRef:
    return ComponentRef(
        name,
        plugin_id=_GENERAL_SCIENCE if name in _GENERAL_RESOURCES else None,
    )


BASE_TOOLS = tuple(
    ComponentRef(name, plugin_id="builtin")
    for name in (
        "file_write_begin_tool",
        "file_write_chunk_tool",
        "file_write_commit_tool",
    )
) + (
    ComponentRef("file_apply_patch_tool", plugin_id="builtin"),
)


_SCHEMA_RESOURCES = {
    "opaque": "opaque_schema",
    "scidiscovery.experiment-portfolio.v1": "experiment_portfolio_schema",
    "scidiscovery.research-objective.v1": "research_objective_schema",
    "scidiscovery.curve-experiment-contract.v1": "curve_contract_schema",
    "scidiscovery.scientific-review.v1": "scientific_review_schema",
    "scidiscovery.curve-consistency-report.v1": "metric_report_schema",
    "scidiscovery.curve-bundle.v1": "curve_bundle_schema",
    "scidiscovery.curve-diagnostic-analysis.v1": "curve_analysis_package_schema",
    "scidiscovery.layered-diagnosis.v1": "diagnosis_schema",
    "scidiscovery.hypothesis-proposal.v2": "hypothesis_schema",
}

_EVIDENCE_PATHS = {
    "scidiscovery.scientific-review.v1": ("/evidence",),
    "scidiscovery.layered-diagnosis.v1": ("/evidence",),
}


def _agent_marker() -> None:
    return None


def _curve_contract_context(
    payload: dict[str, Any], sources: dict[str, bytes], handoff: dict[str, Any]
) -> None:
    del handoff
    contract = CurveExperimentContract.model_validate_json(
        canonical_json(payload), strict=True
    )
    plan = ExperimentPortfolio.model_validate_json(
        sources["experiment_plan"], strict=True
    )
    validate_curve_experiment_contract(contract, plan)
    objective = ResearchObjectiveContract.model_validate_json(
        sources["research_objective"], strict=True
    )
    if plan.objective_key != objective.objective_key:
        raise SemanticRuleViolation("curve contract objective differs from the experiment plan")
    proposal = next(
        item for item in plan.proposals
        if item.experiment_key == contract.experiment_key
    )
    expected_targets = {
        item.target_key
        for item in objective.mandatory_targets
        if item.observable in set(proposal.required_observables)
    }
    actual_targets = {item.target_key for item in contract.objective_target_bindings}
    if actual_targets != expected_targets:
        raise SemanticRuleViolation(
            "curve objective bindings must cover the exact planned targets"
        )


def _curve_contract_review_context(
    payload: dict[str, Any], sources: dict[str, bytes], handoff: dict[str, Any]
) -> None:
    contract = CurveExperimentContract.model_validate_json(
        sources["curve_contract"], strict=True
    )
    plan = ExperimentPortfolio.model_validate_json(
        sources["experiment_plan"], strict=True
    )
    validate_curve_experiment_contract(contract, plan)
    objective = ResearchObjectiveContract.model_validate_json(
        sources["research_objective"], strict=True
    )
    if objective.objective_key != plan.objective_key:
        raise SemanticRuleViolation("curve review objective differs from the plan")
    proposal = next(
        item for item in plan.proposals
        if item.experiment_key == contract.experiment_key
    )
    expected_targets = {
        item.target_key
        for item in objective.mandatory_targets
        if item.observable in set(proposal.required_observables)
    }
    if {item.target_key for item in contract.objective_target_bindings} != expected_targets:
        raise SemanticRuleViolation(
            "reviewed curve contract does not bind the exact planned targets"
        )
    review = ScientificReview.model_validate_json(
        canonical_json(payload), strict=True
    )
    if review.review_target != "domain_contract":
        raise SemanticRuleViolation("curve contract review_target must be domain_contract")
    expected_verdict = "blocked" if review.verdict == "reject" else review.verdict
    if handoff.get("verdict") != expected_verdict:
        raise SemanticRuleViolation("curve contract review handoff differs from payload verdict")


def _nonempty(raw: bytes) -> None:
    if not raw:
        raise ValueError("collection item must not be empty")


def _input(
    name: str,
    description: str,
    schema: str,
    *,
    min_items: int = 1,
    max_items: int = 1,
    max_item_bytes: int = 1024 * 1024,
    exposure: str = "full",
    usage: str = "claim_evidence",
) -> InputPortSpec:
    return InputPortSpec(
        name=name,
        description=description,
        schema=schema,
        media_types=("application/json",),
        codec=ComponentRef("json_codec", plugin_id=_GENERAL_SCIENCE),
        schema_resource=_resource_ref(_SCHEMA_RESOURCES[schema]),
        min_items=min_items,
        max_items=max_items,
        max_item_bytes=max_item_bytes,
        exposure=exposure,
        usage=usage,
    )


def _review_input(name: str, description: str) -> InputPortSpec:
    return _input(
        name,
        description,
        "scidiscovery.scientific-review.v1",
        max_item_bytes=64 * 1024,
        exposure="handoff_only",
        usage="prior_signal",
    )


def _output(
    name: str,
    description: str,
    kind: str,
    schema: str,
    validator: ComponentRef,
    *,
    max_item_bytes: int,
    media_types: tuple[str, ...] = ("application/json",),
    min_items: int = 1,
    max_items: int = 1,
    collection: CollectionSpec | None = None,
    context_validator: ComponentRef | None = None,
    context_sources: tuple[str, ...] = (),
    semantic_contract: ComponentRef | None = None,
) -> OutputPortSpec:
    opaque = schema == "opaque"
    contract = semantic_contract or ComponentRef("diagnosis_semantic_contract")
    payload_rule, context_rule = {
        "diagnosis_semantic_contract": (
            "curve.diagnosis.report_consistency", "curve.diagnosis.input_binding"
        ),
        "figure_semantic_contract": (
            "curve.figure.manifest_consistency", "curve.figure.evidence_binding"
        ),
        "curve_contract_semantic_contract": (
            "curve.contract.case_metric_closure", "curve.contract.objective_binding"
        ),
        "curve_contract_review_contract": (
            "curve.review.verdict_consistency", "curve.review.subject_binding"
        ),
    }[contract.component_id]
    return OutputPortSpec(
        name=name,
        description=description,
        kind=kind,
        schema=schema,
        media_types=media_types,
        codec=ComponentRef(
            "opaque_codec" if opaque else "json_codec",
            plugin_id=_GENERAL_SCIENCE,
        ),
        schema_resource=_resource_ref(_SCHEMA_RESOURCES[schema]),
        min_items=min_items,
        max_items=max_items,
        max_item_bytes=max_item_bytes,
        validator=validator,
        validator_rule_id=payload_rule,
        semantic_contract=contract,
        collection=collection,
        context_validator=context_validator,
        context_rule_id=context_rule if context_validator else None,
        context_sources=context_sources,
        evidence_paths=_EVIDENCE_PATHS.get(schema, ()),
    )


def _diagnosis_operation(
    operation_id: str,
    purpose: str,
    applies_when: str,
    *,
    prompt: str,
) -> OperationSpec:
    return scientific_agent_operation(
        operation_id,
        purpose,
        applies_when,
        "Recomputing canonical metrics, parsing raw outputs, or modifying evidence.",
        agent=ComponentRef("diagnosis_agent"),
        workspace=ComponentRef("workspace", plugin_id=_GENERAL_SCIENCE),
        prompt=ComponentRef(prompt),
        tools=BASE_TOOLS,
        inputs=(
            _input(
                "experiment_plan",
                "Exact experiment portfolio.",
                "scidiscovery.experiment-portfolio.v1",
                max_item_bytes=2 * 1024 * 1024,
                usage="prior_signal",
            ),
            _input(
                "experiment_review",
                "Exact independent plan review.",
                "scidiscovery.scientific-review.v1",
                max_item_bytes=64 * 1024,
                usage="prior_signal",
                exposure="handoff_only",
            ),
            _input(
                "curve_contract",
                "Exact reviewed curve-domain contract.",
                "scidiscovery.curve-experiment-contract.v1",
                max_item_bytes=2 * 1024 * 1024,
                usage="prior_signal",
            ),
            _review_input(
                "curve_contract_review",
                "Exact independent review of the curve-domain contract.",
            ),
            _input(
                "metric_report",
                "Exact deterministic curve comparison report.",
                "scidiscovery.curve-consistency-report.v1",
                max_item_bytes=2 * 1024 * 1024,
            ),
            _input(
                "curve_bundle",
                "Optional canonical curve bundle.",
                "scidiscovery.curve-bundle.v1",
                min_items=0,
                max_item_bytes=8 * 1024 * 1024,
            ),
        ),
        outputs=(
            _output(
                "layered_diagnosis",
                "Layered diagnosis bound to exact curve inputs.",
                "layered_diagnosis",
                "scidiscovery.layered-diagnosis.v1",
                ComponentRef("diagnosis_validator"),
                max_item_bytes=128 * 1024,
                context_validator=ComponentRef("diagnosis_context"),
                context_sources=(
                    "experiment_plan",
                    "curve_contract",
                    "metric_report",
                    "curve_bundle",
                ),
            ),
        ),
        timeout=900,
        max_input_bytes=12 * 1024 * 1024,
        max_output_bytes=128 * 1024,
        max_files=1,
        consequence="scientific",
    )


def _curve_error_diagnosis_operation() -> OperationSpec:
    return scientific_agent_operation(
        "science.result.diagnose.curve-error.v1",
        "Interpret one deterministic curve-error analysis package.",
        "A deterministic curve-error analysis package localizes a failed residual metric.",
        "Recomputing analysis, producing plots, or changing exact scientific inputs.",
        agent=ComponentRef("diagnosis_agent"),
        workspace=ComponentRef("workspace", plugin_id=_GENERAL_SCIENCE),
        prompt=ComponentRef("curve_diagnosis_prompt"),
        tools=BASE_TOOLS,
        inputs=(
            _input(
                "curve_analysis_package",
                "Exact reproducible curve inputs and deterministic error localization.",
                "scidiscovery.curve-diagnostic-analysis.v1",
                max_item_bytes=12 * 1024 * 1024,
                usage="prior_signal",
            ),
        ),
        outputs=(
            _output(
                "layered_diagnosis",
                "Scientific interpretation of the fixed curve-error analysis.",
                "layered_diagnosis",
                "scidiscovery.layered-diagnosis.v1",
                ComponentRef("diagnosis_validator"),
                max_item_bytes=128 * 1024,
                context_validator=ComponentRef("curve_diagnosis_context"),
                context_sources=("curve_analysis_package",),
            ),
        ),
        timeout=900,
        max_input_bytes=12 * 1024 * 1024,
        max_output_bytes=128 * 1024,
        max_files=1,
        consequence="scientific",
    )


CURVE_CONTRACT_PROMPT = """Return exactly one RoleResultEnvelope whose payload is
the CurveExperimentContract required by output.schema.json. Translate the exact
generic experiment plan into a bounded curve-domain realization: declare only
needed series, axes, comparisons, interpolation, masks, operators, and exact
validation-check bindings. Do not change the plan's scientific choices,
thresholds, cases, or priority.
"""

CURVE_CONTRACT_REVIEW_PROMPT = """Return exactly one RoleResultEnvelope whose
payload is the ScientificReview required by output.schema.json. Independently
review the curve-domain contract against the exact generic experiment plan.
Use review_target domain_contract. Check series identity, case binding, units,
domains, operator semantics, and one-to-one validation binding. Do not mutate
either input or grant execution approval.
"""


def _curve_contract_operations() -> tuple[OperationSpec, ...]:
    design = scientific_agent_operation(
        "science.curve.contract.design.v1",
        "Realize one generic experiment as an explicit curve-domain contract.",
        "A reviewed generic experiment needs curve data and metric bindings.",
        "Changing generic scientific intent or running a curve evaluator.",
        agent=ComponentRef("curve_contract_agent"),
        workspace=ComponentRef("workspace", plugin_id=_GENERAL_SCIENCE),
        prompt=ComponentRef("curve_contract_prompt"),
        tools=BASE_TOOLS,
        inputs=(
            _input(
                "research_objective",
                "Exact objective for the scientific plan.",
                "scidiscovery.research-objective.v1",
                max_item_bytes=512 * 1024,
                usage="prior_signal",
            ),
            _input(
                "experiment_plan",
                "Exact generic experiment portfolio.",
                "scidiscovery.experiment-portfolio.v1",
                max_item_bytes=2 * 1024 * 1024,
                usage="prior_signal",
            ),
            _review_input(
                "experiment_review",
                "Exact independent review of the generic experiment plan.",
            ),
        ),
        outputs=(
            _output(
                "curve_contract",
                "Curve-domain realization of one experiment.",
                "domain_realization",
                "scidiscovery.curve-experiment-contract.v1",
                ComponentRef("curve_contract_validator"),
                max_item_bytes=2 * 1024 * 1024,
                context_validator=ComponentRef("curve_contract_context"),
                context_sources=("research_objective", "experiment_plan"),
                semantic_contract=ComponentRef("curve_contract_semantic_contract"),
            ),
        ),
        timeout=900,
        max_input_bytes=2 * 1024 * 1024,
        max_output_bytes=2 * 1024 * 1024,
        max_files=1,
        review=ReviewSpec(
            reviewer_operation="science.curve.contract.review.v1",
            reviewer_input_port="curve_contract",
            subject_outputs=("curve_contract",),
        ),
    )
    review = scientific_agent_operation(
        "science.curve.contract.review.v1",
        "Independently review a curve-domain contract against its generic plan.",
        "A curve contract needs domain review before deterministic use.",
        "Editing the contract or granting human execution approval.",
        agent=ComponentRef("curve_contract_reviewer"),
        workspace=ComponentRef("workspace", plugin_id=_GENERAL_SCIENCE),
        prompt=ComponentRef("curve_contract_review_prompt"),
        tools=BASE_TOOLS,
        inputs=(
            _input(
                "research_objective",
                "Exact objective for the scientific plan.",
                "scidiscovery.research-objective.v1",
                max_item_bytes=512 * 1024,
                usage="prior_signal",
            ),
            _input(
                "experiment_plan",
                "Exact generic experiment portfolio.",
                "scidiscovery.experiment-portfolio.v1",
                max_item_bytes=2 * 1024 * 1024,
                usage="prior_signal",
            ),
            _review_input(
                "experiment_review",
                "Exact independent review of the generic experiment plan.",
            ),
            _input(
                "curve_contract",
                "Exact curve-domain contract under review.",
                "scidiscovery.curve-experiment-contract.v1",
                max_item_bytes=2 * 1024 * 1024,
                usage="prior_signal",
            ),
        ),
        outputs=(
            _output(
                "scientific_review",
                "Independent curve-contract review.",
                "scientific_review",
                "scidiscovery.scientific-review.v1",
                ComponentRef("scientific_review_validator"),
                max_item_bytes=64 * 1024,
                context_validator=ComponentRef("curve_contract_review_context"),
                context_sources=(
                    "research_objective",
                    "experiment_plan",
                    "curve_contract",
                ),
                semantic_contract=ComponentRef("curve_contract_review_contract"),
            ),
        ),
        timeout=600,
        max_input_bytes=4 * 1024 * 1024,
        max_output_bytes=64 * 1024,
        max_files=1,
    )
    return design, review


AGENT_OPERATIONS = (
    *_curve_contract_operations(),
    _diagnosis_operation(
        "science.result.diagnose.v1",
        "Interpret deterministic curve metrics against the pre-registered plan.",
        "A complete plan and deterministic curve metric report are available.",
        prompt="diagnosis_prompt",
    ),
    _curve_error_diagnosis_operation(),
)


def _diagnosis_context(
    payload: dict[str, Any], sources: dict[str, bytes], handoff: dict[str, Any]
) -> None:
    del handoff
    diagnosis = LayeredDiagnosisReport.model_validate_json(
        canonical_json(payload), strict=True
    )
    allowed_inputs = (
        {"experiment_plan", "curve_contract", "metric_report"},
        {"experiment_plan", "curve_contract", "metric_report", "curve_bundle"},
    )
    if set(sources) not in allowed_inputs:
        raise SemanticRuleViolation(
            "curve diagnosis requires experiment_plan, curve_contract, metric_report, "
            "and at most curve_bundle"
        )
    portfolio = ExperimentPortfolio.model_validate_json(
        sources["experiment_plan"], strict=True
    )
    contract = CurveExperimentContract.model_validate_json(
        sources["curve_contract"], strict=True
    )
    metric_report = CurveConsistencyReport.model_validate_json(
        sources["metric_report"], strict=True
    )
    _validate_diagnosis_against(diagnosis, portfolio, contract, metric_report)
    curve_bundle_raw = sources.get("curve_bundle")
    if curve_bundle_raw is not None:
        CurveBundle.model_validate_json(curve_bundle_raw, strict=True)
        if failed_residual_analysis_available(portfolio, contract, metric_report):
            raise SemanticRuleViolation(
                "analyzable residual failure requires the curve-error diagnosis operation"
            )


def _curve_diagnosis_context(
    payload: dict[str, Any], sources: dict[str, bytes], handoff: dict[str, Any]
) -> None:
    del handoff
    if set(sources) != {"curve_analysis_package"}:
        raise SemanticRuleViolation("curve-error diagnosis requires one exact analysis package")
    package = CurveDiagnosticAnalysisPackage.model_validate_json(
        sources["curve_analysis_package"], strict=True
    )
    diagnosis = LayeredDiagnosisReport.model_validate_json(
        canonical_json(payload), strict=True
    )
    _validate_diagnosis_against(
        diagnosis,
        package.experiment_plan,
        package.curve_contract,
        package.metric_report,
    )


def _validate_diagnosis_against(
    diagnosis: LayeredDiagnosisReport,
    portfolio: ExperimentPortfolio,
    contract: CurveExperimentContract,
    metric_report: CurveConsistencyReport,
) -> None:
    validate_curve_experiment_contract(contract, portfolio)
    if portfolio.objective_key is None:
        if diagnosis.objective_assessment is not None:
            raise SemanticRuleViolation(
                "objective_assessment is not admissible without plan objective_key"
            )
    else:
        assessment = diagnosis.objective_assessment
        if assessment is None or assessment.objective_key != portfolio.objective_key:
            raise SemanticRuleViolation("diagnosis objective assessment differs from the plan")
        comparisons = tuple(
            item
            for item in metric_report.comparisons
            if item.gate_scope == "objective" and item.purpose == "target_fit"
        )
        if assessment.comparison_keys != tuple(
            item.comparison_key for item in comparisons
        ):
            raise SemanticRuleViolation(
                "objective_assessment must name the exact target-fit comparisons"
            )
        if diagnosis.gates.prerequisite_status == "invalid":
            expected_status = "not_evaluable"
        else:
            statuses = {item.status for item in comparisons if item.required}
            expected_status = (
                "fail"
                if "fail" in statuses
                else "inconclusive"
                if not statuses or statuses & {"unavailable", "inconclusive"}
                else "pass"
            )
        if assessment.status != expected_status:
            raise SemanticRuleViolation(
                "objective assessment status differs from exact target-fit metrics"
            )
    plans = tuple(
        plan
        for plan in portfolio.validation_plans
        if plan.experiment_key == diagnosis.experiment_key
        and plan.plan_key == diagnosis.plan_key
    )
    if len(plans) != 1:
        raise SemanticRuleViolation("diagnosis does not name one exact validation plan")
    plan = plans[0]
    if metric_report.validation_scope != "complete_plan":
        raise SemanticRuleViolation("diagnosis requires a complete-plan metric report")
    if metric_report.validation_plan_sha256 != canonical_sha256(plan):
        raise SemanticRuleViolation("metric report validation-plan digest differs")
    if metric_report.covered_validation_check_keys != deterministic_validation_check_keys(
        plan
    ):
        raise SemanticRuleViolation("metric report does not cover every exact validation check")


def _curve_error_analysis(
    values: dict[str, tuple[bytes, ...]],
) -> dict[str, tuple[bytes, ...]]:
    required = (
        "experiment_plan",
        "experiment_review",
        "curve_contract",
        "curve_contract_review",
        "metric_report",
        "curve_bundle",
    )
    if set(values) != set(required) or any(len(values[name]) != 1 for name in required):
        raise ValueError("curve error analysis inputs violate their cardinality")
    portfolio = ExperimentPortfolio.model_validate_json(
        values["experiment_plan"][0], strict=True
    )
    contract = CurveExperimentContract.model_validate_json(
        values["curve_contract"][0], strict=True
    )
    metric_report = CurveConsistencyReport.model_validate_json(
        values["metric_report"][0], strict=True
    )
    bundle = CurveBundle.model_validate_json(values["curve_bundle"][0], strict=True)
    artifacts = analyze_curve_error(portfolio, contract, metric_report, bundle)
    package = CurveDiagnosticAnalysisPackage(
        experiment_plan=portfolio,
        curve_contract=contract,
        metric_report=metric_report,
        curve_bundle=bundle,
        curve_analysis=artifacts.report,
    )
    plots = dict(artifacts.plots)
    if sum(len(content) for content in plots.values()) > 8 * 1024 * 1024:
        raise ValueError("curve analysis plot collection exceeds its declared limit")
    validate_curve_error_plot_collection(
        package.model_dump(mode="json"), plots
    )
    return {
        "curve_analysis_package": (package.canonical_json(),),
        "curve_analysis_plots": tuple(plots.values()),
    }


DIAGNOSIS_PROMPT = """Return exactly one RoleResultEnvelope whose payload is the
LayeredDiagnosisReport required by output.schema.json. Interpret the supplied
deterministic curve reports against the exact experiment plan. Stop at the
earliest failed or inconclusive prerequisite. Never recompute metrics, reparse
raw solver outputs, repair files, or author state transitions.
"""


class Resources:
    diagnosis_schema = schema_resource(
        LayeredDiagnosisReport, "scidiscovery.layered-diagnosis.v1"
    )
    curve_analysis_package_schema = schema_resource(
        CurveDiagnosticAnalysisPackage,
        "scidiscovery.curve-diagnostic-analysis.v1",
    )
    diagnosis_semantic_contract = scientific_semantic_contract(
        "curve.diagnosis",
        "Bind the diagnosis to the exact plan and deterministic curve report.",
        "Interpret deterministic results without recomputing metrics.",
        payload_rule_id="curve.diagnosis.report_consistency",
        context_rule_id="curve.diagnosis.input_binding",
    )
    figure_semantic_contract = scientific_semantic_contract(
        "curve.figure",
        "Curve-analysis images are deterministic supporting outputs, not evidence by themselves.",
        "Figure manifests, attachments, media types, hashes, and deterministic reports must bind exactly.",
        "Series identity, calibration, and missing visual support must never be inferred silently.",
        payload_rule_id="curve.figure.manifest_consistency",
        context_rule_id="curve.figure.evidence_binding",
    )
    curve_contract_semantic_contract = scientific_semantic_contract(
        "curve.contract",
        "Realize curve data and metric bindings without changing the generic experiment.",
        "Every threshold and case must bind exactly to the supplied experiment plan.",
        required_inputs=("research_objective", "experiment_plan"),
        payload_constraint=(
            "Every curve case, series, extraction rule, metric binding, and threshold "
            "must form a closed deterministic comparison contract."
        ),
        context_constraint=(
            "Objective, case, metric, and threshold identities must match the exact "
            "research objective and experiment plan."
        ),
        payload_rule_id="curve.contract.case_metric_closure",
        context_rule_id="curve.contract.objective_binding",
    )
    curve_contract_review_contract = scientific_semantic_contract(
        "curve.review",
        "Review the complete curve contract independently without mutating it.",
        "The verdict is scientific review, not human approval.",
        required_inputs=(
            "research_objective",
            "experiment_plan",
            "curve_contract",
        ),
        context_constraint=(
            "The review must bind the exact research objective, experiment plan, and "
            "complete curve contract."
        ),
        payload_rule_id="curve.review.verdict_consistency",
        context_rule_id="curve.review.subject_binding",
    )
    curve_contract_prompt = OPERATION_AGENT_PREAMBLE + CURVE_CONTRACT_PROMPT
    curve_contract_review_prompt = (
        OPERATION_AGENT_PREAMBLE + CURVE_CONTRACT_REVIEW_PROMPT
    )
    diagnosis_prompt = OPERATION_AGENT_PREAMBLE + DIAGNOSIS_PROMPT
    curve_diagnosis_prompt = OPERATION_AGENT_PREAMBLE + """Return exactly one
RoleResultEnvelope whose payload is the LayeredDiagnosisReport required by
output.schema.json. Interpret the supplied immutable curve-analysis package,
stopping at the earliest failed prerequisite. The package's metric values,
localized residuals, and plot identities are deterministic facts: do not
recompute or alter them. Do not mutate evidence or author state transitions.
"""


class Components:
    diagnosis_validator = CallableComponent(
        "validator", payload_validator(validate_layered_diagnosis)
    )
    diagnosis_context = CallableComponent("validator", _diagnosis_context)
    curve_diagnosis_context = CallableComponent(
        "validator", _curve_diagnosis_context
    )
    curve_analysis_package_validator = CallableComponent(
        "validator",
        lambda raw: CurveDiagnosticAnalysisPackage.model_validate_json(
            raw, strict=True
        ),
    )
    diagnosis_agent = CallableComponent("agent", _agent_marker)
    curve_contract_agent = CallableComponent("agent", _agent_marker)
    curve_contract_reviewer = CallableComponent("agent", _agent_marker)
    curve_contract_context = CallableComponent("validator", _curve_contract_context)
    curve_contract_review_context = CallableComponent(
        "validator", _curve_contract_review_context
    )
    scientific_review_validator = CallableComponent(
        "validator", payload_validator(validate_scientific_review)
    )
    curve_error_analysis = CallableComponent("transform", _curve_error_analysis)


def _curve_error_analysis_operation() -> OperationSpec:
    return OperationSpec(
        operation_id="science.curve.error.analyze.v1",
        version="1",
        catalog_scope="support",
        description=OperationDescription(
            purpose="Reproduce failed residual metrics and localize their curve error.",
            applies_when="A reviewed curve contract, complete metric report, and exact curve bundle are available.",
            not_for="Authoring scientific diagnoses or proposing the next experiment.",
        ),
        executor=ExecutorRef(
            kind="transform",
            component=ComponentRef("curve_error_analysis"),
        ),
        inputs=(
            _input(
                "experiment_plan",
                "Exact experiment portfolio.",
                "scidiscovery.experiment-portfolio.v1",
                max_item_bytes=2 * 1024 * 1024,
                usage="prior_signal",
            ),
            _input(
                "experiment_review",
                "Exact independent plan review.",
                "scidiscovery.scientific-review.v1",
                max_item_bytes=64 * 1024,
                exposure="handoff_only",
                usage="prior_signal",
            ),
            _input(
                "curve_contract",
                "Exact reviewed curve-domain contract.",
                "scidiscovery.curve-experiment-contract.v1",
                max_item_bytes=2 * 1024 * 1024,
                usage="prior_signal",
            ),
            _review_input(
                "curve_contract_review",
                "Exact independent review of the curve-domain contract.",
            ),
            _input(
                "metric_report",
                "Exact deterministic curve comparison report.",
                "scidiscovery.curve-consistency-report.v1",
                max_item_bytes=2 * 1024 * 1024,
            ),
            _input(
                "curve_bundle",
                "Canonical curve bundle for residual localization.",
                "scidiscovery.curve-bundle.v1",
                max_item_bytes=8 * 1024 * 1024,
            ),
        ),
        outputs=(
            _output(
                "curve_analysis_package",
                "Exact inputs and reproducible deterministic curve-error analysis.",
                "curve_diagnostic_analysis",
                "scidiscovery.curve-diagnostic-analysis.v1",
                ComponentRef("curve_analysis_package_validator"),
                max_item_bytes=12 * 1024 * 1024,
                semantic_contract=ComponentRef("diagnosis_semantic_contract"),
            ),
            _output(
                "curve_analysis_plots",
                "Deterministic residual plots bound to the analysis package.",
                "curve_error_plot",
                "opaque",
                ComponentRef("nonempty_validator"),
                max_item_bytes=1024 * 1024,
                media_types=("image/png",),
                min_items=1,
                max_items=8,
                collection=CollectionSpec(
                    max_total_bytes=8 * 1024 * 1024,
                ),
            ),
        ),
        consequence="scientific",
        limits=LimitsSpec(
            timeout_seconds=120,
            max_input_bytes=12 * 1024 * 1024,
            max_output_bytes=20 * 1024 * 1024,
            max_files=9,
        ),
    )


TRANSFORM_OPERATIONS = (
    _curve_error_analysis_operation(),
)


def component_specs() -> tuple[ComponentSpec, ...]:
    values = [
        ComponentSpec(
            "diagnosis_validator",
            "validator",
            "curve_score.science_operations:Components.diagnosis_validator",
            resources=(ComponentRef("diagnosis_semantic_contract"),),
        ),
        ComponentSpec(
            "diagnosis_context",
            "validator",
            "curve_score.science_operations:Components.diagnosis_context",
            resources=(ComponentRef("diagnosis_semantic_contract"),),
        ),
        ComponentSpec(
            "curve_diagnosis_context",
            "validator",
            "curve_score.science_operations:Components.curve_diagnosis_context",
            resources=(ComponentRef("diagnosis_semantic_contract"),),
        ),
        ComponentSpec(
            "curve_analysis_package_validator",
            "validator",
            "curve_score.science_operations:Components.curve_analysis_package_validator",
            resources=(ComponentRef("diagnosis_semantic_contract"),),
        ),
        ComponentSpec(
            "diagnosis_agent",
            "agent",
            "curve_score.science_operations:Components.diagnosis_agent",
        ),
        ComponentSpec(
            "curve_contract_agent",
            "agent",
            "curve_score.science_operations:Components.curve_contract_agent",
        ),
        ComponentSpec(
            "curve_contract_reviewer",
            "agent",
            "curve_score.science_operations:Components.curve_contract_reviewer",
        ),
        ComponentSpec(
            "curve_contract_context",
            "validator",
            "curve_score.science_operations:Components.curve_contract_context",
            resources=(ComponentRef("curve_contract_semantic_contract"),),
        ),
        ComponentSpec(
            "curve_contract_review_context",
            "validator",
            "curve_score.science_operations:Components.curve_contract_review_context",
            resources=(ComponentRef("curve_contract_review_contract"),),
        ),
        ComponentSpec(
            "scientific_review_validator",
            "validator",
            "curve_score.science_operations:Components.scientific_review_validator",
            resources=(ComponentRef("curve_contract_review_contract"),),
        ),
        ComponentSpec(
            "curve_error_analysis",
            "transform",
            "curve_score.science_operations:Components.curve_error_analysis",
            configuration_identity="curve-error-analysis:v1",
        ),
        ComponentSpec(
            "nonempty_validator",
            "validator",
            "curve_score.science_operations:_NONEMPTY_COMPONENT",
            resources=(ComponentRef("diagnosis_semantic_contract"),),
        ),
    ]
    for name in (
        "diagnosis_schema",
        "curve_analysis_package_schema",
        "diagnosis_semantic_contract",
        "diagnosis_prompt",
        "curve_diagnosis_prompt",
        "curve_contract_semantic_contract",
        "curve_contract_review_contract",
        "curve_contract_prompt",
        "curve_contract_review_prompt",
    ):
        values.append(
            ComponentSpec(
                name,
                "resource",
                f"curve_score.science_operations:Resources.{name}",
            )
        )
    return tuple(values)


_NONEMPTY_COMPONENT = CallableComponent("validator", _nonempty)
COMPONENT_SPECS = component_specs()
OPERATIONS = AGENT_OPERATIONS + TRANSFORM_OPERATIONS

__all__ = ["COMPONENT_SPECS", "OPERATIONS"]
