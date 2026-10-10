"""Durable platform-thread to Run bindings, owned by the scheduler."""

import json

from ...agent_execution_settings import HelperSettings, ExecutionProfile
from ...operations.tooling import operation_agent_type
from ..schema.common import canonical_json

from ...agent_execution_settings import canonical_model_id
from .run_records import RunStateConflict, timestamp
from ...operation_contract import DiagnosticError, contract_diagnostic

WORKER_CONNECTION_SCHEMA = """
CREATE TABLE IF NOT EXISTS worker_connections (
    run_id TEXT PRIMARY KEY REFERENCES runs(run_id),
    platform_session TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    attached_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS worker_connection_thread
    ON worker_connections(platform_session, thread_id);
CREATE INDEX IF NOT EXISTS worker_usage_thread ON worker_connections(thread_id);
"""

# Zero preserves unknown historical order; only accepted new bindings get a sequence.
WORKER_CONNECTION_COLUMNS = {"attachment_sequence": ("INTEGER NOT NULL DEFAULT 0", 0)}


WORKER_PARTICIPANT_SCHEMA = """
CREATE TABLE IF NOT EXISTS worker_participants (
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    task_origin TEXT NOT NULL REFERENCES runs(run_id),
    name TEXT NOT NULL,
    request_json BLOB NOT NULL,
    platform_session TEXT NOT NULL,
    owner_thread TEXT NOT NULL,
    thread_id TEXT,
    prepared_at TEXT NOT NULL,
    admitted_at TEXT,
    released_at TEXT,
    PRIMARY KEY(task_origin, name),
    UNIQUE(platform_session, thread_id)
);
CREATE INDEX IF NOT EXISTS worker_participant_run ON worker_participants(run_id);
CREATE INDEX IF NOT EXISTS helper_usage_thread ON worker_participants(thread_id);
"""


class HelperAdmissionError(RunStateConflict, DiagnosticError):
    """Keep existing conflict semantics and expose an owner-declared repair."""
    def __init__(self, message):
        RunStateConflict.__init__(self, message)
        self.details = (contract_diagnostic("helper_admission_rejected", phase="tool_arguments",
            affected_action="tool_call", repairable=True, message=message),)


class WorkerNotAttached(RunStateConflict):
    """A platform Worker has not yet been bound to any Run."""


