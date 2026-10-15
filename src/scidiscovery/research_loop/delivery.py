"""Bounded delivery bindings and isolated calls; the control ledger owns actions."""
from __future__ import annotations

from . import execution

import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import selectors
import signal
import stat
import subprocess
import tempfile
import time

from . import budget, contracts as c, history, runtime

MAX_BYTES = 256_000
MAX_ASSET_BYTES = 32 * 1024 * 1024
MAX_READ_BYTES = 128 * 1024 * 1024
MAX_SOURCES = 128
SOURCE_SECONDS = 5  # Mechanical transport safety, never a scientific cost estimate.
MAX_LEAF_TAIL = 64 * 1024  # Host-only stream tail retained per isolated leaf call.


class DeliveryUnresolved(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _bytes(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True) + '\n').encode()


def _file(path, limit=MAX_ASSET_BYTES):
    path = Path(path).absolute()
    if path.resolve() != path:
        raise ValueError('Delivery requires an exact original, without symbolic links')
    return c.regular(path, limit=limit)


def policy(value):
    keys = {'closeout_a', 'inflight_tokens', 'cleanup_seconds', 'submit_seconds', 'confirm_seconds', 'adapter'}
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError('Delivery requires explicit closeout, execution and transport ceilings')
    a = value['closeout_a']
    budget.node_policy({role: a for role in ('H', 'W', 'A', 'E')})
    if type(value['inflight_tokens']) is not int or value['inflight_tokens'] < 0:
        raise ValueError('In-flight allowance must be a nonnegative integer')
    for key in ('cleanup_seconds', 'submit_seconds', 'confirm_seconds'):
        amount = value[key]
        if type(amount) not in (int, float) or not math.isfinite(amount) or amount < 0:
            raise ValueError('Explicit finite delivery seconds required')
    adapter = value['adapter']
    if adapter is None:
        if value['submit_seconds'] != 0 or value['confirm_seconds'] != 0:
            raise ValueError('Export-only delivery has no external execution allowance')
        return {**value, 'closeout_a': dict(a)}
    if value['submit_seconds'] <= 0 or value['confirm_seconds'] <= 0:
        raise ValueError('An adapter requires positive submit and confirm ceilings')
    if not isinstance(adapter, dict) or set(adapter) != {'adapter', 'launcher_argv', 'config', 'target', 'inputs', 'source_roots'}:
        raise ValueError('Adapter requires exact code, launcher, scoped inputs, configuration and target')
    script = _file(adapter['adapter'], MAX_BYTES)
    argv = adapter['launcher_argv']
    if not isinstance(argv, list) or not argv or any(not isinstance(s, str) or not s for s in argv):
        raise ValueError('An explicit isolating launcher argv is required')
    launcher_files = []
    for arg in argv:
        path = Path(arg)
        if path.is_file():
            path = path.resolve()
            launcher_files.append(dict(path=str(_file(path, 128 * 1024 * 1024)), invoked_path=str(Path(arg).absolute()), sha256=c.digest(path)))
    if not launcher_files or not Path(argv[0]).is_absolute():
        raise ValueError('Launcher executable and original files must be frozen')
    if not isinstance(adapter['config'], dict) or not isinstance(adapter['target'], dict):
        raise ValueError('Adapter configuration and target must be bounded objects')
    inputs = adapter['inputs']
    roots = adapter['source_roots']
    if not isinstance(inputs, list) or len(inputs) > 16 or not isinstance(roots, list) or not 1 <= len(roots) <= 8:
        raise ValueError('Explicit bounded provider input and read scope required')
    frozen_inputs, labels = [], set()
    for item in inputs:
        if not isinstance(item, dict) or set(item) != {'label', 'path'}:
            raise ValueError('Provider inputs require label and exact original')
        label = item['label']
        _label(label)
        if label in labels:raise ValueError('Duplicate provider input label')
        labels.add(label)
        invoked = Path(item['path']).absolute()
        path = _file(invoked.resolve())
        frozen_inputs.append(dict(label=label, path=str(path), invoked_path=str(invoked), sha256=c.digest(path), size_bytes=path.stat().st_size))
    for path in roots:
        if not isinstance(path, str) or not Path(path).is_absolute() or Path(path).resolve() != Path(path):
            raise ValueError('Provider read scopes require exact absolute originals')
    frozen = dict(adapter=str(script), adapter_sha256=c.digest(script), launcher_argv=list(argv),
                  launcher_files=launcher_files, config=adapter['config'], target=adapter['target'],
                  inputs=frozen_inputs, source_roots=list(roots))
    if len(_bytes(frozen)) > MAX_BYTES:
        raise ValueError('Delivery descriptor exceeds byte capacity')
    return {**value, 'closeout_a': dict(a), 'adapter': frozen}


