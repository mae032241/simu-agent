"""Real installed-package smoke and exact production contract comparison."""
import hashlib,json,sys,tempfile,tomllib
from pathlib import Path
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.operations.tooling import operation_tool_contracts,operation_worker_tool_names
from scidiscovery.artifact_agent.interfaces.mcp_root import root_tools_for_backend
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.platforms.codex import initialize,validate_installation_profile
import scidiscovery
assert Path(scidiscovery.__file__).is_relative_to(Path(sys.prefix)),scidiscovery.__file__
evidence=Path(sys.argv[1]);before=json.loads((evidence/'CONTRACTS_BEFORE.json').read_text())
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
catalog=compile_installed_catalog();snapshot={'catalog_digest':catalog.digest(),'operations':{},'root_tools':{}}
for name in sorted(catalog.operation_ids()):
 operation=catalog.operation(name);v={'digest':operation.digest,'spec_digest':digest(operation.spec.model_dump(mode='json'))}
 if operation.spec.executor.kind=='agent':v['worker_tools']={k:digest(v) for k,v in operation_tool_contracts(operation,operation_worker_tool_names(operation)).items()}
 snapshot['operations'][name]=v
assert snapshot['operations']==before['operations'],'scientific or Worker contract drift'
for backend in ('local','hardened'):
 snapshot['root_tools'][backend]={t.name:digest(t.schema()) for t in root_tools_for_backend(backend)}
 changed={k for k in snapshot['root_tools'][backend] if snapshot['root_tools'][backend][k]!=before['root_tools'][backend].get(k)}
 assert changed=={'operation_preflight','operation_invoke'},changed
(evidence/'CONTRACTS_AFTER.json').write_text(json.dumps(snapshot,indent=2)+'\n')
with tempfile.TemporaryDirectory(prefix='scid-settings-install-smoke-') as d:
 root=Path(d);project=root/'project';project.mkdir();config=root/'agent-settings.json'
 config.write_text(json.dumps({'defaults':{'narrative_language':'zh-CN','model':'gpt-5.6-luna','reasoning_effort':'low'}}))
 runtime=open_runtime(project_root=project,state_root=root/'state',agent_settings_file=config)
 assert runtime.runs.agent_settings.defaults.model=='gpt-5.6-luna'
 initialize(project_root=project,control_socket=root/'unused.sock',state_root=root/'state',local_workspace_root=project/'.scidiscovery-runs',python_executable=sys.executable,operation_catalog=catalog)
 roles=list((project/'.codex/agents').glob('*.toml'))
 for role in roles:
  parsed=tomllib.loads(role.read_text());assert 'model' not in parsed and 'model_reasoning_effort' not in parsed
 value={'operations_unchanged':len(catalog.operation_ids()),'worker_contracts_unchanged':True,'changed_root_schemas':['operation_preflight','operation_invoke'],
        'generated_dynamic_roles':len(roles),'installed_settings_loaded':True,'import_source':scidiscovery.__file__}
 (evidence/'INSTALLED_PROBE.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value))
