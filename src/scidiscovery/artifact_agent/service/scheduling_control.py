"""Durable scheduling authority; scientific work retains its own accepted authority.

The maintenance guard precedes the scheduling mutex. The latter covers the entire
Root mutation (including backend admission), so pause/takeover cannot race a
check followed by an external submission. No SQLite transaction spans callbacks.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
import threading
from functools import wraps

from ..schema.refs import ArtifactRef

CONTROL_VERSION = 1
CONTROL_SCHEMA = """
CREATE TABLE IF NOT EXISTS scheduler_progression (
    instance_id TEXT PRIMARY KEY REFERENCES scheduler_instances(instance_id),
    generation INTEGER NOT NULL,
    owner_session TEXT,
    requested_by TEXT,
    state TEXT NOT NULL CHECK(state IN ('active','paused','stopped','pending')),
    mode TEXT NOT NULL CHECK(mode IN ('interactive','background')),
    reason TEXT NOT NULL,
    objective_name TEXT,
    objective_ref_json TEXT,
    config_json TEXT NOT NULL,
    request_fingerprint TEXT,
    host_json TEXT,
    checkpoint_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scheduler_dispatch_intents (
    instance_id TEXT NOT NULL REFERENCES scheduler_instances(instance_id),
    run_id TEXT PRIMARY KEY,
    generation INTEGER NOT NULL,
    owner_session TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""
_LOCAL = threading.local()


def conflict(message):
    from .scheduler_bindings import SchedulerInstanceConflict
    raise SchedulerInstanceConflict(message)


class SchedulingControl:
    @property
    def control_maintenance(self):
        from .instance_maintenance import InstanceMaintenance
        return InstanceMaintenance(self.database_path.parent.parent)

    @contextmanager
    def scheduling_lock(self):
        """Reentrant across service objects on this thread; shared across processes."""
        key = str(self.database_path)
        held = getattr(_LOCAL, 'scheduling', None)
        if held is None:
            held = _LOCAL.scheduling = set()
        if key in held:
            yield
            return
        path = self.database_path.with_suffix('.scheduling.lock')
        mode = self.control_maintenance.mode
        fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, mode)
        try:
            os.fchmod(fd, mode)
            fcntl.flock(fd, fcntl.LOCK_EX)
            held.add(key)
            try:
                yield
            finally:
                held.remove(key)
        finally:
            os.close(fd)

    def progression_status(self, *, instance_id, session_key=None, internal=False):
        self.get_instance(instance_id=instance_id)
        with self._connect() as connection:
            row = connection.execute('SELECT * FROM scheduler_progression WHERE instance_id=?', (instance_id,)).fetchone()
        if row is None:
            return {'state': 'idle', 'mode': 'interactive', 'reason': 'not_started',
                    'can_schedule': False, 'objective_name': None}
        value = dict(row)
        if internal:
            return value
        return {key: value[key] for key in ('state', 'mode', 'reason', 'objective_name')} | {
            'can_schedule': value['state'] == 'active' and value['owner_session'] == session_key,
            'writer': 'this_session' if value['owner_session'] == session_key and session_key else
                      'other_session' if value['owner_session'] else 'none',
            'in_flight': 'Previously accepted Workers and executions retain their authority; their exact Run states remain authoritative.'}

    def _selected(self, instance_id, session_key):
        self.require_active_instance(instance_id=instance_id)
        if session_key is not None and self.session_instance(session_key=session_key) != instance_id:
            conflict('Select this research instance in the management UI before scheduling.')

    def _write_progression(self, connection, instance_id, values):
        from .scheduler_bindings import _timestamp
        values['updated_at'] = _timestamp()
        columns = tuple(values)
        connection.execute('INSERT INTO scheduler_progression(instance_id,' + ','.join(columns) + ') VALUES ('
            + ','.join('?' for _ in range(len(columns)+1)) + ') ON CONFLICT(instance_id) DO UPDATE SET '
            + ','.join(key+'=excluded.'+key for key in columns), (instance_id, *values.values()))

    def progression_command(self, *, instance_id, session_key, command, mode='interactive',
                            objective_name=None, objective_ref=None, expected_generation=None):
        """Shared UI/CLI/MCP control; hidden identities come from trusted transports."""
        if command not in {'start', 'pause', 'resume', 'stop', 'takeover'} or mode not in {'interactive', 'background'}:
            raise ValueError('invalid progression command')
        with self.control_maintenance.guard(instance_id), self.scheduling_lock():
            self._selected(instance_id, session_key)
            session_key = session_key or 'administrative'
            old = self.progression_status(instance_id=instance_id, internal=True)
            exists = old['state'] != 'idle'
            if expected_generation is not None and (not exists or old['generation'] != expected_generation):
                conflict('Scheduling generation changed; reread control status.')
            if exists and old['owner_session'] not in {None, session_key} and command not in {'takeover', 'pause', 'stop'}:
                conflict('Another scheduler owns this instance; explicitly take over first.')
            # Pause and stop are explicit controls available to an authorized reader.
            if command in {'resume', 'takeover'} and exists:
                mode = old['mode'] if command == 'resume' else mode
            if command != 'start' and (objective_name is not None or objective_ref is not None):
                raise ValueError('objective is accepted only by start')
            if command == 'start' and objective_name is not None:
                if objective_ref is None:
                    raise ValueError('start requires the exact objective Artifact')
                ref = ArtifactRef.model_validate(objective_ref)
                bound = self.resolve(instance=instance_id, namespace='artifact', name=objective_name)
                if bound != ref.artifact_id:
                    conflict('Objective must match its exact instance binding.')
                ref_json = ref.canonical_json().decode()
            else:
                ref_json = old.get('objective_ref_json')
                objective_name = old.get('objective_name')
            if mode == 'background' and ref_json is None:
                conflict('Background progression requires a frozen research objective.')
            settings = self.agent_settings(instance_id)
            config = json.dumps(settings, sort_keys=True, separators=(',', ':'))
            fingerprint = hashlib.sha256(json.dumps([mode, objective_name, ref_json, config]).encode()).hexdigest()
            if command == 'start' and exists:
                if old['request_fingerprint'] == fingerprint:
                    return self.progression_status(instance_id=instance_id, session_key=session_key)
                if old['state'] not in {'stopped', 'paused'}:
                    conflict('Pause or stop before changing the frozen objective or configuration.')
            state = {'pause': 'paused', 'stop': 'stopped'}.get(command, 'active' if mode == 'interactive' else 'pending')
            reason = {'pause': 'user_paused', 'stop': 'user_stopped'}.get(command,
                       'interactive' if mode == 'interactive' else 'runtime_unavailable')
            if command in {'pause', 'stop'} and exists:
                mode = old['mode']
            values = dict(generation=old.get('generation', 0)+1,
                requested_by=session_key if command in {'start', 'resume', 'takeover'} else old.get('requested_by'),
                owner_session=session_key if state == 'active' else None,
                state=state, mode=mode, reason=reason, objective_name=objective_name,
                objective_ref_json=ref_json, config_json=config if command == 'start' or not exists else old['config_json'],
                request_fingerprint=fingerprint if command == 'start' or not exists else old['request_fingerprint'],
                host_json=old.get('host_json'), checkpoint_json=old.get('checkpoint_json', '{}'))
            with self._connect() as connection:
                self._write_progression(connection, instance_id, values)
            if state == 'active' and self.client_database_path.exists():
                with self._client_connect() as connection:
                    connection.execute('UPDATE scheduler_clients SET enabled=1 WHERE session_key=?', (session_key,))
            return self.progression_status(instance_id=instance_id, session_key=session_key)

    @contextmanager
    def scheduling_guard(self, *, instance_id, session_key, expected_generation=None):
        with self.control_maintenance.guard(instance_id), self.scheduling_lock():
            self._selected(instance_id, session_key)
            if session_key is not None and not self.client_enabled(session_key=session_key):
                conflict('This research client is paused in the workbench.')
            identity = session_key or 'administrative'
            row = self.progression_status(instance_id=instance_id, internal=True)
            if row['state'] == 'idle':
                # First interactive mutation keeps legacy single-client usage viable.
                self.progression_command(instance_id=instance_id, session_key=session_key, command='start')
                row = self.progression_status(instance_id=instance_id, internal=True)
            if row['state'] != 'active' or row['owner_session'] != identity:
                conflict('Scheduling is paused or owned by another session; use an explicit control command.')
            if self.agent_settings(instance_id) != json.loads(row['config_json']):
                conflict('Configuration changed; pause and explicitly start with the new snapshot before scheduling.')
            if expected_generation is not None and row['generation'] != expected_generation:
                conflict('Stale scheduling generation; reconciliation is required.')
            yield row['generation']

    def record_dispatch_intent(self, *, instance_id, run_id, session_key):
        from .scheduler_bindings import _timestamp
        with self.scheduling_guard(instance_id=instance_id, session_key=session_key) as generation, self._connect() as connection:
            connection.execute('INSERT OR IGNORE INTO scheduler_dispatch_intents VALUES(?,?,?,?,?)',
                (instance_id, run_id, generation, session_key or "administrative", _timestamp()))

    def require_dispatch_intent(self, *, instance_id, run_id, session_key, generation):
        with self._connect() as connection:
            row = connection.execute('SELECT * FROM scheduler_dispatch_intents WHERE run_id=?', (run_id,)).fetchone()
        if row is None or (row['instance_id'], row['owner_session'], row['generation']) != (instance_id, session_key or "administrative", generation):
            conflict('Dispatch intent is absent or stale; reconcile the actual Worker before attaching. Native start state is unknown.')

    def activate_host(self, *, instance_id, source_session, scheduler_session, platform_session, thread_id, expected_generation):
        """Trusted host adapter only; actual platform coordinates must be supplied by it."""
        if not platform_session or platform_session != thread_id:
            raise ValueError('host requires actual Root platform session and thread coordinates')
        self._validate_session_key(scheduler_session)
        with self.control_maintenance.guard(instance_id), self.scheduling_lock():
            self._selected(instance_id, source_session)
            row = self.progression_status(instance_id=instance_id, internal=True)
            if (row.get('generation') != expected_generation or row['state'] != 'pending'
                    or row['mode'] != 'background' or row.get('requested_by') != source_session):
                conflict('Background start is no longer pending at this generation.')
            if row.get('host_json') is not None:
                conflict('Previous host quiescence must be confirmed before activation.')
            if self.agent_settings(instance_id) != json.loads(row['config_json']):
                conflict('Configuration changed before host activation; explicitly start a new snapshot.')
            self.bind_session(session_key=scheduler_session, instance_id=instance_id)
            with self._connect() as connection:
                connection.execute("UPDATE scheduler_progression SET state='active', owner_session=?, generation=generation+1, "
                    "reason='host_active', host_json=? WHERE instance_id=?",
                    (scheduler_session, json.dumps({'platform_session': platform_session, 'thread_id': thread_id}), instance_id))
            return self.progression_status(instance_id=instance_id, internal=True)

    def release_host(self, *, instance_id, platform_session, thread_id):
        """Trusted adapter confirms the exact native Root turn is terminal/stopped.

        App-server client exit or transport loss is not quiescence proof. Worker
        and helper quiescence remains independently required by maintenance.
        """
        with self.control_maintenance.guard(instance_id), self.scheduling_lock():
            row = self.progression_status(instance_id=instance_id, internal=True)
            expected = {'platform_session': platform_session, 'thread_id': thread_id}
            if row['state'] == 'active' or json.loads(row.get('host_json') or 'null') != expected:
                conflict('Host release requires paused control and the exact confirmed host.')
            with self._connect() as connection:
                connection.execute('UPDATE scheduler_progression SET host_json=NULL WHERE instance_id=?', (instance_id,))

    def checkpoint_progression(self, *, instance_id, session_key, expected_generation, checkpoint):
        value = json.dumps(checkpoint, sort_keys=True, allow_nan=False)
        if not isinstance(checkpoint, dict) or len(value.encode()) > 65536:
            raise ValueError('checkpoint must be a bounded control record')
        with self.scheduling_guard(instance_id=instance_id, session_key=session_key, expected_generation=expected_generation), self._connect() as connection:
            connection.execute('UPDATE scheduler_progression SET checkpoint_json=? WHERE instance_id=?', (value, instance_id))


def owned_mutation(method):
    """Protect direct trusted facade consumers as well as MCP routing."""
    @wraps(method)
    def guarded(self, *args, **kwargs):
        with self.scheduling_guard():
            return method(self, *args, **kwargs)
    return guarded
