"""Rebuildable scientific history and optional host observations; no attachments."""
from __future__ import annotations

from . import execution

import hashlib
import json
import math
import os
from pathlib import Path
import re
import resource
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlsplit

from . import contracts as c

PAGE_ROWS = 8
TEXT_CHARS = 8192
MAX_PAGE_BYTES = 64_000
MAX_HISTORY_BYTES = 32 * 1024 * 1024
MAX_BRIEF_BYTES = 4096


class UnresolvedImplementation(ValueError):
    """A scientific object choice has no unique frozen original; not corruption."""
MAX_OBSERVER_BYTES = 256_000
MAX_OBJECT_BYTES = 128 * 1024 * 1024
OBSERVER_SECONDS = 5
MAX_CANDIDATES = 128
ID = re.compile(r'[A-Za-z0-9._-]{1,80}\Z')
HANDLE = re.compile(r'history/nodes/([0-9]{3,})/artifacts/(.+)\Z')


class ObserverIntegrityError(ValueError):
    pass


def _bytes(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n').encode()


def observer_config(value):
    """Freeze a trusted synchronous, side-effect-free external adapter."""
    if (not isinstance(value, dict) or set(value) not in ({'adapter','config'},{'adapter','config','contract_version'})
            or not isinstance(value['config'],dict) or 'contract_version' in value and (type(value['contract_version']) is not int or value['contract_version'] != 2)):
        raise ValueError('Observer requires an exact adapter and configuration')
    path = Path(value['adapter']).absolute()
    if path.resolve() != path or len(_bytes(value['config'])) > MAX_PAGE_BYTES:
        raise ValueError('Observer requires an original bounded configuration')
    c.regular(path, limit=MAX_OBSERVER_BYTES)
    return dict(adapter=str(path), adapter_sha256=c.digest(path), config=value['config'],
                **(dict(contract_version=2) if value.get('contract_version') == 2 else {}))


def handle(row):
    # Existing four-field paths retain the original node ownership.
    parts = Path(row['path']).parts
    return 'history/nodes/' + '/'.join(parts[2:])


def resolve(root, target, receipts, *, current=None):
    match = HANDLE.fullmatch(target)
    if not match or '..' in Path(target).parts or '\\' in target or unquote(target) != target:
        raise ValueError('History reuse requires an exact historical implementation handle')
    step = int(match[1])
    if match[1] != f'{step:03d}':
        raise ValueError('History node identity is not canonical')
    if current is not None and step == current['step']:
        rows = current['materials']
    else:
        receipt = next((row for row in receipts if row['step'] == step), None)
        if receipt is None:
            raise ValueError('Historical implementation is outside the frozen history')
        path = c.host_record(c.workspace(root, step)) / 'result-identity.json'
        if c.digest(c.regular(path)) != receipt['seal_sha256']:
            raise ValueError('Historical node seal changed')
        rows = c.read(path)['materials']
    row = next((row for row in rows if handle(row) == target), None)
    if row is None:
        raise ValueError('Historical implementation is not an exact sealed deliverable')
    return row


def _proof(root, source, read_limit=MAX_OBJECT_BYTES):
    if not isinstance(source, str):
        raise ValueError('Observer evidence path is not a string')
    path = root / source
    if Path(source).is_absolute() or '..' in Path(source).parts or path.resolve() != path:
        raise ObserverIntegrityError('Observer evidence must be an exact instance original')
    c.regular(path)
    size = path.stat().st_size
    if size > min(MAX_HISTORY_BYTES, read_limit):
        return dict(path=source, sha256=None, size_bytes=size, retention='unavailable', reason='read_capacity')
    data = path.read_bytes()
    if len(data) > MAX_HISTORY_BYTES:
        raise ValueError('Observer source exceeded its read capacity')
    sha = hashlib.sha256(data).hexdigest()
    objects = root / 'host-history/objects'
    snapshot = objects / sha
    if objects.resolve() != objects or snapshot.is_symlink():
        raise ObserverIntegrityError('Observer archive must contain original files')
    if snapshot.exists():
        if not snapshot.is_file() or c.digest(c.regular(snapshot, limit=MAX_HISTORY_BYTES)) != sha:
            raise ObserverIntegrityError('Archived observer original changed')
    else:
        total = sum(row.stat().st_size for row in objects.iterdir()) if objects.exists() else 0
        if total + len(data) > MAX_OBJECT_BYTES:
            return dict(path=source, sha256=sha, size_bytes=len(data), retention='digest_only', reason='total_capacity')
        objects.mkdir(parents=True, exist_ok=True)
        if objects.resolve() != objects:
            raise ObserverIntegrityError('Observer archive must be an original directory')
        temporary = objects / (sha + '.tmp')
        if temporary.exists() or temporary.is_symlink():
            raise ObserverIntegrityError('Observer archive has an uncertain temporary original')
        with temporary.open('xb') as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
        temporary.chmod(0o400);temporary.replace(snapshot)
    return dict(path=source, sha256=sha, size_bytes=len(data), retention='archived',
                snapshot=snapshot.relative_to(root).as_posix())


def _capture(root, job, payload, materials):
    """Snapshot mechanical adapter facts once, before the scientific seal."""
    config = c.settings(root).get('history_observer')
    if config is None:
        return None
    adapter = c.regular(Path(config['adapter']), limit=MAX_OBSERVER_BYTES)
    if adapter.resolve() != adapter or c.digest(adapter) != config['adapter_sha256']:
        raise ObserverIntegrityError('Frozen observer adapter changed')
    raw = execution.raw(root, job['step'])
    source_sha = c.digest(c.regular(raw, limit=c.MAX_RESULT_BYTES))
    path = root / 'host-history/observations' / f'{job["step"]:03d}.json'
    binding = _observer_binding(source_sha, config)
    if path.exists():
        stored = c.read(c.regular(path, limit=MAX_OBSERVER_BYTES))
        if stored.get('binding') != binding:
            raise ObserverIntegrityError('Retained observer snapshot binding changed')
        return dict(path=path.relative_to(root).as_posix(), sha256=c.digest(path))
    known = set();known_contexts = set();prior_contexts = []
    for receipt in job.get('history', {}).get('nodes', []):
        old_seal = c.read(c.host_record(c.workspace(root, receipt['step'])) / 'result-identity.json')
        observation = old_seal.get('observations')
        if observation:
            old_path = root / observation['path']
            if c.digest(c.regular(old_path, limit=MAX_OBSERVER_BYTES)) != observation['sha256']:
                raise ObserverIntegrityError('Sealed observer snapshot changed')
            prior = c.read(old_path)
            known.update(row['id'] for row in prior['candidates'])
            known_contexts.update(row['call_id'] for row in prior.get('contexts', []))
            prior_contexts.extend(prior.get('contexts', []))
    request = dict(root=str(root), step=job['step'], config=config['config'], materials=materials,
                   known_candidates=sorted(known),
                   **(dict(known_contexts=sorted(known_contexts)) if config.get('contract_version') == 2 else {}))
    if len(_bytes(request)) > MAX_OBSERVER_BYTES:
        raise ValueError('Observer input exceeds byte bound')
    def bound_output():
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OBSERVER_BYTES, MAX_OBSERVER_BYTES))
    # Trusted adapters must be synchronous and must not spawn children or effects.
    # This is a small observation call, not an execution/recovery engine.
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        result = subprocess.run([sys.executable, '-I', str(adapter)], input=_bytes(request),
            stdout=out, stderr=err, timeout=OBSERVER_SECONDS, env={'PATH': os.defpath}, preexec_fn=bound_output)
        out.seek(0)
        data = out.read(MAX_OBSERVER_BYTES + 1)
    if result.returncode:
        raise ValueError('Observer output capacity exceeded' if result.returncode == -25 else 'Observer adapter failed')
    if len(data) > MAX_OBSERVER_BYTES:
        raise ValueError('Observer output capacity exceeded')
    value = json.loads(data)
    if config.get('contract_version') == 2 and isinstance(value,dict) and set(value)=={'integrity_error'}:
        raise ObserverIntegrityError(str(value['integrity_error']))
    expected = {'candidates','current_candidate','actual_submission','coverage'}
    if config.get('contract_version') == 2:expected.add('contexts')
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError('Observer must return candidates and actual_submission separately')
    if not isinstance(value['candidates'], list) or len(value['candidates']) > MAX_CANDIDATES:
        raise ValueError('Observer candidate count exceeds bound')
    coverage = value['coverage']
    if not isinstance(coverage, dict) or set(coverage) != {'status', 'note'} or coverage['status'] not in ('complete', 'partial', 'unavailable') or not isinstance(coverage['note'], str) or len(coverage['note']) > 256:
        raise ValueError('Observer coverage requires an explicit bounded status')
    proof_cache, read_bytes = {}, 0
    def proof(name):
        nonlocal read_bytes
        if not isinstance(name, str):
            raise ValueError('Observer original path is not a string')
        if name not in proof_cache:
            item = _proof(root, name, MAX_OBJECT_BYTES - read_bytes)
            if item['sha256'] is not None:
                read_bytes += item['size_bytes']
            proof_cache[name] = item
        return proof_cache[name]
    candidates, seen = [], set()
    receipts = job.get('history', {}).get('nodes', [])
    for item in value['candidates']:
        if not isinstance(item, dict) or set(item) != {'id', 'label', 'implementation', 'evaluation_key', 'metric', 'direction', 'status', 'evidence'}:
            raise ValueError('Observer candidate fields differ from the interface')
        if (not isinstance(item['id'], str) or not ID.fullmatch(item['id']) or item['id'] in seen or item['id'] in known
                or not isinstance(item['label'], str) or len(item['label']) > 160
                or not isinstance(item['evaluation_key'], str) or len(item['evaluation_key']) > 512
                or item['direction'] not in ('max', 'min') or item['status'] not in ('ok', 'failed', 'unknown')
                or (item['metric'] is not None and (type(item['metric']) not in (int, float) or not math.isfinite(item['metric'])))):
            raise ValueError('Observer candidate identity or metric is invalid')
        seen.add(item['id'])
        implementation = item['implementation']
        if implementation is not None:
            resolve(root, implementation, receipts, current=dict(step=job['step'], materials=materials))
        if not isinstance(item['evidence'], list) or not 1 <= len(item['evidence']) <= 8:
            raise ValueError('Observer candidates require bounded original evidence')
        candidates.append({**item, 'evidence': [proof(name) for name in item['evidence']]})
    if len(known | seen) > 4096:
        raise ValueError('Historical candidate count exceeds observation capacity')
    current = value['current_candidate']
    if current is not None:
        if (not isinstance(current, dict) or set(current) != {'candidate_id', 'evidence'}
                or current['candidate_id'] not in seen | known
                or not isinstance(current['evidence'], list) or not 1 <= len(current['evidence']) <= 8):
            raise ValueError('Current candidate requires a known identity and original evidence')
        current = dict(candidate_id=current['candidate_id'], evidence=[proof(name) for name in current['evidence']])
    actual = value['actual_submission']
    if actual is not None:
        if (not isinstance(actual, dict) or set(actual) != {'candidate_id', 'artifact', 'evidence'}
                or (actual['candidate_id'] is not None and actual['candidate_id'] not in seen | known)
                or not isinstance(actual['evidence'], list) or not 1 <= len(actual['evidence']) <= 8):
            raise ValueError('Actual submission requires an original artifact and evidence')
        actual = dict(candidate_id=actual['candidate_id'], artifact=proof(actual['artifact']),
                      evidence=[proof(name) for name in actual['evidence']])
    contexts = None
    if config.get('contract_version') == 2:
        from . import lineage
        contexts = lineage.contexts(root, job, value['contexts'], proof, prior_contexts)
        if any(row['status']=='unknown' for row in contexts):
            coverage = dict(status='partial',note='Original execution contexts include unknown outcomes.')
    snapshot = dict(binding=binding, candidates=candidates, current_candidate=current, actual_submission=actual, coverage=coverage,
                    **(dict(contexts=contexts) if contexts is not None else {}))
    if len(_bytes(snapshot)) > MAX_OBSERVER_BYTES:
        raise ValueError('Observer snapshot exceeds byte bound')
    c.write(path, snapshot)
    return dict(path=path.relative_to(root).as_posix(), sha256=c.digest(path))


