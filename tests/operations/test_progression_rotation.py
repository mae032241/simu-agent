"""Root rotation through the production factory and a bounded Python protocol peer."""
import json
import sys
import time

import pytest

from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerInstanceConflict
from scidiscovery.platforms.codex_progression import CodexProgressionFactory
from tests.operations.test_progression import progression, checkpoint, row
from tests.operations.research_loop_fixtures import authorize_loop


PEER = r'''
import hashlib,json,sys
from pathlib import Path
base=Path(sys.argv[1])
config=json.loads((base/'config.json').read_text())
state=json.loads((base/'state.json').read_text()) if (base/'state.json').exists() else {'threads':{},'next':0}
def emit(v): print(json.dumps(v),flush=True)
def save(): (base/'state.json').write_text(json.dumps(state))
for line in sys.stdin:
    msg=json.loads(line)
    with (base/'requests.jsonl').open('a') as log: log.write(json.dumps(msg)+'\n')
    if 'id' not in msg: continue
    method,p=msg['method'],msg['params']
    if method=='initialize': result={}
    elif method=='config/read': result={'config':config}
    elif method in ('thread/start','thread/resume'):
        if method=='thread/start':
            state['next']+=1
            thread='root-'+str(state['next'])
            state['threads'][thread]=[]
            save()
            mode=(base/'mode').read_text()
            if state['next']>1 and mode in {'late-usage','lost-opening-late'}:
                emit({'method':'thread/tokenUsage/updated','params':{'threadId':'root-1','tokenUsage':{'total':{
                  'inputTokens':175,'cachedInputTokens':75,'outputTokens':25}}}})
            if state['next']>1 and mode in {'lost-opening','lost-opening-late'}: sys.exit(0)
        else: thread=p['threadId']
        result={'thread':{'id':thread,'sessionId':thread},'approvalPolicy':p['approvalPolicy'],
          'sandbox':{'type':{'read-only':'readOnly','workspace-write':'workspaceWrite'}[p['sandbox']],
          'networkAccess':p.get('config',{}).get('sandbox_workspace_write',{}).get('network_access',False),'writableRoots':[]}}
    elif method=='thread/read':
        child_status=(base/'child-status').read_text() if (base/'child-status').exists() else 'completed'
        result={'thread':{'id':p['threadId'],'turns':state['threads'].get(p['threadId'],
          [] if child_status=='missing' else [{'id':'worker-turn','status':child_status}])}}
    elif method=='mcpServerStatus/list': result={'data':[{'name':'scidiscovery','tools':{'scid_catalog':{},'scid_describe':{},'scid_call':{}}}]}
    elif method=='mcpServer/tool/call':
        session='sch_'+hashlib.sha256(p['threadId'].encode()).hexdigest()[:32]
        result={'structuredContent':{'management_url':'http://127.0.0.1:8765/sessions/'+session+'?capability=test'}}
    elif method=='turn/start':
        thread=p['threadId']
        turn=thread+'-turn-'+str(len(state['threads'][thread])+1)
        state['threads'][thread].append({'id':turn,'status':'completed'});save()
        emit({'method':'turn/started','params':{'threadId':thread,'turn':{'id':turn}}})
        mode=(base/'mode').read_text()
        if mode in {'denial','user-input'}:
            request_method='item/commandExecution/requestApproval' if mode=='denial' else 'item/tool/requestUserInput'
            emit({'id':901,'method':request_method,'params':{'threadId':thread,'turnId':turn,'itemId':'request-1',
              'questions':[{'id':'condition','header':'Input','question':'Which original condition applies?'}]}})
            if mode=='denial':
                reply=json.loads(sys.stdin.readline())
                with (base/'requests.jsonl').open('a') as log: log.write(json.dumps(reply)+'\n')
        emit({'id':msg['id'],'result':{'turn':{'id':turn}}})
        emit({'method':'thread/tokenUsage/updated','params':{'threadId':thread,'tokenUsage':{'total':{
          'inputTokens':100*len(state['threads'][thread]),'cachedInputTokens':50*len(state['threads'][thread]),'outputTokens':20*len(state['threads'][thread])}}}})
        emit({'method':'turn/completed','params':{'threadId':thread,'turn':{'id':turn,'status':'completed'}}})
        continue
    elif method=='turn/interrupt': result={}
    else: raise RuntimeError(method)
    emit({'id':msg['id'],'result':result})
'''


