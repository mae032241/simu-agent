"""Portable, identity-neutral snapshots of active scientific Artifacts."""

from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import stat
import tempfile
from pathlib import Path
from typing import Annotated

from pydantic import Field, model_validator

from .schema.artifact import (
    ArtifactEnvelope,
    ArtifactRegistration,
    Confidentiality,
    ContentEncoding,
    LabelValue,
    MediaType,
)
from .schema.common import Identifier, SchemaModel, Sha256, canonical_sha256
from .schema.refs import ArtifactRef
from .service.scheduler_bindings import SchedulerNameNotFound


BUNDLE_SCHEMA = "scidiscovery.active-research-bundle.v1"
MANIFEST_NAME = "bundle.json"
_CONTROL_LABELS = {
    "artifact_id",
    "approval_id",
    "assignment_id",
    "execution_id",
    "instance_id",
    "proxy_id",
    "run_id",
    "session_id",
}


class ActiveBundleError(RuntimeError):
    """The portable scientific bundle is unsafe, incomplete, or inconsistent."""


class ActiveBundleNeed(SchemaModel):
    name: Identifier
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]


class ActiveBundleSelection(SchemaModel):
    bundle_name: Identifier
    instance_name: Identifier
    purpose: Annotated[str, Field(min_length=1, max_length=8192)]
    artifact_names: tuple[Identifier, ...]
    unresolved_inputs: tuple[ActiveBundleNeed, ...] = ()

    @model_validator(mode="after")
    def _validate_selection(self) -> ActiveBundleSelection:
        if not self.artifact_names:
            raise ValueError("active bundle selection requires at least one Artifact")
        if len(self.artifact_names) != len(set(self.artifact_names)):
            raise ValueError("active bundle Artifact names must be unique")
        names = tuple(item.name for item in self.unresolved_inputs)
        if len(names) != len(set(names)):
            raise ValueError("active bundle unresolved inputs must be unique")
        return self


class ActiveBundleInstance(SchemaModel):
    name: Identifier
    title: Annotated[str, Field(min_length=1, max_length=512)]
    objective: Annotated[str, Field(min_length=1, max_length=8192)]


class ActiveBundleContentRef(SchemaModel):
    """Identity-neutral description of scientific content outside the selection."""

    sha256: Sha256
    kind: Identifier
    schema_id: Identifier


class ActiveBundleEntry(SchemaModel):
    local_key: Identifier
    semantic_names: tuple[Identifier, ...] = ()
    payload_path: Annotated[str, Field(min_length=73, max_length=80)]
    sha256: Sha256
    size_bytes: Annotated[int, Field(ge=0)]
    kind: Identifier
    schema_id: Identifier
    payload_schema_version: Annotated[int, Field(ge=1)]
    media_type: MediaType
    labels: dict[Identifier, LabelValue] = Field(default_factory=dict)
    removed_label_keys: tuple[Identifier, ...] = ()
    confidentiality: Confidentiality = "project"
    content_encoding: ContentEncoding = "identity"
    parent_keys: tuple[Identifier, ...] = ()
    omitted_parent_refs: tuple[ActiveBundleContentRef, ...] = ()
    supersedes_key: Identifier | None = None
    omitted_supersedes_ref: ActiveBundleContentRef | None = None

    @model_validator(mode="after")
    def _validate_entry(self) -> ActiveBundleEntry:
        if self.payload_path != f"payloads/{self.sha256}":
            raise ValueError("active bundle payload path must match its SHA-256")
        if len(self.semantic_names) != len(set(self.semantic_names)):
            raise ValueError("active bundle semantic names must be unique")
        if len(self.parent_keys) != len(set(self.parent_keys)):
            raise ValueError("active bundle parent keys must be unique")
        omitted_parents = tuple(
            (item.sha256, item.kind, item.schema_id)
            for item in self.omitted_parent_refs
        )
        if len(omitted_parents) != len(set(omitted_parents)):
            raise ValueError("omitted parent content references must be unique")
        if len(self.removed_label_keys) != len(set(self.removed_label_keys)):
            raise ValueError("removed label keys must be unique")
        return self


