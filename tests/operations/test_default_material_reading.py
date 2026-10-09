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
        assert 'checked findings' in policy and 'directly' in policy
        assert 'do not reread merely' in policy
        assert 'specific conflict' in policy
        assert 'explicit independent-check requirement' in policy
        assert 'not personal reading or formal qualification' in policy
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
    assert 'Report checked findings directly' in helper['role_instructions']
    assert 'Do not return a mandatory rereading list' in helper['role_instructions']
    assert 'counterevidence' in helper['role_instructions']
    assert 'inspected scope' not in HELPER_TOOL.description
    assert 'integrate checked findings' in HELPER_TOOL.description


def test_owner_bulk_reading_uses_fresh_helper_and_long_native_wait_without_reporting_rules():
    from scidiscovery.artifact_agent.service.worker_start import MATERIAL_READING
    from scidiscovery.helper_tool import HELPER_TOOL
    from scidiscovery.platforms.codex import _local_native_tool_instruction
    from types import SimpleNamespace
    for text in (MATERIAL_READING, HELPER_TOOL.description):
        assert 'One fresh helper per bounded question' in text
        assert 'then release/close' in text
        assert '60 seconds when supported' in text
        assert 'Avoid repeated short waits or sleeps' in text
        assert 'Independent analysis uses its own helper' in text
        assert 'inspected scope' not in text
    compiled = SimpleNamespace(spec=SimpleNamespace(executor=SimpleNamespace(
        native_tools=SimpleNamespace(web_search='disabled',view_image=False))))
    instructions = _local_native_tool_instruction(compiled)
    assert 'Reuse the returned workspace_path exactly as workdir' in instructions
    assert '60 seconds when supported' in instructions


def test_compact_inventory_keeps_failure_unknown_qualification_and_omission_states():
    from copy import deepcopy
    from scidiscovery.artifact_agent.schema.common import canonical_json
    from scidiscovery.artifact_agent.service.worker_start import compact_startup_document
    entries = [dict(path=f'scratch/artifacts/long-original-result-{n}.json',
        status='failed' if n == 0 else 'unknown' if n == 1 else 'retained',
        producer_trust='unverified', projection_coverage='incomplete',
        raw_retained=False, source_name=f'bound_{n}' if n != 1 else None) for n in range(24)]
    entries.append(dict(path='scratch/artifacts/exact-reuse.json', status='retained', same_entry_as='inventory'))
    inventory = dict(source_name='inventory', kind='capture_inventory', coverage='incomplete',
        coverage_changed=True, attempt_inventory='declared_author_reported', reference_namespace='producer_task',
        roots=['scratch/artifacts'], source_declarations=[{'status':'unverified'}], entries=entries)
    ledger = dict(source_name='ledger', kind='ledger_view', records=[{'status':'failed', 'values':[-3]}])
    observed = dict(basis='Author-reported, unverified, incomplete coverage; unknown is not success.',
        sources=[inventory, ledger], omitted=[dict(source_name='unreadable', reason='material_receipt_unverifiable')],
        omitted_read='Read the exact bound original.')
    original = dict(observed_results=observed)
    frozen = deepcopy(original)
    result = compact_startup_document(original)
    compact = result['observed_results']['sources'][0]
    assert len(canonical_json(result)) < len(canonical_json(original))
    assert compact['coverage'] == 'incomplete' and compact['coverage_changed'] is True
    assert compact['attempt_inventory'] == 'declared_author_reported'
    assert compact['reference_namespace'] == 'producer_task'
    assert compact['entry_count'] == 25 and compact['exact_reuses'] == 1 and compact['unresolved_sources'] == 1
    assert compact['entry_states']['status'] == {'failed':1, 'unknown':1, 'retained':23}
    assert compact['entry_states']['producer_trust'] == {'unverified':24, 'unknown_missing':1}
    assert compact['entry_states']['projection_coverage'] == {'incomplete':24, 'unknown_missing':1}
    assert compact['entry_states']['raw_retained'] == {'False':24, 'unknown_missing':1}
    assert result['observed_results']['sources'][1] == ledger
    assert result['observed_results']['omitted'] == observed['omitted']
    assert result['observed_results']['omitted_read'] == observed['omitted_read']
    assert compact['details_read'].endswith('/observed_results/sources/0')
    assert 'not scientific coverage or qualification' in result['observed_results']['instruction']
    assert original == frozen


def test_complete_inventory_detail_is_preserved_at_the_advertised_pointer(tmp_path):
    from scidiscovery.artifact_agent.schema.common import canonical_json
    from scidiscovery.artifact_agent.service.local_workspace import LocalTrustedBackend
    from scidiscovery.artifact_agent.service.worker_start import write_worker_start
    from scidiscovery.artifact_agent.service.input_reader import read
    from tests.artifact_agent.test_input_reader import body
    inventory = dict(source_name='inventory', kind='capture_inventory', coverage='incomplete',
        attempt_inventory='declared_author_reported', roots=['scratch/artifacts'],
        source_declarations=[dict(statement='Incomplete original capture.', status='unverified')],
        entries=[dict(path=f'scratch/artifacts/original-attempt-{n}.json', status='failed',
            source_name=f'bound_{n}', producer_trust='unverified') for n in range(20)])
    observed = dict(basis='Author reported; failed and unknown remain limited.', sources=[inventory])
    assignment = dict(inputs=[], tools=[], observed_results=observed)
    workspace = LocalTrustedBackend(tmp_path/'backend').prepare(run_id='run_inventorynavigation',
        inputs=(), assignment=canonical_json(assignment), result_schema=b'{}')
    start = json.loads(write_worker_start(workspace, assignment).read_bytes())
    compact = start['observed_results']['sources'][0]
    assert compact['entry_states']['status'] == {'failed':20}
    assert 'entries' not in compact
    context = json.loads((workspace.root/'worker-context.json').read_bytes())
    assert context['observed_results'] == observed
    pointer = compact['details_read'].split(' --pointer ')[1]
    restored = read(workspace.root, 'worker-context.json', file=True, pointers=[pointer], budget=8192)
    assert json.loads(body(restored)) == inventory


def test_analysis_own_helper_does_not_replace_owner_judgment_or_numerical_checks():
    from scidiscovery.general_science_result_analysis import CORE_PROMPT
    core = CORE_PROMPT.replace('\n', ' ')
    assert "your own fresh helper" in core
    assert "independently of W's" in core
    assert "without routine rereading" in core
    assert "Read goal/constraints yourself" in core
    assert "Scientific judgments and required independent numerical checks remain yours" in core
