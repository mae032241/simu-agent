"""Validated output emitted by a deterministic Artifact transform."""

from __future__ import annotations

import re
from dataclasses import dataclass


_OUTPUT_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


@dataclass(frozen=True, slots=True)
class TransformOutput:
    label: str
    content: bytes
    kind: str
    schema: str
    payload_schema_version: int
    media_type: str
    port_name: str | None = None

    def __post_init__(self) -> None:
        if not _OUTPUT_LABEL.fullmatch(self.label):
            raise ValueError("transform output label is invalid")
        if type(self.content) is not bytes:
            raise TypeError("transform output content must be bytes")
        if self.port_name is not None and not _OUTPUT_LABEL.fullmatch(self.port_name):
            raise ValueError("transform output port name is invalid")
        if not self.kind or not self.schema or not self.media_type:
            raise ValueError("transform output semantics are incomplete")
        if self.payload_schema_version < 1:
            raise ValueError("transform output schema version is invalid")


__all__ = ["TransformOutput"]
