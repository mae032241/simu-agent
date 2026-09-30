"""Background authority, coalescing, scientific projections and durable limits."""
import json
from types import SimpleNamespace

import pytest

from scidiscovery.artifact_agent.service.progression import ProgressionCoordinator
from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerInstanceConflict
from scidiscovery.agent_execution_settings import parse_settings
from tests.operations.test_local_worker_contracts import _system, _invoke, _worker, _write_result


class Host:
    def __init__(self, row, event):
        self.identity = SimpleNamespace(thread_id='native-root', session_id='native-root')
        self.scheduler_session = 'sch_'+'b'*32
        self.turn_id = json.loads(row['checkpoint_json']).get('turn_id')
        self.completion = None
        self.event = event
        self.prompts = []
        self.interrupted = False
        self.closed = False
        self.restored = []
    def start_turn(self, prompt):
        self.completion = None
        self.prompts.append(prompt)
        self.turn_id = 'turn-'+str(len(self.prompts))
        self.event(dict(method='turn/started', params=dict(threadId=self.identity.thread_id, turn=dict(id=self.turn_id))))
        return self.turn_id
    def poll(self, timeout=0):
        return self.completion
    def finish(self):
        self.completion = dict(id=self.turn_id, status='completed')
        self.event(dict(method='turn/completed', params=dict(threadId=self.identity.thread_id, turn=self.completion)))
    def interrupt(self):
        self.interrupted = True
    def close(self):
        self.closed = True
    def restore_worker(self, *args, **kwargs):
        self.restored.append(args)


@pytest.fixture
def progression(tmp_path):
    catalog, runtime, instance, root = _system(tmp_path)
    bindings = runtime.scheduler_bindings
    user = 'sch_'+'a'*32
    bindings.bind_session(session_key=user, instance_id=instance.instance_id)
    root.facade.session_key = user
    root.call_tool('artifact_ingest_text', dict(name='goal', text='Compare exact data and retain limitations.', on_conflict='reject'))
    root.call_tool('progression_command', dict(command='pause'))
    root.call_tool('progression_command', dict(command='start', mode='background', objective_name='goal'))
    def facade(session):
        from copy import copy
        value = copy(root.facade)
        value.session_key = session
        return value
    now = [1000.0]
    coordinator = ProgressionCoordinator(runtime=runtime, host_factory=Host, facade_factory=facade, clock=lambda: now[0])
    yield SimpleNamespace(catalog=catalog, runtime=runtime, instance=instance.instance_id,
        root=root, coordinator=coordinator, now=now, user=user, facade=facade)
    coordinator.close()


def row(p):
    return p.runtime.scheduler_bindings.progression_status(instance_id=p.instance, internal=True)


def checkpoint(p):
    return json.loads(row(p)['checkpoint_json'])


def test_two_decisions_use_sealed_result_and_no_stage_or_idle_wake(progression):
    p = progression
    p.coordinator.tick()
    host = p.coordinator.host
    assert len(host.prompts) == 1
    assert 'Compare exact data' in host.prompts[0]
    brief = json.loads(host.prompts[0].split('\n')[-1])
    assert brief['objective']['kind'] == 'source_text'
    assert brief['objective']['schema'] == 'opaque'
    assert 'Do not ask permission' in host.prompts[0]
    root = p.root.__class__(p.facade(host.scheduler_session))
    _invoke(root, 'first')
    worker = _worker(p.catalog, p.runtime)
    worker.call_tool('worker_open_assignment', {})
    host.finish()
    p.coordinator.tick()
    for _ in range(3):
        p.now[0] += 6
        p.coordinator.tick()
    assert len(host.prompts) == 1  # running/heartbeat/stages do not request decisions
    _write_result(worker)
    worker.call_tool('worker_submit_result', {})
    p.now[0] += 6
    p.coordinator.tick()
    assert len(host.prompts) == 2
    assert 'selected_output' in host.prompts[1]
    assert 'first.output' in host.prompts[1]
    assert row(p)['state'] == 'active'  # one sealed Run does not complete the goal
    _invoke(root, 'second')
    assert len(p.runtime.runs.list(instance_id=p.instance)) == 2


