from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from pydantic import ValidationError

from curve_figure_evidence.figure_digitization import build_digitized_figure_bundle
from curve_figure_evidence.figure_digitization_contract import FigureDigitizationRequest
from curve_figure_evidence.figure_source import inspect_figure_source_bytes
from curve_figure_evidence.figure_worker_tool import (
    FIGURE_DIGITIZATION_PREVIEW_TOOL,
    FIGURE_SOURCE_INSPECTION_TOOL,
    FigureDigitizationPreviewInput,
    FigureSourceInspectionInput,
)
from curve_figure_evidence.operation_transforms import (
    bundle_figure_evidence,
    figure_parentage,
)
from curve_score.schema import CurveBundle
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.refs import ArtifactRef


def _digitized_outputs(source, request):
    files, _ = build_digitized_figure_bundle(source, request)
    return {port: tuple(content for name, (content, _) in sorted(files.items()) if name.startswith(prefix + "/"))
        for port, prefix in (("figure_manifest", "figure_manifest"), ("source_panels", "source_panels"),
            ("audit_overlays", "audit_overlays"), ("curve_tables", "curve_tables"), ("validation_report", "validation_reports"))}


def _png(*, shared: bool = False) -> bytes:
    image = Image.new("RGB", (20, 20), "white")
    for x in range(2, 18):
        image.putpixel((x, 12), (0, 0, 0))
        image.putpixel((x, 8), (255, 0, 0))
    if shared:
        for x in range(8, 11):
            image.putpixel((x, 12), (255, 255, 255))
            image.putpixel((x, 8), (255, 255, 255))
            image.putpixel((x, 10), (255, 0, 0))
    for x in range(2, 5):
        image.putpixel((x, 1), (0, 0, 0))
    for x in range(6, 9):
        image.putpixel((x, 1), (255, 0, 0))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def _request(source: bytes, *, shared: bool = False, y_scale: str = "linear") -> bytes:
    digest = hashlib.sha256(source).hexdigest()
    recovered = inspect_figure_source_bytes(source, media_type="image/png")[0]
    series = [
        {
            "series_key": "black",
            "label": "Black curve",
            "color": "#000000",
            "line_style": "solid",
            "binding_source": "legend",
            "visible_label": "Black curve",
            "binding_bbox": [2, 0, 5, 2],
            "seeds": (
                [[2.0, 12.0], [7.0, 12.0], [8.0, 10.0], [10.0, 10.0], [11.0, 12.0], [17.0, 12.0]]
                if shared
                else [[2.0, 12.0], [17.0, 12.0]]
            ),
        }
    ]
    if shared:
        series.append(
            {
                "series_key": "red",
                "label": "Red curve",
                "color": "#ff0000",
                "line_style": "solid",
                "binding_source": "legend",
                "visible_label": "Red curve",
                "binding_bbox": [6, 0, 9, 2],
                "seeds": [[2.0, 8.0], [7.0, 8.0], [8.0, 10.0], [10.0, 10.0], [11.0, 8.0], [17.0, 8.0]],
            }
        )
    y_ticks = [[16.0, 1.0], [4.0, 13.0]]
    if y_scale == "log10":
        y_ticks = [[16.0, 1e-6], [4.0, 1e6]]
    return canonical_json(
        {
            "schema_version": "scidiscovery.curve-figure-digitization-request.v2",
            "figure_key": "test_figure",
            "panel_key": "main",
            "figure": "Fig. test",
            "citation": "Fig. test",
            "source": {
                "source_kind": "raster_image",
                "media_type": "image/png",
                "source_sha256": digest,
                "recovered_image_sha256": recovered.image_sha256,
                "width": recovered.width,
                "height": recovered.height,
                "recovery_tool": recovered.recovery_tool,
                "recovery_tool_version": recovered.recovery_tool_version,
            },
            "plot_bbox": [2, 3, 18, 18],
            "axis_calibration": {
                "x": {
                    "scale": "linear",
                    "unit": "V",
                    "ticks": [[17.0, 15.0], [2.0, 0.0]],
                    "uncertainty_px": 0.0,
                },
                "y": {
                    "scale": y_scale,
                    "unit": "A",
                    "ticks": y_ticks,
                    "uncertainty_px": 0.0,
                },
            },
            "series": series,
        }
    )


