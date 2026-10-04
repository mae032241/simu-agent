"""Task-specific launch and stop checks. RPC transport is simulated, not live roles."""
from pathlib import Path
import json
import pytest
from scripts import run_covshift_pilot as driver
from scripts import prepare_covshift_pilot as inputs
from tests.operations.test_covshift_pilot_preparation import inputs as fixture_inputs


def pair(tmp_path,monkeypatch):
    old,candidate,python,revision=fixture_inputs(tmp_path,monkeypatch)
    path=tmp_path/'pair';inputs.prepare(path,old,candidate,python,revision)
    return path/'launch.json'


def native_bundle(tmp_path):
    root=tmp_path/'native-bin';root.mkdir()
    (root/'codex').write_bytes(b'simulated native protocol transport')
    (root/'codex-code-mode-host').write_bytes(b'simulated code mode runtime')
    return root/'codex'


def test_preparation_rejects_changed_public_bytes_before_create(tmp_path,monkeypatch):
    source=pair(tmp_path,monkeypatch);launch=json.loads(source.read_text())
    target=Path(launch['arms']['native_goal']['project'],'instruction.md');target.chmod(0o644);target.write_text('changed')
    with pytest.raises(ValueError,match='public_input_changed'):
        driver.prepare(source,tmp_path/'new',Path('/bin/true'))
    assert not (tmp_path/'new').exists()


@pytest.mark.parametrize('tokens,wall',[(200000,1800),(112607,1761),(2000000,1800)])
def test_prepare_consumes_exact_candidate_builds_same_aliases_and_fresh_settings(tmp_path,monkeypatch,tokens,wall):
    source=pair(tmp_path,monkeypatch)
    invoked=[]
    def init(command,**kwargs):
        project=Path(command[command.index('--project-root')+1]);(project/'.codex').mkdir()
        (project/'.codex/config.toml').write_text('web_search="disabled"\n')
        from types import SimpleNamespace
        invoked.append(command)
        return SimpleNamespace(returncode=0,stdout=b'fixture init: no processes')
    monkeypatch.setattr(driver.subprocess,'run',init)
    result=driver.prepare(source,tmp_path/'new',native_bundle(tmp_path),
        native_goal_tokens=tokens,native_goal_wall_seconds=wall)
    assert len(invoked)==2 and result['launch_ready'] is False
    assert result['limits']['all_role_tokens']==2000000 and result['limits']['trial_wall_seconds']==1800
    specs=[json.loads(Path(p).read_text()) for p in result['arms'].values()]
    assert specs[0]['public_sha256']==specs[1]['public_sha256']
    for spec in specs:
        expected={'all_role_tokens':tokens if spec['arm']=='native_goal' else 200000,
            'trial_wall_seconds':wall if spec['arm']=='native_goal' else 1800}
        assert spec['limits']==expected==result['arm_limits'][spec['arm']]
        settings=json.loads(Path(spec['root'],'agent-settings.json').read_text())
        from scidiscovery.agent_execution_settings import parse_settings
        effective=parse_settings(settings)
        assert effective.debug_disable_task_network and effective.defaults.model==driver.MODEL
        assert effective.progression.enabled==(spec['arm']=='scidiscovery')
        assert effective.progression.root_network_access is False
        assert effective.progression.max_tokens==expected['all_role_tokens']
        assert effective.progression.max_elapsed_seconds==expected['trial_wall_seconds']
        assert effective.progression.max_calendar_seconds==expected['trial_wall_seconds']
        assert spec['settings_sha256']==driver.sha(Path(spec['root'],'agent-settings.json'))
        for key in ('/workspace','/opt/exp/runs','/submission'):
            assert spec['definition']['filesystem'][key]=='write'
        assert spec['definition']['filesystem']['/opt/exp']=='read'
        assert spec['environment']['PATH'].split(':')[0]==spec['project']+'/bin'
        assert '/usr/local/bin/exp' not in driver.outer_command(spec)
        assert not list(Path(spec['project'],'harness/runs').iterdir())
        assert spec['definition']['filesystem'][':root']=='deny'
        assert spec['definition']['network']['enabled'] is False
        runtime=spec['code_mode_host']
        assert runtime==driver.native_runtime(spec['native'])
        assert spec['definition']['filesystem'][runtime['path']]=='read'
        assert str(Path(spec['native']).parent) not in spec['definition']['filesystem']
        command=driver.outer_command(spec)
        assert ['--ro-bind',runtime['path'],runtime['path']]==command[command.index(runtime['path'])-1:command.index(runtime['path'])+2]
        assert '--unshare-pid' in command and '--unshare-net' not in command
        assert str(Path.home()) not in command and '--clearenv' in command
        compile(driver.canary_code({**spec,'canary_port':12345}),'native_canary','exec')
        assert not list(Path(spec['project'],'workspace').iterdir())
        config=__import__('tomllib').loads(Path(spec['root'],'codex-home/config.toml').read_text())
        assert config['shell_environment_policy']['inherit']=='none'
        assert config['permissions'][driver.NAME]['network']['enabled'] is False
        assert config['web_search']=='disabled'


def usage(thread,inputs=100,outputs=20,cached=0):
    return {'method':'thread/tokenUsage/updated','params':{'threadId':thread,'turnId':'turn',
        'tokenUsage':{'total':{'inputTokens':inputs,'outputTokens':outputs,'cachedInputTokens':cached}}}}


def test_existing_usage_reducer_counts_all_threads_without_cached_double_count_and_stops():
    now=[0.];meter=driver.Meter(lambda:now[0]);meter.activate()
    meter.observe(usage('root',100,20,80));meter.observe(usage('helper',30,10,20))
    meter.observe(usage('root',110,21,85))
    assert meter.total()==171
    with pytest.raises(RuntimeError,match='observed_token_limit'):
        meter.observe(usage('worker',200000,1))
    assert meter.total()==200172  # observation overshoot is retained, never refunded.


