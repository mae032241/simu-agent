"""Deterministic, escaped review workbench for frozen approval subjects."""

from __future__ import annotations

import html
import json
import shlex
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from urllib.parse import quote, urlsplit

from ..schema.approval import ApprovalPresentation, LocalIdentityRef
from ..service.approvals import ApprovalReview


MAX_PREVIEW_BYTES = 16 * 1024 * 1024
MAX_PREVIEW_DIMENSION = 8192
MAX_PREVIEW_PIXELS = 40_000_000
MAX_FIGURE_PANELS = 32
MAX_FIGURE_SERIES_PER_PANEL = 64
MAX_FIGURE_TOTAL_SERIES = 256
MAX_FIGURE_METRICS = 128
MAX_FIGURE_AMBIGUITIES = 128
MAX_FIGURE_PREVIEWS = 16
MAX_FIGURE_TEXT = 1024


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
    "active": "进行中",
    "proposed": "待创建",
    "binding": "待绑定",
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
    "qualified": "已通过资格校验",
    "revision_required": "需要修订",
    "available": "可用",
    "unavailable": "不可用",
    "observed": "已观测",
    "eligible": "可用于定量比较",
    "pass": "通过",
    "fail": "不通过",
    "not_applicable": "不适用",
    "revise": "修订",
    "matched": "已匹配",
    "legend": "图例",
    "annotation": "标注",
    "caption": "图注",
    "line": "实线轨迹",
    "fit_segment": "拟合片段",
    "external_reproduction": "外部定量复现",
    "qualified_segments": "合格连续区间",
    "confirmed": "多源一致",
    "authoritative_single": "权威单源",
    "single_source": "普通单源",
    "not_comparable": "条件不可比",
    "conflict": "来源冲突",
    "missing": "参数缺失",
    "assumed": "建模假设",
    "review_required": "需要重点审阅",
    "geometry": "几何结构",
    "material": "材料",
    "composition": "材料组分",
    "doping": "掺杂",
    "process": "工艺",
    "physics_model": "物理模型",
    "contact_boundary": "接触与边界",
    "initial_condition": "初始条件",
    "required": "必需",
    "recommended": "建议",
    "optional": "可选",
    "paper_fact": "论文事实",
    "user_defined": "用户给定",
    "assumption": "建模假设",
    "primary_paper": "原始论文",
    "secondary_paper": "二手论文",
    "authoritative_database": "权威数据库",
    "standard": "标准",
    "manufacturer_datasheet": "厂商数据表",
    "user_source": "用户资料",
    "runtime_source": "运行结果",
}

_TUNING_PURPOSE_LABELS = {
    "uncertainty_sweep": "不确定性扫描",
    "calibration": "校准扫描",
}

_TUNING_BASIS_LABELS = {
    "conflicting_sources": "来源冲突",
    "engineering_prior": "工程先验",
    "human_review": "人工复核",
}


_APPROVAL_KIND_LABELS = {
    "scientific_foundation": "科学基础审批",
    "execution_authorization": "执行授权审批",
    "instance_creation": "研究实例创建审批",
    "research_instance_registration": "研究实例创建审批",
    "session_binding": "进程绑定审批",
    "research_session_binding": "进程绑定审批",
}


_JSON_TYPE_LABELS = {
    "null": "空值",
    "boolean": "布尔值",
    "string": "字符串",
    "integer": "整数",
    "number": "数值",
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
    display_structured = _localized_subjects(structured, request.presentation)
    problem = _first_schema(display_structured, "scidiscovery.problem-spec")
    scientific_foundation = _first_schema(
        display_structured, "scidiscovery.scientific-foundation.v1"
    )
    evidence_bundle = _first_schema(
        display_structured, "scidiscovery.evidence-bundle"
    )
    figure_manifest = _first_schema(
        display_structured, "scidiscovery.figure-evidence-manifest.v1"
    )
    evidence_audit = _first_schema(
        display_structured, "scidiscovery.evidence-audit.v1"
    )
    parameter_requirements = _first_schema(
        display_structured, "scidiscovery.device-parameter-requirements.v1"
    )
    device_parameters = _first_schema(
        display_structured, "scidiscovery.device-parameter-set.v1"
    )
    source_catalog = _first_schema(
        display_structured, "scidiscovery.evidence-source-catalog.v1"
    )
    parameter_coverage = _first_schema(
        display_structured, "scidiscovery.device-parameter-coverage.v1"
    )
    parameter_review = (
        (
            parameter_requirements[2],
            device_parameters[2],
            source_catalog[2],
            parameter_coverage[2],
        )
        if all(
            item is not None
            for item in (
                parameter_requirements,
                device_parameters,
                source_catalog,
                parameter_coverage,
            )
        )
        else None
    )
    instance_proposal = _first_schema(
        display_structured, "scidiscovery.research-instance-proposal.v1"
    )
    session_binding = _first_schema(
        display_structured, "scidiscovery.session-binding-proposal.v1"
    )
    diff = _first_schema(display_structured, "scidiscovery.problem-spec-diff")
    execution_request = _first_schema(
        display_structured, "scidiscovery.execution-request"
    )
    tcad_project = _first_schema(display_structured, "tcad.deck-project.v1")
    reviewed_package = _first_schema(
        display_structured, "tcad.reviewed-deck-package.v2"
    )
    reviewed_payload = reviewed_package[2] if reviewed_package is not None else None
    reviewed_project = (
        reviewed_payload.get("project")
        if isinstance(reviewed_payload, dict)
        else None
    )
    reviewed_capability = (
        reviewed_payload.get("capability")
        if isinstance(reviewed_payload, dict)
        else None
    )
    execution_project = (
        tcad_project[2]
        if tcad_project is not None
        else reviewed_project if isinstance(reviewed_project, dict) else None
    )
    execution_review = (
        (
            execution_request[2],
            execution_project,
            reviewed_capability if isinstance(reviewed_capability, dict) else None,
            reviewed_payload if isinstance(reviewed_payload, dict) else None,
        )
        if execution_request is not None and execution_project is not None
        else None
    )
    title = (
        "TCAD 执行审批"
        if execution_review is not None
        else (
            (
                "器件关键参数审批 · "
                f"{_bounded_text(parameter_requirements[2].get('title'))}"
            )
            if parameter_review is not None
            else (
            (
                "科学基础与图证据 · "
                f"{_bounded_text(figure_manifest[2].get('figure_key'))}"
            )
            if scientific_foundation is not None and figure_manifest is not None
            else (
            f"图证据 · {_bounded_text(figure_manifest[2].get('figure_key'))}"
            if figure_manifest is not None
            else _page_title(
                scientific_foundation
                or evidence_bundle
                or problem
                or instance_proposal
                or session_binding,
                request.question,
            )
            ))
        )
    )
    status_label = _VALUE_LABELS.get(review.status, review.status)
    figure_previews = _figure_previews(review, access_token)

    detail_panel = (
        _render_tcad_execution_content(*execution_review)
        if execution_review is not None
        else (
            _render_instance_proposal_content(instance_proposal[2])
            if instance_proposal is not None
            else (
            _render_session_binding_content(session_binding[2])
            if session_binding is not None
            else (
            (
                _render_scientific_foundation_content(scientific_foundation[2])
                + _render_figure_manifest_content(
                    figure_manifest[2],
                    "",
                )
            )
            if scientific_foundation is not None and figure_manifest is not None
            else (
            _render_missing_foundation_parameters()
            + _render_figure_manifest_content(figure_manifest[2], "")
            if figure_manifest is not None
            else (
                _render_scientific_foundation_content(scientific_foundation[2])
                if scientific_foundation is not None
                else (
                    _render_evidence_bundle_content(evidence_bundle[2])
                    if evidence_bundle is not None
                    else (
                        _render_problem_content(problem[2])
                        if problem is not None
                        else _render_generic_overview(display_structured)
                    )
                )
            )))
            )
        )
    )
    if parameter_review is not None:
        supporting_detail = detail_panel
        detail_panel = _render_device_parameter_content(
            parameter_review[0],
            parameter_review[1],
            parameter_review[2],
            parameter_review[3],
        )
        if evidence_audit is not None:
            detail_panel += _render_evidence_audit_content(evidence_audit[2])
        detail_panel += _render_collapsible_supporting_content(supporting_detail)
    elif evidence_audit is not None and execution_review is None:
        detail_panel += _render_evidence_audit_content(evidence_audit[2])
    evidence_panel = (
        _render_tcad_parameter_bindings(execution_review[1])
        if execution_review is not None
        else (
            (
                _render_scientific_foundation_sources(scientific_foundation[2])
                + _render_figure_manifest_evidence(figure_manifest[2])
            )
            if scientific_foundation is not None and figure_manifest is not None
            else (
            _render_figure_manifest_evidence(figure_manifest[2])
            if figure_manifest is not None
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
        )
    )
    if parameter_review is not None:
        evidence_panel = _render_device_parameter_sources(
            parameter_review[0],
            parameter_review[1],
            parameter_review[2],
            parameter_review[3],
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
                "科学基础与图证据"
                if scientific_foundation is not None and figure_manifest is not None
                else (
                    "参数明细"
                    if parameter_review is not None
                    else (
                "图证据"
                if figure_manifest is not None
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
                ))
                )
            )
        ),
        change_count=_change_count(diff[2]) if diff is not None else 0,
        evidence_label="来源追溯" if parameter_review is not None else "来源与假设",
    )
    decision = _render_decision(review, access_token, identity)
    technical = _render_request_metadata(review, status_label)
    context_panel = _render_review_context(context)
    summary_panel = (
        _render_device_parameter_summary(
            question=request.question,
            requirements=parameter_review[0],
            parameters=parameter_review[1],
            catalog=parameter_review[2],
            coverage=parameter_review[3],
            audit=evidence_audit[2] if evidence_audit is not None else None,
            foundation=(
                scientific_foundation[2]
                if scientific_foundation is not None
                else None
            ),
        )
        if parameter_review is not None
        else _render_approval_summary(
            question=request.question,
            figure_previews=figure_previews,
        )
    )

    page = (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=" + "de" + "vice-width,initial-scale=1'>"
        f"<title>{html.escape(title)} · 科研审批</title>"
        "<link rel='stylesheet' href='/static/style.css'>"
        "<script src='/static/app.js' defer></script></head><body>"
        "<header class='topbar'><div class='topbar-inner'>"
        "<div><p class='product-name'>科研证据审批</p>"
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
        f"<div id='panel-summary' class='review-panel' role='tabpanel'>{summary_panel}</div>"
        f"<div id='panel-content' class='review-panel' role='tabpanel' hidden>{detail_panel}</div>"
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
            "<strong>未绑定研究实例</strong></div>"
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


def _localized_subjects(
    subjects: list[tuple[int, object, object]],
    presentation: ApprovalPresentation | None,
) -> list[tuple[int, object, object]]:
    if presentation is None:
        return subjects
    translations: dict[int, list[tuple[str, str]]] = {}
    for item in presentation.translations:
        translations.setdefault(item.subject_index, []).append(
            (item.json_pointer, item.text)
        )
    localized = []
    for index, envelope, value in subjects:
        replacements = translations.get(index)
        if not replacements:
            localized.append((index, envelope, value))
            continue
        copied = json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
        for pointer, text in replacements:
            _replace_json_pointer_string(copied, pointer, text)
        localized.append((index, envelope, copied))
    return localized


def _replace_json_pointer_string(value: object, pointer: str, text: str) -> None:
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer.split("/")[1:]]
    current = value
    for part in parts[:-1]:
        if isinstance(current, dict):
            current = current[part]
        elif isinstance(current, list):
            current = current[int(part)]
        else:
            raise ValueError("display translation pointer traverses a scalar")
    final = parts[-1]
    if isinstance(current, dict):
        if not isinstance(current[final], str):
            raise ValueError("display translation target is not a string")
        current[final] = text
        return
    if isinstance(current, list):
        index = int(final)
        if not isinstance(current[index], str):
            raise ValueError("display translation target is not a string")
        current[index] = text
        return
    raise ValueError("display translation pointer parent is a scalar")


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


