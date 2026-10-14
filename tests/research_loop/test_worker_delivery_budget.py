"""A continuing shallow task retains incomplete work at its original hard cap."""
import sys

from scidiscovery.research_loop import (contracts as c, controller, budget, native,
    continuation, checkpoint, execution, runtime, search, experiments)
from execution_fixtures import execution_registry
from test_breadth_science import h, worker, run, findings
from test_worker_delivery import output, stopped_native, tree


def test_incomplete_continue_at_original_hard_cap_seals_partial_without_wait_loop(tmp_path,execution_registry,monkeypatch):
    public=tmp_path/'public';public.mkdir()
    objective=public/'goal.md';objective.write_text('Compare the original mechanisms within finite investment.')
    root=tmp_path/'instance'
    controller.prepare(root,objective,public,[sys.executable],model='no-model',reasoning_effort='high',
        max_tokens=100000,max_seconds=600,max_steps=16,search_policy=search.DEFAULT_POLICY,node_budget_mode='hard',
        node_budget_policy={role:dict(max_observed_tokens=10 if role=='W' else 100,max_seconds=60)
                            for role in ('H','W','A','E')},
        resume_policy=dict(max_attempts=1,protocol='codex_exec_resume',usage_scope='turn',output_repair=False),
        worker_fragment_policy=dict(context='new_context'))
    c.write(root/'host-started.json',budget.clock_stamp())
    budget.transition(root,'advance','Known zero-model host start for original hard-cap probe')
    h(root,labels=('P','Q'))
    job=c.build_job(root,2,'W',[1])
    anchor=budget.accept_node(root,job)
    job,config=worker(root,tmp_path,2,[1]);record=execution.record(root,2)
    intent=c.read(record/'native-intent.json');intent['budget_slice']=anchor
    c.write(record/'native-intent.json',intent)
    run(root,config,'P')
    record,_=output(root,findings('P'),intent='continue');stopped_native(root,record)
    meter=c.read(record/'usage.json');outcome=c.read(record/'native-outcome.json')
    outcome['budget_slice']=dict(role='W',limits=budget.node_limits(root,job),usage_observed=True,
        dispatches=1,advance_seconds=0.,observed_tokens=meter['input_tokens']+meter['output_tokens'],**meter)
    c.write(record/'native-outcome.json',outcome)
    monkeypatch.setattr(runtime,'process_matches',lambda *args:False)
    def no_new_native(*args,**kwargs):
        raise AssertionError('Original budget boundary cannot start or wait for another native turn')
    monkeypatch.setattr(native,'wait_native',no_new_native)
    monkeypatch.setattr(native,'execute_native',no_new_native)
    checkpoint.capture(root,job,record)
    continuation.seal_or_repair(root,2)
    receipt=c.read(record/'result-identity.json')['control_outcome']['worker_delivery']
    assert receipt['status']=='partial' and receipt['reason']=='worker_resume_node_exhausted'
    ending=checkpoint.stage_end(root,job,record)
    assert ending['work_exit']['kind']=='budget'
    assert ending['work_exit']['consumption']['tokens']==10
    assert len(execution.records(root,2))==1 and len(experiments.Records(config).calls())==1
    before=tree(root)
    continuation.seal_or_repair(root,2)
    c.validate(c.workspace(root,2))
    assert tree(root)==before
