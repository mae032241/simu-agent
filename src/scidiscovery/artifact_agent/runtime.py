"""Deterministic assembly of SciDiscovery application services."""

from __future__ import annotations

import os
import stat
from importlib import import_module
from dataclasses import dataclass
from pathlib import Path

from scidiscovery.platforms.roles import load_roles, role_output_json_schema

from .schema.refs import ActorRef
from .context_policy import DEFAULT_CONTEXT_POLICIES, RoleContextPolicies
from .security import TaskTokenService
from .service import (
    ApprovalService,
    ArtifactService,
    SecureIntakeService,
    TaskService,
    RoleOutputContract,
    SchedulerBindingService,
    ExecutionService,
)


class RuntimeConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ArtifactAgentRuntime:
    project_root: Path
    state_root: Path
    actor: ActorRef
    artifacts: ArtifactService
    tokens: TaskTokenService
    tasks: TaskService
    intake: SecureIntakeService
    approvals: ApprovalService | None
    executions: ExecutionService | None
    scheduler_bindings: SchedulerBindingService


def open_runtime(
    *,
    project_root: Path | str,
    state_root: Path | str,
    task_token_secret: bytes,
    approval_receipt_secret: bytes | None = None,
    actor_id: str = "root_orchestrator",
    shared_group: bool = False,
) -> ArtifactAgentRuntime:
    project = Path(project_root).expanduser().resolve()
    state = Path(state_root).expanduser().absolute()
    _validate_state_root(project, state)
    actor = ActorRef(actor_id=actor_id, actor_type="service")
    artifacts = ArtifactService.open(
        cas_root=state / "artifacts",
        database_path=state / "database" / "artifact_agent.sqlite3",
        shared_group=shared_group,
    )
    tokens = TaskTokenService(
        database_path=state / "database" / "task_tokens.sqlite3",
        secret=task_token_secret,
    )
    role_output_contracts = {
        role.name: RoleOutputContract(
            kind=role.output,
            format=role.output_format,
            schema_id=role.output_schema,
            validator=role.output_validator,
            json_schema=role_output_json_schema(role),
        )
        for role in load_roles()
    }
    role_context_policies = {
        role.name: _load_context_policies(role.context_policies)
        for role in load_roles()
    }
    tasks = TaskService(
        artifacts=artifacts,
        tokens=tokens,
        database_path=state / "database" / "tasks.sqlite3",
        service_actor=actor,
        role_output_contracts=role_output_contracts,
        role_context_policies=role_context_policies,
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
    scheduler_bindings = SchedulerBindingService(
        state / "database" / "scheduler-bindings.sqlite3"
    )
    return ArtifactAgentRuntime(
        project_root=project,
        state_root=state,
        actor=actor,
        artifacts=artifacts,
        tokens=tokens,
        tasks=tasks,
        intake=intake,
        approvals=approvals,
        executions=executions,
        scheduler_bindings=scheduler_bindings,
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


def _load_context_policies(locator: str | None) -> RoleContextPolicies:
    if locator is None:
        return DEFAULT_CONTEXT_POLICIES
    module_name, separator, attribute = locator.partition(":")
    if not separator or not module_name or not attribute:
        raise RuntimeConfigurationError("role context policy locator is invalid")
    try:
        value = getattr(import_module(module_name), attribute)
    except (ImportError, AttributeError) as error:
        raise RuntimeConfigurationError(
            f"role context policies are unavailable: {locator}"
        ) from error
    if not isinstance(value, RoleContextPolicies):
        raise RuntimeConfigurationError(
            f"role context policies have the wrong type: {locator}"
        )
    return value


__all__ = [
    "ArtifactAgentRuntime",
    "RuntimeConfigurationError",
    "open_runtime",
    "read_secret_file",
]
