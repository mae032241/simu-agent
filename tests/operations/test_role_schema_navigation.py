"""Role navigation must resolve to the authoritative assignment output schema."""
import json

from scidiscovery.artifact_agent.service.run_assignment import assignment_json
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.invoke import BoundOperationCall
from scidiscovery.operations.tooling import operation_role_instructions
from tests.operations.test_agent_contract_alignment import CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN
from curve_figure_evidence.plugin import PLUGIN as FIGURE_PLUGIN


def test_all_compiled_roles_use_assignment_schema_navigation():
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN, FIGURE_PLUGIN))
    corrected = []
    for name in catalog.operation_ids():
        compiled = catalog.operation(name)
        if compiled.spec.executor.kind != 'agent':
            continue
        role = operation_role_instructions(compiled)
        assert 'output.schema.json' not in role, name
        if 'the schema identified by assignment.output.schema_path' not in role:
            continue
        # This tests assignment generation only, not admission of empty inputs.
        bound = BoundOperationCall(compiled=compiled, name='navigation', inputs=(), instruction=None)
        assignment = json.loads(assignment_json(bound, (), tool_names=()))
        assert assignment['role_instructions'] == role
        assert assignment['output']['schema_path'] == 'schema/result.schema.json'
        corrected.append(name)
    # Design composes EXPERIMENT_PROMPT too, beyond its direct revise consumer.
    assert 'science.experiment.design.v1' in corrected
    assert len(corrected) == 16, "\n".join(corrected)


def test_installed_non_analysis_role_schema_path_and_full_reader(installed_probe):
    installed_probe('all_domains', r'''
import json, tempfile, subprocess, sys
from pathlib import Path
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.operations.invoke import BoundOperationCall
from scidiscovery.artifact_agent.service.run_assignment import assignment_json, result_schema_json
from scidiscovery.artifact_agent.service.local_workspace import LocalTrustedBackend
catalog = compile_installed_catalog()
compiled = catalog.operation('science.hypothesis.propose.v1')
# Isolated materialization, no scientific task admission or model execution.
bound = BoundOperationCall(compiled=compiled, name='navigation', inputs=(), instruction=None)
assignment = assignment_json(bound, (), tool_names=())
schema = result_schema_json(compiled)
backend = LocalTrustedBackend(Path(tempfile.mkdtemp()))
workspace = backend.prepare(run_id='run_schemanavigation', inputs=(), assignment=assignment, result_schema=schema)
opened = json.loads(workspace.assignment_path.read_bytes())
role = opened['role_instructions']
assert 'assignment.output.schema_path' in role and 'output.schema.json' not in role
original = workspace.root / opened['output']['schema_path']
assert original.read_bytes() == schema
assert not (workspace.root/'output.schema.json').exists()
read = json.loads(subprocess.check_output([sys.executable, '-I',
    str(workspace.root/'tools/read_output_schema.py'), '--full'], timeout=10))
assert read['schema'] == json.loads(original.read_bytes())
# An older workspace without the helper still has the authoritative original.
(workspace.root/'tools/read_output_schema.py').unlink()
assert json.loads(original.read_bytes()) == read['schema']
''')
