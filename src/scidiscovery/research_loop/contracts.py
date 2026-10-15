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
MAX_UNRESOLVED_LINKS = 16
REUSE_FRAGMENT = 'reuse-implementation'
from .protocol import CURRENT
HANDOFF_PROTOCOL = CURRENT
AUDIT_PROJECTION_VERSION = 1
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


def actions(role,protocol=CURRENT):
    from .protocol import _current
    _current(protocol,'Scientific result schema')
    return (*ACTIONS[role],'audit') if role=='A' else ACTIONS.get(role,())


def result_schema(role: str,protocol=CURRENT):
    from .protocol import _current
    _current(protocol,'Scientific result schema')
    if role not in ROLE_INSTRUCTIONS:raise ValueError('Unknown scientific role')
    properties=dict(summary=dict(type='string',minLength=1),scientific_result=dict(type='string',minLength=1),
        limitations=dict(type='array',items=dict(type='string')),
        implementation_selection=dict(type=['array','null'],maxItems=MAX_REUSED_INPUTS,
            items=dict(type='string',minLength=1,maxLength=80),
            description='Null retains the selected implementation; [] clears it; listed scientific object IDs replace it. No paths, hashes or handoff markers.'))
    if role in ACTIONS:
        properties.update(next_action=dict(type='string',enum=list(actions(role))),route_reason=dict(type='string',minLength=1))
    if role=='W':
        from . import worker_delivery
        properties['mechanism_findings']=worker_delivery.schema()
        properties['stage_intent']=dict(type='string',enum=['continue','review','decision'],
        description='Continue the same scientific stage, report completed work for review, or request an A scientific decision with partial work. This does not grant budget or execution. Control may end the stage at a review or shared boundary.')
    if role in {'H','A'}:
        from . import search
        properties['search_plan' if role=='H' else 'search_review']=search.schema(role)
    if role=='A':
        from . import correction,decision
        properties.update(candidate_recommendation=dict(type=['string','null'],maxLength=80),
            progress_assessment=correction.schema(),decision_request=decision.schema(),
            portfolio_review=dict(type=['string','null'],maxLength=1024,
                description='When the configured overview requests it, explain scientific opportunity cost. Explicit justified selection may provide this reason; otherwise null.'))
    return dict(type='object',properties=properties,required=list(properties),additionalProperties=False)


def science_payload(path: Path, role: str, protocol=CURRENT):
    import jsonschema
    from .output_repair import OutputRepairRequired
    original = regular(path, limit=MAX_RESULT_BYTES)
    try:
        value = read(original)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise OutputRepairRequired('invalid_json', 'Return one valid JSON object matching final_response; completed experiments remain retained.') from error
    try:
        jsonschema.validate(value, result_schema(role, protocol))
    except jsonschema.ValidationError as error:
        location = '.'.join(map(str, error.absolute_path))[:128] or 'final response'
        raise OutputRepairRequired('invalid_fields', 'Correct required fields and types in ' + location + ' using final_response; do not repeat experiments.') from error
    if any(not value[key].strip() for key in ('summary', 'scientific_result')) or (
            role in ACTIONS and not value['route_reason'].strip()):
        raise OutputRepairRequired('empty_content', 'Return nonempty scientific content and routing reasons for the already completed task.')
    return value


def envelope(job, payload):
    return {**payload, 'role': job['role'], 'direct_refs': job['direct_refs'],
            'next_action': payload.get('next_action', ''), 'route_reason': payload.get('route_reason', '')}


def _whole_limitations(values, *, byte_limit=1024):
    """Keep whole authored entries; a long item cannot crowd out later caveats."""
    selected=[]
    for value in values:
        if len((json.dumps([*selected,value],ensure_ascii=False,indent=2)+'\n').encode())<=byte_limit:
            selected.append(value)
    return selected,len(values)-len(selected)


