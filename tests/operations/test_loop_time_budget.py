"""Frozen calendar and enabled budgets through real local UI/MCP entry points."""
import json
import os
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_root import OperationCallInput
from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService
from tests.operations.test_progression import progression, checkpoint, row, Host
from tests.operations.test_research_loop_budget import loop_ui, authorize, start, loop_form, historical_checkpoint, LoopHost
from tests.operations.test_loop_review_budget import configure
from tests.operations.test_scientific_progress import request, active
from tests.operations.test_local_worker_contracts import _invoke, _write_result
from tests.operations.test_unified_mcp import call, result
from tests.operations.test_human_progress_continuation import human_ui, paused, submit, fresh_binding


def budget(p):
    return p.root.call_tool('progression_status', {})['budget']


def test_ui_pause_calendar_expiry_and_new_consent_alone_creates_new_deadline(loop_ui):
    p = loop_ui
    configure(p, max_calendar_seconds=40, max_elapsed_seconds=100)
    form = loop_form(p)
    assert authorize(p, form) == 303
    original = checkpoint(p)['loop_authorizations'][checkpoint(p)['current_loop_id']]
    assert datetime.fromisoformat(original['authorized_at']).timestamp() == p.now[0]
    assert datetime.fromisoformat(original['deadline_at']).timestamp() == p.now[0] + 40
    start(p, mode='interactive')
    p.root.call_tool('artifact_ingest_text', dict(name='other-goal', text='An original changed goal.'))
    p.now[0] += 10
    p.root.call_tool('progression_command', dict(command='pause'))
    p.now[0] += 30
    timing = budget(p)
    assert timing['elapsed_seconds'] == 10 and timing['remaining_seconds'] == 90
    assert timing['calendar_remaining_seconds'] == timing['effective_remaining_seconds'] == 0
    assert timing['time_exhaustion'] == 'calendar_deadline'
    assert not p.root.call_tool('progression_status', {})['can_schedule']
    for args in (dict(command='resume'), dict(command='takeover'),
            dict(command='start', mode='interactive', objective_name='other-goal')):
        with pytest.raises(Exception, match='calendar_deadline'):
            p.root.call_tool('progression_command', args)
    configure(p, max_calendar_seconds=200, max_elapsed_seconds=200)
    assert budget(p) == timing  # Editing configuration cannot replenish the old loop.
    assert authorize(p, form) == 303  # Idempotent original consent does not grant again.
    retained = checkpoint(p)['loop_authorizations'][checkpoint(p)['current_loop_id']]
    assert all(retained[key] == original[key] for key in ('authorized_at', 'deadline_at', 'config', 'request_fingerprint'))
    old_id = checkpoint(p)['current_loop_id']
    assert authorize(p) == 303
    assert checkpoint(p)['current_loop_id'] != old_id
    assert budget(p)['effective_remaining_seconds'] == 200
    assert historical_checkpoint(p)['loop_authorizations'][old_id]['deadline_at'] == original['deadline_at']
    from tests.operations.test_m6a_direct_instance_management import _request
    body = _request(p.base, 'GET', p.path)[2].decode()
    assert '自然寿命：200 秒' in body and '初始有效时间上限：200 秒' in body
    assert '冻结自然截止时间' in body and '有效剩余时间' in body


def test_wait_offline_reconnect_and_rollback_share_frozen_native_cap(loop_ui):
    p = loop_ui
    configure(p, max_calendar_seconds=100, max_elapsed_seconds=200)
    assert authorize(p) == 303
    observed = []
    original_factory = p.coordinator.host_factory
    def factory(record, event):
        observed.append(record['_execution_remaining_seconds'])
        host = original_factory(record, event)
        host.set_execution_deadline = lambda seconds: observed.append(seconds)
        return host
    p.coordinator.host_factory = factory
    start(p)
    assert observed == [100, 100]
    deadline = budget(p)['deadline_at']
    host = p.coordinator.host
    host.finish()
    p.now[0] += 10
    p.coordinator.tick()
    assert budget(p)['elapsed_seconds'] == budget(p)['calendar_elapsed_seconds'] == 10
    host.close()
    p.coordinator.host = None
    p.now[0] += 20
    p.coordinator.tick()
    assert observed[-2:] == [70, 70]
    before = budget(p)
    assert before['elapsed_seconds'] == before['calendar_elapsed_seconds'] == 30
    p.now[0] -= 10
    p.root.call_tool('progression_command', dict(command='pause'))
    assert budget(p) == before
    reopened = SchedulerBindingService(p.runtime.scheduler_bindings.database_path)
    reopened.progression_clock = lambda: p.now[0]
    assert reopened.progression_status(instance_id=p.instance)['budget'] == before
    assert budget(p)['deadline_at'] == deadline
    p.coordinator.tick()
    assert row(p)['state'] == 'paused'  # A connection never revives explicit pause.


