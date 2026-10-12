"""Same-session native continuation through real detached local processes; no models."""
import json
import sys
import time
from pathlib import Path

import pytest

from scidiscovery.research_loop import budget, contracts as c, controller, execution, native
from scidiscovery.research_loop.cli import status


FAKE = r'''import json,os,pathlib,sys
args=sys.argv[1:];sys.stdin.read()
work=pathlib.Path(os.environ['THIN_HWA_WORKSPACE']);home=pathlib.Path(os.environ['THIN_HWA_NATIVE_HOME'])
role=os.environ['THIN_HWA_ROLE']
thread='11111111-2222-4333-8444-555555555555'
with (work/'work/launches').open('a') as f:f.write('resume\n' if 'resume' in args else 'exec\n')
print(json.dumps({'type':'thread.started','thread_id':thread}),flush=True)
if 'resume' not in args and role!='A':
 p=home/'sessions/rollout.jsonl';p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps({'type':'session_meta','payload':{'id':thread,'cwd':str(work)}})+'\n')
 print(json.dumps({'type':'turn.completed','usage':{'input_tokens':10,'cached_input_tokens':3,'output_tokens':4}}),flush=True)
 (work/'work/checkpoint').write_text('original checkpoint')
 sys.exit(7)
if 'resume' in args:assert thread in args and (work/'work/checkpoint').read_text()=='original checkpoint'
assert pathlib.Path(os.environ['CODEX_HOME'])==home
payload={'summary':'Continued scientific finding','scientific_result':'Original checkpoint was retained.','limitations':['Fake transport only'],'implementation_selection':None}
if role=='H':payload.update(search_plan=None,next_action='wait',route_reason='Bounded contribution complete')
if role=='A':payload.update(search_review=None,candidate_recommendation=None,progress_assessment=None,next_action='finish',route_reason='Independent fake conclusion')
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':20,'cached_input_tokens':5,'output_tokens':2}}),flush=True)
if (work/'work/fail-again').exists():sys.exit(7)
pathlib.Path(args[args.index('--output-last-message')+1]).write_text(json.dumps(payload))
'''


def instance(tmp_path, *, cap=100, attempts=2, max_tokens=1000, steps=6, search_policy=None, delivery_policy=None):
    public=tmp_path/'public';public.mkdir()
    objective=public/'objective.md';objective.write_text('Continue a bounded scientific task using its checkpoint.')
    launcher=tmp_path/'native.py';launcher.write_text(FAKE)
    root=tmp_path/'instance'
    controller.prepare(root,objective,public,[sys.executable,str(launcher)],max_tokens=max_tokens,
        max_seconds=120,max_steps=steps,model='no-model',reasoning_effort='high', node_budget_mode='hard',search_policy=search_policy,delivery_policy=delivery_policy,
        node_budget_policy={role:dict(max_observed_tokens=cap,max_seconds=20) for role in 'HWAE'},
        resume_policy=dict(max_attempts=attempts,protocol='codex_exec_resume',usage_scope='turn'))
    return root


def wait_runner(root, step=1):
    # Terminal outcome precedes runner exit by a bounded transport gap.
    from scidiscovery.research_loop import runtime
    end=time.monotonic()+3
    record=execution.record(root,step)
    while runtime.process_matches(c.read(record/'runner-process.json'),execution.identity(root,step)):
        assert time.monotonic()<end
        time.sleep(.02)
    return record


def fail(root, step=1):
    assert controller.run(root)['status']=='native_stopped'
    return wait_runner(root, step)


def test_known_failure_same_thread_success_keeps_originals_and_cumulative_budget(tmp_path):
    root=instance(tmp_path);first=fail(root)
    preserved={p:p.read_bytes() for p in first.iterdir() if p.is_file()}
    assert controller.worker_resume(root,1)['status']=='wait'
    assert all(p.read_bytes()==data for p,data in preserved.items())
    assert execution.raw(root,1)==first/'continuations/001/science-output.json'
    assert c.validate(c.workspace(root,1))['summary']=='Continued scientific finding'
    assert native.usage(root)['observed_tokens']==36
    assert budget.used_steps(root)==2
    node=status(root)['nodes'][0]
    assert node['continuations']==1 and node['budget_report']['observed_tokens']==36
    assert node['budget_report']['dispatches']==2
    assert c.read(first/'result-identity.json')['execution_ref']==execution.reference(root,1)
    c.build_job(root,2,'H',[1])
    from scidiscovery.research_loop import history
    assert history.direct_sources(root,c.read(root/'jobs/002.json'))[0][1]['summary']=='Continued scientific finding'
    assert controller.run(root)['status']=='wait'
    assert controller.worker_resume(root,1)['status']=='wait'
    assert (c.workspace(root,1)/'work/launches').read_text()=='exec\nresume\n'


