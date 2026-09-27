"""Exercise draft routing through the existing Root and local Worker surfaces."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_root import OperationCallInput, RootToolError
from tests.operations.test_l2_run_invariants import _envelope, _invoke, _system, _worker


def _request(name: str, **extra):
    return {
        "name": name,
        "operation_id": "blind.csv.observe.v1",
        "inputs": [{"port": "source_table", "artifact_names": ["source_csv"]}],
        "instruction": "Make one bounded observation.",
        **extra,
    }


def _failed_source(catalog, runtime, root):
    _invoke(root, "draft_source")
    opened = _worker(catalog, runtime).call_tool("worker_open_assignment", {})
    Path(opened["output_directory"], "result.json").write_bytes(
        _envelope("PRIVATE_UNACCEPTED_DRAFT")
    )
    status = root.call_tool("run_status", {"name": "draft_source"})
    return root.call_tool("run_record_failure", {
        "name": "draft_source", "reason": "agent exited",
        "expected_state": "running",
        "expected_last_activity_at": status["last_activity_at"],
    })


def test_root_draft_source_handoff_is_not_scientific_output(tmp_path):
    catalog, runtime, _, _, root = _system(tmp_path)
    status = _failed_source(catalog, runtime, root)
    assert status["sealed_output"] is None
    assert status["recovery"]["delivery_preserved"]
    assert status["recovery"]["draft_available"]
    assert "PRIVATE_UNACCEPTED_DRAFT" not in json.dumps(status)
    assert "PRIVATE_UNACCEPTED_DRAFT" not in json.dumps(root.call_tool("run_list", {}))
    request = _request("draft_successor", draft_from="draft_source")
    assert root.call_tool("operation_preflight", request)["admissible"]
    result = root.call_tool("operation_invoke", request)["result"]
    assert result["draft_from"] == "draft_source"
    assert result["sealed_output"] is None
    opened = _worker(catalog, runtime).call_tool("worker_open_assignment", {})
    assignment = json.loads(Path(opened["assignment_path"]).read_text())
    assert assignment["recovery_draft"]["scientific_evidence"] is False
    assert "PRIVATE_UNACCEPTED_DRAFT" in Path(
        opened["workspace_path"], "recovery-draft/result.json"
    ).read_text()


@pytest.mark.parametrize("extra, reason", [
    ({"draft_from": "missing", "resume_from": "missing"}, "recovery_sources_mutually_exclusive"),
    ({"draft_from": "missing"}, "draft_source_unavailable"),
])
def test_root_draft_rejection_creates_no_run(tmp_path, extra, reason):
    _, _, _, _, root = _system(tmp_path)
    request = _request("rejected_draft", **extra)
    assert root.call_tool("operation_preflight", request)["reason_code"] == reason
    with pytest.raises(RootToolError, match=reason):
        root.call_tool("operation_invoke", request)
    assert root.call_tool("run_list", {}) == {"runs": []}


def test_root_draft_fingerprint_binds_controlled_digest(tmp_path, monkeypatch):
    catalog, runtime, _, _, root = _system(tmp_path)
    _failed_source(catalog, runtime, root)
    request = OperationCallInput.model_validate(_request("new_run", draft_from="draft_source"))
    values = request.model_dump()
    values["inputs"] = request.inputs
    bound = root.facade._prepare_operation_call(**values)
    first = root.facade._prepare_local_run(
        bound, "reject", resume_from=None, draft_from="draft_source"
    )
    monkeypatch.setattr(runtime.runs, "validate_draft_source", lambda *a, **kw: "f" * 64)
    second = root.facade._prepare_local_run(
        bound, "reject", resume_from=None, draft_from="draft_source"
    )
    assert first[0:2] == second[0:2]
    assert first[2] != second[2]
    assert first[3] != second[3]


def test_root_draft_rejects_foreign_instance_even_with_local_alias(tmp_path):
    catalog, runtime, instance, _, root = _system(tmp_path)
    _failed_source(catalog, runtime, root)
    source_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id, namespace="run", name="draft_source"
    )
    other = runtime.scheduler_bindings.create_instance(
        name="other_instance", title="Other instance", objective="Isolation test"
    )
    source_artifact_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id, namespace="artifact", name="source_csv"
    )
    runtime.scheduler_bindings.bind(
        instance=other.instance_id, namespace="artifact", name="source_csv",
        object_id=source_artifact_id,
    )
    runtime.scheduler_bindings.bind(
        instance=other.instance_id, namespace="run", name="foreign_source",
        object_id=source_id,
    )
    root.facade.instance = other.instance_id
    request = _request("foreign_successor", draft_from="foreign_source")
    assert root.call_tool("operation_preflight", request)["reason_code"] == "draft_source_unavailable"
    with pytest.raises(RootToolError, match="draft_source_unavailable"):
        root.call_tool("operation_invoke", request)
    with pytest.raises(Exception, match="unknown run name"):
        runtime.scheduler_bindings.resolve(
            instance=other.instance_id, namespace="run", name="foreign_successor"
        )
