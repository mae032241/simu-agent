"""Bounded source regressions for the complete experiment's compiled entry."""
from scidiscovery.operations.catalog import compile_catalog


def test_complete_experiment_compiles_with_one_domain_provider(monkeypatch):
    import scidiscovery.operations.catalog as compiler
    original = compiler._build_compiled_catalog
    def assert_reachable(*args):
        unused = [key for key, value in args[1].items() if key not in args[-1] and not value.spec.public]
        assert not unused, "Unreferenced declarations: " + ", ".join(unused)
        return original(*args)
    monkeypatch.setattr(compiler, "_build_compiled_catalog", assert_reachable)
    from scidiscovery.builtin_plugin import CORE_PLUGIN as builtin
    from scidiscovery.general_science_plugin import PLUGIN as science
    from tcad_artifact.plugin import PLUGIN as tcad
    from curve_score.plugin import PLUGIN as curve
    catalog = compile_catalog((builtin, science, curve, tcad))
    experiment = catalog.operation("science.experiment.v1")
    assert experiment.spec.executor.capability.plugin_id == "tcad_artifact"
    assert {tool.name for tool in experiment.worker_tools} >= {
        "worker_experiment_stage", "worker_experiment_prepare", "worker_experiment_execute"}
    assert experiment.spec.review is None
    assert {port.name for port in experiment.spec.inputs} == {
        "research_objective", "scientific_materials", "prior_experiment", "scientific_files", "user_context"}


def test_completed_experiment_requires_linked_control_observations():
    import json
    import pytest
    from scidiscovery.general_science_experiment_task import validate_completion
    from scidiscovery.operations.input_validation import ValidationSources
    from scidiscovery.operation_contract import SemanticRuleViolation
    payload = dict(summary="Result", outcome="completed", limitations=[], remaining_question="", adopted_stages=[])
    def sources(records):
        return ValidationSources({}, {}, tool_snapshot=json.dumps({"records": records}).encode())
    with pytest.raises(SemanticRuleViolation, match="collected execution"):
        validate_completion(payload, sources([]), {})
    records = [
        {"alias": "implementation", "metadata": {"kind": "experiment_implementation"}},
        {"alias": "execution", "metadata": {"kind": "experiment_execution", "implementation": "implementation"}},
        {"alias": "validity", "metadata": {"kind": "experiment_stage", "stage": "validity", "derived_from": ["execution"]}},
    ]
    payload["adopted_stages"] = [r["alias"] for r in records]
    validate_completion(payload, sources(records), {})
    records[1]["metadata"]["implementation"] = "different_implementation"
    with pytest.raises(SemanticRuleViolation):
        validate_completion(payload, sources(records), {})
    payload.update(outcome="blocked", adopted_stages=[])
    validate_completion(payload, sources([]), {})


def test_scientific_projection_preserves_private_control_snapshot():
    import json
    from scidiscovery.artifact_agent.service.tool_evidence import scientific_evidence_projection
    raw = json.dumps({"bindings": {"subject": {"artifact_ref": "private-id"}},
        "records": [{"alias": "material", "artifact_ref": "private-id", "source_ref": "private-source",
            "media_type": "application/json", "size_bytes": 5,
            "metadata": {"kind": "experiment_stage", "stage": "design", "derived_from": ["subject"]}}]}).encode()
    visible = scientific_evidence_projection(raw)
    assert b"private" not in visible and b"artifact_ref" not in visible and b"bindings" not in visible
    assert json.loads(visible)["materials"][0]["reference"] == "material"
    assert json.loads(raw)["records"][0]["artifact_ref"] == "private-id"


