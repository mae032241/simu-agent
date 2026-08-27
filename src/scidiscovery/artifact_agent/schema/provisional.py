"""Task-private manifests for bounded, reusable worker checkpoints."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .artifact import MediaType, UtcRfc3339
from .common import SchemaModel
from .refs import ArtifactRef
from .task import OutputPathSegment


class ProvisionalDiagnostic(SchemaModel):
    path: Annotated[str, Field(min_length=1, max_length=1024)]
    message: Annotated[str, Field(min_length=1, max_length=2048)]
    type: Annotated[str, Field(min_length=1, max_length=256)]


class ProvisionalSnapshotFile(SchemaModel):
    relative_path: Annotated[str, Field(min_length=1, max_length=2048)]
    media_type: MediaType
    size_bytes: Annotated[int, Field(ge=0, le=512 * 1024 * 1024)]
    artifact_ref: ArtifactRef
    collection: OutputPathSegment | None = None
    item: OutputPathSegment | None = None
    control_generated: bool = False
    materialize_on_retry: bool = True

    @model_validator(mode="after")
    def _collection_shape(self) -> ProvisionalSnapshotFile:
        if (self.collection is None) != (self.item is None):
            raise ValueError("snapshot collection and item must be supplied together")
        return self


class ProvisionalSnapshotManifest(SchemaModel):
    schema_version: Literal[1] = 1
    reason: Literal[
        "checkpoint",
        "validation_rejected",
        "finalization_candidate",
        "development_debug_candidate",
        "development_debug_result",
    ]
    attempt: Annotated[int, Field(ge=1, le=10)]
    sequence: Annotated[int, Field(ge=1, le=4096)]
    created_at: UtcRfc3339
    validation_status: Literal["not_validated", "rejected", "valid"]
    files: Annotated[tuple[ProvisionalSnapshotFile, ...], Field(max_length=4098)]
    diagnostics: Annotated[
        tuple[ProvisionalDiagnostic, ...], Field(max_length=64)
    ] = ()
    diagnostics_truncated: bool = False
    development_only: bool = False

    @model_validator(mode="after")
    def _unique_paths(self) -> ProvisionalSnapshotManifest:
        paths = tuple(item.relative_path for item in self.files)
        if len(paths) != len(set(paths)):
            raise ValueError("provisional snapshot paths must be unique")
        return self


__all__ = [
    "ProvisionalDiagnostic",
    "ProvisionalSnapshotFile",
    "ProvisionalSnapshotManifest",
]
