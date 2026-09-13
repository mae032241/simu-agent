"""Independent append-only SQLite registry for SciDiscovery."""

from __future__ import annotations

import hashlib
import re
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

from pydantic import ValidationError

from ..schema.artifact import (
    ArtifactEnvelope,
    ArtifactRegisterRequest,
    artifact_register_mismatches,
)
from ..schema.refs import ArtifactRef


REGISTRY_SCHEMA_VERSION = 1
IMMUTABLE_TABLES = (
    "artifact_envelopes",
    "artifact_links",
    "idempotency_records",
)
_RETIRED_ARTIFACT_EVENTS_SQL = """
CREATE TABLE IF NOT EXISTS artifact_events (
    event_id TEXT PRIMARY KEY,
    artifact_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK(event_type = 'artifact_registered'),
    recorded_at TEXT NOT NULL,
    event_json BLOB NOT NULL,
    event_sha256 TEXT NOT NULL CHECK(length(event_sha256) = 64),
    UNIQUE (artifact_id, event_type),
    FOREIGN KEY (artifact_id) REFERENCES artifact_envelopes(artifact_id)
);
CREATE TRIGGER IF NOT EXISTS artifact_events_deny_update
BEFORE UPDATE ON artifact_events BEGIN
    SELECT RAISE(ABORT, 'artifact_events is append-only');
END;
CREATE TRIGGER IF NOT EXISTS artifact_events_deny_delete
BEFORE DELETE ON artifact_events BEGIN
    SELECT RAISE(ABORT, 'artifact_events is append-only');
END;
"""


class ArtifactRegistryError(RuntimeError):
    """Base error for registry configuration or integrity failures."""


class RegistryConfigurationError(ArtifactRegistryError):
    """The requested database is unsafe or incompatible with this registry."""


class RegistryIntegrityError(ArtifactRegistryError):
    """Persisted registry bytes do not match their immutable metadata."""


class ArtifactNotFoundError(ArtifactRegistryError):
    """An exact artifact identity is not registered."""


class ArtifactReferenceError(ArtifactRegistryError):
    """A provenance reference does not resolve to an exact registered object."""


class ArtifactIdentityConflictError(ArtifactRegistryError):
    """An immutable logical artifact ID has already been used."""


class IdempotencyConflictError(ArtifactRegistryError):
    """An idempotency key was reused for different canonical request bytes."""


@dataclass(frozen=True)
class RawEnvelopeRecord:
    artifact_id: str
    payload_sha256: str
    size_bytes: int
    kind: str
    schema_id: str
    payload_schema_version: int
    media_type: str
    created_at: str
    envelope_json: bytes
    envelope_sha256: str


@dataclass(frozen=True)
class RawLinkRecord:
    source_artifact_id: str
    relation: str
    position: int
    target_artifact_id: str
    target_sha256: str
    target_kind: str
    target_schema_id: str


@dataclass(frozen=True)
class RawIdempotencyRecord:
    idempotency_key: str
    request_json: bytes
    request_sha256: str
    artifact_id: str
    response_json: bytes
    response_sha256: str
    created_at: str


@dataclass(frozen=True)
class RegistryAuditSnapshot:
    integrity: str
    envelopes: tuple[RawEnvelopeRecord, ...]
    links: tuple[RawLinkRecord, ...]
    idempotency_records: tuple[RawIdempotencyRecord, ...]
    referenced_digests: frozenset[object]


