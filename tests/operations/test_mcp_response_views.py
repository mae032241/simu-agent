from contextlib import nullcontext
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolError
from scidiscovery.artifact_agent.interfaces.mcp_root_operation_routes import RootOperationRoutes
from scidiscovery.artifact_agent.interfaces.mcp_response_views import (
    operation_invoke_contract,
    page,
    run_intent_projection,
)


def router(**methods):
    facade = SimpleNamespace(runs=SimpleNamespace(), session_key=None, scheduling_guard=nullcontext,
        engineering_diagnostics=SimpleNamespace(capture=Mock()), _instance_id=lambda: "fixture", **methods)
    return RootMCPRouter(facade)


@pytest.mark.parametrize('tool', ['run_list', 'scientific_inventory'])
def test_large_summary_lists_obey_configured_bytes_and_resume_without_loss(tmp_path, tool):
    from scidiscovery.agent_execution_settings import load_settings
    config = tmp_path / 'agent-settings.json'
    config.write_text(json.dumps({'mcp_read': {'summary_max_bytes': 2048}}))
    entries = []
    for i in range(100):
        name = f'm8/material/{i:03d}/' + 'x' * 120
        if tool == 'run_list':
            entries.append({'name': name, 'operation_id': 'science.experiment.v1',
                'state': 'queued', 'operation_contract_status': 'historical', 'recovery_available': False,
                'execution_profile': {'profile': {'model': 'model', 'reasoning_effort': 'high'}},
                'dispatch': {'instruction': '重复说明' * 1000}})
        else:
            entries.append({'artifact_name': name, 'kind': 'report', 'schema': 'scientific.report.v1',
                'historical': True, 'selected_current': False, 'claim_admissible': False,
                'producer_handoff': 'blocked', 'revision': 27})
    field, key = ('runs', 'name') if tool == 'run_list' else ('objects', 'artifact_name')
    if tool == 'run_list':
        def listing(**args):
            items, cursor = page(entries, key=key, limit=args['limit'], before=args['before'])
            return {field: items, 'next_before': cursor}
    else:
        def listing(**args):
            return {field: entries}
    root = router(**{tool: listing})
    root.facade.runs.agent_settings = load_settings(config)
    seen, cursor = [], None
    for _ in range(101):
        result = root.call_tool(tool, {'view': 'summary', 'limit': 100, 'before': cursor})
        assert len(json.dumps(result, ensure_ascii=False, separators=(',', ':')).encode()) <= 2048
        assert result[field]
        assert 'dispatch' not in json.dumps(result) and 'execution_profile' not in json.dumps(result)
        if tool == 'scientific_inventory':
            assert all(item['claim_admissible'] is False and item['producer_handoff'] == 'blocked'
                and item['historical'] is True for item in result[field])
            assert 'revision' not in json.dumps(result)
        seen.extend(item[key] for item in result[field])
        cursor = result['next_before']
        if cursor is None:
            break
        assert cursor == seen[-1] and result['page_limited_by'] == 'bytes'
    assert seen == [item[key] for item in entries]


def test_list_byte_pagination_preserves_owner_continuation_and_exact_detail():
    from scidiscovery.agent_execution_settings import MCPReadSettings
    from scidiscovery.artifact_agent.interfaces.mcp_response_views import root_response
    settings = MCPReadSettings(summary_max_bytes=1024, detail_max_bytes=1024)
    rows = [{'name': str(i), 'state': 'completed', 'reason': '中文原文' * 60} for i in range(3)]
    result = root_response('run_list', {'runs': rows, 'next_before': '2'}, {'view': 'detail'}, read_settings=settings)
    assert result['runs'] == rows[:1] and result['next_before'] == '0'
    assert len(json.dumps(result, ensure_ascii=False, separators=(',', ':')).encode()) <= 1024
    result = root_response('run_list', {'runs': rows[:1], 'next_before': '0'}, {'view': 'detail'}, read_settings=settings)
    assert result['next_before'] == '0' and result['runs'] == rows[:1]
    omitted = root_response('run_list', {'runs': [{**rows[0], 'reason': '中文' * 2000}], 'next_before': None},
        {'view': 'detail'}, read_settings=settings)
    assert omitted['runs'][0]['entry_omitted'] == 'page_byte_budget'
    assert omitted['runs'][0]['name'] == rows[0]['name'] and omitted['next_before'] is None


def test_execution_poll_is_short_but_exact_logs_and_failure_remain_readable():
    full = {"name": "execution", "state": "failed", "solver_state": "failed",
        "progress": {"elapsed_seconds": 19, "exit_code": 1,
            "log_tails": [{"source": source, "tail": "specific solver error\n"*100}
                          for source in ("stdout", "solver_log")]},
        "collection": {"state": "failed", "error": {"code": "collection_timeout", "diagnostic_ref": "diag_saved"}}}
    root = router(execution_status=lambda **args: deepcopy(full), execution_sync=lambda **args: deepcopy(full))
    for name in ("execution_status", "execution_sync"):
        short = root.call_tool(name, {"name": "execution"}, surface="execution")
        assert "log_tails" not in short["progress"]
        assert short["collection"]["error"] == full["collection"]["error"]
        assert short["progress"]["exit_code"] == 1
        assert len(json.dumps(short)) < .4*len(json.dumps(full))
        detail = root.call_tool(name, {"name": "execution", "view": "detail"}, surface="execution")
        assert "specific solver error" not in json.dumps(detail)
        assert detail["collection"] == full["collection"]


