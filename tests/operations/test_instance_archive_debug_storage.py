"""No solver: exact persisted diagnostic ownership through real archive IO."""
import fcntl
import hashlib
import json
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json, canonical_sha256
from scidiscovery.artifact_agent.service.instance_archive import ArchiveError
from scidiscovery.artifact_agent.service.instance_archive_files import Files, roots
from scidiscovery.operations.runtime_plugins import ArchiveStorage, ArchiveStorageSelection
from tests.operations.test_instance_archive import archive_system, failed_run, restore_archive, save_archive


def configure(runtime, service, tmp_path):
    path = tmp_path / 'tcad.json'
    # Archive ownership discovery must not connect this deliberately absent socket.
    path.write_text(json.dumps(dict(transport='socket', socket_path=str(tmp_path / 'never-connect.sock'))))
    service.plugin_configs = {'tcad_artifact': path}
    return runtime.state_root / 'local-tcad-debug'


def diagnostic(runtime, root, instance, name, *, state='collected'):
    run_id = 'run_debug' + name
    failed_run(runtime, instance, run_id)
    key = canonical_sha256({'subject': canonical_sha256({'instance': instance})})
    record_key = canonical_sha256({'run_id': run_id, 'run_name': name})
    exchange = root / hashlib.sha256(name.encode()).hexdigest()[:32] / name
    exchange.mkdir(parents=True)
    source = exchange / 'job.json'
    source.write_bytes(b'{"synthetic":"no solver"}')
    submission = dict(name='job', local_path=str(source), sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        size_bytes=source.stat().st_size, media_type='application/json')
    record = dict(run_id=run_id, run_name=name, mode='smoke', state=state, external_run_id='synthetic-' + name)
    response = dict(state='succeeded', phase='collected')
    if state == 'collected':
        record['response'] = response
    ledger = dict(schema_version=2, reserved_wall_seconds=17, debug_policy={'fixture': True},
        runs={record_key: record}, reservations={record_key: dict(submission=submission, record=dict(record, state='accepted'))})
    budgets = root / 'budgets'
    budgets.mkdir(exist_ok=True)
    path = budgets / (key + '.json')
    path.write_bytes(canonical_json(ledger))
    path.with_suffix('.lock').touch()
    receipt = budgets / 'receipts' / record_key
    receipt.mkdir(parents=True)
    raw = b'exact diagnostic original'
    sha = hashlib.sha256(raw).hexdigest()
    (receipt / sha).write_bytes(raw)
    (receipt / 'receipt.json').write_bytes(canonical_json(dict(submission=submission, response=response,
        proof=dict(run_id=run_id, run_name=name, files=[dict(sha256=sha, size_bytes=len(raw))]))))
    return path, receipt, exchange.parent


def bytes_under(root):
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob('*') if path.is_file()}


def test_other_instance_debug_is_retained_while_target_and_owned_debug_roundtrip(archive_system, tmp_path):
    runtime, service, first, second = archive_system
    root = configure(runtime, service, tmp_path)
    assert service.preview(first)['ready'] and not root.exists()  # Read-only provider assembly.
    other = diagnostic(runtime, root, second, 'other')
    before = bytes_under(root)
    preview = service.preview(first)
    assert preview['ready'], preview
    assert any(row.get('reason') == 'unselected_plugin_state_retained' for row in preview['unowned'])
    save_archive(service, first)
    restore_archive(service, first)
    assert bytes_under(root) == before
    owned = diagnostic(runtime, root, first, 'owned')
    all_before = bytes_under(root)
    save_archive(service, first)
    assert not owned[0].exists() and not owned[1].exists() and not owned[2].exists()
    assert not owned[0].with_suffix('.lock').exists()
    assert all(path.exists() for path in other)
    assert service.preview(second)['ready']
    restore_archive(service, first)
    assert bytes_under(root) == all_before
    assert json.loads(owned[0].read_bytes())['reserved_wall_seconds'] == 17


@pytest.mark.parametrize('state', ['accepted', 'running', 'failed', 'succeeded'])
def test_target_pending_or_uncollected_debug_blocks_without_solver_calls(archive_system, tmp_path, state):
    runtime, service, first, _ = archive_system
    root = configure(runtime, service, tmp_path)
    diagnostic(runtime, root, first, 'pending', state=state)
    before = bytes_under(root)
    preview = service.preview(first)
    assert not preview['ready']
    assert any(row['code'] == 'plugin_storage_unavailable' for row in preview['unsupported'])
    assert bytes_under(root) == before


