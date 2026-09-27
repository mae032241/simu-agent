from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from curve_score.analysis import (
    CurveDiagnosticAnalysisPackage,
    validate_curve_error_plot_collection,
)
from curve_score.curve_contract_compiler import (
    CURVE_CONTRACT_COMPILER_TOOL,
    CurveContractCompileInput,
    compile_curve_contract,
    validate_compiled_curve_contract,
)
from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from curve_score.objective import evaluate_objective_coverage
from curve_score.schema import (
    CurveBundle,
    CurveExperimentContract,
    evaluate_curve_consistency,
    validate_curve_experiment_contract,
)
from curve_score.science_operations import Components, Resources, _validate_diagnosis_against
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.operation_tool_context import OperationToolContext
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json, canonical_sha256
from scidiscovery.artifact_agent.schema.experiment import ExperimentPortfolio
from scidiscovery.artifact_agent.schema.layered_diagnosis import LayeredDiagnosisReport
from scidiscovery.artifact_agent.schema.research_objective import (
    ResearchObjectiveContract,
)
from scidiscovery.artifact_agent.schema.role_result import parse_role_result
from scidiscovery.artifact_agent.service.local_workspace import LocalTrustedBackend
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.tooling import operation_local_worker_tool_names
from scidiscovery.operation_contract import SemanticRuleViolation




def _plan() -> ExperimentPortfolio:
    return ExperimentPortfolio.model_validate_json(
        canonical_json(
            {
                "study_kind": "engineering",
                "objective": "Check one bounded implementation curve.",
                "proposals": [
                    {
                        "experiment_key": "implementation_check",
                        "objectives": ["Check one bounded implementation curve."],
                        "current_objectives": ["Check one bounded implementation curve."],
                        "frozen_invariants": ["same implementation"],
                        "cases": [
                            {
                                "case_key": "baseline",
                                "scientific_role": "baseline",
                                "purpose": "Supply one bounded implementation output.",
                            }
                        ],
                        "required_observables": ["carrier profile"],
                        "resource_estimate": {
                            "case_count": 1,
                            "relative_cost": "low",
                            "runtime_basis": "One bounded case.",
                        },
                        "stop_conditions": ["The declared check is evaluated."],
                        "value_assessment": {
                            "evidence_support": "medium",
                            "discrimination_power": "low",
                            "information_gain": "medium",
                            "cost": "low",
                            "added_free_parameters": 0,
                            "rationale": "A small engineering check.",
                        },
                    }
                ],
                "validation_plans": [
                    {
                        "plan_key": "validate_implementation",
                        "experiment_key": "implementation_check",
                        "numerical": {
                            "applicability": "required",
                            "rationale": "The curve difference is deterministic.",
                            "checks": [
                                {
                                    "check_key": "profile_rms",
                                    "observable": "carrier profile",
                                    "metric": "Log residual RMS.",
                                    "evaluation_mode": "deterministic_threshold",
                                    "evaluator_profile": "scidiscovery.curve-score.v1",
                                    "evaluator_metric": "residual_rms",
                                    "threshold": {
                                        "operator": "le",
                                        "value": 0.2,
                                        "unit": "decade",
                                    },
                                    "acceptance_condition": "RMS is at most 0.2 decade.",
                                    "failure_action": "Inspect the implementation.",
                                    "basis": "Bounded smoke criterion.",
                                }
                            ],
                        },
                        "physical": {
                            "applicability": "not_applicable",
                            "rationale": "Engineering-only check.",
                        },
                        "experimental": {
                            "applicability": "not_applicable",
                            "rationale": "Engineering-only check.",
                        },
                    }
                ],
                "priority_order": ["implementation_check"],
                "priority_rationale": "Only one bounded experiment exists.",
            }
        ),
        strict=True,
    )


