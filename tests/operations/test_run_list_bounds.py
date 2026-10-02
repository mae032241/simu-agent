"""Bounded Run pages use actual storage and the published Root/MCP route."""
import json
import os
import sqlite3
from contextlib import closing
from copy import copy
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter
from scidiscovery.artifact_agent.service.runs import RunNotFound, RunStateConflict
from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerNameNotFound
from tests.operations.test_local_worker_contracts import _system, _invoke, _worker, _write_result
from tests.operations.test_unified_mcp import call, result


def collection(tmp_path, count):
    catalog, runtime, instance, root = _system(tmp_path)
    _invoke(root, 'task-0000')
    worker = _worker(catalog, runtime)
    worker.call_tool('worker_open_assignment', {})
    _write_result(worker)
    worker.call_tool('worker_submit_result', {})
    bindings, runs = runtime.scheduler_bindings, runtime.runs
    ids, states, clocks = {}, {}, {}
    with runs._connect() as db:
        original = dict(db.execute('SELECT * FROM runs').fetchone())
        columns = list(original)
        for index in range(count):
            name = f'task-{index:04d}'
            identity = original['run_id'] if index == 0 else 'run_'+f'{index:032x}'
            state = 'failed' if index == 0 else 'completed'
            clock = f'2026-01-01T00:{index//180:02d}:{(index//3)%60:02d}Z'
            value = dict(original, run_id=identity, state=state, created_at=clock,
                output_binding_name=name+'.output', output_logical_name=name+'.output')
            if index:
                db.execute('INSERT INTO runs ('+','.join(columns)+') VALUES ('+
                    ','.join('?' for _ in columns)+')', [value[key] for key in columns])
            else:
                db.execute('UPDATE runs SET state=?,created_at=? WHERE run_id=?', (state,clock,identity))
            ids[name], states[name], clocks[name] = identity, state, clock
    with bindings._connect() as db:
        for name, identity in ids.items():
            if name != 'task-0000':
                db.execute('INSERT INTO scheduler_bindings VALUES(?,?,?,?,?,?,?,?)',
                    (instance.instance_id,'run',name,name,1,identity,None,clocks[name]))
            else:
                db.execute('UPDATE scheduler_bindings SET created_at=? WHERE instance=? AND namespace=? AND name=?',
                    (clocks[name],instance.instance_id,'run',name))
    # Match the mixed direction SQL ordering exactly, including timestamp ties.
    expected = sorted(ids, key=lambda name: name)
    expected.sort(key=lambda name: clocks[name], reverse=True)
    return SimpleNamespace(root=root, runtime=runtime, bindings=bindings, runs=runs,
        instance=instance.instance_id, ids=ids, states=states, expected=expected,
        gateway=UnifiedMCPRouter(root, worker_backend='local'))


def observe_reads(system, monkeypatch):
    counts = dict(full_runs=0, bindings_materialized=0, payload_reads=0, max_identity_rows=0,
                  diagnostic_rows=0)
    statuses, bindings = system.runs._statuses_from_rows, system.bindings.list
    connect = system.runs._connect
    class Cursor:
        def __init__(self, cursor, sql): self.cursor, self.sql = cursor, sql
        def __getattr__(self, name): return getattr(self.cursor, name)
        def fetchall(self):
            values = self.cursor.fetchall()
            if self.sql.startswith('SELECT b.name,b.object_id'):
                counts['max_identity_rows'] = max(counts['max_identity_rows'], len(values))
            if self.sql.startswith('SELECT activity,diagnostic_json'):
                counts['diagnostic_rows'] += len(values)
            return values
        def fetchone(self):
            value = self.cursor.fetchone()
            if self.sql.startswith('SELECT activity,diagnostic_json') and value is not None:
                counts['diagnostic_rows'] += 1
            return value
    class Connection:
        def __init__(self): self.connection = connect()
        def __getattr__(self, name): return getattr(self.connection, name)
        def __enter__(self): self.connection.__enter__(); return self
        def __exit__(self, *args): return self.connection.__exit__(*args)
        def execute(self, sql, *args): return Cursor(self.connection.execute(sql, *args), sql)
    def counted_statuses(rows):
        rows = list(rows)
        counts['full_runs'] += len(rows)
        return statuses(rows)
    def counted_bindings(**arguments):
        values = bindings(**arguments)
        if arguments['namespace'] == 'run': counts['bindings_materialized'] += len(values)
        return values
    def forbidden_payload(*arguments, **keywords):
        counts['payload_reads'] += 1
        pytest.fail('summary must not read scientific output bodies')
    monkeypatch.setattr(system.runs, '_statuses_from_rows', counted_statuses)
    monkeypatch.setattr(system.runs, '_connect', Connection)
    monkeypatch.setattr(system.bindings, 'list', counted_bindings)
    monkeypatch.setattr(system.runtime.artifacts, 'read', forbidden_payload)
    return counts