def _label(label):
    if (not isinstance(label, str) or not label or len(label.encode()) > 160
            or Path(label).is_absolute() or '..' in Path(label).parts
            or '\\' in label or Path(label).as_posix() != label):
        raise ValueError('Canonical bounded provider object label required')


def _adapter(root):
    spec = c.settings(root).get('delivery_policy', {}).get('adapter')
    if spec is None:
        raise DeliveryUnresolved('delivery_adapter_unavailable')
    for proof in [dict(path=spec['adapter'], sha256=spec['adapter_sha256']), *spec['launcher_files'], *spec['inputs']]:
        if 'invoked_path' in proof and Path(proof['invoked_path']).resolve() != Path(proof['path']):
            raise ValueError('Frozen executable or input path now names another original')
        if c.digest(_file(proof['path'], 128 * 1024 * 1024)) != proof['sha256']:
            raise ValueError('Frozen delivery executable or public harness changed')
    from . import protocol
    source=Path(protocol.__file__).resolve()
    if any(item['label']=='scid-current-protocol' for item in spec['inputs']):raise ValueError('Reserved current protocol input label')
    item=dict(label='scid-current-protocol',path=str(source),sha256=c.digest(source),size_bytes=source.stat().st_size)
    return dict(spec,inputs=[*spec['inputs'],item])


