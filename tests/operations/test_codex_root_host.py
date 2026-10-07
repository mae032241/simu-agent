"""Real stdio subprocesses, no Codex model, credentials, or scientific services."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scidiscovery.platforms.codex_app_server import AppServer, HostError, HostLimits
from scidiscovery.platforms.codex_root_host import CodexRootHost, RootIdentity, RootPermissions
from scidiscovery.platforms.codex_usage import observe_usage

pytestmark = pytest.mark.process_e2e


@pytest.fixture
def peer(tmp_path):
    script = tmp_path / "peer.py"
    script.write_text(r'''
import json,sys,time
from pathlib import Path
mode, requests = sys.argv[1:]
def emit(x): print(json.dumps(x),flush=True)
turn=0
for line in sys.stdin:
    msg=json.loads(line)
    with Path(requests).open('a') as f:f.write(json.dumps(msg)+'\n')
    if 'id' not in msg:continue
    m=msg['method'];p=msg['params']
    if m=='initialize':result={}
    elif m=='config/read':result={'config':{'agents':{'enabled':True}}}
    elif m in ('thread/start','thread/resume'):
        result={'thread':{'id':'wrong' if mode=='identity' else 'root','sessionId':'root'}}
        if 'sandbox' in p:
            net=p.get('config',{}).get('sandbox_workspace_write',{}).get('network_access',False)
            result.update(approvalPolicy=p['approvalPolicy'],sandbox={'type':'readOnly' if p['sandbox']=='read-only' else 'workspaceWrite',
                'networkAccess':(not net) if mode=='network-mismatch' else net,'writableRoots':['/unexpected'] if mode=='extra-root' else []})
    elif m=='turn/start':
        turn+=1;result={'turn':{'id':'t'+str(turn)}}
        if mode=='timeout':time.sleep(20)
        if mode=='malformed':result=[]
        if mode=='eof':sys.exit(0)
        if mode=='invalid':print('invalid',flush=True);continue
        if mode=='oversized':print('x'*8193,flush=True);continue
        if mode=='server-request':emit({'id':42,'method':'item/commandExecution/requestApproval','params':{}});continue
        if mode=='error':emit({'id':msg['id'],'error':{'code':-32603,'message':'failed to load workspace requirements: secret'}});continue
        if mode=='event-before-reply':emit({'method':'turn/completed','params':{'threadId':'root','turn':{'id':'t'+str(turn),'status':'completed'}}})
    elif m=='turn/interrupt':
        if mode in ('terminal-no-ack','foreign-terminal-no-ack','no-terminal-no-ack'):
            if mode != 'no-terminal-no-ack':
                emit({'method':'turn/completed','params':{'threadId':'other' if mode=='foreign-terminal-no-ack' else 'root','turn':{'id':p['turnId'],'status':'interrupted'}}})
            continue
        result={}
    else:result={}
    emit({'id':msg['id'],'result':result})
    if m=='turn/start' and mode not in ('interrupt','waiting','terminal-no-ack','foreign-terminal-no-ack','no-terminal-no-ack'):
        emit({'method':'thread/tokenUsage/updated','params':{'threadId':'root','turnId':'t'+str(turn),
              'tokenUsage':{'total':{'inputTokens':turn*10,'cachedInputTokens':turn*2,'outputTokens':turn}}}})
        emit({'method':'turn/completed','params':{'threadId':'worker','turn':{'id':'worker-turn','status':'completed'}}})
        emit({'method':'turn/completed','params':{'threadId':'root','turn':{'id':'t'+str(turn),'status':'failed' if mode=='failed' else 'completed'}}})
    if m=='turn/interrupt':
        time.sleep(.05)
        emit({'method':'turn/completed','params':{'threadId':'root','turn':{'id':p['turnId'],'status':'interrupted'}}})
''')
    hosts = []
    def start(mode="normal", sink=None, limits=None):
        events = []
        def observe(event):
            events.append(event)
            if sink:sink(event)
        connection = AppServer.launch([sys.executable, str(script), mode, str(tmp_path / "requests")],
            cwd=tmp_path, environment=dict(os.environ), stderr=subprocess.DEVNULL,
            limits=limits or HostLimits(rpc_timeout_seconds=2, termination_grace_seconds=1, frame_bytes=8192),
            on_event=observe)
        host = CodexRootHost(connection)
        hosts.append(host)
        host.initialize(cwd=str(tmp_path), expected_config={'agents':{'enabled':True}})
        return host, events
    yield start
    for host in hosts:host.close()


def test_two_turns_wait_without_model_and_reduce_usage(peer, tmp_path):
    records = {}
    def persist(event):
        if event['method']=='thread/tokenUsage/updated':
            record=observe_usage(event['params'], previous=records.get('root'), role='root', owner='goal')
            # A production consumer supplies its own transaction, not this fixture file.
            (tmp_path/'usage.json').write_text(json.dumps(record))
            records['root']=record
    host,events=peer(sink=persist)
    assert host.open_root(cwd=str(tmp_path))==RootIdentity('root','root')
    for i in (1,2):
        assert host.start_turn('bounded task')=='t'+str(i)
        assert host.wait_turn(2)=={'id':'t'+str(i),'status':'completed'}
        assert host.connection.child.poll() is None
        for _ in range(3):host.poll(.01)
        calls=[json.loads(x) for x in (tmp_path/'requests').read_text().splitlines()]
        assert sum(c['method']=='turn/start' for c in calls)==i
    assert records['root']['counted_tokens']['input_tokens']==20
    assert json.loads((tmp_path/'usage.json').read_text())==records['root']
    host.close();host.close()
    assert host.connection.child.poll() is not None


def test_resume_has_exact_identity_and_no_automatic_turn(peer,tmp_path):
    host,_=peer()
    assert host.open_root(cwd=str(tmp_path),prior=RootIdentity('root','root'))==RootIdentity('root','root')
    calls=[json.loads(x)['method'] for x in (tmp_path/'requests').read_text().splitlines()]
    assert 'thread/start' not in calls and 'turn/start' not in calls
    bad,_=peer('identity')
    with pytest.raises(HostError,match='identity'):bad.open_root(cwd=str(tmp_path),prior=RootIdentity('root','root'))
    assert bad.identity is None


def test_interrupt_acknowledgement_is_not_completion(peer,tmp_path):
    host,_=peer('interrupt');host.open_root(cwd=str(tmp_path));host.start_turn('work')
    with pytest.raises(HostError,match='already_active'):host.start_turn('duplicate')
    host.interrupt()
    assert host.wait_turn(2)['status']=='interrupted'
    calls=[json.loads(x) for x in (tmp_path/'requests').read_text().splitlines()]
    assert next(c['params'] for c in calls if c['method']=='turn/interrupt')=={'threadId':'root','turnId':'t1'}


@pytest.mark.parametrize('mode', ['terminal-no-ack','foreign-terminal-no-ack','no-terminal-no-ack'])
def test_terminal_proof_survives_missing_interrupt_reply_but_transport_cannot_restart(peer, tmp_path, mode):
    host, events = peer(mode, limits=HostLimits(rpc_timeout_seconds=.2, termination_grace_seconds=1, frame_bytes=8192))
    host.open_root(cwd=str(tmp_path)); host.start_turn('one turn')
    if mode != 'terminal-no-ack':
        with pytest.raises(HostError, match='turn/interrupt:rpc_timeout'):
            host.interrupt()
        assert host.completion is None
    else:
        host.interrupt()
        assert host.poll(0) == {'id':'t1', 'status':'interrupted'}
        assert host.connection.closed and host.terminal_transport_error == 'rpc_timeout'
        assert any(event['method']=='turn/completed' for event in events)
        with pytest.raises(HostError, match='host_connection_unusable'):
            host.start_turn('must not replay')
        assert host.completion == {'id':'t1', 'status':'interrupted'}


def test_turn_timeout_preserves_exact_active_turn_for_interrupt(peer,tmp_path):
    host,_=peer('waiting');host.open_root(cwd=str(tmp_path));host.start_turn('work')
    with pytest.raises(HostError,match='root_turn_timeout'):host.wait_turn(.05)
    assert host.turn_id=='t1' and host.completion is None
    with pytest.raises(HostError,match='already_active'):host.start_turn('retry')
    host.interrupt();assert host.wait_turn(2)['status']=='interrupted'


@pytest.mark.parametrize('mode,code', [('timeout','rpc_timeout'),('eof','app_server_closed'),
    ('invalid','protocol_invalid_json'),('oversized','protocol_message_limit'),
    ('server-request','unsupported_server_request'),('malformed','actual_turn_identity_missing')])
def test_uncertain_protocol_failure_never_retries(peer,tmp_path,mode,code):
    host,_=peer(mode,limits=HostLimits(rpc_timeout_seconds=.3,termination_grace_seconds=1,frame_bytes=8192))
    host.open_root(cwd=str(tmp_path))
    with pytest.raises(HostError,match=code):host.start_turn('one attempt')
    with pytest.raises(HostError,match='unusable'):host.start_turn('never sent')
    calls=[json.loads(x)['method'] for x in (tmp_path/'requests').read_text().splitlines()]
    assert calls.count('turn/start')==1


def test_pinned_root_never_answers_server_permission_request(peer,tmp_path):
    host,events=peer('server-request')
    host.permissions=RootPermissions()
    host.open_root(cwd=str(tmp_path))
    with pytest.raises(HostError,match='unsupported_server_request'):host.start_turn('one attempt')
    sent=[json.loads(x) for x in (tmp_path/'requests').read_text().splitlines()]
    assert not any(item.get('id')==42 for item in sent)  # no reply, approval or denial is fabricated
    assert next(item for item in sent if item.get('method')=='turn/start')['params']['sandboxPolicy']=={'type':'workspaceWrite','networkAccess':True}
    assert any(event.get('method') == 'scid/serverRequest' and event['params']['state'] == 'unsupported' for event in events)


@pytest.mark.parametrize('mode',['network-mismatch','extra-root'])
def test_pinned_root_stops_when_effective_network_or_roots_differ(peer,tmp_path,mode):
    # Review counterexample: networkAccess=false (or an extra writable root) while
    # the frozen declaration allows network in the workspace only.
    host,_=peer(mode)
    host.permissions=RootPermissions()
    with pytest.raises(HostError,match='root_permissions_mismatch'):host.open_root(cwd=str(tmp_path))
    sent=[json.loads(x) for x in (tmp_path/'requests').read_text().splitlines()]
    start=next(item for item in sent if item.get('method')=='thread/start')['params']
    assert start['config']['sandbox_workspace_write']=={'network_access':True,'writable_roots':[]}
    assert 'turn/start' not in {item.get('method') for item in sent}


def test_rpc_error_is_sanitized_but_private_evidence_kept(peer,tmp_path):
    host,events=peer('error');host.open_root(cwd=str(tmp_path))
    with pytest.raises(HostError,match='workspace_requirements_unavailable') as caught:host.start_turn('work')
    assert 'secret' not in str(caught.value)
    assert events[-1]['params']['error']['message'].endswith('secret')


def test_failed_turn_not_reported_as_success(peer,tmp_path):
    host,_=peer('failed');host.open_root(cwd=str(tmp_path));host.start_turn('work')
    assert host.wait_turn(2)['status']=='failed'


def test_idle_permanent_persistence_failure_preserves_original_error_without_transport_failure(peer,tmp_path):
    def broken(event):
        if event['method']=='turn/completed':raise OSError('store unavailable')
    host,_=peer('interrupt',sink=broken);host.open_root(cwd=str(tmp_path))
    host.start_turn('work');host.interrupt()
    with pytest.raises(OSError,match='store unavailable'):
        host.poll(1)
    assert host.completion is None and not host.connection.failed


def test_idle_retryable_event_persistence_keeps_connection_and_retries_exact_terminal(peer,tmp_path):
    from scidiscovery.artifact_agent.service.progression import ObservationRetriesExhausted
    attempts = []
    def busy_once(event):
        if event['method'] == 'turn/completed':
            attempts.append(event['params']['turn'].copy())
            if len(attempts) <= 2:
                raise ObservationRetriesExhausted()
    host, _ = peer('interrupt', sink=busy_once)
    host.open_root(cwd=str(tmp_path))
    host.start_turn('work')
    host.interrupt()
    with pytest.raises(ObservationRetriesExhausted):
        host.poll(1)
    assert host.completion is None and not host.connection.failed
    buffered = bytes(host.connection.buffer)
    assert 0 < len(buffered) <= host.connection.limits.frame_bytes + 65536
    with pytest.raises(ObservationRetriesExhausted):
        host.poll(0)
    assert bytes(host.connection.buffer) == buffered  # No duplicate queue or new read while delivery is blocked.
    host.poll(0)  # Retry buffered notification even without another readable frame.
    assert attempts == [dict(id='t1', status='interrupted')] * 3
    assert host.completion == dict(id='t1', status='interrupted') and not host.connection.failed
    calls = [json.loads(line)['method'] for line in (tmp_path/'requests').read_text().splitlines()]
    assert calls.count('turn/start') == calls.count('turn/interrupt') == 1


def test_retryable_event_inside_unresolved_rpc_still_forbids_request_replay(peer,tmp_path):
    from scidiscovery.artifact_agent.service.progression import ObservationRetriesExhausted
    def busy(event):
        if event['method'] == 'turn/completed':
            raise ObservationRetriesExhausted()
    host, _ = peer('event-before-reply', sink=busy)
    host.open_root(cwd=str(tmp_path))
    with pytest.raises(ObservationRetriesExhausted):
        host.start_turn('work')
    assert host.connection.failed and host.completion is None
    with pytest.raises(HostError):
        host.start_turn('must not replay')
    calls = [json.loads(line)['method'] for line in (tmp_path/'requests').read_text().splitlines()]
    assert calls.count('turn/start') == 1


def test_disconnect_does_not_signal_other_process(peer,tmp_path):
    other=subprocess.Popen([sys.executable,'-c','import time;time.sleep(20)'])
    try:
        host,_=peer();host.open_root(cwd=str(tmp_path));host.close()
        assert other.poll() is None
    finally:
        other.terminate();other.wait(timeout=3)


def test_pipe_backpressure_obeys_deadline_without_blocking(tmp_path):
    script=tmp_path/'not-reading.py'
    script.write_text('import time; time.sleep(20)')
    connection=AppServer.launch([sys.executable,str(script)],cwd=tmp_path,environment=dict(os.environ),
        stderr=subprocess.DEVNULL,limits=HostLimits(rpc_timeout_seconds=.1,termination_grace_seconds=1,frame_bytes=262144),
        on_event=lambda event:None)
    try:
        with pytest.raises(HostError,match='rpc_timeout'):
            connection.rpc('turn/start',{'input':'x'*200000})
        assert connection.failed
    finally:connection.close()


def test_multiple_small_frames_do_not_count_as_one_oversized_message(tmp_path):
    script=tmp_path/'many-frames.py'
    script.write_text('''import sys,json
request=json.loads(sys.stdin.readline())
sys.stdout.write(''.join(json.dumps({'method':'update','params':{'text':'x'*700}})+'\\n' for _ in range(8)))
sys.stdout.write(json.dumps({'id':request['id'],'result':{}})+'\\n');sys.stdout.flush()
sys.stdin.read()
''')
    events=[]
    connection=AppServer.launch([sys.executable,str(script)],cwd=tmp_path,environment=dict(os.environ),
        stderr=subprocess.DEVNULL,limits=HostLimits(rpc_timeout_seconds=2,frame_bytes=1024),on_event=events.append)
    try:
        assert connection.rpc('read',{})=={}
        assert len(events)==8
        assert not connection.buffer
    finally:connection.close()


def test_restore_active_turn_blocks_new_work_until_observed_terminal(peer,tmp_path):
    host,_=peer('interrupt')
    host.open_root(cwd=str(tmp_path),prior=RootIdentity('root','root'),active_turn_id='old-turn')
    with pytest.raises(HostError,match='already_active'):host.start_turn('duplicate')
    host.interrupt()
    assert host.wait_turn(2)=={'id':'old-turn','status':'interrupted'}
    calls=[json.loads(x) for x in (tmp_path/'requests').read_text().splitlines()]
    assert not any(c['method']=='turn/start' for c in calls)
