from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.interfaces.mcp_worker import WorkerMCPRouter
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.core_context_policies import (
    EXPERIMENT_DESIGN_CONTEXT_POLICIES,
)
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.experiment import (
    ExperimentPortfolio,
    experiment_value_score,
    validate_experiment_portfolio,
)


def _dimension(prefix: str, observable: str) -> dict[str, object]:
    return {
        "applicability": "required",
        "rationale": f"{prefix} validation is required before a claim.",
        "checks": [
            {
                "check_key": f"{prefix}_check",
                "observable": observable,
                "metric": f"{prefix} metric",
                "evaluation_mode": "reviewed_qualitative",
                "acceptance_condition": f"The declared {prefix} threshold passes.",
                "failure_action": "Reject the claim and diagnose the failed invariant.",
                "basis": "Pre-registered scientific acceptance rule.",
            }
        ],
    }


def _proposal(
    key: str = "complete_vs_uniform_field",
    *,
    information_gain: str = "high",
    cost: str = "medium",
) -> dict[str, object]:
    return {
        "experiment_key": key,
        "objective": "Test whether complete topology localizes the electric field.",
        "hypothesis_keys": ["field_localization"],
        "changed_factors": [
            {
                "name": "lateral_topology",
                "factor_type": "physical",
                "values": ["complete", "uniform_control"],
                "unit": "categorical",
                "rationale": "This is the mechanism-specific structural factor.",
            }
        ],
        "frozen_invariants": [
            "Identical vertical five-layer stack and material parameters."
        ],
        "cases": [
            {
                "case_key": f"{key}_control",
                "scientific_role": "control",
                "settings": [
                    {
                        "name": "lateral_topology",
                        "value": "uniform_control",
                        "unit": "categorical",
                    }
                ],
                "purpose": "Establish the uniform-topology field baseline.",
            },
            {
                "case_key": f"{key}_complete",
                "scientific_role": "perturbation",
                "settings": [
                    {
                        "name": "lateral_topology",
                        "value": "complete",
                        "unit": "categorical",
                    }
                ],
                "purpose": "Realize the paper-consistent complete topology.",
            },
        ],
        "required_observables": [
            "Electric-field map",
            "Depletion boundary",
            "Terminal capacitance",
        ],
        "comparison_contract": {
            "baseline_case_key": f"{key}_control",
            "comparison_case_keys": [f"{key}_complete"],
            "variables": [
                {
                    "variable_key": "lateral_topology",
                    "scientific_path": "device.geometry.lateral_topology",
                    "factor_type": "physical",
                    "comparison_role": "intended_change",
                    "unit": "categorical",
                    "expectations": [
                        {
                            "case_key": f"{key}_control",
                            "value": "uniform_control",
                        },
                        {
                            "case_key": f"{key}_complete",
                            "value": "complete",
                        },
                    ],
                    "equivalence_rule": "exact",
                    "rationale": "Topology is the only intended physical change.",
                },
                {
                    "variable_key": "mesh_policy",
                    "scientific_path": "numerics.mesh.policy",
                    "factor_type": "numerical",
                    "comparison_role": "frozen",
                    "unit": "categorical",
                    "expectations": [
                        {"case_key": f"{key}_control", "value": "mesh_v1"},
                        {"case_key": f"{key}_complete", "value": "mesh_v1"},
                    ],
                    "equivalence_rule": "exact",
                    "rationale": "The numerical realization must not confound topology.",
                },
            ],
            "required_observables": [
                "Electric-field map",
                "Depletion boundary",
                "Terminal capacitance",
            ],
            "identifiability_claims": [
                {
                    "hypothesis_key": "field_localization",
                    "observable": "Electric-field map",
                    "distinguishing_outcome": "Only the complete case has an edge peak.",
                    "decision_rule": "Compare converged peak location and magnitude.",
                    "ambiguity_conditions": [
                        "A mesh or boundary-condition difference can create the peak."
                    ],
                    "smallest_resolving_control": "Run an otherwise identical mesh-only control.",
                }
            ],
        },
        "prediction_tests": [
            {
                "hypothesis_key": "field_localization",
                "prediction_key": "edge_field_peak",
                "observable": "Electric-field map",
                "expected_result": "The complete case shows a localized edge peak.",
                "falsifying_result": "The converged field distributions are equivalent.",
            }
        ],
        "resource_estimate": {
            "case_count": 2,
            "relative_cost": cost,
            "runtime_basis": "Two equilibrium or bounded bias cases.",
        },
        "stop_conditions": [
            "Stop if the complete structure is not realized exactly.",
            "Stop if numerical convergence checks fail.",
        ],
        "value_assessment": {
            "evidence_support": "medium",
            "discrimination_power": "high",
            "information_gain": information_gain,
            "cost": cost,
            "added_free_parameters": 0,
            "rationale": "The comparison isolates topology without adding fitted physics.",
        },
    }


