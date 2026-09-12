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


def test_declared_input_checker_gets_exact_bounded_sources_before_run_creation(monkeypatch) -> None:
    from dataclasses import replace
    from hashlib import sha256
    from scidiscovery.operations.spec import ComponentRef, InputValidationSpec, scheduler_operation_view
    from scidiscovery.operation_contract import operation_input_validation_contract, operation_port_json_schema

    compiled = compile_catalog((PLUGIN,)).operation("builtin.test.agent")
    declaration = InputValidationSpec(
        ComponentRef("nonempty_validator"), "fixture.input_binding",
        "The input must carry the expected exact content.",
    )
    spec = compiled.spec.model_copy(update={"input_validation": declaration})
    calls = []

    def checker(sources):
        calls.append(sources)
        assert sources["agent_input"] == b"{}"
        assert sources.binding_descriptors["agent_input"].artifact_ref.sha256 == sha256(b"{}").hexdigest()
        raise OperationInvocationError("input_fixture_rejected", port="agent_input", field="/fixture")

    from scidiscovery.operations.spec import CallableComponent
    import architecture_operation_test_plugin.plugin as plugin_module
    monkeypatch.setattr(plugin_module, "VALIDATOR_COMPONENT", CallableComponent("validator", checker))
    plugin = PLUGIN.model_copy(update={"operations": tuple(
        spec if item.operation_id == spec.operation_id else item for item in PLUGIN.operations
    )})
    compiled = compile_catalog((plugin,)).operation(spec.operation_id)
    artifact = _artifact(ref=_artifact().ref.model_copy(update={"sha256": sha256(b"{}").hexdigest()}))
    with pytest.raises(OperationInvocationError, match="input_fixture_rejected"):
        preflight_operation(compiled, name="checked", artifacts_by_port={"agent_input": (artifact,)}, instruction="Review.", read_artifact=lambda ref: b"{}")
    assert len(calls) == 1
    projection = scheduler_operation_view(spec).input_validation
    assert projection == operation_input_validation_contract(compiled)
    assert operation_port_json_schema(compiled, spec.outputs[0])["x-scidiscovery-input-validation-contract"] == projection
    assert scheduler_operation_view(spec).input_admission == spec.input_admission
    with pytest.raises(OperationInvocationError, match="input_content_integrity_failure"):
        preflight_operation(compiled, name="corrupt", artifacts_by_port={"agent_input": (artifact,)}, instruction="Review.", read_artifact=lambda ref: b"[]")
    assert len(calls) == 1
    oversized = _artifact(size_bytes=spec.limits.max_input_bytes + 1)
    with pytest.raises(OperationInvocationError, match="input_item_too_large|input_total_too_large"):
        preflight_operation(compiled, name="oversized", artifacts_by_port={"agent_input": (oversized,)}, instruction="Review.", read_artifact=lambda ref: pytest.fail("must not read beyond metadata budget"))


def test_input_checker_reference_is_compiled_and_default_digest_is_compatible() -> None:
    import json
    from scidiscovery.operations.spec import ComponentRef, InputValidationSpec, canonical_json

    original = PLUGIN.operations[0]
    legacy = original.model_dump(mode="python", by_alias=True)
    legacy.pop("input_validation")
    assert canonical_json(original) == canonical_json(legacy)
    assert json.loads(canonical_json(original))["input_admission"] is None
    declaration = InputValidationSpec(ComponentRef("nonempty_validator"), "fixture.input_binding", "Check exact bound input content.")
    revised = original.model_copy(update={"input_validation": declaration})
    plugin = PLUGIN.model_copy(update={"operations": (revised, *PLUGIN.operations[1:])})
    compiled = compile_catalog((plugin,)).operation(original.operation_id)
    assert "architecture_fixture:nonempty_validator" in compiled.component_ids
    assert compiled.digest != compile_catalog((PLUGIN,)).operation(original.operation_id).digest
    invalid = revised.model_copy(update={"input_validation": declaration.model_copy(update={"validator": ComponentRef("absent")})})
    with pytest.raises(ValueError):
        compile_catalog((PLUGIN.model_copy(update={"operations": (invalid, *PLUGIN.operations[1:])}),))


def test_service_alias_overrides_are_frozen_before_input_checker() -> None:
    from dataclasses import replace
    from hashlib import sha256
    from scidiscovery.operations.spec import ComponentRef, InputValidationSpec

    compiled = compile_catalog((PLUGIN,)).operation("builtin.test.agent")
    observed = []
    implementations = dict(compiled.implementations)
    implementations["architecture_fixture:nonempty_validator"] = lambda sources: observed.append(tuple(sources))
    compiled = replace(compiled, implementations=implementations, spec=compiled.spec.model_copy(update={
        "input_validation": InputValidationSpec(ComponentRef("nonempty_validator"), "fixture.alias", "Check final frozen input aliases."),
    }))
    artifact = _artifact(ref=_artifact().ref.model_copy(update={"sha256": sha256(b"{}").hexdigest()}))
    kwargs = dict(name="aliases", artifacts_by_port={"agent_input": (artifact,)}, instruction="Review.", read_artifact=lambda ref: b"{}")
    bound = preflight_operation(compiled, **kwargs, source_name_overrides={("agent_input", artifact.artifact_name): "legacy_source"})
    assert bound.inputs[0].source_name == "legacy_source"
    assert observed == [("legacy_source",)]
    with pytest.raises(OperationInvocationError, match="input_source_alias_invalid"):
        preflight_operation(compiled, **kwargs, source_name_overrides={("agent_input", artifact.artifact_name): "../escape"})
    with pytest.raises(OperationInvocationError, match="input_source_alias_unknown"):
        preflight_operation(compiled, **kwargs, source_name_overrides={("agent_input", "foreign_artifact"): "source"})
    assert observed == [("legacy_source",)]


def test_service_alias_overrides_reject_duplicate_final_sources() -> None:
    from dataclasses import replace
    compiled = compile_catalog((PLUGIN,)).operation("builtin.test.agent")
    other_port = compiled.spec.inputs[0].model_copy(update={"name": "other_input"})
    compiled = replace(compiled, spec=compiled.spec.model_copy(update={"inputs": (*compiled.spec.inputs, other_port)}))
    first = _artifact()
    second = _artifact(artifact_name="other_artifact", ref=first.ref.model_copy(update={"artifact_id": "art_other"}))
    with pytest.raises(OperationInvocationError, match="input_source_alias_duplicate"):
        preflight_operation(compiled, name="duplicates", instruction="Review.",
                            artifacts_by_port={"agent_input": (first,), "other_input": (second,)},
                            source_name_overrides={("agent_input", first.artifact_name): "same", ("other_input", second.artifact_name): "same"})
