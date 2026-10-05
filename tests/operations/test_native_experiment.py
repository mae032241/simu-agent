"""Native experiment delivery through real source entry points, without a solver."""
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from scidiscovery.agent_execution_settings import AgentSettings, effective_settings
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as SCIENCE_PLUGIN
from scidiscovery.operations.catalog import compile_catalog, compile_installed_catalog
from scidiscovery.operations.spec import ComponentRef, ComponentSpec, PluginDefinition, PluginDependency
from scidiscovery.general_science_experiment_task import validate_completion
from scidiscovery.operations.input_validation import ValidationSources
from scidiscovery.operation_contract import SemanticRuleViolation


@pytest.fixture
def installed(monkeypatch):
    import scidiscovery.operations.catalog as compiler
    def set_plugins(plugins):
        class Entries(tuple):
            def select(self, **kwargs):
                assert kwargs == {"group": compiler.PLUGIN_ENTRY_POINT_GROUP}
                return self
        entries = Entries(SimpleNamespace(name=p.plugin_id, load=lambda p=p: p) for p in plugins)
        monkeypatch.setattr(compiler, "entry_points", lambda: entries)
        compile_installed_catalog.cache_clear()
    monkeypatch.delenv("SCID_AGENT_SETTINGS_FILE", raising=False)
    set_plugins((CORE_PLUGIN, SCIENCE_PLUGIN))
    yield set_plugins
    compile_installed_catalog.cache_clear()


def _start_native(tmp_path, settings=None, scientific_material=False):
    from scidiscovery.artifact_agent.runtime import open_runtime
    from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    from scidiscovery.artifact_agent.service.worker_connections import WorkerConnections
    project = tmp_path / "project"
    project.mkdir()
    runtime = open_runtime(project_root=project, state_root=tmp_path / "state", agent_settings=settings)
    catalog = runtime.operation_catalog
    compiled = catalog.operation("science.experiment.v1")
    instance = runtime.scheduler_bindings.create_instance(name="native", title="Native experiment", objective="Compute 2+2.")
    goal = {"objective_key": "sum", "intent": "engineering", "statement": "Compute 2+2.",
        "closure_requirements": [{"requirement_key": "result", "description": "Retain the computed result.",
            "requirement_type": "comparison_present", "comparison_purposes": ["exploratory_diagnostic"]}]}
    envelope = runtime.artifacts.register(json.dumps(goal).encode(), ArtifactRegistration(kind="objective",
        schema_id="scidiscovery.research-objective.v1", payload_schema_version=1,
        media_type="application/json", creator=runtime.actor), idempotency_key="goal")
    runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace="artifact", name="goal", object_id=envelope.artifact_id)
    root = RootMCPRouter(RootToolFacade(runtime.artifacts, runtime.intake, runs=runtime.runs,
        approvals=runtime.approvals, executions=runtime.executions,
        bindings=runtime.scheduler_bindings, instance=instance.instance_id, operation_catalog=catalog))
    inputs = [{"port": "subject", "artifact_names": ["goal"]}]
    if scientific_material:
        parameters = runtime.artifacts.register(b'{"offset":0}', ArtifactRegistration(kind="parameters",
            schema_id="opaque", payload_schema_version=1, media_type="application/json", creator=runtime.actor), idempotency_key="parameters")
        runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace="artifact", name="parameters", object_id=parameters.artifact_id)
        inputs.append({"port": "scientific_materials", "artifact_names": ["parameters"]})
    invoked = root.call_tool("operation_invoke", {"name": "compute", "operation_id": "science.experiment.v1",
        "inputs": inputs, "instruction": "Compute using the installed local environment."})
    assert invoked["result"]["state"] == "queued", invoked
    run_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace="run", name="compute")
    WorkerConnections(runtime.runs).attach(run_id=run_id, platform_session="fixture", thread_id="native-author")
    worker = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    opened = worker.call_tool("worker_open_assignment", {})
    assignment = json.loads(Path(opened["assignment_path"]).read_text())
    assert "worker_experiment_execute" not in assignment["tools"]
    assert "worker_experiment_execute" not in assignment["tool_contracts"]
    workspace = Path(opened["workspace_path"])
    return SimpleNamespace(runtime=runtime, worker=worker, workspace=workspace, run_id=run_id,
        root=root, compiled=compiled)


def _publish(f, name, raw, sources):
    (f.workspace / "scratch" / name).write_bytes(raw)
    reply = f.worker.call_tool("worker_publish_files", {"files": [{"path": "scratch/" + name, "purpose": name}],
        "source_aliases": sources})
    return reply["files"][0]["reference"]


