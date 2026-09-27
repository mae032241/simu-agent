"""An unrelated instance's history must not consume the target snapshot budget."""
import hashlib
import sqlite3

import pytest

from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.service.instance_archive import InstanceArchive
from scidiscovery.artifact_agent.service.instance_archive_records import Records, canonical, encode, readonly


@pytest.fixture
def scale_system(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    runtime = open_runtime(project_root=project, state_root=tmp_path / "state",
                           worker_backend="hardened", approval_receipt_secret=b"s" * 32)
    target = runtime.scheduler_bindings.create_instance(
        name="scale.small", title="Small target", objective="Original small-instance description")
    other = runtime.scheduler_bindings.create_instance(
        name="scale.other", title="Large history", objective="Keep this instance intact")
    return runtime, InstanceArchive(runtime), target.instance_id, other.instance_id


def register(runtime, instance_id, name, raw, *, parents=()):
    envelope = runtime.artifacts.register(raw, ArtifactRegistration(
        kind="fixture", schema_id="retired.scale-fixture.v1", payload_schema_version=1,
        media_type="application/octet-stream", creator=runtime.actor, parent_refs=parents), idempotency_key=name)
    runtime.scheduler_bindings.bind(instance=instance_id, namespace="artifact", name=name, object_id=envelope.artifact_id)
    return envelope


def historical_run(runtime, instance_id, run_id):
    backend = runtime.runs.backend
    workspace = backend.prepare(run_id=run_id, inputs=(), assignment=b"{}", result_schema=b"{}")
    values = {
        "run_id": run_id, "instance_id": instance_id, "operation_id": "retired.scale-fixture",
        "operation_version": "1", "operation_digest": "a" * 64, "agent_type": "retired.scale-fixture",
        "instruction": "Original instruction", "inputs_json": b"[]", "backend_id": backend.backend_id,
        "backend_version": backend.backend_version, "backend_capabilities_json": canonical_json(list(backend.capabilities)),
        "output_binding_name": run_id + ".output", "output_logical_name": run_id + ".output", "output_revision": 1,
        "output_binding_fingerprint": "b" * 64, "request_digest": "c" * 64, "state": "failed",
        "created_at": "2000-01-01T00:00:00+00:00", "deadline_at": "2000-01-02T00:00:00+00:00",
        "completed_at": "2000-01-01T00:01:00+00:00", "reason": "Original historical failure",
    }
    with sqlite3.connect(runtime.runs.database_path) as connection:
        connection.execute("INSERT INTO runs (" + ",".join(values) + ") VALUES (" + ",".join("?" for _ in values) + ")",
                           tuple(values.values()))
    runtime.scheduler_bindings.bind(instance=instance_id, namespace="run", name=run_id, object_id=run_id)
    backend.claim_transport(run_id, "historical-owner")
    with sqlite3.connect(backend.dispatch_database) as connection:
        connection.execute("UPDATE active_transport SET lease_deadline_at='2000-01-01T00:00:00+00:00' WHERE run_id=?",
                           (run_id,))
    return workspace.root


def add_activity(runtime, run_id, raw, *, count=1):
    # The generator does not retain a second copy of the whole large history.
    with sqlite3.connect(runtime.runs.database_path) as connection:
        connection.executemany(
            "INSERT INTO run_activity(run_id,activity,recorded_at,diagnostic_json) VALUES (?,?,?,?)",
            ((run_id, "tool_failed", "2000-01-01T00:00:00+00:00", raw) for _ in range(count)))
        connection.execute("UPDATE run_activity_sequence SET high_water=(SELECT MAX(rowid) FROM run_activity) WHERE slot=1")


def run_fingerprint(runtime, run_id):
    """Compare original SQLite values and event rowids without retaining history."""
    fingerprint = hashlib.sha256()
    with readonly(runtime.runs.database_path) as connection:
        for query in ("SELECT * FROM runs WHERE run_id=?",
                      "SELECT rowid AS original_rowid,* FROM run_activity WHERE run_id=? ORDER BY rowid",
                      "SELECT * FROM run_tool_evidence WHERE run_id=? ORDER BY ordinal"):
            fingerprint.update(query.encode())
            for row in connection.execute(query, (run_id,)):
                raw = canonical(encode(dict(row)))
                fingerprint.update(len(raw).to_bytes(8, "big"))
                fingerprint.update(raw)
    return fingerprint.hexdigest()


def test_other_instance_over_16_mib_history_does_not_block_small_round_trip(scale_system):
    runtime, service, target, other = scale_system
    shared = register(runtime, target, "scale.shared", b"exact shared original")
    exclusive = register(runtime, target, "scale.exclusive", b"exact exclusive original", parents=(shared.ref,))
    outside_raw = canonical_json({"untrusted_scientific_claim": exclusive.ref.model_dump(mode="json")})
    outside = register(runtime, other, "scale.outside.scientific", outside_raw)
    historical_run(runtime, other, "run_largehistory")
    detail = canonical_json({"detail": "x" * (64 * 1024)})
    add_activity(runtime, "run_largehistory", detail, count=320)
    # A real controlled reference after the old inventory boundary still keeps
    # its exact target parent. Scientific payload text above grants no ownership.
    add_activity(runtime, "run_largehistory", canonical_json({"evidence": shared.ref.model_dump(mode="json")}))
    workspace = historical_run(runtime, target, "run_smallhistory")
    (workspace / "original.txt").write_bytes(b"original workspace bytes")
    add_activity(runtime, "run_smallhistory", b'{"untouched":null}', count=2)
    with readonly(runtime.runs.database_path) as connection:
        foreign_bytes = connection.execute(
            "SELECT SUM(length(diagnostic_json)) FROM run_activity WHERE run_id='run_largehistory'").fetchone()[0]
    assert foreign_bytes > 16 * 1024 * 1024
    before_other = run_fingerprint(runtime, "run_largehistory")
    before_target = run_fingerprint(runtime, "run_smallhistory")
    other_instance = runtime.scheduler_bindings.get_instance(instance_id=other)
    other_bindings = runtime.scheduler_bindings.instance_bindings(instance=other)

    selected = Records(runtime).select(target)
    assert selected["run_ids"] == ["run_smallhistory"]
    assert selected["artifact_ids"] == sorted((shared.artifact_id, exclusive.artifact_id))
    assert selected["exclusive_artifact_ids"] == [exclusive.artifact_id]
    assert selected["databases"]["runs"]["tables"]["run_activity_sequence"] == []
    assert "run_activity_sequence" in selected["databases"]["runs"]["schema"]["tables"]
    preview = service.preview(target)
    assert preview["ready"], preview
    assert preview["counts"]["shared_bytes"] == len(b"exact shared original")
    assert service.archive(target, preview["fingerprint"])["storage_state"] == "archived"
    assert run_fingerprint(runtime, "run_largehistory") == before_other
    assert runtime.scheduler_bindings.get_instance(instance_id=other) == other_instance
    assert runtime.scheduler_bindings.instance_bindings(instance=other) == other_bindings
    assert runtime.artifacts.read(shared.ref) == b"exact shared original"
    assert runtime.artifacts.read(outside.ref) == outside_raw
    assert not runtime.artifacts.cas.path_for(exclusive.sha256).exists()
    assert service.archived_model(target).artifacts.read(exclusive.ref) == b"exact exclusive original"

    restore = service.restore_preview(target)
    assert restore["ready"], restore
    assert service.restore(target, restore["fingerprint"])["storage_state"] == "restored"
    assert run_fingerprint(runtime, "run_smallhistory") == before_target
    assert run_fingerprint(runtime, "run_largehistory") == before_other
    assert runtime.scheduler_bindings.get_instance(instance_id=other) == other_instance
    assert runtime.scheduler_bindings.instance_bindings(instance=other) == other_bindings
    assert runtime.artifacts.read(outside.ref) == outside_raw
    assert (workspace / "original.txt").read_bytes() == b"original workspace bytes"
    assert runtime.artifacts.read(exclusive.ref) == b"exact exclusive original"


def test_oversized_foreign_control_carrier_keeps_target_copies_with_explicit_gap(scale_system):
    runtime, service, target, other = scale_system
    envelope = register(runtime, target, "scale.uncertain", b"retained original")
    historical_run(runtime, other, "run_oversizedcarrier")
    with sqlite3.connect(runtime.runs.database_path) as connection:
        connection.execute("INSERT INTO run_activity(run_id,activity,recorded_at,diagnostic_json) "
                           "VALUES ('run_oversizedcarrier','tool_failed','2000-01-01T00:00:00+00:00',zeroblob(?))",
                           (17 * 1024 * 1024,))
    before = run_fingerprint(runtime, "run_oversizedcarrier")
    preview = service.preview(target)
    assert preview["ready"], preview
    gap = next(item for item in preview["gaps"] if item["code"] == "retained_control_scan_incomplete")
    assert gap["retention"] == "all_target_artifacts"
    assert gap["count"] >= 1
    assert preview["counts"]["shared_bytes"] == len(b"retained original")
    service.archive(target, preview["fingerprint"])
    assert runtime.artifacts.read(envelope.ref) == b"retained original"
    assert service.archived_model(target).artifacts.read(envelope.ref) == b"retained original"
    restore = service.restore_preview(target)
    assert restore["ready"], restore
    service.restore(target, restore["fingerprint"])
    assert run_fingerprint(runtime, "run_oversizedcarrier") == before


def test_target_inventory_keeps_its_own_explicit_budget(scale_system):
    runtime, service, target, other = scale_system
    historical_run(runtime, target, "run_targettoolarge")
    with sqlite3.connect(runtime.runs.database_path) as connection:
        connection.execute("UPDATE runs SET instruction=zeroblob(?) WHERE run_id='run_targettoolarge'",
                           (33 * 1024 * 1024,))
    preview = service.preview(target)
    assert not preview["ready"]
    assert any("target control inventory exceeds bounded record budget" in item.get("detail", "")
               for item in preview["unsupported"])
    # An instance with no artifact closure has no retention scan to perform.
    other_preview = service.preview(other)
    assert other_preview["ready"], other_preview
