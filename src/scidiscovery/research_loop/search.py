"""Frozen W slices and scientific commitments derived from original nodes."""
from __future__ import annotations

from . import execution

import json
import copy
import re

from . import budget, contracts as c, history

DEFAULT_POLICY = dict(max_w_seconds=900.0, max_w_observed_tokens=2_000_000, max_requested_repairs=2)
MAX_VIEW_BYTES = 4096
MAX_COMMITMENTS = 4
MODES = ('screen', 'improve', 'repair')


class UnresolvedSearch(ValueError):
    def __init__(self, code, subject, message):
        super().__init__(message)
        self.code, self.subject = code, subject


def policy(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULT_POLICY):
        raise ValueError('Search policy requires three exact finite ceilings')
    seconds = value['max_w_seconds']
    if type(seconds) not in (int, float) or not 0 < seconds < float('inf'):
        raise ValueError('W slice seconds must be positive and finite')
    if any(type(value[key]) is not int or value[key] <= 0
           for key in ('max_w_observed_tokens', 'max_requested_repairs')):
        raise ValueError('W tokens and repair ceilings must be positive integers')
    return dict(value)


def _object(properties, *, nullable=False):
    return dict(type=['object', 'null'] if nullable else 'object', properties=properties,
                required=list(properties), additionalProperties=False)


def _text(limit=1024, nullable=False):
    return dict(type=['string', 'null'] if nullable else 'string', maxLength=limit, minLength=1)


def schema(role, protocol=6):
    focus = lambda key: _object({key: _text(80), 'action': dict(type='string', enum=list(MODES)),
        **({'repair_source': _text(512, nullable=True)} if protocol < 7 else {})}, nullable=True)
    if role == 'H':
        commitment = _object(dict(label=_text(80), minimal_test=_text(), existing_ref=_text(80, nullable=True)))
        value = _object(dict(scope=_text(), commitments=dict(type='array', maxItems=MAX_COMMITMENTS,
                items=commitment), focus=focus('label')), nullable=True)
        value['description'] = 'Declare science, not a ledger. When search is enabled, experiment needs a non-null plan and focus. Revisions preserve known mechanism refs.'
        if protocol >= 8:
            value['description'] = ('Declare at most four additions or revisions this round; omitted registered mechanisms '
                'and their statuses remain. Focus selects a newly declared label or an exact existing mechanism ref/unique '
                'label. A new focus requires its own declared commitment and minimal_test; never restate the whole portfolio.')
        return value
    if role == 'A':
        disposition = _object(dict(mechanism_ref=_text(80), status=dict(type='string',
            enum=['screened', 'deferred', 'waived', 'pending']), reason=_text(),
            **(dict(evidence=dict(type='array', maxItems=4, items=_text(512))) if protocol < 7 else {})))
        value = _object(dict(dispositions=dict(type='array', maxItems=MAX_COMMITMENTS,
                items=disposition), next_focus=focus('mechanism_ref')), nullable=True)
        value['description'] = 'Dispose commitments using scientific evidence. Null review or next_focus clears the next W focus; continue_w needs an explicit focus.'
        if protocol >= 7:
            value['description'] = ('Report only this round\'s changed dispositions; omitted mechanisms retain their sealed status. '
                'Same-status restatements are ignored and do not replace prior evidence or reasons. '
                'Explain scientific judgments in reason and scientific_result. The host binds the exact task lineage; '
                'screened needs a same-mechanism screen W, not a role-authored evidence path. '
                'Null review or next_focus clears the next W focus; continue_w needs an explicit focus.')
        return value
    raise ValueError('Only H and A declare scientific search choices')


def _evidence(root, job, path):
    match = re.fullmatch(r'inputs/parents/([0-9]{3,})/conclusion\.json|inputs/history/nodes/([0-9]{3,})/([0-9]{4,})\.json', path)
    if not match:
        raise ValueError('Search evidence requires a bound original scientific conclusion')
    step = int(match[1] or match[2])
    rows = job['direct_refs'] if match[1] else job.get('history', {}).get('files', [])
    row = next((row for row in rows if row['path'] == path), None)
    original = c.regular(c.workspace(root, job['step']) / path)
    if row is None or c.digest(original) != row['sha256'] or not 0 < step < job['step']:
        raise ValueError('Search scientific evidence is not exactly bound')
    source, _, _, _ = history._source(root, step)
    return source


