"""Domain-neutral execution identity and lifecycle contracts."""

from __future__ import annotations

from typing import Annotated, Literal, Any

from pydantic import Field

from .approval import CompiledApprovalIdentity
from .artifact import MediaType, UtcRfc3339
from .common import (
    Identifier,
    SchemaModel,
    Sha256,
    canonical_json as encode_canonical_json,
)
from .refs import ArtifactRef


class ExecutionAdmission(SchemaModel):
    """Domain adapter judgment over administrator configuration and exact budget."""

    outcome: Literal["policy", "require_human_approval", "deny"]
    policy_digest: Sha256
    policy: dict[str, Any]
    budget: dict[str, int]
    allowance: dict[str, int]
    outside_allowance: Literal["require_human_approval", "deny"]
    budget_key: Sha256
    reason: Annotated[str, Field(min_length=1, max_length=1024)]


class ExecutionRequest(SchemaModel):
    execution_id: Identifier
    executor: Identifier
    preparation_profile: Identifier
    payload_ref: ArtifactRef
    created_at: UtcRfc3339
    compiled_identity: CompiledApprovalIdentity | None = None

    def canonical_json(self) -> bytes:
        if self.compiled_identity is not None:
            return encode_canonical_json(self)
        return encode_canonical_json(
            {
                field_name: getattr(self, field_name)
                for field_name in type(self).model_fields
                if field_name != "compiled_identity"
            }
        )


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
