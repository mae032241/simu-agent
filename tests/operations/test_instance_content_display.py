"""Real original pagination and saved-family display do not change science gates."""
from copy import deepcopy
from io import BytesIO
import json
from types import SimpleNamespace
from urllib.parse import urlencode

from PIL import Image
import pytest

from scidiscovery.artifact_agent.approval_ui import presentation
from scidiscovery.artifact_agent.approval_ui.app import ApprovalUI
from scidiscovery.artifact_agent.approval_ui.access import access_cookie
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.general_science_views import build_presentation as general
from tcad_artifact.instance_views import build_presentation as tcad
from curve_figure_evidence.instance_views import build_presentation as figures, MANIFEST
from tests.operations.test_instance_read_model import system, artifact, approval
from tests.operations.test_instance_browser_http import _request
from tests.operations.test_instance_presentations import view, parameter_family


@pytest.fixture
def providers(monkeypatch):
    monkeypatch.setattr(presentation, "entry_points", lambda **_: tuple(SimpleNamespace(name=name, load=lambda p=p: p)
        for name, p in (("general", general), ("tcad", tcad), ("figures", figures))))


def register(system, name, schema, payload, *, parents=(), labels=None, raw=None, media="application/json", instance=None, fingerprint=None):
    item = system.artifacts.register(canonical_json(payload) if raw is None else raw,
        ArtifactRegistration(kind="fixture", schema_id=schema, payload_schema_version=1,
            creator=system.actor, parent_refs=parents, labels=labels or {}, media_type=media), idempotency_key=name)
    system.bindings.bind(instance=instance or system.a, namespace="artifact", name=name, object_id=item.artifact_id,
                         request_fingerprint=fingerprint)
    return item


def long_plan(count=153):
    return {"proposals": [{"experiment_key": "one", "comparison_contract": {"variables": [
        {"scientific_path": "D(u)", "unit": "cm2/s", "rationale": "Exact selection rationale " * 12,
         "factor_type": "physical", "comparison_role": "fixed", "expectations": [
             {"case_key": f"case{i}", "value": i, "historical_note": "saved note " * 30} for i in range(count)]}]}}]}


def test_pagination_reaches_beyond_projection_and_128_rows_via_http(system, providers):
    payload = long_plan()
    assert len(canonical_json(payload["proposals"][0]["comparison_contract"]["variables"])) > 24 * 1024
    original = register(system, "long_plan", "scidiscovery.experiment-portfolio.v1", payload)
    ui = ApprovalUI(system.approvals, bindings=system.bindings, read_model=system.model, instance_management_secret=b"p"*32)
    base = ui.start()
    cookie = access_cookie(system.a, ui.browser_access.issue(system.a))
    try:
        root = f"/instance/{system.a}/evidence/{original.artifact_id}"
        status, _, page = _request(base, "GET", root + "?view=parameters&after=144", cookie=cookie)
        assert status == 200
        text = page.decode()
        assert "共 153 条" in text and "case144" in text and "case151" in text
        assert "case143" not in text and "case152" not in text
        assert "expectations%2F144%2Fvalue" in text and "after=152" in text
        assert "实验设计取值" in text and "来源未记录/是否默认未知" not in text
        assert "变量类型" in text and "物理参数" in text and "对照角色" in text and "固定" in text
        assert _request(base, "GET", root+"?view=parameters&after=152", cookie=cookie)[2].decode().count("case152") == 1
        assert _request(base, "GET", root+"?format=download", cookie=cookie)[2] == canonical_json(payload)
        assert _request(base, "GET", f"/instance/{system.b}/evidence/{original.artifact_id}?view=parameters", cookie=cookie)[0] == 403
        assert _request(base, "GET", root+"?view=parameters&after=-1", cookie=cookie)[0] == 400
    finally:
        ui.stop()


def test_sources_only_match_original_dependency_graph(providers):
    cohort = list(parameter_family())
    unrelated = deepcopy(cohort[1]); unrelated["artifact_id"] = unrelated["source"]["artifact_id"] = "unrelated"
    unrelated["payload"]["sources"][0]["title"] = "Wrong current source"
    cohort.append(unrelated)
    result = presentation.build_presentation(cohort)
    assert result["parameters"][0]["sources"][0]["title"] == "Original paper"
    cohort[0]["provenance"] = []
    result = presentation.build_presentation(cohort)
    assert result["parameters"][0]["sources"] == []
    assert "暂未解析" in result["parameters"][0]["source_status"]


