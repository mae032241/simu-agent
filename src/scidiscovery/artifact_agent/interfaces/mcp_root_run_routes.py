"""Minimal Run lifecycle routes for the Root scheduler facade."""

from __future__ import annotations

import json
from typing import Any


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
                   diagnostic_limit: int = 50) -> dict[str, Any]:
        if self.runs is None:
            raise RuntimeError("minimal Run service is unavailable")
        value = self.runs.status(self._resolve("run", name))
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
        output_status, output = self._sealed_output(value)
        result["sealed_output_status"] = output_status
        result["sealed_output"] = output
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
        self, value: Any
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
        payload = json.loads(self.artifacts.read(value.output_ref))
        if not isinstance(payload, dict):
            raise RuntimeError("completed scientific output is not a JSON object")
        return (
            output_status,
            {
                "artifact_name": value.output_binding_name,
                "kind": value.output_ref.kind,
                "schema": value.output_ref.schema_id,
                "payload": payload,
            },
        )


__all__ = ["RootRunRoutes"]