def test_serial_admission_does_not_block_worker_result(progression):
    p = progression
    p.coordinator.tick()
    root = p.root.__class__(p.facade(p.coordinator.host.scheduler_session))
    _invoke(root, 'first')
    with pytest.raises(Exception, match='operation_busy'):
        _invoke(root, 'second')
    worker = _worker(p.catalog, p.runtime)
    worker.call_tool('worker_open_assignment', {})
    p.root.call_tool('progression_command', dict(command='pause'))
    p.coordinator.tick()
    assert p.coordinator.host.interrupted
    with pytest.raises(SchedulerInstanceConflict):
        _invoke(root, 'late')
    _write_result(worker)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'


def test_reader_message_is_original_and_wakes_at_safe_boundary(progression):
    p = progression
    p.coordinator.tick()
    host = p.coordinator.host
    value = p.root.call_tool('progression_message', dict(name='scope.clarification', text='Also retain negative results.'))
    assert value['application'] == 'next_safe_turn'
    assert p.root.call_tool('progression_message', dict(name='scope.clarification', text='Also retain negative results.'))['state'] == 'saved'
    with pytest.raises(SchedulerInstanceConflict):
        p.root.call_tool('progression_message', dict(name='scope.clarification', text='Changed.'))
    assert len(host.prompts) == 1
    host.finish()
    p.now[0] += 6
    p.coordinator.tick()
    assert len(host.prompts) == 2
    assert 'Also retain negative results.' in host.prompts[-1]
    ref = checkpoint(p)['messages'][0]['artifact_ref']
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    assert p.runtime.artifacts.read(ArtifactRef.model_validate(ref)) == b'Also retain negative results.'


def test_lost_native_start_is_not_replayed(progression):
    p = progression
    p.coordinator.tick()
    host = p.coordinator.host
    p.coordinator._save(dict(phase='prepared', turn_id=None))
    host.close()
    p.coordinator.host = None
    p.coordinator.tick()
    assert row(p)['reason'] == 'submission_unknown'
    assert row(p)['state'] == 'paused'
    assert row(p)['host_json'] is not None
    p.coordinator.tick()
    assert p.coordinator.host is None


def test_restart_restores_same_turn_and_consumption(progression):
    p = progression
    p.coordinator.tick()
    old = p.coordinator.host
    rounds = checkpoint(p)['rounds']
    old.close()
    p.coordinator.host = None
    p.coordinator.tick()
    assert p.coordinator.host.turn_id == old.turn_id
    assert not p.coordinator.host.prompts
    assert checkpoint(p)['rounds'] == rounds
    assert row(p)['owner_session'] == old.scheduler_session


def restore_terminal_host(p, status):
    old = p.coordinator.host
    old.close()
    p.coordinator.host = None
    def factory(record, event):
        host = Host(record, event)
        host.completion = dict(id=host.turn_id, status=status)
        return host
    p.coordinator.host_factory = factory
    p.now[0] += 6


@pytest.mark.parametrize('delayed_terminal', [False, True])
def test_restart_interrupted_root_reconciles_existing_work_without_reset(progression, delayed_terminal):
    p = progression
    p.coordinator.tick()
    host = p.coordinator.host
    root = p.root.__class__(p.facade(host.scheduler_session))
    _invoke(root, 'accepted')
    before = checkpoint(p)
    old_turn = host.turn_id
    restore_terminal_host(p, 'interrupted')
    if delayed_terminal:
        p.coordinator.host_factory = Host
        p.coordinator.tick()
        assert not p.coordinator.host.prompts
        p.coordinator.host.completion = dict(id=old_turn, status='interrupted')
    p.coordinator.tick()
    after = checkpoint(p)
    assert row(p)['state'] == 'active'
    assert after['attempts'] == before['attempts'] + 1
    assert after['rounds'] == before['rounds'] + 1
    assert after['started_at'] == before['started_at']
    assert after['admissions'] == before['admissions']
    assert after['recovered_interruption'] == old_turn
    assert len(p.runtime.runs.list(instance_id=p.instance)) == 1
    prompt = p.coordinator.host.prompts[-1]
    assert 'accepted' in prompt and 'do not create a replacement' in prompt
    p.coordinator.tick()
    assert checkpoint(p)['attempts'] == after['attempts']
    assert len(p.coordinator.host.prompts) == 1


