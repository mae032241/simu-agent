"""Offline verification and non-destructive orphan reporting."""

from __future__ import annotations

import hashlib
import re
import sqlite3
from collections import Counter, defaultdict
from collections.abc import Callable
from typing import Annotated

from pydantic import Field, ValidationError

from .schema.artifact import (
    ArtifactEnvelope,
    ArtifactEvent,
    ArtifactRegisterRequest,
    artifact_register_mismatches,
)
from .schema.common import Identifier, SchemaModel, Sha256
from .schema.refs import ArtifactRef
from .storage.cas import CASIntegrityError, ContentAddressedStore
from .storage.sqlite import (
    RawEnvelopeRecord,
    RegistryConfigurationError,
    RegistryIntegrityError,
    SQLiteArtifactRegistry,
)


class AuditIssue(SchemaModel):
    category: Identifier
    detail: Annotated[str, Field(min_length=1, max_length=2048)]
    artifact_id: Identifier | None = None


class OrphanScanReport(SchemaModel):
    referenced_digests: Annotated[int, Field(ge=0)]
    cas_digests: Annotated[int, Field(ge=0)]
    orphan_digests: tuple[Sha256, ...]
    missing_digests: tuple[Sha256, ...]
    invalid_referenced_digests: tuple[str, ...]
    unrecognized_paths: tuple[str, ...]


