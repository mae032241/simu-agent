"""Real bwrap/main/registered-cov path with two fake native turns, zero models."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from scidiscovery.research_loop import budget,contracts as c,controller,cov_lineage,execution,lineage,native,search
from scidiscovery.research_loop.protocol import CURRENT
from test_cov_lineage import BACKEND


FAKE_NATIVE=r'''import json,os,pathlib,subprocess,sys
args=sys.argv[1:];sys.stdin.read()
work=pathlib.Path(args[args.index('-C')+1]);home=pathlib.Path(os.environ['CODEX_HOME'])
root=work.parents[2]
assert (root/'jobs'/(work.name+'.json')).is_file()
assert (root/'settings-identity.json').is_file()
assert {p.name for p in (root/'jobs').glob('*.json')}=={work.name+'.json'}
assert not (root/'settings.json').exists()
assert not (root/'control-ledger').exists()
assert not (root.parent/'private-owner-state').exists()
for original in (root/'jobs'/(work.name+'.json'),root/'settings-identity.json'):
 try:
  with original.open('ab'):pass
 except OSError:pass
 else:raise AssertionError('Shared owner metadata must stay read-only')
task=json.loads((work/'science-task.json').read_text());role=task['role']
search_enabled=bool(task.get('lineage',{}).get('mechanisms',{}).get('authorized_count'))
output=pathlib.Path(args[args.index('--output-last-message')+1]);later=output.parent.parent.name=='continuations'
assert 'resume' not in args
assert pathlib.Path(args[args.index('--output-schema')+1]).name=='science-result.schema.json'
thread='22222222-2222-4222-8222-222222222222' if later else '11111111-1111-4111-8111-111111111111'
print(json.dumps(dict(type='thread.started',thread_id=thread)),flush=True)
session=home/'sessions/current.jsonl';session.parent.mkdir(parents=True,exist_ok=True)
session.write_text(json.dumps(dict(type='session_meta',payload=dict(id=thread,cwd=str(work))))+'\n')
if role=='W':
 capabilities=subprocess.run([str(work/'bin/exp'),'capabilities'],capture_output=True,text=True)
 assert capabilities.returncode==0,(capabilities.stdout,capabilities.stderr)
 assert any(item['key']=='cov_single_source' for item in json.loads(capabilities.stdout)['contracts'])
 contract=work/'work'/('cov-contract-later.json' if later else 'cov-contract-first.json')
 described=subprocess.run([str(work/'bin/exp'),'describe','--key','cov_single_source','--output',str(contract)],capture_output=True,text=True)
 assert described.returncode==0,(described.stdout,described.stderr)
 assert json.loads(contract.read_text())['experiment_directory'] is False
 status=subprocess.run([str(work/'bin/exp'),'lineage-status'],capture_output=True,text=True)
 assert status.returncode==0,(status.stdout,status.stderr)
 if not later:
  p=work/'payload.json';p.write_text('{}')
  cmd=[str(work/'bin/exp'),'run','--script',str(p),'--new-plan']
  rejected_options=[]
  for options in (['--experiment-dir',str(work)],['--','--seed','7']):
   rejected=subprocess.run(cmd+options,capture_output=True,text=True)
   assert rejected.returncode==2,(rejected.stdout,rejected.stderr)
   rejection=json.loads(rejected.stdout)
   assert rejection['status']=='known_not_started' and rejection['accepted'] is False,rejection
   assert 'call_id' not in rejection
   assert not list((work/'work/lineage/calls').glob('*/accepted.json'))
   rejected_options.append(rejection)
  (work/'work/rejected-caller-options.json').write_text(json.dumps(rejected_options))
  result=subprocess.run(cmd+(['--mechanism','P'] if search_enabled else []),capture_output=True,text=True)
  assert result.returncode==0,(result.stdout,result.stderr)
  reply=json.loads(result.stdout);assert reply['status']=='known_success'
  if search_enabled:
   rejected=subprocess.run(cmd+['--mechanism','P'],capture_output=True,text=True)
   assert rejected.returncode!=0 and 'Other H mechanisms' in rejected.stdout+rejected.stderr,(rejected.stdout,rejected.stderr)
   other=subprocess.run(cmd+['--mechanism','Q'],capture_output=True,text=True)
   assert other.returncode==0,(other.stdout,other.stderr)
   assert json.loads(other.stdout)['status']=='known_success'
  (work/'work/original-call.json').write_text(json.dumps(dict(call_id=reply['call_id'])))
 else:
  assert home.name=='context-001'
  assert (work/'work/science-resume.json').is_file()
  call=json.loads((work/'work/original-call.json').read_text())['call_id']
  result=subprocess.run([str(work/'bin/exp'),'query','--call-id',call],capture_output=True,text=True)
  assert result.returncode==0,(result.stdout,result.stderr)
  assert json.loads(result.stdout)['state']=='succeeded'
  (work/'work/second-context-query.json').write_text(result.stdout)
print(json.dumps(dict(type='turn.completed',usage=dict(input_tokens=1,cached_input_tokens=0,output_tokens=0))),flush=True)
payload=dict(summary='Synthetic namespace contribution',scientific_result='No scientific efficacy was measured.',
 limitations=['Fake native transport, not a model.'],implementation_selection=None)
if role=='W':
 payload['stage_intent']='review' if later else 'continue'
 payload['mechanism_findings']=([dict(mechanism=label,basis='observed',finding='Independent bounded interpretation; fake transport, no measured efficacy.') for label in ('P','Q')] if search_enabled else None)
if role=='H':payload.update(next_action='experiment',route_reason='Discriminate the declared mechanism',
 search_plan=dict(scope='Synthetic current search',commitments=[dict(label=label,minimal_test='One bounded experiment; prioritize competing mechanisms before fine tuning',existing_ref=None) for label in ('P','Q')],focus=dict(label=None,action='screen')))
if role=='A':payload.update(next_action='finish',route_reason='The synthetic combination was observed',candidate_recommendation=None,
 progress_assessment=None,decision_request=None,portfolio_review=None,
 search_review=dict(dispositions=[dict(mechanism_ref=ref,status='screened',reason='One final W was assessed') for ref in ('h001.m1','h001.m2')],next_focus=dict(mechanism_ref=None,action='screen')))
output.write_text(json.dumps(payload))
'''


def prepare_namespace(tmp_path,*,search_enabled=False,fake_source=FAKE_NATIVE,context='new_context',repair=False):
    if shutil.which('bwrap') is None:pytest.skip('Actual namespace unavailable')
    isolated=subprocess.run([sys.executable,'-I','-c',
        f'from pathlib import Path;from scidiscovery.research_loop.protocol import CURRENT;assert CURRENT=={CURRENT};'
        f'from scidiscovery.research_loop import contracts;assert Path(contracts.__file__).resolve()==Path({str(Path(c.__file__).resolve())!r})'],
        capture_output=True,text=True)
    if isolated.returncode:pytest.skip(f'Exact current CURRENT{CURRENT} package must be importable with -I; use an explicit source bridge or matching installed interpreter')
    repo=Path(__file__).resolve().parents[2];launcher=repo/'scripts/acceptance/rootless_cov_launcher.py'
    (tmp_path/'private-owner-state').write_text('Host-only owner-state canary; no credentials.')
    public=tmp_path/'public';harness=public/'environment/harness';harness.mkdir(parents=True)
    (public/'instruction.md').write_text('Two synthetic native contexts; zero model requests.')
    (public/'task.toml').write_text('fixture=true\n');(public/'environment/Dockerfile').write_text('FROM fixture\n')
    (harness/'exp_cli.py').write_text(BACKEND.replace("p.add_argument('--runs-root',type=pathlib.Path,required=True)","p.add_argument('--runs-root',type=pathlib.Path,default=pathlib.Path(__import__('os').environ['EXP_RUN_DIR']))"))
    for name in ('runner.py','train.csv','val.csv','meta.json'):(harness/name).write_text('{}')
    manifest=tmp_path/'public-manifest.json'
    c.write(manifest,dict(task_revision='d78f5eb52ad754c5ee9154741af73130a85a65b8',
        public_files_sha256={p.relative_to(public).as_posix():c.digest(p) for p in public.rglob('*') if p.is_file()}))
    fake=tmp_path/'fake-codex';fake.write_text('#!'+sys.executable+'\n'+fake_source);fake.chmod(0o555)
    root=tmp_path/'instance';config=tmp_path/'launcher.json';python=str(Path(sys.executable).absolute());codehost=Path('/usr/bin/true').resolve()
    # Preserve this interpreter's explicit -I source bridge, including its
    # selected metadata and dependency sites. This is source-entry transport
    # coverage, not installed-wheel qualification; never mount the checkout.
    source_root=Path(c.__file__).resolve().parents[2]
    metadata_root=Path(importlib.metadata.distribution('scidiscovery').locate_file('')).resolve()
    dependency_sites=[str(Path(path).resolve()) for path in sys.path
        if Path(path).name in ('site-packages','dist-packages') and Path(path).is_dir()]
    runtime_paths=list(dict.fromkeys([sys.base_prefix,str(Path(python).parent.parent),
        str(source_root),str(metadata_root),*dependency_sites]))
    assert str(repo) not in runtime_paths
    c.write(config,dict(scene_root=str(root),public_root=str(public),public_manifest=str(manifest),
        runs_dir=str(root/'runs'),submission_dir=str(root/'submission'),native=str(fake),native_sha256=c.digest(fake),
        code_mode_host=dict(path=str(codehost),sha256=c.digest(codehost)),task_python=python,scid_python=python,
        runtime_paths=runtime_paths,
        model='no-model',reasoning_effort='high',profile='namespace-no-model',cov_receipt_channel='backend_file'))
    controller.prepare(root,public/'instruction.md',public,[python,str(launcher),'--config',str(config),'--'],
        max_tokens=100000,max_seconds=120,max_steps=8,model='no-model',reasoning_effort='high',search_policy=search.DEFAULT_POLICY if search_enabled else None,
        history_observer=dict(adapter=str(Path(cov_lineage.__file__).resolve()),contract_version=2,
            config=dict(runs='runs',calls='project/nodes',evaluation_key='covshift-public-val-v1')) if search_enabled else None,
        node_budget_policy={role:dict(max_observed_tokens=10000,max_seconds=60) for role in 'HWAE'},
        resume_policy=dict(max_attempts=2,protocol='codex_exec_resume',usage_scope='turn',output_repair=repair),
        worker_fragment_policy=dict(context=context))
    c.write(root/'host-started.json',budget.clock_stamp());budget.transition(root,'advance','Namespace zero-model transport probe')
    return root


@pytest.mark.parametrize('search_enabled',[False,True],ids=['no-search','sealed-h-search-w-a'])
def test_actual_launcher_two_new_contexts_keep_original_registered_call(tmp_path,search_enabled):
    root=prepare_namespace(tmp_path,search_enabled=search_enabled)
    if search_enabled:
        c.build_job(root,1,'H',[]);native.execute_native(root,1)
        assert 'exploration_order_version' not in c.settings(root)
        assert c.validate(c.workspace(root,1))['search_plan']['commitments']
    step=2 if search_enabled else 1
    job=c.build_job(root,step,'W',[1] if search_enabled else [])
    if search_enabled:
        assert job['search']['focus']['mechanism_ref']=='h001.m1'
        assert lineage.build(root,step)['mechanisms']==search.project(root,step)['mechanisms']
    native.execute_native(root,step)
    chain=execution.records(root,step)
    assert len(chain)==2 and chain[1].name=='001'
    assert c.read(chain[0]/'science-output.json')['stage_intent']=='continue'
    assert c.read(chain[1]/'science-output.json')['stage_intent']=='review'
    assert c.read(chain[0]/'native-outcome.json')['thread_id']!=c.read(chain[1]/'native-outcome.json')['thread_id']
    assert native.usage(root)['observed_tokens']==(3 if search_enabled else 2)
    first=c.read(chain[0]/'experiment-config.json');second=c.read(chain[1]/'experiment-config.json')
    assert first['scope']==second['scope'] and first['native_attempt']!=second['native_attempt']
    work=c.workspace(root,step)
    assert len(list((work/'work/lineage/calls').glob('*/accepted.json')))==(2 if search_enabled else 1)
    assert len(c.read(work/'work/rejected-caller-options.json'))==2
    assert c.read(work/'work/second-context-query.json')['state']=='succeeded'
    assert len(list((root/'jobs').glob('*.json')))==step
    assert c.validate(work)['stage_intent']=='review'
    if search_enabled:
        assert first['scope']['mechanism_ref'] is None
        c.build_job(root,3,'A',[1,2]);native.execute_native(root,3)
        assert c.validate(c.workspace(root,3))['next_action']=='finish'
        state=search.project(root,4);graph=lineage.build(root,4)
        assert graph['mechanisms']==state['mechanisms']
        assert all(row['status']=='screened' for row in state['mechanisms'].values())
        assert len(state['order']['seen_w'])==1 and state['order']['remaining']==[]
        assert len(graph['candidates'])==2
        assert {item['mechanism_ref'] for item in graph['candidates'].values()}=={'h001.m1','h001.m2'}
        assert native.usage(root)['observed_tokens']==4
