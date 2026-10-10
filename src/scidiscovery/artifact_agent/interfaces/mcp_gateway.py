"""One bounded MCP surface; contracts and handlers stay in their existing owners.

Codex supplies session/thread metadata outside model-controlled tool arguments.
This is a LocalTrusted transport boundary, not protection against a hostile OS user.
"""

from __future__ import annotations

import threading
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ...agent_execution_settings import canonical_model_id
from ...operation_contract import DiagnosticError, validation_diagnostics
from ...operations.tooling import parse_tool_arguments
from ..service.worker_connections import WorkerConnections, WorkerNotAttached
from ..service.run_records import RunStateConflict
from .mcp import MCPRouter, rpc_error
from .mcp_local_worker import LocalWorkerMCPRouter
from ..worker_services import load_operation_services
from ..runtime import validate_worker_backend
from .mcp_platform_context import PlatformContext as _Context, platform_context as _context


GATEWAY_TOOLS = ("scid_catalog", "scid_describe", "scid_call")


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CatalogInput(_Input):
    surface: Literal["research", "execution"] = Field(default="research",
        description="Root interfaces: research is normal scheduling; execution explicitly selects standalone Effect diagnostics/recovery. Active task ownership and internal Operation restrictions still apply. Workers use research.")
    kind: Literal["operations", "interfaces"] = "operations"
    view: Literal["summary", "index", "facets", "matches"] = Field(default="summary",
        description="Root: summary = IDs + exact purposes; index/facets/matches = structural navigation.")
    limit: int = Field(default=20, ge=1, le=100)
    before: str | None = Field(default=None, max_length=512)
    dimension: Literal["consequence", "executor_kind", "input_schema"] | None = Field(default=None,
        description="facets: omit for P1 structural dimensions/counts; set to page values.")
    where: dict[str, str | list[str]] | None = Field(default=None,
        description="matches: P1 keys consequence, executor_kind, input_schema; AND keys, OR values. Values are exact and case-sensitive: for example executor_kind='agent' (lowercase). Use facets only when the value is unknown; zero filtered matches do not mean the public catalog is empty.")


class DescribeInput(_Input):
    surface: Literal["research", "execution"] = Field(default="research",
        description="Root interfaces: research is normal scheduling; execution explicitly selects standalone Effect diagnostics/recovery. Active task ownership and internal Operation restrictions still apply. Workers use research.")
    name: str = Field(min_length=1, max_length=256)
    view: Literal["full", "invoke"] = Field(
        default="invoke",
        description="Operations: invoke is the default self-contained caller contract; no separate operation_invoke description is needed. full adds execution diagnostics. Interfaces always return their complete input contract for either view.",
    )


class CallInput(_Input):
    surface: Literal["research", "execution"] = Field(default="research",
        description="Root interfaces: research is normal scheduling; execution explicitly selects standalone Effect diagnostics/recovery. Active task ownership and internal Operation restrictions still apply. Workers use research.")
    name: str = Field(min_length=1, max_length=256)
    arguments: dict[str, Any] = Field(default_factory=dict,
        description="Match the exact scid_describe contract.")


class AttachInput(_Input):
    name: str = Field(min_length=1, max_length=256, description="Exact queued Run semantic name.")
    thread_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,128}$",
        description="Native child thread ID from platform spawn or worker_identity; never a role or task nickname.")


class BootstrapInput(_Input):
    dispatch_token: str | None = Field(default=None, min_length=1, max_length=4096,
        description="Control-issued exact task bootstrap from Root; omit for an already attached assignment.")


_OPEN = {"name": "worker_open_assignment",
    "description": "Open after Root confirms worker_attach for this actual child. Prepared helpers open directly. A legacy dispatch_token remains supported; never select a Run.",
    "inputSchema": BootstrapInput.model_json_schema()}


_DECLARATIONS = (
    ("scid_catalog", "List authorized names and purposes; no full contracts.", CatalogInput),
    ("scid_describe", "Read a known capability's exact contract directly; use catalog only to discover names. Selected Operation invoke views include their complete caller contract.", DescribeInput),
    ("scid_call", "Call an authorized capability by its exact contract.", CallInput),
)
_ATTACH = {"name": "worker_attach", "description": "Bind the actual spawned child thread to an exact queued Run; Root only. Calling again with a corrected native ID replaces an unopened queued binding. Once assignment is opened, ownership cannot change.",
           "inputSchema": AttachInput.model_json_schema()}
