"""Append terminal evidence for a sealed unknown call; never rewrite its science."""
import copy
import hashlib
from pathlib import Path

from . import contracts as c, execution, experiments as e, history

DIRECTORY = 'host-history/execution-recoveries'


def prefix(root,step):
    path=Path(root)/'jobs'/f'{step:03d}.json'
    if path.exists():return c.read(c.regular(path)).get('history',{}).get('execution_recoveries',[])
    paths=sorted((Path(root)/DIRECTORY).glob('*/*.json'))
    if len(paths)>128:raise ValueError('Execution recovery prefix capacity exceeded')
    return [dict(path=path.relative_to(root).as_posix(),sha256=c.digest(c.regular(path))) for path in paths]


def validate(root,refs):
    if not isinstance(refs,list) or len(refs)>128:raise ValueError('Execution recovery prefix capacity exceeded')
    values=[];seen=set()
    for ref in refs:
        if set(ref)!={'path','sha256'}:raise ValueError('Execution recovery prefix is malformed')
        path=Path(root)/ref['path']
        if (path.resolve()!=path or not path.is_relative_to(Path(root)/DIRECTORY)
                or c.digest(c.regular(path,limit=history.MAX_OBSERVER_BYTES))!=ref['sha256']):
            raise history.ObserverIntegrityError('Frozen execution recovery original changed')
        value=c.read(path);step=value['source_step'];call=value['row']['call_id'];key=(step,call)
        if key in seen or path!=Path(root)/DIRECTORY/f'{step:03d}'/(call+'.json'):
            raise history.ObserverIntegrityError('Execution recovery identity is ambiguous')
        seen.add(key)
        job,_,seal,sha=history._source(root,step)
        if sha!=value['seal_sha256'] or not seal.get('observations'):
            raise history.ObserverIntegrityError('Execution recovery source seal changed')
        old=c.read(Path(root)/seal['observations']['path'])
        matches=[row for row in old.get('managed_calls',[]) if row['call_id']==call]
        if len(matches)!=1 or matches[0]['status']!='unknown' or hashlib.sha256(e.encoded(matches[0])).hexdigest()!=value['old_row_sha256']:
            raise history.ObserverIntegrityError('Execution recovery has no exact sealed unknown origin')
        row=value['row']
        if (row['accepted']!=matches[0]['accepted'] or row['scope']!=matches[0]['scope']
                or row.get('mechanism_binding')!=matches[0].get('mechanism_binding')
                or row['status'] not in {'known_success','known_failed'}):
            raise history.ObserverIntegrityError('Execution recovery changed original reservation')
        history.validate_managed(root,job,[row]);values.append(value)
    return values


def resolved(root,refs):
    return {(value['source_step'],value['row']['call_id']):value['row'] for value in validate(root,refs)}


def create(root,step):
    job,_,seal,sha=history._source(root,step)
    if job['role']!='W' or not seal.get('observations'):raise ValueError('Recovery requires an exact sealed W observation')
    old=c.read(root/seal['observations']['path']);created=[];unresolved=[]
    for row in old.get('managed_calls',[]):
        if row['status']!='unknown':continue
        path=root/DIRECTORY/f'{step:03d}'/(row['call_id']+'.json')
        if path.exists():
            ref=dict(path=path.relative_to(root).as_posix(),sha256=c.digest(path));validate(root,[ref]);created.append(ref);continue
        accepted=c.read(root/row['accepted']['snapshot'])
        from . import managed_wait
        _,config=managed_wait._config(root,job,accepted)
        directory=e.Records(config).directory(row['call_id'])
        if not (directory/'execution-observation.json').exists():
            if not config['execution_interface']['capabilities']['query']:
                unresolved.append(row['call_id']);continue
            if e.record_observation(config,e.load(config),row['call_id']) is None:
                unresolved.append(row['call_id']);continue
        current=[item for item in history.managed_calls(root,job) if item['call_id']==row['call_id']]
        if len(current)!=1 or current[0]['status']=='unknown':raise ValueError('Original recovery terminal is unverified')
        value=dict(source_step=step,seal_sha256=sha,old_row_sha256=hashlib.sha256(e.encoded(row)).hexdigest(),row=current[0])
        c.write(path,value);path.chmod(0o400)
        ref=dict(path=path.relative_to(root).as_posix(),sha256=c.digest(path));validate(root,[ref]);created.append(ref)
    return dict(status='execution_recovered' if created and not unresolved else 'execution_recovery_pending',
        recovered=len(created),unresolved=len(unresolved),qualification='Terminal evidence only; old scientific conclusions and reservation counts are unchanged.')


def project_records(root,records,refs):
    known=resolved(root,refs)
    result=copy.deepcopy(records)
    for record in result:
        observed=record.get('observation') or {};recovered=[]
        for index,row in enumerate(observed.get('managed_calls',[])):
            current=known.get((record['step'],row['call_id']))
            if current is not None:
                observed['managed_calls'][index]=current;recovered.append(row['call_id'])
        record['recovered_calls']=recovered
    return result
