from __future__ import annotations

import http.client
import base64
import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import pytest

from scidiscovery.artifact_agent.approval_ui import ApprovalUI
from scidiscovery.artifact_agent.interfaces.mcp_root import (
    RootMCPRouter,
    RootToolFacade,
)
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.approval import ApprovalOption
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.service.instance_management import (
    InstanceManagementCapabilityError,
    issue_instance_management_capability,
    verify_instance_management_capability,
)
from scidiscovery.artifact_agent.service.scheduler_bindings import (
    SchedulerInstanceConflict,
)
from tests.operations.test_agent_contract_alignment import experiment_case


def _setup(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    secret = os.urandom(32)
    state = tmp_path / "state"
    runtime = open_runtime(
        project_root=project,
        state_root=state,
        approval_receipt_secret=secret,
    )
    ui = ApprovalUI(
        runtime.approvals,
        bindings=runtime.scheduler_bindings,
        instance_management_secret=secret,
    )
    base = ui.start()
    return runtime, state, secret, ui, base


def _root(runtime, *, session_key: str, secret: bytes, base: str):
    return RootMCPRouter(
        RootToolFacade(
            runtime.artifacts,
            runtime.intake,
            runs=runtime.runs,
            approvals=runtime.approvals,
            executions=runtime.executions,
            bindings=runtime.scheduler_bindings,
            instance=None,
            session_key=session_key,
            approval_base_url=base,
            instance_management_secret=secret,
            operation_catalog=runtime.operation_catalog,
        )
    )


def _request(base: str, method: str, path: str, *, form=None, origin=None):
    parsed = urlparse(base)
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=5)
    body = None if form is None else urlencode(form)
    headers = {}
    if body is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["Origin"] = origin or base
    connection.request(method, path, body=body, headers=headers)
    response = connection.getresponse()
    raw = response.read()
    result = response.status, dict(response.getheaders()), raw
    connection.close()
    return result


def _management_page(root: RootMCPRouter, base: str):
    current = root.call_tool("instance_current", {})
    assert current["state"] == "unbound"
    parsed = urlparse(current["management_url"])
    assert f"{parsed.scheme}://{parsed.netloc}" == base
    status, _, page = _request(base, "GET", parsed.path + "?" + parsed.query)
    assert status == 200
    match = re.search(rb"name='csrf' value='([^']+)'", page)
    assert match is not None
    capability = parse_qs(parsed.query)["capability"][0]
    return capability, match.group(1).decode("utf-8"), page


def _table_names(path: Path) -> set[str]:
    with sqlite3.connect(path) as connection:
        return {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }


def _row_count(path: Path, table: str) -> int:
    with sqlite3.connect(path) as connection:
        return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _approval_rows(path: Path) -> tuple[tuple[object, ...], ...]:
    with sqlite3.connect(path) as connection:
        return tuple(
            connection.execute(
                """
                SELECT approval_id, status, access_token, csrf_token,
                       access_expires_at, expires_at
                FROM approval_requests ORDER BY approval_id
                """
            ).fetchall()
        )


def test_instance_current_is_pure_and_ui_directly_creates_and_binds(
    tmp_path: Path,
) -> None:
    runtime, state, secret, ui, base = _setup(tmp_path)
    root = _root(runtime, session_key="sch_" + "1" * 32, secret=secret, base=base)
    scheduler_db = state / "database" / "scheduler-bindings.sqlite3"
    approval_db = state / "database" / "approvals.sqlite3"
    artifact_db = state / "database" / "artifact_agent.sqlite3"
    before_scheduler = scheduler_db.read_bytes()
    before_approvals = _row_count(approval_db, "approval_requests")
    before_artifacts = _row_count(artifact_db, "artifact_envelopes")
    try:
        capability, csrf, page = _management_page(root, base)
        assert "创建新实例".encode("utf-8") in page
        assert scheduler_db.read_bytes() == before_scheduler

        status, headers, _ = _request(
            base,
            "POST",
            "/instances/create",
            form={
                "capability": capability,
                "csrf": csrf,
                "name": "m6a.direct",
                "title": "M6-A direct instance",
                "objective": "Create and bind without a scientific approval.",
            },
        )
        assert status == 303
        assert headers["Location"].startswith("/instance/ins_")
        assert root.call_tool("instance_current", {})["name"] == "m6a.direct"
        assert _row_count(approval_db, "approval_requests") == before_approvals
        assert _row_count(artifact_db, "artifact_envelopes") == before_artifacts
        assert not {
            "scheduler_instance_proposals",
            "scheduler_session_binding_requests",
            "scheduler_session_binding_candidates",
        } & _table_names(scheduler_db)
    finally:
        ui.stop()


