"""Startup-only TCAD execution adapter and local Operation-tool factory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from scidiscovery.artifact_agent.schema.approval import (
    ReviewDocument,
    ReviewDocumentItem,
    ReviewDocumentSection,
)
from scidiscovery.artifact_agent.schema.execution import ExecutionRequest
from scidiscovery.operations.invoke import ApprovalProjectorContext, EffectExecutorPlan
from scidiscovery.operations.runtime_plugins import (
    RuntimePluginContext,
    RuntimePluginContribution,
    RuntimePluginFactory,
)
from scidiscovery.operations.spec import CallableComponent

from .debug_adapter import TCADDevelopmentDebugBridge
from .local_debug_service import LocalTCADDebugService
from .project_packager import ExecutionPackage, validate_execution_package_eligibility


_REVIEW_DETAIL_LIMIT = 64


def _review_item(
    kind: str,
    label: str,
    subject_index: int,
    pointer: str,
) -> ReviewDocumentItem:
    return ReviewDocumentItem(
        kind=kind,
        label=label,
        subject_index=subject_index,
        json_pointer=pointer,
    )


class TCADRuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    transport: Literal["socket", "command"]
    socket_path: str | None = Field(default=None, min_length=1, max_length=4096)
    socket_timeout_seconds: float = Field(default=10.0, gt=0)
    command_config_path: str | None = Field(
        default=None, min_length=1, max_length=4096
    )

    @model_validator(mode="after")
    def _one_transport(self) -> "TCADRuntimeConfig":
        if self.transport == "socket":
            if self.socket_path is None or self.command_config_path is not None:
                raise ValueError("socket transport requires only socket_path")
            if not Path(self.socket_path).is_absolute():
                raise ValueError("TCAD socket path must be absolute")
        elif self.command_config_path is None or self.socket_path is not None:
            raise ValueError("command transport requires only command_config_path")
        elif not Path(self.command_config_path).is_absolute():
            raise ValueError("TCAD command config path must be absolute")
        return self


def build_runtime(context: RuntimePluginContext) -> RuntimePluginContribution:
    config = TCADRuntimeConfig.model_validate_json(context.config_bytes, strict=True)
    if config.transport == "socket":
        from .execution_adapter import TCADExecutorAdapter

        assert config.socket_path is not None
        adapter = TCADExecutorAdapter(config.socket_path, timeout=config.socket_timeout_seconds)
    else:
        from .command_adapter import CommandTCADExecutorAdapter

        assert config.command_config_path is not None
        adapter = CommandTCADExecutorAdapter.from_file(
            config.command_config_path,
            local_result_root=context.state_root / "executor-results",
        )
    if context.mode == "control":
        return RuntimePluginContribution(execution_adapters={"tcad": adapter})
    if context.mode != "local_worker":
        raise ValueError("TCAD runtime mode is unsupported")
    from .output_recovery import OutputInspectionService
    return RuntimePluginContribution(
        tool_services={
            "tcad.output_inspection": OutputInspectionService(adapter),
            "tcad.development_debug": LocalTCADDebugService(
                adapter=TCADDevelopmentDebugBridge(adapter),
                exchange_root=context.state_root / "local-tcad-debug",
                runtime_context=context,
            )
        }
    )


def execute_effect() -> EffectExecutorPlan:
    return EffectExecutorPlan(
        executor="tcad",
        preparation_profile="tcad.execution-package.v2",
        payload_port="execution_package",
        budget_subject_schemas=("scidiscovery.experiment-scientific-skeleton.v1",
                                "scidiscovery.experiment-portfolio.v1"),
    )


def execution_projector(context: ApprovalProjectorContext) -> ReviewDocument:
    if (
        tuple(item.port_name for item in context.subjects)
        != ("execution_request", "execution_package")
    ):
        raise ValueError("TCAD execution review requires request and execution package")
    request = ExecutionRequest.model_validate_json(
        context.subjects[0].content, strict=True
    )
    package = ExecutionPackage.model_validate_json(
        context.subjects[1].content, strict=True
    )
    validate_execution_package_eligibility(package)
    if (
        request.compiled_identity is None
        or request.compiled_identity.operation_id != context.operation_id
        or request.compiled_identity.operation_version != context.operation_version
        or request.compiled_identity.operation_digest != context.operation_digest
    ):
        raise ValueError("TCAD execution request has a different compiled identity")
    if len(package.resolved_inputs) > _REVIEW_DETAIL_LIMIT:
        resolved_input_items = (
            _review_item(
                "json_tree", f"全部已解析输入（{len(package.resolved_inputs)} 项）",
                1, "/resolved_inputs",
            ),
        )
    else:
        resolved_input_items = tuple(
            _review_item(
                "json_tree", f"已解析输入 {index}",
                1, f"/resolved_inputs/{index - 1}",
            )
            for index, _item in enumerate(package.resolved_inputs, start=1)
        )
    return ReviewDocument(
        title="TCAD 外部执行授权",
        description="核对冻结执行合同、精确工程、求解能力、参数绑定和副作用边界。",
        sections=(
            ReviewDocumentSection(
                title="执行与副作用边界",
                items=(
                    _review_item("json_value", "执行适配器", 0, "/executor"),
                    _review_item(
                        "json_value", "工程准备合同", 0,
                        "/preparation_profile",
                    ),
                    _review_item(
                        "json_value", "已编译操作", 0,
                        "/compiled_identity/operation_id",
                    ),
                    _review_item(
                        "json_value", "操作版本", 0,
                        "/compiled_identity/operation_version",
                    ),
                ),
            ),
            ReviewDocumentSection(
                title="工程与资源边界",
                items=(
                    _review_item(
                        "json_value", "求解器类型", 1, "/project/solver_kind",
                    ),
                    _review_item(
                        "json_value", "工具配置", 1, "/project/tool_profile",
                    ),
                    _review_item(
                        "json_value", "工程入口", 1, "/project/entrypoint",
                    ),
                    _review_item(
                        "json_tree", "资源上限", 1, "/project/resource_limits",
                    ),
                    _review_item(
                        "json_tree", "预期输出", 1, "/project/expected_outputs",
                    ),
                ),
            ),
            *( (ReviewDocumentSection(
                title="独立审查结论",
                items=(
                    _review_item("status", "审查结论", 1, "/review/verdict"),
                    _review_item("status", "可执行状态", 1, "/review/execution_ready"),
                    _review_item("json_value", "审查摘要", 1, "/review/summary"),
                    _review_item("json_value", "审查依据", 1, "/review/rationale"),
                    _review_item("status", "物理一致性", 1, "/review/physical_fidelity"),
                    _review_item(
                        "status", "实现一致性", 1,
                        "/review/implementation_fidelity",
                    ),
                    _review_item("status", "语法一致性", 1, "/review/syntax_fidelity"),
                    _review_item(
                        "status", "数值协议一致性", 1,
                        "/review/numerical_protocol_fidelity",
                    ),
                    _review_item("json_tree", "审查发现", 1, "/review/findings"),
                    _review_item("json_tree", "缺失输入", 1, "/review/missing_inputs"),
                    _review_item("json_tree", "后续动作", 1, "/review/next_actions"),
                ),
            ),) if package.review is not None else () ),
            ReviewDocumentSection(
                title="求解能力与输入",
                description=f"共 {len(package.resolved_inputs)} 个已解析输入。",
                items=(
                    _review_item(
                        "json_value", "能力配置", 1, "/capability/profile_id",
                    ),
                    _review_item(
                        "json_value", "公开版本", 1,
                        "/capability/public_release_label",
                    ),
                    _review_item(
                        "json_value", "启动程序", 1, "/capability/launch_name",
                    ),
                    *resolved_input_items,
                ),
            ),
        ),
    )


_config_schema = TCADRuntimeConfig.model_json_schema(mode="validation")
_config_schema["$id"] = "tcad.runtime-plugin-config.v1"
CONFIGURATION_SCHEMA = json.dumps(
    _config_schema, ensure_ascii=False, separators=(",", ":"), sort_keys=True
)
RUNTIME_FACTORY = RuntimePluginFactory(build_runtime)
EXECUTE_EFFECT = CallableComponent("effect", execute_effect)
EXECUTION_PROJECTOR = CallableComponent("projector", execution_projector)


__all__ = [
    "CONFIGURATION_SCHEMA",
    "EXECUTE_EFFECT",
    "EXECUTION_PROJECTOR",
    "RUNTIME_FACTORY",
    "TCADRuntimeConfig",
]
