"""One isolated wheel/stdio recovery smoke; no production state or scientific Run."""
import ast, json, os, subprocess, sys, tempfile, venv
from pathlib import Path
base=Path(__file__).resolve().parent
repo=base.parents[3]
for path in (repo, repo/'src', repo/'plugins/curve_score', repo/'plugins/tcad_artifact'):
 sys.path.insert(0,str(path))
from tests.operations.conftest import _supply_runtime_dependencies
from tests.operations import test_tcad_result_analysis as fixture
plan,package,manifest,plx,csv=fixture.analysis_materials(mapped=False)
source=Path(fixture.__file__).read_text()
functions=[]
for node in ast.parse(source).body:
 if isinstance(node,ast.FunctionDef) and node.name in {'analysis_system','analysis_report'}:
  text=ast.get_source_segment(source,node)
  text=text.replace('compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN))','compile_installed_catalog()')
  text=text.replace("_CURVE['_diagnosis']().model_dump(mode='json')",'deepcopy(report_fixture)')
  functions.append(text)
root=Path(tempfile.mkdtemp(prefix='scid-attempt-budget-installed-'))
def command(args):
 p=subprocess.run(args,cwd=root,capture_output=True,text=True,timeout=90)
 if p.returncode:raise RuntimeError(p.stdout[-2000:]+p.stderr[-4000:])
 return p.stdout
release=root/'release'
command([sys.executable,str(repo/'scripts/build_git_release.py'),'--source',str(repo),'--output',str(release)])
print('Clean release built',flush=True)
wheels=root/'wheels';wheels.mkdir()
for package_path in (release,release/'plugins/curve_score',release/'plugins/tcad_artifact'):
 command([sys.executable,'-m','pip','wheel','--no-deps','--no-build-isolation','--wheel-dir',str(wheels),str(package_path)])