class SQLiteArtifactRegistry:
    """Append-only artifact metadata registry at one explicit path."""

    def __init__(self, database_path: Path | str, *, deadline_monotonic: float | None = None) -> None:
        self.deadline_monotonic = deadline_monotonic
        self.database_path = _validate_database_path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def register(
        self,
        envelope: ArtifactEnvelope,
        *,
        idempotency_key: str,
        request_json: bytes,
        request_sha256: str,
        verify_payload: Callable[[], object],
    ) -> ArtifactEnvelope:
        _validate_identifier(idempotency_key, label="idempotency_key")
        if type(request_json) is not bytes:
            raise TypeError("request_json must be canonical bytes")
        _validate_sha256(request_sha256, label="request_sha256")
        if hashlib.sha256(request_json).hexdigest() != request_sha256:
            raise ValueError("request_sha256 does not match request_json")
        try:
            request = ArtifactRegisterRequest.model_validate_json(
                request_json,
                strict=True,
            )
        except ValidationError as error:
            raise ValueError("request_json does not match ArtifactRegisterRequest") from error
        if request.canonical_json() != request_json:
            raise ValueError("request_json must use canonical JSON bytes")
        mismatches = artifact_register_mismatches(request, envelope)
        if mismatches:
            raise ValueError(
                "request does not produce envelope fields: " + ", ".join(mismatches)
            )
        envelope_json = envelope.canonical_json()
        envelope_sha256 = hashlib.sha256(envelope_json).hexdigest()

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT request_json, request_sha256, artifact_id,
                       response_json, response_sha256
                FROM idempotency_records WHERE idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()
            if existing is not None:
                if existing["request_sha256"] != request_sha256:
                    raise IdempotencyConflictError(
                        "idempotency key is already bound to a different request"
                    )
                if existing["request_json"] != request_json:
                    raise RegistryIntegrityError(
                        "idempotency request bytes disagree with their hash"
                    )
                replay = self._decode_response(
                    existing["response_json"],
                    expected_sha256=existing["response_sha256"],
                )
                if replay.artifact_id != existing["artifact_id"]:
                    raise RegistryIntegrityError(
                        "idempotency response does not match its artifact_id"
                    )
                replay_mismatches = artifact_register_mismatches(request, replay)
                if replay_mismatches:
                    raise RegistryIntegrityError(
                        "idempotency request does not produce stored response"
                    )
                self._resolve_in_connection(connection, replay.ref)
                verify_payload()
                connection.execute("ROLLBACK")
                return replay

            if connection.execute(
                "SELECT 1 FROM artifact_envelopes WHERE artifact_id = ?",
                (envelope.artifact_id,),
            ).fetchone() is not None:
                raise ArtifactIdentityConflictError(
                    f"artifact_id is already registered: {envelope.artifact_id}"
                )

            for reference in _direct_references(envelope):
                try:
                    self._resolve_in_connection(connection, reference)
                except ArtifactNotFoundError as error:
                    raise ArtifactReferenceError(
                        "artifact provenance reference does not exist exactly: "
                        f"{reference.artifact_id}"
                    ) from error

            connection.execute(
                """
                INSERT INTO artifact_envelopes (
                    artifact_id, payload_sha256, size_bytes, kind, schema_id,
                    payload_schema_version, media_type, created_at,
                    envelope_json, envelope_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    envelope.artifact_id,
                    envelope.sha256,
                    envelope.size_bytes,
                    envelope.kind,
                    envelope.schema_id,
                    envelope.payload_schema_version,
                    envelope.media_type,
                    envelope.created_at,
                    envelope_json,
                    envelope_sha256,
                ),
            )
            self._insert_links(connection, envelope)
            connection.execute(
                """
                INSERT INTO idempotency_records (
                    idempotency_key, request_json, request_sha256, artifact_id,
                    response_json, response_sha256, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    idempotency_key,
                    request_json,
                    request_sha256,
                    envelope.artifact_id,
                    envelope_json,
                    envelope_sha256,
                    envelope.created_at,
                ),
            )

            # Re-read the full CAS object as close as possible to the metadata commit.
            verify_payload()
            self._commit(connection)
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()
        return envelope

    def resolve(self, reference: ArtifactRef) -> ArtifactEnvelope:
        with self._connect() as connection:
            return self._resolve_in_connection(connection, reference)

    def get_by_id(self, artifact_id: str) -> ArtifactEnvelope:
        _validate_identifier(artifact_id, label="artifact_id")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM artifact_envelopes WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
        if row is None:
            raise ArtifactNotFoundError(f"artifact is not registered: {artifact_id}")
        return self._decode_envelope_row(row)

    def list_artifacts(
        self,
        *,
        kind: str | None = None,
        schema_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[ArtifactEnvelope, ...]:
        if kind is not None:
            _validate_identifier(kind, label="kind")
        if schema_id is not None:
            _validate_identifier(schema_id, label="schema_id")
        if type(limit) is not int or not 1 <= limit <= 10_000:
            raise ValueError("limit must be an integer between 1 and 10000")
        if type(offset) is not int or offset < 0:
            raise ValueError("offset must be a non-negative integer")

        clauses: list[str] = []
        parameters: list[object] = []
        if kind is not None:
            clauses.append("kind = ?")
            parameters.append(kind)
        if schema_id is not None:
            clauses.append("schema_id = ?")
            parameters.append(schema_id)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        parameters.extend((limit, offset))
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM artifact_envelopes"
                + where
                + " ORDER BY created_at, artifact_id LIMIT ? OFFSET ?",
                parameters,
            ).fetchall()
        return tuple(self._decode_envelope_row(row) for row in rows)

    def referenced_digests(self) -> frozenset[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_sha256 FROM artifact_envelopes"
            ).fetchall()
        return frozenset(row[0] for row in rows)

    def raw_envelopes(self) -> tuple[RawEnvelopeRecord, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM artifact_envelopes ORDER BY rowid"
            ).fetchall()
        return tuple(RawEnvelopeRecord(**dict(row)) for row in rows)

    def raw_links(self) -> tuple[RawLinkRecord, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT source_artifact_id, relation, position,
                       target_artifact_id, target_sha256,
                       target_kind, target_schema_id
                FROM artifact_links
                ORDER BY source_artifact_id, relation, position
                """
            ).fetchall()
        return tuple(RawLinkRecord(**dict(row)) for row in rows)

    def raw_idempotency_records(self) -> tuple[RawIdempotencyRecord, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM idempotency_records ORDER BY rowid"
            ).fetchall()
        return tuple(RawIdempotencyRecord(**dict(row)) for row in rows)

    def integrity_check(self) -> str:
        with self._connect() as connection:
            row = connection.execute("PRAGMA integrity_check").fetchone()
        return str(row[0])

    def audit_snapshot(self) -> RegistryAuditSnapshot:
        """Read all audit state from one immutable SQLite read transaction."""

        connection = self._connect(read_only=True)
        try:
            connection.execute("BEGIN")
            self._verify_schema(connection)
            integrity = str(
                connection.execute("PRAGMA integrity_check").fetchone()[0]
            )
            envelope_rows = connection.execute(
                "SELECT * FROM artifact_envelopes ORDER BY rowid"
            ).fetchall()
            link_rows = connection.execute(
                """
                SELECT source_artifact_id, relation, position,
                       target_artifact_id, target_sha256,
                       target_kind, target_schema_id
                FROM artifact_links
                ORDER BY source_artifact_id, relation, position
                """
            ).fetchall()
            idempotency_rows = connection.execute(
                "SELECT * FROM idempotency_records ORDER BY rowid"
            ).fetchall()
            snapshot = RegistryAuditSnapshot(
                integrity=integrity,
                envelopes=tuple(
                    RawEnvelopeRecord(**dict(row)) for row in envelope_rows
                ),
                links=tuple(RawLinkRecord(**dict(row)) for row in link_rows),
                idempotency_records=tuple(
                    RawIdempotencyRecord(**dict(row))
                    for row in idempotency_rows
                ),
                referenced_digests=frozenset(
                    row["payload_sha256"] for row in envelope_rows
                ),
            )
            connection.execute("ROLLBACK")
            return snapshot
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        connection = self._connect()
        try:
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            tables = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                    """
                )
            }
            if version == 0:
                if tables:
                    raise RegistryConfigurationError(
                        "refusing to migrate a non-empty unversioned database"
                    )
                connection.executescript(_migration_sql())
                version = int(
                    connection.execute("PRAGMA user_version").fetchone()[0]
                )
            if version != REGISTRY_SCHEMA_VERSION:
                raise RegistryConfigurationError(
                    f"unsupported artifact registry schema version: {version}"
                )
            self._verify_schema(connection)
        finally:
            connection.close()

    def _connect(self, *, read_only: bool = False) -> sqlite3.Connection:
        timeout = 30.0 if self.deadline_monotonic is None else min(30.0, self.deadline_monotonic - time.monotonic())
        if timeout <= 0:
            raise TimeoutError("artifact registration connection budget exhausted")
        target: Path | str = self.database_path
        parameters: dict[str, object] = {}
        if read_only:
            target = self.database_path.as_uri() + "?mode=ro"
            parameters["uri"] = True
        connection = sqlite3.connect(
            target,
            timeout=timeout,
            isolation_level=None,
            **parameters,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {max(1, int(timeout * 1000))}")
        if read_only:
            connection.execute("PRAGMA query_only = ON")
        else:
            connection.execute("PRAGMA synchronous = FULL")
        return connection

    @staticmethod
    def _commit(connection: sqlite3.Connection) -> None:
        connection.execute("COMMIT")

    @staticmethod
    def _verify_schema(connection: sqlite3.Connection) -> None:
        try:
            actual = _schema_contract(connection)
            expected = _expected_schema_contract()
        except sqlite3.DatabaseError as error:
            raise RegistryConfigurationError(
                "artifact registry schema cannot be inspected"
            ) from error
        if actual not in (expected, _expected_schema_contract_with_retired_events()):
            raise RegistryConfigurationError(
                "artifact registry schema differs from migration contract"
            )
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RegistryConfigurationError(
                "artifact registry contains foreign-key violations"
            )

    @classmethod
    def _resolve_in_connection(
        cls,
        connection: sqlite3.Connection,
        reference: ArtifactRef,
    ) -> ArtifactEnvelope:
        row = connection.execute(
            """
            SELECT * FROM artifact_envelopes
            WHERE artifact_id = ? AND payload_sha256 = ?
              AND kind = ? AND schema_id = ?
            """,
            (
                reference.artifact_id,
                reference.sha256,
                reference.kind,
                reference.schema_id,
            ),
        ).fetchone()
        if row is None:
            raise ArtifactNotFoundError(
                f"exact artifact reference is not registered: {reference.artifact_id}"
            )
        envelope = cls._decode_envelope_row(row)
        if envelope.ref != reference:
            raise RegistryIntegrityError("resolved envelope does not match reference")
        return envelope

    @staticmethod
    def _decode_envelope_row(row: sqlite3.Row) -> ArtifactEnvelope:
        raw = row["envelope_json"]
        if type(raw) is not bytes:
            raise RegistryIntegrityError("envelope_json is not stored as bytes")
        observed = hashlib.sha256(raw).hexdigest()
        if observed != row["envelope_sha256"]:
            raise RegistryIntegrityError("envelope registry hash mismatch")
        try:
            envelope = ArtifactEnvelope.model_validate_json(raw, strict=True)
        except ValidationError as error:
            raise RegistryIntegrityError("envelope schema validation failed") from error
        if envelope.canonical_json() != raw:
            raise RegistryIntegrityError("envelope JSON is not canonical")
        expected_columns = (
            envelope.artifact_id,
            envelope.sha256,
            envelope.size_bytes,
            envelope.kind,
            envelope.schema_id,
            envelope.payload_schema_version,
            envelope.media_type,
            envelope.created_at,
        )
        actual_columns = tuple(
            row[name]
            for name in (
                "artifact_id",
                "payload_sha256",
                "size_bytes",
                "kind",
                "schema_id",
                "payload_schema_version",
                "media_type",
                "created_at",
            )
        )
        if actual_columns != expected_columns:
            raise RegistryIntegrityError("envelope columns disagree with envelope bytes")
        return envelope

    @staticmethod
    def _decode_response(raw: object, *, expected_sha256: object) -> ArtifactEnvelope:
        if type(raw) is not bytes or type(expected_sha256) is not str:
            raise RegistryIntegrityError("idempotency response storage is malformed")
        if hashlib.sha256(raw).hexdigest() != expected_sha256:
            raise RegistryIntegrityError("idempotency response hash mismatch")
        try:
            response = ArtifactEnvelope.model_validate_json(raw, strict=True)
        except ValidationError as error:
            raise RegistryIntegrityError(
                "idempotency response schema validation failed"
            ) from error
        if response.canonical_json() != raw:
            raise RegistryIntegrityError("idempotency response JSON is not canonical")
        return response

    @staticmethod
    def _insert_links(
        connection: sqlite3.Connection,
        envelope: ArtifactEnvelope,
    ) -> None:
        links: list[tuple[str, int, ArtifactRef]] = [
            ("parent", position, reference)
            for position, reference in enumerate(envelope.parent_refs)
        ]
        if envelope.supersedes_ref is not None:
            links.append(("supersedes", 0, envelope.supersedes_ref))
        connection.executemany(
            """
            INSERT INTO artifact_links (
                source_artifact_id, relation, position,
                target_artifact_id, target_sha256,
                target_kind, target_schema_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    envelope.artifact_id,
                    relation,
                    position,
                    reference.artifact_id,
                    reference.sha256,
                    reference.kind,
                    reference.schema_id,
                )
                for relation, position, reference in links
            ],
        )


def _direct_references(envelope: ArtifactEnvelope) -> tuple[ArtifactRef, ...]:
    references = list(envelope.parent_refs)
    if envelope.supersedes_ref is not None:
        references.append(envelope.supersedes_ref)
    return tuple(references)


def _validate_database_path(database_path: Path | str) -> Path:
    if not isinstance(database_path, (Path, str)):
        raise TypeError("database_path must be a filesystem path")
    if str(database_path) == ":memory:" or str(database_path).startswith("file:"):
        raise RegistryConfigurationError(
            "artifact registry requires an explicit independent filesystem path"
        )
    return Path(database_path).expanduser().resolve(strict=False)


def _migration_sql() -> str:
    return (
        files(f"{__package__}.migrations")
        .joinpath("0001_artifacts.sql")
        .read_text(encoding="utf-8")
    )


@lru_cache(maxsize=1)
def _expected_schema_contract() -> tuple[object, ...]:
    connection = sqlite3.connect(":memory:", isolation_level=None)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(_migration_sql())
        return _schema_contract(connection)
    finally:
        connection.close()


@lru_cache(maxsize=1)
def _expected_schema_contract_with_retired_events() -> tuple[object, ...]:
    """Accept the exact former v1 event table as inert state, never as authority."""

    connection = sqlite3.connect(":memory:", isolation_level=None)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(_migration_sql())
        connection.executescript(_RETIRED_ARTIFACT_EVENTS_SQL)
        return _schema_contract(connection)
    finally:
        connection.close()


def _schema_contract(connection: sqlite3.Connection) -> tuple[object, ...]:
    master_rows = connection.execute(
        """
        SELECT type, name, tbl_name, sql
        FROM sqlite_master
        WHERE name NOT LIKE 'sqlite_%' AND sql IS NOT NULL
        ORDER BY type, name
        """
    ).fetchall()
    master = tuple(
        (
            row["type"],
            row["name"],
            row["tbl_name"],
            " ".join(str(row["sql"]).split()),
        )
        for row in master_rows
    )
    table_names = tuple(
        row["name"] for row in master_rows if row["type"] == "table"
    )
    tables: list[tuple[object, ...]] = []
    for table_name in table_names:
        quoted_table = _quote_identifier(table_name)
        columns = tuple(
            tuple(row)
            for row in connection.execute(
                f"PRAGMA table_xinfo({quoted_table})"
            ).fetchall()
        )
        foreign_keys = tuple(
            tuple(row)
            for row in connection.execute(
                f"PRAGMA foreign_key_list({quoted_table})"
            ).fetchall()
        )
        index_rows = connection.execute(
            f"PRAGMA index_list({quoted_table})"
        ).fetchall()
        indices: list[tuple[object, ...]] = []
        for index_row in index_rows:
            index_name = index_row[1]
            index_contract = (
                index_name,
                index_row[2],
                index_row[3],
                index_row[4],
                tuple(
                    tuple(row)
                    for row in connection.execute(
                        f"PRAGMA index_xinfo({_quote_identifier(index_name)})"
                    ).fetchall()
                ),
            )
            indices.append(index_contract)
        tables.append(
            (
                table_name,
                columns,
                foreign_keys,
                tuple(sorted(indices, key=lambda item: str(item[0]))),
            )
        )
    user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    return user_version, master, tuple(tables)


def _quote_identifier(value: object) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def _validate_identifier(value: str, *, label: str) -> None:
    if (
        type(value) is not str
        or not 1 <= len(value) <= 256
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]*", value) is None
    ):
        raise ValueError(f"{label} must be a valid identifier")


def _validate_sha256(value: str, *, label: str) -> None:
    if (
        type(value) is not str
        or re.fullmatch(r"[0-9a-f]{64}", value) is None
    ):
        raise ValueError(f"{label} must be 64 lowercase hexadecimal characters")


__all__ = [
    "IMMUTABLE_TABLES",
    "REGISTRY_SCHEMA_VERSION",
    "ArtifactIdentityConflictError",
    "ArtifactNotFoundError",
    "ArtifactReferenceError",
    "ArtifactRegistryError",
    "IdempotencyConflictError",
    "RawEnvelopeRecord",
    "RawIdempotencyRecord",
    "RawLinkRecord",
    "RegistryAuditSnapshot",
    "RegistryConfigurationError",
    "RegistryIntegrityError",
    "SQLiteArtifactRegistry",
]
