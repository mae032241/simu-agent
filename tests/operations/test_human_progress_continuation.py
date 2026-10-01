"""Human management confirmation through HTTP, followed by actual MCP admission."""
import json
import re
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest

from scidiscovery.artifact_agent.approval_ui import ApprovalUI
from scidiscovery.artifact_agent.service.instance_management import issue_instance_management_capability
from scidiscovery.artifact_agent.service.progression_read import progression_read_view
from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService
from tests.operations.test_m6a_direct_instance_management import _request
from tests.operations.test_progression import progression, row, checkpoint
from tests.operations.test_progress_assist import configure, trigger, next_turn, notice, correction_state, finish_changed
from tests.operations.test_scientific_progress import active, finish, request, assess


@pytest.fixture
def paused(progression, monkeypatch):
    p = progression
    monkeypatch.setattr('scidiscovery.artifact_agent.service.scheduling_control.time', lambda: p.now[0])
    configure(p)
    root = active(p)
    trigger(p, root)
    next_turn(p)
    p.coordinator.host.finish()
    next_turn(p)
    p.coordinator.tick()  # confirmed terminal host release, no additional model turn
    assert row(p)['state'] == 'paused' and row(p)['host_json'] is None
    assert notice(p)['state'] == 'exhausted'
    return p


@pytest.fixture
def human_ui(paused):
    p = paused
    secret = b'h' * 32
    bindings = p.runtime.scheduler_bindings
    model = SimpleNamespace(artifacts=p.runtime.artifacts, progression_status=lambda instance, **kw: progression_read_view(
        bindings=bindings, runs=p.runtime.runs, artifacts=p.runtime.artifacts,
        operation_catalog=p.catalog, instance_id=instance, **kw))
    ui = ApprovalUI(p.runtime.approvals, bindings=bindings, instance_management_secret=secret, read_model=model)
    base = ui.start()
    capability = issue_instance_management_capability(session_key=p.user, secret=secret)
    path = '/sessions/' + p.user + '?' + urlencode(dict(capability=capability))
    status, _, raw = _request(base, 'GET', path)
    assert status == 200
    page = raw.decode()
    assert '人工接管并继续（保留预算）' in page and 'coverage_gap' in page
    binding = re.search(r"name='confirmation_binding' value='([^']+)'", page)
    assert binding
    form = dict(capability=capability, csrf=ui.session_id, command='human_continue',
        instance_id=p.instance, confirmation_binding=binding[1], confirm_human_continue='yes')
    try:
        yield SimpleNamespace(p=p, base=base, form=form, secret=secret, path=path)
    finally:
        ui.stop()


def submit(ui, **changes):
    return _request(ui.base, 'POST', '/instances/progression', form=dict(ui.form, **changes))[0]


def status(p):
    return p.root.call_tool('progression_status', {})


def save_checkpoint(p, **changes):
    cp = checkpoint(p)
    cp.update(changes)
    with p.runtime.scheduler_bindings._connect() as db:
        db.execute('UPDATE scheduler_progression SET checkpoint_json=? WHERE instance_id=?', (json.dumps(cp), p.instance))


def test_ui_confirmation_continues_same_goal_and_keeps_scientific_gap(human_ui):
    ui, p = human_ui, human_ui.p
    before, episode = checkpoint(p), correction_state(p)
    assert submit(ui) == 303
    view = status(p)
    assert view['human_continuation']['active'] and view['reason'] == 'human_continuation'
    assert view['human_continuation']['history'][0]['prior_reason'] == 'scientific_progress_persistent_gap'
    assert 'session_key' not in json.dumps(view['human_continuation'])
    assert correction_state(p) == episode
    for key in ('rounds', 'attempts', 'probes', 'started_at', 'admissions', 'budget'):
        assert checkpoint(p)[key] == before[key]
    finish(p, p.root, 'human-directed-task')
    assert len(checkpoint(p)['admissions']) == len(before['admissions']) + 1
    assert status(p)['progress_shadow']['assist']['reassessments'] == 1
    assert p.root.call_tool('run_status', dict(name='human-directed-task'))['state'] == 'completed'
    assert submit(ui) == 409  # stale confirmation is not a reusable authority
    page = _request(ui.base, 'GET', ui.path)[2].decode()
    assert '当前人工继续有效' in page and 'coverage_gap' in page
    reopened = SchedulerBindingService(p.runtime.scheduler_bindings.database_path)
    assert reopened.progression_status(instance_id=p.instance)['human_continuation'] == status(p)['human_continuation']