def _render_approval_summary(*, question: str, figure_previews: str) -> str:
    preview_content = figure_previews or _empty_state(
        "本审批对象集没有可安全预览的图像附件。"
    )
    return (
        "<section class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>审</span>"
        "<div><p class='eyebrow'>中文审批摘要</p><h2>本次审批说明</h2></div></div>"
        f"<p class='question'>{html.escape(question)}</p>"
        "<p class='bounded-note'>本页仅提供中文辅助说明；冻结科研对象的精确原文、"
        "数据格式与哈希未被翻译或修改，可在“完整内容”和“原始数据”页核验。</p>"
        "</section>"
        "<section class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>图</span>"
        "<div><p class='eyebrow'>证据预览</p><h2>源图与审计图</h2></div></div>"
        f"{preview_content}</section>"
    )


def _render_device_parameter_summary(
    *,
    question: str,
    requirements: Mapping[str, object],
    parameters: Mapping[str, object],
    catalog: Mapping[str, object],
    coverage: Mapping[str, object],
    audit: Mapping[str, object] | None,
    foundation: Mapping[str, object] | None,
) -> str:
    requirement_items = _object_list(requirements.get("parameters"))
    claims = {
        _text(item.get("parameter_key")): item
        for item in _object_list(parameters.get("claims"))
    }
    coverage_items = {
        _text(item.get("parameter_key")): item
        for item in _object_list(coverage.get("items"))
    }
    attention = [
        item
        for item in requirement_items
        if _parameter_needs_attention(
            coverage_items.get(_text(item.get("parameter_key")), {}),
            claims.get(_text(item.get("parameter_key")), {}),
        )
    ]
    sources = _object_list(catalog.get("sources"))
    independent_works = {
        _text(item.get("work_key")) for item in sources if item.get("work_key")
    }
    audit_checks = _object_list(audit.get("checks")) if audit is not None else []
    audit_failures = [
        item for item in audit_checks if _text(item.get("status")) != "pass"
    ]
    coverage_status = _text(coverage.get("status"))
    tunable_count = sum(_parameter_has_tuning(item) for item in claims.values())
    conclusion, explanation, tone = _parameter_review_conclusion(
        coverage_status,
        _integer(coverage.get("review_count")),
        _integer(coverage.get("blocking_count")),
        audit_checks,
        audit_failures,
    )
    metrics = (
        ("覆盖结论", _VALUE_LABELS.get(coverage_status, coverage_status), tone),
        ("参数需求", f"{len(requirement_items)} 项", "neutral"),
        ("多源确认", f"{_integer(coverage.get('confirmed_count'))} 项", "good"),
        ("需人工关注", f"{_integer(coverage.get('review_count'))} 项", "warn"),
        ("阻塞项", f"{_integer(coverage.get('blocking_count'))} 项", "bad"),
        ("可调参数", f"{tunable_count} 项", "warn" if tunable_count else "neutral"),
        ("独立来源", f"{len(independent_works)} 个", "neutral"),
    )
    metric_cards = "".join(
        "<div class='parameter-metric'>"
        f"<dt>{html.escape(label)}</dt>"
        f"<dd class='metric-{tone_name}'>{html.escape(value)}</dd></div>"
        for label, value, tone_name in metrics
    )
    attention_rows = "".join(
        _render_parameter_attention_row(
            item,
            claims.get(_text(item.get("parameter_key")), {}),
            coverage_items.get(_text(item.get("parameter_key")), {}),
        )
        for item in attention
    )
    if not attention_rows:
        attention_rows = _empty_state("覆盖报告中没有需要人工处置的参数。")
    audit_note = (
        "未附独立审计"
        if not audit_checks
        else (
            f"独立审计 {len(audit_checks)} 项全部通过"
            if not audit_failures
            else f"独立审计仍有 {len(audit_failures)} 项未通过"
        )
    )
    required_groups = _group_parameter_requirements(
        [item for item in requirement_items if item.get("criticality") == "required"]
    )
    key_groups = "".join(
        _render_parameter_quick_group(
            category,
            items,
            claims,
            coverage_items,
            {
                _text(source.get("source_key")): source
                for source in sources
            },
        )
        for category, items in required_groups
    )
    return (
        "<section class='semantic-section parameter-summary-lead'>"
        "<p class='eyebrow'>先看结论，再核对异常</p>"
        "<div class='parameter-conclusion'>"
        f"<span class='conclusion-mark conclusion-{tone}' aria-hidden='true'></span>"
        f"<div><h2>{html.escape(conclusion)}</h2>"
        f"<p>{html.escape(explanation)}</p></div></div>"
        f"<p class='question parameter-question'>{html.escape(question)}</p>"
        f"<p class='audit-summary'>{html.escape(audit_note)}</p>"
        f"<dl class='parameter-metrics'>{metric_cards}</dl>"
        "</section>"
        "<section class='semantic-section attention-section'>"
        "<div class='section-heading'><span class='section-number'>!</span>"
        "<div><p class='eyebrow'>优先处理</p><h2>需要关注的参数</h2></div></div>"
        f"<div class='parameter-attention-list'>{attention_rows}</div>"
        f"{_render_parameter_gap_context(foundation)}</section>"
        "<section class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>K</span>"
        "<div><p class='eyebrow'>按科学类别折叠</p><h2>必需参数速览</h2></div></div>"
        "<p class='bounded-note'>这里只展示标记为“必需”的参数；展开类别即可核对候选值。"
        "完整条件、覆盖说明和建议项位于“参数明细”页签。</p>"
        f"<div class='parameter-category-list'>{key_groups or _empty_state('没有标记为必需的参数。')}</div>"
        "</section>"
    )


def _render_review_tabs(
    *, primary_label: str, change_count: int, evidence_label: str = "来源与假设"
) -> str:
    return (
        "<nav class='review-tabs' role='tablist' aria-label='审批内容'>"
        f"{_tab_button('summary', '审批摘要', selected=True)}"
        f"{_tab_button('content', primary_label)}"
        f"{_tab_button('evidence', evidence_label)}"
        f"{_tab_button('changes', '语义变更', badge=change_count)}"
        f"{_tab_button('raw', '原始数据')}"
        "</nav>"
    )


