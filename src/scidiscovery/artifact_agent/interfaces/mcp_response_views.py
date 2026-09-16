"""Read projections for MCP clients; services and sealed records stay complete."""
from __future__ import annotations

from .mcp_root_shared import RootToolError


def pick(value, *keys):
    return {key: value[key] for key in keys if key in value}


def page(items, *, key, limit=20, before=None):
    """Keep the owner's order and use its exact semantic key as the cursor."""
    found = before is None
    selected = []
    for item in items:
        if not found:
            found = item[key] == before
            continue
        if len(selected) == limit:
            return selected, selected[-1][key]
        selected.append(item)
    if not found:
        raise RootToolError("page cursor is not present in this query; restart the listing")
    return selected, None


def execution_summary(value):
    result = pick(value, "name", "state", "solver_state", "result_artifact_name",
                  "status_observed_at", "progress_observed_at", "reason", "observation_error")
    progress = value.get("progress") or {}
    if "progress" in value:
        result["progress"] = (None if value["progress"] is None else pick(progress,
            "elapsed_seconds", "started_at", "completed_at", "observed_at", "state", "exit_code",
            "reason", "error", "diagnostic_ref", "diagnostics", "observation_error"))
    tails = progress.get("log_tails", [])
    if tails:
        result["progress"]["logs_available"] = True
    if "collection" in value:
        result["collection"] = pick(value["collection"], "state", "accepted", "busy",
            "completed_bytes", "total_bytes", "completed_files", "total_files",
            "total_seconds", "recovery_pending", "reason", "error", "diagnostic_ref", "diagnostics",
            "record_error", "progress_error", "stop_record_error", "observation_error", "stop_observation_error", "stop_reason")
    result["detail"] = {"tool": "execution_status", "name": value.get("name"), "view": "detail"}
    return result


def run_summary(value):
    result = pick(value, "name", "state", "operation_id", "agent_type", "execution_profile",
        "output_artifact_name", "reason", "deadline_at", "last_activity_at", "completed_at", "draft_from",
        "recovery", "recovery_available", "sealed_output_status", "output_metadata",
        "output_delivery", "selected_output", "scheduler_signal_status", "scheduler_signal",
        "diagnostic_events")
    if "evidence_outputs" in value:
        result["evidence_output_count"] = len(value["evidence_outputs"])
    diagnostic = value.get("diagnostic_summary") or {}
    result["diagnostic_summary"] = pick(diagnostic, "failure", "latest_rejection",
        "latest_tool_error", "latest_native_error", "native_coverage", "rejection_count")
    native = value.get("native_execution")
    if native is not None:
        result["native_execution"] = pick(native, "coverage", "state", "reason", "elapsed_seconds",
            "exit_code", "timed_out", "error_type", "error_count", "observation_status")
    result["detail"] = {"tool": "run_status", "name": value.get("name"), "view": "detail", "output_paths": []}
    return result


def _summary_excerpt(result):
    selection = result.get("selected_output")
    if selection is None:
        return
    for item in selection.get("items", []):
        if item.get("pointer") == "/summary" and isinstance(item.get("value"), str):
            text = item["value"]
            if len(text) > 512:
                item.update(value=text[:512], status="excerpt", omitted_characters=len(text)-512)


def root_response(name, value, arguments):
    """Never replace a scientific object, precise request, or error with a verdict."""
    detail = arguments.get("view") == "detail"
    if name == "run_status":
        if detail:
            return value
        result = run_summary(value)
        if arguments.get("output_paths") is None:
            _summary_excerpt(result)
        return result
    if name in {"execution_status", "execution_sync", "execution_start", "execution_cancel", "execution_abandon"}:
        return value if detail else execution_summary(value)
    if name == "operation_invoke":
        kind = value["executor_kind"]
        result = value["result"]
        if kind == "agent":
            result = run_summary(result)
            result.pop("selected_output", None)
        # Transform/effect/approval returns already expose output identities and exact review URLs.
        return {**value, "result": result}
    if name == "run_record_failure":
        return run_summary(value)
    if name == "operation_catalog":
        items = value["operations"]
        selected = arguments.get("operation_id")
        if selected is not None:
            items = [item for item in items if item["operation_id"] == selected]
            if not items:
                raise RootToolError("operation is not available in the selected catalog scope")
        total = len(items)
        items, cursor = page(items, key="operation_id", limit=arguments["limit"], before=arguments.get("before"))
        if not detail:
            items = [pick(item, "operation_id", "purpose", "executor_kind", "catalog_scope", "runtime_binding") for item in items]
        return {"scope": value["scope"], "view": "detail" if detail else "summary",
                "operations": items, "total": total, "next_before": cursor,
                "detail": {"tool": "operation_catalog", "scope": value["scope"], "view": "detail", "operation_id": "<selected operation_id>"}}
    lists = {"scientific_inventory": ("objects", "artifact_name"),
             "scientific_current": ("selections", "kind"), "instance_list": ("instances", "name"),
             "execution_outputs": ("outputs", "output_label")}
    if name in lists:
        field, key = lists[name]
        values = value[field]
        items, cursor = page(values, key=key, limit=arguments["limit"], before=arguments.get("before"))
        result = {field: items, "total": len(values), "next_before": cursor}
        if name == "instance_list" and not detail:
            result[field] = [pick(item, "name", "title", "state") for item in items]
        if name == "scientific_inventory":
            result["catalog"] = {"tool": "operation_catalog", "scope": "public"}
            result["current_selections"] = {"tool": "scientific_current"}
        if name == "execution_outputs":
            result["execution_name"] = value["execution_name"]
        return result
    if name in {"run_list", "execution_list", "approval_list"}:
        field = {"run_list": "runs", "execution_list": "executions", "approval_list": "approvals"}[name]
        if not detail:
            value = {**value, field: [pick(item, "name", "state", "status", "operation_id",
                        "output_artifact_name", "selected_option") for item in value[field]]}
        return value
    if name == "artifact_catalog" and not detail:
        return {**pick(value, "name", "kind", "schema", "media_type", "size_bytes", "payload_schema_version"),
                "parent_count": len(value["parents"]),
                "detail": {"tool": name, "name": value["name"], "view": "detail"}}
    if name in {"instance_current", "instance_close"} and not detail:
        return pick(value, "name", "title", "state", "management_url")
    if name == "approval_status" and not detail:
        result = pick(value, "name", "status", "selected_option", "review_url", "rationale")
        rationale = result.get("rationale")
        if isinstance(rationale, str) and len(rationale) > 512:
            result.pop("rationale")
            result.update(rationale_excerpt=rationale[:512], omitted_characters=len(rationale)-512)
        result["detail"] = {"tool": name, "name": value.get("name"), "view": "detail"}
        return result
    if name == "execution_capabilities":
        items = value["capabilities"]
        items, cursor = page(items, key="profile", limit=arguments["limit"], before=arguments.get("before"))
        if not detail:
            items = [pick(item, "profile", "solver_kind", "launch_name", "public_release_label") for item in items]
        return {**value, "capabilities": items, "next_before": cursor,
                "detail": {"tool": name, "operation_id": arguments["operation_id"], "view": "detail"}}
    return value


__all__ = ["root_response", "page", "pick"]
