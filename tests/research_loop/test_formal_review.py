"""Exact review through existing native nodes; scripted transport is not Codex qualification."""
import sys

import pytest

from scidiscovery.operations.review_rules import independence
from scidiscovery.research_loop import budget, contracts as c, controller, formal_review as review, semantic
from test_history_handoff import finish


# This independent local process supplies protocol-shaped native/session events.
# It never calls a model, backend or solver. Its identities are synthetic.
LAUNCHER = '''import json,os,pathlib,sys,uuid
work=pathlib.Path(os.environ['THIN_HWA_WORKSPACE']);step=int(work.name)
task=json.loads((work/'science-task.json').read_text());sys.stdin.read()
thread=str(uuid.uuid5(uuid.NAMESPACE_URL,'formal-native-'+str(2 if step==4 and os.environ.get('REVIEW_REUSE_AUTHOR') else step)))
home=pathlib.Path(os.environ['CODEX_HOME']);sessions=home/'sessions';sessions.mkdir(parents=True,exist_ok=True)
if not (step==2 and os.environ.get('REVIEW_MISSING_AUTHOR')):
 (sessions/(thread+'.jsonl')).write_text(json.dumps({'type':'session_meta','payload':{'id':thread,'cwd':str(work)}})+'\\n')
print(json.dumps({'type':'thread.started','thread_id':thread}),flush=True)
if 'review' in task:
 assert 'history' not in task and 'parents' not in task
 assert (work/task['review']['subject']).read_text()=='a scientific implementation'
 value=dict(verdict='pass',summary='Exact fixture review',scientific_result='No fixture defect observed.',limitations=['Synthetic native transport only.'])
else:
 value=dict(summary='Fixture science',scientific_result='A bounded finding.',limitations=['No real science.'],implementation_selection=None)
 role=task['role']
 if role=='H':value.update(next_action='experiment',route_reason='Implement the question',search_plan=None)
 if role=='W':
  (work/'artifacts/model.txt').write_text('a scientific implementation')
  value.update(stage_intent='review',mechanism_findings=None)
 if role=='A':
  mode=os.environ.get('REVIEW_UNAVAILABLE_ROUTE','finish')
  request=step==3 or bool(os.environ.get('REVIEW_MISSING_AUTHOR')) and (step<5 or mode!='finish')
  value.update(next_action='extract' if step==4 and mode=='extract' else 'formal_review' if request else 'finish',route_reason='Assess the selected implementation '+str(step),candidate_recommendation=None,search_review=None,progress_assessment=None,decision_request=None,portfolio_review=None)
  if request:value['implementation_selection']=['W002-I001']
  if step==5 and not os.environ.get('REVIEW_MISSING_AUTHOR'):assert task['formal_review_feedback']['status']==('not_qualified' if os.environ.get('REVIEW_REUSE_AUTHOR') else 'passed')
args=sys.argv[1:];pathlib.Path(args[args.index('--output-last-message')+1]).write_text(json.dumps(value))
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':10,'cached_input_tokens':0,'output_tokens':5}}),flush=True)
'''


def prepare(tmp_path, launcher, *, enabled=True, steps=6, delivery_policy=None, decision_contract_version=None):
    public=tmp_path/'public';public.mkdir()
    objective=public/'objective.md';objective.write_text('Review one exact authored scientific object when useful.')
    root=tmp_path/'instance'
    controller.prepare(root,objective,public,launcher,max_tokens=2000,max_seconds=60,max_steps=steps,
        model='no-model',reasoning_effort='high',search_policy=None,experiment_mode='external',
        formal_review_policy=dict(version=1) if enabled else None,delivery_policy=delivery_policy,
        node_budget_policy={role:dict(max_observed_tokens=100,max_seconds=5) for role in 'HWAE'} if delivery_policy is not None else None,
        decision_contract_version=decision_contract_version)
    return root


