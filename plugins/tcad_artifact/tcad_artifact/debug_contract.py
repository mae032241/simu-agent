"""TCAD 开发调试的领域合同；不依赖任何控制面任务实体。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from scidiscovery.artifact_agent.schema.execution import LocalFileDescriptor
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.artifact_agent.service.execution_collection import CollectionContext


class TCADDebugError(RuntimeError):
    pass


@dataclass(frozen=True)
class TCADDebugSource:
    source_name: str
    artifact_ref: ArtifactRef
    media_type: str
    content: bytes


@dataclass(frozen=True)
class PreparedTCADDebugRun:
    submission: LocalFileDescriptor
    wall_time_seconds: int


@dataclass(frozen=True)
class CollectedTCADDebugFile:
    name: str
    media_type: str
    content: bytes


@dataclass(frozen=True)
class TCADSourceDiagnostic:
    source_relative_path: str | None
    reported_line: int | None
    line_basis: str
    procedure: str | None
    procedure_line: int | None
    message: str
    command_excerpt: str | None


@dataclass(frozen=True)
class CollectedTCADDebugRun:
    terminal_state: str
    exit_code: int
    diagnostic_layer: str
    summary: str
    log_excerpt: str
    files: tuple[CollectedTCADDebugFile, ...]
    source_diagnostic: TCADSourceDiagnostic | None = None
    timing: dict[str, object] | None = None


class TCADDevelopmentDebugAdapter(Protocol):
    def prepare(
        self,
        *,
        project: bytes,
        capability: bytes,
        sources: tuple[TCADDebugSource, ...],
        exchange_directory: Path,
        mode: str,
    ) -> PreparedTCADDebugRun: ...

    def clamp_wall_time(
        self, prepared: PreparedTCADDebugRun, *, wall_time_seconds: int
    ) -> PreparedTCADDebugRun: ...

    def prepare_submission(
        self, prepared: PreparedTCADDebugRun
    ) -> LocalFileDescriptor: ...

    def submit(self, submission: LocalFileDescriptor) -> tuple[str, str]: ...

    def status(self, external_run_id: str) -> str: ...

    def cancel(self, external_run_id: str) -> str: ...

    def collect(self, external_run_id: str) -> CollectedTCADDebugRun: ...

    def collect_with_budget(self, external_run_id: str, *, context: CollectionContext) -> CollectedTCADDebugRun: ...


__all__ = [
    "CollectedTCADDebugFile",
    "CollectedTCADDebugRun",
    "PreparedTCADDebugRun",
    "TCADDebugError",
    "TCADDebugSource",
    "TCADDevelopmentDebugAdapter",
    "TCADSourceDiagnostic",
]
