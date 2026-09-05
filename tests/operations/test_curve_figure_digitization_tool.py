from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

from curve_score.figure_digitization import (
    FigureDigitizationRequest,
    build_digitized_figure_bundle,
)
from curve_score.operation_transforms import bundle_figure_evidence
from curve_score.schema import CurveBundle, CurveDomain, curve_series_domain_reason
from curve_score.figure_science_operations import FIGURE_REQUEST_CONTEXT
from curve_score.figure_evidence_validation import (
    FigureEvidenceBundleError,
    build_figure_evidence_validation_report,
)
from curve_score.figure_source import inspect_figure_source, inspect_figure_source_bytes
from curve_score.figure_worker_tool import (
    FIGURE_SOURCE_INSPECTION_TOOL,
    FigureSourceInspectionInput,
)
from curve_score.operation_transforms import materialize_figure_evidence
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.operation_contract import SemanticRuleViolation


def _png_with_points(points: tuple[tuple[int, int], ...]) -> bytes:
    image = Image.new("RGB", (12, 12), "white")
    for point in points:
        image.putpixel(point, (255, 0, 0))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def _request(source: bytes, *, recovered=None) -> bytes:
    image = recovered or inspect_figure_source_bytes(source, media_type="image/png")[0]
    return canonical_json(
        {
            "schema_version": "scidiscovery.curve-figure-digitization-request.v2",
            "figure_key": "bounded_figure",
            "panel_key": "main",
            "figure": "Fig. 1",
            "citation": "Fig. 1",
            "source": {
                "source_kind": "raster_image",
                "media_type": "image/png",
                "source_sha256": hashlib.sha256(source).hexdigest(),
                "recovered_image_sha256": image.image_sha256,
                "width": image.width,
                "height": image.height,
                "recovery_tool": image.recovery_tool,
                "recovery_tool_version": image.recovery_tool_version,
            },
            "plot_bbox": [1, 1, 10, 10],
            "axis_calibration": {
                "x": {
                    "scale": "linear",
                    "unit": "um",
                    "pixel_min": 1.0,
                    "pixel_max": 9.0,
                    "value_min": 0.0,
                    "value_max": 8.0,
                    "reprojection_error_px": 0.0,
                },
                "y": {
                    "scale": "linear",
                    "unit": "cm^-3",
                    "pixel_min": 9.0,
                    "pixel_max": 1.0,
                    "value_min": 1.0,
                    "value_max": 9.0,
                    "reprojection_error_px": 0.0,
                },
            },
            "series": [
                {
                    "series_key": "reference",
                    "label": "Reference",
                    "color": "#ff0000",
                    "color_tolerance": 0.0,
                    "line_style": "solid",
                    "binding_source": "legend",
                    "visible_label": "Reference",
                    "binding_bbox": [1, 1, 4, 10],
                    "min_color_pixels": 1,
                    "seeds": [[1.0, 9.0], [9.0, 1.0]],
                    "tracking": {
                        "max_vertical_step_px": 2.0,
                        "max_gap_px": 0,
                        "max_gap_vertical_displacement_px": 2.0,
                        "max_guide_distance_px": 2.0,
                        "ambiguity_margin_px": 0.25,
                        "guide_weight": 0.9,
                        "min_visible_fraction": 0.5,
                        "max_ambiguous_fraction": 0.1,
                        "skip_penalty": 3.0,
                        "min_points": 3,
                        "seed_radius_px": 1,
                        "plot_border_exclusion_px": 0,
                        "overdraw_candidate_endpoint_distance_px": 2.0,
                    },
                    "eligibility": {"default_eligible": True},
                }
            ],
        }
    )


def _valid_source() -> bytes:
    return _png_with_points(tuple((x, 10 - x) for x in range(1, 10)))


def _frozen_fig4_request(pdf: Path) -> tuple[bytes, bytes]:
    source = pdf.read_bytes()
    recovered = next(
        item
        for item in inspect_figure_source(
            pdf, media_type="application/pdf", page=6
        )
        if item.pdf_object_id == 241
    )
    geometry = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "fig4_measured_continuous_lines.json"
        ).read_text(encoding="utf-8")
    )
    request = {
        "schema_version": "scidiscovery.curve-figure-digitization-request.v2",
        "request_status": "ready",
        **geometry,
        "source": {
            "source_kind": "pdf_embedded_image",
            "media_type": "application/pdf",
            "source_sha256": hashlib.sha256(source).hexdigest(),
            "page": recovered.page,
            "document_image_index": recovered.document_image_index,
            "page_image_index": recovered.page_image_index,
            "pdf_object_id": recovered.pdf_object_id,
            "pdf_object_generation": recovered.pdf_object_generation,
            "recovered_image_sha256": recovered.image_sha256,
            "width": recovered.width,
            "height": recovered.height,
            "recovery_tool": recovered.recovery_tool,
            "recovery_tool_version": recovered.recovery_tool_version,
        },
    }
    return source, canonical_json(request)


