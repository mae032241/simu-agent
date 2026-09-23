from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


def _pythonpath(source_root: Path, repository_root: Path) -> str:
    return os.pathsep.join(
        str(path)
        for path in (
            source_root / "src",
            source_root / "plugins" / "curve_score",
            source_root / "plugins" / "curve_figure_evidence",
            source_root / "plugins" / "tcad_artifact",
            repository_root,
        )
    )


def _run_corpus(
    *, source_root: Path, repository_root: Path, work_root: Path
) -> dict[str, object]:
    output = work_root / "manifest.json"
    environment = dict(os.environ)
    environment.update(
        {
            "MALLOC_ARENA_MAX": "2",
            "PYTHONPATH": _pythonpath(source_root, repository_root),
        }
    )
    completed = subprocess.run(
        (
            sys.executable,
            str(
                repository_root
                / "tests"
                / "operations"
                / "m3_transform_equivalence_runner.py"
            ),
            "--source-root",
            str(source_root),
            "--work-root",
            str(work_root / "runs"),
            "--output",
            str(output),
        ),
        cwd=repository_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert completed.returncode == 0, (
        f"transform corpus failed for {source_root}\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
    return json.loads(output.read_text(encoding="utf-8"))


def test_retained_generic_transform_corpus_matches_the_complete_catalog(tmp_path: Path) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    current = _run_corpus(
        source_root=repository_root,
        repository_root=repository_root,
        work_root=tmp_path / "current",
    )
    assert current["transform_count"] == 19
    assert current["guard_count"] == 8
    assert set(current["catalog_transform_ids"]) == {
        *(item["operation_id"] for item in current["operations"]),
        "science.figure.evidence.materialize.v1",
        "scidiscovery.curve-bundle.figure-evidence.v2",
        "tcad.execution-plan.project.v1",
    }
