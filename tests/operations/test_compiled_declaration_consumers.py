"""One declaration change reaches catalog, admission, and formal submission."""
import json
from pathlib import Path

import pytest

import architecture_operation_test_plugin.plugin as fixture
from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_root import RootToolError
from scidiscovery.artifact_agent.interfaces.mcp_response_views import (
    operation_invoke_contract,
    operation_revision_policy,
)
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.spec import CallableComponent, ComponentRef, InputValidationSpec
from tests.operations.test_general_transform_operations import _register, _root


def _probe_plugin(monkeypatch):
    admission = {"allowed": True, "calls": 0}

    def check_inputs(sources):
        assert admission["allowed"], "Input admission must not run during output submission."
        assert all(raw == b"{}" for raw in sources.values())
        admission["calls"] += 1

    monkeypatch.setattr(fixture, "CONTEXT_VALIDATOR_COMPONENT", CallableComponent("validator", check_inputs))
    schema = {"$id": "scidiscovery.architecture-agent-result.v1", "type": "object",
              "additionalProperties": True, "properties": {"declaration_probe": {"type": "integer"}},
              "required": []}
    monkeypatch.setattr(fixture, "ARCHITECTURE_AGENT_RESULT_SCHEMA", json.dumps(schema))
    agent = fixture.ARCHITECTURE_TEST_PLUGIN.operations[0]
    output = agent.outputs[0].model_copy(update={"validator": ComponentRef("nonempty_validator"),
        "context_validator": None, "context_rule_id": None, "context_sources": ()})
    agent = agent.model_copy(update={"outputs": (output,), "input_validation": InputValidationSpec(
        ComponentRef("context_validator"), "fixture.input_binding", "The bound fixture input is an empty object.")})
    plugin = fixture.ARCHITECTURE_TEST_PLUGIN.model_copy(update={
        "operations": (agent, *fixture.ARCHITECTURE_TEST_PLUGIN.operations[1:]),
        "components": tuple(item for item in fixture.ARCHITECTURE_TEST_PLUGIN.components
                            if item.component_id != "agent_result_validator"),
    })
    return plugin, admission, schema


def _submit(worker, opened, payload):
    Path(opened["output_directory"], "result.json").write_bytes(canonical_json({
        "schema_version": 1, "handoff": {"verdict": "inconclusive", "summary": "Architecture fixture only."},
        "payload": payload,
    }))
    reply = MCPRouter(worker, name="declaration-probe").handle({"jsonrpc": "2.0", "id": 1,
        "method": "tools/call", "params": {"name": "worker_submit_result", "arguments": {}}})
    assert "error" not in reply, reply
    return reply["result"]["structuredContent"]


def test_every_public_invoke_view_is_one_projection_of_its_compiled_contract(tmp_path):
    from tests.operations.test_agent_contract_alignment import _catalog

    catalog = _catalog()
    _, _, root = _root(tmp_path, catalog=catalog)
    full_items = root.call_tool(
        "operation_catalog", {"scope": "public", "view": "detail", "limit": 100}
    )["operations"]
    assert full_items
    for full in full_items:
        compiled = catalog.operation(full["operation_id"])
        policy = operation_revision_policy(compiled.spec)
        invoke = operation_invoke_contract(full, revision_policy=policy)
        assert full["version"] == compiled.spec.version
        assert "operation_digest" not in full and "operation_digest" not in invoke
        assert "revision_policy" not in full
        assert invoke["revision_policy"] == policy
        for field in (
            "inputs", "outputs", "input_admission", "input_validation",
            "complete_transform_family", "consequence", "review_edge",
            "requires_independent_review", "requires_human_approval",
            "timeout_seconds", "max_input_bytes",
        ):
            if field in full:
                assert invoke[field] == full[field]
        for internal in (
            "native_shell", "native_view_image", "network_mode",
            "max_network_requests", "max_output_bytes", "max_files",
            "optional_runtime_services",
        ):
            assert internal not in invoke

    invoke_schema = next(
        item["inputSchema"] for item in root.list_tools() if item["name"] == "operation_invoke"
    )
    assert {
        "on_conflict", "execution_profile", "max_attempts", "resume_from", "draft_from"
    } <= set(invoke_schema["properties"])


