"""Independent bounded review probes; only synthetic test workspaces are used."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from tests.operations.test_agent_contract_alignment import (
    experiment_case, _experiment_run, _experiment_envelope,
)
from tests.operations.test_l2_run_invariants import _system, _invoke, _worker, _envelope

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def record(name, value):
    path = HERE / "review_probe_r1.json"
    data = json.loads(path.read_text()) if path.exists() else {}
    data[name] = value
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def test_exact_candidate_hashes():
    manifest = json.loads((HERE / "REVIEW_MANIFEST_R2.json").read_text())
    snapshot = Path(manifest["base_snapshot"])
    mismatches = []
    for entry in manifest["files"]:
        current = ROOT / entry["path"]
        if hashlib.sha256(current.read_bytes()).hexdigest() != entry["sha256"]:
            mismatches.append("current:" + entry["path"])
        before = snapshot / entry["path"]
        if entry["before_sha256"] is not None:
            if hashlib.sha256(before.read_bytes()).hexdigest() != entry["before_sha256"]:
                mismatches.append("before:" + entry["path"])
        elif before.exists():
            mismatches.append("unexpected-before:" + entry["path"])
    record("candidate_hashes", {"checked": len(manifest["files"]), "mismatches": mismatches})
    assert mismatches == []


def test_derived_variable_diagnostic_points_to_editable_intent_field(tmp_path):
    intent, sources = deepcopy(experiment_case.__wrapped__())
    intent["objective_key"] = "objective_expected"
    variable = intent["proposals"][0]["variables"][0]
    variable["baseline_value"] = False
    variable["case_overrides"][0]["value"] = 0
    runtime, run_id, output = _experiment_run(tmp_path, sources)
    output.write_bytes(_experiment_envelope(intent))
    state, details = runtime.runs.submit(run_id)
    record("derived_variable", {"state": state, "details": details,
        "summary": runtime.runs.diagnostic_summary(runtime.runs.status(run_id))})
    assert state == "rejected"
    assert details[0]["path"] == "$.payload.proposals[0].variables[0].comparison_role"


def test_failed_reuse_open_does_not_record_time_on_completed_prior_run(tmp_path, monkeypatch):
    catalog, runtime, instance, _, root = _system(tmp_path)
    _invoke(root, "review_prior")
    worker = _worker(catalog, runtime)
    opened = worker.call_tool("worker_open_assignment", {})
    Path(opened["output_directory"], "result.json").write_bytes(_envelope())
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    prior_id = worker._run_id
    before = runtime.runs.tool_timing(prior_id)
    _invoke(root, "review_next")
    next_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id,
        namespace="run", name="review_next")

    def unavailable_workspace(run_id):
        assert run_id == next_id
        raise OSError("review fixture: selected assignment could not be opened")

    monkeypatch.setattr(runtime.runs.backend, "open", unavailable_workspace)
    reply = worker.call_tool("worker_open_assignment", {})
    after = runtime.runs.tool_timing(prior_id)
    current = root.call_tool("run_status", {"name": "review_next", "diagnostic_after": 0})
    record("failed_reuse_open", {"reply": reply,
        "prior_timing_before": len(before), "prior_timing_after": len(after),
        "prior_added_timing": after[len(before):],
        "next_state": current["state"],
        "next_timing": runtime.runs.tool_timing(next_id),
        "next_diagnostic_events": current["diagnostic_events"],
        "next_diagnostic_summary": current["diagnostic_summary"]})
    assert runtime.runs.status(prior_id).state == "completed"
    assert current["state"] == "failed"
    assert after == before
