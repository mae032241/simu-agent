"""Existing foreground runner against source UI/MCP routes; no native process/model."""
from copy import deepcopy
import json
import re
import sqlite3
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from scripts import accept_progression as entry
from scripts import accept_b6 as suite
from scripts.acceptance_native_cases import NativeCaseJourney,case_objective
from scripts.accept_progression_recovery import RecoveryJourney
from scripts.b6_evidence import digest, write
from tests.operations.test_m6a_direct_instance_management import _setup, _root, _request

SOURCE='e07d6f080efbd56d3f01f0245c2d42deba602935'


def expired_wait(r,*,objective=None):
    j=r.journey;r.select()
    j.platform_session=j.thread
    r.root.call_tool('artifact_ingest_text',dict(name='acceptance.objective',text=objective or case_objective(r.case),on_conflict='reject'))
    with sqlite3.connect(j.root/'state/database/scheduler-bindings.sqlite3') as db:
        assert json.loads(db.execute('SELECT config_json FROM scheduler_progression').fetchone()[0])=={}
    old=j.logdir.parent
    write(old/'summary.json',dict(status='failed',failure_type='TimeoutError',diagnostic='instance_wait_timeout',rpc_error=None))
    write(old/'resource.json',dict(returncode=1,stop_reason='exited',elapsed_seconds=912))
    write(old/'thread.json',dict(thread_id=j.thread,session_id=j.platform_session))
    write(old/'started-threads.json',[])
    write(old/'usage.json',dict(threads={},items=[]))
    write(j.root/'progress.json',dict(state='awaiting_user',management_url=j.current_instance()['management_url'],evidence=str(old)))
    return old


def wait_suite(r):
    j=r.journey;old=expired_wait(r);case_id=j.root.name;root=j.root.parent
    r.case.update(human_wait_seconds=900,baseline_digest='frozen-state',conditions_digest='frozen-conditions')
    write(j.root/'acceptance-case.json',r.case)
    budget=dict(total_tokens=2000000,uncached_tokens=200000,execution_seconds=1200)
    manifest=dict(harness_digest='old-harness',freeze_identity=r.case['freeze_identity'],prior_attempt_costs=[],
        config=dict(instance=r.case['instance'],cases={case_id:dict(requires=['sealed_delivery'])},budget=dict(suite=budget,session=budget)))
    write(root/'suite.json',manifest)
    write(root/(case_id+'.prepared.json'),dict(case_digest=digest(r.case)))
    write(root/(case_id+'.attempt.json'),dict(original=True))
    write(root/(case_id+'.exit.json'),dict(returncode=1))
    write(root/(case_id+'.result.json'),dict(status='not_observed'))
    write(j.root/'host-resources.json',dict(startup_timeout_seconds=120,instance_wait_timeout_seconds=900,execution_timeout_seconds=1200))
    return root,manifest,case_id,old


@pytest.mark.parametrize('bad',['model','turn','grant','unknown','objective','identity','rpc'])
def test_wait_resume_rejects_unsafe_source_through_actual_bootstrap_routes(runner,bad):
    r=runner;j=r.journey;old=expired_wait(r,objective='Different original' if bad=='objective' else None)
    if bad=='model':(j.root/'model-submission-started').touch()
    elif bad=='turn':write(old/'started-threads.json',[j.thread])
    elif bad=='grant':r.command('pause');r.grant()
    elif bad=='unknown':
        with sqlite3.connect(j.root/'state/database/scheduler-bindings.sqlite3') as db:
            db.execute('UPDATE scheduler_progression SET checkpoint_json=?',(json.dumps(dict(fault_class='outcome_unknown')),))
    elif bad=='objective':
        assert r.root.call_tool('artifact_catalog',dict(name='acceptance.objective',view='content'))['text']=='Different original'
    elif bad=='identity':write(old/'thread.json',dict(thread_id=j.thread,session_id='different'))
    else:write(old/'summary.json',dict(status='failed',failure_type='TimeoutError',diagnostic='instance_wait_timeout',rpc_error={'unknown':True}))
    with pytest.raises(ValueError,match='wait_resume_'):
        entry.wait_source(j.root,r.case,old)
    assert not (j.root/'wait-resume-1').exists()


@pytest.mark.parametrize('outcome',['grant','fast_grant','identity','stop','status_grant','loop_status_grant',
    'status_wrong_owner','status_wrong_goal','status_wrong_config','status_unknown'])
