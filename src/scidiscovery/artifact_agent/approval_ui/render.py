"""Deterministic, escaped review workbench for frozen approval subjects."""

from __future__ import annotations

import html
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from ..schema.approval import LocalIdentityRef
from ..service.approvals import ApprovalReview


_FIELD_LABELS = {
    "schema_version": "数据版本",
    "input_type": "输入类型",
    "problem_id": "问题 ID",
    "title": "标题",
    "objective": "任务目标",
    "contradiction": "当前矛盾",
    "success_criteria": "成功条件",
    "failure_criteria": "失败条件",
    "constraints": "约束条件",
    "claim_scope": "结论适用范围",
    "out_of_scope": "不在本轮范围",
    "metrics": "评价指标",
    "resource_budget": "资源预算",
    "max_runs": "最多仿真次数",
    "max_parallel": "最大并行数",
    "max_wall_time_seconds": "最长运行时间（秒）",
    "max_storage_bytes": "最大存储量（字节）",
    "max_cost": "最大费用",
    "cost_currency": "费用币种",
    "stop_conditions": "停止条件",
    "source_refs": "来源文件",
    "assumptions": "明确假设",
    "open_questions": "未决问题",
    "approval_policy": "审批规则",
    "criterion_id": "条件 ID",
    "description": "说明",
    "observable": "检查对象",
    "condition": "判定条件",
    "metric_id": "指标 ID",
    "constraint_id": "约束 ID",
    "kind": "类型",
    "statement": "具体内容",
    "rationale": "理由",
    "condition_id": "停止条件 ID",
    "required_action": "触发后的操作",
    "statement_id": "假设 ID",
    "basis": "依据",
    "revocation_condition": "撤销条件",
    "question_id": "问题 ID",
    "question": "问题",
    "status": "状态",
    "resolution_needed": "解决所需信息",
    "policy_id": "规则 ID",
    "requirements": "审批要求",
    "requirement_id": "要求 ID",
    "subject_kind": "审批对象类型",
    "action": "可执行操作",
    "artifact_id": "资料 ID",
    "sha256": "内容哈希",
    "schema_id": "数据格式 ID",
    "bundle_id": "基础资料包 ID",
    "overview": "资料概览",
    "items": "关键科学信息",
    "item_id": "信息 ID",
    "item_type": "信息类型",
    "epistemic_status": "证据状态",
    "summary": "科学内容",
    "value": "数值或定义",
    "unit": "单位",
    "conditions": "适用条件",
    "tags": "任务标签",
    "locators": "原文证据位置",
    "source_coverage": "来源覆盖范围",
    "coverage": "覆盖程度",
    "locations": "已核对位置",
    "notes": "说明",
    "conflicts": "冲突与缺口",
    "conflict_id": "冲突 ID",
    "item_ids": "相关信息 ID",
    "resolution": "处理状态",
    "source_ref": "精确来源",
    "locator_type": "定位类型",
    "location": "原文位置",
    "excerpt": "证据摘录",
    "excerpt_sha256": "摘录哈希",
    "item_key": "信息键",
    "statement": "科学陈述",
    "scope": "适用范围",
    "uncertainty": "不确定度",
    "evidence_keys": "证据键",
    "rationale": "判断依据",
    "source_key": "来源键",
    "source_type": "来源类型",
    "title": "标题",
    "objective": "研究目标",
    "missing_inputs": "缺失输入",
    "open_questions": "未决问题",
    "frozen_input": "冻结输入",
    "web_snapshot": "网页快照",
    "user_statement": "用户陈述",
    "runtime_output": "仿真输出",
    "paper_fact": "论文事实",
    "runtime_observation": "仿真观察",
    "inference": "推断",
    "speculation": "推测",
    "dimensionless": "无量纲",
}

_VALUE_LABELS = {
    "paper": "论文任务",
    "custom": "用户自定义任务",
    "scientific": "科学约束",
    "permission": "权限约束",
    "time": "时间约束",
    "tool": "工具约束",
    "data": "数据约束",
    "other": "其他约束",
    "completion": "完成",
    "failure": "失败",
    "blocked": "阻塞",
    "human_review": "人工审批",
    "unknown": "未知",
    "partially_known": "部分已知",
    "pending": "待审批",
    "decided": "已决定",
    "expired": "已过期",
    "cancelled_by_human": "已由用户取消",
    "added": "新增",
    "removed": "删除",
    "changed": "修改",
    "fact": "事实",
    "parameter": "参数",
    "structure": "物理结构",
    "target_data": "目标数据",
    "constraint": "科学约束",
    "prior_observation": "已有观察",
    "assumption": "假设",
    "open_question": "未决问题",
    "source_fact": "来源事实",
    "user_defined": "用户定义",
    "derived_observation": "派生观察",
    "full": "完整核对",
    "partial": "部分核对",
    "metadata_only": "仅元数据",
    "unresolved": "未解决",
    "resolved": "已解决",
    "accepted_assumption": "已接受为假设",
}


@dataclass(frozen=True)
class ReviewContext:
    instance_name: str
    instance_title: str
    instance_objective: str
    approval_name: str
    approval_logical_name: str
    approval_revision: int
    instance_status: str = "active"


