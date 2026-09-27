"""Cross-task handoff through real Root/Worker routes, with bounded fake adapters."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.operations.test_r4_experiment_task import _real_experiment
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.service.experiment_execution import bind_experiment_services
from scidiscovery.operation_contract import DiagnosticError


def continuation(tmp_path, monkeypatch, solver="sprocess", *, all_stages=False, include_grid=True):
    runtime, root, catalog, connections, instance = _real_experiment(tmp_path, monkeypatch, solver)
    runs = runtime.runs
    old_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace="run", name="observe")
    records = runs.tool_evidence(old_id)
    implementation = next(r for r in records if r["metadata"].get("kind") == "experiment_implementation")
    chosen = records if all_stages else [implementation]
    bindings = runtime.scheduler_bindings.list(instance=instance.instance_id, namespace="artifact")
    names = [next(b.name for b in bindings if b.object_id == r["artifact_ref"]["artifact_id"]) for r in chosen]
    if solver == "sdevice" and include_grid:
        names.append("grid")  # A different port produces a different alias from the author's.
    invocation = {"name":"continuation", "operation_id":"science.experiment.v1",
        "inputs":[{"port":"research_objective", "artifact_names":["objective"]},
                  {"port":"prior_experiment", "artifact_names":["observe.output"]},
                  {"port":"scientific_materials", "artifact_names":names}], "instruction":"Reuse exact sealed materials."}
    result = root.call_tool("operation_invoke", invocation)
    assert result["result"]["state"] == "queued", result
    run_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace="run", name="continuation")
    connections.attach(run_id=run_id, platform_session="continuation-fixture", thread_id="next-owner")
    compiled = catalog.operation("science.experiment.v1")
    coordinator = runs.experiment_executions
    services = bind_experiment_services(runs, compiled, dict(coordinator.worker_services), coordinator=coordinator)
    worker = LocalWorkerMCPRouter(runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest, tool_services=services)
    opened = worker.call_tool("worker_open_assignment", {})
    alias = next(i.source_name for i in runs.status(run_id).inputs
                 if i.artifact_ref == ArtifactRef.model_validate(implementation["artifact_ref"]))
    return SimpleNamespace(runtime=runtime, runs=runs, root=root, instance=instance, worker=worker,
        coordinator=coordinator, run_id=run_id, old_id=old_id, implementation=implementation, alias=alias,
        workspace=Path(opened["workspace_path"]), records=records, invocation=invocation, catalog=catalog)


def submit(f, aliases, outcome="completed"):
    (f.workspace / "output/result.json").write_bytes(canonical_json({"schema_version":1,
        "payload":{"summary":"Retained exact observations.", "outcome":outcome,
                   "remaining_question":"", "adopted_stages":aliases}}))
    return f.worker.call_tool("worker_submit_result", {})


@pytest.mark.parametrize("solver", ["sprocess", "sdevice"])
def test_bound_implementation_runs_collects_and_delivers_without_prepare(tmp_path, monkeypatch, solver):
    f = continuation(tmp_path, monkeypatch, solver)
    original_ref = ArtifactRef.model_validate(f.implementation["artifact_ref"])
    assert f.alias != f.implementation["alias"]
    assert not f.runs.tool_evidence(f.run_id)
    debug = f.worker.call_tool("worker_experiment_debug", {"implementation":f.alias, "name":"diagnostic", "mode":"preflight"})
    assert debug["state"] == "succeeded"
    adapter = f.coordinator.bridge._adapter("tcad_artifact:tcad")
    adapter.lookup_submission = lambda _: None
    adapter.submit = lambda *args, **kw: ("continuation-external", "running")
    adapter.state = "running"
    started = f.worker.call_tool("worker_experiment_execute", {"action":"start", "implementation":f.alias})
    assert started["state"] == "running"
    assert submit(f, [f.alias], "blocked")["state"] == "rejected"  # Active execution cannot disappear.
    adapter.state = "succeeded"
    f.worker.call_tool("worker_experiment_execute", {"action":"advance"})
    collected = f.worker.call_tool("worker_experiment_execute", {"action":"collect"})
    assert collected["terminal_state"] == "succeeded" and "tcad_manifest" not in json.dumps(collected)
    exported = f.worker.call_tool("worker_experiment_execute", {"action":"export", "output_name":"binary"})
    assert (f.workspace / exported["path"]).read_bytes() == b"observed fixture\n"
    validity = f.worker.call_tool("worker_experiment_stage", {"stage":"validity", "conclusion":"Retained fixture observation.", "materials":[collected["reference"]]})
    completed = submit(f, [f.alias, collected["reference"], validity["reference"]])
    assert completed["state"] == "completed", completed
    assert not any(r["metadata"].get("kind") == "experiment_implementation" for r in f.runs.tool_evidence(f.run_id))
    assert f.runs.sealed_material_record(f.runs.status(f.run_id), f.alias)["artifact_ref"] == original_ref.model_dump(mode="json")
    stage = f.root.call_tool("run_status", {"name":"continuation", "stage_reference":f.alias})["sealed_stages"]["material"]
    assert stage["origin"] == "reused" and stage["adopted"] is True
    assert "artifact_ref" not in json.dumps(stage)
    if solver == "sdevice":
        assert json.loads(stage["text"])["scientific_files"]["device_grid"].startswith("scientific_materials")
    from scidiscovery.artifact_agent.approval_ui.workbench_render import _sealed_stages
    html = _sealed_stages({"sealed_stages":{"items":[stage]}, "key":"run:continuation"}, f.instance.instance_id)
    assert "复用已有封存材料" in html


def test_missing_file_and_unknown_implementation_have_repairable_diagnostics(tmp_path, monkeypatch):
    f = continuation(tmp_path, monkeypatch, "sdevice", include_grid=False)
    for alias, code in ((f.alias, "experiment_source_not_bound"), ("not_bound", "experiment_implementation_unavailable")):
        with pytest.raises(DiagnosticError) as caught:
            f.worker.call_tool("worker_experiment_debug", {"implementation":alias, "name":"not_submitted", "mode":"preflight"})
        assert caught.value.details[0]["code"] == code
    assert f.worker.call_tool("worker_experiment_debug", {"action":"status", "name":"not_submitted"})["submission"] == "not_submitted"


def test_execution_ownership_uses_request_not_reused_package(tmp_path, monkeypatch):
    from scidiscovery.plugin_runtime.diagnostics import RunOutputError
    f = continuation(tmp_path, monkeypatch)
    executions = f.runtime.executions
    old_execution = next(b.object_id for b in f.runtime.scheduler_bindings.list(instance=f.instance.instance_id, namespace="execution")
                         if executions.status(b.object_id).state == "collected")
    old = executions.request(old_execution)
    new_id = "exe_continued_pending"
    executions.create(executor=old.executor, preparation_profile=old.preparation_profile, payload_ref=old.payload_ref,
        execution_id=new_id, compiled_identity=old.compiled_identity, labels={"experiment_run":f.run_id})
    f.runtime.scheduler_bindings.bind(instance=f.instance.instance_id, namespace="execution",
        name="experiment-" + f.run_id + "-pending", object_id=new_id)
    with pytest.raises(RunOutputError):
        f.coordinator.require_idle(f.runs.status(f.run_id))
    f.coordinator.cancel_owned(f.runs.status(f.run_id))
    assert executions.status(new_id).state == "abandoned"
    assert executions.status(old_execution).state == "collected"


def test_old_implementation_execution_and_validity_can_be_adopted_by_exact_ref(tmp_path, monkeypatch):
    f = continuation(tmp_path, monkeypatch, all_stages=True)
    aliases = [i.source_name for i in f.runs.status(f.run_id).inputs if i.port_name == "scientific_materials"]
    result = submit(f, aliases)
    assert result["state"] == "completed", result


def test_diagnostic_reuse_never_changes_implementation_or_takes_over_active_job(tmp_path, monkeypatch):
    f = continuation(tmp_path, monkeypatch)
    body = json.loads(f.runtime.artifacts.read(ArtifactRef.model_validate(f.implementation["artifact_ref"])))
    body["implementation"]["files"][0]["content"] += "\n# different implementation"
    (f.workspace / "scratch/experiment.json").write_bytes(canonical_json(body["implementation"]))
    changed = f.worker.call_tool("worker_experiment_prepare", {})["implementation"]
    with pytest.raises(DiagnosticError) as mismatch:
        f.worker.call_tool("worker_experiment_debug", {"implementation":changed, "name":"diagnostic", "mode":"preflight"})
    assert mismatch.value.details[0]["code"] == "tcad_debug_implementation_mismatch"
    ledger = next((tmp_path / "debug/budgets").glob("*.json"))
    value = json.loads(ledger.read_bytes())
    value["runs"]["active_old"] = {k:v for k,v in value["runs"]["diagnostic"].items() if k != "response"}
    value["runs"]["active_old"]["state"] = "running"
    value["reservations"]["active_old"] = value["reservations"]["diagnostic"]
    ledger.write_bytes(canonical_json(value))
    with pytest.raises(DiagnosticError) as owner:
        f.worker.call_tool("worker_experiment_debug", {"implementation":f.alias, "name":"active_old", "mode":"preflight"})
    assert owner.value.details[0]["code"] == "tcad_debug_owner_mismatch"
    assert json.loads(ledger.read_bytes())["runs"]["active_old"]["run_id"] == f.old_id


def test_material_resolution_rejects_foreign_instance_and_receipt_mutation(tmp_path, monkeypatch):
    from dataclasses import replace
    f = continuation(tmp_path, monkeypatch)
    value = f.runs.status(f.run_id)
    with pytest.raises(DiagnosticError) as foreign:
        f.runs.sealed_material_record(replace(value, instance_id="ins_foreign"), f.alias)
    assert foreign.value.details[0]["code"] == "material_origin_mismatch"
    original = f.runs.tool_evidence
    def altered(run_id):
        return [{**r, "size_bytes":r["size_bytes"]+1} if r["artifact_ref"] == f.implementation["artifact_ref"] else r for r in original(run_id)]
    monkeypatch.setattr(f.runs, "tool_evidence", altered)
    with pytest.raises(DiagnosticError) as receipt:
        f.runs.sealed_material_record(value, f.alias)
    assert receipt.value.details[0]["code"] == "material_receipt_mismatch"


def test_control_manifest_is_not_misclassified_as_a_material(tmp_path, monkeypatch):
    from dataclasses import replace
    f = continuation(tmp_path, monkeypatch)
    original = f.runs.status(f.old_id)
    manifest = next(ref for ref in f.runtime.artifacts.catalog(original.output_ref).parent_refs
                    if ref.schema_id == "scidiscovery.tool-evidence-manifest.v1")
    value = f.runs.status(f.run_id)
    bound = replace(value.inputs[0], source_name="control_manifest", artifact_ref=manifest)
    assert f.runs.sealed_material_record(replace(value, inputs=(*value.inputs, bound)), "control_manifest") is None


def test_failed_producer_receipt_survives_recovery_and_a_third_task(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.service.worker_connections import WorkerConnections
    f = continuation(tmp_path, monkeypatch)
    debug = f.worker.call_tool("worker_experiment_debug", {"implementation":f.alias, "name":"diagnostic", "mode":"preflight"})
    original_record = next(r for r in f.runs.tool_evidence(f.run_id) if r["alias"] == debug["reference"])
    value = f.runs.status(f.run_id)
    f.runs.record_failure(f.run_id, reason="fixture interruption", expected_state="running",
                          expected_last_activity_at=value.last_activity_at)
    recovered = f.root.call_tool("operation_invoke", {**f.invocation, "name":"recovered", "draft_from":"continuation"})
    assert recovered["result"]["state"] == "queued", recovered
    recovered_id = f.runtime.scheduler_bindings.resolve(instance=f.instance.instance_id, namespace="run", name="recovered")
    WorkerConnections(f.runs).attach(run_id=recovered_id, platform_session="recovery-fixture", thread_id="recovered")
    compiled = f.catalog.operation("science.experiment.v1")
    services = bind_experiment_services(f.runs, compiled, dict(f.coordinator.worker_services), coordinator=f.coordinator)
    worker = LocalWorkerMCPRouter(f.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest, tool_services=services)
    opened = worker.call_tool("worker_open_assignment", {})
    assert next(r for r in f.runs.tool_evidence(recovered_id) if r["alias"] == debug["reference"]) == original_record
    f.worker, f.workspace = worker, Path(opened["workspace_path"])
    result = submit(f, [debug["reference"]], outcome="blocked")
    assert result["state"] == "completed", result
    name = next(b.name for b in f.runtime.scheduler_bindings.list(instance=f.instance.instance_id, namespace="artifact")
                if b.object_id == original_record["artifact_ref"]["artifact_id"])
    third = f.root.call_tool("operation_invoke", {"name":"third", "operation_id":"science.experiment.v1",
        "inputs":[{"port":"research_objective", "artifact_names":["objective"]},
                  {"port":"scientific_materials", "artifact_names":[name]}], "instruction":"Retain the exact recovered diagnostic."})
    assert third["result"]["state"] == "queued", third
    third_id = f.runtime.scheduler_bindings.resolve(instance=f.instance.instance_id, namespace="run", name="third")
    WorkerConnections(f.runs).attach(run_id=third_id, platform_session="third-fixture", thread_id="third")
    worker = LocalWorkerMCPRouter(f.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest, tool_services=services)
    opened = worker.call_tool("worker_open_assignment", {})
    third_run = f.runs.status(third_id)
    alias = next(i.source_name for i in third_run.inputs if i.artifact_ref == ArtifactRef.model_validate(original_record["artifact_ref"]))
    preserved = f.runs.sealed_material_record(third_run, alias)
    assert preserved["producer_run_id"] == f.run_id and f.runs.status(f.run_id).state == "failed"
    f.worker, f.workspace = worker, Path(opened["workspace_path"])
    result = submit(f, [alias], outcome="blocked")
    assert result["state"] == "completed", result
