"""Ordinary closeout bounds details while accounting for its whole frozen scope."""
import json
import sqlite3
from contextlib import closing
from threading import Event, Thread
from types import SimpleNamespace

import pytest

from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.refs import ActorRef, ArtifactRef
from scidiscovery.artifact_agent.service.progression_records import store_checkpoint
from scidiscovery.platforms.codex_usage import observe_usage
from tests.operations.test_attempt_history import history_system
from tests.operations.test_run_list_bounds import metrics


def observe_status_reads(system, monkeypatch):
    counts = dict(full_runs=0, payload_reads=0, identity_rows=0, reader_writes=0,
        accounting_rows=0, accounting_record_bytes=0)
    statuses, read, connect = system.runs._statuses_from_rows, system.runtime.artifacts.read, system.runs._connect
    def counted_statuses(rows):
        rows = list(rows)
        counts['full_runs'] += len(rows)
        return statuses(rows)
    def counted_read(*args, **kwargs):
        counts['payload_reads'] += 1
        return read(*args, **kwargs)
    class Cursor:
        def __init__(self, cursor, sql): self.cursor, self.sql = cursor, sql
        def __getattr__(self, name): return getattr(self.cursor, name)
        def __iter__(self): return iter(self.cursor)
        def fetchall(self):
            rows = self.cursor.fetchall()
            if self.sql.startswith('WITH admissions AS'):
                counts['identity_rows'] += len(rows)
            if self.sql.startswith('SELECT record_key,record_json'):
                counts['accounting_rows'] += len(rows)
                counts['accounting_record_bytes'] += sum(len(row['record_json'].encode()) for row in rows)
            if self.sql.startswith('SELECT run_id,state FROM runs'):
                counts['identity_rows'] += len(rows)
            return rows
    class Connection:
        def __init__(self): self.connection = connect()
        def __getattr__(self, name): return getattr(self.connection, name)
        def __enter__(self): self.connection.__enter__(); return self
        def __exit__(self, *args): return self.connection.__exit__(*args)
        def execute(self, sql, *args):
            if sql.startswith(('INSERT', 'UPDATE', 'DELETE', 'REPLACE')):
                counts['reader_writes'] += 1
            return Cursor(self.connection.execute(sql, *args), sql)
    monkeypatch.setattr(system.runs, '_statuses_from_rows', counted_statuses)
    monkeypatch.setattr(system.runtime.artifacts, 'read', counted_read)
    monkeypatch.setattr(system.runs, '_connect', Connection)
    return counts


