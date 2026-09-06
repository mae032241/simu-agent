"""Typed request and exact-source contract for continuous-line digitization."""

from __future__ import annotations

import hashlib
import math
import json
import subprocess
from dataclasses import asdict
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .figure_evidence import (
    FigureAxisCalibration,
    FigurePanelAxisCalibration,
    FigureSharedSupport,
    MAX_FORMAL_RGB_DISTANCE,
    AutomaticFigureSource, FigureResultShape, UnrecoveredFigureSource,
)
from .figure_source import RecoveredFigureImage, inspect_figure_source_bytes
from .figure_source import AUTOMATIC_SOURCE_POLICY
from .figure_detection import (DETECTOR_VERSION, POLICY, SourceDetection, detect_source,
    MAX_TOKENS, MAX_AXIS_COMBINATIONS, MAX_LINE_SEGMENTS)
from PIL import __version__ as PILLOW_VERSION
from .figure_dependencies import RUNTIME_CONTRACT, command_path, verify_ocr


# The installed dependency record is serialized through the existing resource edge.
DETECTOR_CONTRACT = json.dumps({
    "detector_version": DETECTOR_VERSION, "policy": POLICY,
    "source_policy": AUTOMATIC_SOURCE_POLICY,
    "limits": {"ocr_tokens": MAX_TOKENS, "axis_combinations": MAX_AXIS_COMBINATIONS,
               "line_segments": MAX_LINE_SEGMENTS},
    **RUNTIME_CONTRACT,
}, sort_keys=True, separators=(",", ":")).encode()


def replay_detection(content: bytes) -> SourceDetection:
    """Verify the declared runtime boundary before replaying raw-source detection."""
    contract = json.loads(DETECTOR_CONTRACT)
    if contract["pillow_version"] is not None and PILLOW_VERSION != contract["pillow_version"]:
        raise RuntimeError("Pillow version differs from detector contract")
    if content.startswith(b"%PDF-") and contract["poppler_version"] is not None:
        for command in ("pdfinfo", "pdfimages", "pdftoppm"):
            result = subprocess.run([command_path(command), "-v"], capture_output=True, check=True, timeout=15)
            first_line = (result.stdout + result.stderr).decode().splitlines()[0].split()
            if len(first_line) < 3 or first_line[2] != contract["poppler_version"]:
                raise RuntimeError("Poppler version differs from detector contract")
    if contract["ocr"]["supply_status"] == "verified":
        verify_ocr(contract)
    return detect_source(content)


def identity_anchor_id(source_sha256: str, image_sha256: str, token: object) -> str:
    return hashlib.sha256(json.dumps((source_sha256, image_sha256, asdict(token)),
        sort_keys=True, separators=(",", ":")).encode()).hexdigest()


FigureKey = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$"),
]
ShortText = Annotated[str, Field(min_length=1, max_length=4096)]
PixelRange = tuple[int, int]
PixelBox = tuple[int, int, int, int]
PixelSeed = tuple[float, float]
PANEL_SELECTION_DESCRIPTION = (
    "Set panel to null for the whole figure or when no panel label is visible; "
    "otherwise copy the exact visible panel label."
)


class _DigitizationModel(BaseModel):
    model_config = ConfigDict(
        allow_inf_nan=False,
        extra="forbid",
        frozen=True,
        strict=True,
    )


class FigureCandidateBinding(_DigitizationModel):
    candidate_id: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    visible_label: ShortText
    semantic_identity: ShortText
    identity_anchor_id: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None = None


class FigureCandidateRejection(_DigitizationModel):
    candidate_id: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    reason: ShortText