def scripted(tmp_path, monkeypatch, *, reuse=False, missing=False, unavailable_route='finish', delivery_policy=None):
    launcher=tmp_path/'codex'
    launcher.write_text('#!'+sys.executable+'\n'+LAUNCHER)
    launcher.chmod(0o700)
    home=tmp_path/'actual-native-home';home.mkdir()
    monkeypatch.setenv('CODEX_HOME',str(home))
    if reuse:monkeypatch.setenv('REVIEW_REUSE_AUTHOR','1')
    else:monkeypatch.delenv('REVIEW_REUSE_AUTHOR',raising=False)
    if missing:monkeypatch.setenv('REVIEW_MISSING_AUTHOR','1')
    else:monkeypatch.delenv('REVIEW_MISSING_AUTHOR',raising=False)
    monkeypatch.setenv('REVIEW_UNAVAILABLE_ROUTE',unavailable_route)
    return prepare(tmp_path,[str(launcher)],steps=10,delivery_policy=delivery_policy),home


def test_independence_needs_every_verified_participant():
    assert independence({('engine','author')},{('engine','reviewer')})=='independent'
    assert independence({('engine','author')},{('engine','reviewer'),('engine','author')})=='overlap'
    assert independence(set(),{('engine','reviewer')},authors_complete=False)=='unknown'


@pytest.mark.process_e2e
def test_real_native_route_freezes_exact_review_and_uses_actual_home(tmp_path,monkeypatch):
    root,home=scripted(tmp_path,monkeypatch)
    result=controller.run(root)
    assert result['status']=='finish' and result['completed_steps']==5
    job=c.read(root/'jobs/004.json');record=c.host_record(c.workspace(root,4))
    assert job['role']=='A' and job['purpose']=='formal_review'
    assert set(c.read(record/'science-output.json'))=={'verdict','summary','scientific_result','limitations'}
    seal=c.read(record/'result-identity.json');proof=c.read(root/seal['formal_review']['path'])
    assert proof['status']=='passed' and proof['independence']=='independent'
    assert proof['subject']['producer_step']==2
    own=c.read(root/seal['native_authorship']['path'])
    assert own['complete'] and own['attempts'][0]['session']['home']==str(home)
    assert home!=root/'native-homes/004'
    assert review.require_review(root,proof['subject'],seal['formal_review'])==seal['formal_review']
    wrong=dict(proof['subject'],material={**proof['subject']['material'],'source':str(root/'same-bytes-other-origin')})
    with pytest.raises(ValueError,match='Exact subject'):
        review.require_review(root,wrong,seal['formal_review'])
    before={path:path.read_bytes() for path in (root/'jobs').glob('*.json')}
    assert controller.run(root)['status']=='finish'
    assert all(path.read_bytes()==data for path,data in before.items())


@pytest.mark.process_e2e
def test_native_author_session_cannot_review_itself_even_with_pass(tmp_path,monkeypatch):
    root,_=scripted(tmp_path,monkeypatch,reuse=True)
    assert controller.run(root)['status']=='finish'
    seal=c.read(c.host_record(c.workspace(root,4))/'result-identity.json')
    proof=c.read(root/seal['formal_review']['path'])
    assert proof['verdict']=='pass' and proof['independence']=='overlap' and proof['status']=='not_qualified'
    with pytest.raises(ValueError,match='independent sealed pass'):
        review.require_review(root,proof['subject'],seal['formal_review'])


