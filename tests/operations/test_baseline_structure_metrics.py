from __future__ import annotations

import re
import subprocess
from pathlib import Path


def test_r0_source_structure_metrics_are_reproducible() -> None:
    repository = Path(__file__).resolve().parents[2]
    baseline = "404aeb14c6ebc4b08bac599db91eaee54c103f48"

    def baseline_lines(name: str) -> list[str]:
        return subprocess.run(
            ["git", "show", f"{baseline}:{name}"],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
    measured_files = (
        "src/scidiscovery/scheduler_topology.py",
        "src/scidiscovery/platforms/roles.py",
        "src/scidiscovery/artifact_agent/runtime.py",
        "src/scidiscovery/artifact_agent/interfaces/mcp_root.py",
        "src/scidiscovery/artifact_agent/service/tasks.py",
        "src/scidiscovery/artifact_agent/approval_ui/render.py",
    )
    expected_lines = {
        "src/scidiscovery/scheduler_topology.py": 341,
        "src/scidiscovery/platforms/roles.py": 339,
        "src/scidiscovery/artifact_agent/runtime.py": 256,
        "src/scidiscovery/artifact_agent/interfaces/mcp_root.py": 2616,
        "src/scidiscovery/artifact_agent/service/tasks.py": 6952,
        "src/scidiscovery/artifact_agent/approval_ui/render.py": 3153,
        "deploy/install.sh": 1008,
    }
    assert {
        name: len(baseline_lines(name))
        for name in expected_lines
    } == expected_lines

    branch_pattern = re.compile(
        r"if .*role|elif .*role|role ==|role in|schema_id ==|profile ==|"
        r"context_profile ==|tcad"
    )
    branch_hits = sum(
        1
        for name in measured_files
        for line in baseline_lines(name)
        if branch_pattern.search(line)
    )
    assert branch_hits == 114

    import_pattern = re.compile(
        r"(^|\s)(from|import) (tcad_artifact|curve_score|ingaas)"
    )
    source_files = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", baseline, "src"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    domain_import_hits = sum(
        1
        for name in source_files
        if name.endswith(".py")
        for line in baseline_lines(name)
        if import_pattern.search(line)
    )
    assert domain_import_hits == 6
