"""Durable pull notices and shared UI projections without models or solvers."""
import json
import sqlite3
from copy import copy
from dataclasses import replace
from urllib.parse import parse_qs, urlparse

import pytest

from scidiscovery.artifact_agent.approval_ui.read_model import InstanceReadModel
from scidiscovery.artifact_agent.approval_ui.workbench_render import render_workbench
from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService
from tests.operations.test_progression import progression, row, checkpoint
from tests.operations.test_local_worker_contracts import _invoke, _worker, _write_result
from tests.operations.test_instance_workbench_render import _overview
from tests.operations.test_instance_browser_http import _request
from tests.operations.test_m6a_direct_instance_management import _root, _setup


def _bounded_context(p, context_bytes=10000):
    from blind_csv_plugin.plugin import PLUGIN
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
    from scidiscovery.operations.catalog import compile_catalog
    author = PLUGIN.operations[0].model_copy(update=dict(decision_fields=('interpretation', 'limitations')))
    plugin = PLUGIN.model_copy(update=dict(operations=(author, *PLUGIN.operations[1:])))
    p.catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, plugin))
    p.runtime.runs.operation_catalog = p.catalog
    p.root.facade._operation_catalog = p.catalog
    p.root.call_tool('progression_command', dict(command='pause'))
    bindings = p.runtime.scheduler_bindings
    settings = bindings.global_settings
    bindings.global_settings = settings.model_copy(update=dict(progression=settings.progression.model_copy(
        update=dict(context_bytes=context_bytes))))
    from tests.operations.research_loop_fixtures import authorize_loop
    authorize_loop(p.runtime, p.instance, p.user, 'goal')
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='goal'))


def _sealed_result(p, root, name, *, interpretation_chars=0, capacity_handoff=True):
    _invoke(root, name)
    worker = _worker(p.catalog, p.runtime)
    worker.call_tool('worker_open_assignment', {})
    _write_result(worker)
    if interpretation_chars:
        path = worker._workspace.output_directory / 'result.json'
        result = json.loads(path.read_text())
        result['payload']['interpretation'] = '界' * interpretation_chars
        # Compact defaults no longer copy a long raw interpretation. Exercise
        # actual brief capacity with complete, valid sealed handoff statements.
        if capacity_handoff:
            result['handoff']['summary'] = '界' * 1000
            entries = 4 if interpretation_chars >= 4000 else 1
            result['handoff']['assumptions'] = ['A' * 1024] * entries
            if interpretation_chars >= 4000:
                result['handoff']['missing_inputs'] = ['M' * 1024] * entries
                result['handoff']['next_actions'] = ['N' * 1024] * entries
        path.write_text(json.dumps(result, ensure_ascii=False))
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'


def _next_poll(p):
    p.now[0] += 6
    p.coordinator.tick()


def _progress_native_host(p):
    from tests.operations.test_progression import Host
    def factory(saved,event):
        host=Host(saved,event)
        host.native_connection_id='progress-context-connection'
        return host
    p.coordinator.host_factory=factory


