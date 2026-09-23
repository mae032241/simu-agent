"""One bounded MCP surface; contracts and handlers stay in their existing owners.

Codex supplies session/thread metadata outside model-controlled tool arguments.
This is a LocalTrusted transport boundary, not protection against a hostile OS user.
"""

from __future__ import annotations

import re
import hashlib
import threading
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ...agent_execution_settings import canonical_model_id
from ...operation_contract import DiagnosticError, validation_diagnostics
from ...operations.tooling import parse_tool_arguments
from ..service.worker_connections import WorkerConnections, WorkerNotAttached
from .mcp import MCPRouter, rpc_error
from .mcp_local_worker import LocalWorkerMCPRouter, _load_operation_services
from .mcp_hardened_worker import HardenedWorkerMCPRouter


GATEWAY_TOOLS = ("scid_catalog", "scid_describe", "scid_call")


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CatalogInput(_Input):
    kind: Literal["operations", "interfaces"] = "operations"
    limit: int = Field(default=20, ge=1, le=100)
    before: str | None = Field(default=None, max_length=256)


class DescribeInput(_Input):
    name: str = Field(min_length=1, max_length=256)
    view: Literal["full", "invoke"] = Field(
        default="full",
        description="full preserves the existing complete interface or Operation contract; invoke is available only for Operations and retains every field needed to prepare and interpret a legal call.",
    )


class CallInput(_Input):
    name: str = Field(min_length=1, max_length=256)
    arguments: dict[str, Any] = Field(default_factory=dict,
        description="Arguments matching this entry's exact scid_describe contract.")


class AttachInput(_Input):
    name: str = Field(min_length=1, max_length=256, description="Exact queued Run semantic name.")
    thread_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,128}$",
        description="Native child thread ID from platform spawn or worker_identity; never a role or task nickname.")


_DECLARATIONS = (
    ("scid_catalog", "List authorized capabilities by name and purpose; no full contracts.", CatalogInput),
    ("scid_describe", "Read one capability's exact contract before calling it.", DescribeInput),
    ("scid_call", "Call an authorized capability using its exact contract; return its ordinary result.", CallInput),
)
_ATTACH = {"name": "worker_attach", "description": "Bind the actual spawned child thread to an exact queued Run; Root only.",
           "inputSchema": AttachInput.model_json_schema()}
_IDENTITY = {"name": "worker_identity", "description": "Read this Worker's platform-supplied thread ID and model profile for scheduler attachment; does not claim a Run.",
             "inputSchema": _Input.model_json_schema()}


@dataclass(frozen=True)
class _Context:
    session: str
    thread: str
    worker: bool
    model: str | None
    effort: str | None


