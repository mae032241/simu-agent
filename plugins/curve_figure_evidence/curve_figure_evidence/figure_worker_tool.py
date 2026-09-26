"""Operation-scoped inspection, digitization and explicit family publication."""

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
from .figure_digitization_contract import FigureDigitizationRequest, ScientificFigureRequest, materialize_figure_request
from .figure_source import inspect_figure_source
from .scientific_files import SOURCE_CONTROL, project_figure_file, restore_figure_file


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
    request: ScientificFigureRequest


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
        results.append({key:value for key,value in image.public_metadata(local_path=str(destination)).items() if key not in SOURCE_CONTROL})
    context.record_activity("deterministic_analysis_completed")
    result = {
        "name": request.name,
        "source_page": request.source_page,
        "source_media_type": media_type,
        "images": results,
    }
    details = directory / f"inspection_{request.source_page}.json"
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
    if context.source_descriptor(request.name).port_name != "paper_source":
        raise ValueError("figure tool requires the declared original paper source")
    source = context.read_input(request.name)
    request_raw = canonical_json(materialize_figure_request(request.request.model_dump(mode="json", exclude_none=True), source))
    files, report = build_digitized_figure_bundle(source, request_raw)
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
    details = {"request": json.loads(project_figure_file("figure_request/request.json", request_raw)[0]), "validation_report": json.loads(project_figure_file("validation_reports/validation_report.json", canonical_json(report))[0]), "images": images}
    details_path = directory / "details.json"
    _publish_read_only(details_path, canonical_json(details))
    result = {"details_path": str(details_path),
        "integrity_status": report["integrity_status"], "source_status": report["source_status"],
        "validated_artifact_count": report["validated_artifact_count"],
        "metrics": {key: report["metrics"][key] for key in ("curve_table_count", "total_curve_rows",
            "observed_curve_rows", "eligible_curve_rows", "eligibility_flagged_table_count")},
        "images": images[:8], "omitted_images": max(0, len(images)-8)}
    context.finish_attempt(result_status="figure_preview_" + request_sha256, response=result, successful=True)
    return result


FIGURE_DIGITIZATION_PREVIEW_TOOL = WorkerToolDefinition(
    name="worker_curve_figure_preview",
    description=(
        "Run the same deterministic curve digitizer used by materialization for one "
        "draft request. Return read-only source-overlay and numeric-redraw paths for "
        "the current Agent to inspect before explicitly saving the selected family."
    ),
    input_model=FigureDigitizationPreviewInput,
    capability="input.preview_curve_figure",
    contextual_handler=_preview,
    record_attempts=True,
)


__all__ = [
    "FIGURE_DIGITIZATION_PREVIEW_TOOL",
    "FIGURE_SOURCE_INSPECTION_TOOL",
    "FIGURE_SAVE_TOOL",
    "FIGURE_REUSE_TOOL",
    "FigureFamilyReuseInput",
    "FigureDigitizationPreviewInput",
    "FigureSourceInspectionInput",
]