def render_review(
    review: ApprovalReview,
    *,
    access_token: str,
    identity: LocalIdentityRef,
    context: ReviewContext | None = None,
) -> bytes:
    request = review.request
    structured = _structured_subjects(review)
    problem = _first_schema(structured, "scidiscovery.problem-spec")
    scientific_foundation = _first_schema(
        structured, "scidiscovery.scientific-foundation.v1"
    )
    evidence_bundle = _first_schema(structured, "scidiscovery.evidence-bundle")
    instance_proposal = _first_schema(
        structured, "scidiscovery.research-instance-proposal.v1"
    )
    session_binding = _first_schema(
        structured, "scidiscovery.session-binding-proposal.v1"
    )
    diff = _first_schema(structured, "scidiscovery.problem-spec-diff")
    execution_request = _first_schema(
        structured, "scidiscovery.execution-request"
    )
    tcad_project = _first_schema(structured, "tcad.deck-project.v1")
    execution_review = (
        (execution_request[2], tcad_project[2])
        if execution_request is not None and tcad_project is not None
        else None
    )
    title = (
        "TCAD 执行审批"
        if execution_review is not None
        else _page_title(
            scientific_foundation
            or evidence_bundle
            or problem
            or instance_proposal
            or session_binding,
            request.question,
        )
    )
    status_label = _VALUE_LABELS.get(review.status, review.status)

    content_panel = (
        _render_tcad_execution_content(*execution_review)
        if execution_review is not None
        else (
            _render_instance_proposal_content(instance_proposal[2])
            if instance_proposal is not None
            else (
            _render_session_binding_content(session_binding[2])
            if session_binding is not None
            else (
            _render_scientific_foundation_content(scientific_foundation[2])
            if scientific_foundation is not None
            else (
                _render_evidence_bundle_content(evidence_bundle[2])
                if evidence_bundle is not None
                else (
                    _render_problem_content(problem[2])
                    if problem is not None
                    else _render_generic_overview(structured)
                )
            )))
        )
    )
    evidence_panel = (
        _render_tcad_parameter_bindings(execution_review[1])
        if execution_review is not None
        else (
            _render_scientific_foundation_sources(scientific_foundation[2])
            if scientific_foundation is not None
            else (
                _render_evidence_bundle_sources(evidence_bundle[2])
                if evidence_bundle is not None
                else (
                    _render_problem_evidence(problem[2])
                    if problem is not None
                    else _empty_state("当前审批对象没有专用的来源视图。")
                )
            )
        )
    )
    changes_panel = (
        _render_problem_diff(diff[2])
        if diff is not None
        else _empty_state("当前审批没有注册语义变更对象。")
    )
    raw_panel = _render_raw_subjects(review, structured, access_token)

    review_tabs = _render_review_tabs(
        primary_label=(
            "执行内容"
            if execution_review is not None
            else (
                "基础资料"
                if scientific_foundation is not None or evidence_bundle is not None
                else (
                    "实例草案"
                    if instance_proposal is not None
                    else (
                        "进程绑定"
                        if session_binding is not None
                        else ("合同内容" if problem is not None else "对象内容")
                    )
                )
            )
        ),
        change_count=_change_count(diff[2]) if diff is not None else 0,
    )
    decision = _render_decision(review, access_token, identity)
    technical = _render_request_metadata(review, status_label)
    context_panel = _render_review_context(context)

    page = (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=" + "de" + "vice-width,initial-scale=1'>"
        f"<title>{html.escape(title)} · 科研审批</title>"
        "<link rel='stylesheet' href='/static/style.css'>"
        "<script src='/static/app.js' defer></script></head><body>"
        "<header class='topbar'><div class='topbar-inner'>"
        "<div><p class='product-name'>Scientific Artifact Review</p>"
        f"<h1>{html.escape(title)}</h1></div>"
        f"<span class='status-badge status-{html.escape(review.status)}'>{html.escape(status_label)}</span>"
        "</div></header>"
        "<main class='page'>"
        f"{context_panel}"
        "<section class='review-intro'>"
        "<p class='eyebrow'>审批问题</p>"
        f"<p class='question'>{html.escape(request.question)}</p>"
        f"{technical}"
        "</section>"
        "<div class='review-layout'>"
        "<div class='review-main'>"
        f"{review_tabs}"
        f"<div id='panel-content' class='review-panel' role='tabpanel'>{content_panel}</div>"
        f"<div id='panel-evidence' class='review-panel' role='tabpanel' hidden>{evidence_panel}</div>"
        f"<div id='panel-changes' class='review-panel' role='tabpanel' hidden>{changes_panel}</div>"
        f"<div id='panel-raw' class='review-panel' role='tabpanel' hidden>{raw_panel}</div>"
        "</div>"
        f"<aside class='decision-column'>{decision}</aside>"
        "</div></main></body></html>"
    )
    return page.encode("utf-8")


def _render_review_context(context: ReviewContext | None) -> str:
    if context is None:
        return (
            "<section class='instance-context instance-context-unbound'>"
            "<div><p class='eyebrow'>研究实例</p>"
            "<strong>未绑定 ResearchInstance</strong></div>"
            "<p>这是兼容保留的旧审批，控制面没有可显示的实例归属。</p>"
            "</section>"
        )
    revision = (
        f" · 修订 {context.approval_revision}"
        if context.approval_revision > 1
        else ""
    )
    instance_label = (
        "待创建研究实例"
        if context.instance_status == "proposed"
        else (
            "待绑定研究实例"
            if context.instance_status == "binding"
            else "研究实例"
        )
    )
    return (
        "<section class='instance-context'>"
        f"<div class='instance-primary'><p class='eyebrow'>{instance_label}</p>"
        f"<strong>{html.escape(context.instance_title)}</strong>"
        f"<code>{html.escape(context.instance_name)}</code></div>"
        "<div class='instance-objective'><p class='eyebrow'>实例目标</p>"
        f"<p>{html.escape(context.instance_objective)}</p></div>"
        "<div class='approval-context'><p class='eyebrow'>审批项</p>"
        f"<strong>{html.escape(context.approval_name)}</strong>"
        f"<span>{html.escape(context.approval_logical_name)}{revision}</span></div>"
        "</section>"
    )


def _structured_subjects(
    review: ApprovalReview,
) -> list[tuple[int, object, object]]:
    result: list[tuple[int, object, object]] = []
    for index, (envelope, raw) in enumerate(review.subjects):
        base_type = envelope.media_type.split(";", 1)[0].lower()
        if base_type != "application/json":
            continue
        result.append((index, envelope, json.loads(raw)))
    return result


def _first_schema(
    subjects: Iterable[tuple[int, object, object]], schema_id: str
) -> tuple[int, object, Mapping[str, object]] | None:
    for index, envelope, value in subjects:
        if envelope.ref.schema_id == schema_id and isinstance(value, dict):
            return index, envelope, value
    return None


def _page_title(
    problem: tuple[int, object, Mapping[str, object]] | None,
    fallback: str,
) -> str:
    if problem is not None:
        title = problem[2].get("title")
        if isinstance(title, str) and title.strip():
            return title
    return fallback


def _render_review_tabs(*, primary_label: str, change_count: int) -> str:
    return (
        "<nav class='review-tabs' role='tablist' aria-label='审批内容'>"
        f"{_tab_button('content', primary_label, selected=True)}"
        f"{_tab_button('evidence', '来源与假设')}"
        f"{_tab_button('changes', '语义变更', badge=change_count)}"
        f"{_tab_button('raw', '原始数据')}"
        "</nav>"
    )


def _render_evidence_bundle_content(bundle: Mapping[str, object]) -> str:
    overview = _text(bundle.get("overview"))
    items = _object_list(bundle.get("items"))
    groups = (
        ("structure", "器件与物理结构"),
        ("parameter", "关键参数"),
        ("target_data", "目标数据"),
        ("fact", "其他事实"),
        ("constraint", "科学约束"),
        ("prior_observation", "已有观察"),
        ("assumption", "明确假设"),
        ("open_question", "未决问题"),
    )


def _render_scientific_foundation_content(
    foundation: Mapping[str, object],
) -> str:
    groups = (
        ("structure", "器件与物理结构"),
        ("parameter", "关键参数"),
        ("target_data", "目标数据"),
        ("fact", "其他事实"),
        ("constraint", "科学约束"),
        ("prior_observation", "已有观察"),
        ("assumption", "明确假设"),
        ("open_question", "未决问题"),
    )
    items = _object_list(foundation.get("items"))
    sections = []
    for index, (kind, title) in enumerate(groups, 2):
        selected = [item for item in items if item.get("item_type") == kind]
        if not selected:
            continue
        sections.append(
            "<section class='semantic-section'>"
            f"<div class='section-heading'><span class='section-number'>{index:02d}</span>"
            f"<div><p class='eyebrow'>结构化科学信息</p><h2>{html.escape(title)}</h2></div></div>"
            + "".join(_scientific_foundation_item_row(item) for item in selected)
            + "</section>"
        )
    return (
        "<section class='semantic-section evidence-lead'>"
        "<div class='section-heading'><span class='section-number'>01</span>"
        "<div><p class='eyebrow'>待人工确认的科学基础</p>"
        f"<h2>{html.escape(_text(foundation.get('title')))}</h2></div></div>"
        "<div class='statement-grid'>"
        f"{_statement('研究目标', _text(foundation.get('objective')), 'objective')}"
        f"{_statement('资料摘要', _text(foundation.get('summary')), 'scope')}"
        "</div></section>"
        + "".join(sections)
    )