def test_wait_resume_new_native_session_reuses_exact_objective_via_real_ui(runner,monkeypatch,outcome):
    from scidiscovery.platforms.codex_root_host import CodexRootHost
    r=runner;j=r.journey;old=expired_wait(r)
    old_hash={p.name:entry.file_hash(p) for p in old.glob('*.json')}
    source=entry.wait_source(j.root,r.case,old)
    j.wait_resume=dict(source=source,human_wait_seconds=3600,human_poll_seconds=r.case['effective_settings']['progression']['poll_seconds'])
    j.resources['instance_wait_timeout_seconds']=3600
    j.logdir=j.root/'wait-resume-1/fixture-logs';j.logdir.mkdir(parents=True)
    j.__class__=NativeCaseJourney
    current=_root(r.runtime,session_key='sch_'+'2'*32,secret=r.secret,base=r.base)
    requests=[]
    def initialize(host,*args,**kw):
        assert kw==dict(check_native=False)
        def rpc(method,params):
            requests.append(method)
            assert method=='thread/start' and params['ephemeral'] is False and 'threadId' not in params
            return dict(thread=dict(id='new-actual-thread',sessionId='invalid' if outcome=='identity' else 'new-actual-thread'))
        native=CodexRootHost(SimpleNamespace(on_event=lambda _:None,rpc=rpc,failed=False));native._initialized=True
        identity=native.open_root(cwd=str(j.root))
        j.thread,j.platform_session=identity.thread_id,identity.session_id
        def mcp(method,params):
            assert method=='mcpServer/tool/call' and params['threadId']==identity.thread_id
            assert params['_meta']['x-codex-turn-metadata']==dict(session_id=identity.session_id,thread_id=identity.thread_id)
            name=params['arguments']['name'];r.calls.append(name)
            return dict(structuredContent=current.call_tool(name,params['arguments']['arguments']))
        j.rpc=mcp
        return j.current_instance()
    monkeypatch.setattr(entry.Host,'initialize_host',initialize)
    pumps=[]
    def pump():
        assert not (j.root/'model-submission-started').exists()
        pumps.append(1)
        if len(pumps)==1:
            r.select_existing(current,r.case['instance'])
            r.command('takeover',current)
            if outcome=='fast_grant':
                r.command('pause',current);r.grant(router=current)
        elif outcome=='stop':r.command('stop',current)
        elif outcome=='loop_status_grant':pass
        elif len(pumps)==2:r.command('pause',current)
        else:r.grant(router=current)
    j.pump=pump
    original=j.call
    statuses=[]
    def call(name,args):
        if name=='progression_command':
            assert args['command']=='start' and len(pumps)==dict(fast_grant=1,status_grant=1,loop_status_grant=2).get(outcome,3)
            raise RuntimeError('fixture_model_boundary')
        value=original(name,args)
        if name=='progression_status':
            statuses.append(value)
            index=2 if outcome=='loop_status_grant' else 1
            if len(statuses)==index and (outcome.startswith('status_') or outcome=='loop_status_grant'):
                assert not (value.get('loop') or {}).get('managed')
                if outcome=='status_wrong_goal':
                    current.call_tool('artifact_ingest_text',dict(name='other.objective',text='Other original',on_conflict='reject'))
                r.command('pause',current)
                r.grant(objective='other.objective' if outcome=='status_wrong_goal' else 'acceptance.objective',router=current)
                if outcome=='status_wrong_owner':
                    other=_root(r.runtime,session_key='sch_'+'3'*32,secret=r.secret,base=r.base)
                    r.select_existing(other,r.case['instance']);r.command('takeover',other)
                elif outcome in {'status_wrong_config','status_unknown'}:
                    with sqlite3.connect(j.root/'state/database/scheduler-bindings.sqlite3') as db:
                        field='config_json' if outcome=='status_wrong_config' else 'checkpoint_json'
                        changed=json.loads(db.execute('SELECT '+field+' FROM scheduler_progression').fetchone()[0])
                        if field=='config_json':changed['effective']['defaults']['model']='other'
                        else:changed['fault_class']='outcome_unknown'
                        db.execute('UPDATE scheduler_progression SET '+field+'=?',(json.dumps(changed),))
        return value
    j.call=call
    expected={'identity':'actual_root_identity_invalid','stop':'user_stop','status_wrong_owner':'bootstrap_owner_changed',
        'status_wrong_goal':'loop_authorization_mismatch','status_wrong_config':'wait_resume_requires_unspent_known_bootstrap',
        'status_unknown':'wait_resume_requires_unspent_known_bootstrap'}.get(outcome,'fixture_model_boundary')
    with pytest.raises((RuntimeError,ValueError),match=expected):
        j.run_case()
    assert requests==['thread/start']
    assert 'artifact_ingest_text' not in r.calls
    assert old_hash=={p.name:entry.file_hash(p) for p in old.glob('*.json')}
    if outcome in {'grant','fast_grant','status_grant','loop_status_grant'}:
        status=current.call_tool('progression_status',{});clock=j.phase_deadline
        j.confirm_loop(status,'acceptance.objective')
        assert j.phase_deadline<=clock
    else:assert not (j.root/'model-submission-started').exists()


