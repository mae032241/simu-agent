"""Exact-object local human approval contracts."""

from __future__ import annotations

import json

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .artifact import UtcRfc3339
from .common import (
    Identifier,
    SchemaModel,
    Sha256,
    canonical_json as encode_canonical_json,
    canonical_sha256,
)
from .refs import ActorRef, ArtifactRef


def execution_approval_option_id(decision: str) -> str:
    """Use the same execution decision vocabulary for every caller."""
    return {
        "accept": "authorize_execution",
        "accept_with_exception": "authorize_execution_with_exception",
        "reject": "reject_execution",
        "revise": "revise_execution",
    }[decision]


def execution_decision_authorizes(request, decision) -> bool:
    # Preserve already sealed Worker receipts using the earlier 'approve'
    # spelling. A generic scientific approval is never an execution grant.
    return (request.kind == "execution_authorization"
        and decision.selected_option in {execution_approval_option_id("accept"),
            execution_approval_option_id("accept_with_exception"), "approve"}
        and any(option.option_id == decision.selected_option for option in request.options))


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


class ApprovalDisplayTranslation(SchemaModel):
    subject_index: Annotated[int, Field(ge=0, le=255)]
    json_pointer: Annotated[str, Field(min_length=1, max_length=4096)]
    text: Annotated[str, Field(min_length=1, max_length=8192)]

    @model_validator(mode="after")
    def _validate_pointer(self) -> ApprovalDisplayTranslation:
        if not self.json_pointer.startswith("/"):
            raise ValueError("display translation json_pointer must be absolute")
        return self


class ApprovalPresentation(SchemaModel):
    locale: Literal["zh-CN"]
    translations: Annotated[
        tuple[ApprovalDisplayTranslation, ...], Field(min_length=1, max_length=512)
    ]

    @model_validator(mode="after")
    def _validate_translations(self) -> ApprovalPresentation:
        identities = [
            (item.subject_index, item.json_pointer) for item in self.translations
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("display translations must bind unique subject paths")
        if sum(len(item.text.encode("utf-8")) for item in self.translations) > 512 * 1024:
            raise ValueError("display translations exceed the bounded byte budget")
        return self


class ReviewDocumentItem(SchemaModel):
    kind: Literal[
        "json_value", "json_tree", "status", "subject_metadata", "download"
    ]
    label: Annotated[str, Field(min_length=1, max_length=256)]
    subject_index: Annotated[int, Field(ge=0, le=255)]
    json_pointer: Annotated[str, Field(max_length=4096)] | None = None

    @model_validator(mode="after")
    def _validate_pointer_contract(self) -> ReviewDocumentItem:
        pointer_kinds = {"json_value", "json_tree", "status"}
        if self.kind in pointer_kinds:
            if self.json_pointer is None:
                raise ValueError("review item requires an absolute JSON pointer")
            parse_json_pointer(self.json_pointer)
        elif self.json_pointer is not None:
            raise ValueError("metadata and download items cannot carry JSON pointers")
        return self


def parse_json_pointer(pointer: str) -> tuple[str, ...]:
    """Decode one strict RFC 6901 pointer without reading a document."""

    if pointer == "":
        return ()
    if not pointer.startswith("/"):
        raise ValueError("JSON pointer must be empty or start with a slash")
    decoded: list[str] = []
    for raw_token in pointer[1:].split("/"):
        token: list[str] = []
        index = 0
        while index < len(raw_token):
            character = raw_token[index]
            if character != "~":
                token.append(character)
                index += 1
                continue
            if index + 1 >= len(raw_token) or raw_token[index + 1] not in {"0", "1"}:
                raise ValueError("JSON pointer contains an invalid escape")
            token.append("~" if raw_token[index + 1] == "0" else "/")
            index += 2
        decoded.append("".join(token))
    return tuple(decoded)


class ReviewDocumentSection(SchemaModel):
    title: Annotated[str, Field(min_length=1, max_length=256)]
    description: Annotated[str, Field(max_length=4096)] = ""
    items: Annotated[tuple[ReviewDocumentItem, ...], Field(min_length=1, max_length=512)]


class ReviewDocument(SchemaModel):
    locale: Literal["zh-CN"] = "zh-CN"
    title: Annotated[str, Field(min_length=1, max_length=256)]
    description: Annotated[str, Field(max_length=4096)] = ""
    sections: Annotated[
        tuple[ReviewDocumentSection, ...], Field(min_length=1, max_length=64)
    ]

    @model_validator(mode="after")
    def _validate_document_bounds(self) -> ReviewDocument:
        if sum(len(section.items) for section in self.sections) > 512:
            raise ValueError("review document contains too many items")
        if len(encode_canonical_json(self)) > 512 * 1024:
            raise ValueError("review document exceeds the bounded byte budget")
        return self


class CompiledApprovalIdentity(SchemaModel):
    operation_id: Identifier
    operation_version: Annotated[str, Field(min_length=1, max_length=128)]
    operation_digest: Sha256
    approval_contract_digest: Sha256


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
    presentation: ApprovalPresentation | None = None
    review_document: ReviewDocument | None = None
    compiled_identity: CompiledApprovalIdentity | None = None

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
        if self.presentation is not None and any(
            item.subject_index >= len(self.subject_refs)
            for item in self.presentation.translations
        ):
            raise ValueError("display translation subject_index is out of range")
        if self.review_document is not None and any(
            item.subject_index >= len(self.subject_refs)
            for section in self.review_document.sections
            for item in section.items
        ):
            raise ValueError("review document subject_index is out of range")
        return self

    def canonical_json(self) -> bytes:
        if any(
            value is not None
            for value in (
                self.presentation,
                self.review_document,
                self.compiled_identity,
            )
        ):
            return encode_canonical_json(self)
        return encode_canonical_json(
            {
                field_name: getattr(self, field_name)
                for field_name in type(self).model_fields
                if field_name not in {
                    "presentation", "review_document", "compiled_identity"
                }
            }
        )

    @property
    def content_hash(self) -> str:
        return canonical_sha256(json.loads(self.canonical_json()))


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
    "CompiledApprovalIdentity",
    "ApprovalDisplayTranslation",
    "ApprovalOption",
    "ApprovalPresentation",
    "ApprovalRequest",
    "ApprovalTerminalState",
    "HumanDecision",
    "LocalIdentityRef",
    "ReviewManifest",
    "ReviewDocument",
    "ReviewDocumentItem",
    "ReviewDocumentSection",
    "parse_json_pointer",
    "ReviewSubject",
    "subject_set_sha256",
    "approval_options_template",
]
