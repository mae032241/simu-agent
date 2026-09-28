"""Acceptance assertions use real persisted control shapes, without a model."""
import json
from copy import deepcopy
import pytest

from scripts.accept_progression_recovery import INGEST_ARGUMENTS, RecoveryJourney, recovery_matches, running_turn
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
