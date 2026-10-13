"""Soft scientific targets retain native work; shared hard guards remain real."""
import json
from pathlib import Path
import sys
import time

import pytest

from scidiscovery.research_loop import budget, contracts as c, controller, execution, native, search
from test_history_handoff import finish
from test_worker_resume import wait_runner

FAKE = r'''import json,os,pathlib,sys,time
args=sys.argv[1:];prompt=sys.stdin.read();work=pathlib.Path(os.environ['THIN_HWA_WORKSPACE']);home=pathlib.Path(os.environ['THIN_HWA_NATIVE_HOME']);role=os.environ['THIN_HWA_ROLE']
config=json.loads(pathlib.Path(sys.argv[0]).with_suffix('.json').read_text())
(work/'work/prompt.txt').write_text(prompt)
thread='11111111-2222-4333-8444-555555555555'
print(json.dumps({'type':'thread.started','thread_id':thread}),flush=True)
if config['resume']:
 p=home/'sessions/rollout.jsonl';p.parent.mkdir(parents=True,exist_ok=True)
 if not p.exists():p.write_text(json.dumps({'type':'session_meta','payload':{'id':thread,'cwd':str(work)}})+'\n')
with (work/'work/launches').open('a') as f:f.write('resume\n' if 'resume' in args else 'exec\n')
if config['mode']!='no_usage':print(json.dumps({'type':'turn.completed','usage':{'input_tokens':12,'cached_input_tokens':5,'output_tokens':3}}),flush=True)
if config['mode']=='forge_hint':
 (work/'work/budget-status.json').unlink(missing_ok=True)
 (work/'work/budget-status.json').write_text(json.dumps({'shared_observed_tokens_remaining_upper_bound':1000000000}))
if config['mode']=='known_failure' and 'resume' not in args:sys.exit(7)
time.sleep(config['sleep'])
payload=dict(summary='Original bounded finding',scientific_result='Soft target did not destroy the accepted work',limitations=['Fake process, not scientific efficacy'],implementation_selection=None)
if role=='H':payload.update(search_plan=None,next_action='experiment' if config['mode']=='reserve' else 'wait',route_reason='Bounded contribution')
if role=='A':payload.update(search_review=None,candidate_recommendation=None,progress_assessment=None,next_action='finish',route_reason='Independent conclusion')
pathlib.Path(args[args.index('--output-last-message')+1]).write_text(json.dumps(payload))
'''


def scene(tmp_path, *, mode='normal', tokens=10, seconds=.05, total_tokens=1000, total_seconds=30, resume=False, delivery=None, search_policy=None, sleep=.15):
    public=tmp_path/'public';public.mkdir();objective=public/'objective';objective.write_text('Complete useful scientific work within the total authorization.')
    launcher=tmp_path/'native.py';launcher.write_text(FAKE)
    c.write(launcher.with_suffix('.json'),dict(mode=mode,resume=resume,sleep=sleep))
    root=tmp_path/'instance'
    controller.prepare(root,objective,public,[sys.executable,str(launcher)],max_tokens=total_tokens,max_seconds=total_seconds,max_steps=12,
        model='fake',reasoning_effort='high',search_policy=search_policy,
        node_budget_policy={role:dict(max_observed_tokens=tokens,max_seconds=seconds) for role in 'HWAE'},delivery_policy=delivery,
        resume_policy=dict(max_attempts=2,protocol='codex_exec_resume',usage_scope='turn') if resume else None)
    return root


def start_clock(root, reason):
    c.write(root / 'host-started.json', budget.clock_stamp())
    budget.transition(root, 'advance', reason)


@pytest.mark.parametrize('role','HWAE')
def test_each_role_can_cross_targets_and_seal_its_original_conclusion(tmp_path,role):
    root=scene(tmp_path)
    step=1 if role=='H' else 2
    if step==2:finish(root,1,'H',[],action={'W':'experiment','A':'analyze','E':'extract'}[role])
    c.build_job(root,step,role,[1] if step==2 else [])
    start_clock(root,'real soft transport')
    native.execute_native(root,step)
    record=execution.record(root,step);outcome=c.read(record/'native-outcome.json')
    assert outcome['stop_reason'] is None and outcome['budget_slice']['observed_tokens']==15
    assert outcome['budget_slice']['advance_seconds']>.05
    assert c.validate(c.workspace(root,step))['summary']=='Original bounded finding'
    hint=c.read(c.workspace(root,step)/'work/budget-status.json')
    assert hint['mode']=='soft' and hint['scope']=='advice_only_not_authorization_or_scientific_evidence'
    assert 'budget-status.json' in (c.workspace(root,step)/'work/prompt.txt').read_text()


