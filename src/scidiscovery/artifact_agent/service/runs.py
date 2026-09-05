"""One minimal Run authority for validation, completion and recovery."""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from ...operations.catalog import CompiledCatalog
from ...operations.invoke import (
    BoundOperationCall,
    active_direct_revision_ports,
)
from ...operations.tooling import operation_agent_type
from ...operations.workspace import (
    WorkspaceFinalizationRequest,
    WorkspaceMaterializationRequest,
    WorkspaceProtocolError,
    operation_workspace_hooks,
)
from ..schema.artifact import ArtifactRegistration
from ..schema.common import canonical_json, canonical_sha256
from ..schema.refs import ActorRef, ArtifactRef
from ..schema.run_signal import SchedulerSignal
from .artifacts import ArtifactService
from .local_workspace import (
    OpenWorkspace,
    WorkspaceBackend,
    WorkspaceError,
    WorkspaceInput,
)
from .run_assignment import assignment_json, result_schema_json, revision_draft_json
from .run_current import RunCurrentGuard
from .run_outputs import (
    RunCheckerError,
    RunOutputError,
    ValidatedRunOutput,
    validate_run_output,
)
from .run_records import (
    RunCompletionReceipt,
    RunError,
    RunInputBinding,
    RunNotFound,
    RunSlotBusy,
    RunStateConflict,
    RunStatus,
    completion_receipt_json,
    expired,
    future,
    inputs_json,
    parse_stored_signal,
    status_from_row,
    timestamp,
)
from .scheduler_bindings import SchedulerBindingService


