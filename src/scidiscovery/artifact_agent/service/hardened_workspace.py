"""Server-edited workspace transport for an exact compiled Operation Run.

This backend adds no scientific state. It reuses the trusted-local immutable
workspace implementation while fencing each Run's transport independently.
"""

from __future__ import annotations

import fcntl
import hashlib
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from .local_workspace import LocalTrustedBackend, WorkspaceError


class HardenedWorkerBackend(LocalTrustedBackend):
    """Optional MCP-only transport for workers without native host tools."""

    backend_id = "hardened_worker"
    backend_version = "1"
    edit_protocol = "mcp"
    capabilities = (
        "exact_operation_slot",
        "server_file_transport",
        "restart_same_run",
        "immutable_candidate",
        "failure_isolation",
        "native_tools_disabled",
    )

    def __init__(self, root, *, lease_seconds: int = 30) -> None:
        super().__init__(root)
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 300:
            raise ValueError("hardened lease must be between 1 and 300 seconds")
        self.lease_seconds = lease_seconds
        self.dispatch_database = self.root / "dispatch.sqlite3"
        self.transport_lock_root = self.root / "transport-locks"
        self.transport_lock_root.mkdir(mode=0o700, exist_ok=True)
        with self._connect_dispatch() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS active_transport (
                    run_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    lease_deadline_at TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def supports_operation(compiled: object) -> bool:
        """Hardened v1 authorizes only declared Worker MCP tools."""

        return not HardenedWorkerBackend.unsupported_requirements(compiled)

    @staticmethod
    def unsupported_requirements(compiled: object) -> tuple[str, ...]:
        from ...operations.invoke import direct_revision_ports
        from ...operations.tooling import operation_worker_tool_names, tool_evidence_ports

        native = compiled.spec.executor.native_tools
        required_file_tools = {
            "worker_file_write_begin",
            "worker_file_write_chunk",
            "worker_file_write_commit",
        }
        available = set(operation_worker_tool_names(compiled))
        return tuple(
            name
            for name, unsupported in (
                ("native_shell", native.shell != "none"),
                ("native_view_image", native.view_image),
                ("native_web_search", native.web_search != "disabled"),
                (
                    "agent_collection_outputs",
                    any(port.collection is not None and not (port.name == "recovery_manifest_output"
                        and port.name in tool_evidence_ports(compiled)) for port in compiled.spec.outputs),
                ),
                (
                    "server_file_create",
                    not required_file_tools.issubset(available),
                ),
                (
                    "server_file_read",
                    direct_revision_ports(compiled) is not None,
                ),
                (
                    "server_file_patch",
                    direct_revision_ports(compiled) is not None
                    and not {
                        "worker_file_apply_patch",
                        "worker_file_json_patch",
                    }
                    & available,
                ),
            )
            if unsupported
        )

    @staticmethod
    def assignment_tool_names(compiled: object) -> tuple[str, ...]:
        from ...operations.tooling import operation_worker_tool_names

        return operation_worker_tool_names(compiled)

    def claim_transport(self, run_id: str, owner_id: str) -> None:
        """Bind one owner; takeover waits for any in-flight call of this Run."""

        with self._run_transport_lock(run_id):
            now = datetime.now(timezone.utc)
            deadline = (now + timedelta(seconds=self.lease_seconds)).isoformat()
            with self._connect_dispatch() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT owner_id, lease_deadline_at FROM active_transport WHERE run_id = ?",
                    (run_id,),
                ).fetchone()
                if row is not None:
                    prior_deadline = datetime.fromisoformat(str(row[1]))
                    if str(row[0]) != owner_id and prior_deadline > now:
                        connection.execute("ROLLBACK")
                        raise WorkspaceError("exact Run transport is already active")
                connection.execute(
                    """
                    INSERT INTO active_transport(run_id, owner_id, lease_deadline_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(run_id) DO UPDATE SET
                        owner_id = excluded.owner_id,
                        lease_deadline_at = excluded.lease_deadline_at
                    """,
                    (run_id, owner_id, deadline),
                )
                connection.execute("COMMIT")

    @contextmanager
    def transport_guard(self, run_id: str, owner_id: str, *, renew: bool = False):
        """Fence one call without holding the shared SQLite writer lock."""

        with self._run_transport_lock(run_id):
            now = datetime.now(timezone.utc)
            with self._connect_dispatch() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """
                    SELECT owner_id, lease_deadline_at FROM active_transport
                    WHERE run_id = ?
                    """,
                    (run_id,),
                ).fetchone()
                if (
                    row is None
                    or str(row[0]) != owner_id
                    or datetime.fromisoformat(str(row[1])) <= now
                ):
                    connection.execute("ROLLBACK")
                    raise WorkspaceError("exact Run transport ownership is stale")
                if renew:
                    deadline = (
                        now + timedelta(seconds=self.lease_seconds)
                    ).isoformat()
                    connection.execute(
                        """
                        UPDATE active_transport SET lease_deadline_at = ?
                        WHERE run_id = ? AND owner_id = ?
                        """,
                        (deadline, run_id, owner_id),
                    )
                connection.execute("COMMIT")
            # The OS lock remains held only for this Run while the tool executes.
            yield

    def release_transport(self, run_id: str, owner_id: str) -> None:
        with self._run_transport_lock(run_id):
            with self._connect_dispatch() as connection:
                connection.execute(
                    "DELETE FROM active_transport WHERE run_id = ? AND owner_id = ?",
                    (run_id, owner_id),
                )

    @contextmanager
    def _run_transport_lock(self, run_id: str, *, blocking: bool = True, create: bool = True):
        digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest()
        path = self.transport_lock_root / f"{digest}.lock"
        flags = os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW | (os.O_CREAT if create else 0)
        descriptor = os.open(path, flags, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    @contextmanager
    def quiescence_guard(self, run_id: str):
        """Observe an inactive exact transport without renewing/deleting a lease."""
        with self._run_transport_lock(run_id, blocking=False, create=False):
            if self.dispatch_database.is_symlink():
                raise WorkspaceError("transport identity is a symlink")
            connection = sqlite3.connect(self.dispatch_database.as_uri() + "?mode=ro", uri=True, timeout=0)
            try:
                row = connection.execute(
                    "SELECT lease_deadline_at FROM active_transport WHERE run_id = ?", (run_id,)
                ).fetchone()
            finally:
                connection.close()
            if row is not None:
                deadline = datetime.fromisoformat(str(row[0]))
                if deadline.tzinfo is None or deadline > datetime.now(timezone.utc):
                    raise WorkspaceError("exact Run transport lease is active or unknown")
            yield

    def _connect_dispatch(self) -> sqlite3.Connection:
        return sqlite3.connect(self.dispatch_database, timeout=30.0)


__all__ = ["HardenedWorkerBackend"]
