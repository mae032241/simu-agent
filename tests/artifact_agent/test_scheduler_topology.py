from __future__ import annotations

import pytest

from scidiscovery.scheduler_topology import advise_topology, role_runtime_profile


def test_baseline_replay_uses_short_chain_without_ideation() -> None:
    advice = advise_topology("baseline_replay")
    roles = {role for stage in advice.stages for role in stage}
    assert {"tcad_deck_author", "tcad_deck_reviewer", "diagnostician"} <= roles
    assert {"ideator", "critic"}.isdisjoint(roles)
    assert "context_builder" not in roles
    assert advice.human_reviews == ("execution_authorization",)


def test_new_mechanism_keeps_independent_creative_and_review_roles() -> None:
    advice = advise_topology("new_mechanism")
    assert ("ideator", "evidence_auditor") in advice.stages
    assert ("critic",) in advice.stages
    assert ("experiment_designer",) in advice.stages
    assert ("tcad_deck_author",) in advice.stages
    assert ("tcad_deck_reviewer",) in advice.stages
    assert ("diagnostician",) in advice.stages
    assert "derive_candidate_eligibility" in advice.deterministic_steps
    assert "derive_knowledge_update" in advice.deterministic_steps
    roles = {role for stage in advice.stages for role in stage}
    assert {
        "adjudicator",
        "context_builder",
        "knowledge_updater",
        "tcad_model_realizer",
        "tcad_model_reviewer",
        "tcad_experiment_designer",
    }.isdisjoint(roles)


def test_baseline_provenance_and_deck_revision_use_short_specialized_paths() -> None:
    provenance = advise_topology("baseline_provenance")
    assert provenance.stages == (("evidence_auditor",), ("diagnostician",))
    assert provenance.deterministic_steps == ("profile_inputs", "score_curves")

    revision = advise_topology("deck_revision")
    assert revision.stages == (("tcad_deck_reviser",), ("tcad_deck_reviewer",))
    assert "apply_deck_project_patch" in revision.deterministic_steps


def test_review_roles_have_smaller_runtime_budget_than_creative_roles() -> None:
    assert role_runtime_profile("critic").max_output_bytes < role_runtime_profile(
        "tcad_deck_author"
    ).max_output_bytes
    assert role_runtime_profile("ideator").latency_class == "creative"
    assert role_runtime_profile("evidence_auditor").timeout_seconds == 600


def test_unknown_task_mode_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown task mode"):
        advise_topology("static_workflow")  # type: ignore[arg-type]