def test_direct_ui_selection_atomically_transfers_the_single_session_owner(
    tmp_path: Path,
) -> None:
    runtime, _, secret, ui, base = _setup(tmp_path)
    first = _root(runtime, session_key="sch_" + "2" * 32, secret=secret, base=base)
    second = _root(runtime, session_key="sch_" + "3" * 32, secret=secret, base=base)
    try:
        capability, csrf, _ = _management_page(first, base)
        status, _, _ = _request(
            base,
            "POST",
            "/instances/create",
            form={
                "capability": capability,
                "csrf": csrf,
                "name": "m6a.transfer",
                "title": "M6-A transfer",
                "objective": "Transfer one exact session owner.",
            },
        )
        assert status == 303

        capability, csrf, page = _management_page(second, base)
        assert b"m6a.transfer" in page
        status, _, _ = _request(
            base,
            "POST",
            "/instances/select",
            form={
                "capability": capability,
                "csrf": csrf,
                "name": "m6a.transfer",
            },
        )
        assert status == 303
        assert first.call_tool("instance_current", {})["state"] == "unbound"
        assert second.call_tool("instance_current", {})["name"] == "m6a.transfer"
        restarted = _root(
            runtime,
            session_key="sch_" + "3" * 32,
            secret=secret,
            base=base,
        )
        assert restarted.call_tool("instance_current", {})["name"] == "m6a.transfer"
    finally:
        ui.stop()


def test_instance_management_rejects_bad_capability_origin_and_csrf(
    tmp_path: Path,
) -> None:
    runtime, _, secret, ui, base = _setup(tmp_path)
    root = _root(runtime, session_key="sch_" + "4" * 32, secret=secret, base=base)
    try:
        capability, csrf, _ = _management_page(root, base)
        common = {
            "capability": capability,
            "csrf": csrf,
            "name": "m6a.rejected",
            "title": "Rejected",
            "objective": "Must not be created.",
        }
        assert _request(
            base,
            "POST",
            "/instances/create",
            form={**common, "capability": capability + "x"},
        )[0] == 403
        assert _request(
            base,
            "POST",
            "/instances/create",
            form={**common, "csrf": "wrong"},
        )[0] == 403
        assert _request(
            base,
            "POST",
            "/instances/create",
            form=common,
            origin="http://127.0.0.1:1",
        )[0] == 403
        assert runtime.scheduler_bindings.list_instances() == ()
    finally:
        ui.stop()


def test_instance_management_capability_expires_and_root_has_no_write_tools(
    tmp_path: Path,
) -> None:
    secret = os.urandom(32)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    token = issue_instance_management_capability(
        session_key="sch_" + "5" * 32,
        secret=secret,
        now=now,
        lifetime=timedelta(minutes=1),
    )
    assert verify_instance_management_capability(
        token, secret=secret, now=now
    ).session_key == "sch_" + "5" * 32
    sealed = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    assert ("sch_" + "5" * 32).encode("utf-8") not in sealed
    with pytest.raises(InstanceManagementCapabilityError, match="expired"):
        verify_instance_management_capability(
            token,
            secret=secret,
            now=now + timedelta(minutes=2),
        )

    runtime, _, runtime_secret, ui, base = _setup(tmp_path)
    try:
        root = _root(
            runtime,
            session_key="sch_" + "6" * 32,
            secret=runtime_secret,
            base=base,
        )
        tools = {item["name"] for item in root.list_tools()}
        assert not {"instance_prepare", "instance_status", "instance_select"} & tools
    finally:
        ui.stop()