class ArtifactVerificationReport(SchemaModel):
    checked_artifacts: Annotated[int, Field(ge=0)]
    verified_artifacts: Annotated[int, Field(ge=0)]
    checked_events: Annotated[int, Field(ge=0)]
    checked_idempotency_records: Annotated[int, Field(ge=0)]
    orphan_scan: OrphanScanReport
    issues: tuple[AuditIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues


def scan_orphans(
    registry: SQLiteArtifactRegistry,
    cas: ContentAddressedStore,
) -> OrphanScanReport:
    """Compare registry addresses with CAS paths without deleting anything."""

    snapshot = registry.audit_snapshot()
    return _scan_orphans(snapshot.referenced_digests, cas)


def _scan_orphans(
    referenced: frozenset[object],
    cas: ContentAddressedStore,
) -> OrphanScanReport:
    valid_referenced = frozenset(
        digest
        for digest in referenced
        if type(digest) is str
        and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
    )
    present = frozenset(cas.iter_digests())
    invalid_paths = tuple(
        str(path.relative_to(cas.root))
        for path in cas.iter_unrecognized_paths()
    )
    return OrphanScanReport(
        referenced_digests=len(referenced),
        cas_digests=len(present),
        orphan_digests=tuple(sorted(present - valid_referenced)),
        missing_digests=tuple(sorted(valid_referenced - present)),
        invalid_referenced_digests=tuple(
            sorted(_safe_detail(value) for value in referenced - valid_referenced)
        ),
        unrecognized_paths=invalid_paths,
    )


def verify_artifacts(
    registry: SQLiteArtifactRegistry,
    cas: ContentAddressedStore,
) -> ArtifactVerificationReport:
    """Fully verify payloads, envelopes, journal entries, and direct provenance."""

    issues: list[AuditIssue] = []
    invalid_artifacts: set[str] = set()

    def report(
        category: object,
        detail: object,
        artifact_id: object | None = None,
    ) -> None:
        safe_category = _safe_identifier(category) or "audit_issue"
        safe_artifact_id = _safe_identifier(artifact_id)
        issues.append(
            AuditIssue(
                category=safe_category,
                detail=_safe_detail(detail),
                artifact_id=safe_artifact_id,
            )
        )
        if safe_artifact_id is not None:
            invalid_artifacts.add(safe_artifact_id)

    try:
        snapshot = registry.audit_snapshot()
        if snapshot.integrity != "ok":
            report("registry_integrity", snapshot.integrity)
        envelopes_raw = snapshot.envelopes
        links_raw = snapshot.links
        events_raw = snapshot.events
        idempotency_raw = snapshot.idempotency_records
    except (
        sqlite3.DatabaseError,
        RegistryConfigurationError,
        RegistryIntegrityError,
        TypeError,
        ValueError,
    ) as error:
        report("registry_unreadable", str(error))
        empty_scan = OrphanScanReport(
            referenced_digests=0,
            cas_digests=len(cas.iter_digests()),
            orphan_digests=cas.iter_digests(),
            missing_digests=(),
            invalid_referenced_digests=(),
            unrecognized_paths=tuple(
                str(path.relative_to(cas.root))
                for path in cas.iter_unrecognized_paths()
            ),
        )
        return ArtifactVerificationReport(
            checked_artifacts=0,
            verified_artifacts=0,
            checked_events=0,
            checked_idempotency_records=0,
            orphan_scan=empty_scan,
            issues=tuple(issues),
        )

    envelopes: dict[str, ArtifactEnvelope] = {}
    envelope_hashes: dict[str, str] = {}
    for row in envelopes_raw:
        envelope = _decode_envelope(row, report)
        if envelope is None:
            continue
        envelopes[envelope.artifact_id] = envelope
        envelope_hashes[envelope.artifact_id] = hashlib.sha256(
            row.envelope_json
        ).hexdigest()
        try:
            cas.verify(envelope.sha256, expected_size=envelope.size_bytes)
        except (CASIntegrityError, OSError) as error:
            report("payload_integrity", str(error), envelope.artifact_id)

    exact_refs = {
        _reference_identity(envelope.ref): envelope.artifact_id
        for envelope in envelopes.values()
    }
    for envelope in envelopes.values():
        for reference in _direct_references(envelope):
            if _reference_identity(reference) not in exact_refs:
                report(
                    "provenance_missing",
                    f"exact reference is absent: {reference.artifact_id}",
                    envelope.artifact_id,
                )

    actual_links: dict[str, list[tuple[str, int, str, str, str, str]]] = (
        defaultdict(list)
    )
    for link in links_raw:
        actual_links[link.source_artifact_id].append(
            (
                link.relation,
                link.position,
                link.target_artifact_id,
                link.target_sha256,
                link.target_kind,
                link.target_schema_id,
            )
        )
    for envelope in envelopes.values():
        expected_links = _expected_links(envelope)
        if sorted(actual_links.pop(envelope.artifact_id, [])) != sorted(expected_links):
            report(
                "provenance_journal",
                "artifact_links do not match canonical envelope provenance",
                envelope.artifact_id,
            )
    for unknown_source in actual_links:
        report(
            "provenance_journal",
            f"artifact_links has unknown source: {unknown_source}",
        )

    event_counts: Counter[str] = Counter()
    for row in events_raw:
        event_counts[row.artifact_id] += 1
        try:
            if type(row.event_json) is not bytes:
                raise ValueError("event_json is not bytes")
            if hashlib.sha256(row.event_json).hexdigest() != row.event_sha256:
                raise ValueError("event hash mismatch")
            event = ArtifactEvent.model_validate_json(row.event_json, strict=True)
            if event.canonical_json() != row.event_json:
                raise ValueError("event JSON is not canonical")
            if (
                event.event_id != row.event_id
                or event.event_type != row.event_type
                or event.recorded_at != row.recorded_at
                or event.artifact_ref.artifact_id != row.artifact_id
            ):
                raise ValueError("event columns disagree with event bytes")
            envelope = envelopes.get(row.artifact_id)
            if envelope is None or event.artifact_ref != envelope.ref:
                raise ValueError("event does not resolve to its exact envelope")
            if event.envelope_sha256 != envelope_hashes[row.artifact_id]:
                raise ValueError("event envelope hash is incorrect")
        except (ValidationError, ValueError) as error:
            report("event_integrity", str(error), row.artifact_id)

    idempotency_counts: Counter[str] = Counter()
    for row in idempotency_raw:
        idempotency_counts[row.artifact_id] += 1
        try:
            if type(row.request_json) is not bytes:
                raise ValueError("idempotency request is not bytes")
            if re.fullmatch(r"[0-9a-f]{64}", row.request_sha256) is None:
                raise ValueError("idempotency request hash is invalid")
            if hashlib.sha256(row.request_json).hexdigest() != row.request_sha256:
                raise ValueError("idempotency request hash mismatch")
            request = ArtifactRegisterRequest.model_validate_json(
                row.request_json,
                strict=True,
            )
            if request.canonical_json() != row.request_json:
                raise ValueError("idempotency request JSON is not canonical")
            if type(row.response_json) is not bytes:
                raise ValueError("idempotency response is not bytes")
            if hashlib.sha256(row.response_json).hexdigest() != row.response_sha256:
                raise ValueError("idempotency response hash mismatch")
            response = ArtifactEnvelope.model_validate_json(
                row.response_json,
                strict=True,
            )
            if response.canonical_json() != row.response_json:
                raise ValueError("idempotency response JSON is not canonical")
            envelope = envelopes.get(row.artifact_id)
            if envelope is None or response != envelope:
                raise ValueError("idempotency response does not match its envelope")
            mismatches = artifact_register_mismatches(request, response)
            if mismatches:
                raise ValueError(
                    "idempotency request does not produce response fields: "
                    + ", ".join(mismatches)
                )
        except (ValidationError, ValueError) as error:
            report("idempotency_integrity", str(error), row.artifact_id)

    for artifact_id in envelopes:
        if event_counts[artifact_id] != 1:
            report(
                "event_cardinality",
                f"expected one registration event, found {event_counts[artifact_id]}",
                artifact_id,
            )
        if idempotency_counts[artifact_id] != 1:
            report(
                "idempotency_cardinality",
                "expected one idempotency record, "
                f"found {idempotency_counts[artifact_id]}",
                artifact_id,
            )

    orphan_report = _scan_orphans(snapshot.referenced_digests, cas)
    for digest in orphan_report.missing_digests:
        for envelope in envelopes.values():
            if envelope.sha256 == digest:
                report(
                    "payload_missing",
                    f"registry digest is absent from CAS: {digest}",
                    envelope.artifact_id,
                )
    for digest in orphan_report.invalid_referenced_digests:
        report(
            "registry_digest",
            f"registry contains an invalid payload digest: {digest}",
        )
    for path in orphan_report.unrecognized_paths:
        report("cas_layout", f"unrecognized CAS path: {path}")

    return ArtifactVerificationReport(
        checked_artifacts=len(envelopes_raw),
        verified_artifacts=max(0, len(envelopes) - len(invalid_artifacts)),
        checked_events=len(events_raw),
        checked_idempotency_records=len(idempotency_raw),
        orphan_scan=orphan_report,
        issues=tuple(issues),
    )


def _decode_envelope(
    row: RawEnvelopeRecord,
    report: Callable[[object, object, object | None], None],
) -> ArtifactEnvelope | None:
    try:
        if type(row.envelope_json) is not bytes:
            raise ValueError("envelope_json is not bytes")
        if hashlib.sha256(row.envelope_json).hexdigest() != row.envelope_sha256:
            raise ValueError("envelope registry hash mismatch")
        envelope = ArtifactEnvelope.model_validate_json(
            row.envelope_json,
            strict=True,
        )
        if envelope.canonical_json() != row.envelope_json:
            raise ValueError("envelope JSON is not canonical")
        expected = (
            envelope.artifact_id,
            envelope.sha256,
            envelope.size_bytes,
            envelope.kind,
            envelope.schema_id,
            envelope.payload_schema_version,
            envelope.media_type,
            envelope.created_at,
        )
        actual = (
            row.artifact_id,
            row.payload_sha256,
            row.size_bytes,
            row.kind,
            row.schema_id,
            row.payload_schema_version,
            row.media_type,
            row.created_at,
        )
        if actual != expected:
            raise ValueError("envelope columns disagree with envelope bytes")
        return envelope
    except (ValidationError, ValueError) as error:
        report("envelope_integrity", str(error), row.artifact_id)
        return None


def _safe_identifier(value: object) -> str | None:
    if (
        type(value) is str
        and 1 <= len(value) <= 256
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]*", value) is not None
    ):
        return value
    return None