@pytest.mark.parametrize('outcome',['ok','exhausted','failed'])
def test_resume_wait_link_preserves_old_records_uses_exact_output_and_checks_suite_budget(runner,monkeypatch,outcome):
    import os
    r=runner;j=r.journey;root,manifest,case_id,old=wait_suite(r)
    monkeypatch.setattr(suite,'serial_lock',lambda:entry.guard.serial_lock(int(os.environ['SCID_TEST_LOCK_FD'])))
    protected=[root/'suite.json',root/(case_id+'.attempt.json'),root/(case_id+'.exit.json'),root/(case_id+'.result.json'),
        j.root/'acceptance-case.json',j.root/'host-resources.json',*[p for p in old.glob('*.json')]]
    before={str(p):entry.file_hash(p) for p in protected}
    launched=[]
    real_run=suite.subprocess.run
    def start(command,**kw):
        if command[0]=='git':return real_run(command,**kw)
        launched.append(command)
        link=root/(case_id+'.resume-wait.json');record=json.loads(link.read_text())
        assert record['human_wait_seconds']==3600 and record['original_harness_digest']=='old-harness'
        monkeypatch.setattr(entry,'preflight',lambda:dict(blockers=[]))
        monkeypatch.setattr(entry.sys,'argv',command[1:])
        def guarded(command,env,limits,output,*args,**kwargs):
            assert limits['timeout_seconds']==4920
            write(output/'summary.json',dict(status='source_fixture',checks={}))
            return dict(returncode=1 if outcome=='failed' else 0,stop_reason='exited',elapsed_seconds=1)
        monkeypatch.setattr(entry.guard,'run_one',guarded)
        return SimpleNamespace(returncode=entry.main())
    monkeypatch.setattr(suite.subprocess,'run',start)
    if outcome=='exhausted':
        manifest['prior_attempt_costs']=[dict(costs=dict(total_tokens=2000000,uncached_tokens=200000,execution_seconds=1200))]
        with pytest.raises(ValueError,match='acceptance_suite_budget_insufficient'):
            suite.resume_wait(root,manifest,case_id,old,3600)
        assert not launched and not (root/(case_id+'.resume-wait.json')).exists()
    else:
        assert suite.resume_wait(root,manifest,case_id,old,3600)==(1 if outcome=='failed' else 0)
        report=suite.result(root,manifest,case_id)
        assert report['evidence']!=str(old) and report['wait_resume']['human_wait_seconds']==3600
        assert report['resource']['elapsed_seconds']==0 and report['usage']['coverage'] in {'missing','partial'}
        if outcome=='failed':
            progress=json.loads((j.root/'progress.json').read_text())
            assert progress['state']=='failed' and 'management_url' not in progress and progress['model_requests']==0
        with pytest.raises(FileExistsError):suite.resume_wait(root,manifest,case_id,old,3600)
        assert len(launched)==1
        record=json.loads((root/(case_id+'.resume-wait.json')).read_text())
        record['output']=str(root/'foreign-output');write(root/(case_id+'.resume-wait.json'),record)
        with pytest.raises(ValueError,match='wait_resume_link_mismatch'):suite.result(root,manifest,case_id)
    assert before=={str(p):entry.file_hash(p) for p in protected}


