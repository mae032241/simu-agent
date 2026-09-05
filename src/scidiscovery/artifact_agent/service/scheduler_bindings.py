"""Research-instance isolation and semantic revision bindings."""

from __future__ import annotations

import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..schema.refs import ArtifactRef


_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}$")
_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")
_NAMESPACES = {"artifact", "run", "approval", "execution"}
_EXPECTED_REF_UNSET = object()


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


@dataclass(frozen=True)
class SchedulerScientificSelection:
    kind: str
    logical_name: str
    artifact_ref: ArtifactRef | None
    selected_at: str


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
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            value = self._create_instance_in_connection(
                connection, name=name, title=title, objective=objective
            )
            connection.execute("COMMIT")
        return value

    def create_instance_and_bind_session(
        self,
        *,
        session_key: str,
        name: str,
        title: str,
        objective: str,
    ) -> SchedulerInstance:
        """Atomically create one active instance and bind the exact UI session."""

        self._validate_session_key(session_key)
        self._validate_name(name, label="research instance name")
        _bounded_text(title, label="research instance title", maximum=512)
        _bounded_text(objective, label="research instance objective", maximum=8192)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            value = self._create_instance_in_connection(
                connection, name=name, title=title, objective=objective
            )
            self._bind_session_in_connection(
                connection,
                session_key=session_key,
                instance_id=value.instance_id,
            )
            connection.execute("COMMIT")
        return value

    def bind_session_by_name(
        self, *, session_key: str, name: str
    ) -> SchedulerInstance:
        """Atomically bind the exact UI session to one named active instance."""

        self._validate_session_key(session_key)
        self._validate_name(name, label="research instance name")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM scheduler_instances WHERE name = ?", (name,)
            ).fetchone()
            if row is None:
                raise SchedulerInstanceNotFound(
                    f"unknown research instance: {name}"
                )
            value = _instance(row)
            if value.state != "active":
                raise SchedulerInstanceClosed(
                    f"research instance is closed: {name}"
                )
            self._bind_session_in_connection(
                connection,
                session_key=session_key,
                instance_id=value.instance_id,
            )
            connection.execute("COMMIT")
        return value

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
        if state in {"active", "closed"}:
            query += " WHERE state = ?"
            parameters = (state,)
        query += " ORDER BY created_at DESC, name"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        values = tuple(
            self.get_instance(instance_id=str(row["instance_id"])) for row in rows
        )
        return tuple(value for value in values if state is None or value.state == state)

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
            connection.execute(
                "DELETE FROM scheduler_sessions WHERE instance_id = ?",
                (instance_id,),
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
        self._validate_session_key(session_key)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._bind_session_in_connection(
                connection, session_key=session_key, instance_id=instance_id
            )
            connection.execute("COMMIT")

    def session_instance(self, *, session_key: str) -> str | None:
        self._validate_session_key(session_key)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT session.instance_id
                FROM scheduler_sessions AS session
                JOIN scheduler_instances AS instance
                  ON instance.instance_id = session.instance_id
                WHERE session.session_key = ? AND instance.state = 'active'
                """,
                (session_key,),
            ).fetchone()
        return str(row["instance_id"]) if row is not None else None

    @staticmethod
    def _create_instance_in_connection(
        connection: sqlite3.Connection,
        *,
        name: str,
        title: str,
        objective: str,
    ) -> SchedulerInstance:
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
            return existing
        created_at = _timestamp()
        instance_id = f"ins_{uuid.uuid4().hex}"
        connection.execute(
            """
            INSERT INTO scheduler_instances (
                instance_id, name, title, objective, state, created_at, closed_at
            ) VALUES (?, ?, ?, ?, 'active', ?, NULL)
            """,
            (instance_id, name, title, objective, created_at),
        )
        return SchedulerInstance(
            instance_id=instance_id,
            name=name,
            title=title,
            objective=objective,
            state="active",
            created_at=created_at,
            closed_at=None,
        )

    @staticmethod
    def _bind_session_in_connection(
        connection: sqlite3.Connection, *, session_key: str, instance_id: str
    ) -> None:
        row = connection.execute(
            """
            SELECT instance.state
            FROM scheduler_instances AS instance
            WHERE instance.instance_id = ?
            """,
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

    @staticmethod
    def _validate_session_key(session_key: str) -> None:
        if not isinstance(session_key, str) or not 1 <= len(session_key) <= 256:
            raise ValueError("scheduler session binding is invalid")

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
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            value = self.bind_in_connection(
                connection,
                instance=instance,
                namespace=namespace,
                name=name,
                object_id=object_id,
                logical_name=logical_name,
                revision=revision,
                request_fingerprint=request_fingerprint,
            )
            connection.execute("COMMIT")
        return value

    def bind_in_connection(
        self,
        connection: sqlite3.Connection,
        *,
        instance: str,
        namespace: str,
        name: str,
        object_id: str,
        logical_name: str | None = None,
        revision: int = 1,
        request_fingerprint: str | None = None,
        attached: bool = False,
    ) -> SchedulerBinding:
        """Bind through an existing control transaction.

        `attached=True` is reserved for Run completion, where the scheduler
        database is attached as ``scheduler_control``.  This keeps binding
        validation and idempotency in one authority without opening a nested
        transaction.
        """

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
        prefix = "scheduler_control." if attached else ""
        row = connection.execute(
            f"""
            SELECT * FROM {prefix}scheduler_bindings
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
            return existing
        created_at = _timestamp()
        connection.execute(
            f"""
            INSERT INTO {prefix}scheduler_bindings (
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

    def select_scientific_object(
        self,
        *,
        instance: str,
        kind: str,
        logical_name: str,
        artifact_ref: ArtifactRef | None = None,
        expected_ref: ArtifactRef | None | object = _EXPECTED_REF_UNSET,
    ) -> SchedulerScientificSelection:
        """Select one semantic lineage as current for a scientific object kind."""

        if not isinstance(instance, str) or not instance:
            raise ValueError("research instance identity is invalid")
        self._validate_name(kind, label="scientific object kind")
        self._validate_name(logical_name, label="scheduler logical name")
        selected_at = _timestamp()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                """
                SELECT artifact_ref_json FROM scheduler_scientific_selections
                WHERE instance = ? AND kind = ?
                """,
                (instance, kind),
            ).fetchone()
            current_ref = (
                None
                if current is None or current["artifact_ref_json"] is None
                else ArtifactRef.model_validate_json(
                    current["artifact_ref_json"], strict=True
                )
            )
            if expected_ref is not _EXPECTED_REF_UNSET and current_ref != expected_ref:
                connection.execute("ROLLBACK")
                raise SchedulerNameConflict("scientific current compare-and-set failed")
            connection.execute(
                """
                INSERT INTO scheduler_scientific_selections (
                    instance, kind, logical_name, artifact_ref_json, selected_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(instance, kind) DO UPDATE SET
                    logical_name = excluded.logical_name,
                    artifact_ref_json = excluded.artifact_ref_json,
                    selected_at = excluded.selected_at
                """,
                (
                    instance,
                    kind,
                    logical_name,
                    None if artifact_ref is None else artifact_ref.canonical_json(),
                    selected_at,
                ),
            )
            connection.execute("COMMIT")
        return SchedulerScientificSelection(
            kind=kind,
            logical_name=logical_name,
            artifact_ref=artifact_ref,
            selected_at=selected_at,
        )

    def scientific_selections(
        self, *, instance: str
    ) -> tuple[SchedulerScientificSelection, ...]:
        if not isinstance(instance, str) or not instance:
            raise ValueError("research instance identity is invalid")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT kind, logical_name, artifact_ref_json, selected_at
                FROM scheduler_scientific_selections
                WHERE instance = ?
                ORDER BY kind
                """,
                (instance,),
            ).fetchall()
        return tuple(
            SchedulerScientificSelection(
                kind=str(row["kind"]),
                logical_name=str(row["logical_name"]),
                artifact_ref=(
                    None
                    if row["artifact_ref_json"] is None
                    else ArtifactRef.model_validate_json(
                        row["artifact_ref_json"], strict=True
                    )
                ),
                selected_at=str(row["selected_at"]),
            )
            for row in rows
        )

    def instance_bindings(self, *, instance: str) -> tuple[SchedulerBinding, ...]:
        """Return every semantic control-object binding owned by one instance."""

        self.get_instance(instance_id=instance)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM scheduler_bindings
                WHERE instance = ?
                ORDER BY namespace, created_at DESC, name
                """,
                (instance,),
            ).fetchall()
        return tuple(_binding(row) for row in rows)

    def object_owner_count(self, *, namespace: str, object_id: str) -> int:
        if namespace not in _NAMESPACES:
            raise ValueError("scheduler namespace is invalid")
        if not isinstance(object_id, str) or not object_id:
            raise ValueError("control object identity is invalid")
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(DISTINCT instance) AS owners
                FROM scheduler_bindings
                WHERE namespace = ? AND object_id = ?
                """,
                (namespace, object_id),
            ).fetchone()
        return int(row["owners"])

    def instance_history_approval_ids(self, *, instance: str) -> tuple[str, ...]:
        """Return approvals owned by one instance's visible audit history."""

        self.get_instance(instance_id=instance)
        with self._connect() as connection:
            bound = connection.execute(
                """
                SELECT object_id AS approval_id FROM scheduler_bindings
                WHERE instance = ? AND namespace = 'approval'
                """,
                (instance,),
            ).fetchall()
        values = [str(row["approval_id"]) for row in bound]
        return tuple(dict.fromkeys(values))

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
        allowed = {"run", "approval", "execution"}
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
            # Run completion attaches this database to runs.sqlite3 so that the
            # output binding and terminal receipt commit as one SQLite unit.
            # SQLite only guarantees crash-atomic multi-file transactions when
            # no participating database uses WAL.
            mode = connection.execute("PRAGMA journal_mode = DELETE").fetchone()
            if mode is None or str(mode[0]).lower() != "delete":
                raise SchedulerBindingError(
                    "scheduler database cannot provide atomic attached commits"
                )
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
                CREATE TABLE IF NOT EXISTS scheduler_scientific_selections (
                    instance TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    logical_name TEXT NOT NULL,
                    artifact_ref_json BLOB,
                    selected_at TEXT NOT NULL,
                    PRIMARY KEY (instance, kind)
                )
                """
            )
            selection_columns = {
                str(row["name"])
                for row in connection.execute(
                    "PRAGMA table_info(scheduler_scientific_selections)"
                ).fetchall()
            }
            if "artifact_ref_json" not in selection_columns:
                connection.execute(
                    "ALTER TABLE scheduler_scientific_selections ADD COLUMN artifact_ref_json BLOB"
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
    "SchedulerNameConflict",
    "SchedulerNameNotFound",
]
