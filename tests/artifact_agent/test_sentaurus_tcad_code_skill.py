from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from tcad_artifact.project_packager import DeckProjectDraft


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "skills" / "sentaurus-tcad-code" / "scripts" / "validate_deck_project.py"


def _project(*, profile: str, entrypoint: str, content: str, arguments=()) -> dict:
    return {
        "schema_version": 1,
        "tool_profile": profile,
        "files": [{"relative_path": entrypoint, "content": content}],
        "entrypoint": entrypoint,
        "arguments": list(arguments),
        "expected_outputs": [
            {
                "name": "solver_log",
                "relative_path": "case.log",
                "media_type": "text/plain",
                "required": True,
                "max_bytes": 1024 * 1024,
            }
        ],
        "parameter_bindings": [],
        "runtime_assertions": [],
        "realization_manifest": [],
        "resource_limits": {
            "wall_time_seconds": 60,
            "cpu_time_seconds": 60,
            "max_memory_bytes": 1024 * 1024 * 1024,
            "max_output_bytes": 16 * 1024 * 1024,
            "max_processes": 8,
        },
    }


def _run_skill_validator(tmp_path: Path, project: dict) -> tuple[int, dict]:
    source = tmp_path / "project.json"
    source.write_text(json.dumps(project), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(VALIDATOR), str(source)],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode, json.loads(completed.stdout)


def _validate_packager(project: dict) -> DeckProjectDraft:
    return DeckProjectDraft.model_validate_json(json.dumps(project))


def test_skill_validator_accepts_direct_sprocess_and_sdevice_decks(tmp_path: Path) -> None:
    sprocess = _project(
        profile="sentaurus-sprocess-r2020.09",
        entrypoint="process.cmd",
        content="math coord.ucs\nexit\n",
    )
    sdevice = _project(
        profile="sentaurus-sdevice-r2020.09",
        entrypoint="device.cmd",
        content="File { Output=\"case.log\" }\nSolve { Poisson }\n",
    )

    for project in (sprocess, sdevice):
        returncode, report = _run_skill_validator(tmp_path, project)
        assert returncode == 0
        assert report == {"findings": [], "valid": True}
        _validate_packager(project)


def test_skill_and_packager_reject_shell_as_direct_sprocess_entrypoint(
    tmp_path: Path,
) -> None:
    project = _project(
        profile="sentaurus-sprocess-r2020.09",
        entrypoint="run_qualification.sh",
        content="#!/usr/bin/env bash\nset -eu\nsprocess process.cmd\n",
        arguments=("submit", "qualification_smoke_001"),
    )

    returncode, report = _run_skill_validator(tmp_path, project)
    assert returncode == 1
    codes = {item["code"] for item in report["findings"]}
    assert {"entrypoint.kind", "entrypoint.shell", "arguments.scheduler"} <= codes
    with pytest.raises(ValidationError, match="direct sprocess entrypoint"):
        _validate_packager(project)


def test_skill_and_packager_reject_unresolved_workbench_tokens(tmp_path: Path) -> None:
    project = _project(
        profile="sentaurus-sdevice-r2020.09",
        entrypoint="device.cmd",
        content='File { Grid="@tdr@" Output="case.log" }\nSolve { Poisson }\n',
    )

    returncode, report = _run_skill_validator(tmp_path, project)
    assert returncode == 1
    assert "files.workbench_tokens" in {
        item["code"] for item in report["findings"]
    }
    with pytest.raises(ValidationError, match="unresolved Workbench tokens"):
        _validate_packager(project)


def test_skill_validator_rejects_output_that_overwrites_input(tmp_path: Path) -> None:
    project = _project(
        profile="sentaurus-sprocess-r2020.09",
        entrypoint="process.cmd",
        content="math coord.ucs\nexit\n",
    )
    project["expected_outputs"][0]["relative_path"] = "process.cmd"

    returncode, report = _run_skill_validator(tmp_path, project)
    assert returncode == 1
    assert "outputs.overwrite_input" in {
        item["code"] for item in report["findings"]
    }


def test_skill_package_metadata_is_valid() -> None:
    spec = importlib.util.spec_from_file_location("tcad_skill_validator", VALIDATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert callable(module.validate)
