"""Semantic scheduler MCP with all control identity kept behind the service."""

from __future__ import annotations

from ...agent_execution_settings import ExecutionProfile
from ..schema.scientific_progress import ScientificIntent, ProgressAssessment

import threading
import re
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

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
from ..service.stage_deliveries import StageReadQuery
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


class ProgressionCommandInput(RootToolInput):
    command: Literal["start", "pause", "resume", "stop", "takeover"]
    mode: Literal["interactive", "background"] = "interactive"
    objective_name: str | None = Field(default=None, pattern=_NAME_PATTERN,
        description="Exact frozen original user text or research objective for start; changes require pausing first.")


class ProgressionMessageScope(RootToolInput):
    objective_name: str = Field(pattern=_NAME_PATTERN,
        description="Exact immutable instance name of the expected frozen goal; control resolves its original Artifact binding.")
    loop_id: str = Field(min_length=1, max_length=256,
        description="Unchanged loop.id from the captured control status; a caller scope constraint, never a budget authorization.")


class ProgressionMessageInput(RootToolInput):
    name: str = Field(pattern=_NAME_PATTERN)
    text: str = Field(min_length=1, max_length=16384,
        description="Original user direction or supplementary information; saved unchanged for the next safe decision.")
    expected_scope: ProgressionMessageScope | None = Field(default=None,
        description="Optional caller guard: atomically require this exact frozen goal and authorized loop to remain active/background with available total budget before any saved acknowledgement or intake. Does not resume control, grant authority or judge science. Omit for ordinary reader context, including paused goals.")


class ProgressionStatusInput(RootToolInput):
    progress_cursor: str | None = Field(default=None, max_length=512, description="Continue using progress.next_cursor unchanged, bound to this exact instance and frozen goal.")
    progress_limit: int = Field(default=4, ge=1, le=8)
    delivery_cursor: str | None = Field(default=None, max_length=512, description="Continue terminal_deliveries.next_cursor unchanged; bound to the exact instance and goal.")
    delivery_limit: int = Field(default=8, ge=1, le=8)


class ProgressionReportInput(RootToolInput):
    assessments: list[ProgressAssessment] = Field(default_factory=list, max_length=8,
        description="Optional task-level goal judgments. Control freezes evidence and appends corrections; this is not a scientific result or qualification. Ordinary tasks require no assessment. In configured assist mode, persistent missing or unsupported assessments can trigger observation-gap protection and directly pause further dispatch. Cited new bytes plus a Root advance judgment do not independently establish scientific progress.")
    summary: str = Field(min_length=1, max_length=4096,
        description="Current goal outcome or specific waiting condition; retain scientific limitations.")
    completed: bool = Field(default=False, description="Root judges the whole frozen goal complete, after reading sealed results.")
    question: str | None = Field(default=None, min_length=1, max_length=2048,
        description="Specific missing user information, when needed to continue.")


class ReadInput(RootToolInput):
    view: Literal["summary", "detail"] = Field(default="summary",
        description="Default compact view with explicit omission and original-detail navigation. Detail preserves exact bindings, original logs and full metadata.")


class PageInput(ReadInput):
    limit: int = Field(default=20, ge=1, le=100)
    before: str | None = Field(default=None, max_length=256,
        description="Continue after the exact next_before cursor from this same query.")


class OperationCatalogInput(PageInput):
    view: Literal["summary", "detail", "index", "facets", "matches"] = "summary"
    operation_id: str | None = Field(default=None, max_length=256,
        description="Select one exact operation; use view=detail to read its complete contract before binding.")
    scope: Literal["public", "support", "internal", "all"] = "public"
    before: str | None = Field(default=None, max_length=512,
        description="Continue after the exact next_before cursor from this same query and navigation snapshot.")
    dimension: Literal["consequence", "executor_kind", "input_schema"] | None = None
    where: dict[str, str | list[str]] | None = Field(default=None,
        description="matches only: AND across consequence, executor_kind and input_schema; multiple values within one field are OR.")


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


