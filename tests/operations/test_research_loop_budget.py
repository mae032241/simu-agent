"""Explicit UI loop budgets through real admission and native accounting paths."""
import json
import re
from copy import copy
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest

from scidiscovery.artifact_agent.approval_ui import ApprovalUI
from scidiscovery.artifact_agent.interfaces.mcp_root import OperationCallInput
from scidiscovery.artifact_agent.service.instance_management import issue_instance_management_capability
from scidiscovery.artifact_agent.service.progression import ProgressionCoordinator
from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService
from tests.operations.test_local_worker_contracts import _system, _invoke, _write_result
from tests.operations.test_m6a_direct_instance_management import _request
from tests.operations.test_progression import Host, checkpoint, row
from tests.operations.test_scientific_progress import request
from tests.operations.worker_fixtures import attached_worker


class LoopHost(Host):
    def __init__(self, record, event):
        super().__init__(record, event)
        thread = json.loads(record['checkpoint_json'])['current_loop_id'] + '-root'
        self.identity = SimpleNamespace(thread_id=thread, session_id=thread)


@pytest.fixture
def loop_ui(tmp_path):
    catalog, runtime, instance, root = _system(tmp_path)
    bindings = runtime.scheduler_bindings
    user, now = 'sch_' + 'a' * 32, [1000.0]
    bindings.progression_clock = lambda: now[0]
    bindings.bind_session(session_key=user, instance_id=instance.instance_id)
    root.facade.session_key = user
    root.call_tool('artifact_ingest_text', dict(name='goal', text='Compare exact data and retain limits.'))
    root.call_tool('progression_command', dict(command='pause'))
    def facade(session):
        result = copy(root.facade)
        result.session_key = session
        return result
    coordinator = ProgressionCoordinator(runtime=runtime, host_factory=LoopHost,
        facade_factory=facade, clock=lambda: now[0])
    model = SimpleNamespace(artifacts=runtime.artifacts,
        progression_status=lambda instance, **kw: bindings.progression_status(instance_id=instance, **kw))
    secret = b'l' * 32
    ui = ApprovalUI(runtime.approvals, bindings=bindings,
        instance_management_secret=secret, read_model=model)
    base = ui.start()
    capability = issue_instance_management_capability(session_key=user, secret=secret)
    value = SimpleNamespace(catalog=catalog, runtime=runtime, instance=instance.instance_id,
        root=root, user=user, now=now, coordinator=coordinator, facade=facade, ui=ui, base=base,
        capability=capability, path='/sessions/' + user + '?' + urlencode(dict(capability=capability)))
    try:
        yield value
    finally:
        coordinator.close()
        ui.stop()


def loop_form(p):
    code, _, raw = _request(p.base, 'GET', p.path)
    assert code == 200
    panel = raw.decode().split('data-loop-authorization>', 1)[1].split('</details>', 1)[0]
    binding = re.search(r"name='confirmation_binding' value='([^']+)'", panel)[1]
    return dict(capability=p.capability, csrf=p.ui.session_id, command='authorize_loop',
        instance_id=p.instance, confirmation_binding=binding, objective_name='goal', confirm_loop_budget='yes')


def authorize(p, form=None, **changes):
    return _request(p.base, 'POST', '/instances/progression', form=dict(form or loop_form(p), **changes))[0]


def start(p, *, mode='background'):
    control = row(p)
    if control['state'] == 'paused' and control['mode'] == mode and control.get('request_fingerprint'):
        p.root.call_tool('progression_command', dict(command='resume'))
    else:
        p.root.call_tool('progression_command', dict(command='start', mode=mode, objective_name='goal'))
    if mode == 'interactive':
        return p.root
    p.coordinator.tick()
    assert p.coordinator.host is not None, row(p)
    return type(p.root)(p.facade(p.coordinator.host.scheduler_session))


def usage(p, thread, amount=10):
    p.coordinator._event(dict(method='thread/tokenUsage/updated', params=dict(threadId=thread,
        tokenUsage=dict(total=dict(inputTokens=amount, cachedInputTokens=0, outputTokens=1)))))


