"""Direct stdio MCP for one trusted-local compiled Operation Run."""

from __future__ import annotations

import argparse
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ...operations.catalog import CompiledCatalog, compile_installed_catalog
from ...operations.tooling import (
    WorkerToolDefinition,
    operation_local_worker_tools,
)
from ..operation_tool_context import OperationToolContext
from ..runtime_plugin_bindings import (
    load_runtime_plugin_contributions,
    parse_plugin_config_assignments,
)
from ..schema.refs import ActorRef
from ..service.artifacts import ArtifactService
from ..service.local_workspace import LocalTrustedBackend, WorkspaceError
from ..service.local_workspace import workspace_input_filename
from ..service.run_outputs import RunCheckerError, RunOutputError
from ..service.runs import RunService, RunStateConflict
from ..service.scheduler_bindings import SchedulerBindingService
from .mcp import MCPRouter
from .mcp_worker_protocol import LIFECYCLE_WORKER_TOOLS, WorkerToolError


class LocalWorkerMCPRouter:
    """Expose three lifecycle actions and this Operation's real domain tools."""

    def __init__(
        self,
        runs: RunService,
        *,
        operation_id: str,
        operation_digest: str,
        tool_services: dict[str, object] | None = None,
    ) -> None:
        compiled = runs.operation_catalog.operation(operation_id)
        if compiled.digest != operation_digest or compiled.spec.executor.kind != "agent":
            raise ValueError("local Worker operation identity is invalid")
        self.runs = runs
        self.compiled = compiled
        self.operation_id = operation_id
        self.operation_digest = operation_digest
        self.tool_services = dict(tool_services or {})
        self._tools = {tool.name: tool for tool in LIFECYCLE_WORKER_TOOLS}
        self._registered: dict[str, WorkerToolDefinition] = {}
        for tool in operation_local_worker_tools(compiled):
            self._registered[tool.name] = tool
            self._tools[tool.name] = tool
        self._register_backend_tools()
        required = {
            service
            for tool in self._registered.values()
            for service in tool.required_services
        }
        self._missing_services = tuple(sorted(required - set(self.tool_services)))
        self._run_id: str | None = None
        self._workspace: Any | None = None
        self._completed = False
        self._tool_state: dict[str, dict[str, object]] = {}
        self._lock = threading.RLock()
        expected = set(runs.backend.assignment_tool_names(compiled))
        if set(self._tools) != expected:
            raise ValueError("Worker router differs from its backend tool projection")

    def _register_backend_tools(self) -> None:
        """Allow a backend router to add its declared transport tools."""

    def list_tools(self) -> list[dict[str, Any]]:
        return [self._tools[name].schema() for name in sorted(self._tools)]

    def call_tool(self, name: str, arguments: dict[str, Any] | None) -> Any:
        with self._lock:
            try:
                tool = self._tools[name]
            except KeyError as error:
                raise WorkerToolError(f"unknown worker tool: {name}") from error
            try:
                parsed = tool.input_model.model_validate(arguments or {}, strict=False)
            except ValidationError as error:
                raise WorkerToolError(f"invalid arguments for {name}: {error}") from error
            if name == "worker_open_assignment":
                return self._open()
            if self._run_id is None or self._workspace is None:
                raise WorkerToolError("worker_open_assignment must be called first")
            if self._completed:
                if name == "worker_submit_result":
                    return self._completed_result()
                raise WorkerToolError("this Run is already completed")
            if name == "worker_heartbeat":
                status = self.runs.heartbeat(self._run_id)
                return {"state": status.state, "remaining_seconds": _remaining(status.deadline_at)}
            if name == "worker_submit_result":
                state, diagnostics = self.runs.submit(self._run_id)
                self._completed = state == "completed"
                return self._completed_result() if self._completed else {
                    "state": state,
                    "diagnostics": list(diagnostics),
                }
            registered = self._registered.get(name)
            if registered is None:
                raise WorkerToolError(f"unknown local domain tool: {name}")
            try:
                if registered.handler is not None:
                    result = registered.handler(parsed)
                else:
                    assert registered.contextual_handler is not None
                    result = registered.contextual_handler(
                        parsed, self._context(name, registered)
                    )
            except RunCheckerError as error:
                status = self.runs.status(self._run_id)
                self.runs.record_failure(
                    self._run_id,
                    reason=f"compiled output checker failed: {error}",
                    expected_state="running",
                    expected_last_activity_at=status.last_activity_at,
                )
                return {"state": "failed", "diagnostics": []}
            except (RunOutputError, WorkspaceError) as error:
                details = getattr(error, "details", ()) or (
                    {"path": "$", "message": str(error), "type": "value_error"},
                )
                self.runs.record_activity(self._run_id, "output_rejected")
                return {"state": "rejected", "diagnostics": list(details)}
            except Exception as error:
                self.runs.record_activity(self._run_id, f"tool_failed:{name}")
                raise WorkerToolError("registered operation tool failed") from error
            self.runs.record_activity(self._run_id, f"tool_succeeded:{name}")
            return result

    def _open(self) -> dict[str, Any]:
        if self._completed:
            return {"state": "completed"}
        if self._missing_services:
            raise WorkerToolError(
                "required Operation runtime service is unavailable: "
                + ", ".join(self._missing_services)
            )
        if self._run_id is None:
            try:
                status, workspace = self.runs.open(
                    operation_id=self.operation_id,
                    operation_digest=self.operation_digest,
                )
            except RunStateConflict as error:
                raise WorkerToolError(str(error)) from error
            self._run_id = status.run_id
            self._workspace = workspace
        status = self.runs.status(self._run_id)
        return {
            "state": "opened",
            "workspace_path": str(self._workspace.root),
            "assignment_path": str(self._workspace.assignment_path),
            "output_directory": str(self._workspace.output_directory),
            "domain_workspace_path": (
                None
                if self._workspace.domain_workspace_path is None
                else str(self._workspace.domain_workspace_path)
            ),
            "remaining_seconds": _remaining(status.deadline_at),
        }

    def _completed_result(self) -> dict[str, Any]:
        assert self._run_id is not None
        receipt = self.runs.status(self._run_id).completion_receipt
        return {
            "state": "completed",
            "receipt": (
                None
                if receipt is None
                else {
                    "head_advance": receipt.head_advance,
                    "completed_at": receipt.completed_at,
                }
            ),
        }

    def _context(
        self, name: str, tool: WorkerToolDefinition
    ) -> OperationToolContext:
        assert self._run_id is not None and self._workspace is not None
        status = self.runs.status(self._run_id)
        inputs = {item.source_name: item for item in status.inputs}

        def read_input(source_name: str) -> bytes:
            try:
                return self.runs.artifacts.read(inputs[source_name].artifact_ref)
            except KeyError as error:
                raise ValueError("tool requested an undeclared Run input") from error

        def input_binding(source_name: str):
            try:
                return inputs[source_name]
            except KeyError as error:
                raise ValueError("tool requested an undeclared Run input") from error

        def input_path(source_name: str) -> Path:
            item = input_binding(source_name)
            path = self._workspace.root / "inputs" / workspace_input_filename(
                source_name, item.media_type
            )
            if not path.is_file() or path.is_symlink():
                raise ValueError("declared Run input is unavailable")
            return path

        def snapshot() -> tuple[str, ...]:
            compiled = self.compiled
            assert compiled.spec.limits is not None
            self.runs.validate_candidate(self._run_id)
            sealed = self.runs.backend.seal(
                self._run_id,
                max_files=compiled.spec.limits.max_files,
                max_bytes=compiled.spec.limits.max_output_bytes,
            )
            return tuple(item.relative_path for item in sealed.files)

        return OperationToolContext(
            services={
                key.partition(":")[2]: self.tool_services[key]
                for key in tool.required_services
                if key in self.tool_services
            },
            state=self._tool_state.setdefault(name, {}),
            workspace=self._workspace.root,
            output_directory=self._workspace.output_directory,
            output_collections=tuple(
                item.name for item in self.compiled.spec.outputs if item.collection is not None
            ),
            remaining_seconds=_remaining(status.deadline_at),
            _read_input=read_input,
            _input_path=input_path,
            _input_media_type=lambda source_name: input_binding(source_name).media_type,
            _input_ref=lambda source_name: input_binding(source_name).artifact_ref,
            _validate_outputs=lambda: self.runs.validate_candidate(self._run_id) and None,
            _record_activity=lambda activity: self.runs.record_activity(self._run_id, activity),
            _candidate_snapshot=snapshot,
        )


