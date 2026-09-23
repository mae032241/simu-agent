"""Semantic scheduler MCP with all control identity kept behind the service."""

from __future__ import annotations

from ...agent_execution_settings import ExecutionProfile

import threading
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, ValidationInfo

from ...operation_contract import validation_diagnostics, contract_diagnostic
from ...operations.tooling import parse_tool_arguments
from ...operations.invoke import EmptyOperationParameters
from ...operations.spec import freeze_json, json_projection

from ..execution_bridge import ExecutionBridge
from ..service.approvals import ApprovalService
from ..service.artifacts import ArtifactService
from ..service.executions import ExecutionService
from ..service.intake import SecureIntakeService, USER_TEXT_MAX_LENGTH
from ..service.scheduler_bindings import (
    SchedulerBinding,
    SchedulerBindingService,
    SchedulerNameConflict,
    SchedulerNameNotFound,
)
from ..service.runs import RunService
from ...operations.catalog import CompiledCatalog, compile_installed_catalog
from .mcp_root_shared import (
    CreationTarget as _CreationTarget,
    RootToolError,
)
from .mcp_root_approval_routes import RootApprovalRoutes
from .mcp_root_execution_routes import RootExecutionRoutes
from .mcp_root_instance_routes import RootInstanceRoutes
from .mcp_root_operation_routes import RootOperationRoutes
from .mcp_root_run_routes import RootRunRoutes
from ..service.engineering_diagnostics import EngineeringDiagnostics
from ..service.execution_collection import COLLECTION_SECONDS


_NAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}$"
_SOURCE_NAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$"
class RootToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmptyInput(RootToolInput):
    pass


class ReadInput(RootToolInput):
    view: Literal["summary", "detail"] = Field(default="summary",
        description="Default compact view with explicit omission and original-detail navigation. Detail preserves exact bindings, original logs and full metadata.")


class PageInput(ReadInput):
    limit: int = Field(default=20, ge=1, le=100)
    before: str | None = Field(default=None, max_length=256,
        description="Continue after the exact next_before cursor from this same query.")


class OperationCatalogInput(PageInput):
    operation_id: str | None = Field(default=None, max_length=256,
        description="Select one exact operation; use view=detail to read its complete contract before binding.")
    scope: Literal["public", "support", "internal", "all"] = "public"


class NamedInput(RootToolInput):
    name: str = Field(pattern=_NAME_PATTERN)


class NamedReadInput(NamedInput, ReadInput):
    pass


class NamedPageInput(NamedInput, PageInput):
    pass


class LifecycleEventsInput(RootToolInput):
    limit: int = Field(default=20, ge=1, le=100,
        description="Consume at most this many changed states; poll again if poll_again is true.")


class DiagnosticReadInput(RootToolInput):
    reference: str = Field(pattern=r"^diag_[0-9a-f]{32}$")
    offset: int = Field(default=0, ge=0)
    max_bytes: int = Field(default=16384, ge=1, le=65536)
    section: Literal["summary", "traceback", "stdout", "stderr"] = "summary"


class ExecutionCollectInput(NamedInput):
    total_seconds: float = Field(default=COLLECTION_SECONDS, gt=0, allow_inf_nan=False,
        description="Total collection attempt budget, including transfer, registration and cleanup. A running attempt is never extended by a duplicate call.")


class InstanceListInput(PageInput):
    state: Literal["active", "closed"] | None = None


class RevisionInput(RootToolInput):
    on_conflict: Literal["reject", "create_revision"] = "reject"


class IngestFileInput(NamedInput, RevisionInput):
    relative_path: str = Field(min_length=1, max_length=4096)
    media_type: str | None = Field(default=None, min_length=3, max_length=255)


class IngestTextInput(NamedInput, RevisionInput):
    text: str = Field(
        min_length=1,
        max_length=USER_TEXT_MAX_LENGTH,
        description="Original user text in valid Unicode, stored as UTF-8 without changing whitespace, line endings, or normalization.",
    )

    @field_validator("text", mode="before")
    @classmethod
    def _validate_unicode(cls, value: Any) -> Any:
        if isinstance(value, str):
            try:
                value.encode("utf-8")
            except UnicodeEncodeError as error:
                raise ValueError("text must be valid Unicode encodable as UTF-8") from error
        return value


