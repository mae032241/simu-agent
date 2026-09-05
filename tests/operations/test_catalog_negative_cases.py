from __future__ import annotations

import pytest
from pydantic import BaseModel

from architecture_operation_test_plugin.plugin import ARCHITECTURE_TEST_PLUGIN as PLUGIN
from scidiscovery.operations.catalog import CatalogCompileError, compile_catalog
from scidiscovery.operations.spec import (
    ApprovalContract,
    CollectionSpec,
    ComponentRef,
    ComponentSpec,
    ExecutorRef,
    NativeToolPolicy,
    NetworkPolicy,
    PluginDefinition,
    PluginDependency,
    ReviewSpec,
)


def replace(instance, **changes):
    assert isinstance(instance, BaseModel)
    return instance.model_copy(update=changes)


def _expect(code: str, *plugins: PluginDefinition) -> CatalogCompileError:
    with pytest.raises(CatalogCompileError) as caught:
        compile_catalog(plugins)
    assert caught.value.reason_code == code
    return caught.value


@pytest.mark.parametrize(
    ("implementation", "code"),
    (
        ("missing_operation_test_module:value", "component_implementation_missing"),
        ("architecture_operation_test_plugin.plugin:MISSING", "component_implementation_missing"),
        ("builtins:len", "component_protocol_invalid"),
    ),
)
def test_component_implementation_failures_are_closed(
    implementation: str, code: str
) -> None:
    prompt = replace(PLUGIN.components[-1], implementation=implementation)
    plugin = replace(PLUGIN, components=(*PLUGIN.components[:-1], prompt))
    _expect(code, plugin)


def test_duplicate_and_protocol_failures_are_closed() -> None:
    _expect("plugin_duplicate", PLUGIN, PLUGIN)
    _expect(
        "component_duplicate",
        replace(PLUGIN, components=(*PLUGIN.components, PLUGIN.components[0])),
    )
    _expect(
        "operation_duplicate",
        replace(PLUGIN, operations=(*PLUGIN.operations, PLUGIN.operations[0])),
    )
    _expect("plugin_protocol_unsupported", replace(PLUGIN, protocol_version="2"))


def test_agent_output_context_and_collection_contracts_fail_closed() -> None:
    agent = PLUGIN.operations[0]
    bad_context = replace(
        agent.outputs[0], context_sources=("missing_input",)
    )
    _expect(
        "output_context_invalid",
        replace(
            PLUGIN,
            operations=(replace(agent, outputs=(bad_context,)), *PLUGIN.operations[1:]),
        ),
    )
    collection = replace(
        agent.outputs[0],
            name="attachments",
            validator=None,
            validator_rule_id=None,
            context_validator=None,
            context_rule_id=None,
        context_sources=(),
        collection=CollectionSpec(max_total_bytes=4096),
    )
    limits = replace(agent.limits, max_output_bytes=8192, max_files=2)
    _expect(
        "agent_output_contract_invalid",
        replace(
            PLUGIN,
            operations=(
                replace(agent, outputs=(*agent.outputs, collection), limits=limits),
                *PLUGIN.operations[1:],
            ),
        ),
    )
    transform = PLUGIN.operations[1]
    _expect(
        "output_evidence_path_invalid",
        replace(
            PLUGIN,
            operations=(
                agent,
                replace(
                    transform,
                    outputs=(
                        replace(transform.outputs[0], evidence_paths=("/evidence",)),
                    ),
                ),
                *PLUGIN.operations[2:],
            ),
        ),
    )
    component = replace(PLUGIN.components[0], protocol_version="2")
    _expect(
        "component_protocol_unsupported",
        replace(PLUGIN, components=(component, *PLUGIN.components[1:])),
    )
    malformed = PLUGIN.model_copy(update={"components": list(PLUGIN.components)})
    _expect("declaration_structure_invalid", malformed)