class WorkerConnections:
    def __init__(self, runs):
        self.runs = runs

    @staticmethod
    def _latest(connection, platform_session, thread_id):
        rows = connection.execute(
            "SELECT w.*, r.state, r.operation_id, r.operation_digest, r.execution_profile_json "
            "FROM worker_connections w JOIN runs r USING(run_id) "
            "WHERE w.platform_session=? AND w.thread_id=? "
            "ORDER BY (r.state IN ('queued','running')) DESC, "
            "w.attachment_sequence DESC, w.attached_at DESC LIMIT 2",
            (platform_session, thread_id)).fetchall()
        if len(rows) == 2:
            active = [row['state'] in {'queued', 'running'} for row in rows]
            if all(active) or (not any(active) and rows[0]['attachment_sequence'] == rows[1]['attachment_sequence']
                    and rows[0]['attached_at'] == rows[1]['attached_at']):
                raise RunStateConflict("Worker binding order is ambiguous; attach a fresh native thread.")
        return rows[0] if rows else None

    def attach(self, *, run_id, platform_session, thread_id, allow_rebind=True):
        self.runs.require_task_network_policy(self.runs.status(run_id))
        with self.runs._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM worker_connections WHERE run_id=?", (run_id,)).fetchone()
            same_binding = (existing is not None and
                (existing['platform_session'], existing['thread_id']) == (platform_session, thread_id))
            # Preserve exact legacy owner recovery; block only a new role transfer
            # or correction to a historical helper identity.
            if not same_binding and connection.execute(
                "SELECT 1 FROM worker_participants WHERE platform_session=? AND thread_id=?",
                (platform_session, thread_id)).fetchone() is not None:
                raise RunStateConflict("Worker thread has helper history; use a fresh owner thread, even after helper release")
            row = connection.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if row is None or row["state"] != "queued":
                if row is not None and row["state"] == "running" and same_binding:
                    return
                raise RunStateConflict("attach requires the exact queued Run")
            status = self.runs.status(run_id)
            self._require_same_loop_thread(connection, status, platform_session, thread_id)
            self._require_independent(connection, status, platform_session, thread_id)
            previous = self._latest(connection, platform_session, thread_id)
            if previous is not None and previous["run_id"] != run_id:
                if not allow_rebind:
                    raise RunStateConflict("Worker bootstrap requires a fresh native thread for a new task")
                if previous["state"] in {"queued", "running"}:
                    raise RunStateConflict("Worker thread already belongs to an active Run")
                old_profile = json.loads(previous["execution_profile_json"] or "null")
                new_profile = json.loads(row["execution_profile_json"] or "null")
                if (any(previous[key] != row[key] for key in ("operation_id", "operation_digest"))
                        or old_profile is None or new_profile is None
                        or canonical_model_id(old_profile["profile"]["model"])
                        != canonical_model_id(new_profile["profile"]["model"])
                        or old_profile["profile"]["reasoning_effort"]
                        != new_profile["profile"]["reasoning_effort"]):
                    raise RunStateConflict("reuse requires the same compiled Operation and execution profile")
            current = connection.execute("SELECT * FROM worker_connections WHERE run_id=?", (run_id,)).fetchone()
            sequence = connection.execute(
                "SELECT COALESCE(MAX(attachment_sequence),0)+1 FROM worker_connections "
                "WHERE platform_session=? AND thread_id=?", (platform_session, thread_id)).fetchone()[0]
            if current is not None:
                if (current["platform_session"], current["thread_id"]) != (platform_session, thread_id):
                    if not allow_rebind:
                        raise RunStateConflict("Worker bootstrap already belongs to another native thread")
                    # Nothing scientific has been opened yet. Correct a mistaken
                    # platform handle without consuming/failing the queued Run.
                    connection.execute("UPDATE worker_connections SET platform_session=?,thread_id=?,attached_at=?,attachment_sequence=? WHERE run_id=?",
                        (platform_session, thread_id, timestamp(), sequence, run_id))
                return
            connection.execute(
                "INSERT INTO worker_connections(run_id,platform_session,thread_id,attached_at,attachment_sequence) VALUES(?,?,?,?,?)",
                (run_id, platform_session, thread_id, timestamp(), sequence))

    def _require_same_loop_thread(self, connection, status, platform_session, thread_id):
        """A native cumulative counter keeps one loop owner for its lifetime."""
        loop_id = (status.recovery_policy or {}).get('loop_id')
        prior = connection.execute('SELECT r.recovery_policy_json FROM runs r JOIN worker_connections w USING(run_id) '
            'WHERE w.platform_session=? AND w.thread_id=? UNION ALL '
            'SELECT r.recovery_policy_json FROM runs r JOIN worker_participants p USING(run_id) '
            'WHERE p.platform_session=? AND p.thread_id=?',
            (platform_session, thread_id, platform_session, thread_id)).fetchall()
        if any(json.loads(item[0] or '{}').get('loop_id') != loop_id for item in prior):
            raise RunStateConflict('A Worker or helper native thread cannot be reused across research loops; attach a fresh thread.')

    def resolve(self, *, platform_session, thread_id):
        with self.runs._connect() as connection:
            row = self._latest(connection, platform_session, thread_id)
        if row is None:
            raise WorkerNotAttached("Worker is awaiting scheduler attachment; no assignment is authorized yet")
        return self.runs.status(row["run_id"])

    def previous_run(self, *, run_id, platform_session, thread_id):
        """Derive the predecessor from existing bindings, never a new reuse ledger."""
        with self.runs._connect() as connection:
            rows = connection.execute(
                "SELECT previous.run_id, previous.attachment_sequence, previous.attached_at FROM worker_connections current "
                "JOIN worker_connections previous ON previous.platform_session=current.platform_session "
                "AND previous.thread_id=current.thread_id "
                "WHERE current.run_id=? AND current.platform_session=? AND current.thread_id=? "
                "AND (previous.attachment_sequence < current.attachment_sequence OR "
                "(current.attachment_sequence=0 AND previous.attachment_sequence=0 "
                "AND previous.attached_at < current.attached_at)) "
                "ORDER BY previous.attachment_sequence DESC, previous.attached_at DESC LIMIT 2",
                (run_id, platform_session, thread_id)).fetchall()
        if len(rows) == 2 and tuple(rows[0])[1:] == tuple(rows[1])[1:]:
            return None  # Historical ambiguity means full startup guidance, not guessed reuse.
        return rows[0]["run_id"] if rows else None

    def review_authors(self, connection, compiled, inputs, instance_id):
        """One source of pre-creation author eligibility and attach independence."""
        from ...operations.invoke import OperationInvocationError
        owners = set()
        origins = self.runs.input_origins(instance_id)
        ports = {port.name: port for port in compiled.spec.inputs}
        for item in inputs:
            if item.port_name not in compiled.spec.independent_review_ports:
                continue
            public = ports[item.port_name]
            while public.derivation is not None:
                public = ports[public.derivation.anchor_port]
            public_port = public.name if public.agent_visible else None
            try:
                authors = origins.review_author_runs(item.artifact_name, item.artifact_ref)
            except OperationInvocationError as error:
                raise OperationInvocationError(error.reason_code, port=public_port,
                    message=error.details[0]['message']) from error
            for author in authors:
                author_owners = set()
                for prior in self.runs.task_lineage(author):
                    row = connection.execute("SELECT platform_session,thread_id FROM worker_connections WHERE run_id=?", (prior.run_id,)).fetchone()
                    if row is not None:
                        author_owners.add(tuple(row))
                    author_owners.update(tuple(row) for row in connection.execute(
                        "SELECT platform_session,thread_id FROM worker_participants WHERE run_id=? AND thread_id IS NOT NULL", (prior.run_id,)))
                if not author_owners:
                    raise OperationInvocationError("review_author_identity_unavailable", port=public_port,
                        message="The subject's participating author identity is unavailable. Repair the original task's verified authorship before requesting independent review.")
                owners.update(author_owners)
        return owners

    def _require_independent(self, connection, status, session, thread):
        owners = self.review_authors(connection, self.runs.compiled_operation(status), status.inputs, status.instance_id)
        if (session, thread) in owners:
            raise RunStateConflict("Independent review requires a different Agent from every participating author.")

    def helper_request(self, run_id, request):
        """Reserve or revoke Run tool access; native spawn/wait/close stays on the platform."""
        run = self.runs.running_task(run_id)
        lineage = self.runs.task_lineage(run_id)
        origin = lineage[-1].run_id
        saved_settings = (run.recovery_policy or {}).get("helpers", {"max_depth": 0})
        settings = HelperSettings.model_validate({"profiles": {}, **saved_settings})
        if request.action == "prepare" and (not request.task or not settings.max_depth or not settings.max_active):
            raise HelperAdmissionError("Provide a scientific subtask; helper access must be enabled for this task.")
        selected = request.profile or settings.default_profile
        work = {"task": request.task, "materials": request.materials, "profile": selected}
        profile = dict(run.execution_profile["profile"])
        input_limit, call_limit = settings.max_input_bytes, settings.max_calls
        if request.action == "prepare" and selected != "inherit":
            configured = settings.profiles.get(selected)
            if configured is None or configured.model is None or configured.reasoning_effort is None:
                raise HelperAdmissionError("The selected helper profile is not configured; choose inherit or repair helper configuration.")
            profile.update(model=configured.model, reasoning_effort=configured.reasoning_effort)
            if configured.max_input_bytes is not None:
                input_limit = min(input_limit, configured.max_input_bytes)
            if configured.max_calls is not None:
                call_limit = min(call_limit, configured.max_calls)
        profile = ExecutionProfile.model_validate(profile).model_dump()
        raw = canonical_json({**work, "execution_profile": profile})
        if request.action == "prepare" and len(canonical_json({"task":request.task, "materials":request.materials})) > input_limit:
            raise HelperAdmissionError("Helper task and references exceed the configured input byte limit.")
        with self.runs._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute("SELECT state,accepted_candidate_digest FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if current['state'] != 'running' or current['accepted_candidate_digest'] is not None:
                raise HelperAdmissionError("The task no longer accepts helper participation.")
            owner = connection.execute("SELECT * FROM worker_connections WHERE run_id=?", (run_id,)).fetchone()
            if owner is None:
                raise HelperAdmissionError("Native helpers require a trusted gateway-bound task owner.")
            old = connection.execute("SELECT * FROM worker_participants WHERE task_origin=? AND name=?", (origin, request.name)).fetchone()
            if request.action == "release":
                if old is None:
                    raise HelperAdmissionError("No helper has this scientific subtask name.")
                # Historical owner bindings block cleanup regardless of clocks or
                # terminal state. Read them under the same lock as revocation.
                rebound = connection.execute(
                    "SELECT 1 FROM worker_connections WHERE platform_session=? AND thread_id=?",
                    (old['platform_session'], old['thread_id'])).fetchone() if old['thread_id'] is not None else None
                connection.execute("UPDATE worker_participants SET released_at=COALESCE(released_at,?) WHERE task_origin=? AND name=?", (timestamp(), origin, request.name))
                if rebound is not None:
                    return {"name": request.name, "access": "released", "native_thread_state": "unknown",
                        "native_action": None,
                        "instruction": "This historical helper thread has owner binding history. "
                            "Do not interrupt or close it for this old subtask, including through the original spawn handle. "
                            "Access to this subtask is revoked; native interruption and slot reclamation are not confirmed."}
                if old['thread_id'] is None:
                    return {"name": request.name, "access": "released", "native_thread_state": "unknown",
                        "native_action": None, "cleanup_status": "blocked",
                        "instruction": "No trusted helper thread was admitted. Native cleanup is blocked, not confirmed. "
                            "Do not interrupt or close using an original spawn handle, guess an identity, or respawn. "
                            "Normal dispatch must complete worker_open_assignment admission before work and release. "
                            "Report the unresolved spawn/bootstrap outcome for repair; access to this subtask is revoked."}
                if old['released_at'] is not None:
                    return {"name": request.name, "access": "released", "native_thread_state": "unknown",
                        "native_action": None,
                        "instruction": "Access was already revoked; this repeated release grants no new native action. "
                            "Do not replay a cached interrupt or close instruction. If the first action or its result was lost, "
                            "report cleanup unconfirmed; do not claim interruption or slot reclamation."}
                return {"name": request.name, "access": "released", "native_thread_state": "unknown",
                    "native_action": {"action": "interrupt", "thread_id": old["thread_id"],
                                      "task_name": request.name, "required": True},
                    "instruction": "As your next action, interrupt the exact bound thread_id through the native collaboration tool, "
                        "even after completion; then close it if supported. Do not schedule other work, reuse the thread, "
                        "or cache this instruction for later replay. Report the native result or failure. "
                        "Access is revoked; native interruption and slot reclamation are not confirmed by this response. "
                        "The control transaction and external native call are not atomic; arbitrary native reuse is outside this guarantee."}
            if old is not None:
                previous = json.loads(old['request_json'])
                previous_work = {"task":previous['task'], "materials":previous['materials'],
                                 "profile":previous.get('profile', 'inherit')}
                if previous_work != work:
                    raise HelperAdmissionError("This subtask name already identifies different work; choose a new scientific name.")
                profile = self.helper_profile(run, old)
                # A lost prepare response is idempotent. Bound/released helpers never spawn again implicitly.
                if old['thread_id'] is not None or old['released_at'] is not None or old['run_id'] != run_id:
                    return {"name": request.name, "access": "released" if old['released_at'] else "admitted",
                        "instruction": "Use the existing native helper. Do not respawn this subtask; its result and lifecycle belong to the platform."}
            else:
                rows = connection.execute("SELECT released_at,request_json FROM worker_participants WHERE task_origin=?", (origin,)).fetchall()
                # Historical CLI reservations consume the same original call allowance.
                legacy = sum(connection.execute("SELECT COUNT(*) FROM run_activity WHERE run_id=? AND activity='helper_reserved'", (item.run_id,)).fetchone()[0] for item in lineage)
                if len(rows) + legacy >= settings.max_calls:
                    raise HelperAdmissionError("The original task's helper admission allowance is exhausted.")
                profile_calls = sum(json.loads(row['request_json']).get('profile', 'inherit') == selected for row in rows)
                if profile_calls >= call_limit:
                    raise HelperAdmissionError("The selected helper profile's original task allowance is exhausted.")
                if sum(row['released_at'] is None for row in rows) >= settings.max_active:
                    raise HelperAdmissionError("Integrate or stop the current helper, then release its access before another subtask.")
                connection.execute("INSERT INTO worker_participants(run_id,task_origin,name,request_json,platform_session,owner_thread,prepared_at) VALUES(?,?,?,?,?,?,?)",
                    (run_id, origin, request.name, raw, owner['platform_session'], owner['thread_id'], timestamp()))
        return {"name": request.name, "access": "prepared", "dispatch": {
            "agent_type": operation_agent_type(self.runs.compiled_operation(run)),
            "context": "fresh", "task_name": request.name, "profile": selected,
            "model": profile["model"], "reasoning_effort": profile["reasoning_effort"],
            "message": "Open worker_open_assignment for the prepared internal subtask. Follow its helper participation instructions; do not submit the parent task.",
            "instruction": "Spawn a fresh native helper thread with fork_context=false or fork_turns=none, with exactly the returned model/reasoning_effort and without parent history. Have it complete worker_open_assignment admission before work and release; never reuse an owner thread for a helper or a helper thread for an owner. If a native spawn response is lost, inspect its existing task by this name; never repeat an uncertain spawn. Wait for native completion and integrate its findings/files. Use worker_helper release afterwards; when its first response returns a required interrupt, execute it as your next native action, even after completion, then close if supported. Do not cache or replay the action. Without a returned action, do not interrupt or close through an old spawn handle; report cleanup blocked or unconfirmed."}}

    @staticmethod
    def helper_profile(run, participant):
        saved = json.loads(participant['request_json']).get('execution_profile')
        # Existing admitted helpers predate selectable profiles and inherit their Run.
        return saved if saved is not None else run.execution_profile['profile']

    def participant(self, *, platform_session, thread_id, parent_thread=None, admit=False,
                    model=None, reasoning_effort=None):
        """Resolve an existing helper or admit exactly one prepared direct child."""
        with self.runs._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            # Serialize against attach on the same database: either owner attachment
            # or helper admission wins, never both. Historical author records remain.
            if connection.execute(
                "SELECT 1 FROM worker_connections WHERE platform_session=? AND thread_id=?",
                (platform_session, thread_id)).fetchone() is not None:
                if not admit:
                    raise WorkerNotAttached("Worker has owner binding history and is not an internal helper")
                raise RunStateConflict("Worker thread has owner binding history; use a fresh helper thread")
            row = connection.execute("SELECT * FROM worker_participants WHERE platform_session=? AND thread_id=?", (platform_session, thread_id)).fetchone()
            if row is None:
                if not admit or not parent_thread:
                    raise WorkerNotAttached("Worker is awaiting scheduler attachment; no assignment is authorized yet")
                owner = connection.execute("SELECT w.run_id FROM worker_connections w JOIN runs r USING(run_id) WHERE platform_session=? AND thread_id=? AND r.state='running' ORDER BY attached_at DESC LIMIT 1", (platform_session, parent_thread)).fetchone()
                if owner is None:
                    raise WorkerNotAttached("No live parent task authorizes this helper")
                row = connection.execute("SELECT * FROM worker_participants WHERE run_id=? AND platform_session=? AND owner_thread=? AND thread_id IS NULL AND released_at IS NULL", (owner['run_id'], platform_session, parent_thread)).fetchone()
                if row is None:
                    raise WorkerNotAttached("The task owner has not prepared a helper subtask")
                run = self.runs.running_task(row['run_id'])
                self._require_same_loop_thread(connection, run, platform_session, thread_id)
                self._require_independent(connection, run, platform_session, thread_id)
                expected = self.helper_profile(run, row)
                if (canonical_model_id(model), reasoning_effort) != (canonical_model_id(expected['model']), expected['reasoning_effort']):
                    raise RunStateConflict("Helper platform model/effort do not match its frozen profile; use the prepared dispatch.")
                connection.execute("UPDATE worker_participants SET thread_id=?,admitted_at=? WHERE task_origin=? AND name=?", (thread_id, timestamp(), row['task_origin'], row['name']))
                row = dict(row)
                row['thread_id'] = thread_id
            if row['released_at'] is not None:
                raise RunStateConflict("Helper Run tool access has ended; native thread state is unknown")
            if parent_thread is not None and row['owner_thread'] != parent_thread:
                raise RunStateConflict("Helper parent identity differs from its durable binding")
            run = self.runs.running_task(row['run_id'])
            return run, dict(row)

    def release_helpers(self, run_id):
        """Revocation only. Neither a completion receipt nor a process-stop assertion."""
        with self.runs._connect() as connection:
            connection.execute("UPDATE worker_participants SET released_at=COALESCE(released_at,?) WHERE run_id=?", (timestamp(), run_id))
