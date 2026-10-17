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


def test_status_requires_evidence_and_never_claims_replay_safe(tmp_path):
    path = tmp_path / 'resource.json'
    assert guard.supervision_status(path)['state'] == 'unknown'
    path.write_text(json.dumps({'returncode': 0, 'stop_reason': 'exited'}))
    assert guard.supervision_status(path)['reason'] == 'supervision_heartbeat_unrecorded'
    for value in ('null', '[]', '{broken', 'x' * 65537):
        path.write_text(value)
        assert guard.supervision_status(path)['state'] == 'unknown'
