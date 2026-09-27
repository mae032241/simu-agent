import json
from types import SimpleNamespace

import pytest

from scidiscovery.artifact_agent.runtime_plugin_bindings import (
    LoadedRuntimePlugins, read_runtime_summary, runtime_process_summary, write_runtime_process_summary,
)
from scidiscovery.operation_contract import DiagnosticError, contract_diagnostic
from scidiscovery.plugin_runtime.diagnostics import exception_facts
from scidiscovery.plugin_runtime.transport import forward_request


def test_current_runtime_summary_is_readable_and_bounded(tmp_path):
    catalog = SimpleNamespace(digest=lambda: "a" * 64)
    plugins = LoadedRuntimePlugins({}, {}, (), ())
    path = tmp_path / "summary.json"
    write_runtime_process_summary(path, runtime_process_summary(catalog, plugins, mode="control"))
    result = read_runtime_summary(path, expected_mode="control")
    assert result["io_budget_defaults"]["query_seconds"] > 0
    # Existing summaries without IO defaults remain readable.
    del result["io_budget_defaults"]
    write_runtime_process_summary(path, json.dumps(result).encode())
    assert read_runtime_summary(path, expected_mode="control")["plugins"] == []
    result["io_budget_defaults"] = {"query_seconds": float("nan")}
    write_runtime_process_summary(path, json.dumps(result).encode())
    with pytest.raises(ValueError, match="IO budgets"):
        read_runtime_summary(path, expected_mode="control")


def test_configuration_repair_is_safe_and_distinct_from_scientific_rejection():
    error = DiagnosticError("token=secret /private/config.json", details=(contract_diagnostic(
        "tcad_transport_configuration_invalid", phase="tool_execution", affected_action="tool_call"),))
    error.failure_stage = "configuration"
    facts = exception_facts(error, layer="tool", action="execute")
    assert facts["recovery"]["stage"] == "configuration"
    assert facts["recovery"]["responsibility"] == "administrator"
    assert "secret" not in json.dumps(facts) and "/private" not in json.dumps(facts)
    rejection = ValueError("denied")
    rejection.failure_stage = "pre_execution_rejected"
    assert exception_facts(rejection, layer="execution", action="start")["recovery"]["stage"] == "pre_execution_rejected"


def test_failed_connection_is_known_unsent_but_send_timeout_is_not(monkeypatch):
    from scidiscovery.plugin_runtime import transport
    class Socket:
        phase = "connect"
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def settimeout(self, seconds): pass
        def connect(self, path):
            if self.phase == "connect": raise ConnectionRefusedError("refused")
        def sendall(self, raw): raise TimeoutError("partial send possible")
    socket = Socket()
    monkeypatch.setattr(transport.socket, "socket", lambda *args: socket)
    from pathlib import Path
    for phase in ("connect", "send"):
        socket.phase = phase
        with pytest.raises(OSError) as captured:
            forward_request(Path("/private/socket"), b'{"method":"tools/call"}', timeout=1)
        facts = exception_facts(captured.value, layer="transport", action="forward")
        if phase == "connect":
            assert facts["recovery"]["stage"] == "connection"
        else:
            assert "recovery" not in facts  # Generic transport cannot infer an execution outcome.


def test_health_reuses_capability_probe_and_never_mutates_execution(monkeypatch):
    from scidiscovery.artifact_agent.execution_bridge import AdapterCapability, ExecutionBridge
    calls = []
    def forbidden(*args, **kwargs): pytest.fail("health must not execute or recover work")
    capability = AdapterCapability("solver", "solver", "fixture.v1", 1,
                                   "application/json", b"{}", {})
    adapter = SimpleNamespace(lookup_submission=forbidden, submit=forbidden, collect=forbidden,
        cancel=forbidden, capabilities=lambda: calls.append("capabilities") or (capability,))
    bridge = ExecutionBridge(None, adapters={"fixture": adapter})
    clock = [100.]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])
    assert bridge.health(executor="missing")["recovery"]["stage"] == "configuration"
    first = bridge.health(executor="fixture", minimum_interval_seconds=2)
    assert first["state"] == "available" and first["execution_verified"] is False
    assert bridge.health(executor="fixture", minimum_interval_seconds=2)["cached"] is True
    assert len(calls) == 1
    clock[0] += 3
    bridge.health(executor="fixture", minimum_interval_seconds=2)
    assert len(calls) == 2


@pytest.mark.parametrize("operation", ["capabilities", "execution_policy"])
def test_readonly_command_probe_uses_one_configured_total_query_budget(tmp_path, monkeypatch, operation):
    import sys
    from tcad_artifact import command_adapter
    calls = []
    def run(argv, **kwargs):
        request = json.loads(kwargs["input"])
        calls.append((request["operation"], kwargs["timeout"]))
        return SimpleNamespace(returncode=0, stderr=b"", stdout=json.dumps({
            "schema_version": 1, "operation": operation, "ok": True, "payload": {}}).encode())
    monkeypatch.setattr(command_adapter, "run_bounded", run)
    adapter = command_adapter.CommandTCADExecutorAdapter(command_adapter.CommandAdapterConfig(
        executable=sys.executable, query_timeout_seconds=.25, operation_timeout_seconds=30),
        local_result_root=tmp_path)
    adapter._call(operation, {})
    assert len(calls) == 1 and calls[0][0] == operation
    assert 0 < calls[0][1] <= .25
