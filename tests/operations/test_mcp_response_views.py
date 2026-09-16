from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolError
from scidiscovery.artifact_agent.interfaces.mcp_response_views import page


def router(**methods):
    facade = SimpleNamespace(runs=SimpleNamespace(), session_key=None,
        engineering_diagnostics=SimpleNamespace(capture=Mock()), _instance_id=lambda: "fixture", **methods)
    return RootMCPRouter(facade)


def test_execution_poll_is_short_but_exact_logs_and_failure_remain_readable():
    full = {"name": "execution", "state": "failed", "solver_state": "failed",
        "progress": {"elapsed_seconds": 19, "exit_code": 1,
            "log_tails": [{"source": source, "tail": "specific solver error\n"*100}
                          for source in ("stdout", "solver_log")]},
        "collection": {"state": "failed", "error": {"code": "collection_timeout", "diagnostic_ref": "diag_saved"}}}
    root = router(execution_status=lambda **args: deepcopy(full), execution_sync=lambda **args: deepcopy(full))
    for name in ("execution_status", "execution_sync"):
        short = root.call_tool(name, {"name": "execution"})
        assert "log_tails" not in short["progress"]
        assert short["collection"]["error"] == full["collection"]["error"]
        assert short["progress"]["exit_code"] == 1
        assert len(json.dumps(short)) < .4*len(json.dumps(full))
        assert root.call_tool(name, {"name": "execution", "view": "detail"}) == full


def test_run_default_never_requests_full_output_and_keeps_explicit_pointer_semantics():
    def status(**args):
        return {"name": args["name"], "state": "completed", "bound_inputs": [{"port": "input", "artifact_names": [None]}],
            "scheduler_signal": {"verdict": "blocked"},
            "selected_output": {"items": [{"pointer": "/summary", "status": "selected", "value": "结论"*1000}]},
            "received": args}
    call = Mock(side_effect=status)
    root = router(run_status=call)
    short = root.call_tool("run_status", {"name": "run"})
    assert call.call_args.kwargs["output_paths"] == ["/summary"]
    assert "bound_inputs" not in short and "sealed_output" not in short
    assert short["selected_output"]["items"][0]["status"] == "excerpt"
    assert short["scheduler_signal"]["verdict"] == "blocked"
    root.call_tool("run_status", {"name": "run", "output_paths": []})
    assert call.call_args.kwargs["output_paths"] == []
    detail = root.call_tool("run_status", {"name": "run", "view": "detail", "output_paths": []})
    assert detail["bound_inputs"][0]["artifact_names"] == [None]
    assert "view" not in call.call_args.kwargs
    selected = root.call_tool("run_status", {"name": "run", "output_paths": ["/summary"]})
    assert selected["selected_output"]["items"][0]["status"] == "selected"


def test_catalog_selects_full_exact_contract_and_paginates_without_hiding_tools():
    operations = [{"operation_id": f"operation{i}", "purpose": "test", "executor_kind": "agent",
                   "inputs": [{"name": "evidence"}], "timeout_seconds": 900} for i in range(5)]
    root = router(operation_catalog=lambda **args: {"scope": args["scope"], "operations": operations})
    first = root.call_tool("operation_catalog", {"limit": 2})
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
    assert error["data"]["diagnostics"][0]["path"] == "$.view"


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
    root.call_tool('execution_start', {'name':'broken_observation'})
    def broken(*a, **k):
        raise TimeoutError('fixture status read timed out')
    monkeypatch.setattr(effect, 'status_details', broken, raising=False)
    short = root.call_tool('execution_sync', {'name':'broken_observation'})
    full = root.call_tool('execution_status', {'name':'broken_observation', 'view':'detail'})
    assert short['observation_error'] == full['observation_error']
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
    assert 'public_arguments' not in root.call_tool('execution_capabilities', {'operation_id':'effect'})['capabilities'][0]
    assert root.call_tool('execution_capabilities', {'operation_id':'effect', 'view':'detail'})['capabilities'][0]['public_arguments'] == ['--exact']


def test_tool_audit_covers_exact_published_names():
    from scidiscovery.artifact_agent.interfaces.mcp_root import ROOT_TOOLS
    from tests.operations.test_agent_contract_alignment import CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN
    from curve_figure_evidence.plugin import PLUGIN as FIGURE_PLUGIN
    from scidiscovery.operations.catalog import compile_catalog
    from scidiscovery.operations.tooling import operation_worker_tool_names
    from pathlib import Path
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN, FIGURE_PLUGIN))
    audit = json.loads((Path(__file__).parents[2]/'docs/plans/evidence/mcp-response-levels/tool-inventory.json').read_bytes())
    assert {item['name'] for item in audit['root']} == {item.name for item in ROOT_TOOLS}
    actual = {name for key in catalog.operation_ids() if catalog.operation(key).spec.executor.kind == 'agent'
        for name in operation_worker_tool_names(catalog.operation(key))}
    assert {item['name'] for item in audit['worker'] + audit['lifecycle']} == actual
    assert all(item.get('decision') and item.get('detail_access') for group in audit.values() for item in group)
