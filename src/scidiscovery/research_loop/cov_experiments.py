"""Cov public experiment implementation of the registered lifecycle contract."""
import json
from pathlib import Path

from scidiscovery.operations.execution import ExecutionInterfaceRegistration
from scidiscovery.operations.runtime_plugins import RuntimePluginContribution, RuntimePluginFactory
from .local_experiments import LocalExecution
from . import cov_lineage as cov, experiments as e


class CovExecution(LocalExecution):
    @staticmethod
    def code_assets():
        from . import local_experiments
        return [*LocalExecution.code_assets(),cov.__file__,local_experiments.__file__]

    def acceptance_metadata(self,payload,*,parent=None,new=False,change=None):
        selected,binding=cov._parent(self.config,parent,new)
        return dict(parent=selected,parent_binding=binding,change_intent=change,runs_root=self.config['runs_root'],
            command=[*self.config['run_argv'],'run','--script',payload.local_path],cwd=None,
            config_sha256=e.hashlib.sha256(e.encoded(self.config)).hexdigest())

    def completion(self,directory,accepted,returncode,cleanup,transport_complete):
        result=cov._receipt(directory,accepted,cov._rows(Path(self.config['runs_root'])/'results.jsonl'),
            returncode,cleanup,transport_complete=transport_complete)
        if result is None:
            result=super().completion(directory,accepted,returncode,cleanup,False)
            result.update(change_intent=accepted['change_intent'],
                proofs=[e.proof(directory/name) for name in ('accepted.json','source.py','stdout.raw','terminal.json')],
                note='No exact completed public receipt; preserve without replay')
        return result

    def command(self,accepted):
        # exp records the source's original path. Preserve that contract and
        # verify exact prepared bytes both before execution and in its receipt.
        if e.proof(accepted['source_script'])['sha256']!=accepted['prepared']['sha256']:
            raise e.IntegrityError('Original cov execution source changed')
        return accepted['command']

    def result(self,call_id):
        result=cov._completed(self.records.directory(call_id))
        return result if result is not None else dict(status='unknown',call_id=call_id,note='Original call has no completion')

    def status_details(self,call_id):
        state=self._state(call_id)
        directory=self.records.directory(call_id)
        result=cov._completed(directory,verify_assets=False)
        accepted=json.loads(e.read(directory/'accepted.json'))
        row=json.loads(e.read(directory/'row.json')) if result and result['status'] in {'known_success','known_failed'} else {}
        if result and result['status']=='unknown':state='unknown'
        return dict(state=state,call_id=call_id,candidate_id=result['candidate_id'] if result else None,
            evaluation_key=self.config['evaluation_key'],metric=row.get('val_score') if cov._finite(row.get('val_score')) else None,
            direction='max',wall_seconds=row.get('wall_seconds') if cov._finite(row.get('wall_seconds')) else None,
            parent_candidate=accepted['parent']['candidate_id'])

    def public_result(self,result):
        return cov.public_feedback(self.config,result,include_model=True) if 'proofs' in result else super().public_result(result)


def build(context):
    return RuntimePluginContribution(execution_adapters={'experiment':CovExecution(json.loads(context.config_bytes))})


REGISTRATION=ExecutionInterfaceRegistration('cov_execution','1',RuntimePluginFactory(build))
