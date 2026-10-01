"""HTTP recovery selects the exact paused background goal after manual work."""
import json
import re
from html import unescape

import pytest

from tests.operations.test_human_progress_continuation import (
    human_ui, paused, independent, submit, save_checkpoint,
)
from tests.operations.test_progression import progression, row, checkpoint
from tests.operations.test_scientific_progress import active, finish, request
from tests.operations.test_m6a_direct_instance_management import _request


def enter_manual(ui, target):
    p = ui.p
    if target != 'goal':
        p.root.call_tool('progression_message', dict(name=target, text='A separate exact manual goal.'))
    assert independent(ui, target) == 303
    finish(p, p.root, 'manual-complete')
    assert submit(ui, command='pause') == 303


def background_form(ui, target='goal'):
    code, _, raw = _request(ui.base, 'GET', ui.path)
    assert code == 200
    page = raw.decode()
    forms = re.findall(r"<form[^>]*data-background-continue[^>]*>.*?</form>", page, re.S)
    values = [dict((unescape(name), unescape(value)) for name, value in re.findall(
        r"name='([^']+)' value='([^']*)'", form)) for form in forms]
    chosen = [form for form in values if form.get('objective_name') == target]
    assert len(chosen) == 1, 'The UI must offer an explicit recovery of the exact paused background goal.'
    assert '恢复后台目标' in page and '剩余任务' in page and 'coverage_gap' in page
    return chosen[0]


@pytest.mark.parametrize('target', ['goal', 'manual-goal'])
def test_http_manual_scope_can_recover_exact_original_background_goal(human_ui, target):
    ui, p = human_ui, human_ui.p
    bindings = p.runtime.scheduler_bindings
    original = row(p)
    objective = json.loads(original['objective_ref_json'])
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    ref = ArtifactRef.model_validate(objective)
    trigger = bindings.progress_shadow(instance_id=p.instance, objective_ref=ref)['notices'].copy()
    enter_manual(ui, target)
    before = checkpoint(p)
    manual_scope = before['observation_scope_id']
    manual_ref = ArtifactRef.model_validate_json(row(p)['objective_ref_json'])
    manual_state = bindings.progress_shadow(instance_id=p.instance, objective_ref=manual_ref)
    for command in ('start', 'resume', 'takeover'):
        args = dict(command=command, mode='background')
        if command == 'start':
            args['objective_name'] = 'goal'
        assert submit(ui, **args) == 409
    form = background_form(ui)
    assert _request(ui.base, 'POST', '/instances/progression', form=form)[0] == 303
    assert row(p)['mode'] == 'background' and row(p)['state'] == 'pending'
    assert row(p)['objective_ref_json'] == original['objective_ref_json']
    current = checkpoint(p)
    assert 'observation_scope_id' not in current
    for key in ('rounds', 'attempts', 'probes', 'started_at', 'budget', 'admissions',
                'interactive_sessions', 'interactive_usage_records'):
        assert current.get(key) == before.get(key)
    recovered = bindings.progress_shadow(instance_id=p.instance, objective_ref=ref)
    assert recovered['notices'] == trigger
    assert recovered['window_starts']['background'] == 3
    assert bindings.progress_shadow(instance_id=p.instance, objective_ref=manual_ref)[
        'window_starts'][manual_scope] == manual_state['window_starts'][manual_scope]
    root = active(p)
    finish(p, root, 'background-recovered-task')
    assert checkpoint(p)['admissions']['background-recovered-task'].get('interactive_session_id') is None
    assert root.call_tool('run_status', dict(name='background-recovered-task'))['state'] == 'completed'


def test_background_confirmation_rejects_wrong_target_forgery_stale_and_cross_instance(human_ui):
    ui, p = human_ui, human_ui.p
    enter_manual(ui, 'manual-goal')
    form = background_form(ui)
    before = row(p)
    for changes in (dict(objective_name='manual-goal'), dict(confirmation_binding='forged'),
                    dict(instance_id='wrong-instance'), dict(csrf='wrong-csrf')):
        assert _request(ui.base, 'POST', '/instances/progression', form=dict(form, **changes))[0] in {403, 409}
        assert row(p) == before
    bindings = p.runtime.scheduler_bindings
    other = bindings.create_instance(name='other-recovery-instance', title='Other', objective='Separate scope')
    bindings.bind_session(session_key=p.user, instance_id=other.instance_id)
    assert _request(ui.base, 'POST', '/instances/progression', form=form)[0] == 409
    assert row(p) == before
    bindings.bind_session(session_key=p.user, instance_id=p.instance)
    p.root.call_tool('progression_message', dict(name='recovery.context', text='A new exact control snapshot.'))
    changed = row(p)
    assert _request(ui.base, 'POST', '/instances/progression', form=form)[0] == 409
    assert row(p) == changed


