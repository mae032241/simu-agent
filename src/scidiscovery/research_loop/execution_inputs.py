"""Exact native scientific inputs and immutable compiler provenance; no effects."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path

from . import contracts as c, qualification as q, execution


def _bound(job):
    return [*job['direct_materials'], *[row['material'] for row in job.get('selected_inputs', [])]]


def _producer(root, material):
    source = Path(material['source'])
    try:
        relative = source.relative_to(root / 'project/nodes')
        step = int(relative.parts[0])
    except (ValueError, IndexError) as error:
        raise ValueError('Scientific input needs an exact sealed instance original') from error
    if step <= 0 or relative.parts[0] != f'{step:03d}':
        raise q.IntegrityError('Scientific input producer namespace changed')
    path = c.host_record(c.workspace(root, step)) / 'result-identity.json'
    seal = c.read(c.regular(path))
    if [row for row in seal['materials'] if row['path'] == material['path']] != [material]:
        raise q.IntegrityError('Scientific input is not its exact producer material')
    record = c.host_record(c.workspace(root, step))
    if (seal['job_sha256'] != c.digest(c.regular(root / 'jobs' / f'{step:03d}.json'))
            or seal['sha256'] != c.digest(c.regular(record / 'result.json'))
            or seal['raw_sha256'] != c.digest(c.regular(c._execution_raw(root, step)))
            or source.resolve() != source or q._identity(source) != dict(
                path=str(source), sha256=material['sha256'], size_bytes=material['size_bytes'])):
        raise q.IntegrityError('Scientific input producer or original bytes changed')
    return dict(instance_id=c.settings(root)['goal_id'], producer_step=step,
        producer_seal=q._ref(root, path), material_path=material['path'],
        sha256=material['sha256'], size_bytes=material['size_bytes'])


def resolve_native_original(root, original, *, compiler_job):
    """Membership and origin are exact; a matching digest never selects a source."""
    root = Path(root).resolve()
    if (not isinstance(original, dict) or type(original.get('producer_step')) is not int
            or type(original.get('size_bytes')) is not int):
        raise q.IntegrityError('Native original requires exact integer producer/size declarations')
    if original.get('instance_id') != c.settings(root)['goal_id']:
        raise q.IntegrityError('Native input belongs to another instance')
    found = [row for row in _bound(compiler_job) if row['path'] == original.get('material_path')]
    unique = {json.dumps(row, sort_keys=True): row for row in found}
    if len(unique) != 1:
        raise ValueError('Native input is missing or ambiguous in its compiler task')
    material = next(iter(unique.values()))
    if (json.dumps(original, sort_keys=True) != json.dumps(_producer(root, material), sort_keys=True)
            or original['producer_step'] >= compiler_job['step']):
        raise q.IntegrityError('Native input differs from its frozen compiler source')
    return material


def _directory(root, step):
    return c.host_record(c.workspace(root, step)) / 'compiled-implementations'


def verify_compilation(root, ref, *, material=None):
    """Shared seal/review/run validator; it never recompiles reviewed bytes."""
    root = Path(root).resolve(); value = q._read(root, ref)
    if value.get('version') != 1 or type(value.get('version')) is not int:
        raise q.IntegrityError('Compiler original version changed')
    job = q._read(root, value['job']); step = job['step']
    if (value['job'] != q._ref(root, root / 'jobs' / f'{step:03d}.json')
            or job['role'] != 'W' or Path(root / ref['path']).parent.parent != _directory(root, step)):
        raise q.IntegrityError('Compiler original has no exact W owner')
    config = q._read(root, value['configuration'])
    attempt = config['native_attempt']['number']
    expected = root / 'host-runtime/experiment-control' / config['scope']['job_sha256'] / 'interfaces' / f'{attempt:03d}.json'
    if (value['configuration'] != q._ref(root, expected)
            or value['native_intent'] != q._ref(root, execution.record(root, step, attempt) / 'native-intent.json')
            or q._read(root, value['native_intent'])['task_sha256'] != value['job']['sha256']
            or config['scope']['step'] != step or config['scope']['job_sha256'] != value['job']['sha256']):
        raise q.IntegrityError('Compiler native task/configuration original changed')
    if value['implementation'] != config['execution_interface']:
        raise q.IntegrityError('Compiler implementation differs from its frozen interface')
    for item in value['implementation']['code']:
        q._check(item)
    declared = [item for item in value['implementation'].get('public_capabilities', [])
                if item['key'] == 'implementation_authoring']
    if len(declared) != 1 or value['contract'] != declared[0]:
        raise q.IntegrityError('Compiler public contract changed')
    q._check(value['capability_source'])
    if value['capability_source'] not in value['implementation']['code']:
        raise q.IntegrityError('Compiler capability was not frozen by the host interface')
    if any(value['capability'][key] != value['capability_source'][key] for key in ('sha256', 'size_bytes')):
        raise q.IntegrityError('Compiler retained capability differs from its operator original')
    q._read(root, value['capability']); q._read(root, value['author'])
    author_origin = Path(value['author_origin']['path'])
    if (not author_origin.is_relative_to(c.workspace(root, step))
            or author_origin.resolve() != author_origin
            or any(value['author'][key] != value['author_origin'][key] for key in ('sha256', 'size_bytes'))):
        raise q.IntegrityError('Compiler author snapshot differs from its declared source')
    author_input = value.get('author_input')
    if author_input is not None:
        author_material = resolve_native_original(root, author_input, compiler_job=job)
        if (author_origin != c.workspace(root, step) / author_material['path']
                or any(value['author'][key] != author_material[key] for key in ('sha256', 'size_bytes'))):
            raise q.IntegrityError('Compiler author input differs from its exact bound original')
    elif author_origin.is_relative_to(c.workspace(root, step) / 'inputs'):
        raise q.IntegrityError('Compiler author input has no declared original contribution')
    seen = set()
    for item in value['inputs']:
        if item['semantic_name'] in seen:
            raise q.IntegrityError('Compiler input slots are ambiguous')
        seen.add(item['semantic_name'])
        source = resolve_native_original(root, item['original'], compiler_job=job)
        if (item['alias'] != source['path'] or type(item['size_bytes']) is not int or item['size_bytes'] != source['size_bytes']
                or not isinstance(item['media_type'], str)):
            raise q.IntegrityError('Compiler input alias/metadata changed')
    q._check(value['output'])
    if material is not None and value['output'] != dict(path=material['source'],
            sha256=material['sha256'], size_bytes=material['size_bytes']):
        raise q.IntegrityError('Compiler output is not the exact sealed material')
    return value


def capture(root, job, materials):
    """Only delivered compiler outputs enter this node's existing seal."""
    root = Path(root).resolve(); result = []; seen = set()
    for path in sorted(_directory(root, job['step']).glob('*/compiler.json')):
        ref = q._ref(root, path); value = q._read(root, ref)
        matches = [row for row in materials if row['source'] == value['output']['path']]
        if not matches:
            continue
        if len(matches) != 1 or matches[0]['source'] in seen:
            raise q.IntegrityError('Compiled material has ambiguous provenance')
        verify_compilation(root, ref, material=matches[0]); seen.add(matches[0]['source'])
        result.append(dict(material=matches[0], compiler=ref))
    return result