def setup(p, tmp_path, **limits):
    from tests.operations.test_attempt_history import SECRET
    p.root.facade.instance_management_secret=SECRET
    bindings=p.runtime.scheduler_bindings
    settings=bindings.global_settings
    bindings.global_settings=settings.model_copy(update=dict(progression=settings.progression.model_copy(
        update={'root_rotate_after_rounds':1,'root_rotate_after_input_tokens':0,'progress_mode':'off',**limits})))
    p.root.call_tool('progression_command',dict(command='pause'))
    authorize_loop(p.runtime,p.instance,p.user,'goal')
    p.root.call_tool('progression_command',dict(command='start',mode='background',objective_name='goal'))
    native=tmp_path/'rotation-peer';native.mkdir()
    socket_path=tmp_path/'control.sock'
    directory=p.runtime.project_root/'.codex';directory.mkdir(exist_ok=True)
    config={'mcp_servers':{'scidiscovery':{'command':'scidiscovery-mcp-proxy','args':['--socket',str(socket_path)]}}}
    (directory/'config.toml').write_text('[mcp_servers.scidiscovery]\ncommand="scidiscovery-mcp-proxy"\nargs=["--socket",'+json.dumps(str(socket_path))+']\n')
    (native/'config.json').write_text(json.dumps(config))
    (native/'mode').write_text('normal')
    peer=native/'peer.py';peer.write_text(PEER)
    factory=CodexProgressionFactory(project_root=p.runtime.project_root,state_root=p.runtime.state_root,
        socket_path=socket_path,approval_base_url='http://127.0.0.1:8765',command=[sys.executable,str(peer),str(native)])
    p.coordinator.host_factory=factory
    return native,factory


def calls(native, method):
    return [json.loads(line)['params'] for line in (native/'requests.jsonl').read_text().splitlines()
        if json.loads(line).get('method')==method]


def completed(p):
    deadline=time.monotonic()+3
    while p.coordinator.host.poll(.01) is None:
        assert time.monotonic()<deadline


def wake(p, name='new-context'):
    p.root.call_tool('progression_message',dict(name=name,text='Retain this exact new condition.'))
    p.now[0]+=6
    p.coordinator.tick()


