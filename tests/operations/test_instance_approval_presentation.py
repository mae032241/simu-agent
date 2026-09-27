import re
from urllib.parse import urlencode

from scidiscovery.artifact_agent.approval_ui.app import ApprovalUI
from scidiscovery.artifact_agent.approval_ui.access import access_cookie
from scidiscovery.artifact_agent.approval_ui.trajectory import TrajectoryStore
from scidiscovery.artifact_agent.approval_ui.presentation import build_presentation
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.layered_diagnosis import LayeredDiagnosisReport
from tests.operations.test_instance_read_model import system, approval, bind, run
from tests.operations.test_instance_presentations import installed
from tests.operations.test_instance_browser_http import _request
from tests.operations.test_instance_evidence import picture
from tests.operations.test_m2_parameter_package import _package


def register(system, key, schema, payload=None, parents=(), *, raw=None, media="application/json", labels=None):
    return system.artifacts.register(canonical_json(payload) if raw is None else raw, ArtifactRegistration(
        kind="fixture", schema_id=schema, payload_schema_version=1, media_type=media,
        creator=system.actor, parent_refs=parents, labels=labels or {}), idempotency_key=key)


def test_legal_diagnosis_fields_render_escaped_without_route_badges_in_three_http_entries(system, installed):
    payload = LayeredDiagnosisReport.model_validate_json(canonical_json({
        "study_kind": "scientific",
        "experiment_key": "implementation_check",
        "plan_key": "validate_implementation",
        "summary": "HTTP_DECISION_SUMMARY",
        "evidence": [{"source_key": "bounded_result", "source_type": "runtime_output",
                      "title": "Exact bounded result", "locator": "bounded_result"}],
        "overall_verdict": "inconclusive",
        "claim_allowed": False,
        "objective_assessment": {"objective_key": "objective_implementation", "status": "fail",
            "summary": "HTTP_OBJECTIVE_FAIL", "evidence_keys": ["bounded_result"]},
        "hypothesis_assessments": [{"hypothesis_key": "hypothesis_implementation",
            "outcome": "inconclusive", "rationale": "HTTP_HYPOTHESIS_UNRESOLVED",
            "evidence_keys": ["bounded_result"]}],
        "limitations": ["HTTP_LIMITATION_BOUND"],
        "remaining_contradiction": "HTTP_CONTRADICTION_REMAINS",
        "next_action": "HTTP_UNTRUSTED_NEXT <script>alert('route')</script>",
    })).model_dump(mode="json")
    report = register(system, "legal-http-diagnosis", "scidiscovery.layered-diagnosis.v1", payload)
    bind(system, system.a, "artifact", "analysis-report", report.artifact_id)
    run(system, "analysis", output=report.ref)
    launch = approval(system, "analysis-review", (report.ref,))
    ui = ApprovalUI(system.approvals, bindings=system.bindings, read_model=system.model,
                    instance_management_secret=b"s" * 32)
    base = ui.start()
    try:
        cookie = access_cookie(system.a, ui.browser_access.issue(instance_id=system.a))
        routes = (
            (f"/instance/{system.a}/nodes/run%3Aanalysis", cookie),
            (f"/instance/{system.a}/nodes/artifact%3Aanalysis-report", cookie),
            (f"/review/{launch.approval_id}?" + urlencode({"token": launch.access_token}), None),
        )
        for path, route_cookie in routes:
            status, _, body = _request(base, "GET", path, cookie=route_cookie)
            text = body.decode()
            assert status == 200
            for original in ("HTTP_DECISION_SUMMARY", "inconclusive", "objective_implementation",
                             "HTTP_OBJECTIVE_FAIL", "hypothesis_implementation",
                             "HTTP_HYPOTHESIS_UNRESOLVED", "HTTP_LIMITATION_BOUND",
                             "HTTP_CONTRADICTION_REMAINS", "HTTP_UNTRUSTED_NEXT"):
                assert original in text
            assert "<script>alert('route')</script>" not in text
            assert "&lt;script&gt;alert" in text
            assert "prune" not in text.lower()
            assert "剪枝" not in text
    finally:
        ui.stop()


