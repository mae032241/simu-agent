"""JSON-RPC/MCP transport for SciDiscovery root and worker tools."""

from __future__ import annotations

from pathlib import Path
import threading
from typing import Any, Mapping

from ..execution_bridge import ExecutionAdapter, ExecutionBridge
from ..runtime import open_runtime, read_secret_file
from ..schema.common import canonical_json
from .mcp_root import RootMCPRouter, RootToolFacade


PROTOCOL_VERSION = "2025-03-26"


class MCPRouter:
    def __init__(self, router: Any, *, name: str) -> None:
        self.router = router
        self.name = name

    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        request_id = request.get("id")
        try:
            method = request.get("method")
            if request.get("jsonrpc") != "2.0" or not isinstance(method, str):
                raise ValueError("invalid JSON-RPC request")
            if method == "notifications/initialized":
                return None
            if method == "initialize":
                value = {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": self.name, "version": "1"},
                }
            elif method == "tools/list":
                value = {"tools": self.router.list_tools()}
            elif method == "tools/call":
                params = request.get("params") or {}
                if not isinstance(params, dict):
                    raise ValueError("tools/call params must be an object")
                result = self.router.call_tool(
                    str(params.get("name", "")), params.get("arguments")
                )
                value = {
                    "content": [
                        {
                            "type": "text",
                            "text": canonical_json(result).decode("utf-8"),
                        }
                    ],
                    "structuredContent": result,
                    "isError": False,
                }
            else:
                raise ValueError("unknown JSON-RPC method")
            return {"jsonrpc": "2.0", "id": request_id, "result": value}
        except Exception as error:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32000, "message": str(error)},
            }


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
    )
    return MCPRouter(
        RootMCPRouter(facade),
        name="scidiscovery-root",
    )


__all__ = ["MCPRouter", "PROTOCOL_VERSION", "build_root_router"]
