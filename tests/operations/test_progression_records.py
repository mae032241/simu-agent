"""Persistent detail capacity, atomicity and exact historical scope consumers."""
import json

import pytest

from scidiscovery.artifact_agent.service.progression_records import COLLECTIONS, SNAPSHOTS, store_checkpoint
from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService
from tests.operations.test_progression import progression, row
from tests.operations.test_research_loop_budget import historical_checkpoint as checkpoint
from tests.operations.test_human_progress_continuation import (
    paused, human_ui, submit, status,
)
from tests.operations.test_scientific_progress import finish, request
from tests.operations.test_instance_archive import archive_system
from tests.operations.test_m6a_direct_instance_management import _request


def physical(p):
    with p.runtime.scheduler_bindings._connect() as db:
        raw = db.execute('SELECT checkpoint_json FROM scheduler_progression WHERE instance_id=?',
            (p.instance,)).fetchone()[0]
        details = [tuple(item) for item in db.execute('SELECT collection,record_key,record_json '
            'FROM scheduler_progression_details WHERE instance_id=? ORDER BY collection,record_key', (p.instance,))]
    return raw, details


def test_detail_writer_replaces_owned_records_and_retains_unknown_history(progression):
    p = progression
    with p.runtime.scheduler_bindings._connect() as db:
        db.execute('INSERT INTO scheduler_progression_details VALUES(?,?,?,?)',
            (p.instance, 'snapshot', 'historical-unknown', '{"turn":"uncertain"}'))
        store_checkpoint(db, p.instance, {'processed_snapshot': None, 'usage_records': {'root': {'tokens': 7}}}, replace=True)
        store_checkpoint(db, p.instance, {'decision_snapshot': {}, 'usage_records': {}}, replace=True)
        records = [tuple(item) for item in db.execute('SELECT collection,record_key,record_json '
            'FROM scheduler_progression_details WHERE instance_id=? ORDER BY collection,record_key', (p.instance,))]
    assert records == [('snapshot', 'decision_snapshot', '{}'),
        ('snapshot', 'historical-unknown', '{"turn":"uncertain"}')]


def ui_loop_history(ui, names, *, context_bytes=49152):
    """Every small historical scope is explicitly authorized through real HTTP."""
    import re
    p = ui.p
    bindings = p.runtime.scheduler_bindings
    settings = bindings.global_settings
    bindings.global_settings = settings.model_copy(update=dict(progression=settings.progression.model_copy(
        update=dict(max_tasks=3, max_loop_scopes=40, progress_mode='shadow', context_bytes=context_bytes))))
    for index, name in enumerate(names):
        if index % 2 == 0:
            p.root.call_tool('progression_command', dict(command='pause'))
            page = _request(ui.base, 'GET', ui.path)[2].decode().split('data-loop-authorization>', 1)[1]
            binding = re.search(r"name='confirmation_binding' value='([^']+)'", page)[1]
            form = dict(capability=ui.form['capability'], csrf=ui.form['csrf'], command='authorize_loop',
                instance_id=p.instance, confirmation_binding=binding, objective_name='goal', confirm_loop_budget='yes')
            assert _request(ui.base, 'POST', '/instances/progression', form=form)[0] == 303
            p.root.call_tool('progression_command', dict(command='start', mode='interactive', objective_name='goal'))
        finish(p, p.root, name)


def test_large_history_keeps_ui_admission_budgets_and_archive(human_ui):
    from tests.operations.synchronous_archive_fixture import SynchronousFixtureArchive
    from tests.operations.test_instance_archive import save_archive, restore_archive
    ui, p = human_ui, human_ui.p
    assert submit(ui) == 303
    finish(p, p.root, 'retained-background-task')
    background = checkpoint(p)['admissions']['retained-background-task']
    ui_loop_history(ui, [f'historical-human-{index}' for index in range(72)])
    prior = checkpoint(p)
    from scidiscovery.artifact_agent.service.scheduling_control import background_task_count
    assert background_task_count(prior) == 2
    raw, details = physical(p)
    assert len(json.dumps(prior).encode()) > 65536
    assert len(raw.encode()) < 65536
    assert not (set(COLLECTIONS) & json.loads(raw).keys())
    assert len(prior['loop_authorizations']) == 38  # Original, assist fixture, 36 explicit budgets.
    assert prior['admissions']['historical-human-0']['loop_id'] != prior['current_loop_id']
    assert prior['admissions']['retained-background-task'] == background
    view = status(p)
    assert view['budget']['tasks'] == 2
    assert len(view['loop']['history']) == 8
    assert view['loop']['history_omitted'] == 30
    assert _request(ui.base, 'GET', ui.path)[0] == 200
    assert p.root.call_tool('operation_preflight', request('after-large-history'))['admissible']
    finish(p, p.root, 'after-large-history')
    assert p.root.call_tool('run_status', dict(name='historical-human-0'))['state'] == 'completed'
    reopened = SchedulerBindingService(p.runtime.scheduler_bindings.database_path)
    with reopened._connect() as db:
        from scidiscovery.artifact_agent.service.progression_records import read_control_row
        assert json.loads(read_control_row(db, p.instance, full=True)['checkpoint_json']) == checkpoint(p)
    p.root.call_tool('progression_command', dict(command='pause'))
    expected = status(p)['loop']
    p.runtime.runs._synchronous_archive_fixture = True
    archive = SynchronousFixtureArchive(p.runtime)
    save_archive(archive, p.instance)
    assert archive.archived_model(p.instance).progression_status(p.instance)['loop'] == expected
    restore_archive(archive, p.instance)
    assert checkpoint(p)['admissions']['retained-background-task'] == background
    assert p.runtime.scheduler_bindings.progression_status(instance_id=p.instance)['loop'] == expected


