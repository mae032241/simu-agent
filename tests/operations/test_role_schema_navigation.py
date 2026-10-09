"""Role navigation must resolve to the authoritative assignment output schema."""
import json
import copy
import pytest

from scidiscovery.artifact_agent.service.run_assignment import assignment_json
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.invoke import BoundOperationCall
from scidiscovery.operations.tooling import operation_role_instructions
from tests.operations.test_agent_contract_alignment import CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN
from curve_figure_evidence.plugin import PLUGIN as FIGURE_PLUGIN
from scidiscovery.artifact_agent.service.output_schema_reader import read_schema, SchemaReader
from tests.artifact_agent.test_output_schema_reader import schema as payload_form


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


def navigation_form():
    """Same envelope selectors used by the captured H/W authoring forms."""
    form = payload_form()
    form['required'].append('handoff')
    form['x-validation'] = {'rules': ['Submission-wide constraints must remain visible.']}
    form['properties'].update({
        'handoff': {'$ref': '#/$defs/RoleHandoff'},
        'boundary_declarations': {'type': 'array', 'items': {'$ref': '#/$defs/BoundaryDeclaration'}},
        'capture_sources': {'$ref': '#/$defs/CaptureSources'}})
    form['$defs'] = {
        'RoleHandoff': {'type': 'object', 'required': ['summary'], 'additionalProperties': False,
            'properties': {'summary': {'type': 'string'}, 'source': {'$ref': '#/$defs/Source'}}},
        'BoundaryDeclaration': {'type': 'object', 'required': ['statement'],
            'properties': {'statement': {'type': 'string'}, 'source': {'$ref': '#/$defs/Source'}}},
        'CaptureSources': {'type': 'object', 'additionalProperties': {'$ref': '#/$defs/Source'}},
        'Source': {'type': 'string', 'minLength': 1}}
    return form


@pytest.mark.parametrize('name,definition',[
    ('handoff','/$defs/RoleHandoff'),
    ('boundary_declarations','/$defs/BoundaryDeclaration'),
    ('capture_sources','/$defs/CaptureSources'),
    ('evidence','/properties/payload/$defs/Evidence')])
def test_form_envelope_and_payload_selectors_preserve_complete_reference_closure(name,definition):
    original = navigation_form()
    explicit = '/payload/evidence' if name == 'evidence' else '/' + name
    short = read_schema(original, [name], definitions_only=True)
    exact = read_schema(original, [explicit], definitions_only=True)
    assert short == exact and short['format'] == 'reading_sections'
    assert list(exact['fields']) == [explicit]
    assert exact['definitions'][definition] == (original['properties']['payload']['$defs']['Evidence']
        if name == 'evidence' else original['$defs'][definition.rsplit('/',1)[1]])
    source = '/properties/payload/$defs/Source' if name == 'evidence' else '/$defs/Source'
    assert source in exact['definitions']  # Includes references in optional child fields.
    assert '/properties/payload/$defs/Large' not in exact['definitions']


def test_form_overview_keeps_global_constraints_and_envelope_supplements_do_not_repeat_definitions():
    original = navigation_form(); before = copy.deepcopy(original)
    reader = SchemaReader(original); overview = reader.read()
    for key in ('required','additionalProperties','x-validation'):
        assert overview['overview'][key] == original[key]
    assert overview['overview']['properties']['payload']['x-validation'] == original['properties']['payload']['x-validation']
    assert overview['definitions']['/$defs/RoleHandoff'] == original['$defs']['RoleHandoff']
    assert '/$defs/Source' in overview['definitions']
    supplements = reader.read(['boundary_declarations','/boundary_declarations','capture_sources'])
    assert set(supplements['definitions']) == {'/$defs/BoundaryDeclaration','/$defs/CaptureSources'}
    assert reader.read(['/boundary_declarations','/capture_sources'])['definitions'] == {}
    assert original == before


def test_form_same_name_requires_explicit_envelope_or_payload_path_and_typos_do_not_offer_full():
    original = navigation_form()
    original['properties']['payload']['properties']['handoff'] = {'$ref': '#/$defs/Evidence'}
    with pytest.raises(ValueError) as ambiguous:
        read_schema(original, ['handoff'])
    assert 'Ambiguous field' in str(ambiguous.value)
    assert '/handoff' in str(ambiguous.value) and '/payload/handoff' in str(ambiguous.value)
    envelope = read_schema(original, ['/handoff'], definitions_only=True)
    payload = read_schema(original, ['/payload/handoff'], definitions_only=True)
    assert set(envelope['definitions']) == {'/$defs/RoleHandoff','/$defs/Source'}
    assert set(payload['definitions']) == {'/properties/payload/$defs/Evidence','/properties/payload/$defs/Source'}
    for name in ('typo','/payload/typo','payload.handoff'):
        with pytest.raises(ValueError) as unknown:
            read_schema(original, [name])
        assert '/handoff' in str(unknown.value) and '/payload/handoff' in str(unknown.value)
        assert '--full' not in str(unknown.value)


def test_form_json_pointer_escapes_field_names_without_dotted_syntax():
    original = navigation_form()
    original['properties']['payload']['properties']['evidence/source~label'] = {'$ref': '#/$defs/Evidence'}
    view = read_schema(original, ['/payload/evidence~1source~0label'], definitions_only=True)
    assert set(view['definitions']) == {'/properties/payload/$defs/Evidence','/properties/payload/$defs/Source'}