def finish_task(p, root, name):
    _invoke(root, name)
    worker = attached_worker(p.runtime, root, name)
    worker.call_tool('worker_open_assignment', {})
    _write_result(worker, observe_tokens=False)
    worker.call_tool('worker_submit_result', {})
    run_id = p.runtime.scheduler_bindings.resolve(instance=p.instance, namespace='run', name=name)
    return run_id, 'worker-' + run_id


def release(p):
    p.coordinator.host.finish()
    p.root.call_tool('progression_command', dict(command='pause'))
    p.coordinator.tick()
    assert row(p)['host_json'] is None


def test_unmanaged_interactive_retains_permissions_but_mcp_cannot_authorize_background(loop_ui):
    p = loop_ui
    p.root.call_tool('progression_command', dict(command='resume'))
    _invoke(p.root, 'ordinary-unmanaged')
    assert not (p.runtime.runs.status(p.runtime.scheduler_bindings.resolve(instance=p.instance,
        namespace='run', name='ordinary-unmanaged')).recovery_policy or {}).get('loop_id')
    p.root.call_tool('progression_command', dict(command='pause'))
    before = row(p)
    with pytest.raises(Exception, match='explicit research loop budget authorization'):
        start(p)
    with pytest.raises(Exception):
        p.root.call_tool('progression_command', dict(command='authorize_loop'))
    assert row(p) == before
    assert not checkpoint(p).get('loop_authorizations')


@pytest.mark.parametrize('bad', ['csrf', 'capability', 'instance_id', 'confirmation_binding', 'confirm_loop_budget'])
def test_ui_budget_confirmation_is_exact_and_cannot_be_forged(loop_ui, bad):
    p = loop_ui
    before = row(p)
    assert authorize(p, **{bad: 'invalid'}) in {403, 409}
    assert row(p) == before


def test_ui_budget_authorization_is_idempotent_and_scope_survives_goal_mode_restart(loop_ui):
    p = loop_ui
    form = loop_form(p)
    assert authorize(p, form) == 303
    first = checkpoint(p)
    identity = first['current_loop_id']
    assert authorize(p, form) == 303
    assert checkpoint(p) == first
    root = start(p, mode='interactive')
    root.call_tool('artifact_ingest_text', dict(name='revision', text='Retain the same budget for a revised objective.'))
    root.call_tool('progression_command', dict(command='pause'))
    root.call_tool('progression_command', dict(command='start', mode='background', objective_name='revision'))
    assert checkpoint(p)['current_loop_id'] == identity
    assert row(p)['config_json'] == json.dumps(first['loop_authorizations'][identity]['config'], sort_keys=True, separators=(',', ':'))
    reopened = SchedulerBindingService(p.runtime.scheduler_bindings.database_path)
    assert reopened.progression_status(instance_id=p.instance)['loop']['id'] == identity
    body = _request(p.base, 'GET', p.path)[2].decode()
    assert identity in body and '实际预算作用域' in body
    assert '建立独立人工工作作用域' not in body


def test_managed_interactive_and_direct_runservice_charge_the_same_task_budget(loop_ui):
    p = loop_ui
    bindings = p.runtime.scheduler_bindings
    settings = bindings.global_settings
    bindings.global_settings = settings.model_copy(update=dict(progression=settings.progression.model_copy(update=dict(max_tasks=1))))
    assert authorize(p) == 303
    root = start(p, mode='interactive')
    bound, _ = root.facade._configured_operation_call(vars(OperationCallInput.model_validate(request('direct-task'))))
    run_id = p.runtime.runs.schedule(bound, instance_id=p.instance, output_binding_name='direct-task.output',
        output_logical_name='direct-task.output', output_revision=1, output_binding_fingerprint='direct-task')
    identity = checkpoint(p)['current_loop_id']
    assert p.runtime.runs.status(run_id).recovery_policy['loop_id'] == identity
    assert checkpoint(p)['admissions']['direct-task']['loop_id'] == identity
    assert checkpoint(p)['admissions']['direct-task']['state'] == 'accepted'
    p.runtime.runs.record_failure(run_id, reason='Confirmed failed before platform attachment.',
        expected_state='queued', expected_last_activity_at=None)
    checked = root.call_tool('operation_preflight', request('cannot-escape'))
    assert not checked['admissible'] and checked['reason_code'] == 'background_task_budget_exhausted'
    root.call_tool('progression_command', dict(command='pause'))
    root.call_tool('progression_command', dict(command='resume'))
    with pytest.raises(Exception, match='task_budget_exhausted'):
        _invoke(root, 'renamed-cannot-escape')
    assert len(checkpoint(p)['admissions']) == 1


