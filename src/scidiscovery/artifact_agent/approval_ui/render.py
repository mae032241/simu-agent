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


_STATUS_LABELS = {
    "pending": "待审批",
    "decided": "已决定",
    "expired": "已过期",
    "cancelled_by_human": "已由用户取消",
}

@dataclass(frozen=True)
class ReviewContext:
    instance_name: str
    instance_title: str
    instance_objective: str
    approval_name: str
    approval_logical_name: str
    approval_revision: int


def render_review(
    review: ApprovalReview,
    *,
    access_token: str,
    identity: LocalIdentityRef,
    context: ReviewContext | None = None,
    read_only: bool = False,
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
    document_panel = (
        _render_document(review, document, access_token)
        if document is not None
        else _render_fallback_notice(request.kind)
    )
    page = (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(title)} · 科研审批</title>"
        "<link rel='stylesheet' href='/static/style.css'>"
        "<script src='/static/app.js' defer></script></head><body>"
        "<header class='topbar'><div class='topbar-inner'>"
        "<div><p class='product-name'>科研审批</p>"
        f"<h1>{html.escape(title)}</h1></div>"
        f"<span class='status-badge'>{html.escape(status_label)}</span>"
        "</div></header>"
        "<main class='page'>"
        f"{_render_review_context(context)}"
        "<section class='review-intro'>"
        "<p class='eyebrow'>审批问题</p>"
        f"<p class='question'>{html.escape(request.question)}</p>"
        f"{_render_request_metadata(review, status_label)}"
        "</section>"
        "<div class='review-layout'><div class='review-main'>"
        f"{document_panel}"
        f"{_render_raw_subjects(review, access_token)}"
        "</div>"
        f"<aside class='decision-column'>{_render_decision(review, access_token, identity, read_only=read_only)}</aside>"
        "</div></main></body></html>"
    )
    return page.encode("utf-8")


def _render_document(
    review: ApprovalReview,
    document: ReviewDocument,
    access_token: str,
) -> str:
    sections = "".join(
        "<section class='semantic-section review-document-section'>"
        "<div class='section-heading'><div>"
        f"<h2>{html.escape(section.title)}</h2>"
        f"<p>{html.escape(section.description)}</p>"
        "</div></div>"
        "<div class='review-document-items'>"
        + "".join(
            _render_document_item(review, item, access_token)
            for item in section.items
        )
        + "</div></section>"
        for section in document.sections
    )
    description = (
        f"<p class='bounded-note'>{html.escape(document.description)}</p>"
        if document.description
        else ""
    )
    return (
        "<section class='semantic-section review-document-intro'>"
        "<p class='eyebrow'>已编译审批视图</p>"
        f"<h2>{html.escape(document.title)}</h2>{description}"
        "<p class='bounded-note'>本视图只读取审批请求中已经冻结的标签、对象序号和 JSON 指针；"
        "完整对象与精确字节见下方原始数据。</p></section>"
        f"{sections}"
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
        value = _json_pointer_value(json.loads(raw), item.json_pointer)
        if item.kind == "json_value":
            content = f"<pre class='json-value'>{_escaped_json(value)}</pre>"
        elif item.kind == "status":
            content = (
                "<p class='status-badge review-document-status'>"
                f"{html.escape(_display_scalar(value))}</p>"
            )
        else:
            content = f"<pre class='json-tree'>{_escaped_json(value)}</pre>"
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
    revision = (
        f" · 修订 {context.approval_revision}"
        if context.approval_revision > 1
        else ""
    )
    return (
        "<section class='instance-context'>"
        "<div class='instance-primary'><p class='eyebrow'>研究实例</p>"
        f"<strong>{html.escape(context.instance_title)}</strong>"
        f"<code>{html.escape(context.instance_name)}</code></div>"
        "<div class='instance-objective'><p class='eyebrow'>实例目标</p>"
        f"<p>{html.escape(context.instance_objective)}</p></div>"
        "<div class='approval-context'><p class='eyebrow'>审批项</p>"
        f"<strong>{html.escape(context.approval_name)}</strong>"
        f"<span>{html.escape(context.approval_logical_name)}{revision}</span></div>"
        "</section>"
    )


def _render_raw_subjects(review: ApprovalReview, access_token: str) -> str:
    sections = []
    for index, (envelope, raw) in enumerate(review.subjects):
        base_type = envelope.media_type.split(";", 1)[0].strip().lower()
        if base_type == "application/json":
            try:
                content = f"<pre class='json-tree'>{_escaped_json(json.loads(raw))}</pre>"
            except (UnicodeDecodeError, json.JSONDecodeError):
                content = (
                    "<p class='binary-note'>该对象声明为 JSON，但不能安全解析；"
                    "请下载精确冻结字节核验。</p>"
                )
        else:
            content = (
                "<p class='binary-note'>该对象不是 JSON。固定渲染器只显示元数据并提供下载，"
                "不会内联解释其内容。</p>"
            )
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
        f"<strong>{html.escape(option.label)}</strong>"
        f"<small>{html.escape(option.description)}</small>"
        "</span></label>"
        for option in review.request.options
    )
    action = f"/review/{quote(review.request.approval_id, safe='')}/decision"
    return (
        "<section class='decision-panel'><p class='eyebrow'>人工决定</p>"
        "<h2>审阅结论</h2>"
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


def _display_scalar(value: object) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


__all__ = ["ReviewContext", "render_review"]