def _save(request: BaseModel, context: OperationToolContext) -> dict[str, object]:
    """Explicitly select one complete family after preview, with retry-safe writes."""
    from .figure_family import (ALGORITHM, REQUEST_ITEM, SELECTION_ITEM,
        FigureFamilyMember, SelectedFigureFamily)
    if not isinstance(request, FigureDigitizationPreviewInput):
        raise ValueError("figure save request has the wrong type")
    if context.source_descriptor(request.name).port_name != "paper_source":
        raise ValueError("figure tool requires the declared original paper source")
    source = context.read_input(request.name)
    request_raw = canonical_json(materialize_figure_request(request.request.model_dump(mode="json", exclude_none=True), source))
    request_digest = hashlib.sha256(request_raw).hexdigest()
    existing = context.evidence()
    if any(r.get("metadata", {}).get("request_sha256") != request_digest for r in existing):
        raise ValueError("a saved selection or partial save already exists for a different request; use a new Run")
    parsed = FigureDigitizationRequest.model_validate_json(request_raw, strict=True)
    selected = [r for r in existing if r.get("metadata", {}).get("data_item") == SELECTION_ITEM]
    if selected:
        # Reopening a Run may change its workspace/alias spelling. Preserve the
        # original immutable family instead of regenerating or re-registering it.
        from scidiscovery.artifact_agent.schema.refs import ArtifactRef
        from scidiscovery.artifact_agent.service.tool_evidence import ToolEvidenceManifest
        from .figure_family import selected_family_files
        contents = {ArtifactRef.model_validate(r["artifact_ref"]): context.read_evidence(r["alias"]) for r in existing}
        files = selected_family_files(ToolEvidenceManifest(records=tuple(existing)), contents, context.input_ref(request.name))
        directory = context.workspace / ".operation-tools" / "figure-saved" / request_digest
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if directory.resolve() != context.workspace.resolve() / ".operation-tools" / "figure-saved" / request_digest:
            raise ValueError("saved figure files must remain in the exact workspace")
        returned = []
        for record in existing:
            name = record["metadata"]["data_item"]
            if name == SELECTION_ITEM:
                continue
            path = directory / (record["alias"] + Path(name).suffix)
            _publish_read_only(path, context.read_evidence(record["alias"]))
            returned.append({"alias": record["alias"], "data_item": name, "local_path": str(path)})
        report = files.get("validation_reports/validation_report.json")
        result = {"selected_material": selected[0]["alias"],
            "request_status": parsed.request_status, "files": returned,
            "integrity_status": json.loads(report[0])["integrity_status"] if report else "unresolved"}
        context.finish_attempt(result_status="figure_saved", response=result, successful=True)
        return result
    if parsed.request_status == "ready":
        if not any(a["state"] == "completed" and a["tool_name"] == "worker_curve_figure_preview"
                and a.get("result_status") == "figure_preview_" + request_digest for a in context.tool_attempts()):
            raise ValueError("preview this exact ready request before saving it")
        files, report = build_digitized_figure_bundle(source, request_raw)
    else:
        files, report = {}, None
    files[REQUEST_ITEM] = (request_raw, "application/json")
    members, returned = [], []
    directory = context.workspace / ".operation-tools" / "figure-saved" / request_digest
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if directory.resolve() != context.workspace.resolve() / ".operation-tools" / "figure-saved" / request_digest:
        raise ValueError("saved figure files must remain in the exact workspace")
    # Recovery aliases are navigation, never receipt identity. Validate every
    # adopted partial member first, then register only genuinely missing files.
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    by_item = {}
    for record in existing:
        name = record.get("metadata", {}).get("data_item")
        if name in by_item or name not in files:
            raise ValueError("partial figure save contains duplicate or unselected members")
        content, media_type = files[name]
        ref = ArtifactRef.model_validate(record["artifact_ref"])
        if (record.get("tool_name") != "worker_curve_figure_save"
                or record.get("source_ref") != context.input_ref(request.name).model_dump(mode="json")
                or record["metadata"].get("algorithm") != ALGORITHM
                or record["media_type"] != media_type
                or restore_figure_file(context.read_evidence(record["alias"]), record["metadata"]) != content):
            raise ValueError("partial figure member differs from its exact saved source/request/bytes")
        by_item[name] = record
    for name, (content, media_type) in sorted(files.items()):
        public, control = project_figure_file(name, content)
        record = by_item.get(name)
        if record is None:
            record = context.accept_evidence(raw=public, media_type=media_type,
                metadata={"kind":"figure_file", "figure_control":control, "data_item": name, "request_sha256": request_digest, "algorithm": ALGORITHM},
                derived_from=(request.name,))
        members.append(FigureFamilyMember(data_item=name, artifact_ref=record["artifact_ref"],
            media_type=media_type, size_bytes=len(public)))
        path = directory / (record["alias"] + Path(name).suffix)
        _publish_read_only(path, public)
        returned.append({"alias": record["alias"], "data_item": name, "local_path": str(path)})
    selection = SelectedFigureFamily(source_ref=context.input_ref(request.name),
        request_sha256=request_digest, members=tuple(members))
    public, control = project_figure_file(SELECTION_ITEM, canonical_json(selection.model_dump(mode="json")))
    record = context.accept_evidence(raw=public, media_type="application/json",
        metadata={"kind":"figure_file", "figure_control":control, "data_item": SELECTION_ITEM, "request_sha256": request_digest, "algorithm": ALGORITHM},
        derived_from=(request.name,))
    context.record_activity("deterministic_analysis_completed")
    result = {"selected_material": record["alias"],
        "request_status": parsed.request_status, "files": returned,
        "integrity_status": report["integrity_status"] if report else "unresolved"}
    context.finish_attempt(result_status="figure_saved", response=result, successful=True)
    return result


