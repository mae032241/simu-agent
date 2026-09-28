"""Bounded, serial Codex stdio transport. No model, services or retry loop.

The caller owns persistence, deadlines for scientific work and resource supervision.
A transport timeout is an unknown outcome: this connection cannot send more work.
Only the child created here is terminated on close, never its process group.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import selectors
import subprocess
import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class HostLimits:
    rpc_timeout_seconds: float = 30
    termination_grace_seconds: float = 5
    frame_bytes: int = 8 * 1024 * 1024

    def __post_init__(self):
        for value in (self.rpc_timeout_seconds, self.termination_grace_seconds):
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError("host time limits must be finite and positive")
        if type(self.frame_bytes) is not int or self.frame_bytes < 1024:
            raise ValueError("host frame_bytes must be an integer >= 1024")


class HostError(RuntimeError):
    """Safe diagnostic; raw RPC evidence is delivered only to the private sink."""
    def __init__(self, code: str, *, method: str | None = None, rpc_code=None):
        self.code, self.method, self.rpc_code = code, method, rpc_code
        super().__init__((method + ":" if method else "") + code)


def config_flags(config: dict) -> list[str]:
    """CLI dotted keys are literal; JSON is used only for TOML-compatible values."""
    flags = []
    def visit(prefix, value):
        if isinstance(value, dict):
            for key, child in value.items():
                if not re.fullmatch(r"[A-Za-z0-9_-]+", key):
                    raise ValueError("unsupported_cli_config_key")
                visit(prefix + [key], child)
        else:
            flags.extend(["-c", ".".join(prefix) + "=" + json.dumps(value, allow_nan=False)])
    visit([], config)
    return flags


def rpc_diagnostic(error: dict) -> str:
    message = str(error.get("message", "")).lower()
    for text, code in (
        ("trusted platform session/thread metadata is required", "platform_identity_metadata_missing"),
        ("code-mode host closed its stdout", "native_code_mode_host_closed"),
        ("failed to load workspace requirements", "workspace_requirements_unavailable"),
        ("requires experimentalapi", "experimental_capability_required"),
    ):
        if text in message:
            return code
    if re.search(r"unknown variant|invalid variant|missing field|invalid type", message):
        return "request_schema_mismatch"
    return "request_rejected" if error.get("code") in (-32600, -32602) else "rpc_failure"


class AppServer:
    def __init__(self, child: subprocess.Popen, *, limits: HostLimits,
                 on_event: Callable[[dict], None], checkpoint: Callable[[], None] = lambda: None):
        if child.stdin is None or child.stdout is None:
            raise ValueError("app-server requires piped stdin/stdout")
        self.child, self.limits = child, limits
        self.on_event, self.checkpoint = on_event, checkpoint
        self.selector = selectors.DefaultSelector()
        os.set_blocking(child.stdin.fileno(), False)
        os.set_blocking(child.stdout.fileno(), False)
        self.selector.register(child.stdout, selectors.EVENT_READ)
        self.buffer = bytearray()
        self.counter = 0
        self.pending = None
        self.reply = None
        self.failed = False
        self.closed = False

    @classmethod
    def launch(cls, command: list[str], *, cwd: Path, environment: dict, stderr,
               limits: HostLimits, on_event: Callable[[dict], None], checkpoint=lambda: None):
        env = dict(environment)
        for key in ("CODEX_SESSION_ID", "CODEX_THREAD_ID"):
            env.pop(key, None)
        child = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=stderr, bufsize=0)
        try:
            return cls(child, limits=limits, on_event=on_event, checkpoint=checkpoint)
        except BaseException:
            child.terminate()
            try:
                child.wait(timeout=limits.termination_grace_seconds)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
            raise

    def _available(self):
        if self.closed or self.failed:
            raise HostError("host_connection_unusable")
        self.checkpoint()

    def _send(self, value: dict, deadline: float):
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False).encode() + b"\n"
        if len(raw) - 1 > self.limits.frame_bytes:
            raise HostError("protocol_message_limit")
        remaining = memoryview(raw)
        self.selector.register(self.child.stdin, selectors.EVENT_WRITE)
        try:
            while remaining:
                self._available()
                if time.monotonic() >= deadline:
                    raise HostError("rpc_timeout")
                ready = self.selector.select(min(.1, max(0, deadline - time.monotonic())))
                for key, _ in ready:
                    if key.fileobj is self.child.stdout:
                        self._read()
                    else:
                        count = os.write(self.child.stdin.fileno(), remaining)
                        remaining = remaining[count:]
        finally:
            self.selector.unregister(self.child.stdin)

    def _read(self):
        data = os.read(self.child.stdout.fileno(), min(65536, self.limits.frame_bytes + 1))
        if not data:
            raise HostError("app_server_closed")
        self.buffer.extend(data)
        while True:
            end = self.buffer.find(b"\n")
            if end < 0:
                if len(self.buffer) > self.limits.frame_bytes:
                    raise HostError("protocol_message_limit")
                return
            if end > self.limits.frame_bytes:
                raise HostError("protocol_message_limit")
            line = bytes(self.buffer[:end])
            del self.buffer[:end + 1]
            try:
                message = json.loads(line)
            except (ValueError, UnicodeError):
                raise HostError("protocol_invalid_json") from None
            if not isinstance(message, dict):
                raise HostError("protocol_invalid_message")
            if "id" in message:
                if "method" in message:
                    # Never silently approve a platform permission request.
                    self.on_event(message)
                    raise HostError("unsupported_server_request")
                if (type(message["id"]) is not int or message["id"] != self.pending
                        or self.reply is not None or ("result" in message) == ("error" in message)):
                    raise HostError("protocol_unexpected_response")
                self.reply = message
            elif isinstance(message.get("method"), str) and isinstance(message.get("params", {}), dict):
                self.on_event(message)
            else:
                raise HostError("protocol_invalid_message")

    def poll(self, timeout: float = .1):
        """Drain notifications while idle; never starts a model turn."""
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout < 0:
            raise ValueError("poll timeout must be finite and nonnegative")
        try:
            self._available()
            if self.selector.select(timeout):
                self._read()
        except BaseException:
            self.failed = True
            raise

    def notify(self, method: str, params: dict):
        try:
            self._available()
            self._send({"method": method, "params": params}, time.monotonic() + self.limits.rpc_timeout_seconds)
        except BaseException:
            self.failed = True
            raise

    def rpc(self, method: str, params: dict):
        self._available()
        if self.pending is not None:
            raise HostError("concurrent_host_rpc_forbidden")
        self.counter += 1
        self.pending, self.reply = self.counter, None
        deadline = time.monotonic() + self.limits.rpc_timeout_seconds
        try:
            self._send({"id": self.pending, "method": method, "params": params}, deadline)
            while self.reply is None:
                if time.monotonic() >= deadline:
                    raise HostError("rpc_timeout", method=method)
                self.poll(min(.1, max(0, deadline - time.monotonic())))
            reply = self.reply
        except BaseException:
            self.failed = True
            raise
        finally:
            self.pending, self.reply = None, None
        if "error" in reply:
            error = reply["error"]
            if not isinstance(error, dict):
                self.failed = True
                raise HostError("protocol_invalid_error", method=method)
            try:
                self.on_event({"method": "scid/rpcError", "params": {"method": method, "error": error}})
            except BaseException:
                self.failed = True
                raise
            raise HostError(rpc_diagnostic(error), method=method, rpc_code=error.get("code"))
        return reply["result"]

    def close(self):
        """Disconnect only this child. Not a claim that Workers have stopped."""
        if self.closed:
            return
        self.closed = True
        try:
            if self.child.poll() is None:
                self.child.terminate()
            try:
                self.child.wait(timeout=self.limits.termination_grace_seconds)
            except subprocess.TimeoutExpired:
                self.child.kill()
                self.child.wait()
        finally:
            for stream in (self.child.stdin, self.child.stdout):
                if stream:
                    stream.close()
            self.selector.close()
