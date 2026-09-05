from __future__ import annotations

from dataclasses import asdict
import json

import pytest
from unittest.mock import Mock
from pydantic import BaseModel

from architecture_operation_test_plugin.plugin import ARCHITECTURE_TEST_PLUGIN as PLUGIN
from scidiscovery.operations.spec import (
    CompleteTransformFamilySpec,
    ComponentRef,
    ComponentSpec,
    ExecutorRef,
    NetworkPolicy,
    ReviewSpec,
    WorkspaceContract,
)


def replace(instance, **changes):
    assert isinstance(instance, BaseModel)
    return instance.model_copy(update=changes)
from scidiscovery.operations.catalog import CatalogCompileError, compile_catalog


def test_builtin_catalog_compiles_exactly_three_architecture_test_operations() -> None:
    first = compile_catalog((PLUGIN,))
    second = compile_catalog((PLUGIN,))
    assert first.operation_ids() == (
        "builtin.test.agent",
        "builtin.test.effect",
        "builtin.test.transform",
    )
    for operation_id in first.operation_ids():
        compiled = first.operation(operation_id)
        assert len(compiled.digest) == 64
        assert compiled.digest == second.operation(operation_id).digest
        assert all(
            component_id.startswith("architecture_fixture:")
            for component_id in compiled.component_ids
        )

    assert "architecture_fixture:test_effect" not in first.operation("builtin.test.agent").component_ids
    assert "architecture_fixture:test_agent" not in first.operation("builtin.test.effect").component_ids


def test_compiled_agent_authority_is_exact_and_default_deny() -> None:
    compiled = compile_catalog((PLUGIN,)).operation("builtin.test.agent")
    authority = compiled.permission_template
    assert authority is not None
    assert authority.inputs == (("agent_input", "full", 1, 4096),)
    assert authority.workspace == "architecture_fixture:test_workspace"
    assert authority.tools == (
        "architecture_fixture:file_write_begin_tool",
        "architecture_fixture:file_write_chunk_tool",
        "architecture_fixture:file_write_commit_tool",
        "architecture_fixture:fixture_inspect_tool",
    )
    assert tuple(tool.name for tool in authority.lifecycle.tools) == (
        "worker_open_assignment",
        "worker_heartbeat",
        "worker_submit_result",
    )
    assert authority.resources == ("architecture_fixture:test_prompt",)
    assert authority.model == "gpt-5.4"
    assert authority.limits.network.mode == "none"
    assert authority.limits.network.allowed_domains == ()
    assert authority.limits.network.max_requests == 0
    view = compile_catalog((PLUGIN,)).scheduler_projection()[0]
    assert (view.max_input_bytes, view.max_output_bytes) == (4096, 4096)
    assert view.max_files == 2
    assert (view.network_mode, view.max_network_requests) == ("none", 0)


def test_catalog_scope_is_declared_semantics_not_inferred_from_executor_or_id() -> None:
    agent = replace(PLUGIN.operations[0], catalog_scope="internal")
    transform = replace(PLUGIN.operations[1], catalog_scope="public")
    plugin = replace(PLUGIN, operations=(agent, transform, PLUGIN.operations[2]))

    views = {
        item.operation_id: item
        for item in compile_catalog((plugin,)).scheduler_projection()
    }
    assert views[agent.operation_id].catalog_scope == "internal"
    assert views[transform.operation_id].catalog_scope == "public"


@pytest.mark.parametrize("operation_index", (0, 2))
def test_support_scope_rejects_non_transform_executors(operation_index: int) -> None:
    operation = replace(PLUGIN.operations[operation_index], catalog_scope="support")
    operations = list(PLUGIN.operations)
    operations[operation_index] = operation

    with pytest.raises(CatalogCompileError) as caught:
        compile_catalog((replace(PLUGIN, operations=tuple(operations)),))
    assert caught.value.reason_code == "support_executor_invalid"


def test_support_scope_still_requires_a_complete_review_edge() -> None:
    transform = replace(
        PLUGIN.operations[1],
        catalog_scope="support",
        review=ReviewSpec(reviewer_operation="builtin.test.agent"),
    )
    operations = (
        PLUGIN.operations[0],
        transform,
        PLUGIN.operations[2],
    )

    with pytest.raises(CatalogCompileError) as caught:
        compile_catalog((replace(PLUGIN, operations=operations),))
    assert caught.value.reason_code == "reviewer_port_missing"


