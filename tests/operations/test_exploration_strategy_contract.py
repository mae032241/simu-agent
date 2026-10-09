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
from tests.operations.test_progression import progression, row, checkpoint
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


def _values(root, name):
    status = root.call_tool("run_status", {"name": name})
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
    # Inspect retained scientific originals inside the fixture; Root only reads
    # compact scheduling statements, never raw portfolio children.
    fields = ("mechanism", "predictions", "falsifiers")
    with pytest.raises(Exception, match="tool arguments do not satisfy the declared model"):
        root.call_tool("run_status", {"name": "h2", "output_paths": ["/hypotheses/0/mechanism"]})
    retained = root.facade.run_status(name="h2", intent="full")["sealed_output"]["payload"]["hypotheses"][0]
    assert {field: retained[field] for field in fields} == {field: mechanism[field] for field in fields}
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


def _assert_target_coverage_policy(role):
    role = " ".join(role.split())
    assert "one testable solution mechanism directly addressing the target conditions" in role
    assert "For each mechanism, use existing statement/mechanism/scope" in role
    assert "current or training conditions, target-use conditions" in role
    assert "observations distinguishing support from rejection" in role
    assert "Tasks without training use current versus target conditions" in role
    assert "Information lawfully available only under target conditions may be used" in role
    assert "no particular algorithm or adaptation strategy is prescribed" in role
    assert "method hints do not exhaust the mechanism space" in role
    assert "Reuse an applicable mechanism with its rationale" in role
    assert "A pure diagnosis goal need not propose solution mechanisms" in role
    assert "specific gap and clarification/extraction or limited-stop direction" in role
    assert "not a new form or control hypothesis-count gate" in role
    _assert_conditional_proposal_policy(role)


@pytest.mark.parametrize("entry", ["original", "extracted"])
def test_target_mechanism_policy_reaches_real_original_and_extracted_assignments(tmp_path, catalog, entry):
    from tests.operations.test_general_transform_operations import _intake
    runtime, _, root = _root(tmp_path, catalog=catalog)
    runtime.runs.operation_catalog = catalog
    root.call_tool("artifact_ingest_text", {"name": "goal",
        "text": "Improve the target-use response within the original constraints. Method examples are starting points."})
    inputs = [{"port": "subject", "artifact_names": ["goal"]}]
    if entry == "extracted":
        payload = json.loads(_intake().canonical_json().replace(b'"paper"', b'"source_material"'))
        extracted = _complete(runtime, root, "extracted", "science.evidence.extract.v1", {"source_material": "goal"}, payload)
        # An extraction is scientific material, never replacement user text.
        invalid = {"name": "wrong-origin", "operation_id": "science.hypothesis.propose.v1",
            "inputs": [{"port": "subject", "artifact_names": [extracted]}]}
        assert not root.call_tool("operation_preflight", invalid)["admissible"]
        inputs.append({"port": "scientific_materials", "artifact_names": [extracted]})
    request = {"name": "target-H", "operation_id": "science.hypothesis.propose.v1",
        "inputs": inputs,
        "instruction": "Formulate the next bounded mechanism question from these exact sources."}
    assert root.call_tool("operation_preflight", request)["admissible"]
    assert root.call_tool("operation_invoke", request)["result"]["state"] == "queued"
    worker = attached_worker(runtime, root, "target-H")
    opened = worker.call_tool("worker_open_assignment", {})
    assignment = json.loads(Path(opened["assignment_path"]).read_bytes())
    _assert_target_coverage_policy(assignment["role_instructions"])
    schema = json.loads((Path(opened["workspace_path"]) / "schema/result.schema.json").read_bytes())
    semantic = json.dumps(schema["properties"]["payload"]["x-scidiscovery-semantic-constraints"])
    assert "each mechanism explains current/training versus target-use conditions" in semantic
    assert "not a new hypothesis-count admission gate" in semantic
    assert "Method hints are not an exhaustive mechanism list" in semantic
    assert "Pure diagnosis need not propose solutions" in semantic
    assert "prior efficacy or generalization is not a prerequisite" in semantic
    assert not schema["properties"]["payload"]["properties"]["hypotheses"].get("minItems")
    if entry == "extracted":
        material = next(item for item in assignment["inputs"] if item["artifact_name"] == extracted)
        assert material["source_name"] and material["relative_path"]
    assert "execution_requirements" not in assignment


