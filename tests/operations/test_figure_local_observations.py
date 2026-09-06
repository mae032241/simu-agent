"""Regression: tracker diagnostics must not erase measured source pixels."""

import csv
import io
import json

import pytest
from PIL import Image

from scidiscovery.artifact_agent.schema.common import canonical_json
from curve_figure_evidence.operation_transforms import materialize_figure_evidence
from curve_figure_evidence.operation_transforms import bundle_figure_evidence
from tests.operations.test_curve_figure_digitization_tool import (
    _bundle_from_materialized,
    _coincident_overlap_request,
    _png_with_points,
    _request,
)


def test_gap_bad_seed_and_tracking_thresholds_preserve_other_direct_points():
    source = _png_with_points(tuple((x, 5) for x in (1, 2, 3, 7, 8, 9)))
    request = json.loads(_request(source))
    request["series"][0]["seeds"] = [[1.0, 5.0], [5.0, 5.0], [9.0, 5.0]]
    request["series"][0]["tracking"].update(
        min_points=100, min_visible_fraction=1.0, max_gap_px=0,
    )
    outputs = materialize_figure_evidence(
        {"paper_source": (source,), "figure_request": (canonical_json(request),)}
    )
    rows = list(csv.DictReader(outputs["curve_tables"][0].decode().splitlines()))
    assert {int(row["pixel_x_raw"]) for row in rows} == {1, 2, 3, 7, 8, 9}
    assert all(row["quantitative_measurement_claim_eligible"] == "1" for row in rows)
    series = _bundle_from_materialized(outputs).series[0]
    assert series.availability.status == "available"
    assert len(series.valid_intervals) == 2
    manifest = json.loads(outputs["figure_manifest"][0])
    assert manifest["ambiguities"] == []


def test_shared_direct_pixels_survive_member_tracking_diagnostics():
    source, request = _coincident_overlap_request()
    request["series"][0]["tracking"]["min_points"] = 100
    outputs = materialize_figure_evidence(
        {"paper_source": (source,), "figure_request": (canonical_json(request),)}
    )
    bundle = _bundle_from_materialized(outputs)
    assert all(series.availability.status == "available" for series in bundle.series)
    for raw in outputs["curve_tables"]:
        shared = [row for row in csv.DictReader(raw.decode().splitlines()) if row["shared_group"]]
        assert len(shared) == 3
        assert all(row["quantitative_measurement_claim_eligible"] == "1" for row in shared)
        assert all(row["support_source_series"] in {"black", "red"} for row in shared)
    normalized = bundle_figure_evidence({key: outputs[key] for key in ("figure_manifest", "validation_report", "curve_tables")})
    audit = json.loads(normalized["normalization_audit"][0])
    assert all(item["shared_pixel_provenance"] for item in audit["series"])


def test_single_direct_pixel_is_preserved_without_fabricating_an_interval():
    source = _png_with_points(((2, 5),))
    request = json.loads(_request(source))
    request["series"][0]["seeds"] = [[2.0, 5.0]]
    outputs = materialize_figure_evidence({"paper_source": (source,), "figure_request": (canonical_json(request),)})
    rows = list(csv.DictReader(outputs["curve_tables"][0].decode().splitlines()))
    assert len(rows) == 1 and rows[0]["quantitative_measurement_claim_eligible"] == "1"
    series = _bundle_from_materialized(outputs).series[0]
    assert len(series.points) == 1
    assert series.valid_intervals == ()


def test_overlay_distinguishes_each_series_and_shared_source():
    source, request = _coincident_overlap_request()
    outputs = materialize_figure_evidence(
        {"paper_source": (source,), "figure_request": (canonical_json(request),)}
    )
    overlay = Image.open(io.BytesIO(outputs["audit_overlays"][0])).convert("RGB")
    assert overlay.size == (420, 164)
    assert overlay.getpixel((2, 4 + 25)) == (0, 191, 255)
    assert overlay.getpixel((2, 5 + 25 + 82)) == (255, 0, 255)
    # The coverage strip marks real shared pixels identically in both views.
    assert overlay.getpixel((5, 40)) == overlay.getpixel((5, 122)) == (214, 160, 0)


def test_shared_gap_preserves_real_pixels_without_inventing_a_source():
    source, request = _coincident_overlap_request(black_overlap=(4,), red_overlap=(6,))
    outputs = materialize_figure_evidence(
        {"paper_source": (source,), "figure_request": (canonical_json(request),)}
    )
    for raw in outputs["curve_tables"]:
        rows = list(csv.DictReader(raw.decode().splitlines()))
        assert {int(row["pixel_x_raw"]) for row in rows} == {1, 2, 3, 4, 6, 7, 8, 9}
        assert all(row["quantitative_measurement_claim_eligible"] == "1" for row in rows)
        assert {row["support_source_series"] for row in rows if row["shared_group"]} == {"red", "black"}
    assert all(len(series.valid_intervals) == 2 for series in _bundle_from_materialized(outputs).series)
    overlay = Image.open(io.BytesIO(outputs["audit_overlays"][0])).convert("RGB")
    assert overlay.getpixel((5, 40)) == overlay.getpixel((5, 122)) == (170, 170, 170)


