"""Read projections for MCP clients; services and sealed records stay complete."""
from __future__ import annotations

import base64
import binascii
import hashlib
import json

from .mcp_root_shared import RootToolError
from ..service.run_read_projection import run_intent_projection, run_is_terminal, pick


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
    result["contract_view_version"] = "invoke.scientific.v3"
    result["binding_policy"] = "Choose scientific materials by their instance names. Control resolves declared exact original materials; missing or ambiguous origins require repair of the selected subject. Internal bindings are not caller inputs."
    result["review_policy"] = "Independent review is optional unless this action explicitly requests qualification or authorization. A review applies only to its exact immutable subject."
    # Use the actual caller DTO once, including enum/default/recovery rules.
    # Scientific port constraints remain above; do not create another schema
    # for Worker output or duplicate ScientificIntent definitions here.
    from .mcp_root import OperationCallInput
    call_schema = OperationCallInput.model_json_schema()
    call_schema["properties"]["operation_id"]["const"] = value["operation_id"]
    call_schema["$defs"]["OperationInputSelection"]["properties"]["port"]["enum"] = [
        port["name"] for port in value.get("inputs", ())]
    call_schema["properties"]["inputs"]["description"] = (
        "One entry per chosen visible port listed in this contract's inputs: "
        "{port, artifact_names: [exact semantic names]}. Obey those ports' cardinality, "
        "schema, source and qualification constraints; omit irrelevant optional ports.")
    if value.get("executor_kind") == "agent":
        call_schema["properties"]["instruction"]["description"] = (
            "Required for Agent tasks. " + call_schema["properties"]["instruction"]["description"])
        call_schema["properties"]["scientific_intent"]["description"] += (
            " Recommended for background research; no mechanical identifiers.")
    result["invocation"] = {"tool": "operation_invoke", "inputSchema": call_schema,
        "description": "Complete caller contract for this selected Operation. Use scid_call(name='operation_invoke', arguments={operation_id: this Operation ID, ...caller inputs}); the Operation ID is not the tool name; no separate scid_describe(operation_invoke) is needed. Optional preflight creates nothing; reuse its normalized_request unchanged.",
        "idempotency": "Reuse a name only for an identical request. An intentional changed request uses on_conflict=create_revision.",
        "dispatch": "For a queued Agent, use its returned dispatch instructions and frozen execution_profile. Transform and Approval actions complete through their returned result or review_url."}
    result["full"] = {"tool": "scid_describe", "name": value["operation_id"], "view": "full"}
    return result


def execution_summary(value):
    result = pick(value, "name", "state", "solver_state", "result_artifact_name",
                  "status_observed_at", "progress_observed_at", "reason", "observation_error",
                  "authorization", "authorization_required", "recovery", "submission", "approval")
    progress = value.get("progress") or {}
    if "progress" in value:
        result["progress"] = (None if value["progress"] is None else pick(progress,
            "elapsed_seconds", "started_at", "completed_at", "observed_at", "state", "exit_code",
            "reason", "error", "diagnostic_ref", "diagnostics", "observation_error"))
    if isinstance(progress, dict) and isinstance(progress.get("log_tails"), list):
        from ...plugin_runtime.experiment import progress_summary
        result["progress"].update(progress_summary(progress))
    if isinstance(progress, dict) and progress.get("log_tails") and progress.get("log_cache_state") != "released":
        result["logs"] = {"tool": "scid_call", "arguments": {"name": "execution_logs",
            "surface": "execution", "arguments": {"name": value.get("name")}}}
    if "collection" in value:
        result["collection"] = pick(value["collection"], "state", "accepted", "busy",
            "completed_bytes", "total_bytes", "completed_files", "total_files",
            "total_seconds", "recovery_pending", "reason", "error", "diagnostic_ref", "diagnostics",
            "record_error", "progress_error", "stop_record_error", "observation_error", "stop_observation_error", "stop_reason")
    result["detail"] = {"tool": "scid_call", "arguments": {"name": "execution_status",
        "surface": "execution", "arguments": {"name": value.get("name"), "view": "detail"}}}
    return result


