"""Single TCAD plugin declaration for Agent operations and their narrow parts."""

from __future__ import annotations

from scidiscovery.operations.input_validation import parse_bound_json

import json
from typing import Annotated, Any, Callable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.service.local_workspace import WorkspaceError
from scidiscovery.artifact_agent.service.run_outputs import RunOutputError
from scidiscovery.operation_contract import SemanticRuleViolation
from scidiscovery.operations.input_validation import OperationInvocationError
from scidiscovery.operation_declaration import semantic_contract, with_user_context
from .device_parameters import (
    DeviceParameterCoverageReport,
    DeviceParameterRequirementSet,
    DeviceParameterSet,
    EvidenceSourceCatalog,
    ParameterUncertaintyProjection,
)
from scidiscovery.artifact_agent.schema.execution import ExecutionRequest
from scidiscovery.operations.spec import (
    PLUGIN_PROTOCOL_VERSION,
    ApprovalContract,
    ApprovalOption,
    CallableComponent,
    ComponentRef,
    ComponentSpec,
    ExecutorRef,
    InputAdmissionSpec,
    InputValidationSpec,
    InputPortSpec,
    LimitsSpec,
    NativeToolPolicy,
    OperationDescription,
    OperationSpec,
    OutputPortSpec,
    PluginDefinition,
    PluginDependency,
    ReviewSpec,
    SemanticRuleSpec,
    WorkspaceContract,
)
from scidiscovery.operations.tooling import WorkerToolDefinition
from scidiscovery.artifact_agent.operation_tool_context import OperationToolContext

from .execution_control import SolverCapabilitySnapshot
from .role_pack import role_prompt
from .debug_contract import TCADDebugError
from .local_debug_service import debug_summary, debug_tool_description
from .project_packager import (
    DeckProjectDraft,
    DeckAuthorResult,
    DeckReviewReport,
    RuntimeAttestation,
    validate_deck_author_task_output,
    validate_deck_project_output,
    validate_deck_review_report,
    validate_deck_review_task_output,
)
from .operation_transforms import COMPONENT_SPECS as TRANSFORM_COMPONENT_SPECS
from .operation_transforms import OPERATIONS as TRANSFORM_OPERATIONS
from .parameter_operations import COMPONENT_SPECS as PARAMETER_COMPONENT_SPECS
from .parameter_operations import OPERATIONS as PARAMETER_OPERATIONS
from .curve_operations import COMPONENT_SPECS as CURVE_COMPONENT_SPECS
from .curve_operations import OPERATIONS as CURVE_OPERATIONS
from .result_analysis import COMPONENT_SPECS as RESULT_ANALYSIS_COMPONENT_SPECS
from .result_analysis import OPERATIONS as RESULT_ANALYSIS_OPERATIONS


def _schema(model: type[BaseModel], schema_id: str) -> str:
    value = model.model_json_schema(mode="validation")
    value["$id"] = schema_id
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _payload_validator(function: Callable[[dict[str, object]], Any]) -> Callable[[bytes], None]:
    def validate(raw: bytes) -> None:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise SemanticRuleViolation("TCAD payload must be an object")
        try:
            function(value)
        except ValidationError as error:
            raise SemanticRuleViolation(str(error)) from error

    return validate


def _author_context(
    payload: dict[str, object], sources: dict[str, bytes], handoff: dict[str, object]
) -> None:
    validate_deck_author_task_output(payload, sources, handoff)


