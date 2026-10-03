"""Finite fake-clock delivery checks with real scientific receipts/public acks."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import acceptance_native_cases as native
from scripts.b6_evidence import batch_payloads, batch_scientific_facts, write
from tests.operations.test_experiment_material_delivery import (
    catalog, staged_experiment, prediction_request, comparison_request, submit_staged_report)
from tests.operations.test_progression import Host
from tests.operations.research_loop_fixtures import authorize_loop, measured_fixture_usage


@pytest.fixture
def delivery(staged_experiment, monkeypatch):
    from scidiscovery.artifact_agent.service.progression import ProgressionCoordinator
    f = staged_experiment
    bindings = f.runtime.scheduler_bindings
    user = 'sch_'+'a'*32
    bindings.bind_session(session_key=user, instance_id=f.instance.instance_id)
    f.root.facade.session_key = user
    f.root.call_tool('progression_command', dict(command='pause'))
    authorize_loop(f.runtime, f.instance.instance_id, user, 'objective')
    f.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='objective'))
    now = [0.0]
    def facade(session):
        from copy import copy
        result = copy(f.root.facade)
        result.session_key = session
        return result
    coordinator = ProgressionCoordinator(runtime=f.runtime, host_factory=Host, facade_factory=facade, clock=lambda:now[0])
    coordinator.tick()
    f.root.facade.session_key = coordinator.host.scheduler_session
    monkeypatch.setattr(native.time, 'monotonic', lambda:now[0])
    material = Path(__file__).resolve().parents[2]/'scripts/acceptance/fixtures/hourly_loop_memory/materials.json'
    spec = dict(version=1, materials_file=str(material), materials_sha256=hashlib.sha256(material.read_bytes()).hexdigest())
    journey = object.__new__(native.NativeCaseJourney)
    journey.root, journey.instance = f.runtime.state_root.parent, f.instance.instance_id
    journey.logdir = journey.root/'evidence/logs'
    journey.logdir.mkdir(parents=True)
    journey.case_config = dict(batch_delivery=spec, max_observed_runs=8)
    journey.case_started_at = 0
    journey.row = lambda:bindings.progression_status(instance_id=journey.instance, internal=True)
    journey.call = f.root.call_tool
    loop = json.loads(journey.row()['checkpoint_json'])['current_loop_id']
    write(journey.logdir.parent/'loop-authorization.json', dict(id=loop, objective_name='objective'))
    yield SimpleNamespace(f=f, journey=journey, now=now, coordinator=coordinator,
        payloads=batch_payloads(spec), spec=spec, bindings=bindings)
    coordinator.close()


def completed_design(d, name='first'):
    author = d.f.start(name)
    stage = author.worker.call_tool('worker_experiment_stage', dict(stage='design', conclusion='Retain actual first-round scope.'))
    measured_fixture_usage(author.worker)
    submit_staged_report(author, [stage['reference']])
    assert d.f.runtime.runs.status(author.run_id).state == 'completed'
    return author


def messages(d):
    return json.loads(d.journey.row()['checkpoint_json']).get('messages', [])


def safe_fixture_rotation(d):
    """Synthetic terminal events, followed by real fence/attach CAS services."""
    control = d.journey.row()
    old = json.loads(control['host_json'])
    d.coordinator.host.finish()
    cp = json.loads(control['checkpoint_json'])
    records = cp['usage_records']
    records[old['thread_id']]['scheduler_session'] = control['owner_session']
    d.bindings.observe_progression(instance_id=d.journey.instance, expected_host=old,
        changes=dict(usage_records=records, phase='idle', turn_id=None, native_completion='completed',
            rotation_boundary=dict(checked=2, unchecked=0, unknown=0, reasons=[])))
    prepared = d.bindings.prepare_host_rotation(instance_id=d.journey.instance, expected_host=old,
        expected_generation=control['generation'], terminal_turn=d.coordinator.host.completion)
    d.journey.deliver_batches(prepared)
    new_session = 'sch_'+'c'*32
    active = d.bindings.complete_host_rotation(instance_id=d.journey.instance, expected_host=old,
        expected_generation=prepared['generation'], scheduler_session=new_session,
        platform_session='new-root', thread_id='new-root')
    d.f.root.facade.session_key = new_session
    return prepared, active


def test_release_uses_real_completed_original_public_ack_and_monotonic_threshold(delivery):
    d = delivery
    author = d.f.start('first')
    stage = author.worker.call_tool('worker_experiment_stage', dict(stage='design', conclusion='Preview.'))
    d.now[0] = 1500
    d.journey.deliver_batches(d.journey.row())
    assert messages(d) == []  # a sealed running stage is not a first final result
    measured_fixture_usage(author.worker)
    submit_staged_report(author, [stage['reference']])
    d.now[0] = 1499
    d.journey.deliver_batches(d.journey.row())
    assert messages(d) == []
    d.now[0] = 1500
    prompts = len(d.coordinator.host.prompts)
    d.journey.deliver_batches(d.journey.row())
    ack = messages(d)
    assert len(ack) == 1 and ack[0]['name'] == 'acceptance.p6s.A_discrimination'
    assert d.f.runtime.artifacts.read(d.f.runtime.artifacts.get_by_id(ack[0]['artifact_ref']['artifact_id']).ref).decode() == d.payloads[1]['text']
    d.journey.deliver_batches(d.journey.row())
    assert messages(d) == ack and len(d.coordinator.host.prompts) == prompts
    assert 'A_validation' not in native.case_objective(dict(text=d.payloads[0]['text']))


def test_running_prediction_then_completed_adopted_comparison_requires_actual_rotation(delivery):
    d = delivery
    completed_design(d)
    d.now[0] = 1500
    d.journey.deliver_batches(d.journey.row())
    declaration_author = d.f.start('prediction', ('acceptance.p6s.A_discrimination',))
    declaration = declaration_author.worker.call_tool('worker_experiment_stage',
        prediction_request(declaration_author.aliases['acceptance.p6s.A_discrimination']))
    d.now[0] = 3299
    d.journey.deliver_batches(d.journey.row())
    assert len(messages(d)) == 1
    d.now[0] = 3300
    d.journey.deliver_batches(d.journey.row())
    assert len(messages(d)) == 2
    assert d.f.runtime.runs.status(declaration_author.run_id).state == 'running'
    measured_fixture_usage(declaration_author.worker)
    submit_staged_report(declaration_author, [declaration['reference']])
    assert d.f.runtime.runs.status(declaration_author.run_id).state == 'completed'
    consumer = d.f.start('comparison', (declaration['artifact_name'], 'acceptance.p6s.A_validation'))
    comparison = consumer.worker.call_tool('worker_experiment_stage',
        comparison_request(consumer.aliases[declaration['artifact_name']], consumer.aliases['acceptance.p6s.A_validation'], status='fail'))
    d.now[0] = 5100
    d.journey.deliver_batches(d.journey.row())
    assert len(messages(d)) == 2  # running comparison is a preview
    measured_fixture_usage(consumer.worker)
    submit_staged_report(consumer, [comparison['reference']])
    assert d.f.runtime.runs.status(consumer.run_id).state == 'completed', d.f.runtime.runs.status(consumer.run_id).reason
    d.journey.deliver_batches(d.journey.row())
    assert len(messages(d)) == 2  # completed negative comparison does not fake rotation
    facts = batch_scientific_facts(d.journey.root, d.journey.row(), max_runs=8,
        discrimination=messages(d)[0]['artifact_ref'], validation=messages(d)[1]['artifact_ref'],
        prediction=d.journey._batch_prediction)
    output = d.f.runtime.runs.status(consumer.run_id).output_ref
    assert [v['run_id'] for v in facts['comparisons']] == [consumer.run_id], d.f.runtime.artifacts.read(output).decode()
    prepared, active = safe_fixture_rotation(d)
    assert prepared['owner_session'] is None
    d.journey.deliver_batches(active)
    assert len(messages(d)) == 3
    proof = d.journey._batch_rotation_proof
    assert proof['old'] != proof['new'] and proof['scope']['loop'] == json.loads(active['checkpoint_json'])['current_loop_id']
    assert messages(d)[2]['fingerprint'] == hashlib.sha256((d.payloads[3]['text']+'\n'+native.NEUTRAL_CHANGED_CONDITION_QUESTION).encode()).hexdigest()
    d.journey.deliver_batches(d.journey.row())
    observation = json.loads((d.journey.logdir.parent/'batch-delivery-observation.json').read_text())
    assert observation['status']=='complete' and len(observation['releases'])==3
    assert observation['releases'][-1]['rotation']==proof and observation['science_passed'] is False


def test_existing_message_ack_is_reused_and_wrong_alias_does_not_precommit(delivery):
    d = delivery
    completed_design(d)
    d.now[0] = 1500
    d.journey.deliver_batches(d.journey.row())
    original = messages(d)
    # A new observer can reuse the control's saved message; it cannot reconstruct
    # a lost post-model precommit/rotation observation or claim host recovery.
    del d.journey._delivery_scope
    author = d.f.start('wrong-condition', ('condition',))
    author.worker.call_tool('worker_experiment_stage', prediction_request(author.aliases['condition']))
    d.now[0] = 3300
    d.journey.deliver_batches(d.journey.row())
    assert messages(d) == original and not hasattr(d.journey, '_batch_prediction')


def test_multiple_precommitments_and_incomplete_receipt_coverage_remain_unknown(delivery):
    d = delivery
    completed_design(d)
    d.now[0] = 1500
    d.journey.deliver_batches(d.journey.row())
    author = d.f.start('ambiguous', ('acceptance.p6s.A_discrimination',))
    request = prediction_request(author.aliases['acceptance.p6s.A_discrimination'])
    author.worker.call_tool('worker_experiment_stage', request)
    request['conclusion'] = 'A distinct scientific revision.'
    author.worker.call_tool('worker_experiment_stage', request)
    d.now[0] = 3300
    d.journey.deliver_batches(d.journey.row())
    assert len(messages(d)) == 1 and not hasattr(d.journey, '_batch_prediction')
    d.journey.case_config['max_observed_runs'] = 1
    with pytest.raises(ValueError, match='coverage_limit'):
        d.journey.deliver_batches(d.journey.row())
    assert len(messages(d)) == 1


@pytest.mark.parametrize('reply_saved', [True, False, 'unreadable'])
def test_lost_reply_reads_exact_ack_and_unknown_never_replays(delivery, reply_saved):
    d = delivery
    completed_design(d)
    d.now[0] = 1500
    calls = []
    original_row = d.journey.row
    control = original_row()
    def lost(name, args):
        calls.append((name, args))
        if reply_saved:
            d.f.root.call_tool(name, args)
        if reply_saved == 'unreadable':
            def unavailable():
                raise TimeoutError('ack read timeout')
            d.journey.row = unavailable
        raise TimeoutError('lost reply')
    d.journey.call = lost
    if reply_saved is True:
        d.journey.deliver_batches(d.journey.row())
        d.journey.deliver_batches(d.journey.row())
        assert len(messages(d)) == 1
    else:
        with pytest.raises(RuntimeError, match='submission_unknown'):
            d.journey.deliver_batches(control)
        with pytest.raises(RuntimeError, match='submission_unknown'):
            d.journey.deliver_batches(control)
        d.journey.row = original_row
        assert len(messages(d)) == (1 if reply_saved == 'unreadable' else 0)
    assert len(calls) == 1


@pytest.mark.parametrize('missing', ['not_run', 'not_adopted', 'wrong_observation', 'wrong_prediction'])
def test_completed_comparison_requires_exact_observation_prediction_and_adoption(delivery, missing):
    d = delivery
    completed_design(d)
    d.now[0] = 1500
    d.journey.deliver_batches(d.journey.row())
    author = d.f.start('declaration', ('acceptance.p6s.A_discrimination', 'condition'))
    declared = author.worker.call_tool('worker_experiment_stage', prediction_request(author.aliases['acceptance.p6s.A_discrimination']))
    d.now[0] = 3300
    d.journey.deliver_batches(d.journey.row())
    if missing == 'wrong_prediction':
        declared = author.worker.call_tool('worker_experiment_stage', prediction_request(author.aliases['condition']))
    measured_fixture_usage(author.worker)
    submit_staged_report(author, [declared['reference']])
    consumer = d.f.start('comparison', (declared['artifact_name'], 'acceptance.p6s.A_validation', 'observation'))
    observation = consumer.aliases['observation' if missing == 'wrong_observation' else 'acceptance.p6s.A_validation']
    compared = consumer.worker.call_tool('worker_experiment_stage', comparison_request(
        consumer.aliases[declared['artifact_name']], observation, status='not_run' if missing=='not_run' else 'fail'))
    measured_fixture_usage(consumer.worker)
    submit_staged_report(consumer, [] if missing=='not_adopted' else [compared['reference']])
    assert d.f.runtime.runs.status(consumer.run_id).state == 'completed'
    d.now[0] = 5100
    _, active = safe_fixture_rotation(d)
    d.journey.deliver_batches(active)
    assert len(messages(d)) == 2


def test_native_poll_calls_delivery_after_budget_and_closeout_records_omissions(delivery):
    d = delivery
    host = d.journey
    host.case_config.update(scenario='autonomous', text=d.payloads[0]['text'], multi_task=True, poll_seconds=1)
    host.initialize_host = lambda **kw: dict(state='active')
    host.await_loop_authorization = lambda *args, **kw: None  # already authorized through real fixture UI contract
    host.status = lambda *args, **kw: None
    public = host.call
    host.call = lambda name, args: {} if name=='progression_command' else public(name, args)
    ticks = [0]
    def pump():
        ticks[0] += 1
        if ticks[0] == 1:
            completed_design(d)
        d.now[0] = 1498+ticks[0]
    host.pump = pump
    host.observe_background = lambda *args: None
    def budget(*args, **kw):
        if ticks[0] == 3:
            raise RuntimeError('acceptance_session_budget_exhausted:fixture_limit')
    host.check_case_budget = budget
    with pytest.raises(RuntimeError, match='budget_exhausted'):
        host.run_case()
    assert len(messages(d)) == 1
    host.record_batch_closeout(dict(host.row(), reason='budget_exhausted'))
    closeout = json.loads((host.logdir.parent/'batch-delivery-closeout.json').read_text())
    assert closeout['status']=='omitted' and len(closeout['omitted'])==2
    assert closeout['reason']=='budget_exhausted' and closeout['science_passed'] is False


def test_native_poll_stops_failed_run_before_an_otherwise_eligible_delivery(delivery):
    from scidiscovery.artifact_agent.schema.common import canonical_json
    d = delivery
    host = d.journey
    host.case_config.update(scenario='autonomous', text=d.payloads[0]['text'], multi_task=True, poll_seconds=1)
    host.initialize_host = lambda **kw: dict(state='active')
    host.await_loop_authorization = lambda *args, **kw: None
    host.status = lambda *args, **kw: None
    public = host.call
    host.call = lambda name, args: {} if name=='progression_command' else public(name, args)
    def pump():
        completed_design(d)
        d.f.register('copied-json', canonical_json(prediction_request('invented-original')))
        broken = d.f.start('broken', ('copied-json', 'observation'))
        compared = broken.worker.call_tool('worker_experiment_stage',
            comparison_request(broken.aliases['copied-json'], broken.aliases['observation']))
        measured_fixture_usage(broken.worker)
        submit_staged_report(broken, [compared['reference']])
        assert d.f.runtime.runs.status(broken.run_id).state != 'completed'
        # Invalid adoption is repairable, not an automatic terminal failure.
        # Simulate the separate fatal platform outcome through its real service.
        d.f.runtime.runs.fail(broken.run_id, reason='fixture fatal Worker outcome')
        assert d.f.runtime.runs.status(broken.run_id).state == 'failed'
        d.now[0] = 1500
    host.pump = pump
    host.observe_background = lambda *args: None
    host.check_case_budget = lambda *args, **kw: None
    with pytest.raises(RuntimeError, match='accepted_worker_failed'):
        host.run_case()
    assert messages(d) == []


def test_frozen_material_digest_and_wrong_scope_fail_closed(delivery):
    d = delivery
    wrong = dict(d.journey.row(), instance_id='another')
    with pytest.raises(RuntimeError, match='scope'):
        d.journey.deliver_batches(wrong)
    d.journey.case_config['batch_delivery'] = {**d.spec, 'materials_sha256':'0'*64}
    with pytest.raises(ValueError, match='digest_changed'):
        d.journey.deliver_batches(d.journey.row())
    assert messages(d) == []


@pytest.mark.parametrize('transition', ['pause', 'goal'])
def test_public_delivery_rechecks_scope_atomically_before_saving_future_bytes(delivery, transition):
    d = delivery
    completed_design(d)
    d.now[0] = 1500
    call = d.f.root.call_tool
    ingested = []
    reached_message = []
    transition_errors = []
    intake = d.f.root.facade.intake
    original_ingest = intake.ingest_text
    if transition == 'goal':
        ref = original_ingest(content=b'A separately frozen goal.')
        d.bindings.bind(instance=d.journey.instance, namespace='artifact', name='revised.goal',
            object_id=ref.artifact_id, request_fingerprint=hashlib.sha256(b'A separately frozen goal.').hexdigest())
    def ingest(**values):
        ingested.append(values)
        return original_ingest(**values)
    def racing_call(name, values):
        assert name == 'progression_message'
        try:
            call('progression_command', dict(command='pause'))
            if transition == 'goal':
                call('progression_command', dict(command='start', mode='background', objective_name='revised.goal'))
        except Exception as error:
            transition_errors.append(str(error))
            raise
        intake.ingest_text = ingest
        reached_message.append(name)
        return call(name, values)
    d.journey.call = racing_call
    try:
        # A rejected or uncertain submission remains non-replayable. The core
        # guarantee is zero future bytes/bindings, not a particular RPC error.
        try:
            d.journey.deliver_batches(d.journey.row())
        except RuntimeError:
            pass
        assert reached_message == ['progression_message'], transition_errors
        assert ingested == []
        assert messages(d) == []
        assert not any(v.name == 'acceptance.p6s.A_discrimination' for v in
            d.bindings.list(instance=d.journey.instance, namespace='artifact'))
    finally:
        intake.ingest_text = original_ingest
