"""Complete research tasks and private provenance through production services."""
import json
from pathlib import Path


def test_calculation_science_and_private_proof_seal_together(tmp_path, monkeypatch):
    from tests.operations.test_r4_experiment_task import _real_experiment
    from tests.operations.test_m2_curve_analysis_boundary import _bundle, _contract
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    runtime, root, catalog, _, instance = _real_experiment(tmp_path, monkeypatch)
    bundle = runtime.artifacts.register(_bundle().canonical_json(), ArtifactRegistration(kind='curves',
        schema_id='scidiscovery.curve-bundle.v1', payload_schema_version=1, media_type='application/json', creator=runtime.actor), idempotency_key='curves')
    runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace='artifact', name='curves', object_id=bundle.artifact_id)
    root.call_tool('operation_invoke', dict(name='analyze', operation_id='science.result.diagnose.v1',
        instruction='Analyze exact observed curves.', inputs=[dict(port='experiment_results',artifact_names=['observe.output']), dict(port='curve_bundle',artifact_names=['curves'])]))
    compiled = catalog.operation('science.result.diagnose.v1')
    worker = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    opened = worker.call_tool('worker_open_assignment', {})
    request = dict(sources=[dict(input_alias='curve_bundle',format='bundle')], comparison_spec=_contract().comparison_spec.model_dump(mode='json'))
    from scidiscovery.artifact_agent.schema.layered_diagnosis import CalculationRecord, LayeredDiagnosisReport
    value = worker.call_tool('worker_curve_score', {'record_key':'bounded_score', 'request':request})
    assert value['status'] == 'computed', value
    assert not {'attempt', 'input_digests', 'sha256', 'calculation_path'} & value.keys()
    schema = json.dumps(LayeredDiagnosisReport.model_json_schema())
    assert 'input_digests' not in schema and 'proof_kind' not in schema and 'attempt_key' not in schema
    assert 'calculation_records' not in LayeredDiagnosisReport.model_json_schema()['properties']
    directory = worker.call_tool('worker_reference_read', {'source':value['calculation_ref'],'action':'list'})
    content = directory['references'][0]['reference']
    page = worker.call_tool('worker_reference_read', {'source':value['calculation_ref'],'action':'read','reference':content,'limit':512})
    assert page['omitted'] and page['next_offset']
    continuation = worker.call_tool('worker_reference_read', {'source':value['calculation_ref'],'action':'read','reference':content,'offset':page['next_offset'],'limit':512})
    assert continuation['provided']['offset'] == page['next_offset']
    science = worker.call_tool('worker_reference_read', {'source':value['calculation_ref'],'action':'read','reference':content,'pointer':'/status'})
    assert json.loads(science['fragment']) == 'computed'
    assert not {'file_path','attempt','input_digests'} & science.keys()
    record = next(item for item in worker.runs.tool_evidence(worker._run_id) if item['alias'] == value['calculation_ref'])
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    raw = worker.runs.artifacts.read(ArtifactRef.model_validate(record['artifact_ref']))
    public = json.loads(raw)
    CalculationRecord.model_validate_json(raw)
    assert not {'attempt','input_digests'} & public.keys()
    assert 'curve_bundle_sha256' not in public['result']
    assert record['metadata']['calculation_proof']['attempt']['attempt_key']
    report = dict(experiment_key="observed", plan_key="bounded", summary="Fixture calculation is limited to supplied curves.", overall_verdict="inconclusive", claim_allowed=False, evidence=[])
    report['evidence'].append(dict(source_key=value['calculation_ref'], source_type='runtime_output',
        title='Registered calculation', locator=value['calculation_ref']))
    Path(opened['output_directory'], 'result.json').write_text(json.dumps(dict(schema_version=1,payload=report)))
    # The declared schema rejects the retired duplicate representation before proof validation.
    inline = {**report, 'calculation_records':[public]}
    Path(opened['output_directory'], 'result.json').write_text(json.dumps(dict(schema_version=1,payload=inline)))
    rejected = worker.call_tool('worker_submit_result', {})
    assert rejected['state'] == 'rejected', rejected
    Path(opened['output_directory'], 'result.json').write_text(json.dumps(dict(schema_version=1,payload=report)))
    result = worker.call_tool('worker_submit_result', {})
    assert result['state'] == 'completed', result
    status = worker.runs.status(worker._run_id)
    assert not json.loads(worker.runs.artifacts.read(status.output_ref)).get('calculation_records')
    # The controlled receipt rejects edited scientific bytes without recomputation.
    from scidiscovery.artifact_agent.service.calculation_proof import controlled_calculation
    import pytest
    public['result']['comparisons'][0]['metrics'][0]['value'] = 999
    with pytest.raises(ValueError, match='differs'):
        controlled_calculation(json.dumps(public).encode(), record)
    assert b'calculation_proof' not in Path(opened['output_directory'], 'tool-evidence.json').read_bytes()
    # A continuation selects the exact scientific report; control resolves its manifest.
    root.call_tool('operation_invoke', dict(name='follow_analysis', operation_id='science.result.diagnose.v1', max_attempts=2,
        instruction='Reuse the exact calculation.', inputs=[dict(port='experiment_results', artifact_names=['observe.output']),
            dict(port='prior_analysis', artifact_names=['analyze.output'])]))
    follow_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='run', name='follow_analysis')
    follow = runtime.runs.status(follow_id)
    proof_input = next(item for item in follow.inputs if item.port_name == 'prior_analysis_manifest')
    assert runtime.artifacts.catalog(proof_input.artifact_ref).labels['tool_producer_run'] == status.run_id
    next_worker = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    next_open = next_worker.call_tool('worker_open_assignment', {})
    assignment = json.loads(Path(next_open['assignment_path']).read_text())
    assert 'prior_analysis_manifest' not in json.dumps(assignment['inputs'])
    assert all('port' not in item for item in assignment['inputs'])
    workspace = Path(next_open['workspace_path'])
    from scidiscovery.artifact_agent.service.local_workspace import workspace_input_filename
    hidden_path = workspace / 'inputs' / workspace_input_filename(proof_input.source_name, proof_input.media_type)
    assert not hidden_path.exists()
    private_raw = runtime.artifacts.read(proof_input.artifact_ref)
    assert all(path.read_bytes() != private_raw for path in (workspace / 'inputs').iterdir())
    import subprocess, sys
    read = subprocess.run([sys.executable,'-B',str(workspace / 'tools/read_input.py'),'--file',str(hidden_path.relative_to(workspace))],capture_output=True,text=True,timeout=10)
    assert read.returncode == 1 and 'attempt_key' not in read.stdout
    from scidiscovery.operation_contract import DiagnosticError
    with pytest.raises(DiagnosticError):
        next_worker.call_tool('worker_reference_read', {'source':proof_input.source_name,'action':'list'})
    with pytest.raises(DiagnosticError):
        next_worker.call_tool('worker_reference_read', {'source':value['calculation_ref'],'action':'list'})
    listed = next_worker.call_tool('worker_reference_read', {'source':'prior_analysis','action':'list'})
    handle = next(item['reference'] for item in listed['references'] if item.get('alias') == value['calculation_ref'])
    accessed = next_worker.call_tool('worker_reference_read', {'source':'prior_analysis','action':'read','reference':handle,'pointer':'/status'})
    assert 'input_digests' not in json.dumps(accessed) and 'proof_kind' not in json.dumps(accessed)

    from scidiscovery.artifact_agent.interfaces.mcp_root_shared import RootToolError
    with pytest.raises(RootToolError):
        root.call_tool('operation_invoke', dict(name='wrong',operation_id='science.result.diagnose.v1', inputs=[
            dict(port='experiment_results',artifact_names=['observe.output']),
            dict(port='prior_analysis_manifest',artifact_names=['observe.output'])]))

    # A committed historical read survives a failed task and actual assignment open.
    original_access = runtime.runs.reference_access_records(next_worker._run_id)[0]
    interrupted = runtime.runs.status(next_worker._run_id)
    runtime.runs.record_failure(interrupted.run_id, reason='Fixture interrupted after reading the original.',
        expected_state=interrupted.state, expected_last_activity_at=interrupted.last_activity_at)
    root.call_tool('operation_invoke', dict(name='recovered_reader', operation_id=compiled.spec.operation_id,
        instruction='Continue using the exact original calculation.', draft_from='follow_analysis', max_attempts=2,
        inputs=[dict(port='experiment_results',artifact_names=['observe.output']),
            dict(port='prior_analysis',artifact_names=['analyze.output'])]))
    recovered = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    recovered_open = recovered.call_tool('worker_open_assignment', {})
    assert runtime.runs.status(recovered._run_id).state == 'running'
    adopted = runtime.runs.reference_access_records(recovered._run_id)[0]
    assert adopted['adopted_from'] == original_access['request_key']
    for key in ('artifact_ref','root_ref','chain','budget_scope','authorizing_manifest_ref','authorizing_run_id','proof_manifest_ref','proof_run_id'):
        assert adopted[key] == original_access[key]
    replayed = recovered.call_tool('worker_reference_read',
        {'source':'prior_analysis','action':'read','reference':handle,'pointer':'/status'})
    assert json.loads(replayed['fragment']) == 'computed'
    assert len(runtime.runs.reference_access_records(recovered._run_id)) == 1
    report['evidence'] = [dict(source_key=adopted['alias'], source_type='runtime_output',
        title='Recovered original calculation', locator=adopted['alias'])]
    Path(recovered_open['output_directory'],'result.json').write_text(json.dumps(dict(schema_version=1,payload=report)))
    finished = recovered.call_tool('worker_submit_result', {})
    assert finished['state'] == 'completed', finished


