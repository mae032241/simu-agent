"""Control-owned task scheduling and worker lifecycle."""

from __future__ import annotations

import base64
import binascii
import fcntl
import hashlib
import json
import os
import re
import sqlite3
import stat
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from importlib import import_module
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..figure_evidence_validation import (
    FigureEvidenceBundleError,
    build_figure_evidence_validation_report,
)
from ..schema.artifact import ArtifactRegistration
from ..schema.common import canonical_json, canonical_sha256
from ..schema.pdf_excerpt import PDF_TEXT_EXTRACTOR_PROFILE, PdfExcerptSet
from ..schema.evidence_receipt import UnchangedEvidenceReceipt
from ..schema.figure_evidence import validate_figure_evidence_validation_report
from ..schema.provisional import (
    ProvisionalDiagnostic,
    ProvisionalSnapshotFile,
    ProvisionalSnapshotManifest,
)
from ..schema.refs import ActorRef, ArtifactRef
from ..schema.task import (
    AgentTask,
    AssignmentInput,
    AssignmentOutput,
    AssignmentOutputCollection,
    AssignmentProvisionalContext,
    SchedulerSignal,
    TaskBudget,
    TaskEvent,
    TaskInput,
    TaskOutputBundle,
    TaskOutputBundleItem,
    TaskOutputCollectionSpec,
    TaskOutputSpec,
    WorkerAssignment,
)
from ..schema.cognitive import CriticReview, EvidenceAudit, HypothesisProposal
from ..schema.device_parameters import (
    DeviceParameterRequirementSet,
    DeviceParameterSet,
    EvidenceSourceCatalog,
    evaluate_device_parameter_coverage,
)
from ..schema.role_result import RoleHandoff, RoleResultEnvelope, parse_role_result
from ..schema.structured_revision import StructuredRevision, operation_is_within_scope
from ..schema.scientific_foundation import ScientificFoundation
from ..schema.validation import ValidationReport
from ..schema.layered_diagnosis import LayeredDiagnosisReport
from ..schema.research_cycle import ScientificIntake
from ..schema.knowledge import KnowledgeUpdate
from ..schema.web_evidence import WebEvidenceSnapshot
from ..security.task_tokens import TaskTokenService
from .artifacts import ArtifactService
from .maintenance import remove_private_directory, validate_private_directory
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


_TCAD_DECK_AUTHOR_REVISION_PROFILES = frozenset(
    {
        "tcad.deck-author.capability-bound.revision.v1",
        "tcad.deck-author.runtime-failure-revision.v1",
    }
)

_FIRST_PERSISTED_PROGRESS_SECONDS = 420
_PERSISTED_PROGRESS_ACTIVITIES = frozenset(
    {
        "output_json_parseable",
    }
)


def _same_device_parameter_checklist(
    left: DeviceParameterRequirementSet,
    right: DeviceParameterRequirementSet,
) -> bool:
    """Compare scientific requirements while excluding their UI display labels."""

    def scientific_fields(value: DeviceParameterRequirementSet) -> dict[str, Any]:
        result = value.model_dump(mode="json")
        for item in result["parameters"]:
            item.pop("display_name", None)
        return result

    return scientific_fields(left) == scientific_fields(right)


@dataclass(frozen=True)
class RoleOutputVariant:
    kind: str
    format: str
    schema_id: str
    validator: str | None = None
    context_validator: str | None = None
    context_sources: tuple[str, ...] = ()
    json_schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class RoleOutputContract:
    kind: str
    format: str
    schema_id: str
    validator: str | None = None
    context_validator: str | None = None
    context_sources: tuple[str, ...] = ()
    json_schema: dict[str, Any] | None = None
    collection_profiles: dict[str, tuple[TaskOutputCollectionSpec, ...]] = field(
        default_factory=dict
    )
    primary_profiles: dict[str, RoleOutputVariant] = field(default_factory=dict)

    def resolve_profile(
        self, profile: str | None
    ) -> tuple[RoleOutputVariant, tuple[TaskOutputCollectionSpec, ...]]:
        primary = RoleOutputVariant(
            kind=self.kind,
            format=self.format,
            schema_id=self.schema_id,
            validator=self.validator,
            context_validator=self.context_validator,
            context_sources=self.context_sources,
            json_schema=self.json_schema,
        )
        if profile is None:
            return primary, ()
        if profile in self.primary_profiles:
            return self.primary_profiles[profile], ()
        try:
            return primary, self.collection_profiles[profile]
        except KeyError as error:
            raise ValueError("unknown output profile for scientific role") from error

    def collections_for_profile(
        self, profile: str | None
    ) -> tuple[TaskOutputCollectionSpec, ...]:
        if profile is None:
            return ()
        try:
            return self.collection_profiles[profile]
        except KeyError as error:
            raise ValueError("unknown output profile for scientific role") from error

    def admits_output(self, output: TaskOutputSpec) -> bool:
        candidates = (
            RoleOutputVariant(
                kind=self.kind,
                format=self.format,
                schema_id=self.schema_id,
                validator=self.validator,
                context_validator=self.context_validator,
                context_sources=self.context_sources,
                json_schema=self.json_schema,
            ),
            *self.primary_profiles.values(),
        )
        return any(
            output.kind == candidate.kind
            and output.format == candidate.format
            and output.schema_id == candidate.schema_id
            and output.validator == candidate.validator
            and output.context_validator in {None, candidate.context_validator}
            and output.context_sources in {(), candidate.context_sources}
            and (
                output.collections == ()
                if candidate.schema_id != self.schema_id
                else self.admits_collections(output.collections)
            )
            for candidate in candidates
        )

    def contract_for_output(self, output: TaskOutputSpec) -> RoleOutputVariant:
        candidates = (
            RoleOutputVariant(
                kind=self.kind,
                format=self.format,
                schema_id=self.schema_id,
                validator=self.validator,
                context_validator=self.context_validator,
                context_sources=self.context_sources,
                json_schema=self.json_schema,
            ),
            *self.primary_profiles.values(),
        )
        for candidate in candidates:
            if (
                output.kind == candidate.kind
                and output.format == candidate.format
                and output.schema_id == candidate.schema_id
                and output.validator == candidate.validator
                and output.context_validator in {None, candidate.context_validator}
                and output.context_sources in {(), candidate.context_sources}
            ):
                return candidate
        raise ValueError("task output differs from the registered role contract")

    def admits_collections(
        self, collections: tuple[TaskOutputCollectionSpec, ...]
    ) -> bool:
        return collections == () or any(
            collections == configured
            for configured in self.collection_profiles.values()
        )


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
    finalization_deadline_at: str | None
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
    extracted_text_ref: ArtifactRef | None
    text_truncated: bool


@dataclass(frozen=True)
class WebEvidenceMaterializationView:
    local_path: str
    size_bytes: int
    text_local_path: str | None
    text_size_bytes: int | None
    text_truncated: bool


@dataclass(frozen=True)
class TaskPdfExcerptView:
    source_name: str
    excerpt_ref: ArtifactRef
    first_page: int
    last_page: int
    max_chars: int
    truncated: bool


@dataclass(frozen=True)
class PdfTextExtractionView:
    local_path: str
    size_bytes: int
    first_page: int
    last_page: int
    available_page_count: int
    truncated: bool
    cache_hit: bool


@dataclass(frozen=True)
class TaskOutputArtifactView:
    collection: str
    item: str
    artifact_ref: ArtifactRef
    media_type: str
    size_bytes: int


@dataclass(frozen=True)
class _ValidatedOutputArtifact:
    descriptor: TaskOutputBundleItem
    spec: TaskOutputCollectionSpec
    content: bytes
    control_generated: bool = False


@dataclass(frozen=True)
class _WorkspaceSnapshotFile:
    relative_path: str
    media_type: str
    content: bytes
    collection: str | None = None
    item: str | None = None
    control_generated: bool = False
    materialize_on_retry: bool = True


@dataclass(frozen=True)
class _WorkerFileTarget:
    path: Path
    max_bytes: int
    text_required: bool
    removable: bool


_FIGURE_VALIDATION_REPORT_SPEC = TaskOutputCollectionSpec(
    name="validation_reports",
    kind="figure_evidence_validation_report",
    schema_id="scidiscovery.figure-evidence-validation-report.v1",
    validator=(
        "scidiscovery.artifact_agent.schema.figure_evidence:"
        "validate_figure_evidence_validation_report"
    ),
    media_types=("application/json",),
    min_items=1,
    max_items=1,
    max_item_bytes=1024 * 1024,
    max_total_bytes=1024 * 1024,
)


