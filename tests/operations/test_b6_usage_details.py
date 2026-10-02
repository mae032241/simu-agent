"""Acceptance accounting reads the production detail ledger, without native work."""
import json
import sqlite3
import threading
import time

import pytest

from scripts.b6_evidence import budget_assessment, control_rows, token_totals, usage_report, write
from scripts.acceptance_native_cases import NativeCaseJourney
from scidiscovery.agent_execution_settings import parse_settings
from scidiscovery.artifact_agent.service.progression_records import DETAIL_SCHEMA, store_checkpoint


@pytest.fixture
def ledger(tmp_path):
    database = tmp_path/'state/database'
    database.mkdir(parents=True)
    journey = tmp_path/'journey-1'
    journey.mkdir()
    path = database/'scheduler-bindings.sqlite3'
    settings = parse_settings({}).model_dump(mode='json')
    config = dict(effective=settings)
    def usage(thread, role, loop='current', **changes):
        return dict(thread_id=thread, role=role, owner='instance', loop_id=loop,
            counted_tokens=dict(input_tokens=100, cached_input_tokens=80, output_tokens=5),
            has_gaps=False, **changes)
    checkpoint = dict(current_loop_id='current', started_at='2026-10-02T00:00:00Z',
        loop_authorizations={'current':dict(config=config), 'old':dict(config=config)},
        admissions={'task':dict(run_id='run', loop_id='current'),
                    'manual':dict(run_id='manual', loop_id='current', interactive_session_id='human'),
                    'old':dict(run_id='old', loop_id='old')},
        usage_records={'root':usage('root','root'), 'worker':usage('worker','worker'),
                       'manual':usage('manual','worker', interactive_session_id='human'),
                       'old':usage('old','root','old')},
        usage_summary=dict(coverage='observed', groups={'root':dict(input_tokens=999999999)}),
        decision_snapshot={'private':'omitted snapshot'}, interactive_usage_records={'human':usage('human','root')})
    with sqlite3.connect(path) as db:
        db.executescript('CREATE TABLE scheduler_instances(instance_id TEXT PRIMARY KEY); '
            'CREATE TABLE scheduler_progression(instance_id TEXT PRIMARY KEY,checkpoint_json,config_json,host_json,state,reason);')
        db.executescript(DETAIL_SCHEMA)
        db.execute('INSERT INTO scheduler_instances VALUES(?)', ('instance',))
        db.execute('INSERT INTO scheduler_instances VALUES(?)', ('other',))
        db.execute('INSERT INTO scheduler_progression VALUES(?,?,?,?,?,?)',
            ('instance','{}',json.dumps(config),None,'paused','goal_completed'))
        compact = store_checkpoint(db, 'instance', checkpoint, replace=True)
        db.execute('UPDATE scheduler_progression SET checkpoint_json=?', (compact,))
        db.execute('INSERT INTO scheduler_progression_details VALUES(?,?,?,?)',
            ('other','usage_records','other',json.dumps(usage('other','root'))))
    write(journey/'loop-authorization.json', {'id':'current'})
    write(journey/'started-threads.json', [])
    write(journey/'usage.json', {'threads':{'worker':dict(inputTokens=10000,cachedInputTokens=0,outputTokens=10),
                                          'other':dict(inputTokens=10000,cachedInputTokens=0,outputTokens=10)}})
    workers = [dict(run_id=run, thread_id=thread) for run,thread in
               [('run','worker'),('old','old-worker'),('manual','manual')]]
    return tmp_path, path, journey, workers


def accounting(ledger):
    root, _, _, _ = ledger
    return control_rows(root, 'SELECT * FROM scheduler_progression WHERE instance_id=?',
        ('instance',), accounting=True, loop_id='current')[0]