def test_progress_explanation_reuse_keeps_dynamic_status_and_usage_identity(progression):
    p=progression
    _progress_native_host(p)
    p.coordinator.tick()
    host=p.coordinator.host
    first=json.loads(host.prompts[-1].split('\n')[-1])['progress_shadow']
    assert isinstance(first['limitations'],list)
    fingerprint=checkpoint(p)['usage_records'][host.identity.thread_id]['progress_explanation_fingerprint']
    host.event(dict(method='thread/tokenUsage/updated',params=dict(threadId=host.identity.thread_id,
        tokenUsage=dict(total=dict(inputTokens=100,cachedInputTokens=50,outputTokens=20)))))
    assert checkpoint(p)['usage_records'][host.identity.thread_id]['progress_explanation_fingerprint']==fingerprint
    p.root.call_tool('progression_message',dict(name='progress-direction',text='Retain the exact scientific limits.'))
    host.finish();_next_poll(p)
    brief=json.loads(host.prompts[-1].split('\n')[-1])
    shadow=brief['progress_shadow']
    assert 'limitations' not in shadow
    guide=shadow['limitations_reused']['read']
    # Exercise the advertised parameters through the actual strict Root entry.
    arguments=guide.get('arguments',{k:v for k,v in guide.items() if k!='tool'})
    public=p.root.call_tool(guide['tool'],arguments)['progress_shadow']
    assert guide==dict(tool='progression_status',arguments={})
    assert public['limitations']==first['limitations']
    assert {k:v for k,v in shadow.items() if k!='limitations_reused'}=={k:v for k,v in public.items() if k!='limitations'}
    record=checkpoint(p)['usage_records'][host.identity.thread_id]
    assert record['progress_explanation_fingerprint']==fingerprint
    assert record['high_water']['input_tokens']==100 and record['native_turn']['turn_id']==host.turn_id
    complete_budget=checkpoint(p)['budget']
    assert {k:v for k,v in brief['budget'].items() if k not in {'limits','limits_omitted'}} == {
        k:v for k,v in complete_budget.items() if k!='limits'}
    limits_read=brief['budget']['limits_omitted']['read']
    expanded=p.root.call_tool(limits_read['tool'],limits_read['arguments'])
    assert expanded['budget']['limits']==complete_budget['limits']
    assert all(complete_budget['limits'][key]==value for key,value in brief['budget']['limits'].items())


@pytest.mark.parametrize('change',['context','thread','configuration','explanation'])
def test_progress_explanation_restores_full_at_changed_context(progression,monkeypatch,change):
    from scidiscovery.artifact_agent.service import scientific_progress
    p=progression
    _progress_native_host(p);p.coordinator.tick()
    saved=row(p);cp=json.loads(saved['checkpoint_json']);host=json.loads(saved['host_json'])
    if change=='context':
        cp['usage_records'][host['thread_id']]['context_delivered']=False
        saved['checkpoint_json']=json.dumps(cp)
    elif change=='thread':
        saved['host_json']=json.dumps(dict(host,thread_id='fresh-root'))
    elif change=='configuration':
        config=json.loads(saved['config_json']);config['effective']['progression']['poll_seconds']+=1
        saved['config_json']=json.dumps(config)
    else:
        original=scientific_progress.shadow_projection
        monkeypatch.setattr(scientific_progress,'shadow_projection',lambda **kw:
            dict(original(**kw),limitations=['Changed fixed explanation.']))
    snapshot=dict(goal=saved['objective_ref_json'],runs=[],approvals=[])
    brief=json.loads(p.coordinator._brief(saved,snapshot,45000).split('\n')[-1])
    assert isinstance(brief['progress_shadow']['limitations'],list)
    assert 'limitations_reused' not in brief['progress_shadow']


@pytest.mark.parametrize('boundary',['context_limit','unknown_reply'])
def test_unconfirmed_progress_explanation_never_establishes_seen_evidence(progression,monkeypatch,boundary):
    from scidiscovery.artifact_agent.service import scientific_progress
    p=progression
    _progress_native_host(p)
    if boundary=='context_limit':
        original=scientific_progress.shadow_projection
        monkeypatch.setattr(scientific_progress,'shadow_projection',lambda **kw:
            dict(original(**kw),limitations=['Fixed explanation '+('界'*30000)]))
        p.coordinator.tick()
        assert json.loads(p.coordinator.host.prompts[-1].split('\n')[-1])['progress_shadow']['brief_omitted']
    else:
        factory=p.coordinator.host_factory
        def unknown(saved,event):
            host=factory(saved,event);start=host.start_turn
            def submit(prompt):
                start(prompt)  # accepted started notification precedes the unknown reply.
                raise sqlite3.OperationalError('uncertain progress submission')
            host.start_turn=submit
            return host
        p.coordinator.host_factory=unknown
        with pytest.raises(sqlite3.OperationalError,match='uncertain progress submission'):p.coordinator.tick()
    assert not checkpoint(p)['usage_records']['native-root'].get('progress_explanation_fingerprint')
    saved=row(p);snapshot=dict(goal=saved['objective_ref_json'],runs=[],approvals=[])
    restored=json.loads(p.coordinator._brief(saved,snapshot,200000).split('\n')[-1])
    assert isinstance(restored['progress_shadow']['limitations'],list)


