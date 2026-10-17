"""Public compile/seal/review/run contracts with injected local transport.

Native session files and scheduling eligibility are synthetic trusted fixture
inputs. This is not real platform independence, backend or solver qualification.
"""
import json
from pathlib import Path
import uuid

import pytest

from scidiscovery.operations.execution import LocalFileDescriptor
from scidiscovery.research_loop import (budget, contracts as c, controller, execution_inputs as inputs,
    execution_authority as authority, experiments as e, formal_review as review, native)
from tcad_artifact import managed_execution as managed
from tcad_artifact.execution_policy import execution_admission
from tcad_artifact.project_packager import (materialize_execution_inputs, package_execution_package_json,
    validate_execution_package_json)
from tests.operations.tcad_policy_fixtures import policy_snapshot
from test_history_handoff import finish


class InputBackend:
    def __init__(self):
        self.prepared = []; self.submits = 0; self.policy_reads = 0

    def execution_admission(self, raw, *, preparation_profile):
        self.policy_reads += 1
        return execution_admission(policy_snapshot(), validate_execution_package_json(
            raw, preparation_profile=preparation_profile))

    def prepare(self, payload, *, preparation_profile, exchange_directory, input_metadata, open_input):
        raw = Path(payload.local_path).read_bytes()
        package = validate_execution_package_json(raw, preparation_profile=preparation_profile)
        resolved = materialize_execution_inputs(package, None, exchange_directory, 2,
            input_metadata=input_metadata, open_input=open_input)
        self.prepared.append({name: path.read_bytes() for name, path in resolved.items()})
        packed = package_execution_package_json(raw, preparation_profile=preparation_profile,
            input_payloads=resolved, output_root=exchange_directory / 'physical')
        return LocalFileDescriptor.model_validate(packed.job_spec_file.model_dump(mode='json'), strict=True)

    def lookup_submission(self, prepared):
        return ('native-remote-id', 'queued') if self.submits else None

    def submit(self, prepared, *, authorization):
        self.submits += 1
        return 'native-remote-id', 'queued'

    def status_details(self, external):
        return dict(state='queued', run_id=external)


@pytest.fixture
def chain(tmp_path, monkeypatch):
    old = json.loads((Path(__file__).parents[1] / 'fixtures/tcad_analysis_package.json').read_bytes())
    snapshot = tmp_path / 'operator-capability.json'; c.write(snapshot, old['capability'])
    launcher = tmp_path / 'codex'; launcher.write_text('# synthetic identity files only; never executed\n'); launcher.chmod(0o700)
    public = tmp_path / 'public'; public.mkdir(); objective = public / 'objective.md'; objective.write_text('Use one exact supplied mesh.')
    backend = InputBackend()
    monkeypatch.setattr(e, 'registration', lambda name: (managed.REGISTRATION, 'tcad'))
    monkeypatch.setattr(managed, 'build_adapter', lambda *args, **kwargs: backend)
    root = tmp_path / 'instance'
    options = dict(transport='socket', socket_path=str(tmp_path / 'unused.sock'),
        implementation_compilation=dict(capability_snapshot_path=str(snapshot)))
    controller.prepare(root, objective, public, [str(launcher)], max_tokens=4000, max_seconds=1000,
        max_steps=8, model='fixture', reasoning_effort='high', search_policy=None, experiment_mode='local',
        node_budget_mode='hard', execution_config=dict(executor='tcad_execution:tcad', configuration=options),
        formal_review_policy={'version': 1}, execution_authority_policy={'version': 1},
        execution_resource_policy=dict(version=1, allowance=dict(wall_time_seconds=100, max_storage_bytes=1000000)),
        source_restrictions=[dict(source=str(objective), sha256=c.digest(objective), restriction='clear')])
    # Only the native scheduling/identity boundary is synthetic. Source binding,
    # compiler proofs, formal qualification rules, gate and resource ledger run
    # through their actual production functions if this test is later authorized.
    monkeypatch.setattr(authority, '_remaining', lambda *args, **kwargs: (budget.clock_stamp(), 100.))
    original_seal = c.seal_result

    def seal(root, step):
        work = c.workspace(root, step); record = c.host_record(work)
        thread = str(uuid.uuid5(uuid.NAMESPACE_URL, 'native-input-fixture-' + str(step)))
        home = tmp_path / 'native-home'; session = home / 'sessions' / (thread + '.jsonl'); session.parent.mkdir(parents=True, exist_ok=True)
        session.write_text(json.dumps(dict(type='session_meta', payload=dict(id=thread, cwd=str(work)))) + '\n')
        (record / 'native.jsonl').write_text(json.dumps(dict(type='thread.started', thread_id=thread)) + '\n')
        outcome = c.read(record / 'native-outcome.json')
        outcome.update(thread_id=thread, native_identity=dict(participant_scope='codex_exec_single_agent_v1',
            home=str(home), path=str(session)))
        c.write(record / 'native-outcome.json', outcome)
        return original_seal(root, step)

    monkeypatch.setattr(c, 'seal_result', seal)
    finish(root, 1, 'H', [], action='experiment', files={'mesh.tdr': 'mesh'})
    job = c.build_job(root, 2, 'W', [1]); work = c.workspace(root, 2); record = c.host_record(work)
    c.write(record / 'native-intent.json', dict(task_sha256=c.digest(root / 'jobs/002.json')))
    config_path = work / 'work/execution.json'; config = e.configure(root, 2, 'tcad_execution:tcad', options, config_path)
    author = work / 'work/implementation.json'
    c.write(author, dict(solver_kind='sdevice', files=[dict(relative_path='main.cmd', content='Solve {}\n')],
        input_slots=[dict(semantic_name='mesh', target_relative_path='inputs/mesh.tdr', media_type='application/octet-stream')],
        entrypoint='main.cmd', resource_limits=dict(wall_time_seconds=1, cpu_time_seconds=1,
            max_memory_bytes=1024, max_output_bytes=128, max_storage_bytes=100000)))
    aliases = work / 'work/scientific-files.json'; c.write(aliases, {'mesh': 'inputs/parents/001/artifacts/mesh.tdr'})
    return root, backend, options, config, config_path, author, aliases


