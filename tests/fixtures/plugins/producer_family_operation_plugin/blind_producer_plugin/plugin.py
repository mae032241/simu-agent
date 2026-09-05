"""Declarations for a domain that the generic framework cannot name or special-case."""

from __future__ import annotations

from scidiscovery.operations.spec import (
    PLUGIN_PROTOCOL_VERSION,
    ApprovalContract,
    ApprovalOption,
    CollectionSpec,
    ComponentRef,
    ComponentSpec,
    ExecutorRef,
    InputPortSpec,
    LimitsSpec,
    OperationDescription,
    OperationSpec,
    OutputPortSpec,
    PluginDependency,
    PluginDefinition,
    ReviewSpec,
)


def _ref(component_id: str, plugin_id: str | None = None) -> ComponentRef:
    return ComponentRef(component_id, plugin_id)


def _input(
    name: str,
    schema: str,
    resource: str,
    *,
    usage: str = "prior_signal",
    min_items: int = 1,
    max_items: int = 1,
) -> InputPortSpec:
    return InputPortSpec(
        name=name,
        description=f"Blind fixture input {name}.",
        schema=schema,
        media_types=("application/json",),
        codec=_ref("json_codec"),
        schema_resource=_ref(resource),
        usage=usage,
        exposure="full",
        min_items=min_items,
        max_items=max_items,
        max_item_bytes=4096,
    )


def _output(
    name: str,
    kind: str,
    schema: str,
    resource: str,
    validator: str,
    *,
    collection: bool = False,
) -> OutputPortSpec:
    return OutputPortSpec(
        name=name,
        description=f"Blind fixture output {name}.",
        schema=schema,
        media_types=("application/json",),
        codec=_ref("json_codec"),
        schema_resource=_ref(resource),
        kind=kind,
        validator=_ref(validator),
        validator_rule_id="producer.output",
        semantic_contract=_ref("semantic_contract"),
        min_items=1,
        max_items=2 if collection else 1,
        max_item_bytes=4096,
        collection=CollectionSpec(max_total_bytes=8192) if collection else None,
    )


LIMITS = LimitsSpec(
    timeout_seconds=120,
    max_input_bytes=16384,
    max_output_bytes=16384,
    max_files=4,
)


def _description(action: str) -> OperationDescription:
    return OperationDescription(
        purpose=f"Exercise a blind plugin {action}.",
        applies_when="The exact blind fixture inputs are available.",
        not_for="Production scientific use.",
    )


