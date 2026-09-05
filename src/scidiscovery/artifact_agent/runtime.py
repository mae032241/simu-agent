"""Deterministic assembly of SciDiscovery application services."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from scidiscovery.operations.catalog import CompiledCatalog, compile_installed_catalog
from .schema.refs import ActorRef
from .service import (
    ApprovalService,
    ArtifactService,
    SecureIntakeService,
    RunService,
    SchedulerBindingService,
    ExecutionService,
    StateMaintenanceLock,
)
from .service.local_workspace import LocalTrustedBackend

if TYPE_CHECKING:
    from .service.hardened_workspace import HardenedWorkerBackend


class RuntimeConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ArtifactAgentRuntime:
    project_root: Path
    state_root: Path
    actor: ActorRef
    artifacts: ArtifactService
    runs: RunService
    local_backend: LocalTrustedBackend | None
    hardened_backend: HardenedWorkerBackend | None
    intake: SecureIntakeService
    approvals: ApprovalService | None
    executions: ExecutionService | None
    scheduler_bindings: SchedulerBindingService
    maintenance: StateMaintenanceLock
    operation_catalog: CompiledCatalog


def open_runtime(
    *,
    project_root: Path | str,
    state_root: Path | str,
    approval_receipt_secret: bytes | None = None,
    actor_id: str = "root_orchestrator",
    shared_group: bool = False,
    worker_backend: str = "local",
    local_workspace_root: Path | str | None = None,
) -> ArtifactAgentRuntime:
    project = Path(project_root).expanduser().resolve()
    state = Path(state_root).expanduser().absolute()
    _validate_state_root(project, state)
    if worker_backend not in {"local", "hardened"}:
        raise RuntimeConfigurationError("worker backend is invalid")
    operation_catalog = compile_installed_catalog()
    scheduler_database_path = state / "database" / "scheduler-bindings.sqlite3"
    actor = ActorRef(actor_id=actor_id, actor_type="service")
    maintenance = StateMaintenanceLock(
        state / "maintenance.lock", shared_group=shared_group
    )
    with maintenance.shared():
        artifacts = ArtifactService.open(
            cas_root=state / "artifacts",
            database_path=state / "database" / "artifact_agent.sqlite3",
            shared_group=shared_group,
        )
        scheduler_bindings = SchedulerBindingService(scheduler_database_path)
        local_backend = None
        hardened_backend = None
        if worker_backend == "hardened":
            from .service.hardened_workspace import HardenedWorkerBackend

            hardened_backend = HardenedWorkerBackend(state / "hardened-runs")
            runs = RunService(
                artifacts=artifacts,
                database_path=state / "database" / "runs.sqlite3",
                service_actor=actor,
                operation_catalog=operation_catalog,
                backend=hardened_backend,
                scheduler_bindings=scheduler_bindings,
            )
        else:
            local_backend = LocalTrustedBackend(
                local_workspace_root or project / ".scidiscovery-runs"
            )
            runs = RunService(
                artifacts=artifacts,
                database_path=state / "database" / "runs.sqlite3",
                service_actor=actor,
                operation_catalog=operation_catalog,
                backend=local_backend,
                scheduler_bindings=scheduler_bindings,
            )
        intake = SecureIntakeService(
            project_root=project,
            artifact_service=artifacts,
            creator=actor,
        )
        approvals = (
            ApprovalService(
                artifacts=artifacts,
                database_path=state / "database" / "approvals.sqlite3",
                service_actor=ActorRef(
                    actor_id="approval_ui_service", actor_type="service"
                ),
                receipt_secret=approval_receipt_secret,
            )
            if approval_receipt_secret is not None
            else None
        )
        executions = (
            ExecutionService(
                artifacts=artifacts,
                approvals=approvals,
                database_path=state / "database" / "executions.sqlite3",
                exchange_root=state / "execution-exchange",
                service_actor=actor,
            )
            if approvals is not None
            else None
        )
    return ArtifactAgentRuntime(
        project_root=project,
        state_root=state,
        actor=actor,
        artifacts=artifacts,
        runs=runs,
        local_backend=local_backend,
        hardened_backend=hardened_backend,
        intake=intake,
        approvals=approvals,
        executions=executions,
        scheduler_bindings=scheduler_bindings,
        maintenance=maintenance,
        operation_catalog=operation_catalog,
    )


def read_secret_file(path: Path | str, *, label: str) -> bytes:
    source = Path(path).expanduser().absolute()
    try:
        metadata = os.lstat(source)
    except FileNotFoundError as error:
        raise RuntimeConfigurationError(f"{label} secret file does not exist") from error
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise RuntimeConfigurationError(f"{label} secret must be a regular non-symlink file")
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        raise RuntimeConfigurationError(f"{label} secret file must have mode 0600")
    raw = source.read_bytes()
    if len(raw) < 32:
        raise RuntimeConfigurationError(f"{label} secret must contain at least 32 bytes")
    return raw


def _validate_state_root(project: Path, state: Path) -> None:
    if not project.is_dir():
        raise RuntimeConfigurationError("project root must be an existing directory")
    if state.is_symlink() or (state.exists() and not state.is_dir()):
        raise RuntimeConfigurationError("state root must be a non-symlink directory")


__all__ = [
    "ArtifactAgentRuntime",
    "RuntimeConfigurationError",
    "open_runtime",
    "read_secret_file",
]
