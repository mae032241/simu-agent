"""Real process failure injection at reusable supervision and pilot boundaries."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from scripts import run_tests as guard


def await_file(path, process, timeout=5):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if path.exists():
            return
        assert process.poll() is None, process.communicate()[0]
        time.sleep(.02)
    raise AssertionError(f"fixture did not create {path.name}")


def stopped(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().split()[2] == "Z"
    except FileNotFoundError:
        return True


def cleanup_owned(process, directory):
    if process.poll() is None:
        process.kill()
    process.wait(timeout=3)
    # SIGKILL cannot clean its child. The test owns these exact recorded PIDs.
    for name in ('owned.json', 'host.json'):
        path = directory / name
        if path.exists():
            pids = json.loads(path.read_text())
            guard._signal_processes(pids[0], set(pids), signal.SIGKILL)


SUPERVISOR = r'''
import json,os,signal,sys,time
from pathlib import Path
from scripts import run_tests as guard
case,root,fd=sys.argv[1:];root=Path(root);fd=int(fd)
limits=json.loads(guard.DEFAULT_CONFIG.read_text())['limits']
limits.update(minimum_available_bytes=1,available_drop_stop_bytes=2_000_000_000,
              observed_tree_rss_stop_bytes=500_000_000,timeout_seconds=10,
              sample_interval_seconds=.02,termination_grace_seconds=.3)
child="""
import json,os,subprocess,sys,time
from pathlib import Path
case,root=sys.argv[1:];root=Path(root)
child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(100)'],start_new_session=True)
(root/'owned.json').write_text(json.dumps([os.getpid(),child.pid]))
time.sleep(.3 if case in ('normal','exit_error') else 100)
print('x'*200000+'tail_retained',flush=True)
sys.exit(7 if case=='exit_error' else 0)
"""
original=guard._descendant_rss_kib
ready_samples=0
if case in ('sampling_error','cleanup_error'):
    def sample(pid):
        global ready_samples
        answer=original(pid)
        if (root/'owned.json').exists():
            ready_samples+=1
            if ready_samples>1:raise ValueError('first_sampler_fault')
        return answer
    guard._descendant_rss_kib=sample
if case in ('cleanup_error','timeout_cleanup_error'):
    if case=='timeout_cleanup_error':limits['timeout_seconds']=.4
    original_signal=guard._signal_processes
    def send(group,pids,signum):
        original_signal(group,pids,signum)
        if signum==signal.SIGTERM:raise RuntimeError('secondary_cleanup_fault')
    guard._signal_processes=send
try:
    result=guard.run_one([sys.executable,'-c',child,case,str(root)],dict(os.environ),limits,root,fd)
except BaseException as exc:
    (root/'raised.json').write_text(json.dumps({'type':type(exc).__name__,'message':str(exc),
        'notes':getattr(exc,'__notes__',[])}))
    sys.exit(31)
print(json.dumps(result),flush=True)
'''


@pytest.mark.process_e2e
@pytest.mark.parametrize('case', ['normal', 'exit_error', 'sampling_error', 'cleanup_error',
                                  'TERM', 'HUP', 'INT', 'KILL', 'timeout_cleanup_error'])
def test_imported_supervisor_persists_faults_signals_and_stale_unknown(tmp_path, case):
    # The outer scripts/run_tests.py already owns the shared serial lock.
    with (tmp_path / 'fd').open('w') as inherited:
        process = subprocess.Popen([sys.executable, '-c', SUPERVISOR, case, str(tmp_path), str(inherited.fileno())],
            cwd=guard.ROOT, env=dict(os.environ), pass_fds=(inherited.fileno(),),
            start_new_session=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            await_file(tmp_path / 'owned.json', process)
            first = json.loads((tmp_path / 'resource.json').read_text())
            assert first['state'] == 'running' and not first['cleanup_complete']
            if case in ('TERM', 'HUP', 'INT', 'KILL'):
                # Require a later heartbeat while the long child is still active.
                time.sleep(1.15)
                second = json.loads((tmp_path / 'resource.json').read_text())
                assert second['heartbeat_at_unix'] > first['heartbeat_at_unix']
                assert second['observed_tree_rss_high_water_bytes'] > 0
                process.send_signal(getattr(signal, 'SIG' + case))
            output, _ = process.communicate(timeout=5)
            record = json.loads((tmp_path / 'resource.json').read_text())
            pids = json.loads((tmp_path / 'owned.json').read_text())
            if case == 'KILL':
                assert process.returncode == -signal.SIGKILL
                assert record['state'] == 'running' and not record['cleanup_complete']
                status = guard.supervision_status(tmp_path / 'resource.json',
                    now=record['heartbeat_at_unix'] + record['heartbeat_stale_after_seconds'] + 1)
                assert status['state'] == 'unknown' and status['reason'] == 'supervision_heartbeat_stale'
                assert status['recorded_state'] == 'running' and not status['replay_safe']
                return
            assert record['state'] == 'terminal', output.decode()
            assert all(stopped(pid) for pid in pids), record
            assert guard.supervision_status(tmp_path / 'resource.json')['state'] == 'terminal'
            if case in ('normal', 'exit_error'):
                assert process.returncode == 0 and record['stop_reason'] == 'exited'
                assert record['returncode'] == (0 if case == 'normal' else 7)
                assert record['cleanup_complete']
                assert (tmp_path/'pytest.log').read_bytes().endswith(b'tail_retained\n')
            else:
                assert process.returncode == 31
                raised = json.loads((tmp_path / 'raised.json').read_text())
                if case in ('sampling_error', 'cleanup_error'):
                    assert raised['type'] == 'ValueError' and raised['message'] == 'first_sampler_fault'
                    assert record['stop_reason'] == 'supervisor_error'
                    assert not record['cleanup_complete']  # final sampling failed too
                    if case == 'cleanup_error':
                        assert any(e['message'] == 'secondary_cleanup_fault' for e in record['cleanup_errors'])
                        assert raised['notes']
                elif case=='timeout_cleanup_error':
                    assert raised['type']=='RuntimeError' and raised['message']=='secondary_cleanup_fault'
                    assert record['stop_reason']=='timeout' and not record['cleanup_complete']
                    assert record['cleanup_errors'][0]['message']=='secondary_cleanup_fault'
                else:
                    assert raised['type'] == 'SupervisorInterrupted'
                    assert record['received_signals'] == [getattr(signal, 'SIG' + case)]
                    assert record['stop_reason'] == 'interrupted' and record['cleanup_complete']
        finally:
            cleanup_owned(process, tmp_path)


def test_status_requires_evidence_and_never_claims_replay_safe(tmp_path):
    path = tmp_path / 'resource.json'
    assert guard.supervision_status(path)['state'] == 'unknown'
    path.write_text(json.dumps({'returncode': 0, 'stop_reason': 'exited'}))
    assert guard.supervision_status(path)['reason'] == 'supervision_heartbeat_unrecorded'
    for value in ('null', '[]', '{broken', 'x' * 65537):
        path.write_text(value)
        assert guard.supervision_status(path)['state'] == 'unknown'


PILOT = r'''
import json,os,signal,subprocess,sys,time
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path.cwd()/'src'))
from scripts import run_covshift_pilot as pilot
import scidiscovery.artifact_agent.interfaces.mcp_daemon as installed
case,root=sys.argv[1:];root=Path(root)
spec={'root':str(root),'project':str(root),'python':sys.executable,'arm':'native_goal',
      'native':'not-executed','task_python':sys.executable,'settings_sha256':'digest','native_sha256':'digest',
      'public_sha256':{},'code_mode_host':{}}
installed.__file__=str(Path(sys.executable).parent.parent/'synthetic-installed.py')
pilot.sha=lambda path:'digest';pilot.native_runtime=lambda path:{}
pilot.canary_code=lambda spec:'synthetic-no-execution'
for name in ('control/private-canary.txt','codex-home/auth-canary.json','codex-home/sessions/history-canary'):
    path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.touch()
def launch(spec,meter):
    child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(100)'],start_new_session=True,
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    (root/'host.json').write_text(json.dumps([child.pid]))
    def rpc(*args):
        if case=='TERM':
            (root/'ready').touch();time.sleep(100)
        raise RuntimeError('first_control_fault')
    def close():
        # First fault and cleanup intent must already be durable at close entry.
        saved=json.loads((root/'run-result.json').read_text())
        (root/'close-observed.json').write_text(json.dumps(saved))
        if case=='cleanup_KILL':
            (root/'ready').touch();time.sleep(100)
        child.terminate();child.wait(timeout=2)
        if case=='cleanup_error':raise RuntimeError('secondary_host_close_fault')
    return SimpleNamespace(identity=SimpleNamespace(thread_id='synthetic',session_id='synthetic'),
                           connection=SimpleNamespace(rpc=rpc),close=close)
pilot.launch_root=launch
try:
    result=pilot.arm_action(spec,'run')
except BaseException as exc:
    (root/'raised.json').write_text(json.dumps({'type':type(exc).__name__,'message':str(exc)}))
    sys.exit(31)
print(json.dumps(result),flush=True)
'''


@pytest.mark.process_e2e
@pytest.mark.parametrize('case', ['control_error', 'cleanup_error', 'TERM', 'cleanup_KILL'])
def test_pilot_seals_first_fault_before_real_host_cleanup(tmp_path, case):
    process = subprocess.Popen([sys.executable, '-c', PILOT, case, str(tmp_path)],
        cwd=guard.ROOT, env=dict(os.environ), start_new_session=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        if case in ('TERM', 'cleanup_KILL'):
            await_file(tmp_path / 'ready', process)
            process.send_signal(signal.SIGTERM if case == 'TERM' else signal.SIGKILL)
        output, _ = process.communicate(timeout=5)
        record = json.loads((tmp_path / 'run-result.json').read_text())
        before_close = json.loads((tmp_path / 'close-observed.json').read_text())
        assert before_close['state'] == 'stopping' and not before_close['cleanup_complete']
        if case == 'cleanup_KILL':
            assert process.returncode == -signal.SIGKILL
            assert record['state'] == 'stopping' and record['reason'] == 'first_control_fault'
            assert not record['cleanup_complete']
            return
        assert record['state'] == 'terminal' and record['status'] == 'fail', output.decode()
        assert all(stopped(pid) for pid in json.loads((tmp_path / 'host.json').read_text()))
        if case == 'TERM':
            assert process.returncode == 31 and record['exception'] == 'SupervisorInterrupted'
            assert record['received_signals'] == [signal.SIGTERM] and record['cleanup_complete']
        else:
            assert process.returncode == 0 and record['reason'] == 'first_control_fault'
            assert before_close['reason'] == 'first_control_fault'
            assert record['cleanup_complete'] is (case != 'cleanup_error')
            if case == 'cleanup_error':
                assert record['cleanup_errors'][0]['message'] == 'secondary_host_close_fault'
    finally:
        cleanup_owned(process, tmp_path)


@pytest.mark.process_e2e
def test_partial_control_start_preserves_first_error_and_stops_real_child(tmp_path, monkeypatch):
    from scripts import run_covshift_pilot as pilot
    for name in ('control', 'evidence', 'project'):
        (tmp_path/name).mkdir()
    popen, path_open = subprocess.Popen, Path.open
    children = []
    def start(*args, **kwargs):
        child = popen([sys.executable, '-c', 'import sys;sys.exit(3)'], **kwargs)
        children.append(child)
        return child
    class BadClose:
        def __init__(self, stream):self.stream = stream
        def fileno(self):return self.stream.fileno()
        def close(self):
            self.stream.close()
            raise OSError('secondary_log_close_fault')
    def opened(path, *args, **kwargs):
        stream = path_open(path, *args, **kwargs)
        return BadClose(stream) if path.name == 'ui.log' and args == ('wb',) else stream
    monkeypatch.setattr(pilot.subprocess, 'Popen', start)
    monkeypatch.setattr(Path, 'open', opened)
    with pytest.raises(RuntimeError, match='management_ui_exited') as raised:
        pilot.start_control({'root':str(tmp_path), 'project':str(tmp_path/'project'), 'python':sys.executable})
    assert children and all(child.poll() == 3 for child in children)
    assert 'control startup log close: OSError' in raised.value.__notes__


@pytest.mark.process_e2e
@pytest.mark.parametrize('signum', [signal.SIGTERM, signal.SIGHUP])
def test_runner_cancellation_between_batches_seals_summary(tmp_path, signum):
    script = r"""
