from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import runpy

import pytest

from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter, WorkerToolError
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.layered_diagnosis import CalculationRecord
from scidiscovery.artifact_agent.service.run_outputs import InputBindingDescriptor, ValidationSources, RunCheckerError
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operation_contract import SemanticRuleViolation
from tcad_artifact.plugin import PLUGIN as TCAD_PLUGIN
from tcad_artifact.project_packager import ExecutionPackage, ProjectExpectedOutput
from tcad_artifact.result_analysis import analysis_context, evaluate_tcad_request

_TCAD = json.loads((Path(__file__).parents[1] / 'fixtures/tcad_analysis_package.json').read_text())
_CURVE = runpy.run_path(str(Path(__file__).with_name('test_m2_curve_analysis_boundary.py')))


def analysis_materials(*, mapped=True, state='succeeded', output_names=('A', 'B'), plan=None):
    plan = plan or _CURVE['_plan']()
    value = deepcopy(_TCAD['project'])
    value['expected_outputs'] = [dict(name=name, relative_path=name+'.plx',
        media_type='application/x-synopsys-plx', max_bytes=32*1024*1024,
        **({'experiment_key': 'implementation_check', 'case_key': 'baseline'} if mapped else {}))
        for name in output_names]
    package = ExecutionPackage.model_validate_json(canonical_json({
        'schema_version': 2, 'project': value, 'review': _TCAD['review'],
        'capability': _TCAD['capability'],
    }), strict=True)
    plx = b'"carrier"\n0 1e10\n0.5 1e11\n1 1e12\n'
    csv = b'depth,carrier,original_group\n0,1e10,g1\n0.5,1e11,g2\n1,1e12,g3\n'
    manifest = dict(started_at=None, completed_at='2026-09-09T00:00:00Z', terminal_state=state,
        exit_code=0 if state == 'succeeded' else 1, error='' if state == 'succeeded' else 'fixture failure',
        outputs=[dict(name=name,relative_path=name+'.plx',media_type='application/x-synopsys-plx',
            sha256=hashlib.sha256(plx).hexdigest(),size_bytes=len(plx)) for name in output_names])
    return plan, package, canonical_json(manifest), plx, csv


def analysis_report(*, alias='runtime_manifest', output_name=None, mapped=False):
    report = _CURVE['_diagnosis']().model_dump(mode='json')
    report['evidence'] = [dict(source_key='raw_evidence', source_type='runtime_output',
        title='Exact fixture result', locator=alias)]
    report['source_references'] = [dict(source_key='raw_evidence',input_alias=alias,
        **({'output_name':output_name} if output_name else {}),
        **({'experiment_key':'implementation_check','case_key':'baseline'} if mapped else {}))]
    for gate in report['gates'].values():
        if isinstance(gate,dict) and gate.get('evidence_keys'):
            gate['evidence_keys'] = ['raw_evidence']
    return report


def raw_request(*, alias='solver_outputs_001'):
    spec = _CURVE['_contract']().comparison_spec.model_dump(mode='json')
    axes = dict(x_axis={'name':'depth','unit':'um','scale':'linear'},
                y_axis={'name':'carrier','unit':'cm^-3','scale':'log10'})
    return dict(comparison_spec=spec, sources=[
        dict(input_alias=alias,format='sprocess_plx',output_name='A',
             experiment_key='implementation_check',case_key='baseline',series_key='candidate',
             role='candidate',dataset_name='carrier',**axes),
        dict(input_alias='reference_material',format='csv',series_key='reference',case_key='baseline',
             role='reference',x_column='depth',y_column='carrier',**axes),
    ])