def test_factory_rotates_exact_writer_and_preserves_loop_positions(progression,tmp_path):
    p=progression
    native,_=setup(p,tmp_path)
    p.coordinator.tick();completed(p)
    old_root=p.root.__class__(p.facade(p.coordinator.host.scheduler_session))
    old=checkpoint(p)
    wake(p)
    rotated=checkpoint(p)
    assert json.loads(row(p)['host_json'])==dict(platform_session='root-2',thread_id='root-2')
    assert rotated['current_loop_id']==old['current_loop_id']
    assert rotated['rounds']==old['rounds']==1
    assert rotated['usage_records']['root-1']['retired']
    assert rotated['usage_records']['root-1']['counted_tokens']['input_tokens']==100
    assert rotated['processed_snapshot']==old['decision_snapshot']
    assert rotated['notified_snapshot']==old['notified_snapshot']
    assert len(calls(native,'thread/start'))==2 and len(calls(native,'turn/start'))==1
    with pytest.raises(SchedulerInstanceConflict,match='retired'):
        old_root.call_tool('progression_command',dict(command='takeover'))
    with pytest.raises(SchedulerInstanceConflict):
        old_root.call_tool('artifact_ingest_text',dict(name='late-write',text='old writer'))
    from tests.operations.test_local_worker_contracts import _invoke
    with pytest.raises(SchedulerInstanceConflict): _invoke(old_root,'late-admission')
    with pytest.raises(SchedulerInstanceConflict,match='retired'):
        old_root.call_tool('progression_report',dict(summary='late old judgment'))
    with pytest.raises(SchedulerInstanceConflict,match='retired'):
        old_root.call_tool('progression_message',dict(name='late-old-context',text='late old writer'))
    assert old_root.call_tool('progression_status',{})['state']=='active'
    p.now[0]+=6;p.coordinator.tick();completed(p)
    prompt=calls(native,'turn/start')[-1]['input'][0]['text']
    brief=json.loads(prompt.split('\n')[-1])
    assert brief['objective']['original']=='Compare exact data and retain limitations.'
    assert brief['user_messages'][0]['name']=='new-context'
    assert 'attempt_memory' in brief
    assert all(c['model']=='gpt-5.6-sol' and c['config']['model_reasoning_effort']=='high' for c in calls(native,'thread/start'))
    from tests.operations.test_run_list_bounds import metrics
    assert len(prompt.encode())<=json.loads(row(p)['config_json'])['effective']['progression']['context_bytes']
    metrics('root-rotation',dict(opened_root_threads=2,model_turns=2,rotated_startup_bytes=len(prompt.encode()),
        brief_bytes=len(json.dumps(brief,ensure_ascii=False).encode()),retired_input_tokens=100))


def test_factory_unknown_opening_never_replays_on_cold_start(progression,tmp_path):
    p=progression
    native,factory=setup(p,tmp_path)
    p.coordinator.tick();completed(p)
    (native/'mode').write_text('lost-opening')
    with pytest.raises(Exception): wake(p)
    failed=checkpoint(p)
    assert failed['phase']=='prepared' and failed['native_action']=='root_rotation'
    assert failed['fault_class']=='outcome_unknown' and row(p)['state']=='paused'
    assert row(p)['owner_session'] is None
    assert failed['rounds']==1 and json.loads(row(p)['host_json'])['thread_id']=='root-1'
    (native/'mode').write_text('normal')
    p.root.call_tool('progression_command',dict(command='resume'))
    from scidiscovery.artifact_agent.service.progression import ProgressionCoordinator
    restored=ProgressionCoordinator(runtime=p.runtime,host_factory=factory,facade_factory=p.facade,clock=lambda:p.now[0])
    try:
        restored.tick()
        assert restored.host is None and row(p)['reason']=='submission_unknown'
        assert len(calls(native,'thread/start'))==2 and len(calls(native,'turn/start'))==1
        assert checkpoint(p)['current_loop_id']==failed['current_loop_id']
    finally: restored.close()


@pytest.mark.parametrize('command',['pause','takeover'])
def test_human_control_wins_cas_during_known_empty_opening(progression,tmp_path,monkeypatch,command):
    p=progression
    native,_=setup(p,tmp_path)
    p.coordinator.tick();completed(p)
    bindings=p.runtime.scheduler_bindings
    complete=bindings.complete_host_rotation
    decided={}
    def race(**kwargs):
        p.root.call_tool('progression_command',dict(command=command))
        decided.update(row(p))
        return complete(**kwargs)
    monkeypatch.setattr(bindings,'complete_host_rotation',race)
    wake(p)
    after=row(p)
    assert (after['generation'],after['state'],after['mode'],after['owner_session'])==(
        decided['generation'],decided['state'],decided['mode'],decided['owner_session'])
    assert after['host_json'] is None and checkpoint(p)['phase']=='idle'
    assert checkpoint(p)['runtime_status']=='root_rotation_control_changed'
    assert p.coordinator.host is None
    p.coordinator.tick()
    assert row(p)==after
    assert len(calls(native,'thread/start'))==2 and len(calls(native,'turn/start'))==1