@pytest.mark.parametrize("case", ["target-mechanism", "diagnosis", "unavailable"])
def test_existing_h_fields_deliver_target_mechanism_or_honest_gap_without_new_gate(tmp_path, catalog, case):
    runtime, instance, root = _root(tmp_path, catalog=catalog)
    runtime.runs.operation_catalog = catalog
    task = ("Diagnose the bounded response; a solution is not requested." if case == "diagnosis" else
        "Improve the response under target-use conditions. Preserve original data restrictions and permissions.")
    root.call_tool("artifact_ingest_text", {"name": "goal", "text": task})
    proposal = _proposal(hypothesis_keys=("target_mechanism",) if case == "target-mechanism" else ())
    proposal.pop("research_objective_key")
    if case == "target-mechanism":
        proposal.update(stage_objective="Discriminate a conditional target-use mechanism.",
            contradiction="A different target condition may expose a finite response failure; this remains an assumption.")
        mechanism = proposal["hypotheses"][0]
        mechanism.update(statement="If the target-condition sensitivity is relevant, a bounded intervention can reduce the response failure.",
            mechanism="Compare an unchanged baseline with one bounded intervention under the target condition.",
            scope="No training stage: compare current and target-use conditions; causal sensitivity remains conditional.",
            predictions=[{"prediction_key": "target_response", "observable": "Paired response under the target condition.",
                "expected_outcome": "The intervention reduces the specified response failure relative to baseline."}],
            falsifiers=[{"falsifier_key": "target_failure", "observable": "The same paired target-condition response.",
                "rejection_condition": "The intervention does not reduce the failure."}])
    else:
        proposal.update(stage_objective="Characterize the bounded unresolved gap.",
            contradiction="Required target observations are unavailable within permissions; original improvement remains incomplete."
            if case == "unavailable" else "The diagnosis remains unresolved; no solution mechanism is justified yet.")
    output = _complete(runtime, root, "H", "science.hypothesis.propose.v1", {"subject": "goal"}, proposal, verdict="inconclusive")
    sealed = root.facade.run_status(name="H", intent="full")["sealed_output"]["payload"]
    assert sealed["hypotheses"] == proposal["hypotheses"]
    assert sealed["contradiction"] == proposal["contradiction"]
    request = {"name": "test-target", "operation_id": "science.experiment.v1",
        "inputs": [{"port": "subject", "artifact_names": [output]}], "instruction": "Test the exact H question if it has a mechanism."}
    admissible = root.call_tool("operation_preflight", request)["admissible"]
    if case == "target-mechanism":
        assert admissible
        assert root.call_tool("operation_invoke", request)["result"]["state"] == "queued"
    else:
        assert not admissible  # Existing empty-portfolio behavior; no forced experiment.
    assert runtime.scheduler_bindings.list(instance=instance.instance_id, namespace="approval") == ()


