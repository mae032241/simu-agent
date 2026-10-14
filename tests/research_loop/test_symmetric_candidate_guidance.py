"""New frozen guidance is delivered without changing execution or legacy tasks."""
import copy

import pytest

from scidiscovery.research_loop import contracts as c, controller, guidance, selection
from test_history_handoff import finish
from execution_fixtures import execution_registry
from test_breadth_science import prepare as managed_prepare, h, worker, run, a, findings

DOMAIN_SUFFIX=' Use exp run --mechanism LABEL [--script FILE]; exp lineage-status.'


def prepare(tmp_path,advice,*,portfolio=False):
    public=tmp_path/'public';public.mkdir()
    objective=public/'goal.md';objective.write_text('Compare candidate gains, losses and unknowns under the same original goal.')
    root=tmp_path/'instance'
    from scidiscovery.research_loop import search
    controller.prepare(root,objective,public,['never-call-a-model'],model='no-model',reasoning_effort='high',
        max_tokens=100000,max_seconds=600,max_steps=12,role_guidance=advice,search_policy=search.DEFAULT_POLICY,
        portfolio_policy=dict(review_after_cycles=3) if portfolio else None)
    finish(root,1,'H',[],action='experiment',search_choice=dict(scope='One named mechanism',
        commitments=[dict(label='P',minimal_test='A discriminating scientific question remains unresolved',existing_ref=None)],
        focus=dict(label=None,action='screen')))
    return root


def assigned_views(root):
    job=c.build_job(root,2,'W',[1]);worker_view=c.read(c.workspace(root,2)/'science-task.json')
    finish(root,2,'W',[1],mechanism_findings=[dict(mechanism='P',basis='blocked',
        finding='This guidance fixture has no domain observation and does not assert scientific screening.')])
    judge=c.build_job(root,3,'A',[1,2]);judge_view=c.read(c.workspace(root,3)/'science-task.json')
    return job,worker_view,judge,judge_view


@pytest.mark.parametrize('kind',['default','opportunity','default_domain','opportunity_domain'])
def test_actual_prepared_worker_and_a_views_deliver_symmetric_choice_and_adaptive_task_roles(tmp_path,kind):
    opportunity=kind.startswith('opportunity')
    supplied=guidance.DEFAULT
    if kind.endswith('_domain'):
        supplied=dict(guidance.OPPORTUNITY if opportunity else guidance.DEFAULT)
        supplied['W']+=DOMAIN_SUFFIX
    root=prepare(tmp_path,supplied,portfolio=opportunity)
    _,worker_view,_,judge_view=assigned_views(root)
    expected=guidance.OPPORTUNITY if opportunity and supplied is guidance.DEFAULT else supplied
    assert c.settings(root)['role_guidance']==expected
    assert sum(len(text.encode()) for text in expected.values())<=guidance.MAX_BYTES==2560
    text=worker_view['role_guidance']
    assert text==expected['W']
    assert 'improve allows observation-driven candidate adjustment and continued local search' in text
    assert 'validate supplies evidence for a concrete choice with fair controls' in text
    assert 'Neither defaults to one candidate or full validation after each candidate' in text
    assert 'breadth fairness, not local trial totals' in text
    assert 'original runtime/feedback limits apply' in text
    assert 'Query unknown calls without replay' in text
    assert 'Honor required checks' in text and 'No auxiliary agents' in text
    judge_text=judge_view['role_guidance']
    assert judge_text==expected['A']
    assert 'Compare retaining and replacing candidates by the same original-goal criteria: gains, losses and unknowns' in judge_text
    assert 'existing candidate has no default priority' in judge_text
    assert 'unknown target optimality alone cannot block replacement' in judge_text
    assert 'proxy leads do not mandate choice' in judge_text
    assert 'Missing/unbound audit remains unknown' in judge_text
    assert 'confirmed delivery remain distinct' in judge_text
    assert worker_view['lineage']['mechanisms']['task_action']=='screen'


@pytest.mark.parametrize('custom',[False,True])
def test_no_guidance_fallback_and_custom_frozen_text_preserve_their_actual_assignment(tmp_path,custom):
    advice={role:'Custom scientific instruction for '+role for role in 'HWAE'} if custom else None
    root=prepare(tmp_path,advice)
    w,w_view,judge,a_view=assigned_views(root)
    for role,job,view in [('W',w,w_view),('A',judge,a_view)]:
        if custom:
            assert view['role_guidance']==advice[role]
            assert job['native_role_instruction']==advice[role]
            assert 'role_instruction' not in view
        else:
            assert 'role_guidance' not in view
            assert view['role_instruction']==guidance.OPPORTUNITY[role]
            assert job['native_role_instruction']==guidance.OPPORTUNITY[role]


def test_previously_frozen_native_literal_is_not_rewritten_by_new_defaults(tmp_path,monkeypatch):
    root=prepare(tmp_path,None)
    monkeypatch.setitem(guidance.OPPORTUNITY,'W','Previously frozen Worker scientific instruction.')
    job=c.build_job(root,2,'W',[1])
    finish(root,2,'W',[1],mechanism_findings=[dict(mechanism='P',basis='blocked',finding='A fixture observation remains missing.')])
    files=[root/'settings.json',root/'jobs/002.json',c.workspace(root,2)/'science-task.json',c.host_record(c.workspace(root,2))/'result-identity.json']
    before={path:path.read_bytes() for path in files}
    monkeypatch.setitem(guidance.OPPORTUNITY,'W','New defaults cannot retroactively change an accepted assignment.')
    assert c.build_job(root,2,'W',[1])==job
    c.validate(c.workspace(root,2))
    assert before=={path:path.read_bytes() for path in files}


def test_local_improve_multiple_calls_already_share_original_scope_without_a_single_trial_gate(tmp_path,execution_registry):
    root=managed_prepare(tmp_path);h(root,labels=('P','Q'))
    _,first=worker(root,tmp_path,2,[1]);run(root,first,'P')
    finish(root,2,'W',[1],mechanism_findings=findings('P',blocked=('Q',)))
    a(root,3,[1,2],focus='h001.m1',mode='improve')
    job,local=worker(root,tmp_path,4,[1,2,3])
    assert job['search']['focus']['action']=='improve'
    assert len(local['breadth']['mechanisms'])==1 and local['breadth']['grant']['extra_calls']==1
    results=[run(root,local,'P') for _ in range(3)]
    assert all(result['status']=='known_success' and result['scope']==local['scope'] for result in results)
    assert all(result['mechanism_binding']['grant'] is None for result in results)
    assert len({result['call_id'] for result in results})==3
    assert c.read(root/'jobs/004.json')==job
    text=c.read(c.workspace(root,4)/'science-task.json')['role_guidance']
    assert 'continued local search' in text and 'original runtime/feedback limits apply' in text


@pytest.mark.parametrize('recommended',['old','new'])
def test_recommendation_does_not_require_proxy_lead_or_proven_target_optimality(recommended):
    candidates=[dict(id=cid,label=cid,evaluation_key='same-public-evaluation',metric=metric,direction='max',status='ok')
        for cid,metric in [('old',.9),('new',.8)]]
    records=[dict(step=1,role='W',recommendation=None,coverage='complete',candidates=candidates,
        current_candidate=dict(candidate_id='old'),actual_submission=None),
        dict(step=2,role='A',recommendation=recommended,coverage=None,candidates=[],current_candidate=None,actual_submission=None)]
    original=copy.deepcopy(records)
    view=selection.project(records)
    assert view['a_recommended']['candidate_id']==recommended
    assert view['target_best'] is None and records==original
    assert view['proxy_highest'][0]['candidate_ids']==['old']
