"""Real process-held locks must not hide coordinator observation deadlines."""
from contextlib import contextmanager
import select
import subprocess
import sys
import threading
import time

import pytest

from scidiscovery.artifact_agent.service.progression import ProgressionFault
from scidiscovery.platforms.codex_app_server import HostError
from tests.operations.test_progression import progression, row, checkpoint

pytestmark = pytest.mark.process_e2e

HOLDER = '''
import fcntl, os, sqlite3, sys
kind, path = sys.argv[1:]
if kind == 'db':
    connection = sqlite3.connect(path, timeout=0)
    connection.execute('BEGIN EXCLUSIVE')
else:
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(descriptor, fcntl.LOCK_EX)
print('held', flush=True)
sys.stdin.read()
'''


@pytest.fixture(autouse=True)
def approval_store(progression, tmp_path):
    # The source-only Worker fixture omits approvals; use the real service store.
    from scidiscovery.artifact_agent.schema.refs import ActorRef
    from scidiscovery.artifact_agent.service.approvals import ApprovalService
    progression.approvals = ApprovalService(artifacts=progression.runtime.artifacts,
        database_path=tmp_path / 'approvals.sqlite3',
        service_actor=ActorRef(actor_type='service', actor_id='lock-test'), receipt_secret=b'x' * 32)


@contextmanager
def held_lock(p, kind):
    bindings = p.runtime.scheduler_bindings
    maintenance = bindings.control_maintenance
    paths = {
        'db': bindings.database_path,
        'runs_db': p.runtime.runs.database_path,
        'artifacts_db': p.runtime.artifacts.registry.database_path,
        'approvals_db': p.approvals.database_path,
        'global': maintenance.maintenance.path,
        'instance': maintenance._lock_path(p.instance),
        'scheduling': bindings.database_path.with_suffix('.scheduling.lock'),
    }
    child = subprocess.Popen([sys.executable, '-c', HOLDER,
        'db' if kind.endswith('db') else 'lock', str(paths[kind])],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert select.select([child.stdout], [], [], 3)[0], 'lock holder did not start'
        assert child.stdout.readline().strip() == 'held'
        yield
    finally:
        child.communicate(timeout=3)
        assert child.returncode == 0


def observation(p, kind):
    if kind == 'runs_db':
        return lambda: p.coordinator._observation(lambda: p.runtime.runs.active_ids(instance_id=p.instance))
    if kind == 'artifacts_db':
        from scidiscovery.artifact_agent.schema.refs import ArtifactRef
        ref = ArtifactRef.model_validate_json(row(p)['objective_ref_json'])
        return lambda: p.coordinator._observation(lambda: p.runtime.artifacts.catalog(ref))
    if kind == 'approvals_db':
        # The same connection factory used by the approval_status snapshot.
        def read():
            with p.approvals._connect() as db:
                return db.execute('SELECT count(*) FROM sqlite_master').fetchone()
        return lambda: p.coordinator._observation(read)
    return lambda: p.coordinator._save(dict(runtime_status='observed'))


@pytest.mark.parametrize('kind', ['db', 'global', 'instance', 'scheduling', 'runs_db', 'artifacts_db', 'approvals_db'])
@pytest.mark.parametrize('stop', ['retry', 'deadline', 'resource', 'close'])
def test_real_lock_waits_obey_retry_deadline_resource_and_close(progression, kind, stop):
    p = progression
    p.coordinator.tick()
    coordinator, host = p.coordinator, p.coordinator.host
    operation = observation(p, kind)
    coordinator._limits.update(observation_retries=100, observation_retry_seconds=.12,
        observation_backoff_seconds=.01)
    code, error = 'observation_retry_exhausted', ProgressionFault
    samples = []
    host.guard_resources = lambda: samples.append(time.monotonic())
    timer = None
    if stop == 'deadline':
        coordinator.clock = time.monotonic
        coordinator._goal_deadline = time.monotonic() + .04
        code = 'observation_budget_expired'
    elif stop == 'resource':
        def guard():
            samples.append(time.monotonic())
            raise HostError('resource_limit')
        host.guard_resources = guard
        code, error = 'resource_limit', HostError
    elif stop == 'close':
        timer = threading.Timer(.04, coordinator.closed.set)
        code = 'coordinator_closed'
    with held_lock(p, kind):
        started = time.monotonic()
        if timer:
            timer.start()
        try:
            with pytest.raises(error, match=code):
                operation()
            assert time.monotonic() - started < .5
            assert len(host.prompts) == 1
            if stop != 'deadline':
                assert samples
        finally:
            if timer:
                timer.join()


@pytest.mark.parametrize('kind', ['db', 'global', 'instance', 'scheduling'])
def test_real_lock_fault_write_remains_pending_until_release(progression, kind):
    p = progression
    p.coordinator.tick()
    coordinator, host = p.coordinator, p.coordinator.host
    coordinator._limits.update(observation_retries=1, observation_retry_seconds=.08,
        observation_backoff_seconds=.01)
    # A periodic budget observation forces the actual write path on this tick.
    coordinator._budget_saved_at = None
    with held_lock(p, kind):
        started = time.monotonic()
        with pytest.raises(ProgressionFault, match='observation_retry_exhausted'):
            coordinator.tick()
        assert time.monotonic() - started < .5
        pending = coordinator._pending_fault.copy()
        assert coordinator.host is None and host.closed
        with pytest.raises(ProgressionFault, match='observation_retry_exhausted'):
            coordinator.tick()
        assert coordinator._pending_fault == pending
        coordinator._goal_deadline = coordinator.clock()
        started = time.monotonic()
        with pytest.raises(ProgressionFault, match='observation_budget_expired'):
            coordinator.tick()
        assert time.monotonic() - started < .1
        assert coordinator._pending_fault == pending
        assert len(host.prompts) == 1
    coordinator.tick()
    assert coordinator._pending_fault is None
    assert row(p)['state'] == 'paused' and row(p)['host_json']
    assert checkpoint(p)['fault_class'] == 'observation_exhausted'
    assert coordinator.host is None


@pytest.mark.parametrize('kind', ['db', 'global', 'instance', 'scheduling'])
def test_close_joins_coordinator_while_another_process_holds_lock(progression, kind):
    p = progression
    p.coordinator.tick()
    coordinator, host = p.coordinator, p.coordinator.host
    coordinator._budget_saved_at = None
    entered = threading.Event()
    host.guard_resources = entered.set
    with held_lock(p, kind):
        coordinator.start()
        assert entered.wait(1)
        started = time.monotonic()
        coordinator.close()
        assert time.monotonic() - started < .5
        assert not coordinator.thread.is_alive()
        assert coordinator.lease is None and host.closed
        assert coordinator._pending_fault is not None
