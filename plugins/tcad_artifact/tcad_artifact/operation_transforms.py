"""TCAD support projections consumed by current scientific tasks."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.execution_context import ExecutionContext
from scidiscovery.operations.input_validation import parse_bound_json, OperationInvocationError
from scidiscovery.operations.spec import (
    CallableComponent, CollectionSpec, ComponentRef, ComponentSpec, ExecutorRef,
    InputPortSpec, InputValidationSpec, LimitsSpec, OperationDescription,
    OperationSpec, OutputPortSpec,
)
from .execution_control import SolverCapabilitySnapshot
from .project_packager import ExecutionPackage, TCADRuntimeManifest
from .transform_adapter import attest_runtime as attest_runtime_payload

RUNTIME_ATTESTATION_OPERATION = "tcad.runtime-attestation.v1"
EXECUTION_CONTEXT_OPERATION = "tcad.execution-context.project.v1"

def _schema(model: type[Any], schema_id: str) -> str:
    value = model.model_json_schema(mode="validation")
    value["$id"] = schema_id
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

def _one(values: Mapping[str, tuple[bytes, ...]], name: str) -> bytes:
    items = values.get(name, ())
    if len(items) != 1:
        raise ValueError(f"TCAD transform input {name} must contain exactly one item")
    return items[0]

def runtime_inputs(sources: Mapping[str, bytes]) -> None:
    manifest = parse_bound_json(TCADRuntimeManifest, sources["runtime_manifest"], admission_port="runtime_manifest")
    parse_bound_json(ExecutionPackage, sources["execution_package"], admission_port="execution_package")
    descriptors = sources.binding_descriptors
    outputs = [name for name, descriptor in descriptors.items() if descriptor.port_name == "runtime_outputs"]
    if len(outputs) != len(manifest.outputs):
        raise OperationInvocationError("input_runtime_collection_mismatch", port="runtime_outputs",
                                       message="Bind the complete output collection declared by the runtime manifest.")
    for name, record in zip(outputs, manifest.outputs, strict=True):
        if len(sources[name]) != record.size_bytes or hashlib.sha256(sources[name]).hexdigest() != record.sha256:
            raise OperationInvocationError("input_runtime_output_mismatch", port="runtime_outputs",
                                           message="Each runtime output must match its exact manifest record and order.")

def attest_runtime(
    values: Mapping[str, tuple[bytes, ...]],
) -> dict[str, tuple[bytes, ...]]:
    manifest_raw = _one(values, "runtime_manifest")
    manifest = TCADRuntimeManifest.model_validate_json(manifest_raw, strict=True)
    payloads = values.get("runtime_outputs", ())
    if len(payloads) != len(manifest.outputs):
        raise ValueError("runtime output collection differs from its exact manifest")
    inputs = {
        "execution_package": _one(values, "execution_package"),
        "runtime_manifest": manifest_raw,
        **{
            f"output__{record.name}": payload
            for record, payload in zip(manifest.outputs, payloads, strict=True)
        },
    }
    return attest_runtime_payload(inputs)

def project_execution_context(
    values: Mapping[str, tuple[bytes, ...]],
) -> dict[str, tuple[bytes, ...]]:
    snapshot = SolverCapabilitySnapshot.model_validate_json(
        _one(values, "capability"), strict=True
    )
    context = ExecutionContext(
        domain="tcad",
        implementation_backend=snapshot.launch_name,
        implementation_kind=snapshot.solver_kind,
        release_label=snapshot.public_release_label,
        public_arguments=snapshot.public_arguments,
        capability_statements=None,
        limitations=None,
    )
    return {"execution_context": (canonical_json(context),)}

def _has_parent(child: Any, parent: Any) -> bool:
    return parent.artifact.ref in child.artifact.parent_refs

def runtime_parentage(inputs: tuple[Any, ...], parameters: Mapping[str, Any]) -> bool:
    del parameters
    by_port: dict[str, list[Any]] = {}
    for item in inputs:
        by_port.setdefault(item.port_name, []).append(item)
    package = by_port["execution_package"][0]
    manifest = by_port["runtime_manifest"][0]
    if not _has_parent(manifest, package):
        return False
    execution_parents = manifest.artifact.parent_refs
    return all(
        item.artifact.parent_refs == execution_parents
        for item in by_port.get("runtime_outputs", ())
    )

def _ref(name: str, plugin_id: str | None = None) -> ComponentRef:
    return ComponentRef(name, plugin_id=plugin_id)

def _input(
    name: str,
    schema: str,
    resource: str | ComponentRef,
    *,
    min_items: int = 1,
    max_items: int = 1,
    max_bytes: int = 32 * 1024 * 1024,
    usage: str = "claim_evidence",
    exposure: str = "full",
    media_types: tuple[str, ...] = ("application/json",),
) -> InputPortSpec:
    return InputPortSpec(
        name=name,
        description=f"Exact deterministic TCAD transform input: {name}." + (" File reference only: exact identity and size are bound; use controlled input_path for streaming, never inline bytes." if exposure == "file_reference" else ""),
        schema=schema,
        media_types=media_types,
        codec=_ref(
            "json_codec" if media_types == ("application/json",) else "opaque_codec",
            "general_science",
        ),
        schema_resource=resource if isinstance(resource, ComponentRef) else _ref(resource),
        min_items=min_items,
        max_items=max_items,
        max_item_bytes=max_bytes,
        usage=usage,
        exposure=exposure,
    )

def _output(
    name: str,
    kind: str,
    schema: str,
    resource: str,
    *,
    min_items: int = 1,
    max_items: int = 1,
    max_bytes: int = 32 * 1024 * 1024,
    collection_bytes: int | None = None,
    payload_schema_version: int = 1,
) -> OutputPortSpec:
    return OutputPortSpec(
        name=name,
        description=f"Deterministic TCAD transform output: {name}.",
        schema=schema,
        media_types=("application/json",),
        codec=_ref("json_codec", "general_science"),
        schema_resource=_ref(resource),
        min_items=min_items,
        max_items=max_items,
        max_item_bytes=max_bytes,
        kind=kind,
        payload_schema_version=payload_schema_version,
        collection=(
            CollectionSpec(max_total_bytes=collection_bytes)
            if collection_bytes is not None
            else None
        ),
    )

def _operation(
    operation_id: str,
    component: str,
    purpose: str,
    inputs: tuple[InputPortSpec, ...],
    outputs: tuple[OutputPortSpec, ...],
    *,
    guards: tuple[ComponentRef, ...] = (),
    input_validation: InputValidationSpec | None = None,
    max_input_bytes: int = 256 * 1024 * 1024,
    max_output_bytes: int = 64 * 1024 * 1024,
    max_files: int = 8,
) -> OperationSpec:
    return OperationSpec(
        operation_id=operation_id,
        version="1",
        catalog_scope="support",
        description=OperationDescription(
            purpose=purpose,
            applies_when="All declared immutable inputs are available.",
            not_for="Open-ended scientific judgment or external execution.",
        ),
        executor=ExecutorRef(kind="transform", component=_ref(component)),
        inputs=inputs,
        outputs=outputs,
        consequence="scientific",
        guards=guards,
        input_validation=input_validation,
        limits=LimitsSpec(
            timeout_seconds=300,
            max_input_bytes=max_input_bytes,
            max_output_bytes=max_output_bytes,
            max_files=max_files,
        ),
    )

RUNTIME_INPUT_VALIDATOR = CallableComponent("validator", runtime_inputs)
RUNTIME_ATTEST_COMPONENT = CallableComponent("transform", attest_runtime)
EXECUTION_CONTEXT_COMPONENT = CallableComponent("transform", project_execution_context)
RUNTIME_PARENTAGE_GUARD = CallableComponent("guard", runtime_parentage)
REVIEWED_PACKAGE_SCHEMA = _schema(ExecutionPackage, "tcad.execution-package.v2")

COMPONENT_SPECS = (
    ComponentSpec("runtime_inputs", "validator", "tcad_artifact.operation_transforms:RUNTIME_INPUT_VALIDATOR"),
    ComponentSpec("runtime_attest", "transform", "tcad_artifact.operation_transforms:RUNTIME_ATTEST_COMPONENT"),
    ComponentSpec("execution_context_project", "transform", "tcad_artifact.operation_transforms:EXECUTION_CONTEXT_COMPONENT",
        resources=(_ref("capability_schema"), _ref("execution_context_schema", "general_science")),
        configuration_identity="tcad.execution-context-project.v1"),
    ComponentSpec("runtime_parentage", "guard", "tcad_artifact.operation_transforms:RUNTIME_PARENTAGE_GUARD"),
    ComponentSpec("execution_package_schema", "resource", "tcad_artifact.operation_transforms:REVIEWED_PACKAGE_SCHEMA"),
)

OPERATIONS = (
    _operation(
        EXECUTION_CONTEXT_OPERATION,
        "execution_context_project",
        "Project one public TCAD capability snapshot into a domain-neutral execution context.",
        (
            _input(
                "capability",
                "tcad.solver-capability.v2",
                "capability_schema",
                max_bytes=64 * 1024,
                usage="prior_signal",
            ),
        ),
        (
            OutputPortSpec(
                name="execution_context",
                description="Domain-neutral execution context projected from one TCAD capability snapshot.",
                schema="scidiscovery.execution-context.v1",
                media_types=("application/json",),
                codec=_ref("json_codec", "general_science"),
                schema_resource=_ref("execution_context_schema", "general_science"),
                min_items=1,
                max_items=1,
                max_item_bytes=64 * 1024,
                kind="execution_context",
                payload_schema_version=1,
            ),
        ),
        max_input_bytes=64 * 1024,
        max_output_bytes=64 * 1024,
        max_files=1,
    ),
    _operation(
        RUNTIME_ATTESTATION_OPERATION,
        "runtime_attest",
        "Attest raw execution outputs against one exact TCAD execution package.",
        (
            _input("execution_package", "tcad.execution-package.v2", "execution_package_schema", usage="prior_signal", max_bytes=64 * 1024 * 1024),
            _input(
                "runtime_manifest",
                "opaque",
                _ref("opaque_schema", "general_science"),
                usage="prior_signal",
                media_types=("application/json",),
            ),
            _input(
                "runtime_outputs",
                "opaque",
                _ref("opaque_schema", "general_science"),
                min_items=0,
                max_items=4096,
                max_bytes=256 * 1024 * 1024,
                usage="evidence_inventory",
                media_types=(
                    "application/octet-stream",
                    "application/x-synopsys-plx",
                    "application/json",
                    "text/plain",
                    "text/csv",
                    "image/png",
                ),
            ),
        ),
        (_output("runtime_attestation", "runtime_attestation", "tcad.runtime-attestation.v1", "runtime_attestation_schema"),),
        guards=(_ref("runtime_parentage"),),
        input_validation=InputValidationSpec(_ref("runtime_inputs"), "tcad.runtime.inputs",
            "The supplied runtime outputs must match the manifest collection, order, sizes and digests before attestation."),
        max_input_bytes=512 * 1024 * 1024,
    ),
)

__all__ = ["COMPONENT_SPECS", "EXECUTION_CONTEXT_OPERATION", "OPERATIONS"]
