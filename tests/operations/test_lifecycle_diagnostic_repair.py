"""Repairs cross the real Worker, durable diagnostic, Root and execution boundaries."""
import hashlib
import json
from types import SimpleNamespace

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_worker_protocol import WorkerToolError
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.operation_contract import contract_diagnostic
from tests.operations.test_experiment_continuation import continuation, submit
from tests.operations.test_experiment_approval_handoff import experiment, start, decide


def pending_execution(f, name="obsolete"):
    execution_id = "exe_" + hashlib.sha256(canonical_json({"task": f.run_id, "name": name})).hexdigest()
    old_id = next(b.object_id for b in f.runtime.scheduler_bindings.list(
        instance=f.instance.instance_id, namespace="execution")
        if f.runtime.executions.status(b.object_id).state == "collected")
    original = f.runtime.executions.request(old_id)
    f.runtime.executions.create(executor=original.executor, preparation_profile=original.preparation_profile,
        payload_ref=original.payload_ref, execution_id=execution_id, compiled_identity=original.compiled_identity,
        labels={"experiment_run": f.run_id})
    f.runtime.scheduler_bindings.bind(instance=f.instance.instance_id, namespace="execution",
        name="experiment-" + f.run_id + "-" + name, object_id=execution_id)
    return execution_id


def test_pending_request_repair_preserves_science_and_is_visible_while_running(tmp_path, monkeypatch):
    f = continuation(tmp_path, monkeypatch, all_stages=True)
    execution_id = pending_execution(f)
    aliases = [i.source_name for i in f.runs.status(f.run_id).inputs if i.port_name == "scientific_materials"]
    rejected = submit(f, aliases)
    assert rejected["state"] == "rejected"
    detail = rejected["diagnostics"][0]
    assert detail["code"] == "experiment_outstanding_work"
    assert detail["phase"] == "protocol" and detail["path"] == "$"
    assert "obsolete" in detail["message"] and "action='cancel'" in detail["message"]
    assert "rule_id" not in detail
    saved = (f.workspace / "output/result.json").read_bytes()
    page = f.root.call_tool("run_status", {"name": "continuation", "intent": "status", "diagnostic_after": 0})
    diagnostic = page["diagnostic_events"]["events"][-1]["diagnostic"]
    assert diagnostic["repairable_by_output"] is False
    assert diagnostic["details"][0]["message"] == detail["message"]
    assert diagnostic["details"][0]["code"] == detail["code"]
    assert "safe_details_version" not in json.dumps(page)
    assert f.worker.call_tool("worker_experiment_execute", {"action": "cancel", "name": "obsolete"})["state"] == "abandoned"
    assert f.runtime.executions.status(execution_id).external_run_id is None
    assert (f.workspace / "output/result.json").read_bytes() == saved
    assert f.worker.call_tool("worker_submit_result", {})["state"] == "completed"


def test_safe_diagnostics_round_trip_but_incoming_trust_flags_do_not(tmp_path, monkeypatch):
    f = continuation(tmp_path, monkeypatch)
    detail = contract_diagnostic("fixture_repair", phase="output_payload", affected_action="submit",
        path="$.payload.adopted_stages", message="Bind the original execution before adopting its validity stage.",
        rule_id="experiment.sealed_material", repairable=True)
    for details in ([detail], [{**detail, "message": "PRIVATE_INPUT_SHOULD_NOT_APPEAR"}]):
        f.runs.record_error_observation(f.run_id, "output_rejected", diagnostic={
            "category": "output_rejected", "details": details, "safe_details_version": 1})
    page = f.root.call_tool("run_status", {"name": "continuation", "intent": "status", "diagnostic_after": 0})
    events = page["diagnostic_events"]["events"]
    first = events[-2]["diagnostic"]["details"][0]
    assert first["message"] == detail["message"]
    assert first["code"] == "fixture_repair" and first["phase"] == "output_payload"
    assert "PRIVATE_INPUT_SHOULD_NOT_APPEAR" not in json.dumps(page)


