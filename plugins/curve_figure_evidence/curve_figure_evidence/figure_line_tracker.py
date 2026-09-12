"""Small deterministic tracker for visibly continuous, guide-anchored plot lines."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Iterable

from PIL import Image


@dataclass(frozen=True, slots=True)
class TracePoint:
    point_index: int
    pixel_x_raw: int
    pixel_y_raw: int
    pixel_x_subpixel: float
    pixel_y_subpixel: float
    uncertainty_px: float
    support_kind: str = "direct_pixel"
    coordinate_ownership: str = "exclusive"
    shared_group: str = ""
    support_source_series: str = ""
    shared_eligible: bool = False
    identity_ambiguous: bool = False


@dataclass(frozen=True, slots=True)
class LineFinding:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class LineTrace:
    points: tuple[TracePoint, ...]
    visible_fraction: float
    max_gap_px: int
    ambiguous_fraction: float
    findings: tuple[LineFinding, ...]


def _matches(pixel: tuple[int, ...], rgb: tuple[int, int, int], tolerance: float) -> bool:
    return sum(
        (int(pixel[index]) - rgb[index]) ** 2 for index in range(3)
    ) <= tolerance**2


def _excluded(
    x: int, y: int, regions: Iterable[tuple[int, int, int, int]]
) -> bool:
    return any(
        left <= x < right and top <= y < bottom
        for left, top, right, bottom in regions
    )


def guide_y(
    seeds: tuple[tuple[float, float], ...], x: float, fallback: float
) -> float:
    if x <= seeds[0][0]:
        return seeds[0][1]
    if x >= seeds[-1][0]:
        return seeds[-1][1]
    for (left_x, left_y), (right_x, right_y) in zip(seeds, seeds[1:]):
        if left_x <= x <= right_x:
            if right_x == left_x:
                return (left_y + right_y) / 2.0
            fraction = (x - left_x) / (right_x - left_x)
            return left_y + fraction * (right_y - left_y)
    return fallback


def _column_candidates(
    image: Image.Image,
    *,
    x: int,
    top: int,
    bottom: int,
    rgb: tuple[int, int, int],
    tolerance: float,
    exclusions: tuple[tuple[int, int, int, int], ...],
) -> list[dict[str, float]]:
    pixels = image.load()
    matching = [
        y
        for y in range(top, bottom)
        if not _excluded(x, y, exclusions)
        and _matches(pixels[x, y], rgb, tolerance)
    ]
    if not matching:
        return []
    groups: list[list[int]] = [[matching[0]]]
    for y in matching[1:]:
        if y == groups[-1][-1] + 1:
            groups[-1].append(y)
        else:
            groups.append([y])
    result: list[dict[str, float]] = []
    for group in groups:
        weights = []
        for y in group:
            distance = math.sqrt(
                sum(
                    (int(pixels[x, y][index]) - rgb[index]) ** 2
                    for index in range(3)
                )
            )
            weights.append(max(1.0, tolerance + 1.0 - distance))
        subpixel_y = sum(
            y * weight for y, weight in zip(group, weights)
        ) / sum(weights)
        raw_y = min(group, key=lambda y: (abs(y - subpixel_y), y))
        result.append(
            {
                "raw_y": float(raw_y),
                "subpixel_y": subpixel_y,
                "uncertainty_px": max(0.5, len(group) / 2.0),
            }
        )
    return result


def _select_path(
    image: Image.Image,
    *,
    rgb: tuple[int, int, int],
    tolerance: float,
    seeds: tuple[tuple[float, float], ...],
    bounds: tuple[int, int, int, int],
    exclusions: tuple[tuple[int, int, int, int], ...],
) -> tuple[tuple[TracePoint, ...], int]:
    left, top, right, bottom = bounds
    fallback = (top + bottom - 1) / 2.0
    selected: dict[int, dict[str, float]] = {}
    ambiguous_columns: set[int] = set()
    for x in range(left, right):
        guide = guide_y(seeds, x, fallback)
        candidates = _column_candidates(
            image,
            x=x,
            top=top,
            bottom=bottom,
            rgb=rgb,
            tolerance=tolerance,
            exclusions=exclusions,
        )
        if not candidates:
            continue
        ranked = sorted(
            candidates,
            key=lambda candidate: (
                abs(candidate["subpixel_y"] - guide),
                candidate["subpixel_y"],
            ),
        )
        selected[x] = ranked[0]
        if (
            len(ranked) > 1
            and abs(ranked[0]["subpixel_y"] - guide)
            == abs(ranked[1]["subpixel_y"] - guide)
        ):
            ambiguous_columns.add(x)
    return (
        tuple(
            TracePoint(
                point_index=x - left,
                pixel_x_raw=x,
                pixel_y_raw=int(selected[x]["raw_y"]),
                pixel_x_subpixel=float(x),
                pixel_y_subpixel=selected[x]["subpixel_y"],
                uncertainty_px=selected[x]["uncertainty_px"],
                identity_ambiguous=x in ambiguous_columns,
            )
            for x in sorted(selected)
        ),
        len(ambiguous_columns),
    )


def trace_continuous_line(
    image: Image.Image,
    *,
    rgb: tuple[int, int, int],
    tolerance: float,
    seeds: tuple[tuple[float, float], ...],
    bounds: tuple[int, int, int, int],
    exclusions: tuple[tuple[int, int, int, int], ...],
) -> LineTrace:
    """Select real descriptor-colored pixels nearest the Agent's visible guide."""

    left, top, right, bottom = bounds
    findings: list[LineFinding] = []
    points, ambiguous_columns = _select_path(
        image,
        rgb=rgb,
        tolerance=tolerance,
        seeds=seeds,
        bounds=bounds,
        exclusions=exclusions,
    )
    width = max(1, right - left)
    observed_x = [point.pixel_x_raw for point in points]
    gaps: list[tuple[int, int]] = []
    if observed_x:
        if observed_x[0] > left:
            gaps.append((left, observed_x[0]))
        gaps.extend(
            (previous + 1, current)
            for previous, current in zip(observed_x, observed_x[1:])
            if current - previous > 1
        )
        if observed_x[-1] < right - 1:
            gaps.append((observed_x[-1] + 1, right))
    else:
        gaps.append((left, right))
    visible_fraction = len(set(observed_x)) / width
    ambiguous_fraction = ambiguous_columns / width
    if ambiguous_columns:
        findings.append(
            LineFinding(
                "ambiguous_path",
                f"{ambiguous_columns} columns have equally near real pixel clusters",
            )
        )
    max_gap = max((right - left,), default=width)
    if observed_x:
        max_gap = max(
            observed_x[0] - left,
            right - 1 - observed_x[-1],
            *(current - previous - 1 for previous, current in zip(observed_x, observed_x[1:])),
        )
    return LineTrace(
        points=points,
        visible_fraction=visible_fraction,
        max_gap_px=max_gap,
        ambiguous_fraction=ambiguous_fraction,
        findings=tuple(findings),
    )


def mark_shared(
    point: TracePoint,
    *,
    group: str,
    source_series: str,
    support_kind: str,
    uncertainty_px: float | None = None,
    shared_eligible: bool = False,
) -> TracePoint:
    return replace(
        point,
        support_kind=support_kind,
        coordinate_ownership="shared",
        shared_group=group,
        support_source_series=source_series,
        uncertainty_px=(
            point.uncertainty_px if uncertainty_px is None else uncertainty_px
        ),
        shared_eligible=shared_eligible,
    )


__all__ = [
    "LineFinding",
    "LineTrace",
    "TracePoint",
    "guide_y",
    "mark_shared",
    "trace_continuous_line",
]