def test_progress_confirmation_fingerprints_sent_explanation_not_later_projection(progression,monkeypatch):
    from scidiscovery.artifact_agent.service import scientific_progress
    from scidiscovery.artifact_agent.service.progression import _progress_explanation_fingerprint
    p=progression
    changed=[False];original=scientific_progress.shadow_projection
    monkeypatch.setattr(scientific_progress,'shadow_projection',lambda **kw:
        dict(original(**kw),limitations=['New fixed explanation.']) if changed[0] else original(**kw))
    _progress_native_host(p);factory=p.coordinator.host_factory
    def after_send(saved,event):
        host=factory(saved,event);start=host.start_turn
        def submit(prompt):
            turn=start(prompt);changed[0]=True
            return turn
        host.start_turn=submit
        return host
    p.coordinator.host_factory=after_send;p.coordinator.tick()
    saved=row(p);sent=json.loads(p.coordinator.host.prompts[-1].split('\n')[-1])['progress_shadow']
    assert checkpoint(p)['usage_records']['native-root']['progress_explanation_fingerprint']==_progress_explanation_fingerprint(saved,sent)
    snapshot=dict(goal=saved['objective_ref_json'],runs=[],approvals=[])
    assert json.loads(p.coordinator._brief(saved,snapshot,45000).split('\n')[-1])['progress_shadow']['limitations']==['New fixed explanation.']


def _select_objective(p, original):
    p.root.call_tool('progression_command', dict(command='pause'))
    p.root.call_tool('progression_message', dict(name='exact.goal', text=original))
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='exact.goal'))


def test_root_developer_and_delivered_continuations_share_scientific_task_boundary(progression,tmp_path):
    import tomllib
    from scidiscovery.platforms.codex import _root_instruction_config
    from scidiscovery.platforms.scheduler_prompt import load_scheduler_prompt
    p=progression
    p.coordinator.tick();host=p.coordinator.host
    p.root.call_tool('progression_message',dict(name='local-question',text='Retain the assigned question and authorization.'))
    host.finish();_next_poll(p)
    assert len(host.prompts)==2
    for prompt in host.prompts:
        assert 'seal and analyze before another test' not in prompt
        assert 'Do not hide multiple research decisions inside one experiment' not in prompt
        assert 'Root scheduler instructions' in prompt
        assert 'When budget.new_task_allowed is false' in prompt
        assert 'User text does not authorize an approval or execution exception' in prompt
    guide=tmp_path/'guides'
    generated=tomllib.loads(_root_instruction_config('',guide))['developer_instructions']
    assert generated==load_scheduler_prompt().replace('{{SCHEDULER_GUIDE_ROOT}}',str(guide))
    assert 'Related trials and bounded correction belong to their Worker' in generated
    assert 'H/W/A experiment contracts' in generated
    assert 'remaining time, token, execution and retry' in generated
    assert 'Root must not invent hypotheses' in generated
    assert generated not in host.prompts[-1]  # The full developer rule is not recopied every turn.


def test_same_thread_objective_is_delivered_once_and_remains_readable(progression):
    p = progression
    original = '比较精确数据，保留负结果与原始限制。' * 100
    _select_objective(p, original)
    p.coordinator.tick()
    host = p.coordinator.host
    first = json.loads(host.prompts[0].split('\n')[-1])['objective']
    assert first['original'] == original
    assert checkpoint(p)['usage_records'][host.identity.thread_id]['context_delivered']
    for index in range(3):
        p.root.call_tool('progression_message', dict(name=f'direction-{index}', text=f'Consider exact condition {index}.'))
        host.finish()
        _next_poll(p)
        brief = json.loads(host.prompts[-1].split('\n')[-1])
        goal = brief['objective']
        assert goal['status'] == 'unchanged' and 'original' not in goal
        assert (goal['name'], goal['kind'], goal['schema']) == ('exact.goal', first['kind'], first['schema'])
        assert brief['user_messages'] == [dict(name=f'direction-{index}', original=f'Consider exact condition {index}.')]
        assert len(host.prompts[-1].encode()) < len(host.prompts[0].encode()) - len(original.encode()) // 2
    fresh = p.root.__class__(p.facade(host.scheduler_session))
    assert fresh.call_tool(goal['read'], dict(name=goal['name'], view=goal['view']))['text'] == original
    assert 'Prior delivery does not prove retained context' in goal['guidance']


