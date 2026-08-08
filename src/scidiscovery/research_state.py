from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


NonEmpty = Annotated[str, Field(min_length=1)]


class ScientificModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


SOURCE_PATHS = {
    "task": "research/task.yaml",
    "environment": "research/environment.yaml",
    "acceptance": "research/acceptance.yaml",
    "legacy_state": "research/state.yaml",
    "hypotheses": "research/hypotheses.md",
    "decisions": "research/decisions.md",
    "runs": "research/runs.jsonl",
    "evidence_database": "agent/runtime/evidence.sqlite3",
}


class CurrentStateValidationError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = tuple(errors)
        super().__init__("current-state validation failed:\n- " + "\n- ".join(errors))


class CurrentFocus(ScientificModel):
    operational_phase: NonEmpty
    scientific_phase: NonEmpty
    latest_user_directive: NonEmpty
    contradiction: NonEmpty
    next_action: NonEmpty


class ScientificPosition(ScientificModel):
    evidence_level: Literal[
        "exploratory", "diagnostic", "candidate", "validated", "accepted"
    ]
    accepted_dark_current_model: bool
    accepted_optical_model: bool
    accepted_model_refs: tuple[str, ...] = ()
    latest_verdict: NonEmpty
    blockers: tuple[NonEmpty, ...] = ()
    prohibited_next_actions: tuple[NonEmpty, ...] = ()

    @model_validator(mode="after")
    def accepted_models_require_registry_refs(self) -> ScientificPosition:
        if (
            self.accepted_dark_current_model or self.accepted_optical_model
        ) and not self.accepted_model_refs:
            raise ValueError("an accepted model claim requires accepted_model_refs")
        return self


class ActiveJob(ScientificModel):
    run_id: NonEmpty
    phase: NonEmpty
    lane: NonEmpty
    remote_host: NonEmpty
    pid: int = Field(ge=1)
    state_dir: NonEmpty


class CompletedRun(ScientificModel):
    run_id: NonEmpty
    base_run_id: NonEmpty
    phase: NonEmpty
    lane: NonEmpty
    status: int
    numerical_verdict: NonEmpty
    scientific_verdict: NonEmpty
    acceptance_level: NonEmpty
    accepted_model: bool
    artifacts: tuple[NonEmpty, ...]
    key_metrics: dict[str, float | int | str | bool] = Field(default_factory=dict)

    @model_validator(mode="after")
    def completion_cannot_be_pending(self) -> CompletedRun:
        pending_tokens = ("submitted", "executing", "running", "pending")
        lowered = self.acceptance_level.lower()
        if any(token in lowered for token in pending_tokens):
            raise ValueError("completed run has a non-terminal acceptance_level")
        return self


class RegistryIndex(ScientificModel):
    scope: Literal["selected_current_dependency_refs"]
    accepted: tuple[NonEmpty, ...] = ()
    validated: tuple[NonEmpty, ...] = ()
    candidate: tuple[NonEmpty, ...] = ()
    rejected: tuple[NonEmpty, ...] = ()
    stale: tuple[NonEmpty, ...] = ()

    @model_validator(mode="after")
    def references_are_unique(self) -> RegistryIndex:
        groups = (
            self.accepted,
            self.validated,
            self.candidate,
            self.rejected,
            self.stale,
        )
        refs = [ref for group in groups for ref in group]
        if len(refs) != len(set(refs)):
            raise ValueError("a registry reference appears in multiple status groups")
        return self


class SourceDigest(ScientificModel):
    path: NonEmpty
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SourceIntegrity(ScientificModel):
    files: dict[NonEmpty, SourceDigest]
    runs_records: int = Field(ge=0)
    addressable_run_events: int = Field(ge=0)
    latest_run_id: NonEmpty


class HistoryPolicy(ScientificModel):
    current_entry: NonEmpty
    immutable_run_ledger: NonEmpty
    legacy_state_mode: Literal["append_only_history_not_current_entry"]
    migration_status: NonEmpty