def test_new_loop_requires_resolved_work_and_complete_usage(loop_ui):
    p = loop_ui
    assert authorize(p) == 303
    root = start(p)
    _, thread = finish_task(p, root, 'original')
    original = checkpoint(p)['admissions']['original'].copy()
    release(p)
    before = row(p)
    assert authorize(p) == 409  # Missing Root/Worker observations are not zero cost.
    assert row(p) == before
    assert checkpoint(p)['admissions']['original'] == original
    root = start(p)
    usage(p, p.coordinator.host.identity.thread_id)
    usage(p, thread)
    assert checkpoint(p)['usage_summary']['coverage'] == 'observed'
    release(p)
    assert authorize(p) == 303
    assert checkpoint(p)['current_loop_id'] != original['loop_id']
    assert checkpoint(p)['admissions']['original'] == original


def test_late_usage_settles_retired_loop_and_native_threads_cannot_change_owner(loop_ui):
    p = loop_ui
    assert authorize(p) == 303
    root = start(p)
    usage(p, p.coordinator.host.identity.thread_id)
    run_id, thread = finish_task(p, root, 'old-work')
    usage(p, thread, 20)
    old_root = p.coordinator.host.identity.thread_id
    old = checkpoint(p)['current_loop_id']
    release(p)
    assert authorize(p) == 303
    root = start(p)
    new = checkpoint(p)['current_loop_id']
    usage(p, p.coordinator.host.identity.thread_id, 2)
    before = checkpoint(p)['loop_authorizations'][old]['budget_snapshot']['remaining_tokens']
    current = root.call_tool('progression_status', {})['budget']['remaining_tokens']
    usage(p, thread, 35)
    assert checkpoint(p)['usage_records'][thread]['loop_id'] == old
    assert checkpoint(p)['loop_authorizations'][old]['budget_snapshot']['remaining_tokens'] == before - 15
    assert root.call_tool('progression_status', {})['budget']['remaining_tokens'] == current
    usage(p, old_root, 30)
    assert checkpoint(p)['usage_records'][old_root]['loop_id'] == old
    assert checkpoint(p)['usage_records'][old_root]['role'] == 'root'
    assert checkpoint(p)['loop_authorizations'][old]['budget_snapshot']['remaining_tokens'] == before - 35
    assert root.call_tool('progression_status', {})['budget']['remaining_tokens'] == current
    assert p.runtime.runs.status(run_id).recovery_policy['loop_id'] == old
    with pytest.raises(Exception, match='original research loop'):
        p.runtime.runs.schedule(root.facade._configured_operation_call(vars(OperationCallInput.model_validate(request('replay'))))[0],
            instance_id=p.instance, output_binding_name='replay.output', output_logical_name='replay.output',
            output_revision=1, output_binding_fingerprint='replay', draft_from=run_id)
    _invoke(root, 'new-work')
    new_id = p.runtime.scheduler_bindings.resolve(instance=p.instance, namespace='run', name='new-work')
    with pytest.raises(Exception, match='cannot be reused across research loops'):
        p.runtime.runs.worker_connections.attach(run_id=new_id, platform_session='source-test-session', thread_id=thread)