def test_one_input_cardinality_change_reaches_catalog_preflight_and_root_invoke(tmp_path, monkeypatch):
    plugin, admission, _ = _probe_plugin(monkeypatch)
    digests = []
    for minimum in (1, 0):
        admission["allowed"] = True
        agent = plugin.operations[0]
        port = agent.inputs[0].model_copy(update={"min_items": minimum})
        changed = plugin.model_copy(update={"operations": (
            agent.model_copy(update={"inputs": (port,)}), *plugin.operations[1:])})
        catalog = compile_catalog((changed,))
        compiled = catalog.operation(agent.operation_id)
        digests.append(compiled.digest)
        directory = tmp_path / f"minimum_{minimum}"
        directory.mkdir()
        runtime, instance, root = _root(directory, catalog=catalog)
        runtime.runs.operation_catalog = catalog
        _register(runtime, instance, name="source", raw=b"{}", kind="fixture_input", schema=port.schema_id)
        view = next(item for item in root.call_tool("operation_catalog", {"scope": "public", "view": "detail"})["operations"]
                    if item["operation_id"] == agent.operation_id)
        assert view["inputs"][0]["min_items"] == minimum
        request = {"name": "cardinality", "operation_id": agent.operation_id,
                   "inputs": [{"port": "agent_input", "artifact_names": []}],
                   "instruction": "Return a finite architecture fixture result from the available inputs."}
        preflight = root.call_tool("operation_preflight", request)
        assert preflight["admissible"] is (minimum == 0)
        if minimum:
            assert preflight["reason_code"] == "input_cardinality_invalid"
            with pytest.raises(RootToolError, match="input_cardinality_invalid"):
                root.call_tool("operation_invoke", request)
            request["inputs"][0]["artifact_names"] = ["source"]
            assert root.call_tool("operation_preflight", request)["admissible"] is True
        assert root.call_tool("operation_invoke", request)["result"]["state"] == "queued"
        admitted_calls = admission["calls"]
        assert admitted_calls > 0
        admission["allowed"] = False
        worker = LocalWorkerMCPRouter(runtime.runs, operation_id=agent.operation_id, operation_digest=compiled.digest)
        opened = worker.call_tool("worker_open_assignment", {})
        assignment = json.loads(Path(opened["assignment_path"]).read_bytes())
        assert len(assignment["inputs"]) == minimum
        assert _submit(worker, opened, {"summary": "Only the available fixture input was considered."})["state"] == "completed"
        assert admission["calls"] == admitted_calls
        assert root.call_tool("run_status", {"name": "cardinality"})["state"] == "completed"
    assert digests[0] != digests[1]


def test_one_output_required_field_change_reaches_worker_schema_and_formal_submit(tmp_path, monkeypatch):
    plugin, admission, schema = _probe_plugin(monkeypatch)
    digests = []
    for required in (False, True):
        admission["allowed"] = True
        # Only the existing output resource's required-field declaration changes.
        schema["required"] = ["declaration_probe"] if required else []
        monkeypatch.setattr(fixture, "ARCHITECTURE_AGENT_RESULT_SCHEMA", json.dumps(schema))
        catalog = compile_catalog((plugin,))
        compiled = catalog.operation(plugin.operations[0].operation_id)
        digests.append(compiled.digest)
        assert compile_catalog((plugin,)).operation(compiled.spec.operation_id).digest == compiled.digest
        directory = tmp_path / f"required_{required}"
        directory.mkdir()
        runtime, instance, root = _root(directory, catalog=catalog)
        runtime.runs.operation_catalog = catalog
        _register(runtime, instance, name="source", raw=b"{}", kind="fixture_input",
                  schema=compiled.spec.inputs[0].schema_id)
        request = {"name": "output_shape", "operation_id": compiled.spec.operation_id,
                   "inputs": [{"port": "agent_input", "artifact_names": ["source"]}],
                   "instruction": "Return only the architecture fixture fields required by the current schema."}
        assert root.call_tool("operation_preflight", request)["admissible"] is True
        assert root.call_tool("operation_invoke", request)["result"]["state"] == "queued"
        admitted_calls = admission["calls"]
        assert admitted_calls > 0
        admission["allowed"] = False
        worker = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
        opened = worker.call_tool("worker_open_assignment", {})
        assignment = json.loads(Path(opened["assignment_path"]).read_bytes())
        visible = json.loads(Path(opened["workspace_path"], assignment["output"]["schema_path"]).read_bytes())
        payload_schema = visible["properties"]["payload"]
        assert payload_schema["required"] == schema["required"]
        assert payload_schema["properties"]["declaration_probe"] == {"type": "integer"}
        assert "digest" not in assignment["operation"]
        assert runtime.runs.status(worker._run_id).operation_digest == compiled.digest
        assert payload_schema["x-scidiscovery-validation-contract"]["operation_digest"] == compiled.digest
        payload = {"summary": "A bounded architecture fixture result."}
        submitted = _submit(worker, opened, payload)
        if required:
            assert submitted["state"] == "rejected"
            assert {item["rule_id"] for item in submitted["diagnostics"]} == {"runtime.schema"}
            rejected = _submit(worker, opened, {**payload, "declaration_probe": "1"})
            assert rejected["state"] == "rejected"
            assert {item["rule_id"] for item in rejected["diagnostics"]} == {"runtime.schema"}
            submitted = _submit(worker, opened, {**payload, "declaration_probe": 1})
        assert submitted["state"] == "completed"
        assert admission["calls"] == admitted_calls
        assert root.call_tool("run_status", {"name": "output_shape"})["state"] == "completed"
    assert digests[0] != digests[1]
