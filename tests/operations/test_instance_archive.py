"""Whole-history archive invariants with isolated stores; never run a solver."""
from dataclasses import replace
import hashlib
import json
import os
import sqlite3

import pytest

from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.service.instance_archive import ArchiveError, InstanceArchive
from scidiscovery.artifact_agent.service.instance_archive_records import readonly


@pytest.fixture
def archive_system(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    runtime = open_runtime(project_root=project, state_root=tmp_path / "state",
                           worker_backend="hardened", approval_receipt_secret=b"a" * 32)
    first = runtime.scheduler_bindings.create_instance_and_bind_session(
        session_key="sch_" + "a" * 32, name="archive.one", title="Original", objective="Verbatim original objective")
    second = runtime.scheduler_bindings.create_instance(name="archive.two", title="Other", objective="Keep everything")
    return runtime, InstanceArchive(runtime), first.instance_id, second.instance_id


def artifact(runtime, instance_id, name, raw=b"original bytes", parents=()):
    envelope = runtime.artifacts.register(raw, ArtifactRegistration(kind="fixture", schema_id="retired.fixture.v1",
        payload_schema_version=1, media_type="application/octet-stream", creator=runtime.actor, parent_refs=parents),
        idempotency_key=name)
    runtime.scheduler_bindings.bind(instance=instance_id, namespace="artifact", name=name, object_id=envelope.artifact_id)
    return envelope


def save_archive(service, instance_id):
    preview = service.preview(instance_id)
    assert preview["ready"], preview
    return service.archive(instance_id, preview["fingerprint"])


def test_registered_client_must_be_paused_at_preview_and_archive_commit(archive_system):
    from scidiscovery.artifact_agent.service.instance_maintenance import InstanceMaintenanceBusy
    runtime,service,first,_=archive_system
    key="sch_"+"a"*32
    runtime.scheduler_bindings.register_client(session_key=key)
    blocked=service.preview(first)
    assert not blocked['ready']
    assert any(x.get('reason')=='client_scheduling_enabled' for x in blocked['busy'])
    runtime.scheduler_bindings.set_client_enabled(session_key=key,enabled=False,expected=True)
    ready=service.preview(first)
    assert ready['ready'],ready
    runtime.scheduler_bindings.set_client_enabled(session_key=key,enabled=True,expected=False)
    with pytest.raises(InstanceMaintenanceBusy):
        service.archive(first,ready['fingerprint'])
    assert runtime.scheduler_bindings.get_instance(instance_id=first).state=='active'
    assert runtime.scheduler_bindings.session_instance(session_key=key)==first
    runtime.scheduler_bindings.set_client_enabled(session_key=key,enabled=False,expected=True)
    save_archive(service,first)


def test_reconnected_client_blocks_archive_commit_but_disconnect_keeps_history(archive_system):
    from scidiscovery.artifact_agent.service.instance_maintenance import InstanceMaintenanceBusy
    runtime, service, first, _ = archive_system
    bindings = runtime.scheduler_bindings
    key = "sch_" + "a" * 32
    bindings.register_client(session_key=key)
    with sqlite3.connect(bindings.client_database_path) as db:
        db.execute("UPDATE scheduler_clients SET last_seen=0")
    ready = service.preview(first)
    assert ready["ready"], ready
    bindings.client_heartbeat(session_key=key)
    with pytest.raises(InstanceMaintenanceBusy):
        service.archive(first, ready["fingerprint"])
    bindings.disconnect_client(session_key=key)
    assert bindings.session_instance(session_key=key) == first
    save_archive(service, first)


@pytest.mark.parametrize("presence", ["paused", "disconnected", "expired", "cleared"])
def test_pausing_client_does_not_allow_archiving_queued_or_running_work(tmp_path, presence):
    from tests.operations.test_instance_archive_continuation import _hardened_system
    from tests.operations.test_l5_hardened_run_backend import _invoke, _worker
    catalog,runtime,instance,root=_hardened_system(tmp_path)
    key='sch_'+'e'*32
    runtime.scheduler_bindings.register_client(session_key=key)
    runtime.scheduler_bindings.bind_session(session_key=key,instance_id=instance.instance_id)
    _invoke(root,'still_active')
    if presence == 'paused':
        runtime.scheduler_bindings.set_client_enabled(session_key=key,enabled=False,expected=True)
    elif presence == 'disconnected':
        runtime.scheduler_bindings.disconnect_client(session_key=key)
    else:
        with sqlite3.connect(runtime.scheduler_bindings.client_database_path) as db:
            db.execute('UPDATE scheduler_clients SET last_seen=0')
    if presence == 'cleared':
        assert runtime.scheduler_bindings.clear_offline_clients() == 1
    service=InstanceArchive(runtime)
    for expected in ('queued','running'):
        view=service.preview(instance.instance_id)
        assert not view['ready'] and any(x.get('reason')=='run_nonterminal' for x in view['busy'])
        assert root.call_tool('run_status',{'name':'still_active','output_paths':[]})['state']==expected
        if expected=='queued':
            worker=_worker(catalog,runtime)
            worker.call_tool('worker_open_assignment',{})


def restore_archive(service, instance_id):
    preview = service.restore_preview(instance_id)
    assert preview["ready"], preview
    return service.restore(instance_id, preview["fingerprint"])


def test_shared_parent_and_same_digest_are_copied_but_retained_for_other_closed_instance(archive_system):
    runtime, service, first, second = archive_system
    parent = artifact(runtime, first, "parent", b"shared bytes")
    only = artifact(runtime, first, "exclusive", b"exclusive bytes", (parent.ref,))
    other = artifact(runtime, second, "other", b"other bytes", (parent.ref,))
    same = artifact(runtime, second, "same.bytes", b"shared bytes")
    runtime.scheduler_bindings.close_instance(instance_id=second)
    initial = {key: path.stat().st_ino for key, path in {
        "scheduler": runtime.scheduler_bindings.database_path, "artifacts": runtime.artifacts.registry.database_path}.items()}
    preview = service.preview(first)
    assert preview["counts"]["shared_bytes"] == len(b"shared bytes")
    assert save_archive(service, first)["storage_state"] == "archived"
    assert runtime.artifacts.read(parent.ref) == b"shared bytes"
    assert runtime.artifacts.read(same.ref) == b"shared bytes"
    assert runtime.artifacts.read(other.ref) == b"other bytes"
    assert not runtime.artifacts.cas.path_for(only.sha256).exists()
    model = service.archived_model(first)
    assert model.artifacts.read(only.ref) == b"exclusive bytes"
    with model.artifacts.open_original(only.ref) as original_file:
        assert original_file.read() == b"exclusive bytes"
    assert model.overview(first)["instance"]["objective"] == "Verbatim original objective"
    with pytest.raises(AttributeError):
        model.artifacts.register(b"write", None, idempotency_key="forbidden")
    assert service.owner("artifact", only.artifact_id) == first
    assert restore_archive(service, first)["storage_state"] == "restored"
    assert service.owner("artifact", only.artifact_id) is None
    assert runtime.artifacts.read(only.ref) == b"exclusive bytes"
    assert runtime.scheduler_bindings.get_instance(instance_id=first).state == "active"
    assert runtime.scheduler_bindings.get_instance(instance_id=second).state == "closed"
    assert runtime.scheduler_bindings.session_instance(session_key="sch_" + "a" * 32) is None
    assert runtime.scheduler_bindings.database_path.stat().st_ino == initial["scheduler"]
    assert runtime.artifacts.registry.database_path.stat().st_ino == initial["artifacts"]


def test_closed_instance_state_and_all_semantic_revisions_round_trip(archive_system):
    runtime, service, first, _ = archive_system
    envelope = artifact(runtime, first, "old")
    runtime.scheduler_bindings.bind(instance=first, namespace="artifact", name="old.r2", logical_name="old",
                                   revision=2, object_id=envelope.artifact_id)
    runtime.scheduler_bindings.close_instance(instance_id=first)
    original = runtime.scheduler_bindings.get_instance(instance_id=first)
    save_archive(service, first)
    model = service.archived_model(first)
    assert len(model.nodes(first)["items"]) == 2
    restore_archive(service, first)
    assert runtime.scheduler_bindings.get_instance(instance_id=first) == original
    assert len(runtime.scheduler_bindings.instance_bindings(instance=first)) == 2


@pytest.mark.parametrize("point", ["after_file_copy", "before_publish", "after_publish", "database:artifacts",
                                  "before_database_commit", "after_database_commit", "before_cleanup", "after_cleanup"])
def test_interrupted_archive_resumes_without_half_database_commit_or_changed_triggers(archive_system, point):
    runtime, service, first, _ = archive_system
    envelope = artifact(runtime, first, "faulted", b"durable source")
    with readonly(runtime.artifacts.registry.database_path) as connection:
        original_triggers = [tuple(row) for row in connection.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' ORDER BY name")]
    def fault(current):
        if current == point:
            raise OSError("injected " + point)
    service._fault = fault
    with pytest.raises(OSError, match="injected"):
        save_archive(service, first)
    with readonly(runtime.artifacts.registry.database_path) as connection:
        assert [tuple(row) for row in connection.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' ORDER BY name")] == original_triggers
        artifact_exists = bool(connection.execute("SELECT 1 FROM artifact_envelopes WHERE artifact_id=?", (envelope.artifact_id,)).fetchone())
    with readonly(runtime.scheduler_bindings.database_path) as connection:
        binding_exists = bool(connection.execute("SELECT 1 FROM scheduler_bindings WHERE instance=?", (first,)).fetchone())
    assert binding_exists == artifact_exists
    service = InstanceArchive(runtime)  # fresh process-equivalent service memory
    assert service.status(first)["can_resume"]
    assert service.resume(first)["storage_state"] == "archived"
    assert service.archived_model(first).artifacts.read(envelope.ref) == b"durable source"
    assert not runtime.artifacts.cas.path_for(envelope.sha256).exists()
    restore_archive(service, first)
    assert runtime.artifacts.read(envelope.ref) == b"durable source"
    with sqlite3.connect(runtime.artifacts.registry.database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM artifact_envelopes WHERE artifact_id=?", (envelope.artifact_id,))


def test_manifest_tampering_and_changed_preview_fail_closed(archive_system):
    runtime, service, first, _ = archive_system
    artifact(runtime, first, "first")
    preview = service.preview(first)
    artifact(runtime, first, "later", b"later")
    with pytest.raises(ArchiveError, match="preview changed"):
        service.archive(first, preview["fingerprint"])
    assert service.gate.status(first) is None
    save_archive(service, first)
    path = service.root / first / "manifest.json"
    path.write_bytes(path.read_bytes() + b" ")
    assert not service.restore_preview(first)["ready"]
    with pytest.raises(ArchiveError, match="manifest digest"):
        service.archived_model(first)


def test_missing_original_bytes_recorded_without_fabrication(archive_system):
    runtime, service, first, _ = archive_system
    missing = artifact(runtime, first, "missing", b"historically missing")
    runtime.artifacts.cas.path_for(missing.sha256).unlink()
    preview = service.preview(first)
    assert preview["ready"]
    assert preview["counts"]["missing_files"] == 1
    save_archive(service, first)
    restore_archive(service, first)
    assert not runtime.artifacts.cas.path_for(missing.sha256).exists()


def test_arbitrary_scientific_payload_does_not_grant_private_artifact_ownership(archive_system):
    runtime, service, first, second = archive_system
    private = artifact(runtime, second, "private", b"secret")
    artifact(runtime, first, "untrusted.reference", canonical_json({"claimed": private.ref.model_dump(mode="json")}))
    save_archive(service, first)
    model = service.archived_model(first)
    from scidiscovery.artifact_agent.approval_ui.read_model import ReadModelScopeError
    with pytest.raises(ReadModelScopeError):
        model.artifact(first, private.artifact_id)
    assert runtime.artifacts.read(private.ref) == b"secret"


def test_restore_conflicting_bytes_never_overwrites_active_or_archive(archive_system):
    runtime, service, first, _ = archive_system
    envelope = artifact(runtime, first, "conflict", b"original")
    save_archive(service, first)
    original = runtime.artifacts.cas.path_for(envelope.sha256)
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(b"conflict")
    assert not service.restore_preview(first)["ready"]
    assert original.read_bytes() == b"conflict"
    assert service.archived_model(first).artifacts.read(envelope.ref) == b"original"


def test_unknown_plugin_debug_and_nondelete_journal_block_real_migration(archive_system):
    runtime, service, first, _ = archive_system
    debug = runtime.state_root / "local-tcad-debug" / "unowned"
    debug.mkdir(parents=True)
    (debug / "job.json").write_text("{}")
    preview = service.preview(first)
    assert not preview["ready"]
    assert any(item["code"] == "local_debug_ownership_and_writer_unknown" for item in preview["unsupported"])
    assert (debug / "job.json").exists()
    with sqlite3.connect(runtime.artifacts.registry.database_path) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
    assert not service.preview(first)["ready"]


def failed_run(runtime, instance_id, run_id, *, draft_digest=None):
    backend = runtime.runs.backend
    workspace = backend.prepare(run_id=run_id, inputs=(), assignment=b"{}", result_schema=b"{}")
    row = {"run_id": run_id, "instance_id": instance_id, "operation_id": "retired.fixture",
        "operation_version": "1", "operation_digest": "a" * 64, "agent_type": "retired.fixture", "instruction": "original",
        "inputs_json": b"[]", "backend_id": backend.backend_id, "backend_version": backend.backend_version,
        "backend_capabilities_json": canonical_json(list(backend.capabilities)), "output_binding_name": run_id + ".output",
        "output_logical_name": run_id + ".output", "output_revision": 1, "output_binding_fingerprint": "b" * 64,
        "request_digest": "c" * 64, "state": "failed", "created_at": "2000-01-01T00:00:00+00:00",
        "deadline_at": "2000-01-02T00:00:00+00:00", "completed_at": "2000-01-01T00:01:00+00:00",
        "reason": "original failure", "recovery_draft_json": canonical_json({"draft_digest": draft_digest,
            "recovery_pending": True, "original_retained": True}) if draft_digest else None}
    with sqlite3.connect(runtime.runs.database_path) as connection:
        connection.execute("INSERT INTO runs (" + ",".join(row) + ") VALUES (" + ",".join("?" for _ in row) + ")", tuple(row.values()))
        for _ in range(2):
            runtime.runs._append_activity(connection, run_id, "tool_failed", "2000-01-01T00:00:00+00:00", b'{"unchanged":null}')
    runtime.scheduler_bindings.bind(instance=instance_id, namespace="run", name=run_id, object_id=run_id)
    if hasattr(backend, "claim_transport"):
        backend.claim_transport(run_id, "historical-owner")
        with sqlite3.connect(backend.dispatch_database) as connection:
            connection.execute("UPDATE active_transport SET lease_deadline_at='2000-01-01T00:00:00+00:00' WHERE run_id=?", (run_id,))
    return workspace.root


def test_failed_recovery_pending_workspace_quarantine_and_shared_draft_preserved(archive_system):
    runtime, service, first, second = archive_system
    draft_digest = "d" * 64
    draft = runtime.runs.backend.root / "recovery" / draft_digest
    draft.mkdir()
    (draft / "result.json").write_bytes(b'{"partial":true}')
    os.chmod(draft / "result.json", 0o400)
    source = failed_run(runtime, first, "run_failedone", draft_digest=draft_digest)
    failed_run(runtime, second, "run_failedtwo", draft_digest=draft_digest)
    (source / "scratch").mkdir()
    (source / "scratch" / "attempt.cmd").write_bytes(b"original attempt")
    quarantine = runtime.runs.backend.root / "quarantine" / source.name
    quarantine.mkdir()
    (quarantine / "checkpoint.bin").write_bytes(b"checkpoint")
    with readonly(runtime.runs.database_path) as connection:
        original_rows = [tuple(row) for row in connection.execute("SELECT rowid,* FROM run_activity WHERE run_id='run_failedone'")]
    save_archive(service, first)
    assert not (source / "scratch" / "attempt.cmd").exists()
    assert not (quarantine / "checkpoint.bin").exists()
    assert (draft / "result.json").read_bytes() == b'{"partial":true}'
    restore_archive(service, first)
    assert (source / "scratch" / "attempt.cmd").read_bytes() == b"original attempt"
    assert (quarantine / "checkpoint.bin").read_bytes() == b"checkpoint"
    assert (draft / "result.json").stat().st_mode & 0o777 == 0o400
    value = runtime.runs.status("run_failedone")
    assert value.state == "failed" and value.recovery_draft["recovery_pending"]
    with readonly(runtime.runs.database_path) as connection:
        assert [tuple(row) for row in connection.execute("SELECT rowid,* FROM run_activity WHERE run_id='run_failedone'")] == original_rows
    with readonly(runtime.runs.backend.dispatch_database) as connection:
        assert not connection.execute("SELECT 1 FROM active_transport WHERE run_id='run_failedone'").fetchone()
        assert connection.execute("SELECT 1 FROM active_transport WHERE run_id='run_failedtwo'").fetchone()


def test_legacy_terminal_native_workspace_has_explicit_unknown_busy(tmp_path):
    from scidiscovery.artifact_agent.service.instance_maintenance import InstanceMaintenanceBusy
    project = tmp_path / "project"
    project.mkdir()
    runtime = open_runtime(project_root=project, state_root=tmp_path / "state", approval_receipt_secret=b"a" * 32)
    first = runtime.scheduler_bindings.create_instance(name="native", title="Native", objective="Original")
    source = failed_run(runtime, first.instance_id, "run_native")
    service = InstanceArchive(runtime)
    preview = service.preview(first.instance_id)
    assert not preview["ready"]
    assert any(item.get("reason") == "native_writers_unconfirmed" for item in preview["busy"])
    with pytest.raises(InstanceMaintenanceBusy):
        service.archive(first.instance_id, preview["fingerprint"])
    assert source.exists()
    assert service.gate.status(first.instance_id) is None
    assert service._index(first.instance_id) is None
    assert service.status(first.instance_id)["storage_state"] == "active"


def test_pending_approval_original_rows_nonce_and_access_are_history_only(archive_system):
    from scidiscovery.artifact_agent.schema.approval import approval_options_template
    runtime, service, first, _ = archive_system
    subject = artifact(runtime, first, "subject")
    launch = runtime.approvals.create_request(approval_id="apr_archive", kind="run_request", subject_refs=(subject.ref,),
        question="Frozen request?", options=approval_options_template("run_request"), idempotency_key="archive.approval", requested_by=runtime.actor)
    runtime.scheduler_bindings.bind(instance=first, namespace="approval", name="frozen.approval", object_id="apr_archive")
    with readonly(runtime.approvals.database_path) as connection:
        original = tuple(connection.execute("SELECT * FROM approval_requests WHERE approval_id='apr_archive'").fetchone())
    save_archive(service, first)
    assert not runtime.approvals.has_request("apr_archive")
    assert service.owner("approval", "apr_archive") == first
    model = service.archived_model(first)
    assert model.approvals.review("apr_archive", access_token=launch.access_token).request.approval_id == "apr_archive"
    with pytest.raises(AttributeError):
        model.approvals.refresh_access("apr_archive")
    restore_archive(service, first)
    with readonly(runtime.approvals.database_path) as connection:
        assert tuple(connection.execute("SELECT * FROM approval_requests WHERE approval_id='apr_archive'").fetchone()) == original


def test_execution_exchange_results_and_exact_execution_diagnostics_round_trip(archive_system):
    runtime, service, first, _ = archive_system
    subject = artifact(runtime, first, "execution.payload", b"original execution payload")
    execution_id = runtime.executions.create(executor="tcad", preparation_profile="retired.profile",
                                            payload_ref=subject.ref, execution_id="exe_archiveoriginal")
    runtime.scheduler_bindings.bind(instance=first, namespace="execution", name="execution.original", object_id=execution_id)
    with sqlite3.connect(runtime.executions.database_path) as connection:
        connection.execute("UPDATE executions SET state='collected',external_run_id='external_original' WHERE execution_id=?", (execution_id,))
    with readonly(runtime.executions.database_path) as connection:
        original_row = tuple(connection.execute("SELECT * FROM executions WHERE execution_id=?", (execution_id,)).fetchone())
    result_root = runtime.state_root / "executor-results"
    result = result_root / "runs" / "external_original" / "stdout.txt"
    result.parent.mkdir(parents=True)
    result.write_bytes(b"original solver stdout")
    os.chmod(result, 0o440)
    exchange = runtime.executions.exchange_root / execution_id
    collection = exchange / "collection"
    collection.mkdir(parents=True)
    (collection / "outputs.json").write_text(json.dumps({"local_path": str(result),
        "sha256": hashlib.sha256(result.read_bytes()).hexdigest(), "size_bytes": result.stat().st_size}))
    (collection / "request.json").write_bytes(b'{"historical_collection_only":true}')
    (collection / "active.lock").write_bytes(b"")
    command = runtime.project_root / "command.json"
    command.write_text(json.dumps({"command": ["unused-fixture-command"],
                                  "environment": {"SCIDISCOVERY_TCAD_RESULT_ROOT": str(result_root)}}))
    config = runtime.project_root / "tcad.json"
    config.write_text(json.dumps({"transport": "command", "command_config_path": str(command)}))
    service = InstanceArchive(runtime, plugin_configs={"tcad_artifact": config})
    diagnostics = runtime.state_root / "engineering-diagnostics"
    diagnostics.mkdir(exist_ok=True)
    diagnostic = diagnostics / ("diag_" + "f" * 32 + ".json")
    diagnostic.write_text(json.dumps({"scope": "execution:" + execution_id, "sections": ["stdout"]}))
    diagnostic.with_suffix(".stdout").write_bytes(b"original detailed diagnostic")
    unknown = diagnostics / ("diag_" + "0" * 32 + ".json")
    unknown.write_bytes(b"[]")
    save_archive(service, first)
    assert not result.exists()
    assert not (collection / "outputs.json").exists()
    assert not diagnostic.exists()
    assert unknown.read_bytes() == b"[]"
    package = service.root / first
    assert (package / "executions/results/runs/external_original/stdout.txt").read_bytes() == b"original solver stdout"
    assert (package / "diagnostics" / diagnostic.with_suffix(".stdout").name).read_bytes() == b"original detailed diagnostic"
    assert service.archived_model(first).executions.status(execution_id).state == "collected"
    restore_archive(service, first)
    with readonly(runtime.executions.database_path) as connection:
        assert tuple(connection.execute("SELECT * FROM executions WHERE execution_id=?", (execution_id,)).fetchone()) == original_row
    assert result.read_bytes() == b"original solver stdout"
    assert result.stat().st_mode & 0o777 == 0o440
    assert not (collection / "request.json").exists()
    assert diagnostic.with_suffix(".stdout").read_bytes() == b"original detailed diagnostic"


@pytest.mark.parametrize("point", ["after_restore_copy", "database:artifacts", "after_database_commit"])
def test_interrupted_restore_keeps_archive_and_resumes_original_identity(archive_system, point):
    runtime, service, first, _ = archive_system
    envelope = artifact(runtime, first, "restore.fault", b"immutable")
    save_archive(service, first)
    package = service.root / first
    manifest_before = (package / "manifest.json").read_bytes()
    def fault(current):
        if current == point:
            raise OSError("restore fault")
    service._fault = fault
    with pytest.raises(OSError, match="restore fault"):
        restore_archive(service, first)
    assert (package / "manifest.json").read_bytes() == manifest_before
    assert service.gate.status(first)
    service = InstanceArchive(runtime)
    assert service.resume(first)["storage_state"] == "restored"
    assert runtime.artifacts.read(envelope.ref) == b"immutable"
    assert runtime.scheduler_bindings.session_instance(session_key="sch_" + "a" * 32) is None


def test_new_same_digest_registration_between_switch_and_cleanup_is_retained(archive_system):
    runtime, service, first, second = archive_system
    original = artifact(runtime, first, "initial.digest", b"same digest")
    added = []
    def register_after_switch(point):
        if point == "before_cleanup":
            added.append(artifact(runtime, second, "late.digest", b"same digest"))
    service._fault = register_after_switch
    status = save_archive(service, first)
    assert status["released_bytes"] == 0
    assert runtime.artifacts.read(added[0].ref) == b"same digest"
    assert service.archived_model(first).artifacts.read(original.ref) == b"same digest"
    restore_archive(service, first)
    assert runtime.artifacts.read(original.ref) == b"same digest"


@pytest.mark.parametrize("point", ["after_file_copy", "after_publish", "after_database_commit"])
def test_archive_rollback_preserves_original_active_identity_without_session_rebind(archive_system, point):
    runtime, service, first, _ = archive_system
    original = artifact(runtime, first, "rollback", b"original")
    def fault(current):
        if current == point:
            raise OSError("rollback fault")
    service._fault = fault
    with pytest.raises(OSError, match="rollback fault"):
        save_archive(service, first)
    service = InstanceArchive(runtime)
    assert service.rollback(first)["storage_state"] == "restored"
    assert runtime.artifacts.read(original.ref) == b"original"
    assert runtime.scheduler_bindings.get_instance(instance_id=first).state == "active"
    assert runtime.scheduler_bindings.session_instance(session_key="sch_" + "a" * 32) is None


def test_all_approval_decisions_attempts_nonces_and_triggers_round_trip(archive_system):
    from scidiscovery.artifact_agent.schema.approval import LocalIdentityRef, approval_options_template
    runtime, service, first, _ = archive_system
    subject = artifact(runtime, first, "decision.subject")
    launch = runtime.approvals.create_request(approval_id="apr_decided", kind="run_request", subject_refs=(subject.ref,),
        question="Frozen request?", options=approval_options_template("run_request"), idempotency_key="decided.approval", requested_by=runtime.actor)
    runtime.scheduler_bindings.bind(instance=first, namespace="approval", name="decided", object_id="apr_decided")
    review = runtime.approvals.review("apr_decided", access_token=launch.access_token)
    decision = runtime.approvals.record_ui_decision(approval_id="apr_decided", access_token=launch.access_token,
        csrf_token=review.csrf_token, decision_nonce=review.decision_nonce, selected_option=review.request.options[0].option_id, rationale="isolated fixture",
        decided_by=LocalIdentityRef(identity_id="local_user", display_name="Fixture"), ui_session_id="fixture_ui")
    tables = ("approval_requests", "approval_decisions", "used_nonces", "decision_attempts")
    with readonly(runtime.approvals.database_path) as connection:
        originals = {table: [tuple(row) for row in connection.execute("SELECT * FROM " + table)] for table in tables}
        triggers = [tuple(row) for row in connection.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' ORDER BY name")]
    save_archive(service, first)
    with readonly(runtime.approvals.database_path) as connection:
        assert all(connection.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] == 0 for table in tables)
        assert [tuple(row) for row in connection.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' ORDER BY name")] == triggers
    assert service.archived_model(first).artifacts.read(decision)
    restore_archive(service, first)
    with readonly(runtime.approvals.database_path) as connection:
        assert {table: [tuple(row) for row in connection.execute("SELECT * FROM " + table)] for table in tables} == originals


def test_archive_restore_archive_keeps_previous_package_inside_managed_root(archive_system):
    runtime, service, first, _ = archive_system
    original = artifact(runtime, first, "repeat", b"repeat")
    save_archive(service, first)
    restore_archive(service, first)
    save_archive(service, first)
    histories = list((service.root / ".history").iterdir())
    assert len(histories) == 1
    assert (histories[0] / "manifest.json").is_file()
    assert not (service.root.parent / "history").exists()
    assert service.archived_model(first).artifacts.read(original.ref) == b"repeat"


@pytest.mark.parametrize("point", ["after_file_copy", "before_cleanup"])
def test_new_recovery_owner_during_archive_preserves_whole_digest_tree(archive_system, point):
    runtime, service, first, second = archive_system
    sha = "d" * 64
    recovery = runtime.runs.backend.root / "recovery" / sha
    recovery.mkdir()
    (recovery / "empty").mkdir()
    (recovery / "draft.txt").write_bytes(b"shared complete draft")
    failed_run(runtime, first, "run_draftfirst", draft_digest=sha)
    added = []
    def add_reference(current):
        if current == point and not added:
            added.append(failed_run(runtime, second, "run_draftlate", draft_digest=sha))
    service._fault = add_reference
    save_archive(service, first)
    assert (recovery / "draft.txt").read_bytes() == b"shared complete draft"
    assert (recovery / "empty").is_dir()
    assert runtime.runs.status("run_draftlate").recovery_draft["draft_digest"] == sha
    restore_archive(service, first)
    assert runtime.runs.status("run_draftfirst").state == "failed"


def test_other_unowned_files_do_not_exhaust_target_file_budget(archive_system, monkeypatch):
    from scidiscovery.artifact_agent.service import instance_archive_files
    runtime, service, first, _ = archive_system
    artifact(runtime, first, "small.target", b"one")
    other = runtime.artifacts.cas.root / "unowned"
    other.mkdir()
    for ordinal in range(20):
        (other / str(ordinal)).write_bytes(b"unowned")
    monkeypatch.setattr(instance_archive_files, "MAX_FILES", 3)
    preview = service.preview(first)
    assert preview["ready"], preview
    assert preview["counts"]["files"] == 1
    assert any(scope.get("expanded") is False and scope["files"] is None for scope in preview["unowned"])


@pytest.mark.parametrize("when", ["preview", "before_cleanup"])
@pytest.mark.parametrize("malformed", [False, True])
def test_unknown_other_recovery_metadata_retains_target_tree_without_blocking_archive(archive_system, when, malformed):
    from scidiscovery.artifact_agent.service.instance_archive_files import RECOVERY_SCAN_BYTES
    runtime, service, first, second = archive_system
    sha = "e" * 64
    recovery = runtime.runs.backend.root / "recovery" / sha
    recovery.mkdir()
    (recovery / "empty").mkdir()
    (recovery / "draft.txt").write_bytes(b"preserve on unknown ownership")
    failed_run(runtime, first, "run_uncertainfirst", draft_digest=sha)
    def create_unknown():
        failed_run(runtime, second, "run_uncertainother")
        value = '{"draft_digest":[' if malformed else json.dumps({"old_metadata": "x" * RECOVERY_SCAN_BYTES})
        with sqlite3.connect(runtime.runs.database_path) as connection:
            connection.execute("UPDATE runs SET recovery_draft_json=? WHERE run_id=?", (value, "run_uncertainother"))
    if when == "preview":
        create_unknown()
        preview = service.preview(first)
        assert preview["ready"], preview
        assert any(gap["code"] == "retained_recovery_scan_incomplete" for gap in preview["gaps"])
    else:
        def add_unknown(point):
            if point == when:
                create_unknown()
        service._fault = add_unknown
    save_archive(service, first)
    assert (recovery / "draft.txt").read_bytes() == b"preserve on unknown ownership"
    assert (recovery / "empty").is_dir()


def test_other_instance_activity_never_reuses_archived_event_ids_or_invalidates_preview(archive_system):
    runtime, service, first, second = archive_system
    failed_run(runtime, second, "run_eventsother")
    failed_run(runtime, first, "run_eventslast")
    with readonly(runtime.runs.database_path) as connection:
        original = [tuple(row) for row in connection.execute("SELECT rowid,* FROM run_activity WHERE run_id='run_eventslast' ORDER BY rowid")]
    preview = service.preview(first)
    assert preview["ready"], preview
    runtime.runs.record_tool_observation("run_eventsother", "timing", {"after_preview": True})
    service.archive(first, preview["fingerprint"])
    runtime.runs.record_tool_observation("run_eventsother", "timing", {"after_archive": True})
    with readonly(runtime.runs.database_path) as connection:
        newest = connection.execute("SELECT MAX(rowid) FROM run_activity WHERE run_id='run_eventsother'").fetchone()[0]
    assert newest > max(row[0] for row in original)
    restore_archive(service, first)
    with readonly(runtime.runs.database_path) as connection:
        assert [tuple(row) for row in connection.execute("SELECT rowid,* FROM run_activity WHERE run_id='run_eventslast' ORDER BY rowid")] == original


@pytest.mark.parametrize("rebuild", [False, True])
def test_missing_or_rebuilt_view_cache_does_not_block_scientific_restore(archive_system, rebuild):
    from scidiscovery.artifact_agent.approval_ui.trajectory import TrajectoryStore
    runtime, service, first, second = archive_system
    original = artifact(runtime, first, "cache.original", b"scientific bytes")
    path = runtime.state_root / "ui" / "workbench.sqlite3"
    cache = TrajectoryStore(path)
    cache.observe(first, [{"key": "artifact:cache.original", "state": "registered"}])
    save_archive(service, first)
    history = service.archived_views_path(first).read_bytes()
    path.unlink()
    other_before = None
    if rebuild:
        cache.observe(second, [{"key": "run:other", "state": "failed"}])
        other_before = cache.observations(second)
    preview = service.restore_preview(first)
    assert preview["ready"], preview
    assert any(item["code"] == "active_view_cache_rebuild_required" for item in preview["gaps"])
    service.restore(first, preview["fingerprint"])
    assert runtime.artifacts.read(original.ref) == b"scientific bytes"
    assert service.archived_views_path(first).read_bytes() == history
    assert service.status(first)["restore_gaps"]
    if rebuild:
        assert cache.observations(second) == other_before


def test_restore_copy_can_roll_back_to_intact_archive(archive_system):
    runtime, service, first, _ = archive_system
    original = artifact(runtime, first, "restore.rollback", b"preserved")
    save_archive(service, first)
    def fail(point):
        if point == "after_restore_copy":
            raise OSError("rollback restore")
    service._fault = fail
    with pytest.raises(OSError, match="rollback restore"):
        restore_archive(service, first)
    service = InstanceArchive(runtime)
    assert service.rollback(first)["storage_state"] == "archived"
    assert not runtime.artifacts.cas.path_for(original.sha256).exists()
    assert service.archived_model(first).artifacts.read(original.ref) == b"preserved"
    restore_archive(service, first)


def test_restore_switch_detects_missing_files_before_database_commit(archive_system):
    runtime, service, first, _ = archive_system
    original = artifact(runtime, first, "restore.changed", b"verified")
    save_archive(service, first)
    path = runtime.artifacts.cas.path_for(original.sha256)
    def change_after_verification(point):
        if point == "before_restore_switch":
            path.unlink()
    service._fault = change_after_verification
    with pytest.raises(ArchiveError, match="conflicts changed"):
        restore_archive(service, first)
    with readonly(runtime.artifacts.registry.database_path) as connection:
        assert connection.execute("SELECT 1 FROM artifact_envelopes WHERE artifact_id=?", (original.artifact_id,)).fetchone() is None
    assert service.archived_model(first).artifacts.read(original.ref) == b"verified"
    assert service.gate.status(first) is not None


def sealed_recovery_fixture(runtime, instance_id, run_id, *, publish):
    root = failed_run(runtime, instance_id, run_id)
    (root / "output" / "first.txt").write_bytes(b"first complete recovery file")
    (root / "output" / "second.txt").write_bytes(b"second complete recovery file")
    candidate = runtime.runs.backend.seal(run_id, max_files=4, max_bytes=1024)
    if publish:
        runtime.runs.backend.discard(run_id, preserve_digest=candidate.digest, max_files=4, max_bytes=1024, retain_original=True)
        with sqlite3.connect(runtime.runs.database_path) as connection:
            connection.execute("UPDATE runs SET recovery_draft_json=? WHERE run_id=?",
                (canonical_json({"draft_digest": candidate.digest, "recovery_pending": True, "original_retained": True}), run_id))
    return candidate.digest


def publish_other_recovery(runtime, service, instance_id, run_id, sha):
    with service.gate.guard(instance_id):
        draft = runtime.runs.backend.discard(run_id, preserve_digest=sha, max_files=4, max_bytes=1024, retain_original=True)
        with sqlite3.connect(runtime.runs.database_path) as connection:
            connection.execute("UPDATE runs SET recovery_draft_json=? WHERE run_id=?",
                (canonical_json({"draft_digest": sha, "recovery_pending": True, "original_retained": True}), run_id))
    return draft.root.stat().st_ino


@pytest.mark.parametrize("point", ["during_recovery_restore_copy", "before_recovery_restore_publish"])
def test_restore_shared_recovery_is_published_as_one_complete_immutable_tree(archive_system, point):
    runtime, service, first, second = archive_system
    sha = sealed_recovery_fixture(runtime, first, "run_atomicfirst", publish=True)
    assert sealed_recovery_fixture(runtime, second, "run_atomicother", publish=False) == sha
    save_archive(service, first)
    published = runtime.runs.backend.root / "recovery" / sha
    assert not published.exists()
    identities = []
    def publish_during_restore(current):
        if current == point and not identities:
            assert not published.exists(), "restore must not expose an incomplete digest directory"
            identities.append(publish_other_recovery(runtime, service, second, "run_atomicother", sha))
    service._fault = publish_during_restore
    restore_archive(service, first)
    assert identities and published.stat().st_ino == identities[0]
    assert len(runtime.runs.backend.verify_recovery(sha, max_files=4, max_bytes=1024).files) == 2
    assert not list(published.parent.glob(".staging_" + sha + "_restore_*"))


def test_restore_never_fills_an_existing_incomplete_published_recovery_tree(archive_system):
    runtime, service, first, _ = archive_system
    sha = sealed_recovery_fixture(runtime, first, "run_partialpublished", publish=True)
    save_archive(service, first)
    published = runtime.runs.backend.root / "recovery" / sha
    published.mkdir(mode=0o500)
    inode = published.stat().st_ino
    preview = service.restore_preview(first)
    assert not preview["ready"]
    assert any(item["code"] == "published_recovery_tree_conflict" for item in preview["unsupported"])
    with pytest.raises(ArchiveError):
        service.restore(first, preview["fingerprint"])
    assert published.stat().st_ino == inode and list(published.iterdir()) == []


@pytest.mark.parametrize("action", ["resume", "rollback"])
def test_interrupted_private_restore_stage_is_cleaned_without_touching_other_jobs(archive_system, action):
    runtime, service, first, second = archive_system
    sha = sealed_recovery_fixture(runtime, first, "run_stagefirst", publish=True)
    assert sealed_recovery_fixture(runtime, second, "run_stageother", publish=False) == sha
    save_archive(service, first)
    recovery_root = runtime.runs.backend.root / "recovery"
    other_stage = recovery_root / (".staging_" + sha + "_otherjob")
    other_stage.mkdir()
    (other_stage / "unknown.bin").write_bytes(b"unowned old stage")
    calls = []
    def interrupt_copy(point):
        if point == "during_recovery_restore_copy":
            calls.append(point)
            if len(calls) == 2:
                job = service._index(first)["job_id"]
                stage = recovery_root / (".staging_" + sha + "_" + job)
                (stage / "second.txt.archive-copy").write_bytes(b"partial derived copy")
                raise OSError("private stage copy interrupted")
    service._fault = interrupt_copy
    with pytest.raises(OSError, match="private stage copy interrupted"):
        restore_archive(service, first)
    old_job = service._index(first)["job_id"]
    stage = recovery_root / (".staging_" + sha + "_" + old_job)
    assert stage.exists()
    inode = publish_other_recovery(runtime, service, second, "run_stageother", sha)
    service = InstanceArchive(runtime)
    getattr(service, action)(first)
    assert not stage.exists()
    assert (other_stage / "unknown.bin").read_bytes() == b"unowned old stage"
    assert (recovery_root / sha).stat().st_ino == inode
    assert len(runtime.runs.backend.verify_recovery(sha, max_files=4, max_bytes=1024).files) == 2


def test_restore_resume_rebuilds_an_unpublished_stage_with_a_linked_temporary_name(archive_system):
    runtime, service, first, _ = archive_system
    sha = sealed_recovery_fixture(runtime, first, "run_linkedstage", publish=True)
    save_archive(service, first)
    recovery_root = runtime.runs.backend.root / "recovery"
    calls = []
    def interrupt_copy(point):
        if point == "during_recovery_restore_copy":
            calls.append(point)
            if len(calls) == 2:
                stage = recovery_root / (".staging_" + sha + "_" + service._index(first)["job_id"])
                complete, temporary = stage / "first.txt", stage / "first.txt.archive-copy"
                os.link(complete, temporary)
                assert complete.stat().st_ino == temporary.stat().st_ino
                raise OSError("interrupted before temporary unlink")
    service._fault = interrupt_copy
    with pytest.raises(OSError, match="temporary unlink"):
        restore_archive(service, first)
    old_stage = recovery_root / (".staging_" + sha + "_" + service._index(first)["job_id"])
    assert old_stage.exists() and not (recovery_root / sha).exists()
    service = InstanceArchive(runtime)
    assert service.resume(first)["storage_state"] == "restored"
    assert not old_stage.exists()
    assert len(runtime.runs.backend.verify_recovery(sha, max_files=4, max_bytes=1024).files) == 2


@pytest.mark.parametrize("action", ["resume", "rollback"])
def test_interrupted_recovery_retirement_never_cleans_a_new_published_digest(archive_system, action):
    runtime, service, first, second = archive_system
    sha = sealed_recovery_fixture(runtime, first, "run_retiredfirst", publish=True)
    assert sealed_recovery_fixture(runtime, second, "run_retiredother", publish=False) == sha
    published = runtime.runs.backend.root / "recovery" / sha
    def interrupt(point):
        if point == "after_recovery_retire_rename":
            raise OSError("retirement crash after rename")
    service._fault = interrupt
    with pytest.raises(OSError, match="retirement crash"):
        save_archive(service, first)
    assert not published.exists()
    inode = publish_other_recovery(runtime, service, second, "run_retiredother", sha)
    service = InstanceArchive(runtime)
    getattr(service, action)(first)
    assert published.stat().st_ino == inode
    assert len(runtime.runs.backend.verify_recovery(sha, max_files=4, max_bytes=1024).files) == 2
    assert not list(published.parent.glob(".archive-retired_*"))
    assert all(item["phase"] == "completed" for item in service._index(first)["recovery_retirements"].values())
    if action == "resume":
        restore_archive(service, first)


def test_restore_reuses_a_late_cas_publication_without_replacing_its_inode(archive_system, monkeypatch):
    from scidiscovery.artifact_agent.service import instance_archive_files
    runtime, service, first, second = archive_system
    original = artifact(runtime, first, "cas.late.original", b"same immutable bytes")
    save_archive(service, first)
    destination = runtime.artifacts.cas.path_for(original.sha256)
    link = instance_archive_files.os.link
    published = []
    def publish_before_link(source, target, **kwargs):
        if str(target) == str(destination) and not published:
            published.append(None)
            artifact(runtime, second, "cas.late.other", b"same immutable bytes")
            published[0] = destination.stat().st_ino
        return link(source, target, **kwargs)
    monkeypatch.setattr(instance_archive_files.os, "link", publish_before_link)
    restore_archive(service, first)
    assert published and destination.stat().st_ino == published[0]
    assert runtime.artifacts.read(original.ref) == b"same immutable bytes"


@pytest.mark.parametrize("point", ["after_archive_scan", "after_archive_publish_scan", "after_archive_switch_scan"])
def test_archive_version_ticket_rejects_a_controlled_commit_after_its_scan(archive_system, point):
    runtime, service, first, second = archive_system
    original = artifact(runtime, first, "ticket.original", b"original")
    def change_control(current):
        if current == point:
            artifact(runtime, second, "ticket.other", b"other")
    service._fault = change_control
    with pytest.raises(ArchiveError, match="control records changed during archive scan"):
        save_archive(service, first)
    assert runtime.artifacts.read(original.ref) == b"original"
    if point == "after_archive_scan":
        assert service.gate.status(first) is None
        assert service._index(first) is None
    else:
        assert service.status(first)["can_resume"]
        service = InstanceArchive(runtime)
        assert service.resume(first)["storage_state"] == "archived"


def test_read_ticket_uses_the_same_connections_to_detect_foreign_commits(archive_system):
    from scidiscovery.artifact_agent.service.instance_archive_records import ReadTicket
    runtime, _, _, second = archive_system
    with ReadTicket(runtime) as ticket:
        connection = ticket.connections["scheduler"]
        before = connection.execute("PRAGMA data_version").fetchone()[0]
        artifact(runtime, second, "ticket.foreign", b"foreign")
        assert connection.execute("PRAGMA data_version").fetchone()[0] != before
        with pytest.raises(ArchiveError, match="control records changed"):
            ticket.validate()


def test_full_ownership_scans_and_payload_hashes_stay_outside_global_exclusive(archive_system, monkeypatch):
    from contextlib import contextmanager
    from scidiscovery.artifact_agent.service import instance_archive, instance_archive_files
    from scidiscovery.artifact_agent.service.instance_archive_records import Records
    runtime, service, first, _ = archive_system
    artifact(runtime, first, "outside.exclusive", b"large original bytes" * 50000)
    held = []
    exclusive, select, hash_original = service.gate.exclusive, Records.select, instance_archive_files.hash_file
    @contextmanager
    def tracked_exclusive(instance_id):
        with exclusive(instance_id):
            held.append(instance_id)
            try:
                yield
            finally:
                held.pop()
    def tracked_select(records, *args, **kwargs):
        assert not held, "whole ownership scans must precede the global exclusive switch"
        return select(records, *args, **kwargs)
    def tracked_hash(path):
        assert not held, "content hashing must precede the global exclusive switch"
        return hash_original(path)
    monkeypatch.setattr(service.gate, "exclusive", tracked_exclusive)
    monkeypatch.setattr(Records, "select", tracked_select)
    monkeypatch.setattr(instance_archive, "hash_file", tracked_hash)
    monkeypatch.setattr(instance_archive_files, "hash_file", tracked_hash)
    save_archive(service, first)
    restore_archive(service, first)


def test_foreign_key_commit_still_rolls_back_all_attached_changes(archive_system):
    from scidiscovery.artifact_agent.schema.approval import approval_options_template
    from scidiscovery.artifact_agent.service.instance_archive_records import transfer_records
    runtime, service, first, _ = archive_system
    subject = artifact(runtime, first, "foreign.key.subject")
    runtime.approvals.create_request(approval_id="apr_foreignkey", kind="run_request", subject_refs=(subject.ref,),
        question="Original?", options=approval_options_template("run_request"), idempotency_key="foreign.key.approval", requested_by=runtime.actor)
    runtime.scheduler_bindings.bind(instance=first, namespace="approval", name="foreign.key.approval", object_id="apr_foreignkey")
    with sqlite3.connect(runtime.approvals.database_path) as connection:
        connection.execute("INSERT INTO used_nonces VALUES (?,?,?,?)", ("nonce", "apr_foreignkey", subject.ref.canonical_json(), "2000-01-01"))
    snapshot = service._snapshot(first)
    original = snapshot["databases"]["scheduler"]["tables"]["scheduler_instances"][0]
    # Deliberately omit a dependent immutable row from this mechanical transfer.
    # COMMIT must enforce the original FK without a whole-runtime graph scan.
    snapshot["databases"]["approvals"]["tables"]["used_nonces"] = []
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        transfer_records(snapshot["database_paths"], snapshot["databases"], direction="archive",
                         exclusive_ids=snapshot["exclusive_artifact_ids"], tombstone=original)
    assert runtime.approvals.has_request("apr_foreignkey")
    assert runtime.artifacts.read(subject.ref)


@pytest.mark.process_e2e
@pytest.mark.parametrize("action,point", [("restore", "before_restore_gate_finish"), ("archive", "database:artifacts"),
                                         ("archive", "after_recovery_retire_rename")])
def test_hard_process_exit_preserves_resumable_gate_and_atomic_records(archive_system, action, point):
    import subprocess
    import sys
    from pathlib import Path
    runtime, service, first, _ = archive_system
    original = artifact(runtime, first, "hard.exit", b"durable")
    recovery = None
    if point == "after_recovery_retire_rename":
        sha = sealed_recovery_fixture(runtime, first, "run_hardretirement", publish=True)
        recovery = runtime.runs.backend.root / "recovery" / sha
    if action == "restore":
        save_archive(service, first)
    script = """
import os,sys
sys.path.insert(0,sys.argv[6])
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.service.instance_archive import InstanceArchive
runtime=open_runtime(project_root=sys.argv[1],state_root=sys.argv[2],worker_backend='hardened',approval_receipt_secret=b'a'*32)
service=InstanceArchive(runtime)
def fail(point):
    if point==sys.argv[5]: os._exit(71)
service._fault=fail
instance=sys.argv[3]
if sys.argv[4]=='archive':
    preview=service.preview(instance)
    service.archive(instance,preview['fingerprint'])
else:
    preview=service.restore_preview(instance)
    service.restore(instance,preview['fingerprint'])
"""
    completed = subprocess.run([sys.executable, "-c", script, str(runtime.project_root), str(runtime.state_root), first, action, point,
                                str(Path(__file__).resolve().parents[2] / "src")],
                               timeout=30, capture_output=True)
    assert completed.returncode == 71, completed.stderr.decode()
    service = InstanceArchive(runtime)
    assert service.status(first)["can_resume"]
    assert service.gate.status(first) is not None
    result = service.resume(first)
    assert result["storage_state"] == ("restored" if action == "restore" else "archived")
    if action == "archive":
        restore_archive(service, first)
    assert runtime.artifacts.read(original.ref) == b"durable"
    assert service.gate.status(first) is None
    if recovery is not None:
        assert (recovery / "first.txt").read_bytes() == b"first complete recovery file"
        assert not list(recovery.parent.glob(".archive-retired_*"))
