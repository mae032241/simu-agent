"""Client presence is transport-owned, independent of scientific work and history."""
import json
import os
from pathlib import Path
import select
import sqlite3
import subprocess
import sys
import time

import pytest

from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService

A = 'sch_' + 'a' * 32
B = 'sch_' + 'b' * 32


def test_presence_expiry_disconnect_and_legacy_migration(tmp_path):
    bindings = SchedulerBindingService(tmp_path / 'bindings.sqlite3')
    instance = bindings.create_instance_and_bind_session(session_key=A, name='kept', title='Kept', objective='Keep records')
    with sqlite3.connect(bindings.client_database_path) as db:
        db.execute('CREATE TABLE scheduler_clients (session_key TEXT PRIMARY KEY, enabled INTEGER, requested_at TEXT)')
        db.execute('INSERT INTO scheduler_clients VALUES (?, 0, ?)', (A, 'old'))
    assert bindings.clients() == []  # Old records do not acquire invented liveness.
    assert not bindings.client_enabled(session_key=A)
    bindings.client_heartbeat(session_key=B)
    assert bindings.clients() == []  # Discovery/heartbeat is not registration.
    bindings.register_client(session_key=A)
    bindings.client_heartbeat(session_key=A)
    assert not bindings.clients()[0]['enabled']
    bindings.set_client_enabled(session_key=A, enabled=True, expected=False)
    assert bindings.active_clients(instance_id=instance.instance_id) == (A,)
    with sqlite3.connect(bindings.client_database_path) as db:
        db.execute('UPDATE scheduler_clients SET last_seen=0')
    assert bindings.clients() == []
    assert bindings.active_clients(instance_id=instance.instance_id) == ()
    bindings.client_heartbeat(session_key=A)
    assert len(bindings.clients()) == 1
    bindings.disconnect_client(session_key=A)
    bindings.client_heartbeat(session_key=A)  # Late heartbeat cannot undo disconnect.
    assert bindings.clients() == []
    assert bindings.session_instance(session_key=A) == instance.instance_id
    assert bindings.get_instance(instance_id=instance.instance_id).objective == 'Keep records'


def eventually(predicate):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.02)
    assert predicate()


