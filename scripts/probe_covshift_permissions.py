"""Host-only, no-model Covshift protocol preflight; not a trial driver.

Use a reviewed installed Python containing RootPermissions' named-profile adapter.
Only synthetic inputs enter a fresh thread. Worker/helper inheritance and host MCP
isolation are not proven by this probe. No turn or active Goal is submitted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import sysconfig

NAME = 'covshift-canary'
REQUIRED = ('public_read', 'workspace_write', 'private_read_denied', 'auth_read_denied',
    'history_read_denied', 'host_loopback_denied', 'native_child_public_read',
    'native_child_private_read_denied', 'native_child_auth_read_denied',
    'native_child_history_read_denied', 'native_child_host_loopback_denied')


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def evaluate(reply):
    if not isinstance(reply, dict) or type(reply.get('exitCode')) is not int or reply['exitCode'] != 0:
        return False, {}
    try:
        observed = json.loads(reply['stdout'])
    except (KeyError, TypeError, ValueError):
        return False, {}
    checks = {name: isinstance(observed, dict) and observed.get(name) is True for name in REQUIRED}
    return all(checks.values()), checks


def installed_identity(candidate):
    import scidiscovery.platforms.codex_root_host as root_adapter
    import scidiscovery.platforms.codex_progression as factory_adapter
    raw = candidate / 'candidate.json'
    metadata = json.loads(raw.read_text())
    expected_prefix = Path(metadata['python']).parent.parent.resolve()
    origins = {'codex_root_host': Path(root_adapter.__file__).resolve(),
               'codex_progression': Path(factory_adapter.__file__).resolve()}
    if Path(sys.prefix).resolve() != expected_prefix or any(
            not path.is_relative_to(expected_prefix) for path in origins.values()):
        raise ValueError('installed_candidate_import_mismatch')
    return {'candidate': str(candidate), 'metadata_sha256': sha(raw), 'source_commit': metadata['head'],
            'python': sys.executable, 'prefix': sys.prefix,
            'modules': {name: {'origin': str(path), 'sha256': sha(path)} for name, path in origins.items()}}


def permission_diagnostic(method, reply):
    """Only synthetic-profile permission fields; never dump config/auth/providers."""
    if method == 'config/read':
        config = reply.get('config', {})
        selected = config.get('permissions', {}).get(NAME, {})
        if not isinstance(selected, dict):
            return {'selected_profile_type': type(selected).__name__}
        network = selected.get('network', {})
        # Proxy/domain/socket details can contain credentials. Retain shape and
        # equality fingerprints, while safe booleans/nulls remain diagnostic.
        safe_network = {key: value if value is None or type(value) is bool else
            {'type': type(value).__name__, 'sha256': hashlib.sha256(
                json.dumps(value, sort_keys=True).encode()).hexdigest()}
            for key, value in network.items()} if isinstance(network, dict) else None
        return {'default_permissions': config.get('default_permissions'),
            'approval_policy': config.get('approval_policy'),
            'selected_profile': {'keys': sorted(selected), 'extends': selected.get('extends'),
                'workspace_roots': selected.get('workspace_roots'),
                'description_present': selected.get('description') is not None,
                'filesystem': selected.get('filesystem'), 'network': safe_network}}
    if method in ('thread/start', 'thread/resume'):
        return {key: reply.get(key) for key in ('activePermissionProfile', 'approvalPolicy', 'sandbox')}
    if method.startswith('thread/goal/'):
        goal = reply.get('goal')
        return {'goal': {key: goal.get(key) for key in ('status', 'tokensUsed', 'timeUsedSeconds')}
                if isinstance(goal, dict) else None}
    return None


def prepare(root, native, native_sha):
    if root.parent != Path('/tmp') or not root.name.startswith('scid-covshift-'):
        raise ValueError('require a new direct /tmp/scid-covshift-* directory')
    if not native.is_file() or sha(native) != native_sha:
        raise ValueError('exact native Codex binary changed')
    root.mkdir(mode=0o700)
    for name in ('public', 'host-private', 'host-codex-home', 'host-tmp'):
        (root / name).mkdir(mode=0o700)
    home = root / 'host-codex-home'
    (home / 'tmp/arg0').mkdir(mode=0o700, parents=True)
    (home / 'sessions').mkdir(mode=0o700)
    for name, text in (('public/input.txt', 'public canary\n'),
                       ('host-private/answer-canary.txt', 'synthetic private\n'),
                       ('host-codex-home/auth-canary.json', '{"synthetic":true}\n'),
                       ('host-codex-home/sessions/history-canary.txt', 'synthetic history\n')):
        (root / name).write_text(text)
    shutil.copyfile(Path(__file__).with_name('acceptance') / 'fixtures/covshift_permissions/canary.py',
                    root / 'public/canary.py')
    python = Path(sys._base_executable)
    paths = {':root': 'deny', ':minimal': 'read', str(root / 'public'): 'write',
             str(home / 'tmp/arg0'): 'read', str(native): 'read',
             str(python): 'read', str(python.resolve()): 'read',
             sysconfig.get_path('stdlib'): 'read'}
    if sysconfig.get_config_var('Py_ENABLE_SHARED'):
        library = Path(sysconfig.get_config_var('LIBDIR')) / sysconfig.get_config_var('INSTSONAME')
        if not library.is_file():
            raise ValueError('shared Python runtime library unavailable')
        paths[str(library)] = 'read'
    definition = {'filesystem': paths, 'network': {'enabled': False}}
    lines = ['default_permissions = ' + json.dumps(NAME), 'approval_policy = "never"',
             '[permissions.' + NAME + '.filesystem]']
    lines.extend(json.dumps(key) + ' = ' + json.dumps(value) for key, value in paths.items())
    lines.extend(['[permissions.' + NAME + '.network]', 'enabled = false'])
    (home / 'config.toml').write_text('\n'.join(lines) + '\n')
    (root / 'manifest.json').write_text(json.dumps({'native': str(native), 'native_sha256': native_sha,
        'python': str(python), 'definition': definition, 'no_model': True}, indent=2) + '\n')


def probe(root):
    import scidiscovery.platforms.codex_root_host as adapter
    from scidiscovery.platforms.codex_app_server import AppServer, HostLimits
    manifest = json.loads((root / 'manifest.json').read_text())
    home, public = root / 'host-codex-home', root / 'public'
    private = [root / 'host-private/answer-canary.txt', home / 'auth-canary.json',
               home / 'sessions/history-canary.txt']
    checks = {}
    result = {'status': 'fail', 'qualification': 'fresh Root protocol and standalone native command only',
        'worker_helper_paths_verified': [], 'turns_started': 0, 'active_goal_started': False,
        'instance_bound': False, 'authenticated_account_verified': False,
        'checks': checks}
    connection = listener = None
    turn_events = []
    def event(message):
        if message.get('method') == 'turn/started':
            turn_events.append(message)
            raise RuntimeError('unexpected_native_turn')
    def observe(connection):
        rpc = connection.rpc
        def call(method, params):
            result['phase'] = method
            reply = rpc(method, params)
            snapshot = permission_diagnostic(method, reply)
            if snapshot is not None:
                result.setdefault('permission_diagnostics', []).append({'method': method, **snapshot})
            return reply
        connection.rpc = call
        return connection
    try:
        checks['synthetic_private_files_exist_on_host'] = all(p.is_file() and not p.is_symlink() for p in private)
        checks['native_binary_matches_frozen'] = sha(Path(manifest['native'])) == manifest['native_sha256']
        result['installed_identity'] = installed_identity(Path(manifest['installed_candidate']))
        checks['installed_metadata_matches_frozen'] = (
            result['installed_identity']['metadata_sha256'] == manifest['candidate_metadata_sha256'])
        if not all(checks.values()):
            raise RuntimeError('host_inputs_changed')
        listener = socket.socket(); listener.bind(('127.0.0.1', 0)); listener.listen(2)
        port = listener.getsockname()[1]
        with socket.create_connection(('127.0.0.1', port), timeout=1):
            peer, _ = listener.accept(); peer.close()
        checks['host_loopback_endpoint_live'] = True
        permissions = adapter.RootPermissions(network_access=False, permission_profile=NAME,
            profile_definition=json.dumps(manifest['definition']))
        env = {'PATH': os.environ['PATH'], 'LANG': 'C.UTF-8', 'CODEX_HOME': str(home),
               'TMPDIR': str(root / 'host-tmp')}
        with (root / 'app-server.stderr').open('wb') as stderr:
            connection = AppServer.launch([manifest['native'], 'app-server', '--stdio'], cwd=public,
                environment=env, stderr=stderr, on_event=event,
                limits=HostLimits(rpc_timeout_seconds=30, frame_bytes=1_000_000))
            observe(connection)
            host = adapter.CodexRootHost(connection, permissions)
            host.initialize(cwd=str(public), expected_config={})
            arg0 = home / 'tmp/arg0'
            directories = list(arg0.iterdir())
            if len(directories) > 8:
                raise RuntimeError('runtime_alias_coverage_exceeded')
            aliases = [p / 'codex-linux-sandbox' for p in directories
                       if p.name.startswith('codex-arg0') and (p / 'codex-linux-sandbox').is_symlink()]
            checks['exact_runtime_alias'] = (len(aliases) == 1 and
                aliases[0].resolve(strict=True) == Path(manifest['native']).resolve(strict=True))
            checks['runtime_arg0_owner_only'] = arg0.stat().st_uid == os.getuid() and arg0.stat().st_mode & 0o777 == 0o700
            if not all(checks.values()):
                raise RuntimeError('runtime_helper_unconfirmed')
            identity = host.open_root(cwd=str(public))
            result['thread_id'] = identity.thread_id
            checks['fresh_root_named_profile'] = True
            connection.rpc('thread/goal/set', {'threadId': identity.thread_id,
                'objective': 'Synthetic no-model permission preflight; remain paused.', 'status': 'paused'})
            goal = connection.rpc('thread/goal/get', {'threadId': identity.thread_id}).get('goal')
            checks['paused_goal_zero_usage'] = (isinstance(goal, dict) and goal.get('threadId') == identity.thread_id
                and goal.get('status') == 'paused' and goal.get('tokensUsed') == 0 and goal.get('timeUsedSeconds') == 0)
            if not checks['paused_goal_zero_usage']:
                raise RuntimeError('paused_goal_unconfirmed')
            connection.rpc('thread/goal/clear', {'threadId': identity.thread_id})
            checks['goal_cleared'] = connection.rpc('thread/goal/get', {'threadId': identity.thread_id}).get('goal') is None
            connection.close()
            connection = AppServer.launch([manifest['native'], 'app-server', '--stdio'], cwd=public,
                environment=env, stderr=stderr, on_event=event,
                limits=HostLimits(rpc_timeout_seconds=30, frame_bytes=1_000_000))
            observe(connection)
            resumed = adapter.CodexRootHost(connection, permissions)
            resumed.initialize(cwd=str(public), expected_config={})
            resumed.open_root(cwd=str(public), prior=identity)
            checks['same_root_resume_named_profile'] = True
            directories = list(arg0.iterdir())
            aliases = [p / 'codex-linux-sandbox' for p in directories
                       if p.name.startswith('codex-arg0') and (p / 'codex-linux-sandbox').is_symlink()]
            checks['resumed_exact_runtime_alias'] = (len(directories) <= 8 and len(aliases) == 1 and
                aliases[0].resolve(strict=True) == Path(manifest['native']).resolve(strict=True))
            if not checks['resumed_exact_runtime_alias']:
                raise RuntimeError('resumed_runtime_helper_unconfirmed')
            reply = connection.rpc('command/exec', {'command': [manifest['python'], '-I', str(public / 'canary.py'),
                '--parent', str(public / 'input.txt'), *map(str, private), str(port)], 'cwd': str(public),
                'permissionProfile': NAME, 'timeoutMs': 10000, 'outputBytesCap': 8192})
            result['command_exec'] = reply
            passed, canary_checks = evaluate(reply); checks.update(canary_checks)
            checks['no_turn_observed'] = not turn_events
            result['status'] = 'pass' if passed and all(checks.values()) else 'fail'
    except Exception as error:
        result.update(reason=getattr(error, 'code', str(error)), exception=type(error).__name__,
                      rpc_method=getattr(error, 'method', None), rpc_code=getattr(error, 'rpc_code', None))
    finally:
        if listener:
            listener.close()
        if connection:
            try:
                connection.close()
            except Exception as error:
                result.update(status='fail', close_error=type(error).__name__)
        (root / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    return 0 if result['status'] == 'pass' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--codex-native', type=Path)
    parser.add_argument('--native-sha256')
    parser.add_argument('--installed-candidate', type=Path)
    parser.add_argument('--lease-fd', type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = args.output.absolute()
    if args.lease_fd is not None:
        os.close(args.lease_fd)  # Parent keeps supervision lock; never expose it to native children.
        return probe(root)
    if not args.codex_native or not args.native_sha256 or not args.installed_candidate:
        parser.error('require installed candidate, exact native binary and frozen SHA256')
    candidate = args.installed_candidate.resolve(strict=True)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts import run_tests as guard
    prepare(root, args.codex_native.resolve(strict=True), args.native_sha256)
    manifest = json.loads((root / 'manifest.json').read_text())
    manifest['installed_candidate'] = str(candidate)
    manifest['candidate_metadata_sha256'] = sha(candidate / 'candidate.json')
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    out = root / 'supervision'; out.mkdir(mode=0o700)
    limits = json.loads(guard.DEFAULT_CONFIG.read_text())['limits']
    env = dict(os.environ)
    for key in ('PYTHONPATH', 'SCIDISCOVERY_ROLE_DIR'):
        env.pop(key, None)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS',
                'TOKIO_WORKER_THREADS', 'RAYON_NUM_THREADS'):
        env[key] = '1'
    with guard.serial_lock() as lease:
        command = [sys.executable, '-I', str(Path(__file__).resolve()), '--output', str(root),
                   '--lease-fd', str(lease.fileno())]
        (out / 'command.json').write_text(json.dumps({'command': command, 'limits': limits}, indent=2) + '\n')
        resource = guard.run_one(command, env, limits, out, lease.fileno())
        (out / 'resource.json').write_text(json.dumps(resource, indent=2) + '\n')
    try:
        passed = json.loads((root / 'result.json').read_text())['status'] == 'pass'
    except (OSError, ValueError, KeyError):
        passed = False
    return 0 if passed and resource['returncode'] == 0 and resource['stop_reason'] == 'exited' else 1


if __name__ == '__main__':
    raise SystemExit(main())
