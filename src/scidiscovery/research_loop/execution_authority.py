"""Exact execution decisions and trusted gate; budget remains the ledger owner.

The configured local host is trusted at the same soft boundary as prepare.
Neither model JSON nor browser access is an execution decision. The trusted gate
reserves resources and revalidates originals before a backend side effect.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import hmac
import inspect
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
        'contracts.py', 'formal_review.py', 'qualification.py', 'execution.py', 'budget.py', 'experiments.py',
        'runtime.py', 'native.py', 'search.py', 'execution_inputs.py')]
    paths += [directory / 'instance_control.py']
    from . import instance_owner
    paths += [Path(instance_owner.__file__).resolve()]
    from .execution_resume import capture_pending, verify_pending_set, resume
    from .execution_recovery import call_view
    from .history import validate_managed
    paths += [Path(inspect.getfile(function)).resolve() for function in
              (capture_pending, verify_pending_set, resume, call_view, validate_managed)]
    paths += [directory.parent / 'execution_security.py', directory.parent / 'browser_access.py',
              directory.parent / 'operations/provenance_rules.py', directory.parent / 'operations/runtime_plugins.py',
              directory.parent / 'plugin_runtime/collection.py']
    return [q._identity(path) for path in dict.fromkeys(paths)]


def freeze_configuration(root):
    root = Path(root).resolve()
    return dict(version=1, contract=q._save(root, root / 'execution-authority/contract.json',
        dict(version=1, implementation=implementation(), options=list(OPTIONS), scope=SCOPE,
             stage='decision_originals_resource_gate_separate')))


def contract(root):
    policy = c.settings(root).get('execution_authority_policy')
    if policy is None:
        raise ValueError('Execution authority is unavailable for this instance')
    value = q._read(root, policy['contract'])
    if value != dict(version=1, implementation=implementation(), options=list(OPTIONS), scope=SCOPE,
                     stage='decision_originals_resource_gate_separate'):
        raise q.IntegrityError('Execution authority implementation or contract changed')
    return policy['contract']


@contextmanager
def writer(root, *, context=None, blocking=True):
    from . import instance_owner
    root = Path(root).resolve()
    with instance_owner.lease(root):
        contract(root)
        path = root / 'execution-authority'
        fd = os.open(path / 'writer.lock', os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
        try:
            if context is None and blocking:
                fcntl.flock(fd, fcntl.LOCK_EX)
            else:
                while True:
                    if context is not None:context.remaining_seconds()
                    try:
                        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                    except BlockingIOError:
                        if not blocking:raise
                        time.sleep(min(.05,context.remaining_seconds()))
            yield
        finally:
            os.close(fd)


def bind_secret(root, secret, *, source=None):
    """Only the explicit operator UI startup supplies this secret; never JSON."""
    security.receipt_hmac(secret, b'')
    root = Path(root).resolve()
    with writer(root):
        ref = q._save(root, root / 'execution-authority/host-key.json',
            dict(version=1, instance=c.settings(root)['goal_id'],
                 key_sha256=hashlib.sha256(secret).hexdigest()))
        if source is not None:
            identity = q._identity(Path(source).expanduser().absolute())
            if identity['sha256'] != hashlib.sha256(secret).hexdigest():
                raise q.IntegrityError('Host key locator does not identify the configured key')
            locator = dict(version=1, source=identity, key=ref)
            locator['receipt_hmac'] = security.receipt_hmac(secret, security.canonical(locator))
            q._save(root, root / 'execution-authority/host-key-source.json', locator)
        return ref


def host_secret(root):
    """Read the explicit operator locator, never a Worker configuration path."""
    root = Path(root).resolve()
    locator = c.read(c.regular(root / 'execution-authority/host-key-source.json'))
    q._check(locator['source'])
    secret = security.read_secret_file(locator['source']['path'], label='approval receipt')
    _secret(root, secret)
    body = {key: value for key, value in locator.items() if key != 'receipt_hmac'}
    if (locator['key'] != q._ref(root, root / 'execution-authority/host-key.json')
            or not hmac.compare_digest(locator.get('receipt_hmac', ''),
                                      security.receipt_hmac(secret, security.canonical(body)))):
        raise q.IntegrityError('Host key locator differs from its operator original')
    return secret


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
    alias = value.get('payload_alias', value['payload'])
    allowed = {str(Path(subject['material']['source'])), str(c.workspace(root, job['step']) / subject['material']['path'])}
    if (alias['path'] not in allowed or alias != q._identity(alias['path'])
            or any(alias[key] != value['payload'][key] for key in ('sha256', 'size_bytes'))):
        raise q.IntegrityError('Execution payload alias is not an explicitly bound read copy')
    if subject['material'] not in [*job['direct_materials'], *[
            row['material'] for row in job.get('selected_inputs', [])]]:
        raise ValueError('Execution subject is not a frozen requester input')
    for item in value['target'].get('configuration_files', []):
        q._check(item)
    q._read(root, value['grant_revision'])


def create_request(root, *, step, native_intent, call_id, subject, review_ref,
                   target, policy, resources, grant_revision, expires_at, secret, payload_alias=None, supersedes=None, operation_context=None):
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
    if payload_alias is not None:
        value['payload_alias'] = payload_alias
    if supersedes is not None:
        old=q._read(root,supersedes)
        for key in ('job','native_intent','call_id','subject','review','payload','payload_alias','target','resources'):
            if old.get(key)!=value.get(key):raise q.IntegrityError('Renewal changed the original execution subject')
        value['supersedes']=supersedes
    _validate_binding(root, value)
    request_id = hashlib.sha256(security.canonical(value)).hexdigest()
    value['nonce_hash'] = security.secret_hash(security.token(secret, 'request-nonce', request_id))
    with writer(root,context=operation_context):
        ref=q._save(root, _directory(root, request_id) / 'request.json', value)
        if supersedes is not None:
            q._save(root,(Path(root)/supersedes['path']).parent/'successor.json',dict(previous=supersedes,successor=ref))
        return ref


def request(root, request_id):
    root = Path(root).resolve()
    path = _directory(root, request_id) / 'request.json'
    value = q._read(root, q._ref(root, path))
    body = {key: item for key, item in value.items() if key != 'nonce_hash'}
    if hashlib.sha256(security.canonical(body)).hexdigest() != request_id:
        raise q.IntegrityError('Execution request identity changed')
    _validate_binding(root, value)
    return value, q._ref(root, path)


def request_successor(root,ref):
    path=(Path(root)/ref['path']).parent/'successor.json'
    if not path.exists():return None
    value=q._read(root,q._ref(root,path));next_ref=value['successor']
    old=q._read(root,ref);new,actual=request(root,Path(next_ref['path']).parent.name)
    if value['previous']!=ref or new.get('supersedes')!=ref or actual!=next_ref:
        raise q.IntegrityError('Execution request successor changed its explicit chain')
    for key in ('job','native_intent','call_id','subject','review','payload','payload_alias','target','resources'):
        if old.get(key)!=new.get(key):raise q.IntegrityError('Execution request successor changed its original subject')
    return next_ref


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


def record_policy_decision(root, request_id, *, secret, operation_context=None):
    """Trusted provider consumer seam; no public operation accepts policy JSON."""
    _secret(root, secret)
    with writer(root,context=operation_context):
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
        production='trusted_resource_gate_required' if c.settings(root).get('execution_resource_policy') else 'blocked_pending_resource_gate', scope=SCOPE)


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


class AuthorityRequired(ValueError):
    def __init__(self, feedback):
        super().__init__(feedback['note'])
        self.feedback = feedback


def _host_context(config):
    """Resolve only the existing canonical host projection and accepted task."""
    directory = Path(config['record_dir'])
    if len(directory.parents) < 5:
        raise q.IntegrityError('Trusted execution record namespace is unavailable')
    root = directory.parents[4]
    step = config['scope']['step']; job = c.read(c.regular(root / 'jobs' / f'{step:03d}.json'))
    from .protocol import stage_scope
    if (Path(config['record_dir']) != root / 'project/nodes' / f'{step:03d}' / 'work/lineage'
            or Path(config['record_dir']).resolve() != Path(config['record_dir'])
            or job['role'] != 'W' or config['scope'] != stage_scope(root, job)
            or config.get('host_execution_authority') != contract(root)
            or c.settings(root).get('execution_resource_policy') is None):
        raise q.IntegrityError('Trusted execution services have no exact host task')
    selected = c.settings(root)['execution_config']
    if (config.get('registered_implementation') != selected['implementation']
            or config['execution_interface']['executor'] != selected['executor']
            or any(config.get(key) != value for key, value in selected['configuration'].items())):
        raise q.IntegrityError('Trusted execution services differ from operator configuration')
    attempt = config['native_attempt']['number']
    record = execution.record(root, step, attempt)
    intent = q._ref(root, record / 'native-intent.json')
    if q._read(root, intent).get('task_sha256') != config['scope']['job_sha256']:
        raise q.IntegrityError('Trusted execution services lost their native intent')
    original = root / 'host-runtime/experiment-control' / config['scope']['job_sha256'] / 'interfaces' / f'{attempt:03d}.json'
    if original.exists():
        body = {key: value for key, value in config.items() if key != 'execution_interface'}
        frozen = c.read(c.regular(original))
        if body != {key: value for key, value in frozen.items() if key != 'execution_interface'}:
            raise q.IntegrityError('Trusted execution services differ from their original projection')
    elif config['execution_interface'].get('version') is not None:
        raise q.IntegrityError('Original trusted execution projection is missing')
    return root, job, intent


def _selected_subject(root, job, payload):
    alias = q._identity(payload.local_path)
    if (alias['sha256'], alias['size_bytes']) != (payload.sha256, payload.size_bytes):
        raise q.IntegrityError('Execution payload bytes changed')
    found = []
    for ref in job.get('execution_qualifications', []):
        subject = q._read(root, ref)['subject']; material = subject['material']
        if alias['path'] in {material['source'], str(c.workspace(root, job['step']) / material['path'])}:
            found.append((subject, ref))
    if len(found) != 1:
        raise ValueError('Select one exact frozen material with an explicit independent review; work files and same hashes do not qualify')
    subject, ref = found[0]
    review.require_review(root, subject, ref)
    if q.output_status(root, subject['producer_step'], subject['material'])['restriction'] != 'clear' or q.status(root, job)['restriction'] != 'clear':
        raise ValueError('Execution source restrictions are unknown or restricted')
    return subject, ref, alias


def _remaining(root, config, allocation=None):
    """The one new-dispatch check; original maintenance never enters here."""
    from . import budget, experiments as e, runtime, native, search
    step = config['scope']['step']; attempt = config['native_attempt']['number']
    record = execution.record(root, step, attempt)
    if (execution.record(root, step) != record
            or (c.host_record(c.workspace(root, step)) / 'result-identity.json').exists()
            or (record / 'native-outcome.json').exists() or (record / 'stage-end.json').exists()):
        raise ValueError('Original native attempt has ended; sealed/old-attempt dispatch requires the separate recovery contract')
    process_binding = execution.identity(root, step, attempt)
    if not all(runtime.process_matches(c.read(c.regular(record / name)), process_binding)
               for name in ('runner-process.json', 'native-process.json')):
        raise ValueError('Original native attempt is not verifiably active')
    stamp = budget.clock_stamp()
    limits = budget.snapshot(root, sample_stamp=stamp)
    job = c.read(c.regular(root / 'jobs' / f'{step:03d}.json'))
    intent = c.read(c.regular(record / 'native-intent.json'))
    usage = native.usage(root)
    available = budget.execution_available(root, job, limits, usage)
    if any(item != step for item in usage['unknown_steps']) or available['tokens'] <= 0:
        raise ValueError('Original shared token authorization is exhausted or unknown')
    meter = c.read(c.regular(record / 'usage.json')) if (record / 'usage.json').exists() else dict(input_tokens=0, output_tokens=0)
    reason = budget.stop_node(root, job, intent, limits, meter) or search.stop_reason(root, job, intent, limits, meter)
    if reason:
        raise ValueError('Original native authorization has expired: ' + reason)
    state = e.review_status(config)
    if state['requested']:
        raise ValueError('Original task admission is unavailable: ' + str(state['reason']))
    seconds = available['seconds']
    if budget.node_mode(root) == 'hard':
        node = budget.node_limits(root, job)
        if node is not None:
            seconds = min(seconds, node['max_seconds'] - budget._node_duration(root, job, intent, limits))
        if job.get('search') is not None:
            seconds = min(seconds, job['search']['limits']['max_w_seconds'] -
                          (limits['advance_seconds'] - intent['search_slice']['advance_seconds']))
    if allocation is not None:
        if stamp['boot_id'] != allocation['boot_id']:
            raise ValueError('Original execution authorization belongs to another boot')
        if allocation['scientific_authorization'] != budget.authorization_revision(root):
            raise ValueError('Original scientific authorization ceiling revision changed')
        seconds = min(seconds, allocation['dispatch_deadline_boottime'] - stamp['at_boottime'])
    if seconds <= 0:
        raise ValueError('Original execution authorization has no remaining time')
    return stamp, seconds


def _allocate_call(config, payload, ordinal, mechanism=None):
    from . import budget, native, breadth, experiments as e
    root, job, intent = _host_context(config)
    subject, ref, alias = _selected_subject(root, job, payload)
    body = dict(scope=config['scope'], native_attempt=config['native_attempt'], interface=config['execution_interface'],
                subject=subject, review=ref, payload_alias=alias, ordinal=ordinal)
    mechanism_binding = breadth.admit(config.get('breadth'), mechanism, config['scope'],
        [e.Records(config).accepted(path.name) for path in e.Records(config).calls()])
    body['mechanism_binding'] = mechanism_binding
    call = f'{ordinal:04d}-' + hashlib.sha256(security.canonical(body)).hexdigest()[:32]
    path = root / 'execution-authority/calls' / call / 'allocation.json'
    with writer(root):
        if path.exists():
            original = c.read(c.regular(path))
            if original['binding'] != body:
                raise q.IntegrityError('Pending execution call allocation changed')
            if (path.parent / 'prepare-intent.json').exists():
                raise ValueError('Original preparation may have started; pre-accept recovery/release is unsupported, preserve its reservation')
            _remaining(root, config, original)
        else:
            stamp, seconds = _remaining(root, config)
            if config['admission']['mode'] == 'soft':
                projection = c.read(c.regular(Path(config['admission']['directory']) / 'review.json'))
                seconds = min(seconds, projection['deadline_boottime'] - stamp['at_boottime'])
            if seconds <= 0:
                raise ValueError('Original native deadline has expired')
            q._save(root, path, dict(version=1, call_id=call, binding=body, native_intent=intent,
                boot_id=stamp['boot_id'], dispatch_deadline_boottime=stamp['at_boottime'] + seconds,
                job_deadline_boottime=stamp['at_boottime'] + budget.execution_available(root, job,
                    budget.snapshot(root, sample_stamp=stamp), native.usage(root))['seconds'],
                scientific_authorization=budget.authorization_revision(root),
                expires_at=stamp['at_unix'] + seconds))
    return call


def review_url(root, request_id, secret):
    """Only an actually held UI host lock makes the token-free URL usable."""
    path = Path(root) / 'execution-authority/ui-endpoint.json'
    if not path.exists():
        return None
    value = c.read(c.regular(path)); body = {key: item for key, item in value.items() if key != 'receipt_hmac'}
    if (value.get('instance') != c.settings(root)['goal_id'] or not hmac.compare_digest(
            value.get('receipt_hmac', ''), security.receipt_hmac(secret, security.canonical(body)))):
        raise q.IntegrityError('UI endpoint differs from the host original')
    try:
        fd = os.open(Path(root) / 'execution-authority/ui.lock', os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except FileNotFoundError:
        return None
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return None
        except BlockingIOError:
            return value['origin'] + '/requests/' + request_id
    finally:
        os.close(fd)


def _permit(root, ref, config, target, call, payload, secret):
    q._check(ref); value = c.read(Path(ref['path']))
    body = {key: item for key, item in value.items() if key != 'receipt_hmac'}
    if (value.get('scope') != config['scope'] or value.get('native_attempt') != config['native_attempt']
            or value.get('interface') != config['execution_interface'] or value.get('target') != target
            or value.get('call_id') != call or payload is not None and value.get('payload_alias') != dict(path=payload.local_path,
                sha256=payload.sha256, size_bytes=payload.size_bytes)
            or not hmac.compare_digest(value.get('receipt_hmac', ''),
                                      security.receipt_hmac(secret, security.canonical(body)))):
        raise q.IntegrityError('Original execution permit differs from its exact call or host receipt')
    return value


def _accepted_input_subject(root, job, accepted, secret):
    """Exact historical relations, without current review/source/clock gates."""
    root = Path(root).resolve()
    ref = accepted.get('execution_authority')
    if ref is None:
        return None
    attempt = accepted.get('native_attempt') or {}
    number = attempt.get('number')
    if type(number) is not int or number < 0:
        raise q.IntegrityError('Managed source has no exact native attempt')
    config = c.read(c.regular(execution.record(root, job['step'], number) / 'experiment-config.json'))
    q._check(ref); authorization = c.read(Path(ref['path']))
    request_ref = authorization['request']; request_value = q._read(root, request_ref)
    request_id = Path(request_ref['path']).parent.name
    directory = _directory(root, request_id)
    body = {key:value for key,value in request_value.items() if key != 'nonce_hash'}
    if (request_ref != q._ref(root, directory / 'request.json')
            or Path(ref['path']) != directory / 'authorization.json'
            or hashlib.sha256(security.canonical(body)).hexdigest() != request_id):
        raise q.IntegrityError('Managed source request original changed')
    allocation_ref = authorization['allocation']; allocation = q._read(root, allocation_ref)
    decision_ref = authorization['decision']; decided = q._read(root, decision_ref)
    call = accepted['call_id']; target = accepted.get('execution_target')
    binding = allocation['binding']; subject = request_value['subject']
    alias = request_value.get('payload_alias', request_value['payload'])
    if (config.get('scope') != accepted['scope'] or config.get('native_attempt') != attempt
            or config.get('execution_interface') != accepted['interface']
            or accepted['scope']['job_sha256'] != c.digest(root / 'jobs' / f'{job["step"]:03d}.json')
            or request_value['job'] != q._ref(root, root / 'jobs' / f'{job["step"]:03d}.json')
            or allocation_ref != q._ref(root, root / 'execution-authority/calls' / call / 'allocation.json')
            or allocation['call_id'] != call or binding['scope'] != accepted['scope']
            or binding['native_attempt'] != attempt or binding['interface'] != accepted['interface']
            or binding['subject'] != subject or binding['review'] != request_value['review']
            or binding['payload_alias'] != alias or request_value['call_id'] != call
            or authorization['scope'] != accepted['scope'] or authorization['native_attempt'] != attempt
            or authorization['interface'] != accepted['interface'] or authorization['call_id'] != call
            or authorization['target'] != target or request_value['target'] != target
            or authorization['payload_alias'] != alias
            or allocation['native_intent'] != request_value['native_intent']
            or request_value['native_intent'] != q._ref(root, execution.record(root, job['step'], number) / 'native-intent.json')
            or q._read(root, request_value['native_intent'])['task_sha256'] != request_value['job']['sha256']
            or decision_ref != q._ref(root, directory / 'decision.json')
            or decided['request'] != request_ref or decided['nonce_hash'] != request_value['nonce_hash']
            or not security.decision_authorizes(request_value['kind'], decided['selected_option'], request_value['options'])):
        raise q.IntegrityError('Managed source differs from its exact authorized call')
    if secret is not None:
        for signed in (authorization, decided):
            signed_body = {key:value for key,value in signed.items() if key != 'receipt_hmac'}
            if not hmac.compare_digest(signed.get('receipt_hmac', ''), security.receipt_hmac(secret, security.canonical(signed_body))):
                raise q.IntegrityError('Managed source host signature changed')
    seal = q._read(root, subject['producer_seal']); material = subject['material']
    if (subject['producer_seal'] != q._ref(root, c.host_record(c.workspace(root, subject['producer_step'])) / 'result-identity.json')
            or material not in seal['materials'] or request_value['payload'] != q._identity(material['source'])
            or alias['path'] not in {material['source'], str(c.workspace(root, job['step']) / material['path'])}
            or alias != q._identity(alias['path'])
            or any(alias[key] != request_value['payload'][key] for key in ('sha256','size_bytes'))):
        raise q.IntegrityError('Managed source payload or exact producer changed')
    prepared = accepted['prepared']; script = accepted['script']
    q._check(script)
    q._check(dict(path=prepared['local_path'], sha256=prepared['sha256'], size_bytes=prepared['size_bytes']))
    if any(script[key] != prepared[key] for key in ('sha256','size_bytes')):
        raise q.IntegrityError('Managed source prepared bytes differ from accepted original')
    return dict(subject=subject, authority=q._ref(root, Path(ref['path'])), request=request_ref,
                decision=decision_ref, allocation=allocation_ref)


def accepted_input_subject(root, job, accepted):
    """First publication checks the original host signatures; no new admission."""
    if (accepted.get('execution_authority') is None
            or not (Path(root) / 'execution-authority/host-key-source.json').exists()):
        return None
    return _accepted_input_subject(root, job, accepted, host_secret(root))


def validate_accepted_input_subject(root, job, accepted, published):
    """Read only an already sealed binding; no key, promotion or re-signing."""
    if _accepted_input_subject(root, job, accepted, None) != published:
        raise q.IntegrityError('Sealed managed source authority binding changed')


def _gate(config, provider, phase, *, scope, call_id, payload, target, prepared=None, prior_receipt=None, recovery=None):
    from . import budget
    from scidiscovery.artifact_agent.schema.execution import ExecutionAdmission
    from scidiscovery.plugin_runtime.collection import CollectionContext
    root, job, intent = _host_context(config)
    if not (root / 'execution-authority/host-key-source.json').exists():
        raise ValueError('Trusted execution host key is not configured; explicitly start this instance serve-ui first')
    secret = host_secret(root)
    if scope != config['scope']:
        raise q.IntegrityError('Execution gate escaped its accepted scope')
    allocation_path = root / 'execution-authority/calls' / call_id / 'allocation.json'
    allocation = q._read(root, q._ref(root, allocation_path))
    remaining = (lambda: _remaining(root,config,allocation)) if recovery is None else recovery.check
    if (allocation['call_id'] != call_id or allocation['binding']['scope'] != scope
            or allocation['binding']['native_attempt'] != config['native_attempt']
            or allocation['binding']['interface'] != config['execution_interface']
            or allocation['native_intent'] != intent):
        raise q.IntegrityError('Execution allocation differs from its original task or implementation')
    if prior_receipt is not None:
        original = _permit(root, prior_receipt, config, target, call_id, payload, secret)
        if phase in {'cancel', 'retire'}:
            # Existing adapters bound these maintenance RPCs; no new solver grant,
            # source qualification, clock snapshot or resource amendment is issued.
            return dict(receipt=prior_receipt)
        if phase == 'collect':
            if recovery is not None:
                return dict(receipt=prior_receipt,context=recovery.collection(original))
            stamp = budget.clock_stamp()
            if stamp['boot_id'] != allocation['boot_id']:
                raise ValueError('Original collection deadline is unverifiable across boot')
            runner = original['admission']['policy']['runner']
            window_path = allocation_path.parent / 'collection-window.json'
            with writer(root):
                if window_path.exists():
                    window = c.read(c.regular(window_path))
                else:
                    window = dict(boot_id=allocation['boot_id'], deadline_boottime=min(allocation['job_deadline_boottime'],
                        stamp['at_boottime'] + runner['collection_total_seconds']), authority=prior_receipt)
                    q._save(root, window_path, window)
            if window['boot_id'] != stamp['boot_id'] or window['authority'] != prior_receipt:
                raise q.IntegrityError('Original collection window changed')
            remaining = min(window['deadline_boottime'] - stamp['at_boottime'], budget.snapshot(root)['seconds_remaining'])
            if remaining <= 0:
                raise ValueError('Original collection authority has no remaining time')
            end = time.monotonic() + remaining
            context = CollectionContext(end - min(2., remaining * .1), end,
                file_timeout_seconds=min(remaining, runner['collection_file_seconds']),
                idle_timeout_seconds=min(remaining, runner['collection_idle_seconds']),
                stopped=lambda: budget.clock_stamp()['boot_id'] != allocation['boot_id'] or
                    budget.clock_stamp()['at_boottime'] >= window['deadline_boottime'])
            return dict(receipt=prior_receipt, context=context)
    elif phase != 'prepare':
        raise ValueError('An original execution permit is required')
    if phase not in {'prepare', 'submit'}:
        raise ValueError('Unknown trusted execution gate phase')
    subject, review_ref, alias = _selected_subject(root, job, payload)
    if (allocation['binding']['subject'] != subject or allocation['binding']['review'] != review_ref
            or allocation['binding']['payload_alias'] != alias):
        raise q.IntegrityError('Execution allocation changed its selected input')
    remaining()
    # Only now may the installed trusted factory provider query active capability/policy.
    admission = provider(c.regular(Path(payload.local_path)).read_bytes())
    if not isinstance(admission, ExecutionAdmission):
        raise ValueError('Trusted policy provider returned no execution admission')
    stamp, _ = remaining()
    grant = budget.execution_grant(root,operation_context=recovery.context if recovery is not None else None)
    admission = admission.model_copy(update={'budget_key': grant['owner']['key']})
    from . import native
    job_remaining = (min(allocation['job_deadline_boottime'] - stamp['at_boottime'],
        budget.execution_available(root, job, budget.snapshot(root), native.usage(root))['seconds'])
        if recovery is None else recovery.job_remaining())
    if (hashlib.sha256(security.canonical(admission.policy)).hexdigest() != admission.policy_digest
            or admission.budget.get('wall_time_seconds', float('inf')) > job_remaining):
        raise ValueError('Policy identity or requested job runtime exceeds the original shared authorization')
    if admission.outcome == 'deny':
        raise ValueError('Current administrator execution policy denies the exact request')
    if phase == 'submit':
        if original['admission'] != admission.model_dump(mode='json') or original['grant_revision'] != grant['ref']:
            raise ValueError('Current policy or resource grant revision differs from the prepared authorization')
        request_ref = original['request']
    else:
        request_ref = recovery.request(admission,target) if recovery is not None else create_request(root, step=job['step'], native_intent=intent, call_id=call_id,
            subject=subject, review_ref=review_ref, payload_alias=alias, target=target,
            policy=admission.model_dump(mode='json'), resources=dict(admission.budget),
            grant_revision=grant['ref'], expires_at=allocation['expires_at'], secret=secret)
    request_id = Path(request_ref['path']).parent.name
    if admission.outcome == 'policy':
        record_policy_decision(root, request_id, secret=secret,operation_context=recovery.context if recovery is not None else None)
    current = status(root, request_id, secret=secret)
    if current['state'] != 'decided' or not security.decision_authorizes('execution_authorization',
            current['selected_option'], OPTIONS):
        raise AuthorityRequired(dict(status='authorization_required', call_id=call_id,
            authorization_request=request_ref, review_url=review_url(root, request_id, secret),
            note='Exact execution decision required; preserve this payload and retry only within the original task authorization. This check did not prepare or reserve resources.'))
    with writer(root,context=recovery.context if recovery is not None else None):
        if _revoked(root, request_id, secret) or time.time() >= q._read(root,request_ref)['expires_at']:
            raise ValueError('Original execution decision has expired or been revoked')
        authorization = dict(version=1, scope=config['scope'], native_attempt=config['native_attempt'],
            interface=config['execution_interface'], call_id=call_id, request=request_ref,
            decision=q._ref(root, _directory(root, request_id) / 'decision.json'),
            allocation=q._ref(root, allocation_path), target=target, payload_alias=alias,
            grant_revision=grant['ref'], owner=grant['owner'], admission=admission.model_dump(mode='json'))
        authorization['receipt_hmac'] = security.receipt_hmac(secret, security.canonical(authorization))
        authority_ref = q._save(root, _directory(root, request_id) / 'authorization.json', authorization)
        receipt = {**authority_ref, 'path': str(root / authority_ref['path'])}
        if prior_receipt is not None and receipt != prior_receipt:
            raise ValueError('Execution policy or resource authorization changed; original permit cannot submit')
        binding = dict(call_id=call_id, scope=config['scope'], native_attempt=config['native_attempt'],
                       interface=config['execution_interface'], authority=receipt)
        reservation = budget.reserve_execution(root, binding=binding, request_ref=request_ref,
            decision_ref=authorization['decision'], budget=dict(admission.budget), grant_revision=grant['ref'],
            effective_allowance=dict(admission.allowance),
            **(dict(unprepared_recovery=recovery.proof,operation_context=recovery.context) if recovery is not None else {}))
        remaining()
        if phase == 'prepare':
            if recovery is not None:recovery.begin(request_ref,authorization['decision'])
            prepare_intent = allocation_path.parent / 'prepare-intent.json'
            if prepare_intent.exists():
                raise ValueError('Original preparation may have started; preserve its reservation without replay')
            q._save(root, prepare_intent, dict(call_id=call_id, authority=receipt, reservation=reservation,
                note='Preparation may follow this original; absence of accepted is not proof of no side effect'))
        if phase == 'submit':
            accepted = q._ref(root, Path(config['record_dir']) / 'calls' / call_id / 'accepted.json')
            budget.bind_execution(root, reservation=reservation, accepted=accepted, prepared=prepared.model_dump(mode='json'),
                                  operation_context=recovery.context if recovery is not None else None)
            stamp, _ = remaining()
            seconds=(min(allocation['job_deadline_boottime'] - stamp['at_boottime'],
                    budget.execution_available(root, job, budget.snapshot(root), native.usage(root))['seconds'])
                    if recovery is None else recovery.job_remaining())
            if admission.budget['wall_time_seconds'] > seconds:
                raise ValueError('Preparation consumed the remaining authorization; original submission remains blocked')
    return dict(receipt=receipt, authorization=admission, reservation=reservation)


def host_services(config):
    """The only non-JSON factory injection, after exact host verification."""
    if config.get('host_execution_authority') is None:
        return None
    from scidiscovery.operations.runtime_plugins import ExecutionHostServices
    from .execution_inputs import NativeInputHost
    return ExecutionHostServices(gate=lambda provider: lambda phase, **kwargs: _gate(config, provider, phase, **kwargs),
                                 call_identity=lambda payload, ordinal, mechanism=None: _allocate_call(config, payload, ordinal, mechanism),
                                 implementation_inputs=NativeInputHost(config))


def reconcile_resources(config, adapter, call_id, *, observation=None, operation_context=None):
    """Consume verified original execution facts; accounting never rewrites science.

    An unreadable/cross-boot ledger keeps the reservation. In particular a
    permanent native fence can still be retained independently of budget IO.
    """
    if config.get('host_execution_authority') is None:
        return None
    root = Path(config['record_dir']).parents[4]
    try:
        from . import budget, experiments as e
        root, _, _ = _host_context(config)
        directory = Path(config['record_dir']) / 'calls' / call_id
        accepted_ref = q._ref(root, directory / 'accepted.json'); accepted = q._read(root, accepted_ref)
        reservation = accepted.get('execution_reservation')
        if reservation is None:
            raise ValueError('Original execution has no bound resource reservation')
        _permit(root, accepted['execution_authority'], config, accepted['execution_target'], call_id, None, host_secret(root))
        budget.bind_execution(root, reservation=reservation, accepted=accepted_ref, prepared=accepted['prepared'],operation_context=operation_context)
        if (directory / 'submission-retirement.json').exists():
            # P2d's single validator and its immutable accepted/prepared/authority
            # binding are rechecked by the unique budget owner before release.
            budget.release_execution(root, reservation=reservation,
                retirement=q._ref(root, directory / 'submission-retirement.json'))
            return dict(state='released_permanent_not_submitted', reservation=reservation)
        if observation is None:
            return dict(state='reserved', reservation=reservation)
        observation_ref = q._ref(root, directory / 'execution-observation.json')
        if q._read(root, observation_ref) != observation:
            raise q.IntegrityError('Resource projection lost the canonical execution observation')
        original = budget.execution_reservation(root, reservation)
        if original['settled_observation'] == observation_ref:
            missing = sorted(budget.RESOURCE_DIMENSIONS - set(original['actual']))
            return dict(state='partial_actual' if missing else 'actual', actual=original['actual'],
                        retained_dimensions=missing, reservation=reservation)
        declarations = [item for item in config['execution_interface'].get('public_capabilities', [])
                        if item.get('key') == 'execution_resource_usage'
                        and item.get('schema_id') == 'scidiscovery.execution-resource-usage.v1']
        if len(declarations) != 1 or not callable(getattr(adapter, 'resource_consumption', None)):
            raise ValueError('Trusted native resource projection is unavailable; reservation retained')
        consumed = adapter.resource_consumption(call_id)
        budget.settle_execution(root, reservation=reservation,
            observation=observation_ref, consumed=consumed)
        missing = sorted(budget.RESOURCE_DIMENSIONS - set(consumed))
        return dict(state='partial_actual' if missing else 'actual', actual=consumed,
                    retained_dimensions=missing, reservation=reservation)
    except Exception as error:
        value = dict(state='unavailable_reservation_retained', call_id=call_id, reason=str(error))
        try:
            path = Path(config['record_dir']) / 'calls' / call_id / 'resource-diagnostics' / (
                hashlib.sha256(security.canonical(value)).hexdigest() + '.json')
            value['diagnostic'] = q._save(root, path, value)
        except Exception:
            pass
        return dict(value, reason=value['reason'][:512], reason_omitted_characters=max(0, len(value['reason']) - 512))