def capture(root, job, payload, materials):
    """Optional capacity/availability failures never discard original science."""
    config = c.settings(root).get('history_observer')
    if config is None:
        return None
    adapter = c.regular(Path(config['adapter']), limit=MAX_OBSERVER_BYTES)
    if adapter.resolve() != adapter or c.digest(adapter) != config['adapter_sha256']:
        raise ObserverIntegrityError('Frozen observer adapter changed')
    path = root / 'host-history/observations' / f'{job["step"]:03d}.json'
    if path.exists():
        return _capture(root, job, payload, materials)  # Never repair an uncertain snapshot.
    try:
        return _capture(root, job, payload, materials)
    except ObserverIntegrityError:
        raise
    except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired) as error:
        code = ('timeout' if isinstance(error, subprocess.TimeoutExpired) else
                'malformed' if isinstance(error, json.JSONDecodeError) else
                'capacity' if 'capacity' in str(error) or 'bound' in str(error) else
                'adapter_io' if isinstance(error, OSError) else 'invalid_output')
        raw = execution.raw(root, job['step'])
        value = dict(binding=_observer_binding(c.digest(c.regular(raw,limit=c.MAX_RESULT_BYTES)),config),
                     candidates=[], current_candidate=None, actual_submission=None,
                     **(dict(contexts=[]) if config.get('contract_version') == 2 else {}),
                     coverage=dict(status='unavailable', note='Observer returned no verified bounded facts; original science is retained.'),
                     diagnostic=dict(failure_type=type(error).__name__, error_code=code))
        c.write(path, value)
        return dict(path=path.relative_to(root).as_posix(), sha256=c.digest(path))