def scheduling_summary(value):
    """Discoverable state for any client; no claim that a model has read results."""
    result = pick(value, 'state', 'mode', 'reason', 'objective_name', 'can_schedule',
        'writer', 'fault_code', 'runtime_status', 'historical')
    result['read'] = {'tool': 'progression_status'}
    if value.get('objective_name'):
        result['objective_read'] = {'tool': 'artifact_catalog',
            'name': value['objective_name'], 'view': 'content'}
    result['budget'] = pick(value.get('budget') or {}, 'observed_tokens', 'remaining_tokens',
        'closeout_reserve_tokens', 'observed_worker_thread_tokens', 'new_task_allowed', 'limitation',
        'token_coverage', 'token_enforcement', 'elapsed_seconds', 'tasks')
    notices = value.get('notifications') or {}
    result['notifications'] = pick(notices, 'current_id', 'omitted', 'delivery', 'read_status')
    result['notifications']['count'] = len(notices.get('items', []))
    result['report_available'] = bool(value.get('report') or value.get('last_report'))
    closeout = value.get('closeout') or {}
    tasks = closeout.get('tasks', [])
    result['handoff'] = dict(task_count=len(tasks),
        sealed_result_count=sum(task.get('state') == 'completed' and bool(task.get('output_artifact_name')) for task in tasks),
        accepted_tasks_terminal=closeout.get('accepted_tasks_terminal'),
        in_flight=closeout.get('in_flight', []),
        unresolved_count=len(closeout.get('unresolved', [])),
        omitted_count=len(closeout.get('omissions', [])),
        scientific_content='omitted; read progression_status for the exact handoff and result navigation',
        read={'tool': 'progression_status'})
    return result


def _list_page(result, *, field, items):
    result = {**result, field:items}
    if field == "runs" and "current_goal_tasks" in result:
        names = {item["name"] for item in items}
        result["current_goal_tasks"] = [name for name in result["current_goal_tasks"] if name in names]
    return result


def _bounded_list(result, *, field, key, budget):
    """Deliver complete entries or explicit omission markers with a usable cursor."""
    def size(value):
        return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    items, selected = result[field], []
    for index, item in enumerate(items):
        candidate = _list_page(result, field=field, items=[*selected, item])
        if index + 1 < len(items):
            candidate.update(next_before=item[key], page_limited_by="bytes")
        if size(candidate) > budget:
            if selected:
                return _list_page({**result, "next_before":selected[-1][key], "page_limited_by":"bytes"},
                    field=field, items=selected)
            # Do not make one oversized object a permanent pagination barrier.
            # This is an omission marker, never a substitute scientific summary.
            request = ({"name":"run_status", "arguments":{"name":item[key], "intent":"navigation"}}
                if field == "runs" else {"name":"artifact_catalog", "arguments":{"name":item[key]}})
            item = {key:item[key], "entry_omitted":"page_byte_budget", "read_request":request}
            candidate[field] = [item]
            if size(candidate) > budget:
                # The exact per-object read_request supersedes the page's generic
                # detail template; avoid repeating navigation at the minimum budget.
                result = {name:value for name, value in result.items() if name != "detail"}
                candidate.pop("detail", None)
            if size(candidate) > budget:
                raise RootToolError("list_metadata_too_large: response exceeds configured page budget")
        selected.append(item)
    result = _list_page(result, field=field, items=selected)
    if size(result) > budget:
        raise RootToolError("list_metadata_too_large: response exceeds configured page budget")
    return result


def append_attention(response, notices, *, budget=None, field=None, key=None):
    """Fit the complete reply; never acknowledge notices omitted by its byte limit."""
    def size(value):
        return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    result = dict(response)
    selected = []
    for event in notices['events']:
        candidate = {**result, 'attention_notifications':{
            'events':[*selected, event], 'more_available':False}}
        # Keep at least one list item: an empty page cannot advance next_before.
        # Trim only while trying to deliver the first notice, not an entire burst.
        while (budget is not None and size(candidate)>budget and not selected
                and field and len(result.get(field, ()))>1):
            result = _list_page(result, field=field, items=result[field][:-1])
            result.update(next_before=result[field][-1][key], page_limited_by='bytes')
            candidate = {**result, 'attention_notifications':{
                'events':[event], 'more_available':False}}
        if budget is not None and size(candidate)>budget:
            break
        selected.append(event)
    if not selected:
        return response, 0
    result['attention_notifications'] = {'events':selected,
        'more_available':notices['more_available'] or len(selected)<len(notices['events'])}
    return result, len(selected)