def _scientific_foundation_item_row(item: Mapping[str, object]) -> str:
    kind = _text(item.get("item_type"))
    status = _text(item.get("epistemic_status"))
    value = item.get("value")
    unit = item.get("unit")
    value_text = _text(value) if value is not None else ""
    if value_text and isinstance(unit, str):
        value_text += f" {unit}"
    conditions = _object_list(item.get("conditions"))
    condition_text = "；".join(
        f"{_text(condition.get('name'))}={_text(condition.get('value'))}"
        + (f" {_text(condition.get('unit'))}" if condition.get("unit") else "")
        for condition in conditions
    )
    uncertainty = item.get("uncertainty")
    uncertainty_values = uncertainty if isinstance(uncertainty, dict) else {}
    uncertainty_text = _text(uncertainty_values.get("description"))
    if uncertainty_values.get("value") is not None:
        uncertainty_text += (
            f"：{_text(uncertainty_values.get('value'))}"
            f" {_text(uncertainty_values.get('unit'))}"
        )
    details = []
    if value_text:
        details.append(("数值或定义", value_text))
    details.append(("适用范围", _text(item.get("scope"))))
    if condition_text:
        details.append(("适用条件", condition_text))
    if uncertainty_text:
        details.append(("不确定度", uncertainty_text))
    if item.get("rationale"):
        details.append(("判断依据", _text(item.get("rationale"))))
    evidence_keys = "、".join(_string_list(item.get("evidence_keys")))
    if evidence_keys:
        details.append(("证据", evidence_keys))
    detail_html = "".join(
        f"<dt>{html.escape(label)}</dt><dd>{html.escape(text)}</dd>"
        for label, text in details
    )
    return (
        "<article class='evidence-row'>"
        f"<div class='evidence-marker'>{html.escape(_VALUE_LABELS.get(kind, kind))}</div><div>"
        f"<p class='row-title'>{html.escape(_text(item.get('statement')))}</p>"
        f"<span class='inline-status'>{html.escape(_VALUE_LABELS.get(status, status))}</span>"
        f"<dl class='detail-list'>{detail_html}</dl>"
        f"<code class='object-id'>{html.escape(_text(item.get('item_key')))}</code>"
        "</div></article>"
    )


def _render_scientific_foundation_sources(
    foundation: Mapping[str, object],
) -> str:
    evidence = _object_list(foundation.get("evidence"))
    conflicts = _object_list(foundation.get("conflicts"))
    source_rows = "".join(
        "<article class='policy-row'>"
        f"<p class='row-title'>{html.escape(_text(item.get('title')))}</p>"
        f"<p class='row-secondary'><strong>类型：</strong>{html.escape(_VALUE_LABELS.get(_text(item.get('source_type')), _text(item.get('source_type'))))}</p>"
        f"<p class='row-secondary'><strong>位置：</strong>{html.escape(_text(item.get('locator')))}</p>"
        + (
            f"<blockquote>{html.escape(_text(item.get('excerpt')))}</blockquote>"
            if item.get("excerpt")
            else ""
        )
        + f"<code class='object-id'>{html.escape(_text(item.get('source_key')))}</code>"
        "</article>"
        for item in evidence
    )
    conflict_rows = "".join(
        "<article class='evidence-row question-row'><div class='evidence-marker'>冲突</div><div>"
        f"<p class='row-title'>{html.escape(_text(item.get('statement')))}</p>"
        f"<span class='inline-status'>{html.escape(_VALUE_LABELS.get(_text(item.get('status')), _text(item.get('status'))))}</span>"
        + (
            f"<p class='row-secondary'><strong>处理：</strong>{html.escape(_text(item.get('resolution')))}</p>"
            if item.get("resolution")
            else ""
        )
        + f"<code class='object-id'>{html.escape(_text(item.get('conflict_key')))}</code>"
        "</div></article>"
        for item in conflicts
    )
    missing = _string_list(foundation.get("missing_inputs"))
    questions = _string_list(foundation.get("open_questions"))
    return (
        "<section class='semantic-section'><div class='section-heading'>"
        "<span class='section-number'>A</span><div><p class='eyebrow'>可追溯依据</p>"
        "<h2>关键来源</h2></div></div>"
        f"{source_rows or _empty_state('没有已声明来源。')}</section>"
        "<section class='semantic-section'><div class='section-heading'>"
        "<span class='section-number'>B</span><div><p class='eyebrow'>不可隐藏</p>"
        "<h2>冲突与处理</h2></div></div>"
        f"{conflict_rows or _empty_state('没有已登记冲突。')}</section>"
        "<section class='semantic-section'><div class='section-heading'>"
        "<span class='section-number'>C</span><div><p class='eyebrow'>仍需补充</p>"
        "<h2>缺失输入与未决问题</h2></div></div>"
        f"{_bullet_group('缺失输入', missing)}"
        f"{_bullet_group('未决问题', questions)}"
        "</section>"
    )
    sections = []
    for index, (kind, title) in enumerate(groups, 2):
        selected = [item for item in items if item.get("item_type") == kind]
        if not selected:
            continue
        rows = "".join(_evidence_item_row(item) for item in selected)
        sections.append(
            "<section class='semantic-section'>"
            f"<div class='section-heading'><span class='section-number'>{index:02d}</span>"
            f"<div><p class='eyebrow'>已提取并待审批</p><h2>{html.escape(title)}</h2></div></div>"
            f"{rows}</section>"
        )
    return (
        "<section class='semantic-section evidence-lead'>"
        "<div class='section-heading'><span class='section-number'>01</span>"
        "<div><p class='eyebrow'>首次资料提取产物</p>"
        "<h2>已提取的科学基础资料</h2></div></div>"
        f"{_statement('资料包概览', overview, 'objective')}"
        f"<code class='object-id'>{html.escape(_text(bundle.get('bundle_id')))}</code>"
        "</section>"
        + "".join(sections)
    )


