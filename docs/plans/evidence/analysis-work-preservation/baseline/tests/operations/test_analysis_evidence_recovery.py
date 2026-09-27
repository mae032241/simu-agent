"""Bounded production evidence recovery paths; no solver is launched."""
import hashlib
import json
from pathlib import Path
import pytest

@pytest.mark.parametrize('remote',[False,True])
def test_collection_keeps_later_products(tmp_path, remote):
    from tcad_artifact.worker import _collect_outputs
    from tcad_artifact.remote_runner_py36 import _collect_expected
    (tmp_path/'later.plx').write_bytes(b'raw data\n')
    expected=[dict(name=n,relative_path=p,required=True,max_bytes=1024,media_type='text/plain') for n,p in [('missing','missing.tdr'),('later','later.plx')]]
    records=[]; errors=[]
    if remote:
        _collect_expected(str(tmp_path),expected,{'max_output_bytes':4096},records,errors)
    else:
        _collect_outputs(tmp_path,expected,{'max_output_bytes':4096},records=records,errors=errors)
    assert [x['name'] for x in records]==['later']
    assert len(errors)==1 and 'missing.tdr' in errors[0]


def recovery_system(tmp_path):
    from tests.operations.test_collector_analysis_handoff import _analysis_system,_collect_execution,_bind_collected
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from tcad_artifact.output_recovery import OutputInspectionService
    from tcad_artifact.remote_runner_py36 import _inspect_directory
    system=_analysis_system(tmp_path)
    outputs=_collect_execution(system,tmp_path/'collector',name='collected',output_names=())
    _bind_collected(system,outputs)
    catalog,runtime,root,request,artifacts,_=system
    result=root.facade._publish_execution_result(name='collected')
    request['inputs'].append(dict(port='execution_result',artifact_names=[result]))
    directory=tmp_path/'collector/runs/terminal_collected'
    raw=runtime.artifacts.read(artifacts['output_A'].ref)
    (directory/'work/A_actual.plx').write_bytes(raw)
    class Adapter:
        def inspect_outputs(self, external_run_id, relative_path, max_bytes=32*1024*1024):
            assert external_run_id=='terminal_collected'
            return _inspect_directory(str(directory),relative_path,max_bytes)
    root.call_tool('operation_invoke',request)
    op=catalog.operation('tcad.result.analyze.v1')
    worker=LocalWorkerMCPRouter(runtime.runs,operation_id=op.spec.operation_id,operation_digest=op.digest,
        tool_services={'tcad_artifact:tcad.output_inspection':OutputInspectionService(Adapter())})
    opened=worker.call_tool('worker_open_assignment',{})
    return system,worker,opened,directory


def test_recovered_bytes_score_and_seal_in_same_run(tmp_path):
    from tests.operations.test_tcad_result_analysis import raw_request,analysis_report,write_analysis
    system,worker,opened,directory=recovery_system(tmp_path)
    inspected=worker.call_tool('worker_tcad_inspect_outputs',{'relative_path':'A_actual.plx'})
    assert inspected['status']=='available',inspected
    accepted=worker.call_tool('worker_tcad_accept_output',dict(evidence_alias=inspected['evidence_alias'],output_name='A',rationale='Fixture content and exact case declaration match.',evidence_aliases=[inspected['evidence_alias']]))
    assert accepted['status']=='accepted',accepted
    alias=accepted['evidence_alias']
    record=worker.call_tool('worker_tcad_curve_score',dict(record_key='recovered_score',request=raw_request(alias=alias)))
    assert record['status']=='computed',record
    report=analysis_report(alias=alias,output_name='A',mapped=True)
    report['calculation_records']=[record]
    write_analysis(opened,report)
    submitted=worker.call_tool('worker_submit_result',{})
    assert submitted['state']=='completed',submitted
    status=system[2].call_tool('run_status',{'name':'analysis'})
    assert len(status['evidence_outputs'])==4  # inspection, accepted raw file, calculation, manifest
    assert status['sealed_output']['payload']['calculation_records']==[record]
    assert (directory/'work/A_actual.plx').exists()


