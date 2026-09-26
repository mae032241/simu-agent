"""Control-owned immutable tool evidence wire values; no service implementation.

These models describe receipts, not authority to create or qualify them. Domain
plugins consume the bounded records projection through plugin_runtime.evidence.
"""
from typing import Any, Literal
from pydantic import Field
from .common import SchemaModel, ContractDiagnostic, Sha256, Identifier
from .refs import ArtifactRef


class ToolSourceBinding(SchemaModel):
    artifact_ref: ArtifactRef
    port_name: Identifier


class ToolAttempt(SchemaModel):
    attempt_key: Identifier
    tool_name: Identifier
    operation_digest: Sha256
    request_digest: Sha256
    state: Literal["started", "completed", "rejected", "interrupted"]
    result_status: Identifier | None = None
    reason_code: Identifier | None = None
    result_digest: Sha256 | None = None
    read_sources: tuple[Identifier, ...] = Field(default=(), max_length=128)
    sources_digest: Sha256 | None = None
    diagnostics: tuple[ContractDiagnostic, ...] = Field(default=(), max_length=8)


class ToolAttemptProof(SchemaModel):
    bindings: dict[str, ToolSourceBinding] = Field(default_factory=dict, max_length=128)
    attempts: tuple[ToolAttempt, ...] = Field(default=(), max_length=64)


class ToolRecoveryOrigin(ToolAttemptProof):
    source_request_digest: Sha256
    operation_digest: Sha256
    draft_digest: Sha256


class ToolRecoveryProof(ToolRecoveryOrigin):
    # Each origin keeps its own alias and attempt namespace. The existing total
    # attempt budget bounds this flat history; no recursive proof expansion.
    ancestors: tuple[ToolRecoveryOrigin, ...] = Field(default=(), max_length=64)


class ToolEvidenceManifest(ToolAttemptProof):
    records: tuple[dict[str, Any], ...] = Field(default=(), max_length=128)
    accesses: tuple[dict[str, Any], ...] = Field(default=(), max_length=32)
    recovery: ToolRecoveryProof | None = None
