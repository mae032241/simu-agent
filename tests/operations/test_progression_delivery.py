"""Durable pull notices and shared UI projections without models or solvers."""
import json
from copy import copy
from urllib.parse import parse_qs, urlparse

from scidiscovery.artifact_agent.approval_ui.read_model import InstanceReadModel
from scidiscovery.artifact_agent.approval_ui.workbench_render import render_workbench
from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService
from tests.operations.test_progression import progression, row
from tests.operations.test_instance_workbench_render import _overview
from tests.operations.test_instance_browser_http import _request
from tests.operations.test_m6a_direct_instance_management import _root, _setup


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