def _evidence_item_row(item: Mapping[str, object]) -> str:
    kind = _text(item.get("item_type"))
    status = _text(item.get("epistemic_status"))
    value = item.get("value")
    unit = item.get("unit")
    value_text = ""
    if value is not None:
        value_text = _text(value)
        if isinstance(unit, str):
            value_text += f" {unit}"
    conditions = _object_list(item.get("conditions"))
    condition_text = "；".join(
        f"{_text(condition.get('name'))}={_text(condition.get('value'))}"
        + (f" {_text(condition.get('unit'))}" if condition.get("unit") else "")
        for condition in conditions
    )
    tags = " · ".join(_string_list(item.get("tags")))
    details = ""
    if value_text:
        details += f"<dt>数值或定义</dt><dd>{html.escape(value_text)}</dd>"
    if condition_text:
        details += f"<dt>适用条件</dt><dd>{html.escape(condition_text)}</dd>"
    if tags:
        details += f"<dt>任务标签</dt><dd>{html.escape(tags)}</dd>"
    return (
        "<article class='evidence-row'>"
        f"<div class='evidence-marker'>{html.escape(_VALUE_LABELS.get(kind, kind))}</div><div>"
        f"<p class='row-title'>{html.escape(_text(item.get('summary')))}</p>"
        f"<span class='inline-status'>{html.escape(_VALUE_LABELS.get(status, status))}</span>"
        f"<dl class='detail-list'>{details}</dl>"
        f"<code class='object-id'>{html.escape(_text(item.get('item_id')))}</code>"
        "</div></article>"
    )


def _render_evidence_bundle_sources(bundle: Mapping[str, object]) -> str:
    coverage = _object_list(bundle.get("source_coverage"))
    conflicts = _object_list(bundle.get("conflicts"))
    items = _object_list(bundle.get("items"))
    locators = [
        locator
        for item in items
        for locator in _object_list(item.get("locators"))
    ]
    coverage_rows = "".join(
        "<article class='policy-row'>"
        f"<p class='row-title'>{html.escape(_text(item.get('source_ref', {})))}</p>"
        f"<p class='row-secondary'><strong>覆盖：</strong>{html.escape(_VALUE_LABELS.get(_text(item.get('coverage')), _text(item.get('coverage'))))}</p>"
        f"<p class='row-secondary'>{html.escape(_text(item.get('notes')))}</p>"
        "</article>"
        for item in coverage
    )
    conflict_rows = "".join(
        "<article class='evidence-row question-row'><div class='evidence-marker'>缺口</div><div>"
        f"<p class='row-title'>{html.escape(_text(item.get('description')))}</p>"
        f"<span class='inline-status'>{html.escape(_VALUE_LABELS.get(_text(item.get('resolution')), _text(item.get('resolution'))))}</span>"
        f"<code class='object-id'>{html.escape(_text(item.get('conflict_id')))}</code>"
        "</div></article>"
        for item in conflicts
    )
    locator_rows = "".join(
        "<article class='policy-row'>"
        f"<p class='row-title'>{html.escape(_text(item.get('excerpt')))}</p>"
        f"<p class='row-secondary'><strong>位置：</strong>{html.escape(_text(item.get('location')))}</p>"
        f"<code class='object-id'>{html.escape(_short_hash(_text(item.get('excerpt_sha256'))))}</code>"
        "</article>"
        for item in locators
    )
    return (
        "<section class='semantic-section'><div class='section-heading'>"
        "<span class='section-number'>A</span><div><p class='eyebrow'>来源范围</p>"
        "<h2>资料覆盖</h2></div></div>"
        f"{coverage_rows or _empty_state('没有来源覆盖记录。')}</section>"
        "<section class='semantic-section'><div class='section-heading'>"
        "<span class='section-number'>B</span><div><p class='eyebrow'>不可隐藏</p>"
        "<h2>冲突与缺口</h2></div></div>"
        f"{conflict_rows or _empty_state('没有已登记冲突。')}</section>"
        "<section class='semantic-section'><div class='section-heading'>"
        "<span class='section-number'>C</span><div><p class='eyebrow'>原文核查</p>"
        "<h2>关键证据摘录</h2></div></div>"
        f"{locator_rows or _empty_state('没有来源摘录。')}</section>"
    )


def _tab_button(
    target: str,
    label: str,
    *,
    selected: bool = False,
    badge: int | None = None,
) -> str:
    state = "true" if selected else "false"
    active = " is-active" if selected else ""
    suffix = f"<span class='tab-count'>{badge}</span>" if badge else ""
    return (
        f"<button type='button' class='review-tab{active}' role='tab' "
        f"aria-selected='{state}' aria-controls='panel-{target}' "
        f"data-review-target='panel-{target}'>{html.escape(label)}{suffix}</button>"
    )


def _render_problem_content(problem: Mapping[str, object]) -> str:
    objective = _text(problem.get("objective"))
    contradiction = _text(problem.get("contradiction"))
    scope = _text(problem.get("claim_scope"))
    success = _object_list(problem.get("success_criteria"))
    failure = _object_list(problem.get("failure_criteria"))
    constraints = _object_list(problem.get("constraints"))
    out_of_scope = _string_list(problem.get("out_of_scope"))
    stops = _object_list(problem.get("stop_conditions"))
    budget = problem.get("resource_budget")

    return (
        "<nav class='section-index' aria-label='合同章节'>"
        "<a href='#overview'>目标与矛盾</a><a href='#criteria'>判定标准</a>"
        "<a href='#constraints'>约束</a><a href='#scope'>适用范围</a>"
        "<a href='#budget'>资源预算</a><a href='#stops'>停止条件</a>"
        "</nav>"
        "<section id='overview' class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>01</span>"
        "<div><p class='eyebrow'>研究合同</p><h2>目标与当前矛盾</h2></div></div>"
        "<div class='statement-grid'>"
        f"{_statement('任务目标', objective, 'objective')}"
        f"{_statement('当前矛盾', contradiction, 'contradiction')}"
        "</div></section>"
        "<section id='criteria' class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>02</span>"
        "<div><p class='eyebrow'>判定依据</p><h2>成功与失败标准</h2></div></div>"
        "<div class='criteria-columns'>"
        f"{_criteria_group('成功标准', success, 'success')}"
        f"{_criteria_group('失败标准', failure, 'failure')}"
        "</div></section>"
        "<section id='constraints' class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>03</span>"
        "<div><p class='eyebrow'>不可违反</p><h2>约束条件</h2></div></div>"
        f"{_constraints(constraints)}"
        "</section>"
        "<section id='scope' class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>04</span>"
        "<div><p class='eyebrow'>结论边界</p><h2>适用范围</h2></div></div>"
        f"{_statement('本轮可以支持的结论', scope, 'scope')}"
        f"{_bullet_group('本轮不处理', out_of_scope)}"
        "</section>"
        "<section id='budget' class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>05</span>"
        "<div><p class='eyebrow'>执行边界</p><h2>资源预算</h2></div></div>"
        f"{_resource_budget(budget)}"
        "</section>"
        "<section id='stops' class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>06</span>"
        "<div><p class='eyebrow'>流程出口</p><h2>停止条件</h2></div></div>"
        f"{_stop_conditions(stops)}"
        "</section>"
    )


def _statement(label: str, value: str, tone: str) -> str:
    return (
        f"<article class='statement statement-{tone}'>"
        f"<h3>{html.escape(label)}</h3><p>{html.escape(value)}</p></article>"
    )


def _criteria_group(
    title: str,
    items: list[Mapping[str, object]],
    tone: str,
) -> str:
    rows = "".join(_criterion_row(item, tone) for item in items)
    return (
        f"<div class='criteria-group criteria-{tone}'><h3>{html.escape(title)}"
        f"<span>{len(items)} 项</span></h3>{rows or _empty_state('未定义')}</div>"
    )