def scale_participants_and_executions(system):
    """Readonly scale fixture, not native attachment/execution qualification."""
    workers, helpers = [], []
    requests, executions = {}, []
    with system.runs._connect() as db:
        db.execute('DELETE FROM worker_connections')
        for index, (name, identity) in enumerate(system.ids.items()):
            worker = f'worker-{index}'
            workers.append(worker)
            db.execute('INSERT INTO worker_connections(run_id,platform_session,thread_id,attached_at) VALUES(?,?,?,?)',
                (identity, worker, worker, '2026-10-01'))
            for helper_index in range(2):
                thread = f'helper-{index}-{helper_index}'
                helpers.append(thread)
                db.execute('INSERT INTO worker_participants VALUES(?,?,?,?,?,?,?,?,?,?)',
                    (identity, identity, f'helper-{helper_index}', '{}', thread, worker, thread,
                        '2026-10-01', '2026-10-01', '2026-10-01'))
                db.execute('INSERT INTO run_activity(run_id,activity,recorded_at,diagnostic_json) VALUES(?,?,?,?)',
                    (identity, 'execution_observation', '2026-10-01', json.dumps(dict(detail='x'*8192))))
    for index, (name, identity) in enumerate(system.ids.items()):
        request = system.runtime.artifacts.register(identity.encode(), ArtifactRegistration(kind='fixture', schema_id='opaque',
            payload_schema_version=1, media_type='text/plain', creator=ActorRef(actor_type='service', actor_id='fixture'),
            labels=dict(experiment_run=identity)), idempotency_key='scale-execution:'+name).ref
        for attempt in range(2):
            execution = f'execution-{index}-{attempt}'
            executions.append(execution)
            requests[execution] = request
    control = system.bindings.progression_status(instance_id=system.instance, internal=True)
    checkpoint = json.loads(control['checkpoint_json'])
    usage = {}
    for role, threads in (('root', ['root-0', 'root-1', 'root-2']), ('worker', workers[:2]), ('helper', helpers[:3])):
        for thread in threads:
            usage[thread] = dict(observe_usage(dict(threadId=thread, tokenUsage=dict(total=dict(
                inputTokens=10, cachedInputTokens=0, outputTokens=1))), role=role, owner=thread), loop_id=system.loop)
    checkpoint['usage_records'] = usage
    with system.bindings._connect() as db:
        db.execute('UPDATE scheduler_progression SET checkpoint_json=? WHERE instance_id=?',
            (store_checkpoint(db, system.instance, checkpoint), system.instance))
    # A persisted-state reader fixture exercises the production reminder path.
    reader = SimpleNamespace(active_ids=lambda **kw: tuple(executions[:kw['limit']]),
        record_references=lambda identity: dict(request_ref=requests[identity],
            payload_ref=ArtifactRef.model_validate(system.goal)), status=lambda _: SimpleNamespace(state='running'))
    system.root.facade.executions = reader


@pytest.mark.parametrize('count', [30, 100, 300])
def test_status_details_are_bounded_but_page_outside_work_and_failure_remain_visible(tmp_path, monkeypatch, count):
    system = history_system(tmp_path, count, helper_calls=2)
    with system.runs._connect() as db:
        db.execute("UPDATE runs SET state='queued',completed_at=NULL WHERE run_id=?", (system.ids['task-0001'],))
    scale_participants_and_executions(system)
    counts = observe_status_reads(system, monkeypatch)
    before = system.bindings.progression_status(instance_id=system.instance, internal=True)
    status = system.root.call_tool('progression_status', {})
    response_bytes = len(json.dumps(status, ensure_ascii=False).encode())
    metrics(f'closeout-{count}', dict(**counts, tasks=count, root_identities=3, worker_identities=count,
        helper_identities=2*count, execution_records=2*count, response_bytes=response_bytes))
    assert counts['full_runs'] <= 8, counts
    assert counts['payload_reads'] <= 8, counts
    assert counts['reader_writes'] == 0
    assert response_bytes <= 65536
    closeout = status['closeout']
    assert not closeout['accepted_tasks_terminal']
    assert closeout['state_counts'] == dict(completed=count-2, failed=1, queued=1)
    assert closeout['in_flight'][0]['name'] == 'task-0001'
    assert len(closeout['tasks']) <= 8 and closeout['omissions']
    assert status['budget']['research_tasks'] == count
    assert status['budget']['observed_tokens'] == 88
    assert status['usage']['unmeasured_participants'] == dict(worker=count-2, helper=2*count-3)
    assert status['usage']['coverage'] == status['budget']['token_coverage'] == 'partial'
    assert len(status['external_work']['items']) == 32
    assert status['external_work']['association_coverage'] == 'partial'
    assert status['external_work']['omissions'] == ['execution_candidate_limit']
    assert counts['identity_rows'] <= 64
    assert system.bindings.progression_status(instance_id=system.instance, internal=True) == before
    query = dict(closeout['history_read']); query.pop('tool')
    names, page = [], system.root.call_tool('run_list', query)
    while True:
        names.extend(item['name'] for item in page['runs'])
        if not page['continuation']: break
        query = dict(page['continuation']); query.pop('tool')
        page = system.root.call_tool('run_list', query)
    assert 'task-0000' in names
    assert system.root.call_tool('run_status', dict(name='task-0000', intent='status'))['state'] == 'failed'


