"""Historical canonical vector captured before shared support was introduced."""
import json
from pathlib import Path

import pytest

from curve_score.analysis_tool import evaluate_analysis_request, replay_calculation
from curve_score.schema import CurveBundle, CurveConsistencyReport, metric_bundle_matches
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.plugin_runtime.calculations import CalculationResult
from scidiscovery.operation_contract import SemanticRuleViolation

SUPPORT_CASES = ('none', 'covering_interval', 'gap', 'exclusion', 'outside_exclusion', 'unavailable')
SUPPORT_OPERATORS = ('residual_rms', 'point_difference', 'crossing_shift', 'width_shift')


def support_case(support, operator):
    value = json.loads((Path(__file__).parents[1] / 'fixtures/curve_calculation_pre_support.json').read_text())
    bundle = json.loads(value['sources']['curve_bundle'])
    request = value['record']['request']
    series = bundle['series'][0]
    comparison = request['comparison_spec']['comparisons'][0]
    if support == 'covering_interval':
        series['valid_intervals'] = [{'start': 0., 'stop': 1.}]
    elif support == 'gap':
        series['valid_intervals'] = [{'start': 0., 'stop': .4}, {'start': .6, 'stop': 1.}]
    elif support == 'exclusion':
        series['exclusions'] = [{'start': .2, 'stop': .4}]
    elif support == 'outside_exclusion':
        series['exclusions'] = [{'start': .8, 'stop': 1.}]
        comparison['domain']['stop'] = .5
    elif support == 'unavailable':
        series['availability'].update(status='unavailable', reason_code='source_missing')
    op = {'operator_key': 'probe', 'kind': operator, 'value_space': 'linear'}
    if operator == 'point_difference':
        op['x'] = .25
    if operator in {'crossing_shift', 'width_shift'}:
        op['level'] = 5e10
    if operator == 'width_shift':
        op['second_level'] = 8e10
    comparison['operators'] = [op]
    return request, {'curve_bundle': canonical_json(bundle)}


def historical():
    value = json.loads((Path(__file__).parents[1] / 'fixtures/curve_calculation_pre_support.json').read_text())
    return CalculationResult.model_validate_json(canonical_json(value['record'])), {k: v.encode() for k, v in value['sources'].items()}


def test_old_exact_vector_replays_and_new_records_have_a_new_version():
    record, sources = historical()
    original = record.canonical_json()
    replay_calculation(record, sources)
    assert record.canonical_json() == original
    current = evaluate_analysis_request(record_key=record.record_key, request=record.request, sources=sources)
    assert current.algorithm_version == 'analysis-curve-operators.v2'
    assert current.result['comparisons'] == record.result['comparisons']
    replay_calculation(current, sources)
    # The intervening deployed V1 included the new default in the digest.
    interim = evaluate_analysis_request(record_key=record.record_key, request=record.request,
        sources=sources, algorithm_version='analysis-curve-operators.v1')
    replay_calculation(interim, sources)
    report = CurveConsistencyReport.model_validate_json(canonical_json(record.result))
    from curve_score.analysis_tool import bundle_from_sources, parse_score_request, AnalysisScoreRequest
    bundle = bundle_from_sources(parse_score_request(AnalysisScoreRequest, record.request), sources)
    assert metric_bundle_matches(bundle, report)
    assert not metric_bundle_matches(bundle, report.model_copy(update={'operator_version': 'curve-operators.v2'}))


@pytest.mark.parametrize('damage', ['number', 'digest', 'source', 'version'])
def test_legacy_compatibility_does_not_relax_exact_replay(damage):
    record, sources = historical()
    document = record.model_dump(mode='json')
    if damage == 'number':
        document['result']['comparisons'][0]['metrics'][0]['value'] += 1
    elif damage == 'digest':
        document['result']['curve_bundle_sha256'] = 'a' * 64
    elif damage == 'source':
        sources['curve_bundle'] += b' '
    else:
        document['algorithm_version'] = 'analysis-curve-operators.v2'
    with pytest.raises(SemanticRuleViolation):
        replay_calculation(CalculationResult.model_validate_json(canonical_json(document)), sources)


@pytest.mark.parametrize('support', SUPPORT_CASES)
@pytest.mark.parametrize('operator', SUPPORT_OPERATORS)
def test_historical_support_semantics_replay_from_fixed_vectors(support, operator):
    import hashlib
    request, sources = support_case(support, operator)
    vectors = json.loads((Path(__file__).parents[1] / 'fixtures/curve_support_v1.json').read_text())
    vector = vectors['cases'][operator + '/' + support]
    record = CalculationResult.model_validate_json(canonical_json(dict(
        record_key='old', request=request, input_digests={k: hashlib.sha256(v).hexdigest() for k, v in sources.items()},
        algorithm_version='analysis-curve-operators.v1', status=vector['status'],
        reason_code=vector['reason_code'], result=vector['result'])))
    # The expected digest and numerical result were captured with the actual
    # pre-4872459 evaluator. CI never imports git history or an external image.
    assert hashlib.sha256(record.canonical_json()).hexdigest() == vector['record_sha256']
    replay_calculation(record, sources)
