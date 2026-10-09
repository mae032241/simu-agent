"""Versioned goal-scoped control notices wake an idle host without consuming science."""
import json
import hashlib

import pytest

from scidiscovery.artifact_agent.service.progression_records import store_checkpoint
from scidiscovery.artifact_agent.service.progression import ProgressionFault
from tests.operations.test_local_worker_contracts import _invoke, _worker
from tests.operations.test_progression import progression, checkpoint, row


def idle_running_task(p):
    p.coordinator.tick()
    host = p.coordinator.host
    root = p.root.__class__(p.facade(host.scheduler_session))
    _invoke(root, 'first')
    worker = _worker(p.catalog, p.runtime)
    worker.call_tool('worker_open_assignment', {})
    host.finish()
    p.coordinator.tick()
    return host, worker._run_id


def poll(p):
    p.now[0] += 6
    p.coordinator.tick()


def notice(p, run_id, code='submission_intervention_required'):
    p.runtime.runs.record_attention(run_id, scope='submission:fixture', code=code)


def rendered(host):
    return json.loads(host.prompts[-1].split('\n')[-1])


def clone_notice_run(p, run_id, index, *, in_goal=True, visible=True, foreign=False):
    """Synthetic distinct-operation notification scale; no native/admission qualification.

    Retain the production active-operation unique index. Unknown synthetic digests
    model independent Operations solely for control status/notice projection.
    """
    name = f'notice-{index:02d}'
    identity = 'run_' + f'{index:032x}'
    instance = p.instance
    if foreign:
        instance = p.runtime.scheduler_bindings.create_instance(name=name, title=name, objective='Another goal.').instance_id
    with p.runtime.runs._connect() as db:
        saved = dict(db.execute('SELECT * FROM runs WHERE run_id=?', (run_id,)).fetchone())
        saved.update(run_id=identity, instance_id=instance, output_binding_name=name+'.output',
            output_logical_name=name+'.output', output_binding_fingerprint=f'{index:064x}', request_digest=f'{index:064x}',
            operation_digest=hashlib.sha256(('notification-scale:'+name).encode()).hexdigest())
        db.execute('INSERT INTO runs ('+','.join(saved)+') VALUES ('+','.join('?' for _ in saved)+')', tuple(saved.values()))
    if visible:
        p.runtime.scheduler_bindings.bind(instance=instance, namespace='run', name=name, object_id=identity)
        if not foreign:
            # Control reads must remain usable even though this fixture does not
            # register/qualify an executable scientific operation for the digest.
            status = p.facade(p.coordinator.host.scheduler_session).run_status(name=name, intent='status', scheduler_view=True)
            assert status['state'] == 'running'
    cp = checkpoint(p)
    goal = json.loads(row(p)['objective_ref_json'])
    if not in_goal:
        goal = dict(goal, sha256='f'*64)
    cp['admissions'][name] = dict(cp['admissions']['first'], run_id=identity, objective_ref=goal)
    with p.runtime.scheduler_bindings._connect() as db:
        db.execute('UPDATE scheduler_progression SET checkpoint_json=? WHERE instance_id=?',
            (store_checkpoint(db, p.instance, cp), p.instance))
    return name, identity


def test_running_attention_wakes_once_per_version_without_terminal_consumption(progression):
    p = progression
    host, run_id = idle_running_task(p)
    notice(p, run_id)
    # Other Root readers have independent notification cursors, never swallowing this wake.
    assert p.root.call_tool('instance_current', {})['attention_notifications']['events']
    poll(p)
    assert len(host.prompts) == 2
    brief = rendered(host)
    event, = brief['attention_notifications']
    assert event['name'] == 'first' and event['state'] == 'attention_required'
    assert event['attention_required']['code'] == 'submission_intervention_required'
    assert event['read_request']['arguments'] == dict(name='first', intent='status', diagnostic_after=0, diagnostic_limit=8)
    assert run_id not in json.dumps(event) and 'submission:fixture' not in json.dumps(event)
    assert brief['changes'] == [] and checkpoint(p)['terminal_delivery']['items'] == []
    assert p.runtime.runs.status(run_id).state == 'running'
    host.finish(); p.coordinator.tick()
    version = checkpoint(p)['processed_snapshot']['attention_notices'][0]['version']
    notice(p, run_id)  # Same code updates last_seen, not notice version.
    for _ in range(3): poll(p)
    assert len(host.prompts) == 2
    assert checkpoint(p)['processed_snapshot']['attention_notices'][0]['version'] == version
    notice(p, run_id, None)
    poll(p)
    assert len(host.prompts) == 3
    resolved, = rendered(host)['attention_notifications']
    assert resolved['state'] == 'resolved' and resolved['version'] > version
    assert 'read_request' not in resolved
    host.finish(); p.coordinator.tick()
    notice(p, run_id)
    poll(p)
    assert len(host.prompts) == 4 and rendered(host)['attention_notifications'][0]['version'] > resolved['version']
    assert p.runtime.runs.status(run_id).state == 'running'
    host.finish(); p.coordinator.tick(); poll(p)
    assert len(host.prompts) == 4


