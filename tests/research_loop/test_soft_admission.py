"""Soft targets never reserve a whole next node; hard originals stay hard."""
import sys

import pytest

from scidiscovery.research_loop import budget, contracts as c, controller, native
from test_history_handoff import finish


def fixture(tmp_path, *, mode='soft', seconds=1906, tokens=6_000_000, steps=24, spent=0):
    public=tmp_path/'public';public.mkdir()
    objective=public/'objective.md';objective.write_text('Continue the scientific comparison while preserving necessary delivery resources.')
    launcher=tmp_path/'native.py'
    launcher.write_text("import json,os,pathlib,sys\na=sys.argv[1:];sys.stdin.read()\nrole=os.environ['THIN_HWA_ROLE']\nassert role in ('W','A')\np=dict(summary='W completed',scientific_result='Accepted scientific work retained',limitations=['Fake transport'],implementation_selection=None)\nif role=='A':p.update(search_review=None,candidate_recommendation=None,progress_assessment=None,next_action='wait',route_reason='A retained its conclusion')\nprint(json.dumps(dict(type='turn.completed',usage=dict(input_tokens=7,cached_input_tokens=2,output_tokens=3))),flush=True)\npathlib.Path(a[a.index('--output-last-message')+1]).write_text(json.dumps(p))\n")
    adapter=tmp_path/'never-called.py';adapter.write_text('raise AssertionError("No delivery was requested in this fixture")\n')
    delivery=dict(closeout_a=dict(max_observed_tokens=300_000,max_seconds=300),inflight_tokens=100_000,
        cleanup_seconds=30,submit_seconds=60,confirm_seconds=60,
        adapter=dict(adapter=str(adapter),launcher_argv=[sys.executable,str(adapter)],config={},target={},inputs=[],source_roots=[str(public)]))
    root=tmp_path/'instance'
    controller.prepare(root,objective,public,[sys.executable,str(launcher)],max_tokens=tokens,max_seconds=seconds,max_steps=steps,
        model='fixture',reasoning_effort='high',search_policy=None,node_budget_mode='hard' if mode=='missing' else mode,
        node_budget_policy={role:dict(max_observed_tokens=2_000_000,max_seconds=900) for role in 'HWAE'},delivery_policy=delivery)
    if mode=='missing':
        value=c.read(root/'settings.json');value.pop('node_budget_mode')
        c.write(root/'settings.json',value);c.write(root/'settings-identity.json',dict(sha256=c.digest(root/'settings.json')))
    stamp=budget.clock_stamp()
    stamp['at_unix']-=spent;stamp['at_boottime']-=spent
    c.write(root/'host-started.json',stamp)
    original_stamp=budget.clock_stamp
    try:
        budget.clock_stamp=lambda:stamp
        budget.transition(root,'advance','fixture consumption')
    finally:
        budget.clock_stamp=original_stamp
    return root


def prefix(root):
    finish(root,1,'H',[],action='experiment')
    c.build_job(root,2,'W',[1],instruction='Exact scientific question');finish(root,2,'W',[1])
    finish(root,3,'A',[1,2],action='continue_w')
    c.build_job(root,4,'W',[1,2,3],instruction='Exact scientific question');finish(root,4,'W',[1,2,3])
    finish(root,5,'A',[1,4],action='continue_w')


def test_1906_seconds_continue_w_does_not_require_old_1950_gate(tmp_path,monkeypatch):
    root=fixture(tmp_path);prefix(root)
    assert c.validate(c.workspace(root,5))['next_action']=='continue_w'
    assert budget.snapshot(root)['seconds_remaining']==pytest.approx(1906,abs=2)
    assert budget.delivery_reserve(c.settings(root))['seconds']==450
    assert budget.exploration_admission(root,dict(step=6,role='W')) is None
    real_execute=native.execute_native
    def execute(root,step):
        assert step==6
        real_execute(root,step)
        (root/'pause.request').write_text('Operator pause after accepted W completed')
    monkeypatch.setattr(native,'execute_native',execute)
    result=controller.run(root)
    assert result['status']=='paused' and result['completed_steps']==6, result
    assert budget.closeout_state(root)['begin'] is None
    assert c.validate(c.workspace(root,6))['summary']=='W completed'
    hint=c.read(c.workspace(root,6)/'work/budget-status.json')
    assert hint['current_work_active_seconds_available']==pytest.approx(1456,abs=3)
    assert hint['metering'] in {'observed_lower_bound','inflight_unknown'}


def test_soft_token_target_and_reserve_equality_are_distinct(tmp_path,monkeypatch):
    root=fixture(tmp_path,tokens=1_500_000)
    job=c.build_job(root,1,'H',[])
    assert budget.node_admission(root,job) is None  # Target is 2M; available is 1.5M.
    original=budget.snapshot(root)
    monkeypatch.setattr(budget,'snapshot',lambda *args,**kwargs:dict(original,seconds_remaining=450))
    assert budget.node_admission(root,job)=='closeout_reserve_seconds'
    monkeypatch.setattr(budget,'snapshot',lambda *args,**kwargs:dict(original,max_tokens=400_000))
    assert budget.node_admission(root,job)=='closeout_reserve_tokens'
    monkeypatch.setattr(budget,'snapshot',lambda *args,**kwargs:dict(original,max_tokens=400_001,seconds_remaining=450.001))
    assert budget.node_admission(root,job) is None


