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
    FIGURE_REQUEST_SCHEMA,
    AUTHOR_PROMPT,
)
from curve_figure_evidence.figure_source import inspect_figure_source_bytes
from curve_figure_evidence.plugin import PLUGIN as FIGURE_PLUGIN
from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
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
    assert "[pixel_coordinate, tick_value]" in AUTHOR_PROMPT


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


def test_compiled_author_exposes_inspection_preview_and_explicit_save() -> None:
    catalog = compile_catalog(
        (CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, FIGURE_PLUGIN)
    )
    operation = catalog.operation("science.evidence.extract.figure.v3")
    assert operation.spec.outputs[0].schema_id == (
        "scidiscovery.scientific-intake.v1"
    )
    assert {tool.name for tool in operation_worker_tools(operation)} >= {
        "worker_curve_figure_inspect_source",
        "worker_curve_figure_preview",
        "worker_curve_figure_save",
    }
    source, request = _source_and_request()
    FigureDigitizationRequest.model_validate_json(canonical_json(request), strict=True)


def _saved_family(tmp_path, *, unresolved=False, partial_alias_recovery=False):
    """Use real domain tools/algorithm with a bounded in-memory control receipt store."""
    from types import SimpleNamespace
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    from scidiscovery.artifact_agent.schema.tool_evidence import ToolEvidenceManifest
    from curve_figure_evidence.figure_worker_tool import FigureDigitizationPreviewInput, _preview, _save
    source, request = _source_and_request()
    if unresolved:
        request.update(request_status="unresolved", unresolved_reasons=["Calibration cannot be established visibly."])
    source_ref = ArtifactRef(artifact_id="original", sha256=hashlib.sha256(source).hexdigest(), kind="paper", schema_id="opaque")
    records, contents, attempts = [], {}, []
    active = {"tool": "worker_curve_figure_preview", "source": "paper_source", "interrupt": partial_alias_recovery}
    def accept(*, raw, media_type, metadata, derived_from):
        assert derived_from == (active["source"],)
        metadata = {**metadata, "derived_from": list(derived_from)}
        # Mirror production identity, including aliases in metadata. Do not hide
        # alias-change duplication by deduplicating only on data_item.
        key = hashlib.sha256(canonical_json({"sha256": hashlib.sha256(raw).hexdigest(),
            "metadata": metadata, "source": source_ref.model_dump(mode="json")})).hexdigest()
        for record in records:
            prior_key = hashlib.sha256(canonical_json({"sha256": record["artifact_ref"]["sha256"],
                "metadata": record["metadata"], "source": record["source_ref"]})).hexdigest()
            if key == prior_key:
                return record
        if active["interrupt"] and len(records) == 2:
            active["interrupt"] = False
            raise RuntimeError("interrupted partial save")
        ref = ArtifactRef(artifact_id=f"file_{len(records)}", sha256=hashlib.sha256(raw).hexdigest(), kind="figure_evidence_file", schema_id="opaque")
        record = {"alias": f"tool_evidence_{len(records)+1:03d}", "artifact_ref": ref.model_dump(mode="json"),
            "source_ref": source_ref.model_dump(mode="json"), "media_type": media_type, "size_bytes": len(raw),
            "metadata": metadata, "tool_name": "worker_curve_figure_save"}
        records.append(record); contents[ref] = raw
        return record
    def finish(**values):
        attempts.append({"tool_name": active["tool"], "state": "completed", "result_status": values["result_status"]})
    context = SimpleNamespace(workspace=tmp_path, read_input=lambda name: source,
        input_ref=lambda name: source_ref, record_activity=lambda activity: None,
        evidence=lambda: records, tool_attempts=lambda: attempts, accept_evidence=accept,
        read_evidence=lambda alias: contents[ArtifactRef.model_validate(next(r for r in records if r["alias"] == alias)["artifact_ref"])],
        source_descriptor=lambda name: SimpleNamespace(port_name="paper_source"),
        finish_attempt=finish)
    request["source"] = {key: value for key, value in request["source"].items()
        if key not in {"source_sha256", "recovered_image_sha256", "recovery_tool", "recovery_tool_version"}}
    draft = FigureDigitizationPreviewInput.model_validate_json(canonical_json({"request": request}))
    if not unresolved:
        with pytest.raises(ValueError, match="preview"):
            _save(draft, context)
        _preview(draft, context)
    active["tool"] = "worker_curve_figure_save"
    if partial_alias_recovery:
        with pytest.raises(RuntimeError, match="partial save"):
            _save(draft, context)
        adopted = tuple(records)
        active["source"] = "renamed_original"
        draft = draft.model_copy(update={"name": active["source"]})
        active["tool"] = "worker_curve_figure_preview"
        _preview(draft, context)
        active["tool"] = "worker_curve_figure_save"
    result = _save(draft, context)
    if partial_alias_recovery:
        assert tuple(records[:len(adopted)]) == adopted
        assert len({r["metadata"]["data_item"] for r in records}) == len(records)
    assert result["selected_material"] == records[-1]["alias"]
    before = len(records)
    _save(draft, context)
    assert len(records) == before
    return ToolEvidenceManifest(records=tuple(records)), contents, source_ref


