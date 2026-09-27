"""Reuse the already built wheel environment: proxy -> daemon -> real Root MCP."""
import json, os, select, subprocess, sys, tempfile, time
from pathlib import Path

python = sys.argv[1]
code = r'''
import os, sys
from pathlib import Path
from scidiscovery.interfaces.daemon import UnixSocketDaemon
from scidiscovery.artifact_agent.interfaces.mcp_daemon import RootBrokerRouter
from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_root import RootToolFacade, RootMCPRouter
from scidiscovery.artifact_agent.runtime import open_runtime
import scidiscovery
assert Path(scidiscovery.__file__).is_relative_to(Path(sys.prefix))
project = Path(sys.argv[2])
runtime = open_runtime(project_root=project, state_root=project/'state', approval_receipt_secret=os.urandom(32))
instance = runtime.scheduler_bindings.create_instance(name='isolated', title='Transport fixture', objective='Long objective '+ 'x'*4000)
def builder(session):
    return MCPRouter(RootMCPRouter(RootToolFacade(runtime.artifacts, runtime.intake,
        runs=runtime.runs, approvals=runtime.approvals, executions=runtime.executions,
        bindings=runtime.scheduler_bindings, instance=instance.instance_id)), name='installed-root')
UnixSocketDaemon(Path(sys.argv[1]), RootBrokerRouter(builder, client_bindings=runtime.scheduler_bindings)).serve_forever()
'''
with tempfile.TemporaryDirectory(prefix='scid-installed-transport-') as directory:
    root = Path(directory); socket = root/'root.sock'
    env = dict(os.environ); env.pop('PYTHONPATH',None); env['PYTHONNOUSERSITE']='1'
    daemon = subprocess.Popen([python,'-c',code,str(socket),directory],cwd=directory,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    proxy = None
    try:
        deadline = time.monotonic()+10
        while not socket.exists():
            if daemon.poll() is not None:raise RuntimeError(daemon.stderr.read().decode())
            if time.monotonic()>deadline:raise TimeoutError('isolated daemon startup')
            time.sleep(.02)
        proxy = subprocess.Popen([python,'-m','scidiscovery.artifact_agent.interfaces.mcp_proxy','--socket',str(socket)],
            cwd=directory,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        def call(name, args):
            request=dict(jsonrpc='2.0',id=1,method='tools/call',params=dict(name=name,arguments=args))
            proxy.stdin.write(json.dumps(request).encode()+b'\n');proxy.stdin.flush()
            if not select.select([proxy.stdout],[],[],10)[0]:raise TimeoutError('isolated proxy reply')
            response=json.loads(proxy.stdout.readline())
            if 'error' in response:return response
            result=response['result']
            assert json.loads(result['content'][0]['text']) == result['structuredContent']
            return result['structuredContent']
        short=call('instance_current',{})
        assert short['name']=='isolated' and 'objective' not in short,short
        detail=call('instance_current',{'view':'detail'})
        assert len(detail['objective'])>4000,detail
        brief=call('operation_catalog',{'operation_id':'science.hypothesis.propose.v1'})
        assert 'inputs' not in brief['operations'][0]
        full=call('operation_catalog',{'operation_id':'science.hypothesis.propose.v1','view':'detail'})
        assert 'result_analysis' in json.dumps(full['operations'][0]['inputs'])
        error=call('run_status',{'name':'fixture','view':'invalid'})
        assert error['error']['data']['diagnostics'][0]['path']=='$.view',error
        print('PASS: installed proxy/daemon, summary/detail, text/structured equivalence, exact typed error')
    finally:
        if proxy is not None:
            proxy.terminate()
            try:proxy.wait(timeout=5)
            except subprocess.TimeoutExpired:proxy.kill();proxy.wait(timeout=5)
        daemon.terminate()
        try:daemon.wait(timeout=5)
        except subprocess.TimeoutExpired:daemon.kill();daemon.wait(timeout=5)