def test_complete_transform_family_references_consumer_input_ports() -> None:
    operation = replace(
        PLUGIN.operations[0],
        complete_transform_family=CompleteTransformFamilySpec(
            output_ports=("missing_output",),
            input_ports=("agent_input",),
        ),
    )
    plugin = replace(
        PLUGIN,
        operations=(operation, *PLUGIN.operations[1:]),
    )

    with pytest.raises(CatalogCompileError) as caught:
        compile_catalog((plugin,))
    assert caught.value.reason_code == "complete_transform_family_invalid"


def test_support_scope_rejects_human_approval() -> None:
    transform = replace(
        PLUGIN.operations[1],
        catalog_scope="support",
        review=ReviewSpec(approval=PLUGIN.operations[2].review.approval),
    )
    operations = (PLUGIN.operations[0], transform, PLUGIN.operations[2])

    with pytest.raises(CatalogCompileError) as caught:
        compile_catalog((replace(PLUGIN, operations=operations),))
    assert caught.value.reason_code == "support_approval_forbidden"


def test_catalog_scope_rejects_unknown_visibility() -> None:
    operation = PLUGIN.operations[0].model_copy(
        update={"catalog_scope": "hidden-by-convention"}
    )
    plugin = replace(PLUGIN, operations=(operation, *PLUGIN.operations[1:]))

    with pytest.raises(CatalogCompileError) as caught:
        compile_catalog((plugin,))
    assert caught.value.reason_code == "declaration_structure_invalid"


@pytest.mark.parametrize("path", ("evidence", "/evidence/~2bad", "/evidence",))
def test_output_evidence_paths_are_valid_unique_json_pointers(path: str) -> None:
    output = PLUGIN.operations[0].outputs[0].model_copy(
        update={"evidence_paths": (path, path)}
    )
    operation = PLUGIN.operations[0].model_copy(update={"outputs": (output,)})
    plugin = PLUGIN.model_copy(
        update={"operations": (operation, *PLUGIN.operations[1:])}
    )

    with pytest.raises(CatalogCompileError) as caught:
        compile_catalog((plugin,))
    assert caught.value.reason_code == "output_evidence_path_invalid"


def test_network_tool_compiles_only_with_exact_restricted_scope() -> None:
    agent = PLUGIN.operations[0]
    web_tool = ComponentSpec(
        "web_evidence_tool",
        "worker_tool",
        "architecture_operation_test_plugin.plugin:NETWORK_TOOL",
    )
    executor = replace(
        agent.executor,
        tools=(*agent.executor.tools, ComponentRef("web_evidence_tool")),
    )
    limits = replace(
        agent.limits,
        network=NetworkPolicy(
            mode="restricted",
            allowed_domains=("example.test", "*.example.org"),
            max_requests=3,
        ),
    )
    plugin = replace(
        PLUGIN,
        components=(*PLUGIN.components, web_tool),
        operations=(
            replace(agent, executor=executor, limits=limits),
            *PLUGIN.operations[1:],
        ),
    )
    authority = compile_catalog((plugin,)).operation(
        "builtin.test.agent"
    ).permission_template
    assert authority is not None
    assert authority.limits.network == limits.network


def test_unmaterialized_agent_resources_fail_closed() -> None:
    skill = ComponentSpec(
        "test_skill", "resource", "architecture_operation_test_plugin.plugin:ARCHITECTURE_TEST_SCHEMA"
    )
    components = tuple(
        replace(
            item,
            resources=(ComponentRef("test_skill"),),
        ) if item.component_id == "test_prompt" else item
        for item in PLUGIN.components
    ) + (skill,)
    plugin = replace(PLUGIN, components=components)
    with pytest.raises(CatalogCompileError) as caught:
        compile_catalog((plugin,))
    assert caught.value.reason_code == "agent_resources_unsupported"


