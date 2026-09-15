"""Fixed, escaped renderer for immutable approval subjects."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from urllib.parse import quote

from ..schema.approval import (
    LocalIdentityRef,
    ReviewDocument,
    ReviewDocumentItem,
    parse_json_pointer,
)
from ..service.approvals import ApprovalReview
from .presentation_render import (
    EvidenceHref,
    ImageHref,
    render_json_value,
    render_presentation,
    render_source,
    fold_panel,
    approval_heading,
)
from .navigation import navigation


_STATUS_LABELS = {
    "pending": "待审批",
    "decided": "已决定",
    "expired": "已过期",
    "cancelled_by_human": "已由用户取消",
}
_MAX_PAGE_BYTES = 256 * 1024

# Display translations only. Unknown/custom option prose remains verbatim;
# the submitted option IDs, rationale requirements and frozen request stay intact.
_OPTION_TEXT = {
    "Approve exact problem": "批准本次研究问题",
    "Accept this exact frozen problem contract.": "接受本次冻结的研究问题合同。",
    "Approve exact scientific foundation": "批准本次科学依据",
    "Accept the exact structured facts, parameters, sources, assumptions, and unresolved conflicts shown in this review.": "接受本次展示的事实、参数、来源、假设与未解决冲突。",
    "Authorize exact run request": "授权本次执行",
    "Authorize only this exact frozen run request; this is not a scientific acceptance.": "仅授权本次冻结的执行请求，不代表认可科学结论。",
    "Approve exact claim": "批准本次结论发布",
    "Approve publication of only this exact frozen claim and evidence set.": "仅批准发布本次冻结的结论及其证据集合。",
    "Request revision": "要求修订",
    "Reject this exact version and state the required change.": "拒绝本次版本，并说明需要修改的内容。",
    "Cancel review": "取消本次审批",
    "Close this review without approval or rejection.": "结束本次审批，不作批准或拒绝决定。",
}

@dataclass(frozen=True)
class ReviewContext:
    instance_name: str
    instance_title: str
    instance_objective: str
    approval_name: str
    approval_logical_name: str
    approval_revision: int
    instance_id: str | None = None


def render_review(
    review: ApprovalReview,
    *,
    access_token: str,
    identity: LocalIdentityRef,
    context: ReviewContext | None = None,
    read_only: bool = False,
    presentation: dict | None = None,
    evidence_href: EvidenceHref | None = None,
    image_href: ImageHref | None = None,
) -> bytes:
    """Render one frozen request without dispatching on domain schemas."""

    request = review.request
    document = request.review_document
    title = (
        document.title
        if document is not None
        else "历史审批记录"
    )
    status_label = _STATUS_LABELS.get(review.status, review.status)

    def frozen_evidence_href(artifact_id: str, pointer: str) -> str:
        for index, (envelope, _) in enumerate(review.subjects):
            if envelope.ref.artifact_id == artifact_id:
                return html.unescape(_subject_href(review, index, access_token))
        return ""

    presentation_panel = render_presentation(
        presentation,
        evidence_href=evidence_href or frozen_evidence_href,
        image_href=image_href or (lambda artifact_id: ""),
    )
    document_panel = fold_panel("审批事项与固定依据", (
        _render_document(review, document, access_token)
        if document is not None
        else _render_fallback_notice(request.kind)
    ))
    question_preview = "<p>" + _preview_text(request.question, limit=320) + "</p>"
    if len(request.question) > 320:
        question_preview += fold_panel("展开审批问题原文", "<p>" + _preview_text(request.question, limit=1024) + "</p>")
    action_title, action_prompt = approval_heading(request.kind)
    request_download = (
        f"<a class='source-link' href='{_request_href(review, access_token)}'>"
        "完整审批问题与选项（原件）</a>"
    )
    page_start = (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(title)} · 科研审批</title>"
        "<link rel='stylesheet' href='/static/style.css'>"
        "<script src='/static/app.js' defer></script></head><body class='approval-workspace'>" + navigation(context.instance_id if context else None) +
        "<header class='topbar'><div class='topbar-inner'>"
        "<div><p class='product-name'>科研审批</p>"
        f"<h1>{action_title}</h1></div>"
        f"<span class='status-badge'>{html.escape(status_label)}</span>"
        "</div></header>"
        "<main class='page'>"
        f"{_render_review_context(context)}"
        "<section class='review-intro'>"
        "<p class='eyebrow'>本次需要您决定</p>"
        f"<h2>{action_prompt}</h2>"
        f"<div class='question'>{question_preview}</div>{request_download}"
        f"{_render_request_metadata(review, status_label)}"
        "</section>"
        "<div class='review-layout'><div class='review-main'>"
    )
    page_end = (
        "</div>"
        f"<aside class='decision-column'>{_render_decision(review, access_token, identity, read_only=read_only)}</aside>"
        "</div></main></body></html>"
    )
    raw_panel = _render_raw_subjects(review, access_token)
    omitted = (
        "<section class='semantic-section'><p class='bounded-note'>"
        "本页预览达到大小上限；其余依据请通过冻结原件和来源完整核对。</p>"
        f"{request_download}</section>"
    )
    # Keep the original decision controls and every exact subject download even
    # when a maximum-sized legal request leaves little room for display panels.
    fixed_bytes = len((page_start + raw_panel + page_end).encode("utf-8"))
    if fixed_bytes + len((presentation_panel + document_panel).encode("utf-8")) > _MAX_PAGE_BYTES:
        document_panel = omitted
    if fixed_bytes + len((presentation_panel + document_panel).encode("utf-8")) > _MAX_PAGE_BYTES:
        presentation_panel = ""
    return (page_start + presentation_panel + document_panel + raw_panel + page_end).encode("utf-8")


def _render_document(
    review: ApprovalReview,
    document: ReviewDocument,
    access_token: str,
) -> str:
    sections = []
    used_bytes = 0
    omitted = False
    for section in document.sections:
        items = []
        heading = (
            "<section class='semantic-section review-document-section'>"
            "<div class='section-heading'><div>"
            f"<h2>{html.escape(section.title)}</h2>"
            f"<p>{html.escape(section.description)}</p>"
            "</div></div><div class='review-document-items'>"
        )
        used_bytes += len(heading.encode("utf-8"))
        for item in section.items:
            rendered = _render_document_item(review, item, access_token)
            if used_bytes + len(rendered.encode("utf-8")) > 48 * 1024:
                omitted = True
                break
            items.append(rendered)
            used_bytes += len(rendered.encode("utf-8"))
        sections.append(heading + "".join(items) + "</div></section>")
        if omitted:
            sections.append("<p class='bounded-note'>审批依据预览达到大小上限；请通过下方冻结文件下载核对其余完整原文。</p>")
            break
    description = (
        f"<p class='bounded-note'>{html.escape(document.description)}</p>"
        if document.description
        else ""
    )
    return (
        "<section class='semantic-section review-document-intro'>"
        "<p class='eyebrow'>本次审批的固定依据</p>"
        f"<h2>{html.escape(document.title)}</h2>{description}"
        "<p class='bounded-note'>本视图只读取审批请求中已经冻结的标签、对象序号和 JSON 指针；"
        "完整对象与精确字节见下方原始数据。</p></section>"
        + "".join(sections)
    )


def _render_document_item(
    review: ApprovalReview,
    item: ReviewDocumentItem,
    access_token: str,
) -> str:
    envelope, raw = review.subjects[item.subject_index]
    label = html.escape(item.label)
    if item.kind == "subject_metadata":
        content = _render_subject_metadata(envelope)
    elif item.kind == "download":
        content = (
            f"<a class='download-button' href='{_subject_href(review, item.subject_index, access_token)}'>"
            "下载冻结文件</a>"
        )
    else:
        assert item.json_pointer is not None
        if len(raw) > 4 * 1024 * 1024:
            content = (
                "<p class='bounded-note'>该冻结对象超过页面解析范围；"
                "请下载原件并按下方 JSON 指针核对完整字段。</p>"
            )
        else:
            try:
                value = _json_pointer_value(json.loads(raw), item.json_pointer)
                if item.kind == "status" and not isinstance(value, (dict, list)):
                    content = (
                        "<p class='status-badge review-document-status'>"
                        f"{render_json_value(value, max_bytes=2048)}</p>"
                    )
                else:
                    content = render_json_value(value, max_bytes=6144)
            except (UnicodeDecodeError, ValueError, RecursionError):
                content = "<p class='source-gap'>此固定字段无法安全预览；请下载原件核对。</p>"
        content += render_source(
            {"artifact_id": envelope.ref.artifact_id, "json_pointer": item.json_pointer},
            lambda artifact_id, pointer: html.unescape(_subject_href(review, item.subject_index, access_token)),
        )
    return (
        "<article class='review-document-item'>"
        f"<h3>{label}</h3>{content}</article>"
    )


def _render_fallback_notice(kind: str) -> str:
    del kind
    message = (
        "这是没有 ReviewDocument 的历史审批。系统不再按领域 Schema 猜测展示方式；"
        "请直接核对下方完整原始对象。"
    )
    return (
        "<section class='semantic-section historical-review-notice'>"
        "<p class='eyebrow'>固定安全回退</p><h2>完整对象审阅</h2>"
        f"<p>{html.escape(message)}</p></section>"
    )


def _render_review_context(context: ReviewContext | None) -> str:
    if context is None:
        return (
            "<section class='instance-context instance-context-unbound'>"
            "<div><p class='eyebrow'>研究实例</p><strong>未绑定研究实例</strong></div>"
            "<p>这是兼容保留的历史审批，控制面没有可显示的实例归属。</p>"
            "</section>"
        )
    return (
        "<section class='instance-context compact-instance-context'>"
        "<div><p class='eyebrow'>研究实例</p><strong>"
        + _preview_text(context.instance_title, limit=160) + "</strong></div>"
        + fold_panel("实例管理描述", "<p>" + _preview_text(context.instance_objective, limit=1024)
            + "</p><p>实例：" + _preview_text(context.instance_name, limit=256)
            + "</p><p>审批项：" + _preview_text(context.approval_name, limit=256)
            + "</p><p>修订：" + str(context.approval_revision) + "</p>") + "</section>"
    )


def _render_raw_subjects(review: ApprovalReview, access_token: str) -> str:
    sections = []
    preview_bytes = 0
    for index, (envelope, raw) in enumerate(review.subjects):
        base_type = envelope.media_type.split(";", 1)[0].strip().lower()
        if base_type == "application/json":
            if len(raw) > 4096 or preview_bytes > 24 * 1024:
                content = (
                    "<p class='binary-note'>原始 JSON 较大，未嵌入页面；"
                    "下载冻结文件可读取全部精确原文。</p>"
                )
            else:
                try:
                    content = f"<pre class='json-tree'>{_escaped_json(json.loads(raw))}</pre>"
                    size = len(content.encode("utf-8"))
                    if size > 8192 or preview_bytes + size > 24 * 1024:
                        content = "<p class='binary-note'>原始 JSON 预览达到大小上限；请下载冻结文件查看完整原文。</p>"
                    else:
                        preview_bytes += size
                except (UnicodeDecodeError, ValueError, RecursionError):
                    content = (
                        "<p class='binary-note'>该对象声明为 JSON，但不能安全解析；"
                        "请下载精确冻结字节核验。</p>"
                    )
        else:
            content = (
                "<p class='binary-note'>该对象不是 JSON。固定渲染器只显示元数据并提供下载，"
                "不会内联解释其内容。</p>"
            )
        if len(review.subjects) > 32:
            sections.append(
                "<details class='raw-subject'>"
                f"<summary>对象 {index + 1}</summary><div class='raw-subject-body'>"
                f"<p>SHA-256：<code>{html.escape(envelope.ref.sha256)}</code></p>"
                f"<a class='download-button' href='{_subject_href(review, index, access_token)}'>"
                "下载冻结文件</a></div></details>"
            )
        else:
            sections.append(
                "<details class='raw-subject'>"
                f"<summary><span>对象 {index + 1}</span>"
                f"<small>{html.escape(envelope.schema_id)}</small></summary>"
                "<div class='raw-subject-body'>"
                f"{_render_subject_metadata(envelope)}"
                f"<a class='download-button' href='{_subject_href(review, index, access_token)}'>"
                "下载冻结文件</a>"
                f"{content}</div></details>"
            )
    return (
        "<section class='semantic-section raw-subjects'>"
        "<div class='section-heading'><div><p class='eyebrow'>精确对象核验</p>"
        f"<h2>全部 {len(review.subjects)} 个冻结对象</h2></div></div>"
        + "".join(sections)
        + "</section>"
    )


def _render_subject_metadata(envelope) -> str:
    return (
        "<dl class='metadata compact-metadata'>"
        f"<dt>对象类型</dt><dd>{html.escape(envelope.kind)}</dd>"
        f"<dt>数据格式</dt><dd>{html.escape(envelope.schema_id)}</dd>"
        f"<dt>媒体类型</dt><dd>{html.escape(envelope.media_type)}</dd>"
        f"<dt>SHA-256</dt><dd><code>{html.escape(envelope.ref.sha256)}</code></dd>"
        f"<dt>大小</dt><dd>{envelope.size_bytes} 字节</dd>"
        "</dl>"
    )


def _render_decision(
    review: ApprovalReview,
    access_token: str,
    identity: LocalIdentityRef,
    *,
    read_only: bool,
) -> str:
    if read_only:
        return (
            "<section class='decision-panel terminal'><p class='eyebrow'>历史记录</p>"
            "<h2>该审批入口已停用</h2>"
            "<p>实例创建和会话选择已迁移到直接本地管理页；"
            "此旧请求不能再写入决定。</p></section>"
        )
    if review.status != "pending":
        decision_value = (
            review.decision_ref.artifact_id
            if review.decision_ref is not None
            else "none"
        )
        return (
            "<section class='decision-panel terminal'><p class='eyebrow'>审批结果</p>"
            f"<h2>{html.escape(_STATUS_LABELS.get(review.status, review.status))}</h2>"
            "<p class='decision-record'>决定记录<br>"
            f"<code>{html.escape(decision_value)}</code></p></section>"
        )
    options = "".join(
        "<label class='decision-option'>"
        f"<input type='radio' name='selected_option' value='{html.escape(option.option_id, quote=True)}' "
        f"data-requires-rationale='{str(option.requires_rationale).lower()}' required>"
        "<span>"
        f"<strong>{html.escape(_OPTION_TEXT.get(option.label, option.label))}</strong>"
        f"<small>{_preview_text(_OPTION_TEXT.get(option.description, option.description), limit=128)}</small>"
        "</span></label>"
        for option in review.request.options
    )
    action = f"/review/{quote(review.request.approval_id, safe='')}/decision"
    return (
        "<section class='decision-panel'><p class='eyebrow'>人工决定</p>"
        "<h2>审阅结论</h2>"
        f"<a class='source-link' href='{_request_href(review, access_token)}'>完整审批问题与选项（原件）</a>"
        f"<form method='post' action='{html.escape(action, quote=True)}'>"
        f"<input type='hidden' name='token' value='{html.escape(access_token, quote=True)}'>"
        f"<input type='hidden' name='csrf' value='{html.escape(review.csrf_token, quote=True)}'>"
        f"<input type='hidden' name='nonce' value='{html.escape(review.decision_nonce, quote=True)}'>"
        "<input type='hidden' name='confirm' value='confirm'>"
        f"<div class='decision-options'>{options}</div>"
        "<label class='rationale'><span>决定理由 <small class='rationale-state'>选填</small></span>"
        "<textarea name='rationale' maxlength='16384'></textarea></label>"
        "<p class='identity'>审批身份 "
        f"<strong>{html.escape(identity.display_name)}</strong>"
        f"<code>{html.escape(identity.identity_id)}</code></p>"
        "<button class='submit-decision' type='submit'>确认并记录决定</button>"
        "</form></section>"
    )


def _render_request_metadata(review: ApprovalReview, status_label: str) -> str:
    request = review.request
    expires = request.expires_at or "无"
    compiled = request.compiled_identity
    compiled_rows = ""
    if compiled is not None:
        compiled_rows = (
            f"<dt>操作</dt><dd>{html.escape(compiled.operation_id)}</dd>"
            f"<dt>操作版本</dt><dd>{html.escape(compiled.operation_version)}</dd>"
            f"<dt>操作摘要</dt><dd><code>{html.escape(compiled.operation_digest)}</code></dd>"
            "<dt>审批合同摘要</dt>"
            f"<dd><code>{html.escape(compiled.approval_contract_digest)}</code></dd>"
        )
    return (
        "<details class='request-details'><summary>审批请求技术信息</summary>"
        "<dl class='metadata'>"
        f"<dt>请求类型</dt><dd>{html.escape(request.kind)}</dd>"
        f"<dt>请求 ID</dt><dd><code>{html.escape(request.approval_id)}</code></dd>"
        f"<dt>请求哈希</dt><dd><code>{html.escape(review.request_ref.sha256)}</code></dd>"
        f"<dt>对象集合哈希</dt><dd><code>{html.escape(request.subject_set_sha256)}</code></dd>"
        f"{compiled_rows}"
        f"<dt>过期时间</dt><dd>{html.escape(expires)}</dd>"
        f"<dt>当前状态</dt><dd>{html.escape(status_label)}</dd>"
        "</dl></details>"
    )


def _subject_href(review: ApprovalReview, index: int, access_token: str) -> str:
    approval_id = quote(review.request.approval_id, safe="")
    return (
        f"/subject/{approval_id}/{index}?token="
        f"{html.escape(access_token, quote=True)}"
    )


def _request_href(review: ApprovalReview, access_token: str) -> str:
    return (
        f"/request/{quote(review.request.approval_id, safe='')}?token="
        f"{html.escape(access_token, quote=True)}"
    )


def _preview_text(value: str, *, limit: int) -> str:
    preview = html.escape(value[:limit], quote=True)
    if len(value) > limit:
        preview += "<span class='preview-note'>…（长度超过页面预览范围，请读取完整原文）</span>"
    return preview


def _json_pointer_value(value: object, pointer: str) -> object:
    current = value
    for token in parse_json_pointer(pointer):
        if isinstance(current, dict):
            if token not in current:
                raise ValueError("review document pointer does not exist")
            current = current[token]
            continue
        if isinstance(current, list):
            valid_index = token == "0" or (
                bool(token)
                and token[0] in "123456789"
                and all(character in "0123456789" for character in token[1:])
            )
            if not valid_index:
                raise ValueError("review document array index is invalid")
            index = int(token)
            if index >= len(current):
                raise ValueError("review document array index is out of range")
            current = current[index]
            continue
        raise ValueError("review document pointer traverses a scalar")
    return current


def _escaped_json(value: object) -> str:
    return html.escape(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True),
        quote=True,
    )


__all__ = ["ReviewContext", "render_review"]
