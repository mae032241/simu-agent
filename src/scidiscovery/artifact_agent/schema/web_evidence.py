"""Immutable metadata for one task-scoped web evidence snapshot."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from .artifact import MediaType, UtcRfc3339
from .common import SchemaModel
from .refs import ArtifactRef


class WebEvidenceSnapshot(SchemaModel):
    original_url: Annotated[str, Field(min_length=1, max_length=4096)]
    final_url: Annotated[str, Field(min_length=1, max_length=4096)]
    accessed_at: UtcRfc3339
    http_status: Annotated[int, Field(ge=200, le=299)]
    media_type: MediaType
    response_ref: ArtifactRef


__all__ = ["WebEvidenceSnapshot"]