def freeze_sources(root, source_nodes, *, candidate_id=None):
    """Freeze readable objects before A; no model load, audit or qualification claim."""
    from .protocol import require_current
    require_current(root)
    root = Path(root).resolve()
    spec = _adapter(root)
    remaining = budget.snapshot(root)['seconds_remaining']
    allowance = min(SOURCE_SECONDS, remaining, c.settings(root)['delivery_policy']['cleanup_seconds'])
    if allowance <= 0:
        raise DeliveryUnresolved('delivery_source_preparation_unavailable')
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + allowance
    consumed, cache = 0, {}
    def freeze(path):
        nonlocal consumed
        path = _file(path)
        if path in cache:return cache[path]
        size = path.stat().st_size
        if consumed + size > MAX_READ_BYTES:
            raise DeliveryUnresolved('delivery_source_capacity')
        data = bytearray()
        with path.open('rb') as stream:
            while block := stream.read(65536):
                if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                    raise DeliveryUnresolved('delivery_source_time_limit')
                data.extend(block)
                if len(data) > MAX_ASSET_BYTES:
                    raise DeliveryUnresolved('delivery_source_capacity')
        consumed += len(data)
        digest = hashlib.sha256(data).hexdigest()
        objects = root / 'host-delivery/objects'
        if objects.resolve() != objects:
            raise ValueError('Delivery archive location changed')
        objects.mkdir(parents=True, exist_ok=True)
        saved = objects / digest
        if saved.exists() or saved.is_symlink():
            if c.digest(_file(saved)) != digest:
                raise ValueError('Frozen delivery object changed')
        else:
            if sum(path.stat().st_size for path in objects.iterdir()) + len(data) > MAX_READ_BYTES:
                raise DeliveryUnresolved('delivery_source_capacity')
            with saved.open('xb') as stream:
                stream.write(data);stream.flush();os.fsync(stream.fileno())
            saved.chmod(0o400)
        cache[path] = dict(path=saved.relative_to(root).as_posix(), sha256=digest, size_bytes=len(data))
        return cache[path]
    candidates, known, evidence, contexts = [], set(), {}, {}
    managed = c.settings(root).get('history_observer', {}).get('contract_version') == 2
    for receipt in source_nodes:
        _, _, seal, seal_sha = history._source(root, receipt['step'])
        if seal_sha != receipt['seal_sha256']:
            raise ValueError('Delivery source scientific seal changed')
        observation = seal.get('observations')
        if observation is None:
            continue
        path = _file(root / observation['path'], MAX_BYTES)
        if c.digest(path) != observation['sha256']:
            raise ValueError('Delivery observer original changed')
        fact = c.read(path)
        if fact['binding']['source_sha256'] != seal['raw_sha256']:
            raise ValueError('Delivery observer source binding changed')
        for context in fact.get('contexts', []):
            context_candidate_id = context.get('candidate_id')
            if context_candidate_id is not None:
                contexts.setdefault(context_candidate_id, []).append(context)
        for candidate in fact['candidates']:
            if candidate_id is not None and candidate['id'] != candidate_id:
                continue
            if candidate['id'] in known:
                raise ValueError('Delivery candidate identity is ambiguous')
            known.add(candidate['id'])
            if len(candidates) >= MAX_SOURCES:continue
            proofs = []
            for proof in candidate['evidence']:
                if proof.get('retention') != 'archived':continue
                bound = dict(path=proof['snapshot'], sha256=proof['sha256'], size_bytes=proof['size_bytes'])
                _proof(root, bound)
                label = 'evidence/' + proof['sha256'] + '.jsonl'
                evidence[label] = bound
                proofs.append(dict(label=label, sha256=proof['sha256']))
            candidates.append(dict(candidate_id=candidate['id'], status=candidate['status'], evidence=proofs))
    def execution_proof(proof):
        value = dict(name=Path(proof['path']).name, sha256=proof['sha256'],
                     size_bytes=proof['size_bytes'], retention=proof.get('retention'), input_label=None)
        if proof.get('retention') == 'archived':
            bound = dict(path=proof['snapshot'], sha256=proof['sha256'], size_bytes=proof['size_bytes'])
            _proof(root, bound)
            label = 'execution/' + proof['sha256']
            if label in evidence and evidence[label] != bound:
                raise ValueError('Execution archive alias changed')
            evidence[label] = bound
            value['input_label'] = label
        return value
    for candidate in candidates:
        candidate['execution_contexts'] = None
        if managed:
            candidate['execution_contexts'] = [dict(call_id=context['call_id'], status=context['status'],
                candidate_id=context['candidate_id'], run_id=context['run_id'],
                proofs=[execution_proof(proof) for proof in context['proofs']],
                model=execution_proof(context['model']) if context.get('model') is not None else None)
                for context in contexts.get(candidate['candidate_id'], [])]
    if sum(proof['size_bytes'] for proof in evidence.values()) > MAX_READ_BYTES:
        raise DeliveryUnresolved('delivery_source_capacity')
    with tempfile.TemporaryDirectory(prefix='scid-resolve-') as directory:
        stage = Path(directory)
        (stage / 'inputs').mkdir();(stage / 'scratch').mkdir()
        for label, proof in evidence.items():
            if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                raise DeliveryUnresolved('delivery_source_time_limit')
            destination = stage / 'inputs' / label;destination.parent.mkdir(exist_ok=True)
            shutil.copyfile(_proof(root, proof), destination);destination.chmod(0o400)
        for proof in spec['inputs']:
            destination = stage / 'inputs' / proof['label'];destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(_file(proof['path']), destination);destination.chmod(0o400)
            if c.digest(destination) != proof['sha256']:raise ValueError('Frozen provider input changed during staging')
        request = dict(scope=dict(handoff_protocol=c.settings(root)['handoff_protocol']),phase='resolve', operation_id=hashlib.sha256(_bytes(source_nodes)).hexdigest(),
                       candidate_id=None, artifact_sha256=None, root=str(root), source_roots=spec['source_roots'],
                       candidates=candidates, inputs=spec['inputs'], config=spec['config'], target=spec['target'], stage=str(stage))
        value = _call(spec, request, deadline - time.clock_gettime(time.CLOCK_BOOTTIME), evidence=leaf_output(root))
    if not isinstance(value, dict) or set(value) != {'items'} or not isinstance(value['items'], list):
        raise DeliveryUnresolved('delivery_resolver_unavailable')
    originals = {row['candidate_id']: row for row in candidates}
    items, seen = [], set()
    static = {}
    for proof in spec['inputs']:
        frozen = freeze(proof['path'])
        if frozen['sha256'] != proof['sha256']:raise ValueError('Frozen provider input changed before snapshot')
        static[proof['label']] = frozen
    for item in value['items']:
        if (not isinstance(item, dict) or item.get('candidate_id') not in originals or item['candidate_id'] in seen
                or item.get('status') not in {'audit_pending', 'unavailable'}):
            raise ValueError('Resolver candidate identity or availability changed')
        seen.add(item['candidate_id'])
        if item['status'] == 'unavailable':
            items.append(dict(candidate_id=item['candidate_id'], status='unavailable', reason='delivery_source_unavailable'));continue
        label = item.get('evidence_label')
        if label not in {proof['label'] for proof in originals[item['candidate_id']]['evidence']}:
            raise ValueError('Resolver used another candidate original')
        objects = dict(static)
        try:
            if not isinstance(item.get('objects'), list) or len(item['objects']) > 16 or not isinstance(item.get('context'), dict):
                raise ValueError('Resolver objects require bounded references and context')
            for obj in item['objects']:
                if not isinstance(obj, dict):raise ValueError('Resolver object fields changed')
                from_execution = set(obj) == {'label', 'proof_label'}
                if from_execution:
                    authorized = {proof['input_label'] for context in originals[item['candidate_id']].get('execution_contexts') or []
                                  for proof in context['proofs'] if proof.get('retention') == 'archived'}
                    label = obj['proof_label']
                    if label not in authorized or label not in evidence:
                        raise ValueError('Resolver selected an unbound execution original')
                    bound = evidence[label]
                    obj = dict(label=obj['label'], path=str(_proof(root, bound)), sha256=bound['sha256'], size_bytes=bound['size_bytes'])
                elif set(obj) != {'label', 'path', 'sha256', 'size_bytes'}:
                    raise ValueError('Resolver object fields changed')
                _label(obj['label'])
                path = Path(obj['path'])
                if obj['label'] in objects or not path.is_absolute() or (not from_execution and not any(path.is_relative_to(Path(scope)) for scope in spec['source_roots'])):
                    raise ValueError('Resolver object is outside its frozen read scope')
                proof = freeze(path)
                if proof['sha256'] != obj['sha256'] or proof['size_bytes'] != obj['size_bytes']:
                    raise ValueError('Resolver object changed before freezing')
                objects[obj['label']] = proof
            if 'artifact' not in objects:raise DeliveryUnresolved('delivery_artifact_unavailable')
            if len(_bytes(item['context'])) > 8192:raise ValueError('Resolver context exceeds byte bound')
            items.append(dict(candidate_id=item['candidate_id'], status='audit_pending',
                              context=item['context'], ledger=evidence[label], objects=objects))
        except DeliveryUnresolved as error:
            items.append(dict(candidate_id=item['candidate_id'], status='unavailable', reason=error.code))
    for candidate in candidates:
        if candidate['candidate_id'] not in seen:
            items.append(dict(candidate_id=candidate['candidate_id'], status='unavailable', reason='delivery_source_unavailable'))
    packed = dict(items=[], omitted_count=len(known) - len(candidates), source_nodes=list(source_nodes))
    for item in items:
        if len(_bytes(dict(packed, items=[*packed['items'], item]))) > MAX_BYTES:
            packed['omitted_count'] += 1
        else:
            packed['items'].append(item)
    return packed


