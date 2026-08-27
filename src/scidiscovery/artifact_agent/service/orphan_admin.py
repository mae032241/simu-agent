"""Administrator-only cleanup of control records without instance ownership."""

from __future__ import annotations

from dataclasses import dataclass
import re
import sqlite3
from pathlib import Path

from pydantic import ValidationError

from ..audit import verify_artifacts
from ..schema.refs import ArtifactRef
from .approvals import ApprovalService
from .artifacts import ArtifactService
from .executions import ExecutionService
from .maintenance import (
    PrivatePathError,
    remove_private_directory,
    remove_private_file,
    validate_private_directory,
    validate_private_file,
)
from .scheduler_bindings import SchedulerBindingService
from .tasks import TaskService


CONFIRM_ORPHAN_CLEANUP = "delete-orphan-state"


class OrphanAdministrationError(RuntimeError):
    pass


class OrphanCleanupBlocked(OrphanAdministrationError):
    pass


@dataclass(frozen=True)
class OrphanCleanupPlan:
    orphan_task_ids: tuple[str, ...]
    orphan_approval_ids: tuple[str, ...]
    orphan_execution_ids: tuple[str, ...]
    artifact_refs: tuple[ArtifactRef, ...]
    stale_workspace_names: tuple[str, ...]
    stale_exchange_names: tuple[str, ...]
    stale_executor_run_names: tuple[str, ...]
    stale_submission_names: tuple[str, ...]
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class OrphanCleanupReceipt:
    deleted_tasks: int
    deleted_approvals: int
    deleted_executions: int
    deleted_artifact_registrations: int
    deleted_workspaces: int
    deleted_exchange_directories: int
    deleted_executor_runs: int
    deleted_submission_markers: int
    database_integrity_ok: bool
    artifact_integrity_ok: bool
    remaining_cas_orphans: int


