"""Compilation boundary for the Agent-owned figure request."""

import hashlib
import io
import json

import pytest
from PIL import Image
from pydantic import ValidationError

from curve_figure_evidence.figure_digitization_contract import (
    FigureAxisRequest,
    FigureDigitizationRequest,
)
from curve_figure_evidence.figure_science_operations import (
    FIGURE_REQUEST_CONTEXT,
    FIGURE_REQUEST_SCHEMA,
    REQUEST_PROMPT,
)
from curve_figure_evidence.figure_source import inspect_figure_source_bytes
from curve_figure_evidence.plugin import PLUGIN as FIGURE_PLUGIN
from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operation_contract import SemanticRuleViolation
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.tooling import operation_worker_tools


def _source_and_request() -> tuple[bytes, dict[str, object]]:
    image = Image.new("RGB", (12, 12), "white")
    for x in range(1, 10):
        image.putpixel((x, 10 - x), (255, 0, 0))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    source = stream.getvalue()
    recovered = inspect_figure_source_bytes(source, media_type="image/png")[0]
    request = {
        "schema_version": "scidiscovery.curve-figure-digitization-request.v2",
        "figure_key": "figure",
        "panel_key": "panel",
        "figure": "Fig. 1",
        "citation": "Fig. 1",
        "source": {
            "source_kind": "raster_image",
            "media_type": "image/png",
            "source_sha256": hashlib.sha256(source).hexdigest(),
            "recovered_image_sha256": recovered.image_sha256,
            "width": recovered.width,
            "height": recovered.height,
            "recovery_tool": recovered.recovery_tool,
            "recovery_tool_version": recovered.recovery_tool_version,
        },
        "plot_bbox": [1, 1, 10, 10],
        "axis_calibration": {
            "x": {"scale": "linear", "unit": "V", "ticks": [[9, 8], [1, 0]]},
            "y": {"scale": "log10", "unit": "A", "ticks": [[9, 1], [1, 100000000]]},
        },
        "series": [{
            "series_key": "red",
            "label": "Red curve",
            "color": "#ff0000",
            "line_style": "solid",
            "binding_source": "legend",
            "visible_label": "Red curve",
            "binding_bbox": [1, 1, 10, 10],
            "seeds": [[1, 9], [9, 1]],
        }],
    }
    return source, request


def test_public_schema_contains_only_agent_owned_description() -> None:
    schema = json.loads(FIGURE_REQUEST_SCHEMA)
    assert set(schema["properties"]) == {
        "schema_version",
        "request_status",
        "unresolved_reasons",
        "figure_key",
        "panel_key",
        "figure",
        "citation",
        "source",
        "plot_bbox",
        "axis_calibration",
        "exclusion_regions",
        "series",
    }
    serialized = json.dumps(schema)
    for forbidden in (
        "min_points",
        "pixel_range",
        "shared_support",
        "max_gap_px",
        "min_visible_fraction",
        "color_tolerance",
        "min_color_pixels",
        "eligibility",
    ):
        assert forbidden not in serialized
    assert "[pixel_coordinate, tick_value]" in REQUEST_PROMPT


def test_request_context_replays_the_exact_source() -> None:
    source, request = _source_and_request()
    FIGURE_REQUEST_CONTEXT.implementation(request, {"paper_source": source}, {})
    with pytest.raises(SemanticRuleViolation, match="source hash differs"):
        FIGURE_REQUEST_CONTEXT.implementation(
            request, {"paper_source": b"different"}, {}
        )


@pytest.mark.parametrize(
    "ticks",
    [
        ((36, 100000000000000000000), (685, 1000000000000000)),
        ((685, 1000000000000000), (36, 100000000000000000000)),
    ],
)
def test_tick_normalization_preserves_integer_pixel_value_pairs(ticks) -> None:
    axis = FigureAxisRequest(
        scale="log10", unit="cm^-3", ticks=ticks, uncertainty_px=1
    ).normalized()
    assert (axis.pixel_min, axis.value_min) == (685.0, 1e15)
    assert (axis.pixel_max, axis.value_max) == (36.0, 1e20)


@pytest.mark.parametrize(
    "ticks",
    [((1, 1), (1, 2)), ((1, 0), (2, 2)), ((float("nan"), 1), (2, 2))],
)
def test_invalid_tick_pairs_are_rejected(ticks) -> None:
    with pytest.raises(ValidationError):
        FigureAxisRequest.model_validate(
            {"scale": "log10", "unit": "A", "ticks": ticks}, strict=True
        )


def test_compiled_request_operation_exposes_raw_inspection_and_preview() -> None:
    catalog = compile_catalog(
        (CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, FIGURE_PLUGIN)
    )
    operation = catalog.operation("science.figure.request.prepare.v1")
    assert operation.spec.outputs[0].schema_id == (
        "scidiscovery.curve-figure-digitization-request.v2"
    )
    assert {tool.name for tool in operation_worker_tools(operation)} >= {
        "worker_curve_figure_inspect_source",
        "worker_curve_figure_preview",
    }
    source, request = _source_and_request()
    FigureDigitizationRequest.model_validate_json(canonical_json(request), strict=True)