@pytest.mark.parametrize('pause_first', [False, True])
def test_ui_start_background_after_human_continuation_requires_pause(human_ui, pause_first):
    ui, p = human_ui, human_ui.p
    assert submit(ui) == 303
    episode, before = correction_state(p), checkpoint(p)
    common = {key: ui.form[key] for key in ('capability', 'csrf')}
    if pause_first:
        assert _request(ui.base, 'POST', '/instances/progression', form=dict(common, command='pause'))[0] == 303
    control_before = row(p)
    code = _request(ui.base, 'POST', '/instances/progression', form=dict(common,
        command='start', mode='background', objective_name='goal'))[0]
    if not pause_first:
        assert code == 409
        assert row(p) == control_before
        assert status(p)['human_continuation']['active']
        return
    assert code == 303
    assert row(p)['state'] == 'pending' and row(p)['mode'] == 'background'
    assert not status(p)['human_continuation']['active']
    assert correction_state(p) == episode
    for key in ('rounds', 'attempts', 'probes', 'started_at', 'admissions', 'budget', 'human_continuations'):
        assert checkpoint(p)[key] == before[key]
    next_turn(p)
    assert row(p)['state'] == 'paused' and row(p)['reason'] == 'scientific_progress_persistent_gap'
    assert notice(p)['state'] == 'exhausted' and notice(p)['reassessments'] == 1


@pytest.mark.parametrize('bad', ['csrf', 'capability', 'confirmation_binding', 'instance_id', 'confirm_human_continue'])
def test_bad_ui_confirmation_cannot_change_control(human_ui, bad):
    before = row(human_ui.p)
    assert submit(human_ui, **{bad: 'invalid'}) in {403, 409}
    assert row(human_ui.p) == before
    assert _request(human_ui.base, 'POST', '/instances/progression', form=human_ui.form,
        origin='https://untrusted.example')[0] == 403
    assert row(human_ui.p) == before


def test_other_session_capability_cannot_reuse_confirmation(human_ui):
    ui, p = human_ui, human_ui.p
    p.runtime.scheduler_bindings.bind_session(session_key='other', instance_id=p.instance)
    capability = issue_instance_management_capability(session_key='other', secret=ui.secret)
    assert submit(ui, capability=capability) == 409
    assert not status(p)['human_continuation']['active']


@pytest.mark.parametrize('command', ['takeover', 'start'])
def test_ordinary_mcp_cannot_grant_human_continuation_or_erase_frozen_policy(paused, command):
    p = paused
    frozen = row(p)['config_json']
    args = dict(command=command, mode='interactive')
    if command == 'start':
        args['objective_name'] = 'goal'
    with pytest.raises(Exception):
        p.root.call_tool('progression_command', dict(args, human_continue=True))
    with pytest.raises(Exception):
        p.root.call_tool('progression_command', dict(command='human_continue'))
    p.root.call_tool('progression_command', args)
    assert json.loads(row(p)['config_json']) == json.loads(frozen)
    with pytest.raises(Exception, match='scientific_progress_persistent_gap'):
        p.root.call_tool('operation_invoke', request('mcp-cannot-self-approve'))
    assert not status(p)['human_continuation']['active']
    assert notice(p)['reassessments'] == 1


