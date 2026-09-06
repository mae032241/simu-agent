"""The existing public figure intent and deterministic resource bindings."""

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from jsonschema.validators import validator_for

from curve_figure_evidence.figure_digitization_contract import (
    FigureExtractionIntent, calibration_from_tick_pairs,
)
from curve_figure_evidence.figure_science_operations import FIGURE_INTENT_SCHEMA, FIGURE_REQUEST_CONTEXT, REQUEST_PROMPT
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.operation_contract import SemanticRuleViolation
from scidiscovery.operation_contract import operation_port_json_schema
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from tests.operations.test_catalog_installed_entrypoint import _DETECTOR_RESOURCE_PROBE
from tests.operations.test_m5_figure_review_closure import (
    CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, FIGURE_PLUGIN,
    _system, _register,
    _envelope,
)


def test_detector_resource_uses_existing_compilation_edges():
    exec(_DETECTOR_RESOURCE_PROBE, {
        "plugins": (CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, FIGURE_PLUGIN),
    })


def _intent():
    from tests.operations.test_figure_role_chain_v2 import intent_for
    return intent_for(b"synthetic source")


def test_public_intent_contains_only_scientific_selections():
    schema = json.loads(FIGURE_INTENT_SCHEMA)
    assert set(schema["properties"]) == {
        "schema_version", "source_sha256", "detector_receipt", "figure", "panel",
        "plot_candidate_id", "bindings", "unresolved_reasons", "rejected_candidates",
    }
    for forbidden in ("pixel_min", "pixel_range", "seeds", "min_points", "min_visible_fraction", "max_gap_px", "declared_gap_ranges", "csv"):
        with pytest.raises(ValidationError):
            FigureExtractionIntent.model_validate_json(canonical_json({**_intent(), forbidden: 1}), strict=True)
    with pytest.raises(SemanticRuleViolation, match="source hash differs"):
        FIGURE_REQUEST_CONTEXT.implementation(_intent(), {"paper_source": b"different"}, {})


@pytest.mark.parametrize("field", [None, "bbox", "seed", "ticks", "coverage", "max_gap", "points", "parameters"])
def test_worker_schema_and_formal_submit_agree_on_intent_structure(tmp_path, field):
    from tests.operations.test_figure_role_chain_v2 import source_bytes, intent_for
    source = source_bytes()
    catalog, runtime, instance, root = _system(tmp_path)
    _register(runtime, instance, name="paper_source", content=source, kind="paper_source",
              schema_id="opaque", media_type="image/png")
    payload = intent_for(source)
    if field:
        payload[field] = {"arbitrary": 1}
    valid = field is None
    compiled = catalog.operation("science.figure.request.prepare.v1")
    schema = operation_port_json_schema(compiled, compiled.spec.outputs[0])
    assert schema["properties"]["panel"]["description"] in REQUEST_PROMPT
    assert {item["type"] for item in schema["properties"]["panel"]["anyOf"]} == {"string", "null"}
    assert "panel" in schema["required"]
    assert validator_for(schema)(schema).is_valid(payload) is valid
    call = {"name": "intent_structure", "operation_id": compiled.spec.operation_id,
            "inputs": [{"port": "paper_source", "artifact_names": ["paper_source"]}],
            "instruction": "Select only the exact figure identity or report unresolved reasons."}
    assert root.call_tool("operation_preflight", call)["admissible"] is True
    root.call_tool("operation_invoke", call)
    worker = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id,
                                 operation_digest=compiled.digest)
    opened = worker.call_tool("worker_open_assignment", {})
    worker_schema = json.loads(Path(opened["workspace_path"], "schema", "result.schema.json").read_text())
    envelope = json.loads(_envelope(payload, verdict="inconclusive"))
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


@pytest.mark.parametrize("defect", ["duplicate_binding", "duplicate_rejection", "same_id_other_text", "selected_rejected"])
def test_g3_worker_exposes_and_enforces_candidate_uniqueness(tmp_path, monkeypatch, defect):
    from tests.operations.test_figure_role_chain_v2 import measured_source
    source, payload = measured_source(monkeypatch)
    if defect == "duplicate_binding":
        payload["bindings"].append(dict(payload["bindings"][0]))
    elif defect == "duplicate_rejection":
        rejected = payload["bindings"].pop()
        payload["rejected_candidates"] = [{"candidate_id": rejected["candidate_id"], "reason": "Not relevant"}] * 2
    elif defect == "same_id_other_text":
        payload["bindings"].append({**payload["bindings"][0], "visible_label": "Different visible words"})
    else:
        payload["rejected_candidates"] = [{"candidate_id": payload["bindings"][0]["candidate_id"], "reason": "Not relevant"}]
    catalog, runtime, instance, root = _system(tmp_path)
    _register(runtime, instance, name="paper_source", content=source, kind="paper_source", schema_id="opaque", media_type="image/png")
    compiled = catalog.operation("science.figure.request.prepare.v1")
    call = {"name": "unique_candidates", "operation_id": compiled.spec.operation_id,
        "inputs": [{"port": "paper_source", "artifact_names": ["paper_source"]}],
        "instruction": "Select disjoint candidate identities from the bound source."}
    assert root.call_tool("operation_preflight", call)["admissible"]
    root.call_tool("operation_invoke", call)
    worker = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    opened = worker.call_tool("worker_open_assignment", {})
    schema = json.loads(Path(opened["workspace_path"], "schema", "result.schema.json").read_text())
    envelope = json.loads(_envelope(payload))
    structural = defect in {"duplicate_binding", "duplicate_rejection"}
    assert validator_for(schema)(schema).is_valid(envelope) is not structural
    if not structural:
        rules = schema["properties"]["payload"]["x-scidiscovery-semantic-constraints"]["rules"]
        rule = next(r for r in rules if r["rule_id"] == "curve.figure.request.internal_consistency")
        assert "candidate_id" in rule["description"] and "disjoint" in rule["description"]
    Path(opened["output_directory"], "result.json").write_bytes(canonical_json(envelope))
    rejected = worker.call_tool("worker_submit_result", {})
    assert rejected["state"] == "rejected"
    assert {d["rule_id"] for d in rejected["diagnostics"]} == {
        "runtime.schema" if structural else "curve.figure.request.internal_consistency"}
