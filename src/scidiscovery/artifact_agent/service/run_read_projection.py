"""Shared sealed Run read projection; no scheduling or lifecycle writes."""
from __future__ import annotations

import json
from itertools import islice
from typing import Any

from ..schema.approval import parse_json_pointer
from ..schema.common import canonical_json
from ...operation_contract import DiagnosticError
from .input_reader import compact_scientific_fields, compact_handoff

def run_intent_projection(value, *, intent):
    """Pure compact projection; the route avoids assembling excluded details."""
    result = pick(
        value,
        "name",
        "operation_id",
        "operation_contract_status",
        "state",
        "agent_type",
        "execution_profile",
        "deadline_at",
        "last_activity_at",
        "output_artifact_name",
        "recovery_available",
        "sealed_output_status",
        "diagnostics_available",
        "attention_required",
        "content_unavailable",
        "sealed_stages",
        "dispatch",
        "reason",
        "scientific_intent",
    )
    if isinstance(result.get("execution_profile"), dict):
        result["execution_profile"] = pick(result["execution_profile"], "profile")
    if intent == "full" and value.get("state") == "completed":
        result.update(pick(value, "output_delivery", "sealed_output", "scheduler_signal", "scheduler_signal_status", "scientific_progress"))
    elif intent == "navigation" and value.get("state") == "completed":
        result.update(pick(value, "output_delivery", "output_index", "output_metadata"))
    elif intent == "decision" and value.get("state") == "completed":
        result.update(
            pick(
                value,
                "output_delivery",
                "output_metadata",
                "selected_output",
                "default_output_unavailable",
                "output_index",
                "scheduler_signal",
                "scheduler_signal_status",
                "scheduler_signal_omissions",
                "scientific_progress",
            )
        )
    return result


def run_is_terminal(state):
    # Unknown lifecycle values fail closed; they cannot opt into long details.
    return state in {"completed", "failed", "timed_out", "cancelled", "canceled"}


def pick(value, *keys):
    return {key: value[key] for key in keys if key in value}


def _pointer_value(value: Any, pointer: str) -> Any:
    for token in parse_json_pointer(pointer):
        if isinstance(value, dict):
            value = value[token]
        elif isinstance(value, list) and (token == "0" or (
            token.isascii() and token.isdigit() and not token.startswith("0")
        )):
            value = value[int(token)]
        else:
            raise KeyError(token)
    return value


def _output_index(output: dict[str, Any], pointer: str, offset: int, limit: int, *, error_type=DiagnosticError) -> dict[str, Any]:
    """Bound the whole directory, including origin and pointer, without scientific values."""
    budget = 8 * 1024
    result = {key: output[key] for key in ("artifact_name", "kind", "schema")}
    result.update(pointer=pointer, status="available", children=[], total_children=0, next_offset=None)
    if len(canonical_json(result)) > budget:
        raise error_type("output index metadata exceeds 8192 bytes; select a shorter ancestor path")
    try:
        value = _pointer_value(output["payload"], pointer)
    except (KeyError, IndexError, ValueError):
        result["status"] = "missing"
        return result
    def metadata(value):
        kind = ("null" if value is None else "boolean" if isinstance(value, bool)
            else "object" if isinstance(value, dict) else "array" if isinstance(value, list)
            else "string" if isinstance(value, str) else "number")
        return {"type": kind, "size_bytes": len(canonical_json(value))}
    result.update(metadata(value))
    total = len(value) if isinstance(value, (dict, list)) else 0
    result["total_children"] = total
    if len(canonical_json(result)) > budget:
        raise error_type("output index metadata exceeds 8192 bytes; select a shorter ancestor path")
    if offset > total:
        raise error_type(f"index_offset {offset} exceeds total_children {total}")
    candidates = value.items() if isinstance(value, dict) else enumerate(value) if isinstance(value, list) else ()
    for position, (key, child) in enumerate(islice(candidates, offset, offset + limit), offset):
        child_pointer = pointer + "/" + str(key).replace("~", "~0").replace("/", "~1")
        entry = {"pointer": child_pointer, **metadata(child)}
        result["children"].append(entry)
        result["next_offset"] = position + 1 if position + 1 < total else None
        if len(canonical_json(result)) > budget:
            result["children"].pop()
            if not result["children"]:
                raise error_type(f"output index entry at offset {position} exceeds 8192 bytes; read this parent in values mode")
            result["next_offset"] = position
            break
    return result