def test_deadline_unknown_participant_and_regression_fail_closed():
    now=[0.];meter=driver.Meter(lambda:now[0]);meter.activate()
    meter.observe({'method':'turn/started','params':{'threadId':'child'}})
    now[0]=6;meter.check()  # in-flight usage is pending, not a measured zero.
    meter.observe({'method':'turn/completed','params':{'threadId':'child','turn':{'status':'completed'}}})
    now[0]=12
    with pytest.raises(RuntimeError,match='participant_usage_unconfirmed'):meter.check()
    meter=driver.Meter(lambda:now[0]);meter.activate();meter.observe(usage('root'))
    with pytest.raises(RuntimeError,match='token_coverage_unknown'):meter.observe(usage('root',1))
    meter=driver.Meter(lambda:now[0]);meter.activate();now[0]+=1800
    with pytest.raises(RuntimeError,match='wall_deadline'):meter.check()
    with pytest.raises(RuntimeError,match='already_submitted'):meter.activate()


def test_public_calls_use_only_actual_thread_coordinates_and_typed_errors():
    from types import SimpleNamespace
    requests=[]
    def rpc(method,params):
        requests.append((method,params));return {'structuredContent':{'state':'unbound'}}
    host=SimpleNamespace(identity=SimpleNamespace(thread_id='actual',session_id='actual'),
        connection=SimpleNamespace(rpc=rpc))
    assert driver.public_call(host,'instance_current',{})=={'state':'unbound'}
    params=requests[0][1]
    assert params['_meta']['x-codex-turn-metadata']=={'thread_id':'actual','session_id':'actual'}
    host.connection.rpc=lambda *args:{'isError':True}
    with pytest.raises(RuntimeError,match='public_call_failed'):driver.public_call(host,'instance_current',{})


def test_provider_copy_is_only_transport_tables_not_personal_instructions_or_cli_secrets():
    config=__import__('tomllib').loads('\n'.join(driver.provider_tables({'custom':{
        'name':'synthetic','base_url':'https://example.invalid','http_headers':{'X-Key':'synthetic-secret'}}})))
    assert config['model_providers']['custom']['http_headers']['X-Key']=='synthetic-secret'
    with pytest.raises(ValueError,match='unsupported_null'):driver.provider_tables({'x':{'secret':None}})

@pytest.mark.parametrize('injected',[False,True])
def test_actual_daemon_main_uses_injected_factory_or_unchanged_default(tmp_path,monkeypatch,injected):
    from scidiscovery.artifact_agent.interfaces import mcp_daemon
    from scidiscovery.artifact_agent.service import progression
    from scidiscovery.platforms import codex_progression
    selected=[]
    class Coordinator:
        def __init__(self,**kwargs):selected.append(kwargs['host_factory'])
        def start(self):pass
        def close(self):pass
    class Server:
        def __init__(self,*args,**kwargs):self.ready=kwargs['on_ready']
        def serve_forever(self):self.ready()
    marker=object();constructed=[]
    def default(**kwargs):constructed.append(kwargs);return marker
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN
    from scidiscovery.operations.catalog import compile_catalog
    core=compile_catalog((CORE_PLUGIN,PLUGIN))
    monkeypatch.setattr(mcp_daemon,'compile_installed_catalog',lambda:core)
    monkeypatch.setattr(progression,'ProgressionCoordinator',Coordinator)
    monkeypatch.setattr(codex_progression,'CodexProgressionFactory',default)
    monkeypatch.setattr(mcp_daemon,'UnixSocketDaemon',Server)
    monkeypatch.delenv('SCID_AGENT_SETTINGS_FILE',raising=False)
    (tmp_path/'project').mkdir();(tmp_path/'workers').mkdir()
    secret=tmp_path/'secret';secret.write_text('s'*64);secret.chmod(0o600)
    supplied=lambda *args:None
    args=['--project-root',str(tmp_path/'project'),'--state-root',str(tmp_path/'state'),
        '--socket',str(tmp_path/'control.sock'),'--approval-secret-file',str(secret),
        '--runtime-summary',str(tmp_path/'runtime.json'),'--worker-backend','local',
        '--local-workspace-root',str(tmp_path/'workers')]
    assert mcp_daemon.main(args,progression_host_factory=supplied if injected else None)==0
    assert selected==[supplied if injected else marker]
    assert bool(constructed) is not injected
    if constructed:assert constructed[0]['socket_path']==tmp_path/'control.sock'


def test_role_gate_requires_authentic_exact_command_not_agent_completion_chat():
    meter=driver.Meter(lambda:0.);meter.canary_command='/readonly/python -I /readonly/canary.py'
    checks=dict.fromkeys(driver.CANARY_CHECKS,True)
    def event(item):meter.observe({'method':'item/completed','params':{'threadId':'actual','item':item}})
    event({'type':'agentMessage','text':json.dumps(checks)})
    assert not meter.proofs
    item={'type':'commandExecution','id':'command','status':'completed','exitCode':0,
        'command':meter.canary_command,'aggregatedOutput':json.dumps(checks)}
    event({**item,'command':'echo '+json.dumps(checks)});assert not meter.proofs
    event({**item,'exitCode':1});assert not meter.proofs
    event(item);assert meter.proofs['actual']['item_id']=='command'


def test_captured_shell_receipt_matches_only_exact_platform_wrapper():
    expected='/readonly/python -I /readonly/canary.py'
    wrapped="/usr/bin/bash -lc '/readonly/python -I /readonly/canary.py'"
    item={'type':'commandExecution','id':'actual-os-item','source':'unifiedExecStartup',
        'status':'completed','exitCode':0,'command':wrapped,
        'aggregatedOutput':json.dumps(dict.fromkeys(driver.CANARY_CHECKS,True))}
    meter=driver.Meter(lambda:0.);meter.canary_command=expected
    def event(value,thread='actual'):
        meter.observe({'method':'item/completed','params':{'threadId':thread,'item':value}})
    for command in (
            "/bin/bash -lc '/readonly/python -I /readonly/canary.py'",
            "/usr/bin/bash -c '/readonly/python -I /readonly/canary.py'",
            wrapped+' extra', 'env '+wrapped, 'cd /task; '+wrapped,
            "/usr/bin/bash -lc '/readonly/python -I /readonly/canary.py; true'",
            "/usr/bin/bash -lc '/readonly/python /readonly/canary.py'",
            "/usr/bin/bash -lc '/readonly/python -I /readonly/other.py'",
            "/usr/bin/bash -lc 'unterminated"):
        event({**item,'command':command});assert not meter.proofs
    event({**item,'exitCode':1});event({**item,'status':'failed'})
    event({**item,'type':'agentMessage'});assert not meter.proofs
    event(item,'other-thread');assert 'actual' not in meter.proofs
    event(item);assert meter.proofs['actual']['item_id']=='actual-os-item'