def _real_experiment(tmp_path, monkeypatch, solver="sprocess", before_submit=None):
    import hashlib
    import json
    from pathlib import Path
    from types import SimpleNamespace
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN as science
    from tcad_artifact.plugin import PLUGIN as tcad
    from curve_score.plugin import PLUGIN as curve
    from scidiscovery.artifact_agent import runtime as runtime_module
    from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    from scidiscovery.artifact_agent.schema.common import canonical_json
    from scidiscovery.artifact_agent.schema.execution import LocalFileDescriptor
    from scidiscovery.artifact_agent.execution_bridge import ExecutionBridge, AdapterCapability
    from scidiscovery.artifact_agent.service.experiment_execution import ExperimentExecution, bind_experiment_services
    from tests.operations.tcad_policy_fixtures import policy_snapshot
    catalog = compile_catalog((CORE_PLUGIN, science, curve, tcad))
    monkeypatch.setattr(runtime_module, "compile_installed_catalog", lambda: catalog)
    project = tmp_path / "project"
    project.mkdir()
    runtime = runtime_module.open_runtime(project_root=project, state_root=tmp_path / "state",
        approval_receipt_secret=b"a"*32)
    instance = runtime.scheduler_bindings.create_instance(name="experiment", title="Bounded experiment", objective="Observe a fixture.")
    objective = runtime.artifacts.register(canonical_json({"objective_key":"objective", "intent":"engineering",
        "statement":"Observe a fixture.", "closure_requirements":[{"requirement_key":"observation",
        "description":"Retain one observation.", "requirement_type":"comparison_present",
        "comparison_purposes":["exploratory_diagnostic"]}]}), ArtifactRegistration(kind="objective",
        schema_id="scidiscovery.research-objective.v1", payload_schema_version=1,
        media_type="application/json", creator=runtime.actor), idempotency_key="objective")
    runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace="artifact", name="objective", object_id=objective.artifact_id)
    root = RootMCPRouter(RootToolFacade(runtime.artifacts, runtime.intake, runs=runtime.runs,
        approvals=runtime.approvals, executions=runtime.executions, bindings=runtime.scheduler_bindings,
        instance=instance.instance_id, operation_catalog=catalog))
    inputs = [{"port":"research_objective", "artifact_names":["objective"]}]
    if solver == "sdevice":
        grid = runtime.artifacts.register(b"exact-grid", ArtifactRegistration(kind="grid", schema_id="opaque",
            payload_schema_version=1, media_type="application/octet-stream", creator=runtime.actor), idempotency_key="grid")
        runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace="artifact", name="grid", object_id=grid.artifact_id)
        inputs.append({"port":"scientific_files", "artifact_names":["grid"]})
    created = root.call_tool("operation_invoke", {"name":"observe", "operation_id":"science.experiment.v1",
        "inputs":inputs, "instruction":"Observe the fixture."})
    assert created["result"]["state"] == "queued", created
    assert "operation_digest" not in json.dumps(created)
    capability = canonical_json(dict(profile_id=solver, solver_kind=solver, launch_name=solver,
        public_release_label="Fixture", private_fixed_argument_count=0, private_fixed_arguments_sha256="a"*64,
        private_release_evidence_bytes=1, private_release_evidence_sha256="b"*64, capability_sha256="c"*64))
    class Adapter:
        submits = 0
        state = "running"
        wall_seconds = 1
        def lookup_submission(self, submission):
            return ("external_fixture", self.state) if self.submits else None
        def capabilities(self):
            return (AdapterCapability(solver, "solver", "tcad.solver-capability.v2", 2,
                "application/json", capability, {"solver_kind":solver}),)
        def execution_admission(self, payload, **kwargs):
            return policy_snapshot().admission(budget={"max_storage_bytes":1024, "wall_time_seconds":self.wall_seconds}, budget_key="d"*64)
        def prepare(self, payload, **kwargs): return payload
        def submit(self, submission, **kwargs):
            self.submits += 1
            return "external_fixture", self.state
        def status(self, external): return self.state
    adapter = Adapter()
    bridge = ExecutionBridge(runtime.executions, adapters={"tcad_artifact:tcad":adapter})
    def collect(execution_id, **kwargs):
        output = tmp_path / "observation.txt"
        output.write_bytes(b"observed fixture\n")
        descriptor = LocalFileDescriptor(name="observation", local_path=str(output), media_type="text/plain",
            size_bytes=output.stat().st_size, sha256=hashlib.sha256(output.read_bytes()).hexdigest())
        runtime.executions.ingest_result(execution_id=execution_id, external_run_id="external_fixture",
            outputs=(descriptor, descriptor.model_copy(update={"name":"binary", "media_type":"application/octet-stream"}),
                descriptor.model_copy(update={"name":"tcad_manifest"})))
    coordinator = runtime.runs.experiment_executions = ExperimentExecution(runs=runtime.runs, executions=runtime.executions, bridge=bridge,
        collection=SimpleNamespace(collect=collect), approval_base_url=None)
    compiled = catalog.operation("science.experiment.v1")
    from tcad_artifact.local_debug_service import LocalTCADDebugService
    from tcad_artifact.debug_contract import PreparedTCADDebugRun, CollectedTCADDebugRun, CollectedTCADDebugFile
    class DebugAdapter:
        policy = policy_snapshot().debug
        submits = 0
        def prepare(self, **kwargs):
            path = tmp_path / "debug-submission.json"
            path.write_bytes(kwargs["project"])
            return PreparedTCADDebugRun(LocalFileDescriptor(name="diagnostic", local_path=str(path),
                media_type="application/json", size_bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest()), 1)
        def clamp_wall_time(self, prepared, **kwargs): return prepared
        def prepare_submission(self, prepared): return prepared.submission
        def lookup_submission(self, descriptor): return ("diagnostic", "succeeded") if self.submits else None
        def submit(self, submission):
            self.submits += 1
            return "diagnostic", "succeeded"
        def collect_with_budget(self, external, **kwargs):
            return CollectedTCADDebugRun("succeeded", 0, "complete", "Diagnostic finished.", "finished\n",
                (CollectedTCADDebugFile("debug.log.txt", "text/plain", b"finished\n"),))
        def cancel(self, external): raise AssertionError("Collected diagnostics must never be cancelled.")
    debugger = DebugAdapter()
    debug_service = LocalTCADDebugService(adapter=debugger, exchange_root=tmp_path / "debug")
    services = bind_experiment_services(runtime.runs, compiled, {"tcad_artifact:tcad.development_debug":debug_service}, coordinator=coordinator)
    worker = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest, tool_services=services)
    from scidiscovery.artifact_agent.service.worker_connections import WorkerConnections
    connections = WorkerConnections(runtime.runs)
    author_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace="run", name="observe")
    connections.attach(run_id=author_id, platform_session="session", thread_id="author")
    opened = worker.call_tool("worker_open_assignment", {})
    workspace = Path(opened["workspace_path"])
    assignment = json.loads(Path(opened["assignment_path"]).read_bytes())
    assert "digest" not in assignment["operation"]
    assert "prior_source_bindings" not in assignment
    design = worker.call_tool("worker_experiment_stage", {"stage":"design", "conclusion":"Observe one fixture."})
    document = dict(solver_kind=solver, files=[{"relative_path":"main.cmd", "content":"# fixture"}],
        entrypoint="main.cmd", resource_limits=dict(wall_time_seconds=1, cpu_time_seconds=1,
        max_memory_bytes=1024, max_output_bytes=1024, max_storage_bytes=1024))
    files = {}
    if solver == "sdevice":
        document["input_slots"] = [{"semantic_name":"device_grid", "target_relative_path":"device.tdr", "media_type":"application/octet-stream"}]
        files = {"device_grid":next(item["source_name"] for item in assignment["inputs"] if item["media_type"] == "application/octet-stream")}
    (workspace / "scratch/experiment.json").write_bytes(canonical_json(document))
    import pytest
    from scidiscovery.operation_contract import DiagnosticError
    from scidiscovery.artifact_agent.interfaces.mcp import rpc_error
    (workspace / "scratch/experiment.json").write_bytes(canonical_json({**document,"entrypoint":""}))
    with pytest.raises(DiagnosticError) as rejected:
        worker.call_tool("worker_experiment_prepare", {"scientific_files":files})
    diagnostic = rpc_error(1, rejected.value)
    assert diagnostic["error"]["data"]["diagnostics"][0]["path"] == "$.entrypoint"
    assert str(workspace) not in json.dumps(diagnostic) and "artifact_ref" not in json.dumps(diagnostic)
    (workspace / "scratch/experiment.json").write_bytes(canonical_json(document))
    prepared = worker.call_tool("worker_experiment_prepare", {"scientific_files":files})
    request = {"name":"diagnostic", "implementation":prepared["implementation"], "mode":"preflight"}
    first_debug = worker.call_tool("worker_experiment_debug", request)
    assert first_debug["state"] == "succeeded"
    assert worker.call_tool("worker_experiment_debug", request) == first_debug
    # Reopen with a fresh tool host/service: only the original sealed implementation
    # and persistent receipt are available; there is no legacy author result file.
    debug_service = LocalTCADDebugService(adapter=debugger, exchange_root=tmp_path / "debug")
    services["tcad_artifact:tcad.development_debug"] = debug_service
    worker = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest, tool_services=services, run_id=author_id)
    worker.call_tool("worker_open_assignment", {})
    assert worker.call_tool("worker_experiment_debug", request) == first_debug
    assert worker.call_tool("worker_experiment_debug", {"action":"cancel", "name":"diagnostic"})["state"] == "inactive"
    assert debugger.submits == 1
    ledger = next((tmp_path / "debug/budgets").glob("*.json"))
    assert json.loads(ledger.read_bytes())["reserved_wall_seconds"] == 1
    started = worker.call_tool("worker_experiment_execute", {"action":"start", "implementation":prepared["implementation"]})
    assert started["state"] == "running"
    (workspace / "output/result.json").write_bytes(canonical_json({"schema_version":1,
        "payload":dict(summary="Pending.", outcome="blocked", remaining_question="Await execution.")}))
    assert worker.call_tool("worker_submit_result", {})["state"] == "rejected"
    adapter.state = "succeeded"
    worker.call_tool("worker_experiment_execute", {"action":"advance"})
    assert adapter.submits == 1
    collected = worker.call_tool("worker_experiment_execute", {"action":"collect"})
    assert collected["terminal_state"] == "succeeded"
    before = len(runtime.runs.tool_evidence(worker._run_id))
    status = worker.call_tool("worker_experiment_execute", {"action":"status"})
    assert "reference" not in status and len(runtime.runs.tool_evidence(worker._run_id)) == before
    assert worker.call_tool("worker_experiment_execute", {"action":"read", "output_name":"observation"})["text"] == "observed fixture\n"
    exported = worker.call_tool("worker_experiment_execute", {"action":"export", "output_name":"binary"})
    assert (workspace / exported["path"]).read_bytes() == b"observed fixture\n"
    assert "tcad_manifest" not in json.dumps(collected)
    import pytest
    from scidiscovery.artifact_agent.interfaces.mcp_worker_protocol import WorkerToolError
    with pytest.raises(WorkerToolError):
        worker.call_tool("worker_experiment_execute", {"action":"export", "output_name":"tcad_manifest"})
    adapter.wall_seconds = 4000
    with pytest.raises(WorkerToolError):
        worker.call_tool("worker_experiment_execute", {"action":"start", "name":"over_allowance", "implementation":prepared["implementation"]})
    assert adapter.submits == 1
    assert worker.call_tool("worker_experiment_execute", {"action":"cancel", "name":"over_allowance"})["state"] == "abandoned"
    adapter.wall_seconds = 1
    validity = worker.call_tool("worker_experiment_stage", {"stage":"validity", "conclusion":"The fixture observation is present.", "materials":[collected["reference"]]})
    additional_stages = before_submit(runtime, root, worker, instance, workspace, catalog, collected) if before_submit else []
    (workspace / "output/result.json").write_bytes(canonical_json({"schema_version":1,
        "payload":dict(summary="Observed fixture.", outcome="completed", remaining_question="",
            adopted_stages=[design["reference"], prepared["implementation"], collected["reference"], validity["reference"], *additional_stages])}))
    completed = worker.call_tool("worker_submit_result", {})
    assert completed["state"] == "completed", completed
    visible = json.dumps([assignment, prepared, started, collected, status])
    assert "artifact_ref" not in visible and "external_fixture" not in visible and "policy_digest" not in visible
    private_package = coordinator.implementation(SimpleNamespace(run_id=worker._run_id), prepared["implementation"])
    assert objective.ref in runtime.artifacts.verify(private_package).parent_refs
    assert json.loads(runtime.artifacts.read(private_package))["review"] is None
    if solver == "sdevice":
        package = json.loads(runtime.artifacts.read(private_package))
        assert package["resolved_inputs"][0]["artifact_ref"] == grid.ref.model_dump(mode="json")
        assert grid.ref in runtime.artifacts.verify(private_package).parent_refs
    formal = next(item.object_id for item in runtime.scheduler_bindings.list(instance=instance.instance_id, namespace="execution")
        if runtime.executions.status(item.object_id).state == "collected")
    assert runtime.executions.budget_owner(formal) == runtime.executions.scientific_budget_owner(private_package, ("scidiscovery.research-objective.v1",))
    detail = root.call_tool("run_status", {"name":"observe", "view":"detail", "response_profile":"compat", "include_full_output":True})
    assert "artifact_ref" not in json.dumps(detail) and "operation_digest" not in json.dumps(detail)
    schema = (workspace / "schema/result.schema.json").read_text()
    assert "recovery_manifest_output" not in schema and "tool_recovery_manifest" not in schema
    from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter, _Context
    gateway = UnifiedMCPRouter(root)
    profile = runtime.runs.status(author_id).execution_profile["profile"]
    context = _Context("session", "author", True, profile["model"], profile["reasoning_effort"])
    first, _ = gateway._worker(context)
    assert gateway._worker(context)[0] is first
    return runtime, root, catalog, connections, instance


