import sys, json, tempfile
from pathlib import Path
repo=Path.cwd()
sys.path[:0]=[str(repo/p) for p in ('src','.','plugins/tcad_artifact','plugins/curve_score','plugins/curve_figure_evidence','tests/operations')]
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
import test_l4_local_tcad as f
from tests.operations.test_validation_responsibility_placement import test_review_submission_derives_handoff_from_formal_verdict
from tests.operations.test_analysis_handoff_report import test_tcad_compact_report_seals_and_preserves_scientific_claim
from tests.operations.test_tcad_result_analysis import analysis_system,open_analysis,write_analysis,analysis_report
out=Path(__file__).parent; rows=[]; records=[]
original=RootMCPRouter.call_tool
def capture(self,name,args):
 result=original(self,name,args)
 if name=='run_status' and result['state']=='completed':
  records.append(result); rows.append(dict(kind='run_status',schema=result['sealed_output']['schema'],bytes=len(canonical_json(result))))
 return result
RootMCPRouter.call_tool=capture
old_open=LocalWorkerMCPRouter._open
def capture_open(self):
 result=old_open(self); rows.append(dict(kind='open',operation=self.operation_id,bytes=len(canonical_json(result))))
 return result
LocalWorkerMCPRouter._open=capture_open
with tempfile.TemporaryDirectory(prefix='scid-handoff-fixture-') as temp:
 base=Path(temp)
 def case(name):
  p=base/name;p.mkdir();return p
 f.test_local_tcad_author_debug_and_independent_review_share_one_operation_path(case('complete'),'pass')
 test_review_submission_derives_handoff_from_formal_verdict(case('review'))
 test_tcad_compact_report_seals_and_preserves_scientific_claim(case('compact'),'inconclusive')
 system=analysis_system(case('legacy'));worker,opened=open_analysis(system);write_analysis(opened,analysis_report());assert worker.call_tool('worker_submit_result',{})['state']=='completed';system[2].call_tool('run_status',{'name':'analysis'})
 p=case('long-gap');catalog,runtime,root,_=f._system(p,solver_kind='sprocess');inputs=[dict(port='execution_capability',artifact_names=['execution_capability']),dict(port='experiment_plan',artifact_names=['experiment_plan'])];f._invoke(root,'long_gap','tcad.deck.author.initial.v1',inputs);worker=f._debug_worker(catalog,runtime,f._ImmediateDebugAdapter(),p/'debug');opened=worker.call_tool('worker_open_assignment',{});f._write_gap(opened);Path(opened['workspace_path'],'deck/reports/failure.log').write_text('LARGE_LOG_MARKER fixture initialization failed.\n'*4096);assert worker.call_tool('worker_submit_result',{})['state']=='completed';root.call_tool('run_status',{'name':'long_gap'})
(out/'baseline-statuses.json').write_bytes(canonical_json(records));(out/'baseline-sizes.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows))
