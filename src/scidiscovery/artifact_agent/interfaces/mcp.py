"""JSON-RPC/MCP transport for SciDiscovery root and worker tools."""

from __future__ import annotations

import json
from pathlib import Path
import threading
from typing import Any, Mapping

from ..execution_bridge import ExecutionAdapter, ExecutionBridge
from ..runtime import open_runtime, read_secret_file
from ..schema.common import canonical_json
from ...operation_contract import DiagnosticError, contract_diagnostic
from .mcp_root import RootMCPRouter, RootToolFacade
from ..service.engineering_diagnostics import exception_facts


from ...plugin_runtime.transport import PROTOCOL_VERSION, MCPRouter, rpc_error, parse_rpc_line


def build_root_router(
    *,
    project_root: Path,
    state_root: Path,
    approval_secret_file: Path,
    approval_base_url: str | None = "http://127.0.0.1:8765",
    shared_group: bool = False,
    execution_adapters: Mapping[str, ExecutionAdapter] | None = None,
    scheduler_instance: str | None = None,
    scheduler_session_key: str | None = None,
    scheduler_creation_lock: threading.RLock | None = None,
    worker_backend: str = "local",
    local_workspace_root: Path | None = None,
    execution_collection=None,
    agent_settings=None,
    unified: bool = False,
    worker_plugin_configs=None,
) -> MCPRouter:
    approval_secret = read_secret_file(
        approval_secret_file, label="approval receipt"
    )
    runtime = open_runtime(
        project_root=project_root,
        state_root=state_root,
        approval_receipt_secret=approval_secret,
        actor_id="root_orchestrator",
        shared_group=shared_group,
        worker_backend=worker_backend,
        local_workspace_root=local_workspace_root,
        agent_settings=agent_settings,
    )
    facade = RootToolFacade(
        runtime.artifacts,
        runtime.intake,
        runs=runtime.runs,
        approvals=runtime.approvals,
        executions=runtime.executions,
        bindings=runtime.scheduler_bindings,
        instance=(
            scheduler_instance
            if scheduler_instance is not None
            else (
                runtime.scheduler_bindings.session_instance(
                    session_key=scheduler_session_key
                )
                if scheduler_session_key is not None
                else None
            )
        ),
        session_key=scheduler_session_key,
        creation_lock=scheduler_creation_lock,
        execution_bridge=ExecutionBridge(
            runtime.executions, adapters=execution_adapters or {}
        ),
        approval_base_url=approval_base_url,
        instance_management_secret=approval_secret,
        operation_catalog=runtime.operation_catalog,
        execution_collection=execution_collection,
    )
    root = RootMCPRouter(facade)
    if unified:
        from .mcp_gateway import UnifiedMCPRouter
        return UnifiedMCPRouter(root, plugin_configs=worker_plugin_configs, worker_backend=worker_backend)
    return MCPRouter(
        root,
        name="scidiscovery-root",
    )


__all__ = ["MCPRouter", "PROTOCOL_VERSION", "build_root_router"]
