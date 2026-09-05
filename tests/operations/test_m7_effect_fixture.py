from __future__ import annotations


def test_installed_m7_effect_uses_its_compiled_runtime_factory(installed_probe) -> None:
    installed_probe(
        "m7_effect",
        r'''
import hashlib
import json
import tempfile
from pathlib import Path

from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.runtime_plugin_bindings import (
    load_runtime_plugin_contributions,
)
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.operations.invoke import effect_operation_plan

with tempfile.TemporaryDirectory() as raw_root:
    root = Path(raw_root)
    project = root / "project"
    state = root / "state"
    project.mkdir()
    state.mkdir()
    frozen = root / "frozen.txt"
    frozen.write_bytes(b"m7 effect\n")
    config = root / "config.json"
    config.write_text(
        json.dumps(
            {
                "frozen_output_path": str(frozen),
                "frozen_output_sha256": hashlib.sha256(frozen.read_bytes()).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    catalog = compile_installed_catalog()
    runtime = open_runtime(
        project_root=project,
        state_root=state,
        approval_receipt_secret=b"m" * 32,
    )
    assert runtime.runs.operation_catalog.digest() == catalog.digest()
    assert catalog.runtime_plugin_ids() == ("m7_effect_fixture",)
    operation = catalog.operation("m7.fixture.frozen-copy.v1")
    assert operation.spec.catalog_scope == "public"
    assert operation.spec.executor.kind == "effect"
    assert effect_operation_plan(operation).executor == "m7_effect_fixture:adapter"
    loaded = load_runtime_plugin_contributions(
        catalog,
        {"m7_effect_fixture": config},
        mode="control",
        state_root=state,
    )
    assert tuple(loaded.execution_adapters) == ("m7_effect_fixture:adapter",)
''',
    )
