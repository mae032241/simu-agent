"""N4 sealed-decision gates and operator acknowledgments; no model calls."""
import json
import shutil
from pathlib import Path

import pytest

from scidiscovery.research_loop import budget, cli, contracts as c, controller, correction, native
from test_history_handoff import finish
from test_search import focus, plan


@pytest.fixture
def scene(tmp_path, monkeypatch):
    monkeypatch.setattr(c, 'HANDOFF_PROTOCOL', 6)  # Published correction evidence remains byte compatible.
    public = tmp_path / 'public';public.mkdir()
    objective = public / 'objective.md';objective.write_text('Explain the global unresolved mechanism.')
    root = tmp_path / 'instance'
    controller.prepare(root, objective, public, ['fake'], max_tokens=100_000,
        max_seconds=3600, max_steps=40, model='fake', reasoning_effort='high',
        correction_policy=correction.DEFAULT_POLICY)
    return root


def worker(monkeypatch, decisions=None, actions=None, texts=None):
    calls = []
    decisions, actions = decisions or {}, actions or {}
    texts = texts or {}

    def execute(root, step):
        job = c.read(root / 'jobs' / f'{step:03d}.json')
        role = job['role'];calls.append((step, role))
        parents = [int(row['path'].split('/')[2]) for row in job['direct_refs']]
        choice, assessment = None, None
        action = actions.get(step, 'experiment' if role == 'H' else 'continue_w' if role == 'A' else 'wait')
        if role == 'H':
            known = job['search']['view']['commitments']
            choice = plan(existing_ref=known[0]['mechanism_ref'] if known else None)
        elif role == 'A':
            choice = dict(dispositions=[], next_focus=focus(action='screen'))
            assessment = decisions.get(step, dict(verdict='no_progress', evidence=[]))
        finish(root, step, role, parents, text=texts.get(step, f'Original {role} scientific observation {step}'),
               action=action, search_choice=choice, progress=assessment)

    monkeypatch.setattr(native, 'execute_native', execute)
    return calls


def published_pause(root):
    result = controller.run(root)
    assert result['status'] == 'correction_paused', result
    return result['correction_trigger']['trigger_id']


def test_three_a_force_h_then_two_a_pause_and_replay_is_exact(scene, monkeypatch):
    calls = worker(monkeypatch)
    trigger = published_pause(scene)
    assert calls == [(1, 'H'), (2, 'W'), (3, 'A'), (4, 'W'), (5, 'A'), (6, 'W'),
                     (7, 'A'), (8, 'H'), (9, 'W'), (10, 'A'), (11, 'W'), (12, 'A')]
    a7 = c.host_record(c.workspace(scene, 7)) / 'science-output.json'
    original = a7.read_bytes()
    assert c.read(a7)['next_action'] == 'continue_w'
    h8 = c.read(scene / 'jobs/008.json')
    assert h8['correction_request']['trigger_id'] != trigger
    state = cli.status(scene)['correction']
    assert state['counters'] == dict(no_progress=5, unknown=0)
    assert state['current_pause']['trigger_id'] == trigger
    assert len(state['eligible']) == 5
    assert len(state['triggers']) == 2
    assert controller.run(scene)['correction_trigger']['trigger_id'] == trigger
    assert len(calls) == 12 and a7.read_bytes() == original
    assert not (scene / 'jobs/013.json').exists()


def test_unknown_uses_own_three_two_gate_not_no_progress(scene, monkeypatch):
    worker(monkeypatch, {step: None for step in (3, 5, 7, 10, 12)})
    published_pause(scene)
    state = correction.project(scene)
    assert state['counters'] == dict(no_progress=0, unknown=5)
    assert state['current_pause']['reason'] == 'assessment_gap'


def test_unknown_preserves_no_progress_and_finish_preserves_scientific_route(scene, monkeypatch):
    calls = worker(monkeypatch, {5: dict(verdict='unknown', evidence=[])}, {9: 'finish'})
    assert controller.run(scene)['status'] == 'finish'
    state = correction.project(scene)
    assert state['counters'] == dict(no_progress=3, unknown=0)
    assert state['review_request']['step'] == 9
    assert calls[-1] == (9, 'A') and not (scene / 'jobs/010.json').exists()


