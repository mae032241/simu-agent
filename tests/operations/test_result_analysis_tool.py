from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import runpy
from pathlib import Path

import pytest

from curve_score.analysis_tool import AnalysisScoreInput, evaluate_analysis_request, replay_calculation
from curve_score.science_operations import Components, validate_analysis_report
from curve_score.plugin import PLUGIN
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.layered_diagnosis import CalculationRecord, LayeredDiagnosisReport
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.invoke import InvocationArtifact, OperationInvocationError, preflight_operation
from scidiscovery.operation_contract import SemanticRuleViolation

_FIXTURES = runpy.run_path(str(Path(__file__).with_name('test_m2_curve_analysis_boundary.py')))


def score_inputs():
    return {'curve_bundle': _FIXTURES['_bundle']().canonical_json()}, {'sources': [{'input_alias': 'curve_bundle', 'format': 'bundle'}], 'comparison_spec': _FIXTURES['_contract']().comparison_spec.model_dump(mode='json')}


def limited_report():
    report = _FIXTURES['_diagnosis']().model_dump(mode='json')
    report['evidence'][0].update(source_key='experiment_results', locator='experiment_results:failure', title='Bound result failure')
    report['source_references'] = [dict(source_key='experiment_results', input_alias='experiment_results')]
    for gate in report['gates'].values():
        if isinstance(gate, dict) and gate.get('evidence_keys'):
            gate['evidence_keys'] = ['experiment_results']
    report['summary'] = 'Execution ended before the requested observable was saved.'
    report['gates']['numerical_validity']['summary'] = 'The execution failed; quantitative validity cannot be established.'
    report['remaining_contradiction'] = 'The planned comparison remains unperformed because its output is missing.'
    report['next_action'] = 'Resolve the execution failure and preserve the required observable before comparison.'
    return report


def test_generic_score_replays_exact_values_without_contract():
    sources, request = score_inputs()
    record = evaluate_analysis_request(record_key='score', request=request, sources=sources)
    assert record.status == 'computed'
    replay_calculation(record, sources)
    raw = record.model_dump(mode='json')
    raw['result']['comparisons'][0]['metrics'][0]['value'] += 1
    with pytest.raises(SemanticRuleViolation, match='replay'):
        replay_calculation(CalculationRecord.model_validate_json(canonical_json(raw)), sources)
    with pytest.raises(SemanticRuleViolation, match='source bytes'):
        replay_calculation(record, {'curve_bundle': sources['curve_bundle'] + b' '})


@pytest.mark.parametrize('change', ['metric', 'samples', 'work'])
def test_invalid_comparisons_are_rejected_before_calculation(change):
    sources, request = score_inputs()
    comparison = request['comparison_spec']['comparisons'][0]
    if change == 'metric':
        comparison['operators'][0]['kind'] = 'raw_row_group_weighted_rms'
    elif change == 'samples':
        comparison['evaluation_points'] = 4097
    else:
        comparison['evaluation_points'] = 4096
        comparison['operators'] = [{**comparison['operators'][0], 'operator_key': f'op_{i}'} for i in range(17)]
    with pytest.raises(ValueError):
        AnalysisScoreInput.model_validate_json(canonical_json(dict(record_key='invalid', request=request)))
    record = evaluate_analysis_request(record_key='invalid', request=request, sources=sources)
    assert record.status == 'unavailable' and record.reason_code == 'invalid_arguments'
    assert record.result is None and not record.input_digests


@pytest.mark.parametrize('mappings', [[{'format': 'bundle'}], [{'input_alias': 'absent', 'format': 'bundle'}], []])
def test_missing_or_malformed_sources_return_bounded_unavailable(mappings):
    sources, request = score_inputs()
    request['sources'] = mappings
    record = evaluate_analysis_request(record_key='missing', request=request, sources=sources)
    assert record.status == 'unavailable'
    if record.reason_code != 'invalid_arguments':
        replay_calculation(record, sources)
    assert len(record.canonical_json()) < 32768


def test_request_byte_admission_precedes_calculation():
    with pytest.raises(ValueError, match='12288 canonical JSON bytes'):
        AnalysisScoreInput(record_key='oversize', request={'unbounded': 'x' * 13000})


