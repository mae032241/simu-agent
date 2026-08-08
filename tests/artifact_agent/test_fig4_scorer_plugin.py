from __future__ import annotations

import csv
import hashlib
import io
import json
import math

import pytest

from ingaas_fig4.transform_adapter import (
    FIG4_BASELINE_RECOVERY_PROFILE,
    InGaAsFig4TransformAdapter,
    score_baseline_recovery,
)
from tcad_artifact.project_packager import DeckFile, DeckProjectDraft, ProjectResourceLimits


def _curve_bundle() -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("material", "depth_um", "target", "baseline", "candidate"))
    for index, target_log in enumerate((20.0, 19.0, 18.0, 17.0, 16.0)):
        target = 10.0**target_log
        candidate = 10.0 ** (target_log + 0.01)
        writer.writerow(("ingaas", index / 10.0, target, target, candidate))
    return output.getvalue().encode("utf-8")


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
    ).encode("utf-8")


def _plx(*, log_offset: float) -> bytes:
    rows = [
        (index / 10.0, 10.0 ** (target_log + log_offset))
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
    return ("\n".join(blocks) + "\n").encode("utf-8")


def _scorer_project(curve_bundle: bytes, target_metrics: bytes) -> bytes:
    contract = {
        "scorer_version": "2.0.0",
        "immutable_input_identity": {
            "curve_bundle": {
                "required_columns_in_order": [
                    "material",
                    "depth_um",
                    "target",
                    "baseline",
                    "candidate",
                ],
                "supplied_sha256": hashlib.sha256(curve_bundle).hexdigest(),
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
    return project.model_dump_json().encode("utf-8")


def _payloads() -> dict[str, bytes]:
    curve_bundle = _curve_bundle()
    target_metrics = _target_metrics()
    return {
        "scorer_project": _scorer_project(curve_bundle, target_metrics),
        "curve_bundle": curve_bundle,
        "target_metrics": target_metrics,
        "historical_baseline": _plx(log_offset=0.0),
        "candidate_profile": _plx(log_offset=0.01),
    }


def test_synthetic_fig4_plugin_reproduces_a_known_baseline_failure() -> None:
    result = score_baseline_recovery(_payloads())
    gate = result["baseline_recovery"]
    assert gate["pass"] is False
    assert gate["full_rms_decade"] == pytest.approx(0.01)
    assert gate["max_abs_residual_decade"] == pytest.approx(0.01)
    assert gate["crossing_errors_nm"] == pytest.approx(
        {"1e+19": 1.0, "1e+18": 1.0, "1e+17": 1.0}
    )
    assert result["raw_baseline_reproduces_frozen_curve_bundle"][
        "pass_1e_minus_9_decade"
    ] is True
    assert math.isclose(gate["lower_width_error_nm"], 0.0, abs_tol=1.0e-10)


def test_synthetic_fig4_plugin_rejects_modified_reference_data() -> None:
    payloads = _payloads()
    payloads["curve_bundle"] += b"\n"
    with pytest.raises(ValueError, match="digest differs"):
        score_baseline_recovery(payloads)


def test_synthetic_fig4_plugin_emits_a_metric_not_a_scientific_verdict() -> None:
    output = InGaAsFig4TransformAdapter.transform(
        profile=FIG4_BASELINE_RECOVERY_PROFILE,
        inputs=_payloads(),
    )
    assert len(output) == 1
    assert output[0].kind == "metric_report"
    assert output[0].schema == FIG4_BASELINE_RECOVERY_PROFILE