def test_bound_negative_progress_after_h_resolves_first_stage(scene, monkeypatch):
    worker(monkeypatch, {10: dict(verdict='progress', evidence=['inputs/parents/009/conclusion.json'])},
           {12: 'finish'})
    assert controller.run(scene)['status'] == 'finish'
    state = correction.project(scene)
    assert state['counters'] == dict(no_progress=1, unknown=0)
    assert len(state['triggers']) == 1 and state['current_pause'] is None
    # Historical routing stays H even after later progress resolves the issue.
    assert c.read(scene / 'jobs/008.json')['role'] == 'H'
    assert controller.run(scene)['status'] == 'finish'


def test_parent_and_history_pages_share_one_proof_credit(scene, monkeypatch):
    worker(monkeypatch, {
        3: dict(verdict='progress', evidence=['inputs/parents/002/conclusion.json']),
        5: dict(verdict='progress', evidence=['inputs/history/nodes/002/0001.json']),
    }, {7: 'finish'})
    assert controller.run(scene)['status'] == 'finish'
    assert correction.project(scene)['counters'] == dict(no_progress=1, unknown=0)
    # Repeated proof at A5 was unknown, then known no_progress ends that streak.
    assert correction.project(scene, 6)['counters'] == dict(no_progress=0, unknown=1)


@pytest.mark.parametrize('path', ['artifacts/new-observation.json', 'work/proof.json',
                                 'inputs/parents/003/conclusion.json', '../../foreign/conclusion.json'])
def test_current_a_or_unbound_evidence_cannot_seal_as_progress(scene, monkeypatch, path):
    worker(monkeypatch, {3: dict(verdict='progress', evidence=[path])})
    result = controller.run(scene)
    assert result['status'] == 'seal_pending'
    assert not (c.host_record(c.workspace(scene, 3)) / 'result-identity.json').exists()
    assert not (scene / 'jobs/004.json').exists()


def test_h_e_h_response_and_a_e_a_do_not_count_deferred_nodes(scene, monkeypatch):
    calls = worker(monkeypatch, actions={5: 'extract', 10: 'extract'})
    published_pause(scene)
    assert (5, 'A') in calls and (6, 'E') in calls
    assert (10, 'H') in calls and (11, 'E') in calls and (12, 'H') in calls
    state = correction.project(scene)
    assert len(state['eligible']) == 5  # A3,A7,A9,A14,A16.
    request = c.read(scene / 'jobs/010.json')['correction_request']
    assert c.read(scene / 'jobs/012.json')['correction_request'] == request
    assert correction.project(scene, 12)['current_pause'] is None


def test_h_wait_preserves_scientific_wait_without_fabricated_response(scene, monkeypatch):
    calls = worker(monkeypatch, actions={8: 'wait'})
    assert controller.run(scene)['status'] == 'wait'
    assert len(calls) == 8
    state = correction.project(scene)
    assert state['review_request'] is not None and state['current_pause'] is None
    assert len(state['eligible']) == 3


def test_crash_after_review_trigger_before_h_intent_recovers_same_route(scene, monkeypatch):
    calls = worker(monkeypatch)
    original = native.execute_native

    def crash(root, step):
        if step == 8:
            raise RuntimeError('fixture crash before acceptance')
        return original(root, step)

    monkeypatch.setattr(native, 'execute_native', crash)
    assert controller.run(scene)['status'] == 'native_stopped'
    hjob = (scene / 'jobs/008.json').read_bytes()
    assert not (c.host_record(c.workspace(scene, 8)) / 'native-intent.json').exists()
    monkeypatch.setattr(native, 'execute_native', original)
    published_pause(scene)
    assert (scene / 'jobs/008.json').read_bytes() == hjob
    assert calls.count((8, 'H')) == 1


