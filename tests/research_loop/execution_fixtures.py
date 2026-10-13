"""Source discovery metadata only; installed checks use the wheel's real entries."""
import importlib.metadata
import os
from pathlib import Path
import pytest


@pytest.fixture(autouse=True)
def execution_registry(tmp_path,monkeypatch):
    if list(importlib.metadata.entry_points().select(group='scidiscovery.execution_interfaces')):
        return None
    metadata=tmp_path/'discovery/scidiscovery_execution_source.dist-info'
    metadata.mkdir(parents=True)
    (metadata/'METADATA').write_text('Metadata-Version: 2.1\nName: scidiscovery-execution-source\nVersion: 0\n')
    (metadata/'entry_points.txt').write_text('[scidiscovery.execution_interfaces]\n'
        'local_execution = scidiscovery.research_loop.local_experiments:REGISTRATION\n'
        'cov_execution = scidiscovery.research_loop.cov_experiments:REGISTRATION\n')
    root=str(metadata.parent)
    monkeypatch.syspath_prepend(root)
    monkeypatch.setenv('PYTHONPATH',root+os.pathsep+os.environ.get('PYTHONPATH',''))
    return metadata.parent


# Contract fixture only: no solver, native process or scientific result claim.
from scidiscovery.operations.execution import ExecutionInterfaceRegistration, LifecycleCapabilities, LocalFileDescriptor
from scidiscovery.operations.runtime_plugins import RuntimePluginContribution, RuntimePluginFactory
from scidiscovery.research_loop import experiments as e
import json


class DifferentExternalIdentity:
    def __init__(self,config):self.records=e.Records(config);self.config=config;self.accepted=None
    def lifecycle_capabilities(self):return LifecycleCapabilities(lookup_submission=True,query=True,collect=True,atomic_admission=True)
    def capabilities(self):return ()
    def code_assets(self):return [__file__]
    def prepare(self,payload,**options):return payload
    def acceptance_metadata(self,payload,**options):return dict(parent=dict(candidate_id=None),change_intent=None)
    def dispatch_lease(self,accepted):self.accepted=accepted
    def submit(self,descriptor):
        call=descriptor.name
        found=self.lookup_submission(descriptor)
        if found:return found
        assert self.accepted['call_id']==call
        self.records.publish(call,'completed.json',dict(call_id=call,scope=self.config['scope'],status='known_success',
            proofs=[e.proof(self.records.directory(call)/'accepted.json')],note='Synthetic external identity contract fixture'))
        return 'remote-'+call,'succeeded'
    def lookup_submission(self,descriptor):
        if not (self.records.root/'calls'/descriptor.name/'completed.json').exists():return None
        assert self.records.accepted(descriptor.name)['prepared']==descriptor.model_dump(mode='json')
        return 'remote-'+descriptor.name,'succeeded'
    def status(self,external_run_id):
        assert external_run_id.startswith('remote-')
        return self.records.state(external_run_id.removeprefix('remote-'))
    def status_details(self,call_id):return dict(state=self.records.state(call_id),call_id=call_id)
    def result(self,call_id):return json.loads(e.read(self.records.directory(call_id)/'completed.json'))
    def public_result(self,result):return {key:result[key] for key in ('call_id','status','note')}
    def cancel(self,external_run_id):raise e.UnsupportedExecution('Fixture cancellation unavailable')
    def cancel_original(self,call_id):return self.cancel(self.records.external(call_id))
    def collect(self,external_run_id):
        assert external_run_id.startswith('remote-')
        path=self.records.directory(external_run_id.removeprefix('remote-'))/'source.py';item=e.proof(path)
        return (LocalFileDescriptor(name='original',local_path=str(path),sha256=item['sha256'],
            size_bytes=item['size_bytes'],media_type='application/octet-stream'),)
    def collect_original(self,call_id):return self.collect(self.records.external(call_id))


def remote_factory(context):
    return RuntimePluginContribution(execution_adapters={'fixture':DifferentExternalIdentity(json.loads(context.config_bytes))})


REMOTE_REGISTRATION=ExecutionInterfaceRegistration('remote_execution','1',RuntimePluginFactory(remote_factory))


@pytest.fixture
def remote_registry(tmp_path,monkeypatch,execution_registry):
    metadata=tmp_path/'remote-discovery/remote_execution_contract.dist-info';metadata.mkdir(parents=True)
    (metadata/'METADATA').write_text('Metadata-Version: 2.1\nName: remote-execution-contract\nVersion: 0\n')
    (metadata/'entry_points.txt').write_text('[scidiscovery.execution_interfaces]\nremote_execution = execution_fixtures:REMOTE_REGISTRATION\n')
    monkeypatch.syspath_prepend(str(metadata.parent))
    monkeypatch.setenv('PYTHONPATH',str(metadata.parent)+os.pathsep+str(Path(__file__).parent)+os.pathsep+os.environ.get('PYTHONPATH',''))