@pytest.fixture
def runner(tmp_path, monkeypatch):
    runtime, _, secret, ui, base=_setup(tmp_path)
    root=_root(runtime, session_key='sch_'+'1'*32, secret=secret, base=base)
    from scidiscovery.agent_execution_settings import effective_settings,parse_settings
    settings=effective_settings(runtime.scheduler_bindings.global_settings,{})
    runtime.scheduler_bindings.global_settings=parse_settings(settings)
    ui.read_model=SimpleNamespace(artifacts=runtime.artifacts,runs=runtime.runs,executions=runtime.executions,
        bindings=runtime.scheduler_bindings,progression_status=lambda instance,**kw:
        runtime.scheduler_bindings.progression_status(instance_id=instance,**kw))
    write(tmp_path/'agent-settings.json',settings)
    limits=settings['progression']
    candidate=dict(head=SOURCE,profile=dict(model=limits['root_model'],model_reasoning_effort=limits['root_reasoning_effort']))
    write(tmp_path/'candidate.json',candidate)
    case=dict(instance='b0a-calibration',poll_seconds=.01,text='Frozen synthetic observations (0,1),(1,3),(2,5).',
        progression=limits,effective_settings=settings,agent_settings_digest=digest(settings),candidate_digest=digest(candidate),
        freeze_identity=dict(candidate_source_commit=SOURCE,control_schema=9,platform=dict(version='fixture',executable_sha256='fixture')),
        scenario='autonomous',multi_task=True)
    journey=entry.Journey.__new__(entry.Journey)
    journey.root=tmp_path
    journey.case_config=case
    journey.resources=dict(execution_timeout_seconds=1200,instance_wait_timeout_seconds=900)
    journey.phase='startup'; journey.phase_deadline=entry.time.monotonic()+120
    journey.logdir=tmp_path/'journey-1/fixture-logs';journey.logdir.mkdir(parents=True)
    journey.thread='actual-native-thread';journey.platform_session='actual-native-session';journey.ui_url=base
    calls=[]
    def rpc(method,params):
        assert method=='mcpServer/tool/call'
        assert params['threadId']==journey.thread
        assert params['_meta']['x-codex-turn-metadata']==dict(session_id=journey.platform_session,thread_id=journey.thread)
        name=params['arguments']['name'];calls.append(name)
        return dict(structuredContent=root.call_tool(name,params['arguments']['arguments']))
    journey.rpc=rpc
    monkeypatch.setattr(entry.time,'sleep',lambda _:None)
    def form(router=None):
        url=urlparse((router.call_tool('instance_current',{}) if router else journey.current_instance())['management_url'])
        status,_,raw=_request(base,'GET',url.path+'?'+url.query)
        assert status==200
        return dict(capability=parse_qs(url.query)['capability'][0],csrf=ui.session_id),raw.decode()
    def select():
        values,_=form()
        status,_,_=_request(base,'POST','/instances/create',form=dict(values,name=case['instance'],
            title='Source acceptance fixture',objective=case['text']))
        assert status==303
    def select_existing(router,name):
        values,_=form(router)
        values=dict(values,name=name)
        status,_,raw=_request(base,'POST','/instances/select',form=values)
        if status==200:
            expected=re.search(rb"name='expected_binding' value='([^']+)'",raw)[1].decode()
            status,_,raw=_request(base,'POST','/instances/select',form=dict(values,confirm_binding='yes',expected_binding=expected))
        assert status==303,raw
    def command(command,router=None):
        values,_=form(router)
        status,_,raw=_request(base,'POST','/instances/progression',form=dict(values,command=command))
        assert status==303,raw
    def grant(objective='acceptance.objective',router=None):
        values,page=form(router)
        page=page.split('data-loop-authorization>',1)[-1]
        match=re.search(r"name='confirmation_binding' value='([^']+)'",page)
        assert match, 'UI loop budget proposal unavailable'
        binding=match[1]
        instance=runtime.scheduler_bindings.session_instance(session_key=(router or root).facade.session_key)
        status,_,raw=_request(base,'POST','/instances/progression',form=dict(values,instance_id=instance,
            command='authorize_loop',confirmation_binding=binding,objective_name=objective,confirm_loop_budget='yes'))
        assert status==303,raw
    try:
        yield SimpleNamespace(journey=journey,root=root,runtime=runtime,case=case,calls=calls,select=select,grant=grant,
            form=form,command=command,select_existing=select_existing,base=base,secret=secret)
    finally:
        ui.stop()


def test_runner_waits_for_selected_instance_and_ui_budget_then_preserves_clock(runner):
    r=runner;j=r.journey
    observed=[]
    def pump():
        progress=json.loads((j.root/'progress.json').read_text())
        observed.append(progress['next_step'])
        assert not (j.root/'model-submission-started').exists()
        if len(observed)==1:r.select()
        elif len(observed)==2:
            assert 'artifact_ingest_text' in r.calls
            status=r.root.call_tool('progression_status',{})
            assert status['state']=='active' and not (status.get('loop') or {}).get('managed')
        elif len(observed)==3:r.command('pause')
        elif len(observed)==4:
            status=r.root.call_tool('progression_status',{})
            assert status['state']=='paused' and not (status.get('loop') or {}).get('managed')
            r.grant()
        else:pytest.fail('grant did not release existing foreground runner')
    j.pump=pump
    j.await_loop_authorization(j.current_instance(),objective_name='acceptance.objective',text=r.case['text'])
    assert observed==['select_or_create_instance']+['pause_bootstrap_then_confirm_loop_budget']*3
    status=r.root.call_tool('progression_status',{})
    assert status['state']=='paused' and status['reason']=='loop_authorized'
    deadline=j.phase_deadline;identity=deepcopy(j.loop_identity)
    j.confirm_loop(status,'acceptance.objective')
    assert j.phase_deadline<=deadline and j.loop_identity==identity
    assert status['loop']['authorized_at']==identity['authorized_at']
    assert set(r.calls)<= {'instance_current','artifact_ingest_text','progression_status'}


