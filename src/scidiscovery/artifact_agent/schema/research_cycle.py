"""Domain-neutral framing, review, and readiness objects for scientific cycles."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import Identifier, SchemaModel, canonical_json
from .scientific_foundation import ScientificFoundation
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

    @model_validator(mode="after")
    def _references_are_unique(self) -> ResearchObservable:
        if len(self.foundation_item_keys) != len(set(self.foundation_item_keys)):
            raise ValueError("observable foundation_item_keys must be unique")
        return self


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
        if len(foundation_keys) != len(set(foundation_keys)):
            raise ValueError("problem foundation_item_keys must be unique")
        if len(observable_keys) != len(set(observable_keys)):
            raise ValueError("observable_key values must be unique")
        known = set(foundation_keys)
        for observable in self.observables:
            if not set(observable.foundation_item_keys).issubset(known):
                raise ValueError("observable references an undeclared foundation item")
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
    """A critic's structured scientific review, not a control-plane decision."""

    review_target: Literal[
        "problem_frame",
        "hypothesis_portfolio",
        "experiment_portfolio",
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
        if len(self.evidence_item_keys) != len(set(self.evidence_item_keys)):
            raise ValueError("scientific review evidence_item_keys must be unique")
        source_keys = tuple(item.source_key for item in self.evidence)
        if len(source_keys) != len(set(source_keys)):
            raise ValueError("scientific review evidence source_key values must be unique")
        known_sources = set(source_keys)
        for finding in self.findings:
            if not set(finding.evidence_keys).issubset(known_sources):
                raise ValueError("scientific review finding references undeclared evidence")
        if self.review_target == "hypothesis_portfolio" and not self.hypothesis_reviews:
            raise ValueError("hypothesis portfolio review requires hypothesis_reviews")
        if self.verdict == "pass" and any(
            "fail"
            in {
                item.physical_plausibility,
                item.falsifiability,
                item.identifiability,
            }
            for item in self.hypothesis_reviews
        ):
            raise ValueError("passing review cannot contain a failed hypothesis dimension")
        return self


ArtifactKind = Literal[
    "scientific_intake",
    "problem_frame",
    "scientific_foundation",
    "hypothesis_portfolio",
    "scientific_review",
    "evidence_audit",
    "candidate_eligibility",
    "experiment_portfolio",
    "tcad_project",
    "deck_review",
    "packaged_project",
    "execution_result",
    "runtime_attestation",
    "control_equivalence_report",
    "metric_report",
    "validation_report",
    "layered_diagnosis",
    "knowledge_state",
]
ClaimEvaluability = Literal["not_evaluable", "evaluable", "accepted"]
ExecutionReadiness = Literal["not_ready", "ready", "authorized", "completed"]


class ScientificReadiness(SchemaModel):
    """Scientific inventory and unresolved needs; deliberately not a workflow graph."""

    current_contradiction: Annotated[str, Field(min_length=1, max_length=8192)]
    available_artifacts: Annotated[
        tuple[ArtifactKind, ...], Field(max_length=32)
    ] = ()
    unresolved_needs: Annotated[tuple[str, ...], Field(max_length=128)] = ()
    blockers: Annotated[tuple[str, ...], Field(max_length=128)] = ()
    claim_evaluability: ClaimEvaluability
    execution_readiness: ExecutionReadiness
    suggested_capabilities: Annotated[
        tuple[Identifier, ...], Field(max_length=32)
    ] = ()
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    def _inventory_is_unique_and_coherent(self) -> ScientificReadiness:
        if len(self.available_artifacts) != len(set(self.available_artifacts)):
            raise ValueError("available_artifacts must be unique")
        if len(self.suggested_capabilities) != len(set(self.suggested_capabilities)):
            raise ValueError("suggested_capabilities must be unique")
        if self.claim_evaluability == "accepted" and "validation_report" not in set(
            self.available_artifacts
        ):
            raise ValueError("accepted claim requires a validation_report")
        if self.execution_readiness == "completed" and "execution_result" not in set(
            self.available_artifacts
        ):
            raise ValueError("completed execution requires an execution_result")
        return self


class ScientificObjectStatus(SchemaModel):
    """One semantic scientific object without storage identity."""

    semantic_name: Annotated[str, Field(min_length=1, max_length=256)]
    kind: ArtifactKind
    schema_id: Annotated[str, Field(min_length=1, max_length=512)]
    revision: int = Field(ge=1)
    qualification: Literal["qualified", "human_review_required"] = "qualified"


class ScientificClosureStatus(SchemaModel):
    """Read-only projection used by a scheduler to choose the next action."""

    readiness: ScientificReadiness
    objects: Annotated[tuple[ScientificObjectStatus, ...], Field(max_length=256)] = ()
    available_actions: Annotated[tuple[Identifier, ...], Field(max_length=64)] = ()

    @model_validator(mode="after")
    def _actions_match_readiness(self) -> ScientificClosureStatus:
        if len(self.available_actions) != len(set(self.available_actions)):
            raise ValueError("available_actions must be unique")
        if self.available_actions != self.readiness.suggested_capabilities:
            raise ValueError("available_actions must match suggested_capabilities")
        return self


class ScientificIntake(SchemaModel):
    """One extractor-owned, reviewable problem frame and evidence foundation."""

    problem_frame: ProblemFrame
    scientific_foundation: ScientificFoundation

    @model_validator(mode="after")
    def _frame_uses_the_supplied_foundation(self) -> ScientificIntake:
        validate_problem_frame_against_foundation(
            self.problem_frame, self.scientific_foundation
        )
        if self.problem_frame.objective != self.scientific_foundation.objective:
            raise ValueError("problem frame and scientific foundation objectives differ")
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
    "ClaimEvaluability",
    "ExecutionReadiness",
    "HypothesisReview",
    "ProblemFrame",
    "ResearchObservable",
    "ReviewStatus",
    "ReviewVerdict",
    "ScientificReadiness",
    "ScientificObjectStatus",
    "ScientificClosureStatus",
    "ScientificReview",
    "ScientificIntake",
    "validate_problem_frame",
    "validate_problem_frame_against_foundation",
    "validate_scientific_review",
    "validate_scientific_intake",
]