def _criterion_row(item: Mapping[str, object], tone: str) -> str:
    identifier = _text(item.get("criterion_id"))
    return (
        f"<article class='criterion-row criterion-row-{tone}'>"
        f"<p class='row-title'>{html.escape(_text(item.get('description')))}</p>"
        "<dl class='detail-list'>"
        f"<dt>检查对象</dt><dd>{html.escape(_text(item.get('observable')))}</dd>"
        f"<dt>通过条件</dt><dd>{html.escape(_text(item.get('condition')))}</dd>"
        "</dl>"
        f"<code class='object-id'>{html.escape(identifier)}</code></article>"
    )


def _constraints(items: list[Mapping[str, object]]) -> str:
    return "".join(
        "<article class='constraint-row'>"
        f"<span class='type-badge type-{html.escape(_text(item.get('kind')))}'>"
        f"{html.escape(_VALUE_LABELS.get(_text(item.get('kind')), _text(item.get('kind'))))}</span>"
        "<div>"
        f"<p class='row-title'>{html.escape(_text(item.get('statement')))}</p>"
        f"<p class='row-secondary'>{html.escape(_text(item.get('rationale')))}</p>"
        f"<code class='object-id'>{html.escape(_text(item.get('constraint_id')))}</code>"
        "</div></article>"
        for item in items
    ) or _empty_state("未定义约束。")


def _bullet_group(title: str, items: list[str]) -> str:
    rows = "".join(f"<li>{html.escape(item)}</li>" for item in items)
    return (
        f"<div class='bullet-group'><h3>{html.escape(title)}</h3>"
        f"<ul>{rows or '<li>无</li>'}</ul></div>"
    )


def _resource_budget(value: object) -> str:
    budget = value if isinstance(value, dict) else {}
    cells = (
        ("最多仿真", _format_number(budget.get("max_runs")), "次"),
        ("最大并行", _format_number(budget.get("max_parallel")), "个"),
        ("最长时间", _format_duration(budget.get("max_wall_time_seconds")), ""),
        ("最大存储", _format_bytes(budget.get("max_storage_bytes")), ""),
    )
    return (
        "<dl class='budget-grid'>"
        + "".join(
            f"<div><dt>{html.escape(label)}</dt><dd>{html.escape(amount)}"
            f"<span>{html.escape(unit)}</span></dd></div>"
            for label, amount, unit in cells
        )
        + "</dl>"
    )


def _stop_conditions(items: list[Mapping[str, object]]) -> str:
    return "".join(
        "<article class='stop-row'>"
        f"<span class='type-badge type-{html.escape(_text(item.get('kind')))}'>"
        f"{html.escape(_VALUE_LABELS.get(_text(item.get('kind')), _text(item.get('kind'))))}</span>"
        "<div>"
        f"<p class='row-title'>{html.escape(_text(item.get('condition')))}</p>"
        f"<p class='row-secondary'><strong>触发后：</strong>{html.escape(_text(item.get('required_action')))}</p>"
        f"<code class='object-id'>{html.escape(_text(item.get('condition_id')))}</code>"
        "</div></article>"
        for item in items
    ) or _empty_state("未定义停止条件。")


def _render_problem_evidence(problem: Mapping[str, object]) -> str:
    assumptions = _object_list(problem.get("assumptions"))
    questions = _object_list(problem.get("open_questions"))
    sources = _object_list(problem.get("source_refs"))
    policy = problem.get("approval_policy")
    policy_value = policy if isinstance(policy, dict) else {}
    requirements = _object_list(policy_value.get("requirements"))
    return (
        "<section class='semantic-section evidence-lead'>"
        "<div class='section-heading'><span class='section-number'>A</span>"
        "<div><p class='eyebrow'>需要重点判断</p><h2>明确假设</h2></div></div>"
        f"{_assumptions(assumptions)}"
        "</section>"
        "<section class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>B</span>"
        "<div><p class='eyebrow'>尚未解决</p><h2>未决问题</h2></div></div>"
        f"{_questions(questions)}"
        "</section>"
        "<section class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>C</span>"
        "<div><p class='eyebrow'>来源追踪</p><h2>冻结资料</h2></div></div>"
        f"{_sources_table(sources)}"
        "</section>"
        "<section class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>D</span>"
        "<div><p class='eyebrow'>人工权限</p><h2>审批规则</h2></div></div>"
        f"{_approval_requirements(requirements)}"
        "</section>"
    )


def _assumptions(items: list[Mapping[str, object]]) -> str:
    return "".join(
        "<article class='evidence-row assumption-row'>"
        "<div class='evidence-marker'>假设</div><div>"
        f"<p class='row-title'>{html.escape(_text(item.get('statement')))}</p>"
        f"<p class='row-secondary'><strong>依据：</strong>{html.escape(_text(item.get('basis')))}</p>"
        f"<p class='revocation'><strong>撤销条件：</strong>{html.escape(_text(item.get('revocation_condition')))}</p>"
        f"<code class='object-id'>{html.escape(_text(item.get('statement_id')))}</code>"
        "</div></article>"
        for item in items
    ) or _empty_state("没有声明假设。")


def _questions(items: list[Mapping[str, object]]) -> str:
    return "".join(
        "<article class='evidence-row question-row'>"
        "<div class='evidence-marker'>问题</div><div>"
        f"<p class='row-title'>{html.escape(_text(item.get('question')))}</p>"
        f"<p class='row-secondary'><strong>需要：</strong>{html.escape(_text(item.get('resolution_needed')))}</p>"
        f"<span class='inline-status'>{html.escape(_VALUE_LABELS.get(_text(item.get('status')), _text(item.get('status'))))}</span>"
        f"<code class='object-id'>{html.escape(_text(item.get('question_id')))}</code>"
        "</div></article>"
        for item in items
    ) or _empty_state("没有未决问题。")


def _sources_table(items: list[Mapping[str, object]]) -> str:
    rows = "".join(
        "<tr>"
        f"<td><strong>{html.escape(_text(item.get('artifact_id')))}</strong>"
        f"<small>{html.escape(_text(item.get('kind')))}</small></td>"
        f"<td>{html.escape(_text(item.get('schema_id')))}</td>"
        f"<td><code>{html.escape(_short_hash(_text(item.get('sha256'))))}</code></td>"
        "</tr>"
        for item in items
    )
    return (
        "<div class='table-scroll'><table class='source-table'>"
        "<thead><tr><th>资料</th><th>格式</th><th>内容哈希</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div>"
    ) if rows else _empty_state("没有冻结来源。")


def _approval_requirements(items: list[Mapping[str, object]]) -> str:
    return "".join(
        "<article class='policy-row'>"
        f"<p class='row-title'>{html.escape(_text(item.get('action')))}</p>"
        f"<p class='row-secondary'><strong>发生在：</strong>{html.escape(_text(item.get('condition')))}</p>"
        f"<p class='row-secondary'>{html.escape(_text(item.get('rationale')))}</p>"
        f"<code class='object-id'>{html.escape(_text(item.get('requirement_id')))}</code>"
        "</article>"
        for item in items
    ) or _empty_state("没有审批要求。")


