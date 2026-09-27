from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import re

import pytest

from scidiscovery.artifact_agent.approval_ui.management_render import render_management
from scidiscovery.artifact_agent.approval_ui.workbench_render import render_node, render_workbench


INSTANCE = {"instance_id": "instance-a", "name": "example", "title": "Research example", "objective": "Administrative description"}


def _status(**updates) -> dict:
    return {"instance_id": "instance-a", "storage_state": "active", "phase": "idle",
            "archive_path": "/project/.scidiscovery-archive/instances/instance-a",
            "can_resume": False, "can_rollback": False, "fingerprint": "s" * 64, **updates}


def _preview(action: str = "archive", **updates) -> dict:
    return {"instance_id": "instance-a", "action": action, "fingerprint": "p" * 64, "ready": True,
            "busy": [], "unsupported": [], "gaps": [], "unowned": [],
            "archive_path": "/project/.scidiscovery-archive/instances/instance-a",
            "counts": {"records": 27, "files": 11, "bytes": 4096, "exclusive_bytes": 3072,
                       "shared_bytes": 1024, "temporary_bytes": 8192, "missing_files": 1}, **updates}


def _page(**kwargs) -> str:
    return render_management(INSTANCE, status=kwargs.pop("status", _status()), preferences=kwargs.pop("preferences", {"show_artifacts": True}),
                             csrf_token="csrf-exact", **kwargs).decode("utf-8")


def test_initial_management_reads_status_and_preferences_without_preconfirming_actions() -> None:
    page = _page()
    assert "name='referrer'" not in page
    assert "实例管理描述" in page and "Administrative description" in page
    assert "读取精确预览" in page
    for action in ("archive", "restore", "cleanup"):
        assert f"href='/instance/instance-a/manage?preview={action}'" in page
        assert f"action='/instance/instance-a/manage/{action}'" not in page
    assert "action='/instance/instance-a/manage/preferences'" in page
    assert "name='show_artifacts'" in page and "value='true' selected" in page
    assert "name='csrf_token' value='csrf-exact'" in page
    assert "刷新维护进度" in page
    assert "<script" not in page
    assert "/delete" not in page


def test_archive_preview_preserves_shared_and_missing_scope_before_exact_confirmation() -> None:
    preview = _preview(gaps=[{"code": "historical_original_missing", "artifact_id": "missing-input"}],
                       unowned=[{"path": "system/unbound.log", "reason": "ownership_unknown"}])
    original = deepcopy(preview)
    page = _page(archive_preview=preview)
    for value in ("独占资料字节", "共享保留字节", "临时空间需求（字节）", "历史缺失文件数",
                  "3072", "1024", "8192", "historical_original_missing", "missing-input", "system/unbound.log", "ownership_unknown"):
        assert value in page
    assert "固定归档位置" in page
    assert "action='/instance/instance-a/manage/archive'" in page
    assert "name='fingerprint' value='" + "p" * 64 + "'" in page
    assert "type='checkbox' name='confirm' value='confirm' required" in page
    assert "查看有界结构化预览与缺口" in page
    assert "/api/instances/instance-a/maintenance?view=archive" in page
    assert page.index("historical_original_missing") < page.index("action='/instance/instance-a/manage/archive'")
    assert preview == original


@pytest.mark.parametrize("change", [
    {"ready": False}, {"ready": "true"}, {"fingerprint": None}, {"instance_id": "other-instance"},
    {"action": "restore"}, {"busy": [{"code": "native_stop_unconfirmed", "run": "failed-run"}]},
    {"unsupported": [{"code": "unknown_backend", "backend": "other"}]},
])
def test_unready_or_mismatched_preview_never_offers_mutation(change: dict) -> None:
    page = _page(archive_preview=_preview(**change))
    assert "action='/instance/instance-a/manage/archive'" not in page
    if "busy" in change:
        assert "活动或未确认的写入者" in page
        assert "native_stop_unconfirmed" in page and "failed-run" in page
    if "unsupported" in change:
        assert "unknown_backend" in page


def test_restore_is_offered_only_for_completed_archive_and_is_explicit() -> None:
    preview = _preview("restore")
    assert "action='/instance/instance-a/manage/restore'" not in _page(restore_preview=preview)
    page = _page(status=_status(storage_state="archived", phase="completed"), restore_preview=preview)
    assert "action='/instance/instance-a/manage/restore'" in page
    assert "已归档 · 资料只读" in page
    assert "浏览归档资料（只读）" in page
    assert "不会自动重启 Agent、求解器或旧会话" in page
    page = _page(status=_status(storage_state="archived", phase="cleanup"), restore_preview=preview)
    assert "action='/instance/instance-a/manage/restore'" not in page
    assert "当前存储状态不允许此操作" in page


def test_interrupted_maintenance_uses_only_explicit_flags_and_current_fingerprint() -> None:
    status = _status(storage_state="archiving", phase="interrupted", can_resume=True, can_rollback=True,
                     error={"code": "copy_interrupted", "path": "objects/one"})
    page = _page(status=status)
    assert "维护中断" in page and "copy_interrupted" in page
    for action in ("resume", "rollback"):
        assert f"action='/instance/instance-a/manage/{action}'" in page
    assert page.count("name='fingerprint' value='" + "s" * 64 + "'") == 2
    assert "action='/instance/instance-a/manage/preferences'" not in page
    page = _page(status={**status, "can_resume": "true", "can_rollback": False})
    assert "action='/instance/instance-a/manage/resume'" not in page
    assert "action='/instance/instance-a/manage/rollback'" not in page
    page = _page(status={**status, "fingerprint": None})
    assert "当前维护记录的精确版本" in page
    assert "action='/instance/instance-a/manage/resume'" not in page


