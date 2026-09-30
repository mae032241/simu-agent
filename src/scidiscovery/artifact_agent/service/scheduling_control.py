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
from .scientific_progress import PROGRESS_SCHEMA
from .maintenance import MaintenanceBusy
from ..storage.control_io import control_io_nonblocking

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
CONTROL_SCHEMA += PROGRESS_SCHEMA
_LOCAL = threading.local()


def conflict(message):
    from .scheduler_bindings import SchedulerInstanceConflict
    raise SchedulerInstanceConflict(message)


def is_goal_anchor(artifact):
    """Starting control needs original intent, not prior scientific qualification."""
    from .intake import USER_TEXT_MEDIA_TYPE, USER_TEXT_SOURCE_ORIGIN
    return (artifact.schema_id == 'scidiscovery.research-objective.v1' or
            (artifact.kind == 'source_text' and artifact.schema_id == 'opaque'
             and artifact.media_type == USER_TEXT_MEDIA_TYPE
             and artifact.labels.get('source_origin') == USER_TEXT_SOURCE_ORIGIN))


def record_progression_notice(checkpoint, *, objective, state, reason):
    """Coalesce durable pull notifications on writes, never on status reads.

    Delivery/read acknowledgements are not provided by this transport. Retaining
    a notice cannot authorize work or turn a task result into a goal conclusion.
    """
    from .scheduler_bindings import _timestamp
    report = checkpoint.get('report') or {}
    question = report.get('question') if reason == 'user_question' else None
    category = ('user_decision' if question else 'status' if reason in {
        'interactive', 'host_active', 'user_paused', 'user_stopped', 'goal_completed'
    } else 'system_wait')
    identity = hashlib.sha256(json.dumps([objective, category, reason, question],
        sort_keys=True).encode()).hexdigest()
    notices = checkpoint.setdefault('notices', [])
    if not any(item['id'] == identity for item in notices):
        notices.append(dict(id=identity, category=category, reason=reason,
            state=state, question_preview=question[:256] if question else None,
            question_truncated=bool(question and len(question) > 256), recorded_at=_timestamp()))
        if len(notices) > 16:
            checkpoint['notices_omitted'] = checkpoint.get('notices_omitted', 0) + len(notices) - 16
            del notices[:-16]
    checkpoint['current_notice'] = identity