class OperationInputSelection(RootToolInput):
    port: str = Field(pattern=_SOURCE_NAME_PATTERN)
    artifact_names: tuple[str, ...] = Field(max_length=256)


class OperationCallInput(NamedInput, RevisionInput):
    operation_id: str = Field(min_length=1, max_length=128)
    inputs: tuple[OperationInputSelection, ...] = Field(max_length=64)
    instruction: str | None = Field(default=None, max_length=65536)
    parameters: EmptyOperationParameters = Field(default_factory=dict)
    execution_profile: ExecutionProfile | None = Field(default=None,
        description="Control-owned model, reasoning effort and narrative language snapshot. Invoke resolves and freezes defaults when omitted. Optional preflight returns normalized_request; reuse it unchanged to preserve that snapshot. Not scientific parameters.")
    max_attempts: int | None = Field(
        default=None, ge=1, strict=True,
        description="Scheduler-selected total Run budget for this recovery chain, including its first Run. An explicit value supersedes earlier attempt budgets for this new request; omission inherits the last scheduler budget or the Operation default. Other resource and identity limits are unchanged.",
    )
    resume_from: str | None = Field(default=None, pattern=_NAME_PATTERN)
    draft_from: str | None = Field(
        default=None, pattern=_NAME_PATTERN,
        description="Failed Run name in this instance whose preserved draft is starting material under the new inputs and contract; mutually exclusive with resume_from and never scientific evidence.",
    )


class ScientificCurrentSelectInput(NamedInput):
    kind: str = Field(pattern=_NAME_PATTERN)
    expected_artifact_name: str | None = Field(pattern=_NAME_PATTERN)


class RunListInput(PageInput):
    state: Literal["queued", "running", "completed", "failed"] | None = None
    limit: int = Field(default=20, ge=1, le=100)
    before: str | None = Field(default=None, pattern=_NAME_PATTERN,
        description="Continue after this semantic Run name, returned as next_before by the previous page.")


class ArtifactCatalogInput(NamedReadInput):
    view: Literal["summary", "detail", "parents", "producer_inputs"] = Field(default="summary",
        description="summary gives metadata; parents gives one page of direct parents and, for a recovery manifest, mechanically joins sealed source aliases/records to those exact parents; producer_inputs gives one page of the exact immediate producer's frozen input ports without recursive traversal; detail is the legacy full metadata view. parents and producer_inputs share parent_offset/parent_limit. Direct-parent limit remains 4096.")
    parent_offset: int = Field(default=0, ge=0,
        description="parents or producer_inputs view: continue at next_offset for the same artifact.")
    parent_limit: int = Field(default=16, ge=1, le=32)


class RunStatusInput(NamedReadInput):
    response_profile: Literal["compat", "poll", "navigation", "decision"] = Field(
        default="compat",
        description=(
            "Request-time read projection only. compat preserves existing summary/detail and output "
            "semantics. poll requires summary + values + output_paths=[]; navigation requires summary "
            "+ index with zero or one path; decision requires summary + values with one or more paths. "
            "Compact profiles may page durable diagnostics with diagnostic_after; they reject detail."
        ),
    )
    output_mode: Literal["values", "index"] = Field(default="values",
        description='Use values directly for known paths; [""] for most/all payload fields. Use index only to discover unknown paths, never as a required first step; it returns no values, even with view=detail. Omit output_paths for the root index.')
    output_paths: list[Annotated[str, Field(pattern=r"^(?:/(?:[^~]|~[01])*)?$")]] | None = Field(
        default=None, max_length=8,
        description='JSON Pointers relative to the sealed payload, e.g. /summary, not /payload/summary. Omit/null for a summary excerpt (view=detail returns the complete original); [] skips payload. Up to 8 paths, 32 KiB values total. [""] selects the whole payload; "/" selects an empty key. status=selected returns the exact value: reuse it, including a whole payload, without fetching its fields again. Oversized values have status=omitted with direct-child paths (32 items, 8 KiB); batch needed paths. Missing paths are explicit. view=detail also reveals bindings and timing. selected_output retains origin but is not the sealed_output envelope.',
    )
    index_offset: int = Field(default=0, ge=0,
        description="Index mode only: continue at output_index.next_offset for the same immutable object and path.")
    index_limit: int = Field(default=16, ge=1, le=32,
        description="Index mode only: maximum direct children; the complete output_index is limited to 8 KiB UTF-8 JSON.")

    @field_validator("output_paths")
    @classmethod
    def index_has_one_path(cls, value, info: ValidationInfo):
        if info.data.get("output_mode") == "index" and value is not None and len(value) != 1:
            raise ValueError("index mode requires exactly one output path or null for the root")
        return value
    diagnostic_after: int | None = Field(default=None, ge=0,
        description="Set to 0 for the first page of saved errors, then use diagnostic_events.next_after. Omit for the compact status.")
    diagnostic_limit: int = Field(default=20, ge=1, le=100)