FIGURE_SAVE_TOOL = WorkerToolDefinition(
    name="worker_curve_figure_save",
    description="Explicitly select and seal the exact previewed request and complete deterministic figure family, then use returned evidence aliases to author Intake in this Run. One selection per Run; unchanged retry is idempotent. An unresolved request seals only its known fields and limits.",
    input_model=FigureDigitizationPreviewInput, capability="evidence.save_curve_figure",
    contextual_handler=_save, evidence_ports=("tool_evidence",), record_attempts=True,
)


class FigureFamilyReuseInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str = Field(default="paper_source", min_length=1, max_length=256)


def _reuse(request: BaseModel, context: OperationToolContext) -> dict[str, object]:
    """Select the bound prior family unchanged, for a fresh complete Intake revision."""
    from scidiscovery.operations.input_validation import ValidationSources
    from scidiscovery.artifact_agent.service.tool_evidence import ToolEvidenceManifest
    from .figure_family import _bound_family, SELECTION_ITEM, REQUEST_ITEM
    if not isinstance(request, FigureFamilyReuseInput):
        raise ValueError("figure reuse request has the wrong type")
    provenance_name, = context.input_names_for_port("figure_provenance")
    member_names = context.input_names_for_port("figure_family")
    names = (request.name, provenance_name, *member_names)
    if len(set(names)) != len(names):
        raise ValueError("reuse inputs must have distinct aliases")
    descriptors = {name: context.source_descriptor(name) for name in names}
    if (descriptors[request.name].port_name != "paper_source"
            or descriptors[provenance_name].port_name != "figure_provenance"
            or any(descriptors[name].port_name != "figure_family" for name in member_names)):
        raise ValueError("reuse requires declared prior source, provenance and family inputs")
    sources = ValidationSources({name: context.read_input(name) for name in names}, descriptors)
    files = _bound_family(sources)
    proof = ToolEvidenceManifest.model_validate_json(sources[provenance_name], strict=True)
    prior = {record["alias"]: record for record in proof.records}
    if any(record != prior.get(record["alias"]) for record in context.evidence()):
        raise ValueError("another selected or partial family already exists; cannot mix reuse with new extraction")
    records = context.adopt_bound_evidence(provenance_name)
    paths = {descriptors[name].artifact_ref.artifact_id: context.input_path(name) for name in member_names}
    selected = next(record for record in records if record["metadata"]["data_item"] == SELECTION_ITEM)
    result = {"selected_material": selected["alias"],
        "request_status": json.loads(files[REQUEST_ITEM][0])["request_status"], "reused": True,
        "files": [{"alias": record["alias"], "data_item": record["metadata"]["data_item"],
            "local_path": str(paths[record["artifact_ref"]["artifact_id"]])} for record in records]}
    context.finish_attempt(result_status="figure_reused", response=result, successful=True)
    return result


FIGURE_REUSE_TOOL = WorkerToolDefinition(
    name="worker_curve_figure_reuse",
    description="Explicitly reuse every immutable file and request from the bound prior Intake family for a wording-only revision, preserving original evidence aliases. Produces a new Intake; any chosen formal review applies independently to that new object. Do not combine with new extraction in the same Run.",
    input_model=FigureFamilyReuseInput, capability="evidence.reuse_curve_figure",
    contextual_handler=_reuse, evidence_ports=("tool_evidence",), record_attempts=True,
)
