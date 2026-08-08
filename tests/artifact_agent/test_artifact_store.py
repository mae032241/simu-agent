from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from scidiscovery.artifact_agent import (
    ActorRef,
    ArtifactRef,
    ArtifactRegisterRequest,
    ArtifactReferenceError,
    ArtifactRegistration,
    ArtifactService,
    CASConfigurationError,
    CASIntegrityError,
    ContentAddressedStore,
    IdempotencyConflictError,
    RegistryConfigurationError,
    SQLiteArtifactRegistry,
    scan_orphans,
    verify_artifacts,
    canonical_json,
)
from scidiscovery.artifact_agent.storage import IMMUTABLE_TABLES


def _registration(
    artifact_id: str | None = None,
    *,
    parent_refs: tuple[ArtifactRef, ...] = (),
    supersedes_ref: ArtifactRef | None = None,
    task_ref: ArtifactRef | None = None,
    kind: str = "raw_input",
) -> ArtifactRegistration:
    return ArtifactRegistration(
        artifact_id=artifact_id,
        kind=kind,
        schema_id="opaque",
        payload_schema_version=1,
        media_type="application/octet-stream",
        creator=ActorRef(actor_id="agent:root", actor_type="agent"),
        parent_refs=parent_refs,
        supersedes_ref=supersedes_ref,
        task_ref=task_ref,
        labels={"source": "test"},
    )


def _service(tmp_path: Path) -> ArtifactService:
    return ArtifactService.open(
        cas_root=tmp_path / ".artifact-agent" / "artifacts",
        database_path=(
            tmp_path
            / ".artifact-agent"
            / "database"
            / "artifact_agent.sqlite3"
        ),
    )


def test_artifact_schema_is_strict_deeply_frozen_and_validates_metadata() -> None:
    registration = _registration("art_strict")
    assert registration.labels == {"source": "test"}
    with pytest.raises(TypeError, match="FrozenDict is immutable"):
        registration.labels["source"] = "changed"
    with pytest.raises(ValidationError):
        ArtifactRegistration(
            kind="raw",
            schema_id="opaque",
            payload_schema_version="1",
            media_type="application/octet-stream",
            creator=ActorRef(actor_id="agent:root", actor_type="agent"),
        )
    with pytest.raises(ValidationError, match="media_type"):
        ArtifactRegistration(
            kind="raw",
            schema_id="opaque",
            payload_schema_version=1,
            media_type="not-a-media-type",
            creator=ActorRef(actor_id="agent:root", actor_type="agent"),
        )
    with pytest.raises(ValidationError, match="duplicates"):
        _registration(parent_refs=(
            ArtifactRef(
                artifact_id="art_parent",
                sha256="a" * 64,
                kind="raw",
                schema_id="opaque",
            ),
            ArtifactRef(
                artifact_id="art_parent",
                sha256="a" * 64,
                kind="raw",
                schema_id="opaque",
            ),
        ))

    with pytest.raises(ValidationError):
        ArtifactRegisterRequest(
            operation="artifact.create",
            payload_sha256="a" * 64,
            size_bytes=1,
            registration=registration,
        )
    with pytest.raises(ValidationError, match="Extra inputs"):
        ArtifactRegisterRequest(
            operation="artifact.register",
            payload_sha256="a" * 64,
            size_bytes=1,
            registration=registration,
            unexpected=True,
        )


def test_register_catalog_list_read_and_restart_recovery(tmp_path: Path) -> None:
    service = _service(tmp_path)
    payload = b"immutable payload\x00"
    envelope = service.register(
        payload,
        _registration("art_restart"),
        idempotency_key="register-restart",
    )

    assert envelope.artifact_id == "art_restart"
    assert envelope.sha256 == hashlib.sha256(payload).hexdigest()
    assert envelope.size_bytes == len(payload)
    assert service.catalog(envelope.ref) == envelope
    assert service.get_by_id(envelope.artifact_id) == envelope
    assert service.list_artifacts(kind="raw_input") == (envelope,)
    assert service.read(envelope.ref) == payload

    reopened = _service(tmp_path)
    assert reopened.catalog(envelope.ref) == envelope
    assert reopened.read(envelope.ref) == payload
    report = verify_artifacts(reopened.registry, reopened.cas)
    assert report.ok
    assert report.checked_artifacts == report.verified_artifacts == 1


