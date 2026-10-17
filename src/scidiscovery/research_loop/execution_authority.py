"""Exact execution request/decision originals; no execution or budget owner.

The configured local host is trusted at the same soft boundary as prepare.
Neither model JSON nor a browser grant is an execution decision. P3d must still
reserve resources and revalidate this evidence before any backend side effect.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import hmac
import math
import os
from pathlib import Path
import re
import time

from scidiscovery import execution_security as security
from . import contracts as c, qualification as q, formal_review as review, execution

ID = re.compile(r'[0-9a-f]{64}\Z')
OPTIONS = tuple(security.execution_approval_option_id(key)
                for key in ('accept', 'accept_with_exception', 'reject', 'revise'))
SCOPE = ('Exact framework-frozen source/review/request/policy bindings only; '
         'no OS isolation, scientific verdict, resource reservation or execution permission by itself.')


def configuration(value):
    if value is not None and (value != {'version': 1} or type(value.get('version')) is not int):
        raise ValueError('Execution authority requires explicit version 1 host configuration')
    return value


def implementation():
    directory = Path(__file__).resolve().parent
    paths = [directory / name for name in ('execution_authority.py', 'instance_ui.py',
        'contracts.py', 'formal_review.py', 'qualification.py', 'execution.py')]
    paths += [directory.parent / 'execution_security.py', directory.parent / 'browser_access.py',
              directory.parent / 'operations/provenance_rules.py']
    return [q._identity(path) for path in paths]


def freeze_configuration(root):
    root = Path(root).resolve()
    return dict(version=1, contract=q._save(root, root / 'execution-authority/contract.json',
        dict(version=1, implementation=implementation(), options=list(OPTIONS), scope=SCOPE,
             stage='authority_only_production_gate_unavailable')))


def contract(root):
    policy = c.settings(root).get('execution_authority_policy')
    if policy is None:
        raise ValueError('Execution authority is unavailable for this instance')
    value = q._read(root, policy['contract'])
    if value != dict(version=1, implementation=implementation(), options=list(OPTIONS), scope=SCOPE,
                     stage='authority_only_production_gate_unavailable'):
        raise q.IntegrityError('Execution authority implementation or contract changed')
    return policy['contract']


@contextmanager
def writer(root):
    root = Path(root).resolve()
    contract(root)
    path = root / 'execution-authority'
    fd = os.open(path / 'writer.lock', os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def bind_secret(root, secret):
    """Only the explicit operator UI startup supplies this secret; never JSON."""
    security.receipt_hmac(secret, b'')
    root = Path(root).resolve()
    with writer(root):
        return q._save(root, root / 'execution-authority/host-key.json',
            dict(version=1, instance=c.settings(root)['goal_id'],
                 key_sha256=hashlib.sha256(secret).hexdigest()))


def _secret(root, secret):
    value = c.read(c.regular(Path(root) / 'execution-authority/host-key.json'))
    if (value != dict(version=1, instance=c.settings(root)['goal_id'],
                      key_sha256=hashlib.sha256(secret).hexdigest())):
        raise PermissionError('Execution authority host key differs from its original binding')
    security.receipt_hmac(secret, b'')


def _qualifications(root, job):
    candidates = []
    back = job.get('evidence_return') or {}
    if back.get('kind') == 'formal_review_return':
        candidates.append(back['review'])
    for row in job['direct_refs']:
        parent = int(row['path'].split('/')[2])
        previous = c.read(c.regular(Path(root) / 'jobs' / f'{parent:03d}.json'))
        candidates.extend(previous.get('execution_qualifications', []))
        returned = previous.get('evidence_return') or {}
        if returned.get('kind') == 'formal_review_return':
            candidates.append(returned['review'])
    result = []
    bound = [*job['direct_materials'], *[row['material'] for row in job.get('selected_inputs', [])]]
    for ref in candidates:
        proof = q._read(root, ref)
        if proof['subject']['material'] in bound and ref not in result:
            # Unqualified findings remain scientific evidence, never a grant.
            if proof['status'] == 'passed':
                review.require_review(root, proof['subject'], ref)
                result.append(ref)
    return result


def bind_job(root, job):
    if c.settings(root).get('execution_authority_policy') is not None:
        job['execution_authority'] = contract(root)
        job['execution_qualifications'] = _qualifications(root, job)


def validate_job(root, job):
    if c.settings(root).get('execution_authority_policy') is None:
        if 'execution_authority' in job or 'execution_qualifications' in job:
            raise q.IntegrityError('Task invented execution authority')
        return
    if (job.get('execution_authority') != contract(root)
            or job.get('execution_qualifications') != _qualifications(root, job)):
        raise q.IntegrityError('Task execution qualifications differ from direct frozen originals')


def _directory(root, request_id):
    if not isinstance(request_id, str) or not ID.fullmatch(request_id):
        raise ValueError('Exact execution request identity required')
    path = Path(root).resolve() / 'execution-authority/requests' / request_id
    if path.resolve() != path:
        raise q.IntegrityError('Execution request namespace changed')
    return path


def _validate_binding(root, value):
    if value['contract'] != contract(root) or value['instance'] != c.settings(root)['goal_id']:
        raise q.IntegrityError('Execution request contract or instance changed')
    job = q._read(root, value['job'])
    if value['job'] != q._ref(root, Path(root) / 'jobs' / f'{job["step"]:03d}.json'):
        raise q.IntegrityError('Execution requester is not an exact task original')
    c._validate_inputs(root, c.workspace(Path(root), job['step']), job)
    if job['role'] != 'W':
        raise ValueError('Execution requester must be an exact W task')
    intents = [q._ref(root, row / 'native-intent.json') for row in execution.records(root, job['step'])
               if (row / 'native-intent.json').exists()]
    if (value['native_intent'] not in intents
            or q._read(root, value['native_intent']).get('task_sha256') != value['job']['sha256']):
        raise q.IntegrityError('Execution native intent does not bind the exact requester')
    if value['review'] not in job.get('execution_qualifications', []):
        raise ValueError('Execution request has no directly bound formal qualification')
    subject = value['subject']
    if q._read(root, value['review'])['subject'] != subject:
        raise q.IntegrityError('Execution review names another subject')
    review.require_review(root, subject, value['review'])
    if (q.output_status(root, subject['producer_step'], subject['material'])['restriction'] != 'clear'
            or q.status(root, job)['restriction'] != 'clear'):
        raise ValueError('Execution sources are restricted or unknown')
    # Exact source path, not a same-content workspace substitute.
    if value['payload'] != q._identity(subject['material']['source']):
        raise q.IntegrityError('Execution payload is not its exact reviewed original')
    if subject['material'] not in [*job['direct_materials'], *[
            row['material'] for row in job.get('selected_inputs', [])]]:
        raise ValueError('Execution subject is not a frozen requester input')
    for item in value['target'].get('configuration_files', []):
        q._check(item)
    q._read(root, value['grant_revision'])


def create_request(root, *, step, native_intent, call_id, subject, review_ref,
                   target, policy, resources, grant_revision, expires_at, secret):
    """Trusted host seam for P3d; there is deliberately no JSON/CLI writer.

    This only freezes an authorization request. It performs no prepare, resource
    reservation or dispatch. A later gate must validate the actual policy provider,
    exact call/attempt and resource grant owner before consuming any decision.
    """
    root = Path(root).resolve()
    _secret(root, secret)
    if (not isinstance(call_id, str) or not re.fullmatch(r'[0-9]{4}-[0-9a-f]{32}', call_id)
            or not isinstance(resources, dict) or set(resources) != {'wall_time_seconds', 'max_storage_bytes'}
            or any(type(item) is not int or item <= 0 for item in resources.values())
            or type(expires_at) not in (int, float) or not math.isfinite(expires_at)
            or expires_at <= time.time()):
        raise ValueError('Explicit exact call, finite expiry and resource dimensions required')
    if not isinstance(policy, dict) or policy.get('outcome') not in {'policy', 'require_human_approval', 'deny'}:
        raise ValueError('Trusted policy admission required')
    job_path = root / 'jobs' / f'{step:03d}.json'
    value = dict(version=1, kind='execution_authorization', instance=c.settings(root)['goal_id'],
        contract=contract(root), job=q._ref(root, job_path), native_intent=native_intent,
        call_id=call_id, subject=subject, review=review_ref,
        payload=q._identity(subject['material']['source']), target=target, policy=policy,
        resources=resources, grant_revision=grant_revision, expires_at=expires_at,
        options=list(OPTIONS), scope=SCOPE)
    _validate_binding(root, value)
    request_id = hashlib.sha256(security.canonical(value)).hexdigest()
    value['nonce_hash'] = security.secret_hash(security.token(secret, 'request-nonce', request_id))
    with writer(root):
        return q._save(root, _directory(root, request_id) / 'request.json', value)


def request(root, request_id):
    root = Path(root).resolve()
    path = _directory(root, request_id) / 'request.json'
    value = q._read(root, q._ref(root, path))
    body = {key: item for key, item in value.items() if key != 'nonce_hash'}
    if hashlib.sha256(security.canonical(body)).hexdigest() != request_id:
        raise q.IntegrityError('Execution request identity changed')
    _validate_binding(root, value)
    return value, q._ref(root, path)


def form_tokens(root, request_id, *, secret, boot, browser_token):
    _secret(root, secret)
    value, ref = request(root, request_id)
    nonce = security.token(secret, 'request-nonce', request_id)
    if not hmac.compare_digest(value['nonce_hash'], security.secret_hash(nonce)):
        raise q.IntegrityError('Execution nonce differs from its host original')
    csrf = security.token(secret, 'csrf', ref, boot, security.secret_hash(browser_token))
    return dict(nonce=nonce, csrf=csrf)


def record_decision(root, request_id, *, secret, boot, browser_token, nonce, csrf,
                    selected_option, rationale, actor='local_operator'):
    """Called only by the authenticated UI route, never by a model operation."""
    root = Path(root).resolve()
    tokens = form_tokens(root, request_id, secret=secret, boot=boot, browser_token=browser_token)
    if not all(isinstance(value, str) for value in (nonce, csrf, selected_option, rationale, actor)):
        raise ValueError('Invalid decision form')
    if not hmac.compare_digest(tokens['nonce'], nonce) or not hmac.compare_digest(tokens['csrf'], csrf):
        raise PermissionError('Execution decision CSRF or nonce mismatch')
    if selected_option not in OPTIONS or not rationale.strip() or actor != 'local_operator':
        raise ValueError('Registered execution option and operator rationale required')
    with writer(root):
        value, ref = request(root, request_id)
        path = _directory(root, request_id) / 'decision.json'
        semantic = dict(request=ref, selected_option=selected_option, rationale=rationale,
                        actor=actor, nonce_hash=value['nonce_hash'])
        if path.exists():
            prior = decision(root, request_id, secret=secret)
            if any(prior[key] != item for key, item in semantic.items()):
                raise ValueError('Decision nonce was already used with different content')
            return q._ref(root, path)
        if time.time() >= value['expires_at']:
            raise ValueError('Execution request has expired')
        if (_directory(root, request_id) / 'revocation.json').exists():
            raise ValueError('Execution request has been revoked')
        if (value['policy']['outcome'] == 'deny' and security.decision_authorizes(
                value['kind'], selected_option, value['options'])):
            raise ValueError('A denied policy cannot be overridden by an execution decision')
        body = dict(version=1, kind='human', **semantic, ui_boot=boot,
                    csrf_hash=security.secret_hash(csrf), decided_at=time.time(),
                    implementation=implementation())
        # An exception option is not a resource grant; P3d must separately amend.
        body['receipt_hmac'] = security.receipt_hmac(secret, security.canonical(body))
        return q._save(root, path, body)


def record_policy_decision(root, request_id, *, secret):
    """Trusted provider consumer seam; no public operation accepts policy JSON."""
    _secret(root, secret)
    with writer(root):
        value, ref = request(root, request_id)
        if value['policy']['outcome'] != 'policy' or time.time() >= value['expires_at']:
            raise ValueError('Exact request is not eligible for current policy authorization')
        if (_directory(root, request_id) / 'revocation.json').exists():
            raise ValueError('Execution request has been revoked')
        path = _directory(root, request_id) / 'decision.json'
        if path.exists():
            prior = decision(root, request_id, secret=secret)
            if prior['kind'] != 'policy':
                raise ValueError('Exact execution request already has another decision')
            return q._ref(root, path)
        body = dict(version=1, kind='policy', request=ref, nonce_hash=value['nonce_hash'],
                    selected_option=security.execution_approval_option_id('accept'),
                    actor='configured_policy', rationale='Exact frozen policy admission',
                    implementation=implementation())
        body['receipt_hmac'] = security.receipt_hmac(secret, security.canonical(body))
        return q._save(root, path, body)


def decision(root, request_id, *, secret):
    _secret(root, secret)
    value, ref = request(root, request_id)
    path = _directory(root, request_id) / 'decision.json'
    if not path.exists():
        return None
    document = c.read(c.regular(path))
    body = {key: item for key, item in document.items() if key != 'receipt_hmac'}
    if (body.get('request') != ref or body.get('nonce_hash') != value['nonce_hash']
            or body.get('kind') not in {'human', 'policy'}
            or body.get('implementation') != implementation()
            or body.get('selected_option') not in value['options']
            or not hmac.compare_digest(document.get('receipt_hmac', ''),
                    security.receipt_hmac(secret, security.canonical(body)))):
        raise q.IntegrityError('Execution decision does not match its host receipt')
    return document


def _revoked(root, request_id, secret):
    path = _directory(root, request_id) / 'revocation.json'
    if not path.exists():
        return False
    document = c.read(c.regular(path))
    body = {key: item for key, item in document.items() if key != 'receipt_hmac'}
    _, ref = request(root, request_id)
    if (body.get('request') != ref or body.get('kind') != 'revocation'
            or not hmac.compare_digest(document.get('receipt_hmac', ''),
                    security.receipt_hmac(secret, security.canonical(body)))):
        raise q.IntegrityError('Execution revocation does not match its host receipt')
    return True


def status(root, request_id, *, secret):
    value, ref = request(root, request_id)
    decided = decision(root, request_id, secret=secret)
    revoked = _revoked(root, request_id, secret)
    return dict(request=ref, state='revoked' if revoked else 'expired' if time.time() >= value['expires_at']
        else 'decided' if decided is not None else 'pending',
        selected_option=decided['selected_option'] if decided else None,
        production='blocked_pending_resource_gate', scope=SCOPE)


def revoke(root, request_id, *, secret, reason):
    """Trusted UI owner; revocation never cancels or refunds an execution."""
    _secret(root, secret)
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError('Revocation requires an operator reason')
    with writer(root):
        _, ref = request(root, request_id)
        body = dict(version=1, request=ref, reason=reason, kind='revocation')
        body['receipt_hmac'] = security.receipt_hmac(secret, security.canonical(body))
        return q._save(root, _directory(root, request_id) / 'revocation.json', body)
