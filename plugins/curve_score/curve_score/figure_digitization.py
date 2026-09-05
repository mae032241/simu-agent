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
    LineTrackingConfig,
    TracePoint,
    mark_shared,
    trace_continuous_line,
)
from .figure_digitization_contract import (
    FigureDigitizationRequest,
    FigureDigitizationSeries,
    FigureEligibility,
    FigureLineTracking,
    PdfFigureSource,
    PixelRange,
    RasterFigureSource,
    axis_uncertainty as _axis_uncertainty,
    axis_value as _axis_value,
    recover_requested_image,
)


def _rgb(color: str) -> tuple[int, int, int]:
    return tuple(
        int(color[index : index + 2], 16) for index in (1, 3, 5)
    )  # type: ignore[return-value]


def _tracking(series: FigureDigitizationSeries) -> LineTrackingConfig:
    return LineTrackingConfig(
        **{
            name: getattr(series.tracking, name)
            for name in LineTrackingConfig.__dataclass_fields__
        }
    )


def _binding(
    image: Image.Image, series: FigureDigitizationSeries
) -> tuple[dict[str, object], LineFinding | None]:
    left, top, right, bottom = series.binding_bbox
    target = _rgb(series.color)
    threshold = series.color_tolerance**2
    pixels = image.load()
    count = sum(
        sum((pixels[x, y][index] - target[index]) ** 2 for index in range(3))
        <= threshold
        for x in range(left, right)
        for y in range(top, bottom)
    )
    matched = count >= series.min_color_pixels
    value: dict[str, object] = {
        "source": series.binding_source,
        "visible_label": series.visible_label,
        "status": "matched" if matched else "unresolved",
        "confidence": min(1.0, count / series.min_color_pixels),
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


def _declared_gaps(
    request: FigureDigitizationRequest, series: FigureDigitizationSeries
) -> tuple[PixelRange, ...]:
    shared = tuple(
        interval
        for support in request.shared_support
        if (
            series.series_key in support.covered_series
            if support.mode == "overdraw"
            else series.series_key in support.member_series
        )
        for interval in support.pixel_ranges
    )
    return tuple(sorted({*series.declared_gap_ranges, *shared}))


def _overdraw_findings(
    request: FigureDigitizationRequest,
    direct: dict[str, tuple[TracePoint, ...]],
) -> dict[str, list[LineFinding]]:
    by_x = {
        key: {point.pixel_x_raw: point for point in points}
        for key, points in direct.items()
    }
    definitions = {item.series_key: item for item in request.series}
    declared = set()
    for support in request.shared_support:
        members = (
            support.covered_series
            if support.mode == "overdraw"
            else support.member_series
        )
        declared.update(
            (member, left, right)
            for member in members
            for left, right in support.pixel_ranges
        )
    result = {key: [] for key in definitions}
    for covered_key, covered in by_x.items():
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
                        covered[endpoint].pixel_y_subpixel
                        - donor[endpoint].pixel_y_subpixel
                    )
                    for endpoint in (gap_left - 1, gap_right)
                )
                if endpoint_distance <= definitions[
                    covered_key
                ].tracking.overdraw_candidate_endpoint_distance_px:
                    result[covered_key].append(
                        LineFinding(
                            "possible_overdraw",
                            f"possible overdraw by {donor_key} across pixels "
                            f"[{gap_left},{gap_right})",
                        )
                    )
    return result