def test_ten_attention_versions_are_delivered_in_batches_then_stay_silent(progression):
    p = progression
    host, run_id = idle_running_task(p)
    expected = {'first'}
    notice(p, run_id)
    for index in range(1, 10):
        name, identity = clone_notice_run(p, run_id, index)
        expected.add(name); notice(p, identity)
    poll(p)
    first = rendered(host)
    assert len(first['attention_notifications']) == 8 and first['attention_omissions'] == 2
    first_names = {event['name'] for event in first['attention_notifications']}
    assert len(checkpoint(p)['decision_snapshot']['attention_notices']) == 8
    assert checkpoint(p)['terminal_delivery']['items'] == []
    host.finish(); p.coordinator.tick(); poll(p)
    second = rendered(host)
    second_names = {event['name'] for event in second['attention_notifications']}
    assert len(second_names) == 2 and not first_names & second_names
    assert first_names | second_names == expected
    assert len(checkpoint(p)['decision_snapshot']['attention_notices']) == 10
    host.finish(); p.coordinator.tick()
    for _ in range(3): poll(p)
    assert len(host.prompts) == 3


def test_capacity_omission_stays_pending_without_repeated_empty_wake(progression, monkeypatch):
    p = progression
    host, run_id = idle_running_task(p)
    notice(p, run_id)
    original = p.coordinator._brief
    saved = row(p)
    snapshot = p.coordinator._snapshot(saved)
    # Find a real byte budget that fits only the omission entrance, not the event.
    # All calls are pure fixture projections; no native/model turn is requested.
    low, high = 1, len(original(saved, snapshot, 50000).split('\n')[-1].encode())
    while low < high:
        mid = (low + high) // 2
        try:
            original(saved, snapshot, mid)
        except ProgressionFault:
            low = mid + 1
        else:
            high = mid
    low += 64  # Leave room for changing elapsed-budget digits before the real fixture tick.
    limited = json.loads(original(saved, snapshot, low).split('\n')[-1])
    assert limited['attention_notifications'] == [] and limited['attention_omitted_read']
    assert len(json.dumps(limited, ensure_ascii=False, separators=(',', ':')).encode()) <= low
    monkeypatch.setattr(p.coordinator, '_brief', lambda row, snapshot, limit: original(row, snapshot, min(limit, low)))
    poll(p)
    assert len(host.prompts) == 2 and checkpoint(p)['decision_snapshot']['attention_notices'] == []
    host.finish(); p.coordinator.tick()
    for _ in range(3): poll(p)
    assert len(host.prompts) == 2  # An omitted version is pending, not an endless empty wake.
    monkeypatch.setattr(p.coordinator, '_brief', original)
    poll(p)
    assert len(host.prompts) == 3 and rendered(host)['attention_notifications'][0]['name'] == 'first'
    host.finish(); p.coordinator.tick(); poll(p)
    assert len(host.prompts) == 3


@pytest.mark.parametrize('outside', ['goal', 'visibility', 'instance'])
def test_attention_outside_exact_visible_goal_does_not_wake(progression, outside):
    p = progression
    host, run_id = idle_running_task(p)
    _, other = clone_notice_run(p, run_id, 20, in_goal=outside!='goal',
        visible=outside!='visibility', foreign=outside=='instance')
    notice(p, other)
    for _ in range(3): poll(p)
    assert len(host.prompts) == 1
    assert not p.coordinator._snapshot(row(p)).get('attention_notices')
