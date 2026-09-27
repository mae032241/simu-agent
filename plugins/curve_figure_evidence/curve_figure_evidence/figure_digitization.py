"""Deterministic, source-bound digitization for visibly continuous plot lines."""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import replace

from PIL import Image, ImageDraw

from scidiscovery.artifact_agent.schema.common import canonical_json

from .figure_evidence import validate_figure_evidence_manifest
from .figure_evidence_validation import build_figure_evidence_validation_report
from .figure_line_tracker import (
    LineFinding,
    TracePoint,
    guide_y,
    mark_shared,
    trace_continuous_line,
)
from .figure_numeric_redraw import render_numeric_redraw
from .figure_digitization_contract import (
    FigureDigitizationRequest,
    FigureDigitizationSeries,
    PdfFigureSource,
    RasterFigureSource,
    axis_uncertainty as _axis_uncertainty,
    axis_value as _axis_value,
    recover_requested_image,
)


COLOR_MATCH_TOLERANCE = 24.0


def _rgb(color: str) -> tuple[int, int, int]:
    return tuple(
        int(color[index : index + 2], 16) for index in (1, 3, 5)
    )  # type: ignore[return-value]


def _binding(
    image: Image.Image, series: FigureDigitizationSeries
) -> tuple[dict[str, object], LineFinding | None]:
    left, top, right, bottom = series.binding_bbox
    target = _rgb(series.color)
    threshold = COLOR_MATCH_TOLERANCE**2
    pixels = image.load()
    count = sum(
        sum((pixels[x, y][index] - target[index]) ** 2 for index in range(3))
        <= threshold
        for x in range(left, right)
        for y in range(top, bottom)
    )
    matched = count > 0
    value: dict[str, object] = {
        "source": series.binding_source,
        "visible_label": series.visible_label,
        "status": "matched" if matched else "unresolved",
        "confidence": 1.0 if matched else 0.0,
        "alternatives": [],
    }
    return value, (
        None
        if matched
        else LineFinding(
            "binding_pixels_missing",
            "binding box lacks the declared series color",
        )
    )


def _derive_shared_support(
    request: FigureDigitizationRequest,
    direct: dict[str, tuple[TracePoint, ...]],
) -> tuple[dict[str, tuple[TracePoint, ...]], list[dict[str, object]]]:
    """Share only directly observed pixel clusters whose supports intersect."""

    definitions = {item.series_key: item for item in request.series}
    direct_by_x = {
        key: {point.pixel_x_raw: point for point in points}
        for key, points in direct.items()
    }
    by_x = {key: dict(points) for key, points in direct_by_x.items()}
    memberships: dict[tuple[str, ...], list[int]] = {}
    all_x = sorted(
        {pixel_x for points in direct_by_x.values() for pixel_x in points}
    )
    for pixel_x in all_x:
        available = sorted(
            (key, points[pixel_x])
            for key, points in direct_by_x.items()
            if pixel_x in points
        )
        candidates = set()
        for source_key, source_point in available:
            low = source_point.pixel_y_subpixel - source_point.uncertainty_px
            high = source_point.pixel_y_subpixel + source_point.uncertainty_px
            members = []
            for key, definition in definitions.items():
                domain = (request.plot_bbox[0], request.plot_bbox[2])
                if not domain[0] <= pixel_x < domain[1]:
                    continue
                location = guide_y(
                    definition.seeds,
                    pixel_x,
                    (request.plot_bbox[1] + request.plot_bbox[3] - 1) / 2.0,
                )
                if key == source_key or low < location < high:
                    members.append(key)
            candidates.add(tuple(sorted(members)))
        used: set[str] = set()
        for members in sorted(candidates, key=lambda value: (-len(value), value)):
            selected = tuple(key for key in members if key not in used)
            if len(selected) < 2:
                continue
            memberships.setdefault(selected, []).append(pixel_x)
            used.update(selected)

    records: list[dict[str, object]] = []
    for members, columns in sorted(memberships.items()):
        runs: list[tuple[int, int]] = []
        start = previous = columns[0]
        for pixel_x in columns[1:]:
            if pixel_x != previous + 1:
                runs.append((start, previous + 1))
                start = pixel_x
            previous = pixel_x
        runs.append((start, previous + 1))
        for left, right in runs:
            group = f"shared_{_sha256(canonical_json((members, left, right)))[:20]}"
            sources = _coincident_sources(
                members=members,
                left=left,
                right=right,
                direct_by_x=direct_by_x,
            )
            max_spread = 0.0
            for pixel_x in range(left, right):
                original = [
                    direct_by_x[key][pixel_x]
                    for key in members
                    if pixel_x in direct_by_x[key]
                ]
                max_spread = max(
                    max_spread,
                    max(point.pixel_y_subpixel for point in original)
                    - min(point.pixel_y_subpixel for point in original),
                )
                source_key = sources[pixel_x]
                source_point = direct_by_x[source_key][pixel_x]
                for key in members:
                    domain = (request.plot_bbox[0], request.plot_bbox[2])
                    by_x[key][pixel_x] = replace(
                        mark_shared(
                            source_point,
                            group=group,
                            source_series=source_key,
                            support_kind=(
                                "direct_pixel"
                                if key == source_key
                                else "shared_occlusion"
                            ),
                            shared_eligible=True,
                        ),
                        point_index=pixel_x - domain[0],
                        identity_ambiguous=any(
                            point.identity_ambiguous for point in original
                        ),
                    )
            records.append(
                {
                    "group_key": group,
                    "member_series": list(members),
                    "pixel_ranges": [[left, right]],
                    "mode": "coincident_overlap",
                    "max_member_distance_px": max_spread,
                }
            )
    return (
        {key: tuple(points[x] for x in sorted(points)) for key, points in by_x.items()},
        records,
    )


