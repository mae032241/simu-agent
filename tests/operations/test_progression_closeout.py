"""Mechanical sealed handoff survives stopping, reopening and readonly archives."""
import hashlib
import json
from copy import copy

import pytest

from scidiscovery.artifact_agent.approval_ui.progression_render import render_progression
from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService
from tests.operations.test_progression import progression, checkpoint, row
from tests.operations.test_local_worker_contracts import _invoke, _worker, _write_result
from tests.operations.synchronous_archive_fixture import SynchronousFixtureArchive
from tests.operations.test_instance_archive import save_archive, restore_archive


def usage(p, tokens):
    event = dict(method='thread/tokenUsage/updated', params=dict(threadId='native-root',
        tokenUsage=dict(total=dict(inputTokens=tokens, cachedInputTokens=40, outputTokens=10))))
    if p.coordinator.host is None:
        # Model an exact late original-host observation after transport closure.
        p.runtime.scheduler_bindings.observe_progression(instance_id=p.instance,
            expected_host=json.loads(row(p)['host_json']), changes={}, usage_observation=dict(
                params=event['params'], identity={}, root_thread='native-root'))
    else:
        p.coordinator._event(event)


def test_budget_closeout_reads_late_seal_and_usage_without_root_report(progression, monkeypatch):
    p = progression
    p.coordinator.tick()
    host = p.coordinator.host
    root = p.root.__class__(p.facade(host.scheduler_session))
    _invoke(root, 'accepted')
    native_marker = row(p)['host_json']
    native_turn = {key: checkpoint(p)[key] for key in ('phase', 'turn_id')}
    worker = _worker(p.catalog, p.runtime)
    worker.call_tool('worker_open_assignment', {})
    usage(p, 100)
    p.now[0] += 100000
    p.coordinator.tick()
    status = p.root.call_tool('progression_status', {})
    assert status['reason'] == 'budget_exhausted'
    assert status['report'] is None and status['last_report'] is None
    assert status['closeout']['in_flight'][0]['name'] == 'accepted'
    assert not status['closeout']['accepted_tasks_terminal']
    assert status['budget']['stop_snapshot_tokens'] == 110
    assert host.closed and p.coordinator.host is None and row(p)['host_json'] == native_marker
    assert all(checkpoint(p)[key] == value for key, value in native_turn.items())
    with pytest.raises(Exception):
        _invoke(root, 'cannot-replay-after-close')
    bindings = p.runtime.scheduler_bindings
    proposal = bindings.loop_authorization_proposal(instance_id=p.instance, session_key=p.user)
    with pytest.raises(Exception, match='Unresolved native host'):
        bindings.authorize_loop_from_ui(instance_id=p.instance, session_key=p.user,
            confirmation_binding=proposal['confirmation_binding'], objective_name='goal',
            objective_ref=p.runtime.artifacts.get_by_id(bindings.resolve(instance=p.instance,
                namespace='artifact', name='goal')).ref)
    usage(p, 140)
    usage(p, 140)
    _write_result(worker)
    worker.call_tool('worker_submit_result', {})
    host.finish()
    p.coordinator.tick()
    assert p.coordinator.host is None and row(p)['host_json'] == native_marker
    before = row(p)
    monkeypatch.setattr(p.runtime.runs, 'list', lambda **kw: pytest.fail('must not scan instance'))
    status = p.root.call_tool('progression_status', {})
    assert row(p) == before and len(host.prompts) == 1
    # Submission's measured fixture reports another Root 11 and Worker 11;
    # all original-loop late counters remain part of the sealed handoff.
    assert status['usage']['groups']['root']['tokens']['input_tokens'] == 150
    assert status['usage']['groups']['worker']['tokens']['input_tokens'] == 10
    assert status['budget']['observed_tokens'] == 172
    assert status['budget']['stop_snapshot_tokens'] == 110
    assert status['closeout']['goal_assessment'] == 'not_inferred'
    assert status['closeout']['accepted_tasks_terminal']
    item = status['closeout']['tasks'][0]
    assert item['output_artifact_name'] == 'accepted.output'
    original = root.call_tool('run_status', dict(name='accepted', intent='decision'))
    assert item['selected_output'] == original['selected_output']
    assert item['scheduler_signal'] == original['scheduler_signal']
    assert 'native-root' not in json.dumps(status)
    reopened = copy(p.root.facade)
    reopened.bindings = SchedulerBindingService(p.runtime.scheduler_bindings.database_path)
    reopened.bindings.progression_clock = lambda: p.now[0]
    assert reopened.progression_status() == status
    page = render_progression(status, instance_id=p.instance)
    assert '本目标任务成果交接' in page and '首次止损时已观测 Token' in page
    assert 'accepted.output' in page and 'Bounded result.' in page
    # Synchronous fixture proof only; no claim about native writer quiescence.
    p.runtime.runs._synchronous_archive_fixture = True
    archive = SynchronousFixtureArchive(p.runtime)
    blocked_archive = archive.preview(p.instance)
    assert not blocked_archive['ready']
    assert any(item.get('reason') == 'host_quiescence_unconfirmed' for item in blocked_archive['busy'])
    # A modeled matching terminal notification, rather than client exit, now
    # supplies the trusted adapter's exact release proof for the archive fixture.
    bindings.observe_progression(instance_id=p.instance, expected_host=json.loads(native_marker),
        terminal_turn=host.completion, changes=dict(phase='idle', turn_id=None, native_completion='completed'))
    bindings.release_host(instance_id=p.instance, platform_session=host.identity.session_id,
        thread_id=host.identity.thread_id)
    save_archive(archive, p.instance)
    package = archive.root / p.instance
    def digest():
        return {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in package.rglob('*') if path.is_file()}
    sealed = digest()
    archived = archive.archived_model(p.instance).progression_status(p.instance)
    assert archived['historical']
    archived_item = archived['closeout']['tasks'][0]
    assert archived_item['selected_output'] == item['selected_output']
    assert archived_item['scheduler_signal'] == item['scheduler_signal']
    assert archived['closeout']['accepted_tasks_terminal']
    assert archived['budget'] == status['budget'] and digest() == sealed
    restore_archive(archive, p.instance)
    from scidiscovery.artifact_agent.service.progression_read import progression_read_view
    restored = progression_read_view(bindings=p.runtime.scheduler_bindings, runs=p.runtime.runs,
        artifacts=p.runtime.artifacts, operation_catalog=p.runtime.operation_catalog, instance_id=p.instance)
    assert restored['budget'] == status['budget']