class ActiveResearchBundle(SchemaModel):
    bundle_schema: str = BUNDLE_SCHEMA
    bundle_name: Identifier
    purpose: Annotated[str, Field(min_length=1, max_length=8192)]
    source_instance: ActiveBundleInstance
    entries: tuple[ActiveBundleEntry, ...]
    unresolved_inputs: tuple[ActiveBundleNeed, ...] = ()

    @model_validator(mode="after")
    def _validate_graph(self) -> ActiveResearchBundle:
        if self.bundle_schema != BUNDLE_SCHEMA:
            raise ValueError("unsupported active research bundle schema")
        if not self.entries:
            raise ValueError("active research bundle has no entries")
        keys = tuple(item.local_key for item in self.entries)
        if len(keys) != len(set(keys)):
            raise ValueError("active research bundle entry keys must be unique")
        semantic_names = tuple(
            name for item in self.entries for name in item.semantic_names
        )
        if not semantic_names:
            raise ValueError("active research bundle has no bound semantic Artifacts")
        if len(semantic_names) != len(set(semantic_names)):
            raise ValueError("active research bundle semantic names must be unique")
        seen: set[str] = set()
        for entry in self.entries:
            references = (*entry.parent_keys, entry.supersedes_key)
            for reference in references:
                if reference is not None and reference not in seen:
                    raise ValueError(
                        "active bundle entries must use topological reference order"
                    )
            seen.add(entry.local_key)
        return self


def load_active_bundle_selection(path: Path | str) -> ActiveBundleSelection:
    source = _regular_file(path, label="active bundle selection")
    return ActiveBundleSelection.model_validate_json(source.read_bytes(), strict=True)


