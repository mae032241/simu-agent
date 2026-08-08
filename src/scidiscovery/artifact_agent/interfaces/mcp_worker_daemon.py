"""Independent worker broker for task-bound SciDiscovery MCP calls."""

from __future__ import annotations

import argparse
import re
import threading
from pathlib import Path
from typing import Any

from scidiscovery.interfaces.daemon import UnixSocketDaemon

from ..runtime import ArtifactAgentRuntime, open_runtime, read_secret_file
from .mcp import MCPRouter
from .mcp_worker import WorkerMCPRouter
from .mcp_worker_proxy import PROXY_ID_FIELD, WORKER_ID_FIELD


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}$")


class WorkerBrokerRouter:
    """Route a fixed transport identity to the worker-only MCP surface."""

    def __init__(self, runtime: ArtifactAgentRuntime) -> None:
        self.runtime = runtime
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
    parser.add_argument("--max-connections", type=int, default=16)
    args = parser.parse_args(argv)
    runtime = open_runtime(
        project_root=args.project_root.expanduser().resolve(),
        state_root=args.state_root.expanduser().absolute(),
        task_token_secret=read_secret_file(
            args.task_secret_file,
            label="task token",
        ),
        actor_id="worker_broker",
        shared_group=True,
    )
    UnixSocketDaemon(
        args.socket,
        WorkerBrokerRouter(runtime),
        max_connections=args.max_connections,
        socket_mode=0o660,
    ).serve_forever()
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
