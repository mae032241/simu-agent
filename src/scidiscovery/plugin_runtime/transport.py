"""Generic JSON-RPC/MCP and bounded Unix socket transport; no action registry or admission."""
from __future__ import annotations

import errno
import fcntl
import json
import os
import socket
import stat
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

MAX_REQUEST_BYTES = 1024 * 1024
DEFAULT_IDLE_TIMEOUT_S = 5.0
DEFAULT_MAX_CONNECTIONS = 16
SOCKET_PROBE_TIMEOUT_S = 0.25


class UnixSocketDaemon:
    def __init__(
        self,
        socket_path: Path | str,
        router: Any,
        *,
        idle_timeout_s: float = DEFAULT_IDLE_TIMEOUT_S,
        max_connections: int = DEFAULT_MAX_CONNECTIONS,
        socket_mode: int = 0o600,
    ) -> None:
        if idle_timeout_s <= 0:
            raise ValueError("daemon idle timeout must be positive")
        if max_connections <= 0:
            raise ValueError("daemon connection limit must be positive")
        if socket_mode not in {0o600, 0o660}:
            raise ValueError("daemon socket mode must be 0600 or 0660")
        self.socket_path = Path(socket_path)
        self.router = router
        self.idle_timeout_s = idle_timeout_s
        self.max_connections = max_connections
        self.socket_mode = socket_mode

    def serve_forever(self) -> None:
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        with _exclusive_socket_lock(self.socket_path):
            _prepare_socket_path(self.socket_path)
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(str(self.socket_path))
                os.chmod(self.socket_path, self.socket_mode)
                owner = _socket_identity(self.socket_path)
                server.listen(self.max_connections)
                slots = threading.BoundedSemaphore(self.max_connections)
                workers = ThreadPoolExecutor(
                    max_workers=self.max_connections,
                    thread_name_prefix="scidiscovery-client",
                )
                try:
                    while True:
                        connection, _ = server.accept()
                        connection.settimeout(self.idle_timeout_s)
                        if not slots.acquire(blocking=False):
                            _reject_busy(connection)
                            continue
                        workers.submit(
                            self._serve_and_release,
                            connection,
                            slots,
                        )
                finally:
                    workers.shutdown(wait=True, cancel_futures=True)
                    _unlink_owned_socket(self.socket_path, owner)

    def _serve_and_release(
        self,
        connection: socket.socket,
        slots: threading.BoundedSemaphore,
    ) -> None:
        try:
            with connection:
                self._serve_connection(connection)
        finally:
            slots.release()

    def _serve_connection(self, connection: socket.socket) -> None:
        try:
            with connection.makefile("rwb") as stream:
                while True:
                    line = stream.readline(MAX_REQUEST_BYTES + 1)
                    if not line:
                        return
                    if len(line) > MAX_REQUEST_BYTES:
                        response = _error(
                            None,
                            -32600,
                            "request exceeds size limit",
                        )
                    else:
                        try:
                            request = json.loads(line)
                            if not isinstance(request, dict):
                                raise ValueError(
                                    "request must be a JSON object"
                                )
                            response = self.router.handle(request)
                        except (json.JSONDecodeError, ValueError) as exc:
                            response = _error(None, -32700, str(exc))
                    if response is not None:
                        stream.write(
                            json.dumps(
                                response,
                                separators=(",", ":"),
                                sort_keys=True,
                            ).encode("utf-8")
                            + b"\n"
                        )
                        stream.flush()
        except (TimeoutError, OSError):
            return


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


@contextmanager
def _exclusive_socket_lock(socket_path: Path) -> Iterator[None]:
    lock_path = socket_path.with_name(f"{socket_path.name}.lock")
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(
                f"daemon already owns socket lock: {lock_path}"
            ) from exc
        yield
    finally:
        os.close(descriptor)


def _prepare_socket_path(socket_path: Path) -> None:
    try:
        mode = socket_path.lstat().st_mode
    except FileNotFoundError:
        return
    if not stat.S_ISSOCK(mode):
        raise RuntimeError("daemon socket path exists and is not a socket")
    if _socket_is_live(socket_path):
        raise RuntimeError(f"daemon is already listening on {socket_path}")
    socket_path.unlink()


def _socket_is_live(socket_path: Path) -> bool:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
        probe.settimeout(SOCKET_PROBE_TIMEOUT_S)
        try:
            probe.connect(str(socket_path))
        except OSError as exc:
            if exc.errno in (errno.ECONNREFUSED, errno.ENOENT):
                return False
            raise RuntimeError(
                f"cannot safely determine socket ownership: {socket_path}"
            ) from exc
    return True


def _socket_identity(socket_path: Path) -> tuple[int, int]:
    status = socket_path.lstat()
    return status.st_dev, status.st_ino


def _unlink_owned_socket(
    socket_path: Path,
    expected: tuple[int, int],
) -> None:
    try:
        observed = _socket_identity(socket_path)
    except FileNotFoundError:
        return
    if observed == expected:
        socket_path.unlink()


