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
from tests.operations.test_progress_assist import configure, trigger, next_turn, notice, correction_state
from tests.operations.test_scientific_progress import active, finish, request


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