class RunFailureInput(NamedInput):
    reason: str = Field(min_length=1, max_length=4096)
    expected_state: Literal["queued", "running"]
    expected_last_activity_at: str | None
    timed_out: bool = False


class ApprovalListInput(PageInput):
    status: Literal["pending", "decided", "expired", "cancelled_by_human"] | None = None
    limit: int = Field(default=20, ge=1, le=100)


class ExecutionCapabilitiesInput(PageInput):
    operation_id: str = Field(min_length=1, max_length=256)


class ExecutionCapabilityBindInput(NamedInput, RevisionInput):
    operation_id: str = Field(min_length=1, max_length=256)
    profile: str = Field(pattern=_NAME_PATTERN)


class ExecutionListInput(PageInput):
    state: Literal[
        "created",
        "authorized",
        "submitted",
        "running",
        "cancelling",
        "succeeded",
        "failed",
        "cancelled",
        "collected",
        "abandoned",
    ] | None = None
    limit: int = Field(default=20, ge=1, le=100)


@dataclass(frozen=True)
class RootTool:
    name: str
    description: str
    input_model: type[RootToolInput]

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_model.model_json_schema(),
        }


ROOT_TOOLS = (
    RootTool("diagnostic_read", "Read bounded engineering error details visible to the current instance or session.", DiagnosticReadInput),
    RootTool("instance_current", "Read the bound research instance or return its direct local management URL.", ReadInput),
    RootTool("instance_list", "List research instances without exposing internal identity.", InstanceListInput),
    RootTool("instance_close", "Close the current research instance against further writes.", EmptyInput),
    RootTool("scientific_inventory", "List current immutable scientific objects without suggesting a workflow or capability.", PageInput),
    RootTool("scientific_current", "Read explicit current scientific-object selections for this research instance.", PageInput),
    RootTool("scientific_current_select", "Compare-and-set one immutable scientific object as the explicit current selection.", ScientificCurrentSelectInput),
    RootTool("lifecycle_events", "Return persistent semantic task, approval, and execution state changes for this scheduler process.", LifecycleEventsInput),
    RootTool("artifact_ingest_file", "Freeze and bind one project file under a semantic name.", IngestFileInput),
    RootTool("artifact_ingest_text", "Freeze original user text and bind it under a semantic name in the current instance; does not create a Run.", IngestTextInput),
    RootTool("artifact_catalog", "Read metadata or paged direct parents for one bound semantic input.", ArtifactCatalogInput),
    RootTool("operation_catalog", "List bounded operation summaries; select operation_id with view=detail for its full compiled contract.", OperationCatalogInput),
    RootTool("operation_preflight", "Optional check without creating. Invoke independently checks admission; this does not reserve resources or authorize execution.", OperationCallInput),
    RootTool("operation_invoke", "Validate and create one Agent, Transform, Effect or Approval from the compiled catalog; no prior preflight required. Success preserves dispatch configuration, exact outputs or approval URLs by executor kind; use the returned detail entry for Run context.", OperationCallInput),
    RootTool("run_list", "List minimal Runs in this research instance.", RunListInput),
    RootTool("run_status", "Read Run state and selected output_paths together; only completed Runs expose sealed fields. Use [] for polling, view=detail for bindings/full output.", RunStatusInput),
    RootTool("run_record_failure", "Record failure of one running minimal Run.", RunFailureInput),
    RootTool("approval_list", "List named reviews in this scheduler instance.", ApprovalListInput),
    RootTool("approval_status", "Read one named human-review state.", NamedReadInput),
    RootTool("execution_capabilities", "List sanitized execution capabilities for one compiled Effect operation.", ExecutionCapabilitiesInput),
    RootTool("execution_capability_bind", "Freeze one capability selected through a compiled Effect under a semantic artifact name.", ExecutionCapabilityBindInput),
    RootTool("execution_abandon", "Abandon one named unsubmitted execution.", NamedInput),
    RootTool("execution_cancel", "Request cancellation of one named submitted execution.", NamedInput),
    RootTool("execution_list", "List named executions in this scheduler instance.", ExecutionListInput),
    RootTool("execution_status", "Read one named execution state. Summary gives a bounded deduplicated log index and exact error fields; view=detail reads the complete existing response.", NamedReadInput),
    RootTool("execution_outputs", "Bind and list logical outputs and the exact result_artifact_name from this execution; null means not yet bindable. Bind that result before creating analysis; every page preserves the same identity.", NamedPageInput),
    RootTool("execution_start", "Submit one named execution after its exact local review authorizes it.", NamedInput),
    RootTool("execution_sync", "Refresh bounded solver status and logs; never collect artifacts.", NamedReadInput),
    RootTool("execution_collect", "Start or resume terminal artifact collection; returns immediately. Other active collection returns busy without queuing.", ExecutionCollectInput),
)