@pytest.mark.parametrize('reconnect,status', [(True, 'failed'), (False, 'interrupted')])
def test_only_interruption_confirmed_on_reconnect_can_continue(progression, reconnect, status):
    p = progression
    p.coordinator.tick()
    if reconnect:
        restore_terminal_host(p, status)
    else:
        host = p.coordinator.host
        host.completion = dict(id=host.turn_id, status=status)
    p.coordinator.tick()
    assert row(p)['state'] == 'paused'
    assert row(p)['reason'] == 'root_turn_failed'
    assert checkpoint(p)['rounds'] == 1


def test_interruption_recovery_obeys_attempt_budget(progression):
    p = progression
    p.coordinator.tick()
    maximum = json.loads(row(p)['config_json'])['effective']['progression']['max_attempts']
    p.coordinator._save(dict(attempts=maximum-1))
    restore_terminal_host(p, 'interrupted')
    p.coordinator.tick()
    assert row(p)['state'] == 'paused'
    assert row(p)['reason'] == 'budget_exhausted'
    assert checkpoint(p)['attempts'] == maximum
    assert checkpoint(p)['rounds'] == 1
    assert not p.coordinator.host.prompts


def test_interruption_reconnect_does_not_override_user_pause(progression):
    p = progression
    p.coordinator.tick()
    p.root.call_tool('progression_command', dict(command='pause'))
    restore_terminal_host(p, 'interrupted')
    p.coordinator.tick()
    assert row(p)['state'] == 'paused'
    assert checkpoint(p)['rounds'] == 1
    # Paused native writers are not automatically reconnected. Keep the marker
    # until an explicit reconciliation establishes native quiescence.
    assert row(p)['host_json'] is not None
    assert p.coordinator.host is None


def test_pause_terminal_ack_required_and_takeover_blocks_old_writer(progression):
    p = progression
    p.coordinator.tick()
    host = p.coordinator.host
    p.root.call_tool('progression_command', dict(command='takeover'))
    p.coordinator.tick()
    assert row(p)['host_json'] is not None
    assert host.interrupted
    host.finish()
    p.coordinator.tick()
    assert row(p)['host_json'] is None
    assert row(p)['owner_session'] == p.user


def test_usage_reconnect_dedup_and_unknown_worker_coverage(progression):
    p = progression
    p.coordinator.tick()
    host = p.coordinator.host
    event = dict(method='thread/tokenUsage/updated', params=dict(threadId=host.identity.thread_id,
        tokenUsage=dict(total=dict(inputTokens=100, cachedInputTokens=50, outputTokens=20))))
    host.event(event)
    host.event(event)
    assert checkpoint(p)['usage_records'][host.identity.thread_id]['counted_tokens']['input_tokens'] == 100
    root = p.root.__class__(p.facade(host.scheduler_session))
    _invoke(root, 'first')
    run = p.runtime.runs.list(instance_id=p.instance)[0]
    p.runtime.runs.worker_connections.attach(run_id=run.run_id, platform_session='native-root', thread_id='worker')
    limits = json.loads(row(p)['config_json'])['effective']['progression']
    p.coordinator._check_budget(row(p), limits)
    assert checkpoint(p)['budget']['token_coverage'] == 'partial'


def test_time_budget_and_strict_missing_usage_stop_without_reset(progression):
    p = progression
    p.coordinator.tick()
    limits = json.loads(row(p)['config_json'])['effective']['progression']
    strict = dict(limits, token_policy='strict')
    assert not p.coordinator._check_budget(row(p), strict)
    assert row(p)['reason'] == 'budget_exhausted'
    assert checkpoint(p)['rounds'] == 1
    p.root.call_tool('progression_command', dict(command='resume'))
    p.now[0] += limits['max_elapsed_seconds']+1
    assert not p.coordinator._check_budget(row(p), limits)
    assert checkpoint(p)['rounds'] == 1


