"""Policy boundaries belong here; solver/installer flows are not duplicated."""
import json

import pytest
from pydantic import ValidationError

from tcad_artifact.execution_policy import ExecutionPolicySnapshot
from tests.operations.tcad_policy_fixtures import policy_fields, policy_snapshot


@pytest.mark.parametrize("storage,wall,outcome", [
    (2_000_000_000, 3600, "policy"),
    (1_999_999_999, 3599, "policy"),
    (2_000_000_001, 3600, "require_human_approval"),
    (2_000_000_000, 3601, "require_human_approval"),
])
def test_inclusive_administrator_allowance(storage, wall, outcome):
    result = policy_snapshot().admission(
        budget={"max_storage_bytes": storage, "wall_time_seconds": wall}, budget_key="a" * 64)
    assert result.outcome == outcome
    assert result.budget == {"max_storage_bytes": storage, "wall_time_seconds": wall}


def test_policy_change_and_disabled_authority_are_explicit():
    original = policy_snapshot()
    fields = policy_fields()
    fields["agent_execution_policy"].update(enabled=False, outside_limits="deny")
    changed = ExecutionPolicySnapshot.model_validate_json(json.dumps(fields), strict=True)
    budget = {"max_storage_bytes": 1024, "wall_time_seconds": 1}
    before = original.admission(budget=budget, budget_key="b" * 64)
    after = changed.admission(budget=budget, budget_key="b" * 64)
    assert before.outcome == "policy" and after.outcome == "deny"
    assert before.policy_digest != after.policy_digest


def test_missing_policy_and_unsupported_transfer_are_rejected():
    fields = policy_fields()
    fields.pop("agent_execution_policy")
    with pytest.raises(ValidationError):
        ExecutionPolicySnapshot.model_validate_json(json.dumps(fields), strict=True)
    fields = policy_fields()
    fields["runner"]["max_transfer_bytes"] = 512
    policy = ExecutionPolicySnapshot.model_validate_json(json.dumps(fields), strict=True)
    with pytest.raises(ValueError, match="transfer capability"):
        policy.admission(budget={"max_storage_bytes": 1024, "wall_time_seconds": 1},
            budget_key="c" * 64)


def test_revision_reservations_share_remaining_subject_allowance():
    """Actual terminal usage releases only unused reservations for the same subject."""
    import sqlite3
    from scidiscovery.artifact_agent.service.executions import ExecutionService, ExecutionApprovalError
    service = object.__new__(ExecutionService)
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript('''
        CREATE TABLE execution_budget_pools (executor TEXT, budget_key TEXT, allowance_json BLOB, PRIMARY KEY(executor,budget_key));
        CREATE TABLE execution_budget_reservations (execution_id TEXT PRIMARY KEY, executor TEXT, budget_key TEXT, reserved_json BLOB, consumed_json BLOB);
    ''')
    first = policy_snapshot().admission(budget={"max_storage_bytes": 1000, "wall_time_seconds": 3000}, budget_key="a"*64)
    service._reserve_budget(connection, "revision-one", "tcad", first)
    remaining = service._budget_remaining(connection, "tcad", first)
    assert remaining["wall_time_seconds"] == 600
    second = first.model_copy(update={"budget": {"max_storage_bytes": 1000, "wall_time_seconds": 1000}})
    with pytest.raises(ExecutionApprovalError, match="cumulative"):
        service._reserve_budget(connection, "revision-two", "tcad", second)
    connection.execute("UPDATE execution_budget_reservations SET consumed_json=? WHERE execution_id=?",
        (json.dumps({"max_storage_bytes": 100, "wall_time_seconds": 200}), "revision-one"))
    service._reserve_budget(connection, "revision-two", "tcad", second)
    assert service._budget_remaining(connection, "tcad", second)["wall_time_seconds"] == 2400
    # Tightening applies to the remaining pool; it does not reset prior usage.
    tighter = second.model_copy(update={"allowance": {"max_storage_bytes": 2_000_000_000, "wall_time_seconds": 1800}})
    assert service._budget_remaining(connection, "tcad", tighter)["wall_time_seconds"] == 600
    connection.close()