def test_unknown_native_submission_blocks_new_loop_without_rebinding(loop_ui):
    p = loop_ui
    assert authorize(p) == 303
    cp = checkpoint(p)
    cp.update(phase='prepared', turn_id=None, fault_class='outcome_unknown')
    with p.runtime.scheduler_bindings._connect() as db:
        from scidiscovery.artifact_agent.service.progression_records import store_checkpoint
        db.execute('UPDATE scheduler_progression SET checkpoint_json=? WHERE instance_id=?',
            (store_checkpoint(db, p.instance, cp), p.instance))
    before = row(p)
    assert authorize(p) == 409
    assert row(p) == before


def test_completed_unmanaged_work_and_late_usage_keep_original_scope_after_first_loop(loop_ui):
    p = loop_ui
    p.root.call_tool('progression_command', dict(command='resume'))
    run_id, thread = finish_task(p, p.root, 'before-managed-loop')
    assert not p.runtime.runs.status(run_id).recovery_policy.get('loop_id')
    p.root.call_tool('progression_command', dict(command='pause'))
    assert authorize(p) == 303
    root = start(p)
    usage(p, p.coordinator.host.identity.thread_id)
    before = root.call_tool('progression_status', {})['budget']['remaining_tokens']
    usage(p, thread, 42)
    assert checkpoint(p)['usage_records'][thread]['role'] == 'worker'
    assert not checkpoint(p)['usage_records'][thread].get('loop_id')
    assert root.call_tool('progression_status', {})['budget']['remaining_tokens'] == before
    assert 'before-managed-loop' not in checkpoint(p).get('admissions', {})


def test_two_same_ui_requests_atomically_authorize_one_budget(loop_ui):
    from concurrent.futures import ThreadPoolExecutor
    p = loop_ui
    form = loop_form(p)
    # Two bounded HTTP clients in one source test, with one supervised pytest.
    with ThreadPoolExecutor(max_workers=2) as clients:
        replies = list(clients.map(lambda _: authorize(p, form), range(2)))
    assert replies == [303, 303]
    assert len(checkpoint(p)['loop_authorizations']) == 1


def test_new_loop_budget_does_not_clear_scientific_pause(loop_ui):
    from tests.operations.test_progress_shadow import native_delivery
    p = loop_ui
    bindings = p.runtime.scheduler_bindings
    settings = bindings.global_settings
    bindings.global_settings = settings.model_copy(update=dict(progression=settings.progression.model_copy(update=dict(progress_mode='assist'))))
    assert authorize(p) == 303
    root = start(p)
    usage(p, p.coordinator.host.identity.thread_id)
    for index in range(3):
        _, thread = finish_task(p, root, 'gap-' + str(index))
        usage(p, thread)
        native_delivery(p, root, 'gap-' + str(index))
    p.coordinator.host.finish()
    p.now[0] += 6
    p.coordinator.tick()
    p.coordinator.tick()
    assert row(p)['reason'] == 'scientific_progress_persistent_gap'
    before = bindings.progress_shadow(instance_id=p.instance,
        objective_ref=p.runtime.artifacts.get_by_id(bindings.resolve(instance=p.instance, namespace='artifact', name='goal')).ref)
    assert authorize(p) == 303
    with pytest.raises(Exception, match='scientific_progress_persistent_gap'):
        start(p)
    after = bindings.progress_shadow(instance_id=p.instance,
        objective_ref=p.runtime.artifacts.get_by_id(bindings.resolve(instance=p.instance, namespace='artifact', name='goal')).ref)
    assert after['notices'] == before['notices']
    assert after.get('window_start_sequence', 0) == before.get('window_start_sequence', 0)


