"""Isolated cov launcher: host binds lineage; native receives public work only."""
from pathlib import Path
import argparse, hashlib, json, os, shlex, shutil, sys

def regular(p, bound=4*1024*1024):
    p=Path(p).absolute()
    if p.is_symlink() or not p.is_file() or p.resolve()!=p or p.stat().st_size>bound:
        raise ValueError('regular_bounded_file_required')
    return p.read_bytes()

def file_digest(p):
    p=Path(p).absolute()
    if p.is_symlink() or not p.is_file() or p.resolve()!=p or p.stat().st_size>512*1024*1024:
        raise ValueError('bounded_native_binary_required')
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def load(p):
    s=json.loads(regular(p));public=Path(s['public_root'])
    if s.get('cov_receipt_channel','public_runner_main') not in {'public_runner_main','backend_file'}:
        raise ValueError('explicit_cov_receipt_channel_required')
    if not public.is_absolute() or public.resolve()!=public:
        raise ValueError('absolute_unsymlinked_public_root_required')
    m=json.loads(regular(s['public_manifest']))
    if m['task_revision']!='d78f5eb52ad754c5ee9154741af73130a85a65b8':
        raise ValueError('exact_cov_revision_required')
    expected_files={'task.toml','instruction.md','environment/Dockerfile',*(f'environment/harness/{n}' for n in ['exp_cli.py','runner.py','train.csv','val.csv','meta.json'])}
    if set(m['public_files_sha256'])!=expected_files:raise ValueError('public_whitelist_mismatch')
    expected={}
    for name in expected_files:
        q=Path(name)
        for member in (q,*q.parents[:-1]):expected.setdefault(member.parent,set()).add(member.name)
    for directory,names in expected.items():
        q=public/directory
        if q.is_symlink() or not q.is_dir() or {v.name for v in q.iterdir()}!=names:raise ValueError('public_directory_whitelist_changed')
    for name,h in m['public_files_sha256'].items():
        n=Path(name)
        if n.is_absolute() or '..' in n.parts or hashlib.sha256(regular(public/n)).hexdigest()!=h:
            raise ValueError('frozen_public_input_changed')
    for p,h in [(s['native'],s['native_sha256']),(s['code_mode_host']['path'],s['code_mode_host']['sha256'])]:
        if file_digest(p)!=h:
            raise ValueError('native_binary_changed')
    return s

def controlled(s, workspace, home):
    scene=Path(s['scene_root']).absolute();w=Path(workspace).absolute();h=Path(home).absolute()
    if not scene.is_dir() or scene.resolve()!=scene or not w.is_dir() or w.resolve()!=w:
        raise ValueError('fresh_scene_and_workspace_required')
    if not w.is_relative_to(scene) or not h.is_relative_to(scene) or h==scene or h.is_relative_to(w) or w.is_relative_to(h):
        raise ValueError('separate_scene_home_workspace_required')
    if h.exists() and (not h.is_dir() or h.resolve()!=h):
        raise ValueError('unsymlinked_home_required')
    return w,h

