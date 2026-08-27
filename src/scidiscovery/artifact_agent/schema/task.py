"""Minimal control-owned task contracts for scientific workers."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, model_validator

from .artifact import MediaType, UtcRfc3339
from .common import Identifier, SchemaModel
from .refs import ArtifactRef
from .structured_revision import RevisionTargetSchema, validate_json_pointer


ContextExposure = Literal["full", "on_demand", "handoff_only"]
ContextUsage = Literal[
    "claim_evidence",
    "revision_base",
    "change_request",
    "prior_signal",
    "cached_excerpt",
    "unchanged_set_receipt",
    "evidence_inventory",
]
OutputPathSegment = Annotated[
    str,
    Field(
        min_length=1,
        max_length=256,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$",
    ),
]


class TaskInput(SchemaModel):
    """Internal binding between a task-local source name and an exact artifact."""

    name: Identifier
    artifact_ref: ArtifactRef
    exposure: ContextExposure = "on_demand"
    usage: ContextUsage = "claim_evidence"


class TaskRevisionSpec(SchemaModel):
    """Control-owned boundary for one identity-free structured revision."""

    base_source_name: Identifier
    target_schema: RevisionTargetSchema
    allowed_paths: Annotated[tuple[str, ...], Field(min_length=1, max_length=64)]

    @model_validator(mode="after")
    def _paths_are_bounded(self) -> TaskRevisionSpec:
        if len(self.allowed_paths) != len(set(self.allowed_paths)):
            raise ValueError("allowed revision paths must be unique")
        for path in self.allowed_paths:
            validate_json_pointer(path)
        return self


class TaskOutputSpec(SchemaModel):
    """Control-owned output shape; workers only see format and size."""

    format: Literal["json", "text"]
    kind: Identifier = "scientific_output"
    schema_id: Identifier
    validator: str | None = Field(default=None, min_length=3, max_length=512)
    context_validator: str | None = Field(default=None, min_length=3, max_length=512)
    context_sources: Annotated[tuple[Identifier, ...], Field(max_length=16)] = ()
    media_type: MediaType
    max_bytes: Annotated[int, Field(ge=1, le=8 * 1024 * 1024)]
    collections: Annotated[
        tuple["TaskOutputCollectionSpec", ...], Field(max_length=64)
    ] = ()
    revision: TaskRevisionSpec | None = None

    @model_validator(mode="after")
    def _format_matches_media_type(self) -> TaskOutputSpec:
        base = self.media_type.split(";", 1)[0].strip().lower()
        if self.format == "json" and base != "application/json":
            raise ValueError("json output must use application/json")
        if self.format == "text" and not base.startswith("text/"):
            raise ValueError("text output must use a text media type")
        names = tuple(item.name for item in self.collections)
        if len(names) != len(set(names)):
            raise ValueError("task output collection names must be unique")
        if self.revision is not None and self.collections:
            raise ValueError("structured revision output cannot declare collections")
        if (
            self.schema_id == "scidiscovery.structured-revision.v1"
        ) != (self.revision is not None):
            raise ValueError(
                "structured revision schema and revision boundary must be declared together"
            )
        if self.context_sources and self.context_validator is None:
            raise ValueError(
                "context_sources require a contextual output validator"
            )
        if len(self.context_sources) != len(set(self.context_sources)):
            raise ValueError("context_sources must be unique")
        return self

    @property
    def max_bundle_bytes(self) -> int:
        return self.max_bytes + sum(item.max_total_bytes for item in self.collections)


class TaskOutputCollectionSpec(SchemaModel):
    """Exact bounded contract for one optional collection of sibling outputs."""

    name: OutputPathSegment
    kind: Identifier
    schema_id: Identifier
    validator: str | None = Field(default=None, min_length=3, max_length=512)
    bundle_validator: str | None = Field(default=None, min_length=3, max_length=512)
    json_schema: dict[str, Any] = Field(default_factory=dict)
    media_types: Annotated[tuple[MediaType, ...], Field(min_length=1, max_length=16)]
    min_items: Annotated[int, Field(ge=0, le=4096)] = 0
    max_items: Annotated[int, Field(ge=1, le=4096)]
    max_item_bytes: Annotated[int, Field(ge=1, le=64 * 1024 * 1024)]
    max_total_bytes: Annotated[int, Field(ge=1, le=512 * 1024 * 1024)]

    @model_validator(mode="after")
    def _validate_bounds(self) -> TaskOutputCollectionSpec:
        if self.min_items > self.max_items:
            raise ValueError("collection min_items must not exceed max_items")
        normalized = tuple(value.strip().lower() for value in self.media_types)
        if len(normalized) != len(set(normalized)):
            raise ValueError("collection media_types must be unique")
        return self


class TaskOutputBundleItem(SchemaModel):
    """Identity-free descriptor for one declared collection file."""

    collection: OutputPathSegment
    item: OutputPathSegment
    media_type: MediaType
    relative_path: Annotated[str, Field(min_length=1, max_length=1024)]

    @model_validator(mode="after")
    def _validate_relative_path(self) -> TaskOutputBundleItem:
        expected = f"collections/{self.collection}/{self.item}"
        if self.relative_path != expected:
            raise ValueError(
                "bundle item relative_path must equal collections/<collection>/<item>"
            )
        return self


class TaskOutputBundle(SchemaModel):
    """Worker-authored, identity-free manifest for bounded sibling outputs."""

    protocol: Literal["scidiscovery.task-output-bundle.v1"] = (
        "scidiscovery.task-output-bundle.v1"
    )
    items: Annotated[tuple[TaskOutputBundleItem, ...], Field(max_length=4096)] = ()

    @model_validator(mode="after")
    def _unique_items(self) -> TaskOutputBundle:
        keys = tuple((item.collection, item.item) for item in self.items)
        if len(keys) != len(set(keys)):
            raise ValueError("bundle collection items must be unique")
        paths = tuple(item.relative_path for item in self.items)
        if len(paths) != len(set(paths)):
            raise ValueError("bundle relative paths must be unique")
        return self


class AssignmentOutputCollection(SchemaModel):
    """Worker-visible collection contract without registration metadata."""

    name: OutputPathSegment
    media_types: Annotated[tuple[MediaType, ...], Field(min_length=1, max_length=16)]
    min_items: Annotated[int, Field(ge=0, le=4096)]
    max_items: Annotated[int, Field(ge=1, le=4096)]
    max_item_bytes: Annotated[int, Field(ge=1)]
    max_total_bytes: Annotated[int, Field(ge=1)]
    relative_directory: Annotated[str, Field(min_length=1, max_length=1024)]
    json_schema_relative_path: Annotated[
        str, Field(min_length=1, max_length=1024)
    ] | None = None

    @model_validator(mode="after")
    def _relative_directory_matches(self) -> AssignmentOutputCollection:
        if self.relative_directory != f"output/collections/{self.name}":
            raise ValueError(
                "collection relative_directory must equal output/collections/<name>"
            )
        if self.json_schema_relative_path is not None:
            expected = f"schema/collections/{self.name}.schema.json"
            if self.json_schema_relative_path != expected:
                raise ValueError(
                    "collection JSON Schema path must equal "
                    "schema/collections/<name>.schema.json"
                )
            if not any(
                value.split(";", 1)[0].strip().lower() == "application/json"
                for value in self.media_types
            ):
                raise ValueError(
                    "only a JSON collection may declare a JSON Schema path"
                )
        return self


class AssignmentProvisionalContext(SchemaModel):
    """Identity-free descriptor for one prior-attempt checkpoint."""

    name: Identifier
    attempt: Annotated[int, Field(ge=1, le=10)]
    reason: Literal[
        "checkpoint",
        "validation_rejected",
        "finalization_candidate",
        "development_debug_candidate",
        "development_debug_result",
    ]
    validation_status: Literal["not_validated", "rejected", "valid"]
    relative_directory: Annotated[str, Field(min_length=1, max_length=1024)]
    file_count: Annotated[int, Field(ge=0, le=4098)]
    size_bytes: Annotated[int, Field(ge=0, le=8 * 1024 * 1024 * 1024)]
    diagnostics_available: bool = False
    development_only: bool = False


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
    usage: ContextUsage
    access_modes: tuple[Literal["native_read", "extract_pdf_text"], ...]
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
    collections: Annotated[
        tuple[AssignmentOutputCollection, ...], Field(max_length=64)
    ] = ()
    bundle_relative_path: Literal["output/bundle.json"] | None = None
    max_bundle_bytes: Annotated[int, Field(ge=1)] | None = None
    revision: TaskRevisionSpec | None = None

    @model_validator(mode="after")
    def _bundle_shape(self) -> AssignmentOutput:
        if self.collections:
            if self.bundle_relative_path is None or self.max_bundle_bytes is None:
                raise ValueError("collection output requires its bundle contract")
        elif self.bundle_relative_path is not None or self.max_bundle_bytes is not None:
            raise ValueError("bundle contract requires output collections")
        return self


class WorkerAssignment(SchemaModel):
    """The complete worker view. It intentionally contains no IDs or hashes."""

    role: Identifier
    context_profile: Identifier
    instruction: str
    inputs: tuple[AssignmentInput, ...]
    output: AssignmentOutput
    provisional_contexts: Annotated[
        tuple[AssignmentProvisionalContext, ...], Field(max_length=320)
    ] = ()
    capabilities: tuple[Identifier, ...]
    lease_seconds: Annotated[int, Field(ge=1, le=86400)]


TaskState = Literal[
    "created",
    "dispatched",
    "claimed",
    "finalizing",
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
    "AssignmentOutputCollection",
    "AssignmentProvisionalContext",
    "ContextExposure",
    "ContextUsage",
    "TaskBudget",
    "TaskEvent",
    "TaskEventType",
    "TaskInput",
    "TaskOutputBundle",
    "TaskOutputBundleItem",
    "TaskOutputCollectionSpec",
    "TaskOutputSpec",
    "TaskRevisionSpec",
    "SchedulerSignal",
    "TaskState",
    "WorkerAssignment",
]