@pytest.mark.parametrize('barrier', ['attempts', 'rounds', 'probes', 'elapsed', 'tokens', 'admission', 'native'])
def test_human_confirmation_and_admission_preserve_budget_and_unknown_barriers(human_ui, barrier):
    ui, p = human_ui, human_ui.p
    # Establish real consent, then prove subsequent admission still checks bounds.
    assert submit(ui) == 303
    limits = json.loads(row(p)['config_json'])['effective']['progression']
    if barrier in {'attempts', 'rounds', 'probes'}:
        save_checkpoint(p, **{barrier: limits['max_' + barrier]})
    elif barrier == 'elapsed':
        p.now[0] += limits['max_elapsed_seconds']
    elif barrier == 'tokens':
        from scidiscovery.platforms.codex_usage import observe_usage
        cost = observe_usage(dict(threadId='native-root', tokenUsage=dict(total=dict(
            inputTokens=limits['max_tokens'], cachedInputTokens=0, outputTokens=0))), role='root', owner=p.instance)
        save_checkpoint(p, usage_records={'native-root': cost})
    elif barrier == 'admission':
        save_checkpoint(p, admissions={**checkpoint(p)['admissions'], 'uncertain': dict(state='prepared')})
    else:
        save_checkpoint(p, phase='prepared', turn_id=None, fault_class='outcome_unknown')
    with pytest.raises(Exception, match='budget|submission'):
        p.root.call_tool('operation_invoke', request('barrier-cannot-be-overridden'))
    assert p.root.call_tool('run_status', dict(name='renamed-2'))['state'] == 'completed'
    p.root.call_tool('progression_command', dict(command='pause'))
    from scidiscovery.artifact_agent.service.scheduling_control import human_continuation_binding
    binding = human_continuation_binding(row(p), p.user)
    assert submit(ui, confirmation_binding=binding) == 409
    assert row(p)['state'] == 'paused'


def test_background_and_owner_changes_invalidate_consent_without_refunding(human_ui):
    ui, p = human_ui, human_ui.p
    original = notice(p)
    assert submit(ui) == 303
    before = checkpoint(p)
    p.runtime.scheduler_bindings.bind_session(session_key='other', instance_id=p.instance)
    other = p.root.__class__(p.facade('other'))
    other.call_tool('progression_command', dict(command='takeover'))
    assert not status(p)['human_continuation']['active']
    with pytest.raises(Exception, match='scientific_progress_persistent_gap'):
        other.call_tool('operation_invoke', request('new-owner-not-human-approved'))
    p.root.call_tool('progression_command', dict(command='takeover', mode='background'))
    next_turn(p)
    assert row(p)['state'] == 'paused'
    assert notice(p) == original
    assert checkpoint(p)['human_continuations'] == before['human_continuations']
    for key in ('rounds', 'attempts', 'started_at', 'admissions'):
        assert checkpoint(p)[key] == before[key]


def test_goal_revision_and_archive_keep_trace_without_inheriting_permission(human_ui):
    from tests.operations.synchronous_archive_fixture import SynchronousFixtureArchive
    from tests.operations.test_instance_archive import save_archive, restore_archive
    ui, p = human_ui, human_ui.p
    assert submit(ui) == 303
    p.root.call_tool('artifact_ingest_text', dict(name='revised-goal', text='A revised scientific goal.'))
    p.root.call_tool('progression_command', dict(command='pause'))
    p.root.call_tool('progression_command', dict(command='start', mode='interactive', objective_name='revised-goal'))
    assert not status(p)['human_continuation']['active']
    assert submit(ui) == 409
    p.root.call_tool('progression_command', dict(command='pause'))
    expected = status(p)['human_continuation']
    p.runtime.runs._synchronous_archive_fixture = True
    archive = SynchronousFixtureArchive(p.runtime)
    save_archive(archive, p.instance)
    assert archive.archived_model(p.instance).progression_status(p.instance)['human_continuation'] == expected
    restore_archive(archive, p.instance)
    restored = progression_read_view(bindings=p.runtime.scheduler_bindings, runs=p.runtime.runs,
        artifacts=p.runtime.artifacts, operation_catalog=p.catalog, instance_id=p.instance)
    assert restored['state'] == 'paused'
    assert restored['human_continuation'] == expected


def fresh_binding(ui):
    from scidiscovery.artifact_agent.service.scheduling_control import human_continuation_binding
    return human_continuation_binding(row(ui.p), ui.p.user)


def independent(ui, goal='goal', **changes):
    return submit(ui, command='independent_interactive', objective_name=goal,
        confirm_independent_interactive='yes', confirmation_binding=fresh_binding(ui), **changes)


@pytest.mark.parametrize('phase', ['no_causes', 'causes_without_episode', 'prepared',
    'submitted_unknown', 'delivered', 'awaiting_result', 'exhausted'])
