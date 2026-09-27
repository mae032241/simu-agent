"""Single recursive currentness rule used by Run preflight, creation and commit."""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path

from ..schema.refs import ArtifactRef
from .artifacts import ArtifactService
from .run_records import CurrentAnchor, RunInputBinding, RunStateConflict, RunStatus, status_from_row


class RunCurrentGuard:
    def __init__(
        self, *, artifacts: ArtifactService, scheduler_database_path: Path | str
    ) -> None:
        self.artifacts = artifacts
        self.scheduler_database_path = Path(scheduler_database_path).expanduser().absolute()

    def freeze(
        self,
        connection: sqlite3.Connection,
        instance_id: str,
        inputs: tuple[RunInputBinding, ...],
        *, compiled=None, origins=None,
    ) -> tuple[RunInputBinding, ...]:
        derived = origins.validate_inputs(compiled, inputs) if origins is not None else {}
        values: list[RunInputBinding] = []
        for item in inputs:
            binding = connection.execute(
                """
                SELECT object_id, logical_name
                FROM scheduler_control.scheduler_bindings
                WHERE instance = ? AND namespace = 'artifact' AND name = ?
                """,
                (instance_id, item.artifact_name),
            ).fetchone()
            if binding is None or str(binding["object_id"]) != item.artifact_ref.artifact_id:
                # A private derived input has no public binding of its own. Its
                # exact origin is revalidated by the same resolver as admission;
                # every non-derived anchor is still checked in this transaction.
                expected = derived.get((item.port_name, item.artifact_ref))
                if expected is None or item.require_current:
                    raise RunStateConflict("operation input binding changed before Run creation")
                values.append(replace(item, producer_run_id=expected.producer_run_id, current_anchors=()))
                continue
            producer = connection.execute(
                """
                SELECT * FROM runs
                WHERE state = 'completed' AND output_ref_json = ?
                ORDER BY completed_at DESC LIMIT 1
                """,
                (item.artifact_ref.canonical_json(),),
            ).fetchone()
            inherited: tuple[CurrentAnchor, ...] = ()
            producer_run_id: str | None = None
            if producer is not None:
                producer_status = status_from_row(producer)
                producer_run_id = producer_status.run_id
                if producer_status.completion_receipt is None:
                    raise RunStateConflict("producer Run has no completion receipt")
                inherited = producer_status.completion_receipt.current_anchors
            direct = tuple(
                CurrentAnchor(
                    kind=str(row["kind"]),
                    logical_name=str(row["logical_name"]),
                    artifact_ref=ArtifactRef.model_validate_json(
                        row["artifact_ref_json"], strict=True
                    ),
                )
                for row in connection.execute(
                    """
                    SELECT kind, logical_name, artifact_ref_json
                    FROM scheduler_control.scheduler_scientific_selections
                    WHERE instance = ? AND logical_name = ?
                      AND artifact_ref_json = ?
                    ORDER BY kind
                    """,
                    (
                        instance_id,
                        str(binding["logical_name"]),
                        item.artifact_ref.canonical_json(),
                    ),
                ).fetchall()
            )
            anchors = _unique_anchors((*direct, *inherited))
            if item.require_current and (
                not anchors or not self.unchanged(connection, instance_id, anchors)
            ):
                raise RunStateConflict("operation input is not on its exact current lineage")
            values.append(
                replace(
                    item,
                    producer_run_id=producer_run_id,
                    current_anchors=anchors if item.require_current else (),
                )
            )
        return tuple(values)

    def input_is_current(
        self,
        connection: sqlite3.Connection,
        *,
        instance_id: str,
        artifact_name: str,
        artifact_ref: ArtifactRef,
    ) -> bool:
        probe = RunInputBinding(
            port_name="probe",
            source_name="probe",
            artifact_name=artifact_name,
            artifact_ref=artifact_ref,
            media_type="application/octet-stream",
            exposure="handoff_only",
            usage="evidence_inventory",
            require_current=True,
        )
        try:
            self.freeze(connection, instance_id, (probe,))
        except RunStateConflict:
            return False
        return True

    @staticmethod
    def unchanged(
        connection: sqlite3.Connection,
        instance_id: str,
        anchors: tuple[CurrentAnchor, ...],
    ) -> bool:
        for anchor in anchors:
            row = connection.execute(
                """
                SELECT logical_name, artifact_ref_json
                FROM scheduler_control.scheduler_scientific_selections
                WHERE instance = ? AND kind = ?
                """,
                (instance_id, anchor.kind),
            ).fetchone()
            if (
                row is None
                or str(row["logical_name"]) != anchor.logical_name
                or row["artifact_ref_json"] is None
                or ArtifactRef.model_validate_json(
                    row["artifact_ref_json"], strict=True
                )
                != anchor.artifact_ref
            ):
                return False
        return True

    def run_is_current(
        self, connection: sqlite3.Connection, value: RunStatus
    ) -> bool:
        anchors = _unique_anchors(
            tuple(anchor for item in value.inputs for anchor in item.current_anchors)
        )
        return self.unchanged(connection, value.instance_id, anchors)


def _unique_anchors(values: tuple[CurrentAnchor, ...]) -> tuple[CurrentAnchor, ...]:
    return tuple(
        sorted(
            set(values),
            key=lambda item: (
                item.kind,
                item.logical_name,
                item.artifact_ref.artifact_id,
                item.artifact_ref.sha256,
            ),
        )
    )


__all__ = ["RunCurrentGuard"]