def test_exact_ack_one_cycle_idempotent_and_no_budget_refund(scene, monkeypatch, capsys):
    calls = worker(monkeypatch)
    old = published_pause(scene)
    c.write(scene / 'pause.request', dict(reason='user_pause'))
    ledger = sorted((scene / 'correction-ledger').glob('*.json'))
    assert cli.main(['continue', '--root', str(scene), '--ack-correction', 'wrong',
                     '--authorization-note', 'Review complete']) == 1
    assert (scene / 'pause.request').exists() and len(calls) == 12
    assert sorted((scene / 'correction-ledger').glob('*.json')) == ledger
    capsys.readouterr()
    before = budget.snapshot(scene)
    before_tokens = native.usage(scene)['observed_tokens']
    with controller._writer(scene):
        first = correction.acknowledge(scene, old, 'One review cycle permitted')
        assert correction.acknowledge(scene, old, 'Duplicate delivery') == first
    assert correction.project(scene)['permit'] is not None
    assert cli.main(['continue', '--root', str(scene)]) == 2
    capsys.readouterr()
    assert calls[-2:] == [(13, 'W'), (14, 'A')]
    state = correction.project(scene)
    assert state['current_pause']['trigger_id'] != old and state['permit'] is None
    assert native.usage(scene)['observed_tokens'] == before_tokens + 20
    assert budget.snapshot(scene)['consumed_seconds'] >= before['consumed_seconds']
    assert budget.snapshot(scene)['max_tokens'] == before['max_tokens']
    with controller._writer(scene), pytest.raises(ValueError, match='exact current'):
        correction.acknowledge(scene, old, 'Stale review')
    assert len([event for event in correction._records(scene)[0] if event['kind'] == 'ack']) == 1


def test_plain_continue_and_pause_marker_deletion_do_not_release_gate(scene, monkeypatch, capsys):
    calls = worker(monkeypatch)
    trigger = published_pause(scene)
    c.write(scene / 'pause.request', dict(reason='user_pause'))
    assert cli.main(['continue', '--root', str(scene)]) == 2
    capsys.readouterr()
    assert len(calls) == 12
    assert correction.project(scene)['current_pause']['trigger_id'] == trigger


def test_status_readonly_and_cache_delete_rebuild_counters(scene, monkeypatch):
    worker(monkeypatch)
    published_pause(scene)
    facts = {path: path.read_bytes() for path in (scene / 'correction-ledger').glob('*.json')}
    original = correction.project(scene)
    shutil.rmtree(scene / 'host-history/nodes', ignore_errors=True)
    assert cli.status(scene)['correction'] == original
    assert all(path.read_bytes() == data for path, data in facts.items())


def test_ack_active_or_unknown_execution_is_rejected_before_write(scene, monkeypatch):
    worker(monkeypatch)
    trigger = published_pause(scene)
    monkeypatch.setattr(budget, 'execution_blocked', lambda _: True)
    with controller._writer(scene), pytest.raises(RuntimeError, match='active or unknown'):
        correction.acknowledge(scene, trigger, 'Operator note')
    assert len(correction._records(scene)[0]) == 2


def test_trigger_tamper_fails_closed(scene, monkeypatch):
    worker(monkeypatch)
    published_pause(scene)
    path = scene / 'correction-ledger/000001.json'
    value = c.read(path);value['trigger']['reason'] = 'assessment_gap';c.write(path, value)
    with pytest.raises(ValueError, match='sequence|sealed facts'):
        correction.project(scene)


def test_accepted_terminal_w_collects_before_gate_blocks_next_a(scene, monkeypatch):
    calls = worker(monkeypatch)
    trigger = published_pause(scene)
    last = c.validate(c.workspace(scene, 12))
    route = controller._route(scene, 12, 'A', last, c.read(scene / 'jobs/012.json'), 8, 11)
    c.build_job(scene, 13, route[0], route[1], route[2], route[3])
    finish(scene, 13, 'W', route[1], text='Accepted W contribution before recovery')
    record = c.host_record(c.workspace(scene, 13))
    (record / 'result-identity.json').unlink()  # Original terminal output awaits seal.
    intent = (record / 'native-intent.json').read_bytes()
    result = controller.run(scene)
    assert result['status'] == 'correction_paused' and result['completed_steps'] == 13
    assert result['correction_trigger']['trigger_id'] == trigger
    assert (record / 'result-identity.json').exists()
    assert (record / 'native-intent.json').read_bytes() == intent
    assert not (scene / 'jobs/014.json').exists() and len(calls) == 12