import json,os,signal,sys,time
from pathlib import Path
from scripts import run_tests as guard
root=Path(sys.argv[1]);fd=int(sys.argv[2])
os.environ['SCID_TEST_LOCK_FD']=str(fd)
# Instrument the batch command only; execute a real no-model child through run_one.
original=guard.run_one
child="import time;time.sleep(.05)"
def run(command,environment,limits,output,lock_fd):
    return original([sys.executable,'-c',child],environment,limits,output,lock_fd)
guard.run_one=run
original_remove=guard.shutil.rmtree
def remove(path,**kwargs):
    if Path(path).name=='tmp':
        (root/'between-batches').touch();time.sleep(100)
    return original_remove(path,**kwargs)
guard.shutil.rmtree=remove
sys.argv=['run_tests.py','--output',str(root/'result'),'--config',str(root/'resources.json'),
          'tests/operations/test_guard_memory_pressure.py']
try:guard.main()
except BaseException as exc:
    (root/'raised.json').write_text(json.dumps({'type':type(exc).__name__}))
    sys.exit(31)
"""
    config=json.loads(guard.DEFAULT_CONFIG.read_text())
    config['limits'].update(minimum_available_bytes=1,timeout_seconds=10,termination_grace_seconds=.3)
    (tmp_path/'resources.json').write_text(json.dumps(config))
    inherited=int(os.environ['SCID_TEST_LOCK_FD'])
    process=subprocess.Popen([sys.executable,'-c',script,str(tmp_path),str(inherited)],
        cwd=guard.ROOT,env=dict(os.environ),pass_fds=(inherited,),start_new_session=True,
        stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    try:
        await_file(tmp_path/'between-batches',process)
        process.send_signal(signum)
        output,_=process.communicate(timeout=5)
        assert process.returncode==31,output.decode()
        assert json.loads((tmp_path/'result/result.json').read_text())['status']=='interrupted'
        child=json.loads((tmp_path/'result/batch-001/resource.json').read_text())
        assert child['state']=='terminal' and child['returncode']==0 and child['stop_reason']=='exited'
        assert json.loads((tmp_path/'raised.json').read_text())['type']=='SupervisorInterrupted'
    finally:cleanup_owned(process,tmp_path)