def test_authority_and_resource_bytes_are_part_of_the_compiled_digest(
    monkeypatch,
) -> None:
    original = compile_catalog((PLUGIN,)).operation("builtin.test.agent").digest
    agent = PLUGIN.operations[0]
    changed_limits = replace(agent.limits, timeout_seconds=301)
    changed_plugin = replace(
        PLUGIN,
        operations=(replace(agent, limits=changed_limits), *PLUGIN.operations[1:]),
    )
    assert compile_catalog((changed_plugin,)).operation(
        "builtin.test.agent"
    ).digest != original

    monkeypatch.setattr(
        "architecture_operation_test_plugin.plugin.ARCHITECTURE_TEST_PROMPT",
        "Changed bytes at the same registered resource path.",
    )
    prompt_changed = compile_catalog((PLUGIN,)).operation("builtin.test.agent").digest
    assert prompt_changed != original

    monkeypatch.setattr(
        "architecture_operation_test_plugin.plugin.ARCHITECTURE_TEST_WORKSPACE",
        WorkspaceContract(scratch_directory="temporary"),
    )
    with pytest.raises(CatalogCompileError) as caught:
        compile_catalog((PLUGIN,))
    assert caught.value.reason_code == "component_protocol_invalid"


def test_reviewer_behavior_is_closed_into_the_producer_digest() -> None:
    agent, transform, effect = PLUGIN.operations
    reviewer_component = ComponentSpec(
        "review_agent",
        "agent",
        "architecture_operation_test_plugin.plugin:AGENT_COMPONENT",
    )
    components = tuple(
        component
        for component in PLUGIN.components
        if component.component_id != "test_transform"
    ) + (reviewer_component,)
    reviewer = replace(
        transform,
        inputs=(
            replace(
                transform.inputs[0],
                schema_id=agent.outputs[0].schema_id,
                schema_resource=agent.outputs[0].schema_resource,
                codec=agent.outputs[0].codec,
                media_types=agent.outputs[0].media_types,
            ),
        ),
        consequence="explore",
        executor=ExecutorRef(
            kind="agent",
            component=ComponentRef("review_agent"),
            workspace=agent.executor.workspace,
            prompt=agent.executor.prompt,
            model=agent.executor.model,
        ),
        outputs=(
            replace(
                transform.outputs[0],
                collection=None,
                min_items=1,
                max_items=1,
                max_item_bytes=4096,
                validator=ComponentRef("nonempty_validator"),
            ),
        ),
    )
    producer = replace(
        agent,
        review=ReviewSpec(
            reviewer_operation=reviewer.operation_id,
            reviewer_input_port="transform_input",
            subject_outputs=("agent_output",),
        ),
    )
    plugin = replace(
        PLUGIN, components=components, operations=(producer, reviewer, effect)
    )
    original = compile_catalog((plugin,)).operation(producer.operation_id).digest
    revised = replace(
        plugin,
        operations=(producer, replace(reviewer, version="2"), effect),
    )
    assert compile_catalog((revised,)).operation(producer.operation_id).digest != original


def test_scheduler_projection_contains_no_component_or_runtime_identity() -> None:
    catalog = compile_catalog((PLUGIN,))
    serialized = json.dumps(
        [view.model_dump(mode="json") for view in catalog.scheduler_projection()], sort_keys=True
    )
    for forbidden in (
        "component",
        "implementation",
        "configuration_identity",
        "digest",
        "test_agent",
        "scidiscovery.builtin_plugin",
    ):
        assert forbidden not in serialized


def test_catalog_does_not_expose_mutable_operation_mapping() -> None:
    catalog = compile_catalog((PLUGIN,))
    assert not hasattr(catalog, "operations")
    with pytest.raises(KeyError):
        catalog.operation("unknown.operation")


def test_builtin_transform_carries_one_compiled_collection_contract() -> None:
    operation = compile_catalog((PLUGIN,)).operation("builtin.test.transform")
    output = operation.spec.outputs[0]
    assert output.collection is not None
    assert output.collection.max_total_bytes == 4096
    assert "architecture_fixture:bundle_codec" in operation.component_ids


def test_compilation_resolves_but_does_not_invoke_registered_behavior(
    monkeypatch,
) -> None:
    effect = Mock(side_effect=AssertionError("compiler invoked an effect"))
    from scidiscovery.operations.spec import CallableComponent

    monkeypatch.setattr(
        "architecture_operation_test_plugin.plugin.EFFECT_COMPONENT",
        CallableComponent("effect", effect),
    )
    compile_catalog((PLUGIN,))
    effect.assert_not_called()