def test_effective_global_drift_stops_background_but_interactive_edit_is_next_run(progression):
    p = progression
    p.coordinator.tick()
    bindings = p.runtime.scheduler_bindings
    bindings.global_settings = parse_settings({'defaults': {'model': 'changed'}})
    with pytest.raises(SchedulerInstanceConflict, match='Configuration changed'):
        with bindings.scheduling_guard(instance_id=p.instance, session_key=p.coordinator.host.scheduler_session):
            pass
    p.root.call_tool('progression_command', dict(command='takeover'))
    bindings.save_agent_settings(p.instance, {'defaults': {'narrative_language': 'zh-CN'}},
        expected_revision=0, maintenance=bindings.control_maintenance)
    with bindings.scheduling_guard(instance_id=p.instance, session_key=p.user):
        pass


def test_maintenance_blocks_observation_even_after_pause(progression):
    from scidiscovery.artifact_agent.service.instance_maintenance import InstanceMaintenanceUnavailable
    p = progression
    p.coordinator.tick()
    gate = p.runtime.scheduler_bindings.control_maintenance
    with gate.exclusive(p.instance):
        gate.begin(p.instance, 'maintenance', 'archive')
    with pytest.raises(InstanceMaintenanceUnavailable):
        p.coordinator._save(dict(probes=100))
    assert checkpoint(p)['probes'] != 100


def test_run_creation_crash_reconciles_exact_admission_without_recreation(progression, monkeypatch):
    p = progression
    p.coordinator.tick()
    host = p.coordinator.host
    root = p.root.__class__(p.facade(host.scheduler_session))
    def lost_binding(*args, **kwargs):
        raise RuntimeError('simulated crash before semantic binding')
    monkeypatch.setattr(root.facade, '_bind_target', lost_binding)
    with pytest.raises(RuntimeError, match='simulated crash'):
        _invoke(root, 'accepted')
    assert checkpoint(p)['admissions']['accepted']['state'] == 'prepared'
    assert len(p.runtime.runs.list(instance_id=p.instance)) == 1
    host.finish()
    p.coordinator.tick()
    admission = checkpoint(p)['admissions']['accepted']
    assert admission['state'] == 'accepted'
    assert p.runtime.scheduler_bindings.resolve(instance=p.instance, namespace='run', name='accepted') == admission['run_id']
    assert len(p.runtime.runs.list(instance_id=p.instance)) == 1


def test_report_goal_complete_is_explicit_and_message_supersedes_report(progression):
    p = progression
    p.coordinator.tick()
    host = p.coordinator.host
    root = p.root.__class__(p.facade(host.scheduler_session))
    root.call_tool('progression_report', dict(summary='Goal outcome with explicit limitations.', completed=True))
    p.root.call_tool('progression_message', dict(name='new.direction', text='Consider this additional scope.'))
    host.finish()
    p.now[0] += 6
    p.coordinator.tick()
    assert len(host.prompts) == 2
    assert 'Goal outcome with explicit limitations.' in host.prompts[1]
    assert checkpoint(p)['report'] is None
    root.call_tool('progression_report', dict(summary='Additional scope is now answered.', completed=True))
    host.finish()
    p.coordinator.tick()
    assert row(p)['reason'] == 'goal_completed'


def test_task_and_round_limits_are_checked_without_losing_usage(progression):
    p = progression
    p.coordinator.tick()
    host = p.coordinator.host
    root = p.root.__class__(p.facade(host.scheduler_session))
    _invoke(root, 'first')
    worker = _worker(p.catalog, p.runtime)
    worker.call_tool('worker_open_assignment', {})
    _write_result(worker)
    worker.call_tool('worker_submit_result', {})
    settings = p.runtime.scheduler_bindings.control_settings(p.instance)
    settings['effective']['progression']['max_tasks'] = 1
    from unittest.mock import patch
    with p.runtime.scheduler_bindings._connect() as db:
        db.execute('UPDATE scheduler_progression SET config_json=? WHERE instance_id=?',
            (json.dumps(settings), p.instance))
    with patch.object(p.runtime.scheduler_bindings, 'control_settings', return_value=settings):
        with pytest.raises(Exception, match='background_task_budget_exhausted'):
            _invoke(root, 'budget-exhausted')
    limits = json.loads(row(p)['config_json'])['effective']['progression']
    assert not p.coordinator._check_budget(row(p), dict(limits, max_rounds=1))
    assert checkpoint(p)['rounds'] == 1


