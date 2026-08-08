from __future__ import annotations

import http.client
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse

import pytest

from scidiscovery.artifact_agent import ApprovalOption, LocalIdentityRef, canonical_json
from scidiscovery.artifact_agent.approval_ui import ApprovalUI
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.service import SchedulerBindingService

from ._approval_fixtures import OPTIONS, REQUESTER, create_request, make_approval_fixture


def _request(base_url: str, method: str, path: str, *, body: str | None = None, headers=None):
    parsed = urlparse(base_url)
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=5)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    payload = response.read()
    result = response.status, dict(response.getheaders()), payload
    connection.close()
    return result


def test_dashboard_lists_pending_reviews_without_agent_receiving_token(
    tmp_path: Path,
) -> None:
    fixture = make_approval_fixture(tmp_path)
    launch = create_request(fixture)
    ui = ApprovalUI(fixture.approvals)
    base = ui.start()
    try:
        status, _, body = _request(base, "GET", "/")
        text = body.decode("utf-8")
        assert status == 200
        assert "待审批事项" in text
        assert "problem_spec_review" in text
        assert launch.review_path in text
    finally:
        ui.stop()


def test_dashboard_recovers_expired_pending_review_access(tmp_path: Path) -> None:
    fixture = make_approval_fixture(tmp_path)
    launch = create_request(
        fixture,
        now=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    ui = ApprovalUI(fixture.approvals)
    base = ui.start()
    try:
        status, _, body = _request(base, "GET", "/")
        dashboard = body.decode("utf-8")
        assert status == 200
        assert launch.review_path not in dashboard
        match = re.search(r'href="(/review/review_one\?token=[^"]+)"', dashboard)
        assert match is not None

        recovered_path = match.group(1)
        status, _, _ = _request(base, "GET", recovered_path)
        assert status == 200
        status, _, _ = _request(base, "GET", launch.review_path)
        assert status == 403
    finally:
        ui.stop()


def test_dashboard_and_review_show_research_instance_and_human_question(
    tmp_path: Path,
) -> None:
    fixture = make_approval_fixture(tmp_path)
    launch = create_request(fixture)
    bindings = SchedulerBindingService(tmp_path / "state" / "scheduler.sqlite3")
    instance = bindings.create_instance(
        name="fig4_sims_validation",
        title="Fig. 4 SIMS 工程验证",
        objective="验证实例归属和审批内容，不提交求解器任务。",
    )
    bindings.bind(
        instance=instance.instance_id,
        namespace="approval",
        name="scientific_foundation_review",
        object_id="review_one",
    )
    ui = ApprovalUI(fixture.approvals, bindings=bindings)
    base = ui.start()
    try:
        status, _, body = _request(base, "GET", "/")
        dashboard = body.decode("utf-8")
        assert status == 200
        assert "Fig. 4 SIMS 工程验证" in dashboard
        assert "fig4_sims_validation" in dashboard
        assert "Are these exact frozen subjects correct?" in dashboard
        assert "scientific_foundation_review" in dashboard

        status, _, body = _request(base, "GET", launch.review_path)
        review = body.decode("utf-8")
        assert status == 200
        assert "研究实例" in review
        assert "Fig. 4 SIMS 工程验证" in review
        assert "fig4_sims_validation" in review
        assert "验证实例归属和审批内容，不提交求解器任务。" in review
        assert "scientific_foundation_review" in review
    finally:
        ui.stop()


def test_local_ui_decision_is_the_only_path_that_activates_instance_proposal(
    tmp_path: Path,
) -> None:
    fixture = make_approval_fixture(tmp_path)
    bindings = SchedulerBindingService(tmp_path / "state" / "scheduler.sqlite3")
    proposal = bindings.prepare_instance_proposal(
        name="user_created_instance",
        title="用户创建的研究实例",
        objective="只有网页确认后才建立该研究边界。",
        session_key="sch_user_creation",
    )
    proposal_ref = fixture.artifacts.register(
        canonical_json(
            {
                "schema_version": 1,
                "name": proposal.name,
                "title": proposal.title,
                "objective": proposal.objective,
                "authorization_effect": "用户确认后创建并绑定该实例。",
                "non_effects": [
                    "不批准任何科学结论",
                    "不授权任何仿真执行",
                ],
            }
        ),
        ArtifactRegistration(
            artifact_id="instance_proposal_subject",
            kind="research_instance_proposal",
            schema_id="scidiscovery.research-instance-proposal.v1",
            payload_schema_version=1,
            media_type="application/json",
            creator=REQUESTER,
        ),
        idempotency_key="subject:instance-proposal",
    ).ref
    launch = fixture.approvals.create_request(
        approval_id=proposal.approval_id,
        kind="research_instance_registration",
        subject_refs=(proposal_ref,),
        question="是否创建该研究实例？",
        options=(
            ApprovalOption(
                option_id="create_instance",
                label="创建并进入该实例",
                description="创建页面展示的实例。",
                requires_rationale=False,
            ),
            ApprovalOption(
                option_id="revise_instance",
                label="要求修改草案",
                description="暂不创建并要求修改。",
                requires_rationale=True,
            ),
            ApprovalOption(
                option_id="cancel_instance",
                label="取消创建",
                description="关闭本次草案。",
                requires_rationale=False,
                terminal_state="cancelled_by_human",
            ),
        ),
        requested_by=REQUESTER,
        idempotency_key="approval:user-created-instance",
    )
    assert bindings.list_instances() == ()

    ui = ApprovalUI(fixture.approvals, bindings=bindings)
    base = ui.start()
    try:
        status, _, dashboard_body = _request(base, "GET", "/")
        dashboard = dashboard_body.decode("utf-8")
        assert status == 200
        assert "待创建研究实例" in dashboard
        assert "用户创建的研究实例" in dashboard
        assert "user_created_instance" in dashboard

        status, _, review_body = _request(base, "GET", launch.review_path)
        review_page = review_body.decode("utf-8")
        assert status == 200
        assert "实例草案" in review_page
        assert "研究实例定义" in review_page
        assert "本次批准不包含" in review_page
        assert "不批准任何科学结论" in review_page

        review = fixture.approvals.review(
            proposal.approval_id,
            access_token=launch.access_token,
        )
        body = urlencode(
            {
                "token": launch.access_token,
                "csrf": review.csrf_token,
                "nonce": review.decision_nonce,
                "selected_option": "create_instance",
                "rationale": "",
                "confirm": "confirm",
            }
        )
        status, _, _ = _request(
            base,
            "POST",
            f"/review/{proposal.approval_id}/decision",
            body=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": base,
            },
        )
        assert status == 303
    finally:
        ui.stop()

    instance = bindings.select_instance(name="user_created_instance")
    assert bindings.session_instance(
        session_key="sch_user_creation"
    ) == instance.instance_id


