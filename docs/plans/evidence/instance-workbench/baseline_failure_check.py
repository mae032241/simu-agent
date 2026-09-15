"""Reproduce one untouched fixture failure against the exact Git baseline."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

repository = Path.cwd()
evidence = Path(__file__).resolve().parent
baseline = "da220ce31c8cc9f9a60542a018b279e2f331f4c0"
with tempfile.TemporaryDirectory(prefix="workbench-baseline-fixture-") as temporary:
    source = Path(temporary)
    raw = subprocess.run(["git", "archive", "--format=tar", baseline, "src", "plugins", "pyproject.toml",
        "tests/conftest.py", "tests/operations/conftest.py", "tests/fixtures", "tests/operations/test_l2_run_invariants.py"],
        cwd=repository, check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(raw)) as package:
        package.extractall(source, filter="data")
    selected = "tests/operations/test_l2_run_invariants.py::test_recursive_current_uses_producer_receipts_and_commit_rechecks_head"
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", selected], cwd=source,
        capture_output=True, text=True, timeout=60)
    (evidence / "preexisting-l2-baseline.log").write_text(result.stdout + result.stderr)
    expected = result.returncode == 1 and "output_context_invalid: blind_csv/blind.csv.observe.v1/csv_observation" in result.stdout
    print(json.dumps({"baseline": baseline, "nodeid": selected, "baseline_test_exit_code": result.returncode,
        "known_catalog_fixture_failure_reproduced": expected}))
    if not expected:
        print(result.stdout + result.stderr)
        raise SystemExit(1)
