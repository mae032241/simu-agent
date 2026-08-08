from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scidiscovery.artifact_agent import HumanDecision, LocalIdentityRef, ReviewManifest
from scidiscovery.artifact_agent.service import (
    ApprovalAccessDenied,
    ApprovalExpired,
    ApprovalNonceConflict,
    SchedulerBindingService,
    SecureIntakeService,
)
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade

from ._approval_fixtures import OPTIONS, REQUESTER, create_request, make_approval_fixture


IDENTITY = LocalIdentityRef(identity_id="user_da", display_name="Local User")


def test_request_manifest_review_and_exact_decision_binding(tmp_path: Path) -> None:
    fixture = make_approval_fixture(tmp_path)
    launch = create_request(fixture)
    status = fixture.approvals.status("review_one")
    assert status.status == "pending"
    assert status.decision_ref is None
    assert launch.access_token in status.review_path

    review = fixture.approvals.review(
        "review_one", access_token=launch.access_token
    )
    manifest = ReviewManifest.model_validate_json(
        fixture.artifacts.read(review.request.review_manifest_ref), strict=True
    )
    pointers = manifest.subjects[0].json_pointers
    assert {"/empty_list", "/empty_object", "/nested/enabled", "/nested/value", "/title"} <= set(pointers)
    assert review.request.subject_refs == (
        fixture.structured_ref,
        fixture.binary_ref,
    )

    decision_ref = fixture.approvals.record_ui_decision(
        approval_id="review_one",
        access_token=launch.access_token,
        csrf_token=review.csrf_token,
        decision_nonce=review.decision_nonce,
        selected_option="approve",
        rationale="",
        decided_by=IDENTITY,
        ui_session_id="ui_test",
    )
    decision = HumanDecision.model_validate_json(
        fixture.artifacts.read(decision_ref), strict=True
    )
    assert decision.approval_request_ref == launch.approval_request_ref
    assert decision.subject_refs == review.request.subject_refs
    assert decision.subject_set_sha256 == review.request.subject_set_sha256
    assert decision.selected_option == "approve"
    assert fixture.approvals.status("review_one").decision_ref == decision_ref

    replay = fixture.approvals.record_ui_decision(
        approval_id="review_one",
        access_token=launch.access_token,
        csrf_token=review.csrf_token,
        decision_nonce=review.decision_nonce,
        selected_option="approve",
        rationale="",
        decided_by=IDENTITY,
        ui_session_id="ui_test",
    )
    assert replay == decision_ref
    with pytest.raises(ApprovalNonceConflict):
        fixture.approvals.record_ui_decision(
            approval_id="review_one",
            access_token=launch.access_token,
            csrf_token=review.csrf_token,
            decision_nonce=review.decision_nonce,
            selected_option="revise",
            rationale="different",
            decided_by=IDENTITY,
            ui_session_id="ui_test",
        )


def test_exact_subject_approval_qualification_does_not_leak_to_other_versions(
    tmp_path: Path,
) -> None:
    fixture = make_approval_fixture(tmp_path)
    launch = fixture.approvals.create_request(
        approval_id="foundation_review",
        kind="scientific_foundation",
        subject_refs=(fixture.structured_ref,),
        question="Is this exact scientific foundation acceptable?",
        options=OPTIONS,
        requested_by=REQUESTER,
        idempotency_key="approval:foundation_review",
    )
    review = fixture.approvals.review(
        "foundation_review", access_token=launch.access_token
    )
    fixture.approvals.record_ui_decision(
        approval_id="foundation_review",
        access_token=launch.access_token,
        csrf_token=review.csrf_token,
        decision_nonce=review.decision_nonce,
        selected_option="approve",
        rationale="",
        decided_by=IDENTITY,
        ui_session_id="ui_foundation",
    )

    assert fixture.approvals.is_subject_approved(
        fixture.structured_ref, kind="scientific_foundation"
    )
    assert not fixture.approvals.is_subject_approved(
        fixture.binary_ref, kind="scientific_foundation"
    )
    assert not fixture.approvals.is_subject_approved(
        fixture.structured_ref, kind="execution_authorization"
    )