def _source(root, step):
    record = c.host_record(c.workspace(root, step))
    seal_path = c.regular(record / 'result-identity.json')
    seal = c.read(seal_path)
    raw = c.regular(execution.raw(root, step), limit=c.MAX_RESULT_BYTES)
    job_path = c.regular(root / 'jobs' / f'{step:03d}.json')
    if (c.digest(raw) != seal['raw_sha256'] or c.digest(job_path) != seal['job_sha256']
            or c.digest(c.regular(record / 'result.json')) != seal['sha256']):
        raise ValueError('Historical scientific source changed')
    job = c.read(job_path)
    if job.get('handoff_protocol', 1) >= 3:
        validate_observation(root, job, seal)
    return job, c.read(raw), seal, c.digest(seal_path)


def direct_sources(root, job):
    """Verify frozen input ownership, without asserting scientific support."""
    sources, seen = [], set()
    for ref in job['direct_refs']:
        match = re.fullmatch(r'inputs/parents/([0-9]{3,})/conclusion\.json', ref['path'])
        if match is None:
            raise ValueError('Direct scientific input has no exact node identity')
        step = int(match[1])
        if step in seen or match[1] != f'{step:03d}' or not 0 < step < job['step']:
            raise ValueError('Direct scientific input identity is ambiguous')
        seen.add(step)
        source, payload, seal, _ = _source(root, step)
        record = c.host_record(c.workspace(root, step))
        outcome = c.read(c.regular(execution.record(root, step) / 'native-outcome.json'))
        if (c.digest(c.regular(c.workspace(root, job['step']) / ref['path'])) != ref['sha256']
                or ref['sha256'] != seal['raw_sha256']
                or c.read(execution.record(root, step) / 'native-intent.json')['task_sha256'] != seal['job_sha256']
                or type(outcome.get('returncode')) is not int or outcome['returncode'] != 0 or outcome.get('stop_reason')
                or outcome.get('usage', {}).get('unknown_steps') != []
                or outcome.get('raw_sha256') != seal['raw_sha256']
                or c.read(record / 'result.json') != c.envelope(source, payload)):
            raise ValueError('Direct scientific original or terminal identity changed')
        sources.append((source, payload, seal))
    return sources