def _apply_science(root, job, payload, state, diagnostics):
    mechanisms = state['mechanisms']
    if job['role'] == 'H':
        state['current_h'] = job['step']
        if job.get('handoff_protocol', 1) < 8:
            state['authorized'] = set()
            state['scope'] = None
        plan = payload.get('search_plan')
        state['plan'] = plan
        state['focus'] = None
        if plan is None:
            if job.get('handoff_protocol', 1) >= 8 and payload.get('next_action') == 'experiment':
                raise UnresolvedSearch('h_focus_unresolved', 'missing experiment plan', 'Experiment needs a declared scientific plan')
            return
        if not plan['scope'].strip():
            raise ValueError('H search scope must contain scientific content')
        labels, refs = {}, set()
        for index, item in enumerate(plan['commitments'], 1):
            if not item['label'].strip() or not item['minimal_test'].strip():
                raise ValueError('H commitments require distinct scientific labels and minimal tests')
            if item['label'] in labels:
                raise UnresolvedSearch('h_mechanism_unresolved', item['label'], 'H commitments require distinct scientific labels and minimal tests')
            ref = item['existing_ref']
            if ref is not None and ref not in mechanisms:
                raise UnresolvedSearch('h_mechanism_unresolved', ref, 'H revision must name an original known mechanism')
            ref = ref or f'h{job["step"]:03d}.m{index}'
            if ref in refs:
                raise UnresolvedSearch('h_mechanism_unresolved', ref, 'H revision repeats one mechanism identity')
            refs.add(ref);labels[item['label']] = ref
            if ref not in mechanisms:
                mechanisms[ref] = dict(status='pending', original_h=job['step'])
            mechanisms[ref].update(label=item['label'], minimal_test=item['minimal_test'], source_h=job['step'])
        state['scope'] = plan['scope']
        state['authorized'] = state['authorized'] | refs if job.get('handoff_protocol', 1) >= 8 else refs
        if plan['focus'] is not None:
            focus = plan['focus']
            selected = labels.get(focus['label'])
            if selected is None and job.get('handoff_protocol', 1) >= 8:
                matches = [ref for ref in state['authorized']
                           if ref == focus['label'] or mechanisms[ref]['label'] == focus['label']]
                selected = matches[0] if len(matches) == 1 else None
            if selected is None:
                raise UnresolvedSearch('h_focus_unresolved', focus['label'], 'H focus must select a declared commitment')
            state['focus'] = dict(mechanism_ref=selected, action=focus['action'], repair_source=focus.get('repair_source'))
        elif job.get('handoff_protocol', 1) >= 8 and payload.get('next_action') == 'experiment':
            raise UnresolvedSearch('h_focus_unresolved', 'missing experiment focus', 'Experiment needs a declared scientific focus')
    elif job['role'] == 'A':
        review = payload.get('search_review')
        state['focus'] = None
        if review is None:
            return
        refs = set()
        repeated = {item['mechanism_ref'] for item in review['dispositions']
                    if sum(other['mechanism_ref'] == item['mechanism_ref'] for other in review['dispositions']) > 1}
        for item in review['dispositions']:
            ref = item['mechanism_ref']
            if not item['reason'].strip():
                raise ValueError('A dispositions require distinct known mechanisms and scientific reasons')
            if ref not in mechanisms or ref in repeated:
                if job.get('handoff_protocol', 1) >= 8:
                    diagnostics.append(dict(code='a_mechanism_unresolved', subject=ref))
                    continue
                raise UnresolvedSearch('a_mechanism_unresolved', ref,
                    'A dispositions require distinct known mechanisms and scientific reasons')
            refs.add(ref)
            # Sealed originals own existing state. Redundant prose is retained
            # in the author's output, but neither changes nor re-proves it.
            if item['status'] == mechanisms[ref]['status']:
                continue
            if job.get('handoff_protocol', 1) >= 7:
                sources = [source for source, _, _ in history.direct_sources(root, job)] if item['status'] == 'screened' else []
            else:
                sources = [_evidence(root, job, path) for path in item['evidence']]
            if job.get('handoff_protocol', 1) < 7 and item['status'] != 'pending' and not sources:
                raise ValueError('A mechanism disposition requires original evidence')
            screens = [source for source in sources if source['role'] == 'W'
                    and ((source.get('search') or {}).get('focus') or {}).get('mechanism_ref') == ref
                    and source['search']['focus']['action'] == 'screen']
            if item['status'] == 'screened' and (not screens or (job.get('handoff_protocol', 1) >= 7 and len(screens) != 1)):
                if job.get('handoff_protocol', 1) >= 8:
                    diagnostics.append(dict(code='screen_source_ambiguous' if screens else 'screen_source_unavailable', subject=ref))
                    continue
                raise UnresolvedSearch('screen_source_ambiguous' if screens else 'screen_source_unavailable', ref,
                    'Screened requires same-mechanism W screening evidence')
            mechanisms[ref]['status'] = item['status']
        state['focus'] = dict(review['next_focus'], repair_source=review['next_focus'].get('repair_source')) if review['next_focus'] else None
        if state['focus'] is not None and state['focus']['mechanism_ref'] not in mechanisms:
            if job.get('handoff_protocol', 1) >= 8:
                diagnostics.append(dict(code='a_focus_unresolved', subject=state['focus']['mechanism_ref']))
                state['focus'] = None
            else:
                raise UnresolvedSearch('a_focus_unresolved', state['focus']['mechanism_ref'],
                    'A focus must name an original known mechanism')