def test_two_loops_on_one_goal_preserve_and_observe_the_last_new_result(loop_ui):
    from tests.operations.test_progress_shadow import native_delivery
    p = loop_ui
    bindings = p.runtime.scheduler_bindings
    settings = bindings.global_settings
    bindings.global_settings = settings.model_copy(update=dict(progression=settings.progression.model_copy(update=dict(max_tasks=1))))
    for name in ('early', 'later'):
        assert authorize(p) == 303
        root = start(p)
        assert checkpoint(p)['phase'] == 'running'
        usage(p, p.coordinator.host.identity.thread_id)
        _, thread = finish_task(p, root, name)
        usage(p, thread)
        native_delivery(p, root, name)
        release(p)
    view = p.root.call_tool('progression_status', {})
    with bindings._connect() as db:
        facts = [dict(item) for item in db.execute('SELECT * FROM scheduler_terminal_deliveries WHERE instance_id=?', (p.instance,))]
    assert view['progress_shadow']['counts']['consumed'] == 2, (
        [(item['task_name'], item['sequence'], item['consumed_boundary']) for item in facts],
        view['progress_shadow']['window_start_sequence'],
        [item['config']['effective']['progression']['max_tasks'] for item in checkpoint(p)['loop_authorizations'].values()])
    assert view['progress_shadow']['observation_scope']['max_observed_tasks'] == 1
    assert p.root.call_tool('run_status', dict(name='later'))['state'] == 'completed'
    assert len(checkpoint(p)['loop_authorizations']) == 2


def test_loop_scope_archive_restore_keeps_authorization_and_partial_frontend_usage(loop_ui):
    from tests.operations.synchronous_archive_fixture import SynchronousFixtureArchive
    from tests.operations.test_instance_archive import save_archive, restore_archive
    p = loop_ui
    assert authorize(p) == 303
    start(p, mode='interactive')
    identity = checkpoint(p)['current_loop_id']
    assert p.root.call_tool('progression_status', {})['usage']['coverage'] == 'missing'
    p.root.call_tool('progression_command', dict(command='pause'))
    p.runtime.runs._synchronous_archive_fixture = True
    archive = SynchronousFixtureArchive(p.runtime)
    before = checkpoint(p)
    save_archive(archive, p.instance)
    frozen = archive.archived_model(p.instance).overview(p.instance)['progression']
    assert frozen['loop']['id'] == identity
    assert frozen['loop']['history'][0]['budget']['usage']['unmeasured_roles'] == ['frontend_root', 'frontend_worker', 'frontend_helper']
    restore_archive(archive, p.instance)
    assert checkpoint(p) == before
    assert p.runtime.scheduler_bindings.progression_status(instance_id=p.instance)['loop']['id'] == identity


@pytest.mark.parametrize('policy', ['strict', 'bounded_fallback'])
def test_frontend_missing_usage_respects_existing_token_policy_and_remains_historical(loop_ui, policy):
    p = loop_ui
    bindings = p.runtime.scheduler_bindings
    settings = bindings.global_settings
    bindings.global_settings = settings.model_copy(update=dict(progression=settings.progression.model_copy(update=dict(token_policy=policy))))
    assert authorize(p) == 303
    root = start(p, mode='interactive')
    original = checkpoint(p)['current_loop_id']
    view = root.call_tool('progression_status', {})
    assert view['usage']['coverage'] == 'missing'
    assert view['usage']['unmeasured_roles'] == ['frontend_root', 'frontend_worker', 'frontend_helper']
    if policy == 'strict':
        before = checkpoint(p).get('admissions', {}).copy()
        with pytest.raises(Exception, match='loop_usage_unavailable'):
            _invoke(root, 'strict-missing')
        assert checkpoint(p).get('admissions', {}) == before
    else:
        _invoke(root, 'bounded-unmeasured-worker')
        worker = attached_worker(p.runtime, root, 'bounded-unmeasured-worker')
        worker.call_tool('worker_open_assignment', {})
        root.call_tool('progression_command', dict(command='pause'))
        assert authorize(p) == 409  # Unconnected telemetry never exempts actual accepted active work.
        root.call_tool('progression_command', dict(command='resume'))
        _write_result(worker, observe_tokens=False)
        worker.call_tool('worker_submit_result', {})
        assert p.coordinator.host is None  # No background telemetry or usage fixture injection.
        finish_task(p, root, 'bounded-second-worker')
        assert checkpoint(p)['admissions']['bounded-unmeasured-worker']['usage_source'] == 'frontend_unconnected'
        assert not checkpoint(p).get('usage_records')
        assert root.call_tool('progression_status', {})['usage']['coverage'] == 'missing'
    root.call_tool('progression_command', dict(command='pause'))
    assert authorize(p) == 303
    assert checkpoint(p)['current_loop_id'] != original
    history = checkpoint(p)['loop_authorizations'][original]['budget_snapshot']['usage']
    assert history['coverage'] == 'missing'
    assert history['unmeasured_roles'] == ['frontend_root', 'frontend_worker', 'frontend_helper']
    if policy == 'bounded_fallback':
        assert checkpoint(p)['loop_authorizations'][original]['budget_snapshot']['tasks'] == 2
        assert not checkpoint(p).get('usage_records')
    assert history['unmeasured_roles'] == ['frontend_root', 'frontend_worker', 'frontend_helper']


