"""Caller contract -> frozen task -> actual Worker -> immutable goal judgment."""
import json
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.approval_ui.progression_render import render_progression
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService
from tests.operations.test_progression import progression, checkpoint, row
from tests.operations.test_local_worker_contracts import _worker, _write_result


INTENT = dict(intent='gather_evidence', target='Mean versus mechanism', expected='A bounded mean without causal identification')


def request(name, intent=INTENT):
    return dict(name=name, operation_id='blind.csv.observe.v1',
        inputs=[dict(port='source_table', artifact_names=['source_csv'])],
        instruction='State the bounded arithmetic result and retain limits.',
        **(dict(scientific_intent=intent) if intent else {}))


def active(p):
    p.coordinator.tick()
    return p.root.__class__(p.facade(p.coordinator.host.scheduler_session))


def finish(p, root, name, intent=INTENT):
    root.call_tool('operation_invoke', request(name, intent))
    worker = _worker(p.catalog, p.runtime)
    opened = worker.call_tool('worker_open_assignment', {})
    _write_result(worker)
    worker.call_tool('worker_submit_result', {})
    return opened


def assess(root, name, outcome='advance', evidence=True, reason='The mean is known; causal explanation remains open.'):
    return root.call_tool('progression_report', dict(summary='Consume the sealed result, retaining limitations.',
        assessments=[dict(task_name=name, outcome=outcome, reason=reason,
            evidence_names=[name+'.output'] if evidence else [], limitations='Only two observations.')]))


def test_intent_survives_preflight_run_identity_and_real_worker_start(progression):
    p = progression
    root = active(p)
    pre = root.call_tool('operation_preflight', request('purpose'))
    assert pre['admissible'] and pre['normalized_request']['scientific_intent'] == INTENT
    root.call_tool('operation_invoke', pre['normalized_request'])
    worker = _worker(p.catalog, p.runtime)
    opened = worker.call_tool('worker_open_assignment', {})
    start = json.loads(Path(opened['start_here_path']).read_bytes())
    assert start['scientific_intent'] == INTENT
    assert not {'run_id', 'artifact_ref', 'objective_ref'} & start['scientific_intent'].keys()
    assert root.call_tool('run_status', dict(name='purpose'))['scientific_intent'] == INTENT
    assert root.call_tool('operation_invoke', pre['normalized_request'])['result']['name'] == 'purpose'
    changed = request('purpose', {**INTENT, 'expected':'A different scientific purpose'})
    rejected = root.call_tool('operation_preflight', changed)
    assert not rejected['admissible']
    with pytest.raises(Exception):
        root.call_tool('operation_invoke', changed)


def test_two_tasks_preserve_intents_results_judgment_history_and_readonly_ui(progression, monkeypatch):
    p = progression
    root = active(p)
    finish(p, root, 'first')
    receipt = assess(root, 'first')
    assert receipt['assessment_receipts'] == [dict(task_name='first', revision=1, state='recorded')]
    finish(p, root, 'second', {**INTENT, 'intent':'validate', 'expected':'Test the same observation boundary'})
    assess(root, 'second', 'no_progress')
    assess(root, 'first', 'unknown', evidence=False, reason='Correction: the original assessment was too strong.')
    assess(root, 'first', 'unknown', evidence=False, reason='Correction: the original assessment was too strong.')
    before = row(p)
    monkeypatch.setattr(p.runtime.runs, 'list', lambda **kw: pytest.fail('No whole-instance scan'))
    first = root.call_tool('progression_status', dict(progress_limit=2))
    items = first['progress']['items']
    assert [(v['task_name'], v['revision']) for v in items] == [('first', 2), ('second', 1)]
    assert items[0]['classification'] == 'unknown'
    assert items[1]['classification'] == 'no_progress'
    assert first['closeout']['tasks'][0]['scientific_intent'] == INTENT
    next_page = root.call_tool('progression_status', dict(progress_limit=2, progress_cursor=first['progress']['next_cursor']))
    assert next_page['progress']['items'][0]['classification'] == 'advance'
    assert next_page['progress']['items'][0]['revision'] == 1
    assert next_page['progress']['next_cursor'] is None
    assert row(p) == before
    rendered = render_progression(first, instance_id=p.instance)
    assert '目标进展判断' in rendered and 'Mean versus mechanism' in rendered
    assert 'native-root' not in json.dumps(first)
    reopened = SchedulerBindingService(p.runtime.scheduler_bindings.database_path)
    from scidiscovery.artifact_agent.service.progression_read import progression_read_view
    restored = progression_read_view(bindings=reopened, runs=p.runtime.runs, artifacts=p.runtime.artifacts,
        operation_catalog=p.catalog, instance_id=p.instance, progress_limit=2)
    assert restored['progress'] == first['progress']
    assert len(p.coordinator.host.prompts) == 1