def test_feedback_policy_and_existing_stage_evidence_reach_independent_analysis(tmp_path, catalog):
    from scidiscovery.artifact_agent.schema.common import canonical_json
    runtime, instance, root = _root(tmp_path, catalog=catalog)
    runtime.runs.operation_catalog = catalog
    root.call_tool("artifact_ingest_text", {"name": "goal",
        "text": "Explore useful routes within the original permissions; retain the best candidate and unfinished requirements."})
    proposal = _proposal(hypothesis_keys=("promising", "weak_control"))
    proposal.pop("research_objective_key")
    h = _complete(runtime, root, "H", "science.hypothesis.propose.v1", {"subject": "goal"}, proposal)
    queued = root.call_tool("operation_invoke", {"name": "W", "operation_id": "science.experiment.v1",
        "inputs": [{"port": "subject", "artifact_names": [h]}],
        "instruction": "Test the exact current H question within its original constraints."})
    assert queued["result"]["state"] == "queued"
    worker = attached_worker(runtime, root, "W")
    opened = worker.call_tool("worker_open_assignment", {})
    assignment = json.loads(Path(opened["assignment_path"]).read_bytes())
    role = " ".join(assignment["role_instructions"].split())
    assert "fixed grid or preplanned comparison for initial screening" in role
    assert "After observations, choose the next trial" in role
    assert "refine a promising route inside current H, stop a weak route" in role
    assert "weak-control tail with no improvement does not show" in role
    assert "W does not own global run-count completion" in role
    assert "H revision before executing the new direction" in role
    assert "original user constraints and control permissions remain binding" in role
    assert "native shell permissions and installed environment" in role
    assert "no submission is required for each exp run" in json.dumps(assignment["tool_contracts"])
    schema = json.loads((Path(opened["workspace_path"]) / "schema/result.schema.json").read_bytes())
    semantic = json.dumps(schema["properties"]["payload"]["x-scidiscovery-semantic-constraints"])
    assert "subsequent choices use observed evidence" in semantic
    assert "weak-control tail does not establish exhaustion of a promising route" in semantic
    assert "no per-run form, approval or fixed trial limit" in semantic
    assert catalog.operation("science.experiment.v1").spec.review is None
    # Synthetic stage evidence exercises the real tool and sealed handoff, not a
    # claim that a model chose or actually executed this scientific trajectory.
    screening = worker.call_tool("worker_experiment_stage", {"stage": "design",
        "conclusion": "Synthetic initial grid compares the two current H routes."})["reference"]
    observed = worker.call_tool("worker_experiment_stage", {"stage": "validity", "materials": [screening],
        "conclusion": "Synthetic observation: promising route separates from the weak control; a preset weak tail adds no gain.",
        "remaining_question": "The promising route is not exhausted; refine its intervention within current H."})["reference"]
    revised = worker.call_tool("worker_experiment_stage", {"stage": "design", "materials": [observed],
        "conclusion": "Stop the uninformative weak tail and narrow the next contrast on the promising route using the observed separation.",
        "remaining_question": "If this contrast challenges the mechanism, seal it for A then H revision; global completion remains open."})["reference"]
    report = {"summary": "Synthetic feedback trajectory retained; independent analysis is needed.",
        "outcome": "inconclusive", "remaining_question": "Assess the promising route and unfinished original requirements.",
        "limitations": ["Synthetic stage evidence; no live trial or global success is claimed."],
        "adopted_stages": [screening, observed, revised]}
    Path(opened["output_directory"], "result.json").write_bytes(canonical_json({"payload": report}))
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    stage = root.facade.run_status(name="W", stage_reference=revised)["sealed_stages"]["material"]
    assert "observed separation" in json.loads(stage["text"])["conclusion"]
    output = root.call_tool("run_status", {"name": "W"})["output_artifact_name"]
    analysis = {"summary": "The weak tail does not establish exhaustion; original requirements remain open.",
        "overall_verdict": "inconclusive", "claim_allowed": False,
        "limitations": report["limitations"], "remaining_contradiction": report["remaining_question"],
        "next_action": "Continue the promising contrast within current H; a mechanism change requires H revision after A."}
    _complete(runtime, root, "A", "science.result.analyze.v1", {"subject": output}, analysis, verdict="inconclusive")
    sealed = root.facade.run_status(name="A", intent="full")["sealed_output"]["payload"]
    assert sealed["next_action"] == analysis["next_action"]
    assert runtime.scheduler_bindings.list(instance=instance.instance_id, namespace="approval") == ()


def _assert_closeout_policy(role):
    raw = role
    role = " ".join(role.split())
    for clause in (
        "A bears the burden of supporting successful closeout, especially early closeout",
        "list known reasonable uncovered directions",
        "for each, with original requirements and sealed evidence",
        "Do not enumerate every possible solution",
        "default to continued research", "send a complete question to W within current H",
        "to H for explicit revision", "request evidence extraction for missing materials",
        "wait for missing authorization", "preserve unmet exploration, run-count and delivery requirements",
        "A fixed weak-control tail or proxy plateau", "Read current control budget through worker_open_assignment",
        "assignment.json is an initial snapshot", "Worker task deadline/allocation from global loop",
        "missing or partial global usage makes sufficiency/exhaustion unknown",
        "Unknown budget alone does not justify stopping",
        "without independent evidence of target representativeness",
        "It cannot alone establish target achievement or reasonable results under target conditions",
        "keep those conclusions unknown", "simulation metrics explicitly accepted by the original task",
        "without accessing hidden tests or inventing success",
    ):
        assert clause in role
        # Structure: each clause is in the compact core or a core-tagged on-demand section.
        from tests.operations.test_minimum_support import reachable
        reachable(raw, clause)


