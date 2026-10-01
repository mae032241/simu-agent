"""Human wait time and orphaned exact execution requests, through real services."""
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import pytest

from scidiscovery.artifact_agent.service.approval_waits import parse_time
from scidiscovery.artifact_agent.service.runs import RunService
from tests.operations.test_experiment_approval_handoff import experiment, start, decide as ui_decide
from tests.operations.test_instance_archive import archive_system


def decide(f, result, selected):
    # Human opens a renewed UI link after a long wait; scientific approval is unchanged.
    approval_id = f.runtime.scheduler_bindings.resolve(instance=f.instance.instance_id,
        namespace='approval', name=result['approval_name'])
    launch = f.runtime.approvals.refresh_access(approval_id)
    return ui_decide(f, {**result, 'review_url': 'http://127.0.0.1:8765' + launch.review_path}, selected)


def policy(f, **updates):
    with f.runs._connect() as db:
        saved = json.loads(db.execute('SELECT recovery_policy_json FROM runs WHERE run_id=?', (f.run_id,)).fetchone()[0])
        db.execute('UPDATE runs SET recovery_policy_json=? WHERE run_id=?',
            (json.dumps({**saved, **updates}), f.run_id))


def clock(monkeypatch):
    from scidiscovery.artifact_agent.service import runs, approvals, approval_waits
    value = SimpleNamespace(now=datetime.now(timezone.utc))
    class ClockDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return value.now
    monkeypatch.setattr(approval_waits, 'datetime', ClockDateTime)
    monkeypatch.setattr(runs, 'timestamp', lambda: value.now.isoformat().replace('+00:00', 'Z'))
    monkeypatch.setattr(runs, 'expired', lambda deadline: parse_time(deadline) <= value.now)
    monkeypatch.setattr(approvals, '_now', lambda now: now or value.now)
    return value


def execution(f):
    return f.runtime.scheduler_bindings.list(instance=f.instance.instance_id, namespace='execution',
        name_prefix='experiment-' + f.run_id + '-')[0]


def old_timeout(f):
    # This is the already-failed, pre-fix production shape: no wait ledger existed.
    policy(f, max_attempts=1, scheduler_max_attempts=1)
    with f.runs._connect() as db:
        db.execute("DELETE FROM run_activity WHERE run_id=? AND activity='approval_wait_started'", (f.run_id,))
        db.execute('UPDATE runs SET deadline_at=? WHERE run_id=?', ('2000-01-01T00:00:00Z', f.run_id))
    assert f.runs.reconcile_expired_active(run_ids=(f.run_id,)) == 1
    assert not f.runs.recovery_available(f.runs.status(f.run_id))
    f.root.facade.execution_bridge = f.coordinator.bridge


def test_human_wait_preserves_work_time_across_repeated_reads_and_restart(tmp_path, monkeypatch):
    f = experiment(tmp_path, monkeypatch)
    time = clock(monkeypatch)
    original = parse_time(f.runs.status(f.run_id).deadline_at)
    first = start(f)
    time.now += timedelta(hours=12)
    for _ in range(2):
        assert f.runs.reconcile_expired_active(run_ids=(f.run_id,)) == 0
        assert f.worker.call_tool('worker_experiment_execute', {'action': 'status'})['state'] == 'awaiting_authorization'
        assert parse_time(f.runs.status(f.run_id).deadline_at) == original + timedelta(hours=12)
    with f.runs._connect() as db:
        assert db.execute("SELECT COUNT(*) FROM run_activity WHERE run_id=? AND activity='approval_wait_started'", (f.run_id,)).fetchone()[0] == 1
        assert parse_time(db.execute('SELECT deadline_at FROM runs WHERE run_id=?', (f.run_id,)).fetchone()[0]) == original
    restarted = RunService(artifacts=f.runs.artifacts, database_path=f.runs.database_path,
        service_actor=f.runs.service_actor, operation_catalog=f.catalog, backend=f.runs.backend,
        scheduler_bindings=f.runs.scheduler_bindings, approval_database_path=f.runtime.approvals.database_path)
    assert restarted.status(f.run_id).deadline_at == f.runs.status(f.run_id).deadline_at
    decide(f, first, 'authorize_execution')
    deadline = f.runs.status(f.run_id).deadline_at
    time.now += timedelta(minutes=10)
    assert f.runs.status(f.run_id).deadline_at == deadline
    assert f.worker.call_tool('worker_experiment_execute', {'action': 'advance'})['state'] == 'running'
    assert f.adapter.submits == 1