def test_failed_and_unresolved_handoff_never_claims_goal_complete(progression):
    p = progression
    p.coordinator.tick()
    root = p.root.__class__(p.facade(p.coordinator.host.scheduler_session))
    _invoke(root, 'failed')
    intent = checkpoint(p)['admissions']['failed']
    value = p.runtime.runs.status(intent['run_id'])
    p.runtime.runs.record_failure(value.run_id, reason='fixture failure', expected_state=value.state,
        expected_last_activity_at=value.last_activity_at, timed_out=False)
    admissions = checkpoint(p)['admissions']
    admissions['uncertain'] = dict(intent, state='prepared', run_id=None)
    p.coordinator._save(dict(admissions=admissions))
    p.root.call_tool('progression_command', dict(command='pause'))
    status = p.root.call_tool('progression_status', {})
    assert status['closeout']['tasks'][0]['state'] == 'failed'
    assert status['closeout']['unresolved'][0]['name'] == 'uncertain'
    assert not status['closeout']['accepted_tasks_terminal']
    assert status['report'] is None and status['closeout']['goal_assessment'] == 'not_inferred'
    assert status['budget']['observed_tokens'] == 0 and status['usage']['coverage'] == 'partial'
    assert status['usage']['groups']['root']['unmeasured_threads'] == 1
    assert checkpoint(p)['usage_records']['native-root']['pending_observation']


def test_acceptance_waits_for_accepted_tasks_without_new_model(tmp_path, monkeypatch):
    import scripts.accept_progression as acceptance
    journey = object.__new__(acceptance.Journey)
    journey.phase_deadline = 10
    journey.logdir = tmp_path / 'logs'
    observed = []
    journey.pump = lambda: observed.append('pump')
    final = dict(closeout=dict(accepted_tasks_terminal=True))
    journey.call = lambda name, args: observed.append(name) or final
    monkeypatch.setattr(acceptance.time, 'monotonic', lambda: 1)
    monkeypatch.setattr(acceptance.time, 'sleep', lambda _: None)
    assert journey.wait_for_accepted_tasks(dict(closeout=dict(accepted_tasks_terminal=False))) == final
    assert observed == ['pump', 'progression_status']
    monkeypatch.setattr(acceptance.time, 'monotonic', lambda: 11)
    with pytest.raises(RuntimeError, match='accepted_tasks_not_quiescent'):
        journey.wait_for_accepted_tasks({})
    assert json.loads((tmp_path / 'summary.json').read_text())['b6_passed'] is False


@pytest.mark.parametrize('missing', ['run', 'binding'])
def test_missing_accepted_identity_is_unresolved_not_empty_success(progression, monkeypatch, missing):
    from scidiscovery.artifact_agent.service.runs import RunNotFound
    from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerNameNotFound
    p = progression
    p.coordinator.tick()
    root = p.root.__class__(p.facade(p.coordinator.host.scheduler_session))
    _invoke(root, 'accepted')
    if missing == 'run':
        def unavailable(*args, **kwargs):
            raise RunNotFound('fixture missing run')
        monkeypatch.setattr(p.runtime.runs, 'status', unavailable)
    else:
        def unavailable(*args, **kwargs):
            raise SchedulerNameNotFound('fixture missing binding')
        monkeypatch.setattr(p.runtime.scheduler_bindings, 'get_binding', unavailable)
    status = p.root.call_tool('progression_status', {})
    assert status['closeout']['unresolved'][0]['name'] == 'accepted'
    assert not status['closeout']['accepted_tasks_terminal']
    assert status['report'] is None


def test_new_root_missing_usage_is_not_hidden_by_historical_root(progression, monkeypatch):
    p = progression
    p.coordinator.tick()
    usage(p, 100)
    assert p.root.call_tool('progression_status', {})['usage']['coverage'] == 'observed'
    # Exact control snapshot after a new host takes over, before its first usage
    # notification. Historical accounting remains unchanged across that boundary.
    snapshot = row(p)
    snapshot['host_json'] = json.dumps(dict(thread_id='new-root', platform_session='new-root'))
    monkeypatch.setattr(p.runtime.scheduler_bindings, 'progression_status', lambda **_: snapshot)
    status = p.root.call_tool('progression_status', {})
    assert status['usage']['coverage'] == status['budget']['token_coverage'] == 'partial'
    assert status['usage']['unmeasured_participants']['root'] == 1
    assert status['budget']['observed_tokens'] == 110
