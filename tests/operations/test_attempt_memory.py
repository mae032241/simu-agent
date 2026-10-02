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


def science_system(tmp_path):
    from tests.operations.test_tcad_result_analysis import analysis_system
    from tests.operations.research_loop_fixtures import authorize_loop
    from tests.operations import test_m2_curve_analysis_boundary as curve
    system=analysis_system(tmp_path)
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


def test_history_original_registers_real_citation_then_final_manifest_and_missing_are_not_success(tmp_path):
    system=science_system(tmp_path)
    _,runtime,root,_,_,_=system
    early,opened=science_worker(system,'early-science')
    complete_science(early,opened)
    middle,opened=science_worker(system,'middle-science')
    complete_science(middle,opened)
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


def test_failed_condition_original_cross_page_changed_input_retry_and_scope_negatives(tmp_path,monkeypatch):
    from scidiscovery.artifact_agent.service import runs as run_service
    system=science_system(tmp_path)
    _,runtime,root,_,artifacts,register=system
    failed,opened=science_worker(system,'early-failure')
    value=runtime.runs.status(failed._run_id)
    terminal_clock=run_service.timestamp()
    # The chronological fixture deliberately ties wall-clock timestamps;
    # durable terminal event order must still page every exact task once.
    with monkeypatch.context() as patch:
        patch.setattr(run_service,'timestamp',lambda:terminal_clock)
        runtime.runs.record_failure(failed._run_id,reason='Fixture engineering failure under original finite conditions',expected_state='running',expected_last_activity_at=value.last_activity_at)
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
    while pages[-1]['next_before']:
        assert len(pages)<3, 'Exact two-task index must not repeat or loop.'
        pages.append(worker.call_tool('worker_read_history',dict(limit=1,before=pages[-1]['next_before'])))
    with closing(runtime.runs._connect()) as db:
        terminals=[dict(i) for i in db.execute('SELECT r.run_id,r.state,r.completed_at,a.activity,a.recorded_at,a.rowid AS event FROM runs r JOIN run_activity a USING(run_id) WHERE a.activity IN (\'framework_failure\',\'completion_committed\')')]
    metrics('condition-history',dict(pages=pages,memory=runtime.runs._worker_memory_binding(identity),terminals=terminals))
    assert len(terminals)==2 and {i['completed_at'] for i in terminals}=={terminal_clock}
    assert all(i['recorded_at']==terminal_clock for i in terminals)
    names=[i['name'] for p in pages for i in p['runs']]
    assert names==['unrelated-terminal','early-failure'] and len(set(names))==2
    early=pages[-1]
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
