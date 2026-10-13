"""Registered scientific execution; one owner of the original call receipts.

No model execution, domain parser, subprocess launch or Artifact service lives here.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict
from functools import lru_cache
import fcntl
import hashlib
import importlib.metadata
import inspect
import json
import os
from pathlib import Path
import re
import sys
import time
import uuid

from scidiscovery.operations.execution import (ExecutionInterfaceRegistration,
    LifecycleCapabilities, LocalFileDescriptor, MANAGED_METHODS, lifecycle_capabilities)
from scidiscovery.operations.runtime_plugins import RuntimePluginContext, RuntimePluginContribution

GROUP = 'scidiscovery.execution_interfaces'
VERSION = 1
MAX_BYTES = 256_000
MAX_ASSET = 32 * 1024 * 1024
MAX_CALLS = 128
ID = re.compile(r'[A-Za-z0-9._-]{1,128}\Z')


class IntegrityError(ValueError):
    pass


class UnsupportedExecution(ValueError):
    pass


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n').encode()


def read(path, limit=MAX_BYTES):
    path = Path(path)
    if path.resolve() != path or not path.is_file() or path.stat().st_size > limit:
        raise IntegrityError('Exact bounded execution original required')
    return path.read_bytes()


def proof(path, limit=MAX_ASSET):
    data = read(path, limit)
    return dict(path=str(path), sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data))


def write(path, value):
    data = encoded(value)
    if len(data) > MAX_BYTES:
        raise ValueError('Execution record capacity exceeded')
    with Path(path).open('xb') as stream:
        stream.write(data);stream.flush();os.fsync(stream.fileno())


@lru_cache(maxsize=32)
def registration(executor):
    plugin, separator, binding = executor.partition(':')
    if not separator or not ID.fullmatch(plugin) or not ID.fullmatch(binding):
        raise ValueError('Exact registered executor key required')
    matches = list(importlib.metadata.entry_points().select(group=GROUP, name=plugin))
    if len(matches) != 1:
        raise UnsupportedExecution('Registered execution implementation unavailable')
    value = matches[0].load()
    if not isinstance(value, ExecutionInterfaceRegistration) or value.plugin_id != plugin:
        raise ValueError('Execution registration identity differs from its entry point')
    return value, binding


def _adapter(config, path):
    selected = config['execution_interface']
    declared, binding = registration(selected['executor'])
    body = {key: value for key, value in config.items() if key != 'execution_interface'}
    contribution = declared.factory.build(RuntimePluginContext(declared.plugin_id, 'local_worker',
        Path(path), encoded(body), Path(config['record_dir'])))
    if not isinstance(contribution, RuntimePluginContribution) or binding not in contribution.execution_adapters:
        raise UnsupportedExecution('Registered execution binding unavailable')
    adapter = contribution.execution_adapters[binding]
    if any(not callable(getattr(adapter,name,None)) for name in MANAGED_METHODS):
        raise UnsupportedExecution('Implementation does not provide the managed execution interface')
    return declared, adapter, body


def freeze(config, executor, *, path=None):
    """Host preparation only: freeze selected factory, code, configuration and flags."""
    value = dict(config)
    scope=value.get('scope')
    if (not isinstance(scope,dict) or set(scope)!={'step','role','job_sha256','execution_key','mechanism_ref'}
            or type(scope.get('step')) is not int or scope['step']<=0 or scope['role'] not in {'H','W','A','E'}
            or any(not isinstance(scope.get(key),str) or not re.fullmatch('[0-9a-f]{64}',scope[key])
                   for key in ('job_sha256','execution_key'))):
        raise IntegrityError('Exact host-bound scientific execution scope required')
    value.setdefault('max_seconds',65)
    if type(value['max_seconds']) not in (int,float) or not 0<value['max_seconds']<float('inf'):
        raise ValueError('Finite frozen execution time limit required')
    value['execution_interface'] = dict(executor=executor)
    declared, adapter, body = _adapter(value, path or Path(config['record_dir']).parent / 'config.json')
    assets = [Path(inspect.getfile(declared.factory.build)).resolve(),
              Path(inspect.getfile(type(adapter))).resolve(), Path(__file__).resolve()]
    assets += [Path(item).resolve() for item in adapter.code_assets()]
    value['execution_interface'] = dict(version=VERSION, executor=executor, plugin_version=declared.version,
        config_sha256=hashlib.sha256(encoded(body)).hexdigest(),
        capabilities=asdict(lifecycle_capabilities(adapter)),
        code=[proof(item) for item in dict.fromkeys(assets)])
    return value


def configure(root,step,executor,config,output):
    """Freeze a host-bound interface before the Worker enters its existing namespace."""
    from . import contracts as c, execution
    root=Path(root).resolve();job=c.read(c.regular(root/'jobs'/f'{step:03d}.json'))
    versions=(c.settings(root).get('experiment_interface_version'),job.get('experiment_interface_version'))
    if any(type(value) is not int or value!=VERSION for value in versions):
        raise UnsupportedExecution('Preserved scientific instance is read-only; prepare a new registered instance')
    c._validate_inputs(root,c.workspace(root,step),job)
    record=execution.record(root,step)
    if c.read(c.regular(record/'native-intent.json')).get('task_sha256')!=c.digest(root/'jobs'/f'{step:03d}.json'):
        raise IntegrityError('Host configuration has no exact accepted scientific task')
    value=dict(config,record_dir=str(c.workspace(root,step)/'work/lineage'),
        scope=dict(step=step,role=job['role'],job_sha256=c.digest(root/'jobs'/f'{step:03d}.json'),
            execution_key=execution.identity(root,step),mechanism_ref=((job.get('search') or {}).get('focus') or {}).get('mechanism_ref')))
    value=freeze(value,executor,path=output)
    for path in (Path(output),record/'experiment-config.json'):
        if path.exists():
            if c.read(c.regular(path))!=value:raise IntegrityError('Frozen experiment configuration changed')
        else:c.write(path,value);path.chmod(0o400)
    return value


def load(config, *, path=None):
    if not isinstance(config,dict):
        raise IntegrityError('Frozen execution configuration is malformed')
    selected = config.get('execution_interface')
    if not isinstance(selected, dict) or type(selected.get('version')) is not int or selected['version'] != VERSION:
        raise UnsupportedExecution('Preserved execution configuration is read-only; prepare a new registered instance')
    if freeze({key: value for key, value in config.items() if key != 'execution_interface'}, selected['executor'], path=path) != config:
        raise IntegrityError('Frozen execution implementation or configuration changed')
    _, adapter, _ = _adapter(config, path or Path(config['record_dir']).parent / 'config.json')
    return adapter


class Records:
    """One canonical accepted/process/terminal/completed owner, shared by drivers."""
    def __init__(self, config):
        self.config = config
        self.root = Path(config['record_dir'])
        if self.root.resolve() != self.root:
            raise IntegrityError('Execution record namespace changed')

    def calls(self):
        root = self.root / 'calls'
        if root.resolve() != root:
            raise IntegrityError('Execution call namespace changed')
        paths = sorted(root.iterdir()) if root.exists() else []
        if len(paths) > MAX_CALLS:
            raise ValueError('Execution call capacity exceeded')
        if any(path.resolve() != path or not path.is_dir() for path in paths):
            raise IntegrityError('Execution call directory changed')
        return paths

    def directory(self, call_id):
        if not isinstance(call_id, str) or not ID.fullmatch(call_id):
            raise ValueError('Exact original execution identity required')
        path = self.root / 'calls' / call_id
        if path.resolve() != path or not path.is_dir():
            raise IntegrityError('Original execution call unavailable')
        return path

    @contextmanager
    def lease(self, name='node.lock'):
        self.root.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.root / name, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            os.close(fd)

    def accept(self, descriptor, metadata, interface):
        """Short admission linearization point. No solver or domain IO under lock."""
        data = read(descriptor.local_path, MAX_ASSET)
        if hashlib.sha256(data).hexdigest() != descriptor.sha256 or len(data) != descriptor.size_bytes:
            raise IntegrityError('Prepared execution input changed')
        if len(self.calls()) >= MAX_CALLS:
            raise ValueError('Execution call capacity exceeded')
        directory = self.root / 'calls' / descriptor.name
        directory.mkdir(parents=True)
        source = directory / 'source.py'
        source.write_bytes(data);source.chmod(0o400)
        accepted = dict(metadata, call_id=descriptor.name, scope=self.config['scope'],
            source_script=descriptor.local_path, script=proof(source),
            prepared=descriptor.model_dump(mode='json'), interface=interface)
        with self.lease('accept.lock'):
            write(directory / 'accepted.json', accepted)
        return accepted

    def publish(self, call_id, filename, value):
        if filename not in {'process.json', 'terminal.json', 'completed.json','submission.json','collected.json'}:
            raise ValueError('Unknown execution receipt')
        directory = self.directory(call_id)
        accepted = json.loads(read(directory / 'accepted.json'))
        if accepted['scope'] != self.config['scope'] or accepted['call_id'] != call_id:
            raise IntegrityError('Execution receipt escaped its accepted scope')
        write(directory / filename, value)

    def accepted(self,call_id):
        value=json.loads(read(self.directory(call_id)/'accepted.json'))
        if (not isinstance(value,dict) or value.get('call_id')!=call_id
                or not isinstance(value.get('scope'),dict) or type(value['scope'].get('step')) is not int
                or value['scope']!=self.config['scope']):
            raise IntegrityError('Accepted execution binding changed')
        parent=value.get('parent')
        if not isinstance(parent,dict) or 'candidate_id' not in parent:
            raise IntegrityError('Published execution parent is malformed')
        candidate=parent['candidate_id']
        if candidate is not None and (not isinstance(candidate,str) or not 0<len(candidate.encode())<=80):
            raise IntegrityError('Published execution parent is malformed')
        return value

    def bind_external(self,call_id,external_id,state):
        if not isinstance(external_id,str) or not ID.fullmatch(external_id):
            raise IntegrityError('Submitted external execution identity is invalid')
        value=dict(call_id=call_id,external_run_id=external_id,scope=self.config['scope'])
        path=self.directory(call_id)/'submission.json'
        if path.exists():
            if json.loads(read(path))!=value:raise IntegrityError('Original external execution identity changed')
        else:self.publish(call_id,'submission.json',value)
        return external_id,state

    def external(self,call_id):
        self.accepted(call_id)
        path=self.directory(call_id)/'submission.json'
        if not path.exists():return None
        value=json.loads(read(path))
        if value.get('call_id')!=call_id or value.get('scope')!=self.config['scope']:
            raise IntegrityError('External execution binding changed')
        return value['external_run_id']

    def state(self,call_id):
        """Canonical completion only; process observation belongs to an implementation."""
        self.accepted(call_id)
        path=self.directory(call_id)/'completed.json'
        if not path.exists():return 'unknown'
        completed=json.loads(read(path))
        if not isinstance(completed,dict) or completed.get('call_id')!=call_id or completed.get('scope')!=self.config['scope']:
            raise IntegrityError('Completed execution binding changed')
        return {'known_success':'succeeded','known_failed':'failed','unknown':'unknown'}.get(completed.get('status'),'unknown')


def dispatch(config, script, *, parent=None, new=False, change=None):
    """Convenience input path; neutral callers may provide a descriptor directly."""
    source=Path(script).resolve();item=proof(source)
    payload=LocalFileDescriptor(name='input',local_path=str(source),sha256=item['sha256'],
        size_bytes=item['size_bytes'],media_type='application/octet-stream')
    return dispatch_descriptor(config,payload,parent=parent,new=new,change=change)


def dispatch_descriptor(config, payload, *, parent=None, new=False, change=None):
    try:return _dispatch_descriptor(config,payload,parent=parent,new=new,change=change)
    except BlockingIOError:return dict(status='unknown',note='Original accepted execution still owns its lease')


def _dispatch_descriptor(config, payload, *, parent=None, new=False, change=None):
    adapter = load(config)
    capabilities = lifecycle_capabilities(adapter)
    if not capabilities.atomic_admission:
        raise UnsupportedExecution('Implementation does not support managed admission')
    records = Records(config)
    with records.lease():
        for path in records.calls():
            details=adapter.status_details(path.name)
            if details['state'] in {'unknown', 'running','accepted','submitted'}:
                return dict(status='unknown', note='Preserve original execution; query its identity instead of replay')
        call_id = f'{len(records.calls())+1:04d}-{uuid.uuid4().hex}'
        descriptor = payload.model_copy(update={'name':call_id})
        prepared = adapter.prepare(descriptor, preparation_profile='research_loop.v1', exchange_directory=records.root)
        metadata = adapter.acceptance_metadata(prepared, parent=parent, new=new, change=change)
        accepted = records.accept(prepared, metadata, config['execution_interface'])
        adapter.dispatch_lease(accepted)
        external_id,state=adapter.submit(prepared)
        records.bind_external(call_id,external_id,state)
        return adapter.result(call_id)


def progress(config):
    adapter = load(config)
    if not lifecycle_capabilities(adapter).query:
        raise UnsupportedExecution('Execution query unavailable')
    rows = []
    counts = dict.fromkeys(('accepted', 'running', 'known_success', 'known_failed', 'unknown'), 0)
    for path in Records(config).calls():
        try:
            details = adapter.status_details(path.name)
        except (FileNotFoundError,json.JSONDecodeError,UnicodeDecodeError):
            details=dict(state='unknown')
        except IntegrityError:
            raise
        except (OSError,KeyError,TypeError,AttributeError,RecursionError) as error:
            raise IntegrityError('Published execution metadata is malformed or unavailable') from error
        state = {'succeeded':'known_success', 'failed':'known_failed'}.get(details['state'], details['state'])
        if state not in counts:
            state = 'unknown'
        counts[state] += 1
        rows.append(dict(call_id=path.name, status=state, candidate_id=details.get('candidate_id'),
            evaluation_key=details.get('evaluation_key'), metric=details.get('metric'), direction=details.get('direction'),
            wall_seconds=details.get('wall_seconds'), parent_candidate=details.get('parent_candidate')))
    return dict(version=1, calls=rows[-16:], counts=counts, omitted_count=max(0, len(rows)-16),
        coverage='partial' if counts['unknown'] else 'complete', observed_at=time.time())


def main(argv=None):
    from . import feedback
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True)
    sub=parser.add_subparsers(dest='command',required=True)
    run=sub.add_parser('run');payload=run.add_mutually_exclusive_group(required=True)
    payload.add_argument('--script',type=Path);payload.add_argument('--payload',type=Path)
    choice=run.add_mutually_exclusive_group();choice.add_argument('--parent-plan');choice.add_argument('--new-plan',action='store_true')
    run.add_argument('--change-intent');sub.add_parser('lineage-status')
    for name in ('query','lookup','collect','cancel'):
        item=sub.add_parser(name);item.add_argument('--call-id',required=True)
    args=parser.parse_args(argv)
    try:
        config=json.loads(read(args.config));adapter=load(config,path=args.config)
        if args.command=='run':
            result=dispatch(config,args.script or args.payload,parent=args.parent_plan,new=args.new_plan,change=args.change_intent)
            result=adapter.public_result(result)
            code={'known_success':0,'known_failed':1}.get(result['status'],2)
        elif args.command=='lineage-status':result=progress(config);code=0
        else:
            capability='lookup_submission' if args.command=='lookup' else 'query' if args.command=='query' else args.command
            if not getattr(lifecycle_capabilities(adapter),capability):
                raise UnsupportedExecution('Requested original execution operation unavailable')
            if args.command=='query':result=adapter.status_details(args.call_id)
            elif args.command=='lookup':
                records=Records(config);accepted=records.accepted(args.call_id)
                descriptor=LocalFileDescriptor.model_validate(accepted['prepared'])
                found=adapter.lookup_submission(descriptor)
                if found is None:result=dict(state='unknown',call_id=args.call_id)
                else:
                    records.bind_external(args.call_id,*found)
                    result=adapter.status_details(args.call_id)
            elif args.command=='collect':result=dict(status='collected',outputs=[item.model_dump(mode='json') for item in adapter.collect_original(args.call_id)])
            else:result=dict(status=adapter.cancel_original(args.call_id))
            code=0
        result['feedback']=dict(version=1,budget=feedback.budget_hint(Path(config['record_dir']).parent.parent),
            qualification='Execution metadata does not establish scientific or candidate qualification.')
    except (IntegrityError,feedback.history.ObserverIntegrityError) as error:result=dict(status='integrity_error',note=str(error));code=3
    except OSError:result=dict(status='integrity_error',note='Execution original cannot be read');code=3
    except ValueError as error:result=dict(status='unavailable' if isinstance(error,UnsupportedExecution) else 'unresolved',note=str(error));code=2
    print(json.dumps(result,allow_nan=False));return code


if __name__=='__main__':raise SystemExit(main())
