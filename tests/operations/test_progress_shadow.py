"""Deterministic shadow semantics and the real native-consumption integration."""
import json
import sqlite3

import pytest

from scidiscovery.agent_execution_settings import ProgressionSettings, AgentSettings, effective_settings
from scidiscovery.artifact_agent.schema.common import canonical_sha256
from scidiscovery.artifact_agent.service.scientific_progress import (
    PROGRESS_SCHEMA, _update_fact, observe_deliveries, reduce_shadow, refresh_shadow, shadow_policy,
)
from tests.operations.test_progression import progression, row, checkpoint
from tests.operations.test_scientific_progress import active, finish, assess, INTENT


def fact(sequence, outcome='unknown', digest='same', intent='refine', supported=True):
    ref = dict(artifact_id=f'artifact-{sequence}', sha256=digest, kind='result', schema_id='science')
    return dict(sequence=sequence, task_name=f'renamed-{sequence}',
        terminal=dict(state='completed', output=ref),
        intent=dict(intent=intent, target=f'rewritten target {sequence}') if intent else None,
        assessment=dict(classification=outcome, supported=supported,
            evidence=[dict(name=f'renamed-{sequence}.output', ref=ref)] if supported else [],
            assessment_ref=ref, revision=1))


def test_unknown_missing_support_and_renames_never_clear_no_progress():
    facts = [fact(1, 'no_progress'), fact(2, 'unknown'), fact(3, 'advance', supported=False),
        fact(4, 'advance')]  # same payload under a different exact ref/name/target
    counts = reduce_shadow(facts)
    assert counts['no_progress'] == 1
    assert counts['unchanged_evidence'] == 3
    assert counts['refinement'] == 4
    assert counts['consumed'] == 4
    assert reduce_shadow([fact(1, 'advance', intent=None)])['coverage_gap'] == 1
    assert reduce_shadow([fact(1, 'advance', supported=False)])['coverage_gap'] == 1


def test_negative_scientific_result_and_new_analysis_can_advance_but_file_change_alone_cannot():
    base = [fact(1, 'no_progress')]
    assert reduce_shadow(base + [fact(2, 'unknown', 'new-file')])['no_progress'] == 1
    negative = fact(3, 'advance', 'sealed-mechanism-exclusion')
    assert reduce_shadow(base + [negative])['no_progress'] == 0
    assert reduce_shadow(base + [negative])['unchanged_evidence'] == 0
    # A recoverable engineering failure never supplies a scientific classification.
    failures = [fact(index, supported=False) for index in range(1, 4)]
    for index, item in enumerate(failures):
        item['terminal'] = dict(state='failed', output=None, reason=f'Checker failed at task-{index}/result.json',
            failure_key=dict(operation_id='observe', operation_digest='v1', category='checker_failure', code='checker_failure'))
    counts = reduce_shadow(failures)
    assert counts['no_progress'] == 0 and counts['repeated_failure'] == 3
    assert counts['coverage_gap'] == 3
    # Identical public prose cannot merge different mechanical failure classes.
    failures[-1]['terminal']['reason'] = failures[-2]['terminal']['reason']
    failures[-1]['terminal']['failure_key']['category'] = 'runtime_failure'
    failures[-1]['terminal']['failure_key']['code'] = 'runtime_failure'
    assert reduce_shadow(failures)['repeated_failure'] == 1
    failures[-1]['terminal'].pop('failure_key')
    assert reduce_shadow(failures)['repeated_failure'] == 0


def database():
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.executescript(PROGRESS_SCHEMA)
    objective = dict(artifact_id='goal', sha256='goal-digest', kind='goal', schema_id='science')
    row_value = dict(instance_id='instance', host_json='{}', objective_ref_json=json.dumps(objective),
        config_json=json.dumps(dict(effective=dict(progression=ProgressionSettings().model_dump()))))
    return db, row_value, canonical_sha256(objective)


def consume(db, current, goal_key, item):
    if item.get('assessment'):
        _update_fact(db, current['instance_id'], goal_key, str(item['sequence']), dict(assessment=item['assessment']))
    decision = dict(phase='running', turn_id='confirmed', terminal_delivery=dict(
        objective_ref=json.loads(current['objective_ref_json']), items=[dict(run_id=str(item['sequence']),
            name=item['task_name'], terminal=item['terminal'], scientific_intent=item['intent'],
            delivery=dict(original_read='not_confirmed'))]))
    observe_deliveries(db, current, decision, boundary='turn_completed')
    return decision


