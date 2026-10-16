"""Synthetic registered opaque/async execution contract fixture; no remote service."""
import json
from pathlib import Path
from scidiscovery.research_loop import experiments as e
from scidiscovery.operations.execution import ExecutionInterfaceRegistration, LifecycleCapabilities, LocalFileDescriptor
from scidiscovery.operations.runtime_plugins import RuntimePluginContribution, RuntimePluginFactory


class Remote:
    def __init__(self, config):
        self.config = config
        self.records = e.Records(config)
        self.accepted = None
    @property
    def result_protocol(self): return self.config.get('result_protocol')
    def lifecycle_capabilities(self):
        return LifecycleCapabilities(lookup_submission=True, query=True, collect=self.config.get('collect', True), atomic_admission=True)
    def capabilities(self): return ()
    def code_assets(self): return [__file__]
    def prepare(self, payload, **kwargs): return payload
    def acceptance_metadata(self, payload, **kwargs): return dict(parent=dict(candidate_id=None), change_intent=None)
    def dispatch_lease(self, accepted): self.accepted = accepted
    def lookup_submission(self, descriptor):
        if not (self.records.directory(descriptor.name) / 'backend-accepted.json').exists(): return None
        return 'remote-' + descriptor.name, self.status_details(descriptor.name)['state']
    def submit(self, descriptor):
        assert self.accepted['call_id'] == descriptor.name
        e.write(self.records.directory(descriptor.name) / 'backend-accepted.json', dict(external_run_id='remote-' + descriptor.name))
        if self.config.get('synchronous') or self.config.get('synchronous_first') and len(self.records.calls())==1: self.complete(descriptor.name)
        return 'remote-' + descriptor.name, self.status_details(descriptor.name)['state']
    def complete(self, call):
        accepted = self.records.accepted(call)
        directory = self.records.directory(call)
        e.write(directory / 'backend-terminal.json', dict(call_id=call, scope=accepted['scope'], status=self.config.get('terminal_status','known_success'),native_payload='retained-native-terminal-only'))
        value = dict(status=self.config.get('terminal_status','known_success'), proofs=[e.proof(directory / 'backend-terminal.json')], note='Synthetic backend terminal')
        private = self.config.get('private')
        if private == 'native':
            value['result'] = dict(status='available', metrics=[], candidate=dict(native_model_id='opaque-model-1'))
        elif private == 'local-like':
            value['result'] = dict(status='available', metrics=[dict(name='quality', value=1.0, evaluation_key='backend/public', direction='max')],
                candidate=dict(label='native-model', metric='quality', artifact='artifacts/model.bin'),
                outputs=[dict(path='artifacts/model.bin', label='Backend native output')])
        self.records.publish(call, 'completed.json', value)
    def result(self, call):
        path = self.records.directory(call) / 'completed.json'
        if not path.exists(): return dict(call_id=call, status='unknown', note='Accepted backend task still running')
        value = json.loads(e.read(path))
        terminal = json.loads(e.read(self.records.directory(call) / 'backend-terminal.json'))
        if (terminal['call_id'] != call or terminal['scope'] != self.config['scope'] or terminal['status'] != value['status']
            or ((self.records.directory(call)/'submission.json').exists() and self.records.external(call) != json.loads(e.read(self.records.directory(call)/'backend-accepted.json'))['external_run_id'])):
            raise e.IntegrityError('Original backend terminal binding changed')
        for proof in value['proofs']:
            if e.proof(proof['path']) != proof:raise e.IntegrityError('Original backend terminal proof changed')
        return value
    def status_details(self, call):
        if (self.records.root/'forbid-backend-reads').exists():raise e.IntegrityError('Fixture forbids another native query')
        value = self.result(call)
        return dict(state={'known_success':'succeeded','known_failed':'failed'}.get(value['status'],self.config.get('query_state','running')), call_id=call)
    def status(self, external): return self.status_details(external.removeprefix('remote-'))['state']
    def collect(self, external):
        if not self.config.get('collect', True): raise e.UnsupportedExecution('Backend does not declare collection')
        call = external.removeprefix('remote-')
        assert self.status(external) in {'succeeded','failed'}
        path = self.records.directory(call) / 'source.py'
        proof = e.proof(path)
        return (LocalFileDescriptor(name='original', local_path=str(path), sha256=proof['sha256'], size_bytes=proof['size_bytes'], media_type='application/octet-stream'),)
    def collect_original(self, call): return self.collect(self.records.external(call))
    def cancel(self, external): raise e.UnsupportedExecution('Cancellation is not declared')
    def cancel_original(self, call): return self.cancel(self.records.external(call))
    def public_result(self, result): return {key: result[key] for key in ('call_id', 'status', 'note')}


def factory(context):
    return RuntimePluginContribution(execution_adapters={'fixture': Remote(json.loads(context.config_bytes))})


REGISTRATION = ExecutionInterfaceRegistration('composed_execution', '1', RuntimePluginFactory(factory))