def _bundle_from_materialized(outputs: dict[str, tuple[bytes, ...]]) -> CurveBundle:
    normalized = bundle_figure_evidence(
        {
            "figure_manifest": outputs["figure_manifest"],
            "validation_report": outputs["validation_report"],
            "curve_tables": outputs["curve_tables"],
        }
    )
    return CurveBundle.model_validate_json(normalized["curve_bundle"][0], strict=True)


def test_typed_request_is_bound_to_the_exact_raster_source() -> None:
    source = _valid_source()
    payload = json.loads(_request(source))
    FIGURE_REQUEST_CONTEXT.implementation(payload, {"paper_source": source}, {})

    changed = dict(payload)
    changed["source"] = {**payload["source"], "source_sha256": "0" * 64}
    with pytest.raises(SemanticRuleViolation, match="source hash differs"):
        FIGURE_REQUEST_CONTEXT.implementation(
            changed, {"paper_source": source}, {}
        )


def test_materialization_is_deterministic_and_uses_transform_ports() -> None:
    source = _valid_source()
    request = _request(source)
    first = materialize_figure_evidence(
        {"paper_source": (source,), "figure_request": (request,)}
    )
    second = materialize_figure_evidence(
        {"paper_source": (source,), "figure_request": (request,)}
    )
    assert first == second
    assert set(first) == {
        "figure_manifest",
        "source_panels",
        "audit_overlays",
        "curve_tables",
        "validation_report",
    }
    assert {name: len(items) for name, items in first.items()} == {
        "figure_manifest": 1,
        "source_panels": 1,
        "audit_overlays": 1,
        "curve_tables": 1,
        "validation_report": 1,
    }
    manifest = json.loads(first["figure_manifest"][0])
    assert manifest["source"]["image_sha256"] == json.loads(request)["source"][
        "recovered_image_sha256"
    ]
    rows = tuple(
        csv.DictReader(first["curve_tables"][0].decode("utf-8").splitlines())
    )
    assert len(rows) == 9


def test_changed_source_fails_before_any_curve_is_materialized() -> None:
    source = _valid_source()
    request = _request(source)
    other = _png_with_points(tuple((x, 3) for x in range(1, 10)))
    with pytest.raises(ValueError, match="source hash differs"):
        build_digitized_figure_bundle(other, request)


def test_unresolved_request_records_missing_calibration_without_guessing() -> None:
    source = _valid_source()
    image = inspect_figure_source_bytes(source, media_type="image/png")[0]
    payload = {
        "schema_version": "scidiscovery.curve-figure-digitization-request.v2",
        "request_status": "unresolved",
        "unresolved_reasons": ["Axis calibration is not visibly anchored."],
        "figure_key": "bounded_figure",
        "panel_key": "main",
        "figure": "Fig. 1",
        "citation": "Fig. 1",
        "source": {
            "source_kind": "raster_image",
            "media_type": "image/png",
            "source_sha256": hashlib.sha256(source).hexdigest(),
            "recovered_image_sha256": image.image_sha256,
            "width": image.width,
            "height": image.height,
            "recovery_tool": image.recovery_tool,
            "recovery_tool_version": image.recovery_tool_version,
        },
    }
    FIGURE_REQUEST_CONTEXT.implementation(payload, {"paper_source": source}, {})
    with pytest.raises(ValueError, match="unresolved figure request"):
        build_digitized_figure_bundle(source, canonical_json(payload))


def test_undeclared_visible_gap_and_axis_seed_fail_closed_as_unresolved() -> None:
    source = _png_with_points(
        tuple((x, 10 - x) for x in (*range(1, 4), *range(6, 10)))
        + ((1, 1), (2, 1), (3, 1))
    )
    request = json.loads(_request(source))
    request["series"][0]["seeds"] = [[1.0, 1.0], [9.0, 1.0]]
    request["series"][0]["tracking"]["plot_border_exclusion_px"] = 1
    outputs = materialize_figure_evidence(
        {
            "paper_source": (source,),
            "figure_request": (canonical_json(request),),
        }
    )
    manifest = json.loads(outputs["figure_manifest"][0])
    messages = {item["message"] for item in manifest["ambiguities"]}
    assert manifest["status"] == "unresolved"
    assert any("seed" in message for message in messages)
    assert any("undeclared trace gap" in message for message in messages)
    rows = tuple(csv.DictReader(outputs["curve_tables"][0].decode().splitlines()))
    assert rows and not any(
        int(row["quantitative_measurement_claim_eligible"]) for row in rows
    )