def _parameter_inputs(sources: dict[str, bytes]) -> None:
    from .project_packager import DeckAuthorResult, ImplementationGap
    from scidiscovery.artifact_agent.schema.experiment_intent import ExperimentScientificSkeleton
    from scidiscovery.artifact_agent.schema.experiment import ExperimentPortfolio
    skeleton = sources.get("scientific_skeleton")
    plan = sources.get("experiment_plan")
    if "project" not in sources and (skeleton is None) == (plan is None):
        raise OperationInvocationError("input_author_plan_exact_one", port="scientific_skeleton")
    if skeleton is not None:
        parse_bound_json(ExperimentScientificSkeleton, skeleton, admission_port="scientific_skeleton")
        capability = json.loads(sources["execution_capability"])
        if capability.get("solver_kind") != "sprocess":
            raise OperationInvocationError("input_skeleton_solver_unsupported", port="execution_capability", message="The scientific skeleton author path currently supports sprocess only; legacy sdevice retains its plan contract.")
    descriptors = getattr(sources, "binding_descriptors", {})
    if "project" not in sources and plan is not None and "experiment_plan" in descriptors and dict(descriptors["experiment_plan"].labels).get("operation_id") == "tcad.execution-plan.project.v1":
        raise OperationInvocationError("input_projected_plan_not_author_design", port="experiment_plan", message="Use the original scientific skeleton for authoring; the extracted plan is only a project-derived consumer view.")
    for subject in ("project", "prior_project"):
        if subject not in sources:
            continue
        project = parse_bound_json(DeckAuthorResult, sources[subject], admission_port=subject).root
        descriptor = descriptors.get(subject)
        if skeleton is not None and descriptor is not None:
            if descriptors["scientific_skeleton"].artifact_ref not in descriptor.parent_refs:
                raise OperationInvocationError("input_project_skeleton_mismatch", port="scientific_skeleton")
        if isinstance(project, ImplementationGap):
            if subject == "project" and (skeleton is None) == (plan is None):
                raise OperationInvocationError("input_gap_subject_exact_one", port="scientific_skeleton")
            continue
        if project.execution_plan is not None and descriptor is not None:
            from .operation_transforms import require_skeleton_project_origin
            require_skeleton_project_origin(descriptor, port=subject)
        if (project.execution_plan is not None) != (skeleton is not None):
            raise OperationInvocationError("input_project_plan_branch_mismatch", port=subject)
        if subject == "project" and project.execution_plan is not None:
            if plan is None or parse_bound_json(ExperimentPortfolio, plan, admission_port="experiment_plan") != project.execution_plan:
                raise OperationInvocationError("input_project_execution_plan_mismatch", port="experiment_plan")
            projected = descriptors.get("experiment_plan")
            if projected is not None and (descriptor.artifact_ref not in projected.parent_refs or dict(projected.labels).get("operation_id") != "tcad.execution-plan.project.v1"):
                raise OperationInvocationError("input_execution_plan_projection_mismatch", port="experiment_plan")
        elif subject == "project" and plan is None:
            raise OperationInvocationError("input_legacy_plan_missing", port="experiment_plan")
    parameter_raw = sources.get("device_parameters")
    coverage_raw = sources.get("parameter_coverage")
    if parameter_raw is None and coverage_raw is None:
        return
    if parameter_raw is None or coverage_raw is None:
        raise OperationInvocationError("input_parameter_cohort_incomplete", port="parameter_coverage")
    parameters = parse_bound_json(DeviceParameterSet, parameter_raw, admission_port="device_parameters")
    coverage = parse_bound_json(DeviceParameterCoverageReport, coverage_raw, admission_port="parameter_coverage")
    if coverage.parameter_set_key != parameters.parameter_set_key:
        raise OperationInvocationError("input_parameter_coverage_mismatch", port="parameter_coverage")


def _runtime_author_inputs(sources: dict[str, bytes]) -> None:
    _parameter_inputs(sources)
    attestation = parse_bound_json(RuntimeAttestation, sources["runtime_attestation"],
                                  admission_port="runtime_attestation")
    if attestation.verdict != "fail":
        raise OperationInvocationError("input_runtime_attestation_not_failed", port="runtime_attestation", field="/verdict")


def _runtime_author_context(
    payload: dict[str, object], sources: dict[str, bytes], handoff: dict[str, object]
) -> None:
    validate_deck_author_task_output(payload, sources, handoff)


def _review_context(
    payload: dict[str, object], sources: dict[str, bytes], handoff: dict[str, object]
) -> None:
    validate_deck_review_task_output(payload, sources, handoff)


def _author_agent() -> None:
    return None


def _reviewer_agent() -> None:
    return None


class TCADDebugInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    run_name: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    mode: str = Field(pattern=r"^(preflight|smoke|initialization)$")
    output_names: list[Annotated[str, Field(min_length=1, max_length=256)]] | None = Field(default=None, max_length=63,
        description="Initialization only: names from the staged project's expected_outputs to collect for diagnostic reading. Omit when polling to retain the original selection; never production evidence.")


def _parameter_cohort_guard(inputs: tuple[Any, ...], parameters: dict[str, object]) -> bool:
    del parameters
    by_port = {item.port_name: item.artifact for item in inputs}
    if "parameter_uncertainty" not in by_port:
        return True
    try:
        reviewed = {
            by_port[name].ref
            for name in (
                "parameter_requirements",
                "device_parameters",
                "source_catalog",
                "parameter_coverage",
            )
        }
        if not reviewed.issubset(set(by_port["parameter_audit"].parent_refs)):
            return False
        if by_port["parameter_audit"].ref not in set(
            by_port["scientific_foundation"].parent_refs
        ):
            return False
        expected_projection_parents = (
            by_port["parameter_requirements"].ref,
            by_port["device_parameters"].ref,
            by_port["parameter_coverage"].ref,
        )
        return (
            by_port["parameter_uncertainty"].parent_refs
            == expected_projection_parents
        )
    except KeyError:
        return False