@pytest.mark.parametrize('closing', ['reject_execution', 'cancel_approval', 'expire'])
def test_closed_wait_stops_credit_and_overlap_is_counted_once(tmp_path, monkeypatch, closing):
    f = experiment(tmp_path, monkeypatch)
    time = clock(monkeypatch)
    original = parse_time(f.runs.status(f.run_id).deadline_at)
    first = start(f)
    time.now += timedelta(minutes=30)
    second = f.worker.call_tool('worker_experiment_execute', {'action': 'start', 'implementation': f.alias, 'name': 'second'})
    time.now += timedelta(minutes=30)
    if closing == 'expire':
        approval_id = f.runtime.scheduler_bindings.resolve(instance=f.instance.instance_id,
            namespace='approval', name=first['approval_name'])
        f.runtime.approvals.expire_pending(approval_id)
    else:
        decide(f, first, closing)
    time.now += timedelta(minutes=30)
    decide(f, second, 'cancel_approval')
    assert parse_time(f.runs.status(f.run_id).deadline_at) == original + timedelta(minutes=90)
    time.now += timedelta(minutes=10)
    assert parse_time(f.runs.status(f.run_id).deadline_at) == original + timedelta(minutes=90)
    time.now = original + timedelta(minutes=91)
    assert f.runs.reconcile_expired_active(run_ids=(f.run_id,)) == 1


@pytest.mark.parametrize('review_required', [False, True])
@pytest.mark.parametrize('goal', ['research-objective', 'scientific-foundation', 'scientific-intake'])
def test_approved_orphan_starts_exact_request_without_new_run_or_retry(tmp_path, monkeypatch, review_required, goal):
    f = experiment(tmp_path, monkeypatch, goal=goal)
    if review_required:
        from tests.operations.test_task_execution_review import review
        policy(f, require_execution_review=True)
        handoff = f.worker.call_tool('worker_experiment_execute', {'action': 'review', 'implementation': f.alias})
        review(f, 'required-pass', handoff['review']['subject_artifact_name'], 'pass',
            request=handoff['review']['request'])
    first = start(f)
    binding = execution(f)
    request = f.runtime.executions.request(binding.object_id)
    old_timeout(f)
    decide(f, first, 'authorize_execution')
    before = f.runs.list(instance_id=f.instance.instance_id)
    page = f.root.call_tool('execution_status', {'name': binding.name}, surface='execution')
    assert 'execution_start' in page['recovery']['actions']
    for _ in range(2):
        assert f.root.call_tool('execution_start', {'name': binding.name}, surface='execution')['state'] == 'running'
    assert f.adapter.submits == 1
    assert f.runtime.executions.request(binding.object_id) == request
    assert f.runtime.executions.authorization(binding.object_id)['source'] == 'human'
    assert f.runtime.executions.budget_owner(binding.object_id) == f.coordinator.budget_subject(f.runs.status(f.run_id))
    assert f.runs.list(instance_id=f.instance.instance_id) == before
    assert not f.runs.recovery_available(f.runs.status(f.run_id))