def test_reviewer_and_scientific_surfaces_use_declared_contract(tmp_path, monkeypatch):
    import json
    import pytest
    from pathlib import Path
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from scidiscovery.artifact_agent.interfaces.mcp import rpc_error
    from scidiscovery.artifact_agent.service.runs import RunStateConflict
    from scidiscovery.artifact_agent.interfaces.mcp_worker_protocol import WorkerToolError
    runtime, root, catalog, connections, instance = _real_experiment(tmp_path, monkeypatch, solver="sdevice")
    full = root.call_tool("operation_catalog", {"scope":"public", "view":"detail", "operation_id":"science.experiment.v1"})
    text = json.dumps(full)
    assert "recovery_manifest_output" not in text and "tcad_artifact" not in text and "operation_digest" not in text
    assert root.call_tool("operation_catalog", {"scope":"public", "view":"index", "limit":100})["complete"]
    for view in ("detail", "parents", "producer_inputs"):
        materials = root.call_tool("artifact_catalog", {"name":"observe.output", "view":view})
        visible = json.dumps(materials)
        assert "artifact_ref" not in visible and "operation_digest" not in visible and "port_name" not in visible
        assert "objective" in visible
    listing = root.call_tool("run_list", {"view":"detail", "limit":10})
    assert "recovery" not in next(item for item in listing["runs"] if item["name"] == "observe")
    executions = runtime.scheduler_bindings.list(instance=instance.instance_id, namespace="execution")
    assert executions
    assert root.call_tool("execution_list", {"limit":10})["executions"] == []
    events = root.call_tool("lifecycle_events", {})["events"]
    assert not any(item["object_type"] == "execution" for item in events)
    from scidiscovery.artifact_agent.interfaces.mcp_root_shared import RootToolError
    for execution in executions:
        with pytest.raises(RootToolError, match="managed within its scientific task"):
            root.call_tool("execution_status", {"name":execution.name})
        assert execution.name not in json.dumps(events)
    created = root.call_tool("operation_invoke", {"name":"review", "operation_id":"science.object.review.v1",
        "inputs":[{"port":"subject", "artifact_names":["observe.output"]}], "instruction":"Review the observation."})
    assert created["result"]["state"] == "queued", created
    review_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace="run", name="review")
    compiled = catalog.operation("science.object.review.v1")
    worker = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    with pytest.raises(WorkerToolError) as caught:
        worker.call_tool("worker_open_assignment", {})
    error = json.dumps(rpc_error(1, caught.value))
    assert review_id not in error and compiled.digest not in error and "reference" not in error
    with pytest.raises(RunStateConflict, match="different Agent"):
        connections.attach(run_id=review_id, platform_session="session", thread_id="author")
    connections.attach(run_id=review_id, platform_session="session", thread_id="reviewer")
    # Attachment existence is insufficient for a standalone caller.
    with pytest.raises(WorkerToolError):
        worker.call_tool("worker_open_assignment", {})
    wrong = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest, run_id=review_id, trusted_caller=("session","author"))
    with pytest.raises(WorkerToolError):
        wrong.call_tool("worker_open_assignment", {})
    from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter, _Context
    profile = runtime.runs.status(review_id).execution_profile["profile"]
    gateway = UnifiedMCPRouter(root)
    worker, _ = gateway._worker(_Context("session", "reviewer", True, profile["model"], profile["reasoning_effort"]))
    opened = worker.call_tool("worker_open_assignment", {})
    Path(opened["output_directory"], "result.json").write_text(json.dumps({"schema_version":1,
        "payload":{"verdict":"pass", "summary":"The requested observation is supported."}}))
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    view = root.call_tool("operation_catalog", {"scope":"public", "view":"detail", "operation_id":"science.object.review.v1"})
    assert "recovery_manifest_output" not in json.dumps(view)
    reviewed = runtime.runs.status(review_id)
    assert runtime.runs.evidence_output_refs(reviewed) == []