@pytest.mark.parametrize('missing', ['delivery', 'thread', 'snapshot', 'malformed_snapshot'])
def test_objective_restore_uses_full_original_when_delivery_context_is_missing(progression, missing):
    p = progression
    p.coordinator.tick()
    saved = row(p)
    cp = json.loads(saved['checkpoint_json'])
    host = json.loads(saved['host_json'])
    if missing == 'delivery':
        cp['usage_records'][host['thread_id']].pop('context_delivered')
    elif missing == 'thread':
        saved['host_json'] = json.dumps(dict(host, thread_id='new-root-thread'))
    elif missing == 'snapshot':
        cp.pop('notified_snapshot')
    else:
        cp['notified_snapshot'] = []
    saved['checkpoint_json'] = json.dumps(cp)
    snapshot = dict(goal=saved['objective_ref_json'], runs=[], approvals=[])
    restored = json.loads(p.coordinator._brief(saved, snapshot, 12000).split('\n')[-1])['objective']
    assert restored['status'] == 'available'
    assert restored['original'] == 'Compare exact data and retain limitations.'


def test_oversized_chinese_objective_keeps_exact_paged_entrance(progression):
    p = progression
    _bounded_context(p, context_bytes=12000)
    original = '保留中文原题的全部限制与完成条件。' * 800
    _select_objective(p, original)
    p.coordinator.tick()
    host = p.coordinator.host
    goal = json.loads(host.prompts[-1].split('\n')[-1])['objective']
    assert goal['status'] == 'omitted' and 'original' not in goal
    assert len(host.prompts[-1].encode()) <= 12000
    fresh = p.root.__class__(p.facade(host.scheduler_session))
    parts, cursor = [], None
    while True:
        page = fresh.call_tool(goal['read'], dict(name=goal['name'], view=goal['view'], content_cursor=cursor))
        parts.append(page['text'])
        cursor = page['next_cursor']
        if cursor is None:
            break
    assert len(parts) > 1 and ''.join(parts) == original
    p.root.call_tool('progression_message', dict(name='after-omission', text='Keep this new condition.'))
    host.finish()
    _next_poll(p)
    continued = json.loads(host.prompts[-1].split('\n')[-1])['objective']
    assert continued['status'] == 'unchanged'
    assert (continued['name'], continued['read'], continued['view'], continued['continuation']) == (
        goal['name'], goal['read'], goal['view'], goal['continuation'])
    assert len(host.prompts[-1].encode()) <= 12000


@pytest.mark.parametrize('late_start', [False, True])
def test_unknown_initial_start_does_not_mark_objective_delivered(progression, late_start):
    from tests.operations.test_progression import Host
    p = progression
    submissions = []
    def factory(saved, event):
        host = Host(saved, event)
        def unknown(prompt):
            submissions.append(prompt)
            if late_start:
                host.event(dict(method='turn/started', params=dict(threadId=host.identity.thread_id,
                    turn=dict(id='uncertain-turn'))))
            raise sqlite3.OperationalError('uncertain initial submission')
        host.start_turn = unknown
        return host
    p.coordinator.host_factory = factory
    with pytest.raises(sqlite3.OperationalError, match='uncertain initial submission'):
        p.coordinator.tick()
    cp = checkpoint(p)
    assert cp['fault_class'] == 'outcome_unknown'
    assert not cp['usage_records']['native-root'].get('context_delivered')
    assert not cp.get('notified_snapshot')
    assert json.loads(submissions[0].split('\n')[-1])['objective']['original'] == 'Compare exact data and retain limitations.'
    for _ in range(3):
        _next_poll(p)
    assert len(submissions) == 1