def direct_materials(s,w,job_path):
    if not job_path:raise ValueError('trusted_job_manifest_required')
    p=Path(job_path).absolute();root=Path(s['scene_root'])
    if p.parent!=root/'jobs' or p.is_relative_to(w):raise ValueError('operator_job_root_required')
    job=json.loads(regular(p));items=job.get('direct_materials',[])
    if not isinstance(items,list):raise ValueError('direct_material_list_required')
    result=[];totals={};targets=set()
    for item in items:
        if not isinstance(item,dict) or set(item)!= {'source','path','sha256','size_bytes'}:
            raise ValueError('exact_direct_material_fields_required')
        source=Path(item['source']).absolute();dest=Path(item['path'])
        nodes=root/'project/nodes'
        if not source.is_relative_to(nodes) or source.is_relative_to(w):
            raise ValueError('exact_parent_artifact_path_required')
        relative=source.relative_to(nodes)
        if len(relative.parts)<3 or relative.parts[0]==w.name:
            raise ValueError('exact_parent_artifact_path_required')
        node=relative.parts[0]; inner=Path(*relative.parts[1:])
        if inner.parts[0]=='artifacts':
            exported=Path(*inner.parts[1:])
        elif inner.parts[0]=='experiments':
            parts=inner.parts
            while len(parts)>=3 and parts[0]=='experiments':parts=parts[2:]
            if not (parts[0]=='artifacts' and len(parts)>1 or len(parts)==1 and parts[0] in ('conclusion.json','conclusion.md')):
                raise ValueError('intermediate_material_not_exportable')
            exported=inner
        else:raise ValueError('intermediate_material_not_exportable')
        expected=Path('inputs/parents')/node/'artifacts'/exported
        if dest!=expected or dest.is_absolute() or '..' in dest.parts:
            raise ValueError('exact_parent_artifact_path_required')
        if type(item['size_bytes']) is not int or not 0<=item['size_bytes']<=32*1024*1024:
            raise ValueError('direct_material_file_bound')
        data=regular(source,32*1024*1024);totals[node]=totals.get(node,0)+len(data)
        if totals[node]>64*1024*1024:raise ValueError('direct_material_parent_total_bound')
        if len(data)!=item['size_bytes'] or hashlib.sha256(data).hexdigest()!=item['sha256']:
            raise ValueError('direct_material_digest_mismatch')
        target=w/dest
        if str(target) in targets:raise ValueError('duplicate_direct_material_target')
        targets.add(str(target));target.parent.mkdir(parents=True,exist_ok=True)
        if target.parent.resolve()!=target.parent or target.is_symlink():raise ValueError('material_target_symlink')
        if not target.exists():target.touch(mode=0o444)
        elif not target.is_file():raise ValueError('material_target_not_file')
        result.append((str(source),str(target)))
    return result

def environment(s,w):
    return {'PATH':str(Path(s['scene_root'])/'host-runtime/native-bin')+':'+str(w/'bin')+':'+str(Path(s['task_python']).parent)+':/usr/bin:/bin',
        'EXP_HARNESS':'/opt/exp','EXP_RUN_DIR':s['runs_dir'],'EXP_TRAIN':'/opt/exp/train.csv',
        'EXP_VAL':'/opt/exp/val.csv','EXP_META':'/opt/exp/meta.json','EXP_RUNNER':'/opt/exp/runner.py',
        'EXP_DEFAULT_SCRIPT':str(w/'train.py'),'EXP_WALL_CAP_S':'60','EXP_AUDIT_BUDGET_S':'45',
        'EXP_AUDIT_LEAKAGE_THRESHOLD':'0.10','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1',
        'MKL_NUM_THREADS':'1','TMPDIR':'/task-tmp','HOME':'/task-tmp','LOOPX_USAGE_PING':'0',
        'PYTHONDONTWRITEBYTECODE':'1'}

def exp_wrapper(s,w):
    warning = ('Historical cross-node delivery: use A next_action=deliver and the controller adapter. '
        'Native exp submit uses the paths declared in the run and does not resolve archived historical originals.')
    public = 'exec ' + shlex.quote(s['task_python']) + ' -I /opt/exp/exp_cli.py "$@"'
    return ('#!/bin/sh\ncase "$1" in\nrun|lineage-status|query|collect|cancel) exec '
        + shlex.quote(s['scid_python']) + ' -I -m scidiscovery.research_loop.experiments --config '
        + shlex.quote(str(w/'work/lineage-config.json')) + ' "$@";;\nsubmit|--help|-h|help) printf \'%s\\n\' '
        + shlex.quote(warning) + ' >&2; ' + public + ';;\n*) ' + public + ';;\nesac\n')


def native_profile(s):
    from scidiscovery.research_loop import profiles
    return profiles.selected({'service_tier':'default', **s}, os.environ['THIN_HWA_ROLE'])