def _render_figure_manifest_content(
    manifest: Mapping[str, object], previews: str
) -> str:
    source = manifest.get("source")
    source_values = source if isinstance(source, dict) else {}
    panels = _object_list(manifest.get("panels"))
    visible_panels = panels[:MAX_FIGURE_PANELS]
    series_budget = MAX_FIGURE_TOTAL_SERIES
    panel_rows: list[str] = []
    for panel in visible_panels:
        all_series = _object_list(panel.get("series"))
        visible_series = all_series[
            : min(MAX_FIGURE_SERIES_PER_PANEL, series_budget)
        ]
        series_budget -= len(visible_series)
        series_rows = "".join(_render_figure_series_summary(item) for item in visible_series)
        omitted = len(all_series) - len(visible_series)
        omitted_note = (
            f"<p class='bounded-note'>另有 {omitted} 个系列未在专用视图展开；"
            "请在原始数据页核验。</p>"
            if omitted > 0
            else ""
        )
        calibration = panel.get("axis_calibration")
        calibration_values = calibration if isinstance(calibration, dict) else {}
        panel_rows.append(
            "<article class='figure-panel'>"
            "<div class='figure-panel-heading'>"
            f"<h3>{html.escape(_bounded_text(panel.get('panel_key')))}</h3>"
            f"<p>{html.escape(_bounded_text(panel.get('citation')))}</p></div>"
            "<div class='axis-grid'>"
            f"{_render_axis_calibration('X', calibration_values.get('x'))}"
            f"{_render_axis_calibration('Y', calibration_values.get('y'))}"
            "</div>"
            f"<div class='figure-series-list'>{series_rows or _empty_state('未声明系列。')}</div>"
            f"{omitted_note}</article>"
        )
        if series_budget <= 0:
            break
    omitted_panels = len(panels) - len(panel_rows)
    panel_note = (
        f"<p class='bounded-note'>另有 {omitted_panels} 个面板未在专用视图展开；"
        "请在原始数据页核验。</p>"
        if omitted_panels > 0
        else ""
    )
    return (
        "<section class='semantic-section evidence-lead'>"
        "<div class='section-heading'><span class='section-number'>01</span>"
        "<div><p class='eyebrow'>冻结图证据</p>"
        f"<h2>{html.escape(_bounded_text(manifest.get('figure_key')))}</h2></div></div>"
        "<dl class='metadata figure-source'>"
        f"<dt>资格状态</dt><dd><strong>{html.escape(_VALUE_LABELS.get(_text(manifest.get('status')), _text(manifest.get('status'))))}</strong></dd>"
        f"<dt>输入来源</dt><dd>{html.escape(_bounded_text(source_values.get('source_name')))}</dd>"
        f"<dt>页码 / 图号</dt><dd>{html.escape(_bounded_text(source_values.get('page')))} / "
        f"{html.escape(_bounded_text(source_values.get('figure')))}</dd>"
        f"<dt>源图尺寸</dt><dd>{html.escape(_bounded_text(source_values.get('width')))} × "
        f"{html.escape(_bounded_text(source_values.get('height')))} px</dd>"
        f"<dt>源图 SHA-256</dt><dd><code>{html.escape(_bounded_text(source_values.get('image_sha256')))}</code></dd>"
        "</dl></section>"
        "<section class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>02</span>"
        "<div><p class='eyebrow'>同一审批对象集</p><h2>源图与审计叠加图</h2></div></div>"
        f"{previews or _empty_state('没有通过格式、签名和尺寸检查的 PNG、JPEG 或 WebP 图像。')}"
        "</section>"
        "<section class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>03</span>"
        f"<div><p class='eyebrow'>坐标与系列</p><h2>{len(panels)} 个面板</h2></div></div>"
        f"{''.join(panel_rows) or _empty_state('manifest 未声明面板。')}{panel_note}</section>"
    )


def _render_axis_calibration(axis_name: str, value: object) -> str:
    axis = value if isinstance(value, dict) else {}
    return (
        "<dl class='axis-calibration'>"
        f"<dt>{axis_name} 轴</dt>"
        f"<dd><strong>{html.escape(_bounded_text(axis.get('scale')))}</strong> · "
        f"{html.escape(_bounded_text(axis.get('unit')))}</dd>"
        f"<dt>像素范围</dt><dd>{html.escape(_bounded_text(axis.get('pixel_min')))} — "
        f"{html.escape(_bounded_text(axis.get('pixel_max')))}</dd>"
        f"<dt>数值范围</dt><dd>{html.escape(_bounded_text(axis.get('value_min')))} — "
        f"{html.escape(_bounded_text(axis.get('value_max')))}</dd>"
        f"<dt>重投影误差</dt><dd>{html.escape(_bounded_text(axis.get('reprojection_error_px')))} px</dd>"
        "</dl>"
    )


def _render_figure_series_summary(series: Mapping[str, object]) -> str:
    return (
        "<article class='figure-series'>"
        f"<h4>{html.escape(_bounded_text(series.get('series_key')))}</h4>"
        f"<p><strong>{html.escape(_bounded_text(series.get('label')))}</strong> · "
        f"{html.escape(_VALUE_LABELS.get(_text(series.get('primitive_kind')), _text(series.get('primitive_kind'))))}</p>"
        "<dl class='detail-list figure-series-metrics'>"
        f"<dt>数据项</dt><dd><code>{html.escape(_bounded_text(series.get('data_item')))}</code></dd>"
        f"<dt>点数</dt><dd>{html.escape(_bounded_text(series.get('point_count')))}</dd>"
        f"<dt>可见比例</dt><dd>{html.escape(_bounded_text(series.get('visible_fraction')))}</dd>"
        f"<dt>最大缺口</dt><dd>{html.escape(_bounded_text(series.get('max_gap_px')))} px</dd>"
        f"<dt>不确定度</dt><dd>{html.escape(_bounded_text(series.get('uncertainty_px')))} px</dd>"
        "</dl></article>"
    )


def _render_figure_manifest_evidence(manifest: Mapping[str, object]) -> str:
    panels = _object_list(manifest.get("panels"))[:MAX_FIGURE_PANELS]
    mapping_rows: list[str] = []
    series_budget = MAX_FIGURE_TOTAL_SERIES
    for panel in panels:
        panel_key = _bounded_text(panel.get("panel_key"))
        series = _object_list(panel.get("series"))[
            : min(MAX_FIGURE_SERIES_PER_PANEL, series_budget)
        ]
        series_budget -= len(series)
        mapping_rows.extend(
            _render_figure_binding(panel_key, item) for item in series
        )
        if series_budget <= 0:
            break

    metrics = manifest.get("metrics")
    metric_rows = ""
    metric_note = ""
    if isinstance(metrics, dict):
        metric_items = list(metrics.items())
        metric_rows = "".join(
            "<tr>"
            f"<td><code>{html.escape(_bounded_text(key))}</code></td>"
            f"<td>{html.escape(_bounded_json(value))}</td></tr>"
            for key, value in metric_items[:MAX_FIGURE_METRICS]
        )
        if len(metric_items) > MAX_FIGURE_METRICS:
            metric_note = (
                f"<p class='bounded-note'>另有 {len(metric_items) - MAX_FIGURE_METRICS} "
                "项指标未在专用视图展开。</p>"
            )
    else:
        metric_note = "<p class='notice notice-caution'>manifest 未声明 metrics。</p>"

    ambiguity_value = manifest.get("ambiguities")
    ambiguity_rows = ""
    ambiguity_note = ""
    if isinstance(ambiguity_value, list):
        ambiguities = [item for item in ambiguity_value if isinstance(item, dict)]
        ambiguity_rows = "".join(
            _render_figure_ambiguity(item)
            for item in ambiguities[:MAX_FIGURE_AMBIGUITIES]
        )
        if len(ambiguities) > MAX_FIGURE_AMBIGUITIES:
            ambiguity_note = (
                f"<p class='bounded-note'>另有 {len(ambiguities) - MAX_FIGURE_AMBIGUITIES} "
                "项歧义未在专用视图展开。</p>"
            )
        elif not ambiguities:
            ambiguity_note = "<p class='empty-state'>manifest 明确声明没有未决歧义。</p>"
    else:
        ambiguity_note = (
            "<p class='notice notice-caution'>manifest 未声明 ambiguities；不得推断为无歧义。</p>"
        )

    return (
        "<section class='semantic-section evidence-lead'>"
        "<div class='section-heading'><span class='section-number'>L</span>"
        "<div><p class='eyebrow'>显式身份证据</p><h2>图例、标注与图注绑定</h2></div></div>"
        f"{''.join(mapping_rows) or _empty_state('没有显式系列绑定；不得推断系列身份。')}"
        "</section>"
        "<section class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>M</span>"
        "<div><p class='eyebrow'>提取质量</p><h2>指标</h2></div></div>"
        "<div class='table-scroll'><table class='source-table figure-metrics'><thead><tr>"
        f"<th>指标</th><th>值</th></tr></thead><tbody>{metric_rows}</tbody></table></div>{metric_note}"
        "</section>"
        "<section class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>?</span>"
        "<div><p class='eyebrow'>失败关闭</p><h2>歧义与候选项</h2></div></div>"
        f"{ambiguity_rows}{ambiguity_note}</section>"
    )


