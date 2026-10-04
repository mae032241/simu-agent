"""Real task/open/tool/Root consumers of bounded, frozen attempt memory."""
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from tests.operations.test_attempt_history import history_system, add_terminal, metrics, SECRET
from tests.operations.test_local_worker_contracts import _invoke, _worker
from tests.operations.test_progression import progression, unmanaged_progression, row
from tests.operations.test_scientific_progress import finish, request, assess, active
from tests.operations.test_experiment_material_delivery import catalog, staged_experiment


@pytest.fixture
def historical_experiment_memory(staged_experiment):
    from types import SimpleNamespace
    from scidiscovery.operations.catalog import CompiledCatalog
    from scidiscovery.artifact_agent.service.experiment_execution import bind_experiment_services
    from tests.operations.test_experiment_material_delivery import submit_staged_report
    from tests.operations.research_loop_fixtures import authorize_loop
    f = staged_experiment
    current = f.catalog
    old = next(compiled for (name, _), compiled in current._historical_operations.items()
        if name == 'science.experiment.v1')
    assert current.recorded_contract_status(old.spec.operation_id,
        version=old.spec.version, digest=old.digest) == 'supported_historical'
    # Execute the real predecessor capsule, including its validators and tools;
    # do not relabel a current Run or alias the old digest to a current checker.
    prior = CompiledCatalog({name:old if name == old.spec.operation_id else current.operation(name)
        for name in current.operation_ids()}, current._runtime_factories,
        current._runtime_configuration_digests, current._runtime_identity_digests)
    runs, bindings, root = f.runtime.runs, f.runtime.scheduler_bindings, f.root
    runs.operation_catalog = root.facade._operation_catalog = prior
    user = 'sch_' + 'a'*32
    bindings.bind_session(session_key=user, instance_id=f.instance.instance_id)
    root.facade.session_key = user
    root.facade.instance_management_secret = SECRET
    root.call_tool('progression_command', dict(command='takeover', mode='interactive'))
    root.call_tool('progression_command', dict(command='pause'))
    authorize_loop(f.runtime, f.instance.instance_id, user, 'objective')
    root.call_tool('progression_command', dict(command='start', mode='interactive', objective_name='objective'))
    created = root.call_tool('operation_invoke', dict(name='historical-experiment',
        operation_id=old.spec.operation_id, inputs=[dict(port='subject',artifact_names=['objective']),
            dict(port='scientific_materials',artifact_names=['condition'])], instruction='Retain an unresolved bounded design.'))
    assert created['result']['state'] == 'queued'
    identity = root.facade._resolve('run', 'historical-experiment')
    runs.worker_connections.attach(run_id=identity, platform_session='historical-author', thread_id='historical-author')
    class UnusedService:
        def __getattr__(self, name):
            raise AttributeError(name)
    services = {key:UnusedService() for tool in old.worker_tools for key in tool.required_services}
    services = bind_experiment_services(runs, old, services, coordinator=runs.experiment_executions)
    worker = LocalWorkerMCPRouter(runs, operation_id=old.spec.operation_id,
        operation_digest=old.digest, tool_services=services)
    opened = worker.call_tool('worker_open_assignment', {})
    stage = worker.call_tool('worker_experiment_stage', dict(stage='design',
        conclusion='This bounded design still needs a validation observation.', materials=['scientific_materials']))
    author = SimpleNamespace(worker=worker, workspace=Path(opened['workspace_path']))
    completed = submit_staged_report(author, [stage['reference']])
    metrics('historical-experiment-submit', completed)
    assert completed['state'] == 'completed', completed
    stored = runs.status(identity)
    assert stored.operation_digest == old.digest != current.operation(old.spec.operation_id).digest
    runs.operation_catalog = root.facade._operation_catalog = current
    assert runs._compiled(stored) is old
    reader = f.start('current-memory-reader')
    return SimpleNamespace(f=f, old=old, stored=stored, reader=reader)


def test_supported_historical_contract_survives_real_memory_routes(historical_experiment_memory):
    h = historical_experiment_memory
    root_page = h.f.root.call_tool('run_list', dict(view='history', limit=8))
    worker_page = h.reader.worker.call_tool('worker_read_history', dict(limit=8))
    metrics('historical-memory-routes', dict(root=root_page, worker=worker_page))
    for page in (root_page, worker_page):
        item = next(item for item in page['runs'] if item['name'] == 'historical-experiment')
        assert {source['artifact_name'] for source in item['frozen_inputs']} >= {'objective', 'condition'}
        assert item['scientific_fields']['/outcome'] == 'inconclusive'
        assert item['scientific_fields']['/remaining_question'] == 'The observations do not establish a unique mechanism.'
        assert not any('contract_unavailable' in gap or 'scientific_fields_original_unavailable' == gap
            for gap in item['omissions'])
    scope = h.f.runtime.runs._worker_memory_binding(h.reader.run_id)['scope']
    neutral = h.f.runtime.runs.memory_page(scope, audience='reviewer')
    item = neutral['runs'][0]
    assert item['frozen_inputs'] and item['projection'].startswith('neutral_terminal_index')
    assert not any(key in item for key in ('summary', 'scientific_fields', 'worker_verdict', 'root_judgment'))


@pytest.mark.parametrize('operation_id', [
    'science.evidence.audit.intake.v1', 'science.evidence.audit.v1', 'science.evidence.extract.v1',
    'science.experiment.v1', 'science.hypothesis.criticize.v1', 'science.hypothesis.propose.v1',
    'science.object.review.v1'])
def test_actual_supported_registry_contracts_keep_inputs_and_declared_fields(staged_experiment, operation_id):
    f = staged_experiment
    old = next(compiled for (name, _), compiled in f.catalog._historical_operations.items() if name == operation_id)
    assert f.catalog.recorded_operation(operation_id, version=old.spec.version, digest=old.digest) is old
    assert f.catalog.recorded_contract_status(operation_id, version=old.spec.version,
        digest=old.digest) == 'supported_historical'
    inputs = [dict(port_name=port.name, source_name=port.name, artifact_name='original-'+port.name)
        for port in old.spec.inputs]
    # Synthetic projection bytes exercise the exact seven registered capsules;
    # the route regression above instead seals an actual complete final report.
    body, expected = {}, {}
    for field in old.spec.decision_fields:
        if field == 'summary':continue
        pointer = field if field.startswith('/') else '/' + field.replace('~','~0').replace('/','~1')
        keys = [key.replace('~1','/').replace('~0','~') for key in pointer[1:].split('/')]
        value = 'recorded decision field '+field
        nested = body
        for key in keys[:-1]:nested = nested.setdefault(key,{})
        nested[keys[-1]] = value
        expected[pointer] = value
    assert expected
    original = f.register('recorded-projection', canonical_json(body), old.spec.outputs[0].schema_id)
    row = dict(operation_id=operation_id, operation_version=old.spec.version, operation_digest=old.digest,
        inputs_json=canonical_json(inputs), output_ref_json=original.ref.model_dump_json())
    visible, omission = f.runtime.runs._memory_visible_inputs(row, 16384)
    assert omission is None
    assert {item['original_name'] for item in visible} == {
        port.name for port in old.spec.inputs if port.agent_visible and port.exposure != 'handoff_only'}
    item = dict(omissions=[])
    f.runtime.runs._memory_scientific_fields(item, row, 16384, read_bytes=16384)
    assert item['scientific_fields'] == expected and item['omissions'] == []


