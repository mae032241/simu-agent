"""Compile one exact Operation binding into local assignment files."""

from __future__ import annotations

import json
from typing import Any

from ...operations.invoke import (
    active_direct_revision_ports,
    BoundOperationCall,
    operation_port_json_schema,
    operation_primary_output,
)
from ..schema.common import canonical_json
from ..schema.role_result import RoleResultEnvelope
from .local_workspace import workspace_input_filename
from .run_records import RunInputBinding


def assignment_json(
    bound: BoundOperationCall,
    inputs: tuple[RunInputBinding, ...],
    *,
    tool_names: tuple[str, ...],
    recovery_relative_path: str | None = None,
    revision_workspace_mode: str | None = None,
) -> bytes:
    revision = _revision_assignment(
        bound, inputs, workspace_mode=revision_workspace_mode
    )
    return canonical_json(
        {
            "schema_version": 1,
            "operation": {
                "id": bound.compiled.spec.operation_id,
                "version": bound.compiled.spec.version,
                "digest": bound.compiled.digest,
            },
            "instruction": bound.instruction or "",
            "inputs": [
                {
                    "source_name": item.source_name,
                    "relative_path": (
                        "inputs/"
                        + workspace_input_filename(item.source_name, item.media_type)
                    ),
                    "media_type": item.media_type,
                    "usage": item.usage,
                    "exposure": item.exposure,
                }
                for item in inputs
                if item.exposure != "handoff_only"
            ],
            "output": {
                "relative_path": "output/result.json",
                "schema_path": "schema/result.schema.json",
                "semantic_contract_pointer": (
                    "/properties/payload/x-scidiscovery-semantic-constraints"
                ),
                "validation_contract_pointer": (
                    "/properties/payload/x-scidiscovery-validation-contract"
                ),
            },
            "revision": revision,
            "tools": list(tool_names),
            "recovery_draft": (
                None
                if recovery_relative_path is None
                else {
                    "relative_path": recovery_relative_path,
                    "scientific_evidence": False,
                    "instruction": (
                        "Read this draft before continuing. Use it only as an editable "
                        "starting point, preserve valid handoff assumptions, and "
                        "revalidate the complete result."
                    ),
                }
            ),
        }
    )


def revision_draft_json(
    bound: BoundOperationCall,
    input_bytes: dict[str, bytes],
) -> bytes | None:
    """Build one editable, deliberately non-submittable copy of a revision base."""

    direct = active_direct_revision_ports(
        bound.compiled, (item.port_name for item in bound.inputs)
    )
    if direct is None:
        return None
    base = next(item for item in bound.inputs if item.port_name == direct[0].name)
    try:
        payload = json.loads(input_bytes[base.source_name])
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("revision base cannot initialize a JSON draft") from error
    if not isinstance(payload, dict):
        raise ValueError("revision base payload must be a JSON object")
    return (
        json.dumps(
            {
                "schema_version": 1,
                # Invalid until the Worker authors the new handoff.  The
                # control plane copies scientific payload bytes but never
                # invents a revision verdict or summary.
                "handoff": {"verdict": "", "summary": ""},
                "payload": payload,
            },
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _revision_assignment(
    bound: BoundOperationCall,
    inputs: tuple[RunInputBinding, ...],
    *,
    workspace_mode: str | None,
) -> dict[str, str] | None:
    direct = active_direct_revision_ports(
        bound.compiled, (item.port_name for item in inputs)
    )
    if direct is None:
        return None
    base = next(item for item in inputs if item.port_name == direct[0].name)
    mode = workspace_mode or "result_copy"
    if mode not in {"result_copy", "domain_workspace"}:
        raise ValueError("revision workspace mode is invalid")
    return {
        "mode": "copy_on_write",
        "base_source_name": base.source_name,
        "editable_target": (
            "output/result.json" if mode == "result_copy" else "domain_workspace"
        ),
        "publication": "complete_immutable_snapshot",
    }


def result_schema_json(compiled: Any) -> bytes:
    port = operation_primary_output(compiled)
    envelope = RoleResultEnvelope[Any].model_json_schema(mode="validation")
    envelope["properties"]["payload"] = operation_port_json_schema(compiled, port)
    envelope["$id"] = f"{port.schema_id}.run-envelope"
    return canonical_json(envelope)


__all__ = ["assignment_json", "result_schema_json", "revision_draft_json"]