def state(db):
    return json.loads(db.execute('SELECT state_json FROM scheduler_progress_shadow').fetchone()[0])


def test_repeated_settlement_late_correction_and_new_episode_preserve_snapshots():
    db, current, goal_key = database()
    for index in range(1, 4):
        consume(db, current, goal_key, fact(index, 'no_progress'))
    first = state(db)
    snapshot = next(item for item in first['notices'] if item['reason'] == 'no_progress')
    assert snapshot['trigger_counts']['no_progress'] == 3
    assert snapshot['state'] == 'shadow_recorded' and not snapshot['dispatch_changed']
    # A correction can change live classification without rewriting old triggers.
    _update_fact(db, current['instance_id'], goal_key, '3', dict(assessment=fact(3, 'advance', 'late-new')['assessment']))
    refresh_shadow(db, current, goal_key)
    corrected = state(db)
    assert corrected['counts']['no_progress'] == 0
    assert snapshot in corrected['notices'] and corrected['dispositions'] == []
    decision = consume(db, current, goal_key, fact(4, 'advance', 'actual-new-result'))
    settled = state(db)
    assert next(item for item in settled['notices'] if item['reason'] == 'refinement')['would_act'] == 'refinement_hint'
    assert any(item['notice_id'] == snapshot['id'] for item in settled['dispositions'])
    observe_deliveries(db, current, decision, boundary='next_task_admission')
    assert state(db) == settled
    for index in range(5, 8):
        consume(db, current, goal_key, fact(index, 'no_progress'))
    assert len([item for item in state(db)['notices'] if item['reason'] == 'no_progress']) == 2
    assert snapshot in state(db)['notices']


def test_bounded_replay_omits_excess_and_off_preserves_records():
    db, current, goal_key = database()
    settings = json.loads(current['config_json'])
    settings['effective']['progression']['max_tasks'] = 2
    current['config_json'] = json.dumps(settings)
    for index in range(1, 4):
        consume(db, current, goal_key, fact(index))
    assert state(db)['omitted'] and state(db)['counts']['consumed'] == 2
    saved = state(db)
    settings['effective']['progression']['progress_mode'] = 'off'
    current['config_json'] = json.dumps(settings)
    consume(db, current, goal_key, fact(4))
    assert state(db) == saved


def test_settings_freeze_defaults_and_do_not_enable_old_goals():
    defaults = ProgressionSettings()
    assert (defaults.progress_mode, defaults.no_progress_threshold, defaults.refinement_threshold,
        defaults.observation_gap_threshold) == ('shadow', 3, 4, 3)
    assert ProgressionSettings(progress_mode='assist').progress_mode == 'assist'
    assert shadow_policy(dict(config_json='{}'))['progress_mode'] == 'off'
    global_settings = AgentSettings(progression=ProgressionSettings(progress_mode='off'))
    assert effective_settings(global_settings, dict(progression=dict(progress_mode='shadow')))['progression']['progress_mode'] == 'off'


def native_delivery(p, root, name):
    host = p.coordinator.host
    projection = root.call_tool('run_status', dict(name=name, intent='decision'))
    host.event(dict(method='item/completed', params=dict(threadId=host.identity.thread_id, turnId=host.turn_id,
        item=dict(type='mcpToolCall', id='read-'+name, server='scidiscovery', tool='scid_call', status='completed',
            arguments=dict(name='run_status', arguments=dict(name=name)),
            result=dict(content=[], structuredContent=projection)))))


