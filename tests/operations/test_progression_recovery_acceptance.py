"""Acceptance assertions use real persisted control shapes, without a model."""
import json
from copy import deepcopy
import pytest

from scripts.accept_progression_recovery import INGEST_ARGUMENTS, CLOSEOUT_ARGUMENTS, RecoveryJourney, recovery_matches, running_turn, naturally_completed
from scidiscovery.artifact_agent.interfaces.mcp_root import IngestTextInput
from tests.operations.test_progression import progression, row


def test_recovery_identity_goal_config_and_consumption_are_not_replaceable(progression):
    IngestTextInput.model_validate(INGEST_ARGUMENTS)
    p = progression
    p.coordinator.tick()
    original = row(p)
    assert running_turn(original)
    assert recovery_matches(original, original)
    for field, value in (
        ('host_json', json.dumps(dict(thread_id='replacement'))),
        ('host_json', json.dumps({**json.loads(original['host_json']), 'platform_session':'replacement'})),
        ('objective_ref_json', '{}'),
        ('config_json', '{}'),
        ('checkpoint_json', json.dumps(dict(started_at=-1))),
    ):
        changed = deepcopy(original)
        changed[field] = value
        assert not recovery_matches(original, changed)
    checkpoint = json.loads(original['checkpoint_json'])
    checkpoint['usage_records'] = {'exact-root': {'counted_tokens': {'input_tokens': 100, 'output_tokens': 5}}}
    measured = {**original, 'checkpoint_json': json.dumps(checkpoint)}
    assert not recovery_matches(measured, original)
    assert recovery_matches(measured, measured)
    checkpoint['usage_records']['exact-root']['counted_tokens']['input_tokens'] = 99
    assert not recovery_matches(measured, {**original, 'checkpoint_json':json.dumps(checkpoint)})


def test_prepared_or_paused_turn_does_not_qualify_as_active_native_turn(progression):
    p = progression
    p.coordinator.tick()
    active = row(p)
    for change in ({'state':'paused'}, {'host_json':None}):
        assert not running_turn({**active, **change})
    checkpoint = json.loads(active['checkpoint_json'])
    checkpoint.update(phase='prepared', turn_id=None)
    assert not running_turn({**active, 'checkpoint_json':json.dumps(checkpoint)})


def test_uncertain_start_attempts_one_pause_and_preserves_original_failure(tmp_path):
    journey = RecoveryJourney.__new__(RecoveryJourney)
    journey.logdir = tmp_path / 'logs'
    calls = []
    def fail():
        journey.control_attempted = True
        raise TimeoutError('start outcome unknown')
    def unavailable(name, arguments):
        calls.append((name, arguments))
        raise RuntimeError('service unavailable')
    journey.run_recovery = fail
    journey.call = unavailable
    with pytest.raises(TimeoutError, match='start outcome unknown'):
        journey.run_journey()
    assert calls == [('progression_command', {'command':'pause'})]
    assert json.loads((tmp_path/'failure-pause.json').read_text())['status'] == 'unconfirmed'


def test_known_recovery_stop_does_not_wait_until_timeout(monkeypatch):
    import scripts.accept_progression_recovery as acceptance
    journey = RecoveryJourney.__new__(RecoveryJourney)
    journey.phase_deadline = acceptance.time.monotonic() + 90
    journey.pump = lambda: None
    journey.row = lambda: {'state':'paused','reason':'root_turn_failed'}
    def unexpected_sleep(_):
        pytest.fail('known stopped recovery must be reported immediately')
    monkeypatch.setattr(acceptance.time, 'sleep', unexpected_sleep)
    with pytest.raises(RuntimeError, match='recovered:unexpected_stop:root_turn_failed'):
        journey.wait_row(lambda row: False, 'recovered')


