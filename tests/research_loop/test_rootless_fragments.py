"""Actual launcher boundaries; no model, real or synthetic model service."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from scidiscovery.research_loop import budget,checkpoint,contracts as c,continuation,controller,execution,native,runtime


@pytest.fixture
def launcher():
    repo=Path(__file__).resolve().parents[2]
    spec=importlib.util.spec_from_file_location('actual_rootless_fragment_launcher',repo/'scripts/acceptance/rootless_cov_launcher.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def policies():
    return dict(node_budget_policy={role:dict(max_observed_tokens=10000,max_seconds=60) for role in 'HWAE'},
        resume_policy=dict(max_attempts=2,protocol='codex_exec_resume',usage_scope='turn',output_repair=False),
        worker_fragment_policy=dict(context='new_context'))


@pytest.fixture
def accepted(tmp_path,monkeypatch,request):
    public=tmp_path/'public';public.mkdir();goal=public/'goal';goal.write_text('Bounded native transport fixture; no model.')
    root=tmp_path/'instance'
    controller.prepare(root,goal,public,[sys.executable],max_tokens=100000,max_seconds=120,max_steps=8,
        model='no-model',reasoning_effort='high',search_policy=None,**dict(policies(),
            worker_fragment_policy=dict(context='same_session' if getattr(request,'param',None) else 'new_context'),
            resume_policy=dict(policies()['resume_policy'],output_repair=getattr(request,'param',None)=='repair')))
    job=c.build_job(root,1,'W',[]);record=execution.record(root,1)
    c.write(record/'native-intent.json',dict(task_sha256=c.digest(root/'jobs/001.json'),budget_slice=budget.accept_node(root,job)))
    binding=execution.identity(root,1)
    c.write(record/'runner-process.json',runtime.process_identity(os.getppid(),binding))
    c.write(record/'native-process.json',runtime.process_identity(os.getpid(),binding))
    home=execution.home(root,1);home.mkdir(parents=True)
    monkeypatch.setenv('THIN_HWA_JOB_MANIFEST',str(root/'jobs/001.json'))
    monkeypatch.setenv('THIN_HWA_ROLE','W');monkeypatch.setenv('THIN_HWA_NATIVE_HOME',str(home))
    return root,job,record


def command(record):
    return ['exec','--json','--output-last-message',str(record/'result.pending.json'),'--model','no-model',
        '-c','model_reasoning_effort="high"','--sandbox','workspace-write','-C',str(c.workspace(record.parents[1],1)),'-']


def arguments(root,record):
    args=command(record)
    args[args.index('-C')+1]=str(c.workspace(root,1))
    return args


def spec(root):return dict(scene_root=str(root),model='no-model',reasoning_effort='high')


def next_context(root,job,first,monkeypatch):
    payload=dict(summary='Original contribution',scientific_result='The target remains unresolved.',limitations=['No model.'],
        implementation_selection=None,mechanism_findings=None,stage_intent='continue')
    c.write(first/'science-output.json',payload)
    meter=dict(input_tokens=10,cached_input_tokens=0,output_tokens=0);c.write(first/'usage.json',meter)
    intent=c.read(first/'native-intent.json')
    c.write(first/'native-outcome.json',dict(returncode=0,stop_reason=None,cleanup='observed_group_cleaned',
        raw_sha256=c.digest(first/'science-output.json'),usage=native.usage(root),
        budget_slice=dict(budget.node_report(root,job,intent,meter),usage_observed=True)))
    checkpoint.capture(root,job,first)
    record=first/'continuations/001'
    home=root/'native-homes/001/context-001';home.mkdir(parents=True)
    c.write(record/'native-intent.json',dict(step=1,attempt=1,continuation_kind='fragment',context_mode='new_context',
        native_home=str(home),task_sha256=c.digest(root/'jobs/001.json'),previous=execution.proof(first),
        root_intent_sha256=c.digest(first/'native-intent.json'),budget_slice=budget.accept_continuation(root,job,[first]),
        fragment_checkpoint=dict(path=(first/'checkpoint.json').relative_to(root).as_posix(),sha256=c.digest(first/'checkpoint.json'))))
    binding=execution.identity(root,1,1)
    c.write(record/'runner-process.json',runtime.process_identity(os.getppid(),binding))
    c.write(record/'native-process.json',runtime.process_identity(os.getpid(),binding))
    monkeypatch.setenv('THIN_HWA_NATIVE_HOME',str(home))
    return record


def test_exact_new_context_uses_frozen_origin_schema(launcher,accepted,monkeypatch):
    root,job,first=accepted;record=next_context(root,job,first,monkeypatch)
    result=launcher.native_args(spec(root),c.workspace(root,1),arguments(root,record))
    assert result[result.index('--output-last-message')+1]==str(record/'result.pending.json')
    assert result[result.index('--output-schema')+1]==str(first/'science-result.schema.json')
    assert '--sandbox' not in result


@pytest.mark.parametrize('damage',['old_attempt','wrong_name','arbitrary_subdir','wrong_home','wrong_role','wrong_manifest','unknown_other_pid','terminal'])
def test_nonoriginal_dispatch_rejected_before_launcher_writes(launcher,accepted,monkeypatch,damage):
    root,job,first=accepted;record=next_context(root,job,first,monkeypatch);args=arguments(root,record)
    output=args.index('--output-last-message')+1
    if damage=='old_attempt':args[output]=str(first/'result.pending.json')
    elif damage=='wrong_name':args[output]=str(record/'native-intent.json')
    elif damage=='arbitrary_subdir':args[output]=str(first/'other/result.pending.json')
    elif damage=='wrong_home':monkeypatch.setenv('THIN_HWA_NATIVE_HOME',str(root/'native-homes/001'))
    elif damage=='wrong_role':monkeypatch.setenv('THIN_HWA_ROLE','A')
    elif damage=='wrong_manifest':monkeypatch.setenv('THIN_HWA_JOB_MANIFEST',str(root/'jobs/002.json'))
    elif damage=='unknown_other_pid':
        value=c.read(record/'native-process.json');value['pid']=os.getppid();c.write(record/'native-process.json',value)
    else:c.write(record/'native-outcome.json',dict(returncode=1))
    before={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
    with pytest.raises(ValueError):launcher.native_args(spec(root),c.workspace(root,1),args)
    assert {str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}==before


THREAD='11111111-1111-4111-8111-111111111111'


def next_session(root,job,first,monkeypatch,*,repair=False):
    home=execution.home(root,1);session=home/'sessions/current.jsonl';session.parent.mkdir(parents=True)
    session.write_text(json.dumps(dict(type='session_meta',payload=dict(id=THREAD,cwd=str(c.workspace(root,1)))))+'\n')
    (first/'native.jsonl').write_text(json.dumps(dict(type='thread.started',thread_id=THREAD))+'\n')
    payload=dict(summary='Existing work',scientific_result='Unresolved target',limitations=['No model.'],
        implementation_selection=None,mechanism_findings=None,stage_intent='continue')
    if repair:payload.pop('scientific_result')
    c.write(first/'science-output.json',payload)
    meter=dict(input_tokens=10,cached_input_tokens=0,output_tokens=0);c.write(first/'usage.json',meter)
    original=c.read(first/'native-intent.json')
    c.write(first/'native-outcome.json',dict(returncode=0,stop_reason=None,cleanup='observed_group_cleaned',
        thread_id=THREAD,raw_sha256=c.digest(first/'science-output.json'),usage=native.usage(root),
        budget_slice=dict(budget.node_report(root,job,original,meter),usage_observed=True)))
    if not repair:checkpoint.capture(root,job,first)
    reference=continuation.session(root,1,first)
    record=first/'continuations/001'
    value=dict(step=1,attempt=1,continuation_kind='repair' if repair else 'fragment',context_mode='same_session',
        task_sha256=c.digest(root/'jobs/001.json'),previous=execution.proof(first),session=reference,
        root_intent_sha256=c.digest(first/'native-intent.json'),budget_slice=budget.accept_continuation(root,job,[first]))
    if repair:value['output_repair']=continuation.output_request(root,1,first,source_attempt=0)
    else:value['fragment_checkpoint']=dict(path=(first/'checkpoint.json').relative_to(root).as_posix(),sha256=c.digest(first/'checkpoint.json'))
    c.write(record/'native-intent.json',value)
    binding=execution.identity(root,1,1)
    c.write(record/'runner-process.json',runtime.process_identity(os.getppid(),binding))
    c.write(record/'native-process.json',runtime.process_identity(os.getpid(),binding))
    monkeypatch.setenv('THIN_HWA_NATIVE_HOME',str(home))
    return record


def resume_arguments(root,record):
    return ['exec','-C',str(c.workspace(root,1)),'--sandbox','workspace-write',
        '-c','model_reasoning_effort="high"','resume','--json','--model','no-model',
        '--output-schema',str(execution.origin(root,1)/'science-result.schema.json'),
        '--output-last-message',str(record/'result.pending.json'),THREAD,'-']


@pytest.mark.parametrize('accepted',['fragment','repair'],indirect=True)
def test_exact_accepted_same_session_command(launcher,accepted,monkeypatch,request):
    root,job,first=accepted
    record=next_session(root,job,first,monkeypatch,repair=request.node.callspec.params['accepted']=='repair')
    result=launcher.native_args(spec(root),c.workspace(root,1),resume_arguments(root,record))
    assert result.count('resume')==1 and result[-2:]==[THREAD,'-']
    assert result.count('--output-schema')==1 and '--sandbox' not in result
    assert result[result.index('--output-last-message')+1]==str(record/'result.pending.json')
    assert execution.home(root,1,1)==execution.home(root,1,0)


@pytest.mark.parametrize('accepted',['fragment'],indirect=True)
@pytest.mark.parametrize('damage',['last','wrong_thread','wrong_home','header','schema','missing_schema','fresh_shape',
    'old_output','unknown_pid','terminal','root_intent'])
def test_resumed_dispatch_rejects_identity_changes_without_writes(launcher,accepted,monkeypatch,damage):
    root,job,first=accepted;record=next_session(root,job,first,monkeypatch);args=resume_arguments(root,record)
    if damage=='last':args[-2]='--last'
    elif damage=='wrong_thread':args[-2]='22222222-2222-4222-8222-222222222222'
    elif damage=='wrong_home':monkeypatch.setenv('THIN_HWA_NATIVE_HOME',str(root/'other-home'))
    elif damage=='header':
        session=execution.home(root,1)/'sessions/current.jsonl'
        session.write_text(json.dumps(dict(type='session_meta',payload=dict(id=THREAD,cwd=str(c.workspace(root,1)),changed=True)))+'\n')
    elif damage=='schema':args[args.index('--output-schema')+1]=str(record/'science-result.schema.json')
    elif damage=='missing_schema':
        at=args.index('--output-schema');del args[at:at+2]
    elif damage=='fresh_shape':args=arguments(root,record)
    elif damage=='old_output':args[args.index('--output-last-message')+1]=str(first/'result.pending.json')
    elif damage=='unknown_pid':
        value=c.read(record/'native-process.json');value['pid']=os.getppid();c.write(record/'native-process.json',value)
    elif damage=='terminal':c.write(record/'native-outcome.json',dict(returncode=0))
    else:
        value=c.read(record/'native-intent.json');value['root_intent_sha256']='0'*64;c.write(record/'native-intent.json',value)
    before={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
    with pytest.raises(ValueError):launcher.native_args(spec(root),c.workspace(root,1),args)
    assert {str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}==before
