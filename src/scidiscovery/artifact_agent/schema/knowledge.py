"""Evidence-bound hypothesis updates and deterministic state projection."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import Identifier, SchemaModel, canonical_json, canonical_sha256
from .hypothesis import HypothesisPortfolio, HypothesisStatus, SupportLevel
from .layered_diagnosis import LayeredDiagnosisReport
from .scientific_foundation import SourceType
from .validation import (
    HypothesisAssessmentOutcome,
    RecommendedTaskMode,
    ValidationReport,
)


TransitionOutcome = HypothesisAssessmentOutcome
NextTaskMode = RecommendedTaskMode


class KnowledgeEvidence(SchemaModel):
    source_key: Identifier
    source_type: SourceType
    title: Annotated[str, Field(min_length=1, max_length=2048)]
    locator: Annotated[str, Field(min_length=1, max_length=4096)]


class HypothesisTransition(SchemaModel):
    hypothesis_key: Identifier
    prior_status: HypothesisStatus
    new_status: HypothesisStatus
    prior_support_level: SupportLevel
    new_support_level: SupportLevel
    outcome: TransitionOutcome
    evidence_keys: Annotated[
        tuple[Identifier, ...], Field(min_length=1, max_length=64)
    ]
    predictions_checked: Annotated[tuple[Identifier, ...], Field(max_length=64)] = ()
    falsifiers_triggered: Annotated[tuple[Identifier, ...], Field(max_length=64)] = ()
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    def _transition_is_epistemically_coherent(self) -> HypothesisTransition:
        for values, label in (
            (self.evidence_keys, "evidence_keys"),
            (self.predictions_checked, "predictions_checked"),
            (self.falsifiers_triggered, "falsifiers_triggered"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{label} must be unique")
        if self.outcome == "not_tested" and (
            self.new_status != self.prior_status
            or self.new_support_level != self.prior_support_level
        ):
            raise ValueError("not_tested cannot change hypothesis state")
        if self.outcome == "supports" and self.new_status != "supported":
            raise ValueError("supporting outcome must promote to supported")
        if self.outcome == "contradicts" and self.new_status not in {
            "weakened",
            "rejected",
        }:
            raise ValueError("contradicting outcome must weaken or reject")
        if self.new_status == "rejected" and not self.falsifiers_triggered:
            raise ValueError("rejection requires a triggered pre-registered falsifier")
        if self.outcome == "inconclusive":
            if self.new_status != "inconclusive":
                raise ValueError("inconclusive must produce inconclusive status")
            if self.new_support_level != self.prior_support_level:
                raise ValueError("inconclusive cannot change support level")
        if self.outcome == "invalid_study" and (
            self.new_status != self.prior_status
            or self.new_support_level != self.prior_support_level
        ):
            raise ValueError("invalid_study cannot change hypothesis state")
        return self


class KnowledgeUpdate(SchemaModel):
    update_key: Identifier
    previous_update_key: Identifier | None = None
    objective: Annotated[str, Field(min_length=1, max_length=8192)]
    hypothesis_portfolio_source_key: Identifier
    validation_report_source_key: Identifier
    experiment_key: Identifier
    validation_plan_key: Identifier
    validation_verdict: Literal["pass", "fail", "inconclusive", "invalid_study"]
    numerical_verdict: Literal[
        "pass", "fail", "inconclusive", "not_evaluable", "not_applicable"
    ]
    evidence: Annotated[
        tuple[KnowledgeEvidence, ...], Field(min_length=2, max_length=256)
    ]
    transitions: Annotated[
        tuple[HypothesisTransition, ...], Field(min_length=1, max_length=32)
    ]
    remaining_contradiction: Annotated[str, Field(min_length=1, max_length=8192)]
    next_task_mode: NextTaskMode
    next_task_instruction: Annotated[str, Field(min_length=1, max_length=4096)]
    human_review_required: bool

    @model_validator(mode="after")
    def _update_is_scientifically_coherent(self) -> KnowledgeUpdate:
        source_keys = tuple(item.source_key for item in self.evidence)
        if len(source_keys) != len(set(source_keys)):
            raise ValueError("knowledge source_key values must be unique")
        required = {
            self.hypothesis_portfolio_source_key,
            self.validation_report_source_key,
        }
        if not required.issubset(set(source_keys)):
            raise ValueError("knowledge update must cite its portfolio and validation report")
        transition_keys = tuple(item.hypothesis_key for item in self.transitions)
        if len(transition_keys) != len(set(transition_keys)):
            raise ValueError("a knowledge update may transition each hypothesis once")
        for transition in self.transitions:
            if not set(transition.evidence_keys).issubset(set(source_keys)):
                raise ValueError("transition references an undeclared source_key")
            if transition.outcome == "supports" and (
                self.validation_verdict != "pass" or self.numerical_verdict != "pass"
            ):
                raise ValueError("support requires a numerically valid passing study")
            if transition.outcome == "contradicts" and (
                self.validation_verdict != "fail" or self.numerical_verdict != "pass"
            ):
                raise ValueError(
                    "contradiction requires a numerically valid failed prediction"
                )
            if transition.outcome == "inconclusive" and (
                self.validation_verdict != "inconclusive"
                or self.numerical_verdict != "pass"
            ):
                raise ValueError(
                    "inconclusive outcome requires a valid but inconclusive study"
                )
            if transition.outcome == "invalid_study" and not (
                self.validation_verdict == "invalid_study"
                or self.numerical_verdict
                in {"fail", "inconclusive", "not_evaluable", "not_applicable"}
            ):
                raise ValueError("invalid_study requires an invalid study verdict")
        decisive = any(
            item.new_status in {"supported", "rejected"} for item in self.transitions
        )
        if self.human_review_required != decisive:
            raise ValueError(
                "human review is required exactly for support or rejection promotion"
            )
        return self


class ProjectedHypothesis(SchemaModel):
    hypothesis_key: Identifier
    status: HypothesisStatus
    support_level: SupportLevel
    last_update_key: Identifier | None = None


class KnowledgeStateProjection(SchemaModel):
    hypotheses: Annotated[
        tuple[ProjectedHypothesis, ...], Field(min_length=1, max_length=32)
    ]
    last_update_key: Identifier | None = None
    remaining_contradiction: Annotated[str, Field(min_length=1, max_length=8192)]
    next_task_mode: NextTaskMode
    next_task_instruction: Annotated[str, Field(min_length=1, max_length=4096)]


def validate_update_against_inputs(
    portfolio: HypothesisPortfolio,
    report: ValidationReport | LayeredDiagnosisReport,
    update: KnowledgeUpdate,
    *,
    prior_state: KnowledgeStateProjection | None = None,
) -> None:
    """Validate semantic links that cannot be checked inside one JSON object."""

    if update.experiment_key != report.experiment_key:
        raise ValueError("knowledge update experiment does not match validation report")
    if update.validation_plan_key != report.plan_key:
        raise ValueError("knowledge update plan does not match validation report")
    if update.validation_verdict != report.overall_verdict:
        raise ValueError("knowledge update verdict does not match validation report")
    numerical_verdict = (
        report.gates.numerical_validity.status
        if isinstance(report, LayeredDiagnosisReport)
        else report.numerical.status
    )
    if update.numerical_verdict != numerical_verdict:
        raise ValueError("knowledge update numerical verdict does not match validation report")
    expected_previous = prior_state.last_update_key if prior_state is not None else None
    if update.previous_update_key != expected_previous:
        raise ValueError("knowledge update does not continue the supplied state")
    hypotheses = {item.hypothesis_key: item for item in portfolio.hypotheses}
    prior = (
        {
            item.hypothesis_key: (item.status, item.support_level)
            for item in prior_state.hypotheses
        }
        if prior_state is not None
        else {
            item.hypothesis_key: (item.status, item.support_level)
            for item in portfolio.hypotheses
        }
    )
    if set(prior) != set(hypotheses):
        raise ValueError("knowledge state does not match hypothesis portfolio")
    for transition in update.transitions:
        try:
            hypothesis = hypotheses[transition.hypothesis_key]
        except KeyError as error:
            raise ValueError("knowledge update references an unknown hypothesis") from error
        prior_status, prior_support = prior[transition.hypothesis_key]
        if transition.prior_status != prior_status:
            raise ValueError("knowledge update prior status differs from current state")
        if transition.prior_support_level != prior_support:
            raise ValueError("knowledge update prior support differs from current state")
        prediction_keys = {item.prediction_key for item in hypothesis.predictions}
        falsifier_keys = {item.falsifier_key for item in hypothesis.falsifiers}
        if not set(transition.predictions_checked).issubset(prediction_keys):
            raise ValueError("transition references an unknown prediction")
        if not set(transition.falsifiers_triggered).issubset(falsifier_keys):
            raise ValueError("transition references an unknown falsifier")


def derive_knowledge_update(
    portfolio: HypothesisPortfolio,
    report: ValidationReport | LayeredDiagnosisReport,
    *,
    prior_state: KnowledgeStateProjection | None = None,
) -> KnowledgeUpdate:
    """Convert a diagnostician's explicit judgments into state transitions."""

    if isinstance(report, ValidationReport):
        if report.knowledge_update_applicability != "required":
            raise ValueError("validation report does not require a knowledge update")
        if report.remaining_contradiction is None or report.recommended_task_mode is None:
            raise ValueError("validation report has incomplete knowledge-update fields")
        numerical_verdict = report.numerical.status
    else:
        numerical_verdict = report.gates.numerical_validity.status
    hypotheses = {item.hypothesis_key: item for item in portfolio.hypotheses}
    if prior_state is None:
        current = {
            item.hypothesis_key: (item.status, item.support_level)
            for item in portfolio.hypotheses
        }
        previous_update_key = None
    else:
        current = {
            item.hypothesis_key: (item.status, item.support_level)
            for item in prior_state.hypotheses
        }
        if set(current) != set(hypotheses):
            raise ValueError("knowledge state does not match hypothesis portfolio")
        previous_update_key = prior_state.last_update_key
    transitions = []
    support_order: tuple[SupportLevel, ...] = (
        "unassessed",
        "low",
        "medium",
        "high",
    )
    for assessment in report.hypothesis_assessments:
        try:
            hypothesis = hypotheses[assessment.hypothesis_key]
        except KeyError as error:
            raise ValueError(
                "hypothesis assessment references an unknown hypothesis"
            ) from error
        prediction_keys = {item.prediction_key for item in hypothesis.predictions}
        falsifier_keys = {item.falsifier_key for item in hypothesis.falsifiers}
        if not set(assessment.predictions_checked).issubset(prediction_keys):
            raise ValueError("hypothesis assessment references an unknown prediction")
        if not set(assessment.falsifiers_triggered).issubset(falsifier_keys):
            raise ValueError("hypothesis assessment references an unknown falsifier")
        prior_status, prior_support = current[hypothesis.hypothesis_key]

        if assessment.outcome == "supports":
            new_status: HypothesisStatus = "supported"
            support_index = support_order.index(prior_support)
            new_support: SupportLevel = support_order[min(support_index + 1, 3)]
        elif assessment.outcome == "contradicts":
            new_status = (
                "rejected" if assessment.falsifiers_triggered else "weakened"
            )
            new_support = prior_support
        elif assessment.outcome == "inconclusive":
            new_status = "inconclusive"
            new_support = prior_support
        elif assessment.outcome == "invalid_study":
            new_status = prior_status
            new_support = prior_support
        else:
            new_status = prior_status
            new_support = prior_support

        transitions.append(
            HypothesisTransition(
                hypothesis_key=hypothesis.hypothesis_key,
                prior_status=prior_status,
                new_status=new_status,
                prior_support_level=prior_support,
                new_support_level=new_support,
                outcome=assessment.outcome,
                evidence_keys=("hypothesis_portfolio", "validation_report"),
                predictions_checked=assessment.predictions_checked,
                falsifiers_triggered=assessment.falsifiers_triggered,
                rationale=assessment.rationale,
            )
        )

    update = KnowledgeUpdate(
        update_key=(
            "knowledge_update_"
            + canonical_sha256(
                {
                    "portfolio": portfolio,
                    "report": report,
                    "previous_update_key": previous_update_key,
                }
            )[:24]
        ),
        previous_update_key=previous_update_key,
        objective=portfolio.objective,
        hypothesis_portfolio_source_key="hypothesis_portfolio",
        validation_report_source_key="validation_report",
        experiment_key=report.experiment_key,
        validation_plan_key=report.plan_key,
        validation_verdict=report.overall_verdict,
        numerical_verdict=numerical_verdict,
        evidence=(
            KnowledgeEvidence(
                source_key="hypothesis_portfolio",
                source_type="frozen_input",
                title="Frozen hypothesis portfolio",
                locator="hypothesis_portfolio",
            ),
            KnowledgeEvidence(
                source_key="validation_report",
                source_type="runtime_output",
                title="Validated study diagnosis",
                locator="validation_report",
            ),
        ),
        transitions=tuple(transitions),
        remaining_contradiction=report.remaining_contradiction,
        next_task_mode=report.recommended_task_mode,
        next_task_instruction=report.next_action,
        human_review_required=any(
            item.new_status in {"supported", "rejected"} for item in transitions
        ),
    )
    validate_update_against_inputs(
        portfolio, report, update, prior_state=prior_state
    )
    return update


