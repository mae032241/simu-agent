from __future__ import annotations

import http.client
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import pytest

from scidiscovery.artifact_agent.approval_ui import ApprovalUI
from scidiscovery.artifact_agent.approval_ui.render import (
    ReviewContext,
    _json_pointer_value,
    render_review,
)
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.approval import (
    ApprovalOption,
    CompiledApprovalIdentity,
    LocalIdentityRef,
    ReviewDocument,
    ReviewDocumentItem,
    ReviewDocumentSection,
)
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json


def _runtime(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    return open_runtime(
        project_root=project,
        state_root=tmp_path / "state",
        approval_receipt_secret=os.urandom(32),
    )


def test_fixed_renderer_uses_ascii_json_array_indices() -> None:
    value = {"items": ["first", "second"]}
    assert _json_pointer_value(value, "/items/1") == "second"
    for pointer in (
        "/items/01",
        "/items/2",
        "/items/value",
        "/items/1/value",
        "/items/١",
        "/items/²",
    ):
        with pytest.raises(ValueError):
            _json_pointer_value(value, pointer)


def _subject(runtime, *, raw: bytes, name: str, schema_id: str, media_type: str):
    return runtime.artifacts.register(
        raw,
        ArtifactRegistration(
            kind="architecture_test_input",
            schema_id=schema_id,
            payload_schema_version=1,
            media_type=media_type,
            creator=runtime.actor,
        ),
        idempotency_key=f"r4d-renderer:{name}",
    ).ref


def _options() -> tuple[ApprovalOption, ...]:
    return (
        ApprovalOption(
            option_id="approve",
            label="批准",
            description="批准精确冻结对象。",
            requires_rationale=False,
        ),
        ApprovalOption(
            option_id="revise",
            label="要求修订",
            description="拒绝当前对象并要求修订。",
            requires_rationale=True,
        ),
    )


def _malicious_review(runtime):
    structured = _subject(
        runtime,
        raw=canonical_json(
            {
                "value": "javascript:alert(1)",
                "status": "<svg onload=alert(2)>",
                "tree": {"unsafe": "<iframe srcdoc='<script>x</script>'>"},
            }
        ),
        name="structured",
        schema_id="plugin.synthetic-review.v1",
        media_type="application/json",
    )
    binary = _subject(
        runtime,
        raw=b"<script>binary must never be inlined</script>",
        name="binary",
        schema_id="plugin.synthetic-binary.v1",
        media_type="image/png",
    )
    document = ReviewDocument(
        title="<script>document title</script>",
        description="<img src=x onerror=alert(3)>",
        sections=(
            ReviewDocumentSection(
                title="<style>body{display:none}</style>",
                description="<a href='javascript:alert(4)'>unsafe</a>",
                items=(
                    ReviewDocumentItem(
                        kind="json_value",
                        label="<script>value label</script>",
                        subject_index=0,
                        json_pointer="/value",
                    ),
                    ReviewDocumentItem(
                        kind="status",
                        label="状态",
                        subject_index=0,
                        json_pointer="/status",
                    ),
                    ReviewDocumentItem(
                        kind="json_tree",
                        label="完整子树",
                        subject_index=0,
                        json_pointer="/tree",
                    ),
                    ReviewDocumentItem(
                        kind="subject_metadata",
                        label="二进制元数据",
                        subject_index=1,
                    ),
                    ReviewDocumentItem(
                        kind="download",
                        label="固定下载",
                        subject_index=1,
                    ),
                ),
            ),
        ),
    )
    launch = runtime.approvals.create_request(
        approval_id="r4d_fixed_renderer",
        kind="synthetic_plugin_review",
        subject_refs=(structured, binary),
        question="<script>question</script>",
        options=_options(),
        requested_by=runtime.actor,
        idempotency_key="r4d-renderer:request",
        review_document=document,
        compiled_identity=CompiledApprovalIdentity(
            operation_id="plugin.synthetic.approve.v1",
            operation_version="1",
            operation_digest="1" * 64,
            approval_contract_digest="2" * 64,
        ),
    )
    review = runtime.approvals.review(
        launch.approval_id, access_token=launch.access_token
    )
    return launch, review, binary


def test_fixed_review_document_renderer_escapes_all_plugin_values(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    launch, review, binary = _malicious_review(runtime)
    page = render_review(
        review,
        access_token=launch.access_token,
        identity=LocalIdentityRef(
            identity_id="local_test_user",
            display_name="<img src=x onerror=alert(5)>",
        ),
    ).decode("utf-8")

    assert page.count("<script") == 1
    assert "<script src='/static/app.js' defer></script>" in page
    for executable in ("<style", "<svg", "<iframe", "<img"):
        assert executable not in page
    assert "&lt;script&gt;document title&lt;/script&gt;" in page
    assert "javascript:alert(1)" in page
    assert not re.search(r"href=['\"](?:javascript|data):", page, re.IGNORECASE)
    assert "binary must never be inlined" not in page
    assert binary.sha256 in page
    assert (
        f"/subject/r4d_fixed_renderer/1?token={launch.access_token}" in page
    )
    assert "plugin.synthetic.approve.v1" in page
    assert page.count("<details class='raw-subject'>") == 2
    assert "<details class='raw-subject' open>" not in page
    assert "<details class='request-details' open>" not in page
    assert "<dl class='value-map'>" in page
    assert "查看来源" in page and "原记录位置：/tree" in page
    assert "<pre class='json-value'>" not in page



def test_renderer_uses_raw_fallback_without_domain_schema_dispatch(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    subject = _subject(
        runtime,
        raw=canonical_json(
            {"domain_marker": "visible from the complete frozen object"}
        ),
        name="historical",
        schema_id="tcad.execution-package.v2",
        media_type="application/json",
    )
    launch = runtime.approvals.create_request(
        approval_id="r4d_historical_raw",
        kind="execution_authorization",
        subject_refs=(subject,),
        question="Review a historical request without a document?",
        options=_options(),
        requested_by=runtime.actor,
        idempotency_key="r4d-renderer:historical",
    )
    review = runtime.approvals.review(
        launch.approval_id, access_token=launch.access_token
    )
    page = render_review(
        review,
        access_token=launch.access_token,
        identity=LocalIdentityRef(
            identity_id="local_test_user", display_name="Local test user"
        ),
    ).decode("utf-8")

    assert "历史审批记录" in page
    assert "固定安全回退" in page
    assert "visible from the complete frozen object" in page
    assert "TCAD 执行审批" not in page
    assert "<details class='raw-subject'>" in page
    assert "<details class='raw-subject' open>" not in page
    assert "下载冻结文件" in page

    source = Path(render_review.__code__.co_filename).read_text(encoding="utf-8")
    for forbidden in (
        "scidiscovery.scientific-foundation.v1",
        "scidiscovery.figure-evidence-manifest.v1",
        "scidiscovery.device-parameter-set.v1",
        "tcad.execution-package.v2",
        "_render_tcad",
        "_render_device_parameter",
        "_render_figure",
        "_render_scientific_foundation",
    ):
        assert forbidden not in source


def test_http_surface_only_downloads_binary_and_removes_preview_route(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    launch, _, _ = _malicious_review(runtime)
    ui = ApprovalUI(runtime.approvals)
    base = ui.start()
    try:
        parsed = urlparse(base)

        def request(path: str):
            connection = http.client.HTTPConnection(
                parsed.hostname, parsed.port, timeout=5
            )
            connection.request("GET", path)
            response = connection.getresponse()
            raw = response.read()
            result = response.status, dict(response.getheaders()), raw
            connection.close()
            return result

        page_status, page_headers, page_raw = request(launch.review_path)
        assert page_status == 200
        assert page_headers["X-Content-Type-Options"] == "nosniff"
        assert page_headers["Referrer-Policy"] == "same-origin"
        assert b"name='referrer'" not in page_raw
        assert "script-src 'self'" in page_headers["Content-Security-Policy"]
        assert b"binary must never be inlined" not in page_raw

        download_path = (
            "/subject/r4d_fixed_renderer/1?token=" + launch.access_token
        )
        status, headers, raw = request(download_path)
        assert status == 200
        assert headers["Content-Type"] == "application/octet-stream"
        assert headers["Content-Disposition"] == (
            "attachment; filename=subject-1.bin"
        )
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert raw == b"<script>binary must never be inlined</script>"

        preview_status, _, _ = request(
            "/preview/r4d_fixed_renderer/1?token=" + launch.access_token
        )
        assert preview_status == 404
    finally:
        ui.stop()


def test_large_frozen_subject_is_not_embedded_and_download_is_unchanged(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    raw = canonical_json({"summary": "original summary", "large_report": "not-for-first-page" * 50000})
    subject = _subject(runtime, raw=raw, name="large", schema_id="plugin.large.v1", media_type="application/json")
    launch = runtime.approvals.create_request(
        approval_id="r4d_large_readable",
        kind="synthetic_plugin_review",
        subject_refs=(subject,),
        question="Review exact frozen report?",
        options=_options(),
        requested_by=runtime.actor,
        idempotency_key="r4d-renderer:large",
        review_document=ReviewDocument(title="Readable report", sections=(ReviewDocumentSection(
            title="Original fields", items=(ReviewDocumentItem(kind="json_tree", label="Report", subject_index=0, json_pointer=""),),
        ),)),
    )
    review = runtime.approvals.review(launch.approval_id, access_token=launch.access_token)
    page = render_review(review, access_token=launch.access_token,
        identity=LocalIdentityRef(identity_id="local_test_user", display_name="Reviewer"),
        context=ReviewContext(instance_name="instance", instance_title="Instance", instance_objective="Current administrative description",
            approval_name="request", approval_logical_name="request", approval_revision=1),
        presentation={"sections": [{"title": "Original research objective", "items": [{"label": "Objective",
            "value": "Historically bound original objective", "source": {"artifact_id": subject.artifact_id, "json_pointer": "/summary"}}]}]},
    )
    assert len(page) <= 256 * 1024
    text = page.decode("utf-8")
    assert "实例管理描述" in text
    assert "Historically bound original objective" in text
    assert "原始 JSON 较大，未嵌入页面" in text
    assert "<form method='post' action='/review/r4d_large_readable/decision'>" in text
    assert f"name='csrf' value='{review.csrf_token}'" in text
    assert f"name='nonce' value='{review.decision_nonce}'" in text
    assert subject.sha256 in text
    assert review.request_ref.sha256 in text
    assert runtime.approvals.review(launch.approval_id, access_token=launch.access_token).subjects[0][1] == raw


def test_maximum_request_text_uses_explicit_preview_and_exact_request_link(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    subject = _subject(runtime, raw=b"{}", name="maximum-text", schema_id="plugin.large.v1", media_type="application/json")
    options = tuple(ApprovalOption(option_id=f"option_{index}", label="\"" * 256,
        description="\"" * 4096, requires_rationale=bool(index % 2)) for index in range(32))
    launch = runtime.approvals.create_request(
        approval_id="r4d_maximum_text", kind="synthetic_plugin_review", subject_refs=(subject,),
        question="\"" * 16384, options=options, requested_by=runtime.actor,
        idempotency_key="r4d-renderer:maximum-text",
    )
    review = runtime.approvals.review(launch.approval_id, access_token=launch.access_token)
    page = render_review(review, access_token=launch.access_token,
        identity=LocalIdentityRef(identity_id="local_test_user", display_name="Reviewer"))
    text = page.decode("utf-8")
    assert len(page) <= 256 * 1024
    assert "长度超过页面预览范围，请读取完整原文" in text
    assert "完整审批问题与选项（原件）" in text
    assert f"/request/r4d_maximum_text?token={launch.access_token}" in text
    for option in options:
        assert f"value='{option.option_id}'" in text
        assert f"data-requires-rationale='{str(option.requires_rationale).lower()}'" in text
    assert review.request.question == "\"" * 16384
    assert review.request.options == options
