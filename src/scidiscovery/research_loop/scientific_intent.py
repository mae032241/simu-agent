"""Pure science allocation from a copied fold of exact sealed originals.

This parser does not publish, rank mechanisms, infer evidence or grant execution.
The caller supplies one eligible final W assessment, established from the original
A binding. A preliminary interpretation is committed only after all diagnostics
are resolved in the original control outcome.
"""
from __future__ import annotations

import copy


def resolve_intent(state, job, payload, *, assessed=None):
    mechanisms=state['mechanisms'];authorized=state['authorized']
    remaining=copy.deepcopy(state['order']['remaining'])
    seen=set(state['order']['seen_w'])
    role=job['role'];action=payload.get('next_action')
    choice=(payload.get('search_plan') if role=='H' else payload.get('search_review')) or {}
    declared=choice.get('focus' if role=='H' else 'next_focus')
    selected=None;diagnostics=[]
    if declared is not None and declared['label' if role=='H' else 'mechanism_ref'] is not None:
        name=declared['label' if role=='H' else 'mechanism_ref']
        matches=[name] if name in authorized else [ref for ref in authorized if mechanisms[ref]['label']==name]
        selected=matches[0] if len(matches)==1 else None
        if selected is None:
            diagnostics.append(dict(code='science_focus_ambiguous' if matches else 'science_focus_unauthorized',subject=name))
        elif mechanisms[selected]['status']=='waived':
            diagnostics.append(dict(code='science_focus_waived',subject=selected))
        elif not (payload.get('route_reason') or '').strip():
            diagnostics.append(dict(code='science_focus_reason_required',subject=selected))
    if declared is not None and declared['label' if role=='H' else 'mechanism_ref'] is None and declared['action']!='screen':
        diagnostics.append(dict(code='science_focus_required',subject=declared['action']))
    repair=declared is not None and declared['action']=='repair'
    if role=='A' and action not in {'audit','formal_review','extract','wait'} and assessed is not None:
        identity=assessed['identity']
        if identity not in seen:
            allocation=assessed.get('allocation')
            same_repair=repair and selected in (assessed.get('mechanism_refs') or [assessed['mechanism_ref']])
            if not same_repair:
                if assessed.get('breadth'):
                    disposed={row['mechanism_ref'] for row in choice.get('dispositions',[]) if row['status'] in {'screened','deferred','waived'} and mechanisms.get(row['mechanism_ref'],{}).get('status')==row['status']}
                    remaining=[item for item in remaining if item['mechanism_ref'] not in disposed]
                elif allocation is not None:
                    remaining=[item for item in remaining if item!=allocation]
                seen.add(identity)
    remaining=[item for item in remaining if mechanisms[item['mechanism_ref']]['status']!='waived']
    focus=None;allocation=None
    if action in {'experiment','continue_w'}:
        if declared is None:
            diagnostics.append(dict(code='science_task_action_required',subject='W scientific task'))
        elif selected is None and not diagnostics and declared['action']=='screen':
            available=[item for item in remaining if item['mechanism_ref'] in authorized]
            if not available:
                diagnostics.append(dict(code='science_plan_empty',subject='unfinished scientific plan'))
            else:
                selected=available[0]['mechanism_ref']
                focus=dict(mechanism_ref=selected,action='screen')
        elif selected is not None and not diagnostics:
            focus=dict(mechanism_ref=selected,action=declared['action'])
        if focus is not None:
            allocation=next((item for item in remaining if item['mechanism_ref']==selected),None)
    elif role not in {'H','A'} or action in {'audit','formal_review','extract','wait'}:
        focus=copy.deepcopy(state.get('focus'))
        allocation=copy.deepcopy(state['order'].get('allocation'))
    return dict(focus=focus,allocation=allocation,unfinished_plan=remaining,seen_w=seen,diagnostics=diagnostics)
