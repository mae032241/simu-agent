"""Pure binding and narrow executor adapters for compiled operations."""
from __future__ import annotations
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.operation_contract import (
    active_direct_revision_ports,
    direct_revision_ports,
    operation_output_validation_contract,
    operation_port_json_schema,
)
from .spec import (
    CompiledOperation,
    InputPortSpec,
    OutputPortSpec,
)
from scidiscovery.artifact_agent.schema.transform_output import TransformOutput
_RUNTIME_BINDING = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")
class OperationInvocationError(ValueError):
    def __init__(self, reason_code: str, *, port: str | None = None) -> None:
        self.reason_code = reason_code
        self.port = port
        super().__init__(f"{reason_code}: {port or 'operation'}")
@dataclass(frozen=True, slots=True)
class InvocationArtifact:
    artifact_name: str
    ref: ArtifactRef
    schema_id: str
    media_type: str
    size_bytes: int
    current: bool = False
    parent_refs: tuple[ArtifactRef, ...] = ()
    labels: tuple[tuple[str, str], ...] = ()
    handoff_verdict: str | None = None
@dataclass(frozen=True, slots=True)
class BoundInput:
    port_name: str
    source_name: str
    artifact_name: str
    artifact: InvocationArtifact
    exposure: str
    usage: str
@dataclass(frozen=True, slots=True)
class EffectExecutorPlan:
    executor: str
    preparation_profile: str
    payload_port: str
@dataclass(frozen=True, slots=True)
class BoundOperationCall:
    compiled: CompiledOperation
    name: str
    inputs: tuple[BoundInput, ...]
    instruction: str | None
    executor_plan: EffectExecutorPlan | None = None
@dataclass(frozen=True, slots=True)
class ApprovalSubjectSnapshot:
    subject_index: int
    port_name: str
    item_index: int
    ref: ArtifactRef
    schema_id: str
    media_type: str
    size_bytes: int
    parent_refs: tuple[ArtifactRef, ...]
    labels: tuple[tuple[str, str], ...]
    handoff_verdict: str | None
    content: bytes
@dataclass(frozen=True, slots=True)
class ProducerFamilyMember:
    port_name: str
    item_name: str | None
    ref: ArtifactRef
@dataclass(frozen=True, slots=True)
class ProducerEvidenceSource:
    source_kind: str
    source_name: str
    ref: ArtifactRef
@dataclass(frozen=True, slots=True)
class ProducerOutputFamily:
    primary_ref: ArtifactRef
    operation_id: str
    operation_version: str
    operation_digest: str
    members: tuple[ProducerFamilyMember, ...]
    evidence_sources: tuple[ProducerEvidenceSource, ...]
    reviewer_operation: str | None = None
    review_subject_outputs: tuple[str, ...] = ()
    family_identity: str | None = None
@dataclass(frozen=True, slots=True)
class ApprovalProjectorContext:
    operation_id: str
    operation_version: str
    operation_digest: str
    subjects: tuple[ApprovalSubjectSnapshot, ...]
    producer_families: tuple[ProducerOutputFamily, ...] = ()
_AGENT_INPUT_USAGES = frozenset(
    {
        "claim_evidence",
        "revision_base",
        "change_request",
        "prior_signal",
        "cached_excerpt",
        "evidence_inventory",
        "review_signal",
    }
)


