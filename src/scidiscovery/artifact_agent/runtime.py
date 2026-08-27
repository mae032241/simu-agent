"""Deterministic assembly of SciDiscovery application services."""

from __future__ import annotations

import os
import stat
from importlib import import_module
from dataclasses import dataclass
from pathlib import Path

from scidiscovery.platforms.roles import (
    load_roles,
    role_output_collection_profiles,
    role_output_json_schema,
)

from .schema.refs import ActorRef
from .schema.experiment import ExperimentPortfolio
from .schema.role_result import role_result_json_schema
from .schema.structured_revision import StructuredRevision
from .context_policy import DEFAULT_CONTEXT_POLICIES, RoleContextPolicies
from .security import TaskTokenService
from .service import (
    ApprovalService,
    ArtifactService,
    SecureIntakeService,
    TaskService,
    RoleOutputContract,
    RoleOutputVariant,
    SchedulerBindingService,
    ExecutionService,
    StateMaintenanceLock,
    TCADDebugService,
    TCADDevelopmentDebugAdapter,
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
    maintenance: StateMaintenanceLock
    tcad_debug: TCADDebugService | None


def open_runtime(
    *,
    project_root: Path | str,
    state_root: Path | str,
    task_token_secret: bytes,
    approval_receipt_secret: bytes | None = None,
    actor_id: str = "root_orchestrator",
    shared_group: bool = False,
    tcad_debug_adapter: TCADDevelopmentDebugAdapter | None = None,
) -> ArtifactAgentRuntime:
    project = Path(project_root).expanduser().resolve()
    state = Path(state_root).expanduser().absolute()
    _validate_state_root(project, state)
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
                context_validator=role.output_context_validator,
                context_sources=role.output_context_sources,
                json_schema=role_output_json_schema(role),
                collection_profiles=role_output_collection_profiles(role),
                primary_profiles=_role_primary_output_profiles(role.name),
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
            development_debug_enabled=tcad_debug_adapter is not None,
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
        tcad_debug = (
            TCADDebugService(
                tasks=tasks,
                adapter=tcad_debug_adapter,
                exchange_root=state / "tcad-debug-exchange",
            )
            if tcad_debug_adapter is not None
            else None
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
        maintenance=maintenance,
        tcad_debug=tcad_debug,
    )


def _role_primary_output_profiles(role_name: str) -> dict[str, RoleOutputVariant]:
    profiles: dict[str, RoleOutputVariant] = {}
    if role_name in {"evidence_extractor", "ideator", "experiment_designer"}:
        profiles["structured-revision"] = RoleOutputVariant(
            kind="structured_revision",
            format="json",
            schema_id="scidiscovery.structured-revision.v1",
            validator=(
                "scidiscovery.artifact_agent.schema.structured_revision:"
                "validate_structured_revision"
            ),
            context_validator=(
                "scidiscovery.artifact_agent.transforms:"
                "validate_structured_revision_against_base"
            ),
            context_sources=("prior_draft",),
            json_schema=role_result_json_schema(StructuredRevision),
        )
    if role_name == "experiment_designer":
        profiles["legacy-experiment-portfolio"] = RoleOutputVariant(
            kind="experiment_portfolio",
            format="json",
            schema_id="scidiscovery.experiment-portfolio.v1",
            validator=(
                "scidiscovery.artifact_agent.schema.experiment:"
                "validate_experiment_portfolio"
            ),
            context_validator=(
                "scidiscovery.artifact_agent.schema.experiment:"
                "validate_experiment_design_task_output"
            ),
            context_sources=(
                "research_objective",
                "hypothesis_portfolio",
                "candidate_eligibility",
            ),
            json_schema=role_result_json_schema(ExperimentPortfolio),
        )
    return profiles


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