def _contract() -> CurveExperimentContract:
    axis_x = {"name": "depth", "unit": "um", "scale": "linear"}
    axis_y = {"name": "carrier", "unit": "cm^-3", "scale": "log10"}
    return CurveExperimentContract.model_validate_json(
        canonical_json(
            {
                "experiment_key": "implementation_check",
                "comparison_spec": {
                    "spec_key": "implementation_curve",
                    "series_declarations": [
                        {
                            "series_key": "reference",
                            "case_key": "baseline",
                            "role": "reference",
                            "scientific_role": "diagnostic_series",
                            "source": "solver_output",
                            "x_axis": axis_x,
                            "y_axis": axis_y,
                        },
                        {
                            "series_key": "candidate",
                            "case_key": "baseline",
                            "role": "candidate",
                            "scientific_role": "numerical_variant",
                            "source": "solver_output",
                            "x_axis": axis_x,
                            "y_axis": axis_y,
                        },
                    ],
                    "comparisons": [
                        {
                            "comparison_key": "implementation_residual",
                            "reference_series": "reference",
                            "candidate_series": "candidate",
                            "domain": {
                                "start": 0.0,
                                "stop": 1.0,
                                "unit": "um",
                                "min_points": 2,
                            },
                            "interpolation": "log10_y",
                            "operators": [
                                {
                                    "operator_key": "profile_rms_operator",
                                    "validation_check_key": "profile_rms",
                                    "kind": "residual_rms",
                                    "value_space": "log10",
                                    "threshold": {
                                        "comparison": "le",
                                        "value": 0.2,
                                        "unit": "decade",
                                    },
                                }
                            ],
                            "purpose": "implementation_sanity",
                            "gate_scope": "numerical_qualification",
                            "metric_profile": "smooth_curve",
                        }
                    ],
                },
            }
        ),
        strict=True,
    )


def _plan_with_non_curve_check() -> ExperimentPortfolio:
    value = _plan().model_dump(mode="json")
    value["validation_plans"][0]["numerical"]["checks"].append(
        {
            "check_key": "mass_balance",
            "observable": "Integrated storage and boundary flux.",
            "metric": "Relative mass-balance error.",
            "evaluation_mode": "deterministic_threshold",
            "evaluator_profile": "tcad.mass-balance.v1",
            "evaluator_metric": "relative_mass_balance_error",
            "threshold": {
                "operator": "le",
                "value": 0.001,
                "unit": "dimensionless",
            },
            "acceptance_condition": "Relative error is at most 0.001.",
            "failure_action": "Inspect solver conservation outputs.",
            "basis": "The solver check is not a curve operator.",
        }
    )
    return ExperimentPortfolio.model_validate_json(canonical_json(value), strict=True)


def _compiler_plan() -> ExperimentPortfolio:
    value = _plan().model_dump(mode="json")
    value["study_kind"] = "scientific"
    value["objective_key"] = "objective_implementation"
    value["selected_hypothesis_keys"] = ["hypothesis_implementation"]
    proposal = value["proposals"][0]
    proposal["hypothesis_keys"] = ["hypothesis_implementation"]
    proposal["changed_factors"] = [
        {
            "name": "implementation_factor",
            "factor_type": "physical",
            "values": [0, 1],
            "unit": "1",
            "rationale": "One bounded comparison factor.",
        }
    ]
    proposal["cases"] = [
        {
            "case_key": "baseline",
            "scientific_role": "baseline",
            "settings": [
                {"name": "implementation_factor", "value": 0, "unit": "1"}
            ],
            "purpose": "Supply the baseline curve.",
        },
        {
            "case_key": "perturbation",
            "scientific_role": "perturbation",
            "settings": [
                {"name": "implementation_factor", "value": 1, "unit": "1"}
            ],
            "purpose": "Supply the bounded comparison curve.",
        },
    ]
    proposal["comparison_contract"] = {
        "baseline_case_key": "baseline",
        "comparison_case_keys": ["perturbation"],
        "variables": [
            {
                "variable_key": "implementation_factor",
                "scientific_path": "implementation.factor",
                "factor_type": "physical",
                "comparison_role": "intended_change",
                "unit": "1",
                "expectations": [
                    {"case_key": "baseline", "value": 0},
                    {"case_key": "perturbation", "value": 1},
                ],
                "equivalence_rule": "exact",
                "rationale": "The factor distinguishes the two cases.",
            }
        ],
        "required_observables": ["carrier profile"],
        "identifiability_claims": [
            {
                "hypothesis_key": "hypothesis_implementation",
                "observable": "carrier profile",
                "distinguishing_outcome": "The bounded curves differ.",
                "decision_rule": "Compare the exact curves.",
                "ambiguity_conditions": ["Either curve is unavailable."],
                "smallest_resolving_control": "Repeat the unavailable case.",
            }
        ],
    }
    proposal["prediction_tests"] = [
        {
            "hypothesis_key": "hypothesis_implementation",
            "prediction_key": "prediction_implementation",
            "observable": "carrier profile",
            "expected_result": "The curves differ.",
            "falsifying_result": "The curves do not differ.",
        }
    ]
    proposal["resource_estimate"]["case_count"] = 2
    return ExperimentPortfolio.model_validate_json(canonical_json(value), strict=True)


