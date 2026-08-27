"""Stdio MCP proxy for the local TCAD dispatcher."""

from __future__ import annotations

import argparse
import json
import socket
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tcad-control-mcp")
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        raise ValueError("proxy timeout must be positive")
    for line in sys.stdin.buffer:
        request_id = None
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("request must be a JSON object")
            request_id = request.get("id")
            response = _forward(args.socket, line, timeout=args.timeout)
        except Exception as error:
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32000, "message": str(error)},
            }
        if response is not None:
            print(json.dumps(response, separators=(",", ":"), sort_keys=True), flush=True)
    return 0


def _forward(socket_path: Path, raw: bytes, *, timeout: float) -> dict | None:
    request = json.loads(raw)
    notification = request.get("method") == "notifications/initialized"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(str(socket_path.expanduser().absolute()))
        client.sendall(raw.rstrip(b"\r\n") + b"\n")
        if notification:
            return None
        with client.makefile("rb") as stream:
            response_raw = stream.readline(16 * 1024 * 1024 + 1)
    if not response_raw or len(response_raw) > 16 * 1024 * 1024:
        raise RuntimeError("execution controller returned no bounded response")
    response = json.loads(response_raw)
    if not isinstance(response, dict):
        raise RuntimeError("execution controller response is not an object")
    return response


if __name__ == "__main__":
    raise SystemExit(main())
