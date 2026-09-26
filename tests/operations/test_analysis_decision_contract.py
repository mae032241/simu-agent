"""Synthetic cross-boundary checks for bounded analysis decisions.

These fixtures prove engineering expression and reading behavior only. They are not
Fig.4 evidence, a scientific verdict, or a scheduler-quality measurement.
"""

import json

import pytest

from curve_score.science_operations import Components
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.general_science_views import build_presentation
from tests.operations import test_m2_curve_analysis_boundary as curve
from tests.operations.test_analysis_claim_scope import (
    generic_worker,
    submit,
)
from tests.operations.test_result_analysis_tool import limited_report
from tests.operations.test_m2_curve_analysis_boundary import _compiler_plan
from tests.operations.test_tcad_result_analysis import (
    analysis_report,
    analysis_system,
    open_analysis,
    write_analysis,
)


DECISION_PATHS = [
    "/summary", "/overall_verdict", "/claim_allowed",
    "/objective_assessment", "/hypothesis_assessments", "/limitations",
    "/remaining_contradiction", "/next_action",
]


def _keyed_worker(tmp_path, kind):
    plan = _compiler_plan()
    if kind == "generic":
        worker, opened, system = generic_worker(
            tmp_path, plan=plan, return_system=True
        )
        runtime, root, name = system[1], system[2], "generic_analysis"
        report, evidence_key = limited_report(), "experiment_results"
    else:
        system = analysis_system(
            tmp_path, state="failed", bind_names=(), plan=plan
        )
        worker, opened = open_analysis(system)
        runtime, root, name = system[1], system[2], "analysis"
        report, evidence_key = analysis_report(), "raw_evidence"
    report["study_kind"] = "scientific"
    return plan, worker, opened, runtime, root, name, report, evidence_key


def _submit(worker, opened, report, kind):
    if kind == "tcad":
        write_analysis(opened, report)
        return worker.call_tool("worker_submit_result", {})
    return submit(worker, opened, report)


@pytest.mark.parametrize("kind", ["tcad"])
def test_real_keyed_producer_rejects_then_seals_complete_decision_contract(
    tmp_path, kind
) -> None:
    plan, worker, opened, runtime, root, name, report, evidence_key = (
        _keyed_worker(tmp_path, kind)
    )
    rejected = _submit(worker, opened, report, kind)
    assert rejected["state"] == "rejected", rejected
    diagnostic = next(
        item for item in rejected["diagnostics"]
        if "objective assessment is required" in item["message"]
    )
    assert diagnostic["path"] == "$.payload.objective_assessment"

    report.update(
        summary="The bounded evidence leaves the selected mechanism unresolved.",
        overall_verdict="inconclusive",
        claim_allowed=False,
        objective_assessment={
            "objective_key": plan.objective_key,
            "status": "fail",
            "summary": "The selected objective was not reached in this bounded result.",
            "evidence_keys": [evidence_key],
        },
        hypothesis_assessments=[{
            "hypothesis_key": "hypothesis_implementation",
            "outcome": "inconclusive",
            "rationale": "The cited evidence does not distinguish the selected mechanism.",
            "evidence_keys": [evidence_key],
        }],
        limitations=["Only the exact bound fixture evidence was assessed."],
        remaining_contradiction="The selected mechanism remains unresolved.",
        next_action="Optional bounded follow-up; this text has no command authority.",
    )
    completed = _submit(worker, opened, report, kind)
    assert completed["state"] == "completed", completed

    instance_id = runtime.scheduler_bindings.list_instances()[0].instance_id
    def control_state():
        return (
            tuple(item.run_id for item in runtime.runs.list(instance_id=instance_id)),
            tuple((namespace, item.object_id) for namespace in ("execution", "approval")
                  for item in runtime.scheduler_bindings.list(instance=instance_id, namespace=namespace)),
            tuple(item.artifact_id for item in runtime.artifacts.list_artifacts(limit=100)),
        )
    before = control_state()
    decision = root.call_tool("run_status", {'name': name, 'output_paths': DECISION_PATHS, "intent": 'decision'})
    assert control_state() == before
    assert decision["state"] == "completed"
    assert decision["scheduler_signal_status"] == "available"
    assert decision["scheduler_signal"]["verdict"] == "inconclusive"
    assert decision["output_metadata"]["schema"] == "scidiscovery.layered-diagnosis.v1"
    selected = decision["selected_output"]
    assert selected["artifact_name"] == decision["output_metadata"]["artifact_name"]
    by_pointer = {item["pointer"]: item for item in selected["items"]}
    assert tuple(by_pointer) == tuple(DECISION_PATHS)
    for pointer in DECISION_PATHS:
        key = pointer.removeprefix("/")
        assert by_pointer[pointer]["status"] == "selected"
        assert by_pointer[pointer]["value"] == report[key]

    artifact_id = runtime.scheduler_bindings.resolve(
        instance=runtime.scheduler_bindings.list_instances()[0].instance_id,
        namespace="artifact",
        name=selected["artifact_name"],
    )
    sealed = json.loads(runtime.artifacts.read(runtime.artifacts.get_by_id(artifact_id).ref))
    assert {key: sealed[key] for key in (path[1:] for path in DECISION_PATHS)} == {
        key: report[key] for key in (path[1:] for path in DECISION_PATHS)
    }

    presentation = build_presentation(({
        "artifact_id": artifact_id, "schema_id": "scidiscovery.layered-diagnosis.v1",
        "payload": sealed, "source": {"artifact_id": artifact_id, "json_pointer": ""},
    },))
    facts = {item["source"]["json_pointer"]: item
             for section in presentation["sections"] for item in section["items"]}
    for field in ("objective_assessment", "hypothesis_assessments"):
        assert facts["/" + field]["value"] == report[field]
    assert facts["/next_action"]["label"] == "原报告建议（非调度命令）"