def budget_host(ledger, deadline_seconds=10):
    root, _, journey, _ = ledger
    host = NativeCaseJourney.__new__(NativeCaseJourney)
    host.root, host.logdir, host.instance = root, journey/'logs', 'instance'
    host.phase_deadline = time.monotonic()+deadline_seconds
    host.case_started_at = time.monotonic()
    host.case_config = dict(scenario='autonomous', budget=dict(sample_seconds=5,
        session=dict(total_tokens=1000, uncached_tokens=1000, execution_seconds=10)))
    host.case_checks, host.started_threads = {}, set()
    host.save_usage = lambda: None
    return host


def test_live_budget_and_offline_report_share_scoped_externalized_records(ledger):
    root, path, journey, workers = ledger
    with sqlite3.connect(path) as db:
        raw = json.loads(db.execute('SELECT checkpoint_json FROM scheduler_progression').fetchone()[0])
    assert 'usage_records' not in raw and raw['detail_collections']['usage_records'] == 4
    row = accounting(ledger)
    checkpoint = json.loads(row['checkpoint_json'])
    assert set(checkpoint['loop_authorizations']) == {'current'}
    assert set(checkpoint['usage_records']) == {'root','worker','manual'}
    assert 'decision_snapshot' not in checkpoint and 'interactive_usage_records' not in checkpoint
    report = usage_report(journey, workers, [], row)
    assert report['coverage'] == 'observed'
    assert set(report['groups']) == {'root','worker'}
    assert report['groups']['worker']['observed_threads'] == 1
    assert token_totals(report) == dict(total_tokens=210, uncached_tokens=50)
    assert report['accounting_scope']['source'] == 'scheduler_progression_details'
    host = budget_host(ledger)
    host.check_case_budget(workers, [], final=True)
    final = json.loads((journey/'budget-final.json').read_text())
    assert final['status'] == 'passed' and final['observed']['total_tokens'] == 210
    assert token_totals(usage_report(journey, workers, [], host.row())) == token_totals(report)
    with sqlite3.connect(path) as db:
        assert json.loads(db.execute('SELECT checkpoint_json FROM scheduler_progression').fetchone()[0]) == raw
        for replace in (False, True):
            with pytest.raises(ValueError, match='Read-only accounting'):
                store_checkpoint(db, 'instance', checkpoint, replace=replace)


@pytest.mark.parametrize('change,expected', [
    ('missing','partial'), ('gap','partial'), ('role','conflict'),
    ('owner','unbound'), ('identity','unbound'), ('cache','invalid')])
def test_detail_gaps_and_conflicting_identity_cannot_confirm_budget(ledger, change, expected):
    _, path, journey, workers = ledger
    with sqlite3.connect(path) as db:
        record = json.loads(db.execute("SELECT record_json FROM scheduler_progression_details "
            "WHERE instance_id='instance' AND collection='usage_records' AND record_key='worker'").fetchone()[0])
        if change == 'missing':
            db.execute("DELETE FROM scheduler_progression_details WHERE instance_id='instance' "
                "AND collection='usage_records' AND record_key='worker'")
            raw = json.loads(db.execute('SELECT checkpoint_json FROM scheduler_progression').fetchone()[0])
            raw['detail_collections']['usage_records'] -= 1
            db.execute('UPDATE scheduler_progression SET checkpoint_json=?', (json.dumps(raw),))
        else:
            if change == 'gap': record['has_gaps'] = True
            if change == 'role': record['role'] = 'root'
            if change == 'owner': record['owner'] = 'other'
            if change == 'identity': record['thread_id'] = 'other'
            if change == 'cache': record['counted_tokens']['cached_input_tokens'] = 101
            db.execute("UPDATE scheduler_progression_details SET record_json=? WHERE instance_id='instance' "
                "AND collection='usage_records' AND record_key='worker'", (json.dumps(record),))
    if expected == 'partial':
        report = usage_report(journey, workers, [], accounting(ledger))
        assert report['coverage'] == 'partial' and report['groups']['worker']['missing_threads'] == 1
        assert budget_assessment(report, {'total_tokens':1000}, 1)['status'] == 'not_observed'
        if change == 'missing': assert report['groups']['worker']['input_tokens'] is None
    else:
        with pytest.raises(ValueError, match=expected):
            token_totals(usage_report(journey, workers, [], accounting(ledger)))