def validate_seal(root, job, seal):
    if seal.get('compiled_implementations', []) != capture(root, job, seal['materials']):
        raise q.IntegrityError('Sealed compiler originals changed')


def execution_input_coverage(root, job, subject):
    """Prove coverage by existing selected/compiler edges, without adding edges."""
    root = Path(root).resolve()
    seal = q._read(root, subject['producer_seal'])
    selected = [row for row in job.get('selected_inputs', [])
        if row['origin_step'] == subject['producer_step'] and row['material'] == subject['material']
        and row['origin_result_sha256'] == seal['sha256']]
    if not selected:
        return None
    found = [row for row in seal.get('compiled_implementations', []) if row['material'] == subject['material']]
    if len(found) != 1:
        return None
    compiler = verify_compilation(root, found[0]['compiler'], material=subject['material'])
    compiler_job = q._read(root, compiler['job'])

    def covers(owner, originals):
        if owner.get('source_provenance') is None:
            return False
        q.validate_inputs(root, owner)
        edges = q._read(root, owner['source_provenance'])['edges']
        return all(any(edge['kind'] == 'producer' and edge['step'] == original['producer_step']
            and edge['seal'] == original['producer_seal'] for edge in edges) for original in originals)

    if not covers(job, [subject]):
        return None
    originals = [row['original'] for row in compiler['inputs']]
    if compiler.get('author_input') is not None:
        originals.append(compiler['author_input'])
    # These same originals are already traversed by authors(compiler producer).
    # verify_compilation proves their exact membership in compiler_job.
    if not covers(compiler_job, originals):
        return None
    return found[0]['compiler']


