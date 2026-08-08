from __future__ import annotations

from scidiscovery.artifact_agent.schema.research_cycle import ScientificReadiness
from scidiscovery.scheduler_topology import ready_capabilities


def _state(*artifacts: str, execution: str = "not_ready") -> ScientificReadiness:
    return ScientificReadiness(
        current_contradiction="The active scientific contradiction determines routing.",
        available_artifacts=artifacts,
        claim_evaluability="not_evaluable",
        execution_readiness=execution,
        rationale="This fixture tests data readiness, not a fixed stage sequence.",
    )


def _names(state: ScientificReadiness) -> set[str]:
    return {item.name for item in ready_capabilities(state)}


def test_intake_can_be_split_without_an_extra_agent() -> None:
    names = _names(_state("scientific_intake"))
    assert "split_scientific_intake" in names
    assert "ideator" not in names


def test_multiple_ready_actions_do_not_define_a_fixed_next_stage() -> None:
    names = _names(_state("problem_frame", "scientific_foundation"))
    assert {"evidence_extractor", "ideator", "evidence_auditor"} <= names


def test_baseline_realization_can_skip_new_idea_generation() -> None:
    names = _names(
        _state("scientific_foundation", "experiment_portfolio", "tcad_project")
    )
    assert "tcad_deck_reviewer" in names
    assert "critic" not in names


def test_experiment_design_requires_the_deterministic_review_join() -> None:
    reviews_ready = _names(
        _state("hypothesis_portfolio", "scientific_review", "evidence_audit")
    )
    assert "derive_candidate_eligibility" in reviews_ready
    assert "experiment_designer" not in reviews_ready

    joined = _names(_state("hypothesis_portfolio", "candidate_eligibility"))
    assert "experiment_designer" in joined


def test_execution_requires_both_data_readiness_and_execution_readiness() -> None:
    state = _state("packaged_project")
    assert "execute_project" not in _names(state)
    authorized = _state("packaged_project", execution="authorized")
    assert "execute_project" in _names(authorized)


def test_diagnosis_waits_for_result_and_control_equivalence() -> None:
    partial = _state("experiment_portfolio", "execution_result")
    assert "diagnostician" not in _names(partial)
    complete = _state(
        "experiment_portfolio",
        "execution_result",
        "runtime_attestation",
        "control_equivalence_report",
        "metric_report",
    )
    assert "diagnostician" in _names(complete)


def test_baseline_provenance_diagnosis_needs_only_audit_and_metrics() -> None:
    partial = _state("evidence_audit")
    assert "diagnose_baseline_provenance" not in _names(partial)
    complete = _state("evidence_audit", "metric_report")
    assert "diagnose_baseline_provenance" in _names(complete)


def test_runtime_attestation_is_ready_only_after_execution_collection() -> None:
    assert "attest_runtime" not in _names(_state("packaged_project"))
    assert "attest_runtime" in _names(
        _state("packaged_project", "execution_result", execution="completed")
    )
