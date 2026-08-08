"""Control-owned task scheduling and worker lifecycle."""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import stat
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from importlib import import_module
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..schema.artifact import ArtifactRegistration
from ..schema.common import canonical_json
from ..schema.refs import ActorRef, ArtifactRef
from ..schema.task import (
    AgentTask,
    AssignmentInput,
    AssignmentOutput,
    SchedulerSignal,
    TaskBudget,
    TaskEvent,
    TaskInput,
    TaskOutputSpec,
    WorkerAssignment,
)
from ..schema.cognitive import CriticReview, EvidenceAudit, HypothesisProposal
from ..schema.role_result import parse_role_result
from ..schema.scientific_foundation import ScientificFoundation
from ..schema.validation import ValidationReport
from ..schema.layered_diagnosis import LayeredDiagnosisReport
from ..schema.research_cycle import ScientificIntake
from ..schema.knowledge import KnowledgeUpdate
from ..schema.web_evidence import WebEvidenceSnapshot
from ..security.task_tokens import TaskTokenService
from .artifacts import ArtifactService
from ..context_policy import DEFAULT_CONTEXT_POLICIES, RoleContextPolicies


class TaskServiceError(RuntimeError):
    pass


class TaskNotReady(TaskServiceError):
    pass


class TaskStateConflict(TaskServiceError):
    pass


class TaskInputError(TaskServiceError):
    def __init__(
        self, message: str, *, details: tuple[dict[str, str], ...] = ()
    ) -> None:
        super().__init__(message)
        self.details = details


@dataclass(frozen=True)
class RoleOutputContract:
    kind: str
    format: str
    schema_id: str
    validator: str | None = None
    json_schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class DispatchTicket:
    role: str


@dataclass(frozen=True)
class TaskStatusView:
    task_id: str
    role: str
    state: str
    attempt: int
    output_ref: ArtifactRef | None
    scheduler_signal: SchedulerSignal | None
    reason: str | None
    readiness: str
    blocking_task_ids: tuple[str, ...]
    created_at: str
    lease_deadline_at: str | None
    absolute_deadline_at: str | None
    last_activity_at: str | None
    last_activity: str | None


@dataclass(frozen=True)
class TaskWebEvidenceView:
    source_key: str
    snapshot_ref: ArtifactRef
    original_url: str
    final_url: str
    accessed_at: str
    media_type: str


