"""Delivered strategy policy and sealed continuation, using synthetic evidence.

These checks cover engineering contracts, not a live model's research choices or
performance on an unidentified distribution.
"""
import json
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.service.run_assignment import assignment_json, result_schema_json
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.invoke import BoundOperationCall
from scidiscovery.platforms.scheduler_prompt import load_scheduler_prompt, load_scheduler_guides
from tests.operations.test_general_transform_operations import _root
from tests.operations.test_historical_compatibility_paths import _complete
from tests.operations.test_hypothesis_objective_boundary import _proposal
from tests.operations.worker_fixtures import attached_worker


@pytest.fixture(scope="module")
def catalog():
    return compile_catalog((CORE_PLUGIN, GENERAL))


def _assignment(catalog, operation):
    compiled = catalog.operation(operation)
    return json.loads(assignment_json(BoundOperationCall(
        compiled=compiled, name="strategy", inputs=(), instruction=None), (), tool_names=()))


def _assert_conditional_proposal_policy(role):
    role = " ".join(role.split())
    assert "Factual premises require exact evidence" in role
    assert "uncertain assumptions may be explicit conditional hypotheses" in role
    assert "Prior proof of efficacy or generalization is not required" in role
    assert "cannot be specified or prospectively tested remain blockers" in role
    assert "no supported candidate can be delivered" not in role


def test_generated_proposal_contract_allows_prospective_evidence(catalog):
    operation = "science.hypothesis.propose.v1"
    _assert_conditional_proposal_policy(_assignment(catalog, operation)["role_instructions"])
    schema = json.loads(result_schema_json(catalog.operation(operation)))
    semantic = json.dumps(schema["properties"]["payload"]["x-scidiscovery-semantic-constraints"])
    assert "Unresolved assumptions may be explicitly conditional" in semantic
    assert "prior efficacy or generalization is not a prerequisite" in semantic
    assert "prior efficacy is not required" in catalog.operation(operation).spec.description.purpose


def test_stale_supported_candidate_prerequisite_fails_delivered_policy(monkeypatch):
    from scidiscovery.general_science_resources import Resources
    monkeypatch.setattr(Resources, "ideator_prompt",
        "If the current model set is insufficient and no supported candidate can be delivered, report the bounded gap.")
    stale = compile_catalog((CORE_PLUGIN, GENERAL))
    with pytest.raises(AssertionError):
        _assert_conditional_proposal_policy(_assignment(stale, "science.hypothesis.propose.v1")["role_instructions"])


def test_root_and_analysis_keep_route_scope_and_incomplete_closeout(catalog):
    root = " ".join(load_scheduler_prompt().split())
    analysis = " ".join(_assignment(catalog, "science.result.analyze.v1")["role_instructions"].split())
    for text in (root, analysis):
        assert "Scope negative findings to the tested route" in text
        assert "smallest experiment" in text or "minimal discriminating contrast" in text
        assert "Unknown generalization limits claims" in text
        assert "best eligible candidate" in text
        assert "run-count filler" in text
        assert "cannot change the decision" in text
        assert "scope" in text and "constraints" in text and "permissions" in text
    assert "original task calls for further exploration" in root
    assert "without adding a stricter evidence prerequisite" in root
    assert "Close out honestly incomplete" in root
    assert "required inputs cannot be obtained" in root
    assert "honest incomplete closeout with specific blockers or budget limits" in analysis
    assert "Do not launch experiments or formulate a new portfolio" in analysis
    guides = load_scheduler_guides()
    assert "unknown generalization alone does not rule" in guides["results.md"]
    assert "When independent review or bounded revision is selected" in guides["research.md"]


def _values(root, name, paths=None):
    status = root.call_tool("run_status", {"name": name, **({"output_paths": paths} if paths else {})})
    return {item["pointer"]: item["value"] for item in status["selected_output"]["items"]
            if item["status"] == "selected"}


