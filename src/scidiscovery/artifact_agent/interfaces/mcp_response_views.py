"""Read projections for MCP clients; services and sealed records stay complete."""
from __future__ import annotations

import base64
import binascii
import hashlib
import json

from .mcp_root_shared import RootToolError


RUN_RESPONSE_PROFILES = ("compat", "poll", "navigation", "decision")


def validate_run_status_profile(*, response_profile, view, output_mode, output_paths,
                                include_full_output=False):
    """Keep the model-visible profile matrix and both runtime checks identical."""
    if include_full_output and not (
        view == "detail" and response_profile == "compat" and output_mode == "values"
        and output_paths is None
    ):
        raise RootToolError('include_full_output=true requires view="detail", '
            'response_profile="compat", output_mode="values" and omitted/null output_paths')
    if output_mode == "values" and output_paths and "" in output_paths:
        raise RootToolError('root output pointer requires include_full_output=true with '
            'view="detail", response_profile="compat" and omitted/null output_paths')
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
            'run_status response_profile="poll" requires output_mode="values" and output_paths=[]; '
            'use explicit response_profile="decision" for selected non-root values'
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
        output_mode == "values" and (output_paths is None or isinstance(output_paths, list))
    ):
        raise RootToolError(
            'run_status response_profile="decision" requires output_mode="values" '
            'and optional named output_fields or output_paths'
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
        "agent_type",
        "execution_profile",
        "deadline_at",
        "last_activity_at",
        "output_artifact_name",
        "recovery_available",
        "sealed_output_status",
        "diagnostics_available",
        "content_unavailable",
        "sealed_stages",
        "dispatch",
        "reason",
    )
    if isinstance(result.get("execution_profile"), dict):
        result["execution_profile"] = pick(result["execution_profile"], "profile")
    if response_profile == "navigation" and value.get("state") == "completed":
        result.update(pick(value, "output_delivery", "output_index", "output_metadata"))
    elif response_profile == "decision" and value.get("state") == "completed":
        result.update(
            pick(
                value,
                "output_delivery",
                "output_metadata",
                "selected_output",
                "scheduler_signal",
                "scheduler_signal_status",
                "scheduler_signal_omissions",
            )
        )
    return result


def run_is_terminal(state):
    # Unknown lifecycle values fail closed; they cannot opt into long details.
    return state in {"completed", "failed", "timed_out", "cancelled", "canceled"}


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


_NAV_DIMENSIONS = ("consequence", "executor_kind", "input_schema")
_NAV_BUDGET = {"index": 8192, "facets": 4096, "matches": 8192}


def _nav_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
        allow_nan=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _nav_values(item, dimension):
    if dimension == "input_schema":
        return sorted({port["schema"] for port in item.get("inputs", ())})
    value = item.get(dimension)
    return [] if value is None else [value]