def _plan(experiment_key: str = "complete_vs_uniform_field") -> dict[str, object]:
    return {
        "plan_key": f"validate_{experiment_key}",
        "experiment_key": experiment_key,
        "numerical": _dimension("numerical", "Mesh and solver residuals"),
        "physical": _dimension("physical", "Field and depletion maps"),
        "experimental": _dimension("experimental", "Measured C-V curve"),
    }


def _portfolio() -> dict[str, object]:
    return {
        "objective": "Select the smallest discriminating complete-structure study.",
        "selected_hypothesis_keys": ["field_localization"],
        "proposals": [_proposal()],
        "validation_plans": [_plan()],
        "priority_order": ["complete_vs_uniform_field"],
        "priority_rationale": "This study tests topology before adding physical fit parameters.",
    }


def _engineering_portfolio() -> dict[str, object]:
    experiment_key = "direct_sprocess_smoke"
    return {
        "study_kind": "engineering",
        "objective": "Verify one direct SProcess invocation and its required outputs.",
        "selected_hypothesis_keys": [],
        "proposals": [
            {
                "experiment_key": experiment_key,
                "objective": "Run one bounded direct-entrypoint qualification case.",
                "hypothesis_keys": [],
                "changed_factors": [],
                "frozen_invariants": ["No scientific parameter is calibrated."],
                "cases": [
                    {
                        "case_key": "direct_sprocess_baseline",
                        "scientific_role": "baseline",
                        "settings": [],
                        "purpose": "Test parser, solver termination, and output collection.",
                    }
                ],
                "required_observables": [
                    "solver exit state",
                    "declared TDR and PLX outputs",
                ],
                "comparison_contract": None,
                "prediction_tests": [],
                "resource_estimate": {
                    "case_count": 1,
                    "relative_cost": "low",
                    "runtime_basis": "One bounded SProcess invocation.",
                },
                "stop_conditions": ["Stop at the first parser or output failure."],
                "value_assessment": {
                    "evidence_support": "high",
                    "discrimination_power": "low",
                    "information_gain": "medium",
                    "cost": "low",
                    "added_free_parameters": 0,
                    "rationale": "The case closes an implementation invariant only.",
                },
            }
        ],
        "validation_plans": [
            {
                "plan_key": "validate_direct_sprocess_smoke",
                "experiment_key": experiment_key,
                "numerical": _dimension("numerical", "Solver and declared outputs"),
                "physical": {
                    "applicability": "not_applicable",
                    "rationale": "The engineering smoke makes no physical claim.",
                    "checks": [],
                },
                "experimental": {
                    "applicability": "not_applicable",
                    "rationale": "The engineering smoke makes no measurement claim.",
                    "checks": [],
                },
            }
        ],
        "priority_order": [experiment_key],
        "priority_rationale": "Close the earliest execution invariant first.",
    }


def _validate(value: dict[str, object]) -> ExperimentPortfolio:
    return ExperimentPortfolio.model_validate_json(canonical_json(value), strict=True)


def test_experiment_portfolio_pre_registers_three_validation_dimensions() -> None:
    portfolio = _validate(_portfolio())
    assert experiment_value_score(portfolio.proposals[0]) == 6
    assert portfolio.validation_plans[0].claim_gate == "all_required_checks_pass"
    assert validate_experiment_portfolio(_portfolio())["schema_version"] == 1


def test_engineering_portfolio_is_single_case_and_claim_free() -> None:
    portfolio = _validate(_engineering_portfolio())

    assert portfolio.study_kind == "engineering"
    assert portfolio.selected_hypothesis_keys == ()
    assert portfolio.proposals[0].comparison_contract is None
    assert portfolio.validation_plans[0].physical.applicability == "not_applicable"


def test_engineering_portfolio_rejects_scientific_claim_fields() -> None:
    value = _engineering_portfolio()
    value["selected_hypothesis_keys"] = ["unreviewed_physics"]

    with pytest.raises(ValidationError, match="cannot select scientific hypotheses"):
        _validate(value)


