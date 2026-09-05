from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile


_M2_ARCHIVE_SHA256 = (
    "bd8f548312cdf4eebcc4d3be9f261fb1640a94e9d0b42bf9b784c137706f6002"
)
_M2_SOURCE = {
    "files": 142,
    "lines": 49018,
    "digest": "0b5c37e315984e8dc476efa75bd791be9ba7060607551fcd91876fe311752eb2",
}


def _without_compiled_identity(value: object) -> object:
    """Remove catalog-derived identity while retaining transform result fields."""

    if isinstance(value, dict):
        return {
            key: _without_compiled_identity(item)
            for key, item in value.items()
            if key
            not in {
                "operation_digest",
                "operation_invocation_fingerprint",
                "request_fingerprint",
            }
        }
    if isinstance(value, list):
        return [_without_compiled_identity(item) for item in value]
    return value


def _without_parent_refs(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _without_parent_refs(item)
            for key, item in value.items()
            if key != "parent_refs"
        }
    if isinstance(value, list):
        return [_without_parent_refs(item) for item in value]
    return value


def _pythonpath(source_root: Path, repository_root: Path) -> str:
    return os.pathsep.join(
        str(path)
        for path in (
            source_root / "src",
            source_root / "plugins" / "curve_score",
            source_root / "plugins" / "curve_figure_evidence",
            source_root / "plugins" / "tcad_artifact",
            source_root / "plugins" / "ingaas_fig4",
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


def test_retained_production_transforms_match_the_sealed_m2_oracle(
    tmp_path: Path,
) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    archive = (
        repository_root
        / "archive"
        / "r5-m2-transform-oracle"
        / "m2-production-source.tar.gz"
    )
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == _M2_ARCHIVE_SHA256

    m2_source = tmp_path / "m2-source"
    m2_source.mkdir()
    with tarfile.open(archive, "r:gz") as bundle:
        bundle.extractall(m2_source, filter="data")

    m2 = _run_corpus(
        source_root=m2_source,
        repository_root=repository_root,
        work_root=tmp_path / "m2",
    )
    current = _run_corpus(
        source_root=repository_root,
        repository_root=repository_root,
        work_root=tmp_path / "m3",
    )

    assert m2["source"] == _M2_SOURCE
    assert m2["transform_count"] == current["transform_count"] == 19
    assert m2["guard_count"] == current["guard_count"] == 8
    retained = {item["operation_id"] for item in current["operations"]}
    removed = {
        "science.knowledge.update.diagnosis.v1",
        "science.knowledge.update.validation.v1",
    }
    assert set(m2["catalog_transform_ids"]) == retained | removed
    assert set(current["catalog_transform_ids"]) == retained

    provenance = {"source", "catalog_digest", "catalog_transform_ids"}
    m2_behavior = {key: value for key, value in m2.items() if key not in provenance}
    current_behavior = {
        key: value for key, value in current.items() if key not in provenance
    }
    m2_operations = {
        item["operation_id"]: item for item in m2_behavior.pop("operations")
    }
    current_operations = {
        item["operation_id"]: item for item in current_behavior.pop("operations")
    }
    assert _without_compiled_identity(current_behavior) == _without_compiled_identity(
        m2_behavior
    )
    assert _without_compiled_identity(current_operations) == (
        _without_compiled_identity(m2_operations)
    )