def test_pending_offline_expiry_stops_before_native_factory(loop_ui):
    p = loop_ui
    configure(p, max_calendar_seconds=20, max_elapsed_seconds=100)
    assert authorize(p) == 303
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='goal'))
    p.now[0] += 21
    p.coordinator.host_factory = lambda *_: pytest.fail('expired loop must not open a native host')
    p.coordinator.tick()
    assert row(p)['state'] == 'paused' and row(p)['reason'] == 'budget_exhausted'
    assert budget(p)['elapsed_seconds'] == 21 and budget(p)['time_exhaustion'] == 'calendar_deadline'


def guarded_native(p, monkeypatch):
    """Keep real interrupt/RPC availability, poll, and native deadline guards."""
    from scidiscovery.platforms import codex_progression
    from scidiscovery.platforms.codex_app_server import AppServer
    from scidiscovery.platforms.codex_root_host import CodexRootHost
    monkeypatch.setattr(codex_progression, 'time', SimpleNamespace(monotonic=lambda: p.now[0]))
    class GuardedHost(LoopHost):
        set_execution_deadline = codex_progression.CodexProgressionHost.set_execution_deadline
        guard_resources = codex_progression.CodexProgressionHost.guard_resources
        poll = CodexRootHost.poll
        interrupt = CodexRootHost.interrupt
        def __init__(self, record, event):
            super().__init__(record, event)
            self.execution_deadline = self.resource_limit = self.terminal_transport_error = None
            self.connection = object.__new__(AppServer)
            self.connection.closed = self.connection.failed = False
            self.connection.checkpoint = self.guard_resources
            self.connection.selector = SimpleNamespace(select=lambda _: [])
    p.coordinator.host_factory = GuardedHost