def _debug_tool(
    request: BaseModel, context: OperationToolContext
) -> dict[str, object]:
    if not isinstance(request, TCADDebugInput):
        raise ValueError("TCAD debug request has the wrong type")
    service = context.require_service("tcad.development_debug")
    run = getattr(service, "run", None)
    if not callable(run):
        raise RuntimeError("TCAD development debug service has no run method")
    try:
        try:
            response = run(context, run_name=request.run_name, mode=request.mode,
                **({"output_names": request.output_names} if request.output_names is not None else {}))
        except (RunOutputError, WorkspaceError) as error:
            details = getattr(error, "details", ()) or (
                {"path": "$", "message": str(error), "type": "value_error"},
            )
            if not getattr(error, "recorded", False):
                context.record_activity("output_rejected")
            response = {"state": "rejected", "diagnostics": list(details)}
        return debug_summary(context, request.run_name, response)
    except TCADDebugError as error:
        return debug_summary(context, request.run_name, {
            "state": "rejected",
            "diagnostics": [
                {
                    "path": "$",
                    "message": str(error)[:4096],
                    "type": "tcad_debug_error",
                }
            ],
            "scientific_claim_admissible": False,
        })


AUTHOR_PROMPT = role_prompt("author")
REVIEWER_PROMPT = role_prompt("reviewer")
SEMANTIC_CONTRACT = semantic_contract(
    SemanticRuleSpec(
        rule_id="tcad.deck.contract_consistency",
        description=(
            "The project or review must satisfy the declared TCAD cross-field "
            "contract."
        ),
    ),
    SemanticRuleSpec(
        rule_id="tcad.deck.input_binding",
        description=(
            "Every contextual claim must remain consistent with the explicitly "
            "bound inputs. Every deck review verdict requires parseable exact "
            "project, plan and parameter inputs, matching approved parameter "
            "context, and consistent report subject and handoff. Outputs must preserve "
            "case realization and approved parameter values and units. Submission "
            "does not recheck bound parameter uncertainty readiness. "
            "A revise or blocked review may report implementation gaps with "
            "execution_ready=false without editing its inputs."
        ),
    ),
    SemanticRuleSpec(
        rule_id="tcad.independent_review",
        description=(
            "A completed author result still requires the registered independent review."
        ),
    ),
)
CHANGE_REQUEST_SCHEMA = _schema(DeckReviewReport, "tcad.deck-review-report.v1")


AUTHOR_COMPONENT = CallableComponent("agent", _author_agent)
REVIEWER_COMPONENT = CallableComponent("agent", _reviewer_agent)
PROJECT_VALIDATOR_COMPONENT = CallableComponent(
    "validator", _payload_validator(validate_deck_project_output)
)
AUTHOR_CONTEXT_COMPONENT = CallableComponent("validator", _author_context)
PARAMETER_INPUT_COMPONENT = CallableComponent("validator", _parameter_inputs)
RUNTIME_AUTHOR_INPUT_COMPONENT = CallableComponent("validator", _runtime_author_inputs)
RUNTIME_AUTHOR_CONTEXT_COMPONENT = CallableComponent(
    "validator", _runtime_author_context
)
REVIEW_VALIDATOR_COMPONENT = CallableComponent(
    "validator", _payload_validator(validate_deck_review_report)
)
REVIEW_CONTEXT_COMPONENT = CallableComponent("validator", _review_context)
DEBUG_TOOL = WorkerToolDefinition(
    name="worker_tcad_debug_run",
    description=debug_tool_description(),
    input_model=TCADDebugInput,
    capability="tcad.development_debug",
    contextual_handler=_debug_tool,
    required_services=("tcad.development_debug",),
)
PARAMETER_COHORT_GUARD = CallableComponent("guard", _parameter_cohort_guard)
TCAD_WORKSPACE = WorkspaceContract()


def _ref(name: str, plugin_id: str | None = None) -> ComponentRef:
    return ComponentRef(name, plugin_id=plugin_id)


