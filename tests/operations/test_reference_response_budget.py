"""Measured, explicit limit-only recovery on exact authorized reference reads."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scidiscovery.artifact_agent.schema.common import ContractDiagnostic, canonical_json
from scidiscovery.operation_contract import DiagnosticError
from scidiscovery.reference_tools import ReferenceReadRequest, ReferenceRule, reference_handler
from tests.operations.test_reference_access import Harness, prepared


def budget_failure(response, requested=512):
    assert response['state'] == 'rejected'
    assert response['code'] == 'reference_response_limit'
    assert len(canonical_json(response)) <= requested
    budget = response['response_budget']
    assert budget['requested_limit'] == requested
    assert requested < budget['minimum_limit'] <= budget['suggested_limit'] <= budget['maximum_limit']
    assert budget['retry'] == {'limit': budget['suggested_limit']}
    return budget


def test_file_metadata_low_budget_has_exact_one_retry_and_preserves_costs(tmp_path):
    harness = Harness(tmp_path)
    target, _, handle = prepared(harness, b'x,y\n1,2\n', 'text/csv')
    request = ReferenceReadRequest(source='root_0', action='read', reference=handle, delivery='file', limit=512)
    before = harness.usage('reader')
    failed = harness.reference_read('reader', request, harness.policy)
    budget = budget_failure(failed)
    assert not harness.reference_access_records('reader')
    assert not (tmp_path/'reader/workspace/.reference-access').exists()
    after_failure = harness.usage('reader')
    assert after_failure['calls'] == before['calls'] + 1
    assert after_failure['response_bytes'] == before['response_bytes'] + len(canonical_json(failed))
    assert after_failure['io_bytes'] > before['io_bytes']

    corrected = request.model_copy(update=budget['retry'])
    assert corrected.model_dump(exclude={'limit'}) == request.model_dump(exclude={'limit'})
    response = harness.reference_read('reader', corrected, harness.policy)
    assert response['provided']['kind'] == 'file_access'
    assert budget['minimum_limit'] == len(canonical_json(response))
    assert len(canonical_json(response)) <= corrected.limit
    assert Path(response['file_path']).read_bytes() == harness.contents[target]
    assert len(harness.reference_access_records('reader')) == 1
    assert harness.usage('reader')['io_bytes'] > after_failure['io_bytes']
    replay = harness.reference_read('reader', corrected, harness.policy)
    assert replay == response
    assert len(harness.reference_access_records('reader')) == 1


def test_public_handler_transports_measured_retry_without_echoing_identity(tmp_path):
    harness = Harness(tmp_path)
    _, _, handle = prepared(harness)
    request = ReferenceReadRequest(source='root_0', action='read', reference=handle, delivery='file', limit=512)
    context = SimpleNamespace(read_reference=lambda value: harness.reference_read('reader', value, harness.policy))
    with pytest.raises(DiagnosticError) as caught:
        reference_handler(request, context)
    assert caught.value.details[0]['code'] == 'reference_response_limit'
    detail = caught.value.details[1]
    assert detail['code'] == 'reference_response_budget' and detail['path'] == '$.limit'
    assert len(detail['message']) <= 512
    assert str(tmp_path) not in detail['message'] and handle not in detail['message']
    for value in caught.value.details:
        ContractDiagnostic.model_validate(value)
    corrected = request.model_copy(update=json.loads(detail['message'])['retry'])
    assert reference_handler(corrected, context)['provided']['kind'] == 'file_access'


def long_source(harness):
    name = 's' * 256
    harness.inputs['reader'] = (SimpleNamespace(source_name=name, port_name='reference_material',
        artifact_ref=harness.inputs['reader'][0].artifact_ref),)
    return name


def test_directory_minimum_includes_final_cursor_and_omission(tmp_path):
    harness = Harness(tmp_path)
    targets = {name: harness.artifact(name.encode()) for name in ('first', 'second')}
    root = harness.report('producer', targets)
    harness.run('reader', [root])
    source = long_source(harness)
    request = ReferenceReadRequest(source=source, action='list', cursor=1, limit=512)
    failed = harness.reference_read('reader', request, harness.policy)
    budget = budget_failure(failed)
    # The final single entry has next_cursor=None, not an intermediate cursor.
    exact = request.model_copy(update={'limit': budget['minimum_limit']})
    response = harness.reference_read('reader', exact, harness.policy)
    assert len(response['references']) == 1
    assert response['references'][0]['alias'] == 'second'
    assert response['next_cursor'] is None and response['omitted'] == 0
    assert len(canonical_json(response)) == budget['minimum_limit']
    assert not harness.reference_access_records('reader')


def boundary_harness(tmp_path):
    harness = Harness(tmp_path)
    _, root, _ = prepared(harness)
    source = long_source(harness)
    signal = SimpleNamespace(boundary_references=(), boundary_declarations=tuple({
        'effect': 'preserve', 'verification': 'unverified',
        'declaration': {'boundary_key': f'b{index}', 'statement': '汉字' * 500,
            'interpretation': 'Preserve the original constraint.', 'evidence': []},
    } for index in range(2)))
    original = harness.completed_for_output
    producer = SimpleNamespace(output_ref=root, state='completed', instance_id='one',
        output_binding_name='sealed_' + 'p' * 240, signal=signal)
    harness.completed_for_output = lambda ref: producer if ref == root else original(ref)
    return harness, source


def test_boundary_directory_minimum_and_exact_selected_fragment_progress(tmp_path):
    harness, source = boundary_harness(tmp_path)
    listed_request = ReferenceReadRequest(source=source, view='boundaries', action='list', cursor=1, limit=512)
    budget = budget_failure(harness.reference_read('reader', listed_request, harness.policy))
    listed = harness.reference_read('reader', listed_request.model_copy(update=budget['retry']), harness.policy)
    assert len(listed['references']) == 1 and listed['next_cursor'] is None and listed['omitted'] == 0
    assert len(canonical_json(listed)) == budget['minimum_limit']
    handle = listed['references'][0]['reference']
    request = ReferenceReadRequest(source=source, view='boundaries', action='read', reference=handle,
        pointer='/declaration/statement', offset=7, limit=512)
    failed = harness.reference_read('reader', request, harness.policy)
    budget = budget_failure(failed)
    one = request.model_copy(update={'limit': budget['minimum_limit']})
    response = harness.reference_read('reader', one, harness.policy)
    assert response['provided'] == {'pointer': request.pointer, 'offset': 7, 'characters': 1}
    assert response['next_offset'] == 8 and response['omitted'] is True
    assert len(canonical_json(response)) == budget['minimum_limit']
    following = harness.reference_read('reader', one.model_copy(update={'offset': 8}), harness.policy)
    assert following['provided']['offset'] == response['next_offset']
    assert not harness.reference_access_records('reader')


def test_over_max_directory_has_no_in_contract_retry(tmp_path):
    harness = Harness(tmp_path)
    target = harness.artifact(b'original')
    root = harness.report('producer', {'original': target}, document={
        'groups': {'x' * 9000: {'references': ['original']}}})
    harness.policy = replace(harness.policy, rules=(ReferenceRule(root.schema_id,
        '/groups/*/references/*', selected_only=True),))
    harness.run('reader', [root])
    response = harness.call('reader', limit=512)
    assert response['code'] == 'reference_response_limit'
    assert len(canonical_json(response)) <= 512
    assert response['response_budget']['minimum_limit'] > 8192
    assert response['response_budget']['suggested_limit'] is None
    assert response['response_budget']['retry'] is None
    assert not harness.reference_access_records('reader')


@pytest.mark.parametrize('selection', ['unknown_source', 'unknown_handle', 'invalid_pointer', 'cumulative_budget'])
def test_unavailable_or_invalid_selection_has_no_budget_hint(tmp_path, selection):
    harness = Harness(tmp_path)
    _, _, handle = prepared(harness)
    values = {'source': 'root_0', 'action': 'read', 'reference': handle, 'limit': 512}
    if selection == 'unknown_source':
        values['source'] = 'unbound'
    elif selection == 'unknown_handle':
        values['reference'] = 'ref_not_authorized'
    elif selection == 'invalid_pointer':
        values['pointer'] = '/not_present'
    else:
        harness.policy = replace(harness.policy, max_calls=1)
    response = harness.reference_read('reader', ReferenceReadRequest(**values), harness.policy)
    assert response['state'] == 'rejected'
    assert response['code'] != 'reference_response_limit'
    assert 'response_budget' not in response
    assert not harness.reference_access_records('reader')