def _render_problem_diff(diff: Mapping[str, object]) -> str:
    changes = _object_list(diff.get("changes"))
    string_only = bool(changes) and all(
        item.get("change") == "changed"
        and isinstance(item.get("before"), str)
        and isinstance(item.get("after"), str)
        for item in changes
    )
    notice = (
        "<div class='notice notice-caution'><strong>全部差异均为字符串变化。</strong>"
        "控制面无法仅凭字符串判定这是翻译还是科学语义修改，因此仍完整列出。</div>"
        if string_only
        else ""
    )
    rows = "".join(_change_row(item, index) for index, item in enumerate(changes, 1))
    return (
        "<section class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>Δ</span>"
        f"<div><p class='eyebrow'>精确字段变化</p><h2>{len(changes)} 项变更</h2></div></div>"
        f"{notice}{rows or _empty_state('没有字段变化。')}"
        "</section>"
    )


def _change_row(item: Mapping[str, object], index: int) -> str:
    change = _text(item.get("change"))
    pointer = _text(item.get("pointer"))
    before = _json_value(item.get("before")) if "before" in item else "未定义"
    after = _json_value(item.get("after")) if "after" in item else "未定义"
    return (
        "<details class='change-row'>"
        "<summary>"
        f"<span class='change-index'>{index:02d}</span>"
        f"<span class='change-badge change-{html.escape(change)}'>{html.escape(_VALUE_LABELS.get(change, change))}</span>"
        f"<code>{html.escape(pointer or '/')}</code>"
        "</summary>"
        "<div class='change-values'>"
        f"<div><h3>修改前</h3><pre>{html.escape(before)}</pre></div>"
        f"<div><h3>修改后</h3><pre>{html.escape(after)}</pre></div>"
        "</div></details>"
    )


def _render_generic_overview(
    subjects: list[tuple[int, object, object]],
) -> str:
    rows = "".join(
        "<article class='generic-row'>"
        f"<h3>{html.escape(envelope.ref.artifact_id)}</h3>"
        f"<p>{html.escape(envelope.ref.kind)} · {html.escape(envelope.ref.schema_id)}</p>"
        "</article>"
        for _, envelope, _ in subjects
    )
    return (
        "<section class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>01</span>"
        "<div><p class='eyebrow'>冻结对象</p><h2>审批对象概览</h2></div></div>"
        f"{rows or _empty_state('没有可显示的结构化对象。')}"
        "</section>"
    )


def _render_instance_proposal_content(proposal: Mapping[str, object]) -> str:
    non_effects = _string_list(proposal.get("non_effects"))
    boundaries = "".join(
        f"<li>{html.escape(item)}</li>" for item in non_effects
    ) or "<li>没有声明额外边界。</li>"
    return (
        "<section class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>01</span>"
        "<div><p class='eyebrow'>需要用户确认</p><h2>研究实例定义</h2></div></div>"
        "<dl class='metadata compact-metadata'>"
        f"<dt>实例名称</dt><dd><code>{html.escape(_text(proposal.get('name')))}</code></dd>"
        f"<dt>显示标题</dt><dd>{html.escape(_text(proposal.get('title')))}</dd>"
        f"<dt>研究目标</dt><dd>{html.escape(_text(proposal.get('objective')))}</dd>"
        f"<dt>批准后动作</dt><dd>{html.escape(_text(proposal.get('authorization_effect')))}</dd>"
        "</dl></section>"
        "<section class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>02</span>"
        "<div><p class='eyebrow'>权限边界</p><h2>本次批准不包含</h2></div></div>"
        f"<div class='bullet-group'><ul>{boundaries}</ul></div></section>"
    )


def _render_session_binding_content(proposal: Mapping[str, object]) -> str:
    candidates = _object_list(proposal.get("candidates"))
    rows = "".join(
        "<article class='generic-row'>"
        f"<h3>{html.escape(_text(item.get('title')))}</h3>"
        f"<p><code>{html.escape(_text(item.get('name')))}</code></p>"
        f"<p>{html.escape(_text(item.get('objective')))}</p>"
        "</article>"
        for item in candidates
    )
    boundaries = "".join(
        f"<li>{html.escape(item)}</li>"
        for item in _string_list(proposal.get("non_effects"))
    ) or "<li>没有声明额外边界。</li>"
    return (
        "<section class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>01</span>"
        "<div><p class='eyebrow'>需要用户确认</p><h2>选择进程归属</h2></div></div>"
        f"<p>{html.escape(_text(proposal.get('authorization_effect')))}</p>"
        f"<div class='generic-list'>{rows}</div></section>"
        "<section class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>02</span>"
        "<div><p class='eyebrow'>权限边界</p><h2>本次批准不包含</h2></div></div>"
        f"<div class='bullet-group'><ul>{boundaries}</ul></div></section>"
    )


def _render_tcad_execution_content(
    request: Mapping[str, object], project: Mapping[str, object]
) -> str:
    limits = project.get("resource_limits")
    limit_values = limits if isinstance(limits, dict) else {}
    arguments = _string_list(project.get("arguments"))
    outputs = _object_list(project.get("expected_outputs"))
    assertions = _object_list(project.get("runtime_assertions"))
    files = _object_list(project.get("files"))
    output_rows = "".join(
        "<tr>"
        f"<td><strong>{html.escape(_text(item.get('name')))}</strong></td>"
        f"<td><code>{html.escape(_text(item.get('relative_path')))}</code></td>"
        f"<td>{html.escape(_text(item.get('media_type')))}</td>"
        f"<td>{html.escape(_format_bytes(item.get('max_bytes')))}</td>"
        f"<td>{'是' if item.get('required') is True else '否'}</td>"
        "</tr>"
        for item in outputs
    )
    assertion_rows = "".join(
        "<article class='generic-row'>"
        f"<h3>{html.escape(_text(item.get('expected_output_name')))}</h3>"
        f"<p>{html.escape(_text(item.get('description')))}</p>"
        "</article>"
        for item in assertions
    )
    file_rows = "".join(_render_deck_file(item) for item in files)
    command = " ".join(
        [
            _text(project.get("tool_profile")),
            _text(project.get("entrypoint")),
            *arguments,
        ]
    )
    return (
        "<section class='semantic-section evidence-lead'>"
        "<div class='section-heading'><span class='section-number'>01</span>"
        "<div><p class='eyebrow'>本次授权的实际对象</p>"
        "<h2>将要执行的 TCAD 工程</h2></div></div>"
        "<div class='notice notice-caution'><strong>批准后会提交下列冻结工程。</strong>"
        "审批只授权这一次执行，不代表物理模型或论文拟合已经通过。</div>"
        "<dl class='metadata'>"
        f"<dt>执行 ID</dt><dd><code>{html.escape(_text(request.get('execution_id')))}</code></dd>"
        f"<dt>执行器</dt><dd>{html.escape(_text(request.get('executor')))}</dd>"
        f"<dt>准备方式</dt><dd>{html.escape(_text(request.get('preparation_profile')))}</dd>"
        f"<dt>工具配置</dt><dd>{html.escape(_text(project.get('tool_profile')))}</dd>"
        f"<dt>入口文件</dt><dd><code>{html.escape(_text(project.get('entrypoint')))}</code></dd>"
        f"<dt>完整命令</dt><dd><code>{html.escape(command)}</code></dd>"
        "</dl></section>"
        "<section class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>02</span>"
        "<div><p class='eyebrow'>执行边界</p><h2>资源上限</h2></div></div>"
        "<dl class='budget-grid'>"
        f"<div><dt>墙钟时间</dt><dd>{html.escape(_format_duration(limit_values.get('wall_time_seconds')))}</dd></div>"
        f"<div><dt>CPU 时间</dt><dd>{html.escape(_format_duration(limit_values.get('cpu_time_seconds')))}</dd></div>"
        f"<div><dt>最大内存</dt><dd>{html.escape(_format_bytes(limit_values.get('max_memory_bytes')))}</dd></div>"
        f"<div><dt>最大输出</dt><dd>{html.escape(_format_bytes(limit_values.get('max_output_bytes')))}</dd></div>"
        "</dl>"
        f"<p class='row-secondary'>最大进程数：{html.escape(_format_number(limit_values.get('max_processes')))}</p>"
        "</section>"
        "<section class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>03</span>"
        "<div><p class='eyebrow'>完成条件</p><h2>预期产物</h2></div></div>"
        "<div class='table-scroll'><table class='source-table'><thead><tr>"
        "<th>名称</th><th>相对路径</th><th>格式</th><th>大小上限</th><th>必需</th>"
        f"</tr></thead><tbody>{output_rows}</tbody></table></div>"
        f"{assertion_rows or _empty_state('没有声明运行时断言。')}"
        "</section>"
        "<section class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>04</span>"
        f"<div><p class='eyebrow'>冻结源码</p><h2>{len(files)} 个工程文件</h2></div></div>"
        f"{file_rows or _empty_state('工程没有可显示的文本文件。')}"
        "</section>"
    )


