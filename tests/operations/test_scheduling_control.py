"""Scheduling authority is separate from instance reads and accepted Worker work."""
import json
from pathlib import Path
import sqlite3
import threading

import pytest

from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService, SchedulerInstanceConflict
from scidiscovery.artifact_agent.service.instance_maintenance import InstanceMaintenanceUnavailable
from scidiscovery.artifact_agent.service.instance_archive_records import execution_settings_restore_view, schema
from tests.operations.test_instance_archive import archive_system, artifact, save_archive, restore_archive


@pytest.fixture
def control(tmp_path):
    bindings = SchedulerBindingService(tmp_path / 'database' / 'scheduler-bindings.sqlite3')
    instance = bindings.create_instance_and_bind_session(session_key='first', name='study', title='Study', objective='Original objective')
    bindings.bind_session(session_key='second', instance_id=instance.instance_id)
    return bindings, instance.instance_id


def command(bindings, instance, action, session='first', **kwargs):
    return bindings.progression_command(instance_id=instance, session_key=session, command=action, **kwargs)


def test_legacy_migration_preserves_read_selection_without_starting(control):
    bindings, instance = control
    with bindings._connect() as db:
        db.execute("DELETE FROM scheduler_sessions WHERE session_key='second'")
        db.execute('DROP TABLE scheduler_dispatch_intents')
        db.execute('DROP TABLE scheduler_progression')
        db.execute('CREATE UNIQUE INDEX scheduler_sessions_one_owner ON scheduler_sessions(instance_id)')
        db.execute('PRAGMA user_version=0')
    bindings = SchedulerBindingService(bindings.database_path)
    assert bindings.session_instance(session_key='first') == instance
    bindings.bind_session_by_name(session_key='second', name='study')
    assert bindings.session_instance(session_key='first') == bindings.session_instance(session_key='second') == instance
    assert bindings.progression_status(instance_id=instance)['state'] == 'idle'
    with bindings._connect() as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 1
    SchedulerBindingService(bindings.database_path)
    assert bindings.session_instance(session_key='first') == instance


def test_single_writer_explicit_takeover_pause_and_generation(control):
    bindings, instance = control
    first = command(bindings, instance, 'start')
    before = bindings.progression_status(instance_id=instance, internal=True)
    assert command(bindings, instance, 'start') == first
    assert bindings.progression_status(instance_id=instance, internal=True) == before
    bindings.bind_session_by_name(session_key='second', name='study')
    with pytest.raises(SchedulerInstanceConflict, match='Another scheduler'):
        command(bindings, instance, 'start', 'second')
    with pytest.raises(SchedulerInstanceConflict):
        with bindings.scheduling_guard(instance_id=instance, session_key='second'):
            pytest.fail('reader must not mutate')
    assert command(bindings, instance, 'takeover', 'second')['can_schedule']
    with pytest.raises(SchedulerInstanceConflict):
        with bindings.scheduling_guard(instance_id=instance, session_key='first'):
            pytest.fail('old writer retained authority')
    command(bindings, instance, 'pause', 'second')
    command(bindings, instance, 'resume', 'second')
    with pytest.raises(SchedulerInstanceConflict, match='Stale'):
        with bindings.scheduling_guard(instance_id=instance, session_key='second', expected_generation=before['generation']):
            pytest.fail('old request generation revived')
    assert bindings.session_instance(session_key='first') == instance
    command(bindings, instance, 'stop', 'second')
    assert bindings.progression_status(instance_id=instance)['state'] == 'stopped'


def test_mutation_holds_authority_until_commit(control):
    bindings, instance = control
    entered = threading.Event()
    done = threading.Event()
    def takeover():
        entered.set()
        command(bindings, instance, 'takeover', 'second')
        done.set()
    with bindings.scheduling_guard(instance_id=instance, session_key='first'):
        worker = threading.Thread(target=takeover)
        worker.start()
        assert entered.wait(2)
        assert not done.wait(.1)
    worker.join(3)
    assert done.is_set()
    assert bindings.progression_status(instance_id=instance, session_key='second')['can_schedule']


