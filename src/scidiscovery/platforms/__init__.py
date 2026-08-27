from __future__ import annotations

from pathlib import Path

from .common import GenerationReport, PlatformConflictError


def initialize_platform(
    platform: str,
    project_root: Path | str,
    *,
    python_executable: Path | str | None = None,
    python_path: Path | str | None = None,
    control_socket: Path | str,
    worker_socket: Path | str,
    worker_workspace_root: Path | str | None = None,
    codex_config_root: Path | str | None = None,
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
        worker_socket=worker_socket,
        codex_config_root=codex_config_root,
        worker_workspace_root=worker_workspace_root,
        dry_run=dry_run,
    )


__all__ = [
    "GenerationReport",
    "PlatformConflictError",
    "initialize_platform",
]