@pytest.mark.parametrize("tool,arguments,code,reason", [
    ("worker_experiment_prepare", {"project_path": "scratch/missing.json"}, "implementation_file_unavailable", "absent"),
    ("worker_experiment_execute", {"action": "start"}, "experiment_implementation_required", "Choose"),
    ("worker_experiment_debug", {"name": "missing"}, "experiment_implementation_required", "Choose"),
    ("worker_publish_files", {"files": [{"path": "output/extra.csv", "purpose": "Fixture"}], "source_aliases": ["objective_source"]}, "attachment_publication_invalid", "scratch/"),
    ("worker_helper", {"name": "empty"}, "helper_admission_rejected", "subtask"),
])
def test_owner_declared_corrections_survive_worker_and_root(tmp_path, monkeypatch, tool, arguments, code, reason):
    f = continuation(tmp_path, monkeypatch)
    with pytest.raises(WorkerToolError) as caught:
        f.worker.call_tool(tool, arguments)
    detail = caught.value.details[0]
    from scidiscovery.plugin_runtime.transport import rpc_error
    wire = rpc_error(1, caught.value)["error"]
    assert "engineering" not in wire["data"]
    assert wire["message"] == detail["message"]
    assert detail["code"] == code and detail["phase"] == "tool_arguments"
    assert reason in detail["message"]
    events = f.root.call_tool("run_status", {"name": "continuation", "intent": "status", "diagnostic_after": 0})["diagnostic_events"]["events"]
    assert events[-1]["diagnostic"]["details"][0]["message"] == detail["message"]
    assert events[-1]["diagnostic"]["details"][0]["code"] == code


def test_status_and_cancel_need_no_new_effect_contract_or_material_binding(tmp_path, monkeypatch):
    f = continuation(tmp_path, monkeypatch)
    pending_execution(f)
    def forbidden(*args, **kwargs):
        pytest.fail("cleanup must not require new Effect admission or scientific material binding")
    monkeypatch.setattr(f.coordinator, "_contract", forbidden)
    monkeypatch.setattr(f.coordinator, "_implementation_record", forbidden)
    for action, expected in (("status", "created"), ("cancel", "abandoned"), ("status", "abandoned")):
        assert f.worker.call_tool("worker_experiment_execute", {"action": action, "name": "obsolete"})["state"] == expected
    assert f.worker.call_tool("worker_experiment_execute", {"action": "status", "name": "absent"}) == {
        "name": "absent", "state": "not_created", "submission": "not_submitted"}


@pytest.mark.parametrize("ending", ["reject_execution", "cancel_approval", "expired"])
def test_closed_approval_retires_unsubmitted_execution_and_allows_delivery(tmp_path, monkeypatch, ending):
    f = experiment(tmp_path, monkeypatch)
    first = start(f)
    if ending == "expired":
        approval_id = f.runtime.scheduler_bindings.resolve(instance=f.instance.instance_id,
            namespace="approval", name=first["approval_name"])
        f.runtime.approvals.expire_pending(approval_id)
    else:
        decide(f, first, ending)
    result = f.worker.call_tool("worker_experiment_execute", {"action": "status"})
    assert result["execution_state"] == "abandoned"
    assert "review_url" not in result and f.adapter.submits == 0
    assert submit(f, [f.alias], "blocked")["state"] == "completed"


def test_cancel_pending_execution_retires_approval_without_human_decision(tmp_path, monkeypatch):
    f = experiment(tmp_path, monkeypatch)
    first = start(f)
    assert f.worker.call_tool("worker_experiment_execute", {"action": "cancel"})["state"] == "abandoned"
    status = f.root.call_tool("approval_status", {"name": first["approval_name"]})
    assert status["status"] == "expired"
    assert f.adapter.submits == 0


def test_uncertain_submission_is_not_abandoned_by_approval_reconciliation(tmp_path, monkeypatch):
    f = experiment(tmp_path, monkeypatch)
    first = start(f)
    approval_id = f.runtime.scheduler_bindings.resolve(instance=f.instance.instance_id,
        namespace="approval", name=first["approval_name"])
    f.runtime.approvals.expire_pending(approval_id)
    monkeypatch.setattr(f.runtime.executions, "prepared_submission", lambda _: object())
    result = f.worker.call_tool("worker_experiment_execute", {"action": "status"})
    assert result["state"] == "authorization_expired" and result["execution_state"] == "created"
    assert f.adapter.submits == 0


def test_effect_backend_failure_is_engineering_not_invalid_science():
    from scidiscovery.artifact_agent.interfaces.mcp_root_execution_routes import RootExecutionRoutes
    from scidiscovery.operations.input_validation import OperationEngineeringError
    from unittest.mock import Mock
    bound = SimpleNamespace(compiled=SimpleNamespace(spec=SimpleNamespace(executor=SimpleNamespace(preparation=None))),
        inputs=(SimpleNamespace(port_name="payload", artifact=SimpleNamespace(ref=object())),))
    facade = SimpleNamespace(execution_bridge=SimpleNamespace(validate_request=Mock(side_effect=ConnectionError("PRIVATE_BACKEND_ADDRESS"))),
        artifacts=SimpleNamespace(read=lambda _: b"{}"))
    plan = SimpleNamespace(payload_port="payload", executor="fixture:solver", preparation_profile="fixture")
    with pytest.raises(OperationEngineeringError) as caught:
        RootExecutionRoutes._effect_admission(facade, bound, plan)
    assert caught.value.reason_code == "effect_admission_failed"
    detail = caught.value.details[0]
    assert detail["phase"] == "tool_execution" and detail["repairable"] is False
    assert "PRIVATE_BACKEND_ADDRESS" not in json.dumps(detail)