def root_tools_for_backend(worker_backend: str) -> tuple[RootTool, ...]:
    if worker_backend in {"local", "hardened"}:
        return ROOT_TOOLS
    raise ValueError("worker backend is invalid")


class RootToolFacade(
    RootInstanceRoutes,
    RootOperationRoutes,
    RootRunRoutes,
    RootApprovalRoutes,
    RootExecutionRoutes,
):
    def __init__(
        self,
        artifacts: ArtifactService,
        intake: SecureIntakeService,
        *,
        runs: RunService,
        approvals: ApprovalService,
        executions: ExecutionService,
        bindings: SchedulerBindingService,
        instance: str | None,
        session_key: str | None = None,
        creation_lock: threading.RLock | None = None,
        execution_bridge: ExecutionBridge | None = None,
        approval_base_url: str | None = None,
        instance_management_secret: bytes | None = None,
        operation_catalog: CompiledCatalog | None = None,
        execution_collection=None,
    ) -> None:
        self.artifacts = artifacts
        self.intake = intake
        self.runs = runs
        self.approvals = approvals
        self.executions = executions
        self.bindings = bindings
        self.instance = instance
        self.session_key = session_key
        self.execution_bridge = execution_bridge
        self.execution_collection = execution_collection
        self.approval_base_url = approval_base_url
        self.instance_management_secret = instance_management_secret
        self._operation_catalog = operation_catalog or compile_installed_catalog()
        self._create_lock = creation_lock or threading.RLock()
        self.engineering_diagnostics = EngineeringDiagnostics(runs.database_path.parent.parent / "engineering-diagnostics")

    def diagnostic_read(self, *, reference: str, offset: int, max_bytes: int, section: str) -> dict:
        scopes = ["session:" + self.session_key] if self.session_key else []
        try:
            scopes.append("instance:" + self._instance_id())
        except RootToolError:
            pass
        return self.engineering_diagnostics.read(reference, scopes=tuple(scopes), offset=offset, max_bytes=max_bytes, section=section)

    def _bind(
        self,
        namespace: str,
        name: str,
        object_id: str,
        *,
        request_fingerprint: str | None = None,
    ) -> SchedulerBinding:
        return self.bindings.bind(
            instance=self._instance_id(),
            namespace=namespace,
            name=name,
            object_id=object_id,
            request_fingerprint=request_fingerprint,
        )

    def _resolve(self, namespace: str, name: str) -> str:
        return self.bindings.resolve(
            instance=self._instance_id(), namespace=namespace, name=name
        )

    def _resolve_input_artifact(
        self, name: str, *, allow_nonqualifying: bool = False
    ) -> str:
        try:
            artifact_id = self._resolve("artifact", name)
        except SchedulerNameNotFound:
            suffix = ".output"
            if not name.endswith(suffix):
                raise
            run_name = name[: -len(suffix)]
            run_id = self._resolve("run", run_name)
            status = self.runs.status(run_id)
            if status.output_ref is None:
                raise
            artifact_id = status.output_ref.artifact_id
        del allow_nonqualifying
        return artifact_id

    def _scheduler_signal_for_output(self, reference: Any) -> Any:
        return self.runs.signal_for_output(reference)

    def _is_exact_reviewer_output(self, reference: Any, **values: Any) -> bool:
        return self.runs.is_exact_reviewer_output(reference, **values)

    def _binding(self, namespace: str, name: str) -> SchedulerBinding:
        return self.bindings.get_binding(
            instance=self._instance_id(), namespace=namespace, name=name
        )

    def _optional(self, namespace: str, name: str) -> str | None:
        try:
            return self._resolve(namespace, name)
        except SchedulerNameNotFound:
            return None

    def _creation_target(
        self,
        namespace: str,
        requested_name: str,
        request_fingerprint: str,
        on_conflict: str,
    ) -> _CreationTarget:
        try:
            existing = self._binding(namespace, requested_name)
        except SchedulerNameNotFound:
            return _CreationTarget(requested_name, requested_name, 1, None)
        if existing.request_fingerprint == request_fingerprint:
            return _CreationTarget(
                existing.name,
                existing.logical_name,
                existing.revision,
                existing.object_id,
            )
        if on_conflict != "create_revision":
            detail = (
                "legacy binding has no verifiable request fingerprint"
                if existing.request_fingerprint is None
                else "semantic name already represents different immutable content"
            )
            raise SchedulerNameConflict(
                f"{namespace} name requires an explicit revision: "
                f"{requested_name} ({detail})"
            )
        logical_name = existing.logical_name
        matched = self.bindings.find_revision(
            instance=self._instance_id(),
            namespace=namespace,
            logical_name=logical_name,
            request_fingerprint=request_fingerprint,
        )
        if matched is not None:
            return _CreationTarget(
                matched.name,
                matched.logical_name,
                matched.revision,
                matched.object_id,
            )
        revision_name, revision = self.bindings.next_revision(
            instance=self._instance_id(),
            namespace=namespace,
            logical_name=logical_name,
        )
        return _CreationTarget(revision_name, logical_name, revision, None)

    def _bind_target(
        self,
        namespace: str,
        target: _CreationTarget,
        object_id: str,
        request_fingerprint: str,
    ) -> SchedulerBinding:
        return self.bindings.bind(
            instance=self._instance_id(),
            namespace=namespace,
            name=target.name,
            logical_name=target.logical_name,
            revision=target.revision,
            object_id=object_id,
            request_fingerprint=request_fingerprint,
        )

    def _require_scheduling_enabled(self) -> None:
        if self.session_key is not None and not self.bindings.client_enabled(session_key=self.session_key):
            raise RootToolError("this research client is paused by the workbench; resume it in the local workbench before scheduling")

    def _instance_id(self) -> str:
        if self.session_key is not None:
            bound = self.bindings.session_instance(session_key=self.session_key)
            if bound is not None:
                self.bindings.require_active_instance(instance_id=bound)
                self.instance = bound
                return bound
            self.instance = None
            raise RootToolError(
                "this MCP session is not bound to a research instance; "
                "open the direct local management URL returned by instance_current"
            )
        if self.instance is None:
            raise RootToolError("no research instance is selected")
        return self.instance

    @staticmethod
    def _binding_value(binding: SchedulerBinding) -> dict[str, Any]:
        return {
            "name": binding.name,
            "logical_name": binding.logical_name,
            "revision": binding.revision,
        }

    @staticmethod
    def _instance_value(value: Any) -> dict[str, Any]:
        return {
            "name": value.name,
            "title": value.title,
            "objective": value.objective,
            "state": value.state,
            "created_at": value.created_at,
            "closed_at": value.closed_at,
        }


