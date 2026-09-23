"""Minimal Run lifecycle routes for the Root scheduler facade."""

from __future__ import annotations

import json
from itertools import islice
from typing import Any

from ..schema.approval import parse_json_pointer
from ..schema.common import canonical_json
from .mcp_response_views import validate_run_status_profile
from .mcp_root_shared import RootToolError


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


def _output_index(output: dict[str, Any], pointer: str, offset: int, limit: int) -> dict[str, Any]:
    """Bound the whole directory, including origin and pointer, without scientific values."""
    budget = 8 * 1024
    result = {key: output[key] for key in ("artifact_name", "kind", "schema")}
    result.update(pointer=pointer, status="available", children=[], total_children=0, next_offset=None)
    if len(canonical_json(result)) > budget:
        raise RootToolError("output index metadata exceeds 8192 bytes; select a shorter ancestor path")
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
        raise RootToolError("output index metadata exceeds 8192 bytes; select a shorter ancestor path")
    if offset > total:
        raise RootToolError(f"index_offset {offset} exceeds total_children {total}")
    candidates = value.items() if isinstance(value, dict) else enumerate(value) if isinstance(value, list) else ()
    for position, (key, child) in enumerate(islice(candidates, offset, offset + limit), offset):
        child_pointer = pointer + "/" + str(key).replace("~", "~0").replace("/", "~1")
        entry = {"pointer": child_pointer, **metadata(child)}
        result["children"].append(entry)
        result["next_offset"] = position + 1 if position + 1 < total else None
        if len(canonical_json(result)) > budget:
            result["children"].pop()
            if not result["children"]:
                raise RootToolError(f"output index entry at offset {position} exceeds 8192 bytes; read this parent in values mode")
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