@pytest.mark.parametrize('command',['pause','stop'])
def test_known_empty_rotation_cleanup_settles_human_stop_time(progression,tmp_path,monkeypatch,command):
    p=progression
    native,_=setup(p,tmp_path)
    p.coordinator.tick();completed(p)
    original=checkpoint(p)
    loop=original['current_loop_id']
    deadline=original['loop_authorizations'][loop]['deadline_at']
    bindings=p.runtime.scheduler_bindings
    complete=bindings.complete_host_rotation
    decision={}
    def race(**kwargs):
        p.root.call_tool('progression_command',dict(command=command))
        decision.update(row(p))
        assert checkpoint(p)['enabled_at'] is not None  # Opening is still prepared/unknown here.
        p.now[0]+=4
        return complete(**kwargs)
    monkeypatch.setattr(bindings,'complete_host_rotation',race)
    wake(p)
    cp=checkpoint(p)
    for field in ('generation','state','mode','owner_session','reason'):
        assert row(p)[field]==decision[field]
    assert p.coordinator.host is None and row(p)['host_json'] is None and cp['phase']=='idle'
    assert cp['enabled_seconds']==10 and cp['enabled_at'] is None
    assert cp['loop_authorizations'][loop]['deadline_at']==deadline
    assert cp['loop_authorizations'][loop]['budget_snapshot']['elapsed_seconds']==10
    at_stop=p.root.call_tool('progression_status',{})['budget']
    p.now[0]+=100
    p.coordinator.tick()
    later=p.root.call_tool('progression_status',{})['budget']
    assert later['elapsed_seconds']==at_stop['elapsed_seconds']==10
    assert later['calendar_elapsed_seconds']==at_stop['calendar_elapsed_seconds']+100
    assert later['deadline_at']==deadline
    assert len(calls(native,'thread/start'))==2 and len(calls(native,'turn/start'))==1


def test_confirmed_protocol_denial_is_terminal_for_rotation(progression,tmp_path):
    p=progression
    native,_=setup(p,tmp_path)
    (native/'mode').write_text('denial')
    p.coordinator.tick();completed(p)
    assert checkpoint(p)['platform_requests'][0]['state']=='denied'
    replies=[json.loads(line) for line in (native/'requests.jsonl').read_text().splitlines()]
    assert dict(id=901,result=dict(decision='decline')) in replies
    wake(p)
    assert len(calls(native,'thread/start'))==2
    assert p.coordinator.host.identity.thread_id=='root-2'
    assert checkpoint(p)['platform_requests'][0]['state']=='denied'
    assert checkpoint(p)['rounds']==1 and len(calls(native,'turn/start'))==1


def test_pending_protocol_user_input_still_defers_rotation_after_resume(progression,tmp_path):
    p=progression
    native,_=setup(p,tmp_path)
    (native/'mode').write_text('user-input')
    p.coordinator.tick();completed(p)
    assert row(p)['state']=='paused' and checkpoint(p)['platform_requests'][0]['state']=='pending_user_input'
    p.root.call_tool('progression_command',dict(command='resume'))
    wake(p)
    assert len(calls(native,'thread/start'))==1
    assert all(v['state']=='pending_user_input' for v in checkpoint(p)['platform_requests'])
    assert not any(json.loads(line).get('id')==901 and 'result' in json.loads(line)
        for line in (native/'requests.jsonl').read_text().splitlines())


@pytest.mark.parametrize('state',['pending_user_input','unsupported','denial_prepared','unknown',None])
def test_platform_rotation_boundary_requires_confirmed_denied(state):
    from scidiscovery.artifact_agent.service.scheduling_control import has_unresolved_platform_requests
    assert not has_unresolved_platform_requests({})
    assert not has_unresolved_platform_requests(dict(platform_requests=[dict(state='denied')]))
    assert has_unresolved_platform_requests(dict(platform_requests=[dict(state='denied'),dict(state=state)]))