def test_project_revisions_resolve_one_scientific_budget_owner():
    from types import SimpleNamespace
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    from scidiscovery.artifact_agent.service.executions import ExecutionService
    def ref(name, schema):
        import hashlib
        return ArtifactRef(artifact_id=name, sha256=hashlib.sha256(name.encode()).hexdigest(), kind="fixture", schema_id=schema)
    skeleton = ref("subject", "subject.v1")
    first, second = ref("project-one", "project.v1"), ref("project-two", "project.v1")
    graph = {skeleton: (), first: (skeleton,), second: (first, skeleton)}
    service = object.__new__(ExecutionService)
    service.artifacts = SimpleNamespace(catalog=lambda value: SimpleNamespace(schema_id=value.schema_id, parent_refs=graph[value]))
    assert service.scientific_budget_owner(first, ("subject.v1",)) == service.scientific_budget_owner(second, ("subject.v1",))


def test_large_file_admission_reads_metadata_without_allocating_payload():
    from types import SimpleNamespace
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    from scidiscovery.operations.input_validation import read_validation_sources
    ref = ArtifactRef(artifact_id="grid", sha256="a"*64, kind="mesh", schema_id="opaque")
    item = SimpleNamespace(exposure="file_reference", source_name="device_grid", port_name="device_grid",
        artifact=SimpleNamespace(ref=ref, size_bytes=2_000_000_000, media_type="application/octet-stream",
            labels=(), parent_refs=(), producer_run_id=None))
    def forbidden_read(_):
        raise AssertionError("file reference must not enter the byte reader")
    compiled = SimpleNamespace(spec=SimpleNamespace(limits=SimpleNamespace(max_input_bytes=64)))
    sources = read_validation_sources(compiled, (item,), forbidden_read)
    assert sources["device_grid"] == b""
    assert sources.binding_descriptors["device_grid"].size_bytes == 2_000_000_000


def test_solver_log_is_counted_and_stdout_collision_preserves_original(tmp_path):
    import hashlib
    from tcad_artifact import remote_runner_py36 as runner
    work = tmp_path / "work"
    work.mkdir()
    genuine = work / "main.log"
    genuine.write_bytes(b"real solver log")
    stdout = tmp_path / "worker.log"
    stdout.write_bytes(b"stdout")
    expected = ({"relative_path": "main.log", "capture": "process_log"},)
    assert runner._logical_storage_bytes(tmp_path, (), expected) >= genuine.stat().st_size + stdout.stat().st_size
    with pytest.raises(RuntimeError, match="conflicts"):
        runner._publish_log_mirror(stdout, genuine, hashlib.sha256(b"stdout").hexdigest(), 6, 1024)
    assert genuine.read_bytes() == b"real solver log"
    assert stdout.read_bytes() == b"stdout"


