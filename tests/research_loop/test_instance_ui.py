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
