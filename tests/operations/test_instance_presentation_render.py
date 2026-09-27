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
    assert "<details class='research-panel figures-panel'>" in page
    assert "<span class='panel-count'>1</span>" in page
    assert "<details class='parameter-sources'>" in page
    assert "<details class='parameter-sources' open>" not in page
    without_figures = _presentation()
    without_figures["figures"] = []
    assert "图件与结果对照" not in render_presentation(
        without_figures, evidence_href=_evidence, image_href=_image)


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


def test_scientific_previews_compact_numbers_without_mutating_evidence() -> None:
    from copy import deepcopy
    from html import unescape

    source = {"artifact_id": "original", "json_pointer": "/summary"}
    original = "初始化偏差 1.2332352444688333e-5，浓度 6.76862812233398e19，深度 0.49988384999999996 μm。"
    presentation = {
        "sections": [{"title": "结果分析", "items": [
            {"label": "正式摘要", "value": original, "source": source},
            {"label": "指标", "value": {"error": 1.2332352444688333e-5}, "source": source},
        ]}],
        "parameters": [{"name": "浓度", "selected_value": 6.76862812233398e19,
                        "reported_values": [{"value": "6.76862812233398e19", "unit": "cm^-3"}],
                        "conditions": [{"name": "深度", "value": "0.49988384999999996", "unit": "μm"}],
                        "source": source}],
    }
    before = deepcopy(presentation)
    page = render_presentation(presentation, evidence_href=_evidence, image_href=_image)
    visible = unescape(re.sub(r"<[^>]*>", "", page))
    assert "初始化偏差 1.23324e-5，浓度 6.76863e+19，深度 0.499884 μm。" in visible
    assert "原始值：1.2332352444688333e-5" in page
    assert "原始值：6.76862812233398e19" in page
    assert "阈值比较与判定以原始记录为准" in visible
    assert "1.2332352444688333" not in visible
    assert presentation == before
    # A raw field/evidence preview remains exact unless explicitly opted in.
    assert original in render_json_value(original)


def test_scientific_numeric_display_preserves_identifiers_code_and_exact_comparisons() -> None:
    from scidiscovery.artifact_agent.approval_ui.presentation_render import render_scientific_text

    literal = ("run_1.23456789 /data/1.23456789.csv https://example.org/1.23456789 "
               "`threshold=1.23456789` 2026-09-18T12:34:56.123456789Z 1.12e0 3.0e2 2029 "
               "v1.23456789 1.23456789.2 12345678901234567890 www.example.org/?v=1.23456789")
    assert render_scientific_text(literal) == literal
    page = render_scientific_text("误差 1.0000001e-6 超过阈值 1.0000000e-6")
    assert "原始值：1.0000001e-6" in page
    assert "原始值：1.0000000e-6" in page
    assert "aria-label='显示约值" in page
    assert ">1.23457e+6</span>" in render_scientific_text("1234567.8")
    assert "&lt;script&gt;" in render_scientific_text("<script>1.23456789</script>")
    assert "<script>" not in render_scientific_text("<script>1.23456789</script>")
    assert "rounded-number" not in render_scientific_text("`threshold=1.23456789123", limit=22)
    clipped = render_scientific_text("误差 1.23456789123e-50，", limit=19)
    assert "rounded-number" not in clipped and "预览" in clipped
    assert "1.23456789e9999999999999999999" == render_scientific_text("1.23456789e9999999999999999999")


def test_number_rich_preview_keeps_existing_byte_bound() -> None:
    page = render_json_value(["数值 1.234567891234e-9 " * 100] * 20, max_bytes=8192, compact_numbers=True)
    assert len(page.encode("utf-8")) <= 8192
    assert "rounded-number" in page
    assert "预览" in page


def test_figures_beyond_inline_preview_keep_exact_open_links():
    data = _presentation()
    data['figures'] = [{'artifact_id': f'image-{i}', 'label': f'Case {i}',
        'source': {'artifact_id': 'manifest', 'json_pointer': f'/records/{i}'}} for i in range(12)]
    page = render_presentation(data, evidence_href=_evidence, image_href=_image)
    assert page.count('<img ') == 8
    assert page.count('下载原图') == 12
    assert "<span class='panel-count'>12</span>" in page
    for i in range(12):
        assert _image(f'image-{i}').replace('&', '&amp;') in page
        assert f'Case {i}' in page
    assert '其余图件可逐项打开原图' in page