@pytest.mark.parametrize('mutation', ['root_intent', 'process_receipt', 'session_header', 'launcher', 'schema', 'task'])
def test_original_binding_tamper_never_creates_continuation(tmp_path, mutation):
    root=instance(tmp_path);first=fail(root)
    if mutation=='root_intent':
        value=c.read(first/'native-intent.json');value['task_sha256']='0'*64
        c.write(first/'native-intent.json',value)
    elif mutation=='process_receipt':
        value=c.read(first/'native-process.json');value['start_ticks']+=1
        c.write(first/'native-process.json',value)
    elif mutation=='session_header':
        p=next((root/'native-homes/001/sessions').glob('*.jsonl'))
        value=json.loads(p.read_text());value['payload']['cwd']='/incorrect-workspace';p.write_text(json.dumps(value)+'\n')
    elif mutation=='task':
        work=c.workspace(root,1);value=c.read(work/'science-task.json');value['goal_text']='Injected objective';c.write(work/'science-task.json',value)
    elif mutation=='schema':
        c.write(first/'science-result.schema.json',dict(type='object',properties={},required=[],additionalProperties=False))
    else:
        launcher=Path(c.settings(root)['native_launcher_argv'][1]);launcher.write_text(launcher.read_text()+'\n# changed\n')
    with pytest.raises(ValueError):controller.worker_resume(root,1)
    assert not (first/'continuations/001/native-intent.json').exists()
    assert (c.workspace(root,1)/'work/launches').read_text()=='exec\n'


def test_missing_meter_is_unknown_not_billing_delay(tmp_path):
    root=instance(tmp_path);first=fail(root)
    (first/'usage.json').unlink()
    with pytest.raises((ValueError,OSError)):controller.worker_resume(root,1)
    assert not (first/'continuations/001/native-intent.json').exists()
    assert native.usage(root)['unknown_steps']==[1]


def test_shared_amendment_does_not_expand_original_node_cap(tmp_path):
    root=instance(tmp_path,cap=30);first=fail(root)
    before={p:p.read_bytes() for p in first.iterdir() if p.is_file()}
    budget.amend(root,max_tokens=5000,max_seconds=500,authorization_note='Explicit shared ceiling only')
    # Original 14 + continuation 22 exceeds the original 30-token node cap.
    with pytest.raises(ValueError):controller.worker_resume(root,1)
    outcome=c.read(first/'continuations/001/native-outcome.json')
    assert outcome['stop_reason']=='node_slice_token_limit'
    assert outcome['budget_slice']['observed_tokens']==36
    assert outcome['budget_slice']['limits']['max_observed_tokens']==30
    assert all(p.read_bytes()==raw for p,raw in before.items())
    assert controller.worker_resume(root,1)['reason']=='worker_resume_terminal_ineligible'
    assert not (first/'result-identity.json').exists()


def test_resume_budget_denial_restores_inactive_clock_and_keeps_attempt_unaccepted(tmp_path):
    root=instance(tmp_path);first=fail(root)
    budget.amend(root,max_tokens=99,authorization_note='Reduced explicit shared budget')
    result=controller.worker_resume(root,1)
    assert result['reason']=='worker_resume_budget_unavailable'
    assert budget.snapshot(root)['clock_phase']=='paused'
    assert not (first/'continuations/001/native-intent.json').exists()
    budget.amend(root,max_tokens=200,authorization_note='Explicit capacity restoration')
    assert controller.worker_resume(root,1)['status']=='wait'
    assert native.usage(root)['observed_tokens']==36


