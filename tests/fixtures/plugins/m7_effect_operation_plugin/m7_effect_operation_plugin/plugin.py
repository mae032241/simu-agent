"""One public installed Effect with one startup-registered adapter."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from scidiscovery.artifact_agent.schema.approval import (
    ReviewDocument,
    ReviewDocumentItem,
    ReviewDocumentSection,
)
from scidiscovery.artifact_agent.schema.execution import (
    ExecutionRequest,
    LocalFileDescriptor,
)
from scidiscovery.operations.invoke import ApprovalProjectorContext, EffectExecutorPlan
from scidiscovery.operations.runtime_plugins import (
    RuntimePluginContext,
    RuntimePluginContribution,
    RuntimePluginFactory,
)
from scidiscovery.operations.spec import (
    PLUGIN_PROTOCOL_VERSION,
    ApprovalContract,
    ApprovalOption,
    CallableComponent,
    ComponentRef,
    ComponentSpec,
    ExecutorRef,
    InputPortSpec,
    LimitsSpec,
    OperationDescription,
    OperationSpec,
    OutputPortSpec,
    PluginDefinition,
    PluginDependency,
    ReviewSpec,
)


FIXTURE_ID = "m7-installed-effect-v1"
OPERATION_ID = "m7.fixture.frozen-copy.v1"
PREPARATION_PROFILE = "m7.fixture-frozen-copy.v1"
QUALIFIED_ADAPTER_ID = "m7_effect_fixture:adapter"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class EffectRequest(_StrictModel):
    schema_version: Literal[1]
    fixture_id: Literal[FIXTURE_ID]


class EffectRuntimeConfig(_StrictModel):
    frozen_output_path: str = Field(min_length=1, max_length=4096)
    frozen_output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _path_is_absolute(self) -> Self:
        if not Path(self.frozen_output_path).is_absolute():
            raise ValueError("frozen output path must be absolute")
        return self


def _schema(model: type[BaseModel], schema_id: str) -> str:
    value = model.model_json_schema(mode="validation")
    value["$id"] = schema_id
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def json_codec(value: bytes) -> bytes:
    return value


def effect_plan() -> EffectExecutorPlan:
    return EffectExecutorPlan(
        executor="adapter",
        preparation_profile=PREPARATION_PROFILE,
        payload_port="request",
    )


def approval_projector(context: ApprovalProjectorContext) -> ReviewDocument:
    if (
        context.operation_id != OPERATION_ID
        or tuple(item.port_name for item in context.subjects)
        != ("execution_request", "request")
    ):
        raise ValueError("M7 Effect approval has different subjects")
    execution = ExecutionRequest.model_validate_json(
        context.subjects[0].content, strict=True
    )
    EffectRequest.model_validate_json(context.subjects[1].content, strict=True)
    if (
        execution.executor != QUALIFIED_ADAPTER_ID
        or execution.preparation_profile != PREPARATION_PROFILE
        or execution.compiled_identity is None
        or execution.compiled_identity.operation_id != context.operation_id
        or execution.compiled_identity.operation_version != context.operation_version
        or execution.compiled_identity.operation_digest != context.operation_digest
    ):
        raise ValueError("M7 Effect request has a different compiled identity")
    return ReviewDocument(
        title="M7 冻结文件复制审批",
        description="只授权测试适配器复制一个已冻结文件；不运行求解器。",
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
                        kind="json_tree",
                        label="冻结请求",
                        subject_index=1,
                        json_pointer="",
                    ),
                ),
            ),
        ),
    )


class FrozenCopyAdapter:
    def __init__(self, source: Path, expected_sha256: str) -> None:
        self.source = source.resolve()
        self.expected_sha256 = expected_sha256
        self.exchange_directory: Path | None = None
        self.submission: tuple[str, str] | None = None

    @staticmethod
    def supports_preparation_profile(profile: str) -> bool:
        return profile == PREPARATION_PROFILE

    @staticmethod
    def validate_preparation_payload(
        raw: bytes, *, preparation_profile: str
    ) -> None:
        if preparation_profile != PREPARATION_PROFILE:
            raise ValueError("unsupported M7 Effect preparation profile")
        EffectRequest.model_validate_json(raw, strict=True)

    def prepare(
        self,
        payload: LocalFileDescriptor,
        *,
        preparation_profile: str,
        exchange_directory: Path,
    ) -> LocalFileDescriptor:
        self.validate_preparation_payload(
            Path(payload.local_path).read_bytes(),
            preparation_profile=preparation_profile,
        )
        self.exchange_directory = exchange_directory.resolve()
        return payload

    def submit(self, _submission: LocalFileDescriptor) -> tuple[str, str]:
        self.submission = ("m7-frozen-copy", "accepted")
        return self.submission

    def lookup_submission(
        self, _submission: LocalFileDescriptor
    ) -> tuple[str, str] | None:
        return self.submission

    @staticmethod
    def status(external_run_id: str) -> str:
        if external_run_id != "m7-frozen-copy":
            raise ValueError("unknown M7 Effect run")
        return "succeeded"

    @staticmethod
    def cancel(external_run_id: str) -> str:
        if external_run_id != "m7-frozen-copy":
            raise ValueError("unknown M7 Effect run")
        return "cancelled"

    def collect(self, external_run_id: str) -> tuple[LocalFileDescriptor, ...]:
        if external_run_id != "m7-frozen-copy":
            raise ValueError("unknown M7 Effect run")
        if self.exchange_directory is None:
            raise RuntimeError("M7 Effect was not prepared")
        raw = self.source.read_bytes()
        if hashlib.sha256(raw).hexdigest() != self.expected_sha256:
            raise ValueError("frozen M7 Effect output changed")
        target = self.exchange_directory / "m7-effect-output.txt"
        shutil.copyfile(self.source, target)
        return (
            LocalFileDescriptor(
                name="receipt.txt",
                local_path=str(target),
                sha256=self.expected_sha256,
                size_bytes=len(raw),
                media_type="text/plain; charset=utf-8",
            ),
        )


def build_runtime(context: RuntimePluginContext) -> RuntimePluginContribution:
    config = EffectRuntimeConfig.model_validate_json(context.config_bytes, strict=True)
    if context.mode != "control":
        return RuntimePluginContribution()
    return RuntimePluginContribution(
        execution_adapters={
            "adapter": FrozenCopyAdapter(
                Path(config.frozen_output_path), config.frozen_output_sha256
            )
        }
    )


_execution_schema = ExecutionRequest.model_json_schema(mode="validation")
_execution_schema["$id"] = "scidiscovery.execution-request"

PLUGIN = PluginDefinition(
    plugin_id="m7_effect_fixture",
    version="0.0.1",
    protocol_version=PLUGIN_PROTOCOL_VERSION,
    dependencies=(
        PluginDependency("builtin", "0.1.0"),
        PluginDependency("general_science", "0.1.0"),
    ),
    configuration_schema=ComponentRef("configuration_schema"),
    runtime_factory=ComponentRef("runtime_factory"),
    components=(
        ComponentSpec(
            "json_codec",
            "codec",
            "m7_effect_operation_plugin.plugin:JSON_CODEC",
        ),
        ComponentSpec(
            "request_schema",
            "resource",
            "m7_effect_operation_plugin.plugin:REQUEST_SCHEMA",
        ),
        ComponentSpec(
            "execution_request_schema",
            "resource",
            "m7_effect_operation_plugin.plugin:EXECUTION_REQUEST_SCHEMA",
        ),
        ComponentSpec(
            "configuration_schema",
            "resource",
            "m7_effect_operation_plugin.plugin:CONFIGURATION_SCHEMA",
        ),
        ComponentSpec(
            "runtime_factory",
            "runtime_factory",
            "m7_effect_operation_plugin.plugin:RUNTIME_FACTORY",
            configuration_identity="m7-effect-runtime.v1",
        ),
        ComponentSpec(
            "effect",
            "effect",
            "m7_effect_operation_plugin.plugin:EFFECT",
        ),
        ComponentSpec(
            "projector",
            "projector",
            "m7_effect_operation_plugin.plugin:PROJECTOR",
        ),
    ),
    operations=(
        OperationSpec(
            operation_id=OPERATION_ID,
            version="1",
            catalog_scope="public",
            description=OperationDescription(
                purpose="Verify one installed external Effect through exact UI approval.",
                applies_when="M7 validates the registered Effect lifecycle.",
                not_for="Scientific evidence, solver execution, or production work.",
            ),
            executor=ExecutorRef(kind="effect", component=ComponentRef("effect")),
            inputs=(
                InputPortSpec(
                    name="request",
                    description="Exact frozen M7 Effect request.",
                    schema="m7.fixture-effect-request.v1",
                    media_types=("application/json",),
                    codec=ComponentRef("json_codec"),
                    schema_resource=ComponentRef("request_schema"),
                    max_item_bytes=1024,
                    exposure="full",
                    usage="prior_signal",
                ),
            ),
            outputs=(
                OutputPortSpec(
                    name="execution_request",
                    description="Controlled request for the installed M7 Effect.",
                    schema="scidiscovery.execution-request",
                    media_types=("application/json",),
                    codec=ComponentRef("json_codec"),
                    schema_resource=ComponentRef("execution_request_schema"),
                    max_item_bytes=64 * 1024,
                    kind="execution_request",
                ),
            ),
            consequence="external",
            review=ReviewSpec(
                approval=ApprovalContract(
                    subject_ports=("execution_request", "request"),
                    question="是否授权这个 M7 测试适配器复制一个冻结文件？",
                    options=(
                        ApprovalOption("授权复制", "accept"),
                        ApprovalOption("拒绝复制", "reject"),
                    ),
                    projector=ComponentRef("projector"),
                )
            ),
            limits=LimitsSpec(
                timeout_seconds=30,
                max_input_bytes=1024,
                max_output_bytes=64 * 1024,
                max_files=1,
            ),
        ),
    ),
)

JSON_CODEC = CallableComponent("codec", json_codec)
REQUEST_SCHEMA = _schema(EffectRequest, "m7.fixture-effect-request.v1")
EXECUTION_REQUEST_SCHEMA = json.dumps(
    _execution_schema, ensure_ascii=True, separators=(",", ":"), sort_keys=True
)
CONFIGURATION_SCHEMA = _schema(
    EffectRuntimeConfig, "m7.fixture-effect-runtime-config.v1"
)
RUNTIME_FACTORY = RuntimePluginFactory(build_runtime)
EFFECT = CallableComponent("effect", effect_plan)
PROJECTOR = CallableComponent("projector", approval_projector)

__all__ = ["PLUGIN"]
