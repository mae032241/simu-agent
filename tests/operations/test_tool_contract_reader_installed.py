"""Generated reader scripts execute without access to the installed package."""


def test_installed_workspace_readers_are_standalone(installed_probe):
    installed_probe("all_domains", r'''
import json, tempfile, subprocess, sys
from pathlib import Path
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.operations.tooling import operation_tool_contracts, operation_worker_tool_names
from scidiscovery.artifact_agent.service.local_workspace import LocalTrustedBackend
from scidiscovery.artifact_agent.service.run_assignment import result_schema_json
from scidiscovery.artifact_agent.service.worker_start import write_worker_start
compiled = compile_installed_catalog().operation("tcad.result.analyze.v1")
contracts = operation_tool_contracts(compiled, operation_worker_tool_names(compiled))
schema = result_schema_json(compiled)
workspace = LocalTrustedBackend(Path(tempfile.mkdtemp())).prepare(
    run_id="run_readers", inputs=(), assignment=json.dumps({"tool_contracts": contracts}).encode(),
    result_schema=schema,
)
start = write_worker_start(workspace, {"instruction": "Analyze exact results.",
    "role_instructions": "Keep limitations.", "inputs": [], "tools": list(contracts), "tool_contracts": contracts})
assert json.loads(start.read_bytes())["instruction"] == "Analyze exact results."
assert "tool_contracts" not in json.loads(start.read_bytes())
def read(script, *args):
    return json.loads(subprocess.check_output([
        sys.executable, "-I", str(workspace.root / "tools" / script), *args,
    ], timeout=10))
name = "worker_tcad_curve_score"
assert read("read_tool_contract.py", name, "--full")["contract"] == contracts[name]
form = read("read_output_schema.py", "--full")["schema"]
assert form == json.loads(schema)
assert "schema_version" not in form["properties"]
assert not {"summary", "verdict"} & form["$defs"]["RoleHandoff"]["properties"].keys()
assert "operation_digest" not in form["properties"]["payload"]["x-scidiscovery-validation-contract"]
''')
