from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from scidiscovery.artifact_agent import (
    ActorRef,
    ArtifactIdentityConflictError,
    ArtifactRegistration,
    ArtifactService,
    ContentAddressedStore,
    IdempotencyConflictError,
    verify_artifacts,
)


def _service(tmp_path: Path) -> ArtifactService:
    return ArtifactService.open(
        cas_root=tmp_path / "artifacts",
        database_path=tmp_path / "database" / "artifact_agent.sqlite3",
    )


def _registration(artifact_id: str | None = None) -> ArtifactRegistration:
    return ArtifactRegistration(
        artifact_id=artifact_id,
        kind="concurrency_fixture",
        schema_id="opaque",
        payload_schema_version=1,
        media_type="application/octet-stream",
        creator=ActorRef(actor_id="service:test", actor_type="service"),
    )


def test_fifty_concurrent_identical_cas_writes_publish_one_blob(
    tmp_path: Path,
) -> None:
    cas = ContentAddressedStore(tmp_path / "artifacts")
    payload = b"one physical blob" * 1024
    with ThreadPoolExecutor(max_workers=16) as executor:
        objects = list(executor.map(lambda _: cas.put(payload), range(50)))

    assert len({item.sha256 for item in objects}) == 1
    assert len(cas.iter_digests()) == 1
    assert not tuple((tmp_path / "artifacts").rglob(".*.*"))
    assert cas.read(objects[0].sha256) == payload


def test_fifty_concurrent_idempotent_registrations_return_one_artifact(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    registration = _registration()
    with ThreadPoolExecutor(max_workers=16) as executor:
        envelopes = list(
            executor.map(
                lambda _: service.register(
                    b"same request",
                    registration,
                    idempotency_key="one-logical-request",
                ),
                range(50),
            )
        )

    assert len({envelope.artifact_id for envelope in envelopes}) == 1
    assert len(service.cas.iter_digests()) == 1
    assert len(service.registry.raw_envelopes()) == 1
    assert len(service.registry.raw_events()) == 1
    assert len(service.registry.raw_idempotency_records()) == 1
    assert verify_artifacts(service.registry, service.cas).ok


def test_fifty_logical_artifacts_can_share_one_payload_blob(tmp_path: Path) -> None:
    service = _service(tmp_path)

    def register(index: int) -> str:
        envelope = service.register(
            b"shared bytes",
            _registration(f"art_concurrent_{index:02d}"),
            idempotency_key=f"request-{index:02d}",
        )
        return envelope.artifact_id

    with ThreadPoolExecutor(max_workers=16) as executor:
        artifact_ids = list(executor.map(register, range(50)))

    assert len(set(artifact_ids)) == 50
    assert len(service.cas.iter_digests()) == 1
    assert len(service.registry.raw_envelopes()) == 50
    report = verify_artifacts(service.registry, service.cas)
    assert report.ok
    assert report.verified_artifacts == 50


def test_concurrent_same_artifact_id_fails_closed(tmp_path: Path) -> None:
    service = _service(tmp_path)

    def register(index: int) -> str:
        return service.register(
            f"payload-{index}".encode(),
            _registration("art_single_identity"),
            idempotency_key=f"identity-{index}",
        ).artifact_id

    successes: list[str] = []
    conflicts = 0
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(register, index) for index in range(8)]
        for future in futures:
            try:
                successes.append(future.result())
            except ArtifactIdentityConflictError:
                conflicts += 1

    assert successes == ["art_single_identity"]
    assert conflicts == 7
    assert len(service.registry.raw_envelopes()) == 1
    assert verify_artifacts(service.registry, service.cas).ok


def test_concurrent_idempotency_key_reuse_with_different_bytes_conflicts(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)

    def register(payload: bytes) -> bytes:
        envelope = service.register(
            payload,
            _registration(),
            idempotency_key="contended-key",
        )
        return service.read(envelope.ref)

    results: list[bytes] = []
    conflicts = 0
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(register, payload) for payload in (b"a", b"b")]
        for future in futures:
            try:
                results.append(future.result())
            except IdempotencyConflictError:
                conflicts += 1

    assert len(results) == 1
    assert conflicts == 1
    assert len(service.registry.raw_envelopes()) == 1
    assert verify_artifacts(service.registry, service.cas).ok


def test_audit_uses_one_registry_snapshot_when_registration_commits_mid_scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(tmp_path)
    original = service.register(
        b"snapshot original",
        _registration("art_snapshot_original"),
        idempotency_key="snapshot-original",
    )
    take_snapshot = service.registry.audit_snapshot
    inserted: list[object] = []

    def snapshot_then_commit() -> object:
        snapshot = take_snapshot()
        inserted.append(
            service.register(
                b"committed after snapshot",
                _registration("art_snapshot_later"),
                idempotency_key="snapshot-later",
            )
        )
        return snapshot

    monkeypatch.setattr(service.registry, "audit_snapshot", snapshot_then_commit)
    report = verify_artifacts(service.registry, service.cas)

    assert report.ok
    assert report.checked_artifacts == report.verified_artifacts == 1
    assert service.read(original.ref) == b"snapshot original"
    later = inserted[0]
    assert report.orphan_scan.orphan_digests == (later.sha256,)
    assert len(service.registry.raw_envelopes()) == 2
