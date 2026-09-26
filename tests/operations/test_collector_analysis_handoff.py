"""Real collection/ingestion/analysis seams, starting from bounded terminal fixtures.

No solver or approval is run: durable terminal runner files and submitted execution
state are fixture setup. Collection, status ingestion, artifact registration, Root
binding/admission and Worker validation use their production implementations.
"""
from __future__ import annotations
from tests.operations.tcad_policy_fixtures import policy_fields

from dataclasses import replace
import hashlib
import sqlite3

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.execution import LocalFileDescriptor
from scidiscovery.artifact_agent.service.approvals import ApprovalService
from scidiscovery.artifact_agent.service.executions import ExecutionService
from tcad_artifact.execution_control import TCADExecutionFacade, TCADExecutionPolicy, ToolProfile
from tests.operations.test_tcad_result_analysis import (
    analysis_system, analysis_report, open_analysis, write_analysis,
)


def _analysis_system(tmp_path):
    catalog, runtime, root, request, artifacts, register = analysis_system(tmp_path)
    # The base analysis fixture does not enable execution services. These services
    # belong solely to this temporary test state; no approval decision is issued.
    approvals = ApprovalService(
        artifacts=runtime.artifacts, database_path=runtime.state_root / "database" / "approvals.sqlite3",
        service_actor=runtime.actor, receipt_secret=b"collector-fixture-only-secret-0000",
    )
    executions = ExecutionService(
        artifacts=runtime.artifacts, approvals=approvals,
        database_path=runtime.state_root / "database" / "executions.sqlite3",
        exchange_root=runtime.state_root / "execution-exchange", service_actor=runtime.actor,
    )
    runtime = replace(runtime, approvals=approvals, executions=executions)
    root.facade.approvals = approvals
    root.facade.executions = executions
    return catalog, runtime, root, request, artifacts, register


def _collect_execution(system, directory, *, name, state="succeeded", output_names=("A", "B")):
    _, runtime, root, _, artifacts, _ = system
    collector = TCADExecutionFacade(
        policy=TCADExecutionPolicy(**policy_fields(), allowed_input_roots=(str(directory),), tools=(ToolProfile(
            profile_id="fixture", solver_kind="deterministic_tool",
            executable="/bin/true", release_evidence="unused terminal fixture",
        ),)), state_root=directory,
    )
    external_id = "terminal_" + name
    run_dir = collector.runs_root / external_id
    (run_dir / "work").mkdir(parents=True)
    raw = runtime.artifacts.read(artifacts["output_A"].ref)
    products = []
    for product_name in output_names:
        (run_dir / "work" / (product_name + ".plx")).write_bytes(raw)
        products.append(dict(name=product_name, relative_path=product_name + ".plx",
            media_type="application/x-synopsys-plx", size_bytes=len(raw),
            sha256=hashlib.sha256(raw).hexdigest()))
    manifest = dict(started_at=None, completed_at="2026-09-09T00:00:00Z",
        terminal_state=state, exit_code=0 if state == "succeeded" else 1,
        error="" if state == "succeeded" else "fixture failure", outputs=products)
    (run_dir / "output_manifest.json").write_bytes(canonical_json(manifest))
    (run_dir / "diagnostic.log").write_bytes(b"bounded diagnostic, solver iterations 3\n")
    (run_dir / "done").touch()
    with sqlite3.connect(collector.database_path) as connection:
        connection.execute("INSERT INTO submissions VALUES (?, ?, ?, ?)", (
            hashlib.sha256(name.encode()).hexdigest(), external_id,
            "2026-09-09T00:00:00Z", "terminal",
        ))
    collected = collector.tcad_collect(run_id=external_id)
    assert {item["name"] for item in collected["outputs"]} == {
        *output_names, "tcad_log", "tcad_manifest"
    }
    execution_id = runtime.executions.create(executor="tcad_artifact:tcad",
        preparation_profile="fixture", payload_ref=artifacts["package"].ref)
    # Seed the preexisting submitted boundary; no execution authorization is performed.
    with sqlite3.connect(runtime.executions.database_path) as connection:
        connection.execute("UPDATE executions SET state='submitted', external_run_id=? WHERE execution_id=?",
            (external_id, execution_id))
    runtime.executions.record_status(execution_id=execution_id, external_run_id=external_id, state=state)
    runtime.executions.ingest_result(execution_id=execution_id, external_run_id=external_id,
        outputs=tuple(LocalFileDescriptor.model_validate(item) for item in collected["outputs"]))
    runtime.scheduler_bindings.bind(instance=root.facade._instance_id(), namespace="execution",
        name=name, object_id=execution_id)
    published = root.call_tool("execution_outputs", {"name": name})
    return {item["output_label"]: item["artifact_name"] for item in published["outputs"]}


