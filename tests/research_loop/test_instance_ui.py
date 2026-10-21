"""Direct UI/control boundaries only; no HTTP, model or execution qualification."""
from datetime import datetime, timedelta, timezone
import html
import re
import threading
from urllib.parse import urlencode

import pytest

from scidiscovery.browser_access import access_cookie
from scidiscovery.research_loop import cli, controller, instance_control as control
from scidiscovery.research_loop.instance_ui import InstanceUI
from test_execution_authority import prepare
from test_history_handoff import finish


def session(root, key):
    ui = InstanceUI(root, secret_file=key); ui.host = '127.0.0.1:18753'
    _, _, headers = ui.get('/manage?' + urlencode({'token': ui.management_token}), host=ui.host)
    return ui, headers['Set-Cookie']


def form(ui, cookie, action):
    _, page, _ = ui.get('/', host=ui.host, cookie=cookie)
    original = re.search(r'<form method="post" action="/control/' + action + r'">(.*?)</form>',
                         page.decode(), re.S).group(1)
    return {html.unescape(key): html.unescape(value)
            for key, value in re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)">', original)}


def post(ui, cookie, action, value):
    return ui.post('/control/' + action, host=ui.host, origin='http://' + ui.host,
        cookie=cookie, content_type='application/x-www-form-urlencoded', body=urlencode(value).encode())


def test_ordinary_instance_status_pages_and_browser_bound_controls(tmp_path):
    root, key = prepare(tmp_path, enabled=False)
    finish(root, 1, 'H', [], action='analyze')
    finish(root, 2, 'A', [1])
    ui, cookie = session(root, key)
    full = cli.status(root)
    first = control.status(root, limit=1)
    second = control.status(root, after=first['next_after'], limit=1)
    fields = ('step', 'role', 'state')
    assert [tuple(node[key] for key in fields) for node in first['nodes']] == [(1, 'H', 'seal_present_unverified')]
    assert first['next_after'] == 1
    assert [tuple(node[key] for key in fields) for node in second['nodes']] == [(2, 'A', 'seal_present_unverified')]
    assert [{key: node[key] for key in fields} for node in first['nodes'] + second['nodes']] == [
        {key: node[key] for key in fields} for node in full['nodes']]
    assert second['next_after'] is None
    assert ui.get('/nodes/2', host=ui.host, cookie=cookie)[0] == 200
    with pytest.raises(ValueError, match='Exact instance node'):
        ui.get('/nodes/../../operator.key', host=ui.host, cookie=cookie)
    with pytest.raises(ValueError, match='unavailable'):
        ui.get('/requests', host=ui.host, cookie=cookie)
    _, _, read_headers = ui.get('/view?' + urlencode({'token': ui.read_token}), host=ui.host)
    read_cookie = read_headers['Set-Cookie']
    assert b'action="/control/' not in ui.get('/', host=ui.host, cookie=read_cookie)[1]
    value = form(ui, cookie, 'pause')
    with pytest.raises(PermissionError):
        post(ui, read_cookie, 'pause', value)
    with pytest.raises(PermissionError, match='Origin'):
        ui.post('/control/pause', host=ui.host, origin='http://other.invalid', cookie=cookie,
            content_type='application/x-www-form-urlencoded', body=urlencode(value).encode())
    with pytest.raises(PermissionError, match='CSRF'):
        post(ui, cookie, 'pause', dict(value, csrf='forged'))
    assert not (root / 'pause.request').exists()
    for token in (ui.browser.issue('other-instance', maintenance=True),
                  ui.browser.issue(ui.instance, maintenance=True,
                    now=datetime.now(timezone.utc) - timedelta(days=1), lifetime=timedelta(minutes=1))):
        with pytest.raises(PermissionError):
            ui.get('/', host=ui.host, cookie=access_cookie(ui.instance, token))
    restarted, _ = session(root, key)
    with pytest.raises(PermissionError):
        restarted.get('/', host=restarted.host, cookie=cookie)
    assert not (root / 'execution-authority/host-key.json').exists()


def test_final_results_follow_exact_sealed_terminal_route(tmp_path):
    root, key = prepare(tmp_path, enabled=False)
    finish(root, 1, 'H', [], action='analyze')
    ui, cookie = session(root, key)
    assert '最终综合结论尚未返回' in ui.get('/final-results', host=ui.host, cookie=cookie)[1].decode()
    finish(root, 2, 'A', [1], action='finish')
    assert ui._final_step() == 2
    page = ui.get('/final-results', host=ui.host, cookie=cookie)[1].decode()
    assert '研究发现' in page and '/nodes/2/science' in page
    overview = ui.get('/', host=ui.host, cookie=cookie)[1].decode()
    assert '已完成' in overview and 'href="/final-results" class="primary">查看结果</a>' in overview
    assert '第 1 轮 · A 决定结束探索' in overview


@pytest.mark.parametrize('active', [False, True])
@pytest.mark.parametrize('log_present', [False, True])
def test_progress_distinguishes_unconfirmed_runner_from_active_empty_log(tmp_path, active, log_present):
    import json
    import os
    from scidiscovery.research_loop import contracts as c, execution, runtime
    root, key = prepare(tmp_path, enabled=False)
    c.build_job(root, 1, 'H', [])
    record = execution.origin(root, 1); record.mkdir(parents=True, exist_ok=True)
    c.write(record / 'native-intent.json', dict(task_sha256=c.digest(root / 'jobs/001.json'), prepared_at=1.0))
    runner = runtime.process_identity(os.getpid(), c.digest(root / 'jobs/001.json'))
    if not active:
        runner['pid'] = 0  # No Linux /proc/0 identity can match this stopped runner.
    c.write(record / 'runner-process.json', runner)
    if log_present:
        (record / 'native.jsonl').write_bytes(b'')
    originals = {path: path.read_bytes() for path in (root / 'jobs/001.json',
        record / 'native-intent.json', record / 'runner-process.json')}
    ui, cookie = session(root, key)
    value = json.loads(ui.get('/nodes/1/events?attempt=0', host=ui.host, cookie=cookie)[1])
    page = ui.get('/nodes/1/progress?attempt=0', host=ui.host, cookie=cookie)[1].decode()
    assert value['state'] == ('running' if active else 'unknown')
    assert value['stream_state'] == ('ready' if log_present else 'missing')
    assert value['events'] == [] and value['progress_label'] in page
    if active:
        assert '正在运行' in value['progress_label']
        assert ('等待助手输出' in value['progress_label']) is (not log_present)
    else:
        assert '运行状态未确认' in value['progress_label'] and '核对原任务' in value['progress_label']
        assert '等待助手输出' not in page and '开始运行后会在这里更新' not in page
        hero = ui._dashboard_parts(ui._browser(cookie), ui._snapshot())['live-hero']
        assert 'action="/control/start"' not in hero
    assert {path: path.read_bytes() for path in originals} == originals
    assert not (record / 'native-outcome.json').exists()
    assert not (record / 'result-identity.json').exists()


@pytest.mark.parametrize('malformed', ['native-intent.json', 'usage.json'])
def test_progress_unavailable_observation_never_claims_prepared_or_running(tmp_path, malformed):
    import json
    import os
    from scidiscovery.research_loop import contracts as c, execution, runtime
    root, key = prepare(tmp_path, enabled=False)
    c.build_job(root, 1, 'H', [])
    record = execution.origin(root, 1)
    c.write(record / 'native-intent.json', dict(task_sha256=c.digest(root / 'jobs/001.json'), prepared_at=1.0))
    c.write(record / 'runner-process.json', runtime.process_identity(os.getpid(), c.digest(root / 'jobs/001.json')))
    ui, cookie = session(root, key)
    (record / malformed).write_bytes(b'{')
    value = json.loads(ui.get('/nodes/1/events?attempt=0', host=ui.host, cookie=cookie)[1])
    assert value['state'] == ('unstarted' if malformed == 'native-intent.json' else 'running')
    assert value['observation_state'] == 'unavailable' and value['stream_state'] == 'missing'
    assert '运行状态暂不可确认' in value['progress_label'] and '核对原任务' in value['progress_label']
    page = ui.get('/nodes/1/progress?attempt=0', host=ui.host, cookie=cookie)[1].decode()
    assert value['progress_label'] in page
    assert all(text not in value['progress_label'] for text in ('尚未开始', '正在运行', '等待助手输出'))
    assert (record / malformed).read_bytes() == b'{'


def test_dashboard_shows_controller_stop_receipt_without_private_reason(tmp_path):
    from scidiscovery.research_loop import contracts as c
    root, key = prepare(tmp_path, enabled=False)
    operation_id = 'd' * 32
    c.write(root / 'host-control/operations' / (operation_id + '.json'), dict(
        operation_id=operation_id, kind='controller', sequence=1, status='applied',
        result=dict(status='native_stopped', reason='private-stderr-path-and-token')))
    ui, cookie = session(root, key)
    page = ui.get('/', host=ui.host, cookie=cookie)[1].decode()
    assert '本次控制请求已停止推进：原生工作尚未封存阶段结论' in page
    assert '请核对原任务，勿重复提交' in page
    assert '本次控制请求已处理。' not in page and 'private-stderr-path-and-token' not in page


@pytest.mark.parametrize('reason, explanation', [
    ('Original execution lost its verified completion; preserved without replay',
     '原任务缺少可验证的完成记录；现有工作已保留，未重新执行。'),
    ('private-stderr-path-and-token', None),
])
def test_unsealed_controller_receipt_preserves_unknown_task_in_overview_and_live(tmp_path, reason, explanation):
    from scidiscovery.research_loop import contracts as c, execution
    root, key = prepare(tmp_path, enabled=False)
    c.build_job(root, 1, 'H', [])
    record = execution.origin(root, 1)
    c.write(record / 'native-intent.json', dict(task_sha256=c.digest(root / 'jobs/001.json'), prepared_at=1.0))
    operation_id = 'd' * 32
    c.write(root / 'host-control/operations' / (operation_id + '.json'), dict(
        operation_id=operation_id, kind='controller', sequence=1, status='applied',
        result=dict(status='native_outcome_unsealed', reason=reason)))
    originals = {path: path.read_bytes() for path in (root / 'jobs/001.json', record / 'native-intent.json',
        root / 'host-control/operations' / (operation_id + '.json'))}
    ui, cookie = session(root, key)
    page = ui.get('/', host=ui.host, cookie=cookie)[1].decode()
    overview_hero = re.search(r'<div id="live-hero">(.*?)<div id="live-usage">', page, re.S).group(1)
    hero = ui._live_snapshot(ui._browser(cookie), '', force=True)['fragments']['live-hero']
    for rendered in (overview_hero, hero):
        assert '本次控制请求已停止推进' in rendered and 'native_outcome_unsealed' in rendered
        assert '上次任务结果不确定' in rendered and '请核对原任务，勿重复提交' in rendered
        assert 'href="/progress" class="primary">查看原任务进度</a>' in rendered
        assert '本次控制请求已处理。' not in rendered and reason not in rendered
        assert '工作已结束' not in rendered
        if explanation:
            assert explanation in rendered
        else:
            assert '停止说明：' not in rendered
    assert reason not in page
    assert 'action="/control/start"' not in hero
    assert {path: path.read_bytes() for path in originals} == originals
    assert not (record / 'native-outcome.json').exists()
    assert not (record / 'result-identity.json').exists()


