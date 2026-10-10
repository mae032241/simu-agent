"""Explicit same-child gateway recovery and settled-host dispatch notices; no model."""
import json

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
from scidiscovery.artifact_agent.service.run_records import RunStateConflict
from tests.operations.test_unified_mcp import queued, call, result, separate_proxy_gateway
from tests.operations.test_progression import progression, checkpoint, row
from tests.operations.test_local_worker_contracts import _invoke
from tests.operations.test_progression_attention import poll, rendered


def projection(runtime, run_id):
    with runtime.runs._connect() as db:
        item = db.execute('SELECT version,diagnostic_json FROM run_attention_notices WHERE run_id=?', (run_id,)).fetchone()
    return (item['version'], json.loads(item['diagnostic_json'])) if item else None


@pytest.mark.parametrize('secret', [None, b'explicit-dispatch-test'])
def test_normal_dispatch_retains_explicit_attachment_even_with_secret(tmp_path, secret):
    _, runtime, root, gateway, profile = queued(tmp_path)
    root.facade.instance_management_secret = secret
    dispatch = result(call(gateway, 'run_status', dict(name='observation', intent='navigation')))['dispatch']
    assert 'bootstrap' not in dispatch
    assert dispatch['attachment']['tool'] == 'worker_attach'
    assert 'followup_task' in dispatch['instruction'] and 'same child' in dispatch['instruction']
    assert 'at most one bounded' in dispatch['instruction']
    assert runtime.runs.status(root.facade._resolve('run', 'observation')).state == 'queued'


def test_trusted_attach_failure_resolves_only_after_actual_same_child_open(tmp_path, monkeypatch):
    _, runtime, root, gateway, profile = queued(tmp_path)
    run_id = root.facade._resolve('run', 'observation')
    original = gateway.connections.attach
    def broken(**kwargs):
        raise RunStateConflict('Injected storage binding conflict')
    monkeypatch.setattr(gateway.connections, 'attach', broken)
    assert 'error' in call(gateway, 'worker_attach', dict(name='observation', thread_id='actual-child'))
    version, notice = projection(runtime, run_id)
    assert notice['attention_required']['code'] == 'dispatch_attach_failed'
    assert 'actual-child' not in json.dumps(notice) and run_id not in json.dumps(notice)
    runtime.runs.reconcile_dispatch_attention(run_id, incomplete=True)
    assert projection(runtime, run_id)[0] == version  # generic observations retain specific failure
    monkeypatch.setattr(gateway.connections, 'attach', original)
    result(call(gateway, 'worker_attach', dict(name='observation', thread_id='actual-child')))
    assert projection(runtime, run_id)[0] == version
    worker = separate_proxy_gateway(root, 'independent-worker-proxy')
    opened = result(call(worker, 'worker_open_assignment', child='actual-child', profile=profile))
    assert opened['state'] == 'opened'
    resolved = projection(runtime, run_id)
    assert resolved[0] > version and resolved[1]['state'] == 'resolved'
    # A fresh router preserves exact identity and does not create another resolution.
    again = separate_proxy_gateway(root, 'reconnected-worker-proxy')
    result(call(again, 'worker_open_assignment', child='actual-child', profile=profile))
    assert projection(runtime, run_id) == resolved
    assert runtime.runs.status(run_id).state == 'running'
    assert 'error' in call(gateway, 'worker_attach', dict(name='observation', thread_id='replacement'))
    assert gateway.connections.resolve(platform_session='parent', thread_id='actual-child').run_id == run_id


def test_unbound_early_open_and_malformed_token_never_attribute_a_run(tmp_path):
    _, runtime, root, gateway, profile = queued(tmp_path)
    run_id = root.facade._resolve('run', 'observation')
    worker = separate_proxy_gateway(root, 'unbound-child-proxy')
    early = call(worker, 'worker_open_assignment', child='early', profile=profile)
    assert 'awaiting_attachment' in json.dumps(early) and 'stop this startup turn' in json.dumps(early)
    malformed = call(worker, 'worker_open_assignment', {'dispatch_token': 'not-a-signed-claim'}, child='early', profile=profile)
    assert 'error' in malformed
    assert projection(runtime, run_id) is None and runtime.runs.status(run_id).state == 'queued'
    assert 'error' in call(gateway, 'worker_attach', dict(name='observation', thread_id='parent'))
    assert projection(runtime, run_id) is None  # validation preceding trusted intent attribution
    result(call(gateway, 'worker_attach', dict(name='observation', thread_id='early')))
    assert result(call(worker, 'worker_open_assignment', child='early', profile=profile))['state'] == 'opened'


