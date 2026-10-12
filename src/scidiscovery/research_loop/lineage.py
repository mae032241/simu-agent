"""Rebuildable declared relationships from sealed science and plugin facts.

This module never executes a domain experiment or imports a domain adapter.
"""
from __future__ import annotations

import copy
from pathlib import Path

from . import contracts as c, execution, history, search

MAX_CONTEXTS = 128


def _parent_original(root, item, available):
    """Bind the declared choice to an earlier exact completed call, never a name."""
    accepted=next((p for p in item['proofs'] if Path(p['path']).name=='accepted.json'),None)
    if accepted is None or accepted.get('retention')!='archived':
        raise ValueError('Accepted context original unavailable')
    original=c.read(c.regular(root/accepted['snapshot']))
    for key in ('call_id','scope','parent','change_intent'):
        if original.get(key)!=item[key]:
            raise history.ObserverIntegrityError('Context differs from accepted original')
    parent=item['parent'];binding=original.get('parent_binding')
    if parent['status']!='declared':
        if binding is not None:raise history.ObserverIntegrityError('Undeclared parent acquired a binding')
        return
    source=available.get(parent['candidate_id'])
    if source is None or source['status']!='known_success' or source['model'] is None:
        raise history.ObserverIntegrityError('Declared parent has no earlier completed original')
    completion=next((p for p in source['proofs'] if Path(p['path']).name=='completed.json'),None)
    if completion is None:raise history.ObserverIntegrityError('Parent completion original unavailable')
    model=source['model']
    expected=dict(call_id=source['call_id'],step=source['scope']['step'],completion_sha256=completion['sha256'],
                  model_sha256=model['sha256'],model_size_bytes=model['size_bytes'])
    same=source['scope']['step']==item['scope']['step']
    if (binding!=expected or parent['source']!=('same_node_completed_call' if same else 'sealed')
            or source['scope']['step']>item['scope']['step']):
        raise history.ObserverIntegrityError('Declared parent completion/artifact/source differs')


def contexts(root, job, items, archive, previous=()):
    """Validate plugin v2 against the actual frozen task/attempt before sealing."""
    if not isinstance(items,list) or len(items)>MAX_CONTEXTS:
        raise ValueError('Bounded execution contexts required')
    task=c.digest(root/'jobs'/f'{job["step"]:03d}.json')
    keys={execution.identity(root,job['step'],i) for i in range(len(execution.records(root,job['step'])))}
    mechanism=((job.get('search') or {}).get('focus') or {}).get('mechanism_ref')
    result=[];seen=set();available={item['candidate_id']:item for item in previous if item['status']=='known_success'}
    for item in items:
        if not isinstance(item,dict) or set(item)!={'call_id','scope','status','candidate_id','run_id','model','parent','change_intent','note','proofs'}:
            raise ValueError('Plugin context fields differ from contract2')
        if not isinstance(item['call_id'],str) or len(item['call_id'])>128 or item['call_id'] in seen:
            raise history.ObserverIntegrityError('Execution context identity is ambiguous')
        seen.add(item['call_id']);scope=item['scope']
        if (not isinstance(scope,dict) or set(scope)!={'step','role','job_sha256','execution_key','mechanism_ref'}
                or scope['step']!=job['step'] or scope['role']!=job['role'] or scope['job_sha256']!=task
                or scope['execution_key'] not in keys or scope['mechanism_ref']!=mechanism):
            raise history.ObserverIntegrityError('Execution context differs from frozen scientific task')
        if item['status'] not in {'known_success','known_failed','unknown'}:
            raise ValueError('Explicit known failed/unknown execution status required')
        parent=item['parent']
        if (not isinstance(parent,dict) or set(parent)!={'status','candidate_id','source'}
                or parent['status'] not in {'declared','declared_root','unknown'}
                or parent['source'] not in {'sealed','same_node_completed_call','none'}
                or (parent['status']=='declared')!=(parent['candidate_id'] is not None)):
            raise ValueError('Declared parent choice differs from contract2')
        if not isinstance(item['proofs'],list) or not 1<=len(item['proofs'])<=8:
            raise ValueError('Context originals are missing')
        proofs=[]
        for proof in item['proofs']:
            if not isinstance(proof,dict) or set(proof)!={'path','sha256','size_bytes'}:
                raise ValueError('Context original shape differs')
            original=archive(proof['path'])
            if original['sha256'] is None:raise ValueError('Context archive read capacity unavailable')
            if original['sha256']!=proof['sha256'] or original['size_bytes']!=proof['size_bytes']:
                raise history.ObserverIntegrityError('Execution context original changed')
            proofs.append(original)
        model=None
        if item['model'] is not None:
            model=archive(item['model']['path'])
            if model['sha256'] is None:raise ValueError('Context model read capacity unavailable')
            if model['sha256']!=item['model']['sha256'] or model['size_bytes']!=item['model']['size_bytes']:
                raise history.ObserverIntegrityError('Execution artifact changed')
        if ((item['status']=='known_success')!=(model is not None)
                or (item['status']!='unknown' and (type(item['run_id']) is not int or item['run_id']<1 or not isinstance(item['candidate_id'],str)))):
            raise ValueError('Failed/unknown context cannot acquire model qualification')
        validated={**item,'proofs':proofs,'model':model}
        _parent_original(root,validated,available)
        result.append(validated)
        if validated['status']=='known_success':available[validated['candidate_id']]=validated
    return result