def test_ui_safe_phase_confirmation_and_unknown_native_barrier(human_ui, phase):
    ui, p = human_ui, human_ui.p
    progress = correction_state(p)
    if phase in {'no_causes', 'causes_without_episode'}:
        progress['assist'] = []
        if phase == 'no_causes':
            progress['counts'] = {key: 0 for key in progress['counts']}
    else:
        progress['assist'][-1]['state'] = phase
        if phase in {'prepared', 'submitted_unknown'}:
            progress['assist'][-1].pop('delivered', None)
            progress['assist'][-1]['reassessments'] = 0
    with p.runtime.scheduler_bindings._connect() as db:
        db.execute('UPDATE scheduler_progress_shadow SET state_json=? WHERE instance_id=?',
            (json.dumps(progress), p.instance))
    before = row(p)
    code = submit(ui)
    if phase == 'submitted_unknown':
        assert code == 409 and row(p) == before
        assert independent(ui) == 409 and row(p) == before
        return
    assert code == 303
    finish(p, p.root, 'safe-human-work')
    assert correction_state(p)['assist'] == progress['assist']


@pytest.mark.parametrize('limit', ['tasks', 'tokens', 'elapsed', 'rounds'])
def test_explicit_independent_ui_scope_preserves_old_limits_and_instance_budget(human_ui, limit):
    from dataclasses import replace
    from scidiscovery.artifact_agent.service.executions import ExecutionService
    from tests.operations.test_execution_archive_budget import _policy_executions, _rows
    ui, p = human_ui, human_ui.p
    # A real instance execution ledger must survive the control-only scope change.
    bindings = p.runtime.scheduler_bindings
    executions = ExecutionService(artifacts=p.runtime.artifacts, approvals=p.runtime.approvals,
        database_path=bindings.database_path.with_name('executions.sqlite3'),
        exchange_root=bindings.database_path.parent / 'execution-exchange', service_actor=p.runtime.actor)
    p.runtime = replace(p.runtime, executions=executions)
    p.coordinator.runtime = p.runtime
    p.root.facade.executions = executions
    other = bindings.create_instance(name='execution-peer', title='peer', objective='peer')
    _policy_executions((p.runtime, None, p.instance, other.instance_id))
    execution_before = _rows(p.runtime.executions.database_path)
    p.root.call_tool('progression_command', dict(command='takeover'))
    p.root.call_tool('artifact_ingest_text', dict(name='new-goal', text='Explicit independent analysis.'))
    p.root.call_tool('progression_command', dict(command='pause'))
    limits = json.loads(row(p)['config_json'])['effective']['progression']
    if limit == 'tasks':
        config = json.loads(row(p)['config_json'])
        config['effective']['progression']['max_tasks'] = len(checkpoint(p)['admissions'])
        with bindings._connect() as db:
            db.execute('UPDATE scheduler_progression SET config_json=? WHERE instance_id=?', (json.dumps(config), p.instance))
    elif limit == 'tokens':
        from scidiscovery.platforms.codex_usage import observe_usage
        cost = observe_usage(dict(threadId='native-root', tokenUsage=dict(total=dict(
            inputTokens=limits['max_tokens'], cachedInputTokens=0, outputTokens=0))), role='root', owner=p.instance)
        save_checkpoint(p, usage_records={'native-root': cost})
    elif limit == 'elapsed':
        p.now[0] += limits['max_elapsed_seconds']
    else:
        save_checkpoint(p, rounds=limits['max_rounds'])
    before, config = checkpoint(p), row(p)['config_json']
    # Neither a new goal nor a fabricated argument grants the UI-only scope.
    with pytest.raises(Exception):
        p.root.call_tool('progression_command', dict(command='independent_interactive', objective_name='new-goal'))
    p.root.call_tool('progression_command', dict(command='start', objective_name='new-goal'))
    with pytest.raises(Exception, match='budget'):
        p.root.call_tool('operation_invoke', request('ordinary-mcp-cannot-reset'))
    assert not status(p)['interactive_session']['active']
    p.root.call_tool('progression_command', dict(command='pause'))
    assert independent(ui, 'new-goal') == 303
    finish(p, p.root, 'independent-task')
    current = checkpoint(p)
    assert current['admissions']['independent-task']['interactive_session_id']
    for key in ('rounds', 'attempts', 'probes', 'started_at', 'budget', 'usage_records'):
        assert current.get(key) == before.get(key)
    assert json.loads(row(p)['config_json']) == json.loads(config)
    assert _rows(p.runtime.executions.database_path) == execution_before
    view = status(p)
    assert view['interactive_session']['active'] and view['interactive_session']['tasks'] == 1
    assert 'session_key' not in json.dumps(view['interactive_session'])
    snapshot = row(p)
    status(p)
    _request(ui.base, 'GET', ui.path)
    assert row(p) == snapshot
    assert '独立人工工作作用域' in _request(ui.base, 'GET', ui.path)[2].decode()
    p.root.call_tool('progression_command', dict(command='pause'))
    p.root.call_tool('progression_command', dict(command='resume'))
    assert not status(p)['interactive_session']['active']