def test_same_oversized_result_notifies_once_without_consumption(progression):
    p = progression
    _bounded_context(p)
    p.coordinator.tick()
    host = p.coordinator.host
    root = p.root.__class__(p.facade(host.scheduler_session))
    _sealed_result(p, root, 'oversized', interpretation_chars=4000)
    host.finish()
    _next_poll(p)
    assert len(host.prompts) == 2
    brief = json.loads(host.prompts[-1].split('\n')[-1])
    assert not brief['changes'] and brief['result_omissions'] == 1
    assert brief['omissions'][0] == dict(name='oversized', state='completed', read='run_status', intent='decision')
    assert not checkpoint(p)['decision_snapshot']['runs']
    projection = root.call_tool('run_status', dict(name='oversized', intent='decision'))
    host.event(dict(method='item/completed', params=dict(threadId=host.identity.thread_id, turnId=host.turn_id,
        item=dict(type='mcpToolCall', server='scidiscovery', tool='scid_call', status='completed',
            arguments=dict(name='run_status', arguments=dict(name='oversized')),
            result=dict(content=[dict(type='text', text=json.dumps(projection))])))))
    assert checkpoint(p)['terminal_delivery_coverage'] == 'structured_tool_result_unavailable'
    host.finish()
    for _ in range(3):
        _next_poll(p)
        if host.completion is None:
            host.finish()
    assert len(host.prompts) == 2
    assert not checkpoint(p)['processed_snapshot']['runs']
    status = root.call_tool('progression_status', {})
    assert status['progress_shadow']['counts']['consumed'] == 0
    assert root.call_tool('run_list', dict(view='summary', limit=8))['runs'][0]['name'] == 'oversized'
    from scidiscovery.artifact_agent.interfaces.mcp_root import RootToolError
    with pytest.raises(RootToolError):
        root.call_tool('run_status', dict(name='oversized', intent='full'))
    assert root.facade.run_status(name='oversized', intent='full')['state'] == 'completed'


def test_compact_delivery_records_omitted_science_without_claiming_original_read(progression):
    p=progression
    _bounded_context(p)
    p.coordinator.tick()
    host=p.coordinator.host
    root=p.root.__class__(p.facade(host.scheduler_session))
    _sealed_result(p, root, 'compact', interpretation_chars=4000, capacity_handoff=False)
    host.finish()
    _next_poll(p)
    brief=json.loads(host.prompts[-1].split('\n')[-1])
    assert [item['name'] for item in brief['changes']]==['compact']
    change=brief['changes'][0]
    assert change['output_delivery']=='compact'
    assert next(item for item in change['selected_output']['items'] if item['pointer']=='/interpretation')['status']=='omitted'
    host.finish()
    _next_poll(p)
    assert root.call_tool('progression_status', {})['progress_shadow']['counts']['consumed']==1
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    deliveries=p.runtime.scheduler_bindings.terminal_deliveries(instance_id=p.instance,
        objective_ref=ArtifactRef.model_validate_json(row(p)['objective_ref_json']), after=0, limit=8)
    coverage=json.loads(deliveries[0]['delivery_json'])
    assert coverage['coverage']=='compact' and coverage['original_read']=='not_confirmed'
    assert next(item for item in coverage['fields'] if item['pointer']=='/interpretation')['status']=='omitted'
    assert root.facade.run_status(name='compact',intent='full')['sealed_output']['payload']['interpretation']=='界'*4000
    for _ in range(3):
        _next_poll(p)
    assert len(host.prompts)==2