def public_sources(refs):
    result = dict(items=[{key: row[key] for key in ('candidate_id', 'status', 'reason') if key in row}
                         for row in refs['items'][:16]],
                  omitted_count=refs['omitted_count'] + max(0, len(refs['items']) - 16),
                  qualification='Pending audit; a closeout snapshot does not verify the historical proxy metric.')
    if len(_bytes(result)) > 4096:
        raise ValueError('Delivery public brief exceeds byte bound')
    return result


def _proof(root, proof):
    name = Path(proof['path'])
    if name.is_absolute() or '..' in name.parts:
        raise ValueError('Delivery object is outside its exact instance')
    path = _file(root / name)
    if path.stat().st_size != proof['size_bytes'] or c.digest(path) != proof['sha256']:
        raise ValueError('Frozen delivery original changed')
    return path


def validate_sources(root, refs):
    _adapter(root)
    for receipt in refs['source_nodes']:
        if history._source(root, receipt['step'])[3] != receipt['seal_sha256']:
            raise ValueError('Delivery source scientific identity changed')
    seen = {}
    for item in refs['items']:
        if item['status'] == 'audit_pending':
            for proof in [item['ledger'], *item['objects'].values()]:
                identity = (proof['sha256'], proof['size_bytes'])
                if proof['path'] in seen:
                    if seen[proof['path']] != identity:raise ValueError('Conflicting delivery aliases for one original')
                else:
                    _proof(root, proof)
                    seen[proof['path']] = identity
    return refs


