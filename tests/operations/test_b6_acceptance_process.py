"""Real command transport for the acceptance reporter; no installed/model process."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.b6_evidence import write

pytestmark=pytest.mark.process_e2e
ROOT=Path(__file__).resolve().parents[2]


def invoke(*args):
    return subprocess.run([sys.executable,str(ROOT/'scripts/accept_b6.py'),*map(str,args)],
        cwd=ROOT,capture_output=True,text=True,timeout=15)


@pytest.mark.parametrize('config_name', ['b6.json', 'scientific_progress.json'])
def test_report_keeps_unknown_attempt_and_does_not_create_native_work(tmp_path, config_name):
    config=json.loads((ROOT/'scripts/acceptance'/config_name).read_text())
    pair=next(c['pair'] for c in config['cases'].values() if 'pair' in c)
    case_id='manual-'+pair
    write(tmp_path/'suite.json',{'config':config,'previous':None})
    write(tmp_path/(case_id+'.attempt.json'),{'started_ns':1})
    before=set(tmp_path.iterdir())
    value=invoke('report','--suite',tmp_path)
    assert value.returncode==0,value.stderr
    report=json.loads(value.stdout)
    assert report['cases'][case_id]['attempt']=='outcome_unknown'
    if 'rollback' in config['cases']:
        assert report['cases']['rollback']['status']=='blocked'
    assert report['comparisons'][pair]['comparable'] is False
    assert report['b6_passed'] is False
    assert set(tmp_path.iterdir())==before


def test_native_entry_requires_case_before_any_process_launch(tmp_path):
    value=subprocess.run([sys.executable,str(ROOT/'scripts/accept_progression.py'),
        '--candidate',str(tmp_path),'--scenario','helper'],cwd=ROOT,capture_output=True,text=True,timeout=15)
    assert value.returncode==2
    assert 'requires --case-file' in value.stderr
    assert not list(tmp_path.iterdir())


def test_serial_lock_handoff_keeps_other_processes_out(tmp_path,monkeypatch):
    import fcntl
    from scripts import run_tests as guard
    monkeypatch.setattr(guard,'SERIAL_LOCK',tmp_path/'serial.lock')
    program='''
import fcntl,sys
from pathlib import Path
from scripts import run_tests as guard
guard.SERIAL_LOCK=Path(sys.argv[1])
with guard.serial_lock(int(sys.argv[2])):
    with guard.SERIAL_LOCK.open('a') as other:
        try: fcntl.flock(other,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: pass
        else: raise AssertionError('lock was not held')
print('shared lock retained')
'''
    with guard.serial_lock() as owner:
        child=subprocess.run([sys.executable,'-c',program,str(guard.SERIAL_LOCK),str(owner.fileno())],
            cwd=ROOT,pass_fds=(owner.fileno(),),capture_output=True,text=True,timeout=10)
        assert child.returncode==0,child.stderr
        assert child.stdout.strip()=='shared lock retained'
        with guard.SERIAL_LOCK.open('a') as other:
            with pytest.raises(BlockingIOError):fcntl.flock(other,fcntl.LOCK_EX|fcntl.LOCK_NB)
    with guard.serial_lock():pass
