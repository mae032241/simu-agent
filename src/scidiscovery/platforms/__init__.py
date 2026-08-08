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
    codex_config_root: Path | str | None = None,
    dry_run: bool = False,
) -> GenerationReport:
    normalized = platform.strip().lower()
    if normalized == "both":
        reports = [
            initialize_platform(
                candidate,
                project_root,
                python_executable=python_executable,
                python_path=python_path,
                control_socket=control_socket,
                worker_socket=worker_socket,
                codex_config_root=codex_config_root,
                dry_run=True,
            )
            for candidate in ("codex", "claude")
        ]
        if not dry_run:
            reports = [
                initialize_platform(
                    candidate,
                    project_root,
                    python_executable=python_executable,
                    python_path=python_path,
                    control_socket=control_socket,
                    worker_socket=worker_socket,
                    codex_config_root=codex_config_root,
                    dry_run=False,
                )
                for candidate in ("codex", "claude")
            ]
        return GenerationReport(
            platform="both",
            project_root=reports[0].project_root,
            changed=tuple(
                path for report in reports for path in report.changed
            ),
            unchanged=tuple(
                path for report in reports for path in report.unchanged
            ),
            dry_run=dry_run,
        )
    if normalized == "codex":
        from .codex import initialize
    elif normalized == "claude":
        from .claude import initialize
    else:
        raise ValueError(f"unsupported platform: {platform}")
    return initialize(
        project_root,
        python_executable=python_executable,
        python_path=python_path,
        control_socket=control_socket,
        worker_socket=worker_socket,
        **(
            {"codex_config_root": codex_config_root}
            if normalized == "codex"
            else {}
        ),
        dry_run=dry_run,
    )


__all__ = [
    "GenerationReport",
    "PlatformConflictError",
    "initialize_platform",
]
