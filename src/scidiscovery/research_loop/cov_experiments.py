"""Cov public experiment implementation of the registered lifecycle contract."""
import json
import os
from pathlib import Path
import time

from scidiscovery.operations.execution import AdapterCapability, ExecutionInterfaceRegistration
from scidiscovery.operations.runtime_plugins import RuntimePluginContribution, RuntimePluginFactory
from .local_experiments import LocalExecution
from . import cov_lineage as cov, experiments as e, cov_receipt


class CovExecution(LocalExecution):
    @staticmethod
    def code_assets():
        from . import local_experiments, cov_delivery, delivery
        return [*LocalExecution.code_assets(),cov.__file__,local_experiments.__file__,cov_receipt.__file__,
            cov_delivery.__file__,delivery.__file__]

    def capabilities(self):
        original = super().capabilities()
        if self.config.get('receipt_channel') != 'public_runner_main':
            return original
        policy = dict(max_seconds=10, feedback_seconds=2,
            check_scope=dict(source='exact accepted source.py',
                inputs='exact accepted public runner/train.csv/val.csv/meta.json and task runtime',
                selection='first rows in frozen CSV order', train_rows_max=32, validation_rows_max=8,
                coverage='source import, one sampled train() call and sampled predict; installed runtime dependencies only',
                limitation='Unexecuted paths, full-data training and public audit are untested. Installed libraries are shared, not individually frozen. Pre-acceptance input hash/copy costs belong to the original task, outside this diagnostic ceiling; no scientific qualification.'))
        return (*original, AdapterCapability('isolated_replay', 'engineering', 'scidiscovery.engineering-replay.v1', 1,
            'application/json', e.encoded(policy), policy['check_scope']))

    def _replay_inputs(self, transport):
        """Freeze only the known public harness layout before the original call."""
        from . import protocol
        parent = Path(transport['runner']['path']).parent
        files = []
        for name in ('runner.py', 'train.csv', 'val.csv', 'meta.json'):
            path = parent / name
            environment = {'runner.py':'EXP_RUNNER', 'train.csv':'EXP_TRAIN',
                'val.csv':'EXP_VAL', 'meta.json':'EXP_META'}[name]
            if Path(os.environ.get(environment, str(path))).absolute() != path:
                raise ValueError('Public replay input mapping is not the declared harness layout')
            item = cov_receipt.original(path)
            if name == 'runner.py' and any(item[key] != transport['runner'][key] for key in item):
                raise e.IntegrityError('Public replay runner differs from accepted receipt producer')
            files.append(dict(item, name='replay/harness/' + name))
        files.append(dict(cov_receipt.original(Path(protocol.__file__).resolve()), name='replay/scid-current-protocol'))
        invoked = Path(self.config['run_argv'][0]).absolute()
        runtime = dict(cov_receipt.original(invoked.resolve()), invoked_path=str(invoked))
        return files, runtime

    def acceptance_metadata(self,payload,*,parent=None,new=False,change=None):
        channel=self.config.get('receipt_channel')
        if channel not in {'public_runner_main','backend_file'}:
            raise e.UnsupportedExecution('Cov execution needs an explicit independent receipt channel; preserved calls remain read-only')
        selected,binding=cov._parent(self.config,parent,new)
        transport = cov_receipt.profile(self.config['run_argv'],channel)
        metadata = dict(parent=selected,parent_binding=binding,change_intent=change,runs_root=self.config['runs_root'],
            command=[*self.config['run_argv'],'run','--script',payload.local_path],cwd=None,
            receipt_transport=transport, config_sha256=e.hashlib.sha256(e.encoded(self.config)).hexdigest())
        if channel == 'public_runner_main':
            try:
                metadata['snapshot_files'], metadata['replay_runtime'] = self._replay_inputs(transport)
            except (OSError, ValueError):
                metadata['replay_inputs_unavailable'] = True
        return metadata

    def replay_check(self, call_id, *, deadline_boottime, on_process):
        """No new time grant: preparation and execution share one absolute bound."""
        from . import contracts as c, cov_delivery, delivery
        directory = self.records.directory(call_id)
        accepted = self.records.accepted(call_id)
        if accepted.get('replay_inputs_unavailable') or 'replay_runtime' not in accepted:
            return dict(status='unsupported', note='exact_public_replay_inputs_unavailable', cleanup_confirmed=True)

        def check():
            if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline_boottime:
                raise TimeoutError('Original engineering preparation deadline reached')

        def link(source, destination, proof):
            # Both sources are existing accepted call snapshots. The leaf will
            # stream-verify their hashes within this same absolute deadline.
            check()
            if source.resolve() != source:raise e.IntegrityError('Replay snapshot path changed')
            original = c.regular(source).stat()
            if original.st_size != proof['size_bytes']:raise e.IntegrityError('Replay snapshot size changed')
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.link(source, destination, follow_symlinks=False)
            linked = destination.lstat()
            if destination.is_symlink() or (linked.st_dev, linked.st_ino) != (original.st_dev, original.st_ino):
                raise e.IntegrityError('Replay snapshot link changed')
            check()

        try:
            check()
            # complete() already verified the original observation and these
            # small bindings; do not hash every model/log a second time here.
            completed = json.loads(e.read(directory / 'completed.json'))
            runtime = accepted['replay_runtime']
            operation = e.proof(directory / 'accepted.json')['sha256']
            spec = dict(adapter=str(Path(cov_delivery.__file__).resolve()),
                launcher_argv=[runtime['invoked_path'], str(Path(cov_delivery.__file__).resolve()), '--isolate'])
            stage = directory / 'engineering-replay'
            stage.mkdir()
            (stage / 'inputs/harness').mkdir(parents=True)
            (stage / 'scratch').mkdir()
            objects = {'source.py': accepted['script']['sha256']}
            link(directory / 'source.py', stage / 'inputs/source.py', accepted['script'])
            inputs = [dict(runtime, label='runtime-python')]
            for item in accepted['snapshot_files']:
                label = item['name'].removeprefix('replay/')
                link(directory / 'inputs' / item['name'], stage / 'inputs' / label, item)
                objects[label] = item['sha256']
                inputs.append(dict(item, label=label))
            request = dict(phase='replay', scope=accepted['scope'], operation_id=operation,
                candidate_id=completed['candidate_id'], artifact_sha256=completed['model']['sha256'],
                deadline_boottime=deadline_boottime, object_digests=objects, inputs=inputs,
                config=dict(python=runtime['invoked_path']), stage=str(stage))
            check()
        except TimeoutError:
            return dict(status='not_run', note='original_engineering_preparation_deadline_reached', cleanup_confirmed=True)
        started = False
        def process(phase, identity):
            nonlocal started
            started = True
            on_process(phase, identity)
        try:
            value = delivery._call(spec, request, deadline_boottime - time.clock_gettime(time.CLOCK_BOOTTIME),
                on_process=process, evidence=directory / 'engineering-diagnostics')
        except delivery.DeliveryUnresolved as error:
            return dict(status='unknown', note=error.code, cleanup_confirmed=False)
        # Raw diagnostics stay in the persistent call stage. A deadline never
        # licenses another complete copy/hash just to produce the small view.
        leaf_record = {}
        leaf = stage / 'scratch/replay.json'
        if time.clock_gettime(time.CLOCK_BOOTTIME) < deadline_boottime:
            try:
                if c.regular(leaf).stat().st_size <= 16_000:
                    leaf_record = json.loads(e.read(leaf))
            except (OSError, ValueError):
                pass
        diagnostics = []
        for name in ('replay.stdout', 'replay.stderr', 'replay.json'):
            path = stage / 'scratch' / name
            if path.exists():
                c.regular(path).chmod(0o400)
                proof = dict(path=str(path), size_bytes=path.stat().st_size, sha256=None)
                try:proof['sha256'] = cov_delivery._sha(path, deadline=deadline_boottime)
                except TimeoutError:proof['retention'] = 'original_unhashed_deadline_reached'
                diagnostics.append(proof)
        if value is None:
            return dict(status='inconclusive' if started else 'not_run', note='check_did_not_complete', cleanup_confirmed=True,
                samples=leaf_record.get('samples'), stage=leaf_record.get('stage'), diagnostic_originals=diagnostics,
                completion='Timeout or failed leaf; bounded execution did not produce a verified result.')
        if (not isinstance(value, dict) or any(value.get(key) != request[key]
                for key in ('operation_id', 'candidate_id', 'artifact_sha256'))
                or value.get('status') not in {'sample_replay_ok', 'dependency_error', 'inconclusive'}):
            return dict(status='unknown', note='invalid_sample_replay_result', cleanup_confirmed=True)
        return {key: value[key] for key in ('status', 'note', 'diagnostic', 'diagnostic_omitted_bytes', 'samples', 'stage')} | dict(
            cleanup_confirmed=True, diagnostic_originals=diagnostics)

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
        # The task interpreter retains its scientific libraries and permissions.
        # Only cov's stdout/receipt separation changes; generic execution is shared.
        return [self.config['run_argv'][0],'-I',str(Path(cov_receipt.__file__).resolve()),
            str(self.records.directory(accepted['call_id'])/'accepted.json')]

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
