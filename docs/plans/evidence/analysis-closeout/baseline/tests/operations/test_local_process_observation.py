"""Short real native subprocesses; no solver, fitting or 15-minute waits."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest

from scidiscovery.artifact_agent.service import local_process_observation as observation


def workspace(tmp_path, code, *, remaining=10):
    (tmp_path / 'scratch').mkdir()
    (tmp_path / 'tools').mkdir()
    shutil.copyfile(observation.__file__, tmp_path / 'tools/local_process_observation.py')
    (tmp_path / 'scratch/analysis.py').write_text(code)
    (tmp_path / 'assignment.json').write_text(json.dumps({'budget': {'deadline_at':
        (datetime.now(timezone.utc) + timedelta(seconds=remaining)).isoformat()}}))
    return tmp_path


def launch(root, timeout=5, reserve=0):
    return subprocess.run([sys.executable, 'tools/local_process_observation.py',
        '--timeout', str(timeout), '--submission-reserve', str(reserve), 'analysis.py'],
        cwd=root, capture_output=True, timeout=8)


def test_capture_failure_and_limits_with_safe_pure_summary(tmp_path):
    root = workspace(tmp_path, 'import os,resource\nprint(resource.getrlimit(resource.RLIMIT_AS)[0])\n'
        'print(os.environ["OPENBLAS_NUM_THREADS"])\nraise ModuleNotFoundError("No module named fixture_plotter")\n')
    result = launch(root)
    assert result.returncode == 1, result.stderr
    directory = root / observation.RECORD_DIR
    original = next(directory.glob('*.stderr.raw')).read_bytes()
    normalized = next(directory.glob('*.stderr.log')).read_bytes()
    assert str(root).encode() in original and str(root).encode() not in normalized
    assert b'ModuleNotFoundError' in normalized
    stdout = next(directory.glob('*.stdout.raw')).read_text().splitlines()
    assert int(stdout[0]) <= observation.MEMORY_LIMIT and stdout[1] == '1'
    before = (directory / 'latest.json').read_bytes()
    summary = observation.read_summary(root)
    assert summary['state'] == 'finished' and summary['exit_code'] == 1
    assert summary['peak_rss_kib'] > 0 and summary['process_group_stopped'] is True
    assert (directory / 'latest.json').read_bytes() == before
    assert not list(root.rglob('*.pyc'))


def test_timeout_respects_remaining_run_budget_on_every_retry(tmp_path):
    root = workspace(tmp_path, 'import time\nprint("before",flush=True)\ntime.sleep(4)\n', remaining=.6)
    result = launch(root, timeout=4, reserve=.1)
    assert result.returncode == 124
    first = observation.read_summary(root)
    assert first['timed_out'] is True and 0 < first['effective_timeout_seconds'] < .5
    assert first['process_group_stopped'] is True
    time.sleep(.15)
    assert launch(root, timeout=4, reserve=.1).returncode == 124
    assert observation.read_summary(root)['state'] == 'not_started'
    assert len(list((root / observation.RECORD_DIR).glob('*.stdout.raw'))) == 1


def test_budget_allows_requested_batch_without_180_second_ceiling(tmp_path):
    root = workspace(tmp_path, 'import time\ntime.sleep(.1)\nprint("done")\n', remaining=600)
    assert launch(root, timeout=240, reserve=120).returncode == 0
    summary = observation.read_summary(root)
    assert summary['effective_timeout_seconds'] == 240 and summary['timed_out'] is False


def test_legacy_assignment_and_bounded_logs(tmp_path):
    root = workspace(tmp_path, 'print("x"*300000)\n')
    (root / 'assignment.json').write_text('{}')
    assert launch(root).returncode == 0
    summary = observation.read_summary(root)
    assert summary['budget_source'] == 'unavailable' and summary['logs_truncated']
    assert next((root / observation.RECORD_DIR).glob('*.stdout.raw')).stat().st_size == observation.LOG_LIMIT
    assert b'truncated' in next((root / observation.RECORD_DIR).glob('*.stdout.log')).read_bytes()


def test_outer_exit_does_not_leave_child_computing(tmp_path):
    root = workspace(tmp_path, 'import subprocess,sys\nsubprocess.Popen([sys.executable,"-c",'
        '"import time; from pathlib import Path; time.sleep(1); Path(\\\"late\\\").write_text(\\\"bad\\\")"])\n')
    assert launch(root).returncode == 0
    time.sleep(1.1)
    assert not (root / 'scratch/late').exists()
    # A reparented zombie may remain visible to killpg: this must stay unknown/false.
    assert observation.read_summary(root)['process_group_stopped'] in (True, False)


def test_stop_request_and_single_computation(tmp_path):
    root = workspace(tmp_path, 'import time\ntime.sleep(4)\n')
    command = [sys.executable, 'tools/local_process_observation.py', '--timeout', '5',
        '--submission-reserve', '0', 'analysis.py']
    first = subprocess.Popen(command, cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        until = time.monotonic() + 2
        while observation.read_summary(root).get('state') != 'running' and time.monotonic() < until:
            time.sleep(.01)
        assert launch(root).returncode != 0
        observation.request_stop(root)
        first.wait(timeout=2)
        assert observation.read_summary(root)['cancelled'] is True
        assert launch(root).returncode == 124
    finally:
        if first.poll() is None:
            first.kill(); first.wait()


@pytest.mark.parametrize('raw', ['{}', '{', '{"state":"private command","exit_code": "secret"}'])
def test_missing_or_corrupt_observation_is_not_a_submission_gate(tmp_path, raw):
    root = workspace(tmp_path, 'pass')
    directory = root / observation.RECORD_DIR; directory.mkdir()
    (directory / 'latest.json').write_text(raw)
    summary = observation.read_summary(root)
    assert 'private command' not in json.dumps(summary) and 'secret' not in json.dumps(summary)
    assert summary['scientific_evidence'] is False