class TaskService:
    """Own every task identity and expose no identity-writing worker operation."""

    def __init__(
        self,
        *,
        artifacts: ArtifactService,
        tokens: TaskTokenService,
        database_path: Path | str,
        service_actor: ActorRef,
        role_output_contracts: dict[str, RoleOutputContract],
        role_context_policies: dict[str, RoleContextPolicies] | None = None,
    ) -> None:
        self.artifacts = artifacts
        self.tokens = tokens
        self.database_path = Path(database_path).expanduser().absolute()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.service_actor = service_actor
        if not role_output_contracts:
            raise ValueError("at least one role output contract is required")
        self.role_output_contracts = dict(role_output_contracts)
        self.role_context_policies = {
            role: (role_context_policies or {}).get(role, DEFAULT_CONTEXT_POLICIES)
            for role in self.role_output_contracts
        }
        self.workspace_root = artifacts.cas.root.parent / "workspaces"
        self.workspace_root.mkdir(parents=True, exist_ok=True, mode=0o750)
        self._initialize()

    def schedule(
        self,
        *,
        role: str,
        context_profile: str = "default",
        instruction: str,
        inputs: tuple[TaskInput, ...],
        dependency_task_ids: tuple[str, ...] = (),
        output: TaskOutputSpec,
        budget: TaskBudget,
    ) -> str:
        if not role or not instruction.strip():
            raise ValueError("role and instruction are required")
        contract = self.output_contract(role)
        resolved_profile, context_policy = self._context_policy(
            role, context_profile
        )
        self._validate_context(inputs, context_policy)
        if (
            output.kind != contract.kind
            or output.format != contract.format
            or output.schema_id != contract.schema_id
            or output.validator != contract.validator
        ):
            raise ValueError("task output differs from the registered role contract")
        for item in inputs:
            self.artifacts.verify(item.artifact_ref)
        dependency_refs = tuple(self._task_ref(value) for value in dependency_task_ids)
        task_id = f"tsk_{uuid.uuid4().hex}"
        instruction_ref = self.artifacts.register(
            instruction.encode("utf-8"),
            ArtifactRegistration(
                kind="task_instruction",
                schema_id="opaque",
                payload_schema_version=1,
                media_type="text/plain; charset=utf-8",
                creator=self.service_actor,
                confidentiality="task_private",
            ),
            idempotency_key=f"task:{task_id}:instruction",
        ).ref
        task = AgentTask(
            task_id=task_id,
            role=role,
            context_profile=resolved_profile,
            instruction_ref=instruction_ref,
            inputs=inputs,
            dependency_task_ids=dependency_task_ids,
            output=output,
            budget=budget,
            created_at=_timestamp(),
        )
        parents = (instruction_ref,) + tuple(item.artifact_ref for item in inputs) + dependency_refs
        task_ref = self.artifacts.register(
            task.canonical_json(),
            ArtifactRegistration(
                kind="agent_task",
                schema_id="scidiscovery.agent-task",
                payload_schema_version=1,
                media_type="application/json",
                creator=self.service_actor,
                parent_refs=parents,
                labels={"role": role},
                confidentiality="task_private",
            ),
            idempotency_key=f"task:{task_id}:record",
        ).ref
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO tasks (
                    task_id, task_ref_json, role, state, attempt, created_at
                ) VALUES (?, ?, ?, 'created', 0, ?)
                """,
                (task_id, task_ref.canonical_json(), role, task.created_at),
            )
            self._append_event(connection, task_id, "created", attempt=0)
        return task_id

    def ready(self) -> tuple[str, ...]:
        self._reconcile_expired()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT task_id FROM tasks WHERE state = 'created' ORDER BY created_at"
            ).fetchall()
        return tuple(
            row["task_id"] for row in rows if self._dependencies_complete(row["task_id"])
        )

    def list_statuses(
        self, *, state: str | None = None, limit: int = 50
    ) -> tuple[TaskStatusView, ...]:
        """Return a bounded newest-first recovery view."""

        allowed = {"created", "dispatched", "claimed", "completed", "failed", "timed_out"}
        if state is not None and state not in allowed:
            raise ValueError("unknown task state")
        if not 1 <= limit <= 100:
            raise ValueError("task list limit must be between 1 and 100")
        self._reconcile_expired()
        query = "SELECT task_id FROM tasks"
        parameters: tuple[object, ...]
        if state is None:
            query += " ORDER BY created_at DESC LIMIT ?"
            parameters = (limit,)
        else:
            query += " WHERE state = ? ORDER BY created_at DESC LIMIT ?"
            parameters = (state, limit)
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return tuple(self.status(row["task_id"]) for row in rows)

    def prepare_dispatch(self, task_id: str, *, ttl_seconds: int = 900) -> DispatchTicket:
        self._reconcile_expired(task_id)
        task = self.get_task(task_id)
        self._require_current_output_contract(task)
        readiness, blockers = self._dependency_readiness(task)
        if blockers:
            raise TaskNotReady("task dependency is terminal or blocked")
        if readiness != "ready":
            raise TaskNotReady("task dependencies are not complete")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row(connection, task_id)
            if row["state"] != "created":
                raise TaskStateConflict(f"task is not dispatchable from {row['state']}")
            attempt = int(row["attempt"]) + 1
            if attempt > task.budget.max_attempts:
                raise TaskStateConflict("task attempt budget is exhausted")
            effective_ttl = min(ttl_seconds, task.budget.timeout_seconds)
            dispatched_at = _timestamp()
            deadline_at = _timestamp(
                _parse_timestamp(dispatched_at) + timedelta(seconds=effective_ttl)
            )
            instance_id = f"asi_{uuid.uuid4().hex}"
            connection.execute(
                """
                INSERT INTO assignment_instances (
                    instance_id, task_id, role, attempt, state, created_at
                ) VALUES (?, ?, ?, ?, 'queued', ?)
                """,
                (instance_id, task_id, task.role, attempt, dispatched_at),
            )
            connection.execute(
                """
                UPDATE tasks
                SET state = 'dispatched', attempt = ?, deadline_at = ?
                WHERE task_id = ?
                """,
                (attempt, deadline_at, task_id),
            )
            self._append_event(connection, task_id, "dispatched", attempt=attempt)
            self._append_activity(
                connection, task_id, attempt, "dispatched", dispatched_at
            )
            connection.execute("COMMIT")
        return DispatchTicket(role=task.role)

    def claim_next(self, *, worker_id: str, proxy_id: str) -> str:
        """Atomically bind the next queued role assignment to one worker proxy."""

        self._reconcile_expired()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT i.instance_id, i.task_id, i.attempt, t.task_ref_json
                FROM assignment_instances AS i
                JOIN tasks AS t ON t.task_id = i.task_id
                WHERE i.state = 'queued' AND i.role = ?
                  AND t.state = 'dispatched' AND t.attempt = i.attempt
                ORDER BY i.created_at, i.instance_id
                LIMIT 1
                """,
                (worker_id,),
            ).fetchone()
            if row is None:
                raise TaskNotReady("no queued assignment is available for this worker role")
            task_id = row["task_id"]
            attempt = int(row["attempt"])
            task = self.get_task(task_id)
            self._require_current_output_contract(task)
            handle = self.tokens.issue(
                task_id=task_id,
                task_ref=_parse_ref(row["task_ref_json"]),
                worker_id=worker_id,
                attempt=attempt,
                ttl_seconds=task.budget.timeout_seconds,
            )
            session_token = self.tokens.claim(
                handle,
                worker_id=worker_id,
                session_ttl_seconds=task.budget.timeout_seconds,
            )
            session = self.tokens.verify_session(session_token, worker_id=worker_id)
            now = datetime.now(timezone.utc)
            absolute_deadline = session.expires_at
            lease_deadline = _timestamp(
                min(
                    now + timedelta(seconds=_lease_seconds(task.budget.timeout_seconds)),
                    _parse_timestamp(absolute_deadline),
                )
            )
            connection.execute(
                """
                UPDATE tasks
                SET state = 'claimed', started_at = ?, deadline_at = ?,
                    absolute_deadline_at = ?, last_activity_at = ?,
                    last_activity = 'claimed'
                WHERE task_id = ?
                """,
                (
                    _timestamp(now),
                    lease_deadline,
                    absolute_deadline,
                    _timestamp(now),
                    task_id,
                ),
            )
            connection.execute(
                """
                UPDATE assignment_instances
                SET state = 'bound', proxy_id = ?, session_id = ?, bound_at = ?
                WHERE instance_id = ? AND state = 'queued'
                """,
                (proxy_id, session.session_id, _timestamp(now), row["instance_id"]),
            )
            self._append_event(
                connection, task_id, "claimed", attempt=attempt
            )
            self._append_activity(
                connection, task_id, attempt, "claimed", _timestamp(now)
            )
            connection.execute("COMMIT")
        return session_token

    def heartbeat(
        self, session_token: str, *, worker_id: str
    ) -> tuple[str, str]:
        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        task = self.get_task(session.task_id)
        now = datetime.now(timezone.utc)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row(connection, session.task_id)
            if row["state"] != "claimed" or int(row["attempt"]) != session.attempt:
                raise TaskStateConflict("worker session is not the active claimed attempt")
            absolute_deadline = row["absolute_deadline_at"]
            if absolute_deadline is None:
                raise TaskServiceError("claimed task has no absolute deadline")
            lease_deadline = _timestamp(
                min(
                    now + timedelta(seconds=_lease_seconds(task.budget.timeout_seconds)),
                    _parse_timestamp(absolute_deadline),
                )
            )
            connection.execute(
                """
                UPDATE tasks
                SET deadline_at = ?, last_activity_at = ?, last_activity = 'heartbeat'
                WHERE task_id = ?
                """,
                (lease_deadline, _timestamp(now), session.task_id),
            )
            connection.execute("COMMIT")
        return lease_deadline, absolute_deadline

    def record_activity(
        self, session_token: str, *, worker_id: str, activity: str
    ) -> None:
        """Record one successful worker phase without scientific details."""

        allowed = {
            "assignment_read",
            "assignment_materialized",
            "inputs_listed",
            "input_read",
            "input_staged",
            "pdf_extracted",
            "table_read",
            "input_profiled",
            "deterministic_analysis_completed",
            "web_evidence_frozen",
            "output_validated",
            "output_rejected",
        }
        if activity not in allowed:
            raise ValueError("unknown worker activity")
        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        recorded_at = _timestamp()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE tasks
                SET last_activity_at = ?, last_activity = ?
                WHERE task_id = ? AND state = 'claimed' AND attempt = ?
                """,
                (recorded_at, activity, session.task_id, session.attempt),
            )
            self._append_activity(
                connection, session.task_id, session.attempt, activity, recorded_at
            )
            connection.execute("COMMIT")

    def assignment(self, session_token: str, *, worker_id: str) -> WorkerAssignment:
        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        task = self.get_task(session.task_id)
        self._require_current_output_contract(task)
        instruction = self.artifacts.read(task.instruction_ref).decode("utf-8")
        metadata = tuple(
            AssignmentInput(
                name=item.name,
                media_type=self.artifacts.catalog(item.artifact_ref).media_type,
                size_bytes=self.artifacts.catalog(item.artifact_ref).size_bytes,
                exposure=item.exposure,
                access_modes=(
                    ()
                    if item.exposure == "handoff_only"
                    else _input_access_modes(
                        self.artifacts.catalog(item.artifact_ref).media_type
                    )
                ),
                handoff=(
                    self._scheduler_signal_for_output(item.artifact_ref)
                    if item.exposure == "handoff_only"
                    else None
                ),
            )
            for item in task.inputs
        )
        contract = self.output_contract(task.role)
        return WorkerAssignment(
            role=task.role,
            context_profile=task.context_profile,
            instruction=instruction,
            inputs=metadata,
            output=AssignmentOutput(
                format=task.output.format,
                media_type=task.output.media_type,
                max_bytes=task.output.max_bytes,
                json_schema=contract.json_schema or {},
            ),
            capabilities=WORKER_CAPABILITIES,
            lease_seconds=_lease_seconds(task.budget.timeout_seconds),
        )

    def read_input(
        self, session_token: str, *, worker_id: str, name: str
    ) -> tuple[str, str, bytes]:
        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        task = self.get_task(session.task_id)
        matches = tuple(item for item in task.inputs if item.name == name)
        if len(matches) != 1:
            raise TaskInputError("input name is not bound to this task")
        item = matches[0]
        if item.exposure == "handoff_only":
            raise TaskInputError("input is handoff-only and cannot be read")
        envelope = self.artifacts.verify(item.artifact_ref)
        return item.name, envelope.media_type, self.artifacts.read(item.artifact_ref)

    def stage_input(
        self, session_token: str, *, worker_id: str, name: str
    ) -> tuple[str, str, int]:
        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        input_name, media_type, content = self.read_input(
            session_token, worker_id=worker_id, name=name
        )
        directory = self.workspace_root / session.session_id
        directory.mkdir(mode=0o750, exist_ok=True)
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", input_name)
        destination = directory / safe_name
        if destination.exists():
            if destination.read_bytes() != content:
                raise TaskInputError("staged input differs from immutable source")
        else:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{safe_name}.", dir=directory
            )
            temporary = Path(temporary_name)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.chmod(temporary, 0o440)
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)
        return str(destination), media_type, len(content)

    def materialize_assignment(
        self, session_token: str, *, worker_id: str
    ) -> dict[str, str]:
        """Materialize one identity-free, task-local file exchange."""

        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        task = self.get_task(session.task_id)
        assignment = self.assignment(session_token, worker_id=worker_id)
        workspace = self.workspace_root / session.session_id
        inputs_directory = workspace / "inputs"
        schema_directory = workspace / "schema"
        output_directory = workspace / "output"
        for directory, mode in (
            (inputs_directory, 0o750),
            (schema_directory, 0o750),
            (output_directory, 0o700),
        ):
            directory.mkdir(parents=True, mode=mode, exist_ok=True)

        entries: list[dict[str, Any]] = []
        task_inputs = {item.name: item for item in task.inputs}
        for metadata in assignment.inputs:
            entry: dict[str, Any] = {
                "source_name": metadata.name,
                "media_type": metadata.media_type,
                "size_bytes": metadata.size_bytes,
                "exposure": metadata.exposure,
                "access_modes": list(metadata.access_modes),
            }
            if metadata.exposure == "handoff_only":
                entry["handoff"] = (
                    metadata.handoff.model_dump(mode="json")
                    if metadata.handoff is not None
                    else None
                )
            else:
                item = task_inputs[metadata.name]
                content = self.artifacts.read(item.artifact_ref)
                relative_path = Path("inputs") / _task_input_filename(
                    metadata.name, metadata.media_type
                )
                _write_immutable_file(workspace / relative_path, content)
                entry["relative_path"] = relative_path.as_posix()
            entries.append(entry)

        schema_relative_path = Path("schema/output.schema.json")
        _write_immutable_file(
            workspace / schema_relative_path,
            canonical_json(assignment.output.json_schema),
        )
        output_relative_path = Path("output/result.json")
        manifest = {
            "schema_version": 1,
            "role": assignment.role,
            "context_profile": assignment.context_profile,
            "instruction": assignment.instruction,
            "inputs": entries,
            "output": {
                "format": assignment.output.format,
                "media_type": assignment.output.media_type,
                "max_bytes": assignment.output.max_bytes,
                "relative_path": output_relative_path.as_posix(),
                "schema_relative_path": schema_relative_path.as_posix(),
                "protocol": assignment.output.protocol,
            },
            "capabilities": list(assignment.capabilities),
            "lease_seconds": assignment.lease_seconds,
        }
        assignment_path = workspace / "assignment.json"
        _write_immutable_file(assignment_path, canonical_json(manifest))
        return {
            "workspace_path": str(workspace),
            "assignment_path": str(assignment_path),
            "output_path": str(workspace / output_relative_path),
        }

    def validate_output_file(
        self, session_token: str, *, worker_id: str
    ) -> tuple[bool, int | None, tuple[dict[str, str], ...]]:
        content = self._read_output_file(session_token, worker_id=worker_id)
        return self.validate_output(
            session_token, worker_id=worker_id, content=content
        )

    def finalize_file(
        self,
        session_token: str,
        *,
        worker_id: str,
    ) -> None:
        content = self._read_output_file(session_token, worker_id=worker_id)
        self.finalize(
            session_token,
            worker_id=worker_id,
            content=content,
        )

    def _read_output_file(self, session_token: str, *, worker_id: str) -> Any:
        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        task = self.get_task(session.task_id)
        path = self.workspace_root / session.session_id / "output/result.json"
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags)
        except OSError as error:
            raise TaskInputError(
                "worker output must be one regular file at output/result.json"
            ) from error
        try:
            details = os.fstat(descriptor)
            if not stat.S_ISREG(details.st_mode):
                raise TaskInputError("worker output must be one regular file")
            if details.st_size > task.output.max_bytes:
                raise TaskInputError("worker output exceeds its byte limit")
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                raw = stream.read(task.output.max_bytes + 1)
        finally:
            os.close(descriptor)
        if len(raw) > task.output.max_bytes:
            raise TaskInputError("worker output exceeds its byte limit")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise TaskInputError("worker output is not valid UTF-8") from error
        if task.output.format == "text":
            return text
        try:
            return json.loads(text)
        except json.JSONDecodeError as error:
            raise TaskInputError(
                "worker output is not valid JSON",
                details=(
                    {
                        "path": "$",
                        "message": str(error),
                        "type": "json_invalid",
                    },
                ),
            ) from error

    def analysis_directory(
        self, session_token: str, *, worker_id: str
    ) -> Path:
        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        directory = self.workspace_root / session.session_id
        directory.mkdir(mode=0o750, exist_ok=True)
        return directory

    def web_evidence_for_url(
        self, session_token: str, *, worker_id: str, original_url: str
    ) -> tuple[TaskWebEvidenceView, bytes] | None:
        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM task_web_evidence
                WHERE task_id = ? AND attempt = ? AND original_url = ?
                """,
                (session.task_id, session.attempt, original_url),
            ).fetchone()
        if row is None:
            return None
        view, raw = self._load_web_evidence_row(row)
        return view, raw

    def register_web_evidence(
        self,
        session_token: str,
        *,
        worker_id: str,
        original_url: str,
        final_url: str,
        accessed_at: str,
        http_status: int,
        media_type: str,
        body: bytes,
    ) -> TaskWebEvidenceView:
        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        existing = self.web_evidence_for_url(
            session_token, worker_id=worker_id, original_url=original_url
        )
        if existing is not None:
            return existing[0]
        task = self.get_task(session.task_id)
        task_ref = self._task_ref(session.task_id)
        with self._connect() as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM task_web_evidence WHERE task_id = ? AND attempt = ?",
                (session.task_id, session.attempt),
            ).fetchone()[0]
        source_key = f"web_{int(count) + 1}"
        response_ref = self.artifacts.register(
            body,
            ArtifactRegistration(
                kind="web_response",
                schema_id="opaque",
                payload_schema_version=1,
                media_type=media_type,
                creator=self.service_actor,
                task_ref=task_ref,
                labels={"source_key": source_key},
                confidentiality="task_private",
            ),
            idempotency_key=(
                f"task:{session.task_id}:web:{session.attempt}:{source_key}:response"
            ),
        ).ref
        snapshot = WebEvidenceSnapshot(
            original_url=original_url,
            final_url=final_url,
            accessed_at=accessed_at,
            http_status=http_status,
            media_type=media_type,
            response_ref=response_ref,
        )
        snapshot_ref = self.artifacts.register(
            snapshot.canonical_json(),
            ArtifactRegistration(
                kind="web_evidence_snapshot",
                schema_id="scidiscovery.web-evidence-snapshot",
                payload_schema_version=1,
                media_type="application/json",
                creator=self.service_actor,
                parent_refs=(response_ref,),
                task_ref=task_ref,
                labels={"source_key": source_key},
                confidentiality="task_private",
            ),
            idempotency_key=(
                f"task:{session.task_id}:web:{session.attempt}:{source_key}:snapshot"
            ),
        ).ref
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO task_web_evidence (
                    task_id, attempt, source_key, original_url,
                    snapshot_ref_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session.task_id,
                    session.attempt,
                    source_key,
                    original_url,
                    snapshot_ref.canonical_json(),
                    accessed_at,
                ),
            )
        return TaskWebEvidenceView(
            source_key=source_key,
            snapshot_ref=snapshot_ref,
            original_url=original_url,
            final_url=final_url,
            accessed_at=accessed_at,
            media_type=media_type,
        )

    def list_web_evidence(self, task_id: str) -> tuple[TaskWebEvidenceView, ...]:
        self.get_task(task_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM task_web_evidence
                WHERE task_id = ? ORDER BY attempt, source_key
                """,
                (task_id,),
            ).fetchall()
        return tuple(self._load_web_evidence_row(row)[0] for row in rows)

    def finalize(
        self,
        session_token: str,
        *,
        worker_id: str,
        content: Any,
    ) -> None:
        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        task = self.get_task(session.task_id)
        self._require_current_output_contract(task)
        raw, web_refs, signal = self._validate_complete_output(
            task, attempt=session.attempt, content=content
        )
        task_ref = self._task_ref(task.task_id)
        parents = (
            (task.instruction_ref,)
            + tuple(item.artifact_ref for item in task.inputs)
            + web_refs
        )
        output_ref = self.artifacts.register(
            raw,
            ArtifactRegistration(
                kind=task.output.kind,
                schema_id=task.output.schema_id,
                payload_schema_version=1,
                media_type=task.output.media_type,
                creator=ActorRef(actor_id=worker_id, actor_type="agent_worker"),
                parent_refs=parents,
                task_ref=task_ref,
                labels={"role": task.role, "attempt": str(session.attempt)},
                confidentiality="task_private",
            ),
            idempotency_key=f"task:{task.task_id}:output:{session.attempt}",
        ).ref
        signal_ref = self.artifacts.register(
            signal.canonical_json(),
            ArtifactRegistration(
                kind="scheduler_signal",
                schema_id="scidiscovery.scheduler-signal",
                payload_schema_version=1,
                media_type="application/json",
                creator=ActorRef(actor_id=worker_id, actor_type="agent_worker"),
                parent_refs=(output_ref,),
                task_ref=task_ref,
                labels={"role": task.role, "attempt": str(session.attempt)},
                confidentiality="task_private",
            ),
            idempotency_key=f"task:{task.task_id}:signal:{session.attempt}",
        ).ref
        finalized_at = _timestamp()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row(connection, task.task_id)
            if row["state"] == "completed":
                existing = _parse_optional_ref(row["output_ref_json"])
                if existing != output_ref:
                    raise TaskStateConflict("task already completed with different output")
                connection.execute("ROLLBACK")
                return
            if row["state"] != "claimed" or int(row["attempt"]) != session.attempt:
                raise TaskStateConflict("task is not finalizable from current state")
            connection.execute(
                """
                UPDATE tasks
                SET state = 'completed', output_ref_json = ?, scheduler_signal_ref_json = ?,
                    last_activity_at = ?, last_activity = 'finalized'
                WHERE task_id = ?
                """,
                (
                    output_ref.canonical_json(),
                    signal_ref.canonical_json(),
                    finalized_at,
                    task.task_id,
                ),
            )
            connection.execute(
                """
                UPDATE assignment_instances
                SET state = 'completed', completed_at = ?
                WHERE task_id = ? AND attempt = ? AND state = 'bound'
                """,
                (finalized_at, task.task_id, session.attempt),
            )
            self._append_event(
                connection,
                task.task_id,
                "completed",
                attempt=session.attempt,
                output_ref=output_ref,
            )
            self._append_activity(
                connection, task.task_id, session.attempt, "finalized", finalized_at
            )
            connection.execute("COMMIT")
        shutil.rmtree(self.workspace_root / session.session_id, ignore_errors=True)

    def validate_output(
        self, session_token: str, *, worker_id: str, content: Any
    ) -> tuple[bool, int | None, tuple[dict[str, str], ...]]:
        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        task = self.get_task(session.task_id)
        try:
            raw, _, _ = self._validate_complete_output(
                task, attempt=session.attempt, content=content
            )
        except TaskInputError as error:
            details = error.details or (
                {"path": "$", "message": str(error), "type": "value_error"},
            )
            return False, None, details
        return True, len(raw), ()

    def _validate_complete_output(
        self, task: AgentTask, *, attempt: int, content: Any
    ) -> tuple[bytes, tuple[ArtifactRef, ...], SchedulerSignal]:
        try:
            result = parse_role_result(content)
        except ValidationError as error:
            raise TaskInputError(
                "worker output must use the role result envelope",
                details=_validation_details(error),
            ) from error
        payload = result.payload
        try:
            raw = _encode_output(task.output, payload)
        except TaskInputError as error:
            raise TaskInputError(
                str(error), details=_prefix_validation_paths(error.details, "$.payload")
            ) from error
        web_refs = self._validate_scientific_sources(
            task, attempt=attempt, content=payload
        )
        handoff = result.handoff
        signal = SchedulerSignal(
            verdict=handoff.verdict,
            summary=handoff.summary,
            assumptions=handoff.assumptions,
            missing_inputs=handoff.missing_inputs,
            next_actions=handoff.next_actions,
        )
        return raw, web_refs, signal

    def output_contract(self, role: str) -> RoleOutputContract:
        try:
            return self.role_output_contracts[role]
        except KeyError as error:
            raise ValueError(f"unknown scientific role: {role}") from error

    def _require_current_output_contract(self, task: AgentTask) -> None:
        contract = self.output_contract(task.role)
        if (
            task.output.kind != contract.kind
            or task.output.format != contract.format
            or task.output.schema_id != contract.schema_id
            or task.output.validator != contract.validator
        ):
            raise TaskStateConflict(
                "task output contract is retired; create a new task under the current role contract"
            )

    def fail(
        self,
        task_id: str,
        *,
        reason: str,
        timed_out: bool = False,
        expected_state: str,
        expected_last_activity_at: str | None,
    ) -> None:
        state = "timed_out" if timed_out else "failed"
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row(connection, task_id)
            if row["state"] in {"completed", "failed", "timed_out"}:
                raise TaskStateConflict("task is already terminal")
            if (
                row["state"] != expected_state
                or row["last_activity_at"] != expected_last_activity_at
            ):
                raise TaskStateConflict(
                    "task changed since scheduler observation; refresh status before failing it"
                )
            connection.execute(
                "UPDATE tasks SET state = ?, reason = ? WHERE task_id = ?",
                (state, reason, task_id),
            )
            connection.execute(
                """
                UPDATE assignment_instances
                SET state = ?, completed_at = ?
                WHERE task_id = ? AND attempt = ?
                  AND state IN ('queued', 'bound')
                """,
                (state, _timestamp(), task_id, int(row["attempt"])),
            )
            self._append_event(
                connection,
                task_id,
                state,
                attempt=int(row["attempt"]),
                reason=reason,
            )
            connection.execute("COMMIT")

    def retry(self, task_id: str) -> int:
        task = self.get_task(task_id)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row(connection, task_id)
            if row["state"] not in {"failed", "timed_out"}:
                raise TaskStateConflict("only a failed task can be retried")
            attempt = int(row["attempt"])
            if attempt >= task.budget.max_attempts:
                raise TaskStateConflict("task attempt budget is exhausted")
            connection.execute(
                """
                UPDATE tasks
                SET state = 'created', output_ref_json = NULL,
                    scheduler_signal_ref_json = NULL, reason = NULL,
                    started_at = NULL, deadline_at = NULL,
                    absolute_deadline_at = NULL, last_activity_at = NULL,
                    last_activity = NULL
                WHERE task_id = ?
                """,
                (task_id,),
            )
            self._append_event(
                connection,
                task_id,
                "requeued",
                attempt=attempt,
                reason="retry requested after terminal attempt",
            )
            connection.execute("COMMIT")
        return attempt

    def status(self, task_id: str) -> TaskStatusView:
        self._reconcile_expired(task_id)
        with self._connect() as connection:
            row = self._row(connection, task_id)
        signal_ref = _parse_optional_ref(row["scheduler_signal_ref_json"])
        signal = None
        if signal_ref is not None:
            try:
                signal = SchedulerSignal.model_validate_json(
                    self.artifacts.read(signal_ref), strict=True
                )
            except ValidationError as error:
                raise TaskServiceError("stored scheduler signal is invalid") from error
        task = self.get_task(task_id)
        readiness, blockers = self._readiness(task, row["state"])
        return TaskStatusView(
            task_id=task_id,
            role=row["role"],
            state=row["state"],
            attempt=int(row["attempt"]),
            output_ref=_parse_optional_ref(row["output_ref_json"]),
            scheduler_signal=signal,
            reason=row["reason"],
            readiness=readiness,
            blocking_task_ids=blockers,
            created_at=row["created_at"],
            lease_deadline_at=row["deadline_at"],
            absolute_deadline_at=row["absolute_deadline_at"],
            last_activity_at=row["last_activity_at"],
            last_activity=row["last_activity"],
        )

    def performance(self, task_id: str) -> dict[str, Any]:
        """Return bounded, identity-free lifecycle and payload measurements."""

        task = self.get_task(task_id)
        with self._connect() as connection:
            row = self._row(connection, task_id)
            attempt = int(row["attempt"])
            activities = connection.execute(
                """
                SELECT activity, recorded_at
                FROM task_activity_events
                WHERE task_id = ? AND attempt = ?
                ORDER BY recorded_at, rowid
                """,
                (task_id, attempt),
            ).fetchall()
        phase_counts: dict[str, int] = {}
        phase_times: dict[str, dict[str, str]] = {}
        for activity in activities:
            phase = activity["activity"]
            recorded_at = activity["recorded_at"]
            phase_counts[phase] = phase_counts.get(phase, 0) + 1
            timing = phase_times.setdefault(
                phase, {"first_at": recorded_at, "last_at": recorded_at}
            )
            timing["last_at"] = recorded_at
        durations: dict[str, float] = {}
        _add_duration(durations, "dispatch_to_claim", phase_times, "dispatched", "claimed")
        _add_duration(durations, "claim_to_finalize", phase_times, "claimed", "finalized")
        _add_duration(
            durations,
            "deterministic_analysis_to_finalize",
            phase_times,
            "deterministic_analysis_completed",
            "finalized",
            start_edge="last_at",
        )
        if "finalized" in phase_times:
            durations["created_to_finalize"] = _seconds_between(
                task.created_at, phase_times["finalized"]["last_at"]
            )
        input_bytes = sum(
            self.artifacts.catalog(item.artifact_ref).size_bytes for item in task.inputs
        )
        exposure_counts = {
            exposure: sum(item.exposure == exposure for item in task.inputs)
            for exposure in ("full", "on_demand", "handoff_only")
        }
        readable_input_bytes = sum(
            self.artifacts.catalog(item.artifact_ref).size_bytes
            for item in task.inputs
            if item.exposure != "handoff_only"
        )
        output_ref = _parse_optional_ref(row["output_ref_json"])
        output_bytes = (
            self.artifacts.catalog(output_ref).size_bytes if output_ref is not None else None
        )
        return {
            "attempt": attempt,
            "input_count": len(task.inputs),
            "input_bytes": input_bytes,
            "readable_input_bytes": readable_input_bytes,
            "handoff_only_input_bytes": input_bytes - readable_input_bytes,
            "input_exposure_counts": exposure_counts,
            "output_bytes": output_bytes,
            "phase_counts": phase_counts,
            "phase_timestamps": phase_times,
            "schema_rejections": phase_counts.get("output_rejected", 0),
            "durations_seconds": durations,
        }

    def resolve_context_profile(self, role: str, requested: str | None) -> str:
        profile, _ = self._context_policy(role, requested)
        return profile

    def _context_policy(self, role: str, requested: str | None) -> tuple[str, Any]:
        self.output_contract(role)
        try:
            return self.role_context_policies[role].resolve(requested)
        except ValueError as error:
            raise TaskInputError(str(error)) from error

    def _validate_context(self, inputs: tuple[TaskInput, ...], policy: Any) -> None:
        if len(inputs) > policy.max_inputs:
            raise TaskInputError("task context exceeds the role input-count limit")
        by_name = {item.name: item for item in inputs}
        rules = {rule.source_name: rule for rule in policy.rules}
        missing = [
            rule.source_name
            for rule in policy.rules
            if rule.required and rule.source_name not in by_name
        ]
        if missing:
            raise TaskInputError(
                "task context is missing required sources: " + ", ".join(missing)
            )
        additional = sorted(set(by_name) - set(rules))
        if additional and not policy.allow_additional:
            raise TaskInputError(
                "task context contains undeclared sources: " + ", ".join(additional)
            )
        readable_bytes = 0
        for name, item in by_name.items():
            envelope = self.artifacts.catalog(item.artifact_ref)
            rule = rules.get(name)
            if rule is not None:
                if item.exposure != rule.exposure:
                    raise TaskInputError(
                        f"task source {name} must use {rule.exposure} exposure"
                    )
                if rule.schemas and envelope.schema_id not in rule.schemas:
                    raise TaskInputError(
                        f"task source {name} has an unsupported schema"
                    )
                if rule.max_bytes is not None and envelope.size_bytes > rule.max_bytes:
                    raise TaskInputError(
                        f"task source {name} exceeds its byte limit"
                    )
            if item.exposure == "handoff_only":
                if self._scheduler_signal_for_output(item.artifact_ref) is None:
                    raise TaskInputError(
                        f"task source {name} has no completed scheduler handoff"
                    )
            else:
                readable_bytes += envelope.size_bytes
        if readable_bytes > policy.max_readable_bytes:
            raise TaskInputError("task context exceeds the readable-byte limit")

    def get_task(self, task_id: str) -> AgentTask:
        ref = self._task_ref(task_id)
        raw = self.artifacts.read(ref)
        return _decode_agent_task(raw)

    def _dependencies_complete(self, task_id: str) -> bool:
        task = self.get_task(task_id)
        return all(self.status(value).state == "completed" for value in task.dependency_task_ids)

    def _dependency_readiness(self, task: AgentTask) -> tuple[str, tuple[str, ...]]:
        blockers: list[str] = []
        waiting = False
        for dependency_id in task.dependency_task_ids:
            dependency = self.status(dependency_id)
            if dependency.state in {"failed", "timed_out"} or dependency.readiness == "blocked_by_dependency":
                blockers.append(dependency_id)
            elif dependency.state != "completed":
                waiting = True
        if blockers:
            return "blocked_by_dependency", tuple(blockers)
        if waiting:
            return "waiting_for_dependencies", ()
        return "ready", ()

    def _readiness(self, task: AgentTask, state: str) -> tuple[str, tuple[str, ...]]:
        if state in {"completed", "failed", "timed_out"}:
            return "terminal", ()
        if state in {"dispatched", "claimed"}:
            return "active", ()
        return self._dependency_readiness(task)

    def _require_active_claim(self, task_id: str, attempt: int) -> None:
        view = self.status(task_id)
        if view.state != "claimed" or view.attempt != attempt:
            raise TaskStateConflict("worker session is not the active claimed attempt")

    def _reconcile_expired(self, task_id: str | None = None) -> None:
        now = _timestamp()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if task_id is None:
                rows = connection.execute(
                    """
                    SELECT task_id, attempt FROM tasks
                    WHERE state IN ('dispatched', 'claimed')
                      AND deadline_at IS NOT NULL AND deadline_at <= ?
                    """,
                    (now,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT task_id, attempt FROM tasks
                    WHERE task_id = ? AND state IN ('dispatched', 'claimed')
                      AND deadline_at IS NOT NULL AND deadline_at <= ?
                    """,
                    (task_id, now),
                ).fetchall()
            for row in rows:
                reason = "worker attempt exceeded its dispatch deadline"
                connection.execute(
                    "UPDATE tasks SET state = 'timed_out', reason = ? WHERE task_id = ?",
                    (reason, row["task_id"]),
                )
                connection.execute(
                    """
                    UPDATE assignment_instances
                    SET state = 'timed_out', completed_at = ?
                    WHERE task_id = ? AND attempt = ?
                      AND state IN ('queued', 'bound')
                    """,
                    (now, row["task_id"], int(row["attempt"])),
                )
                self._append_event(
                    connection,
                    row["task_id"],
                    "timed_out",
                    attempt=int(row["attempt"]),
                    reason=reason,
                )
            connection.execute("COMMIT")

    def _task_ref(self, task_id: str) -> ArtifactRef:
        with self._connect() as connection:
            row = self._row(connection, task_id)
        return _parse_ref(row["task_ref_json"])

    def _validate_scientific_sources(
        self, task: AgentTask, *, attempt: int, content: Any
    ) -> tuple[ArtifactRef, ...]:
        citation_path = "$.payload.evidence"
        if task.output.schema_id == "scidiscovery.hypothesis-proposal.v1":
            citations = HypothesisProposal.model_validate_json(
                canonical_json(content), strict=True
            ).evidence
        elif task.output.schema_id == "scidiscovery.critic-review.v1":
            citations = CriticReview.model_validate_json(
                canonical_json(content), strict=True
            ).evidence
        elif task.output.schema_id == "scidiscovery.evidence-audit.v1":
            citations = EvidenceAudit.model_validate_json(
                canonical_json(content), strict=True
            ).evidence
        elif task.output.schema_id == "scidiscovery.scientific-foundation.v1":
            citations = ScientificFoundation.model_validate_json(
                canonical_json(content), strict=True
            ).evidence
        elif task.output.schema_id == "scidiscovery.scientific-intake.v1":
            citations = ScientificIntake.model_validate_json(
                canonical_json(content), strict=True
            ).scientific_foundation.evidence
            citation_path = "$.payload.scientific_foundation.evidence"
        elif task.output.schema_id == "scidiscovery.validation-report.v1":
            citations = ValidationReport.model_validate_json(
                canonical_json(content), strict=True
            ).evidence
        elif task.output.schema_id == "scidiscovery.layered-diagnosis.v1":
            citations = LayeredDiagnosisReport.model_validate_json(
                canonical_json(content), strict=True
            ).evidence
        elif task.output.schema_id == "scidiscovery.knowledge-update.v1":
            citations = KnowledgeUpdate.model_validate_json(
                canonical_json(content), strict=True
            ).evidence
        else:
            return ()
        web = {
            value.source_key: value.snapshot_ref
            for value in self.list_web_evidence(task.task_id)
            if self._web_evidence_attempt(value.snapshot_ref) == attempt
        }
        inputs = {item.name for item in task.inputs}
        used_web = []
        for index, citation in enumerate(citations):
            if citation.source_type == "web_snapshot":
                try:
                    used_web.append(web[citation.source_key])
                except KeyError as error:
                    raise TaskInputError(
                        "scientific output references an unfrozen web source",
                        details=(
                            {
                                "path": f"{citation_path}[{index}].source_key",
                                "message": (
                                    "unknown task-local web source: "
                                    f"{citation.source_key}"
                                ),
                                "type": "value_error.source_binding",
                            },
                        ),
                    ) from error
            elif citation.source_type in {
                "frozen_input",
                "user_statement",
                "runtime_output",
            } and citation.source_key not in inputs:
                raise TaskInputError(
                    "scientific output references an unknown task-local source",
                    details=(
                        {
                            "path": f"{citation_path}[{index}].source_key",
                            "message": (
                                "unknown task-local input source: "
                                f"{citation.source_key}"
                            ),
                            "type": "value_error.source_binding",
                        },
                    ),
                )
        return tuple(dict.fromkeys(used_web))

    def _load_web_evidence_row(
        self, row: sqlite3.Row
    ) -> tuple[TaskWebEvidenceView, bytes]:
        snapshot_ref = _parse_ref(row["snapshot_ref_json"])
        try:
            snapshot = WebEvidenceSnapshot.model_validate_json(
                self.artifacts.read(snapshot_ref), strict=True
            )
        except ValidationError as error:
            raise TaskServiceError("stored web evidence snapshot is invalid") from error
        raw = self.artifacts.read(snapshot.response_ref)
        return (
            TaskWebEvidenceView(
                source_key=row["source_key"],
                snapshot_ref=snapshot_ref,
                original_url=snapshot.original_url,
                final_url=snapshot.final_url,
                accessed_at=snapshot.accessed_at,
                media_type=snapshot.media_type,
            ),
            raw,
        )

    def _web_evidence_attempt(self, snapshot_ref: ArtifactRef) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT attempt FROM task_web_evidence WHERE snapshot_ref_json = ?",
                (snapshot_ref.canonical_json(),),
            ).fetchone()
        if row is None:
            raise TaskServiceError("web evidence mapping is missing")
        return int(row["attempt"])

    def _scheduler_signal_for_output(
        self, artifact_ref: ArtifactRef
    ) -> SchedulerSignal | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT scheduler_signal_ref_json
                FROM tasks
                WHERE output_ref_json = ? AND state = 'completed'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (artifact_ref.canonical_json(),),
            ).fetchone()
        if row is None:
            return None
        signal_ref = _parse_optional_ref(row["scheduler_signal_ref_json"])
        if signal_ref is None:
            return None
        try:
            return SchedulerSignal.model_validate_json(
                self.artifacts.read(signal_ref), strict=True
            )
        except ValidationError as error:
            raise TaskServiceError("stored scheduler signal is invalid") from error

    @staticmethod
    def _row(connection: sqlite3.Connection, task_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
        if row is None:
            raise TaskServiceError("task does not exist")
        return row

    def _append_event(
        self,
        connection: sqlite3.Connection,
        task_id: str,
        event_type: str,
        *,
        attempt: int,
        reason: str | None = None,
        output_ref: ArtifactRef | None = None,
    ) -> None:
        event = TaskEvent(
            event_id=f"tev_{uuid.uuid4().hex}",
            task_id=task_id,
            event_type=event_type,
            attempt=attempt,
            recorded_at=_timestamp(),
            reason=reason,
            output_ref=output_ref,
        )
        connection.execute(
            "INSERT INTO task_events (event_id, task_id, event_json, recorded_at) VALUES (?, ?, ?, ?)",
            (event.event_id, task_id, event.canonical_json(), event.recorded_at),
        )

    @staticmethod
    def _append_activity(
        connection: sqlite3.Connection,
        task_id: str,
        attempt: int,
        activity: str,
        recorded_at: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO task_activity_events (
                task_id, attempt, activity, recorded_at
            ) VALUES (?, ?, ?, ?)
            """,
            (task_id, attempt, activity, recorded_at),
        )

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    task_ref_json BLOB NOT NULL,
                    role TEXT NOT NULL,
                    state TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    output_ref_json BLOB,
                    scheduler_signal_ref_json BLOB,
                    reason TEXT,
                    started_at TEXT,
                    deadline_at TEXT,
                    absolute_deadline_at TEXT,
                    last_activity_at TEXT,
                    last_activity TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS task_events (
                    event_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    event_json BLOB NOT NULL,
                    recorded_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id)
                );
                CREATE TABLE IF NOT EXISTS task_web_evidence (
                    task_id TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    source_key TEXT NOT NULL,
                    original_url TEXT NOT NULL,
                    snapshot_ref_json BLOB NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(task_id, attempt, source_key),
                    UNIQUE(task_id, attempt, original_url),
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id)
                );
                CREATE TABLE IF NOT EXISTS assignment_instances (
                    instance_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    proxy_id TEXT,
                    session_id TEXT,
                    created_at TEXT NOT NULL,
                    bound_at TEXT,
                    completed_at TEXT,
                    UNIQUE(task_id, attempt),
                    UNIQUE(proxy_id),
                    UNIQUE(session_id),
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id)
                );
                CREATE INDEX IF NOT EXISTS assignment_instances_queue
                ON assignment_instances(role, state, created_at);
                CREATE TABLE IF NOT EXISTS task_activity_events (
                    task_id TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    activity TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id)
                );
                CREATE INDEX IF NOT EXISTS task_activity_events_lookup
                ON task_activity_events(task_id, attempt, recorded_at);
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(tasks)").fetchall()
            }
            if "last_activity_at" not in columns:
                connection.execute("ALTER TABLE tasks ADD COLUMN last_activity_at TEXT")
            if "last_activity" not in columns:
                connection.execute("ALTER TABLE tasks ADD COLUMN last_activity TEXT")
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(tasks)").fetchall()
            }
            if "scheduler_signal_ref_json" not in columns:
                connection.execute(
                    "ALTER TABLE tasks ADD COLUMN scheduler_signal_ref_json BLOB"
                )
            if "deadline_at" not in columns:
                connection.execute("ALTER TABLE tasks ADD COLUMN deadline_at TEXT")
            if "started_at" not in columns:
                connection.execute("ALTER TABLE tasks ADD COLUMN started_at TEXT")
            if "absolute_deadline_at" not in columns:
                connection.execute(
                    "ALTER TABLE tasks ADD COLUMN absolute_deadline_at TEXT"
                )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection


def _parse_ref(raw: bytes | str) -> ArtifactRef:
    try:
        return ArtifactRef.model_validate_json(raw, strict=True)
    except ValidationError as error:
        raise TaskServiceError("stored task reference is invalid") from error


def _parse_optional_ref(raw: bytes | str | None) -> ArtifactRef | None:
    return None if raw is None else _parse_ref(raw)


def _timestamp(value: datetime | None = None) -> str:
    return (
        (value or datetime.now(timezone.utc))
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.removesuffix("Z") + "+00:00")


def _seconds_between(start: str, end: str) -> float:
    elapsed = (_parse_timestamp(end) - _parse_timestamp(start)).total_seconds()
    return max(0.0, round(elapsed, 6))


def _add_duration(
    target: dict[str, float],
    label: str,
    phases: dict[str, dict[str, str]],
    start_phase: str,
    end_phase: str,
    *,
    start_edge: str = "first_at",
) -> None:
    if start_phase in phases and end_phase in phases:
        target[label] = _seconds_between(
            phases[start_phase][start_edge], phases[end_phase]["last_at"]
        )


WORKER_CAPABILITIES = (
    "assignment.materialize",
    "input.read_text",
    "input.stage_file",
    "input.extract_pdf_text",
    "input.read_table",
    "input.profile",
    "analysis.python",
    "evidence.web_snapshot",
    "output.validate",
    "output.file",
    "task.heartbeat",
    "image.view",
    "web.search",
)


_MEDIA_SUFFIXES = {
    "application/json": ".json",
    "application/pdf": ".pdf",
    "application/xml": ".xml",
    "application/x-tar": ".tar",
    "text/csv": ".csv",
    "text/tab-separated-values": ".tsv",
    "text/plain": ".txt",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _task_input_filename(name: str, media_type: str) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
    base_type = media_type.split(";", 1)[0].strip().lower()
    suffix = _MEDIA_SUFFIXES.get(base_type, ".bin")
    return safe_name if safe_name.lower().endswith(suffix) else safe_name + suffix


def _write_immutable_file(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.is_symlink() or path.read_bytes() != content:
            raise TaskInputError("materialized task file differs from immutable source")
        return
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


def _lease_seconds(timeout_seconds: int) -> int:
    return min(600, timeout_seconds)


def _input_access_modes(media_type: str) -> tuple[str, ...]:
    base = media_type.split(";", 1)[0].strip().lower()
    if base == "application/pdf":
        return ("stage_file", "extract_pdf_text")
    if base.startswith("image/"):
        return ("stage_file",)
    if base in {"text/csv", "text/tab-separated-values", "application/json"}:
        return ("read_text", "stage_file", "read_table")
    if base.startswith("text/") or base in {"application/xml"}:
        return ("read_text", "stage_file")
    return ("stage_file",)


def _decode_agent_task(raw: bytes) -> AgentTask:
    """Verify immutable task bytes against the current schema only."""

    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TaskServiceError("stored task payload is invalid") from error
    if not isinstance(payload, dict) or canonical_json(payload) != raw:
        raise TaskServiceError("stored task payload is not canonical")
    try:
        return AgentTask.model_validate_json(canonical_json(payload), strict=True)
    except ValidationError as error:
        raise TaskServiceError("stored task payload is invalid") from error


def _encode_output(output: TaskOutputSpec, content: Any) -> bytes:
    if output.format == "json":
        if not isinstance(content, dict):
            raise TaskInputError("json task output must be an object")
        raw = canonical_json(_validate_role_output(output.validator, content))
    else:
        if not isinstance(content, str):
            raise TaskInputError("text task output must be a string")
        raw = content.encode("utf-8")
    if len(raw) > output.max_bytes:
        raise TaskInputError("scientific output exceeds task byte limit")
    return raw


def _validate_role_output(
    validator: str | None, content: dict[str, Any]
) -> dict[str, Any]:
    if validator is None:
        return content
    module_name, separator, attribute = validator.partition(":")
    if not separator or not module_name or not attribute:
        raise TaskServiceError("registered output validator is invalid")
    try:
        function = getattr(import_module(module_name), attribute)
    except (ImportError, AttributeError) as error:
        raise TaskServiceError("registered output validator is unavailable") from error
    try:
        value = function(content)
    except (TypeError, ValueError) as error:
        details = _validation_details(error)
        summary = "; ".join(
            f"{item['path']}: {item['message']}" for item in details[:8]
        ) or str(error)
        raise TaskInputError(
            f"role output validation failed: {summary}", details=details
        ) from error
    if not isinstance(value, dict):
        raise TaskServiceError("registered output validator returned a non-object")
    return value


def _validation_details(error: Exception) -> tuple[dict[str, str], ...]:
    if isinstance(error, ValidationError):
        return tuple(
            {
                "path": ".".join(str(part) for part in item["loc"]) or "$",
                "message": str(item["msg"]),
                "type": str(item["type"]),
            }
            for item in error.errors(include_url=False)
        )
    return ({"path": "$", "message": str(error), "type": "value_error"},)


def _prefix_validation_paths(
    details: tuple[dict[str, str], ...], prefix: str
) -> tuple[dict[str, str], ...]:
    if not details:
        return ()
    prefixed = []
    for item in details:
        path = item["path"]
        if path == "$":
            path = prefix
        elif path.startswith("$"):
            path = prefix + path[1:]
        else:
            path = f"{prefix}.{path}"
        prefixed.append({**item, "path": path})
    return tuple(prefixed)


__all__ = [
    "DispatchTicket",
    "RoleOutputContract",
    "TaskInputError",
    "TaskNotReady",
    "TaskService",
    "TaskServiceError",
    "TaskStateConflict",
    "TaskStatusView",
    "TaskWebEvidenceView",
]