def _compiler_objective() -> ResearchObjectiveContract:
    return ResearchObjectiveContract.model_validate_json(
        canonical_json(
            {
                "objective_key": "objective_implementation",
                "intent": "external_reproduction",
                "statement": "Compare one bounded implementation curve.",
                "mandatory_targets": [
                    {
                        "target_key": "target_implementation",
                        "observable": "carrier profile",
                        "support_requirement": "qualified_subset",
                        "evidence_item_keys": ["evidence_curve"],
                        "rationale": "The exact reference curve is supplied.",
                    }
                ],
                "closure_requirements": [
                    {
                        "requirement_key": "cover_target",
                        "description": "Cover the supplied reference target.",
                        "target_keys": ["target_implementation"],
                    }
                ],
            }
        ),
        strict=True,
    )


def _bundle() -> CurveBundle:
    axis_x = {"name": "depth", "unit": "um", "scale": "linear"}
    axis_y = {"name": "carrier", "unit": "cm^-3", "scale": "log10"}
    common = {
        "case_key": "baseline",
        "x_axis": axis_x,
        "y_axis": axis_y,
        "availability": {"status": "available", "rationale": "Fixture curve."},
    }
    return CurveBundle.model_validate_json(
        canonical_json(
            {
                "source_profile": "fixture",
                "source_digests": ["1" * 64],
                "series": [
                    {
                        **common,
                        "series_key": "reference",
                        "role": "reference",
                        "scientific_role": "diagnostic_series",
                        "points": [
                            {"x": 0.0, "y": 1e10},
                            {"x": 0.5, "y": 1e11},
                            {"x": 1.0, "y": 1e12},
                        ],
                        "source_locator": "fixture:reference",
                    },
                    {
                        **common,
                        "series_key": "candidate",
                        "role": "candidate",
                        "scientific_role": "numerical_variant",
                        "points": [
                            {"x": 0.0, "y": 1e10},
                            {"x": 0.5, "y": 1e13},
                            {"x": 1.0, "y": 1e12},
                        ],
                        "source_locator": "fixture:candidate",
                    },
                ],
            }
        ),
        strict=True,
    )


def _inputs() -> dict[str, bytes]:
    plan = _plan()
    contract = _contract()
    bundle = _bundle()
    report = evaluate_curve_consistency(
        bundle,
        contract.comparison_spec,
        validation_plan_sha256=canonical_sha256(plan.validation_plans[0]),
        covered_validation_check_keys=("profile_rms",),
    )
    assert report.aggregate_status == "fail"
    return {
        "experiment_plan": plan.canonical_json(),
        "experiment_review": b"{}",
        "curve_contract": contract.canonical_json(),
        "curve_contract_review": b"{}",
        "metric_report": report.canonical_json(),
        "curve_bundle": bundle.canonical_json(),
    }