@pytest.mark.parametrize('boundary', ['pause_poll', 'release'])
def test_paused_terminal_root_consumes_pipe_worker_usage_before_release(loop_ui, monkeypatch, boundary):
    from scidiscovery.platforms.codex_app_server import AppServer, HostLimits
    from scidiscovery.platforms.codex_root_host import CodexRootHost
    from tests.operations.worker_fixtures import attached_worker
    p = loop_ui
    configure(p, max_calendar_seconds=20, max_elapsed_seconds=100)
    assert authorize(p) == 303
    guarded_native(p, monkeypatch)
    notification_read, notification_write = os.pipe()
    request_read, request_write = os.pipe()
    os.set_blocking(request_read, False)
    child = SimpleNamespace(stdin=os.fdopen(request_write, 'wb', buffering=0),
        stdout=os.fdopen(notification_read, 'rb', buffering=0), poll=lambda: 0, wait=lambda **_: 0)
    class PipeHost(p.coordinator.host_factory):
        def __init__(self, record, event):
            super().__init__(record, event)
            self._sink, self._starting = event, False
            self.connection = AppServer(child, limits=HostLimits(), on_event=event, checkpoint=self.guard_resources)
            self.connection.on_event = lambda message: CodexRootHost._event(self, message)
        def close(self):
            super().close()
            self.connection.close()
    p.coordinator.host_factory = PipeHost
    def queue(message):
        os.write(notification_write, (json.dumps(message) + '\n').encode())
    def usage(thread, amount):
        queue(dict(method='thread/tokenUsage/updated', params=dict(threadId=thread,
            tokenUsage=dict(total=dict(inputTokens=amount, cachedInputTokens=0, outputTokens=2)))))
    try:
        root = start(p)
        _invoke(root, 'accepted')
        worker = attached_worker(p.runtime, root, 'accepted')
        worker.call_tool('worker_open_assignment', {})
        run_id = worker._run_id
        worker_thread = 'worker-' + run_id
        host, marker = p.coordinator.host, row(p)['host_json']
        loop_id = checkpoint(p)['current_loop_id']
        # Native completion reaches the durable sink through the real pipe,
        # transport reader and Root host adapter; no manual _event delivery.
        queue(dict(method='turn/completed', params=dict(threadId=host.identity.thread_id,
            turn=dict(id=host.turn_id, status='completed'))))
        host.poll(0)
        assert host.completion['id'] == checkpoint(p)['turn_id']
        p.root.call_tool('progression_command', dict(command='pause'))
        p.now[0] += 10
        if boundary == 'release':
            _write_result(worker, observe_tokens=False)
            assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
        else:
            assert p.runtime.runs.status(run_id).state == 'running'
        usage(worker_thread, 200 if boundary == 'release' else 100)
        usage(host.identity.thread_id, 20 if boundary == 'release' else 10)
        p.coordinator.tick()
        cp = checkpoint(p)
        assert cp['usage_records'][worker_thread]['counted_tokens']['input_tokens'] == (200 if boundary == 'release' else 100)
        assert cp['usage_records'][worker_thread]['loop_id'] == cp['current_loop_id'] == loop_id
        assert cp['usage_records'][worker_thread]['role'] == 'worker'
        assert budget(p)['observed_tokens'] == (224 if boundary == 'release' else 114)
        assert row(p)['reason'] == 'user_paused' and row(p)['state'] == 'paused'
        assert not cp.get('time_closeout_source_session') and cp.get('fault_class') is None
        assert len(host.prompts) == 1 and not host.connection.failed
        if host.closed:
            assert os.read(request_read, 1) == b''
        else:
            with pytest.raises(BlockingIOError):
                os.read(request_read, 1)  # No turn/start, interrupt, or permission RPC.
        if boundary == 'release':
            assert host.closed and p.coordinator.host is None and row(p)['host_json'] is None
            assert authorize(p) == 303  # Exact measured original usage permits a new consent.
        else:
            assert p.coordinator.host is host and not host.closed and row(p)['host_json'] == marker
            with pytest.raises(Exception):
                _invoke(root, 'cannot-dispatch-during-pause')
    finally:
        p.coordinator.close()
        child.stdin.close()
        child.stdout.close()
        os.close(notification_write)
        os.close(request_read)


@pytest.mark.parametrize('prior_stop', ['pause', 'stop', 'resource', 'tokens', 'simultaneous', 'disabled'])
def test_native_time_stop_preserves_prior_stop_authority(loop_ui, monkeypatch, prior_stop):
    p = loop_ui
    configure(p, max_calendar_seconds=20, max_elapsed_seconds=100, max_tokens=200000, closeout_reserve_tokens=10)
    assert authorize(p) == 303
    guarded_native(p, monkeypatch)
    root = start(p)
    _invoke(root, 'accepted')
    host, marker = p.coordinator.host, row(p)['host_json']
    if prior_stop in {'pause', 'stop'}:
        p.root.call_tool('progression_command', dict(command=prior_stop))
    elif prior_stop == 'resource':
        p.coordinator._save({}, reason='resource_limit', stop=True)
    elif prior_stop in {'tokens', 'simultaneous'}:
        host.event(dict(method='thread/tokenUsage/updated', params=dict(threadId=host.identity.thread_id,
            tokenUsage=dict(total=dict(inputTokens=200000, cachedInputTokens=0, outputTokens=1)))))
        if prior_stop == 'tokens':
            assert not p.coordinator._check_budget(row(p), p.coordinator._limits, allow_round=False)
    elif prior_stop == 'disabled':
        bindings = p.runtime.scheduler_bindings
        bindings.register_client(session_key=host.scheduler_session)
        bindings.set_client_enabled(session_key=host.scheduler_session, enabled=False, expected=True)
    reason, state = row(p)['reason'], row(p)['state']
    p.now[0] += 20
    failure = None
    try:
        p.coordinator.tick()
    except Exception as error:
        # The old composition throws before RPC sends, then silently rewrites
        # control authority in _bounded_tick. Inspect the actual MCP permission.
        assert getattr(error, 'code', None) == 'budget_deadline'
        failure = error
    attached = call(UnifiedMCPRouter(root), 'worker_attach', dict(name='accepted', thread_id='accepted-child'),
        session=host.identity.session_id)
    assert 'error' in attached, attached
    assert not checkpoint(p).get('time_closeout_source_session')
    if prior_stop not in {'simultaneous', 'disabled'}:
        assert row(p)['reason'] == reason and row(p)['state'] == state
    assert failure is None and row(p)['host_json'] == marker and not host.connection.failed


