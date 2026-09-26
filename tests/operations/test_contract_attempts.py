"""Controlled failure receipts through the actual MCP and sealed Run boundary."""
import hashlib
import json

import pytest

from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.tool_evidence import ToolEvidenceManifest
from scidiscovery.artifact_agent.service.tool_evidence import ToolAttemptLimit
from scidiscovery.artifact_agent.service.run_records import RunStateConflict
from tests.operations.test_tcad_result_analysis import analysis_system, open_analysis, analysis_report, write_analysis


@pytest.mark.parametrize('direct', [False, True])
def test_domain_candidate_rejection_is_logged_once_with_returned_details(tmp_path, direct):
    from dataclasses import replace
    from scidiscovery.artifact_agent.service.local_workspace import WorkspaceError
    from tests.operations.test_tcad_result_analysis import raw_request
    system = analysis_system(tmp_path)
    worker, opened = open_analysis(system)
    write_analysis(opened, {})
    def validate(request, context):
        if direct:
            raise WorkspaceError('PRIVATE_WORKSPACE_DETAIL')
        context.validate_outputs()
    name = 'worker_tcad_curve_score'
    worker._registered[name] = replace(worker._registered[name], contextual_handler=validate, record_attempts=False)
    reply = worker.call_tool(name, dict(record_key='candidate', request=raw_request()))
    assert reply['state'] == 'rejected' and reply['diagnostics']
    runs = system[1].runs
    with runs._connect() as connection:
        rows = connection.execute("SELECT diagnostic_json FROM run_activity WHERE run_id=? AND activity='output_rejected'",
            (worker._run_id,)).fetchall()
    assert len(rows) == 1
    assert json.loads(rows[0][0])['details'] == reply['diagnostics']
    assert 'PRIVATE_WORKSPACE_DETAIL' not in json.dumps(reply)


@pytest.mark.parametrize('category', ['checker_failure', 'integrity_failure', 'admission_defect', 'tool_timeout'])
def test_domain_checker_preserves_its_specific_terminal_category(tmp_path, category):
    from dataclasses import replace
    from scidiscovery.artifact_agent.service.run_outputs import RunCheckerError
    from tests.operations.test_tcad_result_analysis import raw_request
    system = analysis_system(tmp_path)
    worker, _ = open_analysis(system)
    def fail(*args):
        raise RunCheckerError('controlled framework failure', category=category)
    name = 'worker_tcad_curve_score'
    worker._registered[name] = replace(worker._registered[name], contextual_handler=fail, record_attempts=False)
    assert worker.call_tool(name, dict(record_key='failure', request=raw_request()))['state'] == 'failed'
    runs = system[1].runs
    assert runs.diagnostic_summary(runs.status(worker._run_id))['failure']['category'] == category


@pytest.mark.parametrize('category', ['integrity_failure', 'admission_defect'])
@pytest.mark.parametrize('submit', [False, True])
def test_finalizer_failure_keeps_category_and_bounded_reason_through_control(tmp_path, monkeypatch, category, submit):
    from scidiscovery.artifact_agent.service.run_outputs import RunCheckerError
    system = analysis_system(tmp_path)
    worker, opened = open_analysis(system)
    write_analysis(opened, analysis_report())
    runs = system[1].runs
    reason = 'Controlled bound input fault. ' + 'x' * 600
    def fail(*args, **kwargs):
        raise RunCheckerError(reason, category=category)
    monkeypatch.setattr(runs, '_finalize_workspace', fail)
    if submit:
        assert worker.call_tool('worker_submit_result', {})['state'] == 'failed'
    else:
        with pytest.raises(RunCheckerError) as caught:
            runs.validate_candidate(worker._run_id)
        assert caught.value.category == category
    status = system[2].call_tool('run_status', {'name': 'analysis'})
    assert status['state'] == 'failed'
    assert status['reason'] == 'Run validation framework failure: ' + reason[:512]
    assert status['diagnostic_summary']['failure']['category'] == category
    assert status['diagnostic_summary']['rejection_count'] == 0


def test_unclassified_run_failure_is_runtime_failure_and_timeout_keeps_deadline_gate(tmp_path):
    system = analysis_system(tmp_path)
    worker, _ = open_analysis(system)
    runs = system[1].runs
    status = runs.status(worker._run_id)
    with pytest.raises(RunStateConflict, match='deadline has not expired'):
        runs.record_failure(status.run_id, reason='premature timeout', expected_state='running',
            expected_last_activity_at=status.last_activity_at, timed_out=True)
    assert runs.status(status.run_id).state == 'running'
    failed = runs.fail(status.run_id, reason='external Worker stopped')
    assert failed.reason == 'external Worker stopped'
    assert runs.diagnostic_summary(failed)['failure']['category'] == 'runtime_failure'