def _diagnosis() -> LayeredDiagnosisReport:
    evidence = [
        {
            "source_key": "metric_report",
            "source_type": "runtime_output",
            "title": "Deterministic curve metric",
            "locator": "curve_analysis_package:/metric_report",
        }
    ]
    passed = {
        "status": "pass",
        "summary": "The exact packaged evidence is usable.",
        "evidence_keys": ["metric_report"],
    }
    blocked = {
        "status": "not_evaluable",
        "summary": "Blocked by the failed numerical prerequisite.",
    }
    return LayeredDiagnosisReport.model_validate_json(
        canonical_json(
            {
                "study_kind": "engineering",
                "experiment_key": "implementation_check",
                "plan_key": "validate_implementation",
                "summary": "The deterministic residual threshold failed.",
                "evidence": evidence,
                "source_references": [{"source_key": "metric_report", "input_alias": "curve_analysis_package"}],
                "gates": {
                    "evidence_identity": passed,
                    "implementation_fidelity": passed,
                    "numerical_validity": {
                        "status": "fail",
                        "summary": "The residual RMS exceeds its frozen threshold.",
                        "evidence_keys": ["metric_report"],
                    },
                    "control_equivalence": blocked,
                    "observation": blocked,
                    "physical_interpretation": blocked,
                },
                "overall_verdict": "invalid_study",
                "claim_allowed": False,
                "remaining_contradiction": "The implementation mismatch remains localized but unexplained.",
                "next_action": "Revise one bounded implementation hypothesis.",
            }
        ),
        strict=True,
    )


def _passing_diagnosis() -> LayeredDiagnosisReport:
    evidence = [
        {
            "source_key": "metric_report",
            "source_type": "runtime_output",
            "title": "Deterministic curve metric",
            "locator": "metric_report",
        }
    ]
    passed = {
        "status": "pass",
        "summary": "The supplied check passed.",
        "evidence_keys": ["metric_report"],
    }
    return LayeredDiagnosisReport.model_validate_json(
        canonical_json(
            {
                "study_kind": "engineering",
                "experiment_key": "implementation_check",
                "plan_key": "validate_implementation",
                "summary": "The supplied curve check passed.",
                "evidence": evidence,
                "gates": {
                    "evidence_identity": passed,
                    "implementation_fidelity": passed,
                    "numerical_validity": passed,
                    "control_equivalence": passed,
                    "observation": passed,
                    "physical_interpretation": {
                        "status": "not_applicable",
                        "summary": "Engineering check.",
                    },
                },
                "overall_verdict": "pass",
                "claim_allowed": False,
                "remaining_contradiction": "No curve mismatch remains.",
                "next_action": "Evaluate the remaining registered checks.",
            }
        ),
        strict=True,
    )


def test_curve_contract_covers_only_its_bound_checks() -> None:
    assert validate_curve_experiment_contract(
        _contract(),
        _plan_with_non_curve_check(),
        expected_evaluator_profile="scidiscovery.curve-score.v1",
    ) == ("profile_rms",)


def test_curve_contract_compiler_owns_mechanical_fields() -> None:
    contract = compile_curve_contract(
        CurveContractCompileInput.model_validate(
            {
                "experiment_key": "implementation_check",
                "target_bindings": [
                    {
                        "target_key": "target_implementation",
                        "reference_series_key": "reference",
                    }
                ],
                "candidate_case_keys": ["baseline"],
                "comparison_metric": "residual_rms",
            }
        ),
        objective=_compiler_objective(),
        portfolio=_compiler_plan(),
        reference_bundle=_bundle(),
    )
    declarations = contract.comparison_spec.series_declarations
    comparison = contract.comparison_spec.comparisons[0]
    assert contract.experiment_key == "implementation_check"
    assert tuple(item.source for item in declarations) == (
        "reference_input",
        "solver_output",
    )
    assert declarations[0].x_axis == _bundle().series[0].x_axis
    assert declarations[1].y_axis == _bundle().series[0].y_axis
    assert comparison.domain.model_dump(include={"start", "stop", "unit"}) == {
        "start": 0.0,
        "stop": 1.0,
        "unit": "um",
    }
    assert comparison.evaluation_points == 3
    assert comparison.operators[0].validation_check_key == "profile_rms"
    assert comparison.operators[0].threshold is not None
    assert comparison.operators[0].threshold.value == 0.2