def test_import_restores_spent_budget_and_never_wakes_runtime(progression):
    from scidiscovery.artifact_agent.service.instance_archive_records import execution_settings_restore_view, schema
    p = progression
    p.coordinator.tick()
    bindings = p.runtime.scheduler_bindings
    with bindings._connect() as db:
        saved = dict(schema=schema(db), tables={'scheduler_progression': [dict(row(p))]})
    imported = execution_settings_restore_view(saved)['tables']['scheduler_progression'][0]
    assert imported['state'] == 'paused' and imported['host_json'] is None
    assert json.loads(imported['checkpoint_json'])['rounds'] == 1
    assert imported['owner_session'] is None


def test_fast_pause_resume_waits_for_native_terminal_and_retains_budget(progression):
    p = progression
    p.coordinator.tick()
    host = p.coordinator.host
    p.root.call_tool('progression_command', dict(command='pause'))
    p.root.call_tool('progression_command', dict(command='resume'))
    p.coordinator.tick()
    assert row(p)['state'] == 'pending' and host.interrupted
    host.finish()
    p.coordinator.tick()
    assert row(p)['state'] == 'active'
    assert row(p)['owner_session'] == host.scheduler_session
    assert checkpoint(p)['rounds'] == 1


def test_instance_selection_and_goal_revision_do_not_reuse_completed_report(progression):
    p = progression
    p.coordinator.tick()
    host = p.coordinator.host
    p.facade(host.scheduler_session).progression_report(summary='Old goal outcome.', completed=True)
    p.root.call_tool('progression_command', dict(command='pause'))
    message = p.root.call_tool('progression_message', dict(name='new.goal', text='A changed objective.'))
    assert message['state'] == 'saved'
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='new.goal'))
    assert checkpoint(p)['report'] is None
    host.finish()
    p.now[0] += 6
    p.coordinator.tick()
    assert row(p)['state'] == 'active' and len(host.prompts) == 2
    assert 'A changed objective.' in host.prompts[-1]


def test_unchanged_failed_request_cannot_evade_attempt_limit_by_new_name(progression):
    p = progression
    p.coordinator.tick()
    root = p.root.__class__(p.facade(p.coordinator.host.scheduler_session))
    _invoke(root, 'failed.task')
    run = p.runtime.runs.list(instance_id=p.instance)[0]
    p.runtime.runs.record_failure(run.run_id, reason='fixture runtime failure', expected_state='queued', expected_last_activity_at=run.last_activity_at)
    with pytest.raises(Exception, match='background_unchanged_task_failed'):
        _invoke(root, 'renamed.retry')
    assert len(p.runtime.runs.list(instance_id=p.instance)) == 1


def test_interrupted_pause_preserves_unprocessed_message_after_release(progression):
    p = progression
    p.coordinator.tick()
    p.coordinator.host.finish()
    p.coordinator.tick()
    processed = checkpoint(p)['processed_snapshot']
    p.root.call_tool('progression_message', dict(name='unprocessed', text='Retain this new direction.'))
    p.now[0] += 6
    p.coordinator.tick()
    interrupted = p.coordinator.host
    p.root.call_tool('progression_command', dict(command='pause'))
    interrupted.completion = dict(id=interrupted.turn_id, status='interrupted')
    p.coordinator.tick()
    assert p.coordinator.host is None and row(p)['host_json'] is None
    assert checkpoint(p)['processed_snapshot'] == processed
    p.root.call_tool('progression_command', dict(command='resume'))
    p.now[0] += 6
    p.coordinator.tick()
    assert 'Retain this new direction.' in p.coordinator.host.prompts[0]
    assert not p.runtime.runs.list(instance_id=p.instance)


