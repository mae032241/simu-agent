"""Existing frozen plots remain visible when a diagnosis produces only text."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from scidiscovery.artifact_agent.approval_ui import presentation
from scidiscovery.artifact_agent.approval_ui.presentation_render import render_presentation
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.general_science_views import build_presentation as general
from tests.operations.test_instance_read_model import system, approval
from tests.operations.test_instance_trajectory_read import trajectory, artifact, stored_run
from tests.operations.test_instance_content_display import picture


@pytest.fixture
def diagnosis(trajectory, monkeypatch):
    s = trajectory
    labels = dict(operation_id="science.result.diagnose.v1", operation_version="1", operation_digest="a" * 64)
    image = s.artifacts.register(picture("blue"), ArtifactRegistration(
        kind="scientific_attachment", schema_id="opaque", payload_schema_version=1,
        media_type="image/png", creator=s.actor,
        labels={"operation_output_port": "attachments", "tool_producer_run": "earlier_experiment"}),
        idempotency_key="original_plot")
    inputs = (("reference_material_005", image.ref),)
    manifest = artifact(s, "diagnosis_manifest", {
        "records": [], "bindings": {"reference_material_005": {
            "port_name": "reference_materials", "artifact_ref": image.ref.model_dump(mode="json")}}},
        schema="scidiscovery.tool-evidence-manifest.v1", parents=(image.ref,),
        labels={**labels, "tool_producer_run": "diagnosis", "operation_output_port": "recovery_manifest_output"})
    report = artifact(s, "diagnosis_report", {"summary": "Compared the existing three-panel plot.",
        "overall_verdict": "inconclusive", "claim_allowed": False, "evidence": []},
        schema="scidiscovery.layered-diagnosis.v1", parents=(image.ref, manifest.ref),
        labels=labels, instance=s.a)
    stored_run(s, "diagnosis", inputs=inputs, output=report.ref, operation="science.result.diagnose.v1")
    monkeypatch.setattr(presentation, "entry_points", lambda **_: (
        SimpleNamespace(name="general", load=lambda: general),))
    return s, report, manifest, image


@pytest.mark.parametrize("surface", ["run", "artifact", "approval"])
def test_diagnosis_shows_exact_input_plot_without_new_output_receipt(diagnosis, surface):
    s, report, manifest, image = diagnosis
    if surface == "approval":
        launch = approval(s, "review", (report.ref,))
        context = s.model.approval_context(s.a, s.approvals.review("review", access_token=launch.access_token), presentation=True)
    else:
        context = s.model.node_context(s.a, "run:diagnosis" if surface == "run" else "artifact:diagnosis_report")
    result = presentation.build_presentation(context["artifacts"], focus_artifact_ids=[report.artifact_id])
    assert [f["artifact_id"] for f in result["figures"]] == [image.artifact_id]
    assert result["figures"][0]["source"] == {
        "artifact_id": manifest.artifact_id, "json_pointer": "/bindings/reference_material_005"}
    page = render_presentation(result, evidence_href=lambda a, p: f"/evidence/{a}", image_href=lambda a: f"/image/{a}")
    assert "诊断输入图件" in page and "<img " in page
    assert s.artifacts.read(image.ref) == picture("blue")


@pytest.mark.parametrize("damage", ["binding", "report_parent", "manifest_parent", "duplicate_image"])
def test_diagnosis_input_plot_requires_exact_frozen_relationship(diagnosis, damage):
    s, report, manifest, image = diagnosis
    cohort = deepcopy(s.model.node_context(s.a, "run:diagnosis")["artifacts"])
    report_view = next(v for v in cohort if v["artifact_id"] == report.artifact_id)
    manifest_view = next(v for v in cohort if v["artifact_id"] == manifest.artifact_id)
    if damage == "binding":
        manifest_view["payload"]["bindings"]["reference_material_005"]["artifact_ref"]["sha256"] = "f" * 64
    elif damage == "report_parent":
        report_view["provenance"] = [v for v in report_view["provenance"] if v["ref"] != image.ref.model_dump(mode="json")]
    elif damage == "manifest_parent":
        manifest_view["provenance"] = []
    else:
        cohort.append(deepcopy(next(v for v in cohort if v["artifact_id"] == image.artifact_id)))
    assert not presentation.build_presentation(cohort, focus_artifact_ids=[report.artifact_id])["figures"]


@pytest.mark.process_e2e
def test_diagnosis_page_serves_original_input_png(diagnosis):
    from scidiscovery.artifact_agent.approval_ui.app import ApprovalUI
    from scidiscovery.artifact_agent.approval_ui.access import access_cookie
    from tests.operations.test_instance_browser_http import _request
    s, _, _, image = diagnosis
    ui = ApprovalUI(s.approvals, bindings=s.bindings, read_model=s.model, instance_management_secret=b"p" * 32)
    base = ui.start()
    cookie = access_cookie(s.a, ui.browser_access.issue(s.a))
    try:
        status, _, page = _request(base, "GET", f"/instance/{s.a}/nodes/run%3Adiagnosis", cookie=cookie)
        assert status == 200 and "诊断输入图件" in page.decode() and "<img " in page.decode()
        route = f"/instance/{s.a}/evidence/{image.artifact_id}?format=image"
        status, _, body = _request(base, "GET", route, cookie=cookie)
        assert status == 200 and body == s.artifacts.read(image.ref)
        assert _request(base, "GET", route.replace(s.a, s.b), cookie=cookie)[0] == 403
    finally:
        ui.stop()


def test_parent_presentation_stops_serializing_at_byte_budget(diagnosis, monkeypatch):
    from scidiscovery.artifact_agent.approval_ui.view_models import MAX_PAYLOAD_BYTES, json_size
    s, report, _, image = diagnosis
    calls = []
    class Parent:
        artifact_id = image.artifact_id
        def model_dump(self, **kwargs):
            calls.append(True)
            return image.ref.model_dump(**kwargs)
    # Already loaded metadata may be large; rendering must not duplicate all of it.
    envelope = SimpleNamespace(**report.model_dump(), ref=report.ref)
    envelope.parent_refs = (Parent(),) * 100000
    monkeypatch.setattr(s.model, '_artifact_view', lambda *_: dict(payload_state='available',
        payload={}, gaps=[{'code':'provenance_page_limit'}]))
    view = s.model._presentation_view(s.a, envelope)
    assert 100 < len(calls) < 1000
    assert json_size(view['provenance']) <= MAX_PAYLOAD_BYTES
    assert any(g['code'] == 'provenance_page_limit' for g in view['gaps'])