@pytest.mark.parametrize('new_evidence', [False, True])
def test_human_result_gets_one_budgeted_background_consumption_turn(human_ui, new_evidence):
    ui, p = human_ui, human_ui.p
    assert submit(ui) == 303
    old = notice(p)
    (finish_changed if new_evidence else finish)(p, p.root, 'human-result')
    assess(p.root, 'human-result', outcome='advance' if new_evidence else 'unknown')
    before = checkpoint(p)
    p.root.call_tool('progression_command', dict(command='pause'))
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='goal'))
    next_turn(p)
    assert row(p)['state'] == 'active'
    assert checkpoint(p)['rounds'] == before['rounds'] + 1
    assert notice(p)['id'] == old['id'] and notice(p)['reassessments'] == old['reassessments']
    assert checkpoint(p)['human_handoff']['state'] == 'delivered'
    root = p.root.__class__(p.facade(p.coordinator.host.scheduler_session))
    with pytest.raises(Exception, match='handoff_consumption_only'):
        root.call_tool('operation_invoke', request('no-extra-task-during-handoff'))
    p.coordinator.host.finish()
    next_turn(p)
    assert checkpoint(p)['human_handoff']['state'] == 'completed'
    assert notice(p)['state'] == ('resolved' if new_evidence else 'exhausted')
    assert row(p)['state'] == ('active' if new_evidence else 'paused')
    assert notice(p)['reassessments'] == old['reassessments']


def test_human_handoff_cannot_expand_native_round_budget(human_ui):
    ui, p = human_ui, human_ui.p
    assert submit(ui) == 303
    finish_changed(p, p.root, 'unconsumed-result')
    assess(p.root, 'unconsumed-result')
    frozen = notice(p)
    limits = json.loads(row(p)['config_json'])['effective']['progression']
    save_checkpoint(p, rounds=limits['max_rounds'])
    p.root.call_tool('progression_command', dict(command='pause'))
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='goal'))
    next_turn(p)
    assert row(p)['reason'] == 'budget_exhausted'
    assert checkpoint(p)['rounds'] == limits['max_rounds']
    assert checkpoint(p)['human_handoff']['state'] == 'prepared'
    assert not p.coordinator.host.prompts
    assert notice(p) == frozen


def test_interactive_pending_admission_has_a_reachable_ui_exit(human_ui):
    ui, p = human_ui, human_ui.p
    progress = correction_state(p)
    progress['assist'] = []  # The existing consumed causes precede any native brief.
    with p.runtime.scheduler_bindings._connect() as db:
        db.execute('UPDATE scheduler_progress_shadow SET state_json=? WHERE instance_id=?',
            (json.dumps(progress), p.instance))
    p.root.call_tool('progression_command', dict(command='takeover'))
    with pytest.raises(Exception, match='management UI'):
        p.root.call_tool('operation_invoke', request('prepared-needs-human-confirmation'))
    assert notice(p)['state'] == 'prepared'
    p.root.call_tool('progression_command', dict(command='pause'))
    assert submit(ui, confirmation_binding=fresh_binding(ui)) == 303
    finish(p, p.root, 'confirmed-human-task')
    assert notice(p)['state'] == 'prepared' and notice(p)['reassessments'] == 0


@pytest.mark.parametrize('bad', ['csrf', 'capability', 'instance_id', 'confirmation_binding', 'confirm_independent_interactive'])
def test_independent_scope_uses_full_ui_authorization(human_ui, bad):
    ui, p = human_ui, human_ui.p
    before = row(p)
    args = dict(command='independent_interactive', objective_name='goal', confirm_independent_interactive='yes')
    args[bad] = 'invalid'
    assert submit(ui, **args) in {403, 409}
    assert row(p) == before
    assert _request(ui.base, 'POST', '/instances/progression', form=dict(ui.form, **args),
        origin='https://untrusted.example')[0] == 403