@pytest.mark.parametrize(
    ("branch_columns", "guide_y", "ambiguous_columns", "interval_count"),
    [
        (tuple(range(1, 10)), 5.0, set(range(1, 10)), 0),
        ((4, 5, 6), 5.0, {4, 5, 6}, 2),
        (tuple(range(1, 10)), 3.5, set(), 1),
    ],
    ids=("parallel_tie", "local_branch", "unique_nearby_path"),
)
def test_root_materialization_keeps_path_ambiguity_local(
    tmp_path, monkeypatch, branch_columns, guide_y, ambiguous_columns, interval_count,
):
    from tests.operations import test_m5_figure_review_closure as fixture

    source = _png_with_points(tuple(
        (x, y) for x in range(1, 10)
        for y in ((3, 7) if x in branch_columns else (5,))
    ))
    request = json.loads(_request(source))
    request["series"][0]["seeds"] = [[1.0, guide_y], [9.0, guide_y]]
    request["series"][0]["tracking"].update(
        seed_radius_px=2, guide_weight=1.0, max_guide_distance_px=4.0,
    )
    # Only the test-domain compiler supplies geometry; all publication and
    # extraction below use the real Root and production materializer.
    monkeypatch.setattr(fixture, "_two_series_source_and_request", lambda **_: (source, request))
    _, runtime, instance, root = fixture._system(tmp_path)
    fixture._register(runtime, instance, name="paper_source", content=source,
                      kind="paper_source", schema_id="opaque", media_type="image/png")
    compiled = root.call_tool("operation_invoke", {
        "name": "figure_request", "operation_id": "test.figure.compile.v1",
        "inputs": [{"port": "paper_source", "artifact_names": ["paper_source"]}],
    })["result"]["outputs"][0]["artifact_name"]
    call = {
        "name": "ambiguous_materialization", "operation_id": "science.figure.evidence.materialize.v1",
        "inputs": [{"port": "paper_source", "artifact_names": ["paper_source"]},
                   {"port": "figure_request", "artifact_names": [compiled]}],
    }
    assert root.call_tool("operation_preflight", call)["admissible"] is True
    published = root.call_tool("operation_invoke", call)["result"]["outputs"]
    by_kind = {}
    for item in published:
        artifact = runtime.artifacts.get_by_id(runtime.scheduler_bindings.resolve(
            instance=instance.instance_id, namespace="artifact", name=item["artifact_name"],
        ))
        by_kind.setdefault(item["kind"], []).append(runtime.artifacts.read(artifact.ref))
    outputs = {name: tuple(by_kind[kind]) for name, kind in (
        ("curve_tables", "digitized_curve_table"), ("figure_manifest", "figure_evidence_manifest"),
        ("validation_report", "figure_evidence_validation_report"), ("audit_overlays", "figure_audit_overlay"),
    )}
    rows = list(csv.DictReader(outputs["curve_tables"][0].decode().splitlines()))
    assert len(rows) == 9 and all(row["observed"] == "1" for row in rows)
    assert {int(row["pixel_x_raw"]) for row in rows if row["quantitative_measurement_claim_eligible"] == "0"} == ambiguous_columns
    assert all(row["eligibility_reason"] == "ambiguous_path" for row in rows if int(row["pixel_x_raw"]) in ambiguous_columns)
    report = json.loads(outputs["validation_report"][0])
    assert report["metrics"]["eligible_curve_rows"] == 9 - len(ambiguous_columns)
    normalized = _bundle_from_materialized(outputs).series[0]
    assert len(normalized.valid_intervals) == interval_count
    if len(ambiguous_columns) == 9:
        assert normalized.availability.status == "unavailable"
    elif ambiguous_columns:
        from curve_score.schema import CurveDomain, curve_series_domain_reason
        assert normalized.availability.status == "available"
        assert curve_series_domain_reason(normalized, CurveDomain(start=1.0, stop=7.0, unit="um", min_points=2)) == "continuous_domain_unavailable"
    overlay = Image.open(io.BytesIO(outputs["audit_overlays"][0])).convert("RGB")
    assert {x for x in range(1, 10) if overlay.getpixel((x, 40)) == (255, 64, 0)} == ambiguous_columns
