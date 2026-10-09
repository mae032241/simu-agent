"""Default bulk-reading division preserves owner contracts and original access."""
import json
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.service.worker_start import startup_document
from tests.operations.test_r4_internal_helpers import _gateway, _result


def test_bulk_navigation_is_default_without_expanding_or_hiding_originals():
    original = dict(source_name='long_log', relative_path='inputs/log.txt', size_bytes=16384,
        media_type='text/plain', exposure='on_demand', usage='evidence_inventory')
    aliases = [original, dict(original, source_name='earlier_log', same_source_as='long_log', historical=True),
        dict(source_name='objective_source', relative_path='inputs/goal.txt', size_bytes=200,
            media_type='text/plain', exposure='on_demand', usage='evidence_inventory')]
    assignment = dict(instruction='Judge the original criterion, retaining failed attempts.',
        role_instructions='The owner must read its role contract and retain prohibitions.', inputs=aliases,
        tools=['worker_helper'], budget={'remaining_seconds':20},
        inline_inputs={'objective_source':'Do not fit on target observations.'})
    before = json.dumps(assignment, sort_keys=True)
    start = startup_document(assignment, on_demand=True)
    division = start['reading']['material_division']
    assert division['large_sources'] == ['long_log']
    assert division['helper_tool_available'] is True
    assert start['instruction'] == assignment['instruction']
    assert start['role_instructions'] == assignment['role_instructions']
    assert next(item for item in start['inputs'] if item['source_name']=='objective_source')['text'] == assignment['inline_inputs']['objective_source']
    assert next(item for item in start['inputs'] if item['source_name']=='long_log')['relative_path'] == original['relative_path']
    assert next(item for item in start['inputs'] if item['source_name']=='earlier_log')['historical'] is True
    assert json.dumps(assignment, sort_keys=True) == before
    assert 'not a tool admission gate' in division['instruction']


def test_missing_helper_still_delivers_owner_contract_and_direct_reading_route():
    start = startup_document(dict(instruction='Answer within the original constraints.',
        role_instructions='Read the decisive originals.', tools=[], inputs=[]))
    assert start['reading']['material_division']['helper_tool_available'] is False
    assert 'bounded original selections' in start['reading']['material_division']['instruction']
    assert 'unresolved gap' in start['reading']['material_division']['instruction']
    assert start['role_instructions'] == 'Read the decisive originals.'
    assert 'python tools/read_input.py SOURCE' in start['reading']['inputs']


@pytest.mark.parametrize('settings', [{'max_depth':0}, {'max_calls':0}])
def test_disabled_or_exhausted_helper_allows_original_reading_without_new_stage(tmp_path, monkeypatch, settings):
    runtime, _, run_id, call, opened = _gateway(tmp_path, monkeypatch, settings)
    source = json.loads(Path(opened['assignment_path']).read_bytes())['inputs'][0]
    assert 'error' in call('worker_helper', {'name':'read-materials', 'task':'Locate the failed observation.',
        'materials':[source['source_name']]})
    start = json.loads(Path(opened['start_here_path']).read_bytes())
    assert 'read only the bounded original selections' in start['reading']['material_division']['instruction']
    original = Path(opened['workspace_path'])/source['relative_path']
    assert original.is_file() and original.read_bytes()
    assert _result(call('worker_heartbeat'))['state'] == 'running'
    assert runtime.runs.status(run_id).state == 'running'