@pytest.mark.parametrize('result_status, text', [
    ('seal_pending', '阶段结论封存待修复'),
    ('output_repair_required', '原任务输出待修复'),
    ('output_repair_unavailable', '原任务输出暂无法修复'),
    ('waiting_execution', '本次控制请求已结束，正在等待原实验执行'),
])
def test_dashboard_explains_returned_controller_block_without_private_reason(tmp_path, result_status, text):
    from scidiscovery.research_loop import contracts as c
    root, key = prepare(tmp_path, enabled=False)
    operation_id = 'd' * 32
    c.write(root / 'host-control/operations' / (operation_id + '.json'), dict(
        operation_id=operation_id, kind='controller', sequence=1, status='applied',
        result=dict(status=result_status, reason='private-stderr-path-and-token')))
    ui, cookie = session(root, key)
    page = ui.get('/', host=ui.host, cookie=cookie)[1].decode()
    assert text in page and result_status in page
    assert '本次控制请求已处理。' not in page and 'private-stderr-path-and-token' not in page
    if result_status == 'waiting_execution':
        assert '本次控制请求已停止推进' not in page and '执行失败' not in page


@pytest.mark.parametrize('kind', ['controller', 'budget'])
def test_dashboard_preserves_ordinary_applied_notice(tmp_path, kind):
    from scidiscovery.research_loop import contracts as c
    root, key = prepare(tmp_path, enabled=False)
    operation_id = 'd' * 32
    c.write(root / 'host-control/operations' / (operation_id + '.json'), dict(
        operation_id=operation_id, kind=kind, sequence=1, status='applied', result=dict(status='finish')))
    ui, cookie = session(root, key)
    page = ui.get('/', host=ui.host, cookie=cookie)[1].decode()
    assert '本次控制请求已处理。' in page
    assert '本次控制请求已停止推进' not in page


def test_continue_delegates_to_detached_owner_and_pause_remains_immediate(tmp_path, monkeypatch):
    root, key = prepare(tmp_path, enabled=False)
    ui, cookie = session(root, key)
    owners = []

    def detached(instance, **options):
        owners.append((instance, options))
        return dict(operation_id='a' * 32, kind='controller', status='running')

    monkeypatch.setattr(control, 'start_background', detached)
    control.request_pause(root)
    assert post(ui, cookie, 'continue', form(ui, cookie, 'continue'))[0] == 303
    assert owners == [(root, dict(continue_run=True, ack_correction=None, authorization_note=None))]
    # The UI does not own a controller thread or clear its pause marker; the
    # detached shared control operation owns the actual transition.
    assert not hasattr(ui, 'control_thread')
    pause = form(ui, cookie, 'pause')
    assert post(ui, cookie, 'pause', pause)[0] == 303
    with pytest.raises(PermissionError, match='nonce'):
        post(ui, cookie, 'pause', pause)
    assert (root / 'pause.request').exists()


@pytest.mark.parametrize('ceiling,value,legacy_statement', [
    ('max_steps', '9', None), ('max_tokens', '5000', None),
    ('max_steps', '9', ''), ('max_steps', '9', '   \n'),
    ('max_steps', '9', '  Exact statement from an already open form.\n'),
])
def test_budget_form_queues_exact_limits_and_original_adjustment_text(tmp_path, ceiling, value, legacy_statement):
    from scidiscovery.research_loop import contracts as c
    root, key = prepare(tmp_path, enabled=False)
    ui, cookie = session(root, key)
    note = '  Raise this ceiling for the next bounded work.\n保留原文。\n'
    fields = dict(form(ui, cookie, 'budget'), max_tokens='', max_seconds='', max_steps='', authorization_note=note)
    fields[ceiling] = value
    if legacy_statement is not None:
        fields['authorization_statement'] = legacy_statement
    settings = (root / 'settings.json').read_bytes()
    # A current owner keeps the actual browser request queued at its boundary.
    with controller._writer(root):
        status, _, headers = post(ui, cookie, 'budget', fields)
        assert status == 303 and headers['Location'] == '/operations'
        operations = control.operations(root)
        assert len(operations) == 1 and operations[0]['status'] == 'accepted'
        amendment = operations[0]['amendment']
        assert amendment == dict(max_tokens=5000 if ceiling == 'max_tokens' else None,
            max_seconds=None, max_steps=9 if ceiling == 'max_steps' else None,
            authorization_note=note, authorization_statement=legacy_statement if legacy_statement and legacy_statement.strip() else (
                note if ceiling == 'max_steps' else None))
        assert c.read(root / 'host-control/operations' / (operations[0]['operation_id'] + '.json'))['amendment'] == amendment
    assert (root / 'settings.json').read_bytes() == settings
    assert not (root / 'execution-authority').exists()
    with pytest.raises(PermissionError, match='nonce'):
        post(ui, cookie, 'budget', fields)
    ui.translation.close()


@pytest.mark.parametrize('note', ['', '   \n'])
def test_budget_form_rejects_empty_explanation_and_keeps_one_retry_field(tmp_path, note):
    root, key = prepare(tmp_path, enabled=False)
    ui, cookie = session(root, key)
    fields = dict(form(ui, cookie, 'budget'), max_tokens='', max_seconds='', max_steps='9', authorization_note=note)
    status, page, _ = post(ui, cookie, 'budget', fields)
    assert status == 422 and not control.operations(root)
    retry = re.search(r'<form method="post" action="/control/budget">(.*?)</form>', page.decode(), re.S).group(1)
    assert retry.count('name="authorization_note"') == 1 and '调整说明' in retry
    assert 'name="authorization_statement"' not in retry and '确认调整预算' in retry
    assert '9' in retry and 'name="csrf"' in retry and 'name="nonce"' in retry
    ui.translation.close()


@pytest.mark.parametrize('extra', ['unknown=value', 'authorization_note=duplicate'])
def test_budget_form_rejects_unknown_or_duplicate_fields_before_queueing(tmp_path, extra):
    root, key = prepare(tmp_path, enabled=False)
    ui, cookie = session(root, key)
    fields = dict(form(ui, cookie, 'budget'), max_tokens='', max_seconds='', max_steps='9', authorization_note='Exact bounded adjustment.')
    with pytest.raises(ValueError, match='missing or duplicate fields'):
        ui.post('/control/budget', host=ui.host, origin='http://' + ui.host, cookie=cookie,
            content_type='application/x-www-form-urlencoded', body=(urlencode(fields) + '&' + extra).encode())
    assert not control.operations(root)
    ui.translation.close()


def test_read_cookie_opens_only_sealed_science_and_attachment_members(tmp_path,monkeypatch):
    from test_instance_science import read
    from scidiscovery.research_loop import instance_render as render
    from ui_html import element_texts
    root,key=prepare(tmp_path,enabled=False)
    finish(root,1,'H',[],action='analyze',files={'report.html':'<script>untrusted authored file</script>'})
    ui,_=session(root,key)
    _,_,headers=ui.get('/view?'+urlencode({'token':ui.read_token}),host=ui.host)
    cookie=headers['Set-Cookie']
    page=ui.get('/nodes/1',host=ui.host,cookie=cookie)[1]
    assert b'/nodes/1/science' in page and b'/nodes/1/materials' in page
    assert b'untrusted authored file' not in page
    def no_live_status(*args,**kwargs):
        pytest.fail('Original reading must not depend on live status/clock')
    monkeypatch.setattr(control,'status',no_live_status)
    status,body,headers=ui.get('/nodes/1/science',host=ui.host,cookie=cookie)
    assert status==200 and headers['Content-Type'].startswith('application/json')
    assert read(body)==(root/'native-evidence/001/science-output.json').read_bytes()
    page=ui.get('/nodes/1/materials',host=ui.host,cookie=cookie)[1]
    assert b'/nodes/1/materials/1' in page and b'untrusted authored file' not in page
    assert element_texts(page, 'script') == [render.translation_client.SCRIPT]
    _,body,headers=ui.get('/nodes/1/materials/1',host=ui.host,cookie=cookie)
    assert headers['Content-Disposition'].startswith('attachment;')
    assert read(body)==b'<script>untrusted authored file</script>'
    for target in ('/nodes/1/science?path=operator.key','/nodes/1/materials/../../operator.key',
                   '/nodes/1/materials/1?path=native-homes','/nodes/1/materials?after=0&after=1'):
        with pytest.raises(ValueError):ui.get(target,host=ui.host,cookie=cookie)
    with pytest.raises(PermissionError):ui.get('/nodes/1/science',host=ui.host)
    with pytest.raises(PermissionError):ui.get('/nodes/1/materials/1',host='other.invalid',cookie=cookie)


