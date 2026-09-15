from __future__ import annotations

import re
from urllib.parse import quote

import pytest

from scidiscovery.artifact_agent.approval_ui.presentation_render import (
    MAX_PRESENTATION_BYTES,
    render_json_value,
    render_presentation,
)


def _evidence(artifact_id: str, pointer: str) -> str:
    return f"/evidence/{quote(artifact_id, safe='')}?pointer={quote(pointer, safe='')}"


def _image(artifact_id: str) -> str:
    return f"/evidence/{quote(artifact_id, safe='')}?view=image"


def _presentation() -> dict:
    source = {"artifact_id": "frozen-plan", "json_pointer": "/parameters/0"}
    return {
        "sections": [
            {"title": "总体与本轮目标", "items": [{"label": "原始目标", "value": "Only the original bound objective", "source": source}]},
            {"title": "独立审查与限制", "items": [{"label": "原审查", "value": {"conclusion": "Finite case only", "limitations": ["Later objectives remain uncovered"]}, "source": source}]},
            {"title": "执行范围", "kind": "execution_scope", "items": [{"label": "案例", "value": ["case-1"], "source": source}]},
        ],
        "parameters": [{
            "name": "Temperature", "selected_value": 300, "reported_values": [298, 300], "unit": "K",
            "conditions": "ambient", "case_scope": ["case-1"], "epistemic_status": "工程假设",
            "acquisition": "用户给定", "uncertainty": "±2 K", "rationale": "Original selection reason",
            "sources": [{"title": "Original source", "locator": "Table 2 / page 7", "url": "https://example.org/paper?x=1&y=2",
                         "accessed_at": "2026-01-02T03:04:05Z", "source": source}], "source": source,
        }],
        "figures": [{"artifact_id": "safe-figure", "label": "case-1; x: V, y: A", "source": source}],
        "gaps": [{"code": "reference_missing", "artifact_id": "missing-original"}],
    }


def test_readable_sections_parameter_dimensions_and_exact_sources() -> None:
    page = render_presentation(_presentation(), evidence_href=_evidence, image_href=_image)
    for text in ("Only the original bound objective", "Finite case only", "Later objectives remain uncovered",
                 "选用值 / 单位", "原记录报告值", "298", "300", "ambient", "case-1", "工程假设", "用户给定", "±2 K",
                 "Original selection reason", "Table 2 / page 7", "2026-01-02T03:04:05Z", "reference_missing"):
        assert text in page
    assert "pointer=%2Fparameters%2F0" in page
    assert "<dl class='value-map'>" in page
    assert "<table class='parameter-table'>" in page
    assert "loading='lazy'" in page
    assert "rel='noreferrer noopener' referrerpolicy='no-referrer'" in page
    assert page.index("总体与本轮目标") < page.index("关键参数与条件") < page.index("图件与结果对照") < page.index("<span>执行范围</span>")
    assert "<details class='parameter-sources'>" in page
    assert "<details class='parameter-sources' open>" not in page


def test_reported_values_and_conditions_are_compact_with_exact_original_links() -> None:
    source = {"artifact_id": "parameter-original", "json_pointer": "/claims/0"}
    reported_source = {"artifact_id": "reported-original", "json_pointer": "/claims/0/observations/0"}
    page = render_presentation({"parameters": [{
        "name": "Band gap", "selected_value": "1.1e0", "unit": "eV", "source": source,
        "reported_values": [{"value": "1.12e0", "unit": "eV", "conditions": [],
            "evidence_mode": "direct_report", "source": reported_source},
            {"value": "<img src=x>", "unit": "eV", "evidence_mode": "future_mode<&>", "source": reported_source}],
        "conditions": [{"name": "temperature<script>", "value": "3.0e2", "unit": "K"}],
        "case_scope": "bulk silicon", "epistemic_status": "paper_fact", "acquisition": "网络检索",
        "uncertainty": "±0.02 eV", "rationale": "Original selection reason",
        "sources": [{"title": "Original paper", "locator": "Table 2", "source": reported_source}],
    }]}, evidence_href=_evidence, image_href=_image)
    assert "1.12e0 eV" in page
    assert "temperature&lt;script&gt;：3.0e2 K" in page
    assert "证据方式：原文报告" in page
    assert "文献事实" in page
    assert "future_mode&lt;&amp;&gt;" in page
    assert "±0.02 eV" in page
    assert "Original selection reason" in page
    assert "Table 2" in page
    assert _evidence("reported-original", "/claims/0/observations/0") in page
    assert "<dl class='value-map'>" not in page
    assert "<script" not in page and "<img" not in page
    visible = re.sub(r"<[^>]*>", "", page)
    for mechanical in ("artifact_id", "json_pointer", "evidence_mode", "direct_report", "reported-original"):
        assert mechanical not in visible


