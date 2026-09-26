"""Durable platform-thread to Run bindings, owned by the scheduler."""

import json

from ...agent_execution_settings import HelperSettings
from ...operations.tooling import operation_agent_type
from ..schema.common import canonical_json

from ...agent_execution_settings import canonical_model_id
from .run_records import RunStateConflict, timestamp

WORKER_CONNECTION_SCHEMA = """
CREATE TABLE IF NOT EXISTS worker_connections (
    run_id TEXT PRIMARY KEY REFERENCES runs(run_id),
    platform_session TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    attached_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS worker_connection_thread
    ON worker_connections(platform_session, thread_id);
"""


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
"""


class WorkerNotAttached(RunStateConflict):
    """A platform Worker has not yet been bound to any Run."""


class WorkerConnections:
    def __init__(self, runs):
        self.runs = runs

    def attach(self, *, run_id, platform_session, thread_id):
        with self.runs._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute(
                "SELECT 1 FROM worker_participants WHERE platform_session=? AND thread_id=? "
                "AND released_at IS NULL", (platform_session, thread_id)).fetchone() is not None:
                raise RunStateConflict("Worker thread is an active helper; release its task access before owner attachment")
            row = connection.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if row is None or row["state"] != "queued":
                existing = connection.execute(
                    "SELECT * FROM worker_connections WHERE run_id=?", (run_id,)).fetchone()
                if (row is not None and row["state"] == "running" and existing is not None
                        and (existing["platform_session"], existing["thread_id"]) == (platform_session, thread_id)):
                    return
                raise RunStateConflict("attach requires the exact queued Run")
            status = self.runs.status(run_id)
            self._require_independent(connection, status, platform_session, thread_id)
            previous = connection.execute(
                "SELECT w.*, r.state, r.operation_id, r.operation_digest, r.execution_profile_json "
                "FROM worker_connections w JOIN runs r USING(run_id) "
                "WHERE w.platform_session=? AND w.thread_id=? ORDER BY w.attached_at DESC, w.run_id DESC LIMIT 1",
                (platform_session, thread_id)).fetchone()
            if previous is not None and previous["run_id"] != run_id:
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
            if current is not None:
                if (current["platform_session"], current["thread_id"]) != (platform_session, thread_id):
                    raise RunStateConflict("Run already belongs to another Worker thread")
                return
            connection.execute(
                "INSERT INTO worker_connections(run_id,platform_session,thread_id,attached_at) VALUES(?,?,?,?)",
                (run_id, platform_session, thread_id, timestamp()))

    def resolve(self, *, platform_session, thread_id):
        with self.runs._connect() as connection:
            row = connection.execute(
                "SELECT run_id FROM worker_connections WHERE platform_session=? AND thread_id=? "
                "ORDER BY attached_at DESC, run_id DESC LIMIT 1", (platform_session, thread_id)).fetchone()
        if row is None:
            raise WorkerNotAttached("Worker is awaiting scheduler attachment; no assignment is authorized yet")
        return self.runs.status(row["run_id"])

    def previous_run(self, *, run_id, platform_session, thread_id):
        """Derive the predecessor from existing bindings, never a new reuse ledger."""
        with self.runs._connect() as connection:
            row = connection.execute(
                "SELECT previous.run_id FROM worker_connections current "
                "JOIN worker_connections previous ON previous.platform_session=current.platform_session "
                "AND previous.thread_id=current.thread_id "
                "WHERE current.run_id=? AND current.platform_session=? AND current.thread_id=? "
                "AND (previous.attached_at < current.attached_at OR "
                "(previous.attached_at=current.attached_at AND previous.run_id < current.run_id)) "
                "ORDER BY previous.attached_at DESC, previous.run_id DESC LIMIT 1",
                (run_id, platform_session, thread_id)).fetchone()
        return row["run_id"] if row is not None else None

    def _require_independent(self, connection, status, session, thread):
        for item in status.inputs:
            if item.port_name not in self.runs.compiled_operation(status).spec.independent_review_ports:
                continue
            author = item.producer_run_id or self.runs.artifacts.catalog(item.artifact_ref).labels.get("tool_producer_run")
            if author is None:
                raise RunStateConflict("Independent review requires a sealed subject with a known author.")
            owners = []
            for prior in self.runs.task_lineage(author):
                row = connection.execute("SELECT platform_session,thread_id FROM worker_connections WHERE run_id=?", (prior.run_id,)).fetchone()
                if row is not None:
                    owners.append(tuple(row))
                owners.extend(tuple(row) for row in connection.execute(
                    "SELECT platform_session,thread_id FROM worker_participants WHERE run_id=? AND thread_id IS NOT NULL", (prior.run_id,)))
            if not owners:
                raise RunStateConflict("The subject's author identity is unavailable for independent review.")
            if (session, thread) in owners:
                raise RunStateConflict("Independent review requires a different Agent from every participating author.")

    def helper_request(self, run_id, request):
        """Reserve or revoke Run tool access; native spawn/wait/close stays on the platform."""
        run = self.runs.running_task(run_id)
        lineage = self.runs.task_lineage(run_id)
        origin = lineage[-1].run_id
        settings = HelperSettings.model_validate((run.recovery_policy or {}).get("helpers", {"max_depth": 0}))
        if request.action == "prepare" and (not request.task or not settings.max_depth or not settings.max_active):
            raise RunStateConflict("Provide a scientific subtask; helper access must be enabled for this task.")
        raw = canonical_json({"task": request.task, "materials": request.materials})
        if len(raw) > settings.max_input_bytes:
            raise RunStateConflict("Helper task and references exceed the configured input byte limit.")
        with self.runs._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute("SELECT state,accepted_candidate_digest FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if current['state'] != 'running' or current['accepted_candidate_digest'] is not None:
                raise RunStateConflict("The task no longer accepts helper participation.")
            owner = connection.execute("SELECT * FROM worker_connections WHERE run_id=?", (run_id,)).fetchone()
            if owner is None:
                raise RunStateConflict("Native helpers require a trusted gateway-bound task owner.")
            old = connection.execute("SELECT * FROM worker_participants WHERE task_origin=? AND name=?", (origin, request.name)).fetchone()
            if request.action == "release":
                if old is None:
                    raise RunStateConflict("No helper has this scientific subtask name.")
                connection.execute("UPDATE worker_participants SET released_at=COALESCE(released_at,?) WHERE task_origin=? AND name=?", (timestamp(), origin, request.name))
                return {"name": request.name, "access": "released", "native_thread_state": "unknown",
                    "instruction": "Use native stop/close if work remains active. Permission release does not stop native tools or assert thread termination."}
            if old is not None:
                if bytes(old['request_json']) != raw:
                    raise RunStateConflict("This subtask name already identifies different work; choose a new scientific name.")
                # A lost prepare response is idempotent. Bound/released helpers never spawn again implicitly.
                if old['thread_id'] is not None or old['released_at'] is not None or old['run_id'] != run_id:
                    return {"name": request.name, "access": "released" if old['released_at'] else "admitted",
                        "instruction": "Use the existing native helper. Do not respawn this subtask; its result and lifecycle belong to the platform."}
            else:
                rows = connection.execute("SELECT released_at FROM worker_participants WHERE task_origin=?", (origin,)).fetchall()
                # Historical CLI reservations consume the same original call allowance.
                legacy = sum(connection.execute("SELECT COUNT(*) FROM run_activity WHERE run_id=? AND activity='helper_reserved'", (item.run_id,)).fetchone()[0] for item in lineage)
                if len(rows) + legacy >= settings.max_calls:
                    raise RunStateConflict("The original task's helper admission allowance is exhausted.")
                if sum(row['released_at'] is None for row in rows) >= settings.max_active:
                    raise RunStateConflict("Integrate or stop the current helper, then release its access before another subtask.")
                connection.execute("INSERT INTO worker_participants(run_id,task_origin,name,request_json,platform_session,owner_thread,prepared_at) VALUES(?,?,?,?,?,?,?)",
                    (run_id, origin, request.name, raw, owner['platform_session'], owner['thread_id'], timestamp()))
        return {"name": request.name, "access": "prepared", "dispatch": {
            "agent_type": operation_agent_type(self.runs.compiled_operation(run)),
            "context": "fresh", "task_name": request.name,
            "message": "Open worker_open_assignment for the prepared internal subtask. Follow its helper participation instructions; do not submit the parent task.",
            "instruction": "Spawn this native role with fork_context=false or fork_turns=none, without model overrides or parent history. If a native spawn response is lost, inspect its existing task by this name; never repeat an uncertain spawn. Wait for native completion and integrate its findings/files. Use worker_helper release afterwards; native close remains a platform action."}}

    def participant(self, *, platform_session, thread_id, parent_thread=None, admit=False):
        """Resolve an existing helper or admit exactly one prepared direct child."""
        with self.runs._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            # Serialize against attach on the same database: either owner attachment
            # or helper admission wins, never both. Historical author records remain.
            if connection.execute(
                "SELECT 1 FROM worker_connections w JOIN runs r USING(run_id) "
                "WHERE w.platform_session=? AND w.thread_id=? AND r.state IN ('queued','running')",
                (platform_session, thread_id)).fetchone() is not None:
                if not admit:
                    raise WorkerNotAttached("Worker owns an active Run and is not an internal helper")
                raise RunStateConflict("Worker thread already owns an active Run; it cannot also be a helper")
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
                self._require_independent(connection, run, platform_session, thread_id)
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