def _parent_view(job, ref, root=None, *, limitation_bytes=1024):
    directory = str(Path(ref['path']).parent / 'artifacts')
    entries = [row for row in job.get('direct_entry_points', [])
               if row['path'].startswith(directory + '/')]
    view = dict(conclusion=ref['path'], artifacts=directory)
    if entries:
        view['evidence'] = entries[:16]
        if len(entries) > 16:
            view['evidence_omitted_count'] = len(entries) - 16
    if root is not None:
        path=regular(workspace(Path(root),job['step'])/ref['path'],limit=MAX_RESULT_BYTES)
        if digest(path)!=ref['sha256']:
            raise ValueError('Direct scientific original changed')
        payload=read(path)
        parent_step=int(Path(ref['path']).parts[2])
        view['role']=read(regular(Path(root)/'jobs'/f'{parent_step:03d}.json'))['role']
        view['limitations'],view['limitations_omitted_count']=_whole_limitations(payload['limitations'],byte_limit=limitation_bytes)
    return view


def artifact_entry_points(work, payload, materials, protocol=CURRENT, unresolved=None):
    """Resolve explicit inline scientific links, never infer paths from prose."""
    targets = {Path(row['source']).relative_to(work).as_posix(): row['path'] for row in materials}
    entries, seen = [], set()
    def unavailable(label, target, reason):
        if unresolved is not None:
            if len(unresolved['items']) < MAX_UNRESOLVED_LINKS:
                clip = lambda value, capacity: value.encode()[:capacity].decode('utf-8', errors='ignore')
                unresolved['items'].append(dict(label=clip(label, 160), target=clip(target, 512), reason=reason))
            else:
                unresolved['omitted_count'] += 1
    links = re.finditer(r'\[([^\]\n]+)\]\((?:<([^>\n]+)>|([^\s()]+))\)', payload['scientific_result'])
    for link in links:
        label, angled, plain = link.groups()
        target = angled if angled is not None else plain
        try:
            url = urlsplit(target)
        except ValueError:
            unavailable(label, target, 'malformed_scientific_link')
            continue
        if url.scheme or url.netloc:
            continue
        decoded = unquote(url.path)
        normalized = PurePosixPath(decoded)
        if not normalized.parts or normalized.parts[0] not in {'artifacts', 'experiments'}:
            if protocol >= 7 and (normalized.is_absolute() or '..' in normalized.parts
                    or '\\' in decoded or decoded.startswith('.') or url.fragment == REUSE_FRAGMENT):
                unavailable(label, target, 'unmanaged_or_legacy_link')
            continue
        if '..' in normalized.parts or url.query or '\\' in decoded:
            unavailable(label, target, 'Scientific artifact links require an exact local deliverable path')
            continue
        path = normalized.as_posix()
        if path not in targets:
            unavailable(label, target, 'Scientific artifact link does not name a selected deliverable')
            continue
        if path not in seen:
            entries.append(dict(label=label[:160], path=targets[path]))
            seen.add(path)
    return entries


def selected_inputs(work, payload, job, diagnostics=None):
    """Resolve explicit reuse intent against this role's already frozen inputs."""
    root = work.parents[2]
    policy = settings(root)
    bound = {row['path']: row for row in job['direct_materials']}
    selected, seen, total = [], set(), 0
    choices = []
    choice = payload.get('implementation_selection')
    if choice is None:
        if job.get('handoff_protocol', 1) >= 8 and job.get('input_selection_status') == 'unresolved':
            if diagnostics is not None:
                diagnostics.append(dict(code='implementation_unresolved', subject='inherited unresolved choice'))
            return []
        choices = [(row['label'], row['material']) for row in job.get('selected_inputs', [])]
    else:
        from . import history
        unresolved = []
        for object_id in dict.fromkeys(choice):
            try:
                row = history.resolve_implementation(root, object_id, job['history']['nodes'])
            except history.UnresolvedImplementation:
                unresolved.append(dict(code='implementation_unresolved', subject=object_id))
                continue
            choices.append((object_id, row))
        if unresolved:
            if diagnostics is not None:
                diagnostics.extend(unresolved)
            return []  # No partial selection or fallback to a former choice.
    material_seen = set()
    for label, row in choices:
        if job.get('handoff_protocol', 1) >= 7 and row['path'] in material_seen:
            continue
        material_seen.add(row['path'])
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
                or digest(regular(_execution_raw(root, origin_step))) != identity['raw_sha256']
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


