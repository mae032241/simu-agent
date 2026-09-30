"""Daemon-owned Codex host, using the installed workspace and current authentication."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
import tomllib
from urllib.parse import urlsplit

from .codex_app_server import AppServer, HostError, HostLimits, config_flags
from .codex_root_host import CodexRootHost, RootIdentity, RootPermissions


class PrivateLog:
    """Drain stderr continuously, retaining a bounded rotating private log."""
    def __init__(self, path, maximum):
        self.path, self.maximum = path, maximum
        self.reader, self.writer = os.pipe()
        self.thread = threading.Thread(target=self._drain, daemon=True)
        self.thread.start()

    def _drain(self):
        size = 0
        stream = None
        try:
            while data := os.read(self.reader, 4096):
                if stream is None or size + len(data) > self.maximum:
                    if stream:
                        stream.close()
                        self.path.replace(self.path.with_suffix('.previous'))
                    fd = os.open(self.path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
                    stream = os.fdopen(fd, 'wb', buffering=0)
                    size = 0
                stream.write(data)
                size += len(data)
        finally:
            if stream:
                stream.close()
            os.close(self.reader)

    def close(self):
        if self.writer is not None:
            os.close(self.writer)
            self.writer = None
        self.thread.join(timeout=1)


class CodexProgressionHost(CodexRootHost):
    def __init__(self, connection, log, permissions=None):
        super().__init__(connection, permissions)
        self.log = log
        self.scheduler_session = None
        from .process_observation import OwnedProcessTree
        self.resources = OwnedProcessTree(connection.child.pid)
        self.resource_limit = None
        self._sample_at = 0

    def guard_resources(self):
        now = time.monotonic()
        if self.resource_limit is None or now < self._sample_at:
            return
        self._sample_at = now + .1
        sample = self.resources.sample()
        if sample['owned_tree_rss_bytes'] + (sample['control_daemon_rss_bytes'] or 0) >= self.resource_limit:
            self.resources.terminate()
            raise HostError('resource_limit')

    def verify_tools_and_session(self, *, approval_base_url):
        cursor = None
        found = False
        for _ in range(20):
            page = self.connection.rpc('mcpServerStatus/list',
                dict(threadId=self.identity.thread_id, limit=20, cursor=cursor))
            for server in page['data']:
                if server['name'] == 'scidiscovery':
                    found = not server.get('toolsError') and {'scid_catalog', 'scid_describe', 'scid_call'}.issubset(server.get('tools', {}))
            cursor = page.get('nextCursor')
            if not cursor:
                break
        if cursor or not found:
            raise HostError('scidiscovery_tools_unavailable')
        reply = self.connection.rpc('mcpServer/tool/call', dict(
            threadId=self.identity.thread_id, server='scidiscovery', tool='scid_call',
            arguments=dict(name='instance_current', arguments={}),
            _meta={'x-codex-turn-metadata': dict(session_id=self.identity.session_id, thread_id=self.identity.thread_id)}))
        if reply.get('isError'):
            raise HostError('instance_current_failed')
        value = reply.get('structuredContent')
        if not isinstance(value, dict):
            content = reply.get('content', [])
            if len(content) != 1 or content[0].get('type') != 'text':
                raise HostError('instance_current_invalid')
            value = json.loads(content[0]['text'])
        url, origin = urlsplit(value.get('management_url', '')), urlsplit(approval_base_url)
        if ((url.scheme, url.netloc) != (origin.scheme, origin.netloc)
                or not re.fullmatch(r'/sessions/sch_[a-f0-9]{32}', url.path)):
            raise HostError('actual_scheduler_session_unavailable')
        self.scheduler_session = url.path.rsplit('/', 1)[1]

    def reconcile_turn(self, turn_id):
        """Read the exact recorded turn; an absent/unknown turn never permits replay."""
        result = self.connection.rpc('thread/read', dict(threadId=self.identity.thread_id, includeTurns=True))
        thread = result.get('thread', {})
        if thread.get('id') != self.identity.thread_id:
            raise HostError('read_platform_identity_changed')
        turn = next((v for v in thread.get('turns', []) if v.get('id') == turn_id), None)
        if turn is None:
            raise HostError('recorded_turn_unavailable')
        if turn.get('status') in {'completed', 'failed', 'interrupted'}:
            self.completion = dict(id=turn_id, status=turn['status'])
        elif turn.get('status') != 'inProgress':
            raise HostError('recorded_turn_state_unknown')

    def restore_worker(self, thread_id, platform_session, cwd, *, role="worker"):
        if role not in {"worker", "helper"}:
            raise ValueError("invalid native participant role")
        result = self.connection.rpc('thread/resume', dict(threadId=thread_id, cwd=cwd, excludeTurns=True))
        value = result.get('thread', {})
        if (value.get('id'), value.get('sessionId')) != (thread_id, platform_session):
            raise HostError('worker_platform_identity_changed')
        observed = self.connection.rpc('thread/read', dict(threadId=thread_id, includeTurns=True)).get('thread', {})
        if observed.get('id') != thread_id:
            raise HostError('worker_platform_identity_changed')
        turns = observed.get('turns', [])
        statuses = [turn.get('status') for turn in turns]
        if not statuses or any(status not in {'inProgress', 'completed', 'failed', 'interrupted'} for status in statuses):
            raise HostError('worker_native_turn_state_unknown')
        if 'inProgress' not in statuses and role != 'helper':
            raise HostError('worker_native_turn_not_running')
        # Helpers can finish while their owner remains active. Native terminal
        # evidence permits keeping their metering identity without waking them;
        # released_at alone never proves this state.
        # Resume subscribes to the original thread; no synthetic message or turn
        # may restart a side effect whose acceptance cannot be established.

    def close(self):
        try:
            super().close()
        finally:
            self.log.close()


class CodexProgressionFactory:
    def __init__(self, *, project_root, state_root, socket_path, approval_base_url, command=None, catalog=None):
        self.project_root, self.state_root = Path(project_root), Path(state_root)
        self.socket_path, self.approval_base_url = str(socket_path), approval_base_url
        self.command, self.catalog = command, catalog

    def root_permissions(self, limits, checkpoint, prior):
        """Frozen goal policy, checked against inherited Worker needs before any launch."""
        from ..agent_execution_settings import ProgressionSettings, root_permission_conflicts
        default = ProgressionSettings()
        permissions = RootPermissions(limits.get('root_approval_policy', default.root_approval_policy),
            limits.get('root_sandbox', default.root_sandbox),
            limits.get('root_network_access', default.root_network_access))
        if self.catalog is None:
            from ..operations.catalog import compile_installed_catalog
            self.catalog = compile_installed_catalog()
        conflicts = root_permission_conflicts(limits, self.catalog)
        if conflicts:
            raise HostError('root_permissions_incompatible: ' + '; '.join(conflicts))
        # A restored running turn keeps the policy it started with; unproven means stop.
        if prior and checkpoint.get('turn_id') and checkpoint.get('root_permissions') != permissions.declaration():
            raise HostError('root_permissions_unproven')
        return permissions

    def __call__(self, row, on_event):
        settings = json.loads(row['config_json'])['effective']
        limits = settings['progression']
        config = tomllib.loads((self.project_root / '.codex/config.toml').read_text())
        server = config.get('mcp_servers', {}).get('scidiscovery', {})
        # This runtime must reach this daemon, not another project's service.
        if self.socket_path not in server.get('args', []):
            raise HostError('workspace_control_socket_mismatch')
        personal_path = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'config.toml'
        personal = tomllib.loads(personal_path.read_text()) if personal_path.exists() else {}
        disabled = {name: dict(enabled=False) for name in personal.get('mcp_servers', {}) if name != 'scidiscovery'}
        executable = shutil.which('codex') if self.command is None else None
        if self.command is None and executable is None:
            raise HostError('codex_not_installed')
        command = self.command or [executable, 'app-server', '--stdio']
        previous = json.loads(row['host_json'] or 'null')
        checkpoint = json.loads(row['checkpoint_json'])
        prior = RootIdentity(previous['thread_id'], previous['platform_session']) if previous else None
        permissions = self.root_permissions(limits, checkpoint, prior)
        directory = self.state_root / 'progression-logs'
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        log = PrivateLog(directory / 'host.stderr', limits['log_bytes'])
        host = None
        try:
            connection = AppServer.launch(command + config_flags({'mcp_servers': disabled}) + config_flags(config),
                cwd=self.project_root, environment=os.environ, stderr=log.writer,
                limits=HostLimits(rpc_timeout_seconds=limits['rpc_timeout_seconds'], frame_bytes=limits['frame_bytes']),
                on_event=on_event)
            host = CodexProgressionHost(connection, log, permissions)
            host.resource_limit = limits["max_rss_bytes"]
            connection.checkpoint = host.guard_resources
            host.initialize(cwd=str(self.project_root), expected_config=config)
            from ..agent_execution_settings import ProgressionSettings
            root_settings = ProgressionSettings.model_validate(limits)
            options = {'model': root_settings.root_model,
                'config': {'model_reasoning_effort': root_settings.root_reasoning_effort}}
            host.open_root(cwd=str(self.project_root), prior=prior, options=options,
                active_turn_id=checkpoint.get('turn_id') if prior else None)
            host.verify_tools_and_session(approval_base_url=self.approval_base_url)
            if prior and checkpoint.get('turn_id'):
                host.reconcile_turn(checkpoint['turn_id'])
            return host
        except BaseException:
            if host:
                host.close()
            else:
                log.close()
            raise