def _input(
    name: str,
    schema_id: str,
    schema_resource: str,
    *,
    usage: str = "claim_evidence",
    exposure: str = "full",
    media_types: tuple[str, ...] = ("application/json",),
    max_bytes: int = 16 * 1024 * 1024,
    min_items: int = 1,
    schema_plugin: str | None = None,
) -> InputPortSpec:
    return InputPortSpec(
        name=name,
        description=f"Exact TCAD input: {name}.",
        schema=schema_id,
        media_types=media_types,
        codec=_ref(
            "json_codec" if media_types == ("application/json",) else "opaque_codec",
            "general_science",
        ),
        schema_resource=_ref(schema_resource, schema_plugin),
        usage=usage,
        exposure=exposure,
        min_items=min_items,
        max_item_bytes=max_bytes,
    )


def _output(
    name: str,
    kind: str,
    schema_id: str,
    schema_resource: str,
    validator: str,
    context_validator: str,
    context_sources: tuple[str, ...],
    *,
    max_bytes: int,
) -> OutputPortSpec:
    return OutputPortSpec(
        name=name,
        description=f"Validated TCAD output: {name}.",
        schema=schema_id,
        media_types=("application/json",),
        codec=_ref("json_codec", "general_science"),
        schema_resource=_ref(schema_resource),
        kind=kind,
        validator=_ref(validator),
        validator_rule_id="tcad.deck.contract_consistency",
        semantic_contract=_ref("semantic_contract"),
        context_validator=_ref(context_validator),
        context_rule_id="tcad.deck.input_binding",
        context_sources=context_sources,
        max_item_bytes=max_bytes,
    )


_FILE_TOOLS = (
    _ref("file_write_begin_tool", "builtin"),
    _ref("file_write_chunk_tool", "builtin"),
    _ref("file_write_commit_tool", "builtin"),
)
_AUTHOR_TOOLS = _FILE_TOOLS + (
    _ref("file_apply_patch_tool", "builtin"),
    _ref("file_json_patch_tool", "builtin"),
    _ref("file_delete_tool", "builtin"),
    _ref("file_move_tool", "builtin"),
    _ref("debug_tool"),
)
_REVIEW_TOOLS = _FILE_TOOLS + (
    _ref("file_apply_patch_tool", "builtin"),
)


def _author_operation(
    operation_id: str,
    description: OperationDescription,
    inputs: tuple[InputPortSpec, ...],
    context_validator: str,
    *,
    input_validation: InputValidationSpec | None = None,
) -> OperationSpec:
    names = tuple(item.name for item in inputs if item.exposure != "handoff_only")
    return with_user_context(OperationSpec(
        operation_id=operation_id,
        version="3",
        catalog_scope="public",
        description=description,
        executor=ExecutorRef(
            kind="agent",
            component=_ref("author_agent"),
            workspace=_ref("deck_workspace"),
            tools=_AUTHOR_TOOLS,
            prompt=_ref("author_prompt"),
            native_tools=NativeToolPolicy(shell="inherited_prototype"),
        ),
        inputs=inputs,
        outputs=(
            _output(
                "project",
                "tcad_project",
                "tcad.deck-project.v1",
                "project_schema",
                "project_validator",
                context_validator,
                names,
                max_bytes=8 * 1024 * 1024,
            ),
        ),
        consequence="scientific",
        input_admission=DECK_PARAMETER_ADMISSION,
        input_validation=input_validation or InputValidationSpec(_ref("parameter_inputs"), "tcad.author.parameter_inputs", "Bind exactly one scientific_skeleton (SProcess only) or legacy experiment_plan; project-derived plan projections are not new author designs. Revisions retain the exact original skeleton binding. Bound parameter set and coverage must be paired and identify the same set; scientific deficiencies remain reviewable."),
        review=ReviewSpec(
            reviewer_operation="tcad.deck.review.v1",
            reviewer_input_port="project",
            subject_outputs=("project",),
        ),
        guards=(_ref("parameter_cohort_guard"),),
        limits=LimitsSpec(
            timeout_seconds=1200,
            max_input_bytes=64 * 1024 * 1024,
            max_output_bytes=8 * 1024 * 1024,
            max_files=1,
            max_attempts=2,
        ),
    ))


_PARAMETER_APPROVAL_PROVIDERS = (
    "science.parameters.qualify.pass.v1",
    "science.parameters.qualify.exception.v1",
)
DECK_PARAMETER_ADMISSION = InputAdmissionSpec(
    cohort_id="approved_parameters",
    member_ports=(
        "scientific_foundation",
        "parameter_requirements",
        "device_parameters",
        "source_catalog",
        "parameter_coverage",
        "parameter_audit",
        "parameter_uncertainty",
    ),
    approval_subject_ports=(
        "scientific_foundation",
        "parameter_requirements",
        "device_parameters",
        "source_catalog",
        "parameter_coverage",
        "parameter_audit",
    ),
    approval_kind="scientific_foundation",
    accepted_options=("approve", "approve_with_exception"),
    accepted_provider_operations=_PARAMETER_APPROVAL_PROVIDERS,
)


