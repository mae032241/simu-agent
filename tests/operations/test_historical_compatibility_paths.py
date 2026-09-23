"""Cross-generation continuation without inheriting review or execution authority."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from tests.operations.test_agent_contract_alignment import _feedback_root, experiment_case


def _artifact(runtime, instance, name):
    return runtime.artifacts.get_by_id(runtime.scheduler_bindings.resolve(
        instance=instance.instance_id, namespace="artifact", name=name))


def _historical(runtime, instance, name, original, producer_id, port):
    producer = runtime.runs.operation_catalog.operation(producer_id)
    output = next(item for item in producer.spec.outputs if item.name == port)
    artifact = runtime.artifacts.register(runtime.artifacts.read(original.ref), ArtifactRegistration(
        kind=output.kind, schema_id=output.schema_id, payload_schema_version=1,
        media_type=original.media_type, creator=runtime.actor, parent_refs=original.parent_refs,
        labels={"operation_id": producer_id, "operation_version": producer.spec.version,
                "operation_digest": "0" * 64, "operation_output_port": port},
    ), idempotency_key=name)
    runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace="artifact", name=name,
                                    object_id=artifact.artifact_id)
    return artifact


def _complete(runtime, root, name, operation, inputs, payload, verdict="pass", historical_ports=()):
    request = {"name": name, "operation_id": operation,
               "inputs": [{"port": key, "artifact_names": [value]} for key, value in inputs.items()],
               "instruction": "Use only these exact immutable inputs."}
    preflight = root.call_tool("operation_preflight", request)
    assert preflight["admissible"], preflight
    assert root.call_tool("operation_invoke", request)["result"]["state"] == "queued"
    compiled = runtime.runs.operation_catalog.operation(operation)
    worker = LocalWorkerMCPRouter(runtime.runs, operation_id=operation, operation_digest=compiled.digest)
    opened = worker.call_tool("worker_open_assignment", {})
    assignment = json.loads(Path(opened["assignment_path"]).read_bytes())
    described = {item["source_name"]: item for item in assignment["inputs"]}
    for port in historical_ports:
        assert described[port]["historical"] is True
    Path(opened["output_directory"], "result.json").write_bytes(canonical_json({
        "schema_version": 1, "payload": payload,
        "handoff": {"verdict": verdict, "summary": "Exact continuation fixture."},
    }))
    result = worker.call_tool("worker_submit_result", {})
    assert result["state"] == "completed", result
    return root.call_tool("run_status", {"name": name})["output_artifact_name"]


def test_historical_hypothesis_reaches_new_plan_review_author_and_revision(tmp_path, monkeypatch, experiment_case):
    # Only the already-approved foundation fixture is stubbed; actual independent
    # reviews, guards, preflight, invocation and submission stay enabled.
    runtime, instance, root, _, intent = _feedback_root(
        tmp_path, monkeypatch, experiment_case, "science.experiment.design.v1")
    hyp = _artifact(runtime, instance, "hypothesis_portfolio")
    _historical(runtime, instance, "old_hypothesis", hyp, "science.hypothesis.revise.v1", "hypothesis_portfolio")
    critic_payload = json.loads(runtime.artifacts.read(_artifact(runtime, instance, "critic_review").ref))
    critic_payload["reviews"] = [{"hypothesis_key": item["hypothesis_key"],
        "physical_plausibility": "pass", "falsifiability": "pass", "finite_discriminability": "pass"}
        for item in json.loads(runtime.artifacts.read(hyp.ref))["hypotheses"]]
    critic = _complete(runtime, root, "fresh_critic", "science.hypothesis.criticize.v1",
        {"hypothesis_portfolio": "old_hypothesis", "scientific_foundation": "scientific_foundation"}, critic_payload,
        historical_ports=("hypothesis_portfolio",))
    cohort = {"scientific_foundation": "scientific_foundation", "research_objective": "research_objective",
              "hypothesis_portfolio": "old_hypothesis", "critic_review": critic}
    design = _complete(runtime, root, "new_design", "science.experiment.design.v1", cohort, intent)
    request = {"name": "new_plan", "operation_id": "science.experiment.materialize.v1",
               "inputs": [{"port": key, "artifact_names": [value]} for key, value in
                          {"experiment_design_intent": design, **cohort}.items()]}
    qualification = root.call_tool("operation_preflight", request)
    assert qualification["admissible"], qualification
    materialized = root.call_tool("operation_invoke", request)
    plan = materialized["result"]["outputs"][0]["artifact_name"]
    assert {p["artifact_name"] for p in root.call_tool("artifact_catalog", {"name": plan, "view": "parents"})["parents"]} == {design, *cohort.values()}
    review = _complete(runtime, root, "plan_review", "science.object.review.v1", {"experiment_plan": plan},
        {"review_target": "experiment_portfolio", "verdict": "pass", "summary": "Exact new plan reviewed."})
    from tests.operations.test_general_transform_operations import _register
    from tcad_artifact.execution_control import SolverCapability
    capability = SolverCapability(profile_id="history_fixture", solver_kind="sprocess", executable="/opt/fake/sprocess",
        environment={}, release_evidence="Synthetic R-2020.09 fixture", public_release_label="Sentaurus R-2020.09")
    _register(runtime, instance, name="capability", raw=canonical_json(capability.public_snapshot().model_dump(mode="json")),
              kind="solver_capability", schema="tcad.solver-capability.v2")
    author = {"name": "author_new_plan", "operation_id": "tcad.deck.author.initial.v1", "inputs": [
        {"port": "execution_capability", "artifact_names": ["capability"]},
        {"port": "experiment_plan", "artifact_names": [plan]},
        {"port": "experiment_review", "artifact_names": [review]}], "instruction": "Implement the new reviewed plan."}
    assert root.call_tool("operation_preflight", author)["admissible"]
    _historical(runtime, instance, "old_plan", _artifact(runtime, instance, plan),
                "science.experiment.revise.v1", "experiment_plan")
    change = _complete(runtime, root, "new_change", "science.object.review.v1", {"experiment_plan": "old_plan"},
        {"review_target": "experiment_portfolio", "verdict": "revise", "summary": "Clarify the priority rationale."}, "revise")
    revised = json.loads(runtime.artifacts.read(_artifact(runtime, instance, "old_plan").ref))
    revised["priority_rationale"] += " Clarified under the new review."
    result = _complete(runtime, root, "new_revision", "science.experiment.revise.v1",
        {"prior_draft": "old_plan", "change_request": change}, revised, historical_ports=("prior_draft",))
    assert result != "old_plan"
    revised_author = {**author, "name": "author_revised_plan", "inputs": [
        {**item, "artifact_names": [result]} if item["port"] == "experiment_plan" else item
        for item in author["inputs"]]}
    refused = root.call_tool("operation_preflight", revised_author)
    assert refused["reason_code"] == "input_independent_review_missing"
    fresh = _complete(runtime, root, "revision_review", "science.object.review.v1", {"experiment_plan": result},
        {"review_target": "experiment_portfolio", "verdict": "pass", "summary": "Review only this new revision."})
    revised_author["inputs"][-1] = {"port": "experiment_review", "artifact_names": [fresh]}
    assert root.call_tool("operation_preflight", revised_author)["admissible"]


@pytest.mark.parametrize("verdict", ("pass", "blocked"))
def test_historical_intake_can_request_new_qualification_after_fresh_audit(tmp_path, verdict):
    from tests.operations.test_general_transform_operations import _root, _register, _intake
    from tests.operations.test_agent_contract_alignment import _catalog
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
    from curve_score.plugin import PLUGIN as CURVE_PLUGIN
    from tcad_artifact.plugin import PLUGIN as TCAD_PLUGIN
    from scidiscovery.operations.catalog import compile_catalog

    initial_catalog = _catalog()
    runtime, instance, root = _root(tmp_path, catalog=initial_catalog)
    _register(runtime, instance, name="source", raw=b"Frozen fixture source.",
              kind="source", schema="opaque", media_type="text/plain")
    intake_payload = json.loads(_intake().canonical_json().replace(b'"paper"', b'"source_material"'))
    intake_name = _complete(runtime, root, "extracted", "science.evidence.extract.v1", {"source_material": "source"}, intake_payload, verdict=verdict)
    original = _artifact(runtime, instance, intake_name)
    producer_id = "science.evidence.extract.v1"
    changed = GENERAL_PLUGIN.model_copy(update={"operations": tuple(
        op.model_copy(update={"version": "new-generation"}) if op.operation_id == producer_id else op
        for op in GENERAL_PLUGIN.operations)})
    current = compile_catalog((CORE_PLUGIN, changed, CURVE_PLUGIN, TCAD_PLUGIN))
    runtime.runs.operation_catalog = current
    root.facade._operation_catalog = current
    audit_payload = {"checks": [{"check_key": "source_traceability", "subject": "Frozen source",
        "status": "pass", "basis": "Exact fixture source.", "evidence_keys": ["source_material"]}],
        "evidence": [{"source_key": "source_material", "source_type": "frozen_input", "locator": "line 1"}]}
    audit = _complete(runtime, root, "fresh_audit", "science.evidence.audit.intake.v1",
        {"scientific_intake": intake_name, "source_material": "source"}, audit_payload)
    split_request = {"name": "split", "operation_id": "science.intake.split.v1", "inputs": [
        {"port": "scientific_intake", "artifact_names": [intake_name]},
        {"port": "evidence_audit", "artifact_names": [audit]}]}
    assert root.call_tool("operation_preflight", split_request)["admissible"]
    root.call_tool("operation_invoke", split_request)
    if verdict == "blocked":
        assert _artifact(runtime, instance, "split.scientific_foundation").labels["scientific_claim_admissible"] == "false"
        return
    family = root.facade._run_output_family(original)
    assert family.operation_digest == original.labels["operation_digest"]
    assert family.operation_digest != current.operation(producer_id).digest
    assert family.contract_availability == "historical"
    assert family.unavailable_reason == "producer_contract_unavailable"
    projection = root.call_tool("artifact_catalog", {
        "name": intake_name, "view": "producer_inputs"})
    assert projection["producer"]["availability"] == "historical"
    assert projection["producer"]["operation_digest"] == original.labels["operation_digest"]
    assert projection["producer"]["unavailable_reason"] == "producer_contract_unavailable"
    assert {item["port_name"] for item in projection["producer_inputs"]} == {"source_material"}
    request = {"name": "new_qualification", "operation_id": "science.evidence.qualify.v1", "inputs": [
        {"port": "scientific_foundation", "artifact_names": ["split.scientific_foundation"]},
        {"port": "extraction_primary", "artifact_names": [intake_name]},
        {"port": "evidence_audit", "artifact_names": [audit]},
        {"port": "frozen_sources", "artifact_names": ["source"]}]}
    historical_qualification = root.call_tool("operation_preflight", request)
    assert not historical_qualification["admissible"]
    assert historical_qualification["reason_code"] == "approval_subject_invalid"
    runtime.runs.operation_catalog = initial_catalog
    root.facade._operation_catalog = initial_catalog
    qualification = root.call_tool("operation_preflight", request)
    assert qualification["admissible"], qualification
    result = root.call_tool("operation_invoke", request)
    assert result["executor_kind"] == "approval"
    # Updating only the auditor must not renew its old PASS for qualification.
    upgraded = changed.model_copy(update={"operations": tuple(
        op.model_copy(update={"version": "auditor-upgrade"})
        if op.operation_id == "science.evidence.audit.intake.v1" else op
        for op in changed.operations)})
    upgraded_catalog = compile_catalog((CORE_PLUGIN, upgraded, CURVE_PLUGIN, TCAD_PLUGIN))
    runtime.runs.operation_catalog = root.facade._operation_catalog = upgraded_catalog
    historical_request = {**request, "name": "old_audit_qualification"}
    before = runtime.scheduler_bindings.list(instance=instance.instance_id, namespace="approval")
    refused = root.call_tool("operation_preflight", historical_request)
    assert not refused["admissible"], refused
    with pytest.raises(Exception):
        root.call_tool("operation_invoke", historical_request)
    assert runtime.scheduler_bindings.list(instance=instance.instance_id, namespace="approval") == before
    runtime.runs.operation_catalog = root.facade._operation_catalog = current
    # Dropping a frozen source must not create another approvable request.
    missing = {**request, "name": "missing_source", "inputs": request["inputs"][:-1]}
    assert not root.call_tool("operation_preflight", missing)["admissible"]
    from types import SimpleNamespace
    tampered = SimpleNamespace(ref=original.ref, labels={**original.labels, "operation_digest": "f" * 64})
    from scidiscovery.operations.invoke import OperationInvocationError
    with pytest.raises(OperationInvocationError, match="producer_family_inconsistent"):
        root.facade._run_output_family(tampered)


def test_transform_history_preserves_identity_and_requires_all_siblings(tmp_path, monkeypatch, experiment_case):
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
    from curve_score.plugin import PLUGIN as CURVE_PLUGIN
    from tcad_artifact.plugin import PLUGIN as TCAD_PLUGIN
    from scidiscovery.operations.catalog import compile_catalog
    runtime, instance, root, _, intent = _feedback_root(tmp_path, monkeypatch, experiment_case, "science.experiment.design.v1")
    cohort = {p: p for p in ("scientific_foundation", "research_objective", "hypothesis_portfolio", "critic_review")}
    design = _complete(runtime, root, "design", "science.experiment.design.v1", cohort, intent)
    operation = "science.experiment.materialize.v1"
    request = {"name": "plan", "operation_id": operation, "inputs": [
        {"port": k, "artifact_names": [v]} for k, v in {"experiment_design_intent": design, **cohort}.items()]}
    root.call_tool("operation_invoke", request)
    primary = _artifact(runtime, instance, "plan")
    current_projection = root.call_tool("artifact_catalog", {
        "name": "plan", "view": "producer_inputs", "parent_limit": 2})
    assert current_projection["producer"]["availability"] == "current"
    collected = list(current_projection["producer_inputs"])
    while current_projection["next_offset"] is not None:
        current_projection = root.call_tool("artifact_catalog", {
            "name": "plan", "view": "producer_inputs", "parent_limit": 2,
            "parent_offset": current_projection["next_offset"]})
        collected.extend(current_projection["producer_inputs"])
    assert "research_objective" in {item["port_name"] for item in collected}
    assert all(item["artifact_name"] is None and item["source_name"] is None for item in collected)
    assert all(item["current_access_name"] is not None for item in collected)
    with monkeypatch.context() as patch:
        patch.setattr(root.facade, "_transform_input_groups", lambda *args: None)
        ambiguous = root.call_tool("artifact_catalog", {
            "name": "plan", "view": "producer_inputs"})
        assert ambiguous["producer"]["unavailable_reason"] == "producer_input_mapping_ambiguous"
        assert ambiguous["producer_inputs"] == []
    changed = GENERAL_PLUGIN.model_copy(update={"operations": tuple(
        op.model_copy(update={"version": "new-generation"}) if op.operation_id == operation else op
        for op in GENERAL_PLUGIN.operations)})
    current = compile_catalog((CORE_PLUGIN, changed, CURVE_PLUGIN, TCAD_PLUGIN))
    root.facade._operation_catalog = current
    runtime.runs.operation_catalog = current
    family = root.facade._transform_output_family("plan", primary)
    assert family is not None
    assert family.operation_digest == primary.labels["operation_digest"]
    assert family.operation_digest != current.operation(operation).digest
    assert family.contract_availability == "historical"
    assert family.unavailable_reason == "producer_contract_unavailable"
    assert family.members == family.producer_inputs == ()
    projection = root.call_tool("artifact_catalog", {"name": "plan", "view": "producer_inputs"})
    assert projection["producer"]["availability"] == "historical"
    assert projection["producer"]["unavailable_reason"] == "producer_contract_unavailable"
    assert projection["producer_inputs"] == []
    assert projection["parents_fallback"]["view"] == "parents"
    original_list = runtime.scheduler_bindings.list
    monkeypatch.setattr(runtime.scheduler_bindings, "list", lambda **kwargs: tuple(
        b for b in original_list(**kwargs) if b.name != "plan.materialization_report"))
    assert root.facade._transform_output_family("plan", primary) == family


def test_historical_structure_error_is_located_before_run_creation(tmp_path, monkeypatch, experiment_case):
    from tests.operations.test_general_transform_operations import _register
    runtime, instance, root, _, _ = _feedback_root(tmp_path, monkeypatch, experiment_case, "science.object.review.v1")
    malformed = _register(runtime, instance, name="bad_shape", raw=b'{}',
        kind="experiment_portfolio", schema="scidiscovery.experiment-portfolio.v1")
    _historical(runtime, instance, "old_bad_shape", malformed, "science.experiment.revise.v1", "experiment_plan")
    request = {"name": "bad_review", "operation_id": "science.object.review.v1", "inputs": [
        {"port": "experiment_plan", "artifact_names": ["old_bad_shape"]}], "instruction": "Review exact history."}
    before = root.call_tool("run_list", {})
    result = root.call_tool("operation_preflight", request)
    assert result["reason_code"] == "input_content_incompatible"
    assert result["port"] == "experiment_plan"
    assert result["field"].startswith("/") and result["field"] != "/"
    with pytest.raises(Exception, match="input_content_incompatible"):
        root.call_tool("operation_invoke", request)
    assert root.call_tool("run_list", {}) == before