def test_run_router_preserves_omission_and_named_selection():
    call = Mock(return_value={"name":"run", "state":"completed"})
    root = router(run_status=call)
    root.call_tool("run_status", {"name":"run"})
    assert call.call_args.kwargs == {"name":"run"}
    root.call_tool("run_status", {"name":"run", "intent":"decision", "output_fields":["summary"]})
    assert call.call_args.kwargs == {"name":"run", "intent":"decision", "output_fields":["summary"]}


@pytest.mark.parametrize("arguments", [
    {"response_profile":"poll"}, {"view":"detail"}, {"output_mode":"index"},
    {"include_full_output":True},
])
def test_retired_status_parameters_are_rejected(arguments):
    root = router(run_status=Mock())
    with pytest.raises(RootToolError):
        root.call_tool("run_status", {"name":"run", **arguments})
    root.facade.run_status.assert_not_called()


def test_run_compact_profile_golden_fields_keep_diagnostics_and_hide_payloads():
    full = {
        "name": "run", "operation_id": "science.fixture.v1", "operation_version": "1",
        "operation_digest": "a" * 64, "operation_contract_status": "current", "state": "failed",
        "reason": "exact failure", "created_at": "created", "started_at": "started",
        "deadline_at": "deadline", "completed_at": "finished", "last_activity_at": "activity",
        "recovery_available": False, "sealed_output_status": "unavailable",
        "scheduler_signal_status": "unavailable", "scheduler_signal": {"verdict": "blocked"},
        "bound_inputs": [{"port": "research_objective", "artifact_names": ["objective"]}],
        "native_execution": {"path": "/private"}, "tool_timing": [{"duration_seconds": 1}],
        "recovery": {"coverage": {"path": "/private"}},
        "compact_recovery_status": {"delivery_preserved": True, "resume_available": False,
            "draft_available": True, "recovery_pending": True, "original_retained": True,
            "reason_code": "writers_unconfirmed"},
        "diagnostic_summary": {"failure": {"category": "runtime_failure"},
            "latest_rejection": None, "latest_tool_error": None,
            "recent_errors": [{"engineering": {"reference": "diag_exact"}}], "rejection_count": 0},
        "diagnostic_events": {"events": [{"diagnostic": {"engineering": {"reference": "diag_exact"}}}],
            "next_after": 9},
        "selected_output": {"items": [{"value": "unsealed"}]},
    }
    without_events = run_intent_projection(full, intent="status")
    with_events = run_intent_projection(full, intent="status")
    assert "compact_recovery_status" not in without_events
    assert "diagnostic_summary" not in without_events
    assert "diagnostic_events" not in without_events
    assert "diagnostic_events" not in with_events
    for hidden in ("scheduler_signal", "bound_inputs", "native_execution", "tool_timing", "recovery", "selected_output"):
        assert hidden not in without_events
    assert "detail" not in without_events


@pytest.mark.parametrize("state", ["queued", "running", "failed", "timed_out"])
def test_run_decision_does_not_expose_unsealed_science(state):
    value = {"name": "run", "state": state, "sealed_output_status": "unavailable",
        "scheduler_signal_status": "unavailable", "selected_output": {"items": [{"value": "draft"}]},
        "scheduler_signal": {"verdict": "accept"}, "diagnostic_summary": {}}
    result = run_intent_projection(value, intent="decision")
    assert "selected_output" not in result and "scheduler_signal" not in result


def test_run_completed_navigation_and_decision_preserve_exact_mechanical_and_scientific_values():
    selected = {"artifact_name": "report", "kind": "science", "schema": "report.v1",
        "items": [{"pointer": "/summary", "status": "selected", "value": "exact"}]}
    index = {"artifact_name": "report", "kind": "science", "schema": "report.v1",
        "pointer": "", "status": "available", "children": [], "total_children": 0, "next_offset": None}
    signal = {"verdict": "accept", "limitations": ["exact"]}
    value = {"name": "run", "state": "completed", "sealed_output_status": "available",
        "scheduler_signal_status": "available", "selected_output": selected, "output_index": index,
        "output_delivery": "selected", "scheduler_signal": signal}
    decision = run_intent_projection(value, intent="decision")
    navigation = run_intent_projection({**value, "output_delivery": "index"}, intent="navigation")
    assert decision["selected_output"] == selected and decision["scheduler_signal"] == signal
    assert navigation["output_index"] == index and "scheduler_signal" not in navigation