def _apply(root, job, payload, state):
    diagnostics = []
    before = copy.deepcopy(state) if job.get('handoff_protocol', 1) >= 8 else None
    try:
        _apply_science(root, job, payload, state, diagnostics)
    except UnresolvedSearch as error:
        if before is None:
            raise
        state.clear();state.update(before)
        state['current_h'] = job['step']
        state['focus'] = None  # Preserve the attempt; it did not authorize a W.
        diagnostics.append(dict(code=error.code, subject=error.subject))
    return diagnostics


def assess_payload(root, job, payload, *, legacy_attempt=False):
    """A bounded host interpretation, never a scientific correctness verdict."""
    state = project(root, job['step'])
    if legacy_attempt:
        if job.get('handoff_protocol', 1) != 7:
            raise ValueError('Only a terminal protocol7 attempt supports semantic retention')
        try:
            _apply(root, job, payload, copy.deepcopy(state))
        except UnresolvedSearch:
            pass
        else:
            raise ValueError('A valid legacy result must retain its original interpretation')
    interpreted = dict(job, handoff_protocol=8) if legacy_attempt else job
    return _apply(root, interpreted, payload, state)


def apply_source(root, job, payload, seal, state):
    """The existing per-node interpretation guard, shared with read-only lineage."""
    receipt = seal.get('control_outcome')
    if receipt is not None:
        if receipt.get('binding_protocol') != 8 or job.get('handoff_protocol', 1) not in {7, 8}:
            raise ValueError('Control interpretation binding changed')
        if job.get('handoff_protocol', 1) == 7:
            try:
                _apply(root, job, payload, copy.deepcopy(state))
            except UnresolvedSearch:
                pass
            else:
                raise ValueError('Legacy valid science cannot be reinterpreted')
        diagnostics = _apply(root, dict(job, handoff_protocol=8), payload, state)
        if (receipt.get('search_status') != ('unresolved' if diagnostics else 'applied')
                or [row for row in receipt['diagnostics'] if not row['code'].startswith('implementation_')] != diagnostics):
            raise ValueError('Search outcome differs from its original scientific attempt')
    else:
        _apply(root, job, payload, state)


