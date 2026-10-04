"""One persistent Root connection, usable by the control service and probes.

No instance selection, approvals, scientific decisions, automatic retry or storage
lives here. The caller persists private events and verifies sealed Run outcomes.
Returning from a turn leaves the host alive so approvals can be awaited without a
model request. Disconnect does not cancel or prove quiescence of native Workers.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import time

from .codex_app_server import AppServer, HostError


@dataclass(frozen=True)
class RootIdentity:
    thread_id: str
    session_id: str

    def __post_init__(self):
        if (not isinstance(self.thread_id, str) or not self.thread_id
                or self.thread_id != self.session_id):
            raise HostError("actual_root_identity_invalid")


def require_config(expected: dict, actual: dict):
    for key, value in expected.items():
        if key not in actual:
            raise HostError("effective_config_missing")
        if isinstance(value, dict):
            if not isinstance(actual[key], dict):
                raise HostError("effective_config_mismatch")
            require_config(value, actual[key])
        elif actual[key] != value:
            raise HostError("effective_config_mismatch")


def turn_params(thread: str, prompt: str) -> dict:
    return {"threadId": thread, "input": [{"type": "text", "text": prompt}]}


_SANDBOX_TYPE = {"read-only": "readOnly", "workspace-write": "workspaceWrite"}


@dataclass(frozen=True)
class RootPermissions:
    """Background Root policy frozen with the goal, never taken from personal config.

    Native child Agents inherit the Root sandbox and network; settings validation
    rejects values that would remove a Worker capability declared in the catalog.
    Sent and verified on start/resume, sent on every turn. never is not isolation.
    A named profile freezes its private host definition; this adapter alone does
    not prove native child inheritance or restrict host-side MCP tools."""
    approval_policy: str = "never"
    sandbox: str = "workspace-write"
    network_access: bool = True
    permission_profile: str | None = None
    profile_definition: str | None = None

    def __post_init__(self):
        if (self.approval_policy != "never" or self.sandbox not in _SANDBOX_TYPE
                or type(self.network_access) is not bool
                or (self.sandbox == "read-only" and self.network_access)):
            raise HostError("root_permissions_unsupported")
        if self.permission_profile is not None or self.profile_definition is not None:
            try:
                definition = json.loads(self.profile_definition)
                valid = (isinstance(self.permission_profile, str) and bool(self.permission_profile.strip())
                         and isinstance(definition, dict) and 'extends' not in definition
                         and isinstance(definition.get('filesystem'), dict) and bool(definition['filesystem'])
                         and definition.get('network', {}).get('enabled') is self.network_access)
            except (TypeError, ValueError, AttributeError):
                valid = False
            if not valid:
                raise HostError("root_permissions_unsupported")
            # Freeze a self-contained definition, including exact path grants.
            object.__setattr__(self, 'profile_definition', json.dumps(
                definition, sort_keys=True, separators=(',', ':')))

    def declaration(self) -> dict:
        result = {"approval_policy": self.approval_policy, "sandbox": self.sandbox,
                  "network_access": self.network_access}
        if self.permission_profile is not None:
            result['permission_profile'] = {'id': self.permission_profile,
                'sha256': hashlib.sha256(self.profile_definition.encode()).hexdigest()}
        return result

    def verify_config(self, config: dict):
        if self.permission_profile is not None:
            profiles = config.get('permissions', {}) if isinstance(config, dict) else None
            if (not isinstance(profiles, dict) or profiles.get(self.permission_profile)
                    != json.loads(self.profile_definition)):
                raise HostError('root_permissions_mismatch')

    def verify_options(self, options: dict):
        if self.permission_profile is None:
            return
        config = options.get('config', {})
        if (any(key in options for key in ('sandbox', 'sandboxPolicy', 'permissions'))
                or any(key in config for key in ('sandbox_mode', 'sandbox_workspace_write',
                                                 'permissions', 'default_permissions'))):
            raise HostError('root_permissions_conflicting_override')

    def thread(self) -> dict:
        if self.permission_profile is not None:
            return {'approvalPolicy': self.approval_policy, 'permissions': self.permission_profile}
        params = {"approvalPolicy": self.approval_policy, "sandbox": self.sandbox}
        if self.sandbox == "workspace-write":
            # Config.sandbox_workspace_write (exported v2 schema); replaces personal values.
            params["config"] = {"sandbox_workspace_write": {"network_access": self.network_access,
                                                            "writable_roots": []}}
        return params

    def turn(self) -> dict:
        if self.permission_profile is not None:
            return {'approvalPolicy': self.approval_policy, 'permissions': self.permission_profile}
        return {"approvalPolicy": self.approval_policy,
                "sandboxPolicy": {"type": _SANDBOX_TYPE[self.sandbox], "networkAccess": self.network_access}}

    def verify(self, result: dict, *, cwd: str):
        if self.permission_profile is not None:
            active = result.get('activePermissionProfile', {})
            if (not isinstance(active, dict) or active.get('id') != self.permission_profile
                    or active.get('extends') is not None):
                raise HostError('root_permissions_mismatch')
        sandbox = result.get("sandbox") if isinstance(result, dict) else None
        roots = sandbox.get("writableRoots", []) if isinstance(sandbox, dict) else None
        # The working directory is writable under workspace-write anyway; any other root widens it.
        if (result.get("approvalPolicy") != self.approval_policy or not isinstance(sandbox, dict)
                or sandbox.get("type") != _SANDBOX_TYPE[self.sandbox]
                or sandbox.get("networkAccess", False) is not self.network_access
                or not isinstance(roots, list) or any(root != cwd for root in roots)):
            raise HostError("root_permissions_mismatch")


class CodexRootHost:
    def __init__(self, connection: AppServer, permissions: RootPermissions | None = None):
        self.connection = connection
        self.permissions = permissions
        self.identity = None
        self.turn_id = None
        self.completion = None
        self.terminal_transport_error = None
        self._starting = False
        self._initialized = False
        self._sink = connection.on_event
        connection.on_event = self._event

    def _event(self, message):
        # The consumer persists before this host advances its observation state.
        self._sink(message)
        params = message.get("params", {})
        if (message.get("method") == "turn/completed" and self.identity
                and params.get("threadId") == self.identity.thread_id):
            turn = params.get("turn", {})
            if self._starting or turn.get("id") == self.turn_id:
                if not isinstance(turn.get("id"), str) or turn.get("status") not in (
                        "completed", "failed", "interrupted"):
                    raise HostError("root_completion_invalid")
                self.completion = {"id": turn["id"], "status": turn["status"]}

    def initialize(self, *, cwd: str, expected_config: dict):
        if self._initialized:
            raise HostError("host_already_initialized")
        self.connection.rpc("initialize", {"clientInfo": {"name": "scidiscovery", "version": "0.1.1"},
                                           "capabilities": {"experimentalApi": True}})
        self.connection.notify("initialized", {})
        actual = self.connection.rpc("config/read", {"cwd": cwd, "includeLayers": False})
        try:
            require_config(expected_config, actual["config"])
            if self.permissions is not None:
                self.permissions.verify_config(actual['config'])
        except (HostError, KeyError, TypeError):
            self.connection.failed = True
            raise
        self._initialized = True

    def open_root(self, *, cwd: str, prior: RootIdentity | None = None,
                  options: dict | None = None, active_turn_id: str | None = None):
        """Resume only control-recorded coordinates; never replay a prompt.

        The owner reconciles prior work before choosing active_turn_id=None.
        Restoring an unfinished turn blocks new work until its terminal event.
        """
        if not self._initialized or self.identity is not None:
            raise HostError("root_open_state_invalid")
        if active_turn_id is not None and (
                prior is None or not isinstance(active_turn_id, str) or not active_turn_id):
            raise ValueError("active turn requires an exact prior Root identity")
        if prior:
            self.identity, self.turn_id = prior, active_turn_id
            params = {"threadId": prior.thread_id, "cwd": cwd, "excludeTurns": True}
            method = "thread/resume"
        else:
            params = {**(options or {}), "cwd": cwd, "ephemeral": False}
            method = "thread/start"
        if self.permissions is not None:
            self.permissions.verify_options(params)
            declared = self.permissions.thread()
            config = {**params.get("config", {}), **declared.pop("config", {})}
            params.update(declared, **({"config": config} if config else {}))
        try:
            result = self.connection.rpc(method, params)
            if self.permissions is not None:
                self.permissions.verify(result, cwd=cwd)
            thread = result.get("thread", {})
            identity = RootIdentity(thread.get("id"), thread.get("sessionId"))
            if prior is not None and identity != prior:
                raise HostError("resumed_platform_identity_changed")
        except BaseException:
            self.identity = None
            self.connection.failed = True
            raise
        self.identity = identity
        return identity

    def start_turn(self, prompt: str) -> str:
        if self.terminal_transport_error is not None:
            raise HostError('host_connection_unusable')
        if self.identity is None:
            raise HostError("root_not_open")
        if self.turn_id is not None and self.completion is None:
            raise HostError("root_turn_already_active")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("root prompt must be nonempty")
        self.turn_id, self.completion = None, None
        self._starting = True
        try:
            result = self.connection.rpc("turn/start", {**turn_params(self.identity.thread_id, prompt),
                **(self.permissions.turn() if self.permissions is not None else {})})
            turn = result.get("turn") if isinstance(result, dict) else None
            turn_id = turn.get("id") if isinstance(turn, dict) else None
            if not isinstance(turn_id, str) or not turn_id:
                self.connection.failed = True
                raise HostError("actual_turn_identity_missing")
            if self.completion and self.completion["id"] != turn_id:
                self.connection.failed = True
                raise HostError("root_completion_identity_mismatch")
            self.turn_id = turn_id
            return turn_id
        finally:
            self._starting = False

    def poll(self, timeout: float = .1):
        if self.terminal_transport_error is not None:
            return self.completion
        self.connection.poll(timeout)
        return self.completion

    def interrupt(self):
        """Acknowledgement is not a terminal state; keep draining completion."""
        if self.turn_id is None or self.completion is not None:
            return
        try:
            self.connection.rpc("turn/interrupt", {"threadId": self.identity.thread_id, "turnId": self.turn_id})
        except HostError as error:
            # A matching native terminal event was persisted by the sink before
            # completion was set. Losing the separate interrupt reply does not
            # undo that proof. Retire this connection; never reuse a timed-out RPC.
            if (error.code != 'rpc_timeout' or error.method != 'turn/interrupt'
                    or self.completion is None or self.completion['id'] != self.turn_id):
                raise
            self.terminal_transport_error = error.code
            self.connection.close()

    def wait_turn(self, timeout_seconds: float):
        if type(timeout_seconds) not in (int, float) or not 0 < timeout_seconds < float("inf"):
            raise ValueError("turn timeout must be finite and positive")
        if self.turn_id is None:
            raise HostError("root_turn_not_started")
        deadline = time.monotonic() + timeout_seconds
        while self.completion is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                # Keep the exact active turn: caller can interrupt/reconcile, not replay.
                raise HostError("root_turn_timeout")
            self.poll(min(.1, remaining))
        return dict(self.completion)

    def close(self):
        self.connection.close()