def binding(root, job, result):
    if job.get('purpose') != 'closeout' or job['role'] != 'A':
        raise ValueError('Only a frozen closeout A can decide delivery')
    path = root / 'jobs' / f'{job["step"]:03d}.json'
    if c.read(path) != job:
        raise ValueError('Delivery decision job changed')
    raw = c.validate(c.workspace(root, job['step']))
    chosen = result.get('candidate_recommendation')
    if chosen != raw.get('candidate_recommendation'):
        raise ValueError('Delivery choice differs from sealed original')
    if chosen is None or raw.get('next_action') != 'finish':
        raise DeliveryUnresolved('delivery_no_decision')
    rows = [row for row in job.get('delivery_sources', {}).get('items', []) if row['candidate_id'] == chosen]
    if len(rows) != 1 or rows[0]['status'] != 'audit_pending':
        raise DeliveryUnresolved('delivery_source_unavailable')
    item = rows[0]
    # c.validate already checks this entire frozen source pack once. Re-reading
    # every candidate/static object here would multiply mechanical I/O by count.
    record = c.host_record(c.workspace(root, job['step']))
    decision = dict(step=job['step'], job_sha256=c.digest(path),
                    raw_sha256=c.digest(execution.raw(root, job['step'])), seal_sha256=c.digest(record / 'result-identity.json'))
    result = dict(candidate_id=chosen, decision=decision, source=item,
                  target=c.settings(root)['delivery_policy']['adapter']['target'])
    result['operation_id'] = hashlib.sha256(_bytes(dict(settings_sha256=c.digest(root / 'settings.json'), **result))).hexdigest()
    return result


def _result(binding, status, note, *, cleanup_confirmed=True):
    return dict(status=status, operation_id=binding['operation_id'], candidate_id=binding['candidate_id'],
                artifact_sha256=binding['source']['objects']['artifact']['sha256'], note=note,
                cleanup_confirmed=cleanup_confirmed)


def leaf_output(root):
    return Path(root) / 'host-delivery/leaf-output'


def leaf_refs(root, operation_id):
    """Exact host diagnostics for one operation; outcome receipts reference these."""
    directory = leaf_output(root)
    return [dict(path=path.relative_to(root).as_posix(), sha256=c.digest(path))
            for path in sorted(directory.glob(operation_id + '-*.json'))] if directory.is_dir() else []


def _tail(path):
    """Bounded tail of a leaf-written scratch log; never follows a link."""
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except OSError:
        return None
    with os.fdopen(descriptor, 'rb') as stream:
        status = os.fstat(descriptor)
        if not stat.S_ISREG(status.st_mode):return None
        size = status.st_size
        stream.seek(max(0, size - MAX_LEAF_TAIL))
        return size, stream.read(MAX_LEAF_TAIL)


def _keep(evidence, request, outcome, returncode, streams):
    """Host-only diagnostics beside the action outcome, keyed by operation/phase.

    Never a scientific original: no workspace, history or model brief reads it.
    """
    if evidence is None:return
    try:
        directory = Path(evidence);directory.mkdir(parents=True, exist_ok=True)
        if directory.resolve() != directory:return
        stem = next(f"{request['operation_id']}-{request['phase']}-{n}" for n in range(1, 1000)
                    if not (directory / f"{request['operation_id']}-{request['phase']}-{n}.json").exists())
        index = dict(operation_id=request['operation_id'], phase=request['phase'], outcome=outcome, returncode=returncode, streams={})
        for label, (size, data) in streams.items():
            entry = dict(total_bytes=size, kept_bytes=len(data), truncated=size > len(data), path=None, sha256=None)
            if data:
                path = directory / f'{stem}.{label}'
                with path.open('xb') as stream:stream.write(data)
                path.chmod(0o400);entry.update(path=path.name, sha256=hashlib.sha256(data).hexdigest())
            index['streams'][label] = entry
        with (directory / (stem + '.json')).open('x') as stream:stream.write(json.dumps(index, sort_keys=True) + '\n')
        (directory / (stem + '.json')).chmod(0o400)
    except (OSError, StopIteration):
        pass  # Diagnostics never change the bounded delivery outcome.