def _bind_collected(system, outputs):
    request = system[3]
    request["inputs"] = [item for item in request["inputs"] if item["port"] not in {
        "runtime_manifest", "solver_outputs", "diagnostics"
    }]
    request["inputs"].extend([
        dict(port="runtime_manifest", artifact_names=[outputs["tcad_manifest"]]),
        dict(port="diagnostics", artifact_names=[outputs["tcad_log"]]),
    ])
    products = [outputs[name] for name in ("A", "B") if name in outputs]
    if products:
        request["inputs"].append(dict(port="solver_outputs", artifact_names=products))


@pytest.mark.parametrize("state, products", [("succeeded", ("A", "B")), ("failed", ())])
def test_collected_log_and_missing_products_allow_limited_analysis(tmp_path, state, products):
    system = _analysis_system(tmp_path)
    outputs = _collect_execution(system, tmp_path / "collector", name="collected", state=state, output_names=products)
    _bind_collected(system, outputs)
    worker, opened = open_analysis(system)
    write_analysis(opened, analysis_report(alias="diagnostics"))
    submitted = worker.call_tool("worker_submit_result", {})
    assert submitted["state"] == "completed", submitted
    sealed = system[2].call_tool("run_status", {"name": "analysis", "view": "detail"})["sealed_output"]
    assert sealed["payload"]["source_references"][0]["input_alias"] == "diagnostics"


def test_collector_log_in_solver_products_is_rejected_before_run(tmp_path):
    system = _analysis_system(tmp_path)
    outputs = _collect_execution(system, tmp_path / "collector", name="collected")
    _bind_collected(system, outputs)
    root, request = system[2], system[3]
    request["inputs"] = [item for item in request["inputs"] if item["port"] != "diagnostics"]
    next(item for item in request["inputs"] if item["port"] == "solver_outputs")["artifact_names"].append(outputs["tcad_log"])
    before = root.call_tool("run_list", {})
    rejected = root.call_tool("operation_preflight", request)
    assert not rejected["admissible"]
    assert rejected["reason_code"] == "input_manifest_output_mismatch"
    with pytest.raises(Exception, match="input_manifest_output_mismatch"):
        root.call_tool("operation_invoke", request)
    assert root.call_tool("run_list", {}) == before


def test_cross_execution_same_bytes_diagnostic_is_rejected(tmp_path):
    system = _analysis_system(tmp_path)
    first = _collect_execution(system, tmp_path / "collector", name="first")
    second = _collect_execution(system, tmp_path / "collector", name="second")
    runtime, root, request = system[1:4]
    refs = [runtime.artifacts.get_by_id(root.facade._resolve("artifact", row["tcad_log"])).ref
        for row in (first, second)]
    assert runtime.artifacts.read(refs[0]) == runtime.artifacts.read(refs[1])
    _bind_collected(system, first)
    next(item for item in request["inputs"] if item["port"] == "diagnostics")["artifact_names"] = [second["tcad_log"]]
    before = root.call_tool("run_list", {})
    rejected = root.call_tool("operation_preflight", request)
    assert not rejected["admissible"]
    with pytest.raises(Exception):
        root.call_tool("operation_invoke", request)
    assert root.call_tool("run_list", {}) == before


