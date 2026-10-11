"""Replayed scientific-control outcomes and finite author clarification."""
from __future__ import annotations

from . import contracts as c, history, search

MAX_DIAGNOSTICS = 8
MAX_AUTHOR_CORRECTIONS = 2


def outcome(root, job, payload, *, legacy_attempt=False):
    if not legacy_attempt and job.get('handoff_protocol', 1) != 8:
        raise ValueError('Control outcomes require the frozen protocol8 interpretation')
    diagnostics = search.assess_payload(root, job, payload, legacy_attempt=legacy_attempt) if c.settings(root).get('search_policy') else []
    selection = []
    c.selected_inputs(c.workspace(root, job['step']), payload, job, selection)
    rows = [*diagnostics, *selection]
    return dict(binding_protocol=8, search_status='unresolved' if diagnostics else 'applied',
                selection_status='unresolved' if selection else 'applied',
                diagnostics=rows[:MAX_DIAGNOSTICS], omitted_count=max(0, len(rows) - MAX_DIAGNOSTICS))


def _source(root, step):
    job, payload, seal, seal_sha = history._source(root, step)
    return dict(step=step, job_sha256=seal['job_sha256'], raw_sha256=seal['raw_sha256'], seal_sha256=seal_sha)


def public_request(root, job):
    """Bound scientific clarification, without the private identity chain."""
    request = job['author_correction']
    first = c.read(c.host_record(c.workspace(root, request['root']['step'])) / 'result-identity.json')
    source_step = request['source']['step']
    return dict(reason=request['reason'], source_step=source_step,
                original_science=f'inputs/parents/{source_step:03d}/conclusion.json',
                initial_attempt_step=request['root']['step'],
                unresolved=first['control_outcome']['diagnostics'],
                remaining_author_corrections=max(0, MAX_AUTHOR_CORRECTIONS - accepted(root, request, job['step'])))


def validate_job(root, job):
    request = job.get('author_correction')
    if request is None:
        return
    if (job.get('handoff_protocol', 1) < 8 or job['role'] not in {'H', 'A', 'E'}
            or not isinstance(request, dict) or set(request) != {'root', 'source', 'reason'}
            or not isinstance(request['reason'], str)):
        raise ValueError('Author correction binding is invalid')
    for field in ('root', 'source'):
        ref = request[field]
        if (not isinstance(ref, dict) or type(ref.get('step')) is not int or not 0 < ref['step'] < job['step']
                or ref != _source(root, ref['step'])):
            raise ValueError('Author correction original identity changed')
    source = c.read(root / 'jobs' / f'{request["source"]["step"]:03d}.json')
    original = source.get('author_correction')
    if original is not None and (request['root'] != original['root'] or request['reason'] != original['reason']):
        raise ValueError('Author correction root cannot change across retries')
    if original is None and request['root'] != request['source']:
        raise ValueError('Author correction root is not its first attempt')
    root_step = request['root']['step']
    root_job, root_payload, root_seal, _ = history._source(root, root_step)
    if (root_job['role'], root_payload.get('next_action')) not in {('H', 'experiment'), ('A', 'continue_w')}:
        raise ValueError('Author correction root did not request a dependent experiment')
    reason = 'implementation_unresolved' if root_seal.get('control_outcome', {}).get('selection_status') == 'unresolved' else None
    if reason is None and c.settings(root).get('search_policy') is not None:
        reason = search.launch_reason(root, dict(step=root_step + 1, role='W',
            search=search.bind(root, root_step + 1, 'W', 8, write_pages=False)))
    if request['reason'] != reason:
        raise ValueError('Author correction reason differs from its original blocked action')
    if not any(ref['path'] == f'inputs/parents/{request["source"]["step"]:03d}/conclusion.json' for ref in job['direct_refs']):
        raise ValueError('Author correction must bind its actual source attempt')


def accepted(root, request, before_step):
    count = 0
    for step in range(request['root']['step'] + 1, before_step):
        path = root / 'jobs' / f'{step:03d}.json'
        if not path.exists():
            break
        job = c.read(c.regular(path))
        previous = job.get('author_correction')
        intent = c.host_record(c.workspace(root, step)) / 'native-intent.json'
        if previous is not None and previous['root'] == request['root'] and job['role'] in {'H', 'A'} and intent.exists():
            if c.read(c.regular(intent)).get('task_sha256') != c.digest(path):
                raise ValueError('Author correction execution identity changed')
            count += 1
    return count


def effective_route(root, step, result, job, route):
    """Refuse dependent W admission before creating its immutable task."""
    role, parents, instruction, evidence_return, current_h, current_w, correction_request = route
    request = None
    previous = job.get('author_correction')
    seal = c.read(c.host_record(c.workspace(root, step)) / 'result-identity.json')
    if job.get('handoff_protocol', 1) < 8 and seal.get('control_outcome') is None:
        return (*route, None)  # Published valid routes keep their exact frozen successors.
    if role == 'W':
        code = 'implementation_unresolved' if seal.get('control_outcome', {}).get('selection_status') == 'unresolved' else None
        if code is None and c.settings(root).get('search_policy') is not None:
            planned = dict(step=step + 1, role='W', search=search.bind(root, step + 1, 'W', 8, write_pages=False))
            code = search.launch_reason(root, planned)
        if code is not None:
            source = _source(root, step)
            request = dict(root=previous['root'] if previous else source, source=source,
                           reason=previous['reason'] if previous else code)
            role = job['role'] if job['role'] in {'H', 'A'} else 'H'
            if role != 'H':
                correction_request = None
            elif job['role'] == 'H':
                correction_request = job.get('correction_request')
            parents = list(dict.fromkeys([*parents, step]))
            instruction = ('Correct this unresolved scientific control choice: ' + code + '. '
                'The original science is retained; no dependent experiment is authorized. '
                'Declare only the needed scientific change, or choose a justified alternative route.')
            evidence_return = None
    elif previous is not None and role in {'H', 'A', 'E'}:
        # Extraction may gather science, but it does not renew author retries.
        request = dict(previous, source=_source(root, step))
        if step not in parents:
            parents = [*parents, step]
    return role, parents, instruction, evidence_return, current_h, current_w, correction_request, request
