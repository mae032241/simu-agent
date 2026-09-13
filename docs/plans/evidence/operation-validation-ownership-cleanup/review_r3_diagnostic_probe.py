import json
from pathlib import Path
import pytest


def test_gap_handoff_error_points_to_its_actual_file(tmp_path):
    from tests.operations.test_l4_local_tcad import _system, _invoke, _debug_worker, _ImmediateDebugAdapter, _write_gap
    catalog, runtime, root, _ = _system(tmp_path, solver_kind='sprocess')
    _invoke(root, 'gap_author', 'tcad.deck.author.initial.v1', [
        {'port': 'execution_capability', 'artifact_names': ['execution_capability']},
        {'port': 'experiment_plan', 'artifact_names': ['experiment_plan']}])
    worker = _debug_worker(catalog, runtime, _ImmediateDebugAdapter(), tmp_path / 'unused-debug')
    opened = worker.call_tool('worker_open_assignment', {})
    _write_gap(opened)
    handoff = Path(opened['workspace_path']) / 'deck/handoff.json'
    payload = json.loads(handoff.read_bytes()); payload['summary'] = ''
    handoff.write_text(json.dumps(payload))
    rejected = worker.call_tool('worker_submit_result', {})
    assert rejected['state'] == 'rejected'
    payload['summary'] = 'Fixed fixture handoff.'; handoff.write_text(json.dumps(payload))
    corrected = worker.call_tool('worker_submit_result', {})
    assert corrected['state'] == 'completed'
    print(json.dumps({'rejection': rejected, 'correcting_handoff_only': corrected['state']}))
    assert rejected['diagnostics'][0]['path'] == '$.deck.handoff.summary'


@pytest.mark.parametrize('representation', ['inline', 'saved', 'both'])
def test_same_calculation_identity_can_use_its_two_supported_representations(tmp_path, representation):
    from tests.operations.test_tcad_result_analysis import analysis_system, open_analysis, analysis_report, write_analysis, raw_request
    worker, opened = open_analysis(analysis_system(tmp_path))
    record = worker.call_tool('worker_tcad_curve_score', {'record_key': 'score', 'request': raw_request()})
    assert record['status'] == 'computed'
    report = analysis_report(alias='solver_outputs_001')
    report['source_references'] = []
    report['calculation_records'] = [record]
    locators = {'inline': ['calculation_records:score'], 'saved': [record['calculation_ref']],
        'both': ['calculation_records:score', record['calculation_ref']]}[representation]
    for locator in locators:
        report['evidence'].append({**report['evidence'][0], 'source_key': 'same_score', 'locator': locator})
    write_analysis(opened, report)
    result = worker.call_tool('worker_submit_result', {})
    print(json.dumps({'representation': representation, 'same_tool_return': True, 'result': result}))
    assert result['state'] == 'completed'