def test_local_ui_session_takeover_binds_new_process_and_revokes_old(
    tmp_path: Path,
) -> None:
    fixture = make_approval_fixture(tmp_path)
    bindings = SchedulerBindingService(tmp_path / "state" / "scheduler.sqlite3")
    instance = bindings.create_instance(
        name="fig4_resume",
        title="Fig. 4 继续执行",
        objective="由用户确认新的 MCP 进程接管已有研究实例。",
    )
    bindings.bind_session(session_key="sch_old_process", instance_id=instance.instance_id)
    request, candidates = bindings.prepare_session_binding_request(
        session_key="sch_new_process"
    )
    subject = fixture.artifacts.register(
        canonical_json(
            {
                "schema_version": 1,
                "authorization_effect": "新进程接管实例，旧进程绑定作废。",
                "candidates": [
                    {
                        "option_id": candidates[0].option_id,
                        "name": instance.name,
                        "title": instance.title,
                        "objective": instance.objective,
                        "state": instance.state,
                    }
                ],
                "non_effects": ["不启动仿真", "不批准科学结论"],
            }
        ),
        ArtifactRegistration(
            artifact_id="session_binding_subject",
            kind="research_session_binding_proposal",
            schema_id="scidiscovery.session-binding-proposal.v1",
            payload_schema_version=1,
            media_type="application/json",
            creator=REQUESTER,
        ),
        idempotency_key="subject:session-binding",
    ).ref
    launch = fixture.approvals.create_request(
        approval_id=request.approval_id,
        kind="research_session_binding",
        subject_refs=(subject,),
        question="当前 MCP 进程是否接管该研究实例？",
        options=(
            ApprovalOption(
                option_id=candidates[0].option_id,
                label="进入 Fig. 4 继续执行",
                description="绑定新进程并撤销旧进程绑定。",
                requires_rationale=False,
            ),
            ApprovalOption(
                option_id="cancel_binding",
                label="暂不绑定",
                description="保持新进程未绑定。",
                requires_rationale=False,
                terminal_state="cancelled_by_human",
            ),
        ),
        requested_by=REQUESTER,
        idempotency_key="approval:session-binding",
    )

    ui = ApprovalUI(fixture.approvals, bindings=bindings)
    base = ui.start()
    try:
        status, _, dashboard_body = _request(base, "GET", "/")
        dashboard = dashboard_body.decode("utf-8")
        assert status == 200
        assert "待绑定研究实例" in dashboard
        assert "MCP 进程绑定" in dashboard

        status, _, review_body = _request(base, "GET", launch.review_path)
        review_page = review_body.decode("utf-8")
        assert status == 200
        assert "选择进程归属" in review_page
        assert "Fig. 4 继续执行" in review_page
        assert "旧进程绑定作废" in review_page

        review = fixture.approvals.review(
            request.approval_id, access_token=launch.access_token
        )
        body = urlencode(
            {
                "token": launch.access_token,
                "csrf": review.csrf_token,
                "nonce": review.decision_nonce,
                "selected_option": candidates[0].option_id,
                "rationale": "",
                "confirm": "confirm",
            }
        )
        status, _, _ = _request(
            base,
            "POST",
            f"/review/{request.approval_id}/decision",
            body=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": base,
            },
        )
        assert status == 303
    finally:
        ui.stop()

    assert bindings.session_instance(session_key="sch_new_process") == instance.instance_id
    assert bindings.session_instance(session_key="sch_old_process") is None


