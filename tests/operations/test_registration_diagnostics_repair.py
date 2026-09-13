"""Registration semantics and durable diagnostics through real control entrypoints."""
from copy import deepcopy
import json

import pytest
from pydantic import ValidationError

from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.experiment import ExperimentPortfolio
from scidiscovery.artifact_agent.schema.experiment_intent import (
    ExperimentDesignIntent, materialize_experiment_design_intent,
)
from scidiscovery.artifact_agent.schema.research_objective import ResearchObjectiveContract
from scidiscovery.artifact_agent.service.run_outputs import RunOutputError
from scidiscovery.operation_contract import contract_diagnostic
from tests.operations.test_agent_contract_alignment import (
    experiment_case, _experiment_run, _experiment_envelope, _review_run,
)
from tests.operations.test_tcad_result_analysis import (
    analysis_system, open_analysis, analysis_report, write_analysis,
)


def wire(router, name, arguments):
    return MCPRouter(router, name="diagnostic-regression").handle({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    })


@pytest.mark.parametrize("derive_baseline", [False, True])
def test_prose_and_baseline_labels_survive_submit_materialize_and_review(tmp_path, experiment_case, derive_baseline):
    intent, sources = deepcopy(experiment_case)
    intent["objective_key"] = "objective_expected"
    proposal = intent["proposals"][0]
    proposal["identifiability_claims"] = [{
        "hypothesis_key": "hypothesis_a", "observable": "Combined depth and normalized shape response",
        "distinguishing_outcome": "The response distinguishes the stated alternatives.",
        "decision_rule": "Review the supplied response.", "ambiguity_conditions": ["Finite support."],
        "smallest_resolving_control": "The existing bounded comparison.",
    }]
    if derive_baseline:
        proposal.pop("baseline_case_key")
    else:
        proposal["cases"][0]["scientific_role"] = "perturbation"
    (tmp_path / "design").mkdir()
    (tmp_path / "review").mkdir()
    runtime, run_id, output = _experiment_run(tmp_path / "design", sources)
    output.write_bytes(_experiment_envelope(intent))
    assert runtime.runs.submit(run_id) == ("completed", ())
    sealed = runtime.artifacts.read(runtime.runs.status(run_id).output_ref)
    plan = materialize_experiment_design_intent(
        ExperimentDesignIntent.model_validate_json(sealed),
        ResearchObjectiveContract.model_validate_json(sources["research_objective"]),
    )
    assert plan.proposals[0].comparison_contract.baseline_case_key == "baseline"
    assert len(plan.proposals[0].comparison_contract.variables) == 1
    raw = plan.model_dump(mode="json")
    raw["proposals"][0]["comparison_contract"]["required_observables"] = ["A different description of the same observation"]
    parsed = ExperimentPortfolio.model_validate_json(canonical_json(raw))
    revised = deepcopy(raw)
    revised["priority_rationale"] += " Preserve the comparison during this revision."
    (tmp_path / "revision").mkdir()
    runtime, revision_id, workspace = _review_run(tmp_path / "revision", {
        "prior_draft": parsed.canonical_json(),
        "change_request": canonical_json({"review_target": "experiment_portfolio", "verdict": "revise",
                                          "summary": "Clarify the next bounded comparison."}),
    }, operation_id="science.experiment.revise.v1")
    (workspace.output_directory / "result.json").write_bytes(_experiment_envelope(revised))
    assert runtime.runs.submit(revision_id) == ("completed", ())
    runtime, review_id, workspace = _review_run(tmp_path / "review", {"experiment_plan": parsed.canonical_json()})
    (workspace.output_directory / "result.json").write_bytes(canonical_json({
        "schema_version": 1, "handoff": {"verdict": "revise", "summary": "Independent coverage review."},
        "payload": {"review_target": "experiment_portfolio", "verdict": "revise",
                    "summary": "Scientific coverage remains a reviewer judgment."},
    }))
    assert runtime.runs.submit(review_id) == ("completed", ())
    raw["proposals"][0]["comparison_contract"]["baseline_case_key"] = "unknown_case"
    for variable in raw["proposals"][0]["comparison_contract"]["variables"]:
        for expectation in variable["expectations"]:
            if expectation["case_key"] == "baseline":
                expectation["case_key"] = "unknown_case"
    with pytest.raises(ValidationError, match="undeclared experiment case"):
        ExperimentPortfolio.model_validate_json(canonical_json(raw))