def test_new_unknown_rpc_fact_preserves_user_stop_and_blocks_time_closeout(loop_ui, monkeypatch):
    from scidiscovery.platforms.codex_app_server import HostError
    p = loop_ui
    configure(p, max_calendar_seconds=20, max_elapsed_seconds=100)
    assert authorize(p) == 303
    guarded_native(p, monkeypatch)
    root = start(p)
    _invoke(root, 'accepted')
    host, marker = p.coordinator.host, row(p)['host_json']
    host.connection.pending, host.connection.counter = None, 0
    host.connection.limits = SimpleNamespace(rpc_timeout_seconds=1)
    def lost_reply(*args):
        raise HostError('rpc_timeout', method='turn/interrupt')
    host.connection._send = lost_reply
    p.root.call_tool('progression_command', dict(command='pause'))
    with pytest.raises(HostError, match='rpc_timeout'):
        p.coordinator.tick()
    assert host.connection.failed and row(p)['reason'] == 'user_paused'
    assert checkpoint(p)['fault_class'] == 'outcome_unknown'
    p.now[0] += 20
    p.coordinator.tick()
    assert checkpoint(p)['fault_class'] == 'outcome_unknown' and row(p)['host_json'] == marker
    assert not checkpoint(p).get('time_closeout_source_session')
    assert 'error' in call(UnifiedMCPRouter(root), 'worker_attach',
        dict(name='accepted', thread_id='accepted-child'), session=host.identity.session_id)
    assert authorize(p) == 409


def test_interactive_time_and_token_stop_pauses_without_time_closeout(loop_ui):
    p = loop_ui
    configure(p, max_calendar_seconds=20, max_elapsed_seconds=100, max_tokens=200000, closeout_reserve_tokens=10)
    assert authorize(p) == 303
    root = start(p, mode='interactive')
    _invoke(root, 'accepted')
    p.now[0] += 20
    p.runtime.scheduler_bindings.observe_progression(instance_id=p.instance, expected_host=None,
        changes={}, reason='budget_exhausted', stop=True, usage_observation=dict(root_thread='interactive-root',
            identity={}, params=dict(threadId='interactive-root',
                tokenUsage=dict(total=dict(inputTokens=200000, cachedInputTokens=0, outputTokens=1)))))
    assert row(p)['state'] == 'paused' and row(p)['reason'] == 'budget_exhausted'
    assert not checkpoint(p).get('time_closeout_source_session')
    assert not root.call_tool('progression_status', {})['can_schedule']
    assert 'error' in call(UnifiedMCPRouter(root), 'worker_attach',
        dict(name='accepted', thread_id='accepted-child'), session='interactive-root')


def test_connected_pending_resume_expiry_uses_matching_terminal_without_poll(loop_ui, monkeypatch):
    p = loop_ui
    configure(p, max_calendar_seconds=20, max_elapsed_seconds=100)
    assert authorize(p) == 303
    guarded_native(p, monkeypatch)
    root = start(p)
    _invoke(root, 'accepted')
    host = p.coordinator.host
    host.finish()
    p.root.call_tool('progression_command', dict(command='pause'))
    p.root.call_tool('progression_command', dict(command='resume'))
    assert row(p)['state'] == 'pending' and p.coordinator.host is host
    p.now[0] += 20
    p.coordinator.tick()
    assert row(p)['reason'] == 'budget_exhausted' and checkpoint(p).get('fault_class') is None
    assert not host.connection.failed
    result(call(UnifiedMCPRouter(root), 'worker_attach', dict(name='accepted', thread_id='accepted-child'),
        session=host.identity.session_id))
    with pytest.raises(Exception):
        _invoke(root, 'new-run')


