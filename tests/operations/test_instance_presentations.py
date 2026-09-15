"""Domain presentation remains a bounded reader, independent of admission."""

from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from scidiscovery.artifact_agent.approval_ui import presentation
from scidiscovery.general_science_views import build_presentation as general
from tcad_artifact.instance_views import build_presentation as tcad


def view(identity, schema, payload=None, **metadata):
    return {"artifact_id": identity, "schema_id": schema, "payload": payload,
            "source": {"artifact_id": identity, "json_pointer": ""}, **metadata}


@pytest.fixture
def installed(monkeypatch):
    calls = []
    def entries(*, group):
        calls.append(group)
        return (SimpleNamespace(name="general_science", load=lambda: general),
                SimpleNamespace(name="tcad_artifact", load=lambda: tcad))
    monkeypatch.setattr(presentation, "entry_points", entries)
    return calls


def parameter_family(*, source_type="frozen_input", second_catalog=False):
    claim = view("parameters", "scidiscovery.device-parameter-set.v1", {
        "parameter_set_key": "device", "requirement_set_key": "requirements", "title": "Device parameters", "objective": "Frozen objective",
        "claims": [{"parameter_key": "bandgap", "selected_value": "1.1e0", "unit": "eV", "epistemic_status": "paper_fact",
            "conditions": [{"name": "temperature", "value": "3.0e2", "unit": "K"}], "selection_rationale": "Use the reported baseline",
            "observations": [{"source_key": "paper", "reported_value": "1.12e0", "reported_unit": "eV", "locator": "Table 2, row 4", "evidence_mode": "direct_report"}]}]})
    catalog = view("catalog", "scidiscovery.evidence-source-catalog.v1", {
        "catalog_key": "frozen_catalog", "sources": [{"source_key": "paper", "source_type": source_type,
            "title": "Original paper", "doi": "10.1000/example", "authors": ["A. Author"], "publication_year": 2020,
            "original_url": "https://example.org/original", "final_url": "https://example.org/paper", "accessed_at": "2020-01-01T00:00:00Z"}]})
    requirements = view("requirements", "scidiscovery.device-parameter-requirements.v1", {
        "requirement_set_key": "requirements", "parameters": [{"parameter_key": "bandgap", "display_name": "Band gap", "device_scope": "bulk silicon"}]})
    claim["provenance"] = [{"artifact_id": "catalog"}, {"artifact_id": "requirements"}]
    values = [claim, catalog, requirements]
    if second_catalog:
        other = deepcopy(catalog)
        other["artifact_id"] = other["source"]["artifact_id"] = "new_catalog"
        other["payload"]["sources"][0]["title"] = "Newer same-key paper"
        values.append(other)
        claim["provenance"].append({"artifact_id": "new_catalog"})
    return tuple(values)


def test_general_objective_plan_review_and_analysis_preserve_original_facts(installed):
    artifacts = (
        view("goal", "scidiscovery.research-objective.v1", {"statement": "Overall exact objective", "mandatory_targets": [{"target_key": "later", "observable": "later target"}]}),
        view("plan", "scidiscovery.experiment-portfolio.v1", {"objective": "Overall exact objective", "priority_rationale": "Separate mechanisms",
            "proposals": [{"experiment_key": "one", "objectives": ["now", "later"], "current_objectives": ["now"], "stop_conditions": ["retain later until condition met"],
                "comparison_contract": {"variables": [{"variable_key": "temperature", "scientific_path": "device.temperature", "unit": "K", "rationale": "Thermal control",
                    "expectations": [{"case_key": "cold", "value": 280}, {"case_key": "warm", "value": 300}]}]}}]}),
        view("review", "scidiscovery.scientific-review.v1", {"verdict": "revise", "summary": "The scope remains limited", "global_confounders": ["Original uncertainty"]}),
        view("analysis", "scidiscovery.layered-diagnosis.v1", {"summary": "A sealed partial result", "overall_verdict": "inconclusive", "claim_allowed": False, "limitations": ["No fit evidence"]}),
    )
    original = deepcopy(artifacts)
    result = presentation.build_presentation(artifacts)
    facts = [item for section in result["sections"] for item in section["items"]]
    assert any(item["value"] == ["now", "later"] and item["source"]["json_pointer"] == "/proposals/0/objectives" for item in facts)
    assert any(item["value"] is False and item["source"]["artifact_id"] == "analysis" for item in facts)
    assert [row["selected_value"] for row in result["parameters"]] == [280, 300]
    assert [row["case_scope"]["case_key"] for row in result["parameters"]] == ["cold", "warm"]
    assert result["parameters"][1]["field_sources"]["selected_value"]["json_pointer"] == "/proposals/0/comparison_contract/variables/0/expectations/1/value"
    assert artifacts == original
    assert set(installed) == {"scidiscovery.instance_views"}
    presentation.presentation_pointers("scidiscovery.research-objective.v1")
    presentation.presentation_pointers("scidiscovery.experiment-portfolio.v1")
    assert len(installed) == 1


