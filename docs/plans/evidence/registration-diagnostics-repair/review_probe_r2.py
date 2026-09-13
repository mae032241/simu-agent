"""Independent R3 probes; preserve all R1 reproduction artifacts."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from tests.operations.test_agent_contract_alignment import (
    experiment_case, _experiment_run, _experiment_envelope,
)
from tests.operations.test_l2_run_invariants import _system, _invoke, _worker, _envelope
from tests.operations.test_registration_diagnostics_repair import wire

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def record(name, value):
    path = HERE / "review_probe_r2.json"
    data = json.loads(path.read_text()) if path.exists() else {}
    data[name] = value
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def test_exact_candidate_and_wheel_hashes():
    manifest = json.loads((HERE / "REVIEW_MANIFEST_R3.json").read_text())
    snapshot = Path(manifest["base_snapshot"])
    installed = json.loads((HERE / "installed-smoke.json").read_text())
    wheel_paths = list((Path(installed["root"]) / "wheels").glob("*.whl"))
    checked_wheels = []
    for entry in manifest["files"]:
        assert hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest() == entry["sha256"]
        before = snapshot / entry["path"]
        if entry["before_sha256"] is not None:
            assert hashlib.sha256(before.read_bytes()).hexdigest() == entry["before_sha256"]
        else:
            assert not before.exists()
        path = Path(entry["path"])
        if path.parts[0] not in {"src", "plugins"}:
            continue
        package_path = str(Path(*path.parts[1 if path.parts[0] == "src" else 2:]))
        found = []
        for wheel_path in wheel_paths:
            with ZipFile(wheel_path) as wheel:
                if package_path in wheel.namelist():
                    found.append(hashlib.sha256(wheel.read(package_path)).hexdigest())
        assert found == [entry["sha256"]], (package_path, found)
        checked_wheels.append(entry["path"])
    record("candidate_hashes", {"checked": len(manifest["files"]),
        "wheel_checked": len(checked_wheels), "mismatches": []})


def test_derived_variable_nonzero_indexes_and_same_run_correction(tmp_path):
    intent, sources = deepcopy(experiment_case.__wrapped__())
    intent["objective_key"] = "objective_expected"
    second = deepcopy(intent["proposals"][0])
    second["experiment_key"] = "experiment_b"
    variable = deepcopy(second["variables"][0])
    variable["variable_key"] = "second_intervention"
    variable["scientific_path"] = "model.second_intervention"
    variable["baseline_value"] = False
    variable["case_overrides"][0]["value"] = 0
    second["variables"].append(variable)
    intent["proposals"].append(second)
    intent["priority_order"].append("experiment_b")
    runtime, run_id, output = _experiment_run(tmp_path, sources)
    output.write_bytes(_experiment_envelope(intent))
    state, details = runtime.runs.submit(run_id)
    assert state == "rejected"
    assert details[0]["path"] == "$.payload.proposals[1].variables[1].comparison_role"
    assert details[0]["phase"] == "output_payload"
    assert details[0]["rule_id"] == "experiment.design.intent_closure"
    assert runtime.runs.diagnostic_summary(runtime.runs.status(run_id))["latest_rejection"]["details"] == list(details)
    variable["baseline_value"] = 0
    variable["case_overrides"][0]["value"] = 1
    output.write_bytes(_experiment_envelope(intent))
    assert runtime.runs.submit(run_id) == ("completed", ())
    record("derived_variable", {"details": details, "same_run_correction": "completed"})


def test_failed_cross_instance_reuse_is_scoped_redacted_and_reusable(tmp_path, monkeypatch):
    catalog, runtime, original_instance, source, prior_root = _system(tmp_path)
    _invoke(prior_root, "review_prior")
    worker = _worker(catalog, runtime)
    opened = worker.call_tool("worker_open_assignment", {})
    Path(opened["output_directory"], "result.json").write_bytes(_envelope())
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    prior_id = worker._run_id
    before = runtime.runs.tool_timing(prior_id)
    prior_status = runtime.runs.status(prior_id)
    instance = runtime.scheduler_bindings.create_instance(
        name="review_second_instance", title="Review isolation", objective="Synthetic engineering test")
    runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace="artifact",
        name="source_csv", object_id=source.artifact_id)
    root = RootMCPRouter(RootToolFacade(runtime.artifacts, runtime.intake,
        runs=runtime.runs, approvals=runtime.approvals, executions=runtime.executions,
        bindings=runtime.scheduler_bindings, instance=instance.instance_id, operation_catalog=catalog))
    _invoke(root, "review_next")
    selected = runtime.scheduler_bindings.resolve(instance=instance.instance_id,
        namespace="run", name="review_next")

    def unavailable_workspace(run_id):
        assert run_id == selected
        raise OSError("selected assignment unavailable: /srv/private/review.json token=review-secret")

    with monkeypatch.context() as scoped:
        scoped.setattr(runtime.runs.backend, "open", unavailable_workspace)
        reply = wire(worker, "worker_open_assignment", {})
    assert "error" in reply
    assert worker._run_id == selected and worker._workspace is None
    assert runtime.runs.status(prior_id) == prior_status
    assert runtime.runs.tool_timing(prior_id) == before
    status = root.call_tool("run_status", {"name": "review_next", "diagnostic_after": 0})
    assert status["state"] == "failed"
    timing = runtime.runs.tool_timing(selected)
    assert len(timing) == 1 and timing[0]["started_at"] and timing[0]["completed_at"]
    diagnostic = status["diagnostic_summary"]["latest_tool_error"]
    reference = diagnostic["engineering"]["reference"]
    read = root.call_tool("diagnostic_read", {"reference": reference, "section": "traceback"})
    foreign_read = wire(prior_root, "diagnostic_read", {"reference": reference})
    assert "error" in foreign_read
    projected = json.dumps([reply, diagnostic, read])
    assert "selected assignment unavailable" in projected
    for private in (selected, "review-secret", "/srv/private"):
        assert private not in projected
    assert {event["activity"] for event in status["diagnostic_events"]["events"]} == {"framework_failure", "tool_failed"}
    _invoke(root, "review_recovered")
    reopened = worker.call_tool("worker_open_assignment", {})
    assert reopened["state"] == "opened"
    Path(reopened["output_directory"], "result.json").write_bytes(_envelope())
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    assert runtime.runs.tool_timing(prior_id) == before
    record("failed_cross_instance_reuse", {"failed_state": status["state"],
        "selected_call_count": len(timing), "prior_unchanged": True,
        "foreign_reference_denied": True, "cause_retained_and_redacted": True,
        "next_assignment_completed": True})