@pytest.mark.parametrize('invalid', ['unknown_operation', 'wrong_version', 'wrong_digest', 'current_digest_wrong_version'])
def test_unavailable_recorded_identity_stays_unknown_on_real_memory_routes(historical_experiment_memory, invalid):
    h = historical_experiment_memory
    changes = dict(operation_id=h.old.spec.operation_id, operation_version=h.old.spec.version, operation_digest=h.old.digest)
    if invalid == 'unknown_operation':changes['operation_id'] = 'not.installed.v1'
    elif invalid in {'wrong_version', 'current_digest_wrong_version'}:changes['operation_version'] = 'not-supported-version'
    else:changes['operation_digest'] = '0'*64
    if invalid == 'current_digest_wrong_version':
        changes['operation_digest'] = h.f.catalog.operation(h.old.spec.operation_id).digest
    with h.f.runtime.runs._connect() as db:
        db.execute('UPDATE runs SET operation_id=?,operation_version=?,operation_digest=? WHERE run_id=?',
            (*changes.values(),h.stored.run_id))
    pages = (h.f.root.call_tool('run_list', dict(view='history', limit=8)),
        h.reader.worker.call_tool('worker_read_history', dict(limit=8)))
    for page in pages:
        item = next(item for item in page['runs'] if item['name'] == 'historical-experiment')
        assert item['frozen_inputs'] == [] and 'scientific_fields' not in item
        assert 'historical_visibility_contract_unavailable' in item['omissions']
        assert 'scientific_fields_contract_unavailable' in item['omissions']


def test_compiled_independent_reviewer_history_is_neutral_but_subject_original_remains_readable(progression):
    import subprocess,sys
    from blind_csv_plugin.plugin import PLUGIN,REVIEWER
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN as GENERAL
    from scidiscovery.operations.catalog import compile_catalog
    p=progression
    spec=REVIEWER.model_copy(update=dict(operation_id='blind.csv.inspect.v1',independent_review_ports=('csv_observation',)))
    catalog=compile_catalog((CORE_PLUGIN,GENERAL,PLUGIN.model_copy(update=dict(operations=(*PLUGIN.operations,spec)))))
    p.catalog=catalog;p.runtime.runs.operation_catalog=catalog;p.root.facade._operation_catalog=catalog
    root=active(p)
    finish(p,root,'author')
    assess(root,'author',reason='The scheduler endorsed this existing conclusion.')
    subject=root.call_tool('run_status',dict(name='author'))['output_artifact_name']
    root.call_tool('operation_invoke',dict(name='independent-inspection',operation_id=spec.operation_id,
        inputs=[dict(port='source_table',artifact_names=['source_csv']),dict(port='csv_observation',artifact_names=[subject])],
        instruction='Inspect the exact subject independently.'))
    identity=root.facade._resolve('run','independent-inspection')
    caller=('audit-session','independent-inspection-thread')
    p.runtime.runs.worker_connections.attach(run_id=identity,platform_session=caller[0],thread_id=caller[1])
    compiled=catalog.operation(spec.operation_id)
    worker=LocalWorkerMCPRouter(p.runtime.runs,operation_id=spec.operation_id,operation_digest=compiled.digest,
        run_id=identity,trusted_caller=caller)
    opened=worker.call_tool('worker_open_assignment',{})
    startup=json.loads(Path(opened['start_here_path']).read_bytes())
    page=worker.call_tool('worker_read_history',dict(limit=1))
    for memory in (startup['attempt_memory'],page):
        assert all(key not in json.dumps(memory) for key in ('worker_verdict','root_judgment','scientific_fields','Bounded result.'))
    assert page['runs'][0]['name']=='author' and 'summary' not in page['runs'][0]
    assert any(i['source_name']=='csv_observation' for i in startup['inputs'])
    original=subprocess.run([sys.executable,'tools/read_input.py','csv_observation'],cwd=opened['workspace_path'],
        capture_output=True,text=True,check=True)
    assert 'The bounded arithmetic mean is two.' in original.stdout


def test_bad_handoff_content_is_local_unknown_and_healthy_history_remains_readable(progression):
    p=progression
    root=active(p)
    finish(p,root,'healthy')
    finish(p,root,'broken-handoff')
    identity=root.facade._resolve('run','broken-handoff')
    with p.runtime.runs._connect() as db:
        db.execute('UPDATE runs SET signal_json=? WHERE run_id=?',(b'{',identity))
    _invoke(root,'memory-reader')
    worker=_worker(p.catalog,p.runtime)
    opened=worker.call_tool('worker_open_assignment',{})
    startup=json.loads(Path(opened['start_here_path']).read_bytes())['attempt_memory']
    page=worker.call_tool('worker_read_history',dict(limit=1))
    assert page['runs'][0]['name']=='broken-handoff'
    assert 'worker_handoff_invalid' in page['runs'][0]['omissions']
    healthy=worker.call_tool('worker_read_history',dict(limit=1,before=page['next_before']))
    assert healthy['runs'][0]['name']=='healthy' and healthy['runs'][0]['summary']=='Bounded result.'
    assert 'healthy' in json.dumps(startup)
    from tests.operations.test_attempt_history import router
    public=router(p)
    root_page=public.call_tool('run_list',dict(view='history',limit=1))
    assert 'worker_handoff_invalid' in root_page['runs'][0]['omissions']
    assert public.call_tool('run_list',dict(view='history',limit=1,before=root_page['next_before']))['runs'][0]['name']=='healthy'


def test_invalid_optional_judgment_reference_does_not_hide_healthy_history(progression):
    from tests.operations.test_attempt_history import router
    p=progression;root=active(p)
    for name in ('healthy-judgment','invalid-judgment'):
        finish(p,root,name);assess(root,name)
    _invoke(root,'judgment-reader')  # Current accepted identity is fully valid.
    identity=root.facade._resolve('run','invalid-judgment')
    with p.runtime.scheduler_bindings._connect() as db:
        changed=db.execute('UPDATE scheduler_progress_assessments SET artifact_ref_json=? WHERE instance_id=? AND run_id=?',
            (canonical_json(dict(artifact_id='incomplete')),p.instance,identity))
        assert changed.rowcount==1
    worker=_worker(p.catalog,p.runtime)
    opened=worker.call_tool('worker_open_assignment',{})
    startup=json.loads(Path(opened['start_here_path']).read_bytes())['attempt_memory']
    page=worker.call_tool('worker_read_history',dict(limit=1))
    broken=page['runs'][0]
    assert broken['name']=='invalid-judgment'
    assert 'root_judgment_original_unavailable' in broken['omissions']
    assert broken['content_coverage'].startswith('partial_unknown') and 'root_judgment' not in broken
    healthy=worker.call_tool('worker_read_history',dict(limit=1,before=page['next_before']))['runs'][0]
    assert healthy['name']=='healthy-judgment' and healthy['root_judgment']['outcome']=='advance'
    assert 'healthy-judgment' in json.dumps(startup)
    public=router(p);root_page=public.call_tool('run_list',dict(view='history',limit=1))
    assert 'root_judgment_original_unavailable' in root_page['runs'][0]['omissions']
    assert public.call_tool('run_list',dict(view='history',limit=1,before=root_page['next_before']))['runs'][0]['root_judgment']['outcome']=='advance'
    assert not p.runtime.runs.reference_access_records(worker._run_id)
    assert worker.call_tool('worker_open_assignment',{})['start_here_path']==opened['start_here_path']


