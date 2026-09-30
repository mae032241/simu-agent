"""Real daemon and native-protocol subprocesses; no model or external effects."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import pytest

from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService
from scidiscovery.platforms.codex_progression import CodexProgressionFactory
from scidiscovery.platforms.codex_app_server import HostError
from tests.operations.test_progression import progression, checkpoint, row

pytestmark = pytest.mark.process_e2e

PEER = r'''
import json,os,socket,sys
from pathlib import Path
config=json.loads(Path(os.environ['SCID_TEST_CONFIG']).read_text())
mode=os.environ.get('SCID_TEST_MODE','complete')
requests=Path(os.environ['SCID_TEST_REQUESTS'])
def emit(value):print(json.dumps(value),flush=True)
for line in sys.stdin:
    msg=json.loads(line)
    with requests.open('a') as f:f.write(json.dumps(msg)+'\n')
    if 'id' not in msg:continue
    method,p=msg['method'],msg['params']
    if method=='initialize':result={}
    elif method=='config/read':result={'config':config}
    elif method in ('thread/start','thread/resume'):
        # A conflicting personal config wins unless the request declares its own policy.
        effective={'approvalPolicy':'on-request','sandbox':{'type':'dangerFullAccess'}}
        if 'sandbox' in p and not os.environ.get('SCID_TEST_IGNORE_PERMISSIONS'):
            net=p.get('config',{}).get('sandbox_workspace_write',{}).get('network_access',False)
            if os.environ.get('SCID_TEST_NETWORK_MISMATCH'):net=not net
            effective={'approvalPolicy':p['approvalPolicy'],'sandbox':{'type':{'read-only':'readOnly','workspace-write':'workspaceWrite'}[p['sandbox']],'networkAccess':net,'writableRoots':[]}}
        result={'thread':{'id':p.get('threadId','native-root'),'sessionId':'native-root'},**effective}
    elif method=='thread/read':
        status=('inProgress' if p['threadId']=='owner' else os.environ.get('SCID_TEST_HELPER_STATUS','completed') if p['threadId']=='helper' else os.environ.get('SCID_TEST_ROOT_STATUS','completed'))
        result={'thread':{'id':p['threadId'],'turns':[] if status=='missing' else [{'id':'exact-turn','status':status}]}}
    elif method=='mcpServerStatus/list':
        result={'data':[{'name':'scidiscovery','tools':{} if mode=='missing-tools' else
            {'scid_catalog':{},'scid_describe':{},'scid_call':{}}}]}
    elif method=='mcpServer/tool/call':
        if os.environ.get('SCID_TEST_FORWARD'):
            request={'jsonrpc':'2.0','id':1,'method':'tools/call',
                '_scidiscovery_scheduler_proxy':'sch_'+'b'*32,
                'params':{'name':p['tool'],'arguments':p['arguments'],'_meta':p['_meta']}}
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
                connection.connect(config['mcp_servers']['scidiscovery']['args'][-1])
                connection.sendall(json.dumps(request).encode()+b'\n')
                response=json.loads(connection.makefile('rb').readline())
            result=response['result']
        else:result={'structuredContent':{'management_url':'http://127.0.0.1:8765/sessions/sch_'+'b'*32+'?capability=test'}}
    elif method=='turn/start':
        if mode=='blocked-turn':
            import time
            time.sleep(5)
            continue
        if mode=='lost':sys.exit(0)
        turn='recovery-turn' if os.environ.get('SCID_TEST_ROOT_STATUS')=='interrupted' else 'exact-turn'
        emit({'method':'turn/started','params':{'threadId':'native-root','turn':{'id':turn}}})
        if mode in {'denial', 'user-input', 'unknown-request'}:
            method=os.environ.get('SCID_TEST_SERVER_METHOD','item/commandExecution/requestApproval')
            body={'threadId':'native-root','turnId':turn,'itemId':'tool-1','startedAtMs':0,'cwd':'/private',
                'permissions':{'network':{'enabled':True}},'isBlocking':True,
                'questions':[{'id':'data','header':'Missing data','question':'Which measurement applies?'}]}
            if os.environ.get('SCID_TEST_SERVER_PAYLOAD'):
                body={'threadId':'native-root','turnId':turn,'itemId':'tool-1',**json.loads(os.environ['SCID_TEST_SERVER_PAYLOAD'])}
            emit({'id':73,'method':method,'params':body})
            if mode=='denial':
                reply=json.loads(sys.stdin.readline())
                with requests.open('a') as f:f.write(json.dumps(reply)+'\n')
        if mode=='accepted-lost':sys.exit(0)
        result={'turn':{'id':turn}}
        emit({'id':msg['id'],'result':result})
        emit({'method':'thread/tokenUsage/updated','params':{'threadId':'native-root','tokenUsage':{'total':{'inputTokens':100,'cachedInputTokens':50,'outputTokens':20}}}})
        if mode not in {'running','interrupt-disconnect','interrupt-terminal-no-ack','user-input'}:emit({'method':'turn/completed','params':{'threadId':'native-root','turn':{'id':turn,'status':os.environ.get('SCID_TEST_TERMINAL_STATUS','completed')}}})
        continue
    elif method=='turn/interrupt':
        if mode=='interrupt-disconnect':sys.exit(0)
        if mode=='interrupt-terminal-no-ack':
            emit({'method':'turn/completed','params':{'threadId':'native-root','turn':{'id':p['turnId'],'status':'interrupted'}}})
            continue
        result={}
    else:raise RuntimeError(method)
    emit({'id':msg['id'],'result':result})
'''


def native(tmp_path, monkeypatch, project, socket_path, mode='complete'):
    import tomllib
    directory = project / '.codex'
    directory.mkdir(exist_ok=True)
    text = '[mcp_servers.scidiscovery]\ncommand = "scidiscovery-mcp-proxy"\nargs = ["--socket", ' + json.dumps(str(socket_path)) + ']\n'
    (directory / 'config.toml').write_text(text)
    config = tmp_path / 'native-config.json'
    config.write_text(json.dumps(tomllib.loads(text)))
    requests = tmp_path / 'native-requests.jsonl'
    peer = tmp_path / 'codex'
    peer.write_text('#!'+sys.executable+'\n'+PEER)
    peer.chmod(0o700)
    monkeypatch.setenv('SCID_TEST_CONFIG', str(config))
    monkeypatch.setenv('SCID_TEST_REQUESTS', str(requests))
    monkeypatch.setenv('SCID_TEST_MODE', mode)
    monkeypatch.setenv('PATH', str(tmp_path)+os.pathsep+os.environ['PATH'])
    return peer, requests


def methods(requests):
    return [json.loads(v)['method'] for v in requests.read_text().splitlines() if 'method' in json.loads(v)] if requests.exists() else []


def wait_for(predicate, timeout=8):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if predicate():return
        time.sleep(.03)
    raise AssertionError('bounded process condition did not occur')


def test_real_native_process_reconnect_does_not_replay_turn(progression, tmp_path, monkeypatch):
    p=progression
    _,requests=native(tmp_path,monkeypatch,p.runtime.project_root,tmp_path/'control.sock')
    p.coordinator.host_factory=CodexProgressionFactory(project_root=p.runtime.project_root,
        state_root=p.runtime.state_root,socket_path=tmp_path/'control.sock',approval_base_url='http://127.0.0.1:8765')
    p.coordinator.tick()
    wait_for(lambda: p.coordinator.host.poll(.01) is not None)
    p.coordinator.host.close()
    p.coordinator.host=None
    p.coordinator.tick()
    assert methods(requests).count('turn/start')==1
    assert 'thread/resume' in methods(requests) and 'thread/read' in methods(requests)
    assert checkpoint(p)['rounds']==1
    assert checkpoint(p)['usage_records']['native-root']['counted_tokens']['input_tokens']==100


@pytest.mark.parametrize('reason', ['goal_completed', 'budget_exhausted', 'root_turn_failed'])
def test_acceptance_cleanup_observes_followup_tick_release_and_owned_process_exit(progression, tmp_path, monkeypatch, reason):
    from scripts.accept_progression_recovery import RecoveryJourney
    p = progression
    _, requests = native(tmp_path, monkeypatch, p.runtime.project_root, tmp_path/'control.sock')
    if reason == 'root_turn_failed':
        monkeypatch.setenv('SCID_TEST_TERMINAL_STATUS', 'failed')
    p.coordinator.host_factory = CodexProgressionFactory(project_root=p.runtime.project_root,
        state_root=p.runtime.state_root, socket_path=tmp_path/'control.sock', approval_base_url='http://127.0.0.1:8765')
    p.coordinator.tick()
    host = p.coordinator.host
    if reason != 'root_turn_failed':
        root = p.root.__class__(p.facade(host.scheduler_session))
        root.call_tool('progression_report', dict(summary='Sealed handoff.', completed=True))
        assert row(p)['state'] == 'active' and row(p)['host_json'] is not None
    wait_for(lambda: host.poll(.01) is not None)
    if reason == 'budget_exhausted':
        p.now[0] += json.loads(row(p)['config_json'])['effective']['progression']['max_elapsed_seconds']+1
    p.coordinator.tick()
    stopped = row(p)
    assert stopped['state'] == 'paused' and stopped['reason'] == reason and stopped['host_json'] is not None
    assert host.connection.child.poll() is None
    releases = []
    release = p.runtime.scheduler_bindings.release_host
    def witnessed_release(**kwargs):
        releases.append(kwargs)
        return release(**kwargs)
    monkeypatch.setattr(p.runtime.scheduler_bindings, 'release_host', witnessed_release)
    journey = RecoveryJourney.__new__(RecoveryJourney)
    journey.logdir = tmp_path/'logs'
    journey.phase_deadline = old_deadline = time.monotonic()-1
    journey.row = lambda: row(p)
    journey.pump = p.coordinator.tick
    released = journey.wait_row(lambda value: value['state'] in {'paused','stopped'} and not value['host_json'],
        'closeout-released', timeout=2, cleanup=True)
    assert released['reason'] == reason and journey.phase_deadline == old_deadline
    assert releases == [dict(instance_id=p.instance, platform_session='native-root', thread_id='native-root')]
    assert p.coordinator.host is None and host.connection.closed and host.connection.child.poll() is not None
    assert methods(requests).count('turn/start') == 1


def test_native_process_interrupted_recovery_starts_one_new_decision(progression,tmp_path,monkeypatch):
    p=progression
    _,requests=native(tmp_path,monkeypatch,p.runtime.project_root,tmp_path/'control.sock','running')
    p.coordinator.host_factory=CodexProgressionFactory(project_root=p.runtime.project_root,
        state_root=p.runtime.state_root,socket_path=tmp_path/'control.sock',approval_base_url='http://127.0.0.1:8765')
    p.coordinator.tick()
    wait_for(lambda: (p.coordinator.host.poll(.01), bool(checkpoint(p).get('usage_records')))[1])
    before=checkpoint(p)
    original=json.loads(row(p)['host_json'])
    p.coordinator.host.close();p.coordinator.host=None
    monkeypatch.setenv('SCID_TEST_ROOT_STATUS','interrupted')
    p.now[0]+=6
    p.coordinator.tick()
    assert methods(requests).count('turn/start')==2
    assert 'thread/read' in methods(requests) and 'thread/resume' in methods(requests)
    assert json.loads(row(p)['host_json'])==original
    after=checkpoint(p)
    assert after['phase']=='running' and after['turn_id']=='recovery-turn'
    assert after['attempts']==before['attempts']+1
    assert after['started_at']==before['started_at']
    assert after['usage_records']==before['usage_records']
    p.coordinator.tick()
    assert methods(requests).count('turn/start')==2


def params(requests, method):
    return [json.loads(v)['params'] for v in requests.read_text().splitlines() if json.loads(v).get('method')==method]


def test_background_root_pins_declared_permissions_over_personal_config(progression,tmp_path,monkeypatch):
    p=progression
    _,requests=native(tmp_path,monkeypatch,p.runtime.project_root,tmp_path/'control.sock')
    p.coordinator.host_factory=CodexProgressionFactory(project_root=p.runtime.project_root,
        state_root=p.runtime.state_root,socket_path=tmp_path/'control.sock',approval_base_url='http://127.0.0.1:8765')
    p.coordinator.tick()
    wait_for(lambda: p.coordinator.host.poll(.01) is not None)
    p.coordinator.host.close();p.coordinator.host=None
    p.now[0]+=6
    p.coordinator.tick()
    declared={'approvalPolicy':'never','sandbox':'workspace-write'}
    for method in ('thread/start','thread/resume'):
        assert [{k:v[k] for k in declared} for v in params(requests,method)]==[declared]
        assert params(requests,method)[0]['config']['sandbox_workspace_write']=={'network_access':True,'writable_roots':[]}
    assert params(requests,'thread/start')[0]['config']['model_reasoning_effort']
    turns=params(requests,'turn/start')
    # Inherited native Workers keep workspace write and network access.
    assert turns and all(v['approvalPolicy']=='never' and v['sandboxPolicy']=={'type':'workspaceWrite','networkAccess':True} for v in turns)


@pytest.mark.parametrize('variant',['SCID_TEST_IGNORE_PERMISSIONS','SCID_TEST_NETWORK_MISMATCH'])
def test_background_root_rejects_effective_permissions_that_differ_from_declaration(progression,tmp_path,monkeypatch,variant):
    p=progression
    _,requests=native(tmp_path,monkeypatch,p.runtime.project_root,tmp_path/'control.sock')
    monkeypatch.setenv(variant,'1')
    p.coordinator.host_factory=CodexProgressionFactory(project_root=p.runtime.project_root,
        state_root=p.runtime.state_root,socket_path=tmp_path/'control.sock',approval_base_url='http://127.0.0.1:8765')
    with pytest.raises(HostError, match='root_permissions_mismatch'):p.coordinator.tick()
    assert row(p)['state']=='paused'
    assert 'turn/start' not in methods(requests) and 'mcpServer/tool/call' not in methods(requests)


def test_restored_running_turn_without_recorded_policy_stops_before_launch(progression,tmp_path,monkeypatch):
    p=progression
    _,requests=native(tmp_path,monkeypatch,p.runtime.project_root,tmp_path/'control.sock','running')
    p.coordinator.host_factory=CodexProgressionFactory(project_root=p.runtime.project_root,
        state_root=p.runtime.state_root,socket_path=tmp_path/'control.sock',approval_base_url='http://127.0.0.1:8765')
    p.coordinator.tick()
    wait_for(lambda: (p.coordinator.host.poll(.01), bool(checkpoint(p).get('turn_id')))[1])
    assert checkpoint(p)['root_permissions']=={'approval_policy':'never','sandbox':'workspace-write','network_access':True}
    p.coordinator.host.close();p.coordinator.host=None
    # A turn started before the policy was recorded cannot be shown to match.
    with p.runtime.scheduler_bindings._connect() as db:
        value=checkpoint(p);value.pop('root_permissions')
        db.execute('UPDATE scheduler_progression SET checkpoint_json=? WHERE instance_id=?',(json.dumps(value),p.instance))
    before=methods(requests)
    with pytest.raises(HostError,match='root_permissions_unproven'):p.coordinator.tick()
    assert methods(requests)==before and row(p)['state']=='paused'


@pytest.mark.parametrize('mode,expected', [('missing-tools','host_fault'),('lost','host_fault'),('accepted-lost','host_fault')])
def test_real_native_negative_paths_preserve_unknown_identity(progression,tmp_path,monkeypatch,mode,expected):
    p=progression
    _,requests=native(tmp_path,monkeypatch,p.runtime.project_root,tmp_path/'control.sock',mode)
    p.coordinator.host_factory=CodexProgressionFactory(project_root=p.runtime.project_root,
        state_root=p.runtime.state_root,socket_path=tmp_path/'control.sock',approval_base_url='http://127.0.0.1:8765')
    with pytest.raises(HostError):p.coordinator.tick()
    assert row(p)['reason']==expected and row(p)['state']=='paused'
    if mode=='missing-tools':
        assert 'turn/start' not in methods(requests)
    else:
        assert row(p)['host_json'] is not None
        assert methods(requests).count('turn/start')==1
        assert bool(checkpoint(p).get('turn_id'))==(mode=='accepted-lost')
    p.coordinator.tick()
    assert methods(requests).count('turn/start')==(0 if mode=='missing-tools' else 1)


def test_daemon_entry_wires_dormant_runtime_and_survives_frontend_disconnect(tmp_path, monkeypatch):
    # Source entry-point process test. Installed wheel execution is a separate lane.
    from scidiscovery.plugin_runtime.transport import forward_request
    project=tmp_path/'project';project.mkdir()
    state=tmp_path/'state';state.mkdir()
    socket_path=tmp_path/'control.sock'
    _,requests=native(tmp_path,monkeypatch,project,socket_path)
    monkeypatch.setenv('SCID_TEST_FORWARD','1')
    secret=tmp_path/'secret';secret.write_text('f'*64);secret.chmod(0o600)
    command=[sys.executable,'-m','scidiscovery.artifact_agent.interfaces.mcp_daemon',
        '--project-root',str(project),'--state-root',str(state),'--socket',str(socket_path),
        '--approval-secret-file',str(secret),'--local-workspace-root',str(project/'runs'),
        '--runtime-summary',str(tmp_path/'summary.json')]
    user='sch_'+'a'*32
    def call(name,arguments):
        request=dict(jsonrpc='2.0',id=1,method='tools/call',
            _scidiscovery_scheduler_proxy=user,params=dict(name='scid_call',arguments=dict(name=name,arguments=arguments),
            _meta={'x-codex-turn-metadata':dict(session_id='frontend',thread_id='frontend')}))
        response=forward_request(socket_path,json.dumps(request).encode(),timeout=3)
        assert 'error' not in response,response
        value=response['result']
        assert not value.get('isError'),value
        return value.get('structuredContent') or json.loads(value['content'][0]['text'])
    with (tmp_path/'daemon.log').open('wb') as log:
        environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2] / 'src'))
        daemon=subprocess.Popen(command,stdout=log,stderr=log,env=environment)
        try:
            wait_for(socket_path.exists)
            call('instance_current',{})
            bindings=SchedulerBindingService(state/'database/scheduler-bindings.sqlite3')
            instance=bindings.create_instance_and_bind_session(session_key=user,name='user-selected',title='Research',objective='User explicitly starts.')
            assert not requests.exists()  # No native process before user start.
            call('artifact_ingest_text',dict(name='goal',text='Inspect supplied evidence.',on_conflict='reject'))
            call('progression_command',dict(command='pause'))
            call('progression_command',dict(command='start',mode='background',objective_name='goal'))
            wait_for(lambda: methods(requests).count('turn/start')==1)
            wait_for(lambda: json.loads(bindings.progression_status(instance_id=instance.instance_id,internal=True)['checkpoint_json']).get('phase')=='idle')
            # Every frontend call used and closed its own Unix connection. The
            # daemon persists, and a semantic message wakes the existing Root.
            call('progression_message',dict(name='more.context',text='Carry forward the original limitations.'))
            wait_for(lambda: methods(requests).count('turn/start')==2)
            calls=methods(requests)
            assert calls.index('mcpServerStatus/list')<calls.index('turn/start')
            assert bindings.session_instance(session_key=user)==instance.instance_id
            assert bindings.session_instance(session_key='sch_'+'b'*32)==instance.instance_id
        except BaseException:
            log.flush()
            print((tmp_path/'daemon.log').read_text())
            print(methods(requests))
            if "bindings" in locals():
                print(bindings.progression_status(instance_id=instance.instance_id, internal=True))
            raise
        finally:
            daemon.terminate()
            daemon.wait(timeout=10)


def test_owned_resource_stop_preserves_unrelated_process(tmp_path):
    from scidiscovery.platforms.process_observation import OwnedProcessTree
    other=subprocess.Popen([sys.executable,'-c','import time;time.sleep(20)'])
    owned=subprocess.Popen([sys.executable,'-c','import time;time.sleep(20)'])
    try:
        observation=OwnedProcessTree(owned.pid)
        sample=observation.sample()
        assert sample['observed_processes']==1
        assert sample['coverage']=='sampled_owned_tree'
        observation.terminate()
        owned.wait(timeout=3)
        assert other.poll() is None
    finally:
        for process in (owned,other):
            if process.poll() is None:process.terminate()
            process.wait(timeout=3)


def test_protocol_resource_guard_operates_while_rpc_is_running(progression,tmp_path,monkeypatch):
    p=progression
    _,requests=native(tmp_path,monkeypatch,p.runtime.project_root,tmp_path/'control.sock')
    factory=CodexProgressionFactory(project_root=p.runtime.project_root,
        state_root=p.runtime.state_root,socket_path=tmp_path/'control.sock',approval_base_url='http://127.0.0.1:8765')
    settings=json.loads(row(p)['config_json'])
    settings['effective']['progression']['max_rss_bytes']=1_048_576
    value=dict(row(p),config_json=json.dumps(settings))
    with pytest.raises(HostError,match='resource_limit'):
        factory(value,lambda event:None)
    assert 'turn/start' not in methods(requests)


@pytest.mark.parametrize('stop', ['time', 'resource'])
def test_blocked_native_submit_observes_deadline_and_sampling_before_rpc_timeout(progression, tmp_path, monkeypatch, stop):
    p = progression
    _, requests = native(tmp_path, monkeypatch, p.runtime.project_root, tmp_path/'control.sock', 'blocked-turn')
    factory = CodexProgressionFactory(project_root=p.runtime.project_root, state_root=p.runtime.state_root,
        socket_path=tmp_path/'control.sock', approval_base_url='http://127.0.0.1:8765')
    host = factory(row(p), lambda event: None)
    started = time.monotonic()
    try:
        if stop == 'time':
            host.set_execution_deadline(.2)
        else:
            host.resource_limit = 100
            host.resource_sample_seconds = .05
            host._resource_sample = None
            monkeypatch.setattr(host.resources, 'sample', lambda: dict(control_daemon_rss_bytes=0,
                owned_tree_rss_bytes=101 if time.monotonic()-started >= .2 else 50))
        with pytest.raises(HostError, match='budget_deadline' if stop == 'time' else 'resource_limit'):
            host.start_turn('protocol fixture, no model')
        assert time.monotonic()-started < 2
        assert methods(requests).count('turn/start') == 1
        assert host.connection.failed
    finally:
        host.close()
    assert host.connection.child.poll() is not None


def test_worker_restore_requires_native_running_turn_not_only_identity(progression,tmp_path,monkeypatch):
    p=progression
    native(tmp_path,monkeypatch,p.runtime.project_root,tmp_path/'control.sock')
    p.coordinator.host_factory=CodexProgressionFactory(project_root=p.runtime.project_root,
        state_root=p.runtime.state_root,socket_path=tmp_path/'control.sock',approval_base_url='http://127.0.0.1:8765')
    p.coordinator.tick()
    with pytest.raises(HostError,match='worker_native_turn_not_running'):
        p.coordinator.host.restore_worker('worker','native-root',str(p.runtime.project_root))


@pytest.mark.parametrize('control', ['pause', 'resume'])
def test_terminal_interrupt_without_reply_releases_or_reconnects_without_replay(progression, tmp_path, monkeypatch, control):
    from scidiscovery.platforms.codex_app_server import HostLimits
    p = progression
    _, requests = native(tmp_path, monkeypatch, p.runtime.project_root, tmp_path/'control.sock', 'interrupt-terminal-no-ack')
    p.coordinator.host_factory = CodexProgressionFactory(project_root=p.runtime.project_root,
        state_root=p.runtime.state_root, socket_path=tmp_path/'control.sock', approval_base_url='http://127.0.0.1:8765')
    p.coordinator.tick()
    host = p.coordinator.host
    host.connection.limits = HostLimits(rpc_timeout_seconds=.2, termination_grace_seconds=1)
    p.root.call_tool('progression_command', dict(command='pause'))
    if control == 'resume':
        p.root.call_tool('progression_command', dict(command='resume'))
    p.coordinator.tick()
    assert host.connection.closed and p.coordinator.host is None
    assert checkpoint(p)['native_completion'] == 'interrupted'
    assert checkpoint(p)['last_transport_warning'] == 'interrupt_reply_timeout_after_terminal'
    assert not checkpoint(p).get('fault_code') and checkpoint(p)['attempts'] == 0
    assert methods(requests).count('turn/start') == 1
    assert checkpoint(p)['usage_records']['native-root']['counted_tokens']['input_tokens'] == 100
    if control == 'pause':
        assert row(p)['state'] == 'paused' and row(p)['host_json'] is None
    else:
        assert row(p)['state'] == 'pending' and row(p)['host_json'] is not None
        p.coordinator.tick()
        assert row(p)['state'] == 'active' and p.coordinator.host is not host
        assert 'thread/resume' in methods(requests)
        assert methods(requests).count('turn/start') == 1


@pytest.mark.parametrize('control', ['pause', 'resume'])
def test_native_disconnect_during_control_retains_marker_without_spinning(progression, tmp_path, monkeypatch, control):
    from scripts.accept_progression_recovery import RecoveryJourney
    p = progression
    _, requests = native(tmp_path, monkeypatch, p.runtime.project_root, tmp_path/'control.sock', 'interrupt-disconnect')
    p.coordinator.host_factory = CodexProgressionFactory(project_root=p.runtime.project_root,
        state_root=p.runtime.state_root, socket_path=tmp_path/'control.sock', approval_base_url='http://127.0.0.1:8765')
    p.coordinator.tick()
    host = p.coordinator.host
    p.root.call_tool('progression_command', dict(command='pause'))
    if control == 'resume':
        p.root.call_tool('progression_command', dict(command='resume'))
    with pytest.raises(HostError, match='app_server_closed'):
        p.coordinator.tick()
    assert p.coordinator.host is None and host.connection.closed
    assert row(p)['host_json'] is not None and row(p)['state'] == 'paused'
    count = len(methods(requests))
    p.coordinator.tick()
    assert len(methods(requests)) == count
    marker = row(p)['host_json']
    journey = RecoveryJourney.__new__(RecoveryJourney)
    journey.logdir = tmp_path/'logs'
    journey.phase_deadline = time.monotonic()-1
    journey.row = lambda: row(p)
    journey.pump = p.coordinator.tick
    with pytest.raises(TimeoutError, match='closeout-released'):
        journey.wait_row(lambda value: value['state'] in {'paused','stopped'} and not value['host_json'],
            'closeout-released', timeout=.1, cleanup=True)
    assert row(p)['host_json'] == marker and row(p)['reason'] == 'host_fault'
    assert len(methods(requests)) == count and host.connection.child.poll() is not None
    assert not (tmp_path/'closeout-released.json').exists()
    monkeypatch.setenv('SCID_TEST_MODE', 'complete')
    p.root.call_tool('progression_command', dict(command='resume'))
    p.coordinator.tick()
    assert row(p)['state'] == 'active'
    assert p.coordinator.host.identity.thread_id == 'native-root'
    assert checkpoint(p)['phase'] == 'idle' and checkpoint(p)['rounds'] == 1
    assert methods(requests).count('turn/start') == 1
    assert 'thread/resume' in methods(requests) and 'thread/read' in methods(requests)


@pytest.mark.parametrize('helper_state', ['completed', 'inProgress', 'interrupted', 'unknown', 'missing'])
def test_restart_running_owner_keeps_terminal_helper_metering_identity(progression, tmp_path, monkeypatch, helper_state):
    from scidiscovery.helper_tool import HelperRequest
    from tests.operations.test_local_worker_contracts import _invoke, _worker
    p = progression
    _, requests = native(tmp_path, monkeypatch, p.runtime.project_root, tmp_path/'control.sock')
    monkeypatch.setenv('SCID_TEST_HELPER_STATUS', helper_state)
    p.coordinator.host_factory = CodexProgressionFactory(project_root=p.runtime.project_root,
        state_root=p.runtime.state_root, socket_path=tmp_path/'control.sock', approval_base_url='http://127.0.0.1:8765')
    p.coordinator.tick()
    root = p.root.__class__(p.facade(p.coordinator.host.scheduler_session))
    _invoke(root, 'active.owner')
    run = p.runtime.runs.list(instance_id=p.instance)[0]
    connections = p.runtime.runs.worker_connections
    connections.attach(run_id=run.run_id, platform_session='native-root', thread_id='owner')
    worker = _worker(p.catalog, p.runtime)
    worker.call_tool('worker_open_assignment', {})
    connections.helper_request(run.run_id, HelperRequest(name='inspection', task='Inspect the same data.'))
    connections.participant(platform_session='native-root', thread_id='helper', parent_thread='owner', admit=True,
        model=run.execution_profile['profile']['model'],
        reasoning_effort=run.execution_profile['profile']['reasoning_effort'])
    # Release revokes tool access, but is intentionally not native terminal proof.
    connections.release_helpers(run.run_id)
    p.coordinator._event(dict(method='thread/tokenUsage/updated', params=dict(threadId='helper',
        tokenUsage=dict(total=dict(inputTokens=42, cachedInputTokens=12, outputTokens=5)))))
    p.coordinator.host.close()
    p.coordinator.host = None
    if helper_state in {'unknown', 'missing'}:
        with pytest.raises(HostError, match='worker_native_turn_state_unknown'):
            p.coordinator.tick()
        assert row(p)['state'] == 'paused' and row(p)['host_json'] is not None
    else:
        p.coordinator.tick()
        assert row(p)['state'] == 'active'
    assert p.runtime.runs.status(run.run_id).state == 'running'
    assert checkpoint(p)['usage_records']['helper']['counted_tokens']['input_tokens'] == 42
    assert checkpoint(p)['usage_records']['helper']['role'] == 'helper'
    assert methods(requests).count('turn/start') == 1


@pytest.mark.parametrize('override,expected', [({}, ('gpt-5.6-sol', 'high')),
    ({'root_model':'root-explicit', 'root_reasoning_effort':'xhigh'}, ('root-explicit', 'xhigh'))])
def test_root_model_is_independent_of_worker_defaults(progression, tmp_path, monkeypatch, override, expected):
    p = progression
    _, requests = native(tmp_path, monkeypatch, p.runtime.project_root, tmp_path/'control.sock')
    frozen = dict(row(p))
    config = json.loads(frozen['config_json'])
    config['effective']['defaults'].update(model='worker-explicit', reasoning_effort='low')
    config['effective']['progression'].update(override)
    frozen['config_json'] = json.dumps(config)
    factory = CodexProgressionFactory(project_root=p.runtime.project_root,
        state_root=p.runtime.state_root, socket_path=tmp_path/'control.sock', approval_base_url='http://127.0.0.1:8765')
    host = factory(frozen, lambda event: None)
    try:
        calls = [json.loads(line) for line in requests.read_text().splitlines()]
        start = next(v['params'] for v in calls if v['method']=='thread/start')
        assert (start['model'], start['config']['model_reasoning_effort']) == expected
        assert 'turn/start' not in [v['method'] for v in calls]
        assert config['effective']['defaults']['model'] == 'worker-explicit'
    finally:
        host.close()


@pytest.mark.parametrize('method,reply', [
    ('item/commandExecution/requestApproval', {'decision':'decline'}),
    ('item/fileChange/requestApproval', {'decision':'decline'}),
    ('item/permissions/requestApproval', {'permissions':{}, 'scope':'turn'})])
def test_server_approval_denial_uses_exact_protocol_and_is_durable(progression, tmp_path, monkeypatch, method, reply):
    p = progression
    _, requests = native(tmp_path, monkeypatch, p.runtime.project_root, tmp_path/'control.sock', 'denial')
    monkeypatch.setenv('SCID_TEST_SERVER_METHOD', method)
    p.coordinator.host_factory = CodexProgressionFactory(project_root=p.runtime.project_root,
        state_root=p.runtime.state_root, socket_path=tmp_path/'control.sock', approval_base_url='http://127.0.0.1:8765')
    p.coordinator.tick()
    wait_for(lambda: p.coordinator.host.poll(.01) is not None)
    records = [json.loads(line) for line in requests.read_text().splitlines()]
    assert next(value for value in records if value.get('id') == 73) == dict(id=73, result=reply)
    assert checkpoint(p)['platform_requests'][0]['state'] == 'denied'
    assert methods(requests).count('turn/start') == 1
    status = p.root.call_tool('progression_status', {})
    assert status['platform_requests'][0]['state'] == 'denied'
    assert '/private' not in json.dumps(status) and 'native-root' not in json.dumps(status)


@pytest.mark.parametrize('mode,method,state', [
    ('user-input', 'item/tool/requestUserInput', 'pending_user_input'),
    ('unknown-request', 'unknown/private/request', 'unsupported')])
def test_server_information_or_unknown_request_survives_without_turn_replay(progression, tmp_path, monkeypatch, mode, method, state):
    p = progression
    _, requests = native(tmp_path, monkeypatch, p.runtime.project_root, tmp_path/'control.sock', mode)
    monkeypatch.setenv('SCID_TEST_SERVER_METHOD', method)
    p.coordinator.host_factory = CodexProgressionFactory(project_root=p.runtime.project_root,
        state_root=p.runtime.state_root, socket_path=tmp_path/'control.sock', approval_base_url='http://127.0.0.1:8765')
    if mode == 'unknown-request':
        with pytest.raises(HostError, match='unsupported_server_request'):
            p.coordinator.tick()
    else:
        p.coordinator.tick()
    assert row(p)['state'] == 'paused'
    assert checkpoint(p)['platform_requests'][0]['state'] == state
    reopened = SchedulerBindingService(p.runtime.scheduler_bindings.database_path)
    status = reopened.progression_status(instance_id=p.instance)
    assert status['platform_requests'][0]['state'] == state
    if mode == 'user-input':
        assert status['platform_requests'][0]['questions'][0]['question'] == 'Which measurement applies?'
    for _ in range(3):
        p.coordinator.tick()
    records = [json.loads(line) for line in requests.read_text().splitlines()]
    assert not any(value.get('id') == 73 for value in records)
    assert methods(requests).count('turn/start') == 1


@pytest.mark.parametrize('kind', ['options', 'truncated', 'form', 'url'])
def test_pending_native_information_preserves_choices_forms_and_marks_omissions(progression, tmp_path, monkeypatch, kind):
    p = progression
    _, requests = native(tmp_path, monkeypatch, p.runtime.project_root, tmp_path/'control.sock', 'user-input')
    options = [dict(label='Boundary A', description='Use the earlier exact measurement.'),
               dict(label='Boundary B', description='Use the later exact measurement.')]
    schema = dict(type='object', properties=dict(measurement=dict(type='string', enum=['A', 'B'])), required=['measurement'])
    payload = dict(isBlocking=True, questions=[dict(id='measurement', header='Boundary',
        question='Which measurement applies?', options=options)])
    method = 'item/tool/requestUserInput'
    if kind == 'truncated':
        payload['questions'][0].update(id='i'*200, header='界'*200, options=options*10)
    if kind in {'form', 'url'}:
        method = 'mcpServer/elicitation/request'
        payload = dict(serverName='fixture', mode=kind, message='Choose the measurement.')
        if kind == 'form':
            payload['requestedSchema'] = schema
        else:
            payload.update(elicitationId='interaction', url='https://person:SECRET@example.org/SECRET?token=SECRET#SECRET')
    monkeypatch.setenv('SCID_TEST_SERVER_METHOD', method)
    monkeypatch.setenv('SCID_TEST_SERVER_PAYLOAD', json.dumps(payload))
    p.coordinator.host_factory = CodexProgressionFactory(project_root=p.runtime.project_root,
        state_root=p.runtime.state_root, socket_path=tmp_path/'control.sock', approval_base_url='http://127.0.0.1:8765')
    p.coordinator.tick()
    assert row(p)['state'] == 'paused'
    reopened = SchedulerBindingService(p.runtime.scheduler_bindings.database_path)
    entry = reopened.progression_status(instance_id=p.instance)['platform_requests'][0]
    assert entry['state'] == 'pending_user_input'
    assert len(json.dumps(entry, ensure_ascii=False).encode()) < 8192
    if kind == 'options':
        assert entry['questions'][0]['id'] == 'measurement'
        assert entry['questions'][0]['options'] == options and not entry['omitted']
    elif kind == 'truncated':
        assert entry['omitted'] and len(entry['questions'][0]['header']) == 128
        assert len(entry['questions'][0]['options']) <= 8
    elif kind == 'form':
        assert entry['elicitation']['requestedSchema'] == schema and not entry['omitted']
    else:
        assert entry['omitted'] and 'SECRET' not in json.dumps(entry)
        assert entry['elicitation']['url_origin'] == 'https://example.org'
        assert entry['elicitation']['interaction'] == 'unsupported_url_interaction'
        assert 'original requesting app' in entry['elicitation']['instruction']
    assert methods(requests).count('turn/start') == 1