class ExecutionLogsInput(NamedInput):
    log_index: int = Field(default=0, ge=0)
    direction: Literal["tail", "before", "after"] = "tail"
    cursor: str | None = Field(default=None, max_length=2048, description="Pass the returned before/after cursor unchanged; tail requires no cursor.")


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
    scientific_intent: ScientificIntent | None = Field(default=None,
        description="Optional complete Agent task purpose, recommended for background research. Read-only to the Worker; control supplies all bindings. Ordinary tasks remain valid without it. In configured assist mode, persistent missing intent can trigger observation-gap protection and directly pause further dispatch.")
    parameters: EmptyOperationParameters = Field(default_factory=dict)
    require_execution_review: bool | None = Field(default=None,
        description="Experiment tasks only. Set true when the user/task explicitly requires independent implementation review before formal execution. Control requires a pass on the exact sealed implementation and resolves the review automatically; no Worker binding fields. Omission defaults to false for new tasks and inherits the requirement on recovery. Recovery cannot remove an existing requirement.")
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
    view: Literal['summary', 'detail', 'history'] = Field(default='summary',
        description='history reads recorded terminal facts for the exact goal and its bounded, explicitly sealed supersedes ancestors, or the exact recorded recovery source returned by task navigation. revision_scope states incomplete/missing ancestry; old frozen scopes never expand. It provides attributed existing fields and omissions, not new scientific synthesis or a consumption receipt.')
    state: Literal["queued", "running", "completed", "failed"] | None = None
    limit: int = Field(default=20, ge=1, le=100)
    before: str | None = Field(default=None, max_length=2048,
        description='Pass next_before unchanged. summary/detail use a semantic Run name; history uses opaque control navigation bound to the same instance, goal/source, frozen loop, terminal upper bound, state and limit. Same-key restart retains it; a changed key rejects it and requires new navigation.')

    @field_validator('before')
    @classmethod
    def semantic_or_history_cursor(cls, value, info):
        if value is not None and info.data.get('view') != 'history' and not re.fullmatch(_NAME_PATTERN, value):
            raise ValueError('summary/detail before requires a semantic Run name')
        return value


class ArtifactCatalogInput(NamedReadInput):
    view: Literal["summary", "detail", "parents", "producer_inputs", "content"] = Field(default="summary",
        description="content reads a bounded UTF-8 page of the exact named scientific original; continue using next_cursor as content_cursor. Binary or private control objects are unavailable. summary gives metadata; parents gives one page of direct parents and, for a recovery manifest, mechanically joins sealed source aliases/records to those exact parents; producer_inputs gives one page of the exact immediate producer's frozen input ports without recursive traversal; detail is the legacy full metadata view. parents and producer_inputs share parent_offset/parent_limit. Direct-parent limit remains 4096.")
    parent_offset: int = Field(default=0, ge=0,
        description="parents or producer_inputs view: continue at next_offset for the same artifact.")
    parent_limit: int = Field(default=16, ge=1, le=32)
    content_cursor: str | None = Field(default=None, max_length=512, description="content only: exact next_cursor from the previous page of the same immutable named original.")