def test_loopback_page_shows_complete_content_and_security_headers(tmp_path: Path) -> None:
    fixture = make_approval_fixture(tmp_path)
    launch = create_request(fixture)
    ui = ApprovalUI(
        fixture.approvals,
        local_identity=LocalIdentityRef(
            identity_id="user_da", display_name="Local User"
        ),
    )
    base = ui.start()
    try:
        status, headers, body = _request(base, "GET", launch.review_path)
        text = body.decode()
        assert status == 200
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["Referrer-Policy"] == "same-origin"
        assert headers["Cache-Control"] == "no-store"
        assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
        assert "完整审查对象" in text
        assert "x" * 1000 in text
        assert "[]" in text
        assert "data-pointer='/nested/value'" in text
        assert "对象内容" in text
        assert "来源与假设" in text
        assert "语义变更" in text
        assert "原始数据" in text
        assert "审批请求技术信息" in text
        assert "Scientific Artifact Review" in text
        assert "Raw JSON" not in text
        assert "data-tree-action='expand'" in text
        assert "data-tree-action='collapse'" in text
        assert (
            "class='tree-node tree-branch' data-pointer='/nested'>" in text
        )
        assert (
            "class='tree-node tree-branch' data-pointer='/' open>" in text
        )
        assert "role='treeitem'" not in text
        assert "Approve exact subjects" in text
        assert "确认并记录决定" in text

        parsed_base = urlparse(base)
        loopback_alias = f"localhost:{parsed_base.port}"
        alias_status, _, alias_body = _request(
            base,
            "GET",
            launch.review_path,
            headers={"Host": loopback_alias},
        )
        assert alias_status == 200
        assert "Scientific Artifact Review" in alias_body.decode()

        non_loopback_host, _, _ = _request(
            base,
            "GET",
            launch.review_path,
            headers={"Host": f"example.invalid:{parsed_base.port}"},
        )
        assert non_loopback_host == 403

        download_status, download_headers, download_body = _request(
            base,
            "GET",
            f"/subject/review_one/1?token={launch.access_token}",
        )
        assert download_status == 200
        assert download_headers["Content-Type"] == "application/octet-stream"
        assert download_headers["Content-Disposition"] == (
            "attachment; filename=subject-1.bin"
        )
        assert download_body == b"binary subject"

        missing_status, _, _ = _request(base, "GET", "/review/review_one")
        wrong_status, _, _ = _request(
            base, "GET", "/review/review_one?token=wrong"
        )
        assert missing_status in {403, 404}
        assert wrong_status == 403

        review = fixture.approvals.review(
            "review_one", access_token=launch.access_token
        )
        form = urlencode(
            {
                "token": launch.access_token,
                "csrf": review.csrf_token,
                "nonce": review.decision_nonce,
                "selected_option": "approve",
                "rationale": "",
                "confirm": "confirm",
            }
        )
        no_origin, _, _ = _request(
            base,
            "POST",
            "/review/review_one/decision",
            body=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert no_origin == 403
        wrong_origin, _, _ = _request(
            base,
            "POST",
            "/review/review_one/decision",
            body=form,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "http://evil.invalid",
            },
        )
        assert wrong_origin == 403
        null_origin, _, _ = _request(
            base,
            "POST",
            "/review/review_one/decision",
            body=form,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "null",
            },
        )
        assert null_origin == 403
        bad_form = urlencode(
            {
                "token": launch.access_token,
                "csrf": "wrong",
                "nonce": review.decision_nonce,
                "selected_option": "approve",
                "rationale": "",
                "confirm": "confirm",
            }
        )
        bad_csrf, _, _ = _request(
            base,
            "POST",
            "/review/review_one/decision",
            body=bad_form,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": base,
            },
        )
        assert bad_csrf == 403
        alias_origin, _, _ = _request(
            base,
            "POST",
            launch.review_path.replace("?", "/decision?", 1),
            body=form,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Host": loopback_alias,
                "Origin": f"http://{loopback_alias}",
            },
        )
        assert alias_origin == 303

        refreshed_alias, _, terminal_alias = _request(
            base,
            "GET",
            launch.review_path,
            headers={"Host": loopback_alias},
        )
        assert refreshed_alias == 200
        assert "审批结果" in terminal_alias.decode()
    finally:
        ui.stop()


