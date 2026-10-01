"""Direct scientific pauses share control authority with UI and RunService."""
import pytest

from tests.operations.test_progression import progression, row, checkpoint
from tests.operations.test_progress_assist import configure, trigger, next_turn, correction_state
from tests.operations.test_scientific_progress import active, request, finish
from tests.operations.test_progress_shadow import native_delivery
from tests.operations.test_human_progress_continuation import paused, human_ui, submit, independent, fresh_binding


def test_consumed_threshold_pauses_without_reassessment(progression):
    p = progression
    configure(p)
    root = active(p)
    trigger(p, root)
    count = len(p.coordinator.host.prompts)
    next_turn(p)
    assert row(p)['state'] == 'paused'
    assert row(p)['reason'] == 'scientific_progress_persistent_gap'
    assert p.coordinator.host is None or len(p.coordinator.host.prompts) == count
    assert len(checkpoint(p)['admissions']) == 3


def test_poll_terminal_pause_releases_confirmed_host_and_ui_can_continue(progression, monkeypatch):
    from contextlib import contextmanager
    p = progression
    monkeypatch.setattr('scidiscovery.artifact_agent.service.scheduling_control.time', lambda: p.now[0])
    configure(p)
    root = active(p)
    host = p.coordinator.host
    for index in range(3):
        finish(p, root, f'poll-gap-{index}')
        native_delivery(p, root, f'poll-gap-{index}')
    assert row(p)['state'] == 'active'
    p.root.call_tool('progression_message', dict(name='poll.new.context', text='New context remains unread while paused.'))
    p.now[0] = max(p.now[0] + 6, checkpoint(p)['next_probe_at'])
    queued = [True]
    def poll(timeout=0):
        if queued:
            queued.pop()
            host.finish()  # Native completion is dispatched inside the real tick poll.
        return host.completion
    monkeypatch.setattr(host, 'poll', poll)
    error = None
    try:
        p.coordinator.tick()
    except Exception as failure:
        error = failure
    assert error is None, (str(error), row(p)['reason'], checkpoint(p).get('runtime_status'))
    assert row(p)['state'] == 'paused' and row(p)['reason'] == 'scientific_progress_persistent_gap'
    assert row(p)['host_json'] is None and p.coordinator.host is None and host.closed
    assert checkpoint(p).get('fault_code') is None and len(host.prompts) == 1
    assert checkpoint(p)['messages'] != checkpoint(p)['processed_snapshot'].get('messages', [])
    with contextmanager(human_ui.__wrapped__)(p) as ui:
        assert submit(ui) == 303
        assert row(p)['state'] == 'active'


def test_mcp_takeover_cannot_clear_scientific_pause(paused):
    p = paused
    before = checkpoint(p)
    with pytest.raises(Exception, match='scientific_progress_persistent_gap'):
        p.root.call_tool('progression_command', dict(command='takeover', mode='interactive'))
    assert row(p)['state'] == 'paused'
    assert checkpoint(p) == before
    p.root.call_tool('progression_report', dict(summary='A changed plan alone cannot clear this pause.', completed=True))
    assert row(p)['reason'] == 'scientific_progress_persistent_gap'
    p.root.call_tool('progression_message', dict(name='revised-context', text='An exact revised goal.'))
    bindings = p.runtime.scheduler_bindings
    settings = bindings.global_settings
    bindings.global_settings = settings.model_copy(update=dict(progression=settings.progression.model_copy(
        update=dict(progress_mode='off'))))
    with pytest.raises(Exception, match='scientific_progress_persistent_gap'):
        p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='revised-context'))
    from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService
    reopened = SchedulerBindingService(bindings.database_path)
    with pytest.raises(Exception, match='scientific_progress_persistent_gap'):
        reopened.progression_command(instance_id=p.instance, session_key=p.user, command='resume')


def test_ui_continue_opens_consumed_window_preserving_trigger(human_ui):
    ui, p = human_ui, human_ui.p
    before = correction_state(p)
    budget = checkpoint(p)['budget']
    assert submit(ui) == 303
    after = correction_state(p)
    assert after['notices'] == before['notices']
    assert after['window_start_sequence'] == before['through_sequence']
    assert after['counts']['consumed'] == 0
    assert checkpoint(p)['budget'] == budget


def test_direct_runservice_cannot_admit_through_scientific_pause(paused):
    from scidiscovery.artifact_agent.interfaces.mcp_root import OperationCallInput
    p = paused
    bound, _ = p.root.facade._configured_operation_call(vars(
        OperationCallInput.model_validate(request('direct-bypass'))))
    with pytest.raises(Exception, match='scientific_progress_persistent_gap'):
        p.runtime.runs.schedule(bound, instance_id=p.instance,
            output_binding_name='direct-bypass.output', output_logical_name='direct-bypass.output',
            output_revision=1, output_binding_fingerprint='direct-bypass')


