"""A current exact review can resolve a historical verdict, not source restrictions."""
import json

import pytest

from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.interfaces.mcp_root import RootToolError
from tcad_artifact.execution_control import SolverCapability
from tests.operations.science_fixtures import _engineering_intent
from tests.operations.test_agent_contract_alignment import _feedback_root, experiment_case
from tests.operations.test_general_transform_operations import _register
from tests.operations.test_historical_compatibility_paths import _artifact, _complete


def _case(tmp_path, monkeypatch, experiment_case, verdict="revise", provisional=False):
    runtime, instance, root, design_request, _ = _feedback_root(
        tmp_path, monkeypatch, experiment_case, "science.experiment.design.v1")
    intent = json.loads(_engineering_intent())
    if provisional:
        design = "provisional_intent"
        _register(runtime, instance, name=design, raw=canonical_json(intent),
                  kind="experiment_design_intent", schema="scidiscovery.experiment-design-intent.v1",
                  provisional=True)
    else:
        design = _complete(runtime, root, "design", "science.experiment.design.v1",
            {item["port"]: item["artifact_names"][0] for item in design_request["inputs"]},
            intent, verdict=verdict)
    materialize = {"name": "plan", "operation_id": "science.experiment.materialize.v1",
                   "inputs": [{"port": "experiment_design_intent", "artifact_names": [design]}]}
    assert root.call_tool("operation_preflight", materialize)["admissible"]
    root.call_tool("operation_invoke", materialize)
    plan = _artifact(runtime, instance, "plan")
    assert plan.labels["scientific_claim_admissible"] == "false"
    capability = SolverCapability(profile_id="review_fixture", solver_kind="sprocess",
        executable="/opt/fake/sprocess", environment={}, release_evidence="Synthetic fixture",
        public_release_label="Sentaurus R-2020.09")
    _register(runtime, instance, name="capability", raw=canonical_json(capability.public_snapshot().model_dump(mode="json")),
              kind="solver_capability", schema="tcad.solver-capability.v2")
    request = {"name": "author", "operation_id": "tcad.deck.author.initial.v1",
               "instruction": "Implement only this exact reviewed plan.", "inputs": [
        {"port": "execution_capability", "artifact_names": ["capability"]},
        {"port": "experiment_plan", "artifact_names": ["plan"]}]}
    return runtime, instance, root, request, plan


def _review(runtime, root, name, plan="plan", verdict="pass"):
    return _complete(runtime, root, name, "science.object.review.v1", {"experiment_plan": plan},
        {"review_target": "experiment_portfolio", "verdict": verdict,
         "summary": "Assess the exact plan against the now available capability evidence."}, verdict=verdict)


def _with_review(request, review):
    return {**request, "inputs": [*request["inputs"],
        {"port": "experiment_review", "artifact_names": [review]}]}


@pytest.mark.parametrize("verdict", ["revise", "blocked"])
def test_exact_pass_resolves_legacy_transform_verdict_without_rewriting_history(
    tmp_path, monkeypatch, experiment_case, verdict,
):
    runtime, instance, root, request, plan = _case(tmp_path, monkeypatch, experiment_case, verdict)
    original = runtime.artifacts.read(plan.ref)
    assert root.call_tool("operation_preflight", request)["reason_code"] == "input_independent_review_missing"
    for nonpass in ("revise", "blocked", "inconclusive"):
        review = _review(runtime, root, "review_" + nonpass, verdict=nonpass)
        rejected = root.call_tool("operation_preflight", _with_review(request, review))
        assert rejected["reason_code"] == "input_independent_review_missing"
    review = _review(runtime, root, "review_pass")
    request = _with_review(request, review)
    preflight = root.call_tool("operation_preflight", request)
    assert preflight["admissible"], preflight
    assert root.call_tool("operation_invoke", preflight["normalized_request"])["result"]["state"] == "queued"
    assert runtime.artifacts.read(plan.ref) == original
    assert _artifact(runtime, instance, "plan").labels == plan.labels


def test_review_of_other_subject_cannot_resolve_restriction(tmp_path, monkeypatch, experiment_case):
    runtime, instance, root, request, plan = _case(tmp_path, monkeypatch, experiment_case)
    _register(runtime, instance, name="other_plan", raw=runtime.artifacts.read(plan.ref),
              kind=plan.kind, schema=plan.schema_id)
    review = _review(runtime, root, "other_review", plan="other_plan")
    rejected = root.call_tool("operation_preflight", _with_review(request, review))
    assert rejected["reason_code"] == "input_independent_review_missing"


def test_pass_does_not_launder_explicitly_restricted_transform_source(tmp_path, monkeypatch, experiment_case):
    runtime, instance, root, request, _ = _case(tmp_path, monkeypatch, experiment_case, provisional=True)
    review = _review(runtime, root, "review_pass")
    rejected = root.call_tool("operation_preflight", _with_review(request, review))
    assert rejected["reason_code"] == "input_scientific_claim_forbidden"
    assert "explicit non-scientific sources" in rejected["diagnostics"][0]["message"]
    with pytest.raises(RootToolError, match="input_scientific_claim_forbidden"):
        root.call_tool("operation_invoke", _with_review(request, review))


def test_copied_transform_labels_do_not_prove_restriction_origin(tmp_path, monkeypatch, experiment_case):
    runtime, instance, root, request, plan = _case(tmp_path, monkeypatch, experiment_case)
    copied = runtime.artifacts.register(runtime.artifacts.read(plan.ref), ArtifactRegistration(
        kind=plan.kind, schema_id=plan.schema_id, payload_schema_version=1, media_type=plan.media_type,
        creator=runtime.actor, parent_refs=plan.parent_refs, labels=plan.labels), idempotency_key="copied")
    runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace="artifact", name="copied",
                                    object_id=copied.artifact_id)
    review = _review(runtime, root, "copied_review", plan="copied")
    request["inputs"][1]["artifact_names"] = ["copied"]
    rejected = root.call_tool("operation_preflight", _with_review(request, review))
    assert rejected["reason_code"] == "input_scientific_claim_forbidden"
