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
    assert 'science.evidence.extract.v1' in corrected
    assert 'science.evidence.audit.intake.v1' in corrected