def test_queued_dispatch_notices_wait_for_root_settle_then_wake_once(progression):
    p = progression
    p.coordinator.tick()
    host = p.coordinator.host
    root = p.root.__class__(p.facade(host.scheduler_session))
    _invoke(root, 'first')
    run_id = root.facade._resolve('run', 'first')
    poll(p)  # Root is still busy dispatching.
    assert projection(p.runtime, run_id) is None
    host.finish(); p.coordinator.tick()
    version, notice = projection(p.runtime, run_id)
    assert notice['attention_required']['code'] == 'dispatch_attachment_required'
    poll(p)
    assert len(host.prompts) == 2
    event, = rendered(host)['attention_notifications']
    assert event['name'] == 'first' and event['version'] == version
    assert rendered(host)['changes'] == []
    host.finish(); p.coordinator.tick()
    for _ in range(3): poll(p)
    assert len(host.prompts) == 2 and projection(p.runtime, run_id)[0] == version
    # Use the real gateway with actual frozen Root/child coordinates; no followup adapter.
    gateway = UnifiedMCPRouter(root)
    profile = p.runtime.runs.status(run_id).execution_profile['profile']
    result(call(gateway, 'worker_attach', dict(name='first', thread_id='same-child'), session='native-root'))
    assert projection(p.runtime, run_id)[0] == version
    child = separate_proxy_gateway(root, 'worker-proxy')
    assert result(call(child, 'worker_open_assignment', child='same-child', session='native-root', profile=profile))['state'] == 'opened'
    assert projection(p.runtime, run_id)[1]['state'] == 'resolved'
    poll(p)
    assert len(host.prompts) == 3 and rendered(host)['attention_notifications'][0]['state'] == 'resolved'
    assert checkpoint(p)['terminal_delivery']['items'] == []


def test_terminal_dispatch_issue_is_superseded_preserving_failure(tmp_path):
    _, runtime, root, gateway, profile = queued(tmp_path)
    run_id = root.facade._resolve('run', 'observation')
    runtime.runs.reconcile_dispatch_attention(run_id, incomplete=True)
    status = runtime.runs.status(run_id)
    runtime.runs.record_failure(run_id, reason='Definite engineering failure', category='fixture_failure',
        expected_state=status.state, expected_last_activity_at=status.last_activity_at)
    closed = projection(runtime, run_id)
    assert closed[1]['state'] == 'superseded'
    runtime.runs.record_failure(run_id, reason='Definite engineering failure', category='fixture_failure',
        expected_state=status.state, expected_last_activity_at=status.last_activity_at)
    assert projection(runtime, run_id) == closed
    assert runtime.runs.status(run_id).state == 'failed'
    assert runtime.runs.status(run_id).reason == 'Definite engineering failure'


@pytest.mark.parametrize('outside', ['goal', 'visibility', 'generation'])
def test_pending_observation_cannot_authorize_unrelated_or_stale_dispatch(progression, outside):
    p = progression
    p.coordinator.tick()
    host = p.coordinator.host
    root = p.root.__class__(p.facade(host.scheduler_session))
    _invoke(root, 'first')
    run_id = root.facade._resolve('run', 'first')
    host.finish()
    saved = dict(row(p))
    cp = json.loads(saved['checkpoint_json'])
    if outside == 'goal':
        # Change the observed current goal, not merely its checkpoint cache;
        # the durable accepted admission still belongs to the original exact goal.
        goal = json.loads(saved['objective_ref_json'])
        saved['objective_ref_json'] = json.dumps(dict(goal, sha256='f'*64))
    elif outside == 'visibility':
        with p.runtime.scheduler_bindings._connect() as db:
            db.execute("DELETE FROM scheduler_bindings WHERE instance=? AND namespace='run' AND name='first'", (p.instance,))
    else:
        saved['generation'] += 1
    p.coordinator._reconcile_dispatch_attention(saved)
    assert projection(p.runtime, run_id) is None
    assert p.runtime.runs.status(run_id).state == 'queued'