def _decision_context(root, job):
    """Label the exact immediate scientific source; do not parse its prose."""
    if (job['role'] not in {'W', 'H'} or job.get('purpose') is not None
            or job.get('author_correction') or job.get('correction_request')):
        return None
    previous = job['step'] - 1
    ref = next((row for row in job['direct_refs'] if row['path'] == f'inputs/parents/{previous:03d}/conclusion.json'), None)
    if ref is None:
        return None
    source_job = read(regular(root / 'jobs' / f'{previous:03d}.json'))
    source = science_payload(_execution_raw(root, previous), source_job['role'], source_job.get('handoff_protocol', 1))
    action = 'continue_w' if job['role'] == 'W' else 'revise_h'
    if (source_job['role'] != 'A' or source.get('next_action') != action
            or job['instruction'] != source.get('route_reason')):
        return None  # H directives, E questions/returns and control corrections keep their question.
    return dict(source_role='A', source_action=action, source_original=ref['path'],
                original_instruction=job['instruction'],
                authority='A selects global direction and decision-changing evidence. Concrete execution methods are proposals. '
                'Original user constraints and H scope/discriminating commitments remain binding; W owns execution design and H owns mechanism revision.')


def _role_lineage(job):
    """Select default material from the same frozen view; indexes retain all facts."""
    import copy
    view=copy.deepcopy(job['history']['view'])
    if job['role']!='A':
        candidates=view['candidates']
        ranking=candidates.get('proxy_highest',[])
        candidates['proxy_highest']=[]
        candidates['proxy_groups_omitted_count']=candidates.get('proxy_groups_omitted_count',0)+len(ranking)
        if ranking:
            candidates['limitation']='Global ranking omitted here; candidate indexes retain comparisons. '+candidates['limitation']
    breadth=(job.get('search') or {}).get('breadth')
    if job['role']=='W' and breadth is not None:
        rows=breadth['mechanisms']
        mechanisms=view['mechanisms']
        mechanisms['focus']=None
        mechanisms['authorized_count']=len(rows)
        mechanisms['overview']=[dict(mechanism_ref=row['mechanism_ref'],label=row['label'],
            status=row['status'],original=f'inputs/history/nodes/{row["source_h"]:03d}/0001.json') for row in rows[:4]]
        mechanisms['overview_omitted_count']=max(0,len(rows)-4)
        action=((job.get('search') or {}).get('focus') or {}).get('action')
        mechanisms['task_action']=action
        mechanisms['scope']=('Assigned shallow combination; each mechanism needs your own scientific finding or explicit obstacle.' if action=='screen' else
            'Assigned local '+str(action)+' task; do not repeat other mechanisms. Existing observations retain their limitations.')
        mechanisms['coverage_required_count']=len((job.get('search') or {}).get('coverage_obligation',[]))
        from .lineage import bounded_brief
        bounded_brief(view)
    return view