def test_detail_snapshot_replacement_and_failure_roll_back_together(paused):
    p = paused
    bindings = p.runtime.scheduler_bindings
    prior = checkpoint(p)
    for snapshots in ({'decision_snapshot': {'runs': [{'name': 'long-' + str(i)} for i in range(5000)]},
                       'processed_snapshot': None, 'terminal_delivery': {}},
                      {'decision_snapshot': {}, 'processed_snapshot': {}, 'terminal_delivery': None}):
        with bindings._connect() as db:
            raw = store_checkpoint(db, p.instance, {**prior, **snapshots})
            db.execute('UPDATE scheduler_progression SET checkpoint_json=? WHERE instance_id=?', (raw, p.instance))
        restored = checkpoint(p)
        for name, value in snapshots.items():
            assert restored[name] == value
        assert not (SNAPSHOTS & json.loads(physical(p)[0]).keys())
    before = physical(p)
    with pytest.raises(ValueError, match='capacity'):
        with bindings._connect() as db:
            store_checkpoint(db, p.instance, {**checkpoint(p), 'usage_records': {'would-write': {}},
                'terminal_delivery': {'would': 'replace'}, 'oversized_active_field': 'x' * 65537})
    assert physical(p) == before
    with bindings._connect() as db:
        raw = store_checkpoint(db, p.instance, {**checkpoint(p), 'usage_records': {}})
        db.execute('UPDATE scheduler_progression SET checkpoint_json=? WHERE instance_id=?', (raw, p.instance))
    assert checkpoint(p)['usage_records'] == {}
    replacement = checkpoint(p)
    replacement.pop('terminal_delivery')
    replacement.pop('usage_records')
    with pytest.raises(ValueError, match='Incomplete control detail projection'):
        with bindings._connect() as db:
            store_checkpoint(db, p.instance, replacement)
    replacement['usage_records'] = {}
    with bindings._connect() as db:
        raw = store_checkpoint(db, p.instance, replacement)
        db.execute('UPDATE scheduler_progression SET checkpoint_json=? WHERE instance_id=?', (raw, p.instance))
    assert 'terminal_delivery' not in checkpoint(p) and checkpoint(p)['usage_records'] == {}
    assert not any(item[0] == 'usage_records' or item[:2] == ('snapshot', 'terminal_delivery')
        for item in physical(p)[1])


def test_detail_reference_missing_is_not_silently_empty(paused):
    p = paused
    with p.runtime.scheduler_bindings._connect() as db:
        db.execute("DELETE FROM scheduler_progression_details WHERE instance_id=? AND collection='admissions'",
            (p.instance,))
    with pytest.raises(ValueError, match='detail records differ'):
        row(p)



def test_usage_history_persists_over_64_identities_without_reset(progression, monkeypatch):
    from tests.operations.test_scientific_progress import active
    from scidiscovery.artifact_agent.service.progression_budget import token_budget
    p = progression
    from tests.operations.research_loop_fixtures import authorize_loop
    p.root.call_tool('progression_command', dict(command='pause'))
    settings = p.runtime.scheduler_bindings.global_settings
    p.runtime.scheduler_bindings.global_settings = settings.model_copy(update=dict(
        progression=settings.progression.model_copy(update=dict(max_tasks=30))))
    authorize_loop(p.runtime, p.instance, p.user, 'goal')
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='goal'))
    active(p)
    identities = {f'worker-{i}': {'role': 'worker', 'loop_id': checkpoint(p)['current_loop_id']} for i in range(96)}
    identities.update({f'human-{i}': {'role': 'worker', 'interactive_session_id': 'human-scope'} for i in range(96)})
    monkeypatch.setattr(p.coordinator, '_identities', lambda: identities)
    def usage(thread, total):
        p.coordinator._event(dict(method='thread/tokenUsage/updated', params=dict(threadId=thread,
            tokenUsage=dict(total=dict(inputTokens=total, cachedInputTokens=0, outputTokens=1)))))
    for thread in identities:
        usage(thread, 10)
    before = checkpoint(p)
    assert len(before['usage_records']) == 97  # 96 measured Workers and the pending Root identity.
    assert len(before['interactive_usage_records']) == 96
    usage('worker-0', 15)
    usage('worker-0', 15)
    usage('human-0', 17)
    current = checkpoint(p)
    limits = json.loads(row(p)['config_json'])['effective']['progression']
    assert token_budget(current, limits)['remaining_tokens'] == limits['max_tokens'] - 96*11 - 5
    assert current['interactive_usage_records']['human-0']['counted_tokens']['input_tokens'] == 17
    assert len(json.dumps(current)) > 65536 and len(physical(p)[0]) < 65536
    reopened = SchedulerBindingService(p.runtime.scheduler_bindings.database_path)
    with reopened._connect() as db:
        from scidiscovery.artifact_agent.service.progression_records import read_control_row
        assert json.loads(read_control_row(db, p.instance, full=True)['checkpoint_json']) == current


