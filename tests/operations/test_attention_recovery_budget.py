"""Regression boundaries for durable notifications, recovery identity and reply budgets."""
import json
from dataclasses import replace

import pytest

from tests.operations.test_analysis_claim_scope import generic_worker, submit
from tests.operations.test_result_analysis_tool import limited_report


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
