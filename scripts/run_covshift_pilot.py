"""Task-specific paired Covshift launcher. Never reads grader/answers or unpickles.

prepare is no-model. preflight must run on the ordinary host; run additionally
requires an authorized budget and the actual account/model + management UI.
No recovery/replay of a submitted trial is supported. Results are engineering
observations, not original LHTB scores. All evidence/configuration is host-only.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import http.client
import inspect
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import socket
import sqlite3
import stat
import subprocess
import sys
import time
import tomllib
from urllib.parse import parse_qs, urlencode, urlsplit

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from scripts import run_tests as guard
    from scripts import prepare_covshift_local as local
except ModuleNotFoundError:
    import run_tests as guard
    import prepare_covshift_local as local

NAME = 'covshift-pilot'
MODEL = 'gpt-6.1-sol'
WALL = 1800
TOKENS = 200000
MAX_TOKENS = 2000000
OBJECTIVE = 'covshift.pilot.objective'


def arm_limits(spec):
    """Explicit new-attempt caps; absent in older specs means original defaults."""
    value=spec.get('limits',{'trial_wall_seconds':WALL,'all_role_tokens':TOKENS})
    if (not isinstance(value,dict) or set(value)!={'trial_wall_seconds','all_role_tokens'}
            or any(type(value[key]) is not int or not 0<value[key]<=maximum
                for key,maximum in (('trial_wall_seconds',WALL),('all_role_tokens',MAX_TOKENS)))):
        raise ValueError('invalid_arm_budget')
    return dict(value)


def resource_limits(spec):
    limits=json.loads(guard.DEFAULT_CONFIG.read_text())['limits']
    supplied=spec.get('resources',{})
    allowed={'observed_tree_rss_stop_bytes','minimum_available_bytes','available_drop_stop_bytes','app_server_tree_rss_bytes'}
    if not isinstance(supplied,dict) or set(supplied)-allowed or any(type(v) is not int or v<=0 for v in supplied.values()):
        raise ValueError('invalid_resource_budget')
    app=supplied.get('app_server_tree_rss_bytes',1000000000)
    limits.update({k:v for k,v in supplied.items() if k!='app_server_tree_rss_bytes'})
    if app>limits['observed_tree_rss_stop_bytes']:raise ValueError('invalid_resource_budget')
    return limits,app


def write(path, value):
    local.write(Path(path), value)


def regular(path, bound=65536):
    return local.helpers().regular_bytes(Path(path), bound)


def sha(path):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or not 0<before.st_size<=512*1024*1024:
            raise ValueError('bounded_regular_identity_required')
        digest=hashlib.sha256()
        with os.fdopen(os.dup(fd),'rb') as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''): digest.update(chunk)
        after=os.fstat(fd)
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
            raise ValueError('identity_file_changed')
        return digest.hexdigest()
    finally: os.close(fd)


def load_launch(path):
    value = json.loads(regular(path))
    if (value.get('kind') != 'covshift_custom_paired_pilot_inputs'
            or value.get('limits', {}).get('per_mode_wall_seconds') != WALL
            or value['limits'].get('per_mode_total_tokens') != TOKENS
            or value.get('profile') != {'model': MODEL, 'reasoning_effort': 'high',
                'account_runtime_availability': 'not_verified'}):
        raise ValueError('frozen_pilot_input_mismatch')
    metadata = Path(value['candidate'])/'candidate.json'
    if sha(metadata) != value['candidate_metadata_sha256']:
        raise ValueError('candidate_metadata_changed')
    expected = {'instruction.md','bin/exp', *(f'harness/{name}' for name in
        ('exp_cli.py','runner.py','train.csv','val.csv','meta.json'))}
    for arm in ('native_goal','scidiscovery'):
        spec = value['arms'][arm]
        if set(spec['public_files_sha256']) != expected:
            raise ValueError('public_view_not_exact')
        for name, digest in spec['public_files_sha256'].items():
            if sha(Path(spec['project'])/name) != digest:
                raise ValueError('public_input_changed')
    return value


def runtime_paths(python, candidate):
    """Only interpreter/library prefixes, not the user's home or repository."""
    base = Path(sys._base_executable).resolve()
    prefixes=(Path(python).parent.parent,Path(candidate).parent.parent)
    paths={str(base.parent.parent/'lib'),*(str(prefix) for prefix in prefixes)}
    for interpreter in (Path(sys._base_executable),Path(python),Path(candidate)):
        for _ in range(8):
            if not any(interpreter.absolute().is_relative_to(prefix) for prefix in prefixes):
                paths.add(str(interpreter.absolute()))
            if not interpreter.is_symlink(): break
            interpreter=(interpreter.parent/interpreter.readlink()).absolute()
        else: raise ValueError('interpreter_symlink_chain_exceeded')
    return sorted(paths)


def native_runtime(native):
    """Exact sibling used by native exec; never grant the whole binary directory."""
    path=Path(native).parent/'codex-code-mode-host'
    return {'path':str(path),'sha256':sha(path)}


def outer_command(spec):
    """Host app-server network for model API; native commands use named deny.

    A PID namespace owns native descendants, including children that setsid.
    Control socket and fresh auth are reachable by the app-server/MCP client,
    never granted to native commands by the inner named profile.
    """
    root, project = Path(spec['root']), Path(spec['project'])
    command = [shutil.which('bwrap') or 'bwrap', '--unshare-user', '--unshare-pid',
        '--unshare-ipc', '--unshare-uts', '--die-with-parent', '--new-session', '--clearenv',
        '--proc','/proc','--dev','/dev','--tmpfs','/tmp']
    mounts = []
    for path in ('/usr','/bin','/lib','/lib64',*spec['runtime_paths']):
        if Path(path).exists():
            mounts.extend(['--ro-bind', path, path])
    for path in ('/etc/resolv.conf','/etc/hosts','/etc/ssl/certs'):
        if Path(path).exists():
            mounts.extend(['--ro-bind', path, path])
    mounts.extend(['--ro-bind', spec['native'], spec['native'],
        '--ro-bind',spec['code_mode_host']['path'],spec['code_mode_host']['path'],
        '--ro-bind',str(project),str(project), '--bind',str(root/'codex-home'),str(root/'codex-home'),
        '--bind',str(root/'host-tmp'),str(root/'host-tmp'),
        '--ro-bind',str(root/'control'),str(root/'control')])
    for name in ('workspace','runs','submission','.scidiscovery-runs'):
        mounts.extend(['--bind',str(project/name),str(project/name)])
    for source,target,access in spec['bindings']:
        mounts.extend(['--bind' if access=='write' else '--ro-bind',source,target])
    mounts.extend(['--bind',str(root/'task-tmp'),'/task-tmp'])
    environment = {'PATH':spec['environment']['PATH'],'CODEX_HOME':str(root/'codex-home'),
        'TMPDIR':str(root/'host-tmp'),'LANG':'C.UTF-8','HOME':str(root/'empty-home')}
    for key,value in environment.items():
        command.extend(['--setenv',key,value])
    return command + mounts + ['--chdir',str(project),spec['native'],'app-server','--stdio']


def provider_tables(providers):
    """Private TOML only; supported provider values never enter argv/logs."""
    lines=[]
    def visit(table,prefix):
        lines.append('['+'.'.join(json.dumps(key) for key in prefix)+']')
        for key,value in table.items():
            if isinstance(value,dict): continue
            if value is None: raise ValueError('unsupported_null_provider_value')
            lines.append(json.dumps(key)+'='+json.dumps(value,allow_nan=False))
        for key,value in table.items():
            if isinstance(value,dict): visit(value,(*prefix,key))
    if not isinstance(providers,dict): raise ValueError('provider_table_required')
    for key,value in providers.items():
        if not isinstance(value,dict): raise ValueError('provider_table_required')
        visit(value,('model_providers',key))
    return lines

CANARY_CHECKS=('instruction','cli','writes','public_write_denied','private_denied',
    'auth_denied','history_denied','child_private_denied','child_auth_denied','child_history_denied',
    'native_network_denied','child_network_denied')