def test_new_run_replays_original_record_from_sealed_evidence(tmp_path):
    from copy import deepcopy
    from tests.operations.test_tcad_result_analysis import raw_request,analysis_report,write_analysis,open_analysis
    system,worker,opened,_=recovery_system(tmp_path)
    inspected=worker.call_tool('worker_tcad_inspect_outputs',{'relative_path':'A_actual.plx'})
    accepted=worker.call_tool('worker_tcad_accept_output',dict(evidence_alias=inspected['evidence_alias'],output_name='A',rationale='Exact fixture mapping.',evidence_aliases=[inspected['evidence_alias']]))
    alias=accepted['evidence_alias']
    calculation=worker.call_tool('worker_tcad_curve_score',dict(record_key='original',request=raw_request(alias=alias)))
    report=analysis_report(alias=alias,output_name='A',mapped=True); report['calculation_records']=[calculation]
    write_analysis(opened,report)
    assert worker.call_tool('worker_submit_result',{})['state']=='completed'
    catalog,runtime,root,request,artifacts,register=system
    request=deepcopy(request);request['name']='next_analysis'
    request['inputs'].extend([dict(port='prior_analysis',artifact_names=['analysis.output']), dict(port='recovery_manifest',artifact_names=['analysis.output.recovery_manifest']),dict(port='solver_outputs',artifact_names=['analysis.output.'+alias])])
    # An old audit covers only original products, not evidence obtained later.
    from scidiscovery.artifact_agent.schema.common import canonical_json
    original_inputs = runtime.runs.status(worker._run_id).inputs
    manifest_ref = next(i.artifact_ref for i in original_inputs if i.port_name == 'runtime_manifest')
    audit = dict(schema_version=1, verdict='pass', terminal_state='succeeded', exit_code=0,
        checks=[dict(check_key='fixture', status='pass', rationale='Original execution scope only.')],
        solver_native_output_count=0, transport_derived_output_count=0, parser_derived_output_count=0,
        rationale='Does not attest subsequently recovered bytes.')
    register('old_audit', canonical_json(audit), 'tcad.runtime-attestation.v1',
             parents=(artifacts['package'].ref, manifest_ref))
    request['inputs'].append(dict(port='runtime_attestation', artifact_names=['old_audit']))
    from tests.operations.test_collector_analysis_handoff import _collect_execution
    foreign = _collect_execution(system, tmp_path/'foreign', name='foreign', output_names=('A',))
    wrong = deepcopy(request)
    next(i for i in wrong['inputs'] if i['port']=='solver_outputs')['artifact_names'] = [foreign['A']]
    assert not root.call_tool('operation_preflight', wrong)['admissible']
    preflight=root.call_tool('operation_preflight',request)
    assert preflight['admissible'],preflight
    next_worker,next_opened=open_analysis((catalog,runtime,root,request,artifacts,register))
    import json
    from scidiscovery.operation_contract import DiagnosticError
    assignment=json.loads(Path(next_opened['assignment_path']).read_text())
    current_alias=assignment['prior_source_bindings'][alias]
    assert current_alias != alias
    with pytest.raises(DiagnosticError) as rejected:
        next_worker.call_tool('worker_tcad_curve_score',dict(record_key='old_alias',request=calculation['request']))
    assert rejected.value.details[0]['code']=='source_unavailable'
    # B scores the bound A file under its current alias, without accepting it again.
    replay=next_worker.call_tool('worker_tcad_curve_score',dict(record_key='second',request=raw_request(alias=current_alias)))
    second_report=analysis_report(alias=current_alias,output_name='A',mapped=True)
    second_report['calculation_records']=[replay]
    write_analysis(next_opened,second_report)
    submitted=next_worker.call_tool('worker_submit_result',{})
    assert submitted['state']=='completed',submitted
    second_status=root.call_tool('run_status', {'name':'next_analysis'})
    assert len(second_status['evidence_outputs'])==2  # saved calculation and manifest
    assert [item['metadata']['kind'] for item in json.loads(runtime.runs._evidence_snapshot(next_worker._run_id))['records']]==['calculation_record']
    # C needs B's calculation proof and A's original collection proof separately.
    third=deepcopy(request);third['name']='third_analysis'
    next(i for i in third['inputs'] if i['port']=='prior_analysis')['artifact_names']=['next_analysis.output']
    third['inputs'].append(dict(port='prior_analysis_manifest',artifact_names=['next_analysis.output.recovery_manifest']))
    next(i for i in third['inputs'] if i['port']=='solver_outputs')['artifact_names']=[
        'analysis.output.'+inspected['evidence_alias'], 'analysis.output.'+alias]
    wrong_pair=deepcopy(third)
    wrong_pair['inputs']=[i for i in wrong_pair['inputs'] if i['port']!='recovery_manifest']
    next(i for i in wrong_pair['inputs'] if i['port']=='prior_analysis_manifest')['artifact_names']=['analysis.output.recovery_manifest']
    assert not root.call_tool('operation_preflight',wrong_pair)['admissible']
    third_worker,third_opened=open_analysis((catalog,runtime,root,third,artifacts,register))
    assignment=json.loads(Path(third_opened['assignment_path']).read_text())
    third_alias=assignment['prior_source_bindings'][current_alias]
    assert third_alias != current_alias
    retained=deepcopy(replay)
    retained['attempt']['manifest_alias']='prior_analysis_manifest'
    third_report=analysis_report(alias=third_alias,output_name='A',mapped=True)
    third_report['calculation_records']=[retained]
    write_analysis(third_opened,third_report)
    submitted=third_worker.call_tool('worker_submit_result',{})
    assert submitted['state']=='completed',submitted