class RunService:
    """The only service allowed to publish an Agent result as scientific data."""

    def __init__(
        self,
        *,
        artifacts: ArtifactService,
        database_path: Path | str,
        service_actor: ActorRef,
        operation_catalog: CompiledCatalog,
        backend: WorkspaceBackend,
        scheduler_bindings: SchedulerBindingService,
    ) -> None:
        self.artifacts = artifacts
        self.database_path = Path(database_path).expanduser().absolute()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.service_actor = service_actor
        self.operation_catalog = operation_catalog
        self.backend = backend
        self.scheduler_bindings = scheduler_bindings
        self.scheduler_database_path = scheduler_bindings.database_path
        self.current = RunCurrentGuard(
            artifacts=artifacts,
            scheduler_database_path=self.scheduler_database_path,
        )
        self._initialize()

    def schedule(
        self,
        bound: BoundOperationCall,
        *,
        instance_id: str,
        output_binding_name: str,
        output_logical_name: str,
        output_revision: int,
        output_binding_fingerprint: str,
        resume_from: str | None = None,
    ) -> str:
        compiled = bound.compiled
        if compiled.spec.executor.kind != "agent":
            raise ValueError("RunService accepts Agent operations only")
        if not self.backend.supports_operation(compiled):
            raise RunError("runtime backend does not support the compiled Operation")
        if any(port.collection is not None for port in compiled.spec.outputs):
            raise RunError("minimal local Run does not yet support output collections")
        if compiled.spec.limits is None:
            raise ValueError("compiled operation has no limits")
        raw_inputs = tuple(
            RunInputBinding(
                port_name=item.port_name,
                source_name=item.source_name,
                artifact_name=item.artifact_name,
                artifact_ref=item.artifact.ref,
                media_type=item.artifact.media_type,
                exposure=item.exposure,
                usage=item.usage,
                require_current=next(
                    port.require_current
                    for port in compiled.spec.inputs
                    if port.name == item.port_name
                ),
            )
            for item in bound.inputs
        )
        for item in raw_inputs:
            self.artifacts.verify(item.artifact_ref)
        run_id = f"run_{uuid.uuid4().hex}"
        created_at = timestamp()
        deadline_at = future(created_at, compiled.spec.limits.timeout_seconds)
        recovery_digest: str | None = None
        with self._connect() as connection:
            self._attach_scheduler(connection)
            connection.execute("BEGIN IMMEDIATE")
            frozen_inputs = self.current.freeze(connection, instance_id, raw_inputs)
            active_revision = active_direct_revision_ports(
                compiled, (item.port_name for item in frozen_inputs)
            )
            revision_base = (
                None
                if active_revision is None
                else next(
                    item.artifact_ref
                    for item in frozen_inputs
                    if item.port_name == active_revision[0].name
                )
            )
            if (
                revision_base is not None
                and compiled.spec.review is not None
                and compiled.spec.review.max_revisions
                and self._revision_successor(
                    connection,
                    instance_id=instance_id,
                    operation_digest=compiled.digest,
                    base_ref=revision_base,
                )
                is not None
            ):
                connection.execute("ROLLBACK")
                raise RunSlotBusy("this revision base already has a successor Run")
            if resume_from is not None:
                source = status_from_row(self._row(connection, resume_from))
                recovery_digest = self._validate_resume(
                    connection,
                    source,
                    compiled.digest,
                    tuple(item.artifact_ref for item in frozen_inputs),
                    compiled.spec.limits.max_attempts,
                )
            request_digest = canonical_sha256(
                {
                    "operation_id": compiled.spec.operation_id,
                    "operation_version": compiled.spec.version,
                    "operation_digest": compiled.digest,
                    "backend": self.backend.backend_id,
                    "backend_version": self.backend.backend_version,
                    "backend_capabilities": self.backend.capabilities,
                    "instance_id": instance_id,
                    "output_binding": {
                        "name": output_binding_name,
                        "logical_name": output_logical_name,
                        "revision": output_revision,
                        "request_fingerprint": output_binding_fingerprint,
                    },
                    "instruction": bound.instruction or "",
                    "inputs": json.loads(inputs_json(frozen_inputs)),
                    "limits": compiled.spec.limits.model_dump(mode="json"),
                    "resume_from": resume_from,
                    "recovery_digest": recovery_digest,
                }
            )
            try:
                connection.execute(
                    """
                    INSERT INTO runs (
                        run_id, instance_id, operation_id, operation_version,
                        operation_digest, agent_type, instruction, inputs_json,
                        backend_id, backend_version, backend_capabilities_json,
                        output_binding_name, output_logical_name,
                        output_revision, output_binding_fingerprint,
                        request_digest, resume_from_run_id,
                        state, created_at, deadline_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                              'queued', ?, ?)
                    """,
                    (
                        run_id,
                        instance_id,
                        compiled.spec.operation_id,
                        compiled.spec.version,
                        compiled.digest,
                        operation_agent_type(compiled),
                        bound.instruction or "",
                        inputs_json(frozen_inputs),
                        self.backend.backend_id,
                        self.backend.backend_version,
                        canonical_json(self.backend.capabilities),
                        output_binding_name,
                        output_logical_name,
                        output_revision,
                        output_binding_fingerprint,
                        request_digest,
                        resume_from,
                        created_at,
                        deadline_at,
                    ),
                )
            except sqlite3.IntegrityError as error:
                connection.execute("ROLLBACK")
                raise RunSlotBusy(
                    "this compiled Operation already has an unopened or running Run"
                ) from error
            connection.execute("COMMIT")
        try:
            materialized_inputs = tuple(
                WorkspaceInput(
                    name=item.source_name,
                    media_type=item.media_type,
                    content=self.artifacts.read(item.artifact_ref),
                )
                for item in frozen_inputs
                if item.exposure != "handoff_only"
            )
            input_bytes = {item.name: item.content for item in materialized_inputs}
            direct_revision = active_direct_revision_ports(
                compiled, (item.port_name for item in frozen_inputs)
            )
            workspace_hooks = operation_workspace_hooks(compiled)
            revision_workspace_mode = _revision_workspace_mode(
                direct_revision, workspace_hooks
            )
            initial_output = (
                revision_draft_json(bound, input_bytes)
                if revision_workspace_mode == "result_copy"
                else None
            )
            if (
                initial_output is not None
                and len(initial_output) > compiled.spec.limits.max_output_bytes
            ):
                raise RunError("revision draft exceeds the compiled output limit")
            workspace = self.backend.prepare(
                run_id=run_id,
                inputs=materialized_inputs,
                assignment=assignment_json(
                    bound,
                    frozen_inputs,
                    tool_names=self.backend.assignment_tool_names(compiled),
                    recovery_relative_path=(
                        "recovery-draft" if recovery_digest is not None else None
                    ),
                    revision_workspace_mode=revision_workspace_mode,
                ),
                result_schema=result_schema_json(compiled),
                recovery_digest=recovery_digest,
                initial_output=initial_output,
            )
            self._materialize_workspace(compiled, run_id, workspace)
        except Exception as error:
            self.record_failure(
                run_id,
                reason=f"workspace preparation failed: {type(error).__name__}",
                expected_state="queued",
                expected_last_activity_at=None,
            )
            raise RunError("local workspace preparation failed") from error
        return run_id

    def revision_successor(
        self, *, instance_id: str, operation_digest: str, base_ref: ArtifactRef
    ) -> RunStatus | None:
        with self._connect() as connection:
            return self._revision_successor(
                connection,
                instance_id=instance_id,
                operation_digest=operation_digest,
                base_ref=base_ref,
            )

    @staticmethod
    def _revision_successor(
        connection: sqlite3.Connection,
        *,
        instance_id: str,
        operation_digest: str,
        base_ref: ArtifactRef,
    ) -> RunStatus | None:
        rows = connection.execute(
            """
            SELECT * FROM runs
            WHERE instance_id = ? AND operation_digest = ? AND state != 'failed'
            ORDER BY created_at
            """,
            (instance_id, operation_digest),
        )
        return next(
            (
                status
                for status in map(status_from_row, rows)
                if any(
                    item.usage == "revision_base" and item.artifact_ref == base_ref
                    for item in status.inputs
                )
            ),
            None,
        )

    def input_is_current(
        self,
        *,
        instance_id: str,
        artifact_name: str,
        artifact_ref: ArtifactRef,
    ) -> bool:
        with self._connect() as connection:
            self._attach_scheduler(connection)
            return self.current.input_is_current(
                connection,
                instance_id=instance_id,
                artifact_name=artifact_name,
                artifact_ref=artifact_ref,
            )

    def open(
        self, *, operation_id: str, operation_digest: str
    ) -> tuple[RunStatus, OpenWorkspace]:
        return self._open_exact(
            operation_id=operation_id,
            operation_digest=operation_digest,
            allow_running=False,
        )

    def reopen(
        self, *, operation_id: str, operation_digest: str
    ) -> tuple[RunStatus, OpenWorkspace]:
        """Open the exact slot or reattach its running Run after transport restart."""

        return self._open_exact(
            operation_id=operation_id,
            operation_digest=operation_digest,
            allow_running=True,
        )

    def _open_exact(
        self,
        *,
        operation_id: str,
        operation_digest: str,
        allow_running: bool,
    ) -> tuple[RunStatus, OpenWorkspace]:
        now = timestamp()
        expired_run: tuple[str, str, str | None] | None = None
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM runs
                WHERE operation_id = ? AND operation_digest = ?
                  AND state IN ('queued', 'running')
                ORDER BY created_at LIMIT 1
                """,
                (operation_id, operation_digest),
            ).fetchone()
            if row is None:
                connection.execute("ROLLBACK")
                raise RunStateConflict("no exact queued Run is available")
            if row["state"] == "running" and not allow_running:
                connection.execute("ROLLBACK")
                raise RunStateConflict("no exact queued Run is available")
            if expired(str(row["deadline_at"])):
                expired_run = (
                    str(row["run_id"]),
                    str(row["state"]),
                    row["last_activity_at"],
                )
                connection.execute("ROLLBACK")
            elif row["state"] == "running":
                run_id = str(row["run_id"])
                connection.execute("COMMIT")
            else:
                connection.execute(
                    """
                    UPDATE runs SET state = 'running', started_at = ?, last_activity_at = ?
                    WHERE run_id = ? AND state = 'queued'
                    """,
                    (now, now, row["run_id"]),
                )
                connection.execute("COMMIT")
                run_id = str(row["run_id"])
        if expired_run is not None:
            self.record_failure(
                expired_run[0],
                reason="Run deadline expired before open",
                expected_state=expired_run[1],
                expected_last_activity_at=expired_run[2],
                timed_out=True,
            )
            raise RunStateConflict("queued Run has expired")
        try:
            workspace = self.backend.open(run_id)
        except Exception as error:
            value = self.status(run_id)
            self.record_failure(
                run_id,
                reason="prepared workspace is unavailable",
                expected_state="running",
                expected_last_activity_at=value.last_activity_at,
            )
            raise RunStateConflict("prepared workspace is unavailable") from error
        return self.status(run_id), workspace

    def heartbeat(self, run_id: str) -> RunStatus:
        value = self._require_running(run_id)
        self.backend.heartbeat(run_id)
        now = timestamp()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE runs SET last_activity_at = ?
                WHERE run_id = ? AND state = 'running' AND last_activity_at IS ?
                """,
                (now, run_id, value.last_activity_at),
            )
            if cursor.rowcount != 1:
                raise RunStateConflict("Run activity changed concurrently")
        return self.status(run_id)

    def submit(self, run_id: str) -> tuple[str, tuple[dict[str, str], ...]]:
        value = self.status(run_id)
        if value.state == "completed":
            return "completed", ()
        value = self._require_running(run_id)
        try:
            sealed, validated = self._validated_candidate(value)
        except RunCheckerError as error:
            self.record_failure(
                run_id,
                reason=f"compiled output checker failed: {error}",
                expected_state="running",
                expected_last_activity_at=value.last_activity_at,
            )
            return "failed", ()
        except (RunOutputError, WorkspaceError) as error:
            details = getattr(error, "details", ()) or (
                {"path": "$", "message": str(error), "type": "value_error"},
            )
            self.record_activity(run_id, "output_rejected")
            return "rejected", tuple(details)
        self._accept_candidate(run_id, sealed.digest)
        output = self._register_candidate(value, validated, sealed.digest)
        self._complete(run_id, sealed.digest, output, validated.signal)
        return "completed", ()

    def validate_candidate(self, run_id: str) -> ValidatedRunOutput:
        value = self._require_running(run_id)
        _, validated = self._validated_candidate(value)
        return validated

    def record_failure(
        self,
        run_id: str,
        *,
        reason: str,
        expected_state: str,
        expected_last_activity_at: str | None,
        timed_out: bool = False,
    ) -> RunStatus:
        if expected_state not in {"queued", "running"}:
            raise ValueError("failure precondition state is invalid")
        value = self.status(run_id)
        if value.state == "failed":
            return self._finish_failed_workspace(value)
        if value.state != expected_state or value.last_activity_at != expected_last_activity_at:
            raise RunStateConflict("Run failure compare-and-set failed")
        if timed_out and not expired(value.deadline_at):
            raise RunStateConflict("Run deadline has not expired")
        compiled = self._compiled(value)
        assert compiled.spec.limits is not None
        sealed = None
        try:
            sealed = self.backend.seal(
                run_id,
                max_files=compiled.spec.limits.max_files,
                max_bytes=compiled.spec.limits.max_output_bytes,
                expected_digest=value.accepted_candidate_digest,
            )
        except Exception:
            pass
        now = timestamp()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE runs SET state = 'failed', reason = ?, completed_at = ?,
                    recovery_candidate_digest = ?
                WHERE run_id = ? AND state = ? AND last_activity_at IS ?
                """,
                (
                    reason[:4096],
                    now,
                    None if sealed is None else sealed.digest,
                    run_id,
                    expected_state,
                    expected_last_activity_at,
                ),
            )
            if cursor.rowcount != 1:
                connection.execute("ROLLBACK")
                raise RunStateConflict("Run failure compare-and-set failed")
            connection.execute("COMMIT")
        return self._finish_failed_workspace(self.status(run_id))

    def _finish_failed_workspace(self, value: RunStatus) -> RunStatus:
        if value.state != "failed":
            raise RunStateConflict("Run is not failed")
        if value.recovery_draft is not None:
            return value
        compiled = self._compiled(value)
        assert compiled.spec.limits is not None
        try:
            draft = self.backend.discard(
                value.run_id,
                preserve_digest=value.recovery_candidate_digest,
                max_files=compiled.spec.limits.max_files,
                max_bytes=compiled.spec.limits.max_output_bytes,
            )
        except Exception as error:
            raise RunError("failed Run workspace isolation is incomplete") from error
        if draft is not None:
            manifest = canonical_json(
                {
                    "source_run_id": value.run_id,
                    "source_request_digest": value.request_digest,
                    "operation_digest": value.operation_digest,
                    "input_refs": [
                        item.artifact_ref.model_dump(mode="json") for item in value.inputs
                    ],
                    "backend": draft.backend,
                    "backend_version": draft.backend_version,
                    "draft_digest": draft.digest,
                    "files": [
                        {
                            "relative_path": item.relative_path,
                            "media_type": item.media_type,
                            "size_bytes": item.size_bytes,
                            "sha256": item.sha256,
                        }
                        for item in draft.files
                    ],
                    "reason": value.reason,
                }
            )
            with self._connect() as connection:
                connection.execute(
                    """
                    UPDATE runs SET recovery_draft_json = ?
                    WHERE run_id = ? AND state = 'failed' AND recovery_draft_json IS NULL
                    """,
                    (manifest, value.run_id),
                )
        return self.status(value.run_id)

    def fail(self, run_id: str, *, reason: str) -> RunStatus:
        value = self.status(run_id)
        return self.record_failure(
            run_id,
            reason=reason,
            expected_state=value.state,
            expected_last_activity_at=value.last_activity_at,
        )

    def status(self, run_id: str) -> RunStatus:
        """Pure read: observing an expired Run never changes control state."""

        with self._connect() as connection:
            return status_from_row(self._row(connection, run_id))

    def list(self, *, instance_id: str, state: str | None = None) -> tuple[RunStatus, ...]:
        query = "SELECT * FROM runs WHERE instance_id = ?"
        values: list[Any] = [instance_id]
        if state is not None:
            query += " AND state = ?"
            values.append(state)
        query += " ORDER BY created_at DESC"
        with self._connect() as connection:
            rows = connection.execute(query, values).fetchall()
        return tuple(status_from_row(row) for row in rows)

    def completed_for_output(self, artifact_ref: ArtifactRef) -> RunStatus | None:
        """Return the unique completed Run that registered this exact output."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM runs
                WHERE state = 'completed' AND output_ref_json = ?
                """,
                (artifact_ref.canonical_json(),),
            ).fetchall()
        if len(rows) > 1:
            raise RunStateConflict("multiple Runs claim the same exact output")
        return None if not rows else status_from_row(rows[0])

    def record_activity(self, run_id: str, activity: str) -> None:
        if not activity or len(activity) > 128:
            raise ValueError("Run activity is invalid")
        value = self._require_running(run_id)
        now = timestamp()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE runs SET last_activity_at = ?
                WHERE run_id = ? AND state = 'running' AND last_activity_at IS ?
                """,
                (now, run_id, value.last_activity_at),
            )
            if cursor.rowcount != 1:
                connection.execute("ROLLBACK")
                raise RunStateConflict("Run activity changed concurrently")
            connection.execute(
                "INSERT INTO run_activity (run_id, activity, recorded_at) VALUES (?, ?, ?)",
                (run_id, activity, now),
            )
            connection.execute("COMMIT")

    def successful_tools(self, run_id: str) -> tuple[str, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT activity FROM run_activity
                WHERE run_id = ? AND activity LIKE 'tool_succeeded:%'
                """,
                (run_id,),
            ).fetchall()
        return tuple(sorted({str(row["activity"]).partition(":")[2] for row in rows}))

    def signal_for_output(self, artifact_ref: ArtifactRef) -> SchedulerSignal | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM runs
                WHERE state = 'completed' AND output_ref_json = ?
                """,
                (artifact_ref.canonical_json(),),
            ).fetchone()
        if row is None:
            return None
        status = status_from_row(row)
        try:
            self._compiled(status)
        except RunStateConflict:
            return None
        return status.signal

    def is_exact_reviewer_output(
        self,
        artifact_ref: ArtifactRef,
        *,
        reviewer_operation: str,
        reviewer_input_port: str,
        accepted_verdicts: tuple[str, ...] | None,
        subject_ref: ArtifactRef,
    ) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM runs
                WHERE state = 'completed' AND output_ref_json = ?
                """,
                (artifact_ref.canonical_json(),),
            ).fetchone()
        if row is None or str(row["operation_id"]) != reviewer_operation:
            return False
        status = status_from_row(row)
        try:
            self._compiled(status)
        except RunStateConflict:
            return False
        return bool(
            status.signal is not None
            and (accepted_verdicts is None or status.signal.verdict in accepted_verdicts)
            and any(
                item.port_name == reviewer_input_port and item.artifact_ref == subject_ref
                for item in status.inputs
            )
        )

    def _validated_candidate(
        self, value: RunStatus
    ) -> tuple[Any, ValidatedRunOutput]:
        compiled = self._compiled(value)
        assert compiled.spec.limits is not None
        if value.accepted_candidate_digest is None:
            self._finalize_workspace(compiled, value.run_id)
        sealed = self.backend.seal(
            value.run_id,
            max_files=compiled.spec.limits.max_files,
            max_bytes=compiled.spec.limits.max_output_bytes,
            expected_digest=value.accepted_candidate_digest,
        )
        validated = validate_run_output(
            compiled,
            sealed,
            input_source_ports={item.source_name: item.port_name for item in value.inputs},
            input_bytes={
                item.source_name: self.artifacts.read(item.artifact_ref)
                for item in value.inputs
            },
        )
        return sealed, validated

    def _materialize_workspace(
        self, compiled: Any, run_id: str, workspace: OpenWorkspace
    ) -> None:
        materializer = operation_workspace_hooks(compiled).get(
            "workspace_materializer"
        )
        if materializer is None:
            return
        recovery = workspace.root / "recovery-draft"
        try:
            result = materializer(
                WorkspaceMaterializationRequest(
                    operation_id=compiled.spec.operation_id,
                    workspace=workspace.root,
                    input_paths=workspace.input_paths,
                    provisional_roots=(recovery,) if recovery.is_dir() else (),
                    edit_protocol=getattr(self.backend, "edit_protocol", "native"),
                )
            )
            payload = canonical_json(
                {
                    "schema_version": 1,
                    "name": result.manifest_name,
                    "manifest": dict(result.manifest),
                    "paths": dict(result.paths),
                    "read_paths": list(result.read_paths),
                    "patch_contract": dict(result.patch_contract),
                }
            )
            writer = getattr(self.backend, "write_domain_workspace", None)
            if not callable(writer):
                raise WorkspaceError(
                    "workspace backend cannot publish a domain workspace"
                )
            writer(run_id, payload)
        except WorkspaceProtocolError as error:
            raise RunError(str(error)) from error

    def _finalize_workspace(self, compiled: Any, run_id: str) -> None:
        finalizer = operation_workspace_hooks(compiled).get("workspace_finalizer")
        if finalizer is None:
            return
        workspace = self.backend.open(run_id)
        try:
            raw = finalizer(
                WorkspaceFinalizationRequest(
                    operation_id=compiled.spec.operation_id,
                    workspace=workspace.root,
                    input_paths=workspace.input_paths,
                    output_limit_bytes=compiled.spec.limits.max_output_bytes,
                )
            )
            writer = getattr(self.backend, "write_primary_output", None)
            if not callable(writer):
                raise WorkspaceError(
                    "workspace backend cannot publish a finalized output"
                )
            writer(run_id, raw)
        except WorkspaceProtocolError as error:
            raise RunOutputError(str(error), details=error.details) from error

    def _accept_candidate(self, run_id: str, digest: str) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row(connection, run_id)
            if row["state"] != "running":
                connection.execute("ROLLBACK")
                raise RunStateConflict("Run is no longer running")
            accepted = row["accepted_candidate_digest"]
            if accepted is not None and str(accepted) != digest:
                connection.execute("ROLLBACK")
                raise RunStateConflict("Run already accepted a different candidate")
            connection.execute(
                """
                UPDATE runs SET accepted_candidate_digest = ?
                WHERE run_id = ? AND accepted_candidate_digest IS NULL
                """,
                (digest, run_id),
            )
            connection.execute("COMMIT")

    def _register_candidate(
        self,
        value: RunStatus,
        validated: ValidatedRunOutput,
        candidate_digest: str,
    ) -> ArtifactRef:
        compiled = self._compiled(value)
        return self.artifacts.register(
            validated.content,
            ArtifactRegistration(
                kind=validated.kind,
                schema_id=validated.schema_id,
                payload_schema_version=validated.payload_schema_version,
                media_type=validated.media_type,
                creator=ActorRef(actor_id=value.agent_type, actor_type="agent_worker"),
                parent_refs=tuple(item.artifact_ref for item in value.inputs),
                labels={
                    "operation_id": value.operation_id,
                    "operation_version": value.operation_version,
                    "operation_digest": value.operation_digest,
                    "operation_output_port": validated.output_port,
                    "operation_consequence": compiled.spec.consequence,
                    **(
                        {"scientific_claim_admissible": "false"}
                        if (
                            compiled.spec.consequence == "explore"
                            or compiled.spec.catalog_scope == "internal"
                        )
                        else {}
                    ),
                },
                confidentiality="run_private",
            ),
            idempotency_key=f"run:{value.run_id}:candidate:{candidate_digest}",
        ).ref

    def _complete(
        self,
        run_id: str,
        candidate_digest: str,
        output: ArtifactRef,
        signal: SchedulerSignal,
    ) -> RunCompletionReceipt:
        completed_at = timestamp()
        with self._connect() as connection:
            self._attach_scheduler(connection)
            connection.execute("BEGIN IMMEDIATE")
            row = self._row(connection, run_id)
            value = status_from_row(row)
            if value.state == "completed":
                if value.output_ref != output or value.completion_receipt is None:
                    connection.execute("ROLLBACK")
                    raise RunStateConflict("Run completion receipt is inconsistent")
                connection.execute("ROLLBACK")
                return value.completion_receipt
            if value.state != "running" or value.accepted_candidate_digest != candidate_digest:
                connection.execute("ROLLBACK")
                raise RunStateConflict("Run is not completing its accepted candidate")
            anchors = tuple(
                sorted(
                    {anchor for item in value.inputs for anchor in item.current_anchors},
                    key=lambda item: (item.kind, item.logical_name),
                )
            )
            head_advance = (
                "stale_rejected"
                if anchors and not self.current.run_is_current(connection, value)
                else "not_requested"
            )
            receipt = RunCompletionReceipt(
                candidate_digest=candidate_digest,
                output_ref=output,
                head_advance=head_advance,
                current_anchors=anchors,
                completed_at=completed_at,
            )
            self.scheduler_bindings.bind_in_connection(
                connection,
                instance=value.instance_id,
                namespace="artifact",
                name=value.output_binding_name,
                logical_name=value.output_logical_name,
                revision=value.output_revision,
                object_id=output.artifact_id,
                request_fingerprint=value.output_binding_fingerprint,
                attached=True,
            )
            cursor = connection.execute(
                """
                UPDATE runs SET state = 'completed', output_ref_json = ?,
                    signal_json = ?, completion_receipt_json = ?, completed_at = ?,
                    last_activity_at = ?
                WHERE run_id = ? AND state = 'running'
                  AND accepted_candidate_digest = ?
                """,
                (
                    output.canonical_json(),
                    signal.canonical_json(),
                    completion_receipt_json(receipt),
                    completed_at,
                    completed_at,
                    run_id,
                    candidate_digest,
                ),
            )
            if cursor.rowcount != 1:
                connection.execute("ROLLBACK")
                raise RunStateConflict("Run completion compare-and-set failed")
            connection.execute("COMMIT")
        return receipt

    def _require_running(self, run_id: str) -> RunStatus:
        value = self.status(run_id)
        if value.state != "running":
            raise RunStateConflict(f"Run is not running: {value.state}")
        if expired(value.deadline_at):
            raise RunStateConflict("Run deadline expired; record failure explicitly")
        return value

    def _compiled(self, value: RunStatus) -> Any:
        try:
            compiled = self.operation_catalog.operation(value.operation_id)
        except KeyError as error:
            raise RunStateConflict("Run operation is no longer installed") from error
        if compiled.spec.version != value.operation_version or compiled.digest != value.operation_digest:
            raise RunStateConflict("Run operation contract changed")
        return compiled

    def validate_resume(
        self,
        source_run_id: str,
        *,
        operation_digest: str,
        input_refs: tuple[ArtifactRef, ...],
        max_attempts: int,
    ) -> str:
        """Validate the exact recovery source used by preflight and schedule."""

        with self._connect() as connection:
            return self._validate_resume(
                connection,
                status_from_row(self._row(connection, source_run_id)),
                operation_digest,
                input_refs,
                max_attempts,
            )

    def recovery_available(self, value: RunStatus) -> bool:
        """Report whether this failed Run remains a valid recovery source."""

        if value.state != "failed" or value.recovery_draft is None:
            return False
        try:
            compiled = self._compiled(value)
            assert compiled.spec.limits is not None
            if (
                value.backend_id != self.backend.backend_id
                or value.backend_version != self.backend.backend_version
                or value.backend_capabilities != self.backend.capabilities
                or not self.backend.supports_operation(compiled)
            ):
                return False
            self.validate_resume(
                value.run_id,
                operation_digest=compiled.digest,
                input_refs=tuple(item.artifact_ref for item in value.inputs),
                max_attempts=compiled.spec.limits.max_attempts,
            )
        except (RunError, KeyError, ValueError):
            return False
        return True

    def _validate_resume(
        self,
        connection: sqlite3.Connection,
        source: RunStatus,
        operation_digest: str,
        input_refs: tuple[ArtifactRef, ...],
        max_attempts: int,
    ) -> str:
        digest = self._recovery_digest(source, operation_digest, input_refs)
        root_run_id = self._recovery_root_id(connection, source.run_id)
        attempts = connection.execute(
            """
            WITH RECURSIVE recovery_chain(run_id) AS (
                SELECT run_id FROM runs WHERE run_id = ?
                UNION
                SELECT child.run_id
                FROM runs AS child
                JOIN recovery_chain AS parent
                  ON child.resume_from_run_id = parent.run_id
            )
            SELECT COUNT(*) FROM recovery_chain
            """,
            (root_run_id,),
        ).fetchone()
        if attempts is None or int(attempts[0]) >= max_attempts:
            raise RunStateConflict("recovery attempt limit reached")
        return digest
    def _recovery_root_id(
        self, connection: sqlite3.Connection, source_run_id: str
    ) -> str:
        current = source_run_id
        seen: set[str] = set()
        while True:
            if current in seen:
                raise RunStateConflict("recovery chain is cyclic")
            seen.add(current)
            row = self._row(connection, current)
            parent = row["resume_from_run_id"]
            if parent is None:
                return current
            current = str(parent)

    @staticmethod
    def _recovery_digest(
        source: RunStatus,
        operation_digest: str,
        input_refs: tuple[ArtifactRef, ...],
    ) -> str:
        if source.state != "failed" or source.recovery_draft is None:
            raise RunStateConflict("source Run has no recovery draft")
        if source.operation_digest != operation_digest:
            raise RunStateConflict("recovery Operation digest differs")
        if tuple(item.artifact_ref for item in source.inputs) != input_refs:
            raise RunStateConflict("recovery inputs differ")
        digest = source.recovery_draft.get("draft_digest")
        if not isinstance(digest, str):
            raise RunStateConflict("recovery draft digest is invalid")
        return digest

    @staticmethod
    def _row(connection: sqlite3.Connection, run_id: str) -> sqlite3.Row:
        row = connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise RunNotFound("Run does not exist")
        return row

    def _attach_scheduler(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            "ATTACH DATABASE ? AS scheduler_control",
            (str(self.scheduler_database_path),),
        )

    def _initialize(self) -> None:
        with self._connect() as connection:
            mode = connection.execute("PRAGMA journal_mode = DELETE").fetchone()
            if mode is None or str(mode[0]).lower() != "delete":
                raise RunError(
                    "Run database cannot provide atomic attached commits"
                )
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    instance_id TEXT NOT NULL,
                    operation_id TEXT NOT NULL,
                    operation_version TEXT NOT NULL,
                    operation_digest TEXT NOT NULL,
                    agent_type TEXT NOT NULL,
                    instruction TEXT NOT NULL,
                    inputs_json BLOB NOT NULL,
                    backend_id TEXT NOT NULL,
                    backend_version TEXT NOT NULL,
                    backend_capabilities_json BLOB NOT NULL,
                    output_binding_name TEXT NOT NULL,
                    output_logical_name TEXT NOT NULL,
                    output_revision INTEGER NOT NULL,
                    output_binding_fingerprint TEXT NOT NULL,
                    request_digest TEXT NOT NULL,
                    resume_from_run_id TEXT,
                    state TEXT NOT NULL CHECK(state IN ('queued','running','completed','failed')),
                    accepted_candidate_digest TEXT,
                    output_ref_json BLOB,
                    signal_json BLOB,
                    completion_receipt_json BLOB,
                    reason TEXT,
                    recovery_candidate_digest TEXT,
                    recovery_draft_json BLOB,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    deadline_at TEXT NOT NULL,
                    completed_at TEXT,
                    last_activity_at TEXT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_run_per_operation
                    ON runs(operation_digest) WHERE state IN ('queued','running');
                CREATE TABLE IF NOT EXISTS run_activity (
                    run_id TEXT NOT NULL,
                    activity TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(run_id)
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def _revision_workspace_mode(
    direct_revision: object | None, workspace_hooks: object
) -> str | None:
    if direct_revision is None:
        return None
    return (
        "domain_workspace"
        if {
            "workspace_materializer",
            "workspace_finalizer",
        }.issubset(workspace_hooks)
        else "result_copy"
    )


__all__ = [
    "RunError",
    "RunInputBinding",
    "RunNotFound",
    "RunService",
    "RunSlotBusy",
    "RunStateConflict",
    "RunStatus",
]