def canary_code(spec):
    private=[str(Path(spec['root'])/'control/private-canary.txt'),
        str(Path(spec['root'])/'codex-home/auth-canary.json'),
        str(Path(spec['root'])/'codex-home/sessions/history-canary')]
    common="""import pathlib,json,errno,socket
def denied(path):
    try:pathlib.Path(path).read_bytes()
    except OSError as exc:return exc.errno in (errno.EACCES,errno.EPERM,errno.ENOENT)
    return False
def netdenied(port):
    try:
        with socket.create_connection(('127.0.0.1',port),timeout=1): return False
    except OSError as exc:return exc.errno in (errno.EPERM,errno.EACCES,errno.ENETUNREACH,errno.ECONNREFUSED,errno.ETIMEDOUT)
    return False
"""
    child=common+f"print(json.dumps([*[denied(p) for p in {private!r}],netdenied({spec['canary_port']!r})]))"
    return common+f"""import subprocess,sys,hashlib
private={private!r}
child=subprocess.run([sys.executable,'-I','-c',{child!r}],capture_output=True,text=True,timeout=5)
values=json.loads(child.stdout) if child.returncode==0 else [False]*4
result={{'instruction':hashlib.sha256(pathlib.Path('/instruction.md').read_bytes()).hexdigest()=={spec['public_sha256']['instruction.md']!r},
'cli':hashlib.sha256(pathlib.Path('/opt/exp/exp_cli.py').read_bytes()).hexdigest()=={spec['public_sha256']['harness/exp_cli.py']!r},
'writes':all((pathlib.Path(p)/'canary').write_text('synthetic')==9 for p in ['/workspace','/opt/exp/runs','/submission']),
'native_network_denied':netdenied({spec['canary_port']!r}),'child_network_denied':values[3]}}
try:pathlib.Path('/instruction.md').write_text('forbidden');result['public_write_denied']=False
except OSError as exc:result['public_write_denied']=exc.errno in (errno.EPERM,errno.EACCES,errno.EROFS)
for key,path,value in zip(['private','auth','history'],private,values):result[key+'_denied']=denied(path);result['child_'+key+'_denied']=value
print(json.dumps(result))
"""


def permissions(spec):
    from scidiscovery.platforms.codex_root_host import RootPermissions
    return RootPermissions(network_access=False, permission_profile=NAME,
        profile_definition=json.dumps(spec['definition']))