def test_approved_parameter_reference_is_not_an_unrelated_same_key(providers):
    project = view("project", "tcad.deck-project.v1", {"parameter_bindings": [
        {"name": "Eg", "declared_value": "1.1", "approved_parameter_key": "bandgap"}]}, provenance=[{"artifact_id": "parameters"}])
    cohort = (project, *parameter_family())
    result = presentation.build_presentation(cohort)
    row = next(r for r in result["parameters"] if r["name"] == "Eg")
    assert row["sources"][0]["source"]["artifact_id"] == "parameters"
    project["provenance"] = []
    result = presentation.build_presentation(cohort)
    row = next(r for r in result["parameters"] if r["name"] == "Eg")
    assert not row["sources"] and "暂未解析" in row["source_status"]


def picture(color):
    output = BytesIO(); Image.new("RGB", (20, 12), color).save(output, format="PNG"); return output.getvalue()


def family(system, *, prefix="old", numeric=True, fingerprint="a"*64, modern=False):
    paper = artifact(system, prefix+"paper", raw=b"paper", media_type="application/pdf")
    parent = (paper.ref,)
    labels = {"transform_profile": "old.figure.transform", "operation_invocation_fingerprint": fingerprint}
    if modern:
        labels.update(operation_id="old.figure.transform", operation_version="1", operation_digest="b"*64)
    members, manifest_entries = {}, []
    sources = [("source_panels/panel.png", "image/png", picture("white")),
               ("audit_overlays/panel--identity-fidelity.png", "image/png", picture("red")),
               ("curve_tables/panel--line.csv", "text/csv", b"x,y\n1,2\n2,3\n")]
    if numeric:
        sources.append(("audit_overlays/panel--numeric-redraw.png", "image/png", picture("blue")))
    for i, (data_item, media, raw) in enumerate(sources):
        collection = data_item.split("/")[0]
        member_labels = {**labels, "output_label": f"arbitrary-{i}"}
        member_labels["operation_output_port"] = collection
        member = register(system, prefix+f"_arbitrary{i}", "opaque", {}, parents=parent,
            labels=member_labels, media=media, raw=raw, fingerprint=fingerprint)
        members[data_item] = member
        manifest_entries.append({"data_item": data_item, "collection": collection, "media_type": media,
                                 "sha256": member.sha256, "bytes": member.size_bytes})
    payload = {"source": {"figure": "Fig.4", "page": 4}, "panels": [{"panel_key": "panel", "axis_calibration": {
        "x": {"scale": "linear", "unit": "nm"}, "y": {"scale": "log10", "unit": "cm-3"}},
        "series": [{"label": "line", "data_item": "curve_tables/panel--line.csv", "point_count": 2}]}],
        "provenance": {"output_artifacts": manifest_entries}}
    original = register(system, prefix, MANIFEST, payload, parents=parent,
        labels={**labels, "output_label": "primary"}, fingerprint=fingerprint)
    return original, members


@pytest.mark.parametrize("modern", [False, True])
def test_saved_family_visible_and_downloads_exact_but_approval_scope_unchanged(system, providers, modern):
    original, members = family(system, modern=modern)
    newer, _ = family(system, prefix="new", fingerprint="c"*64)
    context = system.model.node_context(system.a, "artifact:old")
    ids = {v["artifact_id"] for v in context["artifacts"]}
    assert newer.artifact_id not in ids
    assert all(m.artifact_id in ids for m in members.values())
    rendered = presentation.build_presentation(context["artifacts"], focus_artifact_ids=[original.artifact_id])
    assert {f["label"] for f in rendered["figures"]} == {"论文原图", "CSV 数值重绘", "原图叠点检查"}
    assert not any(g["code"] == "provider_unavailable" for g in rendered["gaps"])
    launch = approval(system, "frozen", (original.ref,))
    review = system.approvals.review("frozen", access_token=launch.access_token)
    frozen = system.model.approval_context(system.a, review, presentation=True)
    assert all(m.artifact_id not in {v["artifact_id"] for v in frozen["artifacts"]} for m in members.values())
    ui = ApprovalUI(system.approvals, bindings=system.bindings, read_model=system.model, instance_management_secret=b"p"*32)
    base = ui.start(); cookie = access_cookie(system.a, ui.browser_access.issue(system.a))
    try:
        status, _, page = _request(base, "GET", f"/instance/{system.a}/nodes/artifact%3Aold", cookie=cookie)
        assert status == 200 and "CSV 数值重绘" in page.decode() and "下载 CSV" in page.decode()
        for path, member in members.items():
            mode = "download" if path.endswith("csv") else "image"
            response = _request(base, "GET", f"/instance/{system.a}/evidence/{member.artifact_id}?format={mode}", cookie=cookie)
            assert response[0] == 200 and response[2] == system.artifacts.read(member.ref)
            assert _request(base, "GET", f"/review/frozen/evidence/{member.artifact_id}?"+urlencode({"token": launch.access_token, "format": mode}))[0] == 403
    finally:
        ui.stop()


