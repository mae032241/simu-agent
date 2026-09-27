import os
os.environ.update(PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
import resource
resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024))
resource.setrlimit(resource.RLIMIT_CPU,(20,20))
import json,time
from pathlib import Path
from types import SimpleNamespace
from pydantic import ValidationError,TypeAdapter
from scidiscovery.artifact_agent.schema.research_cycle import ScientificReview
from scidiscovery.artifact_agent.schema.validation import HypothesisAssessment
from scidiscovery.operation_contract import validation_diagnostics
from curve_score.schema import CurveComparison,CurveOperatorSpec
from curve_figure_evidence.figure_digitization_contract import FigureDigitizationRequest
from tcad_artifact.device_parameters import ScientificDecimal
from tcad_artifact.plugin import _parameter_inputs
from tcad_artifact.project_packager import _validate_approved_parameter_bindings,_safe_relative_path

rows=[]
def probe(name,func):
    try:func();rows.append({'name':name,'accepted':True})
    except Exception as e:
        d={'name':name,'accepted':False,'exception':type(e).__name__,'message':str(e)[:2000]}
        if isinstance(e,ValidationError):
            d['raw_errors']=[{'path':list(x['loc']),'type':x['type'],'message':x['msg']} for x in e.errors()]
            d['public_diagnostics']=validation_diagnostics(e,schema={},phase='output_payload',action='submit')
        rows.append(d)
def valid(model,obj):return model.model_validate_json(json.dumps(obj),strict=True)
review={'review_target':'experiment_portfolio','verdict':'revise','summary':'Synthetic bounded review'}
probe('review_baseline',lambda:valid(ScientificReview,review))
probe('duplicate_reference_only',lambda:valid(ScientificReview,{**review,'evidence_item_keys':['item.a','item.a']}))
probe('same_source_two_locators',lambda:valid(ScientificReview,{**review,'evidence':[
    {'source_key':'plan','source_type':'frozen_input','locator':'plan#/proposals/0'},
    {'source_key':'plan','source_type':'frozen_input','locator':'plan#/proposals/1'}]}))
comparison={'comparison_key':'compare.a','reference_series':'ref','candidate_series':'candidate',
    'domain':{'start':0.0,'stop':1.0,'unit':'cm'},'interpolation':'linear_y',
    'operators':[{'operator_key':'crossing','kind':'crossing_shift','level':0.5}]}
probe('crossing_without_profile',lambda:valid(CurveComparison,comparison))
probe('same_crossing_labeled_smooth',lambda:valid(CurveComparison,{**comparison,
    'purpose':'exploratory_diagnostic','gate_scope':'diagnostic_only','metric_profile':'smooth_curve'}))
probe('missing_required_crossing_level',lambda:valid(CurveOperatorSpec,{'operator_key':'crossing','kind':'crossing_shift'}))
figure={'schema_version':'scidiscovery.curve-figure-digitization-request.v2',
    'request_status':'unresolved','unresolved_reasons':['Y-axis unit not yet identified'],
    'figure_key':'figure.a','panel_key':'panel.a','figure':'Synthetic image','citation':'Synthetic source',
    'source':{'source_kind':'raster_image','media_type':'image/png','source_sha256':'0'*64,
    'recovered_image_sha256':'0'*64,'width':100,'height':100,'recovery_tool':'Pillow','recovery_tool_version':'probe'}}
probe('unresolved_without_known_geometry',lambda:valid(FigureDigitizationRequest,figure))
probe('unresolved_preserving_known_geometry',lambda:valid(FigureDigitizationRequest,{**figure,'plot_bbox':[10,10,90,90]}))
assessment={'hypothesis_key':'h.a','outcome':'invalid_study','evidence_keys':['e.a'],
    'falsifiers_triggered':['f.a'],'rationale':'Observed falsifier pattern, but numerical evidence invalidates the study.'}
probe('falsifier_with_invalid_study',lambda:valid(HypothesisAssessment,assessment))
probe('exact_decimal_ordinary_spelling',lambda:TypeAdapter(ScientificDecimal).validate_json('"1.0"'))
probe('exact_decimal_scientific_spelling',lambda:TypeAdapter(ScientificDecimal).validate_json('"1e+0"'))
probe('path_escape',lambda:_safe_relative_path('../outside.cmd'))
parameters={'parameter_set_key':'params.a','requirement_set_key':'requirements.a','title':'Synthetic parameters','objective':'Synthetic objective','claims':[]}
coverage={'requirement_set_key':'requirements.a','parameter_set_key':'params.a','source_catalog_key':'catalog.a','status':'fail',
    'items':[{'parameter_key':'later.a','status':'missing','canonical_unit':'cm','independent_source_count':0,'summary':'Later-stage parameter missing'}],
    'confirmed_count':0,'review_count':0,'blocking_count':1}
sources={'device_parameters':json.dumps(parameters).encode(),'parameter_coverage':json.dumps(coverage).encode()}
probe('parameter_input_hook_accepts_failed_coverage',lambda:_parameter_inputs(sources))
probe('author_context_helper_rejects_unused_failed_coverage',lambda:_validate_approved_parameter_bindings(SimpleNamespace(parameter_bindings=()),sources))
output={'scope':'Isolated installed model/helper probes; no ResearchInstance, no preflight approval, no Run or solver. Parameter pair probe is not a complete admission test.',
    'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'probes':rows}
Path('/tmp/scid-validation-microprobes.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'peak_rss_kib':output['peak_rss_kib'],'results':[{'name':x['name'],'accepted':x['accepted'],'error':x.get('raw_errors',[{}])[0].get('message',x.get('message'))} for x in rows]},ensure_ascii=False))