def _coincident_sources(
    *,
    members: tuple[str, ...],
    left: int,
    right: int,
    direct_by_x: dict[str, dict[int, TracePoint]],
) -> dict[int, str]:
    """Choose real per-column sources while preserving one source for every member."""

    available_by_x = {
        pixel_x: tuple(
            member for member in members if pixel_x in direct_by_x[member]
        )
        for pixel_x in range(left, right)
    }

    member_by_x: dict[int, str] = {}

    def assign(member: str, visited: set[int]) -> bool:
        for pixel_x in range(left, right):
            if pixel_x in visited or pixel_x not in direct_by_x[member]:
                continue
            visited.add(pixel_x)
            previous = member_by_x.get(pixel_x)
            if previous is None or assign(previous, visited):
                member_by_x[pixel_x] = member
                return True
        return False

    for member in members:
        assign(member, set())
    return {
        pixel_x: member_by_x[pixel_x]
        if pixel_x in member_by_x
        else available_by_x[pixel_x][0]
        for pixel_x in range(left, right)
        if available_by_x[pixel_x]
    }


def _curve_csv(
    request: FigureDigitizationRequest,
    series: FigureDigitizationSeries,
    points: tuple[TracePoint, ...],
    *,
    series_unresolved: bool,
) -> bytes:
    _, axes, _ = request.require_ready()
    fields = (
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
    )
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for point in points:
        eligible = bool(
            not series_unresolved and not point.identity_ambiguous
        )
        reason = (
            "ambiguous_path"
            if point.identity_ambiguous
            else "series_unresolved"
            if series_unresolved
            else ""
        )
        writer.writerow(
            {
                "panel_key": request.panel_key,
                "series_key": series.series_key,
                "point_index": point.point_index,
                "pixel_x_raw": point.pixel_x_raw,
                "pixel_y_raw": point.pixel_y_raw,
                "pixel_x_subpixel": format(point.pixel_x_subpixel, ".17g"),
                "pixel_y_subpixel": format(point.pixel_y_subpixel, ".17g"),
                "x_value": format(
                    _axis_value(axes.x, point.pixel_x_subpixel), ".17g"
                ),
                "y_value": format(
                    _axis_value(axes.y, point.pixel_y_subpixel), ".17g"
                ),
                "uncertainty_px": format(point.uncertainty_px, ".17g"),
                "x_uncertainty": format(
                    _axis_uncertainty(
                        axes.x, point.pixel_x_subpixel, point.uncertainty_px
                    ),
                    ".17g",
                ),
                "y_uncertainty": format(
                    _axis_uncertainty(
                        axes.y, point.pixel_y_subpixel, point.uncertainty_px
                    ),
                    ".17g",
                ),
                "observed": 1,
                "quantitative_measurement_claim_eligible": int(eligible),
                "below_sims_detection_limit": 0,
                "eligibility_reason": reason,
                "support_kind": point.support_kind,
                "coordinate_ownership": point.coordinate_ownership,
                "shared_group": point.shared_group,
                "support_source_series": point.support_source_series,
            }
        )
    return stream.getvalue().encode("utf-8")


