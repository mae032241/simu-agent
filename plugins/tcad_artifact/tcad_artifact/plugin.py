"""Single TCAD plugin declaration for Agent operations and their narrow parts."""

from __future__ import annotations


import json

from pydantic import BaseModel

from .device_parameters import DeviceParameterRequirementSet
from scidiscovery.artifact_agent.schema.execution import ExecutionRequest
from scidiscovery.operations.spec import PLUGIN_PROTOCOL_VERSION, ApprovalContract, ApprovalOption, ComponentRef, ComponentSpec, ExecutorRef, InputPortSpec, LimitsSpec, OperationDescription, OperationSpec, OutputPortSpec, PluginDefinition, PluginDependency, ReviewSpec

from .execution_control import SolverCapabilitySnapshot
from .project_packager import RuntimeAttestation
from .operation_transforms import COMPONENT_SPECS as TRANSFORM_COMPONENT_SPECS
from .operation_transforms import OPERATIONS as TRANSFORM_OPERATIONS
from .parameter_operations import COMPONENT_SPECS as PARAMETER_COMPONENT_SPECS
from .parameter_operations import OPERATIONS as PARAMETER_OPERATIONS
from .result_analysis import COMPONENT_SPECS as RESULT_ANALYSIS_COMPONENT_SPECS
from .result_analysis import OPERATIONS as RESULT_ANALYSIS_OPERATIONS
from .experiment_capability import COMPONENTS as EXPERIMENT_COMPONENTS


def _schema(model: type[BaseModel], schema_id: str) -> str:
    value = model.model_json_schema(mode="validation")
    value["$id"] = schema_id
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _ref(name: str, plugin_id: str | None = None) -> ComponentRef:
    return ComponentRef(name, plugin_id=plugin_id)




PLUGIN = PluginDefinition(
    plugin_id="tcad_artifact",
    version="0.2.0",
    protocol_version=PLUGIN_PROTOCOL_VERSION,
    dependencies=(
        PluginDependency("builtin", "0.1.0"),
        PluginDependency("general_science", "0.1.0"),
        PluginDependency("curve_score", "0.2.1"),
    ),
    configuration_schema=_ref("runtime_configuration_schema"),
    runtime_factory=_ref("runtime_factory"),
    components=(
        *EXPERIMENT_COMPONENTS,
        ComponentSpec("capability_schema", "resource", "tcad_artifact.plugin:CAPABILITY_SCHEMA"),
        ComponentSpec("runtime_attestation_schema", "resource", "tcad_artifact.plugin:RUNTIME_ATTESTATION_SCHEMA"),
        ComponentSpec("parameter_requirements_schema", "resource", "tcad_artifact.plugin:PARAMETER_REQUIREMENTS_SCHEMA"),
        ComponentSpec("runtime_configuration_schema", "resource", "tcad_artifact.runtime_plugin:CONFIGURATION_SCHEMA"),
        ComponentSpec("runtime_factory", "runtime_factory", "tcad_artifact.runtime_plugin:RUNTIME_FACTORY", configuration_identity="tcad.runtime-factory.v3:run-local-tool-service"),
        ComponentSpec("study_execute", "effect", "tcad_artifact.runtime_plugin:EXECUTE_EFFECT", configuration_identity="tcad.execution-adapter:tcad:execution-package.v2"),
        ComponentSpec("execution_projector", "projector", "tcad_artifact.runtime_plugin:EXECUTION_PROJECTOR"),
        ComponentSpec("execution_request_schema", "resource", "tcad_artifact.plugin:EXECUTION_REQUEST_SCHEMA"),
        *PARAMETER_COMPONENT_SPECS,
        *TRANSFORM_COMPONENT_SPECS,
        *RESULT_ANALYSIS_COMPONENT_SPECS,
    ),
    operations=(
        *PARAMETER_OPERATIONS,
        *RESULT_ANALYSIS_OPERATIONS,
        *TRANSFORM_OPERATIONS,
        OperationSpec(
            operation_id="tcad.experiment.execute.internal",
            version="4",
            catalog_scope="internal",
            description=OperationDescription(
                purpose="Execute a control-sealed implementation under configured resource authorization.",
                applies_when="The experiment capability has sealed an exact implementation and scientific sources.",
                not_for="Direct scheduler invocation or scientific interpretation.",
            ),
            executor=ExecutorRef(kind="effect", component=_ref("study_execute")),
            inputs=(InputPortSpec(name="execution_package", description="Exact control-sealed implementation.",
                schema="tcad.execution-package.v2", media_types=("application/json",),
                codec=_ref("json_codec", "general_science"), schema_resource=_ref("execution_package_schema"),
                max_item_bytes=64*1024*1024),),
            outputs=(
                OutputPortSpec(
                    name="execution_request",
                    description="Controlled request for one exact TCAD execution.",
                    schema="scidiscovery.execution-request",
                    media_types=("application/json",),
                    codec=_ref("json_codec", "general_science"),
                    schema_resource=_ref("execution_request_schema"),
                    kind="execution_request",
                    max_item_bytes=64 * 1024,
                ),
            ),
            consequence="external",
            review=ReviewSpec(
                approval=ApprovalContract(
                    allow_policy_authorization=True,
                    subject_ports=("execution_request", "execution_package"),
                    question="是否授权执行这个精确封存的 TCAD 工程？",
                    options=(
                        ApprovalOption("授权执行", "accept"),
                        ApprovalOption("拒绝执行", "reject"),
                    ),
                    projector=_ref("execution_projector"),
                )
            ),
            limits=LimitsSpec(
                timeout_seconds=300,
                max_input_bytes=256 * 1024 * 1024,
                max_output_bytes=64 * 1024 * 1024 + 64 * 1024,
                max_files=2,
            ),
        ),
    ),
)


CAPABILITY_SCHEMA = _schema(SolverCapabilitySnapshot, "tcad.solver-capability.v2")
RUNTIME_ATTESTATION_SCHEMA = _schema(RuntimeAttestation, "tcad.runtime-attestation.v1")
PARAMETER_REQUIREMENTS_SCHEMA = _schema(DeviceParameterRequirementSet, "scidiscovery.device-parameter-requirements.v1")
EXECUTION_REQUEST_SCHEMA = _schema(ExecutionRequest, "scidiscovery.execution-request")


__all__ = ["PLUGIN"]
