"""Spawn one generated role in an independent CLI; process-local configuration."""
import json
import os
import sys
import tomllib
from pathlib import Path

base=Path(os.environ.get('SCID_SETTINGS_PROBE_ROOT', '/tmp/scid-execution-settings-p0'))
record=json.loads((base/'fixture.json').read_text())
model, effort=sys.argv[1:3]
controller=base/'controller';controller.mkdir(exist_ok=True)
cli_tmp=base/'cli-tmp';cli_tmp.mkdir(exist_ok=True)
role=record['agent_type']
env=dict(os.environ,CODEX_HOME=str(base/'cli-home'),TMPDIR=str(cli_tmp),MALLOC_ARENA_MAX='2',
    RAYON_NUM_THREADS='1',TOKIO_WORKER_THREADS='1',_RJEM_MALLOC_CONF='narenas:1,dirty_decay_ms:0,muzzy_decay_ms:0',
    MALLOC_CONF='narenas:1,dirty_decay_ms:0,muzzy_decay_ms:0')
binary='/home/da/.nvm/versions/node/v25.2.1/lib/node_modules/@openai/codex/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex'
args=[binary,'exec','--ignore-user-config','--json','--skip-git-repo-check',
    '-C',str(controller),'-m','gpt-5.6-luna','-s','workspace-write',
    '--add-dir',str(base/'fixture/.scidiscovery-runs')]
settings={
    'model_reasoning_effort':'low','features.multi_agent':True,
    'features.multi_agent_v2.enabled':False,'features.multi_agent_v2.hide_spawn_agent_metadata':False,
    'agents.enabled':True,'agents.max_concurrent_threads_per_session':1,
    f'agents.{role}.description':'Complete one controlled CSV observation assignment.',
    f'agents.{role}.config_file':record['profile'],
    'features.shell_tool':True,'features.unified_exec':True,
    'features.shell_snapshot':False,'features.code_mode_host':True,
}
parent=tomllib.loads((base/'fixture/.codex/config.toml').read_text())
server=parent['mcp_servers'][record['server']]
for key,value in server.items():
    if isinstance(value,dict):
        for k,v in value.items():settings[f'mcp_servers.{record["server"]}.{key}.{k}']=v
    else:settings[f'mcp_servers.{record["server"]}.{key}']=value
for key,value in settings.items(): args += ['-c',key+'='+json.dumps(value)]
negative=len(sys.argv)>3 and sys.argv[3]=='negative'
message=(f'Use spawn_agent exactly once with agent_type={role}, model={model}, '
    f'reasoning_effort={effort}, and no parent-history inheritance (fork_context=false or fork_turns=none, whichever the tool declares). '
    'The child message must only be: Complete the already queued assignment for your Operation using its Worker server. '
    'Do not use a default agent, do not inspect files or call Worker tools yourself. '
    'If the requested model conflicts with a fixed role model, report MODEL_OVERRIDE_REJECTED and stop without spawning a fallback. '
    'Otherwise wait for this one child to finish, then close that child if a close tool exists, and reply P0_DISPATCH_DONE. '
    'No other subagents or tools. This is an explicitly authorized, isolated platform dispatch test.')
if negative:
    message = (f'This is an explicitly authorized negative interface test. Call spawn_agent exactly once with agent_type={role}, model={model}, reasoning_effort={effort}, fork_context=false, and message: Complete the already queued assignment for your Operation using its Worker server. The role deliberately fixes a conflicting model. Record the actual tool rejection; do not substitute your own prediction for the tool response. Do not use any fallback model or role, and do not create additional children. If the platform nevertheless creates a child, wait until it finishes and then close it. No assignment is queued; the child must stop after worker_open_assignment reports none. Never call Worker tools yourself. Report only the actual interface outcome.')
args.append(message)
os.dup2(os.open(os.devnull,os.O_RDONLY),0)
os.execve(binary,args,env)
