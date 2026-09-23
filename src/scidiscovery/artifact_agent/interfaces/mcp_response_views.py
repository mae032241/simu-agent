"""Read projections for MCP clients; services and sealed records stay complete."""
from __future__ import annotations

import hashlib

from .mcp_root_shared import RootToolError


RUN_RESPONSE_PROFILES = ("compat", "poll", "navigation", "decision")


def validate_run_status_profile(*, response_profile, view, output_mode, output_paths):
    """Keep the model-visible profile matrix and both runtime checks identical."""
    if response_profile == "compat":
        return
    if view != "summary":
        raise RootToolError(
            f'run_status response_profile="{response_profile}" requires view="summary"; '
            'use response_profile="compat", view="detail" for the full record'
        )
    if response_profile == "poll" and not (
        output_mode == "values" and output_paths == []
    ):
        raise RootToolError(
            'run_status response_profile="poll" requires output_mode="values" and output_paths=[]'
        )
    if response_profile == "navigation" and not (
        output_mode == "index"
        and (output_paths is None or len(output_paths) == 1)
    ):
        raise RootToolError(
            'run_status response_profile="navigation" requires output_mode="index" '
            'and zero or one output path'
        )
    if response_profile == "decision" and not (
        output_mode == "values" and isinstance(output_paths, list) and len(output_paths) > 0
    ):
        raise RootToolError(
            'run_status response_profile="decision" requires output_mode="values" '
            'and one or more output paths'
        )


def run_profile_projection(value, *, response_profile, diagnostics_requested=False):
    """Pure compact projection; the route avoids assembling excluded details."""
    if response_profile == "compat":
        return value
    result = pick(
        value,
        "name",
        "operation_id",
        "operation_version",
        "operation_digest",
        "operation_contract_status",
        "state",
        "reason",
        "created_at",
        "started_at",
        "deadline_at",
        "completed_at",
        "last_activity_at",
        "recovery_available",
        "sealed_output_status",
        "scheduler_signal_status",
    )
    if value.get("state") != "completed":
        result["diagnostic_summary"] = pick(
            value.get("diagnostic_summary") or {},
            "failure",
            "latest_rejection",
            "latest_tool_error",
            "recent_errors",
            "rejection_count",
        )
    if value.get("state") == "failed" and "compact_recovery_status" in value:
        result["compact_recovery_status"] = value["compact_recovery_status"]
    if response_profile == "navigation":
        result.update(pick(value, "output_delivery", "output_index", "output_metadata"))
    elif response_profile == "decision" and value.get("state") == "completed":
        result.update(
            pick(
                value,
                "output_delivery",
                "output_metadata",
                "selected_output",
                "scheduler_signal",
            )
        )
    if diagnostics_requested and "diagnostic_events" in value:
        result["diagnostic_events"] = value["diagnostic_events"]
    result["detail"] = {
        "tool": "run_status",
        "name": value.get("name"),
        "response_profile": "compat",
        "view": "detail",
        "output_paths": [],
    }
    return result


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


def operation_detail(value):
    """One compiled declaration, without obsolete routing or duplicate port lists."""
    result = {key: item for key, item in value.items() if key != "accepts_actions"}
    validation = result.get("input_validation")
    if isinstance(validation, dict):
        # Cardinality and optionality are already explicit on every input port.
        result["input_validation"] = {key: item for key, item in validation.items()
            if key not in {"required_inputs", "optional_inputs"}}
    return result


def operation_revision_policy(spec):
    """Expose revision call rules from the same immutable OperationSpec."""
    review = spec.review
    revision_base_ports = [port.name for port in spec.inputs if port.usage == "revision_base"]
    change_request_ports = [port.name for port in spec.inputs if port.usage == "change_request"]
    return {
        "max_revisions": 0 if review is None else review.max_revisions,
        "requires_progress_between_change_requests": bool(
            review is not None and review.max_revisions > 0
        ),
        "revision_base_ports": revision_base_ports,
        "change_request_ports": change_request_ports,
        "progress_fingerprint_ports": change_request_ports if (
            review is not None and review.progress_fingerprint is not None
        ) else [],
    }