def test_standalone_effect_creation_and_launch_obey_current_loop_total_budget(tmp_path):
    from tests.operations.test_r4_execution_approval_identity import _setup, _create_effect, _effect_call, _decide_execution_approval
    from tests.operations.research_loop_fixtures import authorize_loop
    runtime, instance, adapter, facade, root, _ = _setup(tmp_path)
    bindings = runtime.scheduler_bindings
    session = 'loop-effects'
    bindings.bind_session(session_key=session, instance_id=instance.instance_id)
    facade.session_key = session
    root.call_tool('artifact_ingest_text', dict(name='goal', text='A separately budgeted fixture effect.'))
    root.call_tool('progression_command', dict(command='pause'))
    authorize_loop(runtime, instance.instance_id, session, 'goal')
    root.call_tool('progression_command', dict(command='resume'))
    _create_effect(root, name='owned-effect')
    _decide_execution_approval(runtime, root, name='owned-effect')
    row = bindings.progression_status(instance_id=instance.instance_id, internal=True)
    cp = json.loads(row['checkpoint_json'])
    execution = bindings.resolve(instance=instance.instance_id, namespace='execution', name='owned-effect')
    request_ref, _ = runtime.executions.approval_subject_refs(execution)
    assert runtime.artifacts.catalog(request_ref).labels['budget_loop'] == cp['current_loop_id']
    limits = json.loads(row['config_json'])['effective']['progression']
    bindings.observe_progression(instance_id=instance.instance_id, expected_host=None,
        changes=dict(attempts=limits['max_attempts']))
    with pytest.raises(Exception, match='loop_budget_exhausted'):
        root.call_tool('operation_invoke', _effect_call('cannot-create'))
    with pytest.raises(Exception, match='loop_budget_exhausted'):
        root.call_tool('execution_start', dict(name='owned-effect'), surface='execution')
    assert adapter.submit_count == 0


@pytest.mark.parametrize('source_field', ['resume_from', 'draft_from'])
def test_legal_failed_recovery_is_rejected_before_prepared_admission_in_new_loop(loop_ui, source_field):
    p = loop_ui
    assert authorize(p) == 303
    root = start(p)
    usage(p, p.coordinator.host.identity.thread_id)
    root.call_tool('operation_invoke', request('recoverable-A'))
    worker = attached_worker(p.runtime, root, 'recoverable-A')
    worker.call_tool('worker_open_assignment', {})
    _write_result(worker, observe_tokens=False)
    run_id = p.runtime.scheduler_bindings.resolve(instance=p.instance, namespace='run', name='recoverable-A')
    value = p.runtime.runs.status(run_id)
    p.runtime.runs.record_failure(run_id, reason='Confirmed Worker failure with a real recovery draft.',
        expected_state='running', expected_last_activity_at=value.last_activity_at)
    assert p.runtime.runs.status(run_id).recovery_draft
    assert root.call_tool('run_status', dict(name='recoverable-A'))['recovery_available']
    usage(p, 'worker-' + run_id)
    release(p)
    assert authorize(p) == 303
    root = start(p)
    usage(p, p.coordinator.host.identity.thread_id)
    rejected = dict(request('replay-B'), **{source_field: 'recoverable-A'})
    before = checkpoint(p)['admissions'].copy()
    preflight = root.call_tool('operation_preflight', rejected)
    reason = 'recovery_source_unavailable' if source_field == 'resume_from' else 'draft_source_unavailable'
    assert not preflight['admissible'] and preflight['reason_code'] == reason
    with pytest.raises(Exception, match=reason):
        root.call_tool('operation_invoke', rejected)
    assert checkpoint(p)['admissions'] == before
    assert all(item['state'] != 'prepared' for item in checkpoint(p)['admissions'].values())
    root.call_tool('operation_invoke', dict(request('ordinary-B'), instruction='Compare a new question under the second budget.'))


