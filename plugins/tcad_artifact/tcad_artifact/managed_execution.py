"""Opaque TCAD transport binding; trusted P3 authority is required for effects."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from scidiscovery.artifact_agent.schema.execution import ExecutionAdmission
from scidiscovery.operations.execution import (
    AdapterCapability, ExecutionInterfaceRegistration, LifecycleCapabilities,
    LocalFileDescriptor, execution_status,
)
from scidiscovery.operations.runtime_plugins import RuntimePluginContribution, RuntimePluginFactory
from scidiscovery.plugin_runtime.collection import CollectionContext
from scidiscovery.research_loop import experiments as e
from scidiscovery.research_loop import contracts as c

from .project_packager import ExecutionPackage, TCADRuntimeManifest, validate_execution_package_json
from .runtime_plugin import TCADRuntimeConfig, build_adapter


def _directory(path):
    path = Path(path).absolute()
    if path.resolve() != path or path.exists() and not path.is_dir():
        raise e.IntegrityError('Exact TCAD original directory required')
    path.mkdir(parents=True, exist_ok=True)
    return path


def _proof(path, context=None):
    path = Path(path)
    if path.resolve() != path or not path.is_file():
        raise e.IntegrityError('Exact TCAD regular original required')
    digest, size = hashlib.sha256(), 0
    with path.open('rb') as source:
        while True:
            if context is not None:
                context.remaining_seconds()
            block = source.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
            size += len(block)
    if context is not None:
        context.remaining_seconds()
    return dict(path=str(path), sha256=digest.hexdigest(), size_bytes=size)


def _verify_descriptor(descriptor, context=None):
    if Path(descriptor.local_path).stat().st_size != descriptor.size_bytes:
        raise e.IntegrityError('TCAD descriptor original size changed')
    original = _proof(descriptor.local_path, context)
    if (original['sha256'], original['size_bytes']) != (descriptor.sha256, descriptor.size_bytes):
        raise e.IntegrityError('TCAD descriptor original changed')
    return original


def _verify_proof(original, context=None):
    if not isinstance(original, dict) or _proof(original['path'], context) != original:
        raise e.IntegrityError('TCAD original proof changed')


def _write_original(path, value):
    if path.exists():
        if json.loads(e.read(path)) != value:
            raise e.IntegrityError('TCAD retained original changed')
    else:
        e.write(path, value)


def _copy_original(descriptor, target, context):
    if target.exists() or target.is_symlink():
        _verify_descriptor(descriptor.model_copy(update={'local_path': str(target)}), context)
        target.chmod(0o440)
        return
    partial = target.with_name('.' + target.name + '.partial')
    if partial.exists() or partial.is_symlink():
        if partial.resolve() != partial or not partial.is_file():
            raise e.IntegrityError('TCAD retention partial is not an original regular file')
        partial.chmod(0o600)
    digest, size = hashlib.sha256(), 0
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW
    with Path(descriptor.local_path).open('rb') as source, os.fdopen(os.open(partial, flags, 0o600), 'wb') as output:
        while True:
            context.remaining_seconds()
            block = source.read(1024 * 1024)
            if not block:
                break
            size += len(block)
            if size > descriptor.size_bytes:
                raise e.IntegrityError('TCAD original exceeds its declared identity')
            digest.update(block)
            output.write(block)
        if (digest.hexdigest(), size) != (descriptor.sha256, descriptor.size_bytes):
            raise e.IntegrityError('TCAD original changed during retention')
        output.flush()
        os.fsync(output.fileno())
    context.remaining_seconds()
    os.chmod(partial, 0o440)
    os.replace(partial, target)


class TCADManagedExecution:
    terminal_evidence_kind = 'adapter_result'
    result_protocol = None

    def __init__(self, config, adapter, *, gate=None, input_metadata=None, open_input=None):
        self.config, self.adapter = config, adapter
        self.records = e.Records(config)
        self.gate = gate
        self.input_metadata, self.open_input = input_metadata, open_input
        self._lease = None
        transport = {key: config[key] for key in TCADRuntimeConfig.model_fields if key in config}
        self.transport = TCADRuntimeConfig.model_validate_json(json.dumps(transport), strict=True)
        assets = []
        if self.transport.command_config_path is not None:
            assets.append(self.transport.command_config_path)
            from .command_adapter import bundled_ssh_configuration
            nested = bundled_ssh_configuration(adapter.config)
            if nested is not None:
                assets.append(str(nested))
        self.target = dict(transport=self.transport.model_dump(mode='json'),
                           configuration_files=[e.proof(path) for path in assets])

    def code_assets(self):
        root = Path(__file__).parent
        names = ('managed_execution.py', 'runtime_plugin.py', 'execution_adapter.py',
                 'command_adapter.py', 'project_packager.py', 'execution_policy.py',
                 'execution_control.py', 'ssh_transport.py', 'transport_logs.py', 'remote_runner_py36.py')
        return [str(root / name) for name in names] + [item['path'] for item in self.target['configuration_files']]

    @staticmethod
    def lifecycle_capabilities():
        return LifecycleCapabilities(lookup_submission=True, query=True, cancel=True,
                                     collect=True, atomic_admission=True)

    def capabilities(self):
        return (AdapterCapability('execution_package', 'execution', 'tcad.execution-package.v2', 2,
            'application/schema+json', e.encoded(ExecutionPackage.model_json_schema(mode='validation')),
            dict(input='Exact TCAD execution package', result_protocol=None,
                 production='blocked_pending_trusted_gate' if self.gate is None else 'trusted_host_gate_required')),)

    def _check(self, phase, call, payload, *, prepared=None, prior=None):
        if self.gate is None:
            raise e.UnsupportedExecution('TCAD production blocked: trusted P3 execution gate is unavailable')
        permit = self.gate(phase, scope=self.config['scope'], call_id=call, payload=payload,
                           target=self.target, prepared=prepared, prior_receipt=prior)
        if not isinstance(permit, dict) or 'receipt' not in permit:
            raise e.IntegrityError('Trusted TCAD gate returned no authority original')
        _verify_proof(permit['receipt'])
        if prior is not None and permit['receipt'] != prior:
            raise e.IntegrityError('TCAD gate changed the original authority binding')
        if phase in {'prepare', 'submit'} and not isinstance(permit.get('authorization'), ExecutionAdmission):
            raise e.IntegrityError('Trusted TCAD gate returned no execution admission')
        if phase in {'prepare', 'submit'} and permit['authorization'].outcome == 'deny':
            raise e.UnsupportedExecution('TCAD execution authority denied the original request')
        if phase == 'collect' and not isinstance(permit.get('context'), CollectionContext):
            raise e.UnsupportedExecution('Original TCAD collection remaining authority is unavailable')
        return permit

    def _stage(self, call):
        if not isinstance(call, str) or not e.ID.fullmatch(call):
            raise ValueError('Exact TCAD call identity required')
        return self.records.root / 'tcad-prepared' / call

    def prepare(self, payload, *, preparation_profile, exchange_directory):
        if preparation_profile != 'research_loop.v1' or Path(exchange_directory) != self.records.root:
            raise ValueError('Exact managed TCAD preparation context required')
        _verify_descriptor(payload)
        reviewed = validate_execution_package_json(Path(payload.local_path).read_bytes())
        # No capability/policy RPC or transport prepare is permitted before this gate.
        permit = self._check('prepare', payload.name, payload)
        if reviewed.resolved_inputs and (self.input_metadata is None or self.open_input is None):
            raise e.UnsupportedExecution('Exact frozen TCAD input originals are unavailable')
        stage = _directory(self._stage(payload.name))
        source = stage / 'package.json'
        c._copy_bound(Path(payload.local_path), source, payload.sha256)
        original = payload.model_copy(update={'local_path': str(source)})
        prepared = self.adapter.prepare(original, preparation_profile='tcad.execution-package.v2',
            exchange_directory=stage, input_metadata=self.input_metadata, open_input=self.open_input)
        prepared = prepared.model_copy(update={'name': payload.name})
        _verify_descriptor(prepared)
        binding = dict(payload=payload.model_dump(mode='json'), retained_payload=original.model_dump(mode='json'),
            prepared=prepared.model_dump(mode='json'),
            target=self.target, authority=permit['receipt'],
            authorization=permit['authorization'].model_dump(mode='json'))
        e.write(stage / 'binding.json', binding)
        os.chmod(stage / 'binding.json', 0o440)
        return prepared

    def _preparation(self, descriptor):
        value = json.loads(e.read(self._stage(descriptor.name) / 'binding.json'))
        if value.get('prepared') != descriptor.model_dump(mode='json') or value.get('target') != self.target:
            raise e.IntegrityError('Original TCAD preparation target or descriptor changed')
        _verify_descriptor(descriptor)
        payload = LocalFileDescriptor.model_validate(value['payload'])
        retained = LocalFileDescriptor.model_validate(value['retained_payload'])
        if retained.model_copy(update={'local_path': payload.local_path}) != payload:
            raise e.IntegrityError('TCAD retained package differs from its original descriptor')
        _verify_descriptor(retained)
        _verify_proof(value['authority'])
        return value

    def acceptance_metadata(self, payload, *, parent=None, new=False, change=None):
        if parent is not None or new or change is not None:
            raise e.UnsupportedExecution('TCAD opaque execution declares no candidate parent semantics')
        return dict(parent=dict(candidate_id=None), change_intent=None, tcad=self._preparation(payload))

    def _bound(self, call):
        accepted = self.records.accepted(call)
        descriptor = LocalFileDescriptor.model_validate(accepted['prepared'])
        if (accepted.get('native_attempt') != self.config.get('native_attempt')
                or accepted.get('interface') != self.config.get('execution_interface')
                or descriptor.name != call
                or accepted['script'].get('path') != str(self.records.directory(call) / 'source.py')
                or (accepted['script'].get('sha256'), accepted['script'].get('size_bytes'))
                    != (descriptor.sha256, descriptor.size_bytes)
                or accepted.get('tcad') != self._preparation(descriptor)):
            raise e.IntegrityError('TCAD call differs from its original acceptance')
        _verify_proof(accepted['script'])
        return accepted, descriptor

    def dispatch_lease(self, accepted):
        original, descriptor = self._bound(accepted['call_id'])
        if original != accepted:
            raise e.IntegrityError('TCAD dispatch acceptance changed')
        if not (self.records.directory(descriptor.name) / 'tcad-dispatch.json').exists():
            self._lease = (descriptor.name, descriptor.model_dump(mode='json'))

    def _binding(self, call, descriptor, external):
        if not isinstance(external, str) or not e.ID.fullmatch(external):
            raise e.IntegrityError('TCAD backend returned no exact execution identity')
        known = self.records.external(call)
        if known is not None and external != known:
            raise e.IntegrityError('TCAD backend changed the original external identity')
        value = dict(call_id=call, scope=self.config['scope'], prepared_sha256=descriptor.sha256,
                     external_run_id=external, target=self.target)
        path = self.records.directory(call) / 'tcad-backend-binding.json'
        with self.records.lease('tcad-binding-' + call + '.lock'):
            if path.exists():
                if json.loads(e.read(path)) != value:
                    raise e.IntegrityError('TCAD backend acceptance binding changed')
            else:
                e.write(path, value)

    def lookup_submission(self, submission):
        _, descriptor = self._bound(submission.name)
        if descriptor != submission:
            raise e.IntegrityError('TCAD lookup differs from the original prepared descriptor')
        found = self.adapter.lookup_submission(descriptor)
        if found is not None:
            self._binding(descriptor.name, descriptor, found[0])
        return found

    def submit(self, submission):
        accepted, descriptor = self._bound(submission.name)
        if submission != descriptor:
            raise e.IntegrityError('TCAD submission differs from accepted preparation')
        found = self.lookup_submission(descriptor)
        if found is not None:
            return found
        directory = self.records.directory(descriptor.name)
        if ((directory / 'tcad-dispatch.json').exists()
                or self._lease != (descriptor.name, descriptor.model_dump(mode='json'))):
            raise e.UnsupportedExecution('TCAD original submission is unknown; lookup without resubmission')
        value = accepted['tcad']
        permit = self._check('submit', descriptor.name, LocalFileDescriptor.model_validate(value['payload']),
                             prepared=descriptor, prior=value['authority'])
        if permit['authorization'].model_dump(mode='json') != value['authorization']:
            raise e.IntegrityError('TCAD execution admission changed after preparation')
        # The exclusive original precedes the uncertain external side effect.
        e.write(directory / 'tcad-dispatch.json', dict(call_id=descriptor.name, scope=self.config['scope'],
            prepared=descriptor.model_dump(mode='json'), authority=permit['receipt']))
        self._lease = None
        try:
            external, state = self.adapter.submit(descriptor, authorization=permit['authorization'])
        except (OSError, RuntimeError) as error:
            raise e.UnsupportedExecution('TCAD submission response is unknown; preserve the original call') from error
        self._binding(descriptor.name, descriptor, external)
        return external, state

    def _query(self, call):
        _, descriptor = self._bound(call)
        external = self.records.external(call)
        if external is None:
            return dict(state='unknown', call_id=call)
        directory = self.records.directory(call)
        if (directory / 'collected.json').exists():
            receipt = json.loads(e.read(directory / 'tcad-terminal-binding.json'))
            if (receipt.get('call_id') != call or receipt.get('scope') != self.config['scope']
                    or receipt.get('prepared_sha256') != descriptor.sha256
                    or receipt.get('external_run_id') != external
                    or execution_status(receipt.get('status', {}).get('state')) not in {'known_success', 'known_failed'}):
                raise e.IntegrityError('TCAD retained terminal binding changed')
            return receipt['status']
        found = self.lookup_submission(descriptor)
        if found is None:
            return dict(state='unknown', call_id=call)
        details = self.adapter.status_details(external)
        if 'run_id' in details and details['run_id'] != external:
            raise e.IntegrityError('TCAD status changed the original external identity')
        return dict(details, call_id=call, external_run_id=external)

    def status_details(self, call):
        path = self.records.directory(call) / 'completed.json'
        if path.exists():
            value = self._completed(call)
            return dict(state=value['native_state'], call_id=call,
                        external_run_id=self.records.external(call))
        return self._query(call)

    def _external_call(self, external):
        matches = [path.name for path in self.records.calls() if self.records.external(path.name) == external]
        if len(matches) != 1:
            raise e.IntegrityError('Exact original TCAD external binding required')
        return matches[0]

    def status(self, external):
        return self.status_details(self._external_call(external))['state']

    def _completed(self, call):
        accepted, _ = self._bound(call)
        value = json.loads(e.read(self.records.directory(call) / 'completed.json'))
        if (any(value.get(key) != accepted.get(key) for key in ('call_id', 'scope', 'mechanism_binding'))
                or value.get('native_state') not in {'succeeded', 'failed', 'cancelled'}
                or value.get('status') != execution_status(value['native_state'])):
            raise e.IntegrityError('TCAD completion differs from the original call')
        for original in value['proofs']:
            _verify_proof(original)
        self._collection(call, value['native_state'])
        return value

    def _collection(self, call, native, context=None):
        accepted, prepared = self._bound(call)
        directory = self.records.directory(call)
        collected = json.loads(e.read(directory / 'collected.json'))
        receipt = json.loads(e.read(directory / 'tcad-terminal-binding.json'))
        backend = json.loads(e.read(directory / 'tcad-backend-binding.json'))
        if (collected.get('call_id') != call or collected.get('scope') != accepted['scope']
                or collected.get('mechanism_binding') != accepted.get('mechanism_binding')
                or collected.get('native_state') != native
                or receipt.get('call_id') != call or receipt.get('scope') != accepted['scope']
                or receipt.get('prepared_sha256') != prepared.sha256
                or receipt.get('external_run_id') != self.records.external(call)
                or receipt.get('outputs') != collected.get('outputs')
                or receipt.get('status', {}).get('state') != native):
            raise e.IntegrityError('TCAD collection differs from the original terminal state')
        if backend != dict(call_id=call, scope=accepted['scope'], prepared_sha256=prepared.sha256,
                           external_run_id=self.records.external(call), target=self.target):
            raise e.IntegrityError('TCAD retained backend binding changed')
        outputs = tuple(LocalFileDescriptor.model_validate(item) for item in collected['outputs'])
        for item in outputs:
            if context is not None:
                context.remaining_seconds()
            if Path(item.local_path) != directory / 'tcad-originals' / item.sha256:
                raise e.IntegrityError('TCAD retained output escaped its original call')
        self._inventory(outputs, native, context=context)
        return collected

    @staticmethod
    def _inventory(outputs, native, *, context=None, verify_bytes=True):
        names = {}
        for item in outputs:
            if context is not None:
                context.remaining_seconds()
            name = Path(item.name)
            if (item.name in names or name.is_absolute() or '..' in name.parts or not name.parts
                    or name.as_posix() != item.name or '\\' in item.name):
                raise e.IntegrityError('TCAD output names are ambiguous or noncanonical')
            if verify_bytes:
                _verify_descriptor(item, context)
            elif Path(item.local_path).resolve() != Path(item.local_path) or not Path(item.local_path).is_file():
                raise e.IntegrityError('Exact TCAD output regular file required')
            elif Path(item.local_path).stat().st_size != item.size_bytes:
                raise e.IntegrityError('TCAD output size differs from its declared identity')
            names[item.name] = item
        if 'tcad_manifest' not in names or 'tcad_log' not in names:
            raise e.IntegrityError('TCAD collection lacks native manifest or log')
        chunks = []
        with Path(names['tcad_manifest'].local_path).open('rb') as source:
            while True:
                if context is not None:
                    context.remaining_seconds()
                block = source.read(1024 * 1024)
                if not block:
                    break
                chunks.append(block)
        manifest = TCADRuntimeManifest.model_validate_json(b''.join(chunks), strict=True)
        if context is not None:
            context.remaining_seconds()
        if manifest.terminal_state != native:
            raise e.IntegrityError('TCAD manifest differs from observed native terminal state')
        if set(names) != {item.name for item in manifest.outputs} | {'tcad_manifest', 'tcad_log'}:
            raise e.IntegrityError('TCAD collection differs from the full native output inventory')
        for item in manifest.outputs:
            if context is not None:
                context.remaining_seconds()
            descriptor = names[item.name]
            if (descriptor.sha256, descriptor.size_bytes, descriptor.media_type) != (item.sha256, item.size_bytes, item.media_type):
                raise e.IntegrityError('TCAD native output differs from its manifest')
        return manifest

    def _retain(self, call, outputs, details, context):
        manifest = self._inventory(outputs, details['state'], context=context, verify_bytes=False)
        directory = self.records.directory(call)
        originals = _directory(directory / 'tcad-originals')
        retained = []
        for item in outputs:
            target = originals / item.sha256
            _copy_original(item, target, context)
            retained.append(item.model_copy(update={'local_path': str(target)}))
        receipt = directory / 'tcad-terminal-binding.json'
        context.remaining_seconds()
        _write_original(receipt, dict(call_id=call, scope=self.config['scope'],
            external_run_id=self.records.external(call), prepared_sha256=self.records.accepted(call)['prepared']['sha256'],
            status=details, outputs=[item.model_dump(mode='json') for item in retained]))
        self.records.publish(call, 'collected.json', dict(native_state=manifest.terminal_state,
            outputs=[item.model_dump(mode='json') for item in retained]))

    def result(self, call):
        directory = self.records.directory(call)
        if (directory / 'completed.json').exists():
            return self._completed(call)
        unknown = dict(call_id=call, status='unknown', note='Original TCAD terminal evidence is not verified')
        accepted, prepared = self._bound(call)
        try:
            details = self._query(call)
        except (OSError, RuntimeError):
            return unknown
        if execution_status(details.get('state')) not in {'known_success', 'known_failed'}:
            return unknown
        unknown['native_state'] = details['state']
        with self.records.lease('tcad-collect-' + call + '.lock'):
            if (directory / 'completed.json').exists():
                return self._completed(call)
            value = accepted['tcad']
            try:
                permit = self._check('collect', call, LocalFileDescriptor.model_validate(value['payload']),
                    prepared=prepared, prior=value['authority'])
                context = permit['context']
                context.remaining_seconds()
                if not (directory / 'collected.json').exists():
                    outputs = self.adapter.collect_with_budget(self.records.external(call), context=context)
                    context.remaining_seconds()
                    self._retain(call, outputs, details, context)
                collected = self._collection(call, details['state'], context)
                context.remaining_seconds()
            except (e.UnsupportedExecution, OSError, RuntimeError):
                return unknown
            native = collected['native_state']
            try:
                proofs = [_proof(directory / name, context) for name in (
                    'tcad-backend-binding.json', 'tcad-terminal-binding.json', 'collected.json')]
                proofs += [dict(path=item['local_path'], sha256=item['sha256'], size_bytes=item['size_bytes'])
                           for item in collected['outputs']]
                context.remaining_seconds()
            except OSError:
                return unknown
            self.records.publish(call, 'completed.json', dict(status=execution_status(native), native_state=native,
                proofs=proofs, note='Retained native TCAD execution facts; no scientific qualification'))
            return json.loads(e.read(directory / 'completed.json'))

    def collect_original(self, call):
        if self.result(call)['status'] == 'unknown':
            raise e.UnsupportedExecution('Original TCAD terminal collection is not verified')
        return tuple(LocalFileDescriptor.model_validate(item)
                     for item in json.loads(e.read(self.records.directory(call) / 'collected.json'))['outputs'])

    def collect(self, external):
        return self.collect_original(self._external_call(external))

    def cancel_original(self, call):
        accepted, prepared = self._bound(call)
        details = self.status_details(call)
        if execution_status(details.get('state')) in {'known_success', 'known_failed'}:
            return details['state']
        if details.get('state') == 'unknown':
            return 'unknown'
        value = accepted['tcad']
        self._check('cancel', call, LocalFileDescriptor.model_validate(value['payload']),
                    prepared=prepared, prior=value['authority'])
        return self.adapter.cancel(self.records.external(call))

    def cancel(self, external):
        return self.cancel_original(self._external_call(external))

    @staticmethod
    def public_result(result):
        return {key: result[key] for key in ('call_id', 'status', 'native_state', 'note') if key in result}


def build_managed_runtime(context):
    if context.mode != 'local_worker':
        raise ValueError('TCAD managed registration requires the existing local_worker factory mode')
    body = json.loads(context.config_bytes)
    allowed = set(TCADRuntimeConfig.model_fields) | e.HOST_CONFIGURATION_FIELDS | {'max_seconds'}
    if not isinstance(body, dict) or set(body) - allowed:
        raise ValueError('TCAD managed configuration contains undeclared settings')
    transport = TCADRuntimeConfig.model_validate_json(json.dumps({
        key: body[key] for key in TCADRuntimeConfig.model_fields if key in body}), strict=True)
    adapter = build_adapter(transport, state_root=context.state_root)
    # P3 alone will wire a trusted gate and frozen originals. JSON cannot enable it.
    return RuntimePluginContribution(execution_adapters={'tcad': TCADManagedExecution(body, adapter)})


REGISTRATION = ExecutionInterfaceRegistration('tcad_execution', '1', RuntimePluginFactory(build_managed_runtime))