def preflight_operation(
    compiled: CompiledOperation,
    *,
    name: str,
    artifacts_by_port: Mapping[str, tuple[InvocationArtifact, ...]],
    instruction: str | None,
    parameters: Mapping[str, Any] | None = None,
    read_artifact: Callable[[ArtifactRef], bytes] | None = None,
) -> BoundOperationCall:
    spec = compiled.spec
    expected = {port.name: port for port in spec.inputs}
    if set(artifacts_by_port) != set(expected):
        missing = next(iter(sorted(set(expected) - set(artifacts_by_port))), None)
        extra = next(iter(sorted(set(artifacts_by_port) - set(expected))), None)
        raise OperationInvocationError(
            "input_port_missing" if missing else "input_port_unknown",
            port=missing or extra,
        )
    parameter_map = dict(parameters or {})
    if parameter_map:
        raise OperationInvocationError("parameters_not_declared")
    if spec.executor.kind == "agent":
        if instruction is None or not instruction.strip():
            raise OperationInvocationError("instruction_required")
        try:
            instruction_bytes = instruction.encode("utf-8")
        except UnicodeError as error:
            raise OperationInvocationError("instruction_encoding_invalid") from error
        if len(instruction_bytes) > 65536:
            raise OperationInvocationError("instruction_too_large")
        invalid_usage = next(
            (port.name for port in spec.inputs if port.usage not in _AGENT_INPUT_USAGES),
            None,
        )
        if invalid_usage is not None:
            raise OperationInvocationError(
                "agent_input_usage_invalid", port=invalid_usage
            )
    elif instruction is not None:
        raise OperationInvocationError("instruction_forbidden")
    bound: list[BoundInput] = []
    seen_refs: set[ArtifactRef] = set()
    total_bytes = 0
    for port in spec.inputs:
        artifacts = artifacts_by_port[port.name]
        _validate_port_binding(port, artifacts)
        total_bytes += sum(item.size_bytes for item in artifacts)
        for index, artifact in enumerate(artifacts, start=1):
            if artifact.ref in seen_refs:
                raise OperationInvocationError("input_artifact_duplicate", port=port.name)
            seen_refs.add(artifact.ref)
            source_name = (
                port.name
                if len(artifacts) == 1
                else f"{port.name}_{index:03d}"
            )
            bound.append(
                BoundInput(
                    port_name=port.name,
                    source_name=source_name,
                    artifact_name=artifact.artifact_name,
                    artifact=artifact,
                    exposure=port.exposure,
                    usage=port.usage,
                )
            )
    assert spec.limits is not None
    if total_bytes > spec.limits.max_input_bytes:
        raise OperationInvocationError("input_total_too_large")
    bound_inputs = tuple(bound)
    admission = spec.input_admission
    if admission is not None:
        present = {item.port_name for item in bound_inputs}.intersection(
            admission.member_ports
        )
        if present:
            missing = next(
                (name for name in admission.member_ports if name not in present),
                None,
            )
            if missing is not None:
                raise OperationInvocationError(
                    "input_cohort_incomplete", port=missing
                )
    _run_guards(compiled, bound_inputs, parameter_map)
    _validate_input_content(compiled, bound_inputs, read_artifact)
    return BoundOperationCall(
        compiled=compiled,
        name=name,
        inputs=bound_inputs,
        instruction=instruction,
    )


def _validate_input_content(
    compiled: CompiledOperation,
    inputs: tuple[BoundInput, ...],
    read_artifact: Callable[[ArtifactRef], bytes] | None,
) -> None:
    """Check declared top-level JSON presence on exact immutable input bytes."""
    ports = {port.name: port for port in compiled.spec.inputs}
    for item in inputs:
        fields = ports[item.port_name].required_non_null_fields
        if not fields:
            continue
        if read_artifact is None:
            raise OperationInvocationError("input_content_reader_missing", port=item.port_name)
        try:
            raw = read_artifact(item.artifact.ref)
        except Exception as error:
            raise OperationInvocationError("input_content_unavailable", port=item.port_name) from error
        try:
            value = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise OperationInvocationError("input_content_invalid", port=item.port_name) from error
        if not isinstance(value, dict):
            raise OperationInvocationError("input_content_invalid", port=item.port_name)
        if any(value.get(field) is None for field in fields):
            raise OperationInvocationError("input_required_field_missing", port=item.port_name)

def preflight_result(action: Any) -> dict[str, Any]:
    try:
        bound = action()
    except OperationInvocationError as error:
        return {"admissible": False, "reason_code": error.reason_code,
                "port": error.port, "executor_kind": None}
    return {"admissible": True, "reason_code": None, "port": None,
            "executor_kind": bound.compiled.spec.executor.kind}
def effect_executor_plan(bound: BoundOperationCall) -> EffectExecutorPlan:
    value = effect_operation_plan(bound.compiled)
    if value.payload_port not in {item.port_name for item in bound.inputs}:
        raise OperationInvocationError(
            "effect_payload_port_missing", port=value.payload_port
        )
    return value


def effect_operation_plan(compiled: CompiledOperation) -> EffectExecutorPlan:
    if compiled.spec.executor.kind != "effect":
        raise OperationInvocationError("effect_executor_required")
    try:
        value = _executor_callable(compiled)()
    except Exception as error:
        raise OperationInvocationError("executor_component_failed") from error
    if not isinstance(value, EffectExecutorPlan):
        raise OperationInvocationError("effect_executor_result_invalid")
    if _RUNTIME_BINDING.fullmatch(value.executor) is None:
        raise OperationInvocationError("effect_executor_result_invalid")
    if value.payload_port not in {item.name for item in compiled.spec.inputs}:
        raise OperationInvocationError(
            "effect_payload_port_missing", port=value.payload_port
        )
    return EffectExecutorPlan(
        executor=f"{compiled.plugin_id}:{value.executor}",
        preparation_profile=value.preparation_profile,
        payload_port=value.payload_port,
    )
def operation_primary_output(compiled: CompiledOperation) -> OutputPortSpec:
    return next(port for port in compiled.spec.outputs if port.collection is None)