def implementation_options(root, step):
    job, _, seal, _ = _source(root, step)
    return [dict(id=f'{job["role"]}{step:03d}-I{index:03d}',
                 label=Path(row['path']).name.encode()[:160].decode('utf-8', errors='ignore'))
            for index, row in enumerate(sorted(seal['materials'], key=lambda row: row['path']), 1)]


def resolve_implementation(root, object_id, receipts):
    match = re.fullmatch(r'([HWAE])([0-9]{3,})-I([0-9]{3,})', object_id)
    if match is None:
        raise UnresolvedImplementation('Implementation selection requires a listed scientific object ID')
    step, index = int(match[2]), int(match[3])
    receipt = next((row for row in receipts if row['step'] == step), None)
    job, _, seal, seal_sha = _source(root, step) if receipt else (None, None, None, None)
    if receipt is not None and seal_sha != receipt['seal_sha256']:
        raise ValueError('Historical node seal changed')
    if (receipt is None or job['role'] != match[1]
            or object_id != f'{job["role"]}{step:03d}-I{index:03d}' or index < 1
            or index > len(seal['materials'])):
        raise UnresolvedImplementation('Implementation selection is outside its exact frozen source')
    return sorted(seal['materials'], key=lambda row: row['path'])[index - 1]


def source_sequence(root, before_step, *, source_cutoff=None, extra_steps=()):
    """Recreate small node projections from originals; caches are not authority."""
    sources = []
    if source_cutoff is None:
        steps = list(range(1, before_step))
        if extra_steps:
            raise ValueError('Ordinary history cannot skip scientific originals')
    else:
        if type(source_cutoff) is not int or not 0 <= source_cutoff < before_step:
            raise ValueError('Invalid frozen scientific source cutoff')
        if (list(extra_steps) != sorted(set(extra_steps))
                or any(type(step) is not int or not source_cutoff < step < before_step for step in extra_steps)):
            raise ValueError('Closeout history requires exact preceding corrective nodes')
        steps = [*range(1, source_cutoff + 1), *extra_steps]
    for step in steps:
        if source_cutoff is not None:
            c.validate(c.workspace(root, step))
            if step > source_cutoff:
                extra = c.read(root / 'jobs' / f'{step:03d}.json')
                if extra.get('purpose') != 'closeout' or extra.get('source_cutoff') != source_cutoff:
                    raise ValueError('Closeout history cannot include an unrelated stopped node')
        sources.append(_source(root, step))
    return sources


