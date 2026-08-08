from __future__ import annotations

from scidiscovery.platforms.roles import load_roles


def _roles():
    return {item.name: item for item in load_roles()}


def test_evidence_extractor_owns_problem_frame_and_foundation() -> None:
    role = _roles()["evidence_extractor"]
    assert role.output_model.endswith(":ScientificIntake")
    assert "ProblemFrame" in role.prompt
    assert "ScientificFoundation" in role.prompt
    assert "same objective" in role.prompt


def test_critic_has_machine_readable_identifiability_contract() -> None:
    role = _roles()["critic"]
    assert role.output_model.endswith(":CriticReview")
    assert "CriticReview" in role.prompt
    assert "identifiability" in role.prompt
    assert "smallest" in role.prompt


def test_experiment_and_diagnosis_roles_expose_scientific_gates() -> None:
    roles = _roles()
    designer = roles["experiment_designer"].prompt
    assert "comparison" in designer
    assert "frozen variables" in designer
    assert "confounded" in designer
    diagnosis = " ".join(roles["diagnostician"].prompt.split())
    assert roles["diagnostician"].output_model.endswith(":LayeredDiagnosisReport")
    for phrase in (
        "evidence identity",
        "implementation fidelity",
        "numerical validity",
        "control equivalence",
        "physical interpretation",
    ):
        assert phrase in diagnosis


def test_tcad_author_and_reviewer_cover_comparison_contract() -> None:
    roles = _roles()
    assert "comparison contract" in roles["tcad_deck_author"].prompt
    assert "comparison contract" in roles["tcad_deck_reviewer"].prompt
    assert "undeclared difference" in roles["tcad_deck_reviewer"].prompt
    assert "tcad.deck-review.provenance.v1" in roles["tcad_deck_reviewer"].prompt
    assert "separate deterministic transform" in roles["tcad_deck_reviewer"].prompt


def test_tcad_code_roles_apply_direct_solver_skill_contract() -> None:
    roles = _roles()
    for name in ("tcad_deck_author", "tcad_deck_reviewer", "tcad_deck_reviser"):
        prompt = roles[name].prompt
        assert "sentaurus-tcad-code" in prompt
        assert ".cmd" in prompt
        assert "Workben" in prompt
    assert "network, VM" in roles["tcad_deck_author"].prompt
