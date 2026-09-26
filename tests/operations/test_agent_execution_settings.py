"""Execution configuration ownership, precedence and persisted settings."""
import json
from pathlib import Path

import pytest

from scidiscovery.agent_execution_settings import (
    AgentSettings, ExecutionProfile, load_settings, packaged_default_model, parse_settings, resolve_settings,
)
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


def test_execution_profile_uses_canonical_platform_model_identity():
    profile = ExecutionProfile(
        model="gpt-6-Astra", reasoning_effort="high", narrative_language="zh-CN"
    )
    assert profile.model == "gpt-6-astra"


def test_packaged_model_default_is_configured_and_overridable():
    assert packaged_default_model() == "gpt-6-sol"
    baseline = resolve_settings(AgentSettings(), AgentSettings(), operation_id="fixture",
        operation_model=None, operation_max_attempts=2)
    assert baseline["profile"].model == "gpt-6-sol"
    assert baseline["sources"]["model"] == "package_default"
    overridden = resolve_settings(parse_settings({"defaults": {"model": "global"}}),
        AgentSettings(), operation_id="fixture", operation_model=None, operation_max_attempts=2)
    assert overridden["profile"].model == "global"
    assert overridden["sources"]["model"] == "global.defaults"


@pytest.mark.parametrize("value,field", [
    ({"defaults": {"model": None}}, "model"),
    ({"defaults": {"max_attempts": True}}, "max_attempts"),
    ({"defaults": {"max_attempts": 0}}, "max_attempts"),
    ({"defaults": {"reasoning_effort": "invalid"}}, "reasoning_effort"),
    ({"operations": {"fixture": {"narrative_language": "en"}}}, "narrative_language"),
    ({"hidden_option": True}, "hidden_option"),
    ({"execution_io": {"max_export_bytes": True}}, "max_export_bytes"),
    ({"execution_io": {"file_timeout_seconds": 0}}, "file_timeout_seconds"),
    ({"execution_io": {"read_page_bytes": 262145}}, "read_page_bytes"),
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
    explicit_defaults = {"helpers": {"max_calls": 4}, "execution_io": {"max_export_bytes": 2_000_000_000}}
    assert parse_settings(explicit_defaults).sparse() == explicit_defaults
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
    # Run-local resource settings resolve at creation; the normalized model profile stays frozen.
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
    if backend == "local":
        assert "role_instructions_sha256" not in opened
        assert "input_reading" not in opened
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
    assert normalized["execution_profile"]["model"] == (packaged_default_model() if legacy else "gpt-5.6-luna")
    assert normalized["execution_profile"]["narrative_language"] == ("en" if legacy else "zh-CN")
    result = root.call_tool("operation_invoke", normalized)["result"]
    binding = settings.get_binding(instance=instance.instance_id, namespace="run", name=result["name"])
    status = runtime.runs.status(binding.object_id)
    assert status.recovery_policy["scheduler_max_attempts"] == 3
    assert status.execution_profile["profile"] == normalized["execution_profile"]


def test_direct_invoke_freezes_once_replays_and_reports_changed_defaults(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from tests.operations.test_l5_hardened_run_backend import _system
    from scidiscovery.artifact_agent.interfaces.mcp_root import RootToolError
    _, runtime, instance, root = _system(tmp_path, worker_backend="local")
    bindings = runtime.scheduler_bindings
    bindings.save_agent_settings(instance.instance_id,
        {"defaults": {"model": "gpt-5.6-luna", "max_attempts": 3}},
        expected_revision=0, maintenance=runtime.instance_maintenance)
    request = dict(name="direct", operation_id="blind.csv.observe.v1",
        instruction="Inspect the CSV.", inputs=[dict(port="source_table", artifact_names=["source_csv"])])
    original = bindings.agent_settings
    reads = []
    def read_once(*args, **kwargs):
        reads.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(bindings, "agent_settings", read_once)
    created = root.call_tool("operation_invoke", request)["result"]
    assert len(reads) == 2  # Profile resolution and separate Run-local helpers/IO snapshot.
    profile = created["execution_profile"]["profile"]
    assert profile["model"] == "gpt-5.6-luna"
    from tests.operations.test_l2_run_invariants import _worker, _envelope
    worker = _worker(runtime.runs.operation_catalog, runtime)
    opened = worker.call_tool("worker_open_assignment", {})
    Path(opened["output_directory"], "result.json").write_bytes(_envelope())
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(lambda _: root.call_tool("operation_invoke", {**request, "name": "concurrent"}), range(2)))
    assert all(reply["result"]["name"] == "concurrent" for reply in replies)
    assert len(root.call_tool("run_list", {})["runs"]) == 2
    bindings.save_agent_settings(instance.instance_id,
        {"defaults": {"model": "gpt-5.6-sol", "max_attempts": 5}},
        expected_revision=1, maintenance=runtime.instance_maintenance)
    with pytest.raises(RootToolError, match="semantic_name_conflict"):
        root.call_tool("operation_invoke", request)
    assert len(root.call_tool("run_list", {})["runs"]) == 2
    replay = root.call_tool("operation_invoke", {**request, "execution_profile": profile, "max_attempts": 3})
    assert replay["result"]["execution_profile"]["profile"] == profile


def test_direct_invoke_bad_inputs_do_not_create_run(tmp_path):
    from tests.operations.test_l5_hardened_run_backend import _system
    from scidiscovery.artifact_agent.interfaces.mcp_root import RootToolError
    _, _, _, root = _system(tmp_path, worker_backend="local")
    request = dict(name="invalid", operation_id="blind.csv.observe.v1", inputs=[])
    checked = root.call_tool("operation_preflight", request)
    assert not checked["admissible"]
    with pytest.raises(RootToolError) as error:
        root.call_tool("operation_invoke", request)
    assert checked["reason_code"] in str(error.value)
    assert root.call_tool("run_list", {})["runs"] == []


@pytest.mark.parametrize('helper_state', ['missing', 'legacy', 'explicit_selection'])
def test_local_open_directs_legacy_reader_without_rewriting_workspace(tmp_path, helper_state):
    from tests.operations.test_l5_hardened_run_backend import _system, _invoke
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    catalog, runtime, instance, root = _system(tmp_path, worker_backend='local')
    _invoke(root)
    compiled=catalog.operation('blind.csv.observe.v1')
    worker=LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id,
                                operation_digest=compiled.digest)
    opened=worker.call_tool('worker_open_assignment', {})
    assignment=Path(opened['assignment_path']); original=assignment.read_bytes()
    helper=assignment.parent/'tools/read_input.py'
    helper.unlink()
    if helper_state == 'explicit_selection':
        helper.write_text('\nREAD_INPUT_NAVIGATION = 1\n')
    if helper_state == 'legacy':
        helper.write_text('"""Legacy helper: --offset and --version."""\n')
    reopened=worker.call_tool('worker_open_assignment', {})
    assert ('bare navigation is unavailable' if helper_state == 'explicit_selection' else
            'targeted standard-library reads') in reopened['input_reading']
    assert 'role_instructions_sha256' not in reopened
    assert assignment.read_bytes() == original
    assert helper.exists() is (helper_state != 'missing')
    if helper_state == 'legacy':
        assert helper.read_text() == '"""Legacy helper: --offset and --version."""\n'