@pytest.mark.parametrize('invalid_inputs',[b'{',b'{}',b'"scalar"',b'["bare element"]',b'[{}]','mixed_object_and_scalar'])
def test_invalid_optional_input_index_does_not_block_open_or_healthy_pages(progression,invalid_inputs):
    from tests.operations.test_attempt_history import router
    p=progression;root=active(p)
    finish(p,root,'healthy-input-index');finish(p,root,'invalid-input-index')
    _invoke(root,'input-index-reader')
    identity=root.facade._resolve('run','invalid-input-index')
    with p.runtime.runs._connect() as db:
        if invalid_inputs=='mixed_object_and_scalar':
            valid=json.loads(db.execute('SELECT inputs_json FROM runs WHERE run_id=?',(identity,)).fetchone()[0])
            invalid_inputs=canonical_json([valid[0],'bare element'])
        db.execute('UPDATE runs SET inputs_json=? WHERE run_id=?',(invalid_inputs,identity))
    worker=_worker(p.catalog,p.runtime)
    opened=worker.call_tool('worker_open_assignment',{})
    startup=json.loads(Path(opened['start_here_path']).read_bytes())['attempt_memory']
    assert 'healthy-input-index' in json.dumps(startup)
    assert 'invalid-input-index' not in json.dumps(startup['exact_source_related'])
    first=worker.call_tool('worker_read_history',dict(limit=1))
    broken=first['runs'][0]
    assert broken['name']=='invalid-input-index' and 'input_index_invalid' in broken['omissions']
    assert broken['content_coverage'].startswith('partial_unknown') and not broken['frozen_inputs']
    healthy=worker.call_tool('worker_read_history',dict(limit=1,before=first['next_before']))['runs'][0]
    assert healthy['name']=='healthy-input-index' and healthy['frozen_inputs']
    public=router(p);page=public.call_tool('run_list',dict(view='history',limit=1))
    assert 'input_index_invalid' in page['runs'][0]['omissions']
    assert public.call_tool('run_list',dict(view='history',limit=1,before=page['next_before']))['runs'][0]['name']=='healthy-input-index'
    assert not p.runtime.runs.reference_access_records(worker._run_id)
    # Optional association never repairs a damaged source or broadens membership.
    with pytest.raises(Exception):
        worker.call_tool('worker_reference_read',dict(history_task='invalid-input-index',action='read',reference='unbound-source'))
    with pytest.raises(Exception):
        worker.call_tool('worker_reference_read',dict(history_task='unbound-foreign-task'))
    assert not p.runtime.runs.reference_access_records(worker._run_id)
    assert worker.call_tool('worker_open_assignment',{})['start_here_path']==opened['start_here_path']


def revision_goal(p, name, previous, *, supersedes=True):
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    old=p.runtime.artifacts.get_by_id(p.root.facade._resolve('artifact',previous))
    new=p.runtime.artifacts.register(('Exact revised direction '+name).encode(),ArtifactRegistration(
        kind=old.kind,schema_id=old.schema_id,payload_schema_version=old.payload_schema_version,
        media_type=old.media_type,creator=old.creator,labels=old.labels,
        supersedes_ref=old.ref if supersedes else None,parent_refs=() if supersedes else (old.ref,)),idempotency_key='revision-'+name)
    p.runtime.scheduler_bindings.bind(instance=p.instance,namespace='artifact',name=name,object_id=new.artifact_id)
    p.root.call_tool('progression_command',dict(command='pause'))
    proposal=p.runtime.scheduler_bindings.loop_authorization_proposal(instance_id=p.instance,session_key=p.user)
    p.runtime.scheduler_bindings.authorize_loop_from_ui(instance_id=p.instance,session_key=p.user,
        confirmation_binding=proposal['confirmation_binding'],objective_name=name,objective_ref=new.ref)
    p.root.call_tool('progression_command',dict(command='start',mode='interactive',objective_name=name))
    return new


def test_explicit_revision_lineage_is_shared_frozen_and_judgments_keep_actual_goal(unmanaged_progression):
    from tests.operations.research_loop_fixtures import authorize_loop
    from tests.operations.test_attempt_history import router
    p=unmanaged_progression
    authorize_loop(p.runtime,p.instance,p.user,'goal')
    p.root.call_tool('progression_command',dict(command='start',mode='interactive',objective_name='goal'))
    finish(p,p.root,'under-a');assess(p.root,'under-a')
    revision_goal(p,'goal-b','goal')
    finish(p,p.root,'under-b')
    revision_goal(p,'goal-c','goal-b')
    _invoke(p.root,'lineage-reader')
    worker=_worker(p.catalog,p.runtime)
    opened=worker.call_tool('worker_open_assignment',{})
    first=worker.call_tool('worker_read_history',dict(limit=1))
    assert first['runs'][0]['name']=='under-b'
    second=worker.call_tool('worker_read_history',dict(limit=1,before=first['next_before']))
    assert second['runs'][0]['name']=='under-a'
    assert second['runs'][0]['root_judgment']['outcome']=='advance'
    public=router(p)
    root_page=public.call_tool('run_list',dict(view='history',limit=1))
    assert root_page['runs'][0]['name']=='under-b'
    old_cursor=root_page['next_before']
    old_scope=deepcopy(p.runtime.runs._worker_memory_binding(worker._run_id)['scope'])
    assert len(old_scope['objective_ancestors'])==2
    # The encrypted old-scope format deliberately remains exact, never expanded.
    exact=dict(old_scope);exact.pop('objective_ancestors');exact['terminal_count']=0
    assert p.runtime.runs.attempt_history_page(exact)==[]
    assert worker.call_tool('worker_open_assignment',{})['start_here_path']==opened['start_here_path']
    assert worker.call_tool('worker_read_history',dict(limit=1))==first
    from tests.operations.test_local_worker_contracts import _write_result
    _write_result(worker);assert worker.call_tool('worker_submit_result',{})['state']=='completed'
    finish(p,p.root,'after-freeze')
    assert public.call_tool('run_list',dict(view='history',limit=1,before=old_cursor))['runs'][0]['name']=='under-a'
    with p.runtime.runs._connect() as db:
        assert json.loads(db.execute('SELECT memory_scope_json FROM runs WHERE run_id=?',(worker._run_id,)).fetchone()[0])['scope']==old_scope
    revision_goal(p,'goal-d','goal-c')
    revision_goal(p,'unrelated','goal-d',supersedes=False)
    assert public.call_tool('run_list',dict(view='history',limit=1))['runs']==[]



def capacity_system(p,count):
    from types import SimpleNamespace
    from tests.operations.research_loop_fixtures import authorize_loop
    from scidiscovery.artifact_agent.service.progression_records import store_checkpoint
    bindings,runs=p.runtime.scheduler_bindings,p.runtime.runs
    settings=bindings.global_settings
    bindings.global_settings=settings.model_copy(update=dict(progression=settings.progression.model_copy(update=dict(max_tasks=count+10,max_rounds=1))))
    authorize_loop(p.runtime,p.instance,p.user,'goal')
    p.root.call_tool('progression_command',dict(command='start',mode='interactive',objective_name='goal'))
    finish(p,p.root,'task-0000')
    control=row(p)
    checkpoint=json.loads(control['checkpoint_json'])
    admission=checkpoint['admissions']['task-0000']
    with closing(runs._connect()) as db:
        template=dict(db.execute('SELECT * FROM runs WHERE run_id=?',(admission['run_id'],)).fetchone())
    columns=list(template)
    admissions={};ids={}
    with closing(runs._connect()) as db,db:
        db.execute('DELETE FROM run_activity')
        for index in range(count):
            name=f'task-{index:04d}'
            identity=template['run_id'] if index==0 else 'run_'+f'{index:032x}'
            clock=f'2026-10-01T00:{index//120:02d}:{(index//2)%60:02d}Z'
            state='failed' if index==0 else 'completed'
            if index:
                value=dict(template,run_id=identity,state=state,completed_at=clock,output_binding_name=name+'.output',output_logical_name=name+'.output')
                db.execute('INSERT INTO runs ('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+')',[value[key] for key in columns])
            else:
                db.execute('UPDATE runs SET state=?,completed_at=? WHERE run_id=?',(state,clock,identity))
            runs._append_activity(db,identity,'framework_failure' if index==0 else 'completion_committed',clock,canonical_json(dict(category='runtime_failure',code='runtime_failure')) if index==0 else None)
            admissions[name]=dict(admission,run_id=identity)
            ids[name]=identity
    for name,identity in ids.items():
        if name!='task-0000':bindings.bind(instance=p.instance,namespace='run',name=name,object_id=identity)
    checkpoint['admissions']=admissions
    with closing(bindings._connect()) as db,db:
        db.execute('UPDATE scheduler_progression SET checkpoint_json=? WHERE instance_id=?',(store_checkpoint(db,p.instance,checkpoint),p.instance))
    return SimpleNamespace(root=p.root,runtime=p.runtime,bindings=bindings,runs=runs,instance=p.instance,
        ids=ids,expected=list(reversed(list(ids))),template=template,goal=json.loads(control['objective_ref_json']),loop=checkpoint['current_loop_id'])