def build_local_worker_router(
    *,
    state_root: Path,
    operation_id: str,
    operation_digest: str,
    operation_catalog: CompiledCatalog | None = None,
    tool_services: dict[str, object] | None = None,
    local_workspace_root: Path | None = None,
) -> MCPRouter:
    state = state_root.expanduser().absolute()
    catalog = operation_catalog or compile_installed_catalog()
    artifacts = ArtifactService.open(
        cas_root=state / "artifacts",
        database_path=state / "database" / "artifact_agent.sqlite3",
    )
    if local_workspace_root is None:
        raise ValueError("local workspace root is required")
    backend = LocalTrustedBackend(local_workspace_root)
    scheduler_bindings = SchedulerBindingService(
        state / "database" / "scheduler-bindings.sqlite3"
    )
    runs = RunService(
        artifacts=artifacts,
        database_path=state / "database" / "runs.sqlite3",
        service_actor=ActorRef(actor_id="root_orchestrator", actor_type="service"),
        operation_catalog=catalog,
        backend=backend,
        scheduler_bindings=scheduler_bindings,
    )
    return MCPRouter(
        LocalWorkerMCPRouter(
            runs,
            operation_id=operation_id,
            operation_digest=operation_digest,
            tool_services=tool_services,
        ),
        name="scidiscovery-local-operation",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scidiscovery-local-worker-mcp")
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--operation-id", required=True)
    parser.add_argument("--operation-digest", required=True)
    parser.add_argument("--local-workspace-root", type=Path, required=True)
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
    router = build_local_worker_router(
        state_root=args.state_root,
        operation_id=args.operation_id,
        operation_digest=args.operation_digest,
        operation_catalog=catalog,
        tool_services=services,
        local_workspace_root=args.local_workspace_root,
    )
    for line in __import__("sys").stdin:
        request_id: Any = None
        try:
            request = json.loads(line)
            request_id = request.get("id") if isinstance(request, dict) else None
            if not isinstance(request, dict):
                raise ValueError("request must be a JSON object")
            response = router.handle(request)
        except Exception as error:
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32000, "message": str(error)},
            }
        if response is not None:
            print(json.dumps(response, separators=(",", ":"), sort_keys=True), flush=True)
    return 0


def _remaining(deadline_at: str) -> int:
    deadline = datetime.fromisoformat(deadline_at.removesuffix("Z") + "+00:00")
    return max(0, int((deadline - datetime.now(timezone.utc)).total_seconds()))


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["LocalWorkerMCPRouter", "build_local_worker_router", "main"]
