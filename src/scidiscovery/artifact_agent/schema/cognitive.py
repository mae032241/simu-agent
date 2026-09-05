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
            (self.competing_hypothesis_keys, "competing hypothesis keys"),
            (self.evidence_keys, "evidence keys"),
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
        source_keys = tuple(item.source_key for item in self.evidence)
        if len(source_keys) != len(set(source_keys)):
            raise ValueError("evidence source_key values must be unique")
        known_evidence = set(source_keys)
        for hypothesis in self.hypotheses:
            competitors = set(hypothesis.competing_hypothesis_keys)
            if hypothesis.hypothesis_key in competitors:
                raise ValueError("hypothesis cannot compete with itself")
            if not competitors.issubset(known_hypotheses):
                raise ValueError("hypothesis references an undeclared competitor")
            if not set(hypothesis.evidence_keys).issubset(known_evidence):
                raise ValueError("hypothesis references undeclared evidence")
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

    @model_validator(mode="after")
    def _failed_dimension_has_resolution(self) -> HypothesisReviewForm:
        dimensions = (
            self.physical_plausibility,
            self.falsifiability,
            self.finite_discriminability,
        )
        if any(value != "pass" for value in dimensions) and self.smallest_resolving_action is None:
            raise ValueError("unresolved review requires smallest_resolving_action")
        return self


class CriticReview(VersionedPayload):
    schema_version: Literal[2] = 2
    disposition: CriticDisposition
    reviews: Annotated[tuple[HypothesisReviewForm, ...], Field(max_length=6)] = ()
    global_issues: Annotated[tuple[str, ...], Field(max_length=12)] = ()
    evidence: Annotated[tuple[SourceReference, ...], Field(max_length=32)] = ()

    @model_validator(mode="after")
    def _keys_are_unique(self) -> CriticReview:
        review_keys = tuple(item.hypothesis_key for item in self.reviews)
        source_keys = tuple(item.source_key for item in self.evidence)
        if len(review_keys) != len(set(review_keys)):
            raise ValueError("a critic may review each hypothesis once")
        if len(source_keys) != len(set(source_keys)):
            raise ValueError("evidence source_key values must be unique")
        statuses = tuple(
            value
            for review in self.reviews
            for value in (
                review.physical_plausibility,
                review.falsifiability,
                review.finite_discriminability,
            )
        )
        if self.disposition in {
            "ready_for_experiment",
            "design_model_counterfactual",
        } and any(value != "pass" for value in statuses):
            raise ValueError(
                "experiment-ready critic disposition requires all review dimensions to pass"
            )
        if self.disposition in {
            "revise_hypothesis",
            "revise_evidence",
            "inconclusive",
        } and (not statuses or all(value == "pass" for value in statuses)):
            raise ValueError(
                "unresolved critic disposition requires a non-passing review dimension"
            )
        if self.disposition == "reject" and "fail" not in statuses:
            raise ValueError("reject disposition requires a failed review dimension")
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

    @model_validator(mode="after")
    def _references_are_unique(self) -> EvidenceCheckForm:
        if len(self.evidence_keys) != len(set(self.evidence_keys)):
            raise ValueError("evidence check evidence keys must be unique")
        if len(self.hypothesis_keys) != len(set(self.hypothesis_keys)):
            raise ValueError("evidence check hypothesis keys must be unique")
        return self


class EvidenceAudit(VersionedPayload):
    checks: Annotated[tuple[EvidenceCheckForm, ...], Field(max_length=24)] = ()
    evidence: Annotated[tuple[SourceReference, ...], Field(max_length=32)] = ()

    @model_validator(mode="after")
    def _audit_is_coherent(self) -> EvidenceAudit:
        check_keys = tuple(item.check_key for item in self.checks)
        source_keys = tuple(item.source_key for item in self.evidence)
        if len(check_keys) != len(set(check_keys)):
            raise ValueError("evidence check keys must be unique")
        if len(source_keys) != len(set(source_keys)):
            raise ValueError("evidence source_key values must be unique")
        known = set(source_keys)
        for check in self.checks:
            if not set(check.evidence_keys).issubset(known):
                raise ValueError("evidence check references undeclared evidence")
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