def test_new_result_and_user_message_wake_with_old_omission_retained(progression):
    p = progression
    _bounded_context(p)
    p.coordinator.tick()
    host = p.coordinator.host
    root = p.root.__class__(p.facade(host.scheduler_session))
    _sealed_result(p, root, 'oversized', interpretation_chars=4000)
    host.finish()
    _next_poll(p)
    host.finish()
    _next_poll(p)
    assert len(host.prompts) == 2
    _sealed_result(p, root, 'new-result')
    _next_poll(p)
    assert len(host.prompts) == 3
    brief = json.loads(host.prompts[-1].split('\n')[-1])
    assert [entry['name'] for entry in brief['changes']] == ['new-result']
    assert brief['result_omissions'] == 1
    host.finish()
    _next_poll(p)
    assert {entry['name'] for entry in checkpoint(p)['processed_snapshot']['runs']} == {'new-result'}
    p.root.call_tool('progression_message', dict(name='read-direction', text='Read the exact omitted interpretation.'))
    _next_poll(p)
    assert len(host.prompts) == 4
    brief = json.loads(host.prompts[-1].split('\n')[-1])
    assert brief['result_omissions'] == 1 and brief['user_messages'][0]['name'] == 'read-direction'
    assert root.call_tool('progression_status', {})['progress_shadow']['counts']['consumed'] == 1


def test_notified_cohort_continues_delivering_actual_batches(progression):
    p = progression
    _bounded_context(p, context_bytes=16000)
    p.coordinator.tick()
    host = p.coordinator.host
    root = p.root.__class__(p.facade(host.scheduler_session))
    names = {f'batch-{index}' for index in range(3)}
    for name in sorted(names):
        _sealed_result(p, root, name, interpretation_chars=2000)
    host.finish()
    _next_poll(p)
    first = json.loads(host.prompts[-1].split('\n')[-1])
    seen = {entry['name'] for entry in first['changes']}
    assert seen and seen < names and first['result_omissions'] == len(names - seen)
    assert {entry['name'] for entry in checkpoint(p)['notified_snapshot']['runs']} == names
    batches = 1
    while seen != names:
        assert batches < 4
        host.finish()
        _next_poll(p)
        batch = json.loads(host.prompts[-1].split('\n')[-1])
        shown = {entry['name'] for entry in batch['changes']}
        assert shown and not seen & shown
        seen |= shown
        batches += 1
    host.finish()
    _next_poll(p)
    assert {entry['name'] for entry in checkpoint(p)['processed_snapshot']['runs']} == names
    assert root.call_tool('progression_status', {})['progress_shadow']['counts']['consumed'] == 3
    assert len(host.prompts) == batches + 1


def test_notification_position_survives_new_coordinator_and_store(progression):
    from scidiscovery.artifact_agent.service.progression import ProgressionCoordinator
    from tests.operations.test_progression import Host
    p = progression
    _bounded_context(p)
    p.coordinator.tick()
    host = p.coordinator.host
    root = p.root.__class__(p.facade(host.scheduler_session))
    _sealed_result(p, root, 'oversized', interpretation_chars=4000)
    host.finish()
    _next_poll(p)
    host.finish()
    _next_poll(p)
    before = checkpoint(p)
    p.coordinator.close()
    reopened = SchedulerBindingService(p.runtime.scheduler_bindings.database_path,
        global_settings=p.runtime.scheduler_bindings.global_settings)
    p.runtime = replace(p.runtime, scheduler_bindings=reopened)
    p.root.facade.bindings = reopened
    p.coordinator = ProgressionCoordinator(runtime=p.runtime, host_factory=Host,
        facade_factory=p.facade, clock=lambda: p.now[0])
    for _ in range(3):
        _next_poll(p)
    assert not p.coordinator.host.prompts
    assert checkpoint(p)['notified_snapshot'] == before['notified_snapshot']
    assert checkpoint(p)['rounds'] == before['rounds']
    assert not checkpoint(p)['processed_snapshot']['runs']
    assert p.root.facade.run_status(name='oversized', intent='full')['state'] == 'completed'
    # Explicit continuation is a new control event, even with unchanged unread science.
    p.root.call_tool('progression_command', dict(command='pause'))
    p.root.call_tool('progression_command', dict(command='resume'))
    _next_poll(p)
    host = p.coordinator.host
    assert len(host.prompts) == 1
    assert json.loads(host.prompts[-1].split('\n')[-1])['result_omissions'] == 1
    host.finish()
    _next_poll(p)
    assert len(host.prompts) == 1 and not checkpoint(p)['processed_snapshot']['runs']