def prepare(launch_path, output, native, auth_file=None, provider_config=None, *,
        native_goal_tokens=TOKENS,native_goal_wall_seconds=WALL,
        scidiscovery_tokens=TOKENS,scidiscovery_wall_seconds=WALL,resource_config=None,human_wait_seconds=1800,
        auto_manage_instance=False,management_authorization_file=None):
    if type(human_wait_seconds) is not int or human_wait_seconds<=0:raise ValueError('invalid_human_wait')
    resources=json.loads(regular(resource_config)) if resource_config is not None else {}
    resource_limits({'resources':resources})
    launch = load_launch(launch_path)
    budgets={arm:arm_limits({'limits':{'all_role_tokens':tokens,'trial_wall_seconds':wall}})
        for arm,tokens,wall in (('native_goal',native_goal_tokens,native_goal_wall_seconds),
            ('scidiscovery',scidiscovery_tokens,scidiscovery_wall_seconds))}
    authorization=None
    if auto_manage_instance:
        if management_authorization_file is None:raise ValueError('explicit_management_authorization_required')
        original=regular(management_authorization_file).decode().strip()
        if not original:raise ValueError('explicit_management_authorization_required')
        authorization={'source':'explicit_user_instruction','text':original,
            'scope':'create and bind one fresh Covshift instance and confirm its frozen loop budget',
            'limits':budgets['scidiscovery']}
    output = Path(output).absolute(); native = Path(native).resolve(strict=True)
    code_mode_host=native_runtime(native)
    output.mkdir(mode=0o700)
    metadata = json.loads(regular(Path(launch['candidate'])/'candidate.json'))
    installed = Path(metadata['python'])
    result = {'kind':'covshift_pilot_launcher','inputs_sha256':sha(launch_path),
        'candidate':launch['candidate'],'candidate_source':metadata['head'],
        'candidate_metadata_sha256':launch['candidate_metadata_sha256'],
        'native':str(native),'native_sha256':sha(native),'code_mode_host':code_mode_host,'task_revision':launch['task_revision'],
        'limits':{'trial_wall_seconds':WALL,'all_role_tokens':MAX_TOKENS,'startup_seconds':300,
            'virtual_address_space':'not_capped_by_supervisor','tree_rss_bytes':resource_limits({'resources':resources})[0]['observed_tree_rss_stop_bytes'],
            'app_server_tree_rss_bytes':resource_limits({'resources':resources})[1],'log_bytes':8388608,'numerical_threads':1,
            'cpu_affinity':'one CPU chosen from supervisor allowed set',
            'token_semantics':'observed cumulative thread counters; asynchronous stop can overshoot; missing coverage stops'},
        'profile':{'model':MODEL,'reasoning_effort':'high'},'arm_limits':budgets,
        'budget_semantics':'limits are original authorization ceilings; arm_limits are new-attempt caps, not resumed state',
        'arms':{},'launch_ready':False}
    for arm in ('native_goal','scidiscovery'):
        budget=budgets[arm]
        base = output/arm; project=base/'project'; project.mkdir(parents=True)
        for name in ('workspace','runs','submission','.scidiscovery-runs'):
            (project/name).mkdir()
        for name in launch['arms'][arm]['public_files_sha256']:
            target=project/name; target.parent.mkdir(exist_ok=True)
            target.write_bytes(regular(Path(launch['arms'][arm]['project'])/name,local.INPUT_BOUND))
            target.chmod(0o555 if name=='bin/exp' else 0o444)
        (project/'harness/runs').mkdir(mode=0o555)  # Existing mountpoint beneath read-only /opt/exp.
        for directory in ('control','state','codex-home','host-tmp','task-tmp','empty-home','evidence'):
            (base/directory).mkdir(mode=0o700)
        (base/'codex-home/tmp/arg0').mkdir(parents=True,mode=0o700)
        settings=json.loads(regular(launch['arms'][arm]['agent_settings_proposal']))
        settings['progression'].update(enabled=arm=='scidiscovery',root_network_access=False,
            max_elapsed_seconds=budget['trial_wall_seconds'],max_calendar_seconds=budget['trial_wall_seconds'],
            max_tokens=budget['all_role_tokens'],max_rss_bytes=resource_limits({'resources':resources})[1],
            token_policy='bounded_fallback',closeout_reserve_tokens=10000)
        write(base/'agent-settings.json',settings)
        env=dict(os.environ,SCID_AGENT_SETTINGS_FILE=str(base/'agent-settings.json'))
        env.pop('PYTHONPATH',None); env['PYTHONNOUSERSITE']='1'
        command=[str(installed),'-I','-m','scidiscovery.artifact_agent.interfaces.cli',
            '--project-root',str(project),'--state-root',str(base/'state'),'init','codex',
            '--python',str(installed),'--control-socket',str(base/'control/control.sock')]
        completed=subprocess.run(command,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
        (base/'evidence/init.log').write_bytes(completed.stdout)
        if completed.returncode:
            raise RuntimeError('installed_initializer_failed:'+arm)
        spec={'arm':arm,'limits':budget,'resources':resources,'human_wait_seconds':human_wait_seconds,
            'management_authorization':authorization if arm=='scidiscovery' else None,
            'root':str(base),'project':str(project),'python':str(installed),
            'task_python':launch['task_python'],'native':str(native),'native_sha256':result['native_sha256'],
            'code_mode_host':code_mode_host,
            'environment':{**launch['arms'][arm]['environment'],
                'PATH':str(project/'bin')+':'+str(Path(launch['task_python']).parent)+':/usr/bin:/bin'},
            'runtime_paths':runtime_paths(launch['task_python'],installed),
            'bindings':[(str(project/'harness'),'/opt/exp','read'),
                (str(project/'instruction.md'),'/instruction.md','read'),
                (str(project/'workspace'),'/workspace','write'),
                (str(project/'runs'),'/opt/exp/runs','write'),
                (str(project/'submission'),'/submission','write')],
            'candidate':launch['candidate'],'candidate_source':metadata['head'],
            'public_sha256':launch['arms'][arm]['public_files_sha256'],
            'settings_sha256':sha(base/'agent-settings.json')}
        grants={':root':'deny',':minimal':'read',str(project):'read',
            str(base/'codex-home/tmp/arg0'):'read',str(native):'read',
            code_mode_host['path']:'read','/task-tmp':'write'}
        for path in spec['runtime_paths']:
            grants[path]='read'
        for path in ('/usr','/bin','/lib','/lib64'):
            grants[path]='read'
        for name in ('workspace','runs','submission','.scidiscovery-runs'):
            grants[str(project/name)]='write'
        for _,target,access in spec['bindings']:
            grants[target]=access
        spec['native_features']=tomllib.loads((project/'.codex/config.toml').read_text()).get('features',{})
        if arm=='native_goal':
            # Native has the task and native platform tools, no Sci scheduler prompt/MCP.
            for path in (project/'AGENTS.md',project/'.codex/AGENTS.md'):
                path.unlink(missing_ok=True)
            shutil.rmtree(project/'.codex/agents',ignore_errors=True)
            (project/'.codex/config.toml').write_text('web_search="disabled"\n')
        spec['definition']={'filesystem':grants,'network':{'enabled':False}}
        lines=['default_permissions='+json.dumps(NAME),'approval_policy="never"','web_search="disabled"',
            '[permissions.'+NAME+'.filesystem]']
        lines.extend(json.dumps(k)+'='+json.dumps(v) for k,v in grants.items())
        lines.extend(['[permissions.'+NAME+'.network]','enabled=false',
            '[shell_environment_policy]','inherit="none"','[shell_environment_policy.set]'])
        lines.extend(json.dumps(k)+'='+json.dumps(v) for k,v in {**spec['environment'],'TMPDIR':'/task-tmp','HOME':'/task-tmp'}.items())
        if provider_config is not None:
            # Only provider transport values are copied. No personal MCPs,
            # instructions, memories, projects or permissions are inherited.
            provider=tomllib.loads(regular(provider_config).decode())
            if 'model_provider' in provider:
                lines.insert(0,'model_provider='+json.dumps(provider['model_provider']))
            lines.extend(provider_tables(provider.get('model_providers',{})))
        (base/'codex-home/config.toml').write_text('\n'.join(lines)+'\n')
        if auth_file is not None:
            destination=base/'codex-home/auth.json'
            destination.write_bytes(regular(auth_file));destination.chmod(0o600)
        (base/'codex-home/auth-canary.json').write_text('{"synthetic":true}\n')
        (base/'codex-home/sessions').mkdir(mode=0o700)
        (base/'codex-home/sessions/history-canary').write_text('synthetic history\n')
        (base/'control/private-canary.txt').write_text('synthetic-private\n')
        write(base/'spec.json',spec); result['arms'][arm]=str(base/'spec.json')
    write(output/'pilot.json',result)
    return result


class Meter:
    """Ephemeral observation of existing platform counters, not another ledger."""
    def __init__(self, clock=time.monotonic, *, tokens=TOKENS,wall_seconds=WALL):
        budget=arm_limits({'limits':{'all_role_tokens':tokens,'trial_wall_seconds':wall_seconds}})
        self.token_limit=budget['all_role_tokens'];self.wall_seconds=budget['trial_wall_seconds']
        self.clock=clock; self.records={}; self.started={}; self.deadline=None; self.reason=None
        self.canary_command=None;self.proofs={};self.children={};self.control_records={};self.completed={}
        self.frontend_roles={};self.frontend_loop=None
        self.turns_requested=0;self.scientific_turns_requested=0;self.observed_turns=set()
    def activate(self):
        if self.deadline is not None: raise RuntimeError('trial_already_submitted')
        self.deadline=self.clock()+self.wall_seconds
    def observe(self,event):
        from scidiscovery.platforms.codex_usage import observe_usage
        params=event.get('params',{}); thread=params.get('threadId')
        turn_id=params.get('turnId') or (params.get('turn') or {}).get('id')
        if isinstance(thread,str) and isinstance(turn_id,str) and turn_id:
            if event.get('method') in ('turn/started','turn/completed','thread/tokenUsage/updated'):
                self.observed_turns.add((thread,turn_id))
        if event.get('method')=='turn/started':
            if not isinstance(thread,str) or not thread: raise RuntimeError('unidentified_native_turn')
            self.started.setdefault(thread,self.clock())
        if event.get('method')=='turn/completed' and isinstance(thread,str):
            self.completed[thread]=self.clock()
        if event.get('method')=='thread/tokenUsage/updated':
            record=observe_usage(params,previous=self.records.get(thread))
            self.records[thread]=record
            if record['has_gaps']: self.reason='token_coverage_unknown'
        item=params.get('item',{})
        if event.get('method')=='item/completed' and isinstance(thread,str):
            if item.get('type')=='subAgentActivity':
                child=item.get('agentThreadId')
                if (item.get('kind') not in {'started','interacted','interrupted','completed'}
                        or not isinstance(item.get('agentPath'),str) or not item['agentPath']
                        or not isinstance(child,str) or not child or child==thread
                        or self.children.get(child,thread)!=thread):
                    raise RuntimeError('native_child_identity_conflict')
                self.children[child]=thread;self.started.setdefault(child,self.clock())
            if item.get('type')=='collabAgentToolCall' and item.get('senderThreadId')==thread:
                for child in item.get('receiverThreadIds',[]):
                    if isinstance(child,str) and child!=thread:
                        if self.children.get(child,thread)!=thread:raise RuntimeError('native_child_identity_conflict')
                        self.children[child]=thread
                        self.started.setdefault(child,self.clock())
            if item.get('type')=='commandExecution' and matches_canary_command(item.get('command'),self.canary_command):
                try:checks=json.loads(item.get('aggregatedOutput',''))
                except (TypeError,ValueError):checks={}
                if (item.get('exitCode')==0 and item.get('status')=='completed'
                        and set(checks)==set(CANARY_CHECKS) and all(v is True for v in checks.values())):
                    self.proofs[thread]={'item_id':item.get('id'),'command':item['command'],'checks':checks}
        self.check()
    def total(self):
        threads=set(self.records)|set(self.control_records)
        return sum(sum(max(self.records.get(thread,{}).get('counted_tokens',{}).get(key,0),
            self.control_records.get(thread,{}).get('counted_tokens',{}).get(key,0))
            for key in ('input_tokens','output_tokens')) for thread in threads)
    def check(self):
        if self.deadline is None: return
        if self.clock()>=self.deadline: self.reason='wall_deadline'
        if self.total()>=self.token_limit: self.reason='observed_token_limit'
        if any(not any(source.get(thread,{}).get('coverage')=='observed' and not source[thread].get('has_gaps')
                for source in (self.records,self.control_records)) and self.clock()-when>5
                for thread,when in self.completed.items()):
            self.reason='participant_usage_unconfirmed'
        if self.reason: raise RuntimeError(self.reason)


def matches_canary_command(actual,expected):
    """0.159.2 shell-formats its real argv; accept only the observed exact wrapper."""
    if not isinstance(actual,str) or not isinstance(expected,str):return False
    if actual==expected:return True
    try:return shlex.split(actual)==['/usr/bin/bash','-lc',expected]
    except ValueError:return False


def public_call(host,name,arguments):
    reply=host.connection.rpc('mcpServer/tool/call',{'threadId':host.identity.thread_id,
        'server':'scidiscovery','tool':'scid_call','arguments':{'name':name,'arguments':arguments},
        '_meta':{'x-codex-turn-metadata':{'thread_id':host.identity.thread_id,'session_id':host.identity.session_id}}})
    if reply.get('isError'): raise RuntimeError('public_call_failed:'+name)
    value=reply.get('structuredContent')
    return value if isinstance(value,dict) else json.loads(reply['content'][0]['text'])


def verify_role_thread(thread,thread_id):
    # Current configured profile is an early rejection, not per-turn telemetry.
    if (thread.get('id')!=thread_id or thread.get('forkedFromId') is not None
            or thread.get('model')!=MODEL or thread.get('reasoningEffort')!='high'):
        raise RuntimeError('role_platform_identity_profile_or_history_unconfirmed')


def role_turn_profiles(thread,spec):
    """Read only profile metadata from the actual fresh host's own bounded log.

    Thread.model is explicitly not per-turn telemetry in the platform schema.
    Missing/unsafe logs or incomplete turn_context evidence cannot earn a gate.
    No chat, instructions, provider or authentication fields are returned.
    """
    path=Path(thread.get('path') or '')
    root=Path(spec['root'])/'codex-home/sessions'
    if not path.is_absolute() or not path.is_relative_to(root):
        raise RuntimeError('role_turn_profile_unconfirmed')
    if any(part.is_symlink() for part in (path,*path.parents)):
        raise RuntimeError('role_turn_profile_unconfirmed')
    data=regular(path,8*1024*1024)
    contexts={};identity=None
    for line in data.splitlines():
        if len(line)>1024*1024:raise RuntimeError('role_turn_profile_coverage_exceeded')
        record=json.loads(line);body=record.get('payload') or {}
        if record.get('type')=='session_meta':
            if identity is not None and identity!=body.get('id'):raise RuntimeError('role_turn_profile_unconfirmed')
            identity=body.get('id')
        if record.get('type')=='turn_context':
            turn=body.get('turn_id');profile=(body.get('model'),body.get('effort'))
            if not isinstance(turn,str) or not turn or profile!=(MODEL,'high'):
                raise RuntimeError('role_executed_model_drift_or_unconfirmed')
            if turn in contexts and contexts[turn]!=profile:raise RuntimeError('role_turn_profile_unconfirmed')
            contexts[turn]=profile
    turns=thread.get('turns')
    if (identity!=thread['id'] or not isinstance(turns,list) or not turns
            or any(t.get('status')!='completed' or not isinstance(t.get('id'),str)
                or t['id'] not in contexts for t in turns)):
        raise RuntimeError('role_turn_profile_unconfirmed')
    return {'turn_ids':sorted(contexts),'model':MODEL,'reasoning_effort':'high',
        'source':'fresh_host_turn_context','source_sha256':hashlib.sha256(data).hexdigest()}


def read_role_proofs(host,meter,spec,roles):
    """Authenticated platform items + exact attachment, never Agent chat."""
    qualification={}
    for role,thread_id in roles.items():
        reply=host.connection.rpc('thread/read',{'threadId':thread_id,'includeTurns':True})
        thread=reply.get('thread',{})
        verify_role_thread(thread,thread_id)
        if (not isinstance(thread.get('sessionId'),str)
                or thread.get('status',{}).get('type')!='idle'):
            raise RuntimeError('role_platform_identity_profile_or_history_unconfirmed')
        executed=role_turn_profiles(thread,spec)
        subscribed=host.connection.rpc('thread/resume',{'threadId':thread_id,'excludeTurns':True})
        if subscribed.get('thread',{}).get('sessionId')!=thread['sessionId']:
            raise RuntimeError('role_native_identity_changed')
        permissions(spec).verify(subscribed,cwd=thread.get('cwd',''))
        for turn in thread.get('turns',[]):
            for item in turn.get('items',[]):
                meter.observe({'method':'item/completed','params':{'threadId':thread_id,'item':item}})
        if thread_id not in meter.proofs: return None
        qualification[role]={'thread_id':thread_id,'platform_session':thread['sessionId'],
            'executed_profile':executed,'permission_declaration':permissions(spec).declaration(),**meter.proofs[thread_id]}
    return qualification


def control_usage(spec,loop_id,current):
    """Bounded original accounting projection plus actual same-loop attachments."""
    from scidiscovery.artifact_agent.service.progression_records import hydrate_control_row
    from scidiscovery.artifact_agent.service.research_loops import loop_usage
    from scidiscovery.agent_execution_settings import progression_usage_capacity
    base=Path(spec['root'])/'state/database'
    with sqlite3.connect((base/'scheduler-bindings.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        db.execute('BEGIN')
        row=db.execute('SELECT p.* FROM scheduler_progression p JOIN scheduler_instances i USING(instance_id) WHERE i.name=?',(current['name'],)).fetchone()
        if not row: raise RuntimeError('authorized_loop_record_missing')
        row=hydrate_control_row(db,row,accounting_only=True)
        cp=json.loads(row['checkpoint_json'])
    if cp.get('current_loop_id')!=loop_id: raise RuntimeError('authorized_loop_changed')
    authorization=cp['loop_authorizations'][loop_id]
    capacity=progression_usage_capacity(authorization['config']['effective'])
    with sqlite3.connect((base/'runs.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
        rows=db.execute("""SELECT w.thread_id,w.platform_session,'worker',r.run_id FROM runs r JOIN worker_connections w USING(run_id)
          WHERE r.instance_id=? AND json_extract(CAST(r.recovery_policy_json AS TEXT),'$.loop_id')=?
          UNION ALL SELECT w.thread_id,w.platform_session,'helper',r.run_id FROM runs r JOIN worker_participants w USING(run_id)
          WHERE r.instance_id=? AND json_extract(CAST(r.recovery_policy_json AS TEXT),'$.loop_id')=?
          AND w.thread_id IS NOT NULL LIMIT ?""",(row['instance_id'],loop_id,row['instance_id'],loop_id,capacity+1)).fetchall()
    if len(rows)>capacity: raise RuntimeError('loop_participant_coverage_exceeded')
    participants={}
    accepted={item['run_id'] for item in cp.get('admissions',{}).values() if item.get('state')=='accepted'}
    for thread,session,role,run in rows:
        if run not in accepted or not thread or not session or (thread in participants and participants[thread]!=(role,session)):
            raise RuntimeError('loop_participant_scope_conflict')
        participants[thread]=(role,session)
    return {'instance':row['instance_id'],'loop':loop_id,'records':loop_usage(cp),
        'participants':participants,'frontend_unmeasured':bool(authorization.get('unmeasured_frontend_root')),
        'root_native':{'thread':(json.loads(row['host_json'] or '{}') or {}).get('thread_id'),
            'inflight':cp.get('phase')=='running' and bool(cp.get('turn_id')),
            'terminal':cp.get('native_completion') in {'completed','failed','interrupted'}}}


def reconcile_control(meter,snapshot):
    """Supplement control's retained partial marker, never clear or rewrite it."""
    records=snapshot['records'];expected={thread:identity[0] for thread,identity in snapshot['participants'].items()}
    if snapshot['frontend_unmeasured']:
        if meter.frontend_loop!=snapshot['loop'] or set(meter.frontend_roles)!={'root','worker','helper'}:
            raise RuntimeError('frontend_role_coverage_unconfirmed')
        for role,proof in meter.frontend_roles.items():
            thread=proof['thread_id']
            if role!='root' and snapshot['participants'].get(thread)!=(role,proof['platform_session']):
                raise RuntimeError('frontend_role_scope_changed')
            expected[thread]=role
    pending_attribution=[]
    for thread,record in records.items():
        unattributed=record.get('role')=='unattributed'
        if (record.get('thread_id')!=thread or record.get('loop_id')!=snapshot['loop']
                or (record.get('owner') is not None if unattributed else record.get('owner')!=snapshot['instance'])
                or record.get('role') not in {'root','worker','helper','unattributed'}
                or (not unattributed and record['role']!='root' and expected.get(thread)!=record['role'])):
            raise RuntimeError('control_usage_scope_conflict')
        if unattributed:
            pending_attribution.append(thread)  # Usage can precede worker_attach; do not infer its role.
        expected[thread]=record['role']
    if (set(meter.records)|set(meter.started)|set(meter.children))-set(expected):
        raise RuntimeError('participant_scope_unconfirmed')
    pending=[]
    for thread in expected:
        sources=[source[thread] for source in (meter.records,records) if thread in source]
        initial=records.get(thread,{})
        placeholder=(initial.get('pending_observation') is True and initial.get('coverage')=='missing'
            and initial.get('high_water')==dict(input_tokens=None,cached_input_tokens=None,output_tokens=None)
            and initial.get('counted_tokens')==dict(input_tokens=0,cached_input_tokens=0,output_tokens=0))
        if any((record.get('has_gaps') or record.get('coverage')!='observed')
                and not (record is initial and placeholder) for record in sources):
            raise RuntimeError('participant_usage_unconfirmed')
        if any(record.get('coverage')=='observed' and not record.get('has_gaps') for record in sources): continue
        native=initial.get('native_turn') or {}
        actual_turn=all(isinstance(native.get(key),str) and native[key] for key in ('binding_key','turn_id','connection_id'))
        terminal=initial.get('native_terminal') or {}
        root=snapshot.get('root_native',{}) if expected[thread]=='root' else {}
        finished=bool(terminal) or bool(initial.get('retired_after_turn')) or (root.get('thread')==thread and root.get('terminal'))
        inflight=(actual_turn and not terminal) or (root.get('thread')==thread and root.get('inflight'))
        if finished: meter.completed.setdefault(thread,meter.clock())
        elif not inflight and meter.clock()-meter.started.setdefault(thread,meter.clock())>5:
            raise RuntimeError('participant_native_activity_unconfirmed')
        pending.append(thread)
    meter.control_records=records
    meter.check()
    return {'coverage':('pending_attribution' if pending_attribution else
            'pending_native_usage' if pending else 'observed_with_frontend_receipts'),
        'pending_attribution_threads':pending_attribution,'pending_threads':pending,'known_tokens_lower_bound':meter.total(),'participants':len(expected),
        'control_frontend_partial_retained':snapshot['frontend_unmeasured']}



def confirm_loop(spec,current,scheduling,objective):
    """Use the existing frozen control record, not only the UI's budget summary."""
    from scidiscovery.agent_execution_settings import load_settings,effective_settings
    expected=effective_settings(load_settings(Path(spec['root'])/'agent-settings.json'),{})
    loop=scheduling.get('loop') or {}
    database=Path(spec['root'])/'state/database/scheduler-bindings.sqlite3'
    with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        row=db.execute('SELECT p.* FROM scheduler_progression p JOIN scheduler_instances i USING(instance_id) WHERE i.name=?',(current['name'],)).fetchone()
        binding=db.execute("SELECT object_id FROM scheduler_bindings b JOIN scheduler_instances i ON b.instance=i.instance_id WHERE i.name=? AND b.namespace='artifact' AND b.name=?",(current['name'],objective)).fetchone()
    if (not row or not binding or loop.get('limits')!=expected['progression']
            or json.loads(row['config_json']).get('effective')!=expected
            or json.loads(row['objective_ref_json'] or '{}').get('artifact_id')!=binding[0]
            or json.loads(row['checkpoint_json']).get('current_loop_id')!=loop.get('id')
            or row['state']!='paused' or row['reason']!='loop_authorized'
            or row['host_json'] or row['owner_session'] is not None):
        raise RuntimeError('frozen_loop_profile_scope_or_authorization_changed')


def attached_roles(spec,instance_id,loop_id):
    # Read the existing control authority; this is not a canary role registry.
    with sqlite3.connect((Path(spec['root'])/'state/database/runs.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
        rows=db.execute("""SELECT 'worker',w.thread_id FROM runs r JOIN worker_connections w USING(run_id)
          WHERE r.instance_id=? AND json_extract(CAST(r.recovery_policy_json AS TEXT),'$.loop_id')=?
          UNION ALL SELECT 'helper',w.thread_id FROM runs r JOIN worker_participants w USING(run_id)
          WHERE r.instance_id=? AND json_extract(CAST(r.recovery_policy_json AS TEXT),'$.loop_id')=?
          AND w.thread_id IS NOT NULL LIMIT 4""",(instance_id,loop_id,instance_id,loop_id)).fetchall()
    result={}
    for role,thread in rows:
        if role in result and result[role]!=thread: raise RuntimeError('canary_attachment_ambiguous')
        result[role]=thread
    return result


def role_canary(host,meter,spec,current=None,loop=None):
    """A bounded paid synthetic stage inside the same frozen arm budget.

    It never sends the Covshift question. Scientific activation requires real
    native command receipts for every role; ordinary completion chat is ignored.
    """
    script=Path(spec['project'])/'.qualification/canary.py'
    script.parent.mkdir(exist_ok=True)
    listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(2)
    try:
        script.write_text(canary_code({**spec,'canary_port':listener.getsockname()[1]}));script.chmod(0o444)
        command=shlex.join([spec['task_python'],'-I',str(script)])
        meter.canary_command=command
        meter.activate();(Path(spec['root'])/'model-submission-started').touch(exist_ok=False)
        prompt='Engineering isolation qualification only; do not read or solve /instruction.md. Execute exactly this read-only synthetic command, without shell wrappers or edits: '+command
        if spec['arm']=='native_goal':
            prompt+=f' Then spawn exactly one fresh native helper with model={MODEL}, reasoning_effort=high, fork_turns=none and the same permissions, to execute exactly the same command. Do not substitute another model. If this exact profile is unavailable, stop without spawning. Wait for it. Do not perform scientific work.'
        else:
            prompt+=' Through the public contracts dispatch one complete science.evidence.extract.v1 Worker task on only the synthetic text "isolation canary, no scientific observation". The Worker must execute this command, prepare and attach one native helper with the same permissions/profile and fresh context to execute the same command, wait and integrate its result, then deliver through its actual contract. Use actual platform coordinates and exact assignment. This is a synthetic engineering task; no Covshift experiment.'
        meter.turns_requested+=1
        host.start_turn(prompt)
        while host.completion is None:
            host.connection.poll(.2);meter.check()
            # A native child is discovered from authenticated platform items;
            # subscribing neither starts a turn nor overrides its permissions.
            for thread in list(meter.children):
                actual=host.connection.rpc('thread/read',{'threadId':thread,'includeTurns':False}).get('thread',{})
                verify_role_thread(actual,thread)
                if thread not in meter.records:
                    host.connection.rpc('thread/resume',{'threadId':thread,'excludeTurns':True})
        roles={'root':host.identity.thread_id}
        if spec['arm']=='native_goal':
            children=[t for t,parent in meter.children.items() if parent==host.identity.thread_id]
            if len(children)!=1: raise RuntimeError('native_helper_canary_missing_or_ambiguous')
            roles['helper']=children[0]
        else:
            with sqlite3.connect((Path(spec['root'])/'state/database/scheduler-bindings.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
                row=db.execute('SELECT instance_id FROM scheduler_instances WHERE name=?',(current['name'],)).fetchone()
            if not row: raise RuntimeError('selected_canary_instance_missing')
            roles.update(attached_roles(spec,row[0],loop['id']))
            if set(roles)!={'root','worker','helper'}: raise RuntimeError('actual_worker_helper_attach_missing')
        proof=read_role_proofs(host,meter,spec,roles)
        if set(meter.started)-set(roles.values()):raise RuntimeError('unexpected_canary_participant')
        if not proof or any(thread not in meter.records for thread in roles.values()):
            raise RuntimeError('actual_role_command_or_usage_unconfirmed')
        if spec['arm']=='scidiscovery':
            meter.frontend_roles=proof;meter.frontend_loop=loop['id']
        write(Path(spec['root'])/'role-canary.json',{'qualification':proof,
            'definition_sha256':permissions(spec).declaration()['permission_profile']['sha256'],
            'script_sha256':sha(script),'tokens_so_far':meter.total(),'science_started':False})
        for path in ('workspace','runs','submission'):
            (Path(spec['project'])/path/'canary').unlink(missing_ok=True)
        script.unlink();script.parent.rmdir()
        return proof
    finally:listener.close()


def launch_root(spec,meter):
    from scidiscovery.platforms.codex_app_server import AppServer,HostLimits,config_flags
    from scidiscovery.platforms.codex_progression import CodexProgressionHost,PrivateLog
    project=Path(spec['project']);config=tomllib.loads((project/'.codex/config.toml').read_text())
    if spec['arm']=='native_goal':
        config.pop('mcp_servers',None);config['mcp_servers']={}
        config['features']=spec['native_features']
    log=PrivateLog(Path(spec['root'])/'evidence/app-server.log',8388608)
    connection=AppServer.launch(outer_command(spec)+config_flags(config),cwd=project,
        environment=dict(os.environ),stderr=log.writer,on_event=meter.observe,
        limits=HostLimits(frame_bytes=1048576))
    rpc=connection.rpc
    def observed_rpc(method,params):
        reply=rpc(method,params)
        if method in ('thread/start','thread/resume'):
            write(Path(spec['root'])/'evidence/permission-projection.json',{k:reply.get(k) for k in ('approvalPolicy','activePermissionProfile','sandbox')})
        return reply
    connection.rpc=observed_rpc
    host=CodexProgressionHost(connection,log,permissions(spec));host.resource_limit=resource_limits(spec)[1]
    connection.checkpoint=lambda:(meter.check(),host.guard_resources())
    host.initialize(cwd=str(project),expected_config=config)
    # No legacy sandbox override and no parent/fork history.
    host.open_root(cwd=str(project),options={'model':MODEL,'config':{'model_reasoning_effort':'high','web_search':'disabled'}})
    fresh=connection.rpc('thread/read',{'threadId':host.identity.thread_id,'includeTurns':False}).get('thread',{})
    if fresh.get('id')!=host.identity.thread_id or fresh.get('forkedFromId') is not None or fresh.get('model')!=MODEL or fresh.get('reasoningEffort')!='high':
        host.close();raise RuntimeError('fresh_root_profile_or_history_unconfirmed')
    return host


def daemon(spec,ui):
    from scidiscovery.agent_execution_settings import load_settings
    from scidiscovery.artifact_agent.interfaces import mcp_daemon
    from scidiscovery.platforms.codex_progression import CodexProgressionFactory
    if 'progression_host_factory' not in inspect.signature(mcp_daemon.main).parameters:
        raise RuntimeError('installed_candidate_missing_reviewed_factory_hook')
    base=Path(spec['root'])
    factory=CodexProgressionFactory(project_root=spec['project'],state_root=base/'state',
        socket_path=base/'control/control.sock',approval_base_url=ui,
        command=outer_command(spec),permissions=permissions(spec),
        agent_settings=load_settings(base/'agent-settings.json'))
    return mcp_daemon.main(['--project-root',spec['project'],'--state-root',str(base/'state'),
        '--socket',str(base/'control/control.sock'),'--approval-secret-file',str(base/'control/approval-secret'),
        '--approval-base-url',ui,'--worker-backend','local',
        '--local-workspace-root',str(Path(spec['project'])/'.scidiscovery-runs'),
        '--runtime-summary',str(base/'control/runtime-summary.json')],progression_host_factory=factory)


def start_control(spec):
    base=Path(spec['root']); project=Path(spec['project']); children=[]
    (base/'control/approval-secret').write_text(os.urandom(32).hex());(base/'control/approval-secret').chmod(0o600)
    env=dict(os.environ,SCID_AGENT_SETTINGS_FILE=str(base/'agent-settings.json'),CODEX_HOME=str(base/'codex-home'))
    env.pop('PYTHONPATH',None)
    ui_log=(base/'evidence/ui.log').open('wb',buffering=0)
    children.append(subprocess.Popen([spec['python'],'-I','-m','scidiscovery.artifact_agent.interfaces.cli',
        '--project-root',str(project),'--state-root',str(base/'state'),
        '--approval-secret-file',str(base/'control/approval-secret'),'serve-approval-ui',
        '--port','0','--worker-backend','local','--local-workspace-root',str(project/'.scidiscovery-runs')],env=env,stdout=ui_log,stderr=ui_log))
    url=None; until=time.monotonic()+20
    while not url and time.monotonic()<until:
        if children[0].poll() is not None: raise RuntimeError('management_ui_exited')
        for line in (base/'evidence/ui.log').read_text().splitlines():
            try: url=json.loads(line).get('approval_ui') or url
            except ValueError: pass
        time.sleep(.1)
    if not url: raise RuntimeError('management_ui_start_timeout')
    log=(base/'evidence/daemon.log').open('wb',buffering=0)
    children.append(subprocess.Popen([spec['python'],'-I',str(Path(__file__).resolve()),'_daemon',
        '--spec',str(base/'spec.json'),'--ui-url',url],env=env,stdout=log,stderr=log))
    until=time.monotonic()+20
    while not (base/'control/control.sock').exists():
        if any(p.poll() is not None for p in children) or time.monotonic()>until:
            raise RuntimeError('control_start_timeout')
        time.sleep(.1)
    ui_log.close();log.close()
    return children,url


def verify_account(connection):
    account=connection.rpc('account/read',{'refreshToken':False}).get('account')
    if not isinstance(account,dict): raise RuntimeError('fresh_account_not_authenticated')
    cursor=None; found=False
    for _ in range(10):
        page=connection.rpc('model/list',{'limit':50,'cursor':cursor})
        found |= any(row.get('model')==MODEL or row.get('id')==MODEL for row in page['data'])
        cursor=page.get('nextCursor')
        if not cursor: break
    if cursor or not found: raise RuntimeError('exact_trial_model_unavailable')
    return {'authenticated':True,'exact_model_listed':MODEL,'reasoning_effort':'high','runtime_execution':'not_yet_verified'}


def science_prompt(spec):
    return regular(Path(spec['project'])/'instruction.md').decode()+(
        f'\nFrozen trial profile for Root, Workers and native helpers: {MODEL}/high. '
        'Use fresh helper context and do not substitute another model or effort; stop if unavailable. '
        'Complete the public task using exp. Save the audited final submission in /submission. '
        'Public paths: /instruction.md, /opt/exp, /workspace, /submission. '
        'All native network is disabled. Do not access any private or hidden material.')


class PilotManagement:
    """Task opt-in uses the same local forms, CSRF and frozen UI confirmation."""
    def __init__(self,url):
        self.url=urlsplit(url)
        if (self.url.scheme!='http' or self.url.hostname not in {'127.0.0.1','localhost','::1'}
                or self.url.username or self.url.password or not self.url.path.startswith('/sessions/')):
            raise RuntimeError('local_session_management_url_required')
        self.capability=parse_qs(self.url.query).get('capability',[None])[0]
        if not self.capability:raise RuntimeError('management_capability_missing')
        self.origin='http://'+self.url.netloc
        self.path=self.url.path+'?'+self.url.query
    def request(self,path,form=None):
        connection=http.client.HTTPConnection(self.url.hostname,self.url.port,timeout=10)
        try:
            headers={'Origin':self.origin} if form is not None else {}
            if form is not None:headers['Content-Type']='application/x-www-form-urlencoded'
            connection.request('POST' if form is not None else 'GET',path,
                body=urlencode(form) if form is not None else None,headers=headers)
            response=connection.getresponse();body=response.read(2*1024*1024+1)
            if response.status!=(303 if form is not None else 200) or len(body)>2*1024*1024:
                raise RuntimeError('management_form_rejected_or_unconfirmed')
            return body.decode()
        finally:connection.close()
    def fields(self,command=None):
        page=self.request(self.path)
        if command:
            forms=re.findall(r'<form\b[^>]*>(.*?)</form>',page,re.S)
            forms=[form for form in forms if f"name='command' value='{command}'" in form]
            if len(forms)!=1:raise RuntimeError('exact_management_confirmation_form_missing')
            page=forms[0]
        fields={name:html.unescape(value) for name,value in
            re.findall(r"<input\b[^>]*name='([^']+)'[^>]*value='([^']*)'",page)}
        if not fields.get('csrf'):raise RuntimeError('management_csrf_missing')
        return fields
    def create(self,name):
        fields=self.fields()
        self.request('/instances/create',{'csrf':fields['csrf'],'capability':self.capability,
            'name':name,'title':'Covshift paired comparison','objective':OBJECTIVE})
    def authorize(self):
        fields=self.fields('pause')
        self.request('/instances/progression',{'csrf':fields['csrf'],'capability':self.capability,'command':'pause'})
        fields=self.fields('authorize_loop')
        self.request('/instances/progression',{'csrf':fields['csrf'],'capability':self.capability,
            'command':'authorize_loop','instance_id':fields['instance_id'],
            'confirmation_binding':fields['confirmation_binding'],'confirm_loop_budget':'yes','objective_name':OBJECTIVE})


def arm_action(spec,action):
    """Paid activation exists only in run; no automatic retries or recovery."""
    budget=arm_limits(spec);tokens=budget['all_role_tokens'];wall=budget['trial_wall_seconds']
    base=Path(spec['root']); meter=Meter(tokens=tokens,wall_seconds=wall); children=[]; host=None;listener=None
    result={'status':'fail','action':action,'arm':spec['arm'],'turns_requested':0,
        'limits':budget,
        'active_goal_requested':False,'science_started':False,'actual_worker_helper_isolation':'not_verified',
        'qualification':'fresh Root and alias precheck only; paid synthetic role qualification not run',
        'scoring':'not_run','launch_ready':False}
    try:
        import scidiscovery.artifact_agent.interfaces.mcp_daemon as installed_daemon
        prefix=Path(spec['python']).parent.parent.resolve()
        if (not Path(installed_daemon.__file__).resolve().is_relative_to(prefix)
                or 'progression_host_factory' not in inspect.signature(installed_daemon.main).parameters):
            raise RuntimeError('installed_launcher_adapter_missing')
        if sha(base/'agent-settings.json')!=spec['settings_sha256']: raise RuntimeError('frozen_agent_settings_changed')
        if sha(Path(spec['native']))!=spec['native_sha256']: raise RuntimeError('native_binary_changed')
        if native_runtime(spec['native'])!=spec.get('code_mode_host'):
            raise RuntimeError('code_mode_runtime_changed_or_unfrozen')
        for name,digest in spec['public_sha256'].items():
            if sha(Path(spec['project'])/name)!=digest: raise RuntimeError('public_input_changed')
        if (base/'model-submission-started').exists(): raise RuntimeError('trial_not_replayable')
        if spec['arm']=='scidiscovery': children,ui=start_control(spec)
        result['phase']='fresh_root_start'; host=launch_root(spec,meter)
        result['identity']={'thread_id':host.identity.thread_id,'session_id':host.identity.session_id}
        result['phase']='alias_native_canary'
        if not all(Path(spec['root'],p).is_file() for p in ('control/private-canary.txt','codex-home/auth-canary.json','codex-home/sessions/history-canary')):
            raise RuntimeError('synthetic_private_host_positive_missing')
        # Actual same launcher path. No paid turns, no real private files.
        listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(2)
        with socket.create_connection(listener.getsockname(),timeout=1):
            peer,_=listener.accept();peer.close()
        code=canary_code({**spec,'canary_port':listener.getsockname()[1]})
        reply=host.connection.rpc('command/exec',{'command':[spec['task_python'],'-I','-c',code],
            'cwd':spec['project'],'permissionProfile':NAME,'timeoutMs':10000,'outputBytesCap':4096})
        result['command_exit']=reply.get('exitCode');result['command_stderr']=reply.get('stderr','')[:2048]
        checks=json.loads(reply.get('stdout','{}')) if reply.get('exitCode')==0 else {}
        result['checks']=checks
        if set(checks)!=set(CANARY_CHECKS) or not all(v is True for v in checks.values()):
            raise RuntimeError('task_alias_canary_failed')
        for path in ('workspace','runs','submission'):
            (Path(spec['project'])/path/'canary').unlink()
        if spec['arm']=='scidiscovery':
            host.verify_tools_and_session(approval_base_url=ui)
            current=public_call(host,'instance_current',{})
            result['management_url']=current['management_url']
            if current.get('state')!='unbound': raise RuntimeError('preflight_instance_not_fresh')
        if action=='preflight':
            if spec['arm']=='native_goal':
                host.connection.rpc('thread/goal/set',{'threadId':host.identity.thread_id,'objective':'Synthetic paused preflight','status':'paused','tokenBudget':tokens})
                goal=host.connection.rpc('thread/goal/get',{'threadId':host.identity.thread_id}).get('goal')
                if not isinstance(goal,dict) or goal.get('status')!='paused' or goal.get('tokensUsed')!=0 or goal.get('tokenBudget')!=tokens:
                    raise RuntimeError('paused_goal_budget_mismatch')
                host.connection.rpc('thread/goal/clear',{'threadId':host.identity.thread_id})
            result.update(status='pass',qualification='fresh Root + exact aliases; no role spawn or accounting qualification')
            return result
        result['phase']='account_and_model'; result['account']=verify_account(host.connection)
        text=science_prompt(spec)
        result['science_prompt_sha256']=hashlib.sha256(text.encode()).hexdigest()
        if spec['arm']=='native_goal':
            result['phase']='scientific_native_goal'
            result['scientific_identity']={'thread_id':host.identity.thread_id,'session_id':host.identity.session_id}
            goal='Complete the public task in /instruction.md using exp. Save the audited final submission in /submission. Do not access any private or hidden material.'
            host.connection.rpc('thread/goal/set',{'threadId':host.identity.thread_id,'objective':goal,'status':'paused','tokenBudget':tokens})
            meter.activate();(base/'model-submission-started').touch(exist_ok=False)
            meter.turns_requested+=1;meter.scientific_turns_requested+=1
            host.start_turn(text)
            result['science_started']=True
            host.connection.rpc('thread/goal/set',{'threadId':host.identity.thread_id,'status':'active'})
            result['active_goal_requested']=True
            while True:
                host.connection.poll(.2); meter.check(); host.guard_resources()
                goal=host.connection.rpc('thread/goal/get',{'threadId':host.identity.thread_id}).get('goal')
                if not isinstance(goal,dict): raise RuntimeError('native_goal_disappeared')
                result['native_goal']={k:goal.get(k) for k in ('status','tokensUsed','timeUsedSeconds','tokenBudget')}
                if goal['status'] in ('complete','usageLimited','budgetLimited','blocked','paused'):
                    result['stop_reason']='native_goal_'+goal['status'];break
        else:
            management=None
            authorization=spec.get('management_authorization')
            if authorization is not None:
                if (authorization.get('source')!='explicit_user_instruction' or not authorization.get('text')
                        or authorization.get('limits')!=budget):
                    raise RuntimeError('explicit_management_authorization_mismatch')
                management=PilotManagement(current['management_url'])
                name='covshift.pilot.'+os.urandom(8).hex()
                result['management_authorization']=authorization
                result['created_instance_name']=name
                management.create(name)
            else:
                print('Select/create an instance only through this management page: '+current['management_url'],flush=True)
            until=time.monotonic()+spec.get('human_wait_seconds',1800)
            while current.get('state')=='unbound' and time.monotonic()<until:
                host.connection.poll(.2);current=public_call(host,'instance_current',{});time.sleep(.5)
            if current.get('state')!='active': raise RuntimeError('user_instance_not_selected')
            if management and current.get('name')!=name:raise RuntimeError('created_instance_binding_mismatch')
            existing=public_call(host,'run_list',{'limit':1})
            if existing.get('runs') or existing.get('continuation') or existing.get('next_before'):
                raise RuntimeError('pilot_requires_fresh_instance; keep_existing_records')
            public_call(host,'artifact_ingest_text',{'name':OBJECTIVE,'text':text,'on_conflict':'reject'})
            if management:
                public_call(host,'artifact_ingest_text',{'name':'covshift.pilot.management.authorization',
                    'text':authorization['text'],'on_conflict':'reject'})
                management.authorize()
            else:
                print(f'In the same management page pause interactive scheduling, then authorize the new loop for {OBJECTIVE} ({wall}s / {tokens} total tokens).',flush=True)
            scheduling=public_call(host,'progression_status',{})
            while time.monotonic()<until:
                loop=scheduling.get('loop') or {}
                if loop.get('managed') and loop.get('authority')=='explicit_management_ui_budget_confirmation':break
                host.connection.poll(.2);time.sleep(.5);scheduling=public_call(host,'progression_status',{})
            loop=scheduling.get('loop') or {}
            if (loop.get('authority')!='explicit_management_ui_budget_confirmation'
                    or scheduling.get('objective_name')!=OBJECTIVE
                    or loop.get('limits',{}).get('max_tokens')!=tokens
                    or loop['limits'].get('max_elapsed_seconds')!=wall):
                raise RuntimeError('actual_loop_authorization_mismatch')
            confirm_loop(spec,current,scheduling,OBJECTIVE)
            result['authorized_loop_id']=loop['id']
            result['phase']='scientific_background_loop'
            meter.activate();(base/'model-submission-started').touch(exist_ok=False)
            public_call(host,'progression_command',{'command':'start','mode':'background','objective_name':OBJECTIVE})
            result['science_started']=True
            while True:
                host.connection.poll(.2);meter.check()
                scheduling=public_call(host,'progression_status',{})
                current_loop=scheduling.get('loop') or {}
                if current_loop.get('id')!=loop['id']: raise RuntimeError('authorized_loop_changed')
                result['combined_usage_coverage']=reconcile_control(meter,control_usage(spec,loop['id'],current))
                budget=scheduling.get('budget',{})
                result['control_budget']=budget
                if type(budget.get('observed_tokens')) is int and budget['observed_tokens']>=tokens:
                    raise RuntimeError('observed_control_token_limit')
                if scheduling.get('state') in ('stopped','paused','intervention_required'):
                    result['stop_reason']='progression_'+scheduling['state'];break
                time.sleep(.5)
        result['status']='stopped_not_scored'
    except Exception as exc:
        result['reason']=getattr(exc,'code',str(exc));result['exception']=type(exc).__name__
    finally:
        # Close each PID namespace before submission handoff. The outer supervisor
        # also terminates observed descendants; no detached command is trusted.
        if listener:listener.close()
        if host:
            try: host.close()
            except Exception as exc: result['close_error']=type(exc).__name__;result['status']='fail'
        for process in children:
            if process.poll() is None: process.terminate()
        for process in children:
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill();process.wait()
        control_tokens=(result.get('control_budget') or {}).get('observed_tokens')
        observed=max(meter.total(),control_tokens if type(control_tokens) is int else 0)
        coverage=result.get('combined_usage_coverage')
        if coverage and coverage.get('pending_attribution_threads'):
            coverage.update(coverage='partial',attribution='unresolved_at_stop')
        result['observed_thread_tokens']=meter.total()
        result['observed_total_tokens']=observed
        result['observed_token_overrun']=max(0,observed-tokens)
        result['usage_records']=list(meter.records.values())
        result['turns_requested']=meter.turns_requested  # Direct frontend Root turn/start attempts.
        result['scientific_turns_requested']=meter.scientific_turns_requested
        result['observed_all_role_turns']=len(meter.observed_turns)
        result['trial_started']=meter.deadline is not None
        result['phase_wall_seconds']=0 if meter.deadline is None else round(time.monotonic()-(meter.deadline-wall),3)
        write(base/(action+'-result.json'),result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','preflight','run','_daemon'))
    parser.add_argument('--launch',type=Path);parser.add_argument('--output',type=Path)
    parser.add_argument('--native',type=Path);parser.add_argument('--spec',type=Path)
    parser.add_argument('--auth-file',type=Path);parser.add_argument('--provider-config',type=Path)
    parser.add_argument('--native-goal-tokens',type=int,default=TOKENS)
    parser.add_argument('--native-goal-wall-seconds',type=int,default=WALL)
    parser.add_argument('--scidiscovery-tokens',type=int,default=TOKENS)
    parser.add_argument('--scidiscovery-wall-seconds',type=int,default=WALL)
    parser.add_argument('--resource-config',type=Path)
    parser.add_argument('--human-wait-seconds',type=int,default=1800)
    parser.add_argument('--auto-manage-instance',action='store_true')
    parser.add_argument('--management-authorization-file',type=Path)
    parser.add_argument('--ui-url');parser.add_argument('--_lease-fd',type=int,help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args._lease_fd is not None:
        os.close(args._lease_fd)  # Before any task/native code; supervisor retains lease.
        os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
        if args.action=='prepare':
            prepare(args.launch,args.output,args.native,args.auth_file,args.provider_config,
                native_goal_tokens=args.native_goal_tokens,native_goal_wall_seconds=args.native_goal_wall_seconds,
                scidiscovery_tokens=args.scidiscovery_tokens,scidiscovery_wall_seconds=args.scidiscovery_wall_seconds,resource_config=args.resource_config,human_wait_seconds=args.human_wait_seconds,
                auto_manage_instance=args.auto_manage_instance,management_authorization_file=args.management_authorization_file)
            return 0
        spec=json.loads(regular(args.spec))
        if args.action=='_daemon': return daemon(spec,args.ui_url)
        result=arm_action(spec,args.action)
        return 0 if result['status'] in ('pass','stopped_not_scored') else 1
    if args.action=='_daemon': return daemon(json.loads(regular(args.spec)),args.ui_url)
    if args.action=='prepare':
        if not args.launch or not args.output or not args.native: parser.error('prepare needs --launch --output --native')
        candidate=json.loads(regular(args.launch))['candidate']
        evidence=args.output.with_name(args.output.name+'-supervision')
    else:
        if not args.spec: parser.error('preflight/run needs --spec')
        spec=json.loads(regular(args.spec));candidate=spec['candidate']
        evidence=Path(spec['root'])/(args.action+'-supervision')
    if evidence.exists(): raise RuntimeError('fresh_supervision_required; no uncertain replay')
    metadata=json.loads(regular(Path(candidate)/'candidate.json'))
    limits=json.loads(guard.DEFAULT_CONFIG.read_text())['limits']
    if args.action!='prepare': limits=resource_limits(spec)[0]
    if args.action=='run': limits={**limits,'timeout_seconds':300+arm_limits(spec)['trial_wall_seconds']+(spec.get('human_wait_seconds',1800) if spec['arm']=='scidiscovery' else 0)}
    env=dict(os.environ);env.pop('PYTHONPATH',None);env['PYTHONNOUSERSITE']='1'
    env['PYTHONDONTWRITEBYTECODE']='1'
    if args.action!='prepare':
        env['CODEX_HOME']=str(Path(spec['root'])/'codex-home')
        env['SCID_AGENT_SETTINGS_FILE']=str(Path(spec['root'])/'agent-settings.json')
    with guard.serial_lock() as lease:
        evidence.mkdir(mode=0o700)
        command=[metadata['python'],'-I',str(Path(__file__).resolve()),*sys.argv[1:],'--_lease-fd',str(lease.fileno())]
        write(evidence/'command.json',{'command':command,'limits':limits,'paid_activation_requested':args.action=='run'})
        resource=guard.run_one(command,env,limits,evidence,lease.fileno());write(evidence/'resource.json',resource)
    if args.action=='run':
        # run_one has killed its observed owned tree before this host-only read.
        files={}
        for name in ('submitted_model.pkl','submitted.json'):
            entry=Path(spec['project'])/'runs'/name
            if not entry.exists() and not entry.is_symlink():continue
            files[name]={'size_bytes':entry.lstat().st_size,'sha256':sha(entry),'origin':str(entry)}
        write(evidence/'submission-handoff.json',{'files':files,'pickle_loaded':False,'scoring':'not_run',
            'supervisor_finished':True,'qualification':'regular files and hashes only; inference/grader adapter still required'})
    print(json.dumps({'resource':resource,'evidence':str(evidence)}),flush=True)
    return 0 if resource['returncode']==0 and resource['stop_reason']=='exited' else 1


if __name__=='__main__': raise SystemExit(main())