def build(root, before_step):
    """Fold relations without rendering a default packet or updating authority."""
    sources=[history._source(root,step) for step in range(1,before_step)]
    state=dict(mechanisms={},current_h=None,scope=None,plan=None,authorized=set(),focus=None,accepted_slices=[],repairs={})
    nodes=[];candidates={};edges=[];calls=set();coverage='complete';available={}
    for job,payload,seal,_ in sources:
        step=job['step']
        if c.settings(root).get('search_policy') is not None:
            search.apply_source(root,job,payload,seal,state)
        nodes.append(dict(step=step,role=job['role'],parents=[int(Path(r['path']).parts[2]) for r in job['direct_refs']],
                          source_sha256=seal['raw_sha256'],summary=payload['summary'],limitations=payload['limitations']))
        for selected in seal.get('selected_inputs',[]):
            edges.append(dict(kind='reuse',subject=dict(node=step),target=dict(node=selected['origin_step'],material=selected['material']),scope='declared_handoff_not_proven_read'))
        receipt=seal.get('observations')
        if not receipt:coverage='partial';continue
        observation=c.read(root/receipt['path'])
        if observation['coverage']['status']!='complete':coverage='partial'
        for row in observation['candidates']:
            if row['id'] in candidates and candidates[row['id']]['observation']!=row:
                raise ValueError('Candidate identity changed')
            candidates.setdefault(row['id'],dict(observation=row,mechanism_ref=None,parent=None,derivation='unknown',support='unknown'))
        for context in observation.get('contexts',[]):
            if context['call_id'] in calls:raise ValueError('Context was sealed more than once')
            calls.add(context['call_id']);candidate=context['candidate_id']
            _parent_original(root,context,available)
            if context['status']=='known_success':available[candidate]=context
            if context['status']=='unknown':coverage='partial';continue
            if candidate not in candidates:raise ValueError('Context has no observed candidate')
            parent=context['parent'];item=candidates[candidate]
            item.update(execution_status=context['status'],mechanism_ref=context['scope']['mechanism_ref'],
                        parent=parent['candidate_id'],derivation=parent['status'],context=context)
            if context['status']=='known_success' and parent['status']=='declared':
                if parent['candidate_id'] not in candidates:raise ValueError('Declared parent has no exact original')
                edges.append(dict(kind='derivation',subject=candidate,target=parent['candidate_id'],scope='declared_not_proven_causality',call_id=context['call_id']))
    # Candidate ancestry is a DAG; names never supply missing historical edges.
    parents={edge['subject']:edge['target'] for edge in edges if edge['kind']=='derivation'}
    for candidate in parents:
        visiting=set();current=candidate
        while current in parents:
            if current in visiting:raise ValueError('Candidate derivation cycle')
            visiting.add(current);current=parents[current]
    return dict(nodes=nodes,mechanisms=copy.deepcopy(state['mechanisms']),candidates=candidates,relations=edges,
                coverage=coverage,limitation='Declared choices and observed call bindings; no inherited scientific or audit qualification')
