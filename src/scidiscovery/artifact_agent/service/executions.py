"""Control-owned generic execution lifecycle."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import stat
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from ..schema.approval import (
    ApprovalRequest,
    CompiledApprovalIdentity,
    HumanDecision,
)
from ..schema.artifact import ArtifactRegistration
from ..schema.execution import (
    ExecutionRequest,
    ExecutionResultManifest,
    LocalFileDescriptor,
)
from ..schema.refs import ActorRef, ArtifactRef
from ..storage import (
    ArtifactIdentityConflictError,
    ArtifactNotFoundError,
    IdempotencyConflictError,
)
from .approvals import ApprovalService
from .artifacts import ArtifactService


class ExecutionServiceError(RuntimeError):
    pass


class ExecutionStateConflict(ExecutionServiceError):
    pass


class ExecutionApprovalError(ExecutionServiceError):
    pass


@dataclass(frozen=True)
class ExecutionStatusView:
    execution_id: str
    executor: str
    state: str
    external_run_id: str | None
    result_ref: ArtifactRef | None
    created_at: str


@dataclass(frozen=True)
class ExecutionOutputView:
    logical_name: str
    artifact_id: str
    media_type: str
    size_bytes: int


class ExecutionService:
    """Own execution identity without interpreting domain payloads."""

    def __init__(
        self,
        *,
        artifacts: ArtifactService,
        approvals: ApprovalService,
        database_path: Path | str,
        exchange_root: Path | str,
        service_actor: ActorRef,
    ) -> None:
        self.artifacts = artifacts
        self.approvals = approvals
        self.database_path = Path(database_path).expanduser().absolute()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.exchange_root = Path(exchange_root).expanduser().absolute()
        self.exchange_root.mkdir(parents=True, exist_ok=True, mode=0o770)
        self.service_actor = service_actor
        self._initialize()

    @staticmethod
    def resolve_result_scope(*, artifacts, database_path, result_ref):
        """Trusted read-only lookup from an already bound immutable result."""
        result = ExecutionResultManifest.model_validate_json(artifacts.read(result_ref), strict=True)
        with sqlite3.connect(database_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute('SELECT * FROM executions WHERE execution_id=?', (result.execution_id,)).fetchone()
        if row is None or row['state'] != 'collected' or row['external_run_id'] != result.external_run_id or _parse_ref(row['result_ref_json']) != result_ref:
            raise ExecutionStateConflict('bound result does not identify a collected execution')
        return {'executor':row['executor'], 'external_run_id':result.external_run_id,
                'payload_ref':_parse_ref(row['payload_ref_json']), 'result_ref':result_ref}

    def create(
        self,
        *,
        executor: str,
        preparation_profile: str,
        payload_ref: ArtifactRef,
        compiled_identity: CompiledApprovalIdentity | None = None,
        labels: dict[str, str] | None = None,
        execution_id: str | None = None,
    ) -> str:
        self.artifacts.verify(payload_ref)
        execution_id = execution_id or f"exe_{uuid.uuid4().hex}"
        expected_labels = labels or {}
        request_artifact_id = "execution_request_" + hashlib.sha256(
            execution_id.encode("utf-8")
        ).hexdigest()
        registration = ArtifactRegistration(
            artifact_id=request_artifact_id,
            kind="execution_request",
            schema_id="scidiscovery.execution-request",
            payload_schema_version=1,
            media_type="application/json",
            creator=self.service_actor,
            parent_refs=(payload_ref,),
            labels=expected_labels,
            confidentiality="approval_only",
        )
        idempotency_key = f"execution:{execution_id}:request"
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM executions WHERE execution_id = ?", (execution_id,)
            ).fetchone()
        if existing is not None:
            request_ref = _parse_ref(existing["request_ref_json"])
            if (
                existing["executor"] != executor
                or _parse_ref(existing["payload_ref_json"]) != payload_ref
                or request_ref.artifact_id != request_artifact_id
            ):
                raise ExecutionServiceError(
                    "execution identity is already bound to a different request"
                )
            request = self._validate_request_artifact(
                request_ref,
                execution_id=execution_id,
                executor=executor,
                preparation_profile=preparation_profile,
                payload_ref=payload_ref,
                compiled_identity=compiled_identity,
                labels=expected_labels,
            )
            replay = self.artifacts.register(
                request.canonical_json(),
                registration,
                idempotency_key=idempotency_key,
            )
            if replay.ref != request_ref:
                raise ExecutionServiceError(
                    "execution request replay returned a different Artifact"
                )
            return execution_id
        existing_request = self._request_artifact_by_id(
            request_artifact_id,
            execution_id=execution_id,
            executor=executor,
            preparation_profile=preparation_profile,
            payload_ref=payload_ref,
            compiled_identity=compiled_identity,
            labels=expected_labels,
        )
        request = existing_request or ExecutionRequest(
            execution_id=execution_id,
            executor=executor,
            preparation_profile=preparation_profile,
            payload_ref=payload_ref,
            created_at=_timestamp(),
            compiled_identity=compiled_identity,
        )
        try:
            request_envelope = self.artifacts.register(
                request.canonical_json(),
                registration,
                idempotency_key=idempotency_key,
            )
        except (ArtifactIdentityConflictError, IdempotencyConflictError):
            request = self._request_artifact_by_id(
                request_artifact_id,
                execution_id=execution_id,
                executor=executor,
                preparation_profile=preparation_profile,
                payload_ref=payload_ref,
                compiled_identity=compiled_identity,
                labels=expected_labels,
            )
            if request is None:
                raise
            request_envelope = self.artifacts.register(
                request.canonical_json(),
                registration,
                idempotency_key=idempotency_key,
            )
        request_ref = request_envelope.ref
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO executions (
                    execution_id, executor, request_ref_json, payload_ref_json,
                    state, created_at
                ) VALUES (?, ?, ?, ?, 'created', ?)
                """,
                (
                    execution_id,
                    executor,
                    request_ref.canonical_json(),
                    payload_ref.canonical_json(),
                    request.created_at,
                ),
            )
        with self._connect() as connection:
            created = self._row(connection, execution_id)
        if (
            created["executor"] != executor
            or _parse_ref(created["request_ref_json"]) != request_ref
            or _parse_ref(created["payload_ref_json"]) != payload_ref
        ):
            raise ExecutionServiceError(
                "execution identity is already bound to a different request"
            )
        return execution_id

    def _request_artifact_by_id(
        self,
        artifact_id: str,
        *,
        execution_id: str,
        executor: str,
        preparation_profile: str,
        payload_ref: ArtifactRef,
        compiled_identity: CompiledApprovalIdentity | None,
        labels: dict[str, str],
    ) -> ExecutionRequest | None:
        try:
            envelope = self.artifacts.get_by_id(artifact_id)
        except ArtifactNotFoundError:
            return None
        return self._validate_request_artifact(
            envelope.ref,
            execution_id=execution_id,
            executor=executor,
            preparation_profile=preparation_profile,
            payload_ref=payload_ref,
            compiled_identity=compiled_identity,
            labels=labels,
        )

    def _validate_request_artifact(
        self,
        request_ref: ArtifactRef,
        *,
        execution_id: str,
        executor: str,
        preparation_profile: str,
        payload_ref: ArtifactRef,
        compiled_identity: CompiledApprovalIdentity | None,
        labels: dict[str, str],
    ) -> ExecutionRequest:
        envelope = self.artifacts.catalog(request_ref)
        try:
            request = ExecutionRequest.model_validate_json(
                self.artifacts.read(request_ref), strict=True
            )
        except ValidationError as error:
            raise ExecutionServiceError(
                "stored execution request is invalid"
            ) from error
        if (
            request.execution_id != execution_id
            or request.executor != executor
            or request.preparation_profile != preparation_profile
            or request.payload_ref != payload_ref
            or request.compiled_identity != compiled_identity
            or envelope.kind != "execution_request"
            or envelope.schema_id != "scidiscovery.execution-request"
            or envelope.payload_schema_version != 1
            or envelope.media_type != "application/json"
            or envelope.creator != self.service_actor
            or envelope.parent_refs != (payload_ref,)
            or envelope.labels != labels
            or envelope.confidentiality != "approval_only"
        ):
            raise ExecutionServiceError(
                "execution identity is already bound to a different request"
            )
        return request

    def request_artifact_id(self, execution_id: str) -> str:
        with self._connect() as connection:
            row = self._row(connection, execution_id)
        return _parse_ref(row["request_ref_json"]).artifact_id

    def approval_subject_refs(self, execution_id: str) -> tuple[ArtifactRef, ArtifactRef]:
        """Return the exact request and executable payload a human must review."""

        with self._connect() as connection:
            row = self._row(connection, execution_id)
        request_ref = _parse_ref(row["request_ref_json"])
        payload_ref = _parse_ref(row["payload_ref_json"])
        request = self.request(execution_id)
        if request.payload_ref != payload_ref:
            raise ExecutionServiceError(
                "execution request payload binding differs from stored execution state"
            )
        self.artifacts.verify(request_ref)
        self.artifacts.verify(payload_ref)
        return request_ref, payload_ref

    def request(self, execution_id: str) -> ExecutionRequest:
        with self._connect() as connection:
            row = self._row(connection, execution_id)
        request_ref = _parse_ref(row["request_ref_json"])
        try:
            return ExecutionRequest.model_validate_json(
                self.artifacts.read(request_ref), strict=True
            )
        except ValidationError as error:
            raise ExecutionServiceError("stored execution request is invalid") from error

    def authorize(
        self,
        *,
        execution_id: str,
        approval_id: str,
        compiled_identity: CompiledApprovalIdentity,
    ) -> LocalFileDescriptor:
        execution_request = self.request(execution_id)
        if execution_request.compiled_identity != compiled_identity:
            raise ExecutionApprovalError(
                "execution request compiled identity is missing or changed"
            )
        approval = self.approvals.status(approval_id)
        if approval.status != "decided" or approval.decision_ref is None:
            raise ExecutionApprovalError("execution approval is not decided")
        raw_decision = self.artifacts.read(approval.decision_ref)
        decision = HumanDecision.model_validate_json(raw_decision, strict=True)
        if decision.selected_option not in {
            "authorize_execution",
            "authorize_execution_with_exception",
        }:
            raise ExecutionApprovalError("human decision did not authorize execution")
        try:
            request_approval = ApprovalRequest.model_validate_json(
                self.artifacts.read(approval.approval_request_ref), strict=True
            )
        except ValidationError as error:
            raise ExecutionApprovalError("execution approval request is invalid") from error
        if decision.approval_request_ref != approval.approval_request_ref:
            raise ExecutionApprovalError(
                "execution decision does not bind the stored approval request"
            )
        if request_approval.kind != "execution_authorization":
            raise ExecutionApprovalError("approval is not an execution authorization")
        if request_approval.compiled_identity != compiled_identity:
            raise ExecutionApprovalError(
                "execution approval compiled identity is missing or changed"
            )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row(connection, execution_id)
            request_ref = _parse_ref(row["request_ref_json"])
            payload_ref = _parse_ref(row["payload_ref_json"])
            exact_subjects = (request_ref, payload_ref)
            if (
                request_approval.subject_refs != exact_subjects
                or decision.subject_refs != exact_subjects
            ):
                raise ExecutionApprovalError(
                    "human decision does not bind the exact request and payload"
                )
            payload = self.artifacts.read(payload_ref)
            directory = self.exchange_root / execution_id
            descriptor = _payload_descriptor(
                directory / "payload.bin",
                payload,
                media_type=self.artifacts.catalog(payload_ref).media_type,
            )
            if row["state"] == "authorized":
                existing_decision = _parse_optional_ref(row["decision_ref_json"])
                if existing_decision != approval.decision_ref:
                    raise ExecutionStateConflict(
                        "execution was authorized by a different decision"
                    )
                _read_descriptor(descriptor)
                connection.execute("ROLLBACK")
                return descriptor
            if row["state"] != "created":
                raise ExecutionStateConflict(
                    "execution is not authorizable from current state"
                )
            directory.mkdir(mode=0o770, exist_ok=False)
            _write_readonly(Path(descriptor.local_path), payload)
            connection.execute(
                """
                UPDATE executions
                SET state = 'authorized', decision_ref_json = ?
                WHERE execution_id = ?
                """,
                (approval.decision_ref.canonical_json(), execution_id),
            )
            connection.execute("COMMIT")
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()
        return descriptor

    def record_submission(self, *, execution_id: str, external_run_id: str) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row(connection, execution_id)
            if (
                row["state"] in {
                    "submitted",
                    "running",
                    "cancelling",
                    "succeeded",
                    "failed",
                    "cancelled",
                    "collected",
                }
                and row["external_run_id"] == external_run_id
            ):
                connection.execute("ROLLBACK")
                return
            if row["state"] != "authorized":
                raise ExecutionStateConflict("execution is not submittable from current state")
            connection.execute(
                "UPDATE executions SET state = 'submitted', external_run_id = ? WHERE execution_id = ?",
                (external_run_id, execution_id),
            )
            connection.execute("COMMIT")

    def abandon(self, execution_id: str) -> None:
        """Permanently prevent an unsubmitted execution from being authorized."""

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row(connection, execution_id)
            if row["state"] == "abandoned":
                connection.execute("ROLLBACK")
                return
            if row["state"] not in {"created", "authorized"}:
                raise ExecutionStateConflict(
                    "only an unsubmitted execution can be abandoned"
                )
            connection.execute(
                "UPDATE executions SET state = 'abandoned' WHERE execution_id = ?",
                (execution_id,),
            )
            connection.execute("COMMIT")

    def record_status(
        self, *, execution_id: str, external_run_id: str, state: str
    ) -> None:
        normalized = {
            "accepted": "submitted",
            "running": "running",
            "succeeded": "succeeded",
            "failed": "failed",
            "cancelled": "cancelled",
            "cancelling": "cancelling",
        }.get(state)
        if normalized is None:
            raise ValueError("unknown executor state")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row(connection, execution_id)
            if row["external_run_id"] != external_run_id:
                raise ExecutionStateConflict("external run identity differs from submission")
            allowed = {
                "submitted": {"submitted", "running", "cancelling", "succeeded", "failed", "cancelled"},
                "running": {"running", "cancelling", "succeeded", "failed", "cancelled"},
                "cancelling": {"cancelling", "succeeded", "failed", "cancelled"},
            }
            if normalized not in allowed.get(row["state"], set()):
                raise ExecutionStateConflict("executor status is not a valid transition")
            connection.execute(
                "UPDATE executions SET state = ? WHERE execution_id = ?",
                (normalized, execution_id),
            )
            connection.execute("COMMIT")

    def ingest_result(
        self,
        *,
        execution_id: str,
        external_run_id: str,
        outputs: tuple[LocalFileDescriptor, ...],
    ) -> ArtifactRef:
        with self._connect() as connection:
            row = self._row(connection, execution_id)
        if row["external_run_id"] != external_run_id:
            raise ExecutionStateConflict("external run identity differs from submission")
        if row["state"] not in {"succeeded", "failed", "cancelled"}:
            raise ExecutionStateConflict("execution is not terminal")
        if len({item.name for item in outputs}) != len(outputs):
            raise ExecutionServiceError("result names must be unique")
        request_ref = _parse_ref(row["request_ref_json"])
        payload_ref = _parse_ref(row["payload_ref_json"])
        output_refs = []
        for descriptor in outputs:
            content = _read_descriptor(descriptor)
            output_refs.append(
                self.artifacts.register(
                    content,
                    ArtifactRegistration(
                        kind="execution_output",
                        schema_id="opaque",
                        payload_schema_version=1,
                        media_type=descriptor.media_type,
                        creator=self.service_actor,
                        parent_refs=(request_ref, payload_ref),
                        labels={"execution_id": execution_id, "logical_name": descriptor.name},
                    ),
                    idempotency_key=f"execution:{execution_id}:output:{descriptor.name}",
                ).ref
            )
        manifest = ExecutionResultManifest(
            execution_id=execution_id,
            external_run_id=external_run_id,
            terminal_state=row["state"],
            output_refs=tuple(output_refs),
            collected_at=_timestamp(),
        )
        result_ref = self.artifacts.register(
            manifest.canonical_json(),
            ArtifactRegistration(
                kind="execution_result",
                schema_id="scidiscovery.execution-result",
                payload_schema_version=1,
                media_type="application/json",
                creator=self.service_actor,
                parent_refs=(request_ref, payload_ref, *output_refs),
            ),
            idempotency_key=f"execution:{execution_id}:result",
        ).ref
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = self._row(connection, execution_id)
            if current["state"] != row["state"]:
                raise ExecutionStateConflict("execution changed during result ingestion")
            connection.execute(
                "UPDATE executions SET state = 'collected', result_ref_json = ? WHERE execution_id = ?",
                (result_ref.canonical_json(), execution_id),
            )
            connection.execute("COMMIT")
        return result_ref

    def status(self, execution_id: str) -> ExecutionStatusView:
        with self._connect() as connection:
            row = self._row(connection, execution_id)
        return ExecutionStatusView(
            execution_id=execution_id,
            executor=row["executor"],
            state=row["state"],
            external_run_id=row["external_run_id"],
            result_ref=_parse_optional_ref(row["result_ref_json"]),
            created_at=row["created_at"],
        )

    def list_statuses(
        self, *, state: str | None = None, limit: int = 50
    ) -> tuple[ExecutionStatusView, ...]:
        """Return a bounded newest-first recovery view."""

        allowed = {
            "created",
            "authorized",
            "submitted",
            "running",
            "succeeded",
            "failed",
            "cancelled",
            "cancelling",
            "collected",
            "abandoned",
        }
        if state is not None and state not in allowed:
            raise ValueError("unknown execution state")
        if not 1 <= limit <= 100:
            raise ValueError("execution list limit must be between 1 and 100")
        query = "SELECT execution_id FROM executions"
        parameters: tuple[object, ...]
        if state is None:
            query += " ORDER BY created_at DESC LIMIT ?"
            parameters = (limit,)
        else:
            query += " WHERE state = ? ORDER BY created_at DESC LIMIT ?"
            parameters = (state, limit)
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return tuple(self.status(row["execution_id"]) for row in rows)

    def outputs(self, execution_id: str) -> tuple[ExecutionOutputView, ...]:
        """Resolve collected outputs without exposing their payload bytes."""

        status = self.status(execution_id)
        if status.state != "collected" or status.result_ref is None:
            raise ExecutionStateConflict("execution outputs require collected state")
        try:
            manifest = ExecutionResultManifest.model_validate_json(
                self.artifacts.read(status.result_ref), strict=True
            )
        except ValidationError as error:
            raise ExecutionServiceError("stored execution result is invalid") from error
        if manifest.execution_id != execution_id:
            raise ExecutionServiceError("execution result identity differs")
        result = []
        names = set()
        for reference in manifest.output_refs:
            envelope = self.artifacts.catalog(reference)
            logical_name = envelope.labels.get("logical_name")
            if not logical_name or logical_name in names:
                raise ExecutionServiceError("execution output logical names are invalid")
            names.add(logical_name)
            result.append(
                ExecutionOutputView(
                    logical_name=logical_name,
                    artifact_id=envelope.artifact_id,
                    media_type=envelope.media_type,
                    size_bytes=envelope.size_bytes,
                )
            )
        return tuple(result)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS executions (
                    execution_id TEXT PRIMARY KEY,
                    executor TEXT NOT NULL,
                    request_ref_json BLOB NOT NULL,
                    payload_ref_json BLOB NOT NULL,
                    state TEXT NOT NULL,
                    decision_ref_json BLOB,
                    external_run_id TEXT UNIQUE,
                    result_ref_json BLOB,
                    created_at TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _row(connection: sqlite3.Connection, execution_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM executions WHERE execution_id = ?", (execution_id,)
        ).fetchone()
        if row is None:
            raise ExecutionServiceError("execution does not exist")
        return row


def _write_readonly(path: Path, content: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o440)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _payload_descriptor(
    path: Path,
    payload: bytes,
    *,
    media_type: str,
) -> LocalFileDescriptor:
    return LocalFileDescriptor(
        name="execution_payload",
        local_path=str(path),
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
        media_type=media_type,
    )


def _read_descriptor(descriptor: LocalFileDescriptor) -> bytes:
    path = Path(descriptor.local_path).absolute()
    metadata = os.lstat(path)
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ExecutionServiceError("result path is not a regular non-symlink file")
    content = path.read_bytes()
    if len(content) != descriptor.size_bytes or hashlib.sha256(content).hexdigest() != descriptor.sha256:
        raise ExecutionServiceError("result bytes differ from descriptor")
    return content


def _parse_ref(raw: bytes | str) -> ArtifactRef:
    try:
        return ArtifactRef.model_validate_json(raw, strict=True)
    except ValidationError as error:
        raise ExecutionServiceError("stored artifact reference is invalid") from error


def _parse_optional_ref(raw: bytes | str | None) -> ArtifactRef | None:
    return None if raw is None else _parse_ref(raw)


def _timestamp(value: datetime | None = None) -> str:
    return (value or datetime.now(timezone.utc)).isoformat(timespec="microseconds").replace("+00:00", "Z")


__all__ = [
    "ExecutionApprovalError",
    "ExecutionService",
    "ExecutionServiceError",
    "ExecutionOutputView",
    "ExecutionStateConflict",
    "ExecutionStatusView",
]
