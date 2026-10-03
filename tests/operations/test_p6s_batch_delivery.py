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


def safe_fixture_rotation(d, *, observe_prepared=True, before_complete=None):
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
    with d.f.runtime.runs._connect() as db:
        fence = db.execute('SELECT COALESCE(MAX(rowid),0) FROM run_activity').fetchone()[0]
    prepared = d.bindings.prepare_host_rotation(instance_id=d.journey.instance, expected_host=old,
        expected_generation=control['generation'], terminal_turn=d.coordinator.host.completion, run_activity_fence=fence)
    if observe_prepared:
        d.journey.deliver_batches(prepared)
    if before_complete:
        before_complete(prepared)
    new_session = 'sch_'+('c' if old['thread_id'] != 'new-root' else 'd')*32
    new_thread = 'new-root' if old['thread_id'] != 'new-root' else 'next-root'
    active = d.bindings.complete_host_rotation(instance_id=d.journey.instance, expected_host=old,
        expected_generation=prepared['generation'], scheduler_session=new_session,
        platform_session=new_thread, thread_id=new_thread)
    d.f.root.facade.session_key = new_session
    return prepared, active


def completed_batch_comparison(d, *, compare=True):
    completed_design(d)
    d.now[0] = 1500
    d.journey.deliver_batches(d.journey.row())
    author = d.f.start('prediction-before-rotation', ('acceptance.p6s.A_discrimination',))
    declared = author.worker.call_tool('worker_experiment_stage', prediction_request(author.aliases['acceptance.p6s.A_discrimination']))
    measured_fixture_usage(author.worker)
    submit_staged_report(author, [declared['reference']])
    d.now[0] = 3300
    d.journey.deliver_batches(d.journey.row())
    if not compare:
        return declared, author
    consumer = d.f.start('comparison-before-rotation', (declared['artifact_name'], 'acceptance.p6s.A_validation'))
    compared = consumer.worker.call_tool('worker_experiment_stage', comparison_request(
        consumer.aliases[declared['artifact_name']], consumer.aliases['acceptance.p6s.A_validation'], status='fail'))
    measured_fixture_usage(consumer.worker)
    submit_staged_report(consumer, [compared['reference']])
    d.now[0] = 5100
    return consumer


def test_rotation_completed_between_polls_releases_from_durable_receipt(delivery):
    d = delivery
    completed_batch_comparison(d)
    _, active = safe_fixture_rotation(d, observe_prepared=False)
    d.journey.deliver_batches(active)
    assert len(messages(d)) == 3  # no poll saw the prepared state
    saved = messages(d)
    d.journey.deliver_batches(d.journey.row())
    assert messages(d) == saved


def test_late_usage_retains_preparation_fence_and_completed_receipt_with_continuous_counts(delivery):
    d = delivery
    completed_batch_comparison(d)
    captured = {}
    def usage(control, amount):
        host = json.loads(control['host_json'])
        thread = captured['old']['thread_id']
        d.bindings.observe_progression(instance_id=d.journey.instance, expected_host=host, changes={},
            usage_observation=dict(params=dict(threadId=thread, tokenUsage=dict(total=dict(
                inputTokens=amount, cachedInputTokens=0, outputTokens=10))), identity={}, root_thread=host['thread_id']))
        return json.loads(d.journey.row()['checkpoint_json'])
    def late(prepared):
        captured['old'] = json.loads(prepared['host_json'])
        original = json.loads(prepared['checkpoint_json'])['usage_records'][captured['old']['thread_id']]
        after = usage(prepared, 100)['usage_records'][captured['old']['thread_id']]
        assert after['retired_after_turn'] == original['retired_after_turn']
        assert after['retired_after_activity'] == original['retired_after_activity']
        assert after['counted_tokens']['input_tokens'] == 100
    _, active = safe_fixture_rotation(d, observe_prepared=False, before_complete=late)
    receipt = json.loads(active['checkpoint_json'])['root_rotation_receipt']
    after = usage(active, 200)
    assert after['root_rotation_receipt'] == receipt
    assert after['usage_records'][captured['old']['thread_id']]['counted_tokens']['input_tokens'] == 200
    d.journey.deliver_batches(d.journey.row())
    assert len(messages(d)) == 3