def _audit_overlay(
    image: Image.Image,
    request: FigureDigitizationRequest,
    traces: dict[str, tuple[TracePoint, ...]],
    unresolved: set[str],
) -> bytes:
    plot, axes, series_values = request.require_ready()
    # Each source-sized panel has its own trace, so coincident members do not
    # paint over one another. The strip below it reports observed columns only.
    panel_height = image.height + 70
    overlay = Image.new(
        "RGB", (max(image.width, 420), panel_height * len(series_values)), "white"
    )
    draw = ImageDraw.Draw(overlay)
    colors = ("#00bfff", "#ff00ff", "#ffb000", "#00b060")
    for index, series in enumerate(series_values):
        color = colors[index % len(colors)]
        offset = index * panel_height + 25
        overlay.paste(image, (0, offset))
        draw.text((4, offset - 20), series.series_key, fill=color)
        left, top, right, bottom = series.binding_bbox
        draw.rectangle((left, top + offset, right, bottom + offset), outline=color, width=1)
        for x, y in series.seeds:
            draw.line((x - 3, y + offset, x + 3, y + offset), fill="#888888", width=1)
            draw.line((x, y + offset - 3, x, y + offset + 3), fill="#888888", width=1)
        domain = (plot[0], plot[2])
        strip_y = offset + image.height + 3
        draw.rectangle((domain[0], strip_y, domain[1] - 1, strip_y + 4), fill="#aaaaaa")
        for point in traces[series.series_key]:
            if point.shared_group:
                x, y = point.pixel_x_subpixel, point.pixel_y_subpixel + offset
                draw.ellipse((x - 2, y - 2, x + 2, y + 2), outline="#d6a000")
        for point in traces[series.series_key]:
            x = int(round(point.pixel_x_subpixel))
            y = int(round(point.pixel_y_subpixel))
            local_limit = (
                series.series_key in unresolved
                or point.identity_ambiguous
            )
            point_color = "#ff4000" if local_limit else color
            draw.point((x, y + offset), fill=point_color)
            draw.line((x, strip_y, x, strip_y + 4), fill=(
                "#ff4000" if local_limit else "#d6a000" if point.shared_group else color
            ))
        draw.text((4, strip_y + 9), "Trace: series color | shared: gold ring", fill="#333333")
        draw.text((4, strip_y + 21), "Coverage: gray missing | red local limit", fill="#333333")
    stream = io.BytesIO()
    overlay.save(stream, format="PNG", optimize=False, compress_level=9)
    return stream.getvalue()


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def build_digitized_figure_bundle(
    source_content: bytes,
    request_content: bytes,
) -> tuple[dict[str, tuple[bytes, str]], dict[str, object]]:
    """Build and mechanically validate one bounded continuous-line evidence family."""

    request = FigureDigitizationRequest.model_validate_json(request_content, strict=True)
    plot, axes, series_values = request.require_ready()
    recovered = recover_requested_image(source_content, request)
    image = Image.open(io.BytesIO(recovered.content)).convert("RGB")

    direct: dict[str, tuple[TracePoint, ...]] = {}
    findings: dict[str, list[LineFinding]] = {}
    bindings: dict[str, dict[str, object]] = {}
    for series in series_values:
        binding, binding_finding = _binding(image, series)
        bindings[series.series_key] = binding
        local = [] if binding_finding is None else [binding_finding]
        domain = (plot[0], plot[2])
        trace = trace_continuous_line(
            image,
            rgb=_rgb(series.color),
            tolerance=COLOR_MATCH_TOLERANCE,
            seeds=series.seeds,
            bounds=(domain[0], plot[1], domain[1], plot[3]),
            exclusions=(*request.exclusion_regions, *series.exclusion_regions),
        )
        local.extend(trace.findings)
        direct[series.series_key] = trace.points
        findings[series.series_key] = local
    traces, shared_support = _derive_shared_support(request, direct)

    siblings: dict[str, tuple[bytes, str]] = {
        f"source_panels/{request.panel_key}.png": (recovered.content, "image/png"),
        f"audit_overlays/{request.panel_key}--identity-fidelity.png": (
            _audit_overlay(
                image,
                request,
                traces,
                {key for key, binding in bindings.items() if binding["status"] != "matched"},
            ),
            "image/png",
        ),
    }
    manifest_series = []
    ambiguities = []
    qualified_count = 0
    for series in series_values:
        key = series.series_key
        points = traces[key]
        local_findings = findings[key]
        # Tracking diagnostics describe extraction, not scientific identity.
        # A missed seed or missing column cannot revoke other measured pixels.
        series_unresolved = bindings[key]["status"] != "matched"
        item = f"curve_tables/{request.panel_key}--{key}.csv"
        siblings[item] = (
            _curve_csv(
                request,
                series,
                points,
                series_unresolved=series_unresolved,
            ),
            "text/csv",
        )
        domain = (plot[0], plot[2])
        observed_x = sorted({point.pixel_x_raw for point in points})
        visible_fraction = len(observed_x) / max(1, domain[1] - domain[0])
        max_gap = max(
            [
                observed_x[0] - domain[0],
                domain[1] - 1 - observed_x[-1],
                *(
                    right - left - 1
                    for left, right in zip(observed_x, observed_x[1:])
                ),
            ]
            if observed_x
            else [domain[1] - domain[0]]
        )
        if not series_unresolved:
            qualified_count += 1
        ambiguities.extend(
            {
                "panel_key": request.panel_key,
                "series_key": key,
                "message": finding.message,
                "candidates": [],
            }
            for finding in local_findings
            if finding.code == "binding_pixels_missing"
        )
        manifest_series.append(
            {
                "series_key": key,
                "label": series.label,
                "primitive_kind": "line",
                "descriptor": {
                    "color": series.color,
                    "color_tolerance": COLOR_MATCH_TOLERANCE,
                    "line_style": "solid",
                },
                "data_item": item,
                "binding": bindings[key],
                "point_count": len(points),
                "visible_fraction": round(visible_fraction, 9),
                "max_gap_px": max_gap,
                "tracking_diagnostics": [
                    finding.message for finding in local_findings
                    if finding.code != "binding_pixels_missing"
                ],
                "uncertainty_px": round(
                    max(
                        (
                            point.uncertainty_px
                            + max(
                                axes.x.reprojection_error_px,
                                axes.y.reprojection_error_px,
                            )
                            for point in points
                        ),
                        default=max(
                            axes.x.reprojection_error_px,
                            axes.y.reprojection_error_px,
                        ),
                    ),
                    6,
                ),
            }
        )
    siblings[f"audit_overlays/{request.panel_key}--numeric-redraw.png"] = (
        render_numeric_redraw(
            request,
            {
                series.series_key: siblings[
                    f"curve_tables/{request.panel_key}--{series.series_key}.csv"
                ][0]
                for series in series_values
            },
        ),
        "image/png",
    )
    manifest = {
        "schema_version": "scidiscovery.figure-evidence-manifest.v1",
        "figure_key": request.figure_key,
        "status": "unresolved" if ambiguities else "qualified",
        "source": {
            "source_name": "paper_source",
            "page": (
                request.source.page
                if isinstance(request.source, PdfFigureSource)
                else "supplied raster"
            ),
            "figure": request.figure,
            "image_sha256": recovered.image_sha256,
            "width": image.width,
            "height": image.height,
            **(
                {
                    "pdf_sha256": request.source.source_sha256,
                    "pdf_page": request.source.page,
                    "pdf_object": (
                        f"{request.source.pdf_object_id} "
                        f"{request.source.pdf_object_generation}"
                    ),
                }
                if isinstance(request.source, PdfFigureSource)
                else {}
            ),
        },
        "panels": [
            {
                "panel_key": request.panel_key,
                "citation": request.citation,
                "axis_calibration": axes.model_dump(mode="json"),
                "series": manifest_series,
                "shared_support": shared_support,
            }
        ],
        "metrics": {
            "panel_count": 1,
            "series_count": len(manifest_series),
            "qualified_series_count": qualified_count,
            "total_point_count": sum(len(points) for points in traces.values()),
            "minimum_visible_fraction": min(
                item["visible_fraction"] for item in manifest_series
            ),
        },
        "ambiguities": ambiguities,
        "provenance": {
            "spec_sha256": _sha256(canonical_json(request.model_dump(mode="json"))),
            "recovery_tool": recovered.recovery_tool,
            "recovery_tool_version": recovered.recovery_tool_version,
            "output_artifacts": [
                {
                    "collection": name.split("/", 1)[0],
                    "data_item": name,
                    "sha256": _sha256(content),
                    "bytes": len(content),
                    "media_type": media_type,
                }
                for name, (content, media_type) in sorted(siblings.items())
            ],
        },
    }
    manifest_raw = canonical_json(validate_figure_evidence_manifest(manifest))
    report = build_figure_evidence_validation_report(
        manifest_data_item="figure_manifest/evidence.json",
        manifest_content=manifest_raw,
        sibling_files=siblings,
    )
    files = {
        "figure_manifest/evidence.json": (manifest_raw, "application/json"),
        **siblings,
        "validation_reports/validation_report.json": (
            canonical_json(report),
            "application/json",
        ),
    }
    return files, report


__all__ = [
    "FigureDigitizationRequest",
    "FigureDigitizationSeries",
    "PdfFigureSource",
    "RasterFigureSource",
    "build_digitized_figure_bundle",
    "recover_requested_image",
]