def records_from_sources(root, sources, *, write_cache=True):
    records, current_h = [], None
    for job, payload, seal, seal_sha in sources:
        step = job["step"]
        if job['role'] == 'H':
            current_h = step
        parents = [int(Path(ref['path']).parts[2]) for ref in job['direct_refs']]
        h_parents = list(dict.fromkeys(record['view']['h_scope'] for record in records if record['step'] in parents and record['view']['h_scope'] is not None))
        ordered = {row['path']: row for row in seal['materials']}
        preferred = [row['path'] for row in seal.get('entry_points', []) if row['path'] in ordered]
        paths = list(dict.fromkeys([*preferred, *ordered]))
        entries = [dict(path=handle(ordered[name])) for name in paths if len(handle(ordered[name])) <= 512][:16]
        limitations = payload['limitations']
        view = dict(step=step, role=job['role'], summary=payload['summary'][:512],
            summary_omitted_chars=max(0, len(payload['summary']) - 512),
            limitations=[value[:256] for value in limitations[:4]],
            limitations_omitted_count=max(0, len(limitations) - 4),
            limitations_omitted_chars=sum(max(0, len(value) - 256) for value in limitations[:4]),
            h_scope=current_h, h_parents=h_parents, implementations=entries,
            implementations_omitted_count=len(paths) - len(entries),
            conclusion_pages=[])
        # Source authors retain the complete bounded original scientific fields.
        # Only the index excerpt is shortened; current roles can read text pages.
        text = json.dumps(payload, ensure_ascii=False)
        detail = [dict(step=step, role=job['role'], source='node:%03d/scientific-output' % step,
                       part=index + 1, parts=(len(text) + TEXT_CHARS - 1) // TEXT_CHARS,
                       text=text[start:start + TEXT_CHARS])
                  for index, start in enumerate(range(0, len(text), TEXT_CHARS))]
        for index in range(len(detail)):
            view['conclusion_pages'].append(f'inputs/history/nodes/{step:03d}/{index + 1:04d}.json')
        observation = None
        if seal.get('observations'):
            receipt = seal['observations'];path = root / receipt['path']
            if c.digest(c.regular(path, limit=MAX_OBSERVER_BYTES)) != receipt['sha256']:
                raise ObserverIntegrityError('Sealed observer snapshot changed')
            observation = c.read(path)
            if observation['binding']['source_sha256'] != seal['raw_sha256']:
                raise ValueError('Observer snapshot differs from scientific source')
        row = dict(step=step, role=job['role'], seal_sha256=seal_sha, view=view, detail=detail,
                   recommendation=payload.get('candidate_recommendation') if job['role'] == 'A' and payload.get('next_action') != 'audit' else None,
                   observation=observation)
        if job.get('handoff_protocol', 1) >= 9 and payload.get('next_action') == 'audit':
            row['audit_request'] = True
        # Replacing a disposable projection repairs deletion/corruption; originals
        # and sealed observer snapshots above remain independently verified.
        if write_cache:
            c.write(root / 'host-history/nodes' / f'{step:03d}.json', row)
        records.append(row)
    return records


