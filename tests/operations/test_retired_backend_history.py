"""Synthetic historical records: read old bytes without an old executor."""
import hashlib
import json
import sqlite3
from importlib.util import find_spec

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.service.instance_archive_files import hash_file
from scidiscovery.artifact_agent.service.instance_archive_reader import archived_model
from scidiscovery.artifact_agent.service.runs import RunStateConflict
from tests.operations.synchronous_archive_fixture import SynchronousFixtureArchive
from tests.operations.test_instance_archive import save_archive
from tests.operations.test_instance_archive_continuation import _local_archive_system
from tests.operations.test_local_worker_contracts import RAW, _invoke, _worker, _write_result


HISTORICAL_CAPABILITIES = ('exact_operation_slot', 'server_file_transport', 'restart_same_run',
    'immutable_candidate', 'failure_isolation', 'native_tools_disabled')


def _retag(database, run_id):
    with sqlite3.connect(database) as connection:
        raw, = connection.execute('SELECT recovery_draft_json FROM runs WHERE run_id=?', (run_id,)).fetchone()
        draft = json.loads(raw) if raw else None
        if draft:
            draft.update(backend='hardened_worker', backend_version='1')
        connection.execute('UPDATE runs SET backend_id=?,backend_version=?,backend_capabilities_json=?,recovery_draft_json=? WHERE run_id=?',
            ('hardened_worker', '1', canonical_json(HISTORICAL_CAPABILITIES),
             canonical_json(draft) if draft else None, run_id))


def test_old_queued_run_cannot_change_state_or_open_on_local(tmp_path):
    catalog, runtime, instance, root = _local_archive_system(tmp_path)
    _invoke(root)
    status, = runtime.runs.list(instance_id=instance.instance_id)
    _retag(runtime.runs.database_path, status.run_id)
    old = runtime.runs.status(status.run_id)
    before = runtime.runs.database_path.read_bytes()
    with pytest.raises(RunStateConflict, match='historical Run backend'):
        runtime.runs.reopen(operation_id=old.operation_id, operation_digest=old.operation_digest, run_id=old.run_id)
    assert runtime.runs.status(old.run_id) == old
    assert runtime.runs.database_path.read_bytes() == before


@pytest.mark.parametrize('state', ['completed', 'failed'])
def test_historical_archive_reads_workspaces_artifacts_and_drafts_without_execution(tmp_path, state):
    catalog, runtime, instance, root = _local_archive_system(tmp_path)
    _invoke(root)
    worker = _worker(catalog, runtime)
    opened = worker.call_tool('worker_open_assignment', {})
    _write_result(worker)
    if state == 'completed':
        assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    else:
        value = runtime.runs.status(worker._run_id)
        runtime.runs.record_failure(value.run_id, reason='synchronous fixture stopped',
            expected_state='running', expected_last_activity_at=value.last_activity_at)
    old = runtime.runs.status(worker._run_id)
    expected_output = runtime.artifacts.read(old.output_ref) if old.output_ref else None
    source = next(item.artifact_ref for item in old.inputs if item.port_name == 'source_table')
    service = SynchronousFixtureArchive(runtime)
    save_archive(service, instance.instance_id)
    package = service.root / instance.instance_id
    # Construct an old-format fixture from the format-compatible Local files.
    # No prior executor runs, and no live or registered production archive changes.
    _retag(package / 'records/runs.sqlite3', old.run_id)
    (package / 'workspaces/local').rename(package / 'workspaces/hardened')
    manifest = json.loads((package / 'manifest.json').read_bytes())
    manifest['records']['runs.sqlite3'] = hash_file(package / 'records/runs.sqlite3')
    # Dispatch is history only; loading this file must never register a transport.
    dispatch = package / 'records/dispatch.sqlite3'
    with sqlite3.connect(dispatch) as connection:
        connection.execute('CREATE TABLE active_transport(run_id TEXT PRIMARY KEY, owner_id TEXT, lease_deadline_at TEXT)')
        connection.execute('INSERT INTO active_transport VALUES (?,?,?)', (old.run_id, 'old-owner', '2000-01-01T00:00:00+00:00'))
    manifest['records']['dispatch.sqlite3'] = hash_file(dispatch)
    def hashes():
        return {str(p.relative_to(package)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in package.rglob('*') if p.is_file()}
    before = hashes()
    archived = archived_model(runtime, package, manifest)
    value = archived.runs.status(old.run_id)
    assert value.backend_id == 'hardened_worker' and value.state == state
    assert archived.artifacts.read(source) == RAW
    assert archived.node(instance.instance_id, 'run:observation')['state'] == state
    if state == 'completed':
        assert archived.runs.backend.open(old.run_id).assignment_path.is_file()
        assert archived.artifacts.read(value.output_ref) == expected_output
    else:
        draft = archived.runs.backend.verify_recovery(value.recovery_draft['draft_digest'], max_files=128, max_bytes=1024*1024)
        assert draft.backend == 'hardened_worker'
        assert (draft.root / 'result.json').is_file()
        assert archived.runs.recovery_status(value)['delivery_preserved']
    for method in ('claim', 'reopen', 'submit', 'record_failure'):
        with pytest.raises(AttributeError):
            getattr(archived.runs, method)
    assert archived.runs.backend.supports_operation(catalog.operation(value.operation_id)) is False
    assert hashes() == before
    assert find_spec('scidiscovery.artifact_agent.interfaces.mcp_hardened_worker') is None
    assert find_spec('scidiscovery.artifact_agent.service.hardened_workspace') is None
    assert find_spec('scidiscovery.artifact_agent.service.hardened_files') is None