class CurrentStateSnapshot(ScientificModel):
    schema_version: Literal[1]
    updated: date
    project: NonEmpty
    authority: Literal["unique_current_state_entry"]
    focus: CurrentFocus
    scientific_position: ScientificPosition
    active_jobs: tuple[ActiveJob, ...] = ()
    latest_completed_run: CompletedRun
    registry: RegistryIndex
    source_integrity: SourceIntegrity
    history: HistoryPolicy

    @model_validator(mode="after")
    def cross_field_invariants(self) -> CurrentStateSnapshot:
        run_ids = [job.run_id for job in self.active_jobs]
        if len(run_ids) != len(set(run_ids)):
            raise ValueError("active job run_ids must be unique")
        accepted_refs = set(self.registry.accepted)
        missing = set(self.scientific_position.accepted_model_refs) - accepted_refs
        if missing:
            raise ValueError(
                "accepted_model_refs are not accepted in the registry index: "
                + ", ".join(sorted(missing))
            )
        return self


def _workspace_path(workspace: Path, relative_path: str) -> Path:
    workspace = workspace.resolve()
    candidate = (workspace / relative_path).resolve()
    if candidate != workspace and workspace not in candidate.parents:
        raise ValueError(f"path escapes workspace: {relative_path}")
    return candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_run_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON at {path}:{line_number}: {exc}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"run record is not an object at {path}:{line_number}")
        records.append(record)
    return records


def load_current_state(path: Path | str) -> CurrentStateSnapshot:
    source = Path(path)
    payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    return CurrentStateSnapshot.model_validate(payload)


