"""Native HTML forms for exact, explicitly previewed instance maintenance."""

from __future__ import annotations

import html
from dataclasses import asdict, is_dataclass
from urllib.parse import quote, urlencode

from .presentation_render import render_json_value, safe_local_href
from .navigation import navigation


_STORAGE = {"active": "未归档", "archiving": "归档进行中", "archived": "已归档",
            "restoring": "恢复进行中", "restored": "已恢复"}
_PHASES = {"idle": "空闲", "preparing": "准备中", "published": "归档已发布", "switched": "资料归属已切换",
           "cleanup": "活动副本收尾中", "completed": "本次维护已完成", "interrupted": "维护中断"}
_COUNTS = {"records": "控制记录数", "files": "清单文件数", "bytes": "清单字节数",
           "exclusive_bytes": "独占资料字节", "shared_bytes": "共享保留字节", "temporary_bytes": "临时空间需求（字节）",
           "missing_files": "历史缺失文件数", "nodes": "缓存节点数", "events": "缓存观察记录数",
           "logical_bytes": "缓存逻辑字节", "physical_bytes_released": "实际释放磁盘字节"}
_PRESERVED = {"scientific_records": "科学与控制记录", "originals": "原始资料", "archive": "归档资料",
              "maintenance_journal": "维护日志与清单", "preferences": "显示偏好"}
_ACTIONS = {"archive": "确认迁移并归档", "restore": "确认按原身份恢复", "resume": "继续本次维护",
            "rollback": "回退本次维护", "cleanup": "确认清理此实例的 UI 缓存"}


def _dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _text(value: object, limit: int = 1024) -> str:
    if value is None:
        return "未提供（null）"
    if not isinstance(value, (str, bool, int, float)):
        return "结构化记录"
    text = str(value)
    return html.escape(text[:limit], quote=True) + ("…（预览）" if len(text) > limit else "")


def _link(href: str, label: str, *, class_name: str = "") -> str:
    safe = safe_local_href(href)
    if safe is None:
        return "<span class='source-gap'>原件入口不可用</span>"
    return f"<a class='{class_name}' href='{html.escape(safe, quote=True)}'>{html.escape(label)}</a>"


def _section(title: str, content: str, *, class_name: str = "") -> str:
    return f"<section class='workbench-section {class_name}'><h2>{html.escape(title)}</h2>{content}</section>"


def _fingerprint(value: object) -> str | None:
    return value if isinstance(value, str) and 0 < len(value) <= 256 else None


def _form(base: str, action: str, *, csrf_token: str, fingerprint: str) -> str:
    return (
        f"<form class='management-confirm' method='post' action='{base}/{action}'>"
        f"<input type='hidden' name='csrf_token' value='{html.escape(csrf_token, quote=True)}'>"
        f"<input type='hidden' name='fingerprint' value='{html.escape(fingerprint, quote=True)}'>"
        "<label class='management-confirm-check'><input type='checkbox' name='confirm' value='confirm' required>"
        "<span>我已核对以上实例、精确预览版本、资料范围与缺口，并确认此操作。</span></label>"
        f"<button type='submit'>{_ACTIONS[action]}</button></form>"
    )


def _counts(value: object) -> str:
    counts = _dict(value)
    rows = []
    for key, label in _COUNTS.items():
        if key in counts:
            rows.append(f"<tr><th scope='row'>{label}</th><td>{render_json_value(counts[key], max_bytes=1024)}</td></tr>")
    return "<table class='management-counts'><tbody>" + "".join(rows) + "</tbody></table>" if rows else "<p class='source-gap'>尚未提供精确计数。</p>"


def _notes(preview: dict) -> str:
    rows = []
    for key, title in (("busy", "活动或未确认的写入者"), ("unsupported", "尚不支持的存储范围"),
                       ("gaps", "已记录的缺口与历史缺失"), ("unowned", "归属尚未确认的资料"),
                       ("paths", "本次资料路径"), ("preserved", "本次操作保留的资料")):
        if key not in preview or preview[key] in ([], {}, None):
            continue
        value = preview[key]
        if key == "preserved" and isinstance(value, list):
            value = [_PRESERVED.get(item, item) if isinstance(item, str) else item for item in value]
        rows.append(f"<div class='management-scope-note'><h3>{title}</h3>{render_json_value(value, max_bytes=4096)}</div>")
    return "".join(rows)