def test_real_variable_conflict_is_precise_and_correctable_without_cascade(tmp_path, experiment_case):
    intent, sources = deepcopy(experiment_case)
    intent["objective_key"] = "objective_expected"
    intent["proposals"][0]["variables"][0]["comparison_role"] = "frozen"
    runtime, run_id, output = _experiment_run(tmp_path, sources)
    output.write_bytes(_experiment_envelope(intent))
    state, details = runtime.runs.submit(run_id)
    assert state == "rejected"
    assert len(details) == 1, details
    assert details[0]["path"] == "$.payload.proposals[0].variables[0].comparison_role"
    assert details[0]["rule_id"] == "experiment.design.intent_closure"
    intent["proposals"][0]["variables"][0]["comparison_role"] = "intended_change"
    output.write_bytes(_experiment_envelope(intent))
    assert runtime.runs.submit(run_id) == ("completed", ())


def test_missing_ambiguous_baseline_and_true_empty_cases_remain_rejected(experiment_case):
    intent, _ = deepcopy(experiment_case)
    proposal = intent["proposals"][0]
    proposal.pop("baseline_case_key")
    for case in proposal["cases"]:
        case["scientific_role"] = "perturbation"
    with pytest.raises(ValidationError, match="unambiguous baseline"):
        ExperimentDesignIntent.model_validate_json(canonical_json(intent))
    proposal["cases"] = []
    with pytest.raises(ValidationError):
        ExperimentDesignIntent.model_validate_json(canonical_json(intent))


def test_derived_plan_failure_keeps_payload_owner(tmp_path, experiment_case):
    intent, sources = deepcopy(experiment_case)
    intent["objective_key"] = "objective_expected"
    intent["proposals"][0]["identifiability_claims"] = [{
        "hypothesis_key": "unknown_hypothesis", "observable": "response",
        "distinguishing_outcome": "response", "decision_rule": "response",
        "ambiguity_conditions": ["bounded"], "smallest_resolving_control": "control",
    }]
    runtime, run_id, output = _experiment_run(tmp_path, sources)
    output.write_bytes(_experiment_envelope(intent))
    state, details = runtime.runs.submit(run_id)
    assert state == "rejected"
    assert details[0]["phase"] == "output_payload"
    assert details[0]["rule_id"] == "experiment.design.intent_closure"
    assert "hypothesis" in details[0]["message"]


def test_materialized_variable_keeps_editable_intent_location(tmp_path, experiment_case):
    intent, sources = deepcopy(experiment_case)
    intent["objective_key"] = "objective_expected"
    variable = intent["proposals"][0]["variables"][0]
    variable["baseline_value"], variable["case_overrides"][0]["value"] = False, 0
    runtime, run_id, output = _experiment_run(tmp_path, sources)
    output.write_bytes(_experiment_envelope(intent))
    state, details = runtime.runs.submit(run_id)
    assert state == "rejected"
    assert details[0]["path"] == "$.payload.proposals[0].variables[0].comparison_role"
    assert details[0]["phase"] == "output_payload"
    variable["baseline_value"], variable["case_overrides"][0]["value"] = 0, 1
    output.write_bytes(_experiment_envelope(intent))
    assert runtime.runs.submit(run_id) == ("completed", ())


def test_expired_and_terminal_calls_keep_diagnostics_without_changing_state(tmp_path):
    system = analysis_system(tmp_path)
    worker, opened = open_analysis(system)
    runs, root = system[1].runs, system[2]
    write_analysis(opened, analysis_report())
    with runs._connect() as connection:
        connection.execute("UPDATE runs SET deadline_at=? WHERE run_id=?", ("2000-01-01T00:00:00Z", worker._run_id))
    before = runs.status(worker._run_id)
    reply = wire(worker, "worker_submit_result", {})
    assert "error" in reply
    status = root.call_tool("run_status", {"name": "analysis", "diagnostic_after": 0})
    assert status["state"] == "running" and status["candidate_accepted"] is False
    error = status["diagnostic_summary"]["latest_tool_error"]
    assert "deadline expired" in json.dumps(error)
    reference = error["engineering"]["reference"]
    assert "error" not in wire(root, "diagnostic_read", {"reference": reference})
    assert runs.status(worker._run_id).last_activity_at == before.last_activity_at
    assert len(status["diagnostic_events"]["events"]) == 1
    failed = runs.record_failure(worker._run_id, reason="scheduler records timeout", timed_out=True,
        expected_state="running", expected_last_activity_at=before.last_activity_at)
    assert "error" in wire(worker, "worker_heartbeat", {})
    after = runs.status(worker._run_id)
    assert after.state == failed.state == "failed" and after.reason == failed.reason
    assert len(root.call_tool("run_status", {"name": "analysis", "diagnostic_after": 0})["diagnostic_events"]["events"]) == 3


