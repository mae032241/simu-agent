"""Conditional case correspondence is a report claim, not mutable file metadata."""
import json
import pytest

from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
from tests.operations.test_tcad_result_analysis import analysis_system, open_analysis, raw_request, analysis_report, write_analysis


@pytest.mark.parametrize('reference_mode', ['different_rationale', 'record_only'])
def test_undeclared_case_records_mapping_once_without_submit_replay(tmp_path, monkeypatch, reference_mode):
    system = analysis_system(tmp_path, mapped=False)
    worker, opened = open_analysis(system)
    request = raw_request()
    rpc = MCPRouter(worker, name="probe")
    def score(value):
        return rpc.handle({"jsonrpc":"2.0", "id":1, "method":"tools/call", "params":{
            "name":"worker_tcad_curve_score", "arguments":{"record_key":"conditional", "request":value}}})
    rejected = score(request)
    assert rejected['error']['data']['diagnostics'][0]['code'] == 'case_mapping_invalid'
    basis = dict(kind='evidence', evidence_refs=[dict(input_alias='experiment_plan',
        locator='/proposals/0/cases/0')], rationale='Fixture mapping to the exact declared plan case; sufficiency remains reviewable.')
    request['sources'][0]['case_mapping_basis'] = basis
    reply = score(request)
    assert 'result' in reply, reply
    record = reply['result']['structuredContent']
    assert record['status'] == 'computed', record
    report = analysis_report(alias='solver_outputs_001', output_name='A', mapped=True)
    report['calculation_records'] = [record]
    report['evidence'].append(dict(source_key='independent_calculation_evidence',
        source_type='runtime_output', title='Exact calculation', locator='calculation_records:conditional'))
    report['source_references'][0]['case_mapping_basis'] = {**basis, 'rationale':'A different claimed basis.'}
    if reference_mode == 'record_only':
        report['source_references'] = []
        report['evidence'] = report['evidence'][1:]
        for gate in report['gates'].values():
            if isinstance(gate, dict) and gate.get('evidence_keys'):
                gate['evidence_keys'] = ['independent_calculation_evidence']
    def never(*args, **kwargs):
        raise AssertionError('submit must not recompute a controlled calculation')
    monkeypatch.setattr('tcad_artifact.result_analysis.evaluate_tcad_request', never)
    write_analysis(opened, report)
    submitted = worker.call_tool('worker_submit_result', {})
    assert submitted['state'] == 'completed', submitted
    manifest = json.loads(system[1].runs._evidence_snapshot(worker._run_id))
    assert len(manifest['attempts']) == 2
    assert manifest['attempts'][0]['state'] == 'rejected'
    assert manifest['attempts'][1]['state'] == 'completed'


def test_evidence_basis_cannot_override_declared_case(tmp_path):
    system = analysis_system(tmp_path)
    worker, _ = open_analysis(system)
    request = raw_request()
    request['sources'][0].update(case_key='not_a_planned_case', case_mapping_basis=dict(
        kind='evidence', evidence_refs=[dict(input_alias='experiment_plan',locator='/proposals/0')],
        rationale='An incompatible claimed case.'))
    reply = MCPRouter(worker,name='probe').handle({'jsonrpc':'2.0','id':1,'method':'tools/call',
        'params':{'name':'worker_tcad_curve_score','arguments':{'record_key':'wrong','request':request}}})
    assert reply['error']['data']['diagnostics'][0]['code'] == 'case_mapping_invalid'
    attempt = system[1].runs.tool_attempts(worker._run_id)[0]
    assert 'solver_outputs_001' not in attempt['read_sources']
