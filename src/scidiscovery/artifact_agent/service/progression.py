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
from functools import wraps

from ..schema.refs import ArtifactRef
from ...platforms.codex_usage import usage_summary
from .progression_budget import token_budget
from .maintenance import MaintenanceBusy
from .scheduler_bindings import SchedulerInstanceConflict
from .scheduling_control import has_unresolved_platform_requests
from ..storage.control_io import bounded_control_io, control_io_remaining
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
output names and distinguish advance, no_progress and unknown; no extra report gate.
The analysis Worker assesses what an exact bounded experiment changes using its
sealed hypothesis judgments and evidence. Control binds sources and counts each
interpreted experiment once; preparation and experiments await that analysis.
First source-bound scientific dimension changes or stronger predeclared test
resolutions can clear the observation window. Repeated judgments, Root advance,
fresh files and changed thresholds cannot. Missing or unsupported assessment
remains unknown and can require direction confirmation, not a stagnation verdict.
Follow the scientific task boundaries in your Root scheduler instructions; this
continuation adds no experiment handoff conditions. Reuse retained portfolios and
exact analyses rather than mechanically rewriting them. Waiting creates no new
observation.
Consider remaining tokens, the closeout reserve
and observed Worker-thread costs before selecting more work; these are not exact
predictions of a new task. When budget.new_task_allowed is false, consume
accepted results and report the supported conclusion or unfinished work; do not
dispatch another task or repeat admission. The reserve is inside the total budget,
not permission to exceed it, and missing evidence is not a completed goal.
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


class ObservationRetriesExhausted(ProgressionFault):
    """Only the bounded local BUSY/LOCKED or maintenance observation boundary."""
    def __init__(self):
        super().__init__('observation_retry_exhausted')


def _progress_explanation_fingerprint(row, shadow):
    if not isinstance(shadow.get('limitations'), list):
        return None
    return hashlib.sha256(json.dumps(dict(configuration=row['config_json'],limitations=shadow['limitations']),
        ensure_ascii=False,sort_keys=True,separators=(',', ':')).encode()).hexdigest()


def fault_diagnostic(error, phase):
    """Persist bounded code coordinates, never messages, SQL, paths or locals."""
    result=dict(phase=phase if phase in {'idle','prepared','running'} else 'unprepared',stage='unknown',frames=[])
    seen=set()
    for _ in range(4):
        if error is None or id(error) in seen:
            break
        seen.add(id(error))
        code=getattr(error,'sqlite_errorcode',None);name=getattr(error,'sqlite_errorname',None)
        if (type(code) is int and 0<=code<=65535 and isinstance(name,str) and len(name)<=64
                and name.startswith('SQLITE_') and name.isidentifier() and getattr(sqlite3,name,None)==code):
            result.update(sqlite_errorcode=code,sqlite_errorname=name)
        frame=error.__traceback__
        for _ in range(64):
            if frame is None:
                break
            module=frame.tb_frame.f_globals.get('__name__','');function=frame.tb_frame.f_code.co_name
            if (isinstance(module,str) and module.startswith('scidiscovery.') and len(module)<=128
                    and all(part.isidentifier() for part in module.split('.')) and function.isidentifier() and len(function)<=96):
                result['frames']=(result['frames']+[dict(module=module,function=function,line=frame.tb_lineno)])[-4:]
                if module==__name__ and function not in {'tick','_bounded_tick','_observation'}:
                    result['stage']=function
            frame=frame.tb_next
        error=error.__cause__
    return result


def observed(method):
    """Only declared local reads/atomic observations may be re-executed."""
    @wraps(method)
    def observe(self, *args, **kwargs):
        return self._observation(lambda: method(self, *args, **kwargs))
    return observe


