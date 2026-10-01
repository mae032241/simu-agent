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
from time import time
from functools import wraps

from ..schema.refs import ArtifactRef
from .scientific_progress import PROGRESS_SCHEMA
from .progression_records import DETAIL_SCHEMA, hydrate_control_row, store_checkpoint
from .maintenance import MaintenanceBusy
from ..storage.control_io import control_io_nonblocking

CONTROL_VERSION = 3
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
CONTROL_SCHEMA += PROGRESS_SCHEMA + DETAIL_SCHEMA
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
        'interactive', 'host_active', 'user_paused', 'user_stopped', 'goal_completed', 'human_continuation'
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
    if limits and (value['mode'] == 'background' or checkpoint.get('human_continuations')):
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
        'human_continuation': human_continuation_view(value, checkpoint),
        'interactive_session': interactive_session_view(value, checkpoint),
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


def human_continuation_binding(row, session_key):
    """UI form freshness binding; authorization remains capability plus CSRF."""
    return hashlib.sha256(json.dumps([row.get(key) for key in
        ('instance_id', 'generation', 'objective_ref_json', 'owner_session', 'checkpoint_json')] + [session_key]).encode()).hexdigest()


def human_continuation_view(row, checkpoint):
    from .scientific_progress import human_continuation_active
    records = checkpoint.get('human_continuations', [])
    return dict(active=human_continuation_active(row, checkpoint),
        authority='human_control_decision_not_scientific_evidence',
        history=[{key: record[key] for key in ('recorded_at', 'objective_name', 'prior_reason', 'causes', 'through_sequence', 'budget_snapshot')} for record in records[-8:]],
        history_omitted=checkpoint.get('human_continuations_omitted', 0) + max(0, len(records)-8))


def interactive_session_view(row, checkpoint):
    from .scientific_progress import independent_interactive_active
    from ...platforms.codex_usage import usage_summary
    records = checkpoint.get('interactive_sessions', [])
    return dict(active=independent_interactive_active(row, checkpoint),
        authority='explicit_human_interactive_scope',
        budget_scope='Independent interactive work does not spend or replenish the frozen background session. '
            'Instance execution budgets still apply. Interactive native token usage is not fully observed.',
        history=[{key: item[key] for key in ('id', 'recorded_at', 'objective_name',
            'prior_objective_name', 'background_budget_snapshot')} for item in records[-8:]],
        history_omitted=max(0, len(records)-8),
        observed_usage=usage_summary(list(checkpoint.get('interactive_usage_records', {}).values())),
        tasks=sum(bool(item.get('interactive_session_id')) for item in checkpoint.get('admissions', {}).values()))


def background_task_count(checkpoint):
    return sum(not item.get('interactive_session_id') for item in checkpoint.get('admissions', {}).values())


def require_resolved_control(row, checkpoint):
    if (row['host_json'] is not None or checkpoint.get('fault_class') == 'outcome_unknown'
            or (checkpoint.get('phase') == 'prepared' and not checkpoint.get('turn_id'))
            or checkpoint.get('phase') == 'running'
            or any(item['state'] == 'prepared' for item in checkpoint.get('admissions', {}).values())):
        conflict('Unresolved native host or task submission; reconcile before human continuation.')


def require_human_continuation_budget(row, checkpoint):
    """Same-session continuation retains the original wall clock and all limits."""
    require_resolved_control(row, checkpoint)
    limits = json.loads(row['config_json'])['effective']['progression']
    budget = checkpoint.get('budget', {})
    resources = checkpoint.get('resources') or {}
    exhausted = any(checkpoint.get(key, 0) >= limits['max_' + key]
        for key in ('rounds', 'attempts', 'probes'))
    exhausted |= background_task_count(checkpoint) >= limits['max_tasks']
    exhausted |= max(budget.get('elapsed_seconds', 0),
        time() - checkpoint.get('started_at', time())) >= limits['max_elapsed_seconds']
    exhausted |= (resources.get('owned_tree_rss_bytes', 0) +
        (resources.get('control_daemon_rss_bytes') or 0)) >= limits['max_rss_bytes']
    exhausted |= limits['token_policy'] == 'strict' and budget.get('token_coverage') != 'observed'
    exhausted |= row['reason'] in {'budget_exhausted', 'attempt_budget_exhausted', 'resource_limit'}
    if exhausted:
        conflict('Frozen progression budget exhausted; same-goal continuation retains all limits including elapsed time. '
            'Explicitly confirm an independent interactive work scope in the management UI if intended.')
    from .progression_budget import require_task_budget
    from ...operations.invoke import OperationInvocationError
    try:
        require_task_budget(checkpoint, limits)
    except OperationInvocationError as error:
        conflict(str(error))


