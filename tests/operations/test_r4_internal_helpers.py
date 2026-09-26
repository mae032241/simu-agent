"""Native participant routing and durable access; no model or CLI transport fixture."""
import json
from pathlib import Path


def _gateway(tmp_path, monkeypatch, settings=None):
    from tests.operations.test_r4_experiment_task import _real_experiment
    from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
    from scidiscovery.agent_execution_settings import AgentSettings, HelperSettings
    runtime, root, catalog, _, instance = _real_experiment(tmp_path, monkeypatch)
    if settings:
        runtime.runs.agent_settings = AgentSettings(helpers=HelperSettings(**settings))
    root.call_tool('operation_invoke', dict(name='helper-analysis', operation_id='science.result.diagnose.v1',
        max_attempts=2, instruction='Assess observations.',
        inputs=[dict(port='experiment_results', artifact_names=['observe.output'])]))
    run_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='run', name='helper-analysis')
    runtime.runs.worker_connections.attach(run_id=run_id, platform_session='session', thread_id='owner')
    gateway = UnifiedMCPRouter(root)
    profile = runtime.runs.status(run_id).execution_profile['profile']

    def call(name, arguments=None, *, thread='owner', parent=None):
        return gateway.handle({'jsonrpc':'2.0', 'id':1, 'method':'tools/call', 'params': {
            'name':'scid_call', 'arguments': {'name':name, 'arguments':arguments or {}},
            '_meta': {'x-codex-turn-metadata': {'session_id':'session', 'thread_id':thread,
                **profile, **({'parent_thread_id':parent, 'subagent_kind':'thread_spawn'} if parent else {})}}}})
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
    assert opened['task'] == request['task'] and opened['materials'] == request['materials']
    assert opened['workspace_path'] == owner['workspace_path']
    assert opened['assignment_path'] != owner['assignment_path']
    assert Path(owner['assignment_path']).read_bytes() == original
    projected = json.loads(Path(opened['assignment_path']).read_bytes())
    assert projected['participation'] == 'helper'
    assert 'worker_submit_result' not in projected['tool_contracts']
    assert 'worker_helper' not in projected['tool_contracts']
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
    assert 'error' in call('worker_heartbeat', thread='helper')
    assert 'error' in call('worker_helper', {'name':'another', 'task':'Inspect more data.'})
    assert _result(call('worker_helper', request))['access'] == 'released'
    _result(call('worker_heartbeat'))


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
        gateway.root.call_tool('operation_invoke', dict(name=name, operation_id='science.result.diagnose.v1',
            instruction='Assess observations.', inputs=[dict(port='experiment_results', artifact_names=['observe.output'])]))
        return runtime.scheduler_bindings.resolve(instance=instance_id, namespace='run', name=name)
    assert _result(call('worker_identity'))['thread_id'] == 'owner'
    target = queued('second-owner')
    _result(call('worker_helper', {'name':'inspect', 'task':'Inspect data.'}))
    _result(call('worker_open_assignment', thread='helper', parent='owner'))
    with pytest.raises(RunStateConflict, match='active helper'):
        connections.attach(run_id=target, platform_session='session', thread_id='helper')
    _result(call('worker_helper', {'name':'inspect', 'action':'release'}))
    connections.attach(run_id=target, platform_session='session', thread_id='helper')
    assert connections.resolve(platform_session='session', thread_id='helper').run_id == target
    assert _result(call('worker_identity', thread='helper', parent='owner'))['thread_id'] == 'helper'
    _result(call('worker_open_assignment', thread='helper', parent='owner'))
    assert _result(call('worker_identity', thread='helper', parent='owner'))['thread_id'] == 'helper'
    with runtime.runs._connect() as db:
        historical = db.execute("SELECT thread_id,released_at FROM worker_participants WHERE run_id=?", (run_id,)).fetchone()
    assert historical['thread_id'] == 'helper' and historical['released_at'] is not None
    _result(call('worker_helper', {'name':'next', 'task':'Inspect more data.'}))
    other = queued('attached-first')
    connections.attach(run_id=other, platform_session='session', thread_id='attached-first')
    assert _result(call('worker_identity', thread='attached-first'))['thread_id'] == 'attached-first'
    with pytest.raises(RunStateConflict, match='owns an active Run'):
        connections.participant(platform_session='session', thread_id='attached-first', parent_thread='owner', admit=True)