@pytest.mark.process_e2e
def test_unknown_identity_preserves_science_and_rewording_cannot_repeat_unavailable(tmp_path,monkeypatch):
    root,_=scripted(tmp_path,monkeypatch,missing=True)
    result=controller.run(root)
    assert result['status']=='finish' and result['completed_steps']==5
    assert not any((c.host_record(c.workspace(root,step))/'formal-review.json').exists() for step in range(1,6))
    assert c.validate(c.workspace(root,3))['next_action']=='formal_review'
    assert c.validate(c.workspace(root,3))['route_reason']!=c.validate(c.workspace(root,4))['route_reason']
    assert review.unavailable(root,3)['failure_key']==review.unavailable(root,4)['failure_key']
    view=c.read(c.workspace(root,5)/'science-task.json')
    assert view['formal_review_feedback']['status']=='unavailable'
    assert view['formal_review_feedback']['formal_review']['available'] is False
    assert 'finish' in view['formal_review_feedback']['alternative_examples']
    assert view['control_request']['remaining_author_corrections']==1
    assert 'formal_review' in c.result_schema('A',**c.response_options(c.read(root/'jobs/005.json')))['properties']['next_action']['enum']


@pytest.mark.process_e2e
def test_unavailable_failure_allowance_survives_extraction_and_restart(tmp_path,monkeypatch):
    root,_=scripted(tmp_path,monkeypatch,missing=True,unavailable_route='extract')
    settings_original=(root/'settings.json').read_bytes()
    result=controller.run(root)
    assert result['status']=='formal_review_blocked' and result['completed_steps']==7,result
    assert result['reason']=='formal_review_unavailable_correction_limit' and result['recovery_conditions']
    assert result['goal_completion']=='not_asserted'
    assert [c.read(root/'jobs'/f'{step:03d}.json')['role'] for step in (4,5,6,7)]==['A','E','A','A']
    assert review.unavailable_attempts(root,7)==[3,6,7]
    correction=c.read(root/'jobs/007.json')['author_correction']
    assert correction['root']['step']==3 and semantic.accepted(root,correction,8)==semantic.MAX_AUTHOR_CORRECTIONS
    assert not (root/'jobs/008.json').exists()
    assert result['usage']['observed_tokens']==7*15 and budget.used_steps(root)==7
    limits=budget.snapshot(root)
    assert limits['max_tokens']==2000 and limits['max_seconds']==60
    assert limits['consumed_seconds']>0 and limits['seconds_remaining']<60
    assert not list((root/'native-evidence').glob('*/formal-review.json'))
    originals={path:path.read_bytes() for path in [*(root/'jobs').glob('*.json'),
        *(root/'native-evidence').glob('*/formal-review-unavailable.json')]}
    used=budget.used_steps(root)
    again=controller.run(root)
    assert again['status']==result['status'] and again['recovery_conditions']==result['recovery_conditions']
    assert budget.used_steps(root)==used and all(path.read_bytes()==raw for path,raw in originals.items())
    assert again['usage']==result['usage'] and (root/'settings.json').read_bytes()==settings_original
    assert budget.snapshot(root)['consumed_seconds']>=limits['consumed_seconds']
    assert not (root/'jobs/008.json').exists()


@pytest.mark.process_e2e
def test_exhausted_unavailable_review_enters_existing_export_closeout(tmp_path,monkeypatch):
    policy=dict(closeout_a=dict(max_observed_tokens=30,max_seconds=1),inflight_tokens=0,
        cleanup_seconds=0,submit_seconds=0,confirm_seconds=0,adapter=None)
    root,_=scripted(tmp_path,monkeypatch,missing=True,unavailable_route='repeat',delivery_policy=policy)
    result=controller.run(root)
    assert result['status']=='exported_unsubmitted' and result['goal_completion']=='not_asserted',result
    state=budget.closeout_state(root)
    assert state['begin']['stop_reason']=='formal_review_unavailable_correction_limit'
    assert state['begin']['source_cutoff']==5 and state['actions']==[]
    assert result['current_actual'] is None and not (root/'jobs/006.json').exists()
    before={path:path.read_bytes() for path in (root/'control-ledger').glob('*.json')}
    assert controller.run(root)['status']=='exported_unsubmitted'
    assert budget.closeout_state(root)['begin']==state['begin']
    assert all(path.read_bytes()==raw for path,raw in before.items())