PLUGIN = PluginDefinition(
    plugin_id="blind_producer_fixture",
    version="0.0.1",
    protocol_version=PLUGIN_PROTOCOL_VERSION,
    dependencies=(PluginDependency("builtin", "0.1.0"),),
    components=(
        ComponentSpec("json_codec", "codec", "blind_producer_plugin.runtime:JSON_CODEC"),
        ComponentSpec(
            "object_validator",
            "validator",
            "blind_producer_plugin.runtime:OBJECT_VALIDATOR",
            resources=(_ref("semantic_contract"),),
        ),
        ComponentSpec(
            "review_validator",
            "validator",
            "blind_producer_plugin.runtime:REVIEW_VALIDATOR",
            resources=(_ref("semantic_contract"),),
        ),
        ComponentSpec("producer", "transform", "blind_producer_plugin.runtime:PRODUCER"),
        ComponentSpec(
            "revision_agent", "agent", "blind_producer_plugin.runtime:REVISION_AGENT"
        ),
        ComponentSpec(
            "review_agent", "agent", "blind_producer_plugin.runtime:REVIEW_AGENT"
        ),
        ComponentSpec(
            "approval_projector",
            "projector",
            "blind_producer_plugin.runtime:APPROVAL_PROJECTOR",
        ),
        ComponentSpec(
            "workspace", "workspace", "blind_producer_plugin.runtime:WORKSPACE"
        ),
        ComponentSpec("prompt", "resource", "blind_producer_plugin.runtime:PROMPT"),
        ComponentSpec(
            "semantic_contract",
            "resource",
            "blind_producer_plugin.runtime:SEMANTIC_CONTRACT",
        ),
        *(
            ComponentSpec(
                name,
                "resource",
                f"blind_producer_plugin.runtime:{symbol}",
            )
            for name, symbol in (
                ("source_schema", "SOURCE_SCHEMA"),
                ("object_schema", "OBJECT_SCHEMA"),
                ("review_schema", "REVIEW_SCHEMA"),
            )
        ),
    ),
    operations=(
        OperationSpec(
            operation_id="blind.domain.produce.v1",
            version="1",
            catalog_scope="public",
            description=_description("production"),
            executor=ExecutorRef(kind="transform", component=_ref("producer")),
            inputs=(_input("seed", "blind.source.v1", "source_schema"),),
            outputs=(
                _output(
                    "specimen",
                    "blind_object",
                    "blind.object.v1",
                    "object_schema",
                    "object_validator",
                ),
                _output(
                    "notes",
                    "blind_attachment",
                    "blind.object.v1",
                    "object_schema",
                    "object_validator",
                    collection=True,
                ),
            ),
            consequence="scientific",
            review=ReviewSpec(
                reviewer_operation="blind.domain.review.v1",
                reviewer_input_port="candidate",
                subject_outputs=("specimen",),
            ),
            limits=LIMITS,
        ),
        OperationSpec(
            operation_id="blind.domain.review.v1",
            version="1",
            catalog_scope="public",
            description=_description("independent review"),
            executor=ExecutorRef(
                kind="agent",
                component=_ref("review_agent"),
                workspace=_ref("workspace"),
                tools=(
                    _ref("file_write_begin_tool", "builtin"),
                    _ref("file_write_chunk_tool", "builtin"),
                    _ref("file_write_commit_tool", "builtin"),
                ),
                prompt=_ref("prompt"),
                model="gpt-5.4",
            ),
            inputs=(
                _input(
                    "candidate",
                    "blind.object.v1",
                    "object_schema",
                    usage="prior_signal",
                ),
            ),
            outputs=(
                _output(
                    "review",
                    "blind_review",
                    "blind.review.v1",
                    "review_schema",
                    "review_validator",
                ),
            ),
            consequence="scientific",
            limits=LIMITS,
        ),
        OperationSpec(
            operation_id="blind.domain.revision.propose.v1",
            version="1",
            catalog_scope="public",
            description=_description("revision proposal"),
            executor=ExecutorRef(
                kind="agent",
                component=_ref("revision_agent"),
                workspace=_ref("workspace"),
                tools=(
                    _ref("file_write_begin_tool", "builtin"),
                    _ref("file_write_chunk_tool", "builtin"),
                    _ref("file_write_commit_tool", "builtin"),
                ),
                prompt=_ref("prompt"),
                model="gpt-5.4",
            ),
            inputs=(
                _input(
                    "ancestor",
                    "blind.object.v1",
                    "object_schema",
                    usage="revision_base",
                ),
                _input(
                    "critique",
                    "blind.review.v1",
                    "review_schema",
                    usage="change_request",
                ),
            ),
            outputs=(
                _output(
                    "specimen",
                    "blind_object",
                    "blind.object.v1",
                    "object_schema",
                    "object_validator",
                ),
            ),
            consequence="scientific",
            review=ReviewSpec(
                reviewer_operation="blind.domain.review.v1",
                reviewer_input_port="candidate",
                subject_outputs=("specimen",),
            ),
            limits=LIMITS,
        ),
        OperationSpec(
            operation_id="blind.domain.qualify.v1",
            version="1",
            catalog_scope="public",
            description=_description("approval"),
            executor=ExecutorRef(
                kind="approval", component=_ref("approval_projector")
            ),
            inputs=(
                _input("candidate", "blind.object.v1", "object_schema"),
                _input(
                    "companions",
                    "blind.object.v1",
                    "object_schema",
                    min_items=0,
                    max_items=2,
                ),
                _input(
                    "review",
                    "blind.review.v1",
                    "review_schema",
                    usage="prior_signal",
                ),
            ),
            outputs=(),
            consequence="scientific",
            review=ReviewSpec(
                approval=ApprovalContract(
                    subject_ports=("candidate", "companions", "review"),
                    question="是否接受盲插件声明的完整生产者族？",
                    options=(
                        ApprovalOption("接受", "accept"),
                        ApprovalOption("退回", "revise", requires_reason=True),
                    ),
                    projector=_ref("approval_projector"),
                    kind="scientific_foundation",
                )
            ),
            limits=LIMITS,
        ),
    ),
)


__all__ = ["PLUGIN"]