@pytest.mark.parametrize('barrier', ['native', 'budget', 'active_work'])
def test_background_recovery_keeps_unknown_budget_and_actual_work_barriers(human_ui, barrier):
    ui, p = human_ui, human_ui.p
    if barrier == 'active_work':
        assert independent(ui) == 303
        p.root.call_tool('operation_invoke', request('still-accepted'))
        assert submit(ui, command='pause') == 303
    else:
        enter_manual(ui, 'goal')
        if barrier == 'native':
            save_checkpoint(p, phase='prepared', turn_id=None, fault_class='outcome_unknown')
            with p.runtime.scheduler_bindings._connect() as db:
                db.execute('UPDATE scheduler_progression SET host_json=? WHERE instance_id=?',
                    (json.dumps(dict(platform_session='unknown-native', thread_id='unknown-thread')), p.instance))
        else:
            limits = json.loads(row(p)['config_json'])['effective']['progression']
            save_checkpoint(p, rounds=limits['max_rounds'])
    form = background_form(ui)
    before = row(p)
    assert _request(ui.base, 'POST', '/instances/progression', form=form)[0] == 409
    assert row(p) == before
    if barrier == 'active_work':
        assert p.root.call_tool('run_status', dict(name='still-accepted'))['state'] == 'queued'


def test_background_confirmation_binds_trigger_and_consumed_position(human_ui):
    """Stored late facts test form freshness without claiming foreground receipt coverage."""
    from scidiscovery.artifact_agent.service.scientific_progress import _update_fact
    ui, p = human_ui, human_ui.p
    enter_manual(ui, 'goal')
    bindings = p.runtime.scheduler_bindings
    form = background_form(ui)
    with bindings._connect() as db:
        record = db.execute('SELECT goal_key,state_json FROM scheduler_progress_shadow WHERE instance_id=?',
            (p.instance,)).fetchone()
        state = json.loads(record['state_json'])
        state['notices'].append(dict(state['notices'][0], id='late-trigger-fixture'))
        db.execute('UPDATE scheduler_progress_shadow SET state_json=? WHERE instance_id=? AND goal_key=?',
            (json.dumps(state), p.instance, record['goal_key']))
    before = row(p)
    assert _request(ui.base, 'POST', '/instances/progression', form=form)[0] == 409
    assert row(p) == before
    form = background_form(ui)
    with bindings._connect() as db:
        delivery = dict(db.execute('SELECT * FROM scheduler_terminal_deliveries WHERE instance_id=? LIMIT 1',
            (p.instance,)).fetchone())
        fact = json.loads(db.execute('SELECT fact_json FROM scheduler_progress_facts WHERE instance_id=? AND run_id=?',
            (p.instance, delivery['run_id'])).fetchone()['fact_json'])
        delivery.update(sequence=4, run_id='late-consumed-fixture', task_name='late-consumed-fixture')
        db.execute('INSERT INTO scheduler_terminal_deliveries VALUES(' + ','.join('?' for _ in delivery) + ')',
            tuple(delivery.values()))
        _update_fact(db, p.instance, delivery['goal_key'], delivery['run_id'], dict(fact, sequence=4))
    assert _request(ui.base, 'POST', '/instances/progression', form=form)[0] == 409
    assert row(p) == before


def test_background_target_prefers_verified_original_name_and_diagnoses_missing_binding(human_ui):
    ui, p = human_ui, human_ui.p
    enter_manual(ui, 'manual-goal')
    bindings = p.runtime.scheduler_bindings
    identity = bindings.resolve(instance=p.instance, namespace='artifact', name='goal')
    bindings.bind(instance=p.instance, namespace='artifact', name='aaa.alternate', object_id=identity)
    options = bindings.background_continuations(instance_id=p.instance, session_key=p.user)
    assert [item.get('objective_name') for item in options] == ['goal']
    form = background_form(ui)
    with bindings._connect() as db:
        db.execute("DELETE FROM scheduler_bindings WHERE instance=? AND namespace='artifact' AND object_id=?",
            (p.instance, identity))
    before = row(p)
    code, _, raw = _request(ui.base, 'GET', ui.path)
    assert code == 200 and '原后台目标绑定缺失或已改变' in raw.decode()
    assert _request(ui.base, 'POST', '/instances/progression', form=form)[0] == 409
    assert row(p) == before
