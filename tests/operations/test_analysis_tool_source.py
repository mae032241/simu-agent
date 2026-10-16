"""Source stdio diagnostics; copied readers and model-free services need no install."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.process_e2e
@pytest.mark.parametrize("entry", ["local_worker", "proxy"])
def test_source_stdio_errors_share_protocol_diagnostics(source_catalog, tmp_path, entry):
    source_catalog("blind_csv")
    from scidiscovery.operations.catalog import compile_installed_catalog

    repository = Path(__file__).resolve().parents[2]
    # The child needs only core and the one declared fixture plugin. Its metadata
    # is a source stand-in, and supplies no packaging evidence.
    paths = [str(repository / "src"), str(repository / "tests/fixtures/plugins/blind_csv_operation_plugin")]
    bootstrap = "import sys; sys.path[:0] = " + repr(paths) + r'''
from importlib.metadata import EntryPoint, EntryPoints
from scidiscovery.operations import catalog
catalog.entry_points = lambda: EntryPoints((
    EntryPoint(name="builtin", value="scidiscovery.builtin_plugin:CORE_PLUGIN", group="scidiscovery.plugins"),
    EntryPoint(name="general_science", value="scidiscovery.general_science_plugin:PLUGIN", group="scidiscovery.plugins"),
    EntryPoint(name="blind_csv", value="blind_csv_plugin.plugin:PLUGIN", group="scidiscovery.plugins"),
))
import runpy
'''
    module = "scidiscovery.artifact_agent.interfaces.mcp_" + entry
    command = [sys.executable, "-I", "-c", bootstrap + f"runpy.run_module({module!r}, run_name='__main__')"]
    if entry == "proxy":
        command += ["--socket", str(tmp_path / "unavailable.sock")]
    else:
        operation = compile_installed_catalog().operation("blind.csv.observe.v1")
        command += ["--state-root", str(tmp_path), "--operation-id", operation.spec.operation_id,
                    "--operation-digest", operation.digest, "--local-workspace-root", str(tmp_path / "workspaces")]
    valid = json.dumps(dict(jsonrpc="2.0", id=3, method="tools/list"))
    process = subprocess.run(command, input='["SECRET_PROTOCOL_VALUE"]\n{\n' + valid + '\n',
                             cwd=tmp_path, text=True, capture_output=True, timeout=30)
    assert process.returncode == 0, process.stderr
    responses = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(responses) == 3 and "SECRET_PROTOCOL_VALUE" not in process.stdout
    for response in responses[:2]:
        diagnostic = response["error"]["data"]["diagnostics"][0]
        assert diagnostic["phase"] == "protocol" and diagnostic["code"] == "invalid_protocol_request"
    if entry == "proxy":
        assert responses[-1]["error"]["data"]["diagnostics"][0]["code"] == "runtime_failure"
    else:
        assert responses[-1]["result"]["tools"]