def _render_deck_file(item: Mapping[str, object]) -> str:
    path = _text(item.get("relative_path"))
    content = _text(item.get("content"))
    return (
        "<details class='raw-subject deck-file'>"
        f"<summary><span>{html.escape(path)}</span>"
        f"<small>{len(content.encode('utf-8'))} 字节</small></summary>"
        "<div class='raw-subject-body'>"
        f"<pre class='deck-source'><code>{html.escape(content)}</code></pre>"
        "</div></details>"
    )


def _render_tcad_parameter_bindings(project: Mapping[str, object]) -> str:
    bindings = _object_list(project.get("parameter_bindings"))
    rows = ""
    for item in bindings:
        evidence_class = _text(item.get("evidence_class"))
        evidence_source = _text(item.get("evidence_source"))
        evidence_locator = _text(item.get("evidence_locator"))
        rationale = _text(item.get("rationale"))
        if evidence_class:
            evidence = (
                f"<strong>{html.escape(evidence_class)}</strong><br>"
                f"{html.escape(evidence_source)}<br>"
                f"<code>{html.escape(evidence_locator)}</code><br>"
                f"<small>{html.escape(rationale)}</small>"
            )
        else:
            evidence = "<span class='muted'>未在执行件中声明</span>"
        rows += (
            "<tr>"
            f"<td><strong>{html.escape(_text(item.get('name')))}</strong></td>"
            f"<td>{html.escape(_text(item.get('declared_value')))} {html.escape(_text(item.get('unit')))}</td>"
            f"<td>{evidence}</td>"
            f"<td><code>{html.escape(_text(item.get('relative_path')))}</code><br>"
            f"<code>{html.escape(_text(item.get('locator')))}</code></td>"
            "</tr>"
        )
    return (
        "<section class='semantic-section'><div class='section-heading'>"
        "<span class='section-number'>P</span><div><p class='eyebrow'>源码中的精确绑定</p>"
        f"<h2>{len(bindings)} 个参数</h2></div></div>"
        "<p class='notice notice-caution'>这里同时展示声明值的源码绑定和提交方声明的证据来源；"
        "来源是否充分、物理解释是否成立仍需独立审查。</p>"
        "<div class='table-scroll'><table class='source-table'><thead><tr>"
        "<th>参数</th><th>声明值</th><th>证据来源与理由</th><th>源码定位</th>"
        f"</tr></thead><tbody>{rows}</tbody></table></div>"
        "</section>"
    )
    return (
        "<section class='semantic-section'><div class='section-heading'>"
        "<span class='section-number'>01</span><div><p class='eyebrow'>冻结对象</p>"
        f"<h2>{len(subjects)} 个结构化对象</h2></div></div>"
        f"{rows or _empty_state('没有结构化对象，请在原始数据页下载文件。')}"
        "</section>"
    )


def _render_raw_subjects(
    review: ApprovalReview,
    structured: list[tuple[int, object, object]],
    access_token: str,
) -> str:
    values = {index: value for index, _, value in structured}
    sections = []
    for index, (envelope, _) in enumerate(review.subjects):
        ref = envelope.ref
        href = (
            f"/subject/{html.escape(review.request.approval_id)}/{index}?token="
            f"{html.escape(access_token, quote=True)}"
        )
        metadata = (
            "<dl class='metadata compact-metadata'>"
            f"<dt>对象类型</dt><dd>{html.escape(ref.kind)}</dd>"
            f"<dt>数据格式</dt><dd>{html.escape(ref.schema_id)}</dd>"
            f"<dt>SHA-256</dt><dd><code>{ref.sha256}</code></dd>"
            f"<dt>大小</dt><dd>{envelope.size_bytes} 字节</dd>"
            "</dl>"
        )
        if index in values:
            content = (
                f"{_tree_toolbar()}<div class='tree tree-json'>"
                f"{_render_tree(values[index], '', 'root', root=True, json_style=True)}"
                "</div>"
            )
        else:
            content = "<p class='binary-note'>该对象不是 JSON，请下载冻结文件核验。</p>"
        sections.append(
            "<details class='raw-subject'>"
            f"<summary><span>{html.escape(ref.artifact_id)}</span>"
            f"<small>{html.escape(ref.schema_id)}</small></summary>"
            f"<div class='raw-subject-body'>{metadata}"
            f"<a class='download-button' href='{href}'>下载冻结文件</a>{content}</div>"
            "</details>"
        )
    return (
        "<section class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>{ }</span>"
        "<div><p class='eyebrow'>精确字节核验</p><h2>原始对象</h2></div></div>"
        + "".join(sections)
        + "</section>"
    )