@pytest.mark.parametrize('failure',['changed','symlink','budget','missing'])
def test_inspection_failures_remain_bounded(tmp_path,failure):
    system,worker,opened,directory=recovery_system(tmp_path)
    if failure=='missing':
        reply=worker.call_tool('worker_tcad_inspect_outputs',{'relative_path':'absent.plx'})
        assert reply['status']=='not_found'
    elif failure=='symlink':
        (directory/'work/foreign.plx').symlink_to(tmp_path/'outside')
        reply=worker.call_tool('worker_tcad_inspect_outputs',{'relative_path':'foreign.plx'})
        assert reply['status']=='unavailable'
    elif failure=='budget':
        system[1].runs.tool_io_budget(worker._run_id,used_bytes=256*1024*1024)
        reply=worker.call_tool('worker_tcad_inspect_outputs',{'relative_path':'A_actual.plx'})
        assert reply['status']=='limit_exceeded'
    else:
        reply=worker.call_tool('worker_tcad_inspect_outputs',{'relative_path':'A_actual.plx'})
        (directory/'work/A_actual.plx').write_bytes(b'changed')
        reply=worker.call_tool('worker_tcad_accept_output',dict(evidence_alias=reply['evidence_alias'],output_name='A',rationale='fixture mapping',evidence_aliases=['runtime_manifest']))
        assert reply['status']=='changed_since_inspection'
    from tests.operations.test_tcad_result_analysis import analysis_report,write_analysis
    write_analysis(opened,analysis_report())
    assert worker.call_tool('worker_submit_result',{})['state']=='completed'


def test_offline_tools_do_not_prevent_open_or_limited_submit(tmp_path):
    from tests.operations.test_tcad_result_analysis import analysis_system,open_analysis,analysis_report,write_analysis
    worker,opened=open_analysis(analysis_system(tmp_path))
    assert worker.call_tool('worker_tcad_inspect_outputs',{})['status']=='unavailable'
    write_analysis(opened,analysis_report())
    assert worker.call_tool('worker_submit_result',{})['state']=='completed'


def test_reopen_keeps_receipts_and_duplicate_accept_is_idempotent(tmp_path):
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    system,worker,opened,_=recovery_system(tmp_path)
    inspected=worker.call_tool('worker_tcad_inspect_outputs',{'relative_path':'A_actual.plx'})
    args=dict(evidence_alias=inspected['evidence_alias'],output_name='A',rationale='Exact mapping',evidence_aliases=[inspected['evidence_alias']])
    accepted=worker.call_tool('worker_tcad_accept_output',args)
    op=system[0].operation('tcad.result.analyze.v1')
    restarted=LocalWorkerMCPRouter(system[1].runs,operation_id=op.spec.operation_id,operation_digest=op.digest,tool_services=worker.tool_services)
    restarted.call_tool('worker_open_assignment',{})
    assert restarted.call_tool('worker_tcad_accept_output',args)['evidence_alias']==accepted['evidence_alias']
    assert len(system[1].runs.tool_evidence(restarted._run_id))==2


