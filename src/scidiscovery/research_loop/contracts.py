"""Thin scientific packets and exact direct-node seals; no MCP dispatch protocol.

Only the controller supplies identities and lineage. These seals attest bytes,
not scientific validity, independent qualification or external-effect authority.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil

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
    return root / 'project/.local/roles' / f'{step:03d}'


def host_record(work: Path):
    return work.parents[3] / 'native-evidence' / work.name


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
    jsonschema.validate(value, result_schema(role))
    if any(not value[key].strip() for key in ('summary', 'scientific_result')) or (
            role in ACTIONS and not value['route_reason'].strip()):
        raise ValueError('Scientific content and routing reasons must be nonempty')
    return value


def envelope(job, payload):
    return {**payload, 'role': job['role'], 'direct_refs': job['direct_refs'],
            'next_action': payload.get('next_action', ''), 'route_reason': payload.get('route_reason', '')}


def science_view(job):
    return {key: value for key, value in {
        'role': job['role'], 'goal_text': job['goal_text'], 'question': job['instruction'],
        'public_root': job['public_root'], 'direct_results': [dict(path=ref['path']) for ref in job['direct_refs']],
        'materials': [dict(path=row['path'], size_bytes=row['size_bytes']) for row in job['direct_materials']],
        'result_schema': 'science-result.schema.json', 'outputs': 'artifacts/',
    }.items() if value}


def collect_materials(root: Path, step: int):
    """Only this node's outputs; parent files and receipts are never inherited."""
    policy = settings(root)
    base = workspace(root, step) / 'artifacts'
    if not base.exists():
        return []
    if base.is_symlink() or not base.is_dir():
        raise ValueError('Managed outputs must be an original directory')
    rows, total = [], 0
    for directory, subdirs, files in os.walk(base, followlinks=False):
        for name in subdirs:
            if (Path(directory) / name).is_symlink():
                raise ValueError('Managed output links are not sealed')
        for name in sorted(files):
            path = regular(Path(directory) / name, limit=policy['max_output_item_bytes'])
            size = path.stat().st_size
            total += size
            if total > policy['max_output_total_bytes']:
                raise ValueError('Managed output byte budget exhausted')
            rows.append(dict(source=str(path), path=f'originals/{step:03d}/{path.relative_to(base).as_posix()}',
                             sha256=digest(path), size_bytes=size))
    return sorted(rows, key=lambda row: row['path'])


def build_job(root: Path, step: int, role: str, parents: list[int], instruction='', evidence_return=None):
    if role not in ROLE_INSTRUCTIONS or type(step) is not int or step < 1:
        raise ValueError('Invalid scientific node')
    if len(parents) != len(set(parents)) or any(type(p) is not int or not 0 < p < step for p in parents):
        raise ValueError('Parents must be exact distinct preceding nodes')
    policy = settings(root)
    work = workspace(root, step)
    work.mkdir(parents=True, exist_ok=True)
    refs, materials = [], []
    for parent in parents:
        source_work = workspace(root, parent)
        validate(source_work)
        # Pass the author's science, not the controller envelope and its parent
        # references. Historical lineage remains in the host-owned node tree.
        source = host_record(source_work) / 'science-output.json'
        ref = dict(path=f'inputs/{parent:03d}.json', sha256=digest(source))
        target = work / ref['path']
        target.parent.mkdir(exist_ok=True)
        if target.exists():
            if digest(regular(target)) != ref['sha256']:
                raise ValueError('Direct result changed')
        else:
            shutil.copyfile(source, target)
        refs.append(ref)
        materials.extend(read(host_record(source_work) / 'result-identity.json')['materials'])
    for item in materials:
        destination = work / item['path']
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copyfile(item['source'], destination)
            destination.chmod(0o400)
        if digest(regular(destination)) != item['sha256']:
            raise ValueError('Direct material copy changed')
    # No recursive parent expansion. Keep a file index; native tools read chosen bytes.
    job = dict(step=step, role=role, goal_text=policy['objective'], public_root=policy['public_root'],
               instruction=instruction, direct_refs=refs, direct_materials=materials,
               evidence_return=evidence_return)
    for path, value in ((root / 'jobs' / f'{step:03d}.json', job),
                        (work / 'science-task.json', science_view(job)),
                        (work / 'science-result.schema.json', result_schema(role))):
        if path.exists():
            if read(regular(path)) != value:
                raise ValueError('Frozen scientific task changed')
        else:
            write(path, value)
    return job


def validate(work: Path):
    root = work.parents[3]
    job_path = root / 'jobs' / f'{int(work.name):03d}.json'
    job = read(regular(job_path))
    record = host_record(work)
    seal = read(regular(record / 'result-identity.json'))
    intent = read(regular(record / 'native-intent.json'))
    raw = regular(record / 'science-output.json', limit=MAX_RESULT_BYTES)
    result = regular(work / 'result.json', limit=MAX_RESULT_BYTES * 2)
    if (seal['job_sha256'] != digest(job_path) or intent['task_sha256'] != digest(job_path)
            or seal['raw_sha256'] != digest(raw) or seal['sha256'] != digest(result)
            or read(regular(work / 'science-task.json')) != science_view(job)):
        raise ValueError('Scientific node identity changed')
    payload = science_payload(raw, job['role'])
    if read(result) != envelope(job, payload):
        raise ValueError('Result envelope differs from author science')
    for ref in job['direct_refs']:
        if digest(regular(work / ref['path'])) != ref['sha256']:
            raise ValueError('Bound result changed')
    for ref in [*job['direct_materials'], *seal['materials']]:
        path = regular(Path(ref['source']))
        if path.stat().st_size != ref['size_bytes'] or digest(path) != ref['sha256']:
            raise ValueError('Scientific original changed')
    for ref in job['direct_materials']:
        if digest(regular(work / ref['path'])) != ref['sha256']:
            raise ValueError('The direct material actually read by this role changed')
    return read(result)


def seal_result(root: Path, step: int):
    work = workspace(root, step)
    record = host_record(work)
    job_path = root / 'jobs' / f'{step:03d}.json'
    job = read(job_path)
    if (record / 'result-identity.json').exists():
        return validate(work)
    raw = record / 'science-output.json'
    value = envelope(job, science_payload(raw, job['role']))
    write(work / 'result.json', value)
    write(record / 'result-identity.json', dict(sha256=digest(work / 'result.json'), raw_sha256=digest(raw),
          job_sha256=digest(job_path), materials=collect_materials(root, step),
          scope='Exact bytes and direct lineage; not scientific qualification'))
    return validate(work)