def test_ui_authorization_and_direct_runservice_schedule_share_one_atomic_boundary(loop_ui, monkeypatch):
    from contextlib import contextmanager
    from threading import Event, Thread, current_thread
    p = loop_ui
    p.root.call_tool('progression_command', dict(command='resume'))
    bound, _ = p.root.facade._configured_operation_call(vars(OperationCallInput.model_validate(request('direct-race'))))
    p.root.call_tool('progression_command', dict(command='pause'))
    form = loop_form(p)
    bindings = p.runtime.scheduler_bindings
    snapshot, attempted, finished = Event(), Event(), Event()
    original_lock = bindings.scheduling_lock
    original_reader = bindings.progress_active_work_reader
    results = {}
    @contextmanager
    def observed_lock():
        if current_thread().name == 'direct-schedule':
            attempted.set()
        with original_lock():
            yield
    def activity_snapshot(**kwargs):
        value = original_reader(**kwargs)
        assert not value
        snapshot.set()
        assert attempted.wait(5)
        assert not finished.is_set()
        return value
    monkeypatch.setattr(bindings, 'scheduling_lock', observed_lock)
    monkeypatch.setattr(bindings, 'progress_active_work_reader', activity_snapshot)
    def create_direct():
        try:
            results['run'] = p.runtime.runs.schedule(bound, instance_id=p.instance,
                output_binding_name='direct-race.output', output_logical_name='direct-race.output',
                output_revision=1, output_binding_fingerprint='direct-race')
        except Exception as error:
            results['rejected'] = str(error)
        finally:
            finished.set()
    client = Thread(name='authorize-client', target=lambda: results.update(ui=authorize(p, form)))
    direct = Thread(name='direct-schedule', target=create_direct)
    client.start()
    try:
        assert snapshot.wait(5)
        direct.start()
    finally:
        client.join(10)
        if direct.ident is not None:
            direct.join(10)
    assert not client.is_alive() and not direct.is_alive(), 'Shared control/Run lock order must not deadlock.'
    assert results['ui'] == 303
    assert 'rejected' in results and 'run' not in results
    with p.runtime.runs._connect() as db:
        assert not db.execute("SELECT 1 FROM runs WHERE instance_id=? AND state IN ('queued','running')", (p.instance,)).fetchone()
    assert checkpoint(p)['current_loop_id']



def test_frontend_fallback_preserves_prior_real_known_tokens_in_retired_loop(loop_ui):
    p = loop_ui
    assert authorize(p) == 303
    root = start(p)
    usage(p, p.coordinator.host.identity.thread_id, 20)
    _, thread = finish_task(p, root, 'native-observed')
    usage(p, thread, 30)
    release(p)
    root = start(p, mode='interactive')
    original = checkpoint(p)['current_loop_id']
    finish_task(p, root, 'frontend-unobserved')  # No usage injection for this front-end task.
    view = root.call_tool('progression_status', {})
    assert view['usage']['coverage'] == 'partial' and view['budget']['observed_tokens'] == 52
    before = view['budget']['remaining_tokens']
    root.call_tool('progression_command', dict(command='pause'))
    assert authorize(p) == 303
    retired = checkpoint(p)['loop_authorizations'][original]['budget_snapshot']
    assert retired['remaining_tokens'] == before
    assert retired['usage']['coverage'] == 'partial'
    assert retired['usage']['unmeasured_roles'] == ['frontend_root', 'frontend_worker', 'frontend_helper']
    assert len(checkpoint(p)['usage_records']) == 2
