"""Domain-neutral framing, review, and readiness objects for scientific cycles."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import Identifier, SchemaModel, canonical_json
from .scientific_foundation import ScientificFoundation, _raise_issues
from .scientific_output import EvidenceCitation, ScientificFinding


class ResearchObservable(SchemaModel):
    observable_key: Identifier
    description: Annotated[str, Field(min_length=1, max_length=4096)]
    role: Literal[
        "target",
        "mechanism_signature",
        "control_invariant",
        "numerical_diagnostic",
    ]
    foundation_item_keys: Annotated[
        tuple[Identifier, ...], Field(min_length=1, max_length=64)
    ]
    acceptance_relevance: Annotated[str, Field(min_length=1, max_length=4096)]


class ClaimBoundary(SchemaModel):
    allowed_claim: Annotated[str, Field(min_length=1, max_length=8192)]
    required_conditions: Annotated[
        tuple[str, ...], Field(min_length=1, max_length=128)
    ]
    excluded_claims: Annotated[tuple[str, ...], Field(max_length=128)] = ()


class ProblemFrame(SchemaModel):
    """The current scientific problem, independent of any workflow topology."""

    title: Annotated[str, Field(min_length=1, max_length=2048)]
    scientific_question: Annotated[str, Field(min_length=1, max_length=8192)]
    objective: Annotated[str, Field(min_length=1, max_length=8192)]
    current_contradiction: Annotated[str, Field(min_length=1, max_length=8192)]
    scope: Annotated[str, Field(min_length=1, max_length=4096)]
    foundation_item_keys: Annotated[
        tuple[Identifier, ...], Field(min_length=1, max_length=512)
    ]
    observables: Annotated[
        tuple[ResearchObservable, ...], Field(min_length=1, max_length=128)
    ]
    claim_boundary: ClaimBoundary
    assumptions: Annotated[tuple[str, ...], Field(max_length=128)] = ()
    open_questions: Annotated[tuple[str, ...], Field(max_length=128)] = ()
    stop_conditions: Annotated[
        tuple[str, ...], Field(min_length=1, max_length=64)
    ]

    @model_validator(mode="after")
    def _frame_is_closed(self) -> ProblemFrame:
        foundation_keys = tuple(self.foundation_item_keys)
        observable_keys = tuple(item.observable_key for item in self.observables)
        issues = []
        if len(observable_keys) != len(set(observable_keys)):
            issues.append((("observables",), "observable_key values must be unique"))
        known = set(foundation_keys)
        for index, observable in enumerate(self.observables):
            if not set(observable.foundation_item_keys).issubset(known):
                issues.append((("observables", index, "foundation_item_keys"), "observable references an undeclared foundation item"))
        _raise_issues(self, issues)
        return self


ReviewVerdict = Literal["pass", "revise", "reject", "blocked", "inconclusive"]
ReviewStatus = Literal["pass", "fail", "unknown", "not_applicable"]


class HypothesisReview(SchemaModel):
    hypothesis_key: Identifier
    physical_plausibility: ReviewStatus
    falsifiability: ReviewStatus
    identifiability: ReviewStatus
    confounders: Annotated[tuple[str, ...], Field(max_length=64)] = ()
    missing_inputs: Annotated[tuple[str, ...], Field(max_length=64)] = ()
    smallest_resolving_action: Annotated[
        str, Field(min_length=1, max_length=4096)
    ]
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]


class ScientificReview(SchemaModel):
    """A reviewer's scientific verdict; individual dimension statuses do not derive it."""

    review_target: Literal[
        "problem_frame",
        "hypothesis_portfolio",
        "experiment_portfolio",
        "experiment_scientific_skeleton",
        "domain_contract",
        "observation",
        "realization",
        "diagnosis",
    ]
    verdict: ReviewVerdict
    summary: Annotated[str, Field(min_length=1, max_length=4096)]
    hypothesis_reviews: Annotated[
        tuple[HypothesisReview, ...], Field(max_length=32)
    ] = ()
    global_confounders: Annotated[tuple[str, ...], Field(max_length=64)] = ()
    findings: Annotated[tuple[ScientificFinding, ...], Field(max_length=64)] = ()
    evidence: Annotated[tuple[EvidenceCitation, ...], Field(max_length=128)] = ()
    evidence_item_keys: Annotated[
        tuple[Identifier, ...], Field(max_length=256)
    ] = ()
    next_actions: Annotated[tuple[str, ...], Field(max_length=32)] = ()

    @model_validator(mode="after")
    def _review_is_coherent(self) -> ScientificReview:
        keys = tuple(item.hypothesis_key for item in self.hypothesis_reviews)
        if len(keys) != len(set(keys)):
            raise ValueError("a scientific review may review each hypothesis once")
        if self.review_target == "hypothesis_portfolio" and not self.hypothesis_reviews:
            raise ValueError("hypothesis portfolio review requires hypothesis_reviews")
        return self


# Plugin-defined kinds remain stable identifiers rather than a core-owned enum.
ArtifactKind = Identifier


class ScientificIntake(SchemaModel):
    """One extractor-owned, reviewable problem frame and evidence foundation."""

    problem_frame: ProblemFrame
    scientific_foundation: ScientificFoundation

    @model_validator(mode="after")
    def _frame_uses_the_supplied_foundation(self) -> ScientificIntake:
        issues = []
        known = {item.item_key for item in self.scientific_foundation.items}
        if not set(self.problem_frame.foundation_item_keys).issubset(known):
            issues.append((("problem_frame", "foundation_item_keys"), "problem frame references an unknown foundation item"))
        if self.problem_frame.objective != self.scientific_foundation.objective:
            issues.append((("problem_frame", "objective"), "problem frame and scientific foundation objectives differ"))
        _raise_issues(self, issues)
        return self


def validate_problem_frame_against_foundation(
    frame: ProblemFrame, foundation: ScientificFoundation
) -> None:
    known = {item.item_key for item in foundation.items}
    if not set(frame.foundation_item_keys).issubset(known):
        raise ValueError("problem frame references an unknown foundation item")


def validate_problem_frame(value: dict[str, object]) -> dict[str, object]:
    return ProblemFrame.model_validate_json(
        canonical_json(value), strict=True
    ).model_dump(mode="json")


def validate_scientific_review(value: dict[str, object]) -> dict[str, object]:
    return ScientificReview.model_validate_json(
        canonical_json(value), strict=True
    ).model_dump(mode="json")


def validate_scientific_intake(value: dict[str, object]) -> dict[str, object]:
    return ScientificIntake.model_validate_json(
        canonical_json(value), strict=True
    ).model_dump(mode="json")


__all__ = [
    "ArtifactKind",
    "ClaimBoundary",
    "HypothesisReview",
    "ProblemFrame",
    "ResearchObservable",
    "ReviewStatus",
    "ReviewVerdict",
    "ScientificReview",
    "ScientificIntake",
    "validate_problem_frame",
    "validate_problem_frame_against_foundation",
    "validate_scientific_review",
    "validate_scientific_intake",
]
