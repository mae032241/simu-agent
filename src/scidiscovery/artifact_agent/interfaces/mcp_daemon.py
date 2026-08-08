"""Unix-socket deployment entry point for the SciDiscovery control service."""

from __future__ import annotations

import argparse
import re
import threading
from pathlib import Path
from typing import Any, Callable

from scidiscovery.interfaces.daemon import UnixSocketDaemon

from .mcp import build_root_router
from .mcp_proxy import SCHEDULER_PROXY_FIELD
from ..transforms import load_transform_adapters


_PROXY = re.compile(r"^sch_[0-9a-f]{32}$")


class RootBrokerRouter:
    """Bind one stateful Root facade to each hidden scheduler proxy."""

    def __init__(self, builder: Callable[[str], Any]) -> None:
        self.builder = builder
        self._routers: dict[str, Any] = {}
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
        return self._router(proxy_id).handle(clean)

    def _router(self, proxy_id: str) -> Any:
        with self._lock:
            router = self._routers.get(proxy_id)
            if router is None:
                router = self.builder(proxy_id)
                self._routers[proxy_id] = router
            return router


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scidiscovery-control-daemon")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--task-secret-file", type=Path, required=True)
    parser.add_argument("--approval-secret-file", type=Path, required=True)
    parser.add_argument("--approval-base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--tcad-socket", type=Path)
    parser.add_argument("--tcad-command-config", type=Path)
    parser.add_argument("--max-connections", type=int, default=16)
    args = parser.parse_args(argv)
    adapters = {}
    transform_adapters = load_transform_adapters()
    if args.tcad_socket is not None and args.tcad_command_config is not None:
        parser.error("choose either --tcad-socket or --tcad-command-config")
    if args.tcad_command_config is not None:
        from tcad_artifact.command_adapter import CommandTCADExecutorAdapter

        adapters["tcad"] = CommandTCADExecutorAdapter.from_file(
            args.tcad_command_config,
            local_result_root=args.state_root / "executor-results",
        )
    elif args.tcad_socket is not None:
        from tcad_artifact.execution_adapter import TCADExecutorAdapter

        adapters["tcad"] = TCADExecutorAdapter(args.tcad_socket)
    project_root = args.project_root.expanduser().resolve()
    state_root = args.state_root.expanduser().absolute()
    creation_lock = threading.RLock()
    router = RootBrokerRouter(
        lambda proxy_id: build_root_router(
            project_root=project_root,
            state_root=state_root,
            task_secret_file=args.task_secret_file,
            approval_secret_file=args.approval_secret_file,
            approval_base_url=args.approval_base_url,
            shared_group=True,
            execution_adapters=adapters,
            transform_adapters=transform_adapters,
            scheduler_session_key=proxy_id,
            scheduler_creation_lock=creation_lock,
        )
    )
    UnixSocketDaemon(
        args.socket,
        router,
        max_connections=args.max_connections,
        socket_mode=0o660,
    ).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["RootBrokerRouter", "main"]