def test_maintenance_blocks_controls_and_selection(control):
    bindings, instance = control
    gate = bindings.control_maintenance
    with gate.exclusive(instance):
        gate.begin(instance, 'job', 'archive')
    with pytest.raises(InstanceMaintenanceUnavailable):
        command(bindings, instance, 'start')
    with pytest.raises(InstanceMaintenanceUnavailable):
        bindings.bind_session_by_name(session_key='third', name='study')
    assert bindings.progression_status(instance_id=instance)['state'] == 'idle'


def test_dispatch_intent_does_not_survive_takeover(control):
    bindings, instance = control
    with bindings.scheduling_guard(instance_id=instance, session_key='first') as generation:
        bindings.record_dispatch_intent(instance_id=instance, run_id='run', session_key='first')
        bindings.require_dispatch_intent(instance_id=instance, run_id='run', session_key='first', generation=generation)
    command(bindings, instance, 'takeover', 'second')
    with bindings.scheduling_guard(instance_id=instance, session_key='second') as generation:
        with pytest.raises(SchedulerInstanceConflict, match='Native start state is unknown'):
            bindings.require_dispatch_intent(instance_id=instance, run_id='run', session_key='second', generation=generation)


def test_pending_background_exact_objective_snapshot_and_trusted_activation(archive_system):
    runtime, archive, instance, _ = archive_system
    bindings = runtime.scheduler_bindings
    user = 'sch_' + 'a'*32
    goal = artifact(runtime, instance, 'exact.goal')
    assert command(bindings, instance, 'start', user, mode='background', objective_name='exact.goal', objective_ref=goal.ref)['reason'] == 'runtime_unavailable'
    pending = bindings.progression_status(instance_id=instance, internal=True)
    assert pending['owner_session'] is None
    with pytest.raises(SchedulerInstanceConflict):
        with bindings.scheduling_guard(instance_id=instance, session_key=user):
            pytest.fail('pending host must not schedule')
    with pytest.raises(ValueError):
        bindings.activate_host(instance_id=instance, source_session=user, scheduler_session="actual-root", platform_session='real', thread_id='different', expected_generation=pending['generation'])
    active = bindings.activate_host(instance_id=instance, source_session=user, scheduler_session="actual-root", platform_session='actual-root', thread_id='actual-root', expected_generation=pending['generation'])
    assert bindings.session_instance(session_key=user) == bindings.session_instance(session_key='actual-root') == instance
    assert active['generation'] > pending['generation']
    assert json.loads(active['objective_ref_json']) == goal.ref.model_dump(mode='json')
    bindings.checkpoint_progression(instance_id=instance, session_key='actual-root', expected_generation=active['generation'], checkpoint={'consumed': 27})
    command(bindings, instance, 'pause', user)
    paused_checkpoint = json.loads(bindings.progression_status(instance_id=instance, internal=True)['checkpoint_json'])
    assert not archive.preview(instance)['ready']
    bindings.release_host(instance_id=instance, platform_session='actual-root', thread_id='actual-root')
    save_archive(archive, instance)
    archived_status = archive.archived_model(instance).overview(instance)['progression']
    assert archived_status['historical'] and not archived_status['can_schedule']
    assert archived_status['notifications']['current_id'] is None
    assert archived_status['notifications']['items'] == paused_checkpoint['notices']
    restore_archive(archive, instance)
    restored = bindings.progression_status(instance_id=instance, internal=True)
    assert (restored['state'], restored['reason'], restored['owner_session'], restored['host_json']) == ('paused', 'archive_restored', None, None)
    assert json.loads(restored['checkpoint_json']) == paused_checkpoint
    assert paused_checkpoint['consumed'] == 27
    assert bindings.progression_status(instance_id=instance)['notifications']['current_id'] is None
    assert restored['objective_ref_json'] == active['objective_ref_json']
    assert restored['config_json'] == active['config_json']
    assert bindings.session_instance(session_key=user) is None
    assert bindings.session_instance(session_key='actual-root') is None


def test_active_disconnected_writer_still_blocks_archive(archive_system):
    runtime, archive, instance, _ = archive_system
    bindings = runtime.scheduler_bindings
    user = 'sch_'+'a'*32
    command(bindings, instance, 'start', user)
    bindings.disconnect_client(session_key=user)
    assert not archive.preview(instance)['ready']
    command(bindings, instance, 'pause', user)
    assert archive.preview(instance)['ready']


