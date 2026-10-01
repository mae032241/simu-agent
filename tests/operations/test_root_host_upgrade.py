"""Upgrade snapshots retain scientific state without inheriting session authority."""
from contextlib import closing
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from scripts.root_host_upgrade import snapshot_state


def database(path, sql):
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.executescript(sql)


@pytest.fixture
def source(tmp_path):
    root = tmp_path / 'old'
    project = root / 'build/project'
    (project / '.codex').mkdir(parents=True)
    (project / '.codex/auth.json').write_text('must not copy')
    (project / 'sealed.json').write_text('{"subject":"原始材料"}')
    (project / 'sealed.json').chmod(0o400)
    (project / 'sealed-directory').mkdir()
    (project / 'sealed-directory/result').write_bytes(b'locked result')
    (project / 'sealed-directory').chmod(0o500)
    (project / 'empty-output').mkdir()
    (project / 'notes-wal').write_text('scientific attachment, not a database sidecar')
    (root / 'candidate.json').write_text(json.dumps({'project': str(project), 'head': 'old-head'}))
    state = root / 'state'
    database(state / 'database/runs.sqlite3', "CREATE TABLE runs(id, state); INSERT INTO runs VALUES('sealed-run','completed');")
    database(state / 'database/executions.sqlite3', 'CREATE TABLE executions(id, state);')
    database(state / 'database/scheduler-bindings.sqlite3', """
        CREATE TABLE scheduler_sessions(session_key, instance_id);
        INSERT INTO scheduler_sessions VALUES('old-session','existing-instance');
        CREATE TABLE worker_connections(run_id, thread_id);
        INSERT INTO worker_connections VALUES('sealed-run','original-author');
    """)
    database(state / 'database/scheduler-bindings-clients.sqlite3', """
        CREATE TABLE scheduler_clients(session_key, enabled);
        INSERT INTO scheduler_clients VALUES('old-session',1);
    """)
    (state / 'maintenance.lock').touch()
    (state / 'artifacts').mkdir()
    (state / 'artifacts/sealed-object').write_bytes(b'immutable evidence')
    (root / 'approval-secret').write_text('fixture-signing-key')
    (root / 'agent-settings.json').write_text('{}')
    return root


def fingerprints(root):
    # A read-only SQLite connection updates transient WAL reader marks in SHM;
    # the database and committed WAL bytes must remain unchanged.
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and not p.name.endswith('.sqlite3-shm')}


def test_snapshot_preserves_wal_science_and_original_but_drops_session_authority(source, tmp_path):
    path = source / 'state/database/artifact_agent.sqlite3'
    with closing(sqlite3.connect(path)) as writer:
        writer.execute('PRAGMA journal_mode=WAL')
        writer.executescript("CREATE TABLE objects(id); INSERT INTO objects VALUES('frozen-object');")
        before = fingerprints(source)
        target = tmp_path / 'upgrade'
        receipt = snapshot_state(source, target)
        assert fingerprints(source) == before
        with closing(sqlite3.connect(target / 'state/database/artifact_agent.sqlite3')) as db:
            assert db.execute('SELECT id FROM objects').fetchall() == [('frozen-object',)]
    with closing(sqlite3.connect(target / 'state/database/scheduler-bindings.sqlite3')) as db:
        assert db.execute('SELECT * FROM scheduler_sessions').fetchall() == []
        assert db.execute('SELECT * FROM worker_connections').fetchall() == [('sealed-run', 'original-author')]
    with closing(sqlite3.connect(target / 'state/database/scheduler-bindings-clients.sqlite3')) as db:
        assert db.execute('SELECT * FROM scheduler_clients').fetchall() == []
    assert (target / 'state/artifacts/sealed-object').read_bytes() == b'immutable evidence'
    project = Path(json.loads((source / 'candidate.json').read_text())['project'])
    assert (target / 'project/sealed.json').read_bytes() == (project / 'sealed.json').read_bytes()
    assert (target / 'project/notes-wal').read_bytes() == (project / 'notes-wal').read_bytes()
    assert (target / 'project/empty-output').is_dir()
    assert (target / 'project/sealed-directory/result').read_bytes() == b'locked result'
    assert (target / 'project/sealed-directory').stat().st_mode & 0o777 == 0o500
    assert not (target / 'project/.codex').exists()
    assert (target / 'approval-secret').read_bytes() == (source / 'approval-secret').read_bytes()
    assert (target / 'approval-secret').stat().st_mode & 0o777 == 0o600
    assert receipt['source_head'] == 'old-head'
    assert receipt['scientific_identities_rewritten'] is False


