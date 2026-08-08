"""Research-instance isolation and semantic revision bindings."""

from __future__ import annotations

import re
import sqlite3
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path


_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}$")
_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")
_NAMESPACES = {"artifact", "task", "approval", "execution"}


class SchedulerBindingError(RuntimeError):
    pass


class SchedulerNameConflict(SchedulerBindingError):
    pass


class SchedulerNameNotFound(SchedulerBindingError):
    pass


class SchedulerInstanceConflict(SchedulerBindingError):
    pass


class SchedulerInstanceNotFound(SchedulerBindingError):
    pass


class SchedulerInstanceClosed(SchedulerBindingError):
    pass


@dataclass(frozen=True)
class SchedulerInstance:
    instance_id: str
    name: str
    title: str
    objective: str
    state: str
    created_at: str
    closed_at: str | None


@dataclass(frozen=True)
class SchedulerInstanceProposal:
    proposal_id: str
    name: str
    title: str
    objective: str
    approval_id: str
    session_key: str
    state: str
    selected_option: str | None
    instance_id: str | None
    created_at: str
    resolved_at: str | None


@dataclass(frozen=True)
class SchedulerSessionBindingRequest:
    request_id: str
    approval_id: str
    session_key: str
    state: str
    selected_option: str | None
    instance_id: str | None
    created_at: str
    resolved_at: str | None


@dataclass(frozen=True)
class SchedulerSessionBindingCandidate:
    option_id: str
    instance: SchedulerInstance
    position: int


@dataclass(frozen=True)
class SchedulerBinding:
    namespace: str
    name: str
    logical_name: str
    revision: int
    object_id: str
    request_fingerprint: str | None
    created_at: str


@dataclass(frozen=True)
class SchedulerStateChange:
    object_type: str
    name: str
    previous_state: str | None
    state: str
    observed_at: str