def test_csv_columns_preserve_explicit_identity_and_missing_column_reason():
    bundle = _FIXTURES['_bundle']()
    sources, request = {}, score_inputs()[1]
    request['sources'] = []
    for item in bundle.series:
        alias = item.series_key
        sources[alias] = ('depth,value,extra\n' + ''.join(f'{point.x},{point.y},kept\n' for point in item.points)).encode()
        request['sources'].append({'input_alias': alias, 'format': 'csv', 'series_key': item.series_key, 'case_key': item.case_key, 'role': item.role, 'x_axis': item.x_axis.model_dump(mode='json'), 'y_axis': item.y_axis.model_dump(mode='json'), 'x_column': 'depth', 'y_column': 'value'})
    record = evaluate_analysis_request(record_key='csv', request=request, sources=sources)
    assert record.status == 'computed'
    assert all(record.input_digests[key] == hashlib.sha256(raw).hexdigest() for key, raw in sources.items())
    replay_calculation(record, sources)
    request['sources'][0]['y_column'] = 'absent'
    missing = evaluate_analysis_request(record_key='missing', request=request, sources=sources)
    assert missing.status == 'unavailable'
    replay_calculation(missing, sources)


def test_error_has_no_numeric_result_and_is_not_required_to_recur():
    sources, request = score_inputs()
    good = evaluate_analysis_request(record_key='error', request=request, sources=sources)
    record = CalculationRecord.model_validate_json(canonical_json({**good.model_dump(mode='json'), 'status': 'error', 'result': None, 'reason_code': 'timeout'}))
    replay_calculation(record, sources)
    with pytest.raises(ValueError, match='no numeric result'):
        CalculationRecord.model_validate_json(canonical_json({**record.model_dump(mode='json'), 'result': {'value': 1}}))


def test_no_score_limited_analysis_uses_actual_bound_results():
    Components.diagnosis_context.implementation(limited_report(), {'experiment_plan': _FIXTURES['_plan']().canonical_json(), 'experiment_results': b'Execution failed before observable output.'}, {})


def test_keyed_generic_scope_requires_objective_assessment_but_accepts_not_evaluable():
    plan = _FIXTURES['_compiler_plan']()
    report = limited_report()
    report['study_kind'] = 'scientific'
    with pytest.raises(SemanticRuleViolation, match='objective assessment is required') as caught:
        Components.diagnosis_context.implementation(
            report,
            {'experiment_plan': plan.canonical_json(),
             'experiment_results': b'Execution failed before observable output.'},
            {},
        )
    assert caught.value.details[0]['path'] == '$.objective_assessment'
    report['objective_assessment'] = {
        'objective_key': plan.objective_key,
        'status': 'not_evaluable',
        'summary': 'The failed bounded execution did not produce the planned observable.',
    }
    Components.diagnosis_context.implementation(
        report,
        {'experiment_plan': plan.canonical_json(),
         'experiment_results': b'Execution failed before observable output.'},
        {},
    )


def test_generic_compiled_preflight_accepts_no_score_and_rejects_wrong_round():
    compiled = compile_catalog((CORE_PLUGIN, GENERAL, PLUGIN)).operation('science.result.diagnose.v1')
    assert compiled.spec.version == '4'
    assert 'curve_contract' not in {item.name for item in compiled.spec.inputs}
    raw_by_hash = {}
    def artifact(name, schema, parents=(), verdict=None):
        raw = (_FIXTURES['_plan']().canonical_json() if name == 'plan' else
               canonical_json(dict(review_target='experiment_portfolio', verdict='pass', summary='Exact plan review.'))
               if name == 'review' else b'{}')
        digest = hashlib.sha256(raw).hexdigest()
        raw_by_hash[digest] = raw
        labels = (('operation_id', 'science.object.review.v1'), ('operation_output_port', 'scientific_review')) if name == 'review' else ()
        return InvocationArtifact(artifact_name=name, ref=ArtifactRef(artifact_id='art_' + name, sha256=digest, kind='fixture', schema_id=schema), schema_id=schema, media_type='application/json', size_bytes=len(raw), parent_refs=parents, handoff_verdict=verdict, labels=labels)
    plan = artifact('plan', 'scidiscovery.experiment-portfolio.v1')
    review = artifact('review', 'scidiscovery.scientific-review.v1', (plan.ref,), 'pass')
    result = artifact('result', 'opaque', (plan.ref,))
    inputs = {**{item.name: () for item in compiled.spec.inputs}, 'experiment_plan': (plan,), 'experiment_review': (review,), 'experiment_results': (result,)}
    preflight_operation(compiled, name='analysis', artifacts_by_port=inputs, instruction='Analyze available evidence.', read_artifact=lambda ref: raw_by_hash[ref.sha256])
    from dataclasses import replace
    invalid_inputs = [
        ({**inputs, 'experiment_results': (replace(result, parent_refs=()),)},
         'input_result_plan_mismatch'),
        ({**inputs, 'experiment_review': (replace(review, parent_refs=()),)},
         'input_review_plan_mismatch'),
    ]
    for key, value in (('operation_id', 'science.curve.contract.review.v1'), ('operation_output_port', 'other_review')):
        labels = {**dict(review.labels), key: value}
        invalid_inputs.append((
            {**inputs, 'experiment_review': (replace(review, labels=tuple(labels.items())),)},
            'input_review_plan_mismatch',
        ))
    for invalid, reason in invalid_inputs:
        with pytest.raises(OperationInvocationError, match=reason):
            preflight_operation(compiled, name='wrong_round', artifacts_by_port=invalid, instruction='Analyze.')