def prepare_home(s,w,h, auth_source=None):
    profile=native_profile(s)
    h.mkdir(parents=True,exist_ok=True);(h/'tmp/arg0').mkdir(parents=True,exist_ok=True)
    for p in [Path(s['runs_dir']),Path(s['submission_dir'])]:
        if not p.is_relative_to(Path(s['scene_root'])):
            raise ValueError('scene_output_root_required')
        p.mkdir(parents=True,exist_ok=True)
        if p.resolve()!=p:raise ValueError('unsymlinked_scene_output_required')
    evidence=Path(s['scene_root'])/'native-evidence'/w.name;evidence.mkdir(parents=True,exist_ok=True)
    if evidence.resolve()!=evidence:raise ValueError('unsymlinked_native_evidence_required')
    helper=Path(s['scene_root'])/'host-runtime/native-bin';helper.mkdir(parents=True,exist_ok=True)
    if helper.resolve()!=helper:raise ValueError('unsymlinked_native_helper_root_required')
    for name,target in [('codex-linux-sandbox',s['native']),('apply_patch',s['native']),('codex-code-mode-host',s['code_mode_host']['path'])]:
        alias=helper/name
        if alias.is_symlink():
            if str(alias.readlink())!=target:raise ValueError('native_helper_alias_changed')
        elif alias.exists():raise ValueError('native_helper_alias_not_symlink')
        else:alias.symlink_to(target)
    (w/'bin').mkdir(exist_ok=True)
    wrapper = exp_wrapper(s,w)
    p=w/'bin/exp'
    if p.exists() and regular(p).decode()!=wrapper:raise ValueError('exp_wrapper_changed')
    if not p.exists():p.write_text(wrapper);p.chmod(0o555)
    grants={':root':'deny',':minimal':'read',str(w):'write',str(w/'inputs'):'read',str(h/'tmp/arg0'):'read',
        s['public_root']:'read','/instruction.md':'read','/opt/exp':'read','/opt/exp/runs':'write',
        '/submission':'write','/task-tmp':'write',s['runs_dir']:'write',s['submission_dir']:'write',
        s['native']:'read',s['code_mode_host']['path']:'read',str(helper):'read'}
    control=Path(s['scene_root'])/'host-runtime/experiment-control'/hashlib.sha256(regular(os.environ['THIN_HWA_JOB_MANIFEST'])).hexdigest()
    grants[str(control)]='read'
    for p in ['/usr','/bin','/lib','/lib64',*s['runtime_paths']]:grants[p]='read'
    lines=['model='+json.dumps(profile['model']),'model_reasoning_effort='+json.dumps(profile['reasoning_effort']),
        'service_tier='+json.dumps(profile['service_tier']),'default_permissions='+json.dumps(s['profile']),
        'approval_policy="never"','web_search="disabled"','[permissions.'+s['profile']+'.filesystem]']
    lines.extend(json.dumps(k)+'='+json.dumps(v) for k,v in grants.items())
    lines.extend(['[permissions.'+s['profile']+'.network]','enabled=false','[shell_environment_policy]',
        'inherit="none"','[shell_environment_policy.set]'])
    lines.extend(json.dumps(k)+'='+json.dumps(v) for k,v in environment(s,w).items())
    lines.extend(['[features]','fast_mode=false','apps=false','multi_agent=false'])
    content='\n'.join(lines)+'\n';p=h/'config.toml'
    if p.exists() and regular(p).decode()!=content:raise ValueError('frozen_home_config_changed')
    if not p.exists():p.write_text(content);p.chmod(0o600)
    if auth_source:
        auth=h/'auth.json'
        if not auth.exists():auth.write_bytes(regular(auth_source));auth.chmod(0o600)
    # This metadata is operator-owned outside the scientific workspace.
    (h/'launcher-config-sha256.txt').write_text(hashlib.sha256(content.encode()).hexdigest()+'\n')