def test_author_saves_complete_selected_family_and_bundle_consumes_it(tmp_path):
    from curve_figure_evidence.figure_family import selected_family_files
    from curve_figure_evidence.operation_transforms import bundle_selected_figure
    proof, contents, source = _saved_family(tmp_path)
    files = selected_family_files(proof.records, contents, source)
    assert "figure_request/request.json" in files
    assert len([name for name in files if name.startswith("audit_overlays/")]) == 2
    result = bundle_selected_figure({"figure_provenance": (canonical_json(proof),), "figure_family": tuple(contents.values())})
    assert result["curve_bundle"]


@pytest.mark.parametrize("defect", ["missing", "extra", "tampered", "wrong_source", "unselected", "wrong_tool"])
def test_selected_family_rejects_identity_and_completeness_defects(tmp_path, defect):
    from curve_figure_evidence.figure_family import selected_family_files
    proof, contents, source = _saved_family(tmp_path)
    if defect == "missing":
        contents.pop(next(iter(contents)))
    elif defect == "extra":
        contents[source] = b"not a selected member"
    elif defect == "tampered":
        contents[next(iter(contents))] = b"changed"
    elif defect == "wrong_source":
        source = source.model_copy(update={"artifact_id": "another_original"})
    elif defect == "unselected":
        selected = proof.records[-1]
        contents.pop(next(ref for ref in contents if ref.artifact_id == selected["artifact_ref"]["artifact_id"]))
        proof = proof.model_copy(update={"records": proof.records[:-1]})
    else:
        proof = proof.model_copy(update={"records": ({**proof.records[0], "tool_name": "other_tool"}, *proof.records[1:])})
    with pytest.raises(ValueError):
        selected_family_files(proof.records, contents, source)


def test_unresolved_selection_retains_limits_without_quantitative_bundle(tmp_path):
    from curve_figure_evidence.figure_family import selected_family_files
    from curve_figure_evidence.operation_transforms import bundle_selected_figure
    proof, contents, source = _saved_family(tmp_path, unresolved=True)
    assert set(selected_family_files(proof.records, contents, source)) == {"figure_request/request.json"}
    with pytest.raises(ValueError, match="quantitative"):
        bundle_selected_figure({"figure_provenance": (canonical_json(proof),), "figure_family": tuple(contents.values())})


def test_partial_save_recovery_reuses_exact_members_despite_source_alias_change(tmp_path):
    from curve_figure_evidence.figure_family import selected_family_files
    proof, contents, source = _saved_family(tmp_path, partial_alias_recovery=True)
    assert selected_family_files(proof.records, contents, source)
    assert proof.records[0]["metadata"]["derived_from"] == ("paper_source",)
    assert proof.records[-1]["metadata"]["derived_from"] == ("renamed_original",)


def test_wording_revision_reuses_prior_family_without_digitization(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    from scidiscovery.operations.input_validation import InputBindingDescriptor
    from curve_figure_evidence import figure_worker_tool as tool
    proof, contents, source = _saved_family(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError("wording-only revision must not redigitize")
    monkeypatch.setattr(tool, "build_digitized_figure_bundle", forbidden)
    source_raw, _ = _source_and_request()
    raw = {"paper_source": source_raw, "figure_provenance": canonical_json(proof)}
    proof_ref = ArtifactRef(artifact_id="prior_proof", sha256=hashlib.sha256(raw["figure_provenance"]).hexdigest(),
        kind="tool_evidence_manifest", schema_id="scidiscovery.tool-evidence-manifest.v1")
    refs = {"paper_source": source, "figure_provenance": proof_ref}
    for index, (ref, content) in enumerate(contents.items()):
        alias = f"prior_file_{index}"
        raw[alias], refs[alias] = content, ref
    descriptors = {name: InputBindingDescriptor(source_name=name,
        port_name="figure_family" if name.startswith("prior_file_") else name,
        artifact_ref=ref, media_type="application/json", size_bytes=len(raw[name]), sha256=ref.sha256)
        for name, ref in refs.items()}
    adopted = []
    def adopt(alias):
        assert alias == "figure_provenance"
        adopted.extend(proof.records)
        return proof.records
    context = SimpleNamespace(source_descriptor=descriptors.__getitem__, read_input=raw.__getitem__,
        input_names_for_port=lambda port: tuple(name for name, descriptor in descriptors.items() if descriptor.port_name == port),
        input_path=lambda name: tmp_path / name, evidence=lambda: [], adopt_bound_evidence=adopt,
        finish_attempt=lambda **values: None)
    result = tool._reuse(tool.FigureFamilyReuseInput(), context)
    assert result["reused"] is True
    assert tuple(adopted) == proof.records
    assert {item["alias"] for item in result["files"]} == {record["alias"] for record in proof.records}