def test_old_archive_schema_projects_new_tables_without_restoring_authority(control):
    bindings, instance = control
    with bindings._connect() as db:
        db.execute('DROP TABLE scheduler_dispatch_intents')
        db.execute('DROP TABLE scheduler_progression')
        db.execute('DELETE FROM scheduler_sessions WHERE session_key=?', ('second',))
        db.execute('CREATE UNIQUE INDEX scheduler_sessions_one_owner ON scheduler_sessions(instance_id)')
        db.execute('PRAGMA user_version=0')
        data = {'schema': schema(db), 'tables': {'scheduler_instances': [], 'scheduler_sessions': []}}
    projected = execution_settings_restore_view(data)
    assert projected['schema']['user_version'] == 1
    assert projected['tables']['scheduler_progression'] == []
    assert 'scheduler_sessions_one_owner' not in {x['name'] for x in projected['schema']['objects']}
    assert data['schema']['user_version'] == 0


def test_paused_router_mutations_block_while_reads_and_accepted_worker_complete(tmp_path):
    from pathlib import Path
    from blind_csv_plugin.contracts import CSV_SCHEMA_PROBE
    from tests.operations.test_unified_mcp import queued, call, result
    _, runtime, root, gateway, profile = queued(tmp_path)
    result(call(gateway, 'worker_attach', {'name': 'observation', 'thread_id': 'accepted-child'}))
    child = dict(child='accepted-child', profile=profile)
    opened = result(call(gateway, 'worker_open_assignment', **child))
    result(call(gateway, 'progression_command', {'command': 'pause'}))
    # An acknowledged existing attachment may reconnect with identical coordinates.
    result(call(gateway, 'worker_attach', {'name': 'observation', 'thread_id': 'accepted-child'}))
    for name, surface in [('artifact_ingest_text', 'research'), ('scientific_current_select', 'research'),
                          ('operation_invoke', 'research'), ('run_record_failure', 'research'),
                          ('execution_start', 'execution'), ('execution_cancel', 'execution'),
                          ('execution_collect', 'execution'), ('execution_outputs', 'execution')]:
        with pytest.raises(SchedulerInstanceConflict):
            root.call_tool(name, {}, surface=surface)
    assert result(call(gateway, 'instance_current'))['name']
    assert result(call(gateway, 'run_status', {'name': 'observation', 'intent': 'status'}))['state'] == 'running'
    structure = result(call(gateway, 'worker_csv_summarize', **child))
    Path(opened['output_directory'], 'result.json').write_text(json.dumps({
        'schema_version': 1, 'handoff': {'verdict': 'pass', 'summary': 'Accepted work completed while Root paused.'},
        'payload': {'schema_probe': CSV_SCHEMA_PROBE, 'structure': structure,
                    'interpretation': 'The mean is two.', 'limitations': ['Two rows do not establish causality.']}}))
    assert result(call(gateway, 'worker_submit_result', **child))['state'] == 'completed'
    assert result(call(gateway, 'run_status', {'name': 'observation', 'intent': 'status'}))['state'] == 'completed'


def test_gateway_rejects_unattached_old_intent_after_resume(tmp_path):
    from tests.operations.test_unified_mcp import queued, call, result
    _, runtime, root, gateway, _ = queued(tmp_path)
    result(call(gateway, 'progression_command', {'command': 'pause'}))
    assert 'error' in call(gateway, 'worker_attach', {'name': 'observation', 'thread_id': 'late-child'})
    result(call(gateway, 'progression_command', {'command': 'resume'}))
    rejected = call(gateway, 'worker_attach', {'name': 'observation', 'thread_id': 'late-child'})
    assert 'Native start state is unknown' in rejected['error']['message']
    assert result(call(gateway, 'run_status', {'name': 'observation', 'intent': 'status'}))['state'] == 'queued'


def test_client_pause_keeps_instance_readable_and_offline_cleanup_retains_goal(tmp_path):
    from tests.operations.test_local_worker_contracts import _system
    _, runtime, instance, root = _system(tmp_path)
    bindings = runtime.scheduler_bindings
    bindings.bind_session(session_key='user', instance_id=instance.instance_id)
    bindings.register_client(session_key='user')
    root.facade.session_key = 'user'
    root.call_tool('progression_command', {'command': 'start'})
    bindings.set_client_enabled(session_key='user', enabled=False, expected=True)
    current = root.call_tool('instance_current', {})
    assert current['name'] == instance.name and current['scheduling']['state'] == 'paused'
    bindings.disconnect_client(session_key='user')
    assert bindings.clear_offline_clients() == 1
    assert bindings.progression_status(instance_id=instance.instance_id)['state'] == 'paused'


