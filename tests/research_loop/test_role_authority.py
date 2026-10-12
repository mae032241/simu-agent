"""Model-visible scientific authority without editing original routes or schemas."""
import json
from pathlib import Path

import pytest

from scidiscovery.research_loop import contracts as c, controller, correction, guidance, native
from test_history_handoff import finish

RECIPE = 'Run algorithm Z on an exact 148-cell perturbation grid and fixed seed matrix; reconsider the global robustness gap.'
FAKE = r'''#!/usr/bin/env python
import json,os,pathlib,sys
args=sys.argv[1:];prompt=sys.stdin.read()
work=pathlib.Path(os.environ['THIN_HWA_WORKSPACE']);role=os.environ['THIN_HWA_ROLE'];step=int(work.name)
job=json.loads(pathlib.Path(os.environ['THIN_HWA_JOB_MANIFEST']).read_text())
value=next(s.split('=',1)[1] for s in args if s.startswith('developer_instructions='))
assert json.loads(value)==job['native_role_instruction']
assert prompt.startswith(job['native_role_instruction']+'\n')
assert 'Leave further scientific verification requests to A.' not in prompt
(work/'work/prompt.txt').write_text(prompt)
p=dict(summary='Scientific contribution',scientific_result='Original scientific observation and scope',limitations=['Fake transport only'],implementation_selection=None)
if role=='H':p.update(search_plan=None,next_action='analyze',route_reason='Compare the original mechanism using comparator C')
if role=='A':p.update(search_review=None,candidate_recommendation=None,progress_assessment=None,next_action='continue_w' if step==2 else 'finish',route_reason='Run algorithm Z on an exact 148-cell perturbation grid and fixed seed matrix; reconsider the global robustness gap.' if step==2 else 'Global judgment with limits')
if role=='W':
 task=json.loads((work/'science-task.json').read_text());ctx=task['decision_context']
 assert task['question']!=ctx['original_instruction']
 assert ctx['original_instruction']==json.loads((work/ctx['source_original']).read_text())['route_reason']
 assert 'comparator C' in (work/'inputs/parents/001/conclusion.json').read_text()
 assert 'Keep original data separation' in (work/'inputs/global/objective.md').read_text()
print(json.dumps(dict(type='turn.completed',usage=dict(input_tokens=7,cached_input_tokens=2,output_tokens=3))),flush=True)
pathlib.Path(args[args.index('--output-last-message')+1]).write_text(json.dumps(p))
'''


def prepare(tmp_path, *, marker=1, correction_policy=None, search_policy=None, real=False):
    public=tmp_path/'public';public.mkdir()
    objective=public/'objective.md';objective.write_text('Keep original data separation and compare the mechanism.')
    launcher=tmp_path/'codex';launcher.write_text(FAKE);launcher.chmod(0o700)
    root=tmp_path/'instance'
    controller.prepare(root,objective,public,[str(launcher)] if real else ['fixture-never-launched'],
        max_tokens=100000,max_seconds=120,max_steps=12,model='fake',reasoning_effort='high',
        search_policy=search_policy,correction_policy=correction_policy,handoff_authority_version=marker)
    return root


def a_source(root, *, action='continue_w'):
    finish(root,1,'H',[],action='analyze',text='Original H scope and comparator C constraint')
    c.build_job(root,2,'A',[1],instruction='Exact scientific question')
    job=c.read(root/'jobs/002.json');record=c.host_record(c.workspace(root,2))
    payload=dict(summary='Global contribution and gap',scientific_result='A scientific direction, not an implementation mandate',
        limitations=['Original H constraints remain'],implementation_selection=None,search_review=None,
        candidate_recommendation=None,progress_assessment=None,next_action=action,route_reason=RECIPE)
    c.write(record/'native-intent.json',dict(task_sha256=c.digest(root/'jobs/002.json')))
    c.write(record/'science-output.json',payload);c.write(record/'usage.json',dict(input_tokens=7,cached_input_tokens=2,output_tokens=3))
    c.write(record/'native-outcome.json',dict(returncode=0,stop_reason=None,usage=native.usage(root),raw_sha256=c.digest(record/'science-output.json')))
    return job,c.seal_result(root,2)


