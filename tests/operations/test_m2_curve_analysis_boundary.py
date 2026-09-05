from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from curve_score.analysis import (
    CurveDiagnosticAnalysisPackage,
    validate_curve_error_plot_collection,
)
from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from curve_score.schema import CurveBundle, CurveExperimentContract, evaluate_curve_consistency
from curve_score.science_operations import Components
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json, canonical_sha256
from scidiscovery.artifact_agent.schema.experiment import ExperimentPortfolio
from scidiscovery.artifact_agent.schema.layered_diagnosis import LayeredDiagnosisReport
from scidiscovery.artifact_agent.service.local_workspace import LocalTrustedBackend
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.tooling import operation_local_worker_tool_names


ANALYZE_OPERATION = "science.curve.error.analyze.v1"
DIAGNOSE_OPERATION = "science.result.diagnose.curve-error.v1"


def _plan() -> ExperimentPortfolio:
    return ExperimentPortfolio.model_validate_json(
        canonical_json(
            {
                "study_kind": "engineering",
                "objective": "Check one bounded implementation curve.",
                "proposals": [
                    {
                        "experiment_key": "implementation_check",
                        "objective": "Check one bounded implementation curve.",
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
            "locator": "curve_analysis_package:metric_report",
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


def _analysis_request() -> dict[str, object]:
    return {
        "name": "curve_error_analysis",
        "operation_id": ANALYZE_OPERATION,
        "inputs": [
            {"port": name, "artifact_names": [name]}
            for name in (
                "experiment_plan",
                "experiment_review",
                "curve_contract",
                "curve_contract_review",
                "metric_report",
                "curve_bundle",
            )
        ],
    }


def test_curve_analysis_transform_and_single_file_agent_complete_real_run(
    tmp_path: Path,
) -> None:
    catalog, runtime, instance, root = _root(tmp_path)
    _register_inputs(runtime, instance, _inputs())
    transform = catalog.operation(ANALYZE_OPERATION)
    agent = catalog.operation(DIAGNOSE_OPERATION)

    assert transform.spec.catalog_scope == "support"
    assert transform.spec.executor.kind == "transform"
    assert tuple(port.name for port in agent.spec.inputs) == (
        "curve_analysis_package",
    )
    assert tuple(port.name for port in agent.spec.outputs) == ("layered_diagnosis",)
    assert LocalTrustedBackend.supports_operation(agent)
    assert "worker_curve_analyze" not in operation_local_worker_tool_names(agent)

    request = _analysis_request()
    first = root.call_tool("operation_invoke", request)
    assert root.call_tool("operation_invoke", request) == first
    outputs = first["result"]["outputs"]
    assert [item["output_label"] for item in outputs] == [
        "primary",
        "curve_analysis_plots_001",
    ]
    package_name = outputs[0]["artifact_name"]
    package_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id,
        namespace="artifact",
        name=package_name,
    )
    package_envelope = runtime.artifacts.get_by_id(package_id)
    package = CurveDiagnosticAnalysisPackage.model_validate_json(
        runtime.artifacts.read(package_envelope.ref), strict=True
    )
    assert len(package.curve_analysis.analyses) == 1
    plot_name = outputs[1]["artifact_name"]
    plot_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id,
        namespace="artifact",
        name=plot_name,
    )
    assert runtime.artifacts.read(
        runtime.artifacts.get_by_id(plot_id).ref
    ).startswith(b"\x89PNG\r\n\x1a\n")

    invoke = {
        "name": "curve_error_diagnosis",
        "operation_id": DIAGNOSE_OPERATION,
        "inputs": [
            {
                "port": "curve_analysis_package",
                "artifact_names": [package_name],
            }
        ],
        "instruction": "Interpret the fixed deterministic curve-error analysis.",
    }
    assert root.call_tool("operation_preflight", invoke)["admissible"] is True
    root.call_tool("operation_invoke", invoke)
    worker = LocalWorkerMCPRouter(
        runtime.runs,
        operation_id=agent.spec.operation_id,
        operation_digest=agent.digest,
    )
    opened = worker.call_tool("worker_open_assignment", {})
    Path(opened["output_directory"], "result.json").write_bytes(
        canonical_json(
            {
                "schema_version": 1,
                "handoff": {
                    "verdict": "blocked",
                    "summary": "The numerical prerequisite failed.",
                },
                "payload": _diagnosis().model_dump(mode="json"),
            }
        )
    )
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    status = next(
        item
        for item in runtime.runs.list(instance_id=instance.instance_id)
        if item.operation_id == DIAGNOSE_OPERATION
    )
    assert status.state == "completed"
    result_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id,
        namespace="artifact",
        name=status.output_binding_name,
    )
    LayeredDiagnosisReport.model_validate_json(
        runtime.artifacts.read(runtime.artifacts.get_by_id(result_id).ref), strict=True
    )


def test_curve_analysis_package_and_plot_bundle_fail_closed_on_tampering() -> None:
    payloads = _inputs()
    artifacts = Components.curve_error_analysis.implementation(
        {name: (content,) for name, content in payloads.items()}
    )
    package_raw = artifacts["curve_analysis_package"][0]
    package = json.loads(package_raw)
    plot = artifacts["curve_analysis_plots"][0]

    plot_name = package["curve_analysis"]["analyses"][0]["plot_item"]
    validate_curve_error_plot_collection(package, {plot_name: plot})
    with pytest.raises(ValueError, match="digest differs"):
        validate_curve_error_plot_collection(package, {plot_name: plot + b"x"})
    package["curve_analysis"]["curve_bundle_sha256"] = "0" * 64
    with pytest.raises(ValidationError, match="reproduce"):
        CurveDiagnosticAnalysisPackage.model_validate_json(
            canonical_json(package), strict=True
        )


def test_obsolete_curve_analysis_worker_tool_is_removed() -> None:
    root = Path(__file__).parents[2]
    assert not (root / "plugins/curve_score/curve_score/worker_tool.py").exists()
    assert all(
        component.component_id != "curve_analyze_tool"
        for component in CURVE_PLUGIN.components
    )