def test_independent_scope_survives_archive_without_reactivating(human_ui):
    from tests.operations.synchronous_archive_fixture import SynchronousFixtureArchive
    from tests.operations.test_instance_archive import save_archive, restore_archive
    ui, p = human_ui, human_ui.p
    assert independent(ui) == 303
    finish(p, p.root, 'independent-archived-task')
    p.root.call_tool('progression_command', dict(command='pause'))
    expected = status(p)['interactive_session']
    p.runtime.runs._synchronous_archive_fixture = True
    archive = SynchronousFixtureArchive(p.runtime)
    save_archive(archive, p.instance)
    assert archive.archived_model(p.instance).progression_status(p.instance)['interactive_session'] == expected
    restore_archive(archive, p.instance)
    restored = progression_read_view(bindings=p.runtime.scheduler_bindings, runs=p.runtime.runs,
        artifacts=p.runtime.artifacts, operation_catalog=p.catalog, instance_id=p.instance)
    assert restored['interactive_session'] == expected
    assert row(p)['state'] == 'paused'


def test_independent_result_after_full_background_allowance_remains_observable(human_ui):
    ui, p = human_ui, human_ui.p
    assert submit(ui) == 303
    limit = json.loads(row(p)['config_json'])['effective']['progression']['max_tasks']
    for index in range(len(checkpoint(p)['admissions']), limit):
        finish(p, p.root, f'old-allowance-{index}')
    p.root.call_tool('progression_command', dict(command='pause'))
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='goal'))
    next_turn(p)
    p.coordinator.host.finish()
    next_turn(p)
    p.coordinator.tick()
    assert status(p)['progress_shadow']['counts']['consumed'] == limit
    assert independent(ui) == 303
    finish_changed(p, p.root, 'independent-new-evidence')
    assess(p.root, 'independent-new-evidence')
    p.root.call_tool('progression_command', dict(command='pause'))
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='goal'))
    next_turn(p)
    assert checkpoint(p)['budget']['tasks'] == limit
    p.coordinator.host.finish()
    next_turn(p)
    assert notice(p)['state'] == 'resolved'
    assert status(p)['progress_shadow']['counts']['consumed'] == limit + 1


def test_native_usage_reused_across_scopes_keeps_each_observed_delta(progression, monkeypatch):
    p = progression
    active(p)
    identity = dict(role='worker')
    monkeypatch.setattr(p.coordinator, '_identities', lambda: {'shared-worker': identity})
    def usage(tokens):
        p.coordinator._event(dict(method='thread/tokenUsage/updated', params=dict(threadId='shared-worker',
            tokenUsage=dict(total=dict(inputTokens=tokens, cachedInputTokens=0, outputTokens=0)))))
    usage(10)
    identity['interactive_session_id'] = 'explicit-human-scope'
    usage(15)
    assert checkpoint(p)['usage_records']['shared-worker']['counted_tokens']['input_tokens'] == 10
    identity.pop('interactive_session_id')
    usage(19)
    assert checkpoint(p)['usage_records']['shared-worker']['counted_tokens']['input_tokens'] == 14
    assert checkpoint(p)['interactive_usage_records']['shared-worker']['counted_tokens']['input_tokens'] == 5
    assert checkpoint(p)['usage_records']['shared-worker']['has_gaps']


@pytest.mark.parametrize('mode', ['shadow', 'off'])
def test_ordinary_shadow_and_off_interactive_behavior_does_not_gain_assist_budget_gate(paused, mode):
    p = paused
    config = json.loads(row(p)['config_json'])
    config['effective']['progression'].update(progress_mode=mode, max_tasks=len(checkpoint(p)['admissions']))
    with p.runtime.scheduler_bindings._connect() as db:
        db.execute('UPDATE scheduler_progression SET config_json=? WHERE instance_id=?', (json.dumps(config), p.instance))
    p.root.call_tool('progression_command', dict(command='takeover'))
    finish(p, p.root, 'ordinary-interactive')
    assert 'ordinary-interactive' not in checkpoint(p)['admissions']
    assert not status(p)['interactive_session']['active']


