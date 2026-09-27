"""Four-column legacy migration with immutable archive and transaction recovery."""
import hashlib
import sqlite3

import pytest

from scidiscovery.agent_execution_settings import EXECUTION_SETTINGS_COLUMNS
from scidiscovery.artifact_agent.service.instance_archive import ArchiveError, InstanceArchive
from tests.operations.test_instance_archive import save_archive, restore_archive
from tests.operations.test_instance_archive_continuation import _hardened_system
from tests.operations.test_l5_hardened_run_backend import _invoke, _worker, _write_result


def _fixture(tmp_path, *, legacy):
    catalog, runtime, instance, root = _hardened_system(tmp_path)
    _invoke(root)
    worker = _worker(catalog, runtime)
    worker.call_tool("worker_open_assignment", {})
    _write_result(worker)
    worker.call_tool("worker_submit_result", {})
    run_id = worker._run_id
    runtime.runs.backend.release_transport(run_id, worker._transport_owner)
    if legacy:
        # Synthetic old schema. An actual old installed-package archive is also
        # replayed in installation evidence; no production database is changed.
        for table, path in (("scheduler_instances", runtime.scheduler_bindings.database_path),
                            ("runs", runtime.runs.database_path)):
            with sqlite3.connect(path) as connection:
                for column in EXECUTION_SETTINGS_COLUMNS[table]:
                    connection.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
    else:
        runtime.scheduler_bindings.save_agent_settings(instance.instance_id,
            {"defaults": {"model": "gpt-5.6-luna"}}, expected_revision=0, maintenance=runtime.instance_maintenance)
    original = runtime.runs.status(run_id)
    service = InstanceArchive(runtime)
    save_archive(service, instance.instance_id)
    package = service.root / instance.instance_id
    hashes = {str(path.relative_to(package)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in package.rglob("*") if path.is_file()}
    runtime.scheduler_bindings._initialize()
    runtime.runs._initialize()
    return runtime, service, instance.instance_id, run_id, original, package, hashes


@pytest.mark.parametrize("legacy", [True, False])
def test_old_and_new_archive_resume_after_commit_preserves_exact_configuration(tmp_path, legacy):
    runtime, service, instance, run_id, original, package, hashes = _fixture(tmp_path, legacy=legacy)
    preview = service.restore_preview(instance)
    assert preview["ready"], preview
    def fault(point):
        if point == "after_database_commit":
            raise OSError("interrupted after commit")
    service._fault = fault
    with pytest.raises(OSError, match="after commit"):
        service.restore(instance, preview["fingerprint"])
    service = InstanceArchive(runtime)
    assert service.resume(instance)["storage_state"] == "restored"
    assert runtime.runs.status(run_id) == original
    settings = runtime.scheduler_bindings.agent_settings(instance)
    assert settings["revision"] == (0 if legacy else 1)
    assert settings["settings"] == ({} if legacy else {"defaults": {"model": "gpt-5.6-luna"}})
    if legacy:
        assert runtime.runs.status(run_id).execution_profile is None
    runtime.scheduler_bindings.save_agent_settings(instance, {"defaults": {"narrative_language": "zh-CN"}},
        expected_revision=settings["revision"], maintenance=runtime.instance_maintenance)
    with pytest.raises(ArchiveError):
        service.restore(instance, preview["fingerprint"])
    assert runtime.scheduler_bindings.agent_settings(instance)["settings"]["defaults"]["narrative_language"] == "zh-CN"
    assert {str(path.relative_to(package)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in package.rglob("*") if path.is_file()} == hashes


@pytest.mark.parametrize("change", ["extra_column", "index", "trigger", "old_identity", "new_settings"])
def test_legacy_restore_rejects_unrelated_changes_without_overwriting(tmp_path, change):
    runtime, service, instance, *_ = _fixture(tmp_path, legacy=True)
    with sqlite3.connect(runtime.scheduler_bindings.database_path) as connection:
        if change == "extra_column":
            connection.execute("ALTER TABLE scheduler_instances ADD COLUMN unrelated TEXT")
        elif change == "index":
            connection.execute("CREATE INDEX unrelated_index ON scheduler_instances(title)")
        elif change == "trigger":
            connection.execute("CREATE TRIGGER unrelated_trigger AFTER UPDATE ON scheduler_instances BEGIN SELECT 1; END")
        elif change == "old_identity":
            connection.execute("UPDATE scheduler_instances SET title='changed' WHERE instance_id=?", (instance,))
        else:
            connection.execute("UPDATE scheduler_instances SET agent_settings_revision=7 WHERE instance_id=?", (instance,))
        before = connection.execute("SELECT * FROM scheduler_instances WHERE instance_id=?", (instance,)).fetchone()
    preview = service.restore_preview(instance)
    assert not preview["ready"], preview
    with pytest.raises(ArchiveError):
        service.restore(instance, preview["fingerprint"])
    with sqlite3.connect(runtime.scheduler_bindings.database_path) as connection:
        assert connection.execute("SELECT * FROM scheduler_instances WHERE instance_id=?", (instance,)).fetchone() == before


def test_restore_rechecks_schema_before_switch(tmp_path):
    runtime, service, instance, *_ = _fixture(tmp_path, legacy=True)
    preview = service.restore_preview(instance)
    assert preview["ready"]
    def fault(point):
        if point == "before_restore_switch":
            with sqlite3.connect(runtime.runs.database_path) as connection:
                connection.execute("CREATE INDEX changed_after_preview ON runs(created_at)")
    service._fault = fault
    with pytest.raises(ArchiveError, match="schema|control records changed"):
        service.restore(instance, preview["fingerprint"])
    assert runtime.scheduler_bindings.get_instance(instance_id=instance).state == "closed"


@pytest.mark.parametrize("legacy", [True, False])
@pytest.mark.parametrize("committed", [False, True])
def test_empty_archive_restore_recovery_respects_database_commit(tmp_path, legacy, committed):
    from tests.operations.test_instance_archive import archive_system
    runtime, service, instance, _ = archive_system.__wrapped__(tmp_path)
    if legacy:
        for table, path in (("scheduler_instances", runtime.scheduler_bindings.database_path),
                            ("runs", runtime.runs.database_path)):
            with sqlite3.connect(path) as connection:
                for column in EXECUTION_SETTINGS_COLUMNS[table]:
                    connection.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
    save_archive(service, instance)
    runtime.scheduler_bindings._initialize()
    runtime.runs._initialize()
    package = service.root / instance
    hashes = {str(path.relative_to(package)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in package.rglob("*") if path.is_file()}
    preview = service.restore_preview(instance)
    assert preview["ready"], preview
    def fault(point):
        if point == ("after_database_commit" if committed else "after_restore_copy"):
            raise OSError("interrupted restore")
    service._fault = fault
    with pytest.raises(OSError, match="interrupted restore"):
        service.restore(instance, preview["fingerprint"])
    service = InstanceArchive(runtime)
    if committed:
        with pytest.raises(ArchiveError, match="committed"):
            service.rollback(instance)
        assert service.resume(instance)["storage_state"] == "restored"
    else:
        assert service.rollback(instance)["storage_state"] == "archived"
        assert runtime.scheduler_bindings.get_instance(instance_id=instance).state == "closed"
        assert restore_archive(service, instance)["storage_state"] == "restored"
    assert runtime.scheduler_bindings.agent_settings(instance)["settings"] == {}
    assert {str(path.relative_to(package)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in package.rglob("*") if path.is_file()} == hashes