@pytest.mark.parametrize("source_type,expected", [("frozen_input", "冻结输入材料"), ("web_snapshot", "网络检索")])
def test_selected_reported_and_acquisition_dimensions_remain_separate(installed, source_type, expected):
    result = presentation.build_presentation(parameter_family(source_type=source_type))
    row = result["parameters"][0]
    assert row["name"] == "Band gap" and row["selected_value"] == "1.1e0"
    assert row["reported_values"][0]["value"] == "1.12e0"
    assert row["unit"] == "eV" and row["epistemic_status"] == "paper_fact"
    assert row["acquisition"] == expected  # A DOI does not imply web acquisition.
    assert row["uncertainty"] == "未提供估计"
    assert row["sources"][0]["source"] == {"artifact_id": "catalog", "json_pointer": "/sources/0"}
    assert row["sources"][0]["locator_source"] == {"artifact_id": "parameters", "json_pointer": "/claims/0/observations/0/locator"}
    assert row["sources"][0]["accessed_at"] == ("2020-01-01T00:00:00Z" if source_type == "web_snapshot" else None)


def test_source_catalog_ambiguity_never_selects_newer_version(installed):
    result = presentation.build_presentation(parameter_family(second_catalog=True))
    assert result["parameters"][0]["sources"] == []
    assert any(gap["code"] == "source_catalog_ambiguous" for gap in result["gaps"])
    assert result["parameters"][0]["reported_values"][0]["value"] == "1.12e0"


def test_parameters_repeat_per_exact_case_and_version(installed):
    payload = {"entrypoint": "device.cmd", "resource_limits": {"wall_time_seconds": 60},
        "parameter_bindings": [{"name": "mobility", "declared_value": "default", "unit": "cm2/Vs", "evidence_class": "tool_default"}],
        "case_parameter_bindings": [{"experiment_key": "test", "case_key": case, "scientific_path": "device.temperature", "realized_value": str(value), "unit": "K"}
                                    for case, value in (("cold", 280), ("warm", 300))]}
    artifacts = (view("old_project", "tcad.deck-project.v1", payload), view("new_project", "tcad.deck-project.v1", deepcopy(payload)))
    result = presentation.build_presentation(artifacts)
    assert len(result["parameters"]) == 6
    assert {row["source"]["artifact_id"] for row in result["parameters"]} == {"old_project", "new_project"}
    assert any(row["uncertainty"] == "工具默认值；适用性未证实；未提供估计" for row in result["parameters"])
    assert any(gap["code"] == "default_source_missing" for gap in result["gaps"])
    assert any(section.get("kind") == "execution_scope" for section in result["sections"])


def test_reviewed_package_projects_parameters_without_source_code(installed):
    artifact = view("package", "tcad.reviewed-deck-package.v2", {"project": {
        "files": [{"content": "private solver source must not become presentation facts"}],
        "entrypoint": "device.cmd", "parameter_bindings": [{"name": "length", "declared_value": "1e-6", "unit": "m"}]},
        "review": {"summary": "Original review", "verdict": "pass", "execution_ready": True}})
    result = presentation.build_presentation((artifact,))
    assert result["parameters"][0]["source"]["json_pointer"] == "/project/parameter_bindings/0"
    assert "private solver source" not in str(result)
    paths = presentation.presentation_pointers("tcad.reviewed-deck-package.v2")
    assert "/project/parameter_bindings" in paths and "/project/files" not in paths


