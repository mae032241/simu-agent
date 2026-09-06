"""Raw-source role-chain regressions; no paper-specific geometry or answers."""
import io
import json

import pytest
from PIL import Image, ImageDraw
from pydantic import ValidationError

from curve_figure_evidence import figure_detection
from curve_figure_evidence.figure_detection import detect_source, OCRToken
from curve_figure_evidence.figure_digitization_contract import FigureExtractionIntent
from curve_figure_evidence.figure_worker_tool import FigureSourceInspectionInput
from curve_figure_evidence.operation_transforms import materialize_figure_evidence


def source_bytes():
    output = io.BytesIO()
    Image.new("RGB", (80, 60), "white").save(output, format="PNG")
    return output.getvalue()


def intent_for(raw):
    source_page = 1 if raw.startswith(b"%PDF-") else None
    detected = figure_detection.detect_reference_source(raw, source_page)
    return {
        "schema_version": "scidiscovery.figure-extraction-intent.v2",
        "source_sha256": detected.source_sha256,
        "detector_receipt": detected.receipt,
        "figure": "Unresolved figure", "panel": None, "source_page": source_page,
        "plot_candidate_id": None, "bindings": [],
        "unresolved_reasons": ["No visible quantitative plot"],
        "rejected_candidates": [],
    }


