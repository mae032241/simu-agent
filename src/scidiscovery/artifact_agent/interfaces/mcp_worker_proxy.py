"""Stateful stdio boundary for one role-bound worker process."""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import uuid
from pathlib import Path
from typing import Any, Callable

from .mcp_proxy import forward_request


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}$")
WORKER_ID_FIELD = "_scidiscovery_worker_id"
PROXY_ID_FIELD = "_scidiscovery_proxy_id"


class _AutomaticLeaseKeeper:
    """Renew one claimed task while its role-bound stdio proxy is alive."""

    def __init__(
        self,
        *,
        socket_path: Path,
        worker_id: str,
        proxy_id: str,
        timeout: float,
        interval: float,
        forward: Callable[..., dict[str, Any] | None] = forward_request,
    ) -> None:
        if interval <= 0:
            raise ValueError("heartbeat interval must be positive")
        self.socket_path = socket_path
        self.worker_id = worker_id
        self.proxy_id = proxy_id
        self.timeout = timeout
        self.interval = interval
        self.forward = forward
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def observe(
        self, request: dict[str, Any], response: dict[str, Any] | None
    ) -> None:
        """Start after a successful claim and stop after successful completion."""

        tool_name = _tool_name(request)
        state = _structured_state(response)
        if tool_name == "worker_claim_task" and state == "claimed":
            self.start()
        elif tool_name in {"worker_finalize", "worker_finalize_file"} and state == "completed":
            self.stop()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run,
            name=f"scidiscovery-heartbeat-{self.proxy_id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=min(1.0, self.timeout))

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            request = {
                "jsonrpc": "2.0",
                "id": f"auto-heartbeat-{uuid.uuid4().hex}",
                "method": "tools/call",
                "params": {"name": "worker_heartbeat", "arguments": {}},
            }
            raw = json.dumps(
                request, separators=(",", ":"), sort_keys=True
            ).encode("utf-8")
            try:
                response = self.forward(
                    self.socket_path,
                    bind_worker_identity(raw, self.worker_id, self.proxy_id),
                    timeout=self.timeout,
                )
            except Exception:
                # The task remains bounded by its absolute deadline. A transient
                # broker error must not terminate the scientific worker process.
                continue
            if response is not None and response.get("error") is not None:
                # A terminal or replaced claim cannot be renewed.
                self._stop.set()
                return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scidiscovery-worker-mcp-proxy")
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--heartbeat-interval", type=float, default=240.0)
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        raise ValueError("proxy timeout must be positive")
    if args.heartbeat_interval <= 0:
        raise ValueError("heartbeat interval must be positive")
    if not _IDENTIFIER.fullmatch(args.worker_id):
        raise ValueError("worker ID is invalid")
    proxy_id = f"pxy_{uuid.uuid4().hex}"
    lease_keeper = _AutomaticLeaseKeeper(
        socket_path=args.socket,
        worker_id=args.worker_id,
        proxy_id=proxy_id,
        timeout=args.timeout,
        interval=args.heartbeat_interval,
    )

    try:
        for line in sys.stdin.buffer:
            request_id = None
            request: dict[str, Any] | None = None
            try:
                decoded = json.loads(line)
                if not isinstance(decoded, dict):
                    raise ValueError("request must be a JSON object")
                request = decoded
                request_id = request.get("id")
                raw = bind_worker_identity(line, args.worker_id, proxy_id)
                response = forward_request(args.socket, raw, timeout=args.timeout)
            except Exception as error:
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32000, "message": str(error)},
                }
            if request is not None:
                lease_keeper.observe(request, response)
            if response is not None:
                print(
                    json.dumps(response, separators=(",", ":"), sort_keys=True),
                    flush=True,
                )
    finally:
        lease_keeper.stop()
    return 0


def _tool_name(request: dict[str, Any]) -> str | None:
    if request.get("method") != "tools/call":
        return None
    params = request.get("params")
    if not isinstance(params, dict):
        return None
    name = params.get("name")
    return name if isinstance(name, str) else None


def _structured_state(response: dict[str, Any] | None) -> str | None:
    if not isinstance(response, dict) or response.get("error") is not None:
        return None
    result = response.get("result")
    if not isinstance(result, dict):
        return None
    structured = result.get("structuredContent")
    if not isinstance(structured, dict):
        return None
    state = structured.get("state")
    return state if isinstance(state, str) else None


def bind_worker_identity(raw: bytes, worker_id: str, proxy_id: str) -> bytes:
    if not _IDENTIFIER.fullmatch(worker_id):
        raise ValueError("worker ID is invalid")
    if not _IDENTIFIER.fullmatch(proxy_id):
        raise ValueError("proxy ID is invalid")
    request = json.loads(raw)
    if not isinstance(request, dict):
        raise ValueError("request must be a JSON object")
    if WORKER_ID_FIELD in request or PROXY_ID_FIELD in request:
        raise ValueError("worker binding is transport-managed")
    request[WORKER_ID_FIELD] = worker_id
    request[PROXY_ID_FIELD] = proxy_id
    return json.dumps(
        request,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "PROXY_ID_FIELD",
    "WORKER_ID_FIELD",
    "bind_worker_identity",
    "main",
]