def test_optional_assessment_and_missing_evidence_never_become_scientific_success(progression):
    p = progression
    root = active(p)
    finish(p, root, 'ordinary', intent=None)
    status = root.call_tool('progression_status', {})
    assert status['progress']['items'] == []
    assert 'scientific_intent' not in status['closeout']['tasks'][0]
    assess(root, 'ordinary', evidence=False)
    item = root.call_tool('progression_status', {})['progress']['items'][0]
    assert item['assessment']['outcome'] == 'advance'
    assert item['classification'] == 'unknown' and item['evidence_support'] == 'missing_task_output'
    assert root.call_tool('run_status', dict(name='ordinary'))['state'] == 'completed'


def test_reports_reject_wrong_goal_and_nonterminal_task_without_partial_history(progression):
    p = progression
    root = active(p)
    root.call_tool('operation_invoke', request('pending'))
    with pytest.raises(Exception, match='terminal task'):
        assess(root, 'pending', evidence=False)
    worker = _worker(p.catalog, p.runtime)
    worker.call_tool('worker_open_assignment', {})
    _write_result(worker)
    worker.call_tool('worker_submit_result', {})
    prior = checkpoint(p).get('report')
    with pytest.raises(Exception):
        root.call_tool('progression_report', dict(summary='Must not commit partially.', assessments=[
            dict(task_name='pending', outcome='advance', reason='Valid first entry', evidence_names=['pending.output']),
            dict(task_name='absent', outcome='advance', reason='Unknown task')]))
    assert root.call_tool('progression_status', {})['progress']['items'] == []
    assert checkpoint(p).get('report') == prior
    # Same task name/material never grants membership in an unrelated goal.
    root.call_tool('artifact_ingest_text', dict(name='different-goal', text='An unrelated scientific objective.'))
    old_checkpoint = checkpoint(p)
    old_objective = json.loads(row(p)['objective_ref_json'])
    p.coordinator.host.finish()
    p.root.call_tool('progression_command', dict(command='pause'))
    p.coordinator.tick()
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='different-goal'))
    root = active(p)
    with pytest.raises(Exception, match='not associated'):
        assess(root, 'pending')
    current = checkpoint(p)
    assert current['admissions'] == old_checkpoint['admissions']
    assert current['admissions']['pending']['objective_ref'] == old_objective
    assert current['started_at'] == old_checkpoint['started_at']
    assert current['rounds'] >= old_checkpoint['rounds']
    assert current['relevant_runs_objective_ref'] == json.loads(row(p)['objective_ref_json'])
    assert p.coordinator._snapshot(row(p))['runs'] == []
    status = root.call_tool('progression_status', {})
    assert status['progress']['items'] == []
    assert status['closeout']['tasks'] == []