def _safe_detail(value: object) -> str:
    try:
        text = str(value)
    except Exception:
        text = f"unprintable {type(value).__name__}"
    escaped = text.encode("unicode_escape", "backslashreplace").decode("ascii")
    if not escaped:
        escaped = "audit issue"
    if len(escaped) > 2048:
        escaped = escaped[:2045] + "..."
    return escaped


def _reference_identity(reference: ArtifactRef) -> tuple[str, str, str, str]:
    return (
        reference.artifact_id,
        reference.sha256,
        reference.kind,
        reference.schema_id,
    )


def _direct_references(envelope: ArtifactEnvelope) -> tuple[ArtifactRef, ...]:
    references = list(envelope.parent_refs)
    if envelope.supersedes_ref is not None:
        references.append(envelope.supersedes_ref)
    if envelope.task_ref is not None:
        references.append(envelope.task_ref)
    return tuple(references)


def _expected_links(
    envelope: ArtifactEnvelope,
) -> list[tuple[str, int, str, str, str, str]]:
    links = [
        (
            "parent",
            position,
            reference.artifact_id,
            reference.sha256,
            reference.kind,
            reference.schema_id,
        )
        for position, reference in enumerate(envelope.parent_refs)
    ]
    for relation, reference in (
        ("supersedes", envelope.supersedes_ref),
        ("task", envelope.task_ref),
    ):
        if reference is not None:
            links.append(
                (
                    relation,
                    0,
                    reference.artifact_id,
                    reference.sha256,
                    reference.kind,
                    reference.schema_id,
                )
            )
    return links


__all__ = [
    "ArtifactVerificationReport",
    "AuditIssue",
    "OrphanScanReport",
    "scan_orphans",
    "verify_artifacts",
]
