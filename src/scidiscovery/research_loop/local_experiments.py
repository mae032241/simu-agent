"""Ordinary local scientific commands under the caller's native permissions."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time

from scidiscovery.operations.execution import (AdapterCapability, ExecutionInterfaceRegistration,
    LifecycleCapabilities, LocalFileDescriptor)
from scidiscovery.operations.runtime_plugins import RuntimePluginContribution, RuntimePluginFactory
from . import experiments as e


class LocalExecution:
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

    def acceptance_metadata(self,payload,*,parent=None,new=False,change=None):
        if parent is not None or change is not None:
            raise ValueError('This implementation does not declare candidate parent semantics')
        return dict(parent=dict(status='unknown',candidate_id=None,source='none'),change_intent=None,
            command=[*self.config['run_argv'],payload.local_path],cwd=self.config.get('cwd'),
            config_sha256=hashlib.sha256(e.encoded(self.config)).hexdigest())

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
        return [*accepted['command'][:-1],str(self.records.directory(accepted['call_id'])/'source.py')]

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
        transport_complete=True;cleanup=False;returncode=None
        with (directory/'stdout.raw').open('xb') as out,(directory/'stderr.raw').open('xb') as err:
            process=subprocess.Popen(self.command(accepted),cwd=accepted.get('cwd'),stdout=subprocess.PIPE,
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
            transport_complete=transport_complete))
        self.records.publish(call_id,'completed.json',self.completion(directory,accepted,returncode,cleanup,transport_complete))

    def completion(self,directory,accepted,returncode,cleanup,transport_complete):
        known=cleanup and transport_complete and type(returncode) is int
        return dict(call_id=accepted['call_id'],status=('known_success' if returncode==0 else 'known_failed') if known else 'unknown',
            candidate_id=None,run_id=None,model=None,parent=accepted['parent'],change_intent=None,scope=accepted['scope'],
            proofs=[e.proof(directory/name) for name in ('accepted.json','source.py','process.json','stdout.raw','stderr.raw','terminal.json')],
            note='Original local command outcome; no domain metric or candidate qualification')

    def result(self,call_id):
        directory=self.records.directory(call_id)
        path=directory/'completed.json'
        if not path.exists():return dict(status='unknown',call_id=call_id,note='Original execution has no confirmed completion')
        result=json.loads(e.read(path))
        if result['call_id']!=call_id or result['scope']!=self.config['scope']:
            raise e.IntegrityError('Completed execution binding changed')
        for item in result['proofs']:
            if e.proof(item['path'])!=item:raise e.IntegrityError('Completed execution original changed')
        return result

    def status(self,external_run_id):
        return self._state(external_run_id)

    def status_details(self,external_run_id):
        state=self._state(external_run_id)
        if state in {'succeeded','failed'}:
            result=self.result(external_run_id)
            if result['status']=='unknown':state='unknown'
        return dict(state=state,call_id=external_run_id,candidate_id=None,evaluation_key=None,metric=None,
            direction=None,wall_seconds=None,parent_candidate=None)

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
        self.result(external_run_id)
        directory=self.records.directory(external_run_id)
        return tuple(LocalFileDescriptor(name=name.replace('.','-'),local_path=str(directory/name),
            sha256=e.proof(directory/name)['sha256'],size_bytes=(directory/name).stat().st_size,
            media_type='application/octet-stream') for name in ('stdout.raw','stderr.raw'))

    @staticmethod
    def public_result(result):
        return {key:result[key] for key in ('call_id','status','note') if key in result}


def build(context):
    return RuntimePluginContribution(execution_adapters={'command':LocalExecution(json.loads(context.config_bytes))})


REGISTRATION=ExecutionInterfaceRegistration('local_execution','1',RuntimePluginFactory(build))
