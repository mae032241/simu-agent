"""Typed score requests reach parsing only after admission, preserving raw JSON."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from curve_score.analysis_tool import (
    AnalysisScoreInput, evaluate_analysis_request, replay_calculation, score_tool,
)
from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
from scidiscovery.artifact_agent.operation_tool_context import OperationToolContext
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.layered_diagnosis import CalculationRecord
from scidiscovery.artifact_agent.schema.tool_evidence import ToolEvidenceManifest
from tcad_artifact.result_analysis import TCADScoreInput, evaluate_tcad_request
from tests.operations.test_result_analysis_tool import score_inputs
from tests.operations.test_tcad_result_analysis import (
    analysis_materials, analysis_system, open_analysis, raw_request,
)


def call_score(worker, request):
    return MCPRouter(worker, name='typed-score').handle({
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {'name': 'worker_tcad_curve_score',
                   'arguments': {'record_key': 'score', 'request': request}},
    })


def test_tcad_schema_reuses_axes_and_comparisons_with_discriminated_sources():
    schema = TCADScoreInput.model_json_schema()
    request = schema['$defs']['TCADScoreRequest']['properties']
    assert request['comparison_spec']['$ref'] == '#/$defs/AnalysisCurveComparisonSpec'
    assert set(request['sources']['items']['discriminator']['mapping']) == {
        'csv', 'sprocess_plx', 'sprocess_log',
    }
    plx = schema['$defs']['SProcessPLXSource']
    assert plx['properties']['x_axis'] == {'$ref': '#/$defs/CurveAxis'}
    assert plx['properties']['y_axis'] == {'$ref': '#/$defs/CurveAxis'}
    assert {'dataset_name', 'case_key', 'series_key'} <= set(plx['required'])
    assert plx['additionalProperties'] is False


@pytest.mark.parametrize('model,make_request', [(AnalysisScoreInput, lambda: score_inputs()[1]),
                                                (TCADScoreInput, raw_request)])
@pytest.mark.parametrize('bound', ['comparisons', 'operators', 'evaluation_points'])
def test_analysis_schema_and_model_share_actual_bounds(model, make_request, bound):
    from jsonschema import Draft202012Validator
    from pydantic import ValidationError
    from scidiscovery.operation_contract import validation_diagnostics
    schema = model.model_json_schema()
    validator = Draft202012Validator(schema)
    limit = 4096 if bound == 'evaluation_points' else 16
    for count in (limit, limit + 1):
        request = make_request()
        comparison = request['comparison_spec']['comparisons'][0]
        # Isolate each field bound from the separate canonical request byte budget.
        comparison = {key: comparison[key] for key in (
            'comparison_key', 'reference_series', 'candidate_series', 'domain', 'interpolation')}
        comparison['operators'] = [dict(operator_key='metric', kind='residual_max_abs')]
        request['comparison_spec']['comparisons'] = [comparison]
        if bound == 'evaluation_points':
            comparison[bound] = count
        elif bound == 'operators':
            comparison[bound] = [{**comparison['operators'][0], 'operator_key': f'op_{i}'} for i in range(count)]
        else:
            request['comparison_spec'][bound] = [{**comparison, 'comparison_key': f'comparison_{i}'} for i in range(count)]
        payload = dict(record_key='boundary', request=request)
        if count == limit:
            validator.validate(payload)
            assert model.model_validate_json(canonical_json(payload)).request.raw_request == request
        else:
            assert list(validator.iter_errors(payload))
            with pytest.raises(ValidationError) as caught:
                model.model_validate_json(canonical_json(payload))
            details = validation_diagnostics(caught.value, schema=schema)
            assert any(item['path'].endswith('.' + bound) and str(limit) in item['message'] for item in details), details


def test_5000_samples_reject_before_source_reads_with_the_visible_bound(tmp_path, monkeypatch):
    worker, _ = open_analysis(analysis_system(tmp_path))
    request = raw_request()
    request['comparison_spec']['comparisons'][0]['evaluation_points'] = 5000
    monkeypatch.setattr(OperationToolContext, 'read_evidence', lambda *a: pytest.fail('read before argument correction'))
    reply = call_score(worker, request)
    diagnostic = reply['error']['data']['diagnostics'][0]
    assert diagnostic['path'] == '$.request.comparison_spec.comparisons[0].evaluation_points'
    assert diagnostic['message'] == 'Value must be at most 4096.'


def test_supported_log_and_linear_metrics_have_independent_known_values(tmp_path):
    sources, request = score_inputs()
    bundle = json.loads(sources['curve_bundle'])
    for series in bundle['series']:
        values = [10, 100] if series['series_key'] == 'reference' else [100, 1000]
        series['points'] = [dict(x=float(x), y=float(y)) for x, y in enumerate(values)]
    sources['curve_bundle'] = canonical_json(bundle)
    comparison = request['comparison_spec']['comparisons'][0]
    request['comparison_spec']['comparisons'] = [dict(
        comparison_key='known', reference_series='reference', candidate_series='candidate',
        domain={**comparison['domain'], 'min_points': 2}, interpolation='linear_y', evaluation_points=2,
        operators=[dict(operator_key=space, kind='residual_max_abs', value_space=space)
                   for space in ('linear', 'log10')])]
    parsed = AnalysisScoreInput.model_validate_json(canonical_json(dict(record_key='known', request=request)))
    context = SimpleNamespace(remaining_seconds=30,
        read_evidence=sources.__getitem__, finish_attempt=lambda **kwargs: None,
        workspace=tmp_path, accept_evidence=lambda **kwargs: {'alias': 'tool_evidence_001'})
    from scidiscovery.artifact_agent.operation_tool_context import OperationToolContext
    context.complete_calculation = lambda record, **kwargs: OperationToolContext.complete_calculation(context, record, **kwargs)
    record = score_tool(parsed, context)
    assert record['status'] == 'computed', record
    metrics = record['summary']['comparisons'][0]['metrics']
    assert {item['operator_key']: item['value'] for item in metrics} == {'linear': 900.0, 'log10': 1.0}


def test_string_axes_and_wrong_comparison_shape_reject_at_mcp_before_reads(tmp_path, monkeypatch):
    system = analysis_system(tmp_path)
    worker, _ = open_analysis(system)
    request = raw_request()
    request['sources'][0].update(x_axis='x', y_axis='ZnPhen')
    request['comparison_spec'] = {
        'operator': 'max_normalized_log_difference', 'pairs': [],
        'normalization_left': 1.0, 'normalization_right': 1.0,
    }
    def forbidden(*args):
        pytest.fail('invalid request reached an evidence read')
    monkeypatch.setattr(OperationToolContext, 'read_evidence', forbidden)
    response = call_score(worker, request)
    assert 'error' in response and 'result' not in response
    diagnostics = response['error']['data']['diagnostics']
    assert all(item['code'] == 'invalid_arguments' and item['phase'] == 'tool_arguments'
               for item in diagnostics)
    assert any(item['path'].endswith('.x_axis') for item in diagnostics)
    assert any(item['path'].endswith('.y_axis') for item in diagnostics)
    assert any(item['path'].endswith('.comparisons') for item in diagnostics)
    manifest = ToolEvidenceManifest.model_validate_json(system[1].runs._evidence_snapshot(worker._run_id))
    assert manifest.attempts[0].state == 'rejected'
    assert not manifest.attempts[0].read_sources


@pytest.mark.parametrize('change', ['operator', 'format', 'option'])
def test_unsupported_call_values_are_distinct_typed_errors(tmp_path, change):
    worker, _ = open_analysis(analysis_system(tmp_path))
    request = raw_request()
    if change == 'operator':
        request['comparison_spec']['comparisons'][0]['operators'][0]['kind'] = 'max_normalized_log_difference'
    elif change == 'format':
        request['sources'][0]['format'] = 'unimplemented_format'
    else:
        request['sources'][0]['unrecognized_option'] = 'DO_NOT_ECHO_VALUE'
    response = call_score(worker, request)
    diagnostics = response['error']['data']['diagnostics']
    expected_type = {'operator': 'literal_error', 'format': 'union_tag_invalid', 'option': 'extra_forbidden'}[change]
    assert any(item['type'] == expected_type for item in diagnostics)
    assert all(item['phase'] == 'tool_arguments' for item in diagnostics)
    assert 'DO_NOT_ECHO_VALUE' not in json.dumps(response)
    if change == 'operator':
        assert any('residual_max_abs' in item['message'] for item in diagnostics)


@pytest.mark.parametrize('explicit_defaults', [False, True])
def test_generic_tool_uses_defaults_without_rewriting_the_raw_receipt(explicit_defaults, tmp_path):
    sources, request = score_inputs()
    comparison = request['comparison_spec']['comparisons'][0]
    comparison.pop('evaluation_points')
    if explicit_defaults:
        comparison['evaluation_points'] = 257
    original = deepcopy(request)
    parsed = AnalysisScoreInput.model_validate_json(canonical_json(dict(record_key='score', request=request)))
    assert parsed.request.comparison_spec.comparisons[0].evaluation_points == 257
    record = evaluate_analysis_request(record_key='score', request=original, sources=sources)
    assert record.status == 'computed'
    assert record.model_dump(mode="json")["request"] == original
    replay_calculation(record, sources)


@pytest.mark.parametrize('kind', ['sprocess_plx', 'sprocess_log'])
def test_valid_tcad_sources_execute_with_omitted_and_explicit_defaults(kind):
    _, _, _, plx, csv = analysis_materials()
    request = raw_request()
    source = request['sources'][0]
    source['format'] = kind
    if kind == 'sprocess_log':
        source.pop('dataset_name')
        plx = (b'SCID_CURVE_V1|POINT|baseline|candidate|0|0|1e10\n'
               b'SCID_CURVE_V1|POINT|baseline|candidate|1|0.5|1e11\n'
               b'SCID_CURVE_V1|POINT|baseline|candidate|2|1|1e12\n'
               b'SCID_CURVE_V1|END|baseline|candidate|3\n')
    sources = {'solver_outputs_001': plx, 'reference_material': csv}
    first = evaluate_tcad_request(record_key='score', request=request, sources=sources)
    assert first.status == 'computed', first
    assert canonical_json(first.request) == canonical_json(request)
    assert 'min_points' not in first.request['sources'][0]
    explicit = deepcopy(request)
    explicit['sources'][0]['min_points'] = 2
    second = evaluate_tcad_request(record_key='score', request=explicit, sources=sources)
    assert second.status == 'computed'
    assert canonical_json(second.request) == canonical_json(explicit)
    assert first.result == second.result
    assert first.request != second.request


@pytest.mark.parametrize(('raw', 'status', 'reason'), [
    (b'"carrier"\n0 bad\n1 2\n', 'unavailable', 'tcad_source_data_invalid'),
    (b'"carrier"\n0 1\x0b1 2\n', 'unsupported', 'source_line_separator_unsupported'),
    (b'"carrier"\n' + b'0 1\n' * 65537, 'error', 'source_point_limit'),
    (b'"carrier"\n0 1\n', 'unavailable', 'tcad_source_data_invalid'),
    (b'"carrier"\n' + b'0 1\n' * 66000, 'error', 'source_line_limit'),
])
def test_valid_request_distinguishes_bad_data_unsupported_encoding_and_bounds(raw, status, reason):
    record = evaluate_tcad_request(record_key='score', request=raw_request(),
        sources={'solver_outputs_001': raw, 'reference_material': b'depth,carrier\n0,1\n1,2\n'})
    assert (record.status, record.reason_code) == (status, reason)
    assert record.result is None


def test_expired_valid_tcad_request_has_a_time_budget_reason():
    record = evaluate_tcad_request(record_key='score', request=raw_request(), sources={}, deadline=0.0)
    assert record.status == 'error' and record.reason_code == 'calculation_time_budget'


@pytest.mark.parametrize('exception', [TypeError, AttributeError, RuntimeError])
def test_unknown_calculator_failures_are_not_reported_as_bad_data(monkeypatch, exception):
    import curve_score.analysis_tool as analysis
    def broken(*args, **kwargs):
        raise exception('internal failure')
    monkeypatch.setattr(analysis, 'evaluate_curve_consistency', broken)
    sources, request = score_inputs()
    with pytest.raises(exception):
        evaluate_analysis_request(record_key='score', request=request, sources=sources)


def test_unknown_parser_failure_remains_a_framework_error(tmp_path, monkeypatch):
    import tcad_artifact.result_analysis as analysis
    system = analysis_system(tmp_path)
    worker, _ = open_analysis(system)
    def broken(*args, **kwargs):
        raise RuntimeError('DO_NOT_ECHO_PARSER_INTERNALS')
    monkeypatch.setattr(analysis, 'normalize_sprocess_plx', broken)
    response = call_score(worker, raw_request())
    diagnostic = response['error']['data']['diagnostics'][0]
    assert diagnostic['code'] == 'runtime_failure' and diagnostic['phase'] == 'tool_execution'
    assert 'DO_NOT_ECHO_PARSER_INTERNALS' not in json.dumps(response)
    assert 'reference' not in response['error']['data']['engineering']
    diagnostic = system[1].runs.diagnostic_summary(system[1].runs.status(worker._run_id))['latest_tool_error']
    from scidiscovery.artifact_agent.service.engineering_diagnostics import EngineeringDiagnostics
    store = EngineeringDiagnostics(system[1].runs.database_path.parent.parent / 'engineering-diagnostics')
    assert 'DO_NOT_ECHO_PARSER_INTERNALS' in store.read(diagnostic['engineering']['reference'],
        scopes=('instance:' + system[1].runs.status(worker._run_id).instance_id,))['text']