@pytest.mark.parametrize('condition', ['active_owner', 'pending', 'rejected', 'changed_contract', 'review_revised', 'policy_denied'])
def test_recovery_start_keeps_authorization_review_and_owner_boundaries(tmp_path, monkeypatch, condition):
    from tests.operations.test_task_execution_review import review
    f = experiment(tmp_path, monkeypatch)
    if condition == 'review_revised':
        policy(f, require_execution_review=True)
        handoff = f.worker.call_tool('worker_experiment_execute', {'action': 'review', 'implementation': f.alias})
        subject = handoff['review']['subject_artifact_name']
        review(f, 'pass-before-request', subject, 'pass', request=handoff['review']['request'])
    first = start(f)
    binding = execution(f)
    f.root.facade.execution_bridge = f.coordinator.bridge
    if condition != 'active_owner':
        old_timeout(f)
    if condition != 'pending':
        decide(f, first, 'reject_execution' if condition == 'rejected' else 'authorize_execution')
    if condition == 'changed_contract':
        original = f.coordinator._contract_for_run
        def changed(run):
            owner, effect, identity, capability = original(run)
            return owner, effect, identity.model_copy(update={'operation_digest': 'f'*64}), capability
        monkeypatch.setattr(f.coordinator, '_contract_for_run', changed)
    if condition == 'review_revised':
        review(f, 'revise-after-request', subject, 'revise')
    if condition == 'policy_denied':
        check = f.adapter.execution_admission
        monkeypatch.setattr(f.adapter, 'execution_admission', lambda *args, **kwargs:
            check(*args, **kwargs).model_copy(update={'outcome': 'deny', 'reason': 'fixture current policy denies'}))
    with pytest.raises(Exception) as caught:
        f.root.call_tool('execution_start', {'name': binding.name}, surface='execution')
    message = str(caught.value)
    assert {'active_owner': 'managed within', 'pending': 'not authorized', 'rejected': 'not authorized',
        'changed_contract': 'contract differs', 'review_revised': 'did not pass', 'policy_denied': 'policy denied'}[condition] in message
    assert f.adapter.submits == 0
    assert f.runtime.executions.prepared_submission(binding.object_id) is None


def test_uncertain_recovery_submission_is_looked_up_without_duplicate(tmp_path, monkeypatch):
    f = experiment(tmp_path, monkeypatch)
    first = start(f)
    binding = execution(f)
    old_timeout(f)
    decide(f, first, 'authorize_execution')
    def uncertain(*args, **kwargs):
        f.adapter.submits += 1
        raise ConnectionError('fixture response lost after remote accepted')
    monkeypatch.setattr(f.adapter, 'submit', uncertain)
    result = f.root.call_tool('execution_start', {'name': binding.name}, surface='execution')
    assert result['submission']['state'] == 'unknown'
    assert result['submission']['error']
    descriptor = f.runtime.executions.prepared_submission(binding.object_id)
    assert descriptor is not None
    assert f.runtime.executions.budget_accounting(binding.object_id)['actual'] == {}
    assert f.root.call_tool('execution_start', {'name': binding.name}, surface='execution')['state'] == 'running'
    assert f.runtime.executions.prepared_submission(binding.object_id) == descriptor
    assert f.adapter.submits == 1


