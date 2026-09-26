"""Operation-bound Worker MCP using the optional server-edited Run backend."""

from __future__ import annotations

from ...agent_execution_settings import narrative_instruction

import argparse
import json
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ...operation_contract import DiagnosticError, validation_diagnostics, contract_diagnostic
from ...operations.tooling import parse_tool_arguments

from ...operations.catalog import CompiledCatalog, compile_installed_catalog
from ...operations.tooling import operation_worker_tools
from ..runtime_plugin_bindings import (
    load_runtime_plugin_contributions,
    parse_plugin_config_assignments,
)
from ..schema.refs import ActorRef
from ..service.artifacts import ArtifactService
from ..service.hardened_files import HardenedFileEditor, JsonPatchError
from ..service.hardened_workspace import HardenedWorkerBackend
from ..service.runs import RunService, RunStateConflict
from ..service.scheduler_bindings import SchedulerBindingService
from ..service.instance_maintenance import InstanceMaintenanceBusy, InstanceMaintenanceUnavailable
from .mcp import MCPRouter, parse_rpc_line, rpc_error
from .mcp_local_worker import LocalWorkerMCPRouter
from .mcp_worker_protocol import WorkerToolError


_FILE_TOOLS = frozenset(
    {
        "worker_file_write_begin",
        "worker_file_write_chunk",
        "worker_file_write_commit",
        "worker_file_apply_patch",
        "worker_file_json_patch",
        "worker_file_delete",
        "worker_file_move",
    }
)


class HardenedWorkerMCPRouter(LocalWorkerMCPRouter):
    """Keep scientific completion in RunService while enforcing server-side writes."""

    def _register_backend_tools(self) -> None:
        for tool in operation_worker_tools(self.compiled):
            projected = replace(
                tool,
                contextual_handler=(
                    tool.local_contextual_handler or tool.contextual_handler
                ),
            )
            self._registered[tool.name] = projected
            self._tools[tool.name] = projected

    def __init__(self, runs: RunService, **values: Any) -> None:
        super().__init__(runs, **values)
        self._editor: HardenedFileEditor | None = None
        self._transport_owner = f"transport_{uuid.uuid4().hex}"

    def call_tool(self, name: str, arguments: dict[str, Any] | None) -> Any:
        # Include the transport lock, inherited timing/failure handlers, and the
        # final transport release under the same outer maintenance ownership.
        self._check_participation()
        self._validate_open_call(name, arguments)
        with self._maintenance_call(name, existing_assignment=self._run_id is not None):
            return self._transport_call_tool(name, arguments)

    def _transport_call_tool(self, name: str, arguments: dict[str, Any] | None) -> Any:
        backend = self.runs.backend
        assert isinstance(backend, HardenedWorkerBackend)
        if name == "worker_open_assignment" and self._run_id is not None and not self._completed:
            # This backend reattaches the same cached Run on open. Check that
            # exact owner before reading/locking its potentially expired lease.
            # A fresh assignment has no cached Run and never takes this branch.
            self._check_opened_instance()
            self._opened_call_run_id = self._run_id
        try:
            if self._run_id is not None and not self._completed:
                with backend.transport_guard(
                    self._run_id,
                    self._transport_owner,
                    renew=name == "worker_heartbeat",
                ):
                    result = self._observed_call_tool(name, arguments)
            else:
                result = self._observed_call_tool(name, arguments)
        except (InstanceMaintenanceBusy, InstanceMaintenanceUnavailable):
            raise
        except DiagnosticError as error:
            if not getattr(error, "engineering", None):
                self._engineering_failure(name, error)
                self._record_failure_safely(name, error)
            raise
        except Exception as error:
            failure = self._engineering_failure(name, error)
            self._record_failure_safely(name, failure)
            raise failure from error
        if (
            name == "worker_submit_result"
            and isinstance(result, dict)
            and result.get("state") == "completed"
            and self._run_id is not None
        ):
            backend.release_transport(self._run_id, self._transport_owner)
        return result

    def _call_tool(self, name: str, arguments: dict[str, Any] | None) -> Any:
        if name not in _FILE_TOOLS:
            return super()._call_tool(name, arguments)
        with self._lock:
            try:
                tool = self._tools[name]
            except KeyError as error:
                raise WorkerToolError(f"unknown worker tool: {name}") from error
            try:
                parsed = parse_tool_arguments(tool.input_model, arguments)
            except ValidationError as error:
                raise WorkerToolError("tool arguments do not satisfy the declared model",
                    details=validation_diagnostics(error, schema=tool.schema()["inputSchema"])) from error
            if self._run_id is None or self._workspace is None or self._editor is None:
                raise WorkerToolError("worker_open_assignment must be called first")
            if self._completed:
                raise WorkerToolError("this Run is already completed")
            try:
                if name == "worker_file_write_begin":
                    result = self._editor.begin(
                        parsed.relative_path, parsed.expected_bytes, parsed.operation
                    )
                elif name == "worker_file_write_chunk":
                    result = self._editor.chunk(parsed.content, parsed.encoding)
                elif name == "worker_file_write_commit":
                    result = self._editor.commit()
                elif name == "worker_file_json_patch":
                    result = self._editor.json_patch(
                        parsed.relative_path,
                        parsed.operations,
                        parsed.expected_digest,
                    )
                elif name == "worker_file_apply_patch":
                    result = self._editor.text_patch(
                        parsed.relative_path, parsed.patch
                    )
                elif name == "worker_file_delete":
                    result = self._editor.delete(parsed.relative_path)
                elif name == "worker_file_move":
                    result = self._editor.move(
                        parsed.source_relative_path,
                        parsed.destination_relative_path,
                    )
                else:
                    raise WorkerToolError("unknown server-side file operation")
            except JsonPatchError as error:
                raise WorkerToolError("server-side workspace edit failed", details=(
                    contract_diagnostic(
                        "json_patch_invalid", phase="tool_arguments", affected_action="tool_call",
                        repairable=True,
                        message="Check the JSON pointer, operation, current file digest and file size, then retry.",
                        error_type="value_error",
                    ),
                )) from error
            except Exception as error:
                if isinstance(error, DiagnosticError):
                    raise
                raise WorkerToolError("server-side workspace edit failed") from error
            self.runs.record_activity(self._run_id, f"tool_succeeded:{name}")
            return result

    def _open(self) -> dict[str, Any]:
        if self._completed:
            self._check_opened_instance()
            self._opened_call_run_id = self._run_id
            return {"state": "completed"}
        if self._missing_services:
            raise WorkerToolError(
                "required Operation runtime service is unavailable: "
                + ", ".join(self._missing_services)
            )
        if self._run_id is None:
            try:
                status, workspace = self.runs.reopen(
                    operation_id=self.operation_id,
                    operation_digest=self.operation_digest,
                    **({"run_id": self._bound_run_id} if self._bound_run_id else {}),
                )
            except RunStateConflict as error:
                raise WorkerToolError(str(error)) from error
            self._run_id = status.run_id
            self._opened_call_run_id = status.run_id
            self._workspace = workspace
            backend = self.runs.backend
            assert isinstance(backend, HardenedWorkerBackend)
            try:
                backend.claim_transport(status.run_id, self._transport_owner)
            except Exception as error:
                self._run_id = None
                self._workspace = None
                raise WorkerToolError(str(error)) from error
            self._editor = HardenedFileEditor(self.compiled, workspace)
        self._check_opened_instance()
        self._opened_call_run_id = self._run_id
        status = self.runs.status(self._run_id)
        if self.is_helper:
            reply = self._helper_open_reply(status)
            reply["tool_contracts"] = {item["name"]: {key: item[key] for key in ("description", "inputSchema")} for item in self.list_tools()}
            reply["write_protocol"] = "server_file_tools"
            return reply
        return {
            "state": "opened",
            "role_instructions": json.loads(self._workspace.assignment_path.read_bytes()).get("role_instructions", ""),
            "narrative_instruction": narrative_instruction(
                status.execution_profile["profile"] if status.execution_profile else None),
            "workspace_path": str(self._workspace.root),
            "assignment_path": str(self._workspace.assignment_path),
            "tool_contracts": self._assignment_tool_contracts(),
            "output_directory": str(self._workspace.output_directory),
            "domain_workspace_path": (
                None
                if self._workspace.domain_workspace_path is None
                else str(self._workspace.domain_workspace_path)
            ),
            "write_protocol": "server_file_tools",
            "remaining_seconds": _remaining(status.deadline_at),
        }


