"""Authority-only negatives; no backend/resource permission is asserted here."""
import hashlib
import hmac
import json
from pathlib import Path
import sys
import time
from urllib.parse import urlencode

import pytest

from scidiscovery import execution_security as security
from scidiscovery.research_loop import contracts as c, controller, execution_authority as authority
from scidiscovery.research_loop import qualification as q
from scidiscovery.research_loop.instance_ui import InstanceUI
from test_formal_review import LAUNCHER
from test_history_handoff import finish


def prepare(tmp_path, *, enabled=True, launcher=None):
    public = tmp_path / 'public'; public.mkdir()
    objective = public / 'objective.md'; objective.write_text('Assess one exact declared implementation.')
    root = tmp_path / 'instance'
    controller.prepare(root, objective, public, launcher or ['fixture'],
        max_tokens=4000, max_seconds=60, max_steps=7, model='fixture', reasoning_effort='high',
        search_policy=None, experiment_mode='external', formal_review_policy={'version': 1} if enabled else None,
        execution_authority_policy={'version': 1} if enabled else None,
        source_restrictions=[dict(source=str(objective), sha256=c.digest(objective), restriction='clear')])
    secret = tmp_path / 'operator.key'; secret.write_bytes(b'operator-key-for-fixture-only----32'); secret.chmod(0o600)
    return root, secret


def test_execution_vocabulary_and_legacy_hmac_wire_bytes():
    options = [security.execution_approval_option_id('accept')]
    assert not security.decision_authorizes('scientific_review', options[0], options)
    assert not security.decision_authorizes('execution_authorization', 'pass', ['pass'])
    assert not security.decision_authorizes('execution_authorization', 'approve', ['approve'])
    assert security.decision_authorizes('execution_authorization', 'approve', ['approve'], legacy=True)
    # Existing receipts sign the caller's exact canonical bytes, without a new prefix.
    payload = b'{"request_ref":{"artifact_id":"original"},"selected_option":"authorize_execution"}'
    key = b'fixture-receipt-secret-32-bytes----'
    assert security.receipt_hmac(key, payload) == hmac.new(key, payload, hashlib.sha256).hexdigest()


def test_secret_file_refuses_symlink_and_public_permissions(tmp_path):
    key = tmp_path / 'key'; key.write_bytes(b'x' * 32); key.chmod(0o600)
    link = tmp_path / 'link'; link.symlink_to(key)
    with pytest.raises(ValueError, match='non-symlink'):
        security.read_secret_file(link, label='fixture')
    key.chmod(0o644)
    with pytest.raises(ValueError, match='0600'):
        security.read_secret_file(key, label='fixture')


def test_ordinary_science_has_no_authority_or_approval_requirement(tmp_path):
    root, secret = prepare(tmp_path, enabled=False)
    finish(root, 1, 'H', [], action='analyze')
    _, _, record = finish(root, 2, 'A', [1], text='pass, approved, authorized')
    assert c.validate(c.workspace(root, 2))['scientific_result'] == 'pass, approved, authorized'
    assert 'execution_authority' not in c.read(root / 'jobs/002.json')
    assert 'execution_qualifications' not in c.read(record / 'result-identity.json')
    with pytest.raises(ValueError, match='unavailable'):
        InstanceUI(root, secret_file=secret)


def test_loopback_host_rejects_origin_and_old_boot_without_http(tmp_path):
    root, secret = prepare(tmp_path)
    first = InstanceUI(root, secret_file=secret); first.host = '127.0.0.1:18751'
    status, _, headers = first.get('/manage?' + urlencode({'token': first.management_token}), host=first.host)
    assert status == 303 and headers['Location'] == '/'
    cookie = headers['Set-Cookie']
    assert first.get('/', host=first.host, cookie=cookie)[0] == 200
    with pytest.raises(PermissionError, match='Host'):
        first.get('/', host='attacker.invalid', cookie=cookie)
    with pytest.raises(PermissionError, match='Origin'):
        first.post('/requests/' + '0' * 64 + '/decision', host=first.host,
            origin='http://attacker.invalid', cookie=cookie,
            content_type='application/x-www-form-urlencoded', body=b'')
    restarted = InstanceUI(root, secret_file=secret); restarted.host = first.host
    with pytest.raises(PermissionError):
        restarted.get('/', host=restarted.host, cookie=cookie)
    other_key = tmp_path / 'other.key'; other_key.write_bytes(b'y' * 32); other_key.chmod(0o600)
    with pytest.raises(ValueError, match='Frozen source receipt changed'):
        InstanceUI(root, secret_file=other_key)