def test_early_rotation_does_not_cover_later_comparison_but_next_rotation_does(delivery):
    d = delivery
    declared, author = completed_batch_comparison(d, compare=False)
    _, early = safe_fixture_rotation(d, observe_prepared=False)
    early_receipt = json.loads(early['checkpoint_json'])['root_rotation_receipt']
    fresh_host = json.loads(early['host_json'])
    d.bindings.observe_progression(instance_id=d.journey.instance, expected_host=fresh_host, changes={},
        usage_observation=dict(params=dict(threadId=fresh_host['thread_id'], tokenUsage=dict(total=dict(
            inputTokens=10, cachedInputTokens=0, outputTokens=1))), identity={}, root_thread=fresh_host['thread_id']))
    consumer = d.f.start('comparison-after-rotation', (declared['artifact_name'], 'acceptance.p6s.A_validation'))
    compared = consumer.worker.call_tool('worker_experiment_stage', comparison_request(
        consumer.aliases[declared['artifact_name']], consumer.aliases['acceptance.p6s.A_validation'], status='fail'))
    measured_fixture_usage(consumer.worker)
    submit_staged_report(consumer, [compared['reference']])
    # The legacy fixture helper replaces Root records; restore its trusted
    # session metadata from the current control owner via the existing service.
    current = d.journey.row()
    cp = json.loads(current['checkpoint_json'])
    cp['usage_records'][fresh_host['thread_id']]['scheduler_session'] = current['owner_session']
    d.bindings.observe_progression(instance_id=d.journey.instance, expected_host=fresh_host,
        changes=dict(usage_records=cp['usage_records']))
    d.now[0] = 5100
    d.journey.deliver_batches(d.journey.row())
    observation = json.loads((d.journey.logdir.parent/'batch-delivery-observation.json').read_text())
    event = observation['facts']['comparisons'][0]['completion_event']
    assert event > early_receipt['run_activity_fence']
    assert observation['reason']=='comparison_before_rotation_unknown' and len(messages(d)) == 2
    _, later = safe_fixture_rotation(d, observe_prepared=False)
    assert json.loads(later['checkpoint_json'])['root_rotation_receipt']['run_activity_fence'] >= event
    d.journey.deliver_batches(later)
    assert len(messages(d)) == 3


@pytest.mark.parametrize('damage', ['missing', 'version', 'goal', 'loop', 'generation', 'boundary', 'terminal', 'retirement'])
def test_missing_or_inconsistent_receipt_is_unknown_not_a_generation_inference(delivery, damage):
    d = delivery
    completed_batch_comparison(d)
    _, active = safe_fixture_rotation(d, observe_prepared=False)
    cp = json.loads(active['checkpoint_json'])
    receipt = cp['root_rotation_receipt']
    if damage == 'missing': cp.pop('root_rotation_receipt')
    elif damage == 'version': receipt['version'] = 999
    elif damage == 'goal': receipt['scope']['goal']['sha256'] = '0'*64
    elif damage == 'loop': receipt['scope']['loop'] = 'other-loop'
    elif damage == 'generation': receipt['completed_generation'] += 1
    elif damage == 'boundary': receipt['boundary']['unknown'] = 1
    elif damage == 'terminal': receipt['terminal_turn'] = None
    else: cp['usage_records'][receipt['old']['thread_id']]['retired_after_turn'] = 'wrong-turn'
    # Corrupt a read snapshot, not the authority. All unrelated new host and
    # retired/generation facts still exist and must not substitute for receipt.
    d.journey.deliver_batches(dict(active, checkpoint_json=json.dumps(cp)))
    observation = json.loads((d.journey.logdir.parent/'batch-delivery-observation.json').read_text())
    assert observation['reason']=='safe_rotation_unknown' and len(messages(d)) == 2


