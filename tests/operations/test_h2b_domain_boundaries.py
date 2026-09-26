from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from curve_figure_evidence.plugin import PLUGIN as FIGURE_PLUGIN
from curve_score.schema import (
    CurveExperimentContract,
    validate_curve_experiment_contract,
)
from scidiscovery.artifact_agent.schema.experiment import ExperimentPortfolio
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from table_observation.plugin import PLUGIN as TABLE_PLUGIN
from tcad_artifact.plugin import PLUGIN as TCAD_PLUGIN


def _engineering_plan() -> ExperimentPortfolio:
    return ExperimentPortfolio.model_validate_json(
        canonical_json({
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
        }),
        strict=True,
    )


def _curve_contract() -> CurveExperimentContract:
    axis_x = {"name": "depth", "unit": "um", "scale": "linear"}
    axis_y = {"name": "carrier", "unit": "cm^-3", "scale": "log10"}
    return CurveExperimentContract.model_validate_json(
        canonical_json({
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
        }),
        strict=True,
    )


def test_curve_contract_binds_generic_checks_without_core_fields() -> None:
    plan = _engineering_plan()
    contract = _curve_contract()
    assert validate_curve_experiment_contract(
        contract,
        plan,
        expected_evaluator_profile="scidiscovery.curve-score.v1",
    ) == ("profile_rms",)
    assert "curve_comparison_spec" not in plan.model_dump(mode="json")["proposals"][0]


def test_install_combinations_compile_without_reverse_dependency() -> None:
    base = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN))
    curve = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN))
    figure = compile_catalog(
        (CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, FIGURE_PLUGIN)
    )
    table = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, TABLE_PLUGIN))
    full = compile_catalog(
        (CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN)
    )
    assert set(base.operation_ids()) < set(curve.operation_ids())
    assert set(base.operation_ids()) < set(table.operation_ids())
    assert "science.evidence.extract.figure.v3" not in base.operation_ids()
    assert "science.evidence.extract.figure.v3" not in curve.operation_ids()
    assert "science.evidence.extract.figure.v3" in figure.operation_ids()
    assert "tcad.study.execute" not in curve.operation_ids()
    assert "science.table.observation.analyze.v1" in table.operation_ids()
    assert "tcad.curve-bundle.sprocess-plx.v1" in full.operation_ids()
    assert "tcad_artifact" not in {
        item.plugin_id for item in CURVE_PLUGIN.dependencies
    }
    assert {item.plugin_id for item in FIGURE_PLUGIN.dependencies} == {
        "builtin",
        "general_science",
        "curve_score",
    }
