"""Native participant routing and durable access; no model or CLI transport fixture."""
import json
from pathlib import Path

import pytest


def _gateway(tmp_path, monkeypatch, settings=None, instance_settings=None):
    from tests.operations.test_r4_experiment_task import _real_experiment
    from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
    from scidiscovery.agent_execution_settings import AgentSettings, HelperSettings
    runtime, root, catalog, _, instance = _real_experiment(tmp_path, monkeypatch)
    if settings:
        runtime.runs.agent_settings = AgentSettings(helpers=HelperSettings(**settings))
    if instance_settings is not None:
        runtime.scheduler_bindings.save_agent_settings(instance.instance_id, instance_settings,
            expected_revision=0, maintenance=runtime.instance_maintenance)
    root.call_tool('operation_invoke', dict(name='helper-analysis', operation_id='science.result.diagnose.v1',
        max_attempts=2, instruction='Assess observations.',
        inputs=[dict(port='experiment_results', artifact_names=['observe.output'])]))
    run_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='run', name='helper-analysis')
    runtime.runs.worker_connections.attach(run_id=run_id, platform_session='session', thread_id='owner')
    gateway = UnifiedMCPRouter(root)
    profile = runtime.runs.status(run_id).execution_profile['profile']

    def call(name, arguments=None, *, thread='owner', parent=None, observed=None):
        return gateway.handle({'jsonrpc':'2.0', 'id':1, 'method':'tools/call', 'params': {
            'name':'scid_call', 'arguments': {'name':name, 'arguments':arguments or {}},
            '_meta': {'x-codex-turn-metadata': {'session_id':'session', 'thread_id':thread,
                **(observed or profile), **({'parent_thread_id':parent, 'subagent_kind':'thread_spawn'} if parent else {})}}}})
    owner = _result(call('worker_open_assignment'))
    return runtime, gateway, run_id, call, owner


def _result(reply):
    assert 'error' not in reply, reply
    return reply['result']['structuredContent']


def test_native_helper_uses_frozen_task_and_separate_projection(tmp_path, monkeypatch):
    runtime, gateway, run_id, call, owner = _gateway(tmp_path, monkeypatch)
    original = Path(owner['assignment_path']).read_bytes()
    request = {'name':'inspect', 'task':'Inspect the relevant data and improve the local explanation.', 'materials':['scratch/observations.txt']}
    prepared = _result(call('worker_helper', request))
    assert prepared['dispatch']['context'] == 'fresh'
    assert 'thread_id' not in json.dumps(prepared) and run_id not in json.dumps(prepared)
    opened = _result(call('worker_open_assignment', thread='helper', parent='owner'))
    assert opened['workspace_path'] == owner['workspace_path']
    assert opened['assignment_path'] != owner['assignment_path']
    assert Path(owner['assignment_path']).read_bytes() == original
    projected = json.loads(Path(opened['assignment_path']).read_bytes())
    assert projected['participation'] == 'helper'
    assert projected['task'] == request['task'] and projected['materials'] == request['materials']
    assert 'worker_submit_result' not in projected['tools']
    assert 'worker_helper' not in projected['tools']
    _result(call('worker_heartbeat', thread='helper'))
    assert 'error' in call('worker_submit_result', thread='helper')
    assert 'error' in call('worker_helper', request, thread='helper')
    assert 'error' in call('worker_identity', thread='helper')
    assert 'error' in call('instance_current', thread='helper')


def test_helper_parent_identity_and_admission_are_required(tmp_path, monkeypatch):
    runtime, gateway, run_id, call, owner = _gateway(tmp_path, monkeypatch)
    assert 'error' in call('worker_open_assignment', thread='unprepared', parent='owner')
    _result(call('worker_helper', {'name':'inspect', 'task':'Inspect data.'}))
    assert 'error' in call('worker_open_assignment', thread='other', parent='wrong-parent')
    _result(call('worker_open_assignment', thread='helper', parent='owner'))
    assert 'error' in call('worker_open_assignment', thread='nested', parent='helper')
    assert runtime.runs.worker_connections.resolve(platform_session='session', thread_id='owner').run_id == run_id
    from scidiscovery.artifact_agent.service.worker_connections import WorkerNotAttached
    import pytest
    with pytest.raises(WorkerNotAttached):
        runtime.runs.worker_connections.resolve(platform_session='session', thread_id='helper')


