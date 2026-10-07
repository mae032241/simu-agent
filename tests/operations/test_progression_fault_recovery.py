"""Finite recovery through real persisted UI/MCP/control and native boundaries."""
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from scidiscovery.artifact_agent.service.progression import ProgressionCoordinator, ProgressionFault
from scidiscovery.platforms.codex_app_server import AppServer, HostError, HostLimits
from scidiscovery.platforms.codex_root_host import CodexRootHost
from tests.operations.test_progression import progression, checkpoint, row, Host
from tests.operations.test_progress_assist import configure
from tests.operations.test_progression_pacing import busy
from tests.operations.test_local_worker_contracts import _invoke, _worker, _write_result
from tests.operations.test_research_loop_budget import loop_ui, authorize, loop_form, historical_checkpoint
from tests.operations.test_loop_review_budget import configure as ui_configure


def failed(p, *, thread=None, turn=None, status='failed'):
    host = p.coordinator.host
    completion = dict(id=turn or host.turn_id, status=status)
    if thread is None and turn is None:
        host.completion = completion
    host.event(dict(method='turn/completed', params=dict(threadId=thread or host.identity.thread_id, turn=completion)))


def start(p, **limits):
    configure(p, **dict(observation_retries=0, recovery_backoff_seconds=1, poll_seconds=1) | limits)
    p.coordinator.tick()
    return p.coordinator.host


def snapshot_busy(p, monkeypatch):
    def unavailable(_):
        raise busy()
    monkeypatch.setattr(p.coordinator, '_snapshot', unavailable)


def ready(p):
    p.now[0] = checkpoint(p)['recovery']['next_at']


def completed_worker(p):
    host=start(p,observation_retries=6,observation_retry_seconds=.12,
        observation_backoff_seconds=.01,max_recoveries=1)
    root=type(p.root)(p.facade(host.scheduler_session))
    _invoke(root,'sealed')
    worker=_worker(p.catalog,p.runtime)
    worker.call_tool('worker_open_assignment',{})
    _write_result(worker)
    worker.call_tool('worker_submit_result',{})
    host.finish();p.now[0]+=2
    return host


def frozen_loops(cp):
    # budget_snapshot is a live balance; these are the immutable grant fields.
    return {identity:{key:value[key] for key in ('authorized_at','deadline_at','authorized_by',
        'request_fingerprint','config','objective_name','objective_ref_json')}
        for identity,value in cp['loop_authorizations'].items()}


@pytest.mark.parametrize('release',[True,False])
def test_post_brief_real_database_contention_obeys_existing_recovery_budget(progression,monkeypatch,release):
    p=progression;host=completed_worker(p);before=checkpoint(p)
    blocker=sqlite3.connect(p.runtime.runs.database_path,timeout=0,check_same_thread=False)
    brief=p.coordinator._brief;armed=[];timer=None
    def brief_then_lock(*args):
        nonlocal timer
        value=brief(*args)
        if not armed or not release:
            armed.append(1);blocker.execute('BEGIN EXCLUSIVE')
            if release:
                timer=threading.Timer(.025,blocker.rollback);timer.start()
        return value
    monkeypatch.setattr(p.coordinator,'_brief',brief_then_lock)
    started=time.monotonic()
    try:
        p.coordinator.tick()
        assert time.monotonic()-started<.8
        cp=checkpoint(p)
        assert frozen_loops(cp)==frozen_loops(before)
        assert cp['budget']['effective_remaining_seconds']<=before['budget']['effective_remaining_seconds']
        assert cp['current_loop_id']==before['current_loop_id'] and cp['admissions']==before['admissions']
        if release:
            assert len(host.prompts)==2 and cp['recovery'].get('used',0)==0
            assert row(p)['state']=='active'
        else:
            assert len(host.prompts)==1 and cp['recovery']['used']==1 and cp['attempts']==before['attempts']
            assert cp['recovery']['pending_kind']=='observation' and row(p)['state']=='active'
            diagnostic=cp['fault_diagnostic']
            assert diagnostic['sqlite_errorcode']==sqlite3.SQLITE_BUSY and diagnostic['sqlite_errorname']=='SQLITE_BUSY'
            assert diagnostic['stage']=='_terminal_delivery' and diagnostic['phase']=='idle'
            blocker.rollback()
            p.coordinator.tick()
            assert checkpoint(p)['recovery']['used']==1 and len(host.prompts)==1
            ready(p)
            with pytest.raises(ProgressionFault,match='observation_retry_exhausted'):p.coordinator.tick()
            assert row(p)['state']=='paused' and checkpoint(p)['recovery']['used']==1
            assert len(host.prompts)==1
    finally:
        if timer:timer.join()
        blocker.rollback();blocker.close()
    if not release:
        p.coordinator.tick()
        assert len(host.prompts)==1
    assert len(p.runtime.runs.list(instance_id=p.instance))==1
    assert frozen_loops(checkpoint(p))==frozen_loops(before)