@pytest.mark.parametrize('mode',['hard','missing'])
def test_original_hard_full_target_and_three_a_reserve_are_unchanged(tmp_path,mode):
    root=fixture(tmp_path,mode=mode);prefix(root)
    settings=(root/'settings.json').read_bytes()
    assert budget.delivery_reserve(c.settings(root))['seconds']==1050
    assert budget.node_admission(root,dict(step=6,role='W'))=='closeout_reserve_seconds'
    assert (root/'settings.json').read_bytes()==settings


def test_known_failed_resume_does_not_require_unused_soft_target(tmp_path):
    from test_soft_node_budget import scene
    from test_worker_resume import wait_runner
    root=scene(tmp_path,mode='known_failure',tokens=1000,seconds=900,total_tokens=100,total_seconds=30,resume=True,sleep=0)
    assert controller.run(root)['status']=='native_stopped'
    first=wait_runner(root)
    originals={path:path.read_bytes() for path in first.iterdir() if path.is_file()}
    assert native.usage(root)['observed_tokens']==15
    assert controller.worker_resume(root,1)['status']=='wait'
    assert native.usage(root)['observed_tokens']==30 and budget.used_steps(root)==2
    assert all(path.read_bytes()==value for path,value in originals.items())


def test_prepared_closeout_a_uses_its_existing_slot_and_only_execution_floor(tmp_path,monkeypatch):
    root=fixture(tmp_path,seconds=500,steps=3,spent=140)
    refs=dict(items=[],omitted_count=0,source_nodes=[])
    budget.begin_closeout(root,0,1,'Explicit bounded closeout',delivery_sources=refs)
    real_execute=native.execute_native
    def interrupt_before_acceptance(*args,**kwargs):
        raise RuntimeError('Fixture controller stopped after preparing A, before acceptance')
    monkeypatch.setattr(native,'execute_native',interrupt_before_acceptance)
    assert controller.run(root)['status']=='closeout_native_unsealed'
    job_path=root/'jobs/001.json';original=job_path.read_bytes()
    assert budget.used_steps(root)==1 and not (c.host_record(c.workspace(root,1))/'native-intent.json').exists()
    assert controller._closeout_funds(root,step=1)
    job=c.read(job_path)
    assert budget.node_admission(root,job) is None
    monkeypatch.setattr(native,'execute_native',real_execute)
    result=controller.run(root)
    assert result['status']=='closeout_unresolved',result
    assert job_path.read_bytes()==original and budget.used_steps(root)==1
    assert c.validate(c.workspace(root,1))['next_action']=='wait'
    hint=c.read(c.workspace(root,1)/'work/budget-status.json')
    assert hint['reserve_scope']=='external_closeout_floor' and hint['reserve_state']=='within'
    assert hint['current_work_active_seconds_available']==pytest.approx(210,abs=3)
    assert not (root/'jobs/002.json').exists()


def test_closeout_audit_has_follow_a_headroom_without_full_a_target(tmp_path,monkeypatch):
    from scidiscovery.research_loop import candidate_audit, delivery
    from test_candidate_audit import audit_fixture, _seal_existing
    original_prepare=controller.prepare
    def prepare(*args,**kwargs):
        kwargs['max_seconds']=500
        kwargs['max_tokens']=1_000_000
        kwargs['delivery_policy']=dict(kwargs['delivery_policy'],closeout_a=dict(max_observed_tokens=300000,max_seconds=300),
            inflight_tokens=100000,cleanup_seconds=30,submit_seconds=90,confirm_seconds=30)
        return original_prepare(*args,**kwargs)
    monkeypatch.setattr(controller,'prepare',prepare)
    root=audit_fixture(tmp_path)
    job,_,_=finish(root,3,'A',[1,2],action='audit',recommendation='run-1')
    ordinary=c.validate(c.workspace(root,3))
    assert candidate_audit.execute(root,job,ordinary) is None
    assert candidate_audit.public_receipt(root,candidate_audit.receipt_ref(root,3))['status']=='unavailable'
    # Ordinary audit retains a whole minimal closeout reserve (90+450 > 500).
    nodes=[dict(step=i,seal_sha256=c.digest(c.host_record(c.workspace(root,i))/'result-identity.json')) for i in (1,2,3)]
    refs=delivery.freeze_sources(root,nodes)
    budget.begin_closeout(root,3,4,'Exact closeout prefix',delivery_sources=refs)
    closeout=c.build_job(root,4,'A',[1,2,3],purpose='closeout',source_cutoff=3,delivery_sources=refs)
    payload=dict(summary='Audit before deciding',scientific_result='A retains scientific uncertainty',limitations=['Public check only'],
        implementation_selection=None,search_review=None,progress_assessment=None,candidate_recommendation='run-1',
        next_action='audit',route_reason='Assess after exact public audit')
    result=_seal_existing(root,4,payload)
    assert candidate_audit.execute(root,closeout,result) is None
    assert candidate_audit.public_receipt(root,candidate_audit.receipt_ref(root,4))['status']=='audited'
    assert not (root/'runs/submitted.json').exists() and budget.closeout_state(root)['actions']==[]