def test_release_revokes_without_asserting_native_termination(tmp_path, monkeypatch):
    runtime, gateway, run_id, call, owner = _gateway(tmp_path, monkeypatch, {'max_calls':1})
    request = {'name':'inspect', 'task':'Inspect data.'}
    assert _result(call('worker_helper', request)) == _result(call('worker_helper', request))
    _result(call('worker_open_assignment', thread='helper', parent='owner'))
    released = _result(call('worker_helper', {'name':'inspect', 'action':'release'}))
    assert released['access'] == 'released' and released['native_thread_state'] == 'unknown'
    assert released['native_action'] == {'action': 'interrupt', 'thread_id': 'helper',
                                         'task_name': 'inspect', 'required': True}
    assert 'even after completion' in released['instruction']
    assert 'As your next action, interrupt the exact bound thread_id' in released['instruction']
    assert 'are not atomic' in released['instruction']
    repeated = _result(call('worker_helper', {'name': 'inspect', 'action': 'release'}))
    assert repeated['native_action'] is None and repeated['access'] == 'released'
    assert 'Do not replay a cached interrupt' in repeated['instruction']
    assert _result(call('worker_helper', {'name': 'inspect', 'action': 'release'})) == repeated
    assert 'error' in call('worker_heartbeat', thread='helper')
    assert 'error' in call('worker_helper', {'name':'another', 'task':'Inspect more data.'})
    assert _result(call('worker_helper', request))['access'] == 'released'
    _result(call('worker_heartbeat'))


def test_release_before_binding_does_not_invent_native_identity(tmp_path, monkeypatch):
    runtime, gateway, run_id, call, owner = _gateway(tmp_path, monkeypatch)
    _result(call('worker_helper', {'name': 'inspect', 'task': 'Inspect data.'}))
    released = _result(call('worker_helper', {'name': 'inspect', 'action': 'release'}))
    assert released['native_action'] is None
    assert released['cleanup_status'] == 'blocked'
    assert 'Do not interrupt or close using an original spawn handle' in released['instruction']
    assert 'No trusted helper thread was admitted' in released['instruction']
    assert _result(call('worker_helper', {'name': 'inspect', 'action': 'release'})) == released
    assert released['native_thread_state'] == 'unknown'


def test_restart_retains_participant_access_and_parent_revocation(tmp_path, monkeypatch):
    runtime, gateway, run_id, call, owner = _gateway(tmp_path, monkeypatch)
    _result(call('worker_helper', {'name':'inspect', 'task':'Inspect data.'}))
    _result(call('worker_open_assignment', thread='helper', parent='owner'))
    from scidiscovery.artifact_agent.service.worker_connections import WorkerConnections
    connections = WorkerConnections(runtime.runs)
    assert connections.participant(platform_session='session', thread_id='helper')[0].run_id == run_id
    connections.release_helpers(run_id)
    import pytest
    from scidiscovery.artifact_agent.service.run_records import RunStateConflict
    with pytest.raises(RunStateConflict, match='access has ended'):
        connections.participant(platform_session='session', thread_id='helper')