def test_initialization_collection_consumes_its_frozen_limits(tmp_path):
    import hashlib
    from types import SimpleNamespace
    from scidiscovery.artifact_agent.schema.execution import LocalFileDescriptor
    from tcad_artifact.debug_adapter import TCADDevelopmentDebugBridge
    def descriptor(name, raw, media):
        path = tmp_path / name
        path.write_bytes(raw)
        return LocalFileDescriptor(name=name, local_path=str(path), media_type=media,
            size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    descriptors = (
        descriptor("tcad_log", b"complete", "text/plain"),
        descriptor("tcad_manifest", b'{"terminal_state":"succeeded","exit_code":0,"error":""}', "application/json"),
        descriptor("snapshot", b"x" * (9*1024*1024), "application/octet-stream"),
    )
    bridge = TCADDevelopmentDebugBridge(SimpleNamespace(execution_policy=policy_snapshot))
    limits = {**policy_fields()["debug"], "max_output_bytes": 12*1024*1024, "max_output_file_bytes": 10*1024*1024}
    result = bridge._collected_run(descriptors, limits=limits)
    assert any(len(item.content) == 9*1024*1024 for item in result.files)
    from tcad_artifact.project_packager import AttemptFile
    assert len(AttemptFile(relative_path="reports/snapshot", content="x"*(9*1024*1024)).raw_bytes()) == 9*1024*1024
    with pytest.raises(ValueError):
        bridge._collected_run(descriptors, limits={**limits, "max_output_bytes": 8*1024*1024})


def _reauthorization_service(tmp_path):
    from types import SimpleNamespace
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    from scidiscovery.artifact_agent.service.executions import ExecutionService
    ref = ArtifactRef(artifact_id="subject", sha256="a"*64, kind="fixture", schema_id="fixture.v1")
    identity = SimpleNamespace(model_dump=lambda **_: {"operation": "fixture"})
    service = ExecutionService(artifacts=SimpleNamespace(read=lambda _: b"{}",
        catalog=lambda _: SimpleNamespace(media_type="application/json")), approvals=None,
        database_path=tmp_path / "executions.sqlite", exchange_root=tmp_path / "exchange", service_actor=None)
    service.request = lambda _: SimpleNamespace(compiled_identity=identity, executor="tcad")
    service.approval_subject_refs = lambda _: (ref, ref)
    with service._connect() as connection:
        connection.execute("INSERT INTO executions (execution_id,executor,request_ref_json,payload_ref_json,state,created_at) VALUES ('one','tcad','{}','{}','created','fixture')")
    return service, identity


def test_tightened_policy_reauthorizes_unstarted_request_without_double_reservation(tmp_path):
    service, identity = _reauthorization_service(tmp_path)
    budget = {"max_storage_bytes": 1000, "wall_time_seconds": 1000}
    old = policy_snapshot().admission(budget=budget, budget_key="a"*64)
    service.authorize_policy(execution_id="one", admission=old, compiled_identity=identity)
    fields = policy_fields()
    fields["agent_execution_policy"]["max_wall_time_seconds"] = 1800
    new = ExecutionPolicySnapshot.model_validate_json(json.dumps(fields), strict=True).admission(budget=budget, budget_key="a"*64)
    service.authorize_policy(execution_id="one", admission=new, compiled_identity=identity)
    with service._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM execution_policy_authorizations").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM execution_budget_reservations").fetchone()[0] == 1
        assert service._budget_remaining(connection, "tcad", new)["wall_time_seconds"] == 800
    assert service.authorization("one")["policy_digest"] == new.policy_digest


@pytest.mark.parametrize("prepared", [False, True])
def test_policy_deferral_releases_only_never_prepared_reservation(tmp_path, prepared):
    service, identity = _reauthorization_service(tmp_path)
    admission = policy_snapshot().admission(budget={"max_storage_bytes": 1000, "wall_time_seconds": 1000}, budget_key="a"*64)
    descriptor = service.authorize_policy(execution_id="one", admission=admission, compiled_identity=identity)
    if prepared:
        service.record_prepared_submission("one", descriptor, policy_digest=admission.policy_digest)
    fields = policy_fields()
    fields["agent_execution_policy"].update(enabled=False, outside_limits="deny")
    denied = ExecutionPolicySnapshot.model_validate_json(json.dumps(fields), strict=True).admission(budget=admission.budget, budget_key=admission.budget_key)
    service.defer_policy(execution_id="one", admission=denied)
    with service._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM execution_budget_reservations").fetchone()[0] == int(prepared)
        assert connection.execute("SELECT COUNT(*) FROM execution_policy_authorizations").fetchone()[0] == 2
    assert service.authorization("one")["outcome"] == "deny"
    assert (service.prepared_submission("one") is not None) == prepared