def rebuild(root, before_step, *, source_cutoff=None, extra_steps=(), write_cache=True):
    """Legacy layout, using the same verified source boundary as lineage."""
    return records_from_sources(root, source_sequence(root, before_step, source_cutoff=source_cutoff, extra_steps=extra_steps),
                                write_cache=write_cache)

def candidate_overview(records):
    from . import lineage
    return lineage.candidate_view(records)


def page_writer(work):
    files, total = [], 0
    def add(path, value):
        nonlocal total
        data = _bytes(value)
        total += len(data)
        if len(data) > MAX_PAGE_BYTES or total > MAX_HISTORY_BYTES:
            raise ValueError('Scientific history exceeds its bounded page capacity')
        destination = work / path
        # _copy_bound checks existing data and all destination directory symlinks.
        with tempfile.TemporaryDirectory() as temporary:
            original = Path(temporary) / 'page.json';original.write_bytes(data)
            c._copy_bound(original, destination, hashlib.sha256(data).hexdigest())
        files.append(dict(path=path, sha256=c.digest(destination), size_bytes=len(data)))
    def paged(rows, row_limit, key, prefix, source=None):
        groups, group = [], []
        # Use the longest possible continuation path and count in packing checks.
        def value(items, next_page, omitted):
            return {key: items, 'next_page': next_page, 'omitted_count': omitted,
                    **(dict(source=source) if source else {})}
        maximum_next = f'{prefix}/{max(1, len(rows)):04d}.json'
        for row in rows:
            tentative = [*group, row]
            if group and (len(tentative) > row_limit or len(_bytes(value(tentative, maximum_next, len(rows)))) > MAX_PAGE_BYTES):
                groups.append(group);group = []
            group.append(row)
            if len(_bytes(value(group, maximum_next, len(rows)))) > MAX_PAGE_BYTES:
                raise ValueError('One scientific history record exceeds page capacity')
        if group:
            groups.append(group)
        paths, remaining = [], len(rows)
        for index, items in enumerate(groups):
            path = f'{prefix}/{index + 1:04d}.json';paths.append(path)
            remaining -= len(items)
            next_page = f'{prefix}/{index + 2:04d}.json' if index + 1 < len(groups) else None
            add(path, value(items, next_page, remaining))
        return paths
    return add, paged, files