def metrics(label, value):
    directory = os.environ.get('SCID_TEST_LOG_DIR')
    if directory:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        (path/(label+'.log')).write_text(json.dumps(value, sort_keys=True)+'\n')


def test_sparse_state_reads_only_the_matching_page(tmp_path, monkeypatch):
    system = collection(tmp_path, 30)
    counts = observe_reads(system, monkeypatch)
    page = system.root.call_tool('run_list', dict(state='failed', limit=2))
    metrics('sparse-state', counts)
    assert [item['name'] for item in page['runs']] == ['task-0000']
    assert counts['full_runs'] <= 2, counts
    assert counts['bindings_materialized'] == 0, counts
    assert page['next_before'] is None


@pytest.mark.parametrize('count', [30,100,300])
def test_root_and_mcp_traverse_bounded_pages_with_timestamp_ties(tmp_path, monkeypatch, count):
    system = collection(tmp_path, count)
    counts = observe_reads(system, monkeypatch)
    cursor, names, pages, peak_bytes = None, [], 0, 0
    while True:
        before = counts['full_runs']
        query = dict(limit=7, view='summary', **({'before':cursor} if cursor else {}))
        page = result(call(system.gateway, 'run_list', query)) if pages % 2 else system.root.call_tool('run_list', query)
        assert counts['full_runs']-before <= 7
        assert counts['max_identity_rows'] <= 8
        peak_bytes = max(peak_bytes, len(json.dumps(page, ensure_ascii=False).encode()))
        names.extend(item['name'] for item in page['runs'])
        pages += 1
        cursor = page['next_before']
        if cursor is None: break
        assert cursor == page['runs'][-1]['name'] and pages <= count
    assert names == system.expected and len(set(names)) == count
    assert counts['full_runs'] == count and counts['bindings_materialized'] == counts['payload_reads'] == 0
    assert peak_bytes < 16384
    metrics(f'pages-{count}', dict(**counts, tasks=count, pages=pages, peak_response_bytes=peak_bytes))


def test_cursor_scope_state_filter_and_missing_binding_are_explicit(tmp_path):
    system = collection(tmp_path, 30)
    with pytest.raises(SchedulerNameNotFound):
        system.root.call_tool('run_list', dict(before='unknown'))
    # A cursor of another state retains same-timestamp/name ordering.
    page = system.root.call_tool('run_list', dict(state='completed', before='task-0000'))
    assert [item['name'] for item in page['runs']] == ['task-0001','task-0002'] and page['next_before'] is None
    other = system.bindings.create_instance(name='other', title='Other', objective='Isolation')
    facade = copy(system.root.facade)
    facade.instance = other.instance_id
    foreign = RootMCPRouter(facade)
    assert foreign.call_tool('run_list', {}) == dict(runs=[],next_before=None)
    with pytest.raises(SchedulerNameNotFound): foreign.call_tool('run_list', dict(before='task-0000'))
    system.bindings.bind(instance=system.instance,namespace='run',name='broken',object_id='missing')
    with system.bindings._connect() as db:
        db.execute("UPDATE scheduler_bindings SET created_at='2099' WHERE name='broken'")
    with pytest.raises(RunNotFound): system.root.call_tool('run_list', dict(state='completed',limit=1))
    # A bound cursor is a position even if its old Run record is unavailable.
    assert len(system.root.call_tool('run_list', dict(before='broken',limit=3))['runs']) == 3
    with system.runs._connect() as db:
        db.execute('UPDATE runs SET instance_id=? WHERE run_id=?', (other.instance_id,system.ids['task-0000']))
    with system.bindings._connect() as db:
        db.execute("UPDATE scheduler_bindings SET object_id=? WHERE name='broken'", (system.ids['task-0000'],))
    with pytest.raises(RunStateConflict, match='another instance'):
        system.root.call_tool('run_list', dict(state='completed',limit=1))