class _Context:
    def __init__(self, workspace: Path, source: Path) -> None:
        self.workspace = workspace
        self.source = source
        self.remaining_seconds = 30
        self.activities: list[str] = []

    def read_input(self, name: str) -> bytes:
        return self.input_path(name).read_bytes()

    def source_descriptor(self, name: str):
        assert name == "paper_source"
        return SimpleNamespace(port_name="paper_source")

    def finish_attempt(self, **values):
        assert values["successful"]

    def input_path(self, name: str) -> Path:
        assert name == "paper_source"
        return self.source

    def input_media_type(self, name: str) -> str:
        assert name == "paper_source"
        return "image/png"

    def input_ref(self, name: str) -> ArtifactRef:
        assert name == "paper_source"
        content = self.source.read_bytes()
        return ArtifactRef(
            artifact_id="paper_source",
            sha256=hashlib.sha256(content).hexdigest(),
            kind="paper_source",
            schema_id="opaque",
        )

    def record_activity(self, name: str) -> None:
        self.activities.append(name)


@pytest.mark.parametrize("y_scale", ["linear", "log10"])
def test_agent_tick_pairs_are_normalized_and_program_materializes_outputs(
    y_scale: str,
) -> None:
    source = _png()
    request = _request(source, y_scale=y_scale)
    files, report = build_digitized_figure_bundle(source, request)

    assert report["integrity_status"] == "valid"
    assert sorted(name for name in files if name.startswith("audit_overlays/")) == [
        "audit_overlays/main--identity-fidelity.png",
        "audit_overlays/main--numeric-redraw.png",
    ]
    manifest = json.loads(files["figure_manifest/evidence.json"][0])
    axes = manifest["panels"][0]["axis_calibration"]
    assert (axes["x"]["pixel_min"], axes["x"]["value_min"]) == (2.0, 0.0)
    assert axes["y"]["scale"] == y_scale
    table = next(value[0] for name, value in files.items() if name.startswith("curve_tables/"))
    rows = tuple(csv.DictReader(table.decode().splitlines()))
    assert len(rows) == 16
    assert all(row["quantitative_measurement_claim_eligible"] == "1" for row in rows)


def test_missing_columns_are_reported_not_rejected() -> None:
    source = _png()
    image = Image.open(io.BytesIO(source)).convert("RGB")
    image.putpixel((9, 12), (255, 255, 255))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    changed = stream.getvalue()
    request = json.loads(_request(changed))

    files, report = build_digitized_figure_bundle(changed, canonical_json(request))

    assert report["integrity_status"] == "valid"
    manifest = json.loads(files["figure_manifest/evidence.json"][0])
    series = manifest["panels"][0]["series"][0]
    assert series["point_count"] == 15
    assert series["max_gap_px"] == 1


def test_shared_visible_pixels_are_program_derived_and_eligible_for_both_series() -> None:
    source = _png(shared=True)
    request = _request(source, shared=True)
    files, report = build_digitized_figure_bundle(source, request)
    manifest = json.loads(files["figure_manifest/evidence.json"][0])

    shared = manifest["panels"][0]["shared_support"]
    assert len(shared) == 1
    assert shared[0]["member_series"] == ["black", "red"]
    assert shared[0]["pixel_ranges"] == [[8, 11]]
    group = shared[0]["group_key"]
    rows = [
        row
        for name, (raw, _) in files.items()
        if name.startswith("curve_tables/")
        for row in csv.DictReader(raw.decode().splitlines())
        if row["shared_group"] == group
    ]
    assert len(rows) == 6
    assert {(row["pixel_x_raw"], row["pixel_y_raw"]) for row in rows} == {
        (str(x), "10") for x in range(8, 11)
    }
    assert all(row["quantitative_measurement_claim_eligible"] == "1" for row in rows)
    assert report["metrics"]["cross_series_shared_pixel_count"] == 3


def test_request_rejects_program_owned_fields() -> None:
    source = _png()
    request = json.loads(_request(source))
    for field, value in (
        ("pixel_range", [2, 18]),
        ("tracking", {"min_points": 5}),
        ("eligibility", {"default_eligible": True}),
        ("color_tolerance", 2.0),
        ("min_color_pixels", 3),
    ):
        changed = json.loads(json.dumps(request))
        changed["series"][0][field] = value
        with pytest.raises(ValidationError):
            FigureDigitizationRequest.model_validate_json(canonical_json(changed), strict=True)
    changed = json.loads(json.dumps(request))
    changed["shared_support"] = []
    with pytest.raises(ValidationError):
        FigureDigitizationRequest.model_validate_json(canonical_json(changed), strict=True)