def test_execution_review_shows_deck_parameters_limits_outputs_and_source(
    tmp_path: Path,
) -> None:
    fixture = make_approval_fixture(tmp_path)
    project_ref = fixture.artifacts.register(
        canonical_json(
            {
                "schema_version": 1,
                "tool_profile": "sentaurus-sprocess-r2020.09",
                "files": [
                    {
                        "relative_path": "fig4.cmd",
                        "content": "set TemperatureC 480\nset TimeMin 8.0\n",
                    }
                ],
                "entrypoint": "fig4.cmd",
                "arguments": [],
                "expected_outputs": [
                    {
                        "name": "profile",
                        "relative_path": "results/fig4.plx",
                        "media_type": "text/plain",
                        "required": True,
                        "max_bytes": 1024,
                    }
                ],
                "parameter_bindings": [
                    {
                        "name": "temperature",
                        "declared_value": "480",
                        "unit": "degC",
                        "relative_path": "fig4.cmd",
                        "locator": "set TemperatureC 480",
                        "evidence_class": "paper_fact",
                        "evidence_source": "J. Appl. Phys. 137, 123103 (2025)",
                        "evidence_locator": "Table I",
                        "rationale": "Table I reports the diffusion temperature.",
                    }
                ],
                "runtime_assertions": [
                    {
                        "description": "The PLX profile must exist.",
                        "expected_output_name": "profile",
                    }
                ],
                "resource_limits": {
                    "wall_time_seconds": 180,
                    "cpu_time_seconds": 180,
                    "max_memory_bytes": 4 * 1024 * 1024 * 1024,
                    "max_output_bytes": 256 * 1024 * 1024,
                    "max_processes": 16,
                },
            }
        ),
        ArtifactRegistration(
            artifact_id="art_execution_project",
            kind="tcad_project",
            schema_id="tcad.deck-project.v1",
            payload_schema_version=1,
            media_type="application/json",
            creator=REQUESTER,
        ),
        idempotency_key="subject:execution-project",
    ).ref
    request_ref = fixture.artifacts.register(
        canonical_json(
            {
                "schema_version": 1,
                "execution_id": "exe_review_fixture",
                "executor": "tcad",
                "preparation_profile": "tcad.deck-project.v1",
                "payload_ref": project_ref.model_dump(mode="json"),
                "created_at": "2026-08-03T00:00:00Z",
            }
        ),
        ArtifactRegistration(
            artifact_id="art_execution_request",
            kind="execution_request",
            schema_id="scidiscovery.execution-request",
            payload_schema_version=1,
            media_type="application/json",
            creator=REQUESTER,
            parent_refs=(project_ref,),
            confidentiality="approval_only",
        ),
        idempotency_key="subject:execution-request",
    ).ref
    launch = fixture.approvals.create_request(
        approval_id="review_execution",
        kind="execution_authorization",
        subject_refs=(request_ref, project_ref),
        question="Authorize this exact execution?",
        options=OPTIONS,
        requested_by=REQUESTER,
        idempotency_key="approval:execution",
    )
    ui = ApprovalUI(fixture.approvals)
    base = ui.start()
    try:
        status, _, body = _request(base, "GET", launch.review_path)
        text = body.decode()
        assert status == 200
        assert "TCAD 执行审批" in text
        assert "将要执行的 TCAD 工程" in text
        assert "sentaurus-sprocess-r2020.09" in text
        assert "fig4.cmd" in text
        assert "temperature" in text
        assert "480 degC" in text
        assert "paper_fact" in text
        assert "J. Appl. Phys. 137, 123103 (2025)" in text
        assert "Table I" in text
        assert "Table I reports the diffusion temperature." in text
        assert "results/fig4.plx" in text
        assert "3 分钟" in text
        assert "4 GiB" in text
        assert "set TemperatureC 480" in text
        assert "不代表物理模型或论文拟合已经通过" in text
    finally:
        ui.stop()