def test_summary_does_not_materialize_execution_helper_activity_history(tmp_path, monkeypatch):
    system = collection(tmp_path, 30)
    identity = system.ids['task-0000']
    with system.runs._connect() as db:
        db.executemany('INSERT INTO run_activity(run_id,activity,recorded_at,diagnostic_json) VALUES(?,?,?,?)',
            [(identity,'helper_or_execution_activity','2026-01-01',json.dumps({'private':'x'*8192})) for _ in range(400)])
        for index in range(12):
            db.execute('INSERT INTO run_activity(run_id,activity,recorded_at,diagnostic_json) VALUES(?,?,?,?)',
                (identity,'output_rejected','2026-01-01',json.dumps({'category':'output_rejected','tool_name':str(index)})))
        db.execute('INSERT INTO run_activity(run_id,activity,recorded_at,diagnostic_json) VALUES(?,?,?,NULL)',
            (identity,'output_rejected','2026-01-01'))
    counts = observe_reads(system, monkeypatch)
    page = system.root.call_tool('run_list', dict(state='failed',limit=1))
    assert len(page['runs']) == 1 and counts['full_runs'] == 1
    assert counts['diagnostic_rows'] <= 11 and counts['payload_reads'] == 0
    metrics('activity-history', counts.copy())
    summary = system.runs.diagnostic_summary(system.runs.status(identity))
    assert summary['rejection_count'] == 13 and summary['latest_rejection'] is None
    assert [item['tool_name'] for item in summary['recent_errors']] == list(map(str,range(4,12)))
    with system.runs._connect() as db:
        system.runs._attach_scheduler(db)
        plan = [row['detail'] for row in db.execute('EXPLAIN QUERY PLAN SELECT b.name FROM '
            'scheduler_control.scheduler_bindings b WHERE b.instance=? AND b.namespace=? '
            'ORDER BY b.created_at DESC,b.name LIMIT 8', (system.instance,'run')).fetchall()]
    assert any('scheduler_bindings_page' in item for item in plan)
    metrics('query-plan', dict(binding_page=plan, limitation='Sparse states may scan more SQLite identities than returned rows.'))


