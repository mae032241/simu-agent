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


def schema(role, protocol=None):
    focus=lambda key:_object({key:_text(80),'action':dict(type='string',enum=list(MODES))},nullable=True)
    if role=='H':
        commitment=_object(dict(label=_text(80),minimal_test=_text(),existing_ref=_text(80,nullable=True)))
        value=_object(dict(scope=_text(),commitments=dict(type='array',maxItems=MAX_COMMITMENTS,items=commitment),focus=focus('label')),nullable=True)
        value['description']=('Declare at most four additions or revisions in scientific exploration order; omitted unfinished mechanisms remain. '
            'Null focus follows the confirmed unfinished plan. Explicit exact ref or unique label with route_reason selects scientific screen/improve/repair without rewriting an order table.')
        return value
    if role=='A':
        disposition=_object(dict(mechanism_ref=_text(80),status=dict(type='string',enum=['screened','deferred','waived','pending']),reason=_text()))
        value=_object(dict(dispositions=dict(type='array',maxItems=MAX_COMMITMENTS,items=disposition),next_focus=focus('mechanism_ref')),nullable=True)
        value['description']=('Declare only changed scientific dispositions; screened needs one same-mechanism final W original. '
            'Null next_focus follows the unfinished plan after this eligible final W assessment. '
            'An explicit exact ref or unique label plus route_reason may deepen another authorized mechanism. Do not write mechanical IDs, counts, paths or priorities.')
        return value
    raise ValueError('Only H and A declare scientific search choices')


def _assessed(root,job):
    if job['role']!='A' or job.get('purpose') is not None:return None
    original=history._source(root,job['author_correction']['root']['step'])[0] if job.get('author_correction') else job
    if original['role']!='A':return None
    sources=[source for source,_,_ in history.direct_sources(root,job) if source['role']=='W']
    if len(sources)!=1:return None
    source=sources[0]
    if not any(ref['path']==f'inputs/parents/{source["step"]:03d}/conclusion.json' for ref in original['direct_refs']):return None
    focus=(source.get('search') or {}).get('focus')
    if focus is None:return None
    seal=c.regular(c.host_record(c.workspace(root,source['step']))/'result-identity.json')
    return dict(identity=(source['step'],c.digest(seal)),mechanism_ref=focus['mechanism_ref'],allocation=source['search']['allocation'])


def _apply_science(root,job,payload,state,diagnostics):
    mechanisms=state['mechanisms']
    if job['role']=='H':
        state['current_h']=job['step']
        plan=payload.get('search_plan')
        if plan is not None:
            if not plan['scope'].strip():raise UnresolvedSearch('h_scope_empty','scope','H scope needs scientific content')
            labels=set();refs=set()
            for index,item in enumerate(plan['commitments'],1):
                if not item['label'].strip() or not item['minimal_test'].strip() or item['label'] in labels:
                    raise UnresolvedSearch('h_mechanism_unresolved',item['label'],'H commitments need distinct labels and minimal tests')
                labels.add(item['label']);ref=item['existing_ref']
                if ref is not None and ref not in mechanisms:raise UnresolvedSearch('h_mechanism_unresolved',ref,'Revision requires an exact registered mechanism')
                ref=ref or f'h{job["step"]:03d}.m{index}'
                if ref in refs:raise UnresolvedSearch('h_mechanism_unresolved',ref,'A revision cannot repeat one mechanism')
                refs.add(ref)
                if ref not in mechanisms:
                    mechanisms[ref]=dict(status='pending',original_h=job['step'])
                    state['order']['remaining'].append(dict(mechanism_ref=ref,planned_step=job['step']))
                mechanisms[ref].update(label=item['label'],minimal_test=item['minimal_test'],source_h=job['step'])
            state['scope']=plan['scope'];state['plan']=plan;state['authorized']|=refs
    elif job['role']=='A':
        review=payload.get('search_review') or dict(dispositions=[])
        repeated={item['mechanism_ref'] for item in review['dispositions'] if sum(other['mechanism_ref']==item['mechanism_ref'] for other in review['dispositions'])>1}
        for item in review['dispositions']:
            ref=item['mechanism_ref']
            if ref not in mechanisms or ref in repeated:
                diagnostics.append(dict(code='a_mechanism_unresolved',subject=ref));continue
            if not item['reason'].strip():
                diagnostics.append(dict(code='a_disposition_reason_required',subject=ref));continue
            if item['status']==mechanisms[ref]['status']:continue
            if item['status']=='screened':
                screens=[source for source,_,_ in history.direct_sources(root,job) if source['role']=='W'
                    and ((source.get('search') or {}).get('focus') or {}).get('mechanism_ref')==ref
                    and source['search']['focus']['action']=='screen']
                if len(screens)!=1:
                    diagnostics.append(dict(code='screen_source_ambiguous' if screens else 'screen_source_unavailable',subject=ref));continue
            mechanisms[ref]['status']=item['status']
    from .scientific_intent import resolve_intent
    interpretation=resolve_intent(state,job,payload,assessed=_assessed(root,job))
    diagnostics.extend(interpretation['diagnostics'])
    state['focus']=interpretation['focus']
    state['order'].update(remaining=interpretation['unfinished_plan'],seen_w=interpretation['seen_w'],allocation=interpretation['allocation'],diagnostics=interpretation['diagnostics'])