def test_permanent_database_fault_keeps_bounded_safe_diagnostic_and_never_retries(progression,monkeypatch):
    p=progression;host=completed_worker(p);before=checkpoint(p);calls=[]
    brief=p.coordinator._brief
    def bad_status(_):
        calls.append(1)
        with sqlite3.connect(p.runtime.runs.database_path) as db:
            db.execute('SELECT * FROM "credential_do_not_emit_OR_SQL_text"')
    def brief_then_fail(*args):
        value=brief(*args);monkeypatch.setattr(p.runtime.runs,'status',bad_status);return value
    monkeypatch.setattr(p.coordinator,'_brief',brief_then_fail)
    with pytest.raises(sqlite3.OperationalError):p.coordinator.tick()
    cp=checkpoint(p);diagnostic=cp['fault_diagnostic']
    assert calls==[1] and row(p)['state']=='paused' and row(p)['reason']=='host_fault'
    assert cp['fault_code']=='OperationalError' and cp['fault_class']=='configuration_or_runtime'
    assert cp['recovery'].get('used',0)==0 and len(host.prompts)==1 and host.closed
    assert frozen_loops(cp)==frozen_loops(before) and cp['admissions']==before['admissions']
    assert diagnostic['stage']=='_terminal_delivery' and diagnostic['phase']=='idle'
    assert diagnostic['sqlite_errorcode']==sqlite3.SQLITE_ERROR and diagnostic['sqlite_errorname']=='SQLITE_ERROR'
    assert 0<len(diagnostic['frames'])<=4 and len(json.dumps(diagnostic).encode())<2048
    assert all(set(frame)=={'module','function','line'} for frame in diagnostic['frames'])
    assert all(frame['module'].startswith('scidiscovery.') for frame in diagnostic['frames'])
    assert 'credential_do_not_emit' not in json.dumps(diagnostic)
    assert not ({'message','sql','locals','filename','path','traceback'} & set(diagnostic))


def test_local_observation_backoff_success_and_health_never_refunds(progression, monkeypatch):
    p = progression
    host = start(p)
    host.finish()
    p.now[0] += 2
    with monkeypatch.context() as blocked:
        snapshot_busy(p, blocked)
        p.coordinator.tick()
    cp = checkpoint(p)
    assert cp['recovery']['used'] == 1 and cp['recovery']['consecutive_failures'] == 1
    assert cp['recovery']['pending_kind'] == 'observation' and cp['attempts'] == 0
    assert p.coordinator.host is host and not host.closed
    p.coordinator.tick()
    assert checkpoint(p)['recovery'] == cp['recovery'] and len(host.prompts) == 1
    ready(p)
    p.coordinator.tick()
    recovery = checkpoint(p)['recovery']
    assert recovery['used'] == 1 and recovery['consecutive_failures'] == 0
    assert recovery['pending_kind'] is None and recovery['next_at'] is None
    assert row(p)['state'] == 'active' and len(host.prompts) == 1
    assert p.root.call_tool('progression_status', {})['budget']['recovery']['by_kind'] == {'observation': 1}


@pytest.mark.parametrize('limit', ['consecutive', 'cumulative'])
def test_observation_failures_exhaust_separate_limits(progression, monkeypatch, limit):
    p = progression
    host = start(p, max_recoveries=1 if limit == 'cumulative' else 8, recovery_failure_threshold=3)
    host.finish()
    p.now[0] += 2
    snapshot_busy(p, monkeypatch)
    allowed = 1 if limit == 'cumulative' else 2
    for used in range(1, allowed+1):
        p.coordinator.tick()
        assert checkpoint(p)['recovery']['used'] == used
        ready(p)
    with pytest.raises(ProgressionFault, match='observation_retry_exhausted'):
        p.coordinator.tick()
    cp = checkpoint(p)
    assert cp['recovery']['used'] == allowed and cp['recovery']['consecutive_failures'] == allowed+1
    assert row(p)['state'] == 'paused' and cp['recovery']['pending_kind'] is None