def test_recreated_gateway_restores_running_owner_and_helper_without_open(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
    runtime, gateway, run_id, call, owner = _gateway(tmp_path, monkeypatch)
    _result(call('worker_helper', {'name':'inspect', 'task':'Inspect data.'}))
    _result(call('worker_open_assignment', thread='helper', parent='owner'))
    before=runtime.runs.status(run_id)
    marker=Path(owner['workspace_path'])/'scratch'/'preserved.txt'
    marker.parent.mkdir(exist_ok=True)
    marker.write_text('unfinished work')
    # A new gateway has no cached routers or tool state, like a restarted daemon.
    UnifiedMCPRouter.__init__(gateway, gateway.root)
    assert _result(call('worker_heartbeat'))['state']=='running'
    assert _result(call('worker_heartbeat', thread='helper'))['state']=='running'
    assert marker.read_text()=='unfinished work'
    after=runtime.runs.status(run_id)
    assert (after.run_id,after.deadline_at,after.started_at)==(before.run_id,before.deadline_at,before.started_at)
    assert _result(call('worker_helper', {'name':'inspect','action':'release'}))['access']=='released'
    assert 'error' in call('worker_heartbeat', thread='helper')
    # Submission reaches output validation rather than requiring another open.
    reply=_result(call('worker_submit_result'))
    assert reply['state']=='rejected' and reply['diagnostics']


def test_stage_and_submission_authority_are_declared_once():
    from scidiscovery.general_science_experiment_task import STAGE_TOOL
    from scidiscovery.operations.lifecycle import AGENT_LIFECYCLE_PROTOCOL
    assert STAGE_TOOL.owner_only
    assert next(item for item in AGENT_LIFECYCLE_PROTOCOL.tools if item.name == 'worker_submit_result').owner_only


def test_active_helper_and_owner_admission_are_mutually_exclusive(tmp_path, monkeypatch):
    import pytest
    from scidiscovery.artifact_agent.service.run_records import RunStateConflict
    runtime, gateway, run_id, call, owner = _gateway(tmp_path, monkeypatch)
    connections = runtime.runs.worker_connections
    instance_id = runtime.runs.status(run_id).instance_id
    def queued(name):
        gateway.root.call_tool('operation_invoke', dict(name=name, operation_id='science.object.review.v1',
            instruction='Assess observations.', inputs=[dict(port='subject', artifact_names=['observe.output'])]))
        return runtime.scheduler_bindings.resolve(instance=instance_id, namespace='run', name=name)
    assert _result(call('worker_identity'))['thread_id'] == 'owner'
    target = queued('second-owner')
    _result(call('worker_helper', {'name':'inspect', 'task':'Inspect data.'}))
    _result(call('worker_open_assignment', thread='helper', parent='owner'))
    with pytest.raises(RunStateConflict, match='helper history'):
        connections.attach(run_id=target, platform_session='session', thread_id='helper')
    _result(call('worker_helper', {'name':'inspect', 'action':'release'}))
    with pytest.raises(RunStateConflict, match='helper history'):
        connections.attach(run_id=target, platform_session='session', thread_id='helper')
    assert runtime.runs.status(target).state == 'queued'
    connections.attach(run_id=target, platform_session='session', thread_id='fresh-owner')
    _result(call('worker_open_assignment', thread='fresh-owner'))
    with runtime.runs._connect() as db:
        historical = db.execute("SELECT thread_id,released_at FROM worker_participants WHERE run_id=?", (run_id,)).fetchone()
    assert historical['thread_id'] == 'helper' and historical['released_at'] is not None
    _result(call('worker_helper', {'name':'next', 'task':'Inspect more data.'}))
    assert _result(call('worker_identity', thread='owner'))['thread_id'] == 'owner'
    with pytest.raises(RunStateConflict, match='owner binding history'):
        connections.participant(platform_session='session', thread_id='owner', parent_thread='owner', admit=True)
    stale_release = _result(call('worker_helper', {'name': 'inspect', 'action': 'release'}))
    assert stale_release['access'] == 'released'
    assert stale_release['native_thread_state'] == 'unknown'
    assert stale_release['native_action'] is None
    assert 'Do not replay a cached interrupt' in stale_release['instruction']
    assert _result(call('worker_helper', {'name': 'inspect', 'action': 'release'})) == stale_release
    assert connections.resolve(platform_session='session', thread_id='fresh-owner').run_id == target
    assert runtime.runs.status(target).state == 'running'
    _result(call('worker_heartbeat', thread='fresh-owner'))


@pytest.mark.parametrize('state', ['queued', 'running', 'completed'])
def test_legacy_owner_helper_overlap_blocks_cleanup_regardless_of_clock(tmp_path, monkeypatch, state):
    from scidiscovery.artifact_agent.service.run_records import RunStateConflict
    runtime, gateway, run_id, call, owner = _gateway(tmp_path, monkeypatch)
    instance_id = runtime.runs.status(run_id).instance_id
    gateway.root.call_tool('operation_invoke', dict(name='legacy-owner', operation_id='science.object.review.v1',
        instruction='Assess observations.', inputs=[dict(port='subject', artifact_names=['observe.output'])]))
    target = runtime.scheduler_bindings.resolve(instance=instance_id, namespace='run', name='legacy-owner')
    _result(call('worker_helper', {'name': 'inspect', 'task': 'Inspect data.'}))
    _result(call('worker_open_assignment', thread='helper', parent='owner'))
    _result(call('worker_helper', {'name': 'inspect', 'action': 'release'}))
    # Reconstruct an overlap persisted by older versions, with reversed clocks.
    # Current attach rejects this transition; no production guard is bypassed by
    # an actual caller. Test legacy data directly rather than permit new overlap.
    with runtime.runs._connect() as db:
        db.execute('INSERT INTO worker_connections(run_id,platform_session,thread_id,attached_at,attachment_sequence) '
            'VALUES(?,?,?,?,?)', (target, 'session', 'helper', '2000-01-01T00:00:00Z', 1))
        db.execute('UPDATE worker_participants SET admitted_at=? WHERE run_id=?',
            ('2099-01-01T00:00:00Z', run_id))
    if state != 'queued':
        _result(call('worker_open_assignment', thread='helper', parent='owner'))
    if state == 'completed':
        with runtime.runs._connect() as db:
            db.execute("UPDATE runs SET state='completed' WHERE run_id=?", (target,))
    connections = runtime.runs.worker_connections
    if state in {'queued', 'running'}:
        # Existing exact legacy ownership can recover idempotently; no new role
        # transfer is performed and the original binding remains unchanged.
        for _ in range(2):
            connections.attach(run_id=target, platform_session='session', thread_id='helper')
        with runtime.runs._connect() as db:
            binding = db.execute('SELECT attached_at,attachment_sequence FROM worker_connections WHERE run_id=?',
                (target,)).fetchone()
        assert (binding['attached_at'], binding['attachment_sequence']) == ('2000-01-01T00:00:00Z', 1)
    else:
        with pytest.raises(RunStateConflict, match='attach requires the exact queued Run'):
            connections.attach(run_id=target, platform_session='session', thread_id='helper')
    with pytest.raises(RunStateConflict, match='helper history'):
        connections.attach(run_id=run_id, platform_session='session', thread_id='helper')
    released = _result(call('worker_helper', {'name': 'inspect', 'action': 'release'}))
    assert released['native_action'] is None
    assert released['native_thread_state'] == 'unknown'
    assert 'owner binding history' in released['instruction']
    assert 'Do not interrupt or close' in released['instruction']
    assert 'including through the original spawn handle' in released['instruction']
    assert _result(call('worker_helper', {'name': 'inspect', 'action': 'release'})) == released
    assert connections.resolve(platform_session='session', thread_id='helper').run_id == target
    assert connections.resolve(platform_session='session', thread_id='owner').run_id == run_id
    assert runtime.runs.status(target).state == state
    if state == 'running':
        _result(call('worker_heartbeat', thread='helper', parent='owner'))


def test_terminal_owner_cannot_be_helper_but_can_reuse_owner_role(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.service.run_records import RunStateConflict
    runtime, gateway, run_id, call, owner = _gateway(tmp_path, monkeypatch)
    connections = runtime.runs.worker_connections
    instance_id = runtime.runs.status(run_id).instance_id
    def queued(name):
        gateway.root.call_tool('operation_invoke', dict(name=name, operation_id='science.object.review.v1',
            instruction='Assess observations.', inputs=[dict(port='subject', artifact_names=['observe.output'])]))
        return runtime.scheduler_bindings.resolve(instance=instance_id, namespace='run', name=name)
    first = queued('first-owner')
    connections.attach(run_id=first, platform_session='session', thread_id='former-owner')
    _result(call('worker_open_assignment', thread='former-owner'))
    previous = runtime.runs.status(first)
    runtime.runs.record_failure(first, reason='End fixture task', category='fixture',
        expected_state=previous.state, expected_last_activity_at=previous.last_activity_at)
    _result(call('worker_helper', {'name': 'inspect', 'task': 'Inspect data.'}))
    with pytest.raises(RunStateConflict, match='owner binding history'):
        connections.participant(platform_session='session', thread_id='former-owner', parent_thread='owner', admit=True)
    second = queued('second-owner')
    connections.attach(run_id=second, platform_session='session', thread_id='former-owner')
    assert connections.resolve(platform_session='session', thread_id='former-owner').run_id == second
    _result(call('worker_open_assignment', thread='former-owner'))
    _result(call('worker_heartbeat', thread='former-owner'))


def test_helper_startup_selects_material_navigation_and_contracts_on_demand(tmp_path, monkeypatch):
    runtime, gateway, run_id, call, owner = _gateway(tmp_path, monkeypatch)
    parent = json.loads(Path(owner['assignment_path']).read_bytes())
    selected = parent['inputs'][0]
    request = {'name': 'investigate', 'task': 'Investigate the uncertainty of the selected observations.',
               'materials': [selected['source_name'], 'scratch/uncertainty.csv', 'missing-original']}
    _result(call('worker_helper', request))
    opened = _result(call('worker_open_assignment', thread='helper', parent='owner'))
    assignment = json.loads(Path(opened['assignment_path']).read_bytes())
    # Comparable UTF-8 response/assignment bytes, not model token measurements.
    import os
    if log_dir := os.environ.get('SCID_TEST_LOG_DIR'):
        normalized = json.loads(json.dumps(opened).replace(opened['workspace_path'], '<workspace>'))
        normalized['remaining_seconds'] = 0
        measures = {key: len(json.dumps(value, ensure_ascii=False, sort_keys=True,
                    separators=(',', ':')).encode()) for key, value in
                    [('open_response', normalized), ('assignment', assignment)]}
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        Path(log_dir, 'helper-startup-bytes.json').write_text(json.dumps(measures))
    assert len(assignment['inputs']) == 1
    navigation = assignment['inputs'][0]
    assert {key: navigation[key] for key in selected if key != 'scientific_view'} == {
        key: value for key, value in selected.items() if key != 'scientific_view'}
    assert 'scientific_view' not in navigation
    if 'scientific_view' in selected:
        assert navigation['scientific_overview_available'] is True
        assert navigation['read'].endswith('/inputs/0/scientific_view')
    assert assignment['materials'] == request['materials']
    assert 'tool_contracts' not in assignment
    assert 'output' not in assignment and 'output_schema' not in assignment
    assert not {'task', 'materials', 'role_instructions', 'tool_contracts'} & opened.keys()
    assert assignment['tools'] and 'worker_submit_result' not in assignment['tools']
    # Default reading division retains observations and omissions in an attributed
    # helper report; the owner keeps original-read and finalization authority.
    for clause in ('supporting and contrary evidence', 'failed/inconclusive observations',
                   'pointers/line locators', 'omissions/unread ranges', 'missing coverage',
                   'For material-reading subtasks', 'permitted reading/check tools, no edits',
                   'grant no formal independent review'):
        assert clause in assignment['role_instructions']
    profile = runtime.runs.status(run_id).execution_profile['profile']
    described = _result(gateway.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {
        'name': 'scid_describe', 'arguments': {'name': 'worker_reference_read'},
        '_meta': {'x-codex-turn-metadata': {'session_id': 'session', 'thread_id': 'helper',
            'parent_thread_id': 'owner', 'subagent_kind': 'thread_spawn', **profile}}}}))
    assert described['inputSchema'] == parent['tool_contracts']['worker_reference_read']['inputSchema']
    assert described['description'] == parent['tool_contracts']['worker_reference_read']['description']
    _result(call('worker_helper', {'name': 'investigate', 'action': 'release'}))
    _result(call('worker_helper', {'name': 'local-files', 'task': 'Investigate scratch output.'}))
    next_open = _result(call('worker_open_assignment', thread='second-helper', parent='owner'))
    assert json.loads(Path(next_open['assignment_path']).read_bytes())['inputs'] == []