@pytest.mark.parametrize(
    ("stored_code", "visible_code"),
    [("snapshot_unavailable", "snapshot_unavailable"),
     ("contract_unavailable", "contract_unavailable"),
     ("writers_unconfirmed", "writers_unconfirmed"),
     ("future_private_detail", "other"), (None, None)],
)
def test_compact_recovery_reason_code_is_allowlisted(stored_code, visible_code):
    from scidiscovery.artifact_agent.service.runs import RunService
    service = object.__new__(RunService)
    service._recovery_gate_status = lambda value: ({"delivery_preserved": True,
        "resume_available": False, "draft_available": True, "recovery_pending": True}, True, None)
    record = {"original_retained": True}
    if stored_code is not None:
        record["code"] = stored_code
    result = service.compact_recovery_status(SimpleNamespace(recovery_draft=record))
    assert result == {"delivery_preserved": True, "resume_available": False,
        "draft_available": True, "recovery_pending": True, "original_retained": True,
        "reason_code": visible_code}


def test_catalog_selects_full_exact_contract_and_paginates_without_hiding_tools():
    operations = [{"operation_id": f"operation{i}", "purpose": "test", "executor_kind": "agent",
                   "inputs": [{"name": "evidence"}], "timeout_seconds": 900} for i in range(5)]
    root = router(operation_catalog=lambda **args: {"scope": args["scope"], "operations": operations})
    first = root.call_tool("operation_catalog", {"limit": 2})
    assert set(first) == {"scope", "view", "operations", "total", "next_before", "returned", "complete"}
    assert set(first["operations"][0]) == {"operation_id", "purpose"}
    assert "inputs" not in first["operations"][0]
    found = first["operations"]
    cursor = first["next_before"]
    while cursor:
        part = root.call_tool("operation_catalog", {"limit": 2, "before": cursor})
        found += part["operations"]
        cursor = part["next_before"]
    assert [item["operation_id"] for item in found] == [item["operation_id"] for item in operations]
    detail = root.call_tool("operation_catalog", {"operation_id": "operation3", "view": "detail"})
    assert detail["operations"] == [operations[3]]
    with pytest.raises(RootToolError, match="not available"):
        root.call_tool("operation_catalog", {"operation_id": "missing", "view": "detail"})


def test_public_navigation_index_facets_matches_and_zero_match_are_bounded():
    operations = [
        {"operation_id": f"operation{i}", "operation_digest": str(i) * 64,
         "purpose": "Investigate " + "x" * 200, "executor_kind": "effect" if i == 4 else "agent",
         "consequence": "explore" if i < 3 else "scientific",
         "inputs": [{"schema": "source.v1" if i % 2 else "report.v1"}],
         "runtime_binding": {"status": "available"}}
        for i in range(5)
    ]
    state = {"items": operations}

    def catalog(**args):
        return {"scope": args["scope"], "operations": state["items"],
            "catalog_digest": "a" * 64,
            "navigation_state": [{"operation_id": item["operation_id"], "available": True}
                for item in state["items"]]}

    root = router(operation_catalog=catalog)
    default = root.call_tool("operation_catalog", {})
    assert default["view"] == "summary" and "navigation_snapshot_digest" not in default
    found = []
    cursor = None
    while True:
        part = root.call_tool("operation_catalog", {"view": "index", "limit": 2, "before": cursor})
        assert len(json.dumps(part, ensure_ascii=False).encode("utf-8")) <= 8192
        found.extend(item["operation_id"] for item in part["operations"])
        assert part["describe"] == {"tool": "scid_describe", "name": "<selected operation_id>", "view": "invoke"}
        assert all("describe" not in item for item in part["operations"])
        cursor = part["next_before"]
        if cursor is None:
            assert part["complete"] is True
            break
    assert found == [item["operation_id"] for item in operations]
    assert part["omitted_fields"] == ["purpose_tail"]
    dimensions = root.call_tool("operation_catalog", {"view": "facets"})
    assert dimensions["semantic_labels_available"] is False
    assert {entry["name"] for entry in dimensions["dimensions"]} == {
        "consequence", "executor_kind", "input_schema"}
    assert "facets" not in dimensions
    first_facet = root.call_tool("operation_catalog", {"view": "facets", "dimension": "consequence", "limit": 1})
    assert first_facet["total"] == 2 and first_facet["omitted_count"] == 1
    next_facet = root.call_tool("operation_catalog", {"view": "facets", "dimension": "consequence",
        "limit": 1, "before": first_facet["next_before"]})
    assert next_facet["complete"] and next_facet["omitted_count"] == 0
    matched = root.call_tool("operation_catalog", {"view": "matches", "where": {
        "consequence": ["explore"], "input_schema": "source.v1"}})
    assert matched["matched_total"] == 1 and matched["visible_total"] == 5
    assert matched["coverage"] == "filtered_subset"
    assert matched["describe"]["name"] == "<selected operation_id>"
    assert "describe" not in matched["operations"][0]
    zero = root.call_tool("operation_catalog", {"view": "matches", "where": {
        "consequence": "explore", "executor_kind": "effect"}})
    assert zero["matched_total"] == 0 and zero["operations"] == []
    assert zero["complete"] and zero["fallback"]["view"] == "index"
    absent = root.call_tool("operation_catalog", {"view": "matches", "where": {"consequence": "external"}})
    assert absent["matched_total"] == 0 and absent["operations"] == []
    assert absent["complete"] and absent["fallback"]["view"] == "index"
    unknown_schema = root.call_tool("operation_catalog", {"view": "matches", "where": {
        "input_schema": "schema.not.in.current.catalog"}})
    assert unknown_schema["matched_total"] == 0 and unknown_schema["complete"]