def _output_selection(output: dict[str, Any], pointers: list[str]) -> dict[str, Any]:
    """Select exact scientific values; omission and navigation are not evidence."""
    remaining = 32 * 1024
    navigation_remaining = 8 * 1024
    items = []
    for pointer in pointers:
        value = output["payload"]
        try:
            value = _pointer_value(value, pointer)
        except (KeyError, IndexError, ValueError):
            items.append({"pointer": pointer, "status": "missing"})
            continue
        size = len(canonical_json(value))
        item = {"pointer": pointer, "size_bytes": size}
        if size <= remaining:
            item.update(status="selected", value=value)
            remaining -= size
        else:
            item["status"] = "omitted"
            if isinstance(value, (dict, list)):
                children = []
                candidates = value.items() if isinstance(value, dict) else enumerate(value)
                for key, child in candidates:
                    if len(children) == 32:
                        break
                    child_pointer = pointer + "/" + str(key).replace("~", "~0").replace("/", "~1")
                    child_type = ("null" if child is None else "boolean" if isinstance(child, bool)
                        else "object" if isinstance(child, dict) else "array" if isinstance(child, list)
                        else "string" if isinstance(child, str) else "number")
                    entry = {"pointer": child_pointer, "type": child_type,
                        "size_bytes": len(canonical_json(child))}
                    # Count the complete navigation array; never shorten a key into a false pointer.
                    cost = len(canonical_json([*children, entry]))
                    if cost <= navigation_remaining:
                        children.append(entry)
                navigation_remaining -= len(canonical_json(children)) if children else 0
                item.update(children=children, omitted_children=len(value) - len(children))
        items.append(item)
    return {key: output[key] for key in ("artifact_name", "kind", "schema")} | {"items": items}