def _preview(
    action: str, preview: object, *, instance_id: str, status: dict, base: str, csrf_token: str,
) -> str:
    title = {"archive": "迁移实例资料并归档", "restore": "按原身份恢复归档", "cleanup": "清理 UI 自有缓存"}[action]
    preview_href = base + "?" + urlencode({"preview": action})
    details_href = "/api/instances/" + quote(instance_id, safe="") + "/maintenance?" + urlencode({"view": action})
    intro = {
        "archive": "归档会迁移本实例可精确归属的本地历史资料。远端执行机的原文件仍留在远端；共享原件保留其他实例需要的活动副本。历史缺失和未知归属会列入清单。",
        "restore": "恢复使用已登记的原归档及原身份。完成后仍通过现有入口选择实例；不会自动重启 Agent、求解器或旧会话。",
        "cleanup": "仅清理此实例的可重建 UI 缓存。科学记录、原件、归档、维护日志及显示偏好保留。",
    }[action]
    body = f"<p>{intro}</p>"
    if action == "cleanup":
        body += "<p class='bounded-note'>缓存逻辑字节与实际释放磁盘字节分别记录；SQLite 可能只复用空页，实际释放量可能为 0。</p>"
    body += "<nav class='management-preview-links'>" + _link(preview_href, "读取精确预览", class_name="download-button") + "</nav>"
    if not isinstance(preview, dict):
        return _section(title, body + "<p class='source-gap'>尚未读取本操作的精确预览。</p>")
    fingerprint = _fingerprint(preview.get("fingerprint"))
    identity_matches = preview.get("action") == action and (
        preview.get("instance_id") == instance_id or action == "cleanup" and "instance_id" not in preview
    )
    storage, phase = status.get("storage_state"), status.get("phase")
    state_allows = (action == "archive" and storage in ("active", "restored")
                    or action == "restore" and storage == "archived" and phase == "completed"
                    or action == "cleanup")
    ready = (preview.get("ready") is True and identity_matches and state_allows
             and not preview.get("busy") and not preview.get("unsupported") and status.get("action_running") is not True)
    body += f"<p class='management-readiness'>{'精确预览已就绪' if ready else '本预览当前不可确认'}</p>"
    if "archive_path" in preview:
        body += f"<p class='management-path'><strong>固定归档位置</strong><code>{_text(preview['archive_path'], 2048)}</code></p>"
    body += _counts(preview.get("counts")) + _notes(preview)
    body += (
        "<details class='management-fingerprint'><summary>精确预览版本</summary>"
        f"<code>{_text(preview.get('fingerprint'), 256)}</code></details>"
        + _link(details_href, "查看有界结构化预览与缺口", class_name="source-link")
    )
    if preview.get("manifest_href"):
        body += _link(preview["manifest_href"], "下载登记归档的原清单", class_name="source-link")
    if not identity_matches:
        body += "<p class='source-gap'>预览中的实例或操作与本页不匹配；请重新读取精确预览。</p>"
    elif not state_allows:
        body += "<p class='source-gap'>当前存储状态不允许此操作；请刷新维护状态。</p>"
    if status.get("action_running") is True:
        body += "<p class='source-gap'>后台维护操作尚未结束；请刷新读取进度。</p>"
    if fingerprint is None:
        body += "<p class='source-gap'>精确预览版本未提供；不能提交确认。</p>"
    if ready and fingerprint is not None:
        body += _form(base, action, csrf_token=csrf_token, fingerprint=fingerprint)
    if isinstance(preview.get("result"), dict):
        body += "<h3>最近操作的实际结果</h3>" + render_json_value(preview["result"], max_bytes=4096)
    return _section(title, body)