def test_known_thread_created_before_binding_fault_is_not_reopened(progression,tmp_path,monkeypatch):
    p=progression
    native,factory=setup(p,tmp_path)
    p.coordinator.tick();completed(p)
    def crash(**kwargs):
        raise RuntimeError('simulated process boundary after verified thread/start before binding')
    monkeypatch.setattr(p.runtime.scheduler_bindings,'complete_host_rotation',crash)
    with pytest.raises(RuntimeError,match='process boundary'): wake(p)
    old=checkpoint(p)
    assert old['fault_class']=='outcome_unknown' and old['phase']=='prepared'
    p.root.call_tool('progression_command',dict(command='resume'))
    p.coordinator.host_factory=factory
    p.coordinator.tick()
    assert row(p)['reason']=='submission_unknown' and p.coordinator.host is None
    assert len(calls(native,'thread/start'))==2 and len(calls(native,'turn/start'))==1
    assert checkpoint(p)['usage_records']['root-1']==old['usage_records']['root-1']


@pytest.mark.parametrize('command',['pause','takeover'])
def test_unknown_opening_records_fault_without_overwriting_human_decision(progression,tmp_path,monkeypatch,command):
    p=progression
    native,_=setup(p,tmp_path)
    p.coordinator.tick();completed(p)
    host=p.coordinator.host
    rotate=host.rotate_root
    decided={}
    def race():
        p.root.call_tool('progression_command',dict(command=command))
        decided.update(row(p))
        (native/'mode').write_text('lost-opening-late')
        rotate()
    monkeypatch.setattr(host,'rotate_root',race)
    with pytest.raises(Exception): wake(p)
    after=row(p)
    for key in ('generation','state','mode','owner_session','reason'):
        assert after[key]==decided[key]
    assert checkpoint(p)['fault_class']=='outcome_unknown' and checkpoint(p)['phase']=='prepared'
    late=checkpoint(p)['usage_records']['root-1']
    assert late['counted_tokens']['input_tokens']==175 and late['retired']
    assert checkpoint(p)['enabled_at']==json.loads(decided['checkpoint_json'])['enabled_at']
    assert len(calls(native,'thread/start'))==2 and len(calls(native,'turn/start'))==1


def test_late_usage_multiple_rotations_and_cold_identity_keep_same_budget(progression,tmp_path):
    p=progression
    native,factory=setup(p,tmp_path)
    p.coordinator.tick();completed(p)
    initial=checkpoint(p)
    (native/'mode').write_text('late-usage')
    wake(p,'message-1')
    cp=checkpoint(p)
    assert cp['usage_records']['root-1']['high_water']['input_tokens']==175
    assert cp['usage_records']['root-1']['role']=='root' and cp['usage_records']['root-1']['retired']
    p.now[0]+=6;p.coordinator.tick();completed(p)
    wake(p,'message-2')
    assert json.loads(row(p)['host_json'])['thread_id']=='root-3'
    before=checkpoint(p)
    p.coordinator.close()
    from scidiscovery.artifact_agent.service.progression import ProgressionCoordinator
    restored=ProgressionCoordinator(runtime=p.runtime,host_factory=factory,facade_factory=p.facade,clock=lambda:p.now[0])
    try:
        restored.tick()
        assert restored.host.identity.thread_id=='root-3'
        assert len(calls(native,'thread/start'))==3
        assert calls(native,'thread/resume')[-1]['threadId']=='root-3'
        cp=checkpoint(p)
        assert cp['processed_snapshot']==before['processed_snapshot'] and cp['notified_snapshot']==before['notified_snapshot']
        assert cp['rounds']==before['rounds']==2 and cp['attempts']==before['attempts']
        assert cp['current_loop_id']==initial['current_loop_id']
        assert cp['loop_authorizations'][cp['current_loop_id']]['config']==initial['loop_authorizations'][initial['current_loop_id']]['config']
        restored._event(dict(method='thread/tokenUsage/updated',params=dict(threadId='root-1',
            tokenUsage=dict(total=dict(inputTokens=200,cachedInputTokens=80,outputTokens=30)))))
        late=checkpoint(p)['usage_records']['root-1']
        assert late['role']=='root' and late['loop_id']==initial['current_loop_id'] and late['retired']
        assert late['counted_tokens']['input_tokens']==200
        p.now[0]+=6;restored.tick()
        deadline=time.monotonic()+3
        while restored.host.poll(.01) is None: assert time.monotonic()<deadline
        assert len(calls(native,'turn/start'))==3
        prompt=calls(native,'turn/start')[-1]['input'][0]['text']
        assert json.loads(prompt.split('\n')[-1])['user_messages']==[dict(name='message-2',original='Retain this exact new condition.')]
        restored.tick()
        assert checkpoint(p)['usage_summary']['groups']['root']['tokens']['input_tokens']==400
        assert len(calls(native,'turn/start'))==3
    finally: restored.close()