@pytest.mark.parametrize('cancel', ['complete_failure', 'pause', 'takeover'])
def test_unsuccessful_rotation_never_publishes_a_receipt_or_releases(delivery, cancel):
    d = delivery
    completed_batch_comparison(d)
    control = d.journey.row()
    old = json.loads(control['host_json'])
    d.coordinator.host.finish()
    d.bindings.observe_progression(instance_id=d.journey.instance, expected_host=old,
        changes=dict(phase='idle', turn_id=None, native_completion='completed',
            rotation_boundary=dict(checked=2, unchecked=0, unknown=0, reasons=[])))
    prepared = d.bindings.prepare_host_rotation(instance_id=d.journey.instance, expected_host=old,
        expected_generation=control['generation'], terminal_turn=d.coordinator.host.completion)
    assert 'root_rotation_receipt' not in json.loads(prepared['checkpoint_json'])
    if cancel == 'complete_failure':
        with pytest.raises(Exception, match='fresh actual native identity'):
            d.bindings.complete_host_rotation(instance_id=d.journey.instance, expected_host=old,
                expected_generation=prepared['generation'], scheduler_session='sch_'+'d'*32, **old)
        d.bindings.abandon_host_rotation(instance_id=d.journey.instance, expected_host=old,
            expected_generation=prepared['generation'])
    else:
        d.bindings.progression_command(instance_id=d.journey.instance, session_key=None, command='pause')
        with pytest.raises(Exception, match='ownership changed'):
            d.bindings.complete_host_rotation(instance_id=d.journey.instance, expected_host=old,
                expected_generation=prepared['generation'], scheduler_session='sch_'+'d'*32,
                platform_session='never-bound', thread_id='never-bound')
        current = d.journey.row()
        d.bindings.abandon_host_rotation(instance_id=d.journey.instance, expected_host=old, expected_generation=current['generation'])
        if cancel == 'takeover':
            d.bindings.progression_command(instance_id=d.journey.instance, session_key='sch_'+'a'*32, command='takeover')
    assert 'root_rotation_receipt' not in json.loads(d.journey.row()['checkpoint_json'])
    if cancel == 'takeover':
        with pytest.raises(RuntimeError, match='scope_unconfirmed'):
            d.journey.deliver_batches(d.journey.row())
    else:
        d.journey.deliver_batches(d.journey.row())
    assert len(messages(d)) == 2


def test_rotation_receipt_survives_runtime_reopen_and_archive_without_public_bindings(delivery):
    from scidiscovery.artifact_agent.runtime import open_runtime
    from tests.operations.synchronous_archive_fixture import SynchronousFixtureArchive
    from tests.operations.test_instance_archive import save_archive, restore_archive
    d = delivery
    consumer = completed_batch_comparison(d)
    _, active = safe_fixture_rotation(d, observe_prepared=False)
    receipt = json.loads(active['checkpoint_json'])['root_rotation_receipt']
    public = d.f.root.call_tool('progression_status', {})
    assert all(key not in json.dumps(public) for key in ('root_rotation_receipt','old_session','new_session','retired_after_activity'))
    reopened = open_runtime(project_root=d.f.runtime.project_root, state_root=d.f.runtime.state_root,
        approval_receipt_secret=b'b'*32)
    read = reopened.scheduler_bindings.progression_status(instance_id=d.journey.instance, internal=True)
    assert json.loads(read['checkpoint_json'])['root_rotation_receipt'] == receipt
    d.journey.deliver_batches(read)  # keep B2's existing same-process selection
    assert len(messages(d)) == 3
    d.f.root.call_tool('progression_command', dict(command='pause'))
    d.bindings.release_host(instance_id=d.journey.instance, **receipt['new'])
    with d.f.runtime.runs._connect() as db:
        event = db.execute("SELECT rowid FROM run_activity WHERE run_id=? AND activity='completion_committed'", (consumer.run_id,)).fetchone()[0]
    d.f.runtime.runs._synchronous_archive_fixture = True
    output = d.f.runtime.runs.status(consumer.run_id).output_ref
    service = SynchronousFixtureArchive(d.f.runtime)
    save_archive(service, d.journey.instance)
    archived = service.archived_model(d.journey.instance)
    archived_control = archived.bindings.progression_status(instance_id=d.journey.instance, internal=True)
    assert json.loads(archived_control['checkpoint_json'])['root_rotation_receipt'] == receipt
    assert archived.runs.status(consumer.run_id).output_ref == output
    restore_archive(service, d.journey.instance)
    restored = d.bindings.progression_status(instance_id=d.journey.instance, internal=True)
    assert json.loads(restored['checkpoint_json'])['root_rotation_receipt'] == receipt
    with d.f.runtime.runs._connect() as db:
        assert db.execute("SELECT rowid FROM run_activity WHERE run_id=? AND activity='completion_committed'", (consumer.run_id,)).fetchone()[0] == event


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


