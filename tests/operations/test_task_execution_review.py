"""An explicit scientific task requirement, never a global stage-review gate."""
import json
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.operation_contract import DiagnosticError
from tests.operations.test_experiment_continuation import continuation


def review(f, name, subject, verdict):
    result = f.root.call_tool("operation_invoke", {"name": name, "operation_id": "science.object.review.v1",
        "inputs": [{"port": "subject", "artifact_names": [subject]}], "instruction": "Assess this exact implementation."})
    assert result["result"]["state"] == "queued", result
    run_id = f.runtime.scheduler_bindings.resolve(instance=f.instance.instance_id, namespace="run", name=name)
    f.runs.worker_connections.attach(run_id=run_id, platform_session="review-session", thread_id=name)
    compiled = f.catalog.operation("science.object.review.v1")
    worker = LocalWorkerMCPRouter(f.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest,
        run_id=run_id, trusted_caller=("review-session", name))
    opened = worker.call_tool("worker_open_assignment", {})
    Path(opened["output_directory"], "result.json").write_text(json.dumps({"schema_version": 1,
        "payload": {"verdict": verdict, "summary": "Exact fixture assessment."}}))
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"


def test_explicit_review_blocks_missing_wrong_subject_and_negative_verdict(tmp_path, monkeypatch):
    f = continuation(tmp_path, monkeypatch, require_execution_review=True)
    assert f.runs.status(f.run_id).recovery_policy["require_execution_review"] is True
    assignment = json.loads((f.workspace / "assignment.json").read_bytes())
    assert assignment["execution_requirements"]["independent_implementation_review"] == "required"
    command = {"action": "start", "implementation": f.alias}
    def blocked(code):
        with pytest.raises(DiagnosticError) as caught:
            f.worker.call_tool("worker_experiment_execute", command)
        assert caught.value.details[0]["code"] == code
        assert not f.runtime.scheduler_bindings.list(instance=f.instance.instance_id, namespace="execution",
            name_prefix="experiment-" + f.run_id + "-")
    blocked("experiment_execution_review_required")
    review(f, "wrong-subject", "observe.output", "pass")
    blocked("experiment_execution_review_required")
    subject = next(i.artifact_name for i in f.runs.status(f.run_id).inputs if i.source_name == f.alias)
    review(f, "negative-review", subject, "revise")
    blocked("experiment_execution_review_not_passed")
    review(f, "passing-review", subject, "pass")
    adapter = f.coordinator.bridge._adapter("tcad_artifact:tcad")
    adapter.lookup_submission = lambda _: None
    adapter.state = "running"
    adapter.submit = lambda *args, **kwargs: ("new-reviewed-execution", "running")
    assert f.worker.call_tool("worker_experiment_execute", command)["state"] == "running"
    bound = f.runtime.scheduler_bindings.list(instance=f.instance.instance_id, namespace="execution",
        name_prefix="experiment-" + f.run_id + "-")[0]
    envelope = f.runtime.artifacts.get_by_id(f.runtime.executions.request_artifact_id(bound.object_id))
    assert "implementation_review" in envelope.labels


def test_review_requirement_is_in_normalized_request_and_cannot_be_removed_on_recovery(tmp_path, monkeypatch):
    f = continuation(tmp_path, monkeypatch, require_execution_review=True)
    current = f.runs.status(f.run_id)
    f.runs.record_failure(f.run_id, reason="fixture stop", expected_state=current.state,
        expected_last_activity_at=current.last_activity_at)
    request = {**f.invocation, "name": "recovered", "resume_from": "continuation"}
    request.pop("require_execution_review")
    check = f.root.call_tool("operation_preflight", request)
    assert check["admissible"] is True, check
    assert check["normalized_request"]["require_execution_review"] is True
    bad = f.root.call_tool("operation_preflight", {**request, "require_execution_review": False})
    assert bad["admissible"] is False
    assert "execution_review_requirement_immutable" in json.dumps(bad)
    reply = f.root.call_tool("operation_invoke", check["normalized_request"])
    assert reply["result"]["state"] == "queued", reply
