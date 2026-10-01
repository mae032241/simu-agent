"""One event-coalescing background scheduler; scientific choices stay with Root.

Injected native host and existing public read projections keep this service free
of interface dependencies. The durable checkpoint is part of instance archives.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sqlite3
import threading
import time

from ..schema.refs import ArtifactRef
from ...platforms.codex_usage import observe_usage, usage_summary
from .progression_budget import token_budget
from .maintenance import MaintenanceBusy
from ..storage.control_io import nonblocking_control_io
from .scientific_progress import goal_bound_runs
from ...agent_execution_settings import ProgressionSettings


INSTRUCTION = """Continue the explicitly started frozen research goal from this bounded brief.
Choose the next complete task using public Operations and sealed evidence, or wait,
ask a specific question, or conclude the whole goal. A completed Run does not mean
the goal is complete. Starting this goal authorizes ordinary task selection within
its scope and budget, including source-based analysis. Do not ask permission to
choose such a task or repair an input selection. Ask only for missing user facts,
an actual scope decision, or an explicitly required authorization; policy gates
still apply. An original text/file is not yet a Worker-authored scientific object.
Use a task accepting that original when no suitable scientific result exists;
do not force an experiment or a preparatory workflow for pure evidence analysis.
Keep limitations and negative results. Read exact materials
and contracts as needed; omitted content is not evidence. Reuse the decision
fields in this brief and contracts already read in this native thread. Request
specific output_fields/output_paths when more evidence is needed; do not default
to full outputs or repeat unchanged contract discovery. Native tool discovery
returns matching names first, never arrays of full descriptions. Dispatch native Workers
with the returned agent_type and frozen model/reasoning profile, fresh context and
actual platform identities. If spawn omits a thread ID, ask that child for its
platform-provided identity while it waits for attachment; do not search the tool
registry for identity. Ordinary task stages belong to that Worker; do not
turn them into separate Root approvals. At most one complete Agent task may be
queued/running. Helpers belong to its owner and retain native permissions.
At complete-task selection, scientific_intent may state intent, target and expected observation.
Use progression_report when recording a goal conclusion, specific question, waiting
condition or task assessment is useful. Its optional assessments cite exact sealed
output names and distinguish advance, no_progress and unknown; no extra report gate. Consider remaining tokens, the closeout reserve
and observed Worker-thread costs before selecting more work; these are not exact
predictions of a new task. When budget.new_task_allowed is false, consume
accepted results and report the supported conclusion or unfinished work; do not
dispatch another task or repeat admission. The reserve is inside the total budget,
not permission to exceed it, and missing evidence is not a completed goal.
When human_handoff is present and active, consume only its existing sealed results
and record supported assessments. It grants no new scientific task or reassessment.
A review_requests entry is an exact dependency: let its owner wait, dispatch only
that independent review, then read its result and notify the existing owner to
continue. It grants no permission for unrelated concurrent work.
Finish this turn after dispatch or while waiting;
the service wakes you on authoritative changes. Do not poll unchanged status or
invent retries. User text does not authorize an approval or execution exception.
"""


class ProgressionFault(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class ProgressionCoordinator:
    def __init__(self, *, runtime, host_factory, facade_factory, clock=time.time):
        self.runtime, self.bindings = runtime, runtime.scheduler_bindings
        self.host_factory, self.facade_factory, self.clock = host_factory, facade_factory, clock
        self.host = None
        self.instance = None
        self.events = []
        self.closed = threading.Event()
        self.thread = None
        self.lease = None
        self._pending_fault = None
        self._restored_turn_id = None
        self._limits = ProgressionSettings().model_dump()
        self._budget_saved_at = None
        self._sample_host = None
        self._sample_at = 0
        self._resource_sample = None
        self._submitting = False
        self._goal_deadline = None
        self._last_row = None

    def start(self):
        # Exactly one owner per deployed control database, including two daemons.
        path = self.bindings.database_path.with_suffix('.progression.lock')
        self.lease = os.open(path, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(self.lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(self.lease)
            self.lease = None
            return
        self.thread = threading.Thread(target=self._run, name='research-progression', daemon=True)
        self.thread.start()

    def _run(self):
        while not self.closed.is_set():
            try:
                self.tick()
                delay = self._limits['event_wait_seconds']
                if self.host is not None and hasattr(self.host, 'wait_for_event'):
                    self.host.wait_for_event(delay)
                else:
                    self.closed.wait(delay)
            except Exception:
                # Durable fault handling in tick is the recovery authority. A
                # maintenance gate may deny even fault writes; retry observation
                # after the gate, never retry an unrecorded model submission.
                self.closed.wait(self._limits['event_wait_seconds'])

    def _observation(self, operation, *, terminal=False):
        """Retry local reads/atomic observations, never native submission calls.

        SQLITE_BUSY/LOCKED and a maintenance gate mean this local transaction
        did not complete. Retrying an absolute observation retains the same
        expected host and values; no new model attempt is granted.
        """
        started = time.monotonic()
        for attempt in range(self._limits['observation_retries'] + 1):
            try:
                with nonblocking_control_io():
                    return operation()
            except (sqlite3.OperationalError, MaintenanceBusy) as error:
                code = getattr(error, 'sqlite_errorcode', 0) & 255
                if not isinstance(error, MaintenanceBusy) and code not in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
                    raise
                if self._goal_deadline is not None and self.clock() >= self._goal_deadline:
                    raise ProgressionFault('observation_budget_expired') from error
                remaining = self._limits['observation_retry_seconds'] - (time.monotonic() - started)
                if attempt >= self._limits['observation_retries'] or remaining <= 0:
                    raise ProgressionFault('observation_retry_exhausted') from error
                # This also guards resources during RPC callbacks waiting on DB.
                if not terminal and self.host is not None and hasattr(self.host, 'guard_resources'):
                    self.host.guard_resources()
                delay = min(self._limits['observation_backoff_seconds'] * 2**attempt, remaining,
                    self._limits['event_wait_seconds'])
                if self._goal_deadline is not None:
                    delay = min(delay, max(0, self._goal_deadline-self.clock()))
                if self.closed.wait(delay):
                    raise ProgressionFault('coordinator_closed') from error

    def _row(self):
        value = self._observation(lambda: self.bindings.progression_status(instance_id=self.instance, internal=True))
        self._last_row = value
        return value

    def _host_binding(self):
        identity = self.host.identity
        return dict(platform_session=identity.session_id, thread_id=identity.thread_id)

    def _save(self, changes, **kwargs):
        expected_host = self._host_binding()
        if (changes.get('phase') == 'idle' and self.host.completion
                and self.host.completion['status'] == 'completed'):
            kwargs['completed_turn'] = self.host.completion['id']
        return self._observation(lambda: self.bindings.observe_progression(instance_id=self.instance,
            expected_host=expected_host, changes=changes, **kwargs))

    def _event(self, event):
        # No transcripts in control memory/storage. Only native identity, turn
        # terminal state and cumulative accounting are retained.
        if event.get('method') not in {'thread/tokenUsage/updated', 'turn/started', 'turn/completed', 'scid/serverRequest', 'item/completed'}:
            return
        if self.host is None:
            if len(self.events) >= 128:
                raise ProgressionFault('native_initialization_event_limit')
            self.events.append(event)
            return
        params = event.get('params', {})
        row = self._row()
        checkpoint = json.loads(row['checkpoint_json'])
        thread = params.get('threadId')
        if event['method'] == 'item/completed':
            self._terminal_tool_delivery(row, checkpoint, params)
        elif event['method'] == 'scid/serverRequest':
            requests = checkpoint.get('platform_requests', [])
            key = (params.get('threadId'), params.get('turnId'), params['request_id'])
            requests = [value for value in requests if
                (value.get('threadId'), value.get('turnId'), value['request_id']) != key]
            if len(requests) >= 8:
                raise ProgressionFault('platform_request_capacity')
            requests.append(params)
            pending = params['state'] == 'pending_user_input'
            self._save(dict(platform_requests=requests), reason='platform_user_input_pending' if pending else None, stop=pending)
        elif event['method'] == 'thread/tokenUsage/updated':
            identities = self._identities()
            role = 'root' if thread == self.host.identity.thread_id else identities.get(thread, {}).get('role', 'unattributed')
            independent = bool(identities.get(thread, {}).get('interactive_session_id'))
            record_key = 'interactive_usage_records' if independent else 'usage_records'
            records = checkpoint.get(record_key, {})
            if thread not in records and len(records) >= 64:
                raise ProgressionFault('usage_identity_capacity')
            previous = records.get(thread)
            # A native Worker thread can be reused across task scopes. Carry its
            # highest observed counter, while each scope retains only its deltas.
            other = checkpoint.get('usage_records' if independent else 'interactive_usage_records', {}).get(thread)
            if other:
                previous = dict(previous or {**other, 'counted_tokens':
                    dict.fromkeys(other['counted_tokens'], 0)})
                previous['high_water'] = {key: max(value for value in
                    (previous['high_water'][key], other['high_water'][key]) if value is not None)
                    if any(value is not None for value in
                        (previous['high_water'][key], other['high_water'][key])) else None
                    for key in previous['high_water']}
                previous['has_gaps'] = True  # Attribution between observations is not measured.
            if previous and previous['role'] == 'unattributed' and role != 'unattributed':
                # Native notifications can precede the exact Worker attach. Only
                # the now-authoritative connection may repair that attribution.
                previous = {**previous, 'role': role, 'owner': self.instance}
            record = observe_usage(params, previous=previous, role=role,
                owner=self.instance if role != 'unattributed' else None,
                outcome='running')
            # Keep reducer state, not repeated diagnostic prose or per-event deltas.
            records[thread] = {key: record[key] for key in ('platform', 'thread_id', 'role', 'owner',
                'outcome', 'high_water', 'counted_tokens', 'has_gaps', 'coverage')}
            self._save({record_key: records, **({} if independent else
                dict(usage_summary=usage_summary(list(records.values()))))})
        elif thread == self.host.identity.thread_id:
            turn = params.get('turn', {})
            if event['method'] == 'turn/started':
                if checkpoint.get('phase') == 'prepared':
                    self._save(dict(turn_id=turn.get('id'), phase='running'))
            elif turn.get('id') == checkpoint.get('turn_id'):
                records = checkpoint.get('usage_records', {})
                if thread in records:
                    records[thread]['outcome'] = 'completed' if turn.get('status') == 'completed' else 'failed'
                self._save(dict(native_completion=turn.get('status'), usage_records=records,
                    usage_summary=usage_summary(list(records.values()))))

    def _terminal_tool_delivery(self, row, checkpoint, params):
        """Native v2 ItemCompletedNotification proves a Root tool result was handed back.

        Only declared structured MCP results are observable. Code-mode/native
        wrappers are outside this receipt and never parsed as scientific text.
        """
        if (params.get('threadId') != self.host.identity.thread_id
                or params.get('turnId') != checkpoint.get('turn_id') or checkpoint.get('phase') != 'running'):
            return
        item = params.get('item', {})
        if (item.get('type'), item.get('server'), item.get('tool'), item.get('status')) != (
                'mcpToolCall', 'scidiscovery', 'scid_call', 'completed'):
            return
        arguments, result = item.get('arguments'), item.get('result')
        if not isinstance(arguments, dict) or arguments.get('name') not in {'run_status', 'run_list', 'progression_status'}:
            return
        body = result.get('structuredContent') if isinstance(result, dict) else None
        if not isinstance(body, dict):
            self._save(dict(terminal_delivery_coverage='structured_tool_result_unavailable'))
            return
        closeout = body.get('closeout')
        entries = ([body] if arguments['name'] == 'run_status' and isinstance(body.get('name'), str)
            else body.get('runs') if arguments['name'] == 'run_list'
            else closeout.get('tasks') if isinstance(closeout, dict) else None)
        if not isinstance(entries, list):
            self._save(dict(terminal_delivery_coverage='structured_tool_result_unavailable'))
            return
        from .scientific_progress import delivery_coverage, read_intent, terminal_fact
        related = goal_bound_runs(checkpoint, json.loads(row['objective_ref_json']))
        decision = checkpoint.get('terminal_delivery')
        if not decision or decision['objective_ref'] != json.loads(row['objective_ref_json']):
            return
        known = {value['run_id'] for value in decision['items']}
        snapshot = checkpoint.get('decision_snapshot', {})
        for entry in entries[:100]:
            if not isinstance(entry, dict) or entry.get('state') not in {'completed', 'failed', 'timed_out', 'cancelled', 'canceled'}:
                continue
            run_id = related.get(entry.get('name'))
            if not run_id or run_id in known:
                continue
            value = self.runtime.runs.status(run_id)
            if value.instance_id != self.instance or value.state != entry['state']:
                continue
            # An earlier admission cannot settle information delivered later in
            # the same native turn. Existing settled rows remain immutable.
            decision.pop('boundary', None)
            decision['items'].append(dict(name=entry['name'], run_id=run_id,
                terminal=terminal_fact(self.runtime.runs, value),
                scientific_intent=read_intent(self.runtime.artifacts, value), delivery=delivery_coverage(entry)))
            snapshot['runs'] = [record for record in snapshot.get('runs', []) if record['name'] != entry['name']]
            snapshot['runs'].append(dict(name=entry['name'], state=value.state,
                output=value.output_ref.model_dump(mode='json') if value.output_ref else None, reason=value.reason))
            known.add(run_id)
        self._save(dict(terminal_delivery=decision, decision_snapshot=snapshot, phase='running'))

    def _identities(self):
        """Attribution uses accepted dispatch and exact native bindings."""
        admissions = json.loads(self._row()['checkpoint_json']).get('admissions', {})
        result = {}
        for admission in admissions.values():
            if not admission.get('run_id'):
                continue
            for identity in self.runtime.runs.native_identities(admission['run_id']):
                result[identity['thread_id']] = dict(identity,
                    interactive_session_id=admission.get('interactive_session_id'))
        return result

    def _reconcile_admissions(self):
        row = self._row()
        checkpoint = json.loads(row['checkpoint_json'])
        admissions = checkpoint.get('admissions', {})
        for name, intent in admissions.items():
            if intent['state'] != 'prepared':
                continue
            matches = self.runtime.runs.admission_matches(instance_id=self.instance,
                output_fingerprint=intent['output_fingerprint'])
            if len(matches) != 1:
                self._save(dict(runtime_status='task_admission_unknown'), reason='task_admission_unknown', stop=True)
                return False
            run_id = matches[0]
            with self.bindings.scheduling_guard(instance_id=self.instance, session_key=row['owner_session'], expected_generation=row['generation']):
                self.bindings.bind(instance=self.instance, namespace='run', name=name,
                    logical_name=intent['logical_name'], revision=intent['revision'], object_id=run_id,
                    request_fingerprint=intent['fingerprint'])
                self.bindings.record_goal_binding(instance_id=self.instance, session_key=row['owner_session'],
                    namespace='run', name=name, object_id=run_id)
                self.bindings.record_dispatch_intent(instance_id=self.instance, session_key=row['owner_session'], run_id=run_id)
        return True

    def _snapshot(self, row):
        """Final results and exact review dependencies wake scientific decisions."""
        facade = self.facade_factory(row['owner_session'])
        checkpoint = json.loads(row['checkpoint_json'])
        runs, review_requests = [], []
        related = goal_bound_runs(checkpoint, json.loads(row['objective_ref_json']))
        selected = dict(related)
        selected.update({name: v['run_id'] for name, v in checkpoint.get('admissions', {}).items() if v.get('run_id')})
        for name, run_id in selected.items():
            value = self.runtime.runs.status(run_id)
            dependency = self.runtime.runs.review_wait_projection(run_id)
            if dependency is not None:
                review_requests.append(dict(owner=name, request=dependency['request'],
                    state=('waiting' if dependency['state'] in {'requested', 'queued', 'running'} else dependency['state'])))
            if name in related and value.state not in {'queued', 'running'}:
                runs.append(dict(name=name, state=value.state, output=value.output_ref.model_dump(mode='json') if value.output_ref else None,
                    reason=value.reason))
        approvals = []
        for name in checkpoint.get('approval_names', []):
            value = facade.approval_status(name=name)
            if value['status'] != 'pending':
                approvals.append(value)
        from .scientific_progress import shadow_projection
        progress = shadow_projection(bindings=self.bindings, row=row)
        correction = progress['assist'].get('id') if progress['mode'] == 'assist' else None
        return dict(goal=row['objective_ref_json'], runs=runs, approvals=approvals, messages=checkpoint.get('messages', []),
            **({'progress_correction': correction} if correction else {}),
            **({'review_requests':review_requests} if review_requests else {}))

    def _brief(self, row, snapshot, limit):
        facade = self.facade_factory(row['owner_session'])
        ref = ArtifactRef.model_validate_json(row['objective_ref_json'])
        artifact = self.runtime.artifacts.catalog(ref)
        goal = dict(name=row['objective_name'], kind=artifact.kind, schema=artifact.schema_id,
            status='omitted', read='artifact_catalog', view='content')
        # Check stored size before reading the exact immutable goal.
        if artifact.size_bytes <= limit // 3:
            raw = self.runtime.artifacts.read(ref)
            goal.update(status='available', original=raw.decode('utf-8'))
        checkpoint = json.loads(row['checkpoint_json'])
        from .scheduling_control import human_handoff_view
        brief = dict(objective=goal, changes=[], omissions=[], budget=checkpoint.get('budget'),
            human_handoff=human_handoff_view(checkpoint),
            previous_report=checkpoint.get('report') or checkpoint.get('last_report'), material_names=[row['objective_name']],
            related_results_omitted=checkpoint.get('relevant_omitted', False),
            limitations=['Originals and full contracts are available through public tools.',
                'Stages are previews; only final sealed outputs establish task conclusions.'])
        from .scientific_progress import progress_page, shadow_projection
        brief['progress_shadow'] = shadow_projection(bindings=self.bindings, row=row)
        brief['progress'] = progress_page(bindings=self.bindings, artifacts=self.runtime.artifacts, row=row, limit=1)
        if checkpoint.get('relevant_omitted'):
            brief['omissions'].append(dict(reason='related_result_limit', read='run_list', view='summary', limit=10))
        brief['review_requests'] = []
        for entry in snapshot.get('review_requests', []):
            run_id = self.bindings.resolve(instance=self.instance, namespace='run', name=entry['owner'])
            dependency = self.runtime.runs.review_wait_projection(run_id)
            if dependency is not None:
                brief['review_requests'].append(dict(owner=entry['owner'], **dependency))
        brief['active_tasks'] = []
        for name, intent in checkpoint.get('admissions', {}).items():
            if not intent.get('run_id'):
                continue
            value = self.runtime.runs.status(intent['run_id'])
            if value.state in {'queued', 'running'}:
                brief['active_tasks'].append(dict(name=name, state=value.state, deadline=value.deadline_at,
                    instruction='Observe this accepted task; do not create a replacement or repeat uncertain native dispatch.'))
        previous = checkpoint.get('processed_snapshot', {})
        prior = {v['name']: v for v in previous.get('runs', [])}
        for run in snapshot['runs']:
            if prior.get(run['name']) == run:
                continue
            result = facade.run_status(name=run['name'], intent='decision')
            brief['changes'].append(result)
            if len(json.dumps(brief, ensure_ascii=False).encode()) > limit:
                brief['changes'].pop()
                brief['omissions'].append(dict(name=run['name'], state=run['state'], read='run_status', intent='decision'))
            output_name = result.get('output_artifact_name')
            if output_name:
                brief['material_names'].append(output_name)
        brief['user_messages'] = []
        for message in snapshot.get('messages', []):
            if message in previous.get('messages', []):
                continue
            ref = ArtifactRef.model_validate(message['artifact_ref'])
            size = self.runtime.artifacts.catalog(ref).size_bytes
            if len(json.dumps(brief, ensure_ascii=False).encode()) + size < limit - 2048:
                raw = self.runtime.artifacts.read(ref)
                brief['user_messages'].append(dict(name=message['name'], original=raw.decode('utf-8')))
            else:
                brief['omissions'].append(dict(name=message['name'], read='artifact_catalog', view='content'))
        brief['approval_changes'] = [value for value in snapshot['approvals'] if value not in previous.get('approvals', [])][-8:]
        if len(snapshot['approvals']) > 8:
            brief['omissions'].append(dict(read='approval_list', omitted=len(snapshot['approvals'])-8))
        while len(json.dumps(brief, ensure_ascii=False).encode()) > limit:
            if brief['approval_changes']:
                brief['approval_changes'].pop(0)
                brief['omissions'].append(dict(read='approval_list', reason='context_limit'))
            elif brief['review_requests']:
                entry = brief['review_requests'].pop(0)
                brief['omissions'].append(dict(name=entry['owner'], read='run_status', intent='status'))
            elif brief.get('progress_shadow') and not brief['progress_shadow'].get('brief_omitted'):
                progress = brief['progress_shadow']
                correction = progress.get('assist', {})
                brief['progress_shadow'] = dict(mode=progress['mode'], brief_omitted=True,
                    **({'assist': {key: correction[key] for key in ('id', 'state', 'causes', 'instruction')}}
                        if correction.get('state') == 'prepared' else {}),
                    read=dict(tool='progression_status'), reason='context_limit')
            elif brief['changes']:
                entry = brief['changes'].pop(0)
                brief['omissions'].append(dict(name=entry['name'], state=entry['state'], read='run_status', intent='decision'))
            else:
                raise ProgressionFault('decision_brief_capacity')
        return INSTRUCTION + '\n' + json.dumps(brief, ensure_ascii=False)

    def _connect(self, row):
        self._restored_turn_id = None
        self.instance = row['instance_id']
        self._last_row = row
        checkpoint = json.loads(row['checkpoint_json'])
        settings = json.loads(row['config_json'])['effective']
        self._limits = {**ProgressionSettings().model_dump(), **settings['progression']}
        self._budget_saved_at = None
        self._goal_deadline = (checkpoint['started_at'] + self._limits['max_elapsed_seconds']
            if 'started_at' in checkpoint else None)
        if settings['progression']['max_tasks'] * (1 + settings['helpers']['max_calls']) + settings['progression']['max_rounds'] > 64:
            raise ProgressionFault('configured_usage_attribution_capacity')
        if checkpoint.get('attempts', 0) >= settings['progression']['max_attempts']:
            self.bindings.observe_progression(instance_id=self.instance, expected_host=json.loads(row['host_json'] or 'null'),
                changes=dict(runtime_status='attempt_budget_exhausted'), reason='attempt_budget_exhausted', stop=True)
            return
        if checkpoint.get('phase') == 'prepared' and not checkpoint.get('turn_id'):
            self.bindings.observe_progression(instance_id=self.instance,
                expected_host=json.loads(row['host_json'] or 'null'), changes=dict(runtime_status='submission_unknown'),
                reason='submission_unknown', stop=True)
            return
        self.events = []
        # Transient adapter context, computed with the coordinator's clock;
        # never reinterpret the durable timestamp using a different clock.
        factory_row = dict(row, _execution_remaining_seconds=(
            max(0, self._goal_deadline-self.clock()) if self._goal_deadline is not None else None))
        host = self.host_factory(factory_row, self._event)
        self.host = host
        # Only the adapter's exact persisted-turn reconciliation permits this
        # continuation. Ordinary failures, user pauses and unknown submissions
        # do not gain an automatic retry merely because a connection exists.
        if (row['host_json'] and row['state'] == 'active' and row['mode'] == 'background'
                and checkpoint.get('phase') == 'running' and checkpoint.get('turn_id')
                and host.turn_id == checkpoint['turn_id']):
            # Terminal interruption may arrive after reconnect's thread/read.
            self._restored_turn_id = checkpoint['turn_id']
        if row['host_json']:
            row = self.bindings.reconnect_host(instance_id=self.instance, scheduler_session=host.scheduler_session,
                platform_session=host.identity.session_id, thread_id=host.identity.thread_id,
                expected_generation=row['generation'])
        else:
            row = self.bindings.activate_host(instance_id=self.instance, source_session=row['requested_by'],
                scheduler_session=host.scheduler_session, platform_session=host.identity.session_id,
                thread_id=host.identity.thread_id, expected_generation=row['generation'])
        initial = dict(runtime_status='connected')
        if 'started_at' not in checkpoint:
            initial.update(started_at=self.clock(), rounds=0, probes=0, attempts=0)
        if checkpoint.get('relevant_runs_objective_ref') != json.loads(row['objective_ref_json']):
            initial.update(self._related_runs(row))
        self._save(initial)
        self._goal_deadline = (checkpoint.get('started_at', initial.get('started_at'))
            + self._limits['max_elapsed_seconds'])
        if hasattr(host, 'set_execution_deadline'):
            host.set_execution_deadline(self._goal_deadline-self.clock())
        for event in self.events:
            self._event(event)
        self.events = []
        if not self._reconcile_admissions():
            return
        for identity in self._identities().values():
            run = self.runtime.runs.status(identity['run_id'])
            if run.state in {'queued', 'running'}:
                try:
                    host.restore_worker(identity['thread_id'], identity['platform_session'], str(self.runtime.project_root),
                        role=identity['role'])
                except Exception:
                    # A Worker can seal while native state is being reconciled.
                    if self.runtime.runs.status(identity['run_id']).state in {'queued', 'running'}:
                        raise

    def _related_runs(self, row):
        initial = dict(relevant_runs={}, relevant_runs_objective_ref=json.loads(row['objective_ref_json']))
        settings = json.loads(row['config_json'])['effective']
        ref = ArtifactRef.model_validate_json(row['objective_ref_json'])
        scope = (self.bindings.progress_shadow(instance_id=self.instance, objective_ref=ref) or {}).get('observation_scope')
        if scope is not None:
            return dict(initial, relevant_runs=scope['relevant_runs'], relevant_omitted=scope['related_omitted'])
        related, omitted = self.runtime.runs.goal_related_runs(instance_id=self.instance, artifact_ref=ref,
            limit=17, source_limit=settings['progression']['related_source_limit'])
        initial['relevant_omitted'] = omitted or len(related) > 16
        for run in related[:16]:
            name = self.bindings.find_name(instance=self.instance, namespace='run', object_id=run.run_id)
            if name:
                initial['relevant_runs'][name] = run.run_id
        return initial

    def _persist_fault(self):
        fault = self._pending_fault
        self._observation(lambda: self.bindings.observe_progression(**fault), terminal=True)
        self._pending_fault = None

    def tick(self):
        with nonblocking_control_io():
            return self._bounded_tick()

    def _bounded_tick(self):
        if self._pending_fault is not None:
            # Maintenance can temporarily prevent recording a connection fault.
            # Retry only that observation; never reconnect the failed host first.
            self._persist_fault()
            return
        try:
            self._tick()
        except Exception as error:
            try:
                if self.instance is not None:
                    try:
                        row = self._row()
                    except Exception:
                        # A busy store must not lose the terminal fault and
                        # cause an automatic reconnect before it is recorded.
                        row = self._last_row
                        if row is None or row['instance_id'] != self.instance:
                            raise
                    uncertain = self._submitting or getattr(getattr(self.host, 'connection', None), 'failed', False)
                    code = getattr(error, 'code', type(error).__name__)
                    reason = ('budget_exhausted' if code in {'budget_deadline', 'observation_budget_expired'}
                        else 'resource_limit' if code == 'resource_limit' else 'host_fault')
                    self._pending_fault = dict(instance_id=self.instance,
                        expected_host=json.loads(row['host_json'] or 'null'),
                        changes=dict(runtime_status=reason, fault_code=code,
                            fault_class='outcome_unknown' if uncertain else 'observation_exhausted'
                                if getattr(error, 'code', None) == 'observation_retry_exhausted' else 'configuration_or_runtime',
                            attempts=json.loads(row['checkpoint_json']).get('attempts', 0)+(reason == 'host_fault')),
                        reason=reason, stop=True)
                    self._persist_fault()
            finally:
                # Closing a client does not prove native quiescence. Keep the
                # persisted writer marker, even if maintenance denied fault IO.
                host, self.host = self.host, None
                if host is not None:
                    host.close()
            raise

    def _tick(self):
        self._submitting = False
        if self.host is None:
            row = self._observation(self.bindings.next_background_progression)
            if row is None:
                return
            self.instance = row['instance_id']
            self._connect(row)
            if self.host is None:
                return
        row = self._row()
        checkpoint = json.loads(row['checkpoint_json'])
        limits = json.loads(row['config_json'])['effective']['progression']
        if row['mode'] == 'background' and row['state'] == 'pending':
            # Explicit resume/start can arrive before the old Root interruption
            # was acknowledged. Reclaim the existing connection only at a proven
            # terminal boundary, preserving accepted work and consumed budgets.
            self.host.interrupt()
            self.host.poll(0)
            if self.host.turn_id and self.host.completion is None:
                return
            processed = checkpoint.get('processed_snapshot', {})
            if self.host.completion and self.host.completion['status'] == 'completed':
                processed = checkpoint.get('decision_snapshot', processed)
            self._save(dict(phase='idle', turn_id=None, processed_snapshot=processed))
            if getattr(self.host, 'terminal_transport_error', None):
                self._save(dict(last_transport_warning='interrupt_reply_timeout_after_terminal'))
                # Explicit resume retains the exact recorded host. Next tick
                # reconnects a fresh client and restores participants; no new
                # model turn can use the failed transport.
                self.host.close()
                self.host = None
                return
            row = self.bindings.reconnect_host(instance_id=self.instance, scheduler_session=self.host.scheduler_session,
                expected_generation=row['generation'], **self._host_binding())
            checkpoint = json.loads(row['checkpoint_json'])
            if not self._reconcile_admissions():
                return
        if row['mode'] != 'background' or row['state'] not in {'active', 'pending'}:
            self.host.interrupt()
            self.host.poll(0)
            if getattr(self.host, 'terminal_transport_error', None) and checkpoint.get('last_transport_warning') != 'interrupt_reply_timeout_after_terminal':
                self._save(dict(last_transport_warning='interrupt_reply_timeout_after_terminal'))
            if self.host.turn_id is None or self.host.completion is not None:
                if self.runtime.runs.active_ids(instance_id=self.instance, limit=1):
                    self._save(dict(runtime_status='paused_accepted_work_continues'))
                    return
                processed = checkpoint.get('processed_snapshot', {})
                if self.host.completion and self.host.completion['status'] == 'completed':
                    processed = checkpoint.get('decision_snapshot', processed)
                self._save(dict(phase='idle', turn_id=None, processed_snapshot=processed))
                self.bindings.release_host(instance_id=self.instance, **self._host_binding())
                self.host.close()
                self.host = None
            return
        if checkpoint.get('relevant_runs_objective_ref') != json.loads(row['objective_ref_json']):
            self._save(self._observation(lambda: self._related_runs(row)))
        self.host.poll(0)
        if self.host.turn_id and self.host.completion is None:
            self._check_budget(row, limits, allow_round=False)
            return
        checkpoint = json.loads(self._row()['checkpoint_json'])
        if checkpoint.get('phase') == 'running':
            if self.host.completion is None:
                raise ProgressionFault('native_turn_state_unknown')
            if self.host.completion.get('id') != checkpoint.get('turn_id'):
                raise ProgressionFault('native_turn_identity_mismatch')
            if not self._reconcile_admissions():
                return
            processed = checkpoint.get('processed_snapshot', {})
            if self.host.completion['status'] == 'completed':
                self._save(dict(native_completion='completed'))
                processed = checkpoint.get('decision_snapshot', processed)
            recovered = (self.host.completion['status'] == 'interrupted'
                and self._restored_turn_id == checkpoint['turn_id'])
            recovery = dict(attempts=checkpoint.get('attempts', 0)+1,
                recovered_interruption=checkpoint['turn_id'],
                last_report=checkpoint.get('report') or checkpoint.get('last_report'), report=None) if recovered else {}
            # Charge recovery and consume the old turn in one checkpoint write.
            # Retain the unprocessed snapshot and accepted tasks for a fresh
            # decision; never replay the interrupted prompt or its tool calls.
            self._save(dict(phase='idle', processed_snapshot=processed,
                running_seconds=checkpoint.get('running_seconds', 0)+max(0, self.clock()-checkpoint.get('round_started_at', self.clock())),
                runtime_status='reconciling_interruption' if recovered else 'waiting', turn_id=None, **recovery))
            self._restored_turn_id = None
            checkpoint = json.loads(self._row()['checkpoint_json'])
            if self.host.completion['status'] != 'completed' and not recovered:
                self._save(dict(runtime_status='root_turn_failed', attempts=checkpoint.get('attempts', 0)+1), reason='root_turn_failed', stop=True)
                return
        if checkpoint.get('human_continuations') or checkpoint.get('interactive_sessions'):
            handoff_snapshot = self._observation(lambda: self._snapshot(self._row()))
            self._observation(lambda: self.bindings.prepare_human_handoff(
                instance_id=self.instance, terminal_runs=handoff_snapshot['runs']))
            checkpoint = json.loads(self._row()['checkpoint_json'])
        if self._observation(lambda: self.bindings.progress_assist_boundary(instance_id=self.instance)):
            return
        report = checkpoint.get('report') or {}
        if report.get('completed') and checkpoint.get('messages', []) == checkpoint.get('processed_snapshot', {}).get('messages', []):
            # The last native response can arrive with turn/completed. Charge it
            # before accepting the goal; reaching the round limit alone is fine
            # when no further round is requested.
            if not self._check_budget(row, limits, allow_round=False, force=True):
                return
            self._save(dict(runtime_status='goal_completed'), reason='goal_completed', stop=True)
            return
        if not self._check_budget(row, limits):
            return
        if self.clock() < checkpoint.get('next_probe_at', 0):
            return
        self._save(dict(probes=checkpoint.get('probes', 0)+1, next_probe_at=self.clock()+limits['poll_seconds']))
        self._observation(lambda: self.bindings.progress_assist_boundary(instance_id=self.instance, event='prepare'))
        snapshot = self._observation(lambda: self._snapshot(self._row()))
        if snapshot == checkpoint.get('processed_snapshot'):
            return
        prompt = self._observation(lambda: self._brief(self._row(), snapshot, limits['context_bytes']-len(INSTRUCTION.encode())))
        from .scientific_progress import delivery_coverage, read_intent, terminal_fact
        delivered = json.loads(prompt.split('\n')[-1])
        shown = {value['name']: value for value in delivered['changes']}
        prior = {value['name']: value for value in checkpoint.get('processed_snapshot', {}).get('runs', [])}
        terminal_delivery = dict(objective_ref=json.loads(row['objective_ref_json']), items=[])
        for value in snapshot['runs']:
            if value == prior.get(value['name']):
                continue
            projection = shown.get(value['name'])
            run = self.runtime.runs.status(self.bindings.resolve(instance=self.instance, namespace='run', name=value['name']))
            terminal_delivery['items'].append(dict(name=value['name'], run_id=run.run_id,
                terminal=terminal_fact(self.runtime.runs, run),
                scientific_intent=read_intent(self.runtime.artifacts, run), delivery=delivery_coverage(projection)))
        # Intent is durable before the non-idempotent native turn/start.
        with self.bindings.scheduling_guard(instance_id=self.instance, session_key=row['owner_session'], expected_generation=row['generation']):
            # The policy a native turn starts with; restoring it later must match.
            permissions = getattr(self.host, 'permissions', None)
            prepared = self._save(dict(phase='prepared', turn_id=None, decision_snapshot=snapshot, terminal_delivery=terminal_delivery,
                progress_notice=delivered.get('progress_shadow', {}).get('assist', {}).get('id'),
                round_started_at=self.clock(),
                root_permissions=permissions.declaration() if permissions is not None else None,
                rounds=checkpoint.get('rounds', 0)+1, runtime_status='deciding',
                last_report=checkpoint.get('report') or checkpoint.get('last_report'), report=None, native_completion=None), reason='host_active')
        if prepared.get('progress_notice_invalidated'):
            return
        self._submitting = True
        turn = self.host.start_turn(prompt)
        self._save(dict(phase='running', turn_id=turn))
        self._submitting = False

    def _check_budget(self, row, limits, allow_round=True, *, force=False):
        from .scheduling_control import background_task_count
        checkpoint = json.loads(self._row()['checkpoint_json'])
        elapsed = max(0, self.clock()-checkpoint['started_at'])
        exhausted = elapsed >= limits['max_elapsed_seconds']
        exhausted |= allow_round and checkpoint.get('rounds', 0) >= limits['max_rounds']
        exhausted |= checkpoint.get('probes', 0) >= limits['max_probes']
        exhausted |= checkpoint.get('attempts', 0) >= limits['max_attempts']
        tokens = sum(sum(v['counted_tokens'][key] for key in ('input_tokens', 'output_tokens')) for v in checkpoint.get('usage_records', {}).values())
        exhausted |= tokens >= limits['max_tokens']
        coverage = checkpoint.get('usage_summary', {}).get('coverage', 'missing')
        expected_threads = {key for key, value in self._identities().items()
            if not value.get('interactive_session_id')} | {self.host.identity.thread_id}
        if (expected_threads - set(checkpoint.get('usage_records', {})) or
                any(v['role'] == 'unattributed' for v in checkpoint.get('usage_records', {}).values())):
            coverage = 'partial' if checkpoint.get('usage_records') else 'missing'
        if hasattr(self.host, 'sample_resources'):
            resources = self.host.sample_resources()
        elif hasattr(self.host, 'resources'):
            if self._sample_host is not self.host or self.clock() >= self._sample_at:
                self._resource_sample = self.host.resources.sample()
                self._sample_host = self.host
                self._sample_at = self.clock() + self._limits['resource_sample_seconds']
            resources = self._resource_sample
        else:
            resources = None
        resource_stop = bool(resources and (resources['owned_tree_rss_bytes'] +
            (resources['control_daemon_rss_bytes'] or 0)) >= limits['max_rss_bytes'])
        exhausted |= resource_stop
        exhausted |= allow_round and limits['token_policy'] == 'strict' and coverage != 'observed'
        running = checkpoint.get('running_seconds', 0)
        if checkpoint.get('phase') in {'prepared', 'running'}:
            running += max(0, self.clock()-checkpoint.get('round_started_at', self.clock()))
        budget = dict(rounds=checkpoint.get('rounds', 0), elapsed_seconds=elapsed,
            root_running_seconds=running, waiting_seconds=max(0, elapsed-running),
            time_coverage='observed_wall_intervals_including_recovery_gaps',
            probes=checkpoint.get('probes', 0), attempts=checkpoint.get('attempts', 0),
            tasks=background_task_count(checkpoint),
            observed_tokens=tokens, limits=limits,
            **token_budget(checkpoint, limits),
            token_coverage=coverage, token_enforcement='asynchronous_observation; time_and_round_limits_apply')
        # Counters/coverage/limits are authority; only elapsed/resource display
        # may lag. Each tick still checks deadlines and newly consumed tokens.
        # Probe counts already persist at the probe boundary; their display
        # copy does not require another write on the following event tick.
        timed = {'elapsed_seconds', 'root_running_seconds', 'waiting_seconds', 'probes'}
        previous = checkpoint.get('budget', {})
        changed = {k:v for k,v in budget.items() if k not in timed} != {k:v for k,v in previous.items() if k not in timed}
        if (force or exhausted or changed or self._budget_saved_at is None
                or self.clock()-self._budget_saved_at >= self._limits['budget_snapshot_seconds']):
            self._save(dict(resources=resources, budget=budget),
                **(dict(reason='resource_limit' if resource_stop else 'budget_exhausted', stop=True) if exhausted else {}))
            self._budget_saved_at = self.clock()
        if resource_stop:
            # Resource emergency is distinct from user pause: stop only the
            # observed owned process identities; retain unknown native writers.
            self.host.resources.terminate()
            self._save(dict(runtime_status='resource_stopped_native_coverage_unknown'))
        return not exhausted

    def close(self):
        self.closed.set()
        if self.thread:
            self.thread.join(timeout=2)
        # Do not race the serial RPC owner, or pretend daemon disconnect stopped
        # native threads. Restart reconciles the durable turn before any new work.
        if not self.thread or not self.thread.is_alive():
            if self.host:
                self.host.close()
                self.host = None
            if self.lease is not None:
                os.close(self.lease)
                self.lease = None
