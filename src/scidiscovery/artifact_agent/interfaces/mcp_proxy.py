"""Credential-free stdio proxy for the SciDiscovery control socket."""

from __future__ import annotations

import argparse
import json
import socket
import sys
import signal
import threading
import time
import uuid
from pathlib import Path

from .mcp import parse_rpc_line, rpc_error
from .mcp_platform_context import platform_context
from ..service.engineering_diagnostics import exception_facts


from ...plugin_runtime.transport import MAX_RESPONSE_BYTES, forward_request
SCHEDULER_PROXY_FIELD = "_scidiscovery_scheduler_proxy"
CLIENT_HEARTBEAT = "scidiscovery/client-heartbeat"
CLIENT_DISCONNECT = "scidiscovery/client-disconnect"
HEARTBEAT_INTERVAL_SECONDS = 20
LIFECYCLE_TIMEOUT_SECONDS = 3


def _client_event(socket_path, proxy_id, method):
    response = forward_request(socket_path, json.dumps({
        "jsonrpc": "2.0", "id": "client-lifecycle", "method": method,
        SCHEDULER_PROXY_FIELD: proxy_id,
    }).encode(), timeout=LIFECYCLE_TIMEOUT_SECONDS)
    if response and "error" in response:
        raise RuntimeError(response["error"].get("message", "client lifecycle rejected"))


def _heartbeat(socket_path, proxy_id, stopped):
    failed = False
    while not stopped.wait(HEARTBEAT_INTERVAL_SECONDS):
        try:
            _client_event(socket_path, proxy_id, CLIENT_HEARTBEAT)
            failed = False
        except Exception as error:
            if not failed:
                print(json.dumps(exception_facts(error, layer="root_proxy", action="client_heartbeat"),
                                 ensure_ascii=False), file=sys.stderr, flush=True)
            failed = True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scidiscovery-mcp-proxy")
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        raise ValueError("proxy timeout must be positive")
    proxy_id = f"sch_{uuid.uuid4().hex}"
    stopped = threading.Event()
    heartbeat = None
    def terminate(*_):
        raise SystemExit(0)
    previous_term = signal.signal(signal.SIGTERM, terminate)
    try:
        for line in sys.stdin.buffer:
            request_id = None
            try:
                request = parse_rpc_line(line)
                request_id = request.get("id")
                worker_call = (request.get("method") == "tools/call"
                               and platform_context(request).worker)
                if request.get("method") == "tools/call" and heartbeat is None and not worker_call:
                    heartbeat = threading.Thread(target=_heartbeat, args=(args.socket, proxy_id, stopped), daemon=True)
                    heartbeat.start()
                response = forward_request(
                    args.socket,
                    bind_scheduler_proxy(line, proxy_id),
                    timeout=args.timeout,
                )
            except Exception as error:
                error.engineering = exception_facts(error, layer="root_proxy", action="forward_request")
                error.engineering["response_timeout_seconds"] = args.timeout
                print(json.dumps(error.engineering, ensure_ascii=False), file=sys.stderr, flush=True)
                response = rpc_error(request_id, error)
            if response is not None:
                print(
                    json.dumps(response, separators=(",", ":"), sort_keys=True),
                    flush=True,
                )
    finally:
        stopped.set()
        if heartbeat is not None:
            heartbeat.join(timeout=LIFECYCLE_TIMEOUT_SECONDS + 1)
            try:
                _client_event(args.socket, proxy_id, CLIENT_DISCONNECT)
            except Exception as error:
                print(json.dumps(exception_facts(error, layer="root_proxy", action="client_disconnect"),
                                 ensure_ascii=False), file=sys.stderr, flush=True)
        signal.signal(signal.SIGTERM, previous_term)
    return 0


def bind_scheduler_proxy(raw: bytes, proxy_id: str) -> bytes:
    if not isinstance(proxy_id, str) or not proxy_id.startswith("sch_"):
        raise ValueError("scheduler proxy binding is invalid")
    request = json.loads(raw)
    if not isinstance(request, dict):
        raise ValueError("request must be a JSON object")
    if request.get("method") in (CLIENT_HEARTBEAT, CLIENT_DISCONNECT):
        raise ValueError("client lifecycle is transport-managed")
    if SCHEDULER_PROXY_FIELD in request:
        raise ValueError("scheduler proxy binding is transport-managed")
    request[SCHEDULER_PROXY_FIELD] = proxy_id
    return json.dumps(request, separators=(",", ":"), sort_keys=True).encode("utf-8")


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "MAX_RESPONSE_BYTES",
    "SCHEDULER_PROXY_FIELD",
    "bind_scheduler_proxy",
    "forward_request",
    "main",
]