_ROLE_RESULT_ENVELOPE_OVERHEAD_BYTES = 64 * 1024
_PDF_TEXT_CACHE_MAX_BYTES = 64 * 1024 * 1024
_RESULT_UPLOAD_CHUNK_BYTES = 64 * 1024
_WORKER_FILE_UPLOAD_BYTES = 64 * 1024
_WORKER_FILE_UPLOAD_DATA = ".worker-file-upload.data"
_WORKER_FILE_UPLOAD_METADATA = ".worker-file-upload.json"
_FINALIZATION_GRACE_SECONDS = 30
_FINALIZATION_COMMIT_SECONDS = 30
_PROVISIONAL_DIAGNOSTIC_BYTES = 32 * 1024
_PROVISIONAL_SNAPSHOTS_PER_ATTEMPT = 32


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
        development_debug_enabled: bool = False,
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
        self.development_debug_enabled = development_debug_enabled
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
        self._validate_context(
            inputs,
            context_policy,
            role=role,
            context_profile=resolved_profile,
        )
        if not contract.admits_output(output):
            raise ValueError("task output differs from the registered role contract")
        output_variant = contract.contract_for_output(output)
        output = output.model_copy(
            update={
                "context_validator": output_variant.context_validator,
                "context_sources": output_variant.context_sources,
            }
        )
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

        allowed = {
            "created",
            "dispatched",
            "claimed",
            "finalizing",
            "completed",
            "failed",
            "timed_out",
        }
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

    def delete_tasks(self, task_ids: tuple[str, ...]) -> tuple[ArtifactRef, ...]:
        """Delete terminal or unstarted tasks selected by instance administration."""

        if len(task_ids) != len(set(task_ids)):
            raise ValueError("task identities must be unique")
        if any(not isinstance(value, str) or not value for value in task_ids):
            raise ValueError("task identity is invalid")
        deleting = set(task_ids)
        active_debug = self.active_development_debug_tasks(task_ids=task_ids)
        if active_debug:
            raise TaskStateConflict(
                "cannot delete tasks with unclosed development debug runs: "
                + ", ".join(active_debug)
            )
        owned: list[ArtifactRef] = []
        workspace_session_ids: set[str] = set()
        with self._connect() as connection:
            existing = {
                str(row["task_id"]): row
                for task_id in task_ids
                for row in connection.execute(
                    "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
                ).fetchall()
            }
            active = {
                task_id: str(row["state"])
                for task_id, row in existing.items()
                if row["state"] in {"dispatched", "claimed", "finalizing"}
            }
            if active:
                raise TaskStateConflict(
                    "cannot delete active tasks: "
                    + ", ".join(f"{key}={value}" for key, value in sorted(active.items()))
                )
            retained_ids = tuple(
                str(row["task_id"])
                for row in connection.execute("SELECT task_id FROM tasks").fetchall()
                if str(row["task_id"]) not in deleting
            )
        for task_id in retained_ids:
            dependencies = set(self.get_task(task_id).dependency_task_ids)
            if dependencies & deleting:
                raise TaskStateConflict(
                    f"retained task depends on a task selected for deletion: {task_id}"
                )
        for task_id, row in existing.items():
            owned.append(_parse_ref(row["task_ref_json"]))
            for field in ("output_ref_json", "scheduler_signal_ref_json"):
                reference = _parse_optional_ref(row[field])
                if reference is not None:
                    owned.append(reference)
            with self._connect() as connection:
                owned.extend(
                    _parse_ref(item["snapshot_ref_json"])
                    for item in connection.execute(
                        "SELECT snapshot_ref_json FROM task_web_evidence WHERE task_id = ?",
                        (task_id,),
                    ).fetchall()
                )
                owned.extend(
                    _parse_ref(item["artifact_ref_json"])
                    for item in connection.execute(
                        "SELECT artifact_ref_json FROM task_output_artifacts WHERE task_id = ?",
                        (task_id,),
                    ).fetchall()
                )
                owned.extend(
                    _parse_ref(item["excerpt_ref_json"])
                    for item in connection.execute(
                        "SELECT excerpt_ref_json FROM task_pdf_excerpts WHERE task_id = ?",
                        (task_id,),
                    ).fetchall()
                )
                provisional_rows = connection.execute(
                    """
                    SELECT manifest_ref_json FROM task_provisional_snapshots
                    WHERE task_id = ?
                    """,
                    (task_id,),
                ).fetchall()
                for item in provisional_rows:
                    manifest_ref = _parse_ref(item["manifest_ref_json"])
                    owned.append(manifest_ref)
                    try:
                        manifest = ProvisionalSnapshotManifest.model_validate_json(
                            self.artifacts.read(manifest_ref), strict=True
                        )
                    except ValidationError as error:
                        raise TaskServiceError(
                            "stored provisional snapshot is invalid"
                        ) from error
                    owned.extend(value.artifact_ref for value in manifest.files)
                workspace_session_ids.update(
                    str(item["session_id"])
                    for item in connection.execute(
                        """
                        SELECT session_id FROM assignment_instances
                        WHERE task_id = ? AND session_id IS NOT NULL
                        """,
                        (task_id,),
                    ).fetchall()
                )
        session_ids = self.tokens.delete_tasks(tuple(existing))
        workspace_session_ids.update(session_ids)
        for session_id in workspace_session_ids:
            validate_private_directory(self.workspace_root, session_id)
        for session_id in workspace_session_ids:
            remove_private_directory(self.workspace_root, session_id)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            for table in (
                "task_activity_events",
                "task_output_artifacts",
                "task_pdf_excerpts",
                "task_provisional_snapshots",
                "task_web_evidence",
                "tcad_debug_runs",
                "tcad_debug_leases",
                "assignment_instances",
                "task_events",
            ):
                connection.executemany(
                    f"DELETE FROM {table} WHERE task_id = ?",
                    ((value,) for value in existing),
                )
            connection.executemany(
                "DELETE FROM tasks WHERE task_id = ?",
                ((value,) for value in existing),
            )
            connection.execute("COMMIT")
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()
        return tuple(dict.fromkeys(owned))

    def active_development_debug_tasks(
        self, *, task_ids: tuple[str, ...] | None = None
    ) -> tuple[str, ...]:
        """Return exact tasks whose private debug adapter binding is not closed."""

        if task_ids is not None:
            if len(task_ids) != len(set(task_ids)):
                raise ValueError("task identities must be unique")
            if not task_ids:
                return ()
            placeholders = ",".join("?" for _ in task_ids)
            query = f"""
                SELECT DISTINCT task_id FROM tcad_debug_runs
                WHERE state NOT IN ('collected', 'reaped')
                  AND task_id IN ({placeholders})
                ORDER BY task_id
            """
            parameters: tuple[object, ...] = tuple(task_ids)
        else:
            query = """
                SELECT DISTINCT task_id FROM tcad_debug_runs
                WHERE state NOT IN ('collected', 'reaped')
                ORDER BY task_id
            """
            parameters = ()
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return tuple(str(row["task_id"]) for row in rows)

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
            initial_lease_seconds = (
                min(
                    _lease_seconds(task.budget.timeout_seconds),
                    _FIRST_PERSISTED_PROGRESS_SECONDS,
                )
                if _requires_first_persisted_progress(task)
                else _lease_seconds(task.budget.timeout_seconds)
            )
            lease_deadline = _timestamp(
                min(
                    now + timedelta(seconds=initial_lease_seconds),
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
            if _requires_first_persisted_progress(task) and not self._has_persisted_progress(
                connection, session.task_id, session.attempt
            ):
                started_at = row["started_at"]
                if started_at is None:
                    raise TaskServiceError("claimed task has no start time")
                first_progress_deadline = _parse_timestamp(started_at) + timedelta(
                    seconds=_FIRST_PERSISTED_PROGRESS_SECONDS
                )
                if now >= first_progress_deadline:
                    raise TaskStateConflict(
                        "experiment design first-progress deadline exceeded: "
                        + self._first_progress_reason(
                            connection, session.task_id, session.attempt
                        )
                    )
                next_deadline = first_progress_deadline
            else:
                next_deadline = now + timedelta(
                    seconds=_lease_seconds(task.budget.timeout_seconds)
                )
            lease_deadline = _timestamp(
                min(next_deadline, _parse_timestamp(absolute_deadline))
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
        """Record one bounded worker phase without scientific details."""

        allowed = {
            "assignment_read",
            "assignment_materialized",
            "inputs_listed",
            "input_read",
            "input_staged",
            "pdf_extracted",
            "pdf_cache_hit",
            "table_read",
            "input_profiled",
            "deterministic_analysis_completed",
            "deterministic_analysis_rejected",
            "web_evidence_frozen",
            "worker_file_written",
            "worker_file_patched",
            "worker_file_patch_rejected",
            "worker_file_json_patched",
            "worker_file_deleted",
            "worker_file_moved",
            "output_written",
            "output_checkpointed",
            "output_json_parseable",
            "output_validated",
            "output_rejected",
            "tcad_debug_submitted",
            "tcad_debug_polled",
            "tcad_debug_collected",
        }
        if activity not in allowed:
            raise ValueError("unknown worker activity")
        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        task = self.get_task(session.task_id)
        recorded_at = _timestamp()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if (
                activity in _PERSISTED_PROGRESS_ACTIVITIES
                and _requires_first_persisted_progress(task)
            ):
                row = self._row(connection, session.task_id)
                absolute_deadline = row["absolute_deadline_at"]
                if absolute_deadline is None:
                    raise TaskServiceError("claimed task has no absolute deadline")
                renewed_deadline = _timestamp(
                    min(
                        _parse_timestamp(recorded_at)
                        + timedelta(
                            seconds=_lease_seconds(task.budget.timeout_seconds)
                        ),
                        _parse_timestamp(absolute_deadline),
                    )
                )
                connection.execute(
                    """
                    UPDATE tasks
                    SET deadline_at = ?, last_activity_at = ?, last_activity = ?
                    WHERE task_id = ? AND state = 'claimed' AND attempt = ?
                    """,
                    (
                        renewed_deadline,
                        recorded_at,
                        activity,
                        session.task_id,
                        session.attempt,
                    ),
                )
            else:
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

    @staticmethod
    def _has_persisted_progress(
        connection: sqlite3.Connection, task_id: str, attempt: int
    ) -> bool:
        placeholders = ",".join("?" for _ in _PERSISTED_PROGRESS_ACTIVITIES)
        row = connection.execute(
            f"""
            SELECT 1 FROM task_activity_events
            WHERE task_id = ? AND attempt = ?
              AND activity IN ({placeholders})
            LIMIT 1
            """,
            (task_id, attempt, *sorted(_PERSISTED_PROGRESS_ACTIVITIES)),
        ).fetchone()
        return row is not None

    @staticmethod
    def _first_progress_reason(
        connection: sqlite3.Connection, task_id: str, attempt: int
    ) -> str:
        activities = {
            str(item["activity"])
            for item in connection.execute(
                """
                SELECT activity FROM task_activity_events
                WHERE task_id = ? AND attempt = ?
                """,
                (task_id, attempt),
            ).fetchall()
        }
        if not activities.intersection(
            {"worker_file_written", "worker_file_patched", "output_written"}
        ):
            return "no_persisted_bytes"
        if "output_json_parseable" not in activities:
            return "unparseable_checkpoint"
        return "unparseable_checkpoint"

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
                usage=item.usage,
                access_modes=(
                    ()
                    if item.exposure == "handoff_only"
                    else _input_access_modes(
                        self.artifacts.catalog(item.artifact_ref).media_type
                    )
                ),
                handoff=(
                    self.scheduler_signal_for_output(item.artifact_ref)
                    if item.exposure == "handoff_only"
                    else None
                ),
            )
            for item in task.inputs
        )
        contract = self.output_contract(task.role).contract_for_output(task.output)
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
                collections=tuple(
                    AssignmentOutputCollection(
                        name=item.name,
                        media_types=item.media_types,
                        min_items=item.min_items,
                        max_items=item.max_items,
                        max_item_bytes=item.max_item_bytes,
                        max_total_bytes=item.max_total_bytes,
                        relative_directory=f"output/collections/{item.name}",
                        json_schema_relative_path=(
                            f"schema/collections/{item.name}.schema.json"
                            if item.json_schema
                            else None
                        ),
                    )
                    for item in task.output.collections
                ),
                bundle_relative_path=(
                    "output/bundle.json" if task.output.collections else None
                ),
                max_bundle_bytes=(
                    task.output.max_bundle_bytes if task.output.collections else None
                ),
                revision=task.output.revision,
            ),
            provisional_contexts=self._assignment_provisional_contexts(
                task.task_id, before_attempt=session.attempt
            ),
            capabilities=WORKER_CAPABILITIES
            + (
                (
                    "tcad.development_preflight",
                    "tcad.development_smoke",
                    "tcad.development_initialization",
                )
                if task.role == "tcad_deck_author"
                and self.development_debug_enabled
                else ()
            ),
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

    def extract_pdf_text(
        self,
        session_token: str,
        *,
        worker_id: str,
        name: str,
        first_page: int,
        last_page: int | None,
        max_chars: int,
    ) -> PdfTextExtractionView:
        """Reuse one immutable full-document extraction and freeze the requested excerpt."""

        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        task = self.get_task(session.task_id)
        matches = tuple(item for item in task.inputs if item.name == name)
        if len(matches) != 1:
            raise TaskInputError("input name is not bound to this task")
        item = matches[0]
        if item.exposure == "handoff_only":
            raise TaskInputError("input is handoff-only and cannot be read")
        source = self.artifacts.verify(item.artifact_ref)
        if source.media_type.split(";", 1)[0].strip().lower() != "application/pdf":
            raise TaskInputError("PDF extraction requires application/pdf")
        if last_page is not None and last_page < first_page:
            raise TaskInputError("last_page must not precede first_page")

        cache_key = canonical_sha256(
            {
                "source_sha256": source.sha256,
                "extractor_profile": PDF_TEXT_EXTRACTOR_PROFILE,
                "layout_mode": "layout",
            }
        )
        cache_hit = False
        lock_directory = self.workspace_root.parent / "pdf-cache-locks"
        lock_directory.mkdir(
            mode=0o770 if self.artifacts.cas.file_mode == 0o640 else 0o700,
            exist_ok=True,
        )
        lock_path = lock_directory / f"{cache_key}.lock"
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(
            lock_path,
            flags,
            0o660 if self.artifacts.cas.file_mode == 0o640 else 0o600,
        )
        try:
            os.fchmod(
                descriptor,
                0o660 if self.artifacts.cas.file_mode == 0o640 else 0o600,
            )
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            with self._connect() as connection:
                cached = connection.execute(
                    "SELECT * FROM pdf_text_cache WHERE cache_key = ?",
                    (cache_key,),
                ).fetchone()
            if cached is not None:
                cache_ref = _parse_ref(cached["text_ref_json"])
                cached_envelope = self.artifacts.verify(cache_ref)
                cached_source_ref = _parse_ref(cached["source_ref_json"])
                cached_source = self.artifacts.verify(cached_source_ref)
                if (
                    cached["extractor_profile"] != PDF_TEXT_EXTRACTOR_PROFILE
                    or cached_source.sha256 != source.sha256
                    or cached_source_ref not in cached_envelope.parent_refs
                ):
                    raise TaskServiceError("PDF text cache parentage is invalid")
                text = self.artifacts.read(cache_ref).decode("utf-8")
                cache_hit = True
            else:
                local_path, _, _ = self.stage_input(
                    session_token, worker_id=worker_id, name=name
                )
                try:
                    completed = subprocess.run(
                        ["pdftotext", "-layout", local_path, "-"],
                        check=False,
                        capture_output=True,
                        timeout=60,
                    )
                except FileNotFoundError as error:
                    raise TaskInputError("pdftotext is not installed") from error
                except subprocess.TimeoutExpired as error:
                    raise TaskInputError("PDF text extraction timed out") from error
                if completed.returncode != 0:
                    detail = completed.stderr.decode(
                        "utf-8", errors="replace"
                    )[-2048:]
                    raise TaskInputError(
                        f"PDF text extraction failed: {detail}"
                    )
                text = completed.stdout.decode("utf-8", errors="replace")
                raw_text = text.encode("utf-8")
                if not raw_text:
                    raise TaskInputError("PDF text extraction produced no text")
                if len(raw_text) > _PDF_TEXT_CACHE_MAX_BYTES:
                    raise TaskInputError("PDF text cache exceeds its byte limit")
                cache_ref = self.artifacts.register(
                    raw_text,
                    ArtifactRegistration(
                        kind="pdf_text_cache",
                        schema_id="opaque",
                        payload_schema_version=1,
                        media_type="text/plain; charset=utf-8",
                        creator=self.service_actor,
                        parent_refs=(source.ref,),
                        labels={"extractor_profile": PDF_TEXT_EXTRACTOR_PROFILE},
                        confidentiality="task_private",
                    ),
                    idempotency_key=f"pdf-text-cache:{cache_key}",
                ).ref
                with self._connect() as connection:
                    connection.execute(
                        """
                        INSERT INTO pdf_text_cache (
                            cache_key, source_ref_json, extractor_profile,
                            text_ref_json, created_at
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            cache_key,
                            source.ref.canonical_json(),
                            PDF_TEXT_EXTRACTOR_PROFILE,
                            cache_ref.canonical_json(),
                            _timestamp(),
                        ),
                    )
        finally:
            os.close(descriptor)

        pages = _pdf_text_pages(text)
        if first_page > len(pages):
            raise TaskInputError("PDF first_page exceeds the extracted page count")
        selected_last = min(last_page or len(pages), len(pages))
        selected_text = "\f".join(pages[first_page - 1 : selected_last])
        bounded_text = selected_text[:max_chars]
        excerpt = PdfExcerptSet(
            first_page=first_page,
            last_page=selected_last,
            available_page_count=len(pages),
            content=bounded_text,
            truncated=len(selected_text) > max_chars,
        )
        excerpt_key = canonical_sha256(
            {
                "source_ref": source.ref,
                "cache_ref": cache_ref,
                "first_page": first_page,
                "last_page": selected_last,
                "max_chars": max_chars,
            }
        )
        excerpt_ref = self.artifacts.register(
            excerpt.canonical_json(),
            ArtifactRegistration(
                kind="pdf_excerpt_set",
                schema_id="scidiscovery.pdf-excerpt-set.v1",
                payload_schema_version=1,
                media_type="application/json",
                creator=self.service_actor,
                parent_refs=(source.ref, cache_ref),
                labels={"extractor_profile": PDF_TEXT_EXTRACTOR_PROFILE},
                confidentiality="task_private",
            ),
            idempotency_key=f"pdf-excerpt-set:{excerpt_key}",
        ).ref
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO task_pdf_excerpts (
                    task_id, attempt, source_name, first_page, last_page,
                    max_chars, excerpt_ref_json, truncated, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    session.attempt,
                    name,
                    first_page,
                    selected_last,
                    max_chars,
                    excerpt_ref.canonical_json(),
                    int(excerpt.truncated),
                    _timestamp(),
                ),
            )
            stored = connection.execute(
                """
                SELECT excerpt_ref_json FROM task_pdf_excerpts
                WHERE task_id = ? AND attempt = ? AND source_name = ?
                  AND first_page = ? AND last_page = ? AND max_chars = ?
                """,
                (
                    task.task_id,
                    session.attempt,
                    name,
                    first_page,
                    selected_last,
                    max_chars,
                ),
            ).fetchone()
        if stored is None or _parse_ref(stored["excerpt_ref_json"]) != excerpt_ref:
            raise TaskServiceError("PDF excerpt mapping is inconsistent")
        workspace = self.workspace_root / session.session_id
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
        excerpt_path = (
            workspace
            / "excerpts"
            / (
                f"{safe_name}.pages-{first_page}-{selected_last}."
                f"max-{max_chars}.txt"
            )
        )
        excerpt_raw = excerpt.content.encode("utf-8")
        _write_immutable_file(excerpt_path, excerpt_raw)
        return PdfTextExtractionView(
            local_path=str(excerpt_path),
            size_bytes=len(excerpt_raw),
            first_page=excerpt.first_page,
            last_page=excerpt.last_page,
            available_page_count=excerpt.available_page_count,
            truncated=excerpt.truncated,
            cache_hit=cache_hit,
        )

    def materialize_assignment(
        self, session_token: str, *, worker_id: str
    ) -> dict[str, Any]:
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
                "usage": metadata.usage,
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

        provisional_entries: list[dict[str, Any]] = []
        for context in assignment.provisional_contexts:
            manifest = self._provisional_manifest(
                task.task_id,
                attempt=context.attempt,
                name=context.name,
            )
            relative_directory = Path(context.relative_directory)
            for item in manifest.files:
                if not item.materialize_on_retry:
                    continue
                relative_path = _validated_provisional_relative_path(
                    item.relative_path
                )
                destination = workspace / relative_directory / relative_path
                _write_immutable_file(destination, self.artifacts.read(item.artifact_ref))
            if manifest.diagnostics:
                _write_immutable_file(
                    workspace / relative_directory / "diagnostics.json",
                    canonical_json(
                        {
                            "diagnostics": [
                                item.model_dump(mode="json")
                                for item in manifest.diagnostics
                            ],
                            "truncated": manifest.diagnostics_truncated,
                        }
                    ),
                )
            provisional_entries.append(context.model_dump(mode="json"))

        schema_relative_path = Path("schema/output.schema.json")
        _write_immutable_file(
            workspace / schema_relative_path,
            canonical_json(assignment.output.json_schema),
        )
        collection_specs = {item.name: item for item in task.output.collections}
        collection_schema_paths: list[str] = []
        for collection in assignment.output.collections:
            relative_schema_path = collection.json_schema_relative_path
            if relative_schema_path is None:
                continue
            spec = collection_specs[collection.name]
            if not spec.json_schema:
                raise TaskServiceError(
                    "assignment collection JSON Schema is unavailable"
                )
            _write_immutable_file(
                workspace / relative_schema_path,
                canonical_json(spec.json_schema),
            )
            collection_schema_paths.append(relative_schema_path)
        output_relative_path = Path("output/result.json")
        deck_workspace = self._materialize_deck_workspace(
            task=task,
            assignment=assignment,
            workspace=workspace,
        )
        declared_read_paths = [
            "assignment.json",
            schema_relative_path.as_posix(),
            *collection_schema_paths,
            *(
                entry["relative_path"]
                for entry in entries
                if "relative_path" in entry
            ),
            *(
                entry["relative_directory"]
                for entry in provisional_entries
            ),
        ]
        if deck_workspace is not None:
            declared_read_paths.append("deck")
        patch_contract: dict[str, object] = {
            "format": "unified_diff",
            "context_policy": "declared_position_or_unique_current_context",
            "rejection_diagnostic": (
                "reason_target_sha256_declared_line_and_bounded_current_context"
            ),
            "after_success": "reread_target_before_next_patch",
            "after_rejection": "reread_and_regenerate_never_retry_same_diff",
            "large_patch_operation": "patch",
            "generated_json_layout": "stable_multiline_indent_2",
            "max_json_line_bytes": _PATCHABLE_JSON_MAX_LINE_BYTES,
            "json_path_patch": {
                "atomic": True,
                "operations": ["test", "add", "replace", "remove"],
                "guard": "expected_digest_or_test",
            },
        }
        if (
            task.role == "tcad_deck_author"
            and task.context_profile in _TCAD_DECK_AUTHOR_REVISION_PROFILES
        ):
            patch_contract.update(
                {
                    "first_checkpoint_seconds": 180,
                    "first_change_strategy": (
                        "one_small_justified_patch_or_checkpoint_unchanged_fail_closed"
                    ),
                }
            )
        elif _requires_first_persisted_progress(task):
            patch_contract.update(
                {
                    "first_checkpoint_seconds": _FIRST_PERSISTED_PROGRESS_SECONDS,
                    "first_change_strategy": (
                        "write_one_schema-shaped_compact_intent_then_checkpoint"
                    ),
                    "first_checkpoint_requirement": "parseable_output_json",
                    "failure_reason_codes": [
                        "no_persisted_bytes",
                        "unparseable_checkpoint",
                    ],
                }
            )
        manifest = {
            "schema_version": 1,
            "role": assignment.role,
            "context_profile": assignment.context_profile,
            "instruction": assignment.instruction,
            "inputs": entries,
            "provisional_contexts": provisional_entries,
            "output": {
                "format": assignment.output.format,
                "media_type": assignment.output.media_type,
                "max_bytes": assignment.output.max_bytes,
                "relative_path": output_relative_path.as_posix(),
                "schema_relative_path": schema_relative_path.as_posix(),
                "protocol": assignment.output.protocol,
                "collections": [
                    item.model_dump(mode="json")
                    for item in assignment.output.collections
                ],
                "bundle_relative_path": assignment.output.bundle_relative_path,
                "max_bundle_bytes": assignment.output.max_bundle_bytes,
                "revision": (
                    assignment.output.revision.model_dump(mode="json")
                    if assignment.output.revision is not None
                    else None
                ),
            },
            "capabilities": list(assignment.capabilities),
            "lease_seconds": assignment.lease_seconds,
            "file_access": {
                "read_protocol": "native_filesystem",
                "read_only": True,
                "read_only_relative_paths": declared_read_paths,
                "write_protocol": "scidiscovery.worker-file-edit.v1",
                "native_filesystem_write": False,
                "patch_contract": patch_contract,
                "write_tools": [
                    "worker_file_write_begin",
                    "worker_file_write_chunk",
                    "worker_file_write_commit",
                    "worker_file_apply_patch",
                    "worker_file_json_patch",
                    "worker_file_delete",
                    "worker_file_move",
                ],
            },
        }
        if deck_workspace is not None:
            manifest["deck_workspace"] = deck_workspace["manifest"]
        assignment_path = workspace / "assignment.json"
        _write_immutable_file(assignment_path, canonical_json(manifest))
        result = {
            "workspace_path": str(workspace),
            "assignment_path": str(assignment_path),
            "output_path": str(workspace / output_relative_path),
            "input_paths": {
                entry["source_name"]: str(workspace / entry["relative_path"])
                for entry in entries
                if "relative_path" in entry
            },
            "read_protocol": "native_filesystem",
            "write_protocol": "scidiscovery.worker-file-edit.v1",
        }
        if deck_workspace is not None:
            result.update(deck_workspace["paths"])
        if task.output.collections:
            collections_directory = output_directory / "collections"
            collections_directory.mkdir(parents=True, mode=0o700, exist_ok=True)
            result["bundle_path"] = str(output_directory / "bundle.json")
            result["collections_path"] = str(collections_directory)
        return result

    def _materialize_deck_workspace(
        self,
        *,
        task: AgentTask,
        assignment: WorkerAssignment,
        workspace: Path,
    ) -> dict[str, dict[str, object]] | None:
        if task.role not in {"tcad_deck_author", "tcad_deck_reviewer"}:
            return None

        deck_directory = workspace / "deck"
        files_directory = deck_directory / "files"
        contract_directory = deck_directory / "contract"
        reports_directory = deck_directory / "reports"
        metadata_path = deck_directory / "project.json"
        declarations_path = deck_directory / "declarations.json"
        handoff_path = deck_directory / "handoff.json"
        readme_path = deck_directory / "README.md"
        author = task.role == "tcad_deck_author"
        capability_inputs = tuple(
            item for item in task.inputs if item.name == "execution_capability"
        )
        experiment_plan_inputs = tuple(
            item for item in task.inputs if item.name == "experiment_plan"
        )
        deterministic_materialization = author and self._uses_deck_materializer(task)
        mode = "review"
        base_project: Any | None = None
        base_handoff: dict[str, object] | None = None

        if author:
            restored = self._latest_deck_workspace_retry(
                assignment=assignment, workspace=workspace
            )
            if restored is not None:
                mode = "retry"
                base_project, base_handoff = restored
            elif task.context_profile in _TCAD_DECK_AUTHOR_REVISION_PROFILES:
                mode = "revise"
                base_project = self._task_deck_project(task, "prior_project")
            else:
                mode = "create"
        else:
            for candidate in ("project", "revised_project"):
                if any(item.name == candidate for item in task.inputs):
                    base_project = self._task_deck_project(task, candidate)
                    break
            if base_project is None:
                raise TaskInputError(
                    "TCAD deck review requires one complete project input"
                )

        if not deck_directory.exists():
            deck_directory.mkdir(parents=True, mode=0o700)
        if not files_directory.exists():
            files_directory.mkdir(parents=True, mode=0o700)
        if author and not contract_directory.exists():
            contract_directory.mkdir(parents=True, mode=0o700)
        if author and not reports_directory.exists():
            reports_directory.mkdir(parents=True, mode=0o700)

        if not metadata_path.exists():
            if base_project is None:
                metadata = self._new_deck_workspace_template(task)
            else:
                metadata = base_project.model_dump(mode="json")
                metadata.pop("files", None)
                if deterministic_materialization:
                    for generated in (
                        "schema_version",
                        "tool_profile",
                        "solver_kind",
                        "capability_sha256",
                        "expected_outputs",
                        "parameter_bindings",
                        "case_parameter_bindings",
                        "runtime_assertions",
                        "realization_manifest",
                        "materialization_report",
                        "preflight_attestation",
                    ):
                        metadata.pop(generated, None)
                for item in base_project.files:
                    destination = files_directory / Path(item.relative_path)
                    _write_deck_workspace_file(
                        files_directory,
                        destination,
                        item.content.encode("utf-8"),
                        editable=author,
                    )
            _write_deck_workspace_file(
                deck_directory,
                metadata_path,
                _pretty_json(metadata),
                editable=author and not deterministic_materialization,
            )
        if deterministic_materialization:
            materializer = import_module("tcad_artifact.project_materializer")
            experiment_plan = self.artifacts.read(
                experiment_plan_inputs[0].artifact_ref
            )
            if not declarations_path.exists():
                _write_deck_workspace_file(
                    deck_directory,
                    declarations_path,
                    materializer.declarations_template_json(
                        experiment_plan, base_project=base_project
                    ),
                    editable=True,
                )
            for relative, payload in (
                (
                    Path("contract/capability.json"),
                    self.artifacts.read(capability_inputs[0].artifact_ref),
                ),
                (
                    Path("contract/experiment-controls.json"),
                    experiment_plan,
                ),
                (
                    Path("contract/materialization-spec.json"),
                    materializer.materialization_contract_json(experiment_plan),
                ),
            ):
                destination = deck_directory / relative
                if not destination.exists():
                    _write_deck_workspace_file(
                        deck_directory, destination, payload, editable=False
                    )
        if author and not handoff_path.exists():
            handoff = base_handoff or {
                "verdict": None,
                "summary": None,
                "assumptions": [],
                "missing_inputs": [],
                "next_actions": [],
            }
            _write_deck_workspace_file(
                deck_directory,
                handoff_path,
                _pretty_json(handoff),
                editable=True,
            )
        if not readme_path.exists():
            text = (
                (
                    "# TCAD deck workspace\n\n"
                    "Read files below `files/` and the read-only contracts with normal "
                    "filesystem tools. Write the complete solver project, then edit "
                    "`declarations.json` and `handoff.json` through the task-bound Worker "
                    "MCP interfaces. Declarations contain only source locators; the control "
                    "plane does not parse or generate solver-language code. `project.json`, "
                    "bindings, manifests, capability identity, outputs, arguments, and "
                    "resource policy are control-generated and must not be edited.\n"
                    if deterministic_materialization
                    else
                    "# TCAD deck workspace\n\n"
                    "Read `project.json` and files below `files/` with normal filesystem "
                    "tools. Change them only through the task-bound Worker MCP unified-diff "
                    "or new-file interfaces. The control plane reconstructs and validates the canonical "
                    "DeckProjectDraft. Do not write embedded source content into project.json.\n"
                )
                if author
                else (
                    "# TCAD deck review workspace\n\n"
                    "The supplied effective deck is expanded below `files/` for read-only "
                    "code review. Write only the formal review envelope to "
                    "`../output/result.json`.\n"
                )
            )
            _write_deck_workspace_file(
                deck_directory,
                readme_path,
                text.encode("utf-8"),
                editable=False,
            )

        if not author:
            _make_tree_read_only(deck_directory)

        manifest: dict[str, object] = {
            "protocol": "scidiscovery.tcad-deck-workspace.v1",
            "mode": mode,
            "access": "mcp_edit" if author else "read_only",
            "native_filesystem_access": "read_only",
            "edit_protocol": (
                "scidiscovery.worker-file-edit.v1" if author else None
            ),
            "root_relative_path": "deck",
            "files_relative_path": "deck/files",
            "project_metadata_relative_path": "deck/project.json",
            "declarations_relative_path": "deck/declarations.json",
            "canonical_output_relative_path": "output/result.json",
            "control_builds_canonical_project": author,
        }
        if deterministic_materialization:
            manifest["control_materializes_plan_bindings"] = True
            manifest["control_interprets_solver_source"] = False
            manifest["project_metadata_access"] = "control_read_only"
        if author:
            manifest["handoff_relative_path"] = "deck/handoff.json"
        paths: dict[str, object] = {
            "deck_workspace_path": str(deck_directory),
            "deck_files_path": str(files_directory),
            "deck_project_path": str(metadata_path),
            "deck_project_access": (
                "control_read_only" if deterministic_materialization else manifest["access"]
            ),
            "deck_access": manifest["access"],
            "deck_mode": mode,
        }
        if author:
            paths["deck_handoff_path"] = str(handoff_path)
            if deterministic_materialization:
                paths["deck_declarations_path"] = str(declarations_path)
                paths["deck_contract_path"] = str(contract_directory)
                paths["deck_materialization_spec_path"] = str(
                    contract_directory / "materialization-spec.json"
                )
                paths["deck_materialization_report_path"] = str(
                    reports_directory / "materialization.json"
                )
                paths["deck_preflight_attestation_path"] = str(
                    reports_directory / "preflight.json"
                )
        return {"manifest": manifest, "paths": paths}

    def _task_deck_project(self, task: AgentTask, source_name: str) -> Any:
        matches = tuple(item for item in task.inputs if item.name == source_name)
        if len(matches) != 1:
            raise TaskInputError(f"TCAD deck source {source_name} is not bound")
        model = _deck_project_model()
        try:
            return model.model_validate_json(
                self.artifacts.read(matches[0].artifact_ref), strict=True
            )
        except ValidationError as error:
            raise TaskInputError(
                f"TCAD deck source {source_name} is invalid",
                details=_validation_details(error),
            ) from error

    def _new_deck_workspace_template(self, task: AgentTask) -> dict[str, object]:
        capability = tuple(
            item for item in task.inputs if item.name == "execution_capability"
        )
        if len(capability) != 1:
            raise TaskInputError(
                "TCAD deck author requires exactly one execution_capability"
            )
        if self._uses_deck_materializer(task):
            return {}
        try:
            snapshot = json.loads(
                self.artifacts.read(capability[0].artifact_ref).decode("utf-8")
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise TaskInputError("execution_capability is invalid JSON") from error
        return {
            "schema_version": 1,
            "tool_profile": snapshot.get("profile_id"),
            "solver_kind": snapshot.get("solver_kind"),
            "capability_sha256": snapshot.get("capability_sha256"),
            "input_slots": [],
            "entrypoint": None,
            "arguments": [],
            "expected_outputs": [],
            "parameter_bindings": [],
            "case_parameter_bindings": [],
            "runtime_assertions": [],
            "realization_manifest": [],
            "resource_limits": None,
        }

    def _uses_deck_materializer(self, task: AgentTask) -> bool:
        capability = tuple(
            item for item in task.inputs if item.name == "execution_capability"
        )
        if len(capability) != 1 or not any(
            item.name == "experiment_plan" for item in task.inputs
        ):
            return False
        try:
            value = json.loads(
                self.artifacts.read(capability[0].artifact_ref).decode("utf-8")
            )
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False
        return isinstance(value, dict) and value.get("solver_kind") == "sprocess"

    def _latest_deck_workspace_retry(
        self, *, assignment: WorkerAssignment, workspace: Path
    ) -> tuple[Any, dict[str, object]] | None:
        model = _deck_project_model()
        for context in reversed(assignment.provisional_contexts):
            directory = workspace / context.relative_directory
            result_path = directory / "result.json"
            if result_path.is_file() and not result_path.is_symlink():
                try:
                    result = parse_role_result(json.loads(result_path.read_text("utf-8")))
                    project = model.model_validate_json(
                        canonical_json(result.payload), strict=True
                    )
                    return project, result.handoff.model_dump(mode="json")
                except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValidationError):
                    pass
            deck = directory / "deck"
            metadata_path = deck / "project.json"
            handoff_path = deck / "handoff.json"
            if not metadata_path.is_file() or not handoff_path.is_file():
                continue
            try:
                metadata = json.loads(metadata_path.read_text("utf-8"))
                files = _read_deck_workspace_files(deck / "files")
                project = model.model_validate_json(
                    canonical_json({**metadata, "files": files}), strict=True
                )
                handoff = RoleHandoff.model_validate_json(
                    handoff_path.read_bytes(), strict=True
                ).model_dump(mode="json")
                return project, handoff
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValidationError, TaskInputError):
                continue
        return None

    def _build_author_result_from_deck_workspace(
        self, session: Any, task: AgentTask
    ) -> bytes:
        workspace = self.workspace_root / session.session_id
        deck = workspace / "deck"
        metadata_path = deck / "project.json"
        declarations_path = deck / "declarations.json"
        handoff_path = deck / "handoff.json"
        try:
            metadata_raw = _read_regular_deck_file(
                deck, Path("project.json"), max_bytes=8 * 1024 * 1024
            )
            handoff_raw = _read_regular_deck_file(
                deck, Path("handoff.json"), max_bytes=64 * 1024
            )
            metadata = json.loads(metadata_raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise TaskInputError(
                "deck/project.json is not valid UTF-8 JSON",
                details=(
                    {
                        "path": "$.deck.project",
                        "message": str(error),
                        "type": "json_invalid",
                    },
                ),
            ) from error
        if not isinstance(metadata, dict) or "files" in metadata:
            raise TaskInputError(
                "deck/project.json must contain project metadata without embedded files",
                details=(
                    {
                        "path": "$.deck.project.files",
                        "message": "source files are controlled by deck/files",
                        "type": "value_error",
                    },
                ),
            )
        files = _read_deck_workspace_files(deck / "files")
        try:
            handoff = RoleHandoff.model_validate_json(handoff_raw, strict=True)
        except ValidationError as error:
            raise TaskInputError(
                "TCAD deck workspace is invalid",
                details=_prefix_validation_paths(
                    _validation_details(error), "$.deck"
                ),
            ) from error

        experiment_plan = tuple(
            item for item in task.inputs if item.name == "experiment_plan"
        )
        capability = tuple(
            item for item in task.inputs if item.name == "execution_capability"
        )
        if self._uses_deck_materializer(task):
            materializer = import_module("tcad_artifact.project_materializer")
            try:
                declarations_raw = _read_regular_deck_file(
                    deck, Path("declarations.json"), max_bytes=8 * 1024 * 1024
                )
                declarations = json.loads(declarations_raw.decode("utf-8"))
            except (TaskInputError, UnicodeDecodeError, json.JSONDecodeError) as error:
                raise TaskInputError(
                    "deck/declarations.json is not valid UTF-8 JSON"
                ) from error
            if not isinstance(declarations, dict):
                raise TaskInputError("deck/declarations.json must be an object")
            preflight: dict[str, object] | None = None
            try:
                preflight_raw = _read_regular_deck_file(
                    deck, Path("reports/preflight.json"), max_bytes=16 * 1024
                )
            except TaskInputError:
                pass
            else:
                try:
                    parsed_preflight = json.loads(preflight_raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as error:
                    raise TaskInputError(
                        "control-owned deck preflight report is invalid"
                    ) from error
                if not isinstance(parsed_preflight, dict):
                    raise TaskInputError(
                        "control-owned deck preflight report must be an object"
                    )
                preflight = parsed_preflight
            try:
                project = materializer.materialize_deck_project(
                    metadata=metadata,
                    declarations=declarations,
                    files=files,
                    experiment_plan=self.artifacts.read(
                        experiment_plan[0].artifact_ref
                    ),
                    execution_capability=self.artifacts.read(
                        capability[0].artifact_ref
                    ),
                    preflight_attestation=preflight,
                )
            except materializer.ProjectMaterializationError as error:
                report_path = deck / "reports" / "materialization.json"
                report_path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
                _write_control_output_file(
                    report_path, materializer.report_json(error.report)
                )
                raise TaskInputError(
                    "TCAD deck deterministic materialization failed",
                    details=error.details,
                ) from error
            report_path = deck / "reports" / "materialization.json"
            report_path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
            assert project.materialization_report is not None
            _write_control_output_file(
                report_path,
                materializer.report_json(project.materialization_report),
            )
        else:
            model = _deck_project_model()
            try:
                project = model.model_validate_json(
                    canonical_json({**metadata, "files": files}), strict=True
                )
            except ValidationError as error:
                raise TaskInputError(
                    "TCAD deck workspace is invalid",
                    details=_prefix_validation_paths(
                        _validation_details(error), "$.deck"
                    ),
                ) from error

        if task.context_profile in _TCAD_DECK_AUTHOR_REVISION_PROFILES:
            base = self._task_deck_project(task, "prior_project")
            frozen = ("tool_profile", "solver_kind", "capability_sha256")
            changed = tuple(
                name for name in frozen if getattr(base, name) != getattr(project, name)
            )
            if changed:
                raise TaskInputError(
                    "revised deck changed its frozen execution capability",
                    details=tuple(
                        {
                            "path": f"$.deck.project.{name}",
                            "message": "field must equal prior_project",
                            "type": "frozen_field_changed",
                        }
                        for name in changed
                    ),
                )

        envelope = RoleResultEnvelope[Any](
            schema_version=1, handoff=handoff, payload=project
        ).canonical_json()
        limit = task.output.max_bytes + _ROLE_RESULT_ENVELOPE_OVERHEAD_BYTES
        if len(envelope) > limit:
            raise TaskInputError("control-built deck result exceeds its byte limit")
        output_directory = workspace / "output"
        output_directory.mkdir(parents=True, mode=0o700, exist_ok=True)
        destination = output_directory / "result.json"
        _write_control_output_file(destination, envelope)
        return envelope

    def begin_worker_file_write(
        self,
        session_token: str,
        *,
        worker_id: str,
        relative_path: str,
        expected_bytes: int | None,
        operation: str,
    ) -> int:
        """Begin one bounded task-relative file creation or unified-diff patch."""

        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        task = self.get_task(session.task_id)
        workspace = self._materialized_worker_workspace(session.session_id)
        target = self._worker_file_target(
            workspace=workspace,
            task=task,
            relative_path=relative_path,
        )
        exists = target.path.exists() or target.path.is_symlink()
        if operation == "create":
            if exists:
                raise TaskInputError(
                    "existing worker files must be changed with a unified diff"
                )
            upload_limit = target.max_bytes
        elif operation == "patch":
            if not exists:
                raise TaskInputError("worker patch target does not exist")
            if not target.text_required:
                raise TaskInputError("binary worker files cannot be patched")
            upload_limit = min(2 * target.max_bytes, 16 * 1024 * 1024)
        else:
            raise TaskInputError("worker file operation is unsupported")
        if expected_bytes is not None and (
            expected_bytes < 0 or expected_bytes > upload_limit
        ):
            raise TaskInputError("worker file operation exceeds its byte limit")
        data_path = workspace / _WORKER_FILE_UPLOAD_DATA
        metadata_path = workspace / _WORKER_FILE_UPLOAD_METADATA
        data_path.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)
        descriptor = os.open(
            data_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        os.close(descriptor)
        _write_control_output_file(
            metadata_path,
            canonical_json(
                {
                    "relative_path": relative_path,
                    "expected_bytes": expected_bytes,
                    "operation": operation,
                }
            ),
        )
        return upload_limit

    def append_worker_file_write(
        self,
        session_token: str,
        *,
        worker_id: str,
        content: str,
        encoding: str,
    ) -> int:
        """Append one bounded UTF-8 or base64-decoded upload chunk."""

        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        task = self.get_task(session.task_id)
        workspace = self._materialized_worker_workspace(session.session_id)
        metadata = _read_worker_upload_metadata(workspace)
        target = self._worker_file_target(
            workspace=workspace,
            task=task,
            relative_path=metadata["relative_path"],
        )
        if encoding == "utf8":
            raw = content.encode("utf-8")
        elif encoding == "base64":
            try:
                raw = base64.b64decode(content, validate=True)
            except (binascii.Error, ValueError) as error:
                raise TaskInputError("worker file chunk is not valid base64") from error
        else:
            raise TaskInputError("worker file chunk encoding is unsupported")
        if len(raw) > _WORKER_FILE_UPLOAD_BYTES:
            raise TaskInputError("worker file chunk exceeds its byte limit")
        upload = workspace / _WORKER_FILE_UPLOAD_DATA
        flags = os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(upload, flags)
        except OSError as error:
            raise TaskInputError("worker file write has not been started") from error
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            details = os.fstat(descriptor)
            if not stat.S_ISREG(details.st_mode):
                raise TaskInputError("worker file upload must be one regular file")
            expected = metadata["expected_bytes"]
            operation = metadata["operation"]
            upload_limit = (
                target.max_bytes
                if operation == "create"
                else min(2 * target.max_bytes, 16 * 1024 * 1024)
            )
            if details.st_size + len(raw) > (
                expected if expected is not None else upload_limit
            ):
                raise TaskInputError("worker file upload exceeds its declared size")
            with os.fdopen(descriptor, "ab", closefd=False) as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            return details.st_size + len(raw)
        finally:
            os.close(descriptor)

    def commit_worker_file_write(
        self, session_token: str, *, worker_id: str
    ) -> tuple[str, int]:
        """Atomically publish a new file or apply the uploaded unified diff."""

        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        task = self.get_task(session.task_id)
        workspace = self._materialized_worker_workspace(session.session_id)
        metadata = _read_worker_upload_metadata(workspace)
        target = self._worker_file_target(
            workspace=workspace,
            task=task,
            relative_path=metadata["relative_path"],
        )
        upload = workspace / _WORKER_FILE_UPLOAD_DATA
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(upload, flags)
        except OSError as error:
            raise TaskInputError("worker file write has not been started") from error
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            details = os.fstat(descriptor)
            if not stat.S_ISREG(details.st_mode):
                raise TaskInputError("worker file upload must be one regular file")
            if (
                metadata["expected_bytes"] is not None
                and details.st_size != metadata["expected_bytes"]
            ):
                raise TaskInputError("worker file upload is incomplete")
            operation = metadata["operation"]
            upload_limit = (
                target.max_bytes
                if operation == "create"
                else min(2 * target.max_bytes, 16 * 1024 * 1024)
            )
            if details.st_size > upload_limit:
                raise TaskInputError("worker file operation exceeds its byte limit")
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                raw = stream.read(upload_limit + 1)
        finally:
            os.close(descriptor)
        if len(raw) != details.st_size:
            raise TaskInputError("worker file upload changed during commit")
        if operation == "create":
            if target.path.exists() or target.path.is_symlink():
                raise TaskInputError(
                    "existing worker files must be changed with a unified diff"
                )
            if target.text_required:
                try:
                    raw.decode("utf-8")
                except UnicodeDecodeError as error:
                    raise TaskInputError("worker file must be valid UTF-8") from error
            if (
                metadata["relative_path"] == "output/result.json"
                and task.output.format == "json"
                and task.role != "tcad_deck_author"
            ):
                _require_patchable_worker_json(raw)
            _prepare_worker_file_parent(workspace, target.path.parent)
            _replace_worker_file(upload, target.path)
            final_size = len(raw)
        elif operation == "patch":
            try:
                patch = raw.decode("utf-8")
            except UnicodeDecodeError as error:
                raise TaskInputError("worker file patch must be valid UTF-8") from error
            original_raw = _read_regular_worker_file(
                workspace, target.path, max_bytes=target.max_bytes
            )
            try:
                original = original_raw.decode("utf-8")
            except UnicodeDecodeError as error:
                raise TaskInputError("worker patch target is not valid UTF-8") from error
            try:
                revised_raw = _apply_worker_patch(
                    original,
                    patch,
                    relative_path=metadata["relative_path"],
                    max_patch_bytes=min(2 * target.max_bytes, 16 * 1024 * 1024),
                ).encode("utf-8")
            except TaskInputError:
                self.record_activity(
                    session_token,
                    worker_id=worker_id,
                    activity="worker_file_patch_rejected",
                )
                raise
            if len(revised_raw) > target.max_bytes:
                raise TaskInputError("patched worker file exceeds its byte limit")
            if (
                metadata["relative_path"] == "output/result.json"
                and task.output.format == "json"
                and task.role != "tcad_deck_author"
            ):
                _require_patchable_worker_json(revised_raw)
            _atomic_worker_file_write(workspace, target.path, revised_raw)
            upload.unlink(missing_ok=True)
            final_size = len(revised_raw)
        else:
            raise TaskInputError("worker file upload metadata is invalid")
        (workspace / _WORKER_FILE_UPLOAD_METADATA).unlink(missing_ok=True)
        self.record_activity(
            session_token,
            worker_id=worker_id,
            activity=(
                "worker_file_patched"
                if operation == "patch"
                else "worker_file_written"
            ),
        )
        self._record_parseable_output_progress(
            session_token,
            worker_id=worker_id,
            task=task,
            relative_path=metadata["relative_path"],
            raw=raw if operation == "create" else revised_raw,
        )
        return metadata["relative_path"], final_size

    def apply_worker_file_patch(
        self,
        session_token: str,
        *,
        worker_id: str,
        relative_path: str,
        patch: str,
    ) -> int:
        """Apply one bounded unified diff to one task-relative text file."""

        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        task = self.get_task(session.task_id)
        workspace = self._materialized_worker_workspace(session.session_id)
        target = self._worker_file_target(
            workspace=workspace,
            task=task,
            relative_path=relative_path,
        )
        raw = _read_regular_worker_file(
            workspace, target.path, max_bytes=target.max_bytes
        )
        try:
            original = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise TaskInputError("worker patch target is not valid UTF-8") from error
        try:
            revised = _apply_worker_patch(
                original,
                patch,
                relative_path=relative_path,
                max_patch_bytes=_WORKER_FILE_UPLOAD_BYTES,
            )
        except TaskInputError:
            self.record_activity(
                session_token,
                worker_id=worker_id,
                activity="worker_file_patch_rejected",
            )
            raise
        revised_raw = revised.encode("utf-8")
        if len(revised_raw) > target.max_bytes:
            raise TaskInputError("patched worker file exceeds its byte limit")
        if (
            relative_path == "output/result.json"
            and task.output.format == "json"
            and task.role != "tcad_deck_author"
        ):
            _require_patchable_worker_json(revised_raw)
        _atomic_worker_file_write(workspace, target.path, revised_raw)
        self.record_activity(
            session_token, worker_id=worker_id, activity="worker_file_patched"
        )
        self._record_parseable_output_progress(
            session_token,
            worker_id=worker_id,
            task=task,
            relative_path=relative_path,
            raw=revised_raw,
        )
        return len(revised_raw)

    def apply_worker_file_json_patch(
        self,
        session_token: str,
        *,
        worker_id: str,
        relative_path: str,
        operations: tuple[dict[str, Any], ...],
        expected_digest: str | None,
    ) -> tuple[int, str]:
        """Apply one CAS-guarded bounded JSON Pointer patch atomically."""

        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        task = self.get_task(session.task_id)
        workspace = self._materialized_worker_workspace(session.session_id)
        target = self._worker_file_target(
            workspace=workspace,
            task=task,
            relative_path=relative_path,
        )
        if target.path.suffix.lower() != ".json":
            raise TaskInputError("worker JSON patch target must have a .json suffix")
        lock_descriptor = os.open(
            workspace, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        )
        try:
            fcntl.flock(lock_descriptor, fcntl.LOCK_EX)
            raw = _read_regular_worker_file(
                workspace, target.path, max_bytes=target.max_bytes
            )
            current_digest = hashlib.sha256(raw).hexdigest()
            if expected_digest is not None and expected_digest != current_digest:
                raise TaskInputError(
                    "worker JSON patch expected_digest does not match current file; "
                    f"current_digest={current_digest}"
                )
            if expected_digest is None and not any(
                operation.get("op") == "test" for operation in operations
            ):
                raise TaskInputError(
                    "worker JSON patch requires expected_digest or a test operation"
                )
            try:
                document = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise TaskInputError(
                    "worker JSON patch target is not valid JSON"
                ) from error
            try:
                revised = _apply_worker_json_patch(document, operations)
                revised_raw = (
                    json.dumps(
                        revised,
                        ensure_ascii=False,
                        indent=2,
                        allow_nan=False,
                    )
                    + "\n"
                ).encode("utf-8")
            except (TypeError, ValueError) as error:
                self.record_activity(
                    session_token,
                    worker_id=worker_id,
                    activity="worker_file_patch_rejected",
                )
                raise TaskInputError(f"worker JSON patch rejected: {error}") from error
            if len(revised_raw) > target.max_bytes:
                raise TaskInputError("patched worker JSON exceeds its byte limit")
            if (
                relative_path == "output/result.json"
                and task.output.format == "json"
                and task.role != "tcad_deck_author"
            ):
                _require_patchable_worker_json(revised_raw)
            _atomic_worker_file_write(workspace, target.path, revised_raw)
        finally:
            fcntl.flock(lock_descriptor, fcntl.LOCK_UN)
            os.close(lock_descriptor)
        self.record_activity(
            session_token, worker_id=worker_id, activity="worker_file_json_patched"
        )
        self._record_parseable_output_progress(
            session_token,
            worker_id=worker_id,
            task=task,
            relative_path=relative_path,
            raw=revised_raw,
        )
        return len(revised_raw), hashlib.sha256(revised_raw).hexdigest()

    def _record_parseable_output_progress(
        self,
        session_token: str,
        *,
        worker_id: str,
        task: AgentTask,
        relative_path: str,
        raw: bytes,
    ) -> None:
        if (
            relative_path == "output/result.json"
            and task.output.format == "json"
            and _is_parseable_json(raw)
        ):
            self.record_activity(
                session_token,
                worker_id=worker_id,
                activity="output_json_parseable",
            )

    def delete_worker_file(
        self,
        session_token: str,
        *,
        worker_id: str,
        relative_path: str,
    ) -> None:
        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        task = self.get_task(session.task_id)
        workspace = self._materialized_worker_workspace(session.session_id)
        target = self._worker_file_target(
            workspace=workspace,
            task=task,
            relative_path=relative_path,
        )
        if not target.removable:
            raise TaskInputError("required worker file cannot be deleted")
        _read_regular_worker_file(workspace, target.path, max_bytes=target.max_bytes)
        target.path.unlink()
        self.record_activity(
            session_token, worker_id=worker_id, activity="worker_file_deleted"
        )

    def move_worker_file(
        self,
        session_token: str,
        *,
        worker_id: str,
        source_relative_path: str,
        destination_relative_path: str,
    ) -> int:
        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        task = self.get_task(session.task_id)
        workspace = self._materialized_worker_workspace(session.session_id)
        source = self._worker_file_target(
            workspace=workspace,
            task=task,
            relative_path=source_relative_path,
        )
        destination = self._worker_file_target(
            workspace=workspace,
            task=task,
            relative_path=destination_relative_path,
        )
        if not source.removable or not destination.removable:
            raise TaskInputError("required worker file cannot be moved")
        raw = _read_regular_worker_file(
            workspace, source.path, max_bytes=source.max_bytes
        )
        if len(raw) > destination.max_bytes:
            raise TaskInputError("moved worker file exceeds its byte limit")
        if destination.path.exists() or destination.path.is_symlink():
            raise TaskInputError("worker file move destination already exists")
        _prepare_worker_file_parent(workspace, destination.path.parent)
        os.rename(source.path, destination.path)
        self.record_activity(
            session_token, worker_id=worker_id, activity="worker_file_moved"
        )
        return len(raw)

    def _materialized_worker_workspace(self, session_id: str) -> Path:
        workspace = self.workspace_root / session_id
        assignment = workspace / "assignment.json"
        if not assignment.is_file() or assignment.is_symlink():
            raise TaskInputError("worker assignment has not been materialized")
        return workspace

    def _worker_file_target(
        self,
        *,
        workspace: Path,
        task: AgentTask,
        relative_path: str,
    ) -> _WorkerFileTarget:
        relative = _validated_worker_file_path(relative_path)
        parts = relative.parts
        text_required = True
        removable = False
        if task.role == "tcad_deck_author":
            if relative == Path("deck/project.json"):
                if self._uses_deck_materializer(task):
                    raise TaskInputError(
                        "deck/project.json is a control-generated read-only projection"
                    )
                limit = 8 * 1024 * 1024
            elif relative == Path("deck/declarations.json"):
                if not self._uses_deck_materializer(task):
                    raise TaskInputError(
                        "deck/declarations.json applies only to declared-source projects"
                    )
                limit = 8 * 1024 * 1024
            elif relative == Path("deck/handoff.json"):
                limit = 64 * 1024
            elif len(parts) >= 3 and parts[:2] == ("deck", "files"):
                limit = 8 * 1024 * 1024
                removable = True
            else:
                raise TaskInputError(
                    "TCAD deck author may write only deck project, handoff, and files"
                )
        elif relative == Path("output/result.json"):
            limit = task.output.max_bytes + _ROLE_RESULT_ENVELOPE_OVERHEAD_BYTES
        elif task.output.collections and relative == Path("output/bundle.json"):
            limit = min(task.output.max_bundle_bytes, 1024 * 1024)
        elif (
            task.output.collections
            and len(parts) == 4
            and parts[:2] == ("output", "collections")
        ):
            collection, item = parts[2:]
            specs = {value.name: value for value in task.output.collections}
            spec = specs.get(collection)
            if spec is None or re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9_.-]*", item
            ) is None:
                raise TaskInputError("worker collection path is not declared")
            limit = spec.max_item_bytes
            text_required = False
            removable = True
        else:
            raise TaskInputError("worker file path is outside the task write scope")
        return _WorkerFileTarget(
            path=workspace / relative,
            max_bytes=limit,
            text_required=text_required,
            removable=removable,
        )

    def begin_result_upload(self, session_token: str, *, worker_id: str) -> None:
        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        output_directory = self.workspace_root / session.session_id / "output"
        output_directory.mkdir(parents=True, mode=0o700, exist_ok=True)
        upload = output_directory / ".result.upload"
        upload.unlink(missing_ok=True)
        descriptor = os.open(
            upload,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        os.close(descriptor)

    def append_result_upload(
        self, session_token: str, *, worker_id: str, content: str
    ) -> int:
        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        task = self.get_task(session.task_id)
        raw = content.encode("utf-8")
        if len(raw) > _RESULT_UPLOAD_CHUNK_BYTES:
            raise TaskInputError("result upload chunk exceeds its byte limit")
        upload = self.workspace_root / session.session_id / "output/.result.upload"
        flags = os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(upload, flags)
        except OSError as error:
            raise TaskInputError("result upload has not been started") from error
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            details = os.fstat(descriptor)
            if not stat.S_ISREG(details.st_mode):
                raise TaskInputError("result upload must be one regular file")
            limit = task.output.max_bytes + _ROLE_RESULT_ENVELOPE_OVERHEAD_BYTES
            if details.st_size + len(raw) > limit:
                raise TaskInputError("worker result envelope exceeds its byte limit")
            with os.fdopen(descriptor, "ab", closefd=False) as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            return details.st_size + len(raw)
        finally:
            os.close(descriptor)

    def commit_result_upload(self, session_token: str, *, worker_id: str) -> int:
        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        task = self.get_task(session.task_id)
        output_directory = self.workspace_root / session.session_id / "output"
        upload = output_directory / ".result.upload"
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(upload, flags)
        except OSError as error:
            raise TaskInputError("result upload has not been started") from error
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            details = os.fstat(descriptor)
            if not stat.S_ISREG(details.st_mode):
                raise TaskInputError("result upload must be one regular file")
            limit = task.output.max_bytes + _ROLE_RESULT_ENVELOPE_OVERHEAD_BYTES
            if details.st_size > limit:
                raise TaskInputError("worker result envelope exceeds its byte limit")
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                raw = stream.read(limit + 1)
            if len(raw) > limit:
                raise TaskInputError("worker result envelope exceeds its byte limit")
            try:
                raw.decode("utf-8")
            except UnicodeDecodeError as error:
                raise TaskInputError(
                    "worker result upload is not valid UTF-8"
                ) from error
            os.replace(upload, output_directory / "result.json")
        finally:
            os.close(descriptor)
        self.record_activity(
            session_token, worker_id=worker_id, activity="output_written"
        )
        return len(raw)

    def checkpoint_output(self, session_token: str, *, worker_id: str) -> str:
        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        task = self.get_task(session.task_id)
        manifest = self._freeze_workspace_snapshot(
            session=session,
            task=task,
            reason="checkpoint",
            validation_status="not_validated",
        )
        self.record_activity(
            session_token, worker_id=worker_id, activity="output_checkpointed"
        )
        return f"snapshot_{manifest.sequence}"

    def validate_output_file(
        self, session_token: str, *, worker_id: str
    ) -> tuple[bool, int | None, tuple[dict[str, str], ...]]:
        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        task = self.get_task(session.task_id)
        self._begin_file_validation(session, task)
        try:
            try:
                content = self._read_output_file_for_session(session, task)
                raw, _, _ = self._validate_complete_output(
                    task, attempt=session.attempt, content=content
                )
            except TaskInputError as error:
                details = error.details or (
                    {"path": "$", "message": str(error), "type": "value_error"},
                )
                self._reject_file_validation(
                    session, task, diagnostics=details
                )
                return False, None, details
            validated_artifacts: tuple[_ValidatedOutputArtifact, ...] = ()
            if task.output.collections:
                try:
                    validated_artifacts = self._read_output_bundle(
                        session.session_id,
                        task,
                        attempt=session.attempt,
                        primary_size=len(raw),
                        primary_content=json.loads(raw),
                        primary_envelope=content,
                    )
                except TaskInputError as error:
                    details = error.details or (
                        {
                            "path": "$.bundle",
                            "message": str(error),
                            "type": "value_error",
                        },
                    )
                    self._reject_file_validation(
                        session, task, diagnostics=details
                    )
                    return False, None, details
            manifest = self._freeze_workspace_snapshot(
                session=session,
                task=task,
                reason="finalization_candidate",
                validation_status="valid",
                validated_artifacts=validated_artifacts,
            )
            self._seal_file_validation(session, manifest)
            return True, len(raw), ()
        except Exception:
            self._abort_file_validation(session, task)
            raise

    def write_result_file(
        self,
        session_token: str,
        *,
        worker_id: str,
        content: Any,
    ) -> int:
        """Validate and atomically stage one primary worker result."""

        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        task = self.get_task(session.task_id)
        self._require_current_output_contract(task)
        self._validate_complete_output(
            task, attempt=session.attempt, content=content
        )
        raw = parse_role_result(content).canonical_json()
        if len(raw) > task.output.max_bytes + _ROLE_RESULT_ENVELOPE_OVERHEAD_BYTES:
            raise TaskInputError("worker result envelope exceeds its byte limit")
        output_directory = self.workspace_root / session.session_id / "output"
        output_directory.mkdir(parents=True, mode=0o700, exist_ok=True)
        destination = output_directory / "result.json"
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".result.json.", dir=output_directory
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return len(raw)

    def finalize_file(
        self,
        session_token: str,
        *,
        worker_id: str,
    ) -> None:
        session = self.tokens.verify_session_binding(
            session_token, worker_id=worker_id
        )
        task = self.get_task(session.task_id)
        manifest = self._begin_sealed_finalization(session)
        content, validated_artifacts = self._sealed_output(manifest, task)
        self._finalize_validated_output(
            session=session,
            task=task,
            worker_id=worker_id,
            content=content,
            validated_artifacts=validated_artifacts,
        )

    def _read_output_file(self, session_token: str, *, worker_id: str) -> Any:
        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        task = self.get_task(session.task_id)
        return self._read_output_file_for_session(session, task)

    def _read_output_file_for_session(self, session: Any, task: AgentTask) -> Any:
        if task.role == "tcad_deck_author" and not self._legacy_author_result_is_staged(
            session
        ):
            self._build_author_result_from_deck_workspace(session, task)
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
            file_limit = (
                task.output.max_bytes + _ROLE_RESULT_ENVELOPE_OVERHEAD_BYTES
            )
            if details.st_size > file_limit:
                raise TaskInputError("worker output exceeds its byte limit")
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                raw = stream.read(file_limit + 1)
        finally:
            os.close(descriptor)
        if len(raw) > file_limit:
            raise TaskInputError("worker output exceeds its byte limit")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise TaskInputError("worker output is not valid UTF-8") from error
        if task.output.format == "text":
            return text
        if task.role != "tcad_deck_author":
            _require_patchable_worker_json(raw)
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

    def _legacy_author_result_is_staged(self, session: Any) -> bool:
        """Keep old sealed/uploaded author attempts readable during migration."""

        workspace = self.workspace_root / session.session_id
        output = workspace / "output/result.json"
        if not output.is_file() or output.is_symlink():
            return False
        deck = workspace / "deck"
        if not deck.exists():
            return True
        try:
            metadata = json.loads(
                _read_regular_deck_file(
                    deck, Path("project.json"), max_bytes=8 * 1024 * 1024
                ).decode("utf-8")
            )
            handoff = json.loads(
                _read_regular_deck_file(
                    deck, Path("handoff.json"), max_bytes=64 * 1024
                ).decode("utf-8")
            )
            files = _read_deck_workspace_file_bytes(deck / "files")
        except (TaskInputError, UnicodeDecodeError, json.JSONDecodeError):
            return False
        return (
            isinstance(metadata, dict)
            and metadata.get("entrypoint") is None
            and metadata.get("resource_limits") is None
            and not files
            and isinstance(handoff, dict)
            and handoff.get("verdict") is None
            and handoff.get("summary") is None
        )

    def _read_output_bundle(
        self,
        session_id: str,
        task: AgentTask,
        *,
        attempt: int,
        primary_size: int,
        primary_content: dict[str, Any],
        primary_envelope: dict[str, Any],
    ) -> tuple[_ValidatedOutputArtifact, ...]:
        output_directory = self.workspace_root / session_id / "output"
        try:
            bundle_raw = _read_regular_output_file(
                output_directory,
                Path("bundle.json"),
                max_bytes=1024 * 1024,
            )
        except TaskInputError as error:
            raise _bundle_error(str(error), "$.bundle") from error
        try:
            bundle = TaskOutputBundle.model_validate_json(bundle_raw, strict=True)
        except ValidationError as error:
            raise TaskInputError(
                "worker output bundle is invalid",
                details=_prefix_validation_paths(
                    _validation_details(error), "$.bundle"
                ),
            ) from error

        specs = {item.name: item for item in task.output.collections}
        by_collection: dict[str, list[_ValidatedOutputArtifact]] = {
            name: [] for name in specs
        }
        expected_paths: set[str] = set()
        total_bytes = 0
        for index, descriptor in enumerate(bundle.items):
            try:
                spec = specs[descriptor.collection]
            except KeyError as error:
                raise _bundle_error(
                    "bundle declares an unconfigured collection",
                    f"$.bundle.items[{index}].collection",
                ) from error
            allowed_media_types = {
                value.strip().lower() for value in spec.media_types
            }
            if descriptor.media_type.strip().lower() not in allowed_media_types:
                raise _bundle_error(
                    "bundle item media_type is not allowed for its collection",
                    f"$.bundle.items[{index}].media_type",
                )
            relative_path = Path(descriptor.relative_path)
            content = _read_regular_output_file(
                output_directory,
                relative_path,
                max_bytes=spec.max_item_bytes,
            )
            base_media_type = (
                descriptor.media_type.split(";", 1)[0].strip().lower()
            )
            child_value: Any | None = None
            if base_media_type == "application/json":
                try:
                    child_value = json.loads(content.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as error:
                    raise _bundle_error(
                        "JSON collection item is not valid UTF-8 JSON",
                        f"$.bundle.items[{index}].relative_path",
                    ) from error
                if spec.schema_id != "opaque" and not isinstance(child_value, dict):
                    raise _bundle_error(
                        "schema-bound JSON collection item must be an object",
                        f"$.bundle.items[{index}].relative_path",
                    )
            if spec.validator is not None:
                if child_value is None or not isinstance(child_value, dict):
                    raise _bundle_error(
                        "validated collection item must be a JSON object",
                        f"$.bundle.items[{index}].relative_path",
                    )
                try:
                    _validate_role_output(spec.validator, child_value)
                except TaskInputError as error:
                    raise TaskInputError(
                        str(error),
                        details=_prefix_validation_paths(
                            error.details,
                            f"$.bundle.items[{index}]",
                        ),
                    ) from error
            validated = _ValidatedOutputArtifact(
                descriptor=descriptor,
                spec=spec,
                content=content,
            )
            by_collection[descriptor.collection].append(validated)
            expected_paths.add(descriptor.relative_path)
            total_bytes += len(content)

        for name, spec in specs.items():
            items = by_collection[name]
            if not spec.min_items <= len(items) <= spec.max_items:
                raise _bundle_error(
                    f"collection {name} item count is outside its configured bounds",
                    "$.bundle.items",
                )
            if sum(len(item.content) for item in items) > spec.max_total_bytes:
                raise _bundle_error(
                    f"collection {name} exceeds its total byte limit",
                    "$.bundle.items",
                )
        if primary_size + total_bytes > task.output.max_bundle_bytes:
            raise _bundle_error(
                "task output bundle exceeds its aggregate byte limit",
                "$.bundle.items",
            )
        actual_paths = _collection_output_paths(output_directory)
        if actual_paths != expected_paths:
            raise _bundle_error(
                "collection files must exactly match output/bundle.json",
                "$.bundle.items",
            )
        validated_artifacts = tuple(
            sorted(
                (item for items in by_collection.values() for item in items),
                key=lambda item: (
                    item.descriptor.collection,
                    item.descriptor.item,
                ),
            )
        )
        for name, spec in specs.items():
            if spec.bundle_validator is None:
                continue
            _validate_collection_bundle(
                spec.bundle_validator,
                primary_content,
                {
                    item.descriptor.item: item.content
                    for item in by_collection[name]
                },
            )
        validation_report = _validate_figure_evidence_bundle(validated_artifacts)
        if validation_report is not None:
            _validate_figure_evidence_handoff_binding(
                primary_envelope, validation_report
            )
            validated_artifacts += (validation_report,)
        self._validate_device_parameter_evidence_bundle(
            task=task,
            attempt=attempt,
            primary_content=primary_content,
            artifacts=validated_artifacts,
        )
        return validated_artifacts

    def _validate_device_parameter_evidence_bundle(
        self,
        *,
        task: AgentTask,
        attempt: int,
        primary_content: dict[str, Any],
        artifacts: tuple[_ValidatedOutputArtifact, ...],
    ) -> None:
        by_collection = {
            item.descriptor.collection: item
            for item in artifacts
            if item.descriptor.collection
            in {"parameter_requirements", "device_parameters", "source_catalog"}
        }
        if not by_collection:
            return
        if set(by_collection) != {
            "parameter_requirements",
            "device_parameters",
            "source_catalog",
        }:
            raise _bundle_error(
                "device parameter evidence requires requirements, parameter, and source files",
                "$.bundle.items",
            )
        requirement_input = next(
            (item for item in task.inputs if item.name == "parameter_requirements"),
            None,
        )
        try:
            intake = ScientificIntake.model_validate_json(
                canonical_json(primary_content), strict=True
            )
            requirements = DeviceParameterRequirementSet.model_validate_json(
                by_collection["parameter_requirements"].content, strict=True
            )
            parameters = DeviceParameterSet.model_validate_json(
                by_collection["device_parameters"].content, strict=True
            )
            catalog = EvidenceSourceCatalog.model_validate_json(
                by_collection["source_catalog"].content, strict=True
            )
            evaluate_device_parameter_coverage(requirements, parameters, catalog)
        except (ValidationError, ValueError) as error:
            raise _bundle_error(
                f"device parameter evidence is inconsistent: {error}",
                "$.bundle.items",
            ) from error
        if requirement_input is not None:
            try:
                supplied_requirements = (
                    DeviceParameterRequirementSet.model_validate_json(
                        self.artifacts.read(requirement_input.artifact_ref),
                        strict=True,
                    )
                )
            except ValidationError as error:
                raise _bundle_error(
                    f"supplied parameter requirements are invalid: {error}",
                    "$.bundle.items",
                ) from error
            if not _same_device_parameter_checklist(
                supplied_requirements, requirements
            ):
                raise _bundle_error(
                    "emitted parameter scientific requirements differ from the supplied immutable checklist",
                    "$.bundle.items",
                )
        if not (
            intake.scientific_foundation.objective
            == requirements.objective
            == parameters.objective
        ):
            raise _bundle_error(
                "device parameter evidence does not share the exact intake objective",
                "$.bundle.items",
            )
        observed_keys = {
            observation.source_key
            for claim in parameters.claims
            for observation in claim.observations
        }
        catalog_by_key = {item.source_key: item for item in catalog.sources}
        if observed_keys != set(catalog_by_key):
            raise _bundle_error(
                "source catalog must exactly match parameter observations",
                "$.bundle.items",
            )
        foundation_sources = {
            item.source_key: item
            for item in intake.scientific_foundation.evidence
        }
        if not observed_keys.issubset(foundation_sources):
            raise _bundle_error(
                "every parameter source must also be declared in the scientific intake",
                "$.bundle.items",
            )
        web = {
            item.source_key: item
            for item in self.list_web_evidence(task.task_id)
            if self._web_evidence_attempt(item.snapshot_ref) == attempt
        }
        input_names = {item.name for item in task.inputs}
        for source_key, source in catalog_by_key.items():
            foundation_source = foundation_sources[source_key]
            if foundation_source.source_type != source.source_type:
                raise _bundle_error(
                    f"source type differs for {source_key}",
                    "$.bundle.items",
                )
            if source.source_type == "web_snapshot":
                snapshot = web.get(source_key)
                if snapshot is None or (
                    snapshot.original_url,
                    snapshot.final_url,
                    snapshot.accessed_at,
                ) != (
                    source.original_url,
                    source.final_url,
                    source.accessed_at,
                ):
                    raise _bundle_error(
                        "source catalog metadata does not match frozen web source "
                        f"{source_key}",
                        "$.bundle.items",
                    )
            elif source_key not in input_names:
                raise _bundle_error(
                    "parameter source is neither a frozen web source nor task input: "
                    f"{source_key}",
                    "$.bundle.items",
                )

    def _assignment_provisional_contexts(
        self, task_id: str, *, before_attempt: int
    ) -> tuple[AssignmentProvisionalContext, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT attempt, sequence, manifest_ref_json
                FROM task_provisional_snapshots
                WHERE task_id = ? AND attempt < ?
                ORDER BY attempt, sequence
                """,
                (task_id, before_attempt),
            ).fetchall()
        contexts: list[AssignmentProvisionalContext] = []
        for row in rows:
            manifest_ref = _parse_ref(row["manifest_ref_json"])
            try:
                manifest = ProvisionalSnapshotManifest.model_validate_json(
                    self.artifacts.read(manifest_ref), strict=True
                )
            except ValidationError as error:
                raise TaskServiceError("stored provisional snapshot is invalid") from error
            attempt = int(row["attempt"])
            sequence = int(row["sequence"])
            if manifest.attempt != attempt or manifest.sequence != sequence:
                raise TaskServiceError("stored provisional snapshot mapping is invalid")
            contexts.append(
                AssignmentProvisionalContext(
                    name=f"snapshot_{sequence}",
                    attempt=attempt,
                    reason=manifest.reason,
                    validation_status=manifest.validation_status,
                    relative_directory=(
                        f"provisional/prior_attempt_{attempt}/snapshot_{sequence}"
                    ),
                    file_count=len(manifest.files),
                    size_bytes=sum(item.size_bytes for item in manifest.files),
                    diagnostics_available=bool(manifest.diagnostics),
                    development_only=manifest.development_only,
                )
            )
        return tuple(contexts)

    def _provisional_manifest(
        self, task_id: str, *, attempt: int, name: str
    ) -> ProvisionalSnapshotManifest:
        match = re.fullmatch(r"snapshot_([1-9][0-9]*)", name)
        if match is None:
            raise TaskServiceError("provisional snapshot name is invalid")
        sequence = int(match.group(1))
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT manifest_ref_json FROM task_provisional_snapshots
                WHERE task_id = ? AND attempt = ? AND sequence = ?
                """,
                (task_id, attempt, sequence),
            ).fetchone()
        if row is None:
            raise TaskServiceError("provisional snapshot mapping is missing")
        reference = _parse_ref(row["manifest_ref_json"])
        try:
            manifest = ProvisionalSnapshotManifest.model_validate_json(
                self.artifacts.read(reference), strict=True
            )
        except ValidationError as error:
            raise TaskServiceError("stored provisional snapshot is invalid") from error
        if manifest.attempt != attempt or manifest.sequence != sequence:
            raise TaskServiceError("stored provisional snapshot mapping is invalid")
        return manifest

    def provisional_snapshot_ref(
        self, *, task_id: str, attempt: int, sequence: int
    ) -> ArtifactRef:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT manifest_ref_json FROM task_provisional_snapshots
                WHERE task_id = ? AND attempt = ? AND sequence = ?
                """,
                (task_id, attempt, sequence),
            ).fetchone()
        if row is None:
            raise TaskServiceError("provisional snapshot mapping is missing")
        return _parse_ref(row["manifest_ref_json"])

    def _freeze_workspace_snapshot(
        self,
        *,
        session: Any,
        task: AgentTask,
        reason: str,
        validation_status: str,
        diagnostics: tuple[dict[str, str], ...] = (),
        validated_artifacts: tuple[_ValidatedOutputArtifact, ...] = (),
    ) -> ProvisionalSnapshotManifest:
        if task.role == "tcad_deck_author" and reason != "finalization_candidate":
            files = list(self._deck_workspace_snapshot_files(session.session_id))
        else:
            files = list(self._workspace_snapshot_files(session.session_id, task))
        validated_by_path = {
            value.descriptor.relative_path: value for value in validated_artifacts
            if not value.control_generated
        }
        files = [
            _WorkspaceSnapshotFile(
                relative_path=item.relative_path,
                media_type=(
                    validated_by_path[item.relative_path].descriptor.media_type
                    if item.relative_path in validated_by_path
                    else item.media_type
                ),
                content=item.content,
                collection=(
                    validated_by_path[item.relative_path].descriptor.collection
                    if item.relative_path in validated_by_path
                    else item.collection
                ),
                item=(
                    validated_by_path[item.relative_path].descriptor.item
                    if item.relative_path in validated_by_path
                    else item.item
                ),
                control_generated=item.control_generated,
                materialize_on_retry=item.materialize_on_retry,
            )
            for item in files
        ]
        for value in validated_artifacts:
            if value.control_generated:
                files.append(
                    _WorkspaceSnapshotFile(
                        relative_path=(
                            "control/" + value.descriptor.relative_path
                        ),
                        media_type=value.descriptor.media_type,
                        content=value.content,
                        collection=value.descriptor.collection,
                        item=value.descriptor.item,
                        control_generated=True,
                        materialize_on_retry=True,
                    )
                )
        return self._store_provisional_snapshot(
            session=session,
            task=task,
            reason=reason,
            validation_status=validation_status,
            files=tuple(files),
            diagnostics=diagnostics,
        )

    def store_development_debug_snapshot(
        self,
        *,
        session: Any,
        task: AgentTask,
        files: tuple[_WorkspaceSnapshotFile, ...],
        diagnostics: tuple[dict[str, str], ...],
    ) -> ProvisionalSnapshotManifest:
        return self._store_provisional_snapshot(
            session=session,
            task=task,
            reason="development_debug_result",
            validation_status="not_validated",
            files=files,
            diagnostics=diagnostics,
            development_only=True,
        )

    def _store_provisional_snapshot(
        self,
        *,
        session: Any,
        task: AgentTask,
        reason: str,
        validation_status: str,
        files: tuple[_WorkspaceSnapshotFile, ...],
        diagnostics: tuple[dict[str, str], ...] = (),
        development_only: bool = False,
    ) -> ProvisionalSnapshotManifest:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM task_provisional_snapshots
                WHERE task_id = ? AND attempt = ?
                """,
                (task.task_id, session.attempt),
            ).fetchone()
            if int(row["count"]) >= _PROVISIONAL_SNAPSHOTS_PER_ATTEMPT:
                raise TaskInputError(
                    "provisional snapshot count exceeds its attempt limit"
                )
            task_row = self._row(connection, task.task_id)
            sequence = int(task_row["provisional_sequence"]) + 1
            connection.execute(
                "UPDATE tasks SET provisional_sequence = ? WHERE task_id = ?",
                (sequence, task.task_id),
            )
            connection.execute("COMMIT")
        task_ref = self._task_ref(task.task_id)
        snapshot_id = f"psn_{uuid.uuid4().hex}"
        stored_files: list[ProvisionalSnapshotFile] = []
        for index, item in enumerate(sorted(files, key=lambda value: value.relative_path)):
            relative_path = _validated_provisional_relative_path(
                item.relative_path
            ).as_posix()
            artifact_ref = self.artifacts.register(
                item.content,
                ArtifactRegistration(
                    kind="task_provisional_file",
                    schema_id="opaque",
                    payload_schema_version=1,
                    media_type=item.media_type,
                    creator=self.service_actor,
                    task_ref=task_ref,
                    labels={
                        "role": task.role,
                        "attempt": str(session.attempt),
                        "provisional": "true",
                        "scientific_claim_admissible": "false",
                        **({"development_only": "true"} if development_only else {}),
                    },
                    confidentiality="task_private",
                ),
                idempotency_key=f"{snapshot_id}:file:{index}",
            ).ref
            stored_files.append(
                ProvisionalSnapshotFile(
                    relative_path=relative_path,
                    media_type=item.media_type,
                    size_bytes=len(item.content),
                    artifact_ref=artifact_ref,
                    collection=item.collection,
                    item=item.item,
                    control_generated=item.control_generated,
                    materialize_on_retry=item.materialize_on_retry,
                )
            )
        bounded_diagnostics, diagnostics_truncated = _bounded_provisional_diagnostics(
            diagnostics
        )
        created_at = _timestamp()
        manifest = ProvisionalSnapshotManifest(
            reason=reason,
            attempt=session.attempt,
            sequence=sequence,
            created_at=created_at,
            validation_status=validation_status,
            files=tuple(stored_files),
            diagnostics=bounded_diagnostics,
            diagnostics_truncated=diagnostics_truncated,
            development_only=development_only,
        )
        manifest_ref = self.artifacts.register(
            manifest.canonical_json(),
            ArtifactRegistration(
                kind="task_provisional_snapshot",
                schema_id="scidiscovery.task-provisional-snapshot.v1",
                payload_schema_version=1,
                media_type="application/json",
                creator=self.service_actor,
                parent_refs=(task_ref,) + tuple(item.artifact_ref for item in stored_files),
                task_ref=task_ref,
                labels={
                    "role": task.role,
                    "attempt": str(session.attempt),
                    "provisional": "true",
                    "scientific_claim_admissible": "false",
                    **({"development_only": "true"} if development_only else {}),
                },
                confidentiality="task_private",
            ),
            idempotency_key=f"{snapshot_id}:manifest",
        ).ref
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO task_provisional_snapshots (
                    snapshot_id, task_id, attempt, sequence, reason,
                    manifest_ref_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    task.task_id,
                    session.attempt,
                    sequence,
                    reason,
                    manifest_ref.canonical_json(),
                    created_at,
                ),
            )
        return manifest

    def _workspace_snapshot_files(
        self, session_id: str, task: AgentTask
    ) -> tuple[_WorkspaceSnapshotFile, ...]:
        output_directory = self.workspace_root / session_id / "output"
        try:
            details = os.lstat(output_directory)
        except OSError:
            return ()
        if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode):
            raise TaskInputError("worker output directory must be a real directory")
        values: list[_WorkspaceSnapshotFile] = []
        primary_limit = task.output.max_bytes + _ROLE_RESULT_ENVELOPE_OVERHEAD_BYTES
        for name, media_type, limit in (
            ("result.json", "application/json", primary_limit),
            ("bundle.json", "application/json", 1024 * 1024),
        ):
            path = output_directory / name
            if path.exists() or path.is_symlink():
                try:
                    content = _read_regular_output_file(
                        output_directory, Path(name), max_bytes=limit
                    )
                except TaskInputError:
                    continue
                values.append(
                    _WorkspaceSnapshotFile(
                        relative_path=name,
                        media_type=media_type,
                        content=content,
                    )
                )
        collections = output_directory / "collections"
        if collections.exists() or collections.is_symlink():
            specs = {item.name: item for item in task.output.collections}
            total_by_collection = {name: 0 for name in specs}
            count_by_collection = {name: 0 for name in specs}
            try:
                collection_paths = sorted(_collection_output_paths(output_directory))
            except TaskInputError:
                collection_paths = []
            for relative in collection_paths:
                parts = Path(relative).parts
                if len(parts) != 3 or parts[0] != "collections":
                    continue
                collection, item = parts[1:]
                spec = specs.get(collection)
                if spec is None or not re.fullmatch(
                    r"[A-Za-z0-9][A-Za-z0-9_.-]*", item
                ):
                    continue
                try:
                    content = _read_regular_output_file(
                        output_directory,
                        Path(relative),
                        max_bytes=spec.max_item_bytes,
                    )
                except TaskInputError:
                    continue
                if (
                    total_by_collection[collection] + len(content)
                    > spec.max_total_bytes
                    or count_by_collection[collection] >= spec.max_items
                ):
                    continue
                total_by_collection[collection] += len(content)
                count_by_collection[collection] += 1
                values.append(
                    _WorkspaceSnapshotFile(
                        relative_path=relative,
                        media_type="application/octet-stream",
                        content=content,
                    )
                )
        if sum(len(item.content) for item in values) > (
            task.output.max_bundle_bytes
            + _ROLE_RESULT_ENVELOPE_OVERHEAD_BYTES
            + 1024 * 1024
        ):
            raise TaskInputError("provisional snapshot exceeds its aggregate byte limit")
        return tuple(values)

    def _deck_workspace_snapshot_files(
        self, session_id: str
    ) -> tuple[_WorkspaceSnapshotFile, ...]:
        deck = self.workspace_root / session_id / "deck"
        values: list[_WorkspaceSnapshotFile] = []
        for name, media_type, limit in (
            ("project.json", "application/json", 8 * 1024 * 1024),
            ("handoff.json", "application/json", 64 * 1024),
        ):
            values.append(
                _WorkspaceSnapshotFile(
                    relative_path=f"deck/{name}",
                    media_type=media_type,
                    content=_read_regular_deck_file(
                        deck, Path(name), max_bytes=limit
                    ),
                )
            )
        for relative_path, content in _read_deck_workspace_file_bytes(deck / "files"):
            values.append(
                _WorkspaceSnapshotFile(
                    relative_path=f"deck/files/{relative_path}",
                    media_type="text/plain",
                    content=content,
                )
            )
        return tuple(values)

    def _begin_file_validation(self, session: Any, task: AgentTask) -> None:
        self._require_current_output_contract(task)
        now = datetime.now(timezone.utc)
        absolute_deadline = _parse_timestamp(session.expires_at)
        lease_deadline = _timestamp(
            min(
                now + timedelta(seconds=_lease_seconds(task.budget.timeout_seconds)),
                absolute_deadline,
            )
        )
        recorded_at = _timestamp(now)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row(connection, task.task_id)
            if row["state"] != "claimed" or int(row["attempt"]) != session.attempt:
                raise TaskStateConflict("worker session is not the active claimed attempt")
            connection.execute(
                """
                UPDATE tasks
                SET deadline_at = ?, finalization_deadline_at = NULL,
                    finalization_manifest_ref_json = NULL,
                    finalization_commit_started_at = NULL,
                    last_activity_at = ?, last_activity = 'output_validation_started'
                WHERE task_id = ?
                """,
                (lease_deadline, recorded_at, task.task_id),
            )
            self._append_activity(
                connection,
                task.task_id,
                session.attempt,
                "output_validation_started",
                recorded_at,
            )
            connection.execute("COMMIT")

    def _reject_file_validation(
        self,
        session: Any,
        task: AgentTask,
        *,
        diagnostics: tuple[dict[str, str], ...],
    ) -> None:
        self._freeze_workspace_snapshot(
            session=session,
            task=task,
            reason="validation_rejected",
            validation_status="rejected",
            diagnostics=diagnostics,
        )
        now = datetime.now(timezone.utc)
        recorded_at = _timestamp(now)
        absolute_deadline = _parse_timestamp(session.expires_at)
        expired = now >= absolute_deadline
        next_deadline = None
        if not expired:
            next_deadline = _timestamp(
                min(
                    now + timedelta(seconds=_lease_seconds(task.budget.timeout_seconds)),
                    absolute_deadline,
                )
            )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row(connection, task.task_id)
            if row["state"] != "claimed" or int(row["attempt"]) != session.attempt:
                raise TaskStateConflict("task changed while output was validated")
            if expired:
                reason = "worker attempt expired during output validation"
                connection.execute(
                    """
                    UPDATE tasks
                    SET state = 'timed_out', reason = ?, deadline_at = ?,
                        finalization_deadline_at = NULL,
                        finalization_manifest_ref_json = NULL,
                        finalization_commit_started_at = NULL,
                        last_activity_at = ?, last_activity = 'output_rejected'
                    WHERE task_id = ?
                    """,
                    (reason, recorded_at, recorded_at, task.task_id),
                )
                assignment_state = "timed_out"
                completed_at = recorded_at
                self._append_event(
                    connection,
                    task.task_id,
                    "timed_out",
                    attempt=session.attempt,
                    reason=reason,
                )
            else:
                connection.execute(
                    """
                    UPDATE tasks
                    SET state = 'claimed', deadline_at = ?,
                        finalization_deadline_at = NULL,
                        finalization_manifest_ref_json = NULL,
                        finalization_commit_started_at = NULL,
                        last_activity_at = ?, last_activity = 'output_rejected'
                    WHERE task_id = ?
                    """,
                    (next_deadline, recorded_at, task.task_id),
                )
                assignment_state = "bound"
                completed_at = None
            connection.execute(
                """
                UPDATE assignment_instances
                SET state = ?, completed_at = ?
                WHERE task_id = ? AND attempt = ? AND state = 'bound'
                """,
                (assignment_state, completed_at, task.task_id, session.attempt),
            )
            self._append_activity(
                connection,
                task.task_id,
                session.attempt,
                "output_rejected",
                recorded_at,
            )
            connection.execute("COMMIT")

    def _abort_file_validation(self, session: Any, task: AgentTask) -> None:
        now = datetime.now(timezone.utc)
        absolute_deadline = _parse_timestamp(session.expires_at)
        recorded_at = _timestamp(now)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row(connection, task.task_id)
            if row["state"] != "claimed" or int(row["attempt"]) != session.attempt:
                connection.execute("ROLLBACK")
                return
            if now >= absolute_deadline:
                reason = "worker attempt expired during output validation"
                connection.execute(
                    """
                    UPDATE tasks
                    SET state = 'timed_out', reason = ?, deadline_at = ?,
                        finalization_deadline_at = NULL,
                        finalization_manifest_ref_json = NULL,
                        finalization_commit_started_at = NULL
                    WHERE task_id = ?
                    """,
                    (reason, recorded_at, task.task_id),
                )
                connection.execute(
                    """
                    UPDATE assignment_instances
                    SET state = 'timed_out', completed_at = ?
                    WHERE task_id = ? AND attempt = ? AND state = 'bound'
                    """,
                    (recorded_at, task.task_id, session.attempt),
                )
                self._append_event(
                    connection,
                    task.task_id,
                    "timed_out",
                    attempt=session.attempt,
                    reason=reason,
                )
            else:
                lease_deadline = _timestamp(
                    min(
                        now
                        + timedelta(seconds=_lease_seconds(task.budget.timeout_seconds)),
                        absolute_deadline,
                    )
                )
                connection.execute(
                    """
                    UPDATE tasks
                    SET state = 'claimed', deadline_at = ?,
                        finalization_deadline_at = NULL,
                        finalization_manifest_ref_json = NULL,
                        finalization_commit_started_at = NULL,
                        last_activity_at = ?,
                        last_activity = 'output_validation_aborted'
                    WHERE task_id = ?
                    """,
                    (lease_deadline, recorded_at, task.task_id),
                )
                self._append_activity(
                    connection,
                    task.task_id,
                    session.attempt,
                    "output_validation_aborted",
                    recorded_at,
                )
            connection.execute("COMMIT")

    def _seal_file_validation(
        self, session: Any, manifest: ProvisionalSnapshotManifest
    ) -> None:
        with self._connect() as connection:
            mapping = connection.execute(
                """
                SELECT manifest_ref_json FROM task_provisional_snapshots
                WHERE task_id = ? AND attempt = ? AND sequence = ?
                """,
                (session.task_id, session.attempt, manifest.sequence),
            ).fetchone()
            if mapping is None:
                raise TaskServiceError("validated provisional snapshot is not registered")
            manifest_ref = _parse_ref(mapping["manifest_ref_json"])
            connection.execute("BEGIN IMMEDIATE")
            row = self._row(connection, session.task_id)
            if row["state"] != "claimed" or int(row["attempt"]) != session.attempt:
                raise TaskStateConflict("task changed while output was sealed")
            now = datetime.now(timezone.utc)
            if now >= _parse_timestamp(session.expires_at):
                raise TaskStateConflict("worker attempt expired before output was sealed")
            recorded_at = _timestamp(now)
            grace_deadline = _timestamp(
                now + timedelta(seconds=_FINALIZATION_GRACE_SECONDS)
            )
            connection.execute(
                """
                UPDATE tasks
                SET state = 'finalizing', deadline_at = ?,
                    finalization_deadline_at = ?,
                    finalization_manifest_ref_json = ?,
                    last_activity_at = ?, last_activity = 'output_validated'
                WHERE task_id = ?
                """,
                (
                    grace_deadline,
                    grace_deadline,
                    manifest_ref.canonical_json(),
                    recorded_at,
                    session.task_id,
                ),
            )
            connection.execute(
                """
                UPDATE assignment_instances SET state = 'finalizing'
                WHERE task_id = ? AND attempt = ? AND state = 'bound'
                """,
                (session.task_id, session.attempt),
            )
            self._append_activity(
                connection,
                session.task_id,
                session.attempt,
                "output_validated",
                recorded_at,
            )
            connection.execute("COMMIT")

    def _begin_sealed_finalization(
        self, session: Any
    ) -> ProvisionalSnapshotManifest:
        self._reconcile_expired(session.task_id)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row(connection, session.task_id)
            if row["state"] not in {"finalizing", "completed"}:
                raise TaskStateConflict("task has no sealed output to finalize")
            if int(row["attempt"]) != session.attempt:
                raise TaskStateConflict("sealed output belongs to another attempt")
            raw_reference = row["finalization_manifest_ref_json"]
            if raw_reference is None:
                raise TaskStateConflict("task output validation has not sealed bytes")
            if row["state"] == "finalizing":
                now = datetime.now(timezone.utc)
                commit_started = row["finalization_commit_started_at"]
                deadline = (
                    row["finalization_deadline_at"]
                    if commit_started is None
                    else row["deadline_at"]
                )
                if deadline is None or now >= _parse_timestamp(deadline):
                    raise TaskStateConflict("output finalization grace has expired")
                if commit_started is None:
                    hard_deadline = _timestamp(
                        now + timedelta(seconds=_FINALIZATION_COMMIT_SECONDS)
                    )
                    recorded_at = _timestamp(now)
                    connection.execute(
                        """
                        UPDATE tasks
                        SET finalization_commit_started_at = ?, deadline_at = ?,
                            last_activity_at = ?, last_activity = 'finalization_started'
                        WHERE task_id = ?
                        """,
                        (
                            recorded_at,
                            hard_deadline,
                            recorded_at,
                            session.task_id,
                        ),
                    )
                    self._append_activity(
                        connection,
                        session.task_id,
                        session.attempt,
                        "finalization_started",
                        recorded_at,
                    )
            connection.execute("COMMIT")
        reference = _parse_ref(raw_reference)
        try:
            manifest = ProvisionalSnapshotManifest.model_validate_json(
                self.artifacts.read(reference), strict=True
            )
        except ValidationError as error:
            raise TaskServiceError("sealed output manifest is invalid") from error
        if (
            manifest.attempt != session.attempt
            or manifest.reason != "finalization_candidate"
            or manifest.validation_status != "valid"
        ):
            raise TaskServiceError("sealed output manifest is not finalizable")
        return manifest

    def _sealed_output(
        self, manifest: ProvisionalSnapshotManifest, task: AgentTask
    ) -> tuple[Any, tuple[_ValidatedOutputArtifact, ...]]:
        by_path = {item.relative_path: item for item in manifest.files}
        primary = by_path.get("result.json")
        if primary is None:
            raise TaskServiceError("sealed output has no primary result")
        primary_raw = self.artifacts.read(primary.artifact_ref)
        try:
            text = primary_raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise TaskServiceError("sealed primary result is not UTF-8") from error
        if task.output.format == "text":
            content: Any = text
        else:
            try:
                content = json.loads(text)
            except json.JSONDecodeError as error:
                raise TaskServiceError("sealed primary result is not JSON") from error
        self._validate_complete_output(task, attempt=manifest.attempt, content=content)
        specs = {item.name: item for item in task.output.collections}
        artifacts: list[_ValidatedOutputArtifact] = []
        for item in manifest.files:
            if item.collection is None or item.item is None:
                continue
            if item.control_generated and item.collection == "validation_reports":
                spec = _FIGURE_VALIDATION_REPORT_SPEC
            else:
                try:
                    spec = specs[item.collection]
                except KeyError as error:
                    raise TaskServiceError(
                        "sealed output declares an unknown collection"
                    ) from error
            descriptor = TaskOutputBundleItem(
                collection=item.collection,
                item=item.item,
                media_type=item.media_type,
                relative_path=f"collections/{item.collection}/{item.item}",
            )
            raw = self.artifacts.read(item.artifact_ref)
            if len(raw) != item.size_bytes:
                raise TaskServiceError("sealed output file size is inconsistent")
            artifacts.append(
                _ValidatedOutputArtifact(
                    descriptor=descriptor,
                    spec=spec,
                    content=raw,
                    control_generated=item.control_generated,
                )
            )
        return content, tuple(
            sorted(
                artifacts,
                key=lambda value: (
                    value.descriptor.collection,
                    value.descriptor.item,
                ),
            )
        )

    def analysis_directory(
        self, session_token: str, *, worker_id: str
    ) -> Path:
        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        directory = self.workspace_root / session.session_id
        directory.mkdir(mode=0o750, exist_ok=True)
        return directory

    def analysis_output_directory(
        self, session_token: str, *, worker_id: str
    ) -> Path | None:
        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        task = self.get_task(session.task_id)
        if not task.output.collections:
            return None
        directory = self.workspace_root / session.session_id / "output"
        directory.mkdir(parents=True, mode=0o700, exist_ok=True)
        (directory / "collections").mkdir(mode=0o700, exist_ok=True)
        return directory

    def validate_analysis_outputs(
        self, session_token: str, *, worker_id: str
    ) -> None:
        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        task = self.get_task(session.task_id)
        if not task.output.collections:
            return
        output_directory = self.workspace_root / session.session_id / "output"
        paths = _collection_output_paths(output_directory)
        specs = {item.name: item for item in task.output.collections}
        counts = {name: 0 for name in specs}
        sizes = {name: 0 for name in specs}
        aggregate = 0
        for value in paths:
            parts = Path(value).parts
            if len(parts) != 3 or parts[0] != "collections":
                raise TaskInputError("analysis output paths must be collection items")
            collection, item = parts[1:]
            if collection not in specs or not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9_.-]*", item
            ):
                raise TaskInputError("analysis wrote an undeclared collection path")
            size = os.lstat(output_directory / value).st_size
            spec = specs[collection]
            if size > spec.max_item_bytes:
                raise TaskInputError("analysis collection item exceeds its byte limit")
            counts[collection] += 1
            sizes[collection] += size
            aggregate += size
        for name, spec in specs.items():
            if counts[name] > spec.max_items:
                raise TaskInputError(
                    f"analysis collection {name} item count exceeds its upper bound"
                )
            if sizes[name] > spec.max_total_bytes:
                raise TaskInputError(
                    f"analysis collection {name} exceeds its total byte limit"
                )
        if aggregate > sum(item.max_total_bytes for item in task.output.collections):
            raise TaskInputError("analysis outputs exceed the aggregate byte limit")

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
        text: str,
        text_truncated: bool,
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
            rows = connection.execute(
                "SELECT source_key FROM task_web_evidence "
                "WHERE task_id = ? AND attempt = ?",
                (session.task_id, session.attempt),
            ).fetchall()
        reserved_source_keys = {item.name for item in task.inputs}
        reserved_source_keys.update(str(row[0]) for row in rows)
        source_index = 1
        while f"web_{source_index}" in reserved_source_keys:
            source_index += 1
        source_key = f"web_{source_index}"
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
        text_ref = self.artifacts.register(
            text.encode("utf-8"),
            ArtifactRegistration(
                kind="web_extracted_text",
                schema_id="opaque",
                payload_schema_version=1,
                media_type="text/plain; charset=utf-8",
                creator=self.service_actor,
                parent_refs=(response_ref,),
                task_ref=task_ref,
                labels={"source_key": source_key},
                confidentiality="task_private",
            ),
            idempotency_key=(
                f"task:{session.task_id}:web:{session.attempt}:{source_key}:text"
            ),
        ).ref
        snapshot = WebEvidenceSnapshot(
            original_url=original_url,
            final_url=final_url,
            accessed_at=accessed_at,
            http_status=http_status,
            media_type=media_type,
            response_ref=response_ref,
            extracted_text_ref=text_ref,
            text_truncated=text_truncated,
        )
        snapshot_ref = self.artifacts.register(
            snapshot.canonical_json(),
            ArtifactRegistration(
                kind="web_evidence_snapshot",
                schema_id="scidiscovery.web-evidence-snapshot",
                payload_schema_version=1,
                media_type="application/json",
                creator=self.service_actor,
                parent_refs=(response_ref, text_ref),
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
            extracted_text_ref=text_ref,
            text_truncated=text_truncated,
        )

    def materialize_web_evidence(
        self,
        session_token: str,
        *,
        worker_id: str,
        original_url: str,
        source_key: str,
    ) -> WebEvidenceMaterializationView:
        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        bound = self.web_evidence_for_url(
            session_token,
            worker_id=worker_id,
            original_url=original_url,
        )
        if bound is None or bound[0].source_key != source_key:
            raise TaskInputError("web evidence source is not bound to this task")
        view, raw = bound
        if len(raw) > 8 * 1024 * 1024:
            raise TaskInputError("web evidence response exceeds its byte limit")
        suffix = _MEDIA_SUFFIXES.get(
            view.media_type.split(";", 1)[0].strip().lower(), ".bin"
        )
        workspace = self._materialized_worker_workspace(session.session_id)
        destination = workspace / "web" / f"{source_key}{suffix}"
        _write_immutable_file(destination, raw)
        text_path = None
        text_size = None
        if view.extracted_text_ref is not None:
            extracted = self.artifacts.read(view.extracted_text_ref)
            if len(extracted) > 262144:
                raise TaskInputError("web evidence extracted text exceeds its byte limit")
            text_destination = workspace / "web" / f"{source_key}.txt"
            _write_immutable_file(text_destination, extracted)
            text_path = str(text_destination)
            text_size = len(extracted)
        return WebEvidenceMaterializationView(
            local_path=str(destination),
            size_bytes=len(raw),
            text_local_path=text_path,
            text_size_bytes=text_size,
            text_truncated=view.text_truncated,
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

    def list_pdf_excerpts(self, task_id: str) -> tuple[TaskPdfExcerptView, ...]:
        self.get_task(task_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM task_pdf_excerpts
                WHERE task_id = ?
                ORDER BY attempt, source_name, first_page, last_page, max_chars
                """,
                (task_id,),
            ).fetchall()
        values = []
        for row in rows:
            reference = _parse_ref(row["excerpt_ref_json"])
            envelope = self.artifacts.verify(reference)
            try:
                excerpt = PdfExcerptSet.model_validate_json(
                    self.artifacts.read(reference), strict=True
                )
            except ValidationError as error:
                raise TaskServiceError("stored PDF excerpt is invalid") from error
            if (
                envelope.schema_id != "scidiscovery.pdf-excerpt-set.v1"
                or excerpt.first_page != int(row["first_page"])
                or excerpt.last_page != int(row["last_page"])
                or excerpt.truncated != bool(row["truncated"])
            ):
                raise TaskServiceError("stored PDF excerpt mapping is invalid")
            values.append(
                TaskPdfExcerptView(
                    source_name=row["source_name"],
                    excerpt_ref=reference,
                    first_page=excerpt.first_page,
                    last_page=excerpt.last_page,
                    max_chars=int(row["max_chars"]),
                    truncated=excerpt.truncated,
                )
            )
        return tuple(values)

    def list_output_artifacts(
        self, task_id: str
    ) -> tuple[TaskOutputArtifactView, ...]:
        self.get_task(task_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM task_output_artifacts
                WHERE task_id = ?
                ORDER BY collection_name, item_name
                """,
                (task_id,),
            ).fetchall()
        values = []
        for row in rows:
            reference = _parse_ref(row["artifact_ref_json"])
            envelope = self.artifacts.verify(reference)
            if (
                envelope.media_type != row["media_type"]
                or envelope.size_bytes != int(row["size_bytes"])
            ):
                raise TaskServiceError("stored task output artifact mapping is invalid")
            values.append(
                TaskOutputArtifactView(
                    collection=row["collection_name"],
                    item=row["item_name"],
                    artifact_ref=reference,
                    media_type=row["media_type"],
                    size_bytes=int(row["size_bytes"]),
                )
            )
        return tuple(values)

    def finalize(
        self,
        session_token: str,
        *,
        worker_id: str,
        content: Any,
        _validated_artifacts: tuple[_ValidatedOutputArtifact, ...] | None = None,
    ) -> None:
        session = self.tokens.verify_session(session_token, worker_id=worker_id)
        self._require_active_claim(session.task_id, session.attempt)
        task = self.get_task(session.task_id)
        if task.output.collections and _validated_artifacts is None:
            raise TaskInputError(
                "collection-enabled output must be finalized from output/bundle.json",
                details=(
                    {
                        "path": "$.bundle",
                        "message": "collection-enabled output requires output/bundle.json",
                        "type": "value_error.missing",
                    },
                ),
            )
        self._finalize_validated_output(
            session=session,
            task=task,
            worker_id=worker_id,
            content=content,
            validated_artifacts=_validated_artifacts or (),
            required_state="claimed",
        )

    def _finalize_validated_output(
        self,
        *,
        session: Any,
        task: AgentTask,
        worker_id: str,
        content: Any,
        validated_artifacts: tuple[_ValidatedOutputArtifact, ...],
        required_state: str = "finalizing",
    ) -> None:
        self._require_current_output_contract(task)
        raw, web_refs, signal = self._validate_complete_output(
            task, attempt=session.attempt, content=content
        )
        signal = _figure_evidence_scheduler_signal(signal, validated_artifacts)
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
        output_artifacts: list[tuple[_ValidatedOutputArtifact, ArtifactRef]] = []
        for value in sorted(
            validated_artifacts,
            key=lambda item: (item.descriptor.collection, item.descriptor.item),
        ):
            creator = (
                self.service_actor
                if value.control_generated
                else ActorRef(actor_id=worker_id, actor_type="agent_worker")
            )
            child_parents = (output_ref,)
            if value.control_generated:
                child_parents += tuple(reference for _, reference in output_artifacts)
            artifact_ref = self.artifacts.register(
                value.content,
                ArtifactRegistration(
                    kind=value.spec.kind,
                    schema_id=value.spec.schema_id,
                    payload_schema_version=1,
                    media_type=value.descriptor.media_type,
                    creator=creator,
                    parent_refs=child_parents,
                    task_ref=task_ref,
                    labels={
                        "role": task.role,
                        "attempt": str(session.attempt),
                        "collection": value.descriptor.collection,
                        "item": value.descriptor.item,
                    },
                    confidentiality="task_private",
                ),
                idempotency_key=(
                    f"task:{task.task_id}:output:{session.attempt}:"
                    f"{value.descriptor.collection}:{value.descriptor.item}"
                ),
            ).ref
            output_artifacts.append((value, artifact_ref))
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
            if row["state"] != required_state or int(row["attempt"]) != session.attempt:
                raise TaskStateConflict("task is not finalizable from current state")
            if required_state == "finalizing":
                deadline = (
                    row["deadline_at"]
                    if row["finalization_commit_started_at"] is not None
                    else row["finalization_deadline_at"]
                )
                if deadline is None or datetime.now(timezone.utc) >= _parse_timestamp(deadline):
                    raise TaskStateConflict("output finalization grace has expired")
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
                WHERE task_id = ? AND attempt = ? AND state = ?
                """,
                (finalized_at, task.task_id, session.attempt, required_state),
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
            for value, artifact_ref in output_artifacts:
                connection.execute(
                    """
                    INSERT INTO task_output_artifacts (
                        task_id, attempt, collection_name, item_name,
                        artifact_ref_json, media_type, size_bytes, relative_path
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task.task_id,
                        session.attempt,
                        value.descriptor.collection,
                        value.descriptor.item,
                        artifact_ref.canonical_json(),
                        value.descriptor.media_type,
                        len(value.content),
                        value.descriptor.relative_path,
                    ),
                )
            connection.execute("COMMIT")
        remove_private_directory(self.workspace_root, session.session_id)

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
        output_variant = self.output_contract(task.role).contract_for_output(task.output)
        if output_variant.context_validator is not None:
            try:
                _validate_contextual_role_output(
                    output_variant.context_validator,
                    payload,
                    {
                        item.name: self.artifacts.read(item.artifact_ref)
                        for item in task.inputs
                        if item.name in set(output_variant.context_sources)
                    },
                    result.handoff.model_dump(mode="json"),
                )
            except TaskInputError as error:
                raise TaskInputError(
                    str(error),
                    details=_prefix_validation_paths(error.details, "$.payload"),
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

    def resolve_output_collections(
        self, role: str, profile: str | None
    ) -> tuple[TaskOutputCollectionSpec, ...]:
        return self.output_contract(role).collections_for_profile(profile)

    def resolve_output_profile(
        self, role: str, profile: str | None
    ) -> tuple[RoleOutputVariant, tuple[TaskOutputCollectionSpec, ...]]:
        return self.output_contract(role).resolve_profile(profile)

    def _require_current_output_contract(self, task: AgentTask) -> None:
        contract = self.output_contract(task.role)
        if not contract.admits_output(task.output):
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
            if (
                row["state"] == "finalizing"
                and row["finalization_commit_started_at"] is not None
            ):
                raise TaskStateConflict(
                    "sealed finalization is in progress; wait for completion or its hard cutoff"
                )
            if (
                row["state"] == "claimed"
                and row["last_activity"] == "output_validation_started"
            ):
                raise TaskStateConflict(
                    "output validation is in progress; wait for completion or lease expiry"
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
                  AND state IN ('queued', 'bound', 'finalizing')
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
                    finalization_deadline_at = NULL,
                    finalization_manifest_ref_json = NULL,
                    finalization_commit_started_at = NULL,
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
            finalization_deadline_at=row["finalization_deadline_at"],
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

    def admits_nonqualifying_input(
        self,
        *,
        role: str,
        context_profile: str | None,
        source_name: str,
        exposure: str,
        usage: str | None,
    ) -> bool:
        """Pure policy query for an explicitly non-claim task input."""

        _, policy = self._context_policy(role, context_profile)
        if exposure == "handoff_only":
            return True
        if usage is None or usage == "claim_evidence":
            return False
        rule = next(
            (item for item in policy.rules if item.source_name == source_name),
            None,
        )
        if rule is not None:
            return rule.usage is not None and rule.usage == usage
        return (
            policy.allow_additional
            and policy.additional_usages is not None
            and usage in policy.additional_usages
        )

    def _context_policy(self, role: str, requested: str | None) -> tuple[str, Any]:
        self.output_contract(role)
        try:
            return self.role_context_policies[role].resolve(requested)
        except ValueError as error:
            raise TaskInputError(str(error)) from error

    def _validate_context(
        self,
        inputs: tuple[TaskInput, ...],
        policy: Any,
        *,
        role: str,
        context_profile: str,
    ) -> None:
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
            if (
                item.usage == "claim_evidence"
                and envelope.labels.get("scientific_claim_admissible") == "false"
            ):
                raise TaskInputError(
                    f"task source {name} is provisional and cannot support a scientific claim"
                )
            rule = rules.get(name)
            if (
                rule is None
                and policy.additional_usages is not None
                and item.usage not in policy.additional_usages
            ):
                raise TaskInputError(
                    f"task source {name} has an unsupported additional usage"
                )
            if rule is not None:
                if item.exposure != rule.exposure:
                    raise TaskInputError(
                        f"task source {name} must use {rule.exposure} exposure"
                    )
                if rule.usage is not None and item.usage != rule.usage:
                    raise TaskInputError(
                        f"task source {name} must use {rule.usage} usage"
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
                if self.scheduler_signal_for_output(item.artifact_ref) is None:
                    raise TaskInputError(
                        f"task source {name} has no completed scheduler handoff"
                    )
            else:
                readable_bytes += envelope.size_bytes
        receipts = tuple(
            item for item in inputs if item.usage == "unchanged_set_receipt"
        )
        if len(receipts) > 1:
            raise TaskInputError("task context admits at most one unchanged-set receipt")
        if receipts:
            receipt_input = receipts[0]
            receipt_envelope = self.artifacts.verify(receipt_input.artifact_ref)
            if receipt_envelope.schema_id != (
                "scidiscovery.unchanged-evidence-receipt.v1"
            ):
                raise TaskInputError("unchanged-set receipt has an unsupported schema")
            try:
                receipt = UnchangedEvidenceReceipt.model_validate_json(
                    self.artifacts.read(receipt_input.artifact_ref), strict=True
                )
            except ValidationError as error:
                raise TaskInputError("unchanged-set receipt is invalid") from error
            revised_input = by_name.get("revised_object")
            diff_input = by_name.get("revision_diff")
            if (
                revised_input is None
                or diff_input is None
                or len(receipt_envelope.parent_refs)
                != len(receipt.evidence_source_labels) + 3
                or receipt_envelope.parent_refs[1] != revised_input.artifact_ref
                or receipt_envelope.parent_refs[2] != diff_input.artifact_ref
            ):
                raise TaskInputError(
                    "unchanged-set receipt does not bind the exact revision context"
                )
            evidence_parent_refs = set(receipt_envelope.parent_refs[3:])
            cached_excerpt_refs = {
                item.artifact_ref for item in inputs if item.usage == "cached_excerpt"
            }
            if not cached_excerpt_refs.issubset(evidence_parent_refs):
                raise TaskInputError(
                    "unchanged-set receipt does not bind the supplied cached excerpts"
                )
            if self.artifacts.catalog(
                revised_input.artifact_ref
            ).schema_id != receipt.target_schema:
                raise TaskInputError(
                    "unchanged-set receipt targets a different revised object"
                )
        if (
            role == "tcad_deck_author"
            and context_profile
            == "tcad.deck-author.runtime-failure-revision.v1"
        ):
            self._validate_tcad_runtime_failure_revision_context(by_name)
        if readable_bytes > policy.max_readable_bytes:
            raise TaskInputError("task context exceeds the readable-byte limit")

    def _validate_tcad_runtime_failure_revision_context(
        self, by_name: dict[str, TaskInput]
    ) -> None:
        """Bind a failed runtime diagnosis to its exact project and solver log."""

        packager = import_module("tcad_artifact.project_packager")
        prior_input = by_name["prior_project"]
        attestation_input = by_name["runtime_attestation"]
        solver_log_input = by_name["solver_log"]
        attestation_envelope = self.artifacts.verify(
            attestation_input.artifact_ref
        )
        try:
            attestation = packager.RuntimeAttestation.model_validate_json(
                self.artifacts.read(attestation_input.artifact_ref), strict=True
            )
        except ValidationError as error:
            raise TaskInputError("runtime-failure attestation is invalid") from error
        if attestation.verdict != "fail":
            raise TaskInputError(
                "runtime-failure revision requires a failing runtime attestation"
            )
        if solver_log_input.artifact_ref not in attestation_envelope.parent_refs:
            raise TaskInputError(
                "runtime-failure attestation was not produced from the exact solver log"
            )
        package_refs = tuple(
            ref
            for ref in attestation_envelope.parent_refs
            if self.artifacts.verify(ref).schema_id
            == "tcad.reviewed-deck-package.v2"
        )
        if len(package_refs) != 1:
            raise TaskInputError(
                "runtime-failure attestation must bind one exact reviewed package"
            )
        try:
            package = packager.ReviewedDeckPackage.model_validate_json(
                self.artifacts.read(package_refs[0]), strict=True
            )
        except ValidationError as error:
            raise TaskInputError("runtime-failure reviewed package is invalid") from error
        try:
            prior = packager.DeckProjectDraft.model_validate_json(
                self.artifacts.read(prior_input.artifact_ref), strict=True
            )
        except ValidationError as error:
            raise TaskInputError("runtime-failure prior project is invalid") from error
        exact_source_fields = (
            "files",
            "input_slots",
            "entrypoint",
            "arguments",
            "tool_profile",
            "solver_kind",
            "capability_sha256",
        )
        if any(
            getattr(package.project, name) != getattr(prior, name)
            for name in exact_source_fields
        ):
            raise TaskInputError(
                "runtime-failure reviewed package contains a different prior source tree"
            )

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
        if state in {"dispatched", "claimed", "finalizing"}:
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
                    SELECT task_id, attempt, state FROM tasks
                    WHERE state IN ('dispatched', 'claimed', 'finalizing')
                      AND deadline_at IS NOT NULL AND deadline_at <= ?
                    """,
                    (now,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT task_id, attempt, state FROM tasks
                    WHERE task_id = ? AND state IN ('dispatched', 'claimed', 'finalizing')
                      AND deadline_at IS NOT NULL AND deadline_at <= ?
                    """,
                    (task_id, now),
                ).fetchall()
            for row in rows:
                reason = (
                    "worker finalization grace expired"
                    if row["state"] == "finalizing"
                    else "worker attempt exceeded its dispatch deadline"
                )
                connection.execute(
                    "UPDATE tasks SET state = 'timed_out', reason = ? WHERE task_id = ?",
                    (reason, row["task_id"]),
                )
                connection.execute(
                    """
                    UPDATE assignment_instances
                    SET state = 'timed_out', completed_at = ?
                    WHERE task_id = ? AND attempt = ?
                      AND state IN ('queued', 'bound', 'finalizing')
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
                extracted_text_ref=snapshot.extracted_text_ref,
                text_truncated=snapshot.text_truncated,
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

    def scheduler_signal_for_output(
        self, artifact_ref: ArtifactRef
    ) -> SchedulerSignal | None:
        """Return the signal bound to one exact completed output artifact."""

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT tasks.scheduler_signal_ref_json
                FROM tasks
                LEFT JOIN task_output_artifacts
                  ON task_output_artifacts.task_id = tasks.task_id
                 AND task_output_artifacts.attempt = tasks.attempt
                WHERE tasks.state = 'completed'
                  AND (
                    tasks.output_ref_json = ?
                    OR task_output_artifacts.artifact_ref_json = ?
                  )
                ORDER BY tasks.created_at DESC
                LIMIT 1
                """,
                (artifact_ref.canonical_json(), artifact_ref.canonical_json()),
            ).fetchone()
        if row is None:
            return None
        signal_ref = _parse_optional_ref(row["scheduler_signal_ref_json"])
        if signal_ref is None:
            raise TaskServiceError("completed task output has no scheduler signal")
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
                    finalization_deadline_at TEXT,
                    finalization_manifest_ref_json BLOB,
                    finalization_commit_started_at TEXT,
                    provisional_sequence INTEGER NOT NULL DEFAULT 0,
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
                CREATE TABLE IF NOT EXISTS pdf_text_cache (
                    cache_key TEXT PRIMARY KEY,
                    source_ref_json BLOB NOT NULL,
                    extractor_profile TEXT NOT NULL,
                    text_ref_json BLOB NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS task_pdf_excerpts (
                    task_id TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    source_name TEXT NOT NULL,
                    first_page INTEGER NOT NULL,
                    last_page INTEGER NOT NULL,
                    max_chars INTEGER NOT NULL,
                    excerpt_ref_json BLOB NOT NULL,
                    truncated INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(
                        task_id, attempt, source_name,
                        first_page, last_page, max_chars
                    ),
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id)
                );
                CREATE TABLE IF NOT EXISTS task_output_artifacts (
                    task_id TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    collection_name TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    artifact_ref_json BLOB NOT NULL UNIQUE,
                    media_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    relative_path TEXT NOT NULL,
                    PRIMARY KEY(task_id, attempt, collection_name, item_name),
                    UNIQUE(task_id, attempt, relative_path),
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id)
                );
                CREATE TABLE IF NOT EXISTS task_provisional_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    sequence INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    manifest_ref_json BLOB NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    UNIQUE(task_id, attempt, sequence),
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id)
                );
                CREATE INDEX IF NOT EXISTS task_provisional_snapshots_lookup
                ON task_provisional_snapshots(task_id, attempt, sequence);
                CREATE TABLE IF NOT EXISTS tcad_debug_leases (
                    session_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    max_runs INTEGER NOT NULL,
                    max_total_wall_seconds INTEGER NOT NULL,
                    UNIQUE(task_id, attempt),
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id)
                );
                CREATE TABLE IF NOT EXISTS tcad_debug_runs (
                    session_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    run_name TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    snapshot_ref_json BLOB NOT NULL,
                    source_tree_sha256 TEXT,
                    submission_json BLOB NOT NULL,
                    external_run_id TEXT,
                    state TEXT NOT NULL,
                    wall_time_seconds INTEGER NOT NULL,
                    response_json BLOB,
                    result_snapshot_ref_json BLOB,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(session_id, run_name),
                    FOREIGN KEY(session_id) REFERENCES tcad_debug_leases(session_id),
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id)
                );
                CREATE INDEX IF NOT EXISTS tcad_debug_runs_task
                ON tcad_debug_runs(task_id, attempt, created_at);
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
            if "finalization_deadline_at" not in columns:
                connection.execute(
                    "ALTER TABLE tasks ADD COLUMN finalization_deadline_at TEXT"
                )
            if "finalization_manifest_ref_json" not in columns:
                connection.execute(
                    "ALTER TABLE tasks ADD COLUMN finalization_manifest_ref_json BLOB"
                )
            if "finalization_commit_started_at" not in columns:
                connection.execute(
                    "ALTER TABLE tasks ADD COLUMN finalization_commit_started_at TEXT"
                )
            if "provisional_sequence" not in columns:
                connection.execute(
                    """
                    ALTER TABLE tasks
                    ADD COLUMN provisional_sequence INTEGER NOT NULL DEFAULT 0
                    """
                )
            debug_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(tcad_debug_runs)"
                ).fetchall()
            }
            if "mode" not in debug_columns:
                connection.execute(
                    """
                    ALTER TABLE tcad_debug_runs
                    ADD COLUMN mode TEXT NOT NULL DEFAULT 'legacy_full'
                    """
                )
            if "source_tree_sha256" not in debug_columns:
                connection.execute(
                    "ALTER TABLE tcad_debug_runs ADD COLUMN source_tree_sha256 TEXT"
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


def _pdf_text_pages(text: str) -> tuple[str, ...]:
    pages = text.split("\f")
    if pages and pages[-1] == "":
        pages.pop()
    if not pages or all(not page for page in pages):
        raise TaskInputError("PDF text extraction produced no text")
    if len(pages) > 100000:
        raise TaskInputError("PDF text extraction exceeds the page-count limit")
    return tuple(pages)


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


def _bounded_provisional_diagnostics(
    values: tuple[dict[str, str], ...],
) -> tuple[tuple[ProvisionalDiagnostic, ...], bool]:
    diagnostics: list[ProvisionalDiagnostic] = []
    truncated = len(values) > 64
    used = 0
    for value in values[:64]:
        diagnostic = ProvisionalDiagnostic(
            path=str(value.get("path", "$"))[:1024] or "$",
            message=str(value.get("message", "validation rejected"))[:2048]
            or "validation rejected",
            type=str(value.get("type", "value_error"))[:256] or "value_error",
        )
        size = len(diagnostic.canonical_json())
        if used + size > _PROVISIONAL_DIAGNOSTIC_BYTES:
            truncated = True
            break
        diagnostics.append(diagnostic)
        used += size
    return tuple(diagnostics), truncated


WORKER_CAPABILITIES = (
    "assignment.materialize",
    "input.native_filesystem_read",
    "input.extract_pdf_text",
    "analysis.python",
    "evidence.web_snapshot",
    "file.chunked_write",
    "file.unified_patch",
    "file.move_delete",
    "output.checkpoint",
    "output.sealed_finalize",
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


def _validated_provisional_relative_path(value: str) -> Path:
    path = Path(value)
    if (
        len(value) > 2048
        or path.is_absolute()
        or not path.parts
        or len(path.parts) > 16
        or "\\" in value
        or any(
            part in {"", ".", ".."}
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,255}", part) is None
            for part in path.parts
        )
    ):
        raise TaskInputError("provisional snapshot path is unsafe")
    return path


def _validated_worker_file_path(value: str) -> Path:
    path = _validated_provisional_relative_path(value)
    if len(value) > 1024:
        raise TaskInputError("worker file path exceeds its length limit")
    return path


def _read_worker_upload_metadata(workspace: Path) -> dict[str, Any]:
    path = workspace / _WORKER_FILE_UPLOAD_METADATA
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise TaskInputError("worker file write has not been started") from error
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode) or details.st_size > 4096:
            raise TaskInputError("worker file upload metadata is invalid")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            raw = stream.read(4097)
    finally:
        os.close(descriptor)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TaskInputError("worker file upload metadata is invalid") from error
    if (
        not isinstance(value, dict)
        or set(value) != {"relative_path", "expected_bytes", "operation"}
        or not isinstance(value["relative_path"], str)
        or not (
            value["expected_bytes"] is None
            or (
                isinstance(value["expected_bytes"], int)
                and not isinstance(value["expected_bytes"], bool)
                and value["expected_bytes"] >= 0
            )
        )
        or value["operation"] not in {"create", "patch"}
    ):
        raise TaskInputError("worker file upload metadata is invalid")
    _validated_worker_file_path(value["relative_path"])
    return value


def _prepare_worker_file_parent(workspace: Path, parent: Path) -> None:
    try:
        relative = parent.relative_to(workspace)
    except ValueError as error:
        raise TaskInputError("worker file path escapes its workspace") from error
    current = workspace
    for part in relative.parts:
        current = current / part
        if current.exists() or current.is_symlink():
            details = os.lstat(current)
            if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode):
                raise TaskInputError("worker file parent must be a real directory")
        else:
            current.mkdir(mode=0o700)


def _replace_worker_file(source: Path, destination: Path) -> None:
    if destination.exists() or destination.is_symlink():
        details = os.lstat(destination)
        if stat.S_ISLNK(details.st_mode) or not stat.S_ISREG(details.st_mode):
            raise TaskInputError("worker file destination must be a regular file")
    os.chmod(source, 0o600)
    os.replace(source, destination)


def _atomic_worker_file_write(workspace: Path, destination: Path, content: bytes) -> None:
    _prepare_worker_file_parent(workspace, destination.parent)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.worker.", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        _replace_worker_file(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _read_regular_worker_file(
    workspace: Path, path: Path, *, max_bytes: int
) -> bytes:
    try:
        relative = path.relative_to(workspace)
    except ValueError as error:
        raise TaskInputError("worker file path escapes its workspace") from error
    _prepare_worker_file_parent(workspace, path.parent)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(workspace / relative, flags)
    except OSError as error:
        raise TaskInputError("worker file does not exist") from error
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode):
            raise TaskInputError("worker file must be a regular file")
        if details.st_size > max_bytes:
            raise TaskInputError("worker file exceeds its byte limit")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            content = stream.read(max_bytes + 1)
    finally:
        os.close(descriptor)
    if len(content) > max_bytes:
        raise TaskInputError("worker file exceeds its byte limit")
    return content


_UNIFIED_HUNK = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?:.*)(?:\n)?$"
)
_PATCH_DIAGNOSTIC_MAX_BYTES = 2048
_PATCH_LINE_PREVIEW_MAX_BYTES = 256
_PATCHABLE_JSON_MAX_LINE_BYTES = 24 * 1024


def _is_parseable_json(raw: bytes) -> bool:
    try:
        json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    return True


def _require_patchable_worker_json(raw: bytes) -> None:
    """Reject valid JSON whose physical lines cannot fit one bounded patch."""

    try:
        text = raw.decode("utf-8")
        json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return
    longest = max((len(line) for line in raw.splitlines()), default=len(raw))
    if longest > _PATCHABLE_JSON_MAX_LINE_BYTES:
        raise TaskInputError(
            "worker JSON has a physical line longer than 24576 bytes; "
            "write output/result.json as stable pretty JSON with two-space "
            "indentation so later Codex patches can match bounded lines"
        )


def _apply_worker_json_patch(
    document: Any, operations: tuple[dict[str, Any], ...]
) -> Any:
    """Apply the supported RFC-6902 subset to a detached JSON value."""

    value = json.loads(json.dumps(document, ensure_ascii=False, allow_nan=False))
    for index, operation in enumerate(operations):
        op = operation.get("op")
        path = operation.get("path")
        if op not in {"test", "add", "replace", "remove"}:
            raise ValueError(f"operation {index} has an unsupported op")
        if not isinstance(path, str):
            raise ValueError(f"operation {index} requires a JSON Pointer path")
        tokens = _worker_json_pointer_tokens(path)
        parent = value
        for token in tokens[:-1]:
            parent = _worker_json_pointer_get(parent, token, path)
        leaf = tokens[-1]
        has_value = "value" in operation
        if op == "remove" and has_value:
            raise ValueError(f"remove operation {index} must not declare value")
        if op != "remove" and not has_value:
            raise ValueError(f"operation {index} requires value")
        if op == "test":
            current = _worker_json_pointer_get(parent, leaf, path)
            if canonical_json(current) != canonical_json(operation["value"]):
                current_preview = _bounded_utf8(
                    canonical_json(current).decode("utf-8"), 256
                )
                raise ValueError(
                    f"test operation {index} did not match {path}; "
                    f"current={current_preview}"
                )
            continue
        if isinstance(parent, dict):
            exists = leaf in parent
            if op in {"replace", "remove"} and not exists:
                raise ValueError(f"JSON Pointer path does not exist: {path}")
            if op == "remove":
                del parent[leaf]
            else:
                parent[leaf] = json.loads(
                    json.dumps(operation["value"], ensure_ascii=False, allow_nan=False)
                )
            continue
        if isinstance(parent, list):
            if op == "add" and leaf == "-":
                list_index = len(parent)
            else:
                list_index = _worker_json_list_index(
                    leaf, len(parent), allow_end=op == "add"
                )
            if op == "add":
                parent.insert(list_index, operation["value"])
            elif op == "replace":
                parent[list_index] = operation["value"]
            else:
                del parent[list_index]
            continue
        raise ValueError(f"JSON Pointer path has a scalar parent: {path}")
    return value


def _worker_json_pointer_tokens(path: str) -> tuple[str, ...]:
    if not path.startswith("/") or path == "/":
        raise ValueError("JSON patch path must be a non-root JSON Pointer")
    tokens: list[str] = []
    for raw in path[1:].split("/"):
        token = ""
        cursor = 0
        while cursor < len(raw):
            if raw[cursor] != "~":
                token += raw[cursor]
                cursor += 1
                continue
            if cursor + 1 >= len(raw) or raw[cursor + 1] not in {"0", "1"}:
                raise ValueError("JSON patch path contains an invalid escape")
            token += "~" if raw[cursor + 1] == "0" else "/"
            cursor += 2
        tokens.append(token)
    return tuple(tokens)


def _worker_json_pointer_get(parent: Any, token: str, path: str) -> Any:
    if isinstance(parent, dict):
        if token not in parent:
            raise ValueError(f"JSON Pointer path does not exist: {path}")
        return parent[token]
    if isinstance(parent, list):
        return parent[_worker_json_list_index(token, len(parent), allow_end=False)]
    raise ValueError(f"JSON Pointer path has a scalar parent: {path}")


def _worker_json_list_index(token: str, length: int, *, allow_end: bool) -> int:
    if not token.isdigit() or (len(token) > 1 and token.startswith("0")):
        raise ValueError("JSON patch list index is invalid")
    index = int(token)
    maximum = length if allow_end else length - 1
    if index > maximum:
        raise ValueError("JSON patch list index is out of range")
    return index


def _bounded_utf8(value: str, max_bytes: int) -> str:
    raw = value.encode("utf-8")
    if len(raw) <= max_bytes:
        return value
    return raw[: max(0, max_bytes - 3)].decode("utf-8", errors="ignore") + "..."


def _patch_line_preview(value: str | None) -> str:
    if value is None:
        return "<missing>"
    line = value.rstrip("\r\n")
    return json.dumps(
        _bounded_utf8(line, _PATCH_LINE_PREVIEW_MAX_BYTES), ensure_ascii=True
    )


def _patch_context_not_found_message(
    *,
    original: str,
    original_lines: list[str],
    hunk_count: int,
    old_start: int,
    declared_start: int,
    old_payload: list[str],
) -> str:
    current = original_lines[declared_start : declared_start + len(old_payload)]
    difference_offset = next(
        (
            offset
            for offset, expected in enumerate(old_payload)
            if offset >= len(current) or current[offset] != expected
        ),
        0,
    )
    expected_line = (
        old_payload[difference_offset]
        if difference_offset < len(old_payload)
        else None
    )
    current_line = (
        current[difference_offset] if difference_offset < len(current) else None
    )
    message = (
        f"worker file patch hunk {hunk_count} context_not_found; "
        f"target_sha256={hashlib.sha256(original.encode('utf-8')).hexdigest()}; "
        f"declared_line={old_start}; "
        f"difference_line={declared_start + difference_offset + 1}; "
        f"expected_line={_patch_line_preview(expected_line)}; "
        f"current_line={_patch_line_preview(current_line)}; "
        "re-read the current target and regenerate one smaller diff"
    )
    return _bounded_utf8(message, _PATCH_DIAGNOSTIC_MAX_BYTES)


def _patch_context_ambiguous_message(
    *,
    original: str,
    hunk_count: int,
    old_payload: list[str],
    candidates: list[int],
) -> str:
    candidate_lines = ",".join(str(index + 1) for index in candidates[:16])
    if len(candidates) > 16:
        candidate_lines += ",..."
    message = (
        f"worker file patch hunk {hunk_count} context_ambiguous; "
        f"target_sha256={hashlib.sha256(original.encode('utf-8')).hexdigest()}; "
        f"candidate_lines={candidate_lines}; "
        f"expected_line={_patch_line_preview(old_payload[0] if old_payload else None)}; "
        "re-read the current target and include more unchanged context"
    )
    return _bounded_utf8(message, _PATCH_DIAGNOSTIC_MAX_BYTES)


def _apply_unified_patch(
    original: str, patch: str, *, max_patch_bytes: int
) -> str:
    if not patch or len(patch.encode("utf-8")) > max_patch_bytes:
        raise TaskInputError("worker file patch exceeds its byte limit")
    original_lines = original.splitlines(keepends=True)
    patch_lines = patch.splitlines(keepends=True)
    output: list[str] = []
    original_cursor = 0
    patch_cursor = 0
    hunk_count = 0
    while patch_cursor < len(patch_lines):
        line = patch_lines[patch_cursor]
        if line.startswith("--- ") or line.startswith("+++ "):
            patch_cursor += 1
            continue
        match = _UNIFIED_HUNK.match(line)
        if match is None:
            raise TaskInputError("worker file patch must contain unified diff hunks")
        hunk_count += 1
        old_start = int(match.group(1))
        old_count = int(match.group(2) or "1")
        new_count = int(match.group(4) or "1")
        patch_cursor += 1
        changes: list[str] = []
        observed_old = 0
        observed_new = 0
        while patch_cursor < len(patch_lines):
            change = patch_lines[patch_cursor]
            if _UNIFIED_HUNK.match(change):
                break
            if change.startswith("--- ") or change.startswith("+++ "):
                raise TaskInputError("worker file patch contains misplaced headers")
            if change.startswith("\\ No newline at end of file"):
                raise TaskInputError("worker file patch newline markers are unsupported")
            if not change or change[0] not in {" ", "+", "-"}:
                raise TaskInputError("worker file patch contains an invalid change line")
            changes.append(change)
            if change[0] in {" ", "-"}:
                observed_old += 1
            if change[0] in {" ", "+"}:
                observed_new += 1
            patch_cursor += 1
        if observed_old != old_count or observed_new != new_count:
            raise TaskInputError("worker file patch hunk counts are inconsistent")
        old_payload = [
            change[1:] for change in changes if change[0] in {" ", "-"}
        ]
        declared_start = (
            old_start if old_count == 0 else (0 if old_start == 0 else old_start - 1)
        )
        if old_count == 0:
            if declared_start < original_cursor or declared_start > len(original_lines):
                raise TaskInputError(
                    f"worker file patch hunk {hunk_count} position_invalid"
                )
            hunk_start = declared_start
        elif (
            declared_start >= original_cursor
            and declared_start + old_count <= len(original_lines)
            and original_lines[declared_start : declared_start + old_count]
            == old_payload
        ):
            hunk_start = declared_start
        else:
            candidates = [
                index
                for index in range(
                    original_cursor, len(original_lines) - old_count + 1
                )
                if original_lines[index : index + old_count] == old_payload
            ]
            if not candidates:
                raise TaskInputError(
                    _patch_context_not_found_message(
                        original=original,
                        original_lines=original_lines,
                        hunk_count=hunk_count,
                        old_start=old_start,
                        declared_start=declared_start,
                        old_payload=old_payload,
                    )
                )
            if len(candidates) != 1:
                raise TaskInputError(
                    _patch_context_ambiguous_message(
                        original=original,
                        hunk_count=hunk_count,
                        old_payload=old_payload,
                        candidates=candidates,
                    )
                )
            hunk_start = candidates[0]
        output.extend(original_lines[original_cursor:hunk_start])
        original_cursor = hunk_start
        for change in changes:
            payload = change[1:]
            if change[0] in {" ", "-"}:
                if (
                    original_cursor >= len(original_lines)
                    or original_lines[original_cursor] != payload
                ):
                    raise TaskInputError(
                        f"worker file patch hunk {hunk_count} context_changed; "
                        "re-read the current target and regenerate the diff"
                    )
                original_cursor += 1
            if change[0] in {" ", "+"}:
                output.append(payload)
    if hunk_count == 0:
        raise TaskInputError("worker file patch contains no hunks")
    output.extend(original_lines[original_cursor:])
    return "".join(output)


def _apply_codex_patch(
    original: str,
    patch: str,
    *,
    relative_path: str,
    max_patch_bytes: int,
) -> str:
    """Apply one count-free Codex ``*** Begin Patch`` update section."""

    if not patch or len(patch.encode("utf-8")) > max_patch_bytes:
        raise TaskInputError("worker file patch exceeds its byte limit")
    patch_lines = patch.splitlines(keepends=True)
    if (
        len(patch_lines) < 4
        or patch_lines[0].rstrip("\r\n") != "*** Begin Patch"
        or patch_lines[-1].rstrip("\r\n") != "*** End Patch"
    ):
        raise TaskInputError("worker Codex patch envelope is invalid")
    update = patch_lines[1].rstrip("\r\n")
    prefix = "*** Update File: "
    if not update.startswith(prefix) or update[len(prefix) :] != relative_path:
        raise TaskInputError("worker Codex patch target differs from relative_path")

    original_lines = original.splitlines(keepends=True)
    output: list[str] = []
    original_cursor = 0
    patch_cursor = 2
    hunk_count = 0
    while patch_cursor < len(patch_lines) - 1:
        header = patch_lines[patch_cursor].rstrip("\r\n")
        if not header.startswith("@@"):
            raise TaskInputError("worker Codex patch must contain @@ hunks")
        hunk_count += 1
        patch_cursor += 1
        changes: list[str] = []
        while patch_cursor < len(patch_lines) - 1:
            change = patch_lines[patch_cursor]
            if change.startswith("@@"):
                break
            if change.startswith("*** "):
                raise TaskInputError("worker Codex patch contains an unsupported section")
            if not change or change[0] not in {" ", "+", "-"}:
                raise TaskInputError(
                    "worker Codex patch change lines must start with space, +, or -"
                )
            changes.append(change)
            patch_cursor += 1
        if not changes:
            raise TaskInputError("worker Codex patch hunk is empty")
        old_payload = [
            change[1:] for change in changes if change[0] in {" ", "-"}
        ]
        if not old_payload:
            raise TaskInputError(
                "worker Codex patch insertion requires at least one context line"
            )
        candidates = [
            index
            for index in range(
                original_cursor, len(original_lines) - len(old_payload) + 1
            )
            if original_lines[index : index + len(old_payload)] == old_payload
        ]
        if not candidates:
            raise TaskInputError(
                _patch_context_not_found_message(
                    original=original,
                    original_lines=original_lines,
                    hunk_count=hunk_count,
                    old_start=original_cursor + 1,
                    declared_start=original_cursor,
                    old_payload=old_payload,
                )
            )
        if len(candidates) != 1:
            raise TaskInputError(
                _patch_context_ambiguous_message(
                    original=original,
                    hunk_count=hunk_count,
                    old_payload=old_payload,
                    candidates=candidates,
                )
            )
        hunk_start = candidates[0]
        output.extend(original_lines[original_cursor:hunk_start])
        original_cursor = hunk_start
        for change in changes:
            payload = change[1:]
            if change[0] in {" ", "-"}:
                if (
                    original_cursor >= len(original_lines)
                    or original_lines[original_cursor] != payload
                ):
                    raise TaskInputError(
                        f"worker file patch hunk {hunk_count} context_changed; "
                        "re-read the current target and regenerate the patch"
                    )
                original_cursor += 1
            if change[0] in {" ", "+"}:
                output.append(payload)
    if hunk_count == 0:
        raise TaskInputError("worker Codex patch contains no hunks")
    output.extend(original_lines[original_cursor:])
    return "".join(output)


def _apply_worker_patch(
    original: str,
    patch: str,
    *,
    relative_path: str,
    max_patch_bytes: int,
) -> str:
    if patch.startswith("*** Begin Patch"):
        return _apply_codex_patch(
            original,
            patch,
            relative_path=relative_path,
            max_patch_bytes=max_patch_bytes,
        )
    return _apply_unified_patch(original, patch, max_patch_bytes=max_patch_bytes)


def _read_regular_output_file(
    root: Path, relative_path: Path, *, max_bytes: int
) -> bytes:
    try:
        root_details = os.lstat(root)
    except OSError as error:
        raise TaskInputError("worker output directory does not exist") from error
    if stat.S_ISLNK(root_details.st_mode) or not stat.S_ISDIR(root_details.st_mode):
        raise TaskInputError("worker output directory must be a real directory")
    if (
        relative_path.is_absolute()
        or not relative_path.parts
        or any(part in {"", ".", ".."} for part in relative_path.parts)
        or "\\" in relative_path.as_posix()
    ):
        raise TaskInputError("worker output path is unsafe")
    current = root
    for part in relative_path.parts[:-1]:
        current = current / part
        try:
            details = os.lstat(current)
        except OSError as error:
            raise TaskInputError("declared collection path does not exist") from error
        if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode):
            raise TaskInputError("declared collection path must use real directories")
    path = root / relative_path
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise TaskInputError(
            "declared collection item must exist as a regular file"
        ) from error
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode):
            raise TaskInputError("declared collection item must be a regular file")
        if details.st_size > max_bytes:
            raise TaskInputError("declared collection item exceeds its byte limit")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            content = stream.read(max_bytes + 1)
    finally:
        os.close(descriptor)
    if len(content) > max_bytes:
        raise TaskInputError("declared collection item exceeds its byte limit")
    return content


def _collection_output_paths(output_directory: Path) -> set[str]:
    collections = output_directory / "collections"
    try:
        root_details = os.lstat(collections)
    except OSError as error:
        raise TaskInputError("output/collections must be a real directory") from error
    if stat.S_ISLNK(root_details.st_mode) or not stat.S_ISDIR(root_details.st_mode):
        raise TaskInputError("output/collections must be a real directory")
    paths: set[str] = set()
    for current, directories, files in os.walk(collections, followlinks=False):
        current_path = Path(current)
        for name in directories:
            details = os.lstat(current_path / name)
            if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode):
                raise TaskInputError("collection directories must not be symlinks")
        for name in files:
            path = current_path / name
            details = os.lstat(path)
            if stat.S_ISLNK(details.st_mode) or not stat.S_ISREG(details.st_mode):
                raise TaskInputError("collection items must be regular non-symlink files")
            paths.add(path.relative_to(output_directory).as_posix())
    return paths


def _bundle_error(message: str, path: str) -> TaskInputError:
    return TaskInputError(
        message,
        details=({"path": path, "message": message, "type": "value_error"},),
    )


def _validate_figure_evidence_bundle(
    artifacts: tuple[_ValidatedOutputArtifact, ...],
) -> _ValidatedOutputArtifact | None:
    """Bind manifest provenance claims to the exact sibling bytes."""

    manifests = tuple(
        item
        for item in artifacts
        if item.spec.schema_id == "scidiscovery.figure-evidence-manifest.v1"
    )
    if not manifests:
        return None
    if len(manifests) != 1:
        raise _bundle_error(
            "figure evidence bundle must contain exactly one manifest",
            "$.bundle.items",
        )
    try:
        manifest = json.loads(manifests[0].content.decode("utf-8"))
        declared_items = manifest["provenance"]["output_artifacts"]
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise _bundle_error(
            "figure manifest provenance is unavailable",
            "$.bundle.items",
        ) from error
    declared = {item["data_item"]: item for item in declared_items}
    actual = {
        f"{item.descriptor.collection}/{item.descriptor.item}": item
        for item in artifacts
        if item.descriptor.collection
        in {"source_panels", "audit_overlays", "curve_tables"}
    }
    if set(declared) != set(actual):
        raise _bundle_error(
            "figure manifest provenance must exactly enumerate sibling outputs",
            "$.bundle.items",
        )
    for name, sibling in actual.items():
        record = declared[name]
        if (
            record["bytes"] != len(sibling.content)
            or record["sha256"] != hashlib.sha256(sibling.content).hexdigest()
            or record["media_type"].strip().lower()
            != sibling.descriptor.media_type.strip().lower()
        ):
            raise _bundle_error(
                f"figure manifest provenance does not match sibling bytes: {name}",
                "$.bundle.items",
            )
    try:
        report = build_figure_evidence_validation_report(
            manifest_data_item=(
                f"{manifests[0].descriptor.collection}/"
                f"{manifests[0].descriptor.item}"
            ),
            manifest_content=manifests[0].content,
            sibling_files={
                name: (item.content, item.descriptor.media_type)
                for name, item in actual.items()
            },
        )
        normalized = validate_figure_evidence_validation_report(report)
    except (FigureEvidenceBundleError, ValidationError, ValueError) as error:
        raise _bundle_error(
            f"figure evidence CSV validation failed: {error}",
            "$.bundle.items",
        ) from error
    return _ValidatedOutputArtifact(
        descriptor=TaskOutputBundleItem(
            collection="validation_reports",
            item="validation_report.json",
            media_type="application/json",
            relative_path="collections/validation_reports/validation_report.json",
        ),
        spec=_FIGURE_VALIDATION_REPORT_SPEC,
        content=canonical_json(normalized),
        control_generated=True,
    )


def _validate_figure_evidence_handoff_binding(
    primary_content: dict[str, Any],
    validation_report: _ValidatedOutputArtifact,
) -> None:
    """Require the handoff to name the exact staged evidence bundle."""

    try:
        handoff = primary_content["handoff"]
        expected = json.loads(validation_report.content.decode("utf-8"))[
            "bundle_fingerprint_sha256"
        ]
        actual = handoff["evidence_bundle_fingerprint_sha256"]
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise _bundle_error(
            "figure evidence handoff must bind the exact validated bundle fingerprint",
            "$.handoff.evidence_bundle_fingerprint_sha256",
        ) from error
    if actual != expected:
        raise _bundle_error(
            "figure evidence handoff fingerprint does not match the staged bundle",
            "$.handoff.evidence_bundle_fingerprint_sha256",
        )
    if handoff.get("assumptions"):
        raise _bundle_error(
            "figure evidence handoff assumptions belong in the payload and exact manifest",
            "$.handoff.assumptions",
        )
    if handoff.get("missing_inputs"):
        raise _bundle_error(
            "figure evidence handoff missing_inputs must be represented by the exact manifest and audit",
            "$.handoff.missing_inputs",
        )
    if handoff.get("next_actions"):
        raise _bundle_error(
            "figure evidence handoff next_actions are projected from the exact bundle",
            "$.handoff.next_actions",
        )


def _figure_evidence_scheduler_signal(
    signal: SchedulerSignal,
    artifacts: tuple[_ValidatedOutputArtifact, ...],
) -> SchedulerSignal:
    """Project figure task status from the exact registered manifest/report bytes."""

    reports = tuple(
        item
        for item in artifacts
        if item.control_generated
        and item.spec.schema_id
        == "scidiscovery.figure-evidence-validation-report.v1"
    )
    if not reports:
        return signal
    if len(reports) != 1:
        raise TaskServiceError("validated figure evidence report is not unique")
    manifests = tuple(
        item
        for item in artifacts
        if item.spec.schema_id == "scidiscovery.figure-evidence-manifest.v1"
    )
    if len(manifests) != 1:
        raise TaskServiceError("validated figure evidence manifest is not unique")
    try:
        report = json.loads(reports[0].content.decode("utf-8"))
        manifest = json.loads(manifests[0].content.decode("utf-8"))
        source_status = report["source_status"]
        series_count = report["metrics"]["curve_table_count"]
        ambiguities = manifest.get("ambiguities", [])
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise TaskServiceError("validated figure evidence projection is invalid") from error
    missing_inputs = tuple(
        str(item["message"])[:512]
        for item in ambiguities[:32]
        if isinstance(item, dict) and isinstance(item.get("message"), str)
    )
    return SchedulerSignal(
        verdict=signal.verdict,
        summary=(
            "The exact registered figure-evidence bundle is mechanically valid "
            f"and fingerprint-bound; manifest status is {source_status} across "
            f"{series_count} curve tables. Independent evidence audit is required "
            "for image semantics and claim scope."
        ),
        assumptions=(),
        missing_inputs=missing_inputs,
        next_actions=(
            "Audit the exact registered manifest, validation report, source panels, "
            "overlays, and curve tables as one provisional evidence set.",
        ),
    )


def _deck_project_model() -> Any:
    try:
        return getattr(import_module("tcad_artifact.project_packager"), "DeckProjectDraft")
    except (ImportError, AttributeError) as error:
        raise TaskServiceError("TCAD deck project model is unavailable") from error


def _pretty_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_deck_workspace_file(
    root: Path, destination: Path, content: bytes, *, editable: bool
) -> None:
    root = root.absolute()
    destination = destination.absolute()
    if destination != root and root not in destination.parents:
        raise TaskInputError("deck workspace path escapes its root")
    relative = destination.relative_to(root)
    _validated_provisional_relative_path(relative.as_posix())
    current = root
    for part in relative.parts[:-1]:
        current = current / part
        if current.exists() or current.is_symlink():
            details = os.lstat(current)
            if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode):
                raise TaskInputError("deck workspace parent must be a real directory")
        else:
            current.mkdir(mode=0o700)
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not destination.is_file():
            raise TaskInputError("deck workspace file must be regular")
        if destination.read_bytes() != content:
            raise TaskInputError("existing deck workspace file differs from its source")
        return
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(destination, flags, 0o600 if editable else 0o440)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def _make_tree_read_only(root: Path) -> None:
    for current, directories, files in os.walk(root, topdown=False, followlinks=False):
        directory = Path(current)
        if directory.is_symlink():
            raise TaskInputError("deck review workspace cannot contain symlinks")
        for name in files:
            path = directory / name
            if path.is_symlink() or not path.is_file():
                raise TaskInputError("deck review file must be regular")
            os.chmod(path, 0o440)
        for name in directories:
            path = directory / name
            if path.is_symlink() or not path.is_dir():
                raise TaskInputError("deck review directory must be real")
            os.chmod(path, 0o550)
        os.chmod(directory, 0o550)


def _read_regular_deck_file(root: Path, relative: Path, *, max_bytes: int) -> bytes:
    try:
        details = os.lstat(root)
    except OSError as error:
        raise TaskInputError("deck workspace has not been materialized") from error
    if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode):
        raise TaskInputError("deck workspace must be a real directory")
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise TaskInputError("deck workspace path is unsafe")
    current = root
    for part in relative.parts[:-1]:
        current = current / part
        try:
            details = os.lstat(current)
        except OSError as error:
            raise TaskInputError("deck workspace directory is missing") from error
        if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode):
            raise TaskInputError("deck workspace directory must be real")
    path = root / relative
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise TaskInputError(f"deck workspace file is missing: {relative.as_posix()}") from error
    try:
        file_details = os.fstat(descriptor)
        if not stat.S_ISREG(file_details.st_mode):
            raise TaskInputError("deck workspace item must be a regular file")
        if file_details.st_size > max_bytes:
            raise TaskInputError("deck workspace file exceeds its byte limit")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            content = stream.read(max_bytes + 1)
    finally:
        os.close(descriptor)
    if len(content) > max_bytes:
        raise TaskInputError("deck workspace file exceeds its byte limit")
    return content


def _read_deck_workspace_file_bytes(root: Path) -> tuple[tuple[str, bytes], ...]:
    try:
        root_details = os.lstat(root)
    except OSError as error:
        raise TaskInputError("deck/files directory does not exist") from error
    if stat.S_ISLNK(root_details.st_mode) or not stat.S_ISDIR(root_details.st_mode):
        raise TaskInputError("deck/files must be a real directory")
    values: list[tuple[str, bytes]] = []
    total = 0
    for current, directories, files in os.walk(root, followlinks=False):
        directory = Path(current)
        if directory.is_symlink():
            raise TaskInputError("deck/files cannot contain symlink directories")
        for name in directories:
            path = directory / name
            if path.is_symlink() or not path.is_dir():
                raise TaskInputError("deck/files directory must be real")
        for name in files:
            path = directory / name
            relative = path.relative_to(root)
            _validated_provisional_relative_path(relative.as_posix())
            content = _read_regular_deck_file(
                root, relative, max_bytes=8 * 1024 * 1024
            )
            total += len(content)
            if total > 64 * 1024 * 1024:
                raise TaskInputError("deck source exceeds its total byte limit")
            values.append((relative.as_posix(), content))
            if len(values) > 4096:
                raise TaskInputError("deck source file count exceeds its limit")
    return tuple(sorted(values))


def _read_deck_workspace_files(root: Path) -> list[dict[str, str]]:
    values: list[dict[str, str]] = []
    for relative_path, content in _read_deck_workspace_file_bytes(root):
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise TaskInputError(
                f"deck source file is not UTF-8: {relative_path}"
            ) from error
        values.append({"relative_path": relative_path, "content": text})
    return values


def _write_control_output_file(destination: Path, content: bytes) -> None:
    parent = destination.parent
    details = os.lstat(parent)
    if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode):
        raise TaskInputError("worker output directory must be a real directory")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".result.json.control.", dir=parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _lease_seconds(timeout_seconds: int) -> int:
    return min(600, timeout_seconds)


def _requires_first_persisted_progress(task: AgentTask) -> bool:
    return (
        task.role == "experiment_designer"
        and task.output.schema_id == "scidiscovery.experiment-design-intent.v1"
    )


def _input_access_modes(media_type: str) -> tuple[str, ...]:
    base = media_type.split(";", 1)[0].strip().lower()
    if base == "application/pdf":
        return ("native_read", "extract_pdf_text")
    return ("native_read",)


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
        validated = _validate_role_output(output.validator, content)
        if output.revision is not None:
            revision = StructuredRevision.model_validate_json(
                canonical_json(validated), strict=True
            )
            for operation in revision.operations:
                if not operation_is_within_scope(
                    operation.path, output.revision.allowed_paths
                ):
                    raise TaskInputError(
                        f"revision path is outside the declared scope: {operation.path}"
                    )
        raw = canonical_json(validated)
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


def _validate_contextual_role_output(
    validator: str | None,
    content: dict[str, Any],
    inputs: dict[str, bytes],
    handoff: dict[str, Any],
) -> None:
    """Validate one role result against its exact declared task inputs."""

    if validator is None:
        return
    module_name, separator, attribute = validator.partition(":")
    if not separator or not module_name or not attribute:
        raise TaskServiceError("registered contextual output validator is invalid")
    try:
        function = getattr(import_module(module_name), attribute)
    except (ImportError, AttributeError) as error:
        raise TaskServiceError(
            "registered contextual output validator is unavailable"
        ) from error
    try:
        function(content, inputs, handoff)
    except (TypeError, ValueError) as error:
        details = _validation_details(error)
        summary = "; ".join(
            f"{item['path']}: {item['message']}" for item in details[:8]
        ) or str(error)
        raise TaskInputError(
            f"contextual role output validation failed: {summary}", details=details
        ) from error


def _validate_collection_bundle(
    validator: str,
    primary_content: dict[str, Any],
    items: dict[str, bytes],
) -> None:
    """Run one internal collection-to-primary integrity validator."""

    module_name, separator, attribute = validator.partition(":")
    if not separator or not module_name or not attribute:
        raise TaskServiceError("registered collection bundle validator is invalid")
    try:
        function = getattr(import_module(module_name), attribute)
    except (ImportError, AttributeError) as error:
        raise TaskServiceError(
            "registered collection bundle validator is unavailable"
        ) from error
    try:
        function(primary_content, items)
    except (TypeError, ValueError) as error:
        details = _validation_details(error)
        summary = "; ".join(
            f"{item['path']}: {item['message']}" for item in details[:8]
        ) or str(error)
        raise TaskInputError(
            f"collection bundle validation failed: {summary}", details=details
        ) from error


def _validation_details(error: Exception) -> tuple[dict[str, str], ...]:
    if isinstance(error, ValidationError):
        raw = error.errors(include_url=False)
        leaf_errors = []
        for item in raw:
            location = tuple(item["loc"])
            if str(item["type"]) in {
                "too_short",
                "too_long",
                "missing",
            } and any(
                len(tuple(other["loc"])) > len(location)
                and tuple(other["loc"])[: len(location)] == location
                for other in raw
            ):
                continue
            leaf_errors.append(item)
        details = []
        for item in leaf_errors[:64]:
            location = tuple(item["loc"])
            error_type = str(item["type"])
            message = str(item["msg"])
            details.append(
                {
                    "path": ".".join(str(part) for part in location) or "$",
                    "json_pointer": _validation_json_pointer(location),
                    "message": message,
                    "type": error_type,
                    "reason_code": _validation_reason_code(error_type, message),
                    "expected_contract": _validation_expected_contract(
                        error_type, message
                    ),
                    "fix_hint": _validation_fix_hint(error_type, message),
                }
            )
        return tuple(details)
    return ({"path": "$", "message": str(error), "type": "value_error"},)


def _validation_json_pointer(location: tuple[Any, ...]) -> str:
    if not location:
        return ""
    return "/" + "/".join(
        str(part).replace("~", "~0").replace("/", "~1") for part in location
    )


def _validation_reason_code(error_type: str, message: str) -> str:
    normalized = message.lower()
    if "sharp-front comparison requires" in normalized:
        return "sharp_front_operator_required"
    if "thresholded validation-check binding" in normalized:
        return "threshold_check_binding_required"
    if "series roles are incompatible" in normalized:
        return "curve_series_role_incompatible"
    if "series declarations must be unique" in normalized:
        return "curve_series_declaration_duplicate"
    if error_type == "json_invalid":
        return "json_invalid"
    return error_type.replace(".", "_")


def _validation_expected_contract(error_type: str, message: str) -> str:
    if error_type == "missing":
        return "required field present"
    if error_type == "extra_forbidden":
        return "only declared schema fields"
    if error_type in {"float_type", "int_type", "string_type", "bool_type"}:
        return error_type.removesuffix("_type")
    return message


def _validation_fix_hint(error_type: str, message: str) -> str:
    normalized = message.lower()
    if error_type == "json_invalid":
        return "repair JSON syntax at the reported pointer before schema changes"
    if error_type == "missing":
        return "add only the required field at this pointer"
    if error_type == "extra_forbidden":
        return "remove the undeclared field at this pointer"
    if error_type == "float_type":
        return "encode the numeric literal as a JSON float, for example 1.0e3"
    if "thresholded validation-check binding" in normalized:
        return "bind a threshold only for a required numerical-qualification gate"
    if "series roles are incompatible" in normalized:
        return "use one declaration per series; control derives compact-intent roles"
    return "correct this leaf field without rewriting unrelated scientific content"


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
    "TaskOutputArtifactView",
    "TaskWebEvidenceView",
]
