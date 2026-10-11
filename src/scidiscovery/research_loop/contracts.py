"""Thin scientific packets and exact direct-node seals; no MCP dispatch protocol.

Only the controller supplies identities and lineage. These seals attest bytes,
not scientific validity, independent qualification or external-effect authority.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import re
from urllib.parse import unquote, urlsplit

MAX_RESULT_BYTES = 64_000
ACTIONS = {
    'H': ('experiment', 'analyze', 'extract', 'wait'),
    'A': ('continue_w', 'revise_h', 'extract', 'wait', 'finish'),
}
ROLE_INSTRUCTIONS = {
    'H': 'Own the scientific direction toward the original global goal. Propose or revise mechanisms, '
         'distinguishing hypotheses from implementation choices. Decide whether evidence extraction is needed, '
         'then choose experiment or independent analysis. Preserve original constraints and unmet questions.',
    'W': 'Work within the bound hypothesis scope. Choose implementation and bounded experiments yourself. '
         'Preserve observations, failures, candidate files and limitations. A new mechanism belongs to H. '
         'Return your contribution for independent A; do not declare global completion.',
    'A': 'Independently judge the contribution to the original global goal, not only local improvement. '
         'Check evaluation blind spots, contrary evidence and unexplored mechanisms. Request further W experiments '
         'within H, return to H for a mechanism revision, request evidence, wait or support a scoped conclusion. '
         'A self-built proxy alone does not establish performance under unobserved target conditions.',
    'E': 'Answer the exact evidence question from the requesting H or A. Retrieve or extract only needed materials '
         'using available functional tools. Preserve original sources, locators, conflicts and missing evidence. '
         'Return to the requester; do not choose the research direction or assert qualification.',
}


def read(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        os.chmod(temporary, 0o600)
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def digest(path: Path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def settings(root: Path):
    path = regular(root / 'settings.json')
    identity = read(regular(root / 'settings-identity.json'))
    # Read once: verify and parse the same bytes, not two racing reads.
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != identity.get('sha256'):
        raise ValueError('Frozen instance settings changed')
    return json.loads(data)


def workspace(root: Path, step: int):
    return root / 'project/nodes' / f'{step:03d}'


def host_record(work: Path):
    return work.parents[2] / 'native-evidence' / work.name


def regular(path: Path, *, limit=None):
    if path.is_symlink() or not path.is_file():
        raise ValueError('Expected an original regular file')
    if limit is not None and path.stat().st_size > limit:
        raise ValueError('File exceeds its declared byte budget')
    return path


def result_schema(role: str):
    if role not in ROLE_INSTRUCTIONS:
        raise ValueError('Unknown scientific role')
    properties = {
        'summary': {'type': 'string', 'minLength': 1},
        'scientific_result': {'type': 'string', 'minLength': 1},
        'limitations': {'type': 'array', 'items': {'type': 'string'}},
    }
    if role in ACTIONS:
        properties.update(next_action={'type': 'string', 'enum': list(ACTIONS[role])},
                          route_reason={'type': 'string', 'minLength': 1})
    return dict(type='object', properties=properties, required=list(properties), additionalProperties=False)


def science_payload(path: Path, role: str):
    import jsonschema
    value = read(regular(path, limit=MAX_RESULT_BYTES))
    try:
        jsonschema.validate(value, result_schema(role))
    except jsonschema.ValidationError as error:
        raise ValueError('Invalid scientific result fields') from error
    if any(not value[key].strip() for key in ('summary', 'scientific_result')) or (
            role in ACTIONS and not value['route_reason'].strip()):
        raise ValueError('Scientific content and routing reasons must be nonempty')
    return value


def envelope(job, payload):
    return {**payload, 'role': job['role'], 'direct_refs': job['direct_refs'],
            'next_action': payload.get('next_action', ''), 'route_reason': payload.get('route_reason', '')}


def _parent_view(job, ref):
    directory = str(Path(ref['path']).parent / 'artifacts')
    entries = [row for row in job.get('direct_entry_points', [])
               if row['path'].startswith(directory + '/')]
    view = dict(conclusion=ref['path'], artifacts=directory)
    if entries:
        view['evidence'] = entries[:16]
        if len(entries) > 16:
            view['evidence_omitted_count'] = len(entries) - 16
    return view


def artifact_entry_points(work, payload, materials):
    """Resolve explicit inline scientific links, never infer paths from prose."""
    targets = {Path(row['source']).relative_to(work).as_posix(): row['path'] for row in materials}
    entries, seen = [], set()
    links = re.finditer(r'\[([^\]\n]+)\]\((?:<([^>\n]+)>|([^\s()]+))\)', payload['scientific_result'])
    for link in links:
        label, angled, plain = link.groups()
        target = angled if angled is not None else plain
        url = urlsplit(target)
        if url.scheme or url.netloc:
            continue
        decoded = unquote(url.path)
        normalized = PurePosixPath(decoded)
        if not normalized.parts or normalized.parts[0] not in {'artifacts', 'experiments'}:
            continue
        if '..' in normalized.parts or url.query or '\\' in decoded:
            raise ValueError('Scientific artifact links require an exact local deliverable path')
        path = normalized.as_posix()
        if path not in targets:
            raise ValueError(f'Scientific artifact link {path!r} does not name a selected deliverable')
        if path not in seen:
            entries.append(dict(label=label[:160], path=targets[path]))
            seen.add(path)
    return entries


def science_view(job):
    return {key: value for key, value in {
        'role': job['role'], 'question': job['instruction'],
        'global': dict(objective='inputs/global/objective.md',
                       updates=[row['path'] for row in job['global_materials'][1:]]),
        'public_root': job['public_root'],
        'parents': [_parent_view(job, ref) for ref in job['direct_refs']],
        'final_response': list(result_schema(job['role'])['properties']),
        'outputs': 'artifacts/', 'scratch': 'work/',
        'experiments': 'experiments/<id>/{work/,artifacts/,conclusion.json or conclusion.md}; '
                       'child deliverables are collected by the host; scratch is excluded',
    }.items() if value}


def collect_materials(root: Path, step: int):
    """Collect selected deliverables; scratch and input trees never enter a seal."""
    policy = settings(root)
    work = workspace(root, step)
    rows, total = [], 0

    def add(path, relative):
        nonlocal total
        path = regular(path)
        size = path.stat().st_size
        if size > policy['max_output_item_bytes']:
            raise ValueError(f'Deliverable {relative!r} exceeds item byte budget '
                             f'({size} > {policy["max_output_item_bytes"]})')
        total += size
        if total > policy['max_output_total_bytes']:
            raise ValueError(f'Deliverable {relative!r} exhausts total byte budget '
                             f'({total} > {policy["max_output_total_bytes"]})')
        rows.append(dict(source=str(path), path=f'inputs/parents/{step:03d}/artifacts/{relative}',
                         sha256=digest(path), size_bytes=size))

    def artifacts(base, prefix=''):
        if not base.exists() and not base.is_symlink():
            return
        if base.is_symlink() or not base.is_dir():
            raise ValueError('Managed outputs must be an original directory')
        for directory, subdirs, files in os.walk(base, followlinks=False):
            for name in subdirs:
                if (Path(directory) / name).is_symlink():
                    raise ValueError('Managed output links are not sealed')
            for name in sorted(files):
                path = Path(directory) / name
                add(path, prefix + path.relative_to(base).as_posix())

    def experiments(base, prefix='experiments/'):
        if not base.exists() and not base.is_symlink():
            return
        if base.is_symlink() or not base.is_dir():
            raise ValueError('Experiments must be an original directory')
        for child in sorted(base.iterdir()):
            if child.is_symlink() or not child.is_dir():
                raise ValueError('Experiment nodes must be original directories')
            child_prefix = prefix + child.name + '/'
            artifacts(child / 'artifacts', child_prefix + 'artifacts/')
            for name in ('conclusion.json', 'conclusion.md'):
                path = child / name
                if path.exists() or path.is_symlink():
                    add(path, child_prefix + name)
            experiments(child / 'experiments', child_prefix + 'experiments/')

    artifacts(work / 'artifacts')
    experiments(work / 'experiments')
    if len({row['path'] for row in rows}) != len(rows):
        raise ValueError('Deliverable paths collide with nested experiment outputs')
    return sorted(rows, key=lambda row: row['path'])


def global_materials(root: Path):
    """Frozen original context shared by all nodes, with node-local read copies."""
    rows = settings(root)['global_materials']
    for row in rows:
        source = regular(root / row['source'])
        if digest(source) != row['sha256']:
            raise ValueError('Frozen global context changed')
    return rows


def _copy_bound(source: Path, destination: Path, sha256: str):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        if digest(regular(destination)) != sha256:
            raise ValueError('Bound input copy changed')
    else:
        shutil.copyfile(source, destination)
        destination.chmod(0o400)
    if digest(regular(destination)) != sha256:
        raise ValueError('Bound input copy changed')


def build_job(root: Path, step: int, role: str, parents: list[int], instruction='', evidence_return=None):
    if role not in ROLE_INSTRUCTIONS or type(step) is not int or step < 1:
        raise ValueError('Invalid scientific node')
    if len(parents) != len(set(parents)) or any(type(p) is not int or not 0 < p < step for p in parents):
        raise ValueError('Parents must be exact distinct preceding nodes')
    policy = settings(root)
    work = workspace(root, step)
    work.mkdir(parents=True, exist_ok=True)
    (work / 'work').mkdir(exist_ok=True)
    (work / 'artifacts').mkdir(exist_ok=True)
    globals_ = global_materials(root)
    for item in globals_:
        _copy_bound(root / item['source'], work / item['path'], item['sha256'])
    refs, materials, entry_points = [], [], []
    for parent in parents:
        source_work = workspace(root, parent)
        validate(source_work)
        # Pass the author's science, not the controller envelope and its parent
        # references. Historical lineage remains in the host-owned node tree.
        source = host_record(source_work) / 'science-output.json'
        ref = dict(path=f'inputs/parents/{parent:03d}/conclusion.json', sha256=digest(source))
        _copy_bound(source, work / ref['path'], ref['sha256'])
        (work / Path(ref['path']).parent / 'artifacts').mkdir(exist_ok=True)
        refs.append(ref)
        parent_seal = read(host_record(source_work) / 'result-identity.json')
        materials.extend(parent_seal['materials'])
        entry_points.extend(parent_seal.get('entry_points', []))
    for item in materials:
        _copy_bound(Path(item['source']), work / item['path'], item['sha256'])
    # No recursive parent expansion; per-file identities stay in host storage.
    job = dict(step=step, role=role, goal_text=policy['objective'], public_root=policy['public_root'],
               instruction=instruction, direct_refs=refs, direct_materials=materials, direct_entry_points=entry_points, global_materials=globals_,
               evidence_return=evidence_return)
    for path, value in ((root / 'jobs' / f'{step:03d}.json', job),
                        (work / 'science-task.json', science_view(job)),
                        (host_record(work) / 'science-result.schema.json', result_schema(role))):
        if path.exists():
            if read(regular(path)) != value:
                raise ValueError('Frozen scientific task changed')
        else:
            write(path, value)
    return job


def validate(work: Path):
    root = work.parents[2]
    job_path = root / 'jobs' / f'{int(work.name):03d}.json'
    job = read(regular(job_path))
    record = host_record(work)
    seal = read(regular(record / 'result-identity.json'))
    intent = read(regular(record / 'native-intent.json'))
    outcome = read(regular(record / 'native-outcome.json'))
    raw = regular(record / 'science-output.json', limit=MAX_RESULT_BYTES)
    result = regular(record / 'result.json', limit=MAX_RESULT_BYTES * 2)
    conclusion = regular(work / 'conclusion.json', limit=MAX_RESULT_BYTES)
    if (seal['job_sha256'] != digest(job_path) or intent['task_sha256'] != digest(job_path)
            or seal['raw_sha256'] != digest(raw) or seal['sha256'] != digest(result)
            or seal['raw_sha256'] != digest(conclusion) or outcome.get('raw_sha256') != seal['raw_sha256']
            or read(regular(work / 'science-task.json')) != science_view(job)):
        raise ValueError('Scientific node identity changed')
    payload = science_payload(raw, job['role'])
    if read(result) != envelope(job, payload):
        raise ValueError('Result envelope differs from author science')
    if seal.get('entry_points', []) != artifact_entry_points(work, payload, seal['materials']):
        raise ValueError('Scientific deliverable entry points changed')
    _validate_inputs(root, work, job)
    for ref in seal['materials']:
        path = regular(Path(ref['source']))
        if path.stat().st_size != ref['size_bytes'] or digest(path) != ref['sha256']:
            raise ValueError('Scientific original changed')
    return read(result)


def _validate_inputs(root, work, job):
    if read(regular(work / 'science-task.json')) != science_view(job):
        raise ValueError('Frozen scientific task changed')
    if job['global_materials'] != global_materials(root):
        raise ValueError('Bound global context changed')
    for row in job['global_materials']:
        if digest(regular(work / row['path'])) != row['sha256']:
            raise ValueError('The global context read by this role changed')
    for ref in job['direct_refs']:
        if digest(regular(work / ref['path'])) != ref['sha256']:
            raise ValueError('Bound result changed')
    for ref in job['direct_materials']:
        path = regular(Path(ref['source']))
        if path.stat().st_size != ref['size_bytes'] or digest(path) != ref['sha256']:
            raise ValueError('Scientific original changed')
    for ref in job['direct_materials']:
        if digest(regular(work / ref['path'])) != ref['sha256']:
            raise ValueError('The direct material actually read by this role changed')


def seal_result(root: Path, step: int):
    work = workspace(root, step)
    record = host_record(work)
    job_path = root / 'jobs' / f'{step:03d}.json'
    job = read(job_path)
    if (record / 'result-identity.json').exists():
        return validate(work)
    intent = read(regular(record / 'native-intent.json'))
    if intent['task_sha256'] != digest(regular(job_path)):
        raise ValueError('Native launch task changed')
    _validate_inputs(root, work, job)
    raw = regular(record / 'science-output.json', limit=MAX_RESULT_BYTES)
    outcome = read(regular(record / 'native-outcome.json'))
    if (type(outcome.get('returncode')) is not int or outcome['returncode'] != 0
            or outcome.get('stop_reason') or outcome['usage']['unknown_steps']
            or outcome.get('raw_sha256') != digest(raw)):
        raise ValueError('Terminal scientific output is unverified or changed')
    value = envelope(job, science_payload(raw, job['role']))
    materials = collect_materials(root, step)
    entry_points = artifact_entry_points(work, value, materials)
    _copy_bound(raw, work / 'conclusion.json', digest(raw))
    write(record / 'result.json', value)
    write(record / 'result-identity.json', dict(sha256=digest(record / 'result.json'), raw_sha256=digest(raw),
          job_sha256=digest(job_path), materials=materials, entry_points=entry_points,
          scope='Exact bytes and direct lineage; not scientific qualification'))
    return validate(work)