def test_confirmed_failed_root_selects_next_decision_without_replacing_accepted_task(progression):
    p = progression
    host = start(p, recover_failed_turns=True)
    root = type(p.root)(p.facade(host.scheduler_session))
    _invoke(root, 'accepted')
    before = checkpoint(p)
    with p.runtime.scheduler_bindings._connect() as db:
        dispatches = [tuple(value) for value in db.execute('SELECT * FROM scheduler_dispatch_intents')]
    old_turn = host.turn_id
    failed(p)
    p.coordinator.tick()
    cp = checkpoint(p)
    assert cp['phase'] == 'idle' and cp['turn_id'] is None
    assert cp['recovery']['used'] == cp['attempts'] == 1 and cp['rounds'] == before['rounds']
    assert cp['recovery']['last_failure']['code'] == 'native_turn_failed'
    assert cp['admissions'] == before['admissions'] and row(p)['state'] == 'active'
    failed(p, turn=old_turn)  # Consumed old terminal is transport only.
    p.coordinator.tick()
    assert checkpoint(p)['recovery']['used'] == 1 and len(host.prompts) == 1
    ready(p)
    p.coordinator.tick()
    assert len(host.prompts) == 2 and checkpoint(p)['rounds'] == before['rounds']+1
    assert 'accepted' in host.prompts[-1] and 'do not create a replacement' in host.prompts[-1]
    assert checkpoint(p)['admissions'] == before['admissions']
    assert len(p.runtime.runs.list(instance_id=p.instance)) == 1
    with p.runtime.scheduler_bindings._connect() as db:
        assert [tuple(value) for value in db.execute('SELECT * FROM scheduler_dispatch_intents')] == dispatches
    failed(p, turn=old_turn)
    failed(p, thread='foreign-root')
    assert checkpoint(p)['recovery']['used'] == 1
    host.finish()
    p.coordinator.tick()
    assert checkpoint(p)['recovery']['consecutive_failures'] == 0
    assert checkpoint(p)['recovery']['used'] == 1 and checkpoint(p)['attempts'] == 1


@pytest.mark.parametrize('kind', ['default', 'interrupted', 'native_limit', 'rounds', 'tokens'])
def test_failed_turn_policy_and_original_budgets_stop_recovery(progression, kind):
    p = progression
    limits = {'recover_failed_turns': kind != 'default'}
    if kind == 'native_limit':
        limits['max_attempts'] = 1
    elif kind == 'rounds':
        limits['max_rounds'] = 1
    host = start(p, **limits)
    if kind == 'tokens':
        host.event(dict(method='thread/tokenUsage/updated', params=dict(threadId=host.identity.thread_id,
            tokenUsage=dict(total=dict(inputTokens=2000000, cachedInputTokens=0, outputTokens=0)))))
    failed(p, status='interrupted' if kind == 'interrupted' else 'failed')
    p.coordinator.tick()
    assert row(p)['state'] == 'paused' and checkpoint(p)['recovery'].get('used', 0) == 0
    assert len(host.prompts) == 1


@pytest.mark.parametrize('control', ['pause', 'stop', 'time', 'tokens', 'resource', 'disabled', 'science'])
def test_delayed_recovery_respects_stops_before_native_entry(progression, control):
    p = progression
    host = start(p, recover_failed_turns=True)
    failed(p)
    p.coordinator.tick()
    used = checkpoint(p)['recovery']['used']
    polls = []
    host.poll = lambda *_: polls.append(1)
    ready(p)
    if control in {'pause', 'stop'}:
        p.root.call_tool('progression_command', dict(command=control))
    elif control == 'time':
        p.now[0] += 3600
    elif control == 'tokens':
        host.event(dict(method='thread/tokenUsage/updated', params=dict(threadId=host.identity.thread_id,
            tokenUsage=dict(total=dict(inputTokens=2000000, cachedInputTokens=0, outputTokens=0)))))
    elif control == 'resource':
        host.resources = SimpleNamespace(sample=lambda:dict(owned_tree_rss_bytes=1000000000, control_daemon_rss_bytes=0), terminate=lambda:None)
    elif control == 'disabled':
        bindings = p.runtime.scheduler_bindings
        bindings.register_client(session_key=host.scheduler_session)
        bindings.set_client_enabled(session_key=host.scheduler_session, enabled=False, expected=True)
    else:
        p.coordinator._save({}, reason='scientific_progress_persistent_gap', stop=True)
    p.coordinator.tick()
    assert row(p)['state'] in {'paused', 'stopped'} and len(host.prompts) == 1
    assert checkpoint(p)['recovery']['used'] == used
    if control in {'tokens', 'resource'}:
        assert not polls
    if control in {'pause', 'stop'}:
        assert row(p)['reason'] == 'user_'+('paused' if control == 'pause' else 'stopped')


