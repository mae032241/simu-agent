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
    count = 0
    for name in catalog.operation_ids():
        spec = catalog.operation(name).spec
        ports = [port for port in spec.inputs if port.name == "user_context"]
        if spec.executor.kind != "agent" or spec.catalog_scope != "public":
            assert ports == []
            continue
        count += 1
        assert len(ports) == 1
        port = ports[0]
        assert (port.min_items, port.max_items, port.max_item_bytes) == (0, 4, 32768)
        assert (port.usage, port.exposure, port.schema_id) == ("prior_signal", "on_demand", "opaque")
        assert port.codec.plugin_id == port.schema_resource.plugin_id == "general_science"
        assert port.codec.component_id == "opaque_codec"
        for output in spec.outputs:
            assert ("user_context" in output.context_sources) == (output.context_validator is not None)
    assert count == 25


def _revision_cohort(tmp_path, *, audit_note):
    """Real control lifecycle and fixture UI approval; no admission/signal stubs."""
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN))
    runtime, instance, root = _root(tmp_path, catalog=catalog)
    _register(runtime, instance, name="source", raw=b"Frozen fixture source.",
              kind="source", schema="opaque", media_type="text/plain")
    root.call_tool("artifact_ingest_text", {"name": "note", "text": "这是一条待判断的建议；保留原始证据。\r\n"})
    payload = json.loads(_intake().canonical_json().replace(b'"paper"', b'"source_material"'))
    payload["scientific_foundation"]["objective_contract"] = {
        "objective_key": "global_objective", "intent": "mechanism_discrimination",
        "statement": payload["scientific_foundation"]["objective"],
        "closure_requirements": [{"requirement_key": "comparison", "description": "One finite comparison.",
                                  "requirement_type": "comparison_present", "comparison_purposes": ["mechanism_separation"]}],
    }
    intake = _complete(runtime, root, "extraction", "science.evidence.extract.v1",
        {"source_material": "source"}, payload)
    audit_inputs = {"scientific_intake": intake, "source_material": "source"}
    if audit_note:
        audit_inputs["user_context"] = "note"
    audit = _complete(runtime, root, "audit", "science.evidence.audit.intake.v1", audit_inputs,
        {"checks": [{"check_key": "trace", "subject": "Frozen source", "status": "pass",
                     "basis": "Exact source; the optional suggestion does not change it.", "evidence_keys": ["source_material"]}]})
    split = root.call_tool("operation_invoke", {"name": "split", "operation_id": "science.intake.split.v1", "inputs": [
        {"port": "scientific_intake", "artifact_names": [intake]}, {"port": "evidence_audit", "artifact_names": [audit]}]})
    split_names = {item["output_label"]: item["artifact_name"] for item in split["result"]["outputs"]}
    foundation = split_names["scientific_foundation"]
    root.call_tool("operation_invoke", {"name": "qualification", "operation_id": "science.evidence.qualify.v1", "inputs": [
        {"port": "scientific_foundation", "artifact_names": [foundation]},
        {"port": "extraction_primary", "artifact_names": [intake]},
        {"port": "evidence_audit", "artifact_names": [audit]},
        {"port": "frozen_sources", "artifact_names": ["source"]}]})
    approval_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace="approval", name="qualification")
    launch = runtime.approvals.status(approval_id)
    token = parse_qs(urlparse(launch.review_path).query)["token"][0]
    view = runtime.approvals.review(approval_id, access_token=token)
    runtime.approvals.record_ui_decision(approval_id=approval_id, access_token=token,
        csrf_token=view.csrf_token, decision_nonce=view.decision_nonce, selected_option="approve", rationale="",
        decided_by=LocalIdentityRef(identity_id="fixture_reviewer", display_name="Fixture UI reviewer"),
        ui_session_id="user_context_test")
    hypothesis = _proposal(hypothesis_keys=("hypothesis_a",))
    # This alias belongs to the foundation, not to a hypothesis input port.
    hypothesis["hypotheses"][0]["evidence_keys"] = ["source_material"]
    proposal = _complete(runtime, root, "hypotheses", "science.hypothesis.propose.v1",
        {"problem_frame": split_names["primary"], "scientific_foundation": foundation}, hypothesis)
    critic = _complete(runtime, root, "critic", "science.hypothesis.criticize.v1",
        {"hypothesis_portfolio": proposal, "scientific_foundation": foundation},
        _critic(disposition="revise_evidence").model_dump(mode="json"), verdict="inconclusive")
    request = {"name": "evidence_revision", "operation_id": "science.evidence.revise-from-critic.v1", "inputs": [
        {"port": "prior_draft", "artifact_names": [intake]},
        {"port": "intake_audit", "artifact_names": [audit]},
        {"port": "scientific_foundation", "artifact_names": [foundation]},
        {"port": "hypothesis_portfolio", "artifact_names": [proposal]},
        {"port": "change_request", "artifact_names": [critic]},
        {"port": "source_material", "artifact_names": ["source"]}],
        "instruction": "Revise the bounded factual gap in the exact original evidence."}
    return runtime, instance, root, request, audit


@pytest.mark.parametrize("audit_note", (False, True))
def test_root_preflight_and_schedule_preserve_exact_sources_with_audit_background(tmp_path, monkeypatch, audit_note):
    runtime, instance, root, request, audit = _revision_cohort(tmp_path, audit_note=audit_note)
    before = root.call_tool("operation_preflight", request)
    assert before["admissible"], before
    result = root.call_tool("operation_invoke", request)
    assert result["result"]["state"] == "queued", result
    saved = runtime.runs.status(runtime.scheduler_bindings.resolve(
        instance=instance.instance_id, namespace="run", name=request["name"]))
    assert [item.artifact_name for item in saved.inputs if item.port_name == "source_material"] == ["source"]
    audit_artifact = _artifact(runtime, instance, audit)
    family = root.facade._run_output_family(audit_artifact)
    assert family.producer_inputs == tuple((item.port_name, item.artifact_ref)
        for item in runtime.runs.completed_for_output(audit_artifact.ref).inputs)
    assert all(source.ref != _artifact(runtime, instance, "note").ref for source in family.evidence_sources)
    assert (_artifact(runtime, instance, "note").ref in audit_artifact.parent_refs) == audit_note
    _register(runtime, instance, name="replacement", raw=b"Other source.", kind="source", schema="opaque", media_type="text/plain")
    for sources in ([], ["replacement"]):
        bad = {**request, "name": "bad_source", "inputs": [
            {**item, "artifact_names": sources} if item["port"] == "source_material" else item for item in request["inputs"]]}
        assert not root.call_tool("operation_preflight", bad)["admissible"]
    query = runtime.runs.completed_for_output
    monkeypatch.setattr(runtime.runs, "completed_for_output", lambda ref: None if ref == audit_artifact.ref else query(ref))
    missing = root.call_tool("operation_preflight", {**request, "name": "missing_producer"})
    assert missing["reason_code"] == "input_producer_metadata_unavailable", missing
    assert "intake_audit" in json.dumps(missing)


def test_background_reference_is_not_a_formal_parameter_source(tmp_path):
    from pathlib import Path
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from tests.operations.test_m2_parameter_package import _root as parameter_root, _package, _envelope
    catalog, runtime, instance, root = parameter_root(tmp_path)
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
    item, = [item for item in assignment["inputs"] if item["port"] == "user_context"]
    assert Path(new_opened["workspace_path"], item["relative_path"]).read_text().startswith("Continue from")
    write_analysis(new_opened, analysis_report())
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    assert root.call_tool("run_status", {"name": "analysis"})["state"] == "failed"
