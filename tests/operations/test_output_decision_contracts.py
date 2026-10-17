"""Production output declarations and sealed decision reads stay aligned."""
import json
import pytest

from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL
from curve_score.plugin import PLUGIN as CURVE
from tcad_artifact.plugin import PLUGIN as TCAD
from curve_figure_evidence.plugin import PLUGIN as FIGURE
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.invoke import operation_primary_output
from scidiscovery.artifact_agent.schema.common import canonical_json


@pytest.fixture(scope='module')
def catalog():
    return compile_catalog((CORE_PLUGIN, GENERAL, CURVE, TCAD, FIGURE))


def _schema_path(root, path):
    current = root
    for token in path.lstrip('/').split('/'):
        while '$ref' in current:
            ref = current['$ref']
            assert ref.startswith('#/')
            current = root
            for part in ref[2:].split('/'):
                current = current[part]
        if 'anyOf' in current:
            current = next(part for part in current['anyOf'] if part.get('type') != 'null')
            while '$ref' in current:
                current = root['$defs'][current['$ref'].split('/')[-1]]
        token = token.replace('~1', '/').replace('~0', '~')
        assert token in current.get('properties', {}), path
        current = current['properties'][token]


def test_all_twelve_production_agent_decision_paths_exist_in_primary_schema(catalog):
    agents = [catalog.operation(key) for key in catalog.operation_ids()
              if catalog.operation(key).spec.executor.kind == 'agent']
    assert len(agents) == 12
    problems = []
    for operation in agents:
        schema = operation.output_contracts[operation_primary_output(operation).name]
        for path in operation.spec.decision_fields:
            try:
                _schema_path(schema, path)
            except AssertionError:
                problems.append((operation.spec.operation_id, path))
    assert not problems, problems


def _values(result):
    return {item['pointer']: item['value'] for item in result['selected_output']['items'] if item['status'] == 'selected'}