def outer(s,w,h,command,materials=()):
    c=[shutil.which('bwrap') or 'bwrap','--unshare-user','--unshare-pid','--unshare-ipc','--unshare-uts',
       '--die-with-parent','--new-session','--clearenv','--proc','/proc','--dev','/dev','--tmpfs','/tmp']
    for p in dict.fromkeys(['/usr','/bin','/lib','/lib64',*s['runtime_paths'],s['native'],s['code_mode_host']['path']]):
        if Path(p).exists():c.extend(['--ro-bind',p,p])
    for p in ['/etc/resolv.conf','/etc/hosts','/etc/ssl/certs']:
        if Path(p).exists():c.extend(['--ro-bind',p,p])
    c.extend(['--ro-bind',str(Path(s['scene_root'])/'host-runtime/native-bin'),str(Path(s['scene_root'])/'host-runtime/native-bin'),'--ro-bind',s['public_root'],s['public_root'],'--ro-bind',s['public_root']+'/instruction.md','/instruction.md',
        '--dir','/opt/exp','--dir','/opt/exp/runs','--bind',str(w),str(w),
        '--bind',str(h),str(h),'--bind',str(Path(s['scene_root'])/'native-evidence'/w.name),str(Path(s['scene_root'])/'native-evidence'/w.name),'--bind',s['runs_dir'],'/opt/exp/runs','--bind',s['submission_dir'],'/submission',
        '--bind',s['runs_dir'],s['runs_dir'],'--bind',s['submission_dir'],s['submission_dir'],
        '--tmpfs','/task-tmp','--chdir',str(w)])
    for name in ['exp_cli.py','runner.py','train.csv','val.csv','meta.json']:
        c.extend(['--ro-bind',str(Path(s['scene_root'])/'host-runtime/native-bin'),str(Path(s['scene_root'])/'host-runtime/native-bin'),'--ro-bind',s['public_root']+'/environment/harness/'+name,'/opt/exp/'+name])
    for source,target in materials:c.extend(['--ro-bind',source,target])
    c.extend(['--ro-bind', str(Path(s['scene_root'])/'host-runtime'/('lineage-'+w.name+'.json')), str(w/'work/lineage-config.json')])
    manifest=Path(s['scene_root'])/'jobs'/(w.name+'.json')
    control=Path(s['scene_root'])/'host-runtime/experiment-control'/hashlib.sha256(regular(manifest)).hexdigest()
    if control.exists():c.extend(['--ro-bind',str(control),str(control)])
    for k,v in {**environment(s,w),'CODEX_HOME':str(h),'LANG':'C.UTF-8'}.items():c.extend(['--setenv',k,v])
    return c+command

