"""Execution configuration ownership, precedence and persisted settings."""
import json
from pathlib import Path

import pytest

from scidiscovery.agent_execution_settings import load_settings, parse_settings, resolve_settings
from scidiscovery.artifact_agent.service.scheduler_bindings import (
    SchedulerBindingService, SchedulerInstanceConflict,
)
from scidiscovery.artifact_agent.service.instance_maintenance import InstanceMaintenance


def test_sparse_precedence_and_unknown_operation_retention():
    global_settings = parse_settings({"defaults": {"model": "global", "narrative_language": "zh-CN"},
        "operations": {"fixture": {"model": "global-op", "max_attempts": 4}}})
    instance = parse_settings({"defaults": {"model": "instance", "reasoning_effort": "low"},
        "operations": {"fixture": {"reasoning_effort": "high"}, "disabled-plugin": {"model": "retained"}}})
    value = resolve_settings(global_settings, instance, operation_id="fixture",
                             operation_model="legacy", operation_max_attempts=2)
    assert value["profile"].model_dump() == dict(model="instance", reasoning_effort="high", narrative_language="zh-CN")
    assert value["max_attempts"] == 4
    assert value["sources"] == dict(model="instance.defaults", reasoning_effort="instance.operation",
                                   narrative_language="global.defaults", max_attempts="global.operation")
    assert instance.sparse()["operations"]["disabled-plugin"] == {"model": "retained"}
    cleared = resolve_settings(global_settings, parse_settings({}), operation_id="fixture",
                               operation_model="legacy", operation_max_attempts=2)
    assert cleared["profile"].model == "global-op"


@pytest.mark.parametrize("value,field", [
    ({"defaults": {"model": None}}, "model"),
    ({"defaults": {"max_attempts": True}}, "max_attempts"),
    ({"defaults": {"max_attempts": 0}}, "max_attempts"),
    ({"defaults": {"reasoning_effort": "invalid"}}, "reasoning_effort"),
    ({"operations": {"fixture": {"narrative_language": "en"}}}, "narrative_language"),
    ({"hidden_option": True}, "hidden_option"),
])
def test_configuration_errors_retain_field(value, field):
    with pytest.raises(ValueError, match=field):
        parse_settings(value)


def test_file_missing_inherits_but_invalid_file_reports_path(tmp_path):
    path = tmp_path / "agent-settings.json"
    assert load_settings(path).sparse() == {}
    path.write_text(json.dumps({"defaults": {"reasoning_effort": "invalid"}}))
    with pytest.raises(ValueError, match="(?s)agent-settings.json.*reasoning_effort"):
        load_settings(path)
    path.write_bytes(b"\xff")
    with pytest.raises(ValueError, match="agent-settings.json"):
        load_settings(path)


def test_settings_persist_cas_and_do_not_rebind_session(tmp_path):
    bindings = SchedulerBindingService(tmp_path / "database/scheduler-bindings.sqlite3")
    gate = InstanceMaintenance(tmp_path)
    instance = bindings.create_instance(name="settings", title="fixture", objective="fixture")
    original = bindings.get_instance(instance_id=instance.instance_id)
    assert bindings.agent_settings(instance.instance_id) == dict(settings={}, revision=0, updated_at=None)
    saved = bindings.save_agent_settings(instance.instance_id, {"defaults": {"narrative_language": "zh-CN"}},
                                         expected_revision=0, maintenance=gate)
    assert saved["revision"] == 1
    assert SchedulerBindingService(bindings.database_path).agent_settings(instance.instance_id) == saved
    with pytest.raises(SchedulerInstanceConflict, match="设置已更新"):
        bindings.save_agent_settings(instance.instance_id, {}, expected_revision=0, maintenance=gate)
    assert bindings.get_instance(instance_id=instance.instance_id) == original
    assert bindings.agent_settings(instance.instance_id) == saved
    cleared = bindings.save_agent_settings(instance.instance_id, {}, expected_revision=1, maintenance=gate)
    assert cleared["settings"] == {} and cleared["revision"] == 2