DEVICE_GRID_INPUT = _input(
    "device_grid",
    "opaque",
    "opaque_schema",
    schema_plugin="general_science",
    media_types=("application/octet-stream",),
    max_bytes=64 * 1024 * 1024,
    min_items=0,
)


CURRENT_PROGRESS_INPUT = InputPortSpec(
    name="current_progress", description="Exact overall objective and relevant sealed progress; background only.",
    schema="*", schema_resource=_ref("wildcard_schema", "general_science"),
    codec=_ref("opaque_codec", "general_science"), media_types=("*/*",),
    min_items=0, max_items=4, max_item_bytes=2 * 1024 * 1024,
    exposure="on_demand", usage="evidence_inventory",
)


INITIAL_INPUTS = (
    CURRENT_PROGRESS_INPUT,
    _input("execution_capability", "tcad.solver-capability.v2", "capability_schema", max_bytes=64 * 1024),
    _input("experiment_plan", "scidiscovery.experiment-portfolio.v1", "experiment_portfolio_schema", schema_plugin="general_science", max_bytes=2 * 1024 * 1024, min_items=0),
    _input("scientific_skeleton", "scidiscovery.experiment-scientific-skeleton.v1", "experiment_skeleton_schema", schema_plugin="general_science", max_bytes=64 * 1024, min_items=0),
    _input("curve_contract", "scidiscovery.curve-experiment-contract.v1", "curve_contract_schema", schema_plugin="curve_score", usage="prior_signal", max_bytes=2 * 1024 * 1024, min_items=0),
    _input("experiment_review", "scidiscovery.scientific-review.v1", "scientific_review_schema", schema_plugin="general_science", usage="prior_signal", exposure="on_demand", max_bytes=512 * 1024, min_items=0),
    _input("curve_contract_review", "scidiscovery.scientific-review.v1", "scientific_review_schema", schema_plugin="general_science", usage="prior_signal", exposure="handoff_only", max_bytes=512 * 1024, min_items=0),
    _input("scientific_foundation", "scidiscovery.scientific-foundation.v1", "scientific_foundation_schema", schema_plugin="general_science", exposure="on_demand", max_bytes=1024 * 1024, min_items=0),
    _input("parameter_requirements", "scidiscovery.device-parameter-requirements.v1", "parameter_requirements_schema", exposure="on_demand", max_bytes=2 * 1024 * 1024, min_items=0),
    _input("device_parameters", "scidiscovery.device-parameter-set.v1", "device_parameters_schema", max_bytes=2 * 1024 * 1024, min_items=0),
    _input("source_catalog", "scidiscovery.evidence-source-catalog.v1", "source_catalog_schema", exposure="on_demand", max_bytes=1024 * 1024, min_items=0),
    _input("parameter_coverage", "scidiscovery.device-parameter-coverage.v1", "parameter_coverage_schema", usage="prior_signal", max_bytes=2 * 1024 * 1024, min_items=0),
    _input("parameter_audit", "scidiscovery.evidence-audit.v1", "evidence_audit_schema", schema_plugin="general_science", usage="prior_signal", exposure="on_demand", max_bytes=512 * 1024, min_items=0),
    _input("parameter_uncertainty", "scidiscovery.parameter-uncertainty.v1", "parameter_uncertainty_schema", usage="prior_signal", max_bytes=512 * 1024, min_items=0),
)
REVISION_INPUTS = (
    _input("prior_project", "tcad.deck-project.v1", "project_schema", usage="revision_base"),
    _input("change_request", "tcad.deck-review-report.v1", "review_schema", usage="change_request", max_bytes=512 * 1024),
    DEVICE_GRID_INPUT,
    *INITIAL_INPUTS,
)
RUNTIME_INPUTS = (
    _input("prior_project", "tcad.deck-project.v1", "project_schema", usage="revision_base"),
    _input("runtime_attestation", "tcad.runtime-attestation.v1", "runtime_attestation_schema", usage="prior_signal", max_bytes=512 * 1024),
    _input("solver_log", "opaque", "opaque_schema", schema_plugin="general_science", usage="prior_signal", media_types=("text/plain", "text/plain; charset=utf-8"), max_bytes=32 * 1024 * 1024),
    *INITIAL_INPUTS,
)
REVIEW_INPUTS = (
    _input("project", "tcad.deck-project.v1", "project_schema", usage="prior_signal"),
    *(item.model_copy(update={"usage": "prior_signal"})
      if item.name == "experiment_plan" else item for item in INITIAL_INPUTS),
)


