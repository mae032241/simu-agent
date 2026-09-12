import json
from pathlib import Path
from types import SimpleNamespace
from copy import deepcopy
from pydantic import ValidationError
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from tcad_artifact.plugin import PLUGIN as TCAD_PLUGIN
from curve_figure_evidence.plugin import PLUGIN as FIGURE_PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.tooling import operation_local_worker_tools
from scidiscovery.artifact_agent.service.run_assignment import result_schema_json
from scidiscovery.artifact_agent.schema.layered_diagnosis import AnalysisSourceReference, CalculationRecord
from scidiscovery.operation_contract import validation_diagnostics
from scidiscovery.artifact_agent.service.runs import RunService
from scidiscovery.artifact_agent.interfaces.mcp_root import OperationCallInput
from scidiscovery.operations.invoke import preflight_operation
from tcad_artifact.result_analysis import TCADScoreInput
from tests.operations.test_tcad_result_analysis import raw_request

out=Path('docs/plans/evidence/operation-tool-contract-coherence')
catalog=compile_catalog((CORE_PLUGIN,GENERAL_PLUGIN,CURVE_PLUGIN,TCAD_PLUGIN,FIGURE_PLUGIN))
result={'catalog_digest':catalog.digest(),'operation_count':len(catalog.operation_ids())}

def check_refs(schema):
    base='https://audit.invalid/root.json'
    resource=Resource.from_contents(schema,default_specification=DRAFT202012)
    registry=Registry().with_resource(base,resource).crawl()
    errors=[]; count=0
    def walk(node,resolver,path):
        nonlocal count
        if isinstance(node,dict):
            resolver=resolver.in_subresource(Resource.from_contents(node,default_specification=DRAFT202012))
            if '$ref' in node:
                count+=1
                try:resolver.lookup(node['$ref'])
                except Exception as error:errors.append({'path':path,'ref':node['$ref'],'error':type(error).__name__})
            for k,v in node.items():
                if k in {'default','examples'} or k.startswith('x-scidiscovery-'):continue
                if isinstance(v,(dict,list)):walk(v,resolver,path+'/'+k)
        elif isinstance(node,list):
            for i,v in enumerate(node):walk(v,resolver,path+'/'+str(i))
    walk(schema,registry.resolver(base),'')
    return {'ref_count':count,'unresolved':errors}

schemas=[]; tools={}; port_views=[]
for oid in catalog.operation_ids():
    compiled=catalog.operation(oid)
    view=next(x for x in catalog.scheduler_projection() if x.operation_id==oid)
    for p,v in zip(compiled.spec.inputs,view.inputs):
        if (p.name,p.schema_id,p.min_items,p.max_items,p.required_non_null_fields)!=(v.name,v.schema_id,v.min_items,v.max_items,v.required_non_null_fields):
            port_views.append({'operation_id':oid,'port':p.name})
    if compiled.spec.executor.kind!='agent':continue
    schema=json.loads(result_schema_json(compiled))
    Draft202012Validator.check_schema(schema)
    schemas.append({'operation_id':oid,'payload_id':schema['properties']['payload'].get('$id'),**check_refs(schema)})
    for tool in operation_local_worker_tools(compiled):
        if tool.name in tools:continue
        s=tool.schema()['inputSchema']
        Draft202012Validator.check_schema(s)
        tools[tool.name]={'bytes':len(json.dumps(s)),'defs':len(s.get('$defs',{})),**check_refs(s)}
result['worker_output_schemas']=schemas
result['worker_tool_schemas']=tools
result['catalog_port_mismatches']=port_views
result['diagnostic_probes']=[]
for model,raw in [
    (AnalysisSourceReference,{'source_key':'s','input_alias':'input','experiment_key':'e'}),
    (CalculationRecord,{'record_key':'r','input_digests':{},'request':{},'algorithm_version':'v1','status':'computed'}),
]:
    schema=model.model_json_schema()
    schema_accepts=Draft202012Validator(schema).is_valid(raw)
    try:model.model_validate(raw)
    except ValidationError as error:
        result['diagnostic_probes'].append({'model':model.__name__,'jsonschema_accepts':schema_accepts,
            'owner_error':[x['msg'] for x in error.errors(include_input=False)],
            'projected':validation_diagnostics(error,schema=schema,phase='output_payload',action='submit')})

request=raw_request()
request['comparison_spec']['comparisons'][0]['evaluation_points']=5000
raw={'record_key':'bounded-probe','request':request}
schema=TCADScoreInput.model_json_schema()
item={'jsonschema_accepts':Draft202012Validator(schema).is_valid(raw),
      'advertised_maximum':schema['$defs']['CurveComparison']['properties']['evaluation_points']['maximum'],
      'submitted_evaluation_points':5000}
try:TCADScoreInput.model_validate_json(json.dumps(raw),strict=True)
except ValidationError as error:
    item.update(owner_error=[x['msg'] for x in error.errors(include_input=False)],
                projected=validation_diagnostics(error,schema=schema))
result['score_bounds_probe']=item

parsed=OperationCallInput.model_validate({'name':'audit','operation_id':'tcad.result.analyze.v1','inputs':[], 'parameters':{'x':1}})
compiled=catalog.operation(parsed.operation_id)
try:preflight_operation(compiled,name='audit',artifacts_by_port={p.name:() for p in compiled.spec.inputs},instruction='audit',parameters=parsed.parameters)
except Exception as error:result['root_parameters_probe']={'dto_accepts':True,'preflight_error':getattr(error,'reason_code',str(error))}
result['timeout_category_projection']=RunService._safe_diagnostic('timeout',repairable=False)
failure=json.loads((out/'P6_ANALYSIS_FIRST_FAILURE.json').read_text())
result['live_timeout_evidence']={k:failure.get(k) for k in ['state','reason','deadline_at','completed_at']}
result['live_timeout_evidence']['failure_diagnostic']=failure['diagnostic_summary']['failure']
(out/'PROJECTION_AUDIT_PROBES.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'catalog_digest':result['catalog_digest'],'operations':result['operation_count'],
    'output_schemas':len(schemas),'bad_output_refs':[x for x in schemas if x['unresolved']],
    'worker_tools':len(tools),'bad_tool_refs':{k:v for k,v in tools.items() if v['unresolved']},
    'port_mismatches':port_views,'diagnostic_probes':result['diagnostic_probes'],
    'score_bounds_probe':item,'root_parameters_probe':result.get('root_parameters_probe'),
    'live_timeout':result['live_timeout_evidence']},ensure_ascii=False,indent=2))