class RunStatusInput(NamedInput, StageReadQuery):
    intent: Literal["decision", "status", "navigation", "full"] = Field(default="decision",
        description="decision reads bounded sealed conclusions and scheduler signal after completion, using frozen decision fields for historical Runs; older records without those fields return an explicit unavailable default and bounded field index. status reads lifecycle and optional saved diagnostics; navigation lists exact fields, scientific input names and a page of already sealed public evidence names even while running or after failure; full explicitly reads the complete sealed scientific output. Sealed materials are not final conclusions. Active or failed Runs never expose draft science.")
    output_fields: list[str] | None = Field(default=None, max_length=8,
        description="decision only: named top-level fields; omit for declared decision fields. Mutually exclusive with output_paths.")
    output_paths: list[Annotated[str, Field(pattern=r"^(?:/(?:[^~]|~[01])*)?$")]] | None = Field(
        default=None, max_length=8,
        description="decision: exact non-root JSON Pointers, up to 32 KiB selected values; oversized values carry explicit omissions. navigation: one pointer, omitted for root. Use full for complete output, including oversized scalars. '/' selects an empty key.")
    index_offset: int = Field(default=0, ge=0, description="navigation: continue the field index at output_index.next_offset or the sealed evidence list at evidence_outputs_next_offset.")
    index_limit: int = Field(default=16, ge=1, le=32, description="navigation: direct children, bounded to 8 KiB including metadata.")
    diagnostic_after: int | None = Field(default=None, ge=0,
        description="status: 0 starts a bounded page of saved safe diagnostics, including running Runs; continue at diagnostic_events.next_after. Engineering bodies are excluded; opaque references support an explicit diagnostic_read.")
    diagnostic_limit: int = Field(default=20, ge=1, le=100)


def parse_run_status_arguments(arguments):
    """One intent contract shared by direct facade and MCP callers."""
    try:
        parsed = parse_tool_arguments(RunStatusInput, arguments)
    except ValidationError as error:
        raise RootToolError("tool arguments do not satisfy the declared model",
            details=validation_diagnostics(error, schema=RunStatusInput.model_json_schema())) from error
    values = parsed.model_dump()
    fields = values.pop("output_fields")
    paths, intent = values["output_paths"], values["intent"]
    if fields is not None:
        if intent != "decision" or paths is not None:
            raise RootToolError("output_fields requires decision intent and omitted output_paths")
        paths = ["/" + field.replace("~", "~0").replace("/", "~1") for field in fields]
        values["output_paths"] = paths
    if intent in {"status", "full"} and paths is not None:
        raise RootToolError(f"{intent} intent does not accept output selection")
    if intent == "navigation" and paths is not None and len(paths) != 1:
        raise RootToolError("navigation accepts one output path; omit it for root")
    if intent == "decision" and paths and "" in paths:
        raise RootToolError("root output pointer requires full intent")
    if intent != "navigation" and parsed.model_fields_set & {"index_offset", "index_limit"}:
        raise RootToolError("index pagination requires navigation intent")
    if intent != "status" and parsed.model_fields_set & {"diagnostic_after", "diagnostic_limit"}:
        raise RootToolError("saved diagnostics require status intent")
    return values


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
    surface: Literal["research", "execution"] = "research"

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_model.model_json_schema(),
        }


SCHEDULING_WRITES = frozenset({
    "instance_close", "scientific_current_select", "artifact_ingest_file", "artifact_ingest_text",
    "operation_invoke", "run_record_failure", "execution_capability_bind", "execution_abandon",
    "execution_cancel", "execution_outputs", "execution_start", "execution_sync", "execution_collect",
})

