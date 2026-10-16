"""Ordinary local scientific commands under the caller's native permissions."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import selectors
import signal
import shutil
import subprocess
import time

from scidiscovery.operations.execution import (AdapterCapability, ExecutionInterfaceRegistration,
    LifecycleCapabilities, LocalFileDescriptor)
from scidiscovery.operations.runtime_plugins import RuntimePluginContribution, RuntimePluginFactory
from . import experiments as e

MAX_SCAN_ENTRIES = 1024


class LocalExecution:
    terminal_evidence_kind = 'local_process'
    result_protocol = e.LOCAL_RESULT_PROTOCOL

    def __init__(self, config):
        self.config=config
        self.records=e.Records(config)
        self._lease=None

    @staticmethod
    def code_assets():
        from . import runtime
        from scidiscovery.operations import execution
        return [runtime.__file__, execution.__file__]

    @staticmethod
    def lifecycle_capabilities():
        return LifecycleCapabilities(lookup_submission=True,query=True,collect=True,atomic_admission=True)

    @staticmethod
    def capabilities():
        content=e.encoded(dict(kind='local_command',domain_metrics=False))
        return (AdapterCapability('local_command','execution','scidiscovery.local-command.v1',1,
            'application/json',content,dict(kind='local_command')),)

    def prepare(self,payload,*,preparation_profile,exchange_directory):
        if preparation_profile!='research_loop.v1' or Path(exchange_directory)!=self.records.root:
            raise ValueError('Exact managed preparation context required')
        if e.proof(payload.local_path)['sha256']!=payload.sha256:
            raise e.IntegrityError('Prepared command source changed')
        argv=self.config['run_argv']
        if not isinstance(argv,list) or not argv or not all(isinstance(item,str) and item for item in argv):
            raise ValueError('Explicit local command argv required')
        seconds=self.config['max_seconds']
        if type(seconds) not in (int,float) or not 0<seconds<float('inf'):
            raise ValueError('Finite original execution time limit required')
        return payload

    def acceptance_metadata(self,payload,*,parent=None,new=False,change=None,command_options=None):
        if parent is not None or change is not None:
            raise ValueError('This implementation does not declare candidate parent semantics')
        options=command_options or {}; arguments=options.get('arguments',[])
        if (set(options)-{'arguments','experiment_directory'} or not isinstance(arguments,list)
                or len(arguments)>128 or any(not isinstance(item,str) or '\0' in item for item in arguments)
                or sum(len(item.encode()) for item in arguments)>16_000):
            raise ValueError('Bounded command argv required')
        metadata=dict(parent=dict(status='unknown',candidate_id=None,source='none'),change_intent=None,
            local_observation_version=1,
            command=[*self.config['run_argv'],payload.local_path,*arguments],script_index=len(self.config['run_argv']),cwd=self.config.get('cwd'),
            config_sha256=hashlib.sha256(e.encoded(self.config)).hexdigest())
        if options.get('experiment_directory') is not None:
            root=Path(options['experiment_directory']).absolute()
            if root.resolve()!=root or not root.is_dir() or self.records.root.is_relative_to(root):
                raise ValueError('Explicit original experiment directory must exclude execution records')
            source=Path(payload.local_path)
            if not source.is_relative_to(root) or source.relative_to(root).parts[0]=='artifacts':
                raise ValueError('Script must belong to the experiment input directory')
            metadata.update(experiment_directory=str(root),entry=source.relative_to(root).as_posix(),
                snapshot_files=self.files(root,exclude_artifacts=True))
            entry=next(item for item in metadata['snapshot_files'] if item['name']==metadata['entry'])
            if entry['sha256']!=payload.sha256 or entry['size_bytes']!=payload.size_bytes:
                raise e.IntegrityError('Experiment script changed during preparation')
            metadata['cwd']=str(self.records.root/'calls'/payload.name/'inputs')
        snapshot=self.records.root/'calls'/payload.name
        metadata['command'][metadata['script_index']]=str(snapshot/'inputs'/metadata['entry'] if 'entry' in metadata else snapshot/'source.py')
        return metadata

    @staticmethod
    def files(root,*,exclude_artifacts=False):
        if root.resolve()!=root or not root.is_dir():
            raise ValueError('Managed files require an original directory')
        files=[];total=0;scanned=0;pending=[root]
        while pending:
            directory=pending.pop()
            if directory.resolve()!=directory or not directory.is_dir():
                raise ValueError('Managed directories must remain original')
            with os.scandir(directory) as entries:
                for entry in entries:
                    if exclude_artifacts and directory==root and entry.name=='artifacts':
                        if not entry.is_dir(follow_symlinks=False):
                            raise ValueError('Managed artifacts output must be an original directory')
                        continue
                    scanned+=1
                    if scanned>MAX_SCAN_ENTRIES:
                        raise ValueError('Managed directory entry capacity exceeded')
                    path=Path(entry.path);name=path.relative_to(root).as_posix()
                    if entry.is_symlink():raise ValueError('Managed directories cannot contain links')
                    if len(name.encode())>512:raise ValueError('Managed file path capacity exceeded')
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(path);continue
                    item=e.proof(path);total+=item['size_bytes']
                    files.append(dict(item,name=name))
                    if len(files)>e.MAX_INPUT_FILES or total>e.MAX_INPUT_BYTES:
                        raise ValueError('Managed file capacity exceeded')
        return sorted(files,key=lambda item:item['name'])

    def dispatch_lease(self,accepted):
        if accepted['scope']!=self.config['scope']:
            raise e.IntegrityError('Dispatch lease differs from exact frozen scope')
        self._lease=(accepted['call_id'],accepted['prepared'])

    def lookup_submission(self,submission):
        path=self.records.root/'calls'/submission.name/'accepted.json'
        if not path.exists():return None
        accepted=self.records.accepted(submission.name)
        if accepted['prepared']!=submission.model_dump(mode='json'):
            raise e.IntegrityError('Original submission differs from prepared input')
        return submission.name,self._state(submission.name)

    def submit(self,submission):
        found=self.lookup_submission(submission)
        if self._lease!=(submission.name,submission.model_dump(mode='json')):
            if found is not None:return found
            raise e.UnsupportedExecution('No exact accepted dispatch lease; submission is not permitted')
        self._lease=None
        if found is None:raise e.IntegrityError('Dispatch has no durable acceptance original')
        directory=self.records.directory(submission.name)
        if (directory/'process.json').exists() or (directory/'terminal.json').exists():return found
        accepted=json.loads(e.read(directory/'accepted.json'))
        self._execute(submission.name,accepted)
        return submission.name,self._state(submission.name)

    def command(self,accepted):
        # Execute the exact control snapshot. cwd is separately configured;
        # imports/environment beyond this one payload are not frozen evidence.
        command=list(accepted['command']);directory=self.records.directory(accepted['call_id'])
        command[accepted.get('script_index',len(command)-1)]=str(directory/'inputs'/accepted['entry'] if 'entry' in accepted else directory/'source.py')
        return command

    def _state(self,call_id):
        from . import runtime
        directory=self.records.directory(call_id);accepted=self.records.accepted(call_id)
        path=directory/'process.json'
        identity=None
        if path.exists():
            identity=json.loads(e.read(path))
            key=e.hashlib.sha256(e.encoded(accepted)).hexdigest()
            if (not isinstance(identity,dict) or identity.get('task_sha256')!=key
                    or any(type(identity.get(field)) is not int or identity[field]<=0
                           for field in ('pid','start_ticks','pgid','sid'))):
                raise e.IntegrityError('Original local process identity is malformed or changed')
        if (directory/'completed.json').exists():
            state=self.records.state(call_id)
            if state=='unknown':return state
            terminal=json.loads(e.read(directory/'terminal.json'))
            if (not isinstance(terminal,dict) or terminal.get('cleanup_confirmed') is not True
                    or terminal.get('transport_complete') is not True or type(terminal.get('returncode')) is not int):
                return 'unknown'
            if state!=('succeeded' if terminal['returncode']==0 else 'failed'):
                raise e.IntegrityError('Completed local execution differs from its transport')
            return state
        return 'running' if identity and runtime.process_matches(identity,identity['task_sha256']) else 'unknown'

    def _execute(self,call_id,accepted):
        from . import runtime
        directory=self.records.directory(call_id)
        runtime._subreaper()
        started=time.monotonic()
        transport_complete=True;cleanup=False;returncode=None
        cwd=accepted.get('cwd')
        if 'entry' in accepted:
            cwd=str(directory/'inputs');(Path(cwd)/'artifacts').mkdir()
        with (directory/'stdout.raw').open('xb') as out,(directory/'stderr.raw').open('xb') as err:
            process=subprocess.Popen(self.command(accepted),cwd=cwd,stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,start_new_session=True)
            identity=runtime.process_identity(process.pid,hashlib.sha256(e.encoded(accepted)).hexdigest())
            self.records.publish(call_id,'process.json',identity)
            seconds=self.config['max_seconds']
            deadline=time.monotonic()+seconds
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout,selectors.EVENT_READ);selector.register(process.stderr,selectors.EVENT_READ)
                count=0
                while selector.get_map() or process.poll() is None:
                    for key,_ in selector.select(.1):
                        chunk=os.read(key.fileobj.fileno(),65536)
                        if not chunk:selector.unregister(key.fileobj);continue
                        count+=len(chunk)
                        if count>e.MAX_BYTES:transport_complete=False;break
                        sink=out if key.fileobj is process.stdout else err;sink.write(chunk);sink.flush()
                    if count>e.MAX_BYTES or time.monotonic()>=deadline:
                        transport_complete=False
                        if runtime.process_matches(identity,identity['task_sha256']):os.killpg(identity['pgid'],signal.SIGTERM)
                        break
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if runtime.process_matches(identity,identity['task_sha256']):os.killpg(identity['pgid'],signal.SIGKILL)
                process.wait(timeout=5)
            cleanup=runtime.cleanup_owned_group(identity)=='observed_group_cleaned'
            returncode=process.returncode
            process.stdout.close();process.stderr.close()
        self.records.publish(call_id,'terminal.json',dict(returncode=returncode,cleanup_confirmed=cleanup,
            transport_complete=transport_complete,wall_seconds=time.monotonic()-started))
        self.records.publish(call_id,'completed.json',self.completion(directory,accepted,returncode,cleanup,transport_complete))

    def completion(self,directory,accepted,returncode,cleanup,transport_complete):
        known=cleanup and transport_complete and type(returncode) is int
        original=dict(call_id=accepted['call_id'],status=('known_success' if returncode==0 else 'known_failed') if known else 'unknown',
            candidate_id=None,run_id=None,model=None,parent=accepted['parent'],change_intent=None,scope=accepted['scope'],
            proofs=[e.proof(directory/name) for name in ('accepted.json','source.py','process.json','stdout.raw','stderr.raw','terminal.json')],
            note='Original local command outcome; no domain metric or candidate qualification')
        if accepted.get('local_observation_version')!=1:return original
        outputs=[];result=dict(status='not_requested',metrics=[],outputs=[])
        if 'entry' in accepted:
            if not cleanup:
                result=dict(status='unavailable',metrics=[],outputs=[],diagnostic='execution_cleanup_unknown')
            else:
                try:
                    for item in self.files(directory/'inputs/artifacts'):
                        source=Path(item['path']);target=directory/'outputs'/item['name']
                        target.parent.mkdir(parents=True,exist_ok=True)
                        shutil.copyfile(source,target);target.chmod(0o400)
                        frozen=e.proof(target)
                        if frozen['sha256']!=item['sha256']:raise e.IntegrityError('Managed output changed during collection')
                        outputs.append(dict(frozen,name=item['name']))
                    result=self.read_result(directory/'outputs',outputs)
                except (OSError,ValueError) as error:
                    result=dict(status='unavailable',metrics=[],outputs=[],diagnostic='managed_output_io' if isinstance(error,OSError) else 'managed_output_invalid')
        terminal=json.loads(e.read(directory/'terminal.json'))
        completed=dict(original,
            outputs=outputs,result=result,wall_seconds=terminal.get('wall_seconds'),returncode=returncode,
            note='Observed local command and declared results; external imports/environment and scientific validity are not qualified')
        if len(e.encoded(completed))>e.MAX_BYTES:
            retained=[item for item in outputs if item['name']=='result.json']
            completed.update(outputs=retained,result=dict(status='unavailable',metrics=[],outputs=[],
                diagnostic='managed_output_metadata_capacity',outputs_omitted_count=len(outputs)-len(retained)))
        return completed

    @staticmethod
    def read_result(directory,outputs):
        path=directory/'result.json'
        if not path.exists():return dict(status='missing',metrics=[],outputs=[])
        try:
            value=json.loads(e.read(path,64_000))
            if (not isinstance(value,dict) or set(value)-{'candidate'}!={'version','metrics','outputs'}
                    or type(value['version']) is not int or value['version']!=1
                    or not isinstance(value['metrics'],list) or len(value['metrics'])>32
                    or not isinstance(value['outputs'],list) or len(value['outputs'])>128):
                raise ValueError('Expected version 1 metrics and outputs')
            seen=set()
            for metric in value['metrics']:
                if (not isinstance(metric,dict) or set(metric)-{'name','value','unit','evaluation_key','direction'}
                        or not {'name','value'}<=set(metric) or not isinstance(metric['name'],str) or not 0<len(metric['name'].encode())<=160
                        or metric['name'] in seen or type(metric['value']) not in (int,float) or not math.isfinite(metric['value'])
                        or metric.get('direction') is not None and (not isinstance(metric['direction'],str) or metric['direction'] not in ('min','max'))
                        or any(metric.get(key) is not None and (not isinstance(metric[key],str) or not 0<len(metric[key].encode())<=512)
                            for key in ('unit','evaluation_key'))):
                    raise ValueError('Metrics require distinct names and explicit finite values')
                seen.add(metric['name'])
            names={'artifacts/'+item['name'] for item in outputs}
            seen=set()
            for item in value['outputs']:
                if (not isinstance(item,dict) or set(item)!={'path','label'} or not isinstance(item['path'],str)
                        or item['path'] not in names or item['path'] in seen
                        or not isinstance(item['label'],str) or not 0<len(item['label'].encode())<=160):
                    raise ValueError('Result outputs require unique retained artifacts paths and labels')
                seen.add(item['path'])
            if 'candidate' in value:
                candidate=value['candidate']
                if (not isinstance(candidate,dict) or set(candidate)!={'label','metric','artifact'}
                        or not isinstance(candidate['label'],str) or not 0<len(candidate['label'].encode())<=160
                        or not isinstance(candidate['metric'],str) or not isinstance(candidate['artifact'],str)
                        or candidate['metric'] not in {item['name'] for item in value['metrics']
                            if item.get('evaluation_key') and item.get('direction')}
                        or candidate['artifact'] not in {item['path'] for item in value['outputs']}):
                    raise ValueError('Candidate requires an explicit comparable metric and declared artifact')
            return dict(status='available',metrics=value['metrics'],outputs=value['outputs'],
                **(dict(candidate=value['candidate']) if 'candidate' in value else {}))
        except (OSError,ValueError,OverflowError,RecursionError) as error:
            return dict(status='invalid',metrics=[],outputs=[],diagnostic='result_io' if isinstance(error,OSError) else 'result_json_invalid')

    def result(self,call_id):
        directory=self.records.directory(call_id)
        path=directory/'completed.json'
        if not path.exists():return dict(status='unknown',call_id=call_id,note='Original execution has no confirmed completion')
        result=json.loads(e.read(path))
        if result['call_id']!=call_id or result['scope']!=self.config['scope']:
            raise e.IntegrityError('Completed execution binding changed')
        accepted=self.records.accepted(call_id)
        if result.get('mechanism_binding')!=accepted.get('mechanism_binding'):
            raise e.IntegrityError('Completed scientific mechanism binding changed')
        for item in result['proofs']:
            if e.proof(item['path'])!=item:raise e.IntegrityError('Completed execution original changed')
        for item in result.get('outputs',[]):
            if e.proof(item['path'])!={key:item[key] for key in ('path','sha256','size_bytes')}:
                raise e.IntegrityError('Completed output original changed')
        for item in accepted.get('snapshot_files',[]):
            original=e.proof(directory/'inputs'/item['name'])
            if any(original[key]!=item[key] for key in ('sha256','size_bytes')):
                raise e.IntegrityError('Accepted input snapshot changed')
        return result

    def status(self,external_run_id):
        return self._state(external_run_id)

    def status_details(self,external_run_id):
        state=self._state(external_run_id)
        result={}
        if state in {'succeeded','failed'}:
            result=self.result(external_run_id)
            if result['status']=='unknown':state='unknown'
        return dict(state=state,call_id=external_run_id,candidate_id=None,evaluation_key=None,metric=None,
            direction=None,wall_seconds=result.get('wall_seconds'),returncode=result.get('returncode'),
            result=result.get('result'),parent_candidate=None)

    def cancel(self,external_run_id):
        raise e.UnsupportedExecution('Original command cancellation is not declared')

    def cancel_original(self,call_id):
        external=self.records.external(call_id)
        if external is None:raise e.UnsupportedExecution('Original external execution is unknown')
        return self.cancel(external)

    def collect_original(self,call_id):
        external=self.records.external(call_id)
        if external is None:raise e.UnsupportedExecution('Original external execution is unknown')
        return self.collect(external)

    def collect(self,external_run_id):
        if self.status(external_run_id) not in {'succeeded','failed'}:
            raise e.UnsupportedExecution('Original command is not confirmed terminal')
        result=self.result(external_run_id)
        directory=self.records.directory(external_run_id)
        paths=[directory/name for name in ('stdout.raw','stderr.raw')]+[Path(item['path']) for item in result.get('outputs',[])]
        return tuple(LocalFileDescriptor(name=f'output-{index}',local_path=str(path),
            sha256=e.proof(path)['sha256'],size_bytes=path.stat().st_size,
            media_type='application/octet-stream') for index,path in enumerate(paths))

    @staticmethod
    def public_result(result):
        return {key:result[key] for key in ('call_id','status','note','returncode','wall_seconds','result') if key in result}


def build(context):
    return RuntimePluginContribution(execution_adapters={'command':LocalExecution(json.loads(context.config_bytes))})


REGISTRATION=ExecutionInterfaceRegistration('local_execution','1',RuntimePluginFactory(build))


def cleanup(root,job,*,watchdog=False):
    """Clean only this native owner's accepted local groups; never replay calls."""
    from . import contracts as c, execution, protocol, runtime
    if job.get('experiment_mode')!='local' or job['role']!='W':return 'not_applicable'
    path=execution.record(root,job['step'])/'experiment-config.json'
    if not path.exists():return 'not_configured'
    config=c.read(c.regular(path));e.load(config,path=path)
    if config['scope']!=protocol.stage_scope(root,job) or config['execution_interface']['executor']!='local_execution:command':
        raise e.IntegrityError('Local cleanup escaped its frozen native owner')
    result='observed_group_cleaned'
    records=e.Records(config)
    for directory in records.calls():
        accepted=records.accepted(directory.name)
        if accepted.get('local_observation_version')!=1:raise e.IntegrityError('Local cleanup original differs')
        terminal=directory/'terminal.json'
        if terminal.exists():
            value=json.loads(e.read(terminal))
            if value.get('call_id')!=directory.name or value.get('scope')!=config['scope']:
                raise e.IntegrityError('Local terminal owner differs')
            if value.get('cleanup_confirmed') is True:continue
        process=directory/'process.json'
        if not process.exists():result='cleanup_unknown';continue
        identity=json.loads(e.read(process));key=hashlib.sha256(e.encoded(accepted)).hexdigest()
        if identity.get('task_sha256')!=key or identity.get('pgid')!=identity.get('pid') or identity.get('sid')!=identity.get('pid'):
            raise e.IntegrityError('Local cleanup process binding differs')
        status=runtime.signal_observed_group(identity) if watchdog else runtime.cleanup_owned_group(identity)
        if status!='observed_group_cleaned':result='cleanup_unknown'
    return result
