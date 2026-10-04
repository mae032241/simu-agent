"""Regression boundaries for durable notifications, recovery identity and reply budgets."""
import json
from copy import deepcopy
from dataclasses import replace

import pytest

from tests.operations.test_analysis_claim_scope import generic_worker, submit
from tests.operations.test_result_analysis_tool import limited_report


@pytest.mark.parametrize('count', [30, 3])
def test_history_attention_preserves_producer_pages_and_opaque_continuations(tmp_path, monkeypatch, count):
    from tests.operations.test_attempt_history import history_system, SECRET
    from tests.operations.test_run_list_bounds import metrics
    from scidiscovery.artifact_agent.service.progression_records import read_history_cursor
    system = history_system(tmp_path, count)
    root = system.root
    expected_notices = [f'task-{index:04d}' for index in range(min(8, count))]
    for name in expected_notices:
        system.runs.record_attention(system.ids[name], scope='submission:control',
            code='submission_intervention_required')
    original = root.facade.run_list
    produced = []
    def capture(**query):
        value = original(**query)
        produced.append(deepcopy(value))
        return value
    monkeypatch.setattr(root.facade, 'run_list', capture)
    query, seen, notifications, pages = dict(view='history', limit=20), [], [], []
    for _ in range(30):
        reply = root.call_tool('run_list', query)
        pages.append(reply)
        metrics(f'history-attention-{count}', dict(produced=produced, delivered=pages, expected=system.expected))
        if len(pages) == 1 and count == 30:
            assert len(json.dumps(produced[-1], separators=(',', ':')).encode()) > 4096
        assert {key:value for key,value in reply.items() if key != 'attention_notifications'} == produced[-1]
        assert len(json.dumps(reply, ensure_ascii=False, separators=(',', ':')).encode()) <= 16384
        seen.extend(item['name'] for item in reply['runs'])
        notifications.extend(reply.get('attention_notifications', {}).get('events', []))
        if len(pages) == 1 and count == 30:
            # The real eight-notice burst cannot all fit beside this full page.
            delivered = {event['name'] for event in notifications}
            assert 0 < len(delivered) < len(expected_notices)
            pending, _ = root.facade.prepare_attention_notifications()
            assert {event['name'] for event in pending['events']} == set(expected_notices) - delivered
        if not reply['continuation']:
            assert reply['next_before'] is None
            break
        # Both opaque positions remain valid and resume after the same member.
        positions = [read_history_cursor(token, secret=SECRET, instance_id=system.instance,
            state=None, limit=20)['after'] for token in (reply['next_before'],reply['continuation']['before'])]
        assert positions[0] == positions[1]
        query = dict(reply['continuation']);query.pop('tool')
    else:
        pytest.fail('finite history fixture must not repeat or loop')
    assert seen == system.expected and len(set(seen)) == count
    assert [event['name'] for event in notifications] == expected_notices
    assert root.facade.prepare_attention_notifications() is None


def test_history_notice_with_no_remaining_bytes_does_not_call_ack(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.interfaces import mcp_root
    from tests.operations.test_attempt_history import history_system
    system = history_system(tmp_path, 3)
    root = system.root
    system.runs.record_attention(system.ids['task-0000'], scope='submission:control',
        code='submission_intervention_required')
    # Inject total reply pressure at the real producer/router boundary. Reducing
    # this allowance does not change the producer's page or its cursor budget.
    original = root.facade.run_list
    produced, acknowledgements = [], []
    def capture(**query):
        value = original(**query)
        produced.append(deepcopy(value))
        monkeypatch.setattr(mcp_root, 'HISTORY_ATTENTION_REPLY_MAX_BYTES',
            len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()))
        return value
    ack = root.facade.acknowledge_attention_notifications
    def acknowledge(delivery, count):
        acknowledgements.append(count)
        return ack(delivery, count)
    monkeypatch.setattr(root.facade, 'run_list', capture)
    monkeypatch.setattr(root.facade, 'acknowledge_attention_notifications', acknowledge)
    reply = root.call_tool('run_list', dict(view='history', limit=20))
    assert reply == produced[-1] and acknowledgements == []
    assert root.facade.prepare_attention_notifications() is not None
    # Another ordinary reply can deliver this exact pending notice.
    assert root.call_tool('instance_current', {})['attention_notifications']['events'][0]['name'] == 'task-0000'
    assert acknowledgements == [1] and root.facade.prepare_attention_notifications() is None


