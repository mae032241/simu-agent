#!/usr/bin/env python3
"""Deterministic, configuration-calibrated scientific plot digitizer.

This intentionally does not do OCR or semantic curve discovery.  A JSON spec
binds the exact image and supplies all panel, calibration, descriptor, seed,
and identity information needed to follow raster pixels with Pillow.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import sys
import tempfile
from collections import deque
from pathlib import Path
from typing import Any, Iterable

try:
    from PIL import Image, ImageDraw
except ImportError as exc:  # pragma: no cover - exercised only without Pillow
    raise SystemExit(
        "digitize_plot.py requires Pillow in the execution environment"
    ) from exc


SPEC_VERSION = "scidiscovery.plot-digitization-spec.v1"
EVIDENCE_VERSION = "scidiscovery.figure-evidence-manifest.v1"
SAFE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
IDENTITY_COLORS = (
    "#e41a1c",
    "#377eb8",
    "#4daf4a",
    "#984ea3",
    "#ff7f00",
    "#a65628",
    "#f781bf",
    "#17becf",
)


class SpecError(ValueError):
    """Raised before any output is created when the immutable spec is invalid."""


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SpecError(f"{where} must be an object")
    return value


def _sequence(value: Any, where: str) -> list[Any]:
    if not isinstance(value, list):
        raise SpecError(f"{where} must be an array")
    return value


def _number(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SpecError(f"{where} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise SpecError(f"{where} must be a finite number")
    return result


def _integer(value: Any, where: str, *, minimum: int | None = None) -> int:
    result = _number(value, where)
    if not result.is_integer():
        raise SpecError(f"{where} must be an integer")
    integer = int(result)
    if minimum is not None and integer < minimum:
        raise SpecError(f"{where} must be at least {minimum}")
    return integer


def _key(value: Any, where: str) -> str:
    if not isinstance(value, str) or not SAFE_KEY.fullmatch(value):
        raise SpecError(f"{where} must match {SAFE_KEY.pattern}")
    return value


def _bbox(value: Any, where: str, width: int, height: int) -> tuple[int, int, int, int]:
    items = _sequence(value, where)
    if len(items) != 4:
        raise SpecError(f"{where} must have four coordinates")
    coords = tuple(_integer(item, where) for item in items)
    left, top, right, bottom = coords
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise SpecError(f"{where} lies outside the {width}x{height} image")
    return left, top, right, bottom


def _color(value: Any, where: str) -> tuple[int, int, int]:
    if isinstance(value, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))
    if isinstance(value, list) and len(value) == 3:
        channels = tuple(int(_number(item, where)) for item in value)
        if all(0 <= item <= 255 for item in channels):
            return channels
    raise SpecError(f"{where} must be #RRGGBB or three 0..255 channels")


def _seed(value: Any, where: str, width: int, height: int) -> tuple[float, float]:
    if isinstance(value, dict):
        value = value.get("pixel")
    items = _sequence(value, where)
    if len(items) != 2:
        raise SpecError(f"{where} must have x and y")
    x = _number(items[0], where)
    y = _number(items[1], where)
    if not (0 <= x < width and 0 <= y < height):
        raise SpecError(f"{where} lies outside the image")
    return x, y


def _axis(value: Any, where: str) -> dict[str, Any]:
    axis = _mapping(value, where)
    scale = axis.get("scale")
    if scale not in {"linear", "log10"}:
        raise SpecError(f"{where}.scale must be linear or log10")
    unit = axis.get("unit")
    if not isinstance(unit, str) or not unit.strip():
        raise SpecError(f"{where}.unit must be a non-empty string")
    pixel_min = _number(axis.get("pixel_min"), f"{where}.pixel_min")
    pixel_max = _number(axis.get("pixel_max"), f"{where}.pixel_max")
    value_min = _number(axis.get("value_min"), f"{where}.value_min")
    value_max = _number(axis.get("value_max"), f"{where}.value_max")
    error = _number(
        axis.get("reprojection_error_px", 0.5),
        f"{where}.reprojection_error_px",
    )
    if pixel_min == pixel_max or value_min == value_max:
        raise SpecError(f"{where} endpoints must differ")
    if scale == "log10" and (value_min <= 0 or value_max <= 0):
        raise SpecError(f"{where} log10 endpoints must be positive")
    if error < 0:
        raise SpecError(f"{where}.reprojection_error_px cannot be negative")
    return {
        "scale": scale,
        "unit": unit,
        "pixel_min": pixel_min,
        "pixel_max": pixel_max,
        "value_min": value_min,
        "value_max": value_max,
        "reprojection_error_px": error,
    }


def _tracking(value: Any, where: str) -> dict[str, Any]:
    raw = _mapping(value, where)
    result = dict(raw)
    nonnegative_floats = (
        "max_vertical_step_px",
        "max_gap_vertical_displacement_px",
        "max_guide_distance_px",
        "ambiguity_margin_px",
        "max_seed_distance_px",
        "skip_penalty",
        "overdraw_candidate_endpoint_distance_px",
    )
    nonnegative_ints = (
        "max_gap_px",
        "seed_radius_px",
        "plot_border_exclusion_px",
        "min_component_pixels",
        "max_component_pixels",
    )
    fractions = ("min_visible_fraction", "max_ambiguous_fraction", "guide_weight")
    positive_ints = ("min_points", "expected_point_count")
    for key in nonnegative_floats:
        if key in raw:
            result[key] = _number(raw[key], f"{where}.{key}")
            if result[key] < 0:
                raise SpecError(f"{where}.{key} cannot be negative")
    for key in nonnegative_ints:
        if key in raw:
            result[key] = _integer(raw[key], f"{where}.{key}", minimum=0)
    for key in fractions:
        if key in raw:
            result[key] = _number(raw[key], f"{where}.{key}")
            if not 0 <= result[key] <= 1:
                raise SpecError(f"{where}.{key} must be between zero and one")
    for key in positive_ints:
        if key in raw:
            result[key] = _integer(raw[key], f"{where}.{key}", minimum=1)
    if result.get("max_vertical_step_px", 12) == 0:
        raise SpecError(f"{where}.max_vertical_step_px must be positive")
    if result.get("max_component_pixels", 10000) < result.get("min_component_pixels", 2):
        raise SpecError(f"{where}.max_component_pixels is below min_component_pixels")
    return result


def _eligibility(
    value: Any,
    where: str,
    domain: tuple[int, int],
) -> dict[str, Any]:
    raw = _mapping(value, where)
    default_eligible = raw.get("default_eligible", False)
    if not isinstance(default_eligible, bool):
        raise SpecError(f"{where}.default_eligible must be boolean")

    def ranges(name: str) -> list[tuple[int, int]]:
        result = []
        for index, item in enumerate(_sequence(raw.get(name, []), f"{where}.{name}")):
            parts = _sequence(item, f"{where}.{name}[{index}]")
            if len(parts) != 2:
                raise SpecError(f"{where}.{name}[{index}] needs two endpoints")
            interval = (
                _integer(parts[0], f"{where}.{name}[{index}]"),
                _integer(parts[1], f"{where}.{name}[{index}]"),
            )
            if not domain[0] <= interval[0] < interval[1] <= domain[1]:
                raise SpecError(f"{where}.{name}[{index}] is outside the trace domain")
            result.append(interval)
        return sorted(result)

    ineligible_regions: list[dict[str, Any]] = []
    for index, item in enumerate(
        _sequence(
            raw.get("ineligible_pixel_regions", []),
            f"{where}.ineligible_pixel_regions",
        )
    ):
        region_where = f"{where}.ineligible_pixel_regions[{index}]"
        region = _mapping(item, region_where)
        parts = _sequence(region.get("pixel_range"), f"{region_where}.pixel_range")
        if len(parts) != 2:
            raise SpecError(f"{region_where}.pixel_range needs two endpoints")
        interval = (
            _integer(parts[0], f"{region_where}.pixel_range[0]"),
            _integer(parts[1], f"{region_where}.pixel_range[1]"),
        )
        if not domain[0] <= interval[0] < interval[1] <= domain[1]:
            raise SpecError(f"{region_where}.pixel_range is outside the trace domain")
        reason = _key(region.get("reason"), f"{region_where}.reason")
        ineligible_regions.append({"pixel_range": interval, "reason": reason})

    for previous, current in zip(
        sorted(ineligible_regions, key=lambda item: item["pixel_range"]),
        sorted(ineligible_regions, key=lambda item: item["pixel_range"])[1:],
    ):
        if current["pixel_range"][0] < previous["pixel_range"][1]:
            raise SpecError(f"{where}.ineligible_pixel_regions must not overlap")

    return {
        "default_eligible": default_eligible,
        "ineligible_pixel_ranges": ranges("ineligible_pixel_ranges"),
        "ineligible_pixel_regions": sorted(
            ineligible_regions, key=lambda item: item["pixel_range"]
        ),
        "below_detection_limit_pixel_ranges": ranges(
            "below_detection_limit_pixel_ranges"
        ),
    }


def _normalize_spec(
    raw: Any, spec_path: Path
) -> tuple[dict[str, Any], Path, list[dict[str, Any]]]:
    spec = _mapping(raw, "spec")
    if spec.get("schema_version") != SPEC_VERSION:
        raise SpecError(f"schema_version must be {SPEC_VERSION}")
    figure_key = _key(spec.get("figure_key"), "figure_key")
    source = _mapping(spec.get("source"), "source")
    source_name = source.get("source_name")
    figure = source.get("figure")
    page = source.get("page")
    if not isinstance(source_name, str) or not source_name.strip():
        raise SpecError("source.source_name must be a non-empty string")
    if not isinstance(figure, str) or not figure.strip():
        raise SpecError("source.figure must be a non-empty string")
    if not isinstance(page, (str, int)) or isinstance(page, bool):
        raise SpecError("source.page must be a string or integer")
    image_binding = _mapping(source.get("image"), "source.image")
    image_name = image_binding.get("path")
    if not isinstance(image_name, str) or not image_name:
        raise SpecError("source.image.path must be a non-empty string")
    image_path = Path(image_name)
    if not image_path.is_absolute():
        image_path = (spec_path.parent / image_path).resolve()
    if not image_path.is_file():
        raise SpecError(f"source image does not exist: {image_path}")
    expected_sha = image_binding.get("sha256")
    if not isinstance(expected_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
        raise SpecError("source.image.sha256 must be a lowercase SHA-256 digest")
    actual_sha = _sha256_file(image_path)
    if actual_sha != expected_sha:
        raise SpecError("source image SHA-256 does not match the immutable binding")
    expected_width = _integer(image_binding.get("width"), "source.image.width", minimum=1)
    expected_height = _integer(image_binding.get("height"), "source.image.height", minimum=1)
    with Image.open(image_path) as opened:
        actual_size = opened.size
    if actual_size != (expected_width, expected_height):
        raise SpecError(
            "source image dimensions do not match the immutable binding: "
            f"expected {(expected_width, expected_height)}, observed {actual_size}"
        )
    pdf_provenance: dict[str, Any] = {}
    if "pdf" in source:
        pdf_binding = _mapping(source["pdf"], "source.pdf")
        pdf_name = pdf_binding.get("path")
        if not isinstance(pdf_name, str) or not pdf_name:
            raise SpecError("source.pdf.path must be a non-empty string")
        pdf_path = Path(pdf_name)
        if not pdf_path.is_absolute():
            pdf_path = (spec_path.parent / pdf_path).resolve()
        if not pdf_path.is_file():
            raise SpecError(f"source PDF does not exist: {pdf_path}")
        pdf_sha = pdf_binding.get("sha256")
        if not isinstance(pdf_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", pdf_sha):
            raise SpecError("source.pdf.sha256 must be a lowercase SHA-256 digest")
        if _sha256_file(pdf_path) != pdf_sha:
            raise SpecError("source PDF SHA-256 does not match the immutable binding")
        pdf_page = pdf_binding.get("page")
        object_id = pdf_binding.get("object_id")
        if not isinstance(pdf_page, int) or isinstance(pdf_page, bool) or pdf_page < 1:
            raise SpecError("source.pdf.page must be a positive integer")
        if not isinstance(object_id, str) or not object_id.strip():
            raise SpecError("source.pdf.object_id must be a non-empty string")
        if isinstance(page, int) and page != pdf_page:
            raise SpecError("source.page and source.pdf.page must agree")
        pdf_provenance = {
            "pdf_sha256": pdf_sha,
            "pdf_page": pdf_page,
            "pdf_object": object_id,
        }

    normalized_panels: list[dict[str, Any]] = []
    panel_keys: set[str] = set()
    data_items: set[str] = set()
    panels = _sequence(spec.get("panels"), "panels")
    if not panels:
        raise SpecError("panels must not be empty")
    for panel_index, panel_value in enumerate(panels):
        where = f"panels[{panel_index}]"
        panel = _mapping(panel_value, where)
        panel_key = _key(panel.get("panel_key"), f"{where}.panel_key")
        if panel_key in panel_keys:
            raise SpecError(f"duplicate panel_key: {panel_key}")
        panel_keys.add(panel_key)
        citation = panel.get("citation")
        if not isinstance(citation, str) or not citation.strip():
            raise SpecError(f"{where}.citation must be a non-empty string")
        plot_bbox = _bbox(
            panel.get("plot_bbox"),
            f"{where}.plot_bbox",
            expected_width,
            expected_height,
        )
        axes_value = _mapping(panel.get("axis_calibration"), f"{where}.axis_calibration")
        axes = {
            "x": _axis(axes_value.get("x"), f"{where}.axis_calibration.x"),
            "y": _axis(axes_value.get("y"), f"{where}.axis_calibration.y"),
        }
        exclusions = [
            _bbox(item, f"{where}.exclusion_regions", expected_width, expected_height)
            for item in _sequence(panel.get("exclusion_regions", []), f"{where}.exclusion_regions")
        ]
        series_items: list[dict[str, Any]] = []
        series_keys: set[str] = set()
        for series_index, series_value in enumerate(
            _sequence(panel.get("series"), f"{where}.series")
        ):
            series_where = f"{where}.series[{series_index}]"
            series = _mapping(series_value, series_where)
            series_key = _key(series.get("series_key"), f"{series_where}.series_key")
            if series_key in series_keys:
                raise SpecError(f"duplicate series_key in {panel_key}: {series_key}")
            series_keys.add(series_key)
            label = series.get("label")
            if not isinstance(label, str) or not label.strip():
                raise SpecError(f"{series_where}.label must be a non-empty string")
            primitive = series.get("primitive_kind")
            if primitive not in {"line", "marker", "fit_segment"}:
                raise SpecError(
                    f"{series_where}.primitive_kind must be line, marker, or fit_segment"
                )
            descriptor = _mapping(series.get("descriptor"), f"{series_where}.descriptor")
            rgb = _color(descriptor.get("color"), f"{series_where}.descriptor.color")
            tolerance = _number(
                descriptor.get("color_tolerance", 24),
                f"{series_where}.descriptor.color_tolerance",
            )
            if not 0 <= tolerance <= 441.7:
                raise SpecError(f"{series_where}.descriptor.color_tolerance is out of range")
            style = descriptor.get("line_style", "solid")
            if style not in {"solid", "dashed", "dotted", "none"}:
                raise SpecError(f"{series_where}.descriptor.line_style is invalid")
            if primitive != "marker" and style == "none":
                raise SpecError(f"{series_where} line-like series needs a line_style")
            signature = _mapping(
                descriptor.get("style_signature", {}),
                f"{series_where}.descriptor.style_signature",
            )
            for signature_key in ("min_runs", "min_run_px", "max_run_px", "min_gap_px"):
                if signature_key in signature:
                    signature[signature_key] = _number(
                        signature[signature_key],
                        f"{series_where}.descriptor.style_signature.{signature_key}",
                    )
                    if signature[signature_key] < 0:
                        raise SpecError(
                            f"{series_where}.descriptor.style_signature.{signature_key} cannot be negative"
                        )
            seeds = [
                _seed(item, f"{series_where}.seeds", expected_width, expected_height)
                for item in _sequence(series.get("seeds", []), f"{series_where}.seeds")
            ]
            binding = _mapping(series.get("binding"), f"{series_where}.binding")
            binding_source = binding.get("source")
            if binding_source not in {"legend", "annotation"}:
                raise SpecError(
                    f"{series_where}.binding.source must be legend or annotation"
                )
            visible_label = binding.get("visible_label")
            if not isinstance(visible_label, str) or not visible_label.strip():
                raise SpecError(f"{series_where}.binding.visible_label is required")
            binding_bbox = _bbox(
                binding.get("bbox"),
                f"{series_where}.binding.bbox",
                expected_width,
                expected_height,
            )
            alternatives = binding.get("alternatives", [])
            if not isinstance(alternatives, list) or not all(
                isinstance(item, str) for item in alternatives
            ):
                raise SpecError(f"{series_where}.binding.alternatives must be strings")
            tracking = _tracking(series.get("tracking", {}), f"{series_where}.tracking")
            item_name = f"curve_tables/{panel_key}--{series_key}.csv"
            if item_name in data_items:
                raise SpecError(f"duplicate data item: {item_name}")
            data_items.add(item_name)
            pixel_range = series.get("pixel_range")
            if pixel_range is not None:
                parts = _sequence(pixel_range, f"{series_where}.pixel_range")
                if len(parts) != 2:
                    raise SpecError(f"{series_where}.pixel_range needs two endpoints")
                pixel_range = (
                    _integer(parts[0], f"{series_where}.pixel_range"),
                    _integer(parts[1], f"{series_where}.pixel_range"),
                )
                if not plot_bbox[0] <= pixel_range[0] < pixel_range[1] <= plot_bbox[2]:
                    raise SpecError(f"{series_where}.pixel_range is outside plot_bbox")
            series_exclusions = [
                _bbox(item, f"{series_where}.exclusion_regions", expected_width, expected_height)
                for item in _sequence(
                    series.get("exclusion_regions", []),
                    f"{series_where}.exclusion_regions",
                )
            ]
            declared_gap_ranges = []
            for gap_index, item in enumerate(
                _sequence(
                    series.get("declared_gap_ranges", []),
                    f"{series_where}.declared_gap_ranges",
                )
            ):
                parts = _sequence(
                    item, f"{series_where}.declared_gap_ranges[{gap_index}]"
                )
                if len(parts) != 2:
                    raise SpecError(
                        f"{series_where}.declared_gap_ranges[{gap_index}] needs two endpoints"
                    )
                gap = (
                    _integer(parts[0], f"{series_where}.declared_gap_ranges[{gap_index}]"),
                    _integer(parts[1], f"{series_where}.declared_gap_ranges[{gap_index}]"),
                )
                domain_left, domain_right = pixel_range or (plot_bbox[0], plot_bbox[2])
                if not domain_left <= gap[0] < gap[1] <= domain_right:
                    raise SpecError(
                        f"{series_where}.declared_gap_ranges[{gap_index}] is outside the trace domain"
                    )
                declared_gap_ranges.append(gap)
            trace_domain = pixel_range or (plot_bbox[0], plot_bbox[2])
            eligibility = _eligibility(
                series.get("eligibility", {}),
                f"{series_where}.eligibility",
                trace_domain,
            )
            series_items.append(
                {
                    "series_key": series_key,
                    "label": label,
                    "primitive_kind": primitive,
                    "rgb": rgb,
                    "color": "#%02x%02x%02x" % rgb,
                    "tolerance": tolerance,
                    "line_style": style,
                    "style_signature": signature,
                    "seeds": sorted(seeds),
                    "binding": {
                        "source": binding_source,
                        "visible_label": visible_label,
                        "bbox": binding_bbox,
                        "alternatives": alternatives,
                        "min_color_pixels": _integer(
                            binding.get("min_color_pixels", 1),
                            f"{series_where}.binding.min_color_pixels",
                            minimum=1,
                        ),
                        "verify_style": binding.get("verify_style", True),
                    },
                    "tracking": tracking,
                    "pixel_range": pixel_range,
                    "exclusion_regions": exclusions + series_exclusions,
                    "declared_gap_ranges": sorted(declared_gap_ranges),
                    "eligibility": eligibility,
                    "data_item": item_name,
                }
            )
            if not isinstance(series_items[-1]["binding"]["verify_style"], bool):
                raise SpecError(f"{series_where}.binding.verify_style must be boolean")
        if not series_items:
            raise SpecError(f"{where}.series must not be empty")
        shared_support = []
        shared_groups: set[str] = set()
        claimed_ranges: dict[str, list[tuple[int, int]]] = {}
        for support_index, support_value in enumerate(
            _sequence(panel.get("shared_support", []), f"{where}.shared_support")
        ):
            support_where = f"{where}.shared_support[{support_index}]"
            support = _mapping(support_value, support_where)
            group_key = _key(support.get("group_key"), f"{support_where}.group_key")
            if group_key in shared_groups:
                raise SpecError(f"duplicate shared-support group in {panel_key}: {group_key}")
            shared_groups.add(group_key)
            visible_series = _key(
                support.get("visible_series"), f"{support_where}.visible_series"
            )
            if visible_series not in series_keys:
                raise SpecError(f"{support_where}.visible_series is unknown")
            covered_series = tuple(
                _key(item, f"{support_where}.covered_series")
                for item in _sequence(
                    support.get("covered_series"), f"{support_where}.covered_series"
                )
            )
            if not covered_series or len(covered_series) != len(set(covered_series)):
                raise SpecError(f"{support_where}.covered_series must be unique and non-empty")
            if visible_series in covered_series or any(
                item not in series_keys for item in covered_series
            ):
                raise SpecError(f"{support_where} references an invalid covered series")
            if support.get("mode") != "overdraw":
                raise SpecError(f"{support_where}.mode must be overdraw")
            covered_eligible = support.get("covered_eligible", False)
            if not isinstance(covered_eligible, bool):
                raise SpecError(f"{support_where}.covered_eligible must be boolean")
            max_endpoint_distance = _number(
                support.get("max_endpoint_distance_px", 4),
                f"{support_where}.max_endpoint_distance_px",
            )
            if max_endpoint_distance < 0:
                raise SpecError(
                    f"{support_where}.max_endpoint_distance_px cannot be negative"
                )
            pixel_ranges = []
            for range_index, range_value in enumerate(
                _sequence(support.get("pixel_ranges"), f"{support_where}.pixel_ranges")
            ):
                parts = _sequence(
                    range_value, f"{support_where}.pixel_ranges[{range_index}]"
                )
                if len(parts) != 2:
                    raise SpecError(
                        f"{support_where}.pixel_ranges[{range_index}] needs two endpoints"
                    )
                interval = (
                    _integer(parts[0], f"{support_where}.pixel_ranges[{range_index}]"),
                    _integer(parts[1], f"{support_where}.pixel_ranges[{range_index}]"),
                )
                if not plot_bbox[0] < interval[0] < interval[1] < plot_bbox[2]:
                    raise SpecError(
                        f"{support_where}.pixel_ranges[{range_index}] needs direct support on both sides"
                    )
                for member in (visible_series, *covered_series):
                    claimed_ranges.setdefault(member, []).append(interval)
                pixel_ranges.append(interval)
            if not pixel_ranges:
                raise SpecError(f"{support_where}.pixel_ranges must not be empty")
            shared_support.append(
                {
                    "group_key": group_key,
                    "visible_series": visible_series,
                    "covered_series": list(covered_series),
                    "pixel_ranges": sorted(pixel_ranges),
                    "mode": "overdraw",
                    "covered_eligible": covered_eligible,
                    "max_endpoint_distance_px": max_endpoint_distance,
                }
            )
        for member, intervals in claimed_ranges.items():
            ordered = sorted(intervals)
            for previous, current in zip(ordered, ordered[1:]):
                if current[0] < previous[1]:
                    raise SpecError(
                        f"shared-support ranges overlap for {member}"
                    )
        series_by_key = {item["series_key"]: item for item in series_items}
        for support in shared_support:
            for covered in support["covered_series"]:
                series_by_key[covered]["declared_gap_ranges"] = sorted(
                    {
                        *series_by_key[covered]["declared_gap_ranges"],
                        *support["pixel_ranges"],
                    }
                )
        normalized_panels.append(
            {
                "panel_key": panel_key,
                "citation": citation,
                "plot_bbox": plot_bbox,
                "axis_calibration": axes,
                "series": series_items,
                "shared_support": shared_support,
            }
        )
    normalized = {
        "figure_key": figure_key,
        "source": {
            "source_name": source_name,
            "page": page,
            "figure": figure,
            "image_sha256": actual_sha,
            "width": expected_width,
            "height": expected_height,
            **pdf_provenance,
        },
    }
    return normalized, image_path, normalized_panels


def _matches(pixel: tuple[int, ...], rgb: tuple[int, int, int], tolerance: float) -> bool:
    return sum((int(pixel[index]) - rgb[index]) ** 2 for index in range(3)) <= tolerance**2


def _excluded(x: int, y: int, regions: Iterable[tuple[int, int, int, int]]) -> bool:
    return any(left <= x < right and top <= y < bottom for left, top, right, bottom in regions)


def _runs(values: list[bool]) -> tuple[list[int], list[int]]:
    true_runs: list[int] = []
    gaps: list[int] = []
    current = values[0] if values else False
    length = 0
    for value in values:
        if value == current:
            length += 1
            continue
        (true_runs if current else gaps).append(length)
        current = value
        length = 1
    if values:
        (true_runs if current else gaps).append(length)
    if values and not values[0] and gaps:
        gaps = gaps[1:]
    if values and not values[-1] and gaps:
        gaps = gaps[:-1]
    return true_runs, gaps


def _median(values: list[int]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2


def _style_matches(style: str, columns: list[bool], signature: dict[str, Any]) -> bool:
    runs, gaps = _runs(columns)
    if not runs:
        return False
    default: dict[str, float] = {}
    if style == "solid":
        default = {"min_runs": 1, "min_run_px": 4}
    elif style == "dashed":
        default = {"min_runs": 2, "min_run_px": 3, "min_gap_px": 1}
    elif style == "dotted":
        default = {"min_runs": 2, "max_run_px": 5, "min_gap_px": 1}
    else:
        return True
    limits = {**default, **signature}
    if len(runs) < int(limits.get("min_runs", 0)):
        return False
    median_run = _median(runs)
    if median_run < float(limits.get("min_run_px", 0)):
        return False
    if "max_run_px" in limits and median_run > float(limits["max_run_px"]):
        return False
    if gaps and _median(gaps) < float(limits.get("min_gap_px", 0)):
        return False
    if limits.get("min_gap_px", 0) and not gaps:
        return False
    return True


def _verify_binding(image: Image.Image, series: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    binding = series["binding"]
    left, top, right, bottom = binding["bbox"]
    pixels = image.load()
    columns: list[bool] = []
    color_pixels = 0
    for x in range(left, right):
        present = False
        for y in range(top, bottom):
            if _matches(pixels[x, y], series["rgb"], series["tolerance"]):
                color_pixels += 1
                present = True
        columns.append(present)
    enough_color = color_pixels >= max(1, binding["min_color_pixels"])
    style_ok = True
    if binding["verify_style"] and series["primitive_kind"] != "marker":
        style_ok = _style_matches(
            series["line_style"], columns, series["style_signature"]
        )
    matched = enough_color and style_ok
    confidence = 0.0
    if enough_color:
        confidence += 0.65
    if style_ok:
        confidence += 0.35
    result = {
        "source": binding["source"],
        "visible_label": binding["visible_label"],
        "status": "matched" if matched else "unresolved",
        "confidence": round(confidence, 6),
        "alternatives": binding["alternatives"],
    }
    if matched:
        return result, None
    reasons = []
    if not enough_color:
        reasons.append("binding box lacks descriptor-colored pixels")
    if not style_ok:
        reasons.append("binding glyph does not match the declared line style")
    return result, "; ".join(reasons)


def _guide_y(seeds: list[tuple[float, float]], x: float, fallback: float) -> float:
    if not seeds:
        return fallback
    if x <= seeds[0][0]:
        return seeds[0][1]
    if x >= seeds[-1][0]:
        return seeds[-1][1]
    for (left_x, left_y), (right_x, right_y) in zip(seeds, seeds[1:]):
        if left_x <= x <= right_x:
            if right_x == left_x:
                return (left_y + right_y) / 2
            fraction = (x - left_x) / (right_x - left_x)
            return left_y + fraction * (right_y - left_y)
    return fallback


def _column_candidates(
    image: Image.Image,
    x: int,
    top: int,
    bottom: int,
    series: dict[str, Any],
) -> list[dict[str, float]]:
    pixels = image.load()
    matching = [
        y
        for y in range(top, bottom)
        if not _excluded(x, y, series["exclusion_regions"])
        and _matches(pixels[x, y], series["rgb"], series["tolerance"])
    ]
    if not matching:
        return []
    groups: list[list[int]] = [[matching[0]]]
    for y in matching[1:]:
        if y == groups[-1][-1] + 1:
            groups[-1].append(y)
        else:
            groups.append([y])
    candidates: list[dict[str, float]] = []
    for group in groups:
        weights = []
        for y in group:
            distance = math.sqrt(
                sum((int(pixels[x, y][index]) - series["rgb"][index]) ** 2 for index in range(3))
            )
            weights.append(max(1.0, series["tolerance"] + 1.0 - distance))
        subpixel = sum(y * weight for y, weight in zip(group, weights)) / sum(weights)
        raw = min(group, key=lambda y: (abs(y - subpixel), y))
        candidates.append(
            {
                "raw_y": float(raw),
                "subpixel_y": subpixel,
                "uncertainty_px": max(0.5, len(group) / 2),
            }
        )
    return candidates


def _seed_is_supported(image: Image.Image, series: dict[str, Any], seed: tuple[float, float]) -> bool:
    radius = int(series["tracking"].get("seed_radius_px", 4))
    pixels = image.load()
    center_x, center_y = (int(round(seed[0])), int(round(seed[1])))
    for x in range(max(0, center_x - radius), min(image.width, center_x + radius + 1)):
        for y in range(max(0, center_y - radius), min(image.height, center_y + radius + 1)):
            if _matches(pixels[x, y], series["rgb"], series["tolerance"]):
                return True
    return False


def _global_line_path(
    image: Image.Image,
    series: dict[str, Any],
    *,
    left: int,
    top: int,
    right: int,
    bottom: int,
) -> tuple[list[dict[str, float]], int]:
    """Choose one bounded, guide-anchored path without stale greedy state."""

    tracking = series["tracking"]
    max_step = float(tracking.get("max_vertical_step_px", 12))
    guide_weight = float(tracking.get("guide_weight", 0.7))
    max_guide_distance = float(
        tracking.get("max_guide_distance_px", math.inf)
    )
    ambiguity_margin = float(tracking.get("ambiguity_margin_px", 0.75))
    fallback = (top + bottom - 1) / 2
    states: list[dict[str, Any]] = []
    terminal_states: list[dict[str, Any]] = []
    ambiguous_columns = 0
    max_gap = int(tracking.get("max_gap_px", 0))
    skip_penalty = float(tracking.get("skip_penalty", max_step + 1.0))
    border_exclusion = int(tracking.get("plot_border_exclusion_px", 4))
    search_top = min(bottom, top + border_exclusion)
    search_bottom = max(search_top, bottom - border_exclusion)

    for x in range(left, right):
        guide = _guide_y(series["seeds"], x, fallback)
        candidates = _column_candidates(
            image, x, search_top, search_bottom, series
        )
        guided_candidates = [
            candidate
            for candidate in candidates
            if abs(candidate["subpixel_y"] - guide) <= max_guide_distance
        ]
        next_states: list[dict[str, Any]] = []
        candidate_states: list[dict[str, Any]] = []
        if states:
            for candidate in candidates:
                choices = []
                for prior in states:
                    span = max(1, x - prior["last_x"])
                    if span == 1:
                        allowed_step = max_step
                    else:
                        default_gap_step = (
                            max_step + max_guide_distance
                            if math.isfinite(max_guide_distance)
                            else max_step * span
                        )
                        allowed_step = float(
                            tracking.get(
                                "max_gap_vertical_displacement_px",
                                default_gap_step,
                            )
                        )
                    step = abs(
                        candidate["subpixel_y"]
                        - prior["last_point"]["subpixel_y"]
                    )
                    if step <= allowed_step:
                        choices.append(
                            (
                                prior["cost"]
                                + guide_weight * abs(candidate["subpixel_y"] - guide)
                                + (1 - guide_weight) * step / span,
                                prior,
                            )
                        )
                if choices:
                    cost, prior = min(
                        choices,
                        key=lambda item: (
                            item[0],
                            item[1]["last_point"]["subpixel_y"],
                        ),
                    )
                    candidate_states.append(
                        {
                            "cost": cost,
                            "last_point": candidate,
                            "last_x": x,
                            "node": {
                                "point": candidate,
                                "x": x,
                                "previous": prior["node"],
                            },
                        }
                    )
            next_states.extend(candidate_states)
            next_states.extend(
                {
                    **prior,
                    "cost": prior["cost"] + skip_penalty,
                }
                for prior in states
                if x - prior["last_x"] <= max_gap
            )
        if not states and guided_candidates:
            candidate_states = [
                {
                    "cost": guide_weight * abs(candidate["subpixel_y"] - guide),
                    "last_point": candidate,
                    "last_x": x,
                    "node": {"point": candidate, "x": x, "previous": None},
                }
                for candidate in guided_candidates
            ]
            next_states.extend(candidate_states)
        if states and not next_states:
            terminal_states.append(
                min(
                    states,
                    key=lambda item: (
                        item["cost"],
                        item["last_point"]["subpixel_y"],
                    ),
                )
            )
            states = []
            if guided_candidates:
                next_states = [
                    {
                        "cost": guide_weight
                        * abs(candidate["subpixel_y"] - guide),
                        "last_point": candidate,
                        "last_x": x,
                        "node": {
                            "point": candidate,
                            "x": x,
                            "previous": None,
                        },
                    }
                    for candidate in guided_candidates
                ]
                candidate_states = next_states
        ranked_costs = sorted(item["cost"] for item in candidate_states)
        if len(ranked_costs) > 1 and ranked_costs[1] - ranked_costs[0] <= ambiguity_margin:
            ambiguous_columns += 1
        states = sorted(
            next_states,
            key=lambda item: (item["cost"], item["last_point"]["subpixel_y"]),
        )[:64]
    if states:
        terminal_states.append(
            min(
                states,
                key=lambda item: (
                    item["cost"],
                    item["last_point"]["subpixel_y"],
                ),
            )
        )

    selected: dict[int, dict[str, float]] = {}
    for terminal in terminal_states:
        current: dict[str, Any] | None = terminal["node"]
        while current is not None:
            selected[current["x"]] = current["point"]
            current = current["previous"]
    points = [
        {
            "point_index": float(x - left),
            "pixel_x_raw": float(x),
            "pixel_y_raw": selected[x]["raw_y"],
            "pixel_x_subpixel": float(x),
            "pixel_y_subpixel": selected[x]["subpixel_y"],
            "uncertainty_px": selected[x]["uncertainty_px"],
        }
        for x in sorted(selected)
    ]
    return points, ambiguous_columns


def _line_points(
    image: Image.Image,
    panel: dict[str, Any],
    series: dict[str, Any],
) -> tuple[list[dict[str, float]], dict[str, Any], list[dict[str, Any]]]:
    left, top, right, bottom = panel["plot_bbox"]
    if series["pixel_range"] is not None:
        left, right = series["pixel_range"]
    tracking = series["tracking"]
    min_visible = float(tracking.get("min_visible_fraction", 0.15))
    max_ambiguous = float(tracking.get("max_ambiguous_fraction", 0.1))
    seeds = series["seeds"]
    findings: list[dict[str, Any]] = []
    for seed in seeds:
        if not _seed_is_supported(image, series, seed):
            findings.append(
                {
                    "message": f"configured seed {list(seed)} is not supported by descriptor pixels",
                    "candidates": [],
                }
            )
    points, ambiguous_columns = _global_line_path(
        image,
        series,
        left=left,
        top=top,
        right=right,
        bottom=bottom,
    )
    width = max(1, right - left)
    observed_x = [int(item["pixel_x_raw"]) for item in points]
    visible_fraction = len(set(observed_x)) / width
    max_gap = 0
    if observed_x:
        max_gap = max(
            [observed_x[0] - left, right - 1 - observed_x[-1]]
            + [max(0, current - previous - 1) for previous, current in zip(observed_x, observed_x[1:])]
        )
    else:
        max_gap = width
    unexpected_gap_max = 0
    gap_intervals = []
    if observed_x:
        gap_intervals.extend(
            (previous + 1, current)
            for previous, current in zip(observed_x, observed_x[1:])
            if current - previous > 1
        )
        if observed_x[0] > left:
            gap_intervals.append((left, observed_x[0]))
        if observed_x[-1] < right - 1:
            gap_intervals.append((observed_x[-1] + 1, right))
    else:
        gap_intervals.append((left, right))
    for gap_left, gap_right in gap_intervals:
        declared = any(
            declared_left <= gap_left and gap_right <= declared_right
            for declared_left, declared_right in series["declared_gap_ranges"]
        )
        if not declared:
            unexpected_gap_max = max(unexpected_gap_max, gap_right - gap_left)
    ambiguous_fraction = ambiguous_columns / width
    min_points = int(tracking.get("min_points", 2))
    if len(points) < min_points:
        findings.append({"message": "too few trace points", "candidates": []})
    if visible_fraction < min_visible:
        findings.append(
            {
                "message": (
                    f"visible fraction {visible_fraction:.4f} is below configured minimum "
                    f"{min_visible:.4f}"
                ),
                "candidates": [],
            }
        )
    allowed_gap = int(tracking.get("max_gap_px", 0))
    if unexpected_gap_max > allowed_gap:
        findings.append(
            {
                "message": (
                    f"maximum undeclared trace gap {unexpected_gap_max}px exceeds "
                    f"{allowed_gap}px"
                ),
                "candidates": [
                    "retrace a visibly continuous source",
                    "declare an exact visible occlusion/source-gap range",
                ],
            }
        )
    # A declared source gap limits quantitative continuity without making a
    # separately matched series identity ambiguous.  Undeclared gaps above the
    # configured raster tolerance fail closed as extraction defects.
    if ambiguous_fraction > max_ambiguous:
        findings.append(
            {
                "message": (
                    f"candidate tie fraction {ambiguous_fraction:.4f} exceeds "
                    f"{max_ambiguous:.4f}"
                ),
                "candidates": ["multiple descriptor-colored paths"],
            }
        )
    metrics = {
        "visible_fraction": visible_fraction,
        "max_gap_px": max_gap,
        "ambiguous_fraction": ambiguous_fraction,
    }
    return points, metrics, findings


def _marker_points(
    image: Image.Image,
    panel: dict[str, Any],
    series: dict[str, Any],
) -> tuple[list[dict[str, float]], dict[str, Any], list[dict[str, Any]]]:
    left, top, right, bottom = panel["plot_bbox"]
    if series["pixel_range"] is not None:
        left, right = series["pixel_range"]
    pixels = image.load()
    remaining = {
        (x, y)
        for x in range(left, right)
        for y in range(top, bottom)
        if not _excluded(x, y, series["exclusion_regions"])
        and _matches(pixels[x, y], series["rgb"], series["tolerance"])
    }
    tracking = series["tracking"]
    minimum = int(tracking.get("min_component_pixels", 2))
    maximum = int(tracking.get("max_component_pixels", 10000))
    max_seed_distance = float(tracking.get("max_seed_distance_px", 24))
    components: list[list[tuple[int, int]]] = []
    while remaining:
        start = min(remaining)
        remaining.remove(start)
        queue = deque([start])
        component = [start]
        while queue:
            x, y = queue.popleft()
            for nx in range(x - 1, x + 2):
                for ny in range(y - 1, y + 2):
                    neighbor = (nx, ny)
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        queue.append(neighbor)
                        component.append(neighbor)
        if minimum <= len(component) <= maximum:
            components.append(component)
    points: list[dict[str, float]] = []
    for component in components:
        sub_x = sum(item[0] for item in component) / len(component)
        sub_y = sum(item[1] for item in component) / len(component)
        if series["seeds"]:
            guide = _guide_y(series["seeds"], sub_x, sub_y)
            if abs(sub_y - guide) > max_seed_distance:
                continue
        raw_x, raw_y = min(
            component,
            key=lambda item: ((item[0] - sub_x) ** 2 + (item[1] - sub_y) ** 2, item),
        )
        component_width = max(item[0] for item in component) - min(item[0] for item in component) + 1
        component_height = max(item[1] for item in component) - min(item[1] for item in component) + 1
        points.append(
            {
                "pixel_x_raw": float(raw_x),
                "pixel_y_raw": float(raw_y),
                "pixel_x_subpixel": sub_x,
                "pixel_y_subpixel": sub_y,
                "uncertainty_px": max(component_width, component_height) / 2,
            }
        )
    points.sort(key=lambda item: (item["pixel_x_subpixel"], item["pixel_y_subpixel"]))
    min_points = int(tracking.get("min_points", 1))
    findings = []
    if len(points) < min_points:
        findings.append({"message": "too few marker components", "candidates": []})
    expected = tracking.get("expected_point_count")
    if expected is None:
        visible_fraction = 1.0 if points else 0.0
    else:
        expected_count = max(1, int(expected))
        visible_fraction = min(1.0, len(points) / expected_count)
        if len(points) != expected_count:
            findings.append(
                {
                    "message": f"observed {len(points)} marker components, expected {expected_count}",
                    "candidates": [],
                }
            )
    metrics = {"visible_fraction": visible_fraction, "max_gap_px": 0, "ambiguous_fraction": 0.0}
    return points, metrics, findings


def _axis_value(axis: dict[str, Any], pixel: float) -> float:
    fraction = (pixel - axis["pixel_min"]) / (axis["pixel_max"] - axis["pixel_min"])
    if axis["scale"] == "linear":
        return axis["value_min"] + fraction * (axis["value_max"] - axis["value_min"])
    low = math.log10(axis["value_min"])
    high = math.log10(axis["value_max"])
    return 10 ** (low + fraction * (high - low))


def _axis_uncertainty(axis: dict[str, Any], pixel: float, uncertainty_px: float) -> float:
    uncertainty_px = uncertainty_px + axis["reprojection_error_px"]
    center = _axis_value(axis, pixel)
    low = _axis_value(axis, pixel - uncertainty_px)
    high = _axis_value(axis, pixel + uncertainty_px)
    return max(abs(center - low), abs(high - center))


def _inside_ranges(pixel_x: int, ranges: list[tuple[int, int]]) -> bool:
    return any(left <= pixel_x < right for left, right in ranges)


def _calibrate_points(
    points: list[dict[str, float]],
    axes: dict[str, dict[str, Any]],
    eligibility: dict[str, Any],
) -> list[dict[str, float]]:
    calibrated = []
    for point in points:
        px = point["pixel_x_subpixel"]
        py = point["pixel_y_subpixel"]
        raw_x = int(point["pixel_x_raw"])
        uncertainty = point["uncertainty_px"]
        below_limit = _inside_ranges(
            raw_x, eligibility["below_detection_limit_pixel_ranges"]
        )
        explicitly_ineligible = _inside_ranges(
            raw_x, eligibility["ineligible_pixel_ranges"]
        )
        region_reason = next(
            (
                region["reason"]
                for region in eligibility["ineligible_pixel_regions"]
                if region["pixel_range"][0] <= raw_x < region["pixel_range"][1]
            ),
            "",
        )
        shared_ineligible = (
            point.get("support_kind", "direct_pixel") == "shared_occlusion"
            and not point.get("shared_eligible", False)
        )
        row_eligible = bool(
            eligibility["default_eligible"]
            and not below_limit
            and not explicitly_ineligible
            and not region_reason
            and not shared_ineligible
        )
        if below_limit:
            eligibility_reason = "below_detection_limit"
        elif region_reason:
            eligibility_reason = region_reason
        elif explicitly_ineligible:
            eligibility_reason = "unspecified_ineligible_range"
        elif shared_ineligible:
            eligibility_reason = "shared_occlusion"
        elif not eligibility["default_eligible"]:
            eligibility_reason = "series_default_ineligible"
        else:
            eligibility_reason = ""
        calibrated.append(
            {
                **point,
                "x_value": _axis_value(axes["x"], px),
                "y_value": _axis_value(axes["y"], py),
                "x_uncertainty": _axis_uncertainty(axes["x"], px, uncertainty),
                "y_uncertainty": _axis_uncertainty(axes["y"], py, uncertainty),
                "observed": 1,
                "quantitative_measurement_claim_eligible": int(row_eligible),
                "below_sims_detection_limit": int(below_limit),
                "eligibility_reason": eligibility_reason,
                "support_kind": point.get("support_kind", "direct_pixel"),
                "coordinate_ownership": point.get(
                    "coordinate_ownership", "exclusive"
                ),
                "shared_group": point.get("shared_group", ""),
                "support_source_series": point.get(
                    "support_source_series", ""
                ),
            }
        )
    return calibrated


def _materialize_shared_support(
    panel: dict[str, Any],
    direct: dict[str, list[dict[str, float]]],
) -> dict[str, list[dict[str, float]]]:
    """Apply only operator-declared overdraw support to otherwise missing columns."""

    result = {key: [dict(point) for point in points] for key, points in direct.items()}
    series_by_key = {item["series_key"]: item for item in panel["series"]}
    by_x = {
        key: {int(point["pixel_x_raw"]): point for point in points}
        for key, points in result.items()
    }
    for support in panel["shared_support"]:
        donor_key = support["visible_series"]
        donor = by_x[donor_key]
        for left, right in support["pixel_ranges"]:
            required = set(range(left, right))
            if not required.issubset(donor):
                missing = min(required - set(donor))
                raise SpecError(
                    f"shared-support donor {donor_key} lacks direct pixel {missing}"
                )
            for covered_key in support["covered_series"]:
                covered = by_x[covered_key]
                if left - 1 not in covered or right not in covered:
                    raise SpecError(
                        f"shared-support {support['group_key']} lacks covered-series endpoints"
                    )
                for endpoint in (left - 1, right):
                    distance = abs(
                        covered[endpoint]["pixel_y_subpixel"]
                        - donor[endpoint]["pixel_y_subpixel"]
                    )
                    if distance > support["max_endpoint_distance_px"]:
                        raise SpecError(
                            f"shared-support {support['group_key']} endpoint distance "
                            f"{distance:.3f}px exceeds {support['max_endpoint_distance_px']:.3f}px"
                        )
                if any(pixel_x in covered for pixel_x in required):
                    raise SpecError(
                        f"shared-support {support['group_key']} may fill only missing covered pixels"
                    )
                endpoint_uncertainty = max(
                    abs(
                        covered[endpoint]["pixel_y_subpixel"]
                        - donor[endpoint]["pixel_y_subpixel"]
                    )
                    for endpoint in (left - 1, right)
                )
                for pixel_x in range(left, right):
                    donor_point = donor[pixel_x]
                    covered_domain_left = (
                        series_by_key[covered_key]["pixel_range"] or panel["plot_bbox"]
                    )[0]
                    covered[pixel_x] = {
                        **donor_point,
                        "point_index": float(pixel_x - covered_domain_left),
                        "uncertainty_px": max(
                            donor_point["uncertainty_px"], endpoint_uncertainty + 0.5
                        ),
                        "support_kind": "shared_occlusion",
                        "coordinate_ownership": "shared",
                        "shared_group": support["group_key"],
                        "support_source_series": donor_key,
                        "shared_eligible": support["covered_eligible"],
                    }
                    donor_point["support_kind"] = "direct_pixel"
                    donor_point["coordinate_ownership"] = "shared"
                    donor_point["shared_group"] = support["group_key"]
                    donor_point["support_source_series"] = donor_key
        for series_key in {donor_key, *support["covered_series"]}:
            result[series_key] = sorted(
                by_x[series_key].values(), key=lambda point: point["pixel_x_raw"]
            )
    return result


def _overdraw_candidates(
    panel: dict[str, Any],
    direct: dict[str, list[dict[str, float]]],
) -> dict[str, list[dict[str, Any]]]:
    """Report geometry-supported multicolor overdraw candidates without assigning them."""

    by_x = {
        key: {int(point["pixel_x_raw"]): point for point in points}
        for key, points in direct.items()
    }
    series_by_key = {item["series_key"]: item for item in panel["series"]}
    declared = {
        (covered, left, right)
        for support in panel["shared_support"]
        for covered in support["covered_series"]
        for left, right in support["pixel_ranges"]
    }
    result: dict[str, list[dict[str, Any]]] = {
        key: [] for key in series_by_key
    }
    for covered_key, covered in by_x.items():
        definition = series_by_key[covered_key]
        if definition["primitive_kind"] == "marker" or not covered:
            continue
        observed = sorted(covered)
        gaps = [
            (previous + 1, current)
            for previous, current in zip(observed, observed[1:])
            if current - previous > 1
        ]
        for gap_left, gap_right in gaps:
            if (covered_key, gap_left, gap_right) in declared:
                continue
            for donor_key, donor in by_x.items():
                if donor_key == covered_key or not all(
                    pixel_x in donor
                    for pixel_x in range(gap_left - 1, gap_right + 1)
                ):
                    continue
                endpoint_distance = max(
                    abs(
                        covered[endpoint]["pixel_y_subpixel"]
                        - donor[endpoint]["pixel_y_subpixel"]
                    )
                    for endpoint in (gap_left - 1, gap_right)
                )
                limit = float(
                    definition["tracking"].get(
                        "overdraw_candidate_endpoint_distance_px", 8.0
                    )
                )
                if endpoint_distance <= limit:
                    result[covered_key].append(
                        {
                            "message": (
                                f"possible multicolor overdraw by {donor_key} across "
                                f"pixels [{gap_left},{gap_right})"
                            ),
                            "candidates": [
                                "confirm an explicit shared_support declaration",
                                "retain the source-column gap",
                            ],
                        }
                    )
    return result


def _format_number(value: float) -> str:
    return format(float(value), ".12g")


def _write_csv(path: Path, panel_key: str, series_key: str, points: list[dict[str, float]]) -> None:
    fields = [
        "panel_key",
        "series_key",
        "point_index",
        "pixel_x_raw",
        "pixel_y_raw",
        "pixel_x_subpixel",
        "pixel_y_subpixel",
        "x_value",
        "y_value",
        "uncertainty_px",
        "x_uncertainty",
        "y_uncertainty",
        "observed",
        "quantitative_measurement_claim_eligible",
        "below_sims_detection_limit",
        "eligibility_reason",
        "support_kind",
        "coordinate_ownership",
        "shared_group",
        "support_source_series",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for index, point in enumerate(points):
            writer.writerow(
                {
                    "panel_key": panel_key,
                    "series_key": series_key,
                    "point_index": int(point.get("point_index", index)),
                    **{
                        key: str(int(point[key]))
                        if key
                        in {
                            "pixel_x_raw",
                            "pixel_y_raw",
                            "observed",
                            "quantitative_measurement_claim_eligible",
                            "below_sims_detection_limit",
                        }
                        else point[key]
                        if key
                        in {
                            "support_kind",
                            "eligibility_reason",
                            "coordinate_ownership",
                            "shared_group",
                            "support_source_series",
                        }
                        else _format_number(point[key])
                        for key in fields[3:]
                    },
                }
            )


def _draw_overlays(
    image: Image.Image,
    panels: list[dict[str, Any]],
    traces: dict[tuple[str, str], list[dict[str, float]]],
    fidelity_path: Path,
    identity_path: Path,
) -> None:
    fidelity = image.copy()
    identity = image.copy()
    fidelity_draw = ImageDraw.Draw(fidelity)
    identity_draw = ImageDraw.Draw(identity)
    color_index = 0
    for panel in panels:
        fidelity_draw.rectangle(panel["plot_bbox"], outline="#666666", width=1)
        identity_draw.rectangle(panel["plot_bbox"], outline="#666666", width=1)
        for series in panel["series"]:
            identity_color = IDENTITY_COLORS[color_index % len(IDENTITY_COLORS)]
            color_index += 1
            points = traces[(panel["panel_key"], series["series_key"])]
            for point in points:
                x = int(round(point["pixel_x_subpixel"]))
                y = int(round(point["pixel_y_subpixel"]))
                fidelity_draw.point((x, y), fill="#00ff00")
                identity_draw.ellipse((x - 1, y - 1, x + 1, y + 1), fill=identity_color)
            identity_draw.rectangle(series["binding"]["bbox"], outline=identity_color, width=2)
            for x, y in series["seeds"]:
                identity_draw.line((x - 3, y, x + 3, y), fill=identity_color, width=1)
                identity_draw.line((x, y - 3, x, y + 3), fill=identity_color, width=1)
            if points:
                x = int(points[0]["pixel_x_subpixel"]) + 3
                y = int(points[0]["pixel_y_subpixel"]) - 10
            else:
                x, y = series["binding"]["bbox"][:2]
            identity_draw.text((x, y), series["series_key"], fill=identity_color)
    fidelity.save(fidelity_path, format="PNG", optimize=False, compress_level=9)
    identity.save(identity_path, format="PNG", optimize=False, compress_level=9)


def _media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".json": "application/json",
        ".csv": "text/csv",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
        ".bmp": "image/bmp",
        ".webp": "image/webp",
    }.get(suffix, "application/octet-stream")


def _collection(relative: str) -> str:
    return relative.split("/", 1)[0]


def digitize(spec_path: Path, output_dir: Path) -> str:
    """Digitize *spec_path* into a new *output_dir* and return package status."""
    spec_path = spec_path.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise SpecError(f"refusing to overwrite existing output path: {output_dir}")
    raw_bytes = spec_path.read_bytes()
    try:
        raw = json.loads(raw_bytes)
    except json.JSONDecodeError as exc:
        raise SpecError(f"invalid JSON spec: {exc}") from exc
    normalized, image_path, panels = _normalize_spec(raw, spec_path)
    spec_sha = _sha256_bytes(_canonical_bytes(raw))
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.tmp-", dir=str(output_dir.parent))
    )
    try:
        for dirname in ("figure_manifest", "source_panels", "audit_overlays", "curve_tables"):
            (temporary / dirname).mkdir()
        with Image.open(image_path) as opened:
            image = opened.convert("RGB")
        source_suffix = image_path.suffix.lower() or ".bin"
        shutil.copyfile(image_path, temporary / "source_panels" / f"source_image{source_suffix}")
        for panel in panels:
            image.crop(panel["plot_bbox"]).save(
                temporary / "source_panels" / f"{panel['panel_key']}.png",
                format="PNG",
                optimize=False,
                compress_level=9,
            )

        ambiguities: list[dict[str, Any]] = []
        evidence_panels: list[dict[str, Any]] = []
        traces: dict[tuple[str, str], list[dict[str, float]]] = {}
        total_points = 0
        qualified_series = 0
        visible_fractions: list[float] = []
        for panel in panels:
            color_counts: dict[tuple[int, int, int], int] = {}
            for series in panel["series"]:
                color_counts[series["rgb"]] = color_counts.get(series["rgb"], 0) + 1
            evidence_series: list[dict[str, Any]] = []
            direct_traces: dict[str, list[dict[str, float]]] = {}
            trace_metadata: dict[str, dict[str, Any]] = {}
            for series in panel["series"]:
                local_findings: list[dict[str, Any]] = []
                if color_counts[series["rgb"]] > 1 and not series["seeds"]:
                    local_findings.append(
                        {
                            "message": "color is shared by multiple series but no identity seed is configured",
                            "candidates": ["same-color paths require configured identity anchors"],
                        }
                    )
                binding, binding_finding = _verify_binding(image, series)
                if binding_finding:
                    local_findings.append({"message": binding_finding, "candidates": binding["alternatives"]})
                if series["primitive_kind"] == "marker":
                    points, metrics, trace_findings = _marker_points(image, panel, series)
                else:
                    points, metrics, trace_findings = _line_points(image, panel, series)
                local_findings.extend(trace_findings)
                direct_traces[series["series_key"]] = points
                trace_metadata[series["series_key"]] = {
                    "binding": binding,
                    "findings": local_findings,
                    "metrics": metrics,
                }
            overdraw_candidates = _overdraw_candidates(panel, direct_traces)
            for series_key, findings in overdraw_candidates.items():
                trace_metadata[series_key]["findings"].extend(findings)
            supported_traces = _materialize_shared_support(panel, direct_traces)
            for series in panel["series"]:
                series_key = series["series_key"]
                points = supported_traces[series_key]
                metadata = trace_metadata[series_key]
                binding = metadata["binding"]
                local_findings = metadata["findings"]
                metrics = dict(metadata["metrics"])
                if series["primitive_kind"] != "marker":
                    if series["pixel_range"] is not None:
                        domain_left, domain_right = series["pixel_range"]
                    else:
                        domain_left, domain_right = (
                            panel["plot_bbox"][0],
                            panel["plot_bbox"][2],
                        )
                    observed_x = sorted(
                        {int(point["pixel_x_raw"]) for point in points}
                    )
                    width = max(1, domain_right - domain_left)
                    metrics["visible_fraction"] = len(observed_x) / width
                    metrics["max_gap_px"] = max(
                        [
                            observed_x[0] - domain_left,
                            domain_right - 1 - observed_x[-1],
                        ]
                        + [
                            max(0, current - previous - 1)
                            for previous, current in zip(observed_x, observed_x[1:])
                        ],
                        default=width,
                    )
                calibrated = _calibrate_points(
                    points,
                    panel["axis_calibration"],
                    series["eligibility"],
                )
                traces[(panel["panel_key"], series_key)] = calibrated
                _write_csv(
                    temporary / series["data_item"],
                    panel["panel_key"],
                    series_key,
                    calibrated,
                )
                total_points += len(calibrated)
                visible_fractions.append(metrics["visible_fraction"])
                if not local_findings:
                    qualified_series += 1
                for finding in local_findings:
                    ambiguities.append(
                        {
                            "panel_key": panel["panel_key"],
                            "series_key": series["series_key"],
                            "message": finding["message"],
                            "candidates": finding.get("candidates", []),
                        }
                    )
                reprojection = max(
                    axis["reprojection_error_px"]
                    for axis in panel["axis_calibration"].values()
                )
                uncertainty = max(
                    (
                        point["uncertainty_px"] + reprojection
                        for point in calibrated
                    ),
                    default=reprojection,
                )
                evidence_series.append(
                    {
                        "series_key": series["series_key"],
                        "label": series["label"],
                        "primitive_kind": series["primitive_kind"],
                        "descriptor": {
                            "color": series["color"],
                            "color_tolerance": series["tolerance"],
                            "line_style": series["line_style"],
                        },
                        "data_item": series["data_item"],
                        "binding": binding,
                        "point_count": len(calibrated),
                        "visible_fraction": round(metrics["visible_fraction"], 9),
                        "max_gap_px": int(metrics["max_gap_px"]),
                        "uncertainty_px": round(uncertainty, 6),
                    }
                )
            evidence_panels.append(
                {
                    "panel_key": panel["panel_key"],
                    "citation": panel["citation"],
                    "axis_calibration": panel["axis_calibration"],
                    "series": evidence_series,
                    "shared_support": panel["shared_support"],
                }
            )
        status = "qualified" if not ambiguities else "unresolved"
        evidence = {
            "schema_version": EVIDENCE_VERSION,
            "figure_key": normalized["figure_key"],
            "status": status,
            "source": normalized["source"],
            "panels": evidence_panels,
            "metrics": {
                "panel_count": len(panels),
                "series_count": sum(len(panel["series"]) for panel in panels),
                "qualified_series_count": qualified_series,
                "total_point_count": total_points,
                "minimum_visible_fraction": round(min(visible_fractions, default=0.0), 9),
            },
            "ambiguities": ambiguities,
        }
        _draw_overlays(
            image,
            panels,
            traces,
            temporary / "audit_overlays" / "fidelity_overlay.png",
            temporary / "audit_overlays" / "identity_overlay.png",
        )
        artifacts = []
        for path in sorted(item for item in temporary.rglob("*") if item.is_file()):
            relative = path.relative_to(temporary).as_posix()
            artifacts.append(
                {
                    "collection": _collection(relative),
                    "data_item": relative,
                    "sha256": _sha256_file(path),
                    "bytes": path.stat().st_size,
                    "media_type": _media_type(path),
                }
            )
        evidence["provenance"] = {
            "spec_sha256": spec_sha,
            "output_artifacts": artifacts,
        }
        (temporary / "figure_manifest" / "evidence.json").write_bytes(
            _canonical_bytes(evidence)
        )
        os.rename(temporary, output_dir)
        return status
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Digitize a bound scientific plot using a calibrated JSON spec."
    )
    parser.add_argument("spec", type=Path, help="JSON digitization spec")
    parser.add_argument(
        "--output-dir", type=Path, required=True, help="new evidence package directory"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        status = digitize(args.spec, args.output_dir)
    except (OSError, SpecError) as exc:
        print(json.dumps({"error": str(exc), "status": "failed"}, sort_keys=True), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {"output_dir": str(args.output_dir.resolve()), "status": status}, sort_keys=True
        )
    )
    return 0 if status == "qualified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
