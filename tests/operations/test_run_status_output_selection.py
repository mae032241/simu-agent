"""Root reading projections preserve exact results without repeating large payloads."""


from scidiscovery.artifact_agent.interfaces.mcp_root_run_routes import _output_selection
from scidiscovery.artifact_agent.schema.common import canonical_json


def test_pointer_values_and_navigation_remain_exact_and_bounded():
    payload = {'a/b': {'~key': [None, {'summary': 'exact'}]}, '': True,
               'large': '文' * 12000, 'x' * 10000: 'oversized key',
               **{str(i): i for i in range(40)}}
    output = dict(artifact_name='fixture.output', kind='fixture', schema='fixture.v1', payload=payload)
    result = _output_selection(output, ['/a~1b/~0key/0', '/a~1b/~0key/1/summary', '/',
        '/a~1b/~0key/01', '/missing', '/large', ''])
    items = result['items']
    assert items[0]['status'] == 'selected' and items[0]['value'] is None
    assert items[1]['value'] == 'exact' and items[2]['value'] is True
    assert items[3]['status'] == items[4]['status'] == 'missing'
    assert items[5]['status'] == 'omitted' and items[5]['size_bytes'] == len(canonical_json(payload['large']))
    assert len(items[6]['children']) == 32
    assert items[6]['omitted_children'] == len(payload) - 32
    assert len(canonical_json(items[6]['children'])) <= 8192
    assert all('x' * 10000 not in child['pointer'] for child in items[6]['children'])
    assert sum(item.get('size_bytes', 0) for item in items if item['status'] == 'selected') <= 32768


def test_compact_fields_balance_exact_science_and_delivery_coverage():
    from scidiscovery.artifact_agent.service.input_reader import compact_scientific_fields
    from scidiscovery.artifact_agent.service.scientific_progress import delivery_coverage
    payload = dict(assessments=[dict(identity='negative', outcome='contradicts',
        reason='Evidence conflicts with the proposed mechanism.', evidence=list(range(3000))) for _ in range(30)],
        conclusion='Original criterion failed.', limitations=['No independent control.'],
        remaining_question='Does the mechanism survive a control?', next_action='Measure the control.')
    projection = compact_scientific_fields(payload, ['/assessments', '/conclusion', '/limitations', '/remaining_question', '/next_action'])
    assert len(canonical_json(projection)) < 8192
    items=projection['items']
    assert items[0]['status']=='projected' and items[0]['omitted_children'] > 0
    def selected(items):
        return {item['pointer']: item['value'] for item in items if item['status']=='selected'}
    assert selected(items)['/conclusion']==payload['conclusion']
    assert selected(items)['/next_action']==payload['next_action']
    nested=items[0]['items'][0]['items']
    assert selected(nested)['/assessments/0/outcome']=='contradicts'
    coverage=delivery_coverage(dict(output_delivery='compact', selected_output=projection))
    assert coverage['coverage']=='compact' and coverage['original_read']=='not_confirmed'
    assert coverage['fields'][0]['status']=='projected'
    assert coverage['fields'][0]['omitted_children']==items[0]['omitted_children']
    assert 'value' not in str(coverage)
