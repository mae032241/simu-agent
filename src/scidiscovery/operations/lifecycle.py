"""The one compiler-owned lifecycle protocol for every Agent Operation."""

from __future__ import annotations

from types import MappingProxyType

from pydantic import BaseModel, ConfigDict

from .spec import AgentLifecycleProtocol, AgentLifecycleTool, canonical_digest


class AgentLifecycleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


_INPUT_SCHEMA_DIGEST = canonical_digest(AgentLifecycleInput.model_json_schema())

AGENT_LIFECYCLE_PROTOCOL = AgentLifecycleProtocol(
    version="1",
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
            name="worker_heartbeat",
            description="Record bounded liveness without extending the absolute budget.",
            input_schema_sha256=_INPUT_SCHEMA_DIGEST,
            capability="run.heartbeat",
        ),
        AgentLifecycleTool(
            name="worker_submit_result",
            description=(
                "Validate, seal, and submit the complete result bundle, or return "
                "bounded correction diagnostics."
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
