"""Real reader, MCP projection and admission boundaries; no native model calls."""
import json
from copy import deepcopy

import pytest

from scripts.b6_evidence import usage_report
from scripts.native_usage_audit import audit
from scidiscovery.agent_execution_settings import MaterialInputSettings, ProgressionSettings
from scidiscovery.artifact_agent.service.input_reader import read
from scidiscovery.artifact_agent.service.progression_budget import token_budget
from scidiscovery.artifact_agent.interfaces.mcp_response_views import root_response
from scidiscovery.artifact_agent.interfaces.mcp_root_shared import RootToolError
from tests.operations.test_progression import progression, row, checkpoint
from tests.operations.test_local_worker_contracts import _invoke, _worker, _write_result


def test_native_audit_deduplicates_requests_and_outputs_without_exporting_bodies(tmp_path):
    payload = dict(thread_id='r', response_id='response', turn_id='turn',
        usage=dict(input_tokens=100, cached_input_tokens=80, output_tokens=5))
    events = [dict(type='session_meta', payload={'id':'r'}),
        dict(type='token_usage_record', payload=payload), dict(type='token_usage_record', payload=payload),
        dict(type='event_msg', payload=dict(type='token_count', info={'total_token_usage':payload['usage']})),
        dict(type='response_item', payload=dict(type='custom_tool_call', call_id='c', name='exec', input='private input')),
        dict(type='response_item', payload=dict(type='custom_tool_call_output', call_id='c',
            output=[{'type':'input_text', 'text':'私密'}]))]
    events.append(events[-1])
    path = tmp_path/'native.jsonl'
    path.write_text('\n'.join(json.dumps(event) for event in events))
    report = audit([dict(path=path, thread_id='r', role='root')])
    thread = report['threads'][0]
    assert thread['requests'] == 1 and thread['tokens'] == payload['usage']
    assert report['tool_result_bytes'] == len('私密'.encode())
    assert thread['text_bytes_by_outer_tool']['code_mode'] == report['tool_result_bytes']
    assert '私密' not in json.dumps(report, ensure_ascii=False)
    assert 'private input' not in json.dumps(report)
    with pytest.raises(ValueError, match='identity_mismatch'):
        audit([dict(path=path, thread_id='other', role='root')])
    with pytest.raises(ValueError, match='duplicate_native_thread'):
        audit([dict(path=path, thread_id='r', role='root')]*2)
    events.append(dict(type='token_usage_record', payload={**payload, 'usage':{**payload['usage'], 'input_tokens':101}}))
    path.write_text('\n'.join(json.dumps(event) for event in events))
    with pytest.raises(ValueError, match='response_conflict'):
        audit([dict(path=path, thread_id='r', role='root')])


def test_absent_tool_notifications_are_unknown_and_wire_bytes_are_not_model_bytes(tmp_path):
    report = usage_report(tmp_path, [], [])
    assert report['tool_result_bytes'] is None
    assert report['tool_output_observation']['coverage'] == 'missing'
    (tmp_path/'usage.json').write_text(json.dumps({'items':[{'type':'commandExecution', 'bytes':1000}]}))
    report = usage_report(tmp_path, [], [])
    assert report['tool_result_bytes'] is None
    assert report['tool_output_observation']['notification_bytes'] == 1000
    assert report['tool_output_observation']['coverage'] == 'partial'


def test_startup_reads_once_but_scientific_originals_keep_pagination(tmp_path):
    (tmp_path/'tools').mkdir()
    size = MaterialInputSettings().startup_read_page_bytes
    (tmp_path/'tools/input-reader-settings.json').write_text(json.dumps({'startup_page_bytes':size}))
    text = json.dumps({'instruction':'完整规则'*700, 'last_rule':'必须保留'}, ensure_ascii=False)
    (tmp_path/'worker-start.json').write_text(text)
    (tmp_path/'original.json').write_text(text)
    result = read(tmp_path, 'worker-start.json', file=True)
    assert result.endswith('[read_input: end]\n') and text in result
    assert len(result.encode()) < size
    assert read(tmp_path, action='repeat') == result
    original = read(tmp_path, 'original.json', file=True)
    assert len(original.encode()) <= 4096 and not original.endswith('[read_input: end]\n')
    with pytest.raises(ValueError, match='scientific-input limit'):
        read(tmp_path, 'original.json', file=True, budget=size)
    (tmp_path/'tools/input-reader-settings.json').write_text(json.dumps({'startup_page_bytes':1024}))
    parts = [read(tmp_path, 'worker-start.json', file=True, action='restart')]
    while not parts[-1].endswith('[read_input: end]\n'):
        parts.append(read(tmp_path, action='next'))
    assert all(len(part.encode()) <= 1024 for part in parts)
    assert ''.join(part.rsplit('\n[read_input: ', 1)[0] for part in parts) == text


