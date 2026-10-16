"""No solver: exact persisted diagnostic ownership through real archive IO."""
import fcntl
import hashlib
import json
from pathlib import Path
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json, canonical_sha256
from scidiscovery.artifact_agent.service.instance_archive import ArchiveError
from scidiscovery.artifact_agent.service.instance_archive_files import Files, roots
from scidiscovery.operations.runtime_plugins import ArchiveStorage, ArchiveStorageSelection
from tests.operations.test_instance_archive import archive_system, failed_run, restore_archive, save_archive


@dataclass
class DiagnosticContext:
    run_id: str
    operation_id: str
    workspace: Path
    output_directory: Path
    service: object

    def require_service(self, name):
        assert name == 'tcad.development_debug'
        return self.service


def configure(runtime, service, tmp_path):
    path = tmp_path / 'tcad.json'
    # Archive ownership discovery must not connect this deliberately absent socket.
    path.write_text(json.dumps(dict(transport='socket', socket_path=str(tmp_path / 'never-connect.sock'))))
    service.plugin_configs = {'tcad_artifact': path}
    return runtime.state_root / 'local-tcad-debug'


def diagnostic(runtime, root, instance, name, *, state='collected'):
    run_id = 'run_debug' + name
    failed_run(runtime, instance, run_id)
    from scidiscovery.artifact_agent.service.experiment_execution import _TaskExperimentTools
    service = SimpleNamespace(exchange_root=root)
    controlled = SimpleNamespace(run_id=run_id, operation_id='retired.fixture')
    coordinator = SimpleNamespace(runs=SimpleNamespace(running_task=lambda _: controlled), task_origin=lambda _: run_id)
    tools = _TaskExperimentTools(coordinator, operation_id='retired.fixture', run_id=run_id)
    private = tools.diagnostic_context(DiagnosticContext(run_id, 'retired.fixture', root, root / 'output', service),
        service_name='tcad.development_debug')
    (private.workspace / 'private.json').write_bytes(b'original private diagnostic workspace')
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
    assert not (root / 'experiment-workspaces/run_debugowned').exists()
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


@pytest.mark.parametrize('provider', ['missing', 'changed_root'])
def test_restore_requires_the_original_plugin_provider(archive_system, tmp_path, provider):
    runtime, service, first, _ = archive_system
    root = configure(runtime, service, tmp_path)
    ledger, _, _ = diagnostic(runtime, root, first, 'owned')
    save_archive(service, first)
    if provider == 'missing':
        service.plugin_configs = {}
    else:
        from tcad_artifact.debug_archive import storage
        service._archive_storage = lambda: {'tcad_artifact:debug': storage(runtime.state_root / 'other-debug')}
    assert not service.restore_preview(first)['ready']
    assert not ledger.exists()


def test_worker_debug_handler_preserves_other_instance_and_allows_real_generic_archive(tmp_path, monkeypatch):
    from dataclasses import replace
    from tests.operations.test_experiment_continuation import continuation, submit
    from scidiscovery.artifact_agent.service.instance_archive import InstanceArchive
    from tests.operations.test_instance_archive import artifact
    f = continuation(tmp_path, monkeypatch)
    debugger = f.coordinator.worker_services['tcad_artifact:tcad.development_debug']
    debugger.exchange_root = f.runtime.state_root / 'local-tcad-debug'
    debugger.exchange_root.mkdir()
    prepare = debugger.adapter.prepare
    def managed_submission(**kwargs):
        prepared = prepare(**kwargs)
        source = Path(prepared.submission.local_path)
        target = kwargs['exchange_directory'] / 'submission.json'
        target.write_bytes(source.read_bytes())
        return replace(prepared, submission=prepared.submission.model_copy(update={
            'local_path': str(target), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}))
    monkeypatch.setattr(debugger.adapter, 'prepare', managed_submission)
    observed = f.worker.call_tool('worker_experiment_debug',
        {'implementation': f.alias, 'name': 'managed', 'mode': 'preflight'})
    assert observed['state'] == 'succeeded'
    assert submit(f, [f.alias], outcome='blocked')['state'] == 'completed'
    private = debugger.exchange_root / 'experiment-workspaces' / f.coordinator.task_origin(f.runs.status(f.run_id))
    assert (private / 'deck/reports/diagnostic-managed.json').is_file()
    other = f.runtime.scheduler_bindings.create_instance(name='generic.archive', title='Generic', objective='Exact original')
    original = b'generic original independent of TCAD'
    envelope = artifact(f.runtime, other.instance_id, 'original', original)
    config = tmp_path / 'archive-tcad.json'
    config.write_text(json.dumps(dict(transport='socket', socket_path=str(tmp_path / 'never.sock'))))
    service = InstanceArchive(f.runtime, plugin_configs={'tcad_artifact': config})
    before = bytes_under(debugger.exchange_root)
    preview = service.preview(other.instance_id)
    assert preview['ready'], preview
    service.archive(other.instance_id, preview['fingerprint'])
    service.plugin_configs = {}
    restored = service.restore_preview(other.instance_id)
    assert restored['ready'], restored
    service.restore(other.instance_id, restored['fingerprint'])
    assert f.runtime.artifacts.read(envelope.ref) == original
    assert bytes_under(debugger.exchange_root) == before