def analysis_system(tmp_path, *, state='succeeded', mapped=True, bind_names=('A','B'), plan=None):
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN))
    project_root = tmp_path/'project'
    project_root.mkdir()
    runtime = open_runtime(project_root=project_root, state_root=tmp_path/'state', worker_backend='local')
    runtime.runs.operation_catalog = catalog
    instance = runtime.scheduler_bindings.create_instance(name='analysis_fixture',title='TCAD analysis fixture',objective='Test raw result analysis.')
    root = RootMCPRouter(RootToolFacade(runtime.artifacts,runtime.intake,runs=runtime.runs,
        approvals=runtime.approvals,executions=runtime.executions,bindings=runtime.scheduler_bindings,
        instance=instance.instance_id,operation_catalog=catalog))
    artifacts = {}
    def register(name, raw, schema, *, parents=(), media='application/json', output_name=None):
        artifact = runtime.artifacts.register(raw,ArtifactRegistration(kind='fixture',schema_id=schema,
            payload_schema_version=1,media_type=media,creator=runtime.actor,parent_refs=parents,
            labels={'logical_name':output_name} if output_name is not None else {}),idempotency_key=name)
        runtime.scheduler_bindings.bind(instance=instance.instance_id,namespace='artifact',name=name,object_id=artifact.artifact_id)
        artifacts[name] = artifact
        return artifact
    plan, package, manifest, plx, csv = analysis_materials(state=state,mapped=mapped,plan=plan)
    plan_artifact = register('plan',plan.canonical_json(),'scidiscovery.experiment-portfolio.v1')
    package_artifact = register('package',canonical_json(package.model_dump(mode="json")),'tcad.execution-package.v2',parents=(plan_artifact.ref,))
    manifest_artifact = register('manifest',manifest,'opaque',parents=(package_artifact.ref,))
    for name in ('A','B'):
        register('output_'+name,plx,'opaque',parents=manifest_artifact.parent_refs,media='application/x-synopsys-plx',output_name=name)
    register('reference',csv,'opaque',media='text/csv')
    request = dict(name='analysis',operation_id='tcad.result.analyze.v1',instruction='Analyze the bound fixture outputs.',inputs=[
        dict(port='experiment_plan',artifact_names=['plan']),
        dict(port='execution_package',artifact_names=['package']),dict(port='runtime_manifest',artifact_names=['manifest']),
        dict(port='reference_material',artifact_names=['reference']),
        *([dict(port='solver_outputs',artifact_names=['output_'+name for name in bind_names])] if bind_names else []),
    ])
    return catalog,runtime,root,request,artifacts,register


def open_analysis(system):
    catalog,runtime,root,request,_,_ = system
    result = root.call_tool('operation_preflight',request)
    assert result['admissible'] is True,result
    root.call_tool('operation_invoke',request)
    compiled = catalog.operation('tcad.result.analyze.v1')
    worker = LocalWorkerMCPRouter(runtime.runs,operation_id=compiled.spec.operation_id,operation_digest=compiled.digest)
    opened = worker.call_tool('worker_open_assignment',{})
    return worker,opened


def write_analysis(opened,report):
    Path(str(opened['output_directory']),'result.json').write_bytes(canonical_json(dict(
        schema_version=1,handoff=dict(verdict='blocked',summary='Bounded analysis; further work remains.'),payload=report)))




@pytest.mark.parametrize('state',['failed','cancelled'])
def test_failed_execution_zero_outputs_no_score_can_seal(tmp_path,state):
    system = analysis_system(tmp_path,state=state,bind_names=())
    missing_review=deepcopy(system[3]); missing_review['name']='analysis_without_legacy_review'
    missing_review['inputs']=[item for item in missing_review['inputs'] if item['port']!='experiment_review']
    admitted=system[2].call_tool('operation_preflight',missing_review)
    assert admitted['admissible'] is True,admitted
    worker,opened = open_analysis(system)
    write_analysis(opened,analysis_report())
    result=worker.call_tool('worker_submit_result',{})
    assert result['state']=='completed',result


