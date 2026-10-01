"""Deterministic assembly of SciDiscovery application services."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path

from scidiscovery.agent_execution_settings import AgentSettings, load_settings
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
from .service.instance_maintenance import InstanceMaintenance


class RuntimeConfigurationError(RuntimeError):
    pass


def validate_worker_backend(value: str) -> str:
    if value == "hardened":
        raise RuntimeConfigurationError(
            "hardened Worker backend has been retired; finish or archive existing runs on the previous release, "
            "then explicitly configure local and regenerate profiles. "
            "Local retains native permissions; migration is not automatic."
        )
    if value != "local":
        raise RuntimeConfigurationError("worker backend must be local")
    return value


@dataclass(frozen=True)
class ArtifactAgentRuntime:
    project_root: Path
    state_root: Path
    actor: ActorRef
    artifacts: ArtifactService
    runs: RunService
    local_backend: LocalTrustedBackend
    intake: SecureIntakeService
    approvals: ApprovalService | None
    executions: ExecutionService | None
    scheduler_bindings: SchedulerBindingService
    maintenance: StateMaintenanceLock
    operation_catalog: CompiledCatalog
    instance_maintenance: InstanceMaintenance | None = None
    execution_bridge: object | None = None


def open_runtime(
    *,
    project_root: Path | str,
    state_root: Path | str,
    approval_receipt_secret: bytes | None = None,
    actor_id: str = "root_orchestrator",
    shared_group: bool = False,
    worker_backend: str = "local",
    local_workspace_root: Path | str | None = None,
    agent_settings_file: Path | str | None = None,
    agent_settings: AgentSettings | None = None,
    execution_adapters=None,
    execution_collection=None,
    worker_plugin_configs=None,
    approval_base_url: str | None = None,
) -> ArtifactAgentRuntime:
    project = Path(project_root).expanduser().resolve()
    state = Path(state_root).expanduser().absolute()
    _validate_state_root(project, state)
    validate_worker_backend(worker_backend)
    from .state_format import ensure_state_format
    ensure_state_format(state, shared_group=shared_group)
    operation_catalog = compile_installed_catalog()
    agent_settings = agent_settings or load_settings(agent_settings_file or os.environ.get("SCID_AGENT_SETTINGS_FILE"))
    scheduler_database_path = state / "database" / "scheduler-bindings.sqlite3"
    actor = ActorRef(actor_id=actor_id, actor_type="service")
    maintenance = StateMaintenanceLock(
        state / "maintenance.lock", shared_group=shared_group
    )
    instance_maintenance = InstanceMaintenance(state, maintenance=maintenance)
    with maintenance.shared():
        artifacts = ArtifactService.open(
            cas_root=state / "artifacts",
            database_path=state / "database" / "artifact_agent.sqlite3",
            shared_group=shared_group,
        )
        scheduler_bindings = SchedulerBindingService(scheduler_database_path, global_settings=agent_settings)
        local_backend = LocalTrustedBackend(
            local_workspace_root or project / ".scidiscovery-runs"
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
        if executions is not None:
            executions.instance_maintenance = instance_maintenance
            executions.scheduler_bindings = scheduler_bindings
        bridge, experiment_factory = None, None
        if execution_adapters is not None:
            if executions is None:
                raise RuntimeConfigurationError("experiment execution requires an approval receipt secret")
            from .execution_bridge import ExecutionBridge
            from .service.experiment_execution import ExperimentExecution
            from .worker_services import load_operation_services
            bridge = ExecutionBridge(executions, adapters=execution_adapters,
                lifecycle_settings=agent_settings.lifecycle)
            experiment_factory = lambda owner: ExperimentExecution(
                runs=owner, executions=executions, bridge=bridge,
                collection=execution_collection, approval_base_url=approval_base_url,
                services_for=lambda operation_id: load_operation_services(
                    operation_catalog, operation_id, worker_plugin_configs or {}, state))
        runs = RunService(
            artifacts=artifacts,
            database_path=state / "database" / "runs.sqlite3",
            service_actor=actor,
            operation_catalog=operation_catalog,
            backend=local_backend,
            scheduler_bindings=scheduler_bindings,
            instance_maintenance=instance_maintenance,
            agent_settings=agent_settings,
            experiment_execution_factory=experiment_factory,
            approval_database_path=state / "database" / "approvals.sqlite3",
        )
        scheduler_bindings.progress_run_reader = runs.goal_related_runs
        scheduler_bindings.progress_native_identity_reader = runs.native_identities
        scheduler_bindings.progress_active_work_reader = lambda *, instance_id: (
            tuple('任务 ' + (scheduler_bindings.find_name(instance=instance_id, namespace='run', object_id=item)
                or '未绑定名称（标识：' + item + '）') for item in runs.active_ids(instance_id=instance_id, limit=1))
            or (tuple('执行 ' + (scheduler_bindings.find_name(instance=instance_id, namespace='execution', object_id=item)
                or '未绑定名称（标识：' + item + '）') for item in executions.active_ids(instance_id=instance_id,
                scheduler_database_path=scheduler_bindings.database_path, limit=1))
                if executions is not None else ()))
        scheduler_bindings.progress_accepted_execution_reader = (lambda execution_id: (
            executions.status(execution_id).external_run_id or executions.prepared_submission(execution_id))) if executions is not None else None
    return ArtifactAgentRuntime(
        project_root=project,
        state_root=state,
        actor=actor,
        artifacts=artifacts,
        runs=runs,
        local_backend=local_backend,
        intake=intake,
        approvals=approvals,
        executions=executions,
        scheduler_bindings=scheduler_bindings,
        maintenance=maintenance,
        operation_catalog=operation_catalog,
        instance_maintenance=instance_maintenance,
        execution_bridge=bridge,
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
