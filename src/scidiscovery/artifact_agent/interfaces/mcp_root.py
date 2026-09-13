"""Semantic scheduler MCP with all control identity kept behind the service."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ...operation_contract import validation_diagnostics, contract_diagnostic
from ...operations.tooling import parse_tool_arguments
from ...operations.invoke import EmptyOperationParameters
from ...operations.spec import freeze_json, json_projection

from ..execution_bridge import ExecutionBridge
from ..service.approvals import ApprovalService
from ..service.artifacts import ArtifactService
from ..service.executions import ExecutionService
from ..service.intake import SecureIntakeService
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


class OperationCatalogInput(RootToolInput):
    scope: Literal["public", "support", "internal", "all"] = "public"


class NamedInput(RootToolInput):
    name: str = Field(pattern=_NAME_PATTERN)


class DiagnosticReadInput(RootToolInput):
    reference: str = Field(pattern=r"^diag_[0-9a-f]{32}$")
    offset: int = Field(default=0, ge=0)
    max_bytes: int = Field(default=16384, ge=1, le=65536)
    section: Literal["summary", "traceback", "stdout", "stderr"] = "summary"


class ExecutionCollectInput(NamedInput):
    total_seconds: float = Field(default=COLLECTION_SECONDS, gt=0, allow_inf_nan=False,
        description="Total collection attempt budget, including transfer, registration and cleanup. A running attempt is never extended by a duplicate call.")


class InstanceListInput(RootToolInput):
    state: Literal["active", "closed"] | None = None


class RevisionInput(RootToolInput):
    on_conflict: Literal["reject", "create_revision"] = "reject"


class IngestFileInput(NamedInput, RevisionInput):
    relative_path: str = Field(min_length=1, max_length=4096)
    media_type: str | None = Field(default=None, min_length=3, max_length=255)


class OperationInputSelection(RootToolInput):
    port: str = Field(pattern=_SOURCE_NAME_PATTERN)
    artifact_names: tuple[str, ...] = Field(max_length=256)


class OperationCallInput(NamedInput, RevisionInput):
    operation_id: str = Field(min_length=1, max_length=128)
    inputs: tuple[OperationInputSelection, ...] = Field(max_length=64)
    instruction: str | None = Field(default=None, max_length=65536)
    parameters: EmptyOperationParameters = Field(default_factory=dict)
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


class RunListInput(RootToolInput):
    state: Literal["queued", "running", "completed", "failed"] | None = None
    limit: int = Field(default=50, ge=1, le=100)
    before: str | None = Field(default=None, pattern=_NAME_PATTERN,
        description="Continue after this semantic Run name, returned as next_before by the previous page.")


class RunStatusInput(NamedInput):
    diagnostic_after: int | None = Field(default=None, ge=0,
        description="Set to 0 for the first page of saved errors, then use diagnostic_events.next_after. Omit for the compact status.")
    diagnostic_limit: int = Field(default=50, ge=1, le=100)


class RunFailureInput(NamedInput):
    reason: str = Field(min_length=1, max_length=4096)
    expected_state: Literal["queued", "running"]
    expected_last_activity_at: str | None
    timed_out: bool = False


class ApprovalListInput(RootToolInput):
    status: Literal["pending", "decided", "expired", "cancelled_by_human"] | None = None
    limit: int = Field(default=50, ge=1, le=100)


class ExecutionCapabilitiesInput(RootToolInput):
    operation_id: str = Field(min_length=1, max_length=256)


class ExecutionCapabilityBindInput(NamedInput, RevisionInput):
    operation_id: str = Field(min_length=1, max_length=256)
    profile: str = Field(pattern=_NAME_PATTERN)


class ExecutionListInput(RootToolInput):
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
    limit: int = Field(default=50, ge=1, le=100)


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
    RootTool("instance_current", "Read the bound research instance or return its direct local management URL.", EmptyInput),
    RootTool("instance_list", "List research instances without exposing internal identity.", InstanceListInput),
    RootTool("instance_close", "Close the current research instance against further writes.", EmptyInput),
    RootTool("scientific_inventory", "List current immutable scientific objects without suggesting a workflow or capability.", EmptyInput),
    RootTool("scientific_current", "Read explicit current scientific-object selections for this research instance.", EmptyInput),
    RootTool("scientific_current_select", "Compare-and-set one immutable scientific object as the explicit current selection.", ScientificCurrentSelectInput),
    RootTool("lifecycle_events", "Return persistent semantic task, approval, and execution state changes for this scheduler process.", EmptyInput),
    RootTool("artifact_ingest_file", "Freeze and bind one project file under a semantic name.", IngestFileInput),
    RootTool("artifact_catalog", "Read sanitized metadata for one bound semantic input.", NamedInput),
    RootTool("operation_catalog", "List one view of installed compiled operations without implementation identity.", OperationCatalogInput),
    RootTool("operation_preflight", "Check one exact operation call without writing control state.", OperationCallInput),
    RootTool("operation_invoke", "Create one Agent, Transform, or Effect through the compiled operation catalog.", OperationCallInput),
    RootTool("run_list", "List minimal Runs in this research instance.", RunListInput),
    RootTool("run_status", "Read one minimal Run and optional paginated error history; completed Runs include their sealed scientific output.", RunStatusInput),
    RootTool("run_record_failure", "Record failure of one running minimal Run.", RunFailureInput),
    RootTool("approval_list", "List named reviews in this scheduler instance.", ApprovalListInput),
    RootTool("approval_status", "Read one named human-review state.", NamedInput),
    RootTool("execution_capabilities", "List sanitized execution capabilities for one compiled Effect operation.", ExecutionCapabilitiesInput),
    RootTool("execution_capability_bind", "Freeze one capability selected through a compiled Effect under a semantic artifact name.", ExecutionCapabilityBindInput),
    RootTool("execution_abandon", "Abandon one named unsubmitted execution.", NamedInput),
    RootTool("execution_cancel", "Request cancellation of one named submitted execution.", NamedInput),
    RootTool("execution_list", "List named executions in this scheduler instance.", ExecutionListInput),
    RootTool("execution_status", "Read one named execution state.", NamedInput),
    RootTool("execution_outputs", "Bind and list logical outputs from one named execution.", NamedInput),
    RootTool("execution_start", "Submit one named execution after its exact local review authorizes it.", NamedInput),
    RootTool("execution_sync", "Refresh bounded solver status and logs; never collect artifacts.", NamedInput),
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
        try:
            tool = self._tools[name]
        except KeyError as error:
            raise RootToolError(f"unknown root tool: {name}") from error
        try:
            parsed = parse_tool_arguments(tool.input_model, arguments)
        except ValidationError as error:
            raise RootToolError("tool arguments do not satisfy the declared model",
                    details=validation_diagnostics(error, schema=tool.schema()["inputSchema"])) from error
        values = {field: getattr(parsed, field) for field in type(parsed).model_fields}
        try:
            return getattr(self.facade, name)(**values)
        except Exception as error:
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