def test_context_content_must_be_visible_but_lineage_inputs_may_be_hidden() -> None:
    agent = PLUGIN.operations[0]
    hidden = replace(agent.inputs[0], exposure="handoff_only")
    _expect(
        "output_context_input_hidden",
        replace(PLUGIN, operations=(replace(agent, inputs=(hidden,)), *PLUGIN.operations[1:])),
    )
    lineage = replace(hidden, name="lineage_only", min_items=0)
    for exposure in ("full", "on_demand"):
        visible = replace(agent.inputs[0], exposure=exposure)
        compile_catalog((replace(
            PLUGIN, operations=(replace(agent, inputs=(visible, lineage)), *PLUGIN.operations[1:])
        ),))


@pytest.mark.parametrize("changes", (
    {"required_non_null_fields": ("field", "field")},
    {"required_non_null_fields": ("",)},
    {"required_non_null_fields": ("field",), "media_types": ("text/plain",)},
))
def test_input_content_requirements_reject_invalid_declarations(changes) -> None:
    transform = PLUGIN.operations[1]
    port = replace(transform.inputs[0], **changes)
    _expect(
        "input_content_requirement_invalid",
        replace(PLUGIN, operations=(PLUGIN.operations[0], replace(transform, inputs=(port,)), *PLUGIN.operations[2:])),
    )


def test_agent_contract_requires_exactly_one_primary_output() -> None:
    agent = PLUGIN.operations[0]
    output = agent.outputs[0]
    second = replace(output, name="unexpected_primary")
    limits = replace(
        agent.limits,
        max_output_bytes=output.max_item_bytes + second.max_item_bytes,
    )
    _expect(
        "agent_output_contract_invalid",
        replace(
            PLUGIN,
            operations=(
                replace(agent, outputs=(output, second), limits=limits),
                *PLUGIN.operations[1:],
            ),
        ),
    )


def test_agent_runtime_validator_requires_worker_visible_semantics() -> None:
    agent = PLUGIN.operations[0]
    output = replace(agent.outputs[0], semantic_contract=None)
    _expect(
        "agent_semantic_contract_missing",
        replace(
            PLUGIN,
            operations=(replace(agent, outputs=(output,)), *PLUGIN.operations[1:]),
        ),
    )


def test_agent_validator_must_reference_the_exact_port_semantic_contract() -> None:
    agent = PLUGIN.operations[0]
    alternate_contract = ComponentSpec(
        "alternate_semantic_contract",
        "resource",
        "architecture_operation_test_plugin.plugin:ARCHITECTURE_SEMANTIC_CONTRACT",
    )
    output = replace(
        agent.outputs[0],
        semantic_contract=ComponentRef("alternate_semantic_contract"),
    )
    _expect(
        "validator_semantic_contract_mismatch",
        replace(
            PLUGIN,
            components=(*PLUGIN.components, alternate_contract),
            operations=(replace(agent, outputs=(output,)), *PLUGIN.operations[1:]),
        ),
    )


def test_agent_checkers_bind_only_declared_semantic_rules() -> None:
    agent = PLUGIN.operations[0]
    output = agent.outputs[0]
    missing = replace(output, validator_rule_id=None)
    _expect(
        "checker_rule_missing",
        replace(
            PLUGIN,
            operations=(replace(agent, outputs=(missing,)), *PLUGIN.operations[1:]),
        ),
    )
    unknown = replace(output, validator_rule_id="fixture.not_declared")
    _expect(
        "checker_rule_unknown",
        replace(
            PLUGIN,
            operations=(replace(agent, outputs=(unknown,)), *PLUGIN.operations[1:]),
        ),
    )


@pytest.mark.parametrize(
    ("implementation", "code"),
    (
        (
            "architecture_operation_test_plugin.plugin:"
            "ARCHITECTURE_LEGACY_SEMANTIC_CONTRACT",
            "semantic_contract_invalid",
        ),
        (
            "architecture_operation_test_plugin.plugin:"
            "ARCHITECTURE_UNKNOWN_INPUT_CONTRACT",
            "semantic_rule_input_unknown",
        ),
    ),
)
def test_agent_semantic_contract_is_structured_and_input_closed(
    implementation: str, code: str
) -> None:
    semantic = next(
        item for item in PLUGIN.components if item.component_id == "semantic_contract"
    ).model_copy(update={"implementation": implementation})
    components = tuple(
        semantic if item.component_id == "semantic_contract" else item
        for item in PLUGIN.components
    )
    _expect(code, replace(PLUGIN, components=components))