@pytest.mark.parametrize('terminal', [True, False])
def test_production_expiry_releases_only_exact_terminal_and_unblocks_other_instance(loop_ui, monkeypatch, terminal):
    from scidiscovery.artifact_agent.service.instance_archive import InstanceArchive
    from tests.operations.research_loop_fixtures import authorize_loop
    p = loop_ui
    configure(p, max_calendar_seconds=20, max_elapsed_seconds=100)
    assert authorize(p) == 303
    guarded_native(p, monkeypatch)
    start(p)
    host, marker = p.coordinator.host, row(p)['host_json']
    if terminal:
        host.event(dict(method='thread/tokenUsage/updated', params=dict(threadId=host.identity.thread_id,
            tokenUsage=dict(total=dict(inputTokens=10, cachedInputTokens=0, outputTokens=1)))))
        host.finish()
        p.coordinator.tick()  # Matching completion is settled; host stays active.
        assert checkpoint(p)['phase'] == 'idle' and p.coordinator.host is host
    p.now[0] += 20
    p.coordinator.tick()
    assert host.closed and p.coordinator.host is None and not host.connection.failed
    assert (row(p)['host_json'] is None) == terminal
    archive = InstanceArchive(p.runtime)
    preview = archive.preview(p.instance)
    assert preview['ready'] == terminal, preview
    assert authorize(p) == (303 if terminal else 409)
    if terminal:
        p.root.call_tool('progression_command', dict(command='stop'))
    else:
        assert row(p)['host_json'] == marker and checkpoint(p)['phase'] == 'running'
    bindings = p.runtime.scheduler_bindings
    other = bindings.create_instance(name='other-expiry', title='Other', objective='Separate authorized research.')
    other_user = 'sch_' + 'e' * 32
    bindings.bind_session(session_key=other_user, instance_id=other.instance_id)
    bindings.bind(instance=other.instance_id, namespace='artifact', name='goal',
        object_id=bindings.resolve(instance=p.instance, namespace='artifact', name='goal'))
    bindings.progression_command(instance_id=other.instance_id, session_key=other_user, command='pause')
    authorize_loop(p.runtime, other.instance_id, other_user, 'goal')
    bindings.progression_command(instance_id=other.instance_id, session_key=other_user,
        command='start', mode='background', objective_name='goal',
        objective_ref=p.runtime.artifacts.get_by_id(bindings.resolve(instance=other.instance_id,
            namespace='artifact', name='goal')).ref)
    selected = bindings.next_background_progression()
    assert (selected['instance_id'] if selected else None) == (other.instance_id if terminal else None)
    p.coordinator.tick()
    if terminal:
        assert p.coordinator.instance == other.instance_id and p.coordinator.host is not None
        assert p.coordinator.host.identity.thread_id != host.identity.thread_id
    else:
        assert p.coordinator.host is None and row(p)['host_json'] == marker


