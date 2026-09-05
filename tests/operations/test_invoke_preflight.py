from __future__ import annotations

import pytest

from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from architecture_operation_test_plugin.plugin import ARCHITECTURE_TEST_PLUGIN as PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.invoke import (
    execute_compiled_transform,
    InvocationArtifact,
    OperationInvocationError,
    effect_executor_plan,
    preflight_operation,
)


def _artifact(**changes) -> InvocationArtifact:
    values = {
        "artifact_name": "fixture_input",
        "ref": ArtifactRef(
            artifact_id="art_fixture",
            sha256="0" * 64,
            kind="architecture_test_input",
            schema_id="scidiscovery.architecture-test.v1",
        ),
        "schema_id": "scidiscovery.architecture-test.v1",
        "media_type": "application/json",
        "size_bytes": 2,
    }
    values.update(changes)
    return InvocationArtifact(**values)


def _bind(operation_id: str, *, instruction: str | None = None):
    compiled = compile_catalog((PLUGIN,)).operation(operation_id)
    port = compiled.spec.inputs[0].name
    return preflight_operation(
        compiled,
        name="fixture_call",
        artifacts_by_port={port: (_artifact(),)},
        instruction=instruction,
    )


def test_agent_preflight_binds_exact_input_and_default_deny_authority() -> None:
    bound = _bind("builtin.test.agent", instruction="Review the fixture.")
    assert [(item.port_name, item.source_name) for item in bound.inputs] == [
        ("agent_input", "agent_input")
    ]
    permission = bound.compiled.permission_template
    assert permission is not None
    assert permission.limits.network.mode == "none"
    assert "analysis.python" not in permission.tools
    assert "evidence.web_snapshot" not in permission.tools
    assert bound.compiled.spec.executor.kind == "agent"
    assert permission.tools[-1] == "architecture_fixture:fixture_inspect_tool"


def test_preflight_rejects_unknown_ports_schema_parameters_and_claim_gates() -> None:
    compiled = compile_catalog((PLUGIN,)).operation("builtin.test.agent")
    with pytest.raises(OperationInvocationError, match="input_port_unknown"):
        preflight_operation(
            compiled,
            name="bad",
            artifacts_by_port={
                "agent_input": (_artifact(),),
                "unknown": (),
            },
            instruction="Review.",
        )
    with pytest.raises(OperationInvocationError, match="input_schema_mismatch"):
        preflight_operation(
            compiled,
            name="bad",
            artifacts_by_port={
                "agent_input": (_artifact(schema_id="wrong.schema"),)
            },
            instruction="Review.",
        )
    with pytest.raises(OperationInvocationError, match="parameters_not_declared"):
        preflight_operation(
            compiled,
            name="bad",
            artifacts_by_port={"agent_input": (_artifact(),)},
            instruction="Review.",
            parameters={"undeclared": True},
        )
    gated_port = compiled.spec.inputs[0].model_copy(update={"require_current": True})
    gated = compiled.spec.model_copy(update={"inputs": (gated_port,)})
    gated_plugin = PLUGIN.model_copy(
        update={"operations": (gated, *PLUGIN.operations[1:])}
    )
    gated_compiled = compile_catalog((gated_plugin,)).operation(gated.operation_id)
    with pytest.raises(OperationInvocationError, match="input_not_current"):
        preflight_operation(
            gated_compiled,
            name="bad",
            artifacts_by_port={"agent_input": (_artifact(),)},
            instruction="Review.",
        )

    invalid_usage_port = compiled.spec.inputs[0].model_copy(
        update={"usage": "plugin_private_usage"}
    )
    invalid_usage_spec = compiled.spec.model_copy(
        update={"inputs": (invalid_usage_port,)}
    )
    invalid_usage_plugin = PLUGIN.model_copy(
        update={"operations": (invalid_usage_spec, *PLUGIN.operations[1:])}
    )
    invalid_usage_compiled = compile_catalog((invalid_usage_plugin,)).operation(
        invalid_usage_spec.operation_id
    )
    with pytest.raises(OperationInvocationError, match="agent_input_usage_invalid"):
        preflight_operation(
            invalid_usage_compiled,
            name="bad",
            artifacts_by_port={"agent_input": (_artifact(),)},
            instruction="Review.",
        )


def test_transform_and_effect_components_are_invoked_only_after_binding() -> None:
    transform = _bind("builtin.test.transform")
    outputs = execute_compiled_transform(
        transform, {"transform_input": b"{}"}
    )
    assert [(item.label, item.content) for item in outputs] == [("primary", b"{}")]
    effect = _bind("builtin.test.effect")
    plan = effect_executor_plan(effect)
    assert (plan.executor, plan.payload_port) == (
        "architecture_fixture:fixture",
        "effect_input",
    )


def test_compiled_transform_uses_declared_payload_schema_version() -> None:
    original = next(
        item for item in PLUGIN.operations
        if item.operation_id == "builtin.test.transform"
    )
    revised = original.model_copy(
        update={
            "outputs": (
                original.outputs[0].model_copy(
                    update={"payload_schema_version": 2}
                ),
            )
        }
    )
    plugin = PLUGIN.model_copy(
        update={
            "operations": tuple(
                revised if item.operation_id == revised.operation_id else item
                for item in PLUGIN.operations
            )
        }
    )
    compiled = compile_catalog((plugin,)).operation(revised.operation_id)
    bound = preflight_operation(
        compiled,
        name="versioned_transform",
        artifacts_by_port={"transform_input": (_artifact(),)},
        instruction=None,
    )
    outputs = execute_compiled_transform(bound, {"transform_input": b"{}"})
    assert outputs[0].payload_schema_version == 2