def fold(root, sources):
    state = dict(mechanisms={}, current_h=None, scope=None, plan=None, authorized=set(), focus=None,
                 accepted_slices=[], repairs={})
    for job, payload, seal, _ in sources:
        step = job["step"]
        apply_source(root, job, payload, seal, state)
        intent = execution.record(root, step) / 'native-intent.json'
        if job['role'] == 'W' and job.get('search') and intent.exists():
            value = c.read(c.regular(intent))
            if value['task_sha256'] != c.digest(root / 'jobs' / f'{step:03d}.json'):
                raise ValueError('W dispatch identity changed')
            outcome = c.read(execution.record(root, step) / 'native-outcome.json')
            observation = c.read(root / seal['observations']['path']) if seal.get('observations') else None
            state['accepted_slices'].append(dict(step=step, focus=job['search']['focus'],
                meter=outcome.get('search_slice'), observed_new_candidates=len(observation['candidates']) if observation else None,
                candidate_coverage=observation['coverage']['status'] if observation else 'unknown'))
            focus = job['search']['focus']
            if focus and focus['action'] == 'repair':
                repair_root = job['search']['repair_root']
                state['repairs'][repair_root] = state['repairs'].get(repair_root, 0) + 1
    return state


def project(root, before_step):
    return fold(root, history.source_sequence(root, before_step))