class OrphanAdministrationService:
    """Plan and execute conservative cleanup outside instance ownership."""

    def __init__(
        self,
        *,
        artifacts: ArtifactService,
        approvals: ApprovalService,
        bindings: SchedulerBindingService,
        tasks: TaskService,
        executions: ExecutionService,
        executor_result_root: Path | str,
    ) -> None:
        self.artifacts = artifacts
        self.approvals = approvals
        self.bindings = bindings
        self.tasks = tasks
        self.executions = executions
        self.executor_result_root = Path(executor_result_root).expanduser().absolute()

    def plan(self) -> OrphanCleanupPlan:
        task_states = _state_inventory(
            self.tasks.database_path, "tasks", "task_id", "state"
        )
        approval_states = _state_inventory(
            self.approvals.database_path,
            "approval_requests",
            "approval_id",
            "status",
        )
        execution_rows = _execution_inventory(self.executions.database_path)
        protected = _protected_control_ids(self.bindings.database_path)

        orphan_tasks = tuple(
            sorted(set(task_states) - protected["task"])
        )
        orphan_approvals = tuple(
            sorted(set(approval_states) - protected["approval"])
        )
        orphan_executions = tuple(
            sorted(set(execution_rows) - protected["execution"])
        )

        blockers: list[str] = []
        active_tasks = sum(
            task_states[value] in {"dispatched", "claimed", "finalizing"}
            for value in orphan_tasks
        )
        if active_tasks:
            blockers.append(f"存在 {active_tasks} 个无实例归属的活动任务")
        active_debug_tasks = set(
            self.tasks.active_development_debug_tasks(
                task_ids=orphan_tasks
            )
        )
        if active_debug_tasks:
            blockers.append(
                f"存在 {len(active_debug_tasks)} 个尚未关闭开发调试执行的无实例任务"
            )
        unsafe_executions = sum(
            execution_rows[value][0]
            in {"submitted", "running", "cancelling", "succeeded", "failed", "cancelled"}
            for value in orphan_executions
        )
        if unsafe_executions:
            blockers.append(
                f"存在 {unsafe_executions} 个仍在运行或终态尚未采集的无实例归属执行"
            )

        retained_tasks = set(task_states) - set(orphan_tasks)
        for task_id in retained_tasks:
            if set(self.tasks.get_task(task_id).dependency_task_ids) & set(orphan_tasks):
                blockers.append("保留任务依赖无实例归属任务")
                break

        workspace_names, unexpected_workspaces = _directory_children(
            self.tasks.workspace_root, r"ses_[0-9a-f]{32}"
        )
        active_workspace_names = _active_workspace_names(
            self.tasks.database_path, task_states
        )
        stale_workspaces = tuple(sorted(set(workspace_names) - active_workspace_names))
        if unexpected_workspaces:
            blockers.append(
                f"Worker 运行目录包含 {len(unexpected_workspaces)} 个无法识别的条目"
            )

        exchange_names, unexpected_exchange = _directory_children(
            self.executions.exchange_root, r"exe_[0-9a-f]{32}"
        )
        protected_exchange = {
            execution_id
            for execution_id, (state, _) in execution_rows.items()
            if state in {"authorized", "submitted", "running", "cancelling"}
        }
        stale_exchange = tuple(sorted(set(exchange_names) - protected_exchange))
        if unexpected_exchange:
            blockers.append(
                f"执行交换目录包含 {len(unexpected_exchange)} 个无法识别的条目"
            )

        run_root = self.executor_result_root / "runs"
        run_names, unexpected_runs = _directory_children(
            run_root, r"run_[0-9a-f]{32}"
        )
        orphan_execution_set = set(orphan_executions)
        protected_runs = {
            external_run_id
            for execution_id, (state, external_run_id) in execution_rows.items()
            if execution_id not in orphan_execution_set
            and external_run_id is not None
            and state not in {"collected", "abandoned"}
        }
        stale_runs = tuple(sorted(set(run_names) - protected_runs))
        if unexpected_runs:
            blockers.append(
                f"执行结果目录包含 {len(unexpected_runs)} 个无法识别的条目"
            )

        submission_root = self.executor_result_root / "submissions"
        submission_names, unexpected_submissions = _file_children(
            submission_root, r"[0-9a-f]{64}\.json"
        )
        if any(state == "authorized" for state, _ in execution_rows.values()):
            stale_submissions: tuple[str, ...] = ()
        else:
            stale_submissions = tuple(sorted(submission_names))
        if unexpected_submissions:
            blockers.append(
                f"执行提交目录包含 {len(unexpected_submissions)} 个无法识别的条目"
            )

        artifact_refs = self._artifact_deletion_refs(
            orphan_task_ids=set(orphan_tasks),
            orphan_approval_ids=set(orphan_approvals),
            orphan_execution_ids=orphan_execution_set,
            protected_artifact_ids=protected["artifact"],
        )
        return OrphanCleanupPlan(
            orphan_task_ids=orphan_tasks,
            orphan_approval_ids=orphan_approvals,
            orphan_execution_ids=orphan_executions,
            artifact_refs=artifact_refs,
            stale_workspace_names=stale_workspaces,
            stale_exchange_names=stale_exchange,
            stale_executor_run_names=stale_runs,
            stale_submission_names=stale_submissions,
            blockers=tuple(dict.fromkeys(blockers)),
        )

    def delete(self, *, confirmation: str) -> OrphanCleanupReceipt:
        if confirmation != CONFIRM_ORPHAN_CLEANUP:
            raise OrphanAdministrationError("孤儿状态清理确认文本不匹配")
        plan = self.plan()
        if plan.blockers:
            raise OrphanCleanupBlocked("；".join(plan.blockers))

        _preflight_directories(self.tasks.workspace_root, plan.stale_workspace_names)
        _preflight_directories(
            self.executions.exchange_root, plan.stale_exchange_names
        )
        _preflight_directories(
            self.executor_result_root / "runs", plan.stale_executor_run_names
        )
        _preflight_files(
            self.executor_result_root / "submissions", plan.stale_submission_names
        )
        deleted_workspaces = _delete_directories(
            self.tasks.workspace_root, plan.stale_workspace_names
        )
        deleted_exchange_directories = _delete_directories(
            self.executions.exchange_root, plan.stale_exchange_names
        )
        deleted_executor_runs = _delete_directories(
            self.executor_result_root / "runs", plan.stale_executor_run_names
        )
        deleted_submission_markers = _delete_files(
            self.executor_result_root / "submissions", plan.stale_submission_names
        )

        self.tasks.delete_tasks(plan.orphan_task_ids)
        for execution_id in plan.orphan_execution_ids:
            if self.executions.status(execution_id).state in {"created", "authorized"}:
                self.executions.abandon(execution_id)
        self.executions.delete_executions(plan.orphan_execution_ids)
        self.approvals.delete_requests(plan.orphan_approval_ids)
        purged = self.artifacts.purge_registrations(plan.artifact_refs)
        database_integrity_ok = all(
            _database_integrity_ok(path)
            for path in (
                self.artifacts.registry.database_path,
                self.tasks.database_path,
                self.tasks.tokens.database_path,
                self.approvals.database_path,
                self.executions.database_path,
                self.bindings.database_path,
            )
        )
        verification = verify_artifacts(
            self.artifacts.registry, self.artifacts.cas
        )
        return OrphanCleanupReceipt(
            deleted_tasks=len(plan.orphan_task_ids),
            deleted_approvals=len(plan.orphan_approval_ids),
            deleted_executions=len(plan.orphan_execution_ids),
            deleted_artifact_registrations=len(purged),
            deleted_workspaces=deleted_workspaces,
            deleted_exchange_directories=deleted_exchange_directories,
            deleted_executor_runs=deleted_executor_runs,
            deleted_submission_markers=deleted_submission_markers,
            database_integrity_ok=database_integrity_ok,
            artifact_integrity_ok=verification.ok,
            remaining_cas_orphans=len(verification.orphan_scan.orphan_digests),
        )

    def _artifact_deletion_refs(
        self,
        *,
        orphan_task_ids: set[str],
        orphan_approval_ids: set[str],
        orphan_execution_ids: set[str],
        protected_artifact_ids: set[str],
    ) -> tuple[ArtifactRef, ...]:
        directly_retained = set(protected_artifact_ids)
        directly_retained.update(
            reference.artifact_id
            for reference in _task_artifact_refs(
                self.tasks.database_path, excluding=orphan_task_ids
            )
        )
        directly_retained.update(
            reference.artifact_id
            for reference in _approval_artifact_refs(
                self.approvals.database_path, excluding=orphan_approval_ids
            )
        )
        directly_retained.update(
            reference.artifact_id
            for reference in _execution_artifact_refs(
                self.executions.database_path, excluding=orphan_execution_ids
            )
        )

        envelopes = []
        offset = 0
        while True:
            page = self.artifacts.list_artifacts(limit=10_000, offset=offset)
            envelopes.extend(page)
            if len(page) < 10_000:
                break
            offset += len(page)
        candidates = {
            envelope.artifact_id: envelope.ref
            for envelope in envelopes
            if envelope.artifact_id not in directly_retained
        }
        protected_by_provenance = _provenance_protected_ids(
            self.artifacts.registry.database_path, set(candidates)
        )
        return tuple(
            candidates[value]
            for value in sorted(set(candidates) - protected_by_provenance)
        )