def test_parameter_and_figure_tasks_keep_science_tools_and_exact_origins(tmp_path, monkeypatch):
    from tests.operations.test_r4_experiment_task import _real_experiment
    from tests.operations.test_m2_parameter_package import _package
    from tests.operations.test_general_transform_operations import _intake
    from tests.operations.test_minimal_figure_extraction import _png, _request
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN as science
    from curve_score.plugin import PLUGIN as curve
    from tcad_artifact.plugin import PLUGIN as tcad
    from curve_figure_evidence.plugin import PLUGIN as figure
    from scidiscovery.operations.catalog import compile_catalog
    from scidiscovery.operations.spec import scheduler_operation_view
    runtime, root, _, _, instance = _real_experiment(tmp_path, monkeypatch)
    catalog = compile_catalog((CORE_PLUGIN, science, curve, tcad, figure))
    runtime.runs.operation_catalog = catalog
    root.facade._operation_catalog = catalog
    operations = {op.operation_id for plugin in (science, tcad, figure) for op in plugin.operations}
    assert not operations & {'science.hypothesis.revise.v1','science.intake.revise.v1','science.evidence.revise-from-critic.v1',
        'tcad.parameter.evidence.expand.v1','tcad.parameter.evidence.audit.v1','science.parameter.coverage.v1',
        'science.parameter.uncertainty.v1','science.parameters.qualify.pass.v1','science.parameters.qualify.exception.v1'}
    root.call_tool('artifact_ingest_text', {'name':'parameter_source', 'text':'Parameter source fixture.'})
    root.call_tool('operation_invoke', dict(name='parameter',operation_id='tcad.parameter.evidence.extract.v1',
        instruction='Retain bounded parameter observations.', inputs=[dict(port='source_material',artifact_names=['parameter_source'])]))
    compiled = catalog.operation('tcad.parameter.evidence.extract.v1')
    worker = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id,operation_digest=compiled.digest)
    opened = worker.call_tool('worker_open_assignment', {})
    output = Path(opened['output_directory'], 'result.json')
    output.write_text(json.dumps(dict(schema_version=1,payload=_package('source_material').model_dump(mode='json'),
        handoff=dict(verdict='pass',summary='Parameter fixture.'))))
    checked = worker.call_tool('worker_parameter_check', {'package_path':'output/result.json'})
    assert checked['coverage']['status'] == 'pass'
    completed = worker.call_tool('worker_submit_result', {})
    assert completed['state'] == 'completed', completed
    package = json.loads(runtime.artifacts.read(runtime.runs.status(worker._run_id).output_ref))
    assert package['coverage'] == checked['coverage']
    # Figure extraction keeps one author; no family or provenance is supplied by the caller.
    source = runtime.artifacts.register(_png(), ArtifactRegistration(kind='paper',schema_id='opaque',payload_schema_version=1,
        media_type='image/png',creator=runtime.actor),idempotency_key='figure-source')
    runtime.scheduler_bindings.bind(instance=instance.instance_id,namespace='artifact',name='figure_source',object_id=source.artifact_id)
    root.call_tool('operation_invoke',dict(name='figure',operation_id='science.evidence.extract.figure.v3',instruction='Retain the unresolved figure identity.',
        inputs=[dict(port='paper_source',artifact_names=['figure_source'])]))
    compiled = catalog.operation('science.evidence.extract.figure.v3')
    visible = scheduler_operation_view(compiled.spec)
    assert not {'figure_family','figure_provenance'} & {port.name for port in visible.inputs}
    worker = LocalWorkerMCPRouter(runtime.runs,operation_id=compiled.spec.operation_id,operation_digest=compiled.digest)
    opened = worker.call_tool('worker_open_assignment', {})
    from curve_figure_evidence.scientific_files import SOURCE_CONTROL
    request = json.loads(_request(_png()))
    for key in SOURCE_CONTROL:
        request['source'].pop(key, None)
    preview = worker.call_tool('worker_curve_figure_preview',dict(name='paper_source',request=request))
    assert 'sha256' not in json.dumps(preview)
    reply = worker.call_tool('worker_curve_figure_save',dict(name='paper_source',request=request))
    assert reply['request_status'] == 'ready'
    assert 'sha256' not in json.dumps(reply) and 'artifact_ref' not in json.dumps(reply)
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    for item in runtime.runs.tool_evidence(worker._run_id):
        raw = runtime.artifacts.read(ArtifactRef.model_validate(item['artifact_ref']))
        if item['media_type'] == 'application/json':
            assert b'sha256' not in raw and b'artifact_ref' not in raw
    intake = _intake().model_dump(mode='json')
    intake['scientific_foundation']['evidence'][0]['source_key'] = 'paper_source'
    intake['scientific_foundation']['items'][0]['evidence_keys'] = ['paper_source']
    Path(opened['output_directory'],'result.json').write_text(json.dumps(dict(schema_version=1,payload=intake,
        handoff=dict(verdict='inconclusive',summary='Unresolved source identity.'))))
    completed = worker.call_tool('worker_submit_result', {})
    assert completed['state'] == 'completed', completed
    # A fresh wording revision restores the exact prior family without a required review.
    root.call_tool('operation_invoke',dict(name='figure_revision',operation_id=compiled.spec.operation_id,instruction='Clarify the preserved limitation.',
        inputs=[dict(port='paper_source',artifact_names=['figure_source']),dict(port='prior_draft',artifact_names=['figure.output'])]))
    worker2 = LocalWorkerMCPRouter(runtime.runs,operation_id=compiled.spec.operation_id,operation_digest=compiled.digest)
    opened2 = worker2.call_tool('worker_open_assignment', {})
    reused = worker2.call_tool('worker_curve_figure_reuse',dict(name='paper_source'))
    assert reused['reused'] and 'sha256' not in json.dumps(reused)
    assert 'figure_provenance' not in json.dumps(json.loads(Path(opened2['assignment_path']).read_text())['inputs'])
    Path(opened2['output_directory'],'result.json').write_text(json.dumps(dict(schema_version=1,payload=intake,
        handoff=dict(verdict='inconclusive',summary='Preserved source limitation.'))))
    assert worker2.call_tool('worker_submit_result', {})['state'] == 'completed'
    root.call_tool('operation_invoke',dict(name='figure_followup',operation_id=compiled.spec.operation_id,instruction='Reuse the same selected figure.',
        inputs=[dict(port='paper_source',artifact_names=['figure_source']),dict(port='prior_draft',artifact_names=['figure_revision.output'])]))


