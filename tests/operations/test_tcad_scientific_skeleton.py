"""Scientific skeleton author path through compiled Run and downstream admission."""
import json
from pathlib import Path

from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from tcad_artifact.execution_control import SolverCapability
from tests.operations.test_agent_contract_alignment import _feedback_root, experiment_case
from tests.operations.test_l4_local_tcad import (
    _system, _invoke, _debug_worker, _ImmediateDebugAdapter, _write_sprocess_workspace,
    _portfolio, LocalWorkerMCPRouter,
)


def skeleton():
    return {"selected_hypothesis_keys": ["hypothesis_a"], **{name: ["Bounded scientific fixture with stated evidence basis."] for name in (
        "current_objectives", "competing_explanations_and_controls", "changed_conditions",
        "held_conditions", "observables", "discrimination_criteria_and_basis",
        "immutable_conditions", "stop_conditions")}}


def test_skeleton_author_projection_review_package_analysis(
    tmp_path, monkeypatch, experiment_case,
):
    runtime, instance, root, skeleton_request, _ = _feedback_root(
        tmp_path, monkeypatch, experiment_case,
        "science.experiment.skeleton.v1", name="skeleton_design",
    )
    catalog = runtime.runs.operation_catalog
    instance_id = instance.instance_id
    def register(name, value, schema, parents=(), labels=None):
        artifact = runtime.artifacts.register(canonical_json(value), ArtifactRegistration(
            kind="fixture", schema_id=schema, payload_schema_version=1, media_type="application/json",
            creator=runtime.actor, parent_refs=parents, labels=labels or {}), idempotency_key=name)
        runtime.scheduler_bindings.bind(instance=instance_id, namespace="artifact", name=name, object_id=artifact.artifact_id)
        return artifact
    def artifact(name):
        aid = runtime.scheduler_bindings.resolve(instance=instance_id, namespace="artifact", name=name)
        return runtime.artifacts.get_by_id(aid)
    def binding(port, name):
        return {"port": port, "artifact_names": [name]}
    root.call_tool("operation_invoke", skeleton_request)
    compiled_skeleton = catalog.operation("science.experiment.skeleton.v1")
    designer = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled_skeleton.spec.operation_id,
                                    operation_digest=compiled_skeleton.digest)
    opened = designer.call_tool("worker_open_assignment", {})
    Path(opened["output_directory"], "result.json").write_bytes(canonical_json(dict(
        schema_version=1,
        handoff=dict(verdict="pass", summary="Bounded scientific skeleton."),
        payload=skeleton(),
    )))
    assert designer.call_tool("worker_submit_result", {})["state"] == "completed"
    skeleton_name = root.call_tool("run_status", {"name": "skeleton_design"})["output_artifact_name"]
    capability = SolverCapability(
        profile_id="skeleton_fixture", solver_kind="sprocess", executable="/opt/fake/sprocess",
        environment={}, release_evidence="Synthetic fixture", public_release_label="Fixture",
    )
    register("execution_capability", capability.public_snapshot().model_dump(mode="json"),
             "tcad.solver-capability.v2")
    register("experiment_plan", _portfolio().model_dump(mode="json"),
             "scidiscovery.experiment-portfolio.v1")
    author_inputs = [binding("execution_capability", "execution_capability"),
                     binding("scientific_skeleton", skeleton_name)]
    both = root.call_tool("operation_preflight", dict(instruction="Exercise the bounded skeleton fixture.", name="both", operation_id="tcad.deck.author.initial.v1", inputs=author_inputs+[binding("experiment_plan", "experiment_plan")]))
    assert not both["admissible"] and both["reason_code"] == "input_author_plan_exact_one"
    _invoke(root, "author", "tcad.deck.author.initial.v1", author_inputs)
    worker = _debug_worker(catalog, runtime, _ImmediateDebugAdapter(), tmp_path / "debug")
    opened = worker.call_tool("worker_open_assignment", {})
    _write_sprocess_workspace(opened)
    workspace = Path(opened["workspace_path"])
    (workspace / "deck/execution-plan.json").write_bytes(canonical_json(_portfolio().model_dump(mode="json")))
    # No early scientific review; controlled fixture observations still required.
    for mode in ("preflight", "initialization"):
        reply = worker.call_tool("worker_tcad_debug_run", {"run_name": mode, "mode": mode})
        assert reply["state"] == "succeeded", reply
    changed_plan = _portfolio().model_dump(mode="json")
    changed_plan["priority_rationale"] = "Changed author implementation plan identity."
    (workspace / "deck/execution-plan.json").write_bytes(canonical_json(changed_plan))
    stale = worker.call_tool("worker_submit_result", {})
    assert stale["state"] == "rejected", stale
    (workspace / "deck/execution-plan.json").write_bytes(canonical_json(_portfolio().model_dump(mode="json")))
    submitted = worker.call_tool("worker_submit_result", {})
    assert submitted["state"] == "completed", submitted
    project_name = root.call_tool("run_status", {"name": "author"})["output_artifact_name"]
    project = json.loads(runtime.artifacts.read(artifact(project_name).ref))
    assert project["execution_plan"] == _portfolio().model_dump(mode="json")
    register("forged_project", project, "tcad.deck-project.v1", (artifact(skeleton_name).ref,),
             dict(artifact(project_name).labels))
    forged = root.call_tool("operation_preflight", dict(name="forged_projection", operation_id="tcad.execution-plan.project.v1", inputs=[binding("project", "forged_project")]))
    assert forged["reason_code"] == "input_skeleton_project_producer_required", forged
    projection = root.call_tool("operation_invoke", dict(name="project_plan", operation_id="tcad.execution-plan.project.v1", inputs=[binding("project", project_name)]))
    plan_name = projection["result"]["outputs"][0]["artifact_name"]
    assert json.loads(runtime.artifacts.read(artifact(plan_name).ref)) == project["execution_plan"]
    assert artifact(plan_name).parent_refs == (artifact(project_name).ref,)
    assert artifact(plan_name).labels["scientific_claim_admissible"] == "false"
    from tests.operations.m3_transform_equivalence_runner import _review
    from tests.operations.test_m2_curve_analysis_boundary import _bundle, _contract
    plan_review = json.loads(_review())
    contract_review = {**plan_review, "summary": "Independent fixture contract review."}
    register("projected_plan_review", plan_review, "scidiscovery.scientific-review.v1")
    register("curve_contract", _contract().model_dump(mode="json"),
             "scidiscovery.curve-experiment-contract.v1")
    register("curve_contract_review", contract_review, "scidiscovery.scientific-review.v1")
    register("reference_bundle", _bundle().model_dump(mode="json"),
             "scidiscovery.curve-bundle.v1")
    legacy_claim = root.call_tool("operation_preflight", dict(
        name="projected_plan_legacy_claim",
        operation_id="scidiscovery.curve-reference-coverage.v1",
        inputs=[binding("experiment_plan", plan_name),
                binding("experiment_review", "projected_plan_review"),
                binding("curve_contract", "curve_contract"),
                binding("curve_contract_review", "curve_contract_review"),
                binding("reference_bundles", "reference_bundle")],
    ))
    assert not legacy_claim["admissible"]
    assert legacy_claim["reason_code"] == "input_scientific_claim_forbidden"
    denied_author = root.call_tool("operation_preflight", dict(name="projection_as_design", operation_id="tcad.deck.author.initial.v1",
        instruction="Attempt to reuse a projection as a legacy design.", inputs=[binding("execution_capability", "execution_capability"), binding("experiment_plan", plan_name)]))
    assert denied_author["reason_code"] == "input_projected_plan_not_author_design"
    review_inputs = [*author_inputs, binding("project", project_name), binding("experiment_plan", plan_name)]
    register("same_bytes_wrong_origin", project["execution_plan"], "scidiscovery.experiment-portfolio.v1")
    denied = root.call_tool("operation_preflight", dict(instruction="Exercise the bounded skeleton fixture.", name="wrong_origin", operation_id="tcad.deck.review.v1", inputs=[*review_inputs[:-1], binding("experiment_plan", "same_bytes_wrong_origin")]))
    assert denied["admissible"] is False
    _invoke(root, "review", "tcad.deck.review.v1", review_inputs)
    compiled = catalog.operation("tcad.deck.review.v1")
    reviewer = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    opened = reviewer.call_tool("worker_open_assignment", {})
    listed = reviewer.call_tool("worker_reference_read", {
        "source": "scientific_skeleton", "action": "list",
    })
    objective_reference = next(item for item in listed["references"]
                               if item.get("alias") == "research_objective")
    objective = reviewer.call_tool("worker_reference_read", {
        "source": "scientific_skeleton", "action": "read",
        "reference": objective_reference["reference"], "delivery": "file",
    })
    assert Path(objective["file_path"]).read_bytes() == runtime.artifacts.read(
        artifact("research_objective").ref)
    review = dict(verdict="pass", scientific_assessment="pass", capability_sha256=capability.canonical_sha256(),
        summary="Fixture science and implementation assessed together.", rationale="The comparison is sufficient within fixture limits.",
        physical_fidelity="pass", implementation_fidelity="pass", syntax_fidelity="pass", numerical_protocol_fidelity="pass", execution_ready=True)
    output = Path(opened["output_directory"]) / "result.json"
    def write_review(value):
        output.write_bytes(canonical_json(dict(schema_version=1, handoff=dict(verdict="pass", summary="Comprehensive fixture review."), payload=value)))
    missing = dict(review); missing.pop("scientific_assessment")
    write_review(missing)
    assert reviewer.call_tool("worker_submit_result", {})["state"] == "rejected"
    write_review(review)
    submitted = reviewer.call_tool("worker_submit_result", {})
    assert submitted["state"] == "completed", submitted
    review_name = root.call_tool("run_status", {"name": "review"})["output_artifact_name"]
    package_request = dict(name="package", operation_id="tcad.reviewed-deck-package.v2", inputs=[
        binding("project", project_name), binding("review", review_name), binding("capability", "execution_capability"),
        binding("experiment_plan", plan_name), binding("scientific_skeleton", skeleton_name)])
    admitted = root.call_tool("operation_preflight", package_request)
    assert admitted["admissible"], admitted
    packaged = root.call_tool("operation_invoke", package_request)
    package_name = packaged["result"]["outputs"][0]["artifact_name"]
    register("standalone_skeleton", skeleton(), "scidiscovery.experiment-scientific-skeleton.v1")
    unqualified = root.call_tool("operation_preflight", {
        **package_request, "name": "standalone_skeleton_package",
        "inputs": [*package_request["inputs"][:-1], binding("scientific_skeleton", "standalone_skeleton")],
    })
    assert not unqualified["admissible"]
    assert unqualified["reason_code"] == "input_skeleton_objective_source_required"
    # Terminal zero-output fixture permits bounded failure analysis; no solver/execution is launched.
    register("manifest", dict(started_at=None, completed_at="2026-09-20T00:00:00Z", terminal_state="failed", exit_code=1, error="Fixture failure", outputs=[]), "opaque", (artifact(package_name).ref,))
    analysis = dict(instruction="Exercise the bounded skeleton fixture.", name="analysis", operation_id="tcad.result.analyze.v1", inputs=[
        binding("experiment_plan", plan_name), binding("execution_review", review_name), binding("scientific_skeleton", skeleton_name),
        binding("reviewed_package", package_name), binding("runtime_manifest", "manifest")])
    missing_review = {**analysis, "name": "analysis_without_execution_review",
        "inputs": [item for item in analysis["inputs"] if item["port"] != "execution_review"]}
    rejected = root.call_tool("operation_preflight", missing_review)
    assert rejected["admissible"] is False and rejected["reason_code"] == "guard_rejected", rejected
    admitted = root.call_tool("operation_preflight", analysis)
    assert admitted["admissible"], admitted
    wrong = {**analysis, "name": "wrong_analysis", "inputs": [binding("experiment_plan", "same_bytes_wrong_origin"), *analysis["inputs"][1:]]}
    assert not root.call_tool("operation_preflight", wrong)["admissible"]
    root.call_tool("operation_invoke", analysis)