@pytest.mark.process_e2e
def test_loopback_science_download_uses_existing_browser_scope_and_safe_headers(tmp_path,monkeypatch):
    import http.client
    from scidiscovery.research_loop import instance_ui
    root,key=prepare(tmp_path,enabled=False)
    authored=b'<svg onload="never execute"/>'
    finish(root,1,'H',[],action='analyze',files={'figure.svg':authored.decode()})
    ui=InstanceUI(root,secret_file=key);ready=threading.Event();servers=[];errors=[]
    server_type=instance_ui.ThreadingHTTPServer
    class Server(server_type):
        def serve_forever(self,**options):
            servers.append(self);ready.set();super().serve_forever(**options)
    monkeypatch.setattr(instance_ui,'ThreadingHTTPServer',Server)
    monkeypatch.setattr(instance_ui,'InstanceUI',lambda *args,**options:ui)
    monkeypatch.setattr(instance_ui,'print',lambda *args,**options:None,raising=False)
    def serve():
        try:instance_ui.serve(root,secret_file=key)
        except BaseException as error:errors.append(error);ready.set()
    worker=threading.Thread(target=serve);worker.start();connection=None
    try:
        assert ready.wait(5) and not errors
        connection=http.client.HTTPConnection('127.0.0.1',servers[0].server_port,timeout=5)
        connection.request('GET','/nodes/1/science')
        response=connection.getresponse();assert response.status==403
        recovery=response.read()
        assert b'management_url' in recovery and b'?token=' not in recovery
        assert b'data-live-url' not in recovery and b'<script>' not in recovery
        connection.request('GET','/view?'+urlencode({'token':ui.read_token}))
        response=connection.getresponse();assert response.status==200
        cookie=response.getheader('Set-Cookie').split(';',1)[0];response.read()
        connection.request('GET','/results/1',headers={'Cookie':cookie})
        response=connection.getresponse()
        from scidiscovery.research_loop import instance_render
        assert response.status==200 and instance_render.STYLE_SOURCE in response.getheader('Content-Security-Policy')
        result_page=response.read()
        assert b'/nodes/1/science' in result_page and b'<details>' in result_page
        assert b'<svg' not in result_page and b'<script' not in result_page
        connection.request('GET','/nodes/1/materials/1',headers={'Cookie':cookie})
        response=connection.getresponse()
        assert response.status==200 and response.getheader('Content-Disposition').startswith('attachment;')
        assert response.getheader('Content-Type')=='application/octet-stream'
        assert response.getheader('X-Content-Type-Options')=='nosniff'
        assert "default-src 'none'" in response.getheader('Content-Security-Policy')
        assert response.read()==authored
    finally:
        if connection is not None:connection.close()
        if servers:servers[0].shutdown()
        worker.join(5)
    assert not worker.is_alive() and not errors


def test_management_configuration_guidance_and_explicit_instance_selection(tmp_path):
    from scidiscovery.research_loop import contracts as c
    from test_research_config import declaration
    root, key = prepare(tmp_path, enabled=False)
    ui, cookie = session(root, key)
    _, _, read_headers = ui.get('/view?' + urlencode({'token': ui.read_token}), host=ui.host)
    reader = read_headers['Set-Cookie']
    for path in ('/instances', '/configuration', '/operations'):
        with pytest.raises(PermissionError):
            ui.get(path, host=ui.host, cookie=reader)
    page = ui.get('/configuration', host=ui.host, cookie=cookie)[1]
    assert '此实例实际冻结的配置'.encode() in page and b'operator.key' not in page
    submit = dict(form(ui, cookie, 'pause'), text='Check uncertainty', target='W', kind='advice', scope='research', effective_step='')
    submit['csrf'] = ui._csrf(ui._browser(cookie), 'guidance-submit', submit['nonce'])
    assert post(ui, cookie, 'guidance-submit', submit)[2]['Location'] == '/guidance'
    assert b'Check uncertainty' in ui.get('/guidance', host=ui.host, cookie=reader)[1]
    config_dir = tmp_path / 'declarations'; config_dir.mkdir()
    config = declaration(config_dir)
    value = dict(form(ui, cookie, 'pause'), config_path=str(config), config_text='', mode='prepare')
    value['csrf'] = ui._csrf(ui._browser(cookie), 'configuration', value['nonce'])
    assert post(ui, cookie, 'configuration', value)[0] == 200
    created = config_dir / 'instance'
    assert c.settings(created)['objective'] == 'Compare alternatives and retain limitations.'
    listing = ui.get('/instances', host=ui.host, cookie=cookie)[1]
    assert str(created).encode() in listing and b'/instances/1/manage?token=' in listing
    child = ui._child(1)
    status, _, headers = ui.get('/instances/1/manage?' + urlencode({'token': child.management_token}), host=ui.host)
    assert status == 200 and 'Location' not in headers
    child_cookie = headers['Set-Cookie']
    page = ui.get('/instances/1/', host=ui.host, cookie=child_cookie)[1]
    assert b'action="/instances/1/control/start"' in page
    assert b'href="/instances"' in page
    with pytest.raises(PermissionError):
        ui.get('/instances/1/', host=ui.host, cookie=cookie)


@pytest.mark.process_e2e
def test_real_http_start_survives_disconnect_server_death_and_restart(tmp_path):
    import http.client
    import json
    import os
    from pathlib import Path
    import select
    import subprocess
    import sys
    import time
    from urllib.parse import urlsplit
    from scidiscovery.research_loop import control_operations

    root, key = prepare(tmp_path, enabled=False)
    # A bounded control-only stand-in: it neither invokes a model nor authors a
    # scientific result. The production HTTP/CLI/process ownership path is real.
    shim = tmp_path / 'shim'; shim.mkdir()
    (shim / 'sitecustomize.py').write_text('''
import time
from scidiscovery.research_loop import controller
def bounded_control(root):
    (root / 'entered').touch()
    deadline = time.monotonic() + 20
    while not (root / 'release').exists() and time.monotonic() < deadline:
        time.sleep(.02)
    return dict(status='wait', reason='HTTP lifetime fixture')
controller._run = bounded_control
''')
    source = Path(control_operations.__file__).resolve().parents[2]
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(shim), str(source)]))
    command = [sys.executable, '-m', 'scidiscovery.research_loop.cli', 'serve-ui', '--root', str(root), '--approval-secret-file', str(key)]
    hosts = []

    def start_host():
        process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        hosts.append(process)
        assert select.select([process.stdout], [], [], 8)[0]
        endpoint = json.loads(process.stdout.readline())
        url = urlsplit(endpoint['management_url'])
        connection = http.client.HTTPConnection(url.hostname, url.port, timeout=5)
        connection.request('GET', url.path + '?' + url.query)
        response = connection.getresponse(); response.read()
        assert response.status == 200
        cookie = response.getheader('Set-Cookie').split(';', 1)[0]
        return process, connection, url.netloc, cookie

    def get_form(connection, cookie):
        connection.request('GET', '/', headers={'Cookie': cookie})
        response = connection.getresponse(); page = response.read().decode()
        assert response.status == 200
        original = re.search(r'<form method="post" action="/control/start">(.*?)</form>', page, re.S).group(1)
        return {html.unescape(key): html.unescape(value) for key, value in
            re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)">', original)}

    connection = None
    try:
        first, connection, host, cookie = start_host()
        fields = get_form(connection, cookie)
        connection.request('POST', '/control/start', body=urlencode(fields), headers={
            'Cookie': cookie, 'Origin': 'http://' + host, 'Content-Type': 'application/x-www-form-urlencoded'})
        # Disconnect the browser without waiting for its control response.
        connection.close()
        deadline = time.monotonic() + 8
        while not (root / 'entered').exists() and time.monotonic() < deadline:
            time.sleep(.02)
        assert (root / 'entered').exists()
        receipt = control_operations.operations(root)[0]
        first.terminate(); first.wait(5)
        assert control_operations.operation(root, receipt['operation_id'])['status'] == 'running'
        second, connection, host, cookie = start_host()
        fields = get_form(connection, cookie)
        connection.request('POST', '/control/start', body=urlencode(fields), headers={
            'Cookie': cookie, 'Origin': 'http://' + host, 'Content-Type': 'application/x-www-form-urlencoded'})
        response = connection.getresponse(); response.read()
        assert response.status == 303
        assert [row['operation_id'] for row in control_operations.operations(root)] == [receipt['operation_id']]
        connection.request('GET', '/operations', headers={'Cookie': cookie})
        response = connection.getresponse()
        assert response.status == 200 and receipt['operation_id'].encode() in response.read()
        second.terminate(); second.wait(5)
        assert control_operations.operation(root, receipt['operation_id'])['status'] == 'running'
    finally:
        if connection is not None: connection.close()
        (root / 'release').touch()
        for process in hosts:
            if process.poll() is None: process.terminate(); process.wait(5)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            rows = control_operations.operations(root)
            if rows and rows[0]['status'] not in {'accepted', 'running'}: break
            time.sleep(.02)
    assert rows[0]['status'] == 'applied'
    assert not list(root.glob('**/result-identity.json'))


@pytest.mark.parametrize('backend', ['codex', 'protocol'])
def test_configuration_displays_requested_and_effective_permission_limits(tmp_path, backend):
    public = tmp_path / 'public'; public.mkdir()
    objective = public / 'objective.md'; objective.write_text('Explicit permission visibility fixture.')
    root = tmp_path / 'instance'
    controller.prepare(root, objective, public, ['codex'] if backend == 'codex' else ['operator-launcher'],
        native_backend=backend, native_options=dict(workspace='danger-full-access', network=False, web='disabled', subagents=False),
        max_tokens=100, max_seconds=10, max_steps=2, model='fixture', reasoning_effort=None, service_tier=None,
        experiment_mode='external', search_policy=None)
    key = tmp_path / 'operator.key'; key.write_bytes(b'fixture-key-for-browser-only-32bytes'); key.chmod(0o600)
    ui, cookie = session(root, key)
    page = html.unescape(ui.get('/configuration', host=ui.host, cookie=cookie)[1].decode())
    if backend == 'codex':
        assert 'The requested offline setting is not enforced' in page
        assert '"network": true' in page and '"network": false' in page
        assert '"response_schema_transport": "native_flag"' in page
    else:
        assert '"hint_only"' in page and '"network": "unknown"' in page
        assert '"response_schema_transport": "protocol_request"' in page
        assert '"session_resume": false' in page and '"complete_native_authorship": false' in page
    assert '"native_capabilities"' in page and '"session_resume"' in page
    assert 'operator.key' not in page and 'native_launcher_argv' not in page