def _render_figure_binding(panel_key: str, series: Mapping[str, object]) -> str:
    binding = series.get("binding")
    binding_values = binding if isinstance(binding, dict) else {}
    alternatives = binding_values.get("alternatives")
    alternative_values = alternatives if isinstance(alternatives, list) else []
    alternatives_text = ", ".join(
        _bounded_text(item) for item in alternative_values[:16]
    ) or "未声明"
    return (
        "<article class='figure-binding'>"
        f"<div><span class='inline-status'>{html.escape(_VALUE_LABELS.get(_text(binding_values.get('status')), _text(binding_values.get('status'))))}</span>"
        f"<strong>{html.escape(panel_key)} / {html.escape(_bounded_text(series.get('series_key')))}</strong></div>"
        "<dl class='metadata compact-metadata'>"
        f"<dt>声明系列</dt><dd>{html.escape(_bounded_text(series.get('label')))}</dd>"
        f"<dt>绑定来源</dt><dd>{html.escape(_VALUE_LABELS.get(_text(binding_values.get('source')), _text(binding_values.get('source'))))}</dd>"
        f"<dt>可见文字</dt><dd>{html.escape(_bounded_text(binding_values.get('visible_label')))}</dd>"
        f"<dt>置信度</dt><dd>{html.escape(_bounded_text(binding_values.get('confidence')))}</dd>"
        f"<dt>备选项</dt><dd>{html.escape(alternatives_text)}</dd>"
        "</dl></article>"
    )


def _render_figure_ambiguity(item: Mapping[str, object]) -> str:
    candidates = item.get("candidates")
    candidate_values = candidates if isinstance(candidates, list) else []
    candidates_text = ", ".join(
        _bounded_text(value) for value in candidate_values[:16]
    ) or "未声明"
    return (
        "<article class='evidence-row question-row'>"
        "<div class='evidence-marker'>歧义</div><div>"
        f"<h3>{html.escape(_bounded_text(item.get('panel_key')))} / "
        f"{html.escape(_bounded_text(item.get('series_key')))}</h3>"
        f"<p>{html.escape(_bounded_text(item.get('message')))}</p>"
        f"<p class='row-secondary'><strong>候选：</strong>{html.escape(candidates_text)}</p>"
        "</div></article>"
    )


def _figure_previews(review: ApprovalReview, access_token: str) -> str:
    rows: list[str] = []
    eligible = 0
    for index, (envelope, content) in enumerate(review.subjects):
        preview = _safe_raster_preview(content, envelope.media_type)
        if preview is None:
            continue
        eligible += 1
        if len(rows) >= MAX_FIGURE_PREVIEWS:
            continue
        media_type, width, height = preview
        collection = envelope.labels.get("collection")
        item = envelope.labels.get("item")
        label_parts = [value for value in (collection, item) if value]
        label = "/".join(label_parts) or envelope.ref.artifact_id
        path = (
            f"/preview/{quote(review.request.approval_id, safe='')}/{index}?token="
            f"{quote(access_token, safe='')}"
        )
        rows.append(
            "<figure class='figure-preview'>"
            f"<img src='{html.escape(path, quote=True)}' "
            f"alt='{html.escape(label, quote=True)}' width='{width}' height='{height}'>"
            f"<figcaption><strong>{html.escape(label)}</strong>"
            f"<span>{html.escape(media_type)} · {width} × {height} px</span></figcaption>"
            "</figure>"
        )
    omitted = eligible - len(rows)
    note = (
        f"<p class='bounded-note'>另有 {omitted} 张合格栅格图未在专用视图展开。</p>"
        if omitted > 0
        else ""
    )
    return f"<div class='figure-preview-grid'>{''.join(rows)}</div>{note}" if rows else ""


def _safe_raster_preview(
    content: bytes, declared_media_type: str
) -> tuple[str, int, int] | None:
    if not content or len(content) > MAX_PREVIEW_BYTES:
        return None
    base_type = declared_media_type.split(";", 1)[0].strip().lower()
    dimensions: tuple[int, int] | None = None
    detected_type = ""
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        detected_type = "image/png"
        dimensions = _png_dimensions(content)
    elif content.startswith(b"\xff\xd8"):
        detected_type = "image/jpeg"
        dimensions = _jpeg_dimensions(content)
    elif content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        detected_type = "image/webp"
        dimensions = _webp_dimensions(content)
    if detected_type != base_type or dimensions is None:
        return None
    width, height = dimensions
    if (
        width <= 0
        or height <= 0
        or width > MAX_PREVIEW_DIMENSION
        or height > MAX_PREVIEW_DIMENSION
        or width * height > MAX_PREVIEW_PIXELS
    ):
        return None
    return detected_type, width, height


def _png_dimensions(content: bytes) -> tuple[int, int] | None:
    if (
        len(content) < 33
        or content[8:12] != b"\x00\x00\x00\r"
        or content[12:16] != b"IHDR"
    ):
        return None
    return int.from_bytes(content[16:20], "big"), int.from_bytes(
        content[20:24], "big"
    )


def _jpeg_dimensions(content: bytes) -> tuple[int, int] | None:
    position = 2
    sof_markers = {
        0xC0, 0xC1, 0xC2, 0xC3,
        0xC5, 0xC6, 0xC7,
        0xC9, 0xCA, 0xCB,
        0xCD, 0xCE, 0xCF,
    }
    while position < len(content):
        if content[position] != 0xFF:
            return None
        while position < len(content) and content[position] == 0xFF:
            position += 1
        if position >= len(content):
            return None
        marker = content[position]
        position += 1
        if marker in {0x00, 0xD8} or 0xD0 <= marker <= 0xD7:
            continue
        if marker in {0xD9, 0xDA} or position + 2 > len(content):
            return None
        segment_length = int.from_bytes(content[position : position + 2], "big")
        if segment_length < 2 or position + segment_length > len(content):
            return None
        if marker in sof_markers:
            if segment_length < 7:
                return None
            height = int.from_bytes(content[position + 3 : position + 5], "big")
            width = int.from_bytes(content[position + 5 : position + 7], "big")
            return width, height
        position += segment_length
    return None


def _webp_dimensions(content: bytes) -> tuple[int, int] | None:
    if len(content) < 30 or int.from_bytes(content[4:8], "little") + 8 != len(content):
        return None
    chunk_type = content[12:16]
    chunk_size = int.from_bytes(content[16:20], "little")
    if chunk_size > len(content) - 20:
        return None
    if chunk_type == b"VP8X" and chunk_size >= 10:
        width = 1 + int.from_bytes(content[24:27], "little")
        height = 1 + int.from_bytes(content[27:30], "little")
        return width, height
    if chunk_type == b"VP8L" and chunk_size >= 5 and content[20] == 0x2F:
        packed = int.from_bytes(content[21:25], "little")
        return 1 + (packed & 0x3FFF), 1 + ((packed >> 14) & 0x3FFF)
    if chunk_type == b"VP8 " and chunk_size >= 10 and content[23:26] == b"\x9d\x01\x2a":
        width = int.from_bytes(content[26:28], "little") & 0x3FFF
        height = int.from_bytes(content[28:30], "little") & 0x3FFF
        return width, height
    return None


def _bounded_text(value: object) -> str:
    if value is None:
        return "未声明"
    if isinstance(value, str):
        rendered = value
    elif isinstance(value, (bool, int, float)):
        rendered = str(value)
    else:
        rendered = _bounded_json(value)
    if len(rendered) <= MAX_FIGURE_TEXT:
        return rendered
    return rendered[: MAX_FIGURE_TEXT - 1] + "…"


def _bounded_json(value: object) -> str:
    try:
        rendered = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError):
        rendered = "未声明"
    if len(rendered) <= MAX_FIGURE_TEXT:
        return rendered
    return rendered[: MAX_FIGURE_TEXT - 1] + "…"


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


def _render_scientific_foundation_content(
    foundation: Mapping[str, object],
) -> str:
    groups = (
        ("structure", "器件与物理结构"),
        ("target_data", "目标数据"),
        ("fact", "其他事实"),
        ("constraint", "科学约束"),
        ("prior_observation", "已有观察"),
        ("assumption", "明确假设"),
        ("open_question", "未决问题"),
    )
    items = _object_list(foundation.get("items"))
    objective_contract = foundation.get("objective_contract")
    objective_contract_panel = (
        _render_objective_contract(objective_contract)
        if isinstance(objective_contract, Mapping)
        else ""
    )
    parameter_items = [
        item for item in items if item.get("item_type") == "parameter"
    ]
    parameter_index = 3 if objective_contract_panel else 2
    parameter_panel = (
        "<section class='semantic-section'>"
        f"<div class='section-heading'><span class='section-number'>{parameter_index:02d}</span>"
        "<div><p class='eyebrow'>必须显式展示</p><h2>实验与模型参数</h2></div></div>"
        + (
            "".join(
                _scientific_foundation_item_row(item) for item in parameter_items
            )
            if parameter_items
            else _empty_state("当前 foundation 未声明可审查的实验或模型参数。")
        )
        + "</section>"
    )
    sections = []
    for index, (kind, title) in enumerate(groups, parameter_index + 1):
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
        + objective_contract_panel
        + parameter_panel
        + "".join(sections)
    )