def test_progress_artifacts_survive_instance_archive_and_restore(progression):
    from tests.operations.synchronous_archive_fixture import SynchronousFixtureArchive
    from tests.operations.test_instance_archive import save_archive, restore_archive
    p = progression
    root = active(p)
    finish(p, root, 'archived')
    assess(root, 'archived')
    p.coordinator.host.finish()
    p.now[0] += 6
    p.coordinator.tick()
    p.coordinator.host.finish()
    p.root.call_tool('progression_command', dict(command='pause'))
    p.coordinator.tick()
    expected = root.call_tool('progression_status', {})
    p.runtime.runs._synchronous_archive_fixture = True
    archive = SynchronousFixtureArchive(p.runtime)
    save_archive(archive, p.instance)
    archived = archive.archived_model(p.instance).progression_status(p.instance)
    assert archived['progress'] == expected['progress']
    assert archived['terminal_deliveries'] == expected['terminal_deliveries']
    assert archived['progress_shadow'] == expected['progress_shadow']
    assert archived['terminal_deliveries']['items'][0]['consumption'] == 'settled'
    assert archived['closeout']['tasks'][0]['scientific_intent'] == INTENT
    restore_archive(archive, p.instance)
    from scidiscovery.artifact_agent.service.progression_read import progression_read_view
    restored = progression_read_view(bindings=p.runtime.scheduler_bindings, runs=p.runtime.runs,
        artifacts=p.runtime.artifacts, operation_catalog=p.catalog, instance_id=p.instance)
    assert restored['progress'] == expected['progress']
    assert restored['terminal_deliveries'] == expected['terminal_deliveries']
    assert restored['progress_shadow'] == expected['progress_shadow']


def test_unicode_history_pages_bound_bytes_and_do_not_lose_corrections(progression):
    from scidiscovery.artifact_agent.schema.common import canonical_json
    p = progression
    root = active(p)
    finish(p, root, 'bounded')
    for index in range(3):
        root.call_tool('progression_report', dict(summary='Revision history.', assessments=[dict(
            task_name='bounded', outcome='unknown', reason=str(index)+'界'*1000,
            limitations='界'*1000, evidence_names=['bounded.output'])]))
    revisions, after = [], None
    while True:
        page = root.call_tool('progression_status', dict(progress_cursor=after, progress_limit=8))['progress']
        assert len(canonical_json(page)) <= 16384
        revisions.extend(item['revision'] for item in page['items'])
        if page['next_cursor'] is None:
            break
        assert page['next_cursor'] != after
        after = page['next_cursor']
    assert revisions == [3, 2, 1]
    from scidiscovery.artifact_agent.service.scientific_progress import progress_page
    for changed in (dict(row(p), instance_id='another-instance'),
                    dict(row(p), objective_ref_json=json.dumps({**json.loads(row(p)['objective_ref_json']),
                        'artifact_id':'another-goal'}))):
        with pytest.raises(ValueError, match='Invalid progress cursor'):
            progress_page(bindings=p.runtime.scheduler_bindings, artifacts=p.runtime.artifacts,
                row=changed, cursor=after)


def test_control_judgment_is_never_a_scientific_original_or_evidence(progression):
    p = progression
    root = active(p)
    finish(p, root, 'science')
    assess(root, 'science')
    objective = ArtifactRef.model_validate_json(row(p)['objective_ref_json'])
    record = p.runtime.scheduler_bindings.progress_assessments(instance_id=p.instance, objective_ref=objective)[0]
    ref = ArtifactRef.model_validate_json(record['artifact_ref_json'])
    # Even a mistakenly bound internal record does not become scientific evidence.
    p.runtime.scheduler_bindings.bind(instance=p.instance, namespace='artifact', name='control-record',
        object_id=ref.artifact_id, request_fingerprint=ref.sha256)
    with pytest.raises(Exception, match='not a public scientific original'):
        root.call_tool('artifact_catalog', dict(name='control-record', view='content'))
    with pytest.raises(Exception, match='visible scientific original'):
        root.call_tool('progression_report', dict(summary='Invalid circular support.', assessments=[dict(
            task_name='science', outcome='advance', reason='Cannot cite myself.', evidence_names=['control-record'])]))
    assert len(root.call_tool('progression_status', {})['progress']['items']) == 1