def test_debug_recovery_cancellation_preserves_original_budget(tmp_path):
    import json
    from types import SimpleNamespace
    from tcad_artifact.local_debug_service import LocalTCADDebugService
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    from scidiscovery.artifact_agent.schema.common import canonical_sha256
    subject = ArtifactRef(artifact_id="objective", sha256="a"*64, kind="objective", schema_id="scidiscovery.research-objective.v1")
    calls = []
    adapter = SimpleNamespace(lookup_submission=lambda descriptor: ("external_debug", "running"),
        cancel=lambda external: calls.append(external) or "cancelled")
    service = LocalTCADDebugService(adapter=adapter, exchange_root=tmp_path)
    directory = tmp_path / "budgets"
    directory.mkdir()
    path = directory / (canonical_sha256({"subject":subject}) + ".json")
    record = {"run_id":"original_run", "state":"accepted", "external_run_id":None}
    ledger = {"reserved_wall_seconds":30, "runs":{}, "reservations":{"debug":{
        "record":record, "submission":{"schema_version":1, "name":"submitted", "local_path":"/private/submission",
        "sha256":"b"*64, "size_bytes":1, "media_type":"application/json"}}}}
    path.write_text(json.dumps(ledger))
    inputs = (SimpleNamespace(port_name="research_objective", artifact_ref=subject),)
    assert not service.experiment_activity({"unrelated_run"}, inputs, cancel=True)
    assert calls == []
    assert service.experiment_activity({"original_run", "recovered_run"}, inputs)
    assert json.loads(path.read_text()) == ledger
    assert not service.experiment_activity({"original_run", "recovered_run"}, inputs, cancel=True)
    after = json.loads(path.read_text())
    assert after["reserved_wall_seconds"] == 30 and after["reservations"] == ledger["reservations"]
    assert calls == ["external_debug"]
    assert not service.experiment_activity({"original_run", "recovered_run"}, inputs, cancel=True)
    assert calls == ["external_debug"]


