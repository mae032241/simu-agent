"""Replay only the four broad-regression failures against the saved pre-change bytes."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

repository = Path.cwd()
evidence = Path(__file__).parent
baseline = json.loads((evidence / "baseline.json").read_text())
root = Path(tempfile.mkdtemp(prefix="scid-registration-baseline-check-"))
for directory in ("src", "tests", "plugins", "roles"):
    shutil.copytree(repository / directory, root / directory,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "build", "*.egg-info", ".pytest_cache"))
shutil.copy2(repository / "pyproject.toml", root / "pyproject.toml")
for item in baseline["files"]:
    target = root / item["path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(baseline["snapshot"]) / item["path"], target)
names = (
    "test_candidate_binding_crash_windows_and_response_replay",
    "test_status_is_pure_and_failure_recovery_is_explicit",
    "test_real_process_failure_isolation_windows_replay_after_restart",
    "test_recovery_without_snapshot_keeps_original_and_reports_pending",
)
result = subprocess.run([sys.executable, "-m", "pytest", "-q", *(
    "tests/operations/test_l2_run_invariants.py::" + name for name in names)],
    cwd=root, env={**os.environ, "PYTHONNOUSERSITE": "1"}, timeout=90)
print("baseline replay root:", root)
raise SystemExit(result.returncode)
