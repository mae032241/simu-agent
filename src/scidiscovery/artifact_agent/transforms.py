"""Domain-neutral contract for deterministic Artifact transformations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import Mapping, Protocol

from .schema.common import canonical_json
from .schema.cognitive import CriticReview, EvidenceAudit, HypothesisProposal
from .schema.eligibility import CandidateAssessment, CandidateEligibility
from .schema.hypothesis import HypothesisPortfolio
from .schema.knowledge import (
    KnowledgeStateProjection,
    advance_knowledge_state,
    derive_knowledge_update,
    project_knowledge_state,
)
from .schema.validation import ValidationReport
from .schema.layered_diagnosis import LayeredDiagnosisReport
from .schema.research_cycle import ScientificIntake


_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


@dataclass(frozen=True)
class TransformOutput:
    label: str
    content: bytes
    kind: str
    schema: str
    payload_schema_version: int
    media_type: str

    def __post_init__(self) -> None:
        if not _LABEL.fullmatch(self.label):
            raise ValueError("transform output label is invalid")
        if type(self.content) is not bytes:
            raise TypeError("transform output content must be bytes")
        if not self.kind or not self.schema or not self.media_type:
            raise ValueError("transform output semantics are incomplete")
        if self.payload_schema_version < 1:
            raise ValueError("transform output schema version is invalid")


class ArtifactTransformAdapter(Protocol):
    def supports_transform_profile(self, profile: str) -> bool: ...

    def required_input_parentage(
        self, profile: str
    ) -> tuple[tuple[str, str], ...]: ...

    def transform(
        self, *, profile: str, inputs: Mapping[str, bytes]
    ) -> tuple[TransformOutput, ...]: ...


KNOWLEDGE_UPDATE_PROFILE = "scidiscovery.knowledge-update-from-validation.v1"
SCIENTIFIC_INTAKE_SPLIT_PROFILE = "scidiscovery.scientific-intake-split.v1"
CANDIDATE_ELIGIBILITY_PROFILE = "scidiscovery.candidate-eligibility.v1"
TRANSFORM_ADAPTER_ENTRY_POINT = "scidiscovery.transform_adapters"


class ScientificStateTransformAdapter:
    """Domain-neutral transforms that preserve scientific judgment boundaries."""

    @staticmethod
    def supports_transform_profile(profile: str) -> bool:
        return profile in {
            KNOWLEDGE_UPDATE_PROFILE,
            SCIENTIFIC_INTAKE_SPLIT_PROFILE,
            CANDIDATE_ELIGIBILITY_PROFILE,
        }

    @staticmethod
    def required_input_parentage(profile: str) -> tuple[tuple[str, str], ...]:
        return ()

    @staticmethod
    def transform(
        *, profile: str, inputs: Mapping[str, bytes]
    ) -> tuple[TransformOutput, ...]:
        if profile == SCIENTIFIC_INTAKE_SPLIT_PROFILE:
            if frozenset(inputs) != {"scientific_intake"}:
                raise ValueError("scientific intake split requires scientific_intake")
            intake = ScientificIntake.model_validate_json(
                inputs["scientific_intake"], strict=True
            )
            return (
                TransformOutput(
                    # The root transform contract binds exactly one primary
                    # output to the requested semantic name. Here that object
                    # is the frame; the foundation remains a derived sibling.
                    label="primary",
                    content=intake.problem_frame.canonical_json(),
                    kind="problem_frame",
                    schema="scidiscovery.problem-frame.v1",
                    payload_schema_version=1,
                    media_type="application/json",
                ),
                TransformOutput(
                    label="scientific_foundation",
                    content=intake.scientific_foundation.canonical_json(),
                    kind="scientific_foundation",
                    schema="scidiscovery.scientific-foundation.v1",
                    payload_schema_version=1,
                    media_type="application/json",
                ),
            )
        if profile == CANDIDATE_ELIGIBILITY_PROFILE:
            if frozenset(inputs) != {
                "hypothesis_portfolio",
                "critic_review",
                "evidence_audit",
            }:
                raise ValueError(
                    "candidate eligibility requires hypothesis_portfolio, "
                    "critic_review, and evidence_audit"
                )
            portfolio = HypothesisProposal.model_validate_json(
                inputs["hypothesis_portfolio"], strict=True
            )
            critic = CriticReview.model_validate_json(
                inputs["critic_review"], strict=True
            )
            audit = EvidenceAudit.model_validate_json(
                inputs["evidence_audit"], strict=True
            )
            eligibility = _derive_candidate_eligibility(portfolio, critic, audit)
            return (
                TransformOutput(
                    label="primary",
                    content=eligibility.canonical_json(),
                    kind="candidate_eligibility",
                    schema="scidiscovery.candidate-eligibility.v1",
                    payload_schema_version=1,
                    media_type="application/json",
                ),
            )
        if profile != KNOWLEDGE_UPDATE_PROFILE:
            raise ValueError("unsupported scientific-state transform profile")
        input_names = frozenset(inputs)
        report_names = {"validation_report", "layered_diagnosis"}
        selected_reports = input_names & report_names
        required_base = {"hypothesis_portfolio"}
        if len(selected_reports) != 1 or input_names not in {
            frozenset(required_base | selected_reports),
            frozenset(required_base | selected_reports | {"knowledge_state"}),
        }:
            raise ValueError(
                "knowledge update requires hypothesis_portfolio, exactly one diagnosis, "
                "and optionally knowledge_state"
            )
        portfolio = _knowledge_portfolio_view(inputs["hypothesis_portfolio"])
        report_name = next(iter(selected_reports))
        report = (
            LayeredDiagnosisReport.model_validate_json(
                inputs[report_name], strict=True
            )
            if report_name == "layered_diagnosis"
            else ValidationReport.model_validate_json(inputs[report_name], strict=True)
        )
        prior_state = (
            KnowledgeStateProjection.model_validate_json(
                inputs["knowledge_state"], strict=True
            )
            if "knowledge_state" in inputs
            else project_knowledge_state(portfolio, ())
        )
        update = derive_knowledge_update(portfolio, report, prior_state=prior_state)
        state = advance_knowledge_state(prior_state, update)
        return (
            TransformOutput(
                label="primary",
                content=canonical_json(update.model_dump(mode="json")),
                kind="knowledge_update",
                schema="scidiscovery.knowledge-update.v1",
                payload_schema_version=1,
                media_type="application/json",
            ),
            TransformOutput(
                label="state",
                content=canonical_json(state.model_dump(mode="json")),
                kind="knowledge_state_projection",
                schema="scidiscovery.knowledge-state-projection.v1",
                payload_schema_version=1,
                media_type="application/json",
            ),
        )


def _knowledge_portfolio_view(raw: bytes) -> HypothesisPortfolio:
    """Build the narrow internal view required by the knowledge reducer."""

    parsed = HypothesisProposal.model_validate_json(raw, strict=True)
    evidence_keys = tuple(item.source_key for item in parsed.evidence)
    if not evidence_keys:
        raise ValueError("knowledge update requires a source-backed hypothesis handoff")
    hypotheses = []
    for item in parsed.hypotheses:
        hypotheses.append(
            {
                "hypothesis_key": item.hypothesis_key,
                "statement": item.statement,
                "mechanism": item.mechanism,
                "scope": item.scope,
                # The knowledge reducer never reads parameters. Keep simulator
                # locators in the source payload instead of normalizing them.
                "parameters": [],
                "predictions": [
                    {
                        "prediction_key": prediction.prediction_key,
                        "observable": prediction.observable,
                        "expected_outcome": prediction.expected_outcome,
                        "rationale": prediction.expected_outcome,
                    }
                    for prediction in item.predictions
                ],
                "falsifiers": [
                    {
                        "falsifier_key": falsifier.falsifier_key,
                        "observable": falsifier.observable,
                        "rejection_condition": falsifier.rejection_condition,
                        "rationale": falsifier.rejection_condition,
                    }
                    for falsifier in item.falsifiers
                ],
                "competing_hypothesis_keys": list(item.competing_hypothesis_keys),
                "status": "testable",
                "support_level": "unassessed",
                "support_rationale": (
                    "The proposal payload carries no support promotion; runtime evidence "
                    "must update support through the deterministic knowledge reducer."
                ),
            }
        )
    return HypothesisPortfolio.model_validate_json(
        canonical_json({
            "objective": parsed.objective,
            "contradiction": parsed.contradiction,
            "foundation_summary": parsed.objective,
            "foundation_item_keys": list(evidence_keys),
            "hypotheses": hypotheses,
            "ranking": [item.hypothesis_key for item in parsed.hypotheses],
            "ranking_rationale": "Payload order is the ideator's declared priority.",
            "missing_inputs": [],
        }),
        strict=True,
    )


def _derive_candidate_eligibility(
    portfolio: HypothesisProposal,
    critic: CriticReview,
    audit: EvidenceAudit,
) -> CandidateEligibility:
    portfolio_keys = tuple(item.hypothesis_key for item in portfolio.hypotheses)
    reviews = {item.hypothesis_key: item for item in critic.reviews}
    if set(reviews) != set(portfolio_keys):
        raise ValueError("critic review must cover every portfolio hypothesis exactly once")

    audit_statuses = tuple(item.status for item in audit.checks)
    audit_verdict = (
        "blocked"
        if "fail" in audit_statuses
        else "pass"
        if audit_statuses and all(value in {"pass", "not_applicable"} for value in audit_statuses)
        else "revise"
    )
    critic_statuses = tuple(
        value
        for review in critic.reviews
        for value in (
            review.physical_plausibility,
            review.falsifiability,
            review.identifiability,
        )
    )
    critic_verdict = (
        "blocked"
        if "fail" in critic_statuses
        else "pass"
        if critic_statuses and all(value == "pass" for value in critic_statuses)
        else "revise"
    )
    audit_blocked = audit_verdict == "blocked"
    audit_unresolved = audit_verdict != "pass"
    critic_globally_blocked = critic_verdict == "blocked"
    assessments = []
    for hypothesis_key in portfolio_keys:
        review = reviews[hypothesis_key]
        dimensions = (
            review.physical_plausibility,
            review.falsifiability,
            review.identifiability,
        )
        unresolved = (
            (review.smallest_resolving_action,)
            if review.smallest_resolving_action is not None
            and any(value != "pass" for value in dimensions)
            else ()
        )
        if audit_blocked or critic_globally_blocked or "fail" in dimensions:
            status = "blocked"
        elif audit_unresolved or any(value != "pass" for value in dimensions):
            status = "revise"
        else:
            status = "eligible"
        assessments.append(
            CandidateAssessment(
                hypothesis_key=hypothesis_key,
                status=status,
                critic_dimensions=dimensions,
                unresolved_requirements=unresolved,
                rationale=(
                    "Status is derived from the supplied critic dimensions and the "
                    f"portfolio-wide evidence verdict {audit_verdict}."
                ),
            )
        )
    eligible = tuple(
        item.hypothesis_key for item in assessments if item.status == "eligible"
    )
    unresolved = tuple(
        dict.fromkeys(
            tuple(item.basis for item in audit.checks if item.status in {"fail", "unknown"})
            + tuple(
                missing
                for assessment in assessments
                for missing in assessment.unresolved_requirements
            )
        )
    )
    if eligible:
        status = "ready"
    elif audit_blocked or critic_globally_blocked or all(
        item.status == "blocked" for item in assessments
    ):
        status = "blocked"
    else:
        status = "revise"
    return CandidateEligibility(
        objective=portfolio.objective,
        status=status,
        critic_verdict=critic_verdict,
        evidence_verdict=audit_verdict,
        assessments=tuple(assessments),
        eligible_hypothesis_keys=eligible,
        unresolved_requirements=unresolved,
        rationale=(
            "Deterministic join only: critic dimensions govern candidate-level "
            "status and the evidence audit gates the complete portfolio."
        ),
    )


def select_transform_adapter(
    profile: str, adapters: tuple[ArtifactTransformAdapter, ...]
) -> ArtifactTransformAdapter:
    matches = tuple(
        adapter for adapter in adapters if adapter.supports_transform_profile(profile)
    )
    if not matches:
        raise ValueError(f"unsupported deterministic transform profile: {profile}")
    if len(matches) != 1:
        raise ValueError(f"ambiguous deterministic transform profile: {profile}")
    return matches[0]


def load_transform_adapters() -> tuple[ArtifactTransformAdapter, ...]:
    """Load deterministic domain transforms without coupling core to a domain."""

    discovered = entry_points().select(group=TRANSFORM_ADAPTER_ENTRY_POINT)
    adapters: list[ArtifactTransformAdapter] = []
    for entry in sorted(discovered, key=lambda item: item.name):
        factory = entry.load()
        adapter = factory()
        if not callable(getattr(adapter, "supports_transform_profile", None)):
            raise TypeError(f"transform adapter {entry.name} has no profile predicate")
        if not callable(getattr(adapter, "transform", None)):
            raise TypeError(f"transform adapter {entry.name} has no transform method")
        adapters.append(adapter)
    return tuple(adapters)


__all__ = [
    "ArtifactTransformAdapter",
    "CANDIDATE_ELIGIBILITY_PROFILE",
    "TRANSFORM_ADAPTER_ENTRY_POINT",
    "KNOWLEDGE_UPDATE_PROFILE",
    "SCIENTIFIC_INTAKE_SPLIT_PROFILE",
    "ScientificStateTransformAdapter",
    "load_transform_adapters",
    "TransformOutput",
    "select_transform_adapter",
]