def test_closeout_policy_reaches_compiled_analysis_and_neutral_consumers(catalog):
    from scidiscovery.artifact_agent.service.progression import INSTRUCTION
    _assert_closeout_policy(_assignment(catalog, "science.result.analyze.v1")["role_instructions"])
    schema = json.loads(result_schema_json(catalog.operation("science.result.analyze.v1")))
    payload = schema["properties"]["payload"]
    semantic = json.dumps(payload["x-scidiscovery-semantic-constraints"])
    assert "per-direction reasons for known reasonable uncovered directions" in semantic
    assert "those conclusions remain unknown" in semantic
    assert "Original-task-accepted simulation metrics retain their original criteria" in semantic
    assert "not a new control gate, budget threshold, form or approval" in semantic
    assert "budget" not in payload["properties"]
    assert catalog.operation("science.result.analyze.v1").spec.review is None
    for text in (load_scheduler_prompt(), INSTRUCTION):
        text = " ".join(text.split())
        assert "A local pass" in text and "whole-task success" in text
        assert "Root does not decide" in text
        assert "global" in text and "unknown" in text
    root_policy = " ".join(load_scheduler_prompt().split())
    assert "Use current control-provided budget for scheduling" in root_policy
    assert "Workers receive control-provided balances through their own tools" in root_policy
    assert "50%" not in semantic


@pytest.mark.parametrize("decision", ["continue", "revise", "success", "proxy", "extract", "wait", "limited"])
def test_exact_analysis_delivers_closeout_gap_and_owner_direction_without_new_gate(tmp_path, catalog, decision):
    from scidiscovery.artifact_agent.schema.common import canonical_json
    runtime, instance, root = _root(tmp_path, catalog=catalog)
    runtime.runs.operation_catalog = catalog
    original = ("Evaluate the explicitly accepted simulation metric and deliver its result." if decision == "success" else
        "Continue useful exploration within permissions and deliver the final candidate; a local pass does not finish this task.")
    root.call_tool("artifact_ingest_text", {"name": "goal", "text": original})
    proposal = _proposal(hypothesis_keys=("current_route",))
    proposal.pop("research_objective_key")
    h = _complete(runtime, root, "H", "science.hypothesis.propose.v1", {"subject": "goal"}, proposal)
    w = _complete(runtime, root, "W", "science.experiment.v1", {"subject": h}, {
        "summary": "Synthetic local pass after a weak-control tail; target representativeness is not independently supported.",
        "outcome": "inconclusive", "limitations": ["Synthetic evidence exercises transport only."],
        "remaining_question": "Assess original completion requirements and target coverage independently.",
    }, verdict="inconclusive")
    directions = {
        "continue": f"W: continue the bounded current-route contrast using {h}; the weak tail does not exclude this useful direction.",
        "revise": "H: revise from goal and A.analysis for a distinct target mechanism; current-route scope is too narrow.",
        "success": "Close out successfully: the original accepts this simulation metric, its condition and delivery are supported.",
        "proxy": "H: clarify target validation from goal and A.analysis; self-built proxy ranks candidates only, target achievement and reasonableness remain unknown.",
        "extract": "Evidence extraction: obtain the missing target observation from goal within the existing permissions.",
        "wait": "Wait for authorization for the specified external observation; the current proxy cannot settle the target.",
        "limited": "Stop with a limited conclusion: required target observations cannot be obtained lawfully; exploration and final delivery remain unfinished.",
    }
    request = {"name": "A", "operation_id": "science.result.analyze.v1",
        "inputs": [{"port": "subject", "artifact_names": [w]}],
        "instruction": "Independently assess the exact result and original requirements within current permissions."}
    assert root.call_tool("operation_invoke", request)["result"]["state"] == "queued"
    worker = attached_worker(runtime, root, "A")
    opened = worker.call_tool("worker_open_assignment", {})
    assignment = json.loads(Path(opened["assignment_path"]).read_bytes())
    _assert_closeout_policy(assignment["role_instructions"])
    source = next(item for item in assignment["inputs"] if item["source_name"] == "objective_source")
    assert (Path(opened["workspace_path"]) / source["relative_path"]).read_text() == original
    budget = json.loads(Path(opened["start_here_path"]).read_bytes())["budget"]
    assert budget["source"] == "control" and budget["loop"] is None
    assert "remaining_tokens" not in budget  # Local TTL cannot invent global sufficiency.
    successful = decision == "success"
    report = {"summary": "Original accepted metric and delivery supported." if successful else "Local pass; global requirements remain open.",
        "overall_verdict": "pass" if decision in {"success", "continue"} else "inconclusive",
        "claim_allowed": successful,
        "limitations": [] if successful else ["Global budget unknown; proxy covers only its self-selected perturbations; original exploration/delivery remain open."],
        "remaining_contradiction": "No remaining original requirement in this bounded fixture." if successful else
            "Known reasonable current-route refinement remains untested; weak-control tail does not exclude it. Target achievement and reasonableness are unknown.",
        "next_action": directions[decision]}
    Path(opened["output_directory"], "result.json").write_bytes(canonical_json({"payload": report}))
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    compact = root.call_tool("run_status", {"name": "A"})
    assert compact["scheduler_signal"]["summary"] == report["summary"]
    assert compact["scheduler_signal"]["next_actions"] == [report["next_action"]]
    assert _values(root, "A")["/claim_allowed"] is successful
    sealed = root.facade.run_status(name="A", intent="full")["sealed_output"]["payload"]
    assert sealed.get("objective_assessment") is None
    if decision == "continue":
        following = {"name": "W2", "operation_id": "science.experiment.v1",
            "inputs": [{"port": "subject", "artifact_names": [h]}], "instruction": report["next_action"]}
        assert root.call_tool("operation_invoke", following)["result"]["state"] == "queued"
    elif decision == "revise":
        revised = _proposal(hypothesis_keys=("new_mechanism",))
        revised.pop("research_objective_key")
        revised.update(contradiction=report["remaining_contradiction"])
        _complete(runtime, root, "H2", "science.hypothesis.propose.v1",
            {"subject": "goal", "previous_hypotheses": h, "result_analysis": compact["output_artifact_name"]}, revised,
            verdict="inconclusive")
    assert runtime.scheduler_bindings.list(instance=instance.instance_id, namespace="approval") == ()


