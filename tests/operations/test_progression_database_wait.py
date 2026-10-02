"""Short SQLite contention waits share the existing observation/goal bounds."""
from contextlib import closing
import json
import sqlite3
import threading
import time

import pytest

from scidiscovery.agent_execution_settings import ProgressionSettings, parse_settings
from scidiscovery.artifact_agent.service.progression import ProgressionFault
from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerInstanceConflict
from scidiscovery.artifact_agent.storage.control_io import bounded_control_io, connect_database
from tests.operations.test_progression import progression, row, checkpoint
from tests.operations.test_progression_fault_recovery import start, ready, frozen_loops
from tests.operations.test_local_worker_contracts import _invoke, _worker


def running_worker(p, **limits):
    host = start(p, sqlite_busy_wait_seconds=.1, observation_retry_seconds=.12,
        max_recoveries=1, **limits)
    _invoke(type(p.root)(p.facade(host.scheduler_session)), 'accepted')
    _worker(p.catalog, p.runtime).call_tool('worker_open_assignment', {})
    host.finish()
    p.coordinator.tick()
    assert checkpoint(p)['phase'] == 'idle'
    return host


@pytest.mark.parametrize('release', [True, False])
def test_actual_budget_identity_read_waits_once_or_consumes_frozen_recovery(progression, monkeypatch, release):
    p = progression
    host = running_worker(p)
    before = checkpoint(p)
    native = p.runtime.runs.native_loop_identities
    blocker = sqlite3.connect(p.runtime.runs.database_path, timeout=0, check_same_thread=False)
    calls, timers = [], []
    def identities(**kwargs):
        calls.append(1)
        if not blocker.in_transaction:
            blocker.execute('BEGIN EXCLUSIVE')
            if release:
                timer = threading.Timer(.025, blocker.rollback)
                timers.append(timer)
                timer.start()
        return native(**kwargs)  # Production _check_budget -> _identities -> real SQLite SELECT.
    monkeypatch.setattr(p.runtime.runs, 'native_loop_identities', identities)
    try:
        started = time.monotonic()
        p.coordinator.tick()
        assert time.monotonic()-started < .6
        cp = checkpoint(p)
        assert len(calls) == 1 and cp['attempts'] == before['attempts']
        assert cp['admissions'] == before['admissions'] and frozen_loops(cp) == frozen_loops(before)
        assert cp['budget']['effective_remaining_seconds'] <= before['budget']['effective_remaining_seconds']
        assert len(host.prompts) == 1 and p.coordinator.host is host and not host.closed
        if release:
            assert cp['recovery'].get('used', 0) == 0 and row(p)['state'] == 'active'
        else:
            assert cp['recovery']['used'] == 1 and cp['recovery']['pending_kind'] == 'observation'
            diagnostic = cp['fault_diagnostic']
            assert diagnostic['stage'] == '_identities' and diagnostic['phase'] == 'idle'
            assert diagnostic['sqlite_errorcode'] == sqlite3.SQLITE_BUSY
            blocker.rollback()
            with monkeypatch.context() as unblocked:
                unblocked.setattr(p.runtime.runs, 'native_loop_identities', native)
                p.coordinator.tick()
            assert checkpoint(p)['recovery']['used'] == 1
            ready(p)
            with pytest.raises(ProgressionFault, match='observation_retry_exhausted'):
                p.coordinator.tick()
            assert row(p)['state'] == 'paused' and checkpoint(p)['recovery']['used'] == 1
            assert checkpoint(p)['attempts'] == before['attempts'] and len(host.prompts) == 1
    finally:
        for timer in timers:
            timer.join()
        blocker.rollback()
        blocker.close()
    assert frozen_loops(checkpoint(p)) == frozen_loops(before)
    assert p.runtime.runs.list(instance_id=p.instance)[0].state == 'running'


@pytest.mark.parametrize('stop', ['deadline', 'close'])
def test_actual_budget_identity_wait_obeys_goal_and_close(progression, stop):
    p = progression
    host = running_worker(p)
    current = row(p)
    limits = json.loads(current['config_json'])['effective']['progression']
    timer = None
    if stop == 'deadline':
        p.coordinator.clock = time.monotonic
        p.coordinator._goal_deadline = time.monotonic()+.035
    else:
        timer = threading.Timer(.035, p.coordinator.closed.set)
    with closing(sqlite3.connect(p.runtime.runs.database_path, timeout=0)) as blocker:
        blocker.execute('BEGIN EXCLUSIVE')
        if timer:
            timer.start()
        try:
            started = time.monotonic()
            with pytest.raises(ProgressionFault, match='observation_budget_expired' if stop == 'deadline' else 'coordinator_closed'):
                p.coordinator._check_budget(current, limits)
            assert time.monotonic()-started < .25
            assert len(host.prompts) == 1
        finally:
            if timer:
                timer.join()


def test_nested_observation_and_same_thread_lock_cannot_extend_outer_deadline(progression):
    p = progression
    p.coordinator.tick()
    p.coordinator._limits.update(observation_retry_seconds=.045, observation_retries=100,
        observation_backoff_seconds=.01)
    with closing(sqlite3.connect(p.runtime.runs.database_path, timeout=0)) as blocker:
        blocker.execute('BEGIN EXCLUSIVE')  # Another connection owned by this same thread cannot release during a wait.
        def nested():
            p.coordinator._limits['observation_retry_seconds'] = .5
            return p.coordinator._observation(lambda: p.runtime.runs.active_ids(instance_id=p.instance))
        started = time.monotonic()
        with pytest.raises(ProgressionFault, match='observation_retry_exhausted'):
            p.coordinator._observation(nested)
        assert time.monotonic()-started < .2
        assert blocker.in_transaction
        blocker.rollback()
    assert row(p)['state'] == 'active' and checkpoint(p)['attempts'] == 0