def test_semantic_rule_cannot_make_an_optional_port_required() -> None:
    semantic = next(
        item for item in PLUGIN.components if item.component_id == "semantic_contract"
    ).model_copy(
        update={
            "implementation": (
                "architecture_operation_test_plugin.plugin:"
                "ARCHITECTURE_REQUIRED_INPUT_CONTRACT"
            )
        }
    )
    components = tuple(
        semantic if item.component_id == "semantic_contract" else item
        for item in PLUGIN.components
    )
    agent = PLUGIN.operations[0]
    optional_input = agent.inputs[0].model_copy(update={"min_items": 0})
    operations = (
        agent.model_copy(update={"inputs": (optional_input,)}),
        *PLUGIN.operations[1:],
    )
    _expect(
        "semantic_rule_optional_input_required",
        replace(PLUGIN, components=components, operations=operations),
    )


def test_invalid_unicode_in_a_declaration_has_a_stable_digest_error() -> None:
    agent = PLUGIN.operations[0]
    description = replace(agent.description, purpose="\ud800")
    error = _expect(
        "operation_digest_invalid",
        replace(
            PLUGIN,
            operations=(replace(agent, description=description), *PLUGIN.operations[1:]),
        ),
    )
    assert error.plugin_id == "architecture_fixture"
    assert error.operation_id == "builtin.test.agent"
    assert error.field == "digest"


def test_unused_missing_and_wrong_kind_components_are_closed() -> None:
    unused = ComponentSpec(
        "unused_codec", "codec", "architecture_operation_test_plugin.plugin:JSON_CODEC_COMPONENT"
    )
    _expect("component_unused", replace(PLUGIN, components=(*PLUGIN.components, unused)))

    exported = replace(unused, component_id="exported_codec", public=True)
    assert set(compile_catalog(
        (replace(PLUGIN, components=(*PLUGIN.components, exported)),)
    ).operation_ids()) == {item.operation_id for item in PLUGIN.operations}

    agent = PLUGIN.operations[0]
    unknown_port = replace(agent.inputs[0], codec=ComponentRef("unknown_codec"))
    _expect(
        "component_reference_missing",
        replace(PLUGIN, operations=(replace(agent, inputs=(unknown_port,)), *PLUGIN.operations[1:])),
    )

    wrong_executor = replace(
        agent.executor, component=ComponentRef("json_codec")
    )
    _expect(
        "component_kind_mismatch",
        replace(
            PLUGIN,
            operations=(replace(agent, executor=wrong_executor), *PLUGIN.operations[1:]),
        ),
    )
    wrong_abi = replace(
        next(item for item in PLUGIN.components if item.component_id == "test_agent"),
        implementation="architecture_operation_test_plugin.plugin:JSON_CODEC_COMPONENT",
    )
    components = tuple(
        wrong_abi if item.component_id == "test_agent" else item
        for item in PLUGIN.components
    )
    _expect("component_protocol_invalid", replace(PLUGIN, components=components))


def test_schema_resource_is_required_valid_and_identity_matched() -> None:
    agent = PLUGIN.operations[0]
    missing = replace(agent.inputs[0], schema_resource=ComponentRef("missing_schema"))
    _expect(
        "component_reference_missing",
        replace(PLUGIN, operations=(replace(agent, inputs=(missing,)), *PLUGIN.operations[1:])),
    )
    mismatched = replace(agent.inputs[0], schema_id="missing.schema")
    _expect(
        "schema_resource_mismatch",
        replace(PLUGIN, operations=(replace(agent, inputs=(mismatched,)), *PLUGIN.operations[1:])),
    )
    bad_schema = replace(
        next(item for item in PLUGIN.components if item.component_id == "test_schema"),
        implementation="architecture_operation_test_plugin.plugin:ARCHITECTURE_TEST_PROMPT",
    )
    components = tuple(
        bad_schema if item.component_id == "test_schema" else item
        for item in PLUGIN.components
    )
    _expect("schema_resource_invalid", replace(PLUGIN, components=components))


