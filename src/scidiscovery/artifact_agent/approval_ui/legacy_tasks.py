"""Read-only, exact-reference views of Task-era control records for the UI."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from ..schema.common import canonical_json
from ..schema.refs import ArtifactRef
from ..service.scheduler_bindings import SchedulerBinding
from .legacy_artifacts import LegacyUIArtifactEnvelope


class LegacyTaskReadError(ValueError):
    pass


@dataclass(frozen=True)
class LegacyTaskView:
    task_id: str
    task_ref: ArtifactRef
    role: str
    state: str
    attempt: int
    created_at: str
    last_activity_at: str | None
    inputs: tuple[tuple[str, ArtifactRef], ...]
    output_ref: ArtifactRef | None


def _reference(raw: object) -> ArtifactRef:
    if type(raw) is not bytes:
        raise LegacyTaskReadError("legacy Task Ref is not stored as bytes")
    try:
        ref = ArtifactRef.model_validate_json(raw, strict=True)
    except ValidationError as error:
        raise LegacyTaskReadError("legacy Task Ref is invalid") from error
    if ref.canonical_json() != raw:
        raise LegacyTaskReadError("legacy Task Ref is not canonical")
    return ref


def _binding(row: sqlite3.Row) -> SchedulerBinding:
    return SchedulerBinding(namespace=str(row["namespace"]), name=str(row["name"]),
        logical_name=str(row["logical_name"]), revision=int(row["revision"]),
        object_id=str(row["object_id"]),
        request_fingerprint=(str(row["request_fingerprint"])
            if row["request_fingerprint"] is not None else None),
        created_at=str(row["created_at"]))


class LegacyTaskReader:
    def __init__(self, *, task_database_path: Path, binding_database_path: Path, artifacts) -> None:
        self.task_database_path = Path(task_database_path)
        self.binding_database_path = Path(binding_database_path)
        self.artifacts = artifacts

    @staticmethod
    @contextmanager
    def _connect(path: Path):
        connection = sqlite3.connect(path.absolute().as_uri() + "?mode=ro", uri=True, timeout=2)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def binding(self, instance_id: str, name: str) -> SchedulerBinding | None:
        try:
            with self._connect(self.binding_database_path) as connection:
                row = connection.execute("SELECT * FROM scheduler_bindings "
                    "WHERE instance=? AND namespace='task' AND name=?", (instance_id, name)).fetchone()
        except sqlite3.Error as error:
            raise LegacyTaskReadError("legacy Task binding unavailable") from error
        return None if row is None else _binding(row)

    def trajectory_page(self, instance_id: str, page: int, limit: int = 10):
        try:
            with self._connect(self.binding_database_path) as connection:
                where = "FROM scheduler_bindings WHERE instance=? AND namespace IN ('task','run','approval','execution')"
                connection.execute("BEGIN")
                total = connection.execute("SELECT COUNT(*) " + where, (instance_id,)).fetchone()[0]
                page = min(page, max(1, (total + limit - 1) // limit))
                rows = connection.execute("SELECT * " + where +
                    " ORDER BY created_at DESC, namespace, name LIMIT ? OFFSET ?",
                    (instance_id, limit, (page - 1) * limit)).fetchall()
        except sqlite3.Error as error:
            raise LegacyTaskReadError("legacy Task trajectory unavailable") from error
        return tuple(_binding(row) for row in rows), total, page

    def read(self, task_id: str) -> LegacyTaskView:
        try:
            with self._connect(self.task_database_path) as connection:
                row = connection.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        except sqlite3.Error as error:
            raise LegacyTaskReadError("legacy Task database unavailable") from error
        if row is None:
            raise LegacyTaskReadError("bound legacy Task record is missing")
        task_ref = _reference(row["task_ref_json"])
        envelope = self.artifacts.catalog(task_ref)
        if (not isinstance(envelope, LegacyUIArtifactEnvelope) or envelope.kind != "agent_task"
                or envelope.schema_id != "scidiscovery.agent-task"):
            raise LegacyTaskReadError("bound legacy Task Artifact has the wrong identity")
        if envelope.size_bytes > 1024 * 1024:
            raise LegacyTaskReadError("legacy Task record exceeds UI read bound")
        raw = self.artifacts.read(task_ref)
        try:
            value = json.loads(raw)
            if not isinstance(value, dict) or canonical_json(value) != raw:
                raise ValueError("not a canonical Task record")
            if (value.get("task_id") != task_id or value.get("role") != row["role"]
                    or value.get("created_at") != row["created_at"]):
                raise ValueError("Task row and Artifact disagree")
            instruction = ArtifactRef.model_validate(value["instruction_ref"], strict=True)
            if instruction not in envelope.parent_refs:
                raise ValueError("Task instruction is not an exact parent Ref")
            inputs = value["inputs"]
            if not isinstance(inputs, list) or len(inputs) > 256:
                raise ValueError("Task inputs are malformed")
            parsed = tuple((item["name"], ArtifactRef.model_validate(item["artifact_ref"], strict=True))
                for item in inputs)
            if (len({name for name, _ in parsed}) != len(parsed)
                    or any(type(name) is not str or ref not in envelope.parent_refs for name, ref in parsed)):
                raise ValueError("Task input is not an exact parent Ref")
            output_ref = None if row["output_ref_json"] is None else _reference(row["output_ref_json"])
            if output_ref is not None:
                output = self.artifacts.catalog(output_ref)
                if not isinstance(output, LegacyUIArtifactEnvelope) or output.task_ref != task_ref:
                    raise ValueError("Task output does not bind the exact Task Ref")
        except (KeyError, TypeError, ValueError, ValidationError) as error:
            raise LegacyTaskReadError("legacy Task Artifact or output is inconsistent") from error
        return LegacyTaskView(task_id=task_id, task_ref=task_ref, role=row["role"],
            state=row["state"], attempt=row["attempt"], created_at=row["created_at"],
            last_activity_at=row["last_activity_at"], inputs=parsed, output_ref=output_ref)