def _nav_cursor(snapshot_digest, query_digest, offset, last_key):
    data = json.dumps([1, snapshot_digest, query_digest, offset, _nav_digest(last_key)],
        separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _nav_start(items, before, snapshot_digest, query_digest, key):
    if before is None:
        return 0
    try:
        data = base64.urlsafe_b64decode(before + "=" * (-len(before) % 4))
        version, cursor_snapshot, cursor_query, offset, last_key_digest = json.loads(data)
    except (ValueError, TypeError, UnicodeDecodeError, binascii.Error) as error:
        raise RootToolError("invalid navigation cursor; restart_query") from error
    if version != 1 or type(offset) is not int or not isinstance(last_key_digest, str):
        raise RootToolError("invalid navigation cursor; restart_query")
    if cursor_snapshot != snapshot_digest:
        raise RootToolError("catalog_changed; restart_query")
    if cursor_query != query_digest:
        raise RootToolError("cursor_query_mismatch; restart_query")
    if not 1 <= offset < len(items) or _nav_digest(items[offset - 1][key]) != last_key_digest:
        raise RootToolError("cursor item is no longer present; restart_query")
    return offset


def _nav_page(items, *, key, limit, before, snapshot_digest, query_digest, budget, response):
    start = _nav_start(items, before, snapshot_digest, query_digest, key)
    remaining = items[start:]
    field = "facets" if key == "value" else "operations"
    for count in range(min(limit, len(remaining)), -1, -1):
        selected = remaining[:count]
        next_before = (_nav_cursor(snapshot_digest, query_digest, start + count, selected[-1][key])
            if start + count < len(items) and selected else None)
        candidate = {**response, field: selected, "returned": count,
            "next_before": next_before, "complete": next_before is None}
        if field == "facets":
            candidate["omitted_count"] = len(items) - start - count
        if len(json.dumps(candidate, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) <= budget:
            if count == 0 and remaining:
                raise RootToolError("navigation_entry_too_large; cannot return a progressing page")
            return candidate
    raise RootToolError("navigation_response_too_large; cannot return required metadata")


def operation_navigation(value, arguments):
    view = arguments["view"]
    if value["scope"] != "public":
        raise RootToolError("navigation views require scope=public")
    if arguments.get("operation_id") is not None:
        raise RootToolError("navigation views do not accept operation_id; use view=detail")
    dimension = arguments.get("dimension")
    where = arguments.get("where")
    if view != "facets" and dimension is not None:
        raise RootToolError("dimension is available only for view=facets")
    if view != "matches" and where is not None:
        raise RootToolError("where is available only for view=matches")
    if view == "facets" and where is not None:
        raise RootToolError("facets do not accept filters")
    items = sorted(value["operations"], key=lambda item: item["operation_id"])
    snapshot_digest = _nav_digest({"version": 1, "catalog_digest": value["catalog_digest"],
        "state": value["navigation_state"],
        "visible": [(item["operation_id"], item.get("operation_digest"), item.get("purpose"),
            item.get("consequence"), item.get("executor_kind"),
            _nav_values(item, "input_schema"), item.get("runtime_binding")) for item in items]})
    filters = {}
    if view == "matches":
        if not isinstance(where, dict) or not where:
            raise RootToolError("matches requires nonempty where; use view=index for the full public set")
        if len(where) > len(_NAV_DIMENSIONS):
            raise RootToolError("too many P1 filter fields; use consequence, executor_kind or input_schema")
        unknown_fields = sorted(set(where) - set(_NAV_DIMENSIONS))
        if unknown_fields:
            raise RootToolError(f"unsupported P1 filter field; available: {list(_NAV_DIMENSIONS)}")
        for field in sorted(where):
            raw = where[field]
            requested = [raw] if isinstance(raw, str) else raw
            if (not isinstance(requested, list) or not 1 <= len(requested) <= 8
                or any(not isinstance(entry, str) or not entry or len(entry) > 4096 for entry in requested)):
                raise RootToolError(f"invalid {field} filter; use one to eight nonempty strings of at most 4096 characters")
            filters[field] = sorted(set(requested))
    query_digest = _nav_digest({"version": 1, "scope": "public", "view": view,
        "dimension": dimension, "where": filters, "sort": "ascending", "projection": "root"})
    common = {"scope": "public", "view": view,
        "catalog_digest": value["catalog_digest"],
        "navigation_snapshot_digest": snapshot_digest, "query_digest": query_digest,
        "visible_total": len(items), "semantic_labels_available": False}
    if view == "facets":
        if dimension is None:
            if arguments.get("before") is not None:
                raise RootToolError("facets without dimension do not accept before")
            result = {**common, "dimensions": [{"name": name,
                "value_count": len({entry for item in items for entry in _nav_values(item, name)}),
                "unclassified_count": sum(not _nav_values(item, name) for item in items)}
                for name in _NAV_DIMENSIONS], "returned": len(_NAV_DIMENSIONS),
                "next_before": None, "complete": True}
            if len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > _NAV_BUDGET[view]:
                raise RootToolError("navigation_response_too_large; cannot return dimension index")
            return result
        counts = {entry: sum(entry in _nav_values(item, dimension) for item in items)
            for entry in sorted({entry for item in items for entry in _nav_values(item, dimension)})}
        facets = [{"value": entry, "count": count} for entry, count in counts.items()]
        return _nav_page(facets, key="value", limit=min(arguments["limit"], 12),
            before=arguments.get("before"), snapshot_digest=snapshot_digest,
            query_digest=query_digest, budget=_NAV_BUDGET[view], response={**common,
                "dimension": dimension, "total": len(facets),
                "unclassified_count": sum(not _nav_values(item, dimension) for item in items)})
    if view == "matches":
        matched = [item for item in items if all(
            set(_nav_values(item, field)) & set(requested)
            for field, requested in filters.items())]
        projected = [_nav_entry(item, matches=True) for item in matched]
        omitted = _nav_projected_omissions(projected)
        return _nav_page(projected, key="operation_id", limit=min(arguments["limit"], 20),
            before=arguments.get("before"), snapshot_digest=snapshot_digest,
            query_digest=query_digest, budget=_NAV_BUDGET[view], response={**common, **omitted,
                "matched_total": len(matched), "filtered_out_count": len(items) - len(matched),
                "unclassified_count": None, "coverage": "filtered_subset", "filters_applied": filters,
                "fallback": {"kind": "operations", "view": "index"},
                "describe": {"tool": "scid_describe", "name": "<selected operation_id>", "view": "invoke"}})
    projected = [_nav_entry(item) for item in items]
    return _nav_page(projected, key="operation_id", limit=arguments["limit"],
        before=arguments.get("before"), snapshot_digest=snapshot_digest,
        query_digest=query_digest, budget=_NAV_BUDGET[view], response={**common,
            **_nav_omissions(items),
            "describe": {"tool": "scid_describe", "name": "<selected operation_id>", "view": "invoke"}})


def _nav_omissions(items):
    count = sum(len(item.get("purpose") or "") > 120 for item in items)
    return {"omitted_fields": ["purpose_tail"], "omitted_count": count} if count else {}


def _nav_projected_omissions(items):
    omitted = [item["omitted_fields"] for item in items if "omitted_fields" in item]
    return {"omitted_fields": sorted({field for fields in omitted for field in fields}),
        "omitted_count": len(omitted)} if omitted else {}


def _nav_entry(item, *, matches=False):
    purpose = item.get("purpose") or ""
    entry = {"operation_id": item["operation_id"], "purpose": purpose[:120]}
    if matches:
        omitted = ["purpose_tail"] if len(purpose) > 120 else []
        entry.update(consequence=item.get("consequence"), executor_kind=item.get("executor_kind"),
            input_schemas=_nav_values(item, "input_schema"),
            runtime_status=(item.get("runtime_binding") or {}).get("status", "available"))
        size = lambda: len(json.dumps(entry, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        if size() > 320:
            entry.pop("input_schemas")
            omitted.append("input_schemas")
        if omitted:
            entry["omitted_fields"] = omitted
        while size() > 320 and entry["purpose"]:
            entry["purpose"] = entry["purpose"][:-1]
            if "purpose_tail" not in omitted:
                omitted.append("purpose_tail")
                entry["omitted_fields"] = omitted
        if size() > 320:
            raise RootToolError(f"navigation_entry_too_large: {item['operation_id']}")
    return entry


def operation_detail(value):
    """One compiled declaration, without duplicate port lists."""
    result = dict(value)
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
    # Strip only reviewed execution-only fields. Unknown future constraints are
    # retained, including unknown fields inside every input and output port.
    execution_only = {"native_shell", "native_view_image", "network_mode",
        "max_network_requests", "max_output_bytes", "max_files",
        "optional_runtime_services", "executor_model_usage"}
    result = {key: item for key, item in value.items() if key not in execution_only}
    result["revision_policy"] = revision_policy
    result["contract_view_version"] = "invoke.scientific.v2"
    result["binding_policy"] = "Choose scientific materials by their instance names. Control resolves declared exact original materials; missing or ambiguous origins require repair of the selected subject. Internal bindings are not caller inputs."
    result["review_policy"] = "Independent review is optional unless this action explicitly requests qualification or authorization. A review applies only to its exact immutable subject."
    result["invocation"] = {"tool": "operation_invoke", "required": ["name", "operation_id", "inputs"],
        "instruction": "Required for Agent tasks: state the scientific question and intended deliverable.",
        "inputs": "One entry per chosen visible port: {port, artifact_names: [exact semantic names]}. Omit optional ports when irrelevant.",
        "idempotency": "Reuse a name only for an identical request. An intentional changed request uses on_conflict=create_revision.",
        "dispatch": "For a queued Agent, use its returned dispatch instructions and frozen execution_profile. Transform and Approval actions complete through their returned result or review_url."}
    result["full"] = {"tool": "scid_describe", "name": value["operation_id"], "view": "full"}
    return result


def execution_summary(value):
    result = pick(value, "name", "state", "solver_state", "result_artifact_name",
                  "status_observed_at", "progress_observed_at", "reason", "observation_error",
                  "authorization", "authorization_required")
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
        response_profile = arguments.get("response_profile", "decision")
        validate_run_status_profile(
            response_profile=response_profile,
            view=arguments.get("view", "summary"),
            output_mode=arguments.get("output_mode", "values"),
            output_paths=arguments.get("output_paths"),
            include_full_output=arguments.get("include_full_output", False),
        )
        if not run_is_terminal(value.get("state")):
            return run_profile_projection(value, response_profile="poll")
        if response_profile != "compat":
            return run_profile_projection(
                value,
                response_profile=response_profile,
                diagnostics_requested=arguments.get("diagnostic_after") is not None,
            )
        if detail:
            return value
        result = run_summary(value)
        if "sealed_stages" in value:
            result["sealed_stages"] = value["sealed_stages"]
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
                "operation_version", "operation_digest",
                "deadline_at", "output_artifact_name", "draft_from", "recovery", "normalized_request",
                "diagnostics", "missing_inputs", "review_url", "approval_name", "dispatch")
            result["detail"] = {"tool": "run_status", "name": result.get("name"), "view": "detail", "output_paths": []}
        # Transform/effect/approval returns already expose output identities and exact review URLs.
        return {**value, "result": result}
    if name == "run_record_failure":
        return run_summary(value)
    if name == "operation_catalog":
        if arguments["view"] in _NAV_BUDGET:
            return operation_navigation(value, arguments)
        if arguments.get("dimension") is not None or arguments.get("where") is not None:
            raise RootToolError("dimension and where require an explicit navigation view")
        items = value["operations"]
        selected = arguments.get("operation_id")
        if selected is not None:
            items = [item for item in items if item["operation_id"] == selected]
            if not items:
                raise RootToolError("operation is not available in the selected catalog scope")
        total = len(items)
        if not detail:
            items = sorted(items, key=lambda item: item["operation_id"])
            snapshot = _nav_digest({"version": "summary.v2", "catalog": value.get("catalog_digest"),
                "state": value.get("navigation_state"), "items": items})
            query = _nav_digest({"version": "summary.v2", "scope": value["scope"], "operation_id": selected})
            return _nav_page([pick(item, "operation_id", "purpose") for item in items],
                key="operation_id", limit=arguments["limit"], before=arguments.get("before"),
                snapshot_digest=snapshot, query_digest=query, budget=8192,
                response={"scope": value["scope"], "view": "summary", "total": total})
        items, cursor = page(items, key="operation_id", limit=arguments["limit"], before=arguments.get("before"))
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
        if name == "run_list":
            return {**value, field: [item if detail and run_is_terminal(item.get("state"))
                else run_profile_projection(item, response_profile="poll") for item in value[field]]}
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
