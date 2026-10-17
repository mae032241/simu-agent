"""Registered scientific execution; one owner of the original call receipts.

No model execution, domain parser, subprocess launch or Artifact service lives here.
"""
from __future__ import annotations

import argparse
from collections.abc import Mapping
from contextlib import contextmanager, ExitStack
from dataclasses import asdict
import fcntl
import hashlib
import importlib.metadata
import importlib
import inspect
import json
import os
from pathlib import Path
import re
import sys
import time
import uuid
from functools import wraps

from . import instance_owner

from scidiscovery.operations.execution import (AdapterCapability, ExecutionInterfaceRegistration,
    LifecycleCapabilities, LocalFileDescriptor, MANAGED_METHODS, lifecycle_capabilities, LOCAL_RESULT_PROTOCOL,
    PENDING_EXECUTION_STATES, execution_status)
from scidiscovery.operations.runtime_plugins import (RuntimePluginContext, RuntimePluginContribution,
    HOST_EXECUTION_GATE_KEY, HOST_EXECUTION_GATE_SCHEMA, HOST_EXECUTION_GATE_CONTRACT)

GROUP = 'scidiscovery.execution_interfaces'
VERSION = 1
OBSERVATION_VERSION = 1
ADMISSION_VERSION = 1
MAX_BYTES = 256_000
MAX_ASSET = 32 * 1024 * 1024
MAX_CALLS = 128
MAX_INPUT_FILES = 128
MAX_INPUT_BYTES = 64 * 1024 * 1024
ID = re.compile(r'[A-Za-z0-9._-]{1,128}\Z')
RETIREMENT_KEY = 'original_submission_retirement'
RETIREMENT_SCHEMA = 'scidiscovery.permanent-submission-retirement.v1'
RETIREMENT_CONTRACT = dict(version=1, identity='original_prepared_sha256',
    absent='permanent_not_submitted', invocation='context_manager', refunds=False)
INPUT_SOURCES_KEY = 'managed_input_sources'
INPUT_SOURCES_SCHEMA = 'scidiscovery.managed-input-sources.v1'
INPUT_SOURCES_CONTRACT = dict(version=1, view='exact_snapshot_sources',
    authoring='current_job_experiment_directory', inputs='frozen_job_originals_and_read_copies',
    scope='framework_declared_inputs_only')


class IntegrityError(ValueError):
    pass


class UnsupportedExecution(ValueError):
    pass


class ReviewRequired(ValueError):
    pass


class ConcurrentExecution(ValueError):
    pass


