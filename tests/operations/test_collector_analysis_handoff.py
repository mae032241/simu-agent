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
    published = root.call_tool("execution_outputs", {"name": name}, surface="execution")
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
    sealed = system[2].call_tool("run_status", {'name': "analysis", "intent": 'full'})["sealed_output"]
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
