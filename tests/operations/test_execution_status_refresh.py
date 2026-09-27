"""Explicit status queries refresh one existing job without submission or collection."""
import json

import pytest

from tests.operations.test_r4_execution_approval_identity import _setup, _create_effect, _decide_execution_approval


def test_root_status_refreshes_once_but_inventory_does_not_poll(tmp_path, monkeypatch):
    runtime, _, adapter, _, root, _ = _setup(tmp_path)
    _create_effect(root, name="observed")
    _decide_execution_approval(runtime, root, name="observed")
    root.call_tool("execution_start", {"name": "observed"}, surface="execution")
    calls = []
    def observe(_):
        calls.append(True)
        return {"state": "succeeded", "progress": {"elapsed_seconds": 42}}
    monkeypatch.setattr(adapter, "status_details", observe, raising=False)
    monkeypatch.setattr(root.facade.execution_bridge, "start", lambda **_: pytest.fail("status started a job"))
    before = runtime.scheduler_bindings.list(instance=root.facade._instance_id(), namespace="artifact")
    root.call_tool("execution_list", {}, surface="execution")
    assert calls == []
    value = root.call_tool("execution_status", {"name": "observed"}, surface="execution")
    assert value["state"] == "succeeded" and value["progress"]["elapsed_seconds"] == 42
    assert calls == [True]
    assert value["result_artifact_name"] is None
    assert runtime.scheduler_bindings.list(instance=root.facade._instance_id(), namespace="artifact") == before
    # Terminal execution is authoritative; no network dependency to reread it.
    assert root.call_tool("execution_status", {"name": "observed"}, surface="execution")["state"] == "succeeded"
    assert calls == [True]


def test_root_status_exposes_refresh_failure_and_keeps_last_observation(tmp_path, monkeypatch):
    runtime, _, adapter, _, root, _ = _setup(tmp_path)
    _create_effect(root, name="unreachable")
    _decide_execution_approval(runtime, root, name="unreachable")
    root.call_tool("execution_start", {"name": "unreachable"}, surface="execution")
    monkeypatch.setattr(adapter, "status_details", lambda _: {"state": "running"}, raising=False)
    old = root.call_tool("execution_sync", {"name": "unreachable"}, surface="execution")
    def unavailable(_):
        raise TimeoutError("fixture remote query timed out")
    monkeypatch.setattr(adapter, "status_details", unavailable)
    value = root.call_tool("execution_status", {"name": "unreachable"}, surface="execution")
    assert value["state"] == "running"
    assert value["status_observed_at"] == old["status_observed_at"]
    assert "timed out" in json.dumps(value["observation_error"])
