"""Public pure constructors for deterministic transform declarations and inputs."""
from collections.abc import Mapping
from typing import Any
import json

from .spec import (ComponentRef, ExecutorRef, InputPortSpec, LimitsSpec,
    OperationDescription, OperationSpec, OutputPortSpec)

__all__ = ["object_schema", "single_input", "group_inputs", "transform_output", "transform_operation"]


def object_schema(schema_id: str) -> str:
    return json.dumps({"$id": schema_id, "type": "object"}, separators=(",", ":"), sort_keys=True)


def single_input(values: Mapping[str, tuple[bytes, ...]], name: str) -> bytes:
    items = values.get(name, ())
    if len(items) != 1:
        raise ValueError(f"transform input {name} must contain one item")
    return items[0]


def group_inputs(inputs: tuple[Any, ...]) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = {}
    for item in inputs:
        grouped.setdefault(item.port_name, []).append(item)
    return grouped


def transform_output(name: str, kind: str, schema: str,
                     resource: ComponentRef, validator: ComponentRef, *, codec: ComponentRef,
                     min_items: int = 1, max_items: int = 1,
                     max_bytes: int = 32 * 1024 * 1024, media_type: str = "application/json") -> OutputPortSpec:
    return OutputPortSpec(name=name, description=f"Deterministic transform output: {name}.",
        schema=schema, media_types=(media_type,), codec=codec, schema_resource=resource,
        min_items=min_items, max_items=max_items, max_item_bytes=max_bytes, kind=kind, validator=validator)


def transform_operation(operation_id: str, component: ComponentRef, purpose: str,
                        inputs: tuple[InputPortSpec, ...], outputs: tuple[OutputPortSpec, ...], *,
                        applies_when: str, not_for: str, guards: tuple[ComponentRef, ...] = (),
                        version: str = "1", catalog_scope: str = "support", timeout_seconds: int = 300,
                        max_input_bytes: int = 1024 * 1024 * 1024,
                        max_output_bytes: int = 512 * 1024 * 1024) -> OperationSpec:
    return OperationSpec(operation_id=operation_id, version=version, catalog_scope=catalog_scope,
        description=OperationDescription(purpose=purpose, applies_when=applies_when, not_for=not_for),
        executor=ExecutorRef(kind="transform", component=component), inputs=inputs, outputs=outputs,
        consequence="scientific", guards=guards,
        limits=LimitsSpec(timeout_seconds=timeout_seconds, max_input_bytes=max_input_bytes,
            max_output_bytes=max_output_bytes, max_files=sum(item.max_items for item in outputs)))