@pytest.mark.parametrize('selected',[False,True])
def test_cancel_wait_never_requests_model_or_start(runner,selected):
    r=runner;j=r.journey
    if selected:r.select()
    def pump():
        (j.root/'stop').touch()
        entry.Host.checkpoint(j)
    j.children=[];j.pump=pump
    with pytest.raises(RuntimeError,match='user_stop'):
        j.await_loop_authorization(j.current_instance(),objective_name='acceptance.objective',text=r.case['text'])
    assert not (j.root/'model-submission-started').exists()


def test_public_stop_during_budget_wait_does_not_launch_model(runner):
    r=runner;j=r.journey;r.select()
    j.pump=lambda:r.root.call_tool('progression_command',dict(command='stop'))
    with pytest.raises(RuntimeError,match='user_stop'):
        j.await_loop_authorization(j.current_instance(),objective_name='acceptance.objective',text=r.case['text'])
    assert not (j.root/'model-submission-started').exists()


@pytest.mark.parametrize('race',['rebind','takeover'])
def test_http_binding_or_takeover_after_bootstrap_check_never_pauses_other_work(runner,race):
    r=runner;j=r.journey;r.select()
    other=_root(r.runtime,session_key='sch_'+'2'*32,secret=r.secret,base=r.base)
    if race=='rebind':
        values,_=r.form(other)
        assert _request(r.base,'POST','/instances/create',form=dict(values,name='other.active',
            title='Other active work',objective='Other user objective'))[0]==303
        other.call_tool('artifact_ingest_text',dict(name='other.objective',text='Other original',on_conflict='reject'))
    original=j.require_bootstrap_boundary
    competed=[]
    def boundary(value,*,owned=False):
        original(value,owned=owned)
        if owned:
            if race=='rebind':r.select_existing(r.root,'other.active')
            else:
                r.select_existing(other,r.case['instance'])
                r.command('takeover',other)
            competed.append(other.call_tool('progression_status',{}))
    j.require_bootstrap_boundary=boundary
    def pump():raise RuntimeError('fixture_wait_ended')
    j.pump=pump
    with pytest.raises(RuntimeError,match='selected_instance_changed|bootstrap_owner_changed'):
        j.await_loop_authorization(j.current_instance(),objective_name='acceptance.objective',text=r.case['text'])
    assert len(competed)==1
    after=other.call_tool('progression_status',{})
    assert after['state']==competed[0]['state']=='active'
    assert after['can_schedule'] and competed[0]['can_schedule']
    assert 'progression_command' not in r.calls
    assert not (j.root/'model-submission-started').exists()


@pytest.mark.parametrize('mismatch',['schema','candidate','settings','goal','loop','effective'])
def test_runner_rejects_mismatched_frozen_authority_before_model(runner,mismatch):
    r=runner;j=r.journey
    r.select()
    if mismatch=='schema':
        with sqlite3.connect(j.root/'state/database/scheduler-bindings.sqlite3') as db:db.execute('PRAGMA user_version=8')
    elif mismatch=='candidate':r.case['freeze_identity']['candidate_source_commit']='other'
    elif mismatch=='settings':write(j.root/'agent-settings.json',{})
    elif mismatch=='effective':r.case['effective_settings']['defaults']['model']='other'
    if mismatch=='goal':
        original_call=j.call
        def ingest_both(name,args):
            value=original_call(name,args)
            if name=='artifact_ingest_text':
                original_call(name,dict(name='other',text='Other exact frozen original',on_conflict='reject'))
            return value
        j.call=ingest_both
    def pump():
        r.command('pause')
        r.grant('other' if mismatch=='goal' else 'acceptance.objective')
    j.pump=pump
    if mismatch=='loop':
        original=j.confirm_loop
        def confirm(status,objective):
            status=deepcopy(status);status['loop']['limits']['max_calendar_seconds']+=1
            original(status,objective)
        j.confirm_loop=confirm
    with pytest.raises((ValueError,RuntimeError),match='schema_9|revision_mismatch|settings_changed|authorization_mismatch|config_or_goal_changed'):
        j.await_loop_authorization(j.current_instance(),objective_name='acceptance.objective',text=r.case['text'])
    assert not (j.root/'model-submission-started').exists()