class FigureExtractionIntent(_DigitizationModel):
    """Agent choices and semantic text only; no mechanically writable values."""

    model_config = ConfigDict(json_schema_extra={"anyOf": [
        {"properties": {"bindings": {"minItems": 1}, "plot_candidate_id": {"type": "string"}}},
        {"required": ["unresolved_reasons"], "properties": {"bindings": {"maxItems": 0}, "unresolved_reasons": {"minItems": 1}}},
        {"required": ["rejected_candidates"], "properties": {"bindings": {"maxItems": 0}, "rejected_candidates": {"minItems": 1}}},
    ]})

    schema_version: Literal["scidiscovery.figure-extraction-intent.v2"]
    source_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    detector_receipt: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    figure: ShortText
    panel: Annotated[ShortText | None, Field(description=PANEL_SELECTION_DESCRIPTION)]
    plot_candidate_id: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None
    bindings: Annotated[tuple[FigureCandidateBinding, ...], Field(max_length=32, json_schema_extra={"uniqueItems": True})]
    unresolved_reasons: Annotated[tuple[ShortText, ...], Field(max_length=32)] = ()
    rejected_candidates: Annotated[tuple[FigureCandidateRejection, ...], Field(max_length=64, json_schema_extra={"uniqueItems": True})] = ()

    @model_validator(mode="after")
    def _unique_labels(self) -> FigureExtractionIntent:
        selected = [item.candidate_id for item in self.bindings]
        rejected = [item.candidate_id for item in self.rejected_candidates]
        if len(set(selected + rejected)) != len(selected + rejected):
            raise ValueError("candidate selections and rejections must be disjoint and unique")
        if self.bindings and self.plot_candidate_id is None:
            raise ValueError("bindings require a selected plot candidate")
        if not self.bindings and not (self.unresolved_reasons or self.rejected_candidates):
            raise ValueError("empty selection requires bounded unresolved or rejected reasons")
        return self


def validate_intent_candidates(intent: FigureExtractionIntent, detected: SourceDetection):
    if intent.source_sha256 != detected.source_sha256:
        raise ValueError("figure source hash differs from intent")
    if intent.detector_receipt != detected.receipt:
        raise ValueError("detector receipt differs from replay")
    selected = None
    known = {p.candidate_id for d in detected.detections for p in (*d.plots, *d.paths)}
    for image, detection in zip(detected.images, detected.detections, strict=True):
        for plot in detection.plots:
            if plot.candidate_id == intent.plot_candidate_id:
                selected = image, detection, plot
    if intent.plot_candidate_id is not None and selected is None:
        raise ValueError("unknown plot candidate")
    if any(item.candidate_id not in known for item in intent.rejected_candidates):
        raise ValueError("unknown rejected candidate")
    if selected:
        image, detection, plot = selected
        paths = {p.candidate_id: p for p in detection.paths if p.plot_id == plot.candidate_id}
        anchors = {identity_anchor_id(detected.source_sha256, image.image_sha256, t): t for t in detection.tokens}
        for binding in intent.bindings:
            if binding.candidate_id not in paths:
                raise ValueError("path candidate does not belong to selected plot/source")
            if binding.identity_anchor_id is not None:
                token = anchors.get(binding.identity_anchor_id)
                if token is None or token.text != binding.visible_label:
                    raise ValueError("visible identity anchor differs from selected source")
    return selected


class FigureMeasurementRequest(_DigitizationModel):
    """Deterministic measurement record; never a materialize input."""
    schema_version: Literal["scidiscovery.curve-figure-digitization-request.v3"]
    result_shape: FigureResultShape
    request_status: Literal["ready", "unresolved"]
    source: AutomaticFigureSource
    detector_receipt: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    detector_version: ShortText
    figure: ShortText
    panel: ShortText | None
    plot_candidate_id: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None
    plot_bbox: PixelBox | None
    axis_calibration: FigurePanelAxisCalibration | None
    series: Annotated[tuple[FigureCandidateBinding, ...], Field(max_length=32)]
    unresolved_reasons: Annotated[tuple[ShortText, ...], Field(max_length=256)]
    rejected_candidates: Annotated[tuple[FigureCandidateRejection, ...], Field(max_length=64)]

    @model_validator(mode="after")
    def _shape(self):
        if self.result_shape == "measured":
            if self.request_status != "ready" or not self.series or self.axis_calibration is None or self.plot_bbox is None:
                raise ValueError("measurement requires axes, plot and selected series")
        elif self.request_status != "unresolved" or self.series or not self.unresolved_reasons:
            raise ValueError("unresolved measurement requires reasons and no measured series")
        if self.result_shape == "unrecovered":
            if not isinstance(self.source, UnrecoveredFigureSource) or self.panel is not None or self.plot_bbox is not None or self.axis_calibration is not None or self.plot_candidate_id is not None:
                raise ValueError("unrecovered request must not invent image geometry")
        elif isinstance(self.source, UnrecoveredFigureSource):
            raise ValueError("recovered request requires real source representation")
        return self


def calibration_from_tick_pairs(
    *, scale: str, unit: str, ticks: tuple[tuple[float, float], tuple[float, float]],
    uncertainty_px: float,
) -> FigureAxisCalibration:
    """Normalize measured (pixel, value) pairs without breaking their pairing."""
    low, high = sorted(ticks, key=lambda tick: tick[1])
    return FigureAxisCalibration(
        scale=scale, unit=unit, pixel_min=low[0], value_min=low[1],
        pixel_max=high[0], value_max=high[1], reprojection_error_px=uncertainty_px,
    )


