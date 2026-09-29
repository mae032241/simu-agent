from __future__ import annotations

import json
from pathlib import Path

import pytest

from blind_csv_plugin.contracts import CSV_SCHEMA_PROBE
from blind_csv_plugin.plugin import PLUGIN as BLIND_CSV_PLUGIN
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.spec import ComponentRef


RAW = b"sample,value\na,1\nb,3\n"


def _system(
    tmp_path: Path,
    *,
    blind_plugin=BLIND_CSV_PLUGIN,
    worker_backend="local",
):
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, blind_plugin))
    project = tmp_path / "project"
    project.mkdir()
    runtime = open_runtime(
        project_root=project,
        state_root=tmp_path / "state",
        worker_backend=worker_backend,
    )
    assert runtime.runs is not None
    assert not hasattr(runtime, "tasks") and not hasattr(runtime, "tokens")
    runtime.runs.operation_catalog = catalog
    instance = runtime.scheduler_bindings.create_instance(
        name="local_worker",
        title="Local Worker Run",
        objective="Prove the current local transport consumes the same Run authority.",
    )
    source = runtime.artifacts.register(
        RAW,
        ArtifactRegistration(
            kind="blind_csv_input",
            schema_id="blind.opaque.v1",
            payload_schema_version=1,
            media_type="text/csv",
            creator=runtime.actor,
        ),
        idempotency_key="local:source",
    )
    runtime.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="artifact",
        name="source_csv",
        object_id=source.artifact_id,
    )
    root = RootMCPRouter(
        RootToolFacade(
            runtime.artifacts,
            runtime.intake,
            runs=runtime.runs,
            approvals=runtime.approvals,
            executions=runtime.executions,
            bindings=runtime.scheduler_bindings,
            instance=instance.instance_id,
            operation_catalog=catalog,
        )
    )
    return catalog, runtime, instance, root


def _invoke(root: RootMCPRouter, name: str = "observation") -> None:
    value = root.call_tool(
        "operation_invoke",
        {
            "name": name,
            "operation_id": "blind.csv.observe.v1",
            "inputs": [
                {"port": "source_table", "artifact_names": ["source_csv"]}
            ],
            "instruction": "Make one bounded observation from the exact CSV.",
        },
    )
    assert value["result"]["state"] == "queued"


def _worker(catalog, runtime) -> LocalWorkerMCPRouter:
    compiled = catalog.operation("blind.csv.observe.v1")
    return LocalWorkerMCPRouter(
        runtime.runs,
        operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest,
    )


def _write_result(worker: LocalWorkerMCPRouter) -> None:
    structure = worker.call_tool("worker_csv_summarize", {})
    content = canonical_json(
        {
            "schema_version": 1,
            "handoff": {"verdict": "pass", "summary": "Bounded result."},
            "payload": {
                "schema_probe": CSV_SCHEMA_PROBE,
                "structure": structure,
                "interpretation": "The bounded arithmetic mean is two.",
                "limitations": ["Two rows do not establish causality."],
            },
        }
    ).decode("utf-8")
    (worker._workspace.output_directory / "result.json").write_text(content)


def test_fresh_runtime_submits_existing_bound_workspace_without_reopening(tmp_path):
    from tests.operations.worker_fixtures import attached_worker
    catalog, runtime, _, root = _system(tmp_path)
    _invoke(root)
    worker=attached_worker(runtime, root, 'observation')
    worker.call_tool('worker_open_assignment', {})
    _write_result(worker)
    before=runtime.runs.status(worker._run_id)
    original=(worker._workspace.output_directory/'result.json').read_bytes()
    restarted=open_runtime(project_root=tmp_path/'project',state_root=tmp_path/'state',worker_backend='local')
    restarted.runs.operation_catalog=catalog
    restored=LocalWorkerMCPRouter(restarted.runs,operation_id=before.operation_id,
        operation_digest=before.operation_digest,run_id=before.run_id,
        trusted_caller=worker._trusted_caller)
    assert restored.call_tool('worker_submit_result', {})['state']=='completed'
    after=restarted.runs.status(before.run_id)
    assert (after.deadline_at,after.started_at)==(before.deadline_at,before.started_at)
    assert (restored._workspace.output_directory/'result.json').read_bytes()==original


def test_queued_assignment_still_requires_explicit_open_with_repair_hint(tmp_path):
    from tests.operations.worker_fixtures import attached_worker
    from scidiscovery.artifact_agent.interfaces.mcp_worker_protocol import WorkerToolError
    _, runtime, _, root = _system(tmp_path)
    _invoke(root)
    worker=attached_worker(runtime, root, 'observation')
    with pytest.raises(WorkerToolError) as caught:
        worker.call_tool('worker_heartbeat', {})
    diagnostic=caught.value.details[0]
    assert diagnostic['code']=='assignment_not_open' and diagnostic['repairable']
    assert 'worker_open_assignment' in diagnostic['message']
    assert runtime.runs.status(worker._bound_run_id).state=='queued'