class ProgressionCoordinator:
    def __init__(self, *, runtime, host_factory, facade_factory, clock=time.time):
        self.runtime, self.bindings = runtime, runtime.scheduler_bindings
        self.host_factory, self.facade_factory, self.clock = host_factory, facade_factory, clock
        self.bindings.progression_clock = clock
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
        self._submitting = False
        self._goal_deadline = None
        self._deadline_running = None
        self._deadline_generation = None
        self._last_row = None
        self._selecting = False
        self._rotating = False
        self._rotation_generation = None
        self._rotation_usage_binding = None

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
        deadline = time.monotonic() + min(self._limits['observation_retry_seconds'], control_io_remaining())
        for attempt in range(self._limits['observation_retries'] + 1):
            try:
                with bounded_control_io(wait_seconds=self._database_wait,
                        remaining_seconds=lambda: min(deadline-time.monotonic(), self._database_remaining())):
                    return operation()
            except (sqlite3.OperationalError, MaintenanceBusy) as error:
                code = getattr(error, 'sqlite_errorcode', 0) & 255
                if not isinstance(error, MaintenanceBusy) and code not in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
                    raise
                if self.closed.is_set():
                    raise ProgressionFault('coordinator_closed') from error
                if not self._selecting and self._goal_deadline is not None and self.clock() >= self._goal_deadline:
                    raise ProgressionFault('observation_budget_expired') from error
                remaining = min(deadline-time.monotonic(), control_io_remaining())
                if attempt >= self._limits['observation_retries'] or remaining <= 0:
                    raise ObservationRetriesExhausted() from error
                # This also guards resources during RPC callbacks waiting on DB.
                if not terminal and self.host is not None and hasattr(self.host, 'guard_resources'):
                    self.host.guard_resources()
                delay = min(self._limits['observation_backoff_seconds'] * 2**attempt, remaining,
                    self._limits['event_wait_seconds'])
                if not self._selecting and self._goal_deadline is not None:
                    delay = min(delay, max(0, self._goal_deadline-self.clock()))
                if self.closed.wait(delay):
                    raise ProgressionFault('coordinator_closed') from error

    def _database_wait(self):
        return min(self._limits['sqlite_busy_wait_seconds'], self._limits['event_wait_seconds'])

    def _database_remaining(self):
        if self.closed.is_set():
            return 0.
        if not self._selecting and self._goal_deadline is not None:
            return max(0., self._goal_deadline-self.clock())
        return float('inf')

    def _row(self):
        value = self._observation(lambda: self.bindings.progression_status(instance_id=self.instance, internal=True))
        self._last_row = value
        return value

    def _host_binding(self):
        identity = self.host.identity
        return dict(platform_session=identity.session_id, thread_id=identity.thread_id)

    def _save(self, changes, **kwargs):
        expected_host = self._host_binding()
        if changes.get('phase') == 'idle' and self.host.completion:
            kwargs['terminal_turn'] = self.host.completion
        return self._observation(lambda: self.bindings.observe_progression(instance_id=self.instance,
            expected_host=expected_host, changes=changes, **kwargs))

    def _event(self, event):
        # No transcripts in control memory/storage. Only native identity, turn
        # terminal state and cumulative accounting are retained.
        if event.get('method') not in {'thread/tokenUsage/updated', 'turn/started', 'turn/completed', 'scid/serverRequest', 'item/completed'}:
            return
        if self._rotating and event.get('method')=='thread/tokenUsage/updated':
            old,identities=self._rotation_usage_binding
            params=event.get('params',{})
            if params.get('threadId')==old['thread_id'] or params.get('threadId') in identities:
                # Already corroborated participants keep their original ledger
                # even if opening fails or human control prevents attachment.
                self._observation(lambda:self.bindings.observe_progression(instance_id=self.instance,
                    expected_host=old,changes={},usage_observation=dict(params=params,
                        identity=identities.get(params.get('threadId'),{}),root_thread=old['thread_id'])))
                return
        if self.host is None or self._rotating:
            if len(self.events) >= 128:
                raise ProgressionFault('native_initialization_event_limit')
            self.events.append(event)
            return
        params = event.get('params', {})
        row = self._row()
        checkpoint = json.loads(row['checkpoint_json'])
        from .research_loops import current_loop, loop_usage
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
            if thread != self.host.identity.thread_id and thread not in identities:
                original = self._observation(lambda: self.runtime.runs.native_usage_identity(
                    instance_id=self.instance, thread_id=thread))
                if original is not None:
                    identities[thread] = original
            self._save({}, usage_observation=dict(params=params,
                identity=identities.get(thread, {}), root_thread=self.host.identity.thread_id))
        elif thread == self.host.identity.thread_id:
            turn = params.get('turn', {})
            if event['method'] == 'turn/started':
                if checkpoint.get('phase') == 'prepared':
                    self._save(dict(turn_id=turn.get('id'), phase='running'),
                        native_observation=self._root_native_observation(checkpoint,turn.get('id'),'turn_started'))
            elif (turn.get('id') == checkpoint.get('turn_id')
                    and turn.get('status') in {'completed','failed','interrupted'}):
                records = checkpoint.get('usage_records', {})
                if thread in records:
                    records[thread]['outcome'] = 'completed' if turn.get('status') == 'completed' else 'failed'
                observation=self._root_native_observation(checkpoint,turn['id'],'turn_completed',turn['status'])
                self._save(dict(native_completion=turn.get('status'),
                    **({} if observation else dict(usage_records=records)),
                    usage_summary=usage_summary(list(loop_usage(dict(checkpoint, usage_records=records)).values()))),
                    native_observation=observation)
        elif event['method'] in {'turn/started', 'turn/completed'}:
            identity = self._identities().get(thread)
            turn = params.get('turn', {})
            if identity is not None and identity.get('binding_key') and isinstance(turn.get('id'), str):
                if event['method'] == 'turn/started':
                    observation = dict(identity=identity, source='turn_started', turn_id=turn['id'])
                elif turn.get('status') in {'completed','failed','interrupted'}:
                    observation = dict(identity=identity, source='turn_completed', turn_id=turn['id'], state='terminal')
                else:
                    return
                observation.update(connection_id=getattr(self.host,'native_connection_id',None),
                    event_version=getattr(self.host,'native_event_versions',{}).get(thread,0))
                self._save({}, native_observation=observation)

    def _root_native_observation(self, checkpoint, turn_id, source, state='running'):
        connection = getattr(self.host,'native_connection_id',None)
        if not connection:
            return None
        from .research_loops import current_loop
        thread = self.host.identity.thread_id
        return dict(identity=dict(thread_id=thread,role='root',loop_id=current_loop(checkpoint),
            binding_key='root:'+thread),source=source,turn_id=turn_id,
            connection_id=connection,state=state,
            event_version=getattr(self.host,'native_event_versions',{}).get(thread,0))

    @observed
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
            if run_id is None and isinstance(entry.get('name'), str):
                from .progression_records import goal_admission_run
                with self.bindings._connect() as db:
                    run_id = goal_admission_run(db, self.instance, entry['name'],
                        json.loads(row['objective_ref_json']), bindings=self.bindings)
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

    @observed
    def _identities(self):
        """Attribution uses accepted dispatch and exact native bindings."""
        checkpoint = json.loads(self._row()['checkpoint_json'])
        from .research_loops import current_loop
        identity = current_loop(checkpoint)
        if identity:
            from ...agent_execution_settings import progression_usage_capacity
            settings = checkpoint['loop_authorizations'][identity]['config']['effective']
            return self.runtime.runs.native_loop_identities(instance_id=self.instance, loop_id=identity,
                capacity=progression_usage_capacity(settings))
        admissions = checkpoint.get('admissions', {})
        result = {}
        for admission in admissions.values():
            if not admission.get('run_id'):
                continue
            for identity in self.runtime.runs.native_identities(admission['run_id']):
                result[identity['thread_id']] = dict(identity,
                    interactive_session_id=admission.get('interactive_session_id'), loop_id=admission.get('loop_id'))
        return result

    def _reconcile_admissions(self):
        row = self._row()
        checkpoint = json.loads(row['checkpoint_json'])
        admissions = checkpoint.get('admissions', {})
        for name, intent in admissions.items():
            if intent['state'] != 'prepared' and not intent.get('semantic_binding_pending'):
                continue
            matches = self._observation(lambda: self.runtime.runs.admission_matches(instance_id=self.instance,
                output_fingerprint=intent['output_fingerprint']))
            if intent.get('run_id'):
                matches = [intent['run_id']] if intent['run_id'] in matches else []
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
        from .progression_records import goal_admissions
        with self.bindings._connect() as db:
            historical, historical_omitted = goal_admissions(db, self.instance,
                json.loads(row['objective_ref_json']),
                json.loads(row['config_json'])['effective']['progression']['related_source_limit'])
        related.update(historical)
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
            approvals.append(value)
        return dict(goal=row['objective_ref_json'], runs=runs, approvals=approvals, messages=checkpoint.get('messages', []),
            continuation=checkpoint.get('last_command', {}).get('generation'),
            **({'historical_goal_omitted': True} if historical_omitted else {}),
            **({'review_requests':review_requests} if review_requests else {}))

    def _brief(self, row, snapshot, limit):
        def encode(value):
            return json.dumps(value, ensure_ascii=False, separators=(',', ':'))

        facade = self.facade_factory(row['owner_session'])
        checkpoint = json.loads(row['checkpoint_json'])
        host = json.loads(row['host_json'] or '{}')
        context = checkpoint.get('usage_records', {}).get(host.get('thread_id'), {})
        restore_context = not context.get('context_delivered')
        notified = checkpoint.get('notified_snapshot')
        same_objective = isinstance(notified, dict) and notified.get('goal') == row['objective_ref_json']
        ref = ArtifactRef.model_validate_json(row['objective_ref_json'])
        artifact = self.runtime.artifacts.catalog(ref)
        goal = dict(name=row['objective_name'], kind=artifact.kind, schema=artifact.schema_id,
            status='omitted', read='artifact_catalog', view='content',
            continuation='Use returned next_cursor as content_cursor.')
        # Check stored size before reading the exact immutable goal.
        if not restore_context and same_objective:
            goal.update(status='unchanged', guidance='The exact objective is unchanged. Reuse its original only if retained in context; read it by name when context is missing or the next decision needs it. Prior delivery does not prove retained context.')
        elif artifact.size_bytes <= limit // 3:
            raw = self.runtime.artifacts.read(ref)
            goal.update(status='available', original=raw.decode('utf-8'))
        brief = dict(objective=goal, changes=[], omissions=[], budget=checkpoint.get('budget'),
            previous_report=checkpoint.get('report') or checkpoint.get('last_report'), material_names=[row['objective_name']],
            related_results_omitted=checkpoint.get('relevant_omitted', False),
            limitations=['Originals and full contracts are available through public tools.',
                'Stages are previews; only final sealed outputs establish task conclusions.'])
        if snapshot.get('accepted_work_only'):
            brief['scheduling_authority'] = 'Science is paused. Dispatch only the exact review_requests needed by accepted tasks; retain reads and settlement. New research and standalone execution remain forbidden.'
        from .scientific_progress import progress_page, shadow_projection
        brief['progress_shadow'] = shadow_projection(bindings=self.bindings, row=row)
        fingerprint = _progress_explanation_fingerprint(row,brief['progress_shadow'])
        if not restore_context and fingerprint and context.get('progress_explanation_fingerprint') == fingerprint:
            brief['progress_shadow'].pop('limitations')
            brief['progress_shadow']['limitations_reused'] = dict(
                instruction='Reuse the unchanged explanation from this thread if retained; otherwise read progress_shadow.limitations from the returned status.',
                read=dict(tool='progression_status',arguments={}))
        brief['progress'] = progress_page(bindings=self.bindings, artifacts=self.runtime.artifacts, row=row, limit=1)
        def compact_progress():
            return dict(mode=brief['progress_shadow']['mode'], brief_omitted=True,
                read=dict(tool='progression_status'), reason='context_limit')
        if checkpoint.get('relevant_omitted'):
            brief['omissions'].append(dict(reason='related_result_limit', read='run_list', view='summary', limit=10))
        if snapshot.get('historical_goal_omitted'):
            brief['related_results_omitted'] = True
            brief['omissions'].append(dict(reason='historical_goal_identity_limit', read='run_list', view='summary', limit=8,
                continuation='Use returned next_before unchanged; current_goal_tasks identifies this page.'))
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
        brief['active_external_work'] = []
        if self.runtime.executions is not None:
            executions=self.runtime.executions.active_ids(instance_id=self.instance,
                scheduler_database_path=self.bindings.database_path,limit=9)
            brief['external_work_omitted']=len(executions)>8
            if executions:
                brief['external_work_index']=dict(tool='execution_list',surface='execution',limit=8,
                    continuation='Use returned next_before; task-owned work is observed through its Run.')
            for identity in executions[:8]:
                name=self.bindings.find_name(instance=self.instance,namespace='execution',object_id=identity)
                if name is None:
                    brief['external_work_omitted']=True
                    continue
                saved=self.runtime.executions.status(identity)
                owner=facade._task_execution_owner(identity)
                task=self.bindings.find_name(instance=self.instance,namespace='run',object_id=owner) if owner else None
                read=(dict(tool='run_status',name=task,intent='status') if task else
                    dict(tool='execution_list',surface='execution',limit=8))
                brief['active_external_work'].append(dict(name=name,state=saved.state,read=read,
                    instruction='Saved service state; accepted work remains owned by the service. Do not replace or resubmit.'))
        def omit_result(entry):
            brief['result_omissions'] = brief.get('result_omissions', 0) + 1
            brief['omitted_results_read'] = dict(tool='run_list', view='summary', limit=8,
                continuation='Use returned next_before unchanged as before; read exact names with run_status intent=decision.')
            if len(brief['omissions']) < 8:
                brief['omissions'].append(dict(name=entry['name'], state=entry['state'], read='run_status', intent='decision'))
            else:
                brief['omission_details_omitted'] = brief.get('omission_details_omitted', 0) + 1
        previous = checkpoint.get('processed_snapshot', {})
        prior = {v['name']: v for v in previous.get('runs', [])}
        for run in snapshot['runs']:
            if prior.get(run['name']) == run:
                continue
            result = facade.run_status(name=run['name'], intent='decision')
            signal = result.get('scheduler_signal')
            if (result.get('state') == 'completed' and result.get('sealed_output_status') == 'available'
                    and result.get('operation_contract_status') == 'current'
                    and result.get('scheduler_signal_status') == 'available' and isinstance(signal, dict)):
                for index, item in enumerate((result.get('selected_output') or {}).get('items', [])):
                    if (item.get('pointer') == '/summary' and item.get('status') == 'selected'
                            and isinstance(item.get('value'), str) and item['value'] == signal.get('summary')):
                        # A reference stays inside this complete change. Capacity
                        # fallback removes whole changes, never their selected values.
                        signal = {key: value for key, value in signal.items() if key != 'summary'}
                        signal['summary_ref'] = dict(within='this_change', pointer=f'/selected_output/items/{index}/value')
                        result = dict(result, scheduler_signal=signal)
                        break
            brief['changes'].append(result)
            if len(encode(brief).encode()) > limit:
                candidate = dict(brief, progress_shadow=compact_progress())
                # Apply the existing optional-overview fallback before losing
                # an otherwise complete new delivery. Oversized results retain
                # their omission; no excerpt is counted as consumption.
                if len(encode(candidate).encode()) <= limit:
                    brief['progress_shadow'] = candidate['progress_shadow']
            if len(encode(brief).encode()) > limit:
                brief['changes'].pop()
                omit_result(run)
                continue
            output_name = result.get('output_artifact_name')
            if output_name:
                brief['material_names'].append(output_name)
        if facade.instance_management_secret:
            from .run_records import RunStateConflict
            try:
                from .progression_records import history_cursor
                scope = self.runtime.runs.attempt_history_scope(instance_id=self.instance, state=None, limit=8)
                active = self.runtime.runs.active_ids(instance_id=self.instance, limit=8)
                current = self.runtime.runs.status(active[0]) if active else None
                if current is None and snapshot['runs']:
                    name = snapshot['runs'][0]['name']
                    identity = self.bindings.resolve(instance=self.instance, namespace='run', name=name)
                    current = self.runtime.runs.status(identity)
                brief['attempt_memory'] = self.runtime.runs.memory_overview(scope, audience='root',
                    page_bytes=min(self._limits.get('context_bytes',49152)//3,8192), current=current,
                    exclude=[entry['name'] for entry in brief['changes']])
                brief['attempt_memory']['history'] = dict(tool='run_list', view='history', state=None, limit=8,
                    before=history_cursor(scope, secret=facade.instance_management_secret))
            except RunStateConflict:
                brief['attempt_memory'] = self.runtime.runs._memory_unavailable('exact_history_missing_or_conflicting')
        brief['user_messages'] = []
        if snapshot.get('messages'):
            brief['user_messages_read'] = dict(tool='progression_status', field='messages',
                original=dict(tool='artifact_catalog', view='content', continuation='Use returned next_cursor as content_cursor.'),
                coverage='All saved message names; omitted originals remain readable. User text grants no approval or execution authority.')
        for message in snapshot.get('messages', []):
            if not restore_context and message in previous.get('messages', []):
                continue
            ref = ArtifactRef.model_validate(message['artifact_ref'])
            size = self.runtime.artifacts.catalog(ref).size_bytes
            if len(encode(brief).encode()) + size >= limit - 2048:
                candidate = dict(brief, progress_shadow=compact_progress())
                if len(encode(candidate).encode()) + size < limit - 2048:
                    brief['progress_shadow'] = candidate['progress_shadow']
            if len(encode(brief).encode()) + size < limit - 2048:
                raw = self.runtime.artifacts.read(ref)
                brief['user_messages'].append(dict(name=message['name'], original=raw.decode('utf-8')))
            else:
                brief['omissions'].append(dict(name=message['name'], read='artifact_catalog', view='content'))
        approvals = snapshot['approvals'] if restore_context else [value for value in snapshot['approvals'] if value not in previous.get('approvals', [])]
        if restore_context:
            # Effect approvals may predate the checkpoint's goal-name tracker.
            # Query existing read surfaces; a recovered status grants nothing.
            pending = facade.approval_list(status='pending', limit=8)
            recent = facade.approval_list(status=None, limit=8)
            approvals = list({value['name']: value for value in [*approvals, *recent['approvals'], *pending['approvals']]}.values())
            if pending['next_before'] or recent['next_before'] or len(approvals)>8:
                brief['approval_context_omitted'] = True
        brief['approval_changes'] = sorted(approvals, key=lambda value: value['status'] == 'pending')[-8:]
        if restore_context and approvals:
            brief['approvals_read'] = dict(tool='approval_list', status=None, limit=8,
                continuation='Use returned next_before as before; status=pending selects current requests. Read approval_status by exact name before acting.')
        if len(snapshot['approvals']) > 8:
            brief['omissions'].append(dict(read='approval_list', omitted=len(snapshot['approvals'])-8))
        while len(encode(brief).encode()) > limit:
            if brief['approval_changes']:
                brief['approval_changes'].pop(0)
                brief['omissions'].append(dict(read='approval_list', reason='context_limit'))
            elif brief['review_requests']:
                entry = brief['review_requests'].pop(0)
                brief['omissions'].append(dict(name=entry['owner'], read='run_status', intent='status'))
            elif brief.get('progress_shadow') and not brief['progress_shadow'].get('brief_omitted'):
                brief['progress_shadow'] = compact_progress()
            elif brief.get('attempt_memory') and 'recent' in brief['attempt_memory']:
                memory = brief['attempt_memory']
                brief['attempt_memory'] = dict(history=memory['history'], omissions='context_byte_budget; read the frozen time index')
            elif brief['changes']:
                entry = brief['changes'].pop(0)
                if entry.get('output_artifact_name') in brief['material_names']:
                    brief['material_names'].remove(entry['output_artifact_name'])
                omit_result(entry)
            elif brief['active_external_work']:
                brief['active_external_work'].pop()
                brief['external_work_omitted']=True
            elif brief['user_messages']:
                entry = brief['user_messages'].pop()
                brief['omission_details_omitted'] = brief.get('omission_details_omitted', 0) + 1
            elif brief['omissions']:
                brief['omissions'].pop()
                brief['omission_details_omitted'] = brief.get('omission_details_omitted', 0) + 1
            else:
                raise ProgressionFault('decision_brief_capacity')
        return INSTRUCTION + '\n' + encode(brief)

    def _connect(self, row):
        self._restored_turn_id = None
        self.instance = row['instance_id']
        self._last_row = row
        checkpoint = json.loads(row['checkpoint_json'])
        settings = json.loads(row['config_json'])['effective']
        self._limits = {**ProgressionSettings().model_dump(), **settings['progression']}
        self._budget_saved_at = None
        from .progression_budget import time_budget
        timing = time_budget(checkpoint, self._limits, self.clock())
        remaining = timing['effective_remaining_seconds']
        self._goal_deadline = self.clock() + remaining
        unknown = checkpoint.get('fault_class') == 'outcome_unknown' or (
            checkpoint.get('phase') == 'prepared' and not checkpoint.get('turn_id'))
        if not remaining and not unknown:
            self._observation(lambda: self.bindings.observe_progression(instance_id=self.instance,
                expected_host=json.loads(row['host_json'] or 'null'),
                changes=dict(runtime_status='budget_exhausted', budget=timing), reason='budget_exhausted', stop=True))
            return
        from ...agent_execution_settings import require_progression_capacity
        require_progression_capacity(settings)
        if checkpoint.get('attempts', 0) >= settings['progression']['max_attempts']:
            self._observation(lambda: self.bindings.observe_progression(instance_id=self.instance,
                expected_host=json.loads(row['host_json'] or 'null'),
                changes=dict(runtime_status='attempt_budget_exhausted'), reason='attempt_budget_exhausted', stop=True))
            return
        if checkpoint.get('phase') == 'prepared' and not checkpoint.get('turn_id'):
            self._observation(lambda: self.bindings.observe_progression(instance_id=self.instance,
                expected_host=json.loads(row['host_json'] or 'null'), changes=dict(runtime_status='submission_unknown'),
                reason='submission_unknown', stop=True))
            return
        self.events = []
        # Transient adapter context, computed with the coordinator's clock;
        # never reinterpret the durable timestamp using a different clock.
        factory_row = dict(row, _execution_remaining_seconds=remaining)
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
        self._last_row = row
        if hasattr(host,'initial_native_bindings'):
            host.initial_native_bindings = {identity['binding_key'] for identity in self._identities().values()}
        initial = dict(runtime_status='connected')
        if 'started_at' not in checkpoint:
            initial.update(started_at=self.clock(), **{key: checkpoint.get(key, 0)
                for key in ('rounds', 'probes', 'attempts')})
            if 'enabled_seconds' not in checkpoint:
                initial.update(enabled_seconds=0, enabled_at=self.clock(), time_high_water=self.clock())
        if checkpoint.get('relevant_runs_objective_ref') != json.loads(row['objective_ref_json']):
            initial.update(self._related_runs(row))
        self._save(initial)
        self._deadline_running = None
        self._deadline_generation = None
        self._sync_execution_deadline(self._row())
        for event in self.events:
            self._event(event)
        self.events = []
        if not self._reconcile_admissions():
            return
        for identity in self._identities().values():
            run = self._observation(lambda: self.runtime.runs.status(identity['run_id']))
            if run.state in {'queued', 'running'}:
                try:
                    host.restore_worker(identity['thread_id'], identity['platform_session'], str(self.runtime.project_root),
                        role=identity['role'])
                except Exception:
                    # A Worker can seal while native state is being reconciled.
                    if self._observation(lambda: self.runtime.runs.status(identity['run_id'])).state in {'queued', 'running'}:
                        raise

    def _rotate_if_due(self,row,limits):
        cp=json.loads(row['checkpoint_json'])
        record=cp.get('usage_records',{}).get(self.host.identity.thread_id,{})
        rounds=limits.get('root_rotate_after_rounds',0)
        tokens=limits.get('root_rotate_after_input_tokens',0)
        if not ((rounds and cp.get('rounds',0)-record.get('root_started_round',cp.get('rounds',0))>=rounds)
                or (tokens and (record.get('high_water',{}).get('input_tokens') or 0)>=tokens)):
            return False
        if (not self._host_terminal(cp) or cp.get('native_completion')!='completed'
                or cp.get('fault_class')=='outcome_unknown' or has_unresolved_platform_requests(cp)
                or any(i['state']=='prepared' or i.get('semantic_binding_pending') for i in cp.get('admissions',{}).values())):
            return False
        # Service completion is not native child quiescence. No cross-thread
        # notification/ownership transfer is assumed, including released helpers.
        identities=self._identities()
        if not hasattr(self.host,'rotation_boundary'):
            return False
        def terminal_proofs():
            # Exact thin proof projection, including identities outside the
            # ordinary bounded checkpoint detail sample. This is the same ledger.
            with self.bindings._connect() as db:
                return {value['record_key']:json.loads(value['proof'] or '{}') for value in db.execute(
                    "SELECT record_key,json_extract(record_json,'$.native_terminal') AS proof "
                    "FROM scheduler_progression_details WHERE instance_id=? AND collection='usage_records' "
                    'AND record_key IN (SELECT value FROM json_each(?))',
                    (self.instance,json.dumps(list(identities))))}
        host = self.host
        connection = host.native_connection_id
        known = self._observation(terminal_proofs)
        boundary = self.host.rotation_boundary(identities, known=known,
            limit=limits.get('root_rotation_check_limit',16), after=cp.get('rotation_checked_through'))
        for observation in boundary['observations']:
            self._save({}, native_observation=observation)
        self._save(dict(rotation_checked_through=boundary['next_after'], rotation_boundary={key: boundary[key]
            for key in ('checked','unchecked','unknown','reasons')}))
        if not boundary['safe']:
            return False
        old=self._host_binding()
        def prepare():
            # New admission shares this cross-process lock; participants need
            # an active Run. Revalidate the cohort before fencing its owner.
            with self.bindings.scheduling_lock():
                self.host.poll(0)
                if self.runtime.runs.active_ids(instance_id=self.instance,limit=1) or self._identities()!=identities:
                    return None
                proofs = terminal_proofs()
                invalid = [identity for thread,identity in identities.items()
                    if not host.native_terminal_current(identity,proofs.get(thread,{}))]
                if self.host is not host or host.native_connection_id != connection or invalid:
                    self._save(dict(rotation_boundary=dict(checked=boundary['checked'],unchecked=0,
                        unknown=len(invalid),reasons=['native_terminal_proof_invalidated'])))
                    return None
                with self.runtime.runs._connect() as db:
                    if db.execute('SELECT 1 FROM worker_participants p JOIN runs r USING(run_id) WHERE r.instance_id=? AND p.thread_id IS NULL LIMIT 1',(self.instance,)).fetchone():
                        return None
                    # Only committed visible events form this fence. The Run
                    # allocator serializes event IDs in the original write
                    # transaction; an uncommitted completion is not included.
                    activity_fence = db.execute('SELECT COALESCE(MAX(rowid),0) FROM run_activity').fetchone()[0]
                return self.bindings.prepare_host_rotation(instance_id=self.instance,
                    expected_host=old,expected_generation=row['generation'],terminal_turn=self.host.completion,
                    run_activity_fence=activity_fence)
        opening=self._observation(prepare)
        if opening is None:
            return False
        self._last_row=opening
        self._rotation_generation=opening['generation']
        self._rotation_usage_binding=(old,identities)
        self.events=[]
        self._rotating=self._submitting=True
        try:
            self.host.rotate_root()
            try:
                new=self.bindings.complete_host_rotation(instance_id=self.instance,expected_host=old,
                    expected_generation=opening['generation'],scheduler_session=self.host.scheduler_session,**self._host_binding())
            except SchedulerInstanceConflict:
                changed=self._row()
                if changed['generation']==opening['generation']:
                    raise
                # No turn was opened on the verified new thread. Closing it and
                # clearing only the old terminal host marker preserves the human
                # decision, including a takeover while thread/start was in flight.
                self.host.close();self.host=None
                def abandon():
                    with self.bindings.scheduling_lock():
                        current=self.bindings.progression_status(instance_id=self.instance,internal=True)
                        self.bindings.abandon_host_rotation(instance_id=self.instance,
                            expected_host=old,expected_generation=current['generation'])
                self._observation(abandon)
                self.events=[]
                self._submitting=False
                self._rotation_generation=None
                return True
            self._last_row=new
            self._rotating=self._submitting=False
            self._rotation_generation=None
            events,self.events=self.events,[]
            for event in events:
                self._event(event)
            return True
        finally:
            self._rotating=False
            self._rotation_usage_binding=None

    @observed
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
        checkpoint = self._observation(lambda: self.bindings.observe_progression(**fault), terminal=True)
        self._pending_fault = None
        return checkpoint

    def tick(self):
        with bounded_control_io(wait_seconds=self._database_wait, remaining_seconds=self._database_remaining):
            return self._bounded_tick()

    def _bounded_tick(self):
        if self._pending_fault is not None:
            # Maintenance can temporarily prevent recording a connection fault.
            # Retry only that observation; never reconnect the failed host first.
            self._persist_fault()
            return
        try:
            self._selecting = False
            self._observation_recovery_due = False
            self._tick()
            if self._observation_recovery_due:
                self._save({}, recovery_health='observation')
        except Exception as error:
            recovered = False
            try:
                if self.instance is not None and not self._selecting:
                    try:
                        row = self._last_row if isinstance(error, ObservationRetriesExhausted) else self._row()
                    except Exception:
                        # A busy store must not lose the terminal fault and
                        # cause an automatic reconnect before it is recorded.
                        row = self._last_row
                        if row is None or row['instance_id'] != self.instance:
                            raise
                    uncertain = (self._submitting or getattr(error, 'native_outcome_unknown', False)
                        or getattr(getattr(self.host, 'connection', None), 'failed', False))
                    code = getattr(error, 'code', type(error).__name__)
                    reason = ('budget_exhausted' if code in {'budget_deadline', 'observation_budget_expired'}
                        else 'resource_limit' if code == 'resource_limit' else 'host_fault')
                    safe = isinstance(error, ObservationRetriesExhausted) and not uncertain
                    checkpoint = json.loads(row['checkpoint_json'])
                    rotation_control_changed = (checkpoint.get('native_action')=='root_rotation'
                        and self._rotation_generation is not None and row['generation']!=self._rotation_generation)
                    # Opening can fail after a human changed control. Persist
                    # its unknown outcome without replacing that decision/time.
                    self._pending_fault = dict(instance_id=self.instance,
                        expected_host=json.loads(row['host_json'] or 'null'),
                        changes=dict(runtime_status=reason, fault_code=code,
                            fault_diagnostic=fault_diagnostic(error,checkpoint.get('phase')),
                            fault_class='outcome_unknown' if uncertain else 'observation_exhausted'
                                if getattr(error, 'code', None) == 'observation_retry_exhausted' else 'configuration_or_runtime',
                            attempts=checkpoint.get('attempts', 0)+(reason == 'host_fault' and not safe)),
                        reason=None if rotation_control_changed else reason, stop=not rotation_control_changed)
                    if safe:
                        import uuid
                        self._pending_fault['recoverable_fault'] = dict(id=uuid.uuid4().hex, kind='observation',
                            generation=row['generation'], loop_id=checkpoint.get('current_loop_id'))
                    saved = self._persist_fault()
                    recovered = safe and saved.get('recovery', {}).get('pending_kind') == 'observation'
            finally:
                # Closing a client does not prove native quiescence. Keep the
                # persisted writer marker, even if maintenance denied fault IO.
                if not recovered:
                    host, self.host = self.host, None
                    if host is not None:
                        host.close()
                    self._rotation_generation=None
            if recovered:
                return
            raise

    def _settle_turn(self, checkpoint, changes=None, **kwargs):
        processed = checkpoint.get('processed_snapshot', {})
        if self.host.completion and self.host.completion['status'] == 'completed':
            processed = checkpoint.get('decision_snapshot', processed)
        return self._save(dict(phase='idle', turn_id=None, processed_snapshot=processed, **(changes or {})), **kwargs)

    def _host_terminal(self, checkpoint):
        """Only this host's exact terminal turn permits its durable release."""
        if checkpoint.get('fault_class') == 'outcome_unknown':
            return False
        if self.host.turn_id is None:
            return checkpoint.get('turn_id') is None and checkpoint.get('phase') not in {'prepared', 'running'}
        completion = self.host.completion
        return bool(completion and completion.get('id') == self.host.turn_id
            and checkpoint.get('turn_id') in {None, self.host.turn_id}
            and (checkpoint.get('turn_id') is not None or checkpoint.get('phase') == 'idle'))

    def _finish_inactive_host(self):
        checkpoint = json.loads(self._row()['checkpoint_json'])
        if self._host_terminal(checkpoint):
            from .progression_budget import enabled_time
            if checkpoint.get('enabled_at') is not None:
                enabled_time(checkpoint, self.clock(), enabled=False)
                self._save({key: checkpoint[key] for key in ('enabled_seconds', 'enabled_at', 'time_high_water')})
            self._sync_execution_deadline(self._row())
            self.host.poll(0)  # Drain readable late usage before retaining or releasing this terminal Root.
        else:
            self.host.interrupt()
            self.host.poll(0)
        row = self._row()
        if row['mode'] == 'background' and row['state'] in {'active', 'pending'}:
            return
        checkpoint = json.loads(row['checkpoint_json'])
        if getattr(self.host, 'terminal_transport_error', None) and checkpoint.get('last_transport_warning') != 'interrupt_reply_timeout_after_terminal':
            self._save(dict(last_transport_warning='interrupt_reply_timeout_after_terminal'))
        if self._host_terminal(checkpoint):
            if self._observation(lambda: self.runtime.runs.active_ids(instance_id=self.instance, limit=1)):
                self._save(dict(runtime_status='paused_accepted_work_continues'))
                return
            self._settle_turn(checkpoint)
            self._observation(lambda: self.bindings.release_host(instance_id=self.instance, **self._host_binding()))
            host, self.host = self.host, None
            self.instance = self._last_row = self._goal_deadline = None
            host.close()
        return

    def _finish_expired_host(self, row, limits):
        """Stop before every native entry; release only existing terminal proof."""
        from .progression_budget import time_budget
        checkpoint = json.loads(row['checkpoint_json'])
        if (checkpoint.get('fault_class') == 'outcome_unknown'
                or (checkpoint.get('phase') == 'prepared' and not checkpoint.get('turn_id'))
                or time_budget(checkpoint, limits, self.clock())['effective_remaining_seconds'] > 0):
            return False
        self._check_budget(row, limits, allow_round=False, force=True)
        if self._host_terminal(json.loads(self._row()['checkpoint_json'])):
            self._finish_inactive_host()
        else:
            # Client closure is not writer quiescence. Keep exact host/turn/phase.
            self.host.close()
            self.host = None
        return True

    @observed
    def _review_continuation(self, row):
        """Keep the original host through an accepted review and owner settlement."""
        from .scheduling_control import accepted_work_authority
        checkpoint = json.loads(row['checkpoint_json'])
        source = (checkpoint.get('scientific_pause') or {}).get('source_session')
        if row['mode'] != 'background' or source != self.host.scheduler_session:
            return None
        if not self.bindings.client_enabled(session_key=source):
            return None
        with self.bindings._connect() as db:
            for admission in checkpoint.get('admissions', {}).values():
                run_id = admission.get('run_id')
                if not run_id or not accepted_work_authority(db, row, checkpoint, target=('run', run_id), session_key=source):
                    continue
                wait = self.runtime.runs.review_wait(run_id)
                if wait and wait.get('operation_digest'):
                    return ('run', run_id)
        return None

    def _decision_row(self):
        row = self._row()
        if row['state'] == 'paused':
            source = (json.loads(row['checkpoint_json']).get('scientific_pause') or {}).get('source_session')
            return dict(row, owner_session=source)
        return row

    def _sync_execution_deadline(self, row, continuation=None):
        from .progression_budget import enabled_time, time_budget
        checkpoint = json.loads(row['checkpoint_json'])
        if continuation and checkpoint.get('enabled_at') is None:
            enabled_time(checkpoint, self.clock(), enabled=True)
            self._save({key: checkpoint[key] for key in ('enabled_seconds', 'enabled_at', 'time_high_water')})
        running = checkpoint.get('enabled_at') is not None
        changed = self._deadline_running != running or self._deadline_generation != row['generation']
        if changed:
            unknown = checkpoint.get('fault_class') == 'outcome_unknown' or (
                checkpoint.get('phase') == 'prepared' and not checkpoint.get('turn_id'))
            if unknown or not self._host_terminal(checkpoint):
                return  # Unknown submissions and unconfirmed writers retain their original cap.
        remaining = time_budget(checkpoint, self._limits, self.clock())['effective_remaining_seconds']
        self._goal_deadline = self.clock() + remaining if running else None
        if changed and hasattr(self.host, 'set_execution_deadline'):
            self.host.set_execution_deadline(remaining if running else None)
        self._deadline_running = running
        self._deadline_generation = row['generation']

    def _tick(self):
        self.bindings.progression_clock = self.clock
        self._submitting = False
        if self.host is None:
            # Until this read returns an exact subject, a failure belongs to
            # global selection, including after an unresolved client close.
            # Retained writer facts are not an authority for attributing it.
            self._selecting = True
            row = self._observation(self.bindings.next_background_progression)
            self._selecting = False
            if row is None:
                return
            self.instance = row['instance_id']
            self._connect(row)
            if self.host is None:
                return
        row = self._row()
        checkpoint = json.loads(row['checkpoint_json'])
        limits = json.loads(row['config_json'])['effective']['progression']
        if self._finish_expired_host(row, limits):
            return
        recovery = checkpoint.get('recovery', {})
        waiting_recovery = recovery.get('pending_kind')
        if waiting_recovery and row['mode'] == 'background' and row['state'] in {'active', 'pending'}:
            # Read control/time/budgets before backoff; no native entry can run
            # early, including a resume that arrived while recovery was delayed.
            if not self._check_budget(row, limits):
                return
            if not limits['enabled'] or not self._observation(lambda: self.bindings.client_enabled(
                    session_key=row['owner_session'] or row['requested_by'])):
                self._save({}, reason='client_disabled', stop=True)
                return
            if self._observation(lambda: self.bindings.progress_boundary(instance_id=self.instance)):
                return
            if self.clock() < (recovery.get('next_at') or 0):
                return
            self._observation_recovery_due = waiting_recovery == 'observation'
        if row['mode'] == 'background' and row['state'] == 'pending':
            # Explicit resume/start can arrive before the old Root interruption
            # was acknowledged. Reclaim the existing connection only at a proven
            # terminal boundary, preserving accepted work and consumed budgets.
            self._sync_execution_deadline(row)
            self.host.interrupt()
            self.host.poll(0)
            row = self._row()
            checkpoint = json.loads(row['checkpoint_json'])
            if row['mode'] != 'background' or row['state'] != 'pending':
                self._finish_inactive_host()
                return
            if self.host.turn_id and self.host.completion is None:
                return
            self._settle_turn(checkpoint)
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
            self._last_row = row
            checkpoint = json.loads(row['checkpoint_json'])
            if not self._reconcile_admissions():
                return
        continuation = self._review_continuation(row)
        if row['mode'] != 'background' or (row['state'] not in {'active', 'pending'} and not continuation):
            self._finish_inactive_host()
            return
        self._sync_execution_deadline(row, continuation)
        if checkpoint.get('relevant_runs_objective_ref') != json.loads(row['objective_ref_json']):
            self._save(self._observation(lambda: self._related_runs(row)))
        if self._finish_expired_host(self._row(), limits):
            return
        self.host.poll(0)
        row = self._row()
        continuation = self._review_continuation(row)
        if row['mode'] != 'background' or (row['state'] != 'active' and not continuation):
            self._finish_inactive_host()
            return
        self._sync_execution_deadline(row, continuation)
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
            if self.host.completion['status'] == 'completed':
                self._save(dict(native_completion='completed'))
            recovered = (self.host.completion['status'] == 'interrupted'
                and self._restored_turn_id == checkpoint['turn_id'])
            failure = self.host.completion['status'] == 'failed'
            recovery = dict(attempts=checkpoint.get('attempts', 0)+1,
                recovered_interruption=checkpoint['turn_id'],
                last_report=checkpoint.get('report') or checkpoint.get('last_report'), report=None) if recovered else {}
            # Charge recovery and consume the old turn in one checkpoint write.
            # Retain the unprocessed snapshot and accepted tasks for a fresh
            # decision; never replay the interrupted prompt or its tool calls.
            kwargs = {}
            if failure or recovered:
                kwargs = dict(recoverable_fault=dict(kind='failed_turn' if failure else 'interrupted_turn',
                    id=self.host.identity.thread_id+':'+checkpoint['turn_id'],
                    generation=row['generation'], loop_id=checkpoint.get('current_loop_id')),
                    reason='root_turn_failed', stop=True)
                if failure:
                    recovery.update(attempts=checkpoint.get('attempts', 0)+1,
                        last_report=checkpoint.get('report') or checkpoint.get('last_report'), report=None)
            elif self.host.completion['status'] == 'completed':
                kwargs['recovery_health'] = 'completed_turn'
            self._settle_turn(checkpoint, dict(
                running_seconds=checkpoint.get('running_seconds', 0)+max(0, self.clock()-checkpoint.get('round_started_at', self.clock())),
                runtime_status='reconciling_interruption' if recovered else 'root_turn_failed' if failure else 'waiting',
                **recovery), **kwargs)
            self._restored_turn_id = None
            if failure or recovered:
                return
            row = self._row()
            checkpoint = json.loads(row['checkpoint_json'])
            continuation = self._review_continuation(row)
            if row['mode'] != 'background' or (row['state'] != 'active' and not continuation):
                self._finish_inactive_host()
                return
            self._sync_execution_deadline(row, continuation)
            if self.host.completion['status'] != 'completed' and not recovered:
                self._save(dict(runtime_status='root_turn_failed', attempts=checkpoint.get('attempts', 0)+1), reason='root_turn_failed', stop=True)
                return
        if self._observation(lambda: self.bindings.progress_boundary(instance_id=self.instance)):
            return
        report = checkpoint.get('report') or {}
        if not continuation and report.get('completed') and checkpoint.get('messages', []) == checkpoint.get('processed_snapshot', {}).get('messages', []):
            # The last native response can arrive with turn/completed. Charge it
            # before accepting the goal; reaching the round limit alone is fine
            # when no further round is requested.
            if not self._check_budget(row, limits, allow_round=False, force=True):
                return
            self._save(dict(runtime_status='goal_completed'), reason='goal_completed', stop=True)
            return
        if not self._check_budget(row, limits):
            return
        if waiting_recovery in {'failed_turn', 'interrupted_turn'}:
            self._save(dict(runtime_status='reconciling_interruption' if waiting_recovery == 'interrupted_turn'
                else 'recovering_failed_turn'))
            checkpoint = json.loads(self._row()['checkpoint_json'])
        if self.clock() < checkpoint.get('next_probe_at', 0):
            return
        self._save(dict(probes=checkpoint.get('probes', 0)+1, next_probe_at=self.clock()+limits['poll_seconds']))
        snapshot = self._observation(lambda: self._snapshot(self._decision_row()))
        if continuation:
            snapshot['accepted_work_only'] = True
        if snapshot == checkpoint.get('processed_snapshot'):
            return
        def prepare_brief():
            brief_row = self._decision_row()
            return brief_row, self._brief(brief_row, snapshot, limits['context_bytes']-len(INSTRUCTION.encode())-1)
        brief_row, prompt = self._observation(prepare_brief)
        delivered = json.loads(prompt.split('\n')[-1])
        shadow = delivered.get('progress_shadow', {})
        progress_fingerprint = _progress_explanation_fingerprint(brief_row,shadow)
        if shadow.get('limitations_reused'):
            # Reuse preserves an earlier confirmation; it cannot establish one.
            progress_fingerprint = json.loads(brief_row['checkpoint_json']).get('usage_records', {}).get(
                self.host.identity.thread_id, {}).get('progress_explanation_fingerprint')
        shown = {value['name']: value for value in delivered['changes']}
        # An acknowledged notice does not consume its omitted results. Rebuild
        # against the consumed position so a newly fitting batch still wakes Root.
        if (snapshot == checkpoint.get('notified_snapshot') and not shown
                and checkpoint.get('runtime_status') not in {'reconciling_interruption', 'recovering_failed_turn'}):
            return
        prior = {value['name']: value for value in checkpoint.get('processed_snapshot', {}).get('runs', [])}
        terminal_delivery = self._observation(lambda: self._terminal_delivery(row,snapshot,shown))
        # An omitted result remains pending. Only displayed terminal projections
        # (or a later confirmed native tool receipt) can advance consumption.
        decision_snapshot = dict(snapshot, runs=[value for value in snapshot['runs']
            if value['name'] in shown or value == prior.get(value['name'])])
        # The bounded omission count and run_list/run_status entrance cover the
        # omitted exact versions, even when individual names do not fit the brief.
        notification_snapshot = snapshot if delivered.get('omitted_results_read') else decision_snapshot
        # Intent is durable before the non-idempotent native turn/start.
        decision_row = self._decision_row()
        # The policy a native turn starts with; restoring it later must match.
        if not continuation and self._rotate_if_due(self._row(),limits):
            return
        permissions = getattr(self.host, 'permissions', None)
        self._prepare_turn(row, decision_row, continuation, dict(phase='prepared', turn_id=None,
            decision_snapshot=decision_snapshot, notification_snapshot=notification_snapshot,
            terminal_delivery=terminal_delivery, round_started_at=self.clock(),
            root_permissions=permissions.declaration() if permissions is not None else None,
            rounds=checkpoint.get('rounds', 0)+1, runtime_status='deciding',
            last_report=checkpoint.get('report') or checkpoint.get('last_report'), report=None, native_completion=None))
        self._submitting = True
        turn = self.host.start_turn(prompt)
        # Only the successful native turn/start reply confirms this prepared
        # notice. A late turn/started event cannot acknowledge a newer candidate.
        records = json.loads(self._row()['checkpoint_json']).get('usage_records', {})
        record = records.get(self.host.identity.thread_id)
        if record is not None:
            record['context_delivered'] = True
            if progress_fingerprint:
                record['progress_explanation_fingerprint'] = progress_fingerprint
            else:
                record.pop('progress_explanation_fingerprint', None)
        # The authenticated terminal notification may precede the RPC reply.
        # Only a completion for this accepted turn can survive that boundary.
        completion=self.host.completion
        state=(completion['status'] if completion and completion.get('id')==turn
            and completion.get('status') in {'completed','failed','interrupted'} else 'running')
        observation=self._root_native_observation(checkpoint,turn,'turn_started',state)
        if observation:
            observation['progress_explanation_fingerprint'] = progress_fingerprint
        self._save(dict(phase='running', turn_id=turn, notified_snapshot=notification_snapshot,
            native_completion=None if state=='running' else state,
            **({} if observation else dict(usage_records=records))),native_observation=observation)
        self._submitting = False

    @observed
    def _prepare_turn(self, row, decision_row, continuation, changes):
        # Guard reads and this one absolute checkpoint write are rollback-safe.
        with self.bindings.scheduling_guard(instance_id=self.instance, session_key=decision_row['owner_session'],
                expected_generation=row['generation'], continuation=continuation):
            self._save(changes, **({} if continuation else dict(reason='host_active')))

    def _terminal_delivery(self,row,snapshot,shown):
        """Pure post-brief reads; retry before preparing any native submission."""
        from .scientific_progress import delivery_coverage, read_intent, terminal_fact
        checkpoint=json.loads(row['checkpoint_json'])
        prior={value['name']:value for value in checkpoint.get('processed_snapshot',{}).get('runs',[])}
        delivery=dict(objective_ref=json.loads(row['objective_ref_json']),items=[])
        for value in snapshot['runs']:
            if value==prior.get(value['name']) or value['name'] not in shown:
                continue
            run=self.runtime.runs.status(self.bindings.resolve(instance=self.instance,namespace='run',name=value['name']))
            delivery['items'].append(dict(name=value['name'],run_id=run.run_id,
                terminal=terminal_fact(self.runtime.runs,run),scientific_intent=read_intent(self.runtime.artifacts,run),
                delivery=delivery_coverage(shown[value['name']])))
        return delivery

    def _check_budget(self, row, limits, allow_round=True, *, force=False):
        from .scheduling_control import background_task_count
        checkpoint = json.loads(self._row()['checkpoint_json'])
        from .progression_budget import time_budget
        timing = time_budget(checkpoint, limits, self.clock())
        elapsed = timing['elapsed_seconds']
        exhausted = timing['effective_remaining_seconds'] <= 0
        exhausted |= allow_round and checkpoint.get('rounds', 0) >= limits['max_rounds']
        exhausted |= checkpoint.get('attempts', 0) >= limits['max_attempts']
        from .research_loops import current_loop, loop_usage, loop_task_budget
        records = loop_usage(checkpoint)
        tokens = sum(sum(v['counted_tokens'][key] for key in ('input_tokens', 'output_tokens')) for v in records.values())
        exhausted |= tokens >= limits['max_tokens']
        from .research_loops import loop_usage_summary
        coverage = loop_usage_summary(checkpoint)['coverage']
        expected_threads = {key for key, value in self._identities().items()
            if value.get('loop_id') == current_loop(checkpoint) and not value.get('interactive_session_id')} | {self.host.identity.thread_id}
        if (expected_threads - set(records) or any(v['role'] == 'unattributed' for v in records.values())):
            coverage = 'partial' if records else 'missing'
        if hasattr(self.host, 'sample_resources'):
            resources = self.host.sample_resources()
        else:
            resources = None
        resource_stop = bool(resources and (resources['owned_tree_rss_bytes'] +
            (resources['control_daemon_rss_bytes'] or 0)) >= limits['max_rss_bytes'])
        exhausted |= resource_stop
        exhausted |= allow_round and limits['token_policy'] == 'strict' and coverage != 'observed'
        running = checkpoint.get('running_seconds', 0)
        if checkpoint.get('phase') in {'prepared', 'running'}:
            running += max(0, self.clock()-checkpoint.get('round_started_at', self.clock()))
        budget = dict(rounds=checkpoint.get('rounds', 0), **timing,
            root_running_seconds=running, waiting_seconds=max(0, elapsed-running),
            probes=checkpoint.get('probes', 0), attempts=checkpoint.get('attempts', 0),
            **loop_task_budget(checkpoint, limits),
            observed_tokens=tokens, limits=limits,
            **token_budget(checkpoint, limits),
            token_coverage=coverage, token_enforcement='asynchronous_observation; time_and_round_limits_apply')
        from .research_loops import recovery_budget
        budget['recovery'] = recovery_budget(checkpoint, limits)
        # Counters/coverage/limits are authority; only elapsed/resource display
        # may lag. Each tick still checks deadlines and newly consumed tokens.
        # Probe counts already persist at the probe boundary; their display
        # copy does not require another write on the following event tick.
        timed = {'elapsed_seconds', 'remaining_seconds', 'calendar_elapsed_seconds', 'calendar_remaining_seconds',
            'effective_remaining_seconds', 'root_running_seconds', 'waiting_seconds', 'probes'}
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