def test_same_idempotency_request_replays_and_different_request_conflicts(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    registration = _registration()
    first = service.register(
        b"same",
        registration,
        idempotency_key="stable-request",
    )
    replay = service.register(
        b"same",
        registration,
        idempotency_key="stable-request",
    )
    assert replay == first
    assert service.list_artifacts() == (first,)

    with pytest.raises(IdempotencyConflictError):
        service.register(
            b"different",
            registration,
            idempotency_key="stable-request",
        )
    assert service.list_artifacts() == (first,)


@pytest.mark.parametrize("relation", ["parent", "supersedes", "task"])
def test_missing_provenance_reference_is_rejected(
    tmp_path: Path,
    relation: str,
) -> None:
    service = _service(tmp_path)
    missing = ArtifactRef(
        artifact_id="art_missing",
        sha256="a" * 64,
        kind="raw_input",
        schema_id="opaque",
    )
    arguments: dict[str, object] = {}
    if relation == "parent":
        arguments["parent_refs"] = (missing,)
    else:
        arguments[f"{relation}_ref"] = missing

    with pytest.raises(ArtifactReferenceError):
        service.register(
            b"unregistered provenance",
            _registration("art_child", **arguments),
            idempotency_key=f"missing-{relation}",
        )
    assert service.list_artifacts() == ()


def test_exact_provenance_is_registered_and_auditable(tmp_path: Path) -> None:
    service = _service(tmp_path)
    parent = service.register(
        b"parent",
        _registration("art_parent"),
        idempotency_key="parent",
    )
    task = service.register(
        b"task",
        _registration("art_task", kind="agent_task"),
        idempotency_key="task",
    )
    child = service.register(
        b"child",
        _registration(
            "art_child",
            parent_refs=(parent.ref,),
            supersedes_ref=parent.ref,
            task_ref=task.ref,
        ),
        idempotency_key="child",
    )

    assert service.catalog(child.ref).parent_refs == (parent.ref,)
    report = verify_artifacts(service.registry, service.cas)
    assert report.ok
    assert report.verified_artifacts == 3

    wrong_hash = ArtifactRef(
        artifact_id=parent.artifact_id,
        sha256="b" * 64,
        kind=parent.kind,
        schema_id=parent.schema_id,
    )
    with pytest.raises(ArtifactReferenceError):
        service.register(
            b"wrong exact reference",
            _registration("art_wrong", parent_refs=(wrong_hash,)),
            idempotency_key="wrong-parent",
        )


def test_payload_tampering_fails_read_and_offline_verify(tmp_path: Path) -> None:
    service = _service(tmp_path)
    envelope = service.register(
        b"original",
        _registration("art_tamper"),
        idempotency_key="tamper",
    )
    path = service.cas.path_for(envelope.sha256)
    path.write_bytes(b"modified")

    with pytest.raises(CASIntegrityError, match="hash mismatch"):
        service.read(envelope.ref)
    report = verify_artifacts(service.registry, service.cas)
    assert not report.ok
    assert {issue.category for issue in report.issues} >= {"payload_integrity"}


def test_immutable_registry_tables_reject_update_and_delete(tmp_path: Path) -> None:
    service = _service(tmp_path)
    parent = service.register(
        b"parent",
        _registration("art_parent"),
        idempotency_key="parent",
    )
    service.register(
        b"child",
        _registration("art_child", parent_refs=(parent.ref,)),
        idempotency_key="child",
    )

    connection = sqlite3.connect(service.registry.database_path)
    try:
        for table in IMMUTABLE_TABLES:
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                connection.execute(f"UPDATE {table} SET rowid = rowid")
            connection.rollback()
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                connection.execute(f"DELETE FROM {table}")
            connection.rollback()
    finally:
        connection.close()


def test_orphan_scan_reports_without_deleting(tmp_path: Path) -> None:
    service = _service(tmp_path)
    registered = service.register(
        b"registered",
        _registration("art_registered"),
        idempotency_key="registered",
    )
    orphan = service.cas.put(b"orphan")

    scan = scan_orphans(service.registry, service.cas)
    assert scan.orphan_digests == (orphan.sha256,)
    assert service.cas.read(orphan.sha256) == b"orphan"
    report = verify_artifacts(service.registry, service.cas)
    assert report.ok
    assert report.orphan_scan.orphan_digests == (orphan.sha256,)
    assert service.read(registered.ref) == b"registered"


def test_cas_root_and_blob_symlinks_are_rejected(tmp_path: Path) -> None:
    actual_root = tmp_path / "actual-root"
    actual_root.mkdir()
    root_link = tmp_path / "root-link"
    root_link.symlink_to(actual_root, target_is_directory=True)
    with pytest.raises(CASConfigurationError, match="symlink"):
        ContentAddressedStore(root_link)

    service = _service(tmp_path / "service")
    payload = b"symlinks are not CAS objects"
    envelope = service.register(
        payload,
        _registration("art_symlink"),
        idempotency_key="symlink",
    )
    blob = service.cas.path_for(envelope.sha256)
    external = tmp_path / "external-payload"
    external.write_bytes(payload)
    blob.unlink()
    blob.symlink_to(external)

    with pytest.raises(CASIntegrityError, match="symlink"):
        service.cas.read(envelope.sha256)
    with pytest.raises(CASIntegrityError, match="symlink"):
        service.cas.verify(envelope.sha256)
    report = verify_artifacts(service.registry, service.cas)
    assert not report.ok
    assert "payload_integrity" in {issue.category for issue in report.issues}
    assert report.orphan_scan.unrecognized_paths


@pytest.mark.parametrize("mutation", ["operation", "extra", "semantics"])
def test_offline_audit_strictly_parses_and_binds_registration_request(
    tmp_path: Path,
    mutation: str,
) -> None:
    service = _service(tmp_path)
    service.register(
        b"request payload",
        _registration("art_request_binding"),
        idempotency_key="request-binding",
    )
    record = service.registry.raw_idempotency_records()[0]
    request = json.loads(record.request_json)
    if mutation == "operation":
        request["operation"] = "artifact.create"
    elif mutation == "extra":
        request["unexpected"] = True
    else:
        request["registration"]["media_type"] = "text/plain"
    request_json = canonical_json(request)

    connection = sqlite3.connect(service.registry.database_path)
    try:
        trigger_sql = connection.execute(
            """
            SELECT sql FROM sqlite_master
            WHERE type = 'trigger'
              AND name = 'idempotency_records_deny_update'
            """
        ).fetchone()[0]
        connection.execute("DROP TRIGGER idempotency_records_deny_update")
        connection.execute(
            """
            UPDATE idempotency_records
            SET request_json = ?, request_sha256 = ?
            """,
            (request_json, hashlib.sha256(request_json).hexdigest()),
        )
        connection.execute(trigger_sql)
        connection.commit()
    finally:
        connection.close()

    report = verify_artifacts(service.registry, service.cas)
    assert not report.ok
    assert "idempotency_integrity" in {
        issue.category for issue in report.issues
    }


def test_registry_rejects_user_version_one_lookalike_schema(tmp_path: Path) -> None:
    database = tmp_path / "database" / "artifact_agent.sqlite3"
    database.parent.mkdir(parents=True)
    connection = sqlite3.connect(database)
    try:
        for table in IMMUTABLE_TABLES:
            connection.execute(f"CREATE TABLE {table} (placeholder TEXT)")
            connection.execute(
                f"""
                CREATE TRIGGER {table}_deny_update
                BEFORE UPDATE ON {table} BEGIN SELECT 1; END
                """
            )
            connection.execute(
                f"""
                CREATE TRIGGER {table}_deny_delete
                BEFORE DELETE ON {table} BEGIN SELECT 1; END
                """
            )
        connection.execute("PRAGMA user_version = 1")
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(RegistryConfigurationError, match="migration contract"):
        SQLiteArtifactRegistry(database)


def test_audit_sanitizes_invalid_long_database_values(tmp_path: Path) -> None:
    service = _service(tmp_path)
    envelope = service.register(
        b"payload",
        _registration("art_before_corruption"),
        idempotency_key="before-corruption",
    )
    invalid_id = "invalid id\n" + "x" * 5000
    envelope_payload = envelope.model_dump(mode="json")
    envelope_payload["artifact_id"] = invalid_id
    envelope_json = canonical_json(envelope_payload)

    connection = sqlite3.connect(service.registry.database_path)
    try:
        trigger_names = (
            "artifact_envelopes_deny_update",
            "artifact_events_deny_update",
            "idempotency_records_deny_update",
        )
        trigger_sql = {
            name: connection.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'trigger' AND name = ?",
                (name,),
            ).fetchone()[0]
            for name in trigger_names
        }
        for name in trigger_names:
            connection.execute(f"DROP TRIGGER {name}")
        connection.execute(
            """
            UPDATE artifact_envelopes
            SET artifact_id = ?, envelope_json = ?, envelope_sha256 = ?
            """,
            (invalid_id, envelope_json, hashlib.sha256(envelope_json).hexdigest()),
        )
        connection.execute(
            "UPDATE artifact_events SET artifact_id = ?",
            (invalid_id,),
        )
        connection.execute(
            "UPDATE idempotency_records SET artifact_id = ?",
            (invalid_id,),
        )
        for name in trigger_names:
            connection.execute(trigger_sql[name])
        connection.commit()
    finally:
        connection.close()

    report = verify_artifacts(service.registry, service.cas)
    assert not report.ok
    assert report.issues
    assert all(len(issue.detail) <= 2048 for issue in report.issues)
    assert any(issue.artifact_id is None for issue in report.issues)
    assert "\n" not in "".join(issue.detail for issue in report.issues)