def test_switch_goal_preserves_inflight_task_without_claiming_its_result(progression):
    p = progression
    root = active(p)
    root.call_tool('operation_invoke', request('old-inflight'))
    root.call_tool('artifact_ingest_text', dict(name='next-goal', text='An unrelated next objective.'))
    host = p.coordinator.host
    host.finish()
    p.root.call_tool('progression_command', dict(command='pause'))
    p.coordinator.tick()
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='next-goal'))
    p.now[0] += 6
    p.coordinator.tick()
    brief = json.loads(host.prompts[-1].split('\n')[-1])
    assert brief['objective']['name'] == 'next-goal'
    assert [v['name'] for v in brief['active_tasks']] == ['old-inflight']
    closeout = root.call_tool('progression_status', {})['closeout']
    assert closeout['tasks'] == []
    assert [v['name'] for v in closeout['in_flight']] == ['old-inflight']
    worker = _worker(p.catalog, p.runtime)
    worker.call_tool('worker_open_assignment', {})
    _write_result(worker)
    worker.call_tool('worker_submit_result', {})
    assert p.coordinator._snapshot(row(p))['runs'] == []
    with pytest.raises(Exception, match='not associated'):
        assess(root, 'old-inflight')


def deliveries(p, objective=None):
    return p.runtime.scheduler_bindings.terminal_deliveries(instance_id=p.instance,
        objective_ref=objective or ArtifactRef.model_validate_json(row(p)['objective_ref_json']))


@pytest.mark.parametrize('boundary', ['admission', 'completion', 'early_admission'])
def test_terminal_delivery_settles_once_without_assessment_through_real_facade(progression, boundary):
    p = progression
    root = active(p)
    finish(p, root, 'delivered', intent=None)
    host = p.coordinator.host
    host.finish()
    if boundary == 'early_admission':
        native_start = host.start_turn
        def early(prompt):
            assert checkpoint(p)['phase'] == 'prepared'
            root.call_tool('operation_invoke', request('next'))
            assert deliveries(p) == []  # accepted tool call is not a proven native turn
            return native_start(prompt)
        host.start_turn = early
    p.now[0] += 6
    p.coordinator.tick()
    assert len(deliveries(p)) == 1
    record = deliveries(p)[0]
    assert json.loads(record['delivery_json'])['original_read'] == 'not_confirmed'
    if boundary == 'completion':
        assert record['consumed_boundary'] is None
        host.finish()
        root.call_tool('operation_invoke', request('next'))
    elif boundary == 'admission':
        assert record['consumed_boundary'] is None
        root.call_tool('operation_invoke', request('next'))
        host.finish()
    else:
        host.finish()
    expected = 'turn_completed' if boundary == 'completion' else 'next_task_admission'
    assert deliveries(p)[0]['consumed_boundary'] == expected
    host.finish()  # duplicate native completion and rereads never add consumption
    root.call_tool('run_status', dict(name='delivered'))
    assert len(deliveries(p)) == 1 and deliveries(p)[0]['consumed_boundary'] == expected
    assert root.call_tool('progression_status', {})['progress']['items'] == []
    reopened = SchedulerBindingService(p.runtime.scheduler_bindings.database_path)
    assert reopened.terminal_deliveries(instance_id=p.instance,
        objective_ref=ArtifactRef.model_validate_json(row(p)['objective_ref_json'])) == deliveries(p)


def test_unknown_native_submission_does_not_consume_prepared_terminal_delivery(progression):
    from scidiscovery.platforms.codex_app_server import HostError
    p = progression
    root = active(p)
    finish(p, root, 'uncertain')
    p.coordinator.host.finish()
    def lost(prompt):
        raise HostError('rpc_timeout')
    p.coordinator.host.start_turn = lost
    p.now[0] += 6
    with pytest.raises(HostError):
        p.coordinator.tick()
    assert checkpoint(p)['terminal_delivery']['items'][0]['name'] == 'uncertain'
    assert deliveries(p) == []
    p.coordinator.tick()
    assert deliveries(p) == []


