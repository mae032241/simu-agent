"""Assist through real task admission, native receipts and durable recovery."""
import json

import pytest

from tests.operations.test_progression import progression, unmanaged_progression, row, checkpoint
from tests.operations.test_scientific_progress import active, finish, assess, request, INTENT
from tests.operations.test_progress_shadow import native_delivery


def configure(p, **limits):
    bindings = p.runtime.scheduler_bindings
    settings = bindings.global_settings
    bindings.global_settings = settings.model_copy(update=dict(progression=settings.progression.model_copy(
        update=dict(progress_mode='assist', **limits))))
    p.root.call_tool('progression_command', dict(command='pause'))
    from tests.operations.research_loop_fixtures import authorize_loop
    authorize_loop(p.runtime, p.instance, p.user, 'goal')
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='goal'))


def trigger(p, root, outcome=None):
    for index in range(3):
        name = f'renamed-{index}'
        finish(p, root, name, {**INTENT, 'target': f'Paraphrased target {index}'})
        if outcome:
            assess(root, name, outcome=outcome, evidence=outcome != 'advance')
        native_delivery(p, root, name)
    p.coordinator.host.finish()


def notice(p):
    return p.root.call_tool('progression_status', {})['progress_shadow']


def next_turn(p):
    p.now[0] += 6
    p.coordinator.tick()










def finish_changed(p, root, name):
    from tests.operations.test_local_worker_contracts import _worker, _write_result
    root.call_tool('operation_invoke', request(name))
    worker = _worker(p.catalog, p.runtime)
    worker.call_tool('worker_open_assignment', {})
    _write_result(worker)
    path = worker._workspace.output_directory / 'result.json'
    value = json.loads(path.read_text())
    value['payload']['interpretation'] = 'The sealed analysis excludes a claimed causal mechanism; two observations cannot identify it.'
    path.write_text(json.dumps(value))
    worker.call_tool('worker_submit_result', {})






@pytest.mark.parametrize('mode', ['shadow', 'off'])
def test_non_assist_modes_never_intercept_ordinary_admission(progression, mode):
    p = progression
    if mode == 'off':
        bindings = p.runtime.scheduler_bindings
        settings = bindings.global_settings
        bindings.global_settings = settings.model_copy(update=dict(progression=settings.progression.model_copy(
            update=dict(progress_mode=mode))))
        p.root.call_tool('progression_command', dict(command='pause'))
        from tests.operations.research_loop_fixtures import authorize_loop
        authorize_loop(p.runtime, p.instance, p.user, 'goal')
        p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='goal'))
    root = active(p)
    trigger(p, root)
    next_turn(p)
    finish(p, root, 'ordinary-next')
    assert row(p)['state'] == 'active'
    assert notice(p)['mode'] == mode


def correction_state(p):
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    return p.runtime.scheduler_bindings.progress_shadow(instance_id=p.instance,
        objective_ref=ArtifactRef.model_validate_json(row(p)['objective_ref_json']))


def historical_goal(p, *, pending=False):
    """Interactive science precedes this goal's first background command."""
    p.root.call_tool('progression_command', dict(command='takeover'))
    p.root.call_tool('artifact_ingest_text', dict(name='history-goal', text='Explain this exact historical observation.'))
    p.root.call_tool('progression_command', dict(command='pause'))
    p.root.call_tool('progression_command', dict(command='start', mode='interactive', objective_name='history-goal'))
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    from tests.operations.test_local_worker_contracts import RAW, _worker, _write_result
    source = p.runtime.artifacts.register(RAW, ArtifactRegistration(kind='blind_csv_input',
        schema_id='blind.opaque.v1', payload_schema_version=1, media_type='text/csv', creator=p.runtime.actor,
        parent_refs=(ArtifactRef.model_validate_json(row(p)['objective_ref_json']),)), idempotency_key='history-source')
    p.runtime.scheduler_bindings.bind(instance=p.instance, namespace='artifact', name='history-source',
        object_id=source.artifact_id)
    def invoke(name, intent):
        p.root.call_tool('operation_invoke', dict(request(name, intent),
            inputs=[dict(port='source_table', artifact_names=['history-source'])]))
    for index in range(9):
        invoke(f'history-{index}', None)
        worker = _worker(p.catalog, p.runtime)
        worker.call_tool('worker_open_assignment', {})
        _write_result(worker)
        worker.call_tool('worker_submit_result', {})
    bindings = p.runtime.scheduler_bindings
    settings = bindings.global_settings
    bindings.global_settings = settings.model_copy(update=dict(progression=settings.progression.model_copy(
        update=dict(progress_mode='assist'))))
    p.root.call_tool('progression_command', dict(command='pause'))
    from tests.operations.research_loop_fixtures import authorize_loop
    authorize_loop(p.runtime, p.instance, p.user, 'history-goal')
    if pending:
        p.root.call_tool('progression_command', dict(command='start', mode='interactive', objective_name='history-goal'))
        invoke('already-running', INTENT)
        worker = _worker(p.catalog, p.runtime)
        worker.call_tool('worker_open_assignment', {})
        p.root.call_tool('progression_command', dict(command='pause'))
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='history-goal'))
    return worker if pending else None


def test_prestart_running_completion_before_host_is_observed_and_background_bytes_stay_known(unmanaged_progression):
    from tests.operations.test_local_worker_contracts import _write_result
    p = unmanaged_progression
    worker = historical_goal(p, pending=True)
    scope = correction_state(p)['observation_scope']
    assert len(scope['initial_observed']) == 1 and scope['max_observed_tasks'] == 11
    _write_result(worker)
    worker.call_tool('worker_submit_result', {})  # after start, before host attaches
    root = active(p)
    assess(root, 'already-running', outcome='advance')
    p.coordinator.host.finish()
    next_turn(p)
    counts = correction_state(p)['counts']
    assert counts['consumed'] == 1 and counts['coverage_gap'] == 0
    assert counts['unchanged_evidence'] == 1  # same bytes as pre-start background
    assert correction_state(p)['observation_scope'] == scope


def test_background_scope_and_seen_evidence_survive_actual_archive(unmanaged_progression):
    from tests.operations.synchronous_archive_fixture import SynchronousFixtureArchive
    from tests.operations.test_instance_archive import save_archive, restore_archive
    from scidiscovery.artifact_agent.service.progression_read import progression_read_view
    p = unmanaged_progression
    historical_goal(p)
    active(p)
    p.coordinator.host.finish()
    p.root.call_tool('progression_command', dict(command='pause'))
    p.coordinator.tick()
    expected = p.root.call_tool('progression_status', {})['progress_shadow']
    scope = correction_state(p)['observation_scope']
    p.runtime.runs._synchronous_archive_fixture = True
    archive = SynchronousFixtureArchive(p.runtime)
    save_archive(archive, p.instance)
    assert archive.archived_model(p.instance).progression_status(p.instance)['progress_shadow'] == expected
    restore_archive(archive, p.instance)
    restored = progression_read_view(bindings=p.runtime.scheduler_bindings, runs=p.runtime.runs,
        artifacts=p.runtime.artifacts, operation_catalog=p.catalog, instance_id=p.instance)
    assert restored['progress_shadow'] == expected
    assert correction_state(p)['observation_scope'] == scope
