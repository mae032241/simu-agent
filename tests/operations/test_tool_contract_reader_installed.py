def test_installed_analysis_contract_automatic_delta_roundtrip_and_full_refresh(installed_probe):
    installed_probe("all_domains", r'''
import copy, json, tempfile, subprocess, sys
from pathlib import Path
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.operations.tooling import operation_tool_contracts, operation_worker_tool_names
from scidiscovery.artifact_agent.service.local_workspace import LocalTrustedBackend
from scidiscovery.artifact_agent.service.tool_contract_reader import digest
catalog = compile_installed_catalog()
root = Path(tempfile.mkdtemp())
backend = LocalTrustedBackend(root)
for i, (operation, score, diagnose) in enumerate([
    ("tcad.result.analyze.v1", "worker_tcad_curve_score", "worker_tcad_curve_diagnose"),
    ("science.result.diagnose.v1", "worker_curve_score", "worker_curve_diagnose")]):
    compiled = catalog.operation(operation)
    contracts = operation_tool_contracts(compiled, operation_worker_tool_names(compiled))
    workspace = backend.prepare(run_id="run_reader"+str(i), inputs=(),
        assignment=json.dumps({"tool_contracts":contracts}).encode(), result_schema=b"{}")
    script = workspace.root / "tools/read_tool_contract.py"
    def read(*args):
        return json.loads(subprocess.check_output([sys.executable, "-I", str(script), *args], timeout=10))
    first = read(score)
    assert first["format"] == "full" and first["contract"] == contracts[score]
    second = read(diagnose)
    assert second["format"] == "json_patch"
    restored = copy.deepcopy(first["contract"])
    for entry in second["patch"]:
        keys = [k.replace("~1", "/").replace("~0", "~") for k in entry["path"][1:].split("/")]
        parent = restored
        for key in keys[:-1]: parent = parent[key]
        if entry["op"] == "remove": del parent[keys[-1]]
        else: parent[keys[-1]] = entry["value"]
    # Exact equality covers references, required fields, limits and descriptions.
    assert restored == contracts[diagnose]
    assert digest(restored) == second["sha256"]
    assert read(diagnose, "--full")["contract"] == contracts[diagnose]
    assert json.loads(workspace.assignment_path.read_bytes())["tool_contracts"] == contracts
''')


def test_installed_output_schema_sections_are_exact_and_standalone(installed_probe):
    installed_probe('all_domains', r'''
import json, tempfile, subprocess, sys
from pathlib import Path
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.artifact_agent.service.local_workspace import LocalTrustedBackend
from scidiscovery.artifact_agent.service.run_assignment import result_schema_json
from scidiscovery.artifact_agent.service.output_schema_reader import read_schema
catalog = compile_installed_catalog()
root = Path(tempfile.mkdtemp())
backend = LocalTrustedBackend(root)
for i, name in enumerate(('tcad.result.analyze.v1', 'science.result.diagnose.v1')):
    raw = result_schema_json(catalog.operation(name))
    original = json.loads(raw)
    workspace = backend.prepare(run_id='run_schema'+str(i), inputs=(), assignment=b'{}', result_schema=raw)
    script = workspace.root/'tools/read_output_schema.py'
    def read(*args):
        return json.loads(subprocess.check_output([sys.executable, '-I', str(script), *args], timeout=10))
    view = read('--field', 'evidence')
    assert view['format'] == 'reading_sections', view.get('fallback')
    assert view == read_schema(original, ['evidence'])
    assert view['overview']['properties']['payload']['required'] == original['properties']['payload']['required']
    for path, value in view['definitions'].items():
        exact = original
        for key in path.split('/')[1:]:
            exact = exact[key.replace('~1','/').replace('~0','~')]
        assert exact == value
    assert read('--full')['schema'] == original
    assert (workspace.root/'schema/result.schema.json').read_bytes() == raw
''')
