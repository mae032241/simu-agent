"""Frozen history uses real SQLite, Root/MCP, and existing sealed originals."""
import json
from contextlib import closing

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.service.progression_records import store_checkpoint
from scidiscovery.artifact_agent.storage.cas import CASObjectMissingError
from tests.operations.test_run_list_bounds import collection, metrics
from tests.operations.research_loop_fixtures import authorize_loop
from tests.operations.test_unified_mcp import call, result
from tests.operations.test_progression import progression


SECRET = b'history-fixture-secret-' + b'x'*32


def router(system, *, secret=SECRET, runtime=None, instance=None):
    runtime = runtime or system.runtime
    return RootMCPRouter(RootToolFacade(runtime.artifacts, runtime.intake, runs=runtime.runs,
        approvals=runtime.approvals, executions=runtime.executions, bindings=runtime.scheduler_bindings,
        instance=instance or system.instance, instance_management_secret=secret,
        operation_catalog=system.root.facade._operation_catalog))


def history_system(tmp_path, count, *, helper_calls=0):
    system = collection(tmp_path, count)
    system.root = router(system)
    bindings, runs = system.bindings, system.runs
    user = 'sch_'+'a'*32
    bindings.bind_session(session_key=user, instance_id=system.instance)
    system.root.facade.session_key = user
    settings = bindings.global_settings
    bindings.global_settings = settings.model_copy(update=dict(
        helpers=settings.helpers.model_copy(update=dict(max_calls=helper_calls)),
        progression=settings.progression.model_copy(update=dict(max_tasks=count+10,max_rounds=1))))
    system.root.call_tool('progression_command', dict(command='takeover',mode='interactive'))
    system.root.call_tool('artifact_ingest_text', dict(name='goal',text='Exact original goal.'))
    system.root.call_tool('progression_command', dict(command='pause'))
    authorize_loop(system.runtime, system.instance, user, 'goal')
    system.root.call_tool('progression_command', dict(command='start',mode='interactive',objective_name='goal'))
    control = bindings.progression_status(instance_id=system.instance, internal=True)
    checkpoint = json.loads(control['checkpoint_json'])
    system.goal = json.loads(control['objective_ref_json'])
    system.loop = checkpoint['current_loop_id']
    with closing(runs._connect()) as db:
        system.template = dict(db.execute('SELECT * FROM runs').fetchone())
    admissions = {}
    with closing(runs._connect()) as db, db:
        db.execute('DELETE FROM run_activity')
        for index, (name, identity) in enumerate(system.ids.items()):
            clock = f'2026-10-01T00:{index//120:02d}:{(index//2)%60:02d}Z'
            state = 'failed' if index == 0 else 'completed'
            db.execute('UPDATE runs SET state=?,completed_at=? WHERE run_id=?', (state,clock,identity))
            runs._append_activity(db, identity, 'framework_failure' if index == 0 else 'completion_committed',
                clock, json.dumps(dict(category='runtime_failure',code='runtime_failure')) if index == 0 else None)
            admissions[name] = dict(state='accepted',run_id=identity,objective_ref=system.goal,loop_id=system.loop,
                task_classification=dict(kind='research'),usage_source='frontend_unconnected')
    checkpoint['admissions'] = admissions
    with closing(bindings._connect()) as db, db:
        db.execute('UPDATE scheduler_progression SET checkpoint_json=? WHERE instance_id=?',
            (store_checkpoint(db,system.instance,checkpoint),system.instance))
    system.expected = list(reversed(list(system.ids)))
    system.gateway = UnifiedMCPRouter(system.root,worker_backend='local')
    return system