def test_ineligible_internal_interval_cannot_be_scored_across() -> None:
    source = _valid_source()
    request = json.loads(_request(source))
    request["series"][0]["eligibility"]["ineligible_pixel_ranges"] = [[4, 6]]
    outputs = materialize_figure_evidence(
        {
            "paper_source": (source,),
            "figure_request": (canonical_json(request),),
        }
    )
    bundle = _bundle_from_materialized(outputs)
    series = bundle.series[0]
    assert series.availability.status == "available"
    assert len(series.valid_intervals) == 2
    assert curve_series_domain_reason(
        series, CurveDomain(start=1.0, stop=7.0, unit="um", min_points=2)
    ) == "continuous_domain_unavailable"


def test_axis_outside_plot_is_rejected_by_the_request_schema() -> None:
    source = _valid_source()
    request = json.loads(_request(source))
    request["axis_calibration"]["x"]["pixel_max"] = 10.0
    with pytest.raises(ValidationError, match="axis calibration exceeds plot_bbox"):
        FigureDigitizationRequest.model_validate_json(
            canonical_json(request), strict=True
        )


def test_undeclared_cross_series_pixel_ownership_is_rejected() -> None:
    source = _valid_source()
    request = json.loads(_request(source))
    duplicate = {**request["series"][0], "series_key": "duplicate"}
    request["series"].append(duplicate)
    with pytest.raises(FigureEvidenceBundleError, match="shared_group"):
        build_digitized_figure_bundle(source, canonical_json(request))


def test_unresolved_series_cannot_forge_eligible_rows() -> None:
    source = _valid_source()
    request = json.loads(_request(source))
    request["series"][0]["seeds"] = [[1.0, 1.0], [9.0, 1.0]]
    request["series"][0]["tracking"]["plot_border_exclusion_px"] = 1
    files, _ = build_digitized_figure_bundle(source, canonical_json(request))
    manifest = json.loads(files["figure_manifest/evidence.json"][0])
    table_name = manifest["panels"][0]["series"][0]["data_item"]
    fieldnames, *raw_rows = files[table_name][0].decode().splitlines()
    rows = list(csv.DictReader([fieldnames, *raw_rows]))
    rows[0]["quantitative_measurement_claim_eligible"] = "1"
    rows[0]["eligibility_reason"] = ""
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream, fieldnames=fieldnames.split(","), lineterminator="\n"
    )
    writer.writeheader()
    writer.writerows(rows)
    changed = stream.getvalue().encode()
    siblings = {
        name: value
        for name, value in files.items()
        if not name.startswith("figure_manifest/")
        and not name.startswith("validation_reports/")
    }
    siblings[table_name] = (changed, "text/csv")
    for item in manifest["provenance"]["output_artifacts"]:
        if item["data_item"] == table_name:
            item["sha256"] = hashlib.sha256(changed).hexdigest()
            item["bytes"] = len(changed)
    with pytest.raises(FigureEvidenceBundleError, match="unresolved figure series"):
        build_figure_evidence_validation_report(
            manifest_data_item="figure_manifest/evidence.json",
            manifest_content=canonical_json(manifest),
            sibling_files=siblings,
        )


def test_old_curve_table_without_source_and_request_cannot_materialize() -> None:
    with pytest.raises(ValueError, match="one source and one request"):
        materialize_figure_evidence({"curve_tables": (b"old,csv\n",)})


def test_deprecated_covered_eligibility_remains_parseable_but_is_not_granted() -> None:
    image = Image.new("RGB", (12, 12), "white")
    for x in range(1, 10):
        image.putpixel((x, 5), (255, 0, 0))
    for x in range(1, 4):
        image.putpixel((x, 4), (0, 0, 0))
    for x in range(6, 10):
        image.putpixel((x, 6), (0, 0, 0))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    source = stream.getvalue()
    request = json.loads(_request(source))
    request["series"] = [
        {
            **request["series"][0],
            "series_key": "covered",
            "label": "Covered black line",
            "color": "#000000",
            "visible_label": "Covered",
            "binding_bbox": [1, 3, 10, 7],
            "seeds": [[1.0, 4.0], [9.0, 6.0]],
        },
        {
            **request["series"][0],
            "series_key": "visible",
            "label": "Visible red line",
            "visible_label": "Visible",
            "binding_bbox": [1, 3, 10, 7],
            "seeds": [[1.0, 5.0], [9.0, 5.0]],
        },
    ]
    request["shared_support"] = [
        {
            "group_key": "red_over_black",
            "visible_series": "visible",
            "covered_series": ["covered"],
            "pixel_ranges": [[4, 6]],
            "mode": "overdraw",
            "covered_eligible": True,
            "max_endpoint_distance_px": 2.0,
        }
    ]
    FIGURE_REQUEST_CONTEXT.implementation(
        request, {"paper_source": source}, {}
    )
    outputs = materialize_figure_evidence(
        {
            "paper_source": (source,),
            "figure_request": (canonical_json(request),),
        }
    )
    manifest = json.loads(outputs["figure_manifest"][0])
    assert manifest["status"] == "qualified"
    report = json.loads(outputs["validation_report"][0])
    covered = next(
        item for item in report["series"] if item["series_key"] == "covered"
    )
    assert covered["shared_row_count"] == 2
    assert covered["eligible_row_count"] == 7
    table = next(
        raw
        for raw in outputs["curve_tables"]
        if "covered" in raw.decode().splitlines()[1]
    )
    rows = tuple(csv.DictReader(table.decode().splitlines()))
    shared = tuple(row for row in rows if row["support_kind"] == "shared_occlusion")
    assert {int(row["pixel_x_raw"]) for row in shared} == {4, 5}
    assert not any(int(row["quantitative_measurement_claim_eligible"]) for row in shared)


