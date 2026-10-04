"""Prepare paired public inputs; no model, Goal, instance, training or scoring.

The host-only launch.json is input to the next driver, not a running permission
boundary. Existing namespaces/profile controls must consume its exact bindings.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys

# -I keeps installed product imports isolated; only sibling host-preparation
# helpers need an explicit path. This directory never enters evaluated inputs.
if not __package__:
    sys.path.insert(0,str(Path(__file__).resolve().parent))

try:
    from scripts import prepare_covshift_local as local
except ModuleNotFoundError:
    import prepare_covshift_local as local

ARMS = ('native_goal', 'scidiscovery')
VISIBLE = ('instruction.md', *(f'environment/harness/{n}' for n in
    ('exp_cli.py', 'runner.py', 'train.csv', 'val.csv', 'meta.json')))
WALL_SECONDS = 1800
TOTAL_TOKENS = 200000


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def prepare(output, prepared, candidate, python, source_commit):
    output, prepared, candidate = map(lambda p: Path(p).absolute(), (output, prepared, candidate))
    python = Path(python).absolute()
    old = json.loads(local.helpers().regular_bytes(prepared/'prepared.json', 64*1024))
    local.verify_public(prepared, old)
    metadata_raw = local.helpers().regular_bytes(candidate/'candidate.json', 64*1024)
    metadata = json.loads(metadata_raw)
    if metadata['head'] != source_commit:
        raise ValueError('exact_candidate_source_commit_required')
    if not (python.parent.parent/'pyvenv.cfg').is_file() or not python.is_file():
        raise ValueError('independent_task_venv_required')
    wheels = {}
    for name, expected in metadata['wheels'].items():
        path = Path(name)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('unsafe_wheel_manifest_path')
        raw = local.helpers().regular_bytes(candidate/'build'/path, 32*1024*1024)
        if digest(raw) != expected:
            raise ValueError('candidate_wheel_changed')
        wheels[name] = expected
    if not wheels or not Path(metadata['python']).is_file():
        raise ValueError('prepared_installed_candidate_required')
    public = {name: local.helpers().regular_bytes(prepared/'public'/name, local.INPUT_BOUND)
        for name in VISIBLE}
    settings = {'schema_version':1, 'debug_disable_task_network':True,
        'defaults':{'model':'gpt-6.1-sol', 'reasoning_effort':'high'}, 'operations':{},
        'progression':{'enabled':False, 'root_model':'gpt-6.1-sol', 'root_reasoning_effort':'high'},
        'helpers':{'default_profile':'inherit', 'profiles':{'lightweight':{
            'model':'gpt-6.1-sol', 'reasoning_effort':'high'}}}}
    from scidiscovery.agent_execution_settings import parse_settings
    parse_settings(settings)  # Public format validation, not installed/live qualification.
    output.mkdir(exist_ok=False)
    launch = {'kind':'covshift_custom_paired_pilot_inputs', 'task_revision':local.REVISION,
        'source_prepared':str(prepared), 'source_prepared_sha256':digest((prepared/'prepared.json').read_bytes()),
        'candidate':str(candidate), 'candidate_source_commit':source_commit,
        'candidate_metadata_sha256':digest(metadata_raw), 'candidate_wheels':wheels,
        'task_python':str(python), 'task_venv_config_sha256':digest((python.parent.parent/'pyvenv.cfg').read_bytes()),
        'limits':{'per_mode_wall_seconds':WALL_SECONDS, 'per_mode_total_tokens':TOTAL_TOKENS,
            'participants':'Root, Worker, helper and every native child combined',
            'stop':'whichever limit is reached first; unknown participant usage must stop conservatively',
            'enforcement':'not_verified', 'fixed_currency_cap':'not_claimed'},
        'profile':{'model':'gpt-6.1-sol', 'reasoning_effort':'high',
            'account_runtime_availability':'not_verified'},
        'launch_ready':False, 'models_started':0, 'instances_created':0, 'scoring':'not_run',
        'remaining':['actual native Goal lifecycle driver', 'actual Sci progression with UI binding/authorization',
            'live Worker/helper profile inheritance and owned MCP deployment boundary',
            'all-participant token and deadline supervisor',
            'trusted original grader with isolated untrusted inference'], 'arms':{}}
    for arm in ARMS:
        base=output/arm; project=base/'project'; project.mkdir(parents=True)
        files={}
        for name, raw in public.items():
            target=project/(name if name=='instruction.md' else 'harness/'+Path(name).name)
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(raw);target.chmod(0o444)
            files[str(target.relative_to(project))]=digest(raw)
        (project/'harness/runs').mkdir(mode=0o555)  # Empty mountpoint, no additional task material.
        for name in ('workspace','runs','submission'):
            (project/name).mkdir()
        (project/'bin').mkdir()
        wrapper=('#!/bin/sh\nexec '+shlex.quote(str(python))+' /opt/exp/exp_cli.py "$@"\n').encode()
        (project/'bin/exp').write_bytes(wrapper);(project/'bin/exp').chmod(0o555)
        files['bin/exp']=digest(wrapper)
        local.write(base/'agent-settings.proposal.json',settings)
        environment={'EXP_HARNESS':'/opt/exp','EXP_RUN_DIR':'/opt/exp/runs',
            'EXP_TRAIN':'/opt/exp/train.csv','EXP_VAL':'/opt/exp/val.csv','EXP_META':'/opt/exp/meta.json',
            'EXP_RUNNER':'/opt/exp/runner.py','EXP_DEFAULT_SCRIPT':'/workspace/train.py',
            'EXP_WALL_CAP_S':'60','EXP_AUDIT_BUDGET_S':'45','EXP_AUDIT_LEAKAGE_THRESHOLD':'0.10',
            'PATH':str(project/'bin')+':'+str(python.parent)+':/usr/bin:/bin',
            'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
        launch['arms'][arm]={'project':str(project), 'public_files_sha256':files,
            'agent_settings_proposal':str(base/'agent-settings.proposal.json'),
            'environment':environment,
            'task_path_bindings':[
                {'source':str(project/'harness'),'target':'/opt/exp','access':'read'},
                {'source':str(project/'instruction.md'),'target':'/instruction.md','access':'read'},
                {'source':str(project/'workspace'),'target':'/workspace','access':'write'},
                {'source':str(project/'runs'),'target':'/opt/exp/runs','access':'write'},
                {'source':str(project/'submission'),'target':'/submission','access':'write'}],
            'bindings_enforced':False, 'input_thread':'fresh thread/start; no fork or parent history',
            'driver':'thread/goal/set active' if arm=='native_goal' else 'authorized autonomous progression; not yet activated'}
    local.write(output/'launch.json',launch)
    return launch


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--prepared',type=Path,required=True)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--python',type=Path,required=True)
    parser.add_argument('--source-commit',required=True)
    parser.add_argument('--_lease-fd',type=int,help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args._lease_fd is not None:
        os.close(args._lease_fd)
        metadata=json.loads(local.helpers().regular_bytes(args.candidate/'candidate.json',64*1024))
        if Path(sys.prefix).resolve()!=Path(metadata['python']).parent.parent.resolve():
            raise ValueError('installed_preparer_prefix_mismatch')
        value=prepare(args.output,args.prepared,args.candidate,args.python,args.source_commit)
        print(json.dumps({'launch':str(args.output/'launch.json'),'launch_ready':value['launch_ready']}))
        return
    try:
        from scripts import run_tests as guard
    except ModuleNotFoundError:
        import run_tests as guard
    if args.output.exists():
        raise ValueError('fresh_output_required')
    evidence=args.output.with_name(args.output.name+'-supervision')
    limits=json.loads(guard.DEFAULT_CONFIG.read_text())['limits']
    env=dict(os.environ);env.pop('PYTHONPATH',None);env.pop('SCIDISCOVERY_ROLE_DIR',None)
    env['PYTHONNOUSERSITE']='1';env['PYTHONDONTWRITEBYTECODE']='1'
    with guard.serial_lock() as lease:
        evidence.mkdir(exist_ok=False)
        installed=json.loads(local.helpers().regular_bytes(args.candidate/'candidate.json',64*1024))['python']
        command=[installed,'-I',str(Path(__file__).resolve()),*sys.argv[1:],'--_lease-fd',str(lease.fileno())]
        local.write(evidence/'command.json',{'command':command,'limits':limits,'no_model':True})
        result=guard.run_one(command,env,limits,evidence,lease.fileno())
        local.write(evidence/'resource.json',result)
    print(json.dumps(result))
    if result['returncode'] or result['stop_reason']!='exited':
        raise SystemExit(1)


if __name__=='__main__': main()