def render_management(
    instance,
    *,
    status,
    archive_preview=None,
    restore_preview=None,
    cleanup_preview=None,
    preferences=None,
    csrf_token: str,
    error=None,
) -> bytes:
    """Offer only service-declared storage actions with exact confirmation data."""
    metadata = asdict(instance) if is_dataclass(instance) and not isinstance(instance, type) else _dict(instance)
    status = _dict(status)
    instance_id = metadata.get("instance_id", status.get("instance_id", ""))
    instance_id = instance_id if isinstance(instance_id, str) else ""
    root = "/instance/" + quote(instance_id, safe="")
    base = root + "/manage"
    storage, phase = status.get("storage_state"), status.get("phase")
    storage_label = _STORAGE.get(storage, storage) if isinstance(storage, str) else "未提供"
    phase_label = _PHASES.get(phase, phase) if isinstance(phase, str) else "未提供"
    archived = storage == "archived"
    title = metadata.get("title", metadata.get("name", "研究实例"))
    header = (
        "<header class='workbench-header'><p class='eyebrow'>实例资料管理</p>"
        f"<h1>{_text(title, 256)}</h1>"
        f"<p class='instance-management-description'><strong>实例管理描述</strong> {_text(metadata.get('objective', ''), 1024)}</p>"
        f"<p class='node-key'>实例：{_text(instance_id, 256)}</p>"
        "<nav aria-label='实例管理导航'>"
        + _link(root, "浏览归档资料（只读）" if archived else "返回实例工作台")
        + _link(base, "刷新维护进度") + "</nav></header>"
    )
    if archived:
        header += "<p class='archive-read-only bounded-note'>已归档 · 资料只读。浏览不会自动恢复资料或重新启用历史审批。</p>"
    status_body = (
        "<dl class='metadata'><dt>资料存储状态</dt>"
        f"<dd>{_text(storage_label)}</dd><dt>维护阶段</dt><dd>{_text(phase_label)}</dd></dl>"
    )
    if status.get("action_running") is True:
        status_body += "<p class='bounded-note'>维护后台任务正在执行。请使用“刷新维护进度”读取最新记录。</p>"
    if "archive_path" in status:
        status_body += f"<p class='management-path'><strong>登记归档位置</strong><code>{_text(status['archive_path'], 2048)}</code></p>"
    if "progress" in status:
        status_body += "<h3>已记录进度</h3>" + render_json_value(status["progress"], max_bytes=4096)
    if status.get("error") is not None:
        status_body += "<div class='management-error'><h3>维护记录中的错误</h3>" + render_json_value(status["error"], max_bytes=4096) + "</div>"
    if status.get("restore_gaps"):
        status_body += "<p class='source-gap'>恢复时未导入部分旧展示缓存；科学记录已独立恢复，旧观测资料仍保留在归档中。</p>"
        status_body += "<details><summary>查看展示恢复缺口</summary>" + render_json_value(status["restore_gaps"], max_bytes=4096) + "</details>"
    status_fingerprint = _fingerprint(status.get("fingerprint"))
    if status_fingerprint is not None:
        status_body += (
            "<details class='management-fingerprint'><summary>当前维护记录版本</summary>"
            f"<code>{html.escape(status_fingerprint, quote=True)}</code></details>"
        )
    for action, field in (("resume", "can_resume"), ("rollback", "can_rollback")):
        if status.get(field) is True and status.get("action_running") is not True:
            if status_fingerprint is not None:
                status_body += _form(base, action, csrf_token=csrf_token, fingerprint=status_fingerprint)
            else:
                status_body += f"<p class='source-gap'>{_ACTIONS[action]}需要当前维护记录的精确版本；请刷新。</p>"
    if error is not None:
        header += _section("本次请求未完成", render_json_value(error, max_bytes=4096), class_name="management-error")
    panels = [header, _section("当前维护状态", status_body)]
    for action, preview in (("archive", archive_preview), ("restore", restore_preview), ("cleanup", cleanup_preview)):
        panels.append(_preview(action, preview, instance_id=instance_id, status=status, base=base, csrf_token=csrf_token))
    cleanup_result = status.get("cleanup_result")
    if isinstance(cleanup_result, dict):
        panels.append(_section("最近缓存清理的实际结果", _counts(cleanup_result.get("counts", cleanup_result))
            + render_json_value(cleanup_result, max_bytes=4096)))
    preferences = _dict(preferences)
    preference_body = "<p>显示偏好只改变列表排版，资料位置与科学记录保持原样。</p>"
    preference_state_known = type(preferences.get("show_artifacts")) is bool
    preferences_allowed = (storage in ("active", "restored") and phase in ("idle", "completed")
                           and status.get("action_running") is not True)
    if preferences_allowed and preference_state_known:
        show = preferences["show_artifacts"]
        preference_body += (
            f"<form class='management-preferences' method='post' action='{base}/preferences'>"
            f"<input type='hidden' name='csrf_token' value='{html.escape(csrf_token, quote=True)}'>"
            "<label>成果与转换节点<select name='show_artifacts'>"
            f"<option value='true'{ ' selected' if show else ''}>显示成果与转换节点</option>"
            f"<option value='false'{ ' selected' if not show else ''}>仅显示任务、审批和执行</option>"
            "</select></label><button type='submit'>保存显示偏好</button></form>"
        )
    else:
        preference_body += "<p class='source-gap'>当前显示偏好或可写状态未确认；请在维护空闲后刷新读取。</p>"
    panels.append(_section("列表显示偏好", preference_body))
    page = (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{_text(title, 256)} · 实例资料管理</title>"
        "<link rel='stylesheet' href='/static/style.css'></head><body>" + navigation(instance_id) +
        "<a class='skip-link' href='#management-content'>跳到管理内容</a>"
        "<main class='workbench-page management-page' id='management-content'>"
        + "".join(panels) + "</main></body></html>"
    )
    return page.encode("utf-8")


__all__ = ["render_management"]
