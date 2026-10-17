"""Pure scientific implementation compilation, without services or execution."""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Literal

from pydantic import Field, field_validator

from scidiscovery.artifact_agent.schema.common import canonical_json

from .execution_control import PROCESS_LOG_PATH, SolverCapabilitySnapshot, StrictModel
from .project_packager import (
    DeckProjectDraft, NativeExecutionPackage, NativeResolvedProjectInput,
    ScientificDeckImplementation,
)


class TCADImplementation(ScientificDeckImplementation):
    """The existing direct-solver author form, without control-owned fields."""

    solver_kind: Literal["sprocess", "sdevice"]


class TCADCompilationConfig(StrictModel):
    """Optional operator input; a trusted host separately verifies this file."""

    capability_snapshot_path: str = Field(min_length=1, max_length=4096)

    @field_validator("capability_snapshot_path")
    @classmethod
    def _absolute_snapshot(cls, value):
        path = PurePosixPath(value)
        if (not path.is_absolute() or path.root != "/" or str(path) != value or "\\" in value
                or "\x00" in value or any(part == ".." for part in path.parts)):
            raise ValueError("compilation capability must name an absolute operator file")
        return value


def compile_execution_project(
    authored: ScientificDeckImplementation, capability: SolverCapabilitySnapshot,
) -> DeckProjectDraft:
    """Supply the same control capture fields for both native and legacy tools."""
    authored = ScientificDeckImplementation.model_validate_json(
        canonical_json(authored.model_dump(mode="json")), strict=True)
    if authored.solver_kind is None or capability.solver_kind != authored.solver_kind:
        raise ValueError("implementation solver differs from the selected capability")
    values = authored.model_dump(mode="json")
    values.update(tool_profile=capability.profile_id, capability_sha256=capability.capability_sha256,
        collect_generated_outputs=True, expected_outputs=[{
            "name": "process_log", "capture": "process_log", "relative_path": PROCESS_LOG_PATH,
            "media_type": "text/plain", "max_bytes": authored.resource_limits.max_output_bytes,
        }])
    return DeckProjectDraft.model_validate_json(canonical_json(values), strict=True)


def compile_native_implementation(
    authored: ScientificDeckImplementation, *, capability: SolverCapabilitySnapshot,
    resolved_inputs: tuple[NativeResolvedProjectInput, ...],
) -> bytes:
    """Compile already resolved host inputs; this confers no execution authority."""
    authored = TCADImplementation.model_validate_json(
        canonical_json(authored.model_dump(mode="json")), strict=True)
    package = NativeExecutionPackage(project=compile_execution_project(authored, capability),
        capability=capability, resolved_inputs=resolved_inputs)
    raw = canonical_json(package.model_dump(mode="json"))
    package = NativeExecutionPackage.model_validate_json(raw, strict=True)
    total = sum(len(item.content.encode("utf-8")) for item in package.project.files)
    total += sum(item.size_bytes for item in package.resolved_inputs)
    if total > package.project.resource_limits.max_storage_bytes:
        raise ValueError("declared inputs exceed task storage budget")
    return raw