def test_terminal_consumption_survives_goal_revision_and_budget_is_cumulative(progression):
    p = progression
    root = active(p)
    finish(p, root, 'old-goal')
    p.coordinator.host.finish()
    p.now[0] += 6
    p.coordinator.tick()
    p.coordinator.host.finish()
    original = ArtifactRef.model_validate_json(row(p)['objective_ref_json'])
    saved_shadow = p.runtime.scheduler_bindings.progress_shadow(instance_id=p.instance, objective_ref=original)
    saved = deliveries(p)
    budget = checkpoint(p)['admissions']
    root.call_tool('artifact_ingest_text', dict(name='new-goal', text='A different exact goal.'))
    p.root.call_tool('progression_command', dict(command='pause'))
    p.coordinator.tick()
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='new-goal'))
    p.coordinator.tick()
    assert deliveries(p) == []
    assert deliveries(p, original) == saved
    assert p.runtime.scheduler_bindings.progress_shadow(instance_id=p.instance, objective_ref=original) == saved_shadow
    assert root.call_tool('progression_status', {})['progress_shadow']['counts']['consumed'] == 0
    assert checkpoint(p)['admissions'] == budget


def test_same_turn_native_tool_delivery_counts_without_mutating_read_service(progression):
    p = progression
    root = active(p)
    finish(p, root, 'same-turn', intent=None)
    before = row(p)
    projection = root.call_tool('run_status', dict(name='same-turn', intent='decision'))
    assert row(p) == before and deliveries(p) == []
    host = p.coordinator.host
    notification = dict(method='item/completed', params=dict(threadId=host.identity.thread_id, turnId=host.turn_id,
        item=dict(type='mcpToolCall', id='read-1', server='scidiscovery', tool='scid_call', status='completed',
            arguments=dict(name='run_status', arguments=dict(name='same-turn')),
            result=dict(content=[], structuredContent=projection))))
    from copy import deepcopy
    wrong = deepcopy(notification)
    wrong['params']['threadId'] = 'foreign-worker'
    host.event(wrong)
    assert deliveries(p) == []
    wrong = deepcopy(notification)
    wrong['params']['item']['server'] = 'other-server'
    host.event(wrong)
    assert deliveries(p) == []
    wrong = deepcopy(notification)
    wrong['params']['item']['result'] = dict(content=[dict(type='text', text=json.dumps(projection))])
    host.event(wrong)
    assert deliveries(p) == []
    assert root.call_tool('progression_status', {})['terminal_deliveries']['coverage'] == 'structured_tool_result_unavailable'
    host.event(notification)
    assert deliveries(p)[0]['consumed_boundary'] is None
    root.call_tool('operation_invoke', request('next-same-turn'))
    assert deliveries(p)[0]['consumed_boundary'] == 'next_task_admission'
    host.event(notification)
    host.finish()
    assert len(deliveries(p)) == 1
    p.coordinator.tick()
    p.now[0] += 6
    p.coordinator.tick()
    assert len(host.prompts) == 1  # already delivered science must not wake ordinary waiting