def test_navigation_cursor_binds_snapshot_query_and_scope():
    item = lambda number: {"operation_id": f"operation{number}", "operation_digest": "a" * 64,
        "purpose": "test", "executor_kind": "agent", "consequence": "scientific", "inputs": []}
    state = {"items": [item(1), item(2), item(3)], "backend_state": "ready"}

    def catalog(**args):
        return {"scope": args["scope"], "operations": state["items"],
            "catalog_digest": "a" * 64,
            "navigation_state": [{"operation_id": entry["operation_id"], "available": True,
                "backend_state": state["backend_state"]}
                for entry in state["items"]]}

    root = router(operation_catalog=catalog)
    first = root.call_tool("operation_catalog", {"view": "index", "limit": 1})
    cursor = first["next_before"]
    with pytest.raises(RootToolError, match="cursor_query_mismatch"):
        root.call_tool("operation_catalog", {"view": "matches", "limit": 1, "before": cursor,
            "where": {"consequence": "scientific"}})
    with pytest.raises(RootToolError, match="navigation cursor"):
        root.call_tool("operation_catalog", {"view": "index", "before": "operation1"})
    state["backend_state"] = "changed"
    with pytest.raises(RootToolError, match="catalog_changed"):
        root.call_tool("operation_catalog", {"view": "index", "limit": 1, "before": cursor})
    state["items"] = [item(1), item(3)]
    with pytest.raises(RootToolError, match="catalog_changed"):
        root.call_tool("operation_catalog", {"view": "index", "limit": 1, "before": cursor})
    with pytest.raises(RootToolError, match="scope=public"):
        root.call_tool("operation_catalog", {"scope": "support", "view": "index"})
    with pytest.raises(RootToolError, match="do not accept operation_id"):
        root.call_tool("operation_catalog", {"view": "index", "operation_id": "operation1"})


