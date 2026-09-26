"""Cross-generation continuation without inheriting review or execution authority."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from tests.operations.test_agent_contract_alignment import experiment_case


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
    from tests.operations.worker_fixtures import attached_worker
    worker = attached_worker(runtime, root, name)
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
    assert projection["availability"] == "historical"
    assert {item["source_name"] for item in projection["materials"]} == {"source_material"}
    assert "producer" not in projection
    request = {"name": "new_qualification", "operation_id": "science.evidence.qualify.v1", "inputs": [
        {"port": "scientific_foundation", "artifact_names": ["split.scientific_foundation"]}]}
    historical_qualification = root.call_tool("operation_preflight", request)
    assert not historical_qualification["admissible"]
    assert historical_qualification["reason_code"] == "input_origin_unavailable"
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
    # Dropping the public foundation anchor must not create an approvable request.
    missing = {**request, "name": "missing_source", "inputs": request["inputs"][:-1]}
    assert not root.call_tool("operation_preflight", missing)["admissible"]
    from types import SimpleNamespace
    tampered = SimpleNamespace(ref=original.ref, labels={**original.labels, "operation_digest": "f" * 64})
    from scidiscovery.operations.invoke import OperationInvocationError
    with pytest.raises(OperationInvocationError, match="producer_family_inconsistent"):
        root.facade._run_output_family(tampered)
