"""Independent worker broker for task-bound SciDiscovery MCP calls."""

from __future__ import annotations

import argparse
import re
import threading
from contextlib import nullcontext
from pathlib import Path
from typing import Any

from scidiscovery.interfaces.daemon import UnixSocketDaemon

from ..runtime import ArtifactAgentRuntime, open_runtime, read_secret_file
from ..service import StateMaintenanceLock
from .mcp import MCPRouter
from .mcp_worker import WorkerMCPRouter
from .mcp_worker_proxy import PROXY_ID_FIELD, WORKER_ID_FIELD


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}$")


class _PeriodicDebugReconciler:
    """Run bounded adapter cleanup even when no worker request arrives."""

    def __init__(
        self,
        service: Any,
        *,
        interval_seconds: float = 10.0,
        maintenance: StateMaintenanceLock | None = None,
    ) -> None:
        if not 0.01 <= interval_seconds <= 300:
            raise ValueError("debug reconcile interval is out of bounds")
        self.service = service
        self.interval_seconds = interval_seconds
        self.maintenance = maintenance
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name="scidiscovery-tcad-debug-reconciler",
            daemon=True,
        )

    def start(self) -> None:
        self._reconcile()
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=min(2.0, self.interval_seconds + 0.25))

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self._reconcile()

    def _reconcile(self) -> None:
        try:
            context = (
                self.maintenance.shared()
                if self.maintenance is not None
                else nullcontext()
            )
            with context:
                self.service.reconcile(limit=16)
        except Exception:
            # Rows and external bindings remain durable for the next bounded pass.
            pass


class WorkerBrokerRouter:
    """Route a fixed transport identity to the worker-only MCP surface."""

    def __init__(
        self,
        runtime: ArtifactAgentRuntime,
        *,
        maintenance: StateMaintenanceLock | None = None,
    ) -> None:
        self.runtime = runtime
        self.maintenance = maintenance
        self._routers: dict[tuple[str, str], MCPRouter] = {}
        self._lock = threading.Lock()

    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        request_id = request.get("id")
        worker_id = request.get(WORKER_ID_FIELD)
        proxy_id = request.get(PROXY_ID_FIELD)
        if not isinstance(worker_id, str) or not _IDENTIFIER.fullmatch(worker_id):
            return _error(request_id, "missing or invalid worker transport identity")
        if not isinstance(proxy_id, str) or not _IDENTIFIER.fullmatch(proxy_id):
            return _error(request_id, "missing or invalid worker proxy binding")
        clean_request = dict(request)
        del clean_request[WORKER_ID_FIELD]
        del clean_request[PROXY_ID_FIELD]
        context = (
            self.maintenance.shared()
            if self.maintenance is not None
            else nullcontext()
        )
        with context:
            if self.runtime.tcad_debug is not None:
                self.runtime.tcad_debug.reconcile(limit=4)
            return self._router(worker_id, proxy_id).handle(clean_request)

    def _router(self, worker_id: str, proxy_id: str) -> MCPRouter:
        key = (worker_id, proxy_id)
        with self._lock:
            router = self._routers.get(key)
            if router is None:
                router = MCPRouter(
                    WorkerMCPRouter(
                        self.runtime.tasks,
                        worker_id=worker_id,
                        proxy_id=proxy_id,
                        tcad_debug=self.runtime.tcad_debug,
                    ),
                    name="scidiscovery-worker",
                )
                self._routers[key] = router
            return router


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scidiscovery-worker-daemon")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--task-secret-file", type=Path, required=True)
    parser.add_argument("--tcad-socket", type=Path)
    parser.add_argument("--tcad-command-config", type=Path)
    parser.add_argument(
        "--tcad-debug-reconcile-interval", type=float, default=10.0
    )
    parser.add_argument("--max-connections", type=int, default=16)
    args = parser.parse_args(argv)
    if not 0.01 <= args.tcad_debug_reconcile_interval <= 300:
        parser.error("TCAD debug reconcile interval must be between 0.01 and 300")
    if args.tcad_socket is not None and args.tcad_command_config is not None:
        parser.error("choose either --tcad-socket or --tcad-command-config")
    tcad_debug_adapter = None
    if args.tcad_command_config is not None:
        from tcad_artifact.command_adapter import CommandTCADExecutorAdapter
        from tcad_artifact.debug_adapter import TCADDevelopmentDebugBridge

        base_adapter = CommandTCADExecutorAdapter.from_file(
            args.tcad_command_config,
            local_result_root=args.state_root / "executor-results",
        )
        tcad_debug_adapter = TCADDevelopmentDebugBridge(base_adapter)
    elif args.tcad_socket is not None:
        from tcad_artifact.debug_adapter import TCADDevelopmentDebugBridge
        from tcad_artifact.execution_adapter import TCADExecutorAdapter

        tcad_debug_adapter = TCADDevelopmentDebugBridge(
            TCADExecutorAdapter(args.tcad_socket)
        )
    runtime = open_runtime(
        project_root=args.project_root.expanduser().resolve(),
        state_root=args.state_root.expanduser().absolute(),
        task_token_secret=read_secret_file(
            args.task_secret_file,
            label="task token",
        ),
        actor_id="worker_broker",
        shared_group=True,
        tcad_debug_adapter=tcad_debug_adapter,
    )
    reconciler = (
        _PeriodicDebugReconciler(
            runtime.tcad_debug,
            interval_seconds=args.tcad_debug_reconcile_interval,
            maintenance=runtime.maintenance,
        )
        if runtime.tcad_debug is not None
        else None
    )
    if reconciler is not None:
        reconciler.start()
    try:
        UnixSocketDaemon(
            args.socket,
            WorkerBrokerRouter(runtime, maintenance=runtime.maintenance),
            max_connections=args.max_connections,
            socket_mode=0o660,
        ).serve_forever()
    finally:
        if reconciler is not None:
            reconciler.stop()
    return 0


def _error(request_id: Any, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32000, "message": message},
    }


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["WorkerBrokerRouter", "main"]
