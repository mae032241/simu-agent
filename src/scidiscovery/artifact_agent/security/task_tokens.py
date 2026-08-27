"""Internal single-claim capabilities for the worker broker."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import ValidationError

from ..schema.artifact import UtcRfc3339
from ..schema.common import Identifier, SchemaModel, canonical_json
from ..schema.refs import ArtifactRef


class TaskTokenError(RuntimeError):
    pass


class TaskTokenInvalid(TaskTokenError):
    pass


class TaskTokenExpired(TaskTokenError):
    pass


class TaskTokenIdentityMismatch(TaskTokenError):
    pass


class TaskTokenAlreadyClaimed(TaskTokenError):
    pass


class TaskDispatchCapability(SchemaModel):
    handle_id: Identifier
    task_id: Identifier
    task_ref: ArtifactRef
    worker_id: Identifier
    attempt: int
    expires_at: UtcRfc3339


class ClaimedTaskSession(SchemaModel):
    session_id: Identifier
    handle_id: Identifier
    task_id: Identifier
    task_ref: ArtifactRef
    worker_id: Identifier
    attempt: int
    expires_at: UtcRfc3339


class TaskTokenService:
    """Issue and verify opaque capabilities while keeping identity in control."""

    def __init__(self, *, database_path: Path | str, secret: bytes) -> None:
        if type(secret) is not bytes or len(secret) < 32:
            raise ValueError("task token secret must contain at least 32 bytes")
        self.database_path = Path(database_path).expanduser().absolute()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._secret = secret
        self._initialize()

    def issue(
        self,
        *,
        task_id: str,
        task_ref: ArtifactRef,
        worker_id: str,
        attempt: int,
        ttl_seconds: int,
    ) -> str:
        if not 1 <= ttl_seconds <= 86_400:
            raise ValueError("ttl_seconds must be between 1 and 86400")
        if attempt < 1:
            raise ValueError("attempt must be positive")
        capability = TaskDispatchCapability(
            handle_id=f"hdl_{uuid.uuid4().hex}",
            task_id=task_id,
            task_ref=task_ref,
            worker_id=worker_id,
            attempt=attempt,
            expires_at=_timestamp(_now() + timedelta(seconds=ttl_seconds)),
        )
        token = self._encode("dispatch", capability.canonical_json())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO dispatch_capabilities (
                    handle_id, task_id, task_ref_json, worker_id, attempt,
                    expires_at, token_sha256, issued_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    capability.handle_id,
                    capability.task_id,
                    capability.task_ref.canonical_json(),
                    capability.worker_id,
                    capability.attempt,
                    capability.expires_at,
                    _sha(token),
                    _timestamp(_now()),
                ),
            )
        return token

    def delete_tasks(self, task_ids: tuple[str, ...]) -> tuple[str, ...]:
        """Revoke and remove all capabilities for administratively deleted tasks."""

        if len(task_ids) != len(set(task_ids)):
            raise ValueError("task identities must be unique")
        if any(not isinstance(value, str) or not value for value in task_ids):
            raise ValueError("task identity is invalid")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            session_ids = tuple(
                str(row["session_id"])
                for task_id in task_ids
                for row in connection.execute(
                    "SELECT session_id FROM worker_sessions WHERE task_id = ?",
                    (task_id,),
                ).fetchall()
            )
            connection.executemany(
                "DELETE FROM worker_sessions WHERE task_id = ?",
                ((value,) for value in task_ids),
            )
            connection.executemany(
                "DELETE FROM dispatch_capabilities WHERE task_id = ?",
                ((value,) for value in task_ids),
            )
            connection.execute("COMMIT")
        return session_ids

    def inspect_dispatch(
        self, token: str, *, worker_id: str
    ) -> TaskDispatchCapability:
        capability = self._decode_dispatch(token)
        if capability.worker_id != worker_id:
            raise TaskTokenIdentityMismatch("dispatch handle is bound to another worker")
        if _now() >= _parse_timestamp(capability.expires_at):
            raise TaskTokenExpired("dispatch handle has expired")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM dispatch_capabilities WHERE handle_id = ?",
                (capability.handle_id,),
            ).fetchone()
        if row is None or row["token_sha256"] != _sha(token):
            raise TaskTokenInvalid("dispatch handle is not registered")
        if row["claimed_at"] is not None:
            raise TaskTokenAlreadyClaimed("dispatch handle has already been claimed")
        if _row_binding(row) != _capability_binding(capability):
            raise TaskTokenInvalid("dispatch handle storage binding is inconsistent")
        return capability

    def claim(
        self,
        token: str,
        *,
        worker_id: str,
        session_ttl_seconds: int | None = None,
    ) -> str:
        capability = self.inspect_dispatch(token, worker_id=worker_id)
        ttl_seconds = session_ttl_seconds or max(
            1, int((_parse_timestamp(capability.expires_at) - _now()).total_seconds())
        )
        if not 1 <= ttl_seconds <= 86_400:
            raise ValueError("session_ttl_seconds must be between 1 and 86400")
        session = ClaimedTaskSession(
            session_id=f"ses_{uuid.uuid4().hex}",
            handle_id=capability.handle_id,
            task_id=capability.task_id,
            task_ref=capability.task_ref,
            worker_id=capability.worker_id,
            attempt=capability.attempt,
            expires_at=_timestamp(_now() + timedelta(seconds=ttl_seconds)),
        )
        session_token = self._encode("session", session.canonical_json())
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM dispatch_capabilities WHERE handle_id = ?",
                (capability.handle_id,),
            ).fetchone()
            if row is None or row["token_sha256"] != _sha(token):
                raise TaskTokenInvalid("dispatch handle is not registered")
            if row["claimed_at"] is not None:
                raise TaskTokenAlreadyClaimed("dispatch handle has already been claimed")
            if _row_binding(row) != _capability_binding(capability):
                raise TaskTokenInvalid("dispatch handle storage binding is inconsistent")
            now = _timestamp(_now())
            connection.execute(
                "UPDATE dispatch_capabilities SET claimed_at = ?, session_id = ? WHERE handle_id = ?",
                (now, session.session_id, capability.handle_id),
            )
            connection.execute(
                """
                INSERT INTO worker_sessions (
                    session_id, handle_id, task_id, task_ref_json, worker_id,
                    attempt, expires_at, token_sha256, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.session_id,
                    session.handle_id,
                    session.task_id,
                    session.task_ref.canonical_json(),
                    session.worker_id,
                    session.attempt,
                    session.expires_at,
                    _sha(session_token),
                    now,
                ),
            )
            connection.execute("COMMIT")
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()
        return session_token

    def verify_session(self, token: str, *, worker_id: str) -> ClaimedTaskSession:
        session = self.verify_session_binding(token, worker_id=worker_id)
        if _now() >= _parse_timestamp(session.expires_at):
            raise TaskTokenExpired("task session has expired")
        return session

    def verify_session_binding(
        self, token: str, *, worker_id: str
    ) -> ClaimedTaskSession:
        """Authenticate a stored session without deciding task-phase expiry.

        Only the task service's sealed finalization path may use this method
        after the scientific deadline. All ordinary worker operations must use
        :meth:`verify_session`.
        """

        session = self._decode_session(token)
        if session.worker_id != worker_id:
            raise TaskTokenIdentityMismatch("task session is bound to another worker")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM worker_sessions WHERE session_id = ?",
                (session.session_id,),
            ).fetchone()
        if row is None or row["token_sha256"] != _sha(token):
            raise TaskTokenInvalid("task session is not registered")
        expected = (
            session.handle_id,
            session.task_id,
            session.task_ref.canonical_json(),
            session.worker_id,
            session.attempt,
            session.expires_at,
        )
        actual = (
            row["handle_id"],
            row["task_id"],
            row["task_ref_json"],
            row["worker_id"],
            int(row["attempt"]),
            row["expires_at"],
        )
        if actual != expected:
            raise TaskTokenInvalid("task session storage binding is inconsistent")
        return session

    def _encode(self, kind: str, payload: bytes) -> str:
        body = _b64(payload)
        signature = _b64(hmac.new(self._secret, kind.encode() + b"." + body, hashlib.sha256).digest())
        return f"{kind}.{body.decode('ascii')}.{signature.decode('ascii')}"

    def _decode_dispatch(self, token: str) -> TaskDispatchCapability:
        return self._decode(token, "dispatch", TaskDispatchCapability)

    def _decode_session(self, token: str) -> ClaimedTaskSession:
        return self._decode(token, "session", ClaimedTaskSession)

    def _decode(self, token: str, expected_kind: str, model: type[SchemaModel]):
        try:
            kind, body_text, signature_text = token.split(".", 2)
            body = body_text.encode("ascii")
            signature = _unb64(signature_text)
        except (AttributeError, ValueError, UnicodeEncodeError) as error:
            raise TaskTokenInvalid("malformed task capability") from error
        if kind != expected_kind:
            raise TaskTokenInvalid("task capability has the wrong kind")
        expected = hmac.new(self._secret, kind.encode() + b"." + body, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise TaskTokenInvalid("task capability signature is invalid")
        try:
            raw = _unb64(body_text)
            value = model.model_validate_json(raw, strict=True)
        except (ValueError, ValidationError) as error:
            raise TaskTokenInvalid("task capability payload is invalid") from error
        if value.canonical_json() != raw:
            raise TaskTokenInvalid("task capability payload is not canonical")
        return value

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS dispatch_capabilities (
                    handle_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    task_ref_json BLOB NOT NULL,
                    worker_id TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    expires_at TEXT NOT NULL,
                    token_sha256 TEXT NOT NULL,
                    issued_at TEXT NOT NULL,
                    claimed_at TEXT,
                    session_id TEXT UNIQUE
                );
                CREATE TABLE IF NOT EXISTS worker_sessions (
                    session_id TEXT PRIMARY KEY,
                    handle_id TEXT NOT NULL UNIQUE,
                    task_id TEXT NOT NULL,
                    task_ref_json BLOB NOT NULL,
                    worker_id TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    expires_at TEXT NOT NULL,
                    token_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def _capability_binding(value: TaskDispatchCapability) -> tuple[object, ...]:
    return (
        value.task_id,
        value.task_ref.canonical_json(),
        value.worker_id,
        value.attempt,
        value.expires_at,
    )


def _row_binding(row: sqlite3.Row) -> tuple[object, ...]:
    return (
        row["task_id"],
        row["task_ref_json"],
        row["worker_id"],
        int(row["attempt"]),
        row["expires_at"],
    )


def _b64(raw: bytes) -> bytes:
    return base64.urlsafe_b64encode(raw).rstrip(b"=")


def _unb64(value: str) -> bytes:
    raw = value.encode("ascii")
    return base64.urlsafe_b64decode(raw + b"=" * (-len(raw) % 4))


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.removesuffix("Z") + "+00:00")


__all__ = [
    "ClaimedTaskSession",
    "TaskTokenAlreadyClaimed",
    "TaskTokenError",
    "TaskTokenExpired",
    "TaskTokenIdentityMismatch",
    "TaskTokenInvalid",
    "TaskTokenService",
]