def bind(root, step, role, protocol=6, *, write_pages=True, state=None, unified=False):
    limits = c.settings(root).get('search_policy')
    if limits is None:
        return None
    limits = policy(limits)
    state = project(root, step) if state is None else state
    focus = state['focus'] if role == 'W' else None
    repair_root = None
    repair_binding = None
    if focus is not None and focus['action'] == 'repair':
        # The latest scientific chooser owns this path in its original workspace.
        chooser_step = max(index for index in range(1, step)
            if c.read(root / 'jobs' / f'{index:03d}.json')['role'] in {'H', 'A'})
        chooser = c.read(root / 'jobs' / f'{chooser_step:03d}.json')
        if chooser.get('handoff_protocol', 1) >= 7:
            sources = [source for source, _, _ in history.direct_sources(root, chooser)
                       if source['role'] == 'W' and ((source.get('search') or {}).get('focus') or {}).get('mechanism_ref') == focus['mechanism_ref']]
            repair_binding = 'available' if len(sources) == 1 else 'ambiguous' if sources else 'unavailable'
            source = sources[0] if len(sources) == 1 else None
        else:
            if focus['repair_source'] is None:
                raise ValueError('Repair requests require an exact original W conclusion')
            source = _evidence(root, chooser, focus['repair_source'])
            if source['role'] != 'W' or ((source.get('search') or {}).get('focus') or {}).get('mechanism_ref') != focus['mechanism_ref']:
                raise ValueError('Repair source must be a same-mechanism W original')
        if source is not None:
            repair_root = source['search'].get('repair_root') or source['step']
    elif focus is not None and focus['repair_source'] is not None:
        raise ValueError('Only repair requests may name a repair source')
    if unified:
        return dict(focus=focus, repair_root=repair_root, limits=limits, files=[],
                    **(dict(repair_binding=repair_binding) if protocol >= 7 else {}))
    pending = [ref for ref, item in state['mechanisms'].items() if item['status'] == 'pending']
    def clip(text, size):
        return text.encode()[:size].decode('utf-8', errors='ignore')
    choices = list(dict.fromkeys([*(list(state['authorized'])), *pending]))
    choices.sort(key=lambda ref: (ref != (focus or {}).get('mechanism_ref'), ref not in pending, ref))
    rows = [dict(mechanism_ref=ref, label=clip(state['mechanisms'][ref]['label'], 80),
                 minimal_test=clip(state['mechanisms'][ref]['minimal_test'], 160), status=state['mechanisms'][ref]['status'],
                 original=f'inputs/history/nodes/{state["mechanisms"][ref]["source_h"]:03d}/0001.json') for ref in choices[:MAX_COMMITMENTS]]
    view = dict(scope=clip(state['scope'] or '', 240), commitments=rows, pending_count=len(pending),
        omitted_count=max(0, len(choices) - len(rows)), index='inputs/history/pages/0001.json' if step > 1 else None,
        focus=focus, accepted_w_slices=len(state['accepted_slices']),
        recent_w=[dict(step=row['step'], action=(row['focus'] or {}).get('action'),
            mechanism_ref=(row['focus'] or {}).get('mechanism_ref'), meter=row['meter'],
            observed_new_candidates=row['observed_new_candidates'], candidate_coverage=row['candidate_coverage'],
            original=f'inputs/history/nodes/{row["step"]:03d}/0001.json') for row in state['accepted_slices'][-2:]],
        candidate_count='Unknown unless covered by the sealed N2 observer; candidates are not dispatches.',
        slice=dict(**limits, soft_seconds=limits['max_w_seconds'] * .8, soft_observed_tokens=int(limits['max_w_observed_tokens'] * .8)),
        instructions='H declares scientific scope/commitments; A disposes exact refs with bound conclusion paths. '
            'Enabled experiment needs a non-null H plan/focus. A null review/next_focus clears focus; continue_w needs an explicit focus. '
            'Before deep improvement screen pending commitments or justify deferral/waiver. W reports ordinary science; '
            'W follows its bound focus and does not invent a new mechanism. '
            'do not maintain a ledger. Soft windows are initial advice, not notifications. Hard overruns retain unsealed failure.')
    if protocol >= 7:
        view['instructions'] = ('H declares scientific scope and mechanisms; A reports only changed dispositions. '
            'Omissions and same-status restatements retain sealed state. Choose mechanisms/actions and explain scientific reasons; '
            'the host binds screening and repair tasks, not scientific support. Do not write evidence paths or repair sources. '
            'Enabled experiment needs an H plan/focus; continue_w needs next_focus. Screen pending mechanisms before improvement '
            'or explain deferral/waiver. W follows its frozen focus and reports science, not a ledger. '
            'Hard slice overruns retain unsealed failure; soft windows are advice.')
        view['focus'] = {key: value for key, value in focus.items() if key != 'repair_source'} if focus else None
        view['repair_binding'] = repair_binding
    if budget.node_mode(root)=='soft':
        view['instructions']=view['instructions'].replace(
            'Hard slice overruns retain unsealed failure; soft windows are advice.',
            'Node time/token budgets are soft targets: preserve results and conclude near targets; shared limits remain hard.')
        view['instructions']=view['instructions'].replace(
            'Soft windows are initial advice, not notifications. Hard overruns retain unsealed failure.',
            'Soft targets are advice, not live notifications. Shared hard limits retain unsealed failure.')
    files = []
    if protocol >= 8:
        view['instructions'] += (' H plans contain only this round\'s additions/revisions (at most four), not the whole '
            'portfolio. Omitted registered commitments stay active. Focus names a declared new label or unique existing '
            'label/ref; undeclared new mechanisms never acquire authorization. Read mechanism_index for other identities; '
            'Choose by mechanism_ref when a label is truncated; short excerpts link to the original H conclusion.')
        registry = [dict(mechanism_ref=ref, label=clip(item['label'], 80), label_truncated=len(item['label'].encode()) > 80, status=item['status'],
                         minimal_test=clip(item['minimal_test'], 160),
                         minimal_test_truncated=len(item['minimal_test'].encode()) > 160,
                         original=f'inputs/history/nodes/{item["source_h"]:03d}/0001.json')
                    for ref, item in sorted(state['mechanisms'].items())]
        prefix = 'inputs/search/mechanisms'
        for offset in range(0, len(registry), 16):
            number = offset // 16 + 1
            path = f'{prefix}/{number:04d}.json'
            value = dict(mechanisms=registry[offset:offset + 16],
                next_page=f'{prefix}/{number + 1:04d}.json' if offset + 16 < len(registry) else None,
                omitted_count=max(0, len(registry) - offset - 16))
            raw = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
            if len(raw) > history.MAX_PAGE_BYTES:
                raise ValueError('Mechanism navigation exceeds page byte capacity')
            if write_pages:
                destination = c.workspace(root, step) / path
                if destination.exists() or destination.is_symlink():
                    if c.regular(destination).read_bytes() != raw:
                        raise ValueError('Frozen mechanism navigation changed')
                else:
                    if (root / 'jobs' / f'{step:03d}.json').exists():
                        raise ValueError('Frozen mechanism navigation is missing')
                    if any(parent.is_symlink() for parent in destination.parents):
                        raise ValueError('Mechanism navigation directory is not original')
                    c.write(destination, value);destination.chmod(0o400)
                files.append(dict(path=path, sha256=c.digest(destination), size_bytes=len(raw)))
        view['mechanism_index'] = f'{prefix}/0001.json' if registry else None
        view['mechanism_count'] = len(registry)
    while len(json.dumps(view, ensure_ascii=False, indent=2).encode()) > MAX_VIEW_BYTES and len(view['commitments']) > 1:
        view['commitments'].pop()
        view['omitted_count'] += 1
    if len(json.dumps(view, ensure_ascii=False, indent=2).encode()) > MAX_VIEW_BYTES:
        raise ValueError('Default search view exceeds its byte bound')
    return dict(focus=focus, repair_root=repair_root, limits=limits, view=view,
                **(dict(files=files) if protocol >= 8 else {}),
                **(dict(repair_binding=repair_binding) if protocol >= 7 else {}))


