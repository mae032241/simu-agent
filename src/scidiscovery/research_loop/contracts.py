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
MAX_REUSED_INPUTS = 16
REUSE_FRAGMENT = 'reuse-implementation'
HANDOFF_PROTOCOL = 6
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


def result_schema(role: str, protocol=1):
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
    required = list(properties)
    if role == 'A' and protocol >= 3:
        properties['candidate_recommendation'] = dict(type=['string', 'null'], maxLength=80,
            description='Optional scientific recommendation: one listed candidate ID, or null when unknown.')
        if protocol >= 4:
            properties['candidate_recommendation']['description'] = (
                'Always include this field: one listed candidate ID, or null when no recommendation is made.')
            required.append('candidate_recommendation')
    if protocol >= 5 and role in {'H', 'A'}:
        from . import search
        field = 'search_plan' if role == 'H' else 'search_review'
        properties[field] = search.schema(role)
        required.append(field)
    if protocol >= 6 and role == 'A':
        from . import correction
        properties['progress_assessment'] = correction.schema()
        required.append('progress_assessment')
    return dict(type='object', properties=properties, required=required, additionalProperties=False)


def science_payload(path: Path, role: str, protocol=1):
    import jsonschema
    value = read(regular(path, limit=MAX_RESULT_BYTES))
    try:
        jsonschema.validate(value, result_schema(role, protocol))
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


def selected_inputs(work, payload, job):
    """Resolve explicit reuse intent against this role's already frozen inputs."""
    if job.get('handoff_protocol', 1) < 2:
        return []  # Preserve the meaning and exact packets of historical jobs.
    root = work.parents[2]
    policy = settings(root)
    bound = {row['path']: row for row in job['direct_materials']}
    selected, seen, total = [], set(), 0
    links = re.finditer(r'\[([^\]\n]+)\]\((?:<([^>\n]+)>|([^\s()]+))\)', payload['scientific_result'])
    for link in links:
        label, angled, plain = link.groups()
        url = urlsplit(angled if angled is not None else plain)
        if url.fragment != REUSE_FRAGMENT:
            continue
        decoded = unquote(url.path)
        path = PurePosixPath(decoded)
        if (url.scheme or url.netloc or url.query or '\\' in decoded or '..' in path.parts
                or path.is_absolute() or path.as_posix() != decoded):
            raise ValueError('Implementation reuse must name one exact already bound input')
        if decoded in seen:
            continue
        seen.add(decoded)
        row = bound.get(decoded)
        if row is None and job.get('handoff_protocol', 1) >= 3 and decoded.startswith('history/nodes/'):
            from . import history
            row = history.resolve(root, decoded, job['history']['nodes'])
        if row is None:
            raise ValueError('Implementation reuse must name one exact already bound input')
        source = Path(row['source'])
        try:
            origin = source.relative_to(root / 'project/nodes').parts[0]
            origin_step = int(origin)
        except (ValueError, IndexError) as error:
            raise ValueError('Implementation reuse requires an original instance node') from error
        if origin != f'{origin_step:03d}' or not 0 < origin_step < job['step']:
            raise ValueError('Implementation reuse requires an exact preceding node')
        original = workspace(root, origin_step)
        record = host_record(original)
        identity = read(regular(record / 'result-identity.json'))
        if (row not in identity['materials'] or source.resolve() != source.absolute()
                or digest(regular(record / 'result.json')) != identity['sha256']
                or digest(regular(record / 'science-output.json')) != identity['raw_sha256']
                or digest(regular(root / 'jobs' / f'{origin_step:03d}.json')) != identity['job_sha256']
                or digest(regular(source)) != row['sha256'] or source.stat().st_size != row['size_bytes']):
            raise ValueError('Selected original implementation changed or is not sealed')
        total += row['size_bytes']
        if (len(selected) >= MAX_REUSED_INPUTS or row['size_bytes'] > policy['max_output_item_bytes']
                or total > policy['max_output_total_bytes']):
            raise ValueError('Selected implementations exceed the frozen handoff bound')
        selected.append(dict(label=label[:160], origin_step=origin_step,
                             origin_result_sha256=identity['sha256'], material=row))
    return selected