def test_scientific_foundation_review_shows_scope_conditions_and_sources(
    tmp_path: Path,
) -> None:
    fixture = make_approval_fixture(tmp_path)
    foundation_ref = fixture.artifacts.register(
        canonical_json(
            {
                "schema_version": 1,
                "title": "Fig. 4 科学基础资料",
                "objective": "复现 480 C、8 min 的 Zn 总浓度曲线。",
                "summary": "论文参数与数值假设已经分开。",
                "items": [
                    {
                        "schema_version": 1,
                        "item_key": "da_ingaas",
                        "item_type": "parameter",
                        "epistemic_status": "paper_fact",
                        "statement": "Model-A 扩散系数为 1.05e-12 cm2/s。",
                        "value": 1.05e-12,
                        "unit": "cm^2/s",
                        "scope": "论文 Fig. 4 的单层 InGaAs 模型。",
                        "conditions": [
                            {
                                "schema_version": 1,
                                "name": "temperature",
                                "value": 480,
                                "unit": "degC",
                            }
                        ],
                        "evidence_keys": ["paper_pdf"],
                    },
                    {
                        "schema_version": 1,
                        "item_key": "source_boundary",
                        "item_type": "assumption",
                        "epistemic_status": "assumption",
                        "statement": "采用有限源边界。",
                        "scope": "仅用于当前数值实现。",
                        "rationale": "论文未完整给出边界条件。",
                    },
                ],
                "evidence": [
                    {
                        "schema_version": 1,
                        "source_key": "paper_pdf",
                        "source_type": "frozen_input",
                        "title": "Zn diffusion paper",
                        "locator": "Table I",
                        "excerpt": "DA=1.05e-12 cm2/s",
                    }
                ],
                "conflicts": [
                    {
                        "schema_version": 1,
                        "conflict_key": "boundary_unspecified",
                        "statement": "论文没有完整报告源边界。",
                        "item_keys": ["source_boundary"],
                        "status": "unresolved",
                    }
                ],
                "missing_inputs": ["扩散系数不确定度"],
                "open_questions": ["边界条件是否影响前沿宽度？"],
            }
        ),
        ArtifactRegistration(
            artifact_id="art_scientific_foundation",
            kind="scientific_foundation",
            schema_id="scidiscovery.scientific-foundation.v1",
            payload_schema_version=1,
            media_type="application/json",
            creator=REQUESTER,
        ),
        idempotency_key="subject:scientific-foundation",
    ).ref
    launch = fixture.approvals.create_request(
        approval_id="review_scientific_foundation",
        kind="scientific_foundation",
        subject_refs=(foundation_ref,),
        question="这些科学基础资料是否准确？",
        options=OPTIONS,
        requested_by=REQUESTER,
        idempotency_key="approval:scientific-foundation",
    )
    ui = ApprovalUI(fixture.approvals)
    base = ui.start()
    try:
        status, _, body = _request(base, "GET", launch.review_path)
        text = body.decode()
        assert status == 200
        assert "待人工确认的科学基础" in text
        assert "复现 480 C、8 min" in text
        assert "论文 Fig. 4 的单层 InGaAs 模型" in text
        assert "temperature=480 degC" in text
        assert "Zn diffusion paper" in text
        assert "Table I" in text
        assert "论文没有完整报告源边界" in text
        assert "扩散系数不确定度" in text
        assert "边界条件是否影响前沿宽度" in text
    finally:
        ui.stop()


