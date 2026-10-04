"""Finite SQLite polling/report checks; no native or scientific execution."""
import hashlib
import json
import sqlite3
from types import SimpleNamespace

import pytest

from scripts import accept_b6, acceptance_native_cases as native
from scripts.b6_evidence import (accepted_case_runs, accepted_goal_loop, case_delivery_ready,
    read, sealed_outputs, token_totals, usage_report, write)


@pytest.fixture
def scoped_poll(tmp_path):
    target = tmp_path/'case'
    journey = target/'journey-1'
    logs = journey/'logs'
    logs.mkdir(parents=True)
    database = target/'state/database'
    database.mkdir(parents=True)
    goal = dict(artifact_id='goal', sha256='a'*64, kind='source_text', schema_id='opaque')
    cp = dict(current_loop_id='loop', loop_authorizations={'loop':{}}, started_at='2026-10-04T00:00:00Z', admissions={}, usage_records={},
        native_completion='completed', turn_id=None)
    control = dict(instance_id='instance', objective_name='objective', objective_ref_json=json.dumps(goal),
        checkpoint_json=json.dumps(cp), state='active', reason='host_active', mode='background', host_json=None)
    with sqlite3.connect(database/'scheduler-bindings.sqlite3') as db:
        db.executescript('CREATE TABLE scheduler_instances(instance_id,name); '
            'CREATE TABLE scheduler_bindings(instance,namespace,name,object_id); '
            'CREATE TABLE scheduler_progression(instance_id,objective_name,objective_ref_json,checkpoint_json,state,reason,mode,host_json);')
        db.execute('INSERT INTO scheduler_instances VALUES(?,?)', ('instance','chosen'))
        db.execute('INSERT INTO scheduler_bindings VALUES(?,?,?,?)', ('instance','artifact','objective','goal'))
        db.execute('INSERT INTO scheduler_progression VALUES(?,?,?,?,?,?,?,?)', tuple(control.values()))
    with sqlite3.connect(database/'runs.sqlite3') as db:
        db.executescript('CREATE TABLE runs(run_id,instance_id,state,output_ref_json); '
            'CREATE TABLE worker_connections(run_id,thread_id); '
            'CREATE TABLE worker_participants(run_id,name,platform_session,owner_thread,thread_id,admitted_at,released_at);')
    write(journey/'loop-authorization.json', dict(id='loop', objective_name='objective'))
    case = dict(scenario='autonomous', multi_task=True, instance='chosen', objective='fixture', text='Finite scope.',
        max_observed_runs=3, progression=dict(max_rounds=8), poll_seconds=0, requires=['sealed_delivery'])
    write(target/'acceptance-case.json', dict(case, baseline_digest='baseline', conditions_digest='conditions'))
    host = object.__new__(native.NativeCaseJourney)
    host.root, host.instance, host.logdir = target, 'instance', logs
    host.case_config = case
    host.limits, host.resources = dict(log_bytes=8388608), dict(protocol_frame_bytes=1048576)
    host.initialize_host = lambda **kw: dict(state='active')
    host.await_loop_authorization = lambda *a, **kw: None
    host.status = lambda *a, **kw: None
    host.call = lambda *a, **kw: {}
    host.save_usage = lambda: None
    def row():
        with sqlite3.connect(database/'scheduler-bindings.sqlite3') as db:
            db.row_factory = sqlite3.Row
            return dict(db.execute('SELECT * FROM scheduler_progression').fetchone())
    host.row = row
    return SimpleNamespace(host=host, cp=cp, goal=goal, root=tmp_path, target=target, journey=journey,
        database=database, manifest=dict(config=dict(instance='chosen', cases={'case':case}, quality={'fixture':[]})))


def seed_terminal_attempts(f):
    raw = b'{"summary":"Bounded valid delivery; scientific effect is not graded."}'
    sha = hashlib.sha256(raw).hexdigest()
    path = f.target/'state/artifacts/sha256'/sha[:2]/sha[2:]
    path.parent.mkdir(parents=True)
    path.write_bytes(raw)
    ref = json.dumps(dict(artifact_id='result', sha256=sha, kind='report', schema_id='fixture'))
    values = [('ours-failed','instance','failed',None), ('ours-success','instance','completed',ref),
        ('foreign-instance','other','failed',None), ('old-goal','instance','failed',None),
        ('old-loop','instance','failed',None), ('interactive','instance','failed',None)]
    with sqlite3.connect(f.database/'runs.sqlite3') as db:
        db.executemany('INSERT INTO runs VALUES(?,?,?,?)', values)
        db.executemany('INSERT INTO worker_connections VALUES(?,?)', [(v[0],v[0]+'-worker') for v in values])
    def usage(thread, amount, loop='loop', **kw):
        return dict(thread_id=thread, role='worker', owner='instance', loop_id=loop,
            counted_tokens=dict(input_tokens=amount, cached_input_tokens=0, output_tokens=1), has_gaps=False, **kw)
    for identity in ('ours-failed','ours-success','old-goal','old-loop','interactive'):
        f.cp['admissions'][identity] = dict(run_id=identity, state='accepted', loop_id='old' if identity=='old-loop' else 'loop',
            objective_ref=dict(f.goal, artifact_id='old-goal') if identity=='old-goal' else f.goal,
            **(dict(interactive_session_id='human') if identity=='interactive' else {}))
    f.cp['usage_records'] = {'root':dict(usage('root',100), role='root'),
        'ours-failed-worker':usage('ours-failed-worker',10), 'ours-success-worker':usage('ours-success-worker',20),
        'old-goal-worker':usage('old-goal-worker',1000), 'old-loop-worker':usage('old-loop-worker',1000,'old'),
        'interactive-worker':usage('interactive-worker',1000,interactive_session_id='human')}
    with sqlite3.connect(f.database/'scheduler-bindings.sqlite3') as db:
        db.execute("UPDATE scheduler_progression SET checkpoint_json=?,state='stopped',reason='goal_completed'", (json.dumps(f.cp),))


