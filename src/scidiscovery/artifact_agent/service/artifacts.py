"""High-level registration, catalog, and verified-read API for Artifacts."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..schema.artifact import (
    ArtifactEnvelope,
    ArtifactEvent,
    ArtifactRegisterRequest,
    ArtifactRegistration,
)
from ..schema.refs import ArtifactRef
from ..storage.cas import ContentAddressedStore
from ..storage.sqlite import SQLiteArtifactRegistry


class ArtifactService:
    """Coordinates bytes-first CAS durability with append-only registration."""

    def __init__(
        self,
        cas: ContentAddressedStore,
        registry: SQLiteArtifactRegistry,
    ) -> None:
        if not isinstance(cas, ContentAddressedStore):
            raise TypeError("cas must be a ContentAddressedStore")
        if not isinstance(registry, SQLiteArtifactRegistry):
            raise TypeError("registry must be a SQLiteArtifactRegistry")
        self.cas = cas
        self.registry = registry

    @classmethod
    def open(
        cls,
        *,
        cas_root: Path | str,
        database_path: Path | str,
        shared_group: bool = False,
    ) -> ArtifactService:
        # Validate/open the registry before creating the CAS directory.
        registry = SQLiteArtifactRegistry(database_path)
        return cls(
            ContentAddressedStore(
                cas_root,
                file_mode=0o640 if shared_group else 0o600,
                directory_mode=0o770 if shared_group else 0o700,
            ),
            registry,
        )

    def register(
        self,
        content: bytes,
        registration: ArtifactRegistration,
        *,
        idempotency_key: str,
    ) -> ArtifactEnvelope:
        if type(content) is not bytes:
            raise TypeError("artifact content must be bytes")
        if not isinstance(registration, ArtifactRegistration):
            raise TypeError("registration must be an ArtifactRegistration")

        cas_object = self.cas.put(content)
        # Full read after CAS publication, before any registry transaction.
        self.cas.verify(cas_object.sha256, expected_size=cas_object.size_bytes)
        request = ArtifactRegisterRequest(
            operation="artifact.register",
            payload_sha256=cas_object.sha256,
            size_bytes=cas_object.size_bytes,
            registration=registration,
        )
        request_json = request.canonical_json()
        request_sha256 = hashlib.sha256(request_json).hexdigest()
        created_at = _utc_now()
        envelope = ArtifactEnvelope(
            artifact_id=registration.artifact_id or f"art_{uuid.uuid4().hex}",
            kind=registration.kind,
            schema_id=registration.schema_id,
            payload_schema_version=registration.payload_schema_version,
            sha256=cas_object.sha256,
            size_bytes=cas_object.size_bytes,
            media_type=registration.media_type,
            creator=registration.creator,
            created_at=created_at,
            parent_refs=registration.parent_refs,
            supersedes_ref=registration.supersedes_ref,
            task_ref=registration.task_ref,
            labels=registration.labels,
            confidentiality=registration.confidentiality,
            content_encoding=registration.content_encoding,
        )
        event = ArtifactEvent(
            event_id=f"evt_{uuid.uuid4().hex}",
            event_type="artifact_registered",
            artifact_ref=envelope.ref,
            envelope_sha256=envelope.content_hash,
            recorded_at=created_at,
        )
        result = self.registry.register(
            envelope,
            event,
            idempotency_key=idempotency_key,
            request_json=request_json,
            request_sha256=request_sha256,
            verify_payload=lambda: self.cas.verify(
                cas_object.sha256,
                expected_size=cas_object.size_bytes,
            ),
        )
        # Replays return the original envelope. Recheck its declared bytes before
        # returning it to the caller.
        self.cas.verify(result.sha256, expected_size=result.size_bytes)
        return result

    def catalog(self, reference: ArtifactRef) -> ArtifactEnvelope:
        """Resolve one exact immutable reference without reading its payload."""

        return self.registry.resolve(reference)

    def get_by_id(self, artifact_id: str) -> ArtifactEnvelope:
        """Look up catalog metadata by globally unique logical ID."""

        return self.registry.get_by_id(artifact_id)

    def list_artifacts(
        self,
        *,
        kind: str | None = None,
        schema_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[ArtifactEnvelope, ...]:
        return self.registry.list_artifacts(
            kind=kind,
            schema_id=schema_id,
            limit=limit,
            offset=offset,
        )

    def read(self, reference: ArtifactRef) -> bytes:
        """Resolve exact metadata and fully re-hash payload bytes before return."""

        envelope = self.registry.resolve(reference)
        return self.cas.read(envelope.sha256, expected_size=envelope.size_bytes)

    def verify(self, reference: ArtifactRef) -> ArtifactEnvelope:
        envelope = self.registry.resolve(reference)
        self.cas.verify(envelope.sha256, expected_size=envelope.size_bytes)
        return envelope


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


__all__ = ["ArtifactService"]