def test_rejection_finishing_after_deadline_is_still_saved(tmp_path, monkeypatch):
    system = analysis_system(tmp_path)
    worker, _ = open_analysis(system)
    runs = system[1].runs
    def late_rejection(value, **_):
        with runs._connect() as connection:
            connection.execute("UPDATE runs SET deadline_at=? WHERE run_id=?", ("2000-01-01T00:00:00Z", value.run_id))
        raise RunOutputError("output needs correction", details=(contract_diagnostic(
            "output_invalid", phase="output_payload", affected_action="submit",
            path="$.payload.summary", repairable=True, message="A bounded fixture rejection."),))
    monkeypatch.setattr(runs, "_validated_candidate", late_rejection)
    result = worker.call_tool("worker_submit_result", {})
    assert result["state"] == "rejected"
    summary = runs.diagnostic_summary(runs.status(worker._run_id))
    assert summary["rejection_count"] == 1
    assert summary["latest_rejection"]["details"] == result["diagnostics"]


def test_agent_reuse_keeps_entire_open_call_on_new_run(tmp_path):
    system = analysis_system(tmp_path)
    worker, opened = open_analysis(system)
    runs, root, request = system[1].runs, system[2], system[3]
    write_analysis(opened, analysis_report())
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    prior = worker._run_id
    times = runs.tool_timing(prior)
    root.call_tool("operation_invoke", {**request, "name": "reuse"})
    assert worker.call_tool("worker_open_assignment", {})["state"] == "opened"
    assert worker._run_id != prior
    assert runs.tool_timing(prior) == times
    new_times = runs.tool_timing(worker._run_id)
    assert len(new_times) == 1 and new_times[0]["tool_name"] == "worker_open_assignment"
    assert new_times[0]["started_at"] and new_times[0]["completed_at"]


@pytest.mark.parametrize("failure", ["workspace", "workspace_restart", "evidence", "expired"])
def test_failed_reuse_open_belongs_to_selected_run(tmp_path, monkeypatch, failure):
    from scidiscovery.artifact_agent.service.run_outputs import RunCheckerError
    system = analysis_system(tmp_path)
    worker, opened = open_analysis(system)
    runs, root, request = system[1].runs, system[2], system[3]
    write_analysis(opened, analysis_report())
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    prior = worker._run_id
    before = runs.tool_timing(prior)
    root.call_tool("operation_invoke", {**request, "name": "next"})
    selected = root.facade._resolve("run", "next")
    if failure == "workspace_restart":
        from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
        runs.open(operation_id=worker.operation_id, operation_digest=worker.operation_digest)
        worker = LocalWorkerMCPRouter(runs, operation_id=worker.operation_id,
                                     operation_digest=worker.operation_digest)
    if failure == "expired":
        with runs._connect() as connection:
            connection.execute("UPDATE runs SET deadline_at=? WHERE run_id=?",
                               ("2000-01-01T00:00:00Z", selected))
        reason = "queued Run has expired"
    else:
        reason = "fixture: selected assignment unavailable"
        def broken(run_id):
            assert run_id == selected
            if failure.startswith("workspace"):
                raise OSError(reason)
            raise RunCheckerError(reason)
        if failure.startswith("workspace"):
            monkeypatch.setattr(runs.backend, "open", broken)
        else:
            monkeypatch.setattr(runs, "adopt_tool_evidence", broken)
    reply = wire(worker, "worker_open_assignment", {})
    assert "error" in reply and selected not in json.dumps(reply)
    assert worker._run_id == selected and worker._workspace is None
    assert runs.status(prior).state == "completed" and runs.tool_timing(prior) == before
    status = root.call_tool("run_status", {"name": "next", "diagnostic_after": 0})
    assert status["state"] == "failed" and reason in json.dumps(status["diagnostic_summary"])
    timing = runs.tool_timing(selected)
    assert len(timing) == 1 and timing[0]["tool_name"] == "worker_open_assignment"
    assert timing[0]["started_at"] and timing[0]["completed_at"]
    assert status["diagnostic_events"]["events"][-1]["activity"] == "tool_failed"