def historical_analysis_fixture(tmp_path, *, operation_id="tcad.result.analyze.v1"):
    """Materialize, review and collect under one catalog, then upgrade the reviewer."""
    import json
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN as GENERAL
    from curve_score.plugin import PLUGIN as CURVE
    from tcad_artifact.plugin import PLUGIN as TCAD
    from scidiscovery.operations.catalog import compile_catalog
    from tests.operations.science_fixtures import _engineering_intent
    from tests.operations.test_historical_compatibility_paths import _complete

    system = _analysis_system(tmp_path)
    _, runtime, root, request, artifacts, register = system
    register("intent", _engineering_intent(), "scidiscovery.experiment-design-intent.v1")
    root.call_tool("operation_invoke", dict(name="materialized_plan",
        operation_id="science.experiment.materialize.v1", inputs=[
            dict(port="experiment_design_intent", artifact_names=["intent"])]))
    plan = runtime.artifacts.get_by_id(root.facade._resolve("artifact", "materialized_plan"))
    assert plan.labels["operation_id"] == "science.experiment.materialize.v1"
    review_name = _complete(runtime, root, "materialized_review", "science.object.review.v1",
        {"experiment_plan": "materialized_plan"},
        {"review_target": "experiment_portfolio", "verdict": "pass", "summary": "Exact materialized plan reviewed."})
    review = runtime.artifacts.get_by_id(root.facade._resolve("artifact", review_name))
    _complete(runtime, root, "negative_review", "science.object.review.v1",
        {"experiment_plan": "materialized_plan"},
        {"review_target": "experiment_portfolio", "verdict": "revise", "summary": "Retained historical concern."}, "revise")
    plan_value = json.loads(runtime.artifacts.read(plan.ref))
    package = json.loads(runtime.artifacts.read(artifacts["package"].ref))
    for output in package["project"]["expected_outputs"]:
        output["experiment_key"] = plan_value["proposals"][0]["experiment_key"]
    artifacts["package"] = register("materialized_package", canonical_json(package),
        "tcad.execution-package.v2", parents=(plan.ref,))
    for binding in request["inputs"]:
        if binding["port"] == "experiment_plan":
            binding["artifact_names"] = ["materialized_plan"]
        elif binding["port"] == "experiment_review":
            binding["artifact_names"] = [review_name]
        elif binding["port"] == "execution_package":
            binding["artifact_names"] = ["materialized_package"]
    outputs = _collect_execution(system, tmp_path / "collector", name="historical_execution", state="failed", output_names=())
    _bind_collected(system, outputs)
    report = analysis_report(alias="diagnostics")
    if operation_id == "science.result.diagnose.v1":
        register("generic_result", b"Terminal fixture failed.", "opaque", parents=(plan.ref,), media="text/plain")
        request["inputs"] = [item for item in request["inputs"] if item["port"] in {"experiment_plan", "experiment_review"}]
        request["inputs"].append(dict(port="experiment_results", artifact_names=["generic_result"]))
        report = json.loads(json.dumps(analysis_report(alias="experiment_results")).replace('"raw_evidence"', '"experiment_results"'))
    request["operation_id"] = operation_id
    request["inputs"].append(dict(port="current_progress", artifact_names=["negative_review.output"]))
    report.update(study_kind=plan_value["study_kind"],
        experiment_key=plan_value["validation_plans"][0]["experiment_key"],
        plan_key=plan_value["validation_plans"][0]["plan_key"])
    assert root.call_tool("operation_preflight", request)["admissible"]
    changed = GENERAL.model_copy(update={"operations": tuple(
        op.model_copy(update={"version": "historical-review-probe"})
        if op.operation_id == "science.object.review.v1" else op for op in GENERAL.operations)})
    current = compile_catalog((CORE_PLUGIN, changed, CURVE, TCAD))
    runtime.runs.operation_catalog = root.facade._operation_catalog = current
    status = root.call_tool("run_status", {"name": "materialized_review"})
    assert status["state"] == "completed" and status["sealed_output_status"] == "historical"
    assert status["scheduler_signal"]["verdict"] == "pass"
    assert not runtime.runs.is_exact_reviewer_output(review.ref,
        reviewer_operation="science.object.review.v1", reviewer_input_port="experiment_plan",
        accepted_verdicts=("pass",), subject_ref=plan.ref)
    return (current, *system[1:]), report