def test_checkpoint_continuation_reuses_numbers_and_exact_private_sources(tmp_path, monkeypatch):
    from tests.operations.test_r4_experiment_task import _real_experiment
    from tests.operations.test_m2_curve_analysis_boundary import _bundle, _contract
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    from curve_score import diagnostic_tool
    import pytest
    runtime, root, catalog, _, instance = _real_experiment(tmp_path, monkeypatch)
    bundle = runtime.artifacts.register(_bundle().canonical_json(), ArtifactRegistration(kind='curves',
        schema_id='scidiscovery.curve-bundle.v1', payload_schema_version=1, media_type='application/json', creator=runtime.actor), idempotency_key='checkpoint-curves')
    runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace='artifact', name='curves', object_id=bundle.artifact_id)
    invoke = dict(name='checkpoint_analysis', operation_id='science.result.diagnose.v1', max_attempts=2,
        instruction='Retain calculations through an interrupted report.', inputs=[dict(port='experiment_results',artifact_names=['observe.output']), dict(port='curve_bundle',artifact_names=['curves'])])
    root.call_tool('operation_invoke', invoke)
    compiled = catalog.operation(invoke['operation_id'])
    worker = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    worker.call_tool('worker_open_assignment', {})
    spec = _contract().comparison_spec.model_dump(mode='json')
    spec['comparisons'] = [spec['comparisons'][0]]
    spec['comparisons'][0]['operators'] = [spec['comparisons'][0]['operators'][0]]
    spec['comparisons'][0]['evaluation_points'] = 65
    request = dict(sources=[dict(input_alias='curve_bundle',format='bundle')], comparison_spec=spec)
    render = diagnostic_tool.render_curve_error
    def missing(*args, **kwargs):
        raise OSError('fixture render unavailable')
    monkeypatch.setattr(diagnostic_tool, 'render_curve_error', missing)
    saved = worker.call_tool('worker_curve_diagnose', dict(record_key='saved', request=request))
    assert saved['record']['status'] == 'computed' and saved['checkpoint'] and not saved['images']
    assert saved['record']['summary']['limitations']
    checkpoint = saved['checkpoint']['evidence_alias']
    receipt = next(item for item in runtime.runs.tool_evidence(worker._run_id) if item['alias'] == checkpoint)
    raw = runtime.artifacts.read(ArtifactRef.model_validate(receipt['artifact_ref']))
    assert b'sha256' not in raw and b'input_refs' not in raw and b'input_digests' not in raw
    assert receipt['metadata']['checkpoint_proof']['input_refs']
    value = runtime.runs.status(worker._run_id)
    runtime.runs.record_failure(value.run_id, reason='fixture report interrupted', expected_state=value.state, expected_last_activity_at=value.last_activity_at)
    invoke.update(name='checkpoint_continuation', draft_from='checkpoint_analysis')
    root.call_tool('operation_invoke', invoke)
    following = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    opened = following.call_tool('worker_open_assignment', {})
    assert runtime.runs.recovery_tool_proof(runtime.runs.status(following._run_id)) is not None
    monkeypatch.setattr(diagnostic_tool, 'render_curve_error', render)
    def recomputed(*args, **kwargs):
        pytest.fail('checkpoint continuation recomputed completed numbers')
    monkeypatch.setattr(diagnostic_tool, 'compute_curve_error', recomputed)
    monkeypatch.setattr(diagnostic_tool, 'evaluate_analysis_request', recomputed)
    changed = json.loads(json.dumps(request))
    changed['comparison_spec']['comparisons'][0]['evaluation_points'] += 1
    rejected = following.call_tool('worker_curve_diagnose', dict(record_key='changed', request=changed, checkpoint_alias=checkpoint))
    assert rejected['record']['status'] == 'unavailable'
    reused = following.call_tool('worker_curve_diagnose', dict(record_key='reused', request=request, checkpoint_alias=checkpoint))
    assert reused['record']['status'] == 'computed' and reused['checkpoint']['reused'] and reused['images']
    report = dict(experiment_key='observed',plan_key='bounded',summary='Saved numerical work survives interruption.',overall_verdict='inconclusive',claim_allowed=False,
        evidence=[dict(source_key=reused['record']['calculation_ref'],source_type='runtime_output',title='Retained calculation',locator=reused['record']['calculation_ref'])])
    Path(opened['output_directory'],'result.json').write_text(json.dumps(dict(schema_version=1,payload=report)))
    completed = following.call_tool('worker_submit_result', {})
    assert completed['state'] == 'completed', completed
