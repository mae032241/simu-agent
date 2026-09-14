import json, multiprocessing, subprocess, sys, tempfile, time, tomllib
from pathlib import Path
import scidiscovery.artifact_agent.interfaces.mcp_root as root_module
import tcad_artifact.parameter_operations as parameter_module
import curve_score.analysis_workspace as analysis_module
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_daemon import RootBrokerRouter
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.interfaces.daemon import UnixSocketDaemon
from scidiscovery.platforms.codex import SCHEDULER_TOOLS, _proxy_server_toml
for module in (root_module,parameter_module,analysis_module):
    assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()), module.__file__
catalog=compile_installed_catalog()
assert len([name for name in catalog.operation_ids() if catalog.operation(name).spec.executor.kind=='agent'])==25
assert 'artifact_ingest_text' in SCHEDULER_TOOLS
generated=tomllib.loads(_proxy_server_toml(python=Path(sys.executable), socket_path=Path('/tmp/installed-context.sock'), python_path=None))
assert generated['mcp_servers']['scidiscovery']['enabled_tools']==list(SCHEDULER_TOOLS)
assert SCHEDULER_TOOLS==tuple(tool.name for tool in root_module.ROOT_TOOLS)
repository=Path(sys.argv[1]);sys.path.append(str(repository));sys.path.append(str(repository/'tests/operations'))
from tests.operations.test_tcad_result_analysis import analysis_system, analysis_report, write_analysis
with tempfile.TemporaryDirectory(prefix='user-text-installed-') as temp:
    base=Path(temp); case=base/'case';case.mkdir()
    _,runtime,root,request,_,_=analysis_system(case)
    operation=catalog.operation('tcad.result.analyze.v1')
    assert root.facade._operation_catalog.operation(operation.spec.operation_id).digest==operation.digest
    worker=LocalWorkerMCPRouter(runtime.runs,operation_id=operation.spec.operation_id,operation_digest=operation.digest)
    def serve(socket,router):
        UnixSocketDaemon(socket,RootBrokerRouter(lambda _:MCPRouter(router,name='installed-fixture'))).serve_forever()
    processes=[]
    try:
        for label,router in [('root',root),('worker',worker)]:
            socket=base/(label+'.sock'); process=multiprocessing.get_context('fork').Process(target=serve,args=(socket,router));process.start();processes.append(process)
            deadline=time.monotonic()+5
            while not socket.exists() and time.monotonic()<deadline:time.sleep(.02)
            assert socket.exists()
        def rpc(label,method,params=None):
            packet=dict(jsonrpc='2.0',id=1,method=method)
            if params is not None:packet['params']=params
            response=subprocess.run([sys.executable,'-I','-m','scidiscovery.artifact_agent.interfaces.mcp_proxy','--socket',str(base/(label+'.sock')),'--timeout','10'],input=json.dumps(packet)+'\n',text=True,capture_output=True,timeout=15)
            assert response.returncode==0,response.stderr
            reply=json.loads(response.stdout);assert 'error' not in reply,reply
            return reply['result']
        def call(label,name,args):
            reply=rpc(label,'tools/call',dict(name=name,arguments=args));assert not reply.get('isError'),reply
            return reply['structuredContent']
        listed=rpc('root','tools/list')['tools'];tool=next(item for item in listed if item['name']=='artifact_ingest_text')
        assert tool['inputSchema']['properties']['text']['maxLength']==8192
        original='  Installed user text: 独立判断这条建议。\r\n𐀀\n'
        frozen=call('root','artifact_ingest_text',dict(name='supplement',text=original))
        assert frozen==call('root','artifact_ingest_text',dict(name='supplement',text=original))
        old=None
        for index in range(2):
            current=json.loads(json.dumps(request));current['name']=f'installed_analysis_{index}'
            current['inputs'].append(dict(port='user_context',artifact_names=[frozen['name']]))
            if old:current['inputs'].append(dict(port='current_progress',artifact_names=[old]))
            assert call('root','operation_preflight',current)['admissible']
            assert call('root','operation_invoke',current)['result']['state']=='queued'
            opened=call('worker','worker_open_assignment',{})
            assignment=json.loads(Path(opened['assignment_path']).read_bytes())
            entry,=[item for item in assignment['inputs'] if item['port']=='user_context']
            assert entry['source_origin']=='user_via_scheduler'
            assert Path(opened['workspace_path'],entry['relative_path']).read_bytes()==original.encode()
            write_analysis(opened,analysis_report())
            assert call('worker','worker_submit_result',{})['state']=='completed'
            status=call('root','run_status',dict(name=current['name'],output_paths=['/summary']))
            assert status['state']=='completed' and status['selected_output']['items'][0]['status']=='selected',status
            old=status['output_artifact_name']
        assert [p['port'] for p in status['bound_inputs']].count('user_context')==1
    finally:
        for process in processes:
            process.terminate();process.join(5)
            if process.is_alive():process.kill();process.join(5)
print(json.dumps(dict(installed_modules=True,catalog_agents=25,root_stdio=True,worker_stdio=True,original_utf8=True,local_runs=2,reused_worker=True,live_scientific_agent=False)))
