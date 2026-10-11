"""Frozen W slices and scientific commitments derived from original nodes."""
from __future__ import annotations

import json
import re

from . import budget, contracts as c, history

DEFAULT_POLICY = dict(max_w_seconds=900.0, max_w_observed_tokens=2_000_000, max_requested_repairs=2)
MAX_VIEW_BYTES = 4096
MAX_COMMITMENTS = 4
MODES = ('screen', 'improve', 'repair')


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


def schema(role):
    focus = lambda key: _object({key: _text(80), 'action': dict(type='string', enum=list(MODES)),
                                'repair_source': _text(512, nullable=True)}, nullable=True)
    if role == 'H':
        commitment = _object(dict(label=_text(80), minimal_test=_text(), existing_ref=_text(80, nullable=True)))
        value = _object(dict(scope=_text(), commitments=dict(type='array', maxItems=MAX_COMMITMENTS,
                items=commitment), focus=focus('label')), nullable=True)
        value['description'] = 'Declare science, not a ledger. When search is enabled, experiment needs a non-null plan and focus. Revisions preserve known mechanism refs.'
        return value
    if role == 'A':
        disposition = _object(dict(mechanism_ref=_text(80), status=dict(type='string',
            enum=['screened', 'deferred', 'waived', 'pending']), reason=_text(),
            evidence=dict(type='array', maxItems=4, items=_text(512))))
        value = _object(dict(dispositions=dict(type='array', maxItems=MAX_COMMITMENTS,
                items=disposition), next_focus=focus('mechanism_ref')), nullable=True)
        value['description'] = 'Dispose commitments using scientific evidence. Null review or next_focus clears the next W focus; continue_w needs an explicit focus.'
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


def _apply(root, job, payload, state):
    mechanisms = state['mechanisms']
    if job['role'] == 'H':
        state['current_h'] = job['step']
        state['authorized'] = set()
        state['scope'] = None
        plan = payload.get('search_plan')
        state['plan'] = plan
        state['focus'] = None
        if plan is None:
            return
        if not plan['scope'].strip():
            raise ValueError('H search scope must contain scientific content')
        labels, refs = {}, set()
        for index, item in enumerate(plan['commitments'], 1):
            if not item['label'].strip() or not item['minimal_test'].strip() or item['label'] in labels:
                raise ValueError('H commitments require distinct scientific labels and minimal tests')
            ref = item['existing_ref']
            if ref is not None and ref not in mechanisms:
                raise ValueError('H revision must name an original known mechanism')
            ref = ref or f'h{job["step"]:03d}.m{index}'
            if ref in refs:
                raise ValueError('H revision repeats one mechanism identity')
            refs.add(ref);labels[item['label']] = ref
            if ref not in mechanisms:
                mechanisms[ref] = dict(status='pending', original_h=job['step'])
            mechanisms[ref].update(label=item['label'], minimal_test=item['minimal_test'], source_h=job['step'])
        state['scope'] = plan['scope']
        state['authorized'] = refs
        if plan['focus'] is not None:
            focus = plan['focus']
            if focus['label'] not in labels:
                raise ValueError('H focus must select a declared commitment')
            state['focus'] = dict(mechanism_ref=labels[focus['label']], action=focus['action'], repair_source=focus['repair_source'])
    elif job['role'] == 'A':
        review = payload.get('search_review')
        state['focus'] = None
        if review is None:
            return
        refs = set()
        for item in review['dispositions']:
            ref = item['mechanism_ref']
            if ref not in mechanisms or ref in refs or not item['reason'].strip():
                raise ValueError('A dispositions require distinct known mechanisms and scientific reasons')
            refs.add(ref)
            sources = [_evidence(root, job, path) for path in item['evidence']]
            if item['status'] != 'pending' and not sources:
                raise ValueError('A mechanism disposition requires original evidence')
            if item['status'] == 'screened' and not any(source['role'] == 'W'
                    and ((source.get('search') or {}).get('focus') or {}).get('mechanism_ref') == ref
                    and source['search']['focus']['action'] == 'screen' for source in sources):
                raise ValueError('Screened requires same-mechanism W screening evidence')
            mechanisms[ref]['status'] = item['status']
        state['focus'] = review['next_focus']
        if state['focus'] is not None and state['focus']['mechanism_ref'] not in mechanisms:
            raise ValueError('A focus must name an original known mechanism')