def _read_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, isolation_level=None, timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _database_integrity_ok(path: Path) -> bool:
    with _read_connection(path) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchall()
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
    return [str(row[0]) for row in integrity] == ["ok"] and not foreign_keys


def _state_inventory(
    path: Path, table: str, identity_column: str, state_column: str
) -> dict[str, str]:
    with _read_connection(path) as connection:
        rows = connection.execute(
            f"SELECT {identity_column}, {state_column} FROM {table}"
        ).fetchall()
    return {str(row[identity_column]): str(row[state_column]) for row in rows}


def _execution_inventory(path: Path) -> dict[str, tuple[str, str | None]]:
    with _read_connection(path) as connection:
        rows = connection.execute(
            "SELECT execution_id, state, external_run_id FROM executions"
        ).fetchall()
    return {
        str(row["execution_id"]): (
            str(row["state"]),
            None if row["external_run_id"] is None else str(row["external_run_id"]),
        )
        for row in rows
    }


def _protected_control_ids(path: Path) -> dict[str, set[str]]:
    result = {value: set() for value in ("artifact", "task", "approval", "execution")}
    with _read_connection(path) as connection:
        for row in connection.execute(
            "SELECT namespace, object_id FROM scheduler_bindings"
        ).fetchall():
            namespace = str(row["namespace"])
            if namespace in result:
                result[namespace].add(str(row["object_id"]))
        for query in (
            "SELECT approval_id FROM scheduler_instance_proposals",
            "SELECT approval_id FROM scheduler_session_binding_requests",
        ):
            result["approval"].update(
                str(row["approval_id"])
                for row in connection.execute(query).fetchall()
            )
    return result


