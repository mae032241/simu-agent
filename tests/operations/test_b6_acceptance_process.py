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


def test_report_keeps_unknown_attempt_and_does_not_create_native_work(tmp_path):
    config=json.loads((ROOT/'scripts/acceptance/b6.json').read_text())
    write(tmp_path/'suite.json',{'config':config,'previous':None})
    write(tmp_path/'manual-known.attempt.json',{'started_ns':1})
    before=set(tmp_path.iterdir())
    value=invoke('report','--suite',tmp_path)
    assert value.returncode==0,value.stderr
    report=json.loads(value.stdout)
    assert report['cases']['manual-known']['attempt']=='outcome_unknown'
    assert report['cases']['rollback']['status']=='blocked'
    assert report['comparisons']['known']['comparable'] is False
    assert report['b6_passed'] is False
    assert set(tmp_path.iterdir())==before


def test_native_entry_requires_case_before_any_process_launch(tmp_path):
    value=subprocess.run([sys.executable,str(ROOT/'scripts/accept_progression.py'),
        '--candidate',str(tmp_path),'--scenario','helper'],cwd=ROOT,capture_output=True,text=True,timeout=15)
    assert value.returncode==2
    assert 'requires --case-file' in value.stderr
    assert not list(tmp_path.iterdir())
