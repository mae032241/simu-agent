"""Server-rendered navigation over bounded, instance-scoped read models."""

from __future__ import annotations

import html
import json
from urllib.parse import quote, urlencode

from .presentation_render import render_json_value, render_presentation, safe_local_href, render_source, fold_panel, human_value, approval_heading, render_scientific_text
from .navigation import navigation


_MAX_PAGE_BYTES = 256 * 1024
_KINDS = {"run": "任务", "task": "历史任务", "artifact": "成果 / 转换", "approval": "人工审批", "execution": "外部执行"}
_STATES = {
    "queued": "排队中", "running": "运行中", "completed": "运行完成", "failed": "失败",
    "registered": "已登记", "pending": "待审批", "decided": "已决定", "expired": "已过期",
    "cancelled_by_human": "用户已取消", "created": "已创建", "collected": "已收集",
    "collecting": "收集中", "collection_failed": "收集失败", "unknown": "未记录",
}
_PREVIEW = "<p class='bounded-note'>仅显示有界预览；完整字段请通过原件或记录入口读取。</p>"


def _text(value: object, limit: int = 256) -> str:
    if value is None:
        text = "未提供（null）"
    elif isinstance(value, str):
        text = value
    elif isinstance(value, (bool, int, float)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = "结构化记录"
    return html.escape(text[:limit], quote=True) + ("…（预览）" if len(text) > limit else "")


def _dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list:
    return value if isinstance(value, list) else []


def _path(instance_id: str) -> str:
    return "/instance/" + quote(instance_id, safe="")


def _node_href(instance_id: str, key: object) -> str:
    if not isinstance(key, str) or len(key) > 320:
        return ""
    return _path(instance_id) + "/nodes/" + quote(key if isinstance(key, str) else "", safe="")


def _evidence_href(instance_id: str, artifact_id: str, pointer: str = "") -> str:
    return _path(instance_id) + "/evidence/" + quote(artifact_id, safe="") + "?" + urlencode({"pointer": pointer})


def _link(href: str, label: object, *, class_name: str = "", extra: str = "") -> str:
    safe = safe_local_href(href)
    if safe is None:
        return "<span class='source-gap'>入口不可用</span>"
    return f"<a class='{class_name}' href='{html.escape(safe, quote=True)}'{extra}>{_text(label)}</a>"


def _section(title: str, body: str, *, class_name: str = "", section_id: str = "") -> str:
    return f"<section class='workbench-section {class_name}' id='{section_id}'><h2>{_text(title)}</h2>{body}</section>"


def _document(title: object, body: str, *, instance_id: str, csrf_token: str = "", live_updates: bool = True) -> bytes:
    script = "<script src='/static/workbench.js' defer></script>" if live_updates else ""
    page = (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<meta name='workbench-csrf' content='{html.escape(csrf_token, quote=True)}'>"
        f"<title>{_text(title)} · 科研工作台</title>"
        "<link rel='stylesheet' href='/static/style.css'>"
        f"{script}</head><body>" + navigation(instance_id) +
        "<a class='skip-link' href='#workbench-content'>跳到主要内容</a>"
        f"<main class='workbench-page' id='workbench-content' data-instance-id='{html.escape(instance_id, quote=True)}'>"
        f"{body}</main></body></html>"
    )
    return page.encode("utf-8")


def _state(value: object) -> str:
    label = _STATES.get(value, value) if isinstance(value, str) else "未记录"
    css = value if isinstance(value, str) and value in _STATES else "unknown"
    return f"<span class='workbench-state state-{css}'>{_text(label, 80)}</span>"


def _record_title(node: dict) -> str:
    if node.get("kind") == "task":
        return "历史任务 · " + str(node.get("name") or "未命名")
    schema = node.get("schema_id")
    outputs = _list(node.get("outputs"))
    if not schema and outputs:
        schema = _dict(_dict(outputs[0]).get("ref")).get("schema_id")
    titles = {
        "scidiscovery.scientific-review.v1": "独立科学审查",
        "scidiscovery.experiment-design-intent.v1": "实验设计",
        "scidiscovery.experiment-portfolio.v1": "实验计划",
        "scidiscovery.layered-diagnosis.v1": "结果分析",
        "scidiscovery.research-objective.v1": "研究目标",
        "scidiscovery.scientific-intake.v1": "证据整理",
        "tcad.deck-review-report.v1": "实现独立审查",
        "tcad.deck-project.v1": "仿真实现",
    }
    if schema in titles:
        return titles[schema]
    operation = str(node.get("operation_id", ""))
    for part, title in (("review", "独立审查"), ("analyze", "结果分析"), ("diagnose", "结果诊断"),
                        ("design", "实验设计"), ("author", "实验实现"), ("revise", "受控修订"), ("extract", "证据整理")):
        if part in operation.split("."):
            return title
    return _KINDS.get(node.get("kind"), "研究记录")


def _time(value: object) -> str:
    if not isinstance(value, str):
        return ""
    shown = value[:16].replace("T", " ") + (" UTC" if value.endswith("Z") or value.endswith("+00:00") else "")
    return f"<time class='local-time' datetime='{html.escape(value, quote=True)}'>{_text(shown, 48)}</time>"


def _node_card(node: dict, instance_id: str, *, compact: bool = False) -> str:
    key = node.get("key", "")
    css_kind = node.get("kind") if node.get("kind") in _KINDS else "unknown"
    link = _link(_node_href(instance_id, key), _record_title(node), class_name="node-title",
        extra=(" title='" + html.escape(str(node.get("name", key)), quote=True) + "'") if not compact else "")
    return (f"<li class='trajectory-node node-{css_kind}'><span class='trajectory-dot' aria-hidden='true'></span>"
        "<div class='trajectory-content'><div class='node-card-heading'>" + link + _state(node.get("state"))
        + "</div>" + _time(node.get("source_time") or node.get("created_at")) + "</div></li>")


def _goal_panel(view: dict, instance_id: str) -> str:
    refs = _list(view.get("objective_refs"))
    records = _list(view.get("objective_records"))
    statements = []
    for record in records[:2]:
        value = record.get("payload") if isinstance(record, dict) else None
        if isinstance(value, str):
            original = "<p class='goal-statement'>" + render_scientific_text(value, 260) + "</p>"
            source = render_source(record.get("source"), lambda artifact, pointer: _evidence_href(instance_id, artifact, pointer))
            if any('\u4e00' <= char <= '\u9fff' for char in value):
                statements.append(original + source)
            else:
                statements.append("<p class='source-note'>已定位本节点绑定的原始目标，完整语义以原文为准。</p>"
                    + fold_panel("目标原文（英文）", original + source))
    if not statements:
        statements.append("<p class='source-note'>" + ("原始目标已定位，可按来源查阅。" if refs else "当前节点的原始目标尚未唯一定位。") + "</p>")
    links = _references(refs, instance_id, max_bytes=4096)
    if links:
        statements.append(fold_panel("原目标的精确记录", links))
    return "<section class='goal-card'><p class='eyebrow'>研究边界</p><h2>原始研究目标</h2>" + "".join(statements) + "</section>"




def _plain_preview(value: object, limit: int) -> str:
    text = value if isinstance(value, str) else "未命名记录"
    return text[:limit] + ("…（预览）" if len(text) > limit else "")


def _references(refs: object, instance_id: str, *, max_bytes: int = 12 * 1024) -> str:
    items, used = [], 0
    for ref in _list(refs):
        if not isinstance(ref, dict):
            continue
        artifact = ref.get("artifact_id") or _dict(ref.get("artifact_ref")).get("artifact_id")
        key = ref.get("key")
        label = ref.get("artifact_name") or ref.get("name") or key or artifact or "缺失引用"
        if isinstance(key, str):
            link = _link(_node_href(instance_id, key), label)
        elif isinstance(artifact, str):
            link = _link(_evidence_href(instance_id, artifact), label)
        else:
            link = f"<span class='source-gap'>{_text(label)}：引用缺失</span>"
        pointer = ref.get("source_pointer")
        source = f"<small>绑定位置：{_text(pointer, 120)}</small>" if pointer is not None else ""
        port = f"<strong>{_text(ref['port_name'], 80)}</strong> " if "port_name" in ref else ""
        rendered = "<li>" + port + link + source + "</li>"
        if used + len(rendered.encode("utf-8")) > max_bytes:
            items.append("<li>" + _PREVIEW + "</li>")
            break
        items.append(rendered)
        used += len(rendered.encode("utf-8"))
    return "<ul class='record-links'>" + "".join(items) + "</ul>" if items else "<p class='source-gap'>未提供精确引用。</p>"


def _record_link(node: dict, instance_id: str) -> str:
    url = "/api/instances/" + quote(instance_id, safe="") + "/nodes/" + quote(str(node.get("key", "")), safe="")
    return _link(url, "查看完整结构化记录", class_name="source-link")


def _observations(observations: object, instance_id: str, *, node_key: str | None = None) -> str:
    values = _dict(observations)
    if not values:
        return ""
    rows = []
    for item in _list(values.get("items"))[:8]:
        if isinstance(item, dict):
            rows.append({"观察序号": item.get("sequence"), "原节点": item.get("node_key"),
                         "控制状态": item.get("state"), "原记录时间": item.get("source_time"),
                         "页面观察时间": item.get("observed_at")})
    url = "/api/instances/" + quote(instance_id, safe="") + "/observations"
    if node_key is not None:
        url += "?" + urlencode({"node_key": node_key})
    return _section("页面观察历史", "<p class='bounded-note'>页面观察时间是界面读到记录的时间，不是原事件发生时间。可重建缓存不替代控制记录。</p>"
        + f"<p>观察覆盖：{_text(values.get('coverage', '未提供'))}</p>"
        + render_json_value(rows, max_bytes=6144) + _link(url, "读取更多观察记录", class_name="source-link"))


def _trajectory_pagination(trajectory: dict, base: str, query: dict) -> str:
    page, pages, total = trajectory["page"], trajectory["total_pages"], trajectory["total"]
    def link(target: int, label: str) -> str:
        return _link(base + "?" + urlencode({**query, "page": target}) + "#trajectory", label)
    links = []
    if page > 1:
        links.extend((link(1, "首页"), link(page - 1, "上一页")))
    for number in range(max(1, page - 2), min(pages, page + 2) + 1):
        links.append("<span aria-current='page'>" + str(number) + "</span>" if number == page else link(number, str(number)))
    if page < pages:
        links.extend((link(page + 1, "下一页"), link(pages, "末页")))
    fields = "".join("<input type='hidden' name='" + html.escape(str(key), quote=True)
        + "' value='" + html.escape(str(value), quote=True) + "'>" for key, value in query.items())
    return ("<nav class='trajectory-pagination' aria-label='研究轨迹分页'><p>第 " + str(page) + " / " + str(pages)
        + " 页 · 共 " + str(total) + " 个节点</p><div class='page-links'>" + "".join(links) + "</div>"
        + ("<form method='get' action='" + html.escape(base, quote=True) + "#trajectory'>" + fields
            + "<label>跳至 <input type='number' name='page' min='1' max='" + str(pages) + "' value='"
            + str(page) + "' required aria-label='轨迹页码'> 页</label><button type='submit'>跳转</button></form>" if pages > 1 else "")
        + "</nav>")


def render_workbench(overview: dict, *, browse_base: str, csrf_token: str, can_manage: bool = False) -> bytes:
    instance = _dict(overview.get("instance"))
    instance_id = str(instance.get("instance_id", ""))
    base = safe_local_href(browse_base) or _path(instance_id)
    storage_state = _dict(overview.get("storage")).get("storage_state")
    trajectory = _dict(overview.get("trajectory"))
    query = _dict(overview.get("navigation_query"))
    refresh_query = {**query, **({"page": trajectory["page"]} if trajectory else {})}
    navigation = _link(base + ("?" + urlencode(refresh_query) if refresh_query else ""), "刷新记录", extra=" data-workbench-refresh")
    if can_manage:
        navigation += _link(base + "/manage", "整理与管理")
    header = ("<header class='workbench-header'><div class='workspace-brand'>科研工作台 <span>实例视图</span></div>"
        + "<div class='workspace-heading'><h1>" + _text(instance.get("title", "研究实例"), 160) + "</h1>"
        + "<span class='workspace-storage'>" + ("已归档 · 只读" if storage_state == "archived" else "研究资料") + "</span></div>"
        + "<nav aria-label='工作台导航'>" + navigation + "</nav><p class='workbench-update-status' role='status' aria-live='polite'>显示当前读取的记录。</p></header>")
    nodes = _dict(overview.get("nodes"))
    rows = [n for n in _list(nodes.get("items")) if isinstance(n, dict)]
    hidden_count = 0
    if _dict(overview.get("preferences")).get("show_artifacts") is False:
        visible = [n for n in rows if n.get("kind") != "artifact"]
        hidden_count = len(rows) - len(visible)
        rows = visible
    important = trajectory["items"] if trajectory else [n for n in rows if n.get("kind") != "artifact"]
    cursor = nodes.get("next_cursor")
    more = _link(base + "?" + urlencode({**refresh_query, "cursor":cursor}), "更早的研究记录 →", class_name="pagination-next") if cursor else "<p class='source-note'>本页已到记录末尾。</p>"
    trajectory_navigation = _trajectory_pagination(trajectory, base, query) if trajectory else more
    active = [n for n in _list(overview.get("active_tasks")) if isinstance(n, dict)]
    timeline = ("<section class='trajectory-panel' id='trajectory'><div class='panel-heading'><h2>研究轨迹</h2>"
        + "<span class='panel-count'>" + str(len(important)) + " 个节点</span></div>"
        + "<p class='source-note'>按登记时间从新到旧排列；成果登记见下方全部记录。新增记录后页码可能移动。</p><ol class='trajectory-list'>"
        + "".join(_node_card(n, instance_id, compact=True) for n in important) + "</ol>"
        + ("<p>暂无任务、审批或执行节点；成果可在下方全部记录查看。</p>" if not important else "") + trajectory_navigation + "</section>")
    active_panel = (fold_panel("多个活动分支", "<ul class='active-branches'>" + "".join(_node_card(n, instance_id, compact=True) for n in active) + "</ul>", count=len(active))
        if active else "<p class='source-note active-note'><span class='quiet-dot'></span>当前没有正在运行的任务</p>")
    display = _dict(overview.get("display_node"))
    title = "最近节点" if not overview.get("selected_node") else "选中节点"
    display_link = _link(_node_href(instance_id, display.get("key")), "打开节点详情 →") if display else ""
    presentation = render_presentation(overview.get("presentation"),
        evidence_href=lambda artifact, pointer: _evidence_href(instance_id, artifact, pointer),
        image_href=lambda artifact: base + "/evidence/" + quote(artifact, safe="") + "?format=image")
    content = ("<div class='workspace-grid'><aside class='workspace-sidebar'>" + _goal_panel(overview, instance_id) + timeline
        + "</aside><div class='workspace-main'><div class='panel-heading'><h2>" + title + "</h2>" + display_link + "</div>"
        + active_panel + presentation + _sealed_stages(display, instance_id) + "</div></div>")
    all_records = "<ol class='trajectory-list all-records'>" + "".join(_node_card(n, instance_id, compact=True) for n in rows) + "</ol>" + more
    footer = fold_panel("全部记录（含成果登记）", all_records, count=len(rows))
    if hidden_count:
        footer += ("<p class='source-note'>显示偏好隐藏了本页 " + str(hidden_count) + " 个成果登记节点。"
            + ("本页节点已按显示偏好隐藏。" if not rows else "")
            + (_link(base + "/manage", "在管理页恢复显示") if can_manage else "可从实例管理入口调整显示偏好。") + "</p>")
    footer += fold_panel("实例管理描述与观察记录", "<p>" + _text(overview.get("management_description", ""), 1200) + "</p>"
        + _observations(overview.get("observations"), instance_id))
    if overview.get("gaps"):
        footer += fold_panel("读取缺口", render_json_value(overview["gaps"], max_bytes=4096), count=len(overview["gaps"]))
    page = _document(instance.get("title", "研究实例"), header + content + footer, instance_id=instance_id,
        csrf_token=csrf_token, live_updates=storage_state not in ("archived", "archiving", "restoring"))
    return page




def _relationships(node: dict, instance_id: str) -> str:
    relationships = _dict(node.get("relationships"))
    panels = []
    for key, title in (("predecessors", "精确前序"), ("successors", "精确后继"), ("matching_reviews", "匹配审查")):
        refs = _list(relationships.get(key))
        rows = []
        for ref in refs[:30]:
            if isinstance(ref, dict):
                rows.append({**ref, "port_name": ref.get("relation", title)})
        panels.append(f"<div><h3>{title}</h3>{_references(rows, instance_id, max_bytes=8192)}</div>")
        if len(refs) > 30:
            panels.append(_PREVIEW)
    if relationships.get("has_more"):
        panels.append("<p class='source-gap'>关系查询达到读取上限；其余关系未在本页显示。</p>")
    return _section("记录关系", "<div class='relationship-columns'>" + "".join(panels) + "</div>" + _record_link(node, instance_id))


def _diagnostic_href(instance_id: str, node_key: str, reference: str, *, section: str = "summary", offset: int = 0, api: bool = False) -> str:
    base = "/api/instances/" + quote(instance_id, safe="") if api else _path(instance_id)
    return base + "/diagnostics/" + quote(reference, safe="") + "?" + urlencode({"node_key": node_key, "section": section, "offset": offset})


def _diagnostics(node: dict, instance_id: str) -> str:
    page = _dict(node.get("diagnostics"))
    events = _list(page.get("events"))
    rows, used = [], 0
    node_key = str(node.get("key", ""))
    for event in events:
        if not isinstance(event, dict):
            continue
        diagnostic = _dict(event.get("diagnostic"))
        engineering = _dict(diagnostic.get("engineering"))
        reference = engineering.get("reference")
        record = {key: value for key, value in event.items() if key != "diagnostic"}
        record["original_run"] = event.get("run_id", _dict(node.get("source")).get("object_id"))
        record["diagnostic"] = diagnostic
        link = ""
        if isinstance(reference, str):
            href = _diagnostic_href(instance_id, node_key, reference)
            api = _diagnostic_href(instance_id, node_key, reference, api=True)
            link = _link(href, "读取完整错误与日志", extra=f" data-diagnostic-api='{html.escape(api, quote=True)}'")
        row = "<li class='diagnostic-event'>" + render_json_value(record, max_bytes=4096) + link + "<div class='diagnostic-lazy' aria-live='polite'></div></li>"
        size = len(row.encode("utf-8"))
        if used + size > 32 * 1024:
            after = rows[-1][0] if rows else None
            more = _link(_node_href(instance_id, node_key) + "?" + urlencode({"diagnostic_after": after or 0}), "继续读取本页其余错误")
            rows.append((None, "<li>" + _PREVIEW + more + "</li>"))
            break
        rows.append((event.get("event_id"), row))
        used += size
    next_after = page.get("next_after")
    pagination = _link(_node_href(instance_id, node_key) + "?" + urlencode({"diagnostic_after": next_after}), "下一页错误记录", class_name="pagination-next") if next_after is not None else ""
    content = "<ol class='diagnostic-events'>" + "".join(row for _, row in rows) + "</ol>" if rows else "<p class='source-gap'>本次读取没有诊断事件；这不说明历史上没有错误。</p>"
    return _section("错误与日志", content + pagination, section_id="diagnostics")


def _sealed_stages(node: dict, instance_id: str) -> str:
    page = node.get("sealed_stages")
    if not isinstance(page, dict):
        return ""
    base = _node_href(instance_id, node["key"])
    def link(query, label):
        return _link(base + "?" + urlencode(query), label)
    phases = {"design": "设计", "implementation": "实现", "debug": "调试", "execution": "执行", "validity": "有效性"}
    kinds = {"author_conclusion": "作者科学结论", "scientific_material": "科学产物", "executor_observation": "执行器事实"}
    body = "<p>以下材料已封存；阶段交付不代表 Run 完成、科学资格或批准。</p>"
    if page.get("final_selection") == "sealed":
        body += "<p>最终报告已明确采用版本：</p>" + render_json_value(page.get("adopted_references"), max_bytes=8192)
    else:
        body += "<p>最终采用版本尚未封存。</p>"
    material = page.get("material")
    if isinstance(material, dict):
        body += "<h3>" + _text(material.get("reference")) + " · 科学材料原文</h3>"
        body += "<pre>" + html.escape(material.get("text", "")) + "</pre>"
        body += link({"stage_offset": 0}, "返回阶段历史")
        if material.get("next_text_offset") is not None:
            body += "<p>原文尚有后续内容。</p>" + link({"stage_reference": material["reference"],
                "stage_text_offset": material["next_text_offset"]}, "下一段原文")
    for item in page.get("items", []):
        body += "<article class='stage-delivery'><h3>" + _text(phases.get(item.get("stage"), item.get("stage")))
        body += " · " + _text(kinds.get(item.get("delivery_kind"), item.get("delivery_kind"))) + " · v" + str(item["version"]) + "</h3>"
        if item.get("origin") == "reused":
            body += "<p>复用已有封存材料，保留原始来源。</p>"
        if item.get("unavailable_materials"):
            body += "<p>部分原始依据未绑定到当前任务；请查看原材料的来源记录。</p>"
        if item.get("adopted") is not None:
            body += "<p>" + ("最终采用" if item["adopted"] else "未被最终报告采用") + "</p>"
        for key, label in (("conclusion", "结论"), ("remaining_question", "未决问题"), ("summary", "执行摘要")):
            if item.get(key):
                body += "<h4>" + label + "</h4><p>" + html.escape(item[key]) + "</p>"
        facts = {key: item[key] for key in ("limitations", "state", "mode", "exit_code", "terminal_state", "files", "file_count", "outputs", "missing_outputs") if key in item}
        if facts:
            body += render_json_value(facts, max_bytes=8192)
        body += "<p>依据/产物引用：</p><ul>"
        for source in item.get("materials", []):
            label = source.get("artifact_name") or source["reference"]
            target = (link({"stage_reference": source["reference"]}, label)
                if source["source_kind"] == "sealed_material" else
                _link(_node_href(instance_id, "artifact:" + label), label) if source.get("artifact_name") else _text(label))
            body += "<li>" + target + "</li>"
        body += "</ul>"
        body += link({"stage_reference": item["reference"]}, item["reference"] + " · 读取科学材料")
        if item.get("omitted_fields"):
            body += "<p>预览有省略，请按引用读取分段原文。</p>"
        body += "</article>"
    if not page.get("items") and material is None:
        body += "<p>此页没有已封存阶段材料。</p>"
    if page.get("offset", 0):
        body += link({"stage_offset": 0}, "首批阶段")
    if page.get("next_offset") is not None:
        body += link({"stage_offset": page["next_offset"]}, "后续阶段版本")
    return _section("已封存阶段与版本历史", body, section_id="sealed-stages")


def render_node(node: dict, *, instance_id: str, presentation: dict | None = None) -> bytes:
    key = str(node.get("key", ""))
    heading = _record_title(node)
    storage = _dict(node.get("storage")).get("storage_state")
    header = ("<header class='workbench-header'><nav aria-label='节点导航'>"
        + _link(_path(instance_id), "← 返回研究实例") + _link(_node_href(instance_id,key), "刷新节点")
        + "</nav><div class='workspace-heading'><h1>" + _text(heading) + "</h1>" + _state(node.get("state")) + "</div>"
        + _time(node.get("completed_at") or node.get("source_time") or node.get("created_at"))
        + ("<span class='archive-read-only'>已归档 · 只读</span>" if storage == "archived" else "")
        + "<p class='workbench-update-status' role='status'>显示当前读取的记录。</p></header>")
    science = render_presentation(presentation, show_summary=node.get("kind") != "approval",
        evidence_href=lambda artifact, pointer: _evidence_href(instance_id, artifact, pointer),
        image_href=lambda artifact: _path(instance_id) + "/evidence/" + quote(artifact, safe="") + "?format=image")
    approval = ""
    if node.get("kind") == "approval":
        request = _dict(_dict(node.get("request")).get("payload"))
        decision = _dict(_dict(node.get("decision")).get("payload"))
        kind, _ = approval_heading(request.get("kind"))
        question = request.get("question", "原审批事项需按原件读取。")
        approval = ("<section class='conclusion-card approval-readonly'><p class='eyebrow'>原审批记录 · 只读</p><h2>" + kind
            + "</h2><div class='conclusion-value'><span>人工决定</span><strong>"
            + _text(human_value(decision.get("selected_option")) if decision else "尚无决定") + "</strong></div>"
            + "<p class='conclusion-brief'>" + render_scientific_text(question, 320) + "</p>"
            + fold_panel("审批事项与原问题", render_json_value(question, max_bytes=8192, compact_numbers=True)) + "</section>")
        review_url = safe_local_href(node.get("review_url"))
        if review_url:
            approval += _link(review_url, "打开原审批请求", class_name="download-button")
    metadata = {"节点名称":node.get("name",key), "节点引用":key, "运行状态":human_value(node.get("state")),
        "操作":node.get("operation_id"), "原记录科学可用性声明":node.get("recorded_scientific_claim_admissible"),
        "当前资格记录":node.get("qualification"), "当前选择记录":node.get("current_selection"),
        "创建时间":node.get("created_at"), "完成时间":node.get("completed_at")}
    logs = _diagnostics(node, instance_id) if "diagnostics" in node else ""
    if node.get("kind") == "run":
        profile = _dict(_dict(node.get("execution_profile")).get("profile"))
        if profile:
            metadata.update({"模型（请求配置）": profile.get("model"),
                "推理强度（请求配置）": profile.get("reasoning_effort"),
                "新报告语言": profile.get("narrative_language"),
                "配置说明": "Run 创建时已冻结；不代表平台实际模型已核对。"})
        else:
            metadata["Agent 配置"] = "历史未单独记录"
        native = _dict(node.get("native_execution"))
        logs += "<h3>本地计算观测</h3>" + ("<p>未观测；无法据此判断计算耗时或错误。</p>" if native.get("coverage") in (None,"unobserved") else "")
        logs += render_json_value(native,max_bytes=6144) + fold_panel("工具时间与保存工作", render_json_value({"工具时间":node.get("tool_timing"),"恢复记录":node.get("recovery")},max_bytes=8192))
    if node.get("kind") == "execution":
        metadata["执行收集状态"] = human_value(node.get("collection_status"))
        logs += "<h3>外部执行与收集</h3>" + render_json_value({"收集":node.get("collection"),"观测":node.get("observation")},max_bytes=8192)
    details = fold_panel("依据与日志", logs + _relationships(node,instance_id))
    originals = ("<h3>原始输入</h3>" + _references(node.get("inputs"),instance_id)
        + "<h3>封存成果</h3>" + _references(node.get("outputs"),instance_id) + _record_link(node,instance_id))
    details += fold_panel("全部字段与原件", render_json_value(metadata,max_bytes=8192) + originals
        + _observations(node.get("observations"),instance_id,node_key=key), class_name="workbench-originals")
    if node.get("gaps"):
        details += fold_panel("读取缺口",render_json_value(node["gaps"],max_bytes=4096),count=len(node["gaps"]))
    body = header + "<div class='workspace-grid node-workspace'><aside class='workspace-sidebar'>" + _goal_panel(node,instance_id)
    body += "<p class='source-note'>运行完成、科学结论与人工批准分别记录。</p></aside><div class='workspace-main'>" + approval + science + _sealed_stages(node, instance_id) + details + "</div></div>"
    return _document(heading,body,instance_id=instance_id,live_updates=storage not in ("archived","archiving","restoring"))


def render_diagnostic(data: dict, *, instance_id: str, node_key: str, reference: str) -> bytes:
    section = data.get("section", "summary")
    text = data.get("text", "")
    display = None
    if section == "summary" and isinstance(text, str):
        try:
            display = render_json_value(json.loads(text), max_bytes=32 * 1024)
        except (ValueError, RecursionError):
            pass
    if display is None:
        display = "<pre class='diagnostic-text'>" + _text(text, 32768) + "</pre>"
    navigation = _link(_node_href(instance_id, node_key), "返回原节点")
    for choice in _list(data.get("available_sections"))[:8]:
        if isinstance(choice, str):
            navigation += _link(_diagnostic_href(instance_id, node_key, reference, section=choice), choice)
    next_offset = data.get("next_offset")
    pagination = _link(_diagnostic_href(instance_id, node_key, reference, section=str(section), offset=next_offset), "继续读取原日志") if type(next_offset) is int else ""
    body = (f"<header class='workbench-header'><h1>完整错误与日志</h1><nav>{navigation}</nav>"
            f"<p>原节点：{_text(node_key)} · 分段：{_text(section)} · 字节位置：{_text(data.get('offset', 0))} / {_text(data.get('total_bytes'))}</p></header>"
            + _section("原记录内容", display + pagination))
    return _document("完整错误与日志", body, instance_id=instance_id)


__all__ = ["render_workbench", "render_node", "render_diagnostic"]