def _render_device_parameter_content(
    requirements: Mapping[str, object],
    parameters: Mapping[str, object],
    catalog: Mapping[str, object],
    coverage: Mapping[str, object],
) -> str:
    claims = {
        _text(item.get("parameter_key")): item
        for item in _object_list(parameters.get("claims"))
    }
    coverage_items = {
        _text(item.get("parameter_key")): item
        for item in _object_list(coverage.get("items"))
    }
    sources = {
        _text(item.get("source_key")): item
        for item in _object_list(catalog.get("sources"))
    }
    requirement_items = _object_list(requirements.get("parameters"))
    attention_rows = "".join(
        _render_parameter_attention_row(
            item,
            claims.get(_text(item.get("parameter_key")), {}),
            coverage_items.get(_text(item.get("parameter_key")), {}),
        )
        for item in requirement_items
        if _parameter_needs_attention(
            coverage_items.get(_text(item.get("parameter_key")), {}),
            claims.get(_text(item.get("parameter_key")), {}),
        )
    )
    category_sections = "".join(
        _render_parameter_category(
            category,
            items,
            claims,
            coverage_items,
            sources,
        )
        for category, items in _group_parameter_requirements(requirement_items)
    )
    status = _text(coverage.get("status"))
    return (
        "<section class='semantic-section evidence-lead'>"
        "<div class='section-heading'><span class='section-number'>P</span>"
        "<div><p class='eyebrow'>器件关键参数总览</p>"
        f"<h2>{html.escape(_text(requirements.get('title')))}</h2></div></div>"
        "<dl class='metadata'>"
        f"<dt>覆盖结论</dt><dd><strong>{html.escape(_VALUE_LABELS.get(status, status))}</strong></dd>"
        f"<dt>多源确认</dt><dd>{html.escape(_text(coverage.get('confirmed_count')))} 项</dd>"
        f"<dt>需人工关注</dt><dd>{html.escape(_text(coverage.get('review_count')))} 项</dd>"
        f"<dt>阻塞项</dt><dd>{html.escape(_text(coverage.get('blocking_count')))} 项</dd>"
        "</dl></section>"
        "<section class='semantic-section attention-section'>"
        "<div class='section-heading'><span class='section-number'>!</span>"
        "<div><p class='eyebrow'>异常优先</p><h2>需要关注</h2></div></div>"
        f"<div class='parameter-attention-list'>{attention_rows or _empty_state('没有需要人工处置的参数。')}</div>"
        "</section>"
        "<section class='semantic-section parameter-matrix'>"
        "<div class='section-heading'><span class='section-number'>参数</span>"
        "<div><p class='eyebrow'>按类别分组，按名称检索</p><h2>器件参数矩阵</h2></div></div>"
        "<p class='bounded-note'>点击任一参数展开完整审计信息；默认摘要只保留"
        "基准值、验证状态和独立来源数。</p>"
        f"{_render_parameter_search('在参数名称、键、材料或状态中搜索…')}"
        f"<div class='parameter-category-list'>{category_sections}</div></section>"
    )


def _render_parameter_category(
    category: str,
    requirements: list[Mapping[str, object]],
    claims: Mapping[str, Mapping[str, object]],
    coverage_items: Mapping[str, Mapping[str, object]],
    sources: Mapping[str, Mapping[str, object]],
) -> str:
    attention_count = sum(
        _parameter_needs_attention(
            coverage_items.get(_text(item.get("parameter_key")), {}),
            claims.get(_text(item.get("parameter_key")), {}),
        )
        for item in requirements
    )
    entries = "".join(
        _render_parameter_entry(
            item,
            claims.get(_text(item.get("parameter_key")), {}),
            coverage_items.get(_text(item.get("parameter_key")), {}),
            sources,
        )
        for item in requirements
    )
    category_label = _VALUE_LABELS.get(category, category)
    attention_label = f" · {attention_count} 项需关注" if attention_count else ""
    return (
        f"<details class='parameter-category' data-parameter-group{(' open' if attention_count else '')}>"
        "<summary>"
        f"<strong>{html.escape(category_label)}</strong>"
        f"<span>{len(requirements)} 项{html.escape(attention_label)}</span>"
        f"</summary><div class='parameter-entry-list'>{entries}</div></details>"
    )


def _render_parameter_entry(
    requirement: Mapping[str, object],
    claim: Mapping[str, object],
    result: Mapping[str, object],
    sources: Mapping[str, Mapping[str, object]],
) -> str:
    key = _text(requirement.get("parameter_key"))
    status = _text(result.get("status") or "missing")
    criticality = _text(requirement.get("criticality") or "required")
    value = _parameter_value(requirement, claim, result)
    conditions = _parameter_conditions(claim)
    material_value = requirement.get("material")
    material = _text(material_value) if material_value is not None else "未声明"
    device_scope = _text(requirement.get("device_scope"))
    tuning_search = " ".join(_parameter_tuning_candidates(claim))
    source_search = " ".join(
        " ".join(
            (
                _text(source.get("title")),
                _text(source.get("work_key")),
                _VALUE_LABELS.get(
                    _text(source.get("source_class")),
                    _text(source.get("source_class")),
                ),
            )
        )
        for observation in _object_list(claim.get("observations"))
        if (
            source := sources.get(_text(observation.get("source_key")))
        ) is not None
    )
    search_text = " ".join(
        (
            _text(requirement.get("display_name")),
            key,
            device_scope,
            material,
            _VALUE_LABELS.get(status, status),
            _VALUE_LABELS.get(criticality, criticality),
            tuning_search,
            source_search,
        )
    )
    source_count = _integer(result.get("independent_source_count"))
    summary = result.get("summary")
    summary_text = (
        _text(summary) if summary is not None else "覆盖报告未返回该参数的说明。"
    )
    rationale = claim.get("selection_rationale")
    rationale_text = (
        _text(rationale) if rationale is not None else "尚未提供参数声明。"
    )
    epistemic_status = _text(claim.get("epistemic_status"))
    epistemic_label = (
        _VALUE_LABELS.get(epistemic_status, epistemic_status)
        if claim
        else "尚未声明"
    )
    return (
        "<details class='parameter-entry' data-parameter-item "
        f"data-parameter-text='{html.escape(search_text, quote=True)}'>"
        "<summary class='parameter-entry-summary'>"
        "<span class='parameter-entry-identity'>"
        f"<strong>{html.escape(_text(requirement.get('display_name')) or key)}</strong>"
        f"<code>{html.escape(key)}</code></span>"
        "<span class='parameter-entry-baseline' data-parameter-field='baseline'>"
        f"<small>基准值</small><code>{html.escape(value)}</code></span>"
        f"<span class='inline-status parameter-status-{_parameter_status_tone(status)}'>"
        f"{html.escape(_VALUE_LABELS.get(status, status))}</span>"
        "<span class='parameter-entry-source-count' data-parameter-field='source-count'>"
        f"<strong>{source_count}</strong><small>独立来源</small></span>"
        "</summary><div class='parameter-entry-body'>"
        "<dl class='parameter-entry-metadata'>"
        f"<dt>优先级</dt><dd>{html.escape(_VALUE_LABELS.get(criticality, criticality))}</dd>"
        f"<dt>器件范围</dt><dd>{html.escape(device_scope)}</dd>"
        f"<dt>材料</dt><dd>{html.escape(material)}</dd>"
        f"<dt>适用条件</dt><dd>{html.escape(conditions)}</dd>"
        f"<dt>证据类型</dt><dd>{html.escape(epistemic_label)}</dd>"
        f"<dt>规范单位</dt><dd><code>{html.escape(_text(requirement.get('canonical_unit')))}</code></dd>"
        "</dl>"
        f"{_render_parameter_tuning(claim, _text(claim.get('unit') or requirement.get('canonical_unit')))}"
        "<div class='parameter-entry-review-grid'>"
        "<section><h4>覆盖说明</h4>"
        f"<p>{html.escape(summary_text)}</p></section>"
        "<section><h4>选择依据</h4>"
        f"<p>{html.escape(rationale_text)}</p></section>"
        "<section class='parameter-entry-sources'><h4>来源速览</h4>"
        f"{_render_parameter_source_brief(claim, sources)}"
        f"<p>{source_count} 个独立来源；完整定位见“来源与假设”。</p>"
        "</section></div></div></details>"
    )