def test_curve_contract_compiler_adds_the_planned_metric_when_agent_selects_another() -> None:
    plan = _compiler_plan()
    contract = compile_curve_contract(
        CurveContractCompileInput.model_validate(
            {
                "experiment_key": "implementation_check",
                "target_bindings": [
                    {
                        "target_key": "target_implementation",
                        "reference_series_key": "reference",
                    }
                ],
                "candidate_case_keys": ["baseline"],
                "comparison_metric": "residual_max_abs",
            }
        ),
        objective=_compiler_objective(),
        portfolio=plan,
        reference_bundle=_bundle(),
    )
    operators = contract.comparison_spec.comparisons[0].operators
    assert tuple(item.kind for item in operators) == (
        "residual_max_abs",
        "residual_rms",
    )
    assert operators[0].validation_check_key is None
    assert operators[1].validation_check_key == "profile_rms"
    assert operators[1].threshold is not None
    assert operators[1].threshold.value == 0.2
    assert validate_curve_experiment_contract(
        contract,
        plan,
        expected_evaluator_profile="scidiscovery.curve-score.v1",
    ) == ("profile_rms",)


def test_curve_contract_compiler_uses_explicit_check_target_binding() -> None:
    plan_value = _compiler_plan().model_dump(mode="json")
    plan_value["validation_plans"][0]["numerical"]["checks"][0]["observable"] = (
        "Equivalent curve-fit intent expressed with different wording."
    )
    plan = ExperimentPortfolio.model_validate_json(
        canonical_json(plan_value), strict=True
    )
    contract = compile_curve_contract(
        CurveContractCompileInput.model_validate(
            {
                "experiment_key": "implementation_check",
                "target_bindings": [
                    {
                        "target_key": "target_implementation",
                        "reference_series_key": "reference",
                        "validation_check_keys": ["profile_rms"],
                    }
                ],
                "candidate_case_keys": ["baseline"],
                "comparison_metric": "residual_rms",
            }
        ),
        objective=_compiler_objective(),
        portfolio=plan,
        reference_bundle=_bundle(),
    )
    operator = contract.comparison_spec.comparisons[0].operators[0]
    assert operator.validation_check_key == "profile_rms"
    assert operator.threshold is not None
    assert operator.threshold.value == 0.2
    validate_compiled_curve_contract(
        contract,
        objective=_compiler_objective(),
        portfolio=plan,
        reference_bundle=_bundle(),
    )


def test_curve_contract_compiler_applies_a_plan_check_to_multiple_curves() -> None:
    plan = _compiler_plan()
    contract = compile_curve_contract(
        CurveContractCompileInput.model_validate(
            {
                "experiment_key": "implementation_check",
                "target_bindings": [
                    {
                        "target_key": "target_implementation",
                        "reference_series_key": "reference",
                    }
                ],
                "candidate_case_keys": ["baseline", "perturbation"],
                "comparison_metric": "residual_rms",
            }
        ),
        objective=_compiler_objective(),
        portfolio=plan,
        reference_bundle=_bundle(),
    )
    assert len(contract.comparison_spec.comparisons) == 2
    for comparison in contract.comparison_spec.comparisons:
        assert tuple(
            item.validation_check_key for item in comparison.operators
        ) == ("profile_rms",)
        assert comparison.operators[0].threshold is not None
        assert comparison.operators[0].threshold.value == 0.2
    assert validate_curve_experiment_contract(
        contract,
        plan,
        expected_evaluator_profile="scidiscovery.curve-score.v1",
    ) == ("profile_rms",)
    bundle_value = _bundle().model_dump(mode="json")
    reference = bundle_value["series"][0]
    bundle_value["series"] = [
        reference,
        *(
            {
                **reference,
                "series_key": declaration.series_key,
                "case_key": declaration.case_key,
                "role": declaration.role,
                "scientific_role": "simulation_candidate",
                "source_locator": f"fixture:{declaration.case_key}",
            }
            for declaration in contract.comparison_spec.series_declarations
            if declaration.source == "solver_output"
        ),
    ]
    report = evaluate_curve_consistency(
        CurveBundle.model_validate_json(canonical_json(bundle_value), strict=True),
        contract.comparison_spec,
        validation_plan_sha256=canonical_sha256(plan.validation_plans[0]),
        covered_validation_check_keys=("profile_rms",),
    )
    assert len(report.comparisons) == 2
    assert report.aggregate_status == "pass"