def test_overdraw_support_requires_preserved_covered_series_anchors() -> None:
    image = Image.new("RGB", (12, 12), "white")
    for x in range(1, 10):
        image.putpixel((x, 5), (255, 0, 0))
    for x in range(1, 4):
        image.putpixel((x, 4), (0, 0, 0))
    for x in range(6, 10):
        image.putpixel((x, 6), (0, 0, 0))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    source = stream.getvalue()
    request = json.loads(_request(source))
    request["series"] = [
        {
            **request["series"][0],
            "series_key": "covered",
            "label": "Covered black line",
            "color": "#000000",
            "visible_label": "Covered",
            "binding_bbox": [1, 3, 10, 7],
            "seeds": [[1.0, 4.0], [9.0, 6.0]],
        },
        {
            **request["series"][0],
            "series_key": "visible",
            "label": "Visible red line",
            "visible_label": "Visible",
            "binding_bbox": [1, 3, 10, 7],
            "seeds": [[1.0, 5.0], [9.0, 5.0]],
        },
    ]
    request["shared_support"] = [
        {
            "group_key": "red_over_black",
            "visible_series": "visible",
            "covered_series": ["covered"],
            "pixel_ranges": [[4, 6]],
            "mode": "overdraw",
            "covered_eligible": False,
            "max_endpoint_distance_px": 2.0,
        }
    ]
    files, _ = build_digitized_figure_bundle(source, canonical_json(request))
    manifest = json.loads(files["figure_manifest/evidence.json"][0])
    siblings = {
        name: value
        for name, value in files.items()
        if not name.startswith("figure_manifest/")
        and not name.startswith("validation_reports/")
    }
    table_name = next(
        name
        for name in siblings
        if name.startswith("curve_tables/") and "--covered.csv" in name
    )
    reader = csv.DictReader(siblings[table_name][0].decode().splitlines())
    fields = reader.fieldnames
    assert fields is not None
    rows = [row for row in reader if row["pixel_x_raw"] != "3"]
    changed_stream = io.StringIO(newline="")
    writer = csv.DictWriter(changed_stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    changed = changed_stream.getvalue().encode()
    siblings[table_name] = (changed, "text/csv")
    for series in manifest["panels"][0]["series"]:
        if series["series_key"] == "covered":
            series["point_count"] -= 1
    manifest["metrics"]["total_point_count"] -= 1
    for item in manifest["provenance"]["output_artifacts"]:
        if item["data_item"] == table_name:
            item["sha256"] = hashlib.sha256(changed).hexdigest()
            item["bytes"] = len(changed)

    with pytest.raises(
        FigureEvidenceBundleError,
        match="lacks covered-series endpoints",
    ):
        build_figure_evidence_validation_report(
            manifest_data_item="figure_manifest/evidence.json",
            manifest_content=canonical_json(manifest),
            sibling_files=siblings,
        )


def _coincident_overlap_request(
    *,
    black_overlap: tuple[int, ...] = (5,),
    red_overlap: tuple[int, ...] = (4, 6),
    red_overlap_y: int = 5,
    black_interference: tuple[tuple[int, int], ...] = (),
    max_member_distance_px: float = 2.0,
) -> tuple[bytes, dict[str, object]]:
    image = Image.new("RGB", (12, 12), "white")
    for x in (1, 2, 3):
        image.putpixel((x, 4), (0, 0, 0))
        image.putpixel((x, 5), (255, 0, 0))
    for x in black_overlap:
        image.putpixel((x, 5), (0, 0, 0))
    for x in red_overlap:
        image.putpixel((x, red_overlap_y), (255, 0, 0))
    for x in (7, 8, 9):
        image.putpixel((x, 6), (0, 0, 0))
        image.putpixel((x, 5), (255, 0, 0))
    for point in black_interference:
        image.putpixel(point, (0, 0, 0))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    source = stream.getvalue()
    request = json.loads(_request(source))
    request["series"] = [
        {
            **request["series"][0],
            "series_key": "black",
            "label": "Black",
            "color": "#000000",
            "visible_label": "Black",
            "binding_bbox": [1, 3, 10, 7],
            "seeds": [[1.0, 4.0], [9.0, 6.0]],
        },
        {
            **request["series"][0],
            "series_key": "red",
            "label": "Red",
            "visible_label": "Red",
            "binding_bbox": [1, 3, 10, 7],
            "seeds": [[1.0, 5.0], [9.0, 5.0]],
        },
    ]
    request["shared_support"] = [
        {
            "group_key": "alternating_overlap",
            "member_series": ["black", "red"],
            "pixel_ranges": [[4, 7]],
            "mode": "coincident_overlap",
            "max_member_distance_px": max_member_distance_px,
        }
    ]
    return source, request


def test_coincident_overlap_uses_one_real_source_per_column() -> None:
    source, request = _coincident_overlap_request()
    outputs = materialize_figure_evidence(
        {
            "paper_source": (source,),
            "figure_request": (canonical_json(request),),
        }
    )
    manifest = json.loads(outputs["figure_manifest"][0])
    report = json.loads(outputs["validation_report"][0])
    assert manifest["status"] == "qualified"
    assert report["metrics"]["cross_series_shared_pixel_count"] == 3

    rows_by_x: dict[int, list[dict[str, str]]] = {}
    for table in outputs["curve_tables"]:
        for row in csv.DictReader(table.decode().splitlines()):
            if row["shared_group"] == "alternating_overlap":
                rows_by_x.setdefault(int(row["pixel_x_raw"]), []).append(row)
    assert set(rows_by_x) == {4, 5, 6}
    for rows in rows_by_x.values():
        assert len(rows) == 2
        assert len({(row["pixel_x_subpixel"], row["pixel_y_subpixel"]) for row in rows}) == 1
        direct = [row for row in rows if row["support_kind"] == "direct_pixel"]
        copied = [row for row in rows if row["support_kind"] == "shared_occlusion"]
        assert len(direct) == len(copied) == 1
        assert direct[0]["support_source_series"] == direct[0]["series_key"]
        assert copied[0]["support_source_series"] == direct[0]["series_key"]
        assert sum(int(row["quantitative_measurement_claim_eligible"]) for row in rows) == 1

    bundle = _bundle_from_materialized(outputs)
    assert all(item.availability.status == "available" for item in bundle.series)
    assert all(len(item.valid_intervals) == 2 for item in bundle.series)


def test_coincident_overlap_preserves_each_simultaneously_visible_source() -> None:
    source, request = _coincident_overlap_request(
        black_overlap=(4, 5, 6),
        red_overlap=(4, 5, 6),
        red_overlap_y=6,
    )
    outputs = materialize_figure_evidence(
        {
            "paper_source": (source,),
            "figure_request": (canonical_json(request),),
        }
    )
    direct_sources = set()
    for table in outputs["curve_tables"]:
        for row in csv.DictReader(table.decode().splitlines()):
            if (
                row["shared_group"] == "alternating_overlap"
                and row["support_kind"] == "direct_pixel"
            ):
                direct_sources.add(row["series_key"])
    assert direct_sources == {"black", "red"}


def test_shared_copy_cannot_be_made_independently_eligible() -> None:
    source, request = _coincident_overlap_request()
    files, _ = build_digitized_figure_bundle(source, canonical_json(request))
    manifest = json.loads(files["figure_manifest/evidence.json"][0])
    siblings = {
        name: value
        for name, value in files.items()
        if not name.startswith("figure_manifest/")
        and not name.startswith("validation_reports/")
    }
    table_name = next(
        name for name in siblings if name.startswith("curve_tables/")
    )
    fields, rows = None, []
    reader = csv.DictReader(siblings[table_name][0].decode().splitlines())
    fields = reader.fieldnames
    assert fields is not None
    for row in reader:
        if row["support_kind"] == "shared_occlusion":
            row["quantitative_measurement_claim_eligible"] = "1"
            row["eligibility_reason"] = ""
            rows.append(row)
            rows.extend(reader)
            break
        rows.append(row)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    changed = stream.getvalue().encode()
    siblings[table_name] = (changed, "text/csv")
    for item in manifest["provenance"]["output_artifacts"]:
        if item["data_item"] == table_name:
            item["sha256"] = hashlib.sha256(changed).hexdigest()
            item["bytes"] = len(changed)
    with pytest.raises(
        FigureEvidenceBundleError,
        match="coincident-overlap copied rows must name the source and be ineligible",
    ):
        build_figure_evidence_validation_report(
            manifest_data_item="figure_manifest/evidence.json",
            manifest_content=canonical_json(manifest),
            sibling_files=siblings,
        )


def test_coincident_overlap_source_identity_is_checked_against_image() -> None:
    source, request = _coincident_overlap_request()
    files, _ = build_digitized_figure_bundle(source, canonical_json(request))
    manifest = json.loads(files["figure_manifest/evidence.json"][0])
    siblings = {
        name: value
        for name, value in files.items()
        if not name.startswith("figure_manifest/")
        and not name.startswith("validation_reports/")
    }
    for table_name in tuple(
        name for name in siblings if name.startswith("curve_tables/")
    ):
        reader = csv.DictReader(siblings[table_name][0].decode().splitlines())
        fields = reader.fieldnames
        assert fields is not None
        rows = list(reader)
        for row in rows:
            if row["shared_group"] != "alternating_overlap" or row["pixel_x_raw"] != "4":
                continue
            row["support_source_series"] = "black"
            row["support_kind"] = (
                "direct_pixel" if row["series_key"] == "black" else "shared_occlusion"
            )
            if row["series_key"] == "black":
                row["quantitative_measurement_claim_eligible"] = "1"
                row["eligibility_reason"] = ""
            else:
                row["quantitative_measurement_claim_eligible"] = "0"
                row["eligibility_reason"] = "shared_occlusion"
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        changed = stream.getvalue().encode()
        siblings[table_name] = (changed, "text/csv")
        for item in manifest["provenance"]["output_artifacts"]:
            if item["data_item"] == table_name:
                item["sha256"] = hashlib.sha256(changed).hexdigest()
                item["bytes"] = len(changed)

    with pytest.raises(
        FigureEvidenceBundleError,
        match="source pixel does not match its source series",
    ):
        build_figure_evidence_validation_report(
            manifest_data_item="figure_manifest/evidence.json",
            manifest_content=canonical_json(manifest),
            sibling_files=siblings,
        )


def test_shared_source_raw_pixel_cannot_be_detached_from_subpixel_trace() -> None:
    source, request = _coincident_overlap_request(black_interference=((4, 1),))
    files, _ = build_digitized_figure_bundle(source, canonical_json(request))
    manifest = json.loads(files["figure_manifest/evidence.json"][0])
    siblings = {
        name: value
        for name, value in files.items()
        if not name.startswith("figure_manifest/")
        and not name.startswith("validation_reports/")
    }
    for table_name in tuple(
        name for name in siblings if name.startswith("curve_tables/")
    ):
        reader = csv.DictReader(siblings[table_name][0].decode().splitlines())
        fields = reader.fieldnames
        assert fields is not None
        rows = list(reader)
        for row in rows:
            if row["shared_group"] != "alternating_overlap" or row["pixel_x_raw"] != "4":
                continue
            row["pixel_y_raw"] = "1"
            row["support_source_series"] = "black"
            row["support_kind"] = (
                "direct_pixel" if row["series_key"] == "black" else "shared_occlusion"
            )
            if row["series_key"] == "black":
                row["quantitative_measurement_claim_eligible"] = "1"
                row["eligibility_reason"] = ""
            else:
                row["quantitative_measurement_claim_eligible"] = "0"
                row["eligibility_reason"] = "shared_occlusion"
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        changed = stream.getvalue().encode()
        siblings[table_name] = (changed, "text/csv")
        for item in manifest["provenance"]["output_artifacts"]:
            if item["data_item"] == table_name:
                item["sha256"] = hashlib.sha256(changed).hexdigest()
                item["bytes"] = len(changed)

    with pytest.raises(
        FigureEvidenceBundleError,
        match="raw and subpixel coordinates do not identify one source trace",
    ):
        build_figure_evidence_validation_report(
            manifest_data_item="figure_manifest/evidence.json",
            manifest_content=canonical_json(manifest),
            sibling_files=siblings,
        )


def test_coincident_overlap_requires_preserved_direct_member_anchors() -> None:
    source, request = _coincident_overlap_request()
    files, _ = build_digitized_figure_bundle(source, canonical_json(request))
    manifest = json.loads(files["figure_manifest/evidence.json"][0])
    siblings = {
        name: value
        for name, value in files.items()
        if not name.startswith("figure_manifest/")
        and not name.startswith("validation_reports/")
    }
    table_name = next(
        name
        for name in siblings
        if name.startswith("curve_tables/") and "--black.csv" in name
    )
    reader = csv.DictReader(siblings[table_name][0].decode().splitlines())
    fields = reader.fieldnames
    assert fields is not None
    rows = [row for row in reader if row["pixel_x_raw"] != "3"]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    changed = stream.getvalue().encode()
    siblings[table_name] = (changed, "text/csv")
    for series in manifest["panels"][0]["series"]:
        if series["series_key"] == "black":
            series["point_count"] -= 1
    manifest["metrics"]["total_point_count"] -= 1
    for item in manifest["provenance"]["output_artifacts"]:
        if item["data_item"] == table_name:
            item["sha256"] = hashlib.sha256(changed).hexdigest()
            item["bytes"] = len(changed)

    with pytest.raises(
        FigureEvidenceBundleError,
        match="lacks direct member endpoints",
    ):
        build_figure_evidence_validation_report(
            manifest_data_item="figure_manifest/evidence.json",
            manifest_content=canonical_json(manifest),
            sibling_files=siblings,
        )


def test_coincident_overlap_requires_each_member_binding_to_match() -> None:
    source, request = _coincident_overlap_request()
    request["series"][0]["binding_bbox"] = [4, 4, 5, 6]
    with pytest.raises(
        SemanticRuleViolation,
        match="independently matched member bindings",
    ):
        FIGURE_REQUEST_CONTEXT.implementation(
            request,
            {"paper_source": source},
            {},
        )


@pytest.mark.parametrize(
    ("black_overlap", "red_overlap", "distance", "message"),
    [
        ((), (4, 5, 6), 2.0, "direct contribution"),
        ((4,), (6,), 2.0, "lacks direct pixel 5"),
        ((5,), (4, 6), 0.5, "endpoint distance"),
    ],
)
def test_coincident_overlap_fails_closed_without_visible_support(
    black_overlap: tuple[int, ...],
    red_overlap: tuple[int, ...],
    distance: float,
    message: str,
) -> None:
    source, request = _coincident_overlap_request(
        black_overlap=black_overlap,
        red_overlap=red_overlap,
        max_member_distance_px=distance,
    )
    with pytest.raises(SemanticRuleViolation, match=message):
        FIGURE_REQUEST_CONTEXT.implementation(
            request,
            {"paper_source": source},
            {},
        )


def test_pdf_embedded_image_selection_has_exact_object_identity(tmp_path: Path) -> None:
    image = Image.new("RGB", (12, 12), "white")
    image.putpixel((3, 3), (255, 0, 0))
    pdf = tmp_path / "source.pdf"
    image.save(pdf, format="PDF")

    recovered = inspect_figure_source(
        pdf, media_type="application/pdf", page=1
    )
    assert len(recovered) == 1
    assert recovered[0].page == 1
    assert recovered[0].document_image_index == 0
    assert recovered[0].page_image_index == 0
    assert recovered[0].pdf_object_id == 1
    assert (recovered[0].width, recovered[0].height) == (12, 12)


def test_pdf_request_is_replayed_by_the_formal_materializer(tmp_path: Path) -> None:
    image = Image.new("RGB", (20, 20), "white")
    for x in range(2, 18):
        for offset in (-1, 0, 1):
            image.putpixel((x, 19 - x + offset), (0, 0, 0))
    pdf = tmp_path / "source.pdf"
    image.save(pdf, format="PDF", quality=100)
    source = pdf.read_bytes()
    recovered = inspect_figure_source(
        pdf, media_type="application/pdf", page=1
    )[0]
    request = json.loads(_request(recovered.content, recovered=recovered))
    request["source"] = {
        "source_kind": "pdf_embedded_image",
        "media_type": "application/pdf",
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "page": recovered.page,
        "document_image_index": recovered.document_image_index,
        "page_image_index": recovered.page_image_index,
        "pdf_object_id": recovered.pdf_object_id,
        "pdf_object_generation": recovered.pdf_object_generation,
        "recovered_image_sha256": recovered.image_sha256,
        "width": recovered.width,
        "height": recovered.height,
        "recovery_tool": recovered.recovery_tool,
        "recovery_tool_version": recovered.recovery_tool_version,
    }
    request["plot_bbox"] = [2, 2, 18, 18]
    request["axis_calibration"]["x"].update(
        {"pixel_min": 2.0, "pixel_max": 17.0, "value_max": 15.0}
    )
    request["axis_calibration"]["y"].update(
        {"pixel_min": 17.0, "pixel_max": 2.0, "value_max": 16.0}
    )
    request["series"][0].update(
        {
            "color": "#000000",
            "color_tolerance": 48.0,
            "binding_bbox": [2, 2, 18, 18],
            "seeds": [[2.0, 17.0], [17.0, 2.0]],
        }
    )
    request["series"][0]["tracking"].update(
        {
            "max_vertical_step_px": 4.0,
            "max_gap_vertical_displacement_px": 8.0,
            "max_guide_distance_px": 8.0,
            "min_visible_fraction": 0.4,
        }
    )
    FIGURE_REQUEST_CONTEXT.implementation(
        request, {"paper_source": source}, {}
    )
    outputs = materialize_figure_evidence(
        {
            "paper_source": (source,),
            "figure_request": (canonical_json(request),),
        }
    )
    manifest = json.loads(outputs["figure_manifest"][0])
    assert manifest["source"]["pdf_sha256"] == hashlib.sha256(source).hexdigest()
    assert manifest["source"]["pdf_page"] == 1
    assert manifest["source"]["pdf_object"] == "1 0"


def test_frozen_fig4_preserves_red_evidence_and_black_uncertainty() -> None:
    pdf = (
        Path(__file__).resolve().parents[2]
        / "deliverables"
        / "m7-full-science-gpt56-20260903"
        / "state-resumed-m7-test0"
        / "artifacts"
        / "sha256"
        / "75"
        / "0c8cb5944ed9fe25c5072db084bb0194ed682d5e1ea40f25103f4aa89c05c3"
    )
    if not pdf.is_file():
        pytest.skip("frozen local Fig.4 PDF is not present")
    source, request = _frozen_fig4_request(pdf)
    first = materialize_figure_evidence(
        {"paper_source": (source,), "figure_request": (request,)}
    )
    second = materialize_figure_evidence(
        {"paper_source": (source,), "figure_request": (request,)}
    )
    assert first == second

    manifest = json.loads(first["figure_manifest"][0])
    by_key = {
        item["series_key"]: item for item in manifest["panels"][0]["series"]
    }
    assert manifest["status"] == "unresolved"
    assert manifest["metrics"]["qualified_series_count"] == 1
    assert by_key["measured_in083al017as"]["point_count"] == 565
    assert by_key["measured_in083al017as"]["max_gap_px"] == 56
    assert by_key["measured_in083ga017as"]["point_count"] == 805
    assert by_key["measured_in083ga017as"]["max_gap_px"] == 2
    assert manifest["provenance"]["recovery_tool"] == "pdfimages+Pillow"

    bundle = _bundle_from_materialized(first)
    normalized = {item.series_key: item for item in bundle.series}
    assert normalized["measured_in083al017as"].availability.status == "unavailable"
    assert normalized["measured_in083ga017as"].availability.status == "available"
    report = json.loads(first["validation_report"][0])
    counts = {item["series_key"]: item for item in report["series"]}
    assert counts["measured_in083al017as"]["eligible_row_count"] == 0
    assert counts["measured_in083ga017as"]["eligible_row_count"] == 801
    red_table = next(
        item
        for item in first["curve_tables"]
        if b"measured_in083ga017as" in item
    )
    red_rows = tuple(csv.DictReader(io.StringIO(red_table.decode("utf-8"))))
    annotation_rows = tuple(
        row for row in red_rows if 537 <= int(row["pixel_x_raw"]) < 541
    )
    assert len(annotation_rows) == 4
    assert all(row["observed"] == "1" for row in annotation_rows)
    assert all(
        row["quantitative_measurement_claim_eligible"] == "0"
        for row in annotation_rows
    )
    assert {
        row["eligibility_reason"] for row in annotation_rows
    } == {"same_color_annotation_overlap"}
    red_intervals = normalized["measured_in083ga017as"].valid_intervals
    annotation_left = (537.0 - 166.0) * 0.8 / (974.0 - 166.0)
    annotation_right = (541.0 - 166.0) * 0.8 / (974.0 - 166.0)
    assert all(
        interval.stop <= annotation_left or interval.start >= annotation_right
        for interval in red_intervals
    )


class _ToolContext:
    def __init__(self, workspace: Path, pdf: Path) -> None:
        self.workspace = workspace
        self.remaining_seconds = 30
        self.pdf = pdf
        self.activities: list[str] = []

    def input_path(self, name: str) -> Path:
        assert name == "paper_source"
        return self.pdf

    def input_media_type(self, name: str) -> str:
        assert name == "paper_source"
        return "application/pdf"

    def input_ref(self, name: str) -> ArtifactRef:
        assert name == "paper_source"
        raw = self.pdf.read_bytes()
        return ArtifactRef(
            artifact_id="paper_source",
            sha256=hashlib.sha256(raw).hexdigest(),
            kind="paper_source",
            schema_id="opaque",
        )

    def record_activity(self, name: str) -> None:
        self.activities.append(name)


def test_registered_inspection_tool_publishes_only_run_local_read_only_preview(
    tmp_path: Path,
) -> None:
    image = Image.new("RGB", (12, 12), "white")
    pdf = tmp_path / "source.pdf"
    image.save(pdf, format="PDF")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    context = _ToolContext(workspace, pdf)
    handler = FIGURE_SOURCE_INSPECTION_TOOL.contextual_handler
    assert handler is not None
    response = handler(FigureSourceInspectionInput(page=1), context)
    preview = Path(response["images"][0]["local_path"])
    assert preview.is_relative_to(workspace)
    assert preview.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert preview.stat().st_mode & 0o222 == 0
    assert context.activities == ["deterministic_analysis_completed"]