def test_preview_and_formal_materialization_use_identical_outputs(tmp_path: Path) -> None:
    source = _png(shared=True)
    request = _request(source, shared=True)
    source_path = tmp_path / "source.png"
    source_path.write_bytes(source)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    context = _Context(workspace, source_path)
    handler = FIGURE_DIGITIZATION_PREVIEW_TOOL.contextual_handler
    assert handler is not None
    preview = handler(
        FigureDigitizationPreviewInput(
            request=FigureDigitizationRequest.model_validate_json(request, strict=True)
        ),
        context,
    )
    formal = _digitized_outputs(source, request)

    preview_images = {
        item["data_item"]: Path(item["local_path"]).read_bytes()
        for item in preview["images"]
    }
    formal_images = {
        name: raw
        for name, raw in zip(
            sorted(preview_images), formal["audit_overlays"], strict=True
        )
    }
    assert preview_images == formal_images
    full_report = json.loads(formal["validation_report"][0])
    assert preview["source_status"] == full_report["source_status"]
    assert preview["integrity_status"] == full_report["integrity_status"]
    assert all(full_report["metrics"][key] == value for key, value in preview["metrics"].items())
    assert json.loads(Path(preview["details_path"]).read_bytes())["validation_report"] == json.loads(formal["validation_report"][0])
    assert all(Path(item["local_path"]).stat().st_mode & 0o222 == 0 for item in preview["images"])
    assert context.activities == ["deterministic_analysis_completed"]


def test_raw_inspection_returns_one_read_only_source_image(tmp_path: Path) -> None:
    source_path = tmp_path / "source.png"
    source_path.write_bytes(_png())
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    context = _Context(workspace, source_path)
    handler = FIGURE_SOURCE_INSPECTION_TOOL.contextual_handler
    assert handler is not None

    result = handler(FigureSourceInspectionInput(), context)

    assert len(result["images"]) == 1
    assert "candidate_overlay" not in result["images"][0]
    preview = Path(result["images"][0]["local_path"])
    assert preview.is_relative_to(workspace)
    assert preview.stat().st_mode & 0o222 == 0


def test_materialized_tables_still_normalize_for_curve_consumers() -> None:
    source = _png(shared=True)
    materialized = _digitized_outputs(source, _request(source, shared=True))
    normalized = bundle_figure_evidence(
        {
            "figure_manifest": materialized["figure_manifest"],
            "validation_report": materialized["validation_report"],
            "curve_tables": materialized["curve_tables"],
        }
    )

    bundle = CurveBundle.model_validate_json(normalized["curve_bundle"][0], strict=True)
    assert {item.series_key for item in bundle.series} == {"black", "red"}
    assert all(item.availability.status == "available" for item in bundle.series)


def test_figure_parentage_binds_intake_selected_family_and_exact_audit() -> None:
    def bound(port, ref, *, parents=(), labels=None, verdict=None, producer=None):
        return SimpleNamespace(port_name=port, artifact=SimpleNamespace(ref=ref, parent_refs=tuple(parents),
            labels=tuple((labels or {}).items()), handoff_verdict=verdict, producer_run_id=producer))
    source = bound("paper_source", "source")
    family = [bound("figure_family", "file", parents=("source",), labels={"tool_name": "worker_curve_figure_save"})]
    proof = bound("figure_provenance", "proof", parents=("source", "file"), labels={
        "operation_id": "science.evidence.extract.figure.v3", "operation_output_port": "recovery_manifest_output", "tool_producer_run": "author"})
    intake = bound("scientific_intake", "intake", parents=("source", "proof"), producer="author", labels={
        "operation_id": "science.evidence.extract.figure.v3", "operation_output_port": "scientific_intake"})
    audit = bound("evidence_audit", "audit", parents=("source", "proof", "intake", "file"), verdict="pass", labels={
        "operation_id": "science.figure.evidence.audit.v2", "operation_output_port": "evidence_audit"})
    cohort = (source, proof, intake, audit, *family)
    assert figure_parentage(cohort, {})
    audit.artifact.handoff_verdict = "pass"
    audit.artifact.parent_refs = ("source", "proof", "old_intake", "file")
    assert not figure_parentage(cohort, {})
    audit.artifact.parent_refs = ("source", "proof", "intake", "file")
    proof.artifact.labels = (*proof.artifact.labels[:-1], ("tool_producer_run", "another_author"))
    assert not figure_parentage(cohort, {})