@pytest.mark.parametrize('wrapped',[False,True])
def test_role_read_checks_native_inheritance_without_permission_override(tmp_path,wrapped):
    from types import SimpleNamespace
    definition={'filesystem':{':root':'deny','/task':'read'},'network':{'enabled':False}}
    spec={'definition':definition,'root':str(tmp_path)};meter=driver.Meter(lambda:0.)
    path=tmp_path/'codex-home/sessions/role.jsonl';path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'type':'session_meta','payload':{'id':'real-child'}})+'\n'+
        json.dumps({'type':'turn_context','payload':{'turn_id':'actual-turn','model':driver.MODEL,'effort':'high'}})+'\n')
    meter.canary_command='/readonly/python -I /readonly/canary.py'
    item={'type':'commandExecution','id':'native','status':'completed','exitCode':0,
        'command':meter.canary_command,'aggregatedOutput':json.dumps(dict.fromkeys(driver.CANARY_CHECKS,True))}
    if wrapped:item['command']="/usr/bin/bash -lc '/readonly/python -I /readonly/canary.py'"
    requests=[]
    def rpc(method,params):
        requests.append((method,params))
        if method=='thread/read':return {'thread':{'id':'real-child','sessionId':'real-child',
            'forkedFromId':None,'model':driver.MODEL,'reasoningEffort':'high','cwd':'/task',
            'path':str(path),'status':{'type':'idle'},'turns':[{'id':'actual-turn','status':'completed','items':[item]}]}}
        return {'thread':{'sessionId':'real-child'},'activePermissionProfile':{'id':driver.NAME},
            'approvalPolicy':'never','sandbox':{'type':'workspaceWrite','writableRoots':[],'networkAccess':False}}
    host=SimpleNamespace(connection=SimpleNamespace(rpc=rpc))
    result=driver.read_role_proofs(host,meter,spec,{'helper':'real-child'})
    assert result['helper']['platform_session']=='real-child'
    assert result['helper']['executed_profile']['turn_ids']==['actual-turn']
    assert requests[1]==('thread/resume',{'threadId':'real-child','excludeTurns':True})
    original=host.connection.rpc
    def forked(method,params):
        reply=original(method,params)
        if method=='thread/read':reply['thread']['forkedFromId']='development-thread'
        return reply
    host.connection.rpc=forked
    with pytest.raises(RuntimeError,match='history_unconfirmed'):
        driver.read_role_proofs(host,meter,spec,{'helper':'real-child'})
    host.connection.rpc=original
    def wrong_identity(method,params):
        reply=original(method,params)
        if method=='thread/read':reply['thread']['id']='different-thread'
        return reply
    host.connection.rpc=wrong_identity
    with pytest.raises(RuntimeError,match='identity_profile_or_history_unconfirmed'):
        driver.read_role_proofs(host,meter,spec,{'helper':'real-child'})
    host.connection.rpc=original
    path.write_text(path.read_text().replace(driver.MODEL,'gpt-6-astra'))
    with pytest.raises(RuntimeError,match='executed_model_drift'):
        driver.read_role_proofs(host,meter,spec,{'helper':'real-child'})


def test_real_subagent_activity_shape_discovers_exact_parent_and_counts_distinct_turns():
    meter=driver.Meter(lambda:0.)
    item={'type':'subAgentActivity','id':'spawn-call','agentPath':'/root/qualification_helper',
        'agentThreadId':'actual-child','kind':'started'}
    for kind in ('started','completed'):
        meter.observe({'method':'item/completed','params':{'threadId':'actual-root','item':{**item,'kind':kind}}})
    meter.observe({'method':'item/completed','params':{'threadId':'actual-root','item':{
        'type':'collabAgentToolCall','senderThreadId':'actual-root','receiverThreadIds':[]}}})
    for thread in ('actual-root','actual-child'):
        for _ in range(3):meter.observe(usage(thread))
        meter.observe({'method':'turn/completed','params':{'threadId':thread,'turn':{'id':'turn'}}})
    assert meter.children=={'actual-child':'actual-root'}
    assert len(meter.observed_turns)==2 and meter.total()==240
    with pytest.raises(RuntimeError,match='child_identity_conflict'):
        meter.observe({'method':'item/completed','params':{'threadId':'other-root','item':item}})


def test_actual_canary_request_names_frozen_model_and_stops_on_discovered_child_drift(tmp_path):
    from types import SimpleNamespace
    project=tmp_path/'project';project.mkdir()
    spec={'root':str(tmp_path),'project':str(project),'arm':'native_goal','task_python':'/readonly/python',
        'public_sha256':{'instruction.md':'synthetic','harness/exp_cli.py':'synthetic'}}
    meter=driver.Meter(lambda:0.);prompts=[];requests=[]
    def start(prompt):
        prompts.append(prompt)
        meter.observe({'method':'turn/started','params':{'threadId':'root','turn':{'id':'root-turn'}}})
    def poll(_):
        meter.observe({'method':'item/completed','params':{'threadId':'root','item':{
            'type':'subAgentActivity','id':'spawn','agentPath':'/root/helper','agentThreadId':'child','kind':'started'}}})
    def rpc(method,params):
        requests.append((method,params));return {'thread':{'id':'child','forkedFromId':None,
            'model':'gpt-6-astra','reasoningEffort':'high'}}
    host=SimpleNamespace(identity=SimpleNamespace(thread_id='root'),completion=None,start_turn=start,
        connection=SimpleNamespace(poll=poll,rpc=rpc))
    with pytest.raises(RuntimeError,match='profile_or_history_unconfirmed'):
        driver.role_canary(host,meter,spec)
    assert 'model=gpt-6.1-sol, reasoning_effort=high, fork_turns=none' in prompts[0]
    assert requests==[('thread/read',{'threadId':'child','includeTurns':False})]
    assert meter.turns_requested==1 and meter.scientific_turns_requested==0
    assert len(meter.observed_turns)==1 and meter.deadline==1800


