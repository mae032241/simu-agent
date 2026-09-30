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
    journey.row = lambda: dict(state='active', reason='host_active')
    journey.call = unavailable
    with pytest.raises(TimeoutError, match='start outcome unknown'):
        journey.run_journey()
    assert calls == [('progression_command', {'command':'pause'})]
    assert json.loads((tmp_path/'failure-closeout-error.json').read_text())['status'] == 'unconfirmed'


@pytest.mark.parametrize('reason', ['goal_completed', 'root_turn_failed', 'budget_exhausted',
    'host_fault', 'resource_limit', 'submission_unknown', 'attempt_budget_exhausted', 'task_admission_unknown'])
def test_known_recovery_stop_does_not_wait_until_timeout(monkeypatch, reason):
    import scripts.accept_progression_recovery as acceptance
    journey = RecoveryJourney.__new__(RecoveryJourney)
    journey.phase_deadline = acceptance.time.monotonic() + 90
    journey.pump = lambda: None
    journey.row = lambda: {'state':'paused','reason':reason}
    def unexpected_sleep(_):
        pytest.fail('known stopped recovery must be reported immediately')
    monkeypatch.setattr(acceptance.time, 'sleep', unexpected_sleep)
    with pytest.raises(RuntimeError, match='recovered:unexpected_stop:'+reason):
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


def test_writer_release_wait_observes_next_tick_after_goal_stop(tmp_path, monkeypatch):
    import scripts.accept_progression_recovery as acceptance
    journey = RecoveryJourney.__new__(RecoveryJourney)
    journey.logdir = tmp_path/'logs'
    journey.phase_deadline = acceptance.time.monotonic()+90
    journey.pump = lambda: None
    observed = []
    reports = iter([
        dict(state='active', reason='goal_completed', host_json='recorded-host'),
        dict(state='paused', reason='goal_completed', host_json='recorded-host'),
        dict(state='paused', reason='goal_completed', host_json=None),
    ])
    def next_row():
        value = next(reports)
        observed.append(value)
        return value
    journey.row = next_row
    monkeypatch.setattr(acceptance.time, 'sleep', lambda _: None)
    result = journey.wait_row(lambda row: row['state'] in {'paused','stopped'} and not row['host_json'],
        'closeout-released', cleanup=True)
    assert result['host_json'] is None and len(observed) == 3


@pytest.mark.parametrize('reason', ['goal_completed', 'budget_exhausted', 'root_turn_failed'])
def test_native_case_cleanup_preserves_stop_and_waits_after_expired_deadline(tmp_path, monkeypatch, reason):
    import scripts.accept_progression_recovery as recovery
    from scripts.acceptance_native_cases import NativeCaseJourney
    journey = NativeCaseJourney.__new__(NativeCaseJourney)
    journey.logdir = tmp_path/'logs'
    journey.case_config = dict(stage_timeout_seconds=1)
    journey.phase_deadline = old_deadline = recovery.time.monotonic()-1
    control = dict(state='paused', reason=reason, host_json='recorded-host')
    reports = iter([control, control, {**control, 'host_json':None}])
    journey.row = lambda: next(reports)
    polls = []
    def pump():
        assert journey.phase_deadline > recovery.time.monotonic()
        polls.append(1)
    journey.pump = pump
    journey.call = lambda *args: pytest.fail('already stopped reason must be retained')
    def finished():
        journey.control_attempted = True
    journey.run_case = finished
    monkeypatch.setattr(recovery.time, 'sleep', lambda _: None)
    journey.run_journey()
    assert len(polls) == 2 and journey.phase_deadline == old_deadline
    assert json.loads((tmp_path/'closeout-released.json').read_text())['host_json'] is None
    assert json.loads((tmp_path/'terminal-control.json').read_text())['reason'] == reason
    assert not (tmp_path/'closeout-error.json').exists()


