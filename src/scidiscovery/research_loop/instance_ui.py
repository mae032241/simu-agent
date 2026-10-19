"""One explicit instance's loopback status, controls and optional decision host."""
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
import threading
from urllib.parse import parse_qs, quote, urlsplit
import uuid

from scidiscovery.browser_access import BrowserAccessService, access_cookie, cookie_name
from scidiscovery import execution_security as security
from . import budget, contracts as c, execution, execution_authority as authority, instance_control as control
from . import instance_science as science
from . import instance_render as render


@contextmanager
def _host_lock(root):
    (root / 'execution-authority').mkdir(exist_ok=True)
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
        settings = c.settings(self.root)
        self.approvals = settings.get('execution_authority_policy') is not None
        self.secret = security.read_secret_file(secret_file, label='instance UI')
        if self.approvals:
            authority.contract(self.root)
            authority.bind_secret(self.root, self.secret, source=secret_file)
        self.instance = settings['goal_id']
        self.boot = uuid.uuid4().hex
        self.browser = BrowserAccessService(secret=self.secret, ui_session_id=self.boot)
        self.management_token = secrets.token_urlsafe(32)
        self.read_token = secrets.token_urlsafe(32)
        self.control_nonce = secrets.token_urlsafe(32)
        self.control_lock = threading.Lock()
        self.control_thread = None
        self.control_result = None
        self.host = None

    def _browser(self, cookie, *, scope='maintenance'):
        self.browser.from_cookie(cookie, instance_id=self.instance, scope=scope)
        from http.cookies import SimpleCookie
        parsed = SimpleCookie(); parsed.load(cookie)
        return parsed[cookie_name(self.instance)].value

    def _page(self, title, body):
        return render.page(title,body)

    def _csrf(self, browser_token, action, nonce):
        return security.receipt_hmac(self.secret, security.canonical(
            ['scidiscovery.instance-control.v1', self.instance, self.boot, browser_token, action, nonce]))

    def _control_form(self, browser_token, action, *, correction_trigger=None):
        with self.control_lock:
            nonce = self.control_nonce
        body = ('<form method="post" action="/control/' + action + '">'
            '<input type="hidden" name="nonce" value="' + nonce + '">'
            '<input type="hidden" name="csrf" value="' + self._csrf(browser_token, action, nonce) + '">')
        if action == 'continue':
            body += ('<input type="hidden" name="ack_correction" value="'
                + html.escape(correction_trigger or '', quote=True) + '">')
            body += ('<label>Reason for continuing after the correction pause '
                '<textarea name="authorization_note" required></textarea></label>' if correction_trigger else
                '<input type="hidden" name="authorization_note" value="">')
        return body + '<button type="submit">' + action.capitalize() + '</button></form>'

    def _continue(self, **options):
        """One non-daemon advancement owner, no queue and no server-stop cancel."""
        def work():
            try:
                value = control.continue_instance(self.root, **options)
                result = dict(action='continue', state='finished', status=value.get('status'),
                    note=str(value.get('reason', '')))
            except Exception as error:
                result = dict(action='continue', state='failed', note=str(error))
            note = result['note']
            result.update(note=note[:512], note_omitted_characters=max(0, len(note) - 512))
            with self.control_lock:
                self.control_result = result
        if self.control_thread is not None and self.control_thread.is_alive():
            raise RuntimeError('This instance UI already has an ongoing continue request; no request queued')
        self.control_result = dict(action='continue', state='running')
        self.control_thread = threading.Thread(target=work, name='scid-instance-continue', daemon=False)
        self.control_thread.start()

    @staticmethod
    def _node_view(node):
        value = {key: str(node[key])[:300] if isinstance(node[key], str) else node[key]
                for key in ('step', 'role', 'state', 'stop_reason', 'returncode', 'continuations') if key in node}
        if isinstance(node.get('stop_reason'), str):
            value['stop_reason_omitted_characters'] = max(0, len(node['stop_reason']) - 300)
        return value

    def _instance_page(self, browser_token, *, after=0, step=None):
        view = control.status(self.root, after=step - 1 if step is not None else after,
                              limit=1 if step is not None else 20, live_feedback=False)
        if step is not None and not view['nodes']:
            raise ValueError('This instance node does not exist')
        manager = 'maintenance' in self.browser.verify(browser_token, instance_id=self.instance).scopes
        limits, usage = view['budget'], view['usage']
        summary = dict(instance=self.instance, paused=view['paused'],
            budget={key: limits[key] for key in ('max_tokens', 'max_seconds', 'seconds_remaining',
                'clock_phase', 'advance_seconds', 'waiting_seconds')},
            observed_tokens=usage['observed_tokens'], tokens_remaining_from_observed_usage=max(0, limits['max_tokens'] - usage['observed_tokens']),
            unknown_usage_nodes=len(usage['unknown_steps']),
            reserved_tokens=usage.get('reserved_tokens', 0),
            accounted_tokens=usage.get('accounted_tokens', usage['observed_tokens']),
            blocking_unknown_usage_nodes=len(usage.get('blocking_unknown_steps', usage['unknown_steps'])),
            correction_trigger=(view['correction'].get('current_pause') or {}).get('trigger_id'))
        with self.control_lock:
            summary['last_control_request'] = self.control_result
        body = '<nav><a href="/">Instance</a> | <a href="/results">Scientific results</a> | ' + ('<a href="/requests">Execution requests</a>'
            if self.approvals else 'Execution approval routes unavailable') + '</nav>'
        body += '<pre>' + html.escape(json.dumps(summary, ensure_ascii=False, indent=2)) + '</pre>'
        body += '<p><a href="/">Refresh status</a></p>'
        body += '<p>Pause lets accepted work finish. Continue uses the original authorization and does not replay unknown work.</p>'
        if manager:
            body += self._control_form(browser_token, 'pause') + self._control_form(browser_token, 'continue',
                correction_trigger=summary['correction_trigger'])
        else:
            body += '<p>Read access only. Open the local management link to use controls.</p>'
        body += '<h2>Nodes</h2><ul>'
        for node in view['nodes']:
            body += ('<li><a href="/nodes/' + str(node['step']) + '">Node ' + str(node['step'])
                + '</a><pre>' + html.escape(json.dumps(self._node_view(node), ensure_ascii=False)) + '</pre></li>')
        body += '</ul>'
        if step is not None and view['nodes'][0]['state']=='seal_present_unverified':
            body += ('<p><a href="/results/'+str(step)+'">Scientific result page</a> | <a href="/nodes/'+str(step)+'/science">Complete sealed scientific conclusion</a> | '
                '<a href="/nodes/'+str(step)+'/materials">Sealed scientific deliverables</a></p>'
                '<p>Original bytes are checked only when opened. Sealing does not establish scientific validity or execution permission.</p>')
        if step is None and view.get('next_after') is not None:
            body += '<a href="/?after=' + str(view['next_after']) + '">Next nodes</a>'
        return 200, self._page('Instance status', body), {}

    def _materials_page(self, step, after):
        page=science.materials(self.root,step,after=after)
        body='<nav><a href="/nodes/'+str(step)+'">Node '+str(step)+'</a></nav><ul>'
        for item in page['items']:
            body += ('<li><a href="/nodes/'+str(step)+'/materials/'+str(item['index'])+'">'
                +html.escape(item['name'])+'</a> ('+str(item['size_bytes'])+' bytes)</li>')
        body+='</ul><p>'+str(page['total'])+' sealed deliverables. '+html.escape(page['scope'])+'</p>'
        if page['next_after'] is not None:
            body += '<a href="/nodes/'+str(step)+'/materials?after='+str(page['next_after'])+'">Next deliverables</a>'
        return 200,self._page('Sealed scientific deliverables',body),{}

    def _results_page(self, after):
        maximum=budget.historical_step_limit(self.root)
        steps=sorted(int(path.stem) for path in (self.root/'jobs').glob('*.json')
            if path.stem.isascii() and path.stem.isdecimal() and path.stem==f'{int(path.stem):03d}'
            and after<int(path.stem)<=maximum)
        found=[]
        for step in steps:
            record=execution.origin(self.root,step)/'result-identity.json'
            if record.exists() or record.is_symlink():found.append(step)
            if len(found)==21:break
        body='<nav><a href="/">Instance status</a></nav><p>Sealed records are listed here. Original identity is verified when opened; this list does not establish scientific acceptance.</p><ul>'
        for step in found[:20]:body+='<li><a href="/results/'+str(step)+'">Scientific result · Node '+str(step)+'</a></li>'
        body+='</ul>'
        if not found:body+='<p>No further sealed scientific records are present.</p>'
        if len(found)>20:body+='<a href="/results?after='+str(found[19])+'">Next scientific results</a>'
        return 200,self._page('Scientific results',body),{}

    def _result_page(self, step):
        _,seal,raw,proof=science._sealed(self.root,step)
        job_path=self.root/'jobs'/f'{step:03d}.json'
        job=science._json(job_path,science._proof(job_path,seal['job_sha256']))
        with science.Original(raw,proof) as original:
            payload=json.load(original.stream);original.check()
        return 200,render.result(step,job,payload,seal),{}

    def get(self, target, *, host, cookie=None):
        if host != self.host:
            raise PermissionError('Exact local Host required')
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or parsed.fragment:
            raise PermissionError('Local relative request target required')
        if parsed.path in {'/manage', '/view'}:
            query = parse_qs(parsed.query, strict_parsing=True)
            values = query.get('token', [])
            expected = self.management_token if parsed.path == '/manage' else self.read_token
            if set(query) != {'token'} or len(values) != 1 or not hmac.compare_digest(values[0], expected):
                raise PermissionError('Local management link is invalid')
            token = self.browser.issue(self.instance, maintenance=parsed.path == '/manage')
            return 303, b'', {'Location': '/', 'Set-Cookie': access_cookie(self.instance, token)}
        browser_token = self._browser(cookie, scope='read')
        if parsed.path=='/results':
            query=parse_qs(parsed.query,strict_parsing=True) if parsed.query else {}
            if set(query)-{'after'} or any(len(values)!=1 for values in query.values()):
                raise ValueError('Exact scientific result continuation required')
            after=query.get('after',['0'])[0]
            if not after.isascii() or not after.isdecimal():raise ValueError('Exact scientific result continuation required')
            return self._results_page(int(after))
        if parsed.path.startswith('/results/'):
            number=parsed.path.removeprefix('/results/')
            if parsed.query or not number.isascii() or not number.isdecimal() or int(number)<=0:
                raise ValueError('Exact sealed scientific result required')
            return self._result_page(int(number))
        if parsed.path == '/':
            query = parse_qs(parsed.query, strict_parsing=True) if parsed.query else {}
            if set(query) - {'after'} or any(len(values) != 1 for values in query.values()):
                raise ValueError('Exact node continuation required')
            after = query.get('after', ['0'])[0]
            if not after.isascii() or not after.isdecimal():
                raise ValueError('Invalid node continuation')
            return self._instance_page(browser_token, after=int(after))
        if parsed.path.startswith('/nodes/'):
            parts = parsed.path.removeprefix('/nodes/').split('/')
            number = parts[0]
            if not number.isascii() or not number.isdecimal() or int(number)<=0:
                raise ValueError('Exact instance node required')
            step=int(number)
            if len(parts)==1 and not parsed.query:
                return self._instance_page(browser_token,step=step)
            if parts[1:]==['science'] and not parsed.query:
                return 200,science.science(self.root,step),{'Content-Type':'application/json; charset=utf-8'}
            if parts[1:]==['materials']:
                query=parse_qs(parsed.query,strict_parsing=True) if parsed.query else {}
                if set(query)-{'after'} or any(len(values)!=1 for values in query.values()):
                    raise ValueError('Exact scientific deliverable continuation required')
                after=query.get('after',['0'])[0]
                if not after.isascii() or not after.isdecimal():
                    raise ValueError('Exact scientific deliverable continuation required')
                return self._materials_page(step,int(after))
            if len(parts)==3 and parts[1]=='materials' and not parsed.query:
                if not parts[2].isascii() or not parts[2].isdecimal() or int(parts[2])<=0:
                    raise ValueError('Exact scientific deliverable index required')
                original,name=science.artifact(self.root,step,int(parts[2]))
                return 200,original,{'Content-Type':'application/octet-stream',
                    'Content-Disposition':"attachment; filename=scientific-deliverable; filename*=UTF-8''"+quote(name,safe='')}
            raise ValueError('Exact instance node required')
        if not self.approvals:
            raise ValueError('Execution approval routes are unavailable for this instance; status and controls remain available')
        if parsed.path == '/requests':
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
            more = ('<a href="/requests?after=' + ids[19] + '">Next requests</a>') if len(ids) > 20 else ''
            return 200, self._page('Execution requests', '<a href="/">Instance</a><p>Decisions grant no execution or additional budget by themselves.</p><ul>' + links + '</ul>' + more), {}
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
        successor=authority.request_successor(self.root,ref)
        if successor is not None:
            body += '<p><a href="/requests/' + Path(successor['path']).parent.name + '">Explicit replacement request</a> (the original request and decision remain unchanged).</p>'
        manager = 'maintenance' in self.browser.verify(browser_token, instance_id=self.instance).scopes
        if manager and state['state'] == 'pending':
            options = ''.join('<option value="' + item + '">' + item + '</option>' for item in value['options'])
            body += ('<form method="post" action="/requests/' + request_id + '/decision">'
                '<input type="hidden" name="nonce" value="' + tokens['nonce'] + '">'
                '<input type="hidden" name="csrf" value="' + tokens['csrf'] + '">'
                '<label>Decision <select name="selected_option">' + options + '</select></label>'
                '<label>Reason <textarea name="rationale" required></textarea></label>'
                '<button type="submit">Record decision</button></form>')
        if manager and state['state'] in {'pending', 'decided'}:
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
        if (parsed.scheme or parsed.netloc or parsed.query or parsed.fragment
                or content_type != 'application/x-www-form-urlencoded'):
            raise ValueError('Exact instance control or decision form required')
        if len(parts) == 2 and parts[0] == 'control' and parts[1] in {'pause', 'continue'}:
            form = parse_qs(body.decode('utf-8'), keep_blank_values=True, strict_parsing=True)
            fields = {'nonce', 'csrf'} | ({'ack_correction', 'authorization_note'} if parts[1] == 'continue' else set())
            if set(form) != fields or any(len(values) != 1 for values in form.values()):
                raise ValueError('Control form contains missing or duplicate fields')
            form = {key: values[0] for key, values in form.items()}
            with self.control_lock:
                if (not hmac.compare_digest(form['nonce'], self.control_nonce) or not hmac.compare_digest(
                        form['csrf'], self._csrf(browser_token, parts[1], form['nonce']))):
                    raise PermissionError('Instance control CSRF or nonce mismatch')
                if parts[1] == 'continue':
                    self._continue(ack_correction=form['ack_correction'] or None,
                                   authorization_note=form['authorization_note'] or None)
                else:
                    # Pause is an immediate marker, never a second advancement
                    # owner, and must remain usable during a live continue.
                    control.request_pause(self.root)
                self.control_nonce = secrets.token_urlsafe(32)
            return 303, b'', {'Location': '/'}
        if not self.approvals:
            raise ValueError('Execution approval routes are unavailable for this instance')
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
            body=None
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
                if isinstance(body,science.Original):
                    body.check()
            except (PermissionError, ValueError, OSError, KeyError, TypeError, RuntimeError) as error:
                if isinstance(body,science.Original):body.close()
                status, body, headers = (409 if isinstance(error, RuntimeError) else 403), ui._page(
                    'Request unavailable', '<p>' + html.escape(str(error)) + '</p>'), {}
            try:
                self.send_response(status)
                self.send_header('Content-Type', headers.pop('Content-Type', 'text/html; charset=utf-8'))
                for key, value in {'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer',
                        'X-Content-Type-Options': 'nosniff', 'Content-Security-Policy':
                        render.CSP, **headers}.items():
                    self.send_header(key, value)
                length=body.size if isinstance(body,science.Original) else body.stat().st_size if isinstance(body,Path) else len(body)
                self.send_header('Content-Length',str(length))
                self.end_headers()
                if isinstance(body,science.Original):
                    body.copy_to(self.wfile)
                elif isinstance(body,Path):
                    with c.regular(body).open('rb') as stream:
                        shutil.copyfileobj(stream,self.wfile)
                else:
                    self.wfile.write(body)
            finally:
                if isinstance(body,science.Original):body.close()

        def do_GET(self):
            self.handle_request('GET')

        def do_POST(self):
            self.handle_request('POST')

    with _host_lock(root), ThreadingHTTPServer(('127.0.0.1', port), Handler) as server:
        ui.host = '127.0.0.1:' + str(server.server_port)
        if ui.approvals:
            endpoint = dict(instance=ui.instance, boot=ui.boot, origin='http://' + ui.host)
            endpoint['receipt_hmac'] = security.receipt_hmac(ui.secret, security.canonical(endpoint))
            c.write(root / 'execution-authority/ui-endpoint.json', endpoint)
        print(json.dumps(dict(status='ui_listening', instance=ui.instance,
            management_url='http://' + ui.host + '/manage?token=' + ui.management_token,
            read_url='http://' + ui.host + '/view?token=' + ui.read_token), ensure_ascii=False), flush=True)
        try:
            server.serve_forever(poll_interval=.5)
        except KeyboardInterrupt:
            pass
        finally:
            if ui.approvals:
                (root / 'execution-authority/ui-endpoint.json').unlink(missing_ok=True)
    return dict(status='ui_stopped')
