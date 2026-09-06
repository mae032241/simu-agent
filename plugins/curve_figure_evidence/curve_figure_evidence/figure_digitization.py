"""Deterministic, source-bound digitization for visibly continuous plot lines."""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import replace

from PIL import Image, ImageDraw

from scidiscovery.artifact_agent.schema.common import canonical_json

from .figure_evidence import validate_figure_evidence_manifest
from .figure_evidence import FigurePanelAxisCalibration, FigureEvidenceValidationReport
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
    FigureExtractionIntent, FigureMeasurementRequest, replay_reference_detection,
    validate_intent_candidates, calibration_from_tick_pairs,
)


def build_automatic_figure_bundle(source_content: bytes, intent_content: bytes):
    """Replay raw bytes, validate semantic choices, and measure only detector pixels."""
    intent = FigureExtractionIntent.model_validate_json(intent_content, strict=True)
    detected = replay_reference_detection(source_content, intent.source_page)
    selection = validate_intent_candidates(intent, detected)
    image, detection, plot = selection if selection else (
        (detected.images[0], detected.detections[0], None) if detected.images else (None, None, None))
    reasons = set(detected.unresolved) | set(intent.unresolved_reasons)
    reasons.update(item.reason for item in intent.rejected_candidates)
    axes = None
    selected_paths = []
    if detection:
        reasons.update(detection.unresolved)
    if plot:
        reasons.update(reason for axis in plot.axes for reason in axis.unresolved)
        if all(axis.resolved for axis in plot.axes):
            calibrations = {}
            for axis in plot.axes:
                solution = axis.solutions[0]
                ticks = sorted(solution.ticks)
                # Residual is measured in fitted scientific space; convert to pixels.
                span = abs(solution.slope) * abs(ticks[-1][0] - ticks[0][0])
                error_px = solution.residual * span / abs(solution.slope)
                calibrations[axis.axis] = calibration_from_tick_pairs(
                    scale=solution.scale, unit=solution.unit,
                    ticks=(ticks[0], ticks[-1]), uncertainty_px=max(.5, error_px))
            axes = FigurePanelAxisCalibration(**calibrations)
        paths = {p.candidate_id: p for p in detection.paths}
        for binding in intent.bindings:
            path = paths[binding.candidate_id]
            # Semantic labels belong to the Agent and independent audit. Optional
            # explicit OCR anchors were already checked against this exact frame.
            reasons.update(r for r in path.unresolved if r not in {"identity_unbound", "axes_unresolved"})
            if axes and path.pixels:
                selected_paths.append((binding, path))
    if not selected_paths:
        reasons.add("no_trustworthy_measurement")
    selected_paths.sort(key=lambda item: item[1].candidate_id)
    shape = "measured" if selected_paths else "unresolved_image" if image else "unrecovered"
    source = {"source_kind": "unrecovered", "source_sha256": detected.source_sha256}
    if image:
        source = {
            "source_kind": "embedded" if image.kind == "embedded_image" else image.kind,
            "source_sha256": detected.source_sha256, "image_sha256": image.image_sha256,
            "width": image.width, "height": image.height, "transform": image.transform,
            "coordinate_space": image.coordinate_space, "recovery_tool": image.tool,
            "recovery_tool_version": image.tool_version,
        }
        if image.page is not None:
            source["page"] = image.page
        if image.pdf_object is not None:
            source["pdf_object"] = image.pdf_object
        if image.kind == "page_render":
            source.update(rotation=image.rotation, requested_dpi=image.requested_dpi,
                          media_box=image.media_box, crop_box=image.crop_box)
    request = FigureMeasurementRequest.model_validate_json(canonical_json({
        "schema_version": "scidiscovery.curve-figure-digitization-request.v3",
        "result_shape": shape, "request_status": "ready" if selected_paths else "unresolved",
        "source": source, "detector_receipt": detected.receipt, "detector_version": detected.detector_version,
        "figure": intent.figure, "panel": intent.panel if image else None, "plot_candidate_id": intent.plot_candidate_id,
        "plot_bbox": plot.bbox if plot else None,
        "axis_calibration": axes.model_dump(mode="json") if axes else None,
        "series": [b.model_dump(mode="json") for b, _ in selected_paths],
        "unresolved_reasons": sorted(reasons),
        "rejected_candidates": [r.model_dump(mode="json") for r in intent.rejected_candidates],
    }), strict=True)
    request_raw = canonical_json(request.model_dump(mode="json"))
    panel_key = "panel-" + (plot.candidate_id[:20] if plot else detected.receipt[:20])
    siblings = {} if image is None else {
        f"source_panels/{panel_key}.png": (image.content, "image/png"),
        f"audit_overlays/{panel_key}.png": (detection.overlay, "image/png"),
    }
    series_records = []
    if selected_paths:
        with Image.open(io.BytesIO(image.content)) as raw_image:
            pixels = raw_image.convert("RGB")
        owners = {}
        for _, path in selected_paths:
            for pixel in path.pixels:
                owners[pixel.pixel_id] = owners.get(pixel.pixel_id, 0) + 1
        for binding, path in selected_paths:
            series_key = "path-" + path.candidate_id[:20]
            data_item = f"curve_tables/{panel_key}--{series_key}.csv"
            ordered = sorted(path.pixels, key=lambda p: (_axis_value(axes.x, p.x), p.y))
            stream = io.StringIO(newline="")
            rows = []
            for pixel in ordered:
                shared = owners[pixel.pixel_id] > 1 or bool(pixel.shared_group)
                # Multiple selected series may use the same observed coordinate.
                # This does not resolve their exclusive branches or create another
                # independent physical sample (report statistics deduplicate pixels).
                shared_observation = owners[pixel.pixel_id] > 1
                ambiguous = "path_junction_ambiguous" in path.unresolved and not shared_observation
                rows.append({
                    "panel_key": panel_key, "series_key": series_key,
                    "point_index": abs(pixel.x - ordered[0].x),
                    "pixel_id": pixel.pixel_id, "path_candidate_id": path.candidate_id,
                    "pixel_x_raw": pixel.x, "pixel_y_raw": pixel.y,
                    "pixel_x_subpixel": pixel.x, "pixel_y_subpixel": pixel.y,
                    "x_value": _axis_value(axes.x, pixel.x), "y_value": _axis_value(axes.y, pixel.y),
                    "uncertainty_px": .5,
                    "x_uncertainty": _axis_uncertainty(axes.x, pixel.x, .5),
                    "y_uncertainty": _axis_uncertainty(axes.y, pixel.y, .5),
                    "observed": 1, "quantitative_measurement_claim_eligible": int(not ambiguous),
                    "eligibility_reason": "ambiguous_path" if ambiguous else "",
                    "coordinate_ownership": "shared" if shared else "exclusive",
                    "shared_group": pixel.pixel_id if shared else "",
                })
            writer = csv.DictWriter(stream, fieldnames=tuple(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
            siblings[data_item] = (stream.getvalue().encode(), "text/csv")
            xs = sorted({p.x for p in ordered})
            left, _, right, _ = plot.bbox
            gaps = [xs[0] - left, right - xs[-1], *(b-a-1 for a,b in zip(xs,xs[1:]))]
            color = pixels.getpixel((ordered[0].x, ordered[0].y))
            series_records.append({
                "series_key": series_key, "label": binding.semantic_identity, "primitive_kind": "line",
                "descriptor": {"color": "#%02x%02x%02x" % color, "color_tolerance": 0.0, "line_style": "solid"},
                "data_item": data_item,
                "binding": {"source": "annotation", "visible_label": binding.visible_label,
                            "status": "matched", "confidence": 1.0, "alternatives": []},
                "point_count": len(rows), "visible_fraction": len(xs) / (right-left+1),
                "max_gap_px": max(gaps), "uncertainty_px": .5,
                "tracking_diagnostics": sorted(set(path.unresolved) - {"identity_unbound", "axes_unresolved"}),
            })
    manifest = {
        "schema_version": "scidiscovery.figure-evidence-manifest.v2", "result_shape": shape,
        "detector_receipt": detected.receipt, "unresolved_reasons": sorted(reasons),
        "figure_key": "figure-" + detected.receipt[:20], "status": "unresolved" if reasons else "qualified",
        "source": source,
        "panels": [] if image is None else [{"panel_key": panel_key, "citation": intent.figure,
            "axis_calibration": axes.model_dump(mode="json") if axes else None,
            "series": series_records, "shared_support": []}],
        "metrics": {"panel_count": int(image is not None), "series_count": len(series_records),
            "qualified_series_count": len(series_records), "total_point_count": sum(s["point_count"] for s in series_records),
            "minimum_visible_fraction": min((s["visible_fraction"] for s in series_records), default=0.0)},
        "ambiguities": [],
        "provenance": {"spec_sha256": _sha256(request_raw), "output_artifacts": [
            {"collection": name.split("/")[0], "data_item": name, "sha256": _sha256(raw),
             "bytes": len(raw), "media_type": media} for name,(raw,media) in sorted(siblings.items())]},
    }
    manifest_raw = canonical_json(validate_figure_evidence_manifest(manifest))
    report = build_figure_evidence_validation_report(manifest_data_item="figure_manifest/evidence.json",
        manifest_content=manifest_raw, sibling_files=siblings)
    FigureEvidenceValidationReport.model_validate_json(canonical_json(report), strict=True)
    return {"figure_request/evidence.json": (request_raw, "application/json"),
        "figure_manifest/evidence.json": (manifest_raw, "application/json"),
        "validation_reports/validation_report.json": (canonical_json(report), "application/json"), **siblings}


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
                required = set(range(left, right)) & donor.keys()
                for covered_key in support.covered_series:
                    covered_direct = direct_by_x[covered_key]
                    covered_result = by_x[covered_key]
                    endpoint_distance = max((
                        abs(
                            covered_direct[endpoint].pixel_y_subpixel
                            - donor[endpoint].pixel_y_subpixel
                        )
                        for endpoint in (left - 1, right)
                        if endpoint in covered_direct and endpoint in donor
                    ), default=0.0)
                    if endpoint_distance > support.max_endpoint_distance_px:
                        continue
                    domain = definitions[covered_key].pixel_range or (
                        request.plot_bbox[0],
                        request.plot_bbox[2],
                    )
                    for pixel_x in sorted(required - covered_direct.keys()):
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
                        donor_result[pixel_x] = mark_shared(
                            donor[pixel_x],
                            group=support.group_key,
                            source_series=support.visible_series,
                            support_kind="direct_pixel",
                        )
            continue

        members = support.member_series
        for left, right in support.pixel_ranges:
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
                    continue
                visible_points = tuple(
                    direct_by_x[member][pixel_x] for member in available
                )
                visible_y = tuple(point.pixel_y_subpixel for point in visible_points)
                if max(visible_y) - min(visible_y) > support.max_member_distance_px:
                    continue
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
                            shared_eligible=True,
                        ),
                        point_index=pixel_x - domain[0],
                        identity_ambiguous=(
                            source_point.identity_ambiguous
                            or (
                                pixel_x in direct_by_x[member]
                                and direct_by_x[member][pixel_x].identity_ambiguous
                            )
                        ),
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
        ) or (
            series.eligibility.below_detection_limit_value is not None
            and _axis_value(axes.y, point.pixel_y_subpixel)
            < series.eligibility.below_detection_limit_value
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
            and not point.identity_ambiguous
        )
        reason = (
            "below_detection_limit"
            if below_limit
            else region_reason
            if region_reason
            else "ineligible_range"
            if plain_ineligible
            else "ambiguous_path"
            if point.identity_ambiguous
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
        domain = series.pixel_range or (plot[0], plot[2])
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
                or not series.eligibility.default_eligible
                or _inside(x, series.eligibility.ineligible_pixel_ranges)
                or _inside(x, series.eligibility.below_detection_limit_pixel_ranges)
                or (series.eligibility.below_detection_limit_value is not None
                    and _axis_value(axes.y, point.pixel_y_subpixel)
                    < series.eligibility.below_detection_limit_value)
                or any(region.pixel_range[0] <= x < region.pixel_range[1]
                       for region in series.eligibility.ineligible_pixel_regions)
                or (point.support_kind == "shared_occlusion" and not point.shared_eligible)
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
            if finding.code == "binding_pixels_missing"
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
                "tracking_diagnostics": [
                    finding.message for finding in local_findings
                    if finding.code != "binding_pixels_missing"
                ] + ([series.eligibility.detection_limit_note]
                     if series.eligibility.detection_limit_note else []),
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
