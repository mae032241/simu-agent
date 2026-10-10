"""Cross-task handoff through real Root/Worker routes, with bounded fake adapters."""
import json
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.operations.test_r4_experiment_task import _real_experiment
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.service.experiment_execution import bind_experiment_services
from scidiscovery.operation_contract import DiagnosticError
from scidiscovery.artifact_agent.interfaces.mcp_root import RootToolError
from tcad_artifact.local_debug_service import _record_key


def continuation(tmp_path, monkeypatch, solver="sprocess", *, all_stages=False, include_grid=True, require_execution_review=False, presentation=False, goal="research-objective", managed_loop=False):
    runtime, root, catalog, connections, instance = _real_experiment(tmp_path, monkeypatch, solver, goal=goal)
    runs = runtime.runs
    if presentation:
        runs.agent_settings = runs.agent_settings.model_copy(update={
            "presentation": runs.agent_settings.presentation.model_copy(update={"enabled": True})})
    old_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace="run", name="observe")
    records = runs.tool_evidence(old_id)
    implementation = next(r for r in records if r["metadata"].get("kind") == "experiment_implementation")
    chosen = records if all_stages else [implementation]
    bindings = runtime.scheduler_bindings.list(instance=instance.instance_id, namespace="artifact")
    names = [next(b.name for b in bindings if b.object_id == r["artifact_ref"]["artifact_id"]) for r in chosen]
    if solver == "sdevice" and include_grid:
        names.append("grid")  # A different port produces a different alias from the author's.
    invocation = {"name":"continuation", "operation_id":"science.experiment.v1",
        "inputs":[{"port":"subject", "artifact_names":["observe.output"]},
                  {"port":"prior_experiment", "artifact_names":["observe.output"]},
                  {"port":"scientific_materials", "artifact_names":names}], "instruction":"Reuse exact sealed materials."}
    if require_execution_review:
        invocation["require_execution_review"] = True
    if managed_loop:
        from tests.operations.research_loop_fixtures import authorize_loop
        settings = runtime.scheduler_bindings.global_settings
        runtime.scheduler_bindings.global_settings = settings.model_copy(update=dict(
            progression=settings.progression.model_copy(update=dict(max_tasks=1))))
        user = 'sch_' + 'a' * 32
        runtime.scheduler_bindings.bind_session(session_key=user, instance_id=instance.instance_id)
        root.facade.session_key = user
        root.call_tool('progression_command', {'command':'pause'})
        authorize_loop(runtime, instance.instance_id, user, 'objective')
        root.call_tool('progression_command', {'command':'start', 'objective_name':'objective'})
    result = root.call_tool("operation_invoke", invocation)
    assert result["result"]["state"] == "queued", result
    run_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace="run", name="continuation")
    connections.attach(run_id=run_id, platform_session="continuation-fixture", thread_id="next-owner")
    compiled = catalog.operation("science.experiment.v1")
    coordinator = runs.experiment_executions
    services = bind_experiment_services(runs, compiled, dict(coordinator.worker_services), coordinator=coordinator)
    worker = LocalWorkerMCPRouter(runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest, tool_services=services)
    opened = worker.call_tool("worker_open_assignment", {})
    if managed_loop:
        from tests.operations.research_loop_fixtures import measured_fixture_usage
        measured_fixture_usage(worker)
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