@pytest.mark.parametrize("backend", ["local"])
def test_one_tool_model_change_reaches_schema_call_and_identity(tmp_path, monkeypatch, backend):
    from dataclasses import replace
    from typing import Literal
    from pydantic import BaseModel, field_validator
    import blind_csv_plugin.plugin as plugin_module
    from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from scidiscovery.operations.spec import ComponentSpec
    from scidiscovery.operations.tooling import WorkerToolDefinition

    class NumberInput(BaseModel):
        value: int

    class ChoiceInput(BaseModel):
        value: Literal["ready"]

    class DynamicErrorInput(BaseModel):
        value: str

        @field_validator("value")
        @classmethod
        def check_value(cls, value):
            if value != "ready":
                raise ValueError("Unsupported value: " + value)
            return value

    original = BLIND_CSV_PLUGIN.operations[0]
    # This fixture probes a tool interface, not a scientific review workflow.
    observe = original.model_copy(update={"review": None, "executor": original.executor.model_copy(update={
        "tools": (*original.executor.tools, ComponentRef("declaration_tool")),
    })})
    plugin = BLIND_CSV_PLUGIN.model_copy(update={
        "components": (*BLIND_CSV_PLUGIN.components, ComponentSpec(
            "declaration_tool", "worker_tool", "blind_csv_plugin.plugin:DECLARATION_TOOL",
        )),
        "operations": (observe, *BLIND_CSV_PLUGIN.operations[1:]),
    })
    calls = []
    tool = WorkerToolDefinition(
        name="worker_declaration_probe", description="Read the one declared value.",
        input_model=NumberInput, capability="fixture.declaration",
        handler=lambda value: calls.append(value.value) or {"value": value.value},
    )
    identities = []
    for index, (model, good, bad, expected_type) in enumerate((
        (NumberInput, 7, "7", "integer"), (ChoiceInput, "ready", 7, "string"),
        (DynamicErrorInput, "ready", "SECRET_INPUT_SENTINEL", "string"),
    )):
        # Only the referenced model changes; no per-consumer Schema or parser edit.
        monkeypatch.setattr(plugin_module, "DECLARATION_TOOL", replace(tool, input_model=model), raising=False)
        case = tmp_path / str(index); case.mkdir()
        catalog, runtime, _, root = _system(case, blind_plugin=plugin, worker_backend=backend)
        _invoke(root)
        compiled = catalog.operation(observe.operation_id)
        identities.append(compiled.digest)
        cls = LocalWorkerMCPRouter
        router = cls(runtime.runs, operation_id=observe.operation_id, operation_digest=compiled.digest)
        mcp = MCPRouter(router, name="declared-test")
        def call(name, args):
            return mcp.handle({"jsonrpc":"2.0", "id":1, "method":"tools/call", "params":{"name":name,"arguments":args}})
        assert "result" in call("worker_open_assignment", {})
        schema = next(t for t in router.list_tools() if t['name'] == tool.name)
        assert schema['inputSchema']['properties']['value']['type'] == expected_type
        before = len(calls)
        rejection = call(tool.name, {"value":bad})
        diagnostic = rejection["error"]["data"]["diagnostics"][0]
        assert diagnostic["code"] == "invalid_arguments"
        assert diagnostic["path"] == "$.value"
        assert diagnostic["phase"] == "tool_arguments"
        summary = runtime.runs.diagnostic_summary(runtime.runs.status(router._run_id))
        assert "SECRET_INPUT_SENTINEL" not in json.dumps(rejection) + json.dumps(summary)
        assert summary["latest_tool_error"]["details"][0]["path"] == "$.value"
        assert len(calls) == before
        assert call(tool.name, {"value":good})['result']['structuredContent'] == {"value":good}
        assert calls[-1] == good
    assert len(set(identities)) == len(identities)


def test_root_mcp_argument_diagnostics_exclude_rejected_values():
    from types import SimpleNamespace
    from unittest.mock import Mock
    from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
    called = Mock()
    mcp = MCPRouter(RootMCPRouter(SimpleNamespace(runs=None, run_list=called)), name="root-test")
    response = mcp.handle({"jsonrpc":"2.0", "id":1, "method":"tools/call", "params":{
        "name":"run_list", "arguments":{"limit":"/tmp/secret-token-do-not-echo"},
    }})
    assert "secret-token" not in json.dumps(response)
    detail = response["error"]["data"]["diagnostics"][0]
    assert (detail["code"],detail["path"],detail["phase"]) == ("invalid_arguments","$.limit","tool_arguments")
    called.assert_not_called()