@pytest.mark.parametrize("missing_environment", (False, True))
def test_no_provider_native_shell_delivery_and_environment_blocker(tmp_path, installed, missing_environment):
    f = _start_native(tmp_path)
    assert f.compiled.spec.executor.capability is None
    assert {tool.name for tool in f.compiled.worker_tools if tool.name.startswith("worker_experiment_")} == {"worker_experiment_stage"}
    code = (b"import scid_missing_environment_fixture_673891\n" if missing_environment else
        b"from pathlib import Path\nPath('result.csv').write_text('value\\n4\\n')\nprint('computed 2+2')\n")
    source = _publish(f, "compute.py", code, ["objective_source"])
    impl = f.worker.call_tool("worker_experiment_stage", {"stage": "implementation", "conclusion": "Compute the sum.", "materials": [source]})["reference"]
    # A small native command, with no dedicated observer or execution service.
    observed = subprocess.run([sys.executable, "-B", "compute.py"], cwd=f.workspace / "scratch",
        capture_output=True, timeout=5)
    log = _publish(f, "execution.log", observed.stdout + observed.stderr, [impl])
    outputs = [] if missing_environment else [_publish(f, "result.csv", (f.workspace / "scratch/result.csv").read_bytes(), [impl])]
    execution = f.worker.call_tool("worker_experiment_stage", {"stage": "execution", "conclusion": "Observed local execution.",
        "native_execution": {"implementation": impl, "state": "failed" if observed.returncode else "succeeded", "logs": [log], "results": outputs}})["reference"]
    validity = f.worker.call_tool("worker_experiment_stage", {"stage": "validity", "conclusion": "Environment unavailable." if missing_environment else "The retained sum is 4.",
        "materials": [execution]})["reference"]
    outcome = "blocked" if missing_environment else "completed"
    (f.workspace / "output/result.json").write_text(json.dumps({"schema_version": 1, "payload": {
        "summary": "Environment unavailable." if missing_environment else "Computed 4.", "outcome": outcome,
        "limitations": ["Native execution is reported by the Worker; there is no independent execution attestation."],
        "remaining_question": "Install the missing environment." if missing_environment else "",
        "adopted_stages": [impl, execution, validity]}}))
    completed = f.worker.call_tool("worker_submit_result", {})
    assert completed["state"] == "completed", completed
    records = f.runtime.runs.tool_evidence(f.run_id)
    assert not any(r["metadata"].get("kind") == "experiment_execution" for r in records)
    receipt = next(r for r in records if r["alias"] == execution)
    assert receipt["metadata"]["origin"] == "worker_native"
    assert receipt["metadata"]["execution_attestation"] == "unavailable"
    resolved = f.runtime.runs.sealed_material_record(f.runtime.runs.status(f.run_id), execution)
    assert set(resolved["source_refs"]) >= {impl, log, *outputs}
    view = f.root.call_tool("run_status", {"name": "compute", "stage_reference": execution})["sealed_stages"]["material"]
    assert view["execution_origin"] == "worker_native"
    assert view["execution_attestation"] == "unavailable"
    native = json.loads(view["text"])["native_execution"]
    assert native["implementation"] == impl and native["logs"] == [log]


@pytest.mark.parametrize("include_code", (False, True))
def test_native_implementation_can_cite_original_parameters_but_needs_published_code(tmp_path, installed, include_code):
    f = _start_native(tmp_path, scientific_material=True)
    parameter = next(i.source_name for i in f.runtime.runs.status(f.run_id).inputs if i.port_name == "scientific_materials")
    source = _publish(f, "mixed.py", b"print(4)\n", [parameter])
    implementation = f.worker.call_tool("worker_experiment_stage", {"stage": "implementation", "conclusion": "Use the exact parameters.",
        "materials": [parameter, *([source] if include_code else [])]})["reference"]
    log = _publish(f, "mixed.log", b"4\n", [implementation])
    result = _publish(f, "mixed.csv", b"sum\n4\n", [implementation])
    execution = f.worker.call_tool("worker_experiment_stage", {"stage": "execution", "conclusion": "Worker reported 4.",
        "native_execution": {"implementation": implementation, "state": "succeeded", "logs": [log], "results": [result]}})["reference"]
    validity = f.worker.call_tool("worker_experiment_stage", {"stage": "validity", "conclusion": "Assessed the reported output.", "materials": [execution]})["reference"]
    (f.workspace / "output/result.json").write_text(json.dumps({"schema_version": 1, "payload": {
        "summary": "Retained the exact parameters and reported result.", "outcome": "completed", "remaining_question": "",
        "limitations": ["Worker-reported execution without independent attestation."],
        "adopted_stages": [implementation, execution, validity]}}))
    completed = f.worker.call_tool("worker_submit_result", {})
    assert completed["state"] == ("completed" if include_code else "rejected"), completed


