"""Compact payload forms for hypothesis, critic, and evidence roles."""

from __future__ import annotations

import hashlib
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import Identifier, canonical_json
from .role_result import FormModel


ReviewStatus = Literal["pass", "fail", "unknown", "not_applicable"]
CriticDisposition = Literal[
    "ready_for_experiment",
    "revise_hypothesis",
    "revise_evidence",
    "design_model_counterfactual",
    "inconclusive",
    "reject",
]

class SourceReference(FormModel):
    source_key: Identifier
    source_type: Literal[
        "frozen_input",
        "web_snapshot",
        "user_statement",
        "runtime_output",
        "inference",
    ]
    locator: Annotated[str, Field(min_length=1, max_length=2048)]


class VersionedPayload(FormModel):
    schema_version: Literal[1] = 1

    def canonical_json(self) -> bytes:
        return canonical_json(self.model_dump(mode="json"))


class ParameterForm(FormModel):
    name: Annotated[str, Field(min_length=1, max_length=256)]
    role: Literal["fixed", "calibratable", "missing"]
    unit: Annotated[str, Field(min_length=1, max_length=64)]
    range_description: Annotated[str, Field(min_length=1, max_length=512)] | None = None
    basis: Annotated[str, Field(min_length=1, max_length=1024)]

    @model_validator(mode="after")
    def _calibratable_parameter_is_bounded(self) -> ParameterForm:
        if self.role == "calibratable" and self.range_description is None:
            raise ValueError("calibratable parameter requires range_description")
        return self


class PredictionForm(FormModel):
    prediction_key: Identifier
    observable: Annotated[str, Field(min_length=1, max_length=1024)]
    expected_outcome: Annotated[str, Field(min_length=1, max_length=1024)]


class FalsifierForm(FormModel):
    falsifier_key: Identifier
    observable: Annotated[str, Field(min_length=1, max_length=1024)]
    rejection_condition: Annotated[str, Field(min_length=1, max_length=1024)]


