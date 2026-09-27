"""Storage maintenance fences real writer boundaries without science changes."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from scidiscovery.artifact_agent.service.instance_maintenance import (
    InstanceMaintenance, InstanceMaintenanceBusy, InstanceMaintenanceUnavailable,
    backend_writer_guards,
)


def freeze(gate, instance="one", job="job", action="archive"):
    with gate.exclusive(instance):
        gate.begin(instance, job, action)


def unfreeze(gate, instance="one", job="job"):
    with gate.exclusive(instance):
        gate.finish(instance, job)


def test_durable_owner_survives_restart_and_only_blocks_target(tmp_path):
    gate = InstanceMaintenance(tmp_path)
    freeze(gate)
    restarted = InstanceMaintenance(tmp_path)
    assert restarted.status("one") == {"instance_id": "one", "job_id": "job", "action": "archive"}
    with pytest.raises(InstanceMaintenanceUnavailable):
        with restarted.guard("one"):
            pytest.fail("maintenance admitted a writer")
    with restarted.guard("two"):
        assert restarted.status("two") is None
    with restarted.exclusive("one"):
        with pytest.raises(InstanceMaintenanceBusy):
            restarted.finish("one", "wrong-job")
        with pytest.raises(InstanceMaintenanceBusy):
            restarted.begin("one", "new-job", "restore")
    unfreeze(restarted)
    with gate.guard("one"):
        assert gate.status("one") is None


def test_marker_requires_exclusive_and_corruption_fails_closed(tmp_path):
    gate = InstanceMaintenance(tmp_path)
    with pytest.raises(InstanceMaintenanceBusy):
        gate.begin("one", "job", "archive")
    freeze(gate)
    gate._marker("one").write_text("broken marker")
    with pytest.raises(InstanceMaintenanceUnavailable, match="stays blocked"):
        gate.ensure_available("one")


def test_handoff_replaces_exact_owner_without_unblocking_instance(tmp_path):
    gate = InstanceMaintenance(tmp_path)
    freeze(gate)
    with pytest.raises(InstanceMaintenanceBusy):
        gate.handoff("one", "job", "restore-job", "restore")
    with gate.exclusive("one"):
        with pytest.raises(InstanceMaintenanceBusy):
            gate.handoff("one", "another-job", "restore-job", "restore")
        value = gate.handoff("one", "job", "restore-job", "restore")
        assert value == {"instance_id": "one", "job_id": "restore-job", "action": "restore"}
        with pytest.raises(InstanceMaintenanceBusy):
            gate.finish("one", "job")
    with pytest.raises(InstanceMaintenanceUnavailable):
        InstanceMaintenance(tmp_path).ensure_available("one")


@pytest.mark.parametrize("failure", ["before_replace", "after_replace"])
def test_interrupted_handoff_always_retains_a_durable_marker(tmp_path, monkeypatch, failure):
    gate = InstanceMaintenance(tmp_path)
    freeze(gate)
    replace = os.replace

    def interrupted_replace(source, destination):
        assert gate.status("one")["job_id"] == "job"
        assert Path(destination).is_file()
        if failure == "before_replace":
            raise OSError("injected before replacement")
        replace(source, destination)
        assert gate.status("one")["job_id"] == "restore-job"

    monkeypatch.setattr(os, "replace", interrupted_replace)
    if failure == "after_replace":
        monkeypatch.setattr(gate, "_sync_markers", lambda: (_ for _ in ()).throw(OSError("injected after replacement")))
    with gate.exclusive("one"), pytest.raises(OSError, match="injected"):
        gate.handoff("one", "job", "restore-job", "restore")
    restarted = InstanceMaintenance(tmp_path)
    assert restarted.status("one")["job_id"] == ("job" if failure == "before_replace" else "restore-job")
    with pytest.raises(InstanceMaintenanceUnavailable):
        restarted.ensure_available("one")


def test_reentrant_shared_guards_never_upgrade_or_release_outer_guard(tmp_path):
    first, second = InstanceMaintenance(tmp_path), InstanceMaintenance(tmp_path)
    with first.global_guard(), first.guard("one"):
        with second.global_guard(), second.guard("one"):
            with pytest.raises(InstanceMaintenanceBusy, match="upgrade"):
                second.exclusive("one").__enter__()
        with pytest.raises(InstanceMaintenanceBusy):
            with second.exclusive("two"):
                pytest.fail("nested scope released the outer guard")
    with second.exclusive("one"):
        second.begin("one", "job", "archive")


def test_transferred_and_inherited_writer_ownership_outlives_request(tmp_path):
    gate = InstanceMaintenance(tmp_path)
    with gate.global_guard():
        lease = gate.acquire_writer("one")
    inherited = tuple(os.dup(descriptor) for descriptor in lease.descriptors)
    lease.close()
    try:
        with pytest.raises(InstanceMaintenanceBusy):
            with gate.exclusive("one"):
                pytest.fail("inherited supervisor ownership was released")
    finally:
        for descriptor in inherited:
            os.close(descriptor)
    with gate.exclusive("one"):
        gate.begin("one", "job", "archive")


def _activities(runs, run_id):
    with runs._connect() as connection:
        return tuple(tuple(row) for row in connection.execute(
            "SELECT * FROM run_activity WHERE run_id = ? ORDER BY rowid", (run_id,)))


def _running_system(tmp_path):
    from tests.operations.test_l2_run_invariants import _system, _invoke, _worker
    catalog, runtime, _, _, root = _system(tmp_path)
    _invoke(root, "activity_ids")
    worker = _worker(catalog, runtime)
    worker.call_tool("worker_open_assignment", {})
    return runtime.runs, worker._run_id


def test_all_activity_writers_preserve_deleted_event_id_high_water(tmp_path, monkeypatch):
    runs, run_id = _running_system(tmp_path)
    monkeypatch.setattr(runs, "_finish_failed_workspace", lambda value: value)
    saved = {}

    def failure():
        value = runs.status(run_id)
        runs.record_failure(run_id, reason="fixture failure", expected_state="running",
            expected_last_activity_at=value.last_activity_at)

    actions = (
        lambda: saved.update(attempt=runs.begin_tool_attempt(run_id, SimpleNamespace(name="fixture_tool"), {})),
        lambda: runs.record_tool_attempt_read(run_id, saved["attempt"], {}),
        lambda: runs.finish_tool_attempt(run_id, saved["attempt"], sources={}, result_status="computed", response={}),
        lambda: runs.tool_io_budget(run_id, used_bytes=1, used_seconds=.001),
        lambda: runs.record_activity(run_id, "fixture_activity"),
        lambda: runs.record_tool_observation(run_id, "tool_call_completed", {"call_key": "fixture"}),
        failure,
    )
    for write in actions:
        # A different archived event occupied the last ID. Every real write
        # path must exceed it even when that row is no longer visible.
        runs.record_tool_observation(run_id, "archived_tail", {})
        with runs._connect() as connection:
            removed = connection.execute("SELECT MAX(rowid) FROM run_activity").fetchone()[0]
            connection.execute("DELETE FROM run_activity WHERE rowid = ?", (removed,))
        write()
        with runs._connect() as connection:
            newest = connection.execute("SELECT MAX(rowid) FROM run_activity").fetchone()[0]
            high_water = connection.execute("SELECT high_water FROM run_activity_sequence WHERE slot=1").fetchone()[0]
        assert newest > removed and newest == high_water


def test_activity_allocator_seeds_legacy_rows_never_decreases_and_rolls_back_atomically(tmp_path):
    runs, run_id = _running_system(tmp_path)
    with runs._connect() as connection:
        connection.execute("INSERT INTO run_activity(rowid,run_id,activity,recorded_at) VALUES(10000,?,'legacy','2020-01-01')", (run_id,))
    runs._initialize()
    with runs._connect() as connection:
        assert connection.execute("SELECT high_water FROM run_activity_sequence").fetchone()[0] == 10000
        connection.execute("DELETE FROM run_activity WHERE rowid=10000")
    runs._initialize()
    before = _activities(runs, run_id)
    with pytest.raises(RuntimeError, match="rollback"):
        with runs._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            assert runs._append_activity(connection, run_id, "not_committed", "2020-01-01", None) == 10001
            raise RuntimeError("rollback caller transaction")
    assert _activities(runs, run_id) == before
    with runs._connect() as connection:
        assert connection.execute("SELECT high_water FROM run_activity_sequence").fetchone()[0] == 10000
    runs.record_tool_observation(run_id, "committed", {})
    with runs._connect() as connection:
        assert connection.execute("SELECT MAX(rowid) FROM run_activity").fetchone()[0] == 10001


def test_worker_rejection_has_no_run_timing_error_or_state_writes(tmp_path, monkeypatch):
    from tests.operations.test_l2_run_invariants import _system, _invoke, _worker
    catalog, runtime, instance, _, root = _system(tmp_path)
    _invoke(root, "first")
    worker = _worker(catalog, runtime)
    worker.call_tool("worker_open_assignment", {})
    run_id = worker._run_id
    before = runtime.runs.status(run_id), _activities(runtime.runs, run_id)
    monkeypatch.setattr(worker, "_engineering_failure", lambda *_: pytest.fail("maintenance recorded an engineering failure"))
    freeze(runtime.instance_maintenance, instance.instance_id)
    with pytest.raises(InstanceMaintenanceUnavailable):
        worker.call_tool("worker_heartbeat", {})
    assert (runtime.runs.status(run_id), _activities(runtime.runs, run_id)) == before


def test_reused_agent_open_checks_new_assignment_not_its_cached_instance(tmp_path):
    from tests.operations.test_l2_run_invariants import _system, _invoke, _worker
    catalog, runtime, first, source, root = _system(tmp_path)
    _invoke(root, "old")
    worker = _worker(catalog, runtime)
    worker.call_tool("worker_open_assignment", {})
    old_id = worker._run_id
    with runtime.runs._connect() as connection:
        connection.execute("UPDATE runs SET state = 'completed' WHERE run_id = ?", (old_id,))
    second = runtime.scheduler_bindings.create_instance(name="second", title="Second", objective="Separate test")
    runtime.scheduler_bindings.bind(instance=second.instance_id, namespace="artifact", name="source_csv", object_id=source.artifact_id)
    root.facade.instance = second.instance_id
    _invoke(root, "new")
    new_id = runtime.scheduler_bindings.resolve(instance=second.instance_id, namespace="run", name="new")
    before_old, before_new = _activities(runtime.runs, old_id), _activities(runtime.runs, new_id)
    freeze(runtime.instance_maintenance, second.instance_id)
    with pytest.raises(InstanceMaintenanceUnavailable):
        worker.call_tool("worker_open_assignment", {})
    assert _activities(runtime.runs, old_id) == before_old
    assert _activities(runtime.runs, new_id) == before_new
    assert runtime.runs.status(new_id).state == "queued"
    unfreeze(runtime.instance_maintenance, second.instance_id)
    freeze(runtime.instance_maintenance, first.instance_id)
    assert worker.call_tool("worker_open_assignment", {})["state"] == "opened"
    assert worker._run_id == new_id
    assert _activities(runtime.runs, old_id) == before_old


def _hardened_system(tmp_path):
    from tests.operations.test_l5_hardened_run_backend import _system
    from blind_csv_plugin.plugin import PLUGIN
    # This test exercises transport finalization only. The default Blind CSV
    # reviewer requires a native shell and is correctly unavailable hardened.
    author, reviewer = PLUGIN.operations
    native = reviewer.executor.native_tools.model_copy(update={"shell": "none"})
    reviewer = reviewer.model_copy(update={"executor": reviewer.executor.model_copy(update={"native_tools": native})})
    fixture = PLUGIN.model_copy(update={"operations": (author, reviewer)})
    return _system(tmp_path, blind_plugin=fixture)


def test_hardened_final_timing_and_transport_release_still_hold_gate(tmp_path, monkeypatch):
    from tests.operations.test_l5_hardened_run_backend import _invoke, _worker
    _, runtime, instance, root = _hardened_system(tmp_path)
    _invoke(root)
    worker = _worker(runtime.runs.operation_catalog, runtime)
    worker.call_tool("worker_open_assignment", {})
    calls = []
    observe = runtime.runs.record_tool_observation
    release = runtime.runs.backend.release_transport

    def still_owned(label):
        with pytest.raises(InstanceMaintenanceBusy):
            with runtime.instance_maintenance.exclusive(instance.instance_id):
                pytest.fail("outer Worker ownership ended before finalization")
        calls.append(label)

    def observation(*args, **kwargs):
        still_owned("timing")
        return observe(*args, **kwargs)

    def release_transport(*args, **kwargs):
        still_owned("release")
        return release(*args, **kwargs)

    monkeypatch.setattr(runtime.runs, "record_tool_observation", observation)
    monkeypatch.setattr(runtime.runs.backend, "release_transport", release_transport)
    monkeypatch.setattr(worker, "_call_tool", lambda *_: {"state": "completed"})
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    assert "timing" in calls and calls[-1] == "release"


def test_root_cached_instance_is_rechecked_before_any_route_or_diagnostic(tmp_path, monkeypatch):
    from tests.operations.test_l2_run_invariants import _system
    from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerInstanceClosed
    _, runtime, instance, _, root = _system(tmp_path)
    runtime.scheduler_bindings.close_instance(instance_id=instance.instance_id)
    assert root.call_tool("operation_catalog", {"scope": "all"})["operations"]
    assert root.call_tool("instance_list", {"state": "closed"})["instances"][0]["state"] == "closed"
    monkeypatch.setattr(root, "_call_tool", lambda *_: pytest.fail("closed cached instance reached a write route"))
    with pytest.raises(SchedulerInstanceClosed):
        root.call_tool("artifact_ingest_text", {"name": "late", "text": "late"})


@pytest.mark.parametrize("backend", ["local", "hardened"])
def test_invalid_open_after_maintenance_never_touches_cached_run_or_transport(tmp_path, monkeypatch, backend):
    from scidiscovery.artifact_agent.interfaces.mcp_worker_protocol import WorkerToolError
    if backend == "local":
        from tests.operations.test_l2_run_invariants import _system, _invoke, _worker
        catalog, runtime, instance, _, root = _system(tmp_path)
        _invoke(root, "old")
    else:
        from tests.operations.test_l5_hardened_run_backend import _invoke, _worker
        catalog, runtime, instance, root = _hardened_system(tmp_path)
        _invoke(root)
    worker = _worker(catalog, runtime)
    worker.call_tool("worker_open_assignment", {})
    run_id = worker._run_id
    before = runtime.runs.status(run_id), _activities(runtime.runs, run_id)
    files = tuple(sorted(str(path.relative_to(worker._workspace.root)) for path in worker._workspace.root.rglob("*")))
    freeze(runtime.instance_maintenance, instance.instance_id)
    monkeypatch.setattr(worker, "_engineering_failure", lambda *_: pytest.fail("invalid open wrote an engineering record"))
    if backend == "hardened":
        monkeypatch.setattr(runtime.runs.backend, "transport_guard", lambda *_args, **_kwargs: pytest.fail("invalid open touched cached transport"))
    with pytest.raises(WorkerToolError, match="arguments"):
        worker.call_tool("worker_open_assignment", {"unexpected": True})
    assert (runtime.runs.status(run_id), _activities(runtime.runs, run_id)) == before
    assert tuple(sorted(str(path.relative_to(worker._workspace.root)) for path in worker._workspace.root.rglob("*"))) == files


def test_late_hardened_open_rejects_before_old_expired_transport(tmp_path, monkeypatch):
    from tests.operations.test_l5_hardened_run_backend import _invoke, _worker
    catalog, runtime, instance, root = _hardened_system(tmp_path)
    _invoke(root)
    worker = _worker(catalog, runtime)
    worker.call_tool("worker_open_assignment", {})
    run_id = worker._run_id
    with runtime.runs.backend._connect_dispatch() as connection:
        connection.execute("UPDATE active_transport SET lease_deadline_at = ? WHERE run_id = ?", ("2000-01-01T00:00:00+00:00", run_id))
    before = runtime.runs.status(run_id), _activities(runtime.runs, run_id)
    freeze(runtime.instance_maintenance, instance.instance_id)
    monkeypatch.setattr(worker, "_engineering_failure", lambda *_: pytest.fail("maintenance wrote an old transport error"))
    monkeypatch.setattr(runtime.runs.backend, "transport_guard", lambda *_args, **_kwargs: pytest.fail("late open reached expired transport"))
    with pytest.raises(InstanceMaintenanceUnavailable):
        worker.call_tool("worker_open_assignment", {})
    assert (runtime.runs.status(run_id), _activities(runtime.runs, run_id)) == before


def test_open_failure_before_selection_does_not_inherit_cached_run(tmp_path):
    from tests.operations.test_l2_run_invariants import _system, _invoke, _worker
    from scidiscovery.artifact_agent.interfaces.mcp_worker_protocol import WorkerToolError
    catalog, runtime, instance, _, root = _system(tmp_path)
    _invoke(root, "old")
    worker = _worker(catalog, runtime)
    worker.call_tool("worker_open_assignment", {})
    run_id = worker._run_id
    before = runtime.runs.status(run_id), _activities(runtime.runs, run_id)
    freeze(runtime.instance_maintenance, instance.instance_id)
    worker._missing_services = ("fixture_missing_service",)
    with pytest.raises(WorkerToolError) as caught:
        worker.call_tool("worker_open_assignment", {})
    assert "workspace_report" not in caught.value.engineering
    assert (runtime.runs.status(run_id), _activities(runtime.runs, run_id)) == before


def _backend_runtime(tmp_path, *, hardened=True, state="completed", pending=False):
    from scidiscovery.artifact_agent.service.hardened_workspace import HardenedWorkerBackend
    from scidiscovery.artifact_agent.service.local_workspace import LocalTrustedBackend
    backend = (HardenedWorkerBackend if hardened else LocalTrustedBackend)(tmp_path / "workspace-root")
    run_id = "run_" + "a" * 32
    workspace = backend.prepare(run_id=run_id, inputs=(), assignment=b"{}", result_schema=b"{}")
    value = SimpleNamespace(run_id=run_id, state=state, backend_id=backend.backend_id,
        backend_version=backend.backend_version, backend_capabilities=backend.capabilities,
        recovery_draft={"recovery_pending": True, "code": "writers_unconfirmed"} if pending else None)
    runtime = SimpleNamespace(state_root=tmp_path, runs=SimpleNamespace(backend=backend, status=lambda _: value), executions=None)
    return runtime, value, workspace


@pytest.mark.parametrize("finished", [False, True])
def test_local_native_history_stays_unknown_even_with_stopped_launcher(tmp_path, finished):
    runtime, value, workspace = _backend_runtime(tmp_path, hardened=False, state="failed", pending=True)
    if finished:
        directory = workspace.root / "scratch/.analysis-process"
        directory.mkdir(parents=True)
        (directory / "latest.json").write_text(json.dumps({"state": "finished", "process_group_stopped": True}))
        (directory / "lock").touch()
    before = value.recovery_draft.copy()
    with pytest.raises(InstanceMaintenanceBusy) as caught:
        with backend_writer_guards(runtime, (value.run_id,), ()):
            pytest.fail("legacy native writer was assumed quiescent")
    assert any(item["reason"] == "native_writers_unconfirmed" for item in caught.value.details)
    assert value.recovery_draft == before and workspace.root.is_dir()


@pytest.mark.parametrize("lease", ["active", "expired", "missing"])
def test_hardened_quiescence_requires_terminal_identity_lock_and_inactive_lease(tmp_path, lease):
    runtime, value, workspace = _backend_runtime(tmp_path)
    backend = runtime.runs.backend
    with backend._run_transport_lock(value.run_id):
        pass
    if lease != "missing":
        deadline = datetime.now(timezone.utc) + timedelta(seconds=300 if lease == "active" else -300)
        with backend._connect_dispatch() as connection:
            connection.execute("INSERT INTO active_transport VALUES (?, ?, ?)", (value.run_id, "original-owner", deadline.isoformat()))
    before = backend.dispatch_database.read_bytes()
    if lease == "active":
        with pytest.raises(InstanceMaintenanceBusy):
            with backend_writer_guards(runtime, (value.run_id,), ()):
                pytest.fail("active lease was ignored")
    else:
        with backend_writer_guards(runtime, (value.run_id,), ()) as proof:
            assert proof["quiescent"]
            with pytest.raises(BlockingIOError):
                with backend._run_transport_lock(value.run_id, blocking=False):
                    pytest.fail("transport lock was not held")
    assert backend.dispatch_database.read_bytes() == before
    assert backend.exact_workspace_paths(value.run_id) == (workspace.root,)


def test_missing_hardened_transport_lock_does_not_create_a_quiescence_record(tmp_path):
    runtime, value, _ = _backend_runtime(tmp_path)
    before = tuple(runtime.runs.backend.transport_lock_root.iterdir())
    with pytest.raises(InstanceMaintenanceBusy):
        with backend_writer_guards(runtime, (value.run_id,), ()):
            pytest.fail("missing transport lock was treated as held")
    assert tuple(runtime.runs.backend.transport_lock_root.iterdir()) == before


def test_backend_identity_change_does_not_renew_historical_quiescence(tmp_path):
    runtime, value, _ = _backend_runtime(tmp_path)
    value.backend_version = "retired"
    with pytest.raises(InstanceMaintenanceBusy) as caught:
        with backend_writer_guards(runtime, (value.run_id,), ()):
            pytest.fail("current backend reinterpreted old writer identity")
    assert caught.value.details[0]["reason"] == "backend_identity_unavailable"


def _collection(tmp_path):
    from scidiscovery.artifact_agent.schema.refs import ActorRef
    from scidiscovery.artifact_agent.service.execution_collection import ExecutionCollection
    gate = InstanceMaintenance(tmp_path)
    owner = SimpleNamespace(instance_id="one")
    bindings = SimpleNamespace(find_owner=lambda **_: (owner, None), require_active_instance=lambda **_: owner)
    status = SimpleNamespace(state="succeeded")
    executions = SimpleNamespace(database_path=tmp_path / "database/executions.sqlite3",
        exchange_root=tmp_path / "exchange", service_actor=ActorRef(actor_id="fixture", actor_type="service"),
        status=lambda _: status, instance_maintenance=gate, scheduler_bindings=bindings)
    return ExecutionCollection(executions, plugin_configs={}), gate, status


def test_collection_uses_binding_owner_instead_of_diagnostic_scope(tmp_path, monkeypatch):
    collection, gate, _ = _collection(tmp_path)
    def observed(_execution_id, *, scope, total_seconds, file_timeout_seconds, idle_timeout_seconds, maintenance_lease):
        assert len(maintenance_lease.descriptors) == 2
        return {"scope": scope, "accepted": False}
    monkeypatch.setattr(collection, "_collect_owned", observed)
    assert collection.collect("execution", scope="fixture")["scope"] == "instance:one"
    assert collection.collect("execution", scope="instance:two")["scope"] == "instance:one"
    freeze(gate)
    with pytest.raises(InstanceMaintenanceUnavailable):
        collection.collect("execution", scope="fixture")
    assert not collection.executions.exchange_root.exists()


def test_unowned_legacy_collection_keeps_transferable_global_guard_without_inventing_owner(tmp_path, monkeypatch):
    collection, gate, _ = _collection(tmp_path)
    collection.executions.scheduler_bindings.find_owner = lambda **_: None
    collection.executions.scheduler_bindings.require_active_instance = lambda **_: pytest.fail("unowned execution acquired an invented owner")
    freeze(gate)
    def observed(_execution_id, *, scope, total_seconds, file_timeout_seconds, idle_timeout_seconds, maintenance_lease):
        assert scope == "fixture" and len(maintenance_lease.descriptors) == 1
        with pytest.raises(InstanceMaintenanceBusy):
            with gate.exclusive("two"):
                pytest.fail("legacy collection had no global writer protection")
        return {"accepted": False}
    monkeypatch.setattr(collection, "_collect_owned", observed)
    assert collection.collect("execution", scope="fixture") == {"accepted": False}
    assert not collection.executions.exchange_root.exists()


def test_collection_holds_gate_through_collected_status_final_logs_and_unlock(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.service import execution_collection as module
    collection, gate, status = _collection(tmp_path)
    inherited = []

    class FinishedProcess:
        pid = 987654
        returncode = 0

        def __init__(self, *_, **kwargs):
            assert len(kwargs["pass_fds"]) == 5
            inherited.extend(os.dup(fd) for fd in kwargs["pass_fds"][-2:])
            for name in ("stdout", "stderr"):
                reader, writer = os.pipe()
                os.close(writer)
                setattr(self, name, os.fdopen(reader, "rb"))

        def poll(self):
            return 0

        def wait(self, **_):
            return 0

    monkeypatch.setattr(module.subprocess, "Popen", FinishedProcess)
    monkeypatch.setattr(module.threading.Thread, "start", lambda _: None)
    monkeypatch.setattr(module, "_group_running", lambda _: False)
    assert collection.collect("execution", scope="instance:one")["accepted"]
    status.state = "collected"
    active = collection._active
    with pytest.raises(InstanceMaintenanceBusy):
        with gate.exclusive("one"):
            pytest.fail("collected state prematurely released supervision")
    opened = []
    original_open = os.open

    def observed_open(path, *args, **kwargs):
        if str(path).endswith(("process.stdout.log", "process.stderr.log")):
            with pytest.raises(InstanceMaintenanceBusy):
                with gate.exclusive("one"):
                    pytest.fail("final log write lost maintenance ownership")
            opened.append(Path(path).name)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(os, "open", observed_open)
    try:
        collection._watch(active, "instance:one")
        assert collection._active is None and len(opened) == 2
        # A surviving child guard still owns the inherited shared descriptors.
        with pytest.raises(InstanceMaintenanceBusy):
            with gate.exclusive("one"):
                pytest.fail("supervisor inheritance did not retain ownership")
    finally:
        for descriptor in inherited:
            os.close(descriptor)
        active[-1].close()
    with gate.exclusive("one"):
        assert collection.summary("execution")["state"] == "completed"