def _active_workspace_names(path: Path, task_states: dict[str, str]) -> set[str]:
    active_tasks = {
        task_id
        for task_id, state in task_states.items()
        if state in {"dispatched", "claimed", "finalizing"}
    }
    with _read_connection(path) as connection:
        rows = connection.execute(
            """
            SELECT task_id, session_id FROM assignment_instances
            WHERE session_id IS NOT NULL
            """
        ).fetchall()
    return {
        str(row["session_id"])
        for row in rows
        if str(row["task_id"]) in active_tasks
    }


def _task_artifact_refs(path: Path, *, excluding: set[str]) -> tuple[ArtifactRef, ...]:
    values: list[ArtifactRef] = []
    with _read_connection(path) as connection:
        for row in connection.execute(
            "SELECT task_id, task_ref_json, output_ref_json, scheduler_signal_ref_json FROM tasks"
        ).fetchall():
            if str(row["task_id"]) in excluding:
                continue
            values.append(_parse_ref(row["task_ref_json"]))
            for column in ("output_ref_json", "scheduler_signal_ref_json"):
                if row[column] is not None:
                    values.append(_parse_ref(row[column]))
        for table, column in (
            ("task_web_evidence", "snapshot_ref_json"),
            ("task_output_artifacts", "artifact_ref_json"),
            ("task_pdf_excerpts", "excerpt_ref_json"),
            ("task_provisional_snapshots", "manifest_ref_json"),
        ):
            for row in connection.execute(
                f"SELECT task_id, {column} FROM {table}"
            ).fetchall():
                if str(row["task_id"]) not in excluding:
                    values.append(_parse_ref(row[column]))
        # Cache entries are content-addressed across tasks and have no task FK.
        # Retain every registered cache object until an explicit cache GC owns
        # the source-to-cache reachability decision.
        for row in connection.execute(
            "SELECT source_ref_json, text_ref_json FROM pdf_text_cache"
        ).fetchall():
            values.append(_parse_ref(row["source_ref_json"]))
            values.append(_parse_ref(row["text_ref_json"]))
    return _unique_refs(values)


def _approval_artifact_refs(
    path: Path, *, excluding: set[str]
) -> tuple[ArtifactRef, ...]:
    values: list[ArtifactRef] = []
    with _read_connection(path) as connection:
        rows = connection.execute(
            "SELECT approval_id, request_ref_json, decision_ref_json FROM approval_requests"
        ).fetchall()
    for row in rows:
        if str(row["approval_id"]) in excluding:
            continue
        values.append(_parse_ref(row["request_ref_json"]))
        if row["decision_ref_json"] is not None:
            values.append(_parse_ref(row["decision_ref_json"]))
    return _unique_refs(values)