def test_missing_detail_reference_and_changed_frozen_loop_fail_closed(ledger):
    root, path, _, _ = ledger
    with sqlite3.connect(path) as db:
        db.execute("DELETE FROM scheduler_progression_details WHERE instance_id='instance' "
            "AND collection='usage_records' AND record_key='worker'")
    with pytest.raises(ValueError, match='differ from checkpoint reference'):
        accounting(ledger)
    with pytest.raises(ValueError, match='research_loop_changed'):
        control_rows(root, accounting=True, loop_id='old')


def test_sqlite_contention_and_query_work_have_finite_read_deadlines(ledger):
    root, path, _, _ = ledger
    with sqlite3.connect(path) as writer:
        writer.execute('BEGIN EXCLUSIVE')
        started = time.monotonic()
        with pytest.raises(sqlite3.OperationalError, match='locked'):
            accounting(ledger)
        assert 1.8 < time.monotonic()-started < 2.7
    # A real SQL loop must obey the supplied absolute deadline too.
    with pytest.raises(sqlite3.OperationalError, match='interrupted'):
        control_rows(root, 'WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n) SELECT sum(x) FROM n',
            deadline=time.monotonic()+.02)


def test_budget_entry_retries_short_detail_writer_lock_without_replaying_journey(ledger):
    _, path, journey, workers = ledger
    host = budget_host(ledger)
    with sqlite3.connect(path, check_same_thread=False) as writer:
        writer.execute('BEGIN EXCLUSIVE')
        writer.execute("UPDATE scheduler_progression_details SET record_json=record_json "
            "WHERE collection='usage_records'")
        release = threading.Timer(.25, writer.commit)
        started = time.monotonic()
        release.start()
        try:
            host.check_case_budget(workers, [], final=True)
        finally:
            release.join(timeout=1)
        assert .2 < time.monotonic()-started < 1
    final = json.loads((journey/'budget-final.json').read_text())
    assert final['status'] == 'passed' and final['observed']['total_tokens'] == 210


def test_budget_entry_sustained_lock_keeps_phase_deadline_and_no_partial_report(ledger):
    _, path, journey, workers = ledger
    host = budget_host(ledger, deadline_seconds=.3)
    deadline = host.phase_deadline
    with sqlite3.connect(path) as writer:
        writer.execute('BEGIN EXCLUSIVE')
        started = time.monotonic()
        with pytest.raises(sqlite3.OperationalError, match='locked'):
            host.check_case_budget(workers, [], final=True)
        assert .2 < time.monotonic()-started < .7
    assert host.phase_deadline == deadline
    assert not (journey/'budget-final.json').exists() and host.case_checks == {}


@pytest.mark.parametrize('failure', ['sql','interrupted','identity'])
def test_permanent_sql_interruption_and_identity_errors_are_not_retried(ledger, monkeypatch, failure):
    from scripts import b6_evidence
    root, _, _, _ = ledger
    connects = []
    connect = b6_evidence.connect_database
    def counted_connect(*args, **kwargs):
        connects.append(1)
        return connect(*args, **kwargs)
    monkeypatch.setattr(b6_evidence, 'connect_database', counted_connect)
    if failure == 'identity':
        with pytest.raises(ValueError, match='research_loop_changed'):
            control_rows(root, accounting=True, loop_id='other')
    elif failure == 'sql':
        with pytest.raises(sqlite3.OperationalError, match='no such table'):
            control_rows(root, 'SELECT * FROM missing_table')
    else:
        with pytest.raises(sqlite3.OperationalError, match='interrupted'):
            control_rows(root, 'WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n) SELECT sum(x) FROM n',
                deadline=time.monotonic()+.02)
    assert len(connects) == 1