def test_sealed_local_negative_can_feed_distinct_conditional_hypothesis_without_review(tmp_path, catalog):
    runtime, instance, root = _root(tmp_path, catalog=catalog)
    runtime.runs.operation_catalog = catalog
    root.call_tool("artifact_ingest_text", {"name": "goal",
        "text": "Investigate recovery mechanisms within a finite budget. Keep the original candidate criterion."})
    first = _proposal(hypothesis_keys=("local_refinement",))
    first.pop("research_objective_key")
    h1 = _complete(runtime, root, "h1", "science.hypothesis.propose.v1", {"subject": "goal"}, first)
    w1 = _complete(runtime, root, "w1", "science.experiment.v1", {"subject": h1}, {
        "summary": "Synthetic fixture: local parameter refinement failed its finite contrast.",
        "outcome": "inconclusive", "remaining_question": "Can a distinct mechanism survive a specified model perturbation?",
        "limitations": ["The hidden distribution remains unidentified; no performance guarantee follows."],
    }, verdict="inconclusive")
    report = {
        "summary": "Retire the tested refinement route; exploration remains incomplete.",
        "overall_verdict": "inconclusive", "claim_allowed": False,
        "hypothesis_assessments": [{"hypothesis_key": "local_refinement", "outcome": "contradicts",
            "rationale": "Only the local contrast failed in this synthetic fixture.", "evidence_keys": ["experiment_results"]}],
        "limitations": ["Hidden distribution unknown; retained best candidate and original criterion remain unchanged."],
        "remaining_contradiction": "An explicitly bounded alternative assumption is investigable; generalization is unknown.",
        "next_action": "Seek a distinct conditional mechanism and one minimal perturbation contrast; do not repeat unchanged refinement.",
    }
    a1 = _complete(runtime, root, "a1", "science.result.analyze.v1", {"subject": w1}, report, verdict="inconclusive")
    assert _values(root, "a1")["/next_action"] == report["next_action"]
    second = _proposal(hypothesis_keys=("bounded_robust_mechanism",))
    second.pop("research_objective_key")
    second.update(stage_objective="Compare perturbation training against the retained baseline at fixed +/-0.05 normalized-input perturbations.",
        contradiction="The prior local refinement failed; the alternative mechanism is conditional on a specified perturbation family.")
    mechanism = second["hypotheses"][0]
    mechanism.update(statement="If the bounded perturbation family is informative, robust training can improve that contrast.",
        mechanism="Train with +/-0.05 perturbations of normalized input components instead of changing the old stopping parameter.",
        scope="Synthetic fixed +/-0.05 contrast only; no claim about the unidentified hidden distribution.",
        parameters=[{"name": "perturbation_radius", "role": "fixed", "unit": "dimensionless",
            "basis": "Prospectively fixed at 0.05 for a synthetic contrast; not an estimate of hidden shift."}],
        predictions=[{"prediction_key": "robust_gain", "observable": "Paired difference in the frozen whole-response metric against the retained baseline.",
            "expected_outcome": "Gain >=0.03 in both fixed perturbation directions; this new criterion does not reinterpret prior tests."}],
        falsifiers=[{"falsifier_key": "robust_gain_failure", "observable": "The same paired whole-response metric difference.",
            "rejection_condition": "Gain <0.03 in either fixed perturbation direction."}], evidence_keys=["result_analysis"])
    h2 = _complete(runtime, root, "h2", "science.hypothesis.propose.v1",
        {"subject": "goal", "previous_hypotheses": h1, "result_analysis": a1}, second, verdict="inconclusive")
    # Read exact children when the complete portfolio exceeds the bounded default.
    fields = ("mechanism", "predictions", "falsifiers")
    selected = _values(root, "h2", [f"/hypotheses/0/{field}" for field in fields])
    assert selected == {f"/hypotheses/0/{field}": mechanism[field] for field in fields}
    # No automatic review/approval is needed to queue a feasible scientific test.
    queued = root.call_tool("operation_invoke", {"name": "w2", "operation_id": "science.experiment.v1",
        "instruction": "Test only the specified conditional contrast within the original criteria and remaining budget.",
        "inputs": [{"port": "subject", "artifact_names": [h2]}]})
    assert queued["result"]["state"] == "queued"
    worker = attached_worker(runtime, root, "w2")
    opened = worker.call_tool("worker_open_assignment", {})
    assignment = json.loads(Path(opened["assignment_path"]).read_bytes())
    assert {item["source_name"] for item in assignment["inputs"]} >= {"hypothesis_portfolio", "objective_source"}
    assert "execution_requirements" not in assignment
    assert runtime.scheduler_bindings.list(instance=instance.instance_id, namespace="approval") == ()


@pytest.mark.parametrize("blocker", [
    "A required original is unavailable and cannot be obtained within permissions.",
    "No remaining budget permits the minimal test plus analysis and closeout.",
])
def test_existing_fields_accept_specific_incomplete_closeout(catalog, blocker):
    from scidiscovery.general_science_result_analysis import validate_context
    from scidiscovery.operations.input_validation import ValidationSources
    from scidiscovery.artifact_agent.schema.common import canonical_json
    proposal = _proposal(hypothesis_keys=("local_refinement",))
    report = {"summary": "Local route suspended; global work remains incomplete.",
        "overall_verdict": "inconclusive", "claim_allowed": False,
        "limitations": [blocker], "remaining_contradiction": "Unfinished original requirements remain.",
        "next_action": "Close out honestly incomplete and retain the best eligible candidate."}
    validate_context(report, ValidationSources({"hypothesis_portfolio": canonical_json(proposal)}, {}), {})
