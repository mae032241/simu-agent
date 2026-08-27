#!/usr/bin/env python3
"""Render observed support, quantitative eligibility, and masks from evidence CSVs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    from PIL import Image, ImageColor, ImageDraw, ImageFont
except ImportError as exc:  # pragma: no cover
    raise SystemExit("render_curve_support.py requires Pillow") from exc


@dataclass(frozen=True)
class Row:
    point_index: int
    pixel_x: float | None
    pixel_y: float | None
    x: float
    y: float
    observed: bool
    eligible: bool
    below_limit: bool
    eligibility_reason: str
    support_kind: str


@dataclass(frozen=True)
class Series:
    panel_key: str
    series_key: str
    label: str
    color: str
    rows: tuple[Row, ...]


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render all observed curve support while emphasizing quantitatively "
            "eligible runs and retaining explicit masks."
        )
    )
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--series",
        action="append",
        default=[],
        metavar="PANEL/SERIES",
        help="Select one review series explicitly; repeat as needed.",
    )
    parser.add_argument("--title", default="Observed support and quantitative eligibility")
    parser.add_argument("--width", type=int, default=1400)
    parser.add_argument("--height", type=int, default=900)
    return parser.parse_args()


def _flag(value: str | None, *, default: bool) -> bool:
    if value in (None, ""):
        return default
    if value not in {"0", "1"}:
        raise ValueError(f"flag must be 0 or 1, observed {value!r}")
    return value == "1"


def _finite(value: str | None, name: str) -> float:
    if value is None:
        raise ValueError(f"missing {name}")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"{name} must be finite")
    return parsed


def _optional_finite(value: str | None, name: str) -> float | None:
    if value in (None, ""):
        return None
    return _finite(value, name)


def _read_rows(path: Path) -> tuple[Row, ...]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, strict=True)
        fields = set(reader.fieldnames or ())
        required = {"point_index", "x_value", "y_value", "observed"}
        if not required.issubset(fields):
            raise ValueError(f"{path.name} lacks {sorted(required - fields)}")
        rows = []
        previous: int | None = None
        for item in reader:
            index = int(item["point_index"])
            if previous is not None and index <= previous:
                raise ValueError(f"{path.name} point_index is not strictly increasing")
            previous = index
            observed = _flag(item.get("observed"), default=True)
            rows.append(
                Row(
                    point_index=index,
                    pixel_x=_optional_finite(
                        item.get("pixel_x_subpixel", item.get("pixel_x")),
                        "pixel_x",
                    ),
                    pixel_y=_optional_finite(
                        item.get("pixel_y_subpixel", item.get("pixel_y")),
                        "pixel_y",
                    ),
                    x=_finite(item.get("x_value"), "x_value"),
                    y=_finite(item.get("y_value"), "y_value"),
                    observed=observed,
                    eligible=(
                        observed
                        and _flag(
                            item.get("quantitative_measurement_claim_eligible"),
                            default=True,
                        )
                    ),
                    below_limit=_flag(
                        item.get("below_sims_detection_limit"), default=False
                    ),
                    eligibility_reason=item.get("eligibility_reason") or "",
                    support_kind=item.get("support_kind") or "direct_pixel",
                )
            )
    return tuple(rows)


def _manifest(bundle: Path) -> dict[str, Any]:
    path = bundle / "figure_manifest" / "evidence.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("panels"), list):
        raise ValueError("invalid figure manifest")
    return value


def _selection(values: Iterable[str]) -> set[tuple[str, str]]:
    result = set()
    for value in values:
        parts = value.split("/", 1)
        if len(parts) != 2 or not all(parts):
            raise ValueError("--series must use PANEL/SERIES")
        result.add((parts[0], parts[1]))
    return result


def _load(bundle: Path, selected: set[tuple[str, str]]) -> tuple[dict[str, Any], tuple[Series, ...]]:
    manifest = _manifest(bundle)
    result = []
    found = set()
    for panel in manifest["panels"]:
        panel_key = panel["panel_key"]
        for item in panel["series"]:
            key = (panel_key, item["series_key"])
            if selected and key not in selected:
                continue
            found.add(key)
            result.append(
                Series(
                    panel_key=panel_key,
                    series_key=item["series_key"],
                    label=item["label"],
                    color=item["descriptor"]["color"],
                    rows=_read_rows(bundle / item["data_item"]),
                )
            )
    missing = selected - found
    if missing:
        raise ValueError(f"unknown selected series: {sorted(missing)}")
    if not result:
        raise ValueError("no series selected")
    return manifest, tuple(result)


def _runs(rows: Iterable[Row], predicate: Any) -> tuple[tuple[Row, ...], ...]:
    result: list[tuple[Row, ...]] = []
    current: list[Row] = []
    previous: Row | None = None
    for row in rows:
        adjacent = previous is not None and row.point_index == previous.point_index + 1
        if (
            adjacent
            and row.pixel_x is not None
            and previous.pixel_x is not None
            and abs(row.pixel_x - previous.pixel_x) > 1.01
        ):
            adjacent = False
        if predicate(row):
            if current and not adjacent:
                result.append(tuple(current))
                current = []
            current.append(row)
        elif current:
            result.append(tuple(current))
            current = []
        previous = row
    if current:
        result.append(tuple(current))
    return tuple(result)


def _ticks(low: float, high: float, scale: str) -> tuple[float, ...]:
    if scale == "log10":
        first = math.ceil(math.log10(low))
        last = math.floor(math.log10(high))
        return tuple(10.0**power for power in range(first, last + 1))
    return tuple(low + (high - low) * index / 5 for index in range(6))


def _text(draw: ImageDraw.ImageDraw, xy: tuple[float, float], value: str, fill: str = "#202020") -> None:
    draw.text(xy, value, fill=fill, font=ImageFont.load_default())


def _blend_with_white(rgb: tuple[int, int, int], opacity: float) -> tuple[int, int, int]:
    return tuple(round(255 + (channel - 255) * opacity) for channel in rgb)


def _dashed_line(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[float, float]],
    *,
    fill: tuple[int, int, int],
    width: int,
) -> None:
    for start, stop in zip(points, points[1:]):
        dx, dy = stop[0] - start[0], stop[1] - start[1]
        length = math.hypot(dx, dy)
        steps = max(1, math.ceil(length / 4))
        for index in range(0, steps, 2):
            first = index / steps
            last = min(1.0, (index + 1) / steps)
            draw.line(
                (
                    start[0] + dx * first,
                    start[1] + dy * first,
                    start[0] + dx * last,
                    start[1] + dy * last,
                ),
                fill=fill,
                width=width,
            )


def _render(
    manifest: dict[str, Any],
    series: tuple[Series, ...],
    output: Path,
    *,
    title: str,
    width: int,
    height: int,
) -> None:
    if output.exists():
        raise ValueError(f"refusing to overwrite existing output: {output}")
    if width < 640 or height < 480:
        raise ValueError("render size must be at least 640x480")
    panel_keys = tuple(dict.fromkeys(item.panel_key for item in series))
    if len(panel_keys) != 1:
        raise ValueError("one support plot must select series from exactly one panel")
    panel = next(item for item in manifest["panels"] if item["panel_key"] == panel_keys[0])
    x_axis = panel["axis_calibration"]["x"]
    y_axis = panel["axis_calibration"]["y"]
    x_low, x_high = sorted((float(x_axis["value_min"]), float(x_axis["value_max"])))
    y_low, y_high = sorted((float(y_axis["value_min"]), float(y_axis["value_max"])))
    if x_axis["scale"] == "log10" and x_low <= 0:
        raise ValueError("log10 x axis must be positive")
    if y_axis["scale"] == "log10" and y_low <= 0:
        raise ValueError("log10 y axis must be positive")

    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    left, top, right, bottom = 120, 95, width - 55, height - 105

    def x_pixel(value: float) -> float:
        if x_axis["scale"] == "log10":
            if value <= 0:
                return float("nan")
            fraction = (math.log10(value) - math.log10(x_low)) / (
                math.log10(x_high) - math.log10(x_low)
            )
        else:
            fraction = (value - x_low) / (x_high - x_low)
        return left + fraction * (right - left)

    def y_pixel(value: float) -> float:
        if y_axis["scale"] == "log10":
            if value <= 0:
                return float("nan")
            fraction = (math.log10(value) - math.log10(y_low)) / (
                math.log10(y_high) - math.log10(y_low)
            )
        else:
            fraction = (value - y_low) / (y_high - y_low)
        return bottom - fraction * (bottom - top)

    draw.rectangle((left, top, right, bottom), fill="#ffffff", outline="#202020", width=2)
    _text(draw, (left, 28), title)
    _text(draw, ((left + right) / 2 - 70, height - 45), f"{x_axis['unit']}")
    _text(draw, (15, (top + bottom) / 2), f"{y_axis['unit']} ({y_axis['scale']})")

    for value in _ticks(x_low, x_high, x_axis["scale"]):
        px = x_pixel(value)
        draw.line((px, top, px, bottom), fill="#e8e8e8", width=1)
        _text(draw, (px - 18, bottom + 10), f"{value:.3g}")
    for value in _ticks(y_low, y_high, y_axis["scale"]):
        py = y_pixel(value)
        draw.line((left, py, right, py), fill="#e8e8e8", width=1)
        _text(draw, (45, py - 6), f"{value:.1e}" if y_axis["scale"] == "log10" else f"{value:.3g}")

    legend_x = left
    for item in series:
        rgb = ImageColor.getrgb(item.color)
        observed_direct_runs = _runs(
            item.rows,
            lambda row: row.observed and row.support_kind == "direct_pixel",
        )
        observed_shared_runs = _runs(
            item.rows,
            lambda row: row.observed and row.support_kind == "shared_occlusion",
        )
        eligible_direct_runs = _runs(
            item.rows,
            lambda row: row.observed
            and row.eligible
            and row.support_kind == "direct_pixel",
        )
        eligible_shared_runs = _runs(
            item.rows,
            lambda row: row.observed
            and row.eligible
            and row.support_kind == "shared_occlusion",
        )

        for run in observed_direct_runs:
            points = [(x_pixel(row.x), y_pixel(row.y)) for row in run if math.isfinite(y_pixel(row.y))]
            if len(points) >= 2:
                draw.line(points, fill=_blend_with_white(rgb, 0.32), width=2)
            for px, py in points:
                draw.ellipse(
                    (px - 1.5, py - 1.5, px + 1.5, py + 1.5),
                    fill=_blend_with_white(rgb, 0.4),
                )

        for run in observed_shared_runs:
            points = [
                (x_pixel(row.x), y_pixel(row.y))
                for row in run
                if math.isfinite(y_pixel(row.y))
            ]
            if len(points) >= 2:
                _dashed_line(
                    draw,
                    points,
                    fill=_blend_with_white(rgb, 0.32),
                    width=2,
                )
            for px, py in points:
                draw.ellipse(
                    (px - 1.5, py - 1.5, px + 1.5, py + 1.5),
                    outline=_blend_with_white(rgb, 0.4),
                    width=1,
                )

        for run in eligible_direct_runs:
            points = [(x_pixel(row.x), y_pixel(row.y)) for row in run if math.isfinite(y_pixel(row.y))]
            if len(points) >= 2:
                draw.line(points, fill=rgb, width=4)
            for px, py in points:
                radius = 4 if len(points) == 1 else 2
                draw.ellipse((px - radius, py - radius, px + radius, py + radius), fill=rgb)

        for run in eligible_shared_runs:
            points = [
                (x_pixel(row.x), y_pixel(row.y))
                for row in run
                if math.isfinite(y_pixel(row.y))
            ]
            if len(points) >= 2:
                _dashed_line(draw, points, fill=rgb, width=4)
            for px, py in points:
                draw.ellipse((px - 2, py - 2, px + 2, py + 2), outline=rgb, width=1)

        for row in item.rows:
            if not row.observed or row.eligible or not math.isfinite(y_pixel(row.y)):
                continue
            px, py = x_pixel(row.x), y_pixel(row.y)
            if row.below_limit:
                draw.line((px - 3, py - 3, px + 3, py + 3), fill="#666666", width=1)
                draw.line((px - 3, py + 3, px + 3, py - 3), fill="#666666", width=1)
            elif row.eligibility_reason == "same_color_annotation_overlap":
                draw.rectangle(
                    (px - 3, py - 3, px + 3, py + 3),
                    outline="#7a3db8",
                    width=1,
                )
            else:
                draw.ellipse((px - 3, py - 3, px + 3, py + 3), outline="#d98200", width=1)

        draw.line((legend_x, 62, legend_x + 30, 62), fill=rgb, width=4)
        _text(draw, (legend_x + 36, 56), item.label)
        legend_x += max(190, len(item.label) * 8 + 70)

    _text(
        draw,
        (right - 520, height - 70),
        "solid: direct eligible  dashed: shared occlusion  faint: observed  x: below limit  square: annotation mask  circle: other mask",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG", optimize=False, compress_level=9)


def _bind_bundle_provenance(bundle: Path, output: Path) -> None:
    bundle = bundle.resolve()
    output = output.resolve()
    try:
        relative = output.relative_to(bundle)
    except ValueError:
        return
    if len(relative.parts) != 2 or relative.parts[0] != "audit_overlays":
        raise ValueError(
            "bundle-local support output must be audit_overlays/<item>.png"
        )
    if output.suffix.lower() != ".png":
        raise ValueError("bundle-local support output must be PNG")
    manifest_path = bundle / "figure_manifest" / "evidence.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    provenance = manifest.get("provenance")
    if not isinstance(provenance, dict) or not isinstance(
        provenance.get("output_artifacts"), list
    ):
        raise ValueError("figure manifest lacks provenance.output_artifacts")
    data_item = relative.as_posix()
    artifacts = [
        item
        for item in provenance["output_artifacts"]
        if isinstance(item, dict) and item.get("data_item") != data_item
    ]
    artifacts.append(
        {
            "collection": "audit_overlays",
            "data_item": data_item,
            "media_type": "image/png",
            "bytes": output.stat().st_size,
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        }
    )
    provenance["output_artifacts"] = sorted(
        artifacts, key=lambda item: item["data_item"]
    )
    temporary = manifest_path.with_name(f".{manifest_path.name}.tmp")
    temporary.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    temporary.replace(manifest_path)


def main() -> int:
    args = _arguments()
    try:
        if not args.series:
            raise ValueError("select review series explicitly with --series")
        manifest, series = _load(args.bundle, _selection(args.series))
        _render(
            manifest,
            series,
            args.output,
            title=args.title,
            width=args.width,
            height=args.height,
        )
        _bind_bundle_provenance(args.bundle, args.output)
    except (OSError, ValueError, json.JSONDecodeError, csv.Error) as exc:
        raise SystemExit(str(exc)) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
