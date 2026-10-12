"""Optional cov CLI observer/wrapper. Never imports models or hidden scoring data."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time
import uuid
import fcntl

MAX_BYTES = 256_000
MAX_ASSET = 32 * 1024 * 1024
MAX_SCAN = 4 * 1024 * 1024
MAX_CALLS = 128


class IntegrityError(ValueError):
    pass


def _bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()


def _read(path, limit=MAX_BYTES):
    path = Path(path)
    if path.resolve() != path or not path.is_file() or path.stat().st_size > limit:
        raise IntegrityError('Exact bounded original required')
    return path.read_bytes()


def _write(path, value):
    data = _bytes(value)
    if len(data) > MAX_BYTES:raise ValueError('Call record capacity exceeded')
    with Path(path).open('xb') as stream:
        stream.write(data);stream.flush();os.fsync(stream.fileno())


def _proof(path, limit=MAX_ASSET):
    data = _read(path, limit)
    return dict(path=str(path), sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data))


def _check(proof):
    actual = _proof(Path(proof['path']))
    if actual != proof:raise IntegrityError('Original call proof changed')
    return Path(proof['path'])


def _rows(path):
    data = _read(path, MAX_SCAN) if Path(path).exists() else b''
    rows = [json.loads(line) for line in data.splitlines() if line.strip()]
    ids = [row['run_id'] for row in rows]
    if any(type(i) is not int or i < 1 for i in ids) or len(set(ids)) != len(ids):
        raise IntegrityError('Public ledger run identities are ambiguous')
    return rows


def _config(path):
    data = _read(path);value = json.loads(data)
    keys = {'contract_version','record_dir','runs_root','run_argv','scope','parents','evaluation_key'}
    if set(value) != keys or value['contract_version'] != 2:
        raise ValueError('Explicit wrapper contract2 configuration required')
    scope = value['scope']
    if set(scope) != {'step','role','job_sha256','execution_key','mechanism_ref'} or type(scope['step']) is not int or scope['step'] <= 0 or scope['role'] not in {'H','W','A','E'}:
        raise ValueError('Exact frozen scientific execution scope required')
    for key in ('job_sha256','execution_key'):
        if not isinstance(scope[key],str) or len(scope[key]) != 64:raise ValueError('Execution digest required')
    if not isinstance(value['parents'],list) or len(value['parents']) > 4096:
        raise ValueError('Bounded frozen parents required')
    for key in ('record_dir','runs_root'):
        p = Path(value[key])
        if not p.is_absolute() or p.resolve() != p:raise ValueError('Original namespace directories required')
    if not isinstance(value['run_argv'],list) or not value['run_argv'] or not Path(value['run_argv'][0]).is_absolute():
        raise ValueError('Exact run executable required')
    return value, hashlib.sha256(data).hexdigest()


def _completed(directory):
    accepted = json.loads(_read(directory/'accepted.json'))
    path = directory/'completed.json'
    if not path.exists():return None
    result = json.loads(_read(path))
    if result['call_id'] != accepted['call_id'] or result['scope'] != accepted['scope'] or result['parent'] != accepted['parent'] or result['change_intent'] != accepted['change_intent']:
        raise IntegrityError('Completion differs from accepted scientific context')
    for proof in result['proofs']:_check(proof)
    if result['model'] is not None:_check(result['model'])
    if result['status'] in {'known_success','known_failed'}:
        # Canonical completion comes only from the immutable same-call transport.
        row=json.loads(_read(directory/'row.json'))
        stdout=json.loads(_read(directory/'stdout.raw'))
        terminal=json.loads(_read(directory/'terminal.json'))
        ok=result['status']=='known_success'
        if (row!=stdout or row.get('script')!=accepted['source_script']
                or type(row.get('run_id')) is not int or row['run_id']<1
                or result['run_id']!=row['run_id'] or result['candidate_id']!=f'run-{row["run_id"]}'
                or row.get('ok') is not ok or terminal.get('returncode')!=(0 if ok else 1)
                or terminal.get('cleanup_confirmed') is not True or terminal.get('transport_complete') is not True
                or (result['model'] is not None)!=ok
                or (ok and row.get('model_path')!=str(Path(accepted['runs_root'])/f'model_run{row["run_id"]}.pkl'))):
            raise IntegrityError('Completion differs from immutable same-call transport')
        if ok and (result['model']!=_proof(directory/'model.pkl') or result['model'] not in result['proofs']):
            raise IntegrityError('Completed model differs from this exact call original')
        required={str(directory/name) for name in ('accepted.json','source.py','stdout.raw','row.json','terminal.json')}
        if not required.issubset({proof['path'] for proof in result['proofs']}):
            raise IntegrityError('Completion lacks original transport proofs')
    elif result['status']!='unknown' or any(result[key] is not None for key in ('candidate_id','run_id','model')):
        raise IntegrityError('Unknown completion acquired an experiment identity')
    return result


def _calls(config):
    root = Path(config['record_dir'])/'calls'
    paths = sorted(root.iterdir()) if root.exists() else []
    if len(paths) > MAX_CALLS:raise ValueError('Call observation capacity exceeded')
    for path in paths:
        if path.resolve() != path or not path.is_dir():raise IntegrityError('Call directory changed')
    return paths


def _parent(config, name, new):
    if new:return dict(status='declared_root',candidate_id=None,source='none'),None
    if name is None:return dict(status='unknown',candidate_id=None,source='none'),None
    options = [(row['name'],row['candidate_id'],row['model'],'sealed',row['binding']) for row in config['parents']]
    for path in _calls(config):
        result = _completed(path)
        if result and result['status'] == 'known_success':
            options.append((result['candidate_id'],result['candidate_id'],result['model'],'same_node_completed_call',_binding(result,_proof(path/'completed.json'))))
    matches = [row for row in options if row[0] == name]
    if len(matches) != 1:raise ValueError('parent_plan_unresolved')
    _, candidate, model, source, binding = matches[0]
    _check(model)
    return dict(status='declared',candidate_id=candidate,source=source),binding


def _binding(context, completion):
    model=context['model']
    return dict(call_id=context['call_id'],step=context['scope']['step'],completion_sha256=completion['sha256'],
                model_sha256=model['sha256'],model_size_bytes=model['size_bytes'])


def _receipt(directory, accepted, rows, returncode, cleanup, transport_complete=True):
    if not transport_complete:return None
    try:
        raw = _read(directory/'stdout.raw')
        row = json.loads(raw)
    except (OSError,ValueError):return None
    if not isinstance(row,dict) or type(row.get('run_id')) is not int or row.get('script') != accepted['source_script']:
        return None
    matches = [item for item in rows if item.get('run_id') == row['run_id']]
    if len(matches) != 1 or matches[0] != row:return None
    if not cleanup or returncode not in (0,1) or row.get('ok') is not (returncode == 0):return None
    _check(accepted['script'])
    if _proof(Path(accepted['source_script']))['sha256'] != accepted['script']['sha256']:
        raise IntegrityError('Executed source changed')
    model = None
    if row['ok']:
        path = Path(row.get('model_path',''))
        if path != Path(accepted['runs_root'])/f'model_run{row["run_id"]}.pkl':
            raise IntegrityError('Returned artifact is outside the public run scope')
        data = _read(path,MAX_ASSET);archive = directory/'model.pkl'
        if not archive.exists():archive.write_bytes(data);archive.chmod(0o400)
        model = _proof(archive)
        if model['sha256'] != hashlib.sha256(data).hexdigest():raise IntegrityError('Retained model changed')
    if not (directory/'row.json').exists():_write(directory/'row.json',row)
    proofs = [_proof(directory/name) for name in ('accepted.json','source.py','stdout.raw','row.json','terminal.json')]
    if model:proofs.append(model)
    return dict(call_id=accepted['call_id'],status='known_success' if row['ok'] else 'known_failed',
        candidate_id=f'run-{row["run_id"]}',run_id=row['run_id'],model=model,parent=accepted['parent'],
        change_intent=accepted['change_intent'],note='Exact same-call public receipt; not audit qualification',
        scope=accepted['scope'],proofs=proofs)


def status(config):
    results = []
    for directory in _calls(config):
        result = _completed(directory)
        if result is None:
            accepted = json.loads(_read(directory/'accepted.json'))
            if result is None:
                result = dict(call_id=accepted['call_id'],status='unknown',candidate_id=None,run_id=None,model=None,
                    parent=accepted['parent'],change_intent=accepted['change_intent'],scope=accepted['scope'],proofs=[],note='Accepted original has no verified completion; never replay')
        results.append(result)
    return results


def run(config, config_sha, script, parent=None, new=False, change=None):
    from scidiscovery.research_loop import runtime
    root = Path(config['record_dir']);root.mkdir(parents=True,exist_ok=True)
    fd = os.open(root/'node.lock',os.O_CREAT|os.O_RDWR|os.O_CLOEXEC|os.O_NOFOLLOW,0o600)
    try:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return dict(status='unknown',note='Existing node call still owns execution')
        if any(item['status']=='unknown' for item in status(config)):
            return dict(status='unknown',note='Preserve accepted call; query lineage-status instead of replay')
        selected,parent_binding = _parent(config,parent,new)
        script = Path(script).resolve();data = _read(script,MAX_ASSET)
        if len(_calls(config)) >= MAX_CALLS:raise ValueError('Call capacity exceeded')
        directory = root/'calls'/f'{len(_calls(config))+1:04d}-{uuid.uuid4().hex}';directory.mkdir(parents=True)
        (directory/'source.py').write_bytes(data);(directory/'source.py').chmod(0o400)
        accepted = dict(call_id=directory.name,scope=config['scope'],parent=selected,parent_binding=parent_binding,change_intent=change,
                        source_script=str(script),script=_proof(directory/'source.py'),runs_root=config['runs_root'],config_sha256=config_sha)
        _write(directory/'accepted.json',accepted)
        runtime._subreaper()
        process = None;cleanup = False;returncode = None;transport_complete = True
        with (directory/'stdout.raw').open('xb') as out,(directory/'stderr.raw').open('xb') as err:
            process = subprocess.Popen([*config['run_argv'],'run','--script',str(script)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
            identity = runtime.process_identity(process.pid,hashlib.sha256(_bytes(accepted)).hexdigest())
            _write(directory/'process.json',identity)
            deadline = time.monotonic()+int(os.environ.get('EXP_WALL_CAP_S','60'))+5
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout,selectors.EVENT_READ)
                selector.register(process.stderr,selectors.EVENT_READ)
                count = 0
                while selector.get_map() or process.poll() is None:
                    for key,_ in selector.select(.1):
                        chunk = os.read(key.fileobj.fileno(),65536)
                        if not chunk:selector.unregister(key.fileobj);continue
                        count += len(chunk)
                        if count > MAX_BYTES:
                            transport_complete = False
                            break
                        sink = out if key.fileobj is process.stdout else err
                        sink.write(chunk);sink.flush()
                    if count > MAX_BYTES or time.monotonic() >= deadline:
                        transport_complete = False
                        if runtime.process_matches(identity,identity['task_sha256']):os.killpg(identity['pgid'],signal.SIGTERM)
                        break
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if runtime.process_matches(identity,identity['task_sha256']):os.killpg(identity['pgid'],signal.SIGKILL)
                process.wait(timeout=5)
            cleanup = runtime.cleanup_owned_group(identity)=='observed_group_cleaned'
            returncode = process.returncode
            process.stdout.close();process.stderr.close()
        _write(directory/'terminal.json',dict(returncode=returncode,cleanup_confirmed=cleanup,transport_complete=transport_complete))
        result = _receipt(directory,accepted,_rows(Path(config['runs_root'])/'results.jsonl'),returncode,cleanup,transport_complete=transport_complete)
        if result is None:
            result = dict(call_id=accepted['call_id'],status='unknown',candidate_id=None,run_id=None,model=None,
                parent=selected,change_intent=change,scope=config['scope'],proofs=[_proof(directory/name) for name in ('accepted.json','source.py','stdout.raw','terminal.json')],
                note='No exact completed public receipt; preserve without replay')
        _write(directory/'completed.json',result)
        return result
    finally:os.close(fd)


def observe(request):
    config = request['config'];root = Path(request['root'])
    if set(config) != {'runs','calls','evaluation_key'}:raise ValueError('Explicit public run/call roots required')
    for key in ('runs','calls'):
        path = Path(config[key])
        if path.is_absolute() or '..' in path.parts or (root/path).resolve() != root/path:raise IntegrityError('Observer escaped original instance')
    rows = _rows(root/config['runs']/'results.jsonl');known=set(request.get('known_candidates',[]))
    contexts=[]
    for directory in sorted((root/config['calls']).glob('*/work/lineage/calls/*')):
        result = _completed(directory)
        if result is not None:
            result['proofs'].append(_proof(directory/'completed.json'))
        if result is None:
            accepted=json.loads(_read(directory/'accepted.json'))
            result=dict(call_id=accepted['call_id'],scope=accepted['scope'],status='unknown',candidate_id=None,run_id=None,model=None,
                parent=accepted['parent'],change_intent=accepted['change_intent'],proofs=[_proof(directory/'accepted.json')],note='Accepted original without exact completion')
        if result['scope']['step'] != request['step']:continue
        if result and result['call_id'] not in set(request.get('known_contexts',[])):
            # _completed checks immutable proofs; relative names let core archive once.
            for proof in result['proofs']:proof['path']=str(Path(proof['path']).relative_to(root))
            if result['model']:result['model']['path']=str(Path(result['model']['path']).relative_to(root))
            contexts.append(result)
    if len(contexts)>MAX_CALLS:raise ValueError('Observer new context capacity exceeded')
    candidates=[];partial=False
    for row in rows:
        cid=f'run-{row["run_id"]}'
        if cid in known:continue
        if len(candidates)>=MAX_CALLS:partial=True;break
        candidates.append(dict(id=cid,label=f'Public experiment {row["run_id"]}',implementation=None,evaluation_key=config['evaluation_key'],
            metric=row.get('val_score'),direction='max',status='ok' if row.get('ok') is True else 'failed',evidence=[str(Path(config['runs'])/'results.jsonl')]))
    bound={item['candidate_id'] for item in contexts if item['candidate_id']}
    partial=partial or any(row['id'] not in bound for row in candidates) or any(item['status']=='unknown' for item in contexts)
    return dict(candidates=candidates,current_candidate=None,actual_submission=None,contexts=contexts,
        coverage=dict(status='partial' if partial else 'complete',note='Managed declared relations only; ordinary shell/parallel or unknown calls remain uncovered'))



def configure(root, step, run_argv, runs_root, output):
    """Trusted launcher's host-side preparation, before entering its namespace."""
    from scidiscovery.research_loop import contracts as c, execution, lineage
    root=Path(root).resolve();job=c.read(c.regular(root/'jobs'/f'{step:03d}.json'))
    c._validate_inputs(root,c.workspace(root,step),job)
    record=execution.record(root,step)
    if c.read(c.regular(record/'native-intent.json')).get('task_sha256')!=c.digest(root/'jobs'/f'{step:03d}.json'):
        raise IntegrityError('Launcher preparation has no accepted scientific task')
    parents=[]
    for candidate,item in lineage.build(root,step)['candidates'].items():
        context=item.get('context');model=context.get('model') if context else None
        if context and context['status']=='known_success' and model and model.get('retention')=='archived':
            # The qualified namespace retains the original public runs alias.
            path=Path(runs_root)/f'model_run{context["run_id"]}.pkl'
            completion=next((p for p in context['proofs'] if Path(p['path']).name=='completed.json'),None)
            if completion is None:continue
            parents.append(dict(name=candidate,candidate_id=candidate,model=dict(path=str(path),sha256=model['sha256'],size_bytes=model['size_bytes']),
                                binding=_binding(context,completion)))
    value=dict(contract_version=2,record_dir=str(c.workspace(root,step)/'work/lineage'),runs_root=str(runs_root),run_argv=run_argv,
        scope=dict(step=step,role=job['role'],job_sha256=c.digest(root/'jobs'/f'{step:03d}.json'),execution_key=execution.identity(root,step),
                   mechanism_ref=((job.get('search') or {}).get('focus') or {}).get('mechanism_ref')),
        parents=parents,evaluation_key='covshift-public-val-v1')
    _write(Path(output),value);Path(output).chmod(0o400)
    return dict(status='configured',config=str(output))

