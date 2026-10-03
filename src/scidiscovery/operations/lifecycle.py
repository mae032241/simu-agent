"""The one compiler-owned lifecycle protocol for every Agent Operation."""

from __future__ import annotations

from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field

from .spec import AgentLifecycleProtocol, AgentLifecycleTool, canonical_digest


class AgentLifecycleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentHistoryInput(AgentLifecycleInput):
    before: str | None = Field(default=None, min_length=1, max_length=256,
        description="Pass next_before unchanged to continue older tasks in this assignment's frozen range. Omitted starts the time index.")
    limit: int = Field(default=8, ge=1, le=20,
        description="Maximum complete task entries; encoded response is also bounded by frozen input_materials.original_read_page_bytes. Whole fields may be omitted with original navigation, never silently truncated.")


_INPUT_SCHEMA_DIGEST = canonical_digest(AgentLifecycleInput.model_json_schema())

AGENT_LIFECYCLE_PROTOCOL = AgentLifecycleProtocol(
    version="2",
    tools=(
        AgentLifecycleTool(
            name="worker_open_assignment",
            description=(
                "Open the exact Run assignment and materialize its private "
                "read-only inputs."
            ),
            input_schema_sha256=_INPUT_SCHEMA_DIGEST,
            capability="run.open_assignment",
        ),
        AgentLifecycleTool(
            name="worker_read_history",
            description="Read a bounded time index of terminal tasks frozen at this assignment's first controlled open. before defaults to null and limit to 8; follow next_before for early attempts. revision_scope reports exact immutable supersedes ancestry coverage, bounded by the existing 2048-character Root cursor capacity; old frozen scopes never expand. Independent review Operations receive neutral task/input indexes, without author summaries, verdicts, scientific excerpts or Root judgments; exact bound subjects remain readable. Other Operations receive attributed existing Worker/Root excerpts, not consumed originals, controlled verification, qualification, or retry gates. A scientific_negative is only an explicit Worker hypothesis contradiction under report conditions, not an engineering failure or verified mechanism rejection. Missing/invalid individual content remains unknown while healthy entries remain readable; exact scope/authorization conflicts remain unavailable. Operations with worker_reference_read can list/read an exact history_task's allowed originals under existing reference budgets; other Operations must bind needed originals as scientific inputs. Conditions may change and justify retry.",
            input_schema_sha256=canonical_digest(AgentHistoryInput.model_json_schema()),
            capability="run.read_history",
        ),
        AgentLifecycleTool(
            name="worker_heartbeat",
            description="Record bounded liveness without extending the absolute budget.",
            input_schema_sha256=_INPUT_SCHEMA_DIGEST,
            capability="run.heartbeat",
        ),
        AgentLifecycleTool(
            name="worker_submit_result",
            owner_only=True,
            description=(
                "Validate, seal, and submit the complete result bundle, or return "
                "bounded correction diagnostics. The task owner integrates helper work before submission; submission ends helper tool access."
            ),
            input_schema_sha256=_INPUT_SCHEMA_DIGEST,
            capability="run.submit_result",
        ),
    ),
)

AGENT_LIFECYCLE_BY_NAME = MappingProxyType(
    {item.name: item for item in AGENT_LIFECYCLE_PROTOCOL.tools}
)


__all__ = [
    "AGENT_LIFECYCLE_BY_NAME",
    "AGENT_LIFECYCLE_PROTOCOL",
    "AgentLifecycleInput",
]
