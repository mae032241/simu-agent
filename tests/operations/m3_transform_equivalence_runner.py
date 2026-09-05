"""Run the frozen M3 transform corpus through one isolated source tree.

This file is a subprocess runner, not a production compatibility layer.  The
pytest wrapper extracts the sealed M2 source oracle and starts this runner once
for M2 and once for M3, then compares the emitted manifests byte for byte.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import importlib
import io
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, __version__ as PILLOW_VERSION

from curve_score.figure_digitization import (
    FigureDigitizationRequest,
    build_digitized_figure_bundle,
)
from curve_score.schema import CurveExperimentContract
from curve_figure_evidence.plugin import PLUGIN as FIGURE_PLUGIN
from ingaas_fig4.plugin import PLUGIN as INGAAS_PLUGIN
from scidiscovery.artifact_agent.interfaces.mcp_root import (
    RootMCPRouter,
    RootToolError,
    RootToolFacade,
)
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.approval import (
    ApprovalOption,
    CompiledApprovalIdentity,
    LocalIdentityRef,
)
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.comparison import RealizationSnapshot
from scidiscovery.artifact_agent.schema.experiment import ComparisonContract
from scidiscovery.artifact_agent.schema.experiment_intent import ExperimentDesignIntent
from scidiscovery.artifact_agent.schema.research_cycle import ScientificIntake
from scidiscovery.artifact_agent.schema.research_objective import ResearchObjectiveContract
from scidiscovery.artifact_agent.schema.scientific_foundation import ScientificFoundation
from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerNameConflict
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from tcad_artifact.device_parameters import evaluate_device_parameter_coverage
from tcad_artifact.execution_control import SolverCapability
from tcad_artifact.plugin import PLUGIN as TCAD_PLUGIN
from tcad_artifact.project_materializer import materialize_deck_project
from tcad_artifact.project_packager import (
    DeckFile,
    DeckProjectDraft,
    ProjectPreflightAttestation,
    ReviewedDeckPackage,
    RuntimeAttestation,
    RuntimeContractCheck,
    RuntimeOutputRecord,
    TCADRuntimeManifest,
)

from tests.operations.test_general_transform_operations import _intake
from tests.operations.test_l4_local_tcad import _portfolio as _tcad_portfolio
from tests.operations.test_m2_curve_analysis_boundary import (
    _bundle as _curve_bundle,
    _contract as _curve_contract,
    _inputs as _curve_analysis_inputs,
    _plan as _curve_plan,
)
from tests.operations.test_m2_parameter_package import _package as _parameter_package
from tests.operations.test_runtime_plugin_configuration import _reviewed_package


@dataclass(frozen=True)
class Datum:
    port: str
    key: str
    content: bytes
    media_type: str | None = None
    parent_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class Scenario:
    operation_id: str
    data: tuple[Datum, ...]
    revision_key: str
    negative_edge: tuple[str, str] | None = None


def _safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", value)


def _project_research_objective(raw: bytes) -> bytes:
    foundation = ScientificFoundation.model_validate_json(raw, strict=True)
    if foundation.objective_contract is None:
        raise ValueError("objective fixture requires an explicit objective contract")
    return foundation.objective_contract.canonical_json()


def _review() -> bytes:
    return canonical_json(
        {
            "review_target": "domain_contract",
            "verdict": "pass",
            "summary": "The frozen deterministic fixture is internally consistent.",
        }
    )


def _evidence_audit() -> bytes:
    return canonical_json({"schema_version": 1, "checks": [], "evidence": []})


def _engineering_intent() -> bytes:
    return ExperimentDesignIntent.model_validate_json(
        canonical_json(
            {
                "study_kind": "engineering",
                "engineering_objective": "Verify one bounded analysis.",
                "proposals": [
                    {
                        "experiment_key": "engineering_smoke",
                        "frozen_invariants": ["same fixture"],
                        "cases": [
                            {
                                "case_key": "baseline",
                                "scientific_role": "baseline",
                                "purpose": "Run one fixed case.",
                            }
                        ],
                        "required_observables": ["terminal state"],
                        "validation_intent": {
                            "numerical": {
                                "rationale": "Check completion.",
                                "reviewed_checks": [
                                    {
                                        "observable": "terminal state",
                                        "metric": "clean completion",
                                        "acceptance_condition": "The run completes.",
                                        "failure_action": "Reject the implementation.",
                                        "basis": "Engineering smoke contract.",
                                    }
                                ],
                            },
                            "physical": {"rationale": "No physical claim."},
                            "experimental": {"rationale": "No wet experiment."},
                        },
                        "resource_estimate": {
                            "relative_cost": "low",
                            "runtime_basis": "One bounded case.",
                        },
                        "stop_conditions": ["Stop after completion."],
                        "value_assessment": {
                            "evidence_support": "high",
                            "discrimination_power": "low",
                            "information_gain": "medium",
                            "cost": "low",
                            "added_free_parameters": 0,
                            "rationale": "Close one implementation invariant.",
                        },
                    }
                ],
                "priority_order": ["engineering_smoke"],
                "priority_rationale": "Only one case exists.",
            }
        ),
        strict=True,
    ).canonical_json()


def _hypothesis() -> bytes:
    return canonical_json(
        {
            "schema_version": 2,
            "research_objective_key": "objective",
            "stage_objective": "Explain one bounded mismatch.",
            "contradiction": "The candidate differs from the reference.",
            "evidence": [
                {
                    "source_key": "source",
                    "source_type": "frozen_input",
                    "locator": "fixture",
                }
            ],
            "hypotheses": [
                {
                    "hypothesis_key": "implementation_error",
                    "statement": "The implementation differs.",
                    "mechanism": "A bounded code path changes the curve.",
                    "scope": "Fixture only.",
                    "predictions": [
                        {
                            "prediction_key": "curve_shift",
                            "observable": "carrier profile",
                            "expected_outcome": "The residual is nonzero.",
                        }
                    ],
                    "falsifiers": [
                        {
                            "falsifier_key": "exact_match",
                            "observable": "carrier profile",
                            "rejection_condition": "The curves match.",
                        }
                    ],
                    "evidence_keys": ["source"],
                }
            ],
        }
    )


def _figure_payloads() -> tuple[bytes, bytes, bytes]:
    image = Image.new("RGB", (12, 12), "white")
    for x in range(1, 10):
        image.putpixel((x, 10 - x), (255, 0, 0))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    source = stream.getvalue()
    canonical_stream = io.BytesIO()
    image.convert("RGB").save(
        canonical_stream, format="PNG", optimize=False, compress_level=9
    )
    recovered = canonical_stream.getvalue()
    new_source_contract = "source" in FigureDigitizationRequest.model_fields
    e2_contract = "plot_bbox" in FigureDigitizationRequest.model_fields
    request = canonical_json(
        {
            "schema_version": (
                "scidiscovery.curve-figure-digitization-request.v2"
                if new_source_contract
                else "scidiscovery.curve-figure-digitization-request.v1"
            ),
            "figure_key": "bounded_figure",
            "panel_key": "main",
            "figure": "Fig. 1",
            "citation": "Fig. 1",
            **(
                {
                    "source": {
                        "source_kind": "raster_image",
                        "media_type": "image/png",
                        "source_sha256": hashlib.sha256(source).hexdigest(),
                        "recovered_image_sha256": hashlib.sha256(recovered).hexdigest(),
                        "width": image.width,
                        "height": image.height,
                        **(
                            {
                                "recovery_tool": "Pillow",
                                "recovery_tool_version": PILLOW_VERSION,
                            }
                            if e2_contract
                            else {}
                        ),
                    }
                }
                if new_source_contract
                else {"page": 1}
            ),
            **({"plot_bbox": [1, 1, 10, 10]} if e2_contract else {}),
            "axis_calibration": {
                "x": {
                    "scale": "linear",
                    "unit": "um",
                    "pixel_min": 1.0,
                    "pixel_max": 9.0,
                    "value_min": 0.0,
                    "value_max": 8.0,
                    "reprojection_error_px": 0.0,
                },
                "y": {
                    "scale": "linear",
                    "unit": "cm^-3",
                    "pixel_min": 9.0,
                    "pixel_max": 1.0,
                    "value_min": 1.0,
                    "value_max": 9.0,
                    "reprojection_error_px": 0.0,
                },
            },
            "series": [
                {
                    "series_key": "reference",
                    "label": "Reference",
                    "color": "#ff0000",
                    "color_tolerance": 0.0,
                    "line_style": "solid",
                    "binding_source": "legend",
                    "visible_label": "Reference",
                    **(
                        {
                            "binding_bbox": [1, 1, 4, 10],
                            "seeds": [[1.0, 9.0], [9.0, 1.0]],
                            "tracking": {
                                "max_vertical_step_px": 2.0,
                                "max_gap_px": 0,
                                "max_gap_vertical_displacement_px": 2.0,
                                "max_guide_distance_px": 2.0,
                                "min_visible_fraction": 0.5,
                                "min_points": 3,
                                "plot_border_exclusion_px": 0,
                            },
                            "eligibility": {"default_eligible": True},
                        }
                        if e2_contract
                        else {
                            "min_points": 3,
                            "min_visible_fraction": 0.5,
                            "max_vertical_spread_px": 1.0,
                            "uncertainty_px": 0.0,
                        }
                    ),
                }
            ],
        }
    )
    files, _ = build_digitized_figure_bundle(source, request)
    return (
        files["figure_manifest/evidence.json"][0],
        files["validation_reports/validation_report.json"][0],
        next(content for name, (content, _) in files.items() if name.startswith("curve_tables/")),
    )


def _ingaas_payloads() -> dict[str, bytes]:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("material", "depth_um", "target", "baseline", "candidate"))
    rows = tuple((index / 10.0, target_log) for index, target_log in enumerate((20.0, 19.0, 18.0, 17.0, 16.0)))
    for depth, target_log in rows:
        target = 10.0**target_log
        writer.writerow(("ingaas", depth, target, target, 10.0 ** (target_log + 0.01)))
    curve_table = output.getvalue().encode()
    target_metrics = json.dumps(
        {
            "materials": {
                "ingaas": {
                    "baseline": {"front_ge_1e17_RMS_decade": 0.0, "full_RMS_decade": 0.0},
                    "candidate": {"front_ge_1e17_RMS_decade": 0.01, "full_RMS_decade": 0.01},
                }
            }
        },
        separators=(",", ":"),
    ).encode()
    contract = {
        "scorer_version": "2.0.0",
        "immutable_input_identity": {
            "curve_bundle": {
                "required_columns_in_order": ["material", "depth_um", "target", "baseline", "candidate"],
                "supplied_sha256": hashlib.sha256(curve_table).hexdigest(),
                "ingaas_row_count": 5,
            },
            "target_metrics": {"supplied_sha256": hashlib.sha256(target_metrics).hexdigest()},
            "identity_reproduction": {"maximum_absolute_difference_decade": 1.0e-8},
        },
        "runtime_artifact_requirements": {
            "required_plx_fields": [
                "ZnTotal",
                "Zinc",
                "ZincConcentration",
                "ZincActiveConcentration",
                "xMoleFraction",
                "Potential",
            ]
        },
        "score_definitions": {
            "baseline_recovery": {
                "full_rms_max_decade": 0.005,
                "full_max_abs_residual_max_decade": 0.02,
                "each_crossing_absolute_error_max_nm": 0.05,
                "width_1e18_to_1e17_absolute_error_max_nm": 0.05,
                "target_front_rms_absolute_difference_max_decade": 0.005,
                "target_full_rms_absolute_difference_max_decade": 0.005,
            }
        },
    }
    project = DeckProjectDraft(
        tool_profile="deterministic-scorer",
        solver_kind="deterministic_tool",
        files=(DeckFile(relative_path="scoring/SCORER_CONTRACT.v2.json", content=json.dumps(contract, separators=(",", ":"))),),
        entrypoint="scoring/SCORER_CONTRACT.v2.json",
        expected_outputs=(),
        resource_limits={
            "wall_time_seconds": 30,
            "cpu_time_seconds": 30,
            "max_memory_bytes": 64 * 1024 * 1024,
            "max_output_bytes": 1024 * 1024,
            "max_processes": 1,
        },
    )

    def plx(offset: float) -> bytes:
        blocks: list[str] = []
        for field in ("ZnTotal", "Zinc", "ZincConcentration", "ZincActiveConcentration", "xMoleFraction", "Potential"):
            blocks.append(f'"{field}"')
            blocks.extend(f"{depth:.17g} {10.0 ** (target_log + offset):.17g}" for depth, target_log in rows)
        return ("\n".join(blocks) + "\n").encode()

    return {
        "scorer_project": project.model_dump_json().encode(),
        "curve_bundle": curve_table,
        "target_metrics": target_metrics,
        "historical_baseline": plx(0.0),
        "candidate_profile": plx(0.01),
    }


def _runtime_attestation(*, solver_outputs: int) -> bytes:
    return canonical_json(
        RuntimeAttestation(
            verdict="pass",
            terminal_state="succeeded",
            exit_code=0,
            checks=(
                RuntimeContractCheck(
                    check_key="terminal_state",
                    status="pass",
                    rationale="The frozen execution completed successfully.",
                ),
            ),
            solver_native_output_count=solver_outputs,
            transport_derived_output_count=0,
            parser_derived_output_count=0,
            rationale="The bounded runtime contract passed.",
        ).model_dump(mode="json")
    )


def _tcad_payloads() -> dict[str, bytes]:
    reviewed_raw = _reviewed_package()
    reviewed = ReviewedDeckPackage.model_validate_json(reviewed_raw, strict=True)
    experiment_plan = _tcad_portfolio().canonical_json()
    capability = canonical_json(reviewed.capability.model_dump(mode="json"))
    package_plan_data = _tcad_portfolio().model_dump(mode="json")
    package_plan_data["study_kind"] = "scientific"
    package_plan_data["objective_key"] = "package_fixture"
    package_plan_data["selected_hypothesis_keys"] = ["implementation_smoke"]
    package_proposal = package_plan_data["proposals"][0]
    package_proposal.update(
        {
            "hypothesis_keys": ["implementation_smoke"],
            "changed_factors": [
                {
                    "name": "case_bias",
                    "factor_type": "implementation",
                    "values": [1, 2],
                    "unit": "1",
                    "rationale": "The fixture needs two explicit source-bound cases.",
                }
            ],
            "cases": [
                {
                    "case_key": "baseline",
                    "scientific_role": "baseline",
                    "settings": [{"name": "case_bias", "value": 1, "unit": "1"}],
                    "purpose": "Exercise the baseline source anchor.",
                },
                {
                    "case_key": "comparison",
                    "scientific_role": "perturbation",
                    "settings": [{"name": "case_bias", "value": 2, "unit": "1"}],
                    "purpose": "Exercise the comparison source anchor.",
                },
            ],
            "comparison_contract": {
                "baseline_case_key": "baseline",
                "comparison_case_keys": ["comparison"],
                "variables": [
                    {
                        "variable_key": "case_bias",
                        "scientific_path": "implementation.case_bias",
                        "factor_type": "implementation",
                        "comparison_role": "intended_change",
                        "unit": "1",
                        "expectations": [
                            {"case_key": "baseline", "value": 1},
                            {"case_key": "comparison", "value": 2},
                        ],
                        "equivalence_rule": "exact",
                        "rationale": "The two cases exercise distinct declared anchors.",
                    }
                ],
                "required_observables": ["terminal state"],
                "identifiability_claims": [
                    {
                        "hypothesis_key": "implementation_smoke",
                        "observable": "terminal state",
                        "distinguishing_outcome": "Both bounded cases terminate.",
                        "decision_rule": "Inspect the exact terminal states.",
                        "ambiguity_conditions": ["A bounded case cannot start."],
                        "smallest_resolving_control": "Repeat the failed case.",
                    }
                ],
            },
            "prediction_tests": [
                {
                    "hypothesis_key": "implementation_smoke",
                    "prediction_key": "bounded_completion",
                    "observable": "terminal state",
                    "expected_result": "Both bounded cases terminate.",
                    "falsifying_result": "Either bounded case fails to terminate.",
                }
            ],
            "resource_estimate": {
                "case_count": 2,
                "relative_cost": "low",
                "runtime_basis": "Two bounded synthetic invocations.",
            },
        }
    )
    package_plan = type(_tcad_portfolio()).model_validate_json(
        canonical_json(package_plan_data), strict=True
    ).canonical_json()
    package_source = "set case_bias 1\nset case_bias 2\nSolve {}\n"
    package_source_sha = hashlib.sha256(
        b"main.cmd\0" + package_source.encode() + b"\0"
    ).hexdigest()
    package_project = materialize_deck_project(
        metadata={
            "resource_limits": reviewed.project.resource_limits.model_dump(mode="json"),
        },
        declarations={
            "schema_version": 2,
            "profile": "tcad.project-declaration-contract.v2",
            "entrypoint": reviewed.project.entrypoint,
            "development_initialization_entrypoint": None,
            "case_anchors": [
                {
                    "experiment_key": "entrypoint_smoke",
                    "case_key": "baseline",
                    "relative_path": "main.cmd",
                    "locator": "set case_bias 1",
                },
                {
                    "experiment_key": "entrypoint_smoke",
                    "case_key": "comparison",
                    "relative_path": "main.cmd",
                    "locator": "set case_bias 2",
                }
            ],
            "raw_outputs": [],
        },
        files=({"relative_path": "main.cmd", "content": package_source},),
        experiment_plan=package_plan,
        execution_capability=capability,
        preflight_attestation=ProjectPreflightAttestation(
            source_tree_sha256=package_source_sha,
            terminal_state="succeeded",
            exit_code=0,
            diagnostic_layer="complete",
            qualified=True,
            summary="The synthetic declared-source fixture passed bounded preflight.",
        ).model_dump(mode="json"),
    )
    manifest = TCADRuntimeManifest(
        started_at="2026-09-01T00:00:00Z",
        completed_at="2026-09-01T00:00:01Z",
        terminal_state="succeeded",
        exit_code=0,
        error="",
        outputs=(),
    )
    comparison = ComparisonContract.model_validate_json(
        canonical_json(
            {
                "baseline_case_key": "baseline",
                "comparison_case_keys": ["comparison"],
                "variables": [
                    {
                        "variable_key": "downstream_metric",
                        "scientific_path": "analysis.downstream_metric",
                        "factor_type": "implementation",
                        "comparison_role": "intended_change",
                        "unit": "1",
                        "expectations": [
                            {"case_key": "baseline", "value": 1},
                            {"case_key": "comparison", "value": 2},
                        ],
                        "equivalence_rule": "exact",
                        "rationale": "The downstream value is outside deck realization.",
                    }
                ],
                "required_observables": ["terminal state"],
                "identifiability_claims": [
                    {
                        "hypothesis_key": "implementation_error",
                        "observable": "terminal state",
                        "distinguishing_outcome": "The bounded run terminates.",
                        "decision_rule": "Inspect the exact terminal state.",
                        "ambiguity_conditions": ["The run does not start."],
                        "smallest_resolving_control": "Repeat the bounded run.",
                    }
                ],
            }
        ),
        strict=True,
    )
    return {
        "reviewed_package": reviewed_raw,
        "project": canonical_json(reviewed.project.model_dump(mode="json")),
        "package_project": canonical_json(package_project.model_dump(mode="json")),
        "package_plan": package_plan,
        "review": canonical_json(reviewed.review.model_dump(mode="json")),
        "capability": capability,
        "experiment_plan": experiment_plan,
        "runtime_manifest": canonical_json(manifest.model_dump(mode="json")),
        "comparison_contract": comparison.canonical_json(),
        "case": canonical_json({"schema_version": 1, "case_key": "baseline"}),
    }


def _tcad_curve_payloads() -> dict[str, bytes]:
    plan = _curve_plan().canonical_json()
    contract = _curve_contract().canonical_json()
    parsed = CurveExperimentContract.model_validate_json(contract, strict=True)
    series = tuple(parsed.comparison_spec.series_declarations)
    plx_payloads: dict[str, bytes] = {}
    records: list[RuntimeOutputRecord] = []
    log_lines: list[str] = []
    for declaration in series:
        raw = (
            f'"{declaration.series_key}"\n'
            "0 1e10\n"
            "0.5 1e11\n"
            "1 1e12\n"
        ).encode()
        plx_payloads[declaration.series_key] = raw
        records.append(
            RuntimeOutputRecord(
                name=declaration.series_key,
                relative_path=f"{declaration.series_key}.plx",
                media_type="application/x-synopsys-plx",
                sha256=hashlib.sha256(raw).hexdigest(),
                size_bytes=len(raw),
            )
        )
        for index, (x, y) in enumerate(((0.0, 1e10), (0.5, 1e11), (1.0, 1e12))):
            log_lines.append(
                f"SCID_CURVE_V1|POINT|{declaration.case_key}|{declaration.series_key}|{index}|{x}|{y}"
            )
        log_lines.append(
            f"SCID_CURVE_V1|END|{declaration.case_key}|{declaration.series_key}|3"
        )
    manifest = TCADRuntimeManifest(
        started_at="2026-09-01T00:00:00Z",
        completed_at="2026-09-01T00:00:01Z",
        terminal_state="succeeded",
        exit_code=0,
        error="",
        outputs=tuple(records),
    )
    return {
        "experiment_plan": plan,
        "curve_contract": contract,
        "experiment_review": _review(),
        "curve_contract_review": _review(),
        "runtime_manifest": canonical_json(manifest.model_dump(mode="json")),
        "runtime_attestation": _runtime_attestation(solver_outputs=len(records)),
        "solver_log": ("\n".join(log_lines) + "\n").encode(),
        **{f"plx_{name}": raw for name, raw in plx_payloads.items()},
    }


def _objective_fixture() -> tuple[ScientificIntake, bytes, bytes]:
    intake: ScientificIntake = _intake()
    objective_contract = ResearchObjectiveContract.model_validate_json(
        canonical_json(
            {
                "objective_key": "bounded_curve_reproduction",
                "intent": "external_reproduction",
                "statement": "Reproduce one bounded target curve.",
                "mandatory_targets": [
                    {
                        "target_key": "target_curve",
                        "observable": "profile",
                        "support_requirement": "complete_observation",
                        "evidence_item_keys": ["target"],
                        "rationale": "The supplied curve is the only target.",
                    }
                ],
                "closure_requirements": [
                    {
                        "requirement_key": "target_coverage",
                        "description": "Cover the frozen target.",
                        "requirement_type": "target_coverage",
                        "target_keys": ["target_curve"],
                    }
                ],
            }
        ),
        strict=True,
    )
    foundation = intake.scientific_foundation.model_copy(
        update={"objective_contract": objective_contract}
    ).canonical_json()
    objective = _project_research_objective(foundation)
    return intake, foundation, objective


def _scenarios(catalog) -> tuple[Scenario, ...]:
    intake, foundation, objective = _objective_fixture()
    parameter = _parameter_package()
    parameter_coverage = evaluate_device_parameter_coverage(
        parameter.parameter_requirements,
        parameter.device_parameters,
        parameter.source_catalog,
    ).canonical_json()
    curve_inputs = _curve_analysis_inputs()
    plan = curve_inputs["experiment_plan"]
    contract = curve_inputs["curve_contract"]
    bundle = curve_inputs["curve_bundle"]
    figure_manifest, figure_report, figure_table = _figure_payloads()
    figure_operation = catalog.operation(
        "scidiscovery.curve-bundle.figure-evidence.v2"
    )
    reviewed_figure_bundle = {
        port.name for port in figure_operation.spec.inputs
    } >= {"scientific_intake", "evidence_audit"}
    figure_data = (
        *(
            (Datum("scientific_intake", "figure_intake", intake.canonical_json()),)
            if reviewed_figure_bundle
            else ()
        ),
        Datum("figure_manifest", "figure_manifest", figure_manifest),
        Datum("curve_tables", "figure_table", figure_table, media_type="text/csv"),
        Datum(
            "validation_report",
            "figure_validation",
            figure_report,
            parent_keys=("figure_manifest", "figure_table"),
        ),
        *(
            (
                Datum(
                    "evidence_audit",
                    "figure_audit",
                    _evidence_audit(),
                    parent_keys=(
                        "figure_intake",
                        "figure_manifest",
                        "figure_validation",
                        "figure_table",
                    ),
                ),
            )
            if reviewed_figure_bundle
            else ()
        ),
    )
    tcad = _tcad_payloads()
    tcad_curve = _tcad_curve_payloads()
    ingaas = _ingaas_payloads()
    reference_bundle = _curve_bundle().canonical_json()
    scenarios = [
        Scenario(
            "science.intake.split.v1",
            (
                Datum("scientific_intake", "intake", intake.canonical_json()),
                Datum("evidence_audit", "intake_audit", b"{}"),
            ),
            "intake_audit",
        ),
        Scenario(
            "science.objective.project.v1",
            (Datum("scientific_foundation", "objective_foundation", foundation),),
            "objective_foundation",
        ),
        Scenario(
            "science.experiment.materialize.v1",
            (Datum("experiment_design_intent", "engineering_intent", _engineering_intent()),),
            "engineering_intent",
        ),
        Scenario(
            "tcad.parameter.evidence.expand.v1",
            (Datum("parameter_evidence_package", "parameter_package", parameter.canonical_json()),),
            "parameter_package",
        ),
        Scenario(
            "science.parameter.coverage.v1",
            (
                Datum("parameter_requirements", "coverage_requirements", parameter.parameter_requirements.canonical_json()),
                Datum("device_parameters", "coverage_parameters", parameter.device_parameters.canonical_json()),
                Datum("source_catalog", "coverage_sources", parameter.source_catalog.canonical_json()),
            ),
            "coverage_sources",
        ),
        Scenario(
            "science.parameter.uncertainty.v1",
            (
                Datum("parameter_requirements", "uncertainty_requirements", parameter.parameter_requirements.canonical_json()),
                Datum("device_parameters", "uncertainty_parameters", parameter.device_parameters.canonical_json()),
                Datum(
                    "parameter_coverage",
                    "parameter_coverage",
                    parameter_coverage,
                    parent_keys=("uncertainty_requirements", "uncertainty_parameters"),
                ),
            ),
            "parameter_coverage",
            ("parameter_coverage", "uncertainty_requirements"),
        ),
        Scenario(
            "scidiscovery.curve-reference-coverage.v1",
            (
                Datum("experiment_plan", "reference_plan", plan),
                Datum("experiment_review", "reference_plan_review", _review()),
                Datum("curve_contract", "reference_contract", contract),
                Datum("curve_contract_review", "reference_contract_review", _review()),
                Datum("reference_bundles", "reference_library", reference_bundle),
            ),
            "reference_contract_review",
        ),
        Scenario(
            "scidiscovery.curve-score.v1",
            (
                Datum("experiment_plan", "score_plan", plan),
                Datum("curve_contract", "score_contract", contract),
                Datum(
                    "curve_bundle",
                    "score_bundle",
                    bundle,
                    parent_keys=("score_contract", "score_plan"),
                ),
                Datum("experiment_review", "score_plan_review", _review()),
                Datum("curve_contract_review", "score_contract_review", _review()),
            ),
            "score_contract_review",
            ("score_bundle", "score_contract"),
        ),
        Scenario(
            "scidiscovery.objective-coverage.v1",
            (
                Datum("objective", "curve_objective", objective),
                Datum("experiment_plan", "objective_plan", plan, parent_keys=("curve_objective",)),
                Datum("experiment_review", "objective_plan_review", _review()),
                Datum("curve_contracts", "objective_contract", contract, parent_keys=("objective_plan",)),
                Datum("curve_contract_reviews", "objective_contract_review", _review()),
                Datum("reference_bundles", "objective_reference", reference_bundle),
            ),
            "objective_contract_review",
            ("objective_contract", "objective_plan"),
        ),
        Scenario(
            "science.curve.error.analyze.v1",
            tuple(
                Datum(
                    name,
                    f"analysis_{name}",
                    raw,
                )
                for name, raw in curve_inputs.items()
            ),
            "analysis_curve_contract_review",
        ),
        Scenario(
            "tcad.deck-project-compare.v1",
            (
                Datum("base_project", "base_project", tcad["project"]),
                Datum("revised_project", "revised_project", tcad["project"]),
            ),
            "revised_project",
        ),
        Scenario(
            "tcad.deck-review-validate.v1",
            (
                Datum("project", "review_project", tcad["project"]),
                Datum("review", "deck_review", tcad["review"]),
            ),
            "deck_review",
        ),
        Scenario(
            "tcad.reviewed-deck-package.v2",
            (
                Datum("project", "package_project", tcad["package_project"]),
                Datum("capability", "package_capability", tcad["capability"]),
                Datum("experiment_plan", "package_plan", tcad["package_plan"]),
                Datum(
                    "review",
                    "package_review",
                    tcad["review"],
                    parent_keys=("package_project", "package_capability", "package_plan"),
                ),
            ),
            "package_review",
            ("package_review", "package_capability"),
        ),
        Scenario(
            "tcad.runtime-attestation.v1",
            (
                Datum("reviewed_package", "runtime_package", tcad["reviewed_package"]),
                Datum(
                    "runtime_manifest",
                    "runtime_manifest",
                    tcad["runtime_manifest"],
                    parent_keys=("runtime_package",),
                ),
            ),
            "runtime_manifest",
            ("runtime_manifest", "runtime_package"),
        ),
        Scenario(
            "tcad.realization-snapshot-materialize.v1",
            (
                Datum("comparison_contract", "realization_contract", tcad["comparison_contract"]),
                Datum("reviewed_package", "realization_package", tcad["reviewed_package"]),
                Datum("case", "realization_case", tcad["case"]),
            ),
            "realization_case",
        ),
        Scenario(
            "tcad.control-equivalence.v1",
            (
                Datum("experiment_plan", "control_plan", tcad["experiment_plan"]),
                Datum("reviewed_packages", "control_package", tcad["reviewed_package"]),
            ),
            "control_package",
        ),
        Scenario(
            "tcad.curve-bundle.sprocess-log.v1",
            (
                Datum("solver_output", "solver_log", tcad_curve["solver_log"], media_type="text/plain"),
                Datum(
                    "runtime_attestation",
                    "log_attestation",
                    tcad_curve["runtime_attestation"],
                    parent_keys=("solver_log",),
                ),
                Datum("experiment_plan", "log_plan", tcad_curve["experiment_plan"]),
                Datum("experiment_review", "log_plan_review", tcad_curve["experiment_review"]),
                Datum("curve_contract", "log_contract", tcad_curve["curve_contract"]),
                Datum("curve_contract_review", "log_contract_review", tcad_curve["curve_contract_review"]),
            ),
            "log_attestation",
            ("log_attestation", "solver_log"),
        ),
        Scenario(
            "tcad.curve-bundle.sprocess-plx.v1",
            (
                Datum("experiment_plan", "plx_plan", tcad_curve["experiment_plan"]),
                Datum("runtime_manifest", "plx_manifest", tcad_curve["runtime_manifest"], parent_keys=("plx_plan",)),
                *tuple(
                    Datum(
                        "solver_outputs",
                        f"plx_{name}",
                        tcad_curve[f"plx_{name}"],
                        media_type="application/x-synopsys-plx",
                        parent_keys=("plx_plan",),
                    )
                    for name in ("reference", "candidate")
                ),
                Datum(
                    "runtime_attestation",
                    "plx_attestation",
                    tcad_curve["runtime_attestation"],
                    parent_keys=("plx_manifest", "plx_reference", "plx_candidate"),
                ),
                Datum("experiment_review", "plx_plan_review", tcad_curve["experiment_review"]),
                Datum("curve_contract", "plx_contract", tcad_curve["curve_contract"]),
                Datum("curve_contract_review", "plx_contract_review", tcad_curve["curve_contract_review"]),
            ),
            "plx_attestation",
            ("plx_attestation", "plx_reference"),
        ),
        Scenario(
            "ingaas.fig4-baseline-recovery.v2",
            (
                Datum("scorer_project", "ingaas_project", ingaas["scorer_project"]),
                Datum("curve_bundle", "ingaas_curve", ingaas["curve_bundle"], media_type="text/csv"),
                Datum("target_metrics", "ingaas_metrics", ingaas["target_metrics"]),
                Datum("historical_baseline", "ingaas_history", ingaas["historical_baseline"], media_type="application/x-synopsys-plx"),
                Datum("candidate_profile", "ingaas_candidate", ingaas["candidate_profile"], media_type="application/x-synopsys-plx"),
            ),
            "ingaas_candidate",
        ),
    ]
    return tuple(scenarios)


def _experiment_lineage_probe() -> Scenario:
    _, foundation, objective = _objective_fixture()
    return Scenario(
        "science.experiment.materialize.v1",
        (
            Datum("scientific_foundation", "probe_foundation", foundation),
            Datum(
                "research_objective",
                "probe_objective",
                objective,
                parent_keys=("probe_foundation",),
            ),
            Datum(
                "hypothesis_portfolio",
                "probe_hypothesis",
                _hypothesis(),
                parent_keys=("probe_foundation",),
            ),
            Datum(
                "critic_review",
                "probe_critic",
                _review(),
                parent_keys=("probe_foundation", "probe_hypothesis"),
            ),
            Datum(
                "experiment_design_intent",
                "probe_intent",
                _engineering_intent(),
                parent_keys=(
                    "probe_foundation",
                    "probe_objective",
                    "probe_hypothesis",
                    "probe_critic",
                ),
            ),
        ),
        "probe_intent",
        ("probe_intent", "probe_critic"),
    )


def _catalog():
    return compile_catalog(
        (
            CORE_PLUGIN,
            GENERAL_PLUGIN,
            CURVE_PLUGIN,
            TCAD_PLUGIN,
            INGAAS_PLUGIN,
            FIGURE_PLUGIN,
        )
    )


def _open_root(directory: Path, catalog, operation_id: str):
    project = directory / "project"
    project.mkdir(parents=True)
    runtime = open_runtime(
        project_root=project,
        state_root=directory / "state",
        worker_backend="local",
        approval_receipt_secret=b"m3-equivalence-receipt-secret-0001",
    )
    runtime.runs.operation_catalog = catalog
    instance = runtime.scheduler_bindings.create_instance(
        name=f"m3_{_safe(operation_id)}",
        title="M3 deterministic equivalence fixture",
        objective="Compare one exact deterministic operation across M2 and M3.",
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
    return runtime, instance, root


def _register_data(
    runtime,
    instance,
    operation,
    scenario: Scenario,
    *,
    omit_edge: tuple[str, str] | None = None,
) -> tuple[dict[str, object], dict[str, str]]:
    ports = {port.name: port for port in operation.spec.inputs}
    envelopes: dict[str, object] = {}
    artifact_names: dict[str, str] = {}
    for datum in scenario.data:
        port = ports[datum.port]
        parents = tuple(
            envelopes[key].ref
            for key in datum.parent_keys
            if omit_edge != (datum.key, key)
        )
        artifact_name = f"input_{_safe(datum.key)}"
        envelope = runtime.artifacts.register(
            datum.content,
            ArtifactRegistration(
                artifact_id=f"art_m3_{_safe(datum.key)}",
                kind=f"fixture_{_safe(datum.port)}",
                schema_id=port.schema_id,
                payload_schema_version=1,
                media_type=datum.media_type or port.media_types[0],
                creator=runtime.actor,
                parent_refs=parents,
            ),
            idempotency_key=f"m3-equivalence:{scenario.operation_id}:{datum.key}",
        )
        runtime.scheduler_bindings.bind(
            instance=instance.instance_id,
            namespace="artifact",
            name=artifact_name,
            object_id=envelope.artifact_id,
        )
        envelopes[datum.key] = envelope
        artifact_names[datum.key] = artifact_name
    return envelopes, artifact_names


def _request(operation, scenario: Scenario, names: dict[str, str]) -> dict[str, object]:
    grouped: dict[str, list[str]] = {}
    for datum in scenario.data:
        grouped.setdefault(datum.port, []).append(names[datum.key])
    return {
        "name": f"result_{_safe(scenario.operation_id)}",
        "operation_id": scenario.operation_id,
        "inputs": [
            {"port": port.name, "artifact_names": grouped[port.name]}
            for port in operation.spec.inputs
            if port.name in grouped
        ],
    }


def _approve_input_cohorts(
    runtime, operation, scenario: Scenario, envelopes, *, suffix: str = "base"
) -> None:
    by_port = {datum.port: envelopes[datum.key] for datum in scenario.data}
    if not hasattr(operation.spec, "input_admission"):
        cohorts: dict[str, list[object]] = {}
        for port in operation.spec.inputs:
            if (
                port.cohort_id is not None
                and port.approval_kind is not None
                and port.name in by_port
            ):
                cohorts.setdefault(port.cohort_id, []).append(port)
        for cohort_id, ports in cohorts.items():
            _record_fixture_approval(
                runtime,
                scenario,
                envelopes=by_port,
                cohort_id=cohort_id,
                kind=ports[0].approval_kind,
                subject_ports=tuple(port.name for port in ports),
                option_id=ports[0].accepted_approval_options[0],
                provider=operation.approval_providers[cohort_id][0],
                suffix=suffix,
            )
        return
    admission = operation.spec.input_admission
    if admission is not None and admission.approval_kind is not None:
        if not all(name in by_port for name in admission.approval_subject_ports):
            return
        _record_fixture_approval(
            runtime,
            scenario,
            envelopes=by_port,
            cohort_id=admission.cohort_id,
            kind=admission.approval_kind,
            subject_ports=admission.approval_subject_ports,
            option_id=admission.accepted_options[0],
            provider=operation.approval_providers[0],
            suffix=suffix,
        )


def _record_fixture_approval(
    runtime,
    scenario: Scenario,
    *,
    envelopes,
    cohort_id: str,
    kind: str,
    subject_ports: tuple[str, ...],
    option_id: str,
    provider,
    suffix: str,
) -> None:
    approval_id = (
        f"m3_{_safe(scenario.operation_id)}_{_safe(cohort_id)}_{_safe(suffix)}"
    )
    launch = runtime.approvals.create_request(
        approval_id=approval_id,
        kind=kind,
        subject_refs=tuple(envelopes[name].ref for name in subject_ports),
        question="Approve the exact frozen equivalence fixture.",
        options=(
            ApprovalOption(
                option_id=option_id,
                label="Approve",
                description="Bounded automated debug approval fixture.",
                requires_rationale=False,
            ),
            ApprovalOption(
                option_id="reject_fixture",
                label="Reject",
                description="Reject the bounded automated debug fixture.",
                requires_rationale=False,
            ),
        ),
        requested_by=runtime.actor,
        idempotency_key=(
            f"m3-equivalence-approval:{scenario.operation_id}:{cohort_id}:{suffix}"
        ),
        compiled_identity=CompiledApprovalIdentity(
            operation_id=provider.operation_id,
            operation_version=provider.version,
            operation_digest=provider.operation_digest,
            approval_contract_digest=provider.approval_contract_digest,
        ),
    )
    review = runtime.approvals.review(
        launch.approval_id, access_token=launch.access_token
    )
    runtime.approvals.record_ui_decision(
        approval_id=launch.approval_id,
        access_token=launch.access_token,
        csrf_token=review.csrf_token,
        decision_nonce=review.decision_nonce,
        selected_option=option_id,
        rationale="",
        decided_by=LocalIdentityRef(
            identity_id="m3_debug_approver",
            display_name="M3 Debug Approver",
        ),
        ui_session_id="m3-transform-equivalence",
    )


def _stable_ref(ref) -> dict[str, str]:
    return {
        "artifact_id": ref.artifact_id,
        "sha256": ref.sha256,
        "kind": ref.kind,
        "schema_id": ref.schema_id,
    }


def _capture_outputs(runtime, instance, response: dict[str, object]) -> list[dict[str, object]]:
    captured: list[dict[str, object]] = []
    for item in response["result"]["outputs"]:
        artifact_id = runtime.scheduler_bindings.resolve(
            instance=instance.instance_id,
            namespace="artifact",
            name=item["artifact_name"],
        )
        envelope = runtime.artifacts.get_by_id(artifact_id)
        content = runtime.artifacts.read(envelope.ref)
        binding = runtime.scheduler_bindings.get_binding(
            instance=instance.instance_id,
            namespace="artifact",
            name=item["artifact_name"],
        )
        captured.append(
            {
                "output_label": item["output_label"],
                "artifact_name": item["artifact_name"],
                "kind": envelope.kind,
                "schema_id": envelope.schema_id,
                "payload_schema_version": envelope.payload_schema_version,
                "media_type": envelope.media_type,
                "content_base64": base64.b64encode(content).decode("ascii"),
                "parent_refs": [_stable_ref(ref) for ref in envelope.parent_refs],
                "semantic_binding": {
                    "name": binding.name,
                    "logical_name": binding.logical_name,
                    "revision": binding.revision,
                    "request_fingerprint": binding.request_fingerprint,
                },
                "operation_labels": {
                    key: value
                    for key, value in sorted(envelope.labels.items())
                    if key
                    in {
                        "operation_id",
                        "operation_version",
                        "operation_digest",
                        "operation_invocation_fingerprint",
                        "transform_profile",
                        "output_label",
                        "operation_output_port",
                        "scientific_claim_admissible",
                    }
                },
                "supersedes": (
                    None
                    if envelope.supersedes_ref is None
                    else {
                        key: value
                        for key, value in _stable_ref(envelope.supersedes_ref).items()
                        if key != "artifact_id"
                    }
                ),
            }
        )
    return captured


def _register_revision_input(
    runtime,
    instance,
    operation,
    scenario: Scenario,
    envelopes: dict[str, object],
    names: dict[str, str],
) -> tuple[dict[str, str], object]:
    datum = next(item for item in scenario.data if item.key == scenario.revision_key)
    port = next(item for item in operation.spec.inputs if item.name == datum.port)
    parent_refs = tuple(envelopes[key].ref for key in datum.parent_keys)
    artifact_name = f"{names[datum.key]}_revision"
    envelope = runtime.artifacts.register(
        datum.content,
        ArtifactRegistration(
            artifact_id=f"art_m3_{_safe(datum.key)}_revision",
            kind=f"fixture_{_safe(datum.port)}",
            schema_id=port.schema_id,
            payload_schema_version=1,
            media_type=datum.media_type or port.media_types[0],
            creator=runtime.actor,
            parent_refs=parent_refs,
        ),
        idempotency_key=f"m3-equivalence:{scenario.operation_id}:{datum.key}:revision",
    )
    runtime.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="artifact",
        name=artifact_name,
        object_id=envelope.artifact_id,
    )
    revised = dict(names)
    revised[datum.key] = artifact_name
    return revised, envelope


def _run_scenario(base: Path, catalog, scenario: Scenario) -> dict[str, object]:
    operation = catalog.operation(scenario.operation_id)
    directory = base / _safe(scenario.operation_id)
    if directory.exists():
        shutil.rmtree(directory)
    runtime, instance, root = _open_root(directory, catalog, scenario.operation_id)
    envelopes, names = _register_data(runtime, instance, operation, scenario)
    _approve_input_cohorts(runtime, operation, scenario, envelopes)
    request = _request(operation, scenario, names)
    preflight = root.call_tool("operation_preflight", request)
    if preflight.get("admissible") is not True:
        raise AssertionError(f"positive preflight failed for {scenario.operation_id}: {preflight}")
    first = root.call_tool("operation_invoke", request)
    replay = root.call_tool("operation_invoke", request)
    if replay != first:
        raise AssertionError(f"idempotent replay drifted for {scenario.operation_id}")

    revised_names, revised_envelope = _register_revision_input(
        runtime, instance, operation, scenario, envelopes, names
    )
    revised_envelopes = dict(envelopes)
    revised_envelopes[scenario.revision_key] = revised_envelope
    _approve_input_cohorts(
        runtime, operation, scenario, revised_envelopes, suffix="revision"
    )
    revised_request = _request(operation, scenario, revised_names)
    reject_error: str | None = None
    try:
        root.call_tool("operation_invoke", revised_request)
    except (RootToolError, SchedulerNameConflict) as error:
        reject_error = f"{type(error).__name__}:{error}"
    if reject_error is None:
        raise AssertionError(f"conflicting request was not rejected for {scenario.operation_id}")
    revision = root.call_tool(
        "operation_invoke", {**revised_request, "on_conflict": "create_revision"}
    )

    negative: dict[str, object] | None = None
    if scenario.negative_edge is not None:
        negative_directory = base / f"{_safe(scenario.operation_id)}_negative"
        if negative_directory.exists():
            shutil.rmtree(negative_directory)
        neg_runtime, neg_instance, neg_root = _open_root(
            negative_directory, catalog, scenario.operation_id
        )
        neg_envelopes, neg_names = _register_data(
            neg_runtime,
            neg_instance,
            operation,
            scenario,
            omit_edge=scenario.negative_edge,
        )
        _approve_input_cohorts(neg_runtime, operation, scenario, neg_envelopes)
        negative = neg_root.call_tool(
            "operation_preflight", _request(operation, scenario, neg_names)
        )
        if negative.get("admissible") is not False or negative.get("reason_code") != "guard_rejected":
            raise AssertionError(
                f"guard negative did not fail at its guard for {scenario.operation_id}: {negative}"
            )
        negative = {
            "admissible": negative["admissible"],
            "reason_code": negative["reason_code"],
            "removed_edge": list(scenario.negative_edge),
        }

    return {
        "operation_id": scenario.operation_id,
        "operation_version": operation.spec.version,
        "operation_digest": operation.digest,
        "preflight_admissible": preflight["admissible"],
        "outputs": _capture_outputs(runtime, instance, first),
        "idempotent_replay_equal": True,
        "conflict_rejection": reject_error,
        "revision_outputs": _capture_outputs(runtime, instance, revision),
        "guard_negative": negative,
    }


def _run_guard_probe(base: Path, catalog, scenario: Scenario) -> dict[str, object]:
    if scenario.negative_edge is None:
        raise AssertionError("guard probe requires one removed lineage edge")
    operation = catalog.operation(scenario.operation_id)
    directory = base / f"{_safe(scenario.operation_id)}_guard_probe"
    if directory.exists():
        shutil.rmtree(directory)
    runtime, instance, root = _open_root(directory, catalog, scenario.operation_id)
    envelopes, names = _register_data(runtime, instance, operation, scenario)
    _approve_input_cohorts(runtime, operation, scenario, envelopes, suffix="guard_probe")
    positive = root.call_tool("operation_preflight", _request(operation, scenario, names))
    if positive.get("admissible") is not True:
        raise AssertionError(
            f"guard positive failed for {scenario.operation_id}: {positive}"
        )

    negative_directory = base / f"{_safe(scenario.operation_id)}_guard_probe_negative"
    if negative_directory.exists():
        shutil.rmtree(negative_directory)
    neg_runtime, neg_instance, neg_root = _open_root(
        negative_directory, catalog, scenario.operation_id
    )
    neg_envelopes, neg_names = _register_data(
        neg_runtime,
        neg_instance,
        operation,
        scenario,
        omit_edge=scenario.negative_edge,
    )
    _approve_input_cohorts(
        neg_runtime, operation, scenario, neg_envelopes, suffix="guard_probe_negative"
    )
    negative = neg_root.call_tool(
        "operation_preflight", _request(operation, scenario, neg_names)
    )
    if (
        negative.get("admissible") is not False
        or negative.get("reason_code") != "guard_rejected"
    ):
        raise AssertionError(
            f"guard negative did not fail at its guard for {scenario.operation_id}: "
            f"{negative}"
        )
    return {
        "operation_id": scenario.operation_id,
        "positive_admissible": True,
        "negative_admissible": False,
        "negative_reason_code": "guard_rejected",
        "removed_edge": list(scenario.negative_edge),
    }


def _source_digest(root: Path) -> tuple[int, int, str]:
    files = sorted(
        path
        for base in (root / "src", root / "plugins")
        for path in base.rglob("*.py")
        if "__pycache__" not in path.parts
    )
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(root).as_posix().encode()
        digest.update(relative)
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return (
        len(files),
        sum(len(path.read_text(encoding="utf-8").splitlines()) for path in files),
        digest.hexdigest(),
    )


def _loaded_production_modules(root: Path) -> dict[str, str]:
    source_root = root.resolve()
    names = (
        "scidiscovery.operations.invoke",
        "scidiscovery.general_science_components",
        "scidiscovery.general_science_experiment_components",
        "curve_score.operation_transforms",
        "tcad_artifact.operation_transforms",
        "ingaas_fig4.plugin",
    )
    resolved: dict[str, str] = {}
    for name in names:
        module = importlib.import_module(name)
        path = Path(module.__file__).resolve()
        try:
            relative = path.relative_to(source_root)
        except ValueError as error:
            raise AssertionError(
                f"production module {name} was loaded outside {source_root}: {path}"
            ) from error
        resolved[name] = relative.as_posix()
    return resolved


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    catalog = _catalog()
    scenarios = _scenarios(catalog)
    guard_probes = (_experiment_lineage_probe(),)
    actual = {
        operation_id
        for operation_id in catalog.operation_ids()
        if catalog.operation(operation_id).spec.executor.kind == "transform"
    }
    # This corpus seals behavior retained unchanged from M2. The E1 figure
    # topology has dedicated source-binding, review, guard, and determinism tests.
    actual.discard("science.figure.evidence.materialize.v1")
    actual.discard("scidiscovery.curve-bundle.figure-evidence.v2")
    declared = {scenario.operation_id for scenario in scenarios}
    removed_scientific_state = {
        "science.knowledge.update.diagnosis.v1",
        "science.knowledge.update.validation.v1",
    }
    if actual not in (declared, declared | removed_scientific_state):
        raise AssertionError(
            "retained transform corpus differs from catalog: "
            f"missing={sorted(declared-actual)}, "
            f"unexpected={sorted(actual-declared-removed_scientific_state)}"
        )
    guarded = {
        item.operation_id
        for item in scenarios
        if catalog.operation(item.operation_id).spec.guards
    }
    exercised_guards = {
        item.operation_id for item in scenarios if item.negative_edge is not None
    } | {item.operation_id for item in guard_probes}
    if guarded != exercised_guards:
        raise AssertionError(
            "guard corpus differs from catalog: "
            f"missing={sorted(guarded-exercised_guards)}, "
            f"extra={sorted(exercised_guards-guarded)}"
        )
    source_files, source_lines, source_digest = _source_digest(args.source_root)
    result = {
        "schema_version": 1,
        "source": {
            "files": source_files,
            "lines": source_lines,
            "digest": source_digest,
        },
        "catalog_digest": catalog.digest(),
        "catalog_transform_ids": sorted(actual),
        "loaded_modules": _loaded_production_modules(args.source_root),
        "transform_count": len(scenarios),
        "guard_count": sum(bool(catalog.operation(item.operation_id).spec.guards) for item in scenarios),
        "guard_probes": [
            _run_guard_probe(args.work_root, catalog, item) for item in guard_probes
        ],
        "operations": [
            _run_scenario(args.work_root, catalog, scenario)
            for scenario in scenarios
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_json(result))


if __name__ == "__main__":
    main()