def test_retired_instance_approval_is_read_only_and_not_a_pending_task(
    tmp_path: Path,
) -> None:
    runtime, state, _, ui, base = _setup(tmp_path)
    subject = runtime.artifacts.register(
        b'{"legacy":"instance proposal"}',
        ArtifactRegistration(
            kind="research_instance_proposal",
            schema_id="scidiscovery.research-instance-proposal.v1",
            payload_schema_version=1,
            media_type="application/json",
            creator=runtime.actor,
        ),
        idempotency_key="m6a:retired-instance-subject",
    ).ref
    launch = runtime.approvals.create_request(
        approval_id="m6a_retired_instance_approval",
        kind="research_instance_registration",
        subject_refs=(subject,),
        question="Create the legacy instance?",
        options=(
            ApprovalOption(
                option_id="create_instance",
                label="Create",
                description="Legacy create option.",
                requires_rationale=False,
            ),
            ApprovalOption(
                option_id="cancel_instance",
                label="Cancel",
                description="Legacy cancel option.",
                requires_rationale=False,
            ),
        ),
        requested_by=runtime.actor,
        idempotency_key="m6a:retired-instance-approval",
    )
    review = runtime.approvals.review(
        launch.approval_id, access_token=launch.access_token
    )
    artifact_db = state / "database" / "artifact_agent.sqlite3"
    before_artifacts = _row_count(artifact_db, "artifact_envelopes")
    try:
        dashboard_status, _, dashboard = _request(base, "GET", "/")
        assert dashboard_status == 200
        assert b"m6a_retired_instance_approval" not in dashboard

        page_status, _, page = _request(base, "GET", launch.review_path)
        assert page_status == 200
        assert "该审批入口已停用".encode("utf-8") in page
        assert b"submit-decision" not in page

        status, _, _ = _request(
            base,
            "POST",
            f"/review/{launch.approval_id}/decision",
            form={
                "token": launch.access_token,
                "csrf": review.csrf_token,
                "nonce": review.decision_nonce,
                "selected_option": "create_instance",
                "rationale": "",
                "confirm": "confirm",
            },
        )
        assert status == 409
        current = runtime.approvals.status(launch.approval_id)
        assert current.status == "pending"
        assert current.decision_ref is None
        assert _row_count(artifact_db, "artifact_envelopes") == before_artifacts
    finally:
        ui.stop()


def test_retired_pending_rows_cannot_hide_a_real_pending_review(
    tmp_path: Path,
) -> None:
    runtime, _, _, ui, _ = _setup(tmp_path)
    subject = runtime.artifacts.register(
        b'{"review":"subject"}',
        ArtifactRegistration(
            kind="review_subject",
            schema_id="scidiscovery.test-review-subject.v1",
            payload_schema_version=1,
            media_type="application/json",
            creator=runtime.actor,
        ),
        idempotency_key="m6a:pagination-subject",
    ).ref
    options = (
        ApprovalOption(
            option_id="approve",
            label="Approve",
            description="Approve the exact subject.",
            requires_rationale=False,
        ),
        ApprovalOption(
            option_id="reject",
            label="Reject",
            description="Reject the exact subject.",
            requires_rationale=False,
        ),
    )
    runtime.approvals.create_request(
        approval_id="m6a_real_scientific_review",
        kind="scientific_foundation",
        subject_refs=(subject,),
        question="Review the real scientific subject?",
        options=options,
        requested_by=runtime.actor,
        idempotency_key="m6a:real-scientific-review",
    )
    for index in range(100):
        runtime.approvals.create_request(
            approval_id=f"m6a_retired_{index:03d}",
            kind="research_session_binding",
            subject_refs=(subject,),
            question="Legacy session binding?",
            options=options,
            requested_by=runtime.actor,
            idempotency_key=f"m6a:retired-pagination:{index:03d}",
        )
    try:
        visible = runtime.approvals.list_requests(
            status="pending",
            limit=100,
            excluded_kinds=(
                "instance_creation",
                "research_instance_registration",
                "session_binding",
                "research_session_binding",
            ),
        )
        assert [item.approval_id for item in visible] == [
            "m6a_real_scientific_review"
        ]
    finally:
        ui.stop()