PLUGIN = PluginDefinition(
    plugin_id="tcad_artifact",
    version="0.2.0",
    protocol_version=PLUGIN_PROTOCOL_VERSION,
    dependencies=(
        PluginDependency("builtin", "0.1.0"),
        PluginDependency("general_science", "0.1.0"),
        PluginDependency("curve_score", "0.2.1"),
    ),
    configuration_schema=_ref("runtime_configuration_schema"),
    runtime_factory=_ref("runtime_factory"),
    components=(
        ComponentSpec("author_agent", "agent", "tcad_artifact.plugin:AUTHOR_COMPONENT"),
        ComponentSpec("reviewer_agent", "agent", "tcad_artifact.plugin:REVIEWER_COMPONENT"),
        ComponentSpec("semantic_contract", "resource", "tcad_artifact.plugin:SEMANTIC_CONTRACT"),
        ComponentSpec("author_prompt", "resource", "tcad_artifact.plugin:AUTHOR_PROMPT"),
        ComponentSpec("reviewer_prompt", "resource", "tcad_artifact.plugin:REVIEWER_PROMPT"),
        ComponentSpec("project_schema", "resource", "tcad_artifact.plugin:PROJECT_SCHEMA", public=True),
        ComponentSpec("review_schema", "resource", "tcad_artifact.plugin:REVIEW_SCHEMA"),
        ComponentSpec("capability_schema", "resource", "tcad_artifact.plugin:CAPABILITY_SCHEMA"),
        ComponentSpec("runtime_attestation_schema", "resource", "tcad_artifact.plugin:RUNTIME_ATTESTATION_SCHEMA"),
        ComponentSpec("parameter_requirements_schema", "resource", "tcad_artifact.plugin:PARAMETER_REQUIREMENTS_SCHEMA"),
        ComponentSpec("device_parameters_schema", "resource", "tcad_artifact.plugin:DEVICE_PARAMETERS_SCHEMA"),
        ComponentSpec("source_catalog_schema", "resource", "tcad_artifact.plugin:SOURCE_CATALOG_SCHEMA"),
        ComponentSpec("parameter_coverage_schema", "resource", "tcad_artifact.plugin:PARAMETER_COVERAGE_SCHEMA"),
        ComponentSpec("parameter_uncertainty_schema", "resource", "tcad_artifact.plugin:PARAMETER_UNCERTAINTY_SCHEMA"),
        ComponentSpec("project_validator", "validator", "tcad_artifact.plugin:PROJECT_VALIDATOR_COMPONENT", resources=(_ref("semantic_contract"),)),
        ComponentSpec("author_context", "validator", "tcad_artifact.plugin:AUTHOR_CONTEXT_COMPONENT", configuration_identity="output-responsibility:v2:admitted-prior", resources=(_ref("semantic_contract"),)),
        ComponentSpec("parameter_inputs", "validator", "tcad_artifact.plugin:PARAMETER_INPUT_COMPONENT"),
        ComponentSpec("runtime_author_inputs", "validator", "tcad_artifact.plugin:RUNTIME_AUTHOR_INPUT_COMPONENT"),
        ComponentSpec("runtime_author_context", "validator", "tcad_artifact.plugin:RUNTIME_AUTHOR_CONTEXT_COMPONENT", configuration_identity="output-responsibility:v2:admitted-prior", resources=(_ref("semantic_contract"),)),
        ComponentSpec("review_validator", "validator", "tcad_artifact.plugin:REVIEW_VALIDATOR_COMPONENT", resources=(_ref("semantic_contract"),)),
        ComponentSpec("review_context", "validator", "tcad_artifact.plugin:REVIEW_CONTEXT_COMPONENT", configuration_identity="output-responsibility:v1", resources=(_ref("semantic_contract"),)),
        ComponentSpec("parameter_cohort_guard", "guard", "tcad_artifact.plugin:PARAMETER_COHORT_GUARD", configuration_identity="tcad.approved-parameter-cohort.v1"),
        ComponentSpec("workspace_materializer", "workspace_materializer", "tcad_artifact.operation_workspace:MATERIALIZER_COMPONENT", configuration_identity="tcad.workspace-materializer.v6:author-output-fields"),
        ComponentSpec("workspace_file_policy", "workspace_file_policy", "tcad_artifact.operation_workspace:FILE_POLICY_COMPONENT", configuration_identity="tcad.workspace-file-policy.v1"),
        ComponentSpec("review_result_finalizer", "workspace_finalizer", "tcad_artifact.operation_workspace:REVIEW_FINALIZER_COMPONENT", configuration_identity="tcad.review-finalizer.v2:formal-summary"),
        ComponentSpec("workspace_finalizer", "workspace_finalizer", "tcad_artifact.operation_workspace:FINALIZER_COMPONENT", configuration_identity="tcad.workspace-finalizer.v6:development-candidate-lifecycle"),
        ComponentSpec("workspace_snapshotter", "workspace_snapshotter", "tcad_artifact.operation_workspace:SNAPSHOTTER_COMPONENT", configuration_identity="tcad.workspace-snapshotter.v2"),
        ComponentSpec(
            "deck_workspace",
            "workspace",
            "tcad_artifact.plugin:TCAD_WORKSPACE",
            resources=(
                _ref("workspace_materializer"),
                _ref("workspace_file_policy"),
                _ref("workspace_finalizer"),
                _ref("workspace_snapshotter"),
            ),
            configuration_identity="tcad.deck-workspace.v2",
        ),
        ComponentSpec(
            "review_workspace",
            "workspace",
            "tcad_artifact.plugin:TCAD_WORKSPACE",
            resources=(_ref("workspace_materializer"), _ref("review_result_finalizer")),
            configuration_identity="tcad.deck-review-workspace.v2",
        ),
        ComponentSpec("debug_tool", "worker_tool", "tcad_artifact.plugin:DEBUG_TOOL", configuration_identity="tcad.debug-tool.v7:single-rejection-observation"),
        ComponentSpec("runtime_configuration_schema", "resource", "tcad_artifact.runtime_plugin:CONFIGURATION_SCHEMA"),
        ComponentSpec("runtime_factory", "runtime_factory", "tcad_artifact.runtime_plugin:RUNTIME_FACTORY", configuration_identity="tcad.runtime-factory.v3:run-local-tool-service"),
        ComponentSpec("study_execute", "effect", "tcad_artifact.runtime_plugin:EXECUTE_EFFECT", configuration_identity="tcad.execution-adapter:tcad:reviewed-deck-package.v2"),
        ComponentSpec("execution_projector", "projector", "tcad_artifact.runtime_plugin:EXECUTION_PROJECTOR"),
        ComponentSpec("execution_request_schema", "resource", "tcad_artifact.plugin:EXECUTION_REQUEST_SCHEMA"),
        *PARAMETER_COMPONENT_SPECS,
        *TRANSFORM_COMPONENT_SPECS,
        *CURVE_COMPONENT_SPECS,
        *RESULT_ANALYSIS_COMPONENT_SPECS,
    ),
    operations=(
        *PARAMETER_OPERATIONS,
        *CURVE_OPERATIONS,
        *RESULT_ANALYSIS_OPERATIONS,
        _author_operation(
            "tcad.deck.author.initial.v1",
            OperationDescription(
                purpose="Author one new TCAD solver project from an exact experiment plan.",
                applies_when="An exact scientific skeleton (SProcess) or legacy reviewed plan and solver capability are available.",
                not_for="Postprocessing, scientific diagnosis, or external execution.",
            ),
            INITIAL_INPUTS,
            "author_context",
        ),
        _author_operation(
            "tcad.deck.author.revise.v1",
            OperationDescription(
                purpose="Apply one bounded independently requested TCAD source revision.",
                applies_when="One exact prior project and review request are available.",
                not_for="Redesigning the scientific experiment.",
            ),
            REVISION_INPUTS,
            "author_context",
        ),
        _author_operation(
            "tcad.deck.author.runtime-failure.v1",
            OperationDescription(
                purpose="Correct one concrete TCAD runtime failure without changing the study.",
                applies_when="A failing runtime attestation and exact solver log are available.",
                not_for="Hypothesis changes or broad deck redesign.",
            ),
            RUNTIME_INPUTS,
            "runtime_author_context",
            input_validation=InputValidationSpec(_ref("runtime_author_inputs"), "tcad.author.runtime_failure.inputs", "The bound runtime attestation must report failure; author exact-one plan branch, original skeleton binding and supported SProcess scope also apply."),
        ),
        with_user_context(OperationSpec(
            operation_id="tcad.deck.review.v1",
            version="3",
            catalog_scope="public",
            description=OperationDescription(
                purpose="Independently assess scientific adequacy, implementation and development evidence for the exact TCAD project.",
                applies_when="A structurally readable exact author project, plan, and capability are available, including a blocked project or implementation gaps.",
                not_for="Editing the project or running a solver.",
            ),
            executor=ExecutorRef(
                kind="agent",
                component=_ref("reviewer_agent"),
                workspace=_ref("review_workspace"),
                tools=_REVIEW_TOOLS,
                prompt=_ref("reviewer_prompt"),
                native_tools=NativeToolPolicy(shell="inherited_prototype"),
            ),
            inputs=REVIEW_INPUTS,
            outputs=(
                _output(
                    "review",
                    "tcad_project_review",
                    "tcad.deck-review-report.v1",
                    "review_schema",
                    "review_validator",
                    "review_context",
                    tuple(item.name for item in REVIEW_INPUTS if item.exposure != "handoff_only"),
                    max_bytes=128 * 1024,
                ),
            ),
            consequence="scientific",
            input_admission=DECK_PARAMETER_ADMISSION,
            input_validation=InputValidationSpec(_ref("parameter_inputs"), "tcad.review.parameter_inputs", "For skeleton projects bind the original skeleton and exact project-derived execution plan; a gap needs only its scientific subject. Legacy projects retain their plan and review witness. Bound parameter set and coverage must identify the same set; failed coverage remains independently reviewable."),
            guards=(_ref("parameter_cohort_guard"),),
            limits=LimitsSpec(
                timeout_seconds=600,
                max_input_bytes=32 * 1024 * 1024,
                max_output_bytes=128 * 1024,
                max_files=1,
            ),
        )),
        *TRANSFORM_OPERATIONS,
        OperationSpec(
            operation_id="tcad.study.execute",
            version="1",
            catalog_scope="public",
            description=OperationDescription(
                purpose="Create one controlled execution request for an exact reviewed TCAD package.",
                applies_when="A packaged project and configured TCAD runtime are available.",
                not_for="Development debugging, unreviewed projects, or scientific interpretation.",
            ),
            executor=ExecutorRef(kind="effect", component=_ref("study_execute")),
            inputs=(
                _input(
                    "reviewed_package",
                    "tcad.reviewed-deck-package.v2",
                    "reviewed_package_schema",
                    usage="prior_signal",
                    max_bytes=64 * 1024 * 1024,
                ),
            ),
            outputs=(
                OutputPortSpec(
                    name="execution_request",
                    description="Controlled request for one exact TCAD execution.",
                    schema="scidiscovery.execution-request",
                    media_types=("application/json",),
                    codec=_ref("json_codec", "general_science"),
                    schema_resource=_ref("execution_request_schema"),
                    kind="execution_request",
                    max_item_bytes=64 * 1024,
                ),
            ),
            consequence="external",
            review=ReviewSpec(
                approval=ApprovalContract(
                    subject_ports=("execution_request", "reviewed_package"),
                    question="是否授权执行这个已审查的 TCAD 工程？",
                    options=(
                        ApprovalOption("授权执行", "accept"),
                        ApprovalOption("拒绝执行", "reject"),
                    ),
                    projector=_ref("execution_projector"),
                )
            ),
            limits=LimitsSpec(
                timeout_seconds=300,
                max_input_bytes=64 * 1024 * 1024,
                max_output_bytes=64 * 1024,
                max_files=1,
            ),
        ),
    ),
)


