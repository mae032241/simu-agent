"""Scientific candidate references bound privately to unchanged canonical IDs.

Only declared candidate identity slots in framework-produced views are projected.
Scientific prose, metric names, source files and arbitrary user JSON are untouched.
"""
import copy
import re

_MACHINE_CANDIDATE=re.compile(r'local-[0-9a-f]{64}\Z')
_REFERENCE=re.compile(r'[HWAE]\d{3,}-C\d{3,}\Z')
_SLOTS={'id','candidate_id','candidate_ids','parent_candidate','original_candidate',
    'recommendation','candidate_recommendation','subject'}


def references(records):
    """Assign from each immutable source call order, including unsuccessful calls."""
    result={};owners={}
    for record in records:
        observed=record.get('observation') or {}
        calls={row['call_id']:number for number,row in enumerate(observed.get('managed_calls',[]),1)}
        from . import generic_results
        canonical={generic_results.identity(row):calls[row['call_id']] for row in observed.get('managed_calls',[])}
        for candidate in observed.get('candidates',[]):
            identity=candidate['id']
            if not _MACHINE_CANDIDATE.fullmatch(identity):continue
            if identity in result:continue  # Re-observation retains its original reference.
            if identity not in canonical:raise ValueError('Candidate reference lacks its exact original call')
            ref=f'{record["role"]}{record["step"]:03d}-C{canonical[identity]:03d}'
            if identity in result and result[identity]!=ref or ref in owners and owners[ref]!=identity:
                raise ValueError('Candidate reference is ambiguous')
            result[identity]=ref;owners[ref]=identity
    return result


def for_job(job):
    return (job.get('history') or {}).get('candidate_references',{}) if job.get('worker_view_version')==1 else {}


def public_reference(root, job, identity):
    mapping=for_job(job)
    if identity in mapping:return mapping[identity]
    if job.get('worker_view_version')==1 and isinstance(identity,str) and _MACHINE_CANDIDATE.fullmatch(identity):
        raise ValueError('Candidate has no frozen scientific reference')
    return identity


def public_fields(value, mapping):
    """Project candidate slots in a typed framework view, never arbitrary science."""
    if isinstance(value,list):return [public_fields(item,mapping) for item in value]
    if not isinstance(value,dict):return value
    result={}
    for key,item in value.items():
        if key in _SLOTS and isinstance(item,str):result[key]=mapping.get(item,item)
        elif key=='candidate_ids' and isinstance(item,list):result[key]=[mapping.get(identity,identity) if isinstance(identity,str) else identity for identity in item]
        elif key in {'metrics','scientific_result','text','reported','result'}:result[key]=item
        else:result[key]=public_fields(item,mapping)
    return result


def public_science_fields(value, mapping):
    """Project only declared choice slots in an authored scientific response."""
    result=dict(value)
    chosen=result.get('candidate_recommendation')
    if isinstance(chosen,str):result['candidate_recommendation']=mapping.get(chosen,chosen)
    selected=result.get('implementation_selection')
    if isinstance(selected,list):
        result['implementation_selection']=[mapping.get(item,item) if isinstance(item,str) else item for item in selected]
    table=result.get('candidate_comparison')
    if isinstance(table,dict) and isinstance(table.get('rows'),list):
        rows=[]
        for row in table['rows']:
            if isinstance(row,dict) and isinstance(row.get('candidate_id'),str):
                row=dict(row,candidate_id=mapping.get(row['candidate_id'],row['candidate_id']))
            rows.append(row)
        result['candidate_comparison']=dict(table,rows=rows)
    return result


def resolve_reference(root, job, identity):
    if identity is not None and not isinstance(identity,str):
        raise ValueError('Candidate reference must name one exact scientific object')
    if job.get('worker_view_version')!=1:return identity
    mapping=for_job(job);inverse={ref:canonical for canonical,ref in mapping.items()}
    if len(inverse)!=len(mapping):raise ValueError('Candidate reference is ambiguous')
    if identity in inverse:return inverse[identity]
    if isinstance(identity,str) and _REFERENCE.fullmatch(identity):
        raise ValueError('Candidate reference is outside this frozen scientific task')
    if identity in mapping:raise ValueError('Use the listed scientific candidate reference')
    return identity


def control_payload(job, payload, *, root=None):
    """Resolve only structured author choices; preserve the original return bytes."""
    if job.get('worker_view_version')!=1:return payload
    def resolve(identity):
        try:return resolve_reference(root,job,identity)
        except ValueError:return identity  # Unused scientific advice cannot veto its original.
    value=copy.deepcopy(payload)
    if 'candidate_recommendation' in value:value['candidate_recommendation']=resolve(value['candidate_recommendation'])
    if root is not None and isinstance(value.get('candidate_recommendation'),str) and re.fullmatch(r'[HWAE]\d{3,}-I\d{3,}',value['candidate_recommendation']):
        from . import history
        matches={row['candidate_id'] for row in history.candidate_materials(root,job)
            if row['implementation_id']==value['candidate_recommendation']}
        if len(matches)==1:value['candidate_recommendation']=matches.pop()
    return value
