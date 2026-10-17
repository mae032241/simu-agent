"""Public compile/seal/review/run contracts with injected local transport.

Native session files and scheduling eligibility are synthetic trusted fixture
inputs. This is not real platform independence, backend or solver qualification.
"""
import json
import hashlib
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


def _reviewed_execution(chain, capsys):
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
    return root,backend,output,active,current,before


def test_public_compile_exact_review_and_existing_run_keep_native_original(chain, capsys):
    root,backend,output,active,current,before=_reviewed_execution(chain,capsys)
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


@pytest.fixture
def late_call(chain,capsys,monkeypatch):
    """Synthetic owner cleanup only; actual seal/gate/ledger/factory stay in path."""
    from scidiscovery.research_loop import execution,runtime
    root,backend,output,active,config,_=_reviewed_execution(chain,capsys)
    admission=backend.execution_admission
    monkeypatch.setattr(backend,'execution_admission',lambda *a,**kw:admission(*a,**kw).model_copy(
        update={'outcome':'require_human_approval'}))
    c.write(root/'host-started.json',budget.clock_stamp())
    assert e.main(['--config',str(active),'run','--payload',str(output)])==2
    pending=json.loads(capsys.readouterr().out)
    assert pending['status']=='authorization_required' and backend.submits==0 and not backend.prepared
    call=pending['call_id'];original_seal=c.seal_result

    def cleaned(root,step):
        if step==6:
            record=execution.record(root,step)
            outcome=c.read(record/'native-outcome.json');outcome['cleanup']='observed_group_cleaned'
            c.write(record/'native-outcome.json',outcome)
            owner=dict(pid=999999999,start_ticks=1,pgid=999999999,sid=999999999,
                boot_id='synthetic-original-boot',task_sha256=execution.identity(root,step))
            for name in ('runner-process.json','native-process.json'):c.write(record/name,owner)
        return original_seal(root,step)

    monkeypatch.setattr(c,'seal_result',cleaned)
    monkeypatch.setattr(runtime,'process_matches',lambda *args:False)
    finish(root,6,'W',[5])
    seal_path=c.host_record(c.workspace(root,6))/'result-identity.json'
    assert c.read(root/c.read(seal_path)['pending_executions']['path'])['complete'] is True
    return root,backend,config,call,pending['authorization_request'],seal_path.read_bytes()


def _approve(root,ref):
    key=Path(ref['path']).parent.name
    tokens=authority.form_tokens(root,key,secret=b'x'*32,boot='fixture-ui',browser_token='fixture-browser')
    return authority.record_decision(root,key,secret=b'x'*32,boot='fixture-ui',browser_token='fixture-browser',
        **tokens,selected_option=authority.OPTIONS[0],rationale='Explicit synthetic exact decision')


def _resume(root,call,**options):
    return controller.execution_resume(root,6,call,max_seconds=20,authorization_note='Explicit finite host recovery',**options)


def test_late_decision_public_resume_preserves_call_pending_prefix_and_cancelled(late_call,monkeypatch,capsys):
    from scidiscovery.research_loop import cli,execution_recovery as recovery,history,search
    root,backend,config,call,request,seal_bytes=late_call
    _approve(root,request)
    # An already frozen A continues to see the old zero-accepted prefix.
    old_job=c.build_job(root,7,'A',[6]);old_job_bytes=(root/'jobs/007.json').read_bytes()
    backend.state='queued'
    monkeypatch.setattr(backend,'status_details',lambda external:dict(state=backend.state,run_id=external))
    args=['execution-resume','--root',str(root),'--step','6','--call-id',call,
          '--max-seconds','20','--authorization-note','Explicit finite fixture window']
    assert cli.main(args)==0
    assert json.loads(capsys.readouterr().out)['call_id']==call and backend.submits==1
    accepted=e.Records(config).accepted(call);reservation=accepted['execution_reservation']
    assert accepted['execution_authority']['path'].endswith('/authorization.json')
    assert recovery.prefix(root,7)==old_job['history']['execution_recoveries']==[]
    refs=recovery.prefix(root,9);view=recovery.call_view(root,[],refs)
    assert view[(6,call)]['native_state']=='queued' and view[(6,call)]['row']['status']=='unknown'
    assert recovery.resolved(root,refs)=={} and recovery.pending(root) and not recovery.pending(root,unknown_only=True)
    count=len(refs);assert _resume(root,call)['status']=='execution_resume_recorded'
    assert len(recovery.prefix(root,9))==count and backend.submits==1
    backend.state='cancelling';_resume(root,call)
    assert recovery.call_view(root,[],recovery.prefix(root,9))[(6,call)]['native_state']=='cancelling'
    backend.state='cancelled'

    def collect(external,*,context):
        context.remaining_seconds();directory=root/'synthetic-terminal';directory.mkdir(exist_ok=True)
        rows=[]
        for name,data,media in [('tcad_log',b'cancelled\n','text/plain'),('tcad_manifest',json.dumps(dict(
                started_at=None,completed_at='2026-10-17T00:00:00Z',terminal_state='cancelled',
                exit_code=130,error='synthetic cancellation',outputs=[])).encode(),'application/json')]:
            path=directory/name;path.write_bytes(data)
            rows.append(LocalFileDescriptor(name=name,local_path=str(path),sha256=hashlib.sha256(data).hexdigest(),size_bytes=len(data),media_type=media))
        return tuple(rows)

    monkeypatch.setattr(backend,'collect_with_budget',collect,raising=False)
    _resume(root,call)
    refs=recovery.prefix(root,9);latest=recovery.call_view(root,[],refs)[(6,call)]
    assert latest['phase']=='terminal' and latest['row']['status']=='known_failed'
    assert latest['row']['execution']['native_state']=='cancelled' and not recovery.pending(root)
    sources=history.source_sequence(root,7)
    projected=recovery.project_records(root,history.records_from_sources(root,sources,write_cache=False),refs)
    assert len(projected[-1]['observation']['managed_calls'])==1
    assert projected[-1]['observation']['managed_calls'][0]['accepted']==latest['row']['accepted']
    assert search.fold(root,sources,recovery_refs=[])['opportunity_unknown'] is False
    assert budget.execution_reservation(root,reservation)['released'] is False
    assert (root/'jobs/007.json').read_bytes()==old_job_bytes
    assert (c.host_record(c.workspace(root,6))/'result-identity.json').read_bytes()==seal_bytes