def _configuration_effect(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        first = args[0] if args else kwargs['config']
        config = first.config if isinstance(first, Records) else first
        with instance_owner.lease_for_configuration(config):
            return function(*args, **kwargs)
    return guarded


def review_status(config):
    """Read host facts; a missing lease or deadline never becomes a new grant."""
    admission=config.get('admission')
    if not isinstance(admission,dict) or type(admission.get('version')) is not int or admission['version']!=ADMISSION_VERSION:
        raise UnsupportedExecution('Preserved admission contract is read-only; prepare a new instance')
    if admission.get('mode')=='hard':return dict(requested=False,reason=None,enforced=False,inflight_usage_unknown=True)
    if admission.get('mode')!='soft':raise UnsupportedExecution('Frozen review applicability is unavailable; prepare an applicable admission contract')
    from . import budget
    stamp=budget.clock_stamp()
    try:
        value=json.loads(read(Path(admission['directory'])/'review.json',16_000))
        if (value['scope']!=config['scope'] or value['stage_anchor']!=admission['stage_anchor']
                or value['native_attempt']!=config['native_attempt'] or value['boot_id']!=stamp['boot_id']):
            raise IntegrityError('Host review facts differ from the frozen stage or native attempt')
        deadline,lease=value['deadline_boottime'],value['valid_until_boottime']
        if (type(deadline) not in (int,float) or not 0<deadline<float('inf')
                or type(lease) not in (int,float) or not 0<lease<float('inf')):
            raise IntegrityError('Host review facts have no finite original deadline')
        reason=(value['reason'] if value['pending'] else 'review_deadline_reached' if stamp['at_boottime']>=deadline
            else 'host_review_observation_expired' if stamp['at_boottime']>=lease else None)
    except FileNotFoundError:
        reason='host_review_observation_unavailable'
    except (KeyError,TypeError) as exc:
        raise IntegrityError('Host review facts are malformed') from exc
    return dict(requested=bool(reason),reason=reason,enforced=True,inflight_usage_unknown=True)


def review_feedback(config):
    """Optional current advice cannot erase an original operation's confirmed result."""
    try:return review_status(config)
    except (OSError,ValueError,KeyError,TypeError):
        return dict(requested=None,reason='current_review_observation_unavailable',enforced=False,inflight_usage_unknown=True)


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n').encode()


def read(path, limit=None):
    path = Path(path)
    if path.resolve() != path or not path.is_file() or limit is not None and path.stat().st_size > limit:
        raise IntegrityError('Exact bounded execution original required')
    return path.read_bytes()


def proof(path, limit=None, *, context=None):
    from . import contracts as c
    path=c.regular(Path(path),limit=limit)
    if context is None:return dict(path=str(path),sha256=c.digest(path),size_bytes=path.stat().st_size)
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            context.remaining_seconds();digest.update(block)
    context.remaining_seconds()
    return dict(path=str(path),sha256=digest.hexdigest(),size_bytes=path.stat().st_size)


def write(path, value):
    with Path(path).open('x',encoding='utf-8') as stream:
        json.dump(value,stream,ensure_ascii=False,sort_keys=True,allow_nan=False)
        stream.write('\n');stream.flush();os.fsync(stream.fileno())


def registration(executor):
    if not isinstance(executor,str):raise ValueError('Exact registered executor key required')
    plugin, separator, binding = executor.partition(':')
    if not separator or not ID.fullmatch(plugin) or not ID.fullmatch(binding):
        raise ValueError('Exact registered executor key required')
    matches = list(importlib.metadata.entry_points().select(group=GROUP, name=plugin))
    if len(matches) != 1:
        raise UnsupportedExecution('Registered execution implementation unavailable')
    try:value = matches[0].load()
    except (ImportError,AttributeError) as exc:
        raise UnsupportedExecution('Registered execution implementation cannot be loaded') from exc
    if not isinstance(value, ExecutionInterfaceRegistration) or value.plugin_id != plugin:
        raise ValueError('Execution registration identity differs from its entry point')
    return value, binding


HOST_CONFIGURATION_FIELDS = frozenset({'scope','record_dir','native_attempt','admission','breadth',
    'engineering_repair','execution_interface','registered_implementation', 'host_execution_authority',
    'execution_host_services', 'frozen_execution_interface'})


def operator_configuration(value):
    """Freeze public operator settings without constructing an adapter or fake task."""
    if not isinstance(value,dict) or set(value)!={'executor','configuration'} or not isinstance(value['configuration'],dict):
        raise ValueError('Execution config requires exactly executor and configuration objects')
    if HOST_CONFIGURATION_FIELDS.intersection(value['configuration']):
        raise ValueError('Operator execution configuration cannot supply host identity or admission fields')
    # Round-trip also rejects non-JSON/nonfinite settings before creating an instance.
    body=json.loads(encoded(value))
    body['implementation']=registration_identity(body['executor'])
    return body


def _registration_assets(factory):
    module=importlib.import_module(factory.__module__.partition('.')[0])
    if not getattr(module,'__file__',None) or Path(inspect.getfile(factory)).suffix!='.py':
        raise UnsupportedExecution('Execution factory requires an inspectable regular Python package')
    paths=list(getattr(module,'__path__',()))
    if paths:
        if len(paths)!=1:raise UnsupportedExecution('Execution factory requires one exact Python package root')
        root=Path(paths[0]).absolute()
        if root.resolve()!=root:raise IntegrityError('Execution implementation package root changed')
        entries=sorted(root.rglob('*'))
        if any(path.is_symlink() for path in entries):raise IntegrityError('Registered package contains a symbolic link')
        assets=[path for path in entries if path.suffix=='.py']
    else:
        assets=[Path(inspect.getfile(factory)).absolute()]
    if not assets or any(path.suffix!='.py' for path in assets):
        raise UnsupportedExecution('Execution factory requires inspectable Python source')
    return assets


def registration_identity(executor):
    """Bind registered plugin Python package code; no factory build or backend IO.

    Namespace/multi-root and extension factories are unsupported here. This is not
    an identity for third-party dependencies or dynamically accessed resources.
    The real adapter's declared assets/capabilities are additionally frozen later.
    """
    declared,_=registration(executor)
    factory=declared.factory.build
    return dict(plugin_version=declared.version,factory=factory.__module__+':'+factory.__qualname__,
        code=[proof(path) for path in _registration_assets(factory)])


def validate_operator_configuration(value):
    if not isinstance(value,dict) or set(value)!={'executor','configuration','implementation'}:
        raise IntegrityError('Frozen operator execution configuration is malformed')
    if operator_configuration({key:value[key] for key in ('executor','configuration')})!=value:
        raise IntegrityError('Frozen registered execution implementation or operator configuration changed')
    return value


def _validate_registered_implementation(value,executor):
    """Compare the package path set, then hash each frozen original once."""
    declared,_=registration(executor);factory=declared.factory.build
    if (not isinstance(value,dict) or set(value)!={'plugin_version','factory','code'}
            or value['plugin_version']!=declared.version
            or value['factory']!=factory.__module__+':'+factory.__qualname__
            or not isinstance(value['code'],list) or not value['code']
            or [str(path) for path in _registration_assets(factory)]!=[item['path'] for item in value['code']]
            or [proof(item['path']) for item in value['code']]!=value['code']):
        raise IntegrityError('Frozen registered package implementation changed')


def _adapter(config, path, *, host_services=None):
    selected = config['execution_interface']
    declared, binding = registration(selected['executor'])
    body = {key: value for key, value in config.items() if key != 'execution_interface'}
    from . import execution_authority
    services = host_services if host_services is not None else execution_authority.host_services(config)
    contribution = declared.factory.build(RuntimePluginContext(declared.plugin_id, 'local_worker',
        Path(path), encoded(body), Path(config['record_dir']), execution_host_services=services,
        frozen_execution_interface=selected))
    if not isinstance(contribution, RuntimePluginContribution) or binding not in contribution.execution_adapters:
        raise UnsupportedExecution('Registered execution binding unavailable')
    adapter = contribution.execution_adapters[binding]
    if any(not callable(getattr(adapter,name,None)) for name in MANAGED_METHODS):
        raise UnsupportedExecution('Implementation does not provide the managed execution interface')
    if services is not None:
        gates=[item for item in adapter.capabilities() if item.key==HOST_EXECUTION_GATE_KEY]
        if (len(gates)!=1 or gates[0].schema_id!=HOST_EXECUTION_GATE_SCHEMA
                or gates[0].payload_schema_version!=1 or gates[0].kind!='execution_authority'
                or gates[0].content!=encoded(dict(HOST_EXECUTION_GATE_CONTRACT))):
            raise UnsupportedExecution('Registered implementation does not declare the trusted host execution gate')
    return declared, adapter, body


def _public_capabilities(adapter):
    result=[]
    for item in adapter.capabilities():
        if (not isinstance(item,AdapterCapability) or not isinstance(item.key,str) or not ID.fullmatch(item.key)
                or any(not isinstance(value,str) or not value
                       for value in (item.kind,item.schema_id,item.media_type))
                or type(item.payload_schema_version) is not int or item.payload_schema_version<=0
                or not isinstance(item.content,bytes) or not isinstance(item.public_summary,Mapping)
                or any(previous['key']==item.key for previous in result)):
            raise IntegrityError('Registered public capability contract is malformed')
        result.append(dict(key=item.key,kind=item.kind,schema_id=item.schema_id,
            payload_schema_version=item.payload_schema_version,media_type=item.media_type,
            public_summary=dict(item.public_summary),sha256=hashlib.sha256(item.content).hexdigest(),size_bytes=len(item.content)))
    try:encoded(result)
    except (ValueError,TypeError) as exc:
        raise IntegrityError('Registered public capability metadata is not finite JSON') from exc
    return result


def freeze(config, executor, *, path=None):
    """Host preparation only: freeze selected factory, code, configuration and flags."""
    from .protocol import require_scope
    require_scope(config.get('scope'))
    value = dict(config)
    if 'registered_implementation' in value:
        _validate_registered_implementation(value['registered_implementation'],executor)
    from . import breadth
    breadth.validate(value.get('breadth'))
    value.setdefault('admission',dict(version=ADMISSION_VERSION,mode='unavailable'))
    scope=value.get('scope')
    if (not isinstance(scope,dict) or set(scope)!={'step','role','job_sha256','execution_key','mechanism_ref','handoff_protocol'}
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
              Path(inspect.getfile(type(adapter))).resolve(), Path(__file__).resolve(), Path(inspect.getfile(breadth)).resolve(),
              Path(inspect.getfile(execution_status)).resolve()]
    assets += [Path(item).resolve() for item in adapter.code_assets()]
    from . import replay_check
    assets.append(Path(replay_check.__file__).resolve())
    assets.append(Path(instance_owner.__file__).resolve())
    if value.get('host_execution_authority') is not None:
        from . import execution_authority
        assets.extend(Path(item['path']) for item in execution_authority.implementation())
    result_protocol=getattr(adapter,'result_protocol',None)
    if result_protocol is not None and (not isinstance(result_protocol,str) or not 0<len(result_protocol.encode())<=160):
        raise ValueError('An execution result protocol requires an explicit bounded identifier')
    value['execution_interface'] = dict(version=VERSION, executor=executor, plugin_version=declared.version,
        observation_version=OBSERVATION_VERSION,
        terminal_evidence=getattr(adapter,'terminal_evidence_kind','adapter_result'),
        result_protocol=result_protocol,
        config_sha256=hashlib.sha256(encoded(body)).hexdigest(),
        capabilities=asdict(lifecycle_capabilities(adapter)),
        code=[proof(item) for item in dict.fromkeys(assets)])
    if ('registered_implementation' in value
            or any(getattr(item,'key',None)==INPUT_SOURCES_KEY for item in adapter.capabilities())):
        value['execution_interface']['public_capabilities']=_public_capabilities(adapter)
    return value


@instance_owner.effect
def configure(root,step,executor,config,output):
    """Freeze a host-bound interface before the Worker enters its existing namespace."""
    from .protocol import require_current
    require_current(root)
    from . import contracts as _contracts
    require_current(root,_contracts.read(_contracts.regular(Path(root)/'jobs'/f'{step:03d}.json')))
    from . import contracts as c, execution, budget
    root=Path(root).resolve();job=c.read(c.regular(root/'jobs'/f'{step:03d}.json'))
    versions=(c.settings(root).get('experiment_interface_version'),job.get('experiment_interface_version'))
    if any(type(value) is not int or value!=VERSION for value in versions):
        raise UnsupportedExecution('Preserved scientific instance is read-only; prepare a new registered instance')
    versions=(c.settings(root).get('managed_admission_version'),job.get('managed_admission_version'))
    if any(type(value) is not int or value!=ADMISSION_VERSION for value in versions):
        raise UnsupportedExecution('Preserved scientific admission is read-only; prepare a new instance')
    c._validate_inputs(root,c.workspace(root,step),job)
    record=execution.record(root,step)
    if c.read(c.regular(record/'native-intent.json')).get('task_sha256')!=c.digest(root/'jobs'/f'{step:03d}.json'):
        raise IntegrityError('Host configuration has no exact accepted scientific task')
    native_attempt=dict(number=len(execution.records(root,step))-1,execution_key=execution.identity(root,step))
    selected=c.settings(root).get('execution_config')
    implementation={}
    if selected is not None:
        expected=dict(selected['configuration'])
        if executor=='local_execution:command':expected.setdefault('cwd',str(c.workspace(root,step)))
        if executor!=selected['executor'] or config!=selected['configuration']:
            raise IntegrityError('Host execution configuration differs from the frozen operator selection')
        config=expected
        implementation=dict(registered_implementation=selected['implementation'])
    admission=budget.review_configuration(root,job)
    from .protocol import stage_scope
    value=dict(config,**implementation,record_dir=str(c.workspace(root,step)/'work/lineage'),native_attempt=native_attempt,admission=admission,
        scope=stage_scope(root,job),breadth=(job.get('search') or {}).get('breadth'),
        **(dict(engineering_repair=dict(candidate_id=job['engineering_repair']['candidate_id'])) if job.get('engineering_repair') else {}))
    if c.settings(root).get('execution_resource_policy') is not None and job['role'] == 'W':
        from . import execution_authority
        value['host_execution_authority'] = execution_authority.contract(root)
    value=freeze(value,executor,path=output)
    updates=[]
    # This is the same configuration already exposed to this Worker, without
    # native/session evidence. The existing control mount is read-only in-shell.
    projection=root/'host-runtime/experiment-control'/value['scope']['job_sha256']/'interfaces'/f'{native_attempt["number"]:03d}.json'
    for path in (Path(output),record/'experiment-config.json',projection):
        if path.exists():
            old=c.read(c.regular(path))
            if old==value:continue
            if path in (record/'experiment-config.json',projection) or old.get('scope')!=value['scope']:
                raise IntegrityError('Frozen experiment configuration changed')
        updates.append(path)
    # Validate every immutable conflict before replacing the current pointer.
    for path in updates:
        c.write(path,value);path.chmod(0o400)
    return value


def load(config, *, path=None, host_services=None):
    from .protocol import require_scope
    require_scope(config.get('scope') if isinstance(config,dict) else None)
    if not isinstance(config,dict):
        raise IntegrityError('Frozen execution configuration is malformed')
    if 'admission' not in config:
        raise UnsupportedExecution('Preserved admission contract is read-only; prepare a new instance')
    selected = config.get('execution_interface')
    if not isinstance(selected, dict) or type(selected.get('version')) is not int or selected['version'] != VERSION:
        raise UnsupportedExecution('Preserved execution configuration is read-only; prepare a new registered instance')
    if config.get('host_execution_authority') is not None:
        from . import execution_authority
        execution_authority.host_services(config)
    if freeze({key: value for key, value in config.items() if key != 'execution_interface'}, selected['executor'], path=path) != config:
        raise IntegrityError('Frozen execution implementation or configuration changed')
    _, adapter, _ = _adapter(config, path or Path(config['record_dir']).parent / 'config.json',host_services=host_services)
    return adapter


def original_configuration(config,call_id):
    """Resolve one accepted call's exact configuration, never the latest attempt."""
    accepted=Records(config).accepted(call_id)
    if (accepted.get('native_attempt')==config.get('native_attempt')
            and accepted.get('interface')==config['execution_interface']):
        return config
    attempt=accepted.get('native_attempt')
    if (not isinstance(attempt,dict) or set(attempt)!={'number','execution_key'}
            or type(attempt.get('number')) is not int or not 0<=attempt['number']<10000
            or not isinstance(attempt.get('execution_key'),str)
            or not re.fullmatch('[0-9a-f]{64}',attempt['execution_key'])):
        raise IntegrityError('Original execution native attempt is unavailable')
    directory=Path(config['record_dir'])
    if len(directory.parents)<5:raise IntegrityError('Original execution namespace is unavailable')
    root=directory.parents[4]
    if directory!=root/'project/nodes'/f'{config["scope"]["step"]:03d}'/'work/lineage':
        raise IntegrityError('Original execution namespace differs from its stage')
    path=root/'host-runtime/experiment-control'/config['scope']['job_sha256']/'interfaces'/f'{attempt["number"]:03d}.json'
    original=json.loads(read(path))
    if (original.get('scope')!=config['scope'] or original.get('record_dir')!=config['record_dir']
            or original.get('native_attempt')!=attempt or original.get('execution_interface')!=accepted.get('interface')):
        raise IntegrityError('Original execution configuration differs from accepted binding')
    return original


def original_adapter(config,call_id,capability):
    """Both the current permission and the original interface must allow an action."""
    current=load(config)
    def allowed(settings,adapter):
        if capability=='retire':
            _retirement_capability(settings['execution_interface'])
            return callable(getattr(adapter,'retire_original',None))
        return getattr(lifecycle_capabilities(adapter),capability)
    if not allowed(config,current):
        raise UnsupportedExecution('Requested original execution operation unavailable')
    original=original_configuration(config,call_id)
    adapter=current if original is config else load(original)
    if not allowed(original,adapter):
        raise UnsupportedExecution('Original execution operation unavailable')
    return original,adapter


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
    def lease(self, name='node.lock', *, context=None):
        if name=='accept.lock' and self.config.get('admission',{}).get('mode')=='soft':
            path=Path(self.config['admission']['directory'])/'accept.lock'
            fd=os.open(path,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW)
            try:
                if context is None:fcntl.flock(fd,fcntl.LOCK_EX)
                else:
                    while True:
                        context.remaining_seconds()
                        try:
                            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                        except BlockingIOError:time.sleep(min(.05,context.remaining_seconds()))
                yield
            finally:os.close(fd)
            return
        self.root.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.root / name, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            os.close(fd)

    @_configuration_effect
    def accept(self, descriptor, metadata, interface, *, expected_calls=None, mechanism=None, recovery_admission=None, operation_context=None):
        """Short admission linearization point. No solver or domain IO under lock."""
        from .protocol import require_scope
        require_scope(self.config['scope'])
        from . import contracts as c
        original=proof(descriptor.local_path,context=operation_context)
        if original['sha256']!=descriptor.sha256 or original['size_bytes']!=descriptor.size_bytes:
            raise IntegrityError('Prepared execution input changed')
        import shutil,tempfile
        self.root.mkdir(parents=True,exist_ok=True)
        directory=Path(tempfile.mkdtemp(prefix='.prepared-',dir=self.root))
        source = directory / 'source.py'
        c._copy_bound(Path(descriptor.local_path),source,descriptor.sha256,context=operation_context)
        destination=self.root/'calls'/descriptor.name
        source_proof=proof(source,context=operation_context);source_proof['path']=str(destination/'source.py')
        accepted = dict(metadata, call_id=descriptor.name, scope=self.config['scope'],
            source_script=descriptor.local_path, script=source_proof,native_attempt=self.config.get('native_attempt'),
            prepared=descriptor.model_dump(mode='json'), interface=interface)
        try:
            files = metadata.get('snapshot_files', [])
            if not isinstance(files,list):raise ValueError('Managed input inventory required')
            seen = set()
            for item in files:
                name = item['name']; relative = Path(name)
                if (not isinstance(name, str) or relative.is_absolute() or '..' in relative.parts
                        or relative.as_posix() != name or not relative.parts or name in seen):
                    raise ValueError('Managed input path is not canonical')
                seen.add(name)
                original=proof(item['path'],context=operation_context)
                if any(original[key]!=item[key] for key in ('sha256','size_bytes')):
                    raise IntegrityError('Managed input changed before acceptance')
                target=directory/'inputs'/relative
                c._copy_bound(Path(item['path']),target,item['sha256'],context=operation_context)
            with self.lease():
                if expected_calls is not None and [path.name for path in self.calls()]!=expected_calls:
                    raise ConcurrentExecution('Another original execution was accepted; query its identity')
                with self.lease('accept.lock',context=operation_context):
                    if recovery_admission is None:
                        review=review_status(self.config)
                        if review['requested']:raise ReviewRequired(review['reason'])
                    else:
                        recovery_admission()
                    from . import breadth
                    binding=breadth.admit(self.config.get('breadth'),mechanism,self.config['scope'],
                        [self.accepted(path.name) for path in self.calls()])
                    if binding is not None:accepted['mechanism_binding']=binding
                    write(directory/'accepted.json',accepted)
                    destination.parent.mkdir(exist_ok=True)
                    directory.rename(destination)
        finally:
            if directory.exists():shutil.rmtree(directory)
        return accepted

    @_configuration_effect
    def publish(self, call_id, filename, value):
        from .protocol import require_scope
        require_scope(self.config['scope'])
        if filename not in {'process.json', 'terminal.json', 'completed.json','submission.json','collected.json','submission-retirement.json'}:
            raise ValueError('Unknown execution receipt')
        directory = self.directory(call_id)
        accepted = json.loads(read(directory / 'accepted.json'))
        if accepted['scope'] != self.config['scope'] or accepted['call_id'] != call_id:
            raise IntegrityError('Execution receipt escaped its accepted scope')
        value=dict(value,call_id=call_id,scope=self.config['scope'])
        if 'mechanism_binding' in accepted:
            if 'mechanism_binding' in value and value['mechanism_binding']!=accepted['mechanism_binding']:
                raise IntegrityError('Execution receipt changed scientific mechanism')
            value=dict(value,call_id=call_id,scope=self.config['scope'],mechanism_binding=accepted['mechanism_binding'])
        write(directory / filename, value)

    def accepted(self,call_id):
        value=json.loads(read(self.directory(call_id)/'accepted.json'))
        if (not isinstance(value,dict) or value.get('call_id')!=call_id
                or not isinstance(value.get('scope'),dict) or type(value['scope'].get('step')) is not int
                or value['scope']!=self.config['scope']):
            raise IntegrityError('Accepted execution binding changed')
        from . import breadth
        try:breadth.check_binding(self.config.get('breadth'),value.get('mechanism_binding'),self.config['scope'])
        except ValueError as error:raise IntegrityError('Accepted scientific mechanism binding changed') from error
        parent=value.get('parent')
        if not isinstance(parent,dict) or 'candidate_id' not in parent:
            raise IntegrityError('Published execution parent is malformed')
        candidate=parent['candidate_id']
        if candidate is not None and (not isinstance(candidate,str) or not 0<len(candidate.encode())<=80):
            raise IntegrityError('Published execution parent is malformed')
        return value

    @_configuration_effect
    def bind_external(self,call_id,external_id,state):
        if not isinstance(external_id,str) or not ID.fullmatch(external_id):
            raise IntegrityError('Submitted external execution identity is invalid')
        accepted=self.accepted(call_id)
        value=dict(call_id=call_id,external_run_id=external_id,scope=self.config['scope'])
        if 'mechanism_binding' in accepted:value['mechanism_binding']=accepted['mechanism_binding']
        path=self.directory(call_id)/'submission.json'
        if path.exists():
            if json.loads(read(path))!=value:raise IntegrityError('Original external execution identity changed')
        else:self.publish(call_id,'submission.json',value)
        return external_id,state

    def external(self,call_id):
        accepted=self.accepted(call_id)
        path=self.directory(call_id)/'submission.json'
        if not path.exists():return None
        value=json.loads(read(path))
        if (value.get('call_id')!=call_id or value.get('scope')!=self.config['scope']
                or value.get('mechanism_binding')!=accepted.get('mechanism_binding')):
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
        if 'native_state' in completed:
            state=completed['native_state']
            if (not isinstance(state,str) or state not in {'succeeded','failed','cancelled'}
                    or execution_status(state)!=completed.get('status')):
                raise IntegrityError('Completed execution native terminal state changed')
            return state
        return {'known_success':'succeeded','known_failed':'failed','unknown':'unknown'}.get(completed.get('status'),'unknown')


@_configuration_effect
def dispatch(config, script, *, parent=None, new=False, change=None, mechanism=None, command_options=None):
    """Convenience input path; neutral callers may provide a descriptor directly."""
    source=Path(script).resolve();item=proof(source)
    payload=LocalFileDescriptor(name='input',local_path=str(source),sha256=item['sha256'],
        size_bytes=item['size_bytes'],media_type='application/octet-stream')
    return dispatch_descriptor(config,payload,parent=parent,new=new,change=change,mechanism=mechanism,command_options=command_options)


def local_terminal_status(accepted, completed, terminal):
    """Legacy local originals only; no fabricated POSIX receipts for other backends."""
    if not isinstance(completed,dict) or not isinstance(terminal,dict):return 'unknown'
    if any(value.get(key)!=accepted.get(key) for value in (completed,terminal)
           for key in ('call_id','scope','mechanism_binding')):return 'unknown'
    if (terminal.get('cleanup_confirmed') is not True or terminal.get('transport_complete') is not True
            or type(terminal.get('returncode')) is not int):return 'unknown'
    expected='known_success' if terminal['returncode']==0 else 'known_failed'
    return expected if completed.get('status')==expected else 'unknown'


def verify_observation(value, original, *, interface=None, context=None):
    """Verify frozen control facts using exact bytes, never a live backend query."""
    def bound(item):
        data=original(item)
        if isinstance(data,Path):
            valid=proof(data,context=context)
            changed=any(valid[key]!=item[key] for key in ('sha256','size_bytes'))
        else:changed=hashlib.sha256(data).hexdigest()!=item['sha256'] or len(data)!=item['size_bytes']
        if changed:raise IntegrityError('Execution observation original changed')
        return data
    def decoded(item):
        data=bound(item)
        if isinstance(data,Path):
            with data.open(encoding='utf-8') as stream:return json.load(stream)
        return json.loads(data)
    if not isinstance(value,dict) or value.get('version')!=OBSERVATION_VERSION:
        raise IntegrityError('Execution observation version unavailable')
    accepted=decoded(value['accepted']);completed=decoded(value['completed'])
    submission=decoded(value['submission'])
    if (value.get('interface')!=accepted.get('interface') or interface is not None and value.get('interface')!=interface
            or value.get('status') not in {'known_success','known_failed'}
            or value['status']!=completed.get('status')
            or value.get('external_run_id')!=submission.get('external_run_id')
            or not isinstance(value.get('external_run_id'),str)):
        raise IntegrityError('Execution observation differs from accepted interface or terminal result')
    if ('native_state' in completed or 'native_state' in value):
        state=completed.get('native_state')
        if (not isinstance(state,str) or state not in {'succeeded','failed','cancelled'} or value.get('native_state')!=state
                or execution_status(state)!=value['status']):
            raise IntegrityError('Execution observation differs from the native terminal state')
    for row in (accepted,completed,submission):
        if any(row.get(key)!=value.get(key) for key in ('call_id','scope','mechanism_binding')):
            raise IntegrityError('Execution observation escaped its accepted owner')
    for item in [*value['proofs'],*value['outputs']]:
        bound(item)
        if any(item['source'][key]!=item[key] for key in ('sha256','size_bytes')):
            raise IntegrityError('Collected observation differs from its declared descriptor')
    if [item['source'] for item in value['proofs']]!=completed.get('proofs'):
        raise IntegrityError('Retained backend proofs differ from the original completion descriptors')
    for item in value['outputs']:
        descriptor=LocalFileDescriptor.model_validate(item['descriptor'])
        if (descriptor.name!=item['name'] or descriptor.local_path!=item['source']['path']
                or descriptor.sha256!=item['sha256'] or descriptor.size_bytes!=item['size_bytes']):
            raise IntegrityError('Retained collection differs from its original descriptor')
    if value['interface'].get('terminal_evidence')=='local_process':
        terminal=decoded(value['native_terminal'])
        if local_terminal_status(accepted,completed,terminal)!=value['status']:
            raise IntegrityError('Local observation lacks confirmed cleanup, transport or exit status')
    elif value['interface'].get('terminal_evidence')!='adapter_result':
        raise IntegrityError('Execution terminal evidence contract unavailable')
    return value['status']


def _retirement_capability(interface):
    rows=[row for row in interface.get('public_capabilities',[]) if row.get('key')==RETIREMENT_KEY]
    if (len(rows)!=1 or rows[0].get('schema_id')!=RETIREMENT_SCHEMA
            or type(rows[0].get('payload_schema_version')) is not int or rows[0]['payload_schema_version']!=1
            or rows[0].get('kind')!='execution_recovery' or rows[0].get('media_type')!='application/json'):
        raise UnsupportedExecution('Original permanent retirement capability is unavailable')
    return rows[0]


def _retirement_contract(contract,capability):
    if (not isinstance(contract,dict) or set(contract)!=set(RETIREMENT_CONTRACT)|{'backend_protocol'}
            or encoded({key:contract.get(key) for key in RETIREMENT_CONTRACT})!=encoded(RETIREMENT_CONTRACT)
            or not isinstance(contract.get('backend_protocol'),dict) or not contract['backend_protocol']):
        raise IntegrityError('Permanent retirement capability contract changed')
    raw=encoded(contract)
    if capability.get('sha256')!=hashlib.sha256(raw).hexdigest() or capability.get('size_bytes')!=len(raw):
        raise IntegrityError('Permanent retirement capability bytes differ from the frozen interface')
    return contract


def verify_retirement(value, original, *, interface=None, context=None):
    """Verify an independent never-submitted fact, without a backend or budget IO."""
    def bound(item):
        data=original(item)
        if isinstance(data,Path):
            if data.resolve()!=data:raise IntegrityError('Retirement original path changed')
            actual=proof(data,context=context)
            if any(actual[key]!=item[key] for key in ('sha256','size_bytes')):
                raise IntegrityError('Retirement original changed')
            data=data.read_bytes()
        if hashlib.sha256(data).hexdigest()!=item['sha256'] or len(data)!=item['size_bytes']:
            raise IntegrityError('Retirement original changed')
        return data
    def decoded(item):return json.loads(bound(item))
    if (not isinstance(value,dict) or type(value.get('version')) is not int or value['version']!=1
            or value.get('kind')!='permanent_not_submitted'):
        raise IntegrityError('Permanent retirement contract is unavailable')
    accepted=decoded(value['accepted'])
    selected=accepted.get('interface')
    if (value.get('interface')!=selected or interface is not None and selected!=interface
            or value.get('capability')!=_retirement_capability(selected)
            or any(value.get(key)!=accepted.get(key) for key in ('call_id','scope','native_attempt','mechanism_binding'))
            or value.get('prepared')!=accepted.get('prepared')
            or value.get('authority')!=accepted.get('execution_authority')):
        raise IntegrityError('Retirement differs from the original accepted call')
    contract=_retirement_contract(value['contract'],value['capability'])
    prepared=value['prepared']
    if (accepted['script'].get('path')!=str(Path(value['accepted']['path']).parent/'source.py')
            or prepared.get('name')!=value['call_id']
            or (accepted['script'].get('sha256'),accepted['script'].get('size_bytes'))!=(prepared['sha256'],prepared['size_bytes'])):
        raise IntegrityError('Retirement prepared copy differs from its original descriptor')
    bound(accepted['script'])
    bound(dict(path=prepared['local_path'],sha256=prepared['sha256'],size_bytes=prepared['size_bytes']))
    decoded(value['authority'])
    request=decoded(value['request']);response=decoded(value['response']);protocol=decoded(value['protocol'])
    if encoded(protocol)!=encoded(contract['backend_protocol']):
        raise IntegrityError('Retirement backend protocol differs from its frozen permanent contract')
    if (request.get('call_id')!=value['call_id'] or request.get('scope')!=value['scope']
            or request.get('accepted')!=value['accepted'] or request.get('prepared')!=value['prepared']
            or request.get('authority')!=value['authority'] or request.get('target')!=accepted.get('execution_target')
            or response.get('found') is not False or response.get('retired') is not True
            or response.get('submission_sha256')!=value['prepared']['sha256']):
        raise IntegrityError('Backend retirement does not prove the exact original was never submitted')
    dispatch=value.get('dispatch_intent')
    if dispatch is not None:
        intent=decoded(dispatch)
        if (dispatch.get('path')!=accepted.get('submission_intent_path')
                or intent.get('call_id')!=value['call_id'] or intent.get('scope')!=value['scope']
                or intent.get('prepared')!=value['prepared'] or intent.get('authority')!=value['authority']):
            raise IntegrityError('Retirement changed the original dispatch intent')
    return dict(call_id=value['call_id'],scope=value['scope'],prepared=value['prepared'],
                accepted=value['accepted'],authority=value['authority'])


def retirement_originals(value,accepted):
    prepared=value['prepared']
    result=[value[key] for key in ('accepted','authority','request','response','protocol')]
    result.extend([accepted['script'],dict(path=prepared['local_path'],sha256=prepared['sha256'],size_bytes=prepared['size_bytes'])])
    if value.get('dispatch_intent') is not None:result.append(value['dispatch_intent'])
    return result


def retirement(config,call_id):
    records=Records(config);directory=records.directory(call_id)
    path=directory/'submission-retirement.json'
    if not path.exists() and not path.is_symlink():return None
    value=json.loads(read(path));accepted=records.accepted(call_id)
    if (value.get('accepted')!=proof(directory/'accepted.json') or value.get('prepared')!=accepted['prepared']
            or records.external(call_id) is not None
            or any((directory/name).exists() or (directory/name).is_symlink()
                   for name in ('completed.json','terminal.json','execution-observation.json'))):
        raise IntegrityError('Permanent non-submission contradicts the original call')
    dispatch=Path(accepted['submission_intent_path'])
    if (dispatch.parent!=directory or dispatch.resolve()!=dispatch
            or value.get('dispatch_intent')!=(proof(dispatch) if dispatch.exists() else None)):
        raise IntegrityError('Retired call dispatch identity changed')
    verify_retirement(value,lambda item:Path(item['path']),interface=config['execution_interface'])
    return value


@_configuration_effect
def retire_original(config,adapter,call_id):
    capability=_retirement_capability(config['execution_interface'])
    matches=[item for item in adapter.capabilities() if item.key==RETIREMENT_KEY]
    if len(matches)!=1:raise UnsupportedExecution('Original retirement declaration is unavailable')
    contract=_retirement_contract(json.loads(matches[0].content),capability)
    existing=retirement(config,call_id)
    if existing is not None:
        from . import execution_authority
        accounting=execution_authority.reconcile_resources(config,adapter,call_id)
        return dict(call_id=call_id,status='not_submitted',receipt=proof(Records(config).directory(call_id)/'submission-retirement.json'),
                    **(dict(resource_accounting=accounting) if accounting is not None else {}))
    method=getattr(adapter,'retire_original',None)
    if not callable(method):raise UnsupportedExecution('Original retirement method is unavailable')
    records=Records(config);directory=records.directory(call_id)
    try:
        with method(call_id) as evidence:
            if evidence.get('status')!='not_submitted':return evidence
            accepted=records.accepted(call_id)
            value=dict(version=1,kind='permanent_not_submitted',call_id=call_id,scope=accepted['scope'],
                native_attempt=accepted.get('native_attempt'),mechanism_binding=accepted.get('mechanism_binding'),
                interface=accepted['interface'],accepted=proof(directory/'accepted.json'),prepared=accepted['prepared'],
                authority=accepted['execution_authority'],capability=_retirement_capability(accepted['interface']),contract=contract,
                **{key:evidence[key] for key in ('request','response','protocol','dispatch_intent')})
            verify_retirement(value,lambda item:Path(item['path']),interface=config['execution_interface'])
            path=directory/'submission-retirement.json'
            if path.exists():
                if json.loads(read(path))!=value:raise IntegrityError('Retirement publication changed')
            else:records.publish(call_id,'submission-retirement.json',value)
            retirement(config,call_id)
            from . import execution_authority
            accounting=execution_authority.reconcile_resources(config,adapter,call_id)
            return dict(call_id=call_id,status='not_submitted',receipt=proof(path),
                        **(dict(resource_accounting=accounting) if accounting is not None else {}))
    except BlockingIOError:
        return dict(call_id=call_id,status='unknown',note='Original submission or retirement still owns its call lease')


@_configuration_effect
def record_observation(config, adapter, call_id, *, collected=None, operation_context=None):
    """Freeze one backend-verified terminal projection while executing its protocol.

    The adapter owns its native terminal evidence. In particular local adapters
    validate cleanup, transport and exit code in status_details/result. Scientific
    readers consume only this immutable projection and its retained originals.
    """
    records=Records(config);directory=records.directory(call_id)
    path=directory/'execution-observation.json'
    if path.exists():
        value=json.loads(read(path));verify_observation(value,lambda item:Path(item['path']),
            interface=config['execution_interface'],context=operation_context)
        from . import execution_authority
        execution_authority.reconcile_resources(config,adapter,call_id,observation=value,operation_context=operation_context)
        return value
    accepted=records.accepted(call_id)
    if accepted['interface']!=config['execution_interface']:
        raise IntegrityError('Observation interface differs from accepted execution')
    external=records.external(call_id)
    if external is None:return None
    details=adapter.status_details(call_id);state=details.get('state')
    status=execution_status(state)
    if status not in {'known_success','known_failed'}:return None
    result=adapter.result(call_id)
    completion=directory/'completed.json'
    if result.get('status')=='unknown' and not completion.exists() and not completion.is_symlink():return None
    completed=json.loads(read(directory/'completed.json'))
    if (result!=completed or completed.get('status')!=status
            or any(completed.get(key)!=accepted.get(key) for key in ('call_id','scope','mechanism_binding'))):
        raise IntegrityError('Adapter terminal projection differs from accepted completion')
    if (state=='cancelled' or 'native_state' in completed) and completed.get('native_state')!=state:
        raise IntegrityError('Adapter completion must retain its native terminal state')
    proofs=result.get('proofs')
    if not isinstance(proofs,list) or not proofs:
        raise IntegrityError('Adapter terminal result requires bounded original proofs')
    for item in proofs:
        if proof(item['path'],context=operation_context)!=item:raise IntegrityError('Adapter terminal original changed')
    def retain(item):
        from . import contracts as c
        source=Path(item['path']);original=proof(source,context=operation_context)
        if any(original[key]!=item[key] for key in ('sha256','size_bytes')):
            raise IntegrityError('Execution observation original changed during collection')
        target=directory/'observed-originals'/item['sha256']
        c._copy_bound(source,target,item['sha256'],context=operation_context)
        return dict(proof(target,context=operation_context),source=item)
    proofs=[retain(item) for item in proofs]
    outputs=[];names=set()
    if lifecycle_capabilities(adapter).collect:
        descriptors=adapter.collect_original(call_id) if collected is None else collected
        for descriptor in descriptors:
            name=Path(descriptor.name)
            if (name.is_absolute() or '..' in name.parts or not name.parts or name.as_posix()!=descriptor.name
                    or '\\' in descriptor.name or descriptor.name in names):
                raise IntegrityError('Collected observation requires distinct canonical names')
            names.add(descriptor.name)
            item=proof(descriptor.local_path,context=operation_context)
            if item['sha256']!=descriptor.sha256 or item['size_bytes']!=descriptor.size_bytes:
                raise IntegrityError('Collected observation original changed')
            outputs.append(dict(retain(item),name=descriptor.name,descriptor=descriptor.model_dump(mode='json')))
    value=dict(version=OBSERVATION_VERSION,call_id=call_id,scope=accepted['scope'],
        mechanism_binding=accepted.get('mechanism_binding'),interface=accepted['interface'],
        external_run_id=external,status=status,accepted=proof(directory/'accepted.json'),
        completed=proof(directory/'completed.json'),submission=proof(directory/'submission.json'),proofs=proofs,outputs=outputs)
    if 'native_state' in completed:value['native_state']=completed['native_state']
    if config['execution_interface'].get('terminal_evidence')=='local_process':
        value['native_terminal']=proof(directory/'terminal.json')
    verify_observation(value,lambda item:Path(item['path']),context=operation_context)
    with records.lease('observation-'+call_id+'.lock'):
        if path.exists():
            if json.loads(read(path))!=value:raise IntegrityError('Frozen execution observation changed')
        else:write(path,value)
    from . import execution_authority
    execution_authority.reconcile_resources(config,adapter,call_id,observation=value,operation_context=operation_context)
    return value


@_configuration_effect
def dispatch_descriptor(config, payload, *, parent=None, new=False, change=None, mechanism=None, command_options=None):
    from . import execution_authority
    try:return _dispatch_descriptor(config,payload,parent=parent,new=new,change=change,mechanism=mechanism,command_options=command_options)
    except execution_authority.AuthorityRequired as error:return error.feedback
    except BlockingIOError:return dict(status='unknown',note='Original accepted execution still owns its lease')
    except ConcurrentExecution as error:return dict(status='unknown',note=str(error))


def _dispatch_descriptor(config, payload, *, parent=None, new=False, change=None, mechanism=None, command_options=None):
    from .protocol import require_scope
    require_scope(config.get('scope'))
    if config.get('host_execution_authority') is not None:
        from . import execution_authority,execution_recovery
        root,_,_=execution_authority._host_context(config)
        if execution_recovery.pending(root):
            return dict(status='unknown',note='Original host execution recovery is unresolved; preserve its identity without a new call.')
    repair=config.get('engineering_repair')
    if repair is not None and (parent!=repair['candidate_id'] or new or not change or Records(config).calls()):
        raise ValueError('Engineering repair allows one exact parent candidate call with a declared change')
    adapter = load(config)
    capabilities = lifecycle_capabilities(adapter)
    if not capabilities.atomic_admission:
        raise UnsupportedExecution('Implementation does not support managed admission')
    records = Records(config)
    before=records.calls()
    for path in before:
        if retirement(original_configuration(config,path.name),path.name) is not None:continue
        original,prior=original_adapter(config,path.name,'query')
        details=prior.status_details(path.name)
        state=execution_status(details.get('state'))
        if state not in {'known_success','known_failed'} or records.external(path.name) is None:
            return dict(status=state if state in PENDING_EXECUTION_STATES and records.external(path.name) is not None else 'unknown',
                call_id=path.name,note='Preserve original execution; query its identity instead of replay')
        observed=record_observation(original,prior,path.name)
        if observed is None:
            return dict(status='unknown',call_id=path.name,
                note='Original terminal execution has no verified observation; preserve its identity.')
        if details.get('state')=='cancelled' and observed.get('native_state')!='cancelled':
            raise IntegrityError('Original cancellation has no bound native terminal observation')
    call_id = f'{len(before)+1:04d}-{uuid.uuid4().hex}'
    if config.get('host_execution_authority') is not None:
        from . import execution_authority
        call_id=execution_authority.host_services(config).call_identity(payload,len(before)+1,mechanism)
    descriptor = payload.model_copy(update={'name':call_id})
    prepared = adapter.prepare(descriptor, preparation_profile='research_loop.v1', exchange_directory=records.root)
    options = dict(command_options=command_options) if command_options is not None else {}
    try:
        metadata = adapter.acceptance_metadata(prepared, parent=parent, new=new, change=change, **options)
    except TypeError as error:
        if options:raise UnsupportedExecution('Selected executor does not support local command options') from error
        raise
    source_contracts=[item for item in adapter.capabilities() if item.key==INPUT_SOURCES_KEY]
    if len(source_contracts)>1:raise IntegrityError('Ambiguous managed input source declaration')
    if source_contracts:
        item=source_contracts[0]
        actual=[row for row in _public_capabilities(adapter) if row['key']==INPUT_SOURCES_KEY]
        frozen=[row for row in config['execution_interface'].get('public_capabilities',[]) if row['key']==INPUT_SOURCES_KEY]
        if frozen!=actual:raise IntegrityError('Managed input source capability differs from frozen interface')
        if (item.kind=='source_provenance' and item.schema_id==INPUT_SOURCES_SCHEMA
                and item.payload_schema_version==1 and item.media_type=='application/json'
                and item.content==encoded(INPUT_SOURCES_CONTRACT)):
            method=getattr(adapter,'input_sources',None)
            metadata['input_sources']=dict(contract=dict(key=item.key,kind=item.kind,schema_id=item.schema_id,
                payload_schema_version=item.payload_schema_version,media_type=item.media_type,
                content=item.content.decode('utf-8'),sha256=hashlib.sha256(item.content).hexdigest(),size_bytes=len(item.content)),
                view=method(prepared,metadata) if callable(method) else None)
    from . import replay_check
    metadata['engineering_check'] = replay_check.acceptance(config, adapter)
    accepted = records.accept(prepared, metadata, config['execution_interface'],expected_calls=[path.name for path in before],mechanism=mechanism)
    adapter.dispatch_lease(accepted)
    external_id,state=adapter.submit(prepared)
    records.bind_external(call_id,external_id,state)
    observed=record_observation(config,adapter,call_id)
    replay_check.complete(config, adapter, call_id, observed)
    result=adapter.result(call_id)
    if observed is None and capabilities.query and records.external(call_id) is not None:
        state=execution_status(adapter.status_details(call_id).get('state'))
        if state in PENDING_EXECUTION_STATES:
            result=dict(result,status=state,note='Original execution is '+state+'; preserve its identity without resubmission.')
    return result


@_configuration_effect
def progress(config):
    adapter = load(config)
    if not lifecycle_capabilities(adapter).query:
        raise UnsupportedExecution('Execution query unavailable')
    rows = []
    counts = dict.fromkeys(('accepted', 'submitted', 'queued', 'running', 'cancelling', 'known_success', 'known_failed', 'not_submitted', 'unknown'), 0)
    for path in Records(config).calls():
        if retirement(original_configuration(config,path.name),path.name) is not None:
            counts['not_submitted']+=1
            rows.append(dict(call_id=path.name,status='not_submitted',candidate_id=None))
            continue
        binding=None
        try:
            _,prior=original_adapter(config,path.name,'query')
            details = prior.status_details(path.name)
            binding=Records(config).accepted(path.name).get('mechanism_binding')
        except (FileNotFoundError,json.JSONDecodeError,UnicodeDecodeError):
            details=dict(state='unknown')
        except IntegrityError:
            raise
        except (OSError,KeyError,TypeError,AttributeError,RecursionError) as error:
            raise IntegrityError('Published execution metadata is malformed or unavailable') from error
        state = execution_status(details.get('state'))
        counts[state] += 1
        rows.append(dict(call_id=path.name, **(dict(mechanism_ref=binding['mechanism_ref']) if binding else {}), status=state, candidate_id=details.get('candidate_id'),
            evaluation_key=details.get('evaluation_key'), metric=details.get('metric'), direction=details.get('direction'),
            wall_seconds=details.get('wall_seconds'), parent_candidate=details.get('parent_candidate'),
            **(dict(native_state='cancelled') if details.get('state')=='cancelled' else {}),
            **(dict(returncode=details['returncode'],result=details['result']) if details.get('result') is not None else {})))
    return dict(version=1, calls=rows[-16:], counts=counts, omitted_count=max(0, len(rows)-16),
        coverage='partial' if counts['unknown'] else 'complete', observed_at=time.time())


def preserved_progress(config):
    records=Records(config);rows=[];counts=dict.fromkeys(('accepted','running','known_success','known_failed','unknown'),0)
    for directory in records.calls():
        records.accepted(directory.name)
        path=directory/'completed.json'
        value=json.loads(read(path)) if path.exists() else {}
        status=value.get('status','unknown')
        if status not in counts:status='unknown'
        counts[status]+=1
        rows.append(dict(call_id=directory.name,status=status,qualification='Preserved receipt; no current scientific interpretation'))
    return dict(calls=rows[-16:],counts=counts,omitted_count=max(0,len(rows)-16),coverage='preserved_originals_only')


@_configuration_effect
def compile_implementation(config, adapter, source, aliases, output):
    """Optional registered authoring; this does not dispatch or grant execution."""
    capabilities = [item for item in _public_capabilities(adapter) if item['key'] == 'implementation_authoring']
    if (len(capabilities) != 1 or capabilities[0] not in config['execution_interface'].get('public_capabilities', [])
            or not callable(getattr(adapter, 'compile_implementation', None))):
        raise UnsupportedExecution('Selected implementation does not declare optional scientific compilation')
    if not isinstance(aliases, dict) or any(not isinstance(key, str) or not isinstance(value, str) for key, value in aliases.items()):
        raise ValueError('Scientific file choices must map slot names to exact bound input aliases')
    return adapter.compile_implementation(source, aliases, output)


def main(argv=None):
    # -m runs this file as __main__; registered factories import its canonical name.
    from . import feedback, experiments as common
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True)
    sub=parser.add_subparsers(dest='command',required=True)
    run=sub.add_parser('run');payload=run.add_mutually_exclusive_group(required=True)
    payload.add_argument('--script',type=Path);payload.add_argument('--payload',type=Path)
    run.add_argument('--experiment-dir',type=Path,help='Snapshot only this explicit experiment directory, excluding artifacts/; execute its script copy and collect artifacts/')
    choice=run.add_mutually_exclusive_group();choice.add_argument('--parent-plan');choice.add_argument('--new-plan',action='store_true')
    run.add_argument('--change-intent');run.add_argument('--mechanism')
    run.add_argument('arguments',nargs=argparse.REMAINDER,help='Script arguments after --; passed as argv, never shell text')
    sub.add_parser('lineage-status')
    compile_command = sub.add_parser('compile', help='Optional local compilation of scientific slots; grants no execution')
    compile_command.add_argument('--implementation', type=Path, required=True)
    compile_command.add_argument('--scientific-files', type=Path, required=True, help='JSON slot-name to listed scientific input alias map; {} for self-contained sources')
    compile_command.add_argument('--output', type=Path, required=True, help='New package under this task artifacts/')
    capabilities=sub.add_parser('capabilities',help='Read compact declared public input contracts and lifecycle support')
    capabilities.add_argument('--start',type=int,default=0)
    describe=sub.add_parser('describe',help='Copy one complete declared public contract to an explicit new file')
    describe.add_argument('--key',required=True);describe.add_argument('--output',type=Path,required=True)
    describe.add_argument('--metadata',action='store_true',help='Copy complete public contract metadata instead of its content')
    for name in ('query','lookup','collect','cancel','reconcile','retire'):
        item=sub.add_parser(name,**(dict(help='Freeze the same original terminal facts using query and declared collection; never submit a new execution.') if name=='reconcile' else {}))
        item.add_argument('--call-id',required=True)
    args=parser.parse_args(argv)
    owner_lease = ExitStack()
    try:
        config=json.loads(read(args.config));feedback_config=config
        from . import protocol
        scope=config.get('scope',{})
        if args.command=='lineage-status' and (type(scope.get('handoff_protocol')) is not int or scope['handoff_protocol']!=protocol.CURRENT):
            print(json.dumps(preserved_progress(config),allow_nan=False));return 0
        owner_lease.enter_context(instance_owner.lease_for_configuration(config))
        if args.command in {'run','compile','lookup','collect','cancel','reconcile','retire'}:
            from .protocol import require_scope
            require_scope(config.get('scope'))
        adapter=load(config,path=args.config)
        if args.command in {'capabilities','describe'}:
            declared=_public_capabilities(adapter)
            frozen=config['execution_interface'].get('public_capabilities')
            if frozen is not None and declared!=frozen:raise IntegrityError('Frozen public execution contract changed')
            if args.command=='capabilities':
                if not 0<=args.start<=len(declared):raise ValueError('Exact capability continuation position required')
                result=dict(executor=config['execution_interface']['executor'],lifecycle=config['execution_interface']['capabilities'],contracts=[])
                for item in declared[args.start:]:
                    compact=dict(item)
                    if len(encoded(compact))>8000:compact['public_summary']=dict(view_status='details_omitted')
                    if len(encoded(compact))>8000:
                        compact={key:item[key] for key in ('key','sha256','size_bytes','payload_schema_version')}
                        compact['metadata_view_status']='details_omitted; describe --metadata'
                    if len(encoded(dict(result,contracts=[*result['contracts'],compact])))>14_000:break
                    result['contracts'].append(compact)
                position=args.start+len(result['contracts'])
                result.update(start=args.start,omitted_count=len(declared)-len(result['contracts']),
                    next_start=position if position<len(declared) else None)
                result['read_contract']='describe --key <key> --output <new scratch file>; add --metadata for full public metadata'
            else:
                items=[item for item in adapter.capabilities() if item.key==args.key]
                if len(items)!=1:raise UnsupportedExecution('Exact declared public capability key unavailable')
                item=items[0];expected=next(row for row in declared if row['key']==args.key)
                if hashlib.sha256(item.content).hexdigest()!=expected['sha256'] or len(item.content)!=expected['size_bytes']:
                    raise IntegrityError('Public execution contract changed while reading')
                output=args.output.absolute()
                if output.resolve()!=output or not output.parent.is_dir():raise IntegrityError('Exact new public contract output path required')
                with output.open('xb') as stream:
                    stream.write(encoded(expected) if args.metadata else item.content);stream.flush();os.fsync(stream.fileno())
                result=dict(key=item.key,contract=proof(output),kind='public_metadata' if args.metadata else 'public_contract')
            code=0
        elif args.command=='compile':
            result=compile_implementation(config,adapter,args.implementation,json.loads(read(args.scientific_files)),args.output)
            code=0
        elif args.command=='run':
            arguments=args.arguments[1:] if args.arguments[:1]==['--'] else args.arguments
            options=dict(arguments=arguments,experiment_directory=str(args.experiment_dir.absolute()) if args.experiment_dir else None)
            result=dispatch(config,args.script or args.payload,parent=args.parent_plan,new=args.new_plan,change=args.change_intent,mechanism=args.mechanism,
                command_options=options if arguments or args.experiment_dir else None)
            result=adapter.public_result(result)
            code={'known_success':0,'known_failed':1}.get(result['status'],2)
        elif args.command=='lineage-status':result=progress(config);code=0
        elif args.command=='retire':
            config,adapter=original_adapter(config,args.call_id,'retire')
            result=retire_original(config,adapter,args.call_id)
            code=0 if result.get('status')=='not_submitted' else 2
        else:
            capability='lookup_submission' if args.command=='lookup' else 'query' if args.command in {'query','reconcile'} else args.command
            if not getattr(lifecycle_capabilities(adapter),capability):
                raise UnsupportedExecution('Requested original execution operation unavailable')
            config,adapter=original_adapter(config,args.call_id,capability)
            if args.command=='query':result=adapter.status_details(args.call_id)
            elif args.command=='reconcile':
                observed=record_observation(config,adapter,args.call_id)
                from . import replay_check
                replay_check.complete(config, adapter, args.call_id, observed)
                state=execution_status(adapter.status_details(args.call_id).get('state')) if observed is None and Records(config).external(args.call_id) is not None else 'unknown'
                pending=state in PENDING_EXECUTION_STATES
                result=dict(call_id=args.call_id,status=observed['status'] if observed is not None else state if pending else 'unknown',
                    **(dict(native_state=observed['native_state']) if observed is not None and 'native_state' in observed else {}),
                    note='Original terminal observation frozen; no new submission.' if observed is not None else 'Original accepted execution is '+state+'.' if pending else 'Original execution has no verified terminal observation.')
            elif args.command=='lookup':
                records=Records(config);accepted=records.accepted(args.call_id)
                descriptor=LocalFileDescriptor.model_validate(accepted['prepared'])
                found=adapter.lookup_submission(descriptor)
                if found is None:result=dict(state='unknown',call_id=args.call_id)
                else:
                    records.bind_external(args.call_id,*found)
                    result=adapter.status_details(args.call_id)
            elif args.command=='collect':
                descriptors=adapter.collect_original(args.call_id)
                result=dict(status='collected',outputs=[item.model_dump(mode='json') for item in descriptors])
            else:result=dict(status=adapter.cancel_original(args.call_id))
            if args.command=='collect':record_observation(config,adapter,args.call_id,collected=descriptors)
            elif args.command in {'query','lookup'} and execution_status(result.get('state')) in {'known_success','known_failed'}:
                if (Records(config).directory(args.call_id)/'execution-observation.json').exists():
                    record_observation(config,adapter,args.call_id)
            code=2 if args.command=='reconcile' and result['status'] not in {'known_success','known_failed'} else 0
        call_id = result.get('call_id', getattr(args, 'call_id', None))
        if call_id is not None:
            from . import replay_check
            result['engineering_check'] = replay_check.public(config, call_id)
        result['feedback']=dict(version=1,budget=feedback.budget_hint(Path(feedback_config['record_dir']).parent.parent),
            review=review_feedback(feedback_config),
            qualification='Execution metadata does not establish scientific or candidate qualification.')
    except ReviewRequired as error:result=dict(status='review_required',reason=str(error),accepted=False);code=2
    except (IntegrityError,common.IntegrityError,feedback.history.ObserverIntegrityError) as error:result=dict(status='integrity_error',note=str(error));code=3
    except OSError:result=dict(status='integrity_error',note='Execution original cannot be read');code=3
    except ValueError as error:result=dict(status='unavailable' if isinstance(error,(UnsupportedExecution,common.UnsupportedExecution)) else 'unresolved',note=str(error));code=2
    finally:owner_lease.close()
    # CLI is a compact model view; the complete collection is already durable.
    if isinstance(result.get('outputs'),list):
        original=result['outputs'];result=dict(result,outputs=[])
        for item in original:
            proposed=dict(result,outputs=[*result['outputs'],item])
            if len(encoded(proposed))>16_000:break
            result['outputs'].append(item)
        if len(result['outputs'])<len(original):result['outputs_omitted_count']=len(original)-len(result['outputs'])
    print(json.dumps(result,allow_nan=False));return code


if __name__=='__main__':raise SystemExit(main())
