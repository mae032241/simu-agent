"""Deterministic join between hypothesis criticism and evidence audit."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import Identifier, SchemaModel, Sha256


class CandidateAssessment(SchemaModel):
    hypothesis_key: Identifier
    status: Literal["eligible", "revise", "blocked"]
    critic_dimensions: tuple[Literal["pass", "fail", "unknown", "not_applicable"], ...]
    unresolved_requirements: Annotated[tuple[str, ...], Field(max_length=64)] = ()
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]


class CandidateEligibility(SchemaModel):
    """Machine-derived eligibility; it contains no new scientific judgment."""

    objective: Annotated[str, Field(min_length=1, max_length=8192)]
    hypothesis_portfolio_sha256: Sha256 | None = None
    status: Literal["ready", "revise", "blocked"]
    critic_verdict: Literal[
        "pass", "revise", "reject", "blocked", "inconclusive"
    ]
    evidence_verdict: Literal[
        "pass", "revise", "reject", "blocked", "inconclusive", "fail"
    ]
    assessments: Annotated[
        tuple[CandidateAssessment, ...], Field(min_length=1, max_length=12)
    ]
    eligible_hypothesis_keys: Annotated[tuple[Identifier, ...], Field(max_length=12)] = ()
    unresolved_requirements: Annotated[tuple[str, ...], Field(max_length=128)] = ()
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    def _eligibility_is_coherent(self) -> CandidateEligibility:
        assessment_keys = tuple(item.hypothesis_key for item in self.assessments)
        if len(assessment_keys) != len(set(assessment_keys)):
            raise ValueError("candidate assessments must be unique")
        eligible = tuple(
            item.hypothesis_key for item in self.assessments if item.status == "eligible"
        )
        if self.eligible_hypothesis_keys != eligible:
            raise ValueError("eligible_hypothesis_keys must match candidate assessments")
        if self.status == "ready" and not eligible:
            raise ValueError("ready eligibility requires at least one eligible hypothesis")
        if self.status != "ready" and eligible:
            raise ValueError("non-ready eligibility cannot expose eligible hypotheses")
        return self


__all__ = ["CandidateAssessment", "CandidateEligibility"]