ROOT_TOOLS = (
    RootTool("progression_message", "Save original user context for the started goal from an authorized reading session, without taking over the background writer. Optional expected_scope atomically constrains saving and old acknowledgements to the exact active/background goal and authorized loop with available total budget. Does not grant approvals, resume a paused goal or judge science.", ProgressionMessageInput),
    RootTool("progression_report", "Optionally record a goal outcome, waiting condition, user question or evidence-based task assessment. Corrections append immutable history. Ordinary tasks and stages require no extra report. Root supported advance and new bytes are not verified progress. The configured consumed unverified window requires direction confirmation in assist; only a first predeclared controlled test resolution or qualified independent exact test judgment can clear it. Waiting does not count, repeated checks and target revisions do not renew the window, and human continuation does not renew resource budgets. No research is triggered by this report.", ProgressionReportInput),
    RootTool("progression_status", "Read scheduling ownership, frozen objective, sealed task handoff and recent Root assessment history; continue assessment history with progress_cursor and terminal delivery history with delivery_cursor. Accepted work has independent Run state.", ProgressionStatusInput),
    RootTool("progression_command", "Start, pause, resume, stop or explicitly take over scheduling for the selected instance. Background work requires a research loop budget explicitly authorized in the management UI; this command cannot create or replenish it. All later interactive and background work retains that loop across goal changes and recovery. Background start remains pending until its host is available. Pause/stop do not cancel accepted work or clear scientific pauses. The management UI confirms a new consumed observation window without refunding limits.", ProgressionCommandInput),
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
    RootTool("artifact_catalog", "Read metadata, paged originals (view=content), or direct parents for one exact named scientific material.", ArtifactCatalogInput),
    RootTool("operation_catalog", "List bounded operation summaries; select operation_id with view=detail for its full compiled contract.", OperationCatalogInput),
    RootTool("operation_preflight", "Optional check without creating. Invoke independently checks admission; this does not reserve resources or authorize execution.", OperationCallInput),
    RootTool("operation_invoke", "Validate and create one Agent, Transform, Effect or Approval from the compiled catalog; no prior preflight required. Success preserves dispatch configuration, exact outputs or approval URLs by executor kind; use the returned detail entry for Run context.", OperationCallInput),
    RootTool("run_list", "List minimal Runs in this research instance. current_goal_tasks identifies exact frozen-goal members on this page. view=history freezes terminal and judgment upper bounds for the exact goal and bounded immutable supersedes ancestors authorized in this instance; revision_scope reports missing ancestry and the 2048-character cursor capacity. Names, schema and common parents do not imply revisions; existing frozen scopes never expand. Use an older task's run_status navigation attempt_history.read for its exact old goal or recorded recovery source. Pass the returned continuation unchanged; later tasks/completion/judgments stay out. Missing content remains unknown; attributed Worker conclusions and Root judgments are not controlled verification, consumption or qualification.", RunListInput),
    RootTool("run_status", "Read a Run with one intent: decision (default), status, navigation or full. Explicit stage_offset=0 lists sealed stages even while running; stage_reference reads an exact material. Stages never establish final completion or qualification.", RunStatusInput),
    RootTool("run_record_failure", "Record failure of one running minimal Run.", RunFailureInput),
    RootTool("approval_list", "List named reviews in this scheduler instance.", ApprovalListInput),
    RootTool("approval_status", "Read one named human-review state.", NamedReadInput),
    RootTool("execution_capabilities", "List sanitized execution capabilities for one compiled Effect operation.", ExecutionCapabilitiesInput, surface="execution"),
    RootTool("execution_capability_bind", "Freeze one capability selected through a compiled Effect under a semantic artifact name.", ExecutionCapabilityBindInput, surface="execution"),
    RootTool("execution_abandon", "Abandon one named unsubmitted execution. For an uncertain new-protocol request, control first permanently fences the exact remote submission; an existing job is recovered instead. Unreachable or older backends cannot prove absence and retain the reservation. An active submission owner must finish first.", NamedInput, surface="execution"),
    RootTool("execution_cancel", "Cancel the exact existing job, or retire an uncertain new-protocol submission before abandoning it and releasing its reservation. Never infer permanent absence from lookup found=false.", NamedInput, surface="execution"),
    RootTool("execution_list", "List standalone executions and recoverable executions whose task lineage has failed.", ExecutionListInput, surface="execution"),
    RootTool("execution_status", "Refresh remote state and bounded progress for one submitted execution; never submit, cancel or collect. Pending submissions read durable control state; uncertain submissions trigger only exact read-only lookup, never submit. Confirmed terminal executions read control state directly. Query failures retain the last observation with an explicit error. Status returns timing and log metadata without log text; execution_logs pages the saved cache without querying the remote.", NamedReadInput, surface="execution"),
    RootTool("execution_logs", "Read one bounded page of this execution's cached diagnostic log; never query the remote, submit or collect. Default tail reads the newest page; before reads earlier pages, after reads new text. Pass the matching returned cursor unchanged. No new text returns empty text. A replaced/rotated snapshot that cannot prove continuity returns gap=snapshot_replaced with the newest page and fresh cursors. Cursors belong to this exact execution/log. Select 0 <= log_index < status log_count. After collection use execution_outputs for retained files.", ExecutionLogsInput, surface="execution"),
    RootTool("execution_outputs", "Bind and list logical outputs and the exact result_artifact_name from this execution; null means not yet bindable. Bind that result before creating analysis; every page preserves the same identity.", NamedPageInput, surface="execution"),
    RootTool("execution_start", "Start a bounded background submission of one named execution after its exact review and execution policy authorize it. submission.state=pending is an acknowledgement, not solver success. Poll execution_status with the same name; unknown means read-only lookup is needed, never create a replacement. Async errors remain in submission.error; awaiting_authorization exposes the approval. After a task lineage fails, this can start or recover its original unsubmitted request without creating a Run or consuming a scientific retry; the original implementation, review and authorization remain mandatory.", NamedInput, surface="execution"),
    RootTool("execution_sync", "Refresh bounded solver status and logs, including failed-task recovery; never submit or collect artifacts.", NamedReadInput, surface="execution"),
    RootTool("execution_collect", "Start or resume terminal artifact collection; returns immediately. Other active collection returns busy without queuing.", ExecutionCollectInput, surface="execution"),
)


