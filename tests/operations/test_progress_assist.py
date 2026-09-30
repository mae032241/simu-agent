"""Assist through real task admission, native receipts and durable recovery."""
import json

import pytest

from tests.operations.test_progression import progression, row, checkpoint
from tests.operations.test_scientific_progress import active, finish, assess, request, INTENT
from tests.operations.test_progress_shadow import native_delivery, database, consume, fact, state
from scidiscovery.artifact_agent.service.scientific_progress import (
    assist_transition, _update_fact, refresh_shadow, shadow_projection,
)


def configure(p, **limits):
    bindings = p.runtime.scheduler_bindings
    settings = bindings.global_settings
    bindings.global_settings = settings.model_copy(update=dict(progression=settings.progression.model_copy(
        update=dict(progress_mode='assist', **limits))))
    p.root.call_tool('progression_command', dict(command='pause'))
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='goal'))


def trigger(p, root, outcome=None):
    for index in range(3):
        name = f'renamed-{index}'
        finish(p, root, name, {**INTENT, 'target': f'Paraphrased target {index}'})
        if outcome:
            assess(root, name, outcome=outcome, evidence=outcome != 'advance')
        native_delivery(p, root, name)
    p.coordinator.host.finish()


def notice(p):
    return p.root.call_tool('progression_status', {})['progress_shadow']['assist']


def next_turn(p):
    p.now[0] += 6
    p.coordinator.tick()


@pytest.mark.parametrize('outcome', [None, 'unknown', 'advance'])
def test_consumption_confirmed_notice_one_task_then_next_admission_stops(progression, outcome):
    p = progression
    configure(p)
    root = active(p)
    trigger(p, root, outcome)
    assert notice(p)['state'] == 'observing'
    next_turn(p)
    delivered = notice(p)
    assert delivered['delivery'] == 'confirmed' and delivered['reassessments'] == 1
    assert delivered['state'] == 'delivered'
    assert delivered['causes']
    brief = json.loads(p.coordinator.host.prompts[-1].split('\n')[-1])
    assert brief['progress_shadow']['assist']['state'] == 'prepared'
    # A plan change is not a result; the first adjusted task must remain allowed.
    root.call_tool('progression_report', dict(summary='Change the planned explanation and test it.'))
    finish(p, root, 'one-adjustment')
    assess(root, 'one-adjustment', outcome='unknown')
    native_delivery(p, root, 'one-adjustment')
    with pytest.raises(Exception, match='scientific_progress_persistent_gap'):
        root.call_tool('operation_invoke', request('another-renamed-task'))
    assert row(p)['state'] == 'paused'
    assert notice(p)['state'] == 'exhausted'
    assert notice(p)['id'] == delivered['id'] and notice(p)['reassessments'] == 1
    assert len(checkpoint(p)['admissions']) == 4
    assert p.root.call_tool('run_status', dict(name='one-adjustment'))['state'] == 'completed'


def test_silent_reassessment_ends_at_native_boundary_and_resume_cannot_refund(progression):
    from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService
    p = progression
    configure(p)
    root = active(p)
    trigger(p, root)
    next_turn(p)
    host = p.coordinator.host
    delivered = notice(p)
    # Correction of a trigger does not revoke a delivered episode.
    assess(root, 'renamed-2', outcome='advance')
    assert notice(p)['state'] == 'delivered'
    host.finish()
    next_turn(p)
    assert row(p)['state'] == 'paused'
    assert row(p)['reason'] == 'scientific_progress_persistent_gap'
    saved = notice(p)
    reopened = SchedulerBindingService(p.runtime.scheduler_bindings.database_path)
    assert shadow_projection(bindings=reopened, row=row(p))['assist'] == saved
    count = len(host.prompts)
    p.root.call_tool('progression_command', dict(command='resume'))
    next_turn(p)
    assert row(p)['state'] == 'paused'
    assert len(host.prompts) == count
    assert notice(p)['id'] == delivered['id'] and notice(p)['reassessments'] == 1


def test_adjusted_task_waits_without_extra_round_and_results_get_one_consumption_turn(progression):
    from tests.operations.test_local_worker_contracts import _worker, _write_result
    p = progression
    configure(p)
    root = active(p)
    trigger(p, root)
    next_turn(p)
    host = p.coordinator.host
    root.call_tool('operation_invoke', request('adjusted-pending'))
    host.finish()
    next_turn(p)
    count = len(host.prompts)
    assert notice(p)['state'] == 'awaiting_result' and row(p)['state'] == 'active'
    next_turn(p)
    assert len(host.prompts) == count
    worker = _worker(p.catalog, p.runtime)
    worker.call_tool('worker_open_assignment', {})
    _write_result(worker)
    worker.call_tool('worker_submit_result', {})
    next_turn(p)
    assert len(host.prompts) == count+1
    assert row(p)['state'] == 'active'
    with pytest.raises(Exception, match='scientific_progress_persistent_gap'):
        root.call_tool('operation_invoke', request('second-adjustment'))
    assert row(p)['state'] == 'paused'


