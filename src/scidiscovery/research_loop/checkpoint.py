"""Immutable W fragment originals and a bounded resume brief; no execution grants.

The scientific stage remains the original job. This module neither seals that
stage nor starts a native turn, queries adapters, or updates scientific counters.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import contracts as c, execution, history
from .output_repair import OutputRepairRequired

VERSION = 1
MAX_BYTES = 64_000
MAX_BRIEF_BYTES = 4096
MAX_MATERIALS = 128
NATIVE_ORIGINALS = ('native-intent.json', 'native-outcome.json', 'usage.json',
                    'science-output.json', 'experiment-config.json')


def policy(value):
    if (not isinstance(value, dict) or set(value) != {'context'}
            or value['context'] not in {'same_session', 'new_context'}):
        raise ValueError('W fragments require one explicit same_session or new_context strategy')
    return dict(value)


def enabled(root, job):
    value = c.settings(Path(root)).get('worker_fragment_policy')
    if value is None or job['role'] != 'W':
        return False
    policy(value)
    return True


def _bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()


def _binding(root, job, record):
    root, record = Path(root), Path(record)
    if root.resolve() != root or record.resolve() != record:
        raise ValueError('Fragment originals require exact instance paths')
    path = c.regular(root / 'jobs' / f'{job["step"]:03d}.json')
    if job.get('role') != 'W' or c.read(path) != job:
        raise ValueError('Fragment must bind the exact original W scientific job')
    chain = execution.records(root, job['step'])
    if record not in chain:
        raise ValueError('Fragment must name an accepted original native attempt')
    intent = c.read(c.regular(record / 'native-intent.json'))
    digest = c.digest(path)
    if intent.get('task_sha256') != digest:
        raise ValueError('Fragment native intent changed its scientific job')
    return dict(step=job['step'], attempt=chain.index(record), job_sha256=digest,
                stage_owner=digest, record=record.relative_to(root).as_posix())


def _science(root, job, originals):
    row = next((item for item in originals if Path(item['path']).name == 'science-output.json'), None)
    if row is None:
        return dict(status='missing', diagnostic='missing_output'), None
    outcome = next((item for item in originals if Path(item['path']).name == 'native-outcome.json'), None)
    try:
        receipt = c.read(root / outcome['path']) if outcome else None
    except (json.JSONDecodeError, UnicodeDecodeError):
        receipt = None
    if not isinstance(receipt, dict) or receipt.get('raw_sha256') != row['sha256']:
        return dict(status='unverified', diagnostic='unbound_final_output'), None
    try:
        payload = c.science_payload(root / row['path'], 'W', job.get('handoff_protocol', 1))
    except OutputRepairRequired as error:
        return dict(status='invalid', diagnostic=error.code), None
    return dict(status='present', diagnostic=None), payload


def capture(root, job, record):
    """Freeze only this attempt and current direct deliverables, even without prose.

    The caller must first establish that this attempt's native originals have
    stopped being written. Unknown usage or cleanup can be preserved after that
    boundary; an unknown outcome alone never establishes it. This reference API
    must not capture a live runner. Live observations remain in feedback instead.

    Repeated capture returns the prior verified checkpoint. Direct files can be
    changed by later fragments; their archived bytes remain the checkpoint truth.
    Managed call identity and candidate facts stay in their existing receipts.
    """
    root, record = Path(root), Path(record)
    binding = _binding(root, job, record)
    destination = record / 'checkpoint.json'
    if destination.exists() or destination.is_symlink():
        return validate(root, job, record)
    originals, missing = [], []
    for name in NATIVE_ORIGINALS:
        path = record / name
        if not path.exists() and not path.is_symlink():
            missing.append(name)
            continue
        original = c.regular(path, limit=MAX_BYTES)
        originals.append(dict(path=original.relative_to(root).as_posix(),
                              sha256=c.digest(original), size_bytes=original.stat().st_size))
    science, _ = _science(root, job, originals)
    try:
        direct = c.collect_materials(root, job['step'])
        material_status, material_diagnostic = 'observed', None
    except ValueError as error:
        # Output capacity or unsafe deliverables cannot erase native originals.
        # No missing/unsafe file is presented as a successfully retained result.
        direct = []
        material_status, material_diagnostic = 'unavailable', str(error)[:256]
    work = c.workspace(root, job['step'])
    materials = []
    for row in direct[:MAX_MATERIALS]:
        source = Path(row['source'])
        snapshot = history._proof(root, source.relative_to(root).as_posix())
        materials.append(dict(name=source.relative_to(work).as_posix(), original=snapshot))
    value = dict(version=VERSION, binding=binding, originals=originals,
                 missing_native_originals=missing, science=science, materials=materials,
                 material_status=material_status, material_diagnostic=material_diagnostic,
                 omitted_materials=max(0, len(direct) - len(materials)),
                 scope='Checkpoint originals only; not a stage seal, scientific qualification or restart permission.')
    if len(_bytes(value)) > MAX_BYTES:
        raise ValueError('Fragment checkpoint exceeds its byte capacity')
    c.write(destination, value)
    destination.chmod(0o400)
    return validate(root, job, record)


def validate(root, job, record):
    """Verify this attempt and its immutable snapshots without reading later work."""
    root, record = Path(root), Path(record)
    value = c.read(c.regular(record / 'checkpoint.json', limit=MAX_BYTES))
    if value.get('version') != VERSION or value.get('binding') != _binding(root, job, record):
        raise ValueError('Fragment checkpoint binding changed')
    for row in value['originals']:
        path = root / row['path']
        if (path.parent != record or path.name not in NATIVE_ORIGINALS
                or c.digest(c.regular(path, limit=MAX_BYTES)) != row['sha256']
                or path.stat().st_size != row['size_bytes']):
            raise ValueError('Fragment native original changed')
    expected, _ = _science(root, job, value['originals'])
    if value['science'] != expected:
        raise ValueError('Fragment scientific output diagnosis changed')
    for row in value['materials']:
        original = row['original']
        if original['retention'] == 'archived':
            path = root / original['snapshot']
            if (path.resolve() != path or not path.is_relative_to(root / 'host-history/objects')
                    or c.digest(c.regular(path, limit=history.MAX_HISTORY_BYTES)) != original['sha256']
                    or path.stat().st_size != original['size_bytes']):
                raise ValueError('Fragment direct-deliverable snapshot changed')
    return value


def _clip(value, limit):
    data = value.encode('utf-8')
    return data[:limit].decode('utf-8', errors='ignore'), len(data) > limit


def end_stage(root, job, record, reason):
    """Record why control ended this stage without rewriting scientific bytes."""
    root, record = Path(root), Path(record)
    saved = validate(root, job, record)
    value = dict(version=VERSION, binding=saved['binding'], reason=reason,
                 checkpoint_sha256=c.digest(record / 'checkpoint.json'),
                 raw_sha256=c.digest(c.regular(record / 'science-output.json')))
    path = record / 'stage-end.json'
    if path.exists() or path.is_symlink():
        if stage_end(root, job, record) != value:
            raise ValueError('Scientific stage ending changed its original control reason')
    else:
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 128:
            raise ValueError('Stage ending requires a bounded control reason')
        c.write(path, value)
        path.chmod(0o400)
    return value


def stage_end(root, job, record):
    root, record = Path(root), Path(record)
    value = c.read(c.regular(record / 'stage-end.json', limit=MAX_BYTES))
    if (value.get('version') != VERSION or value.get('binding') != _binding(root, job, record)
            or value.get('checkpoint_sha256') != c.digest(c.regular(record / 'checkpoint.json'))
            or value.get('raw_sha256') != c.digest(c.regular(record / 'science-output.json'))
            or not isinstance(value.get('reason'), str) or not value['reason'].strip() or len(value['reason']) > 128):
        raise ValueError('Scientific stage ending differs from its exact fragment originals')
    return value


def brief(root, job, record):
    """Return at most 4KB of ordinary science and direct-file availability.

    Host paths, hashes, raw logs and private execution bindings are omitted. Full
    originals stay in the checkpoint; omissions never become inferred evidence.
    """
    root, record = Path(root), Path(record)
    value = validate(root, job, record)
    _, science = _science(root, job, value['originals'])
    result = dict(task='science-task.json', science_status=value['science']['status'], scientific_summary=None,
                  current_understanding=None, limitations=[], omitted_limitations=0, direct_files=[],
                  omitted_files=value['omitted_materials'], truncated=False,
                  material_status=value['material_status'],
                  missing_native_originals=value['missing_native_originals'],
                  scope='Fragment preview; original task and permissions remain binding. No restart or scientific qualification is granted.')
    if science is not None:
        result['scientific_summary'], a = _clip(science['summary'], 384)
        result['current_understanding'], b = _clip(science['scientific_result'], 1400)
        result['limitations'] = [_clip(item, 192)[0] for item in science['limitations'][:4]]
        result['omitted_limitations'] = max(0, len(science['limitations']) - len(result['limitations']))
        result['truncated'] = a or b or len(science['limitations']) > 4 or any(
            len(item.encode()) > 192 for item in science['limitations'][:4])
    for row in value['materials']:
        name, clipped = _clip(row['name'], 256)
        result['direct_files'].append(dict(name=name, name_truncated=clipped,
            retention=row['original']['retention']))
    while len(_bytes(result)) > MAX_BRIEF_BYTES and result['direct_files']:
        result['direct_files'].pop()
        result['omitted_files'] += 1
    while len(_bytes(result)) > MAX_BRIEF_BYTES and result['limitations']:
        result['limitations'].pop()
        result['omitted_limitations'] += 1
        result['truncated'] = True
    # UTF-8 lengths alone do not bound JSON: quotes, backslashes and controls
    # expand during encoding. Trim only scientific excerpts using the actual
    # bytes written by c.write, preserving diagnosis and omission metadata.
    for field in ('current_understanding', 'scientific_summary'):
        while len(_bytes(result)) > MAX_BRIEF_BYTES and result[field]:
            result[field] = _clip(result[field], len(result[field].encode()) // 2)[0]
            result['truncated'] = True
    if len(_bytes(result)) > MAX_BRIEF_BYTES:
        raise ValueError('Fragment resume brief exceeds its byte capacity')
    return result


def disposition(science, *, review_requested=False):
    """Interpret only the W intent; host review can end a continuing stage.

    This internal seam is enabled by the final U3 schema, not a protocol upgrade
    or alternate execution contract by itself.
    """
    if science is None:
        return 'repair'
    intent = science.get('stage_intent')
    if intent not in {'continue', 'review'}:
        raise OutputRepairRequired('stage_intent_invalid', 'Express whether to continue this mechanism or request independent A review.')
    return 'review' if review_requested or intent == 'review' else 'continue'