def root_tools_for_backend(worker_backend: str) -> tuple[RootTool, ...]:
    from ..runtime import validate_worker_backend
    validate_worker_backend(worker_backend)
    return ROOT_TOOLS


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

    def _task_managed_execution(self, execution_id: str) -> bool:
        return self._task_execution_owner(execution_id) is not None

    def _task_execution_owner(self, execution_id: str) -> str | None:
        request = self.executions.request_artifact_id(execution_id)
        return self.executions.artifacts.get_by_id(request).labels.get("experiment_run")

    def _execution_recoverable(self, execution_id: str) -> bool:
        owner = self._task_execution_owner(execution_id)
        return owner is not None and self.runs.task_recovery_available(
            owner, instance_id=self._instance_id())

    def _resolve(self, namespace: str, name: str, *, allow_task_recovery: bool = False) -> str:
        object_id = self.bindings.resolve(
            instance=self._instance_id(), namespace=namespace, name=name
        )
        if (namespace == "execution" and self._task_managed_execution(object_id)
                and not (allow_task_recovery and self._execution_recoverable(object_id))):
            raise RootToolError("Execution is managed within its scientific task; read the task's scientific materials.")
        return object_id

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

    def _binding(self, namespace: str, name: str, *, allow_task_recovery: bool = False) -> SchedulerBinding:
        if namespace == "execution":
            self._resolve(namespace, name, allow_task_recovery=allow_task_recovery)
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
        binding = self.bindings.bind(
            instance=self._instance_id(),
            namespace=namespace,
            name=target.name,
            logical_name=target.logical_name,
            revision=target.revision,
            object_id=object_id,
            request_fingerprint=request_fingerprint,
        )
        if namespace in {'run', 'approval'}:
            self.bindings.record_goal_binding(instance_id=self._instance_id(), session_key=self.session_key,
                namespace=namespace, name=target.name, object_id=object_id)
        if namespace == "run":
            self.bindings.record_dispatch_intent(instance_id=self._instance_id(), run_id=object_id, session_key=self.session_key)
        return binding

    @contextmanager
    def scheduling_guard(self, *, continuation=None):
        instance_id = self._instance_id()
        observed = self.bindings.progression_status(instance_id=instance_id, internal=True)
        with self.bindings.scheduling_guard(instance_id=instance_id, session_key=self.session_key,
                expected_generation=observed.get("generation"), continuation=continuation) as generation:
            yield generation

    def progression_message(self, **values):
        scope = values.get('expected_scope')
        if isinstance(scope, ProgressionMessageScope):
            values['expected_scope'] = scope.model_dump(mode='json')
        return self.bindings.progression_message(instance_id=self._instance_id(), session_key=self.session_key,
            intake=self.intake, **values)

    def progression_report(self, **values):
        return self.bindings.progression_report(instance_id=self._instance_id(), session_key=self.session_key,
            artifacts=self.artifacts, runs=self.runs, **values)

    def progression_status(self, progress_cursor=None, progress_limit=4, delivery_cursor=None, delivery_limit=8):
        from ..service.progression_read import progression_read_view
        return progression_read_view(bindings=self.bindings, runs=self.runs, artifacts=self.artifacts, executions=self.executions,
            operation_catalog=self._operation_catalog, instance_id=self._instance_id(), session_key=self.session_key,
            progress_cursor=progress_cursor, progress_limit=progress_limit, delivery_cursor=delivery_cursor, delivery_limit=delivery_limit)

    def progression_command(self, *, command, mode="interactive", objective_name=None):
        instance_id = self._instance_id()
        ref = None
        if objective_name is not None:
            artifact = self.artifacts.get_by_id(self._resolve_input_artifact(objective_name))
            from ..service.scheduling_control import is_goal_anchor
            if not is_goal_anchor(artifact):
                raise RootToolError("start requires frozen original user text or a research objective Artifact")
            ref = artifact.ref
        return self.bindings.progression_command(instance_id=instance_id, session_key=self.session_key,
            command=command, mode=mode, objective_name=objective_name, objective_ref=ref)

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

    def list_tools(self, *, surface: str = "research") -> list[dict[str, Any]]:
        return [json_projection(schema) for tool, schema in zip(self._ordered_tools, self._tool_schemas)
                if tool.surface == surface]

    def call_tool(self, name: str, arguments: dict[str, Any] | None, *, surface: str = "research") -> Any:
        tool = self._tools.get(name)
        if tool is None or tool.surface != surface:
            raise RootToolError(f"interface is not available on {surface} surface: {name}")
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
        # Invocation validates immutable inputs before its own scheduling guard.
        if (name in SCHEDULING_WRITES and name != "operation_invoke"
                and not getattr(getattr(self.facade, name), 'scheduling_guarded', False)):
            with self.facade.scheduling_guard():
                return self._dispatch_tool(name, arguments)
        return self._dispatch_tool(name, arguments)

    def _dispatch_tool(self, name: str, arguments: dict[str, Any] | None) -> Any:
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
                return self.facade.run_status(**parsed.model_dump(exclude_unset=True))
            # Presentation options are never part of an immutable operation request.
            query = dict(values)
            query.pop("view", None)
            if name in {"artifact_catalog", "run_list"}:
                query["view"] = values["view"]
            if name in {"operation_catalog", "scientific_inventory", "scientific_current", "instance_list", "execution_outputs", "execution_capabilities"}:
                query.pop("limit", None)
                query.pop("before", None)
            if name == "operation_catalog":
                if values["view"] != "detail":
                    query.pop("operation_id", None)
                query.pop("dimension", None)
                query.pop("where", None)
                if values["view"] in {"summary", "index", "facets", "matches"}:
                    query["navigation"] = True
            if name == "scientific_inventory":
                query["include_operations"] = False
            from .mcp_response_views import root_response
            return root_response(name, getattr(self.facade, name)(**query), values)
        except Exception as error:
            from ..service.instance_maintenance import InstanceMaintenanceBusy, InstanceMaintenanceUnavailable
            if isinstance(error, (InstanceMaintenanceBusy, InstanceMaintenanceUnavailable)):
                raise
            # Expected caller repair is already a complete scientific diagnostic.
            # Do not misclassify it as a host failure or invite traceback reading.
            details = getattr(error, "details", ())
            if details and all(item.get("phase") == "input_admission"
                               and item.get("repairable") is True for item in details):
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