PROJECT_SCHEMA = _schema(DeckAuthorResult, "tcad.deck-project.v1")
REVIEW_SCHEMA = _schema(DeckReviewReport, "tcad.deck-review-report.v1")
CAPABILITY_SCHEMA = _schema(SolverCapabilitySnapshot, "tcad.solver-capability.v2")
RUNTIME_ATTESTATION_SCHEMA = _schema(RuntimeAttestation, "tcad.runtime-attestation.v1")
PARAMETER_REQUIREMENTS_SCHEMA = _schema(DeviceParameterRequirementSet, "scidiscovery.device-parameter-requirements.v1")
DEVICE_PARAMETERS_SCHEMA = _schema(DeviceParameterSet, "scidiscovery.device-parameter-set.v1")
SOURCE_CATALOG_SCHEMA = _schema(EvidenceSourceCatalog, "scidiscovery.evidence-source-catalog.v1")
PARAMETER_COVERAGE_SCHEMA = _schema(DeviceParameterCoverageReport, "scidiscovery.device-parameter-coverage.v1")
PARAMETER_UNCERTAINTY_SCHEMA = _schema(ParameterUncertaintyProjection, "scidiscovery.parameter-uncertainty.v1")
EXECUTION_REQUEST_SCHEMA = _schema(ExecutionRequest, "scidiscovery.execution-request")


__all__ = ["PLUGIN"]