def science_view(job):
    return {key: value for key, value in {
        'role': job['role'], 'question': job['instruction'],
        'global': dict(objective='inputs/global/objective.md',
                       updates=[row['path'] for row in job['global_materials'][1:]]),
        'public_root': job['public_root'],
        'parents': [_parent_view(job, ref) for ref in job['direct_refs']],
        **(dict(reused_implementations=[dict(label=row['label'], path=row['material']['path'])
                                       for row in job.get('selected_inputs', [])],
                 implementation_reuse='To give the next role a needed implementation, link an already '
                 'bound input with #reuse-implementation. Ordinary citations do not forward old inputs. '
                 'The host resolves identities; do not copy or index them.')
           if job.get('handoff_protocol', 1) >= 2 else {}),
        **(dict(history=job['history']['view']) if job.get('handoff_protocol', 1) >= 3 else {}),
        **(dict(search=job['search']['view']) if job.get('search') else {}),
        **(dict(progress_assessment='Judge global contribution as progress/no_progress/unknown with '
                'few exact bound prior conclusion/history-page paths; null means unknown. Never use '
                'your own new prose or unsealed files as progress evidence. Scientific explanations '
                'belong in scientific_result and limitations; the host counts sealed decisions.')
           if job.get('handoff_protocol', 1) >= 6 and job['role'] == 'A' else {}),
        'final_response': list(result_schema(job['role'], job.get('handoff_protocol', 1))['properties']),
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
    if any(parent.is_symlink() for parent in destination.parents):
        raise ValueError('Bound input directories must not be links')
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        if digest(regular(destination)) != sha256:
            raise ValueError('Bound input copy changed')
    else:
        shutil.copyfile(source, destination)
        destination.chmod(0o400)
    if digest(regular(destination)) != sha256:
        raise ValueError('Bound input copy changed')


def build_job(root: Path, step: int, role: str, parents: list[int], instruction='', evidence_return=None,
              correction_request=None):
    if role not in ROLE_INSTRUCTIONS or type(step) is not int or step < 1:
        raise ValueError('Invalid scientific node')
    if len(parents) != len(set(parents)) or any(type(p) is not int or not 0 < p < step for p in parents):
        raise ValueError('Parents must be exact distinct preceding nodes')
    policy = settings(root)
    job_path = root / 'jobs' / f'{step:03d}.json'
    protocol = read(regular(job_path)).get('handoff_protocol', 1) if job_path.exists() else HANDOFF_PROTOCOL
    if protocol not in (1, 2, 3, 4, 5, HANDOFF_PROTOCOL):
        raise ValueError('Unsupported frozen handoff protocol')
    work = workspace(root, step)
    work.mkdir(parents=True, exist_ok=True)
    (work / 'work').mkdir(exist_ok=True)
    (work / 'artifacts').mkdir(exist_ok=True)
    globals_ = global_materials(root)
    for item in globals_:
        _copy_bound(root / item['source'], work / item['path'], item['sha256'])
    refs, materials, entry_points, selected = [], [], [], []
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
        # Reuse is an instruction to the immediate next node, not persistent
        # baggage on a retained H ancestor in every later scientific cycle.
        if protocol >= 2 and parent == step - 1:
            selected.extend(parent_seal.get('selected_inputs', []))
    unique = {}
    for item in [*materials, *[row['material'] for row in selected]]:
        if item['path'] in unique and unique[item['path']] != item:
            raise ValueError('Selected input paths conflict')
        unique[item['path']] = item
    materials = list(unique.values())
    if protocol >= 2 and (any(row['size_bytes'] > policy['max_output_item_bytes'] for row in materials)
            or sum(row['size_bytes'] for row in materials) > policy['max_output_total_bytes']):
        raise ValueError('Combined input materials exceed the frozen handoff bound')
    reused = {}
    for row in selected:
        reused.setdefault(row['material']['path'], row)
    selected = list(reused.values())
    if (len(selected) > MAX_REUSED_INPUTS
            or sum(row['material']['size_bytes'] for row in selected) > policy['max_output_total_bytes']):
        raise ValueError('Selected implementations exceed the frozen handoff bound')
    for item in materials:
        _copy_bound(Path(item['source']), work / item['path'], item['sha256'])
    # No recursive parent expansion; per-file identities stay in host storage.
    job = dict(step=step, role=role, goal_text=policy['objective'], public_root=policy['public_root'],
               instruction=instruction, direct_refs=refs, direct_materials=materials, direct_entry_points=entry_points, global_materials=globals_,
               evidence_return=evidence_return, **(dict(selected_inputs=selected) if selected else {}),
               **(dict(handoff_protocol=protocol) if protocol >= 2 else {}))
    if protocol >= 3:
        from . import history
        job['history'] = history.bind(root, step)
    if protocol >= 5 and policy.get('search_policy') is not None:
        from . import search
        job['search'] = search.bind(root, step, role)
    if correction_request is not None:
        job['correction_request'] = correction_request
        from . import correction
        correction.validate_job(root, job)
    for path, value in ((root / 'jobs' / f'{step:03d}.json', job),
                        (work / 'science-task.json', science_view(job)),
                        (host_record(work) / 'science-result.schema.json', result_schema(role, protocol))):
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
    payload = science_payload(raw, job['role'], job.get('handoff_protocol', 1))
    if job.get('handoff_protocol', 1) >= 5:
        from . import search
        search.validate_payload(root, job, payload)
    if job.get('handoff_protocol', 1) >= 6:
        from . import correction
        correction.validate_payload(root, job, payload)
    if read(result) != envelope(job, payload):
        raise ValueError('Result envelope differs from author science')
    if seal.get('entry_points', []) != artifact_entry_points(work, payload, seal['materials']):
        raise ValueError('Scientific deliverable entry points changed')
    if seal.get('selected_inputs', []) != selected_inputs(work, payload, job):
        raise ValueError('Selected implementation receipts changed')
    _validate_inputs(root, work, job)
    if job.get('handoff_protocol', 1) >= 3:
        from . import history
        history.validate_observation(root, job, seal)
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
    policy = settings(root)
    if job.get('handoff_protocol', 1) >= 6:
        from . import correction
        correction.validate_job(root, job)
    if job.get('handoff_protocol', 1) >= 5 and policy.get('search_policy') is not None:
        from . import search
        if job.get('search') != search.bind(root, job['step'], job['role']):
            raise ValueError('Frozen scientific search binding changed')
    if job.get('handoff_protocol', 1) >= 3:
        from . import history
        history.validate(root, work, job['history'])
    if job.get('handoff_protocol', 1) >= 2 and (
            any(row['size_bytes'] > policy['max_output_item_bytes'] for row in job['direct_materials'])
            or sum(row['size_bytes'] for row in job['direct_materials']) > policy['max_output_total_bytes']):
        raise ValueError('Combined input materials exceed the frozen handoff bound')
    expected = []
    previous = f'inputs/parents/{job["step"] - 1:03d}/conclusion.json'
    if any(ref['path'] == previous for ref in job['direct_refs']):
        expected = read(regular(host_record(workspace(root, job['step'] - 1)) /
                                'result-identity.json')).get('selected_inputs', [])
    if job.get('selected_inputs', []) != expected:
        raise ValueError('Bound implementation selection differs from its predecessor')
    if any(row['material'] not in job['direct_materials'] for row in expected):
        raise ValueError('Selected implementation is absent from bound materials')
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
        result = validate(work)
        if job.get('handoff_protocol', 1) >= 3:
            from . import history
            history.refresh(root, step + 1)
        return result
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
    value = envelope(job, science_payload(raw, job['role'], job.get('handoff_protocol', 1)))
    if job.get('handoff_protocol', 1) >= 5:
        from . import search
        search.validate_payload(root, job, value)
    if job.get('handoff_protocol', 1) >= 6:
        from . import correction
        correction.validate_payload(root, job, value)
    materials = collect_materials(root, step)
    entry_points = artifact_entry_points(work, value, materials)
    selected = selected_inputs(work, value, job)
    observations = None
    if job.get('handoff_protocol', 1) >= 3:
        from . import history
        history.validate_recommendation(job, value)
        observations = history.capture(root, job, value, materials)
    _copy_bound(raw, work / 'conclusion.json', digest(raw))
    write(record / 'result.json', value)
    write(record / 'result-identity.json', dict(sha256=digest(record / 'result.json'), raw_sha256=digest(raw),
          job_sha256=digest(job_path), materials=materials, entry_points=entry_points,
          scope='Exact bytes and direct lineage; not scientific qualification',
          **(dict(selected_inputs=selected) if selected else {}),
          **(dict(observations=observations) if observations else {})))
    result = validate(work)
    if job.get('handoff_protocol', 1) >= 3:
        history.refresh(root, step + 1)
    return result