@pytest.mark.parametrize('late_start', [False, True])
def test_unknown_submission_and_late_start_do_not_confirm_or_replay(progression, late_start):
    p = progression
    _bounded_context(p)
    p.coordinator.tick()
    host = p.coordinator.host
    root = p.root.__class__(p.facade(host.scheduler_session))
    _sealed_result(p, root, 'oversized', interpretation_chars=4000)
    host.finish()
    prior = checkpoint(p)['notified_snapshot']
    submissions = []
    def unknown(_):
        submissions.append(1)
        # A delayed event from the old turn is insufficient to acknowledge the
        # notice now prepared for a different native submission.
        if late_start:
            host.event(dict(method='turn/started', params=dict(threadId=host.identity.thread_id,
                turn=dict(id=host.turn_id))))
        raise sqlite3.OperationalError('uncertain native submission')
    host.start_turn = unknown
    with pytest.raises(sqlite3.OperationalError, match='uncertain native submission'):
        _next_poll(p)
    current = checkpoint(p)
    assert current['fault_class'] == 'outcome_unknown' and row(p)['state'] == 'paused'
    assert current['phase'] == ('running' if late_start else 'prepared')
    assert current['notified_snapshot'] == prior
    assert [entry['name'] for entry in current['notification_snapshot']['runs']] == ['oversized']
    assert not current['processed_snapshot']['runs']
    assert row(p)['host_json'] is not None
    for _ in range(3):
        _next_poll(p)
    assert submissions == [1] and p.coordinator.host is None


def test_notices_coalesce_survive_reconnect_and_reads_do_not_acknowledge(progression):
    p = progression
    p.coordinator.tick()
    host = p.coordinator.host
    root = p.facade(host.scheduler_session)
    for index in range(4):
        root.progression_report(summary='Evidence remains insufficient.', question='Which exact boundary?')
        p.coordinator._save(dict(waiting_seconds=index))
    bindings = p.runtime.scheduler_bindings
    before = row(p)
    status = p.root.call_tool('progression_status', {})
    notices = status['notifications']
    assert len([item for item in notices['items'] if item['category'] == 'user_decision']) == 1
    assert notices['delivery'] == 'pull_only' and notices['read_status'] == 'not_recorded'
    reopened = SchedulerBindingService(bindings.database_path)
    reopened.progression_clock = p.coordinator.clock
    reader = copy(p.root.facade)
    reader.bindings = reopened
    assert reader.progression_status() == status
    assert p.root.call_tool('progression_status', {}) == status
    assert row(p) == before  # A query neither writes nor acknowledges a notice.
    assert 'native-root' not in json.dumps(status)
    p.root.call_tool('progression_message', dict(name='boundary.answer', text='Use the supplied boundary.'))
    host.finish()
    p.now[0] += 6
    p.coordinator.tick()
    status = p.root.call_tool('progression_status', {})
    assert status['reason'] == 'host_active' and status['report'] is None
    assert status['last_report']['question'] == 'Which exact boundary?'
    assert notices['current_id'] != status['notifications']['current_id']
    assert any(item['id'] == notices['current_id'] for item in status['notifications']['items'])


def test_notice_history_is_bounded_with_explicit_omission(progression):
    p = progression
    p.coordinator.tick()
    root = p.facade(p.coordinator.host.scheduler_session)
    for index in range(20):
        root.progression_report(summary='Still open.', question=f'Boundary {index}: ' + '界' * 300)
    status = p.root.call_tool('progression_status', {})
    notices = status['notifications']
    assert len(notices['items']) == 16 and notices['omitted'] >= 4
    assert notices['items'][-1]['question_truncated']
    assert len(status['report']['question']) > 256
    assert len(row(p)['checkpoint_json'].encode()) <= 65536