class NativeInputHost:
    """A non-JSON service created only after the original host context is checked."""

    def __init__(self, config):
        from . import execution_authority as authority
        self.root, self.job, self.intent = authority._host_context(config)
        self.config = config

    def compile(self, source, output, *, slots, aliases, capability, contract, builder):
        from . import execution_authority as authority
        authority._remaining(self.root, self.config)
        work = c.workspace(self.root, self.job['step']); source = Path(source).absolute(); output = Path(output).absolute()
        if (source.resolve() != source or not source.is_relative_to(work)
                or output.resolve() != output or not output.is_relative_to(work / 'artifacts')
                or any(parent.is_symlink() for parent in output.parents)):
            raise ValueError('Compile source/output must be original files in this task and artifacts')
        authored = c.regular(source).read_bytes(); source_identity = q._identity(source)
        if (len(authored), hashlib.sha256(authored).hexdigest()) != (source_identity['size_bytes'], source_identity['sha256']):
            raise q.IntegrityError('Compiler author changed between reading and identity capture')
        author_input = None
        if source.is_relative_to(work / 'inputs'):
            found = {json.dumps(row, sort_keys=True): row for row in _bound(self.job) if work / row['path'] == source}
            if len(found) != 1:
                raise ValueError('Author input must name one exact frozen scientific document')
            material = next(iter(found.values())); author_input = _producer(self.root, material)
            if any(source_identity[key] != material[key] for key in ('sha256', 'size_bytes')):
                raise q.IntegrityError('Author read copy differs from its original scientific document')
        if set(aliases) != {slot['semantic_name'] for slot in slots}:
            raise ValueError('Select one exact bound scientific-file alias for every slot')
        inputs = []
        for slot in slots:
            alias = aliases[slot['semantic_name']]
            found = {json.dumps(row, sort_keys=True): row for row in _bound(self.job) if row['path'] == alias}
            if len(found) != 1:
                raise ValueError('Scientific file alias is missing or ambiguous; choose an exact listed task input')
            material = next(iter(found.values())); original = _producer(self.root, material)
            if original['producer_step'] >= self.job['step']:
                raise ValueError('Compile inputs must be preceding sealed originals')
            inputs.append(dict(slot, alias=alias, original=original, size_bytes=material['size_bytes']))
        if c.output_quota_exceeded(c.settings(self.root), (item['size_bytes'] for item in inputs)):
            raise ValueError('Scientific inputs exceed the explicit frozen handoff quota')
        raw = builder(authored, [{key: item[key] for key in item if key != 'alias'} for item in inputs])
        if type(raw) is not bytes or q._identity(source) != source_identity:
            raise q.IntegrityError('Compiler author original changed during compilation')
        if c.output_quota_exceeded(c.settings(self.root), [len(raw)]):
            raise ValueError('Compiled package exceeds explicit output quota')
        identity = hashlib.sha256(json.dumps(dict(output=str(output), sha256=hashlib.sha256(raw).hexdigest()),
            sort_keys=True).encode()).hexdigest()
        directory = _directory(self.root, self.job['step']) / identity
        if directory.resolve() != directory:
            raise q.IntegrityError('Compiler original directory changed')
        directory.mkdir(parents=True, exist_ok=True)
        author_path = directory / 'author.json'
        c._copy_bound(source, author_path, source_identity['sha256'])
        c._copy_bound(Path(capability['path']), directory / 'capability.json', capability['sha256'])
        snapshot = q._ref(self.root, directory / 'capability.json')
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists() or output.is_symlink():
            if c.regular(output).read_bytes() != raw:
                raise ValueError('Choose a new output for a changed implementation; sealed packages cannot be overwritten')
        else:
            with output.open('xb') as stream:
                stream.write(raw)
            output.chmod(0o400)
        attempt = self.config['native_attempt']['number']
        projection = self.root / 'host-runtime/experiment-control' / self.config['scope']['job_sha256'] / 'interfaces' / f'{attempt:03d}.json'
        value = dict(version=1, job=q._ref(self.root, self.root / 'jobs' / f'{self.job["step"]:03d}.json'),
            native_intent=self.intent, configuration=q._ref(self.root, projection),
            implementation=self.config['execution_interface'], contract=contract,
            author=q._ref(self.root, author_path), author_origin=source_identity, author_input=author_input,
            capability_source=capability, capability=snapshot, inputs=inputs, output=q._identity(output))
        proof = q._save(self.root, directory / 'compiler.json', value)
        verify_compilation(self.root, proof)
        return dict(status='compiled', path=str(output.relative_to(work)),
                    qualification='Unreviewed compiled material; no execution permission')

    def for_payload(self, payload, resolved_inputs):
        from . import execution_authority as authority
        subject, _, _ = authority._selected_subject(self.root, self.job, payload)
        seal = q._read(self.root, subject['producer_seal'])
        found = [row for row in seal.get('compiled_implementations', []) if row['material'] == subject['material']]
        if len(found) != 1:
            raise ValueError('Native package needs its exact sealed compiler provenance')
        value = verify_compilation(self.root, found[0]['compiler'], material=subject['material'])
        compiler_job = q._read(self.root, value['job'])
        expected = [{key: row[key] for key in row if key != 'alias'} for row in value['inputs']]
        if json.dumps([item.model_dump(mode='json') for item in resolved_inputs], sort_keys=True) != json.dumps(expected, sort_keys=True):
            raise q.IntegrityError('Native package slots differ from their sealed compiler provenance')

        def resolve(item):
            declared = item.model_dump(mode='json')
            matches = [row for row in value['inputs'] if {key: row[key] for key in row if key != 'alias'} == declared]
            if len(matches) != 1:
                raise q.IntegrityError('Native slot differs from its exact reviewed compiler binding')
            return resolve_native_original(self.root, declared['original'], compiler_job=compiler_job)

        def metadata(item):
            material = resolve(item)
            return material['size_bytes'], item.media_type

        @contextmanager
        def open_original(item):
            material = resolve(item)
            with c.regular(Path(material['source'])).open('rb') as stream:
                yield stream

        return metadata, open_original