def test_expiry_during_filtered_scan_cannot_skip_an_older_real_review(
    tmp_path: Path,
) -> None:
    runtime, _, _, ui, _ = _setup(tmp_path)
    subject = runtime.artifacts.register(
        b'{"review":"expiry scan"}',
        ArtifactRegistration(
            kind="review_subject",
            schema_id="scidiscovery.test-review-subject.v1",
            payload_schema_version=1,
            media_type="application/json",
            creator=runtime.actor,
        ),
        idempotency_key="m6a:expiry-scan-subject",
    ).ref
    options = (
        ApprovalOption(
            option_id="approve",
            label="Approve",
            description="Approve the exact subject.",
            requires_rationale=False,
        ),
        ApprovalOption(
            option_id="reject",
            label="Reject",
            description="Reject the exact subject.",
            requires_rationale=False,
        ),
    )
    scan_now = datetime.now(timezone.utc)
    oldest = scan_now - timedelta(hours=3)
    runtime.approvals.create_request(
        approval_id="m6a_real_behind_expired",
        kind="scientific_foundation",
        subject_refs=(subject,),
        question="Review the older real subject?",
        options=options,
        requested_by=runtime.actor,
        idempotency_key="m6a:real-behind-expired",
        now=oldest,
    )
    for index in range(99):
        runtime.approvals.create_request(
            approval_id=f"m6a_expiry_retired_{index:03d}",
            kind="research_session_binding",
            subject_refs=(subject,),
            question="Legacy session binding?",
            options=options,
            requested_by=runtime.actor,
            idempotency_key=f"m6a:expiry-retired:{index:03d}",
            now=oldest + timedelta(seconds=index + 1),
        )
    runtime.approvals.create_request(
        approval_id="m6a_expires_on_scan",
        kind="scientific_foundation",
        subject_refs=(subject,),
        question="This request expires before the scan.",
        options=options,
        requested_by=runtime.actor,
        idempotency_key="m6a:expires-on-scan",
        expires_at=(scan_now - timedelta(hours=1))
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z"),
        now=scan_now - timedelta(hours=2),
    )
    try:
        visible = runtime.approvals.list_requests(
            status="pending",
            limit=100,
            excluded_kinds=(
                "instance_creation",
                "research_instance_registration",
                "session_binding",
                "research_session_binding",
            ),
            now=scan_now,
        )
        assert [item.approval_id for item in visible] == [
            "m6a_real_behind_expired"
        ]
        assert runtime.approvals.status(
            "m6a_expires_on_scan", now=scan_now
        ).status == "expired"
    finally:
        ui.stop()