def main(argv=None):
    if argv is None and len(sys.argv)==1:
        try:print(json.dumps(observe(json.loads(sys.stdin.buffer.read(MAX_BYTES+1))),allow_nan=False))
        except IntegrityError as error:print(json.dumps(dict(integrity_error=str(error))))
        return 0
    if argv is None and len(sys.argv)>1 and sys.argv[1]=='configure':
        p=argparse.ArgumentParser();p.add_argument('command');p.add_argument('--root',type=Path,required=True);p.add_argument('--step',type=int,required=True)
        p.add_argument('--run-argv-json',required=True);p.add_argument('--runs-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
        print(json.dumps(configure(a.root,a.step,json.loads(a.run_argv_json),a.runs_root,a.output)));return 0
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True)
    sub=parser.add_subparsers(dest='command',required=True);r=sub.add_parser('run');r.add_argument('--script',type=Path,required=True)
    group=r.add_mutually_exclusive_group();group.add_argument('--parent-plan');group.add_argument('--new-plan',action='store_true')
    r.add_argument('--change-intent');sub.add_parser('lineage-status');args=parser.parse_args(argv)
    try:
        config,digest=_config(args.config)
        if args.command=='lineage-status':result=dict(calls=status(config));code=0
        else:
            result=run(config,digest,args.script,args.parent_plan,args.new_plan,args.change_intent)
            code={'known_success':0,'known_failed':1,'unknown':2}.get(result['status'],2)
    except IntegrityError as error:result=dict(status='integrity_error',note=str(error));code=3
    except ValueError as error:result=dict(status='unresolved',note=str(error));code=2
    if args.command=='run' and 'scope' in result:
        result={key:result[key] for key in ('call_id','status','candidate_id','run_id','parent','change_intent','note')} | {'model':{'retained':True} if result['model'] else None}
    elif args.command=='lineage-status' and 'calls' in result:
        result={'calls':[{key:item[key] for key in ('call_id','status','candidate_id','run_id','parent','change_intent','note')} for item in result['calls']]}
    print(json.dumps(result,allow_nan=False));return code


if __name__=='__main__':raise SystemExit(main())