def test_real_worker_seals_and_executes_without_legacy_gates(tmp_path, monkeypatch):
    _real_experiment(tmp_path, monkeypatch)


def test_scientific_implementation_and_package_share_constraints():
    import json
    import pytest
    from pydantic import ValidationError
    from tcad_artifact.experiment_capability import Implementation
    from tcad_artifact.project_packager import DeckProjectDraft
    public = Implementation.model_json_schema()
    private = DeckProjectDraft.model_json_schema()
    for name in ("entrypoint", "files", "arguments", "input_slots", "expected_outputs", "resource_limits"):
        assert public["properties"][name] == private["properties"][name]
    assert not {"tool_profile", "capability_sha256", "schema_version"}.intersection(public["properties"])
    source = dict(solver_kind="sdevice", files=[{"relative_path":"main.cmd","content":"# standalone"}],
        entrypoint="main.cmd", resource_limits=dict(wall_time_seconds=1,cpu_time_seconds=1,
        max_memory_bytes=1024,max_output_bytes=1024,max_storage_bytes=1024))
    for change in ({"entrypoint":""}, {"entrypoint":"absent.cmd"},
        {"entrypoint":"main.txt","files":[{"relative_path":"main.txt","content":"# invalid direct entrypoint"}]},
        {"arguments":["x"]*257},
        {"input_slots":[{"semantic_name":"grid","target_relative_path":"grid.tdr","media_type":"application/octet-stream"}]*4097},
        {"expected_outputs":[{"name":"observation","relative_path":"out.txt","media_type":"text/plain","max_bytes":1}]*4097}):
        value = {**source,**change}
        for model, extra in ((Implementation,{}),(DeckProjectDraft,{"tool_profile":"configured", "capability_sha256":"a"*64})):
            with pytest.raises(ValidationError):
                model.model_validate_json(json.dumps({**value,**extra}),strict=True)