@pytest.mark.parametrize('legacy_reader', [False, True])
def test_helper_large_scientific_view_is_navigation_with_exact_original_routes(tmp_path, monkeypatch, legacy_reader):
    from scidiscovery.artifact_agent.schema.common import canonical_json
    from scidiscovery.artifact_agent.service.local_workspace import write_control_workspace_file
    from tests.operations.test_minimum_support import copied_pages, run_command
    runtime, _, _, call, owner = _gateway(tmp_path, monkeypatch)
    workspace = Path(owner['workspace_path'])
    parent = json.loads(Path(owner['assignment_path']).read_bytes())
    index, selected = next((index, item) for index, item in enumerate(parent['inputs'])
        if item.get('relative_path') and item.get('exposure') in {'full', 'on_demand', 'material'}
        and not item.get('materialization') and (workspace/item['relative_path']).is_file())
    # A qualified control view can be large even though the helper's requested input index is tiny.
    qualified = dict(pointers=['/summary'], boundary_application='declared_not_authorization',
        handoff=dict(summary='Bounded source report.', verdict='inconclusive', limitations=['Coverage incomplete.'],
            boundary_declarations=[dict(declaration=dict(boundary_key=f'bound_{n}',
                statement='Original scope.' * 40, interpretation='Unverified interpretation.' * 30),
                source_checks=[dict(status='unknown', locator=f'/omitted/{n}')],
                authority='author_reported', verification='unverified') for n in range(32)]))
    selected['scientific_view'] = qualified
    original = canonical_json(parent)
    write_control_workspace_file(workspace, Path('assignment.json'), original, replace=True, mode=0o400)
    source_bytes = (workspace/selected['relative_path']).read_bytes()
    if legacy_reader:
        script = workspace/'tools/read_input.py'
        script.chmod(0o600)
        script.write_bytes(script.read_bytes().replace(b'SCIENTIFIC_COMPACT_VIEW = 1', b'SCIENTIFIC_COMPACT_VIEW = 0'))
    request = dict(name='scope-navigation', task='Inspect scope, counterevidence and unresolved qualifications.',
        materials=[selected['source_name'], 'unknown-material'])
    _result(call('worker_helper', request))
    opened = _result(call('worker_open_assignment', thread='helper', parent='owner'))
    helper = json.loads(Path(opened['assignment_path']).read_bytes())
    assert len(Path(opened['assignment_path']).read_bytes()) < len(original)
    assert len(Path(opened['assignment_path']).read_bytes()) < len(canonical_json(qualified))
    assert helper['materials'] == request['materials'] and len(helper['inputs']) == 1
    entry = helper['inputs'][0]
    assert {key: entry[key] for key in selected if key != 'scientific_view'} == {
        key: value for key, value in selected.items() if key != 'scientific_view'}
    assert 'scientific_view' not in entry
    assert entry.get('scientific_overview_available', False) is not legacy_reader
    assert 'navigation, not complete originals or proof of inspection' in helper['role_instructions']
    assert 'contrary evidence' in helper['role_instructions'] and 'unresolved material names remain gaps' in helper['role_instructions']
    _, restored = run_command(workspace, entry['read'])
    assert json.loads(restored) == qualified  # All source_checks, declarations, omissions and limitations.
    _, restored_source = copied_pages(workspace, selected['source_name'], full=True)
    assert restored_source.encode() == source_bytes
    assert Path(owner['assignment_path']).read_bytes() == original
    assert (workspace/selected['relative_path']).read_bytes() == source_bytes
    assert 'worker_submit_result' not in helper['tools'] and 'worker_helper' not in helper['tools']