def test_engineering_context_profile_is_explicit_and_bounded() -> None:
    policy = EXPERIMENT_DESIGN_CONTEXT_POLICIES.profiles[
        "scidiscovery.experiment-design.engineering.v1"
    ]

    assert tuple(rule.source_name for rule in policy.rules) == (
        "diagnosis",
        "project_review",
        "project",
        "scientific_foundation",
    )
    assert policy.max_inputs == 4


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda value: [case.update(scientific_role="perturbation") for case in value["proposals"][0]["cases"]],
            "baseline or control",
        ),
        (
            lambda value: value["proposals"][0]["cases"][0]["settings"][0].update(name="unknown"),
            "undeclared factor",
        ),
        (
            lambda value: value["proposals"][0]["resource_estimate"].update(case_count=3),
            "case_count must equal",
        ),
        (
            lambda value: value["proposals"][0]["comparison_contract"]["variables"][1]["expectations"][1].update(value="mesh_v2"),
            "frozen variable",
        ),
        (
            lambda value: value["proposals"][0]["comparison_contract"]["identifiability_claims"].clear(),
            "at least 1 item",
        ),
        (
            lambda value: value.update(validation_plans=[]),
            "at least 1 item",
        ),
        (
            lambda value: value["validation_plans"][0]["physical"].update(applicability="not_applicable"),
            "not_applicable validation dimension cannot contain checks",
        ),
    ],
)
def test_experiment_portfolio_rejects_uncontrolled_or_unvalidated_design(
    mutation, message
) -> None:
    value = _portfolio()
    mutation(value)
    with pytest.raises(ValidationError, match=message):
        _validate(value)


def test_priority_order_must_follow_deterministic_value_score() -> None:
    value = _portfolio()
    value["proposals"].append(
        _proposal("low_information", information_gain="low", cost="high")
    )
    value["validation_plans"].append(_plan("low_information"))
    value["priority_order"] = ["low_information", "complete_vs_uniform_field"]
    with pytest.raises(ValidationError, match="non-increasing"):
        _validate(value)


def test_experiment_designer_receives_exact_specialized_schema(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    runtime = open_runtime(
        project_root=project,
        state_root=tmp_path / "state",
        task_token_secret=os.urandom(32),
        approval_receipt_secret=os.urandom(32),
    )
    root = RootMCPRouter(
        RootToolFacade(
            runtime.artifacts,
            runtime.intake,
            tasks=runtime.tasks,
            approvals=runtime.approvals,
            executions=runtime.executions,
            bindings=runtime.scheduler_bindings,
            instance="test",
        )
    )
    for name, kind, schema in (
        (
            "hypothesis_portfolio",
            "hypothesis_portfolio",
            "scidiscovery.hypothesis-proposal.v1",
        ),
        (
            "candidate_eligibility",
            "candidate_eligibility",
            "scidiscovery.candidate-eligibility.v1",
        ),
    ):
        envelope = runtime.artifacts.register(
            b"{}",
            ArtifactRegistration(
                kind=kind,
                schema_id=schema,
                payload_schema_version=1,
                media_type="application/json",
                creator=runtime.actor,
            ),
            idempotency_key=f"experiment-context:{name}",
        )
        runtime.scheduler_bindings.bind(
            instance="test",
            namespace="artifact",
            name=name,
            object_id=envelope.artifact_id,
        )
    with pytest.raises(Exception, match="candidate_eligibility"):
        root.call_tool(
            "task_schedule",
            {
                "name": "unreviewed_experiment_design",
                "role": "experiment_designer",
                "context_profile": "scidiscovery.experiment-design.reviewed.v1",
                "instruction": "Design one bounded test.",
                "inputs": [
                    {
                        "source_name": "hypothesis_portfolio",
                        "artifact_name": "hypothesis_portfolio",
                        "exposure": "full",
                    }
                ],
            },
        )
    task_name = root.call_tool(
        "task_schedule",
        {
            "name": "bounded_experiment_design",
            "role": "experiment_designer",
            "context_profile": "scidiscovery.experiment-design.reviewed.v1",
            "instruction": "Design one bounded test.",
            "inputs": [
                {
                    "source_name": "hypothesis_portfolio",
                    "artifact_name": "hypothesis_portfolio",
                    "exposure": "full",
                },
                {
                    "source_name": "candidate_eligibility",
                    "artifact_name": "candidate_eligibility",
                    "exposure": "full",
                },
            ],
        },
    )["name"]
    root.call_tool("task_prepare_dispatch", {"name": task_name, "ttl_seconds": 60})
    worker = WorkerMCPRouter(runtime.tasks, worker_id="experiment_designer")
    worker.call_tool("worker_claim_task", {})
    assignment = worker.call_tool("worker_get_assignment", {})
    schema = assignment["output"]["json_schema"]
    assert schema["title"] == "RoleResultEnvelope[ExperimentPortfolio]"
    assert "validation_plans" in schema["$defs"]["ExperimentPortfolio"]["properties"]
    result = {
        "schema_version": 1,
        "handoff": {"verdict": "pass", "summary": "Design is complete."},
        "payload": deepcopy(_portfolio()),
    }
    assert worker.call_tool(
        "worker_validate_output", {"content": result}
    )["valid"]
