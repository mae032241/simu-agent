"""Deployment offline debug policy; real control fixtures, no native/model/network."""
import json
from pathlib import Path

import pytest

from scidiscovery.agent_execution_settings import AgentSettings, effective_settings, parse_settings
from tests.operations.test_evidence_source_capture import open_extraction


def _offline_fixture(monkeypatch):
    from tests.operations.test_l2_run_invariants import _system
    import tests.operations.test_evidence_source_capture as fixture
    def offline_system(path):
        system = _system(path)
        settings = AgentSettings(debug_disable_task_network=True)
        system[1].runs.agent_settings = settings
        system[1].scheduler_bindings.global_settings = settings
        return system
    monkeypatch.setattr(fixture, '_system', offline_system)


def test_debug_policy_is_global_and_default_off():
    assert effective_settings(AgentSettings(), {})['debug_disable_task_network'] is False
    offline = parse_settings({'debug_disable_task_network': True})
    assert effective_settings(offline, {})['progression']['root_network_access'] is False
    with pytest.raises(ValueError, match='deployment'):
        effective_settings(offline, {'debug_disable_task_network': False})


def test_offline_extraction_keeps_local_material_and_rejects_http_before_handler(tmp_path, monkeypatch):
    from scidiscovery import source_capture
    _offline_fixture(monkeypatch)
    _, runtime, _, worker, opened, _ = open_extraction(tmp_path)
    status = runtime.runs.status(worker._run_id)
    assert status.recovery_policy['debug_disable_task_network'] is True
    assignment = json.loads(Path(opened['assignment_path']).read_bytes())
    assert assignment['task_network_policy']['host_requests'] is False
    assert assignment['inputs']  # Sealed/local sources retain normal admission.
    monkeypatch.setattr(source_capture, 'fetch_source', lambda *a, **kw: pytest.fail('denied tool contacted HTTP'))
    with pytest.raises(Exception, match='network.*disabled'):
        worker.call_tool('worker_capture_source', {'url': 'https://example.org/source'})
    assert runtime.runs.status(worker._run_id).state == 'running'
    assert runtime.runs.tool_evidence(worker._run_id) == []
    with runtime.runs._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM run_activity WHERE activity='source_network_request'").fetchone()[0] == 0


def test_new_offline_runtime_rejects_old_run_attach_open_recovery_but_can_settle(tmp_path):
    from scidiscovery.artifact_agent.service.run_records import RunStateConflict
    from scidiscovery.source_capture import SOURCE_CAPTURE_TOOL
    _, runtime, _, worker, _, _ = open_extraction(tmp_path)
    prior = runtime.runs.status(worker._run_id)
    # A restarted service loads the new startup setting; this does not claim to
    # revoke a pre-existing native process. No Run/identity record is edited.
    runtime.runs.agent_settings = AgentSettings(debug_disable_task_network=True)
    with pytest.raises(RunStateConflict, match='task_network_policy_changed'):
        runtime.runs.worker_connections.attach(run_id=prior.run_id,
            platform_session='session', thread_id='new-worker')
    with pytest.raises(RunStateConflict, match='task_network_policy_changed'):
        runtime.runs.reopen(run_id=prior.run_id, operation_id=prior.operation_id,
            operation_digest=prior.operation_digest)
    with pytest.raises(Exception, match='network.*disabled'):
        runtime.runs.reserve_network_request(prior.run_id, SOURCE_CAPTURE_TOOL, 'https://example.org/source')
    compiled = runtime.runs.compiled_operation(prior)
    with pytest.raises(RunStateConflict, match='task_network_policy_changed'):
        runtime.runs.execution_settings(compiled, instance_id=prior.instance_id, recovery_source=prior.run_id)
    runtime.runs.record_failure(prior.run_id, reason='explicit stop after policy change',
        expected_state=prior.state, expected_last_activity_at=prior.last_activity_at)
    assert runtime.runs.status(prior.run_id).state == 'failed'
    assert prior.recovery_policy.get('debug_disable_task_network', False) is False