def test_executed_profile_requires_actual_own_log_and_every_completed_turn(tmp_path):
    spec={'root':str(tmp_path)};path=tmp_path/'codex-home/sessions/role.jsonl';path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'type':'session_meta','payload':{'id':'actual'}})+'\n'+
        json.dumps({'type':'turn_context','payload':{'turn_id':'first','model':driver.MODEL,'effort':'high'}})+'\n')
    thread={'id':'actual','path':str(path),'turns':[{'id':'first','status':'completed'}]}
    assert driver.role_turn_profiles(thread,spec)['model']==driver.MODEL
    thread['turns'].append({'id':'missing','status':'completed'})
    with pytest.raises(RuntimeError,match='profile_unconfirmed'):driver.role_turn_profiles(thread,spec)
    thread['turns'].pop();path.unlink();path.symlink_to(tmp_path/'outside')
    with pytest.raises(RuntimeError,match='profile_unconfirmed'):driver.role_turn_profiles(thread,spec)


def test_canary_and_control_usage_share_budget_without_reset_or_double_count():
    meter=driver.Meter(lambda:0.);meter.activate()
    meter.observe(usage('canary-root',100,20));meter.observe(usage('worker',200,30))
    record=meter.records['worker'];meter.control_records={'worker':record}
    assert meter.total()==350
    meter.control_records['new-science-root']={'counted_tokens':{'input_tokens':50,'output_tokens':10}}
    assert meter.total()==410
    meter.observe(usage('new-science-root',55,12))
    assert meter.total()==417 and meter.deadline==1800
    with pytest.raises(RuntimeError,match='already_submitted'):meter.activate()


@pytest.mark.parametrize('tokens,wall',[(200000,1800),(112607,1761),(2000000,1800)])
def test_scientific_native_goal_starts_directly_with_exact_frozen_budget(tmp_path,monkeypatch,tokens,wall):
    from types import SimpleNamespace
    import scidiscovery.artifact_agent.interfaces.mcp_daemon as installed
    source=pair(tmp_path,monkeypatch)
    def init(command,**kwargs):
        project=Path(command[command.index('--project-root')+1]);(project/'.codex').mkdir()
        (project/'.codex/config.toml').write_text('web_search="disabled"\n')
        return SimpleNamespace(returncode=0,stdout=b'fixture')
    monkeypatch.setattr(driver.subprocess,'run',init)
    prepared=driver.prepare(source,tmp_path/'runtime',native_bundle(tmp_path),
        native_goal_tokens=tokens,native_goal_wall_seconds=wall)
    spec=json.loads(Path(prepared['arms']['native_goal']).read_text())
    monkeypatch.setattr(installed,'__file__',str(Path(spec['python']).parent.parent/'installed-mcp-daemon.py'))
    requests=[]; hosts=[]
    def launch(spec,meter):
        thread='fresh-science-root'
        def rpc(method,params):
            requests.append((thread,method,params))
            if method=='command/exec':
                for name in ('workspace','runs','submission'):Path(spec['project'],name,'canary').write_text('synthetic')
                return {'exitCode':0,'stdout':json.dumps(dict.fromkeys(driver.CANARY_CHECKS,True))}
            if method=='account/read':return {'account':{'type':'synthetic-fixture'}}
            if method=='model/list':return {'data':[{'model':driver.MODEL}],'nextCursor':None}
            if method=='thread/goal/get':return {'goal':{'status':'complete','tokensUsed':10}}
            return {}
        connection=SimpleNamespace(rpc=rpc,poll=lambda _:None)
        def turn(text):
            requests.append((thread,'turn/start',{'text':text}));meter.observe(usage(thread,10,5))
        host=SimpleNamespace(identity=SimpleNamespace(thread_id=thread,session_id=thread),
            connection=connection,start_turn=turn,guard_resources=lambda:None,close=lambda:None)
        hosts.append(host);return host
    monkeypatch.setattr(driver,'launch_root',launch)
    def unexpected(*args):raise AssertionError('paid synthetic canary must not run')
    monkeypatch.setattr(driver,'role_canary',unexpected)
    result=driver.arm_action(spec,'run')
    assert result['status']=='stopped_not_scored'
    assert result['observed_total_tokens']==15 and len(hosts)==1
    paused=next(params for thread,method,params in requests if thread=='fresh-science-root' and method=='thread/goal/set' and params['status']=='paused')
    assert paused['tokenBudget']==tokens
    assert result['limits']==spec['limits']
    science_prompt=next(params['text'] for thread,method,params in requests if method=='turn/start')
    assert 'gpt-6.1-sol/high' in science_prompt
    assert science_prompt==driver.science_prompt(spec)
    assert result['science_prompt_sha256']==__import__('hashlib').sha256(science_prompt.encode()).hexdigest()
    assert len([r for r in requests if r[1]=='turn/start'])==1
    assert result['scientific_identity']['thread_id']=='fresh-science-root'
    assert result['turns_requested']==1 and result['scientific_turns_requested']==1
    assert result['observed_all_role_turns']==1
    assert result['science_started'] and Path(spec['root'],'model-submission-started').exists()
    assert 'role_canary' not in result
    assert 'paid synthetic role qualification not run' in result['qualification']
    assert result['actual_worker_helper_isolation']=='not_verified'  # simulation never earns live qualification.


def test_reduced_arm_limits_stop_invalid_limits_reject_and_legacy_defaults_remain():
    budget={'all_role_tokens':112607,'trial_wall_seconds':1761}
    assert driver.arm_limits({'limits':budget})==budget
    assert driver.arm_limits({})=={'all_role_tokens':200000,'trial_wall_seconds':1800}
    for key,values in {'all_role_tokens':(0,-1,True,2000001,'112607'),
            'trial_wall_seconds':(0,-1,True,1801,1761.0)}.items():
        for value in values:
            with pytest.raises(ValueError,match='arm_budget'):
                driver.arm_limits({'limits':{**budget,key:value}})
    with pytest.raises(ValueError,match='arm_budget'):
        driver.arm_limits({'limits':{**budget,'unknown':1}})
    now=[0.];meter=driver.Meter(lambda:now[0],tokens=112607,wall_seconds=1761)
    meter.activate();meter.observe(usage('canary',100,20))
    meter.observe(usage('science',112480,1))
    assert meter.total()==112601
    with pytest.raises(RuntimeError,match='observed_token_limit'):
        meter.observe(usage('science',112487,1))
    assert meter.total()==112608
    meter=driver.Meter(lambda:now[0],tokens=112607,wall_seconds=1761);meter.activate()
    now[0]=1760;meter.check();now[0]=1761
    with pytest.raises(RuntimeError,match='wall_deadline'):meter.check()