def test_navigation_byte_budget_pages_without_losing_entries():
    operations = [{"operation_id": f"operation{i:03d}", "operation_digest": "a" * 64,
        "purpose": "many " + "x" * 200, "executor_kind": "agent", "consequence": "scientific",
        "inputs": [{"schema": "source.v1"}]} for i in range(100)]
    root = router(operation_catalog=lambda **args: {"scope": args["scope"],
        "operations": operations, "catalog_digest": "a" * 64,
        "navigation_state": [{"operation_id": item["operation_id"], "available": True}
            for item in operations]})
    collected = []
    cursor = None
    while True:
        part = root.call_tool("operation_catalog", {"view": "index", "limit": 100, "before": cursor})
        assert part["returned"] > 0
        assert len(json.dumps(part, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) <= 8192
        collected.extend(item["operation_id"] for item in part["operations"])
        cursor = part["next_before"]
        if cursor is None:
            break
    assert collected == [item["operation_id"] for item in operations]


def test_navigation_oversized_minimum_entry_fails_without_empty_progress_page():
    item = {"operation_id": "oversized", "operation_digest": "a" * 64,
        "purpose": "test", "executor_kind": "agent", "consequence": "scientific",
        "inputs": [{"schema": "s" * 9000}]}
    root = router(operation_catalog=lambda **args: {"scope": args["scope"],
        "operations": [item], "catalog_digest": "a" * 64,
        "navigation_state": [{"operation_id": "oversized", "available": True}]})
    with pytest.raises(RootToolError, match="navigation_entry_too_large"):
        root.call_tool("operation_catalog", {"view": "facets", "dimension": "input_schema"})


def test_matches_omits_oversized_schema_list_explicitly_but_keeps_candidate():
    item = {"operation_id": "many_inputs", "operation_digest": "a" * 64,
        "purpose": "test", "executor_kind": "agent", "consequence": "scientific",
        "inputs": [{"schema": "wanted.v1"}] + [{"schema": f"extra{i}.v1"} for i in range(40)]}
    root = router(operation_catalog=lambda **args: {"scope": args["scope"],
        "operations": [item], "catalog_digest": "a" * 64,
        "navigation_state": [{"operation_id": "many_inputs", "available": True}]})
    result = root.call_tool("operation_catalog", {"view": "matches",
        "where": {"input_schema": "wanted.v1"}})
    assert result["matched_total"] == 1 and result["operations"][0]["operation_id"] == "many_inputs"
    assert result["omitted_fields"] == ["input_schemas"] and result["omitted_count"] == 1
    assert result["operations"][0]["omitted_fields"] == ["input_schemas"]
    assert "input_schemas" not in result["operations"][0]
    assert len(json.dumps(result["operations"][0], ensure_ascii=False,
        separators=(",", ":")).encode("utf-8")) <= 320


def test_navigation_cursor_stays_bounded_for_long_keys():
    operations = [{"operation_id": str(i) + "o" * 255, "operation_digest": "a" * 64,
        "purpose": "test", "executor_kind": "agent", "consequence": "scientific",
        "inputs": [{"schema": letter * 900}]}
        for i, letter in enumerate(("s", "t"))]
    root = router(operation_catalog=lambda **args: {"scope": args["scope"],
        "operations": operations, "catalog_digest": "a" * 64,
        "navigation_state": [{"operation_id": item["operation_id"], "available": True}
            for item in operations]})
    for view, dimension in (("index", None), ("facets", "input_schema")):
        query = {"view": view, "limit": 1}
        if dimension is not None:
            query["dimension"] = dimension
        first = root.call_tool("operation_catalog", query)
        assert len(first["next_before"]) <= 512
        second = root.call_tool("operation_catalog", {**query, "before": first["next_before"]})
        assert second["complete"] and second["returned"] == 1


def test_public_unavailability_diagnostic_uses_the_same_visibility_rule():
    compiled = SimpleNamespace(spec=SimpleNamespace(catalog_scope="public",
        executor=SimpleNamespace(kind="agent"), review=None))
    route = RootOperationRoutes()
    route._operation_catalog = SimpleNamespace(
        scheduler_projection=lambda: (SimpleNamespace(operation_id="blocked", catalog_scope="public"),),
        operation=lambda operation_id: compiled, digest=lambda: "a" * 64)
    route._operation_catalog_item = lambda item: {"operation_id": item.operation_id}
    route.runs = SimpleNamespace(backend=SimpleNamespace(
        supports_operation=lambda item: False,
        unsupported_requirements=lambda item: ("native_shell",)))
    result = route.operation_catalog(scope="public", navigation=True)
    assert result["operations"] == []
    assert result["navigation_state"] == [{"operation_id": "blocked", "available": False,
        "unavailable_reason": {"reason_code": "backend_requirements_unavailable",
            "operation_id": "blocked", "required": ["native_shell"]},
        "runtime_binding": None}]
    assert route._scheduler_operation_available("blocked") is False


def test_public_reviewer_and_effect_unavailability_reuse_catalog_gate(monkeypatch):
    from scidiscovery.artifact_agent.interfaces import mcp_root_operation_routes as routes
    monkeypatch.setattr(routes, "operation_local_worker_missing_tools", lambda compiled: ())
    monkeypatch.setattr(routes, "effect_operation_plan",
        lambda compiled: SimpleNamespace(executor="solver_adapter"))
    specs = {
        "proposal": SimpleNamespace(catalog_scope="public", executor=SimpleNamespace(kind="agent"),
            review=SimpleNamespace(reviewer_operation="reviewer", policy="optional")),
        "reviewer": SimpleNamespace(catalog_scope="support", executor=SimpleNamespace(kind="agent"),
            review=None),
        "execution": SimpleNamespace(catalog_scope="public", executor=SimpleNamespace(kind="effect"),
            review=None),
    }
    compiled = {name: SimpleNamespace(spec=spec) for name, spec in specs.items()}
    route = RootOperationRoutes()
    route._operation_catalog = SimpleNamespace(
        scheduler_projection=lambda: tuple(SimpleNamespace(operation_id=name,
            catalog_scope=spec.catalog_scope) for name, spec in specs.items()),
        operation=lambda name: compiled[name], digest=lambda: "a" * 64)
    route._operation_catalog_item = lambda item: {"operation_id": item.operation_id}
    route.runs = SimpleNamespace(backend=SimpleNamespace(
        supports_operation=lambda item: item is not compiled["reviewer"],
        unsupported_requirements=lambda item: ("native_shell",)))
    route.execution_bridge = None
    assert route.operation_catalog(scope="public")["operations"] == [{"operation_id": "proposal"}]
    result = route.operation_catalog(scope="public", navigation=True)
    reasons = {entry["operation_id"]: entry["unavailable_reason"]
        for entry in result["navigation_state"]}
    assert reasons["proposal"] is None  # Optional review does not block author availability.
    assert reasons["execution"] == {"reason_code": "effect_adapter_unavailable",
        "operation_id": "execution", "required": ["solver_adapter"]}
    assert next(entry for entry in result["navigation_state"] if entry["operation_id"] == "proposal")["available"]


def test_catalog_preserves_unknown_fields_and_removes_repeated_port_lists():
    declaration = {"operation_id": "operation", "future_constraint": {"exact": True},
        "inputs": [{"name": "evidence", "min_items": 1, "max_items": 2}],
        "outputs": [{"name": "result"}], "review_edge": {"operation_id": "review"},
        "input_validation": {"required_inputs": ["evidence"], "optional_inputs": [],
            "rule_id": "exact_evidence", "phase": "input_admission", "description": "Exact evidence required."},
        "input_admission": {"approval_kind": "evidence"}, "timeout_seconds": 900}
    original = deepcopy(declaration)
    root = router(operation_catalog=lambda **args: {"scope": args["scope"], "operations": [declaration]})
    result = root.call_tool("operation_catalog", {"operation_id": "operation", "view": "detail"})["operations"][0]
    assert declaration == original
    assert result["future_constraint"] == {"exact": True}
    assert set(result["input_validation"]) == {"rule_id", "phase", "description"}
    for key in ("inputs", "outputs", "review_edge", "input_admission", "timeout_seconds"):
        assert result[key] == declaration[key]


def test_operation_invoke_contract_keeps_call_rules_and_removes_executor_internals():
    full = {
        "operation_id": "science.fixture.v1", "version": "2", "operation_digest": "a" * 64,
        "executor_kind": "agent", "catalog_scope": "public", "purpose": "Test.",
        "applies_when": "Applicable.", "not_for": "Other work.",
        "inputs": [{"name": "research_objective", "min_items": 1, "max_items": 1,
            "required_non_null_fields": ["objective"], "usage": "claim_evidence",
            "exposure": "full", "require_current": True, "media_types": ["application/json"],
            "max_item_bytes": 4096}],
        "outputs": [{"name": "result", "min_items": 1, "max_items": 1}],
        "input_admission": {"cohort_id": "cohort"},
        "input_validation": {"rule_id": "exact", "phase": "input_admission"},
        "complete_transform_family": None, "consequence": "revise",
        "review_edge": {"reviewer_operation": "science.review.v1"},
        "revision_policy": {"max_revisions": 2,
            "requires_progress_between_change_requests": True,
            "revision_base_ports": ["prior_draft"], "change_request_ports": ["change_request"],
            "progress_fingerprint_ports": ["change_request"]},
        "requires_independent_review": True, "requires_human_approval": False,
        "timeout_seconds": 900, "max_input_bytes": 65536, "default_max_attempts": 2,
        "runtime_binding": {"process": "worker", "status": "available"},
        "native_shell": "workspace", "native_view_image": True,
        "network_mode": "restricted", "max_network_requests": 4,
        "max_output_bytes": 1048576, "max_files": 32,
        "optional_runtime_services": ["private"], "executor_model_usage": "internal",
    }
    before = deepcopy(full)
    invoke = operation_invoke_contract(full, revision_policy=full["revision_policy"])
    assert full == before
    for key in ("operation_id", "version", "operation_digest", "inputs", "outputs",
                "input_admission", "input_validation", "complete_transform_family",
                "review_edge", "revision_policy", "default_max_attempts", "runtime_binding"):
        assert invoke[key] == full[key]
    for removed in ("native_shell", "native_view_image", "network_mode", "max_network_requests",
                    "max_output_bytes", "max_files", "optional_runtime_services", "executor_model_usage"):
        assert removed not in invoke


def test_inventory_omits_full_catalog_and_preserves_null_parent_on_demand():
    inventory = Mock(return_value={"objects": [{"artifact_name": str(i)} for i in range(3)]})
    parent = {"name": "artifact", "schema": "opaque", "parents": [{"artifact_name": None}], "parent_artifact_names": [None]}
    root = router(scientific_inventory=inventory, artifact_catalog=lambda **args: parent)
    result = root.call_tool("scientific_inventory", {"limit": 2})
    assert inventory.call_args.kwargs == {"include_operations": False}
    assert "public_operations" not in result and result["next_before"] == "1"
    assert root.call_tool("artifact_catalog", {"name": "artifact"})["parent_count"] == 1
    assert root.call_tool("artifact_catalog", {"name": "artifact", "view": "detail"}) == parent


def test_transport_has_same_compact_result_in_both_representations_and_typed_errors():
    root = router(instance_current=lambda: {"state": "active", "name": "instance", "objective": "long"*10000})
    transport = MCPRouter(root, name="test")
    reply = transport.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "instance_current", "arguments": {}}})["result"]
    assert json.loads(reply["content"][0]["text"]) == reply["structuredContent"] == {"state": "active", "name": "instance"}
    error = transport.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "run_status", "arguments": {"name": "run", "view": "bogus"}}})["error"]
    assert error["data"]["diagnostics"][0]["path"] == "$[key]"