def add_terminal(system, name, index):
    """Synthetic scale fixture; immutable event IDs use the production allocator."""
    identity = 'run_'+f'{index:032x}'
    value = dict(system.template,run_id=identity,state='completed',completed_at='2026-10-01T00:00:00Z',
        output_binding_name=name+'.output',output_logical_name=name+'.output')
    columns = list(value)
    with closing(system.runs._connect()) as db, db:
        db.execute('INSERT INTO runs ('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+')',
            [value[key] for key in columns])
        system.runs._append_activity(db,identity,'completion_committed',value['completed_at'],None)
    system.bindings.bind(instance=system.instance,namespace='run',name=name,object_id=identity)
    control = system.bindings.progression_status(instance_id=system.instance,internal=True)
    checkpoint = json.loads(control['checkpoint_json'])
    checkpoint['admissions'][name] = dict(state='accepted',run_id=identity,objective_ref=system.goal,loop_id=system.loop,
        task_classification=dict(kind='research'),usage_source='frontend_unconnected')
    with closing(system.bindings._connect()) as db, db:
        db.execute('UPDATE scheduler_progression SET checkpoint_json=? WHERE instance_id=?',
            (store_checkpoint(db,system.instance,checkpoint),system.instance))


@pytest.mark.parametrize('count', [30,100,300])
def test_frozen_pages_find_early_failure_without_new_work_or_full_run_reads(tmp_path, monkeypatch, count):
    system = history_system(tmp_path,count)
    connect = system.runs._connect
    counts = dict(full_runs=0,payload_reads=0,max_identity_rows=0,reader_writes=0)
    class Cursor:
        def __init__(self,cursor,sql): self.cursor,self.sql=cursor,sql
        def __getattr__(self,name): return getattr(self.cursor,name)
        def fetchall(self):
            rows = self.cursor.fetchall()
            if self.sql.startswith('SELECT b.name,r.state,r.completed_at'):
                counts['max_identity_rows'] = max(counts['max_identity_rows'],len(rows))
            return rows
    class Connection:
        def __init__(self): self.connection=connect()
        def __getattr__(self,name): return getattr(self.connection,name)
        def execute(self,sql,*args):
            if sql.startswith(('INSERT','UPDATE','DELETE','REPLACE')): counts['reader_writes'] += 1
            return Cursor(self.connection.execute(sql,*args),sql)
    def full_rows(rows):
        counts['full_runs'] += len(tuple(rows))
        pytest.fail('history must not hydrate complete Runs')
    def payload(*args,**kwargs):
        counts['payload_reads'] += 1
        pytest.fail('history must not read scientific originals')
    with monkeypatch.context() as patch:
        patch.setattr(system.runs,'_connect',Connection)
        patch.setattr(system.runs,'_statuses_from_rows',full_rows)
        patch.setattr(system.runtime.artifacts,'read',payload)
        first = result(call(system.gateway,'run_list',dict(view='history',limit=7)))
    add_terminal(system,'later-backdated-task',count+1000)
    names, page, pages, peak = [], first, 0, 0
    with monkeypatch.context() as patch:
        patch.setattr(system.runs,'_connect',Connection)
        patch.setattr(system.runs,'_statuses_from_rows',full_rows)
        patch.setattr(system.runtime.artifacts,'read',payload)
        while True:
            names.extend(item['name'] for item in page['runs'])
            assert len(page['runs']) <= 7 and page['terminal_source_missing'] == 0
            peak = max(peak,len(json.dumps(page).encode()))
            pages += 1
            if not page['continuation']: break
            query = dict(page['continuation']);query.pop('tool')
            page = system.root.call_tool('run_list',query)
    assert names == system.expected and len(set(names)) == count
    assert page['runs'][-1]['state'] == 'failed'
    assert counts['full_runs'] == counts['payload_reads'] == counts['reader_writes'] == 0
    assert counts['max_identity_rows'] <= 8 and peak <= 16384
    assert first['history_scope']['loop_coverage'] == 'exact_goal_across_loops'
    metrics(f'history-{count}',dict(**counts,tasks=count,pages=pages,peak_response_bytes=peak))
    failure = system.root.call_tool('run_status',dict(name='task-0000',intent='status',diagnostic_after=0))
    assert failure['state'] == 'failed' and failure['diagnostic_events']['events']


