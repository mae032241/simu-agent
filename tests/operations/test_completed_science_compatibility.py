"""Sealed scientific proofs survive runtime drift; Run/execution authority does not."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from blind_csv_plugin.contracts import CsvReview
from blind_csv_plugin.plugin import PLUGIN as BLIND_PLUGIN
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.schema.approval import CompiledApprovalIdentity, LocalIdentityRef
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.service.run_records import RunContractUnavailable
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from tests.operations.test_general_transform_operations import _intake, _register, _root
from tests.operations.test_historical_compatibility_paths import _artifact, _complete
from tests.operations.test_hypothesis_objective_boundary import _proposal, _foundation
from tests.operations.test_l3_review_and_human_policy import (
    _complete_author, _complete_review, _consumer_preflight, _envelope, _system,
)


def _drift(operation):
    return operation.model_copy(update={"description": operation.description.model_copy(
        update={"purpose": operation.description.purpose + " Runtime revision."})})


def _switch(runtime, root, catalog):
    runtime.runs.operation_catalog = root.facade._operation_catalog = catalog


@pytest.mark.parametrize("change", ("runtime", "review_version", "review_kind"))
def test_completed_review_reuse_is_separate_from_run_identity(tmp_path, change):
    old, runtime, instance, root = _system(tmp_path)
    subject = _complete_author(old, runtime, root, instruction="First observation.", conflict="reject")
    review = _complete_review(old, runtime, root, name="old_review", subject_name=subject)
    original = _artifact(runtime, instance, review)
    saved = runtime.runs.completed_for_output(original.ref)
    assert saved is not None
    operations = []
    for name in old.operation_ids():
        compiled = old.operation(name)
        if compiled.plugin_id != BLIND_PLUGIN.plugin_id:
            continue
        operation = _drift(compiled.spec)
        if name == "blind.csv.review.v1" and change == "review_version":
            operation = operation.model_copy(update={"version": "2"})
        if name == "blind.csv.review.v1" and change == "review_kind":
            operation = operation.model_copy(update={"outputs": tuple(
                port.model_copy(update={"kind": "new_review_kind"}) for port in operation.outputs)})
        operations.append(operation)
    current = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN,
        BLIND_PLUGIN.model_copy(update={"operations": tuple(operations)})))
    _switch(runtime, root, current)
    assert current.operation(saved.operation_id).digest != saved.operation_digest
    with pytest.raises(RunContractUnavailable):
        runtime.runs.compiled_operation(saved)
    assert runtime.runs.signal_for_output(original.ref, require_current=False) == saved.signal
    refused_without_review = _consumer_preflight(root, subject, None)
    assert refused_without_review["admissible"]
    preflight = _consumer_preflight(root, subject, review)
    if change != "runtime":
        # Ordinary historical context stays readable without renewing its review proof.
        assert preflight["admissible"] if change == "review_version" else preflight["reason_code"] == "input_producer_port_incompatible"
        assert runtime.runs.signal_for_output(original.ref) is None
        return
    assert preflight["admissible"], preflight
    assert runtime.runs.signal_for_output(original.ref) == saved.signal
    request = {"name": "consume", "operation_id": "blind.csv.consume.v1", "inputs": [
        {"port": "source_table", "artifact_names": ["source_csv"]},
        {"port": "csv_observation", "artifact_names": [subject]},
        {"port": "independent_review", "artifact_names": [review]}],
        "instruction": "Consume only an exactly reviewed observation."}
    assert root.call_tool("operation_invoke", request)["result"]["state"] == "queued"
    compiled = current.operation(request["operation_id"])
    worker = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    opened = worker.call_tool("worker_open_assignment", {})
    assignment = json.loads(Path(opened["assignment_path"]).read_bytes())
    assert next(i for i in assignment["inputs"] if i["source_name"] == "independent_review")["historical"]
    payload = CsvReview(subject_sha256=hashlib.sha256(runtime.artifacts.read(
        _artifact(runtime, instance, subject).ref)).hexdigest(), verdict="pass", rationale="Exact fixture review.")
    Path(opened["output_directory"], "result.json").write_bytes(_envelope(payload.model_dump(mode="json")))
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    assert _artifact(runtime, instance, review).labels == original.labels
    revised = _complete_author(current, runtime, root, instruction="A different revision.", conflict="create_revision")
    assert _consumer_preflight(root, revised, review)["reason_code"] == "semantic_name_conflict"
    other = runtime.scheduler_bindings.create_instance(name="other", title="Other instance", objective="Isolate exact bindings.")
    root.facade.instance = other.instance_id
    assert root.call_tool("operation_preflight", request)["reason_code"] == "input_artifact_unavailable"
    with pytest.raises(Exception, match="input_artifact_unavailable"):
        root.call_tool("operation_invoke", request)


def _qualified_foundation(tmp_path):
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN))
    runtime, instance, root = _root(tmp_path, catalog=catalog)
    _register(runtime, instance, name="source", raw=b"Frozen source.", kind="source", schema="opaque", media_type="text/plain")
    payload = json.loads(_intake().canonical_json().replace(b'"paper"', b'"source_material"'))
    objective = json.loads(_foundation())["objective_contract"]
    objective["statement"] = payload["scientific_foundation"]["objective"]
    objective["mandatory_targets"][0]["evidence_item_keys"] = ["target"]
    payload["scientific_foundation"]["objective_contract"] = objective
    intake = _complete(runtime, root, "extracted", "science.evidence.extract.v1", {"source_material": "source"}, payload)
    audit = _complete(runtime, root, "audit", "science.evidence.audit.intake.v1",
        {"scientific_intake": intake, "source_material": "source"},
        {"checks": [{"check_key": "trace", "subject": "Frozen source", "status": "pass",
            "basis": "Exact fixture.", "evidence_keys": ["source_material"]}],
         "evidence": [{"source_key": "source_material", "source_type": "frozen_input", "locator": "line 1"}]})
    root.call_tool("operation_invoke", {"name": "split", "operation_id": "science.intake.split.v1", "inputs": [
        {"port": "scientific_intake", "artifact_names": [intake]}, {"port": "evidence_audit", "artifact_names": [audit]}]})
    foundation = "split.scientific_foundation"
    request = {"name": "qualification", "operation_id": "science.evidence.qualify.v1", "inputs": [
        {"port": "scientific_foundation", "artifact_names": [foundation]}]}
    checked = root.call_tool("operation_preflight", request)
    assert checked["admissible"], checked
    root.call_tool("operation_invoke", request)
    approval_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace="approval", name="qualification")
    launch = runtime.approvals.status(approval_id)
    token = parse_qs(urlparse(launch.review_path).query)["token"][0]
    view = runtime.approvals.review(approval_id, access_token=token)
    runtime.approvals.record_ui_decision(approval_id=approval_id, access_token=token,
        csrf_token=view.csrf_token, decision_nonce=view.decision_nonce, selected_option="approve", rationale="",
        decided_by=LocalIdentityRef(identity_id="fixture_reviewer", display_name="Independent fixture reviewer"),
        ui_session_id="compatibility_test")
    return catalog, runtime, instance, root, foundation


@pytest.mark.parametrize("change", ("runtime", "approval_version", "approval_contract", "foundation_version"))
def test_real_scientific_approval_and_claim_cross_runtime_change(tmp_path, change):
    old, runtime, instance, root, foundation = _qualified_foundation(tmp_path)
    original = _artifact(runtime, instance, foundation)
    operations = []
    for spec in GENERAL_PLUGIN.operations:
        operation = _drift(spec)
        if change == "approval_version" and spec.operation_id == "science.evidence.qualify.v1":
            operation = operation.model_copy(update={"version": "2"})
        if change == "approval_contract" and spec.operation_id == "science.evidence.qualify.v1":
            approval = operation.review.approval.model_copy(update={"question": "A changed scientific approval?"})
            operation = operation.model_copy(update={"review": operation.review.model_copy(update={"approval": approval})})
        if change == "foundation_version" and spec.operation_id == "science.intake.split.v1":
            operation = operation.model_copy(update={"version": "2"})
        operations.append(operation)
    current = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN.model_copy(update={"operations": tuple(operations)})))
    _switch(runtime, root, current)
    provider = current.operation("science.evidence.qualify.v1").approval_identity
    previous = old.operation("science.evidence.qualify.v1").approval_identity
    assert provider.operation_digest != previous.operation_digest
    request = {"name": "new_proposal", "operation_id": "science.hypothesis.propose.v1", "inputs": [
        {"port": "problem_frame", "artifact_names": ["split"]},
        {"port": "scientific_foundation", "artifact_names": [foundation]}],
        "instruction": "Use only these exact immutable inputs."}
    preflight = root.call_tool("operation_preflight", request)
    if change != "runtime":
        expected = "input_producer_contract_changed" if change == "foundation_version" else "input_cohort_approval_missing"
        assert preflight["reason_code"] == expected, preflight
        before = root.call_tool("run_list", {})
        with pytest.raises(Exception, match=expected):
            root.call_tool("operation_invoke", request)
        assert root.call_tool("run_list", {}) == before
        return
    assert provider.version == previous.version
    assert provider.approval_contract_digest == previous.approval_contract_digest
    assert preflight["admissible"], preflight
    identity = CompiledApprovalIdentity(operation_id=provider.operation_id, operation_version=provider.version,
        operation_digest=provider.operation_digest, approval_contract_digest=provider.approval_contract_digest)
    assert not runtime.approvals.are_subjects_approved_by_provider((original.ref,), kind="scientific_foundation",
        accepted_options=("approve",), accepted_providers=(identity,))
    completed = _complete(runtime, root, request["name"], request["operation_id"],
        {"problem_frame": "split", "scientific_foundation": foundation},
        _proposal(hypothesis_keys=("h1",)))
    assert completed
    assert _artifact(runtime, instance, foundation).labels == original.labels
    other = _register(runtime, instance, name="unapproved_foundation", raw=runtime.artifacts.read(original.ref),
        kind=original.kind, schema=original.schema_id)
    request["name"] = "wrong_subject"
    request["inputs"][-1]["artifact_names"] = ["unapproved_foundation"]
    assert other.ref != original.ref
    assert root.call_tool("operation_preflight", request)["reason_code"] == "input_cohort_approval_missing"