def _execution_artifact_refs(
    path: Path, *, excluding: set[str]
) -> tuple[ArtifactRef, ...]:
    values: list[ArtifactRef] = []
    with _read_connection(path) as connection:
        rows = connection.execute(
            """
            SELECT execution_id, request_ref_json, payload_ref_json,
                   decision_ref_json, result_ref_json
            FROM executions
            """
        ).fetchall()
    for row in rows:
        if str(row["execution_id"]) in excluding:
            continue
        for column in (
            "request_ref_json",
            "payload_ref_json",
            "decision_ref_json",
            "result_ref_json",
        ):
            if row[column] is not None:
                values.append(_parse_ref(row[column]))
    return _unique_refs(values)


def _provenance_protected_ids(path: Path, candidates: set[str]) -> set[str]:
    with _read_connection(path) as connection:
        links = tuple(
            (str(row["source_artifact_id"]), str(row["target_artifact_id"]))
            for row in connection.execute(
                "SELECT source_artifact_id, target_artifact_id FROM artifact_links"
            ).fetchall()
        )
    protected = {
        target
        for source, target in links
        if target in candidates and source not in candidates
    }
    while True:
        additions = {
            target
            for source, target in links
            if source in protected and target in candidates
        } - protected
        if not additions:
            return protected
        protected.update(additions)


def _parse_ref(raw: object) -> ArtifactRef:
    try:
        return ArtifactRef.model_validate_json(raw, strict=True)
    except (TypeError, ValidationError) as error:
        raise OrphanAdministrationError(
            "控制数据库中的 Artifact 引用无效"
        ) from error


def _unique_refs(values: list[ArtifactRef]) -> tuple[ArtifactRef, ...]:
    return tuple(
        {reference.canonical_json(): reference for reference in values}.values()
    )


def _directory_children(root: Path, pattern: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if not root.exists():
        return (), ()
    if root.is_symlink() or not root.is_dir():
        return (), ("<root>",)
    accepted: list[str] = []
    unexpected: list[str] = []
    for path in root.iterdir():
        if path.is_dir() and not path.is_symlink() and re.fullmatch(pattern, path.name):
            accepted.append(path.name)
        else:
            unexpected.append(path.name)
    return tuple(sorted(accepted)), tuple(sorted(unexpected))


def _file_children(root: Path, pattern: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if not root.exists():
        return (), ()
    if root.is_symlink() or not root.is_dir():
        return (), ("<root>",)
    accepted: list[str] = []
    unexpected: list[str] = []
    for path in root.iterdir():
        if path.is_file() and not path.is_symlink() and re.fullmatch(pattern, path.name):
            accepted.append(path.name)
        else:
            unexpected.append(path.name)
    return tuple(sorted(accepted)), tuple(sorted(unexpected))


def _preflight_directories(root: Path, names: tuple[str, ...]) -> None:
    try:
        for name in names:
            validate_private_directory(root, name)
    except PrivatePathError as error:
        raise OrphanCleanupBlocked("运行目录在清理前发生变化") from error


def _preflight_files(root: Path, names: tuple[str, ...]) -> None:
    try:
        for name in names:
            validate_private_file(root, name)
    except PrivatePathError as error:
        raise OrphanCleanupBlocked("运行文件在清理前发生变化") from error


def _delete_directories(root: Path, names: tuple[str, ...]) -> int:
    try:
        return sum(remove_private_directory(root, name) for name in names)
    except PrivatePathError as error:
        raise OrphanCleanupBlocked("运行目录在清理前发生变化") from error


def _delete_files(root: Path, names: tuple[str, ...]) -> int:
    try:
        return sum(remove_private_file(root, name) for name in names)
    except PrivatePathError as error:
        raise OrphanCleanupBlocked("运行文件在清理前发生变化") from error


__all__ = [
    "CONFIRM_ORPHAN_CLEANUP",
    "OrphanAdministrationError",
    "OrphanAdministrationService",
    "OrphanCleanupBlocked",
    "OrphanCleanupPlan",
    "OrphanCleanupReceipt",
]
