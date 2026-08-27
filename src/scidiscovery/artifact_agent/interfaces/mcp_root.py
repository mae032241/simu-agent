"""Semantic scheduler MCP with all control identity kept behind the service."""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from dataclasses import dataclass
from typing import Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..execution_bridge import ExecutionBridge
from ..schema.approval import (
    ApprovalDisplayTranslation,
    ApprovalOption,
    ApprovalPresentation,
    HumanDecision,
)
from ..schema.artifact import ArtifactRegistration
from ..schema.claim import project_claim_decision
from ..schema.cognitive import EvidenceAudit
from ..schema.common import canonical_json, canonical_sha256
from ..schema.curve_score import CurveConsistencyReport
from ..schema.device_parameters import (
    DeviceParameterCoverageReport,
    DeviceParameterRequirementSet,
    DeviceParameterSet,
    EvidenceSourceCatalog,
    evaluate_device_parameter_coverage,
)
from ..schema.experiment import (
    ExperimentPortfolio,
    deterministic_validation_check_keys,
)
from ..schema.layered_diagnosis import LayeredDiagnosisReport
from ..schema.scientific_foundation import ScientificFoundation
from ..schema.scientific_objective import (
    ObjectiveCoverageReport,
    ResearchObjectiveContract,
    project_objective_readiness,
)
from ..schema.research_cycle import (
    ArtifactKind,
    ProblemFrame,
    ScientificClosureStatus,
    ScientificObjectStatus,
    ScientificReadiness,
)
from ..schema.task import TaskBudget, TaskInput, TaskOutputSpec, TaskRevisionSpec
from ..schema.validation import ValidationReport
from ..service.approvals import ApprovalService
from ..service.artifacts import ArtifactService
from ..service.executions import ExecutionService
from ..service.intake import SecureIntakeService
from ..service.scheduler_bindings import (
    SchedulerBinding,
    SchedulerBindingService,
    SchedulerInstanceNotFound,
    SchedulerNameConflict,
    SchedulerNameNotFound,
)
from ..service.tasks import TaskService
from ..transforms import (
    STRUCTURED_REVISION_APPLY_PROFILE,
    UNCHANGED_EVIDENCE_RECEIPT_PROFILE,
    ArtifactTransformAdapter,
    select_transform_adapter,
)
from ...scheduler_topology import ready_capabilities


_NAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}$"
_SOURCE_NAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$"
_SCIENTIFIC_ARTIFACT_KINDS = frozenset(get_args(ArtifactKind))
_NONQUALIFYING_HANDOFF_VERDICTS = frozenset({"blocked", "revise"})
_DEVICE_PARAMETER_APPROVAL_SCHEMAS = frozenset(
    {
        "scidiscovery.device-parameter-requirements.v1",
        "scidiscovery.device-parameter-set.v1",
        "scidiscovery.evidence-source-catalog.v1",
        "scidiscovery.device-parameter-coverage.v1",
    }
)
_PARAMETER_AUDIT_CHECKS = frozenset(
    {
        "parameter_completeness",
        "source_traceability",
        "source_independence",
        "unit_condition_consistency",
    }
)
_REVISION_TRANSFORM_INPUTS = {
    STRUCTURED_REVISION_APPLY_PROFILE: frozenset({"base_object"}),
    UNCHANGED_EVIDENCE_RECEIPT_PROFILE: frozenset({"base_object"}),
}
_REVISION_TARGETS_BY_ROLE = {
    "evidence_extractor": frozenset(
        {
            "scidiscovery.scientific-intake.v1",
            "scidiscovery.scientific-foundation.v1",
        }
    ),
    "ideator": frozenset(
        {
            "scidiscovery.hypothesis-proposal.v1",
            "scidiscovery.hypothesis-portfolio.v1",
        }
    ),
    "experiment_designer": frozenset(
        {"scidiscovery.experiment-portfolio.v1"}
    ),
}


