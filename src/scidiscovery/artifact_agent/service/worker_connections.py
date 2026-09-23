"""Durable platform-thread to Run bindings, owned by the scheduler."""

import json

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


class WorkerNotAttached(RunStateConflict):
    """A platform Worker has not yet been bound to any Run."""


class WorkerConnections:
    def __init__(self, runs):
        self.runs = runs

    def attach(self, *, run_id, platform_session, thread_id):
        with self.runs._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if row is None or row["state"] != "queued":
                existing = connection.execute(
                    "SELECT * FROM worker_connections WHERE run_id=?", (run_id,)).fetchone()
                if (row is not None and row["state"] == "running" and existing is not None
                        and (existing["platform_session"], existing["thread_id"]) == (platform_session, thread_id)):
                    return
                raise RunStateConflict("attach requires the exact queued Run")
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
