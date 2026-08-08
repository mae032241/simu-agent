"""Deterministically package a reviewed textual TCAD project for execution."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, ValidationError, field_validator, model_validator

from .execution_control import (
    ArchiveEntry,
    ExpectedOutput,
    FileDescriptor,
    ResourceLimits,
    StrictModel,
    TCADJobSpec,
)


MAX_PROJECT_BYTES = 64 * 1024 * 1024
WORKBENCH_TOKEN = re.compile(r"@[A-Za-z_][A-Za-z0-9_.:-]*@")
SHELL_ENTRYPOINT_MARKERS = (
    "#!/bin/sh",
    "#!/usr/bin/env sh",
    "#!/bin/bash",
    "#!/usr/bin/env bash",
    "set -e",
    "set -u",
    "nohup ",
)


def _safe_relative_path(value: str) -> str:
    if value.startswith("/") or "\\" in value or any(
        part in {"", ".", ".."} for part in value.split("/")
    ):
        raise ValueError("unsafe relative path")
    return value


def _direct_solver_kind(tool_profile: str) -> str | None:
    normalized = tool_profile.lower()
    if "sprocess" in normalized:
        return "sprocess"
    if "sdevice" in normalized:
        return "sdevice"
    return None


class DeckFile(StrictModel):
    relative_path: str = Field(min_length=1, max_length=1024)
    content: str = Field(max_length=8 * 1024 * 1024)

    _safe_path = field_validator("relative_path")(_safe_relative_path)


class ProjectExpectedOutput(StrictModel):
    name: str = Field(min_length=1, max_length=256)
    relative_path: str = Field(min_length=1, max_length=1024)
    media_type: str = Field(min_length=3, max_length=255)
    required: bool = True
    max_bytes: int = Field(ge=1, le=2**50)

    _safe_path = field_validator("relative_path")(_safe_relative_path)


class ProjectResourceLimits(StrictModel):
    wall_time_seconds: int = Field(ge=1, le=604800)
    cpu_time_seconds: int = Field(ge=1, le=604800)
    max_memory_bytes: int = Field(ge=1, le=2**50)
    max_output_bytes: int = Field(ge=1, le=2**50)
    max_processes: int = Field(ge=1, le=4096)


class ParameterBinding(StrictModel):
    name: str = Field(min_length=1, max_length=256)
    declared_value: str = Field(min_length=1, max_length=4096)
    unit: str = Field(min_length=1, max_length=128)
    relative_path: str = Field(min_length=1, max_length=1024)
    locator: str = Field(min_length=1, max_length=4096)
    evidence_class: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]*$",
    )
    evidence_source: str | None = Field(default=None, min_length=1, max_length=4096)
    evidence_locator: str | None = Field(default=None, min_length=1, max_length=4096)
    rationale: str | None = Field(default=None, min_length=1, max_length=4096)
    requirement_keys: tuple[str, ...] = Field(default=(), max_length=64)

    _safe_path = field_validator("relative_path")(_safe_relative_path)

    @model_validator(mode="after")
    def _complete_evidence(self) -> ParameterBinding:
        evidence = (
            self.evidence_class,
            self.evidence_source,
            self.evidence_locator,
            self.rationale,
        )
        if any(item is not None for item in evidence) and any(
            item is None for item in evidence
        ):
            raise ValueError("parameter evidence fields must be supplied together")
        if len(self.requirement_keys) != len(set(self.requirement_keys)):
            raise ValueError("parameter requirement_keys must be unique")
        return self


class RuntimeAssertion(StrictModel):
    description: str = Field(min_length=1, max_length=4096)
    expected_output_name: str = Field(min_length=1, max_length=256)


class RealizationRequirement(StrictModel):
    """One source-backed physical requirement and its exact deck realization."""

    requirement_key: str = Field(
        min_length=1,
        max_length=256,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]*$",
    )
    category: Literal[
        "geometry",
        "material",
        "doping",
        "physics",
        "contact_boundary",
        "initial_condition",
        "numerical_protocol",
        "observable",
    ]
    requirement: str = Field(min_length=1, max_length=4096)
    evidence_class: str = Field(min_length=1, max_length=128)
    evidence_source: str = Field(min_length=1, max_length=4096)
    evidence_locator: str = Field(min_length=1, max_length=4096)
    rationale: str = Field(min_length=1, max_length=4096)
    implementation_status: Literal["implemented", "unsupported"]
    relative_path: str | None = Field(default=None, min_length=1, max_length=1024)
    locator: str | None = Field(default=None, min_length=1, max_length=4096)
    verification_mode: Literal["static_review", "runtime_log", "runtime_output"]
    expected_output_name: str | None = Field(
        default=None, min_length=1, max_length=256
    )

    @field_validator("relative_path")
    @classmethod
    def _safe_optional_path(cls, value: str | None) -> str | None:
        return None if value is None else _safe_relative_path(value)

    @model_validator(mode="after")
    def _implementation_is_explicit(self) -> RealizationRequirement:
        if self.implementation_status == "implemented":
            if self.relative_path is None or self.locator is None:
                raise ValueError(
                    "implemented requirement needs relative_path and locator"
                )
        elif self.relative_path is not None or self.locator is not None:
            raise ValueError("unsupported requirement cannot claim a deck location")
        if self.verification_mode in {"runtime_log", "runtime_output"}:
            if self.expected_output_name is None:
                raise ValueError(
                    "runtime verification requires expected_output_name"
                )
        elif self.expected_output_name is not None:
            raise ValueError(
                "static verification cannot declare expected_output_name"
            )
        if (
            self.implementation_status == "unsupported"
            and self.verification_mode != "static_review"
        ):
            raise ValueError("unsupported requirement must use static_review")
        return self


class DeckProjectDraft(StrictModel):
    schema_version: Annotated[int, Field(ge=1, le=1)] = 1
    tool_profile: str = Field(
        min_length=1,
        max_length=256,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]*$",
    )
    files: tuple[DeckFile, ...] = Field(min_length=1, max_length=4096)
    entrypoint: str = Field(min_length=1, max_length=1024)
    arguments: tuple[str, ...] = Field(default=(), max_length=256)
    expected_outputs: tuple[ProjectExpectedOutput, ...] = Field(max_length=4096)
    parameter_bindings: tuple[ParameterBinding, ...] = Field(default=(), max_length=4096)
    runtime_assertions: tuple[RuntimeAssertion, ...] = Field(default=(), max_length=4096)
    realization_manifest: tuple[RealizationRequirement, ...] = Field(
        default=(), max_length=4096
    )
    resource_limits: ProjectResourceLimits

    _safe_entrypoint = field_validator("entrypoint")(_safe_relative_path)

    @model_validator(mode="after")
    def _consistent_project(self) -> DeckProjectDraft:
        file_paths = tuple(item.relative_path for item in self.files)
        if len(file_paths) != len(set(file_paths)):
            raise ValueError("project file paths must be unique")
        if self.entrypoint not in set(file_paths):
            raise ValueError("entrypoint must name one project file")
        if sum(len(item.content.encode("utf-8")) for item in self.files) > MAX_PROJECT_BYTES:
            raise ValueError("project source exceeds total byte limit")

        output_names = tuple(item.name for item in self.expected_outputs)
        output_paths = tuple(item.relative_path for item in self.expected_outputs)
        if len(output_names) != len(set(output_names)) or len(output_paths) != len(set(output_paths)):
            raise ValueError("expected output names and paths must be unique")
        if set(file_paths).intersection(output_paths):
            raise ValueError("expected output must not overwrite a project input")

        binding_names = tuple(item.name for item in self.parameter_bindings)
        if len(binding_names) != len(set(binding_names)):
            raise ValueError("parameter binding names must be unique")
        contents = {item.relative_path: item.content for item in self.files}
        solver_kind = _direct_solver_kind(self.tool_profile)
        if solver_kind is not None:
            if Path(self.entrypoint).suffix.lower() != ".cmd":
                raise ValueError(
                    f"direct {solver_kind} entrypoint must be a .cmd solver deck"
                )
            entrypoint_content = contents[self.entrypoint]
            if any(
                marker in entrypoint_content for marker in SHELL_ENTRYPOINT_MARKERS
            ):
                raise ValueError(
                    f"direct {solver_kind} entrypoint contains shell-runner syntax"
                )
            if any(value in {"submit", "worker", "status"} for value in self.arguments):
                raise ValueError(
                    f"direct {solver_kind} arguments contain scheduler commands"
                )
            unresolved = {
                token
                for content in contents.values()
                for token in WORKBENCH_TOKEN.findall(content)
            }
            if unresolved:
                raise ValueError(
                    "standalone direct-solver project contains unresolved "
                    "Workbench tokens: " + ", ".join(sorted(unresolved))
                )
        for binding in self.parameter_bindings:
            if binding.relative_path not in contents:
                raise ValueError("parameter binding file must exist")
            if binding.locator not in contents[binding.relative_path]:
                raise ValueError("parameter binding locator is absent from its file")

        requirement_keys = tuple(
            item.requirement_key for item in self.realization_manifest
        )
        if len(requirement_keys) != len(set(requirement_keys)):
            raise ValueError("realization requirement keys must be unique")
        known_requirements = set(requirement_keys)
        for requirement in self.realization_manifest:
            if requirement.implementation_status == "implemented":
                assert requirement.relative_path is not None
                assert requirement.locator is not None
                try:
                    source = contents[requirement.relative_path]
                except KeyError as error:
                    raise ValueError(
                        "realization requirement file must exist"
                    ) from error
                if requirement.locator not in source:
                    raise ValueError(
                        "realization requirement locator is absent from its file"
                    )
            if (
                requirement.expected_output_name is not None
                and requirement.expected_output_name not in set(output_names)
            ):
                raise ValueError(
                    "realization requirement references an unknown expected output"
                )
        for binding in self.parameter_bindings:
            if not set(binding.requirement_keys).issubset(known_requirements):
                raise ValueError(
                    "parameter binding references an unknown realization requirement"
                )

        output_name_set = set(output_names)
        if any(
            item.expected_output_name not in output_name_set
            for item in self.runtime_assertions
        ):
            raise ValueError("runtime assertion must reference an expected output")
        if any("\x00" in value or len(value) > 4096 for value in self.arguments):
            raise ValueError("project argument is invalid")
        return self


class DeckRequirementReview(StrictModel):
    requirement_key: str = Field(
        min_length=1,
        max_length=256,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]*$",
    )
    status: Literal["pass", "fail", "unknown"]
    rationale: str = Field(min_length=1, max_length=4096)


class DeckReviewFinding(StrictModel):
    finding_key: str = Field(
        min_length=1,
        max_length=256,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]*$",
    )
    severity: Literal["blocker", "major", "minor", "note"]
    category: str = Field(min_length=1, max_length=128)
    summary: str = Field(min_length=1, max_length=4096)
    relative_path: str | None = Field(default=None, min_length=1, max_length=1024)
    locator: str | None = Field(default=None, min_length=1, max_length=4096)
    required_action: str | None = Field(default=None, min_length=1, max_length=4096)

    @field_validator("relative_path")
    @classmethod
    def _safe_optional_path(cls, value: str | None) -> str | None:
        return None if value is None else _safe_relative_path(value)


class DeckReviewReport(StrictModel):
    """Independent physical and implementation review of one complete project."""

    verdict: Literal["pass", "revise", "blocked"]
    summary: str = Field(min_length=1, max_length=4096)
    rationale: str = Field(min_length=1, max_length=8192)
    physical_fidelity: Literal["pass", "fail", "unknown"]
    implementation_fidelity: Literal["pass", "fail", "unknown"]
    syntax_fidelity: Literal["pass", "fail", "unknown"]
    numerical_protocol_fidelity: Literal["pass", "fail", "unknown"]
    requirement_reviews: tuple[DeckRequirementReview, ...] = Field(
        min_length=1, max_length=4096
    )
    findings: tuple[DeckReviewFinding, ...] = Field(default=(), max_length=256)
    undeclared_defaults: tuple[str, ...] = Field(default=(), max_length=128)
    unsupported_constructs: tuple[str, ...] = Field(default=(), max_length=128)
    missing_inputs: tuple[str, ...] = Field(default=(), max_length=128)
    execution_ready: bool
    next_actions: tuple[str, ...] = Field(default=(), max_length=64)

    @model_validator(mode="after")
    def _verdict_matches_review(self) -> DeckReviewReport:
        keys = tuple(item.requirement_key for item in self.requirement_reviews)
        if len(keys) != len(set(keys)):
            raise ValueError("deck requirement reviews must be unique")
        dimensions = {
            self.physical_fidelity,
            self.implementation_fidelity,
            self.syntax_fidelity,
            self.numerical_protocol_fidelity,
        }
        requirement_statuses = {item.status for item in self.requirement_reviews}
        blocking_finding = any(
            item.severity in {"blocker", "major"} for item in self.findings
        )
        clean = (
            dimensions == {"pass"}
            and requirement_statuses == {"pass"}
            and not blocking_finding
            and not self.undeclared_defaults
            and not self.unsupported_constructs
            and not self.missing_inputs
        )
        if self.verdict == "pass":
            if not clean or not self.execution_ready:
                raise ValueError(
                    "passing deck review requires complete clean coverage and execution_ready"
                )
        elif self.execution_ready:
            raise ValueError("non-passing deck review cannot be execution_ready")
        return self


class ReviewedDeckPackage(StrictModel):
    """One exact project paired with its passing independent review."""

    schema_version: Annotated[int, Field(ge=1, le=1)] = 1
    project: DeckProjectDraft
    review: DeckReviewReport

    @model_validator(mode="after")
    def _review_qualifies_project(self) -> ReviewedDeckPackage:
        validate_deck_review_against_project(self.project, self.review)
        if self.review.verdict != "pass" or not self.review.execution_ready:
            raise ValueError("reviewed deck package requires a passing execution-ready review")
        return self


class RuntimeOutputRecord(StrictModel):
    name: str = Field(min_length=1, max_length=256)
    relative_path: str = Field(min_length=1, max_length=1024)
    media_type: str = Field(min_length=3, max_length=255)
    sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0, le=2**50)

    _safe_path = field_validator("relative_path")(_safe_relative_path)


class TCADRuntimeManifest(StrictModel):
    started_at: str = Field(min_length=1, max_length=128)
    completed_at: str = Field(min_length=1, max_length=128)
    terminal_state: Literal["succeeded", "failed", "cancelled"]
    exit_code: int
    error: str = Field(max_length=8192)
    outputs: tuple[RuntimeOutputRecord, ...] = Field(max_length=4096)

    @model_validator(mode="after")
    def _outputs_are_unique(self) -> TCADRuntimeManifest:
        names = tuple(item.name for item in self.outputs)
        paths = tuple(item.relative_path for item in self.outputs)
        if len(names) != len(set(names)) or len(paths) != len(set(paths)):
            raise ValueError("runtime output names and paths must be unique")
        return self


class RuntimeContractCheck(StrictModel):
    check_key: str = Field(
        min_length=1,
        max_length=256,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]*$",
    )
    status: Literal["pass", "fail"]
    rationale: str = Field(min_length=1, max_length=4096)


class RuntimeAttestation(StrictModel):
    schema_version: Annotated[int, Field(ge=1, le=1)] = 1
    verdict: Literal["pass", "fail"]
    terminal_state: Literal["succeeded", "failed", "cancelled"]
    exit_code: int
    checks: tuple[RuntimeContractCheck, ...] = Field(min_length=1, max_length=8192)
    missing_required_outputs: tuple[str, ...] = Field(default=(), max_length=4096)
    scope: Literal["execution_contract_only"] = "execution_contract_only"
    rationale: str = Field(min_length=1, max_length=4096)

    @model_validator(mode="after")
    def _verdict_matches_checks(self) -> RuntimeAttestation:
        failed = any(item.status == "fail" for item in self.checks)
        if (self.verdict == "fail") != failed:
            raise ValueError("runtime attestation verdict differs from its checks")
        return self


class DeckFilePatch(StrictModel):
    operation: Literal["add", "replace", "delete"]
    relative_path: str = Field(min_length=1, max_length=1024)
    content: str | None = Field(default=None, max_length=8 * 1024 * 1024)

    _safe_path = field_validator("relative_path")(_safe_relative_path)

    @model_validator(mode="after")
    def _content_matches_operation(self) -> DeckFilePatch:
        if self.operation == "delete" and self.content is not None:
            raise ValueError("delete file patch must not contain content")
        if self.operation != "delete" and self.content is None:
            raise ValueError("add/replace file patch requires content")
        return self


class ParameterBindingPatch(StrictModel):
    operation: Literal["add", "replace", "delete"]
    name: str = Field(min_length=1, max_length=256)
    binding: ParameterBinding | None = None

    @model_validator(mode="after")
    def _binding_matches_operation(self) -> ParameterBindingPatch:
        if self.operation == "delete" and self.binding is not None:
            raise ValueError("delete binding patch must not contain a binding")
        if self.operation != "delete" and self.binding is None:
            raise ValueError("add/replace binding patch requires a binding")
        if self.binding is not None and self.binding.name != self.name:
            raise ValueError("binding patch name differs from binding name")
        return self


class DeckProjectPatch(StrictModel):
    """Bounded revision; fields outside files and parameter bindings stay frozen."""

    schema_version: Annotated[int, Field(ge=1, le=1)] = 1
    file_operations: tuple[DeckFilePatch, ...] = Field(default=(), max_length=4096)
    parameter_binding_operations: tuple[ParameterBindingPatch, ...] = Field(
        default=(), max_length=4096
    )
    replacement_realization_manifest: tuple[RealizationRequirement, ...] | None = Field(
        default=None, max_length=4096
    )
    rationale: str = Field(min_length=1, max_length=8192)

    @model_validator(mode="after")
    def _operations_are_unique(self) -> DeckProjectPatch:
        file_paths = tuple(item.relative_path for item in self.file_operations)
        binding_names = tuple(item.name for item in self.parameter_binding_operations)
        if len(file_paths) != len(set(file_paths)):
            raise ValueError("file patch paths must be unique")
        if len(binding_names) != len(set(binding_names)):
            raise ValueError("binding patch names must be unique")
        if (
            not file_paths
            and not binding_names
            and self.replacement_realization_manifest is None
        ):
            raise ValueError("deck patch must contain at least one operation")
        return self


@dataclass(frozen=True)
class PackagedTCADProject:
    project_sha256: str
    package_directory: Path
    archive: FileDescriptor
    job_spec_file: FileDescriptor
    job_spec: TCADJobSpec


class PackagerError(RuntimeError):
    pass


def apply_deck_project_patch(
    base: DeckProjectDraft, patch: DeckProjectPatch
) -> DeckProjectDraft:
    """Apply a bounded revision without allowing unrelated project-field changes."""

    files = {item.relative_path: item for item in base.files}
    file_order = [item.relative_path for item in base.files]
    for operation in patch.file_operations:
        exists = operation.relative_path in files
        if operation.operation == "add":
            if exists:
                raise PackagerError("file patch add target already exists")
            files[operation.relative_path] = DeckFile(
                relative_path=operation.relative_path, content=operation.content or ""
            )
            file_order.append(operation.relative_path)
        elif operation.operation == "replace":
            if not exists:
                raise PackagerError("file patch replace target does not exist")
            files[operation.relative_path] = DeckFile(
                relative_path=operation.relative_path, content=operation.content or ""
            )
        else:
            if not exists:
                raise PackagerError("file patch delete target does not exist")
            del files[operation.relative_path]
            file_order.remove(operation.relative_path)

    bindings = {item.name: item for item in base.parameter_bindings}
    binding_order = [item.name for item in base.parameter_bindings]
    for operation in patch.parameter_binding_operations:
        exists = operation.name in bindings
        if operation.operation == "add":
            if exists:
                raise PackagerError("binding patch add target already exists")
            assert operation.binding is not None
            bindings[operation.name] = operation.binding
            binding_order.append(operation.name)
        elif operation.operation == "replace":
            if not exists:
                raise PackagerError("binding patch replace target does not exist")
            assert operation.binding is not None
            bindings[operation.name] = operation.binding
        else:
            if not exists:
                raise PackagerError("binding patch delete target does not exist")
            del bindings[operation.name]
            binding_order.remove(operation.name)

    payload = base.model_dump(mode="python")
    payload["files"] = tuple(files[name] for name in file_order)
    payload["parameter_bindings"] = tuple(bindings[name] for name in binding_order)
    if patch.replacement_realization_manifest is not None:
        payload["realization_manifest"] = patch.replacement_realization_manifest
    return DeckProjectDraft.model_validate(payload, strict=True)


def deck_project_diff(
    base: DeckProjectDraft, revised: DeckProjectDraft
) -> dict[str, object]:
    base_files = {item.relative_path: item.content for item in base.files}
    revised_files = {item.relative_path: item.content for item in revised.files}
    paths = sorted(set(base_files) | set(revised_files))
    file_changes = []
    for path in paths:
        if path not in base_files:
            operation = "add"
        elif path not in revised_files:
            operation = "delete"
        elif base_files[path] != revised_files[path]:
            operation = "replace"
        else:
            continue
        file_changes.append({"relative_path": path, "operation": operation})
    base_bindings = {item.name: item.model_dump(mode="json") for item in base.parameter_bindings}
    revised_bindings = {
        item.name: item.model_dump(mode="json") for item in revised.parameter_bindings
    }
    binding_changes = [
        name
        for name in sorted(set(base_bindings) | set(revised_bindings))
        if base_bindings.get(name) != revised_bindings.get(name)
    ]
    base_requirements = {
        item.requirement_key: item.model_dump(mode="json")
        for item in base.realization_manifest
    }
    revised_requirements = {
        item.requirement_key: item.model_dump(mode="json")
        for item in revised.realization_manifest
    }
    realization_requirement_changes = [
        name
        for name in sorted(set(base_requirements) | set(revised_requirements))
        if base_requirements.get(name) != revised_requirements.get(name)
    ]
    frozen_fields = (
        "tool_profile",
        "entrypoint",
        "arguments",
        "expected_outputs",
        "runtime_assertions",
        "resource_limits",
    )
    return {
        "file_changes": file_changes,
        "parameter_binding_changes": binding_changes,
        "realization_requirement_changes": realization_requirement_changes,
        "frozen_field_changes": [
            field
            for field in frozen_fields
            if getattr(base, field) != getattr(revised, field)
        ],
    }


def package_deck_project(
    project: DeckProjectDraft,
    *,
    output_root: Path | str,
) -> PackagedTCADProject:
    """Create one reproducible package without interpreting its physics."""

    project_raw = _canonical(project.model_dump(mode="python"))
    project_sha256 = hashlib.sha256(project_raw).hexdigest()
    root = Path(output_root).expanduser().absolute()
    root.mkdir(parents=True, exist_ok=True, mode=0o770)
    if root.is_symlink() or not root.is_dir():
        raise PackagerError("package root must be a non-symlink directory")
    target = root / f"pkg_{project_sha256}"
    temporary: Path | None = Path(tempfile.mkdtemp(prefix=".package-", dir=root))
    try:
        assert temporary is not None
        archive_path = temporary / "project.tar"
        entries = _write_archive(project.files, archive_path)
        final_archive_path = target / archive_path.name
        archive_descriptor = _descriptor(
            "input_archive",
            archive_path,
            "application/x-tar",
            reported_path=final_archive_path,
        )
        job = TCADJobSpec(
            tool_profile=project.tool_profile,
            input_archive=archive_descriptor,
            archive_entries=entries,
            arguments=(project.entrypoint, *project.arguments),
            expected_outputs=tuple(
                ExpectedOutput(**item.model_dump(mode="python"))
                for item in project.expected_outputs
            ),
            limits=ResourceLimits(**project.resource_limits.model_dump(mode="python")),
        )
        job_path = temporary / "job.json"
        job_path.write_bytes(_canonical(job.model_dump(mode="python")))
        os.chmod(archive_path, 0o440)
        os.chmod(job_path, 0o440)

        if target.exists():
            if not _same_package(temporary, target):
                raise PackagerError("existing package differs from deterministic build")
        else:
            os.replace(temporary, target)
            temporary = None

        final_archive = target / "project.tar"
        final_job = target / "job.json"
        return PackagedTCADProject(
            project_sha256=project_sha256,
            package_directory=target,
            archive=_descriptor("input_archive", final_archive, "application/x-tar"),
            job_spec_file=_descriptor(
                "execution_payload", final_job, "application/json"
            ),
            job_spec=job,
        )
    finally:
        if temporary is not None:
            shutil.rmtree(temporary, ignore_errors=True)


def package_deck_project_json(
    raw: bytes,
    *,
    output_root: Path | str,
) -> PackagedTCADProject:
    """Validate canonical worker output before creating an execution package."""

    try:
        project = DeckProjectDraft.model_validate_json(raw, strict=True)
    except ValidationError as error:
        raise PackagerError("deck project artifact is invalid") from error
    canonical = _canonical(project.model_dump(mode="python"))
    if raw not in {canonical, canonical + b"\n"}:
        raise PackagerError("deck project artifact must use canonical JSON")
    return package_deck_project(project, output_root=output_root)


def package_reviewed_deck_json(
    raw: bytes,
    *,
    output_root: Path | str,
) -> PackagedTCADProject:
    """Validate one canonical reviewed package before preparing execution."""

    try:
        reviewed = ReviewedDeckPackage.model_validate_json(raw, strict=True)
    except ValidationError as error:
        raise PackagerError("reviewed deck package artifact is invalid") from error
    canonical = _canonical(reviewed.model_dump(mode="python"))
    if raw not in {canonical, canonical + b"\n"}:
        raise PackagerError("reviewed deck package artifact must use canonical JSON")
    return package_deck_project(reviewed.project, output_root=output_root)


def validate_deck_project_output(value: dict[str, object]) -> dict[str, object]:
    """Validate worker content without creating a package or side effect."""

    if not value.get("realization_manifest"):
        raise ValueError("new deck project requires a non-empty realization_manifest")
    project = DeckProjectDraft.model_validate_json(_canonical(value), strict=True)
    requirement_keys = {
        item.requirement_key for item in project.realization_manifest
    }
    for binding in project.parameter_bindings:
        if not binding.requirement_keys:
            raise ValueError(
                "new deck project parameter bindings require requirement_keys"
            )
        if not set(binding.requirement_keys).issubset(requirement_keys):
            raise ValueError(
                "new deck project parameter binding references an unknown requirement"
            )
    return project.model_dump(mode="json")


def validate_deck_review_report(value: dict[str, object]) -> dict[str, object]:
    report = DeckReviewReport.model_validate_json(_canonical(value), strict=True)
    return report.model_dump(mode="json")


def validate_deck_review_against_project(
    project: DeckProjectDraft, report: DeckReviewReport
) -> None:
    """Check that an independent review covers the exact embedded manifest."""

    expected = {item.requirement_key for item in project.realization_manifest}
    observed = {item.requirement_key for item in report.requirement_reviews}
    if observed != expected:
        raise ValueError("deck review does not cover the exact realization manifest")
    unsupported = {
        item.requirement_key
        for item in project.realization_manifest
        if item.implementation_status == "unsupported"
    }
    if unsupported and report.verdict == "pass":
        raise ValueError("deck review cannot pass an unsupported requirement")


def attest_runtime_contract(
    reviewed: ReviewedDeckPackage,
    manifest: TCADRuntimeManifest,
) -> RuntimeAttestation:
    """Verify execution facts without interpreting physical correctness."""

    checks: list[RuntimeContractCheck] = []
    terminal_pass = manifest.terminal_state == "succeeded" and manifest.exit_code == 0
    checks.append(
        RuntimeContractCheck(
            check_key="terminal_state",
            status="pass" if terminal_pass else "fail",
            rationale=(
                "The solver completed successfully with exit code zero."
                if terminal_pass
                else (
                    f"The solver ended as {manifest.terminal_state} with exit code "
                    f"{manifest.exit_code}: {manifest.error or 'no error detail'}"
                )
            ),
        )
    )
    observed = {item.name: item for item in manifest.outputs}
    declared = {item.name: item for item in reviewed.project.expected_outputs}
    missing: list[str] = []
    for index, expected in enumerate(reviewed.project.expected_outputs, start=1):
        actual = observed.get(expected.name)
        if actual is None:
            passed = not expected.required
            if expected.required:
                missing.append(expected.name)
            rationale = (
                "The optional output was not produced."
                if passed
                else f"Required output is missing: {expected.name}."
            )
        else:
            passed = (
                actual.relative_path == expected.relative_path
                and actual.media_type == expected.media_type
                and actual.size_bytes <= expected.max_bytes
            )
            rationale = (
                f"Collected output {expected.name} matches its declared contract."
                if passed
                else f"Collected output {expected.name} differs from its declared contract."
            )
        checks.append(
            RuntimeContractCheck(
                check_key=f"expected_output_{index:04d}",
                status="pass" if passed else "fail",
                rationale=rationale,
            )
        )
    undeclared = sorted(set(observed) - set(declared))
    checks.append(
        RuntimeContractCheck(
            check_key="undeclared_outputs",
            status="pass" if not undeclared else "fail",
            rationale=(
                "No undeclared solver outputs were collected."
                if not undeclared
                else "Undeclared outputs were collected: " + ", ".join(undeclared)
            ),
        )
    )
    for index, assertion in enumerate(reviewed.project.runtime_assertions, start=1):
        passed = assertion.expected_output_name in observed
        checks.append(
            RuntimeContractCheck(
                check_key=f"runtime_assertion_{index:04d}",
                status="pass" if passed else "fail",
                rationale=(
                    f"{assertion.description} Evidence output is present: "
                    f"{assertion.expected_output_name}."
                    if passed
                    else (
                        f"{assertion.description} Evidence output is missing: "
                        f"{assertion.expected_output_name}."
                    )
                ),
            )
        )
    verdict = "fail" if any(item.status == "fail" for item in checks) else "pass"
    return RuntimeAttestation(
        verdict=verdict,
        terminal_state=manifest.terminal_state,
        exit_code=manifest.exit_code,
        checks=tuple(checks),
        missing_required_outputs=tuple(missing),
        rationale=(
            "This attestation covers only solver termination and the declared output "
            "contract; it does not establish physical correctness or agreement with data."
        ),
    )


def validate_deck_project_patch(value: dict[str, object]) -> dict[str, object]:
    patch = DeckProjectPatch.model_validate_json(_canonical(value), strict=True)
    return patch.model_dump(mode="json")


def _write_archive(
    files: tuple[DeckFile, ...], archive_path: Path
) -> tuple[ArchiveEntry, ...]:
    entries: list[ArchiveEntry] = []
    with tarfile.open(archive_path, "w", format=tarfile.USTAR_FORMAT) as archive:
        for item in sorted(files, key=lambda value: value.relative_path):
            raw = item.content.encode("utf-8")
            info = tarfile.TarInfo(item.relative_path)
            info.size = len(raw)
            info.mode = 0o440
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            archive.addfile(info, fileobj=io.BytesIO(raw))
            entries.append(
                ArchiveEntry(
                    relative_path=item.relative_path,
                    sha256=hashlib.sha256(raw).hexdigest(),
                    size_bytes=len(raw),
                )
            )
    return tuple(entries)


def _same_package(candidate: Path, existing: Path) -> bool:
    names = ("job.json", "project.tar")
    if existing.is_symlink() or not existing.is_dir():
        return False
    if {item.name for item in existing.iterdir()} != set(names):
        return False
    return all(
        not (existing / name).is_symlink()
        and (existing / name).is_file()
        and (candidate / name).read_bytes() == (existing / name).read_bytes()
        for name in names
    )


def _descriptor(
    name: str,
    path: Path,
    media_type: str,
    *,
    reported_path: Path | None = None,
) -> FileDescriptor:
    raw = path.read_bytes()
    return FileDescriptor(
        name=name,
        local_path=str(reported_path or path),
        sha256=hashlib.sha256(raw).hexdigest(),
        size_bytes=len(raw),
        media_type=media_type,
    )


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


__all__ = [
    "DeckFile",
    "DeckFilePatch",
    "DeckProjectDraft",
    "DeckProjectPatch",
    "DeckRequirementReview",
    "DeckReviewFinding",
    "DeckReviewReport",
    "ReviewedDeckPackage",
    "RuntimeAttestation",
    "RuntimeContractCheck",
    "RuntimeOutputRecord",
    "TCADRuntimeManifest",
    "PackagedTCADProject",
    "PackagerError",
    "ParameterBinding",
    "ParameterBindingPatch",
    "ProjectExpectedOutput",
    "ProjectResourceLimits",
    "RealizationRequirement",
    "RuntimeAssertion",
    "apply_deck_project_patch",
    "attest_runtime_contract",
    "deck_project_diff",
    "package_deck_project",
    "package_deck_project_json",
    "package_reviewed_deck_json",
    "validate_deck_project_output",
    "validate_deck_project_patch",
    "validate_deck_review_against_project",
    "validate_deck_review_report",
]