def test_real_consumption_without_reports_triggers_shadow_and_readonly_shared_projection(progression):
    from scidiscovery.artifact_agent.approval_ui.progression_render import render_progression
    from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService
    from scidiscovery.artifact_agent.service.scientific_progress import shadow_projection
    p = progression
    root = active(p)
    for index in range(3):
        name = f'no-report-{index}'
        finish(p, root, name, intent=None)
        native_delivery(p, root, name)
    host = p.coordinator.host
    host.finish()
    status = root.call_tool('progression_status', {})
    shadow = status['progress_shadow']
    assert shadow['counts']['consumed'] == 3 and shadow['counts']['coverage_gap'] == 3
    assert shadow['counts']['no_progress'] == 0
    assert {item['reason'] for item in shadow['notices']} == {'coverage_gap', 'unchanged_evidence'}
    assert status['state'] == 'active' and '科研进展观测与提示' in render_progression(status, instance_id=p.instance)
    before = row(p)
    assert root.call_tool('progression_status', {})['progress_shadow'] == shadow
    assert row(p) == before
    reopened = SchedulerBindingService(p.runtime.scheduler_bindings.database_path)
    assert shadow_projection(bindings=reopened, row=before) == shadow
    host.finish()
    assert root.call_tool('progression_status', {})['progress_shadow'] == shadow
    brief = json.loads(p.coordinator._brief(row(p), p.coordinator._snapshot(row(p)), 45000).split('\n')[-1])
    assert brief['progress_shadow'] == shadow
    # Corrections flow through the real report transaction, not a test reducer.
    assess(root, 'no-report-2', outcome='advance')
    after = root.call_tool('progression_status', {})['progress_shadow']
    assert after['notices'] == shadow['notices']
    assert after['counts']['unchanged_evidence'] == 0


def test_running_task_and_ordinary_wait_never_count(progression):
    from tests.operations.test_scientific_progress import request
    p = progression
    root = active(p)
    root.call_tool('operation_invoke', request('still-running'))
    root.call_tool('progression_report', dict(summary='Waiting for the accepted task.'))
    p.coordinator.host.finish()
    p.coordinator.tick()
    before = root.call_tool('progression_status', {})['progress_shadow']
    for _ in range(3):
        p.now[0] += 6
        p.coordinator.tick()
    assert before['counts']['consumed'] == 0
    assert root.call_tool('progression_status', {})['progress_shadow'] == before
    assert len(p.coordinator.host.prompts) == 1


def test_correction_before_settlement_does_not_create_stale_trigger():
    db, current, goal_key = database()
    for index in (1, 2):
        consume(db, current, goal_key, fact(index, 'no_progress'))
    # Latest immutable judgment is present before the terminal consumption.
    corrected = fact(3, 'advance', 'negative-result-excludes-candidate')
    consume(db, current, goal_key, corrected)
    assert state(db)['counts']['no_progress'] == 0
    assert not any(item['reason'] == 'no_progress' for item in state(db)['notices'])


def test_unchanged_events_do_not_rewrite_shadow_state():
    db, current, goal_key = database()
    decision = consume(db, current, goal_key, fact(1))
    sql = []
    db.set_trace_callback(sql.append)
    observe_deliveries(db, current, decision, boundary='turn_completed')
    refresh_shadow(db, current, goal_key)
    assert not any('INSERT INTO scheduler_progress_shadow' in query for query in sql)
    assert not any('INSERT INTO scheduler_progress_facts' in query for query in sql)


@pytest.mark.parametrize('delivery', ['native', 'brief'])
def test_machine_failure_classification_survives_real_terminal_delivery(progression, delivery):
    from tests.operations.test_scientific_progress import request, deliveries
    p = progression
    root = active(p)
    root.call_tool('operation_invoke', request('checker-failure'))
    run_id = p.runtime.scheduler_bindings.resolve(instance=p.instance, namespace='run', name='checker-failure')
    value = p.runtime.runs.status(run_id)
    p.runtime.runs.record_failure(run_id, reason='Checker failed at a run-specific output path.',
        expected_state=value.state, expected_last_activity_at=value.last_activity_at, category='checker_failure')
    if delivery == 'native':
        native_delivery(p, root, 'checker-failure')
    else:
        p.coordinator.host.finish()
        p.now[0] += 6
        p.coordinator.tick()
    p.coordinator.host.finish()
    terminal = json.loads(deliveries(p)[0]['terminal_json'])
    assert terminal['failure_key'] == dict(operation_id=value.operation_id, operation_digest=value.operation_digest,
        category='checker_failure', code='checker_failure')
    assert terminal['failure_classification'] == 'recorded_diagnostic'
    counts = root.call_tool('progression_status', {})['progress_shadow']['counts']
    assert counts['consumed'] == 1 and counts['repeated_failure'] == 1
    assert counts['no_progress'] == 0
