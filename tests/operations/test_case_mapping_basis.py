"""Conditional case correspondence is a report claim, not mutable file metadata."""
import json
from pathlib import Path
import pytest

from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
from tests.operations.test_tcad_result_analysis import analysis_system, open_analysis, raw_request, analysis_report, write_analysis




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
