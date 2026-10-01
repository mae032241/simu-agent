"""Enabled time is one durable budget across pauses, hosts and public controls."""
import json
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from tests.operations.test_progression import progression, row, checkpoint, Host
from tests.operations.test_progress_assist import configure
from tests.operations.test_human_progress_continuation import human_ui, paused, submit, fresh_binding, independent
from tests.operations.test_scientific_progress import active


@pytest.mark.parametrize('unknown', [False, True])
def test_same_host_resume_refreshes_deadline_only_after_confirmed_turn(progression, monkeypatch, unknown):
    from scidiscovery.platforms import codex_progression
    from scidiscovery.platforms.codex_app_server import AppServer, HostError
    from scidiscovery.platforms.codex_root_host import CodexRootHost
    p = progression
    monkeypatch.setattr(codex_progression, 'time', SimpleNamespace(monotonic=lambda: p.now[0]))

    class GuardedHost(Host):
        set_execution_deadline = codex_progression.CodexProgressionHost.set_execution_deadline
        guard_resources = codex_progression.CodexProgressionHost.guard_resources
        interrupt = CodexRootHost.interrupt
        poll = CodexRootHost.poll

        def __init__(self, record, event):
            super().__init__(record, event)
            self.execution_deadline = None
            self.resource_limit = None
            self.terminal_transport_error = None
            self.connection = object.__new__(AppServer)
            self.connection.closed = self.connection.failed = False
            self.connection.checkpoint = self.guard_resources
            self.connection.selector = SimpleNamespace(select=lambda _: [])

    monkeypatch.setattr(p.coordinator, 'host_factory', GuardedHost)
    active(p)
    host = p.coordinator.host
    p.now[0] += 10
    host.finish()  # Matching native completion; no coordinator tick during pause/resume.
    if unknown:
        p.coordinator._save(dict(phase='prepared', turn_id=None, fault_class='outcome_unknown'))
    original_deadline = host.execution_deadline
    p.root.call_tool('progression_command', dict(command='pause'))
    limit = json.loads(row(p)['config_json'])['effective']['progression']['max_elapsed_seconds']
    p.now[0] += limit * 2
    p.root.call_tool('progression_command', dict(command='resume'))
    if unknown:
        with pytest.raises(HostError, match='budget_deadline'):
            p.coordinator.tick()
        assert host.execution_deadline == original_deadline and host.connection.failed
        assert row(p)['host_json'] is not None and checkpoint(p)['fault_class'] == 'outcome_unknown'
        assert len(host.prompts) == 1 and checkpoint(p)['enabled_seconds'] >= limit * 2
        return
    p.coordinator.tick()  # Uses real AppServer.poll and native budget guard, without a process/model.
    assert p.coordinator.host is host and not host.connection.failed
    assert row(p)['state'] == 'active' and checkpoint(p).get('fault_code') is None
    assert host.execution_deadline == p.coordinator._goal_deadline == p.now[0] + limit - 10
    assert p.root.call_tool('progression_status', {})['budget']['elapsed_seconds'] == 10


def test_preconnect_human_continue_initializes_time_and_first_host_preserves_it(progression):
    p = progression
    configure(p)
    p.root.call_tool('progression_command', dict(command='pause'))
    assert p.coordinator.host is None and 'started_at' not in checkpoint(p)
    with contextmanager(human_ui.__wrapped__)(p) as ui:
        assert submit(ui) == 303
        p.now[0] += 10
        assert p.root.call_tool('progression_status', {})['budget']['elapsed_seconds'] == 10
        # Existing diagnostic counters must survive the first native connection too.
        p.runtime.scheduler_bindings.observe_progression(instance_id=p.instance,
            expected_host=None, changes=dict(probes=7, rounds=2, attempts=1))
        p.root.call_tool('progression_command', dict(command='pause'))
        p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='goal'))
        active(p)
        cp = checkpoint(p)
        assert cp['enabled_seconds'] == 10 and cp['rounds'] == 3 and cp['attempts'] == 1
        assert cp['probes'] >= 7
        limit = json.loads(row(p)['config_json'])['effective']['progression']['max_elapsed_seconds']
        assert p.coordinator._goal_deadline == p.now[0] + limit - 10


def test_more_than_720_unchanged_polls_do_not_spend_a_poll_allowance(progression):
    p = progression
    configure(p, max_elapsed_seconds=10000)
    active(p)
    host = p.coordinator.host
    host.finish()
    for _ in range(721):
        p.now[0] += 5
        p.coordinator.tick()
    assert row(p)['state'] == 'active'
    assert len(host.prompts) == 1 and checkpoint(p)['probes'] > 720
    assert 'max_probes' not in json.loads(row(p)['config_json'])['effective']['progression']


def test_long_pause_retired_manual_exemption_and_human_continue_share_the_original_time(human_ui, monkeypatch):
    ui, p = human_ui, human_ui.p
    before = p.root.call_tool('progression_status', {})['budget']['elapsed_seconds']
    started = checkpoint(p)['started_at']
    limit = json.loads(row(p)['config_json'])['effective']['progression']['max_elapsed_seconds']
    p.now[0] += limit * 2
    assert submit(ui, confirmation_binding=fresh_binding(ui)) == 303
    p.now[0] += 10  # Same-budget human continuation is enabled work.
    assert p.root.call_tool('progression_status', {})['budget']['elapsed_seconds'] == before + 10
    p.root.call_tool('progression_command', dict(command='pause'))
    assert independent(ui) == 403
    assert not checkpoint(p).get('interactive_sessions')
    p.now[0] += limit * 2
    assert p.root.call_tool('progression_status', {})['budget']['elapsed_seconds'] == before + 10
    p.root.call_tool('progression_command', dict(command='pause'))
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='goal'))
    remaining = []
    def factory(record, event):
        remaining.append(record['_execution_remaining_seconds'])
        host = Host(record, event)
        host.set_execution_deadline = lambda value: remaining.append(value)
        return host
    monkeypatch.setattr(p.coordinator, 'host_factory', factory)
    active(p)
    assert remaining == [limit - before - 10, limit - before - 10]
    assert p.coordinator._goal_deadline - p.now[0] == limit - before - 10
    host = p.coordinator.host
    host.finish()
    p.now[0] += 20  # Ordinary active waiting still consumes time.
    p.coordinator.tick()
    assert p.root.call_tool('progression_status', {})['budget']['elapsed_seconds'] == before + 30
    assert checkpoint(p)['started_at'] == started


def test_active_restart_gap_and_clock_rollback_do_not_refund(progression):
    p = progression
    active(p)
    p.now[0] += 30
    p.coordinator.tick()
    before = checkpoint(p)
    assert before['budget']['elapsed_seconds'] == 30
    p.coordinator.host.close()
    p.coordinator.host = None
    p.now[0] += 20
    p.coordinator.tick()
    assert checkpoint(p)['budget']['elapsed_seconds'] == 50
    assert checkpoint(p)['rounds'] == before['rounds']
    assert not p.coordinator.host.prompts
    p.now[0] -= 10
    p.coordinator._event(dict(method='thread/tokenUsage/updated', params=dict(threadId='native-root',
        tokenUsage=dict(total=dict(inputTokens=1, cachedInputTokens=0, outputTokens=0)))))
    p.coordinator.tick()
    assert p.root.call_tool('progression_status', {})['budget']['elapsed_seconds'] == 50
    assert checkpoint(p)['budget']['elapsed_seconds'] == 50