@pytest.mark.parametrize("retain_log", (False, True))
def test_reused_native_execution_preserves_exact_files_and_consumer_aliases(tmp_path, installed, retain_log):
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from scidiscovery.artifact_agent.service.worker_connections import WorkerConnections
    f = _start_native(tmp_path)
    code = _publish(f, "original.py", b"print(4)\n", ["objective_source"])
    impl = f.worker.call_tool("worker_experiment_stage", {"stage": "implementation", "conclusion": "Exact source.", "materials": [code]})["reference"]
    log = _publish(f, "original.log", b"4\n", [impl])
    result = _publish(f, "original.csv", b"sum\n4\n", [impl])
    execution = f.worker.call_tool("worker_experiment_stage", {"stage": "execution", "conclusion": "Worker reported 4.",
        "native_execution": {"implementation": impl, "state": "succeeded", "logs": [log], "results": [result]}})["reference"]
    validity = f.worker.call_tool("worker_experiment_stage", {"stage": "validity", "conclusion": "Assessed the reported result.", "materials": [execution]})["reference"]
    (f.workspace / "output/result.json").write_text(json.dumps({"schema_version": 1, "payload": {
        "summary": "Retained original Worker materials.", "outcome": "completed", "remaining_question": "",
        "limitations": ["Worker-reported execution without independent attestation."], "adopted_stages": [impl, execution, validity]}}))
    assert f.worker.call_tool("worker_submit_result", {})["state"] == "completed"
    old = f.runtime.runs.status(f.run_id)
    records = {r["alias"]: r for r in f.runtime.runs.available_material_records(old)}
    names = [f.runtime.runs.material_artifact_name(old, records[alias])
        for alias in (code, impl, execution, validity, result, *([log] if retain_log else []))]
    invoked = f.root.call_tool("operation_invoke", {"name": "reuse", "operation_id": "science.experiment.v1",
        "inputs": [{"port": "subject", "artifact_names": ["goal"]}, {"port": "scientific_materials", "artifact_names": names}],
        "instruction": "Assess the exact retained native materials."})
    assert invoked["result"]["state"] == "queued", invoked
    new_id = f.runtime.scheduler_bindings.resolve(instance=old.instance_id, namespace="run", name="reuse")
    WorkerConnections(f.runtime.runs).attach(run_id=new_id, platform_session="reuse", thread_id="reuse-author")
    worker = LocalWorkerMCPRouter(f.runtime.runs, operation_id=f.compiled.spec.operation_id, operation_digest=f.compiled.digest)
    opened = worker.call_tool("worker_open_assignment", {})
    new = f.runtime.runs.status(new_id)
    def alias_for(reference):
        return next(i.source_name for i in new.inputs if i.artifact_ref.model_dump(mode="json") == records[reference]["artifact_ref"])
    view = f.root.call_tool("run_status", {"name": "reuse", "stage_reference": alias_for(execution)})["sealed_stages"]["material"]
    native = json.loads(view["text"])["native_execution"]
    assert view["origin"] == "reused" and view["execution_attestation"] == "unavailable"
    assert native["implementation"] == alias_for(impl)
    assert native["logs"] == ([alias_for(log)] if retain_log else [None])
    (Path(opened["workspace_path"]) / "output/result.json").write_text(json.dumps({"schema_version": 1, "payload": {
        "summary": "Reused exact reported observations.", "outcome": "completed", "remaining_question": "",
        "limitations": ["Worker-reported execution without independent attestation."],
        "adopted_stages": [alias_for(a) for a in (impl, execution, validity)]}}))
    completed = worker.call_tool("worker_submit_result", {})
    assert completed["state"] == ("completed" if retain_log else "rejected"), completed


