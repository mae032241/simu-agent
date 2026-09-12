"""Verify the shipped Root/Worker projections without a research instance."""
from pathlib import Path
import tempfile,sys
import scidiscovery.operations.spec as spec_module
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.operation_contract import operation_port_json_schema,operation_input_validation_contract
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter,RootToolFacade
assert Path(spec_module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
catalog=compile_installed_catalog()
with tempfile.TemporaryDirectory() as scratch:
 p=Path(scratch);(p/'project').mkdir()
 runtime=open_runtime(project_root=p/'project',state_root=p/'state',worker_backend='local')
 runtime.runs.operation_catalog=catalog
 root=RootMCPRouter(RootToolFacade(runtime.artifacts,runtime.intake,runs=runtime.runs,
    bindings=runtime.scheduler_bindings,operation_catalog=catalog,
    approvals=runtime.approvals,executions=runtime.executions,instance=None))
 public=root.call_tool('operation_catalog',{'scope':'all'})
 checked=0
 for item in public['operations']:
  op=catalog.operation(item['operation_id'])
  if op.spec.input_validation is None:continue
  expected=operation_input_validation_contract(op)
  assert item['input_validation']==expected
  for output in op.spec.outputs:
   assert operation_port_json_schema(op,output)['x-scidiscovery-input-validation-contract']==expected
  checked+=1
 tools={t['name']:t for t in root.list_tools()}
 for name in ['operation_preflight','operation_invoke']:
  assert 'draft_from' in tools[name]['inputSchema']['properties']
 assert checked>0
 print('installed Root and Worker input contracts agree:',checked,'operations; draft_from declared')
