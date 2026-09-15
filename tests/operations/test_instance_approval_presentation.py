from urllib.parse import urlencode

from scidiscovery.artifact_agent.approval_ui.app import ApprovalUI
from scidiscovery.artifact_agent.approval_ui.access import access_cookie
from scidiscovery.artifact_agent.approval_ui.trajectory import TrajectoryStore
from scidiscovery.artifact_agent.approval_ui.presentation import build_presentation
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from tests.operations.test_instance_read_model import system, approval
from tests.operations.test_instance_presentations import installed
from tests.operations.test_instance_browser_http import _request
from tests.operations.test_m2_parameter_package import _package


def register(system, key, schema, payload, parents=()):
    return system.artifacts.register(canonical_json(payload), ArtifactRegistration(
        kind="fixture", schema_id=schema, payload_schema_version=1, media_type="application/json",
        creator=system.actor, parent_refs=parents), idempotency_key=key)


def test_large_execution_package_keeps_original_goal_current_targets_and_exact_parameters(system, installed):
    goal = register(system, "goal", "scidiscovery.research-objective.v1", {"statement": "Frozen original goal"})
    plan = register(system, "plan", "scidiscovery.experiment-portfolio.v1", {
        "objective": "Frozen original goal", "proposals": [{
            "experiment_key": "one", "implementation_notes": "irrelevant protocol detail " * 8000,
            "objectives": ["depth", "shape", "later validation"], "current_objectives": ["depth", "shape"],
            "comparison_contract": {"variables": [{"variable_key": "temperature", "scientific_path": "device.temperature",
                "unit": "K", "expectations": [{"case_key": "control", "value": 300}]}]}}]}, (goal.ref,))
    package = register(system, "package", "tcad.reviewed-deck-package.v2", {"project": {
        "entrypoint": "process.cmd", "files": [{"content": "source code " * 15000}],
        "parameter_bindings": [{"name": "temperature", "declared_value": "300", "unit": "K", "evidence_class": "assumption"}],
        "resource_limits": {"wall_time_seconds": 60}},
        "review": {"summary": "Independent review of this exact package", "verdict": "pass"}}, (plan.ref,))
    launch = approval(system, "execute", (package.ref,))
    review = system.approvals.review(launch.approval_id, access_token=launch.access_token)
    context = system.model.approval_context(system.a, review, presentation=True)
    result = build_presentation(tuple(context["artifacts"]))
    assert "irrelevant protocol detail" not in str(result) and "source code" not in str(result)
    facts = [item for section in result["sections"] for item in section["items"]]
    current = next(item for item in facts if item["source"]["json_pointer"] == "/proposals/0/current_objectives")
    assert current["value"] == ["depth", "shape"]
    assert any(item["source"]["artifact_id"] == goal.artifact_id and item["value"] == "Frozen original goal" for item in facts)
    assert len(result["parameters"]) == 2
    ui = ApprovalUI(system.approvals, bindings=system.bindings, read_model=system.model,
                    instance_management_secret=b"s" * 32)
    base = ui.start()
    try:
        path = f"/review/{launch.approval_id}?" + urlencode({"token": launch.access_token})
        status, _, body = _request(base, "GET", path)
        assert status == 200 and len(body) <= 256 * 1024
        assert "Frozen original goal" in body.decode() and "本轮目标" in body.decode()
        assert "Independent review of this exact package" in body.decode()
        request_path = f"/request/{launch.approval_id}?" + urlencode({"token": launch.access_token})
        assert _request(base, "GET", request_path)[2] == system.artifacts.read(review.request_ref)
        assert system.approvals.status(launch.approval_id).status == "pending"
    finally:
        ui.stop()


def test_real_parameter_package_structure_renders_selected_value_source_and_unknowns(system, installed, tmp_path):
    values = _package().model_dump(mode="json")
    schemas = {"device_parameters": "scidiscovery.device-parameter-set.v1",
               "parameter_requirements": "scidiscovery.device-parameter-requirements.v1",
               "source_catalog": "scidiscovery.evidence-source-catalog.v1"}
    catalog = register(system, "source_catalog", schemas["source_catalog"], values["source_catalog"])
    requirements = register(system, "parameter_requirements", schemas["parameter_requirements"], values["parameter_requirements"])
    parameters = register(system, "device_parameters", schemas["device_parameters"], values["device_parameters"],
                          parents=(catalog.ref, requirements.ref))
    records = [parameters, requirements, catalog]
    launch = approval(system, "parameters", tuple(record.ref for record in records))
    ui = ApprovalUI(system.approvals, bindings=system.bindings, read_model=system.model,
                    instance_management_secret=b"s" * 32,
                    trajectory_store=TrajectoryStore(tmp_path / "ui" / "workbench.sqlite3"))
    base = ui.start()
    try:
        path = f"/review/{launch.approval_id}?" + urlencode({"token": launch.access_token})
        status, _, body = _request(base, "GET", path)
        text = body.decode()
        assert status == 200 and "Scale" in text and "1e+0" in text
        assert "Frozen source A" in text and "source_a:line-1" in text
        assert "未提供估计" in text and "网络检索" not in text
        assert "Use the exact frozen declaration." in text
        assert "实例管理描述" in text
        cookie = access_cookie(system.a, ui.browser_access.issue(instance_id=system.a))
        node_path = f"/instance/{system.a}/nodes/approval%3Aparameters"
        assert _request(base, "GET", node_path)[0] == 403
        status, _, node_body = _request(base, "GET", node_path, cookie=cookie)
        assert status == 200 and "Scale" in node_body.decode()
        assert "Frozen source A" in node_body.decode()
        assert _request(base, "GET", f"/instance/{system.a}", cookie=cookie)[0] == 200
        assert ui.trajectory_store.observations(system.a)["items"]
        assert system.approvals.status(launch.approval_id).status == "pending"
    finally:
        ui.stop()
