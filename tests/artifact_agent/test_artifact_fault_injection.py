from __future__ import annotations

import errno
import hashlib
import os
import sqlite3
import stat
from pathlib import Path

import pytest

from scidiscovery.artifact_agent import (
    ActorRef,
    ArtifactRegistration,
    ArtifactService,
    CASIntegrityError,
    ContentAddressedStore,
    scan_orphans,
    verify_artifacts,
)


def _service(tmp_path: Path) -> ArtifactService:
    return ArtifactService.open(
        cas_root=tmp_path / "artifacts",
        database_path=tmp_path / "database" / "artifact_agent.sqlite3",
    )


def _registration(artifact_id: str) -> ArtifactRegistration:
    return ArtifactRegistration(
        artifact_id=artifact_id,
        kind="fault_fixture",
        schema_id="opaque",
        payload_schema_version=1,
        media_type="application/octet-stream",
        creator=ActorRef(actor_id="service:test", actor_type="service"),
    )


def test_cas_publication_interruption_creates_no_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(tmp_path)

    def interrupted(_temporary: Path, _destination: Path) -> None:
        raise OSError("injected publication interruption")

    monkeypatch.setattr(service.cas, "_publish", interrupted)
    with pytest.raises(OSError, match="injected"):
        service.register(
            b"never published",
            _registration("art_interrupted"),
            idempotency_key="interrupted",
        )

    assert service.registry.raw_envelopes() == ()
    assert service.registry.raw_events() == ()
    assert service.registry.raw_idempotency_records() == ()
    assert service.cas.iter_digests() == ()
    assert not tuple((tmp_path / "artifacts").rglob(".*.*"))


def test_bad_bytes_published_during_cas_write_are_not_registered(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(tmp_path)

    def corrupt_publish(_temporary: Path, destination: Path) -> None:
        destination.write_bytes(b"corrupt")

    monkeypatch.setattr(service.cas, "_publish", corrupt_publish)
    with pytest.raises(CASIntegrityError):
        service.register(
            b"expected",
            _registration("art_bad_publish"),
            idempotency_key="bad-publish",
        )

    assert service.registry.raw_envelopes() == ()
    assert service.registry.raw_events() == ()
    assert service.registry.raw_idempotency_records() == ()


def test_sqlite_commit_failure_rolls_back_registry_and_leaves_reportable_orphan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(tmp_path)

    def fail_commit(_connection: sqlite3.Connection) -> None:
        raise sqlite3.OperationalError("database or disk is full")

    monkeypatch.setattr(service.registry, "_commit", fail_commit)
    with pytest.raises(sqlite3.OperationalError, match="database or disk is full"):
        service.register(
            b"durable before database",
            _registration("art_commit_failure"),
            idempotency_key="commit-failure",
        )

    assert service.registry.raw_envelopes() == ()
    assert service.registry.raw_links() == ()
    assert service.registry.raw_events() == ()
    assert service.registry.raw_idempotency_records() == ()
    scan = scan_orphans(service.registry, service.cas)
    assert len(scan.orphan_digests) == 1
    orphan_path = service.cas.path_for(scan.orphan_digests[0])
    assert orphan_path.exists()
    assert verify_artifacts(service.registry, service.cas).ok
    assert orphan_path.exists(), "audit must not delete orphan payloads"


def test_commit_failure_for_deduplicated_bytes_keeps_existing_artifact_valid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(tmp_path)
    existing = service.register(
        b"shared",
        _registration("art_existing"),
        idempotency_key="existing",
    )

    def fail_commit(_connection: sqlite3.Connection) -> None:
        raise sqlite3.OperationalError("injected commit failure")

    monkeypatch.setattr(service.registry, "_commit", fail_commit)
    with pytest.raises(sqlite3.OperationalError):
        service.register(
            b"shared",
            _registration("art_failed"),
            idempotency_key="failed",
        )

    assert service.read(existing.ref) == b"shared"
    assert len(service.registry.raw_envelopes()) == 1
    assert scan_orphans(service.registry, service.cas).orphan_digests == ()
    assert verify_artifacts(service.registry, service.cas).ok


def test_missing_cas_blob_is_integrity_failure_after_restart(tmp_path: Path) -> None:
    service = _service(tmp_path)
    envelope = service.register(
        b"payload",
        _registration("art_missing_blob"),
        idempotency_key="missing-blob",
    )
    service.cas.path_for(envelope.sha256).unlink()

    reopened = _service(tmp_path)
    with pytest.raises(CASIntegrityError, match="missing"):
        reopened.read(envelope.ref)
    report = verify_artifacts(reopened.registry, reopened.cas)
    assert not report.ok
    assert report.orphan_scan.missing_digests == (envelope.sha256,)
    assert {issue.category for issue in report.issues} >= {
        "payload_integrity",
        "payload_missing",
    }


def test_existing_corrupt_cas_address_rejects_new_registration(tmp_path: Path) -> None:
    service = _service(tmp_path)
    payload = b"expected"
    digest = service.cas.put(payload).sha256
    service.cas.path_for(digest).write_bytes(b"corrupt")

    with pytest.raises(CASIntegrityError):
        service.register(
            payload,
            _registration("art_corrupt_existing"),
            idempotency_key="corrupt-existing",
        )
    assert service.registry.raw_envelopes() == ()


def test_new_cas_directories_fsync_each_parent_before_blob_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Path] = []

    def record_fsync(_cls: type[ContentAddressedStore], directory: Path) -> None:
        calls.append(directory)

    monkeypatch.setattr(
        ContentAddressedStore,
        "_fsync_directory",
        classmethod(record_fsync),
    )
    root = tmp_path / "new-parent" / "artifacts"
    cas = ContentAddressedStore(root)
    result = cas.put(b"durable ordering")
    prefix = cas.path_for(result.sha256).parent

    assert calls == [
        tmp_path,
        tmp_path / "new-parent",
        root,
        root / "sha256",
        prefix,
    ]


