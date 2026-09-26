"""Raw, identity-preserving records for instance storage maintenance.

These routines deliberately do not instantiate services or validate scientific
models. SQLite values (including BLOB/NULL) and original schema SQL survive the
round trip. Only the declared control carriers grant artifact reachability.
"""
from __future__ import annotations

from copy import deepcopy
from ...agent_execution_settings import EXECUTION_SETTINGS_COLUMNS
from .worker_connections import WORKER_CONNECTION_SCHEMA, WORKER_PARTICIPANT_SCHEMA

import base64
import gzip
import hashlib
import json
import re
import sqlite3
from pathlib import Path


DATABASES = {
    "scheduler": "scheduler-bindings.sqlite3", "runs": "runs.sqlite3",
    "approvals": "approvals.sqlite3", "executions": "executions.sqlite3",
    "artifacts": "artifact_agent.sqlite3",
}
TABLES = {
    "scheduler": ("scheduler_instances", "scheduler_bindings", "scheduler_observations",
                  "scheduler_scientific_selections", "scheduler_sessions"),
    "runs": ("runs", "run_activity", "run_tool_evidence", "run_activity_sequence", "worker_connections", "worker_participants"),
    "approvals": ("approval_requests", "approval_decisions", "used_nonces", "decision_attempts"),
    "executions": ("executions",),
    "artifacts": ("artifact_envelopes", "artifact_links", "idempotency_records", "artifact_events"),
    "dispatch": ("active_transport",),
    "views": ("metadata", "nodes", "events", "preferences"),
}
CONTROL_PAYLOADS = {
    "scidiscovery.approval-request", "scidiscovery.review-manifest", "scidiscovery.human-decision",
    "scidiscovery.execution-request", "scidiscovery.execution-result",
    "scidiscovery.tool-evidence-manifest.v1", "tcad.execution-package.v2",
    "tcad.reviewed-deck-package.v2",  # Historical archive reachability only.
}
MAX_RECORD_BYTES = 16 * 1024 * 1024
MAX_CONTROL_PAYLOAD_BYTES = 16 * 1024 * 1024


