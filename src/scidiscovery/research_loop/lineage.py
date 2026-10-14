"""Rebuildable declared relationships from sealed science and plugin facts.

This module never executes a domain experiment or imports a domain adapter.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from . import contracts as c, history, search

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
    from .protocol import stage_scope
    expected_scope=stage_scope(root,job)
    result=[];seen=set();available={item['candidate_id']:item for item in previous if item['status']=='known_success'}
    for item in items:
        if not isinstance(item,dict) or set(item)!={'call_id','scope','status','candidate_id','run_id','model','parent','change_intent','note','proofs'}:
            raise ValueError('Plugin context fields differ from contract2')
        if not isinstance(item['call_id'],str) or len(item['call_id'])>128 or item['call_id'] in seen:
            raise history.ObserverIntegrityError('Execution context identity is ambiguous')
        seen.add(item['call_id']);scope=item['scope']
        if not isinstance(scope,dict) or scope!=expected_scope:
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


def build(root, before_step, *, sources=None, search_state=None):
    """Fold relations without rendering a default packet or updating authority."""
    sources=history.source_sequence(root,before_step) if sources is None else sources
    state=search.fold(root,sources) if search_state is None else search_state
    nodes=[];candidates={};edges=[];calls=set();coverage='complete';available={}
    for job,payload,seal,_ in sources:
        step=job['step']
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


def candidate_view(records):
    candidates, current, actual, selected, coverage = {}, None, None, None, None
    for record in records:
        observation = record['observation']
        if observation is not None:
            coverage = observation.get('coverage')
            for candidate in observation['candidates']:
                # Same scientific ID cannot silently point to another implementation
                # or evaluation. Metric updates require a different candidate ID.
                previous = candidates.get(candidate['id'])
                view = record.get('view', {})
                owner_step = int(candidate['implementation'].split('/')[2]) if candidate['implementation'] else None
                owner = next((row for row in records if row['step'] == owner_step), None)
                item = {**candidate, 'observation_step': record['step'], 'observation_h_scope': view.get('h_scope'),
                        'observation_summary': view.get('summary', '')[:160],
                        'observation_conclusion': next(iter(view.get('conclusion_pages', [])), None),
                        'implementation_owner_step': owner_step,
                        'implementation_conclusion': next(iter(owner.get('view', {}).get('conclusion_pages', [])), None) if owner else None,
                        'candidate_h_scope': None, 'parent_candidate': None, 'candidate_action': None}
                if previous and {k: previous[k] for k in candidate} != candidate:
                    raise ValueError('Observed candidate identity changed')
                candidates.setdefault(candidate['id'], item)
                if len(candidates) > 4096:
                    raise ValueError('Historical candidate count exceeds bound')
            current = (dict(candidate_id=observation['current_candidate']['candidate_id'], observed_at=record['step'])
                       if observation.get('current_candidate') is not None else None)
            if observation['actual_submission'] is not None:
                actual = dict(candidate_id=observation['actual_submission']['candidate_id'],
                              observed_at=record['step'], retention=observation['actual_submission'].get('artifact', {}).get('retention', 'unknown'))
        if record['recommendation'] is not None:
            if record['recommendation'] not in candidates:
                raise ValueError('A recommended an unknown candidate')
            selected = dict(candidate_id=record['recommendation'], author_step=record['step'])
    best = {}
    for item in candidates.values():
        if item['status'] != 'ok' or item['metric'] is None:
            continue
        key = (item['evaluation_key'], item['direction'])
        if key not in best or (item['metric'] > best[key]['metric'] if item['direction'] == 'max' else item['metric'] < best[key]['metric']):
            best[key] = item
    def public(item):
        return {key: item[key] for key in ('id', 'label', 'implementation', 'evaluation_key', 'metric', 'direction', 'status', 'observation_step', 'observation_h_scope', 'observation_summary', 'observation_conclusion', 'implementation_owner_step', 'implementation_conclusion', 'candidate_h_scope', 'parent_candidate', 'candidate_action')}
    def compact(item):
        view = public(item)
        for key, capacity in (('label', 160), ('evaluation_key', 192), ('observation_summary', 160)):
            text = view[key]
            view[key] = text.encode()[:capacity].decode('utf-8', errors='ignore')
            view[key + '_truncated'] = view[key] != text
        if view['implementation'] is not None and len(view['implementation'].encode()) > 512:
            view['implementation'] = None
        view['details_in_index'] = True
        return view
    return dict(coverage=coverage, current_candidate=current, candidate_index=[public(row) for row in candidates.values()], proxy_highest=[compact(row) for row in list(best.values())[:8]],
                proxy_groups_omitted_count=max(0, len(best) - 8),
                a_recommended=selected, actual_submission=actual,
                recent_candidates=[compact(row) for row in list(candidates.values())[-16:]],
                candidates_omitted_count=max(0, len(candidates) - 16),
                limitation='Highest means highest observed metric only; candidate models are not retained unless a sealed artifact or explicit archived snapshot exists. Proxy groups use the frozen adapter evaluation_key and direction; they do not establish target optimality. Read each original scientific conclusion for applicability and blind spots. Null slots mean unknown, not agreement.')



def _clip(text, capacity):
    return text.encode()[:capacity].decode('utf-8', errors='ignore')


def project(root, before_step, *, source_cutoff=None, extra_steps=()):
    """One verified source collection feeds all derived scientific navigation."""
    sources=history.source_sequence(root,before_step,source_cutoff=source_cutoff,extra_steps=extra_steps)
    records=history.records_from_sources(root,sources,write_cache=False)
    state=search.fold(root,sources) if c.settings(root).get('search_policy') is not None else None
    graph=build(root,before_step,sources=sources,search_state=state)
    return dict(sources=sources,records=records,search_state=state,graph=graph,candidates=candidate_view(records))


def brief(records, state, graph, candidates, indexes, *, selection_protocol=0):
    """The complete default lineage packet is bounded using its written bytes."""
    recent=[]
    for record in records[-2:]:
        view=record['view']
        recent.append(dict(step=record['step'],role=record['role'],summary=_clip(view['summary'],160),
            summary_truncated=view['summary_omitted_chars']>0 or len(view['summary'].encode())>160,
            limitation=_clip(next(iter(view['limitations']),''),96),
            limitations_omitted_count=max(0,len(view['limitations'])-1)+view['limitations_omitted_count'],
            original=view['conclusion_pages'][0]))
    focus=state['focus'] if state else None
    pending=[ref for ref,item in state['mechanisms'].items() if item['status']=='pending'] if state else []
    value=dict(indexes=indexes,node_count=len(records),recent=recent,
        mechanisms=dict(availability='available' if state else 'unavailable',count=len(state['mechanisms']) if state else 0,pending_count=len(pending),
                        focus={k:v for k,v in focus.items() if k!='repair_source'} if focus else None),
        candidates=dict(count=len(candidates['candidate_index']),coverage=(dict(status=candidates['coverage']['status'],
            note=_clip(candidates['coverage']['note'],96),note_truncated=len(candidates['coverage']['note'].encode())>96) if candidates['coverage'] else None),
            current=candidates['current_candidate'],a_recommended=candidates['a_recommended'],actual=candidates['actual_submission'],
            proxy_highest=[{k:item[k] for k in ('id','evaluation_key','metric','direction')} for item in candidates['proxy_highest'][:2]],
            proxy_groups_omitted_count=candidates['proxy_groups_omitted_count']+max(0,len(candidates['proxy_highest'])-2)),
        relationships=dict(count=len(graph['relations']),coverage=graph['coverage'],scope='Declared derivation and reuse; support remains unknown without original scientific intent.'),
        access='Read index/next_page and original conclusion pages as needed. Unselected historical attachments are not mounted. '
               'Implementation IDs select exact objects; null keeps current selected inputs, [] clears, lists replace. '
               'Candidate recommendation, proxy highest and actual submission are independent; unknown/partial coverage is not a complete tree.')
    # Large user labels/focus are navigation excerpts, never a license to drop bounds.
    if value['mechanisms']['focus']:
        for key,text in list(value['mechanisms']['focus'].items()):
            if isinstance(text,str):value['mechanisms']['focus'][key]=_clip(text,80)
    for row in value['candidates']['proxy_highest']:
        row['evaluation_key']=_clip(row['evaluation_key'],192)
        row['evaluation_key_truncated']=any(item['id']==row['id'] and item['evaluation_key']!=row['evaluation_key'] for item in candidates['proxy_highest'])
    if selection_protocol == 1:
        from . import selection
        try:
            public = selection.project(selection.public_inputs(records))
        except ValueError:
            # Sources were verified before this optional projection. No broad
            # catch may cover source/hash/permission checks or scientific seals.
            public = dict(scope='unavailable', target_best=None, candidate_count=len(candidates['candidate_index']),
                coverage='unknown', current_candidate=None, a_recommended=None, historical_a_recommendation=None,
                observed_actual_submission=None, delivery=dict(state='unknown', current_confirmed=None, last_confirmed=None),
                proxy_highest=[], proxy_groups_omitted_count=0,
                unranked_ids=[], unranked_omitted_count=0, public_audits=[], audits_omitted_count=0,
                limitation='Public selection overview unavailable; inspect existing candidate and original conclusion indexes.')
        value['candidates'] = dict(public, selection_protocol=1)
    elif selection_protocol != 0:
        raise ValueError('Unsupported frozen selection protocol')
    return bounded_brief(value)


def bounded_brief(value):
    """Drop only navigation excerpts with explicit omissions, never bound identities."""
    value['recent_omitted_count']=value['node_count']-len(value['recent'])
    def size():return len((json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())
    while size()>history.MAX_BRIEF_BYTES and value['recent']:
        value['recent'].pop(0);value['recent_omitted_count']+=1
    if value['candidates'].get('selection_protocol') == 1:
        for field, omitted in (('public_audits','audits_omitted_count'), ('unranked_ids','unranked_omitted_count')):
            while size()>history.MAX_BRIEF_BYTES and value['candidates'].get(field):
                value['candidates'][field].pop();value['candidates'][omitted]+=1
    while size()>history.MAX_BRIEF_BYTES and value['candidates'].get('adapter_audits'):
        value['candidates']['adapter_audits'].pop();value['candidates']['adapter_audits_omitted_count']+=1
    order = value['mechanisms'].get('unfinished_plan')
    while size()>history.MAX_BRIEF_BYTES and order and len(order['remaining']) > 1:
        order['remaining'].pop();order['omitted_count']+=1
    while size()>history.MAX_BRIEF_BYTES and value['mechanisms'].get('overview'):
        value['mechanisms']['overview'].pop();value['mechanisms']['overview_omitted_count']+=1
    while size()>history.MAX_BRIEF_BYTES and value['candidates']['proxy_highest']:
        value['candidates']['proxy_highest'].pop();value['candidates']['proxy_groups_omitted_count']+=1
    while size()>history.MAX_BRIEF_BYTES and value.get('implementation_options'):
        value['implementation_options'].pop();value['implementation_options_omitted_count']+=1
    if size()>history.MAX_BRIEF_BYTES:raise ValueError('Unified lineage brief metadata exceeds its frozen byte bound')
    return value


def public_relations(graph, sources):
    originals={job['step']:(job,seal) for job,_,seal,_ in sources}
    rows=[]
    for edge in graph['relations']:
        if edge['kind']=='reuse':
            step=edge['target']['node'];job,seal=originals[step]
            materials=sorted(seal['materials'],key=lambda row:row['path'])
            index=next((i for i,row in enumerate(materials,1) if row==edge['target']['material']),None)
            if index is None:raise ValueError('Reuse relationship has no exact sealed implementation')
            rows.append(dict(kind='reuse',node=edge['subject']['node'],implementation_id=f'{job["role"]}{step:03d}-I{index:03d}',
                label=_clip(Path(materials[index-1]['path']).name,80),source_node=step,
                original=f'inputs/history/nodes/{step:03d}/0001.json',scope=edge['scope']))
        else:
            rows.append({key:edge[key] for key in ('kind','subject','target','scope')})
    return rows


def bind(root, step, role, protocol, *, source_cutoff=None, extra_steps=(), selection_protocol=0,
         audit_projection_version=0, adjacent_audit=None):
    from .protocol import require_current
    require_current(root)
    projection=project(root,step,source_cutoff=source_cutoff,extra_steps=extra_steps)
    records,state=projection['records'],projection['search_state']
    add,paged,files=history.page_writer(c.workspace(root,step))
    for record,source in zip(records,projection['sources']):
        job,_,seal,_=source
        options=[dict(id=f'{job["role"]}{job["step"]:03d}-I{number:03d}',label=_clip(Path(item['path']).name,80),
                      label_truncated=len(Path(item['path']).name.encode())>80)
                 for number,item in enumerate(sorted(seal['materials'],key=lambda row:row['path']),1)]
        paths=paged(options,16,'implementations',f'inputs/history/implementations/{record["step"]:03d}','sealed-implementation-objects')
        view=record['view'];view['implementation_index']=paths[0] if paths else None
        view['implementations']=options[:16];view['implementations_omitted_count']=max(0,len(options)-16)
        view['summary_truncated']=view['summary_omitted_chars']>0 or len(view['summary'].encode())>160
        view['summary']=_clip(view['summary'],160)
        view['limitations_truncated']=view['limitations_omitted_chars']>0 or any(len(text.encode())>96 for text in view['limitations'])
        view['limitations']=[_clip(text,96) for text in view['limitations']]
        for path,detail in zip(view['conclusion_pages'],record['detail']):add(path,detail)
    nodes=paged([row['view'] for row in records],8,'records','inputs/history/pages','sealed-scientific-nodes')
    overview=projection['candidates'];candidate_rows=overview['candidate_index']
    for row in candidate_rows:
        relation=projection['graph']['candidates'].get(row['id'],{})
        row.update(parent_candidate=relation.get('parent'),mechanism_ref=relation.get('mechanism_ref'),
                   derivation=relation.get('derivation','unknown'),support=relation.get('support','unknown'),
                   execution_status=relation.get('execution_status','unknown'))
    candidates=paged(candidate_rows,16,'candidates','inputs/history/candidates','observed-candidates')
    mechanisms=[dict(mechanism_ref=ref,label=_clip(item['label'],80),label_truncated=len(item['label'].encode())>80,
                     minimal_test=_clip(item['minimal_test'],160),minimal_test_truncated=len(item['minimal_test'].encode())>160,
                     status=item['status'],original=f'inputs/history/nodes/{item["source_h"]:03d}/0001.json')
                for ref,item in sorted(state['mechanisms'].items())] if state else []
    if state and 'portfolio' in state:
        for row in mechanisms:
            row['completed_cycles_in_window'] = state['portfolio']['invested'].get(row['mechanism_ref'], 0)
            row['deferred_cycles_in_window'] = state['portfolio']['deferred'].get(row['mechanism_ref'], 0)
            if state and 'portfolio' in state:
                pending = state['portfolio']['pending_w'] if role == 'A' else None
                row['deferred_cycles_if_assessed'] = (row['deferred_cycles_in_window'] + 1
                    if pending and row['mechanism_ref'] != pending['branch'] and row['status'] in {'pending', 'deferred'}
                    else 0 if pending and row['mechanism_ref'] == pending['branch'] else row['deferred_cycles_in_window'])
    mechanism_pages=paged(mechanisms,16,'mechanisms','inputs/lineage/mechanisms','sealed-H-A-interpretation')
    order_rows = [dict(mechanism_ref=item['mechanism_ref'], label=_clip(state['mechanisms'][item['mechanism_ref']]['label'], 80),
                       original=f'inputs/history/nodes/{item["planned_step"]:03d}/0001.json')
                  for item in state['order']['remaining']] if state else []
    order_pages = paged(order_rows, 16, 'opportunities', 'inputs/lineage/order', 'sealed-scientific-exploration-order') if state else []
    relations=paged(public_relations(projection['graph'],projection['sources']),16,'relations','inputs/lineage/relations','declared-not-proven-causality')
    indexes=dict(nodes=nodes[0] if nodes else None,candidates=candidates[0] if candidates else None,
                 mechanisms=mechanism_pages[0] if mechanism_pages else None,relations=relations[0] if relations else None)
    audit_refs, audit_rows = [], []
    if audit_projection_version == 1:
        from . import candidate_audit
        audit_refs = candidate_audit.collect_refs(root, projection['sources'], step=step, adjacent=adjacent_audit)
        audit_rows = candidate_audit.project_receipts(root, records, audit_refs)
        for index, row in enumerate(audit_rows):
            row['original'] = f'inputs/lineage/audits/{index // 16 + 1:04d}.json'
        audit_pages = paged(audit_rows, 16, 'adapter_audits', 'inputs/lineage/audits', 'frozen-adapter-audit-receipts')
        indexes['audits'] = audit_pages[0] if audit_pages else None
    elif audit_projection_version != 0:
        raise ValueError('Unsupported frozen audit projection')
    view=brief(records,state,projection['graph'],overview,indexes,selection_protocol=selection_protocol)
    if state and 'portfolio' in state:
        threshold = c.settings(root)['portfolio_policy']['review_after_cycles']
        ordered = sorted(mechanisms, key=lambda row: (
            0 if row['status'] in {'pending', 'deferred'} and row.get('deferred_cycles_if_assessed', row['deferred_cycles_in_window']) >= threshold else
            1 if row['status'] in {'pending', 'deferred'} else 2,
            -row.get('deferred_cycles_if_assessed', row['deferred_cycles_in_window']), row['mechanism_ref']))
        view['mechanisms'].update(overview=ordered[:4], overview_omitted_count=max(0, len(ordered)-4),
                                  index=indexes['mechanisms'],
                                  portfolio=search.portfolio_view(state, threshold, prospective=role == 'A', version=2))
    if state:
        view['mechanisms']['unfinished_plan']=dict(remaining=order_rows[:4],remaining_count=len(order_rows),
            omitted_count=max(0,len(order_rows)-4),index=order_pages[0] if order_pages else None,
            rule='Original unfinished opportunities before this A assessment. Null follows the plan; explicit scientific selection does not reorder or discard omitted items. Only an eligible final W assessment consumes its allocation.')
    bounded_brief(view)
    if audit_projection_version == 1:
        candidates_view = view['candidates']
        if selection_protocol == 1:
            explicit = [row for row in candidates_view['public_audits'] if row['status'] != 'unknown']
            if explicit:
                candidates_view['public_audits'] = explicit
            else:
                candidates_view.pop('public_audits')
                candidates_view.pop('audits_omitted_count')
        candidates_view.update(adapter_audits=audit_rows[:2], adapter_audits_omitted_count=max(0, len(audit_rows)-2),
            leakage_assessment='Unknown unless explicitly reported; adapter status does not establish leakage or target suitability.')
        bounded_brief(view)
    return dict(**(dict(audit_projection_version=1, audit_receipts=audit_refs, adjacent_audit=adjacent_audit) if audit_projection_version == 1 else {}), nodes=[dict(step=row['step'],seal_sha256=row['seal_sha256']) for row in records],files=files,
                candidate_ids=[row['id'] for row in candidate_rows],view=view),state