def _materialize_shared_support(
    request: FigureDigitizationRequest,
    direct: dict[str, tuple[TracePoint, ...]],
) -> dict[str, tuple[TracePoint, ...]]:
    definitions = {item.series_key: item for item in request.series}
    direct_by_x = {
        key: {point.pixel_x_raw: point for point in points}
        for key, points in direct.items()
    }
    by_x = {key: dict(points) for key, points in direct_by_x.items()}
    for support in request.shared_support:
        if support.mode == "overdraw":
            donor = direct_by_x[support.visible_series]
            donor_result = by_x[support.visible_series]
            for left, right in support.pixel_ranges:
                required = set(range(left, right))
                if not required.issubset(donor):
                    raise ValueError(
                        "shared-support donor lacks direct pixel "
                        f"{min(required - set(donor))}"
                    )
                for covered_key in support.covered_series:
                    covered_direct = direct_by_x[covered_key]
                    covered_result = by_x[covered_key]
                    if left - 1 not in covered_direct or right not in covered_direct:
                        raise ValueError("shared support lacks covered-series endpoints")
                    endpoint_distance = max(
                        abs(
                            covered_direct[endpoint].pixel_y_subpixel
                            - donor[endpoint].pixel_y_subpixel
                        )
                        for endpoint in (left - 1, right)
                    )
                    if endpoint_distance > support.max_endpoint_distance_px:
                        raise ValueError(
                            "shared-support endpoint distance exceeds its contract"
                        )
                    if any(pixel_x in covered_direct for pixel_x in required):
                        raise ValueError(
                            "shared support may fill only missing covered pixels"
                        )
                    domain = definitions[covered_key].pixel_range or (
                        request.plot_bbox[0],
                        request.plot_bbox[2],
                    )
                    for pixel_x in range(left, right):
                        donor_point = donor[pixel_x]
                        covered_result[pixel_x] = replace(
                            mark_shared(
                                donor_point,
                                group=support.group_key,
                                source_series=support.visible_series,
                                support_kind="shared_occlusion",
                                uncertainty_px=max(
                                    donor_point.uncertainty_px,
                                    endpoint_distance + 0.5,
                                ),
                            ),
                            point_index=pixel_x - domain[0],
                        )
                    for pixel_x in range(left, right):
                        donor_result[pixel_x] = mark_shared(
                            donor[pixel_x],
                            group=support.group_key,
                            source_series=support.visible_series,
                            support_kind="direct_pixel",
                        )
            continue

        members = support.member_series
        for left, right in support.pixel_ranges:
            for member in members:
                points = direct_by_x[member]
                if left - 1 not in points or right not in points:
                    raise ValueError(
                        "coincident overlap lacks direct member endpoints"
                    )
                if not any(pixel_x in points for pixel_x in range(left, right)):
                    raise ValueError(
                        "coincident overlap requires direct contribution from every member"
                    )
            for endpoint in (left - 1, right):
                endpoint_values = tuple(
                    direct_by_x[member][endpoint].pixel_y_subpixel
                    for member in members
                )
                if max(endpoint_values) - min(endpoint_values) > support.max_member_distance_px:
                    raise ValueError(
                        "coincident-overlap endpoint distance exceeds its contract"
                    )
            sources = _coincident_sources(
                members=members,
                left=left,
                right=right,
                direct_by_x=direct_by_x,
            )
            for pixel_x in range(left, right):
                available = tuple(
                    member for member in members if pixel_x in direct_by_x[member]
                )
                if not available:
                    raise ValueError(
                        f"coincident overlap lacks direct pixel {pixel_x}"
                    )
                visible_points = tuple(
                    direct_by_x[member][pixel_x] for member in available
                )
                visible_y = tuple(point.pixel_y_subpixel for point in visible_points)
                if max(visible_y) - min(visible_y) > support.max_member_distance_px:
                    raise ValueError(
                        "coincident-overlap member distance exceeds its contract"
                    )
                source_member = sources[pixel_x]
                source_point = direct_by_x[source_member][pixel_x]
                spread = max(visible_y) - min(visible_y)
                for member in members:
                    domain = definitions[member].pixel_range or (
                        request.plot_bbox[0],
                        request.plot_bbox[2],
                    )
                    by_x[member][pixel_x] = replace(
                        mark_shared(
                            source_point,
                            group=support.group_key,
                            source_series=source_member,
                            support_kind=(
                                "direct_pixel"
                                if member == source_member
                                else "shared_occlusion"
                            ),
                            uncertainty_px=max(
                                source_point.uncertainty_px,
                                spread + 0.5,
                            ),
                        ),
                        point_index=pixel_x - domain[0],
                    )
    return {
        key: tuple(value[x] for x in sorted(value)) for key, value in by_x.items()
    }


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
    for pixel_x, available in available_by_x.items():
        if not available:
            raise ValueError(f"coincident overlap lacks direct pixel {pixel_x}")

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

    if any(not assign(member, set()) for member in members):
        raise ValueError(
            "coincident overlap cannot preserve one direct source for every member"
        )
    return {
        pixel_x: member_by_x[pixel_x]
        if pixel_x in member_by_x
        else available_by_x[pixel_x][0]
        for pixel_x in range(left, right)
    }


