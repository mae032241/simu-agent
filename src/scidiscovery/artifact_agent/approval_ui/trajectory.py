"""Rebuildable UI observations, never a source of scientific or scheduling state."""
from __future__ import annotations

from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import sqlite3
import threading
import uuid

LOGGER = logging.getLogger(__name__)
SCHEMA_VERSION = 1
MAX_EVENTS = 1000
_TERMINAL = {"completed", "failed", "collected", "decided", "expired", "registered", "cancelled_by_human"}


class TrajectoryStore:
    """Small derived index; cache loss does not modify any control database."""
    def __init__(self, path: Path, *, read_only=False):
        self.path = Path(path)
        self.read_only = read_only

    @contextmanager
    def connect(self):
        if self.path.is_symlink() or self.path.parent.is_symlink():
            raise ValueError("UI cache must not be a symlink")
        if self.read_only:
            connection = sqlite3.connect(self.path.absolute().as_uri() + "?mode=ro", uri=True, timeout=2)
            connection.row_factory = sqlite3.Row
            try:
                yield connection
            finally:
                connection.close()
            return
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=2)
        connection.row_factory = sqlite3.Row
        try:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS nodes(instance_id TEXT NOT NULL, node_key TEXT NOT NULL,
                    revision TEXT NOT NULL, payload TEXT NOT NULL, state TEXT NOT NULL,
                    first_observed_at TEXT NOT NULL, last_observed_at TEXT NOT NULL,
                    PRIMARY KEY(instance_id,node_key));
                CREATE TABLE IF NOT EXISTS events(sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    instance_id TEXT NOT NULL,node_key TEXT NOT NULL,revision TEXT NOT NULL,
                    source_time TEXT, observed_at TEXT NOT NULL, state TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS events_instance ON events(instance_id,sequence);
                CREATE TABLE IF NOT EXISTS preferences(instance_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            """)
            version = connection.execute("SELECT value FROM metadata WHERE key='version'").fetchone()
            if version and version[0] != str(SCHEMA_VERSION):
                raise ValueError("UI cache version differs; rebuild the display cache")
            connection.execute("INSERT OR IGNORE INTO metadata VALUES('version',?)", (str(SCHEMA_VERSION),))
            connection.execute("INSERT OR IGNORE INTO metadata VALUES('generation',?)", (uuid.uuid4().hex,))
            connection.commit()
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def observe(self, instance_id, nodes, *, observed_at=None):
        observed_at = observed_at or datetime.now(timezone.utc).isoformat()
        with self.connect() as connection:
            for node in nodes[:200]:
                payload = json.dumps(node, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
                if len(payload.encode()) > 32 * 1024:
                    continue
                revision = hashlib.sha256(payload.encode()).hexdigest()
                prior = connection.execute("SELECT revision FROM nodes WHERE instance_id=? AND node_key=?",
                                           (instance_id, node["key"])).fetchone()
                if prior and prior[0] == revision:
                    continue
                connection.execute("""INSERT INTO nodes VALUES(?,?,?,?,?,?,?)
                    ON CONFLICT(instance_id,node_key) DO UPDATE SET revision=excluded.revision,
                    payload=excluded.payload,state=excluded.state,last_observed_at=excluded.last_observed_at""",
                    (instance_id, node["key"], revision, payload, node["state"], observed_at, observed_at))
                connection.execute("INSERT INTO events(instance_id,node_key,revision,source_time,observed_at,state) VALUES(?,?,?,?,?,?)",
                    (instance_id, node["key"], revision, node.get("source_time"), observed_at, node["state"]))
            connection.execute("""DELETE FROM events WHERE instance_id=? AND sequence NOT IN
                (SELECT sequence FROM events WHERE instance_id=? ORDER BY sequence DESC LIMIT ?)""",
                (instance_id, instance_id, MAX_EVENTS))

    def unsettled(self, instance_id):
        placeholders = ",".join("?" for _ in _TERMINAL)
        with self.connect() as connection:
            return [row[0] for row in connection.execute(
                f"SELECT node_key FROM nodes WHERE instance_id=? AND state NOT IN ({placeholders}) ORDER BY last_observed_at LIMIT 100",
                (instance_id, *sorted(_TERMINAL)))]

    def events(self, instance_id, *, after=None, limit=100):
        if not 1 <= limit <= 100:
            raise ValueError("UI event limit must be between 1 and 100")
        with self.connect() as connection:
            generation = connection.execute("SELECT value FROM metadata WHERE key='generation'").fetchone()[0]
            minimum, maximum = connection.execute("SELECT MIN(sequence),MAX(sequence) FROM events WHERE instance_id=?", (instance_id,)).fetchone()
            reset = False
            sequence = 0
            if after:
                try:
                    previous, text = after.split(":", 1)
                    sequence = int(text)
                    if sequence < 0:
                        raise ValueError("negative UI cursor")
                except (ValueError, AttributeError) as error:
                    raise ValueError("invalid UI event cursor") from error
                reset = previous != generation or (minimum is not None and sequence < minimum - 1) or sequence > (maximum or 0)
            if after is None or reset:
                return {"events": [], "cursor": f"{generation}:{maximum or 0}",
                        "reset_required": reset, "observation_history": "bounded_ui_observations"}
            rows = connection.execute("""SELECT sequence,node_key,revision,source_time,observed_at,state FROM events
                WHERE instance_id=? AND sequence>? ORDER BY sequence LIMIT ?""", (instance_id, sequence, limit + 1)).fetchall()
            entries, used = [], 0
            for row in rows[:limit]:
                entry = dict(row)
                size = len(json.dumps(entry, ensure_ascii=True).encode())
                if entries and used + size > 64 * 1024:
                    break
                entries.append(entry)
                used += size
            return {"events": entries, "cursor": f"{generation}:{entries[-1]['sequence'] if entries else sequence}",
                    "reset_required": False, "has_more": len(rows) > len(entries),
                    "observation_history": "bounded_ui_observations"}

    def observations(self, instance_id, *, node_key=None, before=None, limit=30):
        if not 1 <= limit <= 100 or (before is not None and before < 0):
            raise ValueError("invalid observation page")
        with self.connect() as connection:
            query = "SELECT sequence,node_key,revision,source_time,observed_at,state FROM events WHERE instance_id=?"
            arguments = [instance_id]
            if node_key is not None:
                query += " AND node_key=?"
                arguments.append(node_key)
            if before is not None:
                query += " AND sequence<?"
                arguments.append(before)
            rows = connection.execute(query + " ORDER BY sequence DESC LIMIT ?", (*arguments, limit + 1)).fetchall()
            return {"items": [dict(row) for row in rows[:limit]],
                    "next_before": rows[limit - 1]["sequence"] if len(rows) > limit else None,
                    "coverage": "only_states_observed_by_this_ui_cache"}

    def preferences(self, instance_id, value=None):
        with self.connect() as connection:
            if value is not None:
                if set(value) - {"show_artifacts"} or type(value.get("show_artifacts")) is not bool:
                    raise ValueError("unknown display preference")
                connection.execute("INSERT INTO preferences VALUES(?,?) ON CONFLICT(instance_id) DO UPDATE SET payload=excluded.payload",
                                   (instance_id, json.dumps(value)))
            row = connection.execute("SELECT payload FROM preferences WHERE instance_id=?", (instance_id,)).fetchone()
            return json.loads(row[0]) if row else {"show_artifacts": True}

    def cleanup_preview(self, instance_id):
        with self.connect() as connection:
            return self._cleanup_preview(connection, instance_id)

    @staticmethod
    def _cleanup_preview(connection, instance_id):
        digest, counts = hashlib.sha256(instance_id.encode()), {"nodes": 0, "events": 0, "logical_bytes": 0}
        for table, order in (("nodes", "node_key"), ("events", "sequence")):
            digest.update(table.encode())
            for row in connection.execute(f"SELECT * FROM {table} WHERE instance_id=? ORDER BY {order}", (instance_id,)):
                raw = json.dumps(dict(row), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
                digest.update(raw)
                counts[table] += 1
                counts["logical_bytes"] += len(raw)
        return {"action": "cleanup", "ready": True, "busy": [], "fingerprint": digest.hexdigest(),
                "counts": counts, "preserved": ["scientific_records", "originals", "archive", "maintenance_journal", "preferences"]}

    def cleanup(self, instance_id, fingerprint):
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            preview = self._cleanup_preview(connection, instance_id)
            if preview["fingerprint"] != fingerprint:
                raise ValueError("缓存已变化，请重新预览。")
            for table in ("nodes", "events"):
                connection.execute(f"DELETE FROM {table} WHERE instance_id=?", (instance_id,))
        return {**preview, "physical_bytes_released": 0,
                "space_note": "SQLite 空页供后续缓存复用，未缩减共享数据库文件；仅 UI 观测得到的旧时间已移除。"}


class TrajectoryObserver:
    """One service thread, subscribed instances only, bounded metadata per poll."""
    def __init__(self, model, store, *, maintenance=None, interval=2.0, writable=None):
        self.model, self.store, self.maintenance, self.interval = model, store, maintenance, interval
        self._lock, self._wake, self._stop = threading.Lock(), threading.Event(), threading.Event()
        self._subscriptions = {}
        self._thread = None
        self.errors = {}
        self.writable = writable or (lambda instance_id: True)

    def is_subscribed(self, instance_id):
        with self._lock:
            return bool(self._subscriptions.get(instance_id))

    def refresh(self, instance_id):
        try:
            with self.maintenance.shared() if self.maintenance else nullcontext():
                if not self.writable(instance_id):
                    return False
                recent = self.model.nodes(instance_id, limit=100)["items"]
                known = {node["key"] for node in recent}
                for key in self.store.unsettled(instance_id):
                    if key not in known:
                        try:
                            recent.append(self.model.node_metadata(instance_id, key))
                        except (ValueError, PermissionError):
                            continue
                self.store.observe(instance_id, recent)
            self.errors.pop(instance_id, None)
            return True
        except Exception as error:
            self.errors[instance_id] = {"code": "trajectory_observation_unavailable", "error_type": type(error).__name__}
            LOGGER.warning("UI observation unavailable: %s", type(error).__name__)
            return False

    @contextmanager
    def subscribe(self, instance_id):
        with self._lock:
            self._subscriptions[instance_id] = self._subscriptions.get(instance_id, 0) + 1
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, name="instance-view-observer", daemon=True)
                self._thread.start()
        self._wake.set()
        try:
            yield
        finally:
            with self._lock:
                self._subscriptions[instance_id] -= 1
                if not self._subscriptions[instance_id]:
                    del self._subscriptions[instance_id]

    def _run(self):
        while not self._stop.is_set():
            with self._lock:
                instances = tuple(self._subscriptions)[:8]
            for instance_id in instances:
                if self._stop.is_set():
                    break
                self.refresh(instance_id)
            self._wake.wait(self.interval if instances else 30)
            self._wake.clear()

    def stop(self):
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=5)
