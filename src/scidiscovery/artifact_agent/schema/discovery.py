"""Deterministic cross-object validation for one scientific discovery chain."""

from __future__ import annotations

from collections.abc import Sequence

from .experiment import ExperimentPortfolio
from .hypothesis import HypothesisPortfolio
from .knowledge import (
    KnowledgeStateProjection,
    KnowledgeUpdate,
    advance_knowledge_state,
    project_knowledge_state,
    validate_update_against_inputs,
)
from .layered_diagnosis import LayeredDiagnosisReport
from .research_cycle import (
    ProblemFrame,
    ScientificReview,
    validate_problem_frame_against_foundation,
)
from .scientific_foundation import ScientificFoundation
from .validation import ValidationReport, validate_report_against_plan


def validate_hypotheses_against_foundation(
    foundation: ScientificFoundation,
    portfolio: HypothesisPortfolio,
) -> None:
    foundation_keys = {item.item_key for item in foundation.items}
    if not set(portfolio.foundation_item_keys).issubset(foundation_keys):
        raise ValueError("hypothesis portfolio references an unknown foundation item")


def validate_experiments_against_hypotheses(
    hypotheses: HypothesisPortfolio,
    experiments: ExperimentPortfolio,
) -> None:
    hypothesis_by_key = {
        item.hypothesis_key: item for item in hypotheses.hypotheses
    }
    if not set(experiments.selected_hypothesis_keys).issubset(hypothesis_by_key):
        raise ValueError("experiment portfolio selects an unknown hypothesis")
    for proposal in experiments.proposals:
        for prediction in proposal.prediction_tests:
            hypothesis = hypothesis_by_key[prediction.hypothesis_key]
            if prediction.prediction_key not in {
                item.prediction_key for item in hypothesis.predictions
            }:
                raise ValueError("experiment references an unknown hypothesis prediction")


def validate_review_against_hypotheses(
    foundation: ScientificFoundation,
    hypotheses: HypothesisPortfolio,
    review: ScientificReview,
) -> None:
    if review.review_target != "hypothesis_portfolio":
        raise ValueError("hypothesis review has the wrong review_target")
    hypothesis_keys = {item.hypothesis_key for item in hypotheses.hypotheses}
    reviewed_keys = {item.hypothesis_key for item in review.hypothesis_reviews}
    if reviewed_keys != hypothesis_keys:
        raise ValueError("scientific review must cover every hypothesis exactly once")
    foundation_keys = {item.item_key for item in foundation.items}
    if not set(review.evidence_item_keys).issubset(foundation_keys):
        raise ValueError("scientific review references an unknown foundation item")


def validate_discovery_chain(
    foundation: ScientificFoundation,
    hypotheses: HypothesisPortfolio,
    experiments: ExperimentPortfolio,
    reports: Sequence[ValidationReport],
    updates: Sequence[KnowledgeUpdate],
) -> KnowledgeStateProjection:
    """Audit links and replay updates without choosing the scientific outcome."""

    validate_hypotheses_against_foundation(foundation, hypotheses)
    validate_experiments_against_hypotheses(hypotheses, experiments)
    plans = {
        (item.experiment_key, item.plan_key): item
        for item in experiments.validation_plans
    }
    report_by_key: dict[tuple[str, str], ValidationReport] = {}
    for report in reports:
        key = (report.experiment_key, report.plan_key)
        if key in report_by_key:
            raise ValueError("discovery chain contains duplicate validation reports")
        try:
            plan = plans[key]
        except KeyError as error:
            raise ValueError("validation report references an unknown plan") from error
        validate_report_against_plan(plan, report)
        report_by_key[key] = report

    hypothesis_by_key = {
        item.hypothesis_key: item for item in hypotheses.hypotheses
    }
    used_reports: set[tuple[str, str]] = set()
    for update in updates:
        key = (update.experiment_key, update.validation_plan_key)
        try:
            report = report_by_key[key]
        except KeyError as error:
            raise ValueError("knowledge update has no matching validation report") from error
        if key in used_reports:
            raise ValueError("one validation report cannot create multiple knowledge updates")
        used_reports.add(key)
        if update.validation_verdict != report.overall_verdict:
            raise ValueError("knowledge update verdict does not match validation report")
        if update.numerical_verdict != report.numerical.status:
            raise ValueError("knowledge update numerics do not match validation report")
        for transition in update.transitions:
            try:
                hypothesis = hypothesis_by_key[transition.hypothesis_key]
            except KeyError as error:
                raise ValueError("knowledge update references an unknown hypothesis") from error
            if not set(transition.predictions_checked).issubset(
                {item.prediction_key for item in hypothesis.predictions}
            ):
                raise ValueError("knowledge update references an unknown prediction")
            if not set(transition.falsifiers_triggered).issubset(
                {item.falsifier_key for item in hypothesis.falsifiers}
            ):
                raise ValueError("knowledge update references an unknown falsifier")
    return project_knowledge_state(hypotheses, updates)


def validate_layered_discovery_chain(
    problem_frame: ProblemFrame,
    foundation: ScientificFoundation,
    hypotheses: HypothesisPortfolio,
    reviews: Sequence[ScientificReview],
    experiments: ExperimentPortfolio,
    diagnoses: Sequence[LayeredDiagnosisReport],
    updates: Sequence[KnowledgeUpdate],
) -> KnowledgeStateProjection:
    """Audit and replay the new layered scientific chain without choosing outcomes."""

    validate_problem_frame_against_foundation(problem_frame, foundation)
    validate_hypotheses_against_foundation(foundation, hypotheses)
    hypothesis_reviews = tuple(
        item for item in reviews if item.review_target == "hypothesis_portfolio"
    )
    if len(hypothesis_reviews) != 1:
        raise ValueError("layered discovery chain requires one hypothesis review")
    validate_review_against_hypotheses(
        foundation, hypotheses, hypothesis_reviews[0]
    )
    validate_experiments_against_hypotheses(hypotheses, experiments)

    known_plans = {
        (item.experiment_key, item.plan_key)
        for item in experiments.validation_plans
    }
    diagnosis_by_key: dict[tuple[str, str], LayeredDiagnosisReport] = {}
    for diagnosis in diagnoses:
        key = (diagnosis.experiment_key, diagnosis.plan_key)
        if key not in known_plans:
            raise ValueError("layered diagnosis references an unknown validation plan")
        if key in diagnosis_by_key:
            raise ValueError("layered discovery chain contains duplicate diagnoses")
        diagnosis_by_key[key] = diagnosis

    update_by_key: dict[tuple[str, str], KnowledgeUpdate] = {}
    for update in updates:
        key = (update.experiment_key, update.validation_plan_key)
        if key in update_by_key:
            raise ValueError("one layered diagnosis cannot create multiple updates")
        update_by_key[key] = update
    if set(update_by_key) != set(diagnosis_by_key):
        raise ValueError("every layered diagnosis requires exactly one knowledge update")

    state = project_knowledge_state(hypotheses, ())
    for update in updates:
        key = (update.experiment_key, update.validation_plan_key)
        validate_update_against_inputs(
            hypotheses,
            diagnosis_by_key[key],
            update,
            prior_state=state,
        )
        state = advance_knowledge_state(state, update)
    return state


__all__ = [
    "validate_discovery_chain",
    "validate_layered_discovery_chain",
    "validate_experiments_against_hypotheses",
    "validate_hypotheses_against_foundation",
    "validate_review_against_hypotheses",
]
