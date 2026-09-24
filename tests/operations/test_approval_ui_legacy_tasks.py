"""Task-era trajectory and exact Ref display stay confined to the UI."""

from __future__ import annotations

import http.client
import os
import sqlite3
from urllib.parse import quote, urlencode, urlparse

import pytest

from scidiscovery.artifact_agent.approval_ui.app import ApprovalUI
from scidiscovery.artifact_agent.approval_ui.legacy_artifacts import UIReadableArtifactRegistry
from scidiscovery.artifact_agent.approval_ui.legacy_tasks import LegacyTaskReadError, LegacyTaskReader
from scidiscovery.artifact_agent.approval_ui.read_model import InstanceReadModel, ReadModelNotFound, ReadModelScopeError
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from tests.operations.test_approval_ui_legacy_artifacts import _legacy_envelope


def _request(base, method, path, *, form=None, cookie=None):
    url = urlparse(base)
    connection = http.client.HTTPConnection(url.hostname, url.port, timeout=5)
    headers = {"Cookie": cookie.split(";", 1)[0]} if cookie else {}
    if form is not None:
        headers.update({"Origin": base, "Content-Type": "application/x-www-form-urlencoded"})
    connection.request(method, path, body=None if form is None else urlencode(form), headers=headers)
    response = connection.getresponse()
    result = response.status, dict(response.getheaders()), response.read()
    connection.close()
    return result


@pytest.fixture
def legacy_system(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    state = tmp_path / "state"
    secret = os.urandom(32)
    runtime = open_runtime(project_root=project, state_root=state, approval_receipt_secret=secret)
    first = runtime.scheduler_bindings.create_instance(name="fig4_old", title="Fig.4 historical", objective="Administrative description")
    second = runtime.scheduler_bindings.create_instance(name="other", title="Other", objective="Other")
    goal = runtime.artifacts.register(canonical_json({"statement": "Original Fig.4 objective"}), ArtifactRegistration(
        kind="research_objective", schema_id="scidiscovery.research-objective.v1",
        payload_schema_version=1, media_type="application/json", creator=runtime.actor), idempotency_key="legacy-task:goal")
    instruction = runtime.artifacts.register(b"Frozen instruction", ArtifactRegistration(
        kind="task_instruction", schema_id="opaque", payload_schema_version=1,
        media_type="text/plain", creator=runtime.actor), idempotency_key="legacy-task:instruction")
    runtime.scheduler_bindings.bind(instance=first.instance_id, namespace="artifact", name="goal", object_id=goal.artifact_id)
    created_at = "2026-09-01T00:00:00Z"
    task_id = "tsk_legacy_fig4"
    payload = canonical_json({"schema_version": 1, "task_id": task_id, "role": "hypothesis_worker",
        "context_profile": "default", "instruction_ref": instruction.ref.model_dump(mode="json"),
        "inputs": [{"schema_version": 1, "name": "research_objective",
            "artifact_ref": goal.ref.model_dump(mode="json"), "exposure": "on_demand", "usage": "claim_evidence"}],
        "dependency_task_ids": [], "output": {}, "budget": {}, "created_at": created_at})
    current_task = runtime.artifacts.register(payload, ArtifactRegistration(
        kind="agent_task", schema_id="scidiscovery.agent-task", payload_schema_version=1,
        media_type="application/json", creator=runtime.actor,
        parent_refs=(instruction.ref, goal.ref)), idempotency_key="legacy-task:task")
    artifact_db = state / "database" / "artifact_agent.sqlite3"
    task = _legacy_envelope(artifact_db, current_task, confidentiality="task_private")
    current_output = runtime.artifacts.register(b"sealed result", ArtifactRegistration(
        kind="task_result", schema_id="test.legacy-result.v1", payload_schema_version=1,
        media_type="text/plain", creator=runtime.actor, parent_refs=(goal.ref,)),
        idempotency_key="legacy-task:output")
    output = _legacy_envelope(artifact_db, current_output, task_ref=task.ref, confidentiality="task_private")
    task_db = state / "database" / "tasks.sqlite3"
    with sqlite3.connect(task_db) as connection:
        connection.execute("CREATE TABLE tasks (task_id TEXT PRIMARY KEY, task_ref_json BLOB, role TEXT, state TEXT, "
            "attempt INTEGER, output_ref_json BLOB, created_at TEXT, last_activity_at TEXT)")
        connection.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?)",
            (task_id, task.ref.canonical_json(), "hypothesis_worker", "completed", 1,
                output.ref.canonical_json(), created_at, created_at))
    with sqlite3.connect(runtime.scheduler_bindings.database_path) as connection:
        connection.execute("INSERT INTO scheduler_bindings "
            "(instance,namespace,name,logical_name,revision,object_id,request_fingerprint,created_at) "
            "VALUES (?,?,?,?,?,?,?,?)", (first.instance_id, "task", "legacy_fig4", "legacy_fig4",
                1, task_id, None, created_at))
    runtime.artifacts.registry = UIReadableArtifactRegistry(artifact_db)
    reader = LegacyTaskReader(task_database_path=task_db,
        binding_database_path=runtime.scheduler_bindings.database_path, artifacts=runtime.artifacts)
    model = InstanceReadModel(artifacts=runtime.artifacts, bindings=runtime.scheduler_bindings,
        runs=runtime.runs, approvals=runtime.approvals, executions=runtime.executions,
        operation_catalog=runtime.operation_catalog, legacy_tasks=reader)
    return runtime, model, first, second, goal, task, output, secret, task_db