def test_skeleton_gap_without_concrete_plan_is_reviewable_not_projectable(tmp_path):
    catalog, runtime, root, _ = _system(tmp_path, solver_kind="sprocess")
    instance = runtime.scheduler_bindings.list_instances()[0].instance_id
    record = runtime.artifacts.register(canonical_json(skeleton()), ArtifactRegistration(
        kind="fixture", schema_id="scidiscovery.experiment-scientific-skeleton.v1", payload_schema_version=1,
        media_type="application/json", creator=runtime.actor), idempotency_key="skeleton-gap")
    runtime.scheduler_bindings.bind(instance=instance, namespace="artifact", name="skeleton", object_id=record.artifact_id)
    inputs = [dict(port="execution_capability", artifact_names=["execution_capability"]), dict(port="scientific_skeleton", artifact_names=["skeleton"])]
    _invoke(root, "gap", "tcad.deck.author.initial.v1", inputs)
    worker = _debug_worker(catalog, runtime, _ImmediateDebugAdapter(), tmp_path / "debug")
    opened = worker.call_tool("worker_open_assignment", {})
    workspace = Path(opened["workspace_path"])
    assert not (workspace / "deck/execution-plan.json").exists()
    (workspace / "deck/execution-plan.json").write_text("{unfinished author choice")
    (workspace / "deck/gap.json").write_bytes(canonical_json(dict(result_kind="implementation_gap",
        summary="The interpretation of the initial observation is unresolved.", missing_inputs=[],
        affected_work=[dict(plan_locator="/observables/0", impact="The observable time semantics determine the test.")],
        suggested_resolution="Obtain a bounded independent scientific judgment before searching implementation.")))
    (workspace / "deck/handoff.json").unlink()
    submitted = worker.call_tool("worker_submit_result", {})
    assert submitted["state"] == "completed", submitted
    gap = root.call_tool("run_status", {"name":"gap"})["output_artifact_name"]
    denied = root.call_tool("operation_preflight", dict(name="gap_projection", operation_id="tcad.execution-plan.project.v1",
        inputs=[dict(port="project", artifact_names=[gap])]))
    assert not denied["admissible"]
    _invoke(root, "gap_review", "tcad.deck.review.v1", [dict(port="project", artifact_names=[gap]), *inputs])
    compiled = catalog.operation("tcad.deck.review.v1")
    reviewer = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    opened = reviewer.call_tool("worker_open_assignment", {})
    assert Path(opened["workspace_path"], "deck/execution-plan.json").read_text() == "{unfinished author choice"
    template = json.loads(Path(opened["workspace_path"], "deck/review-template.json").read_bytes())
    template["payload"].update(summary="Resolve initial observation semantics before implementation.", rationale="No further implementation search can distinguish these meanings.")
    Path(opened["output_directory"], "result.json").write_bytes(canonical_json(template))
    submitted = reviewer.call_tool("worker_submit_result", {})
    assert submitted["state"] == "completed", submitted