def test_empty_conflicting_and_invalid_ports_are_closed() -> None:
    agent = PLUGIN.operations[0]
    _expect(
        "operation_ports_empty",
        replace(PLUGIN, operations=(replace(agent, inputs=()), *PLUGIN.operations[1:])),
    )
    duplicate_output = replace(agent.outputs[0], name=agent.inputs[0].name)
    _expect(
        "operation_port_duplicate",
        replace(
            PLUGIN,
            operations=(replace(agent, outputs=(duplicate_output,)), *PLUGIN.operations[1:]),
        ),
    )
    invalid_exposure = replace(agent.inputs[0], exposure="ambient")
    _expect(
        "input_exposure_invalid",
        replace(
            PLUGIN,
            operations=(replace(agent, inputs=(invalid_exposure,)), *PLUGIN.operations[1:]),
        ),
    )


def test_agent_authority_cannot_gain_undeclared_or_unbounded_capabilities() -> None:
    agent = PLUGIN.operations[0]
    missing_tool = replace(agent.executor, tools=(ComponentRef("unknown_tool"),))
    _expect(
        "component_reference_missing",
        replace(
            PLUGIN,
            operations=(replace(agent, executor=missing_tool), *PLUGIN.operations[1:]),
        ),
    )
    _expect(
        "agent_authority_incomplete",
        replace(
            PLUGIN,
            operations=(
                replace(agent, executor=replace(agent.executor, prompt=None)),
                *PLUGIN.operations[1:],
            ),
        ),
    )
    unbounded = replace(
        agent.limits, network=NetworkPolicy(mode="all")  # type: ignore[arg-type]
    )
    _expect(
        "network_mode_invalid",
        replace(
            PLUGIN,
            operations=(replace(agent, limits=unbounded), *PLUGIN.operations[1:]),
        ),
    )
    workspace = replace(
        next(item for item in PLUGIN.components if item.component_id == "test_workspace"),
        implementation="builtins:print",
    )
    components = tuple(
        workspace if item.component_id == "test_workspace" else item
        for item in PLUGIN.components
    )
    _expect("component_protocol_invalid", replace(PLUGIN, components=components))


def test_unknown_native_codex_tool_policy_fails_closed() -> None:
    agent = PLUGIN.operations[0]
    executor = replace(
        agent.executor, native_tools=NativeToolPolicy(shell="workspace_write")
    )
    _expect(
        "native_tool_policy_unsupported",
        replace(
            PLUGIN,
            operations=(replace(agent, executor=executor), *PLUGIN.operations[1:]),
        ),
    )


@pytest.mark.parametrize("domain", ("*", ""))
def test_restricted_network_rejects_global_or_empty_domains(domain: str) -> None:
    agent = PLUGIN.operations[0]
    limits = replace(
        agent.limits,
        network=NetworkPolicy(
            mode="restricted", allowed_domains=(domain,), max_requests=1
        ),
    )
    _expect(
        "network_scope_invalid",
        replace(PLUGIN, operations=(replace(agent, limits=limits), *PLUGIN.operations[1:])),
    )


def test_network_tool_and_policy_must_be_declared_together() -> None:
    agent = PLUGIN.operations[0]
    web_tool = ComponentSpec(
        "web_evidence_tool",
        "worker_tool",
        "architecture_operation_test_plugin.plugin:NETWORK_TOOL",
    )
    with_web = replace(
        agent.executor,
        tools=(*agent.executor.tools, ComponentRef("web_evidence_tool")),
    )
    _expect(
        "network_tool_scope_missing",
        replace(
            PLUGIN,
            components=(*PLUGIN.components, web_tool),
            operations=(replace(agent, executor=with_web), *PLUGIN.operations[1:]),
        ),
    )
    restricted = replace(
        agent.limits,
        network=NetworkPolicy(
            mode="restricted", allowed_domains=("example.test",), max_requests=1
        ),
    )
    _expect(
        "network_scope_without_tool",
        replace(
            PLUGIN,
            operations=(replace(agent, limits=restricted), *PLUGIN.operations[1:]),
        ),
    )


