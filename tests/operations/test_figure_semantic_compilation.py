"""One public semantic contract and one source-bound deterministic compiler."""

import csv
import hashlib
import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError
from jsonschema.validators import validator_for

from curve_score.figure_digitization_contract import (
    FigureExtractionIntent, calibration_from_tick_pairs,
)
from curve_score.figure_science_operations import FIGURE_INTENT_SCHEMA, FIGURE_REQUEST_CONTEXT, REQUEST_PROMPT
from curve_score.operation_transforms import materialize_figure_evidence
from ingaas_fig4.figure_compilation import GEOMETRY, OPERATION, compile_figure_request
from ingaas_fig4.plugin import PLUGIN as FIG4_PLUGIN
from tcad_artifact.plugin import PLUGIN as TCAD_PLUGIN
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.operation_contract import SemanticRuleViolation
from scidiscovery.operation_contract import operation_port_json_schema
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.operations.catalog import compile_catalog
from tests.operations.test_catalog_installed_entrypoint import _DETECTOR_RESOURCE_PROBE
from tests.operations.test_m5_figure_review_closure import (
    CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, FIGURE_PLUGIN,
    _system, _register, _complete_agent,
    _envelope,
)


def test_detector_resource_uses_existing_compilation_edges():
    exec(_DETECTOR_RESOURCE_PROBE, {
        "plugins": (CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, FIGURE_PLUGIN),
    })


def _intent():
    geometry = json.loads(GEOMETRY)
    return {
        "schema_version": "scidiscovery.figure-extraction-intent.v1",
        "source_sha256": geometry["source_sha256"], "figure": "Fig. 4",
        "panel": None, "series_labels": ["In0.83Al0.17As", "In0.83Ga0.17As"],
    }


@pytest.fixture
def frozen_source():
    path = os.environ.get("SCID_FIG4_FROZEN_SOURCE")
    if not path:
        pytest.skip("set SCID_FIG4_FROZEN_SOURCE to run the exact frozen-PDF replay")
    return Path(path).read_bytes()


def test_public_intent_contains_only_scientific_selections():
    schema = json.loads(FIGURE_INTENT_SCHEMA)
    assert set(schema["properties"]) == {
        "schema_version", "source_sha256", "figure", "panel", "series_labels", "unresolved_reasons",
    }
    for forbidden in ("pixel_min", "pixel_range", "seeds", "min_points", "min_visible_fraction", "max_gap_px", "declared_gap_ranges", "csv"):
        with pytest.raises(ValidationError):
            FigureExtractionIntent.model_validate_json(canonical_json({**_intent(), forbidden: 1}), strict=True)
    with pytest.raises(SemanticRuleViolation, match="source hash differs"):
        FIGURE_REQUEST_CONTEXT.implementation(_intent(), {"paper_source": b"different"}, {})


@pytest.mark.parametrize(
    ("labels", "reasons", "valid"),
    [
        (["Reference", "Reference"], [], False),
        ([], [], False),
        (["Reference"], ["Identity unclear"], False),
        (["Reference"], [], True),
        ([], ["Identity unclear"], True),
    ],
    ids=("duplicates", "both_empty", "both_nonempty", "selected", "unresolved"),
)
def test_worker_schema_and_formal_submit_agree_on_intent_structure(tmp_path, labels, reasons, valid):
    from tests.operations.test_curve_figure_digitization_tool import _valid_source

    source = _valid_source()
    catalog, runtime, instance, root = _system(tmp_path)
    _register(runtime, instance, name="paper_source", content=source, kind="paper_source",
              schema_id="opaque", media_type="image/png")
    payload = {**_intent(), "source_sha256": hashlib.sha256(source).hexdigest(),
               "series_labels": labels, "unresolved_reasons": reasons}
    compiled = catalog.operation("science.figure.request.prepare.v1")
    schema = operation_port_json_schema(compiled, compiled.spec.outputs[0])
    assert schema["properties"]["panel"]["description"] in REQUEST_PROMPT
    assert {item["type"] for item in schema["properties"]["panel"]["anyOf"]} == {"string", "null"}
    assert "panel" in schema["required"]
    validator = validator_for(schema)(schema)
    assert validator.is_valid(payload) is valid
    call = {"name": "intent_structure", "operation_id": compiled.spec.operation_id,
            "inputs": [{"port": "paper_source", "artifact_names": ["paper_source"]}],
            "instruction": "Select only the exact figure identity or report unresolved reasons."}
    assert root.call_tool("operation_preflight", call)["admissible"] is True
    root.call_tool("operation_invoke", call)
    worker = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id,
                                 operation_digest=compiled.digest)
    opened = worker.call_tool("worker_open_assignment", {})
    worker_schema = json.loads(Path(opened["workspace_path"], "schema", "result.schema.json").read_text())
    envelope = json.loads(_envelope(payload, verdict="pass" if labels else "inconclusive"))
    assert validator_for(worker_schema)(worker_schema).is_valid(envelope) is valid
    Path(opened["output_directory"], "result.json").write_bytes(canonical_json(envelope))
    submitted = worker.call_tool("worker_submit_result", {})
    assert submitted["state"] == ("completed" if valid else "rejected"), submitted


@pytest.mark.parametrize("ticks", [((36.0, 1e20), (685.0, 1e15)), ((685.0, 1e15), (36.0, 1e20))])
def test_tick_normalization_preserves_pixel_value_pairs(ticks):
    axis = calibration_from_tick_pairs(scale="log10", unit="cm^-3", ticks=ticks, uncertainty_px=1.0)
    assert (axis.pixel_min, axis.value_min) == (685.0, 1e15)
    assert (axis.pixel_max, axis.value_max) == (36.0, 1e20)


