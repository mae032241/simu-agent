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


@dataclass(frozen=True, slots=True)
class LineTrackingConfig:
    max_vertical_step_px: float
    max_gap_px: int
    max_gap_vertical_displacement_px: float
    max_guide_distance_px: float
    ambiguity_margin_px: float
    guide_weight: float
    min_visible_fraction: float
    max_ambiguous_fraction: float
    skip_penalty: float
    min_points: int
    seed_radius_px: int
    plot_border_exclusion_px: int


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


def _guide_y(
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


def _seed_supported(
    image: Image.Image,
    *,
    seed: tuple[float, float],
    rgb: tuple[int, int, int],
    tolerance: float,
    radius: int,
    exclusions: tuple[tuple[int, int, int, int], ...],
) -> bool:
    pixels = image.load()
    center_x, center_y = int(round(seed[0])), int(round(seed[1]))
    for x in range(max(0, center_x - radius), min(image.width, center_x + radius + 1)):
        for y in range(
            max(0, center_y - radius), min(image.height, center_y + radius + 1)
        ):
            if not _excluded(x, y, exclusions) and _matches(
                pixels[x, y], rgb, tolerance
            ):
                return True
    return False


def _select_path(
    image: Image.Image,
    *,
    rgb: tuple[int, int, int],
    tolerance: float,
    seeds: tuple[tuple[float, float], ...],
    bounds: tuple[int, int, int, int],
    exclusions: tuple[tuple[int, int, int, int], ...],
    config: LineTrackingConfig,
) -> tuple[tuple[TracePoint, ...], int]:
    left, top, right, bottom = bounds
    fallback = (top + bottom - 1) / 2.0
    states: list[dict[str, object]] = []
    terminal_states: list[dict[str, object]] = []
    ambiguous_columns: set[int] = set()
    search_top = min(bottom, top + config.plot_border_exclusion_px)
    search_bottom = max(search_top, bottom - config.plot_border_exclusion_px)

    for x in range(left, right):
        guide = _guide_y(seeds, x, fallback)
        candidates = _column_candidates(
            image,
            x=x,
            top=search_top,
            bottom=search_bottom,
            rgb=rgb,
            tolerance=tolerance,
            exclusions=exclusions,
        )
        guided = [
            candidate
            for candidate in candidates
            if abs(candidate["subpixel_y"] - guide) <= config.max_guide_distance_px
        ]
        next_states: list[dict[str, object]] = []
        candidate_states: list[dict[str, object]] = []
        if states:
            for candidate in candidates:
                choices: list[tuple[float, dict[str, object]]] = []
                for prior in states:
                    last_x = int(prior["last_x"])
                    span = max(1, x - last_x)
                    allowed = (
                        config.max_vertical_step_px
                        if span == 1
                        else config.max_gap_vertical_displacement_px
                    )
                    last_point = prior["last_point"]
                    assert isinstance(last_point, dict)
                    step = abs(
                        candidate["subpixel_y"] - float(last_point["subpixel_y"])
                    )
                    if step <= allowed:
                        choices.append(
                            (
                                float(prior["cost"])
                                + config.guide_weight
                                * abs(candidate["subpixel_y"] - guide)
                                + (1.0 - config.guide_weight) * step / span,
                                prior,
                            )
                        )
                if choices:
                    cost, prior = min(
                        choices,
                        key=lambda item: (
                            item[0],
                            float(
                                (item[1]["last_point"])["subpixel_y"]  # type: ignore[index]
                            ),
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
                {**prior, "cost": float(prior["cost"]) + config.skip_penalty}
                for prior in states
                if x - int(prior["last_x"]) <= config.max_gap_px
            )
        if not states and guided:
            candidate_states = [
                {
                    "cost": config.guide_weight
                    * abs(candidate["subpixel_y"] - guide),
                    "last_point": candidate,
                    "last_x": x,
                    "node": {"point": candidate, "x": x, "previous": None},
                }
                for candidate in guided
            ]
            next_states.extend(candidate_states)
        if states and not next_states:
            terminal_states.append(
                min(states, key=lambda item: float(item["cost"]))
            )
            states = []
            if guided:
                next_states = [
                    {
                        "cost": config.guide_weight
                        * abs(candidate["subpixel_y"] - guide),
                        "last_point": candidate,
                        "last_x": x,
                        "node": {"point": candidate, "x": x, "previous": None},
                    }
                    for candidate in guided
                ]
                candidate_states = next_states
        ranked = sorted(float(item["cost"]) for item in candidate_states)
        if len(ranked) > 1 and ranked[1] - ranked[0] <= config.ambiguity_margin_px:
            ambiguous_columns.add(x)
        states = sorted(
            next_states,
            key=lambda item: (
                float(item["cost"]),
                float((item["last_point"])["subpixel_y"]),  # type: ignore[index]
            ),
        )[:64]
    if states:
        terminal_states.append(min(states, key=lambda item: float(item["cost"])))

    selected: dict[int, dict[str, float]] = {}
    for terminal in terminal_states:
        current = terminal["node"]
        while isinstance(current, dict):
            selected[int(current["x"])] = current["point"]  # type: ignore[assignment]
            current = current["previous"]
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
    declared_gaps: tuple[tuple[int, int], ...],
    config: LineTrackingConfig,
) -> LineTrace:
    """Trace one line and report scientific uncertainty instead of guessing."""

    left, top, right, bottom = bounds
    border = config.plot_border_exclusion_px
    findings = [
        LineFinding(
            "unsupported_seed",
            f"configured seed [{seed[0]:g}, {seed[1]:g}] lacks permitted descriptor support",
        )
        for seed in seeds
        if not (
            left + border <= seed[0] < right - border
            and top + border <= seed[1] < bottom - border
            and _seed_supported(
                image,
                seed=seed,
                rgb=rgb,
                tolerance=tolerance,
                radius=config.seed_radius_px,
                exclusions=exclusions,
            )
        )
    ]
    points, ambiguous_columns = _select_path(
        image,
        rgb=rgb,
        tolerance=tolerance,
        seeds=seeds,
        bounds=bounds,
        exclusions=exclusions,
        config=config,
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
    unexpected_gap = max(
        (
            gap_right - gap_left
            for gap_left, gap_right in gaps
            if not any(
                declared_left <= gap_left and gap_right <= declared_right
                for declared_left, declared_right in declared_gaps
            )
        ),
        default=0,
    )
    visible_fraction = len(set(observed_x)) / width
    ambiguous_fraction = ambiguous_columns / width
    if len(points) < config.min_points:
        findings.append(LineFinding("too_few_points", "too few trace points"))
    if visible_fraction < config.min_visible_fraction:
        findings.append(
            LineFinding(
                "insufficient_visible_support",
                f"visible fraction {visible_fraction:.4f} is below "
                f"{config.min_visible_fraction:.4f}",
            )
        )
    if unexpected_gap > config.max_gap_px:
        findings.append(
            LineFinding(
                "undeclared_gap",
                f"maximum undeclared trace gap {unexpected_gap}px exceeds "
                f"{config.max_gap_px}px",
            )
        )
    if ambiguous_fraction > config.max_ambiguous_fraction:
        findings.append(
            LineFinding(
                "ambiguous_path",
                f"candidate tie fraction {ambiguous_fraction:.4f} exceeds "
                f"{config.max_ambiguous_fraction:.4f}",
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
    "LineTrackingConfig",
    "TracePoint",
    "mark_shared",
    "trace_continuous_line",
]