def interpret(root,job,payload,*,state=None):
    """One prospective interpretation; callers do not publish its mutations."""
    state=copy.deepcopy(project(root,job['step']) if state is None else state)
    diagnostics=[]
    try:_apply_science(root,job,payload,state,diagnostics)
    except UnresolvedSearch as error:diagnostics.append(dict(code=error.code,subject=error.subject))
    return dict(state=state,focus=state['focus'],allocation=state['order']['allocation'],diagnostics=diagnostics)


def assess_payload(root,job,payload):
    return interpret(root,job,payload)['diagnostics']


def apply_source(root,job,payload,seal,state):
    from .protocol import CURRENT
    receipt=seal['control_outcome']
    if job.get('handoff_protocol')!=CURRENT or receipt.get('binding_protocol')!=CURRENT:
        raise ValueError('Control interpretation binding changed')
    result=interpret(root,job,payload,state=state)
    diagnostics=result['diagnostics']
    reported=[row for row in receipt['diagnostics'] if not row['code'].startswith(('implementation_','a_decision_','a_portfolio_'))]
    if (receipt['search_status']!=('unresolved' if diagnostics else 'applied') or reported!=diagnostics[:len(reported)]
            or len(reported)<len(diagnostics) and not receipt['omitted_count']
            or receipt['resolved_focus']!=result['focus'] or receipt['resolved_allocation']!=result['allocation']):
        raise ValueError('Scientific intent differs from its sealed interpretation')
    if all(receipt.get(key)!='unresolved' for key in ('search_status','selection_status','decision_status','portfolio_status')):
        state.clear();state.update(result['state'])
    else:
        state['focus']=None
        state['order']['allocation']=None
        state['order']['diagnostics']=receipt['diagnostics']


def fold(root,sources):
    state=dict(mechanisms={},current_h=None,scope=None,plan=None,authorized=set(),focus=None,accepted_slices=[],repairs={},
        order=dict(remaining=[],seen_w=set(),allocation=None,diagnostics=[]))
    if c.settings(root).get('portfolio_policy') is not None:
        state['portfolio']=dict(invested={},deferred={},seen_w=set(),pending_w=None,last_branch=None,last_review=None)
    enabled=c.settings(root).get('search_policy') is not None
    for job,payload,seal,seal_sha in sources:
        if enabled:apply_source(root,job,payload,seal,state)
        if 'portfolio' in state:_portfolio_update(root,job,payload,seal,state,seal_sha)
        step=job['step'];intent=execution.record(root,step)/'native-intent.json'
        if job['role']=='W' and job.get('search') and intent.exists():
            value=c.read(c.regular(intent))
            if value['task_sha256']!=c.digest(root/'jobs'/f'{step:03d}.json'):raise ValueError('W dispatch identity changed')
            outcome=c.read(execution.record(root,step)/'native-outcome.json')
            observation=c.read(root/seal['observations']['path']) if seal.get('observations') else None
            state['accepted_slices'].append(dict(step=step,focus=job['search']['focus'],meter=outcome.get('search_slice'),
                observed_new_candidates=len(observation['candidates']) if observation else None,
                candidate_coverage=observation['coverage']['status'] if observation else 'unknown'))
            focus=job['search']['focus']
            if focus and focus['action']=='repair':
                repair_root=job['search']['repair_root'];state['repairs'][repair_root]=state['repairs'].get(repair_root,0)+1
    return state


def project(root,before_step):
    return fold(root,history.source_sequence(root,before_step))