@pytest.mark.parametrize('reason', ['submission_unknown', 'host_fault', 'task_admission_unknown'])
def test_unconfirmed_cleanup_times_out_with_marker_and_primary_error_intact(tmp_path, monkeypatch, reason):
    import scripts.accept_progression_recovery as recovery
    import scripts.acceptance_native_cases as native
    journey = native.NativeCaseJourney.__new__(native.NativeCaseJourney)
    journey.root = tmp_path
    journey.logdir = tmp_path/'logs'
    journey.case_config = dict(stage_timeout_seconds=.5)
    journey.case_checks = {}
    journey.before_runs = []
    journey.phase_deadline = 99
    clock, polls = [100.], []
    marker = dict(state='paused', reason=reason, host_json='recorded-host')
    journey.row = lambda: marker.copy()
    def pump():
        polls.append(1)
        clock[0] += .1
    journey.pump = pump
    journey.call = lambda *args: pytest.fail('cleanup must not replace an existing stop')
    primary = TimeoutError('uncertain_submit')
    def failed():
        journey.control_attempted = True
        journey.case_started_at = 1
        raise primary
    journey.run_case = failed
    monkeypatch.setattr(recovery.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(recovery.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0]+seconds))
    monkeypatch.setattr(native, 'run_snapshot', lambda _: [])
    monkeypatch.setattr(native, 'participants', lambda *args: ([], []))
    def budget(*args, **kwargs):
        raise RuntimeError('acceptance_session_budget_exhausted:capability=private-secret')
    journey.check_case_budget = budget
    with pytest.raises(TimeoutError) as raised:
        journey.run_journey()
    assert raised.value is primary and polls and journey.phase_deadline == 99
    assert marker['host_json'] == 'recorded-host' and marker['reason'] == reason
    assert not (tmp_path/'closeout-released.json').exists()
    diagnostic = json.loads((tmp_path/'closeout-error.json').read_text())
    assert diagnostic == dict(status='unconfirmed', error_type='TimeoutError', stage='writer_release',
        error_code='timeout', stop_reason=reason)
    final = (tmp_path/'budget-final-error.json').read_text()
    assert json.loads(final)['stage'] == 'budget_final'
    assert json.loads(final)['error_code'] == 'acceptance_session_budget_exhausted'
    assert 'private-secret' not in final and 'capability=' not in final


def test_cleanup_failure_without_primary_is_unconfirmed_and_diagnostic_is_safe(tmp_path):
    from scripts.acceptance_native_cases import NativeCaseJourney
    from scidiscovery.platforms.codex_app_server import HostError
    journey = NativeCaseJourney.__new__(NativeCaseJourney)
    journey.logdir = tmp_path/'logs'
    journey.case_config = dict(stage_timeout_seconds=1)
    journey.row = lambda: dict(state='paused', reason='host_fault', host_json='recorded-host')
    def finished():
        journey.control_attempted = True
    journey.run_case = finished
    def disconnected(*args, **kwargs):
        raise HostError('app_server_closed', method='capability=private-secret')
    journey.wait_row = disconnected
    with pytest.raises(RuntimeError, match='background_closeout_unconfirmed') as raised:
        journey.run_journey()
    assert isinstance(raised.value.__cause__, HostError)
    diagnostic = (tmp_path/'closeout-error.json').read_text()
    assert json.loads(diagnostic)['error_code'] == 'app_server_closed'
    assert 'private-secret' not in diagnostic and 'capability=' not in diagnostic


def test_closeout_evidence_write_failure_cannot_replace_primary(tmp_path, monkeypatch, capsys):
    import scripts.accept_progression_recovery as recovery
    import scripts.acceptance_native_cases as native
    journey = native.NativeCaseJourney.__new__(native.NativeCaseJourney)
    journey.logdir = tmp_path/'logs'
    journey.row = lambda: dict(state='paused', reason='budget_exhausted', host_json='recorded-host')
    primary = RuntimeError('background_stopped:budget_exhausted')
    def failed():
        journey.control_attempted = True
        raise primary
    journey.run_case = failed
    def denied(*args, **kwargs):
        raise OSError('capability=private-secret')
    monkeypatch.setattr(native, 'write', denied)
    monkeypatch.setattr(recovery, 'write', denied)
    with pytest.raises(RuntimeError) as raised:
        journey.run_journey()
    assert raised.value is primary
    diagnostic = capsys.readouterr().err
    assert json.loads(diagnostic)['diagnostic_write'] == 'failed'
    assert 'private-secret' not in diagnostic


def test_failure_keeps_service_alive_until_writer_release(tmp_path):
    journey=RecoveryJourney.__new__(RecoveryJourney)
    journey.logdir=tmp_path/'logs'
    calls=[]
    def fail():
        journey.control_attempted=True
        raise RuntimeError('original_failure')
    journey.run_recovery=fail
    journey.row=lambda:dict(state='active',reason='host_active')
    journey.call=lambda name,args: calls.append(name) or {'state':'paused'}
    def released(predicate,label,**kwargs):
        calls.append(label)
        assert kwargs['cleanup'] is True
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
