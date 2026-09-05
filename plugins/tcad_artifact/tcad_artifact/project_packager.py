"""Deterministically package a reviewed textual TCAD project for execution."""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re
import shutil
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal, Mapping

from pydantic import Field, ValidationError, field_validator, model_validator
from scidiscovery.artifact_agent.schema.common import canonical_sha256
from scidiscovery.artifact_agent.schema.experiment import ExperimentPortfolio
from scidiscovery.operation_contract import SemanticRuleViolation
from .device_parameters import (
    DeviceParameterCoverageReport,
    DeviceParameterSet,
)
from scidiscovery.artifact_agent.schema.refs import ArtifactRef

from .execution_control import (
    ArchiveEntry,
    ExpectedOutput,
    FileDescriptor,
    ResourceLimits,
    SolverCapability,
    SolverCapabilitySnapshot,
    SolverKind,
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


def _safe_optional_relative_path(value: str | None) -> str | None:
    return None if value is None else _safe_relative_path(value)


class DeckFile(StrictModel):
    relative_path: str = Field(min_length=1, max_length=1024)
    content: str = Field(max_length=8 * 1024 * 1024)

    _safe_path = field_validator("relative_path")(_safe_relative_path)


class ProjectInputSlot(StrictModel):
    semantic_name: str = Field(
        min_length=1,
        max_length=256,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$",
    )
    target_relative_path: str = Field(min_length=1, max_length=1024)
    media_type: str = Field(min_length=3, max_length=255)

    _safe_target = field_validator("target_relative_path")(_safe_relative_path)


class ResolvedProjectInput(StrictModel):
    semantic_name: str = Field(
        min_length=1,
        max_length=256,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$",
    )
    target_relative_path: str = Field(min_length=1, max_length=1024)
    artifact_ref: ArtifactRef
    media_type: str = Field(min_length=3, max_length=255)
    size_bytes: int = Field(ge=0, le=2**50)

    _safe_target = field_validator("target_relative_path")(_safe_relative_path)


ProjectExpectedOutput = ExpectedOutput
ProjectResourceLimits = ResourceLimits


class ParameterBinding(StrictModel):
    name: str = Field(min_length=1, max_length=256)
    approved_parameter_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]*$",
    )
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
    materialization_kind: Literal["agent_declared", "control_generated"] = (
        "agent_declared"
    )
    source_sha256: str | None = Field(
        default=None, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    source_line_start: int | None = Field(default=None, ge=1)
    source_line_end: int | None = Field(default=None, ge=1)
    derivation: str | None = Field(default=None, min_length=1, max_length=4096)

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
        if self.materialization_kind == "control_generated":
            if (
                self.source_sha256 is None
                or self.source_line_start is None
                or self.source_line_end is None
                or self.derivation is None
            ):
                raise ValueError(
                    "control-generated parameter binding requires exact source provenance"
                )
            if self.source_line_end < self.source_line_start:
                raise ValueError("parameter binding source line range is invalid")
        elif any(
            value is not None
            for value in (
                self.source_sha256,
                self.source_line_start,
                self.source_line_end,
                self.derivation,
            )
        ):
            raise ValueError(
                "agent-declared parameter binding cannot claim control provenance"
            )
        return self


class CaseParameterBinding(StrictModel):
    """One case-scoped realized control bound to exact solver source text."""

    experiment_key: str = Field(
        min_length=1,
        max_length=256,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]*$",
    )
    case_key: str = Field(
        min_length=1,
        max_length=256,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]*$",
    )
    variable_key: str = Field(
        min_length=1,
        max_length=256,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]*$",
    )
    scientific_path: str = Field(min_length=1, max_length=4096)
    realized_value: str = Field(min_length=1, max_length=4096)
    unit: str = Field(min_length=1, max_length=128)
    relative_path: str = Field(min_length=1, max_length=1024)
    locator: str = Field(min_length=1, max_length=4096)
    requirement_keys: tuple[str, ...] = Field(default=(), max_length=64)
    materialization_kind: Literal["agent_declared", "control_generated"] = (
        "agent_declared"
    )
    source_sha256: str | None = Field(
        default=None, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    source_line_start: int | None = Field(default=None, ge=1)
    source_line_end: int | None = Field(default=None, ge=1)
    derivation: str | None = Field(default=None, min_length=1, max_length=4096)

    _safe_path = field_validator("relative_path")(_safe_relative_path)

    @model_validator(mode="after")
    def _requirements_are_unique(self) -> CaseParameterBinding:
        if len(self.requirement_keys) != len(set(self.requirement_keys)):
            raise ValueError("case parameter requirement_keys must be unique")
        if self.materialization_kind == "control_generated":
            if (
                self.source_sha256 is None
                or self.source_line_start is None
                or self.source_line_end is None
                or self.derivation is None
            ):
                raise ValueError(
                    "control-generated case binding requires exact source provenance"
                )
            if self.source_line_end < self.source_line_start:
                raise ValueError("case binding source line range is invalid")
        elif any(
            value is not None
            for value in (
                self.source_sha256,
                self.source_line_start,
                self.source_line_end,
                self.derivation,
            )
        ):
            raise ValueError(
                "agent-declared case binding cannot claim control provenance"
            )
        return self


class MaterializationFinding(StrictModel):
    reason_code: Literal[
        "missing_control_binding",
        "duplicate_control_anchor",
        "comment_only_anchor",
        "unreachable_assignment",
        "value_mismatch",
        "unit_mismatch",
        "missing_requirement_realization",
        "downstream_only_requirement_in_deck",
        "implicit_solver_default",
        "dead_declaration",
        "raw_output_not_declared",
        "raw_output_not_produced",
        "unsupported_syntax",
        "source_changed_after_materialization",
    ]
    severity: Literal["error", "warning"]
    message: str = Field(min_length=1, max_length=4096)
    experiment_key: str | None = Field(default=None, max_length=256)
    case_key: str | None = Field(default=None, max_length=256)
    variable_key: str | None = Field(default=None, max_length=256)
    requirement_key: str | None = Field(default=None, max_length=256)
    source_path: str | None = Field(default=None, max_length=1024)
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    command_excerpt: str | None = Field(default=None, max_length=1024)
    expected: str | None = Field(default=None, max_length=4096)
    observed: str | None = Field(default=None, max_length=4096)
    suggested_fix_scope: str = Field(min_length=1, max_length=4096)


class ProjectMaterializationReport(StrictModel):
    schema_version: Annotated[int, Field(ge=1, le=1)] = 1
    profile: Literal[
        "tcad.project-materializer.sprocess.v1",
        "tcad.project-materializer.declared-source.v2",
    ]
    source_tree_sha256: str = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    status: Literal["pass", "fail"]
    generated_case_bindings: int = Field(ge=0, le=100000)
    generated_parameter_bindings: int = Field(ge=0, le=100000)
    generated_requirements: int = Field(ge=0, le=100000)
    findings: tuple[MaterializationFinding, ...] = Field(default=(), max_length=4096)

    @model_validator(mode="after")
    def _status_matches_findings(self) -> ProjectMaterializationReport:
        has_error = any(item.severity == "error" for item in self.findings)
        if (self.status == "fail") != has_error:
            raise ValueError("materialization status differs from its findings")
        return self


class ProjectPreflightAttestation(StrictModel):
    """Control-owned result of one source-bound solver preflight."""

    schema_version: Annotated[int, Field(ge=1, le=1)] = 1
    profile: Literal["tcad.project-preflight.v1"] = "tcad.project-preflight.v1"
    source_tree_sha256: str = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    mode: Literal["preflight"] = "preflight"
    terminal_state: Literal["succeeded", "failed", "cancelled"]
    exit_code: int
    diagnostic_layer: Literal[
        "parser",
        "initialization",
        "numerical",
        "output_contract",
        "resource_limit",
        "runtime",
        "complete",
    ]
    qualified: bool
    summary: str = Field(min_length=1, max_length=2048)

    @model_validator(mode="after")
    def _qualification_matches_result(self) -> ProjectPreflightAttestation:
        passed = (
            self.terminal_state == "succeeded"
            and self.exit_code == 0
            and self.diagnostic_layer == "complete"
        )
        if self.qualified != passed:
            raise ValueError("preflight qualification differs from its terminal result")
        return self


class RuntimeAssertion(StrictModel):
    description: str = Field(min_length=1, max_length=4096)
    expected_output_name: str = Field(min_length=1, max_length=256)
    assertion_kind: Literal[
        "output_present",
        "file_nonempty",
        "finite_numeric_table",
        "solver_log_clean",
        "tdr_metadata",
    ] = "output_present"
    required_columns: tuple[str, ...] = Field(default=(), max_length=4096)
    min_numeric_rows: int = Field(default=1, ge=1, le=10**9)

    @model_validator(mode="after")
    def _parser_requirements_are_consistent(self) -> RuntimeAssertion:
        if self.assertion_kind != "finite_numeric_table" and self.required_columns:
            raise ValueError("required columns apply only to numeric-table assertions")
        if len(self.required_columns) != len(set(self.required_columns)):
            raise ValueError("runtime assertion required columns must be unique")
        return self


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
    solver_kind: SolverKind | None = None
    capability_sha256: str | None = Field(
        default=None, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    files: tuple[DeckFile, ...] = Field(min_length=1, max_length=4096)
    input_slots: tuple[ProjectInputSlot, ...] = Field(default=(), max_length=4096)
    entrypoint: str = Field(min_length=1, max_length=1024)
    development_initialization_entrypoint: str | None = Field(
        default=None, min_length=1, max_length=1024
    )
    arguments: tuple[str, ...] = Field(default=(), max_length=256)
    expected_outputs: tuple[ProjectExpectedOutput, ...] = Field(max_length=4096)
    parameter_bindings: tuple[ParameterBinding, ...] = Field(default=(), max_length=4096)
    case_parameter_bindings: tuple[CaseParameterBinding, ...] = Field(
        default=(), max_length=100000
    )
    runtime_assertions: tuple[RuntimeAssertion, ...] = Field(default=(), max_length=4096)
    realization_manifest: tuple[RealizationRequirement, ...] = Field(
        default=(), max_length=4096
    )
    materialization_report: ProjectMaterializationReport | None = None
    preflight_attestation: ProjectPreflightAttestation | None = None
    resource_limits: ProjectResourceLimits

    _safe_entrypoint = field_validator("entrypoint")(_safe_relative_path)
    _safe_initialization_entrypoint = field_validator(
        "development_initialization_entrypoint"
    )(_safe_optional_relative_path)

    @model_validator(mode="after")
    def _consistent_project(self) -> DeckProjectDraft:
        file_paths = tuple(item.relative_path for item in self.files)
        if len(file_paths) != len(set(file_paths)):
            raise ValueError("project file paths must be unique")
        if self.entrypoint not in set(file_paths):
            raise ValueError("entrypoint must name one project file")
        if (
            self.development_initialization_entrypoint is not None
            and self.development_initialization_entrypoint not in set(file_paths)
        ):
            raise ValueError("development initialization entrypoint must name one project file")
        if sum(len(item.content.encode("utf-8")) for item in self.files) > MAX_PROJECT_BYTES:
            raise ValueError("project source exceeds total byte limit")

        output_names = tuple(item.name for item in self.expected_outputs)
        output_paths = tuple(item.relative_path for item in self.expected_outputs)
        if len(output_names) != len(set(output_names)) or len(output_paths) != len(set(output_paths)):
            raise ValueError("expected output names and paths must be unique")
        if set(file_paths).intersection(output_paths):
            raise ValueError("expected output must not overwrite a project input")
        slot_names = tuple(item.semantic_name for item in self.input_slots)
        slot_paths = tuple(item.target_relative_path for item in self.input_slots)
        if len(slot_names) != len(set(slot_names)) or len(slot_paths) != len(
            set(slot_paths)
        ):
            raise ValueError("project input slot names and paths must be unique")
        if set(file_paths).intersection(slot_paths) or set(output_paths).intersection(
            slot_paths
        ):
            raise ValueError("project input slots must not overlap text files or outputs")

        binding_names = tuple(item.name for item in self.parameter_bindings)
        if len(binding_names) != len(set(binding_names)):
            raise ValueError("parameter binding names must be unique")
        case_binding_keys = tuple(
            (item.experiment_key, item.case_key, item.variable_key)
            for item in self.case_parameter_bindings
        )
        if len(case_binding_keys) != len(set(case_binding_keys)):
            raise ValueError("case parameter bindings must be unique")
        contents = {item.relative_path: item.content for item in self.files}
        solver_kind = self.solver_kind
        if solver_kind is not None:
            if solver_kind in {"sprocess", "sdevice"} and Path(
                self.entrypoint
            ).suffix.lower() != ".cmd":
                raise ValueError(
                    f"direct {solver_kind} entrypoint must be a .cmd solver deck"
                )
            entrypoint_content = contents[self.entrypoint]
            if solver_kind in {"sprocess", "sdevice"} and any(
                marker in entrypoint_content for marker in SHELL_ENTRYPOINT_MARKERS
            ):
                raise ValueError(
                    f"direct {solver_kind} entrypoint contains shell-runner syntax"
                )
            if solver_kind in {"sprocess", "sdevice"} and any(
                value in {"submit", "worker", "status"}
                for value in self.arguments
            ):
                raise ValueError(
                    f"direct {solver_kind} arguments contain scheduler commands"
                )
            unresolved = {
                token
                for content in contents.values()
                for token in WORKBENCH_TOKEN.findall(content)
            }
            if solver_kind in {"sprocess", "sdevice"} and unresolved:
                raise ValueError(
                    "standalone direct-solver project contains unresolved "
                    "Workbench tokens: " + ", ".join(sorted(unresolved))
                )
            nested_solver = re.search(
                rf"(^|[;\n])\s*(?:exec\s+)?{solver_kind}\b",
                entrypoint_content,
                re.IGNORECASE,
            )
            if solver_kind in {"sprocess", "sdevice"} and nested_solver:
                raise ValueError(
                    f"direct {solver_kind} entrypoint launches a nested solver"
                )
        for binding in self.parameter_bindings:
            if binding.relative_path not in contents:
                raise ValueError("parameter binding file must exist")
            if binding.locator not in contents[binding.relative_path]:
                raise ValueError("parameter binding locator is absent from its file")
            if binding.materialization_kind == "control_generated":
                if hashlib.sha256(
                    contents[binding.relative_path].encode("utf-8")
                ).hexdigest() != binding.source_sha256:
                    raise ValueError(
                        "control-generated parameter binding source digest differs"
                    )
        for binding in self.case_parameter_bindings:
            if binding.relative_path not in contents:
                raise ValueError("case parameter binding file must exist")
            if contents[binding.relative_path].count(binding.locator) != 1:
                raise ValueError(
                    "case parameter binding locator must occur exactly once"
                )
            if (
                binding.materialization_kind == "agent_declared"
                and binding.realized_value not in binding.locator
            ):
                raise ValueError(
                    "case parameter binding value is not present in its exact locator"
                )
            if binding.materialization_kind == "control_generated":
                if hashlib.sha256(
                    contents[binding.relative_path].encode("utf-8")
                ).hexdigest() != binding.source_sha256:
                    raise ValueError(
                        "control-generated case binding source digest differs"
                    )

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
        for binding in self.case_parameter_bindings:
            if not set(binding.requirement_keys).issubset(known_requirements):
                raise ValueError(
                    "case parameter binding references an unknown realization requirement"
                )

        output_name_set = set(output_names)
        if any(
            item.expected_output_name not in output_name_set
            for item in self.runtime_assertions
        ):
            raise ValueError("runtime assertion must reference an expected output")
        if any("\x00" in value or len(value) > 4096 for value in self.arguments):
            raise ValueError("project argument is invalid")
        source_tree = hashlib.sha256()
        for path, content in sorted(contents.items()):
            source_tree.update(path.encode("utf-8"))
            source_tree.update(b"\0")
            source_tree.update(content.encode("utf-8"))
            source_tree.update(b"\0")
        source_tree_sha256 = source_tree.hexdigest()
        if self.materialization_report is not None:
            if source_tree_sha256 != self.materialization_report.source_tree_sha256:
                raise ValueError("materialization report source digest differs")
            if self.materialization_report.status != "pass":
                raise ValueError("canonical project materialization did not pass")
        if (
            self.preflight_attestation is not None
            and self.preflight_attestation.source_tree_sha256
            != source_tree_sha256
        ):
            raise ValueError("preflight attestation source digest differs")
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
    capability_sha256: str | None = Field(
        default=None, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    summary: str = Field(min_length=1, max_length=4096)
    rationale: str = Field(min_length=1, max_length=8192)
    physical_fidelity: Literal["pass", "fail", "unknown"]
    implementation_fidelity: Literal["pass", "fail", "unknown"]
    syntax_fidelity: Literal["pass", "fail", "unknown"] = "unknown"
    numerical_protocol_fidelity: Literal["pass", "fail", "unknown"]
    requirement_reviews: tuple[DeckRequirementReview, ...] = Field(
        default=(), max_length=4096
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
            self.numerical_protocol_fidelity,
        }
        requirement_statuses = {item.status for item in self.requirement_reviews}
        blocking_finding = any(
            item.severity in {"blocker", "major"} for item in self.findings
        )
        clean = (
            dimensions == {"pass"}
            and self.syntax_fidelity != "fail"
            and requirement_statuses in (set(), {"pass"})
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

    schema_version: Annotated[int, Field(ge=2, le=2)] = 2
    project: DeckProjectDraft
    review: DeckReviewReport
    capability: SolverCapabilitySnapshot
    resolved_inputs: tuple[ResolvedProjectInput, ...] = Field(
        default=(), max_length=4096
    )
    @model_validator(mode="after")
    def _review_qualifies_project(self) -> ReviewedDeckPackage:
        if self.project.solver_kind is None:
            raise ValueError("reviewed deck package requires an explicit solver_kind")
        if (
            self.project.capability_sha256 != self.capability.capability_sha256
            or self.review.capability_sha256
            not in {None, self.capability.capability_sha256}
        ):
            raise ValueError(
                "reviewed deck package project or review capability digest differs"
            )
        if (
            self.capability.profile_id != self.project.tool_profile
            or self.capability.solver_kind != self.project.solver_kind
        ):
            raise ValueError("reviewed deck package capability differs from its project")
        slots = {item.semantic_name: item for item in self.project.input_slots}
        resolved = {item.semantic_name: item for item in self.resolved_inputs}
        if len(resolved) != len(self.resolved_inputs) or set(resolved) != set(slots):
            raise ValueError("reviewed deck package must resolve every project input slot")
        for name, slot in slots.items():
            item = resolved[name]
            if (
                item.target_relative_path != slot.target_relative_path
                or item.media_type != slot.media_type
            ):
                raise ValueError("resolved project input differs from its declared slot")
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
    output_class: Literal[
        "solver_native", "transport_derived", "parser_derived"
    ] = "solver_native"

    _safe_path = field_validator("relative_path")(_safe_relative_path)


class TCADRuntimeManifest(StrictModel):
    started_at: str | None = Field(min_length=1, max_length=128)
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
    gate_kind: Literal["transport", "format", "numeric", "runtime_contract"] = (
        "runtime_contract"
    )
    provider_id: str | None = Field(default=None, min_length=1, max_length=256)


class RuntimeAttestation(StrictModel):
    schema_version: Annotated[int, Field(ge=1, le=1)] = 1
    verdict: Literal["pass", "fail"]
    terminal_state: Literal["succeeded", "failed", "cancelled"]
    exit_code: int
    checks: tuple[RuntimeContractCheck, ...] = Field(min_length=1, max_length=8192)
    missing_required_outputs: tuple[str, ...] = Field(default=(), max_length=4096)
    solver_native_output_count: int = Field(ge=0, le=4096)
    transport_derived_output_count: int = Field(ge=0, le=4096)
    parser_derived_output_count: int = Field(ge=0, le=4096)
    scope: Literal["execution_contract_only"] = "execution_contract_only"
    rationale: str = Field(min_length=1, max_length=4096)

    @model_validator(mode="after")
    def _verdict_matches_checks(self) -> RuntimeAttestation:
        failed = any(item.status == "fail" for item in self.checks)
        if (self.verdict == "fail") != failed:
            raise ValueError("runtime attestation verdict differs from its checks")
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
    base_case_bindings = {
        (item.experiment_key, item.case_key, item.variable_key): item.model_dump(
            mode="json"
        )
        for item in base.case_parameter_bindings
    }
    revised_case_bindings = {
        (item.experiment_key, item.case_key, item.variable_key): item.model_dump(
            mode="json"
        )
        for item in revised.case_parameter_bindings
    }
    case_binding_changes = [
        "/".join(key)
        for key in sorted(set(base_case_bindings) | set(revised_case_bindings))
        if base_case_bindings.get(key) != revised_case_bindings.get(key)
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
    base_outputs = {
        item.name: item.model_dump(mode="json") for item in base.expected_outputs
    }
    revised_outputs = {
        item.name: item.model_dump(mode="json") for item in revised.expected_outputs
    }
    expected_output_changes = [
        name
        for name in sorted(set(base_outputs) | set(revised_outputs))
        if base_outputs.get(name) != revised_outputs.get(name)
    ]
    base_assertions: dict[str, list[dict[str, object]]] = {}
    revised_assertions: dict[str, list[dict[str, object]]] = {}
    for item in base.runtime_assertions:
        base_assertions.setdefault(item.expected_output_name, []).append(
            item.model_dump(mode="json")
        )
    for item in revised.runtime_assertions:
        revised_assertions.setdefault(item.expected_output_name, []).append(
            item.model_dump(mode="json")
        )
    runtime_assertion_output_changes = [
        name
        for name in sorted(set(base_assertions) | set(revised_assertions))
        if base_assertions.get(name) != revised_assertions.get(name)
    ]
    frozen_fields = (
        "tool_profile",
        "solver_kind",
        "capability_sha256",
        "input_slots",
        "entrypoint",
        "development_initialization_entrypoint",
        "arguments",
        "resource_limits",
    )
    return {
        "file_changes": file_changes,
        "parameter_binding_changes": binding_changes,
        "case_parameter_binding_changes": case_binding_changes,
        "realization_requirement_changes": realization_requirement_changes,
        "expected_output_changes": expected_output_changes,
        "runtime_assertion_output_changes": runtime_assertion_output_changes,
        "frozen_field_changes": [
            field
            for field in frozen_fields
            if getattr(base, field) != getattr(revised, field)
        ],
    }


def package_deck_project(
    project: DeckProjectDraft,
    *,
    capability: SolverCapability | SolverCapabilitySnapshot,
    resolved_inputs: tuple[ResolvedProjectInput, ...] = (),
    input_payloads: Mapping[str, bytes] | None = None,
    output_root: Path | str,
) -> PackagedTCADProject:
    """Create one reproducible package without interpreting its physics."""

    snapshot = (
        capability.public_snapshot()
        if isinstance(capability, SolverCapability)
        else capability
    )
    if project.solver_kind is None:
        raise PackagerError("execution packaging requires an explicit solver_kind")
    if (
        snapshot.profile_id != project.tool_profile
        or snapshot.solver_kind != project.solver_kind
    ):
        raise PackagerError("execution capability differs from the deck project")
    if (
        project.capability_sha256 is not None
        and project.capability_sha256 != snapshot.capability_sha256
    ):
        raise PackagerError("execution capability digest differs from the deck project")
    slots = {item.semantic_name: item for item in project.input_slots}
    resolved = {item.semantic_name: item for item in resolved_inputs}
    if len(resolved) != len(resolved_inputs) or set(resolved) != set(slots):
        raise PackagerError("execution packaging requires every project input slot")
    payloads = dict(input_payloads or {})
    if set(payloads) != set(slots):
        raise PackagerError("execution input payloads must cover the exact project slots")
    binary_files: dict[str, bytes] = {}
    for name, slot in slots.items():
        item = resolved[name]
        if (
            item.target_relative_path != slot.target_relative_path
            or item.media_type != slot.media_type
        ):
            raise PackagerError("resolved execution input differs from its project slot")
        raw = payloads[name]
        if type(raw) is not bytes:
            raise PackagerError("resolved execution input payload must be bytes")
        if (
            len(raw) != item.size_bytes
            or hashlib.sha256(raw).hexdigest() != item.artifact_ref.sha256
        ):
            raise PackagerError("resolved execution input differs from its artifact ref")
        binary_files[item.target_relative_path] = raw
    project_raw = _canonical(project.model_dump(mode="python"))
    project_sha256 = hashlib.sha256(project_raw).hexdigest()
    package_sha256 = hashlib.sha256(
        project_raw
        + _canonical(snapshot.model_dump(mode="python"))
        + _canonical([item.model_dump(mode="python") for item in resolved_inputs])
    ).hexdigest()
    root = Path(output_root).expanduser().absolute()
    root.mkdir(parents=True, exist_ok=True, mode=0o770)
    if root.is_symlink() or not root.is_dir():
        raise PackagerError("package root must be a non-symlink directory")
    target = root / f"pkg_{package_sha256}"
    temporary: Path | None = Path(tempfile.mkdtemp(prefix=".package-", dir=root))
    try:
        assert temporary is not None
        archive_path = temporary / "project.tar"
        entries = _write_archive(project.files, binary_files, archive_path)
        final_archive_path = target / archive_path.name
        archive_descriptor = _descriptor(
            "input_archive",
            archive_path,
            "application/x-tar",
            reported_path=final_archive_path,
        )
        job = TCADJobSpec(
            execution_purpose="production",
            tool_profile=project.tool_profile,
            solver_kind=project.solver_kind,
            capability_sha256=snapshot.capability_sha256,
            input_archive=archive_descriptor,
            archive_entries=entries,
            arguments=(project.entrypoint, *project.arguments),
            expected_outputs=project.expected_outputs,
            limits=project.resource_limits,
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


def package_reviewed_deck_json(
    raw: bytes,
    *,
    input_payloads: Mapping[str, bytes] | None = None,
    output_root: Path | str,
) -> PackagedTCADProject:
    """Validate one canonical reviewed package before preparing execution."""

    reviewed = validate_reviewed_deck_json(raw)
    return package_deck_project(
        reviewed.project,
        capability=reviewed.capability,
        resolved_inputs=reviewed.resolved_inputs,
        input_payloads=input_payloads,
        output_root=output_root,
    )


def validate_reviewed_deck_json(raw: bytes) -> ReviewedDeckPackage:
    """Validate a canonical reviewed package without creating execution files."""

    try:
        reviewed = ReviewedDeckPackage.model_validate_json(raw, strict=True)
    except ValidationError as error:
        raise PackagerError("reviewed deck package artifact is invalid") from error
    canonical = _canonical(reviewed.model_dump(mode="python"))
    if raw not in {canonical, canonical + b"\n"}:
        raise PackagerError("reviewed deck package artifact must use canonical JSON")
    return reviewed


def validate_deck_project_output(value: dict[str, object]) -> dict[str, object]:
    """Validate worker content without creating a package or side effect."""

    report = value.get("materialization_report")
    declared_source = (
        isinstance(report, dict)
        and report.get("profile") == "tcad.project-materializer.declared-source.v2"
    )
    if not declared_source and not value.get("realization_manifest"):
        raise SemanticRuleViolation("new deck project requires a non-empty realization_manifest")
    if not value.get("solver_kind"):
        raise SemanticRuleViolation("new deck project requires an explicit solver_kind")
    if not value.get("capability_sha256"):
        raise SemanticRuleViolation("new deck project requires an exact capability digest")
    project = DeckProjectDraft.model_validate_json(_canonical(value), strict=True)
    requirement_keys = {
        item.requirement_key for item in project.realization_manifest
    }
    for binding in project.parameter_bindings:
        if not binding.requirement_keys:
            raise SemanticRuleViolation(
                "new deck project parameter bindings require requirement_keys"
            )
        if not set(binding.requirement_keys).issubset(requirement_keys):
            raise SemanticRuleViolation(
                "new deck project parameter binding references an unknown requirement"
            )
    return project.model_dump(mode="json")


_SOLVER_NATIVE_OUTPUT_SUFFIXES = {
    "sprocess": frozenset({".tdr", ".plx", ".plt", ".log"}),
    "sdevice": frozenset({".tdr", ".plx", ".plt", ".log"}),
}


def solver_deck_scope_violations(project: DeckProjectDraft) -> tuple[str, ...]:
    """Return deterministic direct-solver responsibilities outside a deck."""

    suffixes = _SOLVER_NATIVE_OUTPUT_SUFFIXES.get(project.solver_kind)
    if suffixes is None:
        return ()
    violations = [
        f"unsupported_requirement:{item.requirement_key}"
        for item in project.realization_manifest
        if item.implementation_status == "unsupported"
    ]
    violations.extend(
        f"runtime_assertion:{index}:{item.expected_output_name}:{item.assertion_kind}"
        for index, item in enumerate(project.runtime_assertions, start=1)
    )
    violations.extend(
        f"non_solver_native_output:{item.name}:{item.relative_path}"
        for item in project.expected_outputs
        if Path(item.relative_path).suffix.lower() not in suffixes
    )
    return tuple(sorted(violations))


def validate_deck_author_task_output(
    value: dict[str, object],
    inputs: Mapping[str, bytes],
    handoff: dict[str, object],
) -> None:
    """Keep direct-solver author output inside the solver-code boundary."""

    project = DeckProjectDraft.model_validate_json(_canonical(value), strict=True)
    experiment_plan = inputs.get("experiment_plan")
    if experiment_plan is not None:
        if project.solver_kind == "sprocess" and project.materialization_report is None:
            raise SemanticRuleViolation(
                "new SProcess author output must be control-materialized"
            )
        validate_project_case_controls(project, experiment_plan)
    _validate_approved_parameter_bindings(project, inputs)
    current = set(solver_deck_scope_violations(project))
    prior_raw = inputs.get("prior_project")
    if prior_raw is None:
        if current:
            raise SemanticRuleViolation(
                "direct-solver deck contains post-execution or unsupported duties: "
                + ", ".join(sorted(current))
            )
        return
    prior = DeckProjectDraft.model_validate_json(prior_raw, strict=True)
    introduced = current - set(solver_deck_scope_violations(prior))
    if introduced:
        raise SemanticRuleViolation(
            "deck revision introduced post-execution or unsupported duties: "
            + ", ".join(sorted(introduced))
        )
    if handoff.get("verdict") == "pass" and current:
        raise SemanticRuleViolation(
            "passing deck revision retains post-execution or unsupported duties: "
            + ", ".join(sorted(current))
        )


def validate_deck_review_task_output(
    value: dict[str, object],
    inputs: Mapping[str, bytes],
    handoff: dict[str, object],
) -> None:
    """Cross-check a formal review against its one exact project input."""

    project_names = tuple(
        name for name in ("project", "revised_project") if name in inputs
    )
    if len(project_names) != 1:
        raise SemanticRuleViolation("deck review requires one exact project input")
    project = DeckProjectDraft.model_validate_json(
        inputs[project_names[0]], strict=True
    )
    experiment_plan = inputs.get("experiment_plan")
    if experiment_plan is not None:
        validate_project_case_controls(project, experiment_plan)
    _validate_approved_parameter_bindings(project, inputs)
    report = DeckReviewReport.model_validate_json(_canonical(value), strict=True)
    if handoff.get("verdict") != report.verdict:
        raise SemanticRuleViolation("deck review handoff verdict differs from its report")
    validate_deck_review_against_project(project, report)
    violations = solver_deck_scope_violations(project)
    if violations and report.verdict == "pass":
        raise SemanticRuleViolation(
            "deck review cannot pass post-execution or unsupported duties: "
            + ", ".join(violations)
        )


def _validate_approved_parameter_bindings(
    project: DeckProjectDraft,
    inputs: Mapping[str, bytes],
) -> None:
    parameter_raw = inputs.get("device_parameters")
    coverage_raw = inputs.get("parameter_coverage")
    if parameter_raw is None and coverage_raw is None:
        if any(
            item.approved_parameter_key is not None
            for item in project.parameter_bindings
        ):
            raise SemanticRuleViolation(
                "approved parameter binding requires the exact approved context"
            )
        return
    if parameter_raw is None or coverage_raw is None:
        raise SemanticRuleViolation(
            "approved parameter validation requires parameter set and coverage report"
        )
    parameters = DeviceParameterSet.model_validate_json(parameter_raw, strict=True)
    coverage = DeviceParameterCoverageReport.model_validate_json(
        coverage_raw, strict=True
    )
    if (
        coverage.parameter_set_key != parameters.parameter_set_key
        or coverage.status == "fail"
    ):
        raise SemanticRuleViolation("approved parameter coverage does not qualify this parameter set")
    claims = {item.parameter_key: item for item in parameters.claims}
    coverage_by_key = {item.parameter_key: item for item in coverage.items}
    for binding in project.parameter_bindings:
        key = binding.approved_parameter_key
        if key is None:
            continue
        claim = claims.get(key)
        coverage_item = coverage_by_key.get(key)
        if claim is None or coverage_item is None:
            raise SemanticRuleViolation(
                f"approved_parameter_key is absent from the approved set: {key}"
            )
        if coverage_item.status in {"missing", "conflict", "not_comparable"}:
            raise SemanticRuleViolation(f"approved parameter is not usable by the deck: {key}")
        if binding.declared_value != claim.selected_value or binding.unit != claim.unit:
            raise SemanticRuleViolation(
                f"deck binding differs from the exact approved parameter value: {key}"
            )


def validate_project_case_controls(
    project: DeckProjectDraft,
    experiment_plan: bytes,
) -> None:
    """Require exact source-backed case controls before a scientific execution."""

    portfolio = ExperimentPortfolio.model_validate_json(
        experiment_plan, strict=True
    )
    expected: dict[tuple[str, str, str], tuple[str, str, object, bool]] = {}
    for proposal in portfolio.proposals:
        contract = proposal.comparison_contract
        if contract is None:
            continue
        for variable in contract.variables:
            if not deck_scoped_comparison_variable(variable.scientific_path):
                continue
            for expectation in variable.expectations:
                expected[
                    (
                        proposal.experiment_key,
                        expectation.case_key,
                        variable.variable_key,
                    )
                ] = (
                    variable.scientific_path,
                    variable.unit,
                    expectation.value,
                    variable.comparison_role == "frozen",
                )
    if not expected:
        return
    actual = {
        (item.experiment_key, item.case_key, item.variable_key): item
        for item in project.case_parameter_bindings
    }
    unexpected = sorted(set(actual) - set(expected))
    required_case_keys = {
        key for key, (_, _, _, frozen) in expected.items() if not frozen
    }
    missing = sorted(required_case_keys - set(actual))
    if missing or unexpected:
        raise SemanticRuleViolation(
            "project case_parameter_bindings must cover every case-varying "
            "scientific control and contain no undeclared control; "
            f"missing={missing[:16]}, "
            f"unexpected={unexpected[:16]}"
        )
    global_bindings = {item.name: item for item in project.parameter_bindings}
    frozen_variables = {
        key[2]
        for key, (_, _, _, frozen) in expected.items()
        if frozen
    }
    for variable_key in frozen_variables:
        keys = {key for key in expected if key[2] == variable_key}
        present = keys.intersection(actual)
        if present and present != keys:
            raise SemanticRuleViolation(
                f"case-scoped frozen control is incomplete for {variable_key}"
            )
        if not present:
            try:
                global_binding = global_bindings[variable_key]
            except KeyError as error:
                raise SemanticRuleViolation(
                    f"frozen comparison control is not source-bound: {variable_key}"
                ) from error
            _, unit, expected_value, _ = expected[next(iter(keys))]
            if global_binding.unit != unit or (
                _parse_case_control_value(
                    global_binding.declared_value, expected_value
                )
                != expected_value
            ):
                raise SemanticRuleViolation(
                    f"global frozen control differs from the experiment plan: {variable_key}"
                )
    for key, binding in actual.items():
        scientific_path, unit, expected_value, _ = expected[key]
        if binding.scientific_path != scientific_path or binding.unit != unit:
            raise SemanticRuleViolation(
                "case parameter binding path or unit differs from the comparison "
                f"contract for {key}"
            )
        if _parse_case_control_value(binding.realized_value, expected_value) != expected_value:
            raise SemanticRuleViolation(
                f"case parameter binding value differs from the experiment plan for {key}"
            )


_DOWNSTREAM_COMPARISON_PATH_PREFIXES = (
    "analysis.",
    "diagnosis.",
    "implementation.curve_score",
    "implementation.reference_input",
    "scoring.",
)


def deck_scoped_comparison_variable(scientific_path: str) -> bool:
    """Return whether a planned comparison variable must be realized by solver code."""

    return not scientific_path.startswith(_DOWNSTREAM_COMPARISON_PATH_PREFIXES)


def _parse_case_control_value(raw: str, exemplar: object) -> object:
    if type(exemplar) is bool:
        if raw not in {"true", "false"}:
            raise SemanticRuleViolation("boolean case control must use true or false")
        return raw == "true"
    if type(exemplar) is int:
        try:
            return int(raw)
        except ValueError as error:
            raise SemanticRuleViolation("integer case control is invalid") from error
    if type(exemplar) is float:
        try:
            value = float(raw)
        except ValueError as error:
            raise SemanticRuleViolation("numeric case control is invalid") from error
        if not math.isfinite(value):
            raise SemanticRuleViolation("numeric case control must be finite")
        return value
    return raw


def validate_deck_review_report(value: dict[str, object]) -> dict[str, object]:
    report = DeckReviewReport.model_validate_json(_canonical(value), strict=True)
    return report.model_dump(mode="json")


def validate_deck_review_against_project(
    project: DeckProjectDraft, report: DeckReviewReport
) -> None:
    """Check that an independent review covers the exact embedded manifest."""

    expected = {item.requirement_key for item in project.realization_manifest}
    observed = {item.requirement_key for item in report.requirement_reviews}
    if project.materialization_report is None:
        if observed != expected:
            raise SemanticRuleViolation(
                "deck review does not cover the exact realization manifest; "
                f"missing={sorted(expected - observed)}, "
                f"unexpected={sorted(observed - expected)}"
            )
        if report.verdict == "pass" and report.syntax_fidelity != "pass":
            raise SemanticRuleViolation(
                "passing direct-deck review requires syntax_fidelity pass; use the "
                "control-owned qualified preflight_attestation when present"
            )
        if report.syntax_fidelity == "pass" and (
            project.preflight_attestation is None
            or not project.preflight_attestation.qualified
        ):
            raise SemanticRuleViolation(
                "direct-deck syntax pass requires a source-bound qualified preflight"
            )
    elif observed:
        raise SemanticRuleViolation(
            "control-materialized project review must not restate deterministic requirements"
        )
    if report.execution_ready and (
            project.preflight_attestation is None
            or not project.preflight_attestation.qualified
    ):
        raise SemanticRuleViolation(
            "execution-ready deck review requires a source-bound passing preflight"
        )
    unsupported = {
        item.requirement_key
        for item in project.realization_manifest
        if item.implementation_status == "unsupported"
    }
    if unsupported and report.verdict == "pass":
        raise SemanticRuleViolation("deck review cannot pass an unsupported requirement")
    violations = solver_deck_scope_violations(project)
    if violations and report.verdict == "pass":
        raise SemanticRuleViolation(
            "deck review cannot pass post-execution deck duties: "
            + ", ".join(violations)
        )
    if project.materialization_report is None:
        if project.capability_sha256 != report.capability_sha256:
            raise SemanticRuleViolation("deck review capability digest differs from its project")
    elif report.capability_sha256 not in {None, project.capability_sha256}:
        raise SemanticRuleViolation("deck review capability digest differs from its project")


def attest_runtime_contract(
    reviewed: ReviewedDeckPackage,
    manifest: TCADRuntimeManifest,
    *,
    output_payloads: Mapping[str, bytes] | None = None,
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
    payloads = dict(output_payloads or {})
    if not set(payloads).issubset(observed):
        raise ValueError("runtime payload names must exist in the runtime manifest")
    for name, raw in payloads.items():
        if type(raw) is not bytes:
            raise TypeError("runtime output payload must be bytes")
        descriptor = observed[name]
        passed = (
            len(raw) == descriptor.size_bytes
            and hashlib.sha256(raw).hexdigest() == descriptor.sha256
        )
        checks.append(
            RuntimeContractCheck(
                check_key=f"transport_payload_{name}",
                status="pass" if passed else "fail",
                rationale=(
                    f"Collected payload {name} matches its immutable descriptor."
                    if passed
                    else f"Collected payload {name} differs from its immutable descriptor."
                ),
                gate_kind="transport",
            )
        )
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
                and (actual.size_bytes > 0 or not expected.required)
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
    undeclared = sorted(
        name
        for name, item in observed.items()
        if item.output_class == "solver_native" and name not in declared
    )
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
        passed, rationale, gate_kind, provider_id = _evaluate_runtime_assertion(
            assertion,
            observed.get(assertion.expected_output_name),
            payloads.get(assertion.expected_output_name),
        )
        checks.append(
            RuntimeContractCheck(
                check_key=f"runtime_assertion_{index:04d}",
                status="pass" if passed else "fail",
                rationale=f"{assertion.description} {rationale}",
                gate_kind=gate_kind,
                provider_id=provider_id,
            )
        )
    verdict = "fail" if any(item.status == "fail" for item in checks) else "pass"
    return RuntimeAttestation(
        verdict=verdict,
        terminal_state=manifest.terminal_state,
        exit_code=manifest.exit_code,
        checks=tuple(checks),
        missing_required_outputs=tuple(missing),
        solver_native_output_count=sum(
            item.output_class == "solver_native" for item in manifest.outputs
        ),
        transport_derived_output_count=sum(
            item.output_class == "transport_derived" for item in manifest.outputs
        ),
        parser_derived_output_count=sum(
            item.output_class == "parser_derived" for item in manifest.outputs
        ),
        rationale=(
            "This attestation covers only solver termination and the declared output "
            "contract; it does not establish physical correctness or agreement with data."
        ),
    )


def _evaluate_runtime_assertion(
    assertion: RuntimeAssertion,
    output: RuntimeOutputRecord | None,
    raw: bytes | None,
) -> tuple[bool, str, Literal["format", "numeric", "runtime_contract"], str | None]:
    if output is None:
        return (
            False,
            f"Evidence output is missing: {assertion.expected_output_name}.",
            "runtime_contract",
            None,
        )
    if assertion.assertion_kind == "output_present":
        return True, "The declared output is present.", "runtime_contract", None
    if assertion.assertion_kind == "file_nonempty":
        passed = output.size_bytes > 0
        return (
            passed,
            "The declared output is non-empty."
            if passed
            else "The declared output is empty.",
            "format",
            "tcad.file-nonempty.v1",
        )
    if raw is None:
        return (
            False,
            "Parser input bytes were not bound to the runtime attestation.",
            "format",
            None,
        )
    if assertion.assertion_kind == "tdr_metadata":
        return (
            False,
            "No qualified TDR metadata provider is configured.",
            "format",
            None,
        )
    if assertion.assertion_kind == "solver_log_clean":
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return False, "Solver log is not valid UTF-8.", "format", "tcad.log.v1"
        lowered = text.lower()
        passed = not any(
            marker in lowered
            for marker in ("fatal error", "segmentation fault", "aborted")
        )
        return (
            passed,
            "Solver log has no declared fatal marker."
            if passed
            else "Solver log contains a fatal marker.",
            "format",
            "tcad.log.v1",
        )
    return _parse_finite_numeric_table(assertion, output, raw)


def _parse_finite_numeric_table(
    assertion: RuntimeAssertion,
    output: RuntimeOutputRecord,
    raw: bytes,
) -> tuple[bool, str, Literal["numeric"], str]:
    suffix = Path(output.relative_path).suffix.lower()
    provider_id = (
        "tcad.plx-text-table.v1" if suffix == ".plx" else "tcad.plt-text-table.v1"
    )
    if suffix not in {".plx", ".plt"}:
        return (
            False,
            "No numeric-table provider matches the output path.",
            "numeric",
            provider_id,
        )
    try:
        lines = [
            line.split() for line in raw.decode("utf-8").splitlines() if line.strip()
        ]
    except UnicodeDecodeError:
        return False, "Numeric table is not valid UTF-8.", "numeric", provider_id
    if not lines:
        return False, "Numeric table is empty.", "numeric", provider_id
    first_is_numeric = all(_finite_number(token) for token in lines[0])
    header = () if first_is_numeric else tuple(lines.pop(0))
    if assertion.required_columns and not set(assertion.required_columns).issubset(
        header
    ):
        return (
            False,
            "Numeric table is missing required columns.",
            "numeric",
            provider_id,
        )
    width = len(header) if header else len(lines[0]) if lines else 0
    passed = (
        len(lines) >= assertion.min_numeric_rows
        and width > 0
        and all(
            len(row) == width and all(_finite_number(item) for item in row)
            for row in lines
        )
    )
    return (
        passed,
        "Numeric table has the required columns, rows, and finite values."
        if passed
        else "Numeric table is truncated, non-finite, or structurally inconsistent.",
        "numeric",
        provider_id,
    )


def _finite_number(value: str) -> bool:
    try:
        return math.isfinite(float(value))
    except ValueError:
        return False


def _write_archive(
    files: tuple[DeckFile, ...],
    binary_files: Mapping[str, bytes],
    archive_path: Path,
) -> tuple[ArchiveEntry, ...]:
    entries: list[ArchiveEntry] = []
    contents = {
        item.relative_path: item.content.encode("utf-8") for item in files
    }
    contents.update(binary_files)
    with tarfile.open(archive_path, "w", format=tarfile.USTAR_FORMAT) as archive:
        for relative_path, raw in sorted(contents.items()):
            info = tarfile.TarInfo(relative_path)
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
                    relative_path=relative_path,
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
    "DeckProjectDraft",
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
    "CaseParameterBinding",
    "MaterializationFinding",
    "ParameterBinding",
    "ProjectInputSlot",
    "ProjectExpectedOutput",
    "ProjectMaterializationReport",
    "ProjectPreflightAttestation",
    "ProjectResourceLimits",
    "RealizationRequirement",
    "ResolvedProjectInput",
    "RuntimeAssertion",
    "attest_runtime_contract",
    "deck_project_diff",
    "package_deck_project",
    "package_reviewed_deck_json",
    "validate_deck_project_output",
    "validate_deck_author_task_output",
    "deck_scoped_comparison_variable",
    "validate_project_case_controls",
    "validate_deck_review_against_project",
    "validate_deck_review_report",
    "validate_deck_review_task_output",
    "solver_deck_scope_violations",
    "validate_reviewed_deck_json",
]