def test_soft_w_old_search_threshold_does_not_kill_but_identity_still_does(tmp_path):
    limits=dict(max_w_seconds=.05,max_w_observed_tokens=10,max_requested_repairs=2)
    root=scene(tmp_path,search_policy=limits)
    finish(root,1,'H',[],action='experiment',search_choice=dict(scope='Exact scope',commitments=[dict(label='M',minimal_test='Discriminate M',existing_ref=None)],focus=dict(label='M',action='screen')))
    job=c.build_job(root,2,'W',[1]);start_clock(root,'real soft W');native.execute_native(root,2)
    assert c.validate(c.workspace(root,2))['summary']=='Original bounded finding'
    intent=c.read(execution.record(root,2)/'native-intent.json');intent['budget_slice']['boot_id']='wrong'
    with pytest.raises(ValueError):budget.stop_node(root,job,intent,budget.snapshot(root),dict(input_tokens=15,output_tokens=0))


def test_soft_reserve_cannot_kill_current_node_but_blocks_next_admission(tmp_path):
    delivery=dict(closeout_a=dict(max_observed_tokens=10,max_seconds=1),inflight_tokens=0,cleanup_seconds=0,submit_seconds=0,confirm_seconds=0,adapter=None)
    root=scene(tmp_path,mode='reserve',tokens=10,total_tokens=25,delivery=delivery)
    result=controller.run(root)
    assert result['status']=='exported_unsubmitted'
    begin=budget.closeout_state(root)['begin']
    assert begin['source_cutoff']==1 and begin['stop_reason']=='closeout_reserve_tokens'
    assert not (root/'jobs/002.json').exists()
    assert c.validate(c.workspace(root,1))['summary']=='Original bounded finding'
    assert budget.snapshot(root)['max_tokens']-native.usage(root)['observed_tokens']==10
    assert budget.exploration_stop(root,c.read(root/'jobs/001.json'),budget.snapshot(root)) is None
    assert budget.node_admission(root,dict(step=2,role='W'))=='closeout_reserve_tokens'


@pytest.mark.parametrize('boundary',['time','tokens'])
def test_shared_hard_stop_ignores_forged_advice(tmp_path,boundary):
    root=scene(tmp_path,mode='forge_hint',tokens=5,seconds=.02,total_tokens=12 if boundary=='tokens' else 1000,
               total_seconds=2 if boundary=='time' else 30,sleep=3)
    c.build_job(root,1,'H',[]);start_clock(root,'shared hard boundary')
    with pytest.raises((RuntimeError,ValueError)):native.execute_native(root,1)
    outcome=c.read(execution.record(root,1)/'native-outcome.json')
    assert outcome['stop_reason']==('token_limit' if boundary=='tokens' else 'wall_limit')
    assert not (execution.origin(root,1)/'result-identity.json').exists()


def test_known_failure_above_soft_target_resumes_same_node_without_refund(tmp_path):
    root=scene(tmp_path,mode='known_failure',resume=True)
    assert controller.run(root)['status']=='native_stopped';first=wait_runner(root)
    original={p:p.read_bytes() for p in first.iterdir() if p.is_file()}
    assert controller.worker_resume(root,1)['status']=='wait'
    assert native.usage(root)['observed_tokens']==30 and budget.used_steps(root)==2
    assert all(p.read_bytes()==data for p,data in original.items())
    report=c.read(execution.record(root,1)/'native-outcome.json')['budget_slice']
    assert report['observed_tokens']==30 and report['dispatches']==2
    assert 'zero is not a new grant' in (c.workspace(root,1)/'work/prompt.txt').read_text()


def test_unknown_usage_never_becomes_a_soft_resume_grant(tmp_path):
    root=scene(tmp_path,mode='no_usage',resume=True)
    assert controller.run(root)['status']!='wait';first=wait_runner(root)
    with pytest.raises((ValueError,RuntimeError)):controller.worker_resume(root,1)
    assert not (first/'continuations/001/native-intent.json').exists()


def test_hint_symlink_does_not_write_outside_workspace(tmp_path):
    root=scene(tmp_path);job=c.build_job(root,1,'H',[])
    start_clock(root,'test accepted hint');anchor=budget.accept_node(root,job)
    outside=tmp_path/'untouched';outside.write_text('Original outside file')
    path=c.workspace(root,1)/'work/budget-status.json';path.symlink_to(outside)
    intent=dict(task_sha256=c.digest(root/'jobs/001.json'),budget_slice=anchor)
    c.write(execution.record(root,1)/'native-intent.json',intent)
    budget.write_node_hint(root,job,intent,budget.snapshot(root),dict(input_tokens=0,output_tokens=0),observed=False)
    assert outside.read_text()=='Original outside file' and path.is_symlink()


def test_settings_without_mode_preserve_the_legacy_hard_contract(tmp_path):
    root=scene(tmp_path)
    settings=c.read(root/'settings.json');settings.pop('node_budget_mode')
    c.write(root/'settings.json',settings);c.write(root/'settings-identity.json',dict(sha256=c.digest(root/'settings.json')))
    originals={p:p.read_bytes() for p in (root/'settings.json',root/'settings-identity.json')}
    assert budget.node_mode(root)=='hard'
    assert controller.run(root)['status']=='native_stopped'
    assert c.read(execution.record(root,1)/'native-outcome.json')['stop_reason'] in {'node_slice_token_limit','node_slice_time_limit'}
    assert all(p.read_bytes()==value for p,value in originals.items())