@pytest.mark.parametrize('failure',[None,'authorization','usage'])
@pytest.mark.parametrize('automated',[False,True])
def test_scidiscovery_starts_actual_objective_with_ui_authority_and_control_meter(tmp_path,monkeypatch,failure,automated,capsys):
    from types import SimpleNamespace
    import scidiscovery.artifact_agent.interfaces.mcp_daemon as installed
    source=pair(tmp_path,monkeypatch)
    authorization=tmp_path/'authorization.txt'
    authorization.write_text('For this Covshift comparison, create and bind a fresh instance and confirm the exact authorized arm budget.')
    def init(command,**kwargs):
        project=Path(command[command.index('--project-root')+1]);(project/'.codex').mkdir()
        (project/'.codex/config.toml').write_text('web_search="disabled"\n')
        return SimpleNamespace(returncode=0,stdout=b'fixture')
    monkeypatch.setattr(driver.subprocess,'run',init)
    prepared=driver.prepare(source,tmp_path/'runtime',native_bundle(tmp_path),
        native_goal_tokens=32736,scidiscovery_tokens=32736,
        auto_manage_instance=automated,management_authorization_file=authorization if automated else None)
    spec=json.loads(Path(prepared['arms']['scidiscovery']).read_text())
    native=json.loads(Path(prepared['arms']['native_goal']).read_text())
    assert driver.science_prompt(spec)==driver.science_prompt(native)
    monkeypatch.setattr(installed,'__file__',str(Path(spec['python']).parent.parent/'installed-mcp-daemon.py'))
    monkeypatch.setattr(driver,'start_control',lambda spec:([],'http://management.invalid'))
    monkeypatch.setattr(driver.time,'sleep',lambda _:None)
    calls=[];current_calls=[];checks=[];management=[]
    class Management:
        def __init__(self,url):management.append(('url',url))
        def create(self,name):management.append(('create',name))
        def authorize(self):management.append(('authorize',driver.OBJECTIVE))
    monkeypatch.setattr(driver,'PilotManagement',Management)
    def rpc(method,params):
        if method=='command/exec':
            for name in ('workspace','runs','submission'):Path(spec['project'],name,'canary').write_text('synthetic')
            return {'exitCode':0,'stdout':json.dumps(dict.fromkeys(driver.CANARY_CHECKS,True))}
        if method=='account/read':return {'account':{'type':'synthetic-fixture'}}
        if method=='model/list':return {'data':[{'model':driver.MODEL}],'nextCursor':None}
        raise AssertionError('unexpected RPC '+method)
    host=SimpleNamespace(identity=SimpleNamespace(thread_id='frontend',session_id='frontend'),
        connection=SimpleNamespace(rpc=rpc,poll=lambda _:None),close=lambda:None,
        verify_tools_and_session=lambda **kwargs:None)
    monkeypatch.setattr(driver,'launch_root',lambda *args:host)
    def public(host,name,arguments):
        calls.append((name,arguments))
        if name=='instance_current':
            current_calls.append(name)
            return {'state':'unbound' if len(current_calls)==1 else 'active',
                'name':management[1][1] if automated and len(management)>1 else 'selected',
                'management_url':'http://management.invalid/exact-page'}
        if name=='run_list':return {'runs':[]}
        if name=='progression_status':
            return {'objective_name':'wrong' if failure=='authorization' else driver.OBJECTIVE,
                'state':'stopped','budget':{'observed_tokens':15},
                'loop':{'id':'loop','managed':True,'authority':'explicit_management_ui_budget_confirmation',
                    'limits':{'max_tokens':32736,'max_elapsed_seconds':1800}}}
        if name in ('artifact_ingest_text','progression_command'):return {}
        raise AssertionError('unexpected public call '+name)
    monkeypatch.setattr(driver,'public_call',public)
    monkeypatch.setattr(driver,'confirm_loop',lambda spec,current,scheduling,objective:checks.append(objective))
    def unexpected(*args):raise AssertionError('paid synthetic canary must not run')
    monkeypatch.setattr(driver,'role_canary',unexpected)
    measured=driver.Meter(lambda:0.);measured.observe(usage('science-root',10,5))
    record=measured.records['science-root'];record['has_gaps']=failure=='usage'
    monkeypatch.setattr(driver,'control_usage',lambda *args:{'instance':'selected','loop':'loop',
        'records':{'science-root':{**record,'owner':'selected','loop_id':'loop','role':'root'}},
        'participants':{},'frontend_unmeasured':False})
    result=driver.arm_action(spec,'run')
    assert result['status']==('stopped_not_scored' if failure is None else 'fail')
    output=capsys.readouterr().out
    assert ('http://management.invalid/exact-page' in output) is not automated
    ingested=[arguments for name,arguments in calls if name=='artifact_ingest_text']
    assert ingested[0]=={'name':driver.OBJECTIVE,'text':driver.science_prompt(native),'on_conflict':'reject'}
    if automated:
        assert ingested[1]=={'name':'covshift.pilot.management.authorization','text':authorization.read_text(),'on_conflict':'reject'}
        assert management[-1]==('authorize',driver.OBJECTIVE)
        assert result['management_authorization']['source']=='explicit_user_instruction'
        assert result['created_instance_name'].startswith('covshift.pilot.')
    else:
        assert len(ingested)==1 and not management
    starts=[arguments for name,arguments in calls if name=='progression_command']
    if failure=='authorization':
        assert not checks and not starts and not result['trial_started']
        assert result['reason']=='actual_loop_authorization_mismatch'
        assert not Path(spec['root'],'model-submission-started').exists()
    else:
        assert checks==[driver.OBJECTIVE]
        assert starts==[{'command':'start','mode':'background','objective_name':driver.OBJECTIVE}]
        assert result['trial_started'] and result['science_started']
        assert result['limits']=={'all_role_tokens':32736,'trial_wall_seconds':1800}
        assert Path(spec['root'],'model-submission-started').exists()
        if failure=='usage':assert result['reason']=='participant_usage_unconfirmed'
        else:assert result['observed_total_tokens']==15
    assert result['turns_requested']==0 and 'role_canary' not in result
    assert result['actual_worker_helper_isolation']=='not_verified'


