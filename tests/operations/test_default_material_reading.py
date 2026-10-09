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


def test_shared_startup_policy_is_short_and_preserves_default_delegation():
    from scidiscovery.helper_tool import HELPER_TOOL
    for role in ('H', 'W', 'A'):
        start = startup_document(dict(instruction=role, inputs=[], tools=['worker_helper']), on_demand=True)
        policy = start['reading']['material_division']['instruction']
        assert len(policy.encode()) < 850
        assert 'Use native file reading/search' in start['reading']['inputs']
        assert 'For JSON, optional' in start['reading']['inputs']
        assert 'fresh context' in policy and 'Independent analysis uses its own helper' in policy
        assert 'entire material again by default' in policy
        assert 'Expand verification' in policy
        assert 'claims you will adopt' in policy
        assert 'not every helper citation' in policy
        assert 'unread background remains unread' in policy
        assert 'inspected scope' not in policy  # Detailed report contract is owned by the tool.
    assert 'inspected scope' not in HELPER_TOOL.description
    assert 'reads its own assignment and reporting rules' in HELPER_TOOL.description
    assert len(HELPER_TOOL.description.encode()) < 1100


def test_static_guide_page_survives_memory_refresh(tmp_path):
    from scidiscovery.artifact_agent.schema.common import canonical_json
    from scidiscovery.artifact_agent.service.local_workspace import LocalTrustedBackend
    from scidiscovery.artifact_agent.service.worker_start import write_worker_start
    from scidiscovery.artifact_agent.service.input_reader import read
    from tests.artifact_agent.test_input_reader import body, replay_arguments, next_arguments
    assignment = dict(inputs=[], tools=[], attempt_memory={'coverage':'unknown_not_empty'})
    workspace = LocalTrustedBackend(tmp_path/'backend').prepare(run_id='run_guiderefresh',
        inputs=(), assignment=canonical_json(assignment), result_schema=b'{}')
    write_worker_start(workspace, assignment)
    guide = workspace.root/'worker-guides.json'
    frozen = guide.read_bytes()
    first = read(workspace.root, 'worker-guides.json', file=True, pointers=['/guides/reader'], budget=512)
    assignment['attempt_memory'] = {'coverage':'known', 'recent':[{'name':'new-result'}]}
    write_worker_start(workspace, assignment)
    assert guide.read_bytes() == frozen
    assert json.loads((workspace.root/'worker-context.json').read_bytes())['attempt_memory'] == assignment['attempt_memory']
    handle = replay_arguments(first)[1]
    second = read(workspace.root, selection_id=handle, offset=int(next_arguments(first)[3]), budget=512)
    assert body(second)
    # Actual guide changes still invalidate a cursor; this is not a relaxed hash check.
    guide.chmod(0o600)
    guide.write_bytes(frozen.replace(b'JSON:', b'JSON objects:'))
    with pytest.raises(ValueError, match='changed'):
        read(workspace.root, selection_id=handle, offset=int(next_arguments(first)[3]), budget=512)


def test_reopened_workspace_advertises_its_frozen_schema_reader(tmp_path):
    from scidiscovery.artifact_agent.schema.common import canonical_json
    from scidiscovery.artifact_agent.service.local_workspace import LocalTrustedBackend
    from scidiscovery.artifact_agent.service.worker_start import write_worker_start
    assignment = dict(inputs=[], tools=[])
    workspace = LocalTrustedBackend(tmp_path/'backend').prepare(run_id='run_oldschema',
        inputs=(), assignment=canonical_json(assignment), result_schema=b'{}')
    start = json.loads(write_worker_start(workspace, assignment).read_bytes())
    assert '/payload/NAME' in start['output']['instruction']
    script = workspace.root/'tools/read_output_schema.py'
    script.chmod(0o600)
    script.write_bytes(script.read_bytes().replace(b'READ_OUTPUT_SCHEMA_FIELDS = 2', b'READ_OUTPUT_SCHEMA_FIELDS = 1'))
    start = json.loads(write_worker_start(workspace, assignment).read_bytes())
    assert 'frozen reader' in start['output']['instruction']
    assert '/payload/NAME' not in start['output']['instruction']


def test_unavailable_memory_retains_unknown_and_exact_detail_route():
    from scidiscovery.artifact_agent.service.worker_start import compact_startup_document
    original = dict(attempt_memory=dict(unavailable='no_exact_goal_or_recorded_recovery_source',
        coverage='unknown_not_empty', repair='Restore exact historical bindings.'))
    view = compact_startup_document(original)['attempt_memory']
    assert view['unavailable'] == original['attempt_memory']['unavailable']
    assert view['coverage'] == 'unknown_not_empty'
    assert view['details_read'].endswith('/attempt_memory')
    assert 'repair' not in view
    assert 'repair' in original['attempt_memory']


def test_helper_reporting_rules_go_to_helper_not_owner(tmp_path, monkeypatch):
    from scidiscovery.helper_tool import HELPER_TOOL
    _, _, _, call, owner = _gateway(tmp_path, monkeypatch)
    parent = json.loads(Path(owner['assignment_path']).read_bytes())
    alias = parent['inputs'][0]['source_name']
    _result(call('worker_helper', {'name':'read-scope', 'task':'Find evidence and contrary cases.', 'materials':[alias]}))
    opened = _result(call('worker_open_assignment', thread='helper', parent='owner'))
    helper = json.loads(Path(opened['assignment_path']).read_bytes())
    assert 'supporting and contrary evidence' in helper['role_instructions']
    assert 'narrow pointers/line locators' in helper['role_instructions']
    assert 'inspected scope, omissions/unread ranges' in helper['role_instructions']
    assert 'do not label every relevant section decisive' in helper['role_instructions']
    assert 'not a rereading checklist' in helper['role_instructions']
    assert 'counterevidence' in helper['role_instructions']
    assert 'inspected scope' not in HELPER_TOOL.description
    assert 'verify originals supporting adopted claims' in HELPER_TOOL.description
