from __future__ import annotations

import csv
import copy
import hashlib
import io
import json
from pathlib import Path

import pytest

from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from curve_figure_evidence.plugin import PLUGIN as FIGURE_PLUGIN
from ingaas_fig4.figure_compilation import OPERATION as FIGURE_COMPILE_OPERATION
from ingaas_fig4.plugin import PLUGIN as FIG4_PLUGIN
from ingaas_fig4.transform_adapter import FIG4_BASELINE_RECOVERY_OPERATION
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as SCIENCE_PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.invoke import (
    execute_compiled_transform,
    InvocationArtifact,
    OperationInvocationError,
    preflight_operation,
)
from tcad_artifact.plugin import PLUGIN as TCAD_PLUGIN
from tcad_artifact.project_packager import (
    DeckFile,
    DeckProjectDraft,
    ProjectResourceLimits,
)


def _curve_table() -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("material", "depth_um", "target", "baseline", "candidate"))
    for index, target_log in enumerate((20.0, 19.0, 18.0, 17.0, 16.0)):
        target = 10.0**target_log
        candidate = 10.0 ** (target_log + 0.01)
        writer.writerow(("ingaas", index / 10.0, target, target, candidate))
    return output.getvalue().encode()


def _target_metrics() -> bytes:
    return json.dumps(
        {
            "materials": {
                "ingaas": {
                    "baseline": {
                        "front_ge_1e17_RMS_decade": 0.0,
                        "full_RMS_decade": 0.0,
                    },
                    "candidate": {
                        "front_ge_1e17_RMS_decade": 0.01,
                        "full_RMS_decade": 0.01,
                    },
                }
            }
        },
        separators=(",", ":"),
    ).encode()


def _plx(*, offset: float) -> bytes:
    rows = [
        (index / 10.0, 10.0 ** (target_log + offset))
        for index, target_log in enumerate((20.0, 19.0, 18.0, 17.0, 16.0))
    ]
    blocks = []
    for field in (
        "ZnTotal",
        "Zinc",
        "ZincConcentration",
        "ZincActiveConcentration",
        "xMoleFraction",
        "Potential",
    ):
        blocks.append(f'"{field}"')
        blocks.extend(f"{depth:.17g} {value:.17g}" for depth, value in rows)
    return ("\n".join(blocks) + "\n").encode()


