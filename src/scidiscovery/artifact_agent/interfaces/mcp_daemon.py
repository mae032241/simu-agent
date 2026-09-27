"""Unix-socket deployment entry point for the SciDiscovery control service."""

from __future__ import annotations

from ...agent_execution_settings import load_settings

import argparse
import re
import threading
import signal
import os
from collections import OrderedDict
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Callable

from scidiscovery.plugin_runtime.transport import UnixSocketDaemon
from ...operation_contract import DiagnosticError

from .mcp import build_root_router, rpc_error
from .mcp_platform_context import platform_context
from .mcp_proxy import SCHEDULER_PROXY_FIELD, CLIENT_HEARTBEAT, CLIENT_DISCONNECT
from ..service.scheduler_bindings import SchedulerBindingService
from ..service import StateMaintenanceLock
from ..service.instance_maintenance import InstanceMaintenance
from ..service.execution_collection import ExecutionCollection, open_collection_executions
from ..runtime import open_runtime
from scidiscovery.operations.catalog import compile_installed_catalog
from ..runtime_plugin_bindings import (
    load_runtime_plugin_contributions,
    parse_plugin_config_assignments,
    runtime_process_summary,
    write_runtime_process_summary,
)


_PROXY = re.compile(r"^sch_[0-9a-f]{32}$")