def operation_invoke_contract(value, *, revision_policy):
    """Project one callable contract from the same compiled catalog item."""
    result = pick(
        value,
        "operation_id",
        "version",
        "operation_digest",
        "executor_kind",
        "catalog_scope",
        "purpose",
        "applies_when",
        "not_for",
        "inputs",
        "outputs",
        "input_admission",
        "input_validation",
        "complete_transform_family",
        "consequence",
        "review_edge",
        "requires_independent_review",
        "requires_human_approval",
        "timeout_seconds",
        "max_input_bytes",
        "default_max_attempts",
        "runtime_binding",
    )
    result["revision_policy"] = revision_policy
    return result


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
        groups = {}
        for index, item in enumerate(tails):
            tail = item.get("tail", "")
            digest = hashlib.sha256(tail.encode("utf-8")).hexdigest()
            group = groups.setdefault(digest, {"sha256": digest, "sources": [],
                "pointers": [], "excerpt": tail[-384:], "omitted_characters": max(0, len(tail)-384)})
            group["sources"].append(item.get("source"))
            group["pointers"].append(f"/progress/log_tails/{index}")
        entries = list(groups.values())
        for entry in entries:
            entry["sources_omitted"] = max(0, len(entry["sources"])-8)
            entry["sources"] = entry["sources"][:8]
            entry["pointers"] = entry["pointers"][:8]
        # The raw detail response remains unchanged. This index is navigation,
        # and explicitly marks both excerpt omissions and unlisted log groups.
        result["progress"]["log_index"] = entries[:4]
        result["progress"]["log_groups_omitted"] = max(0, len(entries)-4)
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
        "output_delivery", "selected_output", "output_index", "scheduler_signal_status", "scheduler_signal",
        "diagnostic_events")
    recovery = result.get("recovery")
    if isinstance(recovery, dict) and isinstance(recovery.get("coverage"), dict):
        coverage = recovery["coverage"]
        compact = pick(coverage, "format", "scope", "status", "saved_count", "saved_bytes",
            "saved_by_scope", "omitted_count", "normalized_count", "writers_stopped",
            "original_retained", "complete")
        omitted = coverage.get("omitted")
        if isinstance(omitted, list):
            compact["omitted_listed_count"] = len(omitted)
            # Only known mechanical categories, never arbitrary path-like diagnostic text.
            reasons = {item.get("reason") for item in omitted if isinstance(item, dict)
                and isinstance(item.get("reason"), str)}
            known = {"symlink", "bytecode_cache", "scan_limit", "unsupported_type", "file_limit",
                "changed_during_copy", "byte_limit", "unsafe_unreadable_or_oversized"}
            compact["omission_reasons"] = sorted(reasons & known)
            if reasons - known:
                compact["omission_reasons"].append("other")
        result["recovery"] = {**recovery, "coverage": compact}
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
        response_profile = arguments.get("response_profile", "compat")
        validate_run_status_profile(
            response_profile=response_profile,
            view=arguments.get("view", "summary"),
            output_mode=arguments.get("output_mode", "values"),
            output_paths=arguments.get("output_paths"),
        )
        if response_profile != "compat":
            return run_profile_projection(
                value,
                response_profile=response_profile,
                diagnostics_requested=arguments.get("diagnostic_after") is not None,
            )
        if detail:
            return value
        result = run_summary(value)
        if arguments.get("output_paths") is None:
            _summary_excerpt(result)
        return result
    if name in {"execution_status", "execution_sync", "execution_start", "execution_cancel", "execution_abandon"}:
        return value if detail else execution_summary(value)
    if name == "operation_invoke":
        kind = value.get("executor_kind")
        result = value.get("result")
        if not isinstance(result, dict) or result.get("state") in {"rejected", "failed", "cancelled", "timed_out"}:
            return value
        if kind == "agent":
            result = pick(result, "name", "state", "operation_id", "agent_type", "execution_profile",
                "deadline_at", "output_artifact_name", "draft_from", "recovery", "normalized_request",
                "diagnostics", "missing_inputs", "review_url", "approval_name")
            result["detail"] = {"tool": "run_status", "name": result.get("name"), "view": "detail", "output_paths": []}
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
        else:
            items = [operation_detail(item) for item in items]
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
            result["result_artifact_name"] = value.get("result_artifact_name")
        return result
    if name in {"run_list", "execution_list", "approval_list"}:
        field = {"run_list": "runs", "execution_list": "executions", "approval_list": "approvals"}[name]
        if not detail:
            value = {**value, field: [pick(item, "name", "state", "status", "operation_id",
                        "output_artifact_name", "selected_option") for item in value[field]]}
        return value
    if name == "artifact_catalog" and arguments.get("view") == "parents":
        return value
    if name == "artifact_catalog" and arguments.get("view") == "producer_inputs":
        return value
    if name == "artifact_catalog" and not detail:
        return {**pick(value, "name", "kind", "schema", "media_type", "size_bytes", "payload_schema_version"),
                "parent_count": value["parent_count"] if "parent_count" in value else len(value["parents"]),
                "detail": {"tool": name, "name": value["name"], "view": "parents"}}
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


__all__ = [
    "RUN_RESPONSE_PROFILES",
    "operation_detail",
    "operation_invoke_contract",
    "operation_revision_policy",
    "page",
    "pick",
    "root_response",
    "run_profile_projection",
    "validate_run_status_profile",
]
