"""Wheel export and installed interpreter; no model or production services."""


def test_installed_root_host_can_wait_resume_and_close(installed_probe):
    installed_probe('core', r'''
import os,sys,subprocess,tempfile,json
from pathlib import Path
from scidiscovery.platforms import codex_root_host, codex_app_server
from scidiscovery.platforms.codex_app_server import AppServer, HostLimits
from scidiscovery.platforms.codex_root_host import CodexRootHost, RootIdentity
for module in (codex_root_host,codex_app_server):
    assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
with tempfile.TemporaryDirectory() as folder:
    root=Path(folder)
    script=root/'peer.py'
    script.write_text("""import json,sys
for line in sys.stdin:
    q=json.loads(line)
    if 'id' not in q:continue
    m=q['method']
    if m=='initialize':r={}
    elif m=='config/read':r={'config':{}}
    elif m=='thread/resume':r={'thread':{'id':'installed','sessionId':'installed'}}
    else:raise RuntimeError('unexpected model or service call')
    print(json.dumps({'id':q['id'],'result':r}),flush=True)
""")
    connection=AppServer.launch([sys.executable,str(script)],cwd=root,environment=dict(os.environ),
        stderr=subprocess.DEVNULL,limits=HostLimits(rpc_timeout_seconds=3),on_event=lambda e:None)
    host=CodexRootHost(connection)
    try:
        host.initialize(cwd=str(root),expected_config={})
        host.open_root(cwd=str(root),prior=RootIdentity('installed','installed'))
        host.poll(.01)
        assert connection.child.poll() is None
    finally:host.close()
    assert connection.child.poll() is not None
''')


def test_installed_progression_daemon_starts_without_native_model(installed_probe):
    installed_probe('core', r'''
import os,sys,subprocess,tempfile,json,time
from pathlib import Path
from scidiscovery.artifact_agent.service import progression
from scidiscovery.platforms import codex_progression,process_observation
from scidiscovery.plugin_runtime.transport import forward_request
for module in (progression,codex_progression,process_observation):
    assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
with tempfile.TemporaryDirectory() as folder:
    root=Path(folder);project=root/'project';project.mkdir();secret=root/'secret'
    secret.write_text('a'*64);secret.chmod(0o600);sock=root/'daemon.sock'
    command=[sys.executable,'-I','-m','scidiscovery.artifact_agent.interfaces.mcp_daemon',
        '--project-root',str(project),'--state-root',str(root/'state'),'--socket',str(sock),
        '--approval-secret-file',str(secret),'--local-workspace-root',str(root/'work'),
        '--runtime-summary',str(root/'runtime.json')]
    with (root/'log').open('wb') as log:
        process=subprocess.Popen(command,stdout=log,stderr=log,env=dict(os.environ))
        try:
            deadline=time.monotonic()+10
            while not sock.exists() and process.poll() is None and time.monotonic()<deadline:time.sleep(.05)
            assert sock.exists(),(root/'log').read_text()
            request={'jsonrpc':'2.0','id':1,'method':'initialize','params':{},
                '_scidiscovery_scheduler_proxy':'sch_'+'a'*32}
            response=forward_request(sock,json.dumps(request).encode(),timeout=3)
            assert 'result' in response,response
            assert not (root/'state/progression-logs').exists()
        finally:
            process.terminate();process.wait(timeout=10)
''')
