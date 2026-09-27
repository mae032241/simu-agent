import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scidiscovery.artifact_agent.service.local_workspace import LocalTrustedBackend
from scidiscovery.artifact_agent.service.output_schema_reader import read_schema


def schema():
    return {'$id': 'envelope', 'type': 'object', 'required': ['payload'],
        'additionalProperties': False, 'properties': {'payload': {
            '$id': 'report', 'type': 'object', 'required': ['summary'],
            'additionalProperties': False,
            'properties': {'summary': {'type': 'string', 'minLength': 1},
                'evidence': {'type': 'array', 'items': {'$ref': '#/$defs/Evidence'}},
                'optional': {'$ref': '#/$defs/Large'},
                'literal': {'const': {'$ref': 'not-a-schema-ref', '$defs': {'data': True}}}},
            'x-validation': {'rules': ['Do not invent results.']},
            '$defs': {'Evidence': {'type': 'object', 'required': ['source'],
                'properties': {'source': {'$ref': '#/$defs/Source'}}},
                'Source': {'type': 'string', 'minLength': 1},
                'Large': {'type': 'object', 'description': 'Optional details. ' * 1000}}}}}


def test_optional_closure_and_lossless_overview_preserve_shared_rules():
    original = schema()
    view = read_schema(original, ['evidence'])
    assert view['format'] == 'reading_sections'
    assert set(view['definitions']) == {
        '/properties/payload/$defs/Evidence', '/properties/payload/$defs/Source'}
    assert view['unexpanded_definitions'] == ['/properties/payload/$defs/Large']
    # Reinsert every omitted subtree by its original pointer to recover the exact schema.
    restored = copy.deepcopy(view['overview'])
    restored['properties']['payload']['$defs'] = original['properties']['payload']['$defs']
    assert restored == original
    details = read_schema(original, ['evidence'], definitions_only=True)
    assert 'overview' not in details and details['requires']
    assert details['definitions'] == view['definitions']
    assert read_schema(original, full=True)['schema'] == original


def test_required_and_conditional_refs_cycles_and_nested_resource_scope():
    original = schema()
    payload = original['properties']['payload']
    payload['required'].append('evidence')
    payload['$defs']['Source'] = {'anyOf': [{'type':'string'}, {'$ref':'#/$defs/Evidence'}]}
    original['$defs'] = {'Source': {'const': 'wrong outer scope'}}
    # A conditional property is significant even without its own required keyword.
    payload['if'] = {'properties': {'summary': {'$ref': '#/$defs/Source'}}}
    view = read_schema(original)
    assert view['format'] == 'reading_sections'
    assert view['definitions']['/properties/payload/$defs/Source'] == payload['$defs']['Source']
    assert '/$defs/Source' not in view['definitions']
    assert view['overview']['properties']['payload']['if'] == payload['if']


@pytest.mark.parametrize('ref', ['https://example.invalid/unknown', '#/$defs/Absent', '#anchor'])
def test_unsupported_refs_fall_back_to_full_schema(ref):
    original = schema()
    original['properties']['payload']['properties']['evidence']['items']['$ref'] = ref
    answer = read_schema(original, ['evidence'])
    assert answer['format'] == 'full' and answer['schema'] == original and answer['fallback']


def test_unknown_fields_and_small_or_unsupported_schemas():
    with pytest.raises(ValueError, match='Unknown payload field'):
        read_schema(schema(), ['typo'])
    for original in (True, {'type':'string'}, {'type':'object','properties':{'payload':True}},
                     {'type':'object','properties':{'payload':{'type':'object'}}}):
        assert read_schema(original)['format'] == 'full'


def test_materialized_reader_is_standalone_and_reads_refreshed_original(tmp_path):
    original = schema()
    workspace = LocalTrustedBackend(tmp_path/'backend').prepare(run_id='run_schema', inputs=(),
        assignment=b'{}', result_schema=json.dumps(original).encode())
    path = workspace.root/'schema/result.schema.json'
    script = workspace.root/'tools/read_output_schema.py'
    before = path.read_bytes()
    def read(*args):
        return json.loads(subprocess.check_output([sys.executable, '-I', str(script), *args], cwd=tmp_path, timeout=10))
    first = read('--field', 'evidence')
    assert first['format'] == 'reading_sections'
    assert path.read_bytes() == before and not script.stat().st_mode & 0o222
    assert read('--full')['schema'] == original
    # A control-owned schema refresh must invalidate the disposable reading cache.
    path.chmod(0o600)
    original['properties']['payload']['properties']['summary']['minLength'] = 3
    path.write_text(json.dumps(original))
    fresh = read()
    assert 'sha256' not in fresh and 'sha256' not in first
    assert fresh['format'] == 'reading_sections'
    assert fresh['overview']['properties']['payload']['properties']['summary']['minLength'] == 3


def test_automatic_schema_supplements_reconstruct_closure_and_reset():
    from scidiscovery.artifact_agent.service.output_schema_reader import SchemaReader
    original=schema(); reader=SchemaReader(original)
    first=reader.read();assert 'overview' in first and 'sha256' not in first
    detail=reader.read(['evidence']);assert detail['format']=='supplement' and 'overview' not in detail
    expected=read_schema(original,['evidence'])
    assert {**first['definitions'],**detail['definitions']}==expected['definitions']
    assert reader.read(['evidence'])['definitions']=={}
    assert reader.read()['definitions']=={}
    assert reader.read(full=True)['schema']==original
    assert reader.read(['evidence'])['format']=='retained'
    assert SchemaReader(original, {'broken':True}).read()['overview']==first['overview']
    changed=copy.deepcopy(original);changed['properties']['payload']['required'].append('evidence')
    fresh=SchemaReader(changed,reader.receipt).read()
    assert 'overview' in fresh and fresh['definitions']==expected['definitions']


def test_workspace_schema_cache_recovery_and_independent_field_calls(tmp_path):
    from scidiscovery.artifact_agent.service.output_schema_reader import workspace_view
    from concurrent.futures import ThreadPoolExecutor
    (tmp_path/'schema').mkdir();original=schema()
    (tmp_path/'schema/result.schema.json').write_text(json.dumps(original))
    first=workspace_view(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies=list(pool.map(lambda _:workspace_view(tmp_path,['evidence']),range(2)))
    definitions=[p for reply in replies for p in reply['definitions']]
    assert len(definitions)==len(set(definitions))==2
    assert not any('overview' in reply for reply in replies)
    assert workspace_view(tmp_path,full=True)['schema']==original
    receipt=tmp_path/'.read-input/schema.json';receipt.write_text('broken')
    assert workspace_view(tmp_path)['overview']==first['overview']
    receipt.unlink();receipt.symlink_to('/etc/passwd')
    assert 'overview' in workspace_view(tmp_path,['evidence'])  # cache failure never blocks reading
    with pytest.raises(ValueError,match='Unknown payload field'):
        workspace_view(tmp_path,['does_not_exist'])


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_output_schema_reader_rejects_nonfinite_json(value):
    original = schema()
    original["properties"]["payload"]["properties"]["optional"]["default"] = value
    with pytest.raises(ValueError, match="Out of range float"):
        read_schema(original, full=True)


def test_finite_unicode_reading_identity_preserves_existing_bytes():
    import hashlib
    expected = '{"default":1.5,"title":"温度"}'.encode("utf-8")
    result = read_schema({"default": 1.5, "title": "温度"})
    assert result["sha256"] == hashlib.sha256(expected).hexdigest()