def _inside(pixel_x: int, ranges: tuple[PixelRange, ...]) -> bool:
    return any(left <= pixel_x < right for left, right in ranges)


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
        below_limit = _inside(
            point.pixel_x_raw,
            series.eligibility.below_detection_limit_pixel_ranges,
        )
        plain_ineligible = _inside(
            point.pixel_x_raw, series.eligibility.ineligible_pixel_ranges
        )
        region_reason = next(
            (
                region.reason
                for region in series.eligibility.ineligible_pixel_regions
                if region.pixel_range[0] <= point.pixel_x_raw < region.pixel_range[1]
            ),
            "",
        )
        shared_ineligible = (
            point.support_kind == "shared_occlusion" and not point.shared_eligible
        )
        eligible = bool(
            series.eligibility.default_eligible
            and not series_unresolved
            and not below_limit
            and not plain_ineligible
            and not region_reason
            and not shared_ineligible
        )
        reason = (
            "below_detection_limit"
            if below_limit
            else region_reason
            if region_reason
            else "ineligible_range"
            if plain_ineligible
            else "shared_occlusion"
            if shared_ineligible
            else "series_unresolved"
            if series_unresolved
            else "series_default_ineligible"
            if not series.eligibility.default_eligible
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
                "below_sims_detection_limit": int(below_limit),
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
    overlay = image.copy()
    draw = ImageDraw.Draw(overlay)
    plot, _, series_values = request.require_ready()
    draw.rectangle(plot, outline="#666666", width=1)
    colors = ("#00bfff", "#ff00ff", "#ffb000", "#00b060")
    for index, series in enumerate(series_values):
        color = colors[index % len(colors)]
        draw.rectangle(series.binding_bbox, outline=color, width=2)
        for x, y in series.seeds:
            draw.line((x - 3, y, x + 3, y), fill=color, width=1)
            draw.line((x, y - 3, x, y + 3), fill=color, width=1)
        point_color = "#ff7f00" if series.series_key in unresolved else "#00b050"
        for point in traces[series.series_key]:
            x = int(round(point.pixel_x_subpixel))
            y = int(round(point.pixel_y_subpixel))
            draw.point((x, y), fill=point_color)
        label_x, label_y = series.binding_bbox[:2]
        draw.text((label_x, max(0, label_y - 12)), series.series_key, fill=color)
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
        domain = series.pixel_range or (plot[0], plot[2])
        trace = trace_continuous_line(
            image,
            rgb=_rgb(series.color),
            tolerance=series.color_tolerance,
            seeds=series.seeds,
            bounds=(domain[0], plot[1], domain[1], plot[3]),
            exclusions=(*request.exclusion_regions, *series.exclusion_regions),
            declared_gaps=_declared_gaps(request, series),
            config=_tracking(series),
        )
        local.extend(trace.findings)
        direct[series.series_key] = trace.points
        findings[series.series_key] = local
    for key, values in _overdraw_findings(request, direct).items():
        findings[key].extend(values)
    for support in request.shared_support:
        if support.mode == "coincident_overlap" and any(
            bindings[member]["status"] != "matched"
            for member in support.member_series
        ):
            raise ValueError(
                "coincident overlap requires independently matched member bindings"
            )
    traces = _materialize_shared_support(request, direct)

    siblings: dict[str, tuple[bytes, str]] = {
        f"source_panels/{request.panel_key}.png": (recovered.content, "image/png"),
        f"audit_overlays/{request.panel_key}--identity-fidelity.png": (
            _audit_overlay(
                image,
                request,
                traces,
                {key for key, values in findings.items() if values},
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
        series_unresolved = (
            bool(local_findings) or bindings[key]["status"] != "matched"
        )
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
        domain = series.pixel_range or (plot[0], plot[2])
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
        )
        manifest_series.append(
            {
                "series_key": key,
                "label": series.label,
                "primitive_kind": "line",
                "descriptor": {
                    "color": series.color,
                    "color_tolerance": series.color_tolerance,
                    "line_style": "solid",
                },
                "data_item": item,
                "binding": bindings[key],
                "point_count": len(points),
                "visible_fraction": round(visible_fraction, 9),
                "max_gap_px": max_gap,
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
                "shared_support": [
                    support.model_dump(mode="json")
                    for support in request.shared_support
                ],
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
    "FigureEligibility",
    "FigureLineTracking",
    "PdfFigureSource",
    "RasterFigureSource",
    "build_digitized_figure_bundle",
    "recover_requested_image",
]
