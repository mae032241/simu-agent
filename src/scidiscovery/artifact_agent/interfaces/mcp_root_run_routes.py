"""Minimal Run lifecycle routes for the Root scheduler facade."""

from __future__ import annotations

from ..service.scheduling_control import owned_mutation

import json
from typing import Any

from ..schema.common import canonical_json

from ..service.run_read_projection import RunReadProjection, run_is_terminal, _output_selection, _output_index as _read_output_index
from .mcp_root_shared import RootToolError


# History owns complete entries and encrypted continuations. The producer's
# allowance excludes route metadata. This attention candidate budget is not a
# hard cap on history: an already larger page is preserved without notices.
HISTORY_ATTENTION_REPLY_MAX_BYTES = 16384
HISTORY_PAGE_MAX_BYTES = 15360


def _output_index(output, pointer, offset, limit):
    return _read_output_index(output, pointer, offset, limit, error_type=RootToolError)


class RootRunRoutes(RunReadProjection):
    _output_index = staticmethod(_output_index)

    def run_list(self, *, state: str | None, limit: int, before: str | None = None,
                 view: str = "summary", scheduler_view: bool = False) -> dict[str, Any]:
        if view == 'history':
            return self._attempt_history(state=state, limit=limit, before=before)
        if view not in {"summary", "detail"}:
            raise RootToolError('run_list view must be "summary" or "detail"')
        if self.runs is None:
            return {"runs": [], "next_before": None}
        if before is not None:
            self._resolve("run", before)
        items = []
        control = self.bindings.progression_status(instance_id=self._instance_id(), internal=True)
        checkpoint = json.loads(control.get('checkpoint_json', '{}'))
        from ..service.scientific_progress import goal_bound_runs
        current_goal = json.loads(control.get('objective_ref_json') or 'null')
        members = set(goal_bound_runs(checkpoint, current_goal)) if current_goal else set()
        def result(cursor):
            # The page owns exact bindings; historical goal membership reads
            # just those immutable admission keys, including prior loops.
            if current_goal and items:
                from ..service.progression_records import goal_admission_run
                with self.bindings._connect() as db:
                    members.update(item['name'] for item in items if goal_admission_run(
                        db, self._instance_id(), item['name'], current_goal, bindings=self.bindings))
            return dict(runs=items, next_before=cursor,
                **({'current_goal_tasks': [item['name'] for item in items if item['name'] in members]}
                    if members else {}))
        page, next_before = self.runs.list_bound_page(instance_id=self._instance_id(),
            state=state, limit=limit, before=before)
        for name, value in page:
            items.append(self._scientific_run_view(value, self._run_status_value(name, value))
                if view == "detail" and run_is_terminal(value.state) and not scheduler_view
                else self._compact_run_status(name=name, value=value,
                    intent="status", output_paths=[], index_offset=0, index_limit=16))
        return result(next_before)

    def _attempt_history(self, *, state, limit, before):
        from ..service.progression_records import history_cursor, read_history_cursor
        instance = self._instance_id()
        secret = self.instance_management_secret
        if type(secret) is not bytes or len(secret) < 32:
            raise RootToolError('Frozen history requires the configured local identity.')
        scope = (read_history_cursor(before, secret=secret, instance_id=instance, state=state, limit=limit)
            if before else self.runs.attempt_history_scope(instance_id=instance, state=state, limit=limit))
        response = self.runs.memory_page(scope, audience='root', page_bytes=HISTORY_PAGE_MAX_BYTES,
            continuation=lambda record: dict(tool='run_list', view='history', state=state, limit=limit,
                before=history_cursor(dict(scope, after=[record['completed_at'], record['terminal_event']]), secret=secret)))
        response['history_scope'] = dict(kind='exact_goal' if scope['objective_ref'] else 'authorized_recovery_source',
            objective_name=scope.get('objective_name'), source_task=scope.get('source_task'),
            loop_coverage='exact_goals_and_explicit_revision_ancestors_across_loops' if scope.get('objective_ancestors') else ('exact_goal_across_loops' if scope['objective_ref'] else 'recorded_direct_recovery_source'), frozen=True)
        if scope.get('lineage',{}).get('next_objective'):
            response['revision_scope']=dict(response['revision_scope'],
                original=dict(tool='artifact_catalog',name=scope['lineage']['next_objective'],view='content'),
                limitation='This goal original is readable; its older tasks are outside this frozen time index. Use exact old task navigation when available.')
        response.setdefault('continuation',None)
        return response

    def _attempt_history_navigation(self, *, name, value):
        from ..service.progression_records import history_cursor
        if not self.instance_management_secret:
            return dict(available=False, reason='local_history_identity_unavailable')
        scope = self.runs.attempt_history_scope(instance_id=self._instance_id(), state=None, limit=20,
            source_run_id=value.run_id, source_name=name)
        if scope is None:
            return dict(available=False, reason='no_exact_goal_or_authorized_recovery_source')
        return dict(available=True, read=dict(tool='run_list', view='history', state=None, limit=20,
            before=history_cursor(scope, secret=self.instance_management_secret)))

    def run_status(self, *, name: str, scheduler_view: bool = False, **arguments) -> dict[str, Any]:
        from .mcp_root import parse_run_status_arguments
        request = parse_run_status_arguments({"name": name, **arguments}, scheduler_view=scheduler_view)
        if self.runs is None:
            raise RuntimeError("minimal Run service is unavailable")
        value = self.runs.status(self._resolve("run", name))
        result = self._compact_run_status(name=name, value=value, **{
            key: request[key] for key in ("intent", "output_paths", "index_offset", "index_limit")},
            scheduler_view=scheduler_view)
        if request["intent"] == "status" and request["diagnostic_after"] is not None:
            page = self.runs.diagnostic_events(value, after=request["diagnostic_after"],
                limit=request["diagnostic_limit"])
            result["diagnostic_events"] = {"events": [
                {"event_id": event["event_id"], "recorded_at": event["recorded_at"],
                 "diagnostic": self._scientific_run_diagnostic(value, event["diagnostic"])}
                for event in page["events"]], "next_after": page["next_after"]}
        if request["intent"] == "navigation" and run_is_terminal(value.state):
            aliases = {b.name: b.object_id for b in self.bindings.list(
                instance=self._instance_id(), namespace="artifact")}
            inputs = {}
            for item in value.inputs:
                alias = item.artifact_name if aliases.get(item.artifact_name) == item.artifact_ref.artifact_id else None
                inputs.setdefault(item.port_name, []).append(alias)
            # Preserve exact frozen aliases and order; hidden/derived ports stay private.
            result["bound_inputs"] = self._scientific_run_view(value, {"bound_inputs": [
                {"port": port, "artifact_names": names} for port, names in inputs.items()]})["bound_inputs"]
        if request["intent"] == "navigation":
            result['attempt_history'] = self._attempt_history_navigation(name=name, value=value)
            evidence = (self.runs.evidence_output_refs(value) if value.state == "completed"
                else self.runs.sealed_evidence_output_refs(value))
            if evidence:
                page = []
                offset = request["index_offset"]
                for alias, ref in evidence[offset:offset + request["index_limit"]]:
                    item = {"artifact_name": value.output_binding_name + "." + alias, "schema": ref.schema_id}
                    if len(canonical_json([*page, item])) > 8192:
                        break
                    page.append(item)
                end = offset + len(page)
                result.update(evidence_outputs=page, evidence_outputs_total=len(evidence),
                    evidence_outputs_next_offset=end if end < len(evidence) else None,
                    evidence_outputs_status="sealed_materials_not_final_report")
        if request["stage_offset"] is not None or request["stage_reference"] is not None:
            from ..service.stage_deliveries import read_stage_deliveries
            result["sealed_stages"] = read_stage_deliveries(self.runs, value,
                instance_id=self._instance_id(), **{key: request[key] for key in (
                    "stage_offset", "stage_limit", "stage_reference", "stage_text_offset")})
        dependency = self.runs.review_wait_projection(value.run_id)
        if dependency is not None:
            result['review_dependency'] = dependency
        return result

    def _scientific_run_diagnostic(self, value, diagnostic):
        if diagnostic is None:
            return None
        safe = self.runs.sanitize_diagnostic(value, diagnostic,
            repairable=diagnostic.get("repairable_by_output") is True)
        # Revalidate saved details, including old records. Only an opaque handle
        # crosses this boundary; diagnostic_read separately enforces instance scope.
        from ..service.engineering_diagnostics import diagnostic_locator
        locator = diagnostic_locator(safe.get("engineering"))
        if locator:
            locator['available_sections'] = [section for section in locator['available_sections']
                if section in {'summary', 'traceback'}]
        return {**({"engineering": locator} if locator else {}),**{key: safe[key] for key in ("category", "code", "repairable_by_output", "tool_name") if key in safe},
            "details": [{key: item[key] for key in
                ("code", "path", "message", "phase", "affected_action", "repairable", "rule_id") if key in item}
                for item in safe.get("details", ())]}

    @owned_mutation(namespace='run')
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



__all__ = ["RootRunRoutes"]