def test_provider_receives_read_only_json_without_runtime_capabilities(monkeypatch):
    artifact = view("exact", "unknown.v1", {"nested": [1]})
    artifact["runtime"] = object()
    def provider(cohort):
        assert isinstance(cohort, tuple)
        assert "runtime" not in cohort[0]
        with pytest.raises(TypeError):
            cohort[0]["payload"]["nested"][0] = 99
        raise RuntimeError("fixture provider failure")
    monkeypatch.setattr(presentation, "entry_points", lambda **kw: (SimpleNamespace(name="broken", load=lambda: provider),))
    result = presentation.build_presentation((artifact,))
    assert artifact["payload"] == {"nested": [1]}
    assert any(gap["code"] == "provider_unavailable" for gap in result["gaps"])
    assert result["sections"][0]["items"][0]["value"] == [1]


def test_unregistered_provider_sources_are_rejected_and_unknown_schema_falls_back(monkeypatch):
    def provider(_):
        result = presentation.empty()
        result["sections"] = [{"title": "Unauthorized", "items": [{"label": "fake", "value": "invented", "source": {"artifact_id": "other_instance", "json_pointer": ""}}]}]
        return result
    monkeypatch.setattr(presentation, "entry_points", lambda **kw: (SimpleNamespace(name="bad", load=lambda: provider),))
    result = presentation.build_presentation((view("historical", "old.unknown.v1", {"summary": "Old exact record"}),))
    assert "invented" not in str(result)
    assert any(gap["code"] == "provider_unavailable" for gap in result["gaps"])
    assert any(item["value"] == "Old exact record" for section in result["sections"] for item in section["items"])


def test_markup_stays_text_urls_are_filtered_and_only_authorized_images_are_listed(installed):
    artifacts = list(parameter_family(source_type="web_snapshot"))
    artifacts[1]["payload"]["sources"][0].update(title="<script>alert(1)</script>", final_url="javascript:alert(1)")
    artifacts.extend((view("figure", "opaque", media_type="image/png"), view("active_svg", "opaque", media_type="image/svg+xml")))
    result = presentation.build_presentation(tuple(artifacts))
    assert result["parameters"][0]["sources"][0]["title"] == "<script>alert(1)</script>"
    assert result["parameters"][0]["sources"][0]["url"] is None
    assert {figure["artifact_id"] for figure in result["figures"]} == {"figure"}
    for unsafe in ("https://example.org/?token=secret", "https://example.org/?%74oken=secret", "https://user:secret@example.org/file", "file:///etc/passwd"):
        assert presentation.safe_url(unsafe) is None


def test_large_presentation_has_explicit_bound_and_original_pointers(installed):
    artifacts = tuple(view(f"artifact_{i}", "scidiscovery.research-objective.v1", {"statement": "x" * 15000, "mandatory_targets": ["target"]}) for i in range(40))
    result = presentation.build_presentation(artifacts)
    assert len(json.dumps(result, ensure_ascii=True).encode()) <= presentation.MAX_PRESENTATION_BYTES
    assert any(gap["code"] == "presentation_byte_limit" for gap in result["gaps"])
    assert all(item["source"]["artifact_id"].startswith("artifact_") for section in result["sections"] for item in section["items"])


def test_compact_root_projection_and_absolute_source_pointer_are_supported(installed):
    artifact = view("plan", "scidiscovery.experiment-portfolio.v1", {"objective": "Projected field"})
    result = presentation.build_presentation((artifact,))
    assert result["sections"][0]["items"][0]["source"]["json_pointer"] == "/objective"
    paths = presentation.presentation_pointers(artifact["schema_id"])
    assert "/proposals/*/current_objectives" in paths
    assert "/proposals/*/comparison_contract/variables" in paths
    assert "/proposals" not in paths
    assert presentation.presentation_pointers("scidiscovery.experiment-portfolio.v999") == ()
    assert presentation.value_at({"a/b": {"~x": None}}, "/a~1b/~0x") is None
    with pytest.raises(ValueError):
        presentation.value_at({"a~": 1}, "/a~")