def test_interactive_config_changes_apply_at_next_run_boundary(control):
    bindings, instance = control
    command(bindings, instance, 'start')
    bindings.save_agent_settings(instance, {}, expected_revision=0, maintenance=bindings.control_maintenance)
    with bindings.scheduling_guard(instance_id=instance, session_key='first'):
        pass



@pytest.mark.process_e2e
def test_other_process_cannot_take_over_an_inflight_mutation(control):
    import select
    import subprocess
    import sys
    bindings, instance = control
    code = '''import sys
sys.path.insert(0, sys.argv[3])
from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService
bindings = SchedulerBindingService(sys.argv[1])
print('ready', flush=True)
bindings.progression_command(instance_id=sys.argv[2], session_key='second', command='takeover')
print('taken', flush=True)
'''
    process = None
    try:
        with bindings.scheduling_guard(instance_id=instance, session_key='first'):
            process = subprocess.Popen([sys.executable, '-c', code, str(bindings.database_path), instance, str(Path(__file__).resolve().parents[2] / 'src')], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            assert select.select([process.stdout], [], [], 10)[0]
            assert process.stdout.readline().strip() == 'ready'
            assert not select.select([process.stdout], [], [], .1)[0]
        output, error = process.communicate(timeout=10)
        assert process.returncode == 0, error
        assert output.strip() == 'taken'
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.communicate(timeout=5)
    assert bindings.progression_status(instance_id=instance, session_key='second')['can_schedule']


def test_cli_uses_existing_ui_selection_and_shared_controls(archive_system, monkeypatch, capsys):
    from scidiscovery.artifact_agent.interfaces import cli
    runtime, _, instance, _ = archive_system
    monkeypatch.setattr(cli, 'read_secret_file', lambda *args, **kwargs: b'a'*32)
    monkeypatch.setattr(cli, 'open_runtime', lambda **kwargs: runtime)
    key = 'sch_'+'a'*32
    assert cli.main(['--session', key, 'progression', 'start']) == 0
    assert json.loads(capsys.readouterr().out)['state'] == 'active'
    assert cli.main(['--session', key, 'progression', 'pause']) == 0
    assert json.loads(capsys.readouterr().out)['state'] == 'paused'
    assert cli.main(['--session', 'unselected', 'progression', 'takeover']) == 2
    assert 'management UI' in capsys.readouterr().err
    assert runtime.scheduler_bindings.progression_status(instance_id=instance)['state'] == 'paused'


@pytest.fixture(params=['user_text', 'projected_objective'])
def anchored_goal(tmp_path, request):
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    from scidiscovery.artifact_agent.transforms import project_research_objective
    from scidiscovery.general_science_plugin import PLUGIN
    from tests.operations.test_general_transform_operations import _intake
    from tests.operations.test_local_worker_contracts import _system
    _, runtime, instance, root = _system(tmp_path)
    bindings = runtime.scheduler_bindings
    bindings.bind_session(session_key='goal-user', instance_id=instance.instance_id)
    root.facade.session_key = 'goal-user'
    root.call_tool('artifact_ingest_text', {'name': 'other.goal', 'text': 'A different exact goal.'})
    if request.param == 'user_text':
        root.call_tool('artifact_ingest_text', {'name': 'goal', 'text': 'Investigate the supplied curve within the stated range.'})
    else:
        foundation = _intake().scientific_foundation.model_dump(mode='json')
        foundation['objective_contract'] = {
            'objective_key': 'goal', 'intent': 'mechanism_discrimination', 'statement': foundation['objective'],
            'closure_requirements': [{'requirement_key': 'comparison', 'description': 'Compare supplied cases.',
                'requirement_type': 'comparison_present', 'comparison_purposes': ['mechanism_separation']}]}
        raw = project_research_objective(json.dumps(foundation).encode())
        output = next(operation for operation in PLUGIN.operations if operation.operation_id == 'science.objective.project.v1').outputs[0]
        goal = runtime.artifacts.register(raw, ArtifactRegistration(kind=output.kind, schema_id=output.schema_id,
            payload_schema_version=1, media_type='application/json', creator=runtime.actor), idempotency_key='goal')
        assert (goal.kind, goal.schema_id) == ('research_objective', 'scidiscovery.research-objective.v1')
        bindings.bind(instance=instance.instance_id, namespace='artifact', name='goal', object_id=goal.artifact_id)
    return runtime, instance.instance_id, root


def test_public_goal_start_accepts_original_text_and_projected_objective(anchored_goal):
    runtime, instance, root = anchored_goal
    bindings = runtime.scheduler_bindings
    request = {'command': 'start', 'mode': 'background', 'objective_name': 'goal'}
    # Intake's initial interactive writer is not already a scientific goal.
    assert root.call_tool('progression_command', request)['state'] == 'pending'
    pending = bindings.progression_status(instance_id=instance, internal=True)
    assert root.call_tool('progression_command', request)['state'] == 'pending'
    bindings.activate_host(instance_id=instance, source_session='goal-user', scheduler_session='host-proxy',
        platform_session='actual-root', thread_id='actual-root', expected_generation=pending['generation'])
    active = bindings.progression_status(instance_id=instance, internal=True)
    assert root.call_tool('progression_command', request)['state'] == 'active'
    assert bindings.progression_status(instance_id=instance, internal=True) == active
    with pytest.raises(SchedulerInstanceConflict, match='Another scheduler'):
        root.call_tool('progression_command', {**request, 'objective_name': 'other.goal'})
    for state, action in [('paused', 'pause'), ('stopped', 'stop')]:
        root.call_tool('progression_command', {'command': action})
        frozen = bindings.progression_status(instance_id=instance, internal=True)
        assert root.call_tool('progression_command', request)['state'] == state
        assert bindings.progression_status(instance_id=instance, internal=True) == frozen
    with runtime.runs._connect() as connection:
        assert connection.execute('SELECT COUNT(*) FROM runs').fetchone()[0] == 0


def test_goal_ui_uses_the_same_anchor_contract(anchored_goal):
    from types import SimpleNamespace
    from scidiscovery.artifact_agent.approval_ui import ApprovalUI
    from scidiscovery.artifact_agent.service.instance_management import issue_instance_management_capability
    from tests.operations.test_m6a_direct_instance_management import _request
    runtime, instance, _ = anchored_goal
    secret = b's'*32
    ui = ApprovalUI(runtime.approvals, bindings=runtime.scheduler_bindings, instance_management_secret=secret)
    ui.read_model = SimpleNamespace(artifacts=runtime.artifacts)
    base = ui.start()
    try:
        capability = issue_instance_management_capability(session_key='goal-user', secret=secret)
        status, _, _ = _request(base, 'POST', '/instances/progression', form={
            'capability': capability, 'csrf': ui.session_id, 'command': 'start', 'mode': 'background', 'objective_name': 'goal'})
        assert status == 303
        assert runtime.scheduler_bindings.progression_status(instance_id=instance)['state'] == 'pending'
    finally:
        ui.stop()


def test_confirmed_old_host_release_after_interactive_takeover(anchored_goal):
    runtime, instance, root = anchored_goal
    bindings = runtime.scheduler_bindings
    root.call_tool('progression_command', {'command': 'start', 'mode': 'background', 'objective_name': 'goal'})
    pending = bindings.progression_status(instance_id=instance, internal=True)
    bindings.activate_host(instance_id=instance, source_session='goal-user', scheduler_session='host-proxy',
        platform_session='actual-root', thread_id='actual-root', expected_generation=pending['generation'])
    with pytest.raises(SchedulerInstanceConflict):
        bindings.release_host(instance_id=instance, platform_session='actual-root', thread_id='actual-root')
    root.call_tool('progression_command', {'command': 'takeover'})
    active = bindings.progression_status(instance_id=instance, internal=True)
    assert active['host_json'] is not None
    bindings.release_host(instance_id=instance, platform_session='actual-root', thread_id='actual-root')
    restored = bindings.progression_status(instance_id=instance, internal=True)
    assert restored['state'] == 'active' and restored['host_json'] is None
    assert restored['generation'] == active['generation']
    with bindings.scheduling_guard(instance_id=instance, session_key='goal-user'):
        pass
