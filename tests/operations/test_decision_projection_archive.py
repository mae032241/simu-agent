"""Decision read metadata survives archive without rewriting old archive schemas."""
import hashlib
import sqlite3
import pytest
from scidiscovery.artifact_agent.service.instance_archive import InstanceArchive
from tests.operations.test_instance_archive import save_archive, restore_archive
from tests.operations.test_instance_archive_continuation import _hardened_system
from tests.operations.test_l5_hardened_run_backend import _invoke, _worker, _write_result


@pytest.mark.parametrize('legacy', [False, True])
def test_projection_snapshot_archive_roundtrip_and_old_readonly_schema(tmp_path, legacy):
    catalog, runtime, instance, root = _hardened_system(tmp_path)
    _invoke(root)
    worker = _worker(catalog, runtime)
    worker.call_tool('worker_open_assignment', {})
    _write_result(worker)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    run_id = worker._run_id
    runtime.runs.backend.release_transport(run_id, worker._transport_owner)
    fields = runtime.runs.status(run_id).decision_fields
    assert fields == catalog.operation(runtime.runs.status(run_id).operation_id).spec.decision_fields
    if legacy:
        with sqlite3.connect(runtime.runs.database_path) as connection:
            connection.execute('ALTER TABLE runs DROP COLUMN decision_fields_json')
    service = InstanceArchive(runtime)
    save_archive(service, instance.instance_id)
    package = service.root / instance.instance_id
    def hashes():
        return {str(p.relative_to(package)):hashlib.sha256(p.read_bytes()).hexdigest() for p in package.rglob('*') if p.is_file()}
    original = hashes()
    archived = service.archived_model(instance.instance_id)
    assert archived.runs.status(run_id).decision_fields == (None if legacy else fields)
    assert hashes() == original
    runtime.runs._initialize()
    assert restore_archive(service, instance.instance_id)['storage_state'] == 'restored'
    assert runtime.runs.status(run_id).decision_fields == (None if legacy else fields)
    assert hashes() == original