def test_failed_run_preserves_tool_evidence_for_new_bound_run(tmp_path):
    from copy import deepcopy
    from tests.operations.test_tcad_result_analysis import analysis_report,write_analysis,open_analysis
    system,worker,opened,directory=recovery_system(tmp_path)
    inspected=worker.call_tool('worker_tcad_inspect_outputs',{'relative_path':'A_actual.plx'})
    accepted=worker.call_tool('worker_tcad_accept_output',dict(evidence_alias=inspected['evidence_alias'],output_name='A',rationale='Exact mapping',evidence_aliases=[inspected['evidence_alias']]))
    report=analysis_report(alias=accepted['evidence_alias'],output_name='A',mapped=True)
    from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
    failure=MCPRouter(worker,name='probe').handle({'jsonrpc':'2.0','id':1,'method':'tools/call',
        'params':{'name':'worker_tcad_curve_score','arguments':{'record_key':[], 'request':{}}}})
    from curve_score.analysis_tool import ALGORITHM_VERSION
    details=failure['error']['data']
    report['calculation_records']=[dict(record_key='prior_failure', request={}, input_digests={},
        algorithm_version=ALGORITHM_VERSION, status='unavailable', reason_code='invalid_arguments',
        attempt=details['attempt'], diagnostics=details['diagnostics'])]
    original_receipts=system[1].runs.tool_evidence(worker._run_id)
    write_analysis(opened,report)
    catalog,runtime,root,request,artifacts,register=system
    status=root.call_tool('run_status',{'name':'analysis'})
    failed=root.call_tool('run_record_failure',dict(name='analysis',reason='fixture transport interruption',expected_state='running',expected_last_activity_at=status['last_activity_at']))
    assert failed['recovery']['draft_available'], (failed['recovery'], runtime.runs.status(worker._run_id).recovery_draft)
    assert not failed.get('evidence_outputs')
    # Remote bytes are no longer needed to use the already accepted, preserved copy.
    (directory/'work/A_actual.plx').unlink()
    request=deepcopy(request);request.update(name='resumed',draft_from='analysis')
    next_worker,next_opened=open_analysis((catalog,runtime,root,request,artifacts,register))
    assert len(runtime.runs.tool_evidence(next_worker._run_id))==2
    assert runtime.runs.tool_evidence(next_worker._run_id)==original_receipts
    # Old attempt proof is retained in the old draft, not renamed a current call.
    import json
    proofs=list((Path(next_opened['workspace_path'])/'recovery-draft').rglob('tool-evidence.json'))
    assert len(proofs)==1
    assert json.loads(proofs[0].read_text())['attempts'][0]['state']=='rejected'
    assert runtime.runs.tool_attempts(next_worker._run_id)==[]
    # Only the control-verified original proof may support this failure claim.
    report['calculation_records'][0]['attempt']['proof_kind']='recovery'
    bad=deepcopy(report)
    bad['calculation_records'][0]['attempt']['proof_kind']='current'
    write_analysis(next_opened,bad)
    assert next_worker.call_tool('worker_submit_result',{})['state']=='rejected'
    write_analysis(next_opened,report)
    submitted=next_worker.call_tool('worker_submit_result',{})
    assert submitted['state']=='completed',submitted
    # A normal later analysis can still verify the failed origin via completed B.
    third=deepcopy(request);third.update(name='after_recovery');third.pop('draft_from')
    raw_names=['resumed.output.'+r['alias'] for r in original_receipts]
    third['inputs'].extend([dict(port='prior_analysis',artifact_names=['resumed.output']),
        dict(port='recovery_manifest',artifact_names=['resumed.output.recovery_manifest']),
        dict(port='solver_outputs',artifact_names=raw_names)])
    final_worker,final_opened=open_analysis((catalog,runtime,root,third,artifacts,register))
    report['calculation_records'][0]['attempt']['manifest_alias']='recovery_manifest'
    alias=json.loads(Path(final_opened['assignment_path']).read_text())['prior_source_bindings'][accepted['evidence_alias']]
    report['source_references'][0]['input_alias']=alias
    report['evidence'][0]['locator']=alias
    write_analysis(final_opened,report)
    submitted=final_worker.call_tool('worker_submit_result',{})
    assert submitted['state']=='completed',submitted


def test_tool_evidence_cannot_change_after_candidate_acceptance(tmp_path):
    from tests.operations.test_tcad_result_analysis import analysis_report,write_analysis
    from scidiscovery.artifact_agent.service.run_records import RunStateConflict
    system,worker,opened,_=recovery_system(tmp_path)
    reply=worker.call_tool('worker_tcad_inspect_outputs',{'relative_path':'A_actual.plx'})
    runs=system[1].runs
    write_analysis(opened,analysis_report())
    value=runs.status(worker._run_id)
    sealed,validated=runs._validated_candidate(value)
    runs._accept_candidate(value.run_id,sealed.digest)
    with pytest.raises(RunStateConflict):
        runs.accept_tool_evidence(value.run_id,tool_name='worker_tcad_inspect_outputs',allowed_ports=('tool_evidence',),raw=b'late',media_type='text/plain',metadata={'relative_path':'late'})
    assert worker.call_tool('worker_submit_result',{})['state']=='completed'