@pytest.mark.parametrize('count', [30, 100, 300])
def test_checkpoint_identity_guard_uses_thin_batch_and_physical_writes_are_incremental(tmp_path, count):
    system = history_system(tmp_path, count)
    checkpoint = json.loads(system.bindings.progression_status(instance_id=system.instance, internal=True)['checkpoint_json'])
    with system.bindings._connect() as db:
        original = db.execute('SELECT checkpoint_json FROM scheduler_progression WHERE instance_id=?',
            (system.instance,)).fetchone()[0]
        queries = []
        db.set_trace_callback(queries.append)
        previous = db.total_changes
        unchanged = store_checkpoint(db, system.instance, checkpoint)
        unchanged_writes = db.total_changes-previous
        checkpoint['admissions']['task-0001']['semantic_binding_pending'] = False
        previous = db.total_changes
        changed = store_checkpoint(db, system.instance, checkpoint)
        changed_writes = db.total_changes-previous
        assert unchanged == changed == original
        assert unchanged_writes == 0 and changed_writes == 1
        assert not any(sql.startswith('SELECT record_json FROM scheduler_progression_details') for sql in queries)
        batch_guards = sum(sql.startswith('SELECT record_key,json_extract') for sql in queries)
        assert batch_guards == 2  # One admission identity batch for each write; usage is empty.
        db.set_trace_callback(None)
    restored = json.loads(system.bindings.progression_status(instance_id=system.instance, internal=True)['checkpoint_json'])
    assert restored['admissions']['task-0001']['semantic_binding_pending'] is False
    assert len(restored['admissions']) == count
    metrics(f'checkpoint-{count}', dict(tasks=count, unchanged_detail_writes=unchanged_writes,
        one_changed_detail_writes=changed_writes, loop_identity_queries=batch_guards,
        old_record_body_queries=0, limitation='Current authoritative scope is still fully validated and encoded.'))


def test_unresolved_identity_outside_detail_sample_prevents_terminal_and_observed_coverage(tmp_path):
    system = history_system(tmp_path, 30, helper_calls=2)
    scale_participants_and_executions(system)
    with system.bindings._connect() as db:
        db.executemany("DELETE FROM scheduler_bindings WHERE instance=? AND namespace='run' AND name=?",
            [(system.instance, f'task-{index:04d}') for index in range(1, 12)])
    status = system.root.call_tool('progression_status', {})
    closeout = status['closeout']
    assert closeout['state_counts']['identity_unresolved'] == 11
    assert len(closeout['unresolved']) == 8 and not closeout['accepted_tasks_terminal']
    assert next(item for item in closeout['omissions'] if item['reason'] == 'unresolved_detail_limit')['count'] == 3
    assert status['usage']['unresolved_task_identities'] == 11
    assert status['usage']['coverage'] == status['budget']['token_coverage'] == 'partial'
    assert status['budget']['observed_tokens'] == 88 and status['budget']['research_tasks'] == 30


