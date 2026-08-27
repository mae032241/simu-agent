"""Frozen deterministic baseline-recovery scorer for the Fig.4 InGaAs lane."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from bisect import bisect_right
from typing import Mapping

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.transforms import TransformOutput
from tcad_artifact.project_packager import DeckProjectDraft


FIG4_BASELINE_RECOVERY_PROFILE = "ingaas.fig4-baseline-recovery.v2"
FLOOR = 1.0e10
LEVELS = (1.0e19, 1.0e18, 1.0e17)


class InGaAsFig4TransformAdapter:
    @staticmethod
    def supports_transform_profile(profile: str) -> bool:
        return profile == FIG4_BASELINE_RECOVERY_PROFILE

    @staticmethod
    def required_input_parentage(profile: str) -> tuple[tuple[str, str], ...]:
        return ()

    @staticmethod
    def transform(
        *, profile: str, inputs: Mapping[str, bytes]
    ) -> tuple[TransformOutput, ...]:
        if profile != FIG4_BASELINE_RECOVERY_PROFILE:
            raise ValueError("unsupported InGaAs Fig.4 transform profile")
        expected = {
            "scorer_project",
            "curve_bundle",
            "target_metrics",
            "historical_baseline",
            "candidate_profile",
        }
        if set(inputs) != expected:
            raise ValueError("Fig.4 baseline scorer input set is incomplete")
        result = score_baseline_recovery(inputs)
        return (
            TransformOutput(
                label="primary",
                content=canonical_json(result),
                kind="metric_report",
                schema="ingaas.fig4-baseline-recovery.v2",
                payload_schema_version=1,
                media_type="application/json",
            ),
        )


def score_baseline_recovery(inputs: Mapping[str, bytes]) -> dict[str, object]:
    project = DeckProjectDraft.model_validate_json(inputs["scorer_project"], strict=True)
    files = {item.relative_path: item.content for item in project.files}
    try:
        contract_raw = files["scoring/SCORER_CONTRACT.v2.json"].encode("utf-8")
    except KeyError as error:
        raise ValueError("scorer project has no normative Fig.4 contract") from error
    contract = json.loads(contract_raw)
    if contract.get("scorer_version") != "2.0.0":
        raise ValueError("Fig.4 scorer contract version differs")
    identity = contract["immutable_input_identity"]
    _require_digest(inputs["curve_bundle"], identity["curve_bundle"]["supplied_sha256"])
    _require_digest(inputs["target_metrics"], identity["target_metrics"]["supplied_sha256"])

    reader = csv.DictReader(io.StringIO(inputs["curve_bundle"].decode("utf-8")))
    required_columns = identity["curve_bundle"]["required_columns_in_order"]
    if reader.fieldnames != required_columns:
        raise ValueError("curve bundle columns differ from the frozen contract")
    frozen = [row for row in reader if row["material"] == "ingaas"]
    if len(frozen) != identity["curve_bundle"]["ingaas_row_count"]:
        raise ValueError("curve bundle InGaAs row count differs")
    depths = [float(row["depth_um"]) for row in frozen]
    if depths != sorted(depths) or len(depths) != len(set(depths)):
        raise ValueError("curve bundle depth grid is not strictly increasing")
    target_logs = [math.log10(max(float(row["target"]), FLOOR)) for row in frozen]
    bundled_baseline_logs = [
        math.log10(max(float(row["baseline"]), FLOOR)) for row in frozen
    ]
    bundled_candidate_logs = [
        math.log10(max(float(row["candidate"]), FLOOR)) for row in frozen
    ]
    _validate_registered_metrics(
        json.loads(inputs["target_metrics"]),
        depths,
        target_logs,
        bundled_baseline_logs,
        bundled_candidate_logs,
        identity["identity_reproduction"],
    )

    baseline = _read_plx(inputs["historical_baseline"])
    candidate = _read_plx(inputs["candidate_profile"])
    required_fields = contract["runtime_artifact_requirements"]["required_plx_fields"]
    for label, payload in (("baseline", baseline), ("candidate", candidate)):
        missing = [field for field in required_fields if field not in payload]
        if missing:
            raise ValueError(f"{label} profile is missing PLX fields: {missing}")
        _validate_raw(payload["ZnTotal"], label)

    baseline_logs = _interpolate(baseline["ZnTotal"], depths)
    candidate_logs = _interpolate(candidate["ZnTotal"], depths)
    residuals = [right - left for left, right in zip(baseline_logs, candidate_logs)]
    baseline_metrics = _curve_metrics(depths, baseline_logs, target_logs)
    candidate_metrics = _curve_metrics(depths, candidate_logs, target_logs)
    crossing_errors = {
        level: 1000.0
        * (
            candidate_metrics["crossings_um"][level]
            - baseline_metrics["crossings_um"][level]
        )
        for level in baseline_metrics["crossings_um"]
    }
    width_error = (
        candidate_metrics["width_1e18_to_1e17_nm"]
        - baseline_metrics["width_1e18_to_1e17_nm"]
    )
    gate = contract["score_definitions"]["baseline_recovery"]
    checks = {
        "full_rms": _rms(residuals) <= gate["full_rms_max_decade"],
        "max_abs_residual": max(map(abs, residuals))
        <= gate["full_max_abs_residual_max_decade"],
        "crossings": all(
            abs(value) <= gate["each_crossing_absolute_error_max_nm"]
            for value in crossing_errors.values()
        ),
        "lower_width": abs(width_error)
        <= gate["width_1e18_to_1e17_absolute_error_max_nm"],
        "target_front_rms": abs(
            candidate_metrics["target_front_rms_decade"]
            - baseline_metrics["target_front_rms_decade"]
        )
        <= gate["target_front_rms_absolute_difference_max_decade"],
        "target_full_rms": abs(
            candidate_metrics["target_full_rms_decade"]
            - baseline_metrics["target_full_rms_decade"]
        )
        <= gate["target_full_rms_absolute_difference_max_decade"],
    }
    identity_residual = [
        left - right
        for left, right in zip(baseline_logs, bundled_baseline_logs, strict=True)
    ]
    return {
        "schema_version": 1,
        "scorer_version": contract["scorer_version"],
        "input_digests": {
            name: hashlib.sha256(inputs[name]).hexdigest() for name in sorted(inputs)
        },
        "raw_baseline_reproduces_frozen_curve_bundle": {
            "rms_decade": _rms(identity_residual),
            "max_abs_residual_decade": max(map(abs, identity_residual)),
            "pass_1e_minus_9_decade": max(map(abs, identity_residual)) <= 1.0e-9,
        },
        "baseline_recovery": {
            "full_rms_decade": _rms(residuals),
            "max_abs_residual_decade": max(map(abs, residuals)),
            "crossing_errors_nm": crossing_errors,
            "lower_width_error_nm": width_error,
            "target_front_rms_difference_decade": (
                candidate_metrics["target_front_rms_decade"]
                - baseline_metrics["target_front_rms_decade"]
            ),
            "target_full_rms_difference_decade": (
                candidate_metrics["target_full_rms_decade"]
                - baseline_metrics["target_full_rms_decade"]
            ),
            "checks": checks,
            "pass": all(checks.values()),
        },
        "baseline_metrics": baseline_metrics,
        "candidate_metrics": candidate_metrics,
        "residual_regions_above_0p02_decade": _contiguous_regions(
            depths, residuals, 0.02
        ),
        "interpretation_boundary": (
            "This deterministic report localizes and reproduces the discrepancy; "
            "it does not attribute causality or accept a physical model."
        ),
    }


def _require_digest(raw: bytes, expected: str) -> None:
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("frozen Fig.4 input digest differs from scorer contract")


def _validate_registered_metrics(
    registered: dict[str, object],
    depths: list[float],
    target_logs: list[float],
    baseline_logs: list[float],
    candidate_logs: list[float],
    contract: dict[str, object],
) -> None:
    material = registered["materials"]["ingaas"]
    tolerance = float(contract["maximum_absolute_difference_decade"])
    for name, logs in (("baseline", baseline_logs), ("candidate", candidate_logs)):
        computed = _curve_metrics(depths, logs, target_logs)
        supplied = material[name]
        for computed_key, supplied_key in (
            ("target_front_rms_decade", "front_ge_1e17_RMS_decade"),
            ("target_full_rms_decade", "full_RMS_decade"),
        ):
            if abs(computed[computed_key] - float(supplied[supplied_key])) > tolerance:
                raise ValueError("registered Fig.4 target metric is not reproducible")


def _read_plx(raw: bytes) -> dict[str, list[tuple[float, float]]]:
    data: dict[str, list[tuple[float, float]]] = {}
    current: str | None = None
    for source in raw.decode("utf-8").splitlines():
        line = source.strip()
        if not line:
            continue
        if line.startswith('"') and line.endswith('"'):
            current = line[1:-1]
            data[current] = []
            continue
        fields = line.split()
        if current is not None and len(fields) == 2:
            data[current].append((float(fields[0]), float(fields[1])))
    return data


def _validate_raw(rows: list[tuple[float, float]], label: str) -> None:
    if len(rows) < 2:
        raise ValueError(f"{label}: fewer than two ZnTotal samples")
    for index, (depth, value) in enumerate(rows):
        if not (math.isfinite(depth) and math.isfinite(value)) or value <= 0:
            raise ValueError(f"{label}: invalid ZnTotal sample at index {index}")
        if index and depth <= rows[index - 1][0]:
            raise ValueError(f"{label}: non-increasing depth at index {index}")


def _interpolate(
    rows: list[tuple[float, float]], depths: list[float]
) -> list[float]:
    source_x = [row[0] for row in rows]
    if depths[0] < source_x[0] or depths[-1] > source_x[-1]:
        raise ValueError("raw curve does not cover the frozen scoring grid")
    values: list[float] = []
    for depth in depths:
        upper = bisect_right(source_x, depth)
        if upper == 0:
            lower, upper = 0, 1
        elif upper == len(rows):
            lower, upper = len(rows) - 2, len(rows) - 1
        else:
            lower = upper - 1
        x0, y0 = rows[lower]
        x1, y1 = rows[upper]
        fraction = (depth - x0) / (x1 - x0)
        a = math.log10(max(y0, FLOOR))
        b = math.log10(max(y1, FLOOR))
        values.append(a + fraction * (b - a))
    return values


def _rms(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values) / len(values))


def _crossing(depths: list[float], logs: list[float], level: float) -> float:
    target = math.log10(level)
    exact = [index for index, value in enumerate(logs) if value == target]
    brackets = [
        index
        for index in range(len(logs) - 1)
        if logs[index] > target > logs[index + 1]
        or logs[index] < target < logs[index + 1]
    ]
    if len(exact) == 1 and not brackets:
        return depths[exact[0]]
    if len(brackets) != 1 or exact:
        raise ValueError(f"non-unique crossing for {level:.0e}")
    index = brackets[0]
    fraction = (target - logs[index]) / (logs[index + 1] - logs[index])
    return depths[index] + fraction * (depths[index + 1] - depths[index])


def _curve_metrics(
    depths: list[float], logs: list[float], target_logs: list[float]
) -> dict[str, object]:
    crossings = {f"{level:.0e}": _crossing(depths, logs, level) for level in LEVELS}
    front = [index for index, value in enumerate(target_logs) if value >= 17.0]
    residuals = [value - target_logs[index] for index, value in enumerate(logs)]
    return {
        "crossings_um": crossings,
        "width_1e18_to_1e17_nm": 1000.0
        * (crossings["1e+17"] - crossings["1e+18"]),
        "target_front_rms_decade": _rms([residuals[index] for index in front]),
        "target_full_rms_decade": _rms(residuals),
    }


def _contiguous_regions(
    depths: list[float], residuals: list[float], threshold: float
) -> list[dict[str, object]]:
    regions: list[dict[str, object]] = []
    start: int | None = None
    for index, residual in enumerate(residuals + [0.0]):
        selected = index < len(residuals) and abs(residual) > threshold
        if selected and start is None:
            start = index
        if not selected and start is not None:
            stop = index
            segment = residuals[start:stop]
            peak = max(range(start, stop), key=lambda item: abs(residuals[item]))
            regions.append(
                {
                    "start_depth_um": depths[start],
                    "end_depth_um": depths[stop - 1],
                    "point_count": stop - start,
                    "rms_decade": _rms(segment),
                    "peak_depth_um": depths[peak],
                    "peak_signed_residual_decade": residuals[peak],
                }
            )
            start = None
    return regions


__all__ = [
    "FIG4_BASELINE_RECOVERY_PROFILE",
    "InGaAsFig4TransformAdapter",
    "score_baseline_recovery",
]