@pytest.mark.parametrize("ticks", [((1.0, 1.0), (1.0, 2.0)), ((1.0, 0.0), (2.0, 2.0)), ((float("nan"), 1.0), (2.0, 2.0))])
def test_invalid_tick_pairs_fail_closed(ticks):
    with pytest.raises(ValidationError):
        calibration_from_tick_pairs(scale="log10", unit="cm^-3", ticks=ticks, uncertainty_px=1.0)


def test_domain_compiler_is_registered_only_as_support():
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, FIGURE_PLUGIN, TCAD_PLUGIN, FIG4_PLUGIN))
    compiled = catalog.operation(OPERATION.operation_id)
    assert compiled.spec.catalog_scope == "support"
    assert compiled.plugin_id == "ingaas_fig4"
    assert compiled.spec.executor.kind == "transform"
    assert [port.name for port in compiled.spec.outputs] == ["figure_request"]
    request = catalog.operation("science.figure.request.prepare.v1")
    assert [port.name for port in request.spec.outputs] == ["figure_intent"]
    assert request.spec.outputs[0].schema_id == "scidiscovery.figure-extraction-intent.v1"


def test_compiler_rejects_unbound_source_before_image_recovery():
    with pytest.raises(ValueError, match="frozen source"):
        compile_figure_request({"paper_source": (b"wrong",), "figure_intent": (canonical_json(_intent()),)})


@pytest.mark.parametrize("panel", ["a", "single panel (no panel label)"])
def test_compiler_rejects_unsupported_panel_but_legacy_intent_is_readable(frozen_source, panel):
    intent = canonical_json({**_intent(), "panel": panel})
    assert FigureExtractionIntent.model_validate_json(intent, strict=True).panel == panel
    with pytest.raises(ValueError, match="figure/panel selection"):
        compile_figure_request({"paper_source": (frozen_source,), "figure_intent": (intent,)})


def test_frozen_source_compiles_and_marks_detection_limit_locally(frozen_source):
    intent = _intent()
    inputs = {"paper_source": (frozen_source,), "figure_intent": (canonical_json(intent),)}
    request = compile_figure_request(inputs)["figure_request"]
    assert compile_figure_request(inputs)["figure_request"] == request
    payload = json.loads(request[0])
    assert payload["axis_calibration"]["y"]["pixel_min"] > payload["axis_calibration"]["y"]["pixel_max"]
    outputs = materialize_figure_evidence({"paper_source": (frozen_source,), "figure_request": request})
    rows = [row for raw in outputs["curve_tables"] for row in csv.DictReader(raw.decode().splitlines())]
    low = [row for row in rows if float(row["y_value"]) < 3e15]
    assert low and all(row["below_sims_detection_limit"] == "1" and row["quantitative_measurement_claim_eligible"] == "0" for row in low)
    for key in {row["series_key"] for row in rows}:
        assert any(row["series_key"] == key and row["quantitative_measurement_claim_eligible"] == "1" for row in rows)
    assert len(outputs["curve_tables"]) == 2
    assert outputs["audit_overlays"][0].startswith(b"\x89PNG")
    for bad in ({**intent, "figure": "Fig. 5"}, {**intent, "series_labels": ["unknown"]}):
        with pytest.raises(ValueError, match="does not support"):
            compile_figure_request({"paper_source": (frozen_source,), "figure_intent": (canonical_json(bad),)})


@pytest.mark.parametrize("panel", [None, "whole figure"], ids=["unlabelled", "legacy_canonical"])
def test_semantic_agent_and_compiler_preserve_exact_parent_chain(tmp_path, frozen_source, panel):
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, FIGURE_PLUGIN, TCAD_PLUGIN, FIG4_PLUGIN))
    _, runtime, instance, root = _system(tmp_path, catalog=catalog)
    source = _register(runtime, instance, name="paper_source", content=frozen_source,
                       kind="paper_source", schema_id="opaque", media_type="application/pdf")
    intent_name = _complete_agent(catalog, runtime, root, operation_id="science.figure.request.prepare.v1",
                                  name="figure_selection", inputs=[{"port": "paper_source", "artifact_names": ["paper_source"]}], payload={**_intent(), "panel": panel})
    call = {"name": "compiled_figure_geometry", "operation_id": OPERATION.operation_id,
            "inputs": [{"port": "paper_source", "artifact_names": ["paper_source"]},
                       {"port": "figure_intent", "artifact_names": [intent_name]}]}
    assert root.call_tool("operation_preflight", call)["admissible"] is True
    output = root.call_tool("operation_invoke", call)["result"]["outputs"][0]
    artifact = runtime.artifacts.get_by_id(runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace="artifact", name=output["artifact_name"]))
    intent_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace="artifact", name=intent_name)
    intent_artifact = runtime.artifacts.get_by_id(intent_id)
    assert intent_artifact.parent_refs == (source.ref,)
    assert artifact.parent_refs == (source.ref, intent_artifact.ref)
    materialized = root.call_tool("operation_invoke", {"name": "measured_figure", "operation_id": "science.figure.evidence.materialize.v1",
        "inputs": [{"port": "paper_source", "artifact_names": ["paper_source"]}, {"port": "figure_request", "artifact_names": [output["artifact_name"]]}]})
    for item in materialized["result"]["outputs"]:
        child = runtime.artifacts.get_by_id(runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace="artifact", name=item["artifact_name"]))
        assert child.parent_refs == (source.ref, artifact.ref)
