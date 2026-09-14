"""Safe project-local file and user-text intake into immutable Artifact storage."""

from __future__ import annotations

import mimetypes
import os
import stat
import uuid
from dataclasses import dataclass
from pathlib import Path

from ..schema.artifact import ArtifactRegistration
from ..schema.refs import ActorRef, ArtifactRef
from .artifacts import ArtifactService


USER_TEXT_MAX_LENGTH = 8192
USER_TEXT_MEDIA_TYPE = "text/plain; charset=utf-8"
USER_TEXT_SOURCE_ORIGIN = "user_via_scheduler"


class IntakeError(RuntimeError):
    pass


class UnsafeSourcePathError(IntakeError):
    pass


@dataclass(frozen=True)
class PreparedIntakeFile:
    relative_path: str
    media_type: str
    content: bytes


class SecureIntakeService:
    """Resolve one declared local path and let control assign its identity."""

    def __init__(
        self,
        *,
        project_root: Path | str,
        artifact_service: ArtifactService,
        creator: ActorRef,
    ) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        if not self.project_root.is_dir():
            raise ValueError("project_root must be an existing directory")
        self.artifacts = artifact_service
        self.creator = creator

    def ingest_file(
        self, *, relative_path: str, media_type: str | None = None
    ) -> ArtifactRef:
        return self.ingest_prepared(
            self.prepare_file(relative_path=relative_path, media_type=media_type)
        )

    def prepare_file(
        self, *, relative_path: str, media_type: str | None = None
    ) -> PreparedIntakeFile:
        source = self._resolve_regular_file(relative_path)
        content = source.read_bytes()
        detected = media_type or mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        relative = source.relative_to(self.project_root).as_posix()
        return PreparedIntakeFile(
            relative_path=relative,
            media_type=detected,
            content=content,
        )

    def ingest_prepared(self, source: PreparedIntakeFile) -> ArtifactRef:
        if not isinstance(source, PreparedIntakeFile):
            raise TypeError("source must be a PreparedIntakeFile")
        artifact_id = f"art_{uuid.uuid4().hex}"
        return self.artifacts.register(
            source.content,
            ArtifactRegistration(
                artifact_id=artifact_id,
                kind="source_file",
                schema_id="opaque",
                payload_schema_version=1,
                media_type=source.media_type,
                creator=self.creator,
                labels={"source_path": source.relative_path},
                confidentiality="project",
            ),
            idempotency_key=f"intake:{artifact_id}",
        ).ref

    def ingest_text(self, *, content: bytes) -> ArtifactRef:
        """Register the original UTF-8 bytes validated by the Root input model."""
        artifact_id = f"art_{uuid.uuid4().hex}"
        return self.artifacts.register(
            content,
            ArtifactRegistration(
                artifact_id=artifact_id,
                kind="source_text",
                schema_id="opaque",
                payload_schema_version=1,
                media_type=USER_TEXT_MEDIA_TYPE,
                creator=self.creator,
                labels={"source_origin": USER_TEXT_SOURCE_ORIGIN},
                confidentiality="project",
            ),
            idempotency_key=f"intake:{artifact_id}",
        ).ref

    def _resolve_regular_file(self, relative_path: str) -> Path:
        candidate = Path(relative_path)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise UnsafeSourcePathError("source path must be project-relative")
        source = self.project_root / candidate
        try:
            metadata = os.lstat(source)
            resolved = source.resolve(strict=True)
        except FileNotFoundError as error:
            raise UnsafeSourcePathError("source file does not exist") from error
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise UnsafeSourcePathError("source must be a regular non-symlink file")
        try:
            resolved.relative_to(self.project_root)
        except ValueError as error:
            raise UnsafeSourcePathError("source resolves outside project root") from error
        return resolved


__all__ = [
    "IntakeError",
    "PreparedIntakeFile",
    "SecureIntakeService",
    "UnsafeSourcePathError",
    "USER_TEXT_MAX_LENGTH",
    "USER_TEXT_MEDIA_TYPE",
    "USER_TEXT_SOURCE_ORIGIN",
]