@pytest.mark.process_e2e
def test_headless_browser_executes_public_progress_poll(tmp_path, monkeypatch):
    import json
    import os
    from pathlib import Path
    import shutil
    import subprocess
    import tempfile
    import time
    from scidiscovery.research_loop import instance_ui, contracts as c, execution, runtime, ui_mechanisms, ui_view, ui_translation
    chrome = shutil.which('google-chrome') or shutil.which('chromium')
    node = shutil.which('node')
    if not chrome or not node:
        pytest.skip('Optional local Chrome and Node smoke requires existing executables')
    from test_research_config import declaration
    workspace = tmp_path / 'workspace'; workspace.mkdir()
    config = declaration(workspace, '''
[agent.roles.W]
model = "imported-worker-model"
[agent.native.sandbox_workspace_write]
writable_roots = ["runs", "more/runs"]
network_access = false
[executor.config]
plugin = "fixture"
nested = { enabled = true, values = [1, "two", { exact = "retained" }] }
[permissions]
web = "cached"
network = false
''')
    config.write_text(config.read_text().replace('max_tokens = 1000\n', ''))
    root = workspace / 'instance'
    key = tmp_path / 'operator.key'; key.write_bytes(b'operator-key-for-browser-only---32'); key.chmod(0o600)
    record = execution.origin(root, 1)
    owners = []

    def detached(instance, **options):
        owners.append((instance, options))
        c.build_job(instance, 1, 'H', [])
        record.mkdir(exist_ok=True)
        (record / 'native.jsonl').write_text(json.dumps(dict(type='item.completed', item=dict(type='agent_message', text='Earlier browser fixture'))) + '\n')
        return dict(operation_id='a' * 32, kind='controller', status='accepted')

    # Browser-only fixture host updates: the signal files never reach a model
    # or solver, and scientific production instances are not used.
    original_snapshot = InstanceUI._snapshot
    advanced = set()
    advance = tmp_path / 'advance-live-ui'
    def fixture_snapshot(selected, **options):
        if selected.root == root and advance.exists():
            stage = advance.read_text()
            if stage not in advanced:
                advanced.add(stage)
                if stage == 'metered':
                    task_sha256 = c.digest(root / 'jobs/001.json')
                    c.write(record / 'native-intent.json', dict(task_sha256=task_sha256, prepared_at=1.0))
                    c.write(record / 'runner-process.json', runtime.process_identity(os.getpid(), task_sha256))
                elif stage == '2':
                    finish(root, 1, 'H', [], action='analyze', summary='First browser phase finding')
                    _, _, output = finish(root, 2, 'A', [1], summary='Second browser phase conclusion')
                    (output / 'native.jsonl').write_text(json.dumps(dict(type='item.completed', item=dict(type='agent_message', text='Second phase public output'))) + '\n')
                elif stage == '3':
                    _, _, output = finish(root, 3, 'H', [2], action='analyze', summary='Third browser phase conclusion')
                    (output / 'native.jsonl').write_text(json.dumps(dict(type='item.completed', item=dict(type='agent_message', text='Third phase public output'))) + '\n')
                elif stage == '4':
                    c.build_job(root, 4, 'W', [3])
                    output = execution.origin(root, 4)
                    c.write(output / 'native-intent.json', dict(task_sha256=c.digest(root / 'jobs/004.json'), prepared_at=1.0))
                    c.write(output / 'runner-process.json', runtime.process_identity(os.getpid(), c.digest(root / 'jobs/004.json')))
                elif stage == 'stopped':
                    output = execution.origin(root, 4)
                    runner = c.read(output / 'runner-process.json'); runner['pid'] = 0
                    c.write(output / 'runner-process.json', runner)
                    operation_id = 'd' * 32
                    c.write(root / 'host-control/operations' / (operation_id + '.json'), dict(
                        operation_id=operation_id, kind='controller', sequence=1, status='applied',
                        result=dict(status='native_stopped', last_step=3, reason='Private fixture diagnostic')))
        snapshot = original_snapshot(selected, **options)
        if selected.root == root and advance.exists() and advance.read_text() in {'3-refresh', '3-outside'}:
            # A display-only update exercises focus restoration without another
            # scientific stage or changing any sealed fixture original.
            import copy
            snapshot = copy.deepcopy(snapshot)
            snapshot['ui']['trail']['rounds'][0]['summary'] += ' · Browser heading update ' + advance.read_text()
        return snapshot
    monkeypatch.setattr(InstanceUI, '_snapshot', fixture_snapshot)
    original_candidates = ui_view.candidate_projection
    def fixture_candidates(selected, step, **options):
        projection = original_candidates(selected, step, **options)
        if selected == root:
            # Synthetic public observations exercise presentation only.
            projection.update(index=[dict(id=f'local-{number:02d}', label=f'Browser candidate {number}',
                metric=None if number == 3 else number / 10, evaluation_key='test' if number in (2, 24) else 'val',
                observation_step=1, status='failed' if number == 4 else 'ok') for number in range(1, 38)],
                nominated_ids=[f'local-{number:02d}' for number in range(1, 7)], graph={}, references={})
        return projection
    monkeypatch.setattr(ui_view, 'candidate_projection', fixture_candidates)
    original_card = ui_view.result_card
    def fixture_card(reader, step, **options):
        card = original_card(reader, step, **options)
        if reader.root == root:
            card.update(chosen=dict(id='local-37', label='Browser candidate 37', metric='3.7',
                evaluation_key='val', direction=None, step=1, reference=None),
                delivery_state='recommended', delivery_label='已推荐未交付')
        return card
    monkeypatch.setattr(ui_view, 'result_card', fixture_card)
    original_mechanisms = ui_mechanisms.project
    def fixture_mechanisms(reader, steps, clean, **options):
        value = original_mechanisms(reader, steps, clean, **options)
        if reader.root == root:
            # Synthetic public presentation records exercise long originals,
            # local table scrolling and replacement of this exact live slot.
            question = 'Does the measured response distinguish this mechanism under the declared conditions? ' + 'Original question detail. ' * 25
            reason = 'Await an independent observation before deciding. ' + 'Original disposition caveat. ' * 25
            refreshed = advance.exists() and advance.read_text() == 'mechanisms-refresh'
            items = []
            for index, label in enumerate(('Transport-driven response', 'Interface-state response'), 1):
                finding = ('Updated public observation. ' if refreshed and index == 1 else 'The observed response remains uncertain. ') + 'Original finding detail. ' * 25
                items.append(dict(ref=f'fixture.m{index}', label=label, question=question,
                    status='deferred', reason=reason, declared_in_window=True, events=[
                        dict(step=1, role='H', label=label, text=question),
                        dict(step=2, role='W', text=None, findings=[dict(basis='observed', text=finding)],
                            calls=None, sources=[1], metrics=[dict(key='Exact fixture validation protocol', ambiguous_label=False,
                                omitted=0, rows=[dict(label='Fixture candidate with a long original label', metric='0.125',
                                    direction='lower', status='recorded')])]),
                        dict(step=3, role='A', status='deferred', text=reason)]))
            value.update(mechanisms=items, unbound=[], unresolved=[], errors=[], omitted=0, partial=False)
        return value
    monkeypatch.setattr(ui_mechanisms, 'project', fixture_mechanisms)
    monkeypatch.setattr(control, 'start_background', detached)
    translation_permission = tmp_path / 'explicit-translation-click'
    translation_calls = []
    def fixture_translate(service, settings, texts):
        translation_calls.append((translation_permission.exists(), list(texts)))
        if 'Browser translation failure fixture' in texts:
            raise ui_translation._TranslationError('timeout')
        return ['<b>译文</b> ' + text for text in texts], None
    monkeypatch.setattr(ui_translation.TranslationService, '_translate', fixture_translate)
    ui = InstanceUI(workspace, secret_file=key, workspace=True); ready = threading.Event(); servers = []; errors = []
    ui.translation.configure(dict(enabled=True, model='fixture-reading-model', target_language='zh-CN'))
    server_type = instance_ui.ThreadingHTTPServer

    class Server(server_type):
        def serve_forever(self, **options):
            servers.append(self); ready.set(); super().serve_forever(**options)

    monkeypatch.setattr(instance_ui, 'ThreadingHTTPServer', Server)
    monkeypatch.setattr(instance_ui, 'InstanceUI', lambda selected, **options: ui if Path(selected) == workspace else InstanceUI(selected, **options))
    monkeypatch.setattr(instance_ui, 'print', lambda *args, **options: None, raising=False)

    def serve():
        try: instance_ui.serve(workspace, secret_file=key, workspace=True)
        except BaseException as error: errors.append(error); ready.set()

    # Chromium's wrapper and crash reporter use XDG directories even with an
    # explicit user-data-dir. Keep those writes inside a short test-owned /tmp
    # tree; the supervisor's long TMPDIR can also exceed Unix socket limits.
    browser_environment = tempfile.TemporaryDirectory(prefix='scid-browser-', dir='/tmp')
    browser_base = Path(browser_environment.name)
    browser_env = dict(os.environ)
    for key, name in (('XDG_CONFIG_HOME', 'config'), ('XDG_CACHE_HOME', 'cache'),
                      ('XDG_STATE_HOME', 'state'), ('XDG_DATA_HOME', 'data'),
                      ('XDG_RUNTIME_DIR', 'runtime'), ('TMPDIR', 'tmp')):
        directory = browser_base / name; directory.mkdir(mode=0o700)
        browser_env[key] = str(directory)
    log_dir = Path(os.environ.get('SCID_TEST_LOG_DIR', str(tmp_path)))
    log_dir.mkdir(parents=True, exist_ok=True)
    stderr_path = log_dir / 'headless-public-progress.stderr'
    browser_stderr = stderr_path.open('wb')
    thread = threading.Thread(target=serve); thread.start(); browser = None
    try:
        assert ready.wait(5) and not errors
        origin = 'http://' + ui.host
        profile = tmp_path / 'chrome-profile'
        browser = subprocess.Popen([chrome, '--headless', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
            '--disable-background-networking', '--disable-component-update', '--no-first-run', '--no-default-browser-check',
            '--renderer-process-limit=2', '--disable-features=BackForwardCache',
            '--remote-debugging-port=0', '--user-data-dir=' + str(profile), 'about:blank'],
            stdout=subprocess.DEVNULL, stderr=browser_stderr, env=browser_env, start_new_session=True)
        port_file = profile / 'DevToolsActivePort'
        deadline = time.monotonic() + 10
        while not port_file.exists() and time.monotonic() < deadline and browser.poll() is None:
            time.sleep(.05)
        if not port_file.exists():
            with stderr_path.open('rb') as diagnostic:
                diagnostic.seek(0, os.SEEK_END)
                diagnostic.seek(max(0, diagnostic.tell() - 4096))
                tail = diagnostic.read(4096).decode(errors='replace')
            pytest.fail('Chrome did not expose its local debugging endpoint; returncode='
                + str(browser.poll()) + '; stderr=' + str(stderr_path) + '\n' + tail)
        port = int(port_file.read_text().splitlines()[0])
        script = r'''
import {appendFile, writeFile} from 'node:fs/promises';
import {dirname, join} from 'node:path';
const [port, origin, transport] = process.argv.slice(1);
const managementToken = process.env.SCID_TEST_UI_MANAGEMENT_TOKEN;
const targets = await (await fetch('http://127.0.0.1:' + port + '/json/list')).json();
const ws = new WebSocket(targets.find(target => target.type === 'page').webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
let id = 0;
const pending = new Map();
ws.onmessage = event => { const message = JSON.parse(event.data); const waiter = pending.get(message.id); if (waiter) { pending.delete(message.id); message.error ? waiter.reject(message.error) : waiter.resolve(message.result); } };
function call(method, params = {}) { return new Promise((resolve, reject) => { const next = ++id; pending.set(next, {resolve, reject}); ws.send(JSON.stringify({id: next, method, params})); }); }
await call('Network.enable');
await call('Emulation.setDeviceMetricsOverride', {width:1280,height:900,deviceScaleFactor:1,mobile:false});
async function evaluate(expression) {
  const answer = await call('Runtime.evaluate', {expression, returnByValue: true});
  if (answer.exceptionDetails) throw new Error('Browser expression failed: ' + (answer.exceptionDetails.exception?.description || answer.exceptionDetails.text));
  return answer.result.value;
}
async function waitFor(expression) {
  for (let index = 0; index < 60; index++) { await new Promise(resolve => setTimeout(resolve, 100)); if (await evaluate(expression)) return; }
  const diagnostic = await evaluate('JSON.stringify({path:location.pathname, text:document.body?.innerText?.slice(0,4000)})');
  throw new Error('Browser journey did not reach expected state: ' + expression + '\nPage: ' + diagnostic);
}
async function screenshot(name) {
  if (!process.env.SCID_TEST_LOG_DIR) return;
  const size = (await call('Page.getLayoutMetrics')).cssContentSize;
  const shot = await call('Page.captureScreenshot', {format:'png',captureBeyondViewport:true,clip:{x:0,y:0,width:size.width,height:size.height,scale:1}});
  await writeFile(join(process.env.SCID_TEST_LOG_DIR, name+'.png'), Buffer.from(shot.data,'base64'));
}
async function noOverflow() {
  if (await evaluate('document.documentElement.scrollWidth > innerWidth + 1')) throw new Error('Setup page overflows viewport');
}
await call('Page.navigate', {url: origin + '/manage?token=' + encodeURIComponent(managementToken)});
await waitFor('document.body.innerText.includes("研究工作台")');
await screenshot('setup-workspace');
await evaluate(`document.querySelector('a[href="/new"]').click(); true`);
await waitFor('document.querySelector("textarea[name=task_text]") !== null && document.querySelector("[aria-current=step]") !== null');
if (await evaluate(`document.querySelector('[name="cfg.budget.max_tokens"]').value`) !== '') throw new Error('Missing budget was silently supplied');
if (await evaluate(`document.querySelector('[name="task_text"]').value`) !== '') throw new Error('Workspace task was silently supplied');
if (await evaluate(`document.body.innerText.includes('budget.max_tokens') || document.body.innerText.includes('research.public_root')`)) throw new Error('Ordinary initial screen exposes declaration keys');
// A real missing-file response keeps the chosen path visible and its form usable.
const missingConfig = process.env.SCID_TEST_CONFIG_PATH + '.missing.toml';
await evaluate(`document.querySelector('.setup-tools').open=true;document.querySelector('[name="config_path"]').value=${JSON.stringify(missingConfig)};document.querySelector('form[action="/control/load-config"] button').click();true`);
await waitFor(`document.querySelector('h1')?.textContent==='配置文件不存在' && document.querySelector('.setup-tools').open`);
if (await evaluate(`document.querySelector('[name="config_path"]').value`) !== missingConfig) throw new Error('Missing-config failure lost chosen path');
await screenshot('setup-error-missing-config-desktop');
await call('Emulation.setDeviceMetricsOverride',{width:375,height:812,deviceScaleFactor:1,mobile:true});
await noOverflow(); await screenshot('setup-error-missing-config-mobile');
await call('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false});
// Import a nested declaration, then traverse both steps without changing any control.
await evaluate(`document.querySelector('.setup-tools').open=true;document.querySelector('[name="config_path"]').value=${JSON.stringify(process.env.SCID_TEST_CONFIG_PATH)};document.querySelector('form[action="/control/load-config"] button').click();true`);
await waitFor(`document.querySelector('.import-notice') !== null && document.querySelector('[aria-current=step]')?.dataset.setupMarker === '1'`);
const imported = await evaluate(`JSON.stringify(Array.from(new FormData(document.getElementById('research-config-form'))).filter(([name])=>!['nonce','csrf','selection'].includes(name)))`);
await evaluate(`document.querySelector('[data-setup-go="2"]').click();true`);
await waitFor(`document.querySelector('[aria-current=step]')?.dataset.setupMarker === '2'`);
await evaluate(`document.querySelector('[data-setup-go="1"]').click();true`);
const returned = await evaluate(`JSON.stringify(Array.from(new FormData(document.getElementById('research-config-form'))).filter(([name])=>!['nonce','csrf','selection'].includes(name)))`);
if (imported !== returned || !returned.includes('imported-worker-model') || !returned.includes('retained')) throw new Error('Imported nested controls changed across steps');
// Begin a new draft from this authenticated page so Strict cookies retain a same-site initiator.
await evaluate(`location.assign('/new');true`);
await waitFor(`document.querySelector('[name="task_text"]')?.value === '' && document.querySelector('[aria-current=step]')?.dataset.setupMarker === '1'`);
// An incomplete text attempt must not leave an invalid hidden control when switching to a file.
await evaluate(`document.querySelector('[data-setup-go="2"]').click();document.querySelector('[name="task_mode"]').value='file';document.querySelector('[name="task_mode"]').dispatchEvent(new Event('change',{bubbles:true}));
document.querySelector('[name="cfg.research.objective"]').value=${JSON.stringify(process.env.SCID_TEST_PUBLIC_ROOT+'/objective.md')};
document.querySelector('[name="cfg.research.root"]').value=${JSON.stringify(process.env.SCID_TEST_INSTANCE_ROOT)};
document.querySelector('[name="cfg.research.public_root"]').value=${JSON.stringify(process.env.SCID_TEST_PUBLIC_ROOT)};
document.querySelector('[data-setup-go="2"]').click();true`);
await waitFor(`document.querySelector('[aria-current=step]')?.dataset.setupMarker === '2'`);
if (!(await evaluate(`document.getElementById('research-config-form').checkValidity()`))) throw new Error('Inactive task input blocks submission');
await evaluate(`document.querySelector('[data-setup-go="1"]').click();document.querySelector('[name="task_mode"]').value='text';document.querySelector('[name="task_mode"]').dispatchEvent(new Event('change',{bubbles:true}));document.querySelector('[name="task_text"]').value='Browser direct-form research task.';document.querySelector('[name="task_text"]').dispatchEvent(new Event('input',{bubbles:true}));true`);
if (await evaluate(`document.getElementById('config-edited-note') !== null`)) throw new Error('Fresh draft input shows a stale-preview warning');
await screenshot('setup-task-desktop');
await call('Emulation.setDeviceMetricsOverride',{width:375,height:812,deviceScaleFactor:1,mobile:true});
await noOverflow(); await screenshot('setup-task-mobile');
await evaluate(`document.querySelector('[data-setup-go="2"]').click();true`);
await noOverflow();
await evaluate(`document.querySelector('[name="cfg.agent.model"]').value='browser-fixture-model';document.querySelector('[name="cfg.budget.max_tokens"]').value='not-a-number';document.querySelector('[name="cfg.budget.max_seconds"]').value='120';document.querySelector('[name="cfg.budget.max_steps"]').value='8';true`);
await screenshot('setup-budget-mobile');
await call('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false});
await evaluate(`document.querySelector('[data-setup-go="1"]').click();true`);
if (await evaluate(`document.querySelector('[name="task_text"]').value`) !== 'Browser direct-form research task.') throw new Error('Back lost task');
await evaluate(`document.querySelector('[data-setup-go="2"]').click();document.querySelector('form[action="/control/configure"] button[value="preview"]').click();true`);
await waitFor(`document.querySelector('.setup-notice') !== null && document.querySelector('[aria-current=step]')?.dataset.setupMarker === '2'`);
if (await evaluate(`document.querySelector('[name="cfg.budget.max_tokens"]').value`) !== 'not-a-number') throw new Error('Validation lost invalid input');
if (await evaluate(`document.querySelector('[name="cfg.agent.model"]').value`) !== 'browser-fixture-model') throw new Error('Validation lost model');
await screenshot('setup-error-budget-desktop');
await evaluate(`document.querySelector('[name="cfg.budget.max_tokens"]').value='1234';true`);
await screenshot('setup-budget-desktop');
await evaluate(`document.querySelector('form[action="/control/configure"] button[value="preview"]').click();true`);
await waitFor(`document.querySelector('form[action="/control/create"]') !== null && document.querySelector('[aria-current=step]')?.dataset.setupMarker === '3'`);
if (!(await evaluate('document.body.innerText')).includes('Browser direct-form research task.')) throw new Error('Edited task missing from preview');
if (!(await evaluate(`Array.from(document.querySelectorAll('.review-full-path code')).some(path=>path.textContent===${JSON.stringify(process.env.SCID_TEST_INSTANCE_ROOT)}) && Array.from(document.querySelectorAll('.review-full-path code')).some(path=>path.textContent===${JSON.stringify(process.env.SCID_TEST_PUBLIC_ROOT)})`))) throw new Error('Confirmation lost full path identities');
if (await evaluate(`document.querySelector('.review-summary').innerText.includes(${JSON.stringify(process.env.SCID_TEST_INSTANCE_ROOT)})`)) throw new Error('Long absolute path dominates collapsed confirmation');
await evaluate(`document.querySelector('.review-full-path').open=true;true`);
await noOverflow();
await evaluate(`document.querySelector('.review-full-path').open=false;true`);
await screenshot('setup-confirm-desktop');
await call('Emulation.setDeviceMetricsOverride',{width:375,height:812,deviceScaleFactor:1,mobile:true});
await noOverflow(); await screenshot('setup-confirm-mobile');
await call('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false});
// Editing after a preview must invalidate Create; a fresh server check restores it.
await evaluate(`document.querySelector('.confirmation [data-setup-go="2"]').click();document.querySelector('[name="cfg.agent.model"]').value='browser-corrected-model';document.querySelector('[name="cfg.agent.model"]').dispatchEvent(new Event('input',{bubbles:true}));true`);
if (!(await evaluate(`document.querySelector('form[action="/control/create"] button').disabled`))) throw new Error('Edited config can still create from stale preview');
await evaluate(`document.querySelector('form[action="/control/configure"] button[value="preview"]').click();true`);
await waitFor(`document.querySelector('[aria-current=step]')?.dataset.setupMarker === '3' && !document.querySelector('form[action="/control/create"] button').disabled && document.querySelector('.confirmation').innerText.includes('browser-corrected-model')`);
await evaluate(`document.querySelector('form[action="/control/create"] button').click(); true`);
await waitFor('location.pathname === "/instances/1/" && document.getElementById("live-hero")?.innerText.includes("未开始") && document.querySelector(\'form[action="/instances/1/control/start"]\') !== null');
if (!(await evaluate(`document.querySelector('h1').textContent.includes('Browser direct-form research task.') && document.getElementById('live-usage').innerText.includes('1,234')`))) throw new Error('Created overview lost the selected task or budget');
await call('Page.navigate', {url:origin+'/instances/1/progress'});
await waitFor(`document.querySelector('[data-stream-status]')?.textContent.includes('尚无研究阶段') && document.querySelector('[data-token-scope]')?.textContent==='当前阶段 · 等待助手用量'`);
if (!(await evaluate(`document.querySelectorAll('[data-token-details] dt').length===0`))) throw new Error('Empty research shows stale token readings');
await call('Page.navigate', {url:origin+'/instances/1/'});
await waitFor(`document.querySelector('form[action="/instances/1/control/start"] button') !== null`);
await evaluate(`document.querySelector('form[action="/instances/1/control/start"] button').click(); true`);
await waitFor('document.body.innerText.includes("已接受请求")');
await call('Page.navigate', {url: origin + '/instances/1/nodes/1/progress?attempt=0'});
let observed = '';
for (let index = 0; index < 60; index++) {
  await new Promise(resolve => setTimeout(resolve, 100));
  const answer = await call('Runtime.evaluate', {expression: 'document.querySelector("[data-stream-status]")?.textContent || ""', returnByValue: true});
  observed = answer.result.value;
  if (observed.includes('已连接')) break;
}
if (!observed.includes('已连接')) throw new Error('Public progress JavaScript did not poll: ' + observed);
if (!observed.includes('阶段已准备，尚未开始')) throw new Error('Prepared phase lifecycle missing: ' + observed);
if (!(await evaluate(`document.querySelector('[data-token-details]').textContent.includes('缓存命中率') && document.querySelector('[data-token-details]').textContent.includes('不可用')`))) throw new Error('Missing token telemetry was not shown explicitly');
if (!(await evaluate(`(()=>{const card=document.querySelector('section.token-monitor'),log=document.querySelector('[data-progress]');return card && !card.closest('.stat') && !card.closest('[data-progress]') && card.parentElement===log.parentElement && Boolean(log.compareDocumentPosition(card)&Node.DOCUMENT_POSITION_FOLLOWING)})()`))) throw new Error('Token monitor must follow the primary public work log as an independent sibling card');
await appendFile(transport, JSON.stringify({type: 'item.completed', item: {type: 'agent_message', text: 'Public browser fixture'}}) + '\n');
let rendered = '';
for (let index = 0; index < 60; index++) {
  await new Promise(resolve => setTimeout(resolve, 100));
  const answer = await call('Runtime.evaluate', {expression: 'document.querySelector("[data-events]")?.textContent || ""', returnByValue: true});
  rendered = answer.result.value;
  if (rendered.includes('Public browser fixture')) break;
}
if (!rendered.includes('Public browser fixture')) throw new Error('Initial fixed output missing');
// The metered attempt has actually started, so aggregate accounting includes it.
await writeFile(process.env.SCID_TEST_ADVANCE, 'metered');
await writeFile(join(dirname(transport), 'usage.json'), JSON.stringify({input_tokens:30,cached_input_tokens:20,output_tokens:2}));
await writeFile(join(dirname(transport), 'usage-observation.json'), JSON.stringify({coverage:'live',context:{status:'last_reported',total_tokens:8,model_context_window:100}}));
await waitFor(`(()=>{const rows=Object.fromEntries(Array.from(document.querySelectorAll('[data-token-details] dt'),label=>[label.textContent,label.nextElementSibling.textContent]));return rows['输入']==='30' && rows['缓存输入']==='20' && rows['非缓存输入']==='10' && rows['输出']==='2' && rows['缓存命中率']==='66.7%' && rows['最近一次上报上下文（阶段 1 / attempt 0）']?.startsWith('8 / 100 · 8.0%')})()`);
await evaluate(`window.tokenPollSentinel='preserved';true`);
await writeFile(join(dirname(transport), 'usage.json'), JSON.stringify({input_tokens:100,cached_input_tokens:80,output_tokens:5}));
await writeFile(join(dirname(transport), 'usage-observation.json'), JSON.stringify({coverage:'live',context:{status:'last_reported',total_tokens:64,model_context_window:128}}));
await waitFor(`(()=>{const rows=Object.fromEntries(Array.from(document.querySelectorAll('[data-token-details] dt'),label=>[label.textContent,label.nextElementSibling.textContent]));return rows['输入']==='100' && rows['缓存输入']==='80' && rows['非缓存输入']==='20' && rows['输出']==='5' && rows['缓存命中率']==='80.0%' && rows['最近一次上报上下文（阶段 1 / attempt 0）']?.startsWith('64 / 128 · 50.0%')})()`);
if (!(await evaluate(`window.tokenPollSentinel==='preserved' && document.querySelector('[data-events]').textContent.includes('Public browser fixture')`))) throw new Error('Token updates reloaded the page or lost public output');
await noOverflow(); await screenshot('token-monitor-progress-desktop');
await call('Emulation.setDeviceMetricsOverride', {width:390,height:844,deviceScaleFactor:1,mobile:true});
await noOverflow(); await screenshot('token-monitor-progress-mobile');
await call('Emulation.setDeviceMetricsOverride', {width:1440,height:1000,deviceScaleFactor:1,mobile:false});
await call('Page.navigate', {url:origin+'/instances/1/'});
await waitFor(`document.querySelector('.token-monitor')?.innerText.includes('80.0%')`);
if (!(await evaluate(`(()=>{const ids=['live-hero','live-usage','live-activity','live-trail','live-token-monitor'];return document.querySelectorAll('.stats > .stat').length===4 && ids.every((id,index)=>!index || document.getElementById(ids[index-1]).nextElementSibling===document.getElementById(id)) && document.querySelector('#live-token-monitor > .token-monitor') && !document.querySelector('#live-usage [data-token-details]')})()`))) throw new Error('Overview token monitor must follow the primary research content');
await noOverflow(); await screenshot('token-monitor-overview-desktop');
await call('Emulation.setDeviceMetricsOverride', {width:390,height:844,deviceScaleFactor:1,mobile:true});
await noOverflow(); await screenshot('token-monitor-overview-mobile');
await call('Emulation.setDeviceMetricsOverride', {width:1440,height:1000,deviceScaleFactor:1,mobile:false});
await call('Page.navigate', {url:origin+'/instances/1/nodes/1/progress?attempt=0'});
await waitFor(`document.querySelector('[data-events]')?.textContent.includes('Public browser fixture') && document.querySelector('[data-token-details]')?.textContent.includes('80.0%')`);
// A permanent progress authorization failure explains recovery and never polls again.
await evaluate(`(()=>{window.progressDeniedCalls=0;const originalFetch=window.fetch;window.fetch=(url,options)=>{if(String(url).includes('/nodes/1/events')){window.progressDeniedCalls++;return Promise.resolve(new Response(JSON.stringify({error:{code:'browser_session_invalid',title:'浏览会话已失效',cause:'进度会话已过期。',hint:'请使用本次 management_url 重新打开。',reference:'progress-fixture-ref'}}),{status:403,headers:{'Content-Type':'application/json'}}))}return originalFetch(url,options)};return true})()`);
await waitFor(`document.querySelector('[data-stream-status]')?.textContent.includes('management_url') && document.querySelector('[data-stream-status]').textContent.includes('progress-fixture-ref')`);
await new Promise(resolve=>setTimeout(resolve,2300));
if (!(await evaluate(`window.progressDeniedCalls===1 && document.querySelector('[data-events]').textContent.includes('Public browser fixture')`))) throw new Error('Expired progress kept polling or lost rendered output');
await screenshot('reading-error-progress-session-expired');
await call('Page.navigate', {url:origin+'/instances/1/progress'});
await waitFor(`document.querySelector('[data-progress-heading]')?.textContent.includes('第 1 阶段') && document.querySelector('[data-events]')?.textContent.includes('Public browser fixture')`);
await writeFile(process.env.SCID_TEST_ADVANCE, '2');
await waitFor(`document.querySelector('[data-progress-heading]')?.textContent.includes('第 2 阶段') && document.querySelector('[data-events]')?.textContent.includes('Second phase public output')`);
if (!(await evaluate(`document.querySelector('[data-token-monitor] [data-token-scope]').textContent.includes('第 2 阶段 · attempt 0') && !document.querySelector('[data-progress] [data-token-details]')`))) throw new Error('Separate token card did not follow the latest phase');
if ((await evaluate('location.pathname')) !== '/instances/1/progress') throw new Error('Following output navigated away');
await screenshot('live-follow-current-node');
await call('Page.navigate', {url:origin+'/instances/1/nodes/1/progress?attempt=0'});
await waitFor(`document.querySelector('[data-events]')?.textContent.includes('Public browser fixture')`);
await waitFor(`document.querySelector('[data-stream-status]')?.textContent.includes('已有阶段结论')`);
if ((await evaluate(`document.querySelector('[data-events]').textContent`)).includes('Second phase public output')) throw new Error('Historical output followed a newer node');
await call('Page.navigate', {url:origin+'/instances/1/'});
await waitFor(`document.getElementById('live-hero')?.innerText.includes('第 2 阶段') && document.querySelector('[data-live-url]')?.dataset.state==='connected'`);
if (await evaluate(`document.querySelector('details.budget-adjustment').open`)) throw new Error('Budget adjustment did not begin collapsed');
await evaluate(`document.querySelector('details.more-actions > summary').click();true`);
if (await evaluate(`document.querySelector('details.budget-adjustment').open`)) throw new Error('Opening more actions expanded the budget form');
await evaluate(`document.querySelector('details.budget-adjustment > summary').click();true`);
if (!(await evaluate(`document.querySelector('details.budget-adjustment').open && document.querySelector('#budget [name="max_tokens"]').getClientRects().length>0`))) throw new Error('Budget summary did not reveal its form');
if (!(await evaluate(`document.querySelectorAll('#budget textarea').length===1 && document.querySelector('#budget [name="authorization_note"]').closest('label').innerText.includes('调整说明') && !document.querySelector('#budget [name="authorization_statement"]') && document.querySelector('#budget button').textContent==='确认调整预算'`))) throw new Error('Budget form must use one adjustment explanation and explicit submit confirmation');
await evaluate(`document.querySelector('details.budget-adjustment').open=false;document.querySelector('details.more-actions').open=false;true`);
await call('Page.navigate', {url:origin+'/instances/1/#budget'});
await waitFor(`document.querySelector('details.more-actions').open && document.querySelector('details.budget-adjustment').open && document.querySelector('#budget [name="max_tokens"]').getClientRects().length>0`);
await evaluate(`(()=>{document.querySelector('details.budget-adjustment').open=false;document.querySelector('details.more-actions').open=false;const jump=document.createElement('a');jump.href='#budget';jump.textContent='Budget fragment fixture';document.body.append(jump);jump.click();jump.remove();return true})()`);
await waitFor(`document.querySelector('details.more-actions').open && document.querySelector('details.budget-adjustment').open && document.querySelector('#budget [name="max_tokens"]').getClientRects().length>0`);
await evaluate(`(()=>{window.liveDraftSentinel='preserved';document.querySelector('form[action="/instances/1/control/budget"] [name="max_tokens"]').value='4321';document.querySelector('form[action="/instances/1/control/budget"] [name="authorization_note"]').value='Keep this unsent budget explanation';const round=document.querySelector('#live-trail details[data-round]');window.retainedRound=round.dataset.detailsKey;round.open=false;round.querySelector('summary').focus();return true})()`);
await writeFile(process.env.SCID_TEST_ADVANCE, '3');
await waitFor(`document.getElementById('live-hero')?.innerText.includes('第 3 阶段') && document.getElementById('live-usage')?.innerText.includes('30 / 1,234') && document.getElementById('live-trail')?.innerText.includes('Third browser phase conclusion')`);
if (!(await evaluate(`window.liveDraftSentinel==='preserved' && document.querySelector('form[action="/instances/1/control/budget"] [name="max_tokens"]').value==='4321' && document.querySelector('form[action="/instances/1/control/budget"] [name="authorization_note"]').value==='Keep this unsent budget explanation'`))) throw new Error('Live dashboard lost typed values or reloaded');
if (!(await evaluate(`Array.from(document.querySelectorAll('#live-trail details[data-details-key]')).some(round=>round.dataset.detailsKey===window.retainedRound && !round.open && document.activeElement===round.querySelector('summary'))`))) throw new Error('Live trail lost the reader\'s collapsed round or keyboard summary focus');
await screenshot('live-dashboard-draft-preserved');
await evaluate(`(()=>{const round=Array.from(document.querySelectorAll('#live-trail details[data-details-key]')).find(round=>round.dataset.detailsKey===window.retainedRound);round.open=true;const link=round.querySelector('a');window.retainedLink=link.dataset.liveFocus;link.focus();return true})()`);
await writeFile(process.env.SCID_TEST_ADVANCE, '3-refresh');
await waitFor(`document.getElementById('live-trail')?.innerText.includes('Browser heading update')`);
if (!(await evaluate(`document.activeElement?.dataset.liveFocus===window.retainedLink && document.activeElement.isConnected`))) throw new Error('Live trail lost keyboard focus on the same stage link');
await evaluate(`document.querySelector('form[action="/instances/1/control/budget"] [name="authorization_note"]').focus();true`);
await writeFile(process.env.SCID_TEST_ADVANCE, '3-outside');
await waitFor(`document.getElementById('live-trail')?.innerText.includes('Browser heading update 3-outside')`);
if (!(await evaluate(`document.activeElement===document.querySelector('form[action="/instances/1/control/budget"] [name="authorization_note"]')`))) throw new Error('Live trail stole keyboard focus from another form');
await call('Page.navigate', {url:origin+'/'});
await waitFor(`document.getElementById('live-instances')?.innerText.includes('第 3 阶段') && document.getElementById('live-instances')?.innerText.includes('30 / 1,234 tokens')`);
await screenshot('live-workbench-loaded-status');
await evaluate(`(()=>{const details=document.querySelector('#live-instances details.review-full-path');details.open=true;window.retainedPath=details.dataset.detailsKey;details.querySelector('summary').focus();return true})()`);
await writeFile(process.env.SCID_TEST_ADVANCE, '4');
await waitFor(`document.getElementById('live-instances')?.innerText.includes('第 4 阶段')`);
if (!(await evaluate(`Array.from(document.querySelectorAll('#live-instances details[data-details-key]')).some(details=>details.dataset.detailsKey===window.retainedPath && details.open && document.activeElement===details.querySelector('summary'))`))) throw new Error('Live workbench lost the expanded exact instance path or summary focus');
await screenshot('live-workbench-path-preserved');
await call('Page.navigate', {url:origin+'/instances/1/results/2'});
await waitFor(`document.querySelector('.result-card') !== null && document.querySelector('.candidates-fold') !== null`);
await evaluate(`document.querySelector('.candidates-fold').open=true;true`);
const initialGroups = await evaluate(`Array.from(document.querySelectorAll('.candidate-group')).map(group=>Array.from(group.querySelectorAll('tbody tr')).map(row=>row.dataset.order))`);
if (initialGroups.length !== 2 || initialGroups.flat().length !== 7) throw new Error('Candidate table did not restrict 37 historical candidates to six nominees and the A choice');
if (!(await evaluate(`document.querySelector('.candidates h2').textContent.includes('（7）') && !document.querySelector('.candidates .toggle-all') && Array.from(document.querySelectorAll('.candidate-table .cand-label')).every(label=>['1','2','3','4','5','6','37'].some(number=>label.textContent==='Browser candidate '+number)) && document.querySelector('.candidate-table .mark-recommended').closest('tr').textContent.includes('Browser candidate 37')`))) throw new Error('Candidate comparison leaked historical alternatives or lost the explicit A choice');
for (const direction of ['desc','asc','order']) {
  await evaluate(`document.querySelector('[data-sort-group]').click();true`);
  const state = await evaluate(`(()=>{const groups=Array.from(document.querySelectorAll('.candidate-group'));const group=groups[0];return {order:groups.map(item=>Array.from(item.querySelectorAll('tbody tr')).map(row=>row.dataset.order)),metrics:Array.from(group.querySelectorAll('tbody tr')).map(row=>row.dataset.metric===''?null:Number(row.dataset.metric)),state:group.querySelector('[data-sort-group]').dataset.state,neutral:group.querySelector('[data-sort-note]').hidden}})()`);
  if (state.state !== direction || JSON.stringify(state.order[1]) !== JSON.stringify(initialGroups[1])) throw new Error('Candidate sort crossed evaluation groups');
  if (direction === 'order') {
    if (JSON.stringify(state.order) !== JSON.stringify(initialGroups) || !state.neutral) throw new Error('Candidate sort did not restore neutral observation order');
  } else {
    const numeric = state.metrics.filter(value=>value!==null);
    if (state.neutral || numeric.some((value,index)=>index>0 && (direction==='desc'?numeric[index-1]<value:numeric[index-1]>value)) || state.metrics.at(-1)!==null) throw new Error('Candidate numeric ordering or missing-metric retention failed');
  }
}
await screenshot('result-candidates-desktop');
await call('Emulation.setDeviceMetricsOverride',{width:375,height:812,deviceScaleFactor:1,mobile:true});
await noOverflow();
if (!(await evaluate(`parseFloat(getComputedStyle(document.querySelector('.candidate-table')).fontSize)>=13 && document.querySelector('.result-card').getBoundingClientRect().right<=innerWidth && document.querySelector('.table-scroll').scrollWidth>document.querySelector('.table-scroll').clientWidth`))) throw new Error('Mobile result or candidate table is unreadable');
await screenshot('result-candidates-mobile');
await call('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false});
await call('Page.navigate', {url:origin+'/instances/1/progress'});
await waitFor(`document.querySelector('[data-progress-heading]')?.textContent.includes('第 4 阶段') && document.querySelector('[data-stream-status]')?.textContent.includes('正在运行；等待助手输出')`);
await writeFile(process.env.SCID_TEST_ADVANCE, 'stopped');
await waitFor(`document.querySelector('[data-stream-status]')?.textContent.includes('运行状态未确认')`);
if ((await evaluate(`document.querySelector('[data-stream-status]').textContent`)).includes('等待助手输出')) throw new Error('Stopped runner still claims to wait for output');
await screenshot('live-progress-stopped-unconfirmed');
await call('Page.navigate', {url:origin+'/instances/1/'});
await waitFor(`document.getElementById('live-hero')?.innerText.includes('本次控制请求已停止推进') && document.getElementById('live-hero')?.innerText.includes('原任务状态待核对')`);
if ((await evaluate('document.body.innerText')).includes('Private fixture diagnostic')) throw new Error('Private stop diagnostic was rendered');
await call('Page.navigate', {url:origin+'/instances/1/results'});
await waitFor(`document.querySelector('#live-mechanisms .mechanism-trails') !== null && document.querySelector('[data-live-url]')?.dataset.state==='connected'`);
if ((await evaluate('location.pathname')) !== '/instances/1/results') throw new Error('Research process live connection changed the selected route');
if (!(await evaluate(`(()=>{const cards=Array.from(document.querySelectorAll('.mechanism-card'));const [first,second]=cards.map(card=>card.getBoundingClientRect());return cards.length===2 && Math.abs(first.top-second.top)<1 && second.left>first.right && cards.every(card=>!card.querySelector('details').open) && !document.querySelector('.mechanism-overview').innerText.includes('Original question detail')})()`))) throw new Error('Desktop mechanisms are not separate, concise, collapsed cards in two columns');
await noOverflow();
await screenshot('research-process-mechanisms-live');
await evaluate(`(()=>{const cards=document.querySelectorAll('.mechanism-card');window.neighborCardHeight=cards[1].getBoundingClientRect().height;window.previousMechanism=cards[0].querySelector('details');window.previousMechanism.open=true;window.previousMechanism.querySelector('summary').focus();return true})()`);
if (!(await evaluate(`Math.abs(document.querySelectorAll('.mechanism-card')[1].getBoundingClientRect().height-window.neighborCardHeight)<1 && document.querySelector('.mechanism-details').innerText.includes('Original disposition caveat')`))) throw new Error('Opening a mechanism stretches its neighbor or hides the full A reason');
// Cache lookups on navigation and SSE must not launch the fixture translator.
await waitFor(`!document.querySelector('[data-translation-start]').disabled`);
await writeFile(process.env.SCID_TEST_TRANSLATION_CLICK, 'explicit');
await evaluate(`document.querySelector('[data-translation-start]').click(); true`);
await waitFor(`document.querySelector('.mechanism-card h3 [data-translation-source]')?.textContent.startsWith('<b>译文</b>')`);
if (await evaluate(`document.querySelector('.mechanism-card h3 b') !== null`)) throw new Error('Model text was interpreted as HTML');
await evaluate(`document.querySelector('[data-translation-toggle]').click(); true`);
await waitFor(`document.querySelector('.mechanism-card h3').textContent==='Transport-driven response'`);
await evaluate(`document.querySelector('[data-translation-toggle]').click(); true`);
await waitFor(`document.querySelector('.mechanism-card h3').textContent.startsWith('<b>译文</b>')`);
// CRLF and LF source identities remain distinct through DOM attributes and toggles.
// Hold the next cache lookup so the busy-state button contract is observable.
await evaluate(`(()=>{const original=window.fetch;window.fetch=(input,options)=>{if(String(input).endsWith('/lookup') && options?.body && JSON.parse(options.body).texts.some(text=>text.startsWith('Line'))){return new Promise(resolve=>{window.releaseTranslationRead=()=>{window.fetch=original;resolve(original(input,options))}})}return original(input,options)};return true})()`);
await evaluate(`(()=>{for(const [id,source] of [['crlf','Line'+String.fromCharCode(13,10)+'end'],['lf','Line'+String.fromCharCode(10)+'end']]){const span=document.createElement('span');span.id='translation-'+id;span.dataset.translationSource=JSON.stringify(source);span.textContent=source;document.querySelector('main').append(span)}return true})()`);
await waitFor(`typeof window.releaseTranslationRead==='function'`);
if (!(await evaluate(`document.querySelector('[data-translation-start]').disabled`))) throw new Error('Translation start stayed enabled during cache lookup');
await evaluate(`window.releaseTranslationRead();true`);
await waitFor(`document.querySelector('#translation-crlf')?.dataset.translationStatus==='missing' && document.querySelector('#translation-lf')?.dataset.translationStatus==='missing' && !document.querySelector('[data-translation-start]').disabled`);
await evaluate(`document.querySelector('[data-translation-start]').click();true`);
await waitFor(`document.querySelector('#translation-crlf')?.dataset.translationStatus==='cached' && document.querySelector('#translation-lf')?.dataset.translationStatus==='cached'`);
await evaluate(`document.querySelector('[data-translation-toggle]').click();true`);
if (!(await evaluate(`document.querySelector('#translation-crlf').textContent==='Line'+String.fromCharCode(13,10)+'end' && document.querySelector('#translation-lf').textContent==='Line'+String.fromCharCode(10)+'end'`))) throw new Error('Original toggle normalized source newlines');
await evaluate(`document.querySelector('[data-translation-toggle]').click();true`);
await writeFile(process.env.SCID_TEST_ADVANCE, 'mechanisms-refresh');
await waitFor(`!window.previousMechanism.isConnected && document.querySelector('.mechanism-details').open && document.activeElement===document.querySelector('.mechanism-details > summary') && document.querySelector('.mechanism-overview').innerText.includes('Updated public observation.')`);
await waitFor(`document.querySelector('.mechanism-card h3').textContent.startsWith('<b>译文</b>')`);
if (!(await evaluate(`document.querySelector('.mechanism-overview').textContent.includes('Updated public observation.') && !Array.from(document.querySelectorAll('[data-translation-source]')).find(node=>JSON.parse(node.dataset.translationSource).startsWith('Updated public observation.'))?.textContent.startsWith('<b>译文</b>')`))) throw new Error('New live source used an old translation or launched automatically');
await screenshot('research-process-mechanisms-expanded-desktop');
await call('Emulation.setDeviceMetricsOverride',{width:375,height:812,deviceScaleFactor:1,mobile:true});
await noOverflow();
if (!(await evaluate(`(()=>{const cards=Array.from(document.querySelectorAll('.mechanism-card')).map(card=>card.getBoundingClientRect());const table=document.querySelector('.mechanism-details .table-scroll');return cards[1].top>=cards[0].bottom && Math.abs(cards[0].left-cards[1].left)<1 && cards.every(card=>card.right<=innerWidth) && table.scrollWidth>table.clientWidth})()`))) throw new Error('Mobile mechanism cards or expanded metric table overflow their own column');
await screenshot('research-process-mechanisms-expanded-mobile');
await evaluate(`document.querySelector('.mechanism-details').open=false;true`);
await noOverflow();
await screenshot('research-process-mechanisms-mobile');
await call('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false});
await call('Page.reload');
await waitFor(`document.querySelector('.mechanism-card h3')?.textContent.startsWith('<b>译文</b>')`);
// Natural-language settings work in the browser; switching languages never generates.
await call('Page.navigate', {url:origin+'/instances/1/reading'});
await waitFor(`document.querySelector('[name="target_language"]') !== null`);
await evaluate(`document.querySelector('[name="target_language"]').value='ja';document.querySelector('form[action$="/translation/configure"]').requestSubmit();true`);
await waitFor(`document.querySelector('[name="target_language"]')?.value==='ja' && document.querySelector('[data-translation-status]')?.textContent.includes('ja')`);
await call('Page.navigate', {url:origin+'/instances/1/results'});
await waitFor(`document.querySelector('.mechanism-card h3')?.textContent==='Transport-driven response' && !document.querySelector('[data-translation-start]').disabled`);
await call('Page.navigate', {url:origin+'/instances/1/reading'});
await waitFor(`document.querySelector('[name="target_language"]')?.value==='ja'`);
await evaluate(`document.querySelector('[name="target_language"]').value='zh-CN';document.querySelector('form[action$="/translation/configure"]').requestSubmit();true`);
await waitFor(`document.querySelector('[name="target_language"]')?.value==='zh-CN' && document.querySelector('[data-translation-status]')?.textContent.includes('zh-CN')`);
await evaluate(`document.querySelector('[name="timeout_seconds"]').value='301';document.querySelector('form[action$="/translation/configure"]').requestSubmit();true`);
await waitFor(`document.querySelector('h1')?.textContent==='翻译超时设置无效' && document.querySelector('[name="timeout_seconds"]').closest('details').open`);
if (await evaluate(`document.querySelector('[name="target_language"]').value`) !== 'zh-CN') throw new Error('Translation failure lost reading language');
await screenshot('reading-error-timeout-desktop');
await evaluate(`document.querySelector('[name="timeout_seconds"]').value='120';document.querySelector('form[action$="/translation/configure"]').requestSubmit();true`);
await waitFor(`document.querySelector('h1')?.textContent==='阅读与翻译'`);
await evaluate(`(()=>{const node=document.createElement('p');node.id='translation-failure-fixture';node.dataset.translationSource=JSON.stringify('Browser translation failure fixture');node.textContent='Browser translation failure fixture';document.querySelector('main').append(node)})();true`);
await waitFor(`document.querySelector('#translation-failure-fixture')?.dataset.translationStatus==='missing' && !document.querySelector('[data-translation-start]').disabled`);
await evaluate(`document.querySelector('[data-translation-start]').click();true`);
await waitFor(`document.querySelector('#translation-failure-fixture')?.dataset.translationStatus==='failed' && document.querySelector('[data-translation-status]').textContent.includes('超时')`);
if (await evaluate(`document.querySelector('#translation-failure-fixture').textContent`) !== 'Browser translation failure fixture') throw new Error('Failed translation replaced original source');
if (!(await evaluate(`document.querySelector('[data-translation-status]').textContent.includes('诊断编号')`))) throw new Error('Background translation failure lost diagnostic reference');
await screenshot('reading-error-background-translation-desktop');
await call('Page.navigate', {url:origin+'/instances/1/results'});
await waitFor(`document.querySelector('.mechanism-card h3')?.textContent.startsWith('<b>译文</b>')`);

await call('Page.navigate', {url:origin+'/instances/1/'});
await waitFor(`document.getElementById('live-hero')?.innerText.includes('本次控制请求已停止推进') && document.querySelector('[data-live-url]')?.dataset.state==='connected'`);
await evaluate(`(()=>{const note=document.querySelector('[name="authorization_note"]');note.value='Keep this expired-session draft';window.liveAuthChecks=0;const originalFetch=window.fetch;window.fetch=(url,options)=>{if(String(url).endsWith('/session')){window.liveAuthChecks++;window.checkedSessionURL=String(url);return Promise.resolve(new Response(JSON.stringify({error:{code:'browser_session_invalid',title:'浏览会话已失效',cause:'本地会话已过期。',hint:'请使用本次 management_url 重新打开。',reference:'live-fixture-ref'}}),{status:403,headers:{'Content-Type':'application/json'}}))}return originalFetch(url,options)};source.dispatchEvent(new Event('error'));return true})()`);
await waitFor(`document.querySelector('[data-live-url]')?.dataset.state==='expired' && document.querySelector('[data-live-url]').textContent.includes('management_url') && document.querySelector('[data-live-url]').textContent.includes('live-fixture-ref')`);
await new Promise(resolve=>setTimeout(resolve,1700));
if (!(await evaluate(`source===null && window.liveAuthChecks===1 && window.checkedSessionURL==='/instances/1/session' && document.querySelector('[name="authorization_note"]').value==='Keep this expired-session draft'`))) throw new Error('Expired SSE retained reconnect or lost draft/mounted session route');
await screenshot('reading-error-live-session-expired');
ws.close();
if (rendered.includes('{\"type\"')) throw new Error('Raw JSON appeared in the normal progress panel');
if (!rendered.includes('Public browser fixture')) throw new Error('Public event did not render after append: ' + rendered);
console.log(observed);
console.log(rendered);
'''
        checked = subprocess.run([node, '--input-type=module', '-e', script, str(port), origin, str(record / 'native.jsonl')],
            env=dict(os.environ, SCID_TEST_UI_MANAGEMENT_TOKEN=ui.management_token,
                SCID_TEST_INSTANCE_ROOT=str(root), SCID_TEST_PUBLIC_ROOT=str(workspace / 'public'),
                SCID_TEST_CONFIG_PATH=str(config), SCID_TEST_LOG_DIR=str(log_dir), SCID_TEST_ADVANCE=str(advance),
                SCID_TEST_TRANSLATION_CLICK=str(translation_permission)),
            capture_output=True, text=True, timeout=60)
        assert checked.returncode == 0, checked.stderr
        assert '已连接' in checked.stdout
        assert 'Public browser fixture' in checked.stdout
        assert owners == [(root, {})] and c.settings(root)['max_tokens'] == 1234
    finally:
        if browser is not None:
            import signal
            try: os.killpg(browser.pid, signal.SIGTERM)
            except ProcessLookupError: pass
            try: browser.wait(5)
            except subprocess.TimeoutExpired:
                os.killpg(browser.pid, signal.SIGKILL); browser.wait(5)
        if servers: servers[0].shutdown()
        thread.join(5)
        browser_stderr.close()
        browser_environment.cleanup()
    assert not thread.is_alive() and not errors
    assert translation_calls and all(explicit for explicit, _ in translation_calls)
    assert all(not source.startswith('Updated public observation.') for _, texts in translation_calls for source in texts)
    # Restart the application cache independently; cached fields require no provider.
    with_service = ui_translation.TranslationService(workspace / '.scid-ui')
    try:
        assert all(entry['status'] == 'cached' for entry in with_service.lookup(
            ['Transport-driven response', 'Line\r\nend', 'Line\nend'])['entries'])
    finally:
        with_service.close()
