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
    notifications=base/'native-events.json'
    if notifications.exists():
        events=json.loads(notifications.read_text())
        if isinstance(events,list) or (events['method']==method and events['threadId']==p.get('threadId')):
            notifications.unlink()
            for event in events if isinstance(events,list) else events['events']:emit(event)
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
        else:
            thread=p['threadId']
            unavailable=json.loads((base/'resume-unavailable.json').read_text()) if (base/'resume-unavailable.json').exists() else []
            if thread in unavailable:
                emit({'id':msg['id'],'error':{'code':-32000,'message':'Subscription unavailable'}})
                continue
        sessions=json.loads((base/'thread-sessions.json').read_text()) if (base/'thread-sessions.json').exists() else {}
        result={'thread':{'id':thread,'sessionId':sessions.get(thread,thread if thread.startswith('root-') else 'source-test-session')}}
        if 'approvalPolicy' in p:
            result.update(approvalPolicy=p['approvalPolicy'],sandbox={
              'type':{'read-only':'readOnly','workspace-write':'workspaceWrite'}[p['sandbox']],
              'networkAccess':p.get('config',{}).get('sandbox_workspace_write',{}).get('network_access',False),'writableRoots':[]})
    elif method=='thread/read':
        unavailable=json.loads((base/'unavailable.json').read_text()) if (base/'unavailable.json').exists() else []
        if p['threadId'] in unavailable:
            emit({'id':msg['id'],'error':{'code':-32000,'message':'Historical native thread unavailable'}})
            continue
        child_status=(base/'child-status').read_text() if (base/'child-status').exists() else 'completed'
        sessions=json.loads((base/'thread-sessions.json').read_text()) if (base/'thread-sessions.json').exists() else {}
        if (base/'read-sessions.json').exists(): sessions.update(json.loads((base/'read-sessions.json').read_text()))
        result={'thread':{'id':p['threadId'],'sessionId':sessions.get(p['threadId'],p['threadId'] if p['threadId'].startswith('root-') else 'source-test-session'),'turns':state['threads'].get(p['threadId'],
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
    p.root.call_tool('progression_message',dict(name='prior-direction',text='Retain the original direction and its unresolved limit.'))
    p.coordinator.tick();completed(p)
    old_root=p.root.__class__(p.facade(p.coordinator.host.scheduler_session))
    old=checkpoint(p)
    old_turn=p.coordinator.host.completion['id']
    original_generation=row(p)['generation']
    wake(p)
    rotated=checkpoint(p)
    receipt=rotated['root_rotation_receipt']
    assert receipt['old']==dict(platform_session='root-1',thread_id='root-1')
    assert receipt['new']==dict(platform_session='root-2',thread_id='root-2')
    assert receipt['terminal_turn']==old_turn
    assert receipt['scope']==dict(instance=p.instance,loop=old['current_loop_id'],goal=json.loads(row(p)['objective_ref_json']))
    assert receipt['prepared_generation']==original_generation+1
    assert receipt['completed_generation']==row(p)['generation']==original_generation+2
    with p.runtime.runs._connect() as db:
        assert receipt['run_activity_fence']==db.execute('SELECT COALESCE(MAX(rowid),0) FROM run_activity').fetchone()[0]
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
    assert brief['objective']['name']=='goal' and brief['objective']['status']=='available'
    assert brief['user_messages']==[
        dict(name='prior-direction',original='Retain the original direction and its unresolved limit.'),
        dict(name='new-context',original='Retain this exact new condition.')]
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


def test_factory_context_recovery_is_bounded_originals_page_and_same_thread_is_incremental(progression,tmp_path):
    p=progression
    native,_=setup(p,tmp_path,root_rotate_after_rounds=2,context_bytes=8192)
    original='方向界限'*4095
    for name in ('early-direction','early-limit'):
        p.root.call_tool('progression_message',dict(name=name,text=original))
    p.coordinator.tick();completed(p)
    initial=json.loads(calls(native,'turn/start')[-1]['input'][0]['text'].split('\n')[-1])
    assert initial['budget']==checkpoint(p)['budget']
    assert initial['budget']['token_coverage']=='partial'
    assert initial['budget']['limits']==json.loads(row(p)['config_json'])['effective']['progression']
    wake(p,'increment-before-rotation');completed(p)
    wake(p,'new-direction')
    assert len(calls(native,'thread/start'))==2
    p.now[0]+=6;p.coordinator.tick();completed(p)
    fresh=p.root.__class__(p.facade(p.coordinator.host.scheduler_session))
    prompt=calls(native,'turn/start')[-1]['input'][0]['text']
    brief=json.loads(prompt.split('\n')[-1])
    assert len(prompt.encode())<=8192
    index=fresh.call_tool(brief['user_messages_read']['tool'],{})[brief['user_messages_read']['field']]
    assert [item['name'] for item in index]==['early-direction','early-limit','increment-before-rotation','new-direction']
    recovered=[]
    cursor=None
    while True:
        page=fresh.call_tool('artifact_catalog',dict(name='early-direction',view='content',content_cursor=cursor))
        recovered.append(page['text'])
        cursor=page['next_cursor']
        if cursor is None:break
    assert len(recovered)>1 and ''.join(recovered)==original
    assert all(item['name'] not in {'early-direction','early-limit'} for item in brief['user_messages'])
    wake(p,'same-thread-increment');completed(p)
    assert p.coordinator.host.identity.thread_id=='root-2'
    assert len(calls(native,'turn/start'))==4
    latest=json.loads(calls(native,'turn/start')[-1]['input'][0]['text'].split('\n')[-1])
    assert all(item['name']=='same-thread-increment' for item in latest['user_messages'])
    assert fresh.call_tool(latest['user_messages_read']['tool'],{})['messages'][-1]['name']=='same-thread-increment'
    assert fresh.call_tool('artifact_catalog',dict(name='same-thread-increment',view='content'))['text']=='Retain this exact new condition.'
    assert checkpoint(p)['usage_records']['root-2']['context_delivered']
    assert all(len(item['input'][0]['text'].encode())<=8192 for item in calls(native,'turn/start'))
    from tests.operations.test_run_list_bounds import metrics
    metrics('rotation-context-recovery',dict(startup_bytes=len(prompt.encode()),saved_messages=4,
        original_pages=len(recovered),original_bytes=len(original.encode()),same_thread_messages=1))


def test_insufficient_legal_context_fails_before_starting_a_turn(progression,tmp_path):
    from scidiscovery.artifact_agent.service.progression import ProgressionFault
    p=progression
    native,_=setup(p,tmp_path,context_bytes=4096)
    with pytest.raises(ProgressionFault,match='decision_brief_capacity'):
        p.coordinator.tick()
    assert calls(native,'turn/start')==[]
    assert checkpoint(p).get('phase') not in {'prepared','running'}


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
        assert json.loads(prompt.split('\n')[-1])['user_messages']==[
            dict(name='message-1',original='Retain this exact new condition.'),
            dict(name='message-2',original='Retain this exact new condition.')]
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
    native,_=setup(p,tmp_path,root_rotate_after_rounds=2,root_rotate_after_input_tokens=321,root_rotation_check_limit=3)
    frozen=json.loads(row(p)['config_json'])
    cp=checkpoint(p)
    assert cp['loop_authorizations'][cp['current_loop_id']]['config']==frozen
    assert frozen['effective']['progression']['root_rotation_check_limit']==3
    schema=parse_settings({}).model_json_schema()['$defs']['ProgressionSettings']['properties']
    assert 'not current context size' in schema['root_rotate_after_input_tokens']['description']
    assert effective_settings(parse_settings({}),{})['progression']['root_rotate_after_rounds']==8
    from pathlib import Path
    import scidiscovery
    packaged=json.loads((Path(scidiscovery.__file__).parent/'default_agent_settings.json').read_text())
    assert packaged['progression']['root_rotate_after_input_tokens']==500000
    assert packaged['progression']['root_rotation_check_limit']==16
    for value in (0,129,True,None):
        with pytest.raises(ValueError): parse_settings(dict(progression=dict(root_rotation_check_limit=value)))
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
    original_settings=bindings.global_settings
    bindings.global_settings=original_settings.model_copy(update=dict(progression=original_settings.progression.model_copy(
        update=dict(root_rotation_check_limit=4))))
    assert not bindings._control_settings_match(p.instance,row(p)['config_json'])
    bindings.global_settings=original_settings
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
    for key in ('root_rotate_after_rounds','root_rotate_after_input_tokens','root_rotation_check_limit'):
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


def test_terminal_cache_binding_expires_when_actual_worker_thread_is_reused(progression,tmp_path):
    from tests.operations.test_local_worker_contracts import _invoke,_worker,_write_result
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    p=progression
    native,_=setup(p,tmp_path)
    p.coordinator.tick();completed(p)
    root=p.root.__class__(p.facade(p.coordinator.host.scheduler_session))
    _invoke(root,'cached-worker')
    old=_worker(p.catalog,p.runtime);old.call_tool('worker_open_assignment',{})
    _write_result(old,observe_tokens=False)
    p.coordinator._event(dict(method='thread/tokenUsage/updated',params=dict(threadId=old._trusted_caller[1],
        tokenUsage=dict(total=dict(inputTokens=10,cachedInputTokens=0,outputTokens=1)))))
    old.call_tool('worker_submit_result',{})
    identities=p.coordinator._identities()
    observed=p.coordinator.host.rotation_boundary(identities,known={},limit=2)
    assert observed['safe']
    for observation in observed['observations']:p.coordinator._save({},native_observation=observation)
    thread=old._trusted_caller[1]
    old_key=checkpoint(p)['usage_records'][thread]['native_terminal']['binding_key']
    _invoke(root,'reused-worker')
    identity=root.facade._resolve('run','reused-worker')
    p.runtime.runs.worker_connections.attach(run_id=identity,platform_session=old._trusted_caller[0],thread_id=thread)
    value=p.runtime.runs.status(identity)
    worker=LocalWorkerMCPRouter(p.runtime.runs,operation_id=value.operation_id,operation_digest=value.operation_digest,
        run_id=identity,trusted_caller=old._trusted_caller)
    worker.call_tool('worker_open_assignment',{})
    _write_result(worker,observe_tokens=False)
    p.coordinator._event(dict(method='thread/tokenUsage/updated',params=dict(threadId=worker._trusted_caller[1],
        tokenUsage=dict(total=dict(inputTokens=20,cachedInputTokens=0,outputTokens=2)))))
    worker.call_tool('worker_submit_result',{})
    identities=p.coordinator._identities()
    assert identities[thread]['binding_key']!=old_key
    # A delayed old completion cannot certify this new attachment.
    def notify(*events):
        (native/'native-events.json').write_text(json.dumps(events))
        p.coordinator.host.connection.rpc('mcpServerStatus/list',dict(threadId=p.coordinator.host.identity.thread_id))
    notify(dict(method='turn/completed',params=dict(threadId=thread,turn=dict(id='worker-turn',status='completed'))))
    assert checkpoint(p)['usage_records'][thread]['native_terminal']['binding_key']==old_key
    (native/'child-status').write_text('inProgress')
    before=len(calls(native,'thread/read'))
    boundary=p.coordinator.host.rotation_boundary(identities,
        known={thread:checkpoint(p)['usage_records'][thread]['native_terminal']},limit=1)
    assert not boundary['safe'] and boundary['unknown']==1
    assert len(calls(native,'thread/read'))==before+1
    notify(dict(method='turn/started',params=dict(threadId=thread,turn=dict(id='new-worker-turn'))),
        dict(method='turn/completed',params=dict(threadId=thread,turn=dict(id='new-worker-turn',status='completed'))))
    latest=checkpoint(p)['usage_records'][thread]['native_terminal']
    assert latest['binding_key']==identities[thread]['binding_key'] and latest['turn_id']=='new-worker-turn'
    before=len(calls(native,'thread/read'))
    assert p.coordinator.host.rotation_boundary(identities,known={thread:latest},limit=1)['safe']
    assert len(calls(native,'thread/read'))==before


def _terminal_native_worker(p,root,name):
    from tests.operations.test_local_worker_contracts import _invoke,_worker,_write_result
    _invoke(root,name)
    worker=_worker(p.catalog,p.runtime);worker.call_tool('worker_open_assignment',{})
    _write_result(worker,observe_tokens=False)
    p.coordinator._event(dict(method='thread/tokenUsage/updated',params=dict(threadId=worker._trusted_caller[1],
        tokenUsage=dict(total=dict(inputTokens=10,cachedInputTokens=0,outputTokens=1)))))
    worker.call_tool('worker_submit_result',{})
    return worker._trusted_caller[1]


@pytest.mark.parametrize('changed',['cached','reading'])
def test_production_started_notification_during_other_read_invalidates_rotation_fence(progression,tmp_path,changed):
    p=progression
    native,_=setup(p,tmp_path)
    p.coordinator.tick();completed(p)
    root=p.root.__class__(p.facade(p.coordinator.host.scheduler_session))
    thread=_terminal_native_worker(p,root,'previously-terminal')
    proof=p.coordinator.host.rotation_boundary(p.coordinator._identities(),known={},limit=2)
    assert proof['safe']
    for observation in proof['observations']:p.coordinator._save({},native_observation=observation)
    other=_terminal_native_worker(p,root,'newly-terminal')
    affected=thread if changed=='cached' else other
    p.coordinator._settle_turn(checkpoint(p))
    (native/'native-events.json').write_text(json.dumps(dict(method='thread/read',threadId=other,
        events=[dict(method='turn/started',params=dict(threadId=affected,turn=dict(id='late-new-native-turn')))])))
    before=len(calls(native,'thread/read'))
    assert not p.coordinator._rotate_if_due(row(p),json.loads(row(p)['config_json'])['effective']['progression'])
    assert calls(native,'thread/read')[before:]==[dict(threadId=other,includeTurns=True)]
    assert 'native_terminal' not in checkpoint(p)['usage_records'][affected]
    assert checkpoint(p)['rotation_boundary']['reasons']==[
        'native_terminal_proof_invalidated' if changed=='cached' else 'native_turn_changed_during_read']
    assert len(calls(native,'thread/start'))==1 and row(p)['state']=='active'


@pytest.mark.parametrize('order',['usage_first','lifecycle_first'])
@pytest.mark.parametrize('role',['worker','helper'])
def test_native_attribution_interleaving_uses_public_binding_and_preserves_counters(progression,tmp_path,order,role):
    from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
    from tests.operations.test_unified_mcp import call,result
    from tests.operations.test_local_worker_contracts import _invoke
    p=progression
    native,_=setup(p,tmp_path,root_rotate_after_rounds=0)
    p.coordinator.tick();completed(p)
    host=p.coordinator.host
    root=p.root.__class__(p.facade(host.scheduler_session))
    _invoke(root,'attribution-owner')
    gateway=UnifiedMCPRouter(root)
    profile=root.call_tool('run_status',dict(name='attribution-owner'))['execution_profile']['profile']
    session=host.identity.session_id
    owner='attribution-worker';thread=owner if role=='worker' else 'attribution-helper'
    def emit(event):
        (native/'native-events.json').write_text(json.dumps([event]))
        host.connection.rpc('thread/read',dict(threadId=host.identity.thread_id,includeTurns=True))
    def usage(input_tokens,cached,output):
        return dict(method='thread/tokenUsage/updated',params=dict(threadId=thread,
            tokenUsage=dict(total=dict(inputTokens=input_tokens,cachedInputTokens=cached,outputTokens=output))))
    if role=='helper':
        result(call(gateway,'worker_attach',dict(name='attribution-owner',thread_id=owner),session=session))
        result(call(gateway,'worker_open_assignment',child=owner,profile=profile,session=session))
        result(call(gateway,'worker_helper',dict(name='inspection',task='Inspect this finite data.'),
            child=owner,profile=profile,session=session))
    if order=='usage_first':
        emit(usage(100,None,20))
        unbound=checkpoint(p)['usage_records'][thread]
        assert unbound['role']=='unattributed' and unbound['owner'] is None and unbound['has_gaps']
        assert unbound['counted_tokens']['input_tokens']==100
    if role=='worker':
        result(call(gateway,'worker_attach',dict(name='attribution-owner',thread_id=owner),session=session))
        result(call(gateway,'worker_open_assignment',child=owner,profile=profile,session=session))
    else:
        reply=gateway.handle(dict(jsonrpc='2.0',id=1,method='tools/call',params=dict(
            name='scid_call',arguments=dict(name='worker_open_assignment',arguments={}),
            _meta={'x-codex-turn-metadata':dict(session_id=session,thread_id=thread,parent_thread_id=owner,
                subagent_kind='thread_spawn',model=profile['model'],reasoning_effort=profile['reasoning_effort'])})))
        assert result(reply)['state']=='opened'
    identity=p.coordinator._identities()[thread]
    emit(dict(method='turn/started',params=dict(threadId=thread,turn=dict(id='bound-turn'))))
    if order=='usage_first':
        upgraded=checkpoint(p)['usage_records'][thread]
        for key in ('counted_tokens','high_water','has_gaps','coverage'):
            assert upgraded[key]==unbound[key]
    else:
        emit(usage(100,10,20))
    emit(usage(125,20,25))
    emit(dict(method='turn/completed',params=dict(threadId=thread,turn=dict(id='bound-turn',status='completed'))))
    terminal=checkpoint(p)['usage_records'][thread]['native_terminal']
    emit(usage(125,20,25));emit(usage(100,10,20));emit(usage(150,25,35))
    saved=checkpoint(p)['usage_records'][thread]
    assert (saved['role'],saved['owner'],saved['loop_id'])==(role,p.instance,identity['loop_id'])
    assert saved['counted_tokens']==saved['high_water']==dict(input_tokens=150,cached_input_tokens=25,output_tokens=35)
    assert saved['has_gaps'] and saved['native_terminal']==terminal
    assert terminal['binding_key']==identity['binding_key'] and terminal['connection_id']==host.native_connection_id
    status=root.call_tool('progression_status',{})
    assert status['usage']['groups'][role]['tokens']==saved['counted_tokens']
    assert row(p)['state']=='active' and len(calls(native,'turn/start'))==1
    # Invalid runtime observations must roll back the same real ledger, not
    # manufacture another attribution baseline or a synthetic checkpoint.
    before=checkpoint(p)
    for changed in (dict(role='helper' if role=='worker' else 'worker'),dict(loop_id='other-loop')):
        with pytest.raises(ValueError,match='original'):
            p.coordinator._save({},native_observation=dict(identity={**identity,**changed},
                source='turn_started',turn_id='rejected-turn',connection_id=host.native_connection_id))
        assert checkpoint(p)==before
    foreign=p.runtime.scheduler_bindings.create_instance(name='foreign-attribution',title='Foreign scope',objective='Separate test scope.')
    with pytest.raises(SchedulerInstanceConflict,match='Native host binding changed'):
        p.runtime.scheduler_bindings.observe_progression(instance_id=foreign.instance_id,
            expected_host=json.loads(row(p)['host_json']),changes={},native_observation=dict(identity=identity,
                source='turn_started',turn_id='rejected-turn',connection_id=host.native_connection_id))
    from scidiscovery.artifact_agent.service.progression_budget import _reconcile_attribution
    with pytest.raises(ValueError,match='original role or owner'):
        _reconcile_attribution(saved,role=role,owner=foreign.instance_id)
    assert saved==checkpoint(p)['usage_records'][thread] and checkpoint(p)==before


@pytest.mark.parametrize('run_state',['completed','failed'])
@pytest.mark.parametrize('helper',[False,True])
@pytest.mark.parametrize('limit',[1,2])
def test_rebuilt_coordinator_resubscribes_terminal_cohort_and_rotates_without_new_turn(progression,tmp_path,run_state,helper,limit):
    from scidiscovery.artifact_agent.service.progression import ProgressionCoordinator
    from scidiscovery.helper_tool import HelperRequest
    from tests.operations.test_local_worker_contracts import _invoke,_worker,_write_result
    p=progression
    native,factory=setup(p,tmp_path,root_rotation_check_limit=limit)
    p.coordinator.tick();completed(p)
    root=p.root.__class__(p.facade(p.coordinator.host.scheduler_session))
    _invoke(root,'cold-terminal-owner')
    worker=_worker(p.catalog,p.runtime);worker.call_tool('worker_open_assignment',{})
    run=p.runtime.runs.status(worker._run_id)
    connections=p.runtime.runs.worker_connections
    if helper:
        connections.helper_request(run.run_id,HelperRequest(name='inspection',task='Inspect the same finite data.'))
        connections.participant(platform_session=worker._trusted_caller[0],thread_id='cold-helper',
            parent_thread=worker._trusted_caller[1],admit=True,model=run.execution_profile['profile']['model'],
            reasoning_effort=run.execution_profile['profile']['reasoning_effort'])
        connections.release_helpers(run.run_id)
    for identity in p.coordinator._identities().values():
        p.coordinator._event(dict(method='thread/tokenUsage/updated',params=dict(threadId=identity['thread_id'],
            tokenUsage=dict(total=dict(inputTokens=10,cachedInputTokens=0,outputTokens=1)))))
    if run_state=='completed':
        _write_result(worker,observe_tokens=False)
        assert worker.call_tool('worker_submit_result',{})['state']=='completed'
    else:
        run=p.runtime.runs.status(run.run_id)
        p.runtime.runs.record_failure(run.run_id,reason='Finite fixture failure',expected_state='running',
            expected_last_activity_at=run.last_activity_at)
    (native/'child-status').write_text(run_state)
    identities=p.coordinator._identities()
    proof=p.coordinator.host.rotation_boundary(identities,known={},limit=4)
    assert proof['safe']
    for observation in proof['observations']:p.coordinator._save({},native_observation=observation)
    before=checkpoint(p)
    original=p.runtime.runs.status(run.run_id)
    p.coordinator.close()
    fresh=ProgressionCoordinator(runtime=p.runtime,host_factory=factory,facade_factory=p.facade,clock=lambda:p.now[0])
    p.coordinator=fresh
    fresh._connect(row(p));fresh._settle_turn(checkpoint(p))
    assert fresh.host.native_subscriptions=={}
    assert fresh.host.initial_native_bindings=={i['binding_key'] for i in identities.values()}
    resumes=len(calls(native,'thread/resume'));reads=len(calls(native,'thread/read'))
    limits=json.loads(row(p)['config_json'])['effective']['progression']
    for attempt in range(2*len(identities)):
        prior=len(calls(native,'thread/resume'))+len(calls(native,'thread/read'))
        rotated=fresh._rotate_if_due(row(p),limits)
        assert len(calls(native,'thread/resume'))+len(calls(native,'thread/read'))-prior<=limit
        if rotated:break
    else:pytest.fail('A finite terminal cohort never acquired fresh subscribed proof on reconnect.')
    participant_resumes=[c for c in calls(native,'thread/resume')[resumes:] if c['threadId'] in identities]
    assert participant_resumes==[dict(threadId=i['thread_id'],cwd=str(p.runtime.project_root),excludeTurns=True)
        for i in sorted(identities.values(),key=lambda i:i['binding_key'])]
    assert len(calls(native,'thread/read'))-reads==len(identities)
    after=checkpoint(p)
    for thread,identity in identities.items():
        old=before['usage_records'][thread];new=after['usage_records'][thread]
        assert new['high_water']==old['high_water'] and new['counted_tokens']==old['counted_tokens']
        assert new['native_terminal']['binding_key']==identity['binding_key']
        assert new['native_terminal']['connection_id']!=old['native_terminal']['connection_id']
    assert after['current_loop_id']==before['current_loop_id'] and after['attempts']==before['attempts']
    assert p.runtime.runs.status(run.run_id)==original
    assert len(calls(native,'thread/start'))==2 and len(calls(native,'turn/start'))==1


@pytest.mark.parametrize('failure,reason',[
    ('inProgress','native_turn_not_terminal'),('unknown','native_turn_not_terminal'),
    ('unavailable','native_subscription_unconfirmed'),('identity','native_subscription_unconfirmed'),
    ('read_identity','native_identity_unconfirmed'),('event','native_turn_changed_during_read')])
def test_rebuilt_terminal_cohort_keeps_unknown_native_state_unsafe(progression,tmp_path,failure,reason):
    from scidiscovery.artifact_agent.service.progression import ProgressionCoordinator
    p=progression
    native,factory=setup(p,tmp_path,root_rotation_check_limit=2)
    p.coordinator.tick();completed(p)
    root=p.root.__class__(p.facade(p.coordinator.host.scheduler_session))
    thread=_terminal_native_worker(p,root,'cold-unknown')
    proof=p.coordinator.host.rotation_boundary(p.coordinator._identities(),known={},limit=2)
    assert proof['safe']
    for observation in proof['observations']:p.coordinator._save({},native_observation=observation)
    p.coordinator.close()
    if failure in {'inProgress','unknown'}:(native/'child-status').write_text(failure)
    if failure=='unavailable':(native/'resume-unavailable.json').write_text(json.dumps([thread]))
    if failure in {'identity','read_identity'}:
        (native/('thread-sessions.json' if failure=='identity' else 'read-sessions.json')).write_text(json.dumps({thread:'wrong-session'}))
    if failure=='event':
        (native/'native-events.json').write_text(json.dumps(dict(method='thread/read',threadId=thread,
            events=[dict(method='turn/started',params=dict(threadId=thread,turn=dict(id='new-native-turn')))])))
    fresh=ProgressionCoordinator(runtime=p.runtime,host_factory=factory,facade_factory=p.facade,clock=lambda:p.now[0])
    p.coordinator=fresh
    fresh._connect(row(p));fresh._settle_turn(checkpoint(p))
    before=len(calls(native,'thread/resume'))+len(calls(native,'thread/read'))
    assert not fresh._rotate_if_due(row(p),json.loads(row(p)['config_json'])['effective']['progression'])
    assert len(calls(native,'thread/resume'))+len(calls(native,'thread/read'))-before<=2
    assert checkpoint(p)['rotation_boundary']['reasons']==[reason]
    assert len(calls(native,'thread/start'))==1 and len(calls(native,'turn/start'))==1
    assert row(p)['state']=='active'


def test_rebuilt_terminal_cohort_cannot_reconnect_after_loop_budget_exhaustion(progression,tmp_path):
    from datetime import datetime
    from scidiscovery.artifact_agent.service.progression import ProgressionCoordinator
    p=progression
    native,factory=setup(p,tmp_path)
    p.coordinator.tick();completed(p)
    root=p.root.__class__(p.facade(p.coordinator.host.scheduler_session))
    _terminal_native_worker(p,root,'budget-terminal')
    before=checkpoint(p)
    p.coordinator.close()
    p.now[0]=datetime.fromisoformat(before['loop_authorizations'][before['current_loop_id']]['deadline_at']).timestamp()+1
    requests=(native/'requests.jsonl').read_bytes()
    fresh=ProgressionCoordinator(runtime=p.runtime,host_factory=factory,facade_factory=p.facade,clock=lambda:p.now[0])
    p.coordinator=fresh
    fresh.tick()
    assert fresh.host is None and row(p)['reason']=='budget_exhausted'
    assert (native/'requests.jsonl').read_bytes()==requests
    for thread,record in before['usage_records'].items():
        assert checkpoint(p)['usage_records'][thread]['counted_tokens']==record['counted_tokens']


def test_new_app_server_rechecks_persisted_terminal_proof_without_loading_old_history(progression,tmp_path):
    from scidiscovery.artifact_agent.service.progression import ProgressionCoordinator
    p=progression
    native,factory=setup(p,tmp_path)
    p.coordinator.tick();completed(p)
    root=p.root.__class__(p.facade(p.coordinator.host.scheduler_session))
    thread=_terminal_native_worker(p,root,'old-proof')
    proof=p.coordinator.host.rotation_boundary(p.coordinator._identities(),known={},limit=2)
    assert proof['safe']
    for observation in proof['observations']:p.coordinator._save({},native_observation=observation)
    saved=checkpoint(p)['usage_records'][thread]['native_terminal']
    p.coordinator.close()
    (native/'child-status').write_text('inProgress')
    fresh=ProgressionCoordinator(runtime=p.runtime,host_factory=factory,facade_factory=p.facade,clock=lambda:p.now[0])
    p.coordinator=fresh
    fresh._connect(row(p));fresh._settle_turn(checkpoint(p))
    before=len(calls(native,'thread/read'));resumes=len(calls(native,'thread/resume'))
    assert not fresh._rotate_if_due(row(p),json.loads(row(p)['config_json'])['effective']['progression'])
    assert calls(native,'thread/read')[before:]==[dict(threadId=thread,includeTurns=True)]
    assert len(calls(native,'thread/resume'))==resumes+1
    assert checkpoint(p)['usage_records'][thread]['native_terminal']==saved
    assert len(calls(native,'thread/start'))==1 and row(p)['state']=='active'
    # The first check subscribed, but inProgress did not establish terminal proof.
    (native/'child-status').write_text('completed')
    assert fresh._rotate_if_due(row(p),json.loads(row(p)['config_json'])['effective']['progression'])
    assert len(calls(native,'thread/resume'))==resumes+1
    current=checkpoint(p)['usage_records'][thread]['native_terminal']
    assert current['binding_key']==saved['binding_key'] and current['connection_id']!=saved['connection_id']
    assert checkpoint(p)['rotation_boundary']['reasons']==[]


@pytest.mark.parametrize('limit',[1,2])
def test_fast_complete_task_subscribes_on_production_rotation_without_new_turn_or_permission_override(progression,tmp_path,limit):
    p=progression
    native,_=setup(p,tmp_path,root_rotation_check_limit=limit)
    p.coordinator.tick();completed(p)
    root=p.root.__class__(p.facade(p.coordinator.host.scheduler_session))
    thread=_terminal_native_worker(p,root,'fast-complete')
    assert not calls(native,'thread/resume')
    p.coordinator._settle_turn(checkpoint(p))
    limits=json.loads(row(p)['config_json'])['effective']['progression']
    batches=[]
    for attempt in range(2 if limit==1 else 1):
        before=len(calls(native,'thread/resume'))+len(calls(native,'thread/read'))
        rotated=p.coordinator._rotate_if_due(row(p),limits)
        batches.append(len(calls(native,'thread/resume'))+len(calls(native,'thread/read'))-before)
        assert batches[-1]<=limit
        assert rotated is (limit==2 or attempt==1)
    assert calls(native,'thread/resume')==[dict(threadId=thread,cwd=str(p.runtime.project_root),excludeTurns=True)]
    assert calls(native,'thread/read')==[dict(threadId=thread,includeTurns=True)]
    assert len(calls(native,'turn/start'))==1 and len(calls(native,'thread/start'))==2
    assert row(p)['state']=='active'
    from tests.operations.test_run_list_bounds import metrics
    metrics('rotation-subscription-'+str(limit),dict(rpc_batches=batches,participant_resume=1,participant_read=1,
        extra_model_turns=0,old_terminal_resumes=0))


@pytest.mark.parametrize('opened',[False,True])
def test_protocol_empty_thread_requires_closed_never_started_task(progression,tmp_path,opened):
    from tests.operations.test_local_worker_contracts import _invoke,_worker
    p=progression
    native,_=setup(p,tmp_path)
    p.coordinator.tick();completed(p)
    root=p.root.__class__(p.facade(p.coordinator.host.scheduler_session))
    _invoke(root,'empty-worker')
    worker=_worker(p.catalog,p.runtime)
    if opened:worker.call_tool('worker_open_assignment',{})
    value=p.runtime.runs.status(root.facade._resolve('run','empty-worker'))
    p.runtime.runs.record_failure(value.run_id,reason='Cancelled before any new native work.',
        expected_state=value.state,expected_last_activity_at=value.last_activity_at)
    (native/'child-status').write_text('missing')
    p.coordinator._settle_turn(checkpoint(p))
    result=p.coordinator._rotate_if_due(row(p),json.loads(row(p)['config_json'])['effective']['progression'])
    assert result is (not opened)
    assert len(calls(native,'thread/start'))==(1 if opened else 2)
    assert row(p)['state']=='active'
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    fresh=LocalWorkerMCPRouter(p.runtime.runs,operation_id=value.operation_id,operation_digest=value.operation_digest,
        run_id=value.run_id,trusted_caller=worker._trusted_caller)
    with pytest.raises(Exception,match='terminal|queued|running|assignment'):
        fresh.call_tool('worker_open_assignment',{})


def test_protocol_1500_cached_terminal_bindings_need_no_rpc_and_unknown_cohort_is_batched(progression,tmp_path):
    """Capacity fixture clones retained proof; live reconciliation uses the real peer."""
    from copy import deepcopy
    from tests.operations.test_local_worker_contracts import _invoke,_worker,_write_result
    from scidiscovery.artifact_agent.service.progression_records import store_checkpoint
    p=progression
    native,_=setup(p,tmp_path,max_tasks=1510,detail_capacity=16384,root_rotation_check_limit=2)
    p.coordinator.tick();completed(p)
    root=p.root.__class__(p.facade(p.coordinator.host.scheduler_session))
    _invoke(root,'terminal-prototype')
    prototype=_worker(p.catalog,p.runtime);prototype.call_tool('worker_open_assignment',{})
    _write_result(prototype,observe_tokens=False)
    p.coordinator._event(dict(method='thread/tokenUsage/updated',params=dict(threadId=prototype._trusted_caller[1],
        tokenUsage=dict(total=dict(inputTokens=10,cachedInputTokens=0,outputTokens=1)))))
    prototype.call_tool('worker_submit_result',{})
    identities=p.coordinator._identities()
    proof=p.coordinator.host.rotation_boundary(identities,known={},limit=2)
    assert proof['safe'] and len(proof['observations'])==1
    for observation in proof['observations']:p.coordinator._save({},native_observation=observation)
    prototype_thread=prototype._trusted_caller[1]
    prototype_record=deepcopy(checkpoint(p)['usage_records'][prototype_thread])
    with p.runtime.runs._connect() as db:
        template=dict(db.execute('SELECT * FROM runs WHERE run_id=?',(prototype._run_id,)).fetchone())
        for index in range(1500):
            identity='run_'+f'{index+50000:032x}'
            saved=dict(template,run_id=identity,output_binding_name=f'cache-history-{index}.output',
                output_logical_name=f'cache-history-{index}.output')
            db.execute('INSERT INTO runs ('+','.join(saved)+') VALUES ('+','.join('?' for _ in saved)+')',list(saved.values()))
            db.execute('INSERT INTO worker_connections VALUES(?,?,?,?,?)',
                (identity,'source-test-session',f'cache-history-{index}','2026-10-03T00:00:00Z',1))
    cp=checkpoint(p)
    identities=p.coordinator._identities()
    for thread,identity in identities.items():
        if thread==prototype_thread:continue
        record=deepcopy(prototype_record)
        record['thread_id']=thread
        record['native_terminal']['binding_key']=identity['binding_key']
        cp['usage_records'][thread]=record
        # Capacity clone of the same genuinely subscribed prototype connection.
        p.coordinator.host.native_subscriptions[thread]=identity['platform_session']
    with p.runtime.scheduler_bindings._connect() as db:
        db.execute('UPDATE scheduler_progression SET checkpoint_json=? WHERE instance_id=?',
            (store_checkpoint(db,p.instance,cp),p.instance))
    old_threads=set(identities)
    (native/'unavailable.json').write_text(json.dumps(sorted(old_threads)))
    unknown=[]
    for index in range(3):
        _invoke(root,f'late-native-{index}')
        worker=_worker(p.catalog,p.runtime);worker.call_tool('worker_open_assignment',{})
        _write_result(worker,observe_tokens=False)
        p.coordinator._event(dict(method='thread/tokenUsage/updated',params=dict(threadId=worker._trusted_caller[1],
            tokenUsage=dict(total=dict(inputTokens=10,cachedInputTokens=0,outputTokens=1)))))
        worker.call_tool('worker_submit_result',{})
        unknown.append(worker._trusted_caller[1])
    (native/'child-status').write_text('inProgress')
    p.coordinator._settle_turn(checkpoint(p))
    limits=json.loads(row(p)['config_json'])['effective']['progression']
    batches=[]
    for _ in range(3):
        before=len(calls(native,'thread/read'))
        prior_resumes=len(calls(native,'thread/resume'))
        assert not p.coordinator._rotate_if_due(row(p),limits)
        batch=calls(native,'thread/read')[before:]
        batches.append(len(batch)+len(calls(native,'thread/resume'))-prior_resumes)
        assert len(batch)==1 and batches[-1]==2 and {call['threadId'] for call in batch}<=set(unknown)
        assert row(p)['state']=='active' and checkpoint(p)['rotation_boundary']['unchecked']==2
        public=p.root.call_tool('progression_status',{})['rotation_boundary']
        assert public==checkpoint(p)['rotation_boundary']
        assert public['checked']==2 and public['unknown']==1 and public['reasons']==['native_turn_not_terminal']
    assert len({call['threadId'] for call in calls(native,'thread/read')[-3:]})==3
    (native/'child-status').write_text('completed')
    before=len(calls(native,'thread/read'))
    assert not p.coordinator._rotate_if_due(row(p),limits)
    assert p.coordinator._rotate_if_due(row(p),limits)
    final=calls(native,'thread/read')[before:]
    assert len(final)==3 and {call['threadId'] for call in final}==set(unknown)
    assert len(calls(native,'thread/start'))==2
    assert checkpoint(p)['rounds']==1
    from tests.operations.test_run_list_bounds import metrics
    metrics('rotation-native-cohort',dict(retained_terminal_bindings=len(old_threads),unknown_bindings=3,
        rpc_batches=batches,terminal_reconciliation_rpc=len(final),historical_rpc=0))


def test_rotation_hands_off_saved_external_job_without_resubmitting_or_refreshing(tmp_path):
    from copy import copy
    from types import SimpleNamespace
    from tests.operations.test_r4_execution_approval_identity import _setup,_create_effect,_decide_execution_approval
    from scidiscovery.artifact_agent.service.progression import ProgressionCoordinator
    runtime,instance,adapter,facade,root,catalog=_setup(tmp_path)
    user='sch_'+'a'*32
    runtime.scheduler_bindings.bind_session(session_key=user,instance_id=instance.instance_id)
    facade.session_key=user
    facade.approval_base_url='http://127.0.0.1:8765'
    root.call_tool('artifact_ingest_text',dict(name='goal',text='Retain the accepted external computation.'))
    now=[1000.0]
    def make_facade(session):
        result=copy(facade);result.session_key=session
        return result
    coordinator=ProgressionCoordinator(runtime=runtime,host_factory=None,facade_factory=make_facade,clock=lambda:now[0])
    p=SimpleNamespace(runtime=runtime,instance=instance.instance_id,root=root,user=user,catalog=catalog,
        now=now,facade=make_facade,coordinator=coordinator)
    try:
        native,_=setup(p,tmp_path,root_rotate_after_rounds=2)
        coordinator.tick();completed(p)
        original_root=type(root)(make_facade(coordinator.host.scheduler_session))
        _create_effect(original_root,name='accepted-effect')
        _decide_execution_approval(runtime,original_root,name='accepted-effect')
        original=original_root.call_tool('execution_start',dict(name='accepted-effect'),surface='execution')
        assert original['state']=='submitted' and adapter.submit_count==1
        identity=runtime.scheduler_bindings.resolve(instance=p.instance,namespace='execution',name='accepted-effect')
        before=runtime.executions.status(identity)
        submissions=dict(adapter.submissions)
        _create_effect(original_root,name='pending-effect')
        wake(p,'pending-before-rotation');completed(p)
        assert original_root.call_tool('approval_status',dict(name='pending-effect.approval'))['status']=='pending'
        wake(p)
        assert len(calls(native,'thread/start'))==2
        p.now[0]+=6;coordinator.tick();completed(p)
        brief=json.loads(calls(native,'turn/start')[-1]['input'][0]['text'].split('\n')[-1])
        saved_work={value['name']:value for value in brief['active_external_work']}
        assert len(saved_work)==len(brief['active_external_work'])==2
        assert set(saved_work)=={'accepted-effect','pending-effect'}
        assert saved_work['pending-effect']['state']=='created'
        saved=saved_work['accepted-effect']
        assert saved['name']=='accepted-effect' and saved['state']=='submitted'
        query=dict(saved['read']);tool=query.pop('tool');surface=query.pop('surface')
        fresh=type(root)(make_facade(coordinator.host.scheduler_session))
        assert {value['name']:value['status'] for value in brief['approval_changes']}=={
            'accepted-effect.approval':'decided','pending-effect.approval':'pending'}
        pending=fresh.call_tool('approval_status',dict(name='pending-effect.approval'))
        assert pending['status']=='pending' and pending['review_url']
        inventory=fresh.call_tool(tool,query,surface=surface)
        execution_names=[value['name'] for value in inventory['executions']]
        assert len(execution_names)==len(set(execution_names))==2
        assert set(execution_names)=={'accepted-effect','pending-effect'}
        assert runtime.executions.status(identity)==before
        assert adapter.submit_count==1 and adapter.submissions==submissions
        assert coordinator.host.identity.thread_id=='root-2' and checkpoint(p)['rounds']==3
    finally: coordinator.close()