def export_active_research_bundle(
    *,
    state_root: Path | str,
    selection: ActiveBundleSelection,
    output: Path | str,
) -> dict[str, object]:
    """Export selected semantic Artifacts plus their immutable provenance closure."""

    if not isinstance(selection, ActiveBundleSelection):
        raise TypeError("selection must be ActiveBundleSelection")
    state = Path(state_root).expanduser().resolve(strict=True)
    destination = Path(output).expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise ActiveBundleError(f"active bundle output already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)

    scheduler = _read_only_connection(
        state / "database" / "scheduler-bindings.sqlite3"
    )
    artifacts = _read_only_connection(
        state / "database" / "artifact_agent.sqlite3"
    )
    try:
        instance_row = scheduler.execute(
            "SELECT * FROM scheduler_instances WHERE name = ?",
            (selection.instance_name,),
        ).fetchone()
        if instance_row is None:
            raise ActiveBundleError(
                f"unknown source ResearchInstance: {selection.instance_name}"
            )
        if instance_row["state"] != "active":
            raise ActiveBundleError("source ResearchInstance is not active")
        instance_id = str(instance_row["instance_id"])
        selected: list[tuple[str, ArtifactRef]] = []
        for name in selection.artifact_names:
            row = scheduler.execute(
                """
                SELECT object_id FROM scheduler_bindings
                WHERE instance = ? AND namespace = 'artifact' AND name = ?
                """,
                (instance_id, name),
            ).fetchone()
            if row is None:
                raise ActiveBundleError(f"unknown selected Artifact name: {name}")
            envelope = _load_envelope(artifacts, str(row["object_id"]))
            selected.append((name, envelope.ref))

        envelopes = {
            reference.artifact_id: _load_envelope(artifacts, reference.artifact_id)
            for _, reference in selected
        }
        for _, reference in selected:
            if envelopes[reference.artifact_id].ref != reference:
                raise ActiveBundleError("Artifact reference metadata is inconsistent")

        order: list[str] = []
        active: set[str] = set()
        completed: set[str] = set()

        def visit_selected(artifact_id: str) -> None:
            if artifact_id in completed:
                return
            if artifact_id in active:
                raise ActiveBundleError("selected Artifact graph contains a cycle")
            active.add(artifact_id)
            envelope = envelopes[artifact_id]
            for reference in envelope.parent_refs:
                if reference.artifact_id in envelopes:
                    visit_selected(reference.artifact_id)
            if (
                envelope.supersedes_ref is not None
                and envelope.supersedes_ref.artifact_id in envelopes
            ):
                visit_selected(envelope.supersedes_ref.artifact_id)
            active.remove(artifact_id)
            completed.add(artifact_id)
            order.append(artifact_id)

        for _, reference in selected:
            visit_selected(reference.artifact_id)

        keys = {
            artifact_id: f"entry_{position:04d}"
            for position, artifact_id in enumerate(order, start=1)
        }
        names_by_artifact: dict[str, list[str]] = {}
        for name, reference in selected:
            names_by_artifact.setdefault(reference.artifact_id, []).append(name)

        entries: list[ActiveBundleEntry] = []
        payloads: dict[str, bytes] = {}
        for artifact_id in order:
            envelope = envelopes[artifact_id]
            content = _read_cas_payload(state, envelope)
            payloads.setdefault(envelope.sha256, content)
            labels, removed = _portable_labels(dict(envelope.labels))
            entries.append(
                ActiveBundleEntry(
                    local_key=keys[artifact_id],
                    semantic_names=tuple(names_by_artifact.get(artifact_id, ())),
                    payload_path=f"payloads/{envelope.sha256}",
                    sha256=envelope.sha256,
                    size_bytes=envelope.size_bytes,
                    kind=envelope.kind,
                    schema_id=envelope.schema_id,
                    payload_schema_version=envelope.payload_schema_version,
                    media_type=envelope.media_type,
                    labels=labels,
                    removed_label_keys=removed,
                    confidentiality=envelope.confidentiality,
                    content_encoding=envelope.content_encoding,
                    parent_keys=tuple(
                        keys[value.artifact_id]
                        for value in envelope.parent_refs
                        if value.artifact_id in keys
                    ),
                    omitted_parent_refs=tuple(
                        _portable_content_ref(value)
                        for value in envelope.parent_refs
                        if value.artifact_id not in keys
                    ),
                    supersedes_key=(
                        keys[envelope.supersedes_ref.artifact_id]
                        if envelope.supersedes_ref is not None
                        and envelope.supersedes_ref.artifact_id in keys
                        else None
                    ),
                    omitted_supersedes_ref=(
                        _portable_content_ref(envelope.supersedes_ref)
                        if envelope.supersedes_ref is not None
                        and envelope.supersedes_ref.artifact_id not in keys
                        else None
                    ),
                )
            )

        manifest = ActiveResearchBundle(
            bundle_name=selection.bundle_name,
            purpose=selection.purpose,
            source_instance=ActiveBundleInstance(
                name=str(instance_row["name"]),
                title=str(instance_row["title"]),
                objective=str(instance_row["objective"]),
            ),
            entries=tuple(entries),
            unresolved_inputs=selection.unresolved_inputs,
        )
    finally:
        artifacts.close()
        scheduler.close()

    stage = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent)
    )
    try:
        payload_root = stage / "payloads"
        payload_root.mkdir(mode=0o700)
        for digest, content in sorted(payloads.items()):
            (payload_root / digest).write_bytes(content)
        (stage / MANIFEST_NAME).write_bytes(manifest.canonical_json())
        verify_active_research_bundle(stage)
        os.replace(stage, destination)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return _bundle_summary(manifest, destination)


def verify_active_research_bundle(path: Path | str) -> ActiveResearchBundle:
    root = _bundle_root(path)
    manifest_path = _regular_file(root / MANIFEST_NAME, label="bundle manifest")
    raw = manifest_path.read_bytes()
    manifest = ActiveResearchBundle.model_validate_json(raw, strict=True)
    if manifest.canonical_json() != raw:
        raise ActiveBundleError("active bundle manifest is not canonical JSON")

    expected_files = {MANIFEST_NAME}
    expected_payloads: dict[str, int] = {}
    for entry in manifest.entries:
        expected_files.add(entry.payload_path)
        previous = expected_payloads.setdefault(entry.sha256, entry.size_bytes)
        if previous != entry.size_bytes:
            raise ActiveBundleError("one payload digest has inconsistent sizes")
    observed_files: set[str] = set()
    for candidate in root.rglob("*"):
        metadata = os.lstat(candidate)
        if stat.S_ISLNK(metadata.st_mode):
            raise ActiveBundleError("active bundle must not contain symlinks")
        if stat.S_ISDIR(metadata.st_mode):
            continue
        if not stat.S_ISREG(metadata.st_mode):
            raise ActiveBundleError("active bundle contains a non-regular file")
        observed_files.add(candidate.relative_to(root).as_posix())
    if observed_files != expected_files:
        raise ActiveBundleError("active bundle contains missing or unexpected files")

    for digest, size_bytes in expected_payloads.items():
        payload = _regular_file(
            root / "payloads" / digest,
            label="active bundle payload",
        ).read_bytes()
        if len(payload) != size_bytes:
            raise ActiveBundleError(f"active bundle payload size mismatch: {digest}")
        if hashlib.sha256(payload).hexdigest() != digest:
            raise ActiveBundleError(f"active bundle payload hash mismatch: {digest}")
    return manifest


