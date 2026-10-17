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


def test_single_continue_owner_still_allows_immediate_pause(tmp_path, monkeypatch):
    root, key = prepare(tmp_path, enabled=False)
    ui, cookie = session(root, key)
    entered, release = threading.Event(), threading.Event()
    owners = []

    def accepted_control(instance):
        # The real shared continue holds controller._writer around this bounded
        # stand-in. No scientific node, native process or fake result is sealed.
        owners.append(instance); entered.set()
        assert release.wait(5)
        return dict(status='wait', reason='Control boundary fixture only')

    monkeypatch.setattr(controller, '_run', accepted_control)
    control.request_pause(root)
    assert post(ui, cookie, 'continue', form(ui, cookie, 'continue'))[0] == 303
    try:
        assert entered.wait(5) and not (root / 'pause.request').exists()
        assert ui.control_thread.is_alive() and not ui.control_thread.daemon
        with pytest.raises(RuntimeError, match='ongoing continue'):
            post(ui, cookie, 'continue', form(ui, cookie, 'continue'))
        pause = form(ui, cookie, 'pause')
        assert post(ui, cookie, 'pause', pause)[0] == 303
        assert (root / 'pause.request').exists() and ui.control_thread.is_alive()
        with pytest.raises(PermissionError, match='nonce'):
            post(ui, cookie, 'pause', pause)
        assert post(ui, cookie, 'pause', form(ui, cookie, 'pause'))[0] == 303
        before = (root / 'pause.request').read_bytes()
        with pytest.raises(RuntimeError, match='running controller'):
            control.continue_instance(root)
        assert (root / 'pause.request').read_bytes() == before and owners == [root]
    finally:
        release.set(); ui.control_thread.join(5)
    assert not ui.control_thread.is_alive() and ui.control_result['status'] == 'wait'
    assert (root / 'pause.request').exists() and not list(root.glob('**/accepted.json'))


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
        response=connection.getresponse();assert response.status==403;response.read()
        connection.request('GET','/view?'+urlencode({'token':ui.read_token}))
        response=connection.getresponse();assert response.status==303
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