@pytest.mark.parametrize('case', ['before_poll', 'pending_resume', 'during_poll', 'unknown', 'user_pause'])
def test_real_native_guard_time_ordering_preserves_writer_and_unknown(loop_ui, monkeypatch, case):
    from scidiscovery.platforms import codex_progression
    from scidiscovery.platforms.codex_app_server import AppServer, HostError
    from scidiscovery.platforms.codex_root_host import CodexRootHost
    p = loop_ui
    configure(p, max_calendar_seconds=20, max_elapsed_seconds=100)
    assert authorize(p) == 303
    monkeypatch.setattr(codex_progression, 'time', SimpleNamespace(monotonic=lambda: p.now[0]))
    class GuardedHost(LoopHost):
        set_execution_deadline = codex_progression.CodexProgressionHost.set_execution_deadline
        guard_resources = codex_progression.CodexProgressionHost.guard_resources
        poll = CodexRootHost.poll
        def __init__(self, record, event):
            super().__init__(record, event)
            self.execution_deadline = self.resource_limit = self.terminal_transport_error = None
            self.connection = object.__new__(AppServer)
            self.connection.closed = self.connection.failed = False
            self.connection.checkpoint = self.guard_resources
            self.connection.selector = SimpleNamespace(select=lambda _: [])
    p.coordinator.host_factory = GuardedHost
    root = start(p)
    _invoke(root, 'accepted')
    host = p.coordinator.host
    assert host.execution_deadline == p.now[0] + 20
    marker = row(p)['host_json']
    prior = checkpoint(p)
    if case == 'user_pause':
        host.finish()
        p.root.call_tool('progression_command', dict(command='pause'))
        p.now[0] += 20
        p.coordinator.tick()
        assert row(p)['state'] == 'paused' and row(p)['reason'] == 'user_paused'
        assert not checkpoint(p).get('time_closeout_source_session')
        return
    if case == 'during_poll':
        def race():
            p.now[0] += 20
            host.guard_resources()
        host.connection.checkpoint = race
    else:
        if case == 'pending_resume':
            p.root.call_tool('progression_command', dict(command='pause'))
            p.root.call_tool('progression_command', dict(command='resume'))
            assert row(p)['state'] == 'pending' and row(p)['owner_session'] is None
            host.close()
            p.coordinator.host = None  # Service reconnect has not yet contacted this original writer.
        p.now[0] += 20
    if case == 'unknown':
        p.coordinator._save(dict(fault_class='outcome_unknown'))
    if case in {'during_poll', 'unknown'}:
        with pytest.raises(HostError, match='budget_deadline'):
            p.coordinator.tick()
        assert checkpoint(p)['fault_class'] == 'outcome_unknown' and host.connection.failed
    else:
        p.coordinator.tick()
        assert checkpoint(p).get('fault_class') is None and not host.connection.failed
    assert row(p)['host_json'] == marker
    assert all(checkpoint(p)[key] == prior[key] for key in ('turn_id', 'phase', 'rounds'))
    attached = call(UnifiedMCPRouter(root), 'worker_attach', dict(name='accepted', thread_id='accepted-child'), session=host.identity.session_id)
    assert ('error' in attached) == (case not in {'before_poll', 'pending_resume'})
    stranger = 'sch_' + 'd' * 32
    p.runtime.scheduler_bindings.bind_session(session_key=stranger, instance_id=p.instance)
    other = type(root)(p.facade(stranger))
    assert 'error' in call(UnifiedMCPRouter(other), 'worker_attach',
        dict(name='accepted', thread_id='stranger-child'), session='stranger-root')
    assert authorize(p) == 409  # Closing transport cannot authorize another loop.
    with pytest.raises(Exception, match='time budget exhausted'):
        p.root.call_tool('progression_command', dict(command='resume'))


def test_expired_active_admission_and_direct_schedule_leave_no_prepared_task(loop_ui):
    p = loop_ui
    configure(p, max_calendar_seconds=20, max_elapsed_seconds=100)
    assert authorize(p) == 303
    root = start(p, mode='interactive')
    bound, _ = root.facade._configured_operation_call(vars(OperationCallInput.model_validate(request('direct'))))
    p.now[0] += 20
    checked = root.call_tool('operation_preflight', request('new-research'))
    assert not checked['admissible'] and checked['reason_code'] == 'loop_budget_exhausted'
    with pytest.raises(Exception, match='loop_budget_exhausted'):
        _invoke(root, 'new-research')
    with pytest.raises(Exception, match='loop_budget_exhausted'):
        p.runtime.runs.schedule(bound, instance_id=p.instance, output_binding_name='direct.output',
            output_logical_name='direct.output', output_revision=1, output_binding_fingerprint='direct')
    assert not checkpoint(p).get('admissions')
    assert not p.runtime.runs.list(instance_id=p.instance)


@pytest.mark.parametrize('barrier,expiry', [(value, 'calendar') for value in
    (None, 'pause', 'stop', 'unknown', 'client', 'resource', 'tokens')] + [(None, 'enabled')])