def _render_device_parameter_sources(
    requirements: Mapping[str, object],
    parameters: Mapping[str, object],
    catalog: Mapping[str, object],
    coverage: Mapping[str, object],
) -> str:
    sources = {
        _text(item.get("source_key")): item
        for item in _object_list(catalog.get("sources"))
    }
    coverage_items = {
        _text(item.get("parameter_key")): item
        for item in _object_list(coverage.get("items"))
    }
    claims = {
        _text(item.get("parameter_key")): item
        for item in _object_list(parameters.get("claims"))
    }
    catalog_rows = "".join(_render_source_catalog_row(item) for item in sources.values())
    source_groups = []
    for category, requirement_items in _group_parameter_requirements(
        _object_list(requirements.get("parameters"))
    ):
        details = "".join(
            _render_parameter_source_detail(
                requirement,
                claims[key],
                sources,
                coverage_items.get(key, {}),
            )
            for requirement in requirement_items
            if (key := _text(requirement.get("parameter_key"))) in claims
        )
        if details:
            source_groups.append(
                "<section class='parameter-source-category' data-parameter-group>"
                f"<h3>{html.escape(_VALUE_LABELS.get(category, category))}</h3>"
                f"{details}</section>"
            )
    return (
        "<section class='semantic-section evidence-lead'>"
        "<div class='section-heading'><span class='section-number'>源</span><div>"
        "<p class='eyebrow'>先确认来源身份</p><h2>来源目录</h2></div></div>"
        "<div class='table-scroll'><table class='source-table source-catalog-table'>"
        "<thead><tr><th>来源</th><th>类型</th><th>独立作品标识</th><th>访问时间</th></tr></thead>"
        f"<tbody>{catalog_rows}</tbody></table></div></section>"
        "<section class='semantic-section parameter-source-trails'>"
        "<div class='section-heading'><span class='section-number'>证</span><div>"
        "<p class='eyebrow'>按参数折叠的证据链</p><h2>参数与来源对应关系</h2></div></div>"
        f"{_render_parameter_search('搜索参数、来源或原文位置…')}"
        f"<div class='parameter-source-groups'>{''.join(source_groups)}</div></section>"
    )


def _render_source_catalog_row(source: Mapping[str, object]) -> str:
    source_key = _text(source.get("source_key"))
    source_title = html.escape(_text(source.get("title")) or source_key)
    final_url = _safe_https_url(_text(source.get("final_url")))
    source_link = (
        f"<a href='{html.escape(final_url, quote=True)}' rel='noreferrer noopener' "
        f"target='_blank'>{source_title}</a>"
        if final_url
        else source_title
    )
    source_class = _text(source.get("source_class"))
    accessed_at = source.get("accessed_at")
    accessed_label = _text(accessed_at) if accessed_at is not None else "本地冻结输入"
    return (
        "<tr>"
        f"<td>{source_link}<br><code>{html.escape(source_key)}</code></td>"
        f"<td>{html.escape(_VALUE_LABELS.get(source_class, source_class))}</td>"
        f"<td><code>{html.escape(_text(source.get('work_key')))}</code></td>"
        f"<td>{html.escape(accessed_label)}</td>"
        "</tr>"
    )


def _render_parameter_source_detail(
    requirement: Mapping[str, object],
    claim: Mapping[str, object],
    sources: Mapping[str, Mapping[str, object]],
    result: Mapping[str, object],
) -> str:
    key = _text(claim.get("parameter_key"))
    comparisons = {
        _text(item.get("source_key")): item
        for item in _object_list(result.get("comparisons"))
    }
    rows = []
    search_parts = [
        key,
        _text(requirement.get("display_name")),
        *_parameter_tuning_candidates(claim),
    ]
    for observation in _object_list(claim.get("observations")):
        source_key = _text(observation.get("source_key"))
        source = sources.get(source_key, {})
        comparison = comparisons.get(source_key, {})
        final_url = _safe_https_url(_text(source.get("final_url")))
        source_title_text = _text(source.get("title")) or source_key
        source_title = html.escape(source_title_text)
        source_link = (
            f"<a href='{html.escape(final_url, quote=True)}' rel='noreferrer noopener' target='_blank'>{source_title}</a>"
            if final_url
            else source_title
        )
        source_class = _text(source.get("source_class"))
        normalized = (
            f"{_text(comparison.get('normalized_value'))} "
            f"{_text(comparison.get('unit'))}"
        ).strip()
        locator = _text(observation.get("locator"))
        search_parts.extend((source_title_text, source_key, locator))
        rows.append(
            "<tr>"
            f"<td>{source_link}<br><code>{html.escape(source_key)}</code></td>"
            f"<td>{html.escape(_VALUE_LABELS.get(source_class, source_class))}<br>"
            f"<code>{html.escape(_text(source.get('work_key')))}</code></td>"
            f"<td><code>{html.escape(_text(observation.get('reported_value')))} "
            f"{html.escape(_text(observation.get('reported_unit')))}</code></td>"
            f"<td><code>{html.escape(normalized)}</code></td>"
            f"<td>{html.escape(locator)}</td>"
            f"<td>{html.escape(_text(comparison.get('reason')))}</td>"
            "</tr>"
        )
    status = _text(result.get("status") or "missing")
    source_count = _integer(result.get("independent_source_count"))
    value = _parameter_value(requirement, claim, result)
    search_text = " ".join(search_parts)
    evidence_table = (
        "<div class='table-scroll'><table class='source-table'><thead><tr>"
        "<th>来源</th><th>来源身份</th><th>原始报告值</th><th>规范化值</th>"
        "<th>原文位置</th><th>一致性</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
        if rows
        else _empty_state("该参数没有来源观测；请核对其证据状态与选择理由。")
    )
    return (
        "<details class='parameter-source' data-parameter-item "
        f"data-parameter-text='{html.escape(search_text, quote=True)}'>"
        "<summary><span>"
        f"<strong>{html.escape(_text(requirement.get('display_name')) or key)}</strong>"
        f"<code>{html.escape(key)}</code></span>"
        f"<code>{html.escape(value)}</code>"
        f"<span class='inline-status parameter-status-{_parameter_status_tone(status)}'>"
        f"{html.escape(_VALUE_LABELS.get(status, status))}</span>"
        f"<span>{source_count} 个独立来源</span></summary>"
        "<div class='parameter-source-body'>"
        f"<p><strong>选择依据：</strong>{html.escape(_text(claim.get('selection_rationale')))}</p>"
        f"{_render_parameter_tuning(claim, _text(claim.get('unit') or requirement.get('canonical_unit')))}"
        f"{evidence_table}</div></details>"
    )


def _render_parameter_search(placeholder: str) -> str:
    return (
        "<label class='parameter-search'>"
        "<span>查找参数</span>"
        f"<input type='search' data-parameter-search placeholder='{html.escape(placeholder, quote=True)}' "
        "autocomplete='off'></label>"
    )


def _group_parameter_requirements(
    requirements: list[Mapping[str, object]],
) -> list[tuple[str, list[Mapping[str, object]]]]:
    order = (
        "geometry",
        "material",
        "composition",
        "doping",
        "process",
        "physics_model",
        "contact_boundary",
        "initial_condition",
    )
    grouped: dict[str, list[Mapping[str, object]]] = {}
    for requirement in requirements:
        grouped.setdefault(_text(requirement.get("category")), []).append(requirement)
    rank = {name: index for index, name in enumerate(order)}
    return sorted(
        grouped.items(),
        key=lambda item: (rank.get(item[0], len(order)), item[0]),
    )


def _parameter_value(
    requirement: Mapping[str, object],
    claim: Mapping[str, object],
    result: Mapping[str, object],
) -> str:
    selected = result.get("selected_value")
    if selected is None:
        selected = claim.get("selected_value")
    if selected is None:
        return "—"
    selected_value = _text(selected)
    unit = _text(
        result.get("canonical_unit")
        or claim.get("unit")
        or requirement.get("canonical_unit")
    )
    return f"{selected_value} {unit}".strip()


def _parameter_conditions(claim: Mapping[str, object]) -> str:
    return "；".join(
        f"{_text(item.get('name'))}={_text(item.get('value'))}"
        + (f" {_text(item.get('unit'))}" if item.get("unit") else "")
        for item in _object_list(claim.get("conditions"))
    ) or "未声明"


def _parameter_needs_attention(
    result: Mapping[str, object], claim: Mapping[str, object]
) -> bool:
    return _parameter_has_tuning(claim) or _text(result.get("status")) not in {
        "confirmed",
        "authoritative_single",
    }


def _parameter_has_tuning(claim: Mapping[str, object]) -> bool:
    return isinstance(claim.get("tuning"), Mapping)


def _parameter_tuning_candidates(claim: Mapping[str, object]) -> list[str]:
    tuning = claim.get("tuning")
    if not isinstance(tuning, Mapping):
        return []
    return _string_list(tuning.get("candidate_values"))


def _render_parameter_tuning(claim: Mapping[str, object], unit: str) -> str:
    tuning = claim.get("tuning")
    if not isinstance(tuning, Mapping):
        return ""
    candidates = "、".join(_parameter_tuning_candidates(claim))
    candidate_text = f"{candidates} {unit}".strip()
    purpose = _text(tuning.get("purpose"))
    basis = _text(tuning.get("basis"))
    rationale = _text(tuning.get("rationale"))
    return (
        "<div class='parameter-tuning'>"
        "<strong>可调参数</strong>"
        f"<span>{html.escape(_TUNING_PURPOSE_LABELS.get(purpose, purpose))}</span>"
        f"<span>候选：<code>{html.escape(candidate_text)}</code></span>"
        f"<span>依据：{html.escape(_TUNING_BASIS_LABELS.get(basis, basis))}</span>"
        f"<small>{html.escape(rationale)}</small>"
        "</div>"
    )


