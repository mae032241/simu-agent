"""Minimal control-owned task contracts for scientific workers."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, model_validator

from .artifact import MediaType, UtcRfc3339
from .common import Identifier, SchemaModel
from .refs import ArtifactRef


ContextExposure = Literal["full", "on_demand", "handoff_only"]


class TaskInput(SchemaModel):
    """Internal binding between a task-local source name and an exact artifact."""

    name: Identifier
    artifact_ref: ArtifactRef
    exposure: ContextExposure = "on_demand"


class TaskOutputSpec(SchemaModel):
    """Control-owned output shape; workers only see format and size."""

    format: Literal["json", "text"]
    kind: Identifier = "scientific_output"
    schema_id: Identifier
    validator: str | None = Field(default=None, min_length=3, max_length=512)
    media_type: MediaType
    max_bytes: Annotated[int, Field(ge=1, le=8 * 1024 * 1024)]

    @model_validator(mode="after")
    def _format_matches_media_type(self) -> TaskOutputSpec:
        base = self.media_type.split(";", 1)[0].strip().lower()
        if self.format == "json" and base != "application/json":
            raise ValueError("json output must use application/json")
        if self.format == "text" and not base.startswith("text/"):
            raise ValueError("text output must use a text media type")
        return self


class TaskBudget(SchemaModel):
    max_attempts: Annotated[int, Field(ge=1, le=10)] = 1
    timeout_seconds: Annotated[int, Field(ge=1, le=86400)] = 900


SchedulerItem = Annotated[str, Field(min_length=1, max_length=512)]


class SchedulerSignal(SchemaModel):
    """Small worker-authored result used only for orchestration decisions."""

    verdict: Literal["pass", "revise", "blocked", "inconclusive"]
    summary: Annotated[str, Field(min_length=1, max_length=2048)]
    assumptions: Annotated[tuple[SchedulerItem, ...], Field(max_length=32)] = ()
    missing_inputs: Annotated[tuple[SchedulerItem, ...], Field(max_length=32)] = ()
    next_actions: Annotated[tuple[SchedulerItem, ...], Field(max_length=32)] = ()


class AgentTask(SchemaModel):
    """Internal task record. Every identity is assigned by the control plane."""

    task_id: Identifier
    role: Identifier
    context_profile: Identifier = "default"
    instruction_ref: ArtifactRef
    inputs: Annotated[tuple[TaskInput, ...], Field(max_length=256)]
    dependency_task_ids: Annotated[tuple[Identifier, ...], Field(max_length=64)] = ()
    output: TaskOutputSpec
    budget: TaskBudget = TaskBudget()
    created_at: UtcRfc3339

    @model_validator(mode="after")
    def _unique_names_and_dependencies(self) -> AgentTask:
        names = tuple(item.name for item in self.inputs)
        if len(names) != len(set(names)):
            raise ValueError("task input names must be unique")
        if len(self.dependency_task_ids) != len(set(self.dependency_task_ids)):
            raise ValueError("task dependencies must be unique")
        if self.task_id in self.dependency_task_ids:
            raise ValueError("task cannot depend on itself")
        return self


class AssignmentInput(SchemaModel):
    """Worker-visible task-local input metadata with no control-plane name or identity."""

    name: Identifier
    media_type: MediaType
    size_bytes: Annotated[int, Field(ge=0)]
    exposure: ContextExposure
    access_modes: tuple[
        Literal["read_text", "stage_file", "extract_pdf_text", "read_table"], ...
    ]
    handoff: SchedulerSignal | None = None


class AssignmentOutput(SchemaModel):
    """Exact worker-visible output contract for the active role."""

    format: Literal["json", "text"]
    media_type: MediaType
    max_bytes: Annotated[int, Field(ge=1)]
    json_schema: dict[str, Any]
    protocol: Literal["scidiscovery.role-result-envelope.v1"] = (
        "scidiscovery.role-result-envelope.v1"
    )


class WorkerAssignment(SchemaModel):
    """The complete worker view. It intentionally contains no IDs or hashes."""

    role: Identifier
    context_profile: Identifier
    instruction: str
    inputs: tuple[AssignmentInput, ...]
    output: AssignmentOutput
    capabilities: tuple[Identifier, ...]
    lease_seconds: Annotated[int, Field(ge=1, le=86400)]


TaskState = Literal[
    "created",
    "dispatched",
    "claimed",
    "completed",
    "failed",
    "timed_out",
]
TaskEventType = Literal[
    "created",
    "dispatched",
    "claimed",
    "completed",
    "failed",
    "timed_out",
    "requeued",
]


class TaskEvent(SchemaModel):
    event_id: Identifier
    task_id: Identifier
    event_type: TaskEventType
    attempt: Annotated[int, Field(ge=0)]
    recorded_at: UtcRfc3339
    reason: str | None = Field(default=None, max_length=4096)
    output_ref: ArtifactRef | None = None

    @model_validator(mode="after")
    def _event_shape(self) -> TaskEvent:
        if self.event_type == "completed" and self.output_ref is None:
            raise ValueError("completed task event requires output_ref")
        if self.event_type != "completed" and self.output_ref is not None:
            raise ValueError("only completed task event may carry output_ref")
        if self.event_type in {"failed", "timed_out"} and not self.reason:
            raise ValueError("terminal failure requires reason")
        return self


__all__ = [
    "AgentTask",
    "AssignmentInput",
    "AssignmentOutput",
    "ContextExposure",
    "TaskBudget",
    "TaskEvent",
    "TaskEventType",
    "TaskInput",
    "TaskOutputSpec",
    "SchedulerSignal",
    "TaskState",
    "WorkerAssignment",
]