_IDENTITY = {"name": "worker_identity", "description": "Read this Worker's platform-supplied thread ID and model profile for scheduler attachment; does not claim a Run.",
             "inputSchema": _Input.model_json_schema()}


class UnifiedMCPRouter:
    def __init__(self, root, *, plugin_configs=None, worker_backend="local"):
        validate_worker_backend(worker_backend)
        self.root = root
        self.facade = root.facade
        self.connections = self.facade.runs.worker_connections
        self.plugin_configs = plugin_configs or {}
        self._workers = {}
        self._run_state = {}
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
        participant = None
        try:
            status = self.connections.resolve(platform_session=context.session, thread_id=context.thread)
        except WorkerNotAttached:
            status, participant = self.connections.participant(platform_session=context.session,
                thread_id=context.thread, parent_thread=context.parent_thread,
                admit=context.subagent_kind in (None, "thread_spawn"),
                model=context.model, reasoning_effort=context.effort)
        profile = status.execution_profile
        expected = (self.connections.helper_profile(status, participant) if participant is not None
                    else profile["profile"] if profile is not None else None)
        if expected is None or (
            canonical_model_id(context.model), context.effort
        ) != (
            canonical_model_id(expected["model"]), expected["reasoning_effort"]
        ):
            if participant is None and status.state in {"queued", "running"}:
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
                services = load_operation_services(self.facade.runs.operation_catalog, status.operation_id,
                    self.plugin_configs, self.facade.runs.database_path.parent.parent)
                if self.facade.runs.operation_catalog.operation(status.operation_id).spec.executor.capability is not None:
                    from ..service.experiment_execution import bind_experiment_services
                    bind_experiment_services(self.facade.runs,
                        self.facade.runs.operation_catalog.operation(status.operation_id), services, run_id=status.run_id)
                worker = LocalWorkerMCPRouter(self.facade.runs, operation_id=status.operation_id,
                    operation_digest=status.operation_digest, tool_services=services, run_id=status.run_id,
                    trusted_caller=(context.session, context.thread), participant=participant)
                shared = self._run_state.setdefault(status.run_id, (threading.RLock(), {}))
                worker._lock, worker._tool_state = shared
                worker._previous_run_id = self.connections.previous_run(
                    run_id=status.run_id, platform_session=context.session, thread_id=context.thread)
                # A reused platform thread has only one currently bound workspace.
                for old in tuple(self._workers):
                    if old[:2] == key[:2]:
                        del self._workers[old]
                self._workers[key] = worker
        return worker, status

    def _interfaces(self, context, surface="research"):
        if context.worker:
            if surface != "research":
                raise DiagnosticError("execution surface is available only to Root")
            try:
                worker = self._worker(context)[0]
                return [*([] if worker.is_helper else [_IDENTITY]), *worker.list_tools()]
            except WorkerNotAttached:
                return [_IDENTITY, _OPEN]
        return [*self.root.list_tools(surface=surface), *([_ATTACH] if surface == "research" else [])]

    def catalog(self, context, values):
        if values.surface != "research" and values.kind != "interfaces":
            raise DiagnosticError("execution surface requires kind=interfaces")
        if not context.worker and values.kind == "operations":
            return self.root.call_tool("operation_catalog", {
                "limit": values.limit, "before": values.before, "view": values.view,
                "dimension": values.dimension, "where": values.where})
        if values.view != "summary" or values.dimension is not None or values.where is not None:
            raise DiagnosticError("navigation views are available only for Root operations; Worker and interface catalogs are unchanged")
        entries = sorted(self._interfaces(context, values.surface), key=lambda item: item["name"])
        if values.before is not None:
            entries = [x for x in entries if x["name"] > values.before]
        selected = entries[:values.limit]
        return {"entries": [{"name": x["name"], "purpose": x["description"]} for x in selected],
                "next_before": selected[-1]["name"] if len(entries) > len(selected) else None}

    def describe(self, context, values):
        name = values.name
        declaration = next((item for item in _DECLARATIONS if item[0] == name), None)
        if declaration is not None:
            entry_name, description, model = declaration
            return {"name": entry_name, "description": description,
                    "inputSchema": model.model_json_schema()}
        if context.worker and values.surface != "research":
            raise DiagnosticError("execution surface is available only to Root")
        if context.worker and name == "worker_identity":
            return _IDENTITY
        if context.worker and name == "worker_open_assignment":
            return _OPEN
        for tool in self._interfaces(context, values.surface):
            if tool["name"] == name:
                return tool
        if not context.worker and values.surface == "research":
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
            if "operation_digest" in operations[0] and operations[0]["operation_digest"] != compiled.digest:
                raise DiagnosticError("Operation contract selection changed during projection")
            return {
                **full,
                "view": "invoke",
                "operations": [operation_invoke_contract(
                    operations[0], revision_policy=operation_revision_policy(compiled.spec),
                )],
            }
        raise DiagnosticError("capability is not available in this Worker assignment")

    def _record_bound_open_failure(self, context):
        # Attribution comes only from actual native coordinates, never a token claim.
        try:
            status = self.connections.resolve(platform_session=context.session, thread_id=context.thread)
        except (WorkerNotAttached, RunStateConflict):
            return
        self.facade.runs.reconcile_dispatch_attention(status.run_id, code="dispatch_open_failed")

    def call(self, context, values):
        if context.worker and values.surface != "research":
            raise DiagnosticError("execution surface is available only to Root")
        if context.worker:
            if values.name == "worker_open_assignment" and "dispatch_token" in values.arguments:
                parsed = _parse(BootstrapInput, values.arguments)
                if parsed.dispatch_token is not None:
                    from .worker_bootstrap import attach
                    try:
                        attach(self.facade, self.connections, context, parsed.dispatch_token)
                    except (DiagnosticError, RunStateConflict):
                        self._record_bound_open_failure(context)
                        raise
                values = values.model_copy(update={"arguments": {}})
            if values.name == "worker_identity":
                try:
                    _, participant = self.connections.participant(platform_session=context.session,
                        thread_id=context.thread, parent_thread=context.parent_thread)
                except WorkerNotAttached:
                    participant = None
                if participant is not None:
                    raise DiagnosticError("Internal helpers use their scientific subtask; attachment identity is not exposed")
                _parse(_Input, values.arguments)
                return {"thread_id": context.thread, "model": context.model,
                        "reasoning_effort": context.effort}
            try:
                worker, status = self._worker(context)
            except WorkerNotAttached as error:
                if values.name == "worker_open_assignment":
                    raise DiagnosticError("awaiting_attachment: awaiting scheduler attachment; stop this startup turn and wait for Root attached-start via the same child; do not retry open, select a Run or spawn a replacement") from error
                raise
            except (DiagnosticError, RunStateConflict):
                if values.name == "worker_open_assignment":
                    self._record_bound_open_failure(context)
                raise
            if values.name not in {x["name"] for x in worker.list_tools()}:
                raise DiagnosticError("capability is not available in this Worker assignment")
            if status.state in {"failed", "completed"}:
                if values.name == "worker_open_assignment":
                    return {"state": status.state}
                raise DiagnosticError("bound Run is terminal; scheduler must attach a new Run before more work")
            try:
                reply = worker.call_tool(values.name, values.arguments)
            except (DiagnosticError, RunStateConflict):
                if values.name == "worker_open_assignment":
                    self._record_bound_open_failure(context)
                raise
            if values.name == "worker_open_assignment" and not worker.is_helper and reply.get("state") == "opened":
                self.facade.runs.reconcile_dispatch_attention(status.run_id, opened=True)
            if values.name == "worker_submit_result" and reply.get("state") == "completed":
                with self._lock:
                    for key in tuple(self._workers):
                        if key[2] == status.run_id:
                            self._workers.pop(key)
                    self._run_state.pop(status.run_id, None)
            return reply
        if values.name == "worker_attach" and values.surface == "research":
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
                    # An exact existing connection can recover without renewed scheduling
                    # authority. A new attachment must belong to this generation's intent.
                    with runs._connect() as connection:
                        attached = connection.execute("SELECT platform_session, thread_id FROM worker_connections WHERE run_id=?", (run_id,)).fetchone()
                    if attached is not None and tuple(attached) == (context.session, parsed.thread_id):
                        self.connections.attach(run_id=run_id, platform_session=context.session, thread_id=parsed.thread_id)
                    else:
                        with self.facade.scheduling_guard(continuation=('run', run_id)) as generation:
                            self.facade.bindings.require_dispatch_intent(instance_id=instance_id, run_id=run_id,
                                session_key=self.facade.session_key, generation=generation)
                            try:
                                self.connections.attach(run_id=run_id, platform_session=context.session, thread_id=parsed.thread_id)
                            except (DiagnosticError, RunStateConflict):
                                runs.reconcile_dispatch_attention(run_id, code="dispatch_attach_failed")
                                raise
            return {"state": "attached", "name": parsed.name}
        # Existing Root handlers remain the sole authority for bindings, approvals and Run lifecycle.
        return self.root.call_tool(values.name, values.arguments, surface=values.surface)


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