def test_delivery_history_ninth_task_continues_through_mcp_and_ui_with_goal_scope(progression):
    from urllib.parse import parse_qs, urlparse
    from html import unescape
    import re
    from scidiscovery.artifact_agent.approval_ui.read_model import InstanceReadModel
    from scidiscovery.artifact_agent.service.scientific_progress import terminal_delivery_page
    p = progression
    bindings = p.runtime.scheduler_bindings
    p.root.call_tool('progression_command', dict(command='pause'))
    bindings.save_agent_settings(p.instance, {'progression': {'max_tasks':10, 'max_reviews':0}},
        expected_revision=0, maintenance=bindings.control_maintenance)
    from tests.operations.research_loop_fixtures import authorize_loop
    authorize_loop(p.runtime, p.instance, p.user, 'goal')
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='goal'))
    root = active(p)
    for index in range(9):
        finish(p, root, f'history-{index}')
    p.coordinator.host.finish()
    p.now[0] += 6
    p.coordinator.tick()
    p.coordinator.host.finish()
    first = root.call_tool('progression_status', {})['terminal_deliveries']
    assert len(first['items']) == 8 and first['omitted']
    args = {key: value for key, value in first['continuation'].items() if key != 'tool'}
    before = row(p)
    last = root.call_tool('progression_status', args)['terminal_deliveries']
    assert [item['task_name'] for item in last['items']] == ['history-8']
    assert last['next_cursor'] is None and not last['omitted']
    assert row(p) == before
    model = InstanceReadModel(artifacts=p.runtime.artifacts, bindings=bindings, runs=p.runtime.runs,
        approvals=p.runtime.approvals, executions=p.runtime.executions, operation_catalog=p.catalog)
    html = render_progression(root.call_tool('progression_status', {}), instance_id=p.instance)
    link = next(href for href in re.findall("href='([^']+)'", html) if 'delivery_cursor=' in href)
    query = parse_qs(urlparse(unescape(link)).query)
    ui_page = model.overview(p.instance, delivery_cursor=query['delivery_cursor'][0],
        delivery_limit=int(query['delivery_limit'][0]))['progression']['terminal_deliveries']
    assert ui_page == last
    with pytest.raises(ValueError, match='Invalid delivery cursor'):
        terminal_delivery_page(bindings=bindings, row={**row(p), 'instance_id':'other-instance'}, cursor=first['next_cursor'])
    root.call_tool('artifact_ingest_text', dict(name='history-new-goal', text='A new goal.'))
    p.root.call_tool('progression_command', dict(command='pause'))
    p.coordinator.tick()
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='history-new-goal'))
    with pytest.raises(Exception, match='Invalid delivery cursor'):
        p.root.call_tool('progression_status', args)
    schema = p.root._tools['progression_status'].schema()
    assert {'delivery_cursor', 'delivery_limit'} <= schema['inputSchema']['properties'].keys()


def test_unconfirmed_indirect_execution_goal_has_explicit_coverage_and_execution_surface(progression, monkeypatch):
    from types import SimpleNamespace
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    from scidiscovery.artifact_agent.schema.refs import ActorRef
    p = progression
    root = active(p)
    objective = ArtifactRef.model_validate_json(row(p)['objective_ref_json'])
    def artifact(name, parent):
        return p.runtime.artifacts.register(name.encode(), ArtifactRegistration(kind='fixture', schema_id='opaque',
            payload_schema_version=1, media_type='text/plain', creator=ActorRef(actor_type='service', actor_id='fixture'),
            parent_refs=(parent,)), idempotency_key='review-fixture:'+name).ref
    middle = artifact('intermediate', objective)
    payload = artifact('execution-package', middle)
    request_ref = artifact('execution-request', payload)
    reader = SimpleNamespace(database_path='unused', active_ids=lambda **kwargs: ('execution-fixture',),
        record_references=lambda _: dict(request_ref=request_ref, payload_ref=payload),
        status=lambda _: pytest.fail('Unconfirmed relation must not be presented as associated'))
    monkeypatch.setattr(root.facade, 'executions', reader)
    before = row(p)
    observed = root.call_tool('progression_status', {})['external_work']
    assert observed['items'] == [] and observed['association_coverage'] == 'partial'
    assert observed['omissions'] == ['candidate_goal_association_unconfirmed']
    assert observed['read'] == dict(tool='execution_list', surface='execution', limit=10)
    assert row(p) == before