def test_approval_queries_and_page_gets_are_pure_and_refresh_is_explicit(
    tmp_path: Path,
) -> None:
    runtime, state, _, ui, base = _setup(tmp_path)
    instance = runtime.scheduler_bindings.create_instance(
        name="m6a_query_purity",
        title="M6 query purity",
        objective="Keep approval reads free of hidden commands.",
    )
    subject = runtime.artifacts.register(
        b'{"review":"query purity"}',
        ArtifactRegistration(
            kind="review_subject",
            schema_id="scidiscovery.test-review-subject.v1",
            payload_schema_version=1,
            media_type="application/json",
            creator=runtime.actor,
        ),
        idempotency_key="m6a:query-purity-subject",
    ).ref
    options = (
        ApprovalOption(
            option_id="approve",
            label="Approve",
            description="Approve the exact subject.",
            requires_rationale=False,
        ),
        ApprovalOption(
            option_id="reject",
            label="Reject",
            description="Reject the exact subject.",
            requires_rationale=False,
        ),
    )
    current = datetime.now(timezone.utc)
    expired = runtime.approvals.create_request(
        approval_id="m6a_query_business_expired",
        kind="scientific_foundation",
        subject_refs=(subject,),
        question="Expired business decision?",
        options=options,
        requested_by=runtime.actor,
        idempotency_key="m6a:query-business-expired",
        expires_at=(current - timedelta(hours=1))
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z"),
        now=current - timedelta(hours=2),
    )
    stale = runtime.approvals.create_request(
        approval_id="m6a_query_stale_access",
        kind="scientific_foundation",
        subject_refs=(subject,),
        question="Refresh this access link?",
        options=options,
        requested_by=runtime.actor,
        idempotency_key="m6a:query-stale-access",
        now=current - timedelta(hours=2),
    )
    for name, launch in (("business_expired", expired), ("stale_access", stale)):
        runtime.scheduler_bindings.bind(
            instance=instance.instance_id,
            namespace="approval",
            name=name,
            object_id=launch.approval_id,
        )
    root = RootMCPRouter(
        RootToolFacade(
            runtime.artifacts,
            runtime.intake,
            runs=runtime.runs,
            approvals=runtime.approvals,
            executions=runtime.executions,
            bindings=runtime.scheduler_bindings,
            instance=instance.instance_id,
            approval_base_url=base,
            operation_catalog=runtime.operation_catalog,
        )
    )
    approval_db = state / "database" / "approvals.sqlite3"
    artifact_db = state / "database" / "artifact_agent.sqlite3"
    before_rows = _approval_rows(approval_db)
    before_artifacts = _row_count(artifact_db, "artifact_envelopes")
    try:
        assert root.call_tool(
            "approval_status", {"name": "business_expired"}
        )["status"] == "expired"
        pending = root.call_tool(
            "approval_list", {"status": "pending", "limit": 10}
        )["approvals"]
        assert [item["name"] for item in pending] == ["stale_access"]
        dashboard_status, _, dashboard = _request(base, "GET", "/")
        assert dashboard_status == 200
        assert b"refresh-access" in dashboard
        expired_status, _, _ = _request(base, "GET", expired.review_path)
        assert expired_status == 200
        assert _approval_rows(approval_db) == before_rows
        assert _row_count(artifact_db, "artifact_envelopes") == before_artifacts

        refresh_status, headers, _ = _request(
            base,
            "POST",
            f"/review/{stale.approval_id}/refresh-access",
            form={"csrf": ui.session_id},
        )
        assert refresh_status == 303
        assert headers["Location"].startswith(
            f"/review/{stale.approval_id}?token="
        )
        after_refresh = _approval_rows(approval_db)
        assert after_refresh != before_rows
        assert runtime.approvals.status(stale.approval_id).review_path == headers[
            "Location"
        ]
    finally:
        ui.stop()


def test_atomic_create_conflict_does_not_bind_session(tmp_path: Path) -> None:
    runtime, _, _, ui, _ = _setup(tmp_path)
    service = runtime.scheduler_bindings
    try:
        service.create_instance(
            name="m6a.atomic",
            title="Existing",
            objective="Existing objective.",
        )
        with pytest.raises(SchedulerInstanceConflict):
            service.create_instance_and_bind_session(
                session_key="sch_" + "7" * 32,
                name="m6a.atomic",
                title="Different",
                objective="Different objective.",
            )
        assert service.session_instance(session_key="sch_" + "7" * 32) is None
    finally:
        ui.stop()