class ArchiveError(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def encode(value):
    if isinstance(value, bytes):
        return {"sqlite_blob": base64.b64encode(value).decode("ascii")}
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [encode(item) for item in value]
    return value


def decode(value):
    if isinstance(value, dict):
        if set(value) == {"sqlite_blob"}:
            return base64.b64decode(value["sqlite_blob"], validate=True)
        return {key: decode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [decode(item) for item in value]
    return value


def quote(name):
    return '"' + name.replace('"', '""') + '"'


class _ReadConnection(sqlite3.Connection):
    def __exit__(self, *values):
        try:
            return super().__exit__(*values)
        finally:
            self.close()


def readonly(path):
    connection = sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True, timeout=2, factory=_ReadConnection)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def database_paths(runtime):
    state = Path(runtime.state_root)
    paths = {key: state / "database" / filename for key, filename in DATABASES.items()}
    paths.update(dispatch=state / "hardened-runs" / "dispatch.sqlite3", views=state / "ui" / "workbench.sqlite3")
    return {key: path for key, path in paths.items() if path.exists()}


class ReadTicket:
    """Detect commits during an outside-lock scan using the same RO handles.

    No long-lived SQLite read transaction is opened: data_version must observe
    other connections' commits. The maintenance EX check closes the controlled
    writer race; arbitrary external writes to platform files are unsupported.
    """
    def __init__(self, runtime, *, databases=None):
        from .instance_archive_files import check_path
        self.runtime, self.connections, self.identities = runtime, {}, {}
        self.selected_databases = None if databases is None else frozenset(databases)
        self.paths = self._paths()
        try:
            for key, path in self.paths.items():
                info = check_path(path).stat()
                self.identities[key] = (info.st_dev, info.st_ino)
                self.connections[key] = readonly(path)
            self.versions = {key: connection.execute("PRAGMA data_version").fetchone()[0]
                             for key, connection in self.connections.items()}
        except BaseException:
            self.close()
            raise

    def validate(self):
        from .instance_archive_files import check_path
        if self._paths() != self.paths:
            raise ArchiveError("control databases changed during archive scan; retry preview or maintenance")
        for key, connection in self.connections.items():
            info = check_path(self.paths[key]).stat()
            if ((info.st_dev, info.st_ino) != self.identities[key]
                    or connection.execute("PRAGMA data_version").fetchone()[0] != self.versions[key]):
                raise ArchiveError("control records changed during archive scan; retry preview or maintenance")

    def _paths(self):
        return {key: path for key, path in database_paths(self.runtime).items()
                if self.selected_databases is None or key in self.selected_databases}

    def close(self):
        for connection in self.connections.values():
            connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def schema(connection, alias="main"):
    database = quote(alias)
    objects = [dict(row) for row in connection.execute(
        f"SELECT type,name,tbl_name,sql FROM {database}.sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name")]
    details = {}
    for obj in objects:
        if obj["type"] == "table":
            name = quote(obj["name"])
            details[obj["name"]] = {
                "columns": [dict(row) for row in connection.execute(f"PRAGMA {database}.table_xinfo({name})")],
                "foreign_keys": [dict(row) for row in connection.execute(f"PRAGMA {database}.foreign_key_list({name})")],
                "indexes": [dict(row) for row in connection.execute(f"PRAGMA {database}.index_list({name})")],
            }
            details[obj["name"]]["index_columns"] = {item["name"]: [dict(row) for row in connection.execute(f"PRAGMA {database}.index_xinfo({quote(item['name'])})")]
                                                    for item in details[obj["name"]]["indexes"]}
    return {"user_version": connection.execute(f"PRAGMA {database}.user_version").fetchone()[0],
            "objects": objects, "tables": details}


def execution_settings_restore_view(data):
    """Project additive settings and Worker bindings; never rewrite archive bytes.

    SQLite itself applies the same ALTER statements used by installation, preserving
    original table SQL, constraints and every unrelated index/trigger definition.
    """
    result = None
    for table, definitions in EXECUTION_SETTINGS_COLUMNS.items():
        info = data["schema"]["tables"].get(table)
        if info is None:
            continue
        present = {column["name"] for column in info["columns"]}
        missing = {name: value for name, value in definitions.items() if name not in present}
        if not missing:
            continue
        if result is None:
            result = deepcopy(data)
        obj = next(item for item in result["schema"]["objects"] if item["type"] == "table" and item["name"] == table)
        with sqlite3.connect(":memory:") as transient:
            transient.row_factory = sqlite3.Row
            transient.execute(obj["sql"])
            for name, (definition, _) in missing.items():
                transient.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
            obj["sql"] = transient.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()[0]
            result["schema"]["tables"][table]["columns"] = [dict(row) for row in transient.execute(f"PRAGMA table_xinfo({quote(table)})")]
        for row in result["tables"].get(table, []):
            for name, (_, default) in missing.items():
                row[name] = default
    projected = data if result is None else result
    if "runs" in projected["schema"]["tables"]:
        for table, ddl in (("worker_connections", WORKER_CONNECTION_SCHEMA), ("worker_participants", WORKER_PARTICIPANT_SCHEMA)):
            if table in projected["schema"]["tables"]:
                continue
            projected = deepcopy(projected)
            with sqlite3.connect(":memory:") as transient:
                transient.row_factory = sqlite3.Row
                transient.executescript(ddl)
                addition = schema(transient)
            projected["schema"]["objects"] = sorted(
                [*projected["schema"]["objects"], *addition["objects"]], key=lambda item: (item["type"], item["name"]))
            projected["schema"]["tables"].update(addition["tables"])
            projected["tables"][table] = []
    return projected


def execution_settings_tombstone(row):
    """Fixed migration defaults; existing values (including NULL) are never replaced."""
    return {**{name: value[1] for name, value in EXECUTION_SETTINGS_COLUMNS["scheduler_instances"].items()}, **row}


def read_database(path, key):
    with readonly(path) as connection:
        info = schema(connection)
        unknown = set(info["tables"]) - set(TABLES[key])
        if unknown:
            raise ArchiveError(f"unsupported tables in {key}: {','.join(sorted(unknown))}")
        mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        if str(mode).lower() != "delete":
            raise ArchiveError(f"{key} requires existing DELETE journal mode")
        tables, size = {}, 0
        for table in info["tables"]:
            rows = []
            # Only activity needs its implicit identity restored. Other rows have
            # immutable primary keys and may share a different physical rowid.
            select = "rowid AS __archive_rowid__,*" if table == "run_activity" else "*"
            for row in connection.execute(f"SELECT {select} FROM {quote(table)} ORDER BY rowid"):
                value = dict(row)
                size += sum(len(item) if isinstance(item, (str, bytes)) else 16 for item in value.values())
                if size > MAX_RECORD_BYTES:
                    raise ArchiveError(f"{key} inventory exceeds bounded record budget")
                rows.append(value)
            tables[table] = rows
    return {"schema": info, "tables": tables}


def exact_refs(value):
    """Walk an already trusted control carrier, never arbitrary scientific JSON."""
    if isinstance(value, dict):
        if {"artifact_id", "sha256", "kind", "schema_id"} <= value.keys():
            ref = tuple(value[key] for key in ("artifact_id", "sha256", "kind", "schema_id"))
            if all(isinstance(item, str) for item in ref) and re.fullmatch(r"[0-9a-f]{64}", ref[1]):
                yield ref
        for item in value.values():
            yield from exact_refs(item)
    elif isinstance(value, list):
        for item in value:
            yield from exact_refs(item)


def json_value(raw, context):
    try:
        return json.loads(raw)
    except (ValueError, TypeError, UnicodeError) as error:
        raise ArchiveError(f"invalid controlled JSON: {context}") from error


class Records:
    # These columns belong to control records. Instruction, reason, arbitrary
    # scientific payloads and cache presentation text never grant reachability.
    CONTROL_COLUMNS = (
        "artifact_ref_json", "inputs_json", "output_ref_json", "completion_receipt_json",
        "recovery_draft_json", "record_json", "diagnostic_json", "request_ref_json",
        "decision_ref_json", "create_request_json", "binding_json", "payload_ref_json", "result_ref_json",
    )
    TARGET_RECORD_BYTES = 32 * 1024 * 1024

    def __init__(self, runtime):
        self.runtime = runtime
        state = Path(runtime.state_root)
        self.paths = {key: state / "database" / filename for key, filename in DATABASES.items()}
        self.paths = {key: path for key, path in self.paths.items() if path.exists()}
        for key in ("scheduler", "runs", "artifacts"):
            if key not in self.paths:
                raise ArchiveError(f"required control database missing: {key}")
        dispatch = state / "hardened-runs" / "dispatch.sqlite3"
        views = state / "ui" / "workbench.sqlite3"
        if dispatch.exists():
            self.paths["dispatch"] = dispatch
        if views.exists():
            self.paths["views"] = views
        # Inventory schema first. No unrelated instance's BLOB is materialized
        # here, and the snapshot budget applies only after ownership selection.
        self.databases = {}
        for key, path in self.paths.items():
            with readonly(path) as connection:
                info = schema(connection)
                unknown = set(info["tables"]) - set(TABLES[key])
                if unknown:
                    raise ArchiveError(f"unsupported tables in {key}: {','.join(sorted(unknown))}")
                if str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower() != "delete":
                    raise ArchiveError(f"{key} requires existing DELETE journal mode")
            self.databases[key] = {"schema": info, "tables": {table: [] for table in info["tables"]}}
        self.envelopes, self.links = {}, {}
        self._record_bytes = 0
        self._producer_keys = set()
        self._uncertain_retention = None
        self.gaps = []

    def _columns(self, database, table):
        info = self.databases.get(database, {}).get("schema", {}).get("tables", {}).get(table)
        return tuple(column["name"] for column in info["columns"]) if info else ()

    def rows(self, database, table, *, columns=None, where="", parameters=()):
        """A fresh read-only cursor per call; callers may request narrow columns."""
        available = self._columns(database, table)
        if not available:
            return
        if columns is None:
            projection = "rowid AS __archive_rowid__,*" if table == "run_activity" else "*"
        else:
            if not columns or set(columns) - set(available):
                raise ArchiveError("unknown archive query column")
            projection = ",".join(map(quote, columns))
        query = f"SELECT {projection} FROM {quote(table)}"
        if where:
            query += " WHERE " + where
        with readonly(self.paths[database]) as connection:
            for row in connection.execute(query + " ORDER BY rowid", tuple(parameters)):
                yield dict(row)

    @staticmethod
    def _size_sql(columns):
        return "+".join(f"CASE WHEN typeof({quote(column)}) IN ('text','blob') "
                        f"THEN length(CAST({quote(column)} AS BLOB)) ELSE 16 END" for column in columns) or "0"

    def _materialize(self, database, table, *, where="", parameters=()):
        columns = self._columns(database, table)
        if not columns:
            return []
        size = self._size_sql(columns) + ("+16" if table == "run_activity" else "")
        source = quote(table) + (" WHERE " + where if where else "")
        # Check in SQLite before fetching a potentially very large target BLOB.
        # Both reads share a snapshot so concurrent writers cannot invalidate
        # the byte check between its aggregate and the actual row projection.
        with readonly(self.paths[database]) as connection:
            connection.execute("BEGIN")
            amount = connection.execute(f"SELECT coalesce(sum({size}),0) FROM {source}", tuple(parameters)).fetchone()[0]
            if self._record_bytes + amount > self.TARGET_RECORD_BYTES:
                raise ArchiveError("target control inventory exceeds bounded record budget")
            self._record_bytes += amount
            projection = "rowid AS __archive_rowid__,*" if table == "run_activity" else "*"
            return [dict(row) for row in connection.execute(f"SELECT {projection} FROM {source} ORDER BY rowid", tuple(parameters))]

    def _materialize_ids(self, database, table, column, ids):
        result, ordered = [], sorted(ids)
        # Keep below SQLite's traditional parameter bound. This order is stable
        # across previews; run_activity retains its original implicit rowid.
        for start in range(0, len(ordered), 400):
            batch = ordered[start:start + 400]
            result.extend(self._materialize(database, table,
                where=f"{quote(column)} IN ({','.join('?' for _ in batch)})", parameters=batch))
        return result

    def _envelope(self, artifact_id):
        if artifact_id not in self.envelopes:
            values = self._materialize("artifacts", "artifact_envelopes", where="artifact_id=?", parameters=(artifact_id,))
            if values:
                self.envelopes[artifact_id] = values[0]
        return self.envelopes.get(artifact_id)

    def _links(self, artifact_id):
        if artifact_id not in self.links:
            self.links[artifact_id] = self._materialize("artifacts", "artifact_links",
                where="source_artifact_id=?", parameters=(artifact_id,))
        return self.links[artifact_id]

    def control(self, instance_id):
        result = {key: {"schema": data["schema"], "tables": {table: [] for table in data["tables"]}}
                  for key, data in self.databases.items()}
        for table in result["scheduler"]["tables"]:
            column = "instance_id" if table in {"scheduler_instances", "scheduler_sessions"} else "instance"
            result["scheduler"]["tables"][table] = self._materialize("scheduler", table,
                where=quote(column) + "=?", parameters=(instance_id,))
        bindings = result["scheduler"]["tables"]["scheduler_bindings"]
        for table in result["runs"]["tables"]:
            # The global high-water allocator is never instance-owned. Preserve
            # its schema but not its value in a snapshot or target fingerprint.
            if table == "run_activity_sequence":
                continue
            condition = "instance_id=?" if table == "runs" else "run_id IN (SELECT run_id FROM runs WHERE instance_id=?)"
            result["runs"]["tables"][table] = self._materialize("runs", table,
                where=condition, parameters=(instance_id,))
        runs = {row["run_id"] for row in result["runs"]["tables"]["runs"]}
        approvals = {row["object_id"] for row in bindings if row["namespace"] == "approval"}
        executions = {row["object_id"] for row in bindings if row["namespace"] == "execution"}
        for database, ids, column in (("approvals", approvals, "approval_id"),
                                      ("executions", executions, "execution_id"), ("dispatch", runs, "run_id")):
            for table in result.get(database, {}).get("tables", {}):
                result[database]["tables"][table] = self._materialize_ids(database, table, column, ids)
        for table in result.get("views", {}).get("tables", {}):
            result["views"]["tables"][table] = self._materialize("views", table,
                where="" if table == "metadata" else "instance_id=?",
                parameters=() if table == "metadata" else (instance_id,))
        for namespace, ids, table, key in (("run", runs, "runs", "run_id"),
                ("approval", approvals, "approval_requests", "approval_id"),
                ("execution", executions, "executions", "execution_id")):
            database = {"run": "runs", "approval": "approvals", "execution": "executions"}[namespace]
            existing = {row[key] for row in result.get(database, {}).get("tables", {}).get(table, [])}
            for binding in bindings:
                if binding["namespace"] == namespace and binding["object_id"] not in existing:
                    self.gaps.append({"code": "control_record_missing", "namespace": namespace, "object_id": binding["object_id"]})
                if namespace == "run" and binding["namespace"] == namespace and binding["object_id"] not in runs:
                    raise ArchiveError("Run binding has missing or different recorded instance")
            for row in self.rows("scheduler", "scheduler_bindings", columns=("object_id",),
                    where="namespace=? AND instance IS NOT ?", parameters=(namespace, instance_id)):
                if row["object_id"] in ids:
                    raise ArchiveError(f"control object has multiple instance owners: {namespace}")
        return result, runs, approvals, executions

    def roots(self, selected, runs, approvals, executions):
        for database, data in selected.items():
            if database in {"artifacts", "views", "dispatch"}:
                continue
            for table, rows in data["tables"].items():
                for row in rows:
                    if table == "scheduler_bindings" and row["namespace"] == "artifact":
                        envelope = self._envelope(row["object_id"])
                        if envelope:
                            yield self.identity(envelope)
                        else:
                            self.gaps.append({"code": "bound_artifact_missing", "artifact_id": row["object_id"]})
                    for column in self.CONTROL_COLUMNS:
                        if row.get(column) is not None:
                            yield from exact_refs(json_value(row[column], table + "." + column))
        for namespace, ids in (("run", runs), ("execution", executions)):
            for object_id in sorted(ids):
                prefix = namespace + ":" + object_id + ":"
                # IDs can contain colons. Bind the complete owner ID rather
                # than splitting the key or treating LIKE underscores as wildcards.
                for row in self.rows("artifacts", "idempotency_records", columns=("idempotency_key", "artifact_id"),
                        where="idempotency_key>=? AND idempotency_key<?", parameters=(prefix, prefix[:-1] + ";")):
                    key, suffix = row["idempotency_key"], row["idempotency_key"][len(prefix):]
                    owned = (bool(re.fullmatch(r"(?:candidate:[0-9a-f]{64}|tool-manifest:[0-9a-f]{64}|tool:[^:]+)", suffix))
                             if namespace == "run" else suffix in {"request", "result"} or suffix.startswith("output:"))
                    if owned:
                        envelope = self._envelope(row["artifact_id"])
                        if envelope:
                            self._producer_keys.add(key)
                            yield self.identity(envelope)
        for approval in sorted(approvals):
            for name in ("review_manifest_" + approval, "approval_request_" + approval):
                envelope = self._envelope(name)
                if envelope:
                    yield self.identity(envelope)
        from .instance_archive_files import workspace_refs
        for row in selected.get("runs", {}).get("tables", {}).get("runs", []):
            yield from workspace_refs(self.runtime, [row])

    @staticmethod
    def identity(row):
        return tuple(row[key] for key in ("artifact_id", "payload_sha256", "kind", "schema_id"))

    def _payload_refs(self, envelope, *, retained=False):
        if envelope["schema_id"] not in CONTROL_PAYLOADS:
            return
        path = self.runtime.artifacts.cas.path_for(envelope["payload_sha256"])
        if not path.exists():
            if retained:
                raise ArchiveError("retained controlled payload missing")
            self.gaps.append({"code": "controlled_payload_missing", "artifact_id": envelope["artifact_id"]})
            return
        if path.stat().st_size > MAX_CONTROL_PAYLOAD_BYTES:
            raise ArchiveError("controlled payload exceeds reference scan budget")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != envelope["payload_sha256"]:
            raise ArchiveError("controlled payload hash mismatch")
        encoding = json_value(envelope["envelope_json"], "envelope").get("content_encoding", "identity")
        if encoding == "gzip":
            import io
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
                raw = stream.read(MAX_CONTROL_PAYLOAD_BYTES + 1)
        elif encoding != "identity":
            raise ArchiveError("unsupported controlled payload encoding: " + str(encoding))
        if len(raw) > MAX_CONTROL_PAYLOAD_BYTES:
            raise ArchiveError("decoded control payload exceeds reference scan budget")
        yield from exact_refs(json_value(raw, envelope["artifact_id"]))

    def closure(self, roots, *, allowed=None):
        found, seen = set(), set()
        for root in roots:
            pending = {root}
            while pending:
                ref = pending.pop()
                if ref in seen or (allowed is not None and ref not in allowed):
                    continue
                seen.add(ref)
                envelope = self._envelope(ref[0])
                if envelope is None:
                    self.gaps.append({"code": "referenced_artifact_missing", "artifact_id": ref[0]})
                    continue
                if self.identity(envelope) != ref:
                    raise ArchiveError("artifact reference identity mismatch: " + ref[0])
                if hashlib.sha256(envelope["envelope_json"]).hexdigest() != envelope["envelope_sha256"]:
                    raise ArchiveError("artifact envelope hash mismatch: " + ref[0])
                found.add(ref)
                for link in self._links(ref[0]):
                    linked = tuple(link[key] for key in ("target_artifact_id", "target_sha256", "target_kind", "target_schema_id"))
                    if linked not in seen and (allowed is None or linked in allowed):
                        pending.add(linked)
                for linked in self._payload_refs(envelope):
                    if linked not in seen and (allowed is None or linked in allowed):
                        pending.add(linked)
        return found

    def _uncertain(self, context):
        # An unrelated malformed/oversized control carrier does not block a
        # small archive. Keep active copies and bound the diagnostic itself.
        if self._uncertain_retention is None:
            self._uncertain_retention = {"code": "retained_control_scan_incomplete", "count": 0,
                                         "examples": [], "retention": "all_target_artifacts"}
            self.gaps.append(self._uncertain_retention)
        self._uncertain_retention["count"] += 1
        if len(self._uncertain_retention["examples"]) < 8:
            self._uncertain_retention["examples"].append(str(context)[:256])

    def _bounded_rows(self, database, table, columns, *, where="", parameters=()):
        """Stream carriers without transferring an oversized foreign BLOB."""
        if not self._columns(database, table):
            return
        if set(columns) - set(self._columns(database, table)):
            raise ArchiveError("unknown archive query column")
        size = self._size_sql(columns)
        projection = ",".join(f"CASE WHEN ({size})<={MAX_CONTROL_PAYLOAD_BYTES} THEN {quote(column)} END AS {quote(column)}"
                              for column in columns)
        query = f"SELECT {projection},(({size})>{MAX_CONTROL_PAYLOAD_BYTES}) AS __archive_oversized__ FROM {quote(table)}"
        if where:
            query += " WHERE " + where
        with readonly(self.paths[database]) as connection:
            for row in connection.execute(query + " ORDER BY rowid", tuple(parameters)):
                yield dict(row)

    def _retained(self, instance_id, target, runs, approvals, executions):
        by_id = {ref[0]: ref for ref in target}
        target_digests = {ref[1] for ref in target}
        seeds, shared = set(), set()

        def retain(ref):
            if ref[0] in by_id:
                if ref != by_id[ref[0]]:
                    self._uncertain("retained artifact reference identity differs")
                seeds.add(by_id[ref[0]])

        # Every non-target registration stays active, including unowned ones.
        # Only its digest intersection and final edge into the target matter;
        # there is no need to retain the outside graph or its envelope BLOBs.
        for row in self.rows("artifacts", "artifact_envelopes", columns=("artifact_id", "payload_sha256")):
            if row["artifact_id"] not in by_id and row["payload_sha256"] in target_digests:
                shared.add(row["payload_sha256"])
        link_columns = ("source_artifact_id", "target_artifact_id", "target_sha256", "target_kind", "target_schema_id")
        for row in self.rows("artifacts", "artifact_links", columns=link_columns):
            if row["source_artifact_id"] not in by_id:
                retain(tuple(row[key] for key in link_columns[1:]))
        for row in self.rows("scheduler", "scheduler_bindings", columns=("namespace", "object_id"),
                where="instance IS NOT ?", parameters=(instance_id,)):
            names = ((row["object_id"],) if row["namespace"] == "artifact" else
                     ("review_manifest_" + row["object_id"], "approval_request_" + row["object_id"])
                     if row["namespace"] == "approval" else ())
            seeds.update(by_id[name] for name in names if name in by_id)

        for database, data in self.databases.items():
            if database not in {"scheduler", "runs", "approvals", "executions"}:
                continue
            for table in data["tables"]:
                columns = tuple(column for column in self.CONTROL_COLUMNS if column in self._columns(database, table))
                if not columns:
                    continue
                where, parameters, owner_column, owners = "", (), None, ()
                if database == "scheduler":
                    where, parameters = "instance IS NOT ?", (instance_id,)
                elif database == "runs":
                    where = "instance_id IS NOT ?" if table == "runs" else "run_id NOT IN (SELECT run_id FROM runs WHERE instance_id=?)"
                    parameters = (instance_id,)
                else:
                    owner_column, owners = ("approval_id", approvals) if database == "approvals" else ("execution_id", executions)
                projection = ((owner_column,) if owner_column else ()) + columns
                for row in self._bounded_rows(database, table, projection, where=where, parameters=parameters):
                    if owner_column and row[owner_column] in owners:
                        continue
                    if row["__archive_oversized__"]:
                        self._uncertain(table + ": oversized control record")
                        continue
                    for column in columns:
                        if row[column] is not None:
                            try:
                                for ref in exact_refs(json_value(row[column], table + "." + column)):
                                    retain(ref)
                            except (ArchiveError, RecursionError):
                                self._uncertain(table + "." + column + ": invalid control record")

        columns = ("artifact_id", "payload_sha256", "kind", "schema_id", "envelope_json", "envelope_sha256")
        schemas = sorted(CONTROL_PAYLOADS)
        for row in self._bounded_rows("artifacts", "artifact_envelopes", columns,
                where=f"schema_id IN ({','.join('?' for _ in schemas)})", parameters=schemas):
            if row["artifact_id"] in by_id:
                continue
            try:
                if row["__archive_oversized__"]:
                    raise ArchiveError("oversized retained envelope")
                if hashlib.sha256(row["envelope_json"]).hexdigest() != row["envelope_sha256"]:
                    raise ArchiveError("retained envelope hash differs")
                for ref in self._payload_refs(row, retained=True):
                    retain(ref)
            except (ArchiveError, OSError, EOFError, ValueError, TypeError, AttributeError, RecursionError):
                self._uncertain("retained controlled artifact could not be scanned")

        # Producer registrations may be roots even before a Run binds output.
        # Read only keys and IDs; original request/response BLOBs are selected
        # once, with the target registry rows, below.
        for row in self.rows("artifacts", "idempotency_records", columns=("idempotency_key", "artifact_id")):
            if row["artifact_id"] not in by_id or row["idempotency_key"] in self._producer_keys:
                continue
            if re.fullmatch(r"run:.+:(?:candidate:[0-9a-f]{64}|tool-manifest:[0-9a-f]{64}|tool:[^:]+)|execution:.+:(?:request|result|output:.*)", row["idempotency_key"]):
                seeds.add(by_id[row["artifact_id"]])

        from .instance_archive_files import workspace_refs
        columns = tuple(column for column in ("run_id", "backend_id", "recovery_candidate_digest", "recovery_draft_json")
                        if column in self._columns("runs", "runs"))
        for row in self._bounded_rows("runs", "runs", columns, where="instance_id IS NOT ?", parameters=(instance_id,)):
            try:
                if row["__archive_oversized__"]:
                    raise ArchiveError("oversized retained recovery carrier")
                for ref in workspace_refs(self.runtime, [row]):
                    retain(ref)
            except (ArchiveError, OSError, ValueError, TypeError, AttributeError, RecursionError):
                self._uncertain("retained workspace control manifest could not be scanned")
        retained = target if self._uncertain_retention else self.closure(seeds, allowed=target)
        return retained, shared | {ref[1] for ref in retained}

    def select(self, instance_id):
        selected, runs, approvals, executions = self.control(instance_id)
        target = self.closure(self.roots(selected, runs, approvals, executions))
        target_ids = {ref[0] for ref in target}
        retained, shared_digests = self._retained(instance_id, target, runs, approvals, executions) if target else (set(), set())
        # A missing control carrier could contain retained nested references.
        # Preserve all target objects on the active side in this bounded case.
        if any(item["code"] == "controlled_payload_missing" for item in self.gaps):
            retained |= target
            shared_digests.update(ref[1] for ref in target)
        for table in selected["artifacts"]["tables"]:
            if table == "artifact_envelopes":
                values = [self.envelopes[key] for key in sorted(target_ids)]
            elif table == "artifact_links":
                values = [row for key in sorted(target_ids) for row in self.links[key]]
            else:
                values = self._materialize_ids("artifacts", table, "artifact_id", target_ids)
            selected["artifacts"]["tables"][table] = values
        for row in selected["artifacts"]["tables"].get("idempotency_records", []):
            if row["idempotency_key"] in self._producer_keys:
                for prefix in ("request", "response"):
                    if hashlib.sha256(row[prefix + "_json"]).hexdigest() != row[prefix + "_sha256"]:
                        raise ArchiveError("producer idempotency bytes differ")
                response = json_value(row["response_json"], "idempotency response")
                if not isinstance(response, dict) or response.get("artifact_id") != row["artifact_id"]:
                    raise ArchiveError("producer idempotency identity differs")
        return {"databases": selected, "run_ids": sorted(runs), "approval_ids": sorted(approvals),
                "execution_ids": sorted(executions), "artifact_ids": sorted(target_ids),
                "exclusive_artifact_ids": sorted(ref[0] for ref in target - retained),
                "shared_digests": sorted(shared_digests),
                "gaps": list(self.gaps)}


def build_database(path, data):
    """Create an archive-only subset without running production migrations."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("BEGIN IMMEDIATE")
        for obj in data["schema"]["objects"]:
            if obj["type"] == "table":
                connection.execute(obj["sql"])
        for table, rows in data["tables"].items():
            for row in rows:
                columns = ["rowid" if key == "__archive_rowid__" else key for key in row]
                connection.execute(f"INSERT INTO {quote(table)} ({','.join(map(quote, columns))}) VALUES ({','.join('?' for _ in columns)})", tuple(row.values()))
        for obj in data["schema"]["objects"]:
            if obj["type"] != "table" and obj["sql"]:
                connection.execute(obj["sql"])
        connection.execute("PRAGMA user_version=" + str(data["schema"]["user_version"]))
        connection.commit()
        if connection.execute("PRAGMA foreign_key_check").fetchone():
            raise ArchiveError("archive subset has dangling database foreign keys")
    finally:
        connection.close()


def attached(paths):
    """One on-disk SQLite transaction, with the existing database inodes."""
    from .instance_archive_files import check_path
    if any(not check_path(path).is_file() for path in paths.values()):
        raise ArchiveError("an original attached database is missing")
    connection = sqlite3.connect(paths["scheduler"], timeout=2, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        for key, path in paths.items():
            if key != "scheduler":
                connection.execute(f"ATTACH DATABASE ? AS {quote(key)}", (str(path),))
        for key in paths:
            alias = "main" if key == "scheduler" else key
            if connection.execute(f"PRAGMA {quote(alias)}.journal_mode").fetchone()[0].lower() != "delete":
                raise ArchiveError("attached archive transaction requires DELETE journals")
            connection.execute(f"PRAGMA {quote(alias)}.synchronous=FULL")
        return connection
    except BaseException:
        connection.close()
        raise


def row_where(row, table_info):
    primary = [column["name"] for column in sorted(table_info["columns"], key=lambda item: item["pk"]) if column["pk"]]
    if "__archive_rowid__" in row:
        return 'rowid=?', (row["__archive_rowid__"],)
    if not primary:
        raise ArchiveError("unsupported table without stable row identity")
    return " AND ".join(quote(key) + " IS ?" for key in primary), tuple(row[key] for key in primary)


def transfer_records(paths, selected, *, direction, exclusive_ids=(), tombstone=None, fault=lambda point: None):
    """Remove/restore exact rows; all databases and trigger changes roll back together."""
    if direction == "restore":
        selected = {key: execution_settings_restore_view(data) for key, data in selected.items()}
        tombstone = execution_settings_tombstone(tombstone)
    connection = attached(paths)
    triggers = []
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("PRAGMA defer_foreign_keys=ON")
        if direction == "archive" and "run_activity_sequence" in selected.get("runs", {}).get("tables", {}):
            connection.execute("UPDATE runs.run_activity_sequence SET high_water=MAX(high_water,COALESCE((SELECT MAX(rowid) FROM runs.run_activity),0)) WHERE slot=1")
        for key, data in selected.items():
            alias = "main" if key == "scheduler" else key
            current = [dict(row) for row in connection.execute(f"SELECT type,name,tbl_name,sql FROM {quote(alias)}.sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name")]
            if schema(connection, alias) != data["schema"]:
                raise ArchiveError("database schema changed since archive: " + key)
            if connection.execute(f"PRAGMA {quote(alias)}.user_version").fetchone()[0] != data["schema"]["user_version"]:
                raise ArchiveError("database version changed since archive: " + key)
            if direction == "archive":
                for obj in current:
                    if (obj["type"] == "trigger" and obj["name"] == obj["tbl_name"] + "_deny_delete"
                            and obj["tbl_name"] in {"artifact_envelopes", "artifact_links", "idempotency_records", "artifact_events",
                                                    "approval_decisions", "used_nonces", "decision_attempts"}):
                        triggers.append((alias, obj))
                        connection.execute(f"DROP TRIGGER {quote(alias)}.{quote(obj['name'])}")
        for key, data in selected.items():
            alias = "main" if key == "scheduler" else key
            for table, rows in data["tables"].items():
                if table in {"scheduler_sessions", "run_activity_sequence"} or (key == "views" and table == "metadata"):
                    continue
                if direction == "restore" and key == "dispatch":
                    continue
                for row in rows:
                    if key == "artifacts" and direction == "archive":
                        owner = row["source_artifact_id"] if table == "artifact_links" else row["artifact_id"]
                        if owner not in exclusive_ids:
                            continue
                    where, parameters = row_where(row, data["schema"]["tables"][table])
                    select = "rowid AS __archive_rowid__,*" if "__archive_rowid__" in row else "*"
                    actual = connection.execute(f"SELECT {select} FROM {quote(alias)}.{quote(table)} WHERE {where}", parameters).fetchone()
                    if table == "scheduler_instances":
                        if actual is None or dict(actual) != tombstone:
                            raise ArchiveError("instance tombstone identity conflict")
                        if direction == "restore":
                            columns = list(row)
                            connection.execute(f"UPDATE {quote(alias)}.{quote(table)} SET " + ",".join(quote(column) + "=?" for column in columns) + " WHERE " + where,
                                               (*row.values(), *parameters))
                        continue
                    if direction == "archive":
                        if actual is None or dict(actual) != row:
                            raise ArchiveError("active record differs from frozen archive: " + table)
                        connection.execute(f"DELETE FROM {quote(alias)}.{quote(table)} WHERE {where}", parameters)
                    elif actual is not None:
                        if dict(actual) != row:
                            raise ArchiveError("restore record identity conflict: " + table)
                    else:
                        columns = ["rowid" if column == "__archive_rowid__" else column for column in row]
                        connection.execute(f"INSERT INTO {quote(alias)}.{quote(table)} ({','.join(map(quote, columns))}) VALUES ({','.join('?' for _ in columns)})", tuple(row.values()))
            fault("database:" + key)
        for alias, obj in triggers:
            sql = re.sub(r"^(CREATE\s+TRIGGER\s+(?:IF\s+NOT\s+EXISTS\s+)?)(\"[^\"]+\"|\S+)",
                         lambda match: match[1] + quote(alias) + "." + match[2], obj["sql"], count=1, flags=re.I)
            connection.execute(sql)
        for key, data in selected.items():
            alias = "main" if key == "scheduler" else key
            current = [dict(row) for row in connection.execute(f"SELECT type,name,tbl_name,sql FROM {quote(alias)}.sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name")]
            if schema(connection, alias) != data["schema"]:
                raise ArchiveError("original trigger definitions were not restored")
        # foreign_keys=ON and defer_foreign_keys=ON enforce this transaction's
        # dependencies at COMMIT. Do not rescan unrelated instances' entire
        # existing graph with a database-wide foreign_key_check under global EX.
        fault("before_database_commit")
        connection.execute("COMMIT")
        fault("after_database_commit")
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()