def advance_knowledge_state(
    prior_state: KnowledgeStateProjection,
    update: KnowledgeUpdate,
) -> KnowledgeStateProjection:
    """Apply one already validated update to an existing projection."""

    if update.previous_update_key != prior_state.last_update_key:
        raise ValueError("knowledge update does not continue the supplied state")
    states = {
        item.hypothesis_key: (item.status, item.support_level, item.last_update_key)
        for item in prior_state.hypotheses
    }
    for transition in update.transitions:
        try:
            status, support, _ = states[transition.hypothesis_key]
        except KeyError as error:
            raise ValueError("knowledge update references an unknown hypothesis") from error
        if transition.prior_status != status:
            raise ValueError("knowledge transition has a stale prior status")
        if transition.prior_support_level != support:
            raise ValueError("knowledge transition has a stale prior support level")
        states[transition.hypothesis_key] = (
            transition.new_status,
            transition.new_support_level,
            update.update_key,
        )
    return KnowledgeStateProjection(
        hypotheses=tuple(
            ProjectedHypothesis(
                hypothesis_key=item.hypothesis_key,
                status=states[item.hypothesis_key][0],
                support_level=states[item.hypothesis_key][1],
                last_update_key=states[item.hypothesis_key][2],
            )
            for item in prior_state.hypotheses
        ),
        last_update_key=update.update_key,
        remaining_contradiction=update.remaining_contradiction,
        next_task_mode=update.next_task_mode,
        next_task_instruction=update.next_task_instruction,
    )