@pytest.mark.parametrize('count',[30,100,300])
def test_startup_and_pages_are_bounded_frozen_and_find_early_boundary(unmanaged_progression, monkeypatch, count):
    p=capacity_system(unmanaged_progression,count)
    _invoke(p.root,'memory-reader')
    worker=_worker(p.runs.operation_catalog,p.runtime)
    read=p.runtime.artifacts.read
    counts=dict(original_reads=0)
    def counted(ref):
        counts['original_reads']+=1
        return read(ref)
    with monkeypatch.context() as patch:
        patch.setattr(p.runtime.artifacts,'read',counted)
        opened=worker.call_tool('worker_open_assignment',{})
    start=json.loads(Path(opened['start_here_path']).read_bytes())
    memory=start['attempt_memory']
    assert memory['objective']['original']=='Compare exact data and retain limitations.'
    assert memory['failure_boundaries'][0]['name']=='task-0000'
    assert memory['failure_boundaries'][0]['result_nature']=='engineering_failure_not_scientific_negation'
    assert memory['original_access']=='worker_reference_read'
    assert len(memory['recent'])<=3 and len(memory['exact_source_related'])<=2
    assert not any(k in json.dumps(memory) for k in ('terminal_upper','instance_id','run_id','artifact_ref','assessment_upper'))
    with closing(p.runs._connect()) as db:
        frozen=db.execute('SELECT memory_scope_json,recovery_policy_json FROM runs WHERE run_id=?',(worker._run_id,)).fetchone()
        before_changes=db.execute('SELECT COUNT(*) FROM run_activity').fetchone()[0]
    startup_reads=counts['original_reads']
    pages=[]
    page_reads=[]
    with monkeypatch.context() as patch:
        patch.setattr(p.runtime.artifacts,'read',counted)
        cursor=None
        while True:
            before=counts['original_reads']
            page=worker.call_tool('worker_read_history',dict(limit=7,before=cursor))
            page_reads.append(counts['original_reads']-before)
            pages.append(page)
            if not page['next_before']:break
            cursor=page['next_before']
    assert max(page_reads)<=14
    assert [i['name'] for page in pages for i in page['runs']]==p.expected
    assert pages[-1]['runs'][-1]['failure_category']=='runtime_failure'
    assert max(len(canonical_json(page)) for page in pages)<=16384
    with closing(p.runs._connect()) as db:
        assert db.execute('SELECT COUNT(*) FROM run_activity').fetchone()[0]==before_changes
    add_terminal(p,'later-completion',count+999)
    reopened=worker.call_tool('worker_open_assignment',{})
    with closing(p.runs._connect()) as db:
        assert tuple(db.execute('SELECT memory_scope_json,recovery_policy_json FROM runs WHERE run_id=?',(worker._run_id,)).fetchone())==tuple(frozen)
    assert 'later-completion' not in json.dumps(json.loads(Path(reopened['start_here_path']).read_bytes())['attempt_memory'])
    metrics('memory-'+str(count),dict(tasks=count,startup_bytes=len(Path(opened['start_here_path']).read_bytes()),memory_bytes=len(canonical_json(memory)),max_page_bytes=max(len(canonical_json(page)) for page in pages),startup_original_reads=startup_reads,max_page_original_reads=max(page_reads)))


def test_actual_root_continuation_brief_keeps_old_failure_and_frozen_index(progression):
    p=progression
    p.root.facade.instance_management_secret=SECRET
    root=active(p)
    finish(p,root,'early')
    finish(p,root,'recent')
    assess(root,'early',reason='The early observation has a restricted condition.')
    p.coordinator.host.finish()
    p.now[0]+=6
    p.coordinator.tick()
    assert len(p.coordinator.host.prompts)==2
    brief=json.loads(p.coordinator.host.prompts[-1].split('\n')[-1])
    memory=brief['attempt_memory']
    assert 'objective' not in memory
    assert 'recent' not in [i['name'] for i in memory['recent']]
    query=dict(memory['history']);query.pop('tool')
    page=root.call_tool('run_list',query)
    assert 'early' in [i['name'] for i in page['runs']]
    old=next(i for i in page['runs'] if i['name']=='early')
    assert old['root_judgment']['outcome']=='advance'
    assert old['root_judgment']['details'].startswith('unavailable_in_this_projection')
    assess(root,'early',outcome='unknown',evidence=False,reason='Correction overturns the previous assessment.')
    same=root.call_tool('run_list',query)
    assert next(i for i in same['runs'] if i['name']=='early')['root_judgment_revision']==1
    current=root.call_tool('run_list',dict(view='history',limit=8))
    assert next(i for i in current['runs'] if i['name']=='early')['root_judgment_revision']==2


def science_system(tmp_path, *, plan=None):
    from tests.operations.test_tcad_result_analysis import analysis_system
    from tests.operations.research_loop_fixtures import authorize_loop
    from tests.operations import test_m2_curve_analysis_boundary as curve
    system=analysis_system(tmp_path,plan=plan)
    catalog,runtime,root,_,artifacts,register=system
    instance=root.facade._instance_id()
    user='sch_'+'a'*32
    runtime.scheduler_bindings.bind_session(session_key=user,instance_id=instance)
    root.facade.session_key=user
    root.call_tool('progression_command',dict(command='takeover',mode='interactive'))
    root.call_tool('artifact_ingest_text',dict(name='goal',text='Find the finite scientific boundary and preserve failed conditions.'))
    root.call_tool('progression_command',dict(command='pause'))
    authorize_loop(runtime,instance,user,'goal')
    root.call_tool('progression_command',dict(command='start',mode='interactive',objective_name='goal'))
    bundle=curve._bundle().model_dump(mode='json')
    bundle['series'][1]['points']=deepcopy(bundle['series'][0]['points'])
    register('generic_results',b'Execution finished with a limited finite observation.','opaque',parents=(artifacts['plan'].ref,))
    register('generic_bundle',canonical_json(bundle),'scidiscovery.curve-bundle.v1',parents=(artifacts['plan'].ref,))
    return system


def science_worker(system,name, instruction='Analyze exact bounded originals.', reference_material=None):
    catalog,runtime,root,_,_,_=system
    inputs=[dict(port='experiment_plan',artifact_names=['plan']),dict(port='experiment_results',artifact_names=['generic_results']),dict(port='curve_bundle',artifact_names=['generic_bundle'])]
    if reference_material:
        inputs.append(dict(port='reference_material',artifact_names=[reference_material]))
    root.call_tool('operation_invoke',dict(name=name,operation_id='science.result.diagnose.v1',instruction=instruction,inputs=inputs))
    identity=root.facade._resolve('run',name)
    caller=('source-session',name+'-thread')
    runtime.runs.worker_connections.attach(run_id=identity,platform_session=caller[0],thread_id=caller[1])
    compiled=catalog.operation('science.result.diagnose.v1')
    worker=LocalWorkerMCPRouter(runtime.runs,operation_id=compiled.spec.operation_id,operation_digest=compiled.digest,run_id=identity,trusted_caller=caller)
    opened=worker.call_tool('worker_open_assignment',{})
    return worker,opened