@pytest.mark.parametrize('remote', [False, True])
def test_worker_preserves_solver_success_and_collection_failure(tmp_path, remote):
    import json
    import subprocess
    import sys
    from tcad_artifact import worker, remote_runner_py36
    work = tmp_path / 'work'
    work.mkdir()
    (work / 'main.cmd').write_text('echo raw > later.plx\nexit 0\n')
    expected = [dict(name=n, relative_path=p, required=True, max_bytes=1024, media_type='text/plain')
                for n, p in [('missing', 'missing.tdr'), ('later', 'later.plx')]]
    job = dict(executable='/bin/sh', arguments=['main.cmd'], environment={},
               execution_purpose='production', expected_outputs=expected,
               limits=dict(cpu_time_seconds=5, wall_time_seconds=5,
                           max_memory_bytes=128*1024*1024, max_output_bytes=1024*1024))
    (tmp_path / ('runtime.json' if remote else 'job.json')).write_text(json.dumps(job))
    command = ([sys.executable, '-c', "import runpy,sys; raise SystemExit(runpy.run_path(sys.argv[1])['_run_worker']({},sys.argv[2]))", remote_runner_py36.__file__, str(tmp_path)]
               if remote else [sys.executable, worker.__file__, str(tmp_path)])
    result = subprocess.run(command, capture_output=True, timeout=15)
    assert result.returncode == 97, result.stderr
    manifest = json.loads((tmp_path / 'output_manifest.json').read_bytes())
    assert manifest['solver_exit_code'] == 0 and manifest['exit_code'] == 97
    assert [item['name'] for item in manifest['outputs']] == ['later']
    assert len(manifest['collection_errors']) == 1


def test_command_ssh_remote_inspection_roundtrip(tmp_path):
    import json
    import os
    import sys
    from tcad_artifact.command_adapter import CommandAdapterConfig, CommandTCADExecutorAdapter
    run_id = 'run_' + 'a'*32
    directory = tmp_path / 'remote' / run_id
    (directory / 'work').mkdir(parents=True)
    (directory / 'done').touch()
    (directory / 'work/actual.plx').write_bytes(b'original bytes')
    script = tmp_path / 'transport.py'
    script.write_text('''import json,sys
from pathlib import Path
from tcad_artifact.ssh_transport import SSHTCADTransport
from tcad_artifact.remote_runner_py36 import _rpc
root=Path(sys.argv[1])
class Remote:
    def rpc(self,request): return _rpc({'result_root':str(root/'remote')},{'request':request})
    def get_to(self,path,destination,max_bytes):
        raw=Path(path).read_bytes()
        assert len(raw)<=max_bytes
        destination.write_bytes(raw)
transport=SSHTCADTransport(Remote(),local_result_root=root/'local')
request=json.load(sys.stdin)
value=transport.handle(request['operation'],request['payload'])
print(json.dumps(dict(schema_version=1,operation=request['operation'],ok=True,payload=value)))
''')
    adapter = CommandTCADExecutorAdapter(CommandAdapterConfig(executable=sys.executable,
        arguments=(str(script), str(tmp_path)), environment={'PYTHONPATH':os.pathsep.join(sys.path)}),
        local_result_root=tmp_path/'local')
    listed = adapter.inspect_outputs(run_id)
    assert listed['status'] == 'available' and listed['files'][0]['relative_path'] == 'actual.plx'
    value = adapter.inspect_outputs(run_id, 'actual.plx')
    assert value['status'] == 'available'
    assert Path(value['file']['local_path']).read_bytes() == b'original bytes'
    assert adapter.inspect_outputs(run_id, 'actual.plx', max_bytes=1)['status'] == 'limit_exceeded'
    assert (directory/'work/actual.plx').read_bytes() == b'original bytes'


def test_forged_workspace_receipt_cannot_publish_evidence(tmp_path):
    from tests.operations.test_tcad_result_analysis import analysis_report,write_analysis
    system, worker, opened, _ = recovery_system(tmp_path)
    output = Path(opened['workspace_path'])/'output'
    (output/'tool-evidence.json').write_text('{"schema_version":1,"records":[{"alias":"forged"}]}')
    write_analysis(opened, analysis_report())
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    evidence=system[2].call_tool('run_status', {'name':'analysis'})['evidence_outputs']
    assert evidence==[dict(artifact_name='analysis.output.recovery_manifest',schema='scidiscovery.tool-evidence-manifest.v1')]
    assert json.loads(system[1].runs._evidence_snapshot(worker._run_id))['records']==[]