def test_curve_contract_compiler_preserves_checks_that_share_one_metric() -> None:
    plan_value = _compiler_plan().model_dump(mode="json")
    checks = plan_value["validation_plans"][0]["numerical"]["checks"]
    strict_check = {**checks[0], "check_key": "profile_rms_strict"}
    strict_check["threshold"] = {
        **checks[0]["threshold"],
        "value": 0.1,
    }
    strict_check["acceptance_condition"] = "RMS is at most 0.1 decade."
    checks.append(strict_check)
    plan = ExperimentPortfolio.model_validate_json(
        canonical_json(plan_value), strict=True
    )
    contract = compile_curve_contract(
        CurveContractCompileInput.model_validate(
            {
                "experiment_key": "implementation_check",
                "target_bindings": [
                    {
                        "target_key": "target_implementation",
                        "reference_series_key": "reference",
                    }
                ],
                "candidate_case_keys": ["baseline"],
                "comparison_metric": "residual_rms",
            }
        ),
        objective=_compiler_objective(),
        portfolio=plan,
        reference_bundle=_bundle(),
    )
    operators = contract.comparison_spec.comparisons[0].operators
    assert tuple(item.validation_check_key for item in operators) == (
        "profile_rms",
        "profile_rms_strict",
    )
    assert tuple(item.threshold.value for item in operators if item.threshold) == (
        0.2,
        0.1,
    )
    assert validate_curve_experiment_contract(
        contract,
        plan,
        expected_evaluator_profile="scidiscovery.curve-score.v1",
    ) == ("profile_rms", "profile_rms_strict")


def test_curve_contract_context_rejects_manual_mechanical_changes() -> None:
    objective = _compiler_objective()
    plan = _compiler_plan()
    bundle = _bundle()
    contract = compile_curve_contract(
        CurveContractCompileInput.model_validate(
            {
                "experiment_key": "implementation_check",
                "target_bindings": [
                    {
                        "target_key": "target_implementation",
                        "reference_series_key": "reference",
                    }
                ],
                "candidate_case_keys": ["baseline"],
                "comparison_metric": "residual_rms",
            }
        ),
        objective=objective,
        portfolio=plan,
        reference_bundle=bundle,
    )
    comparison = contract.comparison_spec.comparisons[0].model_copy(
        update={"evaluation_points": 17}
    )
    changed = contract.model_copy(
        update={
            "comparison_spec": contract.comparison_spec.model_copy(
                update={"comparisons": (comparison,)}
            )
        }
    )
    with pytest.raises(
        SemanticRuleViolation,
        match="mechanical fields differ from deterministic compilation",
    ):
        validate_compiled_curve_contract(
            changed,
            objective=objective,
            portfolio=plan,
            reference_bundle=bundle,
        )


def test_curve_contract_compiler_preserves_reference_gaps() -> None:
    plan = _compiler_plan()
    bundle_value = _bundle().model_dump(mode="json")
    bundle_value["series"][0]["points"] = [
        {"x": 0.0, "y": 1e10},
        {"x": 0.4, "y": 1e11},
        {"x": 0.6, "y": 1e11},
        {"x": 1.0, "y": 1e12},
    ]
    bundle_value["series"][0]["valid_intervals"] = [
        {"start": 0.0, "stop": 1.0}
    ]
    bundle_value["series"][0]["exclusions"] = [
        {"start": 0.4, "stop": 0.6}
    ]
    contract = compile_curve_contract(
        CurveContractCompileInput.model_validate(
            {
                "experiment_key": "implementation_check",
                "target_bindings": [
                    {
                        "target_key": "target_implementation",
                        "reference_series_key": "reference",
                    }
                ],
                "candidate_case_keys": ["baseline"],
                "comparison_metric": "residual_rms",
            }
        ),
        objective=_compiler_objective(),
        portfolio=plan,
        reference_bundle=CurveBundle.model_validate_json(
            canonical_json(bundle_value), strict=True
        ),
    )
    assert tuple(
        (item.domain.start, item.domain.stop, item.evaluation_points)
        for item in contract.comparison_spec.comparisons
    ) == ((0.0, 0.4, 2), (0.6, 1.0, 2))


