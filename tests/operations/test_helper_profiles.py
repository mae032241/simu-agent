"""Frozen helper choices compose with native identity, limits and execution logs."""
import json
from pathlib import Path

import pytest

from scidiscovery.agent_execution_settings import AgentSettings, HelperSettings
from tests.operations.test_r4_internal_helpers import _gateway, _result


def test_default_lightweight_is_configured_and_same_tools_with_frozen_identity(tmp_path, monkeypatch):
    runtime, gateway, run_id, call, owner = _gateway(tmp_path, monkeypatch)
    prepared = _result(call('worker_helper', {'name':'inspect', 'profile':'lightweight', 'task':'Inspect bounded observations.'}))
    dispatch = prepared['dispatch']
    assert dispatch['model'] == 'gpt-6-luna' and dispatch['reasoning_effort'] == 'low'
    observed = {key:dispatch[key] for key in ('model','reasoning_effort')}
    # Wrong-profile admission must neither consume the reserved child slot nor fail the owner.
    assert 'error' in call('worker_open_assignment', thread='wrong-helper', parent='owner')
    assert runtime.runs.status(run_id).state == 'running'
    runtime.runs.agent_settings = AgentSettings(helpers=HelperSettings(profiles={}))
    assert _result(call('worker_helper', {'name':'inspect', 'profile':'lightweight', 'task':'Inspect bounded observations.'})) == prepared
    opened = _result(call('worker_open_assignment', thread='helper', parent='owner', observed=observed))
    assignment = json.loads(Path(opened['assignment_path']).read_bytes())
    assert 'output_schema' not in assignment and 'execution_profile' not in assignment
    light_tools = assignment['tools']
    assert 'worker_reference_read' in light_tools
    assert 'error' in call('worker_heartbeat', thread='helper', observed={'model':'wrong','reasoning_effort':'low'})
    _result(call('worker_heartbeat', thread='helper', observed=observed))
    _result(call('worker_helper', {'name':'inspect','action':'release'}))
    assert 'error' in call('worker_heartbeat', thread='helper', observed=observed)
    inherited = _result(call('worker_helper', {'name':'full', 'task':'Investigate a complex question.'}))
    parent = runtime.runs.status(run_id).execution_profile['profile']
    assert inherited['dispatch']['model'] == parent['model']
    full = _result(call('worker_open_assignment', thread='full-helper', parent='owner'))
    assert json.loads(Path(full['assignment_path']).read_bytes())['tools'] == light_tools
    assert runtime.runs.status(run_id).state == 'running'


def test_instance_profile_fields_merge_then_freeze_and_default_can_select_lightweight(tmp_path, monkeypatch):
    settings = {'profiles':{'lightweight':{'model':'configured-small','reasoning_effort':'low'}}}
    runtime, _, run_id, call, _ = _gateway(tmp_path, monkeypatch, settings,
        {'helpers':{'default_profile':'lightweight','profiles':{'lightweight':{'reasoning_effort':'medium'}}}})
    prepared = _result(call('worker_helper', {'name':'inspect','task':'Inspect observations.'}))
    assert prepared['dispatch']['model'] == 'configured-small'
    assert prepared['dispatch']['reasoning_effort'] == 'medium'
    assert prepared['dispatch']['profile'] == 'lightweight'
    changed = call('worker_helper', {'name':'inspect','profile':'inherit','task':'Inspect observations.'})
    assert 'error' in changed


def test_missing_lightweight_never_silently_falls_back(tmp_path, monkeypatch):
    _, _, _, call, _ = _gateway(tmp_path, monkeypatch, {'profiles':{}})
    assert 'error' in call('worker_helper', {'name':'inspect','profile':'lightweight','task':'Inspect data.'})
    assert _result(call('worker_helper', {'name':'inspect','profile':'inherit','task':'Inspect data.'}))['access'] == 'prepared'