def _parameter_status_tone(status: str) -> str:
    if status in {"confirmed", "authoritative_single"}:
        return "good"
    if status in {"single_source", "assumed"}:
        return "warn"
    return "bad"


def _render_parameter_source_brief(
    claim: Mapping[str, object],
    sources: Mapping[str, Mapping[str, object]],
) -> str:
    source_keys = []
    for observation in _object_list(claim.get("observations")):
        source_key = _text(observation.get("source_key"))
        if source_key not in source_keys:
            source_keys.append(source_key)
    if not source_keys:
        return "<span class='source-brief-empty'>无合格来源</span>"
    rows = []
    for source_key in source_keys[:3]:
        source = sources.get(source_key, {})
        source_class = _text(source.get("source_class"))
        title = _text(source.get("title"))
        final_url = _safe_https_url(_text(source.get("final_url")))
        title_html = html.escape(title)
        if final_url:
            title_html = (
                f"<a href='{html.escape(final_url, quote=True)}' "
                f"rel='noreferrer noopener' target='_blank'>{title_html}</a>"
            )
        rows.append(
            "<span class='parameter-source-brief'>"
            f"<strong>{html.escape(_VALUE_LABELS.get(source_class, source_class))}</strong>"
            f"<small>{title_html}</small></span>"
        )
    omitted = len(source_keys) - len(rows)
    if omitted:
        rows.append(f"<small>另有 {omitted} 个来源，见“来源追溯”</small>")
    return "".join(rows)


def _parameter_source_kinds(
    claim: Mapping[str, object],
    sources: Mapping[str, Mapping[str, object]],
) -> str:
    classes = []
    for observation in _object_list(claim.get("observations")):
        source = sources.get(_text(observation.get("source_key")), {})
        source_class = _text(source.get("source_class"))
        label = _VALUE_LABELS.get(source_class, source_class)
        if label not in classes:
            classes.append(label)
    return "、".join(classes) if classes else "无合格来源"


def _render_parameter_gap_context(
    foundation: Mapping[str, object] | None,
) -> str:
    if foundation is None:
        return ""
    missing = _string_list(foundation.get("missing_inputs"))
    questions = _string_list(foundation.get("open_questions"))
    if not missing and not questions:
        return ""
    missing_rows = "".join(f"<li>{html.escape(item)}</li>" for item in missing)
    question_rows = "".join(f"<li>{html.escape(item)}</li>" for item in questions)
    return (
        "<div class='parameter-gap-context'>"
        "<h3>缺失原因与补齐路径</h3>"
        + (
            f"<div><strong>提取器记录的缺失原因</strong><ul>{missing_rows}</ul></div>"
            if missing_rows
            else ""
        )
        + (
            f"<div><strong>待解决问题</strong><ul>{question_rows}</ul></div>"
            if question_rows
            else ""
        )
        + "</div>"
    )


def _render_parameter_attention_row(
    requirement: Mapping[str, object],
    claim: Mapping[str, object],
    result: Mapping[str, object],
) -> str:
    key = _text(requirement.get("parameter_key"))
    status = _text(result.get("status") or "missing")
    criticality = _text(requirement.get("criticality") or "required")
    summary = result.get("summary")
    summary_text = (
        _text(summary) if summary is not None else "覆盖报告未返回该参数的说明。"
    )
    tuning_badge = (
        "<span class='parameter-criticality'>可调参数</span>"
        if _parameter_has_tuning(claim)
        else ""
    )
    return (
        "<article class='parameter-attention'>"
        "<div>"
        f"<span class='inline-status parameter-status-{_parameter_status_tone(status)}'>"
        f"{html.escape(_VALUE_LABELS.get(status, status))}</span>"
        f"<span class='parameter-criticality'>{html.escape(_VALUE_LABELS.get(criticality, criticality))}</span>"
        f"{tuning_badge}"
        "</div><div>"
        f"<strong>{html.escape(_text(requirement.get('display_name')) or key)}</strong>"
        f"<code>{html.escape(key)}</code>"
        f"<p>{html.escape(summary_text)}</p>"
        "</div>"
        "<div class='attention-value'>"
        f"<code>{html.escape(_parameter_value(requirement, claim, result))}</code>"
        f"{_render_parameter_tuning(claim, _text(claim.get('unit') or requirement.get('canonical_unit')))}"
        "</div>"
        "</article>"
    )


def _render_parameter_quick_group(
    category: str,
    requirements: list[Mapping[str, object]],
    claims: Mapping[str, Mapping[str, object]],
    coverage_items: Mapping[str, Mapping[str, object]],
    sources: Mapping[str, Mapping[str, object]],
) -> str:
    attention_count = sum(
        _parameter_needs_attention(
            coverage_items.get(_text(item.get("parameter_key")), {}),
            claims.get(_text(item.get("parameter_key")), {}),
        )
        for item in requirements
    )
    cards = []
    for requirement in requirements:
        key = _text(requirement.get("parameter_key"))
        claim = claims.get(key, {})
        result = coverage_items.get(key, {})
        status = _text(result.get("status") or "missing")
        cards.append(
            "<article class='parameter-quick-item'>"
            f"<span>{html.escape(_text(requirement.get('display_name')) or key)}</span>"
            f"<code>{html.escape(_parameter_value(requirement, claim, result))}</code>"
            f"<small class='parameter-status-{_parameter_status_tone(status)}'>"
            f"{html.escape(_VALUE_LABELS.get(status, status))}</small>"
            f"<small class='parameter-source-kinds'>来源：{html.escape(_parameter_source_kinds(claim, sources))}</small>"
            f"{_render_parameter_tuning(claim, _text(claim.get('unit') or requirement.get('canonical_unit')))}"
            "</article>"
        )
    category_label = _VALUE_LABELS.get(category, category)
    attention_label = f" · {attention_count} 项需关注" if attention_count else ""
    return (
        f"<details class='parameter-category parameter-quick-group'{(' open' if attention_count else '')}>"
        "<summary>"
        f"<strong>{html.escape(category_label)}</strong>"
        f"<span>{len(requirements)} 项{html.escape(attention_label)}</span>"
        "</summary>"
        f"<div class='parameter-quick-grid'>{''.join(cards)}</div></details>"
    )


def _parameter_review_conclusion(
    coverage_status: str,
    review_count: int,
    blocking_count: int,
    audit_checks: list[Mapping[str, object]],
    audit_failures: list[Mapping[str, object]],
) -> tuple[str, str, str]:
    if coverage_status == "fail" or blocking_count:
        return (
            "存在阻塞项，当前不应批准",
            f"确定性覆盖报告发现 {blocking_count} 个阻塞项；应先修订参数或证据。",
            "bad",
        )
    if audit_failures:
        return (
            "独立审计尚未通过",
            f"有 {len(audit_failures)} 个审计检查未通过；应先查看审计依据并修订。",
            "bad",
        )
    if coverage_status == "review_required":
        return (
            "需要带例外审批",
            f"当前没有阻塞项，但有 {review_count} 项需要人工接受；批准时必须说明例外理由。",
            "warn",
        )
    if audit_checks:
        return (
            "覆盖与独立审计均已通过",
            "可以在核对必需参数取值、适用条件和来源后作出审批决定。",
            "good",
        )
    return (
        "参数覆盖检查已通过",
        "当前对象未附独立审计；请在批准前确认这符合本次审批要求。",
        "warn",
    )


def _render_collapsible_supporting_content(content: str) -> str:
    if not content:
        return ""
    return (
        "<section class='semantic-section supporting-content'>"
        "<details><summary><strong>科学基础等辅助对象</strong>"
        "<span>按需展开；完整冻结数据也可在“原始数据”页签核验</span></summary>"
        f"<div class='supporting-content-body'>{content}</div></details></section>"
    )


def _safe_https_url(value: str) -> str | None:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None
    return value


def _render_optional_foundation_images(previews: str) -> str:
    return (
        "<section class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>IMG</span>"
        "<div><p class='eyebrow'>可选视觉证据</p><h2>图像附件</h2></div></div>"
        + (
            previews
            if previews
            else _empty_state("本审批对象集未提供可安全预览的图像附件。")
        )
        + "</section>"
    )


def _render_missing_foundation_parameters() -> str:
    return (
        "<section class='semantic-section notice-section'>"
        "<div class='section-heading'><span class='section-number'>P</span>"
        "<div><p class='eyebrow'>参数状态</p><h2>实验与模型参数</h2></div></div>"
        f"{_empty_state('本审批对象集没有 scientific foundation，未声明可审查的实验或模型参数。')}"
        "</section>"
    )