def test_workbench_projects_reports_cost_gaps_and_authorized_original_links(progression):
    p = progression
    p.coordinator.tick()
    p.facade(p.coordinator.host.scheduler_session).progression_report(
        summary='<script>sealed evidence is insufficient</script>', question='Need another measurement?')
    p.coordinator._save(dict(usage_summary={'coverage': 'partial', 'groups': {
        'root': {'tokens': {'input_tokens': 123, 'cached_input_tokens': 23, 'output_tokens': 7},
                 'failed_threads': 1, 'unmeasured_threads': 1}}},
        resources={'coverage': 'owned_process_tree', 'limitations': ['Detached helper is unmeasured.']}))
    overview = _overview()
    overview['progression'] = p.root.call_tool('progression_status', {})
    overview['active_task_pages']['run']['has_more'] = True
    page = render_workbench(overview, browse_base='/instance/instance-a', csrf_token='csrf').decode()
    for value in ('多个活动分支', 'Need another measurement?', '需用户决定', '系统等待', '普通状态变化',
            '未提供聊天推送和已读回执', '货币费用未测量', '缓存输入是输入子集', 'partial',
            'Detached helper is unmeasured.', '列表达到读取上限', 'Later targets are still open',
            '/instance/instance-a/evidence/safe-image?format=image', '/nodes/artifact%3Agoal'):
        assert value in page
    assert '<script>sealed' not in page and '&lt;script&gt;sealed' in page
    assert '<th>Worker</th><td>未测量 / 未提供</td>' in page
    assert '暂停或停止只阻止后续调度' in page


def test_http_control_roundtrip_shared_state_and_instance_read_authority(tmp_path):
    runtime, state, secret, ui, base = _setup(tmp_path)
    bindings = runtime.scheduler_bindings
    ui.read_model = InstanceReadModel(artifacts=runtime.artifacts, bindings=bindings,
        runs=runtime.runs, approvals=runtime.approvals, executions=runtime.executions,
        operation_catalog=runtime.operation_catalog)
    writer, reader = 'sch_' + 'a'*32, 'sch_' + 'b'*32
    instance = bindings.create_instance_and_bind_session(session_key=writer,
        name='delivery', title='Delivery', objective='Original intent')
    bindings.bind_session(session_key=reader, instance_id=instance.instance_id)
    root = _root(runtime, session_key=reader, secret=secret, base=base)
    bindings.progression_command(instance_id=instance.instance_id, session_key=writer, command='start')
    bindings.progression_report(instance_id=instance.instance_id, session_key=writer,
        summary='Insufficient evidence.', question='Which boundary?')
    try:
        url = urlparse(root.call_tool('instance_current', {})['management_url'])
        capability = parse_qs(url.query)['capability'][0]
        common = dict(capability=capability, csrf=ui.session_id)
        endpoint = f'/api/instances/{instance.instance_id}/overview'
        assert _request(base, 'GET', endpoint)[0] == 403
        response, headers, _ = _request(base, 'POST', '/instances/access', form={
            **common, 'instance_id': instance.instance_id, 'scope': 'read'})
        assert response == 303
        cookie = headers['Set-Cookie']
        before = bindings.progression_status(instance_id=instance.instance_id, internal=True)
        response, _, raw = _request(base, 'GET', endpoint, cookie=cookie)
        assert response == 200
        assert json.loads(raw)['progression']['notifications'] == root.call_tool('progression_status', {})['notifications']
        assert bindings.progression_status(instance_id=instance.instance_id, internal=True) == before
        assert before['owner_session'] == writer
        assert _request(base, 'POST', '/instances/progression', form={'csrf': ui.session_id, 'command': 'pause'}, cookie=cookie)[0] != 303
        for action, expected in [('pause', 'paused'), ('resume', 'active'), ('stop', 'stopped'), ('takeover', 'active')]:
            response, headers, _ = _request(base, 'POST', '/instances/progression', form={**common, 'command': action})
            assert response == 303
            response, _, raw = _request(base, 'GET', headers['Location'])
            assert response == 200 and '最近控制命令的实际结果' in raw.decode()
            status = root.call_tool('progression_status', {})
            assert status['state'] == expected
            assert status['last_command']['command'] == action and status['last_command']['state'] == expected
            assert status['report']['summary'] == 'Insufficient evidence.'
        response, _, raw = _request(base, 'GET', f'/instance/{instance.instance_id}', cookie=cookie)
        assert response == 200 and 'Which boundary?' in raw.decode()
    finally:
        ui.stop()
