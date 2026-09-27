"""Direct stdio MCP for one trusted-local compiled Operation Run."""

from __future__ import annotations

import argparse
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ...operation_contract import DiagnosticError, validation_diagnostics, contract_diagnostic
from ...operations.tooling import parse_tool_arguments
from ...operations.spec import freeze_json, json_projection

from ...operations.catalog import CompiledCatalog, compile_installed_catalog
from ...operations.tooling import (
    WorkerToolDefinition,
    operation_local_worker_tools,
    operation_tool_contracts,
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
from .mcp import MCPRouter, parse_rpc_line, rpc_error
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
        self._tool_schemas = tuple(
            freeze_json(self._tools[name].schema()) for name in sorted(self._tools)
        )
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
        self._active_attempt = None
        self._attempt_finished = False
        self._attempt_sources = {}
        expected = set(runs.backend.assignment_tool_names(compiled))
        if set(self._tools) != expected:
            raise ValueError("Worker router differs from its backend tool projection")

    def _register_backend_tools(self) -> None:
        """Allow a backend router to add its declared transport tools."""

    def list_tools(self) -> list[dict[str, Any]]:
        return json_projection(self._tool_schemas)

    def call_tool(self, name: str, arguments: dict[str, Any] | None) -> Any:
        with self._lock:
            self._active_attempt = None
            self._attempt_sources = {}
            self._attempt_finished = False
            try:
                tool = self._registered.get(name)
                if tool is not None and tool.record_attempts and self._run_id is not None:
                    self._active_attempt = self.runs.begin_tool_attempt(self._run_id, tool, arguments)
                result = self._call_tool(name, arguments)
                if self._active_attempt and not self._attempt_finished:
                    raise WorkerToolError("declared tool omitted its outcome receipt")
                return result
            except Exception as error:
                failure = error if isinstance(error, DiagnosticError) else WorkerToolError(
                    "Worker call failed", details=(contract_diagnostic(
                        "runtime_failure", phase="tool_execution", affected_action="tool_call",
                        message="Worker call failed.", error_type=type(error).__name__),))
                if self._active_attempt and not self._attempt_finished:
                    try:
                        failure.attempt, failure.details = self._finish_attempt(rejected=True, diagnostics=failure.details)
                    except Exception as receipt_error:
                        failure = WorkerToolError("tool receipt could not be retained", details=(contract_diagnostic(
                            "attempt_recording_failed", phase="tool_execution", affected_action="tool_call",
                            message="The call has no terminal receipt; its outcome is unknown."),))
                        self._record_tool_failure(name, failure)
                        raise failure from receipt_error
                self._record_tool_failure(name, failure)
                if failure is error: raise
                raise failure from error
            finally:
                self._active_attempt = None
                self._attempt_sources = {}

    def _finish_attempt(self, **values):
        if self._active_attempt is None: return None
        reference, diagnostics = self.runs.finish_tool_attempt(self._run_id, self._active_attempt,
            sources=self._attempt_sources, **values)
        self._attempt_finished = True
        if values.get("result_status") not in {None, "computed"}:
            self.runs.record_activity(self._run_id, "tool_not_computed", diagnostic={
                "category":"tool_failed", "tool_name":self._active_attempt["tool_name"],
                "details":diagnostics})
        return reference, diagnostics

    def _source_read(self, alias):
        if self._active_attempt is None or alias in self._attempt_sources: return
        descriptor = self.runs.source_descriptor(self.runs.status(self._run_id), alias)
        self._attempt_sources[alias] = {"schema_version":1,
            "artifact_ref":descriptor.artifact_ref.model_dump(mode="json"),
            "port_name":descriptor.port_name}
        self.runs.record_tool_attempt_read(self._run_id, self._active_attempt, self._attempt_sources)

    def _record_tool_failure(self, name: str, error: WorkerToolError) -> None:
        if self._run_id is None or self.runs.status(self._run_id).state != "running":
            return
        self.runs.record_activity(self._run_id, "tool_failed", diagnostic={
            "category": "tool_failed", "tool_name": name,
            "details": error.details or (contract_diagnostic("tool_rejected",
                phase="tool_execution", affected_action="tool_call"),),
        })

    def _call_tool(self, name: str, arguments: dict[str, Any] | None) -> Any:
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
                    category=error.category,
                )
                return {"state": "failed", "diagnostics": []}
            except (RunOutputError, WorkspaceError) as error:
                if isinstance(error, RunOutputError) and error.recorded:
                    details = error.details
                else:
                    diagnostic = self.runs.record_activity(self._run_id, "output_rejected",
                        diagnostic=self.runs._rejection_diagnostic(self.runs.status(self._run_id), error))
                    details = diagnostic.get("details", ())
                return {"state": "rejected", "diagnostics": list(details)}
            except DiagnosticError:
                raise
            except Exception as error:
                raise WorkerToolError("registered operation tool failed", details=(contract_diagnostic(
                    "runtime_failure", phase="tool_execution", affected_action="tool_call",
                    message="Registered tool execution failed.", error_type=type(error).__name__,
                ),)) from error
            self.runs.record_activity(self._run_id, f"tool_succeeded:{name}")
            return result

    def _open(self) -> dict[str, Any]:
        if self._missing_services:
            raise WorkerToolError(
                "required Operation runtime service is unavailable: "
                + ", ".join(self._missing_services)
            )
        terminal = self._run_id is not None and self.runs.status(self._run_id).state in {"completed", "failed"}
        if self._run_id is None or terminal:
            try:
                status, workspace = self.runs.open(
                    operation_id=self.operation_id,
                    operation_digest=self.operation_digest,
                )
            except RunStateConflict as error:
                if terminal:
                    return {"state": self.runs.status(self._run_id).state}
                from ...operations.tooling import tool_evidence_ports
                if not tool_evidence_ports(self.compiled) or str(error) != "no exact queued Run is available":
                    raise WorkerToolError(str(error)) from error
                status, workspace = self.runs.reopen(operation_id=self.operation_id, operation_digest=self.operation_digest)
            self._run_id = status.run_id
            self._workspace = workspace
            self._completed = False
            self._tool_state.clear()
        status = self.runs.status(self._run_id)
        return {
            "state": "opened",
            "workspace_path": str(self._workspace.root),
            "assignment_path": str(self._workspace.assignment_path),
            "tool_contracts": self._assignment_tool_contracts(),
            "output_directory": str(self._workspace.output_directory),
            "domain_workspace_path": (
                None
                if self._workspace.domain_workspace_path is None
                else str(self._workspace.domain_workspace_path)
            ),
            "remaining_seconds": _remaining(status.deadline_at),
        }

    def _assignment_tool_contracts(self) -> dict[str, Any]:
        # Old assignments may lack additive metadata; never replace their files
        # or use a newer contract to reopen an old Run.
        compiled = self.runs._compiled(self.runs.status(self._run_id))
        assignment = json.loads(self._workspace.assignment_path.read_bytes())
        if "tool_contracts" in assignment:
            return assignment["tool_contracts"]
        return operation_tool_contracts(compiled, self.runs.backend.assignment_tool_names(compiled))

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

        def read_evidence(alias):
            if alias in inputs:
                return read_input(alias)
            return self.runs.read_tool_evidence(status, alias)

        def execution_scope(alias):
            from ..service.executions import ExecutionService
            item = input_binding(alias)
            if not tool.evidence_ports or item.port_name != 'execution_result':
                raise ValueError('tool has no execution scope')
            return ExecutionService.resolve_result_scope(artifacts=self.runs.artifacts,
                database_path=self.runs.database_path.parent/'executions.sqlite3', result_ref=item.artifact_ref)

        return OperationToolContext(
            services={
                key.partition(":")[2]: self.tool_services[key]
                for key in (*tool.required_services, *tool.optional_services)
                if key in self.tool_services
            },
            state=self._tool_state.setdefault(name, {}),
            workspace=self._workspace.root,
            output_directory=self._workspace.output_directory,
            output_collections=tuple(
                item.name for item in self.compiled.spec.outputs if item.collection is not None
            ),
            remaining_seconds=_remaining(status.deadline_at),
            _io_budget=(lambda **values: self.runs.tool_io_budget(self._run_id, **values)) if tool.evidence_ports else None,
            _read_evidence=read_evidence,
            _prior_source_bindings=lambda: self.runs.prior_source_bindings(status),
            _source_descriptor=lambda alias: self.runs.source_descriptor(status, alias),
            _source_read=self._source_read if tool.record_attempts else None,
            _finish_attempt=self._finish_attempt if tool.record_attempts else None,
            _list_evidence=lambda: self.runs.tool_evidence(self._run_id),
            _execution_scope=execution_scope if tool.evidence_ports else None,
            _accept_evidence=(lambda **values: self.runs.accept_tool_evidence(self._run_id, tool_name=tool.name, allowed_ports=tool.evidence_ports, **values)) if tool.evidence_ports else None,
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


def _load_operation_services(catalog, operation_id, assignments, state_root):
    tools = operation_local_worker_tools(catalog.operation(operation_id))
    required = {name.partition(':')[0] for tool in tools for name in tool.required_services}
    optional = {name.partition(':')[0] for tool in tools for name in tool.optional_services}
    services = {}
    for plugin_id, path in assignments.items():
        try:
            loaded = load_runtime_plugin_contributions(catalog, {plugin_id: path},
                mode='local_worker', state_root=state_root)
        except Exception:
            if plugin_id not in optional or plugin_id in required:
                raise
            # Preserve the concrete configuration/adapter error in MCP stderr;
            # unavailable optional tooling must not prevent opening the analysis.
            import logging
            logging.getLogger(__name__).exception('Optional Worker service unavailable: %s', plugin_id)
        else:
            services.update(loaded.tool_services)
    return services


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
        services.update(_load_operation_services(catalog, args.operation_id,
            parse_plugin_config_assignments(tuple(args.plugin_config)),
            args.state_root.expanduser().absolute()))
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
            request = parse_rpc_line(line)
            request_id = request.get("id") if isinstance(request, dict) else None
            response = router.handle(request)
        except Exception as error:
            response = rpc_error(request_id, error)
        if response is not None:
            print(json.dumps(response, separators=(",", ":"), sort_keys=True), flush=True)
    return 0


def _remaining(deadline_at: str) -> int:
    deadline = datetime.fromisoformat(deadline_at.removesuffix("Z") + "+00:00")
    return max(0, int((deadline - datetime.now(timezone.utc)).total_seconds()))


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["LocalWorkerMCPRouter", "build_local_worker_router", "main"]