def import_active_research_bundle(
    *, runtime: object, instance_name: str, bundle_path: Path | str
) -> dict[str, object]:
    """Re-register scientific content with fresh target-control identities."""

    manifest = verify_active_research_bundle(bundle_path)
    root = _bundle_root(bundle_path)
    bindings = runtime.scheduler_bindings  # type: ignore[attr-defined]
    artifacts = runtime.artifacts  # type: ignore[attr-defined]
    actor = runtime.actor  # type: ignore[attr-defined]
    instance = bindings.select_instance(name=instance_name)
    bundle_digest = manifest.content_hash

    for entry in manifest.entries:
        for name in entry.semantic_names:
            fingerprint = _import_fingerprint(bundle_digest, entry.local_key, name)
            try:
                existing = bindings.get_binding(
                    instance=instance.instance_id,
                    namespace="artifact",
                    name=name,
                )
            except SchedulerNameNotFound:
                continue
            if existing.request_fingerprint != fingerprint:
                raise ActiveBundleError(
                    f"target semantic name is already bound differently: {name}"
                )

    imported: dict[str, ArtifactRef] = {}
    bound_names: list[str] = []
    for entry in manifest.entries:
        content = (root / entry.payload_path).read_bytes()
        labels = dict(entry.labels)
        labels["portable_bundle"] = manifest.bundle_name
        labels["portable_entry"] = entry.local_key
        envelope = artifacts.register(
            content,
            ArtifactRegistration(
                kind=entry.kind,
                schema_id=entry.schema_id,
                payload_schema_version=entry.payload_schema_version,
                media_type=entry.media_type,
                creator=actor,
                parent_refs=tuple(imported[key] for key in entry.parent_keys),
                supersedes_ref=(
                    imported[entry.supersedes_key]
                    if entry.supersedes_key is not None
                    else None
                ),
                labels=labels,
                confidentiality=entry.confidentiality,
                content_encoding=entry.content_encoding,
            ),
            idempotency_key=(
                f"active-bundle:{bundle_digest}:{entry.local_key}"
            ),
        )
        imported[entry.local_key] = envelope.ref
        for name in entry.semantic_names:
            bindings.bind(
                instance=instance.instance_id,
                namespace="artifact",
                name=name,
                object_id=envelope.artifact_id,
                request_fingerprint=_import_fingerprint(
                    bundle_digest, entry.local_key, name
                ),
            )
            bound_names.append(name)
    return {
        "bundle_name": manifest.bundle_name,
        "bundle_sha256": bundle_digest,
        "target_instance": instance.name,
        "registered_entries": len(imported),
        "bound_artifacts": tuple(bound_names),
        "unresolved_inputs": tuple(
            {"name": item.name, "rationale": item.rationale}
            for item in manifest.unresolved_inputs
        ),
    }