def test_artifact_catalog_projects_exact_ordered_local_parents_without_writes(tmp_path):
    from tests.operations.test_general_transform_operations import _register, _root as root_fixture

    runtime, instance, root = root_fixture(tmp_path)
    old = _register(runtime, instance, name="objective.rev1", raw=b"old constraints",
                    kind="research_objective", schema="scidiscovery.research-objective.v1")
    runtime.scheduler_bindings.bind(
        instance=instance.instance_id, namespace="artifact", name="objective.alias",
        object_id=old.artifact_id,
    )
    _register(runtime, instance, name="objective.rev2", raw=b"new constraints",
              kind=old.kind, schema=old.schema_id)
    foreign_instance = runtime.scheduler_bindings.create_instance(
        name="foreign", title="Foreign instance", objective="Keep names isolated.",
    )
    foreign = _register(runtime, foreign_instance, name="foreign.only", raw=b"foreign",
                        kind="background", schema="example.background.v1")
    local = _register(runtime, instance, name="analysis", raw=b"local",
                      kind="background", schema="example.background.v1")
    _register(runtime, instance, name="plan", raw=b"child", kind="experiment_portfolio",
              schema="scidiscovery.experiment-portfolio.v1",
              parents=(local.ref, old.ref, foreign.ref))
    databases = tuple((tmp_path / "state" / "database").glob("*.sqlite3"))
    before = {path: path.read_bytes() for path in databases}
    first = root.call_tool("artifact_catalog", {"name": "plan"})
    assert first["parent_artifact_names"] == ["analysis", "objective.rev1", None]
    assert root.call_tool("artifact_catalog", {"name": "objective.rev1"})[
        "parent_artifact_names"
    ] == []
    assert root.call_tool("artifact_catalog", {"name": "plan"}) == first
    assert {path: path.read_bytes() for path in databases} == before
    assert not {"parent_refs", "artifact_id", "sha256", "workspace"} & first.keys()


def test_artifact_catalog_parent_limit_never_truncates(tmp_path):
    from scidiscovery.artifact_agent.interfaces.mcp_root import RootToolError
    from tests.operations.test_general_transform_operations import _register, _root as root_fixture

    runtime, instance, root = root_fixture(tmp_path)
    parents = tuple(runtime.artifacts.register(
        str(index).encode(), ArtifactRegistration(
            kind="background", schema_id="example.background.v1", payload_schema_version=1,
            media_type="text/plain", creator=runtime.actor,
        ), idempotency_key=f"unmapped-parent:{index}",
    ).ref for index in range(4097))
    for count in (4096, 4097):
        name = f"many_parents_{count}"
        _register(runtime, instance, name=name, raw=b"bounded query",
                  kind="background", schema="example.background.v1", parents=parents[:count])
        if count == 4096:
            assert root.call_tool("artifact_catalog", {"name": name})[
                "parent_artifact_names"
            ] == [None] * count
        else:
            with pytest.raises(RootToolError, match="direct parent limit exceeded"):
                root.call_tool("artifact_catalog", {"name": name})


