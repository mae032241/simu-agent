"""Bounded arithmetic on the installed Codex 0.157 code-mode protocol.

No model, auth, native daemon or tool delegation. Run only inside the existing
resource supervisor. This probes the packaged engine, not full Codex integration.
Protocol: code-mode-protocol/src/host/{message,codec,payload}.rs in openai/codex.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import selectors
import shutil
import struct
import subprocess
import time


def executable() -> Path:
    cli = Path(shutil.which("codex") or "codex").resolve()
    adjacent = cli.with_name("codex-code-mode-host")
    if adjacent.is_file():
        return adjacent
    # Current npm distribution, resolved from the chosen CLI, never another install.
    package = cli.parent.parent
    hosts = list(package.glob("node_modules/@openai/codex-*/vendor/*/bin/codex-code-mode-host"))
    hosts += list(package.glob("vendor/*/bin/codex-code-mode-host"))
    if len(hosts) != 1:
        raise RuntimeError("native_code_mode_binary_not_identified")
    return hosts[0]


def probe(logdir: Path, settings: dict) -> dict:
    binary = executable()
    events = []
    selector = selectors.DefaultSelector()
    with (logdir / "native-code-mode.log").open("wb") as err:
        process = subprocess.Popen([str(binary)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=err, bufsize=0)
        selector.register(process.stdout, selectors.EVENT_READ)
        buffer = b""
        def exchange(message=None):
            nonlocal buffer
            if message is not None:
                data = json.dumps(message).encode()
                process.stdin.write(struct.pack("<I", len(data)) + data)
                process.stdin.flush()
            deadline = time.monotonic() + settings["native_probe_timeout_seconds"]
            while time.monotonic() < deadline:
                if len(buffer) >= 4:
                    size = struct.unpack("<I", buffer[:4])[0]
                    if size > settings["native_probe_frame_bytes"]:
                        raise RuntimeError("native_code_mode_response_limit")
                    if len(buffer) >= size + 4:
                        reply = json.loads(buffer[4:4+size])
                        buffer = buffer[4+size:]
                        events.append(reply)
                        return reply
                if not selector.select(.1):
                    continue
                chunk = os.read(process.stdout.fileno(), 65536)
                if not chunk:
                    raise RuntimeError("native_code_mode_stdout_closed")
                buffer += chunk
            raise TimeoutError("native_code_mode_timeout")
        try:
            hello = exchange({"type": "connection/hello", "supportedVersions": [1],
                              "requiredCapabilities": [], "optionalCapabilities": []})
            if hello.get("type") != "connection/ready":
                raise RuntimeError("native_code_mode_handshake_failed")
            opened = exchange({"type": "operation/request", "id": 1,
                "request": {"method": "session/open", "sessionId": "bounded-arithmetic-probe"}})
            if opened.get("result", {}).get("status") != "ok":
                raise RuntimeError("native_code_mode_session_failed")
            reply = exchange({"type": "operation/request", "id": 2, "request": {
                "method": "session/execute", "sessionId": "bounded-arithmetic-probe", "request": {
                    "tool_call_id": "arithmetic", "enabled_tools": [], "source": "text(1 + 1);",
                    "yield_time_ms": 1000, "max_output_tokens": 64}}})
            value = reply.get("result", {}).get("value", {})
            if value.get("type") != "execution/started":
                raise RuntimeError("native_code_mode_execution_not_started")
            completed = exchange()
            final = completed.get("result", {}).get("value", {}).get("Result", {})
            if (completed.get("type") != "execute/initialResponse" or completed.get("id") != 2
                    or completed.get("result", {}).get("status") != "ok"
                    or final.get("error_text") is not None
                    or final.get("content_items") != [{"type": "input_text", "text": "2"}]):
                raise RuntimeError("native_code_mode_arithmetic_failed")
            return {"status": "passed", "result": "2", "model_requests": 0,
                    "scope": "packaged native engine arithmetic; not the whole model tool path"}
        finally:
            (logdir / "native-code-mode-events.log").write_text(json.dumps(events, indent=2) + "\n")
            process.stdin.close()
            try:
                process.wait(timeout=settings["native_probe_timeout_seconds"])
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            process.stdout.close()
            selector.close()