class SchedulerBindingService:
    """Keep control identities behind instance-scoped semantic revisions."""

    def __init__(self, database_path: Path | str) -> None:
        self.database_path = Path(database_path).expanduser().absolute()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def create_instance(
        self, *, name: str, title: str, objective: str
    ) -> SchedulerInstance:
        self._validate_name(name, label="research instance name")
        _bounded_text(title, label="research instance title", maximum=512)
        _bounded_text(objective, label="research instance objective", maximum=8192)
        created_at = _timestamp()
        instance_id = f"ins_{uuid.uuid4().hex}"
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM scheduler_instances WHERE name = ?", (name,)
            ).fetchone()
            if row is not None:
                existing = _instance(row)
                if existing.title != title or existing.objective != objective:
                    raise SchedulerInstanceConflict(
                        f"research instance already exists with different metadata: {name}"
                    )
                if existing.state != "active":
                    raise SchedulerInstanceClosed(
                        f"research instance is closed: {name}"
                    )
                connection.execute("ROLLBACK")
                return existing
            connection.execute(
                """
                INSERT INTO scheduler_instances (
                    instance_id, name, title, objective, state, created_at, closed_at
                ) VALUES (?, ?, ?, ?, 'active', ?, NULL)
                """,
                (instance_id, name, title, objective, created_at),
            )
            connection.execute("COMMIT")
        return SchedulerInstance(
            instance_id=instance_id,
            name=name,
            title=title,
            objective=objective,
            state="active",
            created_at=created_at,
            closed_at=None,
        )

    def select_instance(self, *, name: str) -> SchedulerInstance:
        self._validate_name(name, label="research instance name")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM scheduler_instances WHERE name = ?", (name,)
            ).fetchone()
        if row is None:
            raise SchedulerInstanceNotFound(f"unknown research instance: {name}")
        value = _instance(row)
        if value.state != "active":
            raise SchedulerInstanceClosed(f"research instance is closed: {name}")
        return value

    def get_instance(self, *, instance_id: str) -> SchedulerInstance:
        if not isinstance(instance_id, str) or not instance_id:
            raise ValueError("research instance identity is invalid")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM scheduler_instances WHERE instance_id = ?",
                (instance_id,),
            ).fetchone()
        if row is None:
            raise SchedulerInstanceNotFound("unknown research instance")
        return _instance(row)

    def list_instances(self, *, state: str | None = None) -> tuple[SchedulerInstance, ...]:
        if state not in {None, "active", "closed"}:
            raise ValueError("research instance state is invalid")
        query = "SELECT * FROM scheduler_instances"
        parameters: tuple[str, ...] = ()
        if state is not None:
            query += " WHERE state = ?"
            parameters = (state,)
        query += " ORDER BY created_at DESC, name"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return tuple(_instance(row) for row in rows)

    def prepare_instance_proposal(
        self,
        *,
        name: str,
        title: str,
        objective: str,
        session_key: str,
    ) -> SchedulerInstanceProposal:
        """Freeze an instance proposal without creating the instance."""

        self._validate_name(name, label="research instance name")
        _bounded_text(title, label="research instance title", maximum=512)
        _bounded_text(objective, label="research instance objective", maximum=8192)
        if not isinstance(session_key, str) or not session_key:
            raise ValueError("scheduler session key is invalid")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            instance = connection.execute(
                "SELECT state FROM scheduler_instances WHERE name = ?", (name,)
            ).fetchone()
            if instance is not None:
                raise SchedulerInstanceConflict(
                    f"research instance already exists; select it explicitly: {name}"
                )
            row = connection.execute(
                """
                SELECT * FROM scheduler_instance_proposals
                WHERE name = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (name,),
            ).fetchone()
            if row is not None and row["state"] == "pending":
                existing = _instance_proposal(row)
                if existing.title != title or existing.objective != objective:
                    raise SchedulerInstanceConflict(
                        f"research instance proposal is pending with different metadata: {name}"
                    )
                connection.execute(
                    """
                    UPDATE scheduler_instance_proposals
                    SET session_key = ?
                    WHERE proposal_id = ?
                    """,
                    (session_key, existing.proposal_id),
                )
                connection.execute("COMMIT")
                return replace(existing, session_key=session_key)
            proposal_id = f"ipr_{uuid.uuid4().hex}"
            approval_id = f"apr_{uuid.uuid4().hex}"
            created_at = _timestamp()
            connection.execute(
                """
                INSERT INTO scheduler_instance_proposals (
                    proposal_id, name, title, objective, approval_id, session_key,
                    state, selected_option, instance_id, created_at, resolved_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending', NULL, NULL, ?, NULL)
                """,
                (
                    proposal_id,
                    name,
                    title,
                    objective,
                    approval_id,
                    session_key,
                    created_at,
                ),
            )
            connection.execute("COMMIT")
        return SchedulerInstanceProposal(
            proposal_id=proposal_id,
            name=name,
            title=title,
            objective=objective,
            approval_id=approval_id,
            session_key=session_key,
            state="pending",
            selected_option=None,
            instance_id=None,
            created_at=created_at,
            resolved_at=None,
        )

    def get_instance_proposal(self, *, name: str) -> SchedulerInstanceProposal:
        self._validate_name(name, label="research instance name")
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM scheduler_instance_proposals
                WHERE name = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (name,),
            ).fetchone()
        if row is None:
            raise SchedulerInstanceNotFound(
                f"unknown research instance proposal: {name}"
            )
        return _instance_proposal(row)

    def find_instance_proposal_by_approval(
        self, *, approval_id: str
    ) -> SchedulerInstanceProposal | None:
        if not isinstance(approval_id, str) or not approval_id:
            raise ValueError("approval identity is invalid")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM scheduler_instance_proposals WHERE approval_id = ?",
                (approval_id,),
            ).fetchone()
        return _instance_proposal(row) if row is not None else None

    def apply_instance_proposal_decision(
        self, *, approval_id: str, selected_option: str
    ) -> SchedulerInstanceProposal | None:
        """Apply one already-validated local UI decision idempotently."""

        proposal = self.find_instance_proposal_by_approval(approval_id=approval_id)
        if proposal is None:
            return None
        if proposal.state != "pending":
            if proposal.selected_option != selected_option:
                raise SchedulerInstanceConflict(
                    "research instance proposal already has a different decision"
                )
            return proposal
        if selected_option == "create_instance":
            instance = self.create_instance(
                name=proposal.name,
                title=proposal.title,
                objective=proposal.objective,
            )
            self.bind_session(
                session_key=proposal.session_key,
                instance_id=instance.instance_id,
            )
            state = "activated"
            instance_id = instance.instance_id
        elif selected_option == "revise_instance":
            state = "revision_requested"
            instance_id = None
        elif selected_option == "cancel_instance":
            state = "cancelled"
            instance_id = None
        else:
            raise SchedulerInstanceConflict(
                "approval option is not valid for an instance proposal"
            )
        resolved_at = _timestamp()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM scheduler_instance_proposals WHERE proposal_id = ?",
                (proposal.proposal_id,),
            ).fetchone()
            if row is None:
                raise SchedulerInstanceNotFound("research instance proposal disappeared")
            if row["state"] != "pending":
                current = _instance_proposal(row)
                if current.selected_option != selected_option:
                    raise SchedulerInstanceConflict(
                        "research instance proposal decision raced with another decision"
                    )
                connection.execute("ROLLBACK")
                return current
            connection.execute(
                """
                UPDATE scheduler_instance_proposals
                SET state = ?, selected_option = ?, instance_id = ?, resolved_at = ?
                WHERE proposal_id = ?
                """,
                (
                    state,
                    selected_option,
                    instance_id,
                    resolved_at,
                    proposal.proposal_id,
                ),
            )
            connection.execute("COMMIT")
        return self.get_instance_proposal(name=proposal.name)

    def close_instance(self, *, instance_id: str) -> SchedulerInstance:
        closed_at = _timestamp()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM scheduler_instances WHERE instance_id = ?",
                (instance_id,),
            ).fetchone()
            if row is None:
                raise SchedulerInstanceNotFound("unknown research instance")
            if row["state"] == "closed":
                connection.execute("ROLLBACK")
                return _instance(row)
            connection.execute(
                """
                UPDATE scheduler_instances
                SET state = 'closed', closed_at = ?
                WHERE instance_id = ?
                """,
                (closed_at, instance_id),
            )
            connection.execute("COMMIT")
        return self.get_instance(instance_id=instance_id)

    def require_active_instance(self, *, instance_id: str) -> SchedulerInstance:
        value = self.get_instance(instance_id=instance_id)
        if value.state != "active":
            raise SchedulerInstanceClosed(
                f"research instance is closed: {value.name}"
            )
        return value

    def bind_session(self, *, session_key: str, instance_id: str) -> None:
        if not isinstance(session_key, str) or not session_key:
            raise ValueError("scheduler session binding is invalid")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._bind_session_in_connection(
                connection, session_key=session_key, instance_id=instance_id
            )
            connection.execute("COMMIT")

    def session_instance(self, *, session_key: str) -> str | None:
        if not isinstance(session_key, str) or not session_key:
            raise ValueError("scheduler session binding is invalid")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT instance_id FROM scheduler_sessions WHERE session_key = ?",
                (session_key,),
            ).fetchone()
        return str(row["instance_id"]) if row is not None else None

    def clear_session(self, *, session_key: str) -> None:
        if not isinstance(session_key, str) or not session_key:
            raise ValueError("scheduler session binding is invalid")
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM scheduler_sessions WHERE session_key = ?",
                (session_key,),
            )

    def prepare_session_binding_request(
        self, *, session_key: str, preferred_name: str | None = None
    ) -> tuple[
        SchedulerSessionBindingRequest,
        tuple[SchedulerSessionBindingCandidate, ...],
    ]:
        """Freeze one local-review request for an unbound scheduler session."""

        if not isinstance(session_key, str) or not session_key:
            raise ValueError("scheduler session binding is invalid")
        if preferred_name is not None:
            self._validate_name(preferred_name, label="research instance name")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM scheduler_session_binding_requests
                WHERE session_key = ? AND state = 'pending'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (session_key,),
            ).fetchone()
            if row is not None:
                request = _session_binding_request(row)
                candidates = self._session_binding_candidates(
                    connection, request_id=request.request_id
                )
                if preferred_name is not None and all(
                    item.instance.name != preferred_name for item in candidates
                ):
                    raise SchedulerInstanceConflict(
                        "a different session-binding review is already pending"
                    )
                connection.execute("COMMIT")
                return request, candidates

            query = "SELECT * FROM scheduler_instances WHERE state = 'active'"
            parameters: tuple[str, ...] = ()
            if preferred_name is not None:
                query += " AND name = ?"
                parameters = (preferred_name,)
            query += " ORDER BY created_at DESC, name"
            rows = connection.execute(query, parameters).fetchall()
            if not rows:
                connection.execute("ROLLBACK")
                if preferred_name is not None:
                    raise SchedulerInstanceNotFound(
                        f"unknown active research instance: {preferred_name}"
                    )
                raise SchedulerInstanceNotFound(
                    "no active research instance exists; prepare a new instance first"
                )
            if len(rows) > 31:
                connection.execute("ROLLBACK")
                raise SchedulerInstanceConflict(
                    "too many active research instances for one bounded review"
                )

            request_id = f"sbr_{uuid.uuid4().hex}"
            approval_id = f"apr_{uuid.uuid4().hex}"
            created_at = _timestamp()
            connection.execute(
                """
                INSERT INTO scheduler_session_binding_requests (
                    request_id, approval_id, session_key, state, selected_option,
                    instance_id, created_at, resolved_at
                ) VALUES (?, ?, ?, 'pending', NULL, NULL, ?, NULL)
                """,
                (request_id, approval_id, session_key, created_at),
            )
            for position, candidate_row in enumerate(rows, start=1):
                connection.execute(
                    """
                    INSERT INTO scheduler_session_binding_candidates (
                        request_id, option_id, instance_id, position
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        request_id,
                        f"bind_instance_{position:02d}",
                        str(candidate_row["instance_id"]),
                        position,
                    ),
                )
            request_row = connection.execute(
                "SELECT * FROM scheduler_session_binding_requests WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            candidates = self._session_binding_candidates(
                connection, request_id=request_id
            )
            connection.execute("COMMIT")
        if request_row is None:
            raise SchedulerInstanceNotFound("session-binding request disappeared")
        return _session_binding_request(request_row), candidates

    def find_session_binding_request_by_approval(
        self, *, approval_id: str
    ) -> SchedulerSessionBindingRequest | None:
        if not isinstance(approval_id, str) or not approval_id:
            raise ValueError("approval identity is invalid")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM scheduler_session_binding_requests WHERE approval_id = ?",
                (approval_id,),
            ).fetchone()
        return _session_binding_request(row) if row is not None else None

    def session_binding_candidates(
        self, *, request_id: str
    ) -> tuple[SchedulerSessionBindingCandidate, ...]:
        if not isinstance(request_id, str) or not request_id:
            raise ValueError("session-binding request identity is invalid")
        with self._connect() as connection:
            return self._session_binding_candidates(
                connection, request_id=request_id
            )

    def apply_session_binding_decision(
        self, *, approval_id: str, selected_option: str
    ) -> SchedulerSessionBindingRequest | None:
        """Apply a UI-validated binding decision and revoke the old owner."""

        request = self.find_session_binding_request_by_approval(
            approval_id=approval_id
        )
        if request is None:
            return None
        if request.state != "pending":
            if request.selected_option != selected_option:
                raise SchedulerInstanceConflict(
                    "session-binding request already has a different decision"
                )
            return request
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM scheduler_session_binding_requests WHERE request_id = ?",
                (request.request_id,),
            ).fetchone()
            if row is None:
                raise SchedulerInstanceNotFound("session-binding request disappeared")
            current = _session_binding_request(row)
            if current.state != "pending":
                if current.selected_option != selected_option:
                    raise SchedulerInstanceConflict(
                        "session-binding decision raced with another decision"
                    )
                connection.execute("ROLLBACK")
                return current
            if selected_option == "cancel_binding":
                state = "cancelled"
                instance_id = None
            else:
                candidate = connection.execute(
                    """
                    SELECT instance_id FROM scheduler_session_binding_candidates
                    WHERE request_id = ? AND option_id = ?
                    """,
                    (request.request_id, selected_option),
                ).fetchone()
                if candidate is None:
                    raise SchedulerInstanceConflict(
                        "approval option is not valid for this session-binding request"
                    )
                instance_id = str(candidate["instance_id"])
                self._bind_session_in_connection(
                    connection,
                    session_key=request.session_key,
                    instance_id=instance_id,
                )
                state = "activated"
            resolved_at = _timestamp()
            connection.execute(
                """
                UPDATE scheduler_session_binding_requests
                SET state = ?, selected_option = ?, instance_id = ?, resolved_at = ?
                WHERE request_id = ?
                """,
                (
                    state,
                    selected_option,
                    instance_id,
                    resolved_at,
                    request.request_id,
                ),
            )
            updated = connection.execute(
                "SELECT * FROM scheduler_session_binding_requests WHERE request_id = ?",
                (request.request_id,),
            ).fetchone()
            connection.execute("COMMIT")
        if updated is None:
            raise SchedulerInstanceNotFound("session-binding request disappeared")
        return _session_binding_request(updated)

    def _session_binding_candidates(
        self, connection: sqlite3.Connection, *, request_id: str
    ) -> tuple[SchedulerSessionBindingCandidate, ...]:
        rows = connection.execute(
            """
            SELECT c.option_id, c.position, i.*
            FROM scheduler_session_binding_candidates AS c
            JOIN scheduler_instances AS i ON i.instance_id = c.instance_id
            WHERE c.request_id = ?
            ORDER BY c.position
            """,
            (request_id,),
        ).fetchall()
        return tuple(
            SchedulerSessionBindingCandidate(
                option_id=str(row["option_id"]),
                instance=_instance(row),
                position=int(row["position"]),
            )
            for row in rows
        )

    @staticmethod
    def _bind_session_in_connection(
        connection: sqlite3.Connection, *, session_key: str, instance_id: str
    ) -> None:
        row = connection.execute(
            "SELECT state FROM scheduler_instances WHERE instance_id = ?",
            (instance_id,),
        ).fetchone()
        if row is None:
            raise SchedulerInstanceNotFound("unknown research instance")
        if row["state"] != "active":
            raise SchedulerInstanceClosed("research instance is closed")
        connection.execute(
            "DELETE FROM scheduler_sessions WHERE instance_id = ? AND session_key <> ?",
            (instance_id, session_key),
        )
        connection.execute(
            """
            INSERT INTO scheduler_sessions (session_key, instance_id, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(session_key) DO UPDATE SET
                instance_id = excluded.instance_id,
                updated_at = excluded.updated_at
            """,
            (session_key, instance_id, _timestamp()),
        )

    def bind(
        self,
        *,
        instance: str,
        namespace: str,
        name: str,
        object_id: str,
        logical_name: str | None = None,
        revision: int = 1,
        request_fingerprint: str | None = None,
    ) -> SchedulerBinding:
        logical = logical_name or name
        self._validate_binding(
            instance,
            namespace,
            name,
            logical,
            revision,
            object_id,
            request_fingerprint,
        )
        created_at = _timestamp()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM scheduler_bindings
                WHERE instance = ? AND namespace = ? AND name = ?
                """,
                (instance, namespace, name),
            ).fetchone()
            if row is not None:
                existing = _binding(row)
                if (
                    existing.object_id != object_id
                    or existing.logical_name != logical
                    or existing.revision != revision
                    or existing.request_fingerprint != request_fingerprint
                ):
                    raise SchedulerNameConflict(
                        f"{namespace} name is already bound: {name}"
                    )
                connection.execute("ROLLBACK")
                return existing
            connection.execute(
                """
                INSERT INTO scheduler_bindings (
                    instance, namespace, name, logical_name, revision,
                    object_id, request_fingerprint, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    instance,
                    namespace,
                    name,
                    logical,
                    revision,
                    object_id,
                    request_fingerprint,
                    created_at,
                ),
            )
            connection.execute("COMMIT")
        return SchedulerBinding(
            namespace=namespace,
            name=name,
            logical_name=logical,
            revision=revision,
            object_id=object_id,
            request_fingerprint=request_fingerprint,
            created_at=created_at,
        )

    def get_binding(
        self, *, instance: str, namespace: str, name: str
    ) -> SchedulerBinding:
        self._validate_lookup(instance, namespace, name)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM scheduler_bindings
                WHERE instance = ? AND namespace = ? AND name = ?
                """,
                (instance, namespace, name),
            ).fetchone()
        if row is None:
            raise SchedulerNameNotFound(f"unknown {namespace} name: {name}")
        return _binding(row)

    def resolve(self, *, instance: str, namespace: str, name: str) -> str:
        return self.get_binding(
            instance=instance, namespace=namespace, name=name
        ).object_id

    def find_revision(
        self,
        *,
        instance: str,
        namespace: str,
        logical_name: str,
        request_fingerprint: str,
    ) -> SchedulerBinding | None:
        self._validate_binding(
            instance,
            namespace,
            logical_name,
            logical_name,
            1,
            "placeholder",
            request_fingerprint,
        )
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM scheduler_bindings
                WHERE instance = ? AND namespace = ? AND logical_name = ?
                  AND request_fingerprint = ?
                ORDER BY revision
                LIMIT 1
                """,
                (instance, namespace, logical_name, request_fingerprint),
            ).fetchone()
        return _binding(row) if row is not None else None

    def next_revision(
        self, *, instance: str, namespace: str, logical_name: str
    ) -> tuple[str, int]:
        self._validate_lookup(instance, namespace, logical_name)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COALESCE(MAX(revision), 0) AS maximum
                FROM scheduler_bindings
                WHERE instance = ? AND namespace = ? AND logical_name = ?
                """,
                (instance, namespace, logical_name),
            ).fetchone()
        revision = int(row["maximum"]) + 1
        name = f"{logical_name}.rev{revision}"
        self._validate_name(name, label="derived revision name")
        return name, revision

    def find_name(
        self, *, instance: str, namespace: str, object_id: str
    ) -> str | None:
        self._validate_binding(
            instance,
            namespace,
            "placeholder",
            "placeholder",
            1,
            object_id,
            None,
        )
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT name FROM scheduler_bindings
                WHERE instance = ? AND namespace = ? AND object_id = ?
                ORDER BY created_at, name
                LIMIT 1
                """,
                (instance, namespace, object_id),
            ).fetchone()
        return str(row["name"]) if row is not None else None

    def find_owner(
        self, *, namespace: str, object_id: str
    ) -> tuple[SchedulerInstance, SchedulerBinding] | None:
        """Locate the unique ResearchInstance binding for one control object."""

        if namespace not in _NAMESPACES:
            raise ValueError("scheduler namespace is invalid")
        if not isinstance(object_id, str) or not object_id:
            raise ValueError("control object identity is invalid")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT instance, name
                FROM scheduler_bindings
                WHERE namespace = ? AND object_id = ?
                ORDER BY created_at, name
                LIMIT 2
                """,
                (namespace, object_id),
            ).fetchall()
        if not rows:
            return None
        if len(rows) != 1:
            raise SchedulerBindingError(
                f"{namespace} control object has ambiguous instance ownership"
            )
        instance_id = str(rows[0]["instance"])
        name = str(rows[0]["name"])
        return (
            self.get_instance(instance_id=instance_id),
            self.get_binding(instance=instance_id, namespace=namespace, name=name),
        )

    def list(self, *, instance: str, namespace: str) -> tuple[SchedulerBinding, ...]:
        self._validate_lookup(instance, namespace, "placeholder")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM scheduler_bindings
                WHERE instance = ? AND namespace = ?
                ORDER BY created_at DESC, name
                """,
                (instance, namespace),
            ).fetchall()
        return tuple(_binding(row) for row in rows)

    def observe_state_changes(
        self,
        *,
        instance: str,
        observer_key: str,
        states: tuple[tuple[str, str, str], ...],
    ) -> tuple[SchedulerStateChange, ...]:
        """Persist a service-side cursor and return only changed semantic states."""

        if not isinstance(observer_key, str) or not observer_key:
            raise ValueError("scheduler observer key is invalid")
        allowed = {"task", "approval", "execution"}
        normalized: list[tuple[str, str, str]] = []
        for object_type, name, state in states:
            if object_type not in allowed:
                raise ValueError("observed scheduler object type is invalid")
            self._validate_name(name, label="observed scheduler semantic name")
            if not isinstance(state, str) or not state or len(state) > 128:
                raise ValueError("observed scheduler state is invalid")
            normalized.append((object_type, name, state))
        keys = tuple((item[0], item[1]) for item in normalized)
        if len(keys) != len(set(keys)):
            raise ValueError("observed scheduler states must be unique")

        observed_at = _timestamp()
        changes: list[SchedulerStateChange] = []
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for object_type, name, state in sorted(normalized):
                row = connection.execute(
                    """
                    SELECT state FROM scheduler_observations
                    WHERE instance = ? AND observer_key = ?
                      AND object_type = ? AND name = ?
                    """,
                    (instance, observer_key, object_type, name),
                ).fetchone()
                previous = str(row["state"]) if row is not None else None
                if previous == state:
                    continue
                connection.execute(
                    """
                    INSERT INTO scheduler_observations (
                        instance, observer_key, object_type, name, state, observed_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(instance, observer_key, object_type, name)
                    DO UPDATE SET state = excluded.state,
                                  observed_at = excluded.observed_at
                    """,
                    (instance, observer_key, object_type, name, state, observed_at),
                )
                changes.append(
                    SchedulerStateChange(
                        object_type=object_type,
                        name=name,
                        previous_state=previous,
                        state=state,
                        observed_at=observed_at,
                    )
                )
            connection.execute("COMMIT")
        return tuple(changes)

    @staticmethod
    def _validate_name(value: str, *, label: str) -> None:
        if not isinstance(value, str) or not _NAME.fullmatch(value):
            raise ValueError(f"{label} is invalid")

    @classmethod
    def _validate_lookup(cls, instance: str, namespace: str, name: str) -> None:
        if not isinstance(instance, str) or not instance:
            raise ValueError("research instance identity is invalid")
        if namespace not in _NAMESPACES:
            raise ValueError("scheduler namespace is invalid")
        cls._validate_name(name, label="scheduler semantic name")

    @classmethod
    def _validate_binding(
        cls,
        instance: str,
        namespace: str,
        name: str,
        logical_name: str,
        revision: int,
        object_id: str,
        request_fingerprint: str | None,
    ) -> None:
        cls._validate_lookup(instance, namespace, name)
        cls._validate_name(logical_name, label="scheduler logical name")
        if type(revision) is not int or revision < 1:
            raise ValueError("scheduler revision is invalid")
        if not isinstance(object_id, str) or not object_id:
            raise ValueError("control object identity is invalid")
        if request_fingerprint is not None and not _FINGERPRINT.fullmatch(
            request_fingerprint
        ):
            raise ValueError("request fingerprint is invalid")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduler_instances (
                    instance_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ('active', 'closed')),
                    created_at TEXT NOT NULL,
                    closed_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduler_bindings (
                    instance TEXT NOT NULL,
                    namespace TEXT NOT NULL,
                    name TEXT NOT NULL,
                    logical_name TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    object_id TEXT NOT NULL,
                    request_fingerprint TEXT,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (instance, namespace, name)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduler_observations (
                    instance TEXT NOT NULL,
                    observer_key TEXT NOT NULL,
                    object_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    state TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    PRIMARY KEY (instance, observer_key, object_type, name)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduler_sessions (
                    session_key TEXT PRIMARY KEY,
                    instance_id TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(instance_id) REFERENCES scheduler_instances(instance_id)
                )
                """
            )
            connection.execute(
                """
                DELETE FROM scheduler_sessions
                WHERE rowid NOT IN (
                    SELECT newest.rowid
                    FROM scheduler_sessions AS newest
                    WHERE newest.instance_id = scheduler_sessions.instance_id
                    ORDER BY newest.updated_at DESC, newest.rowid DESC
                    LIMIT 1
                )
                """
            )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS scheduler_sessions_one_owner
                ON scheduler_sessions(instance_id)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduler_instance_proposals (
                    proposal_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    approval_id TEXT NOT NULL UNIQUE,
                    session_key TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (
                        state IN (
                            'pending', 'activated', 'revision_requested', 'cancelled'
                        )
                    ),
                    selected_option TEXT,
                    instance_id TEXT,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT,
                    FOREIGN KEY(instance_id) REFERENCES scheduler_instances(instance_id)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS scheduler_instance_proposals_by_name
                ON scheduler_instance_proposals(name, created_at DESC)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduler_session_binding_requests (
                    request_id TEXT PRIMARY KEY,
                    approval_id TEXT NOT NULL UNIQUE,
                    session_key TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (
                        state IN ('pending', 'activated', 'cancelled')
                    ),
                    selected_option TEXT,
                    instance_id TEXT,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT,
                    FOREIGN KEY(instance_id) REFERENCES scheduler_instances(instance_id)
                )
                """
            )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS scheduler_session_binding_pending
                ON scheduler_session_binding_requests(session_key)
                WHERE state = 'pending'
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduler_session_binding_candidates (
                    request_id TEXT NOT NULL,
                    option_id TEXT NOT NULL,
                    instance_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    PRIMARY KEY(request_id, option_id),
                    UNIQUE(request_id, instance_id),
                    UNIQUE(request_id, position),
                    FOREIGN KEY(request_id)
                        REFERENCES scheduler_session_binding_requests(request_id),
                    FOREIGN KEY(instance_id) REFERENCES scheduler_instances(instance_id)
                )
                """
            )
            columns = {
                str(row["name"])
                for row in connection.execute(
                    "PRAGMA table_info(scheduler_bindings)"
                ).fetchall()
            }
            if "logical_name" not in columns:
                connection.execute(
                    "ALTER TABLE scheduler_bindings ADD COLUMN logical_name TEXT"
                )
            if "revision" not in columns:
                connection.execute(
                    "ALTER TABLE scheduler_bindings ADD COLUMN revision INTEGER"
                )
            if "request_fingerprint" not in columns:
                connection.execute(
                    "ALTER TABLE scheduler_bindings ADD COLUMN request_fingerprint TEXT"
                )
            connection.execute(
                "UPDATE scheduler_bindings SET logical_name = name WHERE logical_name IS NULL"
            )
            connection.execute(
                "UPDATE scheduler_bindings SET revision = 1 WHERE revision IS NULL"
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS scheduler_bindings_reverse
                ON scheduler_bindings(instance, namespace, object_id)
                """
            )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS scheduler_binding_revisions
                ON scheduler_bindings(instance, namespace, logical_name, revision)
                """
            )
            legacy_instances = connection.execute(
                """
                SELECT b.instance, MIN(b.created_at) AS created_at
                FROM scheduler_bindings AS b
                LEFT JOIN scheduler_instances AS i
                  ON i.instance_id = b.instance
                WHERE i.instance_id IS NULL
                GROUP BY b.instance
                """
            ).fetchall()
            for row in legacy_instances:
                legacy_id = str(row["instance"])
                legacy_name = f"legacy.{legacy_id}"
                if not _NAME.fullmatch(legacy_name):
                    legacy_name = f"legacy.{uuid.uuid5(uuid.NAMESPACE_URL, legacy_id).hex}"
                connection.execute(
                    """
                    INSERT OR IGNORE INTO scheduler_instances (
                        instance_id, name, title, objective, state, created_at, closed_at
                    ) VALUES (?, ?, ?, ?, 'closed', ?, ?)
                    """,
                    (
                        legacy_id,
                        legacy_name,
                        f"Migrated legacy namespace {legacy_id}",
                        "Preserved read-only during the ResearchInstance migration.",
                        str(row["created_at"]),
                        _timestamp(),
                    ),
                )


def _instance(row: sqlite3.Row) -> SchedulerInstance:
    return SchedulerInstance(
        instance_id=str(row["instance_id"]),
        name=str(row["name"]),
        title=str(row["title"]),
        objective=str(row["objective"]),
        state=str(row["state"]),
        created_at=str(row["created_at"]),
        closed_at=str(row["closed_at"]) if row["closed_at"] is not None else None,
    )


def _binding(row: sqlite3.Row) -> SchedulerBinding:
    return SchedulerBinding(
        namespace=str(row["namespace"]),
        name=str(row["name"]),
        logical_name=str(row["logical_name"]),
        revision=int(row["revision"]),
        object_id=str(row["object_id"]),
        request_fingerprint=(
            str(row["request_fingerprint"])
            if row["request_fingerprint"] is not None
            else None
        ),
        created_at=str(row["created_at"]),
    )


def _instance_proposal(row: sqlite3.Row) -> SchedulerInstanceProposal:
    return SchedulerInstanceProposal(
        proposal_id=str(row["proposal_id"]),
        name=str(row["name"]),
        title=str(row["title"]),
        objective=str(row["objective"]),
        approval_id=str(row["approval_id"]),
        session_key=str(row["session_key"]),
        state=str(row["state"]),
        selected_option=(
            str(row["selected_option"])
            if row["selected_option"] is not None
            else None
        ),
        instance_id=(
            str(row["instance_id"]) if row["instance_id"] is not None else None
        ),
        created_at=str(row["created_at"]),
        resolved_at=(
            str(row["resolved_at"]) if row["resolved_at"] is not None else None
        ),
    )


def _session_binding_request(row: sqlite3.Row) -> SchedulerSessionBindingRequest:
    return SchedulerSessionBindingRequest(
        request_id=str(row["request_id"]),
        approval_id=str(row["approval_id"]),
        session_key=str(row["session_key"]),
        state=str(row["state"]),
        selected_option=(
            str(row["selected_option"])
            if row["selected_option"] is not None
            else None
        ),
        instance_id=(
            str(row["instance_id"]) if row["instance_id"] is not None else None
        ),
        created_at=str(row["created_at"]),
        resolved_at=(
            str(row["resolved_at"]) if row["resolved_at"] is not None else None
        ),
    )


def _bounded_text(value: str, *, label: str, maximum: int) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{label} is invalid")


def _timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


__all__ = [
    "SchedulerBinding",
    "SchedulerBindingError",
    "SchedulerBindingService",
    "SchedulerInstance",
    "SchedulerInstanceClosed",
    "SchedulerInstanceConflict",
    "SchedulerInstanceNotFound",
    "SchedulerInstanceProposal",
    "SchedulerNameConflict",
    "SchedulerNameNotFound",
]
