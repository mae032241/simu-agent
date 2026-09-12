"""Credential-free stdio proxy for the SciDiscovery control socket."""

from __future__ import annotations

import argparse
import json
import socket
import sys
import uuid
from pathlib import Path

from .mcp import parse_rpc_line, rpc_error


MAX_RESPONSE_BYTES = 16 * 1024 * 1024
SCHEDULER_PROXY_FIELD = "_scidiscovery_scheduler_proxy"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scidiscovery-mcp-proxy")
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        raise ValueError("proxy timeout must be positive")
    proxy_id = f"sch_{uuid.uuid4().hex}"
    for line in sys.stdin.buffer:
        request_id = None
        try:
            request = parse_rpc_line(line)
            request_id = request.get("id")
            response = forward_request(
                args.socket,
                bind_scheduler_proxy(line, proxy_id),
                timeout=args.timeout,
            )
        except Exception as error:
            response = rpc_error(request_id, error)
        if response is not None:
            print(
                json.dumps(response, separators=(",", ":"), sort_keys=True),
                flush=True,
            )
    return 0


def forward_request(socket_path: Path, raw: bytes, *, timeout: float) -> dict | None:
    request = json.loads(raw)
    notification = request.get("method") == "notifications/initialized"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(str(socket_path.expanduser().absolute()))
        client.sendall(raw.rstrip(b"\r\n") + b"\n")
        if notification:
            return None
        with client.makefile("rb") as stream:
            response_raw = stream.readline(MAX_RESPONSE_BYTES + 1)
    if not response_raw or len(response_raw) > MAX_RESPONSE_BYTES:
        raise RuntimeError("control service returned no bounded response")
    response = json.loads(response_raw)
    if not isinstance(response, dict):
        raise RuntimeError("control service response is not an object")
    return response


def bind_scheduler_proxy(raw: bytes, proxy_id: str) -> bytes:
    if not isinstance(proxy_id, str) or not proxy_id.startswith("sch_"):
        raise ValueError("scheduler proxy binding is invalid")
    request = json.loads(raw)
    if not isinstance(request, dict):
        raise ValueError("request must be a JSON object")
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