def _chain_sources():
    """Small exact receipt graph; bodies carry the same namespace as receipts."""
    def record(alias, kind, tool_name, **metadata):
        return {"alias": alias, "tool_name": tool_name, "metadata": {"kind": kind, **metadata}}
    records = [record("remote_impl", "experiment_implementation", "worker_experiment_prepare"),
        record("remote_exec", "experiment_execution", "worker_experiment_execute", implementation="remote_impl"),
        record("remote_valid", "experiment_stage", "worker_experiment_stage", stage="validity", derived_from=["remote_exec"]),
        record("code", "scientific_attachment", "worker_publish_files"),
        record("log", "scientific_attachment", "worker_publish_files"),
        record("result", "scientific_attachment", "worker_publish_files"),
        record("native_impl", "experiment_stage", "worker_experiment_stage", stage="implementation", derived_from=["code"]),
        record("native_exec", "experiment_stage", "worker_experiment_stage", stage="execution", origin="worker_native",
            execution_attestation="unavailable", implementation="native_impl", execution_state="succeeded", derived_from=["native_impl", "log", "result"]),
        record("native_valid", "experiment_stage", "worker_experiment_stage", stage="validity", derived_from=["native_exec"])]
    bodies = {"remote_exec": {"state": "collected", "terminal_state": "succeeded"},
        "native_impl": {"stage": "implementation", "conclusion": "Implemented.", "materials": ["code"]},
        "native_exec": {"stage": "execution", "conclusion": "Ran.", "native_execution": {
            "implementation": "native_impl", "state": "succeeded", "logs": ["log"], "results": ["result"]}}}
    for alias in ("remote_valid", "native_valid"):
        bodies[alias] = {"stage": "validity", "conclusion": "Assessed."}
    report = {"summary": "Mixed steps.", "outcome": "completed", "remaining_question": "",
        "adopted_stages": [r["alias"] for r in records if r["alias"] not in {"code", "log", "result"}]}
    return records, bodies, report


@pytest.mark.parametrize("damage", (None, "wrong_version", "orphan", "running", "failed", "remote_running", "remote_failed", "missing_result", "fake_receipt", "ordinary_file"))
def test_mixed_execution_checks_each_adopted_chain(damage):
    records, bodies, report = _chain_sources()
    native = next(r for r in records if r["alias"] == "native_exec")
    if damage == "wrong_version":
        native["metadata"]["implementation"] = "other_version"
    elif damage == "orphan":
        records[-1]["metadata"]["derived_from"] = ["remote_exec"]
    elif damage in {"running", "failed"}:
        bodies["native_exec"]["native_execution"]["state"] = damage
    elif damage == "remote_running":
        bodies["remote_exec"]["state"] = "running"
    elif damage == "remote_failed":
        bodies["remote_exec"]["terminal_state"] = "failed"
    elif damage == "missing_result":
        bodies["native_exec"]["native_execution"]["results"] = []
    elif damage == "fake_receipt":
        records[1]["tool_name"] = "worker_publish_files"
    elif damage == "ordinary_file":
        records[4]["tool_name"] = "worker_experiment_stage"
    sources = ValidationSources({name: json.dumps(body).encode() for name, body in bodies.items()}, {},
        tool_snapshot=json.dumps({"records": records}).encode())
    if damage is None:
        validate_completion(report, sources, {})
    else:
        with pytest.raises(SemanticRuleViolation):
            validate_completion(report, sources, {})


def test_unadopted_exploration_does_not_require_a_chain():
    records, bodies, report = _chain_sources()
    records.append({"alias": "debug_exploration", "metadata": {"kind": "experiment_stage", "stage": "execution"}})
    sources = ValidationSources({name: json.dumps(body).encode() for name, body in bodies.items()}, {},
        tool_snapshot=json.dumps({"records": records}).encode())
    validate_completion(report, sources, {})


# A second installed provider contributes the existing remote tools and executor.
# This tests selection/identity without installing or running a backend.
from tcad_artifact.experiment_capability import CAPABILITY as TCAD_CAPABILITY
SECOND_CAPABILITY = replace(TCAD_CAPABILITY, tools=(ComponentRef("experiment_execute_tool", "general_science"),))
SECOND_PROVIDER = PluginDefinition(plugin_id="second_provider", version="0.1.0", protocol_version="1",
    dependencies=(PluginDependency(plugin_id="tcad_artifact"), PluginDependency(plugin_id="general_science")),
    components=(ComponentSpec("remote", "experiment_capability", __name__ + ":SECOND_CAPABILITY",
        extends=ComponentRef("experiment_task_protocol", "general_science"), resources=SECOND_CAPABILITY.tools),), operations=())