def assist_db():
    db, current, key = database()
    settings = json.loads(current['config_json'])
    settings['effective']['progression']['progress_mode'] = 'assist'
    current['config_json'] = json.dumps(settings)
    for index in range(1, 4):
        consume(db, current, key, fact(index, 'no_progress'))
    return db, current, key


def prepare_confirm(db, current):
    cp = dict(rounds=2, phase='idle')
    assist_transition(db, current, cp, event='prepare')
    cp.update(rounds=3, phase='prepared', turn_id=None, progress_notice=state(db)['assist'][-1]['id'])
    assist_transition(db, current, cp, event='submit')
    cp.update(phase='running', turn_id='confirmed')
    assist_transition(db, current, cp, event='confirm')
    return cp


def test_stale_shadow_candidates_are_not_delivered_and_unknown_submit_not_consumed():
    db, current, key = assist_db()
    _update_fact(db, current['instance_id'], key, '3', dict(assessment=fact(3, 'advance', 'new')['assessment']))
    refresh_shadow(db, current, key)
    assert state(db)['notices']
    assist_transition(db, current, dict(rounds=2), event='prepare')
    assert state(db)['assist'] == []
    db, current, key = assist_db()
    cp = dict(rounds=2, phase='prepared', turn_id=None)
    assist_transition(db, current, cp, event='prepare')
    assist_transition(db, current, cp, event='confirm')
    assert state(db)['assist'][-1]['state'] == 'prepared'
    assert state(db)['assist'][-1]['reassessments'] == 0
    # A correction between preparation and native confirmation withdraws it.
    _update_fact(db, current['instance_id'], key, '3', dict(assessment=fact(3, 'advance', 'new')['assessment']))
    refresh_shadow(db, current, key)
    cp.update(phase='running', turn_id='confirmed', progress_notice=state(db)['assist'][-1]['id'], rounds=3)
    assist_transition(db, current, cp, event='confirm')
    assert state(db)['assist'][-1]['state'] == 'withdrawn'


def test_new_scientific_evidence_resolves_but_same_payload_new_ref_cannot():
    db, current, key = assist_db()
    cp = prepare_confirm(db, current)
    frozen = state(db)['assist'][-1]['snapshot']
    consume(db, current, key, fact(4, 'advance', 'same'))
    assert state(db)['assist'][-1]['state'] == 'delivered'
    consume(db, current, key, fact(5, 'advance', 'negative-evidence-excludes-a-mechanism'))
    assert state(db)['assist'][-1]['state'] == 'resolved'
    assert state(db)['assist'][-1]['snapshot'] == frozen
    assert assist_transition(db, current, cp, event='admission', admission='reasonable-continuation') is None


def test_exhausted_budget_never_starts_reassessment_model_turn(progression):
    p = progression
    configure(p, max_rounds=1)
    root = active(p)
    trigger(p, root)
    host = p.coordinator.host
    next_turn(p)
    assert len(host.prompts) == 1
    assert row(p)['state'] == 'paused' and row(p)['reason'] == 'budget_exhausted'
    assert notice(p)['state'] == 'observing'


def finish_changed(p, root, name):
    from tests.operations.test_local_worker_contracts import _worker, _write_result
    root.call_tool('operation_invoke', request(name))
    worker = _worker(p.catalog, p.runtime)
    worker.call_tool('worker_open_assignment', {})
    _write_result(worker)
    path = worker._workspace.output_directory / 'result.json'
    value = json.loads(path.read_text())
    value['payload']['interpretation'] = 'The sealed analysis excludes a claimed causal mechanism; two observations cannot identify it.'
    path.write_text(json.dumps(value))
    worker.call_tool('worker_submit_result', {})


@pytest.mark.parametrize('new_evidence', [False, True])
def test_actual_adjusted_result_requires_new_evidence_and_allows_negative_advance(progression, new_evidence):
    p = progression
    configure(p)
    root = active(p)
    trigger(p, root, outcome='no_progress')
    next_turn(p)
    old = notice(p)
    (finish_changed if new_evidence else finish)(p, root, 'adjustment')
    assess(root, 'adjustment', outcome='advance')
    native_delivery(p, root, 'adjustment')
    if new_evidence:
        root.call_tool('operation_invoke', request('reasonable-continuation'))
        assert notice(p)['state'] == 'resolved' and row(p)['state'] == 'active'
    else:
        with pytest.raises(Exception, match='scientific_progress_persistent_gap'):
            root.call_tool('operation_invoke', request('same-evidence-renamed'))
        assert notice(p)['state'] == 'exhausted' and row(p)['state'] == 'paused'
    assert notice(p)['trigger_counts'] == old['trigger_counts']


