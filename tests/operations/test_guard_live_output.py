"""The supervised child's user prompt must be visible before it can proceed."""
import json
import os
import sys
import threading

import pytest

from scripts import run_tests as guard


@pytest.mark.process_e2e
def test_child_prompt_visible_before_user_acknowledgement(tmp_path):
    prompt = b"Select instance: http://127.0.0.1:12345/sessions/test\n"
    acknowledgement = tmp_path / "selected"
    stop = threading.Event()

    def user_reads_prompt():
        while not stop.wait(.02):
            log = tmp_path / "pytest.log"
            if log.exists() and prompt in log.read_bytes():
                acknowledgement.touch()
                return

    reader = threading.Thread(target=user_reads_prompt, daemon=True)
    limits = json.loads(guard.DEFAULT_CONFIG.read_text())["limits"]
    limits["timeout_seconds"] = 10
    child = """
import sys, time
from pathlib import Path
print('Select instance: http://127.0.0.1:12345/sessions/test', flush=True)
deadline = time.monotonic() + 5
while not Path(sys.argv[1]).exists():
    if time.monotonic() >= deadline:
        sys.exit(7)
    time.sleep(.02)
"""
    # The outer test runner owns the global serial lock. This descriptor only
    # satisfies run_one's inherited-descriptor plumbing for the nested child.
    with (tmp_path / "inherited-fd").open("w") as inherited:
        reader.start()
        try:
            result = guard.run_one([sys.executable, "-c", child, str(acknowledgement)],
                dict(os.environ), limits, tmp_path, inherited.fileno())
        finally:
            stop.set()
            reader.join(timeout=1)
    assert result["stop_reason"] == "exited", result
    assert result["returncode"] == 0, result
    assert acknowledgement.exists()
