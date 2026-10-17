"""One explicit instance's loopback host; P3c serves execution decisions only.

P4 adds instance pages to this same server/session. No HTTP route dispatches
science, execution, cancellation or a resource amendment.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import html
import hmac
import json
import os
from pathlib import Path
import secrets
import shutil
from urllib.parse import parse_qs, urlsplit
import uuid

from scidiscovery.browser_access import BrowserAccessService, access_cookie, cookie_name
from scidiscovery import execution_security as security
from . import contracts as c, execution_authority as authority


@contextmanager
def _host_lock(root):
    fd = os.open(root / 'execution-authority/ui.lock',
                 os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError('This instance already has a UI host') from error
        yield
    finally:
        os.close(fd)


class InstanceUI:
    def __init__(self, root, *, secret_file):
        self.root = Path(root).resolve()
        authority.contract(self.root)
        self.secret = security.read_secret_file(secret_file, label='approval receipt')
        authority.bind_secret(self.root, self.secret, source=secret_file)
        self.instance = c.settings(self.root)['goal_id']
        self.boot = uuid.uuid4().hex
        self.browser = BrowserAccessService(secret=self.secret, ui_session_id=self.boot)
        self.management_token = secrets.token_urlsafe(32)
        self.host = None

    def _browser(self, cookie):
        self.browser.from_cookie(cookie, instance_id=self.instance, scope='maintenance')
        from http.cookies import SimpleCookie
        parsed = SimpleCookie(); parsed.load(cookie)
        return parsed[cookie_name(self.instance)].value

    def _page(self, title, body):
        return ('<!doctype html><html lang="en"><meta charset="utf-8"><title>'
                + html.escape(title) + '</title><h1>' + html.escape(title) + '</h1>'
                + body + '</html>').encode('utf-8')

    def get(self, target, *, host, cookie=None):
        if host != self.host:
            raise PermissionError('Exact local Host required')
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or parsed.fragment:
            raise PermissionError('Local relative request target required')
        if parsed.path == '/manage':
            query = parse_qs(parsed.query, strict_parsing=True)
            values = query.get('token', [])
            if set(query) != {'token'} or len(values) != 1 or not hmac.compare_digest(values[0], self.management_token):
                raise PermissionError('Local management link is invalid')
            token = self.browser.issue(self.instance, maintenance=True)
            return 303, b'', {'Location': '/', 'Set-Cookie': access_cookie(self.instance, token)}
        browser_token = self._browser(cookie)
        if parsed.path == '/':
            query = parse_qs(parsed.query, strict_parsing=True) if parsed.query else {}
            if set(query) - {'after'} or any(len(values) != 1 for values in query.values()):
                raise ValueError('Exact request continuation required')
            after = query.get('after', [''])[0]
            if after and not authority.ID.fullmatch(after):
                raise ValueError('Invalid request continuation')
            directory = self.root / 'execution-authority/requests'
            paths = sorted(directory.iterdir()) if directory.exists() else []
            ids = [path.name for path in paths if authority.ID.fullmatch(path.name) and path.name > after]
            links = ''.join('<li><a href="/requests/' + key + '">' + key + '</a></li>' for key in ids[:20])
            more = ('<a href="/?after=' + ids[19] + '">Next requests</a>') if len(ids) > 20 else ''
            return 200, self._page('Execution requests', '<p>Decisions grant no execution or additional budget by themselves.</p><ul>' + links + '</ul>' + more), {}
        parts = parsed.path.strip('/').split('/')
        if parsed.query or len(parts) not in (2, 3) or parts[0] != 'requests':
            raise ValueError('Unknown instance UI path')
        request_id = parts[1]
        value, ref = authority.request(self.root, request_id)
        if len(parts) == 3:
            if parts[2] != 'original':
                raise ValueError('Unknown request original')
            return 200, self.root / ref['path'], {'Content-Type': 'application/json; charset=utf-8'}
        state = authority.status(self.root, request_id, secret=self.secret)
        tokens = authority.form_tokens(self.root, request_id, secret=self.secret,
                                       boot=self.boot, browser_token=browser_token)
        # Full mechanical binding stays available as an exact original download.
        compact = dict(state=state['state'], subject=value['subject']['material']['path'],
            target=value['target'], resources=value['resources'], policy=value['policy']['outcome'],
            expires_at=value['expires_at'], scope=authority.SCOPE)
        body = '<pre>' + html.escape(json.dumps(compact, ensure_ascii=False, indent=2)) + '</pre>'
        body += '<p><a href="/requests/' + request_id + '/original">Complete frozen request</a></p>'
        if state['state'] == 'pending':
            options = ''.join('<option value="' + item + '">' + item + '</option>' for item in value['options'])
            body += ('<form method="post" action="/requests/' + request_id + '/decision">'
                '<input type="hidden" name="nonce" value="' + tokens['nonce'] + '">'
                '<input type="hidden" name="csrf" value="' + tokens['csrf'] + '">'
                '<label>Decision <select name="selected_option">' + options + '</select></label>'
                '<label>Reason <textarea name="rationale" required></textarea></label>'
                '<button type="submit">Record decision</button></form>')
        if state['state'] in {'pending', 'decided'}:
            body += ('<form method="post" action="/requests/' + request_id + '/revoke">'
                '<input type="hidden" name="nonce" value="' + tokens['nonce'] + '">'
                '<input type="hidden" name="csrf" value="' + tokens['csrf'] + '">'
                '<label>Reason <textarea name="rationale" required></textarea></label>'
                '<button type="submit">Revoke request</button></form>')
        return 200, self._page('Exact execution decision', body), {}

    def post(self, target, *, host, origin, cookie, content_type, body):
        security.require_same_origin(host, origin, self.host)
        browser_token = self._browser(cookie)
        parsed = urlsplit(target)
        parts = parsed.path.strip('/').split('/')
        if (parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or len(parts) != 3
                or parts[0] != 'requests' or parts[2] not in {'decision', 'revoke'}
                or content_type != 'application/x-www-form-urlencoded'):
            raise ValueError('Exact execution decision form required')
        form = parse_qs(body.decode('utf-8'), keep_blank_values=True, strict_parsing=True)
        fields = {'nonce', 'csrf', 'rationale'} | ({'selected_option'} if parts[2] == 'decision' else set())
        if set(form) != fields or any(len(values) != 1 for values in form.values()):
            raise ValueError('Decision form contains missing or duplicate fields')
        form = {key: values[0] for key, values in form.items()}
        if parts[2] == 'decision':
            authority.record_decision(self.root, parts[1], secret=self.secret, boot=self.boot,
                browser_token=browser_token, **form)
        else:
            expected = authority.form_tokens(self.root, parts[1], secret=self.secret,
                boot=self.boot, browser_token=browser_token)
            if not all(hmac.compare_digest(form[key], expected[key]) for key in ('nonce', 'csrf')):
                raise PermissionError('Execution revocation CSRF or nonce mismatch')
            authority.revoke(self.root, parts[1], secret=self.secret, reason=form['rationale'])
        return 303, b'', {'Location': '/requests/' + parts[1]}


def serve(root, *, secret_file, port=0):
    root = Path(root).resolve()
    ui = InstanceUI(root, secret_file=secret_file)

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, *args):
            pass  # Never copy capability URLs/cookies into logs.

        def handle_request(self, method):
            try:
                fields = ('Host', 'Cookie') + (('Origin', 'Content-Length', 'Content-Type') if method == 'POST' else ())
                if self.headers.get('Transfer-Encoding') or any(len(self.headers.get_all(name, [])) > 1 for name in fields):
                    raise PermissionError('Ambiguous request headers are not accepted')
                if method == 'GET':
                    result = ui.get(self.path, host=self.headers.get('Host'), cookie=self.headers.get('Cookie'))
                else:
                    length = self.headers.get('Content-Length')
                    # A transport form limit is not a record/history truncation.
                    if length is None or not length.isdecimal() or not 0 < int(length) <= 65536:
                        raise ValueError('Decision form length is invalid')
                    result = ui.post(self.path, host=self.headers.get('Host'), origin=self.headers.get('Origin'),
                        cookie=self.headers.get('Cookie'), content_type=self.headers.get('Content-Type'),
                        body=self.rfile.read(int(length)))
                status, body, headers = result
            except (PermissionError, ValueError, OSError, KeyError, TypeError) as error:
                status, body, headers = 403, ui._page('Request unavailable', '<p>' + html.escape(str(error)) + '</p>'), {}
            self.send_response(status)
            self.send_header('Content-Type', headers.pop('Content-Type', 'text/html; charset=utf-8'))
            for key, value in {'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer',
                    'X-Content-Type-Options': 'nosniff', 'Content-Security-Policy':
                    "default-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'", **headers}.items():
                self.send_header(key, value)
            self.send_header('Content-Length', str(body.stat().st_size if isinstance(body, Path) else len(body)))
            self.end_headers()
            if isinstance(body, Path):
                with c.regular(body).open('rb') as stream:
                    shutil.copyfileobj(stream, self.wfile)
            else:
                self.wfile.write(body)

        def do_GET(self):
            self.handle_request('GET')

        def do_POST(self):
            self.handle_request('POST')

    with _host_lock(root), ThreadingHTTPServer(('127.0.0.1', port), Handler) as server:
        ui.host = '127.0.0.1:' + str(server.server_port)
        endpoint = dict(instance=ui.instance, boot=ui.boot, origin='http://' + ui.host)
        endpoint['receipt_hmac'] = security.receipt_hmac(ui.secret, security.canonical(endpoint))
        c.write(root / 'execution-authority/ui-endpoint.json', endpoint)
        print(json.dumps(dict(status='ui_listening', instance=ui.instance,
            management_url='http://' + ui.host + '/manage?token=' + ui.management_token), ensure_ascii=False), flush=True)
        try:
            server.serve_forever(poll_interval=.5)
        except KeyboardInterrupt:
            pass
        finally:
            (root / 'execution-authority/ui-endpoint.json').unlink(missing_ok=True)
    return dict(status='ui_stopped')
