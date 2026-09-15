"""Actual continuation after archive, archived browsing and exact restore.

Only the existing bounded CSV fixture is used; no solver or native process is
started. Both continuation modes retain the original scientific admission and
hardened transport/recovery mechanisms.
"""
from pathlib import Path
import json

import pytest

from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.approval_ui.read_model import InstanceReadModel
from scidiscovery.artifact_agent.service.instance_archive import InstanceArchive
from scidiscovery.operations.spec import ComponentRef, ComponentSpec
from tests.operations.test_instance_archive import save_archive, restore_archive
from tests.operations.test_l5_hardened_run_backend import RAW, _invoke, _system, _worker, _write_result


def _hardened_system(tmp_path):
    from blind_csv_plugin.plugin import PLUGIN
    # The existing whole-envelope CSV writer needs the ordinary result-file
    # workspace. The production general workspace now has a finalizer and does
    # not declare that hardened edit path. Bind a private plain workspace for
    # this synthetic control-chain fixture, retaining every payload validator.
    workspace = ComponentRef("archive_fixture_workspace")
    operations = tuple(operation.model_copy(update={"executor": operation.executor.model_copy(update={
        "workspace": workspace,
        "native_tools": operation.executor.native_tools.model_copy(update={"shell": "none"}),
    })}) for operation in PLUGIN.operations)
    fixture = PLUGIN.model_copy(update={"operations": operations, "components": (*PLUGIN.components,
        ComponentSpec("archive_fixture_workspace", "workspace", "scidiscovery.general_science_components:WORKSPACE"))})
    return _system(tmp_path, blind_plugin=fixture)


def _activity_rows(runs, run_id):
    with runs._connect() as connection:
        return tuple(tuple(row) for row in connection.execute(
            "SELECT rowid,* FROM run_activity WHERE run_id=? ORDER BY rowid", (run_id,)))


def _live_model(runtime):
    return InstanceReadModel(artifacts=runtime.artifacts, bindings=runtime.scheduler_bindings,
        runs=runtime.runs, approvals=runtime.approvals, executions=runtime.executions,
        operation_catalog=runtime.operation_catalog)


def _relationships(model, instance_id, keys):
    return {key: model.node(instance_id, key)["relationships"] for key in keys}


def _archived_and_restored_draft(tmp_path):
    catalog, runtime, instance, root = _hardened_system(tmp_path)
    _invoke(root, "failed_source")
    original_worker = _worker(catalog, runtime)
    opened = original_worker.call_tool("worker_open_assignment", {})
    _write_result(original_worker)
    draft_bytes = Path(opened["output_directory"], "result.json").read_bytes()
    original_id = original_worker._run_id
    original_status = root.call_tool("run_status", {"name": "failed_source", "output_paths": []})
    failed = root.call_tool("run_record_failure", {
        "name": "failed_source", "reason": "Fixture Worker ended before submission",
        "expected_state": "running", "expected_last_activity_at": original_status["last_activity_at"],
    })
    assert failed["state"] == "failed" and failed["recovery_available"]
    source = runtime.runs.status(original_id)
    recovery = runtime.runs.recovery_status(source)
    assert recovery["draft_available"] and recovery["resume_available"]
    assert not recovery["recovery_pending"]
    assert "native_tools_disabled" in source.backend_capabilities
    # End the exact original owner's transport normally. Archive still performs
    # its own nonblocking lock and backend-identity/lease quiescence checks.
    with runtime.instance_maintenance.guard(instance.instance_id):
        runtime.runs.backend.release_transport(original_id, original_worker._transport_owner)
    source_input = next(item for item in source.inputs if item.port_name == "source_table")
    preserved = runtime.runs.backend.root / "recovery" / source.recovery_draft["draft_digest"] / "result.json"
    assert preserved.read_bytes() == draft_bytes
    activities = _activity_rows(runtime.runs, original_id)
    original_links = _relationships(_live_model(runtime), instance.instance_id,
        ("artifact:source_csv", "run:failed_source"))
    assert any(link["key"] == "run:failed_source" and link["relation"] == "consumes"
        for link in original_links["artifact:source_csv"]["successors"])
    service = InstanceArchive(runtime)
    assert save_archive(service, instance.instance_id)["storage_state"] == "archived"
    assert not preserved.exists()

    archived = service.archived_model(instance.instance_id)
    assert archived.overview(instance.instance_id)["instance"]["name"] == instance.name
    detail = archived.node(instance.instance_id, "run:failed_source")
    assert detail["state"] == "failed"
    assert detail["record"]["payload"]["recovery"]["recorded"]
    assert _relationships(archived, instance.instance_id, original_links) == original_links
    assert archived.artifacts.read(source_input.artifact_ref) == RAW
    assert archived.runs.status(original_id) == source
    archived_draft = archived.runs.backend.verify_recovery(source.recovery_draft["draft_digest"],
        max_files=len(source.recovery_draft["files"]),
        max_bytes=sum(item["size_bytes"] for item in source.recovery_draft["files"]))
    assert (archived_draft.root / "result.json").read_bytes() == draft_bytes

    assert restore_archive(service, instance.instance_id)["storage_state"] == "restored"
    assert runtime.scheduler_bindings.get_instance(instance_id=instance.instance_id).state == "active"
    assert runtime.runs.status(original_id) == source
    assert _activity_rows(runtime.runs, original_id) == activities
    assert preserved.read_bytes() == draft_bytes
    assert runtime.runs.recovery_status(source) == recovery
    with runtime.runs.backend._connect_dispatch() as connection:
        assert connection.execute("SELECT 1 FROM active_transport WHERE run_id=?", (original_id,)).fetchone() is None
    return catalog, runtime, instance, root, source, draft_bytes, activities


