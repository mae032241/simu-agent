"""Stdio MCP proxy for the local TCAD dispatcher."""

from __future__ import annotations

import argparse
import json
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
            from scidiscovery.plugin_runtime.transport import rpc_error
            from scidiscovery.plugin_runtime.diagnostics import exception_facts
            error.engineering = exception_facts(error, layer="tcad_proxy", action="forward")
            error.engineering["response_timeout_seconds"] = args.timeout
            print(json.dumps(error.engineering), file=sys.stderr, flush=True)
            response = rpc_error(request_id, error)
        if response is not None:
            print(json.dumps(response, separators=(",", ":"), sort_keys=True), flush=True)
    return 0


def _forward(socket_path: Path, raw: bytes, *, timeout: float) -> dict | None:
    from scidiscovery.plugin_runtime.transport import forward_request
    return forward_request(socket_path, raw, timeout=timeout)


if __name__ == "__main__":
    raise SystemExit(main())