def test_generated_root_and_worker_roles_use_one_policy_and_reject_stale_profiles(tmp_path, monkeypatch):
    import tomllib
    from scidiscovery.platforms.codex import initialize, validate_task_network_profile
    from scidiscovery.operations.catalog import compile_installed_catalog
    from scidiscovery.platforms.common import PlatformConflictError
    settings = tmp_path / 'settings.json'
    settings.write_text('{"debug_disable_task_network":true}')
    monkeypatch.setenv('SCID_AGENT_SETTINGS_FILE', str(settings))
    project = tmp_path / 'project'; project.mkdir()
    catalog = compile_installed_catalog()
    initialize(project, control_socket=tmp_path/'control.sock', operation_catalog=catalog)
    root_config = tomllib.loads((project/'.codex/config.toml').read_text())
    assert root_config['web_search'] == 'disabled'
    assert root_config['sandbox_workspace_write'] == {'network_access':False}
    assert 'debug_disable_task_network=true' in (project/'AGENTS.md').read_text()
    roles = list((project/'.codex/agents').glob('*.toml'))
    assert roles
    for path in roles:
        role = tomllib.loads(path.read_text())
        assert role['web_search'] == 'disabled'
        assert 'permissions' not in role and 'default_permissions' not in role
        assert role['features']['shell_tool'] == role['features']['unified_exec']
    validate_task_network_profile(project, catalog, debug_disable_task_network=True)
    path = roles[0]
    path.write_text(path.read_text().replace('web_search = "disabled"', 'web_search = "live"'))
    with pytest.raises(PlatformConflictError, match='Worker/helper network profile'):
        validate_task_network_profile(project, catalog, debug_disable_task_network=True)


def test_offline_debug_rejects_unenforceable_legacy_sandbox_without_changing_files(tmp_path, monkeypatch):
    from scidiscovery.platforms.codex import initialize
    from scidiscovery.platforms.common import PlatformConflictError
    settings = tmp_path/'settings.json'; settings.write_text('{"debug_disable_task_network":true}')
    monkeypatch.setenv('SCID_AGENT_SETTINGS_FILE', str(settings))
    project = tmp_path/'project'; (project/'.codex').mkdir(parents=True)
    config = project/'.codex/config.toml'; config.write_text('sandbox_mode="danger-full-access"\n')
    before = config.read_bytes()
    with pytest.raises(PlatformConflictError, match='conflicts'):
        initialize(project, control_socket=tmp_path/'socket')
    assert config.read_bytes() == before
    assert not (project/'.codex/agents').exists()


def test_helper_reuses_owner_frozen_deny_and_restart_rejects_old_policy(tmp_path, monkeypatch):
    from tests.operations.test_r4_internal_helpers import _result
    import tests.operations.test_r4_internal_helpers as fixture
    from tests.operations.test_r4_experiment_task import _real_experiment
    def offline_experiment(*args, **kwargs):
        result = _real_experiment(*args, **kwargs)
        result[0].runs.agent_settings = AgentSettings(debug_disable_task_network=True)
        result[0].scheduler_bindings.global_settings = result[0].runs.agent_settings
        return result
    monkeypatch.setattr('tests.operations.test_r4_experiment_task._real_experiment', offline_experiment)
    runtime, _, run_id, call, owner = fixture._gateway(tmp_path, monkeypatch)
    _result(call('worker_helper', {'name':'inspect','task':'Read the sealed observations.'}))
    helper = _result(call('worker_open_assignment', thread='helper', parent='owner'))
    owner_policy = json.loads(Path(owner['assignment_path']).read_bytes())['task_network_policy']
    assert json.loads(Path(helper['assignment_path']).read_bytes())['task_network_policy'] == owner_policy
    assert owner_policy == json.loads(Path(owner['workspace_path'], 'worker-start.json').read_bytes())['task_network_policy']
    runtime.runs.agent_settings = AgentSettings()
    assert 'error' in call('worker_heartbeat', thread='helper')
    assert 'error' in call('worker_helper', {'name':'other','task':'Read inputs.'})
    assert runtime.runs.status(run_id).state == 'running'