def test_ui_window_reaches_threshold_again_on_actual_native_consumption(human_ui):
    ui, p = human_ui, human_ui.p
    notices = correction_state(p)['notices'].copy()
    assert submit(ui) == 303
    p.root.call_tool('progression_command', dict(command='pause'))
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='goal'))
    root = active(p)
    host = p.coordinator.host
    for index in range(3):
        finish(p, root, f'next-window-{index}')
        native_delivery(p, root, f'next-window-{index}')
    host.finish()
    next_turn(p)
    state = correction_state(p)
    assert row(p)['state'] == 'paused'
    assert state['window_start_sequence'] == 3 and state['counts']['consumed'] == 3
    assert state['notices'][:len(notices)] == notices
    assert len(host.prompts) == 1 and len(checkpoint(p)['admissions']) == 6


def test_old_control_format_with_manual_observation_is_explicitly_rejected(paused):
    import json
    from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService
    bindings = paused.runtime.scheduler_bindings
    with bindings._connect() as db:
        db.execute('PRAGMA user_version=3')
        state = correction_state(paused)
        state.update(window_starts={'background': 0, 'old-manual-id': 3},
            through_sequences={'background': 3, 'old-manual-id': 3}, scope_id='old-manual-id')
        db.execute('UPDATE scheduler_progress_shadow SET state_json=? WHERE instance_id=?',
            (json.dumps(state), paused.instance))
    with pytest.raises(Exception, match='incompatible scheduler control schema'):
        SchedulerBindingService(bindings.database_path)
    from scidiscovery.artifact_agent.service.instance_archive_records import schema, execution_settings_restore_view
    with bindings._connect() as db:
        archived = dict(schema=schema(db), tables={})
    with pytest.raises(Exception, match='unsupported scheduler control schema version'):
        execution_settings_restore_view(archived)


def test_http_independent_tasks_keep_background_observation_and_recovery(human_ui):
    """Manual results retain history and remain excluded when background later reads them."""
    from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from tests.operations.test_local_worker_contracts import _write_result
    from tests.operations.test_unified_mcp import call, result
    from tests.operations.test_background_human_recovery import background_form
    from tests.operations.test_m6a_direct_instance_management import _request
    ui, p = human_ui, human_ui.p
    before = correction_state(p)
    assert independent(ui) == 303
    manual_id = checkpoint(p)['interactive_sessions'][-1]['id']
    gateway = UnifiedMCPRouter(p.root)
    compiled = p.catalog.operation('blind.csv.observe.v1')
    for name, outcome in [('manual-success', 'completed'), ('manual-failure', 'failed')]:
        result(call(gateway, 'operation_invoke', request(name), session='manual-root'))
        run_id = checkpoint(p)['admissions'][name]['run_id']
        profile = p.runtime.runs.status(run_id).execution_profile['profile']
        result(call(gateway, 'worker_attach', dict(name=name, thread_id=name), session='manual-root'))
        result(call(gateway, 'worker_open_assignment', child=name, session='manual-root', profile=profile))
        if outcome == 'completed':
            worker = LocalWorkerMCPRouter(p.runtime.runs, operation_id=compiled.spec.operation_id,
                operation_digest=compiled.digest, run_id=run_id, trusted_caller=('manual-root', name))
            worker.call_tool('worker_open_assignment', {})
            _write_result(worker)
            result(call(gateway, 'worker_submit_result', child=name, session='manual-root', profile=profile))
        else:
            run = p.runtime.runs.status(run_id)
            result(call(gateway, 'run_record_failure', dict(name=name, reason='Confirmed manual failure.',
                expected_state='running', expected_last_activity_at=run.last_activity_at), session='manual-root'))
        assert result(call(gateway, 'run_status', dict(name=name), session='manual-root'))['state'] == outcome
        assert checkpoint(p)['admissions'][name]['interactive_session_id'] == manual_id
    assert correction_state(p)['counts'] == before['counts']
    assert correction_state(p)['notices'] == before['notices']
    assert 'observation_scope_id' not in checkpoint(p)
    for command in ('start', 'resume', 'takeover'):
        args = dict(command=command, mode='background')
        if command == 'start':
            args['objective_name'] = 'goal'
        with pytest.raises(Exception):
            p.root.call_tool('progression_command', args)
    assert p.root.call_tool('progression_status', {})['interactive_session']['active']
    p.root.call_tool('progression_command', dict(command='pause'))
    with pytest.raises(Exception):
        p.root.call_tool('operation_invoke', request('expired-manual-authority'))
    for command in ('start', 'resume', 'takeover'):
        args = dict(command=command, mode='background')
        if command == 'start':
            args['objective_name'] = 'goal'
        with pytest.raises(Exception, match='scientific_progress_persistent_gap'):
            p.root.call_tool('progression_command', args)
    form = background_form(ui)
    assert _request(ui.base, 'POST', '/instances/progression', form=form)[0] == 303
    root = active(p)
    p.coordinator.host.finish()  # Real backend receipt of both manual terminal results.
    next_turn(p)
    assert correction_state(p)['counts']['consumed'] == 0
    assert correction_state(p)['notices'] == before['notices']
    root.call_tool('operation_invoke', dict(request('background-after-manual'),
        instruction='Compare the retained manual outcomes after the explicit background confirmation.'))
    assert not checkpoint(p)['admissions']['background-after-manual'].get('interactive_session_id')
