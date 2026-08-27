"""Immutable, domain-neutral SciDiscovery artifact contracts."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from .common import Identifier, SchemaModel, Sha256
from .refs import ActorRef, ArtifactRef


MediaType = Annotated[str, Field(min_length=3, max_length=255)]
LabelValue = Annotated[str, Field(max_length=1024)]
UtcRfc3339 = Annotated[
    str,
    Field(
        pattern=(
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
            r"(?:\.\d{1,6})?Z$"
        )
    ),
]
Confidentiality = Literal["project", "task_private", "approval_only"]
ContentEncoding = Literal["identity", "gzip", "zstd"]

_MIME_TOKEN = r"[A-Za-z0-9!#$%&'*+.^_`|~-]+"
_MEDIA_TYPE_RE = re.compile(rf"^{_MIME_TOKEN}/{_MIME_TOKEN}(?:\s*;.*)?$")
_PARAMETER_RE = re.compile(
    rf"^{_MIME_TOKEN}=(?:{_MIME_TOKEN}|\"[^\"\r\n]*\")$"
)


class ArtifactRegistration(SchemaModel):
    """Caller-supplied immutable semantics for registering payload bytes."""

    artifact_id: Identifier | None = None
    kind: Identifier
    schema_id: Identifier
    payload_schema_version: Annotated[int, Field(ge=1)]
    media_type: MediaType
    creator: ActorRef
    parent_refs: tuple[ArtifactRef, ...] = ()
    supersedes_ref: ArtifactRef | None = None
    task_ref: ArtifactRef | None = None
    labels: dict[Identifier, LabelValue] = Field(default_factory=dict)
    confidentiality: Confidentiality = "project"
    content_encoding: ContentEncoding = "identity"

    @field_validator("media_type")
    @classmethod
    def _validate_media_type(cls, value: str) -> str:
        if "\r" in value or "\n" in value or not _MEDIA_TYPE_RE.fullmatch(value):
            raise ValueError("media_type must be a complete RFC-style media type")
        parts = value.split(";")
        if any(
            not _PARAMETER_RE.fullmatch(parameter.strip())
            for parameter in parts[1:]
        ):
            raise ValueError("media_type contains an invalid parameter")
        return value

    @model_validator(mode="after")
    def _validate_provenance(self) -> ArtifactRegistration:
        identities = [_reference_identity(ref) for ref in self.parent_refs]
        if len(identities) != len(set(identities)):
            raise ValueError("parent_refs must be ordered and free of duplicates")
        return self


class ArtifactRegisterRequest(SchemaModel):
    """Canonical idempotency request persisted with every registration."""

    operation: Literal["artifact.register"]
    payload_sha256: Sha256
    size_bytes: Annotated[int, Field(ge=0)]
    registration: ArtifactRegistration


class ArtifactEnvelope(SchemaModel):
    """Immutable registry record binding logical identity to exact CAS bytes."""

    artifact_id: Identifier
    kind: Identifier
    schema_id: Identifier
    payload_schema_version: Annotated[int, Field(ge=1)]
    sha256: Sha256
    size_bytes: Annotated[int, Field(ge=0)]
    media_type: MediaType
    creator: ActorRef
    created_at: UtcRfc3339
    parent_refs: tuple[ArtifactRef, ...] = ()
    supersedes_ref: ArtifactRef | None = None
    task_ref: ArtifactRef | None = None
    labels: dict[Identifier, LabelValue] = Field(default_factory=dict)
    confidentiality: Confidentiality = "project"
    content_encoding: ContentEncoding = "identity"

    _validate_media_type = field_validator("media_type")(
        ArtifactRegistration._validate_media_type.__func__
    )

    @field_validator("created_at")
    @classmethod
    def _validate_created_at(cls, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
        except ValueError as error:
            raise ValueError("created_at must be a valid UTC RFC 3339 timestamp") from error
        if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
            raise ValueError("created_at must use UTC")
        return value

    @model_validator(mode="after")
    def _validate_provenance(self) -> ArtifactEnvelope:
        identities = [_reference_identity(ref) for ref in self.parent_refs]
        if len(identities) != len(set(identities)):
            raise ValueError("parent_refs must be ordered and free of duplicates")
        return self

    @property
    def ref(self) -> ArtifactRef:
        return ArtifactRef(
            artifact_id=self.artifact_id,
            sha256=self.sha256,
            kind=self.kind,
            schema_id=self.schema_id,
        )


class ArtifactEvent(SchemaModel):
    """Append-only journal entry for one artifact registration."""

    event_id: Identifier
    event_type: Literal["artifact_registered"]
    artifact_ref: ArtifactRef
    envelope_sha256: Sha256
    recorded_at: UtcRfc3339

    _validate_recorded_at = field_validator("recorded_at")(
        ArtifactEnvelope._validate_created_at.__func__
    )


def artifact_register_mismatches(
    request: ArtifactRegisterRequest,
    envelope: ArtifactEnvelope,
) -> tuple[str, ...]:
    """Return request fields that do not produce the supplied envelope."""

    mismatches: list[str] = []
    registration = request.registration
    if request.payload_sha256 != envelope.sha256:
        mismatches.append("payload_sha256")
    if request.size_bytes != envelope.size_bytes:
        mismatches.append("size_bytes")
    if (
        registration.artifact_id is not None
        and registration.artifact_id != envelope.artifact_id
    ):
        mismatches.append("artifact_id")
    for field_name in (
        "kind",
        "schema_id",
        "payload_schema_version",
        "media_type",
        "creator",
        "parent_refs",
        "supersedes_ref",
        "task_ref",
        "labels",
        "confidentiality",
        "content_encoding",
    ):
        if getattr(registration, field_name) != getattr(envelope, field_name):
            mismatches.append(field_name)
    return tuple(mismatches)


def _reference_identity(reference: ArtifactRef) -> tuple[str, str, str, str]:
    return (
        reference.artifact_id,
        reference.sha256,
        reference.kind,
        reference.schema_id,
    )


__all__ = [
    "ArtifactEnvelope",
    "ArtifactEvent",
    "ArtifactRegisterRequest",
    "ArtifactRegistration",
    "Confidentiality",
    "ContentEncoding",
    "MediaType",
    "UtcRfc3339",
    "artifact_register_mismatches",
]