def test_target_writer_lock_and_preview_changes_remain_rejected(archive_system, tmp_path):
    runtime, service, first, _ = archive_system
    root = configure(runtime, service, tmp_path)
    ledger, receipt, _ = diagnostic(runtime, root, first, 'owned')
    with ledger.with_suffix('.lock').open('rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert not service.preview(first)['ready']
    unlocked = service.preview(first)
    assert unlocked['ready']
    with ledger.with_suffix('.lock').open('rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ArchiveError, match='preview changed'):
            service.archive(first, unlocked['fingerprint'])
    preview = service.preview(first)
    assert preview['ready'], preview
    value = json.loads(ledger.read_bytes())
    value['reserved_wall_seconds'] += 1
    ledger.write_bytes(canonical_json(value))
    with pytest.raises(ArchiveError, match='preview changed'):
        service.archive(first, preview['fingerprint'])
    assert receipt.exists()


@pytest.mark.parametrize('damage', ['orphan', 'owner', 'receipt', 'link', 'missing_lock'])
def test_unknown_or_damaged_debug_is_preserved_and_refuses_migration(archive_system, tmp_path, damage):
    runtime, service, first, second = archive_system
    root = configure(runtime, service, tmp_path)
    ledger, receipt, exchange = diagnostic(runtime, root, second, 'other')
    if damage == 'orphan':
        (root / 'old-no-owner').mkdir()
    elif damage == 'owner':
        value = json.loads(ledger.read_bytes())
        record = next(iter(value['runs'].values()))
        record['run_id'] = 'run_missing_owner'
        ledger.write_bytes(canonical_json(value))
    elif damage == 'receipt':
        # Damage the target's own proof; other-instance content is not adopted.
        ledger, receipt, exchange = diagnostic(runtime, root, first, 'owned')
        (receipt / 'receipt.json').write_text('{}')
    elif damage == 'link':
        (root / 'unowned-link').symlink_to(tmp_path)
    else:
        ledger.with_suffix('.lock').unlink()
    assert not service.preview(first)['ready']
    assert ledger.exists() and receipt.exists() and exchange.exists()


def test_uninstalled_provider_residual_remains_explicitly_unsupported(archive_system, tmp_path):
    runtime, service, first, second = archive_system
    root = runtime.state_root / 'local-tcad-debug'
    diagnostic(runtime, root, second, 'other')
    preview = service.preview(first)
    assert not preview['ready']
    assert any(row['code'] == 'local_debug_ownership_and_writer_unknown' for row in preview['unsupported'])


def test_known_other_instance_pending_state_does_not_grant_ownership_to_target(archive_system, tmp_path):
    runtime, service, first, second = archive_system
    root = configure(runtime, service, tmp_path)
    diagnostic(runtime, root, second, 'other', state='running')
    before = bytes_under(root)
    assert service.preview(first)['ready']
    assert not service.preview(second)['ready']
    save_archive(service, first)
    assert bytes_under(root) == before


def test_collected_real_debug_service_records_fit_the_readonly_inventory(tmp_path, monkeypatch):
    from dataclasses import replace
    from tests.operations.test_debug_task_identity import fixture
    from tcad_artifact import debug_archive
    instance = 'ins_fixture'
    subject = canonical_sha256({'instance': instance})
    debugger, adapter, context, _ = fixture(tmp_path, monkeypatch)
    prepare = adapter.prepare
    def exact_submission(**kwargs):
        prepared = prepare(**kwargs)
        source = Path(prepared.submission.local_path)
        return replace(prepared, submission=prepared.submission.model_copy(update={
            'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}))
    monkeypatch.setattr(adapter, 'prepare', exact_submission)
    root = debugger.exchange_root
    current = context('first')
    debugger.run(current, run_name='probe', mode='preflight', budget_subject=subject)
    adapter.states['1'] = 'succeeded'
    debugger.run(current, run_name='probe', mode='preflight', budget_subject=subject)
    before = bytes_under(root)
    selected = debug_archive.inspect(root, instance, ('first',), lambda _: instance)
    assert not selected.unsupported, selected
    assert len(selected.paths) == 4
    assert bytes_under(root) == before


def test_control_writer_started_after_scan_prevents_archive_freeze(archive_system, tmp_path):
    from contextlib import ExitStack
    from scidiscovery.artifact_agent.service.instance_maintenance import InstanceMaintenanceBusy
    runtime, service, first, _ = archive_system
    root = configure(runtime, service, tmp_path)
    ledger, _, _ = diagnostic(runtime, root, first, 'owned')
    preview = service.preview(first)
    with ExitStack() as leases:
        def acquire(point):
            if point == 'after_archive_scan':
                leases.enter_context(runtime.instance_maintenance.guard(first))
        service._fault = acquire
        with pytest.raises(InstanceMaintenanceBusy):
            service.archive(first, preview['fingerprint'])
    assert ledger.exists()


def test_restore_requires_the_original_plugin_provider(archive_system, tmp_path):
    runtime, service, first, _ = archive_system
    root = configure(runtime, service, tmp_path)
    ledger, _, _ = diagnostic(runtime, root, first, 'owned')
    save_archive(service, first)
    service.plugin_configs = {}
    assert not service.restore_preview(first)['ready']
    assert not ledger.exists()


@pytest.mark.parametrize('relative', ['../outside', '/outside', '.', 'dir/../outside'])
def test_common_inventory_rejects_plugin_paths_outside_its_declared_tree(archive_system, tmp_path, relative):
    runtime, _, first, _ = archive_system
    storage = ArchiveStorage(runtime.state_root / 'declared', lambda *args: ArchiveStorageSelection(paths=(relative,)))
    from scidiscovery.artifact_agent.service.instance_archive_records import Records
    records = Records(runtime)
    with pytest.raises(ArchiveError):
        Files(runtime, records, records.select(first), first, archive_storage={'fixture:storage': storage}).collect()


def test_common_inventory_rejects_overlapping_roots_and_symlinked_files(archive_system):
    runtime, _, first, _ = archive_system
    with pytest.raises(ArchiveError, match='overlaps'):
        roots(runtime, {'fixture:storage': ArchiveStorage(runtime.state_root, lambda *args: None)})
    from scidiscovery.artifact_agent.service.instance_archive_records import Records
    records = Records(runtime)
    root = runtime.state_root / 'declared'
    root.mkdir()
    (root / 'link').symlink_to(runtime.state_root)
    storage = ArchiveStorage(root, lambda *args: ArchiveStorageSelection(paths=('link',)))
    with pytest.raises(ArchiveError, match='symbolic links'):
        Files(runtime, records, records.select(first), first, archive_storage={'fixture:storage': storage}).collect()
