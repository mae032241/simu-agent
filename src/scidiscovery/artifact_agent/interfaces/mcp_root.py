"""Semantic scheduler MCP with all control identity kept behind the service."""

from __future__ import annotations

import hashlib
import threading
import uuid
from dataclasses import dataclass
from typing import Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..execution_bridge import ExecutionBridge
from ..schema.approval import ApprovalOption, HumanDecision
from ..schema.artifact import ArtifactRegistration
from ..schema.common import canonical_json, canonical_sha256
from ..schema.research_cycle import (
    ArtifactKind,
    ProblemFrame,
    ScientificClosureStatus,
    ScientificObjectStatus,
    ScientificReadiness,
)
from ..schema.task import TaskBudget, TaskInput, TaskOutputSpec
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
from ..transforms import ArtifactTransformAdapter, select_transform_adapter
from ...scheduler_topology import ready_capabilities


_NAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}$"
_SOURCE_NAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$"
_SCIENTIFIC_ARTIFACT_KINDS = frozenset(get_args(ArtifactKind))


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


class TaskInputSelection(RootToolInput):
    source_name: str = Field(pattern=_SOURCE_NAME_PATTERN)
    artifact_name: str = Field(pattern=_NAME_PATTERN)
    exposure: Literal["full", "on_demand", "handoff_only"] = "on_demand"


class TaskScheduleInput(NamedInput, RevisionInput):
    role: str = Field(min_length=1, max_length=256)
    context_profile: str | None = Field(default=None, min_length=1, max_length=256)
    instruction: str = Field(min_length=1, max_length=65536)
    inputs: tuple[TaskInputSelection, ...] = Field(default=(), max_length=256)
    dependency_names: tuple[str, ...] = Field(default=(), max_length=64)
    max_output_bytes: int = Field(default=262144, ge=1, le=8 * 1024 * 1024)
    timeout_seconds: int = Field(default=900, ge=1, le=86400)
    max_attempts: int = Field(default=1, ge=1, le=10)


class TaskListInput(RootToolInput):
    state: Literal[
        "created", "dispatched", "claimed", "completed", "failed", "timed_out"
    ] | None = None
    limit: int = Field(default=50, ge=1, le=100)


class DispatchInput(NamedInput):
    ttl_seconds: int = Field(default=900, ge=1, le=86400)


class FailureInput(NamedInput):
    reason: str = Field(min_length=1, max_length=4096)
    timed_out: bool = False
    expected_state: Literal["created", "dispatched", "claimed"]
    expected_last_activity_at: str | None


class ApprovalOptionInput(RootToolInput):
    option_key: str = Field(min_length=1, max_length=256)
    label: str = Field(min_length=1, max_length=256)
    description: str = Field(min_length=1, max_length=4096)
    requires_rationale: bool = False
    terminal_state: Literal["decided", "cancelled_by_human"] = "decided"


class ApprovalCreateInput(NamedInput, RevisionInput):
    kind: str = Field(min_length=1, max_length=256)
    subject_names: tuple[str, ...] = Field(min_length=1, max_length=256)
    question: str = Field(min_length=1, max_length=16384)
    options: tuple[ApprovalOptionInput, ...] = Field(min_length=2, max_length=32)
    expires_at: str | None = None


class ApprovalListInput(RootToolInput):
    status: Literal["pending", "decided", "expired", "cancelled_by_human"] | None = None
    limit: int = Field(default=50, ge=1, le=100)