def test_late_sealed_progress_cannot_remove_published_pause(scene, monkeypatch):
    calls = worker(monkeypatch)
    trigger = published_pause(scene)
    c.build_job(scene, 13, 'W', [8, 11, 12], instruction='Exact scientific question')
    finish(scene, 13, 'W', [8, 11, 12], text='New late original evidence')
    finish(scene, 14, 'A', [8, 13], action='continue_w',
           search_choice=dict(dispositions=[], next_focus=focus(action='screen')),
           progress=dict(verdict='progress', evidence=['inputs/parents/013/conclusion.json']))
    record = c.host_record(c.workspace(scene, 14))
    (record / 'result-identity.json').unlink()
    intent = (record / 'native-intent.json').read_bytes()
    result = controller.run(scene)
    assert result['status'] == 'correction_paused' and result['completed_steps'] == 14
    assert (record / 'result-identity.json').exists()
    assert (record / 'native-intent.json').read_bytes() == intent and len(calls) == 12
    state = correction.project(scene)
    assert state['current_pause']['trigger_id'] == trigger and state['permit'] is None
    assert state['counters']['no_progress'] == 5 and len(state['eligible']) == 6


def test_ack_progress_spends_permit_and_resolves_without_changing_old_h_job(scene, monkeypatch):
    calls = worker(monkeypatch, {14: dict(verdict='progress', evidence=['inputs/parents/013/conclusion.json'])},
                   {16: 'finish'})
    trigger = published_pause(scene)
    original = (scene / 'jobs/008.json').read_bytes()
    with controller._writer(scene):
        correction.acknowledge(scene, trigger, 'One independently evaluated cycle')
    assert controller.run(scene)['status'] == 'finish'
    state = correction.project(scene)
    assert state['current_pause'] is None and state['permit'] is None
    assert state['counters'] == dict(no_progress=1, unknown=0)
    assert (scene / 'jobs/008.json').read_bytes() == original
    before = len(calls)
    assert controller.run(scene)['status'] == 'finish' and len(calls) == before


def test_ack_unknown_spends_cycle_but_does_not_resolve_prior_no_progress_pause(scene, monkeypatch):
    calls = worker(monkeypatch, {14: dict(verdict='unknown', evidence=[])})
    trigger = published_pause(scene)
    with controller._writer(scene):
        correction.acknowledge(scene, trigger, 'Only one cycle authorized')
    result = controller.run(scene)
    assert result['status'] == 'correction_paused' and result['completed_steps'] == 14
    assert result['correction_trigger']['trigger_id'] != trigger
    assert result['correction_trigger']['reason'] == 'no_progress_unresolved'
    assert correction.project(scene)['counters'] == dict(no_progress=5, unknown=1)
    assert correction.project(scene)['permit'] is None and calls[-2:] == [(13, 'W'), (14, 'A')]
    assert not (scene / 'jobs/015.json').exists()


@pytest.mark.parametrize('verdict', ['progress', 'no_progress'])
def test_unknown_pause_ack_known_judgment_ends_unknown_issue(scene, monkeypatch, verdict):
    decisions = {step: dict(verdict='unknown', evidence=[]) for step in (3, 5, 7, 10, 12)}
    decisions[14] = dict(verdict=verdict, evidence=['inputs/parents/013/conclusion.json'] if verdict == 'progress' else [])
    calls = worker(monkeypatch, decisions, {14: 'finish'})
    trigger = published_pause(scene)
    assert correction.project(scene)['current_pause']['reason'] == 'assessment_gap'
    with controller._writer(scene):
        correction.acknowledge(scene, trigger, 'One assessment cycle authorized')
    assert controller.run(scene)['status'] == 'finish'
    state = correction.project(scene)
    assert state['current_pause'] is None and state['permit'] is None
    assert state['counters'] == dict(no_progress=1 if verdict == 'no_progress' else 0, unknown=0)
    assert calls[-2:] == [(13, 'W'), (14, 'A')]


