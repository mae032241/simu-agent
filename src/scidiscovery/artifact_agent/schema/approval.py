"""Exact-object local human approval contracts."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .artifact import UtcRfc3339
from .common import Identifier, SchemaModel, Sha256, canonical_sha256
from .refs import ActorRef, ArtifactRef


class ApprovalOption(SchemaModel):
    option_id: Identifier
    label: Annotated[str, Field(min_length=1, max_length=256)]
    description: Annotated[str, Field(min_length=1, max_length=4096)]
    requires_rationale: bool
    terminal_state: Literal["decided", "cancelled_by_human"] = "decided"


class ReviewSubject(SchemaModel):
    artifact_ref: ArtifactRef
    size_bytes: Annotated[int, Field(ge=0)]
    media_type: Annotated[str, Field(min_length=3, max_length=255)]
    envelope_sha256: Sha256
    structured_json: bool
    json_pointers: tuple[str, ...] = ()


class ReviewManifest(SchemaModel):
    approval_id: Identifier
    subjects: Annotated[tuple[ReviewSubject, ...], Field(min_length=1, max_length=256)]
    renderer_contract: Literal["full_tree_raw_json_or_safe_blob_v1"] = (
        "full_tree_raw_json_or_safe_blob_v1"
    )


class ApprovalRequest(SchemaModel):
    approval_id: Identifier
    kind: Identifier
    subject_refs: Annotated[tuple[ArtifactRef, ...], Field(min_length=1, max_length=256)]
    subject_set_sha256: Sha256
    question: Annotated[str, Field(min_length=1, max_length=16384)]
    options: Annotated[tuple[ApprovalOption, ...], Field(min_length=2, max_length=32)]
    review_manifest_ref: ArtifactRef
    requested_by: ActorRef
    expires_at: UtcRfc3339 | None = None
    nonce_hash: Sha256

    @model_validator(mode="after")
    def _validate_request(self) -> ApprovalRequest:
        identities = [_identity(ref) for ref in self.subject_refs]
        if len(identities) != len(set(identities)):
            raise ValueError("approval subjects must be unique exact refs")
        option_ids = [option.option_id for option in self.options]
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("approval options must have unique option_id values")
        if self.subject_set_sha256 != subject_set_sha256(self.subject_refs):
            raise ValueError("subject_set_sha256 does not match subject_refs")
        return self


class LocalIdentityRef(SchemaModel):
    identity_id: Identifier
    display_name: Annotated[str, Field(min_length=1, max_length=256)]
    authentication_method: Literal["local_ui_session"] = "local_ui_session"


class HumanDecision(SchemaModel):
    decision_id: Identifier
    approval_request_ref: ArtifactRef
    subject_refs: Annotated[tuple[ArtifactRef, ...], Field(min_length=1, max_length=256)]
    subject_set_sha256: Sha256
    selected_option: Identifier
    rationale: Annotated[str, Field(max_length=16384)]
    decided_by: LocalIdentityRef
    decided_at: UtcRfc3339
    ui_receipt: Sha256
    previous_decision_ref: ArtifactRef | None = None

    @model_validator(mode="after")
    def _validate_subject_hash(self) -> HumanDecision:
        if self.subject_set_sha256 != subject_set_sha256(self.subject_refs):
            raise ValueError("decision subject_set_sha256 does not match subject_refs")
        return self


ApprovalTerminalState = Literal["pending", "decided", "expired", "cancelled_by_human"]


def approval_options_template(
    kind: Literal["problem_spec", "evidence_bundle", "run_request", "claim_publish"]
) -> tuple[ApprovalOption, ...]:
    primary = {
        "problem_spec": ("approve", "Approve exact problem", "Accept this exact frozen problem contract."),
        "evidence_bundle": (
            "approve",
            "Approve exact scientific foundation",
            "Accept the exact structured facts, parameters, sources, assumptions, and unresolved conflicts shown in this review.",
        ),
        "run_request": ("authorize", "Authorize exact run request", "Authorize only this exact frozen run request; this is not a scientific acceptance."),
        "claim_publish": ("publish", "Approve exact claim", "Approve publication of only this exact frozen claim and evidence set."),
    }.get(kind)
    if primary is None:
        raise ValueError("unknown approval template kind")
    return (
        ApprovalOption(
            option_id=primary[0],
            label=primary[1],
            description=primary[2],
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
            description="Close this review without approval or rejection.",
            requires_rationale=False,
            terminal_state="cancelled_by_human",
        ),
    )


def subject_set_sha256(refs: tuple[ArtifactRef, ...]) -> str:
    return canonical_sha256({"subject_refs": refs})


def _identity(ref: ArtifactRef) -> tuple[str, str, str, str]:
    return ref.artifact_id, ref.sha256, ref.kind, ref.schema_id


__all__ = [
    "ApprovalOption",
    "ApprovalRequest",
    "ApprovalTerminalState",
    "HumanDecision",
    "LocalIdentityRef",
    "ReviewManifest",
    "ReviewSubject",
    "subject_set_sha256",
    "approval_options_template",
]