def test_port_and_collection_totals_cannot_exceed_operation_limits() -> None:
    agent = PLUGIN.operations[0]
    oversized = replace(agent.outputs[0], max_item_bytes=4097)
    _expect(
        "output_limits_inconsistent",
        replace(PLUGIN, operations=(replace(agent, outputs=(oversized,)), *PLUGIN.operations[1:])),
    )
    transform = PLUGIN.operations[1]
    assert transform.outputs[0].collection is not None
    collection = replace(transform.outputs[0].collection, max_total_bytes=4097)
    oversized_bundle = replace(transform.outputs[0], collection=collection)
    _expect(
        "output_limits_inconsistent",
        replace(
            PLUGIN,
            operations=(PLUGIN.operations[0], replace(transform, outputs=(oversized_bundle,)), PLUGIN.operations[2]),
        ),
    )


def test_cross_plugin_components_require_dependency_and_public_export() -> None:
    agent = PLUGIN.operations[0]
    other = PluginDefinition(
        plugin_id="other",
        version="1",
        protocol_version="1",
        components=(
            ComponentSpec(
                "shared_workspace",
                "workspace",
                "scidiscovery.general_science_components:WORKSPACE",
                public=True,
            ),
        ),
        operations=(),
    )
    executor = replace(
        agent.executor,
        workspace=ComponentRef("shared_workspace", plugin_id="other"),
    )
    plugin = replace(
        PLUGIN,
        operations=(replace(agent, executor=executor), *PLUGIN.operations[1:]),
    )
    _expect("component_cross_plugin_forbidden", plugin, other)

    private_other = replace(
        other,
        components=(replace(other.components[0], public=False),),
    )
    dependent = replace(
        plugin,
        dependencies=(PluginDependency("other", "1"),),
    )
    _expect("component_cross_plugin_forbidden", dependent, private_other)

    wrong_component = replace(
        agent.executor,
        workspace=ComponentRef("missing_workspace", plugin_id="other"),
    )
    _expect(
        "component_reference_missing",
        replace(
            dependent,
            operations=(
                replace(agent, executor=wrong_component),
                *dependent.operations[1:],
            ),
        ),
        other,
    )


def test_missing_plugin_dependency_is_closed() -> None:
    plugin = replace(
        PLUGIN,
        dependencies=(PluginDependency("not_installed", "1"),),
    )
    _expect("plugin_dependency_missing", plugin)


def test_effect_cannot_be_downgraded_or_omit_approval() -> None:
    effect = PLUGIN.operations[2]
    _expect(
        "effect_consequence_invalid",
        replace(
            PLUGIN,
            operations=(*PLUGIN.operations[:2], replace(effect, consequence="scientific")),
        ),
    )
    _expect(
        "external_approval_missing",
        replace(
            PLUGIN,
            operations=(*PLUGIN.operations[:2], replace(effect, review=None)),
        ),
    )
    assert effect.review and effect.review.approval
    bad_approval = replace(effect.review.approval, subject_ports=("missing",))
    _expect(
        "approval_subject_missing",
        replace(
            PLUGIN,
            operations=(
                *PLUGIN.operations[:2],
                replace(effect, review=ReviewSpec(approval=bad_approval)),
            ),
        ),
    )
    reversed_subjects = replace(
        effect.review.approval,
        subject_ports=tuple(reversed(effect.review.approval.subject_ports)),
    )
    _expect(
        "effect_approval_contract_mismatch",
        replace(
            PLUGIN,
            operations=(
                *PLUGIN.operations[:2],
                replace(effect, review=ReviewSpec(approval=reversed_subjects)),
            ),
        ),
    )
    no_projector = replace(effect.review.approval, projector=None)
    _expect(
        "approval_contract_invalid",
        replace(
            PLUGIN,
            operations=(*PLUGIN.operations[:2], replace(effect, review=ReviewSpec(approval=no_projector))),
        ),
    )
    accept_only = replace(
        effect.review.approval,
        options=(effect.review.approval.options[0],),
    )
    _expect(
        "external_approval_options_invalid",
        replace(
            PLUGIN,
            operations=(*PLUGIN.operations[:2], replace(effect, review=ReviewSpec(approval=accept_only))),
        ),
    )
    wrong_projector = replace(
        effect.review.approval, projector=ComponentRef("json_codec")
    )
    _expect(
        "component_kind_mismatch",
        replace(
            PLUGIN,
            operations=(*PLUGIN.operations[:2], replace(effect, review=ReviewSpec(approval=wrong_projector))),
        ),
    )