class FigureLineTracking(_DigitizationModel):
    max_vertical_step_px: Annotated[float, Field(gt=0.0, le=1000.0)] = 12.0
    max_gap_px: Annotated[int, Field(ge=0, le=10000)] = 8
    max_gap_vertical_displacement_px: Annotated[
        float, Field(ge=0.0, le=10000.0)
    ] = 32.0
    max_guide_distance_px: Annotated[float, Field(gt=0.0, le=10000.0)] = 24.0
    ambiguity_margin_px: Annotated[float, Field(ge=0.0, le=1000.0)] = 0.75
    guide_weight: Annotated[float, Field(ge=0.0, le=1.0)] = 0.7
    min_visible_fraction: Annotated[float, Field(gt=0.0, le=1.0)] = 0.2
    max_ambiguous_fraction: Annotated[float, Field(ge=0.0, le=1.0)] = 0.1
    skip_penalty: Annotated[float, Field(ge=0.0, le=10000.0)] = 16.0
    min_points: Annotated[int, Field(ge=2, le=100000)] = 3
    seed_radius_px: Annotated[int, Field(ge=0, le=100)] = 4
    plot_border_exclusion_px: Annotated[int, Field(ge=0, le=100)] = 4
    overdraw_candidate_endpoint_distance_px: Annotated[
        float,
        Field(
            ge=0.0,
            le=1000.0,
            description=(
                "Deprecated request-v2 compatibility field; materialization ignores it."
            ),
        ),
    ] = 8.0


class FigureIneligibleRegion(_DigitizationModel):
    pixel_range: PixelRange
    reason: FigureKey


class FigureEligibility(_DigitizationModel):
    default_eligible: bool = False
    below_detection_limit_value: Annotated[float, Field(gt=0.0)] | None = None
    detection_limit_note: ShortText | None = None
    ineligible_pixel_ranges: Annotated[
        tuple[PixelRange, ...], Field(max_length=128)
    ] = ()
    ineligible_pixel_regions: Annotated[
        tuple[FigureIneligibleRegion, ...], Field(max_length=128)
    ] = ()
    below_detection_limit_pixel_ranges: Annotated[
        tuple[PixelRange, ...], Field(max_length=128)
    ] = ()


class FigureDigitizationSeries(_DigitizationModel):
    series_key: FigureKey
    label: ShortText
    primitive_kind: Literal["line"] = "line"
    color: Annotated[str, Field(pattern=r"^#[0-9a-f]{6}$")]
    color_tolerance: Annotated[
        float, Field(ge=0.0, le=MAX_FORMAL_RGB_DISTANCE)
    ] = 24.0
    line_style: Literal["solid"] = "solid"
    binding_source: Literal["legend", "annotation", "caption"]
    visible_label: ShortText
    binding_bbox: PixelBox
    min_color_pixels: Annotated[int, Field(ge=1, le=10_000_000)] = 1
    seeds: Annotated[tuple[PixelSeed, ...], Field(min_length=1, max_length=128)]
    tracking: FigureLineTracking = FigureLineTracking()
    pixel_range: PixelRange | None = None
    exclusion_regions: Annotated[
        tuple[PixelBox, ...], Field(max_length=128)
    ] = ()
    declared_gap_ranges: Annotated[
        tuple[PixelRange, ...], Field(max_length=128)
    ] = ()
    eligibility: FigureEligibility = FigureEligibility()

    @model_validator(mode="after")
    def _anchors_are_ordered(self) -> FigureDigitizationSeries:
        if any(
            right[0] <= left[0] for left, right in zip(self.seeds, self.seeds[1:])
        ):
            raise ValueError("series seed x coordinates must be strictly increasing")
        return self


class PdfFigureSource(_DigitizationModel):
    source_kind: Literal["pdf_embedded_image"]
    media_type: Literal["application/pdf"]
    source_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    page: Annotated[int, Field(ge=1, le=100_000)]
    document_image_index: Annotated[int, Field(ge=0, le=1_000_000)]
    page_image_index: Annotated[int, Field(ge=0, le=10_000)]
    pdf_object_id: Annotated[int, Field(ge=1, le=2**31 - 1)]
    pdf_object_generation: Annotated[int, Field(ge=0, le=65_535)] = 0
    recovered_image_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    width: Annotated[int, Field(ge=1, le=1_000_000)]
    height: Annotated[int, Field(ge=1, le=1_000_000)]
    recovery_tool: Literal["pdfimages+Pillow"]
    recovery_tool_version: Annotated[str, Field(min_length=1, max_length=256)]


