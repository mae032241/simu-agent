"""Real Worker receipts and execution approvals become read-only UI children."""
import json
from urllib.parse import quote

import pytest

from scidiscovery.artifact_agent.approval_ui.read_model import InstanceReadModel
from scidiscovery.artifact_agent.approval_ui.experiment_trajectory import parent_binding, read_children
from tests.operations.test_experiment_approval_handoff import experiment, start


def model_for(f):
    return InstanceReadModel(artifacts=f.runtime.artifacts, bindings=f.runtime.scheduler_bindings,
        runs=f.runs, approvals=f.runtime.approvals, executions=f.runtime.executions,
        operation_catalog=f.catalog, execution_collection=f.coordinator.collection)


@pytest.mark.process_e2e
def test_browser_script_refresh_preserves_history_and_escapes_copy():
    from pathlib import Path
    from shutil import which
    from scidiscovery.plugin_runtime.collection import run_bounded
    node = which("node")
    if node is None:
        pytest.skip("Node.js is required for the DOM transport fixture")
    root = Path(__file__).resolve().parents[2]
    result = run_bounded([node, "--max-old-space-size=128", "--v8-pool-size=1",
        str(root / "tests/fixtures/workbench_progress.mjs"),
        str(root / "src/scidiscovery/artifact_agent/approval_ui/static/workbench.js")],
        input=b"", timeout=10, max_output_bytes=8192)
    assert result.returncode == 0, result.stderr.decode()
    assert b"workbench progress refresh passed" in result.stdout


def test_stage_versions_and_pending_approval_are_children_without_payload_or_solver_reads(tmp_path, monkeypatch):
    f = experiment(tmp_path, monkeypatch)
    first = f.worker.call_tool("worker_experiment_stage", {"stage": "design", "conclusion": "Compare the frozen targets."})
    second = f.worker.call_tool("worker_experiment_stage", {"stage": "design", "conclusion": "Retain an unresolved boundary."})
    request = start(f)
    assert request["state"] == "awaiting_authorization"
    model = model_for(f)
    monkeypatch.setattr(f.runtime.artifacts, "read", lambda *_: pytest.fail("metadata read a scientific payload"))
    monkeypatch.setattr(f.adapter, "status", lambda *_: pytest.fail("UI polled the solver"))
    node = model.node_metadata(f.instance.instance_id, "run:continuation")
    children = node["experiment_children"]
    stages = {i["reference"]: i for i in children["items"] if i["kind"] == "stage"}
    assert stages[first["reference"]]["version"] == 1
    assert stages[second["reference"]]["version"] == 2
    assert children["pending_approvals"] == 1 and not children["gaps"]
    approvals = [i for i in children["items"] if i["kind"] == "approval"]
    assert approvals[0]["key"] == "approval:" + request["approval_name"]
    assert approvals[0]["parent_key"] == "run:continuation" and approvals[0]["state"] == "pending"
    roots = model.trajectory(f.instance.instance_id)["items"]
    assert sum(n["key"] == "run:continuation" for n in roots) == 1
    assert not any(n["kind"] in {"execution", "approval"} for n in roots)
    assert f.adapter.submits == 0


def test_child_pagination_keeps_every_version_and_never_groups_by_approval_name(tmp_path, monkeypatch):
    f = experiment(tmp_path, monkeypatch)
    for version in range(10):
        f.worker.call_tool("worker_experiment_stage", {"stage": "design", "conclusion": f"Design revision {version}."})
    request = start(f)
    model = model_for(f)
    run = f.runs.status(f.run_id)
    all_items, offset = [], 0
    while True:
        page = read_children(model, run, offset=offset, limit=4)
        assert not page["gaps"] and len(page["items"]) <= 4
        all_items.extend(page["items"])
        if page["next_offset"] is None:
            break
        assert page["next_offset"] > offset
        offset = page["next_offset"]
    assert len(all_items) == page["total"]
    versions = [i["version"] for i in all_items if i.get("title") == "实验方案结论"]
    assert sorted(versions) == list(range(1, 11))
    with pytest.raises(ValueError):
        read_children(model, run, offset=-1)
    bindings = f.runtime.scheduler_bindings
    original = bindings.get_binding(instance=f.instance.instance_id, namespace="approval", name=request["approval_name"])
    foreign = bindings.create_instance(name="foreign", title="Foreign", objective="Unrelated")
    copy = bindings.bind(instance=foreign.instance_id, namespace="approval", name=request["approval_name"], object_id=original.object_id)
    assert parent_binding(model, foreign.instance_id, copy) is None
    assert parent_binding(model, f.instance.instance_id, original).object_id == f.run_id


def test_recovery_shows_original_execution_and_approval_without_reparenting_them(tmp_path, monkeypatch):
    f = experiment(tmp_path, monkeypatch)
    request = start(f)
    value = f.runs.status(f.run_id)
    f.runs.record_failure(f.run_id, reason="owner interrupted", expected_state="running",
        expected_last_activity_at=value.last_activity_at)
    recovered = f.root.call_tool("operation_invoke", {**f.invocation, "name": "recovered", "draft_from": "continuation"})
    assert recovered["result"]["state"] == "queued"
    model = model_for(f)
    monkeypatch.setattr(f.runtime.artifacts, "read", lambda *_: pytest.fail("recovery metadata read a payload"))
    node = model.node_metadata(f.instance.instance_id, "run:recovered")
    assert node["state"] == "queued"
    children = node["experiment_children"]
    assert children["pending_approvals"] == 1 and not children["gaps"]
    approval = next(i for i in children["items"] if i["kind"] == "approval")
    assert approval["key"] == "approval:" + request["approval_name"]
    assert approval["parent_key"] == "run:continuation"
    assert node["experiment_progress"]["execution_count"] == 1
    assert f.adapter.submits == 0


@pytest.mark.process_e2e
def test_ui_metadata_route_retains_browser_scope_and_does_not_read_scientific_payloads(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.approval_ui.app import ApprovalUI
    from scidiscovery.artifact_agent.approval_ui.access import access_cookie
    from tests.operations.test_instance_browser_http import _request
    f = experiment(tmp_path, monkeypatch)
    start(f)
    ui = ApprovalUI(f.runtime.approvals, bindings=f.runtime.scheduler_bindings,
        read_model=model_for(f), instance_management_secret=b"ui-test-secret" * 4)
    base = ui.start()
    instance = f.instance.instance_id
    cookie = access_cookie(instance, ui.browser_access.issue(instance))
    endpoint = f"/api/instances/{instance}/nodes/{quote('run:continuation', safe='')}?view=metadata"
    try:
        assert _request(base, "GET", endpoint)[0] == 403
        status, _, body = _request(base, "GET", f"/instance/{instance}?node=run%3Acontinuation", cookie=cookie)
        assert status == 200
        assert "阶段、审批与执行" in body.decode() and "待处理审批" in body.decode()
        monkeypatch.setattr(f.runtime.artifacts, "read", lambda *_: pytest.fail("metadata route read scientific payload"))
        status, _, raw = _request(base, "GET", endpoint, cookie=cookie)
        assert status == 200
        node = json.loads(raw)
        assert node["experiment_children"]["pending_approvals"] == 1
        assert "sealed_output" not in node and "record" not in node
    finally:
        ui.stop()
