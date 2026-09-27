import json,sys,tomllib
from pathlib import Path
from types import SimpleNamespace
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.artifact_agent.service.local_workspace import LocalTrustedBackend
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_root import ROOT_TOOLS
from scidiscovery.artifact_agent.interfaces.mcp_worker_protocol import LIFECYCLE_WORKER_TOOLS
from scidiscovery.operations.tooling import operation_agent_type,operation_worker_server_name
from scidiscovery.platforms.codex import _local_native_tool_instruction
from jsonschema import Draft202012Validator

root=Path('/home/da/project/ai4s/tcad/git_release/scidiscovery-agent')
out=root/'123/scidiscovery-e5.2/docs/plans/evidence/operation-tool-contract-coherence'
catalog=compile_installed_catalog()
config=tomllib.loads((root/'.codex/config.toml').read_text())
wire={}; checks=[]
for oid in catalog.operation_ids():
    compiled=catalog.operation(oid)
    if compiled.spec.executor.kind!='agent':continue
    profile=tomllib.loads((root/'.codex/agents'/f'{operation_agent_type(compiled)}.toml').read_text())
    expected=LocalTrustedBackend.assignment_tool_names(compiled)
    server=operation_worker_server_name(compiled)
    checks.append({'operation_id':oid,
        'tool_names_match':tuple(profile['mcp_servers'][server]['enabled_tools'])==expected,
        'backend_instruction_present':_local_native_tool_instruction(compiled).strip() in profile['developer_instructions'],
        'inherited_tool_names_match':tuple(config['mcp_servers'][server]['enabled_tools'])==expected})
    if oid not in {'tcad.result.analyze.v1','science.result.diagnose.v1','science.figure.request.prepare.v1'}:continue
    # No runtime, Run, Worker claim, control store, or registered tool is opened/called.
    # Production router uses only a catalog/backend descriptor during initialization.
    runs=SimpleNamespace(operation_catalog=catalog,backend=LocalTrustedBackend)
    router=LocalWorkerMCPRouter(runs,operation_id=oid,operation_digest=compiled.digest)
    response=MCPRouter(router,name='read-only-metadata-audit').handle({'jsonrpc':'2.0','id':1,'method':'tools/list'})
    wire[oid]=response

for tool in (*ROOT_TOOLS,*LIFECYCLE_WORKER_TOOLS):Draft202012Validator.check_schema(tool.schema()['inputSchema'])
result={'import_root':sys.modules['scidiscovery'].__path__[0],
    'catalog_digest':catalog.digest(),'root_schema_count':len(ROOT_TOOLS),'lifecycle_schema_count':len(LIFECYCLE_WORKER_TOOLS),
    'checks':checks,'wire':wire}
(out/'PROJECTION_INSTALLED_MCP_METADATA.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'import_root':result['import_root'],'catalog_digest':catalog.digest(),
    'agent_profiles':len(checks),'profile_mismatches':[x for x in checks if not all(x[k] for k in ('tool_names_match','backend_instruction_present','inherited_tool_names_match'))],
    'root_schemas':len(ROOT_TOOLS),'lifecycle_schemas':len(LIFECYCLE_WORKER_TOOLS),
    'wire_request_fields':{oid:{t['name']:t['inputSchema']['properties']['request'] for t in response['result']['tools'] if 'request' in t['inputSchema']['properties']} for oid,response in wire.items()}},indent=2))