@pytest.mark.process_e2e
@pytest.mark.parametrize('ending', ['eof', 'terminate', 'kill', 'two_clients'])
def test_real_proxy_idle_presence_disconnect_and_restart(tmp_path, ending):
    socket = tmp_path / 'control.sock'
    database = tmp_path / 'bindings.sqlite3'
    bindings = SchedulerBindingService(database)
    env = dict(os.environ, PYTHONPATH=str(Path('src').resolve()))
    daemon_code = '''
import sys
from pathlib import Path
from scidiscovery.plugin_runtime.transport import UnixSocketDaemon
from scidiscovery.artifact_agent.interfaces.mcp_daemon import RootBrokerRouter
from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService
class Router:
    def handle(self, request):
        return {'jsonrpc':'2.0','id':request.get('id'),'result':{}}
UnixSocketDaemon(Path(sys.argv[1]), RootBrokerRouter(lambda _: Router(),
    client_bindings=SchedulerBindingService(sys.argv[2]))).serve_forever()
'''
    def start_daemon():
        return subprocess.Popen([sys.executable, '-c', daemon_code, str(socket), str(database)],
                                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    daemon = start_daemon()
    proxy = second = None
    try:
        eventually(socket.exists)
        command = [sys.executable, '-c',
            'from scidiscovery.artifact_agent.interfaces import mcp_proxy as p; '
            'p.HEARTBEAT_INTERVAL_SECONDS=.05; p.LIFECYCLE_TIMEOUT_SECONDS=.3; raise SystemExit(p.main())',
            '--socket', str(socket)]
        proxy = subprocess.Popen(command, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def rpc(method, client=proxy):
            request = {'jsonrpc': '2.0', 'id': 1, 'method': method}
            if method == 'tools/call':
                identity = f'fixture-{client.pid}'
                request['params'] = {'name': 'scid_call', 'arguments': {'name': 'instance_current'},
                    '_meta': {'x-codex-turn-metadata': {'session_id': identity,
                        'thread_id': identity, 'thread_source': 'user'}}}
            client.stdin.write((json.dumps(request)+'\n').encode())
            client.stdin.flush()
            assert select.select([client.stdout], [], [], 5)[0]
            assert 'result' in json.loads(client.stdout.readline())
        rpc('initialize')
        rpc('tools/list')
        assert bindings.clients() == []
        rpc('tools/call')
        row = bindings.clients()[0]
        key = row['session_key']
        bindings.set_client_enabled(session_key=key, enabled=False, expected=True)
        with sqlite3.connect(bindings.client_database_path) as db:
            db.execute('UPDATE scheduler_clients SET last_seen=0')
        eventually(lambda: len(bindings.clients()) == 1)  # No new tool call: idle stdin still heartbeats.
        assert not bindings.client_enabled(session_key=key)
        if ending == 'eof':
            daemon.terminate(); daemon.wait(timeout=5)
            socket.unlink(missing_ok=True)
            daemon = start_daemon()
            eventually(socket.exists)
            with sqlite3.connect(bindings.client_database_path) as db:
                db.execute('UPDATE scheduler_clients SET last_seen=0')
            eventually(lambda: len(bindings.clients()) == 1)
            assert not bindings.client_enabled(session_key=key)
            proxy.stdin.close()
        elif ending == 'two_clients':
            second = subprocess.Popen(command, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            rpc('tools/call', second)
            assert len(bindings.clients()) == 2
            other = next(row['session_key'] for row in bindings.clients() if row['session_key'] != key)
            assert bindings.client_enabled(session_key=other)
            assert not bindings.client_enabled(session_key=key)
            proxy.stdin.close()
        elif ending == 'terminate':
            proxy.terminate()
        else:
            proxy.kill()
        proxy.wait(timeout=5)
        if ending == 'kill':
            with sqlite3.connect(bindings.client_database_path) as db:
                db.execute('UPDATE scheduler_clients SET last_seen=0')  # Deterministically age abnormal loss.
        if second is not None:
            assert [row['session_key'] for row in bindings.clients()] == [other]
            assert bindings.clear_offline_clients() == 1
            assert bindings.client_enabled(session_key=other)
            with sqlite3.connect(bindings.client_database_path) as db:
                db.execute('UPDATE scheduler_clients SET last_seen=0')
            eventually(lambda: len(bindings.clients()) == 1)
        else:
            eventually(lambda: bindings.clients() == [])
        assert proxy.stdout.read() == b''  # Lifecycle traffic never leaks into model MCP output.
    finally:
        if second is not None and second.poll() is None:
            second.terminate(); second.wait(timeout=5)
        if proxy is not None and proxy.poll() is None:
            proxy.kill(); proxy.wait(timeout=5)
        daemon.terminate(); daemon.wait(timeout=5)


def test_cleanup_can_be_first_access_to_legacy_sidecar(tmp_path):
    bindings = SchedulerBindingService(tmp_path / 'bindings.sqlite3')
    instance = bindings.create_instance_and_bind_session(session_key=A, name='legacy', title='Kept', objective='Keep')
    with sqlite3.connect(bindings.client_database_path) as db:
        db.execute('CREATE TABLE scheduler_clients (session_key TEXT PRIMARY KEY, enabled INTEGER, requested_at TEXT)')
        db.execute('INSERT INTO scheduler_clients VALUES (?, 0, ?)', (A, 'old'))
    assert bindings.clear_offline_clients() == 1
    assert bindings.clients() == []
    assert bindings.session_instance(session_key=A) is None
    assert bindings.get_instance(instance_id=instance.instance_id) == instance