def test_expired_request_requires_explicit_successor_without_retry_ttl_refresh(late_call,monkeypatch):
    from scidiscovery.research_loop import execution_recovery as recovery
    root,backend,_,call,original,_=late_call
    old_bytes=(root/original['path']).read_bytes();old=c.read(root/original['path'])
    monkeypatch.setattr(authority.time,'time',lambda:old['expires_at']+1)
    assert _resume(root,call)['status']=='authorization_renewal_required'
    first=_resume(root,call,request_valid_seconds=30)
    assert first['status']=='authorization_required' and not recovery.prefix(root,9)
    new=first['authorization_request'];new_bytes=(root/new['path']).read_bytes()
    assert c.read(root/new['path'])['supersedes']==original and authority.request_successor(root,original)==new
    again=_resume(root,call,request_valid_seconds=30)
    assert again['authorization_request']==new and (root/new['path']).read_bytes()==new_bytes
    with pytest.raises(ValueError,match='expired'):_approve(root,original)
    _approve(root,new);assert _resume(root,call)['status']=='execution_resume_recorded'
    assert backend.submits==1 and (root/original['path']).read_bytes()==old_bytes


def test_missing_positive_cleanup_and_contradictory_prepare_never_dispatch(late_call,monkeypatch):
    from scidiscovery.research_loop import execution_resume as resume,qualification as q,runtime
    root,backend,_,call,request,_=late_call
    _approve(root,request)
    seal=c.read(c.host_record(c.workspace(root,6))/'result-identity.json')
    allocation=q._ref(root,root/'execution-authority/calls'/call/'allocation.json')
    with pytest.raises(ValueError,match='no positive'):resume.verify_pending_set(root,dict(seal,pending_executions=None),allocation)
    proof=root/seal['pending_executions']['path'];before=proof.read_bytes();proof.chmod(0o600);proof.write_bytes(before+b' ')
    with pytest.raises(ValueError):_resume(root,call)
    proof.write_bytes(before);proof.chmod(0o400)
    monkeypatch.setattr(runtime,'process_matches',lambda *args:True)
    with pytest.raises(ValueError,match='live or unknown'):_resume(root,call)
    monkeypatch.setattr(runtime,'process_matches',lambda *args:False)
    c.write(root/'execution-authority/calls'/call/'prepare-intent.json',dict(note='uncertain original side effect'))
    with pytest.raises(ValueError,match='contradict'):_resume(root,call)
    assert backend.submits==0 and not backend.prepared


def test_interrupted_resume_intent_never_regains_fresh_dispatch(late_call,monkeypatch):
    from scidiscovery.research_loop import execution_recovery as recovery
    root,backend,_,call,request,_=late_call;_approve(root,request)
    original=backend.prepare
    monkeypatch.setattr(backend,'prepare',lambda *args,**kwargs:(_ for _ in ()).throw(TimeoutError('synthetic uncertain prepare')))
    with pytest.raises(TimeoutError):_resume(root,call)
    assert recovery.call_view(root,[],recovery.prefix(root,9))[(6,call)]['phase']=='resume_intent'
    monkeypatch.setattr(backend,'prepare',original)
    assert _resume(root,call)['status']=='unknown' and backend.submits==0 and not backend.prepared


def test_reservation_gap_renews_authority_without_second_reservation_or_refund(late_call,monkeypatch):
    from scidiscovery.research_loop import execution_resume as resume,execution_recovery as recovery
    root,backend,config,call,request,_=late_call;_approve(root,request)
    begin=resume._RecoveryAdmission.begin
    monkeypatch.setattr(resume._RecoveryAdmission,'begin',lambda *args:(_ for _ in ()).throw(TimeoutError('after reserve before prepare boundary')))
    with pytest.raises(TimeoutError):_resume(root,call)
    held=budget.execution_accounting(root)['reservations']
    assert len(held)==1 and held[0]['bound'] is None and not recovery.prefix(root,9)
    reservation=held[0]['ref'];remaining=budget.execution_accounting(root)['remaining']
    monkeypatch.setattr(resume._RecoveryAdmission,'begin',begin)
    expires=c.read(root/request['path'])['expires_at']
    monkeypatch.setattr(authority.time,'time',lambda:expires+1)
    renewal=_resume(root,call,request_valid_seconds=30)
    assert renewal['status']=='authorization_required' and not recovery.prefix(root,9)
    _approve(root,renewal['authorization_request'])
    assert _resume(root,call)['status']=='execution_resume_recorded' and backend.submits==1
    assert e.Records(config).accepted(call)['execution_reservation']==reservation
    events=budget._events(root,c.settings(root))[0]
    assert sum(row['kind']=='resource_reserve' for row in events)==1
    assert sum(row['kind']=='resource_rebind' for row in events)==1
    assert not any(row['kind']=='resource_release' for row in events)
    assert budget.execution_accounting(root)['remaining']==remaining
