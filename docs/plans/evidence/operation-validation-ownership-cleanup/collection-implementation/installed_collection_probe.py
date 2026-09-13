"""Installed proxy/daemon -> reopened TCAD command adapter, no checkpoint seed."""
import hashlib
import json
import os
from pathlib import Path
import selectors
import sqlite3
import subprocess
import sys
import tempfile
import time

import scidiscovery
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration

assert Path(scidiscovery.__file__).resolve().is_relative_to(Path(sys.prefix))
root = Path(tempfile.mkdtemp(prefix='installed-collection-path-'))
project = root/'project'; project.mkdir()
state = root/'state'
secret = root/'approval-secret'; secret.write_bytes(os.urandom(32)); secret.chmod(0o600)
runtime = open_runtime(project_root=project, state_root=state, approval_receipt_secret=secret.read_bytes())
instance = runtime.scheduler_bindings.create_instance(name='fixture',title='Installed recovery',objective='Recover a terminal engineering fixture')
runtime.scheduler_bindings.bind_session(session_key='sch_'+'a'*32,instance_id=instance.instance_id)
payload = runtime.artifacts.register(b'{}',ArtifactRegistration(kind='fixture',schema_id='fixture.v1',
    payload_schema_version=1,media_type='application/json',creator=runtime.actor),idempotency_key='fixture')
execution = runtime.executions.create(executor='tcad_artifact:tcad',preparation_profile='fixture.v1',payload_ref=payload.ref)
# Seed a historical terminal execution in this isolated database. Exact approval
# and start behavior are exercised separately by the installed UI negative control.
with sqlite3.connect(runtime.executions.database_path) as connection:
    connection.execute("UPDATE executions SET state='succeeded',external_run_id='terminal_fixture' WHERE execution_id=?",(execution,))
runtime.scheduler_bindings.bind(instance=instance.instance_id,namespace='execution',name='original',object_id=execution)
outputs = state/'executor-results'; outputs.mkdir()
data=outputs/'raw.dat'; data.write_bytes(b'original solver bytes\n')
descriptor=dict(name='profile',local_path=str(data),media_type='text/plain',size_bytes=data.stat().st_size,
    sha256=hashlib.sha256(data.read_bytes()).hexdigest())
transport=root/'transport.py'
transport.write_text('import sys,json,time\nfrom pathlib import Path\nr=json.load(sys.stdin)\n'
    f'with Path({str(root/"calls")!r}).open("a") as stream: stream.write(r["operation"]+"\\n")\n'
    'assert r["operation"] in ("collect","status"), "unexpected solver start"\n'
    f'payload={{"outputs":[{descriptor!r}]}} if r["operation"]=="collect" else {{"state":"succeeded","progress":{{"elapsed_seconds":12}}}}\n'
    'time.sleep(.3 if r["operation"]=="collect" else 0)\n'
    'print(json.dumps({"schema_version":1,"operation":r["operation"],"ok":True,"payload":payload}))\n')
command=root/'command.json'; command.write_text(json.dumps(dict(executable=sys.executable,arguments=[str(transport)],operation_timeout_seconds=30))); command.chmod(0o600)
config=root/'runtime.json'; config.write_text(json.dumps(dict(transport='command',command_config_path=str(command)))); config.chmod(0o600)
socket=root/'control.sock'
daemon_log=(root/'daemon.log').open('wb')
daemon=subprocess.Popen([sys.executable,'-m','scidiscovery.artifact_agent.interfaces.mcp_daemon',
    '--project-root',str(project),'--state-root',str(state),'--socket',str(socket),
    '--approval-secret-file',str(secret),'--local-workspace-root',str(root/'workers'),
    '--plugin-config','tcad_artifact='+str(config),'--runtime-summary',str(root/'runtime-summary.json')],stdout=daemon_log,stderr=daemon_log)
proxy=None
try:
    until=time.monotonic()+8
    while not socket.exists():
        assert daemon.poll() is None and time.monotonic()<until,(root/'daemon.log').read_text()
        time.sleep(.02)
    # Stabilize only the transport session identifier; execute the shipped proxy main.
    proxy=subprocess.Popen([sys.executable,'-c','import uuid; uuid.uuid4=lambda:uuid.UUID("a"*32); from scidiscovery.artifact_agent.interfaces.mcp_proxy import main; raise SystemExit(main())',
        '--socket',str(socket)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    def call(name,args):
        proxy.stdin.write(json.dumps(dict(jsonrpc='2.0',id=1,method='tools/call',params=dict(name=name,arguments=args))).encode()+b'\n'); proxy.stdin.flush()
        with selectors.DefaultSelector() as selector:
            selector.register(proxy.stdout,selectors.EVENT_READ)
            assert selector.select(8), 'installed proxy stalled'
        response=json.loads(proxy.stdout.readline())
        assert 'error' not in response,response
        return json.loads(response['result']['content'][0]['text'])
    assert call('execution_status',{'name':'original'})['state']=='succeeded'
    assert not (runtime.executions.exchange_root/execution/'collection/outputs.json').exists()
    accepted=call('execution_collect',{'name':'original','total_seconds':10})
    assert accepted['collection']['accepted']
    assert call('execution_sync',{'name':'original'})['state'] in ('succeeded','collected')
    until=time.monotonic()+12
    while True:
        status=call('execution_status',{'name':'original'})
        if status['state']=='collected': break
        assert status.get('collection',{}).get('state') not in ('failed','timed_out','interrupted'),status
        assert time.monotonic()<until,status
        time.sleep(.03)
    result=call('execution_outputs',{'name':'original'})
    assert result['outputs'][0]['output_label']=='profile'
    assert (root/'calls').read_text().splitlines().count('collect')==1
    assert call('execution_collect',{'name':'original'})['collection']['state']=='completed'
    assert (root/'calls').read_text().splitlines().count('collect')==1
    print('installed stdio/proxy/daemon, TCAD adapter reconstruction, actual collection, idempotent outputs: pass')
finally:
    if proxy is not None:
        proxy.stdin.close(); proxy.wait(timeout=3); proxy.stdout.close(); proxy.stderr.close()
    daemon.terminate()
    try: daemon.wait(timeout=3)
    except subprocess.TimeoutExpired:
        daemon.kill(); daemon.wait(); raise
    daemon_log.close()