@pytest.mark.parametrize('existing',['active','other_owner','unknown'])
def test_selected_existing_work_is_rejected_without_ingest_pause_or_model(runner,existing):
    r=runner;j=r.journey;r.select()
    bindings=r.runtime.scheduler_bindings
    instance=bindings.session_instance(session_key=r.root.facade.session_key)
    owner=r.root.facade.session_key
    if existing=='other_owner':
        owner='sch_'+'2'*32
        bindings.bind_session(session_key=owner,instance_id=instance)
    bindings.progression_command(instance_id=instance,session_key=owner,command='start',mode='interactive')
    if existing=='unknown':
        bindings.progression_command(instance_id=instance,session_key=owner,command='pause')
        with bindings._connect() as db:
            db.execute('UPDATE scheduler_progression SET checkpoint_json=? WHERE instance_id=?',
                (json.dumps(dict(fault_class='outcome_unknown')),instance))
    before=bindings.progression_status(instance_id=instance,internal=True)
    calls=len(r.calls)
    with pytest.raises(RuntimeError,match='quiescent_unspent'):
        j.await_loop_authorization(j.current_instance(),objective_name='acceptance.objective',text=r.case['text'])
    assert set(r.calls[calls:])=={'instance_current'}
    assert bindings.progression_status(instance_id=instance,internal=True)==before
    assert not (j.root/'model-submission-started').exists()


@pytest.mark.parametrize('kind',['autonomous','manual','recovery'])
def test_actual_journey_entry_checks_grant_before_first_submission(runner,kind):
    r=runner;j=r.journey
    journey_type=RecoveryJourney if kind=='recovery' else NativeCaseJourney
    j.__class__=journey_type
    j.case_config.update(scenario=kind,stage_timeout_seconds=90,max_observed_runs=32)
    j.initialize_host=lambda **kw:j.current_instance()
    model=[]
    def start_turn(prompt):model.append(prompt);raise RuntimeError('fixture_model_boundary')
    j.root_host=SimpleNamespace(start_turn=start_turn)
    def pump():
        assert not model and not (j.root/'model-submission-started').exists()
        if r.root.call_tool('instance_current',{})['state']=='unbound':r.select()
        else:
            objective='acceptance.root-recovery.objective' if kind=='recovery' else 'acceptance.objective'
            r.command('pause')
            r.grant(objective)
    j.pump=pump
    original=j.call
    def call(name,args):
        if name=='progression_command' and args['command']=='start':
            assert (j.logdir.parent/'loop-authorization.json').exists()
            if kind!='manual':raise RuntimeError('fixture_model_boundary')
        return original(name,args)
    j.call=call
    with pytest.raises(RuntimeError,match='fixture_model_boundary'):
        j.run_recovery() if kind=='recovery' else j.run_case()
    assert (j.root/'model-submission-started').exists()
    assert bool(model)==(kind=='manual')
    assert 'progression_command' in r.calls if kind=='manual' else 'artifact_ingest_text' in r.calls


def test_config_freezes_explicit_time_review_token_recovery_without_relabeling_s0():
    config=suite.configuration(suite.SCRIPTS/'acceptance/scientific_progress.json')
    assert config['benchmark']['baseline_commit']=='c00706f'
    assert config['benchmark']['candidate_source_commit']==SOURCE
    assert config['benchmark']['stage']=='S0'
    assert config['benchmark']['freeze_status']=='source_frozen_execution_pending'
    assert config['human_wait_seconds']==900
    assert config['progression']['max_calendar_seconds']==config['budget']['session']['execution_seconds']==1200
    assert config['progression']['max_tokens']==config['budget']['session']['total_tokens']
    assert config['progression']['max_reviews']==2
    assert config['progression']['root_model']=='gpt-5.6-sol'
    assert config['progression']['recover_failed_turns'] is False