class RootRunRoutes:
    def run_list(self, *, state: str | None, limit: int, before: str | None = None) -> dict[str, Any]:
        if self.runs is None:
            return {"runs": [], "next_before": None}
        if before is not None:
            self._resolve("run", before)
        items = []
        past_cursor = before is None
        for binding in self.bindings.list(instance=self._instance_id(), namespace="run"):
            if not past_cursor:
                past_cursor = binding.name == before
                continue
            value = self.runs.status(binding.object_id)
            if state is not None and value.state != state:
                continue
            if len(items) == limit:
                return {"runs": items, "next_before": items[-1]["name"]}
            items.append(self._run_status_value(binding.name, value))
        return {"runs": items, "next_before": None}

    def run_status(self, *, name: str, diagnostic_after: int | None = None,
                   diagnostic_limit: int = 50,
                   output_paths: list[str] | None = None, output_mode: str = "values",
                   index_offset: int = 0, index_limit: int = 16,
                   response_profile: str = "compat") -> dict[str, Any]:
        if self.runs is None:
            raise RuntimeError("minimal Run service is unavailable")
        validate_run_status_profile(
            response_profile=response_profile,
            view="summary",
            output_mode=output_mode,
            output_paths=output_paths,
        )
        value = self.runs.status(self._resolve("run", name))
        if response_profile != "compat":
            return self._compact_run_status(
                name=name,
                value=value,
                response_profile=response_profile,
                diagnostic_after=diagnostic_after,
                diagnostic_limit=diagnostic_limit,
                output_paths=output_paths,
                index_offset=index_offset,
                index_limit=index_limit,
            )
        result = self._run_status_value(name, value)
        if diagnostic_after is not None:
            result["diagnostic_events"] = self.runs.diagnostic_events(
                value, after=diagnostic_after, limit=diagnostic_limit)
        bound_inputs = {}
        instance = self._instance_id()
        aliases = {b.name: b.object_id for b in self.bindings.list(instance=instance, namespace="artifact")}
        for item in value.inputs:
            # Preserve the frozen request's alias and order. Missing aliases are
            # explicit; another record of the same schema is never substituted.
            name = item.artifact_name if aliases.get(item.artifact_name) == item.artifact_ref.artifact_id else None
            bound_inputs.setdefault(item.port_name, []).append(name)
        result["bound_inputs"] = [{"port": port, "artifact_names": names} for port, names in bound_inputs.items()]
        if value.backend_id == "local_trusted":
            from ..service.local_process_observation import read_summary
            from ..service.local_workspace import WorkspaceError
            try:
                result["native_execution"] = read_summary(self.runs.backend.open(value.run_id).root)
            except (WorkspaceError, OSError) as error:
                result["native_execution"] = {"coverage": "unobserved", "scientific_evidence": False,
                    "reason": "workspace_unavailable", "error_type": type(error).__name__}
            native = result["native_execution"]
            result["diagnostic_summary"]["native_coverage"] = native["coverage"]
            result["diagnostic_summary"]["latest_native_error"] = next(
                iter(reversed(native.get("recent_errors", []))), None)
        output_status, output = self._sealed_output(value, include_payload=output_paths != [])
        result["sealed_output_status"] = output_status
        result["sealed_output"] = output if output_paths is None and output_mode == "values" else None
        if output_mode == "index":
            result["output_delivery"] = "index"
            result["output_index"] = (
                _output_index(output, (output_paths or [""])[0], index_offset, index_limit)
                if output is not None else None)
        elif output_paths is not None:
            result["output_delivery"] = "selected" if output_paths else "omitted"
            result["output_metadata"] = (
                {key: output[key] for key in ("artifact_name", "kind", "schema")}
                if output is not None else None
            )
            result["selected_output"] = (
                _output_selection(output, output_paths) if output_paths and output is not None else None
            )
        result["scheduler_signal_status"] = (
            "available" if output is not None and value.signal is not None else "unavailable"
        )
        result["scheduler_signal"] = (
            value.signal.model_dump(mode="json")
            if output_status in {"available", "historical"} and value.signal is not None
            else None
        )
        evidence = self.runs.evidence_output_refs(value)
        if evidence:
            result["evidence_outputs"] = [{"artifact_name": value.output_binding_name+"."+alias, "schema": ref.schema_id} for alias, ref in evidence]
        return result

    def _compact_run_status(
        self,
        *,
        name: str,
        value: Any,
        response_profile: str,
        diagnostic_after: int | None,
        diagnostic_limit: int,
        output_paths: list[str] | None,
        index_offset: int,
        index_limit: int,
    ) -> dict[str, Any]:
        include_payload = response_profile in {"navigation", "decision"}
        output_status, output = self._sealed_output(value, include_payload=include_payload)
        recovery = (
            self.runs.compact_recovery_status(value)
            if value.state == "failed"
            else None
        )
        try:
            compiled = self._operation_catalog.operation(value.operation_id)
        except KeyError:
            contract_status = "historical"
        else:
            contract_status = (
                "current"
                if compiled.spec.version == value.operation_version
                and compiled.digest == value.operation_digest
                else "historical"
            )
        result = {
            "name": name,
            "operation_id": value.operation_id,
            "operation_version": value.operation_version,
            "operation_digest": value.operation_digest,
            "operation_contract_status": contract_status,
            "state": value.state,
            "reason": value.reason,
            "created_at": value.created_at,
            "started_at": value.started_at,
            "deadline_at": value.deadline_at,
            "completed_at": value.completed_at,
            "last_activity_at": value.last_activity_at,
            "recovery_available": (
                recovery["resume_available"]
                if recovery is not None
                else self.runs.recovery_available(value)
            ),
            "sealed_output_status": output_status,
            "scheduler_signal_status": (
                "available"
                if output is not None and value.signal is not None
                else "unavailable"
            ),
        }
        if value.state != "completed":
            result["diagnostic_summary"] = self.runs.diagnostic_summary(value)
        if recovery is not None:
            result["compact_recovery_status"] = recovery
        if diagnostic_after is not None:
            result["diagnostic_events"] = self.runs.diagnostic_events(
                value, after=diagnostic_after, limit=diagnostic_limit
            )
        if response_profile == "navigation":
            result["output_delivery"] = "index"
            result["output_index"] = (
                _output_index(
                    output,
                    (output_paths or [""])[0],
                    index_offset,
                    index_limit,
                )
                if output is not None
                else None
            )
        elif response_profile == "decision" and value.state == "completed":
            result["output_delivery"] = "selected"
            result["output_metadata"] = (
                {key: output[key] for key in ("artifact_name", "kind", "schema")}
                if output is not None
                else None
            )
            result["selected_output"] = (
                _output_selection(output, output_paths or [])
                if output is not None
                else None
            )
            result["scheduler_signal"] = (
                value.signal.model_dump(mode="json")
                if output_status in {"available", "historical"}
                and value.signal is not None
                else None
            )
        return result

    def run_record_failure(
        self,
        *,
        name: str,
        reason: str,
        expected_state: str,
        expected_last_activity_at: str | None,
        timed_out: bool,
    ) -> dict[str, Any]:
        if self.runs is None:
            raise RuntimeError("minimal Run service is unavailable")
        self.runs.record_failure(
            self._resolve("run", name),
            reason=reason,
            expected_state=expected_state,
            expected_last_activity_at=expected_last_activity_at,
            timed_out=timed_out,
        )
        return self.run_status(name=name)

    def _run_status_value(self, name: str, value: Any) -> dict[str, Any]:
        binding = self._binding("run", name)
        return {
            **self._binding_value(binding),
            "operation_id": value.operation_id,
            "agent_type": value.agent_type,
            "execution_profile": value.execution_profile,
            "backend": value.backend_id,
            "state": value.state,
            "output_artifact_name": (
                value.output_binding_name if value.output_ref is not None else None
            ),
            "reason": value.reason,
            "created_at": value.created_at,
            "started_at": value.started_at,
            "deadline_at": value.deadline_at,
            "completed_at": value.completed_at,
            "last_activity_at": value.last_activity_at,
            "candidate_accepted": value.accepted_candidate_digest is not None,
            "head_advance": (
                None
                if value.completion_receipt is None
                else value.completion_receipt.head_advance
            ),
            "recovery_available": self.runs.recovery_available(value),
            "recovery": self.runs.recovery_status(value),
            "diagnostic_summary": self.runs.diagnostic_summary(value),
            "tool_timing": self.runs.tool_timing(value.run_id),
            "draft_from": (
                None if value.draft_from_run_id is None else self.bindings.find_name(
                    instance=self._instance_id(), namespace="run",
                    object_id=value.draft_from_run_id,
                )
            ),
        }

    def _sealed_output(
        self, value: Any, *, include_payload: bool = True
    ) -> tuple[str, dict[str, Any] | None]:
        """Expose scientific content only after the Run completed and sealed it."""

        if value.state != "completed" or value.output_ref is None:
            return "unavailable", None
        output_status = "available"
        try:
            compiled = self._operation_catalog.operation(value.operation_id)
        except KeyError:
            output_status = "historical"
        else:
            if (
                compiled.spec.version != value.operation_version
                or compiled.digest != value.operation_digest
            ):
                output_status = "historical"
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


__all__ = ["RootRunRoutes"]