def test_curve_contract_compiler_respects_exclusions_without_valid_intervals() -> None:
    plan = _compiler_plan()
    bundle_value = _bundle().model_dump(mode="json")
    bundle_value["series"][0]["points"] = [
        {"x": 0.0, "y": 1e10},
        {"x": 0.4, "y": 1e11},
        {"x": 0.6, "y": 1e11},
        {"x": 1.0, "y": 1e12},
    ]
    bundle_value["series"][0]["exclusions"] = [
        {"start": 0.4, "stop": 0.6}
    ]
    contract = compile_curve_contract(
        CurveContractCompileInput.model_validate(
            {
                "experiment_key": "implementation_check",
                "target_bindings": [
                    {
                        "target_key": "target_implementation",
                        "reference_series_key": "reference",
                    }
                ],
                "candidate_case_keys": ["baseline"],
                "comparison_metric": "residual_rms",
            }
        ),
        objective=_compiler_objective(),
        portfolio=plan,
        reference_bundle=CurveBundle.model_validate_json(
            canonical_json(bundle_value), strict=True
        ),
    )
    assert tuple(
        (item.domain.start, item.domain.stop, item.evaluation_points)
        for item in contract.comparison_spec.comparisons
    ) == ((0.0, 0.4, 2), (0.6, 1.0, 2))




@pytest.mark.parametrize(
    ("defect", "message"),
    (
        ("unknown_target", "unknown objective target_key"),
        ("unplanned_observable", "did not bind every curve-score validation check"),
        ("unknown_reference", "missing reference series"),
        ("unknown_case", "unknown experiment case"),
        ("unknown_check", "must cover every curve-score validation check"),
        ("unbound_current_check", "did not bind every curve-score validation check"),
    ),
)
def test_partial_curve_scope_keeps_exact_binding_checks(defect, message) -> None:
    objective = _compiler_objective()
    target = objective.mandatory_targets[0].model_copy(
        update={"target_key": "future_target"}
    )
    if defect == "unplanned_observable":
        target = target.model_copy(update={"observable": "future response"})
    objective = objective.model_copy(
        update={"mandatory_targets": (*objective.mandatory_targets, target)}
    )
    binding = {"target_key": "target_implementation", "reference_series_key": "reference"}
    cases = ["baseline"]
    plan = _compiler_plan()
    if defect == "unknown_target":
        binding["target_key"] = "absent_target"
    elif defect == "unplanned_observable":
        binding["target_key"] = "future_target"
    elif defect == "unknown_reference":
        binding["reference_series_key"] = "absent_reference"
    elif defect == "unknown_case":
        cases = ["absent_case"]
    elif defect == "unknown_check":
        binding["validation_check_keys"] = ["absent_check"]
    elif defect == "unbound_current_check":
        value = plan.model_dump(mode="json")
        proposal = value["proposals"][0]
        proposal["required_observables"].append("required secondary response")
        proposal["comparison_contract"]["required_observables"].append("required secondary response")
        checks = value["validation_plans"][0]["numerical"]["checks"]
        checks.append({**checks[0], "check_key": "secondary_check", "observable": "required secondary response"})
        plan = ExperimentPortfolio.model_validate_json(canonical_json(value), strict=True)
    request = CurveContractCompileInput.model_validate(
        {
            "experiment_key": "implementation_check",
            "target_bindings": [binding],
            "candidate_case_keys": cases,
            "comparison_metric": "residual_rms",
        }
    )
    with pytest.raises(SemanticRuleViolation, match=message):
        compile_curve_contract(
            request, objective=objective, portfolio=plan, reference_bundle=_bundle()
        )