def test_deployment_selection_reaches_control_worker_and_profile_identity(tmp_path, monkeypatch, installed):
    from curve_score.plugin import PLUGIN as curve
    from tcad_artifact.plugin import PLUGIN as tcad
    from scidiscovery.artifact_agent.runtime import open_runtime
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import build_local_worker_router
    from scidiscovery.operations.catalog import CatalogCompileError
    from scidiscovery.platforms.codex import _operation_toml
    from scidiscovery.operations.tooling import operation_agent_type
    installed((CORE_PLUGIN, SCIENCE_PLUGIN, curve, tcad, SECOND_PROVIDER))
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"experiment_provider": "second_provider:remote"}))
    monkeypatch.setenv("SCID_AGENT_SETTINGS_FILE", str(settings_path))
    (tmp_path / "project").mkdir()
    control = open_runtime(project_root=tmp_path / "project", state_root=tmp_path / "state")
    worker_catalog = compile_installed_catalog()
    assert control.operation_catalog.digest() == worker_catalog.digest()
    selected = worker_catalog.operation("science.experiment.v1")
    assert selected.spec.executor.capability.plugin_id == "second_provider"
    assert "worker_experiment_execute" in {tool.name for tool in selected.worker_tools}
    profile = _operation_toml(selected, python=Path(sys.executable), python_path=None,
        state_root=tmp_path / "state", local_workspace_root=tmp_path / "runs")
    assert operation_agent_type(selected) in profile
    assert "Local scientific computation" in profile
    settings_path.write_text(json.dumps({"experiment_provider": "none"}))
    disabled = compile_installed_catalog().operation("science.experiment.v1")
    assert disabled.spec.executor.capability is None
    assert "worker_experiment_execute" not in {tool.name for tool in disabled.worker_tools}
    assert selected.digest != disabled.digest
    # A fresh Worker cannot restart an old selected-provider assignment with a
    # new deployment identity. Original execution adapters remain keyed by executor.
    with pytest.raises(KeyError):
        build_local_worker_router(state_root=tmp_path / "state", operation_id=selected.spec.operation_id,
            operation_digest=selected.digest, local_workspace_root=tmp_path / "runs")
    (tmp_path / "explicit").mkdir()
    explicit = open_runtime(project_root=tmp_path / "explicit", state_root=tmp_path / "explicit-state",
        agent_settings=AgentSettings(experiment_provider="tcad_artifact:experiment_capability"))
    assert explicit.operation_catalog.operation(selected.spec.operation_id).spec.executor.capability.plugin_id == "tcad_artifact"
    settings_path.write_text('{}')
    with pytest.raises(CatalogCompileError, match="experiment_capability_selection_required"):
        compile_installed_catalog()
    with pytest.raises(ValueError, match="deployment-only"):
        effective_settings(AgentSettings(), {"experiment_provider": "none"})


def test_one_worker_moves_native_remote_native(tmp_path, monkeypatch):
    from tests.operations.test_r4_experiment_task import _real_experiment
    sequence = []
    def native_step(runtime, root, worker, instance, workspace, catalog, collected=None):
        f = SimpleNamespace(worker=worker, workspace=workspace)
        name = "after" if collected else "before"
        if collected:
            assert sequence == ["before"]
            sequence.append("remote-collected")
        code = _publish(f, name + ".py", b"print(2+2)\n", ["objective_source"])
        implementation = worker.call_tool("worker_experiment_stage", {"stage": "implementation", "conclusion": "Local arithmetic.", "materials": [code]})["reference"]
        observed = subprocess.run([sys.executable, "-B", name + ".py"], cwd=workspace / "scratch", capture_output=True, timeout=5)
        assert observed.returncode == 0 and observed.stdout == b"4\n"
        log = _publish(f, name + ".log", observed.stdout + observed.stderr, [implementation])
        result = _publish(f, name + ".csv", b"sum\n4\n", [implementation])
        execution = worker.call_tool("worker_experiment_stage", {"stage": "execution", "conclusion": "Computed 4.",
            "native_execution": {"implementation": implementation, "state": "succeeded", "logs": [log], "results": [result]}})["reference"]
        validity = worker.call_tool("worker_experiment_stage", {"stage": "validity", "conclusion": "The retained arithmetic is consistent.",
            "limitations": ["Worker-reported native execution, without independent attestation."], "materials": [execution]})["reference"]
        sequence.append(name)
        return [implementation, execution, validity]
    _real_experiment(tmp_path, monkeypatch, before_execute=native_step, before_submit=native_step)
    assert sequence == ["before", "remote-collected", "after"]