def accepted_attempt(s,w,output,*,resume_thread=None,schema=None):
    """Bind fresh/resumed exec to this exact already accepted native dispatch."""
    from scidiscovery.research_loop import contracts as c,execution,continuation,runtime,profiles
    from scidiscovery.research_loop.protocol import require_current
    import time
    root=Path(s['scene_root']).absolute();step=int(w.name)
    job_path=Path(os.environ['THIN_HWA_JOB_MANIFEST']).absolute()
    if job_path!=root/'jobs'/f'{step:03d}.json' or job_path.resolve()!=job_path:
        raise ValueError('exact_job_manifest_required')
    job=c.read(c.regular(job_path));require_current(root,job)
    if w!=c.workspace(root,step) or os.environ['THIN_HWA_ROLE']!=job['role']:
        raise ValueError('accepted_role_workspace_mismatch')
    frozen=c.settings(root)
    declared={'service_tier':'default', **s}
    if profiles.normalize(declared.get('role_profiles',{}),declared)!=profiles.normalize(frozen.get('role_profiles',{}),frozen):
        raise ValueError('launcher_role_profiles_mismatch')
    profiles.for_job(frozen,job)
    continuation.validate_task(root,step)
    if resume_thread is not None or c.settings(root).get('resume_policy') is not None:
        continuation.validate_launcher(root)
    paths=execution.records(root,step);number=len(paths)-1;record=paths[number]
    if output!=record/'result.pending.json' or output.resolve()!=output:
        raise ValueError('output_path_outside_accepted_attempt')
    if (record/'native-outcome.json').exists() or output.exists():
        raise ValueError('original_dispatch_already_terminal_or_returned')
    intent=c.read(c.regular(record/'native-intent.json'))
    if intent.get('task_sha256')!=c.digest(job_path):raise ValueError('accepted_native_task_changed')
    profiles.validate_intent(frozen,job,intent)
    profiles.validate_intent(frozen,job,c.read(execution.origin(root,step)/'native-intent.json'))
    if Path(os.environ['THIN_HWA_NATIVE_HOME']).absolute()!=execution.home(root,step,number):
        raise ValueError('accepted_native_home_mismatch')
    expected_schema=execution.origin(root,step)/'science-result.schema.json'
    if resume_thread is not None:
        if not number or intent.get('session') is None:
            raise ValueError('accepted_resume_session_required')
        if intent.get('continuation_kind')=='fragment':
            if (intent.get('context_mode')!='same_session'
                    or (c.settings(root).get('worker_fragment_policy') or {}).get('context')!='same_session'):
                raise ValueError('accepted_resume_context_mismatch')
        elif intent.get('continuation_kind')=='repair':
            continuation.validate_repair(root,step,intent)
        else:raise ValueError('accepted_resume_kind_required')
        original=continuation.session(root,step,paths[number-1])
        if intent['session']!=original or resume_thread!=original['thread_id']:
            raise ValueError('accepted_resume_session_mismatch')
        if schema!=expected_schema or schema.resolve()!=schema:
            raise ValueError('accepted_resume_schema_mismatch')
    elif number and (intent.get('continuation_kind')!='fragment' or intent.get('context_mode')!='new_context'
            or (c.settings(root).get('worker_fragment_policy') or {}).get('context')!='new_context'):
        raise ValueError('accepted_resume_command_required')
    binding=execution.identity(root,step,number)
    runner=c.read(c.regular(record/'runner-process.json'))
    if runner['pid']!=os.getppid() or not runtime.process_matches(runner,binding):
        raise ValueError('original_runner_dispatch_required')
    # Popen precedes publication of this exact child receipt; wait only for that receipt.
    deadline=time.monotonic()+2
    while not (record/'native-process.json').exists() and time.monotonic()<deadline:time.sleep(.01)
    child=c.read(c.regular(record/'native-process.json'))
    if child['pid']!=os.getpid() or not runtime.process_matches(child,binding):
        raise ValueError('unknown_native_dispatch_cannot_be_replayed')
    return expected_schema