class HypothesisForm(FormModel):
    hypothesis_key: Identifier
    statement: Annotated[str, Field(min_length=1, max_length=2048)]
    mechanism: Annotated[str, Field(min_length=1, max_length=2048)]
    scope: Annotated[str, Field(min_length=1, max_length=1024)]
    parameters: Annotated[tuple[ParameterForm, ...], Field(max_length=12)] = ()
    predictions: Annotated[
        tuple[PredictionForm, ...], Field(min_length=1, max_length=4)
    ]
    falsifiers: Annotated[
        tuple[FalsifierForm, ...], Field(min_length=1, max_length=4)
    ]
    competing_hypothesis_keys: Annotated[tuple[Identifier, ...], Field(max_length=6)] = ()
    evidence_keys: Annotated[tuple[Identifier, ...], Field(max_length=12)] = ()

    @model_validator(mode="after")
    def _local_keys_are_unique(self) -> HypothesisForm:
        for values, label in (
            (tuple(item.name for item in self.parameters), "parameter names"),
            (tuple(item.prediction_key for item in self.predictions), "prediction keys"),
            (tuple(item.falsifier_key for item in self.falsifiers), "falsifier keys"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{label} must be unique")
        return self


class HypothesisProposal(VersionedPayload):
    schema_version: Literal[2] = 2
    research_objective_key: Identifier
    stage_objective: Annotated[str, Field(min_length=1, max_length=2048)]
    contradiction: Annotated[str, Field(min_length=1, max_length=2048)]
    evidence: Annotated[tuple[SourceReference, ...], Field(max_length=32)] = ()
    hypotheses: Annotated[tuple[HypothesisForm, ...], Field(max_length=6)] = ()

    @model_validator(mode="after")
    def _portfolio_is_coherent(self) -> HypothesisProposal:
        keys = tuple(item.hypothesis_key for item in self.hypotheses)
        if len(keys) != len(set(keys)):
            raise ValueError("hypothesis_key values must be unique")
        known_hypotheses = set(keys)
        for hypothesis in self.hypotheses:
            competitors = set(hypothesis.competing_hypothesis_keys)
            if hypothesis.hypothesis_key in competitors:
                raise ValueError("hypothesis cannot compete with itself")
            if not competitors.issubset(known_hypotheses):
                raise ValueError("hypothesis references an undeclared competitor")
        return self


class HypothesisReviewForm(FormModel):
    hypothesis_key: Identifier
    physical_plausibility: ReviewStatus
    falsifiability: ReviewStatus
    finite_discriminability: ReviewStatus
    issues: Annotated[tuple[str, ...], Field(max_length=12)] = ()
    smallest_resolving_action: Annotated[
        str, Field(min_length=1, max_length=1024)
    ] | None = None

class CriticReview(VersionedPayload):
    """The critic judges disposition; dimension statuses do not mechanically derive it."""

    schema_version: Literal[2] = 2
    disposition: CriticDisposition
    reviews: Annotated[tuple[HypothesisReviewForm, ...], Field(max_length=6)] = ()
    global_issues: Annotated[tuple[str, ...], Field(max_length=12)] = ()
    evidence: Annotated[tuple[SourceReference, ...], Field(max_length=32)] = ()

    @model_validator(mode="after")
    def _keys_are_unique(self) -> CriticReview:
        review_keys = tuple(item.hypothesis_key for item in self.reviews)
        if len(review_keys) != len(set(review_keys)):
            raise ValueError("a critic may review each hypothesis once")
        return self


def critic_progress_fingerprint(raw: bytes) -> str:
    """Fingerprint unresolved scientific dimensions, never reviewer prose."""

    review = CriticReview.model_validate_json(raw, strict=True)
    unresolved = tuple(
        (
            item.hypothesis_key,
            dimension,
            status,
        )
        for item in sorted(review.reviews, key=lambda value: value.hypothesis_key)
        for dimension, status in (
            ("physical_plausibility", item.physical_plausibility),
            ("falsifiability", item.falsifiability),
            ("finite_discriminability", item.finite_discriminability),
        )
        if status != "pass"
    )
    return hashlib.sha256(
        canonical_json(
            {
                "disposition": review.disposition,
                "unresolved": unresolved,
            }
        )
    ).hexdigest()


class EvidenceCheckForm(FormModel):
    check_key: Identifier
    subject: Annotated[str, Field(min_length=1, max_length=1024)]
    status: ReviewStatus
    basis: Annotated[str, Field(min_length=1, max_length=1024)]
    evidence_keys: Annotated[tuple[Identifier, ...], Field(max_length=12)] = ()
    hypothesis_keys: Annotated[tuple[Identifier, ...], Field(max_length=6)] = ()


class EvidenceAudit(VersionedPayload):
    checks: Annotated[tuple[EvidenceCheckForm, ...], Field(max_length=24)] = ()
    evidence: Annotated[tuple[SourceReference, ...], Field(max_length=32)] = ()

    @model_validator(mode="after")
    def _audit_is_coherent(self) -> EvidenceAudit:
        check_keys = tuple(item.check_key for item in self.checks)
        if len(check_keys) != len(set(check_keys)):
            raise ValueError("evidence check keys must be unique")
        return self


def validate_hypothesis_proposal(value: dict[str, object]) -> dict[str, object]:
    return HypothesisProposal.model_validate_json(
        canonical_json(value), strict=True
    ).model_dump(mode="json")


def validate_critic_review(value: dict[str, object]) -> dict[str, object]:
    return CriticReview.model_validate_json(
        canonical_json(value), strict=True
    ).model_dump(mode="json")


def validate_evidence_audit(value: dict[str, object]) -> dict[str, object]:
    return EvidenceAudit.model_validate_json(
        canonical_json(value), strict=True
    ).model_dump(mode="json")


__all__ = [
    "CriticReview",
    "CriticDisposition",
    "EvidenceAudit",
    "EvidenceCheckForm",
    "FalsifierForm",
    "HypothesisForm",
    "HypothesisProposal",
    "HypothesisReviewForm",
    "ParameterForm",
    "PredictionForm",
    "ReviewStatus",
    "SourceReference",
    "critic_progress_fingerprint",
    "validate_critic_review",
    "validate_evidence_audit",
    "validate_hypothesis_proposal",
]