def test_auto_management_requires_authorization_before_preparation(tmp_path,monkeypatch):
    source=pair(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match='explicit_management_authorization_required'):
        driver.prepare(source,tmp_path/'runtime',native_bundle(tmp_path),auto_manage_instance=True)
    assert not (tmp_path/'runtime').exists()


def test_auto_management_uses_real_http_csrf_capability_and_loop_confirmation(tmp_path,monkeypatch):
    from scidiscovery.agent_execution_settings import AgentSettings,effective_settings
    from scidiscovery.artifact_agent.approval_ui.read_model import InstanceReadModel
    from tests.operations.test_m6a_direct_instance_management import _setup,_root
    settings=AgentSettings().model_dump(exclude_none=True)
    settings['progression'].update(enabled=True,max_tokens=2000000,max_elapsed_seconds=1800,max_calendar_seconds=1800,
        root_model=driver.MODEL,root_reasoning_effort='high',token_policy='bounded_fallback')
    settings_path=tmp_path/'agent-settings.json';driver.write(settings_path,settings)
    monkeypatch.setenv('SCID_AGENT_SETTINGS_FILE',str(settings_path))
    runtime,state,secret,ui,base=_setup(tmp_path)
    ui.read_model=InstanceReadModel(artifacts=runtime.artifacts,bindings=runtime.scheduler_bindings,
        runs=runtime.runs,approvals=runtime.approvals,executions=runtime.executions,
        operation_catalog=runtime.operation_catalog)
    root=_root(runtime,session_key='sch_'+'1'*32,secret=secret,base=base)
    try:
        current=root.call_tool('instance_current',{})
        assert current['state']=='unbound'
        management=driver.PilotManagement(current['management_url'])
        management.create('covshift.pilot.http-fixture')
        current=root.call_tool('instance_current',{})
        assert current['name']=='covshift.pilot.http-fixture'
        root.call_tool('artifact_ingest_text',{'name':driver.OBJECTIVE,'text':'Original public Covshift task fixture.','on_conflict':'reject'})
        management.authorize()
        scheduling=root.call_tool('progression_status',{})
        assert scheduling['objective_name']==driver.OBJECTIVE
        assert scheduling['loop']['authority']=='explicit_management_ui_budget_confirmation'
        assert scheduling['loop']['limits']['max_tokens']==2000000
        assert scheduling['loop']['limits']['max_elapsed_seconds']==1800
        assert scheduling['state']=='paused'
        assert root.call_tool('run_list',{'limit':1})['runs']==[]
        # The capability and real CSRF/confirmation remain enforced by the existing UI.
        with pytest.raises(RuntimeError,match='management_form_rejected'):
            management.request('/instances/progression',{'capability':management.capability,
                'csrf':'wrong','command':'pause'})
    finally:ui.stop()
    for url in ('http://example.invalid/sessions/test?capability=x',
            'http://127.0.0.1/instances?capability=x','http://127.0.0.1/sessions/test'):
        with pytest.raises(RuntimeError):driver.PilotManagement(url)


