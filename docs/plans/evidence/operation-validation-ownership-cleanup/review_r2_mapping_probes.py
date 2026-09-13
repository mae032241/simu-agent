import json
from pathlib import Path

def test_direct_alias_conflict_does_not_leave_a_guessed_control_mapping(tmp_path):
    from tests.operations.test_tcad_result_analysis import analysis_system, open_analysis, analysis_report, write_analysis
    system = analysis_system(tmp_path)
    worker, opened = open_analysis(system)
    report = analysis_report(alias='solver_outputs_001')
    report = json.loads(json.dumps(report).replace('raw_evidence', 'solver_outputs_001'))
    report['source_references'] = []
    report['evidence'][0]['locator'] = 'solver_outputs_002:row1'
    write_analysis(opened, report)
    first = worker.call_tool('worker_submit_result', {})
    assert first['state'] == 'rejected'
    path = Path(opened['output_directory'], 'result.json')
    report = json.loads(path.read_bytes())['payload']
    generated = report['source_references']
    report['evidence'][0]['locator'] = 'solver_outputs_001:row1'
    write_analysis(opened, report)
    second = worker.call_tool('worker_submit_result', {})
    print(json.dumps({'initial_rejection': first, 'control_generated_mapping': generated,
        'corrected_locator_reply': second}))
    assert second['state'] == 'completed'

def test_inline_calculation_and_raw_input_do_not_silently_share_one_source_key(tmp_path):
    from tests.operations.test_tcad_result_analysis import analysis_system, open_analysis, analysis_report, write_analysis, raw_request
    system = analysis_system(tmp_path)
    worker, opened = open_analysis(system)
    record = worker.call_tool('worker_tcad_curve_score', {'record_key': 'score', 'request': raw_request()})
    assert record['status'] == 'computed'
    report = analysis_report(alias='solver_outputs_001')
    report['source_references'] = []
    report['calculation_records'] = [record]
    report['evidence'].append({**report['evidence'][0], 'locator': 'calculation_records:score'})
    write_analysis(opened, report)
    reply = worker.call_tool('worker_submit_result', {})
    summary = {'state': reply['state']}
    if reply['state'] == 'completed':
        sealed = system[2].call_tool('run_status', {'name': 'analysis'})['sealed_output']['payload']
        summary.update(source_references=sealed['source_references'], evidence=sealed['evidence'])
    print(json.dumps(summary))
    assert reply['state'] == 'rejected'

def test_optional_citation_does_not_change_the_meaning_of_a_bound_alias(tmp_path):
    from tests.operations.test_tcad_result_analysis import analysis_system, open_analysis, analysis_report, write_analysis
    system = analysis_system(tmp_path)
    worker, opened = open_analysis(system)
    report = analysis_report(alias='solver_outputs_001')
    report = json.loads(json.dumps(report).replace('raw_evidence', 'solver_outputs_002'))
    report['evidence'][0]['locator'] = 'row1'
    write_analysis(opened, report)
    with_citation = worker.call_tool('worker_submit_result', {})
    assert with_citation['state'] == 'rejected'
    report['evidence'] = []
    write_analysis(opened, report)
    without_citation = worker.call_tool('worker_submit_result', {})
    print(json.dumps({'with_citation': with_citation, 'without_citation': without_citation,
        'unchanged_source_references': report['source_references']}))
    assert without_citation['state'] == with_citation['state']