class RasterFigureSource(_DigitizationModel):
    source_kind: Literal["raster_image"]
    media_type: Literal["image/png", "image/jpeg", "image/webp"]
    source_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    recovered_image_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    width: Annotated[int, Field(ge=1, le=1_000_000)]
    height: Annotated[int, Field(ge=1, le=1_000_000)]
    recovery_tool: Literal["Pillow"]
    recovery_tool_version: Annotated[str, Field(min_length=1, max_length=256)]


FigureSource = Annotated[
    PdfFigureSource | RasterFigureSource,
    Field(discriminator="source_kind"),
]


def _valid_range(value: PixelRange, *, left: int, right: int) -> bool:
    return left <= value[0] < value[1] <= right


def _valid_box(value: PixelBox, *, width: int, height: int) -> bool:
    left, top, right, bottom = value
    return 0 <= left < right <= width and 0 <= top < bottom <= height


class FigureDigitizationRequest(_DigitizationModel):
    schema_version: Literal["scidiscovery.curve-figure-digitization-request.v2"]
    request_status: Literal["ready", "unresolved"] = "ready"
    unresolved_reasons: Annotated[tuple[ShortText, ...], Field(max_length=32)] = ()
    figure_key: FigureKey
    panel_key: FigureKey
    figure: ShortText
    citation: ShortText
    source: FigureSource
    plot_bbox: PixelBox | None = None
    axis_calibration: FigurePanelAxisCalibration | None = None
    exclusion_regions: Annotated[
        tuple[PixelBox, ...], Field(max_length=128)
    ] = ()
    series: Annotated[
        tuple[FigureDigitizationSeries, ...], Field(max_length=32)
    ] = ()
    shared_support: Annotated[
        tuple[FigureSharedSupport, ...], Field(max_length=128)
    ] = ()

    @model_validator(mode="after")
    def _request_is_bounded_and_self_consistent(self) -> FigureDigitizationRequest:
        if self.request_status == "unresolved":
            if not self.unresolved_reasons:
                raise ValueError("unresolved figure request requires explicit reasons")
            if (
                self.plot_bbox is not None
                or self.axis_calibration is not None
                or self.exclusion_regions
                or self.series
                or self.shared_support
            ):
                raise ValueError(
                    "unresolved figure request must not contain partial digitization fields"
                )
            return self
        if self.unresolved_reasons:
            raise ValueError("ready figure request cannot declare unresolved reasons")
        if self.plot_bbox is None or self.axis_calibration is None or not self.series:
            raise ValueError(
                "ready figure request requires plot_bbox, axis_calibration, and series"
            )
        if not _valid_box(
            self.plot_bbox, width=self.source.width, height=self.source.height
        ):
            raise ValueError("plot_bbox exceeds the recovered image")
        plot_left, plot_top, plot_right, plot_bottom = self.plot_bbox
        axes = self.axis_calibration
        if not (
            plot_left <= min(axes.x.pixel_min, axes.x.pixel_max)
            and max(axes.x.pixel_min, axes.x.pixel_max) < plot_right
            and plot_top <= min(axes.y.pixel_min, axes.y.pixel_max)
            and max(axes.y.pixel_min, axes.y.pixel_max) < plot_bottom
        ):
            raise ValueError("axis calibration exceeds plot_bbox")
        if any(
            not _valid_box(box, width=self.source.width, height=self.source.height)
            for box in self.exclusion_regions
        ):
            raise ValueError("figure exclusion region exceeds the recovered image")
        keys = tuple(item.series_key for item in self.series)
        if len(keys) != len(set(keys)):
            raise ValueError("digitization series keys must be unique")
        for item in self.series:
            if not _valid_box(
                item.binding_bbox,
                width=self.source.width,
                height=self.source.height,
            ):
                raise ValueError(f"series {item.series_key} binding_bbox is out of bounds")
            domain = item.pixel_range or (plot_left, plot_right)
            if not _valid_range(domain, left=plot_left, right=plot_right):
                raise ValueError(f"series {item.series_key} pixel_range is outside plot_bbox")
            boxes = (*self.exclusion_regions, *item.exclusion_regions)
            if any(
                not _valid_box(box, width=self.source.width, height=self.source.height)
                for box in boxes
            ):
                raise ValueError(f"series {item.series_key} exclusion is out of bounds")
            if any(
                not (
                    domain[0] <= seed[0] < domain[1]
                    and plot_top <= seed[1] < plot_bottom
                )
                for seed in item.seeds
            ):
                raise ValueError(f"series {item.series_key} seed is outside its trace domain")
            ranges = (
                *item.declared_gap_ranges,
                *item.eligibility.ineligible_pixel_ranges,
                *item.eligibility.below_detection_limit_pixel_ranges,
                *(
                    region.pixel_range
                    for region in item.eligibility.ineligible_pixel_regions
                ),
            )
            if any(
                not _valid_range(value, left=domain[0], right=domain[1])
                for value in ranges
            ):
                raise ValueError(f"series {item.series_key} range is outside its trace domain")
        known = set(keys)
        claims: dict[str, list[PixelRange]] = {}
        for support in self.shared_support:
            members = (
                (support.visible_series, *support.covered_series)
                if support.mode == "overdraw"
                else support.member_series
            )
            if not set(members).issubset(known):
                raise ValueError("shared support references an unknown series")
            for interval in support.pixel_ranges:
                for member in members:
                    definition = next(item for item in self.series if item.series_key == member)
                    domain = definition.pixel_range or (plot_left, plot_right)
                    if not _valid_range(interval, left=domain[0], right=domain[1]):
                        raise ValueError("shared support is outside a member trace domain")
                    claims.setdefault(member, []).append(interval)
        for intervals in claims.values():
            ordered = sorted(intervals)
            if any(
                current[0] < previous[1]
                for previous, current in zip(ordered, ordered[1:])
            ):
                raise ValueError("shared-support ranges overlap")
        return self

    def require_ready(self) -> tuple[
        PixelBox, FigurePanelAxisCalibration, tuple[FigureDigitizationSeries, ...]
    ]:
        if (
            self.request_status != "ready"
            or self.plot_bbox is None
            or self.axis_calibration is None
            or not self.series
        ):
            raise ValueError("unresolved figure request cannot be materialized")
        return self.plot_bbox, self.axis_calibration, self.series