def complete_science(worker,opened,alias='experiment_results'):
    from tests.operations.test_analysis_handoff_report import compact_report
    payload=compact_report(alias)
    (Path(opened['workspace_path'])/'output/result.json').write_bytes(canonical_json(dict(payload=payload)))
    reply=worker.call_tool('worker_submit_result',{})
    assert reply['state']=='completed',reply


def test_scientific_negative_is_attributed_conditioned_and_not_engineering_failure(tmp_path):
    from tests.operations.test_analysis_handoff_report import compact_report
    from tests.operations import test_m2_curve_analysis_boundary as curve
    system=science_system(tmp_path,plan=curve._compiler_plan())
    _,runtime,root,_,_,_=system
    for name,negative in (('finite-negative',True),('blocked-delivery',False)):
        worker,opened=science_worker(system,name)
        payload=compact_report('experiment_results',verdict='fail' if not negative else 'inconclusive')
        payload.update(study_kind='scientific',summary='The finite prediction remains conditional.',
            remaining_contradiction='The tested prediction differs from the observation; other mechanisms remain open.')
        if negative:
            payload['hypothesis_assessments']=[dict(hypothesis_key='hypothesis_implementation',outcome='contradicts',
                evidence_keys=['experiment_results'],rationale='Only the bound finite observation contradicts this prediction.')]
        (Path(opened['workspace_path'])/'output/result.json').write_bytes(canonical_json(dict(payload=payload)))
        reply=worker.call_tool('worker_submit_result',{})
        metrics('scientific-submission-'+name,reply)
        assert reply['state']=='completed',reply
    failed,_=science_worker(system,'engineering-failed')
    value=runtime.runs.status(failed._run_id)
    runtime.runs.record_failure(failed._run_id,reason='No numerical output could be produced.',
        expected_state='running',expected_last_activity_at=value.last_activity_at)
    reader,opened=science_worker(system,'inspect-memory',instruction='Inspect the existing finite conclusions and their original conditions.')
    startup=json.loads(Path(opened['start_here_path']).read_bytes())['attempt_memory']
    metrics('scientific-memory',startup)
    assert startup['scientific_negative_candidates'],startup
    assert startup['scientific_negative_candidates'][0]['name']=='finite-negative'
    page=reader.call_tool('worker_read_history',dict(limit=8))
    items={i['name']:i for i in page['runs']}
    negative=items['finite-negative']
    assert negative['scientific_fields']['/hypothesis_assessments'][0]['outcome']=='contradicts'
    assert negative['scientific_authority']=='sealed_worker_conclusion_not_controlled_verification'
    assert negative['scientific_fields']['/remaining_contradiction']
    assert negative['frozen_inputs'] and negative['original']['history_task']=='finite-negative'
    assert 'scientific_negative' not in items['blocked-delivery']
    assert items['engineering-failed']['result_nature']=='engineering_failure_not_scientific_negation'
    assert 'scientific_fields' not in items['engineering-failed']
    directory=reader.call_tool('worker_reference_read',dict(history_task='finite-negative'))
    report=next(i for i in directory['references'] if i['original_name']=='report')
    original=reader.call_tool('worker_reference_read',dict(history_task='finite-negative',action='read',reference=report['reference'],limit=8192))
    assert 'contradicts' in json.dumps(original['fragment'])
    # Content damage is local; exact scope and strict original checks stay intact.
    ref=runtime.runs.status(root.facade._resolve('run','blocked-delivery')).output_ref
    runtime.artifacts.cas.path_for(ref.sha256).write_bytes(b'{')
    changed=reader.call_tool('worker_read_history',dict(limit=8))
    items={i['name']:i for i in changed['runs']}
    assert 'scientific_fields_original_unavailable' in items['blocked-delivery']['omissions']
    assert items['finite-negative']['scientific_fields']==negative['scientific_fields']


def test_history_original_registers_real_citation_then_final_manifest_and_missing_are_not_success(tmp_path):
    from types import SimpleNamespace
    system=science_system(tmp_path)
    _,runtime,root,_,_,_=system
    lineage=SimpleNamespace(runtime=runtime,root=root,instance=root.facade._instance_id(),user=root.facade.session_key)
    early,opened=science_worker(system,'early-science')
    complete_science(early,opened)
    revision_goal(lineage,'science-goal-b','goal')
    middle,opened=science_worker(system,'middle-science')
    complete_science(middle,opened)
    revision_goal(lineage,'science-goal-c','science-goal-b')
    from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter,RootToolFacade
    other=runtime.scheduler_bindings.create_instance(name='foreign-science-instance',title='Foreign',objective='Independent research')
    for name in ('plan','generic_results','generic_bundle'):
        runtime.scheduler_bindings.bind(instance=other.instance_id,namespace='artifact',name=name,object_id=root.facade._resolve('artifact',name))
    foreign_root=RootMCPRouter(RootToolFacade(runtime.artifacts,runtime.intake,runs=runtime.runs,approvals=runtime.approvals,
        executions=runtime.executions,bindings=runtime.scheduler_bindings,instance=other.instance_id,operation_catalog=system[0]))
    foreign_system=(system[0],runtime,foreign_root,*system[3:])
    foreign,foreign_opened=science_worker(foreign_system,'foreign-science')
    complete_science(foreign,foreign_opened)
    worker,opened=science_worker(system,'new-science')
    with pytest.raises(Exception):
        worker.call_tool('worker_reference_read',dict(history_task='foreign-science'))

    assert not runtime.runs.reference_access_records(worker._run_id)
    page=worker.call_tool('worker_read_history',dict(limit=1))
    assert page['runs'][0]['name']=='middle-science'
    old=worker.call_tool('worker_read_history',dict(limit=1,before=page['next_before']))
    assert old['runs'][0]['name']=='early-science'
    directory=worker.call_tool('worker_reference_read',dict(history_task='early-science'))
    report=next(i for i in directory['references'] if i['original_name']=='report')
    original=worker.call_tool('worker_reference_read',dict(history_task='early-science',action='read',reference=report['reference'],limit=8192))
    assert original['source'].startswith('reference_')
    assert 'fragment' in original
    alias=original['source']
    assert runtime.runs.source_descriptor(runtime.runs.status(worker._run_id),alias).artifact_ref==runtime.runs.status(early._run_id).output_ref
    form=json.loads((Path(opened['workspace_path'])/'schema/result.schema.json').read_bytes())
    assert alias in json.dumps(form)
    complete_science(worker,opened,alias)
    producer=runtime.runs.status(worker._run_id)
    manifest=next(ref for ref in runtime.artifacts.catalog(producer.output_ref).parent_refs if ref.schema_id=='scidiscovery.tool-evidence-manifest.v1')
    proof=json.loads(runtime.artifacts.read(manifest))
    assert proof['accesses'][0]['artifact_ref']==runtime.runs.status(early._run_id).output_ref.model_dump(mode='json')
    assert proof['bindings'][alias]['port_name']=='reference_access'
    another,opened=science_worker(system,'missing-original-reader')
    ref=runtime.runs.status(early._run_id).output_ref
    runtime.artifacts.cas.path_for(ref.sha256).unlink()
    directory=another.call_tool('worker_reference_read',dict(history_task='early-science'))
    report=next(i for i in directory['references'] if i['original_name']=='report')
    with pytest.raises(Exception,match='Selected|missing|absent|object|Reference|reference|experiment'):
        another.call_tool('worker_reference_read',dict(history_task='early-science',action='read',reference=report['reference']))
    assert not runtime.runs.reference_access_records(another._run_id)