class RootMCPRouter:
    def __init__(self, facade: RootToolFacade) -> None:
        self.facade = facade
        tools = root_tools_for_backend("local")
        self._ordered_tools = tools
        self._tools = {tool.name: tool for tool in tools}
        self._tool_schemas = tuple(freeze_json(tool.schema()) for tool in tools)

    def list_tools(self) -> list[dict[str, Any]]:
        return json_projection(self._tool_schemas)

    def call_tool(self, name: str, arguments: dict[str, Any] | None) -> Any:
        gate = getattr(self.facade.runs, "instance_maintenance", None)
        if gate is None:
            return self._call_tool(name, arguments)

        def current():
            # Never trust a facade cached before a management close/unbind.
            if self.facade.session_key is not None:
                return self.facade.bindings.session_instance(session_key=self.facade.session_key)
            return self.facade.instance

        if name == "instance_close":
            with gate.global_guard():
                instance_id = current()
            if instance_id is not None:
                with gate.exclusive(instance_id):
                    from ..service.instance_maintenance import InstanceMaintenanceUnavailable
                    if current() != instance_id:
                        raise InstanceMaintenanceUnavailable("session binding changed before instance close")
                    gate.ensure_available(instance_id)
                    self.facade.bindings.require_active_instance(instance_id=instance_id)
                    return self._call_tool(name, arguments)
        with gate.global_guard():
            instance_id = current()
            if instance_id is not None and name not in {"instance_current", "instance_list", "operation_catalog"}:
                with gate.guard(instance_id):
                    self.facade.bindings.require_active_instance(instance_id=instance_id)
                    return self._call_tool(name, arguments)
            return self._call_tool(name, arguments)

    def _call_tool(self, name: str, arguments: dict[str, Any] | None) -> Any:
        try:
            tool = self._tools[name]
        except KeyError as error:
            raise RootToolError(f"unknown root tool: {name}") from error
        try:
            if tool.input_model is IngestTextInput:
                # Validate strings before JSON parsing can turn invalid Unicode
                # into a root-level error without the affected text field.
                parsed = tool.input_model.model_validate(
                    {} if arguments is None else arguments, strict=True
                )
            else:
                parsed = parse_tool_arguments(tool.input_model, arguments)
        except ValidationError as error:
            raise RootToolError("tool arguments do not satisfy the declared model",
                    details=validation_diagnostics(error, schema=tool.schema()["inputSchema"])) from error
        values = {field: getattr(parsed, field) for field in type(parsed).model_fields}
        try:
            if name == "run_status":
                from .mcp_response_views import validate_run_status_profile
                validate_run_status_profile(
                    response_profile=values["response_profile"],
                    view=values["view"],
                    output_mode=values["output_mode"],
                    output_paths=values.get("output_paths"),
                )
            # Presentation options are never part of an immutable operation request.
            query = dict(values)
            query.pop("view", None)
            if name == "artifact_catalog":
                query["view"] = values["view"]
            if name in {"operation_catalog", "scientific_inventory", "scientific_current", "instance_list", "execution_outputs", "execution_capabilities"}:
                query.pop("limit", None)
                query.pop("before", None)
            if name == "operation_catalog":
                query.pop("operation_id", None)
            if name == "scientific_inventory":
                query["include_operations"] = False
            if name == "run_status" and values["output_mode"] == "values" and values["view"] == "summary" and values.get("output_paths") is None:
                query["output_paths"] = ["/summary"]
            from .mcp_response_views import root_response
            return root_response(name, getattr(self.facade, name)(**query), values)
        except Exception as error:
            from ..service.instance_maintenance import InstanceMaintenanceBusy, InstanceMaintenanceUnavailable
            if isinstance(error, (InstanceMaintenanceBusy, InstanceMaintenanceUnavailable)):
                raise
            scope = "session:" + (self.facade.session_key or "unbound")
            try:
                scope = "instance:" + self.facade._instance_id()
            except RootToolError:
                pass
            self.facade.engineering_diagnostics.capture(error, scope=scope, layer="root", action=name)
            raise


__all__ = [
    "ROOT_TOOLS",
    "RootMCPRouter",
    "RootTool",
    "RootToolError",
    "RootToolFacade",
    "root_tools_for_backend",
]