def test_backoff_and_counters_survive_restart_goal_change_and_manual_resume(progression):
    p = progression
    p.root.call_tool('progression_command', dict(command='takeover', mode='interactive'))
    p.root.call_tool('artifact_ingest_text', dict(name='other-goal', text='Keep original accepted work and remaining budget.'))
    host = start(p, recover_failed_turns=True)
    failed(p)
    p.coordinator.tick()
    original = checkpoint(p)['recovery'].copy()
    host.close()
    p.coordinator.host = None
    factories = []
    def factory(record, event):
        factories.append(record['host_json'])
        return Host(record, event)
    p.coordinator.host_factory = factory
    p.coordinator.tick()
    assert not factories and checkpoint(p)['recovery'] == original
    p.root.call_tool('progression_command', dict(command='pause'))
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='other-goal'))
    p.coordinator.tick()
    assert not factories and checkpoint(p)['recovery'] == original
    ready(p)
    p.coordinator.tick()
    assert len(factories) == 1 and checkpoint(p)['recovery']['used'] == original['used']
    assert checkpoint(p)['attempts'] == 1 and checkpoint(p)['rounds'] == 2


def test_busy_fault_not_approved_until_durable_write_and_pause_wins(progression, monkeypatch):
    p = progression
    host = start(p)
    bindings = p.runtime.scheduler_bindings
    with monkeypatch.context() as blocked:
        blocked.setattr(bindings, 'progression_status', lambda **_: (_ for _ in ()).throw(busy()))
        blocked.setattr(bindings, 'observe_progression', lambda **_: (_ for _ in ()).throw(busy()))
        with pytest.raises(ProgressionFault, match='observation_retry_exhausted'):
            p.coordinator.tick()
        assert p.coordinator._pending_fault and p.coordinator.host is host and not host.closed
    assert checkpoint(p)['recovery'] == {}
    p.root.call_tool('progression_command', dict(command='pause'))
    p.coordinator.tick()
    assert row(p)['reason'] == 'user_paused' and checkpoint(p)['recovery'].get('used', 0) == 0
    assert p.coordinator._pending_fault is None


@pytest.mark.parametrize('stop', [None, 'pause', 'stop', 'time'])
def test_root_workspace_lock_defers_fault_write_without_closing_or_restarting_native_host(progression, monkeypatch, stop):
    p = progression
    host = start(p, observation_retries=1, observation_retry_seconds=.06,
        observation_backoff_seconds=.01, event_wait_seconds=.01)
    root = type(p.root)(p.facade(host.scheduler_session))
    entered, release = threading.Event(), threading.Event()
    prepare = p.runtime.runs.backend.prepare
    errors = []
    def slow_workspace(**kwargs):
        entered.set()
        assert release.wait(3)
        return prepare(**kwargs)
    def invoke():
        try:
            _invoke(root, 'accepted')
        except BaseException as error:
            errors.append(error)
    monkeypatch.setattr(p.runtime.runs.backend, 'prepare', slow_workspace)
    worker = threading.Thread(target=invoke)
    worker.start()
    try:
        assert entered.wait(2)
        p.coordinator._budget_saved_at = None
        with pytest.raises(ProgressionFault, match='observation_retry_exhausted'):
            p.coordinator.tick()
        assert p.coordinator._pending_fault is not None
        assert p.coordinator.host is host and not host.closed and not host.interrupted
        assert host.completion is None and len(host.prompts) == 1
    finally:
        release.set()
        worker.join(3)
    assert not worker.is_alive() and errors == []
    if stop in {'pause', 'stop'}:
        p.root.call_tool('progression_command', dict(command=stop))
    elif stop == 'time':
        p.now[0] += 1e6
        with pytest.raises(ProgressionFault, match='budget_deadline'):
            p.coordinator.tick()
        assert host.closed and p.coordinator.host is None
    p.coordinator.tick()  # Only persist the deferred exact fault, not a native action.
    cp = checkpoint(p)
    assert cp['fault_diagnostic']['stage'] == '_save' and cp['fault_diagnostic']['phase'] == 'running'
    assert cp['admissions']['accepted']['state'] == 'accepted'
    if stop:
        assert cp['recovery'].get('used', 0) == 0 and row(p)['state'] in {'paused', 'stopped'}
        p.coordinator.tick()
        assert p.coordinator.host in {None, host} and len(host.prompts) == 1
        assert checkpoint(p)['attempts'] == 0 and len(p.runtime.runs.list(instance_id=p.instance)) == 1
        return
    assert cp['recovery']['by_kind'] == {'observation': 1}
    ready(p)
    p.coordinator.tick()
    assert p.coordinator.host is host and not host.closed and not host.interrupted
    assert len(host.prompts) == 1 and host.completion is None
    assert checkpoint(p)['recovery']['pending_kind'] is None and checkpoint(p)['attempts'] == 0
    assert len(p.runtime.runs.list(instance_id=p.instance)) == 1