def bare_blind_plugin():
    from blind_csv_plugin.plugin import PLUGIN
    operation=PLUGIN.operations[0]
    bare=operation.model_copy(update=dict(executor=operation.executor.model_copy(update=dict(
        tools=tuple(t for t in operation.executor.tools if t.component_id!='reference_read_tool'))),
        outputs=tuple(p for p in operation.outputs if p.name!='recovery_manifest_output')))
    return PLUGIN.model_copy(update=dict(operations=(bare,*PLUGIN.operations[1:])))


def test_no_reference_operation_keeps_native_permissions_and_has_no_fake_original_tool(tmp_path):
    from blind_csv_plugin.plugin import PLUGIN
    from tests.operations.test_local_worker_contracts import _system
    operation=PLUGIN.operations[0]
    plugin=bare_blind_plugin()
    catalog,runtime,_,root=_system(tmp_path,blind_plugin=plugin)
    _invoke(root,'no-reference-reader')
    worker=_worker(catalog,runtime)
    opened=worker.call_tool('worker_open_assignment',{})
    start=json.loads(Path(opened['start_here_path']).read_bytes())
    assert 'worker_read_history' in start['tools']
    assert 'worker_reference_read' not in start['tools']
    assert catalog.operation('blind.csv.observe.v1').spec.executor.native_tools==operation.executor.native_tools
    assert worker.call_tool('worker_read_history',{})['unavailable']=='no_exact_goal_or_recorded_recovery_source'
    with pytest.raises(Exception,match='unknown'):
        worker.call_tool('worker_reference_read',dict(history_task='anything'))


def test_manifestless_terminal_report_is_readable_and_citable_from_frozen_history(tmp_path):
    from tests.operations import test_tcad_result_analysis as analysis
    from tests.operations.test_local_worker_contracts import RAW,_write_result
    system=science_system(tmp_path)
    _,runtime,root,_,_,register=system
    catalog=analysis.compile_catalog((analysis.CORE_PLUGIN,analysis.GENERAL_PLUGIN,
        analysis.CURVE_PLUGIN,analysis.TCAD_PLUGIN,bare_blind_plugin()))
    runtime.runs.operation_catalog=catalog
    root.facade._operation_catalog=catalog
    system=(catalog,*system[1:])
    register('source_csv',RAW,'blind.opaque.v1',media='text/csv')
    _invoke(root,'manifestless-producer')
    producer=_worker(catalog,runtime)
    producer.call_tool('worker_open_assignment',{})
    _write_result(producer)
    assert producer.call_tool('worker_submit_result',{})['state']=='completed'
    sealed=runtime.runs.status(producer._run_id)
    assert not any(ref.schema_id=='scidiscovery.tool-evidence-manifest.v1' for ref in runtime.artifacts.catalog(sealed.output_ref).parent_refs)
    worker,opened=science_worker(system,'manifestless-report-reader')
    page=worker.call_tool('worker_read_history',{})
    assert page['runs'][0]['name']=='manifestless-producer'
    directory=worker.call_tool('worker_reference_read',dict(history_task='manifestless-producer'))
    report=next(i for i in directory['references'] if i['original_name']=='report')
    read=worker.call_tool('worker_reference_read',dict(history_task='manifestless-producer',action='read',reference=report['reference'],limit=8192))
    alias=read['source']
    assert 'bounded arithmetic mean is two' in read['fragment']
    assert runtime.runs.source_descriptor(runtime.runs.status(worker._run_id),alias).artifact_ref==sealed.output_ref
    complete_science(worker,opened,alias)
    value=runtime.runs.status(worker._run_id)
    manifest=next(ref for ref in runtime.artifacts.catalog(value.output_ref).parent_refs if ref.schema_id=='scidiscovery.tool-evidence-manifest.v1')
    proof=json.loads(runtime.artifacts.read(manifest))
    assert proof['bindings'][alias]['artifact_ref']==sealed.output_ref.model_dump(mode='json')
    assert proof['accesses'][0]['producer_run_id']==producer._run_id
    assert proof['accesses'][0]['history_authorization']['task_name']=='manifestless-producer'


def test_history_bound_calculation_keeps_consumer_authority_and_original_producer_proof(tmp_path):
    from tests.operations.test_result_analysis_tool import score_inputs
    system=science_system(tmp_path)
    _,runtime,root,_,_,_=system
    producer,opened=science_worker(system,'calculation-A')
    score=producer.call_tool('worker_curve_score',dict(record_key='bounded-comparison',request=score_inputs()[1]))
    assert score['status']=='computed'
    calculation_ref=runtime.runs.source_descriptor(runtime.runs.status(producer._run_id),score['calculation_ref']).artifact_ref
    complete_science(producer,opened,score['calculation_ref'])
    consumer,opened=science_worker(system,'binding-B',reference_material='calculation-A.output.'+score['calculation_ref'])
    complete_science(consumer,opened)
    b=runtime.runs.status(consumer._run_id)
    b_manifest=next(ref for ref in runtime.artifacts.catalog(b.output_ref).parent_refs if ref.schema_id=='scidiscovery.tool-evidence-manifest.v1')
    b_proof=json.loads(runtime.artifacts.read(b_manifest))
    assert any(i['artifact_ref']==calculation_ref.model_dump(mode='json') for i in b_proof['bindings'].values())
    assert not b_proof['records'] and not b_proof['accesses']
    worker,opened=science_worker(system,'reader-C')
    directory=worker.call_tool('worker_reference_read',dict(history_task='binding-B'))
    bound=next(i for i in directory['references'] if i['original_name']=='reference_material')
    read=worker.call_tool('worker_reference_read',dict(history_task='binding-B',action='read',reference=bound['reference'],limit=8192))
    alias=read['source']
    assert runtime.runs.source_descriptor(runtime.runs.status(worker._run_id),alias).artifact_ref==calculation_ref
    # The historical consumer grants entry; the material's exact owner proves it.
    expanded=worker.call_tool('worker_reference_read',dict(source=alias))
    assert any(i.get('locator')=='/sources/curve_bundle' for i in expanded['references'])
    sources=runtime.runs.reference_calculation_sources(runtime.runs.status(worker._run_id),alias)
    assert sources is not None, 'Historical bound calculation lost its controlled producer receipt.'
    assert sources['curve_bundle']==runtime.artifacts.read(next(i.artifact_ref for i in runtime.runs.status(producer._run_id).inputs if i.source_name=='curve_bundle'))
    record=runtime.runs.reference_access_records(worker._run_id)[0]
    assert record['authorizing_run_id']==consumer._run_id
    assert record['authorizing_manifest_ref']==b_manifest.model_dump(mode='json')
    assert record['producer_run_id']==record['proof_run_id']==producer._run_id
    complete_science(worker,opened,alias)
    c=runtime.runs.status(worker._run_id)
    c_manifest=next(ref for ref in runtime.artifacts.catalog(c.output_ref).parent_refs if ref.schema_id=='scidiscovery.tool-evidence-manifest.v1')
    final=json.loads(runtime.artifacts.read(c_manifest))
    assert final['bindings'][alias]['artifact_ref']==calculation_ref.model_dump(mode='json')
    assert final['accesses'][0]['authorizing_run_id']==consumer._run_id
    assert final['accesses'][0]['proof_run_id']==producer._run_id
    assert final['accesses'][0]['proof_manifest_ref'] in [ref.model_dump(mode='json') for ref in runtime.artifacts.catalog(runtime.runs.status(producer._run_id).output_ref).parent_refs]
    # A mismatched controlled receipt cannot use the ordinary-report path.
    with closing(runtime.runs._connect()) as db,db:
        raw=db.execute('SELECT record_json FROM run_tool_evidence WHERE run_id=? AND alias=?',
            (producer._run_id,score['calculation_ref'])).fetchone()[0]
        damaged=json.loads(raw);damaged['size_bytes']+=1
        db.execute('UPDATE run_tool_evidence SET record_json=? WHERE run_id=? AND alias=?',
            (canonical_json(damaged),producer._run_id,score['calculation_ref']))
    negative,_=science_worker(system,'unpaired-calculation-reader')
    directory=negative.call_tool('worker_reference_read',dict(history_task='binding-B'))
    bound=next(i for i in directory['references'] if i['original_name']=='reference_material')
    with pytest.raises(Exception,match='immutable producer receipt|unpaired') as rejected:
        negative.call_tool('worker_reference_read',dict(history_task='binding-B',action='read',reference=bound['reference']))
    assert any(i.get('code')=='reference_record_unpaired' for i in rejected.value.details)
    assert not runtime.runs.reference_access_records(negative._run_id)