def test_profile_limits_share_total_allowance_and_input_limit(tmp_path, monkeypatch):
    settings = {'max_calls':2,'profiles':{'lightweight':{'model':'fixture-small','reasoning_effort':'low',
        'max_calls':1,'max_input_bytes':512}}}
    _, _, _, call, _ = _gateway(tmp_path, monkeypatch, settings)
    assert 'error' in call('worker_helper', {'name':'too-long','profile':'lightweight','task':'x'*513})
    _result(call('worker_helper', {'name':'small','profile':'lightweight','task':'Inspect.'}))
    _result(call('worker_helper', {'name':'small','action':'release'}))
    assert 'error' in call('worker_helper', {'name':'small-again','profile':'lightweight','task':'Inspect.'})
    _result(call('worker_helper', {'name':'full','profile':'inherit','task':'Inspect.'}))
    _result(call('worker_helper', {'name':'full','action':'release'}))
    assert 'error' in call('worker_helper', {'name':'third','profile':'inherit','task':'Inspect.'})


def test_preexisting_helper_reservation_retains_parent_profile(tmp_path, monkeypatch):
    runtime, _, run_id, call, _ = _gateway(tmp_path, monkeypatch)
    request = {'name':'existing','task':'Inspect.','materials':[]}
    _result(call('worker_helper', request))
    with runtime.runs._connect() as db:
        db.execute('UPDATE worker_participants SET request_json=? WHERE run_id=?',
            (json.dumps({'task':'Inspect.','materials':[]}).encode(), run_id))
    dispatch = _result(call('worker_helper', request))['dispatch']
    assert dispatch['model'] == runtime.runs.status(run_id).execution_profile['profile']['model']
    _result(call('worker_open_assignment', thread='existing-helper', parent='owner'))


def test_lightweight_helper_reads_only_its_execution_cache_through_gateway(tmp_path, monkeypatch):
    from tests.operations.test_experiment_approval_handoff import experiment, start
    from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
    import scidiscovery.artifact_agent.interfaces.mcp_gateway as gateway_module
    f = experiment(tmp_path, monkeypatch, seconds=60)
    monkeypatch.setattr(f.adapter, 'status_details', lambda _: {'state':'running','progress':{
        'log_tails':[{'source':'solver_log','tail':'Newton converged at step 3\n'}]}}, raising=False)
    start(f)
    monkeypatch.setattr(gateway_module, 'load_operation_services', lambda *a, **kw:dict(f.coordinator.worker_services))
    gateway = UnifiedMCPRouter(f.root)
    parent_profile = f.runs.status(f.run_id).execution_profile['profile']
    def call(name, args=None, *, helper=False, observed=None):
        return gateway.handle({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{
            'name':'scid_call','arguments':{'name':name,'arguments':args or {}},
            '_meta':{'x-codex-turn-metadata':{'session_id':'continuation-fixture',
                'thread_id':'diagnostic-helper' if helper else 'next-owner', **(observed or parent_profile),
                **({'parent_thread_id':'next-owner','subagent_kind':'thread_spawn'} if helper else {})}}}})
    _result(call('worker_open_assignment'))
    dispatch = _result(call('worker_helper', {'name':'diagnose','profile':'lightweight','task':'Read the current execution logs; identify convergence or failure.'}))['dispatch']
    observed = {key:dispatch[key] for key in ('model','reasoning_effort')}
    _result(call('worker_open_assignment', helper=True, observed=observed))
    monkeypatch.setattr(f.adapter, 'status_details', lambda _:pytest.fail('cache read contacted remote'))
    page = _result(call('worker_experiment_execute', {'action':'logs'}, helper=True, observed=observed))
    assert page['text'] == 'Newton converged at step 3\n'
    assert 'error' in call('worker_experiment_execute', {'action':'logs','name':'other-task'}, helper=True, observed=observed)
    assert 'error' in call('worker_submit_result', helper=True, observed=observed)
    _result(call('worker_helper', {'name':'diagnose','action':'release'}))
    assert f.adapter.submits == 1


def test_historical_run_without_profiles_does_not_acquire_new_model_policy(tmp_path, monkeypatch):
    runtime, _, run_id, call, _ = _gateway(tmp_path, monkeypatch)
    with runtime.runs._connect() as db:
        row = db.execute('SELECT recovery_policy_json FROM runs WHERE run_id=?', (run_id,)).fetchone()
        policy = json.loads(row[0])
        policy['helpers'].pop('profiles')
        db.execute('UPDATE runs SET recovery_policy_json=? WHERE run_id=?', (json.dumps(policy).encode(), run_id))
    assert 'error' in call('worker_helper', {'name':'light','profile':'lightweight','task':'Inspect.'})
    assert _result(call('worker_helper', {'name':'same','profile':'inherit','task':'Inspect.'}))['dispatch']['profile'] == 'inherit'