def test_multiple_controlled_records_submit_without_recalculation(tmp_path, monkeypatch):
    from tests.operations.test_analysis_claim_scope import generic_worker, submit
    worker, opened = generic_worker(tmp_path)
    request = score_inputs()[1]
    records = [json.loads(Path(worker.call_tool('worker_curve_score', dict(record_key=f'score_{i}', request=request))["calculation_path"]).read_bytes())
               for i in range(8)]
    assert all(item['status'] == 'computed' for item in records)
    def never(*args, **kwargs):
        raise AssertionError('submission reran scoring')
    monkeypatch.setattr('curve_score.analysis_tool.evaluate_analysis_request', never)
    monkeypatch.setattr('curve_score.analysis_tool.replay_calculation', never)
    report = limited_report()
    report['source_references'] = []
    report['calculation_records'] = records
    assert submit(worker, opened, report)['state'] == 'completed'


def test_no_score_real_review_worker_submit_then_next_design_reads_sealed_report(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    catalog = compile_catalog((CORE_PLUGIN, GENERAL, PLUGIN))
    runtime, instance, root = runpy.run_path(str(Path(__file__).with_name('test_general_transform_operations.py')))['_root'](tmp_path, catalog=catalog)
    runtime.runs.operation_catalog = catalog

    def register(name, schema, raw, parents=()):
        item = runtime.artifacts.register(raw, ArtifactRegistration(kind='fixture', schema_id=schema, payload_schema_version=1, media_type='application/json', creator=runtime.actor, parent_refs=parents, labels={'scientific_claim_admissible': 'true'}), idempotency_key='analysis:' + name)
        runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace='artifact', name=name, object_id=item.artifact_id)
        return item

    def invoke_worker(name, operation_id, inputs):
        request = {'name': name, 'operation_id': operation_id, 'inputs': [{'port': key, 'artifact_names': [value]} for key, value in inputs.items()], 'instruction': 'Analyze only the supplied fixture evidence.'}
        preflight = root.call_tool('operation_preflight', request)
        assert preflight['admissible'] is True, preflight
        invoked = root.call_tool('operation_invoke', request)
        operation = catalog.operation(operation_id)
        worker = LocalWorkerMCPRouter(runtime.runs, operation_id=operation_id, operation_digest=operation.digest)
        return worker, worker.call_tool('worker_open_assignment', {}), request, preflight, invoked

    def submit(worker, opened, payload, verdict):
        run_id = next(item.run_id for item in runtime.runs.list(instance_id=instance.instance_id) if item.state == 'running')
        Path(opened['output_directory'], 'result.json').write_bytes(canonical_json({'schema_version': 1, 'handoff': {'verdict': verdict, 'summary': 'Bounded fixture result.'}, 'payload': payload}))
        status = worker.call_tool('worker_submit_result', {})
        assert status['state'] == 'completed', status
        return next(item for item in runtime.runs.list(instance_id=instance.instance_id) if item.run_id == run_id)

    plan = register('plan', 'scidiscovery.experiment-portfolio.v1', _FIXTURES['_plan']().canonical_json())
    worker, opened, _, _, _ = invoke_worker('review', 'science.object.review.v1', {'experiment_plan': 'plan'})
    review = submit(worker, opened, {'review_target': 'experiment_portfolio', 'verdict': 'pass', 'summary': 'Bounded fixture plan is coherent.'}, 'pass')
    register('actual_result', 'opaque', b'Execution failed before observable output.', (plan.ref,))
    analyses = []
    sealed_outputs = []
    for suffix, suggestion in (('a', 'Inspect one bounded failure cause.'),
                               ('b', 'A different untrusted follow-up suggestion.')):
        worker, opened, _, _, _ = invoke_worker(
            'analysis_' + suffix,
            'science.result.diagnose.v1',
            {'experiment_plan': 'plan', 'experiment_review': review.output_binding_name,
             'experiment_results': 'actual_result'},
        )
        report = limited_report()
        report['next_action'] = suggestion
        analysis = submit(worker, opened, report, 'blocked')
        artifact_id = runtime.scheduler_bindings.resolve(
            instance=instance.instance_id, namespace='artifact',
            name=analysis.output_binding_name,
        )
        sealed = runtime.artifacts.get_by_id(artifact_id)
        sealed_bytes = runtime.artifacts.read(sealed.ref)
        assert b'remaining_contradiction' in sealed_bytes
        analyses.append(analysis)
        sealed_outputs.append((sealed, sealed_bytes))
    payloads = [json.loads(raw) for _, raw in sealed_outputs]
    suggestions = [payload.pop('next_action') for payload in payloads]
    assert suggestions[0] != suggestions[1]
    assert payloads[0] == payloads[1]

    # Foundation qualification is fixture-only; the analysis/feedback route itself
    # uses unchanged Root admission, actual Run outputs, and the installed reader.
    from tests.operations.test_agent_contract_alignment import experiment_case
    from tests.operations.test_hypothesis_objective_boundary import _foundation
    design_payload, design_sources = experiment_case.__wrapped__()
    design_payload['objective_key'] = 'objective_expected'
    foundation_value = json.loads(_foundation())
    foundation_value['objective_contract'] = json.loads(design_sources['research_objective'])
    foundation = register('foundation', 'scidiscovery.scientific-foundation.v1', canonical_json(foundation_value))
    register('objective', 'scidiscovery.research-objective.v1', design_sources['research_objective'], (foundation.ref,))
    hypothesis = register('hypotheses', 'scidiscovery.hypothesis-proposal.v2', design_sources['hypothesis_portfolio'], (foundation.ref,))
    register('critic', 'scidiscovery.critic-review.v2', design_sources['critic_review'], (foundation.ref, hypothesis.ref))
    monkeypatch.setattr(runtime.approvals, 'are_subjects_approved_by_provider', lambda *a, **k: True)
    design_admission = []
    design_runs = []
    first_opened = None
    for index, analysis in enumerate(analyses):
        inputs = {'scientific_foundation': 'foundation', 'research_objective': 'objective',
            'hypothesis_portfolio': 'hypotheses', 'critic_review': 'critic',
            'result_analysis': analysis.output_binding_name}
        name = 'next_design_' + str(index)
        request = {'name': name, 'operation_id': 'science.experiment.design.v1',
            'inputs': [{'port': key, 'artifact_names': [value]} for key, value in inputs.items()],
            'instruction': 'Analyze only the supplied fixture evidence.'}
        preflight = root.call_tool('operation_preflight', request)
        invoked = root.call_tool('operation_invoke', request) if preflight['admissible'] else None
        design_admission.append((preflight['admissible'], preflight.get('reason_code'), invoked is not None))
        run_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='run', name=name)
        design_runs.append(runtime.runs.status(run_id))
        if index == 0:
            operation = catalog.operation('science.experiment.design.v1')
            designer = LocalWorkerMCPRouter(runtime.runs, operation_id=operation.spec.operation_id,
                operation_digest=operation.digest)
            first_opened = designer.call_tool('worker_open_assignment', {})
            Path(first_opened['output_directory'], 'result.json').write_bytes(canonical_json({
                'schema_version': 1,
                'handoff': {'verdict': 'pass', 'summary': 'Bounded fixture design.'},
                'payload': design_payload,
            }))
            assert designer.call_tool('worker_submit_result', {})['state'] == 'completed'
    assert design_admission == [(True, None, True), (True, None, True)]
    for index, next_run in enumerate(design_runs):
        binding = next(item for item in next_run.inputs if item.port_name == 'result_analysis')
        sealed, sealed_bytes = sealed_outputs[index]
        assert binding.artifact_ref == sealed.ref
        assert runtime.artifacts.read(binding.artifact_ref) == sealed_bytes
    delivered = next((Path(first_opened['workspace_path']) / 'inputs').glob('result_analysis.*'))
    assert delivered.read_bytes() == sealed_outputs[0][1]


