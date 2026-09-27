"""Bounded navigation keeps exact originals accessible without implicit expansion."""
import json
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_root import RootToolError
from scidiscovery.artifact_agent.interfaces.mcp_root_run_routes import _output_index, _output_selection
from scidiscovery.artifact_agent.schema.common import canonical_json


def envelope(payload):
    return dict(artifact_name="report", kind="scientific", schema="fixture", payload=payload)


def test_index_pages_exact_escaped_paths_without_values():
    payload = {f"层/{i}~": {"private": "x" * 400} for i in range(55)}
    full = envelope(payload)
    offset, pointers = 0, []
    while True:
        page = _output_index(full, "", offset, 16)
        assert len(canonical_json(page)) <= 8192
        assert page["total_children"] == 55
        assert "private" not in json.dumps(page)
        pointers += [item["pointer"] for item in page["children"]]
        if page["next_offset"] is None:
            break
        assert page["next_offset"] > offset
        offset = page["next_offset"]
    assert len(pointers) == len(set(pointers)) == 55
    for pointer, expected in zip(pointers, payload.values()):
        assert _output_selection(full, [pointer])["items"][0]["value"] == expected


def test_index_null_missing_scalar_empty_and_array():
    full = envelope({"null": None, "empty": {}, "array": [False, 1, "秘密"], "": []})
    for pointer, kind in [("/null", "null"), ("/empty", "object"), ("/array/0", "boolean"),
                          ("/array/1", "number"), ("/array/2", "string"), ("/", "array")]:
        item = _output_index(full, pointer, 0, 16)
        assert item["type"] == kind and item["children"] == []
        assert item["next_offset"] is None and "value" not in item
    assert _output_index(full, "/absent", 0, 16)["status"] == "missing"
    assert _output_index(full, "/array/01", 0, 16)["status"] == "missing"
    assert [i["pointer"] for i in _output_index(full, "/array", 1, 1)["children"]] == ["/array/1"]
    assert _output_index(full, "/array", 3, 1)["next_offset"] is None
    with pytest.raises(RootToolError, match="index_offset"):
        _output_index(full, "/array", 4, 1)


def test_index_budget_includes_metadata_and_long_multibyte_paths():
    parent = "父" * 350
    full = envelope({parent: {"键" * 400 + str(i): 1 for i in range(8)}})
    offset, count = 0, 0
    while True:
        page = _output_index(full, "/" + parent, offset, 32)
        assert len(canonical_json(page)) <= 8192
        count += len(page["children"])
        if page["next_offset"] is None:
            break
        assert page["next_offset"] > offset
        offset = page["next_offset"]
    assert count == 8
    with pytest.raises(RootToolError, match="entry at offset 0"):
        _output_index(envelope({"键" * 3000: 1}), "", 0, 16)
    with pytest.raises(RootToolError, match="metadata exceeds"):
        _output_index(envelope({}), "/" + "长" * 3000, 0, 16)


def test_combined_status_and_values_waits_for_sealing(tmp_path):
    from tests.operations.test_l2_run_invariants import _system, _invoke, _worker, _envelope
    from tests.operations.test_unified_mcp import call, result
    from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
    catalog, runtime, _, _, root = _system(tmp_path)
    _invoke(root, 'observation')
    gateway = UnifiedMCPRouter(root, worker_backend='local')
    request = {'name': 'observation', 'intent': 'decision', 'output_paths': ['/limitations']}
    queued = result(call(gateway, 'run_status', request))
    assert queued['state'] == 'queued' and not queued.get('selected_output') and not queued.get('scheduler_signal')
    assert "operation_version" not in queued and "operation_digest" not in queued
    poll = result(call(gateway, 'run_status', {
        'name': 'observation', 'intent': 'status'}))
    assert poll['state'] == 'queued' and 'bound_inputs' not in poll and 'scheduler_signal' not in poll
    worker = _worker(catalog, runtime)
    opened = worker.call_tool('worker_open_assignment', {})
    Path(opened['output_directory'], 'result.json').write_bytes(_envelope())
    running = result(call(gateway, 'run_status', request))
    assert running['state'] == 'running' and not running.get('selected_output') and not running.get('scheduler_signal')
    assert running['sealed_output_status'] == 'unavailable'
    worker.call_tool('worker_submit_result', {})
    completed = result(call(gateway, 'run_status', request))
    assert completed['state'] == 'completed' and completed['scheduler_signal']
    assert completed['selected_output']['items'][0]['value'] == ['Two rows do not establish causality.']
    navigation = result(call(gateway, 'run_status', {
        'name': 'observation', 'intent': 'navigation'}))
    assert navigation['output_index']['pointer'] == '' and 'scheduler_signal' not in navigation
    poll = result(call(gateway, 'run_status', {'name': 'observation', 'intent': 'status'}))
    assert 'scheduler_signal' not in poll
    assert 'operation_version' not in poll and 'operation_digest' not in poll


def test_gateway_index_does_not_read_summary_or_leak_full_output(tmp_path):
    from tests.operations.test_l2_run_invariants import _system, _invoke, _worker, _envelope
    from tests.operations.test_unified_mcp import call, result
    from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
    catalog, runtime, _, _, root = _system(tmp_path)
    _invoke(root, "observation")
    worker = _worker(catalog, runtime)
    opened = worker.call_tool("worker_open_assignment", {})
    Path(opened["output_directory"], "result.json").write_bytes(_envelope())
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    gateway = UnifiedMCPRouter(root, worker_backend="local")
    page = result(call(gateway, "run_status", {"name":"observation", "intent":"navigation"}))
    assert not page.get("sealed_output") and not page.get("selected_output")
    assert page["output_index"]["pointer"] == ""
    assert "/limitations" in [i["pointer"] for i in page["output_index"]["children"]]
    exact = result(call(gateway, "run_status", {"name":"observation", "output_paths":["/limitations"]}))
    assert exact["selected_output"]["items"][0]["value"] == ["Two rows do not establish causality."]
    for paths in ([], ["/limitations", "/structure"]):
        error = call(gateway, "run_status", {"name":"observation", "intent":"navigation", "output_paths":paths})
        assert "navigation accepts one output path" in error["error"]["message"]
    full = result(call(gateway, "run_status", {"name":"observation", "intent":"full"}))
    assert full["sealed_output"]["payload"]["limitations"] == ["Two rows do not establish causality."]


def test_parent_gateway_paging_keeps_limit_and_no_payload_read(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from tests.operations.test_l2_run_invariants import _system
    from tests.operations.test_unified_mcp import call, result
    from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
    _, runtime, _, source, root = _system(tmp_path)
    gateway = UnifiedMCPRouter(root, worker_backend="local")
    monkeypatch.setattr(runtime.artifacts, "read", lambda *_: pytest.fail("parent query read payload"))
    page = result(call(gateway, "artifact_catalog", {"name": "source_csv", "view": "parents"}))
    assert page["parents"] == [] and page["next_offset"] is None and page["parent_count"] == 0
    monkeypatch.setattr(runtime.artifacts, "get_by_id", lambda _: SimpleNamespace(parent_refs=[source.ref]*4097))
    failed = call(gateway, "artifact_catalog", {"name": "source_csv", "view": "parents"})
    assert "direct parent limit exceeded (4096)" in json.dumps(failed)
