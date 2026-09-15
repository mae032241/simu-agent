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


PROTOCOL_VERSION = "2025-03-26"


class MCPRouter:
    def __init__(self, router: Any, *, name: str) -> None:
        self.router = router
        self.name = name

    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        request_id = request.get("id") if isinstance(request, dict) else None
        try:
            if not isinstance(request, dict):
                raise DiagnosticError("invalid protocol request", details=(contract_diagnostic(
                    "invalid_protocol_request", phase="protocol", affected_action="tool_call",
                    message="Expected a JSON-RPC request object."),))
            method = request.get("method")
            if request.get("jsonrpc") != "2.0" or not isinstance(method, str):
                raise DiagnosticError("invalid protocol request", details=(contract_diagnostic(
                    "invalid_protocol_request", phase="protocol", affected_action="tool_call",
                    message="Expected JSON-RPC 2.0 and a string method."),))
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
                params = request.get("params", {})
                if not isinstance(params, dict) or not isinstance(params.get("name"), str):
                    raise DiagnosticError("invalid protocol parameters", details=(contract_diagnostic(
                        "invalid_protocol_parameters", phase="protocol", affected_action="tool_call",
                        message="tools/call requires a parameter object with a string tool name."),))
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
                raise DiagnosticError("unknown protocol method", details=(contract_diagnostic(
                    "unknown_protocol_method", phase="protocol", affected_action="tool_call",
                    message="This JSON-RPC method is not declared by the server."),))
            return {"jsonrpc": "2.0", "id": request_id, "result": value}
        except Exception as error:
            return rpc_error(request_id, error)


def rpc_error(request_id: Any, error: Exception) -> dict[str, Any]:
    details = getattr(error, "details", ()) if isinstance(error, DiagnosticError) else ()
    engineering = getattr(error, "engineering", None)
    if not details:
        engineering = engineering or exception_facts(error, layer="mcp", action="tool_call")
        reason = engineering["causes"][0]
        details = (contract_diagnostic(
            "tool_rejected" if isinstance(error, DiagnosticError) else engineering["category"],
            phase="tool_execution", affected_action="tool_call",
            message=f"{reason['type']}: {reason['message']}", error_type=reason["type"],
        ),)
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32000, "message": details[0]["message"],
                  "data": {"diagnostics": list(details),
                           **({"engineering": engineering} if engineering else {}),
                           **({"attempt": error.attempt} if getattr(error,"attempt",None) else {})}},
    }


def parse_rpc_line(raw: str | bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError) as error:
        raise DiagnosticError("invalid JSON-RPC", details=(contract_diagnostic(
            "invalid_protocol_request", phase="protocol", affected_action="tool_call",
            message="Expected a valid JSON-RPC request object."),)) from error
    if not isinstance(value, dict):
        raise DiagnosticError("invalid JSON-RPC", details=(contract_diagnostic(
            "invalid_protocol_request", phase="protocol", affected_action="tool_call",
            message="Expected a JSON-RPC request object."),))
    return value


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
    if scheduler_session_key is not None:
        runtime.scheduler_bindings.register_client(session_key=scheduler_session_key)
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
    return MCPRouter(
        RootMCPRouter(facade),
        name="scidiscovery-root",
    )


__all__ = ["MCPRouter", "PROTOCOL_VERSION", "build_root_router"]