def test_keyed_tcad_scope_rejects_missing_assessment_then_accepts_not_evaluable(tmp_path):
    plan = _CURVE['_compiler_plan']()
    system = analysis_system(tmp_path, state='failed', bind_names=(), plan=plan)
    worker, opened = open_analysis(system)
    report = analysis_report()
    report['study_kind'] = 'scientific'
    write_analysis(opened, report)
    rejected = worker.call_tool('worker_submit_result', {})
    assert rejected['state'] == 'rejected', rejected
    diagnostic = next(item for item in rejected['diagnostics']
                      if 'objective assessment is required' in item['message'])
    assert diagnostic['path'] == '$.payload.objective_assessment'
    assert diagnostic['rule_id'] == 'tcad.result_analysis.context_binding'
    report['objective_assessment'] = {
        'objective_key': plan.objective_key,
        'status': 'not_evaluable',
        'summary': 'The failed execution produced no solver output for the planned objective.',
    }
    write_analysis(opened, report)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'




@pytest.mark.parametrize('explicit_reference', [False, True])
def test_conflicting_citation_sources_repair_without_forbidding_repeated_citations(tmp_path, explicit_reference):
    system = analysis_system(tmp_path)
    worker, opened = open_analysis(system)
    report = analysis_report(alias='solver_outputs_001')
    if not explicit_reference:
        report['source_references'] = []
    report['evidence'] = [dict(source_key='raw_evidence', source_type='runtime_output', title='Exact output', locator=locator)
        for locator in ('solver_outputs_001:row1', 'solver_outputs_002:row2')]
    write_analysis(opened, report)
    reply = worker.call_tool('worker_submit_result', {})
    assert reply['state'] == 'rejected', reply
    assert reply['diagnostics'][0]['path'] == '$.payload.evidence[1].source_key'
    assert 'conflicting source mappings' in reply['diagnostics'][0]['message']
    assert system[1].runs.status(worker._run_id).state == 'running'
    report = json.loads(Path(opened['output_directory'], 'result.json').read_bytes())['payload']
    if explicit_reference:
        # The explicit binding makes a local locator sufficient.
        report['evidence'][1]['locator'] = 'row2'
    else:
        # Control must not persist a guessed mapping for the Agent to undo.
        assert not report['source_references']
        report['evidence'][0]['locator'] = 'solver_outputs_002:row1'
    write_analysis(opened, report)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    sealed = system[2].call_tool('run_status', {'name': 'analysis', "intent": 'full'})['sealed_output']['payload']
    assert sealed['source_references'][0]['output_name'] == ('A' if explicit_reference else 'B')


@pytest.mark.parametrize('source_key, conflicting_locator', [
    ('solver_outputs_001', 'solver_outputs_002:row2'),
    ('raw_evidence', 'reference_material:row2'),
])
def test_source_conflict_does_not_leave_a_control_mapping_to_repair(tmp_path, source_key, conflicting_locator):
    system = analysis_system(tmp_path)
    worker, opened = open_analysis(system)
    report = json.loads(json.dumps(analysis_report(alias='solver_outputs_001')).replace('raw_evidence', source_key))
    report['source_references'] = []
    report['evidence'][0]['locator'] = 'solver_outputs_001:row1'
    report['evidence'].append({**report['evidence'][0], 'locator': conflicting_locator})
    write_analysis(opened, report)
    rejected = worker.call_tool('worker_submit_result', {})
    assert rejected['state'] == 'rejected'
    assert 'conflicting source mappings' in rejected['diagnostics'][0]['message']
    report = json.loads(Path(opened['output_directory'], 'result.json').read_bytes())['payload']
    assert report['source_references'] == []
    report['evidence'][1]['locator'] = 'solver_outputs_001:row2'
    write_analysis(opened, report)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    sealed = system[2].call_tool('run_status', {'name': 'analysis', "intent": 'full'})['sealed_output']['payload']
    assert sealed['source_references'][0]['output_name'] == 'A'