def test_actual_correction_before_delivery_has_no_stale_assist_gate(progression):
    p = progression
    configure(p)
    root = active(p)
    trigger(p, root, outcome='no_progress')
    assess(root, 'renamed-2', outcome='advance')
    next_turn(p)
    assert notice(p)['state'] == 'observing'
    root.call_tool('operation_invoke', request('continued-with-corrected-understanding'))
    assert row(p)['state'] == 'active'


def test_unknown_native_submission_preserves_prepared_and_never_replays(progression, monkeypatch):
    p = progression
    configure(p)
    root = active(p)
    trigger(p, root)
    host = p.coordinator.host
    attempts = []
    def lost(prompt):
        attempts.append(prompt)
        raise TimeoutError('unknown native submission')
    monkeypatch.setattr(host, 'start_turn', lost)
    with pytest.raises(TimeoutError, match='unknown native submission'):
        next_turn(p)
    assert row(p)['state'] == 'paused'
    assert row(p)['reason'] == 'host_fault' and checkpoint(p)['fault_class'] == 'outcome_unknown'
    assert notice(p)['state'] == 'submitted_unknown' and notice(p)['reassessments'] == 0
    next_turn(p)
    assert len(attempts) == 1


def test_takeover_off_and_new_goal_preserve_history_and_budgets(progression):
    p = progression
    configure(p)
    root = active(p)
    trigger(p, root)
    next_turn(p)
    p.coordinator.host.finish()
    next_turn(p)
    saved = notice(p)
    old_budget = checkpoint(p)
    p.root.call_tool('progression_command', dict(command='takeover'))
    with pytest.raises(Exception, match='scientific_progress_persistent_gap'):
        p.root.call_tool('operation_invoke', request('takeover-is-not-a-new-allowance'))
    assert row(p)['state'] == 'paused'
    configure(p, progress_pause_on_persistent_gap=True)
    # Explicitly turn this policy off using the existing frozen-config restart.
    bindings = p.runtime.scheduler_bindings
    settings = bindings.global_settings
    bindings.global_settings = settings.model_copy(update=dict(progression=settings.progression.model_copy(
        update=dict(progress_mode='off'))))
    p.root.call_tool('progression_command', dict(command='pause'))
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='goal'))
    root = active(p)
    finish(p, root, 'off-task')
    assert notice(p) == saved
    assert checkpoint(p)['started_at'] == old_budget['started_at']
    root.call_tool('artifact_ingest_text', dict(name='revised-goal', text='Separate frozen scientific question.'))
    p.coordinator.host.finish()
    p.root.call_tool('progression_command', dict(command='pause'))
    p.coordinator.tick()
    settings = bindings.global_settings
    bindings.global_settings = settings.model_copy(update=dict(progression=settings.progression.model_copy(
        update=dict(progress_mode='assist'))))
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='revised-goal'))
    root = active(p)
    assert notice(p)['state'] == 'observing'
    assert len(checkpoint(p)['admissions']) == 4
    assert checkpoint(p)['rounds'] >= old_budget['rounds']
    assert checkpoint(p)['started_at'] == old_budget['started_at']
    root.call_tool('operation_invoke', request('new-goal-task'))


def test_archive_restores_exhausted_episode_without_refunding_reassessment(progression):
    from tests.operations.synchronous_archive_fixture import SynchronousFixtureArchive
    from tests.operations.test_instance_archive import save_archive, restore_archive
    from scidiscovery.artifact_agent.service.progression_read import progression_read_view
    p = progression
    configure(p)
    root = active(p)
    trigger(p, root)
    next_turn(p)
    p.coordinator.host.finish()
    next_turn(p)
    p.coordinator.tick()  # release the terminal native host before archiving
    expected = p.root.call_tool('progression_status', {})['progress_shadow']
    p.runtime.runs._synchronous_archive_fixture = True
    archive = SynchronousFixtureArchive(p.runtime)
    save_archive(archive, p.instance)
    assert archive.archived_model(p.instance).progression_status(p.instance)['progress_shadow'] == expected
    restore_archive(archive, p.instance)
    restored = progression_read_view(bindings=p.runtime.scheduler_bindings, runs=p.runtime.runs,
        artifacts=p.runtime.artifacts, operation_catalog=p.catalog, instance_id=p.instance)
    assert restored['progress_shadow'] == expected
    assert restored['state'] == 'paused'
    p.runtime.scheduler_bindings.bind_session(session_key=p.user, instance_id=p.instance)
    p.root.call_tool('progression_command', dict(command='resume'))
    next_turn(p)
    assert row(p)['state'] == 'paused'
    assert notice(p)['state'] == 'exhausted' and notice(p)['reassessments'] == 1


