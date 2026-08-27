"""Task-bound development-only TCAD debugging outside production execution."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

from ..schema.common import canonical_json
from ..schema.execution import LocalFileDescriptor
from ..schema.refs import ArtifactRef
from .tasks import (
    AgentTask,
    TaskInputError,
    TaskService,
    TaskServiceError,
    _WorkspaceSnapshotFile,
    _parse_timestamp,
    _timestamp,
    _write_control_output_file,
)


_DEBUG_LEASE_SECONDS = 900
_DEBUG_MAX_RUNS = 6
_DEBUG_MAX_TOTAL_WALL_SECONDS = 360
_DEBUG_MAX_RESPONSE_BYTES = 32 * 1024
_DEBUG_MAX_FILES = 64
_DEBUG_MAX_FILE_BYTES = 8 * 1024 * 1024
_DEBUG_MAX_OUTPUT_BYTES = 16 * 1024 * 1024
_RUN_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_OUTPUT_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_DEBUG_MODES = frozenset({"preflight", "smoke", "initialization"})
_PREPARATION_REASON_CODES = {
    "development debug requires a direct TCAD solver": "direct_solver_required",
    "development debug capability differs from the project": "capability_mismatch",
    "development debug does not admit worker-selected solver arguments": "solver_arguments_not_admitted",
    "development debug capability is not active": "capability_inactive",
    "development debug capability discovery failed": "capability_discovery_failed",
    "development debug release has no bundled mode contract": "release_mode_unavailable",
    "development debug task sources are not unique": "task_sources_not_unique",
    "initialization mode requires an author-declared development entrypoint": "initialization_entrypoint_missing",
    "development debug project slot has no exact task input": "input_slot_missing",
    "development debug project slot media type differs": "input_slot_media_mismatch",
    "development debug exchange is not a real directory": "exchange_invalid",
    "development debug exchange setup failed": "exchange_setup_failed",
    "development debug project packaging failed": "project_packaging_rejected",
    "development debug archive path is unsupported": "archive_path_unsupported",
    "development debug job materialization failed": "job_materialization_failed",
}


class TCADDebugError(TaskServiceError):
    pass


@dataclass(frozen=True)
class TCADDebugSource:
    source_name: str
    artifact_ref: ArtifactRef
    media_type: str
    content: bytes


@dataclass(frozen=True)
class PreparedTCADDebugRun:
    submission: LocalFileDescriptor
    wall_time_seconds: int


@dataclass(frozen=True)
class CollectedTCADDebugFile:
    name: str
    media_type: str
    content: bytes


@dataclass(frozen=True)
class TCADSourceDiagnostic:
    source_relative_path: str | None
    reported_line: int | None
    line_basis: str
    procedure: str | None
    procedure_line: int | None
    message: str
    command_excerpt: str | None


@dataclass(frozen=True)
class CollectedTCADDebugRun:
    terminal_state: str
    exit_code: int
    diagnostic_layer: str
    summary: str
    log_excerpt: str
    files: tuple[CollectedTCADDebugFile, ...]
    source_diagnostic: TCADSourceDiagnostic | None = None


class TCADDevelopmentDebugAdapter(Protocol):
    def prepare(
        self,
        *,
        project: bytes,
        capability: bytes,
        sources: tuple[TCADDebugSource, ...],
        exchange_directory: Path,
        mode: str,
    ) -> PreparedTCADDebugRun: ...

    def clamp_wall_time(
        self, prepared: PreparedTCADDebugRun, *, wall_time_seconds: int
    ) -> PreparedTCADDebugRun: ...

    def prepare_submission(
        self, prepared: PreparedTCADDebugRun
    ) -> LocalFileDescriptor: ...

    def submit(self, submission: LocalFileDescriptor) -> tuple[str, str]: ...

    def status(self, external_run_id: str) -> str: ...

    def cancel(self, external_run_id: str) -> str: ...

    def collect(self, external_run_id: str) -> CollectedTCADDebugRun: ...


class TCADDebugService:
    """Own a fixed, nonrenewable lease for one author task attempt."""

    def __init__(
        self,
        *,
        tasks: TaskService,
        adapter: TCADDevelopmentDebugAdapter,
        exchange_root: Path | str,
    ) -> None:
        self.tasks = tasks
        self.adapter = adapter
        self.exchange_root = Path(exchange_root).expanduser().absolute()
        self.exchange_root.mkdir(parents=True, exist_ok=True, mode=0o750)
        if self.exchange_root.is_symlink() or not self.exchange_root.is_dir():
            raise ValueError("TCAD debug exchange root must be a real directory")

    def run(
        self,
        session_token: str,
        *,
        worker_id: str,
        run_name: str,
        mode: str,
    ) -> dict[str, object]:
        if not _RUN_NAME.fullmatch(run_name):
            raise TCADDebugError("TCAD debug run_name is invalid")
        if mode not in _DEBUG_MODES:
            raise TCADDebugError("TCAD development mode is invalid")
        session = self.tasks.tokens.verify_session(
            session_token, worker_id=worker_id
        )
        self.tasks._require_active_claim(session.task_id, session.attempt)
        task = self.tasks.get_task(session.task_id)
        if task.role != "tcad_deck_author" or worker_id != "tcad_deck_author":
            raise TCADDebugError(
                "TCAD development debug is available only to tcad_deck_author"
            )
        capability_inputs = tuple(
            item for item in task.inputs if item.name == "execution_capability"
        )
        if len(capability_inputs) != 1:
            raise TCADDebugError(
                "TCAD development debug requires exactly one execution_capability"
            )
        capability_input = capability_inputs[0]
        capability_envelope = self.tasks.artifacts.verify(
            capability_input.artifact_ref
        )
        if capability_envelope.schema_id != "tcad.solver-capability.v2":
            raise TCADDebugError("execution_capability has the wrong schema")
        lease = self._lease(session)
        row = self._run_row(session.session_id, run_name)
        if row is not None and row["mode"] != mode:
            raise TCADDebugError(
                "TCAD debug run_name is already bound to a different mode"
            )
        if row is None:
            raw, snapshot_ref, sources, source_tree_sha256 = self._snapshot_project(
                session=session,
                task=task,
                capability_ref=capability_input.artifact_ref,
            )
            exchange = self.exchange_root / session.session_id / run_name
            exchange.mkdir(parents=True, exist_ok=True, mode=0o750)
            try:
                prepared = self.adapter.prepare(
                    project=raw,
                    capability=self.tasks.artifacts.read(
                        capability_input.artifact_ref
                    ),
                    sources=sources,
                    exchange_directory=exchange,
                    mode=mode,
                )
            except Exception as error:
                reason_code = _preparation_reason_code(error)
                try:
                    self.tasks.store_development_debug_snapshot(
                        session=session,
                        task=task,
                        files=(),
                        diagnostics=(
                            {
                                "path": "$.debug.preparation",
                                "message": (
                                    "staged project is not eligible for direct-solver "
                                    f"debug; preparation_reason_code={reason_code}"
                                ),
                                "type": "development_debug_preparation_rejected",
                            },
                        ),
                    )
                finally:
                    self._cleanup_exchange(session.session_id, run_name)
                raise TCADDebugError(
                    "staged TCAD project is not eligible for development debug; "
                    f"preparation_reason_code={reason_code}"
                ) from error
            try:
                prepared, lease = self._revalidate_and_clamp(
                    session_token=session_token,
                    session=session,
                    worker_id=worker_id,
                    lease=lease,
                    prepared=prepared,
                    include_total_budget=True,
                )
                self._reserve_run(
                    session=session,
                    lease=lease,
                    run_name=run_name,
                    mode=mode,
                    snapshot_ref=snapshot_ref,
                    source_tree_sha256=source_tree_sha256,
                    prepared=prepared,
                )
            except Exception:
                self._cleanup_exchange(session.session_id, run_name)
                raise
            row = self._run_row(session.session_id, run_name)
            assert row is not None

        if row["state"] == "collected":
            return self._stored_response(row)
        if row["state"] == "reaped":
            raise TCADDebugError(
                "TCAD debug run is closed; choose a new run_name within the lease"
            )
        external_run_id = row["external_run_id"]
        if external_run_id is None:
            prepared, lease = self._revalidate_and_clamp(
                session_token=session_token,
                session=session,
                worker_id=worker_id,
                lease=lease,
                prepared=PreparedTCADDebugRun(
                    submission=LocalFileDescriptor.model_validate_json(
                        row["submission_json"], strict=True
                    ),
                    wall_time_seconds=int(row["wall_time_seconds"]),
                ),
                include_total_budget=False,
            )
            self._update_prepared_run(
                session_id=session.session_id,
                run_name=run_name,
                prepared=prepared,
            )
            try:
                submission = self.adapter.prepare_submission(prepared)
                latest, lease = self._revalidate_and_clamp(
                    session_token=session_token,
                    session=session,
                    worker_id=worker_id,
                    lease=lease,
                    prepared=prepared,
                    include_total_budget=False,
                )
                if latest != prepared:
                    prepared = latest
                    self._update_prepared_run(
                        session_id=session.session_id,
                        run_name=run_name,
                        prepared=prepared,
                    )
                    submission = self.adapter.prepare_submission(prepared)
                self._assert_submit_binding(
                    session_token=session_token,
                    session=session,
                    worker_id=worker_id,
                    prepared=prepared,
                )
                self._record_state(
                    session_id=session.session_id,
                    run_name=run_name,
                    state="submitting",
                )
                external_run_id, external_state = self.adapter.submit(submission)
            except Exception as error:
                raise TCADDebugError(
                    "TCAD development debug submission is unavailable"
                ) from error
            external_state = _validated_adapter_state(external_state)
            if (
                not isinstance(external_run_id, str)
                or not external_run_id
                or len(external_run_id) > 256
                or "\x00" in external_run_id
            ):
                raise TCADDebugError(
                    "TCAD development debug returned an invalid private run binding"
                )
            self._record_submission(
                session_id=session.session_id,
                run_name=run_name,
                external_run_id=external_run_id,
                state=external_state,
            )
            self.tasks.record_activity(
                session_token,
                worker_id=worker_id,
                activity="tcad_debug_submitted",
            )
            if external_state not in {"succeeded", "failed", "cancelled"}:
                return _pending_response(run_name, mode, external_state)
        else:
            try:
                external_state = _validated_adapter_state(
                    self.adapter.status(str(external_run_id))
                )
            except Exception as error:
                raise TCADDebugError(
                    "TCAD development debug status is unavailable"
                ) from error
            self._record_state(
                session_id=session.session_id,
                run_name=run_name,
                state=external_state,
            )
            if external_state not in {"succeeded", "failed", "cancelled"}:
                self.tasks.record_activity(
                    session_token,
                    worker_id=worker_id,
                    activity="tcad_debug_polled",
                )
                return _pending_response(run_name, mode, external_state)

        assert external_run_id is not None
        try:
            collected = self.adapter.collect(str(external_run_id))
        except Exception as error:
            raise TCADDebugError(
                "TCAD development debug collection is unavailable"
            ) from error
        response, result_snapshot_ref = self._store_collection(
            session=session,
            task=task,
            run_name=run_name,
            mode=mode,
            collected=collected,
            source_tree_sha256=row["source_tree_sha256"],
        )
        self._record_collection(
            session_id=session.session_id,
            run_name=run_name,
            response=response,
            result_snapshot_ref=result_snapshot_ref,
        )
        self._cleanup_exchange(session.session_id, run_name)
        self.tasks.record_activity(
            session_token,
            worker_id=worker_id,
            activity="tcad_debug_collected",
        )
        return response

    def reconcile(self, *, limit: int = 16) -> dict[str, int]:
        """Boundedly close debug bindings without relying on a worker token."""

        if not 1 <= limit <= 64:
            raise ValueError("TCAD debug reconcile limit must be between 1 and 64")
        with self.tasks._connect() as connection:
            rows = connection.execute(
                """
                SELECT runs.*, leases.expires_at
                FROM tcad_debug_runs AS runs
                JOIN tcad_debug_leases AS leases
                  ON leases.session_id = runs.session_id
                WHERE runs.state NOT IN ('collected', 'reaped')
                ORDER BY runs.updated_at, runs.task_id, runs.run_name
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        counts = {"examined": 0, "cancelled": 0, "collected": 0, "pending": 0}
        for row in rows:
            counts["examined"] += 1
            self.tasks._reconcile_expired(str(row["task_id"]))
            external_run_id = row["external_run_id"]
            state = str(row["state"])
            if external_run_id is None:
                with self.tasks._connect() as connection:
                    task_row = connection.execute(
                        "SELECT state, attempt FROM tasks WHERE task_id = ?",
                        (row["task_id"],),
                    ).fetchone()
                binding_active = (
                    task_row is not None
                    and task_row["state"] == "claimed"
                    and int(task_row["attempt"]) == int(row["attempt"])
                )
                expired = datetime.now(timezone.utc) >= _parse_timestamp(
                    row["expires_at"]
                )
                if state == "submitting":
                    try:
                        prepared = PreparedTCADDebugRun(
                            submission=LocalFileDescriptor.model_validate_json(
                                row["submission_json"], strict=True
                            ),
                            wall_time_seconds=int(row["wall_time_seconds"]),
                        )
                        submission = self.adapter.prepare_submission(prepared)
                        external_run_id, state = self.adapter.submit(submission)
                        state = _validated_adapter_state(state)
                        if (
                            not isinstance(external_run_id, str)
                            or not external_run_id
                            or len(external_run_id) > 256
                            or "\x00" in external_run_id
                        ):
                            raise TCADDebugError(
                                "TCAD debug recovery returned an invalid run binding"
                            )
                        self._record_submission(
                            session_id=str(row["session_id"]),
                            run_name=str(row["run_name"]),
                            external_run_id=external_run_id,
                            state=state,
                        )
                    except Exception:
                        counts["pending"] += 1
                        continue
                elif expired or not binding_active:
                    self._record_state(
                        session_id=str(row["session_id"]),
                        run_name=str(row["run_name"]),
                        state="reaped",
                    )
                    self._cleanup_exchange(
                        str(row["session_id"]), str(row["run_name"])
                    )
                    continue
                else:
                    counts["pending"] += 1
                    continue
            expired = datetime.now(timezone.utc) >= _parse_timestamp(
                row["expires_at"]
            )
            with self.tasks._connect() as connection:
                task_row = connection.execute(
                    "SELECT state, attempt FROM tasks WHERE task_id = ?",
                    (row["task_id"],),
                ).fetchone()
            binding_active = (
                task_row is not None
                and task_row["state"] == "claimed"
                and int(task_row["attempt"]) == int(row["attempt"])
            )
            try:
                if state not in {"succeeded", "failed", "cancelled"}:
                    if expired or not binding_active:
                        state = _validated_adapter_state(
                            self.adapter.cancel(str(external_run_id))
                        )
                        counts["cancelled"] += 1
                    else:
                        state = _validated_adapter_state(
                            self.adapter.status(str(external_run_id))
                        )
                    self._record_state(
                        session_id=str(row["session_id"]),
                        run_name=str(row["run_name"]),
                        state=state,
                    )
                if state not in {"succeeded", "failed", "cancelled"}:
                    counts["pending"] += 1
                    continue
                collected = self.adapter.collect(str(external_run_id))
                task = self.tasks.get_task(str(row["task_id"]))
                session = _ReaperSession(
                    session_id=str(row["session_id"]),
                    task_id=str(row["task_id"]),
                    attempt=int(row["attempt"]),
                )
                response, result_ref = self._store_collection(
                    session=session,
                    task=task,
                    run_name=str(row["run_name"]),
                    mode=str(row["mode"]),
                    collected=collected,
                    source_tree_sha256=row["source_tree_sha256"],
                )
                self._record_collection(
                    session_id=session.session_id,
                    run_name=str(row["run_name"]),
                    response=response,
                    result_snapshot_ref=result_ref,
                )
                self._cleanup_exchange(session.session_id, str(row["run_name"]))
                counts["collected"] += 1
            except Exception:
                # Durable state remains retryable; reconciliation is intentionally
                # bounded and must not erase an external binding on adapter error.
                counts["pending"] += 1
        return counts

    def _revalidate_and_clamp(
        self,
        *,
        session_token: str,
        session: object,
        worker_id: str,
        lease: object,
        prepared: PreparedTCADDebugRun,
        include_total_budget: bool,
    ) -> tuple[PreparedTCADDebugRun, object]:
        current = self.tasks.tokens.verify_session(
            session_token, worker_id=worker_id
        )
        if (
            current.session_id != session.session_id
            or current.task_id != session.task_id
            or current.attempt != session.attempt
        ):
            raise TCADDebugError("TCAD debug session binding changed")
        self.tasks._require_active_claim(session.task_id, session.attempt)
        lease = self._lease(session)
        now = datetime.now(timezone.utc)
        remaining = int((_parse_timestamp(lease["expires_at"]) - now).total_seconds())
        if include_total_budget:
            with self.tasks._connect() as connection:
                usage = connection.execute(
                    """
                    SELECT COALESCE(SUM(wall_time_seconds), 0) AS wall
                    FROM tcad_debug_runs WHERE session_id = ?
                    """,
                    (session.session_id,),
                ).fetchone()
            remaining = min(
                remaining,
                int(lease["max_total_wall_seconds"]) - int(usage["wall"]),
            )
        if remaining < 1:
            raise TCADDebugError("TCAD development debug lease is exhausted")
        try:
            prepared = self.adapter.clamp_wall_time(
                prepared,
                wall_time_seconds=min(prepared.wall_time_seconds, remaining),
            )
        except Exception as error:
            raise TCADDebugError(
                "TCAD development debug resource clamp failed"
            ) from error
        if not 1 <= prepared.wall_time_seconds <= remaining:
            raise TCADDebugError("TCAD debug adapter did not enforce its wall bound")
        return prepared, lease

    def _assert_submit_binding(
        self,
        *,
        session_token: str,
        session: object,
        worker_id: str,
        prepared: PreparedTCADDebugRun,
    ) -> None:
        current = self.tasks.tokens.verify_session(
            session_token, worker_id=worker_id
        )
        if (
            current.session_id != session.session_id
            or current.task_id != session.task_id
            or current.attempt != session.attempt
        ):
            raise TCADDebugError("TCAD debug session binding changed")
        self.tasks._require_active_claim(session.task_id, session.attempt)
        lease = self._lease(session)
        remaining = int(
            (
                _parse_timestamp(lease["expires_at"])
                - datetime.now(timezone.utc)
            ).total_seconds()
        )
        if remaining < prepared.wall_time_seconds:
            raise TCADDebugError(
                "TCAD debug lease cannot cover the prepared solver wall time"
            )

    def _lease(self, session: object):
        now = datetime.now(timezone.utc)
        with self.tasks._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM tcad_debug_leases WHERE session_id = ?",
                (session.session_id,),
            ).fetchone()
            if row is None:
                expires_at = _timestamp(
                    min(
                        _parse_timestamp(session.expires_at),
                        now + timedelta(seconds=_DEBUG_LEASE_SECONDS),
                    )
                )
                connection.execute(
                    """
                    INSERT INTO tcad_debug_leases (
                        session_id, task_id, attempt, created_at, expires_at,
                        max_runs, max_total_wall_seconds
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session.session_id,
                        session.task_id,
                        session.attempt,
                        _timestamp(now),
                        expires_at,
                        _DEBUG_MAX_RUNS,
                        _DEBUG_MAX_TOTAL_WALL_SECONDS,
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM tcad_debug_leases WHERE session_id = ?",
                    (session.session_id,),
                ).fetchone()
            connection.execute("COMMIT")
        if (
            row["task_id"] != session.task_id
            or int(row["attempt"]) != session.attempt
        ):
            raise TCADDebugError("TCAD debug lease binding is inconsistent")
        if now >= _parse_timestamp(row["expires_at"]):
            raise TCADDebugError("TCAD development debug lease has expired")
        return row

    def _snapshot_project(
        self,
        *,
        session: object,
        task: AgentTask,
        capability_ref: ArtifactRef,
    ) -> tuple[bytes, ArtifactRef, tuple[TCADDebugSource, ...], str]:
        try:
            content = self.tasks._read_output_file_for_session(session, task)
            raw, _, _ = self.tasks._validate_complete_output(
                task, attempt=session.attempt, content=content
            )
        except TaskInputError as error:
            details = error.details or (
                {
                    "path": "$.debug.project",
                    "message": str(error),
                    "type": "development_debug_project_rejected",
                },
            )
            self.tasks._store_provisional_snapshot(
                session=session,
                task=task,
                reason="validation_rejected",
                validation_status="rejected",
                files=self.tasks._workspace_snapshot_files(
                    session.session_id, task
                ),
                diagnostics=details,
                development_only=True,
            )
            diagnostic = _bounded_validation_diagnostic(details)
            raise TCADDebugError(
                "staged TCAD project did not pass output validation; "
                "preparation_reason_code=project_output_validation_failed; "
                f"diagnostic={diagnostic}"
            ) from error
        manifest = self.tasks._store_provisional_snapshot(
            session=session,
            task=task,
            reason="development_debug_candidate",
            validation_status="valid",
            files=self.tasks._workspace_snapshot_files(session.session_id, task),
            development_only=True,
        )
        snapshot_ref = self.tasks.provisional_snapshot_ref(
            task_id=task.task_id,
            attempt=session.attempt,
            sequence=manifest.sequence,
        )
        sources = []
        for item in task.inputs:
            if item.artifact_ref == capability_ref or item.exposure == "handoff_only":
                continue
            envelope = self.tasks.artifacts.verify(item.artifact_ref)
            sources.append(
                TCADDebugSource(
                    source_name=item.name,
                    artifact_ref=item.artifact_ref,
                    media_type=envelope.media_type,
                    content=self.tasks.artifacts.read(item.artifact_ref),
                )
            )
        try:
            result = json.loads(raw)
            report = result.get("materialization_report")
            source_tree_sha256 = (
                report.get("source_tree_sha256")
                if isinstance(report, dict)
                else _project_source_tree_sha256(result)
            )
        except (AttributeError, TypeError, json.JSONDecodeError) as error:
            raise TCADDebugError("staged TCAD project is invalid") from error
        if not isinstance(source_tree_sha256, str) or re.fullmatch(
            r"[0-9a-f]{64}", source_tree_sha256
        ) is None:
            raise TCADDebugError(
                "staged TCAD project has an invalid deterministic source digest"
            )
        return raw, snapshot_ref, tuple(sources), source_tree_sha256

    def _reserve_run(
        self,
        *,
        session: object,
        lease: object,
        run_name: str,
        mode: str,
        snapshot_ref: ArtifactRef,
        source_tree_sha256: str,
        prepared: PreparedTCADDebugRun,
    ) -> None:
        with self.tasks._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            task_row = self.tasks._row(connection, session.task_id)
            lease_row = connection.execute(
                "SELECT * FROM tcad_debug_leases WHERE session_id = ?",
                (session.session_id,),
            ).fetchone()
            if (
                task_row["state"] != "claimed"
                or int(task_row["attempt"]) != session.attempt
                or lease_row is None
                or datetime.now(timezone.utc)
                >= _parse_timestamp(lease_row["expires_at"])
            ):
                connection.execute("ROLLBACK")
                raise TCADDebugError(
                    "TCAD debug binding expired before run reservation"
                )
            usage = connection.execute(
                """
                SELECT COUNT(*) AS count,
                       COALESCE(SUM(wall_time_seconds), 0) AS wall
                FROM tcad_debug_runs WHERE session_id = ?
                """,
                (session.session_id,),
            ).fetchone()
            if int(usage["count"]) >= int(lease["max_runs"]):
                raise TCADDebugError("TCAD development debug run limit is exhausted")
            if (
                int(usage["wall"]) + prepared.wall_time_seconds
                > int(lease["max_total_wall_seconds"])
            ):
                raise TCADDebugError(
                    "TCAD development debug total runtime limit is exhausted"
                )
            now = _timestamp()
            connection.execute(
                """
                INSERT INTO tcad_debug_runs (
                    session_id, task_id, attempt, run_name, mode, snapshot_ref_json,
                    source_tree_sha256, submission_json, state, wall_time_seconds,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'prepared', ?, ?, ?)
                """,
                (
                    session.session_id,
                    session.task_id,
                    session.attempt,
                    run_name,
                    mode,
                    snapshot_ref.canonical_json(),
                    source_tree_sha256,
                    prepared.submission.canonical_json(),
                    prepared.wall_time_seconds,
                    now,
                    now,
                ),
            )
            connection.execute("COMMIT")

    def _store_collection(
        self,
        *,
        session: object,
        task: AgentTask,
        run_name: str,
        mode: str,
        collected: CollectedTCADDebugRun,
        source_tree_sha256: object,
    ) -> tuple[dict[str, object], ArtifactRef]:
        if collected.terminal_state not in {"succeeded", "failed", "cancelled"}:
            raise TCADDebugError("TCAD debug terminal state is invalid")
        if type(collected.exit_code) is not int or not -(2**31) <= collected.exit_code < 2**31:
            raise TCADDebugError("TCAD debug exit code is invalid")
        if collected.diagnostic_layer not in {
            "parser",
            "initialization",
            "numerical",
            "output_contract",
            "resource_limit",
            "runtime",
            "complete",
        }:
            raise TCADDebugError("TCAD debug diagnostic layer is invalid")
        if not collected.summary or len(collected.summary.encode("utf-8")) > 2048:
            raise TCADDebugError("TCAD debug summary exceeds its bound")
        if len(collected.log_excerpt.encode("utf-8")) > 8192:
            raise TCADDebugError("TCAD debug log excerpt exceeds its bound")
        source_diagnostic = _validated_source_diagnostic(
            collected.source_diagnostic
        )
        if len(collected.files) > _DEBUG_MAX_FILES:
            raise TCADDebugError("TCAD debug output file count exceeds its bound")
        names: set[str] = set()
        total_bytes = 0
        for item in collected.files:
            _validated_debug_output_name(item.name)
            if (
                not isinstance(item.media_type, str)
                or len(item.media_type) > 255
                or "/" not in item.media_type
            ):
                raise TCADDebugError("TCAD debug output media type is invalid")
            if item.name in names:
                raise TCADDebugError("TCAD debug outputs contain duplicate names")
            names.add(item.name)
            if len(item.content) > _DEBUG_MAX_FILE_BYTES:
                raise TCADDebugError("TCAD debug output file exceeds its bound")
            total_bytes += len(item.content)
        if total_bytes > _DEBUG_MAX_OUTPUT_BYTES:
            raise TCADDebugError("TCAD debug outputs exceed their aggregate bound")
        files = tuple(
            _WorkspaceSnapshotFile(
                relative_path=f"debug/{run_name}/{item.name}",
                media_type=item.media_type,
                content=item.content,
                control_generated=True,
                materialize_on_retry=item.name == "debug.log.txt",
            )
            for item in collected.files
        )
        diagnostic = {
            "path": f"$.debug.{collected.diagnostic_layer}",
            "message": collected.summary,
            "type": f"tcad_debug_{collected.diagnostic_layer}",
        }
        manifest = self.tasks.store_development_debug_snapshot(
            session=session,
            task=task,
            files=files,
            diagnostics=(diagnostic,),
        )
        result_snapshot_ref = self.tasks.provisional_snapshot_ref(
            task_id=task.task_id,
            attempt=session.attempt,
            sequence=manifest.sequence,
        )
        response: dict[str, object] = {
            "run_name": run_name,
            "mode": mode,
            "state": collected.terminal_state,
            "phase": "collected",
            "development_only": True,
            "scientific_claim_admissible": False,
            "diagnostic_layer": collected.diagnostic_layer,
            "summary": collected.summary,
            "log_excerpt": collected.log_excerpt,
            "exit_code": collected.exit_code,
            "outputs": [
                {
                    "name": item.name,
                    "media_type": item.media_type,
                    "size_bytes": len(item.content),
                }
                for item in collected.files
                if item.name != "debug.log.txt"
            ],
        }
        if source_diagnostic is not None:
            response["source_diagnostic"] = source_diagnostic
        response["provisional_context"] = f"snapshot_{manifest.sequence}"
        raw = canonical_json(response)
        if len(raw) > _DEBUG_MAX_RESPONSE_BYTES:
            raise TCADDebugError("TCAD debug diagnostic response exceeds its bound")
        if mode == "preflight" and isinstance(source_tree_sha256, str) and re.fullmatch(
            r"[0-9a-f]{64}", source_tree_sha256
        ):
            report_directory = (
                self.tasks.workspace_root / session.session_id / "deck" / "reports"
            )
            report_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            _write_control_output_file(
                report_directory / "preflight.json",
                canonical_json(
                    {
                        "schema_version": 1,
                        "profile": "tcad.project-preflight.v1",
                        "source_tree_sha256": source_tree_sha256,
                        "mode": "preflight",
                        "terminal_state": collected.terminal_state,
                        "exit_code": collected.exit_code,
                        "diagnostic_layer": collected.diagnostic_layer,
                        "qualified": (
                            collected.terminal_state == "succeeded"
                            and collected.exit_code == 0
                            and collected.diagnostic_layer == "complete"
                        ),
                        "summary": collected.summary,
                    }
                ),
            )
        return response, result_snapshot_ref

    def _run_row(self, session_id: str, run_name: str):
        with self.tasks._connect() as connection:
            return connection.execute(
                """
                SELECT * FROM tcad_debug_runs
                WHERE session_id = ? AND run_name = ?
                """,
                (session_id, run_name),
            ).fetchone()

    def _record_submission(
        self, *, session_id: str, run_name: str, external_run_id: str, state: str
    ) -> None:
        with self.tasks._connect() as connection:
            connection.execute(
                """
                UPDATE tcad_debug_runs
                SET external_run_id = ?, state = ?, updated_at = ?
                WHERE session_id = ? AND run_name = ?
                """,
                (external_run_id, state, _timestamp(), session_id, run_name),
            )

    def _record_state(
        self, *, session_id: str, run_name: str, state: str
    ) -> None:
        with self.tasks._connect() as connection:
            connection.execute(
                """
                UPDATE tcad_debug_runs SET state = ?, updated_at = ?
                WHERE session_id = ? AND run_name = ?
                """,
                (state, _timestamp(), session_id, run_name),
            )

    def _record_collection(
        self,
        *,
        session_id: str,
        run_name: str,
        response: dict[str, object],
        result_snapshot_ref: ArtifactRef,
    ) -> None:
        raw = canonical_json(response)
        with self.tasks._connect() as connection:
            connection.execute(
                """
                UPDATE tcad_debug_runs
                SET state = 'collected', response_json = ?,
                    result_snapshot_ref_json = ?, updated_at = ?
                WHERE session_id = ? AND run_name = ?
                """,
                (
                    raw,
                    result_snapshot_ref.canonical_json(),
                    _timestamp(),
                    session_id,
                    run_name,
                ),
            )

    def _update_prepared_run(
        self,
        *,
        session_id: str,
        run_name: str,
        prepared: PreparedTCADDebugRun,
    ) -> None:
        with self.tasks._connect() as connection:
            connection.execute(
                """
                UPDATE tcad_debug_runs
                SET submission_json = ?, wall_time_seconds = ?, updated_at = ?
                WHERE session_id = ? AND run_name = ?
                  AND external_run_id IS NULL
                """,
                (
                    prepared.submission.canonical_json(),
                    prepared.wall_time_seconds,
                    _timestamp(),
                    session_id,
                    run_name,
                ),
            )

    def _cleanup_exchange(self, session_id: str, run_name: str) -> None:
        run_directory = self.exchange_root / session_id / run_name
        if (
            run_directory.parent.parent != self.exchange_root
            or run_directory.name != run_name
        ):
            raise TCADDebugError("TCAD debug exchange binding is invalid")
        shutil.rmtree(run_directory, ignore_errors=True)
        try:
            run_directory.parent.rmdir()
        except OSError:
            pass

    @staticmethod
    def _stored_response(row: object) -> dict[str, object]:
        raw = row["response_json"]
        if raw is None:
            raise TCADDebugError("collected TCAD debug response is missing")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise TCADDebugError("collected TCAD debug response is invalid")
        return value


def _pending_response(run_name: str, mode: str, state: str) -> dict[str, object]:
    visible = "running" if state in {"accepted", "running"} else state
    return {
        "run_name": run_name,
        "mode": mode,
        "state": visible,
        "phase": "submitted",
        "development_only": True,
        "scientific_claim_admissible": False,
    }


def _project_source_tree_sha256(project: object) -> str:
    if not isinstance(project, dict) or not isinstance(project.get("files"), list):
        raise TypeError("project source files are absent")
    source: list[tuple[str, str]] = []
    for item in project["files"]:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("relative_path"), str)
            or not isinstance(item.get("content"), str)
        ):
            raise TypeError("project source file is invalid")
        source.append((item["relative_path"], item["content"]))
    digest = hashlib.sha256()
    for path, content in sorted(source):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


@dataclass(frozen=True)
class _ReaperSession:
    session_id: str
    task_id: str
    attempt: int


def _validated_debug_output_name(value: str) -> None:
    path = Path(value)
    if (
        len(value) > 512
        or path.is_absolute()
        or not path.parts
        or len(path.parts) > 8
        or "\\" in value
        or any(_OUTPUT_SEGMENT.fullmatch(part) is None for part in path.parts)
    ):
        raise TCADDebugError("TCAD debug output name is unsafe")


def _validated_adapter_state(value: str) -> str:
    if value not in {
        "accepted",
        "running",
        "cancelling",
        "succeeded",
        "failed",
        "cancelled",
    }:
        raise TCADDebugError("TCAD development debug adapter state is invalid")
    return value


def _validated_source_diagnostic(
    value: TCADSourceDiagnostic | None,
) -> dict[str, object] | None:
    if value is None:
        return None
    if value.source_relative_path is not None:
        _validated_debug_output_name(value.source_relative_path)
    if value.reported_line is not None and (
        type(value.reported_line) is not int
        or not 1 <= value.reported_line <= 10_000_000
    ):
        raise TCADDebugError("TCAD debug source diagnostic line is invalid")
    if value.line_basis not in {
        "entrypoint_solver_reported",
        "solver_reported",
        "log_only",
    }:
        raise TCADDebugError("TCAD debug source diagnostic basis is invalid")
    if value.procedure is not None and (
        not value.procedure
        or len(value.procedure.encode("utf-8")) > 256
        or any(character in value.procedure for character in "\r\n\x00")
    ):
        raise TCADDebugError("TCAD debug source diagnostic procedure is invalid")
    if value.procedure_line is not None and (
        type(value.procedure_line) is not int
        or not 1 <= value.procedure_line <= 10_000_000
    ):
        raise TCADDebugError("TCAD debug source diagnostic procedure line is invalid")
    if (
        not value.message
        or len(value.message.encode("utf-8")) > 2048
        or "\x00" in value.message
    ):
        raise TCADDebugError("TCAD debug source diagnostic message is invalid")
    if value.command_excerpt is not None and (
        not value.command_excerpt
        or len(value.command_excerpt.encode("utf-8")) > 1024
        or "\x00" in value.command_excerpt
    ):
        raise TCADDebugError("TCAD debug source diagnostic command is invalid")
    return {
        "source_relative_path": value.source_relative_path,
        "reported_line": value.reported_line,
        "line_basis": value.line_basis,
        "procedure": value.procedure,
        "procedure_line": value.procedure_line,
        "message": value.message,
        "command_excerpt": value.command_excerpt,
    }


def _preparation_reason_code(error: Exception) -> str:
    """Return only fixed public-safe preparation categories, never exception text."""

    current: BaseException | None = error
    seen: set[int] = set()
    for _ in range(6):
        if current is None or id(current) in seen:
            break
        seen.add(id(current))
        reason = _PREPARATION_REASON_CODES.get(str(current))
        if reason is not None:
            return reason
        if current.__class__.__name__ == "ValidationError":
            return "project_schema_invalid"
        current = current.__cause__ or current.__context__
    return "adapter_preparation_rejected"


def _bounded_validation_diagnostic(
    details: tuple[dict[str, str], ...],
) -> str:
    """Expose one useful worker-owned validation error without a large dump."""

    first = details[0] if details else {}
    return json.dumps(
        {
            "path": str(first.get("path", "$.debug.project"))[:192],
            "type": str(first.get("type", "value_error"))[:96],
            "message": str(first.get("message", "output validation failed"))[:384],
            "error_count": len(details),
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


__all__ = [
    "CollectedTCADDebugFile",
    "CollectedTCADDebugRun",
    "PreparedTCADDebugRun",
    "TCADDebugError",
    "TCADDebugService",
    "TCADDebugSource",
    "TCADSourceDiagnostic",
    "TCADDevelopmentDebugAdapter",
]
