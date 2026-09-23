"""Reference navigation ships in wheels through the existing MCP boundary."""


def test_installed_reference_modules_and_mcp_contract(installed_probe):
    installed_probe("full", r'''
from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile

import scidiscovery.reference_tools as reference_tools
import scidiscovery.artifact_agent.service.reference_access as reference_access
from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.operations.tooling import (
    operation_tool_contracts, operation_local_worker_tool_names,
    operation_worker_tools,
)

for module in (reference_tools, reference_access):
    assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
catalog = compile_installed_catalog()
compiled = catalog.operation("science.result.diagnose.v1")
reference = next(tool for tool in operation_worker_tools(compiled)
                 if tool.name == "worker_reference_read")
assert reference.capability == "reference.read"
assert reference.reference_policy is not None
root_dir = Path(tempfile.mkdtemp(prefix="installed-reference-contract-"))
project = root_dir / "project"
project.mkdir()
runtime = open_runtime(project_root=project, state_root=root_dir / "state",
                       worker_backend="local")
assert runtime.operation_catalog.operation(compiled.spec.operation_id).digest == compiled.digest
worker = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id,
                              operation_digest=compiled.digest)
actual = {tool["name"]: {key: tool[key] for key in ("description", "inputSchema")}
          for tool in worker.list_tools()}
expected = operation_tool_contracts(compiled, operation_local_worker_tool_names(compiled))
assert actual == expected
policy = actual["worker_reference_read"]["inputSchema"]["x-scidiscovery-reference-policy"]
assert policy == json.loads(json.dumps(asdict(reference.reference_policy)))
assert policy["rules"] and policy["max_calls"] > 0
assert policy["max_unique_bytes"] > 0 and policy["max_response_bytes"] > 0
root = RootMCPRouter(RootToolFacade(
    runtime.artifacts, runtime.intake, runs=runtime.runs,
    approvals=runtime.approvals, executions=runtime.executions,
    bindings=runtime.scheduler_bindings, operation_catalog=catalog, instance=None,
))
gateway = UnifiedMCPRouter(root)
response = gateway.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
assert "error" not in response, response
assert {tool["name"] for tool in response["result"]["tools"]} == {
    "scid_catalog", "scid_describe", "scid_call",
}
assert len(response["result"]["tools"]) == 3
''')