def progression_status_view(value, *, session_key=None):
    """Project one captured control row without a second database read."""
    if "checkpoint_json" not in value:
        return value
    checkpoint = json.loads(value['checkpoint_json'])
    from ...platforms.codex_usage import usage_summary
    records = list(checkpoint.get('usage_records', {}).values())
    usage = usage_summary(records) if records else checkpoint.get('usage_summary', usage_summary([]))
    budget = dict(checkpoint.get('budget') or {})
    stop_snapshot = checkpoint.get('stop_snapshot_tokens', budget.get('observed_tokens')
        if value['reason'] in {'budget_exhausted', 'resource_limit'} else None)
    budget.update(observed_tokens=sum(sum(record['counted_tokens'][key] for key in
        ('input_tokens', 'output_tokens')) for record in records) if records else None,
        stop_snapshot_tokens=stop_snapshot,
        token_coverage=usage['coverage'])
    config = json.loads(value.get('config_json') or '{}')
    limits = config.get('effective', {}).get('progression')
    if limits and value['mode'] == 'background':
        from .progression_budget import token_budget
        budget.update(token_budget(checkpoint, limits))
    return {key: value[key] for key in ('state', 'mode', 'reason', 'objective_name')} | {
        'can_schedule': value['state'] == 'active' and value['owner_session'] == session_key,
        'writer': 'this_session' if value['owner_session'] == session_key and session_key else
                  'other_session' if value['owner_session'] else 'none',
        'report': checkpoint.get('report'),
        'last_report': checkpoint.get('last_report'),
        'resources': checkpoint.get('resources'),
        'fault_code': checkpoint.get('fault_code'),
        'platform_requests': [{key: item[key] for key in ('method', 'state', 'questions', 'elicitation', 'omitted') if key in item}
            for item in checkpoint.get('platform_requests', [])],
        'last_command': checkpoint.get('last_command'),
        'notifications': {
            'items': checkpoint.get('notices', []),
            'current_id': checkpoint.get('current_notice') if value['reason'] != 'archive_restored' else None,
            'omitted': checkpoint.get('notices_omitted', 0),
            'delivery': 'pull_only', 'read_status': 'not_recorded'},
        'messages': [dict(name=v['name'], application='next_safe_turn',
            processed=v in checkpoint.get('processed_snapshot', {}).get('messages', []))
            for v in checkpoint.get('messages', [])],
        'budget': budget,
        'usage': usage,
        'runtime_status': checkpoint.get('runtime_status', 'not_connected'),
        'in_flight': 'Previously accepted Workers and executions retain their authority; their exact Run states remain authoritative.'}


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
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | (fcntl.LOCK_NB if control_io_nonblocking() else 0))
            except BlockingIOError as error:
                raise MaintenanceBusy("scheduling control is busy") from error
            held.add(key)
            try:
                yield
            finally:
                held.remove(key)
        finally:
            os.close(fd)

    def control_settings(self, instance_id):
        from ...agent_execution_settings import effective_settings
        value = self.agent_settings(instance_id)
        return {**value, "effective": effective_settings(self.global_settings, value["settings"])}

    def next_background_progression(self):
        """Select one eligible host without bypassing an unresolved native writer."""
        with self._connect() as connection:
            outstanding = connection.execute(
                'SELECT instance_id,state FROM scheduler_progression WHERE host_json IS NOT NULL'
            ).fetchall()
            if any(row['state'] not in {'active', 'pending'} for row in outstanding):
                return None
            rows = connection.execute(
                "SELECT * FROM scheduler_progression WHERE mode='background' "
                "AND state IN ('active','pending') ORDER BY updated_at,instance_id"
            )
            for row in rows:
                if outstanding and row['instance_id'] != outstanding[0]['instance_id']:
                    continue
                if json.loads(row['config_json']).get('effective', {}).get('progression', {}).get('enabled'):
                    return dict(row)
        return None

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
        return progression_status_view(value, session_key=session_key)

    def _selected(self, instance_id, session_key):
        self.require_active_instance(instance_id=instance_id)
        if session_key is not None and self.session_instance(session_key=session_key) != instance_id:
            conflict('Select this research instance in the management UI before scheduling.')

    def _write_progression(self, connection, instance_id, values):
        from .scheduler_bindings import _timestamp
        if len(values.get('checkpoint_json', '').encode()) > 65536:
            conflict('Control checkpoint capacity reached.')
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
            settings = self.control_settings(instance_id) if mode == 'background' else {}
            config = json.dumps(settings, sort_keys=True, separators=(',', ':'))
            fingerprint = hashlib.sha256(json.dumps([mode, objective_name, ref_json, config]).encode()).hexdigest()
            if (command == 'start' and exists and old['request_fingerprint'] == fingerprint
                    and (old.get('requested_by') == session_key or old['owner_session'] == session_key
                         or old['state'] in {'paused', 'stopped'})):
                # The original user can retry after a native host acquired ownership.
                # Returning a paused/stopped task does not resume it or change authority.
                return self.progression_status(instance_id=instance_id, session_key=session_key)
            if exists and old['owner_session'] not in {None, session_key} and command not in {'takeover', 'pause', 'stop'}:
                conflict('Another scheduler owns this instance; explicitly take over first.')
            if (command == 'start' and exists and old['state'] not in {'stopped', 'paused'}
                    and old.get('objective_ref_json') is not None):
                conflict('Pause or stop before changing the frozen objective or configuration.')
            state = {'pause': 'paused', 'stop': 'stopped'}.get(command, 'active' if mode == 'interactive' else 'pending')
            reason = {'pause': 'user_paused', 'stop': 'user_stopped'}.get(command,
                       'interactive' if mode == 'interactive' else 'runtime_unavailable')
            if command in {'pause', 'stop'} and exists:
                mode = old['mode']
            checkpoint = json.loads(old.get('checkpoint_json', '{}'))
            if command == 'start' and old.get('objective_ref_json') != ref_json:
                checkpoint['last_report'] = checkpoint.get('report') or checkpoint.get('last_report')
                checkpoint['report'] = None
                checkpoint['relevant_runs'] = {}
                checkpoint.pop('relevant_runs_objective_ref', None)
            checkpoint['last_command'] = dict(command=command, state=state, reason=reason,
                mode=mode, generation=old.get('generation', 0)+1)
            record_progression_notice(checkpoint, objective=ref_json, state=state, reason=reason)
            values = dict(generation=old.get('generation', 0)+1,
                requested_by=session_key if command in {'start', 'resume', 'takeover'} else old.get('requested_by'),
                owner_session=session_key if state == 'active' else None,
                state=state, mode=mode, reason=reason, objective_name=objective_name,
                objective_ref_json=ref_json, config_json=config if command == 'start' or not exists else old['config_json'],
                request_fingerprint=fingerprint if command == 'start' or not exists else old['request_fingerprint'],
                host_json=old.get('host_json'), checkpoint_json=json.dumps(checkpoint))
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
            if row['mode'] == 'background' and self.control_settings(instance_id) != json.loads(row['config_json']):
                conflict('Configuration changed; pause and explicitly start with the new snapshot before scheduling.')
            if expected_generation is not None and row['generation'] != expected_generation:
                conflict('Stale scheduling generation; reconciliation is required.')
            yield row['generation']

    def prepare_admission(self, *, instance_id, session_key, name, logical_name, revision,
                          fingerprint, output_fingerprint, scientific_signature):
        with self.scheduling_guard(instance_id=instance_id, session_key=session_key), self._connect() as db:
            row = db.execute('SELECT * FROM scheduler_progression WHERE instance_id=?', (instance_id,)).fetchone()
            from .scientific_progress import shadow_policy
            if row['mode'] != 'background' and shadow_policy(row)['progress_mode'] != 'assist':
                return
            checkpoint = json.loads(row['checkpoint_json'])
            admissions = checkpoint.setdefault('admissions', {})
            if any(v['state'] == 'prepared' for v in admissions.values()):
                conflict('A prior task admission is unresolved; reconcile it before creating more work.')
            if name in admissions:
                conflict('Prior task admission must be reconciled by exact identity; do not replay creation.')
            limits = json.loads(row['config_json'])['effective']['progression']
            if len(admissions) >= limits['max_tasks']:
                conflict('Frozen task admission budget exhausted.')
            from .progression_budget import require_task_budget
            require_task_budget(checkpoint, limits)
            from .scientific_progress import observe_deliveries, assist_transition
            observe_deliveries(db, row, checkpoint, boundary='next_task_admission')
            progress_stop = assist_transition(db, row, checkpoint, event='admission', admission=name)
            if progress_stop:
                if progress_stop == 'scientific_progress_persistent_gap':
                    self._pause_progress(db, row, checkpoint, progress_stop)
                # Keep consumption and cause state even though admission fails.
                db.commit()
                conflict(progress_stop)
            admissions[name] = dict(logical_name=logical_name, revision=revision,
                fingerprint=fingerprint, output_fingerprint=output_fingerprint, scientific_signature=scientific_signature,
                objective_ref=json.loads(row['objective_ref_json']) if row['objective_ref_json'] else None, state='prepared')
            value = json.dumps(checkpoint)
            if len(value.encode()) > 65536:
                conflict('Control checkpoint capacity reached.')
            db.execute('UPDATE scheduler_progression SET checkpoint_json=? WHERE instance_id=?', (value, instance_id))

    def _pause_progress(self, db, row, checkpoint, reason):
        record_progression_notice(checkpoint, objective=row['objective_ref_json'], state='paused', reason=reason)
        db.execute("UPDATE scheduler_progression SET state='paused',owner_session=NULL,reason=?,"
            "generation=generation+1,checkpoint_json=? WHERE instance_id=?",
            (reason, json.dumps(checkpoint), row['instance_id']))

    def progress_assist_boundary(self, *, instance_id, event='boundary'):
        with self.control_maintenance.guard(instance_id), self.scheduling_lock(), self._connect() as db:
            row = db.execute('SELECT * FROM scheduler_progression WHERE instance_id=?', (instance_id,)).fetchone()
            if row is None or row['mode'] != 'background' or row['state'] != 'active':
                return None
            from .scientific_progress import assist_transition
            checkpoint = json.loads(row['checkpoint_json'])
            reason = assist_transition(db, row, checkpoint, event=event)
            if reason == 'scientific_progress_persistent_gap':
                self._pause_progress(db, row, checkpoint, reason)
            return reason

    def record_goal_binding(self, *, instance_id, session_key, namespace, name, object_id):
        with self.scheduling_guard(instance_id=instance_id, session_key=session_key), self._connect() as db:
            row = db.execute('SELECT * FROM scheduler_progression WHERE instance_id=?', (instance_id,)).fetchone()
            from .scientific_progress import shadow_policy
            if row['mode'] != 'background' and shadow_policy(row)['progress_mode'] != 'assist':
                return
            checkpoint = json.loads(row['checkpoint_json'])
            if namespace == 'run':
                admission = checkpoint.get('admissions', {}).get(name)
                if admission is None:
                    conflict('Background Run has no preceding durable admission intent.')
                admission.update(state='accepted', run_id=object_id)
            elif namespace == 'approval':
                names = checkpoint.setdefault('approval_names', [])
                if name not in names:
                    if len(names) >= 32:
                        conflict('Goal approval observation capacity reached.')
                    names.append(name)
            value = json.dumps(checkpoint)
            if len(value.encode()) > 65536:
                conflict('Control checkpoint capacity reached.')
            db.execute('UPDATE scheduler_progression SET checkpoint_json=? WHERE instance_id=?', (value, instance_id))

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
            with self._connect() as db:
                other = db.execute('SELECT 1 FROM scheduler_progression WHERE instance_id!=? AND host_json IS NOT NULL LIMIT 1', (instance_id,)).fetchone()
            if other:
                conflict('Another autonomous native host has not been quiesced; runtime is serial.')
            if self.control_settings(instance_id) != json.loads(row['config_json']):
                conflict('Configuration changed before host activation; explicitly start a new snapshot.')
            self.bind_session(session_key=scheduler_session, instance_id=instance_id)
            with self._connect() as connection:
                connection.execute("UPDATE scheduler_progression SET state='active', owner_session=?, generation=generation+1, "
                    "reason='host_active', host_json=? WHERE instance_id=?",
                    (scheduler_session, json.dumps({'platform_session': platform_session, 'thread_id': thread_id}), instance_id))
            return self.progression_status(instance_id=instance_id, internal=True)

    def reconnect_host(self, *, instance_id, scheduler_session, platform_session, thread_id, expected_generation):
        """Restore only the exact persisted native host after platform corroboration."""
        expected = dict(platform_session=platform_session, thread_id=thread_id)
        if not platform_session or platform_session != thread_id:
            raise ValueError('actual Root coordinates required')
        with self.control_maintenance.guard(instance_id), self.scheduling_lock():
            row = self.progression_status(instance_id=instance_id, internal=True)
            if (row.get('generation') != expected_generation or row['mode'] != 'background'
                    or row['state'] not in {'active', 'pending'} or json.loads(row['host_json'] or 'null') != expected):
                conflict('Recorded host ownership changed; reconciliation required.')
            if self.control_settings(instance_id) != json.loads(row['config_json']):
                conflict('Effective configuration changed; explicitly restart with a new snapshot.')
            self.bind_session(session_key=scheduler_session, instance_id=instance_id)
            with self._connect() as db:
                db.execute("UPDATE scheduler_progression SET owner_session=?,state='active',generation=generation+1 WHERE instance_id=?", (scheduler_session, instance_id))
            return self.progression_status(instance_id=instance_id, internal=True)

    def release_host(self, *, instance_id, platform_session, thread_id):
        """Trusted adapter confirms the exact native Root turn is terminal/stopped.

        App-server client exit or transport loss is not quiescence proof. Worker
        and helper quiescence remains independently required by maintenance.
        """
        with self.control_maintenance.guard(instance_id), self.scheduling_lock():
            row = self.progression_status(instance_id=instance_id, internal=True)
            expected = {'platform_session': platform_session, 'thread_id': thread_id}
            if (row['state'] == 'active' and row['mode'] == 'background') or json.loads(row.get('host_json') or 'null') != expected:
                conflict('Host release requires inactive background control and the exact confirmed host.')
            with self._connect() as connection:
                connection.execute('UPDATE scheduler_progression SET host_json=NULL WHERE instance_id=?', (instance_id,))

    def checkpoint_progression(self, *, instance_id, session_key, expected_generation, checkpoint):
        value = json.dumps(checkpoint, sort_keys=True, allow_nan=False)
        if not isinstance(checkpoint, dict) or len(value.encode()) > 65536:
            raise ValueError('checkpoint must be a bounded control record')
        with self.scheduling_guard(instance_id=instance_id, session_key=session_key, expected_generation=expected_generation), self._connect() as connection:
            connection.execute('UPDATE scheduler_progression SET checkpoint_json=? WHERE instance_id=?', (value, instance_id))

    def progression_message(self, *, instance_id, session_key, name, text, intake):
        """Reader-authorized original user context, applied at the next safe turn."""
        if not isinstance(text, str) or not 1 <= len(text) <= 16384:
            raise ValueError('message must contain 1..16384 characters')
        self._validate_name(name, label='user message name')
        raw = text.encode('utf-8')
        fingerprint = hashlib.sha256(raw).hexdigest()
        with self.control_maintenance.guard(instance_id), self.scheduling_lock():
            self._selected(instance_id, session_key)
            row = self.progression_status(instance_id=instance_id, internal=True)
            if row['state'] == 'idle':
                conflict('Start a frozen goal before sending progression context.')
            checkpoint = json.loads(row['checkpoint_json'])
            messages = checkpoint.get('messages', [])
            old = next((v for v in messages if v['name'] == name), None)
            if old is not None:
                if old['fingerprint'] != fingerprint:
                    conflict('Message name is already frozen; use a new semantic name.')
                return dict(name=name, state='saved', application='next_safe_turn')
            if len(messages) >= 16:
                conflict('Message capacity reached; freeze an explicit goal revision.')
            # Binding is immutable; intake preserves source_origin=user_text.
            if any(v.name == name for v in self.list(instance=instance_id, namespace='artifact')):
                conflict('Message name already exists; choose an unused semantic name.')
            ref = intake.ingest_text(content=raw)
            self.bind(instance=instance_id, namespace='artifact', name=name, object_id=ref.artifact_id,
                request_fingerprint=fingerprint)
            messages.append(dict(name=name, fingerprint=fingerprint, artifact_ref=ref.model_dump(mode='json')))
            checkpoint['messages'] = messages
            value = json.dumps(checkpoint)
            if len(value.encode()) > 65536:
                conflict('Control checkpoint capacity reached.')
            with self._connect() as db:
                db.execute('UPDATE scheduler_progression SET checkpoint_json=? WHERE instance_id=?', (value, instance_id))
            return dict(name=name, state='saved', application='next_safe_turn',
                limitation='User text grants no execution or approval authorization; paused goals remain paused.')

    def progress_assessments(self, *, instance_id, objective_ref, after=0, limit=5):
        from ..schema.common import canonical_sha256
        with self._connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM scheduler_progress_assessments WHERE instance_id=? AND goal_key=? "
                "AND (?=0 OR sequence<?) ORDER BY sequence DESC LIMIT ?",
                (instance_id, canonical_sha256(objective_ref), after, after, limit))]

    def terminal_deliveries(self, *, instance_id, objective_ref, after=0, limit=9):
        """Bounded exact-goal control facts, independent of Root assessments."""
        from ..schema.common import canonical_sha256
        if type(after) is not int or after < 0 or not 1 <= limit <= 101:
            raise ValueError('invalid delivery limit')
        with self._connect() as db:
            return [dict(item) for item in db.execute(
                'SELECT * FROM scheduler_terminal_deliveries WHERE instance_id=? AND goal_key=? '
                'AND sequence>? ORDER BY sequence LIMIT ?',
                (instance_id, canonical_sha256(objective_ref), after, limit))]

    def progress_shadow(self, *, instance_id, objective_ref):
        from ..schema.common import canonical_sha256
        with self._connect() as db:
            record = db.execute('SELECT state_json FROM scheduler_progress_shadow '
                'WHERE instance_id=? AND goal_key=?', (instance_id, canonical_sha256(objective_ref))).fetchone()
            return json.loads(record['state_json']) if record else None

    def progression_report(self, *, instance_id, session_key, summary, completed=False, question=None,
                           assessments=(), artifacts=None, runs=None):
        """Optional Root disposition; a Run completion is never a goal verdict."""
        if not isinstance(summary, str) or not 1 <= len(summary) <= 4096:
            raise ValueError('summary must contain 1..4096 characters')
        if type(completed) is not bool or (question is not None and
                (not isinstance(question, str) or not 1 <= len(question) <= 2048)):
            raise ValueError('invalid disposition')
        if completed and question:
            raise ValueError('a completed goal cannot await a question')
        with self.scheduling_guard(instance_id=instance_id, session_key=session_key), self._connect() as db:
            row = db.execute('SELECT * FROM scheduler_progression WHERE instance_id=?', (instance_id,)).fetchone()
            checkpoint = json.loads(row['checkpoint_json'])
            from .scientific_progress import record_assessments
            receipts = record_assessments(db=db, row=row, assessments=assessments, bindings=self, artifacts=artifacts, runs=runs)
            checkpoint['report'] = dict(summary=summary, completed=completed, question=question)
            reason = 'goal_completed' if completed else 'user_question' if question else 'waiting'
            record_progression_notice(checkpoint, objective=row['objective_ref_json'], state=row['state'], reason=reason)
            value = json.dumps(checkpoint)
            if len(value.encode()) > 65536:
                raise ValueError('control checkpoint capacity reached')
            db.execute('UPDATE scheduler_progression SET checkpoint_json=?, reason=? WHERE instance_id=?',
                (value, reason, instance_id))
        status = self.progression_status(instance_id=instance_id, session_key=session_key)
        if receipts:
            status.update(assessment_receipts=receipts, assessment_read=dict(tool='progression_status'))
        return status

    def observe_progression(self, *, instance_id, expected_host, changes, reason=None, stop=False, completed_turn=None):
        """Trusted runtime observations survive pause; they grant no dispatch authority.

        Serialize merges with the public report, and keep the native writer marker
        until the adapter has confirmed its terminal turn.
        """
        with self.control_maintenance.guard(instance_id), self.scheduling_lock(), self._connect() as db:
            row = db.execute('SELECT * FROM scheduler_progression WHERE instance_id=?', (instance_id,)).fetchone()
            if row is None or json.loads(row['host_json'] or 'null') != expected_host:
                conflict('Native host binding changed during observation.')
            checkpoint = json.loads(row['checkpoint_json'])
            prior_checkpoint = json.loads(row['checkpoint_json'])
            from .scientific_progress import observe_deliveries, assist_transition
            if completed_turn is not None and checkpoint.get('turn_id') == completed_turn:
                observe_deliveries(db, row, checkpoint, boundary='turn_completed')
                assist_transition(db, row, checkpoint, event='turn_completed')
            checkpoint.update(changes)
            if changes.get('phase') == 'prepared' and changes.get('progress_notice'):
                if assist_transition(db, row, checkpoint, event='submit') == 'scientific_progress_candidate_changed':
                    # The built brief became stale before native submission. Keep
                    # its withdrawal, but charge no round and send no old version.
                    return dict(prior_checkpoint, progress_notice_invalidated=True)
            if changes.get('phase') == 'running':
                assist_transition(db, row, checkpoint, event='confirm')
            if changes.get('phase') == 'running' or changes.get('native_completion') == 'completed':
                observe_deliveries(db, row, checkpoint,
                    boundary='turn_completed' if changes.get('native_completion') == 'completed' else None)
            if changes.get('native_completion') == 'completed':
                assist_transition(db, row, checkpoint, event='turn_completed')
            if stop and 'stop_snapshot_tokens' not in checkpoint:
                records = list(checkpoint.get('usage_records', {}).values())
                checkpoint['stop_snapshot_tokens'] = sum(sum(record['counted_tokens'][key]
                    for key in ('input_tokens', 'output_tokens')) for record in records) if records else None
            record_progression_notice(checkpoint, objective=row['objective_ref_json'],
                state='paused' if stop and row['mode'] == 'background' else row['state'],
                reason=reason if reason is not None else row['reason'])
            if (checkpoint == prior_checkpoint and (reason is None or reason == row['reason'])
                    and (not stop or row['mode'] != 'background' or row['state'] == 'paused')):
                return checkpoint
            value = json.dumps(checkpoint, sort_keys=True, allow_nan=False)
            if len(value.encode()) > 65536:
                conflict('Control checkpoint capacity reached; stop and retain original records.')
            values = dict(checkpoint_json=value)
            if reason is not None:
                values['reason'] = reason
            if stop and row['mode'] == 'background':
                values.update(state='paused', owner_session=None, generation=row['generation']+1)
            from .scheduler_bindings import _timestamp
            values['updated_at'] = _timestamp()
            db.execute('UPDATE scheduler_progression SET ' + ','.join(key+'=?' for key in values) +
                ' WHERE instance_id=?', (*values.values(), instance_id))
            return checkpoint



def owned_mutation(method):
    """Protect direct trusted facade consumers as well as MCP routing."""
    @wraps(method)
    def guarded(self, *args, **kwargs):
        with self.scheduling_guard():
            return method(self, *args, **kwargs)
    return guarded
