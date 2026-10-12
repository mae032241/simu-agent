"""Public covshift source resolver and isolated audit/byte-promotion adapter.

The resolver never loads models. Use [python, __file__, '--isolate'] as the
launcher; its audit namespace cannot mount the real targets or private task data.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

BOUND = 32 * 1024 * 1024
FILES = ('exp_cli.py', 'runner.py', 'train.csv', 'val.csv', 'meta.json')


def _exact(path, limit=BOUND):
    path = Path(path).absolute()
    if path.resolve() != path or not path.is_file() or path.stat().st_size > limit:
        raise ValueError('Exact bounded delivery original required')
    return path


def _sha(path):
    return hashlib.sha256(_exact(path).read_bytes()).hexdigest()


def target(value):
    if not isinstance(value, dict) or set(value) != {'runs', 'submission'}:
        raise ValueError('Cov target requires exact public run output and submission directories')
    for name in value.values():
        path = Path(name)
        if not path.is_absolute() or path.resolve() != path or '..' in path.parts:
            raise ValueError('Cov target must be an explicitly frozen original directory')
    if Path(value['runs']) == Path(value['submission']):
        raise ValueError('Run output and final submission must be distinct')
    return dict(value)


class SourceUnavailable(ValueError):
    pass


def original(root, candidate, cfg, ledger_cache):
    match = re.fullmatch(r'run-([1-9][0-9]*)', candidate['candidate_id'])
    if match is None or candidate['status'] != 'ok':
        raise SourceUnavailable('delivery_candidate_not_available')
    matches = []
    for proof in candidate['evidence']:
        path = _exact(Path('/inputs') / proof['label'])
        if proof['sha256'] not in ledger_cache:
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != proof['sha256']:
                raise ValueError('Frozen public run evidence changed')
            indexed = {}
            for line in data.splitlines():
                if not line.strip():continue
                if len(line) > 256_000:raise ValueError('Public run row exceeds byte bound')
                row = json.loads(line)
                if type(row.get('run_id')) is int:indexed.setdefault(row['run_id'], []).append(row)
            ledger_cache[proof['sha256']] = indexed
        matches.extend((row, proof['label']) for row in ledger_cache[proof['sha256']].get(int(match[1]), []))
    if len(matches) != 1:
        raise SourceUnavailable('delivery_run_source_ambiguous')
    row, proof = matches[0]
    if (row.get('ok') is not True or not isinstance(row.get('model_path'), str)
            or not isinstance(row.get('script'), str) or type(row.get('val_acc')) not in (int, float)
            or not math.isfinite(row['val_acc'])):
        raise SourceUnavailable('delivery_run_source_incomplete')
    # Metric is not reinterpreted as an audit or a guarantee about current bytes.
    return {key: row[key] for key in ('run_id', 'ok', 'model_path', 'script', 'val_acc')}, proof


def mapped_model(root, row, cfg):
    named = Path(row['model_path'])
    prefix = Path(cfg['namespace_runs'])
    if not named.is_absolute() or '..' in named.parts or not named.is_relative_to(prefix):
        raise SourceUnavailable('delivery_model_mapping_unavailable')
    return root / cfg['runs'] / named.relative_to(prefix)


def model_path(root, row, cfg):
    path = mapped_model(root, row, cfg)
    if path.resolve() != path or not path.is_file() or path.stat().st_size > BOUND:
        raise SourceUnavailable('delivery_model_unavailable')
    return path


def source_path(root, row):
    path = Path(row['script'])
    if (not path.is_absolute() or not path.is_relative_to(root / 'project/nodes')
            or '..' in path.parts or path.resolve() != path or not path.is_file()
            or path.stat().st_size > BOUND):
        raise SourceUnavailable('delivery_code_source_unavailable')
    return path


def managed_objects(candidate, row):
    contexts = candidate.get('execution_contexts')
    if contexts is None:
        return None  # Legacy v1: current source snapshot, not a historical claim.
    if not isinstance(contexts, list) or len(contexts) != 1:
        raise SourceUnavailable('delivery_managed_context_missing_or_ambiguous')
    context = contexts[0]
    if (context.get('candidate_id') != candidate['candidate_id'] or context.get('run_id') != row['run_id']
            or context.get('status') != 'known_success' or not isinstance(context.get('proofs'), list)):
        raise SourceUnavailable('delivery_managed_context_not_available')
    def unique(name):
        matches = [proof for proof in context['proofs'] if proof.get('name') == name]
        if len(matches) != 1:
            raise SourceUnavailable('delivery_managed_original_missing_or_ambiguous')
        return matches[0]
    def bound(proof):
        if proof.get('retention') != 'archived' or not isinstance(proof.get('input_label'), str):
            raise SourceUnavailable('delivery_managed_original_not_retained')
        label = proof['input_label']
        if not re.fullmatch(r'execution/[0-9a-f]{64}', label):
            raise ValueError('Frozen execution proof label changed')
        path = _exact(Path('/inputs') / label)
        if _sha(path) != proof['sha256'] or path.stat().st_size != proof['size_bytes']:
            raise ValueError('Frozen managed execution original changed')
        return path
    source, model, receipt = unique('source.py'), unique('model.pkl'), unique('row.json')
    if context.get('model') != model:
        raise ValueError('Managed model differs from frozen exact context')
    original_row = json.loads(bound(receipt).read_text())
    if any(original_row.get(key) != value for key, value in row.items()):
        raise ValueError('Candidate ledger differs from frozen exact call row')
    bound(source);bound(model)
    return [dict(label='artifact', proof_label=model['input_label']),
            dict(label='source.py', proof_label=source['input_label'])]


def _audit(value, run_id):
    return (isinstance(value, dict) and type(value.get('run_id')) is int and value['run_id'] == run_id
            and value.get('leakage_flag') is False
            and all(type(value.get(key)) in (int, float) and math.isfinite(value[key]) for key in ('audit_score', 'audit_gap'))
            and isinstance(value.get('audit_note'), str) and value['audit_note'].startswith('audit took '))


def _reply(request, status, note):
    return dict(status=status, operation_id=request['operation_id'], candidate_id=request['candidate_id'],
                artifact_sha256=request['artifact_sha256'], note=note)


def _write(path, data):
    with path.open('wb') as stream:
        stream.write(data);stream.flush();os.fsync(stream.fileno())


def _replace(path, data):
    pending = path.with_name(path.name + '.rootless-pending')
    if pending.exists() or pending.is_symlink():
        raise ValueError('Uncertain delivery target temporary exists')
    _write(pending, data)
    os.replace(pending, path)


def leaf(request):
    phase = request['phase']
    if phase == 'resolve':
        cfg = request['config']
        if set(cfg) != {'runs', 'namespace_runs', 'python'}:
            raise ValueError('Cov provider requires exact runs mapping and runtime')
        if (Path(cfg['runs']).is_absolute() or '..' in Path(cfg['runs']).parts
                or not Path(cfg['namespace_runs']).is_absolute() or '..' in Path(cfg['namespace_runs']).parts):
            raise ValueError('Cov provider requires canonical original run paths')
        items, ledger_cache, object_cache = [], {}, {}
        for candidate in request['candidates']:
            item = dict(candidate_id=candidate['candidate_id'], status='unavailable')
            try:
                row, evidence = original(Path(request['root']), candidate, cfg, ledger_cache)
                mapped_model(Path(request['root']), row, cfg)
                objects = managed_objects(candidate, row)
                managed = objects is not None
                if objects is None:
                    objects = []
                    for label, path in [('artifact', model_path(Path(request['root']), row, cfg)),
                                        ('source.py', source_path(Path(request['root']), row))]:
                        if path not in object_cache:object_cache[path] = dict(path=str(path), sha256=_sha(path), size_bytes=path.stat().st_size)
                        objects.append(dict(label=label, **object_cache[path]))
                item.update(status='audit_pending', evidence_label=evidence, objects=objects,
                    context=dict(row=row, identity_note=('Exact sealed managed call originals; public audit is still pending.' if managed else
                        'Legacy current-source snapshot; original historical source version is not established.')))
            except (SourceUnavailable, FileNotFoundError):
                pass
            items.append(item)
        return dict(items=items)
    run_id = request['context']['row']['run_id']
    if request['candidate_id'] != f'run-{run_id}' or not re.fullmatch('[0-9a-f]{64}', request['operation_id']):
        raise ValueError('Exact operation and candidate required')
    if _sha('/inputs/artifact') != request['artifact_sha256']:
        raise ValueError('Selected model bytes changed')
    for label, digest in request['object_digests'].items():
        if _sha(Path('/inputs') / label) != digest:raise ValueError('Frozen audit input changed')
    runs, submission = Path('/target/runs'), Path('/target/submission')
    if phase == 'audit':
        scratch = Path('/scratch/runs');scratch.mkdir()
        row = dict(request['context']['row'], model_path='/inputs/artifact', script='/inputs/source.py')
        _write(scratch / 'results.jsonl', (json.dumps(row, allow_nan=False) + '\n').encode())
        env = dict(os.environ, EXP_HARNESS='/inputs/harness', EXP_RUN_DIR=str(scratch),
                   EXP_TRAIN='/inputs/harness/train.csv', EXP_VAL='/inputs/harness/val.csv',
                   EXP_META='/inputs/harness/meta.json', EXP_RUNNER='/inputs/harness/runner.py')
        with Path('/scratch/audit.stdout').open('wb') as out, Path('/scratch/audit.stderr').open('wb') as err:
            result = subprocess.run([request['config']['python'], '-I', '/inputs/harness/exp_cli.py',
                                     'submit', '--run-id', str(run_id)], env=env, stdout=out, stderr=err)
        proof = scratch / 'submitted.json'
        if result.returncode or not proof.exists() or not _audit(json.loads(_exact(proof, 256_000).read_text()), run_id):
            return _reply(request, 'failed', 'audit_unavailable_or_failed')
        if _sha(scratch / 'submitted_model.pkl') != request['artifact_sha256']:
            return _reply(request, 'failed', 'audit_model_identity_changed')
        return _reply(request, 'audited', 'public_audit_completed_nonleaking')
    if phase == 'promote':
        audit = json.loads(_exact('/scratch/runs/submitted.json', 256_000).read_text())
        if not _audit(audit, run_id) or _sha('/scratch/runs/submitted_model.pkl') != request['artifact_sha256']:
            return _reply(request, 'failed', 'audit_not_completed')
        data = _exact('/inputs/artifact').read_bytes()
        # A multi-file commit can be interrupted. The marker is written last;
        # anything partial stays unknown and is queried without resubmission.
        for path in (runs / 'submitted_model.pkl', submission / 'model.pkl'):
            _replace(path, data)
        audit['model_path'] = str(Path(request['target']['runs']) / 'submitted_model.pkl')
        _replace(runs / 'submitted.json', (json.dumps(audit, allow_nan=False) + '\n').encode())
        marker = dict(operation_id=request['operation_id'], candidate_id=request['candidate_id'],
                      artifact_sha256=request['artifact_sha256'], audit_sha256=_sha(runs / 'submitted.json'))
        _replace(runs / 'rootless-delivery-operation.json', (json.dumps(marker) + '\n').encode())
    elif phase != 'confirm':
        raise ValueError('Unknown delivery phase')
    try:
        marker = json.loads(_exact(runs / 'rootless-delivery-operation.json', 256_000).read_text())
        actual = json.loads(_exact(runs / 'submitted.json', 256_000).read_text())
        if (all(marker.get(key) == request[key] for key in ('operation_id', 'candidate_id', 'artifact_sha256'))
                and _audit(actual, run_id) and _sha(runs / 'submitted.json') == marker['audit_sha256']
                and _sha(runs / 'submitted_model.pkl') == request['artifact_sha256']
                and _sha(submission / 'model.pkl') == request['artifact_sha256']):
            return _reply(request, 'confirmed', 'exact_public_submission_confirmed')
    except (OSError, ValueError, KeyError):
        pass
    return _reply(request, 'unknown', 'exact_submission_not_confirmed')


def isolate(request, adapter):
    """Exec the declared namespace; only promotion can write true target dirs."""
    stage = Path(request['stage'])
    if stage.resolve() != stage or not stage.is_dir() or not Path(adapter).is_file():
        raise ValueError('Exact delivery stage required')
    python = Path(request['config']['python'])
    runtime = next((proof for proof in request['inputs'] if proof['label'] == 'runtime-python'), None)
    if runtime is None or python.absolute() != Path(runtime['invoked_path']) or python.resolve() != Path(runtime['path']) or hashlib.sha256(python.resolve().read_bytes()).hexdigest() != runtime['sha256']:
        raise ValueError('Frozen task interpreter changed')
    bwrap = shutil.which('bwrap')
    if bwrap is None:
        raise ValueError('Delivery requires the qualified namespace launcher')
    args = [bwrap, '--unshare-user', '--unshare-pid', '--unshare-net', '--unshare-ipc', '--unshare-uts',
            '--die-with-parent', '--new-session', '--clearenv', '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp']
    base = Path(runtime['path']).parent.parent
    # These paths derive only from the frozen invocation/resolved interpreter;
    # never search an operator home for a compatible Python or package cache.
    for path in dict.fromkeys(['/usr', '/bin', '/lib', '/lib64', str(python.parent.parent),
                               str(base / 'bin'), str(base / 'lib')]):
        if Path(path).exists():args += ['--ro-bind', path, path]
    args += ['--ro-bind', str(stage / 'inputs'), '/inputs', '--ro-bind', adapter, '/delivery.py']
    phase = request['phase']
    target(request['target'])
    args += ['--bind' if phase in {'audit', 'resolve'} else '--ro-bind', str(stage / 'scratch'), '/scratch']
    if phase == 'resolve':
        for scope in request['source_roots']:
            path = Path(scope)
            if path.resolve() != path or not path.is_dir():raise ValueError('Original read scope missing or changed')
            args += ['--ro-bind', str(path), str(path)]
    elif phase != 'audit':
        args += ['--dir', '/target']
        for key in ('runs', 'submission'):
            path = Path(request['target'][key])
            if path.resolve() != path or not path.is_dir():raise ValueError('Declared target missing or changed')
            args += ['--bind' if phase == 'promote' else '--ro-bind', str(path), '/target/' + key]
    args += ['--setenv', 'PATH', os.defpath, '--setenv', 'LANG', 'C.UTF-8',
             '--setenv', 'OPENBLAS_NUM_THREADS', '1', '--setenv', 'OMP_NUM_THREADS', '1',
             '--chdir', '/scratch', '--', str(python), '-I', '/delivery.py', '--leaf']
    # Preserve stdin for the leaf; no host secrets, control root or network mounts.
    os.execv(bwrap, args)


if __name__ == '__main__':
    data = sys.stdin.buffer.read(256_001)
    if len(data) > 256_000:raise ValueError('Delivery input exceeds byte bound')
    request = json.loads(data)
    if sys.argv[1] == '--isolate':
        # Recreate a finite stdin after parsing the launcher request.
        import tempfile
        with tempfile.TemporaryFile() as stream:
            stream.write(data);stream.seek(0);os.dup2(stream.fileno(), 0)
            isolate(request, str(Path(sys.argv[2]).resolve()))
    elif sys.argv[1:] == ['--leaf']:
        print(json.dumps(leaf(request), allow_nan=False))
    else:
        raise ValueError('Delivery must use its isolated execution entry')