def test_lifecycle_paging_does_not_consume_unreturned_events(tmp_path):
    from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService
    service = SchedulerBindingService(tmp_path/"bindings.sqlite3")
    instance = service.create_instance(name="test", title="test", objective="fixture")
    args = dict(instance=instance.instance_id, observer_key="reader",
                states=tuple(("run", f"run{i}", "completed") for i in range(5)), limit=2)
    pages = [service.observe_state_changes(**args) for _ in range(4)]
    assert [len(items) for items in pages] == [2, 2, 1, 0]
    assert len({item.name for items in pages for item in items}) == 5


def test_stale_page_cursor_is_explicit_not_an_empty_success():
    with pytest.raises(RootToolError, match="cursor"):
        page([{"name": "one"}], key="name", before="removed")


def test_observation_and_collection_failures_are_not_hidden_by_summary(tmp_path, monkeypatch):
    from tests.operations.test_r4_execution_approval_identity import _setup, _create_effect, _decide_execution_approval
    runtime, _, effect, _, root, _ = _setup(tmp_path)
    _create_effect(root, name='broken_observation')
    _decide_execution_approval(runtime, root, name='broken_observation')
    root.call_tool('execution_start', {'name':'broken_observation'}, surface="execution")
    def broken(*a, **k):
        raise TimeoutError('fixture status read timed out')
    monkeypatch.setattr(effect, 'status_details', broken, raising=False)
    short = root.call_tool('execution_sync', {'name':'broken_observation'}, surface="execution")
    full = root.call_tool('execution_status', {'name':'broken_observation', 'view':'detail'}, surface="execution")
    assert short['observation_error']['causes'] == full['observation_error']['causes']
    assert 'timed out' in json.dumps(short['observation_error'])
    from scidiscovery.artifact_agent.interfaces.mcp_response_views import execution_summary
    for key in ('record_error', 'progress_error', 'stop_record_error', 'observation_error', 'stop_observation_error'):
        error = {'exception_type':'OSError', 'message':'specific collection failure', 'layer':key, 'diagnostic_ref':'scoped'}
        assert execution_summary({'collection':{key:error}})['collection'][key] == error
    assert 'progress' not in execution_summary({})
    assert execution_summary({'progress':None})['progress'] is None


