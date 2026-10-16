"""Protocol 17 closeout through CLI, native processes and isolated adapters."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from scidiscovery.research_loop import budget, cli, contracts as c, controller, delivery, native
from test_delivery import FAKE_HARNESS, descriptor, delivery_policy
from test_history_handoff import finish


NATIVE = r'''import json,os,pathlib,sys
args=sys.argv[1:];prompt=sys.stdin.read()
work=pathlib.Path(os.environ['THIN_HWA_WORKSPACE'])
root=pathlib.Path(os.environ['THIN_HWA_JOB_MANIFEST']).parents[1]
(work/'work/native-prompt').write_text(prompt)
job=json.loads((work/'science-task.json').read_text())
assert job['role']=='A'
manifest=json.loads(pathlib.Path(os.environ['THIN_HWA_JOB_MANIFEST']).read_text())
index=manifest['step']-FIRST_STEP
item=SCENARIO[index]
with (work/'work/launches').open('a') as f:f.write('resume\n' if 'resume' in args else 'exec\n')
thread='11111111-2222-4333-8444-555555555555'
print(json.dumps(dict(type='thread.started',thread_id=thread)),flush=True)
home=pathlib.Path(os.environ['THIN_HWA_NATIVE_HOME'])
if item.get('crash') and 'resume' not in args:
 p=home/'sessions/rollout.jsonl';p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(dict(type='session_meta',payload=dict(id=thread,cwd=str(work))))+'\n')
 (work/'work/checkpoint').write_text('retained original task')
 print(json.dumps(dict(type='turn.completed',usage=dict(input_tokens=7,cached_input_tokens=2,output_tokens=3))),flush=True)
 sys.exit(7)
if 'resume' in args:
 assert thread in args and (work/'work/checkpoint').read_text()=='retained original task'
if 'closeout' in job and 'catalogue' in job['closeout']['sources']:
 catalogue=json.loads((work/job['closeout']['sources']['catalogue']).read_text())
 assert any(r['candidate_id']==item['candidate'] for r in catalogue['items'])
payload=dict(summary='A bounded choice',scientific_result='Exact public evidence; target performance remains unknown.',
 limitations=item.get('limitations',['Transport fixture; target performance unasserted']),implementation_selection=None,search_review=None,
 progress_assessment=None,decision_request=None,portfolio_review=None,
 next_action=item['action'],candidate_recommendation=item.get('candidate'),route_reason='Scientific selection within original authorization')
pathlib.Path(args[args.index('--output-last-message')+1]).write_text(json.dumps(payload))
print(json.dumps(dict(type='turn.completed',usage=dict(input_tokens=7,cached_input_tokens=2,output_tokens=3))),flush=True)
'''


def scene(tmp_path, actions, *, count=2, audit=True, selective_failure=False, max_tokens=100000, max_seconds=600,node_budget_mode='soft'):
    if shutil.which('bwrap') is None:
        pytest.skip('Actual isolated adapter required')
    root=tmp_path/'instance';public=tmp_path/'public';(public/'harness').mkdir(parents=True)
    harness=FAKE_HARNESS.replace("mode=meta['mode']", "mode='leak' if row['run_id']==1 else 'ok'") if selective_failure else FAKE_HARNESS
    for name in ('exp_cli.py','runner.py','train.csv','val.csv','meta.json'):
        path=public/'harness'/name
        if name=='exp_cli.py':path.write_text(harness)
        elif name=='meta.json':c.write(path,dict(mode='ok',control_path=str(root/'settings.json'),hidden_path=str(tmp_path/'hidden')))
        else:path.write_text('fixture public input\n')
    objective=public/'objective.md';objective.write_text('Choose a candidate for delivery while carrying scientific uncertainty.')
    launcher=tmp_path/'native.py';launcher.write_text('SCENARIO='+repr(actions)+'\nFIRST_STEP='+str(5 if count>128 else 3)+'\n'+NATIVE)
    controller.prepare(root,objective,public,[sys.executable,str(launcher)],max_tokens=max_tokens,max_seconds=max_seconds,max_steps=32,
        model='no-model',reasoning_effort='high',search_policy=None,node_budget_mode=node_budget_mode,
        resume_policy=dict(max_attempts=2,protocol='codex_exec_resume',usage_scope='turn',output_repair=True),
        node_budget_policy={r:dict(max_observed_tokens=2000,max_seconds=60) for r in 'HWAE'},
        candidate_audit_policy={'version':1} if audit else None,
        history_observer=dict(adapter=str(Path(__file__).resolve().parents[2]/'scripts/observe_covshift_candidates.py'),
            config=dict(runs='runs',evaluation_key='fixture-public')),
        delivery_policy=delivery_policy(descriptor(root,public)))
    (root/'runs').mkdir();(root/'submission').mkdir()
    (root/'runs/model.bin').write_bytes(b'exact original fixture model')
    finish(root,1,'H',[],action='experiment')
    rows=[]
    def worker(step,start,end,parents):
        c.build_job(root,step,'W',parents,instruction='Exact scientific question')
        script=c.workspace(root,step)/'artifacts/train.py'
        rows.extend(dict(run_id=n,ok=True,val_score=.6,val_acc=.6,model_path='/opt/exp/runs/model.bin',script=str(script)) for n in range(start,end+1))
        (root/'runs/results.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
        finish(root,step,'W',parents,files={'train.py':'def train(train_df,val_df): return None\n'})
    worker(2,1,min(count,128),[1])
    if count>128:
        finish(root,3,'H',[1,2],action='experiment')
        worker(4,129,count,[3])
    return root


def command(root, action='closeout', *extra):
    env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[2]/'src')}
    result=subprocess.run([sys.executable,'-m','scidiscovery.research_loop.cli',action,'--root',str(root),*extra],
        text=True,capture_output=True,timeout=60,env=env)
    assert result.returncode in (0,2),result.stdout+result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize('limitations,shown',[
    ([],[]),
    (['A whole caveat'],['A whole caveat']),
    ([*['Caveat '+str(n) for n in range(1,5)],'Broader shifts remain unresolved',
      'Required audited-score plateau remains unestablished'],['Caveat '+str(n) for n in range(1,5)]),
    (['长限制'*400,'Escaped caveat: "quoted"\\newline\n',*['Later '+str(n) for n in range(5)]],
     ['Escaped caveat: "quoted"\\newline\n',*['Later '+str(n) for n in range(3)]]),
])
def test_public_closeout_limitations_are_bounded_and_link_complete_original(tmp_path,limitations,shown):
    root=scene(tmp_path,[dict(action='deliver',candidate='run-1',limitations=limitations)])
    result=command(root)
    assert result['status']=='delivery_confirmed',result
    for view in (result,command(root,'status')['closeout'],command(root),command(root,'closeout','--export-only')):
        assert view['scientific_limitations']==shown
        assert view['limitations_omitted_count']==len(limitations)-len(shown)
        assert len((json.dumps(view['scientific_limitations'],ensure_ascii=False,indent=2)+'\n').encode())<=1024
        assert view['limitations_ref']==dict(path=view['scientific_output_ref'],field='limitations')
        original=c.read(Path(view['limitations_ref']['path']))
        assert original['limitations']==limitations
        assert view['limitations_ref']['field'] in original
        assert 'limitations_omitted_count' not in original and 'limitations_ref' not in original


def test_empty_export_has_no_scientific_limitations_original(tmp_path):
    public=tmp_path/'public';public.mkdir();goal=public/'goal';goal.write_text('Bounded export fixture.')
    root=tmp_path/'instance'
    controller.prepare(root,goal,public,['never-launched'],max_tokens=10000,max_seconds=120,max_steps=4,
        model='no-model',reasoning_effort='high',search_policy=None,
        node_budget_policy={role:dict(max_observed_tokens=1000,max_seconds=30) for role in 'HWAE'},
        delivery_policy=dict(delivery_policy(None),submit_seconds=0,confirm_seconds=0))
    result=command(root,'closeout','--export-only')
    assert result['status']=='exported_unsubmitted'
    assert result['scientific_limitations']==[] and result['limitations_omitted_count']==0
    assert result['scientific_output_ref'] is None and result['limitations_ref'] is None


@pytest.mark.parametrize('action',['extract','continue_w','revise_h'])
def test_closeout_legal_role_action_is_corrected_before_explicit_delivery(tmp_path,action):
    root=scene(tmp_path,[dict(action=action,candidate='run-1'),dict(action='deliver',candidate='run-1')])
    result=command(root)
    assert result['status']=='delivery_confirmed',result
    assert [c.read(p)['role'] for p in sorted((root/'jobs').glob('*.json'))]==['H','W','A','A']
    assert c.read(root/'jobs/004.json')['author_correction']['reason']=='delivery_authorization_required'
    assert result['goal_completion']=='not_asserted'
    assert command(root,'status')['closeout']['status']==result['status']
    assert len(budget.closeout_state(root)['actions'])==2


def test_normal_audits_do_not_consume_author_corrections(tmp_path):
    root=scene(tmp_path,[*[dict(action='audit',candidate=f'run-{n}') for n in (1,2,3)],dict(action='deliver',candidate='run-2')],count=3)
    result=command(root)
    assert result['status']=='delivery_confirmed',result
    assert result['existing_A_recommendation']==dict(candidate_id='run-2',author_step=6)
    assert all(c.read(root/'jobs'/f'{step:03d}.json').get('author_correction') is None for step in (3,4,5,6))
    assert c.read(c.workspace(root,4)/'science-task.json')['candidate_audit']['qualification']=='passed'
    assert len(budget.closeout_state(root)['actions'])==2


def test_known_audit_failure_can_reselect_within_same_budget(tmp_path):
    root=scene(tmp_path,[dict(action='deliver',candidate='run-1'),dict(action='deliver',candidate='run-2')],selective_failure=True)
    original=(root/'settings.json').read_bytes()
    result=command(root)
    assert result['status']=='delivery_confirmed',result
    actions=budget.closeout_state(root)['actions']
    assert [row['intent']['action_kind'] for row in actions]==['submit','submit','confirm']
    assert actions[0]['outcome']['result']['failure_phase']=='audit'
    assert c.read(root/'runs/submitted.json')['run_id']==2
    assert result['existing_A_recommendation']==dict(candidate_id='run-2',author_step=4)
    assert (root/'settings.json').read_bytes()==original
    assert command(root,'run')['status']=='delivery_confirmed'
    assert len(budget.closeout_state(root)['actions'])==3


@pytest.mark.parametrize('mode',['soft','hard'])
def test_known_closeout_abort_resumes_exact_session(tmp_path,mode):
    root=scene(tmp_path,[dict(action='deliver',candidate='run-1',crash=True)],max_tokens=3500,node_budget_mode=mode)
    settings=(root/'settings.json').read_bytes()
    assert command(root)['status']=='closeout_native_unsealed'
    original=(root/'jobs/003.json').read_bytes()
    assert command(root,'status')['closeout']['status']=='closeout_native_unsealed'
    result=command(root,'worker-resume','--step','3')
    assert result['status']=='delivery_confirmed',result
    assert (root/'jobs/003.json').read_bytes()==original
    assert (c.workspace(root,3)/'work/launches').read_text()=='exec\nresume\n'
    assert command(root,'run')['status']=='delivery_confirmed'
    assert len(list((root/'native-evidence/003/continuations').glob('*/native-intent.json')))==1
    assert (root/'settings.json').read_bytes()==settings
    assert not any(c.read(path)['kind']=='budget_amend' for path in (root/'control-ledger').glob('*.json'))


@pytest.mark.parametrize('mode',['soft','hard'])
def test_closeout_resume_retains_original_node_allowance_and_delivery_floor(tmp_path,monkeypatch,mode):
    from scidiscovery.research_loop import execution
    root=scene(tmp_path,[dict(action='deliver',candidate='run-1',crash=True)],node_budget_mode=mode)
    assert command(root)['status']=='closeout_native_unsealed'
    job=c.read(root/'jobs/003.json');paths=execution.records(root,3)
    tokens,seconds=budget._attempt_consumption(root,job,paths)
    settings=c.settings(root);policy=budget.node_limits(root,job)
    floor=budget.closeout_floor(settings,preparation_seconds=budget.closeout_state(root)['begin']['preparation_seconds'])
    limits=budget.snapshot(root);meter=native.usage(root);used=budget.used_steps(root)
    current_limits=dict(limits);current_meter=dict(meter);current_steps=[used]
    monkeypatch.setattr(budget,'snapshot',lambda root:dict(current_limits))
    monkeypatch.setattr(native,'usage',lambda root:dict(current_meter))
    monkeypatch.setattr(budget,'used_steps',lambda root:current_steps[0])
    for boundary in ('tokens','seconds','steps'):
        for delta in (-1,0,1):
            current_limits.update(limits);current_meter.update(meter);current_steps[0]=used
            if boundary=='tokens':
                needed=0 if mode=='soft' else policy['max_observed_tokens']-tokens
                current_meter['observed_tokens']=limits['max_tokens']-(needed+floor['tokens']+delta)
            elif boundary=='seconds':
                needed=0 if mode=='soft' else policy['max_seconds']-seconds
                current_limits['seconds_remaining']=needed+floor['seconds']+delta
            else:
                current_steps[0]=settings['max_steps']-(1+floor['steps']+delta)
            blocked=delta<0 or mode=='soft' and boundary!='steps' and delta==0
            if blocked:
                with pytest.raises(budget.NodeBudgetUnavailable,match='worker_resume_budget_unavailable'):
                    budget.accept_continuation(root,job,paths)
            else:
                anchor=budget.accept_continuation(root,job,paths)
                assert anchor['previous_tokens']==tokens and anchor['previous_seconds']==seconds
                assert anchor['limits']==policy and anchor['shared_limits']=={key:limits[key] for key in ('max_tokens','max_seconds')}
    current_limits.update(limits);current_meter.update(meter);current_steps[0]=used
    if mode=='hard':
        current_meter['observed_tokens']=limits['max_tokens']-(policy['max_observed_tokens']-tokens+floor['tokens'])
        anchor=budget.accept_continuation(root,job,paths)
        record=paths[0]/'continuations/001'
        c.write(record/'native-intent.json',dict(task_sha256=c.digest(root/'jobs/003.json'),attempt=1,budget_slice=anchor,
            previous=execution.proof(paths[0]),root_intent_sha256=c.digest(paths[0]/'native-intent.json')))
        assert budget.node_admission(root,job,ignore_step=3,intent=c.read(record/'native-intent.json')) is None
        assert not (record/'native-process.json').exists()
    else:
        assert not (paths[0]/'continuations').exists()


def test_late_candidate_is_locatable_and_resolved_without_historical_pack(tmp_path):
    root=scene(tmp_path,[dict(action='deliver',candidate='run-140')],count=140)
    result=command(root)
    assert result['status']=='delivery_confirmed',result
    job=c.read(root/'jobs/005.json');refs=job['delivery_sources']
    assert refs['catalogue'] is True and len(refs['items'])==140 and refs['omitted_count']==0
    assert refs['items'][-1]['candidate_id']=='run-140' and refs['items'][-1]['source_step']==4
    assert len(list((root/'host-delivery/resolved').glob('*.json')))==1
    assert c.read(root/'runs/submitted.json')['run_id']==140


def test_transient_selected_preparation_failure_is_retryable_without_new_author(tmp_path,monkeypatch):
    root=scene(tmp_path,[dict(action='deliver',candidate='run-1')])
    original=delivery.freeze_sources
    calls=[]
    def unavailable(*args,**kwargs):
        calls.append(kwargs.get('candidate_id'))
        raise delivery.DeliveryUnresolved('delivery_source_time_limit')
    monkeypatch.setattr(delivery,'freeze_sources',unavailable)
    result=controller.closeout(root)
    assert result['status']=='closeout_preparation_unavailable' and calls==['run-1']
    assert budget.closeout_state(root)['begin']['mode']=='model'
    assert not budget.closeout_state(root)['actions']
    assert cli.status(root)['closeout_preparation']['last_failure']=='delivery_source_time_limit'
    original_job=(root/'jobs/003.json').read_bytes()
    monkeypatch.setattr(delivery,'freeze_sources',original)
    assert command(root,'run')['status']=='delivery_confirmed'
    assert (root/'jobs/003.json').read_bytes()==original_job
    assert (c.workspace(root,3)/'work/launches').read_text()=='exec\n'


def test_unknown_submission_never_replays_or_selects_a_new_candidate(tmp_path,monkeypatch):
    root=scene(tmp_path,[dict(action='deliver',candidate='run-1')])
    def unknown(root,intent,*args,**kwargs):
        return delivery._result(intent['binding'],'unknown','accepted submission has no verified outcome',cleanup_confirmed=False)
    monkeypatch.setattr(delivery,'invoke',unknown)
    assert controller.closeout(root)['status']=='delivery_unknown'
    before={str(p):p.read_bytes() for p in (root/'control-ledger').glob('*.json')}
    result=command(root,'run')
    assert result['status']=='delivery_unknown',result
    assert command(root,'status')['closeout']['status']=='delivery_unknown'
    assert len(budget.closeout_state(root)['actions'])==1
    assert before=={str(p):p.read_bytes() for p in (root/'control-ledger').glob('*.json')}
    assert (c.workspace(root,3)/'work/launches').read_text()=='exec\n'
    assert not (root/'runs/submitted.json').exists()


@pytest.mark.parametrize('action,status',[('finish','exported_unsubmitted'),('wait','closeout_waiting')])
def test_scientific_stop_and_wait_do_not_authorize_delivery(tmp_path,action,status):
    root=scene(tmp_path,[dict(action=action,candidate='run-1')])
    result=command(root)
    assert result['status']==status and result['goal_completion']=='not_asserted'
    assert command(root,'run')['status']==status
    assert command(root,'status')['closeout']['status']==status
    assert not budget.closeout_state(root)['actions'] and not (root/'runs/submitted.json').exists()


def test_unsupported_action_has_finite_correction_without_implicit_extract_delivery(tmp_path):
    root=scene(tmp_path,[dict(action='extract',candidate='run-1') for _ in range(3)])
    result=command(root)
    assert result['status']=='closeout_unresolved' and result['reason']=='semantic_correction_limit',result
    assert len(list((root/'jobs').glob('*.json')))==5  # Initial invalid A and two author clarifications.
    assert not budget.closeout_state(root)['actions'] and not (root/'runs/submitted.json').exists()
    assert command(root,'run')['reason']=='semantic_correction_limit'


def test_initial_preparation_failure_retains_failure_without_freezing_export(tmp_path,monkeypatch):
    root=scene(tmp_path,[dict(action='deliver',candidate='run-1')])
    def unavailable(*args,**kwargs):
        raise delivery.DeliveryUnresolved('delivery_catalogue_capacity')
    monkeypatch.setattr(delivery,'catalogue_sources',unavailable)
    assert controller.closeout(root)['status']=='closeout_preparation_unavailable'
    assert budget.closeout_state(root)['begin'] is None
    assert cli.status(root)['closeout_preparation']['last_failure']=='delivery_catalogue_capacity'
    assert command(root)['status']=='delivery_confirmed'


def test_unknown_resolver_cleanup_blocks_repreparation(tmp_path,monkeypatch):
    root=scene(tmp_path,[dict(action='deliver',candidate='run-1')])
    def unknown(*args,**kwargs):
        raise delivery.DeliveryUnresolved('delivery_cleanup_unknown')
    monkeypatch.setattr(delivery,'freeze_sources',unknown)
    assert controller.closeout(root)['reason']=='delivery_cleanup_unknown'
    assert budget.execution_blocked(root)
    assert command(root,'run')['reason']=='delivery_original_execution_unresolved'
    assert len(list((root/'host-delivery/preparation').glob('*.json')))==1
    assert not budget.closeout_state(root)['actions']


def test_ordinary_a_deliver_uses_exact_w_source_without_another_scientific_author(tmp_path):
    from test_closeout import FAKE_NATIVE, real_chain
    launcher=FAKE_NATIVE.replace(";assert task['closeout']['source_cutoff']==2", "")
    root=real_chain(tmp_path,max_steps=8,launcher_text=launcher)
    result=command(root,'run')
    assert result['status']=='delivery_confirmed',result
    jobs=[c.read(path) for path in sorted((root/'jobs').glob('*.json'))]
    assert [job['role'] for job in jobs]==['H','W','A']
    assert all(job.get('purpose') is None for job in jobs)
    assert result['used_steps']==5 and result['goal_completion']=='not_asserted'
    assert budget.closeout_state(root)['begin']['authorization_step']==3
    binding=budget.closeout_state(root)['actions'][0]['intent']['binding']
    assert binding['source']['objects']['source.py']['sha256']==c.digest(c.workspace(root,2)/'artifacts/train.py')
    phases=[c.read(path)['phase'] for path in (root/'host-delivery/leaf-output').glob('*.json')]
    assert phases.count('audit')==1 and phases.count('promote')==1 and phases.count('confirm')==1
    assert command(root,'run')['status']=='delivery_confirmed'
    assert len(list((root/'jobs').glob('*.json')))==3


def test_ordinary_extract_keeps_e_scientific_evidence_role_before_direct_delivery(tmp_path):
    from test_closeout import FAKE_NATIVE, real_chain
    launcher=FAKE_NATIVE.replace(";assert task['closeout']['source_cutoff']==2", "")
    launcher=launcher.replace("if role=='A':", "if role=='E':\n payload['scientific_result']='Requested evidence remains limited; no target result is inferred.'\nif role=='A':")
    launcher=launcher.replace("pathlib.Path(args[args.index('--output-last-message')+1]).write_text", "if role=='A' and json.loads(pathlib.Path(os.environ['THIN_HWA_JOB_MANIFEST']).read_text())['step']==3:\n payload.update(next_action='extract',route_reason='Read the scientific source for the unresolved target evidence question')\npathlib.Path(args[args.index('--output-last-message')+1]).write_text")
    root=real_chain(tmp_path,max_steps=10,launcher_text=launcher)
    result=command(root,'run')
    assert result['status']=='delivery_confirmed',result
    jobs=[c.read(path) for path in sorted((root/'jobs').glob('*.json'))]
    assert [job['role'] for job in jobs]==['H','W','A','E','A']
    assert jobs[3]['evidence_return']==dict(role='A',step=3)
    assert not list((c.workspace(root,4)/'artifacts').iterdir())
    assert c.read(root/'runs/submitted.json')['run_id']==1
    assert len(budget.closeout_state(root)['actions'])==2


def test_ordinary_delivery_missing_choice_uses_bounded_author_clarification(tmp_path):
    root=scene(tmp_path,[dict(action='deliver',candidate=None),dict(action='deliver',candidate='run-1')])
    result=command(root,'run')
    assert result['status']=='delivery_confirmed',result
    assert c.read(root/'jobs/003.json').get('purpose') is None
    corrected=c.read(root/'jobs/004.json')
    assert corrected['purpose']=='closeout' and corrected['author_correction']['root']['step']==3
    assert corrected['author_correction']['reason']=='delivery_no_decision'
    assert len(budget.closeout_state(root)['actions'])==2


def test_ordinary_delivery_audit_failure_reselects_without_e_or_repeated_original_author(tmp_path):
    root=scene(tmp_path,[dict(action='deliver',candidate='run-1'),dict(action='deliver',candidate='run-2')],selective_failure=True)
    result=command(root,'run')
    assert result['status']=='delivery_confirmed',result
    jobs=[c.read(path) for path in sorted((root/'jobs').glob('*.json'))]
    assert [job['role'] for job in jobs]==['H','W','A','A']
    assert jobs[2].get('purpose') is None and jobs[3]['purpose']=='closeout'
    assert jobs[3].get('author_correction') is None
    assert [row['intent']['action_kind'] for row in budget.closeout_state(root)['actions']]==['submit','submit','confirm']
    assert c.read(root/'runs/submitted.json')['run_id']==2


def test_budget_shortage_keeps_pending_closeout_distinct_from_operator_export(tmp_path):
    # The frozen reserve fits at prepare. The two retained scientific nodes use
    # twenty tokens, so a new full A plus the external floor no longer fits.
    root=scene(tmp_path,[dict(action='deliver',candidate='run-1')],max_tokens=1100)
    result=command(root)
    assert result['status']=='closeout_budget_unavailable',result
    begin=budget.closeout_state(root)['begin']
    assert begin['mode']=='model' and begin['delivery_sources']['catalogue'] is True
    assert command(root,'status')['closeout']['status']=='closeout_budget_unavailable'
    assert command(root,'run')['status']=='closeout_budget_unavailable'
    assert len(list((root/'jobs').glob('*.json')))==2 and not budget.closeout_state(root)['actions']
    assert command(root,'closeout','--export-only')['status']=='exported_unsubmitted'
    assert budget.closeout_state(root)['begin']==begin