def test_actual_launcher_supervisor_uses_reduced_frozen_arm_cap(tmp_path,monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace
    source=pair(tmp_path,monkeypatch)
    def init(command,**kwargs):
        project=Path(command[command.index('--project-root')+1]);(project/'.codex').mkdir()
        (project/'.codex/config.toml').write_text('web_search="disabled"\n')
        return SimpleNamespace(returncode=0,stdout=b'fixture')
    monkeypatch.setattr(driver.subprocess,'run',init)
    prepared=driver.prepare(source,tmp_path/'runtime',native_bundle(tmp_path),
        native_goal_tokens=112607,native_goal_wall_seconds=1761)
    spec_path=prepared['arms']['native_goal'];observed=[]
    @contextmanager
    def lease(): yield SimpleNamespace(fileno=lambda:77)
    monkeypatch.setattr(driver.guard,'serial_lock',lease)
    def supervised(command,environment,limits,output,lock_fd):
        observed.append((command,limits,lock_fd))
        return {'returncode':0,'stop_reason':'exited'}  # Inspect owned dispatch; no process or paid request.
    monkeypatch.setattr(driver.guard,'run_one',supervised)
    monkeypatch.setattr(driver.sys,'argv',['run_covshift_pilot.py','run','--spec',spec_path])
    assert driver.main()==0
    assert observed[0][1]['timeout_seconds']==300+1761 and observed[0][2]==77
    assert observed[0][1]['observed_tree_rss_stop_bytes']==1500000000
    assert 'address_space_bytes' not in observed[0][1]
    assert observed[0][0][observed[0][0].index('--spec')+1]==spec_path


def test_failed_alias_precheck_never_activates_goal_or_sends_scientific_turn(tmp_path,monkeypatch):
    from types import SimpleNamespace
    import scidiscovery.artifact_agent.interfaces.mcp_daemon as installed
    source=pair(tmp_path,monkeypatch)
    def init(command,**kwargs):
        project=Path(command[command.index('--project-root')+1]);(project/'.codex').mkdir()
        (project/'.codex/config.toml').write_text('web_search="disabled"\n')
        return SimpleNamespace(returncode=0,stdout=b'fixture')
    monkeypatch.setattr(driver.subprocess,'run',init)
    prepared=driver.prepare(source,tmp_path/'runtime',native_bundle(tmp_path))
    spec=json.loads(Path(prepared['arms']['native_goal']).read_text())
    monkeypatch.setattr(installed,'__file__',str(Path(spec['python']).parent.parent/'installed-mcp-daemon.py'))
    methods=[]
    def rpc(method,params):
        methods.append(method)
        if method=='command/exec':
            for name in ('workspace','runs','submission'):Path(spec['project'],name,'canary').write_text('synthetic')
            return {'exitCode':0,'stdout':json.dumps({**dict.fromkeys(driver.CANARY_CHECKS,True),'private_denied':False})}
        if method=='account/read':return {'account':{'type':'synthetic-fixture'}}
        if method=='model/list':return {'data':[{'model':driver.MODEL}],'nextCursor':None}
        return {}
    monkeypatch.setattr(driver,'launch_root',lambda *a:SimpleNamespace(identity=SimpleNamespace(thread_id='actual',session_id='actual'),
        connection=SimpleNamespace(rpc=rpc),close=lambda:None))
    result=driver.arm_action(spec,'run')
    assert result['status']=='fail' and result['reason']=='task_alias_canary_failed'
    assert 'turn/start' not in methods and 'thread/goal/set' not in methods
    assert result['turns_requested']==result['scientific_turns_requested']==0
    assert not result['trial_started'] and not Path(spec['root'],'model-submission-started').exists()
    methods.clear()
    Path(spec['code_mode_host']['path']).write_bytes(b'changed runtime')
    result=driver.arm_action(spec,'run')
    assert result['reason']=='code_mode_runtime_changed_or_unfrozen' and not methods


def test_exact_loop_profile_rejects_ui_model_override_before_paid_canary(tmp_path):
    import sqlite3
    from scidiscovery.agent_execution_settings import AgentSettings,effective_settings
    root=tmp_path/'root';(root/'state/database').mkdir(parents=True)
    settings=AgentSettings();driver.write(root/'agent-settings.json',settings.model_dump(exclude_none=True))
    expected=effective_settings(settings,{})
    with sqlite3.connect(root/'state/database/scheduler-bindings.sqlite3') as db:
        db.executescript("CREATE TABLE scheduler_instances(instance_id TEXT,name TEXT); CREATE TABLE scheduler_progression(instance_id TEXT,config_json TEXT,objective_ref_json TEXT,checkpoint_json TEXT,state TEXT,reason TEXT,host_json TEXT,owner_session TEXT); CREATE TABLE scheduler_bindings(instance TEXT,namespace TEXT,name TEXT,object_id TEXT);")
        db.execute('INSERT INTO scheduler_instances VALUES (?,?)',('instance','selected'))
        db.execute('INSERT INTO scheduler_bindings VALUES (?,?,?,?)',('instance','artifact','synthetic','exact-goal'))
        db.execute('INSERT INTO scheduler_progression VALUES (?,?,?,?,?,?,?,?)',('instance',json.dumps({'effective':expected}),json.dumps({'artifact_id':'exact-goal'}),json.dumps({'current_loop_id':'loop'}),'paused','loop_authorized',None,None))
    spec={'root':str(root)};current={'name':'selected'};scheduling={'loop':{'id':'loop','limits':expected['progression']}}
    driver.confirm_loop(spec,current,scheduling,'synthetic')
    changed=json.loads(json.dumps(expected));changed['progression']['root_model']='wrong-model'
    with sqlite3.connect(root/'state/database/scheduler-bindings.sqlite3') as db:
        db.execute('UPDATE scheduler_progression SET config_json=?',(json.dumps({'effective':changed}),))
    with pytest.raises(RuntimeError,match='frozen_loop_profile_scope_or_authorization_changed'):
        driver.confirm_loop(spec,current,scheduling,'synthetic')


def test_real_interactive_background_partial_is_supplemented_not_reset(tmp_path):
    from tests.operations.test_progression import _progression_fixture
    from scidiscovery.artifact_agent.service.research_loops import current_loop
    fixture=_progression_fixture(tmp_path)
    p=next(fixture)
    try:
        bindings=p.runtime.scheduler_bindings
        p.root.call_tool('progression_command',dict(command='pause'))
        p.root.call_tool('progression_command',dict(command='start',mode='interactive',objective_name='goal'))
        from tests.operations.test_local_worker_contracts import _invoke
        from tests.operations.worker_fixtures import attached_worker
        from tests.operations.research_loop_fixtures import measured_fixture_usage
        _invoke(p.root)
        worker=attached_worker(p.runtime,p.root,'observation')
        worker.call_tool('worker_open_assignment',{})
        measured_fixture_usage(worker)
        p.root.call_tool('progression_command',dict(command='pause'))
        p.root.call_tool('progression_command',dict(command='start',mode='background',objective_name='goal'))
        row=bindings.progression_status(instance_id=p.instance,internal=True);cp=json.loads(row['checkpoint_json'])
        loop=current_loop(cp)
        assert cp['loop_authorizations'][loop]['unmeasured_frontend_root'] is True
        assert bindings.progression_status(instance_id=p.instance)['budget']['token_coverage']=='partial'
        snapshot=driver.control_usage({'root':str(tmp_path)},loop,{'name':'local_worker'})
        assert snapshot['frontend_unmeasured'] and snapshot['records']
        worker_thread=worker._trusted_caller[1]
        assert snapshot['participants'][worker_thread]==('worker',worker._trusted_caller[0])
        meter=driver.Meter(lambda:0.);meter.activate()
        # These fixtures stand in for already-verified platform command receipts;
        # the real control marker above is neither patched nor cleared.
        meter.frontend_loop=loop
        meter.frontend_roles={'root':{'thread_id':'root','platform_session':'root'},
            'worker':{'thread_id':worker_thread,'platform_session':worker._trusted_caller[0]},
            'helper':{'thread_id':'helper','platform_session':'helper'}}
        snapshot['participants']['helper']=('helper','helper')
        for thread in ('root',worker_thread,'helper'):meter.observe(usage(thread,100,20))
        assert driver.reconcile_control(meter,snapshot)['coverage']=='observed_with_frontend_receipts'
        assert meter.total()==360 and meter.deadline==1800
        from copy import deepcopy
        missing=deepcopy(meter);now=[0.];missing.clock=lambda:now[0]
        incomplete={**snapshot,'participants':{**snapshot['participants'],'missing':('worker','missing')}}
        assert driver.reconcile_control(missing,incomplete)['coverage']=='pending_native_usage'
        now[0]=6
        with pytest.raises(RuntimeError,match='native_activity_unconfirmed'):driver.reconcile_control(missing,incomplete)
        copied={**snapshot,'records':{thread:dict(record) for thread,record in snapshot['records'].items()}}
        copied['records'][worker_thread]['loop_id']='wrong-loop'
        with pytest.raises(RuntimeError,match='control_usage_scope_conflict'):driver.reconcile_control(meter,copied)
        copied['records'][worker_thread]['loop_id']=loop;copied['records'][worker_thread]['owner']='other-instance'
        with pytest.raises(RuntimeError,match='control_usage_scope_conflict'):driver.reconcile_control(meter,copied)
        meter.records['helper']['has_gaps']=True
        with pytest.raises(RuntimeError,match='usage_unconfirmed'):driver.reconcile_control(meter,snapshot)
        assert bindings.progression_status(instance_id=p.instance)['budget']['token_coverage']=='partial'
    finally:
        fixture.close()


@pytest.mark.parametrize('role',['worker','helper'])
def test_actual_native_pending_first_usage_and_terminal_gap(tmp_path,role):
    from tests.operations.test_progression import _progression_fixture
    from tests.operations.test_local_worker_contracts import _invoke
    from tests.operations.worker_fixtures import attached_worker
    from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
    from tests.operations.test_unified_mcp import result
    fixture=_progression_fixture(tmp_path);p=next(fixture)
    try:
        p.coordinator.tick()
        p.root=p.root.__class__(p.facade(p.coordinator.host.scheduler_session))
        _invoke(p.root)
        worker=attached_worker(p.runtime,p.root,'observation');worker.call_tool('worker_open_assignment',{})
        thread=worker._trusted_caller[1]
        if role=='helper':
            worker.call_tool('worker_helper',dict(name='pending-helper',task='Inspect only a finite synthetic fixture.'))
            thread='actual-pending-helper'
            profile=p.runtime.runs.status(worker._run_id).execution_profile['profile']
            reply=UnifiedMCPRouter(p.root).handle(dict(jsonrpc='2.0',id=1,method='tools/call',params=dict(
                name='scid_call',arguments=dict(name='worker_open_assignment',arguments={}),
                _meta={'x-codex-turn-metadata':dict(session_id=worker._trusted_caller[0],thread_id=thread,
                    parent_thread_id=worker._trusted_caller[1],subagent_kind='thread_spawn',
                    model=profile['model'],reasoning_effort=profile['reasoning_effort'])})))
            assert result(reply)['state']=='opened'
        bindings=p.runtime.scheduler_bindings
        row=bindings.progression_status(instance_id=p.instance,internal=True)
        expected_host=json.loads(row['host_json']);loop=json.loads(row['checkpoint_json'])['current_loop_id']
        root_thread=p.coordinator.host.identity.thread_id
        bindings.observe_progression(instance_id=p.instance,expected_host=expected_host,changes={},
            usage_observation=dict(params=usage(root_thread,10,1)['params'],identity={'role':'root','loop_id':loop},root_thread=root_thread))
        identity=p.runtime.runs.native_loop_identities(instance_id=p.instance,loop_id=loop,capacity=16)[thread]
        observation=dict(identity=identity,source='turn_started',turn_id='first-native-turn',connection_id='actual-control-connection')
        bindings.observe_progression(instance_id=p.instance,expected_host=expected_host,changes={},native_observation=observation)
        spec={'root':str(tmp_path)};current={'name':'local_worker'}
        snapshot=driver.control_usage(spec,loop,current)
        assert snapshot['records'][thread]['pending_observation'] is True
        assert snapshot['records'][thread]['coverage']=='missing'
        now=[0.];meter=driver.Meter(lambda:now[0]);meter.activate()
        # The owner Worker also exists in helper cases. Only that distinct
        # owner's synthetic counters are supplied; the target has no first usage.
        if role=='helper':meter.observe(usage(worker._trusted_caller[1],10,1))
        pending=driver.reconcile_control(meter,snapshot)
        assert pending['coverage']=='pending_native_usage' and thread in pending['pending_threads']
        now[0]=7  # real native in-flight proof, not merely Run.running.
        assert driver.reconcile_control(meter,snapshot)['coverage']=='pending_native_usage'
        # The original pending snapshot supplies genuine terminal facts without
        # a usage update, not a fabricated all-zero measured record.
        bindings.observe_progression(instance_id=p.instance,expected_host=expected_host,changes={},
            native_observation={**observation,'source':'thread_read','state':'completed'})
        absent=driver.control_usage(spec,loop,current)
        assert absent['records'][thread]['pending_observation'] and absent['records'][thread]['native_terminal']['state']=='completed'
        fresh=driver.Meter(lambda:now[0]);fresh.activate()
        if role=='helper':fresh.observe(usage(worker._trusted_caller[1],10,1))
        assert driver.reconcile_control(fresh,absent)['coverage']=='pending_native_usage'
        now[0]+=6
        with pytest.raises(RuntimeError,match='participant_usage_unconfirmed'):driver.reconcile_control(fresh,absent)
        bindings.observe_progression(instance_id=p.instance,expected_host=expected_host,changes={},
            usage_observation=dict(params=usage(thread,100,20)['params'],identity=identity,root_thread='not-this-thread'))
        measured=driver.control_usage(spec,loop,current)
        assert 'pending_observation' not in measured['records'][thread]
        assert driver.reconcile_control(meter,measured)['coverage']=='observed_with_frontend_receipts'
        assert meter.total()==(142 if role=='helper' else 131) and meter.deadline==1800
    finally:fixture.close()


def test_explicit_memory_budget_overrides_both_supervisors():
    spec={'resources':{'observed_tree_rss_stop_bytes':13000000000,
        'app_server_tree_rss_bytes':13000000000,'minimum_available_bytes':1000000000,
        'available_drop_stop_bytes':13000000000}}
    limits,app=driver.resource_limits(spec)
    assert app==limits['observed_tree_rss_stop_bytes']==13000000000
    assert limits['minimum_available_bytes']==1000000000
    assert limits['available_drop_stop_bytes']==13000000000
    for bad in ({'app_server_tree_rss_bytes':0},{'unknown':1},
                {'app_server_tree_rss_bytes':True},{'app_server_tree_rss_bytes':2000000000}):
        with pytest.raises(ValueError,match='invalid_resource_budget'):
            driver.resource_limits({'resources':bad})
