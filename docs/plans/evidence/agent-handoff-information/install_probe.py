import json, multiprocessing, subprocess, sys, tempfile, time
from pathlib import Path
import scidiscovery.artifact_agent.interfaces.mcp_root as root_module
import tcad_artifact.operation_workspace as tcad_module
import curve_score.science_operations as curve_module
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_daemon import RootBrokerRouter
from scidiscovery.interfaces.daemon import UnixSocketDaemon
for module in (root_module, tcad_module, curve_module):
    assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()), module.__file__
catalog = compile_installed_catalog()
assert catalog.operation('science.object.review.v1')
# Import test fixtures only after loading the product entirely from installed wheels.
repository = Path(sys.argv[1]); sys.path.append(str(repository)); sys.path.append(str(repository/'tests/operations'))
from tests.operations.test_run_status_output_selection import gap_run
from tests.operations.test_analysis_handoff_report import (
    test_scientific_review_can_submit_one_formal_summary,
    test_tcad_compact_report_seals_and_preserves_scientific_claim,
    test_other_analysis_operations_finalize_compact_drafts_through_mcp)
from tests.operations.test_tcad_gap_continuation import test_formal_gap_and_review_need_no_mechanical_summary_edits
with tempfile.TemporaryDirectory(prefix='handoff-installed-') as temp:
    base = Path(temp)
    def case(name):
        path=base/name;path.mkdir();return path
    runtime,root,_=gap_run(case('root'))
    for name in ('tcad.deck.author.initial.v1','tcad.deck.review.v1','science.object.review.v1'):
        assert root.facade._operation_catalog.operation(name).digest == catalog.operation(name).digest
    socket=base/'root.sock'
    def serve():
        UnixSocketDaemon(socket,RootBrokerRouter(lambda _: MCPRouter(root,name='installed-fixture'))).serve_forever()
    process=multiprocessing.get_context('fork').Process(target=serve);process.start()
    try:
        deadline=time.monotonic()+5
        while not socket.exists() and time.monotonic()<deadline:
            time.sleep(.02)
        assert socket.exists()
        def rpc(method,params=None):
            request=dict(jsonrpc='2.0',id=1,method=method)
            if params is not None:request['params']=params
            response=subprocess.run([sys.executable,'-m','scidiscovery.artifact_agent.interfaces.mcp_proxy',
                '--socket',str(socket),'--timeout','5'],input=json.dumps(request)+'\n',text=True,capture_output=True,timeout=10)
            assert response.returncode==0,response.stderr
            reply=json.loads(response.stdout);assert 'error' not in reply,reply
            return reply['result']
        listed=rpc('tools/list')
        tool=next(item for item in listed['tools'] if item['name']=='run_status')
        assert 'output_paths' in tool['inputSchema']['properties']
        def status(**args):
            return rpc('tools/call',dict(name='run_status',arguments=dict(name='gap',**args)))['structuredContent']
        full=status();omitted=status(output_paths=[]);nav=status(output_paths=['']);selected=status(output_paths=['/summary','/affected_work'])
        assert omitted['sealed_output'] is None and omitted['scheduler_signal_status']=='available'
        assert nav['selected_output']['items'][0]['status']=='omitted'
        assert selected['selected_output']['items'][0]['value']==full['sealed_output']['payload']['summary']
        sizes={name:len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode()) for name,value in
            [('full',full),('omitted',omitted),('navigation',nav),('selected',selected)]}
        assert sizes['omitted']+sizes['navigation']+sizes['selected']<sizes['full']
    finally:
        process.terminate();process.join(5)
        if process.is_alive():process.kill();process.join(5)
    test_scientific_review_can_submit_one_formal_summary(case('review'),False)
    test_formal_gap_and_review_need_no_mechanical_summary_edits(case('gap'),'untouched')
    test_tcad_compact_report_seals_and_preserves_scientific_claim(case('tcad-analysis'),'inconclusive')
    for kind in ('generic','curve_error'):
        test_other_analysis_operations_finalize_compact_drafts_through_mcp(case(kind),kind)
print(json.dumps(dict(installed_modules=True,stdio=True,formal_drafts=True,analysis_entries=3,reply_bytes=sizes)))