class SchedulingControl:
    # Runtime supplies the public, bounded exact-goal reader after RunService opens.
    progress_run_reader = None
    progress_active_work_reader = None

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
            connection.execute('BEGIN')
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
                    return hydrate_control_row(connection, row)
        return None

    def progression_status(self, *, instance_id, session_key=None, internal=False):
        self.get_instance(instance_id=instance_id)
        with self._connect() as connection:
            connection.execute('BEGIN')
            row = connection.execute('SELECT * FROM scheduler_progression WHERE instance_id=?', (instance_id,)).fetchone()
            row = hydrate_control_row(connection, row)
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
        if 'checkpoint_json' in values:
            values['checkpoint_json'] = store_checkpoint(connection, instance_id, json.loads(values['checkpoint_json']))
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
            # Switching to interactive cannot erase an already frozen policy or
            # budget. Ordinary Root commands do not authorize human continuation.
            settings = (self.control_settings(instance_id) if mode == 'background'
                else json.loads(old.get('config_json') or '{}'))
            config = json.dumps(settings, sort_keys=True, separators=(',', ':'))
            fingerprint = hashlib.sha256(json.dumps([mode, objective_name, ref_json, config]).encode()).hexdigest()
            if (command == 'start' and exists and old['mode'] == mode and old['request_fingerprint'] == fingerprint
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
            if command in {'start', 'resume', 'takeover'} and exists:
                from .scientific_progress import scientific_pause
                with self._connect() as db:
                    current_pause = scientific_pause(db, old, checkpoint)
                    checkpoint.pop('observation_scope_id', None)
                    if current_pause or scientific_pause(db, old, checkpoint):
                        conflict('scientific_progress_persistent_gap: confirm a new observation window in the management UI.')
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
                if mode == 'background' and ref_json and self.progress_run_reader:
                    from .scientific_progress import freeze_observation_scope
                    freeze_observation_scope(connection, dict(instance_id=instance_id, **values),
                        self.progress_run_reader, self)
                if ref_json:
                    from .scientific_progress import refresh_shadow
                    from ..schema.common import canonical_sha256
                    refresh_shadow(connection, dict(instance_id=instance_id, **values),
                        canonical_sha256(json.loads(ref_json)))
                self._write_progression(connection, instance_id, values)
            if state == 'active' and self.client_database_path.exists():
                with self._client_connect() as connection:
                    connection.execute('UPDATE scheduler_clients SET enabled=1 WHERE session_key=?', (session_key,))
            return self.progression_status(instance_id=instance_id, session_key=session_key)

    def background_continuations(self, *, instance_id, session_key):
        """UI candidates come from immutable paused-goal deliveries, never recency."""
        from .scientific_progress import scientific_pause, observation_facts, shadow_policy
        from ..schema.common import canonical_sha256
        from .progression_budget import token_budget
        self._selected(instance_id, session_key)
        row = self.progression_status(instance_id=instance_id, internal=True)
        checkpoint = json.loads(row.get('checkpoint_json', '{}'))
        if row['state'] not in {'paused', 'stopped'} or not checkpoint.get('observation_scope_id'):
            return []
        checkpoint.pop('observation_scope_id')
        limits = json.loads(row['config_json'])['effective']['progression']
        remaining = dict(tasks=max(0, limits['max_tasks'] - background_task_count(checkpoint)),
            rounds=max(0, limits['max_rounds'] - checkpoint.get('rounds', 0)),
            seconds=max(0, limits['max_elapsed_seconds'] - max(
                checkpoint.get('budget', {}).get('elapsed_seconds', 0),
                time() - checkpoint.get('started_at', time()))),
            tokens=token_budget(checkpoint, limits)['remaining_tokens'])
        options = []
        with self._connect() as db:
            db.execute('BEGIN')
            pause = scientific_pause(db, row, checkpoint) or dict(causes=[])
            for goal_key in sorted({item['goal_key'] for item in pause['causes']}):
                causes = [item for item in pause['causes'] if item['goal_key'] == goal_key]
                references = db.execute('SELECT DISTINCT objective_ref_json FROM scheduler_terminal_deliveries '
                    'WHERE instance_id=? AND goal_key=?', (instance_id, goal_key)).fetchall()
                if len(references) != 1:
                    options.append(dict(error='后台目标原件引用缺失或不一致；请核对原目标与交付记录后重新确认。', causes=causes))
                    continue
                ref = ArtifactRef.model_validate_json(references[0]['objective_ref_json'])
                if canonical_sha256(ref) != goal_key:
                    options.append(dict(error='后台目标与交付引用不一致；请核对原件绑定后重新确认。', causes=causes))
                    continue
                ref_json = ref.canonical_json().decode()
                names = {item.name for item in self.list(instance=instance_id, namespace='artifact')
                    if item.object_id == ref.artifact_id}
                recorded = {item['objective_name'] for item in checkpoint.get('human_continuations', [])
                    if item.get('scope_id') == 'background' and item['objective_ref_json'] == ref_json}
                recorded.update(item['prior_objective_name'] for item in checkpoint.get('interactive_sessions', []))
                names = names & recorded or names
                if not names:
                    options.append(dict(error='原后台目标绑定缺失或已改变；请在实例工作台核对原件和绑定，修复后重新确认。', causes=causes))
                    continue
                state = json.loads(db.execute('SELECT state_json FROM scheduler_progress_shadow '
                    'WHERE instance_id=? AND goal_key=?', (instance_id, goal_key)).fetchone()['state_json'])
                target_row = dict(row, objective_ref_json=ref_json, checkpoint_json=json.dumps(checkpoint))
                facts, _ = observation_facts(db, target_row, goal_key, shadow_policy(row), state)
                through = max([0, *(fact['sequence'] for fact in facts)])
                window = state.get('window_starts', {}).get('background', 0)
                for name in sorted(names):
                    binding = hashlib.sha256(json.dumps(['background', human_continuation_binding(row, session_key),
                        name, ref_json, causes, through, window]).encode()).hexdigest()
                    options.append(dict(objective_name=name, objective_ref_json=ref_json, causes=causes,
                        through_sequence=through, confirmation_binding=binding, remaining=remaining))
        return options

    def human_continue_from_ui(self, *, instance_id, session_key, confirmation_binding, objective_name=None):
        """Trusted management UI only; deliberately absent from Root/CLI contracts.

        The UI validates capability, origin and CSRF before calling this entry.
        This is the existing local UI trust boundary, not same-UID isolation.
        """
        from .scientific_progress import shadow_policy, open_observation_window
        from .scheduler_bindings import _timestamp
        with self.control_maintenance.guard(instance_id), self.scheduling_lock():
            self._selected(instance_id, session_key)
            row = self.progression_status(instance_id=instance_id, internal=True)
            restore = None
            if objective_name is not None:
                restore = next((item for item in self.background_continuations(instance_id=instance_id,
                    session_key=session_key) if item.get('objective_name') == objective_name
                    and item.get('confirmation_binding') == confirmation_binding), None)
            if (not row.get('objective_ref_json') or (objective_name is not None and restore is None)
                    or (objective_name is None and (row['state'] != 'paused'
                        or confirmation_binding != human_continuation_binding(row, session_key)))):
                conflict('Human continuation target changed; reread and confirm this goal in the management UI.')
            checkpoint = json.loads(row['checkpoint_json'])
            if restore:
                require_human_continuation_budget(row, checkpoint)
                if self.progress_active_work_reader is None or self.progress_active_work_reader(instance_id=instance_id):
                    conflict('Existing work is running, uncollected or unconfirmed; reconcile it before returning to background.')
                checkpoint.pop('observation_scope_id')
                if row['objective_ref_json'] != restore['objective_ref_json']:
                    checkpoint['last_report'] = checkpoint.get('report') or checkpoint.get('last_report')
                    checkpoint['report'] = None
                    checkpoint['relevant_runs'] = {}
                    checkpoint.pop('relevant_runs_objective_ref', None)
                row = dict(row, objective_name=restore['objective_name'], objective_ref_json=restore['objective_ref_json'])
            progress = self.progress_shadow(instance_id=instance_id,
                objective_ref=ArtifactRef.model_validate_json(row['objective_ref_json'])) or {}
            if shadow_policy(row)['progress_mode'] != 'assist':
                conflict('Human continuation requires assist mode and a resolved native submission.')
            if checkpoint.get('observation_scope_id'):
                require_resolved_control(row, checkpoint)
            else:
                require_human_continuation_budget(row, checkpoint)
            generation = row['generation'] + 1
            records = checkpoint.setdefault('human_continuations', [])
            records.append(dict(recorded_at=_timestamp(), objective_name=row['objective_name'],
                objective_ref_json=row['objective_ref_json'], session_key=session_key, generation=generation,
                scope_id=checkpoint.get('observation_scope_id', 'background'),
                prior_reason=row['reason'], causes=restore['causes'] if restore else (checkpoint.get('scientific_pause') or {}).get('causes', []),
                through_sequence=progress.get('through_sequence', 0), budget_snapshot=dict(
                    rounds=checkpoint.get('rounds', 0), attempts=checkpoint.get('attempts', 0),
                    probes=checkpoint.get('probes', 0), tasks=background_task_count(checkpoint),
                    started_at=checkpoint.get('started_at'), budget=checkpoint.get('budget'))))
            state, mode = ('pending', 'background') if restore else ('active', 'interactive')
            checkpoint['last_command'] = dict(command='human_continue', state=state,
                reason='human_continuation', mode=mode, generation=generation)
            record_progression_notice(checkpoint, objective=row['objective_ref_json'],
                state=state, reason='human_continuation')
            values = {key: value for key, value in row.items() if key not in {'instance_id', 'updated_at'}}
            values.update(generation=generation, owner_session=None if restore else session_key, requested_by=session_key,
                state=state, mode=mode, reason='human_continuation', checkpoint_json=json.dumps(checkpoint))
            with self._connect() as db:
                db.execute('BEGIN IMMEDIATE')
                records[-1]['through_sequence'] = open_observation_window(db, dict(row, checkpoint_json=json.dumps(checkpoint)), checkpoint)
                checkpoint.pop('scientific_pause', None)
                values['checkpoint_json'] = json.dumps(checkpoint)
                self._write_progression(db, instance_id, values)
            if self.client_database_path.exists():
                with self._client_connect() as db:
                    db.execute('UPDATE scheduler_clients SET enabled=1 WHERE session_key=?', (session_key,))
            return self.progression_status(instance_id=instance_id, session_key=session_key)

    def independent_interactive_from_ui(self, *, instance_id, session_key, confirmation_binding,
                                        objective_name, objective_ref):
        """One explicit human work scope; ordinary Root commands cannot create it."""
        from .scheduler_bindings import _timestamp
        with self.control_maintenance.guard(instance_id), self.scheduling_lock():
            self._selected(instance_id, session_key)
            row = self.progression_status(instance_id=instance_id, internal=True)
            if (row['state'] not in {'paused', 'stopped'}
                    or confirmation_binding != human_continuation_binding(row, session_key)):
                conflict('Independent interactive target changed; pause and confirm in the management UI.')
            checkpoint = json.loads(row['checkpoint_json'])
            require_resolved_control(row, checkpoint)
            if not objective_name or objective_ref is None:
                raise ValueError('Independent interactive work requires its exact frozen objective.')
            ref = ArtifactRef.model_validate(objective_ref)
            if self.resolve(instance=instance_id, namespace='artifact', name=objective_name) != ref.artifact_id:
                conflict('Objective must match its exact instance binding.')
            records = checkpoint.setdefault('interactive_sessions', [])
            generation = row['generation'] + 1
            ref_json = ref.canonical_json().decode()
            records.append(dict(id=hashlib.sha256(f'{instance_id}:{generation}'.encode()).hexdigest(),
                recorded_at=_timestamp(), session_key=session_key, generation=generation,
                objective_name=objective_name, objective_ref_json=ref_json,
                prior_objective_name=row['objective_name'], background_budget_snapshot=dict(
                    rounds=checkpoint.get('rounds', 0), attempts=checkpoint.get('attempts', 0),
                    probes=checkpoint.get('probes', 0), tasks=background_task_count(checkpoint),
                    started_at=checkpoint.get('started_at'), budget=checkpoint.get('budget'))))
            checkpoint['observation_scope_id'] = records[-1]['id']
            if row['objective_ref_json'] != ref_json:
                checkpoint['last_report'] = checkpoint.get('report') or checkpoint.get('last_report')
                checkpoint['report'] = None
                checkpoint['relevant_runs'] = {}
                checkpoint.pop('relevant_runs_objective_ref', None)
            checkpoint['last_command'] = dict(command='independent_interactive', state='active',
                reason='independent_interactive', mode='interactive', generation=generation)
            record_progression_notice(checkpoint, objective=ref_json, state='active', reason='independent_interactive')
            values = {key: value for key, value in row.items() if key not in {'instance_id', 'updated_at'}}
            values.update(generation=generation, owner_session=session_key, requested_by=session_key,
                state='active', mode='interactive', reason='independent_interactive', objective_name=objective_name,
                objective_ref_json=ref_json, checkpoint_json=json.dumps(checkpoint), request_fingerprint=None)
            if not json.loads(row['config_json']).get('effective', {}).get('progression'):
                values['config_json'] = json.dumps(self.control_settings(instance_id))
            with self._connect() as db:
                from .scientific_progress import open_observation_window
                db.execute('BEGIN IMMEDIATE')
                open_observation_window(db, dict(values, instance_id=instance_id), checkpoint)
                self._write_progression(db, instance_id, values)
            if self.client_database_path.exists():
                with self._client_connect() as db:
                    db.execute('UPDATE scheduler_clients SET enabled=1 WHERE session_key=?', (session_key,))
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
            from .scientific_progress import scientific_pause
            with self._connect() as db:
                checkpoint = json.loads(row['checkpoint_json'])
                pause = scientific_pause(db, row, checkpoint)
                if pause:
                    if row['state'] == 'active':
                        self._pause_progress(db, row, checkpoint, pause)
                        db.commit()
                    conflict('scientific_progress_persistent_gap: confirm a new observation window in the management UI.')
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
            row = hydrate_control_row(db, row)
            checkpoint = json.loads(row['checkpoint_json'])
            from .scientific_progress import shadow_policy, human_continuation_active, independent_interactive_active
            independent = independent_interactive_active(row, checkpoint)
            if row['mode'] != 'background' and shadow_policy(row)['progress_mode'] != 'assist' and not independent:
                return
            if independent:
                require_resolved_control(row, checkpoint)
            elif human_continuation_active(row, checkpoint):
                require_human_continuation_budget(row, checkpoint)
            admissions = checkpoint.setdefault('admissions', {})
            if any(v['state'] == 'prepared' for v in admissions.values()):
                conflict('A prior task admission is unresolved; reconcile it before creating more work.')
            if name in admissions:
                conflict('Prior task admission must be reconciled by exact identity; do not replay creation.')
            limits = json.loads(row['config_json'])['effective']['progression']
            if not independent and background_task_count(checkpoint) >= limits['max_tasks']:
                conflict('Frozen task admission budget exhausted.')
            from .progression_budget import require_task_budget
            if not independent:
                require_task_budget(checkpoint, limits)
            from .scientific_progress import observe_deliveries, scientific_pause
            observe_deliveries(db, row, checkpoint, boundary='next_task_admission')
            progress_stop = scientific_pause(db, row, checkpoint)
            if progress_stop:
                self._pause_progress(db, row, checkpoint, progress_stop)
                # Keep consumption and cause state even though admission fails.
                db.commit()
                conflict('scientific_progress_persistent_gap')
            if row['mode'] == 'interactive' and not independent and not human_continuation_active(row, checkpoint):
                require_human_continuation_budget(row, checkpoint)
            admissions[name] = dict(logical_name=logical_name, revision=revision,
                fingerprint=fingerprint, output_fingerprint=output_fingerprint, scientific_signature=scientific_signature,
                objective_ref=json.loads(row['objective_ref_json']) if row['objective_ref_json'] else None, state='prepared')
            if independent:
                admissions[name]['interactive_session_id'] = checkpoint['interactive_sessions'][-1]['id']
            value = store_checkpoint(db, instance_id, checkpoint)
            db.execute('UPDATE scheduler_progression SET checkpoint_json=? WHERE instance_id=?', (value, instance_id))

    def _pause_progress(self, db, row, checkpoint, pause):
        checkpoint['scientific_pause'] = dict(pause, source_session=row['owner_session'])
        reason = 'scientific_progress_persistent_gap'
        record_progression_notice(checkpoint, objective=row['objective_ref_json'], state='paused', reason=reason)
        db.execute("UPDATE scheduler_progression SET state='paused',owner_session=NULL,reason=?,"
            "generation=generation+1,checkpoint_json=? WHERE instance_id=?",
            (reason, store_checkpoint(db, row['instance_id'], checkpoint), row['instance_id']))

    def progress_boundary(self, *, instance_id):
        with self.control_maintenance.guard(instance_id), self.scheduling_lock(), self._connect() as db:
            row = hydrate_control_row(db, db.execute('SELECT * FROM scheduler_progression WHERE instance_id=?',
                (instance_id,)).fetchone())
            if row is None or row['state'] != 'active':
                return None
            from .scientific_progress import scientific_pause
            checkpoint = json.loads(row['checkpoint_json'])
            pause = scientific_pause(db, row, checkpoint)
            if pause:
                self._pause_progress(db, row, checkpoint, pause)
                return 'scientific_progress_persistent_gap'
            return None

    def record_goal_binding(self, *, instance_id, session_key, namespace, name, object_id):
        with self.scheduling_guard(instance_id=instance_id, session_key=session_key), self._connect() as db:
            row = db.execute('SELECT * FROM scheduler_progression WHERE instance_id=?', (instance_id,)).fetchone()
            row = hydrate_control_row(db, row)
            checkpoint = json.loads(row['checkpoint_json'])
            from .scientific_progress import shadow_policy, independent_interactive_active
            if (row['mode'] != 'background' and shadow_policy(row)['progress_mode'] != 'assist'
                    and not independent_interactive_active(row, checkpoint)):
                return
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
            value = store_checkpoint(db, instance_id, checkpoint)
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
        if not isinstance(checkpoint, dict):
            raise ValueError('checkpoint must be a control record')
        with self.scheduling_guard(instance_id=instance_id, session_key=session_key, expected_generation=expected_generation), self._connect() as connection:
            value = store_checkpoint(connection, instance_id, checkpoint)
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
            with self._connect() as db:
                value = store_checkpoint(db, instance_id, checkpoint)
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
        with self.control_maintenance.guard(instance_id), self.scheduling_lock(), self._connect() as db:
            self._selected(instance_id, session_key)
            current = self.progression_status(instance_id=instance_id, internal=True)
            cp = json.loads(current.get('checkpoint_json', '{}'))
            if (current['state'] != 'paused' or session_key not in
                    {current.get('requested_by'), (cp.get('scientific_pause') or {}).get('source_session')}):
                with self.scheduling_guard(instance_id=instance_id, session_key=session_key):
                    pass
            row = db.execute('SELECT * FROM scheduler_progression WHERE instance_id=?', (instance_id,)).fetchone()
            row = hydrate_control_row(db, row)
            checkpoint = json.loads(row['checkpoint_json'])
            from .scientific_progress import record_assessments
            receipts = record_assessments(db=db, row=row, assessments=assessments, bindings=self, artifacts=artifacts, runs=runs)
            if row['state'] == 'paused':
                from .scientific_progress import scientific_pause
                pause = scientific_pause(db, row, checkpoint)
                if pause:
                    checkpoint['scientific_pause'] = dict(pause, source_session=
                        (checkpoint.get('scientific_pause') or {}).get('source_session'))
            checkpoint['report'] = dict(summary=summary, completed=completed, question=question)
            reason = row['reason'] if row['state'] == 'paused' else (
                'goal_completed' if completed else 'user_question' if question else 'waiting')
            record_progression_notice(checkpoint, objective=row['objective_ref_json'], state=row['state'], reason=reason)
            value = store_checkpoint(db, instance_id, checkpoint)
            db.execute('UPDATE scheduler_progression SET checkpoint_json=?, reason=? WHERE instance_id=?',
                (value, reason, instance_id))
        status = self.progression_status(instance_id=instance_id, session_key=session_key)
        if receipts:
            status.update(assessment_receipts=receipts, assessment_read=dict(tool='progression_status'))
        return status

    def observe_progression(self, *, instance_id, expected_host, changes, reason=None, stop=False, completed_turn=None, terminal_turn=None):
        """Trusted runtime observations survive pause; they grant no dispatch authority.

        Serialize merges with the public report, and keep the native writer marker
        until the adapter has confirmed its terminal turn.
        """
        with self.control_maintenance.guard(instance_id), self.scheduling_lock(), self._connect() as db:
            row = db.execute('SELECT * FROM scheduler_progression WHERE instance_id=?', (instance_id,)).fetchone()
            row = hydrate_control_row(db, row)
            if row is None or json.loads(row['host_json'] or 'null') != expected_host:
                conflict('Native host binding changed during observation.')
            checkpoint = json.loads(row['checkpoint_json'])
            prior_checkpoint = json.loads(row['checkpoint_json'])
            from .scientific_progress import observe_deliveries, scientific_pause
            if terminal_turn is not None and checkpoint.get('turn_id'):
                if terminal_turn.get('id') != checkpoint['turn_id']:
                    conflict('Native terminal turn identity mismatch; retain the unresolved writer.')
                if terminal_turn.get('status') == 'completed':
                    completed_turn = terminal_turn['id']
            if completed_turn is not None and checkpoint.get('turn_id') == completed_turn:
                observe_deliveries(db, row, checkpoint, boundary='turn_completed')
            checkpoint.update(changes)
            if changes.get('phase') == 'running' or changes.get('native_completion') == 'completed':
                observe_deliveries(db, row, checkpoint,
                    boundary='turn_completed' if changes.get('native_completion') == 'completed' else None)
            pause = scientific_pause(db, row, checkpoint)
            if pause and row['state'] in {'active', 'paused'}:
                checkpoint['scientific_pause'] = dict(pause, source_session=
                    (checkpoint.get('scientific_pause') or {}).get('source_session', row['owner_session']))
                if row['state'] == 'active':
                    reason, stop = 'scientific_progress_persistent_gap', True
            if stop and 'stop_snapshot_tokens' not in checkpoint:
                records = list(checkpoint.get('usage_records', {}).values())
                checkpoint['stop_snapshot_tokens'] = sum(sum(record['counted_tokens'][key]
                    for key in ('input_tokens', 'output_tokens')) for record in records) if records else None
            record_progression_notice(checkpoint, objective=row['objective_ref_json'],
                state='paused' if stop and (row['mode'] == 'background' or reason == 'scientific_progress_persistent_gap') else row['state'],
                reason=reason if reason is not None else row['reason'])
            if (checkpoint == prior_checkpoint and (reason is None or reason == row['reason'])
                    and (not stop or row['state'] == 'paused')):
                return checkpoint
            value = store_checkpoint(db, instance_id, checkpoint)
            values = dict(checkpoint_json=value)
            if reason is not None:
                values['reason'] = reason
            if stop and (row['mode'] == 'background' or reason == 'scientific_progress_persistent_gap'):
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
