from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from scidiscovery.artifact_agent.interfaces.mcp_worker import (
    WORKER_TOOLS as WORKER_MCP_TOOLS,
)

from .common import (
    GenerationReport,
    PlatformConflictError,
    absolute_project_root,
    commit_text_files,
    managed_block,
)
from .roles import (
    RoleDefinition,
    load_roles,
    load_scheduler_prompt,
    render_worker_prompt,
)


PROMPT_BEGIN = "<!-- BEGIN SCIDISCOVERY SCHEDULER -->"
PROMPT_END = "<!-- END SCIDISCOVERY SCHEDULER -->"
MANAGED_ENV = "SCIDISCOVERY_MANAGED"
WORKER_TOOLS = tuple(tool.name for tool in WORKER_MCP_TOOLS)


def initialize(
    project_root: Path | str,
    *,
    python_executable: Path | str | None = None,
    python_path: Path | str | None = None,
    control_socket: Path | str,
    worker_socket: Path | str,
    dry_run: bool = False,
) -> GenerationReport:
    root = absolute_project_root(project_root)
    python = _absolute_python_executable(
        python_executable or sys.executable
    )
    module_path = (
        _absolute_path(python_path)
        if python_path is not None
        else Path(__file__).resolve().parents[2]
    )
    socket_path = _absolute_path(control_socket)
    worker_socket_path = _absolute_path(worker_socket)

    desired: dict[Path, str] = {}
    exclusive: set[Path] = set()
    markers: dict[Path, str] = {}
    for role in load_roles():
        path = (
            root
            / ".claude"
            / "agents"
            / f"{role.name.replace('_', '-')}.md"
        )
        desired[path] = _role_markdown(
            role,
            python=python,
            python_path=module_path,
            worker_socket=worker_socket_path,
        )
        exclusive.add(path)
        markers[path] = "<!-- Managed by SciDiscovery -->"

    mcp_path = root / ".mcp.json"
    desired[mcp_path] = _merged_mcp(
        mcp_path,
        python=python,
        python_path=module_path,
        control_socket=socket_path,
    )

    prompt_path = root / "CLAUDE.md"
    desired[prompt_path] = managed_block(
        _read(prompt_path),
        begin=PROMPT_BEGIN,
        end=PROMPT_END,
        body=load_scheduler_prompt(),
    )
    return commit_text_files(
        platform="claude",
        project_root=root,
        desired=desired,
        exclusive=frozenset(exclusive),
        exclusive_markers=markers,
        dry_run=dry_run,
    )


def _role_markdown(
    role: RoleDefinition,
    *,
    python: Path,
    python_path: Path | None,
    worker_socket: Path,
) -> str:
    tools = "\n".join(
        ["  - Read", "  - WebSearch", "  - WebFetch"]
        + [f"  - mcp__scidiscovery__{tool}" for tool in WORKER_TOOLS]
    )
    server = json.dumps(
        [
            {
                "scidiscovery": _worker_proxy_server(
                    python=python,
                    python_path=python_path,
                    socket_path=worker_socket,
                    role=role.name,
                )
            }
        ],
        ensure_ascii=True,
        sort_keys=True,
    )
    prompt = (
        render_worker_prompt(role, python_executable=python).rstrip()
        + "\n\nDo not spawn subagents or delegate this assignment. Complete only "
        "the bound scientific work through a worker finalization tool.\n"
    )
    return (
        "---\n"
        f"name: {role.name.replace('_', '-')}\n"
        f"description: {json.dumps(role.description, ensure_ascii=True)}\n"
        "model: inherit\n"
        "permissionMode: dontAsk\n"
        "tools:\n"
        f"{tools}\n"
        f"mcpServers: {server}\n"
        "---\n"
        f"{prompt}"
        "<!-- Managed by SciDiscovery -->\n"
    )


def _merged_mcp(
    path: Path,
    *,
    python: Path,
    python_path: Path | None,
    control_socket: Path,
) -> str:
    if path.exists():
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise PlatformConflictError(
                f"existing MCP config is invalid: {error}"
            ) from error
        if not isinstance(document, dict):
            raise PlatformConflictError("existing MCP config must be a JSON object")
    else:
        document = {}

    servers = document.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise PlatformConflictError("mcpServers must be a JSON object")
    name = "scidiscovery"
    server = _proxy_server(
        python=python, socket_path=control_socket, python_path=python_path
    )
    existing = servers.get(name)
    if existing is not None and existing != server:
        if not _is_managed(existing):
            raise PlatformConflictError(
                f"existing MCP config owns mcpServers.{name}"
            )
    servers[name] = server
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def _proxy_server(
    *, python: Path, socket_path: Path, python_path: Path | None
) -> dict[str, Any]:
    return {
        "type": "stdio",
        "command": str(python),
        "args": [
            "-m",
            "scidiscovery.artifact_agent.interfaces.mcp_proxy",
            "--socket",
            str(socket_path),
        ],
        "env": {
            MANAGED_ENV: "1",
            "PYTHONNOUSERSITE": "1",
            "SCIDISCOVERY_PRINCIPAL": "service",
            **({"PYTHONPATH": str(python_path)} if python_path else {}),
        },
    }


def _worker_proxy_server(
    *,
    python: Path,
    python_path: Path | None,
    socket_path: Path,
    role: str,
) -> dict[str, Any]:
    return {
        "type": "stdio",
        "command": str(python),
        "args": [
            "-m",
            "scidiscovery.artifact_agent.interfaces.mcp_worker_proxy",
            "--socket",
            str(socket_path),
            "--worker-id",
            role,
        ],
        "env": {
            MANAGED_ENV: "1",
            "PYTHONNOUSERSITE": "1",
            "SCIDISCOVERY_PRINCIPAL": "agent",
            "SCIDISCOVERY_ROLE": role,
            **({"PYTHONPATH": str(python_path)} if python_path else {}),
        },
    }


def _is_managed(value: object) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("env"), dict)
        and value["env"].get(MANAGED_ENV) == "1"
    )


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _absolute_python_executable(value: Path | str) -> Path:
    expanded = Path(value).expanduser()
    return Path(os.path.abspath(os.fspath(expanded)))


def _absolute_path(value: Path | str) -> Path:
    return Path(os.path.abspath(os.fspath(Path(value).expanduser())))