def test_execution_package_version_is_declared_and_enters_identity(monkeypatch):
    from dataclasses import replace
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN as science
    from tcad_artifact.plugin import PLUGIN as tcad
    from curve_score.plugin import PLUGIN as curve
    import tcad_artifact.experiment_capability as provider
    declared = provider.CAPABILITY
    assert declared.execution_package_schema_version == 2
    digests = []
    for version in (1, 2, 3):
        monkeypatch.setattr(provider, 'CAPABILITY', replace(declared, execution_package_schema_version=version))
        catalog = compile_catalog((CORE_PLUGIN, science, curve, tcad))
        operation = catalog.operation('science.experiment.v1')
        digests.append(operation.digest)
        capability = operation.implementations['tcad_artifact:experiment_capability']
        assert capability.execution_package_schema_version == version
    assert len(set(digests)) == 3


def test_execution_package_sealing_preserves_declared_payload_version(monkeypatch):
    from types import SimpleNamespace
    import scidiscovery.artifact_agent.service.experiment_execution as execution
    from scidiscovery.artifact_agent.schema.refs import ActorRef
    registrations = []
    def register(payload, registration, **kwargs):
        registrations.append(registration)
        return SimpleNamespace(ref='private-package')
    effect = SimpleNamespace(spec=SimpleNamespace(inputs=(SimpleNamespace(name='package', schema_id='plugin.package'),)))
    run = SimpleNamespace(run_id='run_fixture')
    service = execution.ExperimentExecution(runs=None, executions=SimpleNamespace(
        artifacts=SimpleNamespace(register=register), service_actor=ActorRef(actor_id='service', actor_type='service')),
        bridge=None, collection=None, approval_base_url=None)
    monkeypatch.setattr(execution, 'effect_operation_plan', lambda _: SimpleNamespace(payload_port='package'))
    monkeypatch.setattr(service, 'task_origin', lambda _: 'run_fixture')
    context = SimpleNamespace(accept_evidence=lambda **kwargs: kwargs)
    for version in (1, 2, 3):
        monkeypatch.setattr(service, '_contract', lambda _, version=version: (
            run, effect, None, SimpleNamespace(execution_package_schema_version=version)))
        service.seal_implementation(context, payload=b'{}', scientific_material=b'{}', sources=())
    assert [record.payload_schema_version for record in registrations] == [1, 2, 3]
    assert all(record.schema_id == 'plugin.package' for record in registrations)