def test_external_owner_navigation_keeps_exact_source_chain_and_default_query(tmp_path):
    system = history_system(tmp_path, 12)
    from scidiscovery.artifact_agent.service.run_records import inputs_json, RunInputBinding
    goal = ArtifactRef.model_validate(system.goal)
    unrelated = system.runtime.artifacts.register(b'Another goal.', ArtifactRegistration(kind='source_text', schema_id='opaque',
        payload_schema_version=1, media_type='text/plain', creator=ActorRef(actor_type='service', actor_id='fixture')),
        idempotency_key='other-scale-goal').ref
    child = system.runtime.artifacts.register(b'Sourced observation.', ArtifactRegistration(kind='fixture', schema_id='opaque',
        payload_schema_version=1, media_type='text/plain', creator=ActorRef(actor_type='service', actor_id='fixture'),
        parent_refs=(goal,)), idempotency_key='scale-child').ref
    def binding(port, name, ref):
        return RunInputBinding(port_name=port, source_name=name, artifact_name=name, artifact_ref=ref,
            media_type='text/plain', exposure='inline', usage='scientific', require_current=False)
    with system.runs._connect() as db:
        db.execute('UPDATE runs SET inputs_json=? WHERE run_id=?', (inputs_json((
            binding('evidence', 'child', child),)), system.ids['task-0001']))
        db.execute('UPDATE runs SET inputs_json=? WHERE run_id=?', (inputs_json((
            binding('evidence', 'child', child), binding('objective', 'other', unrelated))), system.ids['task-0002']))
    default, omitted = system.runs.goal_related_runs(instance_id=system.instance, artifact_ref=goal, limit=8)
    thin, thin_omitted = system.runs.goal_related_runs(instance_id=system.instance, artifact_ref=goal,
        limit=8, identities_only=True)
    assert thin == tuple(value.run_id for value in default) == (system.ids['task-0001'],)
    assert omitted == thin_omitted == False


def test_control_details_use_the_attached_scheduler_schema(tmp_path):
    system = history_system(tmp_path, 12)
    with system.runs._connect() as db:
        db.execute('CREATE TABLE scheduler_progression_details(instance_id TEXT,collection TEXT,record_key TEXT,record_json TEXT)')
        db.execute('INSERT INTO scheduler_progression_details VALUES(?,?,?,?)',
            (system.instance, 'admissions', 'unrelated-shadow', '{}'))
    status = system.root.call_tool('progression_status', {})
    assert status['closeout']['state_counts'] == dict(completed=11, failed=1)
    assert status['budget']['research_tasks'] == 12


def test_closeout_counts_and_details_share_one_read_snapshot(tmp_path, monkeypatch):
    system = history_system(tmp_path, 12)
    start, changed, committed = Event(), Event(), Event()
    errors = []
    def change():
        try:
            assert start.wait(2)
            with closing(sqlite3.connect(system.runs.database_path, timeout=2)) as db:
                db.execute("UPDATE runs SET state='queued' WHERE run_id=?", (system.ids['task-0011'],))
                changed.set()
                db.commit()
                committed.set()
        except BaseException as error:
            errors.append(error)
            changed.set()
    connect = system.runs._connect
    triggered = False
    class CountCursor:
        def __init__(self, cursor): self.cursor = cursor
        def fetchall(self):
            rows = self.cursor.fetchall()
            start.set()
            assert changed.wait(2) and not errors
            committed.wait(0.05)
            assert not committed.is_set(), 'Writer committed while the closeout read snapshot was still open'
            return rows
    class Connection:
        def __init__(self): self.connection = connect()
        def __getattr__(self, name): return getattr(self.connection, name)
        def __enter__(self): self.connection.__enter__(); return self
        def __exit__(self, *args): return self.connection.__exit__(*args)
        def execute(self, sql, *args):
            nonlocal triggered
            cursor = self.connection.execute(sql, *args)
            if sql.startswith('WITH admissions AS') and 'GROUP BY state,in_goal,usage_coverage' in sql and not triggered:
                triggered = True
                return CountCursor(cursor)
            return cursor
    monkeypatch.setattr(system.runs, '_connect', Connection)
    writer = Thread(target=change, daemon=True)
    writer.start()
    try:
        status = system.root.call_tool('progression_status', {})
    finally:
        start.set()
        writer.join(3)
    assert not errors and not writer.is_alive() and committed.is_set()
    closeout = status['closeout']
    assert closeout['state_counts'] == dict(completed=11, failed=1) and closeout['accepted_tasks_terminal']
    assert next(item['state'] for item in closeout['tasks'] if item['name'] == 'task-0011') == 'completed'
    following = system.root.call_tool('progression_status', {})
    assert following['closeout']['state_counts'] == dict(completed=10, failed=1, queued=1)
    assert not following['closeout']['accepted_tasks_terminal']