def test_final_prediction_then_completed_adopted_comparison_requires_actual_rotation(delivery):
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
    assert len(messages(d)) == 1
    assert d.f.runtime.runs.status(declaration_author.run_id).state == 'running'
    measured_fixture_usage(declaration_author.worker)
    submit_staged_report(declaration_author, [declaration['reference']])
    assert d.f.runtime.runs.status(declaration_author.run_id).state == 'completed'
    d.journey.deliver_batches(d.journey.row())
    assert len(messages(d)) == 2
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
    stage = author.worker.call_tool('worker_experiment_stage', prediction_request(author.aliases['condition']))
    measured_fixture_usage(author.worker)
    submit_staged_report(author, [stage['reference']])
    d.now[0] = 3300
    d.journey.deliver_batches(d.journey.row())
    assert messages(d) == original and not hasattr(d.journey, '_batch_prediction')
    observation = json.loads((d.journey.logdir.parent/'batch-delivery-observation.json').read_text())
    assert any(v['reason']=='prediction_conditions_not_discrimination' for v in observation['facts']['waiting'])


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


def test_final_adoption_selects_revision_not_the_historical_preview_count(delivery):
    d = delivery
    completed_design(d)
    d.now[0] = 1500
    d.journey.deliver_batches(d.journey.row())
    author = d.f.start('revised-prediction', ('acceptance.p6s.A_discrimination',))
    request = prediction_request(author.aliases['acceptance.p6s.A_discrimination'])
    preview = author.worker.call_tool('worker_experiment_stage', request)
    request['conclusion'] = 'Adopt the corrected prediction rather than the earlier preview.'
    adopted = author.worker.call_tool('worker_experiment_stage', request)
    d.now[0] = 3300
    d.journey.deliver_batches(d.journey.row())
    assert len(messages(d)) == 1
    measured_fixture_usage(author.worker)
    submit_staged_report(author, [adopted['reference']])
    result = d.f.runtime.runs.status(author.run_id)
    assert result.state == 'completed'  # a legitimate prediction-only, inconclusive report
    d.journey.deliver_batches(d.journey.row())
    assert len(messages(d)) == 2
    selected = d.journey._batch_prediction_binding
    assert selected['run_id'] == author.run_id
    assert selected['report_ref'] == result.output_ref.model_dump(mode='json')
    assert selected['artifact_ref'] == d.f.runtime.artifacts.get_by_id(
        d.bindings.resolve(instance=d.journey.instance, namespace='artifact', name=adopted['artifact_name'])).ref.model_dump(mode='json')
    assert selected['artifact_ref'] != d.f.runtime.artifacts.get_by_id(
        d.bindings.resolve(instance=d.journey.instance, namespace='artifact', name=preview['artifact_name'])).ref.model_dump(mode='json')
    # A later final C has no replacement semantics. It neither changes the
    # already released B binding nor blocks the exact comparison of B.
    later = d.f.start('later-prediction', ('acceptance.p6s.A_discrimination', 'condition'))
    replacement = later.worker.call_tool('worker_experiment_stage',
        prediction_request(later.aliases['acceptance.p6s.A_discrimination']))
    unrelated = later.worker.call_tool('worker_experiment_stage', prediction_request(later.aliases['condition']))
    measured_fixture_usage(later.worker)
    submit_staged_report(later, [replacement['reference'], unrelated['reference']])
    consumer = d.f.start('selected-comparison', (adopted['artifact_name'], 'acceptance.p6s.A_validation'))
    compared = consumer.worker.call_tool('worker_experiment_stage', comparison_request(
        consumer.aliases[adopted['artifact_name']], consumer.aliases['acceptance.p6s.A_validation'], status='fail'))
    measured_fixture_usage(consumer.worker)
    submit_staged_report(consumer, [compared['reference']])
    d.now[0] = 5100
    _, active = safe_fixture_rotation(d)
    d.journey.deliver_batches(active)
    assert len(messages(d)) == 3 and d.journey._batch_prediction_binding == selected
    assert d.journey._batch_release_observations[-1]['prediction_binding'] == selected