@pytest.mark.parametrize('legacy_empty_root', [False, True])
def test_pure_generic_archive_restores_without_empty_provider(archive_system, tmp_path, monkeypatch, legacy_empty_root):
    from scidiscovery.artifact_agent.service.instance_archive import InstanceArchive
    from scidiscovery.artifact_agent.service import instance_archive_files
    from tests.operations.test_instance_archive import artifact
    runtime, _, first, _ = archive_system
    service = InstanceArchive(runtime)
    debug = configure(runtime, service, tmp_path)
    raw = b'generic original; no TCAD execution or file'
    envelope = artifact(runtime, first, 'generic', raw)
    with monkeypatch.context() as patch:
        if legacy_empty_root:
            # Reproduce the old producer before sealing. Restore must verify the
            # resulting original manifest/snapshot without rewriting either.
            patch.setattr(instance_archive_files, 'archive_file_roots', lambda roots, files, gaps: roots)
        preview = service.preview(first)
        assert preview['ready'], preview
        service.archive(first, preview['fingerprint'])
    index = service._index(first)
    snapshot = service._package_snapshot(index)
    assert not any(row['root'].startswith('plugins/') for row in snapshot['files'])
    assert any(key.startswith('plugins/') for key in snapshot['roots']) == legacy_empty_root
    manifest = service.root / first / 'manifest.json'
    sealed_manifest = manifest.read_bytes()
    sealed_snapshot = (service.root / first / 'records/snapshot.json').read_bytes()
    service.plugin_configs = {}
    restored = service.restore_preview(first)
    assert restored['ready'], restored
    service.restore(first, restored['fingerprint'])
    assert runtime.artifacts.read(envelope.ref) == raw
    assert manifest.read_bytes() == sealed_manifest
    assert (service.root / first / 'records/snapshot.json').read_bytes() == sealed_snapshot
    assert not debug.exists()
    preview = service.preview(first)
    assert preview['ready']
    service.archive(first, preview['fingerprint'])
    restored = service.restore_preview(first)
    assert restored['ready']
    service.restore(first, restored['fingerprint'])
    assert runtime.artifacts.read(envelope.ref) == raw


def test_missing_plugin_original_gap_still_requires_provider(archive_system):
    runtime, service, first, _ = archive_system
    root = runtime.state_root / 'declared-plugin'
    storage = ArchiveStorage(root, lambda *args: ArchiveStorageSelection(paths=('missing-original',)))
    service._archive_storage = lambda: {'fixture:storage': storage}
    save_archive(service, first)
    snapshot = service._package_snapshot(service._index(first))
    assert not any(row['root'].startswith('plugins/') for row in snapshot['files'])
    assert 'plugins/fixture/storage' in snapshot['roots']
    assert any(row.get('path') == 'plugins/fixture/storage/missing-original' for row in snapshot['gaps'])
    service._archive_storage = lambda: {}
    assert not service.restore_preview(first)['ready']
    service._archive_storage = lambda: {'fixture:storage': ArchiveStorage(runtime.state_root / 'changed-root', lambda *args: None)}
    assert not service.restore_preview(first)['ready']


@pytest.mark.parametrize('damage', ['unknown_run', 'not_origin', 'cross_instance', 'symlink', 'file'])
def test_workspace_requires_exact_controlled_origin(archive_system, tmp_path, damage):
    import sqlite3
    runtime, service, first, second = archive_system
    root = configure(runtime, service, tmp_path)
    diagnostic(runtime, root, second, 'other')
    workspaces = root / 'experiment-workspaces'
    if damage == 'unknown_run':
        (workspaces / 'run_absent').mkdir()
    elif damage in {'not_origin', 'cross_instance'}:
        failed_run(runtime, first if damage == 'cross_instance' else second, 'run_notorigin')
        with sqlite3.connect(runtime.runs.database_path) as connection:
            connection.execute("UPDATE runs SET draft_from_run_id='run_debugother' WHERE run_id='run_notorigin'")
        (workspaces / 'run_notorigin').mkdir()
    elif damage == 'symlink':
        (workspaces / 'linked').symlink_to(tmp_path)
    else:
        (workspaces / 'run_extra').write_bytes(b'not a workspace')
    assert not service.preview(first)['ready']


def test_controlled_workspace_before_reservation_is_owned_without_inventing_budget(archive_system, tmp_path):
    from scidiscovery.artifact_agent.service.experiment_execution import _TaskExperimentTools
    runtime, service, first, second = archive_system
    root = configure(runtime, service, tmp_path)
    run_id = 'run_unprepared'
    failed_run(runtime, second, run_id)
    controlled = SimpleNamespace(run_id=run_id, operation_id='retired.fixture')
    coordinator = SimpleNamespace(runs=SimpleNamespace(running_task=lambda _: controlled), task_origin=lambda _: run_id)
    tools = _TaskExperimentTools(coordinator, operation_id='retired.fixture', run_id=run_id)
    private = tools.diagnostic_context(DiagnosticContext(run_id, 'retired.fixture', root, root / 'output',
        SimpleNamespace(exchange_root=root)), service_name='tcad.development_debug').workspace
    (private / 'preparation.txt').write_bytes(b'exact failed preparation original')
    assert not (root / 'budgets').exists()
    assert service.preview(first)['ready']
    before = bytes_under(root)
    save_archive(service, second)
    assert not private.exists()
    restore_archive(service, second)
    assert bytes_under(root) == before
    assert not (root / 'budgets').exists()


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