def execute_compiled_transform(
    bound: BoundOperationCall,
    inputs: Mapping[str, bytes],
) -> tuple[TransformOutput, ...]:
    """Invoke one compiled Transform component through its declared ports."""

    if bound.compiled.spec.executor.kind != "transform":
        raise OperationInvocationError("transform_executor_required")
    expected = {item.source_name for item in bound.inputs}
    if set(inputs) != expected:
        raise OperationInvocationError("transform_input_binding_invalid")
    grouped: dict[str, list[bytes]] = {}
    for item in bound.inputs:
        grouped.setdefault(item.port_name, []).append(inputs[item.source_name])
    try:
        value = _executor_callable(bound.compiled)(
            MappingProxyType({key: tuple(items) for key, items in grouped.items()})
        )
    except Exception as error:
        raise OperationInvocationError("executor_component_failed") from error
    if not isinstance(value, Mapping):
        raise ValueError("transform component must return an output mapping")
    return _transform_outputs(bound.compiled, value)
def _validate_port_binding(
    port: InputPortSpec, artifacts: tuple[InvocationArtifact, ...]
) -> None:
    if not port.min_items <= len(artifacts) <= port.max_items:
        raise OperationInvocationError("input_cardinality_invalid", port=port.name)
    wildcard = port.schema_id == "*" and port.media_types == ("*/*",)
    for artifact in artifacts:
        if not wildcard and artifact.schema_id != port.schema_id:
            raise OperationInvocationError("input_schema_mismatch", port=port.name)
        if not wildcard and artifact.media_type not in port.media_types:
            raise OperationInvocationError("input_media_type_mismatch", port=port.name)
        if artifact.size_bytes > port.max_item_bytes:
            raise OperationInvocationError("input_item_too_large", port=port.name)
        if port.require_current and not artifact.current:
            raise OperationInvocationError("input_not_current", port=port.name)
def _run_guards(
    compiled: CompiledOperation,
    inputs: tuple[BoundInput, ...],
    parameters: Mapping[str, Any],
) -> None:
    for reference in compiled.spec.guards:
        key = f"{reference.plugin_id or compiled.plugin_id}:{reference.component_id}"
        try:
            accepted = compiled.implementations[key](inputs, parameters)
        except Exception as error:
            raise OperationInvocationError("guard_failed", port=reference.component_id) from error
        if accepted is not True:
            raise OperationInvocationError("guard_rejected", port=reference.component_id)
def _executor_callable(compiled: CompiledOperation) -> Any:
    reference = compiled.spec.executor.component
    key = f"{reference.plugin_id or compiled.plugin_id}:{reference.component_id}"
    return compiled.implementations[key]
def _transform_outputs(
    compiled: CompiledOperation, values: Mapping[Any, Any]
) -> tuple[TransformOutput, ...]:
    ports = {port.name: port for port in compiled.spec.outputs}
    if set(values) != set(ports):
        raise ValueError("transform output ports differ from the compiled operation")
    outputs: list[TransformOutput] = []
    for port in compiled.spec.outputs:
        raw_items = values[port.name]
        if not isinstance(raw_items, tuple) or not all(
            isinstance(item, bytes) for item in raw_items
        ):
            raise ValueError("transform output items must be a tuple of bytes")
        if not port.min_items <= len(raw_items) <= port.max_items:
            raise ValueError("transform output cardinality is invalid")
        for index, raw in enumerate(raw_items, start=1):
            _validate_transform_item(compiled, port, raw)
            label = ("primary" if not outputs else port.name
                     if port.collection is None and len(raw_items) == 1
                     else f"{port.name}_{index:03d}")
            outputs.append(
                TransformOutput(
                    label=label,
                    port_name=port.name,
                    content=raw,
                    kind=port.kind,
                    schema=port.schema_id,
                    payload_schema_version=port.payload_schema_version,
                    media_type=port.media_types[0],
                )
            )
    if not outputs:
        raise ValueError("transform operation produced no output")
    return tuple(outputs)
def _validate_transform_item(
    compiled: CompiledOperation, port: OutputPortSpec, raw: bytes
) -> None:
    if len(raw) > port.max_item_bytes:
        raise ValueError("transform output item exceeds its port limit")
    if port.validator is None:
        return
    key = f"{port.validator.plugin_id or compiled.plugin_id}:{port.validator.component_id}"
    compiled.implementations[key](raw)
__all__ = [
    "BoundOperationCall",
    "active_direct_revision_ports",
    "execute_compiled_transform",
    "EffectExecutorPlan",
    "InvocationArtifact",
    "OperationInvocationError",
    "operation_port_json_schema",
    "operation_output_validation_contract",
    "effect_executor_plan",
    "effect_operation_plan",
    "direct_revision_ports",
    "preflight_operation",
    "preflight_result",
    "operation_primary_output",
]