def launch_reason(root, job):
    if job['role'] != 'W':
        return None
    if job.get('handoff_protocol', 1) >= 8 and job.get('input_selection_status') == 'unresolved':
        return 'implementation_unresolved'
    if c.settings(root).get('search_policy') is None:
        return None
    state = project(root, job['step'])
    focus = job['search']['focus']
    if focus is None:
        return 'search_focus_required'
    if focus['mechanism_ref'] not in state['authorized']:
        return 'search_focus_outside_h_scope'
    if focus['action'] == 'improve' and any(item['status'] == 'pending' for item in state['mechanisms'].values()):
        return 'search_commitments_pending'
    if focus['action'] == 'repair' and job['search'].get('repair_binding') in {'unavailable', 'ambiguous'}:
        return 'search_repair_source_' + job['search']['repair_binding']
    if focus['action'] == 'repair' and state['repairs'].get(job['search']['repair_root'], 0) >= job['search']['limits']['max_requested_repairs']:
        return 'search_repair_limit'
    return None


def validate_payload(root, job, payload):
    if job.get('handoff_protocol', 1) < 5 or c.settings(root).get('search_policy') is None:
        return
    state = project(root, job['step'])
    _apply(root, job, payload, state)


def accept(root, job):
    if job['role'] == 'W' and launch_reason(root, job):
        raise ValueError('W dispatch violates its frozen search authorization')
    if job.get('search') is None or job['role'] != 'W':
        return None
    stamp = budget.clock_stamp()
    return dict(task_sha256=c.digest(root / 'jobs' / f'{job["step"]:03d}.json'),
                boot_id=stamp['boot_id'], advance_seconds=budget.snapshot(root)['advance_seconds'])


def stop_reason(root, job, intent, limits, meter):
    anchor = intent.get('search_slice')
    if anchor is None:
        if job['role'] == 'W' and job.get('search') is not None:
            raise ValueError('Accepted W slice has no immutable meter anchor')
        return None
    if (anchor['task_sha256'] != c.digest(root / 'jobs' / f'{job["step"]:03d}.json')
            or anchor['boot_id'] != budget.clock_stamp()['boot_id']):
        raise ValueError('Accepted W slice meter identity changed')
    duration = limits['advance_seconds'] - anchor['advance_seconds']
    if duration < 0:
        raise ValueError('W slice consumption cannot move backwards')
    if budget.node_mode(root) == 'soft':
        return None
    if duration >= job['search']['limits']['max_w_seconds']:
        return 'w_slice_time_limit'
    if meter['input_tokens'] + meter['output_tokens'] >= job['search']['limits']['max_w_observed_tokens']:
        return 'w_slice_token_limit'
    return None


def report(root, job, intent, meter):
    anchor = intent.get('search_slice')
    if anchor is None:
        return None
    if anchor['boot_id'] != budget.clock_stamp()['boot_id']:
        raise ValueError('W slice boot changed before final metering')
    duration = budget.snapshot(root)['advance_seconds'] - anchor['advance_seconds']
    if duration < 0:
        raise ValueError('W slice consumption cannot move backwards')
    return dict(advance_seconds=duration, input_tokens=meter['input_tokens'],
                cached_input_tokens=meter['cached_input_tokens'], output_tokens=meter['output_tokens'],
                observed_tokens=meter['input_tokens'] + meter['output_tokens'], dispatches=1)