def test_mid_deleted_legacy_token_does_not_attribute_or_consume_queued_task(tmp_path):
    from tests.operations.test_worker_bootstrap import setup, open_child, native_profile
    runtime, root, gateway, profile, bootstrap = setup(tmp_path)
    token = bootstrap['arguments']['dispatch_token']
    bootstrap['arguments']['dispatch_token'] = token[:30] + token[62:]
    assert 'error' in open_child(gateway, native_profile(profile), bootstrap)
    run_id = root.facade._resolve('run', 'observation')
    assert projection(runtime, run_id) is None
    assert runtime.runs.status(run_id).state == 'queued'
    with runtime.runs._connect() as db:
        assert db.execute('SELECT count(*) FROM worker_connections').fetchone()[0] == 0



def test_real_gateway_open_tail_failure_remains_attention_until_same_child_success(progression, monkeypatch):
    from scidiscovery.artifact_agent.service import worker_start
    p = progression
    p.coordinator.tick()
    host = p.coordinator.host
    root = p.root.__class__(p.facade(host.scheduler_session))
    _invoke(root, 'first')
    run_id = root.facade._resolve('run', 'first')
    gateway = UnifiedMCPRouter(root)
    profile = p.runtime.runs.status(run_id).execution_profile['profile']
    result(call(gateway, 'worker_attach', dict(name='first', thread_id='same-child'), session='native-root'))
    child = separate_proxy_gateway(root, 'tail-failure-child-proxy')
    original = worker_start.write_worker_start
    def broken(*args, **kwargs):
        raise RuntimeError('Injected startup-page generation failure after running transition')
    monkeypatch.setattr(worker_start, 'write_worker_start', broken)
    assert 'error' in call(child, 'worker_open_assignment', child='same-child', session='native-root', profile=profile)
    assert p.runtime.runs.status(run_id).state == 'running'
    version, notice = projection(p.runtime, run_id)
    assert notice['attention_required']['code'] == 'dispatch_open_failed'
    host.finish(); p.coordinator.tick(); poll(p)
    assert projection(p.runtime, run_id)[0] == version
    assert rendered(host)['attention_notifications'][0]['state'] == 'attention_required'
    host.finish(); p.coordinator.tick()
    for _ in range(2): poll(p)
    assert projection(p.runtime, run_id)[0] == version and len(host.prompts) == 2
    monkeypatch.setattr(worker_start, 'write_worker_start', original)
    assert result(call(child, 'worker_open_assignment', child='same-child', session='native-root', profile=profile))['state'] == 'opened'
    resolved = projection(p.runtime, run_id)
    assert resolved[0] > version and resolved[1]['state'] == 'resolved'
    poll(p)
    assert rendered(host)['attention_notifications'][0]['state'] == 'resolved'
    assert p.runtime.runs.status(run_id).state == 'running'
    assert result(call(child, 'worker_open_assignment', child='same-child', session='native-root', profile=profile))['state'] == 'opened'
    assert projection(p.runtime, run_id) == resolved



def test_actual_completed_transaction_supersedes_dispatch_without_idle_reconcile(tmp_path):
    from pathlib import Path
    from blind_csv_plugin.contracts import CSV_SCHEMA_PROBE
    _, runtime, root, gateway, profile = queued(tmp_path)
    run_id = root.facade._resolve('run', 'observation')
    result(call(gateway, 'worker_attach', dict(name='observation', thread_id='child')))
    child = dict(child='child', profile=profile)
    opened = result(call(gateway, 'worker_open_assignment', **child))
    # A later failed legacy open by this actual bound child is a dispatch issue;
    # a terminal submit must close it even when no background coordinator is active.
    assert 'error' in call(gateway, 'worker_open_assignment', {'dispatch_token': 'bad-legacy-claim'}, **child)
    assert projection(runtime, run_id)[1]['attention_required']['code'] == 'dispatch_open_failed'
    structure = result(call(gateway, 'worker_csv_summarize', **child))
    content = dict(schema_version=1, handoff=dict(verdict='pass', summary='Bounded result.'),
        payload=dict(schema_probe=CSV_SCHEMA_PROBE, structure=structure, interpretation='The mean is two.',
            limitations=['Two rows do not establish causality.']))
    Path(opened['output_directory'], 'result.json').write_text(json.dumps(content))
    assert result(call(gateway, 'worker_submit_result', **child))['state'] == 'completed'
    closed = projection(runtime, run_id)
    assert closed[1]['state'] == 'superseded'
    assert runtime.runs.status(run_id).state == 'completed'
    assert runtime.runs.submit(run_id)[0] == 'completed'
    assert projection(runtime, run_id) == closed