def test_public_compile_exact_review_and_existing_run_keep_native_original(chain, capsys):
    root, backend, options, config, config_path, author, aliases = chain
    output = c.workspace(root, 2) / 'artifacts/package.json'
    assert e.main(['--config', str(config_path), 'compile', '--implementation', str(author),
        '--scientific-files', str(aliases), '--output', str(output)]) == 0
    compiled = json.loads(capsys.readouterr().out)
    assert compiled['status'] == 'compiled' and not backend.prepared and not backend.policy_reads
    before = output.read_bytes(); finish(root, 2, 'W', [1])
    seal = c.read(c.host_record(c.workspace(root, 2)) / 'result-identity.json')
    assert len(seal['compiled_implementations']) == 1
    assert ('codex_exec', str(uuid.uuid5(uuid.NAMESPACE_URL, 'native-input-fixture-1'))) in {
        tuple(row) for row in review.authors(root, 2)['participants']}
    job, _, record = finish(root, 3, 'A', [2], action='formal_review', selection=['W002-I001'])
    role, parents, instruction, back = review.request_route(root, job, c.read(record / 'result.json'), [3])
    review_job = c.build_job(root, 4, role, parents, instruction, back)
    review_record = c.host_record(c.workspace(root, 4))
    c.write(review_record / 'native-intent.json', dict(task_sha256=c.digest(root / 'jobs/004.json')))
    c.write(review_record / 'science-output.json', dict(verdict='pass', summary='Synthetic exact review',
        scientific_result='Synthetic transport/input contract only.', limitations=['No real platform/solver qualification.']))
    c.write(review_record / 'usage.json', dict(input_tokens=1, cached_input_tokens=0, output_tokens=1))
    c.write(review_record / 'native-outcome.json', dict(returncode=0, stop_reason=None,
        usage=native.usage(root), raw_sha256=c.digest(review_record / 'science-output.json')))
    c.seal_result(root, 4)
    _, parents, instruction, back = review.return_route(root, review_job, [2, 3, 4])
    c.build_job(root, 5, 'A', parents, instruction, back)
    finish(root, 5, 'A', parents, selection=['W002-I001'])
    job = c.build_job(root, 6, 'W', [5]); work = c.workspace(root, 6); record = c.host_record(work)
    c.write(record / 'native-intent.json', dict(task_sha256=c.digest(root / 'jobs/006.json')))
    active = work / 'work/execution.json'; current = e.configure(root, 6, 'tcad_execution:tcad', options, active)
    secret = root / 'operator.key'; secret.write_bytes(b'x' * 32); secret.chmod(0o600)
    authority.bind_secret(root, b'x' * 32, source=secret)
    assert e.main(['--config', str(active), 'run', '--payload', str(output)]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'queued' and backend.prepared == [{'mesh': b'mesh'}] and backend.submits == 1
    accepted = e.Records(current).accepted(result['call_id'])
    assert accepted['tcad']['payload']['local_path'] == str(output)
    assert accepted['execution_reservation'] is not None
    assert e.main(['--config', str(active), 'run', '--payload', str(output)]) == 2
    assert json.loads(capsys.readouterr().out)['call_id'] == result['call_id'] and backend.submits == 1
    assert output.read_bytes() == before


def test_unbound_alias_and_author_read_race_reject_before_gate(chain, monkeypatch):
    root, backend, _, config, _, author, aliases = chain
    adapter = e.load(config); output = c.workspace(root, 2) / 'artifacts/package.json'
    with pytest.raises(ValueError, match='missing or ambiguous'):
        e.compile_implementation(config, adapter, author, {'mesh': 'mesh.tdr'}, output)
    original_identity = inputs.q._identity

    def changed(path):
        if Path(path) == author:
            document = c.read(author); document['files'][0]['content'] = 'Solve { changed }\n'; c.write(author, document)
        return original_identity(path)

    monkeypatch.setattr(inputs.q, '_identity', changed)
    with pytest.raises(ValueError, match='between reading'):
        e.compile_implementation(config, adapter, author, c.read(aliases), output)
    assert not output.exists() and not backend.prepared and not backend.policy_reads


def test_same_hash_wrong_origin_and_changed_package_cannot_reuse_compiler_proof(chain):
    root, backend, _, config, _, author, aliases = chain
    job = c.read(root / 'jobs/002.json'); original_material = job['direct_materials'][0]
    original = inputs._producer(root, original_material)
    wrong = dict(original, producer_step=2)
    with pytest.raises(ValueError, match='frozen compiler source'):
        inputs.resolve_native_original(root, wrong, compiler_job=job)
    with pytest.raises(ValueError, match='another instance'):
        inputs.resolve_native_original(root, dict(original, instance_id='another-instance'), compiler_job=job)
    output = c.workspace(root, 2) / 'artifacts/package.json'
    e.compile_implementation(config, e.load(config), author, c.read(aliases), output)
    packet = c.read(output); packet['resolved_inputs'][0]['original'] = wrong
    output.chmod(0o600); c.write(output, packet)
    with pytest.raises(ValueError):
        finish(root, 2, 'W', [1])
    assert not (c.host_record(c.workspace(root, 2)) / 'result-identity.json').exists()
    assert not backend.policy_reads and not backend.prepared