@pytest.mark.parametrize('record_kind', ['unsupported', 'failed', 'unrelated'])
def test_record_status_does_not_mechanically_decide_scientific_verdict(record_kind):
    sources, request = score_inputs()
    if record_kind == 'unsupported':
        request['comparison_spec']['comparisons'][0]['operators'][0]['kind'] = 'unsupported_statistic'
    if record_kind == 'unrelated':
        request['comparison_spec']['comparisons'][0]['operators'][0]['validation_check_key'] = 'unrelated_check'
    record = evaluate_analysis_request(record_key='score', request=request, sources=sources)
    report = _FIXTURES['_passing_diagnosis']().model_dump(mode='json')
    report['evidence'][0]['locator'] = 'calculation_records:score'
    report['calculation_records'] = [record.model_dump(mode='json')]
    validate_analysis_report(LayeredDiagnosisReport.model_validate_json(canonical_json(report)), _FIXTURES['_plan']())


def test_inconclusive_observation_can_submit_without_scoring():
    report = _FIXTURES['_passing_diagnosis']().model_dump(mode='json')
    report['evidence'][0].update(source_key='experiment_results', locator='experiment_results:run_log')
    report['source_references'] = [dict(source_key='experiment_results', input_alias='experiment_results')]
    for gate in report['gates'].values():
        if isinstance(gate, dict) and gate.get('evidence_keys'):
            gate['evidence_keys'] = ['experiment_results']
    report['gates']['observation']['status'] = 'inconclusive'
    report['gates']['observation']['summary'] = 'The requested observable is absent.'
    report['overall_verdict'] = 'inconclusive'
    report['summary'] = 'Run prerequisites hold but the observation cannot be compared.'
    Components.diagnosis_context.implementation(report, {'experiment_plan': _FIXTURES['_plan']().canonical_json(), 'experiment_results': b'Run completed; observable missing.'}, {})