def test_old_loop_missing_debug_flag_retains_off_policy_and_cannot_upgrade_in_place(tmp_path):
    from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService
    bindings = SchedulerBindingService(tmp_path/'scheduler.db')
    instance = bindings.create_instance(name='offline-fixture', title='Policy fixture', objective='Retain frozen permissions.')
    old = bindings.control_settings(instance.instance_id)
    old['effective'].pop('debug_disable_task_network')
    assert bindings._control_settings_match(instance.instance_id, json.dumps(old))
    bindings.global_settings = AgentSettings(debug_disable_task_network=True)
    assert not bindings._control_settings_match(instance.instance_id, json.dumps(old))


@pytest.mark.parametrize('effective_search', ['disabled', 'live'])
def test_factory_verifies_effective_root_search_and_preserves_named_policy(tmp_path, monkeypatch, effective_search):
    import os
    import tomllib
    from types import SimpleNamespace
    from scidiscovery.platforms.codex import initialize
    from scidiscovery.platforms.codex_app_server import AppServer, HostError
    from scidiscovery.platforms.codex_progression import CodexProgressionFactory
    from scidiscovery.platforms.codex_root_host import RootPermissions
    from scidiscovery.operations.catalog import compile_installed_catalog
    from tests.operations.test_codex_permission_profiles import Connection
    settings = tmp_path/'settings.json'; settings.write_text('{"debug_disable_task_network":true}')
    monkeypatch.setenv('SCID_AGENT_SETTINGS_FILE', str(settings))
    home = tmp_path/'home'; home.mkdir(); monkeypatch.setenv('CODEX_HOME', str(home))
    definition = {'filesystem':{':root':'deny',':workspace_roots':'write'},'network':{'enabled':False}}
    (home/'config.toml').write_text('default_permissions="isolated"\n[permissions.isolated.filesystem]\n":root"="deny"\n":workspace_roots"="write"\n[permissions.isolated.network]\nenabled=false\n')
    project = tmp_path/'project'; project.mkdir()
    catalog = compile_installed_catalog()
    initialize(project, control_socket=tmp_path/'socket', operation_catalog=catalog)
    config = tomllib.loads((project/'.codex/config.toml').read_text())
    connection = Connection(definition=definition, network=False)
    connection.child = SimpleNamespace(pid=os.getpid()); connection.close = lambda: None
    rpc = connection.rpc
    def reply(method, params):
        if method == 'config/read':
            return {'config':{**config, 'web_search':effective_search, 'permissions':{'isolated':definition}}}
        if method == 'mcpServerStatus/list':
            return {'data':[{'name':'scidiscovery','tools':{'scid_catalog':{},'scid_describe':{},'scid_call':{}}}]}
        if method == 'mcpServer/tool/call':
            return {'structuredContent':{'management_url':'http://127.0.0.1:8765/sessions/sch_'+'0'*32+'?capability=synthetic'}}
        return rpc(method, params)
    connection.rpc = reply
    monkeypatch.setattr(AppServer, 'launch', lambda *a, **kw: connection)
    permissions = RootPermissions(network_access=False, permission_profile='isolated', profile_definition=json.dumps(definition))
    factory = CodexProgressionFactory(project_root=project, state_root=tmp_path/'state', socket_path=tmp_path/'socket',
        approval_base_url='http://127.0.0.1:8765', command=['synthetic-app-server'], catalog=catalog, permissions=permissions)
    frozen = effective_settings(parse_settings({'debug_disable_task_network':True}), {})
    row = {'config_json':json.dumps({'effective':frozen}), 'host_json':'null', 'checkpoint_json':'{}'}
    if effective_search == 'live':
        with pytest.raises(HostError, match='effective_config_mismatch'):
            factory(row, lambda _: None)
        assert not any(method.startswith('thread/') for method, _ in connection.requests)
        return
    host = factory(row, lambda _: None)
    try:
        start = dict(connection.requests)['thread/start']
        assert start['permissions'] == 'isolated'
        assert start['config']['web_search'] == 'disabled'
        assert 'sandbox' not in start
        host.start_turn('Synthetic transport test; no real model exists.')
        assert dict(connection.requests)['turn/start']['permissions'] == 'isolated'
        # Old loop metadata is readable, but cannot launch under the new deny.
        old = dict(row, config_json=json.dumps({'effective':{'progression':frozen['progression']}}))
        with pytest.raises(HostError, match='task_network_policy_changed'):
            factory(old, lambda _: None)
    finally:
        host.close()