def bind(root, step, protocol=6, *, source_cutoff=None, extra_steps=()):
    records = rebuild(root, step, source_cutoff=source_cutoff, extra_steps=extra_steps)
    if protocol >= 7:
        for record in records:
            options = implementation_options(root, record['step'])
            record['view']['implementations'] = options[:16]
            record['view']['implementations_omitted_count'] = max(0, len(options) - 16)
    add, paged, files = page_writer(c.workspace(root, step))
    if protocol >= 7:
        for record in records:
            paths = paged(implementation_options(root, record['step']), 16, 'implementations',
                          f'inputs/history/implementations/{record["step"]:03d}', 'sealed-implementation-objects')
            record['view']['implementation_index'] = paths[0] if paths else None
    pages = paged([row['view'] for row in records], PAGE_ROWS, 'records',
                  'inputs/history/pages', 'sealed-scientific-nodes')
    for record in records:
        for path, value in zip(record['view']['conclusion_pages'], record['detail']):
            add(path, value)
    overview = candidate_overview(records)
    candidate_index = overview.pop('candidate_index')
    paged(candidate_index, 16, 'candidates', 'inputs/history/candidates')
    overview['index'] = 'inputs/history/candidates/0001.json' if candidate_index else None
    add('inputs/history/candidates.json', overview)
    def brief(record):
        original = record['view']
        def clip(text, capacity):
            return text.encode()[:capacity].decode('utf-8', errors='ignore')
        return dict(step=record['step'], role=record['role'], summary=clip(original['summary'], 160),
                    limitations=[clip(value, 96) for value in original['limitations'][:1]],
                    detail=original['conclusion_pages'][0],
                    summary_truncated=(len(original['summary'].encode()) > 160 or original['summary_omitted_chars'] > 0),
                    limitations_omitted_count=max(0, len(original['limitations']) - 1) + original['limitations_omitted_count'],
                    limitations_truncated=any(len(value.encode()) > 96 for value in original['limitations'][:1]) or original['limitations_omitted_chars'] > 0)
    view = dict(index=pages[0] if pages else None, node_count=len(records), page_rows=PAGE_ROWS,
        recent=[brief(row) for row in records[-3:]],
        declared_limitations=[dict(step=row['step'], limitations=[value.encode()[:96].decode('utf-8', errors='ignore') for value in row['view']['limitations'][:1]], detail=row['view']['conclusion_pages'][0], truncated=any(len(value.encode()) > 96 for value in row['view']['limitations'][:1]) or row['view']['limitations_omitted_chars'] > 0, omitted_count=max(0, len(row['view']['limitations']) - 1) + row['view']['limitations_omitted_count']) for row in records if row['view']['limitations']][-3:],
        h_lineage=[dict(step=row['step'], parents=row['view']['h_parents']) for row in records if row['role'] == 'H'][-8:],
        h_lineage_omitted_count=max(0, sum(row['role'] == 'H' for row in records) - 8),
        candidates='inputs/history/candidates.json',
        access='Read one index or conclusion page as needed; these are original scientific fields, not new host conclusions. '
        'Implementation handles are not mounted files. To give the next role an exact old implementation, link its history/nodes/.../artifacts/... handle with #reuse-implementation. '
        'Historical text may cite unavailable attachments; citations never mount them. Ordinary citations only cite evidence. A may optionally report candidate_recommendation using a listed candidate ID.')
    if protocol >= 7:
        view['access'] = ('Read index pages for navigation and node conclusion pages for original science. '
            'Implementation IDs name exact retained objects, not mounted files. For more than the first 16, '
            'read implementation_index and next_page for further IDs; unselected objects are not mounted. '
            'implementation_selection: null keeps only the already selected inputs, [] clears, and an ID list replaces them. '
            'New direct deliverables pass automatically. Ordinary citations never select implementations. '
            'candidate_recommendation is an independent scientific recommendation, not input selection or actual submission.')
    if len(_bytes(view)) > MAX_BRIEF_BYTES:
        raise ValueError('Default scientific history brief exceeds byte bound')
    return dict(nodes=[dict(step=row['step'], seal_sha256=row['seal_sha256']) for row in records],
                files=files, candidate_ids=[row['id'] for row in candidate_index], view=view)


