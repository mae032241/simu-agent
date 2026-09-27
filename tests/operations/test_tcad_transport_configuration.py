"""Local configuration admission and diagnostics through the actual command boundary."""

import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest

from scidiscovery.operation_contract import DiagnosticError
from tcad_artifact.command_adapter import (
    CommandAdapterConfig, CommandTCADExecutorAdapter, validate_command_configuration,
)
from tcad_artifact.ssh_transport import (
    SSHTCADTransportConfig, SSHTransportConfigurationError, read_transport_config,
)


def transport_config(tmp_path, **changes):
    path = tmp_path / "transport.json"
    path.write_text(json.dumps(dict(ssh_executable="/must/not/run/ssh",
        destination="user@private-host", remote_helper="/private/runner",
        remote_config="/private/config", remote_exchange_root="/private/exchange",
        identity_file="/private/key", max_transfer_bytes=2_000_000_000, **changes)))
    path.chmod(0o600)
    return path


def command_config(path):
    return CommandAdapterConfig(executable=sys.executable,
        arguments=("-m", "tcad_artifact.ssh_transport", "--config", str(path)),
        environment={"PYTHONPATH": os.pathsep.join(sys.path)})


def test_optional_chunk_default_and_explicit_override(tmp_path):
    assert read_transport_config(transport_config(tmp_path)).transfer_chunk_bytes == 1024 * 1024
    assert read_transport_config(transport_config(tmp_path, transfer_chunk_bytes=65536)).transfer_chunk_bytes == 65536
    # The compatibility default never invents transfer authority.
    data = json.loads(transport_config(tmp_path).read_text())
    del data["max_transfer_bytes"]
    with pytest.raises(ValueError):
        SSHTCADTransportConfig.model_validate_json(json.dumps(data), strict=True)


@pytest.mark.parametrize("value", [0, -1, "65536", True])
def test_invalid_explicit_chunk_is_rejected(tmp_path, value):
    with pytest.raises(SSHTransportConfigurationError):
        read_transport_config(transport_config(tmp_path, transfer_chunk_bytes=value))


@pytest.mark.parametrize("problem", ["invalid", "missing", "writable", "symlink"])
def test_command_failure_preserves_safe_repair_across_process_boundary(tmp_path, problem):
    path = transport_config(tmp_path, transfer_chunk_bytes=0 if problem == "invalid" else 65536)
    if problem == "missing":
        path.unlink()
    elif problem == "writable":
        path.chmod(0o666)
    elif problem == "symlink":
        target = path.with_suffix(".target")
        path.rename(target)
        path.symlink_to(target)
    adapter = CommandTCADExecutorAdapter(command_config(path), local_result_root=tmp_path / "results")
    with pytest.raises(DiagnosticError) as caught:
        adapter.capabilities()
    public = str(caught.value) + json.dumps(caught.value.details)
    assert caught.value.details[0]["code"] == "tcad_transport_configuration_invalid"
    assert caught.value.details[0]["repairable"] is False
    assert "administrator" in public and "before remote contact" in public
    for private in (str(tmp_path), "private-host", "/private/key", "identity_file"):
        assert private not in public
    # Full engineering facts stay available to the control plane.
    assert caught.value.engineering


@pytest.mark.parametrize("valid", [False, True])
@pytest.mark.parametrize("launcher", ["module", "script", "equals"])
def test_installer_checks_nested_configuration_before_writing(tmp_path, valid, launcher):
    path = transport_config(tmp_path, transfer_chunk_bytes=65536 if valid else 0)
    adapter = command_config(path)
    if launcher != "module":
        adapter = CommandAdapterConfig(executable="/not/executed/scidiscovery-tcad-transport",
            arguments=(f"--config={path}",) if launcher == "equals" else ("--config", str(path)))
    command_path = tmp_path / "command.json"
    command_path.write_text(adapter.model_dump_json())
    plugin = tmp_path / "plugin.json"
    plugin.write_text('{"previous":true}')
    script = Path(__file__).resolve().parents[2] / "plugins/tcad_artifact/deploy/configure_runtime.py"
    spec = importlib.util.spec_from_file_location("configure_tcad_test", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    arguments = dict(policy=tmp_path / "unused-policy", plugin_config=plugin,
        state_root=tmp_path, socket_path=tmp_path / "unused.sock", command_config=command_path)
    if valid:
        module.configure(**arguments)
        assert json.loads(plugin.read_text())["transport"] == "command"
    else:
        with pytest.raises(SSHTransportConfigurationError):
            module.configure(**arguments)
        assert json.loads(plugin.read_text()) == {"previous": True}


def test_generic_command_executor_has_no_assumed_ssh_configuration():
    validate_command_configuration(CommandAdapterConfig(executable="/external/executor"))


@pytest.mark.parametrize("arguments", [(), ("--config",), ("--config", "relative.json"),
    ("--config", "/one", "--config", "/two")])
def test_bundled_command_requires_unambiguous_absolute_config(arguments):
    with pytest.raises(ValueError):
        validate_command_configuration(CommandAdapterConfig(
            executable="/usr/local/bin/scidiscovery-tcad-transport", arguments=arguments))


def test_preparation_bridge_preserves_configuration_failure(tmp_path):
    from types import SimpleNamespace
    from scidiscovery.artifact_agent.execution_bridge import ExecutionBridge
    adapter = CommandTCADExecutorAdapter(command_config(transport_config(tmp_path, transfer_chunk_bytes=0)),
        local_result_root=tmp_path / "results")
    boundary = SimpleNamespace(lookup_submission=lambda _: None,
        validate_preparation_payload=lambda *args, **kwargs: adapter.capabilities())
    bridge = ExecutionBridge(None, adapters={"fixture": boundary})
    with pytest.raises(DiagnosticError) as caught:
        bridge.validate_request(executor="fixture", preparation_profile="fixture", payload=b"{}")
    assert caught.value.details[0]["code"] == "tcad_transport_configuration_invalid"


def test_worker_retains_configuration_repair_without_private_values(tmp_path):
    from tcad_artifact.output_recovery import OutputInspectionService
    from tests.operations.test_analysis_evidence_recovery import recovery_system
    system, worker, _, _ = recovery_system(tmp_path)
    adapter = CommandTCADExecutorAdapter(command_config(transport_config(tmp_path, transfer_chunk_bytes=0)),
        local_result_root=tmp_path / "results")
    class BrokenAdapter:
        def inspect_outputs(self, *args, **kwargs):
            return adapter.capabilities()
    worker.tool_services["tcad_artifact:tcad.output_inspection"] = OutputInspectionService(BrokenAdapter())
    with pytest.raises(DiagnosticError) as caught:
        worker.call_tool("worker_tcad_inspect_outputs", {"relative_path": "A_actual.plx"})
    public = str(caught.value) + json.dumps(caught.value.details) + json.dumps(caught.value.public_engineering)
    assert "tcad_transport_configuration_invalid" in public and "administrator" in public
    assert "/private" not in public and str(tmp_path) not in public
    assert "identity_file" not in public and "private-host" not in public
    assert system[1].runs.status(worker._run_id).state == "running"