def test_cursor_is_query_bound_and_late_completion_stays_out_after_restart(tmp_path):
    from scidiscovery.artifact_agent.runtime import open_runtime
    system = history_system(tmp_path,30)
    add_terminal(system,'already-queued',9000)
    identity = 'run_'+f'{9000:032x}'
    with closing(system.runs._connect()) as db, db:
        db.execute('DELETE FROM run_activity WHERE run_id=?', (identity,))
        db.execute("UPDATE runs SET state='queued',completed_at=NULL WHERE run_id=?", (identity,))
    first = system.root.call_tool('run_list',dict(view='history',limit=7))
    token = first['next_before']
    tampered = token[:20]+('A' if token[20]!='A' else 'B')+token[21:]
    for change in (dict(before=tampered),dict(state='completed'),dict(limit=8)):
        with pytest.raises(ValueError,match='Invalid history cursor'):
            system.root.call_tool('run_list',dict(view='history',limit=7,before=token)|change)
    other = system.bindings.create_instance(name='other',title='Other',objective='Independent original')
    with pytest.raises(ValueError,match='Invalid history cursor'):
        router(system,instance=other.instance_id).call_tool('run_list',dict(view='history',limit=7,before=token))
    with closing(system.runs._connect()) as db, db:
        db.execute("UPDATE runs SET state='completed',completed_at='2026-10-01T00:00:00Z' WHERE run_id=?", (identity,))
        system.runs._append_activity(db,identity,'completion_committed','2026-10-01T00:00:00Z',None)
    reopened = open_runtime(project_root=system.runtime.project_root,state_root=system.runtime.state_root,
        worker_backend='local')
    cold = router(system,runtime=reopened)
    names, page = [item['name'] for item in first['runs']], first
    while page['continuation']:
        query = dict(page['continuation']);query.pop('tool')
        page = cold.call_tool('run_list',query)
        names.extend(item['name'] for item in page['runs'])
    assert names == system.expected and 'already-queued' not in names
    changed = router(system,runtime=reopened,secret=b'z'*32)
    with pytest.raises(ValueError,match='Invalid history cursor'):
        changed.call_tool('run_list',dict(view='history',limit=7,before=token))
    assert changed.call_tool('run_list',dict(view='history',limit=7))['runs']
    system.root.call_tool('artifact_ingest_text',dict(name='new-goal',text='Different exact original.'))
    system.root.call_tool('progression_command',dict(command='pause'))
    system.root.call_tool('progression_command',dict(command='start',mode='interactive',objective_name='new-goal'))
    assert system.root.call_tool('run_list',dict(view='history'))['runs'] == []
    old = system.root.call_tool('run_status',dict(name='task-0001',intent='navigation'))['attempt_history']['read']
    query = dict(old);query.pop('tool')
    old_page = system.root.call_tool('run_list',query)
    assert old_page['runs'] and old_page['history_scope']['objective_name'] == 'goal'


def test_terminal_source_gaps_and_missing_original_are_explicit(tmp_path):
    system = history_system(tmp_path,3)
    with closing(system.runs._connect()) as db, db:
        db.execute('DELETE FROM run_activity WHERE run_id=?', (system.ids['task-0001'],))
    page = system.root.call_tool('run_list',dict(view='history'))
    assert page['terminal_source_missing'] == 1
    assert [item['name'] for item in page['runs']] == ['task-0002','task-0000']
    ref = system.runs.status(system.ids['task-0002']).output_ref
    system.runtime.artifacts.cas.path_for(ref.sha256).unlink()
    assert system.root.call_tool('run_list',dict(view='history'))['original_read'] == 'not_confirmed'
    with pytest.raises(CASObjectMissingError):
        system.root.call_tool('run_status',dict(name='task-0002'))
    with closing(system.runs._connect()) as db, db:
        db.execute('DELETE FROM run_activity WHERE run_id=?', (system.ids['task-0001'],))
        db.execute('DELETE FROM runs WHERE run_id=?', (system.ids['task-0001'],))
    with pytest.raises(Exception,match='unavailable or conflicting exact Run binding'):
        system.root.call_tool('run_list',dict(view='history',state='completed'))


