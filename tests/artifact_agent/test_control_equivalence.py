from __future__ import annotations

from scidiscovery.artifact_agent.schema.comparison import (
    RealizationSnapshot,
    RealizedValue,
    evaluate_control_equivalence,
)
from scidiscovery.artifact_agent.schema.experiment import ComparisonContract


def _contract() -> ComparisonContract:
    return ComparisonContract(
        baseline_case_key="historical_baseline",
        comparison_case_keys=("candidate",),
        variables=(
            {
                "variable_key": "diffusion_model",
                "scientific_path": "physics.zinc.diffusion_model",
                "factor_type": "physical",
                "comparison_role": "intended_change",
                "unit": "categorical",
                "expectations": (
                    {"case_key": "historical_baseline", "value": "model_a"},
                    {"case_key": "candidate", "value": "model_a_plus_b"},
                ),
                "equivalence_rule": "exact",
                "rationale": "The diffusion mechanism is the intended change.",
            },
            {
                "variable_key": "mesh_policy",
                "scientific_path": "numerics.mesh.policy",
                "factor_type": "numerical",
                "comparison_role": "frozen",
                "unit": "categorical",
                "expectations": (
                    {"case_key": "historical_baseline", "value": "fig4_mesh_v1"},
                    {"case_key": "candidate", "value": "fig4_mesh_v1"},
                ),
                "equivalence_rule": "exact",
                "rationale": "The mesh must not confound the physical comparison.",
            },
        ),
        required_observables=("zinc_profile",),
        identifiability_claims=(
            {
                "hypothesis_key": "secondary_tail",
                "observable": "zinc_profile",
                "distinguishing_outcome": "The low-concentration tail improves without moving the front.",
                "decision_rule": "Compare front and tail metrics separately.",
                "ambiguity_conditions": ("The mesh changes between cases.",),
                "smallest_resolving_control": "Run a mesh-only A/B control.",
            },
        ),
    )


def _snapshot(case: str, model: str, mesh: str) -> RealizationSnapshot:
    return RealizationSnapshot(
        case_key=case,
        source_description=f"Realization manifest for {case}.",
        values=(
            RealizedValue(
                variable_key="diffusion_model",
                scientific_path="physics.zinc.diffusion_model",
                value=model,
                unit="categorical",
                source_locator=f"{case}/model.cmd:model",
            ),
            RealizedValue(
                variable_key="mesh_policy",
                scientific_path="numerics.mesh.policy",
                value=mesh,
                unit="categorical",
                source_locator=f"{case}/mesh.cmd:mesh",
            ),
        ),
    )


def test_declared_model_change_with_frozen_mesh_is_evaluable() -> None:
    report = evaluate_control_equivalence(
        _contract(),
        (
            _snapshot("historical_baseline", "model_a", "fig4_mesh_v1"),
            _snapshot("candidate", "model_a_plus_b", "fig4_mesh_v1"),
        ),
    )
    assert report.status == "pass"
    assert report.physical_claim_evaluable
    assert {item.classification for item in report.differences} == {
        "expected_change",
        "verified_invariant",
    }


def test_mesh_change_invalidates_the_physical_comparison() -> None:
    report = evaluate_control_equivalence(
        _contract(),
        (
            _snapshot("historical_baseline", "model_a", "fig4_mesh_v1"),
            _snapshot("candidate", "model_a_plus_b", "fig4_mesh_v2"),
        ),
    )
    assert report.status == "fail"
    assert not report.physical_claim_evaluable
    mesh = next(item for item in report.differences if item.variable_key == "mesh_policy")
    assert mesh.classification == "unexpected_difference"


def test_undeclared_realized_difference_is_not_silently_ignored() -> None:
    baseline = _snapshot("historical_baseline", "model_a", "fig4_mesh_v1")
    candidate = _snapshot("candidate", "model_a_plus_b", "fig4_mesh_v1")
    candidate = candidate.model_copy(
        update={
            "values": candidate.values
            + (
                RealizedValue(
                    variable_key="source_boundary",
                    scientific_path="boundary.zinc.source",
                    value="finite_reservoir",
                    unit="categorical",
                    source_locator="candidate/model.cmd:source",
                ),
            )
        }
    )
    report = evaluate_control_equivalence(_contract(), (baseline, candidate))
    assert report.status == "fail"
    assert any(
        item.variable_key == "source_boundary"
        and item.classification == "unexpected_difference"
        for item in report.differences
    )