def test_operator_pause_does_not_accept_a_new_continuation(tmp_path):
    root=instance(tmp_path);first=fail(root)
    c.write(root/'pause.request',dict(reason='user pause'))
    assert controller.worker_resume(root,1)['reason']=='worker_resume_paused_or_closeout'
    assert not (first/'continuations/001/native-intent.json').exists()


def test_unaccepted_intent_is_not_replayed_or_given_another_attempt(tmp_path):
    root=instance(tmp_path);first=fail(root)
    from scidiscovery.research_loop import continuation
    job=c.read(root/'jobs/001.json')
    budget.transition(root,'advance','accepted fixture before runner')
    anchor=budget.accept_continuation(root,job,[first])
    record=first/'continuations/001';record.mkdir(parents=True)
    c.write(record/'native-intent.json',dict(step=1,attempt=1,task_sha256=c.digest(root/'jobs/001.json'),
        root_intent_sha256=c.digest(first/'native-intent.json'),previous=execution.proof(first),
        session=continuation.session(root,1,first),budget_slice=anchor))
    with pytest.raises(RuntimeError,match='unknown'):controller.worker_resume(root,1)
    assert not (first/'continuations/002').exists()
    assert (c.workspace(root,1)/'work/launches').read_text()=='exec\n'


def test_real_w_continuation_seals_a_and_reuses_successful_science(tmp_path):
    from test_history_handoff import finish
    from scidiscovery.research_loop import history, search
    root=instance(tmp_path,search_policy=dict(max_w_seconds=10,max_w_observed_tokens=80,max_requested_repairs=2))
    plan=dict(scope='A discriminating mechanism',commitments=[dict(label='M',minimal_test='Bounded screen',existing_ref=None)],focus=dict(label='M',action='screen'))
    finish(root,1,'H',[],action='experiment',search_choice=plan)
    first=fail(root,2)
    saved={p:p.read_bytes() for p in first.iterdir() if p.is_file()}
    result=controller.worker_resume(root,2)
    assert result['status']=='finish' and result['completed_steps']==3
    assert all(p.read_bytes()==value for p,value in saved.items())
    node=status(root)['nodes'][1]
    assert node['budget_report']['limits']==dict(max_seconds=10,max_observed_tokens=80)
    assert node['budget_report']['observed_tokens']==36
    view=search.project(root,4)
    assert view['accepted_slices'][0]['meter']['observed_tokens']==36
    assert view['accepted_slices'][0]['meter']['dispatches']==2
    assert c.validate(c.workspace(root,3))['role']=='A'
    sources=history.direct_sources(root,c.read(root/'jobs/003.json'))
    assert next(payload for job,payload,_ in sources if job['role']=='W')['scientific_result']=='Original checkpoint was retained.'
    assert budget.used_steps(root)==4 and native.usage(root)['observed_tokens']==68


def test_continuation_consumes_execution_slot_and_blocks_fresh_successor(tmp_path):
    from test_history_handoff import finish
    root=instance(tmp_path,steps=3)
    finish(root,1,'H',[],action='experiment')
    fail(root,2)
    result=controller.worker_resume(root,2)
    assert result['status']=='step_limit'
    assert (execution.origin(root,2)/'result-identity.json').exists()
    assert not (root/'jobs/003.json').exists()
    assert budget.used_steps(root)==3


def test_delivery_reserve_is_not_spent_on_continuation(tmp_path):
    policy=dict(closeout_a=dict(max_observed_tokens=10,max_seconds=1),inflight_tokens=0,cleanup_seconds=0,
                submit_seconds=0,confirm_seconds=0,adapter=None)
    root=instance(tmp_path,steps=4,delivery_policy=policy)
    first=fail(root)
    assert controller.worker_resume(root,1)['reason']=='worker_resume_budget_unavailable'
    assert budget.used_steps(root)==1 and not (first/'continuations/001').exists()


def test_two_explicit_continuations_never_auto_loop_or_refund_attempts(tmp_path):
    root=instance(tmp_path);first=fail(root)
    (c.workspace(root,1)/'work/fail-again').touch()
    for attempt in (1,2):
        with pytest.raises(ValueError):controller.worker_resume(root,1)
        wait_runner(root)
        assert len(execution.records(root,1))-1==attempt
        assert controller.run(root)['status']=='native_outcome_unsealed'
    assert controller.worker_resume(root,1)['reason']=='worker_resume_limit'
    assert native.usage(root)['observed_tokens']==58 and budget.used_steps(root)==3
    assert not (first/'continuations/003').exists()
    assert (c.workspace(root,1)/'work/launches').read_text()=='exec\nresume\nresume\n'


