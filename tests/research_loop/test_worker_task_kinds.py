"""Scientific authors choose W work; the host never guesses from predecessor role."""
import pytest

from scidiscovery.research_loop import contracts as c, controller, search
from test_history_handoff import finish


def instance(tmp_path, *, enabled=True):
    public=tmp_path/'public';public.mkdir()
    objective=public/'goal.md';objective.write_text('Distinguish mechanisms before allocating deeper work.')
    root=tmp_path/'instance'
    controller.prepare(root,objective,public,['no-model'],max_tokens=100000,max_seconds=600,max_steps=12,
        model='fixture',reasoning_effort='high',search_policy=search.DEFAULT_POLICY if enabled else None)
    return root


def hypothesis(root,focus):
    return finish(root,1,'H',[],action='experiment',search_choice=dict(scope='Two scientific mechanisms',
        commitments=[dict(label=name,minimal_test='A discriminating observation with retained limitations',existing_ref=None)
                     for name in ('P','Q')],focus=focus))


@pytest.mark.parametrize('action',['improve','validate'])
def test_h_can_explicitly_request_local_work_without_repeating_breadth(tmp_path,action):
    root=instance(tmp_path)
    hypothesis(root,dict(label='P',action=action))
    job=c.build_job(root,2,'W',[1])
    assert search.launch_reason(root,job) is None
    assert job['search']['focus']==dict(mechanism_ref='h001.m1',action=action)
    assert job['search']['coverage_obligation']==[]
    assert [item['mechanism_ref'] for item in job['search']['breadth']['mechanisms']]==['h001.m1']
    # Q remains scientifically pending; selecting local work is not a Q verdict.
    assert search.project(root,2)['mechanisms']['h001.m2']['status']=='pending'
    finish(root,2,'W',[1],mechanism_findings=None)
    assert c.validate(c.workspace(root,2))['role']=='W'


def test_a_can_explicitly_return_to_combination_screening(tmp_path):
    root=instance(tmp_path)
    hypothesis(root,dict(label='P',action='improve'))
    finish(root,2,'W',[1],mechanism_findings=None)
    finish(root,3,'A',[1,2],action='continue_w',search_choice=dict(dispositions=[],
        next_focus=dict(mechanism_ref=None,action='screen')))
    job=c.build_job(root,4,'W',[1,2,3])
    assert search.launch_reason(root,job) is None
    assert job['search']['focus']['action']=='screen'
    assert {row['mechanism_ref'] for row in job['search']['coverage_obligation']}=={'h001.m1','h001.m2'}
    assert len(job['search']['breadth']['mechanisms'])==2


def test_missing_author_task_choice_is_not_invented_as_screen(tmp_path):
    root=instance(tmp_path)
    hypothesis(root,None)
    job=c.build_job(root,2,'W',[1])
    assert search.launch_reason(root,job)=='science_task_action_required'
    assert job['search']['focus'] is None
    seal=c.read(c.host_record(c.workspace(root,1))/'result-identity.json')
    assert seal['control_outcome']['search_status']=='unresolved'


@pytest.mark.parametrize('action',['improve','repair','validate'])
def test_null_mechanism_does_not_authorize_ambiguous_local_task(tmp_path,action):
    root=instance(tmp_path)
    hypothesis(root,dict(label=None,action=action))
    job=c.build_job(root,2,'W',[1])
    assert search.launch_reason(root,job) is not None
    assert job['search']['focus'] is None


def test_nonsearch_worker_has_no_combination_obligation(tmp_path):
    root=instance(tmp_path,enabled=False)
    finish(root,1,'W',[],mechanism_findings=None)
    assert c.validate(c.workspace(root,1))['role']=='W'