def test_large_execution_package_keeps_original_goal_current_targets_and_exact_parameters(system, installed):
    goal = register(system, "goal", "scidiscovery.research-objective.v1", {"statement": "Frozen original goal"})
    plan = register(system, "plan", "scidiscovery.experiment-portfolio.v1", {
        "objective": "Frozen original goal", "proposals": [{
            "experiment_key": "one", "implementation_notes": "irrelevant protocol detail " * 8000,
            "objectives": ["depth", "shape", "later validation"], "current_objectives": ["depth", "shape"],
            "comparison_contract": {"variables": [{"variable_key": "temperature", "scientific_path": "device.temperature",
                "unit": "K", "expectations": [{"case_key": "control", "value": 300}]}]}}]}, (goal.ref,))
    package = register(system, "package", "tcad.execution-package.v2", {"project": {
        "entrypoint": "process.cmd", "files": [{"content": "source code " * 15000}],
        "parameter_bindings": [{"name": "temperature", "declared_value": "300", "unit": "K", "evidence_class": "assumption"}],
        "resource_limits": {"wall_time_seconds": 60}},
        "review": {"summary": "Independent review of this exact package", "verdict": "pass"}}, (plan.ref,))
    launch = approval(system, "execute", (package.ref,), question="确认误差 1.23456789123e-9 的执行任务？")
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
        assert ">1.23457e-9</span>" in body.decode()
        assert "原始值：1.23456789123e-9" in body.decode()
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


def test_frozen_approval_shows_direct_and_exact_report_images_only(system, installed):
    run_id = "frozen-figure-run"
    identity = {"operation_id": "fixture.analysis", "operation_version": "1",
                "operation_digest": "d" * 64}
    evidence_identity = {"operation_version": identity["operation_version"],
                         "operation_digest": identity["operation_digest"]}
    wide = tuple(register(system, f"wide-{index:02d}", "fixture.v1",
        {"value": "wide input " * 2600}).ref for index in range(12))
    runtime = register(system, "runtime-image", "opaque", raw=picture(), media="image/png",
        parents=wide, labels={**evidence_identity, "operation_output_port": "tool_evidence",
                              "tool_producer_run": "timed-out-attempt"})
    assert "operation_id" not in runtime.labels
    exploratory, exploratory_records = [], []
    for index in range(1, 32):
        saved = register(system, f"exploratory-image-{index:03d}", "opaque",
            raw=picture(), media="image/png", parents=wide,
            labels={**evidence_identity, "operation_output_port": "tool_evidence",
                    "tool_producer_run": run_id})
        alias = f"tool_evidence_{index:03d}"
        exploratory.append(saved)
        exploratory_records.append({"alias": alias,
            "artifact_ref": saved.ref.model_dump(mode="json"), "source_ref": None,
            "media_type": "image/png", "size_bytes": saved.size_bytes,
            "metadata": {"file_name": f"exploratory-{index:03d}.png"},
            "tool_name": "fixture_plot"})
    record = {"alias": "tool_evidence_032", "artifact_ref": runtime.ref.model_dump(mode="json"),
              "source_ref": None, "media_type": "image/png", "size_bytes": runtime.size_bytes,
              "metadata": {"file_name": "runtime-profile.png"}, "tool_name": "fixture_plot"}
    bindings = {item["alias"]: {"schema_version": 1,
        "artifact_ref": item["artifact_ref"], "port_name": "tool_evidence"}
        for item in (*exploratory_records, record)}
    manifest = register(system, "runtime-manifest", "scidiscovery.tool-evidence-manifest.v1", {
        "records": [*exploratory_records, record], "bindings": bindings},
        parents=wide + tuple(item.ref for item in (*exploratory, runtime)), labels={**identity, "operation_output_port": "recovery_manifest_output",
                                       "tool_producer_run": run_id})
    report = register(system, "runtime-report", "scidiscovery.layered-diagnosis.v1", {
        "summary": "Frozen result", "overall_verdict": "inconclusive", "claim_allowed": False,
        "evidence": [{"source_key": "tool_evidence_032", "source_type": "runtime_output",
                      "title": "Frozen runtime profile", "locator": "tool_evidence_032"}]},
        parents=wide + (manifest.ref,), labels={**identity, "operation_output_port": "layered_diagnosis"})
    direct = register(system, "direct-image", "opaque", raw=picture(), media="image/png")
    outside = register(system, "outside-image", "opaque", raw=picture(), media="image/png")
    launch = approval(system, "figure-review", (report.ref, direct.ref))
    ui = ApprovalUI(system.approvals, bindings=system.bindings, read_model=system.model,
                    instance_management_secret=b"s" * 32)
    base = ui.start()
    try:
        path = f"/review/{launch.approval_id}?" + urlencode({"token": launch.access_token})
        status, _, body = _request(base, "GET", path)
        text = body.decode()
        assert status == 200 and "Frozen runtime profile" in text
        assert runtime.artifact_id in text and direct.artifact_id in text
        images = re.findall(r"<img [^>]+>", text)
        assert len(images) == 2
        assert all(item.artifact_id not in "".join(images) for item in exploratory)
        assert outside.artifact_id not in text
        assert "<details class='research-panel figures-panel'>" in text
        runtime_path = f"/review/{launch.approval_id}/evidence/{runtime.artifact_id}?" + urlencode(
            {"token": launch.access_token, "format": "image"})
        direct_path = f"/review/{launch.approval_id}/evidence/{direct.artifact_id}?" + urlencode(
            {"token": launch.access_token, "format": "image"})
        outside_path = f"/review/{launch.approval_id}/evidence/{outside.artifact_id}?" + urlencode(
            {"token": launch.access_token, "format": "image"})
        assert _request(base, "GET", runtime_path)[0] == 200
        assert _request(base, "GET", direct_path)[0] == 200
        assert _request(base, "GET", outside_path)[0] == 403
    finally:
        ui.stop()