def test_reviewer_must_exist_and_consume_the_exact_compatible_output() -> None:
    agent = PLUGIN.operations[0]
    missing = ReviewSpec(
        reviewer_operation="missing.reviewer",
        reviewer_input_port="review_target",
        subject_outputs=("agent_output",),
    )
    _expect(
        "reviewer_operation_missing",
        replace(
            PLUGIN,
            operations=(replace(agent, review=missing), *PLUGIN.operations[1:]),
        ),
    )
    incompatible = ReviewSpec(
        reviewer_operation="builtin.test.transform",
        reviewer_input_port="transform_input",
        subject_outputs=("agent_output",),
    )
    _expect(
        "reviewer_not_independent",
        replace(
            PLUGIN,
            operations=(replace(agent, review=incompatible), *PLUGIN.operations[1:]),
        ),
    )


def test_reviewer_with_a_different_codec_is_incompatible() -> None:
    agent, transform, effect = PLUGIN.operations
    reviewer_component = ComponentSpec(
        "review_agent", "agent", "architecture_operation_test_plugin.plugin:AGENT_COMPONENT"
    )
    components = tuple(
        item for item in PLUGIN.components if item.component_id != "test_transform"
    ) + (reviewer_component,)
    reviewer = replace(
        transform,
        executor=ExecutorRef(
            kind="agent",
            component=ComponentRef("review_agent"),
            workspace=agent.executor.workspace,
            prompt=agent.executor.prompt,
            model=agent.executor.model,
        ),
        inputs=(replace(transform.inputs[0], codec=ComponentRef("bundle_codec")),),
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
    _expect(
        "reviewer_port_incompatible",
        replace(PLUGIN, components=components, operations=(producer, reviewer, effect)),
    )


def test_reviewer_cycles_are_closed() -> None:
    agent, transform, effect = PLUGIN.operations
    second_agent_component = ComponentSpec(
        "second_agent",
        "agent",
        "architecture_operation_test_plugin.plugin:AGENT_COMPONENT",
    )
    first_review = ReviewSpec(
        reviewer_operation=transform.operation_id,
        reviewer_input_port="transform_input",
        subject_outputs=("agent_output",),
    )
    second_review = ReviewSpec(
        reviewer_operation=agent.operation_id,
        reviewer_input_port="agent_input",
        subject_outputs=("transform_output",),
    )
    second_executor = ExecutorRef(
        kind="agent",
        component=ComponentRef("second_agent"),
        workspace=agent.executor.workspace,
        prompt=agent.executor.prompt,
        model=agent.executor.model,
    )
    plugin = replace(
        PLUGIN,
        components=tuple(
            component
            for component in PLUGIN.components
            if component.component_id != "bundle_codec"
        ) + (second_agent_component,),
        operations=(
            replace(agent, review=first_review),
            replace(
                transform,
                executor=second_executor,
                inputs=(
                    replace(
                        transform.inputs[0],
                        schema_id=agent.outputs[0].schema_id,
                        schema_resource=agent.outputs[0].schema_resource,
                        codec=agent.outputs[0].codec,
                        media_types=agent.outputs[0].media_types,
                    ),
                ),
                outputs=(replace(
                    transform.outputs[0],
                    codec=ComponentRef("json_codec"),
                    min_items=1,
                    max_items=1,
                    max_item_bytes=4096,
                    collection=None,
                ),),
                review=second_review,
            ),
            effect,
        ),
    )
    _expect("reviewer_cycle", plugin)