@pytest.mark.parametrize("check_keys", ([], ["absent_check"], ["profile_rms"]))
def test_curve_contract_without_eligible_checks_rejects_explicit_check_bindings(check_keys) -> None:
    value = _compiler_plan().model_dump(mode="json")
    value["validation_plans"][0]["numerical"]["checks"][0]["evaluator_profile"] = "example.other-score.v1"
    plan = ExperimentPortfolio.model_validate_json(canonical_json(value), strict=True)
    request = CurveContractCompileInput.model_validate({
        "experiment_key": "implementation_check",
        "target_bindings": [{"target_key": "target_implementation", "reference_series_key": "reference",
                             "validation_check_keys": check_keys}],
        "candidate_case_keys": ["baseline"], "comparison_metric": "residual_rms",
    })
    if check_keys:
        with pytest.raises(SemanticRuleViolation, match="must cover every curve-score validation check"):
            compile_curve_contract(request, objective=_compiler_objective(), portfolio=plan, reference_bundle=_bundle())
    else:
        contract = compile_curve_contract(request, objective=_compiler_objective(), portfolio=plan, reference_bundle=_bundle())
        assert all(operator.validation_check_key is None
                   for comparison in contract.comparison_spec.comparisons for operator in comparison.operators)




def test_legacy_curve_diagnosis_accepts_exact_partial_curve_coverage() -> None:
    plan = _plan_with_non_curve_check()
    contract = _contract()
    report = evaluate_curve_consistency(
        _bundle(),
        contract.comparison_spec,
        validation_plan_sha256=canonical_sha256(plan.validation_plans[0]),
        covered_validation_check_keys=("profile_rms",),
    )
    _validate_diagnosis_against(_diagnosis(), plan, contract, report)


def test_legacy_curve_diagnosis_does_not_derive_verdict_from_uncovered_checks() -> None:
    plan = _plan_with_non_curve_check()
    contract = _contract()
    report = evaluate_curve_consistency(
        _bundle(),
        contract.comparison_spec,
        validation_plan_sha256=canonical_sha256(plan.validation_plans[0]),
        covered_validation_check_keys=("profile_rms",),
    )
    _validate_diagnosis_against(_passing_diagnosis(), plan, contract, report)
    assert report.covered_validation_check_keys == ("profile_rms",)


def _root(tmp_path: Path):
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN))
    project = tmp_path / "project"
    project.mkdir()
    runtime = open_runtime(
        project_root=project,
        state_root=tmp_path / "state",
        worker_backend="local",
    )
    runtime.runs.operation_catalog = catalog
    instance = runtime.scheduler_bindings.create_instance(
        name="curve_analysis_boundary",
        title="Curve analysis boundary",
        objective="Separate deterministic curve analysis from scientific diagnosis.",
    )
    root = RootMCPRouter(
        RootToolFacade(
            runtime.artifacts,
            runtime.intake,
            runs=runtime.runs,
            approvals=runtime.approvals,
            executions=runtime.executions,
            bindings=runtime.scheduler_bindings,
            instance=instance.instance_id,
            operation_catalog=catalog,
        )
    )
    return catalog, runtime, instance, root


def _register_inputs(runtime, instance, payloads: dict[str, bytes]) -> None:
    schemas = {
        "experiment_plan": "scidiscovery.experiment-portfolio.v1",
        "experiment_review": "scidiscovery.scientific-review.v1",
        "curve_contract": "scidiscovery.curve-experiment-contract.v1",
        "curve_contract_review": "scidiscovery.scientific-review.v1",
        "metric_report": "scidiscovery.curve-consistency-report.v1",
        "curve_bundle": "scidiscovery.curve-bundle.v1",
    }
    for name, content in payloads.items():
        envelope = runtime.artifacts.register(
            content,
            ArtifactRegistration(
                kind=name,
                schema_id=schemas[name],
                payload_schema_version=1,
                media_type="application/json",
                creator=runtime.actor,
                labels={"scientific_claim_admissible": "true"},
            ),
            idempotency_key=f"m2-02:{name}",
        )
        runtime.scheduler_bindings.bind(
            instance=instance.instance_id,
            namespace="artifact",
            name=name,
            object_id=envelope.artifact_id,
        )










def test_obsolete_curve_analysis_worker_tool_is_removed() -> None:
    root = Path(__file__).parents[2]
    assert not (root / "plugins/curve_score/curve_score/worker_tool.py").exists()
    assert all(
        component.component_id != "curve_analyze_tool"
        for component in CURVE_PLUGIN.components
    )