def test_cumulative_input_includes_cached_and_zero_disables_round_trigger(progression,tmp_path):
    p=progression
    native,_=setup(p,tmp_path,root_rotate_after_rounds=0,root_rotate_after_input_tokens=100)
    frozen=json.loads(row(p)['config_json'])['effective']['progression']
    assert frozen['root_rotate_after_rounds']==0 and frozen['root_rotate_after_input_tokens']==100
    p.coordinator.tick();completed(p)
    wake(p)
    assert len(calls(native,'thread/start'))==2
    old=checkpoint(p)['usage_records']['root-1']
    assert old['high_water']['input_tokens']==100 and old['high_water']['cached_input_tokens']==50


def test_rotation_settings_use_existing_configuration_and_frozen_loop(progression,tmp_path):
    from scidiscovery.agent_execution_settings import parse_settings,effective_settings,packaged_default_model
    from scidiscovery.artifact_agent.approval_ui.agent_settings import apply_form
    p=progression
    native,_=setup(p,tmp_path,root_rotate_after_rounds=2,root_rotate_after_input_tokens=321)
    frozen=json.loads(row(p)['config_json'])
    cp=checkpoint(p)
    assert cp['loop_authorizations'][cp['current_loop_id']]['config']==frozen
    schema=parse_settings({}).model_json_schema()['$defs']['ProgressionSettings']['properties']
    assert 'not current context size' in schema['root_rotate_after_input_tokens']['description']
    assert effective_settings(parse_settings({}),{})['progression']['root_rotate_after_rounds']==8
    from pathlib import Path
    import scidiscovery
    packaged=json.loads((Path(scidiscovery.__file__).parent/'default_agent_settings.json').read_text())
    assert packaged['progression']['root_rotate_after_input_tokens']==500000
    for value in (-1,True,None):
        with pytest.raises(ValueError): parse_settings(dict(progression=dict(root_rotate_after_rounds=value)))
    preserved=apply_form({'progression':{'root_rotate_after_rounds':2,'root_rotate_after_input_tokens':321}},
        {'settings_action':['save'],'default_model':['gpt-5.6-luna']},p.catalog)
    assert preserved['progression']=={'root_rotate_after_rounds':2,'root_rotate_after_input_tokens':321}
    p.coordinator.tick();completed(p)
    worker_profile=p.root.call_tool('operation_preflight',dict(name='profile',operation_id='blind.csv.observe.v1',
        inputs=[dict(port='source_table',artifact_names=['source_csv'])],instruction='Same scientific request.'))['normalized_request']['execution_profile']
    assert worker_profile['model']==packaged_default_model()
    bindings=p.runtime.scheduler_bindings
    bindings.global_settings=bindings.global_settings.model_copy(update=dict(progression=bindings.global_settings.progression.model_copy(
        update=dict(root_rotate_after_rounds=0,root_rotate_after_input_tokens=0))))
    assert json.loads(row(p)['config_json'])==frozen
    # Live policy edits cannot silently replace the accepted loop's snapshot.
    assert checkpoint(p)['loop_authorizations'][cp['current_loop_id']]['config']==frozen
    assert not bindings._control_settings_match(p.instance,row(p)['config_json'])
    p.coordinator.tick()
    with pytest.raises(SchedulerInstanceConflict,match='frozen research loop policy'):
        bindings.prepare_host_rotation(instance_id=p.instance,expected_host=json.loads(row(p)['host_json']),
            expected_generation=row(p)['generation'],terminal_turn=p.coordinator.host.completion)
    assert len(calls(native,'thread/start'))==1