@pytest.mark.parametrize('location', ['request', 'source'])
def test_unknown_weighting_option_is_not_silently_scored_as_rms(location):
    sources, request = score_inputs()
    if location == 'request':
        request['weighting'] = 'original_row_groups'
    else:
        request['sources'][0]['weight_column'] = 'group_weight'
    record = evaluate_analysis_request(record_key='weighted', request=request, sources=sources)
    assert record.status == 'unavailable' and record.reason_code == 'invalid_arguments'
    assert not record.input_digests
    with pytest.raises(ValueError):
        AnalysisScoreInput.model_validate_json(canonical_json(dict(record_key='weighted', request=request)))


@pytest.mark.parametrize('comparisons', [[None], [42], ['invalid'], None])
def test_persisted_malformed_comparisons_remain_readable_as_failed_requests(comparisons):
    sources, request = score_inputs()
    request['comparison_spec']['comparisons'] = comparisons
    record = evaluate_analysis_request(record_key='malformed', request=request, sources=sources)
    assert record.status == 'unavailable' and record.result is None
    assert record.reason_code == 'invalid_arguments' and not record.input_digests
    assert canonical_json(record.request) == canonical_json(request)
    assert all(item.phase == 'tool_arguments' for item in record.diagnostics)


@pytest.mark.parametrize('documented', [False, True])
def test_changed_threshold_record_remains_visible_for_scientific_review(documented):
    sources, request = score_inputs()
    request['comparison_spec']['comparisons'][0]['operators'][0]['threshold']['value'] = 100.0
    record = evaluate_analysis_request(record_key='score', request=request, sources=sources)
    report = _FIXTURES['_passing_diagnosis']().model_dump(mode='json')
    report['evidence'][0]['locator'] = 'calculation_records:score'
    report['calculation_records'] = [record.model_dump(mode='json')]
    if documented:
        report['method_changes'] = ['Exploratory relaxed threshold, not the original acceptance criterion.']
    validate_analysis_report(LayeredDiagnosisReport.model_validate_json(canonical_json(report)), _FIXTURES['_plan']())
    assert record.request['comparison_spec']['comparisons'][0]['operators'][0]['threshold']['value'] == 100.0


