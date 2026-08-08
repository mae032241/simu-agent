from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scidiscovery.artifact_agent import ActorRef, ApprovalOption, canonical_json
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.service import ApprovalService, ArtifactService


SERVICE_ACTOR = ActorRef(actor_id="approval_ui_service", actor_type="service")
REQUESTER = ActorRef(actor_id="root_orchestrator", actor_type="agent")
RECEIPT_SECRET = b"approval-receipt-secret-is-at-least-32-bytes"


OPTIONS = (
    ApprovalOption(
        option_id="approve",
        label="Approve exact subjects",
        description="Accept only the frozen subjects shown on this page.",
        requires_rationale=False,
    ),
    ApprovalOption(
        option_id="revise",
        label="Request revision",
        description="Reject this exact version and state the required change.",
        requires_rationale=True,
    ),
    ApprovalOption(
        option_id="cancel",
        label="Cancel review",
        description="Close the request without approval or rejection.",
        requires_rationale=False,
        terminal_state="cancelled_by_human",
    ),
)


@dataclass(frozen=True)
class ApprovalFixture:
    artifacts: ArtifactService
    approvals: ApprovalService
    structured_ref: object
    binary_ref: object


def make_approval_fixture(tmp_path: Path) -> ApprovalFixture:
    artifacts = ArtifactService.open(
        cas_root=tmp_path / "state" / "cas",
        database_path=tmp_path / "state" / "artifacts.sqlite3",
    )
    structured = canonical_json(
        {
            "title": "完整审查对象",
            "long": "x" * 12_000,
            "empty_list": [],
            "empty_object": {},
            "nested": {"value": 3.14, "enabled": True},
        }
    )
    structured_ref = artifacts.register(
        structured,
        ArtifactRegistration(
            artifact_id="art_review_json",
            kind="problem_spec_draft",
            schema_id="fixture.review-subject",
            payload_schema_version=1,
            media_type="application/json",
            creator=REQUESTER,
        ),
        idempotency_key="subject:json",
    ).ref
    binary_ref = artifacts.register(
        b"binary subject",
        ArtifactRegistration(
            artifact_id="art_review_binary",
            kind="source_document",
            schema_id="opaque",
            payload_schema_version=1,
            media_type="application/octet-stream",
            creator=REQUESTER,
        ),
        idempotency_key="subject:binary",
    ).ref
    approvals = ApprovalService(
        artifacts=artifacts,
        database_path=tmp_path / "state" / "approvals.sqlite3",
        service_actor=SERVICE_ACTOR,
        receipt_secret=RECEIPT_SECRET,
    )
    return ApprovalFixture(artifacts, approvals, structured_ref, binary_ref)


def create_request(fixture: ApprovalFixture, *, approval_id: str = "review_one", **values):
    return fixture.approvals.create_request(
        approval_id=approval_id,
        kind="problem_spec_review",
        subject_refs=(fixture.structured_ref, fixture.binary_ref),
        question="Are these exact frozen subjects correct?",
        options=OPTIONS,
        requested_by=REQUESTER,
        idempotency_key=f"approval:{approval_id}",
        **values,
    )
