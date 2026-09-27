from __future__ import annotations

from pathlib import Path
from typing import Mapping

from .common import GenerationReport, PlatformConflictError
from scidiscovery.operations.catalog import CompiledCatalog


def initialize_platform(
    platform: str,
    project_root: Path | str,
    *,
    python_executable: Path | str | None = None,
    python_path: Path | str | None = None,
    control_socket: Path | str,
    state_root: Path | str | None = None,
    local_workspace_root: Path | str | None = None,
    worker_backend: str = "local",
    codex_config_root: Path | str | None = None,
    operation_catalog: CompiledCatalog | None = None,
    runtime_plugin_configs: Mapping[str, Path | str] | None = None,
    dry_run: bool = False,
) -> GenerationReport:
    normalized = platform.strip().lower()
    if normalized != "codex":
        raise ValueError(f"unsupported platform: {platform}")
    from .codex import initialize

    return initialize(
        project_root,
        python_executable=python_executable,
        python_path=python_path,
        control_socket=control_socket,
        state_root=state_root,
        local_workspace_root=local_workspace_root,
        worker_backend=worker_backend,
        codex_config_root=codex_config_root,
        operation_catalog=operation_catalog,
        runtime_plugin_configs=runtime_plugin_configs,
        dry_run=dry_run,
    )


__all__ = [
    "GenerationReport",
    "PlatformConflictError",
    "initialize_platform",
]
