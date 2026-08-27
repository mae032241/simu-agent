"""Immutable metadata for one task-scoped web evidence snapshot."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, model_validator

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
    extracted_text_ref: ArtifactRef | None = None
    text_truncated: bool = False

    @model_validator(mode="after")
    def _text_metadata_is_complete(self) -> WebEvidenceSnapshot:
        if self.extracted_text_ref is None and self.text_truncated:
            raise ValueError("web evidence cannot truncate absent extracted text")
        return self


__all__ = ["WebEvidenceSnapshot"]
