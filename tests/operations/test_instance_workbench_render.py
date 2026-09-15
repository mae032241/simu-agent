from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote

from scidiscovery.artifact_agent.approval_ui.workbench_render import (
    render_diagnostic,
    render_node,
    render_workbench,
)


def _metadata(kind: str, name: str, state: str) -> dict:
    return {"kind": kind, "name": name, "title": name, "key": f"{kind}:{name}", "state": state,
            "created_at": "2026-09-14T00:00:00Z", "source_time": "2026-09-14T00:00:00Z"}


def _source(artifact: str, *, key: str | None = None) -> dict:
    return {"artifact_id": artifact, "key": key, "source_pointer": "/inputs/0/artifact_ref"}


def _presentation() -> dict:
    return {"sections": [{"title": "原始目标与阶段结论", "items": [
        {"label": "总体目标", "value": "Original historical research objective", "source": {"artifact_id": "goal-old", "json_pointer": "/objective"}},
        {"label": "阶段结论", "value": "Only one sealed conclusion", "source": {"artifact_id": "result-old", "json_pointer": "/conclusion"}},
        {"label": "限制", "value": ["Later targets are still open"], "source": {"artifact_id": "result-old", "json_pointer": "/limitations"}},
    ]}], "figures": [{"artifact_id": "safe-image", "label": "Original comparison", "source": {"artifact_id": "result-old", "json_pointer": "/figure"}}]}


def _overview() -> dict:
    active = [_metadata("run", "branch-a", "running"), _metadata("run", "branch-b", "queued"),
              _metadata("approval", "review-old", "pending"), _metadata("execution", "solver-old", "running")]
    return {"instance": {"instance_id": "instance-a", "name": "instance-a", "title": "Example research"},
        "management_description": "Latest administrative description", "objective_refs": [_source("goal-old")],
        "active_tasks": active, "active_task_pages": {"run": {"has_more": False}},
        "nodes": {"items": active + [_metadata("artifact", "plan-old", "registered")], "next_cursor": "next-page:one"},
        "display_node": {"key": "run:branch-a", "basis": "most_recent_run"}, "presentation": _presentation(), "gaps": []}


def _node() -> dict:
    return {**_metadata("run", "old-failed-run", "failed"), "source": {"object_id": "original-run-id"},
        "objective_refs": [_source("goal-old")], "inputs": [_source("plan-old")], "outputs": [_source("result-old")],
        "recorded_scientific_claim_admissible": "inconclusive", "qualification": {"state": "not_evaluated"},
        "current_selection": [], "sealed_output": {"payload": {"conclusion": "Only one sealed conclusion", "private_bulk": "must not duplicate this payload"}},
        "relationships": {"predecessors": [{"key": "run:exact-parent", "kind": "run", "relation": "draft_from"}],
                          "successors": [{"key": "run:exact-child", "kind": "run", "relation": "resume_from"}],
                          "matching_reviews": [{"key": "run:exact-review"}], "has_more": False},
        "native_execution": {"coverage": "unobserved", "reason": "no_records", "scientific_evidence": False},
        "recovery": {"draft_available": None, "recovery_pending": True, "availability_state": "not_revalidated"},
        "diagnostics": {"events": [{"event_id": 7, "recorded_at": "2026-09-14T00:00:01Z", "activity": "tool_failed",
            "diagnostic": {"code": "exact_failure", "field_path": "/cases/0/contact", "tool_name": "solver",
                "engineering": {"reference": "diag_" + "a" * 32, "available_sections": ["summary", "stderr"]}}}], "next_after": 7},
        "gaps": [{"code": "old_original_missing"}]}


def test_workbench_has_separate_branches_exact_goals_and_native_pagination() -> None:
    page = render_workbench(_overview(), browse_base="/instance/instance-a", csrf_token="csrf", can_manage=True).decode()
    assert "name='referrer'" not in page
    for value in ("实例管理描述", "Latest administrative description", "Original historical research objective",
                  "多个活动分支", "branch-a", "branch-b", "review-old", "solver-old", "成果 / 转换", "人工审批", "外部执行"):
        assert value in page
    assert "最近节点" in page
    assert "/instance/instance-a/nodes/run%3Abranch-a" in page
    assert "/instance/instance-a?cursor=next-page%3Aone" in page
    assert "/instance/instance-a/manage" in page
    assert "name='workbench-csrf' content='csrf'" in page
    assert "<script src='/static/workbench.js' defer>" in page
    assert "<form" not in page
    assert "?format=image" in page
    assert "工作台导航" in page


def test_closed_or_empty_instance_does_not_invent_scientific_objective() -> None:
    overview = _overview()
    overview.update(objective_refs=[], active_tasks=[], presentation=None, display_node=None)
    page = render_workbench(overview, browse_base="/instance/instance-a", csrf_token="csrf").decode()
    assert "当前节点的原始目标尚未唯一定位" in page
    assert "当前没有正在运行的任务" in page
    assert "Original historical research objective" not in page
    assert "/instance/instance-a/manage" not in page
    assert page.count("Latest administrative description") == 1