def test_prepare_freezes_candidate_runner_and_installed_settings_and_report_wait_time(tmp_path,monkeypatch):
    from scripts.root_host_upgrade import snapshot_state
    from scidiscovery.agent_execution_settings import ProgressionSettings,effective_settings,parse_settings
    source=tmp_path/'source';source.mkdir()
    runtime,_,_,ui,_=_setup(source)
    ui.stop()
    settings=effective_settings(runtime.scheduler_bindings.global_settings,{})
    write(source/'agent-settings.json',settings)
    (source/'approval-secret').write_bytes(b'x'*32)
    program=dict(head=SOURCE,project=str(source/'project'),python='unused-installed-python',wheels={'fixture.whl':'fixture'},
        profile=dict(model='gpt-5.6-sol',model_reasoning_effort='high'))
    write(source/'candidate.json',program)
    platform=dict(version='fixture-only',executable_sha256='fixture-binary')
    monkeypatch.setattr(entry,'platform_identity',lambda:platform)
    checked=[]
    def contract(program,settings_file=None,instance_settings=None):
        checked.append(settings_file)
        value=dict(control_schema=9,progression_fields=sorted(ProgressionSettings.model_fields))
        if settings_file:
            value['effective_settings']=effective_settings(parse_settings(json.loads(settings_file.read_text())),instance_settings)
        return value
    monkeypatch.setattr(suite,'installed_contract',contract)
    root=tmp_path/'suite'
    config=suite.SCRIPTS/'acceptance/scientific_progress.json'
    suite.initialize(root,config,source,source,None)
    manifest=json.loads((root/'suite.json').read_text())
    def copy(command,**kw):
        assert 'prepare-upgrade' in command
        target=root/'manual-stagnation-1';target.mkdir()
        receipt=snapshot_state(source,target)
        write(target/'state-snapshot.json',receipt)
        write(target/'candidate.json',{**program,'project':str(target/'project')})
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(suite.subprocess,'run',copy)
    suite.prepare(root,manifest,'manual-stagnation-1')
    target=root/'manual-stagnation-1';frozen=json.loads((target/'acceptance-case.json').read_text())
    assert frozen['freeze_identity']['candidate_source_commit']==SOURCE
    assert frozen['freeze_identity']['runner_digest']==manifest['harness_digest']
    assert frozen['baseline_digest']==manifest['baseline_digest']
    assert frozen['conditions_digest']==manifest['conditions_digest']
    assert checked==[None,target/'agent-settings.json']
    assert not {'quality','auto_checks','grading','objectives'} & frozen.keys()
    assert frozen['effective_settings']['progression']['max_calendar_seconds']==1200
    assert json.loads((target/'host-resources.json').read_text())['instance_wait_timeout_seconds']==900
    entry.validate_candidate(target,frozen)
    waiting=suite.result(root,manifest,'manual-stagnation-1')
    assert waiting['attempt']=='not_started' and waiting['status']=='not_observed'
    assert all(waiting[key]==frozen[key] for key in ('freeze_identity','baseline_digest','conditions_digest'))
    unprepared=suite.result(root,manifest,'auto-stagnation-1')
    assert unprepared['attempt']=='not_started'
    assert all(unprepared[key]==manifest[key] for key in ('freeze_identity','baseline_digest','conditions_digest'))
    journey=target/'journey-1';journey.mkdir()
    write(journey/'summary.json',dict(status='evidence_ready',checks={}))
    write(journey/'resource.json',dict(elapsed_seconds=1800,returncode=0,stop_reason='exited',observed_tree_rss_high_water_bytes=123))
    write(root/'manual-stagnation-1.exit.json',dict(returncode=0))
    waiting=suite.result(root,manifest,'manual-stagnation-1')
    assert waiting['resource']['elapsed_seconds']==0
    assert waiting['resource']['supervisor_elapsed_seconds']==1800
    (target/'model-submission-started').touch()
    write(journey/'execution-time.json',dict(elapsed_seconds=120,human_wait_included=False))
    report=suite.result(root,manifest,'manual-stagnation-1')
    assert report['resource']['elapsed_seconds']==120
    assert report['resource']['observed_tree_rss_high_water_bytes']==123
    assert report['usage']['coverage'] in {'missing','partial'}
    assert not report['usage']['groups']
    assert report['status']=='not_observed'


