from __future__ import annotations

import hashlib
import sqlite3

import pytest

from scidiscovery.artifact_agent.audit import verify_artifacts
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.refs import ActorRef
from scidiscovery.artifact_agent.service.artifacts import ArtifactService
from scidiscovery.artifact_agent.storage.sqlite import RegistryConfigurationError


_RETIRED_EVENT_SQL = """
CREATE TABLE artifact_events (
    event_id TEXT PRIMARY KEY,
    artifact_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK(event_type = 'artifact_registered'),
    recorded_at TEXT NOT NULL,
    event_json BLOB NOT NULL,
    event_sha256 TEXT NOT NULL CHECK(length(event_sha256) = 64),
    UNIQUE (artifact_id, event_type),
    FOREIGN KEY (artifact_id) REFERENCES artifact_envelopes(artifact_id)
);
CREATE TRIGGER artifact_events_deny_update
BEFORE UPDATE ON artifact_events BEGIN
    SELECT RAISE(ABORT, 'artifact_events is append-only');
END;
CREATE TRIGGER artifact_events_deny_delete
BEFORE DELETE ON artifact_events BEGIN
    SELECT RAISE(ABORT, 'artifact_events is append-only');
END;
"""


def _service(tmp_path) -> ArtifactService:
    return ArtifactService.open(
        cas_root=tmp_path / "cas",
        database_path=tmp_path / "registry.sqlite3",
    )


def _register(
    service: ArtifactService,
    *,
    name: str,
    content: bytes,
    parent_refs=(),
):
    return service.register(
        content,
        ArtifactRegistration(
            artifact_id=f"art_{name}",
            kind="audit_fixture",
            schema_id="audit.fixture.v1",
            payload_schema_version=1,
            media_type="application/octet-stream",
            creator=ActorRef(actor_id="audit_test", actor_type="service"),
            parent_refs=parent_refs,
        ),
        idempotency_key=f"audit:{name}",
    )


def _replace_immutable_value(
    database,
    *,
    table: str,
    update_sql: str,
    parameters: tuple[object, ...],
) -> None:
    trigger = f"{table}_deny_update"
    with sqlite3.connect(database) as connection:
        connection.execute(f"DROP TRIGGER {trigger}")
        connection.execute(update_sql, parameters)
        connection.execute(
            f"""
            CREATE TRIGGER {trigger}
            BEFORE UPDATE ON {table} BEGIN
                SELECT RAISE(ABORT, '{table} is append-only');
            END
            """
        )


def _categories(report) -> set[str]:
    return {issue.category for issue in report.issues}


def test_audit_accepts_exact_payload_envelope_parent_and_idempotency(tmp_path) -> None:
    service = _service(tmp_path)
    parent = _register(service, name="parent", content=b"parent")
    _register(service, name="child", content=b"child", parent_refs=(parent.ref,))

    report = verify_artifacts(service.registry, service.cas)

    assert report.ok
    assert report.checked_artifacts == 2
    assert report.verified_artifacts == 2
    assert report.checked_idempotency_records == 2
    assert report.orphan_scan.orphan_digests == ()


def test_audit_detects_missing_payload_and_reports_unreferenced_cas_content(
    tmp_path,
) -> None:
    service = _service(tmp_path)
    registered = _register(service, name="registered", content=b"registered")
    orphan = service.cas.put(b"unreferenced")
    service.cas.discard(registered.sha256)

    report = verify_artifacts(service.registry, service.cas)

    assert not report.ok
    assert {"payload_integrity", "payload_missing"}.issubset(_categories(report))
    assert report.orphan_scan.orphan_digests == (orphan.sha256,)
    assert report.orphan_scan.missing_digests == (registered.sha256,)


def test_audit_detects_envelope_column_corruption(tmp_path) -> None:
    service = _service(tmp_path)
    artifact = _register(service, name="envelope", content=b"envelope")
    _replace_immutable_value(
        service.registry.database_path,
        table="artifact_envelopes",
        update_sql=(
            "UPDATE artifact_envelopes SET envelope_sha256 = ? "
            "WHERE artifact_id = ?"
        ),
        parameters=("0" * 64, artifact.artifact_id),
    )

    report = verify_artifacts(service.registry, service.cas)

    assert not report.ok
    assert "envelope_integrity" in _categories(report)


def test_audit_detects_parent_link_mismatch(tmp_path) -> None:
    service = _service(tmp_path)
    parent = _register(service, name="link_parent", content=b"parent")
    child = _register(
        service,
        name="link_child",
        content=b"child",
        parent_refs=(parent.ref,),
    )
    _replace_immutable_value(
        service.registry.database_path,
        table="artifact_links",
        update_sql=(
            "UPDATE artifact_links SET position = 7 WHERE source_artifact_id = ?"
        ),
        parameters=(child.artifact_id,),
    )

    report = verify_artifacts(service.registry, service.cas)

    assert not report.ok
    assert "provenance_journal" in _categories(report)


def test_audit_detects_idempotency_corruption(tmp_path) -> None:
    service = _service(tmp_path)
    artifact = _register(service, name="idempotency", content=b"idempotency")
    _replace_immutable_value(
        service.registry.database_path,
        table="idempotency_records",
        update_sql=(
            "UPDATE idempotency_records SET request_sha256 = ? "
            "WHERE artifact_id = ?"
        ),
        parameters=("0" * 64, artifact.artifact_id),
    )

    report = verify_artifacts(service.registry, service.cas)

    assert not report.ok
    assert "idempotency_integrity" in _categories(report)


def test_exact_retired_event_table_is_inert_across_restart(tmp_path) -> None:
    service = _service(tmp_path)
    old = _register(service, name="old", content=b"old")
    event = b"legacy-event"
    with sqlite3.connect(service.registry.database_path) as connection:
        connection.executescript(_RETIRED_EVENT_SQL)
        connection.execute(
            """
            INSERT INTO artifact_events (
                event_id, artifact_id, event_type, recorded_at,
                event_json, event_sha256
            ) VALUES (?, ?, 'artifact_registered', ?, ?, ?)
            """,
            (
                "evt_legacy",
                old.artifact_id,
                old.created_at,
                event,
                hashlib.sha256(event).hexdigest(),
            ),
        )

    restarted = _service(tmp_path)
    assert restarted.read(old.ref) == b"old"
    _register(restarted, name="new", content=b"new")
    assert verify_artifacts(restarted.registry, restarted.cas).ok
    with sqlite3.connect(restarted.registry.database_path) as connection:
        rows = connection.execute(
            "SELECT event_id, artifact_id FROM artifact_events ORDER BY event_id"
        ).fetchall()
    assert rows == [("evt_legacy", old.artifact_id)]


@pytest.mark.parametrize("drift", ("unknown_table", "missing_current_trigger"))
def test_retired_event_tolerance_rejects_other_schema_drift(tmp_path, drift) -> None:
    service = _service(tmp_path)
    with sqlite3.connect(service.registry.database_path) as connection:
        connection.executescript(_RETIRED_EVENT_SQL)
        if drift == "unknown_table":
            connection.execute("CREATE TABLE unexpected_state (value TEXT)")
        else:
            connection.execute("DROP TRIGGER artifact_envelopes_deny_update")

    with pytest.raises(
        RegistryConfigurationError,
        match="schema differs from migration contract",
    ):
        _service(tmp_path)