def test_automatic_time_stop_preserves_exact_queued_first_attach_only(progression, barrier, expiry):
    p = progression
    if expiry == 'enabled':
        from tests.operations.test_progress_assist import configure as managed_configure
        managed_configure(p, max_calendar_seconds=10000)
    root = active(p)
    _invoke(root, 'accepted')
    run_id = p.runtime.scheduler_bindings.resolve(instance=p.instance, namespace='run', name='accepted')
    profile = p.runtime.runs.status(run_id).execution_profile['profile']
    if barrier != 'tokens':
        p.now[0] += 3600
    p.coordinator._check_budget(row(p), json.loads(row(p)['config_json'])['effective']['progression'])
    if barrier is None:
        assert budget(p)['time_exhaustion'] == ('enabled_time' if expiry == 'enabled' else 'calendar_deadline')
    if barrier in {'pause', 'stop'}:
        p.root.call_tool('progression_command', dict(command=barrier))
    elif barrier == 'unknown':
        p.coordinator._save(dict(fault_class='outcome_unknown'))
    elif barrier == 'client':
        bindings = p.runtime.scheduler_bindings
        bindings.register_client(session_key=root.facade.session_key)
        bindings.set_client_enabled(session_key=root.facade.session_key, enabled=False, expected=True)
    elif barrier in {'resource', 'tokens'}:
        p.coordinator._save({}, reason='resource_limit' if barrier == 'resource' else 'budget_exhausted', stop=True)
        if barrier == 'tokens':
            assert not checkpoint(p).get('time_closeout_source_session')
    gateway = UnifiedMCPRouter(root)
    attached = call(gateway, 'worker_attach', dict(name='accepted', thread_id='accepted-child'), session='native-root')
    if barrier:
        assert 'error' in attached
        return
    result(attached)
    result(call(gateway, 'worker_open_assignment', child='accepted-child', session='native-root', profile=profile))
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    compiled = p.catalog.operation('blind.csv.observe.v1')
    worker = LocalWorkerMCPRouter(p.runtime.runs, operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest, run_id=run_id, trusted_caller=('native-root', 'accepted-child'))
    worker.call_tool('worker_open_assignment', {})
    _write_result(worker)
    assert result(call(gateway, 'worker_submit_result', child='accepted-child', session='native-root', profile=profile))['state'] == 'completed'
    with pytest.raises(Exception):
        _invoke(root, 'unrelated')
    assert len(checkpoint(p)['admissions']) == 1


def test_human_continue_uses_effective_time_and_cannot_refresh_deadline(human_ui):
    ui, p = human_ui, human_ui.p
    deadline = budget(p)['deadline_at']
    p.now[0] += 3600
    assert budget(p)['remaining_seconds'] > 0 and budget(p)['effective_remaining_seconds'] == 0
    assert submit(ui, confirmation_binding=fresh_binding(ui)) == 409
    assert budget(p)['deadline_at'] == deadline and row(p)['state'] == 'paused'


def test_old_state_and_archive_reject_missing_calendar_authority(loop_ui):
    p = loop_ui
    with p.runtime.scheduler_bindings._connect() as db:
        db.execute('PRAGMA user_version=7')
        from scidiscovery.artifact_agent.service.instance_archive_records import schema
        archived_schema = schema(db)
    with pytest.raises(Exception, match='incompatible scheduler control schema'):
        SchedulerBindingService(p.runtime.scheduler_bindings.database_path)
    from scidiscovery.artifact_agent.service.instance_archive_records import execution_settings_restore_view
    with pytest.raises(Exception, match='unsupported scheduler control schema'):
        execution_settings_restore_view(dict(schema=archived_schema, tables={}))


def test_archive_pause_and_restore_keep_original_deadline(loop_ui):
    from tests.operations.synchronous_archive_fixture import SynchronousFixtureArchive
    from tests.operations.test_instance_archive import save_archive, restore_archive
    p = loop_ui
    configure(p, max_calendar_seconds=40, max_elapsed_seconds=100)
    assert authorize(p) == 303
    deadline = budget(p)['deadline_at']
    p.now[0] += 10
    p.root.call_tool('progression_command', dict(command='pause'))
    p.runtime.runs._synchronous_archive_fixture = True
    archive = SynchronousFixtureArchive(p.runtime)
    save_archive(archive, p.instance)
    archived = archive.archived_model(p.instance).overview(p.instance)['progression']
    assert archived['historical'] and archived['budget']['calendar_remaining_seconds'] == 30
    assert archived['loop']['deadline_at'] == deadline
    p.now[0] += 30
    restore_archive(archive, p.instance)
    p.runtime.scheduler_bindings.bind_session(session_key=p.user, instance_id=p.instance)
    assert budget(p)['effective_remaining_seconds'] == 0 and budget(p)['deadline_at'] == deadline
    with pytest.raises(Exception, match='calendar_deadline'):
        p.root.call_tool('progression_command', dict(command='resume'))