def bind(root,step,role,protocol=None,*,write_pages=True,state=None,unified=True):
    limits=c.settings(root).get('search_policy')
    if limits is None:return None
    state=project(root,step) if state is None else state
    focus=state['focus'] if role=='W' else None
    repair_root=repair_binding=None
    if focus is not None and focus['action']=='repair':
        chooser_step=max(index for index in range(1,step) if c.read(root/'jobs'/f'{index:03d}.json')['role'] in {'H','A'})
        chooser=c.read(root/'jobs'/f'{chooser_step:03d}.json')
        sources=[source for source,_,_ in history.direct_sources(root,chooser) if source['role']=='W'
            and ((source.get('search') or {}).get('focus') or {}).get('mechanism_ref')==focus['mechanism_ref']]
        repair_binding='available' if len(sources)==1 else 'ambiguous' if sources else 'unavailable'
        if len(sources)==1:repair_root=sources[0]['search'].get('repair_root') or sources[0]['step']
    return dict(focus=focus,allocation=copy.deepcopy(state['order']['allocation']),unfinished_plan=copy.deepcopy(state['order']['remaining']),
        intent_diagnostics=state['order']['diagnostics'],repair_root=repair_root,repair_binding=repair_binding,limits=policy(limits),files=[])


def launch_reason(root,job):
    if job['role']!='W':return None
    if job.get('input_selection_status')=='unresolved':return 'implementation_unresolved'
    if c.settings(root).get('search_policy') is None:return None
    bound=job['search'];focus=bound['focus'];state=project(root,job['step'])
    if bound['intent_diagnostics']:return bound['intent_diagnostics'][0]['code']
    if focus is None:return 'science_plan_empty'
    if focus['mechanism_ref'] not in state['authorized']:return 'search_focus_outside_h_scope'
    if focus['action']=='repair' and bound['repair_binding'] in {'unavailable','ambiguous'}:return 'search_repair_source_'+bound['repair_binding']
    if focus['action']=='repair' and state['repairs'].get(bound['repair_root'],0)>=bound['limits']['max_requested_repairs']:return 'search_repair_limit'
    return None


def validate_payload(root,job,payload):
    if c.settings(root).get('search_policy') is None:return
    diagnostics=assess_payload(root,job,payload)
    if diagnostics:raise UnresolvedSearch(diagnostics[0]['code'],diagnostics[0]['subject'],'Scientific intent needs clarification')


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


def portfolio_policy(value):
    if (not isinstance(value, dict) or set(value) not in ({'review_after_cycles'}, {'review_after_cycles', 'version'})
            or type(value['review_after_cycles']) is not int or value['review_after_cycles'] <= 0):
        raise ValueError('Portfolio review needs a positive completed-cycle frequency')
    version = value.get('version', 2)
    if type(version) is not int or version != 2:
        raise ValueError('Unsupported frozen portfolio semantics')
    return dict(review_after_cycles=value['review_after_cycles'],version=2)


def _portfolio_cycle(portfolio, mechanisms, branch):
    portfolio['invested'][branch] = portfolio['invested'].get(branch, 0) + 1
    for ref, item in mechanisms.items():
        if ref != branch and item['status'] in {'pending', 'deferred'}:
            portfolio['deferred'][ref] = portfolio['deferred'].get(ref, 0) + 1
        else:
            portfolio['deferred'].pop(ref, None)
    portfolio['last_branch'] = branch