def test_bound_report_exposes_named_collected_originals_without_execution_takeover(tmp_path, monkeypatch):
    f = continuation(tmp_path, monkeypatch)
    prior = next(i.source_name for i in f.runs.status(f.run_id).inputs if i.port_name == "prior_experiment")
    directory = f.worker.call_tool("worker_reference_read", {"source": prior})
    original = next(r for r in f.records if r["metadata"].get("kind") == "experiment_execution")
    entry = next(item for item in directory["references"] if item["alias"] == original["alias"])
    stage = f.worker.call_tool("worker_reference_read", {"source": prior, "action": "read", "reference": entry["reference"]})
    files = f.worker.call_tool("worker_reference_read", {"source": stage["source"]})
    names = {item["file_name"] for item in files["references"]}
    assert names == {"case-A/profile_480s.txt", "case-A/final.tdr"}
    assert "tcad_manifest" not in json.dumps(files) and "artifact_id" not in json.dumps(files)
    entry = next(item for item in files["references"] if item["alias"] == "binary")
    delivered = f.worker.call_tool("worker_reference_read", {"source": stage["source"], "action": "read",
        "reference": entry["reference"], "delivery": "file"})
    assert Path(delivered["file_path"]).read_bytes() == b"observed fixture\n"
    assert not f.runtime.scheduler_bindings.list(instance=f.instance.instance_id, namespace="execution",
        name_prefix="experiment-" + f.run_id + "-")


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
    # The attached active owner reads the frozen producer original, not a Root
    # projection that rewrites its source namespace into consumer aliases.
    delivered = f.worker.call_tool("worker_reference_read", {"source": f.alias, "action": "read",
        "reference": "content", "delivery": "file"})
    original_bytes = Path(delivered["file_path"]).read_bytes()
    assert original_bytes == f.runtime.artifacts.read(original_ref)
    assert hashlib.sha256(original_bytes).hexdigest() == original_ref.sha256
    original = f.runs.sealed_material_record(f.runs.status(f.run_id), f.alias)
    assert original["producer_run_id"] == f.old_id
    completed = submit(f, [f.alias, collected["reference"], validity["reference"]])
    assert completed["state"] == "completed", completed
    assert not any(r["metadata"].get("kind") == "experiment_implementation" for r in f.runs.tool_evidence(f.run_id))
    assert f.runs.sealed_material_record(f.runs.status(f.run_id), f.alias)["artifact_ref"] == original_ref.model_dump(mode="json")
    for forbidden in ({"stage_reference": f.alias}, {"intent": "full"}):
        with pytest.raises(RootToolError, match="tool arguments"):
            f.root.call_tool("run_status", {"name": "continuation", **forbidden})
    stages = f.root.call_tool("run_status", {"name": "continuation", "intent": "navigation",
        "stage_offset": 0, "stage_limit": 8})["sealed_stages"]
    stage = next(item for item in stages["items"] if item["reference"] == f.alias)
    assert stage["origin"] == "reused" and stage["adopted"] is True
    assert "artifact_ref" not in json.dumps(stage) and "text" not in stage
    if solver == "sdevice":
        original_grid = json.loads(original_bytes)["scientific_files"]["device_grid"]
        grid_ref = original["source_refs"][original_grid]
        aliases = f.runs.material_source_aliases(f.runs.status(f.run_id))
        assert aliases[grid_ref].startswith("scientific_materials")
        assert f.runs.source_descriptor(f.runs.status(f.run_id), aliases[grid_ref]).artifact_ref == grid_ref
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
    f.coordinator._cancel(new_id)
    assert executions.status(new_id).state == "abandoned"
    assert executions.status(old_execution).state == "collected"


def test_old_implementation_execution_and_validity_can_be_adopted_by_exact_ref(tmp_path, monkeypatch):
    f = continuation(tmp_path, monkeypatch, all_stages=True)
    aliases = [i.source_name for i in f.runs.status(f.run_id).inputs if i.port_name == "scientific_materials"]
    result = submit(f, aliases)
    assert result["state"] == "completed", result


@pytest.mark.parametrize("stale_diagnostic", [False, True])
def test_abandoned_requests_do_not_block_collected_experiment_delivery(tmp_path, monkeypatch, stale_diagnostic):
    f = continuation(tmp_path, monkeypatch, all_stages=True)
    executions = f.runtime.executions
    collected_id = next(b.object_id for b in f.runtime.scheduler_bindings.list(
        instance=f.instance.instance_id, namespace="execution")
        if executions.status(b.object_id).state == "collected")
    request = executions.request(collected_id)
    for name in ("old_first", "old_second"):
        execution_id = "exe_" + name
        executions.create(executor=request.executor, preparation_profile=request.preparation_profile,
            payload_ref=request.payload_ref, execution_id=execution_id,
            compiled_identity=request.compiled_identity, labels={"experiment_run":f.run_id})
        f.runtime.scheduler_bindings.bind(instance=f.instance.instance_id, namespace="execution",
            name="experiment-" + f.run_id + "-" + name, object_id=execution_id)
        executions.abandon(execution_id)
    if stale_diagnostic:
        f.worker.call_tool("worker_experiment_debug", {"implementation":f.alias, "name":"diagnostic", "mode":"preflight"})
        ledger_path = next((tmp_path / "debug/budgets").glob("*.json"))
        ledger = json.loads(ledger_path.read_bytes())
        ledger["runs"][_record_key(f.run_id, "diagnostic")]["state"] = "running"
        ledger_path.write_bytes(canonical_json(ledger))
        debugger = f.coordinator.worker_services["tcad_artifact:tcad.development_debug"].adapter
        monkeypatch.setattr(debugger, "status", lambda _: "running", raising=False)
    # Recover the interrupted owner, retaining its requests and exact input receipts.
    value = f.runs.status(f.run_id)
    f.runs.record_failure(f.run_id, reason="fixture owner interrupted", expected_state="running",
        expected_last_activity_at=value.last_activity_at)
    recovered = f.root.call_tool("operation_invoke", {**f.invocation, "name":"recovered",
        "draft_from":"continuation"})
    assert recovered["result"]["state"] == "queued", recovered
    recovered_id = f.runtime.scheduler_bindings.resolve(instance=f.instance.instance_id, namespace="run", name="recovered")
    f.runs.worker_connections.attach(run_id=recovered_id, platform_session="recovery-fixture", thread_id="recovered")
    compiled = f.catalog.operation("science.experiment.v1")
    services = bind_experiment_services(f.runs, compiled, dict(f.coordinator.worker_services), coordinator=f.coordinator)
    f.worker = LocalWorkerMCPRouter(f.runs, operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest, tool_services=services)
    f.workspace = Path(f.worker.call_tool("worker_open_assignment", {})["workspace_path"])
    aliases = [i.source_name for i in f.runs.status(f.run_id).inputs if i.port_name == "scientific_materials"]
    if stale_diagnostic:
        assert submit(f, aliases)["state"] == "rejected"  # An actually active diagnostic still blocks delivery.
        monkeypatch.setattr(debugger, "status", lambda _: "succeeded")
    result = submit(f, aliases)
    assert result["state"] == "completed", result
    assert executions.status(collected_id).state == "collected"


