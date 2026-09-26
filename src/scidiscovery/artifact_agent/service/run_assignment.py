"""Compile one exact Operation binding into local assignment files."""

from __future__ import annotations

from ...agent_execution_settings import narrative_instruction

import json
from typing import Any

from ...operations.invoke import (
    active_direct_revision_ports,
    BoundOperationCall,
    operation_port_json_schema,
    operation_primary_output,
)
from ...operations.tooling import operation_tool_contracts, operation_role_instructions
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
    prior_source_bindings: dict[str, str] | None = None,
    deadline_at: str | None = None,
) -> bytes:
    revision = _revision_assignment(
        bound, inputs, workspace_mode=revision_workspace_mode
    )
    user_context_origins = {
        item.source_name: {"source_origin": "user_via_scheduler"}
        for item in bound.inputs
        if item.port_name == "user_context"
        and dict(item.artifact.labels).get("source_origin") == "user_via_scheduler"
    }
    source_provenance = {}
    for item in bound.inputs:
        labels = dict(item.artifact.labels)
        if labels.get("source_origin") == "public_web":
            source_provenance[item.source_name] = {"source_provenance": {
                "origin": "public_web", "original_source_alias": labels.get("original_source_alias"),
                "instruction": "Original fetched bytes. Cite the current source_name; source_manifest contains URL and retrieval time.",
            }}
    assignment = {
            "schema_version": 1,
            "operation": {
                "id": bound.compiled.spec.operation_id,
                "version": bound.compiled.spec.version,
                "digest": bound.compiled.digest,
            },
            "instruction": bound.instruction or "",
            "role_instructions": operation_role_instructions(bound.compiled),
            "narrative_instruction": narrative_instruction(
                bound.execution_profile["profile"] if bound.execution_profile else None),
            "budget": {"deadline_at": deadline_at, "source": "control"} if deadline_at else None,
            "inputs": [
                {
                    "source_name": item.source_name,
                    "artifact_name": item.artifact_name,
                    "artifact_name_usage": "navigation_only",
                    "port": item.port_name,
                    "description": next(port.description for port in bound.compiled.spec.inputs
                        if port.name == item.port_name),
                    "relative_path": (
                        "inputs/"
                        + workspace_input_filename(item.source_name, item.media_type)
                    ),
                    "media_type": item.media_type,
                    **({"materialization": "controlled_tool_stream_only", "artifact_ref": item.artifact_ref.model_dump(mode="json"),
                        "size_bytes": next(value.artifact.size_bytes for value in bound.inputs if value.source_name == item.source_name)}
                       if item.exposure == "file_reference" else {}),
                    **({"reference_availability": "unknown"} if "worker_reference_read" in tool_names else {}),
                    "usage": item.usage,
                    "exposure": item.exposure,
                    **user_context_origins.get(item.source_name, {}),
                    **source_provenance.get(item.source_name, {}),
                    "historical": next(
                        value.artifact.historical for value in bound.inputs
                        if value.source_name == item.source_name
                    ),
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
            "prior_source_bindings": prior_source_bindings or {},
            **({"reference_access": "Text inputs are readable at their relative_path; file_reference inputs expose metadata only and are streamed by declared control tools; reference availability is unknown until checked, not absent. Use worker_reference_read to list one selected bound report’s direct citations and read selected originals. Select a calculation before its inputs. Do not expand all history; unresolved references remain explicit gaps."}
               if "worker_reference_read" in tool_names else {}),
            "tools": list(tool_names),
            "tool_contracts": operation_tool_contracts(bound.compiled, tool_names),
            "recovery_draft": (
                None
                if recovery_relative_path is None
                else {
                    "relative_path": recovery_relative_path,
                    "scientific_evidence": False,
                    "instruction": (
                        "Read this draft before continuing. Use it only as an editable "
                        "starting point. Its contract and inputs may differ from this Run; "
                        "check every assumption against the newly bound inputs and "
                        "revalidate the complete result without inheriting conclusions."
                    ),
                }
            ),
        }
    assignment["operation"] = {"purpose": bound.compiled.spec.description.purpose}
    assignment.pop("prior_source_bindings", None)
    visible = {port.name: port for port in bound.compiled.spec.inputs if port.agent_visible}
    assignment["inputs"] = [item for item in assignment["inputs"] if item["port"] in visible]
    for item in assignment["inputs"]:
        item.pop("artifact_ref", None)
        item.pop("port", None)
    return canonical_json(assignment)


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


def result_schema_json(
    compiled: Any,
    *,
    input_source_ports: dict[str, str] | None = None,
) -> bytes:
    if input_source_ports is not None:
        visible = {item.name for item in (*compiled.spec.inputs, *compiled.spec.outputs) if item.agent_visible}
        input_source_ports = {alias:name for alias,name in input_source_ports.items() if name in visible}
    port = operation_primary_output(compiled)
    envelope = RoleResultEnvelope[Any].model_json_schema(mode="validation")
    envelope["properties"]["payload"] = operation_port_json_schema(
        compiled, port, input_source_ports=input_source_ports
    )
    envelope["$id"] = f"{port.schema_id}.run-envelope"
    from ...operations.workspace import WorkspaceFinalizer, operation_workspace_hooks
    finalizer = operation_workspace_hooks(compiled).get("workspace_finalizer")
    if isinstance(finalizer, WorkspaceFinalizer):
        envelope = finalizer.draft_schema(envelope, port.schema_id, input_source_ports)
    return canonical_json(envelope)


__all__ = ["assignment_json", "result_schema_json", "revision_draft_json"]