def _portfolio_update(root, job, payload, seal, state, seal_sha=None):
    portfolio, mechanisms = state['portfolio'], state['mechanisms']
    if job['role'] == 'W':
        focus = (job.get('search') or {}).get('focus')
        if focus and focus['mechanism_ref'] in mechanisms:
            identity=(job['step'],seal_sha)
            if focus['action']=='repair':
                original=job['search']['repair_root']
                identity=(original,c.digest(c.regular(c.host_record(c.workspace(root,original))/'result-identity.json')))
            portfolio['pending_w']=dict(step=job['step'],identity=identity,branch=focus['mechanism_ref'])
        return
    if job['role'] != 'A' or job.get('purpose') == 'closeout':
        return
    control = seal.get('control_outcome', {})
    valid = all(control.get(key) != 'unresolved' for key in ('search_status', 'selection_status', 'decision_status', 'portfolio_status'))
    ordinary = not job.get('author_correction') and payload.get('next_action') not in {'audit', 'extract', 'wait'}
    pending = portfolio['pending_w']
    original_cycle = ordinary
    if job.get('author_correction') and pending:
        original = history._source(root, job['author_correction']['root']['step'])[0]
        original_cycle = (original['role'] == 'A' and any(ref['path'] == f'inputs/parents/{pending["step"]:03d}/conclusion.json' for ref in original['direct_refs']))
    focus=state['focus']
    repairing=focus and focus['action']=='repair' and pending and focus['mechanism_ref']==pending['branch']
    if valid and original_cycle and not repairing and payload.get('next_action') not in {'audit', 'extract', 'wait'} and pending and any(ref['path'] == f'inputs/parents/{pending["step"]:03d}/conclusion.json' for ref in job['direct_refs']):
        if pending['identity'] not in portfolio['seen_w']:
            _portfolio_cycle(portfolio, mechanisms, pending['branch'])
            portfolio['seen_w'].add(pending['identity'])
        portfolio['pending_w'] = None
    # Audit/extraction/wait never renew the window. An author may clarify the
    # original global tradeoff without manufacturing another W+A cycle.
    if valid and payload.get('next_action') in {'continue_w', 'revise_h', 'finish'} and ((payload.get('portfolio_review') or '').strip() or
            (payload.get('search_review') or {}).get('next_focus') is not None and (payload.get('route_reason') or '').strip()):
        portfolio['invested'].clear();portfolio['deferred'].clear()
        portfolio['last_review'] = job['step']


def portfolio_due(portfolio,mechanisms,branch,threshold,*,version=2):
    if branch is None or branch not in mechanisms:return False
    overdue=lambda ref:mechanisms[ref]['status'] in {'pending','deferred'} and portfolio['deferred'].get(ref,0)>=threshold
    return not overdue(branch) and any(ref!=branch and overdue(ref) for ref in mechanisms)


def portfolio_assess(root,job,payload,*,interpretation=None,decision_diagnostics=None,selection_diagnostics=None):
    configured=c.settings(root).get('portfolio_policy')
    if configured is None or job['role']!='A' or job.get('purpose') is not None or payload['next_action']!='continue_w':return []
    interpretation=interpret(root,job,payload) if interpretation is None else interpretation
    state=copy.deepcopy(interpretation['state'])
    from . import decision
    if decision_diagnostics is None:decision_diagnostics=decision.assess(root,job,payload,focus=interpretation['focus'])
    if selection_diagnostics is None:
        selection_diagnostics=[];c.selected_inputs(c.workspace(root,job['step']),payload,job,selection_diagnostics)
    control=dict(search_status='unresolved' if interpretation['diagnostics'] else 'applied',
        selection_status='unresolved' if selection_diagnostics else 'applied',decision_status='unresolved' if decision_diagnostics else 'applied')
    _portfolio_update(root,job,payload,dict(control_outcome=control),state)
    focus=interpretation['focus'];branch=focus['mechanism_ref'] if focus else None
    explicit=(payload.get('search_review') or {}).get('next_focus') is not None
    explained=(payload.get('portfolio_review') or '').strip() or explicit and (payload.get('route_reason') or '').strip()
    if not explained and portfolio_due(state['portfolio'],state['mechanisms'],branch,configured['review_after_cycles']):
        return [dict(code='a_portfolio_review_required',subject=branch)]
    return []


def portfolio_view(state,threshold,*,prospective=False,version=2):
    portfolio=copy.deepcopy(state['portfolio'])
    if prospective and portfolio['pending_w']:_portfolio_cycle(portfolio,state['mechanisms'],portfolio['pending_w']['branch'])
    branch=portfolio['last_branch']
    overdue=[ref for ref,item in state['mechanisms'].items() if item['status'] in {'pending','deferred'} and portfolio['deferred'].get(ref,0)>=threshold]
    return dict(version=2,review_after_cycles=threshold,last_assessed_branch=branch,
        completed_cycles=state['portfolio']['invested'].get(branch,0),cycles_if_assessed=portfolio['invested'].get(branch,0),
        pending_assessment=bool(prospective and portfolio['pending_w']),overdue_count_if_assessed=len(overdue),
        review_required_for_non_overdue_selection=bool(overdue),last_review_step=portfolio['last_review'],
        scope='A compares scientific opportunity cost; explicit justified selection or portfolio_review may retain any route. Pending W assessment is not a completed cycle.')