def test_installed_schema_and_supervisor_human_wait_are_checked_without_native_launch(runner,monkeypatch):
    monkeypatch.setattr(suite.subprocess,'check_output',lambda *a,**k:json.dumps(dict(control_schema=8)))
    with pytest.raises(ValueError,match='installed_candidate_requires_control_schema_9'):
        suite.installed_contract(dict(python='not-launched',project='.'))
    j=runner.journey
    __import__('shutil').rmtree(j.logdir.parent)
    write(j.root/'case.json',runner.case)
    monkeypatch.setattr(entry.sys,'argv',['accept_progression','--candidate',str(j.root),'--case-file',str(j.root/'case.json'),
        '--scenario','autonomous','--lock-fd',__import__('os').environ['SCID_TEST_LOCK_FD']])
    monkeypatch.setattr(entry,'preflight',lambda:dict(blockers=[]))
    monkeypatch.setattr(entry,'host_resources',lambda root:dict(startup_timeout_seconds=120,instance_wait_timeout_seconds=900,execution_timeout_seconds=1200))
    observed=[]
    def guarded(command,environment,limits,*args,**kw):
        observed.append(limits['timeout_seconds'])
        return dict(returncode=0,stop_reason='exited',elapsed_seconds=0)
    monkeypatch.setattr(entry.guard,'run_one',guarded)
    assert entry.main()==0
    assert observed==[2220]
    assert not (j.root/'model-submission-started').exists()


@pytest.mark.parametrize('schema',[9,8])
def test_rollback_prepare_freezes_actual_program_and_state_identity_or_rejects_old_schema(tmp_path,monkeypatch,schema):
    from scripts.root_host_upgrade import snapshot_state
    from scidiscovery.agent_execution_settings import ProgressionSettings,effective_settings,parse_settings
    root=tmp_path/'suite';root.mkdir()
    source=root/'managed';source.mkdir()
    runtime,_,_,ui,_=_setup(source);ui.stop()
    settings=effective_settings(runtime.scheduler_bindings.global_settings,{})
    write(source/'agent-settings.json',settings)
    (source/'approval-secret').write_bytes(b'x'*32)
    current=dict(head=SOURCE,project=str(source/'project'),python='never-launch',wheels={'current.whl':'current'},
        profile=dict(model='gpt-5.6-sol',model_reasoning_effort='high'))
    write(source/'candidate.json',current)
    previous=tmp_path/'previous';previous.mkdir()
    old={**current,'head':'different-schema9-program-head','wheels':{'previous.whl':'previous'}}
    write(previous/'candidate.json',old)
    manifest=dict(source=str(source),installed=str(source),previous=str(previous),
        config=suite.configuration(suite.SCRIPTS/'acceptance/b6.json'),conditions_digest='current-program-conditions',
        source_settings_digest=digest(settings),freeze_identity=dict(candidate_source_commit=SOURCE,state_source_commit=SOURCE,
            control_schema=9,runner_source_commit=SOURCE,runner_digest='frozen-runner',platform={'fixture':'platform'},
            installed_contract={'control_schema':9,'progression_fields':sorted(ProgressionSettings.model_fields)}))
    actual_result=suite.result
    monkeypatch.setattr(suite,'result',lambda *a:dict(status='passed'))
    prepared=[]
    def copy(command,**kw):
        prepared.append(command)
        target=root/'rollback';target.mkdir()
        write(target/'state-snapshot.json',snapshot_state(source,target))
        write(target/'candidate.json',{**old,'project':str(target/'project')})
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(suite.subprocess,'run',copy)
    def installed(command,**kw):
        assert command[0]=='never-launch'
        value=dict(control_schema=schema,progression_fields=sorted(ProgressionSettings.model_fields))
        if len(command)>4:
            value['effective_settings']=effective_settings(parse_settings(json.loads(__import__('pathlib').Path(command[4]).read_text())),json.loads(command[5]))
        return json.dumps(value)
    monkeypatch.setattr(suite.subprocess,'check_output',installed)
    if schema==8:
        with pytest.raises(ValueError,match='installed_candidate_requires_control_schema_9'):
            suite.prepare(root,manifest,'rollback')
        assert not prepared and not (root/'rollback.prepare.json').exists()
        assert json.loads((previous/'candidate.json').read_text())==old
    else:
        suite.prepare(root,manifest,'rollback')
        monkeypatch.setattr(suite,'result',actual_result)
        target=root/'rollback';frozen=json.loads((target/'acceptance-case.json').read_text())
        entry.validate_candidate(target,frozen)
        identity=frozen['freeze_identity']
        assert identity['candidate_source_commit']==old['head']
        assert identity['state_source_commit']==SOURCE
        assert identity['runner_digest']=='frozen-runner'
        assert identity['installed_contract']['control_schema']==9
        assert frozen['conditions_digest']!=manifest['conditions_digest']
        assert manifest['freeze_identity']['candidate_source_commit']==SOURCE
        report=suite.result(root,manifest,'rollback')
        assert report['status']=='not_observed' and report['attempt']=='not_started'
        assert report['freeze_identity']==frozen['freeze_identity']
        assert report['baseline_digest']==frozen['baseline_digest']
        assert report['conditions_digest']==frozen['conditions_digest']
