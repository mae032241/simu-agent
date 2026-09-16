"""Operation-scoped read-only inspection of exact figure source inputs."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from scidiscovery.artifact_agent.operation_tool_context import OperationToolContext
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.operations.tooling import WorkerToolDefinition

from .figure_digitization import build_digitized_figure_bundle
from .figure_digitization_contract import FigureDigitizationRequest, materialize_figure_request
from .figure_source import inspect_figure_source


class FigureSourceInspectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(default="paper_source", min_length=1, max_length=256)
    source_page: int | None = Field(
        default=None, ge=1,
        description="One-based PDF page index located from the exact source text.",
    )


class FigureDigitizationPreviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(default="paper_source", min_length=1, max_length=256)
    request: FigureDigitizationRequest


def _publish_read_only(path: Path, content: bytes) -> None:
    if path.exists():
        if path.is_symlink() or path.stat().st_mode & 0o222 or path.read_bytes() != content:
            raise ValueError("existing figure preview differs")
        return
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(temporary, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.fchmod(descriptor, 0o400)
    finally:
        os.close(descriptor)
    os.replace(temporary, path)


def _inspect(
    request: BaseModel, context: OperationToolContext
) -> dict[str, object]:
    if not isinstance(request, FigureSourceInspectionInput):
        raise ValueError("figure source inspection request has the wrong type")
    media_type = context.input_media_type(request.name)
    images = inspect_figure_source(
        context.input_path(request.name),
        media_type=media_type,
        page=request.source_page,
        timeout_seconds=context.remaining_seconds,
    )
    directory = context.workspace / ".operation-tools" / "figures"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if directory.resolve() != context.workspace.resolve() / ".operation-tools" / "figures":
        raise ValueError("figure previews must remain below the exact run-local directory")
    results = []
    for image in images:
        destination = directory / f"preview_{image.image_sha256[:20]}.png"
        _publish_read_only(destination, image.content)
        results.append(image.public_metadata(local_path=str(destination)))
    context.record_activity("deterministic_analysis_completed")
    result = {
        "name": request.name,
        "source_page": request.source_page,
        "source_media_type": media_type,
        "source_sha256": context.input_ref(request.name).sha256,
        "images": results,
    }
    details = directory / f"inspection_{result['source_sha256']}_{request.source_page}.json"
    _publish_read_only(details, canonical_json(result))
    return {**result, "images": results[:8], "omitted_images": max(0, len(results)-8),
            "details_path": str(details)}


FIGURE_SOURCE_INSPECTION_TOOL = WorkerToolDefinition(
    name="worker_curve_figure_inspect_source",
    description=(
        "Recover original embedded images from one exact Agent-located PDF page, or "
        "canonicalize one exact raster source, and return only read-only source previews "
        "and deterministic source metadata. OCR and plot detection are not performed."
    ),
    input_model=FigureSourceInspectionInput,
    capability="input.inspect_curve_figure",
    contextual_handler=_inspect,
)


def _preview(
    request: BaseModel, context: OperationToolContext
) -> dict[str, object]:
    if not isinstance(request, FigureDigitizationPreviewInput):
        raise ValueError("figure preview request has the wrong type")
    request_raw = canonical_json(materialize_figure_request(
        request.request.model_dump(mode="json"), context.input_path(request.name).read_bytes()))
    files, report = build_digitized_figure_bundle(
        context.input_path(request.name).read_bytes(), request_raw
    )
    request_sha256 = hashlib.sha256(request_raw).hexdigest()
    directory = (
        context.workspace
        / ".operation-tools"
        / "figure-previews"
        / request_sha256[:20]
    )
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    images = []
    for data_item, (content, media_type) in sorted(files.items()):
        if not data_item.startswith("audit_overlays/") or media_type != "image/png":
            continue
        destination = directory / Path(data_item).name
        _publish_read_only(destination, content)
        images.append({"data_item": data_item, "local_path": str(destination)})
    context.record_activity("deterministic_analysis_completed")
    details = {"materialized_request": json.loads(request_raw), "validation_report": report, "images": images}
    details_path = directory / "details.json"
    _publish_read_only(details_path, canonical_json(details))
    return {"source_sha256": context.input_ref(request.name).sha256,
        "request_sha256": request_sha256, "details_path": str(details_path),
        "integrity_status": report["integrity_status"], "source_status": report["source_status"],
        "validated_artifact_count": report["validated_artifact_count"],
        "metrics": {key: report["metrics"][key] for key in ("curve_table_count", "total_curve_rows",
            "observed_curve_rows", "eligible_curve_rows", "eligibility_flagged_table_count")},
        "images": images[:8], "omitted_images": max(0, len(images)-8)}


FIGURE_DIGITIZATION_PREVIEW_TOOL = WorkerToolDefinition(
    name="worker_curve_figure_preview",
    description=(
        "Run the same deterministic curve digitizer used by materialization for one "
        "draft request. Return read-only source-overlay and numeric-redraw paths for "
        "the current Agent to inspect before submitting the request."
    ),
    input_model=FigureDigitizationPreviewInput,
    capability="input.preview_curve_figure",
    contextual_handler=_preview,
)


__all__ = [
    "FIGURE_DIGITIZATION_PREVIEW_TOOL",
    "FIGURE_SOURCE_INSPECTION_TOOL",
    "FigureDigitizationPreviewInput",
    "FigureSourceInspectionInput",
]
