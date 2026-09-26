"""User originals remain visible through exact assignment and bounded analysis views."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from tests.operations.test_tcad_result_analysis import (
    analysis_report, analysis_system, open_analysis, write_analysis,
)


USER_TEXT = "  用户补充：请结合原任务评估这项建议。\r\n保留适用范围与不确定性。𐀀\n "


def _context_entry(opened, *, origin):
    assignment_raw = Path(opened["assignment_path"]).read_bytes()
    assignment = json.loads(assignment_raw)
    item, = [item for item in assignment["inputs"] if item["port"] == "user_context"]
    expected_keys = {"source_name", "artifact_name", "artifact_name_usage", "port",
        "description", "relative_path", "media_type", "reference_availability",
        "usage", "exposure", "historical"}
    if origin is not None:
        expected_keys.add("source_origin")
        assert item["source_origin"] == origin
    assert set(item) == expected_keys
    assert item["artifact_name_usage"] == "navigation_only"
    assert item["reference_availability"] == "unknown"
    assert item["usage"] == "prior_signal" and item["exposure"] == "on_demand"
    assert b"private-label-marker" not in assignment_raw
    original = Path(opened["workspace_path"], item["relative_path"]).read_bytes()
    assert original not in assignment_raw
    if "start_here_path" in opened:
        start_raw = Path(opened["start_here_path"]).read_bytes()
        start = json.loads(start_raw)
        indexed, = [entry for entry in start["inputs"] if entry["port"] == "user_context"]
        assert indexed["relative_path"] == item["relative_path"]
        assert indexed["source_name"] == item["source_name"]
        assert indexed["artifact_name"] == item["artifact_name"]
        assert indexed["artifact_name_usage"] == "navigation_only"
        assert indexed["media_type"] == item["media_type"]
        assert indexed["size_bytes"] == len(original)
        assert indexed["schema_id"] == "opaque"
        if origin is None:
            assert "source_origin" not in indexed
        else:
            assert indexed["source_origin"] == origin
        assert not any(entry["source_name"] == item["source_name"] for entry in start["excerpts"])
        assert original not in start_raw
    return assignment, original


@pytest.mark.parametrize("reuse_worker", [False, True])
def test_new_and_reused_local_workers_open_new_context_assignment(tmp_path, reuse_worker):
    system = analysis_system(tmp_path)
    catalog, runtime, root, request, _, _ = system
    # Old records without the new marker, or with another origin, are not relabeled
    # merely because the scheduler binds them through user_context.
    labels = {"private_annotation": "private-label-marker"}
    if reuse_worker:
        labels["source_origin"] = "fixture_import"
    legacy_text = "旧补充原文：仅作为本轮背景。\n".encode()
    legacy = runtime.artifacts.register(legacy_text, ArtifactRegistration(
        kind="source_text", schema_id="opaque", payload_schema_version=1,
        media_type="text/plain", creator=runtime.actor, labels=labels),
        idempotency_key="legacy_context")
    runtime.scheduler_bindings.bind(instance=root.facade.instance, namespace="artifact",
        name="legacy_context", object_id=legacy.artifact_id)
    request["inputs"].append(dict(port="user_context", artifact_names=["legacy_context"]))
    worker, opened = open_analysis(system)
    _, original = _context_entry(opened, origin=None)
    assert original == legacy_text
    old_assignment = Path(opened["assignment_path"]).read_bytes()
    write_analysis(opened, analysis_report())
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    old_status = root.call_tool("run_status", {'name': "analysis", "intent": 'full'})

    registered = root.call_tool("artifact_ingest_text", dict(name="supplement", text=USER_TEXT))
    following = deepcopy(request)
    following["name"] = "analysis_with_supplement"
    next(item for item in following["inputs"] if item["port"] == "user_context")[
        "artifact_names"] = [registered["name"]]
    following["inputs"].append(dict(port="current_progress",
        artifact_names=[old_status["output_artifact_name"]]))
    checked = root.call_tool("operation_preflight", following)
    assert checked["admissible"], checked
    root.call_tool("operation_invoke", following)
    if not reuse_worker:
        compiled = catalog.operation(following["operation_id"])
        worker = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id,
            operation_digest=compiled.digest)
    new_opened = worker.call_tool("worker_open_assignment", {})
    assert new_opened["assignment_path"] != opened["assignment_path"]
    _, original = _context_entry(new_opened, origin="user_via_scheduler")
    assert original == USER_TEXT.encode("utf-8")
    assert Path(opened["assignment_path"]).read_bytes() == old_assignment
    assert runtime.artifacts.read(legacy.ref) == legacy_text
    write_analysis(new_opened, analysis_report())
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    assert root.call_tool("run_status", {'name': "analysis", "intent": 'full'})["sealed_output"] == old_status["sealed_output"]


def test_hardened_assignment_preserves_user_context_original(tmp_path):
    from blind_csv_plugin.plugin import PLUGIN as BLIND
    from scidiscovery.artifact_agent.interfaces.mcp_hardened_worker import HardenedWorkerMCPRouter
    from tests.operations.test_l5_hardened_run_backend import _system

    # The existing MCP-only fixture isolates assignment transport; production TCAD
    # analysis still requires its declared native and collection capabilities.
    author, reviewer = BLIND.operations
    transport = BLIND.model_copy(update={"operations": (
        author.model_copy(update={"review": None}), reviewer)})
    catalog, runtime, _, root = _system(tmp_path, blind_plugin=transport)
    registered = root.call_tool("artifact_ingest_text", dict(name="supplement", text=USER_TEXT))
    request = dict(name="context_transport", operation_id="blind.csv.observe.v1",
        instruction="Read the exact bound originals.", inputs=[
            dict(port="source_table", artifact_names=["source_csv"]),
            dict(port="user_context", artifact_names=[registered["name"]])])
    checked = root.call_tool("operation_preflight", request)
    assert checked["admissible"], checked
    root.call_tool("operation_invoke", request)
    compiled = catalog.operation(request["operation_id"])
    worker = HardenedWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest)
    opened = worker.call_tool("worker_open_assignment", {})
    assert opened["write_protocol"] == "server_file_tools"
    assignment, original = _context_entry(opened, origin="user_via_scheduler")
    assert original == USER_TEXT.encode("utf-8")
    assert set(assignment["tools"]) == {tool["name"] for tool in worker.list_tools()}
    # This fixture covers Hardened assignment and original-file readability only.
    # Its existing general finalizer has no matching file-write policy, so result
    # submission remains outside this test; the Local cases above cover submission.


def test_full_analysis_index_keeps_original_context_reachable(tmp_path):
    from curve_score.analysis_workspace import _start_file
    from scidiscovery.operations.workspace import WorkspaceMaterializationRequest

    (tmp_path / "inputs").mkdir()
    inputs, paths = [], {}
    # Fill the existing 12 KiB TCAD start-view allowance before the final context.
    for index in range(40):
        alias = f"solver_outputs_{index:03}_" + "x" * 96
        relative = f"inputs/{alias}.txt"
        paths[alias] = tmp_path / relative
        paths[alias].write_bytes(b"fixture raw output\n")
        inputs.append(dict(source_name=alias, port="solver_outputs", relative_path=relative,
            media_type="text/plain", exposure="on_demand", usage="evidence_inventory"))
    original = ("𐀀" * 8192).encode("utf-8")
    context_alias = "user_context_" + "y" * 110
    context_relative = f"inputs/{context_alias}.txt"
    paths[context_alias] = tmp_path / context_relative
    paths[context_alias].write_bytes(original)
    inputs.append(dict(source_name=context_alias, port="user_context",
        relative_path=context_relative, media_type="text/plain; charset=utf-8",
        source_origin="user_via_scheduler", exposure="on_demand", usage="prior_signal"))
    (tmp_path / "assignment.json").write_bytes(canonical_json(dict(inputs=inputs, tools=[])))
    request = WorkspaceMaterializationRequest("fixture", tmp_path, paths, ())
    _start_file(request, {"restored": [], "copy_omissions": []}, limit=12 * 1024)
    raw = (tmp_path / "analysis-start.json").read_bytes()
    start = json.loads(raw)
    assert len(raw) <= 12 * 1024 and start["omitted"] > 0
    assert not any(item["port"] == "user_context" for item in start["inputs"])
    navigation = start["omission_source"]
    assert navigation == {"relative_path": start["full_assignment"], "pointer": "/inputs"}
    full = json.loads((tmp_path / navigation["relative_path"]).read_bytes())
    entry, = [item for item in full["inputs"] if item["port"] == "user_context"]
    assert entry["source_origin"] == "user_via_scheduler"
    assert (tmp_path / entry["relative_path"]).read_bytes() == original
    assert not start["excerpts"] and original not in raw