def test_wrong_cross_request_and_expired_access_fail_closed(tmp_path: Path) -> None:
    fixture = make_approval_fixture(tmp_path)
    first = create_request(fixture, approval_id="first")
    second = create_request(fixture, approval_id="second")
    first_review = fixture.approvals.review("first", access_token=first.access_token)
    second_review = fixture.approvals.review("second", access_token=second.access_token)
    with pytest.raises(ApprovalAccessDenied):
        fixture.approvals.record_ui_decision(
            approval_id="second",
            access_token=second.access_token,
            csrf_token=second_review.csrf_token,
            decision_nonce=first_review.decision_nonce,
            selected_option="approve",
            rationale="",
            decided_by=IDENTITY,
            ui_session_id="ui_test",
        )
    with pytest.raises(ApprovalAccessDenied):
        fixture.approvals.review("first", access_token="wrong")

    access_now = datetime(2040, 1, 1, tzinfo=timezone.utc)
    access = create_request(
        fixture,
        approval_id="access_expiry",
        now=access_now,
    )
    with pytest.raises(ApprovalAccessDenied, match="expired"):
        fixture.approvals.review(
            "access_expiry",
            access_token=access.access_token,
            now=access_now + timedelta(hours=1),
        )

    recovered = fixture.approvals.list_requests(
        status="pending",
        now=access_now + timedelta(hours=1),
    )
    recovered_access = next(
        item for item in recovered if item.approval_id == "access_expiry"
    )
    assert recovered_access.review_path is not None
    assert recovered_access.review_path != access.review_path
    recovered_token = recovered_access.review_path.rsplit("token=", 1)[1]
    assert fixture.approvals.review(
        "access_expiry",
        access_token=recovered_token,
        now=access_now + timedelta(hours=1),
    ).status == "pending"

    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    expires = (now + timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
    expiring = create_request(
        fixture,
        approval_id="expiring",
        expires_at=expires,
        now=now,
    )
    assert fixture.approvals.status(
        "expiring", now=now + timedelta(minutes=10)
    ).status == "expired"
    review_path_before = second.review_path
    rotated = fixture.approvals.rotate_access("second")
    assert rotated.review_path != review_path_before
    with pytest.raises(ApprovalAccessDenied):
        fixture.approvals.review("second", access_token=second.access_token)


def test_root_can_create_and_read_status_but_cannot_write_decision(tmp_path: Path) -> None:
    fixture = make_approval_fixture(tmp_path)
    intake = SecureIntakeService(
        project_root=tmp_path,
        artifact_service=fixture.artifacts,
        creator=REQUESTER,
    )
    router = RootMCPRouter(
        RootToolFacade(
            fixture.artifacts,
            intake,
            tasks=object(),
            approvals=fixture.approvals,
            executions=object(),
            bindings=SchedulerBindingService(tmp_path / "scheduler.sqlite3"),
            instance="test",
            approval_base_url="http://127.0.0.1:43123",
        )
    )
    router.facade.bindings.bind(
        instance="test",
        namespace="artifact",
        name="problem_spec",
        object_id=fixture.structured_ref.artifact_id,
    )
    created = router.call_tool(
        "approval_request_create",
        {
            "kind": "problem_spec_review",
            "name": "problem_review",
            "subject_names": ["problem_spec"],
                "question": "Is this exact subject correct?",
                "options": [
                    {
                        **option.model_dump(
                            mode="json", exclude={"schema_version", "option_id"}
                        ),
                        "option_key": option.option_id,
                    }
                    for option in OPTIONS
                ],
        },
    )
    assert created["review_url"] == "http://127.0.0.1:43123/"
    status = router.call_tool("approval_status", {"name": "problem_review"})
    assert status["status"] == "pending"
    assert status["selected_option"] is None
    assert "approval_record_decision" not in {tool.name for tool in router._tools.values()}

    listed = router.call_tool("approval_list", {"status": "pending", "limit": 1})
    assert listed["approvals"] == [created]
    assert listed["approvals"][0]["review_url"] == "http://127.0.0.1:43123/"


def test_decision_artifact_is_reused_after_state_commit_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = make_approval_fixture(tmp_path)
    launch = create_request(fixture)
    review = fixture.approvals.review("review_one", access_token=launch.access_token)
    original_insert_event = fixture.approvals._insert_event
    failed = False

    def fail_once(*args, **kwargs):
        nonlocal failed
        if not failed and args[2] == "decided":
            failed = True
            raise OSError("simulated approval state commit failure")
        return original_insert_event(*args, **kwargs)

    monkeypatch.setattr(fixture.approvals, "_insert_event", fail_once)
    with pytest.raises(OSError, match="simulated"):
        fixture.approvals.record_ui_decision(
            approval_id="review_one",
            access_token=launch.access_token,
            csrf_token=review.csrf_token,
            decision_nonce=review.decision_nonce,
            selected_option="approve",
            rationale="",
            decided_by=IDENTITY,
            ui_session_id="ui_failure",
        )
    assert fixture.approvals.status("review_one").status == "pending"
    assert len(fixture.artifacts.list_artifacts(kind="human_decision")) == 1
    decision_ref = fixture.approvals.record_ui_decision(
        approval_id="review_one",
        access_token=launch.access_token,
        csrf_token=review.csrf_token,
        decision_nonce=review.decision_nonce,
        selected_option="approve",
        rationale="",
        decided_by=IDENTITY,
        ui_session_id="ui_failure",
    )
    assert fixture.approvals.status("review_one").decision_ref == decision_ref
    assert len(fixture.artifacts.list_artifacts(kind="human_decision")) == 1