def test_real_codex_transport_uses_frozen_role_and_source_tagged_a_direction(tmp_path):
    root=prepare(tmp_path,real=True)
    result=controller.run(root)
    assert result['status']=='finish' and result['completed_steps']==4,result
    job=c.read(root/'jobs/003.json');view=c.read(c.workspace(root,3)/'science-task.json')
    assert job['instruction']==RECIPE and view['question']!=RECIPE
    assert view['decision_context']['original_instruction']==RECIPE
    assert view['decision_context']['source_role']=='A' and view['decision_context']['source_action']=='continue_w'
    saved={path:path.read_bytes() for path in (root/'jobs').glob('*.json')}
    assert controller.run(root)['status']=='finish'
    assert all(path.read_bytes()==original for path,original in saved.items())
    assert sum(len(text.encode()) for text in guidance.DEFAULT.values())+200<=2048


@pytest.mark.parametrize('same_instruction',[True,False])
def test_a_revise_h_is_macro_context_but_different_host_instruction_is_not_a_proposal(tmp_path,same_instruction):
    root=prepare(tmp_path);a_source(root,action='revise_h')
    instruction=RECIPE if same_instruction else 'Exact host constraint: comparator C is mandatory'
    job=c.build_job(root,3,'H',[1,2],instruction=instruction)
    view=c.science_view(job,root)
    if same_instruction:
        assert view['question']!=RECIPE and view['decision_context']['original_instruction']==RECIPE
    else:
        # Same immediate A predecessor; only the original-text equality guard distinguishes this case.
        assert 'decision_context' not in job and view['question']==instruction


def test_e_question_and_return_keep_exact_requester_instruction(tmp_path):
    root=prepare(tmp_path);job,result=a_source(root,action='extract')
    role,parents,instruction,target,h,w=controller._route(root,2,'A',result,job,1,None)
    c.build_job(root,3,role,parents,instruction=instruction,evidence_return=target)
    finish(root,3,'E',parents)
    e=c.read(root/'jobs/003.json');ev=c.science_view(e,root)
    assert ev['question']==RECIPE and 'decision_context' not in ev
    returned=controller._route(root,3,'E',c.validate(c.workspace(root,3)),e,h,w)
    a=c.build_job(root,4,returned[0],returned[1],instruction=returned[2])
    av=c.science_view(a,root)
    assert av['question']==RECIPE and 'decision_context' not in av
    assert 'inputs/parents/003/conclusion.json' in [row['path'] for row in a['direct_refs']]


def test_old_marker_absent_prepared_job_is_byte_stable(tmp_path,monkeypatch):
    root=prepare(tmp_path,marker=None);a_source(root)
    job=c.build_job(root,3,'W',[1,2],instruction=RECIPE)
    assert 'handoff_authority_version' not in job and 'native_role_instruction' not in job
    paths=[root/'jobs/003.json',c.workspace(root,3)/'science-task.json',c.host_record(c.workspace(root,3))/'science-result.schema.json']
    original={path:path.read_bytes() for path in paths}
    monkeypatch.setitem(guidance.DEFAULT,'W','Changed advice for future settings')
    assert c.build_job(root,3,'W',[1,2],instruction=RECIPE)==job
    assert c.science_view(job,root)['question']==RECIPE
    assert all(path.read_bytes()==data for path,data in original.items())


def test_n4_revise_h_request_is_bound_before_context_and_seals(tmp_path):
    from scidiscovery.research_loop import search
    root=prepare(tmp_path,search_policy=search.DEFAULT_POLICY,correction_policy=dict(review_after=1,pause_after=1))
    plan=dict(scope='Original mechanism scope',commitments=[dict(label='M',minimal_test='Comparator C',existing_ref=None)],focus=dict(label='M',action='screen'))
    finish(root,1,'H',[],action='experiment',search_choice=plan)
    c.build_job(root,2,'W',[1],instruction='Exact scientific question');finish(root,2,'W',[1])
    finish(root,3,'A',[1,2],action='revise_h',progress={'verdict':'no_progress'})
    job=c.read(root/'jobs/003.json');result=c.validate(c.workspace(root,3))
    correction.publish(root,3)
    route=correction.effective_route(root,3,result,job,controller._route(root,3,'A',result,job,1,2))
    h=c.build_job(root,4,route[0],route[1],instruction=route[2],correction_request=route[6])
    assert h['correction_request'] is not None and 'decision_context' not in h
    assert c.science_view(h,root)['question']==route[2]
    finish(root,4,'H',route[1],action='wait')
    assert c.validate(c.workspace(root,4))['next_action']=='wait'