def test_helper_tool_activity_records_observed_access_and_participation(tmp_path, monkeypatch):
    runtime, gateway, run_id, call, owner = _gateway(tmp_path, monkeypatch)
    _result(call('worker_helper', {'name': 'inspect', 'task': 'Investigate observation uncertainty.'}))
    _result(call('worker_open_assignment', thread='helper', parent='owner'))
    _result(call('worker_heartbeat', thread='helper'))
    _result(call('worker_helper', {'name': 'inspect', 'action': 'release'}))
    with runtime.runs._connect() as db:
        events = [json.loads(row[0]) for row in db.execute(
            "SELECT diagnostic_json FROM run_activity WHERE run_id=? AND activity='tool_call_completed'", (run_id,))]
        relation = db.execute("SELECT * FROM worker_participants WHERE run_id=?", (run_id,)).fetchone()
    accesses = [item['helper_access'] for item in events if 'helper_access' in item]
    assert accesses == [{'name': 'inspect', 'access': 'prepared'},
                        {'name': 'inspect', 'access': 'released', 'native_thread_state': 'unknown'}]
    helper_events = [item for item in events if item.get('participant') == {'role': 'helper', 'name': 'inspect'}]
    assert {item['tool_name'] for item in helper_events} == {'worker_open_assignment', 'worker_heartbeat'}
    assert relation['owner_thread'] == 'owner' and relation['thread_id'] == 'helper'
    assert relation['admitted_at'] and relation['released_at']
    assert all('usage' not in item and 'thread_completed' not in item for item in events)