def _qualified_materialized_project_refs(
    *,
    objects: list[ScientificObjectStatus],
    envelopes: dict[str, Any],
    artifacts: ArtifactService,
) -> frozenset[Any]:
    refs: set[Any] = set()
    for item in objects:
        if item.kind != "tcad_project" or item.qualification != "qualified":
            continue
        envelope = envelopes[item.semantic_name]
        try:
            payload = json.loads(artifacts.read(envelope.ref))
            report = payload["materialization_report"]
            preflight = payload["preflight_attestation"]
            qualified = (
                isinstance(report, dict)
                and report.get("status") == "pass"
                and isinstance(preflight, dict)
                and preflight.get("qualified") is True
                and preflight.get("source_tree_sha256")
                == report.get("source_tree_sha256")
            )
        except (KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
            qualified = False
        if qualified:
            refs.add(envelope.ref)
    return frozenset(refs)


def _qualified_tcad_review_pair_exists(
    *,
    objects: list[ScientificObjectStatus],
    envelopes: dict[str, Any],
    artifacts: ArtifactService,
    project_refs: frozenset[Any],
    portfolio_names: frozenset[str] | None = None,
) -> bool:
    if not project_refs:
        return False
    plan_refs = {
        envelopes[item.semantic_name].ref
        for item in objects
        if item.kind == "experiment_portfolio" and item.qualification == "qualified"
        and (portfolio_names is None or item.semantic_name in portfolio_names)
    }
    if not plan_refs:
        return False
    for item in objects:
        if item.kind != "deck_review" or item.qualification != "qualified":
            continue
        envelope = envelopes[item.semantic_name]
        try:
            payload = json.loads(artifacts.read(envelope.ref))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if (
            isinstance(payload, dict)
            and payload.get("verdict") == "pass"
            and payload.get("execution_ready") is True
            and any(ref in envelope.parent_refs for ref in project_refs)
            and any(ref in envelope.parent_refs for ref in plan_refs)
        ):
            return True
    return False


class RootToolError(RuntimeError):
    pass


class RootToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmptyInput(RootToolInput):
    pass


class NamedInput(RootToolInput):
    name: str = Field(pattern=_NAME_PATTERN)


class InstancePrepareInput(NamedInput):
    title: str = Field(min_length=1, max_length=512)
    objective: str = Field(min_length=1, max_length=8192)


class InstanceListInput(RootToolInput):
    state: Literal["active", "closed"] | None = None


class RevisionInput(RootToolInput):
    on_conflict: Literal["reject", "create_revision"] = "reject"


class IngestFileInput(NamedInput, RevisionInput):
    relative_path: str = Field(min_length=1, max_length=4096)
    media_type: str | None = Field(default=None, min_length=3, max_length=255)


class TransformInputSelection(RootToolInput):
    source_name: str = Field(pattern=_SOURCE_NAME_PATTERN)
    artifact_name: str = Field(pattern=_NAME_PATTERN)


class ArtifactTransformInput(NamedInput, RevisionInput):
    profile: str = Field(min_length=1, max_length=256)
    inputs: tuple[TransformInputSelection, ...] = Field(min_length=1, max_length=32)


class ScientificCurrentSelectInput(NamedInput):
    kind: Literal["research_objective", "experiment_portfolio"]


class TaskInputSelection(RootToolInput):
    source_name: str = Field(pattern=_SOURCE_NAME_PATTERN)
    artifact_name: str = Field(pattern=_NAME_PATTERN)
    exposure: Literal["full", "on_demand", "handoff_only"] = "on_demand"
    usage: Literal[
        "claim_evidence",
        "revision_base",
        "change_request",
        "prior_signal",
        "cached_excerpt",
        "unchanged_set_receipt",
        "evidence_inventory",
    ] = "claim_evidence"


class TaskScheduleInput(NamedInput, RevisionInput):
    role: str = Field(min_length=1, max_length=256)
    context_profile: str | None = Field(default=None, min_length=1, max_length=256)
    output_profile: str | None = Field(default=None, min_length=1, max_length=256)
    revision_base_source: str | None = Field(
        default=None, pattern=_SOURCE_NAME_PATTERN
    )
    allowed_revision_paths: tuple[str, ...] = Field(default=(), max_length=64)
    instruction: str = Field(min_length=1, max_length=65536)
    inputs: tuple[TaskInputSelection, ...] = Field(default=(), max_length=256)
    dependency_names: tuple[str, ...] = Field(default=(), max_length=64)
    max_output_bytes: int = Field(default=262144, ge=1, le=8 * 1024 * 1024)
    timeout_seconds: int = Field(default=900, ge=1, le=86400)
    max_attempts: int = Field(default=1, ge=1, le=10)


class TaskListInput(RootToolInput):
    state: Literal[
        "created",
        "dispatched",
        "claimed",
        "finalizing",
        "completed",
        "failed",
        "timed_out",
    ] | None = None
    limit: int = Field(default=50, ge=1, le=100)


class DispatchInput(NamedInput):
    ttl_seconds: int = Field(default=900, ge=1, le=86400)


class FailureInput(NamedInput):
    reason: str = Field(min_length=1, max_length=4096)
    timed_out: bool = False
    expected_state: Literal["created", "dispatched", "claimed", "finalizing"]
    expected_last_activity_at: str | None


class ApprovalOptionInput(RootToolInput):
    option_key: str = Field(min_length=1, max_length=256)
    label: str = Field(min_length=1, max_length=256)
    description: str = Field(min_length=1, max_length=4096)
    requires_rationale: bool = False
    terminal_state: Literal["decided", "cancelled_by_human"] = "decided"


class ApprovalDisplayTranslationInput(RootToolInput):
    subject_name: str = Field(pattern=_NAME_PATTERN)
    json_pointer: str = Field(min_length=1, max_length=4096)
    text: str = Field(min_length=1, max_length=8192)


class ApprovalPresentationInput(RootToolInput):
    locale: Literal["zh-CN"]
    translations: tuple[ApprovalDisplayTranslationInput, ...] = Field(
        min_length=1, max_length=512
    )


class ApprovalCreateInput(NamedInput, RevisionInput):
    kind: str = Field(min_length=1, max_length=256)
    subject_names: tuple[str, ...] = Field(min_length=1, max_length=256)
    question: str = Field(min_length=1, max_length=16384)
    options: tuple[ApprovalOptionInput, ...] = Field(min_length=2, max_length=32)
    expires_at: str | None = None
    presentation: ApprovalPresentationInput | None = None


class ApprovalListInput(RootToolInput):
    status: Literal["pending", "decided", "expired", "cancelled_by_human"] | None = None
    limit: int = Field(default=50, ge=1, le=100)


class ExecutionCreateInput(NamedInput, RevisionInput):
    executor: str = Field(min_length=1, max_length=256)
    preparation_profile: str = Field(min_length=1, max_length=256)
    payload_name: str = Field(pattern=_NAME_PATTERN)


class ExecutionCapabilitiesInput(RootToolInput):
    executor: str = Field(min_length=1, max_length=256)


class ExecutionCapabilityBindInput(NamedInput, RevisionInput):
    executor: str = Field(min_length=1, max_length=256)
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


@dataclass(frozen=True)
class _CreationTarget:
    name: str
    logical_name: str
    revision: int
    existing_object_id: str | None


ROOT_TOOLS = (
    RootTool("instance_prepare", "Freeze one research-instance proposal for direct local human review.", InstancePrepareInput),
    RootTool("instance_status", "Read one named instance proposal and its human-decision state.", NamedInput),
    RootTool("instance_select", "Request local human review before binding this MCP session to one existing instance.", NamedInput),
    RootTool("instance_current", "Read the bound research instance or prepare local human review for an unbound MCP session.", EmptyInput),
    RootTool("instance_list", "List research instances without exposing internal identity.", InstanceListInput),
    RootTool("instance_close", "Close the current research instance against further writes.", EmptyInput),
    RootTool("scientific_readiness", "Project the current scientific inventory, blockers, and data-ready actions without imposing a workflow.", EmptyInput),
    RootTool("scientific_current", "Read explicit current scientific-object selections for this research instance.", EmptyInput),
    RootTool("scientific_current_select", "Select one qualified semantic lineage as the explicit current objective or experiment plan.", ScientificCurrentSelectInput),
    RootTool("lifecycle_events", "Return persistent semantic task, approval, and execution state changes for this scheduler process.", EmptyInput),
    RootTool("artifact_ingest_file", "Freeze and bind one project file under a semantic name.", IngestFileInput),
    RootTool("artifact_catalog", "Read sanitized metadata for one bound semantic input.", NamedInput),
    RootTool("artifact_transform", "Apply one configured deterministic transform to bound semantic inputs.", ArtifactTransformInput),
    RootTool("task_schedule", "Create one named scientific task from bound semantic inputs.", TaskScheduleInput),
    RootTool("task_ready", "List dependency-ready semantic task names.", EmptyInput),
    RootTool("task_list", "List named tasks in this scheduler instance.", TaskListInput),
    RootTool("task_status", "Read one named task state and bounded scheduler signal.", NamedInput),
    RootTool("task_outputs", "Bind and list collection outputs produced by one named task.", NamedInput),
    RootTool("task_evidence_sources", "List frozen web snapshots and source-bound PDF excerpts produced by one task.", NamedInput),
    RootTool("task_prepare_dispatch", "Queue one named task and return its worker role.", DispatchInput),
    RootTool("task_record_failure", "Record one named task failure using a compare-and-set precondition.", FailureInput),
    RootTool("task_retry", "Return one named failed task to the ready queue.", NamedInput),
    RootTool("approval_request_create", "Create a named local human review for bound subjects.", ApprovalCreateInput),
    RootTool("approval_list", "List named reviews in this scheduler instance.", ApprovalListInput),
    RootTool("approval_status", "Read one named human-review state.", NamedInput),
    RootTool("execution_capabilities", "List sanitized execution capabilities currently advertised by one configured adapter.", ExecutionCapabilitiesInput),
    RootTool("execution_capability_bind", "Freeze one explicitly selected execution capability under a semantic artifact name.", ExecutionCapabilityBindInput),
    RootTool("execution_request_create", "Create one named execution from a bound payload.", ExecutionCreateInput),
    RootTool("execution_approval_request_create", "Create the local review for one named execution.", NamedInput),
    RootTool("execution_abandon", "Abandon one named unsubmitted execution.", NamedInput),
    RootTool("execution_cancel", "Request cancellation of one named submitted execution.", NamedInput),
    RootTool("execution_list", "List named executions in this scheduler instance.", ExecutionListInput),
    RootTool("execution_status", "Read one named execution state.", NamedInput),
    RootTool("execution_outputs", "Bind and list logical outputs from one named execution.", NamedInput),
    RootTool("execution_start", "Submit one named execution after its exact local review authorizes it.", NamedInput),
    RootTool("execution_sync", "Synchronize one named submitted execution.", NamedInput),
)


class RootToolFacade:
    def __init__(
        self,
        artifacts: ArtifactService,
        intake: SecureIntakeService,
        *,
        tasks: TaskService,
        approvals: ApprovalService,
        executions: ExecutionService,
        bindings: SchedulerBindingService,
        instance: str | None,
        session_key: str | None = None,
        creation_lock: threading.RLock | None = None,
        execution_bridge: ExecutionBridge | None = None,
        transform_adapters: tuple[ArtifactTransformAdapter, ...] = (),
        approval_base_url: str | None = None,
    ) -> None:
        self.artifacts = artifacts
        self.intake = intake
        self.tasks = tasks
        self.approvals = approvals
        self.executions = executions
        self.bindings = bindings
        self.instance = instance
        self.session_key = session_key
        self.execution_bridge = execution_bridge
        self.transform_adapters = transform_adapters
        self.approval_base_url = approval_base_url
        self._create_lock = creation_lock or threading.RLock()

    def instance_prepare(
        self, *, name: str, title: str, objective: str
    ) -> dict[str, Any]:
        if self.session_key is None:
            raise RootToolError(
                "instance proposals require a transport-bound scheduler session"
            )
        with self._create_lock:
            proposal = self.bindings.prepare_instance_proposal(
                name=name,
                title=title,
                objective=objective,
                session_key=self.session_key,
            )
            if not self.approvals.has_request(proposal.approval_id):
                payload = canonical_json(
                    {
                        "schema_version": 1,
                        "name": proposal.name,
                        "title": proposal.title,
                        "objective": proposal.objective,
                        "authorization_effect": (
                            "用户确认后，控制面创建该 ResearchInstance，"
                            "并绑定发起草案的调度会话。"
                        ),
                        "non_effects": [
                            "不批准任何科学结论",
                            "不授权任何仿真执行",
                            "不修改其他 ResearchInstance",
                        ],
                    }
                )
                proposal_ref = self.artifacts.register(
                    payload,
                    ArtifactRegistration(
                        artifact_id=f"art_{proposal.proposal_id}",
                        kind="research_instance_proposal",
                        schema_id="scidiscovery.research-instance-proposal.v1",
                        payload_schema_version=1,
                        media_type="application/json",
                        creator=self.intake.creator,
                        labels={"semantic_name": proposal.name},
                        confidentiality="approval_only",
                    ),
                    idempotency_key=f"instance-proposal:{proposal.proposal_id}",
                ).ref
                self.approvals.create_request(
                    approval_id=proposal.approval_id,
                    kind="research_instance_registration",
                    subject_refs=(proposal_ref,),
                    question=(
                        f"是否创建研究实例“{proposal.title}”"
                        f"（{proposal.name}）？"
                    ),
                    options=(
                        ApprovalOption(
                            option_id="create_instance",
                            label="创建并进入该实例",
                            description=(
                                "按页面展示的名称、标题和目标创建独立研究实例。"
                            ),
                            requires_rationale=False,
                        ),
                        ApprovalOption(
                            option_id="revise_instance",
                            label="要求修改草案",
                            description="不创建实例，并说明需要修改的名称、目标或范围。",
                            requires_rationale=True,
                        ),
                        ApprovalOption(
                            option_id="cancel_instance",
                            label="取消创建",
                            description="关闭本次草案，不创建研究实例。",
                            requires_rationale=False,
                            terminal_state="cancelled_by_human",
                        ),
                    ),
                    requested_by=self.intake.creator,
                    idempotency_key=f"instance-approval:{proposal.proposal_id}",
                )
        return self.instance_status(name=name)

    def instance_status(self, *, name: str) -> dict[str, Any]:
        proposal = self.bindings.get_instance_proposal(name=name)
        approval = self.approvals.status(proposal.approval_id)
        if approval.decision_ref is not None and proposal.state == "pending":
            decision = HumanDecision.model_validate_json(
                self.approvals.artifacts.read(approval.decision_ref), strict=True
            )
            proposal = self.bindings.apply_instance_proposal_decision(
                approval_id=proposal.approval_id,
                selected_option=decision.selected_option,
            )
            if proposal is None:
                raise RootToolError("instance proposal ownership disappeared")
        result = {
            "name": proposal.name,
            "title": proposal.title,
            "objective": proposal.objective,
            "proposal_status": proposal.state,
            "selected_option": proposal.selected_option,
            "created_at": proposal.created_at,
            "resolved_at": proposal.resolved_at,
        }
        if proposal.state == "activated" and proposal.instance_id is not None:
            instance = self.bindings.get_instance(instance_id=proposal.instance_id)
            result["instance_state"] = instance.state
            if instance.state == "active" and (
                self.session_key is None or self.session_key == proposal.session_key
            ):
                self.instance = instance.instance_id
                self._persist_instance_selection()
        if approval.status == "pending" and self.approval_base_url is not None:
            result["review_url"] = self.approval_base_url.rstrip("/") + "/"
        return result

    def instance_select(self, *, name: str) -> dict[str, Any]:
        value = self.bindings.select_instance(name=name)
        if self.session_key is None:
            self.instance = value.instance_id
            return self._instance_value(value)
        current = self.bindings.session_instance(session_key=self.session_key)
        if current == value.instance_id:
            self.instance = current
            return self._instance_value(value)
        return self._prepare_session_binding_review(preferred_name=name)

    def instance_current(self) -> dict[str, Any]:
        if self.session_key is not None:
            bound = self.bindings.session_instance(session_key=self.session_key)
            if bound is None:
                try:
                    review = self._prepare_session_binding_review()
                except SchedulerInstanceNotFound as error:
                    raise RootToolError(str(error)) from error
                rebound = self.bindings.session_instance(session_key=self.session_key)
                if rebound is None:
                    self.instance = None
                    return review
                self.instance = rebound
        value = self.bindings.get_instance(instance_id=self._instance_id())
        return self._instance_value(value)

    def instance_list(self, *, state: str | None) -> dict[str, Any]:
        return {
            "instances": [
                self._instance_value(value)
                for value in self.bindings.list_instances(state=state)
            ]
        }

    def instance_close(self) -> dict[str, Any]:
        with self._create_lock:
            instance_id = self._instance_id()
            task_bindings = self.bindings.list(instance=instance_id, namespace="task")
            for binding in task_bindings:
                if self.tasks.status(binding.object_id).state in {
                    "created",
                    "dispatched",
                    "claimed",
                    "finalizing",
                }:
                    raise RootToolError("research instance has an active scientific task")
            if self.tasks.active_development_debug_tasks(
                task_ids=tuple(binding.object_id for binding in task_bindings)
            ):
                raise RootToolError(
                    "research instance has an unclosed development debug execution"
                )
            for binding in self.bindings.list(instance=instance_id, namespace="approval"):
                if self.approvals.status(binding.object_id).status == "pending":
                    raise RootToolError("research instance has a pending human review")
            if self.bindings.instance_pending_binding_approval_ids(
                instance=instance_id
            ):
                raise RootToolError(
                    "research instance is named by a pending session-binding review"
                )
            for binding in self.bindings.list(
                instance=instance_id, namespace="execution"
            ):
                if self.executions.status(binding.object_id).state not in {
                    "collected",
                    "abandoned",
                }:
                    raise RootToolError(
                        "research instance has an unfinished or uncollected execution"
                    )
            value = self.bindings.close_instance(instance_id=instance_id)
            self.instance = None
            return self._instance_value(value)

    def scientific_current(self) -> dict[str, Any]:
        instance_id = self._instance_id()
        latest: dict[str, SchedulerBinding] = {}
        for binding in self.bindings.list(instance=instance_id, namespace="artifact"):
            previous = latest.get(binding.logical_name)
            if previous is None or binding.revision > previous.revision:
                latest[binding.logical_name] = binding
        return {
            "selections": [
                {
                    "kind": item.kind,
                    "artifact_name": latest[item.logical_name].name,
                    "selected_at": item.selected_at,
                }
                for item in self.bindings.scientific_selections(instance=instance_id)
                if item.logical_name in latest
            ]
        }

    def scientific_current_select(self, *, name: str, kind: str) -> dict[str, Any]:
        artifact_id = self._resolve_task_input_artifact(name)
        binding = self._binding("artifact", name)
        latest = max(
            (
                item
                for item in self.bindings.list(
                    instance=self._instance_id(), namespace="artifact"
                )
                if item.logical_name == binding.logical_name
            ),
            key=lambda item: item.revision,
        )
        if latest.name != binding.name:
            raise RootToolError(
                "current scientific selection requires the latest semantic revision"
            )
        envelope = self.artifacts.get_by_id(artifact_id)
        if envelope.kind != kind:
            raise RootToolError(
                f"{name}: scientific object kind is {envelope.kind}, expected {kind}"
            )
        try:
            if kind == "research_objective":
                ResearchObjectiveContract.model_validate_json(
                    self.artifacts.read(envelope.ref), strict=True
                )
            else:
                ExperimentPortfolio.model_validate_json(
                    self.artifacts.read(envelope.ref), strict=True
                )
        except ValidationError as error:
            raise RootToolError(
                f"{name}: selected scientific object payload is invalid"
            ) from error
        selected = self.bindings.select_scientific_object(
            instance=self._instance_id(),
            kind=kind,
            logical_name=binding.logical_name,
        )
        return {
            "kind": selected.kind,
            "artifact_name": latest.name,
            "selected_at": selected.selected_at,
        }

    def scientific_readiness(self) -> dict[str, Any]:
        """Project scientific state from current immutable bindings only."""

        instance_id = self._instance_id()
        try:
            objective = self.bindings.get_instance(instance_id=instance_id).objective
        except SchedulerInstanceNotFound:
            objective = "The current scientific objective requires a problem frame."
        latest: dict[str, SchedulerBinding] = {}
        for binding in self.bindings.list(instance=instance_id, namespace="artifact"):
            previous = latest.get(binding.logical_name)
            if previous is None or binding.revision > previous.revision:
                latest[binding.logical_name] = binding
        selections = {
            item.kind: item.logical_name
            for item in self.bindings.scientific_selections(instance=instance_id)
        }
        selected_names = {
            kind: latest[logical_name].name
            for kind, logical_name in selections.items()
            if logical_name in latest
        }

        objects: list[ScientificObjectStatus] = []
        effective_kinds: list[str] = []
        envelopes: dict[str, Any] = {}
        blockers: list[str] = []
        provisional_foundation = False
        for binding in sorted(latest.values(), key=lambda item: item.logical_name):
            envelope = self.artifacts.get_by_id(binding.object_id)
            if envelope.kind not in _SCIENTIFIC_ARTIFACT_KINDS:
                continue
            qualification = "qualified"
            signal = self.tasks.scheduler_signal_for_output(envelope.ref)
            if envelope.labels.get("scientific_claim_admissible") == "false":
                qualification = "blocked"
                blockers.append(
                    f"{binding.name}: artifact is provisional or development-only "
                    "and cannot support a scientific claim"
                )
            elif self._failed_runtime_attestation(envelope):
                qualification = "revision_required"
                blockers.append(
                    f"{binding.name}: runtime attestation failed; only bounded "
                    "implementation revision or diagnosis is admissible"
                )
            elif (
                signal is not None
                and signal.verdict in _NONQUALIFYING_HANDOFF_VERDICTS
            ):
                qualification = (
                    "blocked"
                    if signal.verdict == "blocked"
                    else "revision_required"
                )
                blockers.append(
                    f"{binding.name}: producing task reported {signal.verdict}: "
                    f"{signal.summary}"
                )
            elif (
                envelope.kind == "scientific_foundation"
                and not self.approvals.is_subject_approved(
                    envelope.ref,
                    kind="scientific_foundation",
                    accepted_options=("approve", "approve_with_exception"),
                )
            ):
                qualification = "human_review_required"
                provisional_foundation = True
                blockers.append(
                    f"{binding.name}: final scientific foundation review is pending; "
                    "evidence audit remains allowed"
                )
            objects.append(
                ScientificObjectStatus(
                    semantic_name=binding.name,
                    kind=envelope.kind,
                    schema_id=envelope.schema_id,
                    revision=binding.revision,
                    qualification=qualification,
                )
            )
            envelopes[binding.name] = envelope
            if qualification == "qualified" and envelope.kind not in effective_kinds:
                effective_kinds.append(envelope.kind)

        qualified_portfolios = tuple(
            envelopes[item.semantic_name]
            for item in objects
            if item.kind == "experiment_portfolio"
            and item.qualification == "qualified"
            and (
                "experiment_portfolio" not in selected_names
                or item.semantic_name == selected_names["experiment_portfolio"]
            )
        )
        parsed_portfolios: list[ExperimentPortfolio] = []
        for envelope in qualified_portfolios:
            try:
                parsed_portfolios.append(
                    ExperimentPortfolio.model_validate_json(
                        self.artifacts.read(envelope.ref), strict=True
                    )
                )
            except ValidationError:
                blockers.append("a qualified experiment portfolio payload is invalid")
        valid_metric_report = False
        for index, item in enumerate(objects):
            if item.kind != "metric_report" or item.qualification != "qualified":
                continue
            envelope = envelopes[item.semantic_name]
            try:
                metric_report = CurveConsistencyReport.model_validate_json(
                    self.artifacts.read(envelope.ref), strict=True
                )
                if not _metric_report_has_complete_plan_coverage(
                    metric_report, tuple(parsed_portfolios)
                ):
                    raise ValueError("metric report has no exact complete-plan coverage")
            except (ValidationError, ValueError):
                objects[index] = item.model_copy(
                    update={"qualification": "revision_required"}
                )
                blockers.append(
                    f"{item.semantic_name}: metric report is standalone, partial, "
                    "or does not match a current validation plan"
                )
            else:
                valid_metric_report = True
        if "metric_report" in effective_kinds and not valid_metric_report:
            effective_kinds.remove("metric_report")

        objective_values: list[ResearchObjectiveContract] = []
        coverage_values: list[ObjectiveCoverageReport] = []
        explicit_foundation_contract = False
        valid_objective_names: set[str] = set()
        valid_coverage_names: set[str] = set()
        for index, item in enumerate(objects):
            if item.qualification != "qualified":
                continue
            envelope = envelopes[item.semantic_name]
            try:
                if (
                    item.kind == "scientific_foundation"
                    and envelope.schema_id
                    == "scidiscovery.scientific-foundation.v1"
                ):
                    foundation = ScientificFoundation.model_validate_json(
                        self.artifacts.read(envelope.ref), strict=True
                    )
                    explicit_foundation_contract = (
                        explicit_foundation_contract
                        or foundation.objective_contract is not None
                    )
                elif item.kind == "research_objective":
                    if (
                        "research_objective" in selected_names
                        and item.semantic_name
                        != selected_names["research_objective"]
                    ):
                        continue
                    objective_values.append(
                        ResearchObjectiveContract.model_validate_json(
                            self.artifacts.read(envelope.ref), strict=True
                        )
                    )
                    valid_objective_names.add(item.semantic_name)
                elif item.kind == "objective_coverage":
                    coverage_values.append(
                        ObjectiveCoverageReport.model_validate_json(
                            self.artifacts.read(envelope.ref), strict=True
                        )
                    )
                    valid_coverage_names.add(item.semantic_name)
            except ValidationError:
                objects[index] = item.model_copy(
                    update={"qualification": "revision_required"}
                )
                blockers.append(
                    f"{item.semantic_name}: invalid {item.kind} payload"
                )
        if "research_objective" in effective_kinds and not valid_objective_names:
            effective_kinds.remove("research_objective")
        if "objective_coverage" in effective_kinds and not valid_coverage_names:
            effective_kinds.remove("objective_coverage")

        objective_projection = project_objective_readiness(
            tuple(objective_values),
            tuple(parsed_portfolios),
            tuple(coverage_values),
        )
        objective_status = objective_projection.status
        mandatory_target_gaps = list(objective_projection.mandatory_target_gaps)
        if explicit_foundation_contract and not objective_values:
            objective_status = "blocked"
            mandatory_target_gaps.append("research_objective:projection_missing")
        if objective_status == "blocked":
            blockers.append(
                "mandatory scientific objective is unresolved: "
                + ", ".join(dict.fromkeys(mandatory_target_gaps))
            )

        contradiction = objective
        frames = [
            (item, envelopes[item.semantic_name])
            for item in objects
            if item.kind == "problem_frame" and item.qualification == "qualified"
        ]
        if frames:
            try:
                frame = ProblemFrame.model_validate_json(
                    self.artifacts.read(frames[-1][1].ref), strict=True
                )
                contradiction = frame.current_contradiction
            except ValidationError:
                blockers.append(
                    f"{frames[-1][0].semantic_name}: invalid problem frame payload"
                )

        unresolved: list[str] = []
        if "problem_frame" not in effective_kinds:
            unresolved.append("problem_frame")
        if "scientific_foundation" not in effective_kinds:
            unresolved.append("approved_scientific_foundation")

        execution_states = tuple(
            self.executions.status(binding.object_id).state
            for binding in self.bindings.list(
                instance=instance_id, namespace="execution"
            )
        )
        if "execution_result" in effective_kinds:
            execution_readiness = "completed"
        elif any(
            state in {"authorized", "submitted", "running", "cancelling", "succeeded"}
            for state in execution_states
        ):
            execution_readiness = "authorized"
        elif "packaged_project" in effective_kinds:
            execution_readiness = "ready"
        else:
            execution_readiness = "not_ready"

        claim_evaluability = "evaluable" if "execution_result" in effective_kinds else "not_evaluable"
        reports = [
            envelopes[item.semantic_name]
            for item in objects
            if item.kind in {"validation_report", "layered_diagnosis"}
            and item.qualification == "qualified"
        ]
        if len(reports) > 1:
            claim_evaluability = "not_evaluable"
            blockers.append(
                "multiple current claim reports are bound; create one semantic revision"
            )
        elif reports:
            envelope = reports[0]
            try:
                report = (
                    LayeredDiagnosisReport.model_validate_json(
                        self.artifacts.read(envelope.ref), strict=True
                    )
                    if envelope.kind == "layered_diagnosis"
                    else ValidationReport.model_validate_json(
                        self.artifacts.read(envelope.ref), strict=True
                    )
                )
                decision = project_claim_decision(report)
                objective_claim_allowed = True
                if objective_values:
                    assessment = (
                        report.objective_assessment
                        if isinstance(report, LayeredDiagnosisReport)
                        else None
                    )
                    exact_objective = (
                        len(objective_values) == 1
                        and assessment is not None
                        and assessment.objective_key
                        == objective_values[0].objective_key
                        and assessment.status == "pass"
                    )
                    objective_claim_allowed = (
                        exact_objective
                        and objective_status == "evaluable"
                        and "objective_coverage" in effective_kinds
                    )
                    if decision.claim_allowed and not objective_claim_allowed:
                        blockers.append(
                            "passing global diagnosis does not satisfy the exact "
                            "approved objective and its coverage gate"
                        )
                    elif decision.claim_allowed:
                        objective_status = "satisfied"
                claim_evaluability = (
                    "accepted"
                    if decision.claim_allowed and objective_claim_allowed
                    else "evaluable"
                )
            except ValidationError:
                blockers.append("current claim report payload is invalid")

        base = ScientificReadiness(
            current_contradiction=contradiction,
            available_artifacts=tuple(effective_kinds),
            unresolved_needs=tuple(dict.fromkeys(unresolved)),
            blockers=tuple(dict.fromkeys(blockers)),
            claim_evaluability=claim_evaluability,
            execution_readiness=execution_readiness,
            objective_status=objective_status,
            mandatory_target_gaps=tuple(dict.fromkeys(mandatory_target_gaps)),
            rationale=(
                "Derived from the latest semantic revisions in this research "
                "instance; capabilities express data readiness, not workflow order."
            ),
        )
        materialized_projects = _qualified_materialized_project_refs(
            objects=objects,
            envelopes=envelopes,
            artifacts=self.artifacts,
        )
        package_inputs_ready = _qualified_tcad_review_pair_exists(
            objects=objects,
            envelopes=envelopes,
            artifacts=self.artifacts,
            project_refs=materialized_projects,
            portfolio_names=frozenset(
                item.semantic_name
                for item in objects
                if item.kind == "experiment_portfolio"
                and item.qualification == "qualified"
                and (
                    "experiment_portfolio" not in selected_names
                    or item.semantic_name
                    == selected_names["experiment_portfolio"]
                )
            ),
        )
        actions_list = []
        for item in ready_capabilities(base):
            if item.transform_profile is not None and not any(
                adapter.supports_transform_profile(item.transform_profile)
                for adapter in self.transform_adapters
            ):
                continue
            if item.name == "tcad_deck_reviewer" and not materialized_projects:
                blockers.append(
                    "deck review requires a passing deterministic project "
                    "materialization and source-bound preflight"
                )
                continue
            if item.name == "package_deck_project" and not package_inputs_ready:
                blockers.append(
                    "deck packaging requires an exact passing review of the current "
                    "materialized and preflight-qualified project"
                )
                continue
            actions_list.append(item.name)
        if provisional_foundation and "evidence_auditor" not in actions_list:
            insert_at = (
                actions_list.index("split_scientific_intake") + 1
                if "split_scientific_intake" in actions_list
                else len(actions_list)
            )
            actions_list.insert(insert_at, "evidence_auditor")
        actions = tuple(actions_list)
        readiness = ScientificReadiness(
            **base.model_dump(
                mode="python", exclude={"suggested_capabilities", "blockers"}
            ),
            blockers=tuple(dict.fromkeys(blockers)),
            suggested_capabilities=actions,
        )
        return ScientificClosureStatus(
            readiness=readiness,
            objects=tuple(objects),
            available_actions=actions,
        ).model_dump(mode="json")

    def lifecycle_events(self) -> dict[str, Any]:
        """Read changed lifecycle states through a durable service-owned cursor."""

        instance_id = self._instance_id()
        states: list[tuple[str, str, str]] = []
        for binding in self.bindings.list(instance=instance_id, namespace="task"):
            states.append(("task", binding.name, self.tasks.status(binding.object_id).state))
        for binding in self.bindings.list(instance=instance_id, namespace="approval"):
            states.append(
                ("approval", binding.name, self.approvals.status(binding.object_id).status)
            )
        for binding in self.bindings.list(instance=instance_id, namespace="execution"):
            states.append(
                ("execution", binding.name, self.executions.status(binding.object_id).state)
            )
        if len(states) > 1024:
            raise RootToolError("scheduler lifecycle inventory exceeds its bounded view")
        observer = self.session_key or f"facade:{instance_id}"
        changes = self.bindings.observe_state_changes(
            instance=instance_id,
            observer_key=observer,
            states=tuple(states),
        )
        return {
            "events": [
                {
                    "object_type": item.object_type,
                    "name": item.name,
                    "previous_state": item.previous_state,
                    "state": item.state,
                    "observed_at": item.observed_at,
                }
                for item in changes
            ]
        }

    def artifact_ingest_file(
        self,
        *,
        name: str,
        relative_path: str,
        media_type: str | None,
        on_conflict: str,
    ) -> dict[str, Any]:
        prepared = self.intake.prepare_file(
            relative_path=relative_path, media_type=media_type
        )
        fingerprint = canonical_sha256(
            {
                "operation": "artifact_ingest_file",
                "relative_path": prepared.relative_path,
                "media_type": prepared.media_type,
                "payload_sha256": hashlib.sha256(prepared.content).hexdigest(),
            }
        )
        with self._create_lock:
            target = self._creation_target(
                "artifact", name, fingerprint, on_conflict
            )
            if target.existing_object_id is None:
                reference = self.intake.ingest_prepared(prepared)
                binding = self._bind_target(
                    "artifact", target, reference.artifact_id, fingerprint
                )
            else:
                binding = self._binding("artifact", target.name)
        return {**self._binding_value(binding), "state": "bound"}

    def artifact_catalog(self, *, name: str) -> dict[str, Any]:
        binding = self._binding("artifact", name)
        envelope = self.artifacts.get_by_id(binding.object_id)
        labels = {
            key: value
            for key, value in envelope.labels.items()
            if not _identity_word(key)
        }
        return {
            **self._binding_value(binding),
            "kind": envelope.kind,
            "schema": envelope.schema_id,
            "payload_schema_version": envelope.payload_schema_version,
            "media_type": envelope.media_type,
            "size_bytes": envelope.size_bytes,
            "created_at": envelope.created_at,
            "labels": labels,
        }

    def artifact_transform(
        self,
        *,
        name: str,
        profile: str,
        inputs: tuple[TransformInputSelection, ...],
        on_conflict: str,
    ) -> dict[str, Any]:
        source_names = tuple(item.source_name for item in inputs)
        artifact_names = tuple(item.artifact_name for item in inputs)
        if len(source_names) != len(set(source_names)):
            raise RootToolError("transform source names must be unique")
        if len(artifact_names) != len(set(artifact_names)):
            raise RootToolError("transform artifacts must be unique")
        try:
            adapter = select_transform_adapter(profile, self.transform_adapters)
        except ValueError as error:
            raise RootToolError(str(error)) from error

        nonqualifying_selector = getattr(
            adapter, "nonqualifying_input_names", None
        )
        allowed_nonqualifying = (
            frozenset(nonqualifying_selector(profile, source_names))
            if nonqualifying_selector is not None
            else frozenset()
        )
        if not allowed_nonqualifying.issubset(source_names):
            raise RootToolError(
                "deterministic transform selected invalid nonqualifying inputs"
            )

        envelopes = tuple(
            self.artifacts.get_by_id(
                self._resolve_task_input_artifact(
                    item.artifact_name,
                    allow_nonqualifying=(
                        item.source_name
                        in _REVISION_TRANSFORM_INPUTS.get(profile, frozenset())
                        or item.source_name in allowed_nonqualifying
                    ),
                )
            )
            for item in inputs
        )
        derived_from_nonqualifying = any(
            item.source_name in allowed_nonqualifying
            and (
                envelope.labels.get("scientific_claim_admissible") == "false"
                or self._failed_runtime_attestation(envelope)
                or (
                    (signal := self.tasks.scheduler_signal_for_output(envelope.ref))
                    is not None
                    and signal.verdict in _NONQUALIFYING_HANDOFF_VERDICTS
                )
            )
            for item, envelope in zip(inputs, envelopes, strict=True)
        )
        by_source = {
            item.source_name: envelope
            for item, envelope in zip(inputs, envelopes, strict=True)
        }
        input_names = tuple(item.source_name for item in inputs)
        dynamic_parentage = getattr(
            adapter, "required_input_parentage_for_inputs", None
        )
        parentage = getattr(adapter, "required_input_parentage", None)
        parentage_pairs = (
            dynamic_parentage(profile, input_names)
            if dynamic_parentage is not None
            else parentage(profile)
            if parentage is not None
            else ()
        )
        for child_name, parent_name in parentage_pairs:
            if child_name not in by_source or parent_name not in by_source:
                raise RootToolError(
                    "deterministic transform parentage names are absent"
                )
            if by_source[parent_name].ref not in by_source[child_name].parent_refs:
                raise RootToolError(
                    f"{child_name} was not produced from the exact {parent_name}"
                )
        payload_selector = getattr(adapter, "payload_input_names", None)
        selected_payload_names = (
            tuple(payload_selector(profile, input_names))
            if payload_selector is not None
            else input_names
        )
        if len(selected_payload_names) != len(set(selected_payload_names)) or not set(
            selected_payload_names
        ).issubset(input_names):
            raise RootToolError(
                "deterministic transform selected invalid payload input names"
            )
        selected = set(selected_payload_names)
        payloads = {
            item.source_name: (
                self.artifacts.read(envelope.ref)
                if item.source_name in selected
                else b""
            )
            for item, envelope in zip(inputs, envelopes, strict=True)
        }
        try:
            outputs = adapter.transform(profile=profile, inputs=payloads)
        except Exception as error:
            raise RootToolError(f"deterministic transform failed: {error}") from error
        labels = tuple(output.label for output in outputs)
        if not outputs or "primary" not in labels or len(labels) != len(set(labels)):
            raise RootToolError(
                "deterministic transform must return unique outputs including primary"
            )

        fingerprint = canonical_sha256(
            {
                "operation": "artifact_transform",
                "profile": profile,
                "inputs": [
                    {"source_name": item.source_name, "artifact_ref": envelope.ref}
                    for item, envelope in zip(inputs, envelopes, strict=True)
                ],
            }
        )
        parent_refs = tuple(envelope.ref for envelope in envelopes)
        with self._create_lock:
            target = self._creation_target("artifact", name, fingerprint, on_conflict)
            registered = []
            for output in outputs:
                output_name = (
                    target.name
                    if output.label == "primary"
                    else _derived_name(target.name, output.label)
                )
                existing_id = self._optional("artifact", output_name)
                if existing_id is None:
                    envelope = self.artifacts.register(
                        output.content,
                        ArtifactRegistration(
                            kind=output.kind,
                            schema_id=output.schema,
                            payload_schema_version=output.payload_schema_version,
                            media_type=output.media_type,
                            creator=self.intake.creator,
                            parent_refs=parent_refs,
                            labels={
                                "transform_profile": profile,
                                "output_label": output.label,
                                **(
                                    {"scientific_claim_admissible": "false"}
                                    if derived_from_nonqualifying
                                    else {}
                                ),
                            },
                        ),
                        idempotency_key=(
                            "artifact-transform:"
                            + canonical_sha256(
                                {
                                    "instance": self._instance_id(),
                                    "name": output_name,
                                    "fingerprint": fingerprint,
                                    "label": output.label,
                                }
                            )
                        ),
                    )
                    if output.label == "primary":
                        binding = self._bind_target(
                            "artifact", target, envelope.artifact_id, fingerprint
                        )
                    else:
                        binding = self._bind(
                            "artifact",
                            output_name,
                            envelope.artifact_id,
                            request_fingerprint=fingerprint,
                        )
                else:
                    envelope = self.artifacts.get_by_id(existing_id)
                    if self.artifacts.read(envelope.ref) != output.content:
                        raise RootToolError(
                            "existing transform output differs from deterministic result"
                        )
                    binding = self._binding("artifact", output_name)
                registered.append(
                    {
                        "output_label": output.label,
                        "artifact_name": binding.name,
                        "kind": envelope.kind,
                        "schema": envelope.schema_id,
                        "media_type": envelope.media_type,
                        "size_bytes": envelope.size_bytes,
                    }
                )
        return {"name": target.name, "profile": profile, "outputs": registered}

    def task_schedule(self, **values: Any) -> dict[str, Any]:
        name = values.pop("name")
        on_conflict = values.pop("on_conflict")
        role = values["role"]
        with self._create_lock:
            input_selections = values.pop("inputs")
            dependency_names = values.pop("dependency_names")
            source_names = tuple(item.source_name for item in input_selections)
            artifact_names = tuple(item.artifact_name for item in input_selections)
            if len(source_names) != len(set(source_names)):
                raise RootToolError("task-local source names must be unique")
            if len(artifact_names) != len(set(artifact_names)):
                raise RootToolError("task artifacts must be unique")
            if len(dependency_names) != len(set(dependency_names)):
                raise RootToolError("task dependency names must be unique")
            resolved_inputs = []
            resolved_by_source = {}
            for item in input_selections:
                envelope = self.artifacts.get_by_id(
                    self._resolve_task_input_artifact(
                        item.artifact_name,
                        allow_nonqualifying=self.tasks.admits_nonqualifying_input(
                            role=role,
                            context_profile=values["context_profile"],
                            source_name=item.source_name,
                            exposure=item.exposure,
                            usage=item.usage,
                        ),
                    )
                )
                if (
                    envelope.kind == "scientific_foundation"
                    and role != "evidence_auditor"
                    and item.usage != "revision_base"
                    and not self.approvals.is_subject_approved(
                        envelope.ref,
                        kind="scientific_foundation",
                        accepted_options=("approve", "approve_with_exception"),
                    )
                ):
                    raise RootToolError(
                        "scientific foundation requires an exact approved human review"
                    )
                resolved_inputs.append(
                    TaskInput(
                        name=item.source_name,
                        artifact_ref=envelope.ref,
                        exposure=item.exposure,
                        usage=item.usage,
                    )
                )
                resolved_by_source[item.source_name] = envelope
            inputs = tuple(resolved_inputs)
            self._require_approved_device_parameter_inputs(
                role=role,
                resolved_by_source=resolved_by_source,
            )
            dependencies = tuple(
                self._resolve("task", dependency_name)
                for dependency_name in dependency_names
            )
            output_profile = values.pop("output_profile")
            revision_base_source = values.pop("revision_base_source")
            allowed_revision_paths = values.pop("allowed_revision_paths")
            try:
                contract, output_collections = self.tasks.resolve_output_profile(
                    values["role"], output_profile
                )
            except ValueError as error:
                raise RootToolError(str(error)) from error
            if output_profile == "device-parameter-evidence":
                requirement_input = resolved_by_source.get("parameter_requirements")
                if (
                    values["role"] != "evidence_extractor"
                    or values["context_profile"]
                    != "scidiscovery.evidence-intake.device-parameters.v1"
                    or (
                        requirement_input is not None
                        and requirement_input.schema_id
                        != "scidiscovery.device-parameter-requirements.v1"
                    )
                ):
                    raise RootToolError(
                        "device parameter evidence extraction requires the exact "
                        "device-parameter intake context; an optional supplied "
                        "parameter_requirements input must use the exact schema"
                    )
            revision = None
            if output_profile == "structured-revision":
                if revision_base_source is None or not allowed_revision_paths:
                    raise RootToolError(
                        "structured revision requires a base source and allowed paths"
                    )
                try:
                    base_input = next(
                        item for item in inputs if item.name == revision_base_source
                    )
                    base_envelope = resolved_by_source[revision_base_source]
                except (KeyError, StopIteration) as error:
                    raise RootToolError(
                        "structured revision base source is not a task input"
                    ) from error
                if base_input.usage != "revision_base":
                    raise RootToolError(
                        "structured revision base must use revision_base usage"
                    )
                if base_envelope.schema_id not in _REVISION_TARGETS_BY_ROLE.get(
                    values["role"], frozenset()
                ):
                    raise RootToolError(
                        "structured revision target is not admitted for this role"
                    )
                try:
                    revision = TaskRevisionSpec(
                        base_source_name=revision_base_source,
                        target_schema=base_envelope.schema_id,
                        allowed_paths=allowed_revision_paths,
                    )
                except ValidationError as error:
                    raise RootToolError(str(error)) from error
            elif revision_base_source is not None or allowed_revision_paths:
                raise RootToolError(
                    "revision scope is only valid for structured-revision output"
                )
            output = TaskOutputSpec(
                format=contract.format,
                kind=contract.kind,
                schema_id=contract.schema_id,
                validator=contract.validator,
                context_validator=contract.context_validator,
                context_sources=contract.context_sources,
                media_type=(
                    "application/json"
                    if contract.format == "json"
                    else "text/markdown; charset=utf-8"
                ),
                max_bytes=values.pop("max_output_bytes"),
                collections=output_collections,
                revision=revision,
            )
            budget = TaskBudget(
                timeout_seconds=values.pop("timeout_seconds"),
                max_attempts=values.pop("max_attempts"),
            )
            values["context_profile"] = self.tasks.resolve_context_profile(
                values["role"], values["context_profile"]
            )
            fingerprint = canonical_sha256(
                {
                    "operation": "task_schedule",
                    "role": values["role"],
                    "instruction": values["instruction"],
                    "inputs": inputs,
                    "dependency_task_ids": dependencies,
                    "output": output,
                    "output_profile": output_profile,
                    "budget": budget,
                }
            )
            target = self._creation_target(
                "task", name, fingerprint, on_conflict
            )
            if target.existing_object_id is not None:
                return self.task_status(name=target.name)
            task_id = self.tasks.schedule(
                inputs=inputs,
                dependency_task_ids=dependencies,
                output=output,
                budget=budget,
                **values,
            )
            self._bind_target("task", target, task_id, fingerprint)
        return self.task_status(name=target.name)

    def _require_approved_device_parameter_inputs(
        self,
        *,
        role: str,
        resolved_by_source: dict[str, Any],
    ) -> None:
        if role in {"evidence_extractor", "evidence_auditor"}:
            return
        envelopes = tuple(resolved_by_source.values())
        trigger_schemas = {
            "scidiscovery.device-parameter-set.v1",
            "scidiscovery.evidence-source-catalog.v1",
            "scidiscovery.device-parameter-coverage.v1",
        }
        if not any(item.schema_id in trigger_schemas for item in envelopes):
            return

        def one(schema_id: str) -> Any:
            matches = tuple(item for item in envelopes if item.schema_id == schema_id)
            if len(matches) != 1:
                raise RootToolError(
                    "downstream device parameter context requires exactly one "
                    + schema_id
                )
            return matches[0]

        foundation = one("scidiscovery.scientific-foundation.v1")
        requirements = one("scidiscovery.device-parameter-requirements.v1")
        parameters = one("scidiscovery.device-parameter-set.v1")
        catalog = one("scidiscovery.evidence-source-catalog.v1")
        coverage = one("scidiscovery.device-parameter-coverage.v1")
        audited_refs = {
            foundation.ref,
            requirements.ref,
            parameters.ref,
            catalog.ref,
            coverage.ref,
        }
        matching_audits = tuple(
            item
            for item in envelopes
            if item.schema_id == "scidiscovery.evidence-audit.v1"
            and audited_refs.issubset(set(item.parent_refs))
        )
        if len(matching_audits) != 1:
            raise RootToolError(
                "downstream device parameter context requires its exact independent audit"
            )
        approved_refs = (
            foundation.ref,
            requirements.ref,
            parameters.ref,
            catalog.ref,
            coverage.ref,
            matching_audits[0].ref,
        )
        if not self.approvals.are_subjects_approved(
            approved_refs,
            kind="scientific_foundation",
            accepted_options=("approve", "approve_with_exception"),
        ):
            raise RootToolError(
                "downstream device parameter inputs were not approved together "
                "in one exact human review"
            )

    def task_ready(self) -> dict[str, Any]:
        names = []
        for task_id in self.tasks.ready():
            name = self.bindings.find_name(
                instance=self._instance_id(), namespace="task", object_id=task_id
            )
            if name is not None:
                names.append(name)
        return {"task_names": names}

    def task_list(self, *, state: str | None, limit: int) -> dict[str, Any]:
        items = []
        for binding in self.bindings.list(instance=self._instance_id(), namespace="task"):
            value = self.tasks.status(binding.object_id)
            if state is not None and value.state != state:
                continue
            items.append(self._task_status_value(binding.name, value))
            if len(items) >= limit:
                break
        return {"tasks": items}

    def task_status(self, *, name: str) -> dict[str, Any]:
        value = self.tasks.status(self._resolve("task", name))
        return self._task_status_value(name, value)

    def task_evidence_sources(self, *, name: str) -> dict[str, Any]:
        task_id = self._resolve("task", name)
        sources = []
        for value in self.tasks.list_web_evidence(task_id):
            artifact_name = _derived_name(name, "web", value.source_key)
            self._bind("artifact", artifact_name, value.snapshot_ref.artifact_id)
            sources.append(
                {
                    "source_label": value.source_key,
                    "artifact_name": artifact_name,
                    "original_url": value.original_url,
                    "final_url": value.final_url,
                    "accessed_at": value.accessed_at,
                    "media_type": value.media_type,
                    "text_truncated": value.text_truncated,
                }
            )
        for value in self.tasks.list_pdf_excerpts(task_id):
            source_label = (
                f"pdf_excerpt_{value.source_name}_p{value.first_page}_{value.last_page}_"
                f"m{value.max_chars}"
            )
            artifact_name = _derived_name(name, source_label)
            self._bind("artifact", artifact_name, value.excerpt_ref.artifact_id)
            sources.append(
                {
                    "source_label": source_label,
                    "artifact_name": artifact_name,
                    "source_type": "pdf_excerpt_set",
                    "input_source_name": value.source_name,
                    "first_page": value.first_page,
                    "last_page": value.last_page,
                    "max_chars": value.max_chars,
                    "truncated": value.truncated,
                    "media_type": "application/json",
                }
            )
        return {"task_name": name, "sources": sources}

    def task_outputs(self, *, name: str) -> dict[str, Any]:
        task_id = self._resolve("task", name)
        outputs = []
        for value in self.tasks.list_output_artifacts(task_id):
            artifact_name = _derived_name(
                name, "output", value.collection, value.item
            )
            self._bind("artifact", artifact_name, value.artifact_ref.artifact_id)
            outputs.append(
                {
                    "collection": value.collection,
                    "item": value.item,
                    "artifact_name": artifact_name,
                    "media_type": value.media_type,
                    "size_bytes": value.size_bytes,
                }
            )
        return {"task_name": name, "outputs": outputs}

    def _task_status_value(self, name: str, value: Any) -> dict[str, Any]:
        binding = self._binding("task", name)
        output_name = _derived_name(name, "output")
        if value.output_ref is not None:
            self._bind("artifact", output_name, value.output_ref.artifact_id)
        blocking_names = []
        for task_id in value.blocking_task_ids:
            dependency = self.bindings.find_name(
                instance=self._instance_id(), namespace="task", object_id=task_id
            )
            blocking_names.append(dependency or "unbound_dependency")
        return {
            **self._binding_value(binding),
            "role": value.role,
            "state": value.state,
            "attempt": value.attempt,
            "output_artifact_name": output_name if value.output_ref is not None else None,
            "scheduler_signal": (
                value.scheduler_signal.model_dump(mode="json")
                if value.scheduler_signal is not None
                else None
            ),
            "reason": value.reason,
            "readiness": value.readiness,
            "blocking_names": blocking_names,
            "created_at": value.created_at,
            "lease_deadline_at": value.lease_deadline_at,
            "absolute_deadline_at": value.absolute_deadline_at,
            "finalization_deadline_at": value.finalization_deadline_at,
            "last_activity_at": value.last_activity_at,
            "last_activity": value.last_activity,
            "performance": self.tasks.performance(binding.object_id),
        }

    def task_prepare_dispatch(self, *, name: str, ttl_seconds: int) -> dict[str, Any]:
        ticket = self.tasks.prepare_dispatch(
            self._resolve("task", name), ttl_seconds=ttl_seconds
        )
        return {"task_name": name, "agent_type": ticket.role}

    def task_record_failure(
        self,
        *,
        name: str,
        reason: str,
        timed_out: bool,
        expected_state: str,
        expected_last_activity_at: str | None,
    ) -> dict[str, Any]:
        self.tasks.fail(
            self._resolve("task", name),
            reason=reason,
            timed_out=timed_out,
            expected_state=expected_state,
            expected_last_activity_at=expected_last_activity_at,
        )
        return self.task_status(name=name)

    def task_retry(self, *, name: str) -> dict[str, Any]:
        self.tasks.retry(self._resolve("task", name))
        return self.task_status(name=name)

    def approval_request_create(self, **values: Any) -> dict[str, Any]:
        name = values.pop("name")
        on_conflict = values.pop("on_conflict")
        with self._create_lock:
            subject_names = tuple(values.pop("subject_names"))
            subjects = tuple(
                self.artifacts.get_by_id(
                    self._resolve_task_input_artifact(subject)
                ).ref
                for subject in subject_names
            )
            options = tuple(
                ApprovalOption(
                    option_id=item.option_key,
                    label=item.label,
                    description=item.description,
                    requires_rationale=item.requires_rationale,
                    terminal_state=item.terminal_state,
                )
                for item in values.pop("options")
            )
            self._validate_device_parameter_approval(
                kind=values["kind"],
                subjects=subjects,
                options=options,
            )
            presentation_input = values.pop("presentation")
            presentation = None
            if presentation_input is not None:
                subject_indexes = {
                    subject_name: index
                    for index, subject_name in enumerate(subject_names)
                }
                try:
                    translations = tuple(
                        ApprovalDisplayTranslation(
                            subject_index=subject_indexes[item.subject_name],
                            json_pointer=item.json_pointer,
                            text=item.text,
                        )
                        for item in presentation_input.translations
                    )
                except KeyError as error:
                    raise ValueError(
                        "display translation subject_name is not an approval subject"
                    ) from error
                presentation = ApprovalPresentation(
                    locale=presentation_input.locale,
                    translations=translations,
                )
            fingerprint = canonical_sha256(
                {
                    "operation": "approval_request_create",
                    "kind": values["kind"],
                    "subject_refs": subjects,
                    "question": values["question"],
                    "options": options,
                    "expires_at": values["expires_at"],
                    "presentation": presentation,
                }
            )
            target = self._creation_target(
                "approval", name, fingerprint, on_conflict
            )
            if target.existing_object_id is not None:
                return self.approval_status(name=target.name)
            approval_id = f"apr_{uuid.uuid4().hex}"
            self.approvals.create_request(
                approval_id=approval_id,
                subject_refs=subjects,
                options=options,
                requested_by=self.intake.creator,
                idempotency_key=f"approval:{approval_id}",
                presentation=presentation,
                **values,
            )
            self._bind_target("approval", target, approval_id, fingerprint)
        return self.approval_status(name=target.name)

    def _validate_device_parameter_approval(
        self,
        *,
        kind: str,
        subjects: tuple[Any, ...],
        options: tuple[ApprovalOption, ...],
    ) -> None:
        """Fail closed for the new, provenance-bearing parameter review set."""

        envelopes = tuple(self.artifacts.verify(reference) for reference in subjects)
        if not any(
            item.schema_id in _DEVICE_PARAMETER_APPROVAL_SCHEMAS
            for item in envelopes
        ):
            return
        if kind != "scientific_foundation":
            raise RootToolError(
                "device parameter subjects require scientific_foundation review"
            )

        def one(schema_id: str) -> Any:
            matches = tuple(item for item in envelopes if item.schema_id == schema_id)
            if len(matches) != 1:
                raise RootToolError(
                    "device parameter review requires exactly one subject with schema "
                    + schema_id
                )
            return matches[0]

        foundation_envelope = one("scidiscovery.scientific-foundation.v1")
        requirements_envelope = one(
            "scidiscovery.device-parameter-requirements.v1"
        )
        parameters_envelope = one("scidiscovery.device-parameter-set.v1")
        catalog_envelope = one("scidiscovery.evidence-source-catalog.v1")
        coverage_envelope = one("scidiscovery.device-parameter-coverage.v1")
        audit_envelope = one("scidiscovery.evidence-audit.v1")
        try:
            foundation = ScientificFoundation.model_validate_json(
                self.artifacts.read(foundation_envelope.ref), strict=True
            )
            requirements = DeviceParameterRequirementSet.model_validate_json(
                self.artifacts.read(requirements_envelope.ref), strict=True
            )
            parameters = DeviceParameterSet.model_validate_json(
                self.artifacts.read(parameters_envelope.ref), strict=True
            )
            catalog = EvidenceSourceCatalog.model_validate_json(
                self.artifacts.read(catalog_envelope.ref), strict=True
            )
            supplied_coverage = DeviceParameterCoverageReport.model_validate_json(
                self.artifacts.read(coverage_envelope.ref), strict=True
            )
            audit = EvidenceAudit.model_validate_json(
                self.artifacts.read(audit_envelope.ref), strict=True
            )
            recomputed = evaluate_device_parameter_coverage(
                requirements, parameters, catalog
            )
        except (ValidationError, ValueError) as error:
            raise RootToolError(
                f"device parameter approval subject is invalid: {error}"
            ) from error

        if not (
            foundation.objective == requirements.objective == parameters.objective
        ):
            raise RootToolError(
                "device parameter review subjects must share the exact objective"
            )
        expected_coverage_parents = (
            requirements_envelope.ref,
            parameters_envelope.ref,
            catalog_envelope.ref,
        )
        if (
            coverage_envelope.parent_refs != expected_coverage_parents
            or coverage_envelope.labels.get("transform_profile")
            != "scidiscovery.device-parameter-coverage.v1"
        ):
            raise RootToolError(
                "device parameter coverage was not produced by the exact deterministic inputs"
            )
        if (
            supplied_coverage != recomputed
            or self.artifacts.read(coverage_envelope.ref) != recomputed.canonical_json()
        ):
            raise RootToolError(
                "device parameter coverage differs from deterministic recomputation"
            )

        observed_source_keys = {
            observation.source_key
            for claim in parameters.claims
            for observation in claim.observations
        }
        catalog_source_keys = {item.source_key for item in catalog.sources}
        if observed_source_keys != catalog_source_keys:
            raise RootToolError(
                "source catalog must exactly match the parameter observations"
            )
        audit_source_keys = {item.source_key for item in audit.evidence}
        if not observed_source_keys.issubset(audit_source_keys):
            raise RootToolError(
                "independent audit does not cover every parameter evidence source"
            )
        audit_checks = {item.check_key: item for item in audit.checks}
        if not _PARAMETER_AUDIT_CHECKS.issubset(audit_checks) or any(
            audit_checks[key].status != "pass" for key in _PARAMETER_AUDIT_CHECKS
        ):
            raise RootToolError(
                "independent parameter audit is missing a required passing check"
            )
        audited_refs = {
            foundation_envelope.ref,
            requirements_envelope.ref,
            parameters_envelope.ref,
            catalog_envelope.ref,
            coverage_envelope.ref,
        }
        if not audited_refs.issubset(set(audit_envelope.parent_refs)):
            raise RootToolError(
                "independent audit was not produced from the exact parameter review set"
            )
        signal = self.tasks.scheduler_signal_for_output(audit_envelope.ref)
        if signal is None or signal.verdict != "pass":
            raise RootToolError(
                "independent parameter audit has no completed passing handoff"
            )

        by_id = {item.option_id: item for item in options}
        if recomputed.status == "fail":
            raise RootToolError(
                "blocking parameter coverage must be revised before human approval"
            )
        if recomputed.status == "review_required":
            exception = by_id.get("approve_with_exception")
            if (
                exception is None
                or not exception.requires_rationale
                or exception.terminal_state != "decided"
                or "approve" in by_id
            ):
                raise RootToolError(
                    "review-required parameters allow only a rationale-required "
                    "approve_with_exception decision"
                )
        elif "approve" not in by_id:
            raise RootToolError(
                "passing parameter coverage requires an approve decision option"
            )

    def approval_status(self, *, name: str) -> dict[str, Any]:
        binding = self._binding("approval", name)
        approval_id = binding.object_id
        status = self.approvals.status(approval_id)
        selected_option = None
        rationale = None
        if status.decision_ref is not None:
            decision = HumanDecision.model_validate_json(
                self.approvals.artifacts.read(status.decision_ref), strict=True
            )
            selected_option = decision.selected_option
            rationale = decision.rationale
        result = {
            **self._binding_value(binding),
            "status": status.status,
            "selected_option": selected_option,
            "rationale": rationale,
        }
        if status.status == "pending" and self.approval_base_url is not None:
            result["review_url"] = self.approval_base_url.rstrip("/") + "/"
        return result

    def approval_list(self, *, status: str | None, limit: int) -> dict[str, Any]:
        items = []
        for binding in self.bindings.list(instance=self._instance_id(), namespace="approval"):
            item = self.approval_status(name=binding.name)
            if status is not None and item["status"] != status:
                continue
            items.append(item)
            if len(items) >= limit:
                break
        return {"approvals": items}

    def execution_capabilities(self, *, executor: str) -> dict[str, Any]:
        capabilities = self._execution_capabilities(executor)
        return {
            "executor": executor,
            "capabilities": [dict(item.public_summary) for item in capabilities],
        }

    def execution_capability_bind(
        self,
        *,
        name: str,
        executor: str,
        profile: str,
        on_conflict: str,
    ) -> dict[str, Any]:
        matches = tuple(
            item
            for item in self._execution_capabilities(executor)
            if item.key == profile
        )
        if len(matches) != 1:
            raise RootToolError(
                "selected execution capability is not currently advertised"
            )
        capability = matches[0]
        fingerprint = canonical_sha256(
            {
                "operation": "execution_capability_bind",
                "executor": executor,
                "profile": profile,
                "schema": capability.schema_id,
                "payload_sha256": hashlib.sha256(capability.content).hexdigest(),
            }
        )
        with self._create_lock:
            target = self._creation_target(
                "artifact", name, fingerprint, on_conflict
            )
            if target.existing_object_id is None:
                envelope = self.artifacts.register(
                    capability.content,
                    ArtifactRegistration(
                        kind=capability.kind,
                        schema_id=capability.schema_id,
                        payload_schema_version=capability.payload_schema_version,
                        media_type=capability.media_type,
                        creator=self.intake.creator,
                        labels={
                            "execution_adapter": executor,
                            "capability_profile": profile,
                            "source": "active_adapter",
                        },
                        confidentiality="task_private",
                    ),
                    idempotency_key=(
                        "execution-capability:"
                        + canonical_sha256(
                            {
                                "instance": self._instance_id(),
                                "name": target.name,
                                "fingerprint": fingerprint,
                            }
                        )
                    ),
                )
                binding = self._bind_target(
                    "artifact", target, envelope.artifact_id, fingerprint
                )
            else:
                binding = self._binding("artifact", target.name)
        return {
            **self._binding_value(binding),
            "executor": executor,
            "profile": profile,
            "schema": capability.schema_id,
            "state": "bound",
        }

    def execution_request_create(
        self,
        *,
        name: str,
        executor: str,
        preparation_profile: str,
        payload_name: str,
        on_conflict: str,
    ) -> dict[str, Any]:
        if self.execution_bridge is None:
            raise RootToolError("no execution bridge is configured")
        with self._create_lock:
            payload_ref = self.artifacts.get_by_id(
                self._resolve_task_input_artifact(payload_name)
            ).ref
            self.execution_bridge.validate_request(
                executor=executor,
                preparation_profile=preparation_profile,
                payload=self.artifacts.read(payload_ref),
            )
            fingerprint = canonical_sha256(
                {
                    "operation": "execution_request_create",
                    "executor": executor,
                    "preparation_profile": preparation_profile,
                    "payload_ref": payload_ref,
                }
            )
            target = self._creation_target(
                "execution", name, fingerprint, on_conflict
            )
            if target.existing_object_id is not None:
                return self.execution_status(name=target.name)
            execution_id = self.executions.create(
                executor=executor,
                preparation_profile=preparation_profile,
                payload_ref=payload_ref,
            )
            self._bind_target("execution", target, execution_id, fingerprint)
        return self.execution_status(name=target.name)

    def _execution_capabilities(self, executor: str) -> tuple[Any, ...]:
        if self.execution_bridge is None:
            raise RootToolError("no execution bridge is configured")
        try:
            return self.execution_bridge.capabilities(executor=executor)
        except Exception as error:
            raise RootToolError("execution capability discovery failed") from error

    def execution_approval_request_create(self, *, name: str) -> dict[str, Any]:
        execution_id = self._resolve("execution", name)
        approval_name = _derived_name(name, "approval")
        with self._create_lock:
            existing = self._optional("approval", approval_name)
            if existing is None:
                approval_id = f"apr_{uuid.uuid4().hex}"
                request_ref, payload_ref = self.executions.approval_subject_refs(
                    execution_id
                )
                self.approvals.create_request(
                    approval_id=approval_id,
                    kind="execution_authorization",
                    subject_refs=(request_ref, payload_ref),
                    question="是否授权执行页面中展示的这一份冻结 TCAD 工程？",
                    options=(
                        ApprovalOption(
                            option_id="authorize_execution",
                            label="授权执行",
                            description="只提交页面中展示的这一个执行请求和冻结工程。",
                            requires_rationale=False,
                        ),
                        ApprovalOption(
                            option_id="revise_execution",
                            label="要求修改",
                            description="不提交本次请求，先修改执行内容再重新审批。",
                            requires_rationale=True,
                        ),
                    ),
                    requested_by=self.intake.creator,
                    idempotency_key=f"execution-approval:{approval_id}",
                )
                fingerprint = canonical_sha256(
                    {
                        "operation": "execution_approval_request_create",
                        "execution_name": name,
                        "subject_refs": (request_ref, payload_ref),
                    }
                )
                self._bind(
                    "approval",
                    approval_name,
                    approval_id,
                    request_fingerprint=fingerprint,
                )
        return self.approval_status(name=approval_name)

    def execution_abandon(self, *, name: str) -> dict[str, Any]:
        self.executions.abandon(self._resolve("execution", name))
        return self.execution_status(name=name)

    def execution_cancel(self, *, name: str) -> dict[str, Any]:
        if self.execution_bridge is None:
            raise RootToolError("no execution bridge is configured")
        self.execution_bridge.cancel(execution_id=self._resolve("execution", name))
        return self.execution_status(name=name)

    def execution_status(self, *, name: str) -> dict[str, Any]:
        binding = self._binding("execution", name)
        status = self.executions.status(binding.object_id)
        result_artifact_name = None
        if status.result_ref is not None:
            result_artifact_name = _derived_name(name, "result")
            self._bind("artifact", result_artifact_name, status.result_ref.artifact_id)
        return {
            **self._binding_value(binding),
            "executor": status.executor,
            "state": status.state,
            "result_artifact_name": result_artifact_name,
            "created_at": status.created_at,
        }

    def execution_list(self, *, state: str | None, limit: int) -> dict[str, Any]:
        items = []
        for binding in self.bindings.list(instance=self._instance_id(), namespace="execution"):
            item = self.execution_status(name=binding.name)
            if state is not None and item["state"] != state:
                continue
            items.append(item)
            if len(items) >= limit:
                break
        return {"executions": items}

    def execution_outputs(self, *, name: str) -> dict[str, Any]:
        execution_id = self._resolve("execution", name)
        outputs = []
        for value in self.executions.outputs(execution_id):
            output_name = _derived_name(name, "output", value.logical_name)
            self._bind("artifact", output_name, value.artifact_id)
            outputs.append(
                {
                    "output_label": value.logical_name,
                    "artifact_name": output_name,
                    "media_type": value.media_type,
                    "size_bytes": value.size_bytes,
                }
            )
        return {"execution_name": name, "outputs": outputs}

    def execution_start(self, *, name: str) -> dict[str, Any]:
        if self.execution_bridge is None:
            raise RootToolError("no execution bridge is configured")
        execution_id = self._resolve("execution", name)
        approval_id = self._resolve("approval", _derived_name(name, "approval"))
        self.execution_bridge.start(
            execution_id=execution_id, approval_id=approval_id
        )
        return self.execution_status(name=name)

    def execution_sync(self, *, name: str) -> dict[str, Any]:
        if self.execution_bridge is None:
            raise RootToolError("no execution bridge is configured")
        execution_id = self._resolve("execution", name)
        self.execution_bridge.sync(execution_id=execution_id)
        return self.execution_status(name=name)

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

    def _resolve_task_input_artifact(
        self, name: str, *, allow_nonqualifying: bool = False
    ) -> str:
        try:
            artifact_id = self._resolve("artifact", name)
        except SchedulerNameNotFound:
            suffix = ".output"
            if not name.endswith(suffix):
                raise
            task_name = name[: -len(suffix)]
            task_id = self._resolve("task", task_name)
            status = self.tasks.status(task_id)
            if status.output_ref is None:
                raise
            self._bind("artifact", name, status.output_ref.artifact_id)
            artifact_id = status.output_ref.artifact_id
        if not allow_nonqualifying:
            envelope = self.artifacts.get_by_id(artifact_id)
            if envelope.labels.get("scientific_claim_admissible") == "false":
                raise RootToolError(
                    f"{name}: artifact is provisional or development-only, cannot "
                    "support a scientific claim, and is not qualified for "
                    "operational use"
                )
            if self._failed_runtime_attestation(envelope):
                raise RootToolError(
                    f"{name}: runtime attestation verdict is fail; artifact is "
                    "not qualified for operational use"
                )
            signal = self.tasks.scheduler_signal_for_output(envelope.ref)
            if (
                signal is not None
                and signal.verdict in _NONQUALIFYING_HANDOFF_VERDICTS
            ):
                raise RootToolError(
                    f"{name}: task output handoff is {signal.verdict}; "
                    "artifact is not qualified for operational use"
                )
        return artifact_id

    def _failed_runtime_attestation(self, envelope: Any) -> bool:
        if envelope.schema_id != "tcad.runtime-attestation.v1":
            return False
        try:
            value = json.loads(self.artifacts.read(envelope.ref))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return True
        return not isinstance(value, dict) or value.get("verdict") != "pass"

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
            try:
                review = self._prepare_session_binding_review()
            except SchedulerInstanceNotFound as error:
                raise RootToolError(str(error)) from error
            rebound = self.bindings.session_instance(session_key=self.session_key)
            if rebound is not None:
                self.bindings.require_active_instance(instance_id=rebound)
                self.instance = rebound
                return rebound
            review_url = review.get("review_url")
            suffix = f" Review: {review_url}" if review_url else ""
            raise RootToolError(
                "this MCP session is not bound to a research instance; "
                f"local human confirmation is required.{suffix}"
            )
        if self.instance is None:
            raise RootToolError("no research instance is selected")
        return self.instance

    def _prepare_session_binding_review(
        self, *, preferred_name: str | None = None
    ) -> dict[str, Any]:
        if self.session_key is None:
            raise RootToolError(
                "session binding requires a transport-bound scheduler session"
            )
        with self._create_lock:
            request, candidates = self.bindings.prepare_session_binding_request(
                session_key=self.session_key,
                preferred_name=preferred_name,
            )
            if not self.approvals.has_request(request.approval_id):
                payload = canonical_json(
                    {
                        "schema_version": 1,
                        "authorization_effect": (
                            "把当前 MCP 进程独占绑定到用户选择的研究实例；"
                            "该实例原有进程绑定同时作废。"
                        ),
                        "candidates": [
                            {
                                "option_id": candidate.option_id,
                                "name": candidate.instance.name,
                                "title": candidate.instance.title,
                                "objective": candidate.instance.objective,
                                "state": candidate.instance.state,
                            }
                            for candidate in candidates
                        ],
                        "non_effects": [
                            "不创建新的研究实例",
                            "不批准任何科学结论",
                            "不授权或启动任何仿真",
                        ],
                    }
                )
                subject_ref = self.artifacts.register(
                    payload,
                    ArtifactRegistration(
                        artifact_id=f"art_{request.request_id}",
                        kind="research_session_binding_proposal",
                        schema_id="scidiscovery.session-binding-proposal.v1",
                        payload_schema_version=1,
                        media_type="application/json",
                        creator=self.intake.creator,
                        labels={"semantic_name": "research_session_binding"},
                        confidentiality="approval_only",
                    ),
                    idempotency_key=f"session-binding-subject:{request.request_id}",
                ).ref
                options = tuple(
                    ApprovalOption(
                        option_id=candidate.option_id,
                        label=f"进入 {candidate.instance.title}",
                        description=(
                            f"绑定到 {candidate.instance.name}，并撤销该实例的旧进程绑定。"
                        ),
                        requires_rationale=False,
                    )
                    for candidate in candidates
                ) + (
                    ApprovalOption(
                        option_id="cancel_binding",
                        label="暂不绑定",
                        description="保持当前 MCP 进程未绑定，不进入任何研究实例。",
                        requires_rationale=False,
                        terminal_state="cancelled_by_human",
                    ),
                )
                self.approvals.create_request(
                    approval_id=request.approval_id,
                    kind="research_session_binding",
                    subject_refs=(subject_ref,),
                    question="当前 MCP 进程要进入哪个研究实例？",
                    options=options,
                    requested_by=self.intake.creator,
                    idempotency_key=f"session-binding-approval:{request.request_id}",
                )

            approval = self.approvals.status(request.approval_id)
            if approval.decision_ref is not None and request.state == "pending":
                decision = HumanDecision.model_validate_json(
                    self.approvals.artifacts.read(approval.decision_ref), strict=True
                )
                request = self.bindings.apply_session_binding_decision(
                    approval_id=request.approval_id,
                    selected_option=decision.selected_option,
                )
                if request is None:
                    raise RootToolError("session-binding request disappeared")
            result: dict[str, Any] = {
                "binding_status": request.state,
                "candidate_names": [
                    candidate.instance.name for candidate in candidates
                ],
            }
            if approval.status == "pending" and self.approval_base_url is not None:
                result["review_url"] = self.approval_base_url.rstrip("/") + "/"
            if request.state == "activated" and request.instance_id is not None:
                self.instance = request.instance_id
                result["instance"] = self._instance_value(
                    self.bindings.get_instance(instance_id=request.instance_id)
                )
            return result

    def _persist_instance_selection(self) -> None:
        if self.session_key is not None:
            self.bindings.bind_session(
                session_key=self.session_key,
                instance_id=self._instance_id(),
            )

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
        self._tools = {tool.name: tool for tool in ROOT_TOOLS}

    def list_tools(self) -> list[dict[str, Any]]:
        return [tool.schema() for tool in ROOT_TOOLS]

    def call_tool(self, name: str, arguments: dict[str, Any] | None) -> Any:
        try:
            tool = self._tools[name]
        except KeyError as error:
            raise RootToolError(f"unknown root tool: {name}") from error
        try:
            parsed = tool.input_model.model_validate(arguments or {}, strict=False)
        except ValidationError as error:
            raise RootToolError(f"invalid arguments for {name}: {error}") from error
        values = {field: getattr(parsed, field) for field in type(parsed).model_fields}
        return getattr(self.facade, name)(**values)


def _metric_report_has_complete_plan_coverage(
    report: CurveConsistencyReport,
    portfolios: tuple[ExperimentPortfolio, ...],
) -> bool:
    if (
        report.validation_scope != "complete_plan"
        or report.validation_plan_sha256 is None
    ):
        return False
    for portfolio in portfolios:
        for plan in portfolio.validation_plans:
            if report.validation_plan_sha256 != canonical_sha256(plan):
                continue
            return report.covered_validation_check_keys == (
                deterministic_validation_check_keys(plan)
            )
    return False


def _derived_name(base: str, *parts: str) -> str:
    value = ".".join((base, *parts))
    if len(value) > 256:
        raise RootToolError("derived semantic name is too long")
    return value


def _identity_word(value: str) -> bool:
    lowered = value.lower()
    return any(word in lowered for word in ("_id", "hash", "token", "ref"))


__all__ = ["ROOT_TOOLS", "RootMCPRouter", "RootTool", "RootToolError", "RootToolFacade"]