def test_natural_approval_expiry_and_root_abandon_end_wait(tmp_path, monkeypatch):
    f = experiment(tmp_path, monkeypatch)
    time = clock(monkeypatch)
    original = parse_time(f.runs.status(f.run_id).deadline_at)
    first = start(f)
    binding = execution(f)
    approval_id = 'apr_' + binding.object_id
    with f.runtime.approvals._connect() as db:
        db.execute('UPDATE approval_requests SET expires_at=? WHERE approval_id=?',
            ((time.now + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"), approval_id))
    time.now += timedelta(hours=1)
    assert parse_time(f.runs.status(f.run_id).deadline_at) == original + timedelta(minutes=30)
    assert f.runtime.approvals.status(approval_id).status == 'expired'
    old_timeout(f)
    result = f.root.call_tool('execution_abandon', {'name': binding.name}, surface='execution')
    assert result['state'] == 'abandoned' and f.adapter.submits == 0
    assert 'execution_start' not in result['recovery']['actions']


@pytest.mark.process_e2e
def test_exact_recovery_through_unified_mcp_proxy_and_daemon(tmp_path, monkeypatch):
    import multiprocessing
    import os
    import subprocess
    import sys
    import time
    from scidiscovery.plugin_runtime.transport import UnixSocketDaemon
    from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
    f = experiment(tmp_path, monkeypatch)
    first = start(f)
    binding = execution(f)
    old_timeout(f)
    decide(f, first, 'authorize_execution')
    ctx = multiprocessing.get_context('fork')
    count = ctx.Value('i', 0)
    submit = f.adapter.submit
    def counted(*args, **kwargs):
        count.value += 1
        return submit(*args, **kwargs)
    monkeypatch.setattr(f.adapter, 'submit', counted)
    socket = tmp_path / 'control.sock'
    gateway = UnifiedMCPRouter(f.root)
    daemon = ctx.Process(target=lambda: UnixSocketDaemon(socket, gateway).serve_forever())
    daemon.start()
    try:
        deadline = time.monotonic() + 5
        while not socket.exists() and time.monotonic() < deadline:
            time.sleep(.02)
        assert socket.exists()
        request = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {
            'name': 'scid_call', 'arguments': {'name': 'execution_start',
                'surface': 'execution', 'arguments': {'name': binding.name}},
            '_meta': {'x-codex-turn-metadata': {'session_id': 'recovery-root',
                'thread_id': 'recovery-root', 'thread_source': 'user'}}}}
        for _ in range(2):
            result = subprocess.run([sys.executable, '-m',
                'scidiscovery.artifact_agent.interfaces.mcp_proxy', '--socket', str(socket)],
                input=json.dumps(request)+'\n', text=True, capture_output=True, timeout=10,
                env=dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path)))
            assert result.returncode == 0, result.stderr
            reply = json.loads(result.stdout)
            assert 'error' not in reply, reply
            assert reply['result']['structuredContent']['state'] == 'running'
        assert count.value == 1
        assert f.runs.status(f.run_id).state == 'failed'
        assert f.runtime.executions.status(binding.object_id).external_run_id == 'next-external'
    finally:
        daemon.terminate()
        daemon.join(3)
        if daemon.is_alive():
            daemon.kill()
            daemon.join(3)


def test_approval_wait_deadline_survives_archive_and_restore(archive_system, monkeypatch):
    from scidiscovery.artifact_agent.schema.approval import approval_options_template
    from tests.operations.test_instance_archive import artifact, failed_run, save_archive, restore_archive
    runtime, service, instance_id, _ = archive_system
    time = clock(monkeypatch)
    original = time.now + timedelta(hours=2)
    failed_run(runtime, instance_id, 'run_waitarchive')
    # Historical storage fixture with no native writer or solver process.
    with runtime.runs._connect() as db:
        db.execute("UPDATE runs SET state='running',created_at=?,deadline_at=?,completed_at=NULL WHERE run_id=?",
            (time.now.isoformat(), original.isoformat(), 'run_waitarchive'))
    subject = artifact(runtime, instance_id, 'wait-subject')
    runtime.approvals.create_request(approval_id='apr_wait_archive', kind='run_request',
        subject_refs=(subject.ref,), question='Fixture wait?', options=approval_options_template('run_request'),
        idempotency_key='archive-wait', requested_by=runtime.actor)
    runtime.scheduler_bindings.bind(instance=instance_id, namespace='approval', name='wait', object_id='apr_wait_archive')
    runtime.runs.record_approval_wait('run_waitarchive', 'apr_wait_archive')
    time.now += timedelta(minutes=30)
    runtime.approvals.expire_pending('apr_wait_archive')
    with runtime.runs._connect() as db:
        db.execute("UPDATE runs SET state='failed',completed_at=? WHERE run_id=?",
            (time.now.isoformat(), 'run_waitarchive'))
    deadline = runtime.runs.status('run_waitarchive').deadline_at
    assert parse_time(deadline) == original + timedelta(minutes=30)
    save_archive(service, instance_id)
    assert service.archived_model(instance_id).runs.status('run_waitarchive').deadline_at == deadline
    restore_archive(service, instance_id)
    assert runtime.runs.status('run_waitarchive').deadline_at == deadline