@pytest.mark.parametrize('value',[0,-1,True,float('nan')])
def test_stored_previous_token_anchor_cannot_refund_exact_prior_meter(tmp_path,value):
    root=instance(tmp_path);first=fail(root)
    from scidiscovery.research_loop import continuation
    job=c.read(root/'jobs/001.json');budget.transition(root,'advance','accepted negative fixture')
    anchor=budget.accept_continuation(root,job,[first]);anchor['previous_tokens']=value
    record=first/'continuations/001';record.mkdir(parents=True)
    intent=dict(step=1,attempt=1,task_sha256=c.digest(root/'jobs/001.json'),
        root_intent_sha256=c.digest(first/'native-intent.json'),previous=execution.proof(first),
        session=continuation.session(root,1,first),budget_slice=anchor)
    # A malicious raw receipt can contain NaN even though the host writer rejects it.
    (record/'native-intent.json').write_text(json.dumps(intent))
    with pytest.raises(ValueError):budget.stop_node(root,job,intent,budget.snapshot(root),dict(input_tokens=0,output_tokens=0))
    assert not (record/'native-process.json').exists()


def test_missing_required_original_report_prevents_qualification(tmp_path):
    root=instance(tmp_path);first=fail(root)
    outcome=c.read(first/'native-outcome.json');del outcome['budget_slice']['input_tokens'];c.write(first/'native-outcome.json',outcome)
    with pytest.raises(ValueError):controller.worker_resume(root,1)
    assert not (first/'continuations/001').exists()


@pytest.mark.parametrize('tamper', ['intent', 'report'])
def test_success_before_seal_does_not_rebind_drifted_attempt(tmp_path,monkeypatch,tamper):
    root=instance(tmp_path);first=fail(root)
    seal=c.seal_result
    def defer(*args):raise ValueError('Fixture leaves successful terminal before seal')
    monkeypatch.setattr(c,'seal_result',defer)
    monkeypatch.setattr(native,'seal_result',defer)
    with pytest.raises(ValueError,match='Fixture leaves'):controller.worker_resume(root,1)
    wait_runner(root)
    monkeypatch.setattr(c,'seal_result',seal)
    monkeypatch.setattr(native,'seal_result',seal)
    current=execution.record(root,1)
    if tamper=='intent':
        value=c.read(current/'native-intent.json');value['budget_slice']['previous_tokens']-=1
        c.write(current/'native-intent.json',value)
    else:
        value=c.read(current/'native-outcome.json');value['budget_slice']['observed_tokens']-=1
        c.write(current/'native-outcome.json',value)
    with pytest.raises(ValueError):c.seal_result(root,1)
    with pytest.raises(ValueError):controller.run(root)
    assert not (first/'result-identity.json').exists()
    assert not (first/'continuations/002').exists()
    assert (c.workspace(root,1)/'work/launches').read_text()=='exec\nresume\n'


@pytest.mark.parametrize('tamper',['schema','task'])
def test_accepted_continuation_rechecks_task_and_schema_before_actual_popen(tmp_path,monkeypatch,tamper):
    root=instance(tmp_path);first=fail(root)
    from scidiscovery.research_loop import runtime
    start=runtime.start
    def drift(root,step,attempt=0):
        if tamper=='schema':
            c.write(first/'science-result.schema.json',dict(type='object'))
        else:
            work=c.workspace(root,step);value=c.read(work/'science-task.json');value['goal_text']='Late injection';c.write(work/'science-task.json',value)
        return start(root,step,attempt)
    monkeypatch.setattr(runtime,'start',drift)
    with pytest.raises(ValueError):controller.worker_resume(root,1)
    current=first/'continuations/001'
    assert (current/'native-outcome.json').exists() and not (current/'native-process.json').exists()
    assert not (first/'result-identity.json').exists()
    assert len(execution.records(root,1))==2
    assert (c.workspace(root,1)/'work/launches').read_text()=='exec\n'