def test_unrelated_completed_predictions_are_unknown_and_restart_cannot_guess_selection(delivery):
    d = delivery
    completed_design(d)
    d.now[0] = 1500
    d.journey.deliver_batches(d.journey.row())
    for name in ('independent-one', 'independent-two'):
        author = d.f.start(name, ('acceptance.p6s.A_discrimination',))
        stage = author.worker.call_tool('worker_experiment_stage', prediction_request(author.aliases['acceptance.p6s.A_discrimination']))
        measured_fixture_usage(author.worker)
        submit_staged_report(author, [stage['reference']])
    d.now[0] = 3300
    d.journey.deliver_batches(d.journey.row())
    observation = json.loads((d.journey.logdir.parent/'batch-delivery-observation.json').read_text())
    assert observation['reason'] == 'multiple_adopted_predictions_no_declared_replacement'
    assert len(observation['facts']['declarations']) == 2 and len(messages(d)) == 1
    # Existing exact public ack alone cannot recover which final report caused
    # a release. A new observer must not choose either candidate by recency.
    d.f.root.call_tool('progression_message', dict(name='acceptance.p6s.A_validation', text=d.payloads[2]['text']))
    d.now[0] = 5100
    d.journey.deliver_batches(d.journey.row())
    observation = json.loads((d.journey.logdir.parent/'batch-delivery-observation.json').read_text())
    assert observation['reason'] == 'prediction_release_binding_unavailable'
    assert observation['post_model_restart_supported'] is False and len(messages(d)) == 2


def test_batch_opening_and_discrimination_discover_only_the_bench_delivery_protocol(delivery):
    d = delivery
    opening = native.case_objective(dict(text=d.payloads[0]['text'], batch_delivery=d.spec))
    for text in (opening, d.payloads[1]['text']):
        assert 'science.experiment.v1' in text
        assert 'prediction_declaration' in text and 'adopted_stages' in text
        assert 'x=4' in text
    assert 'prediction_declaration' not in native.case_objective(dict(text='An ordinary task.'))
    assert 'A_validation' not in opening and 'B_changed_condition' not in opening


@pytest.mark.parametrize('large_candidate', [False, True])
def test_large_unrelated_input_does_not_mask_candidate_but_unread_adopted_stage_blocks_uniqueness(delivery, large_candidate):
    d = delivery
    completed_design(d)
    d.now[0] = 1500
    d.journey.deliver_batches(d.journey.row())
    d.f.register('large-ordinary-material', b'x'*70000)
    author = d.f.start('healthy', ('acceptance.p6s.A_discrimination', 'large-ordinary-material'))
    declared = author.worker.call_tool('worker_experiment_stage', prediction_request(author.aliases['acceptance.p6s.A_discrimination']))
    measured_fixture_usage(author.worker)
    submit_staged_report(author, [declared['reference']])
    if large_candidate:
        other = d.f.start('large-final', ('acceptance.p6s.A_discrimination',))
        request = prediction_request(other.aliases['acceptance.p6s.A_discrimination'])
        request['limitations'] = ['A retained long scientific limitation. '*2000]
        large = other.worker.call_tool('worker_experiment_stage', request)
        measured_fixture_usage(other.worker)
        submit_staged_report(other, [large['reference']])
        assert d.f.runtime.runs.status(other.run_id).state == 'completed'
    d.now[0] = 3300
    d.journey.deliver_batches(d.journey.row())
    observation = json.loads((d.journey.logdir.parent/'batch-delivery-observation.json').read_text())
    assert len(observation['facts']['declarations']) == 1
    assert observation['facts']['declaration_coverage_complete'] is not large_candidate
    assert len(messages(d)) == (1 if large_candidate else 2)
    if large_candidate:
        assert observation['reason']=='adopted_prediction_coverage_unknown'
        assert any(v['reason']=='adopted_stage_body_limit' for v in observation['facts']['waiting'])
    else:
        assert any(v['reason']=='adopted_stage_without_prediction_or_comparison' for v in observation['facts']['waiting'])