def test_temp_write_enospc_leaves_no_blob_or_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(tmp_path)

    def disk_full(descriptor: int, _content: bytes) -> None:
        os.write(descriptor, b"partial")
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(service.cas, "_write_temporary", disk_full)
    with pytest.raises(OSError) as raised:
        service.register(
            b"will not fit",
            _registration("art_write_enospc"),
            idempotency_key="write-enospc",
        )
    assert raised.value.errno == errno.ENOSPC
    assert service.cas.iter_digests() == ()
    assert service.registry.raw_envelopes() == ()
    assert service.registry.raw_events() == ()


def test_temp_file_fsync_enospc_leaves_no_blob_or_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(tmp_path)
    real_fsync = os.fsync

    def disk_full(descriptor: int) -> None:
        if stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError(errno.ENOSPC, "No space left on device")
        real_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", disk_full)
    with pytest.raises(OSError) as raised:
        service.register(
            b"fsync will fail",
            _registration("art_fsync_enospc"),
            idempotency_key="fsync-enospc",
        )
    assert raised.value.errno == errno.ENOSPC
    assert service.cas.iter_digests() == ()
    assert service.registry.raw_envelopes() == ()


def test_directory_fsync_enospc_leaves_only_reportable_orphan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(tmp_path)
    payload = b"published before directory fsync"
    digest = hashlib.sha256(payload).hexdigest()
    prefix = service.cas.path_for(digest).parent
    real_fsync_directory = service.cas._fsync_directory

    def disk_full(directory: Path) -> None:
        if directory == prefix:
            raise OSError(errno.ENOSPC, "No space left on device")
        real_fsync_directory(directory)

    monkeypatch.setattr(service.cas, "_fsync_directory", disk_full)
    with pytest.raises(OSError) as raised:
        service.register(
            payload,
            _registration("art_directory_enospc"),
            idempotency_key="directory-enospc",
        )
    assert raised.value.errno == errno.ENOSPC
    assert service.registry.raw_envelopes() == ()
    scan = scan_orphans(service.registry, service.cas)
    assert scan.orphan_digests == (digest,)
    assert service.cas.read(digest) == payload
    assert verify_artifacts(service.registry, service.cas).ok