@pytest.mark.parametrize("backend", ["local", "hardened"])
def test_preflight_snapshot_survives_settings_change_and_submission(tmp_path, backend, monkeypatch):
    from tests.operations.test_l5_hardened_run_backend import _system, _worker, _write_result
    from tests.operations.test_instance_archive_continuation import _hardened_system
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from blind_csv_plugin.contracts import CSV_SCHEMA_PROBE
    catalog, runtime, instance, root = (_hardened_system(tmp_path) if backend == "hardened"
                                      else _system(tmp_path, worker_backend="local"))
    gate = runtime.instance_maintenance
    bindings = runtime.scheduler_bindings
    bindings.save_agent_settings(instance.instance_id,
        {"defaults": {"model": "gpt-5.6-luna", "reasoning_effort": "low", "narrative_language": "zh-CN", "max_attempts": 3}},
        expected_revision=0, maintenance=gate)
    request = dict(name="snapshot", operation_id="blind.csv.observe.v1",
                   instruction="Inspect this bounded CSV.",
                   inputs=[dict(port="source_table", artifact_names=["source_csv"])])
    checked = root.call_tool("operation_preflight", request)
    assert checked["admissible"], checked
    normalized = checked["normalized_request"]
    assert normalized["execution_profile"] == dict(model="gpt-5.6-luna", reasoning_effort="low", narrative_language="zh-CN")
    assert normalized["max_attempts"] == 3
    bindings.save_agent_settings(instance.instance_id,
        {"defaults": {"model": "gpt-5.6-sol", "reasoning_effort": "medium", "narrative_language": "en"}},
        expected_revision=1, maintenance=gate)
    with monkeypatch.context() as context:
        def unexpected_reload(*_):
            raise AssertionError("frozen invocation must not reload instance preferences")
        context.setattr(bindings, "agent_settings", unexpected_reload)
        invoked = root.call_tool("operation_invoke", normalized)["result"]
    assert invoked["execution_profile"]["profile"] == normalized["execution_profile"]
    assert root.call_tool("operation_invoke", normalized)["result"]["name"] == invoked["name"]
    compiled = catalog.operation("blind.csv.observe.v1")
    worker = (_worker(catalog, runtime) if backend == "hardened" else LocalWorkerMCPRouter(runtime.runs,
        operation_id=compiled.spec.operation_id, operation_digest=compiled.digest))
    opened = worker.call_tool("worker_open_assignment", {})
    assert "简体中文" in opened["narrative_instruction"]
    assignment = json.loads(Path(opened["assignment_path"]).read_text())
    assert assignment["narrative_instruction"] == opened["narrative_instruction"]
    if backend == "hardened":
        _write_result(worker)  # English is accepted: language is not scientific validation.
    else:
        structure = worker.call_tool("worker_csv_summarize", {})
        Path(opened["output_directory"], "result.json").write_text(json.dumps({
            "schema_version": 1, "handoff": {"verdict": "pass", "summary": "Bounded result."},
            "payload": {"schema_probe": CSV_SCHEMA_PROBE, "structure": structure,
                        "interpretation": "Mean is two.", "limitations": ["Two rows."]}}))
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    saved = root.call_tool("run_status", {"name": "snapshot", "output_paths": []})
    assert saved["execution_profile"]["profile"] == normalized["execution_profile"]
    next_checked = root.call_tool("operation_preflight", {**request, "name": "next"})
    assert next_checked["normalized_request"]["execution_profile"]["model"] == "gpt-5.6-sol"


@pytest.mark.parametrize("legacy", [False, True])
def test_recovery_inherits_source_budget_and_profile_not_current_defaults(tmp_path, legacy):
    from tests.operations.test_instance_archive_continuation import _hardened_system
    from tests.operations.test_l5_hardened_run_backend import _invoke, _worker, _write_result
    catalog, runtime, instance, root = _hardened_system(tmp_path)
    settings = runtime.scheduler_bindings
    settings.save_agent_settings(instance.instance_id,
        {"defaults": {"model": "gpt-5.6-luna", "reasoning_effort": "low", "narrative_language": "zh-CN", "max_attempts": 3}},
        expected_revision=0, maintenance=runtime.instance_maintenance)
    _invoke(root, "source")
    worker = _worker(catalog, runtime)
    worker.call_tool("worker_open_assignment", {})
    _write_result(worker)
    old_id = worker._run_id
    old = root.call_tool("run_status", {"name": "source", "output_paths": []})
    root.call_tool("run_record_failure", {"name": "source", "reason": "fixture interruption",
        "expected_state": "running", "expected_last_activity_at": old["last_activity_at"]})
    runtime.runs.backend.release_transport(old_id, worker._transport_owner)
    if legacy:
        with runtime.runs._connect() as connection:
            connection.execute("UPDATE runs SET execution_profile_json=NULL WHERE run_id=?", (old_id,))
    settings.save_agent_settings(instance.instance_id,
        {"defaults": {"model": "new-default", "reasoning_effort": "high", "narrative_language": "zh-CN", "max_attempts": 9}},
        expected_revision=1, maintenance=runtime.instance_maintenance)
    request = {"name": "continued", "operation_id": "blind.csv.observe.v1", "resume_from": "source",
        "inputs": [{"port": "source_table", "artifact_names": ["source_csv"]}],
        "instruction": "Make one bounded observation from the exact CSV."}
    check = root.call_tool("operation_preflight", request)
    assert check["admissible"], check
    normalized = check["normalized_request"]
    assert normalized["max_attempts"] is None  # Inheritance must not become an explicit budget extension.
    assert normalized["execution_profile"]["model"] == (catalog.operation(request["operation_id"]).spec.executor.model if legacy else "gpt-5.6-luna")
    assert normalized["execution_profile"]["narrative_language"] == ("en" if legacy else "zh-CN")
    result = root.call_tool("operation_invoke", normalized)["result"]
    binding = settings.get_binding(instance=instance.instance_id, namespace="run", name=result["name"])
    status = runtime.runs.status(binding.object_id)
    assert status.recovery_policy["scheduler_max_attempts"] == 3
    assert status.execution_profile["profile"] == normalized["execution_profile"]
