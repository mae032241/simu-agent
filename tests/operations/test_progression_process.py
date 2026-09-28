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
        result={'thread':{'id':p.get('threadId','native-root'),'sessionId':'native-root'}}
    elif method=='thread/read':
        result={'thread':{'id':p['threadId'],'turns':[{'id':'exact-turn','status':'completed'}]}}
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
        if mode=='lost':sys.exit(0)
        emit({'method':'turn/started','params':{'threadId':'native-root','turn':{'id':'exact-turn'}}})
        if mode=='accepted-lost':sys.exit(0)
        result={'turn':{'id':'exact-turn'}}
        emit({'id':msg['id'],'result':result})
        emit({'method':'thread/tokenUsage/updated','params':{'threadId':'native-root','tokenUsage':{'total':{'inputTokens':100,'cachedInputTokens':50,'outputTokens':20}}}})
        if mode!='running':emit({'method':'turn/completed','params':{'threadId':'native-root','turn':{'id':'exact-turn','status':'completed'}}})
        continue
    elif method=='turn/interrupt':result={}
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
    return [json.loads(v)['method'] for v in requests.read_text().splitlines()] if requests.exists() else []


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