class RunReadProjection:
    _output_index = staticmethod(_output_index)

    def __init__(self, *, runs, artifacts, operation_catalog):
        self.runs, self.artifacts, self._operation_catalog = runs, artifacts, operation_catalog

    def decision(self, *, name, value):
        return self._compact_run_status(name=name, value=value, intent="decision",
            output_paths=[], index_offset=0, index_limit=16)

    def _compact_run_status(
        self,
        *,
        name: str,
        value: Any,
        intent: str,
        output_paths: list[str] | None,
        index_offset: int,
        index_limit: int,
    ) -> dict[str, Any]:
        include_payload = intent in {"navigation", "decision", "full"}
        output_status, output = self._sealed_output(value, include_payload=include_payload)
        contract_status = self._operation_catalog.recorded_contract_status(value.operation_id,
            version=value.operation_version, digest=value.operation_digest)
        result = {
            "name": name,
            "operation_id": value.operation_id,
            "operation_version": value.operation_version,
            "operation_digest": value.operation_digest,
            "operation_contract_status": contract_status,
            "state": value.state,
            "agent_type": value.agent_type,
            "execution_profile": value.execution_profile,
            "deadline_at": value.deadline_at,
            "last_activity_at": value.last_activity_at,
            "output_artifact_name": value.output_binding_name if value.output_ref is not None else None,
            "recovery_available": self.runs.recovery_available(value),
            "diagnostics_available": True,
            "sealed_output_status": output_status,
            "scheduler_signal_status": (
                "available"
                if output is not None and value.signal is not None
                else "unavailable"
            ),
        }
        if intent in {"decision", "full"}:
            from .scientific_progress import read_intent
            task_intent = read_intent(self.artifacts, value)
            if task_intent is not None:
                result["scientific_intent"] = task_intent
            if value.state == 'completed':
                from .research_progress import research_progress, public_progress
                result['scientific_progress'] = public_progress(research_progress(self.runs, value))
        attention = self.runs.submission_attention(value)
        if attention is not None:
            result["attention_required"] = attention
        if value.state == "failed":
            result["diagnostic_summary"] = self.runs.diagnostic_summary(value)
        if intent != "status" and value.state != "completed":
            result["content_unavailable"] = "run_not_completed"
        if intent == "full" and value.state == "completed":
            result["output_delivery"] = "full"
            result["sealed_output"] = output
            result["scheduler_signal"] = (value.signal.model_dump(mode="json")
                if output_status in {"available", "historical"} and value.signal is not None else None)
        elif intent == "navigation" and value.state == "completed":
            result["output_delivery"] = "index"
            result["output_index"] = (
                self._output_index(
                    output,
                    (output_paths or [""])[0],
                    index_offset,
                    index_limit,
                )
                if output is not None
                else None
            )
        elif intent == "decision" and value.state == "completed":
            default_view = not output_paths
            if not output_paths:
                # The frozen read projection remains useful after its authoring contract
                # retires; it never establishes current scientific qualification.
                fields = value.decision_fields
                if fields is None and contract_status == "current":
                    fields = self._operation_catalog.recorded_operation(value.operation_id,
                        version=value.operation_version, digest=value.operation_digest).spec.decision_fields
                if fields is None:
                    result["default_output_unavailable"] = "decision_fields_not_recorded"
                    result["output_index"] = (self._output_index(output, "", index_offset, index_limit)
                        if output is not None else None)
                else:
                    output_paths = [field if field.startswith("/") else "/" + field.replace("~", "~0").replace("/", "~1") for field in fields]
            result["output_delivery"] = "index" if "default_output_unavailable" in result else "selected"
            result["output_metadata"] = (
                {key: output[key] for key in ("artifact_name", "kind", "schema")}
                if output is not None
                else None
            )
            result["selected_output"] = (
                ({key: output[key] for key in ("artifact_name", "kind", "schema")}
                    | compact_scientific_fields(output['payload'], output_paths)
                    if default_view else _output_selection(output, output_paths or []))
                if output is not None and output_paths
                else None
            )
            if default_view and output_paths:
                result['output_delivery'] = 'compact'
                if result['selected_output'] is not None:
                    result['selected_output']['read'] = dict(tool='run_status', name=name, intent='decision',
                        output_paths=[output_paths[0]])
                    result['selected_output']['reading'] = 'Replace output_paths with selected exact returned pointers; navigation intent indexes omitted children.'
                    result['selected_output']['original'] = dict(tool='run_status', name=name, intent='full')
            result["scheduler_signal"] = (
                value.signal.model_dump(mode="json")
                if output_status in {"available", "historical"}
                and value.signal is not None
                else None
            )
        if intent == "decision" and isinstance(result.get("scheduler_signal"), dict):
            signal, omissions = compact_handoff(result['scheduler_signal'])
            if output_paths and not default_view and 'summary' in result['scheduler_signal']:
                signal['summary'] = result['scheduler_signal']['summary']
                omissions.pop('summary', None)
            result["scheduler_signal"] = signal
            if omissions:
                result["scheduler_signal_omissions"] = {"omitted_items": omissions,
                    "read": {"tool": "run_status", "name": name, "intent": "full"}}
        return run_intent_projection(self._scientific_run_view(value, result), intent=intent)

    def _scientific_run_view(self, value, result):
        if "reason" in result:
            result["reason"] = None
        if value.state == "failed":
            failure = result.get("diagnostic_summary", {}).get("failure") or {}
            result["reason"] = {
                "run_timeout": "The Run exceeded its time limit. Inspect the saved diagnostics before choosing recovery.",
                "output_rejected": "The output did not satisfy its declared contract. Correct the reported scientific fields before retrying.",
                "integrity_failure": "The sealed materials failed integrity checks. Restore the exact originals before retrying.",
                "admission_defect": "The selected materials did not satisfy the declared input requirements. Inspect the saved diagnostics.",
            }.get(failure.get("category"), "The Run failed. Read the saved diagnostic page to identify a repair or choose another scientific action.")
        allowed = {"scientific_intent", "scientific_progress", "name", "operation_id", "operation_contract_status", "state", "agent_type", "execution_profile",
            "created_at", "started_at", "completed_at", "deadline_at", "last_activity_at", "output_artifact_name",
            "recovery_available", "draft_from", "diagnostics_available", "attention_required", "reason", "diagnostic_events", "sealed_output_status", "sealed_output",
            "scheduler_signal_status", "scheduler_signal", "scheduler_signal_omissions", "output_delivery", "output_metadata", "selected_output",
            "output_index", "default_output_unavailable", "evidence_outputs", "bound_inputs", "content_unavailable", "dispatch"}
        result = {key:item for key,item in result.items() if key in allowed}
        try:
            ports = self._operation_catalog.recorded_operation(value.operation_id,
                version=value.operation_version, digest=value.operation_digest).spec.inputs
            visible = {port.name for port in ports if port.agent_visible and port.derivation is None}
        except KeyError:
            visible = set()
        if "bound_inputs" in result:
            result["bound_inputs"] = [item for item in result["bound_inputs"] if item["port"] in visible]
        if value.state == "queued":
            result["dispatch"] = {
                "agent_type": value.agent_type,
                "instruction": "Spawn agent_type with execution_profile.profile model/reasoning_effort and no parent history. Keep child waiting; get its actual thread ID from spawn or ask the child for its platform identity. Use worker_attach, then open assignment. No tool-registry identity search or guessed IDs. Reviewers must differ from subject authors. Read sealed run_status, not completion chat.",
                "attachment": {"tool": "worker_attach", "name": result.get("name")},
                "after_completion": {"tool": "run_status", "name": result.get("name")}}
        if isinstance(result.get("execution_profile"), dict):
            result["execution_profile"] = {"profile":result["execution_profile"]["profile"]}
        return result

    def _sealed_output(
        self, value: Any, *, include_payload: bool = True
    ) -> tuple[str, dict[str, Any] | None]:
        """Expose scientific content only after the Run completed and sealed it."""

        if value.state != "completed" or value.output_ref is None:
            return "unavailable", None
        contract_status = self._operation_catalog.recorded_contract_status(value.operation_id,
            version=value.operation_version, digest=value.operation_digest)
        output_status = "historical" if contract_status == "unavailable" else "available"
        metadata = {"artifact_name": value.output_binding_name, "kind": value.output_ref.kind,
            "schema": value.output_ref.schema_id}
        if not include_payload:
            return output_status, metadata
        payload = json.loads(self.artifacts.read(value.output_ref))
        if not isinstance(payload, dict):
            raise RuntimeError("completed scientific output is not a JSON object")
        return (
            output_status,
            {
                **metadata,
                "payload": payload,
            },
        )
