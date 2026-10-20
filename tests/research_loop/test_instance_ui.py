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
    assert '最终结论已返回' in overview and '查看最终结果' in overview


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


def test_read_cookie_opens_only_sealed_science_and_attachment_members(tmp_path,monkeypatch):
    from test_instance_science import read
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
    assert b'/nodes/1/materials/1' in page and b'<script>' not in page
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
    from scidiscovery.research_loop import instance_ui, contracts as c, execution
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
                if stage == '2':
                    finish(root, 1, 'H', [], action='analyze', summary='First browser phase finding')
                    _, _, output = finish(root, 2, 'A', [1], summary='Second browser phase conclusion')
                    (output / 'native.jsonl').write_text(json.dumps(dict(type='item.completed', item=dict(type='agent_message', text='Second phase public output'))) + '\n')
                elif stage == '3':
                    _, _, output = finish(root, 3, 'H', [2], action='analyze', summary='Third browser phase conclusion')
                    (output / 'native.jsonl').write_text(json.dumps(dict(type='item.completed', item=dict(type='agent_message', text='Third phase public output'))) + '\n')
        return original_snapshot(selected, **options)
    monkeypatch.setattr(InstanceUI, '_snapshot', fixture_snapshot)
    monkeypatch.setattr(control, 'start_background', detached)
    ui = InstanceUI(workspace, secret_file=key, workspace=True); ready = threading.Event(); servers = []; errors = []
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
import {join} from 'node:path';
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
// Import a nested declaration, then traverse both steps without changing any control.
await evaluate(`document.querySelector('.setup-tools').open=true;document.querySelector('[name="config_path"]').value=${JSON.stringify(process.env.SCID_TEST_CONFIG_PATH)};document.querySelector('form[action="/control/load-config"] button').click();true`);
await waitFor(`document.querySelector('.import-notice') !== null && document.querySelector('[aria-current=step]')?.dataset.setupMarker === '1'`);
const imported = await evaluate(`JSON.stringify(Array.from(new FormData(document.getElementById('research-config-form'))).filter(([name])=>!['nonce','csrf','selection'].includes(name)))`);
await evaluate(`document.querySelector('[data-setup-go="2"]').click();true`);
await waitFor(`document.querySelector('[aria-current=step]')?.dataset.setupMarker === '2'`);
await evaluate(`document.querySelector('[data-setup-go="1"]').click();true`);
const returned = await evaluate(`JSON.stringify(Array.from(new FormData(document.getElementById('research-config-form'))).filter(([name])=>!['nonce','csrf','selection'].includes(name)))`);
if (imported !== returned || !returned.includes('imported-worker-model') || !returned.includes('retained')) throw new Error('Imported nested controls changed across steps');
await call('Page.navigate', {url:origin+'/new'});
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
await waitFor('location.pathname === "/instances/1/" && document.body.innerText.includes("实例已创建")');
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
await appendFile(transport, JSON.stringify({type: 'item.completed', item: {type: 'agent_message', text: 'Public browser fixture'}}) + '\n');
let rendered = '';
for (let index = 0; index < 60; index++) {
  await new Promise(resolve => setTimeout(resolve, 100));
  const answer = await call('Runtime.evaluate', {expression: 'document.querySelector("[data-events]")?.textContent || ""', returnByValue: true});
  rendered = answer.result.value;
  if (rendered.includes('Public browser fixture')) break;
}
if (!rendered.includes('Public browser fixture')) throw new Error('Initial fixed output missing');
await call('Page.navigate', {url:origin+'/instances/1/progress'});
await waitFor(`document.querySelector('[data-progress-heading]')?.textContent.includes('第 1 阶段') && document.querySelector('[data-events]')?.textContent.includes('Public browser fixture')`);
await writeFile(process.env.SCID_TEST_ADVANCE, '2');
await waitFor(`document.querySelector('[data-progress-heading]')?.textContent.includes('第 2 阶段') && document.querySelector('[data-events]')?.textContent.includes('Second phase public output')`);
if ((await evaluate('location.pathname')) !== '/instances/1/progress') throw new Error('Following output navigated away');
await screenshot('live-follow-current-node');
await call('Page.navigate', {url:origin+'/instances/1/nodes/1/progress?attempt=0'});
await waitFor(`document.querySelector('[data-events]')?.textContent.includes('Public browser fixture')`);
if ((await evaluate(`document.querySelector('[data-events]').textContent`)).includes('Second phase public output')) throw new Error('Historical output followed a newer node');
await call('Page.navigate', {url:origin+'/instances/1/'});
await waitFor(`document.getElementById('live-hero')?.innerText.includes('第 2 阶段') && document.querySelector('[data-live-url]')?.dataset.state==='connected'`);
await evaluate(`window.liveDraftSentinel='preserved';document.querySelector('details.secondary').open=true;document.querySelector('form[action="/instances/1/control/budget"] [name="max_tokens"]').value='4321';document.querySelector('form[action="/instances/1/control/budget"] [name="authorization_note"]').value='Keep this unsent budget explanation';true`);
await writeFile(process.env.SCID_TEST_ADVANCE, '3');
await waitFor(`document.getElementById('live-hero')?.innerText.includes('第 3 阶段') && document.getElementById('live-usage')?.innerText.includes('30 / 1234 tokens') && document.getElementById('live-conclusion')?.innerText.includes('Third browser phase conclusion')`);
if (!(await evaluate(`window.liveDraftSentinel==='preserved' && document.querySelector('form[action="/instances/1/control/budget"] [name="max_tokens"]').value==='4321' && document.querySelector('form[action="/instances/1/control/budget"] [name="authorization_note"]').value==='Keep this unsent budget explanation'`))) throw new Error('Live dashboard lost typed values or reloaded');
await screenshot('live-dashboard-draft-preserved');
await call('Page.navigate', {url:origin+'/'});
await waitFor(`document.getElementById('live-instances')?.innerText.includes('第 3 阶段') && document.getElementById('live-instances')?.innerText.includes('30 / 1234 tokens')`);
await screenshot('live-workbench-loaded-status');
ws.close();
if (rendered.includes('{\"type\"')) throw new Error('Raw JSON appeared in the normal progress panel');
if (!rendered.includes('Public browser fixture')) throw new Error('Public event did not render after append: ' + rendered);
console.log(observed);
console.log(rendered);
'''
        checked = subprocess.run([node, '--input-type=module', '-e', script, str(port), origin, str(record / 'native.jsonl')],
            env=dict(os.environ, SCID_TEST_UI_MANAGEMENT_TOKEN=ui.management_token,
                SCID_TEST_INSTANCE_ROOT=str(root), SCID_TEST_PUBLIC_ROOT=str(workspace / 'public'),
                SCID_TEST_CONFIG_PATH=str(config), SCID_TEST_LOG_DIR=str(log_dir), SCID_TEST_ADVANCE=str(advance)),
            capture_output=True, text=True, timeout=45)
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
