"""Frozen-source geometry for the measured Fig.4 lines, outside Agent output."""

from __future__ import annotations

import hashlib
import json
from importlib.resources import files

from curve_score.figure_digitization_contract import (
    FigureDigitizationRequest,
    FigureExtractionIntent,
    calibration_from_tick_pairs,
)
from curve_score.figure_source import inspect_figure_source_bytes
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.operations.spec import (
    CallableComponent, ComponentRef, ComponentSpec, ExecutorRef, InputPortSpec,
    LimitsSpec, OperationDescription, OperationSpec, OutputPortSpec,
)


# This resource participates in the compiled Operation digest. It is geometry,
# never qualified evidence: source panels and generated overlays require review.
GEOMETRY = files("ingaas_fig4").joinpath("figure_geometry.json").read_text("utf-8")


def compile_figure_request(values):
    if set(values) != {"paper_source", "figure_intent"} or any(
        len(items) != 1 for items in values.values()
    ):
        raise ValueError("Fig.4 compilation requires one source and one semantic intent")
    source = values["paper_source"][0]
    intent = FigureExtractionIntent.model_validate_json(values["figure_intent"][0], strict=True)
    if intent.unresolved_reasons:
        raise ValueError("unresolved scientific selection cannot be compiled")
    geometry = json.loads(GEOMETRY)
    if hashlib.sha256(source).hexdigest() != intent.source_sha256 or intent.source_sha256 != geometry["source_sha256"]:
        raise ValueError("Fig.4 geometry is not bound to this frozen source")
    if intent.figure != geometry["figure"] or intent.panel != geometry["panel"]:
        raise ValueError("Fig.4 compiler does not support this figure/panel selection")
    labels = {series["visible_label"] for series in geometry["series"]}
    if not set(intent.series_labels).issubset(labels):
        raise ValueError("Fig.4 compiler does not support these visible series labels")
    images = inspect_figure_source_bytes(source, media_type="application/pdf", page=geometry["pdf_page"])
    selected = tuple(image for image in images if image.pdf_object_id == geometry["pdf_object_id"])
    if len(selected) != 1 or selected[0].image_sha256 != geometry["recovered_image_sha256"]:
        raise ValueError("Fig.4 recovered image differs from its frozen geometry")
    image = selected[0]
    for series in geometry["series"]:
        series["eligibility"].update(
            below_detection_limit_value=geometry["detection_limit"]["value"],
            detection_limit_note=geometry["detection_limit"]["note"],
        )
    request = {
        "schema_version": "scidiscovery.curve-figure-digitization-request.v2",
        **{key: geometry[key] for key in ("figure_key", "panel_key", "figure", "citation", "plot_bbox", "exclusion_regions")},
        "axis_calibration": {
            key: calibration_from_tick_pairs(
                scale=axis["scale"], unit=axis["unit"],
                ticks=tuple(tuple(pair) for pair in axis["ticks"]),
                uncertainty_px=axis["uncertainty_px"],
            ).model_dump(mode="json")
            for key, axis in geometry["axis_ticks"].items()
        },
        "series": [series for series in geometry["series"] if series["visible_label"] in intent.series_labels],
        "shared_support": geometry["shared_support"],
        "source": {
            "source_kind": "pdf_embedded_image", "media_type": "application/pdf",
            "source_sha256": intent.source_sha256,
            "page": image.page, "document_image_index": image.document_image_index,
            "page_image_index": image.page_image_index, "pdf_object_id": image.pdf_object_id,
            "pdf_object_generation": image.pdf_object_generation,
            "recovered_image_sha256": image.image_sha256,
            "width": image.width, "height": image.height,
            "recovery_tool": image.recovery_tool, "recovery_tool_version": image.recovery_tool_version,
        },
    }
    validated = FigureDigitizationRequest.model_validate_json(canonical_json(request), strict=True)
    return {"figure_request": (canonical_json(validated.model_dump(mode="json")),)}


COMPILE = CallableComponent("transform", compile_figure_request)
COMPONENTS = (
    ComponentSpec("figure_geometry", "resource", "ingaas_fig4.figure_compilation:GEOMETRY"),
    ComponentSpec("compile_figure_request", "transform", "ingaas_fig4.figure_compilation:COMPILE",
                  resources=(ComponentRef("figure_geometry"),)),
)
OPERATION = OperationSpec(
    operation_id="ingaas.fig4.figure-request.compile.v1", version="1", catalog_scope="support",
    description=OperationDescription(
        purpose="Compile semantic selections into source-bound measured Fig.4 extraction geometry.",
        applies_when="The exact frozen Fig.4 paper and visible measured-series selections are available.",
        not_for="Other images, inferred geometry, curve generation or scientific qualification.",
    ),
    executor=ExecutorRef(kind="transform", component=ComponentRef("compile_figure_request")),
    inputs=(
        InputPortSpec(name="paper_source", description="Exact frozen paper PDF.", schema="opaque",
                      media_types=("application/pdf",), codec=ComponentRef("opaque_codec", plugin_id="general_science"),
                      schema_resource=ComponentRef("opaque_schema", plugin_id="general_science"),
                      max_item_bytes=32 * 1024 * 1024, usage="evidence_inventory", exposure="full"),
        InputPortSpec(name="figure_intent", description="Only scientific figure and visible-series selections.",
                      schema="scidiscovery.figure-extraction-intent.v1", media_types=("application/json",),
                      codec=ComponentRef("json_codec", plugin_id="general_science"),
                      schema_resource=ComponentRef("figure_intent_schema", plugin_id="curve_figure_evidence"),
                      max_item_bytes=64 * 1024, usage="evidence_inventory", exposure="full"),
    ),
    outputs=(OutputPortSpec(
        name="figure_request", description="Deterministic internal calibration and tracking request.",
        kind="figure_digitization_request", schema="scidiscovery.curve-figure-digitization-request.v2",
        media_types=("application/json",), codec=ComponentRef("json_codec", plugin_id="general_science"),
        schema_resource=ComponentRef("figure_request_schema", plugin_id="curve_figure_evidence"),
        max_item_bytes=1024 * 1024,
    ),),
    consequence="scientific", limits=LimitsSpec(timeout_seconds=60, max_input_bytes=33 * 1024 * 1024,
                                                 max_output_bytes=1024 * 1024, max_files=1),
)
