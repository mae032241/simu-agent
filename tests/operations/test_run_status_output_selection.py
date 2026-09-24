"""Root reading projections preserve exact results without repeating large payloads."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_root import RootToolError
from scidiscovery.artifact_agent.interfaces.mcp_root_run_routes import _output_selection
from scidiscovery.artifact_agent.schema.common import canonical_json
from tests.operations import test_l4_local_tcad as fixture


def gap_run(tmp_path):
    catalog, runtime, root, _ = fixture._system(tmp_path, solver_kind='sprocess')
    inputs = [dict(port='execution_capability', artifact_names=['execution_capability']),
              dict(port='experiment_plan', artifact_names=['experiment_plan'])]
    fixture._invoke(root, 'gap', 'tcad.deck.author.initial.v1', inputs)
    worker = fixture._debug_worker(catalog, runtime, fixture._ImmediateDebugAdapter(), tmp_path / 'debug')
    opened = worker.call_tool('worker_open_assignment', {})
    fixture._write_gap(opened)
    Path(opened['workspace_path'], 'deck/reports/failure.log').write_text('LARGE_LOG_MARKER\n' * 4096)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    return runtime, root, inputs


@pytest.mark.parametrize('historical', [False, True])
def test_omitted_status_and_diagnostic_pages_do_not_read_the_payload(tmp_path, monkeypatch, historical):
    runtime, root, _ = gap_run(tmp_path)
    full = root.call_tool('run_status', dict(name='gap', view='detail', include_full_output=True))
    if historical:
        def absent(_):
            raise KeyError('retired operation')
        monkeypatch.setattr(root.facade, '_operation_catalog', SimpleNamespace(operation=absent))
    with monkeypatch.context() as patch:
        def forbidden(*args, **kwargs):
            pytest.fail('status-only query read an Artifact payload')
        patch.setattr(runtime.artifacts, 'read', forbidden)
        for cursor in (None, 0):
            status = root.call_tool('run_status', dict(name='gap', view='detail', output_paths=[], diagnostic_after=cursor))
            assert status['sealed_output'] is status['selected_output'] is None
            assert status['output_delivery'] == 'omitted'
            assert status['sealed_output_status'] == ('historical' if historical else 'available')
            assert status['scheduler_signal_status'] == 'available'
            assert status['scheduler_signal'] is None
            assert status['bound_inputs'] == full['bound_inputs']
            assert status['output_metadata']['artifact_name'] == full['output_artifact_name']
            assert b'LARGE_LOG_MARKER' not in canonical_json(status)
    selected = root.call_tool('run_status', dict(name='gap', view='detail', output_paths=['/summary', '/missing_inputs']))
    assert selected['scheduler_signal_status'] == 'available'
    assert selected['sealed_output_status'] == status['sealed_output_status']
    assert selected['sealed_output'] is None
    for item in selected['selected_output']['items']:
        assert item['value'] == full['sealed_output']['payload'][item['pointer'][1:]]
    restored = root.call_tool('run_status', dict(name='gap', view='detail', output_paths=None, include_full_output=True))
    assert restored['sealed_output'] == full['sealed_output']


def test_large_unknown_result_can_be_navigated_without_guessing_fields(tmp_path):
    _, root, _ = gap_run(tmp_path)
    full = root.call_tool('run_status', dict(name='gap', view='detail', include_full_output=True))
    status = root.call_tool('run_status', dict(name='gap', output_paths=[]))
    navigation = root.call_tool('run_status', dict(name='gap', response_profile='navigation', output_mode='index'))
    item = navigation['output_index']
    assert item['status'] == 'available' and 'value' not in item
    pointers = {child['pointer'] for child in item['children']}
    assert {'/summary', '/affected_work', '/attempt_files'} <= pointers
    selected = root.call_tool('run_status', dict(name='gap', response_profile='decision', output_paths=['/summary', '/affected_work']))
    assert selected['selected_output']['items'][0]['value'] == full['sealed_output']['payload']['summary']
    replies = (status, navigation, selected)
    assert all(b'LARGE_LOG_MARKER' not in canonical_json(reply) for reply in replies)
    assert sum(len(canonical_json(reply)) for reply in replies) < len(canonical_json(full))


@pytest.mark.parametrize('state', ['queued', 'running', 'failed'])
def test_unsealed_runs_do_not_expose_drafts(tmp_path, state):
    catalog, runtime, root, _ = fixture._system(tmp_path, solver_kind='sprocess')
    inputs = [dict(port='execution_capability', artifact_names=['execution_capability']),
              dict(port='experiment_plan', artifact_names=['experiment_plan'])]
    fixture._invoke(root, 'pending', 'tcad.deck.author.initial.v1', inputs)
    if state != 'queued':
        worker = fixture._debug_worker(catalog, runtime, fixture._ImmediateDebugAdapter(), tmp_path / 'debug')
        opened = worker.call_tool('worker_open_assignment', {})
        fixture._write_gap(opened)
        if state == 'failed':
            value = runtime.runs.status(worker._run_id)
            runtime.runs.record_failure(value.run_id, reason='fixture interrupted', expected_state='running',
                expected_last_activity_at=value.last_activity_at)
    for paths in ([], ['/summary']):
        status = root.call_tool('run_status', dict(name='pending', view='detail', output_paths=paths))
        assert status['state'] == state
        assert status['sealed_output_status'] == 'unavailable'
        assert not status.get('sealed_output') and not status.get('selected_output') and not status.get('output_metadata')
    if state == 'failed':
        compact = root.call_tool('run_status', dict(name='pending', response_profile='poll', output_paths=[]))
        assert compact['state'] == 'failed' and 'diagnostic_events' not in compact
        assert 'diagnostic_summary' not in compact and compact['diagnostics_available']
        diagnostic_page = root.call_tool('run_status', dict(name='pending', view='detail', response_profile='compat',
            output_paths=[], diagnostic_after=0, diagnostic_limit=1))
        assert diagnostic_page['diagnostic_events']['events'][0]['activity'] == 'framework_failure'
        assert 'engineering' not in diagnostic_page['diagnostic_events']['events'][0]['diagnostic'] or isinstance(
            diagnostic_page['diagnostic_events']['events'][0]['diagnostic']['engineering'], dict)


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


@pytest.mark.parametrize('paths', [['/a~2b'], ['not/a/pointer'], ['/summary'] * 9])
def test_root_selector_limits_are_declared_query_errors(tmp_path, paths):
    _, root, _ = gap_run(tmp_path)
    with pytest.raises(RootToolError) as error:
        root.call_tool('run_status', dict(name='gap', output_paths=paths))
    assert error.value.details and all('output_paths' in item['path'] for item in error.value.details)
    assert root.call_tool('run_status', dict(name='gap', output_paths=[]))['state'] == 'completed'