def validate(root, work, binding):
    for row in binding['nodes']:
        _, _, _, seal_sha = _source(root, row['step'])
        if seal_sha != row['seal_sha256']:
            raise ValueError('Frozen historical node identity changed')
    for row in binding['files']:
        path = work / row['path']
        if c.digest(c.regular(path, limit=MAX_PAGE_BYTES)) != row['sha256'] or path.stat().st_size != row['size_bytes']:
            raise ValueError('Bound scientific history page changed')


def validate_recommendation(job, payload):
    recommendation = payload.get('candidate_recommendation')
    if job.get('handoff_protocol', 1) >= 9 and payload.get('next_action') == 'audit':
        return  # An unavailable audit request preserves science and returns a host diagnostic.
    if recommendation is not None and (job['role'] != 'A' or recommendation not in job['history']['candidate_ids']):
        raise ValueError('A recommendation requires one frozen listed candidate')


def validate_observation(root, job, seal):
    receipt = seal.get('observations')
    config = c.settings(root).get('history_observer')
    if config is None:
        if receipt is not None:
            raise ValueError('Unconfigured observer snapshot in scientific seal')
        return
    if receipt is None:
        raise ValueError('Configured observer snapshot missing from scientific seal')
    path = root / receipt['path']
    expected = root / 'host-history/observations' / f'{job["step"]:03d}.json'
    if path != expected or c.digest(c.regular(path, limit=MAX_OBSERVER_BYTES)) != receipt['sha256']:
        raise ObserverIntegrityError('Sealed observer snapshot changed')
    value = c.read(path)
    if value['binding'] != _observer_binding(seal['raw_sha256'], config):
        raise ValueError('Observer snapshot source binding changed')
    proofs = [proof for row in value['candidates'] for proof in row['evidence']]
    for field in ('current_candidate', 'actual_submission'):
        if value.get(field):
            proofs.extend(value[field]['evidence'])
    if value.get('actual_submission'):
        proofs.append(value['actual_submission']['artifact'])
    if config.get('contract_version') == 2:
        for context in value.get('contexts', []):
            proofs.extend(context['proofs'])
            if context.get('model'):proofs.append(context['model'])
    for proof in proofs:
        _validate_proof(root, proof)


def _validate_proof(root, proof):
    if proof.get('retention') != 'archived':
        return
    expected = 'host-history/objects/' + proof['sha256']
    if proof.get('snapshot') != expected or c.digest(c.regular(root / expected, limit=MAX_HISTORY_BYTES)) != proof['sha256']:
        raise ObserverIntegrityError('Archived observer original changed')


def refresh(root, before_step):
    """Update disposable projections after every seal, including a terminal A."""
    latest = c.read(root / 'jobs' / f'{before_step-1:03d}.json') if before_step > 1 else {}
    if latest.get('lineage_projection_version') == 1:
        from . import lineage
        overview = lineage.project(root, before_step)['candidates']
    else:
        overview = candidate_overview(rebuild(root, before_step))
    overview.pop('candidate_index')
    if len(_bytes(overview)) > MAX_PAGE_BYTES:
        raise ValueError('Candidate overview exceeds its bounded projection capacity')
    c.write(root / 'host-history/overview.json', overview)


def _observer_binding(source_sha, config):
    return dict(source_sha256=source_sha,adapter_sha256=config['adapter_sha256'],
                **(dict(contract_version=2) if config.get('contract_version') == 2 else {}))