def test_optional_citation_cannot_change_an_exact_bound_alias(tmp_path):
    worker, opened = open_analysis(analysis_system(tmp_path))
    report = json.loads(json.dumps(analysis_report(alias='solver_outputs_001')).replace('raw_evidence', 'solver_outputs_002'))
    report['evidence'][0]['locator'] = 'row1'
    for evidence in (report['evidence'], []):
        report['evidence'] = evidence
        write_analysis(opened, report)
        rejected = worker.call_tool('worker_submit_result', {})
        assert rejected['state'] == 'rejected'
        assert rejected['diagnostics'][0]['path'] == '$.payload.source_references[0].source_key'
    # A local citation name may still use only the optional mapping, without an evidence row.
    report = json.loads(json.dumps(report).replace('solver_outputs_002', 'local_citation'))
    write_analysis(opened, report)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'


def test_legacy_unmapped_output_can_seal_limited_analysis(tmp_path):
    worker,opened=open_analysis(analysis_system(tmp_path,mapped=False,bind_names=('A',)))
    write_analysis(opened,analysis_report(alias='solver_outputs',output_name='A'))
    result=worker.call_tool('worker_submit_result',{})
    assert result['state']=='completed',result



@pytest.mark.parametrize('wrong',['review','manifest','output'])
def test_no_score_preflight_rejects_other_round(tmp_path,wrong):
    catalog,runtime,root,request,artifacts,register=analysis_system(tmp_path)
    request=deepcopy(request)
    if wrong=='review':
        other=register('other_plan',runtime.artifacts.read(artifacts['plan'].ref),'scidiscovery.experiment-portfolio.v1')
        next(item for item in request['inputs'] if item['port']=='experiment_plan')['artifact_names']=['other_plan']
    elif wrong=='manifest':
        register('wrong_manifest',runtime.artifacts.read(artifacts['manifest'].ref),'opaque',parents=(artifacts['plan'].ref,))
        next(item for item in request['inputs'] if item['port']=='runtime_manifest')['artifact_names']=['wrong_manifest']
    else:
        register('wrong_output',runtime.artifacts.read(artifacts['output_A'].ref),'opaque',parents=(artifacts['plan'].ref,),media='application/x-synopsys-plx',output_name='A')
        next(item for item in request['inputs'] if item['port']=='solver_outputs')['artifact_names']=['wrong_output']
    result=root.call_tool('operation_preflight',request)
    assert result['admissible'] is False and result['reason_code']=='guard_rejected',result


def test_same_bytes_correct_names_allow_reversed_bindings(tmp_path):
    worker,opened=open_analysis(analysis_system(tmp_path,bind_names=('B','A')))
    report=analysis_report(alias='solver_outputs_001',output_name='B',mapped=True)
    report['evidence'].append(dict(source_key='second',source_type='runtime_output',title='Second exact output',locator='solver_outputs_002'))
    report['source_references'].append(dict(source_key='second',input_alias='solver_outputs_002',output_name='A',experiment_key='implementation_check',case_key='baseline'))
    write_analysis(opened,report)
    result=worker.call_tool('worker_submit_result',{})
    assert result['state']=='completed',result


@pytest.mark.parametrize('wrong',['bytes','media'])
def test_unscored_manifest_bytes_and_registered_media_are_checked(tmp_path,wrong):
    system=analysis_system(tmp_path)
    _,runtime,_,request,artifacts,register=system
    raw=runtime.artifacts.read(artifacts['output_A'].ref)
    register('bad_output',raw+b' ' if wrong=='bytes' else raw,'opaque',parents=artifacts['manifest'].parent_refs,
        media='application/x-synopsys-plx' if wrong=='bytes' else 'text/plain',output_name='A')
    next(item for item in request['inputs'] if item['port']=='solver_outputs')['artifact_names']=['bad_output']
    root = system[2]
    result=root.call_tool('operation_preflight',request)
    assert result['admissible'] is False,result
    assert result['reason_code']=='input_manifest_output_mismatch',result
    with pytest.raises(Exception, match='input_manifest_output_mismatch'):
        root.call_tool('operation_invoke',request)






