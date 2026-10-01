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


def test_old_control_format_with_unknown_episode_is_explicitly_rejected(paused):
    import json
    from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService
    bindings = paused.runtime.scheduler_bindings
    with bindings._connect() as db:
        db.execute('PRAGMA user_version=2')
        state = correction_state(paused)
        state['assist'] = [dict(state='submitted_unknown')]
        db.execute('UPDATE scheduler_progress_shadow SET state_json=? WHERE instance_id=?',
            (json.dumps(state), paused.instance))
    with pytest.raises(Exception, match='incompatible scheduler control schema'):
        SchedulerBindingService(bindings.database_path)
    from scidiscovery.artifact_agent.service.instance_archive_records import schema, execution_settings_restore_view
    with bindings._connect() as db:
        archived = dict(schema=schema(db), tables={})
    with pytest.raises(Exception, match='unsupported scheduler control schema version'):
        execution_settings_restore_view(archived)


def test_persisted_independent_scope_fixture_keeps_background_pause_and_own_window(human_ui):
    """Stored consumed facts verify scope isolation, not foreground receipt coverage."""
    import json
    from scidiscovery.artifact_agent.schema.common import canonical_sha256
    from scidiscovery.artifact_agent.service.scientific_progress import _update_fact, refresh_shadow
    ui, p = human_ui, human_ui.p
    old = correction_state(p)['notices'].copy()
    assert independent(ui) == 303
    scope_id = checkpoint(p)['interactive_sessions'][-1]['id']
    for index in range(3):
        finish(p, p.root, f'independent-gap-{index}')
    bindings = p.runtime.scheduler_bindings
    control = row(p)
    goal = json.loads(control['objective_ref_json'])
    key = canonical_sha256(goal)
    with bindings._connect() as db:
        for index in range(3):
            name = f'independent-gap-{index}'
            run_id = checkpoint(p)['admissions'][name]['run_id']
            run = p.runtime.runs.status(run_id)
            terminal = dict(state='completed', output=run.output_ref.model_dump(mode='json'), reason=None)
            sequence = index + 4
            db.execute('INSERT INTO scheduler_terminal_deliveries VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (sequence, p.instance, key, run_id, name, json.dumps(goal), json.dumps(terminal),
                 '{}', 'null', 'stored-scope-fixture', 'fixture_consumed_fact'))
            _update_fact(db, p.instance, key, run_id, dict(sequence=sequence, task_name=name,
                terminal=terminal, intent=None))
        refresh_shadow(db, control, key)
    assert bindings.progress_boundary(instance_id=p.instance) == 'scientific_progress_persistent_gap'
    state = correction_state(p)
    assert state['scope_id'] == scope_id and state['counts']['consumed'] == 3
    assert state['notices'][:len(old)] == old
    with pytest.raises(Exception, match='scientific_progress_persistent_gap'):
        p.root.call_tool('progression_command', dict(command='resume'))
    assert submit(ui, confirmation_binding=fresh_binding(ui)) == 303
    finish(p, p.root, 'independent-same-scope')
    assert checkpoint(p)['admissions']['independent-same-scope']['interactive_session_id'] == scope_id
    assert correction_state(p)['window_start_sequence'] == 6
    p.root.call_tool('progression_command', dict(command='pause'))
    with pytest.raises(Exception, match='scientific_progress_persistent_gap'):
        p.root.call_tool('progression_command', dict(command='takeover', mode='background'))