def _call(spec, request, seconds, *, on_process=None, evidence=None):
    if seconds <= 0:return None
    data = _bytes(request)
    if len(data) > MAX_BYTES:raise ValueError('Delivery request exceeds byte bound')
    runtime._subreaper()  # Same actual ownership cleanup used by native runners.
    output, errors, totals = bytearray(), bytearray(), dict(stdout=0, stderr=0)
    def keep(outcome, returncode=None):
        streams = dict(stdout=(totals['stdout'], bytes(output[-MAX_LEAF_TAIL:])), stderr=(totals['stderr'], bytes(errors)))
        if request.get('phase') == 'audit' and request.get('stage'):
            for name in ('stdout', 'stderr'):
                found = _tail(Path(request['stage']) / 'scratch' / f'audit.{name}')
                if found is not None:streams['audit.' + name] = found
        _keep(evidence, request, outcome, returncode, streams)
    with tempfile.TemporaryFile() as input_file:
        input_file.write(data);input_file.seek(0)
        process = subprocess.Popen([*spec['launcher_argv'], spec['adapter']], stdin=input_file,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={'PATH': os.defpath}, start_new_session=True)
        identity = runtime.process_identity(process.pid, request['operation_id'])
        if on_process is not None:
            try:
                on_process(request['phase'], identity)
            except BaseException:
                if runtime.process_matches(identity, identity['task_sha256']):os.killpg(identity['pgid'], signal.SIGKILL)
                process.wait(timeout=5)
                process.stdout.close();process.stderr.close()
                if runtime.cleanup_owned_group(identity) != 'observed_group_cleaned':
                    raise DeliveryUnresolved('delivery_cleanup_unknown')
                raise
        deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + seconds
        total, failed = 0, False
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            selector.register(process.stderr, selectors.EVENT_READ)
            while selector.get_map() or process.poll() is None:
                remaining = deadline - time.clock_gettime(time.CLOCK_BOOTTIME)
                if remaining <= 0:failed = True;break
                for key, _ in selector.select(min(.1, remaining)):
                    block = os.read(key.fileobj.fileno(), 65536)
                    if not block:selector.unregister(key.fileobj);continue
                    total += len(block)
                    if key.fileobj is process.stdout:output.extend(block);totals['stdout'] += len(block)
                    else:errors.extend(block);del errors[:-MAX_LEAF_TAIL];totals['stderr'] += len(block)
                    if total > MAX_BYTES:failed = True;break
                if failed:break
        if failed:
            if runtime.process_matches(identity, identity['task_sha256']):
                os.killpg(identity['pgid'], signal.SIGKILL)
            process.wait(timeout=5)
            process.stdout.close();process.stderr.close()
            keep('time_or_byte_limit', process.returncode)
            if runtime.cleanup_owned_group(identity) != 'observed_group_cleaned':
                raise DeliveryUnresolved('delivery_cleanup_unknown')
            return None
        process.wait(timeout=5)
        process.stdout.close();process.stderr.close()
        keep('exited', process.returncode)
        if runtime.cleanup_owned_group(identity) != 'observed_group_cleaned':
            raise DeliveryUnresolved('delivery_cleanup_unknown')
    if process.returncode:
        return None
    try:
        value = json.loads(output)
    except (ValueError, UnicodeDecodeError):
        return None
    return value


