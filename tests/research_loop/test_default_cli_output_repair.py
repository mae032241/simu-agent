"""Real CLI transport freezes output repair without changing native configuration."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scidiscovery.research_loop import contracts as c, continuation, execution
from scidiscovery.research_loop import search as search_contract, worker_delivery

pytestmark=pytest.mark.process_e2e


NATIVE = r'''import json,os,pathlib,sys
args=sys.argv[1:];prompt=sys.stdin.read();resume='resume' in args
config=json.loads(pathlib.Path(__file__).resolve().with_name('launcher-config.json').read_text())
work=pathlib.Path(os.environ['THIN_HWA_WORKSPACE']);role=os.environ['THIN_HWA_ROLE']
home=pathlib.Path(os.environ['CODEX_HOME'])
if config['default_home']:
 assert str(home)==config['home']
 assert (home/'config.toml').read_text()==config['configuration']
 assert (home/'auth.json').is_file()
thread='11111111-2222-4333-8444-'+('%012d'%int(work.name))
with (work/'work/launches').open('a') as stream:stream.write('resume\n' if resume else 'exec\n')
print(json.dumps(dict(type='thread.started',thread_id=thread)),flush=True)
if not resume:
 session=home/'sessions'/('rollout-'+thread+'.jsonl');session.parent.mkdir(parents=True,exist_ok=True)
 session.write_text(json.dumps(dict(type='session_meta',payload=dict(id=thread,cwd=str(work))))+'\n')
 (work/'work/completed-observation').write_text('one retained observation')
else:
 assert thread in args and 'Repair only your final response' in prompt
 assert (work/'work/completed-observation').read_text()=='one retained observation'
payload=dict(summary='Deterministic CLI transport',scientific_result='No scientific qualification is asserted.',
 limitations=['Only native communication is simulated.'],implementation_selection=None)
if role=='H':
 payload.update(next_action='analyze',route_reason='Review retained evidence',search_plan=None)
 if config['fault']=='incomplete_w':
  payload.update(next_action='experiment',search_plan=dict(scope='One declared fixture mechanism',
   commitments=[dict(label='Fixture mechanism',minimal_test='Read a bounded observation',existing_ref=None)],
   focus=dict(label=None,action='screen')))
elif role=='W':payload.update(stage_intent='review',mechanism_findings=None)
else:
 assert role=='A'
 payload.update(next_action='finish',route_reason='The measured scientific objective remains unresolved.',
  candidate_recommendation='declared-fixture-choice',search_review=None,progress_assessment=None,decision_request=None)
 if (resume and config['fault']!='repeat') or config['fault']=='incomplete_w':
  payload['selection_explanation']=dict(criteria='Retain the declared bounded fixture observation.',
   criteria_change=dict(status='unchanged',prior_criteria=None,changes=None,evidence=None,accepted_tradeoffs=None))
 if config['fault']=='incomplete_w':
  task=json.loads((work/'science-task.json').read_text())
  mechanisms=json.loads((work/task['lineage']['indexes']['mechanisms']).read_text())
  payload['search_review']=dict(dispositions=[dict(mechanism_ref=mechanisms['mechanisms'][0]['mechanism_ref'],
   status='pending',reason='The W contribution lacks the requested scientific findings.')],next_focus=None)
pathlib.Path(args[args.index('--output-last-message')+1]).write_text(json.dumps(payload))
if config['fault']!='unknown' or role=='H':
 print(json.dumps(dict(type='turn.completed',usage=dict(input_tokens=10,cached_input_tokens=3,output_tokens=4))),flush=True)
raise SystemExit(7 if config['fault']=='failed' and role=='A' else 0)
'''


def cli(root,*arguments,env):
    completed=subprocess.run([sys.executable,'-m','scidiscovery.research_loop.cli',*arguments,
        '--root',str(root)],env=env,capture_output=True,text=True,timeout=40)
    # CLI permission/admission rejections remain structured JSON too.
    assert completed.stdout.strip(),completed.stderr
    return json.loads(completed.stdout)


def prepare_cli(tmp_path,*,fault='missing',custom=False,explicit_false=False,final=False):
    public=tmp_path/'public';public.mkdir();objective=public/'objective.md';objective.write_text('Retain scientific uncertainty.')
    home=tmp_path/'inherited-home';home.mkdir()
    configuration='[sandbox_workspace_write]\nnetwork_access=true\nexclude_tmpdir_env_var=true\n'
    (home/'config.toml').write_text(configuration);(home/'auth.json').write_text('{"fixture":"private authentication marker"}')
    program=tmp_path/'native.py';program.write_text('#!'+sys.executable+'\n'+NATIVE);program.chmod(0o755)
    binary=tmp_path/'bin';binary.mkdir();(binary/'codex').symlink_to(program)
    c.write(tmp_path/'launcher-config.json',dict(fault=fault,home=str(home),configuration=configuration,default_home=not explicit_false))
    env=dict(os.environ,CODEX_HOME=str(home),PATH=str(binary)+os.pathsep+os.environ.get('PATH',''))
    source=str(Path(__file__).resolve().parents[2]/'src')
    env['PYTHONPATH']=source+os.pathsep+env.get('PYTHONPATH','')
    root=tmp_path/'instance';search=tmp_path/'search.json'
    c.write(search,dict(search_contract.DEFAULT_POLICY,initial_calls=1) if fault=='incomplete_w' else None)
    launcher=[sys.executable,str(program)] if custom else [str(binary/'codex') if explicit_false else 'codex']
    arguments=['prepare','--objective',str(objective),'--public-root',str(public),
        '--native-launcher-json',json.dumps(launcher),
        '--max-tokens','1' if final else '1000','--max-seconds','60','--max-steps','1' if final else '6',
        '--search-policy',str(search)]
    if explicit_false:
        policy=tmp_path/'resume.json';c.write(policy,dict(max_attempts=2,protocol='codex_exec_resume',usage_scope='turn',output_repair=False))
        nodes=tmp_path/'nodes.json';c.write(nodes,{role:dict(max_observed_tokens=1000,max_seconds=60) for role in 'HWAE'})
        arguments+=['--worker-resume-policy',str(policy),'--node-budget-policy',str(nodes)]
    prepared=cli(root,*arguments,env=env)
    assert prepared['status']=='prepared',prepared
    return root,home,env


@pytest.mark.parametrize('final',[False,True])
def test_default_standard_cli_repairs_same_a_in_original_native_home(tmp_path,final):
    root,home,env=prepare_cli(tmp_path,final=final)
    settings=c.settings(root);policy=settings['resume_policy']
    assert settings['native_launcher_argv']==[str(tmp_path/'bin/codex')]
    assert policy['output_only'] and policy['output_repair'] and policy['max_attempts']==2
    assert policy['native_home']==str(home)
    assert policy['launcher_files'][0]['path']==str(tmp_path/'native.py')
    assert settings['node_budget_policy']=={role:dict(max_observed_tokens=settings['max_tokens'],max_seconds=60) for role in 'HWAE'}
    originals={path:path.read_bytes() for path in (home/'config.toml',home/'auth.json',root/'settings.json')}
    result=cli(root,'closeout' if final else 'run',env=env)
    assert result['status']==('final_a_completed' if final else 'finish'),result
    step=1 if final else 2;origin=execution.origin(root,step);current=execution.record(root,step)
    assert current==origin/'continuations/001'
    assert (c.workspace(root,step)/'work/launches').read_text()=='exec\nresume\n'
    assert 'selection_explanation' not in c.read(origin/'science-output.json')
    assert c.validate(c.workspace(root,step))['selection_explanation']['criteria_change']['status']=='unchanged'
    intent=c.read(current/'native-intent.json')
    assert intent['task_sha256']==c.read(origin/'native-intent.json')['task_sha256']
    assert intent.get('native_profile')==c.read(origin/'native-intent.json').get('native_profile')
    assert intent['session']['home']==str(home) and intent['session']['workspace']==str(c.workspace(root,step))
    assert intent['output_repair']['code']=='selection_explanation_incomplete'
    assert intent['budget_slice']['previous_tokens']==14
    assert all(path.read_bytes()==data for path,data in originals.items())
    assert not (root/'jobs'/f'{step+1:03d}.json').exists()
    if final:
        assert intent['budget_slice']['final_return']==c.read(origin/'native-intent.json')['budget_slice']['final_return']
        assert c.read(current/'native-outcome.json')['final_a_completion']['final_overrun']['observed_node_tokens']==28


@pytest.mark.parametrize('custom,explicit_false',[(True,False),(False,True)])
def test_custom_or_explicitly_disabled_cli_never_gains_default_output_repair(tmp_path,custom,explicit_false):
    root,_,env=prepare_cli(tmp_path,custom=custom,explicit_false=explicit_false)
    policy=c.settings(root).get('resume_policy')
    if custom:assert policy is None
    else:assert policy['output_repair'] is False
    result=cli(root,'run',env=env)
    assert result['status']=='output_repair_required',result
    assert (c.workspace(root,2)/'work/launches').read_text()=='exec\n'
    assert len(execution.records(root,2))==1 and not (root/'jobs/003.json').exists()


@pytest.mark.parametrize('fault',['unknown','failed','repeat'])
def test_default_cli_repair_retains_execution_boundary_and_finite_attempts(tmp_path,fault):
    root,_,env=prepare_cli(tmp_path,fault=fault)
    result=cli(root,'run',env=env)
    assert result['status']!='finish'
    launches=(c.workspace(root,2)/'work/launches').read_text()
    assert launches==('exec\nresume\nresume\n' if fault=='repeat' else 'exec\n')
    assert len(execution.records(root,2))==(3 if fault=='repeat' else 1)
    assert not (execution.origin(root,2)/'result-identity.json').exists()
    assert not (root/'jobs/003.json').exists()
    if fault=='failed':
        rejected=cli(root,'worker-resume','--step','2',env=env)
        assert 'worker_resume_output_only' in json.dumps(rejected)
        assert (c.workspace(root,2)/'work/launches').read_text()==launches


def test_default_cli_policy_cannot_authorize_scientific_work_repair(tmp_path):
    root,_,_=prepare_cli(tmp_path)
    with pytest.raises(ValueError,match='does not authorize scientific work repair'):
        continuation.validate_repair(root,1,dict(work_repair=dict(code='worker_delivery_incomplete')))


def test_default_cli_incomplete_w_retains_partial_exit_and_reaches_a(tmp_path):
    root,_,env=prepare_cli(tmp_path,fault='incomplete_w')
    result=cli(root,'run',env=env)
    assert result['status']=='finish',result
    job=c.read(root/'jobs/002.json');record=execution.origin(root,2)
    assert job['role']=='W' and worker_delivery.applicable(job)
    assert (c.workspace(root,2)/'work/launches').read_text()=='exec\n'
    assert len(execution.records(root,2))==1
    science=c.validate(c.workspace(root,2))
    assert science['mechanism_findings'] is None
    assert worker_delivery.assessment(root,job,science,record)['status']=='incomplete'
    exit=c.read(record/'stage-end.json')['work_exit']
    assert exit['kind']=='resume_policy' and exit['reason']=='worker_resume_output_only'
    assert exit['settings_sha256']==c.digest(root/'settings.json')
    assert worker_delivery.validate_exit(root,job,record,exit)=='worker_resume_output_only'
    assert worker_delivery.require_delivery(root,job,science,record)['status']=='partial'
    assert c.read(root/'jobs/003.json')['role']=='A' and c.validate(c.workspace(root,3))['next_action']=='finish'
    assert not (root/'jobs/004.json').exists()
    forged=dict(exit,reason='worker_resume_unsupported')
    with pytest.raises(ValueError,match='original unsupported policy'):
        worker_delivery.validate_exit(root,job,record,forged)


@pytest.mark.parametrize('native_home',['relative-home','~/.codex'])
def test_default_cli_rejects_literal_relative_native_home(tmp_path,native_home):
    binary=tmp_path/'bin';binary.mkdir();program=binary/'codex'
    program.write_text('#!'+sys.executable+'\nraise SystemExit(99)\n');program.chmod(0o755)
    public=tmp_path/'public';public.mkdir();objective=public/'objective.md';objective.write_text('Do not submit native work.')
    root=tmp_path/'instance';env=dict(os.environ,CODEX_HOME=native_home,PATH=str(binary)+os.pathsep+os.environ.get('PATH',''))
    env['PYTHONPATH']=str(Path(__file__).resolve().parents[2]/'src')+os.pathsep+env.get('PYTHONPATH','')
    result=cli(root,'prepare','--objective',str(objective),'--public-root',str(public),
        '--native-launcher-json','["codex"]','--max-tokens','1000','--max-seconds','60','--max-steps','6',env=env)
    assert result['status']=='error' and 'absolute inherited CODEX_HOME' in result['error']
    assert not root.exists()