@pytest.mark.parametrize('mode', ['shadow', 'off'])
def test_non_assist_modes_never_intercept_ordinary_admission(progression, mode):
    p = progression
    if mode == 'off':
        bindings = p.runtime.scheduler_bindings
        settings = bindings.global_settings
        bindings.global_settings = settings.model_copy(update=dict(progression=settings.progression.model_copy(
            update=dict(progress_mode=mode))))
        p.root.call_tool('progression_command', dict(command='pause'))
        p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='goal'))
    root = active(p)
    trigger(p, root)
    next_turn(p)
    finish(p, root, 'ordinary-next')
    assert row(p)['state'] == 'active'
    assert notice(p)['state'] == 'observing'


def test_first_threshold_at_actual_next_admission_requires_reassessment_before_more_tasks(progression):
    p = progression
    configure(p)
    root = active(p)
    host = p.coordinator.host
    for index in range(3):
        finish(p, root, f'gap-{index}')
        native_delivery(p, root, f'gap-{index}')
    # The third terminal is settled by the fourth admission, while the same
    # native turn is still running. No coordinator idle boundary has occurred.
    for name in ('fourth-ordinary', 'fifth-renamed'):
        with pytest.raises(Exception, match='scientific_progress_reassessment_pending.*coverage_gap'):
            root.call_tool('operation_invoke', request(name))
    assert len(checkpoint(p)['admissions']) == 3
    assert row(p)['state'] == 'active' and notice(p)['state'] == 'prepared'
    assert notice(p)['delivery'] == 'unconfirmed'
    p.coordinator.tick()
    assert len(host.prompts) == 1
    host.finish()
    next_turn(p)
    assert notice(p)['state'] == 'delivered' and notice(p)['reassessments'] == 1
    finish(p, root, 'one-real-reassessment-task')
    assert len(checkpoint(p)['admissions']) == 4


def correction_state(p):
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    return p.runtime.scheduler_bindings.progress_shadow(instance_id=p.instance,
        objective_ref=ArtifactRef.model_validate_json(row(p)['objective_ref_json']))


@pytest.mark.parametrize('when', ['before_submit', 'after_submit_before_ack', 'after_ack'])
def test_actual_brief_versions_cannot_deliver_replaced_causes(progression, monkeypatch, when):
    p = progression
    configure(p)
    root = active(p)
    trigger(p, root, outcome='no_progress')
    host = p.coordinator.host
    def correct():
        for index in range(3):
            assess(root, f'renamed-{index}', outcome='unknown', reason='Correction: the old scientific judgment is unsupported.')
    old_brief, old_start = p.coordinator._brief, host.start_turn
    if when == 'before_submit':
        def changed_brief(*args, **kwargs):
            prompt = old_brief(*args, **kwargs)
            correct()
            return prompt
        monkeypatch.setattr(p.coordinator, '_brief', changed_brief)
    else:
        def changed_start(prompt):
            assert notice(p)['state'] == 'submitted_unknown'
            assert notice(p)['delivery'] == 'unconfirmed'
            if when == 'after_submit_before_ack':
                correct()
            turn = old_start(prompt)
            if when == 'after_ack':
                correct()
            return turn
        monkeypatch.setattr(host, 'start_turn', changed_start)
    next_turn(p)
    first = correction_state(p)['assist'][0]
    assert first['snapshot']['causes'] == ['no_progress']
    assert correction_state(p)['counts']['no_progress'] == 0
    assert correction_state(p)['counts']['coverage_gap'] == 3
    if when == 'before_submit':
        assert len(host.prompts) == 1 and checkpoint(p)['rounds'] == 1
        assert first['state'] == 'withdrawn' and 'delivered' not in first
        monkeypatch.setattr(p.coordinator, '_brief', old_brief)
    else:
        sent = json.loads(host.prompts[-1].split('\n')[-1])['progress_shadow']['assist']
        assert sent['causes'] == ['no_progress']
        assert first['delivered']['candidate_version'] == first['candidate_version']
        assert first['delivered']['control_eligible'] == (when == 'after_ack')
        assert first['reassessments'] == (1 if when == 'after_ack' else 0)
        assert first['state'] == ('delivered' if when == 'after_ack' else 'withdrawn')
        monkeypatch.setattr(host, 'start_turn', old_start)
        host.finish()
    next_turn(p)
    if when == 'after_ack':
        assert row(p)['state'] == 'paused' and len(correction_state(p)['assist']) == 1
    else:
        assert row(p)['state'] == 'active'
        assert notice(p)['state'] == 'delivered' and notice(p)['causes'] == ['coverage_gap']
        assert notice(p)['reassessments'] == 1
        assert correction_state(p)['assist'][0]['snapshot'] == first['snapshot']