@pytest.mark.parametrize('selection,reason',[
    ([], 'formal_review_subject_missing_or_ambiguous'),
    (['W002-I001'], 'reviewer_identity_unsupported'),
])
def test_unavailable_subject_or_launcher_returns_ordinary_author_not_qualification(tmp_path,monkeypatch,selection,reason):
    root=prepare(tmp_path,['unsupported-launcher'])
    finish(root,1,'H',[],action='experiment')
    finish(root,2,'W',[1],files={'model.txt':'a scientific implementation','other.txt':'a different exact subject'})
    job,_,_=finish(root,3,'A',[1,2],action='formal_review',selection=selection)
    # Isolate the launcher-rejection branch; this stand-in grants no native identity/review.
    monkeypatch.setattr(review,'authors',lambda *args:dict(complete=True,participants=[dict(engine='fixture',session='author')]))
    route=review.request_route(root,job,c.validate(c.workspace(root,3)),[1,2,3])
    assert route[0]=='A' and route[3]['kind']=='formal_review_unavailable'
    assert review.unavailable(root,3)['failure']['reason']==reason
    route8=semantic.effective_route(root,3,c.validate(c.workspace(root,3)),job,(*route,1,2,None))
    child=c.build_job(root,4,'A',route8[1],instruction=route8[2],evidence_return=route8[3],author_correction=route8[7])
    assert child.get('purpose') is None and not child.get('formal_review')
    assert not (c.host_record(c.workspace(root,4))/'formal-review.json').exists()
    child,_,_=finish(root,4,'A',route8[1],action='formal_review',selection=['W002-I002'])
    changed=review.request_route(root,child,c.validate(c.workspace(root,4)),[1,2,4])
    changed8=semantic.effective_route(root,4,c.validate(c.workspace(root,4)),child,(*changed,1,2,None))
    assert review.unavailable(root,3)['failure_key']!=review.unavailable(root,4)['failure_key']
    assert changed8[7]['root']['step']==4 and semantic.accepted(root,changed8[7],5)==0


def test_ordinary_a_and_pass_text_do_not_gain_formal_qualification(tmp_path):
    root=prepare(tmp_path,['fixture'],enabled=False)
    finish(root,1,'H',[],action='analyze')
    _,_,record=finish(root,2,'A',[1],text='pass: independent and ready to execute')
    assert 'formal_review' not in c.read(record/'result-identity.json')
    assert 'formal_review' not in c.result_schema('A')['properties']['next_action']['enum']
    assert set(review.schema()['properties'])=={'verdict','summary','scientific_result','limitations'}


def test_unavailable_review_preserves_existing_nonreview_author_correction(tmp_path):
    root=prepare(tmp_path,['unsupported-launcher'],decision_contract_version=1)
    finish(root,1,'H',[],action='experiment')
    finish(root,2,'W',[1],files={'model.txt':'a scientific implementation'})
    job,_,_=finish(root,3,'A',[1,2],action='continue_w',selection=['W002-I001'])
    science=c.validate(c.workspace(root,3))
    route=semantic.effective_route(root,3,science,job,(*controller._route(root,3,'A',science,job,1,2),None))
    prior=route[7]
    assert prior['reason']=='a_decision_request_missing' and prior['root']['step']==3
    c.build_job(root,4,'A',route[1],instruction=route[2],author_correction=prior)
    job,_,_=finish(root,4,'A',route[1],action='formal_review',selection=['W002-I001'])
    science=c.validate(c.workspace(root,4))
    route=semantic.effective_route(root,4,science,job,(*controller._route(root,4,'A',science,job,1,2),None))
    assert route[7]['root']==prior['root'] and route[7]['reason']==prior['reason']
    assert route[7]['source']['step']==4 and route[3]['kind']=='formal_review_unavailable'
    assert semantic.accepted(root,route[7],5)==1
    child=c.build_job(root,5,'A',route[1],instruction=route[2],evidence_return=route[3],author_correction=route[7])
    assert child['author_correction']==route[7] and not child.get('formal_review')