def test_approval_url_and_capability_details_survive_compact_views():
    full = {'name':'decision','status':'pending','review_url':'http://localhost/review/exact', 'rationale':'理由'*1000}
    root = router(approval_status=lambda **args:full,
        execution_capabilities=lambda **args:dict(operation_id='effect', capabilities=[dict(profile='ssh', solver_kind='solver', public_arguments=['--exact'])]))
    short = root.call_tool('approval_status', {'name':'decision'})
    assert short['review_url'] == full['review_url'] and short['omitted_characters'] > 0
    assert root.call_tool('approval_status', {'name':'decision','view':'detail'}) == full
    assert 'public_arguments' not in root.call_tool('execution_capabilities', {'operation_id':'effect'}, surface="execution")['capabilities'][0]
    navigation = root.call_tool('execution_capabilities', {'operation_id': 'effect'}, surface='execution')['detail']
    assert navigation['tool'] == 'scid_call'
    request = navigation['arguments']
    assert request == {'name': 'execution_capabilities', 'surface': 'execution',
        'arguments': {'operation_id': 'effect', 'view': 'detail'}}
    assert root.call_tool(request['name'], request['arguments'], surface=request['surface'])['capabilities'][0]['public_arguments'] == ['--exact']


def test_status_projection_keeps_private_recovery_records_internal():
    original = {"name":"r", "state":"failed", "recovery":{"coverage":{"omitted":["private"]}}}
    before = deepcopy(original)
    result = run_intent_projection(original, intent="status")
    assert "recovery" not in result and original == before


def test_log_summary_indexes_metadata_and_navigates_to_explicit_cache_read():
    full = {'name':'execution', 'state':'failed', 'progress':{'log_tails':[
        {'source':'stdout', 'tail':'unique error A'},
        {'source':'solver_log', 'tail':'unique error A'},
        {'source':'stderr', 'tail':'unique error B'}]}}
    root = router(execution_status=lambda **kw:deepcopy(full),
        execution_logs=lambda **kw:{'text': full['progress']['log_tails'][kw['log_index']]['tail']})
    result = root.call_tool('execution_status', {'name':'execution'}, surface='execution')
    assert result['progress']['log_count'] == 3
    assert [log['log_index'] for log in result['progress']['log_activity']] == [0, 1]
    assert 'unique error' not in json.dumps(result)
    request = result['logs']['arguments']
    assert request == {'name':'execution_logs', 'surface':'execution', 'arguments':{'name':'execution'}}
    assert root.call_tool(request['name'], request['arguments'], surface=request['surface'])['text'] == 'unique error A'
    assert root.call_tool('execution_logs', {'name':'execution', 'log_index':2}, surface='execution')['text'] == 'unique error B'


@pytest.mark.parametrize('kind', ['agent','transform','effect','approval'])
def test_invoke_preserves_executor_dispatch_facts_and_exact_errors(kind):
    from scidiscovery.artifact_agent.interfaces.mcp_response_views import root_response
    result={'name':'n','state':'pending','agent_type':'compiled',
        'execution_profile':{'model':'gpt-5.6-sol','reasoning_effort':'medium'},'deadline_at':'exact-deadline',
        'outputs':{'result':'exact.output'}, 'review_url':'https://localhost/review/exact',
        'approval_name':'approval','execution_name':'execution','bound_inputs':['unneeded']*100}
    value={'executor_kind':kind,'operation_id':'non.tcad.fixture','result':result}
    short=root_response('operation_invoke',deepcopy(value),{})
    if kind=='agent':
        assert short['result']['execution_profile']==result['execution_profile']
        assert short['result']['deadline_at']=='exact-deadline'
        assert 'bound_inputs' not in short['result'] and short['result']['detail']['tool']=='run_status'
    else:
        assert short==value
    failure={**value,'result':{'state':'rejected','error':'exact error '*2000,'missing_inputs':['required'], 'normalized_request':{'needed':'unchanged'}}}
    assert root_response('operation_invoke',deepcopy(failure),{})==failure


def test_execution_outputs_preserve_exact_result_identity_across_pages():
    root=router(execution_outputs=lambda **kw:{'execution_name':'e','result_artifact_name':'e.result',
        'outputs':[{'output_label':str(i),'artifact_name':f'e.output.{i}'} for i in range(3)]})
    first=root.call_tool('execution_outputs',{'name':'e','limit':1}, surface="execution")
    second=root.call_tool('execution_outputs',{'name':'e','limit':1,'before':first['next_before']}, surface="execution")
    assert first['result_artifact_name']==second['result_artifact_name']=='e.result'
    absent=router(execution_outputs=lambda **kw:{'execution_name':'e','result_artifact_name':None,'outputs':[]})
    assert absent.call_tool('execution_outputs',{'name':'e'}, surface="execution")['result_artifact_name'] is None