def test_old_frozen_config_without_rotation_keys_recovers_with_triggers_disabled(progression,tmp_path):
    p=progression
    native,_=setup(p,tmp_path)
    bindings=p.runtime.scheduler_bindings
    control=row(p);cp=checkpoint(p)
    config=json.loads(control['config_json'])
    for key in ('root_rotate_after_rounds','root_rotate_after_input_tokens'):
        config['effective']['progression'].pop(key)
    cp['loop_authorizations'][cp['current_loop_id']]['config']=config
    from scidiscovery.artifact_agent.service.progression_records import store_checkpoint
    with bindings._connect() as db:
        db.execute('UPDATE scheduler_progression SET config_json=?,checkpoint_json=? WHERE instance_id=?',
            (json.dumps(config),store_checkpoint(db,p.instance,cp),p.instance))
    assert bindings._control_settings_match(p.instance,row(p)['config_json'])
    p.coordinator.tick();completed(p)
    wake(p);completed(p)
    assert len(calls(native,'thread/start'))==1 and len(calls(native,'turn/start'))==2
    assert json.loads(row(p)['config_json'])==config
    assert checkpoint(p)['loop_authorizations'][cp['current_loop_id']]['config']==config


def test_active_worker_defers_rotation_and_can_finish_under_original_binding(progression,tmp_path):
    p=progression
    native,_=setup(p,tmp_path)
    p.coordinator.tick();completed(p)
    root=p.root.__class__(p.facade(p.coordinator.host.scheduler_session))
    from tests.operations.test_local_worker_contracts import _invoke,_worker,_write_result
    _invoke(root,'accepted-work')
    worker=_worker(p.catalog,p.runtime);worker.call_tool('worker_open_assignment',{})
    wake(p)
    assert len(calls(native,'thread/start'))==1
    completed(p)
    _write_result(worker,observe_tokens=False)
    thread=worker._trusted_caller[1]
    p.coordinator._event(dict(method='thread/tokenUsage/updated',params=dict(threadId=thread,
        tokenUsage=dict(total=dict(inputTokens=10,cachedInputTokens=0,outputTokens=1)))))
    assert worker.call_tool('worker_submit_result',{})['state']=='completed'
    p.now[0]+=6;p.coordinator.tick()
    assert len(calls(native,'thread/start'))==2
    before=checkpoint(p)
    assert not any(v['name']=='accepted-work' for v in before['processed_snapshot']['runs'])
    p.now[0]+=6;p.coordinator.tick();completed(p)
    brief=json.loads(calls(native,'turn/start')[-1]['input'][0]['text'].split('\n')[-1])
    assert [v['name'] for v in brief['changes']]==['accepted-work']
    assert worker.call_tool('worker_submit_result',{})['state']=='completed'
    p.coordinator.tick()
    assert len(calls(native,'turn/start'))==3 and checkpoint(p)['rounds']==3
    assert [v['name'] for v in checkpoint(p)['processed_snapshot']['runs']]==['accepted-work']