def test_diagnostic_reuse_never_changes_implementation_or_takes_over_active_job(tmp_path, monkeypatch):
    f = continuation(tmp_path, monkeypatch)
    ledger = next((tmp_path / "debug/budgets").glob("*.json"))
    value = json.loads(ledger.read_bytes())
    old_key = _record_key(f.old_id, "diagnostic")
    value["runs"][old_key]["state"] = "running"
    value["runs"][old_key].pop("response")
    ledger.write_bytes(canonical_json(value))
    debugger = f.coordinator.worker_services["tcad_artifact:tcad.development_debug"].adapter
    monkeypatch.setattr(debugger, "status", lambda _: pytest.fail("Unrelated diagnostic was polled"), raising=False)
    before_submits = debugger.submits
    assert f.worker.call_tool("worker_experiment_debug", {"action":"status", "name":"diagnostic"})["state"] == "not_created"
    assert f.worker.call_tool("worker_experiment_debug", {"implementation":f.alias, "name":"diagnostic", "mode":"preflight"})["state"] == "succeeded"
    after = json.loads(ledger.read_bytes())
    assert debugger.submits == before_submits + 1
    assert after["runs"][old_key] == value["runs"][old_key]
    assert after["runs"][_record_key(f.run_id, "diagnostic")]["run_id"] == f.run_id
    assert after["reserved_wall_seconds"] == value["reserved_wall_seconds"] + 1
    body = json.loads(f.runtime.artifacts.read(ArtifactRef.model_validate(f.implementation["artifact_ref"])))
    body["implementation"]["files"][0]["content"] += "\n# different implementation"
    (f.workspace / "scratch/experiment.json").write_bytes(canonical_json(body["implementation"]))
    changed = f.worker.call_tool("worker_experiment_prepare", {})["implementation"]
    with pytest.raises(DiagnosticError) as mismatch:
        f.worker.call_tool("worker_experiment_debug", {"implementation":changed, "name":"diagnostic", "mode":"preflight"})
    assert mismatch.value.details[0]["code"] == "tcad_debug_implementation_mismatch"
    assert debugger.submits == before_submits + 1
    assert json.loads(ledger.read_bytes()) == after


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
        "inputs":[{"port":"subject", "artifact_names":["objective"]},
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


def test_continuation_derives_goal_from_report_without_root_rebinding(tmp_path, monkeypatch):
    runtime, root, catalog, connections, instance = _real_experiment(tmp_path, monkeypatch)
    request = dict(name='followup', operation_id='science.experiment.v1',
        inputs=[dict(port='subject', artifact_names=['observe.output'])],
        instruction='Investigate the remaining question in this sealed result.')
    before = runtime.scheduler_bindings.list(instance=instance.instance_id, namespace='artifact')
    assert root.call_tool('operation_preflight', request)['admissible']
    assert runtime.scheduler_bindings.list(instance=instance.instance_id, namespace='artifact') == before
    root.call_tool('operation_invoke', request)
    run_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='run', name='followup')
    frozen = {item.port_name: item.artifact_ref for item in runtime.runs.status(run_id).inputs}
    original_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='run', name='observe')
    original = runtime.runs.status(original_id)
    assert frozen['subject'] == original.output_ref
    assert frozen['objective_source'] == next(item.artifact_ref for item in original.inputs if item.port_name=='objective_source')
    assert 'prior_experiment' not in frozen