print('Three wheels built serially',flush=True)
env=root/'venv';venv.EnvBuilder(with_pip=False).create(env)
_supply_runtime_dependencies(env)
site=env/'lib'/f'python{sys.version_info.major}.{sys.version_info.minor}'/'site-packages'
command([sys.executable,'-m','pip','install','--no-index','--no-deps','--no-compile','--target',str(site),*[str(p) for p in wheels.glob('*.whl')]])
print('Isolated runtime installed',flush=True)
preamble='''
from copy import deepcopy
import json, shutil, subprocess, sys, tempfile
from pathlib import Path
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.experiment import ExperimentPortfolio
from scidiscovery.operations.catalog import compile_installed_catalog
from tcad_artifact.project_packager import ReviewedDeckPackage
from scidiscovery.artifact_agent.service import local_process_observation
import curve_score.analysis_workspace as workspace_module
for module in (local_process_observation,workspace_module):
 assert Path(module.__file__).is_relative_to(Path(sys.prefix))
def analysis_materials(**unused):
 plan,package,manifest,plx,csv=materials
 return ExperimentPortfolio.model_validate_json(plan),ReviewedDeckPackage.model_validate_json(package),manifest,plx,csv
'''
body=r'''
root=Path(tempfile.mkdtemp(prefix='stdio-analysis-'))
catalog,runtime,facade,request,artifacts,register=analysis_system(root)
operation=catalog.operation('tcad.result.analyze.v1')
command=[sys.executable,'-I','-m','scidiscovery.artifact_agent.interfaces.mcp_local_worker',
 '--state-root',str(root/'state'),'--local-workspace-root',str(runtime.runs.backend.root),
 '--operation-id',operation.spec.operation_id,'--operation-digest',operation.digest]
def rpc(*calls):
 lines=[json.dumps(dict(jsonrpc='2.0',id=index,method='tools/call',params=dict(name=name,arguments=args)))
  for index,(name,args) in enumerate(calls,1)]
 proc=subprocess.run(command,input='\n'.join(lines)+'\n',text=True,capture_output=True,timeout=15)
 assert proc.returncode==0,proc.stderr
 results=[]
 for line in proc.stdout.splitlines():
  value=json.loads(line);assert 'error' not in value,value
  result=value['result'];results.append(result.get('structuredContent') or json.loads(result['content'][0]['text']))
 assert len(results)==len(calls),(proc.stdout,proc.stderr)
 return results
facade.call_tool('operation_invoke',request)
opened=rpc(('worker_open_assignment',{}))[0]
assert 'tool_contracts' not in opened
assert Path(opened['start_here_path']).is_file()
assert len(Path(opened['start_here_path']).read_bytes()) <= 24*1024
workspace=Path(opened['workspace_path']);scratch=workspace/'scratch'
assert json.loads((workspace/'domain-workspace.json').read_bytes())['paths']['recovery_manifest'] is None
probe=[sys.executable,'tools/local_process_observation.py','--timeout','5','--submission-reserve','0','--command',sys.executable,'-c']
assert subprocess.run(probe+['from pathlib import Path; Path("missing-recovery.json").read_text()'],cwd=workspace,capture_output=True,timeout=10).returncode==1
assert subprocess.run(probe+['print("ready")'],cwd=workspace,capture_output=True,timeout=10).returncode==0
observed=facade.call_tool('run_status',{'name':'analysis'})
assert observed['native_execution']['exit_code']==0
assert observed['diagnostic_summary']['latest_native_error']['error_type']=='FileNotFoundError'
assert observed['diagnostic_summary']['rejection_count']==0

script="""import json,sys
from pathlib import Path
if sys.argv[1] == 'compute':
 Path('calls.txt').write_text('1')
 Path('numbers.json').write_text('{"value":3}')
import fixture_plotter
"""
(scratch/'analysis.py').write_text(script)
launcher=[sys.executable,'tools/local_process_observation.py','--timeout','5','--submission-reserve','0','analysis.py']
failed=subprocess.run(launcher+['compute'],cwd=workspace,capture_output=True,timeout=10)
assert failed.returncode==1
numbers=(scratch/'numbers.json').read_bytes()
old_saved=rpc(('worker_open_assignment',{}),('worker_analysis_publish_files',dict(source_aliases=['reference_material'],script_path='scratch/analysis.py',files=[dict(path='scratch/numbers.json',media_type='application/json')],method='Fixture partial numerical work.')))[1]

status=facade.call_tool('run_status',{'name':'analysis'})
assert status['native_execution']['exit_code']==1
facade.call_tool('run_record_failure',dict(name='analysis',reason='controlled fixture plot failure',expected_state='running',expected_last_activity_at=status['last_activity_at']))
request=deepcopy(request);request.update(name='continued_analysis',draft_from='analysis')
register('new_reference',runtime.artifacts.read(artifacts['reference'].ref),'opaque',media='text/csv')
next(i for i in request['inputs'] if i['port']=='reference_material')['artifact_names']=['new_reference']

assert facade.call_tool('operation_preflight',request)['admissible']
facade.call_tool('operation_invoke',request)
opened=rpc(('worker_open_assignment',{}))[0]
assert opened['recovery_evidence']['preserved_count']==2
assert opened['recovery_evidence']['adopted_count']==0
assert opened['recovery_evidence']['not_adopted_record_indices']==[0,1]
assert facade.call_tool('run_status',{'name':'continued_analysis'})['recovery']['tool_evidence']==opened['recovery_evidence']
current=Path(opened['workspace_path']);draft=current/'recovery-draft'
assert (current/json.loads((current/'domain-workspace.json').read_bytes())['paths']['recovery_manifest']).is_file()

assert not (current/local_process_observation.RECORD_DIR).exists()
assert (draft/'scratch/numbers.json').read_bytes()==numbers
assert any(b'ModuleNotFoundError' in path.read_bytes() for path in draft.rglob('*.log'))
assert (current/'scratch/analysis.py').read_text()==script
assert (current/'scratch/numbers.json').read_bytes()==numbers
# Direct editing, no copying or chmod repair and no numerical re-run.
revised=script.replace('import fixture_plotter', "from PIL import Image\nImage.new('RGB',(2,2)).save('plot.png')")
(current/'scratch/analysis.py').write_text(revised)
assert subprocess.run(launcher+['plot'],cwd=current,capture_output=True,timeout=10).returncode==0
assert (current/'scratch/calls.txt').read_text()=='1'
assert (current/'scratch/numbers.json').read_bytes()==numbers
assert (draft/'scratch/analysis.py').read_text()==script
saved=rpc(('worker_open_assignment',{}),('worker_analysis_publish_files',dict(source_aliases=['reference_material'],script_path='scratch/analysis.py',files=[dict(path='scratch/numbers.json',media_type='application/json'),dict(path='scratch/plot.png',media_type='image/png')],method='Tiny engineering fixture; plot saved data without recomputation.')))[1]
report=analysis_report(alias='solver_outputs_001',output_name='A',mapped=True)
report['source_references'][0]['case_mapping_basis']=dict(kind='evidence',evidence_refs=[dict(input_alias='experiment_plan',locator='experiment_plan:/proposals/0/cases/0')],rationale='Conditional fixture association to the exact original plan.')
report['evidence'].append(dict(source_key='saved_numbers',source_type='runtime_output',title='Saved fixture numbers',locator=saved['files'][0]['evidence_alias']))
def submit(root,report):
 (root/'output/result.json').write_bytes(canonical_json(dict(schema_version=1,handoff=dict(verdict='blocked',summary='Finite engineering fixture.'),payload=report)))
 result=rpc(('worker_open_assignment',{}),('worker_submit_result',{}))[-1]
 assert result['state']=='completed',result
submit(current,report)
request.pop('draft_from');request['name']='history_analysis'
request['inputs'].extend([dict(port='prior_analysis',artifact_names=['continued_analysis.output']),dict(port='prior_analysis_manifest',artifact_names=['continued_analysis.output.recovery_manifest'])])
assert facade.call_tool('operation_preflight',request)['admissible']
facade.call_tool('operation_invoke',request)
call=deepcopy(score_fixture);call['sources'][0].pop('output_name');call['sources'][0].pop('experiment_key')
opened,record=rpc(('worker_open_assignment',{}),('worker_tcad_curve_score',dict(record_key='history',request=call)))
assert record['status']=='computed',record
assert record['request']==call
report=analysis_report(alias='solver_outputs_001',output_name='A',mapped=False)
report['source_references']=[];report['calculation_records']=[record]
submit(Path(opened['workspace_path']),report)
status=facade.call_tool('run_status',{'name':'history_analysis'})
assert status['sealed_output']['payload']['source_references'][0]['case_key']=='baseline'
assert (current/'scratch/calls.txt').read_text()=='1'
print(json.dumps(dict(installed_catalog_operations=len(catalog.operation_ids()),stdio_recovery=True,compact_open=True,writable_recovery=True,fresh_runtime_observations=True,prior_mapping_reused=True,raw_request_unchanged=True,numerical_calls=1,numerical_bytes_preserved=True,limited_submit='completed',original_retained=workspace.exists(),real_agent=False,optional_paths_match=True,argv_native_error_survives_success=True,out_of_scope_evidence_does_not_block_recovery=True)))
'''
# raw literal above deliberately preserves normal escaped Python code; RPC newlines are real.
body=body.replace("'\\\\n'.join(lines)+'\\\\n'", "'\\n'.join(lines)+'\\n'")
child=root/'probe.py'
child.write_text('materials='+repr((plan.canonical_json(),package.model_dump_json().encode(),manifest,plx,csv))+'\nscore_fixture='+repr(fixture.raw_request())+'\nreport_fixture='+repr(fixture.analysis_report())+'\n'+preamble+'\n\n'.join(functions)+'\n'+body)
output=command([str(env/'bin/python'),'-I',str(child)])
print(output,flush=True)
record=json.loads(output)
import hashlib
changed=json.loads((base/'changed-files.json').read_text())
packaged={}
for item in changed:
 name=item['path']
 if name.startswith('src/'):
  installed=site/Path(name).relative_to('src')
 elif name.startswith('plugins/') and name.endswith('.py'):
  installed=site/Path(*Path(name).parts[2:])
 else:continue
 assert installed.read_bytes()==(repo/name).read_bytes(),name
 packaged[name]=hashlib.sha256(installed.read_bytes()).hexdigest()
record['packaged_source_sha256']=packaged
(base/'installed-smoke.json').write_text(json.dumps(record,indent=2)+'\n')
(base/'installed-environment.txt').write_text(str(root)+'\n')
