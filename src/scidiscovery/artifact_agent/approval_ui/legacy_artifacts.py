"""Read immutable pre-Run Artifact envelopes only inside the approval UI."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Literal

from pydantic import ValidationError

from ..schema.artifact import ArtifactEnvelope
from ..schema.refs import ArtifactRef
from ..storage.sqlite import RegistryIntegrityError, SQLiteArtifactRegistry


class LegacyUIArtifactEnvelope(ArtifactEnvelope):
    task_ref: ArtifactRef | None = None
    confidentiality: Literal["project", "task_private", "approval_only"] = "project"


class UIReadableArtifactRegistry(SQLiteArtifactRegistry):
    @staticmethod
    def _decode_envelope_row(row: sqlite3.Row) -> ArtifactEnvelope:
        raw = row["envelope_json"]
        if type(raw) is not bytes:
            return SQLiteArtifactRegistry._decode_envelope_row(row)
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            return SQLiteArtifactRegistry._decode_envelope_row(row)
        if not isinstance(value, dict) or "task_ref" not in value:
            return SQLiteArtifactRegistry._decode_envelope_row(row)
        if hashlib.sha256(raw).hexdigest() != row["envelope_sha256"]:
            raise RegistryIntegrityError("envelope registry hash mismatch")
        try:
            envelope = LegacyUIArtifactEnvelope.model_validate_json(raw, strict=True)
        except ValidationError as error:
            raise RegistryIntegrityError("legacy envelope schema validation failed") from error
        if envelope.canonical_json() != raw:
            raise RegistryIntegrityError("legacy envelope JSON is not canonical")
        columns = ("artifact_id", "payload_sha256", "size_bytes", "kind", "schema_id",
            "payload_schema_version", "media_type", "created_at")
        expected = (envelope.artifact_id, envelope.sha256, envelope.size_bytes,
            envelope.kind, envelope.schema_id, envelope.payload_schema_version,
            envelope.media_type, envelope.created_at)
        if tuple(row[name] for name in columns) != expected:
            raise RegistryIntegrityError("envelope columns disagree with envelope bytes")
        return envelope
