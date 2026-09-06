"""Operation-scoped read-only inspection of exact figure source inputs."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from scidiscovery.artifact_agent.operation_tool_context import OperationToolContext
from scidiscovery.operations.tooling import WorkerToolDefinition

from .figure_digitization_contract import replay_detection, identity_anchor_id


class FigureSourceInspectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(default="paper_source", min_length=1, max_length=256)


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
    if media_type not in {"application/pdf", "image/png", "image/jpeg", "image/webp"}:
        raise ValueError("inspection requires a bound paper or raster source")
    detected = replay_detection(context.input_path(request.name).read_bytes())
    directory = context.workspace / ".operation-tools" / "figures"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if directory.resolve() != context.workspace.resolve() / ".operation-tools" / "figures":
        raise ValueError("figure previews must remain below the exact run-local directory")
    results = []
    for image, detection in zip(detected.images, detected.detections, strict=True):
        destination = directory / f"preview_{image.image_sha256[:20]}.png"
        _publish_read_only(destination, image.content)
        overlay = directory / f"overlay_{detection.receipt[:20]}.png"
        _publish_read_only(overlay, detection.overlay)
        results.append({
            "representation": image.kind, "page": image.page,
            "source_preview": str(destination), "candidate_overlay": str(overlay),
            "plots": [{"candidate_id": p.candidate_id, "overlay_label": f"P{i+1}",
                       "unresolved": sorted({r for axis in p.axes for r in axis.unresolved})}
                      for i, p in enumerate(detection.plots)],
            "paths": [{"candidate_id": p.candidate_id, "plot_candidate_id": p.plot_id,
                       "overlay_label": f"L{i+1}", "unresolved": p.unresolved}
                      for i, p in enumerate(detection.paths)],
            "visible_text": [{"text": t.text, "identity_anchor_id": identity_anchor_id(
                detected.source_sha256, image.image_sha256, t)} for t in detection.tokens],
            "unresolved": detection.unresolved,
        })
    context.record_activity("deterministic_analysis_completed")
    return {
        "name": request.name,
        "source_media_type": media_type,
        "source_sha256": detected.source_sha256,
        "detector_version": detected.detector_version,
        "detector_receipt": detected.receipt,
        "unresolved": detected.unresolved,
        "images": results,
    }


FIGURE_SOURCE_INSPECTION_TOOL = WorkerToolDefinition(
    name="worker_curve_figure_inspect_source",
    description=(
        "Automatically inspect one exact bound source and return read-only original "
        "and candidate-overlay paths, candidate IDs and visible text for selection. "
        "The Agent returns semantic selections, not pixel measurements."
    ),
    input_model=FigureSourceInspectionInput,
    capability="input.inspect_curve_figure",
    contextual_handler=_inspect,
)


__all__ = ["FIGURE_SOURCE_INSPECTION_TOOL", "FigureSourceInspectionInput"]