def _read_only_connection(path: Path) -> sqlite3.Connection:
    database = _regular_file(path, label="control database")
    connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def _load_envelope(
    connection: sqlite3.Connection, artifact_id: str
) -> ArtifactEnvelope:
    row = connection.execute(
        "SELECT * FROM artifact_envelopes WHERE artifact_id = ?", (artifact_id,)
    ).fetchone()
    if row is None:
        raise ActiveBundleError("Artifact envelope is missing from the registry")
    raw_value = row["envelope_json"]
    raw = bytes(raw_value) if not isinstance(raw_value, str) else raw_value.encode()
    envelope = ArtifactEnvelope.model_validate_json(raw, strict=True)
    if envelope.canonical_json() != raw:
        raise ActiveBundleError("Artifact envelope is not canonical JSON")
    if (
        envelope.artifact_id != row["artifact_id"]
        or envelope.sha256 != row["payload_sha256"]
        or envelope.size_bytes != row["size_bytes"]
        or envelope.kind != row["kind"]
        or envelope.schema_id != row["schema_id"]
        or envelope.payload_schema_version != row["payload_schema_version"]
        or envelope.media_type != row["media_type"]
        or envelope.created_at != row["created_at"]
        or hashlib.sha256(raw).hexdigest() != row["envelope_sha256"]
    ):
        raise ActiveBundleError("Artifact registry columns disagree with the envelope")
    return envelope


def _read_cas_payload(state: Path, envelope: ArtifactEnvelope) -> bytes:
    path = state / "artifacts" / "sha256" / envelope.sha256[:2] / envelope.sha256[2:]
    content = _regular_file(path, label="CAS payload").read_bytes()
    if len(content) != envelope.size_bytes:
        raise ActiveBundleError("CAS payload size does not match its envelope")
    if hashlib.sha256(content).hexdigest() != envelope.sha256:
        raise ActiveBundleError("CAS payload hash does not match its envelope")
    return content


def _portable_labels(labels: dict[str, str]) -> tuple[dict[str, str], tuple[str, ...]]:
    portable: dict[str, str] = {}
    removed: list[str] = []
    for key, value in sorted(labels.items()):
        if key in _CONTROL_LABELS or key.endswith("_id"):
            removed.append(key)
        else:
            portable[key] = value
    return portable, tuple(removed)


def _portable_content_ref(reference: ArtifactRef) -> ActiveBundleContentRef:
    return ActiveBundleContentRef(
        sha256=reference.sha256,
        kind=reference.kind,
        schema_id=reference.schema_id,
    )


def _bundle_root(path: Path | str) -> Path:
    source = Path(path).expanduser().absolute()
    try:
        metadata = os.lstat(source)
    except FileNotFoundError as error:
        raise ActiveBundleError("active research bundle does not exist") from error
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise ActiveBundleError("active research bundle must be a non-symlink directory")
    return source.resolve(strict=True)


def _regular_file(path: Path | str, *, label: str) -> Path:
    source = Path(path).expanduser().absolute()
    try:
        metadata = os.lstat(source)
    except FileNotFoundError as error:
        raise ActiveBundleError(f"{label} does not exist: {source}") from error
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ActiveBundleError(f"{label} must be a regular non-symlink file")
    return source.resolve(strict=True)


def _import_fingerprint(bundle_digest: str, local_key: str, name: str) -> str:
    return canonical_sha256(
        {
            "operation": "active_research_bundle.import",
            "bundle_sha256": bundle_digest,
            "entry": local_key,
            "semantic_name": name,
        }
    )


def _bundle_summary(
    manifest: ActiveResearchBundle, destination: Path
) -> dict[str, object]:
    return {
        "bundle_name": manifest.bundle_name,
        "bundle_sha256": manifest.content_hash,
        "path": str(destination),
        "entries": len(manifest.entries),
        "bound_artifacts": sum(
            len(entry.semantic_names) for entry in manifest.entries
        ),
        "payload_bytes": sum(
            entry.size_bytes
            for entry in {
                value.sha256: value for value in manifest.entries
            }.values()
        ),
        "unresolved_inputs": tuple(
            {"name": item.name, "rationale": item.rationale}
            for item in manifest.unresolved_inputs
        ),
    }


__all__ = [
    "ActiveBundleEntry",
    "ActiveBundleError",
    "ActiveBundleInstance",
    "ActiveBundleContentRef",
    "ActiveBundleNeed",
    "ActiveBundleSelection",
    "ActiveResearchBundle",
    "export_active_research_bundle",
    "import_active_research_bundle",
    "load_active_bundle_selection",
    "verify_active_research_bundle",
]