def test_ssh_inspection_download_streams_through_remote_protocol(tmp_path, monkeypatch):
    import json
    import subprocess
    import sys
    from tcad_artifact.ssh_transport import SSHRemoteClient, SSHTCADTransportConfig
    from tcad_artifact import remote_runner_py36
    raw = b'0123456789' * 220000
    source = tmp_path/'source'
    source.write_bytes(raw)
    client = SSHRemoteClient(SSHTCADTransportConfig(ssh_executable=sys.executable,
        destination='a@fixture',remote_helper='/fixture/helper',remote_config='/fixture/config',remote_exchange_root='/fixture/exchange'))
    def run(command, **kwargs):
        assert kwargs['stdout'] != subprocess.PIPE
        code = "import runpy,sys,json; m=runpy.run_path(sys.argv[1]); m['_handle'](json.loads(sys.argv[2]),json.loads(sys.stdin.buffer.readline()),sys.stdin.buffer,sys.stdout.buffer)"
        return subprocess.run([sys.executable,'-c',code,remote_runner_py36.__file__,
                               json.dumps({'result_root':str(tmp_path),'max_transfer_bytes':4*1024*1024})], **kwargs)
    monkeypatch.setattr(client, '_run', run)
    target = tmp_path/'download'
    client.get_to(str(source), target, len(raw))
    assert target.read_bytes() == raw


def test_socket_inspection_uses_existing_execution_router(tmp_path):
    import json
    import multiprocessing
    import time
    from scidiscovery.interfaces.daemon import UnixSocketDaemon
    from tcad_artifact.execution_control import TCADExecutionFacade,TCADExecutionPolicy,TCADExecutionRouter,ToolProfile
    from tcad_artifact.execution_adapter import TCADExecutorAdapter
    facade = TCADExecutionFacade(policy=TCADExecutionPolicy(allowed_input_roots=(str(tmp_path),),
        tools=(ToolProfile(profile_id='fixture',solver_kind='deterministic_tool',executable='/bin/true',release_evidence='fixture'),)), state_root=tmp_path/'state')
    directory = facade.runs_root/'terminal_fixture'
    (directory/'work').mkdir(parents=True)
    (directory/'work/actual').write_bytes(b'raw')
    (directory/'done').touch()
    (directory/'output_manifest.json').write_text(json.dumps({'terminal_state':'succeeded','exit_code':0}))
    import sqlite3
    with sqlite3.connect(facade.database_path) as connection:
        connection.execute('INSERT INTO submissions VALUES (?,?,?,?)', ('a'*64,'terminal_fixture','2026-09-09T00:00:00Z','terminal'))
    socket = tmp_path/'control.sock'
    from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
    process = multiprocessing.get_context('fork').Process(target=UnixSocketDaemon(socket,MCPRouter(TCADExecutionRouter(facade),name='tcad-control')).serve_forever)
    process.start()
    try:
        deadline=time.monotonic()+5
        while not socket.exists() and time.monotonic()<deadline:
            time.sleep(.02)
        result=TCADExecutorAdapter(socket).inspect_outputs('terminal_fixture','actual')
        assert result['status']=='available' and result['file']['size_bytes']==3
    finally:
        process.terminate()
        process.join(5)
        assert not process.is_alive()


def test_reserved_io_budget_cannot_be_spent_by_another_router(tmp_path):
    system, worker, _, _ = recovery_system(tmp_path)
    service = system[1].runs
    reserved = service.tool_io_budget(worker._run_id, reserve=True)
    assert reserved['remaining_seconds'] == 120
    assert service.tool_io_budget(worker._run_id, reserve=True)['remaining_seconds'] == 0
    service.tool_io_budget(worker._run_id, used_bytes=-reserved['remaining_bytes']+10, used_seconds=-119)
    assert service.tool_io_budget(worker._run_id)['remaining_seconds'] == 119


def test_optional_service_startup_failure_does_not_relax_author_requirement(tmp_path, monkeypatch):
    from tests.operations.test_tcad_result_analysis import analysis_system
    import scidiscovery.artifact_agent.interfaces.mcp_local_worker as module
    catalog = analysis_system(tmp_path)[0]
    def broken(*args, **kwargs):
        raise FileNotFoundError('missing transport configuration')
    monkeypatch.setattr(module, 'load_runtime_plugin_contributions', broken)
    assert module._load_operation_services(catalog, 'tcad.result.analyze.v1',
        {'tcad_artifact':tmp_path/'absent'}, tmp_path) == {}
    with pytest.raises(FileNotFoundError):
        module._load_operation_services(catalog, 'tcad.deck.author.initial.v1',
            {'tcad_artifact':tmp_path/'absent'}, tmp_path)