def _changed_input(runtime, instance):
    replacement = runtime.artifacts.register(b"sample,value\na,9\n", ArtifactRegistration(
        kind="blind_csv_input", schema_id="blind.opaque.v1", payload_schema_version=1,
        media_type="text/csv", creator=runtime.actor), idempotency_key="archive-continuation:changed-input")
    runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace="artifact",
        name="changed_source_csv", object_id=replacement.artifact_id)
    return replacement.ref


@pytest.mark.parametrize("continuation", ["resume_from", "draft_from"])
def test_archive_browse_restore_preserves_real_continuation_admission_and_assignment(tmp_path, continuation):
    catalog, runtime, instance, root, source, draft_bytes, activities = _archived_and_restored_draft(tmp_path)
    changed_ref = _changed_input(runtime, instance)
    changed_request = {
        "name": "changed_resume_rejected", "operation_id": "blind.csv.observe.v1",
        "inputs": [{"port": "source_table", "artifact_names": ["changed_source_csv"]}],
        "instruction": "Make one bounded observation from the exact CSV.",
        "resume_from": "failed_source",
    }
    rejected = root.call_tool("operation_preflight", changed_request)
    assert rejected["admissible"] is False
    assert rejected["reason_code"] == "recovery_source_unavailable"
    assert runtime.runs.status(source.run_id) == source
    assert _activity_rows(runtime.runs, source.run_id) == activities

    use_changed_input = continuation == "draft_from"
    request = {
        "name": "restored_continuation", "operation_id": "blind.csv.observe.v1",
        "inputs": [{"port": "source_table", "artifact_names": [
            "changed_source_csv" if use_changed_input else "source_csv"]}],
        "instruction": "Make one bounded observation from the exact CSV.",
        continuation: "failed_source",
    }
    admitted = root.call_tool("operation_preflight", request)
    assert admitted["admissible"] is True, admitted
    invoked = root.call_tool("operation_invoke", request)
    assert invoked["result"]["state"] == "queued"
    successor_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id,
        namespace="run", name="restored_continuation")
    assert successor_id != source.run_id
    links = runtime.runs.recovery_links(successor_id)
    assert links[continuation + "_run_id"] == source.run_id
    assert links[("resume_from" if use_changed_input else "draft_from") + "_run_id"] is None

    successor_worker = _worker(catalog, runtime)
    opened = successor_worker.call_tool("worker_open_assignment", {})
    assert opened["state"] == "opened" and opened["write_protocol"] == "server_file_tools"
    assert successor_worker._run_id == successor_id
    assignment = json.loads(Path(opened["assignment_path"]).read_bytes())
    assert assignment["recovery_draft"]["scientific_evidence"] is False
    assert Path(opened["workspace_path"], "recovery-draft/result.json").read_bytes() == draft_bytes
    successor = runtime.runs.status(successor_id)
    chosen_ref = changed_ref if use_changed_input else next(
        item.artifact_ref for item in source.inputs if item.port_name == "source_table")
    assert next(item.artifact_ref for item in successor.inputs if item.port_name == "source_table") == chosen_ref
    if not use_changed_input:
        assert tuple(item.artifact_ref for item in successor.inputs) == tuple(item.artifact_ref for item in source.inputs)
        assert successor.operation_digest == source.operation_digest
    assert successor.state == "running" and successor.output_ref is None
    assert runtime.runs.status(source.run_id) == source
    assert _activity_rows(runtime.runs, source.run_id) == activities

    # Preserve this actual successor through the original failure mechanism so
    # the next archive contains a nonempty historical resume/draft edge. This
    # adds no Run or attempt-budget override and never seals a scientific result.
    _write_result(successor_worker)
    last = root.call_tool("run_status", {"name": "restored_continuation", "output_paths": []})
    assert root.call_tool("run_record_failure", {
        "name": "restored_continuation", "reason": "Fixture successor ended before submission",
        "expected_state": "running", "expected_last_activity_at": last["last_activity_at"],
    })["state"] == "failed"
    with runtime.instance_maintenance.guard(instance.instance_id):
        runtime.runs.backend.release_transport(successor_id, successor_worker._transport_owner)
    original_links = _relationships(_live_model(runtime), instance.instance_id,
        ("artifact:source_csv", "artifact:changed_source_csv", "run:failed_source", "run:restored_continuation"))
    assert any(link["key"] == "run:failed_source" and link["relation"] == continuation
        for link in original_links["run:restored_continuation"]["predecessors"])
    chosen_key = "artifact:changed_source_csv" if use_changed_input else "artifact:source_csv"
    assert any(link["key"] == "run:restored_continuation" and link["relation"] == "consumes"
        for link in original_links[chosen_key]["successors"])
    service = InstanceArchive(runtime)
    assert save_archive(service, instance.instance_id)["storage_state"] == "archived"
    archived_links = _relationships(service.archived_model(instance.instance_id), instance.instance_id, original_links)
    assert archived_links == original_links
    # The fixture has no sealed producer or independent review. Their empty
    # recorded sets are retained alongside the real input and continuation edges.
    assert all(not links["matching_reviews"] for links in archived_links.values())
    assert restore_archive(service, instance.instance_id)["storage_state"] == "restored"
    assert _relationships(_live_model(runtime), instance.instance_id, original_links) == original_links
    assert runtime.runs.status(source.run_id) == source
    assert _activity_rows(runtime.runs, source.run_id) == activities