def test_instance_summary_keeps_goal_and_recovery_navigation_not_historical_bodies():
    value = dict(name='instance', state='bound', scheduling=dict(state='paused', mode='background',
        reason='archive_restored', historical=True, objective_name='original-goal', can_schedule=False,
        budget={'observed_tokens':123, 'token_coverage':'partial'}, report={'summary':'science '*2000},
        closeout=dict(tasks=[{'name':'sealed', 'state':'completed', 'output_artifact_name':'sealed.output', 'selected_output':'science '*10000},
            {'name':'accepted', 'state':'running', 'output_artifact_name':'reserved-not-sealed.output'}],
            in_flight=[{'name':'accepted', 'state':'running', 'read':{'tool':'run_status', 'name':'accepted'}}],
            unresolved=[{'name':'unknown'}], omissions=[{'name':'hidden'}], accepted_tasks_terminal=False)))
    before = deepcopy(value)
    summary = root_response('instance_current', value, {'view':'summary'})
    detail = root_response('instance_current', value, {'view':'detail'})
    assert detail == before and value == before
    status = summary['scheduling']
    assert status['historical'] and not status['can_schedule']
    assert status['objective_read'] == {'tool':'artifact_catalog', 'name':'original-goal', 'view':'content'}
    assert status['handoff']['sealed_result_count'] == 1
    assert status['handoff']['in_flight'][0]['name'] == 'accepted'
    assert status['handoff']['unresolved_count'] == status['handoff']['omitted_count'] == 1
    assert status['handoff']['read'] == {'tool':'progression_status'}
    assert 'science ' not in json.dumps(summary)
    assert root_response('instance_current', {'state':'unbound', 'management_url':'exact'}, {}) == {
        'state':'unbound', 'management_url':'exact'}


def test_budget_projection_does_not_double_count_cache_or_enforce_estimated_task_cost():
    limits = ProgressionSettings().model_dump()
    records = {'worker':dict(role='worker', counted_tokens={'input_tokens':1800000,
        'cached_input_tokens':1700000, 'output_tokens':1000})}
    result = token_budget({'usage_records':records}, limits)
    assert result['remaining_tokens'] == 199000 and result['new_task_allowed']
    assert result['observed_worker_thread_tokens'] == 1801000
    assert result['closeout_reserve_tokens'] == 100000
    assert token_budget({'usage_records':records}, {**limits,'closeout_reserve_tokens':200000})['new_task_allowed'] is False
    assert token_budget({'usage_records':records}, {**limits,'closeout_reserve_tokens':0})['new_task_allowed']


def test_reserve_blocks_new_admission_but_keeps_sealing_and_final_report(progression):
    p = progression
    p.coordinator.tick()
    host = p.coordinator.host
    root = p.root.__class__(p.facade(host.scheduler_session))
    _invoke(root, 'accepted')
    worker = _worker(p.catalog, p.runtime)
    worker.call_tool('worker_open_assignment', {})
    host.event(dict(method='thread/tokenUsage/updated', params=dict(threadId='native-root',
        tokenUsage=dict(total=dict(inputTokens=1910000, cachedInputTokens=1800000, outputTokens=0)))))
    _write_result(worker)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    with pytest.raises(RootToolError, match='background_closeout_budget_reserved') as failure:
        _invoke(root, 'must-not-start')
    assert all(item['phase'] == 'input_admission' for item in failure.value.details)
    assert len(p.runtime.runs.list(instance_id=p.instance)) == 1
    assert len(checkpoint(p)['admissions']) == 1
    host.finish()
    p.now[0] += 6
    p.coordinator.tick()
    brief = json.loads(host.prompts[-1].split('\n')[-1])
    assert brief['budget']['new_task_allowed'] is False
    assert brief['budget']['remaining_tokens'] == 90000
    root.call_tool('progression_report', dict(summary='Sealed result supports the bounded goal.', completed=True))
    host.finish()
    p.coordinator.tick()
    assert row(p)['reason'] == 'goal_completed'


def test_no_additional_model_turn_after_total_budget_exhausted(progression):
    p = progression
    p.coordinator.tick()
    host = p.coordinator.host
    host.event(dict(method='thread/tokenUsage/updated', params=dict(threadId='native-root',
        tokenUsage=dict(total=dict(inputTokens=2000000, cachedInputTokens=1900000, outputTokens=0)))))
    host.finish()
    p.coordinator.tick()
    assert row(p)['reason'] == 'budget_exhausted'
    assert len(host.prompts) == 1