def test_helper_scientific_attempts_retain_control_participant(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
    from tests.operations.test_tcad_result_analysis import analysis_system
    from tests.operations.test_result_analysis_tool import score_inputs
    _, runtime, facade, _, artifacts, register = analysis_system(tmp_path)
    register('generic_results', b'Bounded fixture output.', 'opaque', parents=(artifacts['plan'].ref,))
    register('generic_bundle', score_inputs()[0]['curve_bundle'], 'scidiscovery.curve-bundle.v1', parents=(artifacts['plan'].ref,))
    facade.call_tool('operation_invoke', dict(name='helper-comparison', operation_id='science.result.diagnose.v1',
        instruction='Compare bound curves.', inputs=[
            dict(port='experiment_plan', artifact_names=['plan']),
            dict(port='experiment_results', artifact_names=['generic_results']),
            dict(port='curve_bundle', artifact_names=['generic_bundle'])]))
    run_id = runtime.scheduler_bindings.resolve(instance=facade.facade.instance, namespace='run', name='helper-comparison')
    runtime.runs.worker_connections.attach(run_id=run_id, platform_session='private-session', thread_id='private-owner')
    gateway = UnifiedMCPRouter(facade)
    profile = runtime.runs.status(run_id).execution_profile['profile']
    def call(name, args=None, helper=False):
        return gateway.handle({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{
            'name':'scid_call','arguments':{'name':name,'arguments':args or {}},
            '_meta':{'x-codex-turn-metadata':{'session_id':'private-session',
                'thread_id':'private-helper' if helper else 'private-owner', **profile,
                **({'parent_thread_id':'private-owner','subagent_kind':'thread_spawn'} if helper else {})}}}})
    _result(call('worker_open_assignment'))
    _result(call('worker_helper', {'name':'investigate','task':'Compare exact bound curves.'}))
    _result(call('worker_open_assignment', helper=True))
    args = dict(record_key='helper-comparison', request=score_inputs()[1])
    assert _result(call('worker_curve_score', args, helper=True))['status'] == 'computed'
    assert 'error' in call('worker_curve_score', {}, helper=True)
    assert _result(call('worker_curve_score', args))['status'] == 'computed'
    attempts = runtime.runs.tool_attempts(run_id)
    assert [a['state'] for a in attempts] == ['completed', 'rejected', 'completed']
    assert [a['participant'] for a in attempts] == [
        {'role':'helper','name':'investigate'}, {'role':'helper','name':'investigate'}, {'role':'owner'}]
    with runtime.runs._connect() as db:
        rows = db.execute("SELECT activity,diagnostic_json FROM run_activity WHERE run_id=? AND activity LIKE 'tool_attempt_%'", (run_id,)).fetchall()
    for _, raw in rows:
        record = json.loads(raw)
        assert record['participant'] == next(a['participant'] for a in attempts if a['attempt_key'] == record['attempt_key'])
        assert 'private-' not in json.dumps(record)

    # Cancellation after source reads leaves an explicitly interrupted attempt,
    # never a fabricated successful terminal receipt.
    import pytest
    import curve_score.analysis_tool as score
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt()
    monkeypatch.setattr(score, 'evaluate_analysis_request', interrupted)
    with pytest.raises(KeyboardInterrupt):
        call('worker_curve_score', args, helper=True)
    last = runtime.runs.tool_attempts(run_id)[-1]
    assert last['state'] == 'interrupted'
    assert last['participant'] == {'role':'helper','name':'investigate'}
    assert last['read_sources']
    from scidiscovery.artifact_agent.service.tool_evidence import scientific_evidence_projection
    public = scientific_evidence_projection(runtime.runs._evidence_snapshot(run_id))
    assert b'participant' not in public and b'private-' not in public