def test_node_retains_exact_relationships_and_independent_status_dimensions() -> None:
    page = render_node(_node(), instance_id="instance-a", presentation=_presentation()).decode()
    assert page.count("Only one sealed conclusion") == 1
    assert "private_bulk" not in page
    assert "must not duplicate this payload" not in page
    for value in ("Later targets are still open", "inconclusive", "not_evaluated", "运行完成、科学结论与人工批准分别记录",
                  "未观测；无法据此判断计算耗时或错误", "draft_available", "recovery_pending", "not_revalidated",
                  "exact_failure", "/cases/0/contact", "solver", "original-run-id", "old_original_missing"):
        assert value in page
    for key in ("run:exact-parent", "run:exact-child", "run:exact-review"):
        assert "/instance/instance-a/nodes/" + quote(key, safe="") in page
    assert "diagnostic_after=7" in page
    assert "/instance/instance-a/diagnostics/diag_" in page
    assert "data-diagnostic-api='/api/instances/instance-a/diagnostics/diag_" in page
    assert "<details class='research-panel workbench-originals'>" in page
    assert "<details class='research-panel workbench-originals' open>" not in page
    assert "<pre" not in page


def test_execution_collection_and_approval_link_are_read_only_navigation() -> None:
    node = {**_metadata("execution", "collected-execution", "collected"), "collection_status": "collected",
            "collection": {"state": "collected", "recovery_pending": False},
            "observation": {"payload": {"exit_code": 0, "state": "finished"}}, "gaps": []}
    page = render_node(node, instance_id="instance-a").decode()
    assert "已收集" in page and "执行收集状态" in page and "外部执行与收集" in page
    assert "本地计算未观测" not in page
    assert "<form" not in page
    node = {**_metadata("approval", "old-review", "pending"), "review_url": "/review/exact-old?token=old-token", "gaps": []}
    page = render_node(node, instance_id="instance-a").decode()
    assert "href='/review/exact-old?token=old-token'" in page
    assert "打开原审批请求" in page
    assert "<form" not in page


def test_cache_observation_time_does_not_replace_source_event_time() -> None:
    overview = _overview()
    overview["observations"] = {"coverage": "observed_since_cache_creation", "items": [{"seq": 3,
        "node_key": "run:branch-a", "state": "completed", "source_time": "2020-01-01T00:00:00Z", "observed_at": "2026-09-14T00:00:00Z"}]}
    page = render_workbench(overview, browse_base="/instance/instance-a", csrf_token="csrf").decode()
    assert "原记录时间" in page and "页面观察时间" in page
    assert "不是原事件发生时间" in page
    assert "2020-01-01T00:00:00Z" in page
    assert "/api/instances/instance-a/observations" in page


def test_diagnostic_original_has_readable_summary_sections_and_byte_pagination() -> None:
    reference = "diag_" + "b" * 32
    page = render_diagnostic({"section": "summary", "text": json.dumps({"code": "exact_error", "causes": [{"type": "ValueError", "message": "original detail"}]}),
        "available_sections": ["summary", "stderr"], "offset": 0, "total_bytes": 17000, "next_offset": 16384},
        instance_id="instance-a", node_key="run:exact-run", reference=reference).decode()
    assert "<dl class='value-map'>" in page
    assert "original detail" in page and "exact_error" in page
    assert "node_key=run%3Aexact-run" in page and "offset=16384" in page and "section=stderr" in page
    assert "返回原节点" in page


def test_workbench_untrusted_text_links_and_log_content_are_escaped() -> None:
    overview = _overview()
    overview["instance"]["title"] = "<script>alert('instance')</script>"
    overview["management_description"] = "<img src=x onerror=alert(1)>"
    overview["active_tasks"][0]["title"] = "<svg onload=alert(2)>"
    page = render_workbench(overview, browse_base="javascript:alert(1)", csrf_token="' onload='x").decode()
    assert page.count("<script") == 1
    assert "<svg" not in page
    assert "&lt;img src=x onerror=alert(1)&gt;" in page
    assert not re.search(r"href=['\"](?:javascript|data|https?:)", page)
    node = _node()
    node["review_url"] = "//external.example/"
    node["diagnostics"]["events"][0]["diagnostic"]["field_path"] = "<iframe srcdoc='<script>x</script>'>"
    page = render_node(node, instance_id="instance-a").decode()
    assert "<iframe" not in page and "打开原审批请求" not in page
    page = render_diagnostic({"section": "stderr", "text": "<script>log content</script>", "available_sections": ["stderr"]},
        instance_id="instance-a", node_key="run:original", reference="diag_" + "c" * 32).decode()
    assert "&lt;script&gt;log content&lt;/script&gt;" in page
    assert page.count("<script") == 1


def test_large_page_preserves_all_paged_nodes_and_bounds_raw_payloads() -> None:
    overview = _overview()
    overview["active_tasks"] = [_metadata("run", f"branch-{index}-" + ":" * 220, "running") for index in range(90)]
    overview["nodes"]["items"] = [_metadata("artifact", f"result-{index}-" + ":" * 220, "registered") for index in range(100)]
    overview["presentation"]["sections"][0]["items"][0]["value"] = "'" * 1000000
    page = render_workbench(overview, browse_base="/instance/instance-a", csrf_token="csrf")
    assert len(page) <= 256 * 1024
    text = page.decode()
    for item in overview["active_tasks"] + overview["nodes"]["items"]:
        assert quote(item["key"], safe="") in text
    assert "next-page%3Aone" in text
    node = _node()
    node["sealed_output"]["payload"]["private_bulk"] = "large raw data" * 100000
    page = render_node(node, instance_id="instance-a", presentation=_presentation())
    assert len(page) <= 256 * 1024
    assert b"large raw data" not in page


def test_progressive_script_uses_text_content_and_preserves_native_links() -> None:
    script = Path(render_workbench.__code__.co_filename).with_name("static").joinpath("workbench.js").read_text()
    assert "textContent = value.text" in script
    assert "innerHTML" not in script
    assert "credentials: \"same-origin\"" in script
    assert "original.href = link.href" in script