def project_knowledge_state(
    portfolio: HypothesisPortfolio,
    updates: Sequence[KnowledgeUpdate],
) -> KnowledgeStateProjection:
    """Replay immutable updates without making a new scientific judgment."""

    states = {
        item.hypothesis_key: (item.status, item.support_level, None)
        for item in portfolio.hypotheses
    }
    previous: str | None = None
    remaining = portfolio.contradiction
    next_mode: NextTaskMode = "result_diagnosis"
    next_instruction = "Diagnose the current contradiction before scheduling more work."
    for update in updates:
        if update.previous_update_key != previous:
            raise ValueError("knowledge update chain is not contiguous")
        for transition in update.transitions:
            try:
                status, support, _ = states[transition.hypothesis_key]
            except KeyError as error:
                raise ValueError("knowledge update references an unknown hypothesis") from error
            if transition.prior_status != status:
                raise ValueError("knowledge transition has a stale prior status")
            if transition.prior_support_level != support:
                raise ValueError("knowledge transition has a stale prior support level")
            states[transition.hypothesis_key] = (
                transition.new_status,
                transition.new_support_level,
                update.update_key,
            )
        previous = update.update_key
        remaining = update.remaining_contradiction
        next_mode = update.next_task_mode
        next_instruction = update.next_task_instruction
    return KnowledgeStateProjection(
        hypotheses=tuple(
            ProjectedHypothesis(
                hypothesis_key=item.hypothesis_key,
                status=states[item.hypothesis_key][0],
                support_level=states[item.hypothesis_key][1],
                last_update_key=states[item.hypothesis_key][2],
            )
            for item in portfolio.hypotheses
        ),
        last_update_key=previous,
        remaining_contradiction=remaining,
        next_task_mode=next_mode,
        next_task_instruction=next_instruction,
    )


def validate_knowledge_update(value: dict[str, object]) -> dict[str, object]:
    return KnowledgeUpdate.model_validate_json(
        canonical_json(value), strict=True
    ).model_dump(mode="json")


__all__ = [
    "HypothesisTransition",
    "KnowledgeEvidence",
    "KnowledgeStateProjection",
    "KnowledgeUpdate",
    "NextTaskMode",
    "ProjectedHypothesis",
    "TransitionOutcome",
    "advance_knowledge_state",
    "derive_knowledge_update",
    "project_knowledge_state",
    "validate_knowledge_update",
    "validate_update_against_inputs",
]