@pytest.mark.parametrize("operation_id", ("tcad.result.analyze.v1", "science.result.diagnose.v1"))
def test_historical_review_reaches_new_analysis_without_current_authority(tmp_path, operation_id):
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    system, report = historical_analysis_fixture(tmp_path, operation_id=operation_id)
    catalog, runtime, root, request, artifacts, register = system
    preflight = root.call_tool("operation_preflight", request)
    assert preflight["admissible"], preflight
    root.call_tool("operation_invoke", request)
    compiled = catalog.operation(operation_id)
    worker = LocalWorkerMCPRouter(runtime.runs, operation_id=operation_id, operation_digest=compiled.digest)
    opened = worker.call_tool("worker_open_assignment", {})
    write_analysis(opened, report)
    submitted = worker.call_tool("worker_submit_result", {})
    assert submitted["state"] == "completed", submitted
    assert root.call_tool("run_status", {"name": "analysis", "view": "detail"})["sealed_output"]["payload"]["claim_allowed"] is False
    # Analysis completion does not renew the old review's authoring authority.
    import json
    package = json.loads(runtime.artifacts.read(artifacts["package"].ref))
    register("capability", canonical_json(package["capability"]), "tcad.solver-capability.v2")
    author = dict(name="author_after_upgrade", operation_id="tcad.deck.author.initial.v1",
        instruction="Implement the exact plan after upgrade.", inputs=[
        dict(port="experiment_plan", artifact_names=["materialized_plan"]),
        dict(port="experiment_review", artifact_names=["materialized_review.output"]),
        dict(port="execution_capability", artifact_names=["capability"])])
    denied = root.call_tool("operation_preflight", author)
    assert not denied["admissible"] and denied["reason_code"] == "input_independent_review_incompatible"
    assert denied["port"] == "experiment_plan"


@pytest.mark.parametrize("operation_id", ("tcad.result.analyze.v1", "science.result.diagnose.v1"))
@pytest.mark.parametrize("wrong, port, code", (
    ("plan_shape", "experiment_plan", "input_content_incompatible"),
    ("review_shape", "experiment_review", "input_content_incompatible"),
    ("review_target", "experiment_review", "input_review_target_mismatch"),
    ("review_verdict", "experiment_review", "input_review_verdict_mismatch"),
))
def test_history_input_schema_errors_identify_the_port(tmp_path, operation_id, wrong, port, code):
    from scidiscovery.operations.input_validation import (
        InputBindingDescriptor, OperationInvocationError, ValidationSources,
    )
    from tcad_artifact.result_analysis import validate_analysis_inputs
    from curve_score.science_operations import Components
    from tests.operations.test_tcad_result_analysis import analysis_materials
    plan = analysis_materials()[0]
    review = dict(review_target="experiment_portfolio", verdict="pass", summary="Exact review.")
    if wrong == "review_target":
        review["review_target"] = "domain_contract"
    elif wrong == "review_verdict":
        review["verdict"] = "revise"
    sources = {"experiment_plan": plan.canonical_json(), "experiment_review": canonical_json(review)}
    if operation_id == "tcad.result.analyze.v1":
        _, runtime, root, request, _, _ = analysis_system(tmp_path)
        descriptors = {}
        for binding in request["inputs"]:
            alias = binding["port"]
            if alias not in {"experiment_plan", "experiment_review", "execution_package", "runtime_manifest"}:
                continue
            artifact = runtime.artifacts.get_by_id(root.facade._resolve("artifact", binding["artifact_names"][0]))
            sources[alias] = runtime.artifacts.read(artifact.ref)
            descriptors[alias] = InputBindingDescriptor(
                source_name=alias, port_name=alias, artifact_ref=artifact.ref,
                media_type=artifact.media_type, size_bytes=artifact.size_bytes,
                sha256=artifact.sha256, parent_refs=artifact.parent_refs,
            )
        sources["experiment_review"] = canonical_json(review)
        sources = ValidationSources(sources, descriptors)
    if wrong.endswith("_shape"):
        sources[port] = b'{}'
    checker = validate_analysis_inputs if operation_id == "tcad.result.analyze.v1" else Components.diagnosis_inputs.implementation
    with pytest.raises(OperationInvocationError) as failure:
        checker(sources)
    assert failure.value.reason_code == code
    assert failure.value.port == port and failure.value.field.startswith("/")
