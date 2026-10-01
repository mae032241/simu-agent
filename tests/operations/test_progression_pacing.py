"""Independent pacing, bounded local retries, and unchanged native authority."""
import json
import sqlite3
from types import SimpleNamespace

import pytest

from scidiscovery.agent_execution_settings import ProgressionSettings
from scidiscovery.artifact_agent.service.maintenance import MaintenanceBusy
from scidiscovery.artifact_agent.service.progression import ProgressionFault
from scidiscovery.platforms.codex_app_server import HostError
from scidiscovery.platforms.codex_progression import CodexProgressionHost
from tests.operations.test_progression import progression, row, checkpoint


@pytest.mark.parametrize('waiting', [False, True])
def test_one_minute_ticks_bound_writes_and_samples_without_model_wake(progression, monkeypatch, waiting):
    p = progression
    p.coordinator.tick()
    host = p.coordinator.host
    monkeypatch.setattr('scidiscovery.platforms.codex_progression.time.monotonic', lambda: p.now[0])
    samples = []
    host.resources = SimpleNamespace(sample=lambda: samples.append(p.now[0]) or
        dict(owned_tree_rss_bytes=100, control_daemon_rss_bytes=0))
    if waiting:
        host.finish()
    p.coordinator.tick()
    writes = []
    original = p.runtime.scheduler_bindings.observe_progression
    def observe(**kwargs):
        writes.append(kwargs['changes'])
        return original(**kwargs)
    monkeypatch.setattr(p.runtime.scheduler_bindings, 'observe_progression', observe)
    start = p.now[0]
    for tick in range(1, 301):
        p.now[0] = start + tick / 5
        p.coordinator.tick()
    budget_writes = sum('budget' in value for value in writes)
    assert budget_writes <= 3
    assert len(writes) <= (15 if waiting else 3)
    assert len(samples) <= 61
    assert len(host.prompts) == 1 and row(p)['state'] == 'active'
    assert checkpoint(p)['budget']['elapsed_seconds'] >= 30


def test_identical_observation_does_not_update_sqlite_or_repeat_notice(progression, monkeypatch):
    p = progression
    p.coordinator.tick()
    p.coordinator._save(dict(runtime_status='waiting'))
    updates = []
    bindings = p.runtime.scheduler_bindings
    connect = bindings._connect
    def traced():
        db = connect()
        db.set_trace_callback(lambda sql: updates.append(sql) if sql.startswith('UPDATE scheduler_progression') else None)
        return db
    monkeypatch.setattr(bindings, '_connect', traced)
    for _ in range(5):
        p.coordinator._save(dict(runtime_status='waiting'))
    assert updates == []


@pytest.mark.parametrize('stop', ['time', 'tokens', 'resource', 'pause'])
def test_slow_display_never_delays_safety_or_control(progression, stop):
    p = progression
    p.coordinator.tick()
    host = p.coordinator.host
    p.coordinator.tick()
    limits = json.loads(row(p)['config_json'])['effective']['progression']
    p.coordinator._limits['budget_snapshot_seconds'] = 300
    if stop == 'time':
        p.now[0] += limits['max_elapsed_seconds']
    elif stop == 'tokens':
        host.event(dict(method='thread/tokenUsage/updated', params=dict(threadId=host.identity.thread_id,
            tokenUsage=dict(total=dict(inputTokens=limits['max_tokens'], cachedInputTokens=0, outputTokens=0)))))
    elif stop == 'resource':
        killed = []
        host.resources = SimpleNamespace(sample=lambda: dict(owned_tree_rss_bytes=limits['max_rss_bytes'],
            control_daemon_rss_bytes=0), terminate=lambda: killed.append(True))
    else:
        p.root.call_tool('progression_command', dict(command='pause'))
    p.coordinator.tick()
    assert row(p)['state'] == 'paused'
    assert len(host.prompts) == 1
    if stop == 'pause':
        assert host.interrupted
    elif stop == 'resource':
        assert killed and row(p)['reason'] == 'resource_limit'
    else:
        assert row(p)['reason'] == 'budget_exhausted'


def busy():
    error = sqlite3.OperationalError('busy')
    error.sqlite_errorcode = sqlite3.SQLITE_BUSY
    return error


@pytest.mark.parametrize('error', [busy(), MaintenanceBusy('maintenance')])
def test_local_read_and_atomic_observation_retry_keep_host_and_turn(progression, monkeypatch, error):
    p = progression
    p.coordinator.tick()
    host = p.coordinator.host
    p.coordinator._limits['observation_backoff_seconds'] = .001
    bindings = p.runtime.scheduler_bindings
    original = bindings.progression_status
    attempts = []
    def read(**kwargs):
        attempts.append(1)
        if len(attempts) < 3:
            raise error
        return original(**kwargs)
    monkeypatch.setattr(bindings, 'progression_status', read)
    p.coordinator.tick()
    assert len(attempts) >= 3 and p.coordinator.host is host and not host.closed
    save = bindings.observe_progression
    writes = []
    def observe(**kwargs):
        writes.append(1)
        if len(writes) == 1:
            raise error
        return save(**kwargs)
    monkeypatch.setattr(bindings, 'observe_progression', observe)
    host.event(dict(method='thread/tokenUsage/updated', params=dict(threadId=host.identity.thread_id,
        tokenUsage=dict(total=dict(inputTokens=77, cachedInputTokens=0, outputTokens=2)))))
    assert len(writes) == 2 and checkpoint(p)['usage_records'][host.identity.thread_id]['counted_tokens']['input_tokens'] == 77
    assert len(host.prompts) == 1 and checkpoint(p)['attempts'] == 0