def test_later_unbound_admission_does_not_poison_frozen_range_and_lost_old_run_fails(tmp_path):
    system = history_system(tmp_path,30)
    first = system.root.call_tool('run_list',dict(view='history',limit=1))
    control = system.bindings.progression_status(instance_id=system.instance,internal=True)
    checkpoint = json.loads(control['checkpoint_json'])
    checkpoint['admissions']['late-unbound'] = dict(state='accepted',run_id='run_'+'e'*32,
        objective_ref=system.goal,loop_id=system.loop,task_classification=dict(kind='research'),
        semantic_binding_pending=True)
    with closing(system.bindings._connect()) as db, db:
        db.execute('UPDATE scheduler_progression SET checkpoint_json=? WHERE instance_id=?',
            (store_checkpoint(db,system.instance,checkpoint),system.instance))
    page = system.root.call_tool('run_list',dict(view='history',limit=1,before=first['next_before']))
    assert [item['name'] for item in page['runs']] == ['task-0028']
    with closing(system.runs._connect()) as db, db:
        db.execute('DELETE FROM run_activity WHERE run_id=?', (system.ids['task-0010'],))
        db.execute('DELETE FROM runs WHERE run_id=?', (system.ids['task-0010'],))
    with pytest.raises(Exception,match='Frozen terminal history changed or is unavailable'):
        system.root.call_tool('run_list',dict(view='history',limit=1,before=page['next_before']))


def test_archive_restore_retains_history_and_exact_original_entry(progression):
    from tests.operations.synchronous_archive_fixture import SynchronousFixtureArchive
    from tests.operations.test_instance_archive import save_archive,restore_archive
    from tests.operations.test_scientific_progress import finish
    p = progression
    p.root.facade.instance_management_secret = SECRET
    p.root.call_tool('progression_command',dict(command='pause'))
    p.root.call_tool('progression_command',dict(command='start',mode='interactive',objective_name='goal'))
    for name in ('archive-first','archive-second','archive-third'):
        finish(p,p.root,name)
    first = p.root.call_tool('run_list',dict(view='history',limit=1))
    expected = p.root.call_tool('run_status',dict(name='archive-second'))['selected_output']
    p.root.call_tool('progression_command',dict(command='pause'))
    p.runtime.runs._synchronous_archive_fixture = True
    archive = SynchronousFixtureArchive(p.runtime)
    save_archive(archive,p.instance)
    restore_archive(archive,p.instance)
    restored = router(p)
    second = restored.call_tool('run_list',dict(view='history',limit=1,before=first['next_before']))
    assert [item['name'] for item in second['runs']] == ['archive-second']
    fresh = restored.call_tool('run_list',dict(view='history',limit=3))
    assert [item['name'] for item in fresh['runs']] == ['archive-third','archive-second','archive-first']
    original = restored.call_tool('run_status',dict(name='archive-second'))
    assert original['state'] == 'completed' and original['selected_output'] == expected


def test_two_authorized_loops_on_exact_goal_keep_old_attempts(loop_ui):
    from tests.operations.test_loop_review_budget import configure
    from tests.operations.test_research_loop_budget import authorize,start,usage,finish_task,release,checkpoint,historical_checkpoint
    p = loop_ui
    configure(p,max_tasks=1)
    assert authorize(p) == 303
    root = start(p)
    root.facade.instance_management_secret = SECRET
    usage(p,p.coordinator.host.identity.thread_id)
    _,thread = finish_task(p,root,'old-loop-result')
    usage(p,thread)
    old = checkpoint(p)['current_loop_id']
    release(p)
    assert authorize(p) == 303
    root = start(p)
    root.facade.instance_management_secret = SECRET
    assert checkpoint(p)['current_loop_id'] != old
    usage(p,p.coordinator.host.identity.thread_id,amount=2)
    _,thread = finish_task(p,root,'new-loop-result')
    usage(p,thread)
    before = historical_checkpoint(p)
    page = root.call_tool('run_list',dict(view='history',limit=3))
    assert [item['name'] for item in page['runs']] == ['new-loop-result','old-loop-result']
    navigation = root.call_tool('run_status',dict(name='old-loop-result',intent='navigation'))['attempt_history']['read']
    query = dict(navigation);query.pop('tool')
    assert len(root.call_tool('run_list',query)['runs']) == 2
    assert historical_checkpoint(p) == before


from tests.operations.test_research_loop_budget import loop_ui