def test_unretainable_receipt_is_explicit_unknown_without_false_terminal_proof(tmp_path):
    from dataclasses import replace
    from scidiscovery.artifact_agent.interfaces.mcp_worker_protocol import WorkerToolError
    from scidiscovery.operation_contract import contract_diagnostic
    from tests.operations.test_tcad_result_analysis import raw_request
    system = analysis_system(tmp_path)
    worker, _ = open_analysis(system)
    name = 'worker_tcad_curve_score'
    def oversized_metadata(*args):
        # Inject an over-budget control metadata set; no raw source is read.
        worker._attempt_sources = {f'source_{i:03d}_' + 'x' * 110: {} for i in range(48)}
        raise WorkerToolError('bounded failure', details=(contract_diagnostic('invalid_arguments',
            phase='tool_arguments', affected_action='tool_call', message='A declared argument needs correction.'),))
    worker._registered[name] = replace(worker._registered[name], contextual_handler=oversized_metadata)
    reply = MCPRouter(worker, name='budget').handle(dict(jsonrpc='2.0', id=1, method='tools/call',
        params=dict(name=name, arguments=dict(record_key='unknown', request=raw_request()))))
    data = reply['error']['data']
    assert data['diagnostics'][0]['code'] == 'attempt_recording_failed'
    assert 'attempt' not in data
    attempts = system[1].runs.tool_attempts(worker._run_id)
    assert len(attempts) == 1 and attempts[0]['state'] == 'interrupted'


def test_argument_rejection_is_receipted_before_read_and_sealed_without_raw_files(tmp_path):
    system = analysis_system(tmp_path)
    worker, opened = open_analysis(system)
    request = {"record_key": ["DO_NOT_RECORD_REJECTED_VALUE"], "request": {}}
    response = MCPRouter(worker, name="probe").handle({"jsonrpc":"2.0", "id":1,
        "method":"tools/call", "params":{"name":"worker_tcad_curve_score", "arguments":request}})
    assert "error" in response and "result" not in response
    details = response["error"]["data"]
    assert details["diagnostics"][0]["path"] == "$.record_key"
    assert "attempt" not in details
    runs = system[1].runs
    snapshot = runs._evidence_snapshot(worker._run_id)
    assert b"DO_NOT_RECORD_REJECTED_VALUE" not in snapshot
    manifest = ToolEvidenceManifest.model_validate_json(snapshot)
    assert not manifest.records and manifest.bindings
    attempt = manifest.attempts[0]
    assert attempt.state == "rejected" and not attempt.read_sources
    assert attempt.request_digest == hashlib.sha256(canonical_json(request["request"])).hexdigest()
    assert attempt.diagnostics[0].code == "invalid_arguments"
    assert runs.diagnostic_summary(runs.status(worker._run_id))["latest_tool_error"]["details"][0]["path"] == "$.record_key"
    write_analysis(opened, analysis_report())
    submitted = worker.call_tool("worker_submit_result", {})
    assert submitted["state"] == "completed", submitted
    # Completion publishes the same manifest, even with no collected raw files.
    status = system[2].call_tool("run_status", {'name': "analysis", "intent": 'navigation'})
    assert len(status["evidence_outputs"]) == 1
    assert json.loads(runs._evidence_snapshot(worker._run_id)) == json.loads(snapshot)
    with pytest.raises(RunStateConflict):
        runs.begin_tool_attempt(worker._run_id, worker._registered["worker_tcad_curve_score"], {})


def test_attempt_limit_and_interrupted_calls_preserve_existing_receipts(tmp_path):
    system = analysis_system(tmp_path)
    worker, _ = open_analysis(system)
    runs = system[1].runs
    tool = worker._registered["worker_tcad_curve_score"]
    for i in range(64):
        runs.begin_tool_attempt(worker._run_id, tool, {"request":{"ordinal":i}})
    before = runs._evidence_snapshot(worker._run_id)
    with pytest.raises(ToolAttemptLimit):
        runs.begin_tool_attempt(worker._run_id, tool, {})
    assert runs._evidence_snapshot(worker._run_id) == before
    assert all(a["state"] == "interrupted" and a["result_status"] is None
               for a in json.loads(before)["attempts"])


def test_unknown_input_checker_error_is_engineering_failure_at_mcp():
    from types import SimpleNamespace
    from scidiscovery.operations.input_validation import validate_operation_inputs, ValidationSources
    from scidiscovery.operations.invoke import preflight_result
    def broken(_):
        raise RuntimeError("SECRET_INTERNAL_INPUT")
    compiled = SimpleNamespace(plugin_id="probe", spec=SimpleNamespace(input_validation=SimpleNamespace(
        validator=SimpleNamespace(plugin_id=None, component_id="check"))), implementations={"probe:check":broken})
    class Router:
        def call_tool(self, name, arguments):
            return preflight_result(lambda:validate_operation_inputs(compiled, ValidationSources({}, {})))
    reply = MCPRouter(Router(), name="probe").handle({"jsonrpc":"2.0", "id":1,
        "method":"tools/call", "params":{"name":"operation_preflight", "arguments":{}}})
    assert "error" in reply and "result" not in reply
    diagnostic = reply["error"]["data"]["diagnostics"][0]
    assert diagnostic["code"] == "input_checker_failed" and not diagnostic["repairable"]
    assert "SECRET_INTERNAL_INPUT" not in json.dumps(reply)


@pytest.mark.parametrize("rpc_request", [[], {"jsonrpc":"1.0","method":"tools/list"},
    {"jsonrpc":"2.0","method":"tools/call","params":[]},
    {"jsonrpc":"2.0","method":"tools/call","params":{"name":13}}])
def test_protocol_errors_never_reach_a_handler(rpc_request):
    class Never:
        def call_tool(self, *args):
            raise AssertionError("protocol error reached a tool")
    response=MCPRouter(Never(),name="probe").handle(rpc_request)
    assert response['error']['data']['diagnostics'][0]['phase']=='protocol'