def test_identical_raw_bytes_at_different_nodes_receive_only_one_credit(scene, monkeypatch):
    worker(monkeypatch, {
        3: dict(verdict='progress', evidence=['inputs/parents/002/conclusion.json']),
        5: dict(verdict='progress', evidence=['inputs/parents/004/conclusion.json']),
    }, {5: 'finish'}, {2: 'Same original science bytes', 4: 'Same original science bytes'})
    assert controller.run(scene)['status'] == 'finish'
    assert c.digest(c.host_record(c.workspace(scene, 2)) / 'science-output.json') == c.digest(
        c.host_record(c.workspace(scene, 4)) / 'science-output.json')
    assert correction.project(scene)['counters'] == dict(no_progress=0, unknown=1)


def test_crash_after_trigger_before_any_h_job_reconstructs_h(scene, monkeypatch):
    calls = worker(monkeypatch)
    original = c.build_job

    def crash(root, step, *args, **kwargs):
        if step == 8:
            raise RuntimeError('fixture crash before H job creation')
        return original(root, step, *args, **kwargs)

    monkeypatch.setattr(c, 'build_job', crash)
    with pytest.raises(RuntimeError, match='before H job'):
        controller.run(scene)
    assert len(correction._records(scene)[0]) == 1
    assert not (scene / 'jobs/008.json').exists()
    monkeypatch.setattr(c, 'build_job', original)
    published_pause(scene)
    assert calls.count((8, 'H')) == 1


def test_newly_published_pause_remains_gate_after_already_accepted_late_progress(scene, monkeypatch):
    worker(monkeypatch)
    published_pause(scene)
    # Simulate controller crash before publication of its second trigger;
    # original accepted work is already available when it recovers all seals.
    (scene / 'correction-ledger/000002.json').unlink()
    finish(scene, 13, 'W', [8, 11, 12], text='New late sealed observation')
    finish(scene, 14, 'A', [8, 13], action='continue_w',
           search_choice=dict(dispositions=[], next_focus=focus(action='screen')),
           progress=dict(verdict='progress', evidence=['inputs/parents/013/conclusion.json']))
    assert correction.project(scene)['current_pause'] is None  # Not yet published.
    with controller._writer(scene):
        stopped = correction.gate(scene, 14)
    assert stopped is not None and stopped['step'] == 12 and stopped['published']
    assert correction.project(scene)['current_pause']['trigger_id'] == stopped['trigger_id']
    assert not (scene / 'jobs/015.json').exists()


@pytest.mark.parametrize('verdict', ['no_progress', 'unknown'])
def test_first_pause_published_in_cutoff_order_with_late_accepted_assessment(scene, monkeypatch, verdict):
    worker(monkeypatch)
    published_pause(scene)
    (scene / 'correction-ledger/000002.json').unlink()
    finish(scene, 13, 'W', [8, 11, 12], text='Accepted late experiment')
    finish(scene, 14, 'A', [8, 13], action='continue_w',
           search_choice=dict(dispositions=[], next_focus=focus(action='screen')),
           progress=dict(verdict=verdict, evidence=[]))
    with controller._writer(scene):
        stopped = correction.gate(scene, 14)
    assert stopped['step'] == 12 and stopped['published']
    assert len([event for event in correction._records(scene)[0]
                if event['kind'] == 'trigger' and event['trigger']['level'] == 'pause']) == 1


def test_ack_is_spent_when_a_sealed_even_if_controller_crashes_before_trigger_publish(scene, monkeypatch):
    calls = worker(monkeypatch)
    trigger = published_pause(scene)
    with controller._writer(scene):
        correction.acknowledge(scene, trigger, 'One A cycle authorized')
    original = native.execute_native

    def crash(root, step):
        original(root, step)
        if step == 14:
            raise RuntimeError('fixture crash after A seal')

    monkeypatch.setattr(native, 'execute_native', crash)
    assert controller.run(scene)['status'] == 'seal_pending'
    assert correction.project(scene)['permit'] is None
    monkeypatch.setattr(native, 'execute_native', original)
    result = controller.run(scene)
    assert result['status'] == 'correction_paused' and result['completed_steps'] == 14
    assert calls.count((14, 'A')) == 1 and not (scene / 'jobs/015.json').exists()