def test_checkpoint_update_failure_rolls_back_details_at_runtime_entry(paused):
    import sqlite3
    p = paused
    bindings = p.runtime.scheduler_bindings
    before = physical(p)
    with bindings._connect() as db:
        db.execute("CREATE TRIGGER reject_checkpoint BEFORE UPDATE OF checkpoint_json ON scheduler_progression "
            "BEGIN SELECT RAISE(ABORT, 'simulated_checkpoint_failure'); END")
    try:
        with pytest.raises(sqlite3.IntegrityError, match='simulated_checkpoint_failure'):
            bindings.observe_progression(instance_id=p.instance, expected_host=None,
                changes={'terminal_delivery': {'must': 'roll back'}, 'interactive_usage_records': {'new': {}}})
        assert physical(p) == before
    finally:
        with bindings._connect() as db:
            db.execute('DROP TRIGGER reject_checkpoint')


def test_archive_scopes_detail_rows_and_preserves_detail_only_artifact_refs(archive_system):
    from tests.operations.test_instance_archive import artifact, save_archive, restore_archive
    runtime, archive, first, second = archive_system
    bindings = runtime.scheduler_bindings
    user = 'sch_' + 'a' * 32
    bindings.progression_command(instance_id=first, session_key=user, command='start')
    bindings.progression_command(instance_id=first, session_key=user, command='pause')
    unique = artifact(runtime, first, 'detail-only', b'unique control original')
    shared = artifact(runtime, first, 'detail-shared', b'shared control original')
    refs = {'unique': unique.ref.model_dump(mode='json'), 'shared': shared.ref.model_dump(mode='json')}
    with bindings._connect() as db:
        db.execute("DELETE FROM scheduler_bindings WHERE instance=? AND namespace='artifact'", (first,))
        value = store_checkpoint(db, first, {'admissions': {'first-history': refs}})
        db.execute('UPDATE scheduler_progression SET checkpoint_json=? WHERE instance_id=?', (value, first))
        store_checkpoint(db, second, {'admissions': {'second-history': {'shared': refs['shared']}}})
        second_before = [tuple(item) for item in db.execute(
            'SELECT * FROM scheduler_progression_details WHERE instance_id=?', (second,))]
    save_archive(archive, first)
    archived = archive.archived_model(first)
    assert archived.artifacts.read(unique.ref) == b'unique control original'
    assert runtime.artifacts.read(shared.ref) == b'shared control original'
    with bindings._connect() as db:
        assert not db.execute('SELECT 1 FROM scheduler_progression_details WHERE instance_id=?', (first,)).fetchone()
        assert [tuple(item) for item in db.execute('SELECT * FROM scheduler_progression_details WHERE instance_id=?',
            (second,))] == second_before
    restore_archive(archive, first)
    restored = json.loads(bindings.progression_status(instance_id=first, internal=True)['checkpoint_json'])
    assert restored['admissions'] == {'first-history': refs}
    assert runtime.artifacts.read(unique.ref) == b'unique control original'




def large_native_handoff_fixture(ui, context_bytes=49152):
    p = ui.p
    assert submit(ui) == 303
    names = [f'large-native-result-{index:04d}-' + 'x' * 100 for index in range(72)]
    ui_loop_history(ui, names, context_bytes=context_bytes)
    from tests.operations.test_research_loop_budget import LoopHost
    p.coordinator.host_factory = LoopHost  # A new loop cannot reuse the old Root native thread.
    p.root.call_tool('progression_command', dict(command='pause'))
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='goal'))
    return names