@pytest.mark.parametrize('terminal_order', ['increasing', 'same_time', 'rollback'])
def test_failed_condition_original_cross_page_changed_input_retry_and_scope_negatives(tmp_path,monkeypatch,terminal_order):
    from datetime import datetime, timedelta
    from types import SimpleNamespace
    from scidiscovery.artifact_agent.service import runs as run_service
    from scidiscovery.artifact_agent.service.progression_records import read_history_cursor
    from tests.operations.test_attempt_history import router
    system=science_system(tmp_path)
    _,runtime,root,_,artifacts,register=system
    failed,opened=science_worker(system,'early-failure')
    value=runtime.runs.status(failed._run_id)
    terminal_clock=run_service.timestamp()
    clocks = dict(increasing=1, same_time=0, rollback=-1)
    middle_clock = (datetime.fromisoformat(terminal_clock.replace('Z','+00:00'))
        + timedelta(milliseconds=clocks[terminal_order])).isoformat().replace('+00:00','Z')
    clock = [terminal_clock]
    # Explicit contract expectations, independently of the SQL implementation:
    # newest terminal timestamp first; equal timestamps use later terminal event.
    expected = ['early-failure','unrelated-terminal'] if terminal_order == 'rollback' else ['unrelated-terminal','early-failure']
    with monkeypatch.context() as patch:
        patch.setattr(run_service,'timestamp',lambda:clock[0])
        runtime.runs.record_failure(failed._run_id,reason='Fixture engineering failure under original finite conditions',expected_state='running',expected_last_activity_at=value.last_activity_at)
        clock[0] = middle_clock
        middle,opened=science_worker(system,'unrelated-terminal',instruction='Inspect a separate finite observation boundary in the same originals.')
        complete_science(middle,opened)
    original_ref=root.facade._resolve('artifact','generic_results')
    register('changed_results',b'The experimental conditions have now changed.','opaque',parents=(artifacts['plan'].ref,))
    # A condition change remains normal admission; memory introduces no gate.
    catalog=system[0]
    root.call_tool('operation_invoke',dict(name='changed-conditions',operation_id='science.result.diagnose.v1',instruction='Reassess the changed conditions.',inputs=[dict(port='experiment_plan',artifact_names=['plan']),dict(port='experiment_results',artifact_names=['changed_results']),dict(port='curve_bundle',artifact_names=['generic_bundle'])]))
    identity=root.facade._resolve('run','changed-conditions')
    caller=('source-session','changed-conditions-thread')
    runtime.runs.worker_connections.attach(run_id=identity,platform_session=caller[0],thread_id=caller[1])
    compiled=catalog.operation('science.result.diagnose.v1')
    worker=LocalWorkerMCPRouter(runtime.runs,operation_id=compiled.spec.operation_id,operation_digest=compiled.digest,run_id=identity,trusted_caller=caller)
    opened=worker.call_tool('worker_open_assignment',{})
    page=worker.call_tool('worker_read_history',dict(limit=1))
    pages=[page]
    instance = root.facade._instance_id()
    root_pages, root_scope = [], None
    frozen = runtime.runs._worker_memory_binding(identity)
    def capture():
        with closing(runtime.runs._connect()) as db:
            terminals=[dict(i) for i in db.execute('SELECT r.run_id,r.state,r.completed_at,a.activity,a.recorded_at,a.rowid AS event FROM runs r JOIN run_activity a USING(run_id) WHERE a.activity IN (\'framework_failure\',\'completion_committed\')')]
        diagnostic = dict(terminal_order=terminal_order,expected=expected,pages=pages,root_pages=root_pages,
            memory=frozen,root_scope=root_scope,terminals=terminals)
        metrics('condition-history-'+terminal_order,diagnostic)
        return terminals
    capture()
    public = router(SimpleNamespace(runtime=runtime,root=root,instance=instance))
    root_pages.append(public.call_tool('run_list',dict(view='history',limit=1)))
    capture()
    root_scope = read_history_cursor(root_pages[0]['next_before'],secret=SECRET,instance_id=instance,state=None,limit=1)
    worker.call_tool('worker_open_assignment',{})
    capture()
    while pages[-1]['next_before']:
        assert len(pages)<3, 'Exact two-task index must not repeat or loop.'
        pages.append(worker.call_tool('worker_read_history',dict(limit=1,before=pages[-1]['next_before'])))
        capture()
    while root_pages[-1]['continuation']:
        assert len(root_pages)<3, 'Exact Root continuation must not repeat or loop.'
        query=dict(root_pages[-1]['continuation']);query.pop('tool')
        root_pages.append(public.call_tool('run_list',query))
        capture()
    terminals=capture()
    by_run={item['run_id']:item for item in terminals}
    assert runtime.runs._worker_memory_binding(identity) == frozen
    assert root_scope['terminal_upper'] == frozen['scope']['terminal_upper']
    assert len(terminals)==2 and by_run[failed._run_id]['completed_at']==terminal_clock
    assert by_run[middle._run_id]['completed_at']==middle_clock
    assert by_run[failed._run_id]['event']<by_run[middle._run_id]['event']
    assert all(item['recorded_at']==item['completed_at'] for item in terminals)
    assert frozen['scope']['terminal_count']==root_scope['terminal_count']==2
    names=[i['name'] for p in pages for i in p['runs']]
    root_names=[i['name'] for p in root_pages for i in p['runs']]
    assert names==root_names==expected and len(set(names))==len(set(root_names))==2
    early=next(p for p in pages if p['runs'][0]['name']=='early-failure')
    assert early['runs'][0]['name']=='early-failure'
    assert early['runs'][0]['result_nature']=='engineering_failure_not_scientific_negation'
    historical_input=next(i for i in early['runs'][0]['frozen_inputs'] if i['original_name']=='experiment_results')
    assert historical_input['artifact_name']=='generic_results' and 'source_name' not in historical_input
    current=runtime.runs.status(identity)
    current_original=runtime.runs.source_descriptor(current,'experiment_results').artifact_ref
    assert current_original.artifact_id==root.facade._resolve('artifact','changed_results')
    assert current_original.artifact_id!=original_ref
    assert not runtime.runs.reference_access_records(identity)
    directory=worker.call_tool('worker_reference_read',dict(history_task='early-failure'))
    assert all(i['original_name']!='report' for i in directory['references'])
    original=next(i for i in directory['references'] if i['original_name']=='experiment_results')
    read=worker.call_tool('worker_reference_read',dict(history_task='early-failure',action='read',reference=original['reference']))
    descriptor=runtime.runs.source_descriptor(runtime.runs.status(identity),read['source'])
    assert read['source']!='experiment_results'
    assert descriptor.artifact_ref.artifact_id==original_ref
    assert runtime.runs.source_descriptor(runtime.runs.status(identity),'experiment_results').artifact_ref==current_original
    assert 'limited finite observation' in read['fragment']
    assert not {i['original_name'] for i in directory['references']} & {'recovery_manifest','recovery_manifest_output','prior_analysis_manifest'}
    with pytest.raises(Exception):
        worker.call_tool('worker_reference_read',dict(history_task='changed-conditions'))
    with pytest.raises(Exception):
        worker.call_tool('worker_read_history',dict(before='changed-conditions'))
    with pytest.raises(Exception):
        worker.call_tool('worker_reference_read',dict(history_task='early-failure',source='generic_results'))
    other=runtime.scheduler_bindings.create_instance(name='other',title='Other',objective='Unrelated')
    with closing(runtime.runs._connect()) as db,db:
        old=db.execute('SELECT memory_scope_json FROM runs WHERE run_id=?',(identity,)).fetchone()[0]
        tampered=json.loads(old);tampered['scope']['instance_id']=other.instance_id
        db.execute('UPDATE runs SET memory_scope_json=? WHERE run_id=?',(canonical_json(tampered),identity))
    with pytest.raises(Exception):
        worker.call_tool('worker_read_history',{})
    with closing(runtime.runs._connect()) as db,db:
        db.execute('UPDATE runs SET memory_scope_json=? WHERE run_id=?',(old,identity))
    complete_science(worker,opened,read['source'])


