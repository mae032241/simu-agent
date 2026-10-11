"""Native strict output schemas and immutable legacy packets; no model calls."""
import pytest

from scidiscovery.research_loop import contracts as c
from test_history_handoff import finish, scene, source


@pytest.mark.parametrize('role', ['H', 'W', 'A', 'E'])
def test_current_native_schema_requires_every_declared_property(role):
    schema = c.result_schema(role, c.HANDOFF_PROTOCOL)
    # Native strict response_format requires this equality, beyond JSON Schema validity.
    def strict(value):
        if not isinstance(value, dict):
            return
        if 'properties' in value:
            assert set(value['required']) == set(value['properties'])
            assert value['additionalProperties'] is False
        for nested in value.values():
            if isinstance(nested, dict):
                strict(nested)
            elif isinstance(nested, list):
                for item in nested:
                    strict(item)
    strict(schema)
    if role not in {'H', 'A'}:
        legacy = c.result_schema(role, 3)
        assert set(schema['properties']) == set(legacy['properties']) | {'implementation_selection'}


@pytest.mark.parametrize('recommendation', [None, 'run-33'])
def test_current_a_scientific_recommendation_can_be_null_or_candidate(tmp_path, recommendation):
    raw = tmp_path / 'science-output.json'
    payload = dict(summary='Independent finding', scientific_result='Bounded result', limitations=[],
                   next_action='wait', route_reason='More evidence needed', candidate_recommendation=recommendation,
                   search_review=None, progress_assessment=None, implementation_selection=None)
    c.write(raw, payload)
    assert c.science_payload(raw, 'A', c.HANDOFF_PROTOCOL) == payload
    payload.pop('candidate_recommendation')
    c.write(raw, payload)
    with pytest.raises(ValueError, match='Invalid scientific result fields'):
        c.science_payload(raw, 'A', c.HANDOFF_PROTOCOL)


@pytest.mark.parametrize('protocol', [1, 2, 3])
def test_legacy_a_schema_and_missing_recommendation_remain_valid(tmp_path, protocol):
    expected = dict(type='object', properties={
        'summary': dict(type='string', minLength=1),
        'scientific_result': dict(type='string', minLength=1),
        'limitations': dict(type='array', items=dict(type='string')),
        'next_action': dict(type='string', enum=list(c.ACTIONS['A'])),
        'route_reason': dict(type='string', minLength=1),
    }, required=['summary', 'scientific_result', 'limitations', 'next_action', 'route_reason'], additionalProperties=False)
    if protocol == 3:
        expected['properties']['candidate_recommendation'] = dict(type=['string', 'null'], maxLength=80,
            description='Optional scientific recommendation: one listed candidate ID, or null when unknown.')
    assert c.result_schema('A', protocol) == expected
    raw = tmp_path / 'science-output.json'
    payload = dict(summary='Legacy finding', scientific_result='Original science', limitations=[],
                   next_action='wait', route_reason='Bounded uncertainty')
    c.write(raw, payload)
    assert c.science_payload(raw, 'A', protocol) == payload


def test_legacy_protocol3_a_seal_and_schema_are_unchanged_on_rebuild(scene):
    source(scene)
    job = c.build_job(scene, 3, 'A', [2])
    job['handoff_protocol'] = 3
    work = c.workspace(scene, 3)
    record = c.host_record(work)
    c.write(scene / 'jobs/003.json', job)
    c.write(work / 'science-task.json', c.science_view(job))
    c.write(record / 'science-result.schema.json', c.result_schema('A', 3))
    finish(scene, 3, 'A', [2], action='revise_h')
    assert 'candidate_recommendation' not in c.read(record / 'science-output.json')
    paths = [scene / 'jobs/003.json', work / 'science-task.json', record / 'science-result.schema.json',
             record / 'science-output.json', record / 'result-identity.json']
    original = {path: path.read_bytes() for path in paths}
    c.validate(work)
    assert c.build_job(scene, 3, 'A', [2]) == job
    assert c.build_job(scene, 4, 'H', [3])['handoff_protocol'] == c.HANDOFF_PROTOCOL
    assert all(path.read_bytes() == contents for path, contents in original.items())


def test_current_a_seals_without_any_scientific_recommendation(scene):
    source(scene)
    _, work, record = finish(scene, 3, 'A', [2], action='wait')
    assert c.read(record / 'science-output.json')['candidate_recommendation'] is None
    assert c.validate(work)['next_action'] == 'wait'


def test_legacy_protocol4_a_seal_has_no_search_field_on_rebuild(scene):
    source(scene)
    job = c.build_job(scene, 3, 'A', [2])
    job['handoff_protocol'] = 4
    work = c.workspace(scene, 3);record = c.host_record(work)
    c.write(scene / 'jobs/003.json', job)
    c.write(work / 'science-task.json', c.science_view(job))
    c.write(record / 'science-result.schema.json', c.result_schema('A', 4))
    finish(scene, 3, 'A', [2], action='revise_h')
    assert 'search_review' not in c.read(record / 'science-output.json')
    paths = [scene / 'jobs/003.json', work / 'science-task.json', record / 'science-result.schema.json',
             record / 'science-output.json', record / 'result-identity.json']
    original = {path: path.read_bytes() for path in paths}
    assert c.build_job(scene, 3, 'A', [2]) == job
    c.validate(work)
    assert all(path.read_bytes() == data for path, data in original.items())
