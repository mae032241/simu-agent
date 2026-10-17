"""Exact review through existing native nodes; scripted transport is not Codex qualification."""
import sys

import pytest

from scidiscovery.operations.review_rules import independence
from scidiscovery.research_loop import contracts as c, controller, formal_review as review
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
  request=step==3 or bool(os.environ.get('REVIEW_MISSING_AUTHOR'))
  value.update(next_action='formal_review' if request else 'finish',route_reason='Assess the selected implementation '+str(step),candidate_recommendation=None,search_review=None,progress_assessment=None,decision_request=None,portfolio_review=None)
  if request:value['implementation_selection']=['W002-I001']
  if step==5:assert task['formal_review_feedback']['status']==('not_qualified' if os.environ.get('REVIEW_REUSE_AUTHOR') else 'passed')
args=sys.argv[1:];pathlib.Path(args[args.index('--output-last-message')+1]).write_text(json.dumps(value))
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':10,'cached_input_tokens':0,'output_tokens':5}}),flush=True)
'''


def prepare(tmp_path, launcher, *, enabled=True, steps=6):
    public=tmp_path/'public';public.mkdir()
    objective=public/'objective.md';objective.write_text('Review one exact authored scientific object when useful.')
    root=tmp_path/'instance'
    controller.prepare(root,objective,public,launcher,max_tokens=2000,max_seconds=60,max_steps=steps,
        model='no-model',reasoning_effort='high',search_policy=None,experiment_mode='external',
        formal_review_policy=dict(version=1) if enabled else None)
    return root


def scripted(tmp_path, monkeypatch, *, reuse=False, missing=False):
    launcher=tmp_path/'codex'
    launcher.write_text('#!'+sys.executable+'\n'+LAUNCHER)
    launcher.chmod(0o700)
    home=tmp_path/'actual-native-home';home.mkdir()
    monkeypatch.setenv('CODEX_HOME',str(home))
    if reuse:monkeypatch.setenv('REVIEW_REUSE_AUTHOR','1')
    else:monkeypatch.delenv('REVIEW_REUSE_AUTHOR',raising=False)
    if missing:monkeypatch.setenv('REVIEW_MISSING_AUTHOR','1')
    else:monkeypatch.delenv('REVIEW_MISSING_AUTHOR',raising=False)
    return prepare(tmp_path,[str(launcher)],steps=5),home


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
    assert result['status']=='wait' and result['completed_steps']==4
    assert not (root/'jobs/005.json').exists()
    assert not any((c.host_record(c.workspace(root,step))/'formal-review.json').exists() for step in range(1,5))
    assert c.validate(c.workspace(root,3))['next_action']=='formal_review'
    assert c.validate(c.workspace(root,3))['route_reason']!=c.validate(c.workspace(root,4))['route_reason']


def test_ordinary_a_and_pass_text_do_not_gain_formal_qualification(tmp_path):
    root=prepare(tmp_path,['fixture'],enabled=False)
    finish(root,1,'H',[],action='analyze')
    _,_,record=finish(root,2,'A',[1],text='pass: independent and ready to execute')
    assert 'formal_review' not in c.read(record/'result-identity.json')
    assert 'formal_review' not in c.result_schema('A')['properties']['next_action']['enum']
    assert set(review.schema()['properties'])=={'verdict','summary','scientific_result','limitations'}
