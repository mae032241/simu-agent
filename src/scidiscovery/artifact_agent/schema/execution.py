"""Domain-neutral execution identity and lifecycle contracts."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .artifact import MediaType, UtcRfc3339
from .common import Identifier, SchemaModel, Sha256
from .refs import ArtifactRef


class ExecutionRequest(SchemaModel):
    execution_id: Identifier
    executor: Identifier
    preparation_profile: Identifier
    payload_ref: ArtifactRef
    created_at: UtcRfc3339


class LocalFileDescriptor(SchemaModel):
    name: Identifier
    local_path: Annotated[str, Field(min_length=1, max_length=4096)]
    sha256: Sha256
    size_bytes: Annotated[int, Field(ge=0, le=2**50)]
    media_type: MediaType


ExecutionState = Literal[
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
]


class ExecutionResultManifest(SchemaModel):
    execution_id: Identifier
    external_run_id: Identifier
    terminal_state: Literal["succeeded", "failed", "cancelled"]
    output_refs: tuple[ArtifactRef, ...]
    collected_at: UtcRfc3339


__all__ = [
    "ExecutionRequest",
    "ExecutionResultManifest",
    "ExecutionState",
    "LocalFileDescriptor",
]