def project(root, before_step):
    state = dict(mechanisms={}, current_h=None, scope=None, plan=None, authorized=set(), focus=None,
                 accepted_slices=[], repairs={})
    for step in range(1, before_step):
        job, payload, seal, _ = history._source(root, step)
        _apply(root, job, payload, state)
        intent = c.host_record(c.workspace(root, step)) / 'native-intent.json'
        if job['role'] == 'W' and job.get('search') and intent.exists():
            value = c.read(c.regular(intent))
            if value['task_sha256'] != c.digest(root / 'jobs' / f'{step:03d}.json'):
                raise ValueError('W dispatch identity changed')
            outcome = c.read(c.host_record(c.workspace(root, step)) / 'native-outcome.json')
            observation = c.read(root / seal['observations']['path']) if seal.get('observations') else None
            state['accepted_slices'].append(dict(step=step, focus=job['search']['focus'],
                meter=outcome.get('search_slice'), observed_new_candidates=len(observation['candidates']) if observation else None,
                candidate_coverage=observation['coverage']['status'] if observation else 'unknown'))
            focus = job['search']['focus']
            if focus and focus['action'] == 'repair':
                repair_root = job['search']['repair_root']
                state['repairs'][repair_root] = state['repairs'].get(repair_root, 0) + 1
    return state


def bind(root, step, role):
    limits = c.settings(root).get('search_policy')
    if limits is None:
        return None
    limits = policy(limits)
    state = project(root, step)
    focus = state['focus'] if role == 'W' else None
    repair_root = None
    if focus is not None and focus['action'] == 'repair':
        if focus['repair_source'] is None:
            raise ValueError('Repair requests require an exact original W conclusion')
        # The latest scientific chooser owns this path in its original workspace.
        chooser_step = max(index for index in range(1, step)
            if c.read(root / 'jobs' / f'{index:03d}.json')['role'] in {'H', 'A'})
        chooser = c.read(root / 'jobs' / f'{chooser_step:03d}.json')
        source = _evidence(root, chooser, focus['repair_source'])
        if source['role'] != 'W' or ((source.get('search') or {}).get('focus') or {}).get('mechanism_ref') != focus['mechanism_ref']:
            raise ValueError('Repair source must be a same-mechanism W original')
        repair_root = source['search'].get('repair_root') or source['step']
    elif focus is not None and focus['repair_source'] is not None:
        raise ValueError('Only repair requests may name a repair source')
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
    while len(json.dumps(view, ensure_ascii=False, indent=2).encode()) > MAX_VIEW_BYTES and len(view['commitments']) > 1:
        view['commitments'].pop()
        view['omitted_count'] += 1
    if len(json.dumps(view, ensure_ascii=False, indent=2).encode()) > MAX_VIEW_BYTES:
        raise ValueError('Default search view exceeds its byte bound')
    return dict(focus=focus, repair_root=repair_root, limits=limits, view=view)


def launch_reason(root, job):
    if job['role'] != 'W' or c.settings(root).get('search_policy') is None:
        return None
    state = project(root, job['step'])
    focus = job['search']['focus']
    if focus is None:
        return 'search_focus_required'
    if focus['mechanism_ref'] not in state['authorized']:
        return 'search_focus_outside_h_scope'
    if focus['action'] == 'improve' and any(item['status'] == 'pending' for item in state['mechanisms'].values()):
        return 'search_commitments_pending'
    if focus['action'] == 'repair' and state['repairs'].get(job['search']['repair_root'], 0) >= job['search']['limits']['max_requested_repairs']:
        return 'search_repair_limit'
    return None


def validate_payload(root, job, payload):
    if job.get('handoff_protocol', 1) < 5 or c.settings(root).get('search_policy') is None:
        return
    state = project(root, job['step'])
    _apply(root, job, payload, state)


def accept(root, job):
    if job.get('search') is None or job['role'] != 'W':
        return None
    if launch_reason(root, job):
        raise ValueError('W dispatch violates its frozen search authorization')
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
