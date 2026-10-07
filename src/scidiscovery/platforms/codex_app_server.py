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
from urllib.parse import urlsplit, urlunsplit


def pending_user_information(params):
    """Bounded question/form projection. Never persist credentials from a URL."""
    import ipaddress
    view = dict(questions=[], omitted=False)
    def text(value, limit):
        if not isinstance(value, str):
            view['omitted'] = True
            return ''
        if len(value) > limit:
            view['omitted'] = True
        return value[:limit]
    def fits(candidate):
        return len(json.dumps(candidate, ensure_ascii=False).encode()) <= 7168
    questions = params.get('questions', [dict(id='elicitation', question=params.get('message', ''), header='MCP input')])
    view['omitted'] = len(questions) > 3
    for value in questions[:3]:
        if not isinstance(value, dict):
            view['omitted'] = True
            continue
        question = {key: text(value.get(key, ''), limit) for key, limit in
            (('id', 128), ('header', 128), ('question', 2048))}
        if not fits({**view, 'questions': [*view['questions'], question]}):
            view['omitted'] = True
            break
        view['questions'].append(question)
        if isinstance(value.get('options'), list):
            question['options'] = []
            view['omitted'] |= len(value['options']) > 8
            for option in value['options'][:8]:
                if not isinstance(option, dict):
                    view['omitted'] = True
                    continue
                question['options'].append(dict(label=text(option.get('label', ''), 128),
                    description=text(option.get('description', ''), 512)))
                if not fits(view):
                    question['options'].pop()
                    view['omitted'] = True
                    break
        for flag in ('isOther', 'isSecret'):
            if isinstance(value.get(flag), bool):
                question[flag] = value[flag]
    if 'mode' in params:
        form = dict(mode=text(params['mode'], 32), serverName=text(params.get('serverName', ''), 128))
        if 'requestedSchema' in params:
            schema = params['requestedSchema']
            if fits({**view, 'elicitation': {**form, 'requestedSchema': schema}}):
                form['requestedSchema'] = schema
            else:
                form['requestedSchema_omitted'] = view['omitted'] = True
        if 'url' in params:
            form.update(interaction='unsupported_url_interaction',
                instruction='Return to the original requesting app to complete its URL interaction; this public origin is not the full request URL.')
            # Path, query, fragment and userinfo may contain bearer credentials.
            # Publish only a public origin, never a truncated or guessed login URL.
            try:
                parsed = urlsplit(params['url'])
                host = parsed.hostname or ''
                try:
                    public = ipaddress.ip_address(host).is_global
                except ValueError:
                    public = '.' in host and not host.endswith(('.local', '.localhost', '.internal'))
                if parsed.scheme not in {'http', 'https'} or not public:
                    raise ValueError('non-public URL')
                authority = '[' + host + ']' if ':' in host else host
                if parsed.port:
                    authority += ':' + str(parsed.port)
                origin = urlunsplit((parsed.scheme, authority, '', '', ''))
                if len(origin) > 512:
                    raise ValueError('URL origin too large')
                form['url_origin'] = origin
                if params['url'] != origin:
                    form['url_components_omitted'] = view['omitted'] = True
            except (TypeError, ValueError):
                form['url_omitted'] = view['omitted'] = True
        if fits({**view, 'elicitation': form}):
            view['elicitation'] = form
        else:
            view['omitted'] = True
    return view


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
        self._drain_messages()

    def _drain_messages(self):
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
                    self._server_request(message)
                    continue
                if (type(message["id"]) is not int or message["id"] != self.pending
                        or self.reply is not None or ("result" in message) == ("error" in message)):
                    raise HostError("protocol_unexpected_response")
                self.reply = message
            elif isinstance(message.get("method"), str) and isinstance(message.get("params", {}), dict):
                try:
                    self.on_event(message)
                except Exception as error:
                    self._event_delivery_failed = True
                    if getattr(error, 'retryable_event_delivery', False):
                        # An absolute local observation can be retried before
                        # consuming subsequent frames. This is no native call.
                        self.buffer[:0] = line + b'\n'
                    raise
            else:
                raise HostError("protocol_invalid_message")

    def _server_request(self, message):
        """Codex 0.159.2 generated ServerRequest/Response schemas (v2).

        Denial payloads differ by request type. Unknown protocols never receive
        a fabricated result. User questions remain unanswered for human input.
        https://learn.chatgpt.com/docs/app-server#approvals
        """
        method, params = message.get('method'), message.get('params')
        valid = isinstance(params, dict) and all(isinstance(params.get(key), str) and params[key]
            for key in ('threadId', 'turnId', 'itemId'))
        result, state = None, 'unsupported'
        if valid and method in {'item/commandExecution/requestApproval', 'item/fileChange/requestApproval'}:
            result, state = {'decision': 'decline'}, 'denial_prepared'
        elif valid and method == 'item/permissions/requestApproval' and isinstance(params.get('permissions'), dict):
            result, state = {'permissions': {}, 'scope': 'turn'}, 'denial_prepared'
        elif valid and method == 'item/tool/requestUserInput' and isinstance(params.get('questions'), list):
            state = 'pending_user_input'
        elif (isinstance(params, dict) and method in {'execCommandApproval', 'applyPatchApproval'}
                and isinstance(params.get('conversationId'), str) and isinstance(params.get('callId'), str)):
            result, state = {'decision': {'denied': {'rejection': 'Background control cannot grant approval.'}}}, 'denial_prepared'
        elif (isinstance(params, dict) and method == 'mcpServer/elicitation/request'
                and isinstance(params.get('threadId'), str) and isinstance(params.get('message'), str)):
            state = 'pending_user_input'
        safe = dict(request_id=message['id'], method=method if isinstance(method, str) and len(method) <= 128 else 'unknown',
            state=state, threadId=params.get('threadId') if isinstance(params, dict) else None,
            turnId=params.get('turnId') if isinstance(params, dict) else None)
        if state == 'pending_user_input':
            safe.update(pending_user_information(params))
        self.on_event(dict(method='scid/serverRequest', params=safe))
        if state == 'unsupported':
            raise HostError('unsupported_server_request')
        if result is not None:
            self._send(dict(id=message['id'], result=result), time.monotonic() + self.limits.rpc_timeout_seconds)
            self.on_event(dict(method='scid/serverRequest', params={**safe, 'state': 'denied'}))

    def poll(self, timeout: float = .1):
        """Drain notifications while idle; never starts a model turn."""
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout < 0:
            raise ValueError("poll timeout must be finite and nonnegative")
        self._event_delivery_failed = False
        try:
            self._available()
            self._drain_messages()
            if self.selector.select(timeout):
                self._read()
        except BaseException:
            if not self._event_delivery_failed:
                self.failed = True
            raise
        finally:
            self._event_delivery_failed = False

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