def test_engineering_failure_returns_readable_scoped_locator_without_inline_trace(tmp_path, monkeypatch):
    from scidiscovery.plugin_runtime.transport import rpc_error
    from scidiscovery.artifact_agent.service.engineering_diagnostics import EngineeringDiagnostics, diagnostic_locator
    f = experiment(tmp_path, monkeypatch)
    first = start(f)
    decide(f, first, 'authorize_execution')
    def broken(*args, **kwargs):
        raise RuntimeError('fixture backend failed at /private/host/path token=do-not-expose')
    monkeypatch.setattr(f.adapter, 'prepare', broken)
    with pytest.raises(WorkerToolError) as caught:
        f.worker.call_tool('worker_experiment_execute', {'action': 'advance'})
    wire = rpc_error(1, caught.value)['error']
    locator = wire['data']['engineering']
    assert set(locator) == {'category', 'reference', 'available_sections'}
    assert locator['available_sections'] == ['summary', 'traceback']
    assert 'do-not-expose' not in json.dumps(wire)
    page = f.root.call_tool('run_status', {'name': 'continuation', 'intent': 'status', 'diagnostic_after': 0})
    saved = page['diagnostic_events']['events'][-1]['diagnostic']['engineering']
    assert saved == {k: locator[k] for k in ('reference', 'available_sections')}
    read = f.root.call_tool('diagnostic_read', {'reference': saved['reference'], 'max_bytes': 1024})
    assert 'fixture backend failed' in read['text']
    assert 'do-not-expose' not in json.dumps(page) + json.dumps(read)
    assert '/private/host/path' not in json.dumps(read)
    store = EngineeringDiagnostics(f.runs.database_path.parent.parent / 'engineering-diagnostics')
    with pytest.raises(ValueError, match='another instance'):
        store.read(saved['reference'], scopes=('instance:another',))
    assert diagnostic_locator({'reference': '../private', 'available_sections': ['traceback']}) == {}
    assert diagnostic_locator({**locator, 'causes': ['private'], 'available_sections': ['private']}) == {
        'reference': saved['reference'], 'available_sections': []}
    assert f.adapter.submits == 0


@pytest.mark.process_e2e
def test_worker_diagnostic_locator_survives_real_proxy_and_daemon(tmp_path, monkeypatch):
    import multiprocessing
    import os
    import subprocess
    import sys
    import time
    from scidiscovery.plugin_runtime.transport import UnixSocketDaemon
    from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
    f = continuation(tmp_path, monkeypatch)
    def broken(*args, **kwargs):
        raise RuntimeError('fixture heartbeat service unavailable token=do-not-expose')
    monkeypatch.setattr(f.runs, 'heartbeat', broken)
    socket = tmp_path / 'worker.sock'
    process = multiprocessing.get_context('fork').Process(target=lambda:
        UnixSocketDaemon(socket, MCPRouter(f.worker, name='diagnostic-test')).serve_forever())
    process.start()
    try:
        deadline = time.monotonic() + 5
        while not socket.exists() and time.monotonic() < deadline:
            time.sleep(.02)
        assert socket.exists()
        request = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': 'worker_heartbeat', 'arguments': {}, '_meta': {
                'x-codex-turn-metadata': {'session_id': 'continuation-fixture',
                    'thread_id': 'next-owner', 'thread_source': 'subagent'}}}}
        response = subprocess.run([sys.executable, '-m',
            'scidiscovery.artifact_agent.interfaces.mcp_proxy', '--socket', str(socket)],
            input=json.dumps(request)+'\n', text=True, capture_output=True, timeout=10,
            env=dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path)))
        assert response.returncode == 0, response.stderr
        error = json.loads(response.stdout)['error']
        assert 'do-not-expose' not in json.dumps(error)
        assert 'reference' in error['data'].get('engineering', {}), error
        reference = error['data']['engineering']['reference']
        page = f.root.call_tool('run_status', {'name': 'continuation', 'intent': 'status', 'diagnostic_after': 0})
        assert page['diagnostic_events']['events'][-1]['diagnostic']['engineering']['reference'] == reference
        read = f.root.call_tool('diagnostic_read', {'reference': reference})
        assert 'fixture heartbeat service unavailable' in read['text']
        assert 'do-not-expose' not in read['text']
    finally:
        process.terminate()
        process.join(3)
        if process.is_alive():
            process.kill()
            process.join(3)