def _context(request):
    meta = request.get("params", {}).get("_meta", {}).get("x-codex-turn-metadata", {})
    session, thread, source = (meta.get(key) for key in ("session_id", "thread_id", "thread_source"))
    if (not all(isinstance(x, str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", x) for x in (session, thread))
            or source not in {"user", "subagent"}
            or (source == "user" and session != thread)
            or (source == "subagent" and session == thread)):
        raise DiagnosticError("trusted platform session/thread metadata is required")
    return _Context(session, thread, source == "subagent", meta.get("model"), meta.get("reasoning_effort"))


class UnifiedMCPRouter:
    def __init__(self, root, *, plugin_configs=None, worker_backend="local"):
        self.root = root
        self.facade = root.facade
        self.connections = WorkerConnections(self.facade.runs)
        self.plugin_configs = plugin_configs or {}
        self.worker_backend = worker_backend
        self._workers = {}
        self._lock = threading.RLock()

    def handle(self, request):
        if not isinstance(request, dict):
            return rpc_error(None, DiagnosticError("expected a JSON-RPC request object"))
        try:
            context = _context(request) if request.get("method") == "tools/call" else None
            return MCPRouter(_ScopedSurface(self, context), name="scidiscovery").handle(request)
        except Exception as error:
            return rpc_error(request.get("id"), error)

    def _worker(self, context):
        status = self.connections.resolve(platform_session=context.session, thread_id=context.thread)
        profile = status.execution_profile
        expected = profile["profile"] if profile is not None else None
        if expected is None or (
            canonical_model_id(context.model), context.effort
        ) != (
            canonical_model_id(expected["model"]), expected["reasoning_effort"]
        ):
            if status.state in {"queued", "running"}:
                self.facade.runs.record_failure(
                    status.run_id,
                    reason=(
                        "Worker platform model/effort do not match the bound Run profile: "
                        f"expected={expected!r}, observed={{'model': {context.model!r}, "
                        f"'reasoning_effort': {context.effort!r}}}"
                    ),
                    category="worker_profile_mismatch",
                    expected_state=status.state,
                    expected_last_activity_at=status.last_activity_at,
                )
            raise DiagnosticError("Worker platform model/effort do not match the bound Run profile")
        key = (context.session, context.thread, status.run_id)
        with self._lock:
            worker = self._workers.get(key)
            if worker is None:
                services = _load_operation_services(self.facade.runs.operation_catalog, status.operation_id,
                    self.plugin_configs, self.facade.runs.database_path.parent.parent)
                cls = LocalWorkerMCPRouter if self.worker_backend == "local" else HardenedWorkerMCPRouter
                worker = cls(self.facade.runs, operation_id=status.operation_id,
                    operation_digest=status.operation_digest, tool_services=services, run_id=status.run_id)
                if self.worker_backend == "local":
                    worker._previous_run_id = self.connections.previous_run(
                        run_id=status.run_id, platform_session=context.session, thread_id=context.thread)
                if self.worker_backend == "hardened":
                    worker._transport_owner = "transport_" + hashlib.sha256(
                        "\0".join(key).encode()).hexdigest()
                # A reused platform thread has only one currently bound workspace.
                for old in tuple(self._workers):
                    if old[:2] == key[:2]:
                        del self._workers[old]
                self._workers[key] = worker
        return worker, status

    def _interfaces(self, context):
        if context.worker:
            try:
                return [_IDENTITY, *self._worker(context)[0].list_tools()]
            except WorkerNotAttached:
                return [_IDENTITY]
        return [*self.root.list_tools(), _ATTACH]

    def catalog(self, context, values):
        if not context.worker and values.kind == "operations":
            return self.root.call_tool("operation_catalog", {
                "limit": values.limit, "before": values.before, "view": "summary"})
        entries = sorted(self._interfaces(context), key=lambda item: item["name"])
        if values.before is not None:
            entries = [x for x in entries if x["name"] > values.before]
        selected = entries[:values.limit]
        return {"entries": [{"name": x["name"], "purpose": x["description"]} for x in selected],
                "next_before": selected[-1]["name"] if len(entries) > len(selected) else None}

    def describe(self, context, values):
        name = values.name
        declaration = next((item for item in _DECLARATIONS if item[0] == name), None)
        if declaration is not None:
            if values.view != "full":
                raise DiagnosticError('scid_describe view="invoke" is supported only for Operations')
            entry_name, description, model = declaration
            return {"name": entry_name, "description": description,
                    "inputSchema": model.model_json_schema()}
        if context.worker and name == "worker_identity":
            if values.view != "full":
                raise DiagnosticError('scid_describe view="invoke" is supported only for Operations')
            return _IDENTITY
        for tool in self._interfaces(context):
            if tool["name"] == name:
                if values.view != "full":
                    raise DiagnosticError('scid_describe view="invoke" is supported only for Operations')
                return tool
        if not context.worker:
            full = self.root.call_tool(
                "operation_catalog",
                {"operation_id": name, "view": "detail", "scope": "all"},
            )
            if values.view == "full":
                return full
            from .mcp_response_views import operation_invoke_contract, operation_revision_policy
            operations = full.get("operations") or []
            if len(operations) != 1:
                raise DiagnosticError("Operation contract selection did not return one exact item")
            compiled = self.facade._operation_catalog.operation(name)
            if operations[0].get("operation_digest") != compiled.digest:
                raise DiagnosticError("Operation contract selection changed during projection")
            return {
                **full,
                "view": "invoke",
                "operations": [operation_invoke_contract(
                    operations[0], revision_policy=operation_revision_policy(compiled.spec)
                )],
            }
        raise DiagnosticError("capability is not available in this Worker assignment")

    def call(self, context, values):
        if context.worker:
            if values.name == "worker_identity":
                _parse(_Input, values.arguments)
                return {"thread_id": context.thread, "model": context.model,
                        "reasoning_effort": context.effort}
            worker, status = self._worker(context)
            if values.name not in {x["name"] for x in worker.list_tools()}:
                raise DiagnosticError("capability is not available in this Worker assignment")
            if status.state in {"failed", "completed"}:
                if values.name == "worker_open_assignment":
                    return {"state": status.state}
                raise DiagnosticError("bound Run is terminal; scheduler must attach a new Run before more work")
            reply = worker.call_tool(values.name, values.arguments)
            if values.name == "worker_submit_result" and reply.get("state") == "completed":
                with self._lock:
                    self._workers.pop((context.session, context.thread, status.run_id), None)
            return reply
        if values.name == "worker_attach":
            parsed = _parse(AttachInput, values.arguments)
            if parsed.thread_id == context.thread:
                raise DiagnosticError("Root cannot attach itself as a Worker")
            run_id = self.facade._resolve("run", parsed.name)
            runs = self.facade.runs
            with runs.instance_maintenance.global_guard():
                instance_id = self.facade._instance_id()
                with runs.instance_maintenance.guard(instance_id):
                    runs.scheduler_bindings.require_active_instance(instance_id=instance_id)
                    if runs.status(run_id).instance_id != instance_id:
                        raise DiagnosticError("Run belongs to another research instance")
                    self.connections.attach(run_id=run_id, platform_session=context.session, thread_id=parsed.thread_id)
            return {"state": "attached", "name": parsed.name}
        # Existing Root handlers remain the sole authority for bindings, approvals and Run lifecycle.
        return self.root.call_tool(values.name, values.arguments)


def _parse(model, arguments):
    try:
        return parse_tool_arguments(model, arguments)
    except ValidationError as error:
        raise DiagnosticError("arguments do not match this entry's contract",
            details=validation_diagnostics(error, schema=model.model_json_schema())) from error


class _ScopedSurface:
    def __init__(self, gateway, context):
        self.gateway, self.context = gateway, context

    def list_tools(self):
        return [{"name": name, "description": description, "inputSchema": model.model_json_schema()}
                for name, description, model in _DECLARATIONS]

    def call_tool(self, name, arguments):
        if self.context is None:
            raise DiagnosticError("platform call context is missing")
        models = {name: model for name, _, model in _DECLARATIONS}
        if name not in models:
            raise DiagnosticError("use scid_catalog, scid_describe or scid_call")
        value = _parse(models[name], arguments)
        if name == "scid_catalog":
            return self.gateway.catalog(self.context, value)
        if name == "scid_describe":
            return self.gateway.describe(self.context, value)
        return self.gateway.call(self.context, value)
