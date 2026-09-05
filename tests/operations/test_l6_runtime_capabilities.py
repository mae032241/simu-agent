from __future__ import annotations

from pathlib import Path

from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as SCIENCE_PLUGIN
from scidiscovery.operations.catalog import compile_catalog


def test_curve_error_agent_is_local_runnable_after_collection_is_moved_to_transform(
    tmp_path: Path,
) -> None:
    catalog = compile_catalog((CORE_PLUGIN, SCIENCE_PLUGIN, CURVE_PLUGIN))
    project = tmp_path / "project"
    project.mkdir()
    runtime = open_runtime(
        project_root=project,
        state_root=tmp_path / "state",
        worker_backend="local",
    )
    runtime.runs.operation_catalog = catalog
    instance = runtime.scheduler_bindings.create_instance(
        name="collection_capability",
        title="Collection capability",
        objective="Verify the Run v1 collection-output boundary.",
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
    operation_id = "science.result.diagnose.curve-error.v1"
    compiled = catalog.operation(operation_id)
    inputs: list[dict[str, object]] = []
    for index, port in enumerate(compiled.spec.inputs):
        name = f"input_{index}"
        artifact = runtime.artifacts.register(
            b"{}",
            ArtifactRegistration(
                kind=port.name,
                schema_id=port.schema_id,
                payload_schema_version=1,
                media_type="application/json",
                creator=runtime.actor,
            ),
            idempotency_key=f"collection-capability:{port.name}",
        )
        runtime.scheduler_bindings.bind(
            instance=instance.instance_id,
            namespace="artifact",
            name=name,
            object_id=artifact.artifact_id,
        )
        inputs.append({"port": port.name, "artifact_names": [name]})

    item = next(
        value
        for value in root.call_tool("operation_catalog", {"scope": "all"})[
            "operations"
        ]
        if value["operation_id"] == operation_id
    )
    assert "runtime_binding" not in item
    request = {
        "name": "collection_agent",
        "operation_id": operation_id,
        "inputs": inputs,
        "instruction": "Exercise the declared Run v1 boundary.",
    }
    assert root.call_tool("operation_preflight", request) == {
        "admissible": True,
        "reason_code": None,
        "port": None,
        "executor_kind": "agent",
    }
    assert runtime.runs.list(instance_id=instance.instance_id) == ()