def invoke(root, intent, max_seconds, *, on_process=None, audit_only=False):
    """Caller already durably accepted this action; recovered submits never call here."""
    from .protocol import require_current
    require_current(root)
    root = Path(root).resolve()
    if type(max_seconds) not in (int, float) or not 0 < max_seconds < float('inf'):
        raise ValueError('Bounded action seconds required')
    if audit_only:
        from . import candidate_audit
        candidate_audit.validate_intent(root, intent)
        actions = [dict(intent=intent, outcome=None)]
    else:
        actions = budget.closeout_state(root)['actions']
    stored = next((action for action in actions if action['intent']['action_id'] == intent.get('action_id')), None)
    if stored is None or stored['intent'] != intent:
        raise ValueError('Delivery action was not durably accepted in the control ledger')
    if stored['outcome'] is not None:
        return stored['outcome']['result']
    used = budget.snapshot(root)['advance_seconds'] - intent['advance_seconds']
    if used < 0:raise ValueError('Delivery action time moved backwards')
    max_seconds = min(max_seconds, intent['max_seconds'] - used, budget.snapshot(root)['seconds_remaining'])
    if max_seconds <= 0:return _result(intent['binding'], 'unknown', 'action_time_limit')
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + max_seconds
    spec = _adapter(root)
    bound = intent['binding']
    if intent['operation_id'] != bound['operation_id'] or intent['decision'] != bound['decision']:
        raise ValueError('Delivery action identity differs from frozen decision')
    decision = bound['decision'];step = decision['step']
    record = c.host_record(c.workspace(root, step))
    for path, key in [(root / 'jobs' / f'{step:03d}.json', 'job_sha256'),
                      (execution.raw(root, step), 'raw_sha256'), (record / 'result-identity.json', 'seal_sha256')]:
        if c.digest(_file(path)) != decision[key]:
            raise ValueError('Delivery scientific decision changed')
    job = c.read(root / 'jobs' / f'{step:03d}.json')
    if audit_only:
        candidate_audit.validate_binding(root, intent)
    elif binding(root, job, c.validate(c.workspace(root, step))) != bound:
        raise ValueError('Delivery input binding changed')
    if intent['action_kind'] not in (('audit',) if audit_only else ('submit', 'confirm')):
        raise ValueError('Unknown delivery action')
    with tempfile.TemporaryDirectory(prefix='scid-delivery-') as directory:
        stage = Path(directory)
        (stage / 'inputs/harness').mkdir(parents=True)
        (stage / 'scratch').mkdir()
        for name, proof in bound['source']['objects'].items():
            _label(name)
            (stage / 'inputs' / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(_proof(root, proof), stage / 'inputs' / name)
            (stage / 'inputs' / name).chmod(0o400)
        request = dict(scope=dict(handoff_protocol=c.settings(root)['handoff_protocol']),operation_id=bound['operation_id'], candidate_id=bound['candidate_id'],
                       artifact_sha256=bound['source']['objects']['artifact']['sha256'], context=bound['source']['context'],
                       object_digests={name: proof['sha256'] for name, proof in bound['source']['objects'].items()},
                       inputs=spec['inputs'], config=spec['config'], target=spec['target'], stage=str(stage))
        phases = ('audit',) if audit_only else ('audit', 'promote') if intent['action_kind'] == 'submit' else ('confirm',)
        for phase in phases:
            remaining = deadline - time.clock_gettime(time.CLOCK_BOOTTIME)
            try:
                value = _call(spec, dict(request, phase=phase), remaining, on_process=on_process,
                              evidence=leaf_output(root)) if remaining > 0 else None
            except DeliveryUnresolved as error:
                if error.code != 'delivery_cleanup_unknown':raise
                return _result(bound, 'unknown', 'cleanup_unknown', cleanup_confirmed=False)
            if value is None:
                return _result(bound, 'failed' if phase == 'audit' else 'unknown', 'bounded_' + phase + '_unverified')
            if (not isinstance(value, dict) or set(value) != {'status', 'operation_id', 'candidate_id', 'artifact_sha256', 'note'}
                    or any(value.get(key) != request[key] for key in ('operation_id', 'candidate_id', 'artifact_sha256'))
                    or not isinstance(value['note'], str) or len(value['note'].encode()) > 1024):
                return _result(bound, 'failed' if phase == 'audit' else 'unknown', 'invalid_' + phase + '_result')
            if phase == 'audit' and value['status'] == 'audited':
                if audit_only:
                    return dict(value, cleanup_confirmed=True)
                continue
            if value['status'] not in ('confirmed', 'failed', 'unknown') or phase == 'audit' and value['status'] == 'confirmed':
                return _result(bound, 'failed' if phase == 'audit' else 'unknown', 'invalid_phase_result')
            return dict(value, cleanup_confirmed=True)
    raise AssertionError('Delivery phase produced no bounded outcome')