def test_progression_preserves_local_pass_continuation_without_completing_goal(progression):
    from functools import partial
    from tests.operations.test_scientific_progress import active
    p = progression
    root = active(p)
    complete = partial(_complete, measure_usage=True)
    proposal = _proposal(hypothesis_keys=("current_route",))
    proposal.pop("research_objective_key")
    h = complete(p.runtime, root, "H", "science.hypothesis.propose.v1", {"subject": "goal"}, proposal)
    w = complete(p.runtime, root, "W", "science.experiment.v1", {"subject": h}, {
        "summary": "Local contrast passed; coverage remains limited.", "outcome": "inconclusive",
        "remaining_question": "Assess the original goal and current-route refinement.",
        "limitations": ["Synthetic pipeline evidence; target coverage is unknown."]})
    report = {"summary": "Local pass; the original goal remains unresolved.", "overall_verdict": "pass", "claim_allowed": False,
        "limitations": ["Self-built proxy lacks independent target-representativeness evidence."],
        "remaining_contradiction": "Known reasonable current-route refinement remains uncovered.",
        "next_action": f"W: refine the bounded current route using {h}; retain original criteria and uncertainty."}
    complete(p.runtime, root, "A", "science.result.analyze.v1", {"subject": w}, report)
    status = root.call_tool("progression_status", {})
    saved = row(p)
    snapshot = {"goal": saved["objective_ref_json"], "runs": [{"name": "A", "state": "completed"}], "approvals": []}
    brief = json.loads(p.coordinator._brief(saved, snapshot, 30000).split("\n")[-1])
    change = next(item for item in brief["changes"] if item["name"] == "A")
    assert change["scheduler_signal"]["next_actions"] == [report["next_action"]]
    assert report["limitations"][0] in json.dumps(status["closeout"])
    assert saved["state"] == "active" and not (checkpoint(p).get("report") or {}).get("completed")
    assert "remaining_tokens" in brief["budget"] and "token_coverage" in brief["budget"]
    # Control relays a direction; the fixture's science is not a model verdict.
    following = root.call_tool("operation_invoke", {"name": "W2", "operation_id": "science.experiment.v1",
        "inputs": [{"port": "subject", "artifact_names": [h]}], "instruction": report["next_action"]})
    assert following["result"]["state"] == "queued"