def test_collection_declaration_without_trusted_tool_is_rejected_at_both_gates(tmp_path, monkeypatch):
    from dataclasses import replace
    from types import SimpleNamespace
    from tests.operations.test_tcad_result_analysis import analysis_system
    from scidiscovery.artifact_agent.service.local_workspace import LocalTrustedBackend
    from scidiscovery.artifact_agent.service.runs import RunError
    catalog, runtime, *_ = analysis_system(tmp_path)
    operation = catalog.operation('tcad.result.analyze.v1')
    executor = operation.spec.executor.model_copy(update={'tools':()})
    undeclared = replace(operation,worker_tools=(),spec=operation.spec.model_copy(update={'executor':executor}))
    assert LocalTrustedBackend.unsupported_requirements(undeclared) == ('agent_collection_outputs',)
    monkeypatch.setattr(runtime.runs.backend, 'supports_operation', lambda _: True)
    with pytest.raises(RunError, match='output collections'):
        runtime.runs.schedule(SimpleNamespace(compiled=undeclared), instance_id='unused',
            output_binding_name='unused',output_logical_name='unused',output_revision=1,
            output_binding_fingerprint='unused')


def test_corrupt_retained_evidence_is_engineering_failure(tmp_path, monkeypatch):
    from tests.operations.test_tcad_result_analysis import analysis_report,write_analysis
    system, worker, opened, _ = recovery_system(tmp_path)
    inspected = worker.call_tool('worker_tcad_inspect_outputs', {'relative_path':'A_actual.plx'})
    record = system[1].runs.tool_evidence(worker._run_id)[0]
    original_read = system[1].artifacts.read
    def read(ref):
        return b'corrupted' if ref.model_dump(mode='json') == record['artifact_ref'] else original_read(ref)
    write_analysis(opened, analysis_report(alias=inspected['evidence_alias']))
    monkeypatch.setattr(system[1].artifacts, 'read', read)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'failed'
    assert system[2].call_tool('run_status', {'name':'analysis'})['recovery']['delivery_preserved']


def test_old_runner_tool_error_allows_limited_report(tmp_path):
    from tcad_artifact.output_recovery import OutputInspectionService
    from tests.operations.test_tcad_result_analysis import analysis_report,write_analysis
    system, worker, opened, _ = recovery_system(tmp_path)
    class OldAdapter:
        def inspect_outputs(self, *args, **kwargs):
            raise RuntimeError('unknown runner tool')
    worker.tool_services['tcad_artifact:tcad.output_inspection'] = OutputInspectionService(OldAdapter())
    assert worker.call_tool('worker_tcad_inspect_outputs', {})['status'] == 'unsupported'
    write_analysis(opened, analysis_report())
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'


def test_unmapped_inspection_remains_readable_as_next_run_background(tmp_path):
    from copy import deepcopy
    from tests.operations.test_tcad_result_analysis import analysis_report,write_analysis,open_analysis
    system, worker, opened, _ = recovery_system(tmp_path)
    inspected = worker.call_tool('worker_tcad_inspect_outputs', {'relative_path':'A_actual.plx'})
    alias = inspected['evidence_alias']
    write_analysis(opened, analysis_report(alias=alias))
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    catalog,runtime,root,request,artifacts,register = system
    request = deepcopy(request)
    request['name'] = 'background_analysis'
    request['inputs'].extend([dict(port='recovery_manifest',artifact_names=['analysis.output.recovery_manifest']),
                              dict(port='solver_outputs',artifact_names=['analysis.output.'+alias])])
    next_worker,next_opened = open_analysis((catalog,runtime,root,request,artifacts,register))
    write_analysis(next_opened, analysis_report(alias='solver_outputs'))
    submitted=next_worker.call_tool('worker_submit_result', {})
    assert submitted['state'] == 'completed',submitted