def build_hardened_worker_router(
    *,
    state_root: Path,
    operation_id: str,
    operation_digest: str,
    operation_catalog: CompiledCatalog | None = None,
    tool_services: dict[str, object] | None = None,
) -> MCPRouter:
    state = state_root.expanduser().absolute()
    catalog = operation_catalog or compile_installed_catalog()
    artifacts = ArtifactService.open(
        cas_root=state / "artifacts",
        database_path=state / "database" / "artifact_agent.sqlite3",
    )
    backend = HardenedWorkerBackend(state / "hardened-runs")
    bindings = SchedulerBindingService(
        state / "database" / "scheduler-bindings.sqlite3"
    )
    runs = RunService(
        artifacts=artifacts,
        database_path=state / "database" / "runs.sqlite3",
        service_actor=ActorRef(actor_id="root_orchestrator", actor_type="service"),
        operation_catalog=catalog,
        backend=backend,
        scheduler_bindings=bindings,
    )
    return MCPRouter(
        HardenedWorkerMCPRouter(
            runs,
            operation_id=operation_id,
            operation_digest=operation_digest,
            tool_services=tool_services,
        ),
        name="scidiscovery-hardened-operation",
    )


def _remaining(deadline: str) -> int:
    value = datetime.fromisoformat(deadline)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return max(0, int((value - datetime.now(timezone.utc)).total_seconds()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scidiscovery-hardened-worker-mcp")
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--operation-id", required=True)
    parser.add_argument("--operation-digest", required=True)
    parser.add_argument("--plugin-config", action="append", default=[])
    args = parser.parse_args(argv)
    catalog = compile_installed_catalog()
    services: dict[str, object] = {}
    if args.plugin_config:
        loaded = load_runtime_plugin_contributions(
            catalog,
            parse_plugin_config_assignments(tuple(args.plugin_config)),
            mode="local_worker",
            state_root=args.state_root.expanduser().absolute(),
        )
        services.update(loaded.tool_services)
    router = build_hardened_worker_router(
        state_root=args.state_root,
        operation_id=args.operation_id,
        operation_digest=args.operation_digest,
        operation_catalog=catalog,
        tool_services=services,
    )
    for line in __import__("sys").stdin:
        request_id: Any = None
        try:
            request = parse_rpc_line(line)
            request_id = request.get("id") if isinstance(request, dict) else None
            response = router.handle(request)
        except Exception as error:
            response = rpc_error(request_id, error)
        if response is not None:
            print(json.dumps(response, separators=(",", ":"), sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["HardenedWorkerMCPRouter", "build_hardened_worker_router", "main"]