def test_accepted_exact_review_can_attach_and_seal_after_time_expiry(progression, monkeypatch):
    import hashlib
    from blind_csv_plugin.contracts import CsvReview
    from tests.operations.test_science_pause_accepted_work import accepted_before_pause
    from tests.operations.test_l3_review_and_human_policy import _envelope
    p = progression
    root, gateway, run_id, profile = accepted_before_pause(p, monkeypatch, review=True,
        max_calendar_seconds=20, max_elapsed_seconds=100)
    req = p.runtime.runs.review_wait(run_id)['request']
    root.call_tool('operation_invoke', req)
    p.now[0] += 20
    assert not p.coordinator._check_budget(row(p), json.loads(row(p)['config_json'])['effective']['progression'])
    assert row(p)['reason'] == 'budget_exhausted'
    result(call(gateway, 'worker_attach', dict(name='exact-review', thread_id='independent-child'), session='native-root'))
    opened = result(call(gateway, 'worker_open_assignment', child='independent-child', session='native-root', profile=profile))
    subject = p.runtime.scheduler_bindings.resolve(instance=p.instance, namespace='artifact', name='prior-2.output')
    payload = CsvReview(subject_sha256=hashlib.sha256(p.runtime.artifacts.read(p.runtime.artifacts.get_by_id(subject).ref)).hexdigest(),
        verdict='pass', rationale='Independent review of the previously accepted exact subject.').model_dump(mode='json')
    Path(opened['output_directory'], 'result.json').write_bytes(_envelope(payload))
    assert result(call(gateway, 'worker_submit_result', child='independent-child', session='native-root', profile=profile))['state'] == 'completed'
    assert p.runtime.runs.review_wait(run_id)['state'] == 'completed'
    assert not root.call_tool('operation_preflight', dict(req, name='new-review'))['admissible']
    with pytest.raises(Exception):
        _invoke(root, 'new-research')


@pytest.mark.parametrize('submitted', [False, True])
def test_independent_execution_time_gate_preserves_submitted_cancel_and_collect(tmp_path, monkeypatch, submitted):
    from tests.operations.test_r4_execution_approval_identity import _setup, _create_effect, _effect_call, _decide_execution_approval
    from tests.operations.research_loop_fixtures import authorize_loop
    runtime, instance, adapter, facade, root, _ = _setup(tmp_path)
    bindings, now, session = runtime.scheduler_bindings, [1000.0], 'loop-effects'
    bindings.progression_clock = lambda: now[0]
    bindings.bind_session(session_key=session, instance_id=instance.instance_id)
    facade.session_key = session
    root.call_tool('artifact_ingest_text', dict(name='goal', text='A frozen-time effect fixture.'))
    root.call_tool('progression_command', dict(command='pause'))
    authorize_loop(runtime, instance.instance_id, session, 'goal')
    root.call_tool('progression_command', dict(command='resume'))
    _create_effect(root, name='original-effect')
    _decide_execution_approval(runtime, root, name='original-effect')
    if submitted:
        assert root.call_tool('execution_start', dict(name='original-effect'), surface='execution')['state'] == 'submitted'
    now[0] += 3600
    checked = root.call_tool('operation_preflight', _effect_call('new-effect'))
    assert not checked['admissible'] and checked['reason_code'] == 'loop_budget_exhausted'
    with pytest.raises(Exception, match='loop_budget_exhausted'):
        root.call_tool('operation_invoke', _effect_call('new-effect'))
    if not submitted:
        with pytest.raises(Exception, match='loop_budget_exhausted'):
            root.call_tool('execution_start', dict(name='original-effect'), surface='execution')
        assert adapter.submit_count == 0
        return
    bindings.observe_progression(instance_id=instance.instance_id, expected_host=None,
        changes={}, reason='budget_exhausted', stop=True)
    assert bindings.progression_status(instance_id=instance.instance_id)['state'] == 'paused'
    monkeypatch.setattr(adapter, 'cancel', lambda _: 'cancelled', raising=False)
    monkeypatch.setattr(adapter, 'status', lambda _: 'cancelled', raising=False)
    assert root.call_tool('execution_cancel', dict(name='original-effect'), surface='execution')['state'] == 'cancelled'
    collected = []
    facade.execution_collection = SimpleNamespace(collect=lambda execution_id, **kw: collected.append(execution_id) or dict(state='queued'))
    assert root.call_tool('execution_collect', dict(name='original-effect', total_seconds=10), surface='execution')['collection']['state'] == 'queued'
    assert len(collected) == 1 and adapter.submit_count == 1
    root.call_tool('progression_command', dict(command='pause'))
    with pytest.raises(Exception, match='paused'):
        root.call_tool('execution_cancel', dict(name='original-effect'), surface='execution')