def test_optional_output_case_keys_are_paired():
    output=dict(name='A',relative_path='A.plx',media_type='application/x-synopsys-plx',max_bytes=4096)
    ProjectExpectedOutput(**output)
    with pytest.raises(ValueError,match='declared together'):
        ProjectExpectedOutput(**output,case_key='baseline')
    ProjectExpectedOutput(**output,experiment_key='implementation_check',case_key='baseline')




@pytest.mark.parametrize('source_index', [0, 1])
def test_tcad_unknown_weighting_mapping_is_a_request_error(source_index):
    _, _, _, plx, csv = analysis_materials()
    request = raw_request()
    request['sources'][source_index]['weight_column'] = 'original_group'
    record = evaluate_tcad_request(record_key='weighted', request=request,
        sources={'solver_outputs_001': plx, 'reference_material': csv})
    assert record.status == 'unavailable'
    assert record.reason_code == 'invalid_arguments'
    assert record.result is None and not record.input_digests


@pytest.mark.parametrize('raw', [b'"carrier"\n' + b'0 1\n' * 66000,
    b'"carrier"\n0 1\x0b0 1', b'"carrier"\n0 1\xe2\x80\xa80 1'])
def test_raw_admission_bounds_rows_before_parser_allocation(raw, monkeypatch):
    import tcad_artifact.result_analysis as analysis
    def forbidden(*args, **kwargs):
        pytest.fail('unbounded raw rows reached the parser')
    monkeypatch.setattr(analysis, 'normalize_sprocess_plx', forbidden)
    _, _, _, _, csv = analysis_materials()
    record = evaluate_tcad_request(record_key='bounded', request=raw_request(),
        sources={'solver_outputs_001': raw, 'reference_material': csv})
    assert record.status == ('error' if record.reason_code == 'source_line_limit' else 'unsupported')
    assert record.result is None
    assert record.reason_code in {'source_line_limit', 'source_line_separator_unsupported'}


def test_submission_does_not_readmit_frozen_analysis_inputs(tmp_path, monkeypatch):
    from dataclasses import replace
    system = analysis_system(tmp_path)
    worker, opened = open_analysis(system)
    _, runtime, _, _, _, _ = system
    compiled = system[0].operation('tcad.result.analyze.v1')
    def forbidden(*args):
        pytest.fail('output submission called input admission')
    implementations = dict(compiled.implementations)
    implementations['tcad_artifact:result_analysis_input'] = forbidden
    patched = replace(compiled, implementations=implementations)
    monkeypatch.setattr(runtime.runs, '_compiled', lambda value: patched)
    write_analysis(opened, analysis_report())
    runtime.runs.validate_candidate(worker._run_id)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'


def test_admission_omission_preserves_report_as_framework_failure(tmp_path, monkeypatch):
    from dataclasses import replace
    system = analysis_system(tmp_path)
    catalog, runtime, root, request, artifacts, register = system
    register('malformed_manifest', b'{}', 'opaque', parents=artifacts['manifest'].parent_refs)
    next(item for item in request['inputs'] if item['port'] == 'runtime_manifest')['artifact_names'] = ['malformed_manifest']
    original_operation = type(catalog).operation
    def omitted_input_rule(self, name):
        compiled = original_operation(self, name)
        if name != 'tcad.result.analyze.v1':
            return compiled
        implementations = dict(compiled.implementations)
        implementations['tcad_artifact:result_analysis_input'] = lambda sources: None
        return replace(compiled, implementations=implementations)
    # Inject a pre-existing admission bug, with immutable malformed input accepted.
    monkeypatch.setattr(type(catalog), 'operation', omitted_input_rule)
    worker, opened = open_analysis(system)
    write_analysis(opened, analysis_report())
    assert worker.call_tool('worker_submit_result', {})['state'] == 'failed'
    value = runtime.runs.status(worker._run_id)
    assert runtime.runs.recovery_status(value)['delivery_preserved']
    summary = runtime.runs.diagnostic_summary(value)
    assert 'admission_defect' in str(summary)
    assert summary['rejection_count'] == 0