class ExecutionCreateInput(NamedInput, RevisionInput):
    executor: str = Field(min_length=1, max_length=256)
    preparation_profile: str = Field(min_length=1, max_length=256)
    payload_name: str = Field(pattern=_NAME_PATTERN)


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
    RootTool("lifecycle_events", "Return persistent semantic task, approval, and execution state changes for this scheduler process.", EmptyInput),
    RootTool("artifact_ingest_file", "Freeze and bind one project file under a semantic name.", IngestFileInput),
    RootTool("artifact_catalog", "Read sanitized metadata for one bound semantic input.", NamedInput),
    RootTool("artifact_transform", "Apply one configured deterministic transform to bound semantic inputs.", ArtifactTransformInput),
    RootTool("task_schedule", "Create one named scientific task from bound semantic inputs.", TaskScheduleInput),
    RootTool("task_ready", "List dependency-ready semantic task names.", EmptyInput),
    RootTool("task_list", "List named tasks in this scheduler instance.", TaskListInput),
    RootTool("task_status", "Read one named task state and bounded scheduler signal.", NamedInput),
    RootTool("task_evidence_sources", "List frozen web evidence names produced by one task.", NamedInput),
    RootTool("task_prepare_dispatch", "Queue one named task and return its worker role.", DispatchInput),
    RootTool("task_record_failure", "Record one named task failure using a compare-and-set precondition.", FailureInput),
    RootTool("task_retry", "Return one named failed task to the ready queue.", NamedInput),
    RootTool("approval_request_create", "Create a named local human review for bound subjects.", ApprovalCreateInput),
    RootTool("approval_list", "List named reviews in this scheduler instance.", ApprovalListInput),
    RootTool("approval_status", "Read one named human-review state.", NamedInput),
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
        if proposal.state == "activated":
            instance = self.bindings.select_instance(name=proposal.name)
            self.instance = instance.instance_id
            self._persist_instance_selection()
            result["instance_state"] = instance.state
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
        instance_id = self._instance_id()
        for binding in self.bindings.list(instance=instance_id, namespace="task"):
            if self.tasks.status(binding.object_id).state in {
                "created",
                "dispatched",
                "claimed",
            }:
                raise RootToolError("research instance has an active scientific task")
        for binding in self.bindings.list(instance=instance_id, namespace="approval"):
            if self.approvals.status(binding.object_id).status == "pending":
                raise RootToolError("research instance has a pending human review")
        for binding in self.bindings.list(instance=instance_id, namespace="execution"):
            if self.executions.status(binding.object_id).state in {
                "created",
                "authorized",
                "submitted",
                "running",
                "cancelling",
            }:
                raise RootToolError("research instance has an active execution")
        value = self.bindings.close_instance(instance_id=instance_id)
        if self.session_key is not None:
            self.bindings.clear_session(session_key=self.session_key)
        self.instance = None
        return self._instance_value(value)

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

        objects: list[ScientificObjectStatus] = []
        effective_kinds: list[str] = []
        envelopes: dict[str, Any] = {}
        blockers: list[str] = []
        for binding in sorted(latest.values(), key=lambda item: item.logical_name):
            envelope = self.artifacts.get_by_id(binding.object_id)
            if envelope.kind not in _SCIENTIFIC_ARTIFACT_KINDS:
                continue
            qualification = "qualified"
            if envelope.kind == "scientific_foundation" and not self.approvals.is_subject_approved(
                envelope.ref,
                kind="scientific_foundation",
            ):
                qualification = "human_review_required"
                blockers.append(
                    f"{binding.name}: exact scientific foundation review is required"
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
            if item.kind == "validation_report" and item.qualification == "qualified"
        ]
        if reports:
            try:
                report = ValidationReport.model_validate_json(
                    self.artifacts.read(reports[-1].ref), strict=True
                )
                if report.claim_allowed:
                    claim_evaluability = "accepted"
            except ValidationError:
                blockers.append("latest validation report payload is invalid")

        base = ScientificReadiness(
            current_contradiction=contradiction,
            available_artifacts=tuple(effective_kinds),
            unresolved_needs=tuple(dict.fromkeys(unresolved)),
            blockers=tuple(dict.fromkeys(blockers)),
            claim_evaluability=claim_evaluability,
            execution_readiness=execution_readiness,
            rationale=(
                "Derived from the latest semantic revisions in this research "
                "instance; capabilities express data readiness, not workflow order."
            ),
        )
        actions = tuple(item.name for item in ready_capabilities(base))
        readiness = ScientificReadiness(
            **base.model_dump(mode="python", exclude={"suggested_capabilities"}),
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

        envelopes = tuple(
            self.artifacts.get_by_id(
                self._resolve_task_input_artifact(item.artifact_name)
            )
            for item in inputs
        )
        by_source = {
            item.source_name: envelope
            for item, envelope in zip(inputs, envelopes, strict=True)
        }
        parentage = getattr(adapter, "required_input_parentage", None)
        if parentage is not None:
            for child_name, parent_name in parentage(profile):
                if child_name not in by_source or parent_name not in by_source:
                    raise RootToolError(
                        "deterministic transform parentage names are absent"
                    )
                if by_source[parent_name].ref not in by_source[child_name].parent_refs:
                    raise RootToolError(
                        f"{child_name} was not produced from the exact {parent_name}"
                    )
        payloads = {
            item.source_name: self.artifacts.read(envelope.ref)
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
            for item in input_selections:
                envelope = self.artifacts.get_by_id(
                    self._resolve_task_input_artifact(item.artifact_name)
                )
                if envelope.kind == "scientific_foundation" and not self.approvals.is_subject_approved(
                    envelope.ref,
                    kind="scientific_foundation",
                ):
                    raise RootToolError(
                        "scientific foundation requires an exact approved human review"
                    )
                resolved_inputs.append(
                    TaskInput(
                        name=item.source_name,
                        artifact_ref=envelope.ref,
                        exposure=item.exposure,
                    )
                )
            inputs = tuple(resolved_inputs)
            dependencies = tuple(
                self._resolve("task", dependency_name)
                for dependency_name in dependency_names
            )
            contract = self.tasks.output_contract(values["role"])
            output = TaskOutputSpec(
                format=contract.format,
                kind=contract.kind,
                schema_id=contract.schema_id,
                validator=contract.validator,
                media_type=(
                    "application/json"
                    if contract.format == "json"
                    else "text/markdown; charset=utf-8"
                ),
                max_bytes=values.pop("max_output_bytes"),
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
                }
            )
        return {"task_name": name, "sources": sources}

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
            subjects = tuple(
                self.artifacts.get_by_id(self._resolve("artifact", subject)).ref
                for subject in values.pop("subject_names")
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
            fingerprint = canonical_sha256(
                {
                    "operation": "approval_request_create",
                    "kind": values["kind"],
                    "subject_refs": subjects,
                    "question": values["question"],
                    "options": options,
                    "expires_at": values["expires_at"],
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
                **values,
            )
            self._bind_target("approval", target, approval_id, fingerprint)
        return self.approval_status(name=target.name)

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
            self.execution_bridge.validate_request(
                executor=executor,
                preparation_profile=preparation_profile,
            )
            payload_ref = self.artifacts.get_by_id(
                self._resolve("artifact", payload_name)
            ).ref
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

    def _resolve_task_input_artifact(self, name: str) -> str:
        try:
            return self._resolve("artifact", name)
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
            return status.output_ref.artifact_id

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


def _derived_name(base: str, *parts: str) -> str:
    value = ".".join((base, *parts))
    if len(value) > 256:
        raise RootToolError("derived semantic name is too long")
    return value


def _identity_word(value: str) -> bool:
    lowered = value.lower()
    return any(word in lowered for word in ("_id", "hash", "token", "ref"))


__all__ = ["ROOT_TOOLS", "RootMCPRouter", "RootTool", "RootToolError", "RootToolFacade"]