def dump_current_state(snapshot: CurrentStateSnapshot) -> str:
    def normalize(value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, dict):
            return {key: normalize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [normalize(item) for item in value]
        return value

    payload = normalize(snapshot.model_dump(mode="json", exclude_none=True))
    return yaml.safe_dump(
        payload,
        allow_unicode=True,
        sort_keys=False,
        width=100,
    )


def refresh_integrity(
    snapshot: CurrentStateSnapshot, workspace: Path | str
) -> CurrentStateSnapshot:
    root = Path(workspace).resolve()
    files = {
        name: SourceDigest(path=relative_path, sha256=_sha256(root / relative_path))
        for name, relative_path in SOURCE_PATHS.items()
    }
    records = _load_run_records(root / SOURCE_PATHS["runs"])
    addressable = [record for record in records if record.get("run_id")]
    if not addressable:
        raise CurrentStateValidationError(["run ledger has no addressable run events"])
    integrity = SourceIntegrity(
        files=files,
        runs_records=len(records),
        addressable_run_events=len(addressable),
        latest_run_id=str(addressable[-1]["run_id"]),
    )
    return snapshot.model_copy(
        update={"updated": date.today(), "source_integrity": integrity}
    )


def validate_current_state(
    snapshot: CurrentStateSnapshot,
    workspace: Path | str,
    *,
    evidence_database: Path | None = None,
    check_source_hashes: bool = True,
    check_artifacts: bool = True,
) -> None:
    root = Path(workspace).resolve()
    errors: list[str] = []

    actual_source_names = set(snapshot.source_integrity.files)
    expected_source_names = set(SOURCE_PATHS)
    if actual_source_names != expected_source_names:
        errors.append(
            "source set differs from contract: "
            f"actual={sorted(actual_source_names)}, "
            f"expected={sorted(expected_source_names)}"
        )

    for name, expected_relative_path in SOURCE_PATHS.items():
        source = snapshot.source_integrity.files.get(name)
        if source is None:
            continue
        if source.path != expected_relative_path:
            errors.append(
                f"source {name} points to {source.path}, "
                f"expected {expected_relative_path}"
            )
            continue
        path = _workspace_path(root, source.path)
        if not path.is_file():
            errors.append(f"source file is missing: {source.path}")
        elif check_source_hashes:
            actual_hash = _sha256(path)
            if source.sha256 != actual_hash:
                errors.append(
                    f"source hash is stale for {source.path}: "
                    f"{source.sha256} != {actual_hash}"
                )

    runs_path = root / SOURCE_PATHS["runs"]
    if runs_path.is_file():
        try:
            records = _load_run_records(runs_path)
        except ValueError as exc:
            errors.append(str(exc))
            records = []
    else:
        records = []

    if len(records) != snapshot.source_integrity.runs_records:
        errors.append(
            "run ledger record count is stale: "
            f"{snapshot.source_integrity.runs_records} != {len(records)}"
        )
    addressable = [record for record in records if record.get("run_id")]
    if len(addressable) != snapshot.source_integrity.addressable_run_events:
        errors.append(
            "addressable run-event count is stale: "
            f"{snapshot.source_integrity.addressable_run_events} != {len(addressable)}"
        )
    if addressable:
        actual_latest_run_id = str(addressable[-1]["run_id"])
        if snapshot.source_integrity.latest_run_id != actual_latest_run_id:
            errors.append(
                "latest run pointer is stale: "
                f"{snapshot.source_integrity.latest_run_id} != {actual_latest_run_id}"
            )

    completed = snapshot.latest_completed_run
    matching = [
        record for record in addressable if record["run_id"] == completed.run_id
    ]
    if len(matching) != 1:
        errors.append(
            f"latest_completed_run {completed.run_id} occurs "
            f"{len(matching)} times in ledger"
        )
    else:
        record = matching[0]
        comparisons = {
            "phase": completed.phase,
            "lane": completed.lane,
            "status": completed.status,
            "acceptance_level": completed.acceptance_level,
        }
        for key, expected in comparisons.items():
            if record.get(key) != expected:
                errors.append(
                    f"latest_completed_run.{key} differs from ledger: "
                    f"{expected!r} != {record.get(key)!r}"
                )
        if tuple(record.get("artifacts", ())) != completed.artifacts:
            errors.append("latest_completed_run.artifacts differ from the run ledger")
        if "status" not in record and not completed.run_id.endswith("-completion"):
            errors.append(
                "latest_completed_run does not point to a terminal ledger event"
            )

    terminal_ids: set[str] = set()
    terminal_records: list[dict[str, Any]] = []
    for record in addressable:
        run_id = str(record["run_id"])
        if "status" in record or run_id.endswith("-completion"):
            terminal_ids.add(run_id)
            terminal_records.append(record)
    if terminal_records:
        latest_terminal_run_id = str(terminal_records[-1]["run_id"])
        if completed.run_id != latest_terminal_run_id:
            errors.append(
                "latest_completed_run is not the latest terminal ledger event: "
                f"{completed.run_id} != {latest_terminal_run_id}"
            )
    for job in snapshot.active_jobs:
        if any(
            terminal == job.run_id
            or terminal.startswith(f"{job.run_id}-")
            for terminal in terminal_ids
        ):
            errors.append(
                f"active job {job.run_id} already has a terminal run-ledger record"
            )
        if not any(
            str(record["run_id"]) == job.run_id
            or str(record["run_id"]).startswith(f"{job.run_id}-")
            for record in addressable
        ):
            errors.append(f"active job {job.run_id} has no run-ledger submission event")

    if check_artifacts:
        for artifact in completed.artifacts:
            try:
                artifact_path = _workspace_path(root, artifact)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            if not artifact_path.is_file():
                errors.append(f"latest completed artifact is missing: {artifact}")

    database = evidence_database or root / SOURCE_PATHS["evidence_database"]
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT o.object_ref, s.status AS effective_status
            FROM scientific_objects o
            JOIN object_status s USING(object_ref)
            """
        ).fetchall()
    finally:
        connection.close()
    actual_registry = {row["object_ref"]: row["effective_status"] for row in rows}
    for expected_status in ("accepted", "validated", "candidate", "rejected", "stale"):
        for object_ref in getattr(snapshot.registry, expected_status):
            actual_status = actual_registry.get(object_ref)
            if actual_status is None:
                errors.append(f"registry reference does not exist: {object_ref}")
            elif actual_status != expected_status:
                errors.append(
                    f"registry status mismatch for {object_ref}: "
                    f"snapshot={expected_status}, evidence_store={actual_status}"
                )

    if (
        completed.accepted_model
        and not snapshot.scientific_position.accepted_model_refs
    ):
        errors.append("accepted completed run has no accepted model reference")

    if errors:
        raise CurrentStateValidationError(errors)


def write_current_state(
    snapshot: CurrentStateSnapshot, path: Path | str
) -> None:
    target = Path(path)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(dump_current_state(snapshot), encoding="utf-8")
    temporary.replace(target)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the TCAD current-state snapshot"
    )
    parser.add_argument("command", choices=("validate", "refresh", "format"))
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument("--state", type=Path, default=Path("research/current.yaml"))
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    state_path = args.state
    if not state_path.is_absolute():
        state_path = workspace / state_path
    snapshot = load_current_state(state_path)

    if args.command == "refresh":
        snapshot = refresh_integrity(snapshot, workspace)
        write_current_state(snapshot, state_path)
    elif args.command == "format":
        write_current_state(snapshot, state_path)

    validate_current_state(snapshot, workspace)
    print(
        f"current state valid: {state_path} "
        f"({snapshot.source_integrity.runs_records} run records)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