def test_frozen_approval_fails_closed_for_ambiguous_missing_or_incomplete_direct_manifest(system, installed):
    identity = {"operation_id": "fixture.analysis", "operation_version": "1",
                "operation_digest": "e" * 64}
    evidence_identity = {"operation_version": identity["operation_version"],
                         "operation_digest": identity["operation_digest"]}

    def receipt(prefix, run_id):
        image = register(system, prefix + "-image", "opaque", raw=picture(), media="image/png",
            labels={**evidence_identity, "operation_output_port": "tool_evidence",
                    "tool_producer_run": run_id})
        record = {"alias": "tool_evidence_002", "artifact_ref": image.ref.model_dump(mode="json"),
                  "source_ref": None, "media_type": "image/png", "size_bytes": image.size_bytes,
                  "metadata": {"file_name": prefix + ".png"}, "tool_name": "fixture_plot"}
        manifest = register(system, prefix + "-manifest", "scidiscovery.tool-evidence-manifest.v1", {
            "records": [record], "bindings": {"tool_evidence_002": {"schema_version": 1,
                "artifact_ref": record["artifact_ref"], "port_name": "tool_evidence"}}},
            parents=(image.ref,), labels={**identity, "operation_output_port": "recovery_manifest_output",
                                          "tool_producer_run": run_id})
        return image, manifest

    for scenario in ("ambiguous", "missing", "incomplete"):
        count = 101 if scenario == "incomplete" else 12
        payload = {} if scenario == "incomplete" else {"value": "wide input " * 2600}
        wide = tuple(register(system, f"{scenario}-wide-{index:03d}", "fixture.v1",
            payload).ref for index in range(count))
        parents = wide
        if scenario == "ambiguous":
            prior_image, prior_manifest = receipt("prior", "prior-run")
            _, current_manifest = receipt("current", "current-run")
            # Preserve one complete prior pair ahead of the wide inputs while
            # the second direct manifest remains beyond the response budget.
            parents = (prior_manifest.ref, prior_image.ref, *wide, current_manifest.ref)
        elif scenario == "incomplete":
            _, current_manifest = receipt("incomplete", "incomplete-run")
            parents = (*wide, current_manifest.ref)
        report = register(system, scenario + "-report", "scidiscovery.layered-diagnosis.v1", {
            "summary": "Frozen result", "overall_verdict": "inconclusive", "claim_allowed": False,
            "evidence": [{"source_key": "tool_evidence_002", "source_type": "runtime_output",
                          "title": "Must remain hidden", "locator": "tool_evidence_002"}]},
            parents=parents, labels={**identity, "operation_output_port": "layered_diagnosis"})
        launch = approval(system, scenario + "-figure-review", (report.ref,))
        review = system.approvals.review(launch.approval_id, access_token=launch.access_token)
        context = system.model.approval_context(system.a, review, presentation=True)
        rendered = build_presentation(tuple(context["artifacts"]),
            focus_artifact_ids=[report.artifact_id])
        assert rendered["figures"] == []
        report_view = next(item for item in context["artifacts"] if item["artifact_id"] == report.artifact_id)
        assert report_view["family"]["presentation_manifest_scan_complete"] is (scenario != "incomplete")
        assert report_view["family"]["presentation_manifest_match_count"] == (2 if scenario == "ambiguous" else 0)
