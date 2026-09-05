"""Self-contained architecture Operation test fixture."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from scidiscovery.artifact_agent.schema.approval import (
    ReviewDocument,
    ReviewDocumentItem,
    ReviewDocumentSection,
)
from scidiscovery.artifact_agent.schema.execution import ExecutionRequest
from scidiscovery.operation_contract import SemanticRuleViolation
from scidiscovery.operation_declaration import semantic_contract
from scidiscovery.operations.invoke import ApprovalProjectorContext, EffectExecutorPlan
from scidiscovery.operations.spec import (
    PLUGIN_PROTOCOL_VERSION,
    ApprovalContract,
    ApprovalOption,
    CallableComponent,
    CollectionSpec,
    ComponentRef,
    ComponentSpec,
    ExecutorRef,
    InputPortSpec,
    LimitsSpec,
    NativeToolPolicy,
    OperationDescription,
    OperationSpec,
    OutputPortSpec,
    PluginDefinition,
    ReviewSpec,
    SemanticRuleSpec,
    WorkspaceContract,
)
from scidiscovery.operations.tooling import WorkerToolDefinition
from scidiscovery.artifact_agent.interfaces.mcp_worker_protocol import (
    FILE_JSON_PATCH_TOOL,
)


ARCHITECTURE_TEST_PROMPT = """You are running one architecture-only operation.
Use only the tools allowed by this Agent type. Claim and materialize the queued
assignment, then use one Codex native code tool to read assignment.json without
modifying any file. Read the exact input at its declared task-relative path with
the same native read-only tool, then call
worker_fixture_inspect with value "registered-domain-tool". Confirm from the
assignment that native writes, network, and undeclared tools are forbidden for
this Operation even if the runtime shows them. Create output/result.json only through the
worker_file_write_begin/chunk/commit lifecycle. Write this exact JSON value on
the first create, with no additional fields:
{"schema_version":1,"handoff":{"verdict":"pass","summary":"Architecture operation completed."},"payload":{"input_seen":true,"network_denied":true,"sibling_read_denied":true,"tool_result":"fixture-inspected:registered-domain-tool"}}
Do not copy the input object or the tool response wrapper into these fields.
Then call worker_submit_result.
Do not use native tools to write, patch, access the network, or inspect files
outside this task. Do not use image, delegation, skills, another operation's
Worker MCP server, or any undeclared tool. The control plane validates the exact
result and registered domain-tool receipt."""
ARCHITECTURE_TEST_SCHEMA = (
    '{"$id":"scidiscovery.architecture-test.v1","additionalProperties":true,'
    '"type":"object"}'
)
ARCHITECTURE_AGENT_RESULT_SCHEMA = json.dumps(
    {
        "$id": "scidiscovery.architecture-agent-result.v1",
        "additionalProperties": False,
        "properties": {
            "input_seen": {"const": True},
            "network_denied": {"const": True},
            "sibling_read_denied": {"const": True},
            "tool_result": {"const": "fixture-inspected:registered-domain-tool"},
        },
        "required": [
            "input_seen",
            "network_denied",
            "sibling_read_denied",
            "tool_result",
        ],
        "type": "object",
    },
    ensure_ascii=True,
    separators=(",", ":"),
    sort_keys=True,
)
ARCHITECTURE_INTAKE_SCHEMA = (
    '{"$id":"scidiscovery.scientific-intake.v1","type":"object"}'
)
ARCHITECTURE_SEMANTIC_CONTRACT = semantic_contract(
    SemanticRuleSpec(
        rule_id="fixture.payload",
        description="The output must pass the validator bound to this exact port.",
    ),
    SemanticRuleSpec(
        rule_id="fixture.context",
        description=(
            "Any declared context sources and collection members must satisfy "
            "the port's compiled contextual and bundle validators."
        ),
    ),
)
ARCHITECTURE_REQUIRED_INPUT_CONTRACT = semantic_contract(
    SemanticRuleSpec(
        rule_id="fixture.required_input",
        description="The output is bound to the exact declared Agent input.",
        required_inputs=("agent_input",),
    )
)
ARCHITECTURE_UNKNOWN_INPUT_CONTRACT = semantic_contract(
    SemanticRuleSpec(
        rule_id="fixture.unknown_input",
        description="This deliberately references an undeclared input.",
        required_inputs=("missing_input",),
    )
)
ARCHITECTURE_LEGACY_SEMANTIC_CONTRACT = json.dumps(
    {"rules": ["A legacy free-text rule is no longer a compiled contract."]},
    separators=(",", ":"),
    sort_keys=True,
)
_execution_schema = ExecutionRequest.model_json_schema(mode="validation")
_execution_schema["$id"] = "scidiscovery.execution-request"
EXECUTION_REQUEST_SCHEMA = json.dumps(
    _execution_schema, ensure_ascii=True, separators=(",", ":"), sort_keys=True
)


class FixtureInspectInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    value: str = Field(min_length=1, max_length=128)


def architecture_test_agent() -> None:
    return None


def architecture_test_transform(
    values: dict[str, tuple[bytes, ...]],
) -> dict[str, tuple[bytes, ...]]:
    return {"transform_output": values["transform_input"]}


def architecture_test_effect() -> EffectExecutorPlan:
    return EffectExecutorPlan(
        executor="fixture",
        preparation_profile="fixture.no-effect.v1",
        payload_port="effect_input",
    )


def json_codec(value: bytes) -> bytes:
    return value


def nonempty_validator(value: bytes) -> None:
    if not value:
        raise SemanticRuleViolation("output must not be empty")


def architecture_agent_result_validator(value: bytes) -> None:
    try:
        payload = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SemanticRuleViolation(
            "architecture Agent output is invalid JSON"
        ) from error
    if payload != {
        "input_seen": True,
        "network_denied": True,
        "sibling_read_denied": True,
        "tool_result": "fixture-inspected:registered-domain-tool",
    }:
        raise SemanticRuleViolation("architecture Agent did not use its registered tool")


def architecture_context_validator(
    payload: dict[str, Any], sources: dict[str, bytes], handoff: dict[str, Any]
) -> None:
    if set(sources) != {"agent_input"} or not sources["agent_input"]:
        raise SemanticRuleViolation(
            "architecture Agent did not retain its exact input context"
        )
    if payload.get("input_seen") is not True or handoff.get("verdict") != "pass":
        raise SemanticRuleViolation("architecture Agent context result is inconsistent")


def architecture_bundle_validator(
    primary: dict[str, Any],
    items: dict[str, bytes],
    validation_context: object | None = None,
) -> None:
    del validation_context
    payload = primary.get("payload")
    if (
        not isinstance(payload, dict)
        or payload.get("input_seen") is not True
        or set(items) != {"receipts/receipt.json"}
    ):
        raise ValueError("architecture Agent collection is inconsistent")


def fixture_inspect(request: BaseModel) -> dict[str, str]:
    if not isinstance(request, FixtureInspectInput):
        raise ValueError("fixture tool received the wrong input model")
    return {"inspection": f"fixture-inspected:{request.value}"}


def architecture_test_projector(
    context: ApprovalProjectorContext,
) -> ReviewDocument:
    if (
        context.operation_id != "builtin.test.effect"
        or tuple(item.port_name for item in context.subjects)
        != ("effect_request", "effect_input")
    ):
        raise ValueError("architecture execution review requires request and payload")
    request = ExecutionRequest.model_validate_json(
        context.subjects[0].content, strict=True
    )
    if request.compiled_identity is None:
        raise ValueError("architecture execution request has no compiled identity")
    return ReviewDocument(
        title="无副作用架构执行审批",
        description="核对已编译执行合同和冻结测试输入。",
        sections=(
            ReviewDocumentSection(
                title="执行合同",
                items=(
                    ReviewDocumentItem(
                        kind="json_value",
                        label="执行器",
                        subject_index=0,
                        json_pointer="/executor",
                    ),
                    ReviewDocumentItem(
                        kind="json_value",
                        label="准备合同",
                        subject_index=0,
                        json_pointer="/preparation_profile",
                    ),
                    ReviewDocumentItem(
                        kind="json_value",
                        label="操作",
                        subject_index=0,
                        json_pointer="/compiled_identity/operation_id",
                    ),
                ),
            ),
            ReviewDocumentSection(
                title="冻结输入",
                items=(
                    ReviewDocumentItem(
                        kind="json_tree",
                        label="完整测试输入",
                        subject_index=1,
                        json_pointer="",
                    ),
                ),
            ),
        ),
    )


def architecture_approval_projector(
    context: ApprovalProjectorContext,
) -> ReviewDocument:
    if len(context.subjects) != 1 or context.subjects[0].port_name != "subject":
        raise ValueError("architecture approval requires one exact subject")
    return ReviewDocument(
        title="架构审批测试",
        description="只展示已冻结输入。",
        sections=(
            ReviewDocumentSection(
                title="审批对象",
                items=(
                    ReviewDocumentItem(
                        kind="json_tree",
                        label="完整对象",
                        subject_index=0,
                        json_pointer="",
                    ),
                ),
            ),
        ),
    )


AGENT_COMPONENT = CallableComponent("agent", architecture_test_agent)
TRANSFORM_COMPONENT = CallableComponent("transform", architecture_test_transform)
EFFECT_COMPONENT = CallableComponent("effect", architecture_test_effect)
JSON_CODEC_COMPONENT = CallableComponent("codec", json_codec)
BUNDLE_CODEC_COMPONENT = CallableComponent("codec", json_codec)
VALIDATOR_COMPONENT = CallableComponent("validator", nonempty_validator)
AGENT_RESULT_VALIDATOR_COMPONENT = CallableComponent(
    "validator", architecture_agent_result_validator
)
CONTEXT_VALIDATOR_COMPONENT = CallableComponent(
    "validator", architecture_context_validator
)
BUNDLE_VALIDATOR_COMPONENT = CallableComponent(
    "validator", architecture_bundle_validator
)
PROJECTOR_COMPONENT = CallableComponent("projector", architecture_test_projector)
APPROVAL_PROJECTOR_COMPONENT = CallableComponent(
    "projector", architecture_approval_projector
)
FIXTURE_INSPECT_TOOL = WorkerToolDefinition(
    name="worker_fixture_inspect",
    description="Inspect one bounded architecture-test token.",
    input_model=FixtureInspectInput,
    capability="fixture.inspect",
    handler=fixture_inspect,
)
FIXTURE_INSPECT_TOOL_ALTERNATE = WorkerToolDefinition(
    name="worker_fixture_inspect",
    description="Inspect one alternate bounded architecture-test token.",
    input_model=FixtureInspectInput,
    capability="fixture.inspect.alternate",
    handler=fixture_inspect,
)
COLLIDING_OPEN_TOOL = WorkerToolDefinition(
    name="worker_open_assignment",
    description="Deliberately collide with the compiler-owned lifecycle in tests.",
    input_model=FixtureInspectInput,
    capability="fixture.illegal_lifecycle_override",
    handler=fixture_inspect,
)
NETWORK_TOOL = WorkerToolDefinition(
    name="worker_fixture_network",
    description="Declare network access for catalog-policy tests.",
    input_model=FixtureInspectInput,
    capability="fixture.network",
    handler=fixture_inspect,
    network_access=True,
)
JSON_PATCH_TOOL = FILE_JSON_PATCH_TOOL
ARCHITECTURE_TEST_WORKSPACE = WorkspaceContract()


_JSON = ComponentRef("json_codec")
_SCHEMA = ComponentRef("test_schema")
_VALIDATOR = ComponentRef("nonempty_validator")
_SEMANTIC = ComponentRef("semantic_contract")
_LIMITS = LimitsSpec(
    timeout_seconds=300,
    max_input_bytes=4096,
    max_output_bytes=4096,
    max_files=2,
)


def _input(name: str) -> InputPortSpec:
    return InputPortSpec(
        name=name,
        description="Bound architecture-test input",
        schema="scidiscovery.architecture-test.v1",
        media_types=("application/json",),
        codec=_JSON,
        schema_resource=_SCHEMA,
        exposure="full",
        usage="claim_evidence",
        max_item_bytes=4096,
    )


def _output(
    name: str,
    kind: str,
    *,
    schema_id: str = "scidiscovery.architecture-test.v1",
    schema_resource: ComponentRef = _SCHEMA,
    collection: CollectionSpec | None = None,
) -> OutputPortSpec:
    return OutputPortSpec(
        name=name,
        description="Bound architecture-test output",
        kind=kind,
        schema=schema_id,
        media_types=("application/json",),
        codec=_JSON,
        schema_resource=schema_resource,
        max_item_bytes=4096,
        validator=_VALIDATOR,
        validator_rule_id="fixture.payload",
        semantic_contract=_SEMANTIC,
        collection=collection,
    )


ARCHITECTURE_TEST_PLUGIN = PluginDefinition(
    plugin_id="architecture_fixture",
    version="0.1.0",
    protocol_version=PLUGIN_PROTOCOL_VERSION,
    components=(
        ComponentSpec(
            "json_codec", "codec", "architecture_operation_test_plugin.plugin:JSON_CODEC_COMPONENT"
        ),
        ComponentSpec(
            "bundle_codec", "codec", "architecture_operation_test_plugin.plugin:BUNDLE_CODEC_COMPONENT"
        ),
        ComponentSpec(
            "nonempty_validator",
            "validator",
            "architecture_operation_test_plugin.plugin:VALIDATOR_COMPONENT",
            resources=(ComponentRef("semantic_contract"),),
        ),
        ComponentSpec(
            "agent_result_validator",
            "validator",
            "architecture_operation_test_plugin.plugin:AGENT_RESULT_VALIDATOR_COMPONENT",
            resources=(ComponentRef("semantic_contract"),),
        ),
        ComponentSpec(
            "context_validator",
            "validator",
            "architecture_operation_test_plugin.plugin:CONTEXT_VALIDATOR_COMPONENT",
            resources=(ComponentRef("semantic_contract"),),
        ),
        ComponentSpec(
            "test_agent", "agent", "architecture_operation_test_plugin.plugin:AGENT_COMPONENT"
        ),
        ComponentSpec(
            "test_transform",
            "transform",
            "architecture_operation_test_plugin.plugin:TRANSFORM_COMPONENT",
        ),
        ComponentSpec(
            "test_effect", "effect", "architecture_operation_test_plugin.plugin:EFFECT_COMPONENT"
        ),
        ComponentSpec(
            "test_workspace",
            "workspace",
            "architecture_operation_test_plugin.plugin:ARCHITECTURE_TEST_WORKSPACE",
        ),
        ComponentSpec(
            "test_prompt",
            "resource",
            "architecture_operation_test_plugin.plugin:ARCHITECTURE_TEST_PROMPT",
        ),
        ComponentSpec(
            "test_schema",
            "resource",
            "architecture_operation_test_plugin.plugin:ARCHITECTURE_TEST_SCHEMA",
        ),
        ComponentSpec(
            "agent_result_schema",
            "resource",
            "architecture_operation_test_plugin.plugin:ARCHITECTURE_AGENT_RESULT_SCHEMA",
        ),
        ComponentSpec(
            "semantic_contract",
            "resource",
            "architecture_operation_test_plugin.plugin:ARCHITECTURE_SEMANTIC_CONTRACT",
        ),
        ComponentSpec(
            "execution_request_schema",
            "resource",
            "architecture_operation_test_plugin.plugin:EXECUTION_REQUEST_SCHEMA",
        ),
        ComponentSpec(
            "test_projector",
            "projector",
            "architecture_operation_test_plugin.plugin:PROJECTOR_COMPONENT",
        ),
        ComponentSpec(
            "file_write_begin_tool",
            "worker_tool",
            "scidiscovery.artifact_agent.interfaces.mcp_worker_protocol:FILE_WRITE_BEGIN_TOOL",
            public=True,
        ),
        ComponentSpec(
            "file_write_chunk_tool",
            "worker_tool",
            "scidiscovery.artifact_agent.interfaces.mcp_worker_protocol:FILE_WRITE_CHUNK_TOOL",
            public=True,
        ),
        ComponentSpec(
            "file_write_commit_tool",
            "worker_tool",
            "scidiscovery.artifact_agent.interfaces.mcp_worker_protocol:FILE_WRITE_COMMIT_TOOL",
            public=True,
        ),
        ComponentSpec(
            "fixture_inspect_tool",
            "worker_tool",
            "architecture_operation_test_plugin.plugin:FIXTURE_INSPECT_TOOL",
        ),
    ),
    operations=(
        OperationSpec(
            operation_id="builtin.test.agent",
            version="1",
            catalog_scope="public",
            description=OperationDescription(
                purpose="Verify an Agent operation's compiled authority closure.",
                applies_when="Testing the operation compiler in isolation.",
                not_for="Scientific work or production dispatch.",
            ),
            executor=ExecutorRef(
                kind="agent",
                component=ComponentRef("test_agent"),
                workspace=ComponentRef("test_workspace"),
                tools=(
                    ComponentRef("file_write_begin_tool"),
                    ComponentRef("file_write_chunk_tool"),
                    ComponentRef("file_write_commit_tool"),
                    ComponentRef("fixture_inspect_tool"),
                ),
                prompt=ComponentRef("test_prompt"),
                model="gpt-5.4",
                native_tools=NativeToolPolicy(shell="inherited_prototype"),
            ),
            inputs=(_input("agent_input"),),
            outputs=(
                _output(
                    "agent_output",
                    "architecture_agent_result",
                    schema_id="scidiscovery.architecture-agent-result.v1",
                    schema_resource=ComponentRef("agent_result_schema"),
                ).model_copy(
                    update={
                        "validator": ComponentRef("agent_result_validator"),
                        "context_validator": ComponentRef("context_validator"),
                        "context_rule_id": "fixture.context",
                        "context_sources": ("agent_input",),
                    }
                ),
            ),
            consequence="explore",
            limits=_LIMITS,
        ),
        OperationSpec(
            operation_id="builtin.test.transform",
            version="1",
            catalog_scope="public",
            description=OperationDescription(
                purpose="Verify a deterministic Transform operation can compile.",
                applies_when="Testing the operation compiler in isolation.",
                not_for="Scientific transformation or production use.",
            ),
            executor=ExecutorRef(
                kind="transform", component=ComponentRef("test_transform")
            ),
            inputs=(_input("transform_input"),),
            outputs=(
                _output(
                    "transform_output",
                    "architecture_test_transform_output",
                    collection=CollectionSpec(max_total_bytes=4096),
                ).model_copy(update={
                    "codec": ComponentRef("bundle_codec"),
                    "max_items": 2,
                    "max_item_bytes": 2048,
                }),
            ),
            consequence="scientific",
            limits=_LIMITS,
        ),
        OperationSpec(
            operation_id="builtin.test.effect",
            version="1",
            catalog_scope="public",
            description=OperationDescription(
                purpose="Verify an external Effect cannot compile without review closure.",
                applies_when="Testing the operation compiler in isolation.",
                not_for="Real execution or any external side effect.",
            ),
            executor=ExecutorRef(kind="effect", component=ComponentRef("test_effect")),
            inputs=(_input("effect_input"),),
            outputs=(
                _output(
                    "effect_request",
                    "execution_request",
                    schema_id="scidiscovery.execution-request",
                    schema_resource=ComponentRef("execution_request_schema"),
                ),
            ),
            consequence="external",
            review=ReviewSpec(
                approval=ApprovalContract(
                    subject_ports=("effect_request", "effect_input"),
                    question="Allow this no-effect architecture test request?",
                    options=(
                        ApprovalOption("Allow", "accept"),
                        ApprovalOption("Reject", "reject"),
                    ),
                    projector=ComponentRef("test_projector"),
                )
            ),
            limits=_LIMITS,
        ),
    ),
)
