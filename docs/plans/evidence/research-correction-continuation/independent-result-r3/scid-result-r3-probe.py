import copy
import json
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(sys.argv[1])
sys.path[:0] = [str(ROOT / part) for part in (
    "src", ".", "plugins/tcad_artifact", "plugins/curve_score",
    "plugins/curve_figure_evidence", "tests/fixtures/plugins/blind_csv_operation_plugin",
)]

from scidiscovery.operations import catalog as catalog_module
from tests.conftest import _SOURCE_FULL_PLUGINS
from tests.operations.test_agent_contract_alignment import _feedback_root, experiment_case
from tests.operations.test_general_transform_operations import _register
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.research_objective import ResearchObjectiveContract


def complete(runtime, root, request, payload, verdict="pass"):
    preflight = root.call_tool("operation_preflight", request)
    assert preflight["admissible"], preflight
    root.call_tool("operation_invoke", request)
    compiled = runtime.runs.operation_catalog.operation(request["operation_id"])
    worker = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id,
                                  operation_digest=compiled.digest)
    opened = worker.call_tool("worker_open_assignment", {})
    Path(opened["output_directory"], "result.json").write_bytes(canonical_json({
        "schema_version": 1, "payload": payload,
        "handoff": {"verdict": verdict, "summary": "Independent engineering probe."},
    }))
    submitted = worker.call_tool("worker_submit_result", {})
    status = root.call_tool("run_status", {"name": request["name"]})
    return preflight, submitted, status


with tempfile.TemporaryDirectory(prefix="scid-r3-identity-") as work, pytest.MonkeyPatch.context() as patch:
    patch.setattr(catalog_module, "entry_points", lambda: _SOURCE_FULL_PLUGINS)
    catalog_module.compile_installed_catalog.cache_clear()
    runtime, instance, root, design, intent = _feedback_root(
        Path(work), patch, experiment_case.__wrapped__(), "science.experiment.design.v1")
    _, submitted, status = complete(runtime, root, design, intent)
    assert submitted["state"] == "completed", submitted
    original_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id, namespace="artifact", name="research_objective")
    original = runtime.artifacts.get_by_id(original_id)
    alternative = json.loads(runtime.artifacts.read(original.ref))
    alternative["mandatory_targets"][1]["observable"] = "Contradictory alternate future observable"
    alternative["closure_requirements"][-1]["description"] = "Alternative closure never used to design this plan"
    ResearchObjectiveContract.model_validate_json(canonical_json(alternative), strict=True)
    wrong = _register(runtime, instance, name="same_text_different_contract", raw=canonical_json(alternative),
                      kind=original.kind, schema=original.schema_id, parents=original.parent_refs)
    materialized = root.call_tool("operation_invoke", {
        "name": "plan", "operation_id": "science.experiment.materialize.v1",
        "inputs": [{"port": "experiment_design_intent", "artifact_names": [status["output_artifact_name"]]},
                   *design["inputs"]],
    })
    plan_name = materialized["result"]["outputs"][0]["artifact_name"]
    plan_parents = root.call_tool("artifact_catalog", {"name": plan_name})["parent_artifact_names"]
    review_payload = {"review_target": "experiment_portfolio", "verdict": "pass",
                      "summary": "Current goals are feasible against the supplied objective contract."}
    outcomes = {}
    for name, objective_name in (("exact", "research_objective"),
                                 ("wrong", "same_text_different_contract")):
        request = {"name": f"review_{name}", "operation_id": "science.object.review.v1",
                   "inputs": [{"port": "experiment_plan", "artifact_names": [plan_name]},
                              {"port": "research_objective", "artifact_names": [objective_name]}],
                   "instruction": "Independently assess the plan against its original research objective."}
        preflight, submitted, status = complete(runtime, root, request, review_payload)
        outcomes[name] = {"preflight": preflight, "submission_state": submitted["state"],
                          "run_state": status["state"],
                          "sealed_verdict": status.get("sealed_output", {}).get("payload", {}).get("verdict")}
    from tests.operations.test_m2_curve_analysis_boundary import _bundle
    _register(runtime, instance, name="reference_bundle", raw=canonical_json(_bundle().model_dump(mode="json")),
              kind="curve_bundle", schema="scidiscovery.curve-bundle.v1")
    downstream = root.call_tool("operation_preflight", {
        "name": "downstream_curve", "operation_id": "science.curve.contract.design.v1",
        "inputs": [{"port": "research_objective", "artifact_names": ["research_objective"]},
                   {"port": "experiment_plan", "artifact_names": [plan_name]},
                   {"port": "experiment_review", "artifact_names": [status["output_artifact_name"]]},
                   {"port": "reference_bundle", "artifact_names": ["reference_bundle"]}],
        "instruction": "Assess the exact original plan with the supplied independent review.",
    })
    print(json.dumps({"probe": "materialized_plan_original_objective_binding",
                      "plan_parent_names": plan_parents,
                      "wrong_objective_is_plan_parent": "same_text_different_contract" in plan_parents,
                      "objectives_share_key_and_statement": True,
                      "objective_bytes_differ": wrong.ref.sha256 != original.ref.sha256,
                      "outcomes": outcomes,
                      "downstream_curve_design_with_original_objective_and_wrong_objective_review": downstream,
                      "limits": "Isolated Local engineering fixture; foundation approval predicate mocked; no real research or external execution."},
                     indent=2))