def test_deadline_stops_reading_more_inputs_and_error_can_be_replayed(monkeypatch, tmp_path):
    from types import SimpleNamespace
    import curve_score.analysis_tool as tool
    clock = [0.0]
    monkeypatch.setattr(tool.time, 'monotonic', lambda: clock[0])
    sources, request = score_inputs()
    request['sources'].append({'input_alias': 'second_bundle', 'format': 'bundle'})
    reads = []
    def read(name):
        reads.append(name)
        clock[0] = 6.0
        return sources['curve_bundle']
    raw = tool.score_tool(AnalysisScoreInput.model_validate_json(canonical_json(dict(record_key='timed', request=request))),
        SimpleNamespace(remaining_seconds=10, read_evidence=read, finish_attempt=lambda **kwargs: None,
            workspace=tmp_path, accept_evidence=lambda **kwargs: {'alias': 'tool_evidence_001'}))
    record = CalculationRecord.model_validate_json(Path(raw["calculation_path"]).read_bytes())
    assert record.status == 'error' and record.result is None
    assert reads == ['curve_bundle']
    replay_calculation(record, sources)


def test_sealed_historical_calculation_needs_no_replay_time_budget():
    from scidiscovery.artifact_agent.service.run_outputs import ValidationSources
    from tests.operations.test_prior_analysis_sources import bindings
    sources, request = score_inputs()
    raw = sources['curve_bundle']
    request['sources'][0]['input_alias'] = 'old_curve'
    record = evaluate_analysis_request(record_key='score', request=request, sources={'old_curve': raw})
    report = limited_report()
    report['calculation_records'] = [record.model_dump(mode='json')]
    contents, descriptors = bindings(legacy=True, raw=raw, previous=canonical_json(report))
    contents.update(experiment_plan=_FIXTURES['_plan']().canonical_json(), experiment_results=b'failure')
    bound = ValidationSources(contents, descriptors, validation_deadline=0.0)
    Components.diagnosis_context.implementation(report, bound, {})


def test_score_tool_contract_describes_comparison_and_rejects_invalid_record_key():
    schema = AnalysisScoreInput.model_json_schema()
    assert schema['properties']['request'] == {'$ref': '#/$defs/AnalysisScoreRequest'}
    sources = schema['$defs']['AnalysisScoreRequest']['properties']['sources']['items']
    assert sources['discriminator']['propertyName'] == 'format'
    assert set(sources['discriminator']['mapping']) == {'bundle', 'csv'}
    comparison = schema['$defs']['AnalysisScoreRequest']['properties']['comparison_spec']['$ref'].split('/')[-1]
    assert comparison in schema['$defs'] and 'CurveAxis' in schema['$defs']
    assert 'sprocess_plx' not in json.dumps(schema)
    with pytest.raises(ValueError):
        AnalysisScoreInput(record_key='bad key', request={})


def test_matching_plan_check_can_still_pass_with_computed_evidence():
    import json
    sources, request = score_inputs()
    bundle = json.loads(sources['curve_bundle'])
    by_key = {item['series_key']: item for item in bundle['series']}
    comparison = request['comparison_spec']['comparisons'][0]
    by_key[comparison['candidate_series']]['points'] = by_key[comparison['reference_series']]['points']
    sources['curve_bundle'] = canonical_json(bundle)
    record = evaluate_analysis_request(record_key='score', request=request, sources=sources)
    report = _FIXTURES['_passing_diagnosis']().model_dump(mode='json')
    report['evidence'][0]['locator'] = 'calculation_records:score'
    report['calculation_records'] = [record.model_dump(mode='json')]
    validate_analysis_report(LayeredDiagnosisReport.model_validate_json(canonical_json(report)), _FIXTURES['_plan']())