@pytest.mark.process_e2e
def test_exact_review_to_ui_receipt_rejects_forgery_and_never_dispatches(tmp_path, monkeypatch):
    # Reuses the real thin native/seal/review route with synthetic platform events.
    # The grant below is only an opaque authority-binding fixture: no budget owner
    # or TCAD admission is implemented/claimed in this P3c test.
    launcher = tmp_path / 'codex'; launcher.write_text('#!' + sys.executable + '\n' + LAUNCHER); launcher.chmod(0o700)
    home = tmp_path / 'native'; home.mkdir(); monkeypatch.setenv('CODEX_HOME', str(home))
    monkeypatch.delenv('REVIEW_REUSE_AUTHOR', raising=False); monkeypatch.delenv('REVIEW_MISSING_AUTHOR', raising=False)
    root, secret_file = prepare(tmp_path, launcher=[str(launcher)])
    assert controller.run(root)['status'] == 'finish'
    job, _, record = finish(root, 6, 'W', [2, 5])
    assert len(job['execution_qualifications']) == 1
    ref = job['execution_qualifications'][0]; subject = q._read(root, ref)['subject']
    ui = InstanceUI(root, secret_file=secret_file); ui.host = '127.0.0.1:18752'
    _, _, headers = ui.get('/manage?' + urlencode({'token': ui.management_token}), host=ui.host)
    cookie = headers['Set-Cookie']; browser_token = ui._browser(cookie)
    grant = q._save(root, root / 'host-runtime/fixture-grant.json', dict(fixture_only=True))
    request_ref = authority.create_request(root, step=6, native_intent=q._ref(root, record / 'native-intent.json'),
        call_id='0001-' + 'a' * 32, subject=subject, review_ref=ref, target=dict(configuration_files=[]),
        policy=dict(outcome='require_human_approval'), resources=dict(wall_time_seconds=10, max_storage_bytes=1000),
        grant_revision=grant, expires_at=time.time() + 30, secret=ui.secret)
    request_id = Path(request_ref['path']).parent.name
    tokens = authority.form_tokens(root, request_id, secret=ui.secret, boot=ui.boot, browser_token=browser_token)
    form = dict(tokens, selected_option='authorize_execution', rationale='Fixture operator decision')
    with pytest.raises(PermissionError, match='CSRF'):
        ui.post('/requests/' + request_id + '/decision', host=ui.host, origin='http://' + ui.host,
            cookie=cookie, content_type='application/x-www-form-urlencoded', body=urlencode(dict(form, csrf='forged')).encode())
    arguments = dict(host=ui.host, origin='http://' + ui.host, cookie=cookie,
        content_type='application/x-www-form-urlencoded', body=urlencode(form).encode())
    assert ui.post('/requests/' + request_id + '/decision', **arguments)[0] == 303
    original = (root / request_ref['path']).parent / 'decision.json'
    before = original.read_bytes()
    assert ui.post('/requests/' + request_id + '/decision', **arguments)[0] == 303
    assert original.read_bytes() == before
    assert authority.status(root, request_id, secret=ui.secret)['production'] == 'blocked_pending_resource_gate'
    assert not list(root.glob('**/accepted.json')) and not list(root.glob('**/submission.json'))
    with pytest.raises(ValueError, match='different content'):
        ui.post('/requests/' + request_id + '/decision', **dict(arguments,
            body=urlencode(dict(form, rationale='Changed decision content')).encode()))
    modified = json.loads(before); modified['selected_option'] = 'authorize_execution_with_exception'
    original.chmod(0o600); c.write(original, modified)
    with pytest.raises(ValueError, match='host receipt'):
        authority.decision(root, request_id, secret=ui.secret)
