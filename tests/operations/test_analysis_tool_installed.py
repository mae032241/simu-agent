"""Analysis contracts and controlled result submission from installed wheels."""
from __future__ import annotations

import json
import pytest


def test_installed_catalog_identity_matches_source(installed_probe):
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN as GENERAL
    from curve_score.plugin import PLUGIN as CURVE
    from tcad_artifact.plugin import PLUGIN as TCAD
    from curve_figure_evidence.plugin import PLUGIN as FIGURE
    from scidiscovery.operations.catalog import compile_catalog
    from scidiscovery.operations.tooling import operation_agent_type
    output = installed_probe("all_domains", r'''
import json
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.operations.tooling import operation_agent_type
catalog = compile_installed_catalog()
print(json.dumps({key: dict(digest=catalog.operation(key).digest,
    agent_type=operation_agent_type(catalog.operation(key)) if catalog.operation(key).spec.executor.kind == "agent" else None)
    for key in catalog.operation_ids()}, sort_keys=True))
''')
    catalog = compile_catalog((CORE_PLUGIN, GENERAL, CURVE, TCAD, FIGURE))
    expected = {key:dict(digest=catalog.operation(key).digest,
        agent_type=operation_agent_type(catalog.operation(key)) if catalog.operation(key).spec.executor.kind == "agent" else None)
        for key in catalog.operation_ids()}
    assert json.loads(output) == expected


@pytest.mark.parametrize("entry", ["local_worker", "hardened_worker", "proxy"])
def test_installed_stdio_errors_share_protocol_diagnostics(installed_probe, entry):
    installed_probe("blind_csv", "entry = " + repr(entry) + r'''
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from scidiscovery.operations.catalog import compile_installed_catalog
root = Path(tempfile.mkdtemp(prefix="installed-protocol-"))
command = [sys.executable, "-m", "scidiscovery.artifact_agent.interfaces.mcp_" + entry]
if entry == "proxy":
    command += ["--socket", str(root / "unavailable.sock")]
else:
    operation = compile_installed_catalog().operation("blind.csv.observe.v1")
    command += ["--state-root", str(root), "--operation-id", operation.spec.operation_id,
                "--operation-digest", operation.digest]
    if entry == "local_worker":
        command += ["--local-workspace-root", str(root / "workspaces")]
valid = json.dumps(dict(jsonrpc="2.0", id=3, method="tools/list"))
process = subprocess.run(command, input='["SECRET_PROTOCOL_VALUE"]\n{\n' + valid + '\n',
    text=True, capture_output=True, timeout=30)
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
''')
