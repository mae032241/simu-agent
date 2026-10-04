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
from uuid import uuid4
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
        self.native_connection_id = uuid4().hex
        self.native_event_versions = {}
        self.native_subscriptions = {}
        self.initial_native_bindings = set()
        self._native_connection = connection
        super().__init__(connection, permissions)
        self.log = log
        self.scheduler_session = None
        from .process_observation import OwnedProcessTree
        self.resources = OwnedProcessTree(connection.child.pid)
        self.resource_limit = None
        self.resource_sample_seconds = 1.
        self._sample_at = 0
        self._resource_sample = None
        self.execution_deadline = None

    def _event(self, message):
        if message.get('method') in {'turn/started','turn/completed'}:
            thread = message.get('params', {}).get('threadId')
            if isinstance(thread, str):
                self.native_event_versions[thread] = self.native_event_versions.get(thread, 0) + 1
        super()._event(message)

    def native_terminal_current(self, identity, proof):
        return (self.connection is self._native_connection and not self.connection.failed and not self.connection.closed
            and self.native_subscriptions.get(identity['thread_id']) == identity['platform_session']
            and proof.get('binding_key') == identity['binding_key']
            and proof.get('connection_id') == self.native_connection_id
            and proof.get('event_version') == self.native_event_versions.get(identity['thread_id'], 0)
            and proof.get('state') in {'terminal','never_started_closed'})

    def _subscribe_native(self, thread_id, platform_session, cwd):
        # Resume loads/subscribes without a turn or a permission override. Only
        # exact control-bound participants enter here, including terminal ones
        # whose persisted proof belongs to a previous connection.
        result = self.connection.rpc('thread/resume',dict(threadId=thread_id,cwd=cwd,excludeTurns=True))
        thread = result.get('thread', {})
        if (thread.get('id'), thread.get('sessionId')) != (thread_id, platform_session):
            raise HostError('worker_platform_identity_changed')
        self.native_subscriptions[thread_id] = platform_session

    def set_execution_deadline(self, remaining_seconds):
        self.execution_deadline = (time.monotonic() + max(0, remaining_seconds)
            if remaining_seconds is not None else None)

    def sample_resources(self):
        now = time.monotonic()
        if self._resource_sample is None or now >= self._sample_at:
            self._resource_sample = self.resources.sample()
            self._sample_at = now + self.resource_sample_seconds
        return self._resource_sample

    def wait_for_event(self, timeout):
        # Reuse the transport selector; only poll/RPC consumes its byte stream.
        # Control/shutdown are checked again within this bounded interval.
        self.connection.selector.select(timeout)

    def guard_resources(self):
        if getattr(self, 'execution_deadline', None) is not None and time.monotonic() >= self.execution_deadline:
            raise HostError('budget_deadline')
        if self.resource_limit is None:
            return
        sample = self.sample_resources()
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

    def rotation_boundary(self, identities, *, known, limit, after=None):
        """Count resume and read against one budget; read never subscribes."""
        pending = sorted((value for thread, value in identities.items()
            if not self.native_terminal_current(value,known.get(thread, {}))), key=lambda value: value['binding_key'])
        if after:
            pending = [value for value in pending if value['binding_key'] > after] + [value for value in pending if value['binding_key'] <= after]
        observations, unknown = [], []
        checked = reconciled = 0
        last = None
        for identity in pending:
            if checked >= limit:
                break
            last = identity['binding_key']
            subscribed = self.native_subscriptions.get(identity['thread_id']) == identity['platform_session']
            if not subscribed:
                checked += 1
                try:
                    self._subscribe_native(identity['thread_id'],identity['platform_session'],self.root_cwd)
                except HostError:
                    unknown.append('native_subscription_unconfirmed')
                    reconciled += 1
                    continue
                subscribed = True
                if checked >= limit:
                    break  # Next attempt reads this now subscribed participant.
            version = self.native_event_versions.get(identity['thread_id'], 0)
            checked += 1
            reconciled += 1
            try:
                observed=self.connection.rpc('thread/read',dict(threadId=identity['thread_id'],includeTurns=True)).get('thread',{})
            except HostError:
                unknown.append('native_thread_unavailable')
                continue
            if (observed.get('id') != identity['thread_id'] or observed.get('sessionId') != identity['platform_session']):
                unknown.append('native_identity_unconfirmed')
                continue
            turns=observed.get('turns')
            if not isinstance(turns, list) or any(not isinstance(turn, dict) or not turn.get('id')
                    or turn.get('status') not in {'completed','failed','interrupted'} for turn in turns):
                unknown.append('native_turn_not_terminal')
                continue
            if not turns and not identity['empty_safe']:
                unknown.append('empty_thread_not_proven_closed')
                continue
            if self.native_event_versions.get(identity['thread_id'], 0) != version:
                unknown.append('native_turn_changed_during_read')
                continue
            if not subscribed:
                unknown.append('native_subscription_unconfirmed')
                continue  # Keep historical proof, without claiming fresh safety.
            observations.append(dict(identity=identity, source='thread_read',
                turn_id=turns[-1]['id'] if turns else None, state='terminal' if turns else 'never_started_closed',
                connection_id=self.native_connection_id,event_version=version))
        return dict(safe=not unknown and len(pending)==reconciled, observations=observations,
            checked=checked, unchecked=len(pending)-reconciled, unknown=len(unknown),
            reasons=list(dict.fromkeys(unknown))[:4], next_after=last)

    def rotate_root(self):
        if self.completion is None or self.completion.get('status')!='completed':
            raise HostError('rotation_root_not_terminal')
        self.identity,self.turn_id,self.completion=None,None,None
        try:
            self.open_root(cwd=self.root_cwd,options=self.root_options)
            self.verify_tools_and_session(approval_base_url=self.approval_base_url)
        except BaseException as error:
            error.native_outcome_unknown=True
            raise

    def restore_worker(self, thread_id, platform_session, cwd, *, role="worker"):
        if role not in {"worker", "helper"}:
            raise ValueError("invalid native participant role")
        self._subscribe_native(thread_id,platform_session,cwd)
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
    def __init__(self, *, project_root, state_root, socket_path, approval_base_url, command=None, catalog=None,
                 permissions: RootPermissions | None = None, agent_settings=None):
        self.project_root, self.state_root = Path(project_root), Path(state_root)
        self.socket_path, self.approval_base_url = str(socket_path), approval_base_url
        self.command, self.catalog = command, catalog
        self.permissions = permissions
        from ..agent_execution_settings import load_settings
        self.agent_settings = agent_settings or load_settings(os.environ.get('SCID_AGENT_SETTINGS_FILE'))

    def root_permissions(self, limits, checkpoint, prior, *, debug_disable_task_network=False):
        """Frozen goal policy, checked against inherited Worker needs before any launch."""
        from ..agent_execution_settings import ProgressionSettings, root_permission_conflicts
        default = ProgressionSettings()
        permissions = RootPermissions(limits.get('root_approval_policy', default.root_approval_policy),
            limits.get('root_sandbox', default.root_sandbox),
            limits.get('root_network_access', default.root_network_access))
        if self.permissions is not None:
            if (self.permissions.approval_policy != permissions.approval_policy
                    or self.permissions.sandbox != permissions.sandbox
                    or self.permissions.network_access != permissions.network_access):
                raise HostError('root_permissions_incompatible: injected policy differs from frozen goal')
            permissions = self.permissions
        if self.catalog is None:
            from ..operations.catalog import compile_installed_catalog
            self.catalog = compile_installed_catalog()
        conflicts = root_permission_conflicts(limits, self.catalog,
            debug_disable_task_network=debug_disable_task_network)
        if conflicts:
            raise HostError('root_permissions_incompatible: ' + '; '.join(conflicts))
        # A restored running turn keeps the policy it started with; unproven means stop.
        if prior and checkpoint.get('turn_id') and checkpoint.get('root_permissions') != permissions.declaration():
            raise HostError('root_permissions_unproven')
        return permissions

    def __call__(self, row, on_event):
        settings = json.loads(row['config_json'])['effective']
        offline = settings.get('debug_disable_task_network', False)
        if offline is not self.agent_settings.debug_disable_task_network:
            raise HostError('task_network_policy_changed: stop old hosts/agents; frozen loop cannot resume with a different deployment policy')
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
        permissions = self.root_permissions(limits, checkpoint, prior, debug_disable_task_network=offline)
        if offline:
            from .codex import validate_task_network_profile
            validate_task_network_profile(self.project_root, self.catalog, debug_disable_task_network=True)
            # Both Root and child agents receive this same verified launch configuration.
            config['web_search'] = 'disabled'
        if permissions.permission_profile is not None:
            # The named definition stays in private CODEX_HOME, not project/model inputs.
            permissions.verify_config(personal)
            if any(key in personal for key in ('sandbox_mode', 'sandbox_workspace_write')):
                raise HostError('root_permissions_conflicting_override')
            thread_config = dict(config)
            if offline and thread_config.get('sandbox_workspace_write') == {'network_access': False}:
                # The installed/launch configuration and config/read retain this
                # exact deny. Only the duplicate legacy thread override is absent
                # when the same network=false is supplied by the named profile.
                thread_config.pop('sandbox_workspace_write')
            permissions.verify_options({'config': thread_config})
        directory = self.state_root / 'progression-logs'
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        log = PrivateLog(directory / 'host.stderr', limits['log_bytes'])
        host = None
        opening_root = False
        try:
            connection = AppServer.launch(command + config_flags({'mcp_servers': disabled}) + config_flags(config),
                cwd=self.project_root, environment=os.environ, stderr=log.writer,
                limits=HostLimits(rpc_timeout_seconds=limits['rpc_timeout_seconds'], frame_bytes=limits['frame_bytes']),
                on_event=on_event)
            host = CodexProgressionHost(connection, log, permissions)
            host.resource_limit = limits["max_rss_bytes"]
            from ..agent_execution_settings import ProgressionSettings
            root_settings = ProgressionSettings.model_validate(limits)
            host.resource_sample_seconds = root_settings.resource_sample_seconds
            if row.get('_execution_remaining_seconds') is not None:
                host.set_execution_deadline(row['_execution_remaining_seconds'])
            connection.checkpoint = host.guard_resources
            host.initialize(cwd=str(self.project_root), expected_config=config)
            options = {'model': root_settings.root_model,
                'config': {'model_reasoning_effort': root_settings.root_reasoning_effort}}
            if offline:
                options['config']['web_search'] = 'disabled'
            host.root_options,host.root_cwd,host.approval_base_url=options,str(self.project_root),self.approval_base_url
            opening_root = True
            host.open_root(cwd=str(self.project_root), prior=prior, options=options,
                active_turn_id=checkpoint.get('turn_id') if prior else None)
            host.verify_tools_and_session(approval_base_url=self.approval_base_url)
            if prior and checkpoint.get('turn_id'):
                host.reconcile_turn(checkpoint['turn_id'])
            return host
        except BaseException as error:
            if opening_root:
                # Creating/resuming the native Root can have succeeded before
                # a reply or later verification fails. Closing is no proof that
                # it did not; the coordinator must retain unknown outcome.
                error.native_outcome_unknown = True
            if host:
                host.close()
            else:
                log.close()
            raise
