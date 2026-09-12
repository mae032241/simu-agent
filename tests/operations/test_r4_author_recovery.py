"""Actual author snapshotter handoff across a temporarily unavailable contract."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.service.run_records import RunContractUnavailable
from scidiscovery.operations.catalog import compile_catalog
from test_l4_local_tcad import (
    CORE_PLUGIN, SCIENCE_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN,
    _system, _invoke, _debug_worker, _ImmediateDebugAdapter,
    _write_sprocess_workspace, _write_gap,
)


@pytest.mark.parametrize("entry", ("submit", "preview", "failure"))
def test_author_latest_source_and_declarations_survive_contract_gap(tmp_path: Path, entry: str):
    catalog, runtime, root, _ = _system(tmp_path, solver_kind="sprocess")
    inputs = [{"port": "execution_capability", "artifact_names": ["execution_capability"]},
              {"port": "experiment_plan", "artifact_names": ["experiment_plan"]}]
    operation_id = "tcad.deck.author.initial.v1"
    _invoke(root, "author_old", operation_id, inputs)
    opened = _debug_worker(catalog, runtime, _ImmediateDebugAdapter(), tmp_path / "unused").call_tool(
        "worker_open_assignment", {})
    workspace = Path(opened["workspace_path"])
    _write_sprocess_workspace(opened)
    _write_gap(opened)
    value = runtime.runs.list(instance_id=root.facade._instance_id())[0]
    runtime.runs.validate_candidate(value.run_id)  # Actual old finalizer creates preview A.
    old_output = (workspace / "output/result.json").read_bytes()
    source_b = "set case_smoke 2\nputs case_smoke\n"
    (workspace / "deck/files/main.cmd").write_text(source_b)
    declarations_path = workspace / "deck/declarations.json"
    declarations_b = json.loads(declarations_path.read_bytes())
    declarations_b["case_anchors"][0]["locator"] = "set case_smoke 2"
    declarations_path.write_bytes(canonical_json(declarations_b))
    operation = next(item for item in TCAD_PLUGIN.operations if item.operation_id == operation_id)
    changed = operation.model_copy(update={"limits": operation.limits.model_copy(
        update={"max_attempts": operation.limits.max_attempts + 1})})
    plugin = TCAD_PLUGIN.model_copy(update={"operations": tuple(
        changed if item.operation_id == operation_id else item for item in TCAD_PLUGIN.operations)})
    new_catalog = compile_catalog((CORE_PLUGIN, SCIENCE_PLUGIN, CURVE_PLUGIN, plugin))
    runtime.runs.operation_catalog = new_catalog
    if entry == "submit":
        assert runtime.runs.submit(value.run_id) == ("failed", ())
    elif entry == "preview":
        with pytest.raises(RunContractUnavailable):
            runtime.runs.validate_candidate(value.run_id)
    else:
        runtime.runs.fail(value.run_id, reason="Contract gap")
    assert (workspace / "deck/files/main.cmd").read_text() == source_b
    assert (workspace / "output/result.json").read_bytes() == old_output
    assert runtime.runs.recovery_status(runtime.runs.status(value.run_id))["recovery_pending"]
    # Restart-style repair remains pending without the old contract and preserves B.
    runtime.runs.record_failure(value.run_id, reason="Reconcile", expected_state="running",
                               expected_last_activity_at=None)
    assert (workspace / "deck/files/main.cmd").read_text() == source_b
    runtime.runs.operation_catalog = catalog
    recovered = runtime.runs.record_failure(value.run_id, reason="Original contract restored",
        expected_state="running", expected_last_activity_at=None)
    assert runtime.runs.recovery_status(recovered)["delivery_preserved"]
    assert not workspace.exists()
    runtime.runs.operation_catalog = new_catalog
    new_root = RootMCPRouter(RootToolFacade(runtime.artifacts, runtime.intake,
        runs=runtime.runs, approvals=runtime.approvals, executions=runtime.executions,
        bindings=runtime.scheduler_bindings, instance=value.instance_id,
        operation_catalog=new_catalog))
    new_root.call_tool("operation_invoke", {"name": "author_new", "operation_id": operation_id,
        "inputs": inputs, "instruction": "Revalidate recovered draft against new inputs.",
        "draft_from": "author_old"})
    worker = _debug_worker(new_catalog, runtime, _ImmediateDebugAdapter(), tmp_path / "unused-new")
    opened_new = worker.call_tool("worker_open_assignment", {})
    restored = Path(opened_new["workspace_path"])
    assert (restored / "deck/files/main.cmd").read_text() == source_b
    assert json.loads((restored / "deck/declarations.json").read_bytes()) == declarations_b
    # The new contract validates the limited implementation-gap result itself.
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
