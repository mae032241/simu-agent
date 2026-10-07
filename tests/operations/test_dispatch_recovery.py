"""Trusted native restoration retains exact dispatch authority, without replay."""
import json

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
from scidiscovery.artifact_agent.service.progression_records import store_checkpoint
from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerInstanceConflict
from tests.operations.test_progression import progression, Host, checkpoint, row
from tests.operations.test_local_worker_contracts import _invoke
from tests.operations.test_unified_mcp import call, result


def accepted(p, name='accepted'):
    if p.coordinator.host is None:
        p.coordinator.tick()
    root = type(p.root)(p.facade(p.coordinator.host.scheduler_session))
    _invoke(root, name)
    return dict(root.facade.run_status(name=name), run_id=root.facade._resolve('run', name))


def restore(p, session):
    old = p.coordinator.host
    old.close()
    p.coordinator.host = None
    def factory(record, event):
        host = Host(record, event)
        host.scheduler_session = session
        host.completion = dict(id=host.turn_id, status='interrupted')
        return host
    p.coordinator.host_factory = factory
    p.now[0] += 6
    p.coordinator.tick()
    return old


def dispatches(p):
    with p.runtime.scheduler_bindings._connect() as db:
        return [tuple(item) for item in db.execute('SELECT * FROM scheduler_dispatch_intents ORDER BY run_id')]


def attach(p, session, name='accepted', thread='actual-child'):
    gateway = UnifiedMCPRouter(type(p.root)(p.facade(session)))
    return gateway, call(gateway, 'worker_attach', dict(name=name, thread_id=thread), session='native-root')


def save(p, cp):
    with p.runtime.scheduler_bindings._connect() as db:
        db.execute('UPDATE scheduler_progression SET checkpoint_json=? WHERE instance_id=?',
            (store_checkpoint(db, p.instance, cp), p.instance))


def test_interrupted_native_root_new_owner_attaches_exact_accepted_worker_without_replay(progression):
    p = progression
    status = accepted(p)
    before = checkpoint(p)
    intents = dispatches(p)
    new = 'sch_' + 'c' * 32
    old = restore(p, new)
    cp = checkpoint(p)
    proof = cp['admissions']['accepted']['dispatch_continuation']
    assert proof['run_id'] == status['run_id'] and proof['loop_id'] == before['current_loop_id']
    assert (proof['intent_owner'], proof['intent_generation']) == (old.scheduler_session, row(p)['generation'] - 1)
    assert (proof['owner'], proof['generation']) == (new, row(p)['generation'])
    assert cp['recovery']['last_failure']['code'] == 'native_turn_interrupted'
    assert cp['rounds'] == before['rounds'] and cp['started_at'] == before['started_at']
    assert dispatches(p) == intents and len(p.runtime.runs.list(instance_id=p.instance)) == 1
    assert not p.coordinator.host.prompts and not p.coordinator.host.restored
    # A stale Root cannot choose a new attachment; the current Root supplies the
    # actual already-started child coordinates, without spawning a replacement.
    _, denied = attach(p, old.scheduler_session)
    assert 'error' in denied
    with pytest.raises(SchedulerInstanceConflict, match='Native start state is unknown'):
        p.runtime.scheduler_bindings.require_dispatch_intent(instance_id=p.instance, run_id=status['run_id'],
            session_key=old.scheduler_session, generation=proof['intent_generation'])
    gateway, reply = attach(p, new)
    assert result(reply)['state'] == 'attached'
    duplicate = result(call(gateway, 'worker_attach', dict(name='accepted', thread_id='actual-child'), session='native-root'))
    assert duplicate['state'] == 'attached'
    opened = result(call(gateway, 'worker_open_assignment', child='actual-child', session='native-root',
        profile=status['execution_profile']['profile']))
    assert opened['state'] == 'opened' and p.runtime.runs.status(status['run_id']).state == 'running'
    assert result(call(gateway, 'worker_attach', dict(name='accepted', thread_id='actual-child'), session='native-root'))['state'] == 'attached'
    assert 'error' in call(gateway, 'worker_attach', dict(name='accepted', thread_id='replacement-child'), session='native-root')
    assert dispatches(p) == intents


@pytest.mark.parametrize('invalid', ['unknown', 'prepared_turn', 'prepared_admission', 'other_loop', 'other_run', 'other_host', 'other_intent'])
def test_recovered_dispatch_rejects_unresolved_or_mismatched_authority(progression, invalid):
    p = progression
    accepted(p)
    new = 'sch_' + 'c' * 32
    restore(p, new)
    cp = checkpoint(p)
    admission = cp['admissions']['accepted']
    if invalid == 'unknown':
        cp['fault_class'] = 'outcome_unknown'
    elif invalid == 'prepared_turn':
        cp.update(phase='prepared', turn_id=None)
    elif invalid == 'prepared_admission':
        admission['state'] = 'prepared'
    elif invalid == 'other_loop':
        admission['dispatch_continuation']['loop_id'] = 'different-loop'
    elif invalid == 'other_run':
        admission['dispatch_continuation']['run_id'] = 'different-run'
    elif invalid == 'other_host':
        admission['dispatch_continuation']['host']['thread_id'] = 'different-root'
    else:
        admission['dispatch_continuation']['intent_generation'] += 1
    save(p, cp)
    _, reply = attach(p, new)
    assert 'error' in reply
    with p.runtime.runs._connect() as db:
        assert db.execute('SELECT COUNT(*) FROM worker_connections').fetchone()[0] == 0


def test_repeated_trusted_restoration_carries_only_original_exact_intent(progression):
    p = progression
    status = accepted(p)
    intents = dispatches(p)
    middle = 'sch_' + 'c' * 32
    restore(p, middle)
    bindings = p.runtime.scheduler_bindings
    final = 'sch_' + 'd' * 32
    bindings.reconnect_host(instance_id=p.instance, scheduler_session=final,
        platform_session='native-root', thread_id='native-root', expected_generation=row(p)['generation'])
    _, denied = attach(p, middle)
    assert 'error' in denied
    assert result(attach(p, final)[1])['state'] == 'attached'
    assert dispatches(p) == intents
    with pytest.raises(SchedulerInstanceConflict, match='ownership changed'):
        bindings.reconnect_host(instance_id=p.instance, scheduler_session=middle,
            platform_session='foreign-root', thread_id='foreign-root', expected_generation=row(p)['generation'])
    assert p.runtime.runs.status(status['run_id']).state == 'queued'


@pytest.mark.parametrize('unresolved', ['unknown', 'prepared_admission'])
def test_restoration_cannot_mint_authority_from_unknown_submission(progression, unresolved):
    p = progression
    accepted(p)
    cp = checkpoint(p)
    if unresolved == 'unknown':
        cp['fault_class'] = 'outcome_unknown'
    else:
        cp['admissions']['accepted']['state'] = 'prepared'
    save(p, cp)
    bindings = p.runtime.scheduler_bindings
    new = 'sch_' + 'c' * 32
    bindings.reconnect_host(instance_id=p.instance, scheduler_session=new,
        platform_session='native-root', thread_id='native-root', expected_generation=row(p)['generation'])
    assert 'dispatch_continuation' not in checkpoint(p)['admissions']['accepted']
    assert 'error' in attach(p, new)[1]