def test_goal_report_before_native_terminal_is_not_a_failed_recovery(tmp_path,monkeypatch):
    import scripts.accept_progression_recovery as acceptance
    journey=RecoveryJourney.__new__(RecoveryJourney)
    journey.logdir=tmp_path/'logs'
    journey.phase_deadline=acceptance.time.monotonic()+90
    journey.pump=lambda:None
    reports=iter([
        dict(state='active',reason='goal_completed',checkpoint_json=json.dumps(dict(
            native_completion='interrupted',report=dict(completed=True)))),
        dict(state='paused',reason='goal_completed',checkpoint_json=json.dumps(dict(
            native_completion='completed',report=dict(completed=True)))),
    ])
    journey.row=lambda:next(reports)
    monkeypatch.setattr(acceptance.time,'sleep',lambda _:None)
    result=journey.wait_row(lambda row:json.loads(row['checkpoint_json'])['native_completion']=='completed',
        'recovered-completed')
    assert result['state']=='paused'
    assert (tmp_path/'recovered-completed.json').exists()


def test_failure_keeps_service_alive_until_writer_release(tmp_path):
    journey=RecoveryJourney.__new__(RecoveryJourney)
    journey.logdir=tmp_path/'logs'
    calls=[]
    def fail():
        journey.control_attempted=True
        raise RuntimeError('original_failure')
    journey.run_recovery=fail
    journey.call=lambda name,args: calls.append(name) or {'state':'paused'}
    def released(predicate,label,**kwargs):
        calls.append(label)
        assert not predicate(dict(state='paused',host_json='recorded-host'))
        assert predicate(dict(state='paused',host_json=None))
    journey.wait_row=released
    with pytest.raises(RuntimeError,match='original_failure'):
        journey.run_journey()
    assert calls==['progression_command','failure-released']


def test_natural_completion_requires_consumed_terminal_and_report():
    checkpoint=dict(phase='idle',turn_id=None,native_completion='completed',report={'completed':True})
    def row(value):return dict(checkpoint_json=json.dumps(value))
    assert naturally_completed(row(checkpoint))
    for change in (dict(phase='running'),dict(turn_id='active'),dict(native_completion='interrupted'),dict(report=None)):
        assert not naturally_completed(row({**checkpoint,**change}))


@pytest.mark.parametrize('terminal',['completed','interrupted'])
def test_closeout_uses_exact_native_terminal_without_claiming_recovery(tmp_path,terminal):
    IngestTextInput.model_validate(CLOSEOUT_ARGUMENTS)
    journey=RecoveryJourney.__new__(RecoveryJourney)
    journey.logdir=tmp_path/'logs'
    checkpoint=dict(phase='idle',turn_id=None,native_completion='completed',report={'completed':True},rounds=1)
    completed=dict(checkpoint_json=json.dumps(checkpoint))
    def wait(predicate,label):
        value=completed if label=='recovered-completed' else dict(mode='interactive',host_json=None)
        assert predicate(value)
        return value
    journey.wait_row=wait
    reads=[]
    def rpc(method,args):
        reads.append((method,args))
        return {'thread':{'id':'actual-root','turns':[{'id':'actual-turn','status':terminal}]}}
    journey.rpc=rpc
    calls=[]
    journey.call=lambda name,args:calls.append((name,args)) or {'can_schedule':True}
    journey.runs_snapshot=lambda:[]
    started=dict(host_json=json.dumps(dict(thread_id='actual-root')),
        checkpoint_json=json.dumps(dict(turn_id='actual-turn')))
    if terminal=='interrupted':
        with pytest.raises(RuntimeError,match='one_naturally_completed_turn'):
            journey.finish_control([],started)
        assert not calls
    else:
        journey.finish_control([],started)
        summary=json.loads((tmp_path/'summary.json').read_text())
        assert set(summary['checks'])=={'natural_completion','takeover','writer_release','state_preserved'}
        assert summary['daemon_restart'] is False
        assert [args['command'] for name,args in calls if name=='progression_command']==['takeover','stop']
    assert reads==[('thread/read',{'threadId':'actual-root','includeTurns':True})]