@pytest.mark.parametrize("revise", (False, True))
def test_cold_root_recovers_original_plan_context_and_delivers_exact_files(
    tmp_path, monkeypatch, experiment_case, revise,
):
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from scidiscovery.artifact_agent.schema.common import canonical_json
    from scidiscovery.artifact_agent.schema.research_objective import ResearchObjectiveContract
    from tests.operations.test_agent_contract_alignment import _catalog, _feedback_root
    from tests.operations.test_general_transform_operations import _register

    catalog = _catalog()
    runtime, instance, root, design, intent = _feedback_root(
        tmp_path, monkeypatch, experiment_case, "science.experiment.design.v1",
    )
    runtime.runs.operation_catalog = catalog

    def artifact(name):
        identifier = runtime.scheduler_bindings.resolve(
            instance=instance.instance_id, namespace="artifact", name=name,
        )
        return runtime.artifacts.get_by_id(identifier)

    original = artifact("research_objective")
    original_raw = runtime.artifacts.read(original.ref)
    newer = json.loads(original_raw)
    newer["mandatory_targets"][0]["observable"] = "A later, different observable"
    ResearchObjectiveContract.model_validate_json(canonical_json(newer), strict=True)
    _register(runtime, instance, name="research_objective.rev2", raw=canonical_json(newer),
              kind=original.kind, schema=original.schema_id, parents=original.parent_refs)
    # A same-schema feedback parent must not replace the objective used to materialize.
    design["inputs"].append({"port": "current_progress", "artifact_names": ["research_objective.rev2"]})

    def complete(router, request, payload, verdict="pass", expected_files=None):
        assert router.call_tool("operation_preflight", request)["admissible"] is True
        assert router.call_tool("operation_invoke", request)["result"]["state"] == "queued"
        compiled = catalog.operation(request["operation_id"])
        worker = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id,
                                      operation_digest=compiled.digest)
        opened = worker.call_tool("worker_open_assignment", {})
        if expected_files is not None:
            assignment = json.loads(Path(opened["assignment_path"]).read_text())
            inputs = {item["source_name"]: item for item in assignment["inputs"]}
            for source, raw in expected_files.items():
                path = Path(opened["workspace_path"], inputs[source]["relative_path"])
                assert path.read_bytes() == raw
                assert path.stat().st_mode & 0o777 == 0o400
        Path(opened["output_directory"], "result.json").write_bytes(canonical_json({
            "schema_version": 1, "payload": payload,
            "handoff": {"verdict": verdict, "summary": "One isolated continuation fixture."},
        }))
        assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
        return router.call_tool("run_status", {"name": request["name"]})["output_artifact_name"]

    intent_name = complete(root, design, intent)
    materialize = {"name": "materialized_plan", "operation_id": "science.experiment.materialize.v1",
                   "inputs": [{"port": "experiment_design_intent", "artifact_names": [intent_name]},
                              *[item for item in design["inputs"] if item["port"] != "current_progress"]]}
    assert root.call_tool("operation_preflight", materialize)["admissible"] is True
    plan_name = root.call_tool("operation_invoke", materialize)["result"]["outputs"][0]["artifact_name"]
    if revise:
        review = {"name": "bounded_review", "operation_id": "science.object.review.v1",
                  "inputs": [{"port": "experiment_plan", "artifact_names": [plan_name]}],
                  "instruction": "Review the exact plan."}
        review_name = complete(root, review, {"review_target": "experiment_portfolio", "verdict": "revise",
                                             "summary": "Clarify the retained future condition."}, "revise")
        payload = json.loads(runtime.artifacts.read(artifact(plan_name).ref))
        payload["priority_rationale"] += " Retain the future target until its condition is resolved."
        plan_name = complete(root, {"name": "revised_plan", "operation_id": "science.experiment.revise.v1",
                                    "inputs": [{"port": "prior_draft", "artifact_names": [plan_name]},
                                               {"port": "change_request", "artifact_names": [review_name]}],
                                    "instruction": "Clarify only the reviewed rationale."}, payload)

    # New Root facade starts with the selected plan name, not the remembered objective name.
    cold = RootMCPRouter(RootToolFacade(
        runtime.artifacts, runtime.intake, runs=runtime.runs, approvals=runtime.approvals,
        executions=runtime.executions, bindings=runtime.scheduler_bindings,
        instance=instance.instance_id, operation_catalog=catalog,
    ))
    assert cold.call_tool("instance_current", {})["name"] == instance.name
    cursor = plan_name
    while True:
        names = cold.call_tool("artifact_catalog", {"name": cursor})["parent_artifact_names"]
        parents = [(name, cold.call_tool("artifact_catalog", {"name": name})["schema"]) for name in names]
        previous = [name for name, schema in parents if schema == "scidiscovery.experiment-portfolio.v1"]
        if not previous:
            break
        assert len(previous) == 1
        cursor = previous[0]
    recovered = [name for name, schema in parents if schema == original.schema_id]
    assert recovered == ["research_objective"]
    recovered_intent = next(name for name, schema in parents if schema == "scidiscovery.experiment-design-intent.v1")
    feedback = cold.call_tool("artifact_catalog", {"name": recovered_intent})["parent_artifact_names"]
    assert "research_objective.rev2" in feedback
    complete(cold, {"name": "cold_review", "operation_id": "science.object.review.v1",
                    "inputs": [{"port": "experiment_plan", "artifact_names": [plan_name]},
                               {"port": "research_objective", "artifact_names": recovered},
                               {"port": "current_progress", "artifact_names": [recovered_intent]}],
                    "instruction": "Review only the explicitly recovered originals."},
             {"review_target": "experiment_portfolio", "verdict": "pass", "summary": "Original context is available."},
             expected_files={"research_objective": original_raw,
                             "current_progress": runtime.artifacts.read(artifact(recovered_intent).ref)})