def test_running_maintenance_does_not_offer_duplicate_actions() -> None:
    page = _page(status=_status(action_running=True, can_resume=True, can_rollback=True), archive_preview=_preview())
    assert "维护后台任务正在执行" in page
    assert "后台维护操作尚未结束" in page
    assert "<form" not in page


def test_cleanup_separates_logical_bytes_actual_release_and_preserved_records() -> None:
    preview = {"action": "cleanup", "ready": True, "fingerprint": "c" * 64, "busy": [],
               "counts": {"nodes": 15, "events": 32, "logical_bytes": 4096},
               "preserved": ["scientific_records", "originals", "archive", "maintenance_journal", "preferences"]}
    page = _page(cleanup_preview=preview, status=_status(cleanup_result={"physical_bytes_released": 0, "logical_bytes": 4096}))
    assert "action='/instance/instance-a/manage/cleanup'" in page
    assert "缓存逻辑字节" in page and "实际释放磁盘字节" in page
    assert "实际释放量可能为 0" in page
    for value in ("科学与控制记录", "原始资料", "归档资料", "维护日志与清单", "显示偏好"):
        assert value in page
    assert "最近缓存清理的实际结果" in page
    assert "/delete" not in page


def test_missing_or_unknown_status_has_readable_fallback_and_no_mutation() -> None:
    page = _page(status={"storage_state": ["unexpected"], "phase": None}, preferences=None, archive_preview=_preview())
    assert "尚未读取本操作的精确预览" in page
    assert "当前存储状态不允许此操作" in page
    assert "<form" not in page
    assert "原件入口不可用" not in page


def test_management_escapes_paths_errors_tokens_and_untrusted_manifest_links() -> None:
    instance = {**INSTANCE, "title": "<script>unsafe title</script>", "objective": "<svg onload=alert(1)>"}
    preview = _preview(archive_path="<img src=x onerror=alert(1)>", manifest_href="javascript:alert(1)",
                       gaps=[{"message": "<iframe srcdoc='<script>x</script>'>"}])
    page = render_management(instance, status=_status(), archive_preview=preview, preferences={"show_artifacts": False},
                             csrf_token="' onclick='bad", error={"message": "<style>body{display:none}</style>"}).decode()
    for tag in ("<script", "<svg", "<img", "<iframe", "<style"):
        assert tag not in page
    assert "&lt;script&gt;unsafe title&lt;/script&gt;" in page
    assert "name='csrf_token' value='&#x27; onclick=&#x27;bad'" in page
    assert not re.search(r"href=['\"](?:javascript|data|file|https?):", page)
    assert "原件入口不可用" in page


def test_large_maintenance_scope_is_bounded_and_never_embeds_raw_json() -> None:
    long = "<&>\"'" * 100000
    preview = _preview(ready=False, gaps=[{"code": "missing", "detail": long} for _ in range(1000)],
                       unowned=[{"path": long, "reason": long} for _ in range(1000)])
    page = _page(archive_preview=preview, error={"detail": long})
    assert len(page.encode("utf-8")) <= 256 * 1024
    assert "有界预览" in page
    assert "<pre" not in page
    assert "/api/instances/instance-a/maintenance?view=archive" in page


def test_existing_instance_dataclass_can_render_without_mutation() -> None:
    @dataclass(frozen=True)
    class Instance:
        instance_id: str = "instance-a"
        title: str = "Frozen instance metadata"
        objective: str = "Original administrative text"

    instance = Instance()
    page = render_management(instance, status=_status(), csrf_token="csrf", preferences={"show_artifacts": True}).decode()
    assert "Frozen instance metadata" in page and "Original administrative text" in page
    assert instance.objective == "Original administrative text"


def test_archived_workbench_and_nodes_do_not_start_live_updates() -> None:
    overview = {"instance": INSTANCE, "storage": _status(storage_state="archived", phase="completed"),
                "nodes": {"items": [], "next_cursor": None}, "active_tasks": []}
    page = render_workbench(overview, browse_base="/instance/instance-a", csrf_token="csrf", can_manage=True).decode()
    assert "已归档 · 只读" in page
    assert "/static/workbench.js" not in page
    assert "href='/instance/instance-a/manage'" in page
    node = {"kind": "approval", "key": "approval:old", "name": "old", "state": "pending",
            "storage": overview["storage"], "review_url": "/review/old?token=original", "gaps": []}
    page = render_node(node, instance_id="instance-a").decode()
    assert "原审批记录 · 只读" in page and "打开原审批请求" in page
    assert "/static/workbench.js" not in page


def test_artifact_display_preference_keeps_cursor_and_a_way_to_restore_display() -> None:
    overview = {"instance": INSTANCE, "storage": _status(), "preferences": {"show_artifacts": False},
                "nodes": {"items": [{"kind": "artifact", "key": "artifact:hidden", "name": "hidden", "state": "registered"}],
                          "next_cursor": "next-page"}, "active_tasks": []}
    page = render_workbench(overview, browse_base="/instance/instance-a", csrf_token="csrf", can_manage=True).decode()
    assert "artifact%3Ahidden" not in page
    assert "显示偏好隐藏了本页 1 个成果登记节点" in page
    assert "本页节点已按显示偏好隐藏" in page
    assert "尚无已绑定节点" not in page
    assert "cursor=next-page" in page
    assert "在管理页恢复显示" in page
    assert len(overview["nodes"]["items"]) == 1