@pytest.mark.parametrize('state,host,accepted,reason', [('paused', None, True, 'user_paused'),
    ('paused', None, True, 'budget_exhausted'), ('active', None, False, 'host_active'),
    ('paused', '{"thread_id":"unresolved"}', False, 'host_fault')])
def test_progression_copy_preserves_usage_and_fences_authority(source, tmp_path, state, host, accepted, reason):
    from scidiscovery.artifact_agent.service.scheduling_control import CONTROL_SCHEMA, CONTROL_VERSION
    path = source / 'state/database/scheduler-bindings.sqlite3'
    checkpoint = json.dumps({'budget': {'consumed_tasks': 2, 'observed_tokens': 110}, 'usage_records': {'root': {'tokens': 123}},
                             'report': {'summary': 'insufficient evidence'}})
    with sqlite3.connect(path) as db:
        db.executescript('CREATE TABLE scheduler_instances(instance_id TEXT PRIMARY KEY);' + CONTROL_SCHEMA)
        db.execute(f'PRAGMA user_version={CONTROL_VERSION}')
        db.execute('INSERT INTO scheduler_progression VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                   ('existing-instance', 4, 'old-root', 'old-reader', state, 'background', reason,
                    'goal', '{}', '{}', 'fingerprint', host, checkpoint, '2026-09-28'))
        db.execute("INSERT INTO scheduler_dispatch_intents VALUES('existing-instance','old-run',4,'old-root','now')")
    target = tmp_path / 'upgrade'
    if not accepted:
        with pytest.raises(ValueError, match='unresolved scheduler'):
            snapshot_state(source, target)
        assert not (target / 'state').exists()
        return
    snapshot_state(source, target)
    with sqlite3.connect(target / 'state/database/scheduler-bindings.sqlite3') as db:
        db.row_factory = sqlite3.Row
        row = db.execute('SELECT * FROM scheduler_progression').fetchone()
        assert row['state'] == 'paused' and row['reason'] == 'archive_restored'
        assert row['owner_session'] is row['requested_by'] is row['host_json'] is None
        expected = json.loads(checkpoint)
        if reason == 'budget_exhausted':
            expected['stop_snapshot_tokens'] = 110
        assert json.loads(row['checkpoint_json']) == expected and row['generation'] == 5
        assert not db.execute('SELECT * FROM scheduler_dispatch_intents').fetchall()


@pytest.mark.parametrize('table,state', [('runs', 'running'), ('executions', 'submitted')])
def test_rejects_unfinished_work_without_changing_source(source, tmp_path, table, state):
    database(source / f'state/database/{table}.sqlite3', f"INSERT INTO {table} VALUES('unfinished','{state}');")
    before = fingerprints(source)
    with pytest.raises(ValueError, match='unfinished'):
        snapshot_state(source, tmp_path / 'upgrade')
    assert fingerprints(source) == before
    assert not (tmp_path / 'upgrade/state').exists()


def test_requires_exclusive_source_maintenance_lock(source, tmp_path):
    with (source / 'state/maintenance.lock').open('rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_SH)
        with pytest.raises(BlockingIOError):
            snapshot_state(source, tmp_path / 'upgrade')
    assert not (tmp_path / 'upgrade/state').exists()


@pytest.mark.parametrize('invalid', ['same', 'nested', 'occupied', 'symlink'])
def test_rejects_unsafe_copy_locations(source, tmp_path, invalid):
    target = tmp_path / 'upgrade'
    if invalid == 'same':
        target = source
    elif invalid == 'nested':
        target = source / 'nested'
    elif invalid == 'occupied':
        (target / 'state').mkdir(parents=True)
    else:
        (source / 'state/artifacts/link').symlink_to(source / 'approval-secret')
    before = fingerprints(source)
    with pytest.raises(ValueError):
        snapshot_state(source, target)
    assert fingerprints(source) == before