class RootBrokerRouter:
    """Bind one stateful Root facade to each hidden scheduler proxy."""

    def __init__(
        self,
        builder: Callable[[str], Any],
        *,
        maintenance: StateMaintenanceLock | None = None,
        instance_maintenance: InstanceMaintenance | None = None,
        max_cached_routers: int = 128,
        client_bindings: SchedulerBindingService | None = None,
    ) -> None:
        if type(max_cached_routers) is not int or max_cached_routers < 1:
            raise ValueError("max_cached_routers must be positive")
        self.builder = builder
        self.client_bindings = client_bindings
        self.maintenance = maintenance
        self.instance_maintenance = instance_maintenance
        self.max_cached_routers = max_cached_routers
        self._routers: OrderedDict[str, Any] = OrderedDict()
        self._lock = threading.Lock()

    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        request_id = request.get("id")
        proxy_id = request.get(SCHEDULER_PROXY_FIELD)
        if not isinstance(proxy_id, str) or not _PROXY.fullmatch(proxy_id):
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32000,
                    "message": "missing or invalid scheduler proxy binding",
                },
            }
        clean = dict(request)
        del clean[SCHEDULER_PROXY_FIELD]
        exclusive = (
            clean.get("method") == "tools/call"
            and isinstance(clean.get("params"), dict)
            and (clean["params"].get("name") == "instance_close" or (
                clean["params"].get("name") == "scid_call"
                and isinstance(clean["params"].get("arguments"), dict)
                and clean["params"]["arguments"].get("name") == "instance_close"))
        )
        context = nullcontext()
        if self.instance_maintenance is not None:
            # RootMCPRouter owns the short EX for instance_close. Never nest
            # shared -> exclusive around that call.
            context = nullcontext() if exclusive else self.instance_maintenance.global_guard()
        elif self.maintenance is not None:
            context = (
                self.maintenance.exclusive(blocking=False)
                if exclusive
                else self.maintenance.shared()
            )
        with context:
            method = clean.get("method")
            if method in (CLIENT_HEARTBEAT, CLIENT_DISCONNECT):
                if self.client_bindings is not None:
                    if method == CLIENT_HEARTBEAT:
                        self.client_bindings.client_heartbeat(session_key=proxy_id)
                    else:
                        self.client_bindings.disconnect_client(session_key=proxy_id)
                if method == CLIENT_DISCONNECT:
                    with self._lock:
                        self._routers.pop(proxy_id, None)
                return {"jsonrpc": "2.0", "id": request_id, "result": {}}
            try:
                worker_call = method == "tools/call" and platform_context(clean).worker
            except DiagnosticError as error:
                return rpc_error(request_id, error)
            if method == "tools/call" and self.client_bindings is not None and not worker_call:
                # instance_close owns an exclusive gate internally; protect this
                # short lease write separately to avoid nesting shared -> exclusive.
                with self.instance_maintenance.global_guard() if exclusive and self.instance_maintenance else nullcontext():
                    self.client_bindings.register_client(session_key=proxy_id)
            return self._router(proxy_id).handle(clean)

    def _router(self, proxy_id: str) -> Any:
        with self._lock:
            router = self._routers.get(proxy_id)
            if router is None:
                router = self.builder(proxy_id)
                self._routers[proxy_id] = router
                while len(self._routers) > self.max_cached_routers:
                    self._routers.popitem(last=False)
            else:
                self._routers.move_to_end(proxy_id)
            return router


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scidiscovery-control-daemon")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--approval-secret-file", type=Path, required=True)
    parser.add_argument("--approval-base-url", default="http://127.0.0.1:8765")
    parser.add_argument(
        "--worker-backend", choices=("local", "hardened"), default="local"
    )
    parser.add_argument("--local-workspace-root", type=Path)
    parser.add_argument("--plugin-config", action="append", default=[])
    parser.add_argument("--runtime-summary", type=Path, required=True)
    parser.add_argument("--max-connections", type=int, default=16)
    args = parser.parse_args(argv)
    project_root = args.project_root.expanduser().resolve()
    state_root = args.state_root.expanduser().absolute()
    if args.worker_backend == "local" and args.local_workspace_root is None:
        parser.error("--local-workspace-root is required for the local backend")
    try:
        plugin_configs = parse_plugin_config_assignments(tuple(args.plugin_config))
        agent_settings = load_settings(os.environ.get("SCID_AGENT_SETTINGS_FILE"))
        catalog = compile_installed_catalog()
        contributions = load_runtime_plugin_contributions(
            catalog,
            plugin_configs,
            mode="control",
            state_root=state_root,
        )
        write_runtime_process_summary(
            args.runtime_summary,
            runtime_process_summary(catalog, contributions, mode="control"),
        )
    except ValueError as error:
        parser.error(str(error))
    creation_lock = threading.RLock()
    maintenance = StateMaintenanceLock(
        state_root / "maintenance.lock", shared_group=True
    )
    instance_maintenance = InstanceMaintenance(state_root, maintenance=maintenance)
    with maintenance.shared():
        client_bindings = SchedulerBindingService(state_root / "database" / "scheduler-bindings.sqlite3")
        collection = ExecutionCollection(open_collection_executions(state_root),
            plugin_configs={key: str(value) for key, value in plugin_configs.items()})
    startup_runtime = open_runtime(
        project_root=project_root,
        state_root=state_root,
        shared_group=True,
        worker_backend=args.worker_backend,
        local_workspace_root=args.local_workspace_root,
        agent_settings=agent_settings,
    )
    with maintenance.shared():
        startup_runtime.runs.reconcile_expired_active()
    router = RootBrokerRouter(
        lambda proxy_id: build_root_router(
            project_root=project_root,
            state_root=state_root,
            approval_secret_file=args.approval_secret_file,
            approval_base_url=args.approval_base_url,
            shared_group=True,
            execution_adapters=contributions.execution_adapters,
            scheduler_session_key=proxy_id,
            scheduler_creation_lock=creation_lock,
            worker_backend=args.worker_backend,
            local_workspace_root=args.local_workspace_root,
            execution_collection=collection,
            agent_settings=agent_settings,
            unified=True,
            worker_plugin_configs=plugin_configs,
        ),
        maintenance=maintenance,
        instance_maintenance=instance_maintenance,
        client_bindings=client_bindings,
    )
    def stop(*_):
        collection.close()
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        os.kill(os.getpid(), signal.SIGTERM)
    previous_term = signal.signal(signal.SIGTERM, stop)
    try:
        UnixSocketDaemon(args.socket, router, max_connections=args.max_connections,
            socket_mode=0o660).serve_forever()
    finally:
        collection.close()
        signal.signal(signal.SIGTERM, previous_term)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["RootBrokerRouter", "main"]