def _project(curve_table: bytes, target_metrics: bytes) -> bytes:
    contract = {
        "scorer_version": "2.0.0",
        "immutable_input_identity": {
            "curve_bundle": {
                "required_columns_in_order": [
                    "material", "depth_um", "target", "baseline", "candidate"
                ],
                "supplied_sha256": hashlib.sha256(curve_table).hexdigest(),
                "ingaas_row_count": 5,
            },
            "target_metrics": {
                "supplied_sha256": hashlib.sha256(target_metrics).hexdigest()
            },
            "identity_reproduction": {
                "maximum_absolute_difference_decade": 1.0e-8
            },
        },
        "runtime_artifact_requirements": {
            "required_plx_fields": [
                "ZnTotal", "Zinc", "ZincConcentration",
                "ZincActiveConcentration", "xMoleFraction", "Potential",
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
        files=(
            DeckFile(
                relative_path="scoring/SCORER_CONTRACT.v2.json",
                content=json.dumps(contract, separators=(",", ":")),
            ),
        ),
        entrypoint="scoring/SCORER_CONTRACT.v2.json",
        expected_outputs=(),
        resource_limits=ProjectResourceLimits(
            wall_time_seconds=30,
            cpu_time_seconds=30,
            max_memory_bytes=64 * 1024 * 1024,
            max_output_bytes=1024 * 1024,
            max_processes=1,
        ),
    )
    return project.model_dump_json().encode()


def _payloads() -> dict[str, bytes]:
    curve_table = _curve_table()
    target_metrics = _target_metrics()
    return {
        "scorer_project": _project(curve_table, target_metrics),
        "curve_bundle": curve_table,
        "target_metrics": target_metrics,
        "historical_baseline": _plx(offset=0.0),
        "candidate_profile": _plx(offset=0.01),
    }


def _artifact(name: str, raw: bytes, schema: str, media_type: str) -> InvocationArtifact:
    digest = hashlib.sha256(raw).hexdigest()
    return InvocationArtifact(
        artifact_name=name,
        ref=ArtifactRef(
            artifact_id=f"art_{name}",
            sha256=digest,
            kind="test_input",
            schema_id=schema,
        ),
        schema_id=schema,
        media_type=media_type,
        size_bytes=len(raw),
    )


def _bound(payloads: dict[str, bytes]):
    artifacts = {
        "scorer_project": (
            _artifact(
                "scorer_project", payloads["scorer_project"],
                "tcad.deck-project.v1", "application/json",
            ),
        ),
        "curve_bundle": (
            _artifact(
                "curve_bundle", payloads["curve_bundle"],
                "ingaas.fig4-frozen-curve-table.v1", "text/csv",
            ),
        ),
        "target_metrics": (
            _artifact(
                "target_metrics", payloads["target_metrics"],
                "ingaas.fig4-target-metrics.v1", "application/json",
            ),
        ),
        "historical_baseline": (
            _artifact(
                "historical_baseline", payloads["historical_baseline"],
                "ingaas.fig4-zinc-profile-plx.v1", "application/x-synopsys-plx",
            ),
        ),
        "candidate_profile": (
            _artifact(
                "candidate_profile", payloads["candidate_profile"],
                "ingaas.fig4-zinc-profile-plx.v1", "application/x-synopsys-plx",
            ),
        ),
    }
    catalog = compile_catalog(
        (CORE_PLUGIN, SCIENCE_PLUGIN, TCAD_PLUGIN, CURVE_PLUGIN, FIGURE_PLUGIN, FIG4_PLUGIN)
    )
    return preflight_operation(
        catalog.operation(FIG4_BASELINE_RECOVERY_OPERATION),
        name="fig4_baseline_recovery",
        artifacts_by_port=artifacts,
        instruction=None,
    )


def test_optional_fig4_plugin_adds_two_support_operations_without_digest_drift() -> None:
    baseline = compile_catalog((CORE_PLUGIN, SCIENCE_PLUGIN, TCAD_PLUGIN, CURVE_PLUGIN, FIGURE_PLUGIN))
    extended = compile_catalog(
        (CORE_PLUGIN, SCIENCE_PLUGIN, TCAD_PLUGIN, CURVE_PLUGIN, FIGURE_PLUGIN, FIG4_PLUGIN)
    )
    assert set(extended.operation_ids()) - set(baseline.operation_ids()) == {
        FIG4_BASELINE_RECOVERY_OPERATION, FIGURE_COMPILE_OPERATION.operation_id,
    }
    assert extended.operation(FIG4_BASELINE_RECOVERY_OPERATION).spec.catalog_scope == "support"
    assert {
        operation_id: extended.operation(operation_id).digest
        for operation_id in baseline.operation_ids()
    } == {
        operation_id: baseline.operation(operation_id).digest
        for operation_id in baseline.operation_ids()
    }


def test_compiled_fig4_operation_executes_frozen_scorer_and_validates_output(
    monkeypatch,
) -> None:
    payloads = _payloads()
    bound = _bound(payloads)
    inputs = {
        item.source_name: payloads[item.artifact_name] for item in bound.inputs
    }
    outputs = execute_compiled_transform(
        bound,
        inputs,
    )
    report = json.loads(outputs[0].content)
    assert outputs[0].port_name == "metric_report"
    assert report["baseline_recovery"]["pass"] is False
    assert report["raw_baseline_reproduces_frozen_curve_bundle"][
        "pass_1e_minus_9_decade"
    ] is True

    import ingaas_fig4.plugin as plugin

    original = plugin.score_baseline_recovery
    monkeypatch.setattr(
        plugin,
        "score_baseline_recovery",
        lambda inputs: {"schema_version": 1},
    )
    with pytest.raises(ValueError) as rejected:
        execute_compiled_transform(bound, inputs)
    assert not isinstance(rejected.value, OperationInvocationError)
    monkeypatch.setattr(plugin, "score_baseline_recovery", original)


def test_compiled_fig4_operation_rejects_modified_frozen_reference() -> None:
    payloads = _payloads()
    bound = _bound(payloads)
    payloads["curve_bundle"] += b"\n"
    with pytest.raises(OperationInvocationError, match="executor_component_failed"):
        execute_compiled_transform(
            bound,
            {
                item.source_name: payloads[item.artifact_name]
                for item in bound.inputs
            },
        )


def test_fig4_result_validator_rejects_every_published_nested_shape() -> None:
    import ingaas_fig4.plugin as plugin

    valid = plugin.score_baseline_recovery(_payloads())
    plugin.RESULT_VALIDATOR.implementation(
        json.dumps(valid, allow_nan=False, separators=(",", ":")).encode()
    )

    malformed = []
    for field in (
        "raw_baseline_reproduces_frozen_curve_bundle",
        "baseline_metrics",
        "candidate_metrics",
    ):
        report = copy.deepcopy(valid)
        report[field] = None
        malformed.append(report)

    report = copy.deepcopy(valid)
    report["residual_regions_above_0p02_decade"] = "not-a-region-list"
    malformed.append(report)

    report = copy.deepcopy(valid)
    del report["baseline_recovery"]["crossing_errors_nm"]["1e+17"]
    malformed.append(report)

    report = copy.deepcopy(valid)
    report["baseline_metrics"]["target_full_rms_decade"] = float("nan")
    malformed.append(report)

    for boundary in ("The physical model is accepted.", "   "):
        report = copy.deepcopy(valid)
        report["interpretation_boundary"] = boundary
        malformed.append(report)

    for path in (
        ("raw_baseline_reproduces_frozen_curve_bundle", "rms_decade"),
        ("baseline_metrics", "target_full_rms_decade"),
        ("baseline_recovery", "full_rms_decade"),
    ):
        report = copy.deepcopy(valid)
        report[path[0]][path[1]] = -1.0
        malformed.append(report)

    report = copy.deepcopy(valid)
    report["raw_baseline_reproduces_frozen_curve_bundle"][
        "pass_1e_minus_9_decade"
    ] = False
    malformed.append(report)

    report = copy.deepcopy(valid)
    report["baseline_recovery"]["pass"] = not report["baseline_recovery"]["pass"]
    malformed.append(report)

    report = copy.deepcopy(valid)
    report["baseline_recovery"]["checks"] = {
        name: True for name in report["baseline_recovery"]["checks"]
    }
    report["baseline_recovery"]["pass"] = False
    malformed.append(report)

    report = copy.deepcopy(valid)
    report["residual_regions_above_0p02_decade"] = [
        {
            "start_depth_um": 0.1,
            "end_depth_um": 0.2,
            "point_count": 2,
            "rms_decade": 0.03,
            "peak_depth_um": 0.3,
            "peak_signed_residual_decade": 0.03,
        }
    ]
    malformed.append(report)

    report = copy.deepcopy(valid)
    report["residual_regions_above_0p02_decade"] = [
        {
            "start_depth_um": 0.1,
            "end_depth_um": 0.2,
            "point_count": 2,
            "rms_decade": -0.03,
            "peak_depth_um": 0.2,
            "peak_signed_residual_decade": 0.03,
        }
    ]
    malformed.append(report)

    for report in malformed:
        with pytest.raises(ValueError):
            plugin.RESULT_VALIDATOR.implementation(
                json.dumps(report, allow_nan=True, separators=(",", ":")).encode()
            )


def test_project_semantics_are_absent_from_general_and_domain_shared_code() -> None:
    repository = Path(__file__).resolve().parents[2]
    sources = [
        repository / "src" / "scidiscovery",
        repository / "plugins" / "tcad_artifact" / "tcad_artifact",
        repository / "plugins" / "curve_score" / "curve_score",
    ]
    forbidden = ("ingaas", "fig.4", "fig4-baseline")
    for source in sources:
        for path in source.rglob("*.py"):
            content = path.read_text(encoding="utf-8").lower()
            assert all(token not in content for token in forbidden), path
    scheduler = (repository / "roles" / "scheduler.md").read_text(encoding="utf-8")
    assert all(token not in scheduler.lower() for token in forbidden)