def root_response(name, value, arguments, *, read_settings=None):
    """Never replace a scientific object, precise request, or error with a verdict."""
    detail = arguments.get("view") == "detail"
    if name in {"execution_status", "execution_sync", "execution_start", "execution_cancel", "execution_abandon"}:
        if detail and isinstance(value.get("progress"), dict):
            from ...plugin_runtime.experiment import progress_summary
            # Even status detail does not implicitly deliver log bodies.
            value = {**value, "progress": {**{key: item for key, item in value["progress"].items()
                if key != "log_tails"}, **progress_summary(value["progress"])}}
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
            result["detail"] = {"tool": "run_status", "name": result.get("name"), "intent": "navigation"}
        # Transform/effect/approval returns already expose output identities and exact review URLs.
        return {**value, "result": result}
    if name == "run_record_failure":
        return run_intent_projection(value, intent="status")
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
            if not detail:
                result[field] = [pick(item, "artifact_name", "kind", "schema", "historical",
                    "selected_current", "claim_admissible", "producer_handoff") for item in items]
            result["detail"] = {"tool": "artifact_catalog", "name": "<artifact_name>", "view": "detail"}
            from ...agent_execution_settings import MCPReadSettings
            settings = read_settings or MCPReadSettings()
            return _bounded_list(result, field=field, key=key,
                budget=settings.detail_max_bytes if detail else settings.summary_max_bytes)
        if name == "execution_outputs":
            result["execution_name"] = value["execution_name"]
            result["result_artifact_name"] = value.get("result_artifact_name")
        return result
    if name in {"run_list", "execution_list", "approval_list"}:
        field = {"run_list": "runs", "execution_list": "executions", "approval_list": "approvals"}[name]
        if name == "run_list":
            if arguments.get('view') == 'history':
                return value
            result = {**value, field: [
                (item if run_is_terminal(item.get("state")) else run_intent_projection(item, intent="status"))
                if detail else pick(item, "name", "operation_id", "state",
                    "operation_contract_status", "recovery_available") for item in value[field]]}
            result["detail"] = {"tool": "run_status", "name": "<name>"}
            from ...agent_execution_settings import MCPReadSettings
            settings = read_settings or MCPReadSettings()
            return _bounded_list(result, field=field, key="name",
                budget=settings.detail_max_bytes if detail else settings.summary_max_bytes)
        if name == "execution_list" and detail:
            return {**value, field: [root_response("execution_status", item, arguments) for item in value[field]]}
        if not detail:
            value = {**value, field: [pick(item, "name", "state", "status", "operation_id",
                        "output_artifact_name", "selected_option", "recovery") for item in value[field]]}
        return value
    if name == "artifact_catalog" and arguments.get("view") in {"parents", "content"}:
        return value
    if name == "artifact_catalog" and arguments.get("view") == "producer_inputs":
        return value
    if name == "artifact_catalog" and not detail:
        return {**pick(value, "name", "kind", "schema", "media_type", "size_bytes", "payload_schema_version"),
                "parent_count": value["parent_count"] if "parent_count" in value else len(value["parents"]),
                "detail": {"tool": name, "name": value["name"], "view": "parents"}}
    if name in {"instance_current", "instance_close"} and not detail:
        result = pick(value, "name", "title", "state", "management_url")
        if isinstance(value.get('scheduling'), dict):
            result['scheduling'] = scheduling_summary(value['scheduling'])
        return result
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
                "detail": {"tool": "scid_call", "arguments": {"name": name, "surface": "execution",
                    "arguments": {"operation_id": arguments["operation_id"], "view": "detail"}}}}
    return value


__all__ = [
    "operation_detail",
    "operation_invoke_contract",
    "operation_revision_policy",
    "page",
    "pick",
    "root_response",
    "run_intent_projection",
]