@pytest.mark.parametrize('command', ['pause', 'stop'])
def test_user_control_during_identity_wait_prevents_another_native_turn(progression, monkeypatch, command):
    p = progression
    host = running_worker(p)
    before = checkpoint(p)
    native = p.runtime.runs.native_loop_identities
    blocker = sqlite3.connect(p.runtime.runs.database_path, timeout=0, check_same_thread=False)
    timers, errors = [], []
    def control():
        try:
            p.root.call_tool('progression_command', dict(command=command))
        except Exception as error:
            errors.append(error)
    def identities(**kwargs):
        blocker.execute('BEGIN EXCLUSIVE')
        timers.extend([threading.Timer(.02, control), threading.Timer(.06, blocker.rollback)])
        for timer in timers:
            timer.start()
        return native(**kwargs)
    monkeypatch.setattr(p.runtime.runs, 'native_loop_identities', identities)
    try:
        p.coordinator.tick()
    finally:
        for timer in timers:
            timer.join()
        blocker.rollback()
        blocker.close()
    assert not errors and row(p)['state'] == ('paused' if command == 'pause' else 'stopped')
    assert row(p)['reason'] == ('user_paused' if command == 'pause' else 'user_stopped')
    assert len(host.prompts) == 1 and checkpoint(p)['recovery'].get('used', 0) == 0
    assert checkpoint(p)['admissions'] == before['admissions'] and frozen_loops(checkpoint(p)) == frozen_loops(before)


@pytest.mark.parametrize('entry', ['execute', 'cursor', 'commit', 'exit'])
def test_each_sql_entry_refreshes_deadline_and_failed_commit_rolls_back(tmp_path, entry):
    path = tmp_path/'wait.sqlite3'
    with sqlite3.connect(path) as setup:
        setup.execute('CREATE TABLE sample(value INTEGER)')
        setup.execute('INSERT INTO sample VALUES(0)')
    with closing(sqlite3.connect(path, timeout=0)) as blocker:
        blocker.execute('BEGIN' if entry in {'commit', 'exit'} else 'BEGIN EXCLUSIVE')
        if entry in {'commit', 'exit'}:
            blocker.execute('SELECT * FROM sample').fetchall()
        deadline = time.monotonic()+.08
        with bounded_control_io(wait_seconds=lambda: .5, remaining_seconds=lambda: 1.):
            with closing(connect_database(path, timeout=30, deadline_monotonic=deadline)) as db:
                if entry in {'commit', 'exit'}:
                    db.execute('INSERT INTO sample VALUES(1)')
                time.sleep(.06)  # A connection/earlier statement cannot retain its original wait allowance.
                started = time.monotonic()
                with pytest.raises(sqlite3.OperationalError) as failure:
                    if entry == 'execute':
                        db.execute('SELECT * FROM sample').fetchall()
                    elif entry == 'cursor':
                        db.cursor().execute('SELECT * FROM sample').fetchall()
                    elif entry == 'commit':
                        db.commit()
                    else:
                        db.__exit__(None, None, None)
                assert failure.value.sqlite_errorcode == sqlite3.SQLITE_BUSY
                assert time.monotonic()-started < .055
                if entry == 'exit':
                    assert not db.in_transaction  # SQLite's native __exit__ rolled the failed commit back.
                db.rollback()  # Expiry never prevents necessary cleanup.
        blocker.rollback()
    with sqlite3.connect(path) as verify:
        assert verify.execute('SELECT * FROM sample').fetchall() == [(0,)]


@pytest.mark.parametrize('value', [-.001, 1.001, float('inf'), float('nan')])
def test_administrator_sqlite_wait_has_finite_bounds(value):
    with pytest.raises(ValueError):
        ProgressionSettings(sqlite_busy_wait_seconds=value)


@pytest.mark.parametrize('drift', ['sqlite_busy_wait_seconds', 'max_tokens'])
def test_missing_new_default_is_compatible_without_changing_frozen_config(progression, drift):
    p = progression
    bindings = p.runtime.scheduler_bindings
    config = json.loads(row(p)['config_json'])
    assert config['effective']['progression'].pop('sqlite_busy_wait_seconds') == .1
    legacy = json.dumps(config)
    with bindings._connect() as db:
        db.execute('UPDATE scheduler_progression SET config_json=? WHERE instance_id=?', (legacy, p.instance))
    p.coordinator.tick()  # Real activation and scheduling guard both compare the legacy frozen config.
    assert p.coordinator._limits['sqlite_busy_wait_seconds'] == .1
    assert row(p)['config_json'] == legacy and len(p.coordinator.host.prompts) == 1
    bindings.global_settings = parse_settings({'progression': {drift: .2 if drift == 'sqlite_busy_wait_seconds' else 2000001}})
    with pytest.raises(SchedulerInstanceConflict, match='Configuration changed'):
        with bindings.scheduling_guard(instance_id=p.instance, session_key=p.coordinator.host.scheduler_session):
            pass
    assert row(p)['config_json'] == legacy