def test_legacy_task_trajectory_and_exact_goal_ref_render_through_ui(legacy_system):
    runtime, model, first, second, goal, task, output, secret, _ = legacy_system
    assert model.trajectory(first.instance_id)["total"] == 1
    assert model.trajectory(first.instance_id)["items"][0]["key"] == "task:legacy_fig4"
    node = model.node(first.instance_id, "task:legacy_fig4")
    assert node["objective_refs"][0]["ref"] == goal.ref.model_dump(mode="json")
    assert node["inputs"][0]["port_name"] == "research_objective"
    assert node["outputs"][0]["ref"] == output.ref.model_dump(mode="json")
    assert node["record"]["task_ref"] == task.ref.model_dump(mode="json")
    assert model.artifact(first.instance_id, output.artifact_id)["legacy_task_ref"] == task.ref.model_dump(mode="json")
    context = model.node_context(first.instance_id, "task:legacy_fig4")
    assert context["scope"] == "exact_legacy_task_output_only"
    assert [view["artifact_id"] for view in context["artifacts"]] == [output.artifact_id]
    with pytest.raises(ValueError, match="scheduler namespace is invalid"):
        runtime.scheduler_bindings.get_binding(instance=first.instance_id, namespace="task", name="legacy_fig4")
    with pytest.raises(ReadModelNotFound):
        model.node(second.instance_id, "task:legacy_fig4")
    with pytest.raises(ReadModelScopeError):
        model.artifact(second.instance_id, output.artifact_id)

    ui = ApprovalUI(runtime.approvals, bindings=runtime.scheduler_bindings,
        instance_management_secret=secret, read_model=model)
    base = ui.start()
    try:
        status, headers, _ = _request(base, "POST", "/instances/access", form={
            "csrf": ui.session_id, "instance_id": first.instance_id, "scope": "read"})
        assert status == 303
        cookie = headers["Set-Cookie"]
        status, _, page = _request(base, "GET", f"/instance/{first.instance_id}", cookie=cookie)
        assert status == 200 and b"task%3Alegacy_fig4" in page
        status, _, page = _request(base, "GET", f"/instance/{first.instance_id}/nodes/"
            + quote("task:legacy_fig4", safe=""), cookie=cookie)
        assert status == 200
        html = page.decode()
        assert "Original Fig.4 objective" in html
        assert "历史任务" in html and "research_objective" in html
        assert output.artifact_id in html and goal.artifact_id in html
        assert "Frozen instruction" not in html
    finally:
        ui.stop()


def test_legacy_task_reader_rejects_output_not_bound_to_exact_task(legacy_system):
    runtime, model, first, _, goal, _, _, _, task_db = legacy_system
    with sqlite3.connect(task_db) as connection:
        connection.execute("UPDATE tasks SET output_ref_json=?", (goal.ref.canonical_json(),))
    with pytest.raises(LegacyTaskReadError, match="inconsistent"):
        model.legacy_tasks.read("tsk_legacy_fig4")
    node = model.node(first.instance_id, "task:legacy_fig4")
    assert node["state"] == "unknown" and node["gaps"]
    assert not node.get("objective_refs")


def test_missing_legacy_database_does_not_break_other_ui_nodes(legacy_system):
    runtime, _, first, _, goal, _, _, _, _ = legacy_system
    model = InstanceReadModel(artifacts=runtime.artifacts, bindings=runtime.scheduler_bindings,
        runs=runtime.runs, approvals=runtime.approvals, executions=runtime.executions,
        operation_catalog=runtime.operation_catalog)
    nodes = model.nodes(first.instance_id)["items"]
    task = next(item for item in nodes if item["kind"] == "task")
    assert task["gaps"][0]["code"] == "legacy_task_record_unavailable"
    assert model.artifact(first.instance_id, goal.artifact_id)["artifact_id"] == goal.artifact_id