@pytest.mark.parametrize('solver_code,terminal', [(None,'failed'),(0,'failed'),(1,'failed'),(0,'cancelled')])
def test_collection_97_preserves_solver_facts_without_deciding_local_findings(tmp_path, solver_code, terminal):
    import json
    from scidiscovery.artifact_agent.schema.common import canonical_json
    from tcad_artifact.project_packager import TCADRuntimeManifest
    from tests.operations.test_tcad_result_analysis import analysis_system,analysis_report,open_analysis,write_analysis
    system=analysis_system(tmp_path)
    catalog,runtime,root,request,artifacts,register=system
    manifest=json.loads(runtime.artifacts.read(artifacts['manifest'].ref))
    manifest.update(exit_code=97,terminal_state=terminal,error='fixture collection failure')
    if solver_code is not None:
        manifest['solver_exit_code']=solver_code
    raw=canonical_json(manifest)
    assert TCADRuntimeManifest.model_validate_json(raw).solver_exit_code==solver_code
    registered = register('collection_manifest',raw,'opaque',parents=artifacts['manifest'].parent_refs)
    next(i for i in request['inputs'] if i['port']=='runtime_manifest')['artifact_names']=['collection_manifest']
    worker,opened=open_analysis(system)
    report=analysis_report(alias='solver_outputs_001',output_name='A',mapped=True)
    report['gates']['numerical_validity']['status']='pass'
    report['gates']['numerical_validity']['summary']='Fixture local numerical condition is supported by the raw product; no overall success claimed.'
    report['gates']['control_equivalence']=dict(status='fail',summary='Control mismatch remains.',evidence_keys=['raw_evidence'])
    write_analysis(opened,report)
    result=worker.call_tool('worker_submit_result',{})
    assert result['state']=='completed',result
    # A local scientific assessment never rewrites the actual execution record.
    actual = TCADRuntimeManifest.model_validate_json(runtime.artifacts.read(registered.ref))
    assert actual.terminal_state == terminal and actual.solver_exit_code == solver_code


def test_native_plx_declared_as_text_plain_scores_without_relabeling(tmp_path):
    import json
    from scidiscovery.artifact_agent.schema.common import canonical_json
    from tests.operations.test_tcad_result_analysis import analysis_system,analysis_report,open_analysis,write_analysis,raw_request
    system=analysis_system(tmp_path)
    catalog,runtime,root,request,artifacts,register=system
    package=json.loads(runtime.artifacts.read(artifacts['package'].ref))
    for output in package['project']['expected_outputs']:
        output['media_type']='text/plain'
    new_package=register('text_package',canonical_json(package),'tcad.reviewed-deck-package.v2',parents=artifacts['package'].parent_refs)
    manifest=json.loads(runtime.artifacts.read(artifacts['manifest'].ref))
    for output in manifest['outputs']:
        output['media_type']='text/plain'
    new_manifest=register('text_manifest',canonical_json(manifest),'opaque',parents=(new_package.ref,))
    register('text_output',runtime.artifacts.read(artifacts['output_A'].ref),'opaque',parents=new_manifest.parent_refs,media='text/plain',output_name='A')
    replacements={'reviewed_package':'text_package','runtime_manifest':'text_manifest','solver_outputs':'text_output'}
    for item in request['inputs']:
        if item['port'] in replacements:
            item['artifact_names']=[replacements[item['port']]]
    worker,opened=open_analysis(system)
    record=worker.call_tool('worker_tcad_curve_score',dict(record_key='plain',request=raw_request(alias='solver_outputs')))
    assert record['status']=='computed',record
    report=analysis_report(alias='solver_outputs',output_name='A',mapped=True)
    report['calculation_records']=[record]
    write_analysis(opened,report)
    assert worker.call_tool('worker_submit_result',{})['state']=='completed'


def test_corrupt_preserved_receipt_fails_successor_open_explicitly(tmp_path, monkeypatch):
    from copy import deepcopy
    from tests.operations.test_tcad_result_analysis import analysis_report,write_analysis,open_analysis
    system,worker,opened,_=recovery_system(tmp_path)
    worker.call_tool('worker_tcad_inspect_outputs',{'relative_path':'A_actual.plx'})
    catalog,runtime,root,request,artifacts,register=system
    record=runtime.runs.tool_evidence(worker._run_id)[0]
    write_analysis(opened,analysis_report())
    status=root.call_tool('run_status',{'name':'analysis'})
    root.call_tool('run_record_failure',dict(name='analysis',reason='fixture interruption',expected_state='running',expected_last_activity_at=status['last_activity_at']))
    original_read=runtime.artifacts.read
    monkeypatch.setattr(runtime.artifacts,'read',lambda ref: b'corrupt' if ref.model_dump(mode='json')==record['artifact_ref'] else original_read(ref))
    request=deepcopy(request)
    request.update(name='corrupt_successor',draft_from='analysis')
    with pytest.raises(Exception,match='preserved tool evidence integrity failure'):
        open_analysis((catalog,runtime,root,request,artifacts,register))
    assert root.call_tool('run_status',{'name':'corrupt_successor'})['state']=='failed'
