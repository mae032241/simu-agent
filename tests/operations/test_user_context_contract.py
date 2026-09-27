"""User background remains readable without becoming a formal evidence source."""
from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import pytest

from scidiscovery.artifact_agent.schema.approval import LocalIdentityRef
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from tests.operations.test_general_transform_operations import _root, _register, _intake
from tests.operations.test_historical_compatibility_paths import _artifact, _complete
from tests.operations.test_hypothesis_objective_boundary import _proposal
from tests.operations.test_hypothesis_review_routing import _critic


def test_user_context_is_declared_only_on_public_agents():
    from curve_score.plugin import PLUGIN as CURVE
    from curve_figure_evidence.plugin import PLUGIN as FIGURE
    from tcad_artifact.plugin import PLUGIN as TCAD
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE, FIGURE, TCAD))
    for name in catalog.operation_ids():
        spec = catalog.operation(name).spec
        ports = [port for port in spec.inputs if port.name == "user_context"]
        if spec.executor.kind != "agent" or spec.catalog_scope != "public":
            assert ports == []
            continue
        assert len(ports) == 1
        port = ports[0]
        assert (port.min_items, port.max_items, port.max_item_bytes) == (0, 4, 32768)
        assert (port.usage, port.exposure, port.schema_id) == ("prior_signal", "on_demand", "opaque")
        assert port.codec.plugin_id == port.schema_resource.plugin_id == "general_science"
        assert port.codec.component_id == "opaque_codec"
        for output in spec.outputs:
            assert ("user_context" in output.context_sources) == (output.context_validator is not None)


def test_background_reference_is_not_a_formal_parameter_source(tmp_path):
    from pathlib import Path
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from tests.operations.test_m2_parameter_package import _package
    from curve_score.plugin import PLUGIN as curve
    from tcad_artifact.plugin import PLUGIN as tcad
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, curve, tcad))
    runtime, instance, root = _root(tmp_path, catalog=catalog)
    def _envelope(payload):
        return canonical_json(dict(schema_version=1,payload=payload,handoff=dict(verdict='pass',summary='Bounded parameter fixture.')))
    root.call_tool("artifact_ingest_text", {"name": "source", "text": "scale=1"})
    root.call_tool("artifact_ingest_text", {"name": "note", "text": "A user suggestion to assess."})
    root.call_tool("operation_invoke", {"name": "extract", "operation_id": "tcad.parameter.evidence.extract.v1", "instruction": "Extract the bound fixture parameter.",
        "inputs": [{"port": "source_material", "artifact_names": ["source"]},
                   {"port": "user_context", "artifact_names": ["note"]}]})
    compiled = catalog.operation("tcad.parameter.evidence.extract.v1")
    worker = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    opened = worker.call_tool("worker_open_assignment", {})
    output = Path(opened["output_directory"], "result.json")
    output.write_bytes(_envelope(_package("user_context").model_dump(mode="json")))
    rejected = worker.call_tool("worker_submit_result", {})
    assert rejected["state"] == "rejected", rejected
    assert any("source_catalog.sources[0].source_key" in item["path"] for item in rejected["diagnostics"]), rejected
    payload = _package("source_material").model_dump(mode="json")
    payload["scientific_intake"]["scientific_foundation"]["evidence"].append({
        "source_key": "user_context", "source_type": "user_statement", "title": "User background", "locator": "Original note"})
    output.write_bytes(_envelope(payload))
    completed = worker.call_tool("worker_submit_result", {})
    assert completed["state"] == "completed", completed


def test_four_progress_records_and_four_maximum_texts_fit_without_eviction(tmp_path):
    from tests.operations.test_tcad_result_analysis import analysis_system
    _, runtime, root, request, _, _ = analysis_system(tmp_path)
    for i in range(4):
        root.call_tool("artifact_ingest_text", {"name": f"progress{i}", "text": "Saved progress."})
        root.call_tool("artifact_ingest_text", {"name": f"note{i}", "text": chr(0x10000 + i) * 8192})
    request["inputs"].extend([
        {"port": "current_progress", "artifact_names": [f"progress{i}" for i in range(4)]},
        {"port": "user_context", "artifact_names": [f"note{i}" for i in range(4)]}])
    checked = root.call_tool("operation_preflight", request)
    assert checked["admissible"], checked
    assert root.call_tool("operation_invoke", request)["result"]["state"] == "queued"
    saved = runtime.runs.list(instance_id=root.facade.instance)[0]
    assert len([item for item in saved.inputs if item.port_name == "current_progress"]) == 4
    notes = [item for item in saved.inputs if item.port_name == "user_context"]
    assert len(notes) == 4
    assert sum(len(runtime.artifacts.read(item.artifact_ref)) for item in notes) == 131072
    root.call_tool("artifact_ingest_text", {"name": "overflow", "text": "Fifth note"})
    bad = {**request, "name": "overflow", "inputs": [
        {**item, "artifact_names": [*item["artifact_names"], "overflow"]}
        if item["port"] == "user_context" else item for item in request["inputs"]]}
    refused = root.call_tool("operation_preflight", bad)
    assert not refused["admissible"] and refused["port"] == "user_context", refused
    assert "0..4 items; received 5" in json.dumps(refused)


def test_added_text_uses_draft_recovery_and_cannot_change_strict_resume(tmp_path):
    from copy import deepcopy
    from pathlib import Path
    from tests.operations.test_tcad_result_analysis import analysis_system, open_analysis, analysis_report, write_analysis
    system = analysis_system(tmp_path)
    _, runtime, root, request, _, _ = system
    request["max_attempts"] = 2
    worker, opened = open_analysis(system)
    scratch = Path(opened["workspace_path"], "scratch", "saved.json")
    scratch.write_text('{"fixture_value":3}')
    status = runtime.runs.status(worker._run_id)
    runtime.runs.record_failure(status.run_id, reason="fixture interruption", expected_state=status.state,
        expected_last_activity_at=status.last_activity_at)
    unchanged = {**deepcopy(request), "name": "unchanged", "resume_from": "analysis"}
    assert root.call_tool("operation_preflight", unchanged)["admissible"]
    root.call_tool("artifact_ingest_text", {"name": "note", "text": "Continue from the saved calculation; assess this suggestion."})
    changed = deepcopy(unchanged)
    changed["inputs"].append({"port": "user_context", "artifact_names": ["note"]})
    refused = root.call_tool("operation_preflight", changed)
    assert not refused["admissible"] and refused["reason_code"] == "recovery_source_unavailable", refused
    changed.pop("resume_from")
    changed.update(name="continued", draft_from="analysis")
    checked = root.call_tool("operation_preflight", changed)
    assert checked["admissible"], checked
    root.call_tool("operation_invoke", changed)
    new_opened = worker.call_tool("worker_open_assignment", {})
    assignment = json.loads(Path(new_opened["assignment_path"]).read_bytes())
    original = Path(new_opened["workspace_path"], assignment["recovery_draft"]["relative_path"], "scratch", "saved.json")
    assert original.read_bytes() == scratch.read_bytes()
    item, = [item for item in assignment["inputs"] if item["source_name"].startswith("user_context")]
    assert Path(new_opened["workspace_path"], item["relative_path"]).read_text().startswith("Continue from")
    write_analysis(new_opened, analysis_report())
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    assert root.call_tool("run_status", {"name": "analysis"})["state"] == "failed"