def test_exact_host_decision_flow_remains_supported(tmp_path: Path) -> None:
    fixture = make_approval_fixture(tmp_path)
    launch = create_request(fixture, approval_id="review_exact_host")
    ui = ApprovalUI(fixture.approvals)
    base = ui.start()
    try:
        review = fixture.approvals.review(
            "review_exact_host", access_token=launch.access_token
        )
        form = urlencode(
            {
                "token": launch.access_token,
                "csrf": review.csrf_token,
                "nonce": review.decision_nonce,
                "selected_option": "approve",
                "rationale": "",
                "confirm": "confirm",
            }
        )
        decided, decided_headers, _ = _request(
            base,
            "POST",
            "/review/review_exact_host/decision",
            body=form,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": base,
            },
        )
        assert decided == 303
        assert decided_headers["Location"] == launch.review_path
    finally:
        ui.stop()


def test_tampered_subject_fails_closed_and_non_loopback_binding_is_rejected(
    tmp_path: Path,
) -> None:
    fixture = make_approval_fixture(tmp_path)
    launch = create_request(fixture)
    fixture.artifacts.cas.path_for(fixture.structured_ref.sha256).write_bytes(b"tampered")
    ui = ApprovalUI(fixture.approvals)
    base = ui.start()
    try:
        status, _, _ = _request(base, "GET", launch.review_path)
        assert status == 409
    finally:
        ui.stop()
    with pytest.raises(ValueError, match="loopback"):
        ApprovalUI(fixture.approvals, host="0.0.0.0")