@pytest.mark.parametrize('context_bytes', [49152, 10000])
def test_large_handoff_real_tick_bounds_prompt_and_settles_only_visible_tasks(human_ui, context_bytes):
    from tests.operations.test_progress_assist import next_turn
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    ui, p = human_ui, human_ui.p
    names = large_native_handoff_fixture(ui, context_bytes)
    next_turn(p)
    host = p.coordinator.host
    assert row(p)['state'] == 'active' and len(host.prompts) == 1
    limit = json.loads(row(p)['config_json'])['effective']['progression']['context_bytes']
    assert len(host.prompts[0].encode()) <= limit
    brief = json.loads(host.prompts[0].split('\n')[-1])
    shown = {entry['name'] for entry in brief['changes']} & set(names)
    omitted = set(names) - shown
    assert omitted
    if context_bytes == 49152:
        assert shown
    assert {entry['name'] for entry in checkpoint(p)['decision_snapshot']['runs']} & set(names) == shown
    root = p.root.__class__(p.facade(host.scheduler_session))
    query = dict(view='summary', limit=8)
    page = root.call_tool('run_list', query)
    assert set(page['current_goal_tasks']) <= {entry['name'] for entry in page['runs']}
    found = set(page['current_goal_tasks'])
    while not found & omitted and page['next_before']:
        page = root.call_tool('run_list', dict(query, before=page['next_before']))
        found.update(page['current_goal_tasks'])
    assert found & omitted  # Existing semantic-name cursor finds an omitted exact member.
    # A Python-side read is not a native model-delivery receipt.
    host.finish()
    objective = ArtifactRef.model_validate_json(row(p)['objective_ref_json'])
    records = handoff_delivery_records(p, objective)
    settled = {entry['task_name'] for entry in records if entry['consumed_boundary']} & set(names)
    assert settled == shown
    previous_rounds = len(host.prompts)
    next_turn(p)
    if context_bytes == 10000 and not shown:
        assert len(host.prompts) == previous_rounds  # Same wholly omitted cohort is already notified.
        p.root.call_tool('progression_message', dict(name='handoff.read.omitted',
            text='Read the exact omitted handoff results through the supplied original-reading entrance.'))
        next_turn(p)
        assert len(host.prompts) == previous_rounds + 1
    following = json.loads(host.prompts[-1].split('\n')[-1])
    assert not ({entry['name'] for entry in following['changes']} & shown)

    # An actual structured native read can subsequently deliver a task omitted
    # from both briefs; membership listing without that receipt did not do so.
    from tests.operations.test_progress_shadow import native_delivery
    shown_next = {entry['name'] for entry in following['changes']} & set(names)
    page = root.call_tool('run_list', query)
    candidates = set(page['current_goal_tasks']) & (omitted - shown_next)
    while not candidates and page['next_before']:
        page = root.call_tool('run_list', dict(query, before=page['next_before']))
        candidates = set(page['current_goal_tasks']) & (omitted - shown_next)
    assert candidates
    read_name = next(iter(candidates))
    # This helper calls the actual MCP run_status before emitting its native receipt.
    native_delivery(p, root, read_name)
    assert read_name in {entry['name'] for entry in checkpoint(p)['decision_snapshot']['runs']}
    host.finish()
    records = handoff_delivery_records(p, objective)
    settled = {entry['task_name'] for entry in records if entry['consumed_boundary']} & set(names)
    assert settled == shown | shown_next | {read_name}



def handoff_delivery_records(p, objective):
    records, after = [], 0
    while True:
        page = p.runtime.scheduler_bindings.terminal_deliveries(instance_id=p.instance,
            objective_ref=objective, after=after, limit=101)
        records.extend(page)
        if len(page) < 101:
            return records
        after = page[-1]['sequence']


def test_current_goal_run_list_members_are_bound_to_current_instance_and_goal(human_ui):
    ui, p = human_ui, human_ui.p
    assert submit(ui) == 303
    finish(p, p.root, 'current-goal-result')
    before = row(p)
    page = p.root.call_tool('run_list', dict(view='summary', limit=100))
    assert 'current-goal-result' in page['current_goal_tasks']
    assert row(p) == before
    bindings = p.runtime.scheduler_bindings
    other = bindings.create_instance(name='unrelated-listing', title='Other', objective='Independent scope')
    bindings.bind_session(session_key='other-reader', instance_id=other.instance_id)
    reader = p.root.__class__(p.facade('other-reader'))
    assert reader.call_tool('run_list', dict(limit=8)) == dict(runs=[], next_before=None)
    p.root.call_tool('artifact_ingest_text', dict(name='another-goal', text='A different exact goal.'))
    p.root.call_tool('progression_command', dict(command='pause'))
    p.root.call_tool('progression_command', dict(command='start', objective_name='another-goal'))
    before = row(p)
    assert 'current-goal-result' not in p.root.call_tool('run_list', dict(limit=100)).get('current_goal_tasks', [])
    assert row(p) == before