def _render_objective_contract(contract: Mapping[str, object]) -> str:
    targets = _object_list(contract.get("mandatory_targets"))
    requirements = _object_list(contract.get("closure_requirements"))
    target_rows = []
    for target in targets:
        domains = "; ".join(
            f"{_text(item.get('start'))}–{_text(item.get('stop'))} "
            f"{_text(item.get('unit'))}（至少 {_text(item.get('min_points'))} 个点）"
            for item in _object_list(target.get("required_domains"))
        )
        target_rows.append(
            "<article class='evidence-row'><div class='evidence-marker'>目标</div><div>"
            f"<p class='row-title'>{html.escape(_text(target.get('observable')))}</p>"
            "<dl class='detail-list'>"
            f"<dt>参考曲线</dt><dd>{html.escape(_text(target.get('reference_series_key')))}</dd>"
            f"<dt>必需区间</dt><dd>{html.escape(domains)}</dd>"
            f"<dt>支持要求</dt><dd>{html.escape(_VALUE_LABELS.get(_text(target.get('support_requirement')), _text(target.get('support_requirement'))))}</dd>"
            f"<dt>理由</dt><dd>{html.escape(_text(target.get('rationale')))}</dd>"
            "</dl>"
            f"<code class='object-id'>{html.escape(_text(target.get('target_key')))}</code>"
            "</div></article>"
        )
    requirement_rows = "".join(
        "<li>"
        f"<strong>{html.escape(_text(item.get('requirement_key')))}</strong> · "
        f"{html.escape(_text(item.get('description')))} · "
        f"类型 <code>{html.escape(_text(item.get('requirement_type')))}</code>"
        "</li>"
        for item in requirements
    )
    return (
        "<section class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>02</span>"
        "<div><p class='eyebrow'>不可替换的研究目标合同</p>"
        "<h2>目标、真值与闭环条件</h2></div></div>"
        "<div class='statement-grid'>"
        f"{_statement('目标键', _text(contract.get('objective_key')), 'objective')}"
        f"{_statement('研究意图', _VALUE_LABELS.get(_text(contract.get('intent')), _text(contract.get('intent'))), 'scope')}"
        "</div>"
        + "".join(target_rows)
        + (
            "<h3>闭环要求</h3><ul class='plain-list'>" + requirement_rows + "</ul>"
            if requirement_rows
            else ""
        )
        + "</section>"
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


def _render_evidence_audit_content(audit: Mapping[str, object]) -> str:
    checks = _object_list(audit.get("checks"))
    rows = "".join(
        "<article class='evidence-row'><div class='evidence-marker'>审计</div><div>"
        f"<p class='row-title'>{html.escape(_text(item.get('subject')))}</p>"
        f"<span class='inline-status'>{html.escape(_VALUE_LABELS.get(_text(item.get('status')), _text(item.get('status'))))}</span>"
        f"<p class='row-secondary'><strong>审计依据：</strong>{html.escape(_text(item.get('basis')))}</p>"
        f"<code class='object-id'>{html.escape(_text(item.get('check_key')))}</code>"
        "</div></article>"
        for item in checks
    )
    return (
        "<section class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>审</span>"
        "<div><p class='eyebrow'>独立证据审计</p><h2>最终审计结论</h2></div></div>"
        f"{rows or _empty_state('最终审批对象集没有独立证据审计项。')}"
        "</section>"
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
    request: Mapping[str, object],
    project: Mapping[str, object],
    capability: Mapping[str, object] | None = None,
    reviewed_package: Mapping[str, object] | None = None,
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
    public_arguments = (
        _string_list(capability.get("public_arguments"))
        if capability is not None
        else []
    )
    private_argument_count = (
        capability.get("private_fixed_argument_count")
        if capability is not None
        else None
    )
    launch_name = _text(
        capability.get("launch_name")
        if capability is not None
        else project.get("tool_profile")
    )
    project_command = shlex.join(
        [_text(project.get("entrypoint")), *arguments]
    )
    command = (
        shlex.join([launch_name, *public_arguments]) + " " + project_command
        if private_argument_count == len(public_arguments)
        else (
            f"{shlex.quote(launch_name)} "
            f"<{_format_number(private_argument_count)} deployment-owned fixed arguments> "
            f"{project_command}"
        )
    )
    capability_digest = (
        _text(capability.get("capability_sha256"))
        if capability is not None
        else "未绑定"
    )
    objective_panel = _render_execution_objective(reviewed_package)
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
        f"<dt>求解器类型</dt><dd><code>{html.escape(_text(capability.get('solver_kind') if capability is not None else project.get('solver_kind')))}</code></dd>"
        f"<dt>公开发行标签</dt><dd>{html.escape(_text(capability.get('public_release_label')) if capability is not None else '未绑定')}</dd>"
        f"<dt>私有固定参数数目</dt><dd>{html.escape(_format_number(private_argument_count))}</dd>"
        f"<dt>公开固定参数</dt><dd><code>{html.escape(shlex.join(public_arguments) if public_arguments else '无')}</code></dd>"
        f"<dt>私有参数摘要</dt><dd><code>{html.escape(_text(capability.get('private_fixed_arguments_sha256')) if capability is not None else '未绑定')}</code></dd>"
        f"<dt>私有发行证据摘要</dt><dd><code>{html.escape(_text(capability.get('private_release_evidence_sha256')) if capability is not None else '未绑定')}</code></dd>"
        f"<dt>Capability 摘要</dt><dd><code>{html.escape(capability_digest)}</code></dd>"
        f"<dt>入口文件</dt><dd><code>{html.escape(_text(project.get('entrypoint')))}</code></dd>"
        f"<dt>调用边界</dt><dd><code>{html.escape(command)}</code></dd>"
        "</dl></section>"
        + objective_panel
        + "<section class='semantic-section'>"
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


def _render_execution_objective(
    reviewed_package: Mapping[str, object] | None,
) -> str:
    if reviewed_package is None:
        return ""
    objective_value = reviewed_package.get("objective")
    coverage_value = reviewed_package.get("objective_coverage")
    plan_value = reviewed_package.get("experiment_plan")
    if not isinstance(objective_value, Mapping):
        return ""
    coverage = coverage_value if isinstance(coverage_value, Mapping) else {}
    plan = plan_value if isinstance(plan_value, Mapping) else {}
    target_rows = "".join(
        "<tr>"
        f"<td><code>{html.escape(_text(item.get('target_key')))}</code></td>"
        f"<td>{html.escape(_text(item.get('reference_series_key')))}</td>"
        f"<td>{html.escape(_text(item.get('status')))}</td>"
        f"<td>{html.escape(', '.join(_string_list(item.get('reason_codes'))))}</td>"
        "</tr>"
        for item in _object_list(coverage.get("targets"))
    )
    requirement_rows = "".join(
        "<tr>"
        f"<td><code>{html.escape(_text(item.get('requirement_key')))}</code></td>"
        f"<td>{html.escape(_text(item.get('status')))}</td>"
        f"<td>{html.escape(', '.join(_string_list(item.get('reason_codes'))))}</td>"
        "</tr>"
        for item in _object_list(coverage.get("requirements"))
    )
    comparisons = []
    for proposal in _object_list(plan.get("proposals")):
        spec = proposal.get("curve_comparison_spec")
        if not isinstance(spec, Mapping):
            continue
        for comparison in _object_list(spec.get("comparisons")):
            comparisons.append(
                "<tr>"
                f"<td><code>{html.escape(_text(comparison.get('comparison_key')))}</code></td>"
                f"<td>{html.escape(_text(comparison.get('purpose')))}</td>"
                f"<td>{html.escape(_text(comparison.get('gate_scope')))}</td>"
                f"<td>{'是' if comparison.get('required') is True else '否'}</td>"
                "</tr>"
            )
    return (
        "<section class='semantic-section'>"
        "<div class='section-heading'><span class='section-number'>O</span>"
        "<div><p class='eyebrow'>科学目标执行门禁</p>"
        "<h2>本次执行不会替换研究真值</h2></div></div>"
        "<dl class='metadata'>"
        f"<dt>目标键</dt><dd><code>{html.escape(_text(objective_value.get('objective_key')))}</code></dd>"
        f"<dt>研究意图</dt><dd>{html.escape(_text(objective_value.get('intent')))}</dd>"
        f"<dt>目标覆盖</dt><dd><strong>{html.escape(_text(coverage.get('status')))}</strong></dd>"
        "</dl>"
        "<div class='table-scroll'><table class='source-table'><thead><tr>"
        "<th>必需目标</th><th>参考系列</th><th>状态</th><th>缺口</th>"
        f"</tr></thead><tbody>{target_rows}</tbody></table></div>"
        "<div class='table-scroll'><table class='source-table'><thead><tr>"
        "<th>闭环要求</th><th>状态</th><th>缺口</th>"
        f"</tr></thead><tbody>{requirement_rows}</tbody></table></div>"
        "<div class='table-scroll'><table class='source-table'><thead><tr>"
        "<th>比较</th><th>用途</th><th>门作用域</th><th>必需</th>"
        f"</tr></thead><tbody>{''.join(comparisons)}</tbody></table></div>"
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
        f"<dt>请求类型</dt><dd>{html.escape(_APPROVAL_KIND_LABELS.get(review.request.kind, review.request.kind))}</dd>"
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
        f"<span class='tree-kind'>{_JSON_TYPE_LABELS[_json_type(value)]}</span>"
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


def _integer(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


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