def _reject_busy(connection: socket.socket) -> None:
    with connection:
        try:
            connection.sendall(
                json.dumps(
                    _error(None, -32000, "daemon connection limit reached"),
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")
                + b"\n"
            )
        except OSError:
            return


__all__ = [
    "DEFAULT_IDLE_TIMEOUT_S",
    "DEFAULT_MAX_CONNECTIONS",
    "MAX_REQUEST_BYTES",
    "UnixSocketDaemon",
]

from ..artifact_agent.schema.common import canonical_json
from ..operation_contract import DiagnosticError, contract_diagnostic
from .diagnostics import exception_facts
import time

PROTOCOL_VERSION = "2025-03-26"
MAX_RESPONSE_BYTES = 16 * 1024 * 1024

class MCPRouter:
    def __init__(self, router: Any, *, name: str) -> None:
        self.router = router
        self.name = name

    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        request_id = request.get("id") if isinstance(request, dict) else None
        try:
            if not isinstance(request, dict):
                raise DiagnosticError("invalid protocol request", details=(contract_diagnostic(
                    "invalid_protocol_request", phase="protocol", affected_action="tool_call",
                    message="Expected a JSON-RPC request object."),))
            method = request.get("method")
            if request.get("jsonrpc") != "2.0" or not isinstance(method, str):
                raise DiagnosticError("invalid protocol request", details=(contract_diagnostic(
                    "invalid_protocol_request", phase="protocol", affected_action="tool_call",
                    message="Expected JSON-RPC 2.0 and a string method."),))
            if method == "notifications/initialized":
                return None
            if method == "initialize":
                value = {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": self.name, "version": "1"},
                }
            elif method == "tools/list":
                value = {"tools": self.router.list_tools()}
            elif method == "tools/call":
                params = request.get("params", {})
                if not isinstance(params, dict) or not isinstance(params.get("name"), str):
                    raise DiagnosticError("invalid protocol parameters", details=(contract_diagnostic(
                        "invalid_protocol_parameters", phase="protocol", affected_action="tool_call",
                        message="tools/call requires a parameter object with a string tool name."),))
                result = self.router.call_tool(
                    str(params.get("name", "")), params.get("arguments")
                )
                value = {
                    "content": [
                        {
                            "type": "text",
                            "text": canonical_json(result).decode("utf-8"),
                        }
                    ],
                    "structuredContent": result,
                    "isError": False,
                }
            else:
                raise DiagnosticError("unknown protocol method", details=(contract_diagnostic(
                    "unknown_protocol_method", phase="protocol", affected_action="tool_call",
                    message="This JSON-RPC method is not declared by the server."),))
            return {"jsonrpc": "2.0", "id": request_id, "result": value}
        except Exception as error:
            return rpc_error(request_id, error)


def rpc_error(request_id: Any, error: Exception) -> dict[str, Any]:
    details = getattr(error, "details", ()) if isinstance(error, DiagnosticError) else ()
    public_engineering = getattr(error, "public_engineering", None)
    engineering = public_engineering if public_engineering is not None else getattr(error, "engineering", None)
    if not details:
        engineering = engineering or exception_facts(error, layer="mcp", action="tool_call")
        reason = engineering["causes"][0]
        details = (contract_diagnostic(
            "tool_rejected" if isinstance(error, DiagnosticError) else engineering["category"],
            phase="tool_execution", affected_action="tool_call",
            message=f"{reason['type']}: {reason['message']}", error_type=reason["type"],
        ),)
    if public_engineering is not None and "reference" in public_engineering:
        details = tuple({**item, "message": "Tool execution failed; read the diagnostic reference for details."}
                        for item in details)
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32000, "message": details[0]["message"],
                  "data": {"diagnostics": list(details),
                           **({"engineering": engineering} if engineering else {}),
                           **({"attempt": error.attempt} if getattr(error,"attempt",None) else {})}},
    }


def parse_rpc_line(raw: str | bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError) as error:
        raise DiagnosticError("invalid JSON-RPC", details=(contract_diagnostic(
            "invalid_protocol_request", phase="protocol", affected_action="tool_call",
            message="Expected a valid JSON-RPC request object."),)) from error
    if not isinstance(value, dict):
        raise DiagnosticError("invalid JSON-RPC", details=(contract_diagnostic(
            "invalid_protocol_request", phase="protocol", affected_action="tool_call",
            message="Expected a JSON-RPC request object."),))
    return value


def forward_request(socket_path: Path, raw: bytes, *, timeout: float) -> dict | None:
    request = json.loads(raw)
    notification = request.get("method") == "notifications/initialized"
    started = time.monotonic()
    deadline = started + timeout
    response_raw = bytearray()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            def remaining():
                value = deadline - time.monotonic()
                if value <= 0:
                    raise TimeoutError("proxy response deadline exhausted")
                client.settimeout(value)
            remaining()
            client.connect(str(socket_path.expanduser().absolute()))
            remaining()
            client.sendall(raw.rstrip(b"\r\n") + b"\n")
            if notification:
                return None
            while len(response_raw) <= MAX_RESPONSE_BYTES:
                remaining()
                chunk = client.recv(min(65536, MAX_RESPONSE_BYTES + 1 - len(response_raw)))
                if not chunk:
                    break
                response_raw.extend(chunk)
                if b"\n" in chunk:
                    break
    except TimeoutError as error:
        error.timeout = timeout
        error.timeout_kind = "proxy_response"
        error.elapsed_seconds = time.monotonic() - started
        raise
    if not response_raw or len(response_raw) > MAX_RESPONSE_BYTES:
        raise RuntimeError("control service returned no bounded response")
    response = json.loads(response_raw)
    if not isinstance(response, dict):
        raise RuntimeError("control service response is not an object")
    return response