def test_independent_human_evidence_can_resolve_a_never_submitted_candidate(human_ui):
    ui, p = human_ui, human_ui.p
    progress = correction_state(p)
    episode = progress['assist'][-1]
    episode.update(state='prepared', reassessments=0)
    episode.pop('delivered')
    with p.runtime.scheduler_bindings._connect() as db:
        db.execute('UPDATE scheduler_progress_shadow SET state_json=? WHERE instance_id=?',
            (json.dumps(progress), p.instance))
    assert independent(ui) == 303
    finish_changed(p, p.root, 'independent-prepared-result')
    assess(p.root, 'independent-prepared-result')
    p.root.call_tool('progression_command', dict(command='pause'))
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='goal'))
    next_turn(p)
    assert notice(p)['state'] == 'prepared' and notice(p)['reassessments'] == 0
    p.coordinator.host.finish()
    next_turn(p)
    assert notice(p)['state'] == 'resolved' and notice(p)['reassessments'] == 0


@pytest.mark.parametrize('next_work', ['ordinary', 'requested_review'])
def test_resolved_handoff_uses_background_scope_at_real_preflight_and_creation(human_ui, next_work):
    from tests.operations.test_local_worker_contracts import _worker, _write_result
    from tests.operations.worker_fixtures import attached_worker
    ui, p = human_ui, human_ui.p
    assert independent(ui) == 303
    manual_count = 5 if next_work == 'ordinary' else 4
    for index in range(manual_count):
        name = f'manual-scope-{index}'
        if next_work == 'requested_review' and index < 2:
            p.root.call_tool('operation_invoke', request(name))
            author = attached_worker(p.runtime, p.root, name)
            author.call_tool('worker_open_assignment', {})
            _write_result(author)
            author.call_tool('worker_submit_result', {})
        else:
            (finish_changed if index == manual_count-1 else finish)(p, p.root, name)
    assess(p.root, name)
    p.root.call_tool('progression_command', dict(command='pause'))
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='goal'))
    next_turn(p)
    p.coordinator.host.finish()
    next_turn(p)
    assert notice(p)['state'] == 'resolved'
    root = p.root.__class__(p.facade(p.coordinator.host.scheduler_session))
    if next_work == 'ordinary':
        # The raw history already contains eight tasks, but only three belong to
        # the background session. Exercise both public and transactional checks.
        assert len(checkpoint(p)['admissions']) == 8
        before = row(p)
        assert root.call_tool('operation_preflight', request('after-handoff'))['admissible']
        assert row(p) == before
        finish(p, root, 'after-handoff')
        for index in range(4, 8):
            finish(p, root, f'background-budget-{index}')
        denied = root.call_tool('operation_preflight', request('real-background-budget-exhausted'))
        assert not denied['admissible'] and denied['reason_code'] == 'background_task_budget_exhausted'
        with pytest.raises(Exception, match='background_task_budget_exhausted'):
            root.call_tool('operation_invoke', request('real-background-budget-exhausted'))
        return
    root.call_tool('operation_invoke', request('waiting-owner'))
    owner = _worker(p.catalog, p.runtime)
    owner.call_tool('worker_open_assignment', {})
    bindings = p.runtime.scheduler_bindings
    owner_id = bindings.resolve(instance=p.instance, namespace='run', name='waiting-owner')
    subject = p.runtime.artifacts.get_by_id(bindings.resolve(instance=p.instance,
        namespace='artifact', name='manual-scope-0.output'))
    review = dict(name='owner-exact-review', operation_id='science.object.review.v1',
        inputs=[dict(port='subject', artifact_names=['manual-scope-0.output'])],
        instruction='Review the exact subject requested by the waiting owner.')
    p.runtime.runs.request_implementation_review(owner_id, subject.ref, review)
    assert len(checkpoint(p)['admissions']) == 8  # Four background, four manual.
    wrong = dict(review, name='wrong-review', inputs=[dict(port='subject', artifact_names=['manual-scope-1.output'])])
    denied = root.call_tool('operation_preflight', wrong)
    assert not denied['admissible'] and denied['reason_code'] == 'background_task_busy'
    before = row(p)
    assert root.call_tool('operation_preflight', review)['admissible']
    assert row(p) == before
    assert root.call_tool('operation_invoke', review)['result']['state'] == 'queued'
    reviewer = attached_worker(p.runtime, root, review['name'])
    reviewer.call_tool('worker_open_assignment', {})
    wait = p.runtime.runs.review_wait(owner_id)
    assert wait['state'] == 'running'
    assert wait['reviewer_run_id'] == bindings.resolve(instance=p.instance, namespace='run', name=review['name'])
