"""Typed score requests reach parsing only after admission, preserving raw JSON."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from curve_score.analysis_tool import (
    AnalysisScoreInput, evaluate_analysis_request, replay_calculation, score_tool,
)
from scidiscovery.artifact_agent.operation_tool_context import OperationToolContext
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.layered_diagnosis import CalculationRecord
from scidiscovery.artifact_agent.schema.tool_evidence import ToolEvidenceManifest
from tcad_artifact.result_analysis import TCADScoreInput, evaluate_tcad_request
from tests.operations.test_result_analysis_tool import score_inputs


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


@pytest.mark.parametrize('exception', [TypeError, AttributeError, RuntimeError])
def test_unknown_calculator_failures_are_not_reported_as_bad_data(monkeypatch, exception):
    import curve_score.analysis_tool as analysis
    def broken(*args, **kwargs):
        raise exception('internal failure')
    monkeypatch.setattr(analysis, 'evaluate_curve_consistency', broken)
    sources, request = score_inputs()
    with pytest.raises(exception):
        evaluate_analysis_request(record_key='score', request=request, sources=sources)
