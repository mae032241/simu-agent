"""One isolated wheel/stdio recovery smoke; no production state or scientific Run."""
import ast, json, os, subprocess, sys, tempfile, venv
from pathlib import Path
base=Path(__file__).resolve().parent
repo=base.parents[3]
for path in (repo, repo/'src', repo/'plugins/curve_score', repo/'plugins/tcad_artifact'):
 sys.path.insert(0,str(path))
from tests.operations.conftest import _supply_runtime_dependencies
from tests.operations import test_tcad_result_analysis as fixture
plan,package,manifest,plx,csv=fixture.analysis_materials()
source=Path(fixture.__file__).read_text()
functions=[]
for node in ast.parse(source).body:
 if isinstance(node,ast.FunctionDef) and node.name in {'analysis_system','analysis_report'}:
  text=ast.get_source_segment(source,node)
  text=text.replace('compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN))','compile_installed_catalog()')
  text=text.replace("_CURVE['_diagnosis']().model_dump(mode='json')",'deepcopy(report_fixture)')
  functions.append(text)
root=Path(tempfile.mkdtemp(prefix='scid-work-preservation-installed-'))
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
workspace=Path(opened['workspace_path']);scratch=workspace/'scratch'
assert (workspace/'tools/local_process_observation.py').read_bytes()==Path(local_process_observation.__file__).read_bytes()
script="""import json,sys
from pathlib import Path
if sys.argv[1] == 'compute':
 Path('calls.txt').write_text('1')
 Path('numbers.tmp').write_text('{"value":3}')
 Path('numbers.tmp').replace('numbers.json')
import fixture_plotter
"""
(scratch/'analysis.py').write_text(script)
launcher=[sys.executable,'tools/local_process_observation.py','--timeout','5','--submission-reserve','0','analysis.py']
proc=subprocess.run(launcher+['compute'],cwd=workspace,capture_output=True,timeout=10)
assert proc.returncode==1
numbers=(scratch/'numbers.json').read_bytes()
status=facade.call_tool('run_status',{'name':'analysis'})
assert status['native_execution']['exit_code']==1
facade.call_tool('run_record_failure',dict(name='analysis',reason='controlled fixture plot failure',expected_state='running',expected_last_activity_at=status['last_activity_at']))
status=facade.call_tool('run_status',{'name':'analysis'})
assert status['recovery']['draft_available'] and status['recovery']['recovery_pending']
request=deepcopy(request);request.update(name='continued_analysis',draft_from='analysis')
assert facade.call_tool('operation_preflight',request)['admissible']
facade.call_tool('operation_invoke',request)
next_opened=rpc(('worker_open_assignment',{}))[0]
next_workspace=Path(next_opened['workspace_path']);draft=next_workspace/'recovery-draft'
assignment=json.loads(Path(next_opened['assignment_path']).read_text())
assert assignment['recovery_draft']['relative_path']=='recovery-draft'
assert (draft/'scratch/numbers.json').read_bytes()==numbers
assert any(b'ModuleNotFoundError' in p.read_bytes() for p in draft.rglob('*.log'))
for name in ('analysis.py','numbers.json','calls.txt'):
 shutil.copyfile(draft/'scratch'/name,next_workspace/'scratch'/name)
revised=script.replace('import fixture_plotter', "from PIL import Image\ndata=json.loads(Path('numbers.json').read_text())\nImage.new('RGB',(2,2)).save('plot.png')")
(next_workspace/'scratch/analysis.py').write_text(revised)
assert subprocess.run(launcher+['plot'],cwd=next_workspace,capture_output=True,timeout=10).returncode==0
assert (next_workspace/'scratch/numbers.json').read_bytes()==numbers
assert (next_workspace/'scratch/calls.txt').read_text()=='1'
saved=rpc(('worker_open_assignment',{}),('worker_analysis_publish_files',dict(source_aliases=['reference_material'],script_path='scratch/analysis.py',
 files=[dict(path='scratch/numbers.json',media_type='application/json'),dict(path='scratch/plot.png',media_type='image/png')],method='Tiny engineering fixture; draw saved number without recomputation.')))[1]
report=analysis_report();report['calculation_records']=[]
report['evidence'].append(dict(source_key='saved_numbers',source_type='runtime_output',title='Saved fixture numbers',locator=saved['files'][0]['evidence_alias']))
(next_workspace/'output/result.json').write_bytes(canonical_json(dict(schema_version=1,handoff=dict(verdict='blocked',summary='Finite engineering fixture.'),payload=report)))
assert rpc(('worker_open_assignment',{}),('worker_submit_result',{}))[-1]['state']=='completed'
assert facade.call_tool('run_status',{'name':'continued_analysis'})['sealed_output'] is not None
print(json.dumps(dict(installed_catalog_operations=len(catalog.operation_ids()),stdio_recovery=True,launcher_packaged=True,
 numerical_calls=1,numerical_bytes_preserved=True,limited_submit='completed',original_retained=workspace.exists(),real_agent=False)))
'''
# raw literal above deliberately preserves normal escaped Python code; RPC newlines are real.
body=body.replace("'\\\\n'.join(lines)+'\\\\n'", "'\\n'.join(lines)+'\\n'")
child=root/'probe.py'
child.write_text('materials='+repr((plan.canonical_json(),package.model_dump_json().encode(),manifest,plx,csv))+'\nreport_fixture='+repr(fixture.analysis_report())+'\n'+preamble+'\n\n'.join(functions)+'\n'+body)
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