@pytest.mark.parametrize('boundary', ['deadline', 'deadline_during_retry', 'resource', 'closed'])
def test_pending_fault_stops_exact_client_while_real_scheduling_lock_remains_held(progression, boundary):
    from scidiscovery.platforms.codex_progression import CodexProgressionHost
    from scidiscovery.platforms.process_observation import OwnedProcessTree
    p = progression
    host = start(p, observation_retries=1, observation_retry_seconds=.06,
        observation_backoff_seconds=.01, event_wait_seconds=.01)
    bindings = p.runtime.scheduler_bindings
    entered, release = threading.Event(), threading.Event()
    def hold_lock():
        with bindings.scheduling_lock():
            entered.set()
            assert release.wait(4)
    owner = threading.Thread(target=hold_lock)
    owner.start()
    child = None
    try:
        assert entered.wait(2)
        p.coordinator._budget_saved_at = None
        with pytest.raises(ProgressionFault, match='observation_retry_exhausted'):
            p.coordinator.tick()
        assert p.coordinator.host is host and not host.closed
        original = json.loads(json.dumps(p.coordinator._pending_fault))
        if boundary == 'deadline':
            p.now[0] = p.coordinator._goal_deadline
        elif boundary == 'deadline_during_retry':
            samples = []
            def deadline_after_first_busy():
                samples.append(1)
                if len(samples) == 2:
                    p.now[0] = p.coordinator._goal_deadline
            host.guard_resources = deadline_after_first_busy
        elif boundary == 'closed':
            p.coordinator.closed.set()
        else:
            child = subprocess.Popen([sys.executable, '-c',
                "import time; print('ready', flush=True); time.sleep(20)"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            assert child.stdout.readline().strip() == 'ready'
            host.resources = OwnedProcessTree(child.pid)
            host.resource_limit = 1048576
            host.guard_resources = lambda: CodexProgressionHost.guard_resources(host)
        expected = ('observation_budget_expired' if boundary == 'deadline_during_retry' else
            'budget_deadline' if boundary == 'deadline' else
            'resource_limit' if boundary == 'resource' else 'coordinator_closed')
        with pytest.raises((ProgressionFault, HostError), match=expected):
            p.coordinator.tick()
        assert not release.is_set() and owner.is_alive()  # The stop did not depend on lock release.
        assert host.closed and p.coordinator.host is None and len(host.prompts) == 1
        pending = p.coordinator._pending_fault
        assert pending['changes']['fault_code'] == original['changes']['fault_code']
        assert pending['changes']['fault_diagnostic'] == original['changes']['fault_diagnostic']
        assert pending['changes']['fault_class'] == 'outcome_unknown' and 'recoverable_fault' not in pending
        assert row(p)['host_json'] and checkpoint(p)['phase'] == 'running'
        if child is not None:
            child.wait(timeout=3)
    finally:
        release.set()
        owner.join(3)
        if child is not None:
            if child.poll() is None:
                child.terminate()
            child.wait(timeout=3)
            child.stdout.close()
    assert not owner.is_alive()
    p.coordinator.tick()  # Retired client: terminal fault IO is still allowed after the bound.
    cp = checkpoint(p)
    assert p.coordinator._pending_fault is None and p.coordinator.host is None
    assert cp['fault_class'] == 'outcome_unknown' and cp['fault_code'] == 'observation_retry_exhausted'
    assert cp.get('recovery', {}).get('used', 0) == 0 and row(p)['state'] == 'paused'
    assert row(p)['host_json'] and cp['phase'] == 'running'  # Client retirement is not writer quiescence.


def test_first_post_activation_observation_retry_uses_new_host_binding(progression, monkeypatch):
    p = progression
    configure(p, observation_retries=0)
    bindings = p.runtime.scheduler_bindings
    observe = bindings.observe_progression
    attempts = []
    def busy_once(**kwargs):
        attempts.append(kwargs['expected_host'])
        if len(attempts) == 1:
            raise busy()
        return observe(**kwargs)
    monkeypatch.setattr(bindings, 'observe_progression', busy_once)
    p.coordinator.tick()
    assert row(p)['host_json'] and checkpoint(p)['recovery']['used'] == 1
    assert p.coordinator._pending_fault is None and not p.coordinator.host.closed
    assert attempts[0] == attempts[1] == json.loads(row(p)['host_json'])


@pytest.mark.parametrize('sqlite_code', ['busy', 'locked'])
def test_global_selection_failure_after_release_keeps_old_loop_and_selects_next_authorized_instance(progression, monkeypatch, sqlite_code):
    import sqlite3
    from tests.operations.research_loop_fixtures import authorize_loop
    p = progression
    host = start(p)
    host.finish()
    p.root.call_tool('progression_command', dict(command='pause'))
    p.coordinator.tick()  # Real terminal settlement/release clears the durable writer.
    assert host.closed and p.coordinator.host is None and row(p)['host_json'] is None
    original = checkpoint(p)
    bindings = p.runtime.scheduler_bindings
    other = bindings.create_instance(name='after-release', title='Next research', objective='A separately authorized frozen goal.')
    user = 'sch_'+'e'*32
    bindings.bind_session(session_key=user, instance_id=other.instance_id)
    ref = p.runtime.artifacts.get_by_id(bindings.resolve(instance=p.instance, namespace='artifact', name='goal')).ref
    bindings.bind(instance=other.instance_id, namespace='artifact', name='goal', object_id=ref.artifact_id)
    bindings.progression_command(instance_id=other.instance_id, session_key=user, command='pause')
    authorize_loop(p.runtime, other.instance_id, user, 'goal')
    bindings.progression_command(instance_id=other.instance_id, session_key=user,
        command='start', mode='background', objective_name='goal', objective_ref=ref)
    factories = []
    def factory(record, event):
        factories.append(record['instance_id'])
        value = Host(record, event)
        value.identity = SimpleNamespace(thread_id='next-root', session_id='next-root')
        value.scheduler_session = 'sch_'+'f'*32
        return value
    p.coordinator.host_factory = factory
    first_error = None
    with monkeypatch.context() as blocked:
        def unavailable():
            error = busy()
            error.sqlite_errorcode = sqlite3.SQLITE_LOCKED if sqlite_code == 'locked' else sqlite3.SQLITE_BUSY
            raise error
        blocked.setattr(bindings, 'next_background_progression', unavailable)
        try:
            p.coordinator.tick()
        except Exception as error:
            first_error = error
    resumed_error = None
    try:
        p.coordinator.tick()  # Store restored; no restart or forced pending-fault reset.
    except Exception as error:
        resumed_error = error
    assert resumed_error is None, f'Store recovered but selection is stuck: {resumed_error}'
    assert isinstance(first_error, ProgressionFault) and first_error.code == 'observation_retry_exhausted'
    assert p.coordinator._pending_fault is None and checkpoint(p) == original
    assert factories == [other.instance_id] and p.coordinator.instance == other.instance_id
    assert len(p.coordinator.host.prompts) == 1


def test_offline_backoff_expiry_stops_before_host_factory(progression):
    p = progression
    host = start(p, recover_failed_turns=True, max_calendar_seconds=2, recovery_backoff_seconds=60)
    failed(p)
    p.coordinator.tick()
    host.close()
    p.coordinator.host = None
    p.coordinator.host_factory = lambda *_:pytest.fail('time expiry precedes native reconnection')
    p.now[0] += 2
    p.coordinator.tick()
    assert row(p)['reason'] == 'budget_exhausted' and row(p)['state'] == 'paused'
    assert checkpoint(p)['recovery']['used'] == 1


@pytest.mark.parametrize('stage', ['start', 'writer_poll', 'factory'])
def test_unknown_native_windows_never_retry_even_with_policy_enabled(progression, monkeypatch, stage):
    p = progression
    if stage == 'factory':
        configure(p, recover_failed_turns=True)
        calls = []
        def factory(*_):
            calls.append(1)
            error = HostError('rpc_timeout', method='thread/start')
            error.native_outcome_unknown = True
            raise error
        p.coordinator.host_factory = factory
    else:
        host = start(p, recover_failed_turns=True)
        calls = []
        def unknown(*_):
            calls.append(1)
            host.connection = SimpleNamespace(failed=True)
            raise HostError('rpc_timeout', method='turn/start' if stage == 'start' else None)
        if stage == 'start':
            host.finish()
            p.root.call_tool('progression_message', dict(name='question', text='A new decision is needed.'))
            p.now[0] += 2
            host.start_turn = unknown
        else:
            host.poll = unknown
    with pytest.raises(HostError, match='rpc_timeout'):
        p.coordinator.tick()
    cp = checkpoint(p)
    assert cp['fault_class'] == 'outcome_unknown' and cp['recovery'].get('used', 0) == 0
    marker = row(p)['host_json']
    if stage == 'writer_poll':
        bindings = p.runtime.scheduler_bindings
        p.coordinator._limits['observation_retries'] = 0
        with monkeypatch.context() as blocked:
            blocked.setattr(bindings, 'next_background_progression', lambda:(_ for _ in ()).throw(busy()))
            with pytest.raises(ProgressionFault, match='observation_retry_exhausted'):
                p.coordinator.tick()
        assert p.coordinator._pending_fault is None and checkpoint(p) == cp
        assert row(p)['host_json'] == marker and marker is not None
    p.coordinator.tick()
    assert calls == [1] and row(p)['state'] == 'paused'


def test_ui_freezes_recovery_policy_and_retired_loop_snapshot(loop_ui):
    p = loop_ui
    ui_configure(p, max_recoveries=4, recovery_failure_threshold=2, recover_failed_turns=True)
    form = loop_form(p)
    assert authorize(p, form) == 303
    identity = checkpoint(p)['current_loop_id']
    from tests.operations.test_m6a_direct_instance_management import _request
    body = _request(p.base, 'GET', p.path)[2].decode()
    assert '恢复策略' in body and 'max_attempts 限制（默认 2）' in body
    assert checkpoint(p)['loop_authorizations'][identity]['config']['effective']['progression']['recover_failed_turns'] is True
    p.runtime.scheduler_bindings.observe_progression(instance_id=p.instance, expected_host=None,
        changes=dict(recovery=dict(used=2, consecutive_failures=0, by_kind={'observation':2}, last_failure={'kind':'observation'})))
    ui_configure(p, max_recoveries=7, recover_failed_turns=False)
    assert p.root.call_tool('progression_status', {})['budget']['recovery']['remaining'] == 2
    assert authorize(p) == 303
    old = historical_checkpoint(p)['loop_authorizations'][identity]['budget_snapshot']['recovery']
    assert old['used'] == 2 and old['by_kind'] == {'observation':2} and old['last_failure']['kind'] == 'observation'
    assert checkpoint(p)['recovery'] == {} and old['failed_turns_enabled'] is True


def test_schema8_state_and_archive_cannot_gain_unconfirmed_recovery_policy(loop_ui):
    from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService
    from scidiscovery.artifact_agent.service.instance_archive_records import schema, execution_settings_restore_view
    p = loop_ui
    with p.runtime.scheduler_bindings._connect() as db:
        db.execute('PRAGMA user_version=8')
        archived_schema = schema(db)
    with pytest.raises(Exception, match='incompatible scheduler control schema'):
        SchedulerBindingService(p.runtime.scheduler_bindings.database_path)
    with pytest.raises(Exception, match='unsupported scheduler control schema'):
        execution_settings_restore_view(dict(schema=archived_schema, tables={}))


@pytest.mark.parametrize('stage', ['initialize', 'thread/start'])
def test_production_factory_marks_creation_window_unknown(progression, monkeypatch, stage):
    from scidiscovery.platforms import codex_progression
    p = progression
    directory = p.runtime.project_root / '.codex'
    directory.mkdir(exist_ok=True)
    socket_path = str(p.runtime.state_root / 'fixture.socket')
    (directory / 'config.toml').write_text('[mcp_servers.scidiscovery]\nargs = ['+json.dumps(socket_path)+']\n')
    calls = []
    class NativeHost:
        def __init__(self, connection, log, permissions):
            self.log = log
        def initialize(self, **_):
            if stage == 'initialize':
                raise HostError('rpc_timeout', method=stage)
        def open_root(self, **_):
            calls.append('thread/start')
            raise HostError('rpc_timeout', method=stage)
        def guard_resources(self):
            pass
        def set_execution_deadline(self, _):
            pass
        def close(self):
            self.log.close()
    monkeypatch.setattr(codex_progression, 'CodexProgressionHost', NativeHost)
    monkeypatch.setattr(codex_progression.AppServer, 'launch', lambda *_, **__:SimpleNamespace())
    p.coordinator.host_factory = codex_progression.CodexProgressionFactory(project_root=p.runtime.project_root,
        state_root=p.runtime.state_root, socket_path=socket_path, approval_base_url='http://127.0.0.1:8765',
        command=['fixture'], catalog=p.catalog)
    with pytest.raises(HostError, match='rpc_timeout'):
        p.coordinator.tick()
    assert checkpoint(p)['fault_class'] == ('outcome_unknown' if stage == 'thread/start' else 'configuration_or_runtime')
    assert checkpoint(p)['recovery'].get('used', 0) == 0
    p.coordinator.tick()
    assert calls == (['thread/start'] if stage == 'thread/start' else [])


def test_real_app_server_pipe_failed_and_late_terminal_do_not_recharge(progression):
    p = progression
    configure(p, recover_failed_turns=True, poll_seconds=1)
    notify_read, notify_write = os.pipe()
    request_read, request_write = os.pipe()
    child = SimpleNamespace(stdin=os.fdopen(request_write, 'wb', buffering=0), stdout=os.fdopen(notify_read, 'rb', buffering=0),
        poll=lambda:0, wait=lambda **_:0)
    class PipeHost(Host):
        poll = CodexRootHost.poll
        def __init__(self, record, event):
            super().__init__(record, event)
            self._sink, self._starting = event, False
            self.terminal_transport_error = None
            self.connection = AppServer(child, limits=HostLimits(), on_event=lambda message:CodexRootHost._event(self, message))
        def close(self):
            super().close()
            self.connection.close()
    p.coordinator.host_factory = PipeHost
    try:
        p.coordinator.tick()
        host = p.coordinator.host
        original = host.turn_id
        def emit(turn, status, thread=None):
            os.write(notify_write, (json.dumps(dict(method='turn/completed', params=dict(threadId=thread or host.identity.thread_id,
                turn=dict(id=turn, status=status))))+'\n').encode())
        emit(original, 'failed')
        p.coordinator.tick()
        assert checkpoint(p)['recovery']['used'] == 1 and len(host.prompts) == 1
        emit(original, 'failed')
        ready(p)
        p.coordinator.tick()
        assert len(host.prompts) == 2 and checkpoint(p)['recovery']['used'] == 1
        emit(original, 'failed')
        emit(host.turn_id, 'completed', thread='foreign')
        p.coordinator.tick()
        assert host.completion is None and checkpoint(p)['phase'] == 'running'
        emit(host.turn_id, 'completed')
        p.coordinator.tick()
        assert checkpoint(p)['recovery']['consecutive_failures'] == 0
    finally:
        p.coordinator.close()
        os.close(notify_write)
        os.close(request_read)


def test_failed_root_next_decision_preserves_submitted_remote_effect(tmp_path):
    from copy import copy
    from tests.operations.test_r4_execution_approval_identity import _setup, _create_effect, _decide_execution_approval
    from tests.operations.research_loop_fixtures import authorize_loop
    runtime, instance, adapter, facade, root, _ = _setup(tmp_path)
    bindings, now, session = runtime.scheduler_bindings, [1000.0], 'sch_'+'a'*32
    settings = bindings.global_settings
    bindings.global_settings = settings.model_copy(update=dict(progression=settings.progression.model_copy(
        update=dict(recover_failed_turns=True, poll_seconds=1))))
    bindings.progression_clock = lambda:now[0]
    bindings.bind_session(session_key=session, instance_id=instance.instance_id)
    facade.session_key = session
    root.call_tool('artifact_ingest_text', dict(name='goal', text='Keep the accepted external effect and decide from its authoritative status.'))
    root.call_tool('progression_command', dict(command='pause'))
    authorize_loop(runtime, instance.instance_id, session, 'goal')
    root.call_tool('progression_command', dict(command='resume'))
    _create_effect(root, name='original-effect')
    _decide_execution_approval(runtime, root, name='original-effect')
    original = root.call_tool('execution_start', dict(name='original-effect'), surface='execution')
    assert original['state'] == 'submitted' and adapter.submit_count == 1
    execution_id = bindings.resolve(instance=instance.instance_id, namespace='execution', name='original-effect')
    submissions = dict(adapter.submissions)
    root.call_tool('progression_command', dict(command='pause'))
    root.call_tool('progression_command', dict(command='start', mode='background', objective_name='goal'))
    def make_facade(owner):
        value = copy(facade)
        value.session_key = owner
        return value
    coordinator = ProgressionCoordinator(runtime=runtime, host_factory=Host, facade_factory=make_facade, clock=lambda:now[0])
    p = SimpleNamespace(runtime=runtime, instance=instance.instance_id, coordinator=coordinator, now=now)
    try:
        coordinator.tick()
        host = coordinator.host
        failed(p)
        coordinator.tick()
        ready(p)
        coordinator.tick()
        assert len(host.prompts) == 2 and checkpoint(p)['recovery']['used'] == 1
        assert adapter.submit_count == 1 and adapter.submissions == submissions
        recovered = type(root)(make_facade(host.scheduler_session))
        current = recovered.call_tool('execution_status', dict(name='original-effect'), surface='execution')
        assert current['state'] == original['state']
        assert bindings.resolve(instance=instance.instance_id, namespace='execution', name='original-effect') == execution_id
    finally:
        coordinator.close()