def axis_value(axis: object, pixel: float) -> float:
    fraction = (pixel - axis.pixel_min) / (axis.pixel_max - axis.pixel_min)
    if axis.scale == "linear":
        return axis.value_min + fraction * (axis.value_max - axis.value_min)
    low = math.log10(axis.value_min)
    high = math.log10(axis.value_max)
    return 10 ** (low + fraction * (high - low))


def axis_uncertainty(axis: object, pixel: float, uncertainty_px: float) -> float:
    total = uncertainty_px + axis.reprojection_error_px
    center = axis_value(axis, pixel)
    return max(
        abs(center - axis_value(axis, pixel - total)),
        abs(axis_value(axis, pixel + total) - center),
    )


def recover_requested_image(
    source_content: bytes, request: FigureDigitizationRequest
) -> RecoveredFigureImage:
    source = request.source
    if hashlib.sha256(source_content).hexdigest() != source.source_sha256:
        raise ValueError("figure source hash differs from the typed request")
    page = source.page if isinstance(source, PdfFigureSource) else None
    candidates = inspect_figure_source_bytes(
        source_content,
        media_type=source.media_type,
        page=page,
    )
    if isinstance(source, PdfFigureSource):
        selected = tuple(
            item
            for item in candidates
            if (
                item.document_image_index == source.document_image_index
                and item.page_image_index == source.page_image_index
                and item.pdf_object_id == source.pdf_object_id
                and item.pdf_object_generation == source.pdf_object_generation
            )
        )
        if len(selected) != 1:
            raise ValueError("typed request does not select one exact PDF image object")
        image = selected[0]
    else:
        if len(candidates) != 1:
            raise ValueError("raster source recovery is not singular")
        image = candidates[0]
    if (
        image.image_sha256 != source.recovered_image_sha256
        or image.width != source.width
        or image.height != source.height
        or image.recovery_tool != source.recovery_tool
        or image.recovery_tool_version != source.recovery_tool_version
    ):
        raise ValueError("recovered figure image differs from the typed request")
    return image


__all__ = [
    "FigureDigitizationRequest",
    "FigureDigitizationSeries",
    "FigureEligibility",
    "FigureLineTracking",
    "PdfFigureSource",
    "PixelRange",
    "RasterFigureSource",
    "axis_uncertainty",
    "axis_value",
    "recover_requested_image",
]