def test_execution_status_default_does_not_scale_with_log_content():
    marker = 'solver-log-must-not-enter-context'
    sizes = []
    for length in (100, 100000):
        full = {'name':'execution', 'state':'running', 'progress':{'elapsed_seconds':30,
            'log_tails':[{'source':'solver_log', 'updated_at':'2026-09-27T10:00:30Z',
                'size_bytes':length, 'tail':marker + '日' * length} for _ in range(8)]}}
        root = router(execution_status=lambda **_:deepcopy(full))
        value = root.call_tool('execution_status', {'name':'execution'}, surface='execution')
        raw = json.dumps(value, ensure_ascii=False).encode()
        assert marker.encode() not in raw and '日'.encode() not in raw
        assert value['progress']['log_count'] == 8
        assert value['progress']['log_details_omitted'] is True
        sizes.append(len(raw))
        detail = root.call_tool('execution_status', {'name':'execution', 'view':'detail'}, surface='execution')
        assert marker not in json.dumps(detail) and 'log_tails' not in detail['progress']
    assert max(sizes) < 1500 and abs(sizes[1] - sizes[0]) < 40


def test_execution_inventory_detail_does_not_bypass_log_cache_reader():
    from scidiscovery.artifact_agent.interfaces.mcp_response_views import root_response
    value = {'executions':[{'name':'job', 'state':'running', 'progress':{
        'log_tails':[{'source':'solver_log', 'tail':'body must remain in cache'}]}}], 'next_before':None}
    result = root_response('execution_list', value, {'view':'detail'})
    assert 'body must remain' not in json.dumps(result)
    assert result['executions'][0]['progress']['log_count'] == 1


@pytest.mark.parametrize('tool,field,key', [('run_list','runs','name'), ('scientific_inventory','objects','artifact_name')])
@pytest.mark.parametrize('name_length', [5, 256])
def test_oversized_detail_is_explicit_and_does_not_block_following_objects(tool, field, key, name_length):
    from scidiscovery.agent_execution_settings import MCPReadSettings
    from scidiscovery.artifact_agent.interfaces.mcp_response_views import root_response, page
    settings = MCPReadSettings(detail_max_bytes=1024)
    rows = [{key:f'item{i}'.ljust(name_length, 'x'), 'reason':'x' * (20000 if i == 1 else 100)} for i in range(4)]
    cursor, seen, omissions = None, [], []
    for _ in range(6):
        selected, following = page(rows, key=key, before=cursor, limit=100) if tool == 'run_list' else (rows, None)
        response = root_response(tool, {field:selected, 'next_before':following},
            {'view':'detail', 'before':cursor, 'limit':100}, read_settings=settings)
        assert len(json.dumps(response, ensure_ascii=False, separators=(',', ':')).encode()) <= 1024
        for item in response[field]:
            seen.append(item[key])
            if 'entry_omitted' in item:
                omissions.append(item[key])
                assert item['read_request']['arguments']['name'] == item[key]
        cursor = response['next_before']
        if cursor is None:
            break
    assert seen == [item[key] for item in rows] and omissions == [rows[1][key]]


def test_byte_limited_run_page_keeps_goal_membership_on_delivered_page():
    from scidiscovery.agent_execution_settings import MCPReadSettings
    from scidiscovery.artifact_agent.interfaces.mcp_response_views import root_response, append_attention
    rows = [{'name':f'run_{i}', 'state':'failed', 'reason':'r'*250} for i in range(8)]
    members = [row['name'] for row in rows]
    response = root_response('run_list', {'runs':rows, 'next_before':None,
        'current_goal_tasks':members}, {'view':'detail'},
        read_settings=MCPReadSettings(detail_max_bytes=1024))
    assert 0 < len(response['runs']) < len(rows)
    assert response['current_goal_tasks'] == [row['name'] for row in response['runs']]
    notices = {'events':[{'name':'attention', 'state':'attention_required', 'note':'n'*250}],
        'more_available':False}
    reply, count = append_attention(response, notices, budget=1024, field='runs', key='name')
    assert count == 1
    assert reply['current_goal_tasks'] == [row['name'] for row in reply['runs']]
    assert reply['next_before'] == reply['runs'][-1]['name']
    # Continue at the actual returned page key, including the extra notice trim.
    seen = [row['name'] for row in reply['runs']]
    cursor = reply['next_before']
    for _ in range(8):
        remaining = rows[members.index(cursor)+1:]
        page = root_response('run_list', {'runs':remaining, 'next_before':None,
            'current_goal_tasks':[row['name'] for row in remaining]}, {'view':'detail'},
            read_settings=MCPReadSettings(detail_max_bytes=1024))
        assert page['current_goal_tasks'] == [row['name'] for row in page['runs']]
        seen.extend(row['name'] for row in page['runs'])
        cursor = page['next_before']
        if cursor is None:
            break
    else:
        pytest.fail('finite eight-member fixture did not finish within eight pages')
    assert seen == members