def science_view(job, root=None):
    protocol = job.get('handoff_protocol', 1)
    context = job.get('decision_context')
    question = job['instruction']
    if context is not None:
        question = ("Choose observation-driven experiments within the bound H scientific questions and user constraints; use A's global direction and evidence gap."
                    if job['role'] == 'W' else "Revise the qualitative mechanism matrix and discriminating design in light of A's global assessment; preserve original constraints.")
    if job.get('scientific_work_unit'):
        question += '\nWork unit: ' + job['scientific_work_unit']
    unified = job.get('lineage_projection_version') == 1
    if unified and job.get('selection_protocol', 0) != job['history']['view']['candidates'].get('selection_protocol', 0):
        raise ValueError('Frozen selection projection differs from its task marker')
    request = None
    if protocol >= 8 and job.get('author_correction'):
        from . import semantic
        request = semantic.public_request(root, job)
    audit = None
    if job.get('candidate_audit') is not None:
        from . import candidate_audit
        audit = candidate_audit.public_receipt(root, job['candidate_audit'])
    closeout = None
    if job.get('purpose') == 'closeout':
        from . import delivery
        closeout = dict(source_cutoff=job['source_cutoff'],
            selection='Choose a frozen candidate ID for delivery; null means no decision, not retention. Report scientific reasoning and limitations.',
            sources=delivery.public_sources(job['delivery_sources']))
    priorities={
        'H':('A','E','H','W'), 'W':('H','A','W','E'),
        'A':('W','E','H','A'), 'E':('A','H','W','E')}
    reading={
        'H':'Constraints, A judgments/counterevidence, then unresolved H questions.',
        'W':'Constraints and authorized H questions, then A direction and prior observations.',
        'A':'W observations, H questions and unresolved alternatives, then further investment.',
        'E':'Exact requester question and constraints, then requested original evidence.'}
    parents=[_parent_view(job,ref,root,limitation_bytes=1024//max(1,len(job['direct_refs']))) for ref in job['direct_refs']]
    order=priorities[job['role']]
    if job['role']=='E' and (job.get('evidence_return') or {}).get('role') in order:
        requester=job['evidence_return']['role']
        order=(requester,*[role for role in order if role!=requester])
    parents.sort(key=lambda row:order.index(row['role']) if row.get('role') in order else len(order))
    return {key: value for key, value in {
        'role': job['role'], 'question': question,
        **(dict(stage_continuation=dict(status='configured' if job.get('worker_fragment_policy') else 'unavailable',
            context=(job.get('worker_fragment_policy') or {}).get('context'),
            permission='Configured context is not permission: control verifies original terminal, cleanup, usage, session and remaining shared authorization before accepting another fragment.',
            intent='review reports completed assigned work; decision sends a scientific obstacle to A as partial; continue requests another fragment only when configured; otherwise control ends the stage with an explicit unavailable reason.')) if job['role']=='W' else {}),
        **(dict(decision_context=context) if context is not None else {}),
        **(dict(role_instruction=job['native_role_instruction']) if job.get('native_role_instruction') and not job.get('role_guidance') else {}),
        **(dict(role_guidance=job['role_guidance']) if job.get('role_guidance') else {}),
        'global': dict(objective='inputs/global/objective.md',
                       updates=[row['path'] for row in job['global_materials'][1:]]),
        'public_root': job['public_root'],
        'parents': parents,
        'reading_order':reading[job['role']]+' Preserve listed limitations. Parents are authored statements, not execution facts. Verify relevant originals as needed, delegating when native permissions allow; omissions use conclusion/index/next_page.',
        **(dict(reused_implementations=[dict(label=row['label'], path=row['material']['path'])
                                       for row in job.get('selected_inputs', [])],
                 implementation_reuse='Choose only listed scientific objects; control resolves their originals.')
           if job.get('handoff_protocol', 1) >= 2 else {}),
        **(dict(implementation_options=job.get('implementation_options', []),
                implementation_options_omitted_count=job.get('implementation_options_omitted_count', 0),
                scientific_links='Ordinary citations are scientific prose. Only listed bound files are available; '
                'unresolved links do not select inputs or acquire evidence qualification.') if protocol >= 7 and not unified else {}),
        **(dict(lineage=_role_lineage(job)) if unified else {}),
        **(dict(history=job['history']['view']) if job.get('handoff_protocol', 1) >= 3 and not unified else {}),
        **(dict(input_selection_status=job['input_selection_status'], control_diagnostics=job['control_diagnostics'])
           if job.get('handoff_protocol', 1) >= 8 else {}),
        **(dict(control_request=request)
           if job.get('handoff_protocol', 1) >= 8 and job.get('author_correction') else {}),
        **(dict(closeout=closeout) if closeout is not None else {}),
        **(dict(candidate_audit=audit) if audit is not None else {}),
        **(dict(search=job['search']['view']) if job.get('search') and not unified else {}),
        **(dict(progress_assessment=('Judge the current assessed work as progress/no_progress/unknown; '
                'null means unknown. Explain scientific support and limitations in ordinary science. '
                'The host binds the exact assessed task for counting, not scientific verification. Do not write evidence paths.' if protocol >= 7 else
                'Judge global contribution as progress/no_progress/unknown with '
                'few exact bound prior conclusion/history-page paths; null means unknown. Never use '
                'your own new prose or unsealed files as progress evidence. Scientific explanations '
                'belong in scientific_result and limitations; the host counts sealed decisions.'))
           if job.get('handoff_protocol', 1) >= 6 and job['role'] == 'A' else {}),
        **(dict(decision_request='For scientific continuation, declare the decision, question and result that would change it. '
                'Exact completed requests without new bound evidence require clarification; this is not a scientific value judgment.')
           if protocol >= 10 and job['role'] == 'A' else {}),
        'final_response': list(result_schema(job['role'], job.get('handoff_protocol', 1))['properties']),
        'outputs': 'artifacts/', 'scratch': 'work/',
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
              correction_request=None, author_correction=None, *, purpose=None, source_cutoff=None, delivery_sources=None, role_budget=None):
    if role not in ROLE_INSTRUCTIONS or type(step) is not int or step < 1:
        raise ValueError('Invalid scientific node')
    if role_budget is not None and (role != 'W' or purpose is not None or settings(root).get('role_budget_policy') is None):
        raise ValueError('Control role-budget routing binds only an ordinary W under its frozen policy')
    if len(parents) != len(set(parents)) or any(type(p) is not int or not 0 < p < step for p in parents):
        raise ValueError('Parents must be exact distinct preceding nodes')
    from .protocol import require_current
    policy=require_current(root)
    if purpose is not None:
        from . import budget
        begin=budget.closeout_state(root)['begin']
        if (purpose!='closeout' or role!='A' or begin is None or begin['mode']!='model'
                or source_cutoff!=begin['source_cutoff'] or step<begin['first_step'] or delivery_sources is None):
            raise ValueError('Closeout task requires its immutable configured boundary')
    elif source_cutoff is not None or delivery_sources is not None:
        raise ValueError('Ordinary task cannot select a noncontiguous science prefix')
    job_path=root/'jobs'/f'{step:03d}.json'
    retained=read(regular(job_path)) if job_path.exists() else None
    if retained is not None:require_current(root,retained)
    protocol=CURRENT
    authority_version=projection_version=selection_protocol=1
    audit_projection_version=1 if policy.get('candidate_audit_policy') else 0
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
        source = _execution_raw(root, parent)
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
    if (retained.get('live_feedback_version') if retained is not None else policy.get('live_feedback_version')) == 1:
        job['live_feedback_version'] = 1
    if (retained.get('experiment_interface_version') if retained is not None else policy.get('experiment_interface_version')) == 1:
        job['experiment_interface_version'] = 1
    if (retained.get('managed_admission_version') if retained is not None else policy.get('managed_admission_version')) == 1:
        job['managed_admission_version'] = 1
    advice = retained.get('role_guidance') if retained is not None else policy.get('role_guidance', {}).get(role)
    if advice is not None:
        job['role_guidance'] = advice
    if authority_version == 1:
        job['handoff_authority_version'] = 1
        from . import guidance
        job['native_role_instruction'] = (retained['native_role_instruction'] if retained is not None
                                          else advice if advice is not None else (guidance.OPPORTUNITY if protocol >= 12 else guidance.DEFAULT)[role])
    if audit_projection_version == 1:
        job['audit_projection_version'] = 1
    if selection_protocol == 1:
        job['selection_protocol'] = 1
    if projection_version == 1:
        job['lineage_projection_version'] = 1
    if purpose is not None:
        job.update(purpose=purpose, source_cutoff=source_cutoff, delivery_sources=delivery_sources,
                   closeout_begin=dict(seq=begin['seq'], sha256=digest(root / 'control-ledger' / f'{begin["seq"]:06d}.json')))
    previous = read(host_record(workspace(root, step - 1)) / 'result-identity.json') if step - 1 in parents else {}
    job['input_selection_status'] = previous.get('control_outcome', {}).get('selection_status', 'applied')
    job['control_diagnostics'] = previous.get('control_outcome', {}).get('diagnostics', [])
    if role=='W':job['worker_fragment_policy']=policy.get('worker_fragment_policy')
    if author_correction is not None:
        job['author_correction'] = author_correction
    if role_budget is not None:
        job['role_budget'] = role_budget
    if protocol >= 9 and role == 'A' and step - 1 in parents:
        from . import candidate_audit
        receipt = candidate_audit.receipt_ref(root, step - 1)
        if receipt is not None:
            job['candidate_audit'] = receipt
    state = None
    from . import history
    extra_steps = [parent for parent in parents if source_cutoff is not None and parent > source_cutoff]
    from . import lineage
    job['history'],state=lineage.bind(root,step,role,protocol,source_cutoff=source_cutoff,extra_steps=extra_steps,selection_protocol=selection_protocol,
        audit_projection_version=audit_projection_version,adjacent_audit=job.get('candidate_audit'))
    options = [item for parent in parents for item in history.implementation_options(root, parent)]
    job['implementation_options'] = options[:16]
    job['implementation_options_omitted_count'] = max(0, len(options) - 16)
    if projection_version == 1:
        job['history']['view']['implementation_options'] = [dict(id=row['id'], label=row['label'].encode()[:80].decode('utf-8',errors='ignore')) for row in options[:2]]
        job['history']['view']['implementation_options_omitted_count'] = max(0,len(options)-2)
        lineage.bounded_brief(job['history']['view'])
    if purpose is None and protocol >= 5 and policy.get('search_policy') is not None:
        from . import search
        job['search'] = search.bind(root, step, role, protocol, state=state, unified=projection_version == 1,
                                    redirect=(role_budget or {}).get('focus_source'))
    if retained is not None:
        if 'scientific_work_unit' in retained:job['scientific_work_unit']=retained['scientific_work_unit']
    elif role=='W':
        from . import guidance
        action=((job.get('search') or {}).get('focus') or {}).get('action')
        if action in guidance.WORK_UNITS:job['scientific_work_unit']=guidance.WORK_UNITS[action]
    if correction_request is not None:
        job['correction_request'] = correction_request
        from . import correction
        correction.validate_job(root, job)
    if authority_version == 1:
        context = _decision_context(root, job)
        if context is not None:
            job['decision_context'] = context
    for path, value in ((root / 'jobs' / f'{step:03d}.json', job),
                        (work / 'science-task.json', science_view(job, root)),
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
    from . import execution
    native_record = execution.record(root, job['step'])
    intent = read(regular(native_record / 'native-intent.json'))
    outcome = read(regular(native_record / 'native-outcome.json'))
    raw = regular(native_record / 'science-output.json', limit=MAX_RESULT_BYTES)
    result = regular(record / 'result.json', limit=MAX_RESULT_BYTES * 2)
    conclusion = regular(work / 'conclusion.json', limit=MAX_RESULT_BYTES)
    if (seal['job_sha256'] != digest(job_path) or intent['task_sha256'] != digest(job_path)
            or seal['raw_sha256'] != digest(raw) or seal['sha256'] != digest(result)
            or seal['raw_sha256'] != digest(conclusion) or outcome.get('raw_sha256') != seal['raw_sha256']
            or read(regular(work / 'science-task.json')) != science_view(job, root)):
        raise ValueError('Scientific node identity changed')
    payload = science_payload(raw, job['role'], job.get('handoff_protocol', 1))
    if seal.get('control_outcome') is not None:
        from . import semantic
        if seal['control_outcome'] != semantic.outcome(root, job, payload):
            raise ValueError('Control outcome differs from its original scientific attempt')
    else:
        raise ValueError('Current scientific attempt has no control outcome')
    from . import correction
    correction.validate_payload(root, job, payload)
    if read(result) != envelope(job, payload):
        raise ValueError('Result envelope differs from author science')
    unresolved = dict(items=[], omitted_count=0)
    if seal.get('entry_points', []) != artifact_entry_points(work, payload, seal['materials'], job.get('handoff_protocol', 1), unresolved):
        raise ValueError('Scientific deliverable entry points changed')
    if job.get('handoff_protocol', 1) >= 7 and seal.get('unresolved_links') != unresolved:
        raise ValueError('Scientific unresolved link receipt changed')
    if seal.get('selected_inputs', []) != selected_inputs(work, payload, job):
        raise ValueError('Selected implementation receipts changed')
    _validate_inputs(root, work, job)
    from . import history
    history.validate_observation(root, job, seal)
    for ref in seal['materials']:
        path = regular(Path(ref['source']))
        if path.stat().st_size != ref['size_bytes'] or digest(path) != ref['sha256']:
            raise ValueError('Scientific original changed')
    return read(result)


def _validate_inputs(root, work, job):
    if job['role']=='W' and job.get('worker_fragment_policy')!=settings(root).get('worker_fragment_policy'):
        raise ValueError('Frozen W continuation configuration differs from its original settings')
    if job.get('audit_projection_version') == 1:
        if (job['history'].get('audit_projection_version') != 1
                or job['history'].get('adjacent_audit') != job.get('candidate_audit')):
            raise ValueError('Frozen audit projection differs from its task boundary')
    if job.get('handoff_authority_version') == 1:
        if job.get('decision_context') != _decision_context(root, job):
            raise ValueError('Scientific handoff source authority changed')
        if job.get('role_guidance') and job.get('native_role_instruction') != job['role_guidance']:
            raise ValueError('Native role instruction differs from its frozen scientific guidance')
    if read(regular(work / 'science-task.json')) != science_view(job, root):
        raise ValueError('Frozen scientific task changed')
    if job['global_materials'] != global_materials(root):
        raise ValueError('Bound global context changed')
    policy = settings(root)
    if job.get('purpose') is not None:
        from . import budget, delivery
        begin = budget.closeout_state(root)['begin']
        if (job['purpose'] != 'closeout' or job['role'] != 'A' or begin is None
                or job.get('source_cutoff') != begin['source_cutoff'] or job['step'] < begin['first_step']
                or job.get('closeout_begin') != dict(seq=begin['seq'],sha256=digest(root/'control-ledger'/f'{begin["seq"]:06d}.json'))):
            raise ValueError('Closeout task boundary changed')
        if job.get('delivery_sources') != begin.get('delivery_sources'):
            raise ValueError('Closeout candidate originals differ from their immutable preparation')
        expected_steps = [*range(1, job['source_cutoff'] + 1), *sorted(int(ref['path'].split('/')[2])
            for ref in job['direct_refs'] if int(ref['path'].split('/')[2]) > job['source_cutoff'])]
        if [row['step'] for row in job['history']['nodes']] != expected_steps:
            raise ValueError('Closeout history differs from its frozen science prefix and direct authors')
        delivery.validate_sources(root, job['delivery_sources'])
        first = root / 'jobs' / f'{begin["first_step"]:03d}.json'
        if job['step'] > begin['first_step'] and job['delivery_sources'] != read(regular(first))['delivery_sources']:
            raise ValueError('Closeout correction cannot resolve new candidate originals')
    if job.get('role_budget') is not None and (job['role'] != 'W' or policy.get('role_budget_policy') is None):
        raise ValueError('Control role-budget routing differs from its frozen policy')
    from . import correction
    correction.validate_job(root, job)
    from . import semantic
    semantic.validate_job(root, job)
    if job.get('purpose') is None and job.get('handoff_protocol', 1) >= 5 and policy.get('search_policy') is not None:
        from . import search
        if job.get('search') != search.bind(root, job['step'], job['role'], job['handoff_protocol'], unified=job.get('lineage_projection_version') == 1,
                                            redirect=(job.get('role_budget') or {}).get('focus_source')):
            raise ValueError('Frozen scientific search binding changed')
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
    previous_seal = read(host_record(workspace(root, job['step'] - 1)) / 'result-identity.json') if any(
        ref['path'] == previous for ref in job['direct_refs']) else {}
    if job.get('input_selection_status') != previous_seal.get('control_outcome', {}).get('selection_status', 'applied'):
        raise ValueError('Bound implementation resolution differs from its predecessor')
    if job.get('control_diagnostics') != previous_seal.get('control_outcome', {}).get('diagnostics', []):
        raise ValueError('Bound control diagnostics differ from their predecessor')
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
    from .protocol import require_current
    require_current(root,read(regular(Path(root)/'jobs'/f'{step:03d}.json')))
    work = workspace(root, step)
    record = host_record(work)
    job_path = root / 'jobs' / f'{step:03d}.json'
    job = read(job_path)
    if (record / 'result-identity.json').exists():
        result = validate(work)
        from . import history
        history.refresh(root, step + 1) if job.get('purpose') is None else None
        return result
    from . import execution
    native_record = execution.record(root, step)
    intent = read(regular(native_record / 'native-intent.json'))
    if intent['task_sha256'] != digest(regular(job_path)):
        raise ValueError('Native launch task changed')
    _validate_inputs(root, work, job)
    outcome = read(regular(native_record / 'native-outcome.json'))
    if (type(outcome.get('returncode')) is not int or outcome['returncode'] != 0
            or outcome.get('stop_reason') or outcome['usage']['unknown_steps']):
        raise ValueError('Terminal scientific output is unverified or changed')
    raw_path = native_record / 'science-output.json'
    pending = native_record / 'result.pending.json'
    if outcome.get('output_status') == 'missing':
        if (outcome.get('raw_sha256') is not None or raw_path.exists() or raw_path.is_symlink()
                or pending.exists() or pending.is_symlink()):
            raise ValueError('Missing final output identity changed')
        from .output_repair import OutputRepairRequired
        raise OutputRepairRequired('missing_output', 'Return the required final scientific JSON; the completed work and checkpoints are already retained.')
    raw = regular(raw_path, limit=MAX_RESULT_BYTES)
    if outcome.get('raw_sha256') != digest(raw):
        raise ValueError('Terminal scientific output is unverified or changed')
    value = envelope(job, science_payload(raw, job['role'], job.get('handoff_protocol', 1)))
    if job['role']=='W':
        from . import worker_delivery
        if worker_delivery.applicable(job):
            from . import checkpoint
            if not (native_record/'checkpoint.json').exists():
                worker_delivery.writers_stopped(root,job,native_record)
                checkpoint.capture(root,job,native_record)
            else:checkpoint.validate(root,job,native_record)
        worker_delivery.require_delivery(root,job,value,native_record)
    control = None
    from . import semantic
    control = semantic.outcome(root, job, value)
    from . import correction
    correction.validate_payload(root, job, value)
    materials = collect_materials(root, step)
    unresolved = dict(items=[], omitted_count=0)
    entry_points = artifact_entry_points(work, value, materials, job.get('handoff_protocol', 1), unresolved)
    selected = selected_inputs(work, value, job)
    observations = None
    from . import history
    history.validate_recommendation(job, value)
    observations = history.capture(root, job, value, materials)
    _copy_bound(raw, work / 'conclusion.json', digest(raw))
    write(record / 'result.json', value)
    write(record / 'result-identity.json', dict(sha256=digest(record / 'result.json'), raw_sha256=digest(raw),
          job_sha256=digest(job_path), materials=materials, entry_points=entry_points,
          scope='Exact bytes and direct lineage; not scientific qualification',
          **(dict(execution_ref=execution.reference(root, step)) if execution.reference(root, step) is not None else {}),
          **(dict(control_outcome=control) if control is not None else {}),
          **(dict(unresolved_links=unresolved) if job.get('handoff_protocol', 1) >= 7 else {}),
          **(dict(selected_inputs=selected) if selected else {}),
          **(dict(observations=observations) if observations else {})))
    result = validate(work)
    history.refresh(root, step + 1) if job.get('purpose') is None else None
    return result


def _execution_raw(root, step):
    from . import execution
    return execution.raw(root, step)