@pytest.mark.parametrize('native_status',['inProgress','missing'])
def test_framework_failure_does_not_prove_native_child_quiescence(progression,tmp_path,native_status):
    p=progression
    native,_=setup(p,tmp_path)
    p.coordinator.tick();completed(p)
    root=p.root.__class__(p.facade(p.coordinator.host.scheduler_session))
    from tests.operations.test_local_worker_contracts import _invoke,_worker
    _invoke(root,'early-failure')
    worker=_worker(p.catalog,p.runtime);worker.call_tool('worker_open_assignment',{})
    current=p.runtime.runs.status(worker._run_id)
    p.runtime.runs.record_failure(current.run_id,reason='Exact original finite condition failed',
        expected_state='running',expected_last_activity_at=current.last_activity_at)
    (native/'child-status').write_text(native_status)
    wake(p)
    assert len(calls(native,'thread/start'))==1
    completed(p)
    (native/'child-status').write_text('completed')
    wake(p,'changed-condition')
    assert len(calls(native,'thread/start'))==2
    p.now[0]+=6;p.coordinator.tick();completed(p)
    brief=json.loads(calls(native,'turn/start')[-1]['input'][0]['text'].split('\n')[-1])
    memory=brief['attempt_memory']
    query=dict(memory['history']);query.pop('tool')
    fresh=p.root.__class__(p.facade(p.coordinator.host.scheduler_session))
    page=fresh.call_tool('run_list',query)
    old=next(v for v in page['runs'] if v['name']=='early-failure')
    assert old['result_nature']=='engineering_failure_not_scientific_negation'
    assert old['frozen_inputs'][0]==dict(original_name='source_table',artifact_name='source_csv')
    assert fresh.call_tool('run_status',dict(name='early-failure',intent='navigation'))['state']=='failed'


def test_rotation_hands_off_saved_external_job_without_resubmitting_or_refreshing(tmp_path):
    from copy import copy
    from types import SimpleNamespace
    from tests.operations.test_r4_execution_approval_identity import _setup,_create_effect,_decide_execution_approval
    from scidiscovery.artifact_agent.service.progression import ProgressionCoordinator
    runtime,instance,adapter,facade,root,catalog=_setup(tmp_path)
    user='sch_'+'a'*32
    runtime.scheduler_bindings.bind_session(session_key=user,instance_id=instance.instance_id)
    facade.session_key=user
    root.call_tool('artifact_ingest_text',dict(name='goal',text='Retain the accepted external computation.'))
    now=[1000.0]
    def make_facade(session):
        result=copy(facade);result.session_key=session
        return result
    coordinator=ProgressionCoordinator(runtime=runtime,host_factory=None,facade_factory=make_facade,clock=lambda:now[0])
    p=SimpleNamespace(runtime=runtime,instance=instance.instance_id,root=root,user=user,catalog=catalog,
        now=now,facade=make_facade,coordinator=coordinator)
    try:
        native,_=setup(p,tmp_path)
        coordinator.tick();completed(p)
        original_root=type(root)(make_facade(coordinator.host.scheduler_session))
        _create_effect(original_root,name='accepted-effect')
        _decide_execution_approval(runtime,original_root,name='accepted-effect')
        original=original_root.call_tool('execution_start',dict(name='accepted-effect'),surface='execution')
        assert original['state']=='submitted' and adapter.submit_count==1
        identity=runtime.scheduler_bindings.resolve(instance=p.instance,namespace='execution',name='accepted-effect')
        before=runtime.executions.status(identity)
        submissions=dict(adapter.submissions)
        wake(p)
        assert len(calls(native,'thread/start'))==2
        p.now[0]+=6;coordinator.tick();completed(p)
        brief=json.loads(calls(native,'turn/start')[-1]['input'][0]['text'].split('\n')[-1])
        assert len(brief['active_external_work'])==1
        saved=brief['active_external_work'][0]
        assert saved['name']=='accepted-effect' and saved['state']=='submitted'
        query=dict(saved['read']);tool=query.pop('tool');surface=query.pop('surface')
        fresh=type(root)(make_facade(coordinator.host.scheduler_session))
        inventory=fresh.call_tool(tool,query,surface=surface)
        assert inventory['executions'][0]['name']=='accepted-effect'
        assert runtime.executions.status(identity)==before
        assert adapter.submit_count==1 and adapter.submissions==submissions
        assert coordinator.host.identity.thread_id=='root-2' and checkpoint(p)['rounds']==2
    finally: coordinator.close()