def test_unchanged_notifications_do_not_take_a_write_lock(tmp_path, monkeypatch):
    worker, _, system = generic_worker(tmp_path, return_system=True)
    runs, root = system[1].runs, system[2]
    runs._submission_failure(worker._run_id, RuntimeError('control'))
    assert root.call_tool('instance_current', {})['attention_notifications']['events']
    root.call_tool('lifecycle_events', {})
    statements = []
    connect = root.facade.bindings._connect
    def traced():
        connection = connect()
        connection.set_trace_callback(statements.append)
        return connection
    monkeypatch.setattr(root.facade.bindings, '_connect', traced)
    assert 'attention_notifications' not in root.call_tool('instance_current', {})
    assert 'attention_notifications' not in root.call_tool('lifecycle_events', {})
    assert not any('BEGIN IMMEDIATE' in sql for sql in statements)
    assert root.facade.prepare_attention_notifications() is None


@pytest.mark.parametrize('mode', ['resume_from', 'draft_from'])
@pytest.mark.parametrize('keep_binding', [False, True])
def test_resume_completion_supersedes_old_submission_issue(tmp_path, mode, keep_binding):
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    worker, _, system = generic_worker(tmp_path, return_system=True)
    catalog, runtime, root, *_ = system
    runs = runtime.runs
    runs._submission_failure(worker._run_id, RuntimeError('control'))
    if keep_binding:
        runs.record_attention(worker._run_id, scope='implementation:retained', code='experiment_implementation_unavailable')
    value = runs.status(worker._run_id)
    runs.record_failure(value.run_id, reason='Recover after control repair', expected_state=value.state,
        expected_last_activity_at=value.last_activity_at)
    request = dict(name='repaired', operation_id=value.operation_id,
        max_attempts=2, instruction='Continue after control repair.', inputs=[
            dict(port='experiment_plan', artifact_names=['plan']),
            dict(port='experiment_results', artifact_names=['generic_results']),
            dict(port='curve_bundle', artifact_names=['generic_bundle'])])
    request[mode] = 'generic_analysis'
    assert root.call_tool('operation_invoke', request)['result']['state'] == 'queued'
    following = LocalWorkerMCPRouter(runs, operation_id=value.operation_id,
        operation_digest=catalog.operation(value.operation_id).digest)
    opened = following.call_tool('worker_open_assignment', {})
    assert submit(following, opened, limited_report())['state'] == 'completed'
    attention = runs.submission_attention(runs.status(value.run_id))
    codes = {item['code'] for item in attention['issues']} if attention else set()
    assert ('submission_intervention_required' in codes) == (mode == 'draft_from')
    assert ('experiment_implementation_unavailable' in codes) == keep_binding
    notices, _ = runs.pending_attention_notices(instance=value.instance_id, observer='fresh-root', limit=8)
    assert bool(notices['events']) == bool(codes)