def test_sql_poll_and_report_share_exact_scope_and_keep_failed_cost(scoped_poll):
    f = scoped_poll
    ticks, costs = [], []
    def pump():
        assert not ticks, 'finite fixture must finish at the first completed observation'
        ticks.append(True)
        seed_terminal_attempts(f)
    f.host.pump = pump
    def budget(workers, helpers, **kw):
        costs.append(token_totals(usage_report(f.journey, workers, helpers, f.host.row(), candidate=f.target,
            exact_scope=f.host._case_run_scope)))
    f.host.check_case_budget = budget
    f.host.run_case()
    assert costs[-1] == dict(total_tokens=133, uncached_tokens=133)
    assert {v['run_id'] for v in read(f.journey/'run-outcomes.json')} == {'ours-failed','ours-success'}
    assert {v['run_id'] for v in read(f.journey/'participants.json')['workers']} == {'ours-failed','ours-success'}
    assert [v['run_id'] for v in read(f.journey/'sealed-evidence.json')] == ['ours-success']
    write(f.journey/'resource.json', dict(returncode=0, stop_reason='exited'))
    write(f.root/'case.exit.json', dict(returncode=0))
    report = accept_b6.result(f.root, f.manifest, 'case')
    assert {v['run_id'] for v in report['run_outcomes']} == {'ours-failed','ours-success'}
    assert token_totals(report['usage']) == costs[-1]
    assert report['checks']['sealed_delivery'] == 'passed'
    assert len(report['review_template']['decisions']) == 0  # no scientific score is supplied


@pytest.mark.parametrize('damage', ['unknown_usage','unaccepted_usage','wrong_usage_role','changed_goal','changed_loop','missing_run'])
def test_scope_and_unconfirmed_usage_cannot_be_filtered_into_success(scoped_poll, damage):
    from scripts.b6_evidence import participants
    f = scoped_poll
    seed_terminal_attempts(f)
    control = f.host.row()
    scope = accepted_goal_loop(control)[0]
    runs = accepted_case_runs(f.target, control, max_runs=3, expected_scope=scope)
    workers, helpers = participants(f.target, [v['run_id'] for v in runs])
    cp = json.loads(control['checkpoint_json'])
    if damage == 'unknown_usage':cp['usage_records']['unbound'] = dict(cp['usage_records']['ours-failed-worker'], thread_id='unbound')
    elif damage == 'unaccepted_usage':cp['admissions']['old-goal']['state'] = 'prepared'
    elif damage == 'wrong_usage_role':cp['usage_records']['old-goal-worker']['role'] = 'helper'
    elif damage == 'changed_goal':control['objective_ref_json'] = json.dumps(dict(f.goal,artifact_id='new-goal'))
    elif damage == 'changed_loop':cp['current_loop_id'] = 'new-loop'
    else:
        with sqlite3.connect(f.database/'runs.sqlite3') as db:db.execute("UPDATE runs SET instance_id='other' WHERE run_id='ours-failed'")
    control['checkpoint_json'] = json.dumps(cp)
    expected = {'unknown_usage':'identity_unbound', 'unaccepted_usage':'identity_unbound', 'wrong_usage_role':'identity_conflict',
        'changed_goal':'goal_loop_changed', 'changed_loop':'goal_loop_changed', 'missing_run':'admitted_run_scope_mismatch'}
    with pytest.raises(ValueError, match=expected[damage]):
        if damage in {'unknown_usage','unaccepted_usage','wrong_usage_role'}:
            usage_report(f.journey, workers, helpers, control, candidate=f.target, exact_scope=scope)
        else:accepted_case_runs(f.target, control, max_runs=3, expected_scope=scope)


@pytest.mark.parametrize('state,ready', [('failed',True),('timed_out',True),('cancelled',True),('queued',False),('running',False)])
def test_exploration_requires_success_and_all_attempts_terminal(scoped_poll, state, ready):
    f = scoped_poll
    seed_terminal_attempts(f)
    control = f.host.row()
    runs = accepted_case_runs(f.target, control, max_runs=3)
    next(v for v in runs if v['run_id']=='ours-failed')['state'] = state
    assert case_delivery_ready(runs, exploratory=True) is ready
    assert not case_delivery_ready([dict(run_id='only-failure',state=state)], exploratory=True)
    assert not case_delivery_ready(runs, exploratory=False)
    if not ready:
        with pytest.raises(ValueError, match='required_sealed_delivery_missing'):sealed_outputs(f.target,runs,exploratory=True)
