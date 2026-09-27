"""Copy quiescent candidate state for an upgrade check; never reuse its sessions."""
from contextlib import closing
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat


def _readonly(path):
    return sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)


def _sqlite(path):
    with path.open('rb') as stream:
        return stream.read(16) == b'SQLite format 3\x00'


def _files(root, *, project=False):
    result = {}
    for directory, children, files in os.walk(root, followlinks=False):
        parent = Path(directory)
        if project and parent == root:
            children[:] = [name for name in children if name != '.codex']
        for name in (*children, *files):
            path = parent / name
            mode = path.lstat().st_mode
            if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise ValueError('candidate state contains a link or special file')
        for name in files:
            path = parent / name
            base = next((parent / name[:-len(suffix)] for suffix in ('-wal', '-shm', '-journal')
                         if name.endswith(suffix)), None)
            if base is not None and base.is_file() and _sqlite(base):
                continue  # SQLite backup includes committed WAL pages.
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            result[str(path.relative_to(root))] = digest
    return result


def _copy_tree(source, destination, files, *, project=False):
    # Sealed directories can be read-only: restore their modes after contents.
    directories = []
    for directory, children, _ in os.walk(source):
        parent = Path(directory)
        if project and parent == source:
            children[:] = [name for name in children if name != '.codex']
        target = destination / parent.relative_to(source)
        target.mkdir(parents=True, mode=0o700, exist_ok=False)
        directories.append((parent, target))
    for relative in files:
        path, target = source / relative, destination / relative
        if _sqlite(path):
            with closing(_readonly(path)) as original, closing(sqlite3.connect(target)) as copied:
                original.backup(copied, pages=128)
                if copied.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                    raise ValueError('candidate database snapshot is invalid')
            shutil.copymode(path, target)
        else:
            shutil.copy2(path, target)
            with target.open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != files[relative]:
                    raise ValueError('candidate file changed while copying')
    for original, target in reversed(directories):
        shutil.copystat(original, target)


def snapshot_state(source, target):
    """Caller holds the serial host lock; source control writers are fenced here."""
    source, target = Path(source).resolve(), Path(target).resolve()
    if source == target or source in target.parents or target in source.parents:
        raise ValueError('upgrade candidate must be separate from source')
    config = json.loads((source / 'candidate.json').read_text())
    project = Path(config['project'])
    if project.is_symlink() or not project.resolve().is_relative_to(source):
        raise ValueError('source project must belong to its candidate')
    state = source / 'state'
    if state.is_symlink():
        raise ValueError('source state must be a real directory')
    if any((target / name).exists() for name in ('state', 'project', 'approval-secret', 'agent-settings.json')):
        raise ValueError('upgrade target already contains state; do not overwrite it')
    with (state / 'maintenance.lock').open('r+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with closing(_readonly(state / 'database/runs.sqlite3')) as db:
            if db.execute("SELECT 1 FROM runs WHERE state NOT IN ('completed','failed') LIMIT 1").fetchone():
                raise ValueError('source has unfinished Runs; stop and reconcile them first')
        with closing(_readonly(state / 'database/executions.sqlite3')) as db:
            if db.execute("SELECT 1 FROM executions WHERE state NOT IN ('succeeded','failed','cancelled','collected','abandoned') LIMIT 1").fetchone():
                raise ValueError('source has unfinished executions; reconcile them first')
        if list((state / 'maintenance/instances').glob('*.json')):
            raise ValueError('source has unfinished instance maintenance')
        state_files, project_files = _files(state), _files(project, project=True)
        _copy_tree(state, target / 'state', state_files)
        _copy_tree(project, target / 'project', project_files, project=True)
        # This signing key is part of control state, not Codex credentials.
        # Preserve historical approval verification without printing the key.
        for name in ('approval-secret', 'agent-settings.json'):
            path = source / name
            if path.is_symlink() or not path.is_file():
                raise ValueError('source control file is unavailable')
            shutil.copyfile(path, target / name)
            (target / name).chmod(0o600)
        if state_files != _files(state) or project_files != _files(project, project=True):
            raise ValueError('source changed during snapshot; discard this incomplete candidate')
    # Historical author/Worker identities remain evidence. Interactive session
    # selection and old client admission never become authority in a new host.
    for filename, table in (('scheduler-bindings.sqlite3', 'scheduler_sessions'),
                            ('scheduler-bindings-clients.sqlite3', 'scheduler_clients')):
        path = target / 'state/database' / filename
        if path.exists():
            with sqlite3.connect(path) as db:
                db.execute('DELETE FROM ' + table)
    return {'source_candidate': str(source), 'source_head': config['head'],
            'state_files': state_files, 'project_files': project_files,
            'session_bindings_copied': False, 'scientific_identities_rewritten': False}


def prepare_upgrade(root):
    try:
        from scripts.installed_candidates import _run_logged
        from scripts.probe_root_host_live import write
    except ModuleNotFoundError:
        from installed_candidates import _run_logged
        from probe_root_host_live import write
    request = json.loads((root / 'upgrade-source.json').read_text())
    installed = Path(request['installed_candidate']).resolve()
    if root == installed or installed in root.parents or root in installed.parents:
        raise ValueError('upgrade candidate must be separate from installed candidate')
    config = json.loads((installed / 'candidate.json').read_text())
    python = Path(config['python']).absolute()
    if not python.is_relative_to(installed) or not python.is_file():
        raise ValueError('installed interpreter must belong to its candidate')
    receipt = snapshot_state(request['source_candidate'], root)
    write(root / 'state-snapshot.json', receipt)
    project = root / 'project'
    plugin_arguments = [arg for name, path in config.get('plugin_configs', {}).items()
                        for arg in ('--plugin-config', name + '=' + path)]
    environment = dict(os.environ)
    environment.pop('PYTHONPATH', None)
    environment.pop('SCIDISCOVERY_ROLE_DIR', None)
    environment['PYTHONNOUSERSITE'] = '1'
    _run_logged([str(python), '-m', 'scidiscovery.artifact_agent.interfaces.cli',
        '--project-root', str(project), '--state-root', str(root / 'state'), 'init', 'codex',
        '--python', str(python), '--control-socket', str(root / 'control.sock'), *plugin_arguments],
        cwd=project, env=environment, timeout=120)
    write(root / 'candidate.json', {**config, 'project': str(project),
        'installation_candidate': str(installed), 'state_source': receipt['source_candidate'],
        'state_source_head': receipt['source_head'], 'b0a_passed': False})