def test_consumer_subset_cannot_disambiguate_legacy_execution(tmp_path, monkeypatch):
    from tests.operations.test_experiment_approval_handoff import experiment, start
    from tests.operations.test_implementation_receipt_identity import revised_material, execution_id
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    from scidiscovery.operation_contract import DiagnosticError
    f = experiment(tmp_path, monkeypatch, seconds=60)
    create = f.runtime.executions.create
    def historical_request(**kwargs):
        kwargs['labels'] = {k:v for k,v in kwargs['labels'].items() if k != 'implementation_receipt'}
        return create(**kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(f.runtime.executions, 'create', historical_request)
        assert start(f)['state'] == 'running'
    _, revised = revised_material(f)
    eid = execution_id(f)
    # A consumer has a valid exact binding to only one of the author's two receipts.
    # Its narrowed input visibility must never determine the original execution identity.
    consumer = f.runs.status(f.old_id)
    binding = replace(consumer.inputs[0], source_name='selected_receipt',
        artifact_ref=ArtifactRef.model_validate(revised['artifact_ref']))
    consumer = replace(consumer, inputs=(*consumer.inputs, binding))
    with pytest.raises(DiagnosticError, match='historical execution'):
        f.coordinator._execution_implementation_record(consumer, eid)
    assert f.adapter.submits == 1


@pytest.mark.parametrize('tool', ['run_list', 'scientific_inventory'])
@pytest.mark.parametrize('view', ['summary', 'detail'])
def test_notifications_share_list_budget_without_losing_rows(tmp_path, monkeypatch, tool, view):
    from scidiscovery.agent_execution_settings import load_settings
    from scidiscovery.artifact_agent.interfaces.mcp_response_views import page
    worker, _, system = generic_worker(tmp_path, return_system=True)
    runs, root = system[1].runs, system[2]
    settings = tmp_path / 'settings.json'
    settings.write_text(json.dumps({'mcp_read':{'summary_max_bytes':1024, 'detail_max_bytes':1024}}))
    runs.agent_settings = load_settings(settings)
    runs._submission_failure(worker._run_id, RuntimeError('control'))
    field, key = ('runs', 'name') if tool == 'run_list' else ('objects', 'artifact_name')
    entries = [{key:f'item{i:03d}' + 'x'*120, 'state':'failed', 'operation_id':'science.experiment.v1',
        'kind':'report', 'schema':'science.report.v1', 'historical':False} for i in range(20)]
    def listing(**args):
        if tool == 'scientific_inventory':
            return {field:entries}
        selected, cursor = page(entries, key=key, limit=args['limit'], before=args['before'])
        return {field:selected, 'next_before':cursor}
    monkeypatch.setattr(root.facade, tool, listing)
    seen, cursor, notifications = [], None, []
    for _ in range(30):
        result = root.call_tool(tool, {'view':view, 'limit':100, 'before':cursor})
        assert len(json.dumps(result, ensure_ascii=False, separators=(',', ':')).encode()) <= 1024
        seen.extend(item[key] for item in result[field])
        notifications.extend(result.get('attention_notifications', {}).get('events', []))
        cursor = result['next_before']
        if cursor is None:
            break
    assert seen == [item[key] for item in entries]
    assert len(notifications) == 1
    assert root.facade.prepare_attention_notifications() is None


def test_notice_that_does_not_fit_remains_pending(tmp_path, monkeypatch):
    from scidiscovery.agent_execution_settings import load_settings
    worker, _, system = generic_worker(tmp_path, return_system=True)
    runs, root = system[1].runs, system[2]
    settings = tmp_path / 'settings.json'
    settings.write_text(json.dumps({'mcp_read':{'summary_max_bytes':1024}}))
    runs.agent_settings = load_settings(settings)
    runs._submission_failure(worker._run_id, RuntimeError('control'))
    monkeypatch.setattr(root.facade, 'run_list', lambda **_: {'runs':[
        {'name':'n'*240, 'state':'failed', 'operation_id':'x'*550}], 'next_before':None})
    result = root.call_tool('run_list', {'view':'summary'})
    assert len(json.dumps(result, ensure_ascii=False, separators=(',', ':')).encode()) <= 1024
    assert 'attention_notifications' not in result
    assert root.facade.prepare_attention_notifications() is not None
    assert root.call_tool('instance_current', {})['attention_notifications']['events']
    assert root.facade.prepare_attention_notifications() is None


def test_stale_acknowledgement_cannot_hide_a_new_generation(tmp_path):
    worker, _, system = generic_worker(tmp_path, return_system=True)
    runs, root = system[1].runs, system[2]
    runs._submission_failure(worker._run_id, RuntimeError('control'))
    _, old = root.facade.prepare_attention_notifications()
    runs._submission_failure(worker._run_id, TimeoutError('timeout'))
    _, new = root.facade.prepare_attention_notifications()
    root.facade.acknowledge_attention_notifications(new, 1)
    root.facade.acknowledge_attention_notifications(old, 1)
    assert root.facade.prepare_attention_notifications() is None


def test_old_hash_cursor_cannot_suppress_upgraded_notice(tmp_path):
    worker, _, system = generic_worker(tmp_path, return_system=True)
    runs, root = system[1].runs, system[2]
    runs._submission_failure(worker._run_id, RuntimeError('control'))
    notices, delivery = root.facade.prepare_attention_notifications()
    instance, observer, receipts = delivery
    root.facade.bindings.observe_state_changes(instance=instance, observer_key=observer,
        states=(('attention', receipts[0][0], '999999999999999999999999abcdef'),))
    assert root.call_tool('instance_current', {})['attention_notifications'] == notices
    assert root.facade.prepare_attention_notifications() is None


def test_notification_codes_are_bounded_and_omission_is_explicit(tmp_path):
    worker, _, system = generic_worker(tmp_path, return_system=True)
    runs, root = system[1].runs, system[2]
    for number in range(10):
        runs.record_attention(worker._run_id, scope='implementation:' + str(number),
            code='experiment_implementation_unavailable' if number < 8 else 'experiment_implementation_ambiguous')
    event = root.call_tool('instance_current', {})['attention_notifications']['events'][0]
    detail = event['attention_required']
    assert detail['total'] == 10 and detail['issues_truncated']
    assert len(detail['codes']) <= 8


@pytest.mark.parametrize('author_metadata', [True, False])
def test_legacy_execution_created_by_resume_successor_retains_receipt(tmp_path, monkeypatch, author_metadata):
    from pathlib import Path
    from tests.operations.test_experiment_approval_handoff import experiment, start
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from scidiscovery.artifact_agent.service.experiment_execution import bind_experiment_services
    from scidiscovery.artifact_agent.schema.common import canonical_json
    f = experiment(tmp_path, monkeypatch, seconds=60)
    origin = f.run_id
    value = f.runs.status(origin)
    f.runs.record_failure(origin, reason='Owner interrupted before submission', expected_state='running',
        expected_last_activity_at=value.last_activity_at)
    result = f.root.call_tool('operation_invoke', {**f.invocation, 'name':'resumed',
        'resume_from':'continuation', 'max_attempts':2})
    assert result['result']['state'] == 'queued', result
    f.run_id = f.runtime.scheduler_bindings.resolve(instance=f.instance.instance_id, namespace='run', name='resumed')
    f.runs.worker_connections.attach(run_id=f.run_id, platform_session='resume-fixture', thread_id='resumed')
    compiled = f.catalog.operation('science.experiment.v1')
    services = bind_experiment_services(f.runs, compiled, dict(f.coordinator.worker_services), coordinator=f.coordinator)
    f.worker = LocalWorkerMCPRouter(f.runs, operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest, tool_services=services)
    f.workspace = Path(f.worker.call_tool('worker_open_assignment', {})['workspace_path'])
    # Seal a NEW package in S; O cannot see this receipt. The execution request
    # still labels O as its task root, as pre-receipt-tag releases did.
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    body = json.loads(f.runtime.artifacts.read(ArtifactRef.model_validate(f.implementation['artifact_ref'])))
    body['implementation']['resource_limits']['wall_time_seconds'] = 60
    (f.workspace / 'scratch/experiment.json').write_bytes(canonical_json(body['implementation']))
    register = f.runtime.artifacts.register
    create = f.runtime.executions.create
    def historical_package(payload, registration, **kwargs):
        if not author_metadata and registration.kind == 'experiment_execution_package':
            registration = registration.model_copy(update={'labels':{
                k:v for k,v in registration.labels.items() if k != 'experiment_run'}})
        return register(payload, registration, **kwargs)
    def historical_request(**kwargs):
        kwargs['labels'] = {k:v for k,v in kwargs['labels'].items() if k != 'implementation_receipt'}
        return create(**kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(f.runtime.artifacts, 'register', historical_package)
        f.alias = f.worker.call_tool('worker_experiment_prepare', {})['implementation']
        patch.setattr(f.runtime.executions, 'create', historical_request)
        assert start(f)['state'] == 'running'
    bindings = f.runtime.scheduler_bindings.list(instance=f.instance.instance_id, namespace='execution',
        name_prefix='experiment-' + origin + '-')
    assert len(bindings) == 1
    eid = bindings[0].object_id
    assert f.coordinator._execution_owner(eid) == origin != f.run_id
    exact = f.runs.sealed_material_record(f.runs.status(f.run_id), f.alias)
    assert f.coordinator._execution_implementation_record(f.runs.status(f.run_id), eid)['artifact_ref'] == exact['artifact_ref']
    f.adapter.state = 'succeeded'
    f.worker.call_tool('worker_experiment_execute', {'action':'advance'})
    collected = f.worker.call_tool('worker_experiment_execute', {'action':'collect'})
    assert collected['state'] == 'collected'
    assert f.worker.call_tool('worker_experiment_execute', {'action':'export', 'output_name':'binary'})['path']
    assert f.adapter.submits == 1


def test_concurrent_replies_claim_each_notification_once(tmp_path, monkeypatch):
    worker, _, system = generic_worker(tmp_path, return_system=True)
    runs, root = system[1].runs, system[2]
    runs._submission_failure(worker._run_id, RuntimeError('control'))
    # Deterministically interleave two responses after both have peeked, before
    # either claims. This also exercises the public response filtering boundary.
    batch = root.facade.prepare_attention_notifications()
    monkeypatch.setattr(root.facade, 'prepare_attention_notifications', lambda **_: batch)
    assert root.call_tool('instance_current', {})['attention_notifications']['events']
    assert 'attention_notifications' not in root.call_tool('instance_current', {})
    assert root.facade.attention_notifications() is None


def test_notice_projection_does_not_rewrite_history_and_migrates_cursor(tmp_path):
    from scidiscovery.artifact_agent.service.run_attention import migrate_notices
    worker, _, system = generic_worker(tmp_path, return_system=True)
    runs, root = system[1].runs, system[2]
    run_id = worker._run_id
    runs._submission_failure(run_id, RuntimeError('control'))
    assert root.call_tool('instance_current', {})['attention_notifications']['events']
    with runs._connect() as connection:
        # Downgrade just the projection to the immediately preceding format.
        row = connection.execute('SELECT * FROM run_attention_notices WHERE run_id=?', (run_id,)).fetchone()
        connection.execute("UPDATE run_activity SET activity='attention_notice' WHERE rowid=?", (row['version'],))
        connection.execute('DELETE FROM run_attention_notices WHERE run_id=?', (run_id,))
        migrate_notices(connection)
        migrate_notices(connection)
        old = tuple(connection.execute('SELECT rowid,* FROM run_activity WHERE rowid=?', (row['version'],)).fetchone())
    assert root.facade.prepare_attention_notifications() is None  # original version cursor survives
    runs._submission_failure(run_id, TimeoutError('another issue'))
    assert root.call_tool('instance_current', {})['attention_notifications']['events']
    with runs._connect() as connection:
        assert tuple(connection.execute('SELECT rowid,* FROM run_activity WHERE rowid=?', (row['version'],)).fetchone()) == old
        assert connection.execute('SELECT count(*) FROM run_attention_notices WHERE run_id=?', (run_id,)).fetchone()[0] == 1