def _render_decision(
    review: ApprovalReview,
    access_token: str,
    identity: LocalIdentityRef,
) -> str:
    if review.status != "pending":
        decision_value = (
            review.decision_ref.artifact_id
            if review.decision_ref is not None
            else "none"
        )
        return (
            "<section class='decision-panel terminal'><p class='eyebrow'>审批结果</p>"
            f"<h2>{html.escape(_VALUE_LABELS.get(review.status, review.status))}</h2>"
            f"<p class='decision-record'>决定记录<br><code>{html.escape(decision_value)}</code></p>"
            "</section>"
        )

    options = "".join(
        "<label class='decision-option'>"
        f"<input type='radio' name='selected_option' value='{html.escape(option.option_id, quote=True)}' "
        f"data-requires-rationale='{str(option.requires_rationale).lower()}' required>"
        "<span>"
        f"<strong>{html.escape(option.label)}</strong>"
        f"<small>{html.escape(option.description)}</small>"
        "</span></label>"
        for option in review.request.options
    )
    action = f"/review/{html.escape(review.request.approval_id)}/decision"
    return (
        "<section class='decision-panel'><p class='eyebrow'>人工决定</p>"
        "<h2>审阅结论</h2>"
        f"<form method='post' action='{action}'>"
        f"<input type='hidden' name='token' value='{html.escape(access_token, quote=True)}'>"
        f"<input type='hidden' name='csrf' value='{html.escape(review.csrf_token, quote=True)}'>"
        f"<input type='hidden' name='nonce' value='{html.escape(review.decision_nonce, quote=True)}'>"
        "<input type='hidden' name='confirm' value='confirm'>"
        f"<div class='decision-options'>{options}</div>"
        "<label class='rationale'><span>决定理由 <small class='rationale-state'>选填</small></span>"
        "<textarea name='rationale' maxlength='16384'></textarea></label>"
        f"<p class='identity'>审批身份 <strong>{html.escape(identity.display_name)}</strong>"
        f"<code>{html.escape(identity.identity_id)}</code></p>"
        "<button class='submit-decision' type='submit'>确认并记录决定</button>"
        "</form></section>"
    )


def _render_request_metadata(review: ApprovalReview, status_label: str) -> str:
    expires = review.request.expires_at or "无"
    return (
        "<details class='request-details'><summary>审批请求技术信息</summary>"
        "<dl class='metadata'>"
        f"<dt>请求类型</dt><dd>{html.escape(review.request.kind)}</dd>"
        f"<dt>请求 ID</dt><dd><code>{html.escape(review.request.approval_id)}</code></dd>"
        f"<dt>请求哈希</dt><dd><code>{review.request_ref.sha256}</code></dd>"
        f"<dt>对象集合哈希</dt><dd><code>{review.request.subject_set_sha256}</code></dd>"
        f"<dt>过期时间</dt><dd>{html.escape(expires)}</dd>"
        f"<dt>当前状态</dt><dd>{html.escape(status_label)}</dd>"
        "</dl></details>"
    )


def _tree_toolbar() -> str:
    return (
        "<div class='tree-toolbar'>"
        "<button class='tree-action' type='button' data-tree-action='expand' "
        "title='展开全部' aria-label='展开全部'>+</button>"
        "<button class='tree-action' type='button' data-tree-action='collapse' "
        "title='折叠全部' aria-label='折叠全部'>-</button>"
        "</div>"
    )


def _render_tree(
    value: object,
    pointer: str,
    label: str,
    *,
    root: bool = False,
    json_style: bool = False,
) -> str:
    escaped_label = _render_label(label, json_style=json_style)
    escaped_pointer = html.escape(pointer or "/", quote=True)
    if isinstance(value, dict):
        children = "".join(
            _render_tree(
                value[key],
                pointer + "/" + str(key).replace("~", "~0").replace("/", "~1"),
                str(key),
                json_style=json_style,
            )
            for key in value
        )
        empty = "<div class='tree-empty'>{}</div>" if not value else ""
        suffix = " 个字段" if not json_style else " 个属性"
        open_attribute = " open" if root else ""
        return (
            "<details class='tree-node tree-branch' "
            f"data-pointer='{escaped_pointer}'{open_attribute}>"
            "<summary>"
            f"<span class='tree-key'>{escaped_label}</span>"
            f"<span class='tree-kind'>对象 · {len(value)}{suffix}</span>"
            "</summary>"
            f"<div class='tree-children'>{children}{empty}</div>"
            "</details>"
        )
    if isinstance(value, list):
        children = "".join(
            _render_tree(
                item,
                pointer + f"/{index}",
                f"[{index}]",
                json_style=json_style,
            )
            for index, item in enumerate(value)
        )
        empty = "<div class='tree-empty'>[]</div>" if not value else ""
        open_attribute = " open" if root else ""
        return (
            "<details class='tree-node tree-branch' "
            f"data-pointer='{escaped_pointer}'{open_attribute}>"
            "<summary>"
            f"<span class='tree-key'>{escaped_label}</span>"
            f"<span class='tree-kind'>数组 · {len(value)} 个项目</span>"
            "</summary>"
            f"<div class='tree-children'>{children}{empty}</div>"
            "</details>"
        )
    rendered = json.dumps(value, ensure_ascii=False, allow_nan=False)
    preview = rendered if len(rendered) <= 96 else rendered[:93] + "..."
    separator = ":" if json_style else ""
    return (
        "<details class='tree-node tree-value' "
        f"data-pointer='{escaped_pointer}'>"
        "<summary>"
        f"<span class='tree-key'>{escaped_label}</span>"
        f"<span class='tree-separator'>{separator}</span>"
        f"<span class='tree-preview'>{html.escape(preview)}</span>"
        f"<span class='tree-kind'>{_json_type(value)}</span>"
        "</summary>"
        "<div class='tree-value-full'>"
        f"<div class='tree-path'>路径 <code>{escaped_pointer}</code></div>"
        f"<code>{html.escape(rendered)}</code>"
        "</div></details>"
    )


def _render_label(label: str, *, json_style: bool) -> str:
    if json_style:
        return f"<code>{html.escape(json.dumps(label, ensure_ascii=False))}</code>"
    translated = _FIELD_LABELS.get(label, label)
    original = ""
    if translated != label:
        original = f"<small class='tree-source-key'>{html.escape(label)}</small>"
    return f"<span>{html.escape(translated)}</span>{original}"


def _json_type(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    raise TypeError(f"unsupported JSON value type: {type(value).__name__}")


def _change_count(diff: Mapping[str, object]) -> int:
    changes = diff.get("changes")
    return len(changes) if isinstance(changes, list) else 0


def _object_list(value: object) -> list[Mapping[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _text(value: object) -> str:
    if value is None:
        return "未定义"
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _json_value(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2)


def _format_number(value: object) -> str:
    return str(value) if isinstance(value, (int, float)) else "未定义"


def _format_duration(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "未定义"
    seconds = int(value)
    if seconds % 3600 == 0:
        return f"{seconds // 3600} 小时"
    if seconds % 60 == 0:
        return f"{seconds // 60} 分钟"
    return f"{seconds} 秒"


def _format_bytes(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "未定义"
    amount = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if amount < 1024 or unit == "TiB":
            rendered = f"{amount:.1f}" if amount % 1 else f"{amount:.0f}"
            return f"{rendered} {unit}"
        amount /= 1024
    return "未定义"


def _short_hash(value: str) -> str:
    return f"{value[:10]}…{value[-8:]}" if len(value) > 22 else value


def _empty_state(message: str) -> str:
    return f"<p class='empty-state'>{html.escape(message)}</p>"


__all__ = ["render_review"]