def test_diagnostic_summary_keeps_one_snapshot_during_concurrent_append(tmp_path, monkeypatch):
    system = collection(tmp_path, 1)
    identity = system.ids['task-0000']
    insert = 'INSERT INTO run_activity(run_id,activity,recorded_at,diagnostic_json) VALUES(?,?,?,?)'
    def record(label):
        return (identity, 'output_rejected', '2026-01-01',
                json.dumps({'category':'output_rejected', 'tool_name':label}))
    with closing(system.runs._connect()) as db, db:
        assert db.execute('PRAGMA journal_mode').fetchone()[0] == 'delete'
        db.execute('DELETE FROM run_activity WHERE run_id=?', (identity,))
        db.execute(insert, record('old'))
    value = system.runs.status(identity)
    start, inserted, committed = Event(), Event(), Event()
    failures = []
    def append():
        try:
            assert start.wait(2)
            with closing(sqlite3.connect(system.runs.database_path, timeout=2)) as db:
                db.execute(insert, record('new'))
                inserted.set()
                db.commit()  # DELETE readers hold this commit until the snapshot closes.
                committed.set()
        except BaseException as error:
            failures.append(error)
            inserted.set()
    writer = Thread(target=append, daemon=True)
    connect = system.runs._connect
    triggered = False
    class CountCursor:
        def __init__(self, cursor): self.cursor = cursor
        def fetchone(self):
            result = self.cursor.fetchone()
            self.cursor.fetchone()  # Exhaust COUNT before starting the second connection.
            start.set()
            assert inserted.wait(2), 'writer did not execute its INSERT'
            assert not failures, failures
            # Allow an autocommit reader's writer to commit, but never wait for
            # a transactional reader's blocked commit before finishing its reads.
            committed.wait(0.1)
            return result
    class Connection:
        def __init__(self): self.connection = connect()
        def __getattr__(self, name): return getattr(self.connection, name)
        def __enter__(self): self.connection.__enter__(); return self
        def __exit__(self, *args): return self.connection.__exit__(*args)
        def execute(self, sql, *args):
            nonlocal triggered
            cursor = self.connection.execute(sql, *args)
            if sql.startswith('SELECT COUNT(*) FROM run_activity') and not triggered:
                triggered = True
                return CountCursor(cursor)
            return cursor
    monkeypatch.setattr(system.runs, '_connect', Connection)
    writer.start()
    try:
        snapshot = system.runs.diagnostic_summary(value)
    finally:
        start.set()
        writer.join(3)
    assert not writer.is_alive() and committed.is_set() and not failures, failures
    assert snapshot['rejection_count'] == 1
    assert snapshot['latest_rejection']['tool_name'] == 'old'
    assert [item['tool_name'] for item in snapshot['recent_errors']] == ['old']
    following = system.runs.diagnostic_summary(value)
    assert following['rejection_count'] == 2
    assert following['latest_rejection']['tool_name'] == 'new'
    assert [item['tool_name'] for item in following['recent_errors']] == ['old','new']


@pytest.mark.parametrize('count', [30,300])
def test_recoverable_page_additional_reads_do_not_grow_with_unrelated_history(tmp_path, monkeypatch, count):
    from tests.operations.test_root_draft_routes import _failed_source
    from tests.operations.test_l2_run_invariants import _system as recovery_system
    catalog, runtime, instance, _, root = recovery_system(tmp_path)
    _failed_source(catalog, runtime, root)
    with runtime.runs._connect() as db:
        source = dict(db.execute('SELECT * FROM runs').fetchone())
        # This fixture explicitly retains an unused recovery allowance; the
        # production permission/budget check must actually return true.
        policy = json.loads(source['recovery_policy_json'])
        source['recovery_policy_json'] = json.dumps({**policy, 'scheduler_max_attempts':4})
        db.execute('UPDATE runs SET recovery_policy_json=? WHERE run_id=?',
            (source['recovery_policy_json'],source['run_id']))
        columns = list(source)
        for index in range(count-1):
            historical = dict(source, run_id='run_'+f'{index:032x}', state='completed', recovery_draft_json=None)
            db.execute('INSERT INTO runs ('+','.join(columns)+') VALUES ('+
                ','.join('?' for _ in columns)+')', [historical[key] for key in columns])
    with runtime.scheduler_bindings._connect() as db:
        db.executemany('INSERT INTO scheduler_bindings VALUES(?,?,?,?,?,?,?,?)',
            [(instance.instance_id,'run',f'history-{index}',f'history-{index}',1,
              'run_'+f'{index:032x}',None,'2026-01-01') for index in range(count-1)])
    system = SimpleNamespace(root=root, runtime=runtime, runs=runtime.runs, bindings=runtime.scheduler_bindings)
    counts = observe_reads(system, monkeypatch)
    page = root.call_tool('run_list', dict(state='failed',limit=1))
    assert [item['name'] for item in page['runs']] == ['draft_source']
    assert page['runs'][0]['recovery_available'] is True
    assert counts['max_identity_rows'] == 1 and counts['bindings_materialized'] == counts['payload_reads'] == 0
    # Existing recovery permission/budget checks reread the exact source/root;
    # they remain separate from page selection, never all unrelated history.
    assert counts['full_runs'] <= 3
    metrics(f'recoverable-{count}', dict(**counts, tasks=count, page_full_runs=1,
        additional_exact_recovery_reads=counts['full_runs']-1))