def native_args(s,w,args):
    # Resume is an exact accepted session, never selection by name or recency.
    if not args or args[0]!='exec':raise ValueError('fresh_native_exec_required')
    profile=native_profile(s)
    result=['exec'];i=1;seen=set();configs=set();output=None;schema=None;resuming=False;thread=None
    while i<len(args):
        x=args[i]
        if x=='resume':
            if resuming or any(key in seen for key in ('--model','--output-last-message','--output-schema')):
                raise ValueError('accepted_resume_command_shape_required')
            resuming=True;result.append(x);i+=1;continue
        if x in ['--json','--skip-git-repo-check']:
            result.append(x);i+=1;continue
        if x=='-' and i==len(args)-1:result.append(x);i+=1;continue
        if resuming and not x.startswith('-'):
            import uuid
            if thread is not None:
                raise ValueError('one_exact_resume_thread_required')
            try:
                if str(uuid.UUID(x))!=x:raise ValueError
            except ValueError:raise ValueError('exact_resume_uuid_required') from None
            thread=x;result.append(x);i+=1;continue
        allowed=['--output-last-message','--model','-c','--sandbox','-C']+(['--output-schema'] if resuming else [])
        if x not in allowed or i+1>=len(args) or resuming and x in ['-c','--sandbox','-C']:
            raise ValueError('undeclared_native_argument')
        v=args[i+1];i+=2
        if x in seen and x!='-c':raise ValueError('duplicate_native_argument')
        seen.add(x)
        if x=='--sandbox':
            if v!='workspace-write':raise ValueError('unexpected_legacy_sandbox')
            continue  # Exact legacy flag would override the pinned named deny profile.
        if x=='-C' and Path(v).absolute()!=w:raise ValueError('workspace_argument_mismatch')
        if x=='--model' and v!=profile['model']:raise ValueError('model_profile_mismatch')
        if x=='-c':
            key=v.split('=',1)[0]
            expected={'model_reasoning_effort':profile['reasoning_effort'],'service_tier':profile['service_tier']}
            if key not in expected or v!=key+'='+json.dumps(expected[key]) or key in configs:
                raise ValueError('native_config_override_rejected')
            configs.add(key)
        if x=='--output-last-message':
            p=Path(v).absolute()
            output=p
        if x=='--output-schema':schema=Path(v).absolute()
        result.extend([x,v])
    if not {'--output-last-message','--model','-c','-C'}.issubset(seen) or result[-1]!='-':
        raise ValueError('complete_stdin_role_command_required')
    if 'model_reasoning_effort' not in configs or s.get('role_profiles') is not None and 'service_tier' not in configs:
        raise ValueError('complete_role_profile_config_required')
    if '--skip-git-repo-check' not in result:result.insert(1,'--skip-git-repo-check')
    if resuming and (thread is None or schema is None):
        raise ValueError('complete_resume_session_schema_required')
    schema=accepted_attempt(s,w,output,resume_thread=thread if resuming else None,schema=schema)
    regular(schema)  # The frozen origin schema is mandatory for every context.
    if not resuming:result[-1:-1]=['--output-schema',str(schema)]
    return result

def main():
    a=argparse.ArgumentParser();a.add_argument('--config',required=True);a.add_argument('command',nargs=argparse.REMAINDER);q=a.parse_args()
    s=load(q.config);w,h=controlled(s,os.environ['THIN_HWA_WORKSPACE'],os.environ['THIN_HWA_NATIVE_HOME'])
    if os.environ.get('THIN_HWA_ROLE') not in ['H','W','A','E']:raise ValueError('declared_scientific_role_required')
    args=q.command[1:] if q.command and q.command[0]=='--' else q.command
    import subprocess
    checked=subprocess.run([s['scid_python'],'-I','-c',
        'import sys;from pathlib import Path;from scidiscovery.research_loop import contracts as c;from scidiscovery.research_loop.protocol import require_current;require_current(Path(sys.argv[1]),c.read(c.regular(Path(sys.argv[2]))))',
        s['scene_root'],os.environ['THIN_HWA_JOB_MANIFEST']],capture_output=True,text=True)
    if checked.returncode:raise ValueError('Current scientific contract required before launcher preparation')
    args=native_args(s,w,args);materials=direct_materials(s,w,os.environ.get('THIN_HWA_JOB_MANIFEST'));prepare_home(s,w,h,os.environ.get('THIN_HWA_AUTH_SOURCE'))
    # Only the trusted host sees controller jobs; config is a read-only mount.
    from scidiscovery.research_loop.cov_lineage import configure
    job=json.loads(regular(os.environ['THIN_HWA_JOB_MANIFEST']))
    configured=Path(s['scene_root'])/'host-runtime'/('lineage-'+w.name+'.json')
    configure(Path(s['scene_root']),job['step'],[s['task_python'],'-I','/opt/exp/exp_cli.py'],Path(s['runs_dir']),configured,
        receipt_channel=s.get('cov_receipt_channel','public_runner_main'))
    (w/'work/lineage-config.json').touch(exist_ok=True)
    command=outer(s,w,h,[s['native'],*args],materials);os.execv(command[0],command)

if __name__=='__main__':main()