def test_mcp_pages_all_saved_errors_and_runs_with_instance_isolation(tmp_path):
    system = analysis_system(tmp_path)
    worker, opened = open_analysis(system)
    runs, root, request = system[1].runs, system[2], system[3]
    for i in range(11):
        runs.record_error_observation(worker._run_id, "output_rejected", diagnostic={
            "category": "output_rejected", "details": [contract_diagnostic(
                "output_invalid", phase="output_payload", affected_action="submit", repairable=True,
                path="$.payload.summary", message=f"Fixture rejection {i}.")],
        })
    # Legacy records without details must remain visible, without invented causes.
    with runs._connect() as connection:
        connection.execute("INSERT INTO run_activity(run_id,activity,recorded_at,diagnostic_json) VALUES (?,?,?,NULL)",
            (worker._run_id, "output_rejected", "2026-01-01T00:00:00Z"))
    assert "diagnostic_events" not in root.call_tool("run_status", {"name": "analysis"})
    cursor, events = 0, []
    while cursor is not None:
        reply = wire(root, "run_status", {"name": "analysis", "diagnostic_after": cursor, "diagnostic_limit": 3})
        assert "error" not in reply
        page = reply["result"]["structuredContent"]["diagnostic_events"]
        events.extend(page["events"])
        cursor = page["next_after"]
    assert len(events) == 12 and len({e["event_id"] for e in events}) == 12
    assert events[-1]["diagnostic"] is None
    assert all(e["recorded_at"] and e["activity"] == "output_rejected" for e in events)
    write_analysis(opened, analysis_report())
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    root.call_tool("operation_invoke", {**request, "name": "second"})
    first = root.call_tool("run_list", {"limit": 2})
    opened = worker.call_tool("worker_open_assignment", {})
    write_analysis(opened, analysis_report())
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    root.call_tool("operation_invoke", {**request, "name": "newest"})
    second = root.call_tool("run_list", {"limit": 2, "before": first["next_before"]})
    assert not {r["name"] for r in first["runs"]} & {r["name"] for r in second["runs"]}
    assert "plan_review" in {r["name"] for r in second["runs"]}
    foreign = system[1].scheduler_bindings.create_instance(name="foreign", title="Foreign", objective="Isolation")
    facade = RootToolFacade(system[1].artifacts, system[1].intake, runs=runs, approvals=system[1].approvals,
        executions=system[1].executions, bindings=system[1].scheduler_bindings,
        instance=foreign.instance_id, operation_catalog=system[0])
    foreign_root = RootMCPRouter(facade)
    assert "error" in wire(foreign_root, "run_status", {"name": "analysis", "diagnostic_after": 0})
    assert "error" in wire(foreign_root, "run_list", {"before": "analysis"})
    assert root.call_tool("run_list", {"state": "failed"})["runs"] == []


def test_publication_source_failure_names_exact_argument_and_is_recoverable(tmp_path):
    system = analysis_system(tmp_path)
    worker, opened = open_analysis(system)
    request = {"source_aliases": ["runtime_manifest", "tool_recovery_manifest"],
        "script_path": "scratch/a.py", "files": [{"path": "scratch/a.json", "media_type": "application/json"}],
        "method": "Bounded test."}
    reply = wire(worker, "worker_analysis_publish_files", request)
    assert reply["error"]["data"]["diagnostics"][0]["path"] == "$.source_aliases[1]"
    summary = system[1].runs.diagnostic_summary(system[1].runs.status(worker._run_id))
    assert summary["latest_tool_error"]["details"][0]["path"] == "$.source_aliases[1]"
    write_analysis(opened, analysis_report())
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