def measured_source(monkeypatch, *, reverse=False, gap=False, marker=255):
    image = Image.new("RGB", (320, 240), "white")
    image.putpixel((0, 0), (marker, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((45, 30, 285, 185), outline="black")
    tokens = []
    for x, value in zip((65, 165, 265), ((8, 4, 0) if reverse else (0, 4, 8))):
        draw.line((x, 182, x, 190), fill="black")
        tokens.append(OCRToken(f"{value} V", (x-4, 195, x+4, 205), "synthetic adapter"))
    for y, value in zip((45, 110, 175), (100, 10, 1)):
        draw.line((40, y, 48, y), fill="black")
        tokens.append(OCRToken(f"{value} A", (10, y-4, 35, y+4), "synthetic adapter"))
    for label, offset, color in (("Reference", 0, "red"), ("Candidate", 35, "blue")):
        draw.text((165, 8 + offset//3), label, fill=color)
        tokens.append(OCRToken(label, (165, 8+offset//3, 225, 18+offset//3), "synthetic adapter"))
        for x in range(65, 266):
            if not gap or not 150 <= x < 170:
                image.putpixel((x, 145 - x//5 - offset), Image.new("RGB", (1,1), color).getpixel((0,0)))
    output = io.BytesIO()
    image.save(output, format="PNG")
    monkeypatch.setattr("curve_figure_evidence.figure_detection._ocr", lambda _: (tuple(tokens), (), "synthetic adapter"))
    raw = output.getvalue()
    detected = detect_source(raw)
    plot = next(p for d in detected.detections for p in d.plots if all(a.resolved for a in p.axes))
    detection = next(d for d in detected.detections if plot in d.plots)
    bindings = [{"candidate_id": p.candidate_id, "visible_label": "Reference" if p.color_class == 0 else "Candidate",
                 "semantic_identity": "reference observation" if p.color_class == 0 else "candidate observation"}
                for p in detection.paths if p.plot_id == plot.candidate_id]
    # The synthetic fixture binds by actual source color; production never derives identities from color.
    for binding, path in zip(bindings, (p for p in detection.paths if p.plot_id == plot.candidate_id)):
        pixel = path.pixels[0]
        red = image.getpixel((pixel.x, pixel.y))[0] > 200
        binding.update(visible_label="Reference" if red else "Candidate",
                       semantic_identity="reference observation" if red else "candidate observation")
    return raw, {**intent_for(raw), "plot_candidate_id": plot.candidate_id,
                 "bindings": bindings, "unresolved_reasons": []}


@pytest.mark.parametrize("reverse,gap", [(False, False), (True, False), (True, True)])
def test_real_materializer_measures_detector_pixels(monkeypatch, reverse, gap):
    import csv
    raw, intent = measured_source(monkeypatch, reverse=reverse, gap=gap)
    values = {"paper_source": (raw,), "figure_intent": (json.dumps(intent).encode(),)}
    result = materialize_figure_evidence(values)
    assert result == materialize_figure_evidence(values)
    assert json.loads(result["figure_request"][0])["result_shape"] == "measured"
    for table in result["curve_tables"]:
        rows = list(csv.DictReader(io.StringIO(table.decode())))
        xs = [float(r["x_value"]) for r in rows]
        assert xs == sorted(xs)
        assert all(float(r["y_value"]) > 0 for r in rows)
        if gap:
            assert all(not 150 <= int(r["pixel_x_raw"]) < 170 for r in rows)


@pytest.mark.parametrize("field", ["bbox", "seeds", "ticks", "coverage", "max_gap", "points", "parameters"])
def test_inspection_rejects_mechanical_parameters(field):
    with pytest.raises(ValidationError):
        FigureSourceInspectionInput.model_validate({"name": "paper_source", field: 1})


def test_reference_page_is_semantic_but_not_geometry():
    assert FigureSourceInspectionInput(source_page=12).source_page == 12
    with pytest.raises(ValidationError):
        FigureSourceInspectionInput(source_page=0)


def test_request_prompt_locates_fixed_target_before_inspection():
    from curve_figure_evidence.figure_science_operations import REQUEST_PROMPT
    assert REQUEST_PROMPT.index("worker_extract_pdf_text") < REQUEST_PROMPT.index(
        "worker_curve_figure_inspect_source")
    assert "do not substitute another figure" in REQUEST_PROMPT


def test_materializer_replays_the_exact_reference_page():
    images = [Image.new("RGB", (20, 20), "white") for _ in range(12)]
    stream = io.BytesIO()
    images[0].save(stream, format="PDF", save_all=True, append_images=images[1:])
    raw = stream.getvalue()
    detected = figure_detection.detect_reference_source(raw, 12)
    intent = {
        "schema_version": "scidiscovery.figure-extraction-intent.v2",
        "source_sha256": detected.source_sha256,
        "detector_receipt": detected.receipt,
        "figure": "Requested figure", "panel": None, "source_page": 12,
        "plot_candidate_id": None, "bindings": [],
        "unresolved_reasons": ["No visibly anchored series"],
        "rejected_candidates": [],
    }
    from curve_figure_evidence.figure_science_operations import FIGURE_REQUEST_CONTEXT
    FIGURE_REQUEST_CONTEXT.implementation(intent, {"paper_source": raw}, {})
    result = materialize_figure_evidence({
        "paper_source": (raw,), "figure_intent": (json.dumps(intent).encode(),)})
    assert json.loads(result["figure_request"][0])["source"]["page"] == 12


@pytest.mark.parametrize("raw, counts", [(source_bytes(), (1, 1, 0)), (b"unrecoverable", (0, 0, 0))])
def test_zero_table_materialization_shapes(raw, counts):
    intent = intent_for(raw)
    FigureExtractionIntent.model_validate_json(json.dumps(intent), strict=True)
    result = materialize_figure_evidence({"paper_source": (raw,), "figure_intent": (json.dumps(intent).encode(),)})
    assert tuple(len(result[p]) for p in ("source_panels", "audit_overlays", "curve_tables")) == counts
    assert all(len(result[p]) == 1 for p in ("figure_request", "figure_manifest", "validation_report"))


def publish_family(catalog, runtime, instance, root, raw, intent, prefix):
    from tests.operations.test_m5_figure_review_closure import _register, _complete_agent, REQUEST, MATERIALIZE
    source_name = prefix + "_source"
    _register(runtime, instance, name=source_name, content=raw, kind="paper_source",
              schema_id="opaque", media_type="image/png")
    intent_name = _complete_agent(catalog, runtime, root, operation_id=REQUEST, name=prefix+"_intent",
        inputs=[{"port": "paper_source", "artifact_names": [source_name]}], payload=intent)
    output = root.call_tool("operation_invoke", {"name": prefix+"_materialize", "operation_id": MATERIALIZE,
        "inputs": [{"port": "paper_source", "artifact_names": [source_name]},
                   {"port": "figure_intent", "artifact_names": [intent_name]}]})
    kinds = {"figure_measurement_request": "figure_request", "figure_evidence_manifest": "figure_manifest",
             "figure_evidence_validation_report": "validation_report", "figure_source_panel": "source_panels",
             "figure_audit_overlay": "audit_overlays", "digitized_curve_table": "curve_tables"}
    names = {name: [] for name in kinds.values()}
    names.update(paper_source=[source_name], figure_intent=[intent_name])
    for item in output["result"]["outputs"]:
        names[kinds[item["kind"]]].append(item["artifact_name"])
    return names


@pytest.mark.parametrize("raw", [source_bytes(), b"unrecoverable"], ids=["unresolved_image", "unrecovered"])
def test_zero_table_draft_audit_revision_and_exact_family(tmp_path, raw):
    from tests.operations.test_m5_figure_review_closure import (
        _system, _complete_agent, _bindings, _revision_bindings, _intake_payload, _audit_payload,
        EXTRACTION, AUDIT, BUNDLE,
    )
    from curve_figure_evidence.figure_evidence_normalizer import normalize_figure_evidence
    catalog, runtime, instance, root = _system(tmp_path)
    names = publish_family(catalog, runtime, instance, root, raw, intent_for(raw), "zero")
    intake = _intake_payload()
    intake["scientific_foundation"]["summary"] = "The complete source family has no trustworthy quantitative table."
    draft = _complete_agent(catalog, runtime, root, operation_id=EXTRACTION, name="zero_draft",
        inputs=_bindings(names), payload=intake)
    audit = _complete_agent(catalog, runtime, root, operation_id=AUDIT, name="zero_audit",
        inputs=_bindings(names, include_intake=draft), payload=_audit_payload(status="fail", basis="Preserve the explicit no-table limitation."), verdict="blocked")
    intake["scientific_foundation"]["summary"] += " No quantitative claim can be derived."
    revision_inputs = _revision_bindings(names, prior_draft=draft, change_request=audit)
    revised = _complete_agent(catalog, runtime, root, operation_id=EXTRACTION, name="zero_revision",
        inputs=revision_inputs, payload=intake)
    approved = _complete_agent(catalog, runtime, root, operation_id=AUDIT, name="zero_reaudit",
        inputs=_bindings(names, include_intake=revised), payload=_audit_payload(basis="The Intake faithfully records no quantitative measurement."))
    refused = root.call_tool("operation_preflight", {"name": "zero_normalize", "operation_id": BUNDLE,
        "inputs": _bindings(names, include_intake=revised, include_audit=approved)})
    assert refused["admissible"] is False and refused["reason_code"] == "guard_rejected"
    direct = materialize_figure_evidence({"paper_source": (raw,), "figure_intent": (json.dumps(intent_for(raw)).encode(),)})
    with pytest.raises(ValueError, match="requires measured curve tables"):
        normalize_figure_evidence(manifest_content=direct["figure_manifest"][0],
            validation_report_content=direct["validation_report"][0], curve_tables={})
    for anchor in ("figure_request", "figure_manifest", "validation_report"):
        assert root.call_tool("operation_preflight", {"name": "missing_"+anchor, "operation_id": EXTRACTION,
            "inputs": _bindings({k: v for k, v in names.items() if k != anchor}),
            "instruction": "Reject the absent stable family anchor."})["admissible"] is False
    other_raw = raw + b"different bytes"
    other = publish_family(catalog, runtime, instance, root, other_raw, intent_for(other_raw), "other")
    assert root.call_tool("operation_preflight", {"name": "mixed_zero_family", "operation_id": EXTRACTION,
        "inputs": _bindings({**names, "figure_manifest": other["figure_manifest"]}),
        "instruction": "Reject mixed materializations."})["admissible"] is False


@pytest.mark.parametrize("field", ["bbox", "seeds", "ticks", "coverage", "max_gap", "points", "parameters", "statistics"])
def test_nested_intent_cannot_write_measurements(monkeypatch, field):
    from jsonschema.validators import validator_for
    from curve_figure_evidence.figure_science_operations import FIGURE_INTENT_SCHEMA
    raw, intent = measured_source(monkeypatch)
    intent["bindings"][0][field] = {"arbitrary": 1}
    schema = json.loads(FIGURE_INTENT_SCHEMA)
    assert not validator_for(schema)(schema).is_valid(intent)
    with pytest.raises(ValidationError):
        materialize_figure_evidence({"paper_source": (raw,), "figure_intent": (json.dumps(intent).encode(),)})


@pytest.mark.parametrize("defect", ["source", "receipt", "page", "plot", "path", "anchor", "cross_source", "cross_plot"])
def test_intent_replay_rejects_forged_or_cross_bound_candidates(monkeypatch, defect):
    from curve_figure_evidence.figure_science_operations import FIGURE_REQUEST_CONTEXT
    from scidiscovery.operation_contract import SemanticRuleViolation
    raw, intent = measured_source(monkeypatch)
    if defect in {"source", "receipt", "plot"}:
        intent[{"source": "source_sha256", "receipt": "detector_receipt", "plot": "plot_candidate_id"}[defect]] = "0" * 64
    elif defect == "page":
        intent["source_page"] = 1
    elif defect in {"path", "anchor"}:
        intent["bindings"][0]["candidate_id" if defect == "path" else "identity_anchor_id"] = "0" * 64
    elif defect == "cross_source":
        other, other_intent = measured_source(monkeypatch, marker=254)
        intent["bindings"][0]["candidate_id"] = other_intent["bindings"][0]["candidate_id"]
    else:
        with Image.open(io.BytesIO(raw)) as original:
            combined = Image.new("RGB", (320, 480), "white")
            combined.paste(original, (0, 0))
            combined.paste(original, (0, 240))
        stream = io.BytesIO()
        combined.save(stream, format="PNG")
        raw = stream.getvalue()
        detected = detect_source(raw)
        plots = detected.detections[0].plots
        assert len(plots) >= 2
        intent = {**intent_for(raw), "plot_candidate_id": plots[0].candidate_id,
                  "bindings": [{"candidate_id": next(p.candidate_id for p in detected.detections[0].paths
                     if p.plot_id != plots[0].candidate_id), "visible_label": "Reference", "semantic_identity": "reference observation"}],
                  "unresolved_reasons": []}
    with pytest.raises(SemanticRuleViolation):
        FIGURE_REQUEST_CONTEXT.implementation(intent, {"paper_source": raw}, {})
    with pytest.raises(ValueError):
        materialize_figure_evidence({"paper_source": (raw,), "figure_intent": (json.dumps(intent).encode(),)})


def test_materialize_replays_after_tool_workspace_removed(tmp_path, monkeypatch):
    from curve_figure_evidence.figure_worker_tool import FIGURE_SOURCE_INSPECTION_TOOL
    from tests.operations.test_curve_figure_digitization_tool import _ToolContext
    import shutil
    raw, intent = measured_source(monkeypatch)
    path = tmp_path / "source.png"
    path.write_bytes(raw)
    workspace = tmp_path / "worker"
    workspace.mkdir()
    response = FIGURE_SOURCE_INSPECTION_TOOL.contextual_handler(FigureSourceInspectionInput(), _ToolContext(workspace, path))
    assert response["detector_receipt"] == intent["detector_receipt"]
    forbidden = {"bbox", "pixels", "ticks", "seeds", "coverage", "max_gap", "points", "statistics", "width", "height"}
    def inspect(value):
        if isinstance(value, dict):
            assert not forbidden.intersection(value)
            for child in value.values(): inspect(child)
        elif isinstance(value, (tuple, list)):
            for child in value: inspect(child)
    inspect(response)
    for frame in response["images"]:
        for name in ("source_preview", "candidate_overlay"):
            assert not __import__("pathlib").Path(frame[name]).stat().st_mode & 0o222
    before = materialize_figure_evidence({"paper_source": (raw,), "figure_intent": (json.dumps(intent).encode(),)})
    shutil.rmtree(workspace / ".operation-tools")
    after = materialize_figure_evidence({"paper_source": (raw,), "figure_intent": (json.dumps(intent).encode(),)})
    assert before == after


def test_real_detector_resource_bytes_control_only_declared_consumers(monkeypatch):
    from tests.operations.test_m5_figure_review_closure import CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, FIGURE_PLUGIN
    from tcad_artifact.plugin import PLUGIN as TCAD_PLUGIN
    from scidiscovery.operations.catalog import compile_catalog
    def _catalog():
        return compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, FIGURE_PLUGIN, TCAD_PLUGIN))
    from curve_figure_evidence import figure_digitization_contract as contract
    baseline = _catalog()
    assert len(baseline.operation_ids()) == 48
    original = json.loads(contract.DETECTOR_CONTRACT)
    for changed in ({**original, "detector_version": "changed-test-contract"},
                    {**original, "ocr": {**original["ocr"], "version": "5.4.0"}}):
        monkeypatch.setattr(contract, "DETECTOR_CONTRACT", json.dumps(changed, sort_keys=True).encode())
        catalog = _catalog()
        assert catalog.operation_ids() == baseline.operation_ids()
        for operation_id in ("science.figure.request.prepare.v1", "science.figure.evidence.materialize.v1"):
            assert catalog.operation(operation_id).digest != baseline.operation(operation_id).digest
        for operation_id in baseline.operation_ids():
            if baseline.operation(operation_id).plugin_id == "curve_score":
                assert catalog.operation(operation_id).digest == baseline.operation(operation_id).digest


def test_no_tesseract_never_invents_axes(monkeypatch):
    raw, intent = measured_source(monkeypatch)
    # Restore the actual adapter and exercise its unbound-executable branch.
    monkeypatch.undo()
    detected = detect_source(raw)
    assert "ocr_dependency_unavailable:tesseract" in detected.unresolved
    intent.update(detector_receipt=detected.receipt, plot_candidate_id=None, bindings=[],
                  unresolved_reasons=["OCR unavailable; visual plot cannot be calibrated"])
    result = materialize_figure_evidence({"paper_source": (raw,), "figure_intent": (json.dumps(intent).encode(),)})
    assert not result["curve_tables"]
    assert json.loads(result["figure_request"][0])["axis_calibration"] is None


@pytest.mark.parametrize("select_one", [False, True], ids=["shared_selected_series", "exclusive_ambiguous_path"])
def test_g3_shared_observations_are_eligible_but_exclusive_branches_are_not(monkeypatch, select_one):
    import csv
    from collections import Counter
    raw, _ = measured_source(monkeypatch)
    with Image.open(io.BytesIO(raw)) as original:
        image = original.convert("RGB")
    draw = ImageDraw.Draw(image)
    draw.rectangle((49, 31, 284, 181), fill="white")
    for x in range(65, 266):
        distance = max(0, abs(x-165)-10)//3
        image.putpixel((x, 100-distance), (0,0,0))
        image.putpixel((x, 100+distance), (0,0,0))
    output = io.BytesIO()
    image.save(output, format="PNG")
    raw = output.getvalue()
    detected = detect_source(raw)
    detection = detected.detections[0]
    plot = next(p for p in detection.plots if all(a.resolved for a in p.axes))
    paths = [p for p in detection.paths if p.plot_id == plot.candidate_id]
    assert len(paths) > 1
    intent = {**intent_for(raw), "plot_candidate_id": plot.candidate_id,
        "bindings": [{"candidate_id": path.candidate_id, "visible_label": "Reference", "semantic_identity": "Ambiguous candidate branch"} for path in paths],
        "unresolved_reasons": ["Crossing connectivity remains ambiguous"]}
    if select_one:
        intent["bindings"] = intent["bindings"][:1]
    result = materialize_figure_evidence({"paper_source": (raw,), "figure_intent": (json.dumps(intent).encode(),)})
    rows = [row for table in result["curve_tables"] for row in csv.DictReader(io.StringIO(table.decode()))]
    counts = Counter(row["pixel_id"] for row in rows)
    shared = {pixel for pixel, count in counts.items() if count > 1}
    if select_one:
        assert not shared
        assert all(r["quantitative_measurement_claim_eligible"] == "0" for r in rows)
        from curve_figure_evidence.operation_transforms import bundle_figure_evidence
        normalized = json.loads(bundle_figure_evidence(result)["curve_bundle"][0])
        assert normalized["series"][0]["availability"]["reason_code"] == "no_quantitative_eligible_rows"
        return
    assert shared
    for row in rows:
        if row["pixel_id"] in shared:
            assert row["shared_group"] == row["pixel_id"]
            assert row["coordinate_ownership"] == "shared"
            assert row["quantitative_measurement_claim_eligible"] == "1"
    agreed_rows = [r for r in rows if 155 <= int(r["pixel_x_raw"]) <= 175]
    assert agreed_rows and all(r["coordinate_ownership"] == "shared" for r in agreed_rows)
    assert all(r["quantitative_measurement_claim_eligible"] == "1" for r in agreed_rows)
    branch_rows = [r for r in rows if int(r["pixel_x_raw"]) < 140 or int(r["pixel_x_raw"]) > 190]
    assert branch_rows and any(r["coordinate_ownership"] == "exclusive" for r in branch_rows)
    assert all(r["quantitative_measurement_claim_eligible"] == "0" for r in branch_rows if r["pixel_id"] not in shared)
    assert any(r["coordinate_ownership"] == "shared" for r in branch_rows)
    report = json.loads(result["validation_report"][0])
    assert report["metrics"]["global_unique_pixel_count"] == len(counts)
    assert report["metrics"]["global_duplicate_pixel_rows"] == len(rows)-len(counts)
    from curve_figure_evidence.operation_transforms import bundle_figure_evidence
    normalized = json.loads(bundle_figure_evidence(result)["curve_bundle"][0])
    available = []
    for series in normalized["series"]:
        series_rows = [r for r in rows if r["series_key"] == series["series_key"]]
        if any(r["quantitative_measurement_claim_eligible"] == "1" for r in series_rows):
            assert series["availability"]["status"] == "available"
            assert series["valid_intervals"]
            available.append(series)
        else:
            assert series["availability"]["reason_code"] == "no_quantitative_eligible_rows"
    assert len(available) >= 2


@pytest.mark.parametrize("false_anchor", [False, True])
def test_g3_multiword_visual_binding_survives_ocr_word_splitting(monkeypatch, false_anchor):
    from curve_figure_evidence import figure_detection
    from curve_figure_evidence.figure_science_operations import FIGURE_REQUEST_CONTEXT
    from scidiscovery.operation_contract import SemanticRuleViolation
    raw, _ = measured_source(monkeypatch)
    tokens, _, version = figure_detection._ocr(raw)
    tokens = (*tokens, OCRToken("data", (228, 8, 253, 18), "synthetic adapter"))
    with Image.open(io.BytesIO(raw)) as original:
        image = original.convert("RGB")
    ImageDraw.Draw(image).text((228, 8), "data", fill="red")
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    raw = stream.getvalue()
    monkeypatch.setattr(figure_detection, "_ocr", lambda _: (tokens, (), version))
    detected = detect_source(raw)
    plot = next(p for p in detected.detections[0].plots if all(a.resolved for a in p.axes))
    path = next(p for p in detected.detections[0].paths if p.plot_id == plot.candidate_id)
    intent = {**intent_for(raw), "plot_candidate_id": plot.candidate_id, "unresolved_reasons": [],
        "bindings": [{"candidate_id": path.candidate_id, "visible_label": "Reference data", "semantic_identity": "Reference data observation"}]}
    if false_anchor:
        intent["bindings"][0]["identity_anchor_id"] = "0" * 64
        with pytest.raises(SemanticRuleViolation, match="identity anchor"):
            FIGURE_REQUEST_CONTEXT.implementation(intent, {"paper_source": raw}, {})
        with pytest.raises(ValueError, match="identity anchor"):
            materialize_figure_evidence({"paper_source": (raw,), "figure_intent": (json.dumps(intent).encode(),)})
    else:
        FIGURE_REQUEST_CONTEXT.implementation(intent, {"paper_source": raw}, {})
        result = materialize_figure_evidence({"paper_source": (raw,), "figure_intent": (json.dumps(intent).encode(),)})
        assert len(result["curve_tables"]) == 1
        assert json.loads(result["figure_manifest"][0])["panels"][0]["series"][0]["binding"]["visible_label"] == "Reference data"


@pytest.mark.parametrize("collection", ["source_panels", "audit_overlays", "curve_tables"])
def test_measured_shape_cannot_drop_attachment_or_its_declaration(monkeypatch, collection):
    from curve_figure_evidence.figure_evidence_validation import build_figure_evidence_validation_report
    from curve_figure_evidence.figure_evidence import AutomaticFigureEvidenceManifest
    raw, intent = measured_source(monkeypatch)
    result = materialize_figure_evidence({"paper_source": (raw,), "figure_intent": (json.dumps(intent).encode(),)})
    manifest_raw = result["figure_manifest"][0]
    manifest = json.loads(manifest_raw)
    records = manifest["provenance"]["output_artifacts"]
    positions = {name: 0 for name in ("source_panels", "audit_overlays", "curve_tables")}
    siblings = {}
    for record in records:
        name = record["collection"]
        siblings[record["data_item"]] = (result[name][positions[name]], record["media_type"])
        positions[name] += 1
    victim = next(item for item in records if item["collection"] == collection)
    siblings.pop(victim["data_item"])
    with pytest.raises(ValueError):
        build_figure_evidence_validation_report(manifest_data_item="figure_manifest/evidence.json",
            manifest_content=manifest_raw, sibling_files=siblings)
    records.remove(victim)
    with pytest.raises(ValidationError):
        AutomaticFigureEvidenceManifest.model_validate_json(json.dumps(manifest), strict=True)


@pytest.mark.parametrize("raw", [source_bytes(), b"unrecoverable"], ids=["image", "no_image"])
def test_zero_table_shape_requires_explicit_empty_collections(raw):
    from curve_figure_evidence.figure_evidence import AutomaticFigureEvidenceManifest, AutomaticFigureEvidenceValidationReport
    result = materialize_figure_evidence({"paper_source": (raw,), "figure_intent": (json.dumps(intent_for(raw)).encode(),)})
    manifest = json.loads(result["figure_manifest"][0])
    manifest["provenance"].pop("output_artifacts")
    with pytest.raises(ValidationError):
        AutomaticFigureEvidenceManifest.model_validate_json(json.dumps(manifest), strict=True)
    report = json.loads(result["validation_report"][0])
    report.pop("validated_artifacts")
    with pytest.raises(ValidationError):
        AutomaticFigureEvidenceValidationReport.model_validate_json(json.dumps(report), strict=True)


def test_semantic_selection_order_does_not_break_table_binding(monkeypatch):
    from curve_figure_evidence.operation_transforms import bundle_figure_evidence
    raw, intent = measured_source(monkeypatch, reverse=True)
    intent["bindings"].reverse()
    result = materialize_figure_evidence({"paper_source": (raw,), "figure_intent": (json.dumps(intent).encode(),)})
    normalized = bundle_figure_evidence(result)
    assert json.loads(normalized["curve_bundle"][0])["series"]


@pytest.mark.parametrize("dependency", ["Pillow", "OCR"])
def test_runtime_dependency_identity_is_verified(monkeypatch, dependency):
    from curve_figure_evidence import figure_digitization_contract as contract
    from curve_figure_evidence.figure_digitization_contract import replay_detection
    installed = json.loads(contract.DETECTOR_CONTRACT)
    if dependency == "Pillow":
        installed["pillow_version"] = contract.PILLOW_VERSION
        monkeypatch.setattr("curve_figure_evidence.figure_digitization_contract.PILLOW_VERSION", "different")
    else:
        installed["executables"]["tesseract"] = "/recorded/tesseract"
        installed["ocr"].update(supply_status="verified", version="4.1.1")
        monkeypatch.setattr("curve_figure_evidence.figure_dependencies._tool_version", lambda *_: "different")
    monkeypatch.setattr(contract, "DETECTOR_CONTRACT", json.dumps(installed).encode())
    with pytest.raises(RuntimeError, match="version differs|not been supplied"):
        replay_detection(source_bytes())


def test_page_render_source_has_no_fabricated_pdf_object():
    image = Image.new("RGB", (70, 50), "white")
    output = io.BytesIO()
    image.save(output, format="PDF")
    raw = output.getvalue()
    result = materialize_figure_evidence({"paper_source": (raw,), "figure_intent": (json.dumps(intent_for(raw)).encode(),)})
    request = json.loads(result["figure_request"][0])
    assert request["source"]["source_kind"] == "page_render"
    assert "pdf_object" not in request["source"]
    assert request["source"]["media_box"]
    assert len(request["source"]["transform"]) == 6