def test_restart_and_archive_keep_frozen_scope_and_original_aliases(tmp_path):
    from scidiscovery.artifact_agent.runtime import open_runtime
    from tests.operations.synchronous_archive_fixture import SynchronousFixtureArchive
    from tests.operations.test_instance_archive import save_archive,restore_archive
    system=science_system(tmp_path)
    catalog,runtime,root,_,_,_=system
    prior,opened=science_worker(system,'old-science')
    complete_science(prior,opened)
    worker,opened=science_worker(system,'cold-reader')
    with closing(runtime.runs._connect()) as db:
        frozen=db.execute('SELECT memory_scope_json FROM runs WHERE run_id=?',(worker._run_id,)).fetchone()[0]
    cold=open_runtime(project_root=runtime.project_root,state_root=runtime.state_root,worker_backend='local')
    cold.runs.operation_catalog=catalog
    router=LocalWorkerMCPRouter(cold.runs,operation_id=worker.operation_id,operation_digest=worker.operation_digest,run_id=worker._run_id,trusted_caller=worker._trusted_caller)
    assert router.call_tool('worker_read_history',{})['runs'][0]['name']=='old-science'
    reopened=router.call_tool('worker_open_assignment',{})
    directory=router.call_tool('worker_reference_read',dict(history_task='old-science'))
    report=next(i for i in directory['references'] if i['original_name']=='report')
    original=router.call_tool('worker_reference_read',dict(history_task='old-science',action='read',reference=report['reference']))
    complete_science(router,reopened,original['source'])
    root.call_tool('progression_command',dict(command='pause'))
    runtime.runs._synchronous_archive_fixture=True
    service=SynchronousFixtureArchive(runtime)
    instance=root.facade._instance_id()
    save_archive(service,instance)
    restore_archive(service,instance)
    with closing(runtime.runs._connect()) as db:
        assert db.execute('SELECT memory_scope_json FROM runs WHERE run_id=?',(worker._run_id,)).fetchone()[0]==frozen
    record=runtime.runs.reference_access_records(worker._run_id)[0]
    assert record['alias']==original['source'] and record['history_authorization']['task_name']=='old-science'
    assert runtime.artifacts.read(runtime.runs.status(prior._run_id).output_ref)


def test_summary_omits_whole_large_handoff_and_missing_original_never_becomes_success(unmanaged_progression):
    p=capacity_system(unmanaged_progression,30)
    with closing(p.runs._connect()) as db,db:
        db.execute('UPDATE runs SET signal_json=? WHERE run_id=?',(canonical_json(dict(verdict='inconclusive',summary='A provisional observation',assumptions=['condition '*3000],missing_inputs=['Unresolved source'],next_actions=[])),p.ids['task-0029']))
    page=p.root.facade.runs.memory_page(p.runs.attempt_history_scope(instance_id=p.instance,state=None,limit=1))
    item=page['runs'][0]
    assert 'worker_handoff' not in item and 'worker_limits' not in item
    assert item['summary']=='Sealed delivery; handoff omitted or unavailable.'
    assert 'worker_handoff_missing_or_byte_budget' in item['omissions']
    _invoke(p.root,'limited-memory')
    with closing(p.runs._connect()) as db,db:
        reader=p.root.facade._resolve('run','limited-memory')
        policy=json.loads(db.execute('SELECT recovery_policy_json FROM runs WHERE run_id=?',(reader,)).fetchone()[0])
        policy['input_materials'].update(startup_read_page_bytes=512,original_read_page_bytes=512)
        db.execute('UPDATE runs SET recovery_policy_json=? WHERE run_id=?',(canonical_json(policy),reader))
    worker=_worker(p.runs.operation_catalog,p.runtime)
    opened=worker.call_tool('worker_open_assignment',{})
    memory=json.loads(Path(opened['start_here_path']).read_bytes())['attempt_memory']
    assert len(canonical_json(memory))<=512
    assert 'omissions' in memory
    page=worker.call_tool('worker_read_history',dict(limit=20))
    assert len(canonical_json(page))<=512


def test_missing_old_binding_does_not_block_accepted_worker_or_root_brief(progression):
    p=progression
    p.root.facade.instance_management_secret=SECRET
    root=active(p)
    finish(p,root,'old-terminal')
    _invoke(root,'accepted-reader')
    with closing(p.runtime.scheduler_bindings._connect()) as db,db:
        db.execute("DELETE FROM scheduler_bindings WHERE instance=? AND namespace='run' AND name='old-terminal'",(p.instance,))
    worker=_worker(p.catalog,p.runtime)
    opened=worker.call_tool('worker_open_assignment',{})
    assert opened['state']=='opened'
    start=json.loads(Path(opened['start_here_path']).read_bytes())
    memory=start['attempt_memory']
    assert memory['unavailable']=='exact_history_missing_or_conflicting'
    assert memory['coverage']=='unknown_not_empty'
    assert memory['objective']['original']=='Compare exact data and retain limitations.'
    page=worker.call_tool('worker_read_history',{})
    assert page['unavailable']=='exact_history_missing_or_conflicting' and not page['runs']
    frozen=p.runtime.runs._worker_memory_binding(worker._run_id)
    with closing(p.runtime.runs._connect()) as db:
        identity=db.execute("SELECT run_id FROM runs WHERE output_binding_name='old-terminal.output'").fetchone()[0]
    p.runtime.scheduler_bindings.bind(instance=p.instance,namespace='run',name='old-terminal',object_id=identity)
    worker.call_tool('worker_open_assignment',{})
    assert p.runtime.runs._worker_memory_binding(worker._run_id)==frozen
    assert worker.call_tool('worker_read_history',{})['unavailable']=='exact_history_missing_or_conflicting'
    # A separate damaged optional history path cannot abort the real brief.
    with closing(p.runtime.scheduler_bindings._connect()) as db,db:
        db.execute("DELETE FROM scheduler_bindings WHERE instance=? AND namespace='run' AND name='old-terminal'",(p.instance,))
    control=p.coordinator._decision_row()
    snapshot=dict(runs=[],messages=[],approvals=[])
    brief=json.loads(p.coordinator._brief(control,snapshot,40000).split('\n')[-1])
    assert brief['attempt_memory']['unavailable']=='exact_history_missing_or_conflicting'
    assert brief['objective']['original']=='Compare exact data and retain limitations.'
    assert p.runtime.runs.status(worker._run_id).state=='running'