def test_old_family_missing_redraw_is_a_local_gap_and_no_plugin_falls_back(system, providers, monkeypatch):
    original, members = family(system, numeric=False)
    context = system.model.node_context(system.a, "artifact:old")
    result = presentation.build_presentation(context["artifacts"])
    assert "CSV 数值重绘" not in {f["label"] for f in result["figures"]}
    assert any(g["code"] == "numeric_redraw_not_saved_or_not_readable" for g in result["gaps"])
    monkeypatch.setattr(presentation, "entry_points", lambda **_: ())
    context = system.model.node_context(system.a, "artifact:old")
    assert original.artifact_id in {v["artifact_id"] for v in context["artifacts"]}
    assert all(m.artifact_id not in {v["artifact_id"] for v in context["artifacts"]} for m in members.values())


def test_candidate_matching_never_joins_different_parents(system, providers):
    original, members = family(system)
    extra = register(system, "wrong", "opaque", {}, parents=(), labels={
        "transform_profile": "old.figure.transform", "operation_invocation_fingerprint": "a"*64, "output_label": "wrong"},
        fingerprint="a"*64, raw=picture("yellow"), media="image/png")
    context = system.model.node_context(system.a, "artifact:old")
    assert extra.artifact_id not in {v["artifact_id"] for v in context["artifacts"]}
    assert any(g["code"] == "family_member_identity_mismatch" for g in context["gaps"])


def test_partial_foundation_evidence_cannot_hide_duplicate_key(system, providers):
    payload = {"items": [{"item_type": "parameter", "statement": "scale", "value": 1, "evidence_keys": ["paper"]}],
               "evidence": [{"source_key": "paper", "title": "First"},
                            {"source_key": "padding", "title": "padding" * 5000},
                            {"source_key": "paper", "title": "Second"}]}
    original = register(system, "foundation", "scidiscovery.scientific-foundation.v1", payload)
    context = system.model.node_context(system.a, "artifact:foundation")
    result = presentation.build_presentation(context["artifacts"])
    assert result["parameters"][0]["sources"] == []
    assert "未完整解析" in result["parameters"][0]["source_status"]
    full = system.model.parameter_context(system.a, original.artifact_id)
    page = presentation.build_parameter_page(full["artifact"], full["dependencies"])
    assert page["parameters"][0]["sources"] == []
    assert any(g["code"] == "source_key_ambiguous" for g in page["gaps"])


def test_mixed_resolved_and_missing_foundation_citations_remain_partial(providers):
    value = view("foundation", "scidiscovery.scientific-foundation.v1", {
        "items": [{"item_type": "parameter", "statement": "scale", "value": 1, "evidence_keys": ["known", "missing"]}],
        "evidence": [{"source_key": "known", "title": "Recorded source"}]})
    row = presentation.build_presentation((value,))["parameters"][0]
    assert len(row["sources"]) == 1 and "未完整解析" in row["source_status"]


def test_missing_parent_prevents_unique_citation_claim(providers):
    cohort = list(parameter_family())
    cohort[0]["provenance"].append({"artifact_id": "not_loaded"})
    assert not presentation.build_presentation(cohort)["parameters"][0]["sources"]


def test_incomplete_family_or_missing_port_never_labels_a_numeric_redraw(system, providers):
    original, members = family(system)
    context = system.model.node_context(system.a, "artifact:old")
    manifest = next(v for v in context["artifacts"] if v["artifact_id"] == original.artifact_id)
    manifest["family"]["lookup_incomplete"] = True
    result = presentation.build_presentation(context["artifacts"])
    assert "CSV 数值重绘" not in {f["label"] for f in result["figures"]}
    manifest["family"].pop("lookup_incomplete")
    for value in context["artifacts"]:
        value.get("family", {}).pop("operation_output_port", None)
    result = presentation.build_presentation(context["artifacts"])
    assert "CSV 数值重绘" not in {f["label"] for f in result["figures"]}
    assert any(g["code"] == "figure_member_missing_or_ambiguous" for g in result["gaps"])