def test_copied_declaration_is_rejected_by_final_adoption_and_cannot_release(delivery):
    from scidiscovery.artifact_agent.schema.common import canonical_json
    d = delivery
    completed_design(d)
    d.now[0] = 1500
    d.journey.deliver_batches(d.journey.row())
    d.f.register('copied-prediction', canonical_json(prediction_request('invented-producer-alias')))
    author = d.f.start('copied-consumer', ('copied-prediction', 'observation'))
    compared = author.worker.call_tool('worker_experiment_stage',
        comparison_request(author.aliases['copied-prediction'], author.aliases['observation']))
    measured_fixture_usage(author.worker)
    result = submit_staged_report(author, [compared['reference']])
    assert d.f.runtime.runs.status(author.run_id).state != 'completed'
    assert 'unique original stage receipt' in json.dumps(result)
    d.now[0] = 5100
    d.journey.deliver_batches(d.journey.row())
    assert len(messages(d)) == 1


@pytest.mark.parametrize('corruption', ['bytes', 'receipt', 'namespace'])
def test_selected_original_corruption_is_hard_failure_not_waiting(delivery, corruption):
    import sqlite3
    d = delivery
    completed_design(d)
    d.now[0] = 1500
    d.journey.deliver_batches(d.journey.row())
    author = d.f.start('original', ('acceptance.p6s.A_discrimination',))
    declared = author.worker.call_tool('worker_experiment_stage', prediction_request(author.aliases['acceptance.p6s.A_discrimination']))
    measured_fixture_usage(author.worker)
    submit_staged_report(author, [declared['reference']])
    ref = d.f.runtime.runs.tool_evidence(author.run_id)[0]['artifact_ref']
    if corruption == 'bytes':
        path = d.journey.root/'state/artifacts/sha256'/ref['sha256'][:2]/ref['sha256'][2:]
        raw = path.read_bytes()
        path.write_bytes(raw.replace(b'condition A', b'condition B'))  # equal-size altered bytes
    else:
        with sqlite3.connect(d.journey.root/'state/database/runs.sqlite3') as db:
            if corruption == 'receipt':
                raw = db.execute('SELECT record_json FROM run_tool_evidence WHERE run_id=?', (author.run_id,)).fetchone()[0]
                record = json.loads(raw)
                record['size_bytes'] += 1
                db.execute('UPDATE run_tool_evidence SET record_json=? WHERE run_id=?', (json.dumps(record), author.run_id))
            else:
                raw = db.execute('SELECT inputs_json FROM runs WHERE run_id=?', (author.run_id,)).fetchone()[0]
                inputs = json.loads(raw)
                for item in inputs:
                    if item['source_name'] == author.aliases['acceptance.p6s.A_discrimination']:
                        item['source_name'] = 'wrong-producer-namespace'
                db.execute('UPDATE runs SET inputs_json=? WHERE run_id=?', (json.dumps(inputs), author.run_id))
    d.now[0] = 3300
    with pytest.raises(Exception, match={'bytes':'bytes_mismatch', 'receipt':'original control receipt',
            'namespace':'condition_namespace_missing'}[corruption]):
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
    measured_fixture_usage(author.worker)
    submit_staged_report(author, [declared['reference']])
    d.now[0] = 3300
    d.journey.deliver_batches(d.journey.row())
    if missing == 'wrong_prediction':
        wrong_author = d.f.start('different-declaration', ('condition',))
        declared = wrong_author.worker.call_tool('worker_experiment_stage', prediction_request(wrong_author.aliases['condition']))
        measured_fixture_usage(wrong_author.worker)
        submit_staged_report(wrong_author, [declared['reference']])
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