def test_retries_are_bounded_and_other_sql_errors_are_not_retried(progression):
    p = progression
    p.coordinator._limits.update(observation_retries=2, observation_backoff_seconds=.001)
    calls = []
    def locked():
        calls.append(1)
        raise busy()
    with pytest.raises(ProgressionFault, match='observation_retry_exhausted'):
        p.coordinator._observation(locked)
    assert len(calls) == 3
    calls.clear()
    def invalid():
        calls.append(1)
        raise sqlite3.OperationalError('no such table')
    with pytest.raises(sqlite3.OperationalError):
        p.coordinator._observation(invalid)
    assert len(calls) == 1


def test_submission_error_is_never_replayed_even_if_it_looks_retryable(progression):
    p = progression
    p.coordinator.tick()
    host = p.coordinator.host
    host.finish()
    p.root.call_tool('progression_message', dict(name='new-question', text='Retain limitations.'))
    p.now[0] += 6
    submissions = []
    def submit(_):
        submissions.append(1)
        raise busy()
    host.start_turn = submit
    with pytest.raises(sqlite3.OperationalError):
        p.coordinator.tick()
    assert checkpoint(p)['fault_class'] == 'outcome_unknown'
    assert checkpoint(p)['phase'] == 'prepared' and row(p)['host_json']
    p.coordinator.tick()
    assert submissions == [1] and host.closed


def test_persistent_store_failure_records_fault_before_any_reconnect(progression, monkeypatch):
    p = progression
    from tests.operations.test_progress_assist import configure
    configure(p, max_recoveries=0)
    p.coordinator.tick()
    host = p.coordinator.host
    p.coordinator._limits.update(observation_retries=0)
    bindings = p.runtime.scheduler_bindings
    with monkeypatch.context() as blocked:
        def unavailable(**kwargs):
            raise busy()
        blocked.setattr(bindings, 'progression_status', unavailable)
        blocked.setattr(bindings, 'observe_progression', unavailable)
        with pytest.raises(ProgressionFault, match='observation_retry_exhausted'):
            p.coordinator.tick()
        assert p.coordinator._pending_fault is not None
        assert p.coordinator.host is None and host.closed
        with pytest.raises(ProgressionFault, match='observation_retry_exhausted'):
            p.coordinator.tick()
        assert len(host.prompts) == 1
    p.coordinator.tick()
    assert p.coordinator._pending_fault is None
    assert row(p)['state'] == 'paused'
    assert checkpoint(p)['fault_class'] == 'observation_exhausted'
    assert row(p)['host_json'] and p.coordinator.host is None


def test_local_retry_obeys_goal_deadline(progression):
    p = progression
    p.coordinator._goal_deadline = p.now[0]
    calls = []
    def locked():
        calls.append(1)
        raise busy()
    with pytest.raises(ProgressionFault, match='observation_budget_expired'):
        p.coordinator._observation(locked)
    assert calls == [1]


def test_rpc_resource_guard_and_budget_share_one_sample(monkeypatch):
    import scidiscovery.platforms.codex_progression as module
    clock, samples = [0.], []
    host = CodexProgressionHost.__new__(CodexProgressionHost)
    host.resource_limit = 100
    host.resource_sample_seconds = 1.
    host._sample_at, host._resource_sample = 0, None
    killed = []
    host.resources = SimpleNamespace(sample=lambda: samples.append(clock[0]) or
        dict(owned_tree_rss_bytes=50 if clock[0] < 1 else 101, control_daemon_rss_bytes=0),
        terminate=lambda: killed.append(True))
    monkeypatch.setattr(module.time, 'monotonic', lambda: clock[0])
    for _ in range(20):
        host.guard_resources()
        host.sample_resources()
    assert samples == [0.]
    clock[0] = 1.
    with pytest.raises(HostError, match='resource_limit'):
        host.guard_resources()
    assert samples == [0., 1.] and killed == [True]


@pytest.mark.parametrize('field,value', [('event_wait_seconds', 2.), ('resource_sample_seconds', 0.),
    ('budget_snapshot_seconds', float('inf')), ('observation_retries', -1), ('observation_retry_seconds', 6.)])
def test_pacing_configuration_bounds(field, value):
    with pytest.raises(ValueError):
        ProgressionSettings.model_validate({field:value})