def test_interrupted_fast_resume_reconciles_prepared_admission_once(progression, monkeypatch):
    p = progression
    p.coordinator.tick()
    host = p.coordinator.host
    root = p.root.__class__(p.facade(host.scheduler_session))
    def lost_binding(*args, **kwargs):
        raise RuntimeError('binding reply lost')
    monkeypatch.setattr(root.facade, '_bind_target', lost_binding)
    with pytest.raises(RuntimeError, match='binding reply lost'):
        _invoke(root, 'accepted.before.pause')
    p.root.call_tool('progression_command', dict(command='pause'))
    p.root.call_tool('progression_command', dict(command='resume'))
    host.completion = dict(id=host.turn_id, status='interrupted')
    p.now[0] += 6
    p.coordinator.tick()
    assert checkpoint(p)['admissions']['accepted.before.pause']['state'] == 'accepted'
    assert len(p.runtime.runs.list(instance_id=p.instance)) == 1
    assert len(host.prompts) == 2 and 'accepted.before.pause' in host.prompts[-1]
    assert 'do not create a replacement' in host.prompts[-1]


@pytest.mark.parametrize('control', ['pause', 'resume'])
@pytest.mark.parametrize('method', ['interrupt', 'poll'])
def test_control_disconnect_always_closes_failed_host(progression, monkeypatch, control, method):
    from scidiscovery.platforms.codex_app_server import HostError
    p = progression
    p.coordinator.tick()
    host = p.coordinator.host
    original_marker = row(p)['host_json']
    p.root.call_tool('progression_command', dict(command='pause'))
    if control == 'resume':
        p.root.call_tool('progression_command', dict(command='resume'))
    def disconnect(*args):
        raise HostError('app_server_closed')
    monkeypatch.setattr(host, method, disconnect)
    with pytest.raises(HostError, match='app_server_closed'):
        p.coordinator.tick()
    assert host.closed and p.coordinator.host is None
    assert row(p)['host_json'] == original_marker and row(p)['state'] == 'paused'
    assert checkpoint(p)['fault_code'] == 'app_server_closed'
    p.coordinator.tick()
    assert p.coordinator.host is None


def test_control_disconnect_closes_even_when_maintenance_blocks_fault_record(progression, monkeypatch):
    from scidiscovery.platforms.codex_app_server import HostError
    from scidiscovery.artifact_agent.service.instance_maintenance import InstanceMaintenanceUnavailable
    p = progression
    p.coordinator.tick()
    host = p.coordinator.host
    p.root.call_tool('progression_command', dict(command='pause'))
    def disconnect():
        raise HostError('app_server_closed')
    monkeypatch.setattr(host, 'interrupt', disconnect)
    gate = p.runtime.scheduler_bindings.control_maintenance
    with gate.exclusive(p.instance):
        gate.begin(p.instance, 'fault-gate', 'archive')
    with pytest.raises(InstanceMaintenanceUnavailable):
        p.coordinator.tick()
    assert host.closed and p.coordinator.host is None
    assert p.coordinator._pending_fault is not None and row(p)['host_json'] is not None
    with pytest.raises(InstanceMaintenanceUnavailable):
        p.coordinator.tick()
    with gate.exclusive(p.instance):
        gate.finish(p.instance, 'fault-gate')
    p.coordinator.tick()
    assert p.coordinator._pending_fault is None
    assert checkpoint(p)['fault_code'] == 'app_server_closed'
    assert p.coordinator.host is None and row(p)['state'] == 'paused'


@pytest.mark.parametrize('tokens,expected', [(2034572,'budget_exhausted'),(100,'goal_completed')])
def test_goal_completion_accounts_last_native_usage_before_success(progression, tokens, expected):
    p=progression
    p.coordinator.tick()
    host=p.coordinator.host
    root=p.root.__class__(p.facade(host.scheduler_session))
    root.call_tool('progression_report',dict(summary='Conclusions sealed.',completed=True))
    host.event(dict(method='thread/tokenUsage/updated',params=dict(threadId=host.identity.thread_id,
        tokenUsage=dict(total=dict(inputTokens=tokens,cachedInputTokens=0,outputTokens=0)))))
    host.finish()
    p.coordinator.tick()
    assert row(p)['reason']==expected
    assert checkpoint(p)['budget']['observed_tokens']==tokens
    assert checkpoint(p)['report']['completed'] is True
    assert len(host.prompts)==1
