"""Operation-scoped read-only inspection of exact figure source inputs."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from scidiscovery.artifact_agent.operation_tool_context import OperationToolContext
from scidiscovery.operations.tooling import WorkerToolDefinition

from .figure_source import inspect_figure_source


class FigureSourceInspectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(default="paper_source", min_length=1, max_length=256)
    page: int | None = Field(default=None, ge=1, le=100_000)


def _publish_read_only(path: Path, content: bytes) -> None:
    if path.exists():
        if path.is_symlink() or path.read_bytes() != content:
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
        page=request.page,
        timeout_seconds=context.remaining_seconds,
    )
    directory = context.workspace / ".operation-tools" / "figures"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    results = []
    for image in images:
        destination = directory / f"preview_{image.image_sha256[:20]}.png"
        _publish_read_only(destination, image.content)
        results.append(image.public_metadata(local_path=str(destination)))
    context.record_activity("deterministic_analysis_completed")
    return {
        "name": request.name,
        "source_media_type": media_type,
        "source_sha256": context.input_ref(request.name).sha256,
        "images": results,
    }


FIGURE_SOURCE_INSPECTION_TOOL = WorkerToolDefinition(
    name="worker_curve_figure_inspect_source",
    description=(
        "Recover bounded embedded images from one exact bound PDF page, or "
        "canonicalize one exact bound raster, and return read-only preview paths "
        "plus deterministic source metadata for scientific figure selection. "
        "The Agent returns semantic selections, not pixel measurements."
    ),
    input_model=FigureSourceInspectionInput,
    capability="input.inspect_curve_figure",
    contextual_handler=_inspect,
)


__all__ = ["FIGURE_SOURCE_INSPECTION_TOOL", "FigureSourceInspectionInput"]