@pytest.mark.parametrize("unsafe", ["javascript:alert(1)", "data:image/svg+xml,test", "file:///etc/passwd",
    "https://user:password@example.org/", "//external.example/image.png", "https://example.org/\npath"])
def test_untrusted_source_links_and_images_never_become_active(unsafe: str) -> None:
    presentation = _presentation()
    presentation["parameters"][0]["sources"][0]["url"] = unsafe
    presentation["parameters"][0]["name"] = "<script>parameter</script>"
    presentation["sections"][0]["items"][0]["value"] = "<img src=x onerror=alert(1)>"
    presentation["figures"][0]["label"] = "' onerror='alert(1)"
    page = render_presentation(presentation, evidence_href=lambda *args: unsafe, image_href=lambda *args: unsafe)
    assert "<script" not in page
    assert "<img" not in page
    assert "&lt;script&gt;parameter&lt;/script&gt;" in page
    assert not re.search(r"(?:href|src)=['\"](?:javascript|data|file|https?:|//)", page, re.IGNORECASE)
    assert "原件入口不可用" in page


def test_unknown_source_and_uncertainty_are_not_inferred_from_doi_or_null() -> None:
    page = render_presentation({"parameters": [{"name": "unrecorded", "selected_value": None,
        "reported_values": [1, 2], "sources": [{"title": "doi:10.1234/example"}]}]},
        evidence_href=_evidence, image_href=_image)
    assert "doi:10.1234/example" in page
    assert "网络检索" not in page
    assert "实验测量" not in page
    assert "null（原记录空值）" in page
    assert "未提供估计" in page
    assert "原记录未声明科学分类" in page
    assert "来源未记录" in page


def test_large_values_and_provider_output_have_bounded_previews() -> None:
    source = {"artifact_id": "original-large-record", "json_pointer": "/report"}
    large = "<&>\"'" * 100000
    presentation = {
        "sections": [{"title": "Original report", "items": [{"label": "Record", "value": {"conclusion": large,
            "cases": [{"case": index, "value": large} for index in range(100)]}, "source": source}]} for _ in range(100)],
        "parameters": [{"name": f"parameter-{index}", "selected_value": large, "conditions": large, "source": source} for index in range(100)],
        "gaps": ["An unresolved source gap"],
    }
    page = render_presentation(presentation, evidence_href=_evidence, image_href=_image)
    assert len(page.encode("utf-8")) <= MAX_PRESENTATION_BYTES
    assert "预览" in page
    assert "original-large-record" in page
    assert "An unresolved source gap" in page
    assert len(render_json_value({"x": large}, max_bytes=2048).encode("utf-8")) <= 2048


def test_broken_optional_callbacks_and_malformed_provider_fields_are_visible() -> None:
    def unavailable(*args: object) -> str:
        raise ValueError("not authorized")

    presentation = _presentation()
    presentation["parameters"].append(None)
    presentation["sections"].append({"items": "not an item list"})
    page = render_presentation(presentation, evidence_href=unavailable, image_href=unavailable)
    assert "Only the original bound objective" in page
    assert "原件入口不可用" in page
    assert "安全预览未提供" in page
    assert render_presentation(None, evidence_href=_evidence, image_href=_image) == ""