def test_malformed_figure_member_is_local_and_series_cannot_download_image_as_csv(system, providers):
    original, members = family(system)
    context = system.model.node_context(system.a, "artifact:old")
    manifest = next(v for v in context["artifacts"] if v["artifact_id"] == original.artifact_id)
    manifest["payload"]["provenance"]["output_artifacts"].append({"data_item": None, "collection": []})
    manifest["payload"]["panels"][0]["series"][0]["data_item"] = "source_panels/panel.png"
    result = presentation.build_presentation(context["artifacts"])
    assert any(g["code"] == "figure_member_metadata_unreadable" for g in result["gaps"])
    assert not any(g["code"] == "provider_unavailable" for g in result["gaps"])
    assert not any(i["label"] == "CSV 数据表" for s in result["sections"] for i in s["items"])
    assert "CSV 数值重绘" in {f["label"] for f in result["figures"]}


def test_large_nested_package_parameters_keep_case_and_value_pointer(system, providers):
    payload = {"project": {"files": [{"content": "solver source " * 8000}], "case_parameter_bindings": [
        {"scientific_path": "x", "case_key": f"case{i}", "realized_value": i, "derivation": "original explanation " * 50}
        for i in range(145)]}}
    original = register(system, "package", "tcad.execution-package.v2", payload)
    context = system.model.parameter_context(system.a, original.artifact_id)
    page = presentation.build_parameter_page(context["artifact"], context["dependencies"], after=136)
    assert page["parameter_page"]["total"] == 145
    assert [row["selected_value"] for row in page["parameters"]] == list(range(136,144))
    assert page["parameters"][0]["source"]["json_pointer"] == "/project/case_parameter_bindings/136"
    assert "solver source" not in str(page)


def test_partial_manifest_and_duplicate_data_items_do_not_pick_first(system, providers):
    original, members = family(system)
    context = system.model.node_context(system.a, "artifact:old")
    manifest = next(v for v in context["artifacts"] if v["artifact_id"] == original.artifact_id)
    manifest["gaps"] = [{"code": "display_field_partial", "source_pointer": "/provenance/output_artifacts"}]
    result = presentation.build_presentation(context["artifacts"])
    assert "CSV 数值重绘" not in {f["label"] for f in result["figures"]}
    assert any(g["code"] == "figure_manifest_members_partial" for g in result["gaps"])
    manifest["gaps"] = []
    data = manifest["payload"]["provenance"]["output_artifacts"]
    conflict = deepcopy(next(i for i in data if i['data_item'].endswith('--numeric-redraw.png')))
    conflict['sha256'] = 'f'*64
    data.append(conflict)
    result = presentation.build_presentation(context["artifacts"])
    assert "CSV 数值重绘" not in {f["label"] for f in result["figures"]}
    assert any(g["code"] == "figure_data_item_ambiguous" for g in result["gaps"])


def test_family_query_limit_never_claims_exhaustive_members(system, providers, monkeypatch):
    original, members = family(system)
    records = system.bindings.invocation_artifacts(instance=system.a, request_fingerprint='a'*64)
    monkeypatch.setattr(system.bindings, 'invocation_artifacts', lambda **_: (records[0],)*101)
    context = system.model.node_context(system.a, 'artifact:old')
    manifest = next(v for v in context['artifacts'] if v['artifact_id'] == original.artifact_id)
    assert manifest['family']['lookup_incomplete'] is True
    assert any(g['code'] == 'family_lookup_limit' for g in context['gaps'])


def test_overlong_parameter_details_stay_bounded_with_original_entry(providers):
    from scidiscovery.artifact_agent.approval_ui.evidence import render_parameter_page
    row = {"name": "scale", "selected_value": 1, "source": {"artifact_id": "original", "json_pointer": "/claims/0"},
           "sources": [{"title": "文献"*1000, "url": "https://example.org/"+'x'*4000} for _ in range(8)]}
    value = {"parameters": [row]*8, "parameter_page": {"total": 8, "after": 0}, "gaps": []}
    raw = render_parameter_page(value, href='/instance/one/evidence/original?view=parameters', instance_id='one',
        evidence_href=lambda a,p:'/instance/one/evidence/'+a+'?'+urlencode({'pointer':p}))
    assert len(raw)<256*1024
    assert '此行出处与条件较长'.encode() in raw and b'claims%2F0' in raw