def test_ack_requires_same_writer_lock_before_clearing_user_pause(scene, monkeypatch, capsys):
    worker(monkeypatch)
    trigger = published_pause(scene)
    c.write(scene / 'pause.request', dict(reason='user_pause'))
    with controller._writer(scene):
        assert cli.main(['continue', '--root', str(scene), '--ack-correction', trigger,
                         '--authorization-note', 'Operator decision']) == 1
    capsys.readouterr()
    assert (scene / 'pause.request').exists() and len(correction._records(scene)[0]) == 2


@pytest.mark.parametrize('note', ['复核' * 3000, 'Review accepted: ' + '\n' * 8000])
def test_oversized_serialized_ack_note_never_changes_ledger_or_user_pause(scene, monkeypatch, capsys, note):
    worker(monkeypatch)
    trigger = published_pause(scene)
    c.write(scene / 'pause.request', dict(reason='user_pause'))
    before = {path: path.read_bytes() for path in (scene / 'correction-ledger').glob('*.json')}
    assert cli.main(['continue', '--root', str(scene), '--ack-correction', trigger,
                     '--authorization-note', note]) == 1
    assert 'serialized UTF-8 byte bound' in json.loads(capsys.readouterr().out)['error']
    assert {path: path.read_bytes() for path in (scene / 'correction-ledger').glob('*.json')} == before
    assert (scene / 'pause.request').exists()
    assert correction.project(scene)['current_pause']['trigger_id'] == trigger
    assert correction.project(scene)['permit'] is None


def test_cross_instance_fact_copy_and_progress_source_tamper_rejected(scene, monkeypatch, tmp_path):
    worker(monkeypatch)
    published_pause(scene)
    copied = tmp_path / 'copied';shutil.copytree(scene, copied)
    settings = c.settings(copied);settings['goal_id'] = 'another-instance'
    c.write(copied / 'settings.json', settings)
    c.write(copied / 'settings-identity.json', dict(sha256=c.digest(copied / 'settings.json')))
    with pytest.raises(ValueError, match='identity'):
        correction.project(copied)
    raw = c.host_record(c.workspace(scene, 2)) / 'science-output.json'
    raw.write_text('{}')
    with pytest.raises(ValueError, match='source changed'):
        correction.project(scene)


def test_protocol5_original_job_schema_and_seal_stay_unchanged(scene, monkeypatch):
    monkeypatch.setattr(c, 'HANDOFF_PROTOCOL', 5)
    finish(scene, 1, 'H', [], action='analyze', search_choice=plan())
    c.build_job(scene, 2, 'A', [1])
    work = c.workspace(scene, 2);record = c.host_record(work)
    monkeypatch.setattr(c, 'HANDOFF_PROTOCOL', 7)
    finish(scene, 2, 'A', [1], action='finish')
    paths = [scene / 'jobs/002.json', work / 'science-task.json', record / 'science-result.schema.json',
             record / 'science-output.json', record / 'result-identity.json']
    original = {path: path.read_bytes() for path in paths}
    c.build_job(scene, 2, 'A', [1]);c.validate(work)
    assert all(path.read_bytes() == data for path, data in original.items())
    assert correction.project(scene)['eligible'] == []


def test_seal_marker_does_not_make_unknown_native_outcome_countable(scene, monkeypatch):
    worker(monkeypatch)
    published_pause(scene)
    path = c.host_record(c.workspace(scene, 3)) / 'native-outcome.json'
    value = c.read(path);value['stop_reason'] = 'native_error_unknown';c.write(path, value)
    with pytest.raises(ValueError, match='verified original terminal'):
        correction.project(scene)


@pytest.mark.parametrize('protocol', [1, 2, 3, 4, 5])
def test_legacy_a_schema_has_no_progress_field(protocol):
    assert 'progress_assessment' not in c.result_schema('A', protocol)['properties']
    assert 'progress_assessment' in c.result_schema('A', 6)['required']