def test_problem_spec_is_rendered_as_a_semantic_review_workbench(
    tmp_path: Path,
) -> None:
    fixture = make_approval_fixture(tmp_path)
    problem_spec = {
        "schema_version": 1,
        "input_type": "paper",
        "problem_id": "problem_ui_review",
        "title": "完整结构暗电流模型审批",
        "objective": "验证完整五层异质结结构下的暗电流模型。",
        "contradiction": "历史三层结构无法支持完整器件结论。",
        "success_criteria": [
            {
                "criterion_id": "success_curve",
                "description": "暗电流整段曲线通过",
                "observable": "140 K I-V 曲线",
                "condition": "全偏压区满足预定义误差门限",
                "metric_id": None,
            }
        ],
        "failure_criteria": [
            {
                "criterion_id": "failure_branch",
                "description": "求解结果依赖扫压历史",
                "observable": "正反向 sweep",
                "condition": "出现不一致的载流子分支",
                "metric_id": None,
            }
        ],
        "constraints": [
            {
                "constraint_id": "constraint_full_stack",
                "kind": "scientific",
                "statement": "暗电流必须使用完整五层器件结构。",
                "rationale": "避免简化异质结改变电场和载流子输运。",
            }
        ],
        "claim_scope": "仅支持论文器件在 140 K 下的暗电流机制判断。",
        "out_of_scope": ["本轮不判定光响应绝对值"],
        "metrics": [],
        "resource_budget": {
            "max_runs": 2,
            "max_parallel": 1,
            "max_wall_time_seconds": 7200,
            "max_storage_bytes": 2_147_483_648,
            "max_cost": None,
            "cost_currency": None,
        },
        "stop_conditions": [
            {
                "condition_id": "stop_nonconvergence",
                "kind": "blocked",
                "condition": "两次独立求解均无法收敛",
                "required_action": "停止执行并提交诊断证据",
            }
        ],
        "source_refs": [
            {
                "artifact_id": "paper_ingaas_detector",
                "sha256": "a" * 64,
                "kind": "source_document",
                "schema_id": "opaque",
            }
        ],
        "assumptions": [
            {
                "statement_id": "assumption_contact",
                "statement": "接触边界采用论文未明确给出的欧姆接触假设。",
                "basis": "作为待证的初始实现，不提升为论文事实。",
                "revocation_condition": "接触模型导致可观测的非物理势垒。",
            }
        ],
        "open_questions": [
            {
                "question_id": "question_lifetime",
                "question": "140 K 的少子寿命是否有独立测量依据？",
                "status": "partially_known",
                "resolution_needed": "论文补充材料或公开材料参数来源",
            }
        ],
        "approval_policy": {
            "policy_id": "policy_problem_spec",
            "requirements": [
                {
                    "requirement_id": "approve_problem",
                    "subject_kind": "problem_spec_draft",
                    "condition": "冻结基础事实后",
                    "action": "人工核验科学内容",
                    "rationale": "批准对象应是可读的科学内容，而不是哈希值。",
                }
            ],
        },
    }
    problem_ref = fixture.artifacts.register(
        canonical_json(problem_spec),
        ArtifactRegistration(
            artifact_id="problem_ui_review",
            kind="problem_spec_draft",
            schema_id="scidiscovery.problem-spec",
            payload_schema_version=1,
            media_type="application/json",
            creator=REQUESTER,
        ),
        idempotency_key="subject:problem-ui-review",
    ).ref
    launch = fixture.approvals.create_request(
        approval_id="review_problem_spec",
        kind="problem_spec_review",
        subject_refs=(problem_ref,),
        question="这些冻结的基础事实、假设和边界是否正确？",
        options=OPTIONS,
        requested_by=REQUESTER,
        idempotency_key="approval:review-problem-spec",
    )
    ui = ApprovalUI(fixture.approvals)
    base = ui.start()
    try:
        status, _, body = _request(base, "GET", launch.review_path)
        text = body.decode()
        assert status == 200
        assert "完整结构暗电流模型审批" in text
        assert "合同内容" in text
        assert "目标与当前矛盾" in text
        assert "成功与失败标准" in text
        assert "完整五层异质结结构" in text
        assert "2 小时" in text
        assert "2 GiB" in text
        assert "明确假设" in text
        assert "少子寿命" in text
        assert "paper_ingaas_detector" in text
        assert "data-review-target='panel-raw'" in text
        assert "data-pointer='/objective'" in text
    finally:
        ui.stop()
