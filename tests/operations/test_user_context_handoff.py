"""User originals remain visible through exact assignment and bounded analysis views."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json


USER_TEXT = "  用户补充：请结合原任务评估这项建议。\r\n保留适用范围与不确定性。𐀀\n "


def _context_entry(opened, *, origin):
    assignment_raw = Path(opened["assignment_path"]).read_bytes()
    assignment = json.loads(assignment_raw)
    item, = [item for item in assignment["inputs"] if item["source_name"] == "user_context"]
    expected_keys = {"source_name", "artifact_name", "artifact_name_usage",
        "description", "relative_path", "media_type", "reference_availability",
        "usage", "exposure", "historical", "size_bytes", "schema_id"}
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
        indexed, = [entry for entry in start["inputs"] if entry["source_name"] == "user_context"]
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
        if "workspace" in start:
            assert not any(entry["source_name"] == item["source_name"] for entry in json.loads((Path(opened["workspace_path"]) / start["workspace"]["paths"]["analysis_navigation"]).read_bytes())["excerpts"])
        assert original not in start_raw
    return assignment, original


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
    assert not any(item["source_name"] == context_alias for item in start["inputs"])
    navigation = start["omission_source"]
    assert navigation == {"relative_path": "assignment.json", "pointer": "/inputs"}
    full = json.loads((tmp_path / navigation["relative_path"]).read_bytes())
    entry, = [item for item in full["inputs"] if item["source_name"] == context_alias]
    assert entry["source_origin"] == "user_via_scheduler"
    assert (tmp_path / entry["relative_path"]).read_bytes() == original
    assert not start["excerpts"] and original not in raw
